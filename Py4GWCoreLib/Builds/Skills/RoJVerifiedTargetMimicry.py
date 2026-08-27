from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any

import PyGameThread
import PySkillbar

from Py4GWCoreLib import Agent, GLOBAL_CACHE, Party, Player, Profession, Range, Routines, Utils
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Skillbar import SkillBar


@dataclass
class _VerifiedDonor:
    login: int
    agent_id: int
    skills: tuple[int, ...]


class RoJVerifiedTargetMimicry:
    """Arcane Mimicry with a hard CURRENT-TARGET safety gate.

    Live A/B evidence:
      - Para present + HR equipped -> HR copied
      - Para present + no elite -> Mimicry recharged but copied nothing
      - Para absent -> RoJ copied correctly

    Therefore the actual Guild Wars target at cast time is authoritative.

    This controller NEVER asks Mimicry to cast merely because a target_agent_id
    was supplied to UseSkill.  Instead it behaves like a human:
      1) identify a verified other-account RoJ Monk from Shared Memory;
      2) map that account's LOGIN to this client's LOCAL party AgentID;
      3) physically select that Monk;
      4) wait until Player.GetTargetID() confirms the Monk for multiple ticks;
      5) revalidate that exact current target as Mo/Me + native RoJ donor;
      6) inside one game-thread callback, check the current target AGAIN;
      7) only then use Arcane Mimicry on the CURRENT target (target id 0).

    If the HR Paragon is current target at the final check, NO CAST occurs.
    """

    TARGET_STABLE_SECONDS = 0.12
    ACQUIRE_TIMEOUT_SECONDS = 1.25
    MAX_TARGET_CHANGE_ATTEMPTS = 4
    DISPATCH_TIMEOUT_SECONDS = 0.50
    COPY_TIMEOUT_SECONDS = 5.0
    RETRY_BACKOFF_SECONDS = 1.0

    def __init__(self) -> None:
        self.arcane_id = int(Skill.GetID("Arcane_Mimicry") or 0)
        self.roj_id = int(Skill.GetID("Ray_of_Judgment") or 0)
        self.echo_id = int(Skill.GetID("Arcane_Echo") or 0)

        self.mimicry_slot = 0
        self.state = "idle"
        self.donor_login = 0
        self.donor_agent = 0
        self.donor_skills: tuple[int, ...] = ()
        self.previous_target = 0
        self.started_at = 0.0
        self.target_stable_since = 0.0
        self.target_change_attempts = 0
        self.dispatch_started = 0.0
        self.dispatch_result = ""
        self.copy_started = 0.0
        self.retry_not_before = 0.0
        self.last_result = ""
        self._last_log_key = ""

    @staticmethod
    def _as_int(value: Any) -> int:
        try:
            return int(getattr(value, "value", value))
        except Exception:
            return 0

    @staticmethod
    def _log(event: str, **fields: Any) -> None:
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(event, **fields)
        except Exception:
            pass

    def _log_once(self, key: str, event: str, **fields: Any) -> None:
        if key == self._last_log_key:
            return
        self._last_log_key = key
        self._log(event, **fields)

    def _ensure_slot(self) -> int:
        if self.mimicry_slot > 0:
            return self.mimicry_slot
        try:
            slot = int(SkillBar.GetSlotBySkillID(self.arcane_id) or 0)
            if slot > 0 and int(SkillBar.GetSkillIDBySlot(slot) or 0) == self.arcane_id:
                self.mimicry_slot = slot
        except Exception:
            self.mimicry_slot = 0
        return self.mimicry_slot

    @staticmethod
    def _shared_skills(account: Any) -> tuple[int, ...]:
        result: list[int] = []
        try:
            skillbar = getattr(getattr(account, "AgentData", None), "Skillbar", None)
            for item in (getattr(skillbar, "Skills", []) if skillbar is not None else []):
                sid = int(getattr(item, "Id", 0) or 0)
                if sid > 0:
                    result.append(sid)
        except Exception:
            pass
        return tuple(result)

    @staticmethod
    def _shared_login(account: Any) -> int:
        try:
            return int(getattr(getattr(account, "AgentData", None), "LoginNumber", 0) or 0)
        except Exception:
            return 0

    def _shared_roj_professions(self, account: Any) -> bool:
        try:
            professions = getattr(getattr(account, "AgentData", None), "Profession", (0, 0))
            return bool(
                int(professions[0] or 0) == self._as_int(Profession.Monk)
                and int(professions[1] or 0) == self._as_int(Profession.Mesmer)
            )
        except Exception:
            return False

    def _skills_are_native_roj_donor(self, skills: tuple[int, ...]) -> bool:
        """Accept only the strict RoJ/Echo/Mimicry build contract.

        Echo and Mimicry temporarily replace their own slots with RoJ.  One
        native RoJ plus one extra RoJ for every missing copy skill therefore
        proves that the donor still has the required build while a copy is
        active.  A Monk with another native elite can never pass the elite gate.
        """
        if not all(sid > 0 for sid in (self.roj_id, self.echo_id, self.arcane_id)):
            return False
        if self.roj_id not in skills:
            return False

        missing_copy_skills = sum(
            1 for sid in (self.echo_id, self.arcane_id)
            if sid not in skills
        )
        temporary_roj_copies = max(0, skills.count(self.roj_id) - 1)
        if temporary_roj_copies < missing_copy_skills:
            return False

        # Native RoJ must be the only elite identity currently exposed.  Two or
        # three RoJ entries are legal while Echo/Mimicry copies occupy slots.
        elites: list[int] = []
        for sid in skills:
            try:
                if Skill.Flags.IsElite(int(sid)):
                    elites.append(int(sid))
            except Exception:
                continue
        return bool(elites and all(sid == self.roj_id for sid in elites))

    def _live_roj_professions(self, agent_id: int) -> bool:
        try:
            primary, secondary = Agent.GetProfessionIDs(int(agent_id))
            return bool(
                self._as_int(primary) == self._as_int(Profession.Monk)
                and self._as_int(secondary) == self._as_int(Profession.Mesmer)
            )
        except Exception:
            return False

    def _in_range(self, agent_id: int) -> bool:
        try:
            return (
                Agent.IsValid(int(agent_id))
                and Agent.IsAlive(int(agent_id))
                and Utils.Distance(Player.GetXY(), Agent.GetXY(int(agent_id)))
                <= float(Range.Spellcast.value)
            )
        except Exception:
            return False

    def _candidate_donors(self) -> list[_VerifiedDonor]:
        """Shared account discovery, but LOCAL party AgentID is authoritative."""
        try:
            from Py4GWCoreLib.HeroAI.utils import SameMapOrPartyAsAccount
        except Exception:
            SameMapOrPartyAsAccount = lambda _account: True

        own_login = int(Player.GetLoginNumber() or 0)
        own_agent = int(Player.GetAgentID() or 0)
        try:
            own_party = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
        except Exception:
            own_party = 0

        result: dict[int, _VerifiedDonor] = {}
        try:
            accounts = GLOBAL_CACHE.ShMem.GetAllAccountData() or []
        except Exception:
            accounts = []

        for account in accounts:
            try:
                if not getattr(account, "IsSlotActive", False) or getattr(account, "IsIsolated", False):
                    continue
                if not SameMapOrPartyAsAccount(account):
                    continue
                party_id = int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)
                if own_party > 0 and party_id > 0 and party_id != own_party:
                    continue
                if not self._shared_roj_professions(account):
                    continue

                login = self._shared_login(account)
                if login <= 0 or login == own_login:
                    continue

                skills = self._shared_skills(account)
                if not self._skills_are_native_roj_donor(skills):
                    continue

                # CRITICAL: never use Shared-Memory AgentData.AgentID as the cast target.
                # Resolve the account LOGIN through THIS client's actual party.
                agent_id = int(Party.Players.GetAgentIDByLoginNumber(login) or 0)
                if agent_id <= 0 or agent_id == own_agent:
                    continue
                if not self._live_roj_professions(agent_id):
                    continue
                if not self._in_range(agent_id):
                    continue

                try:
                    live_login = int(Agent.GetLoginNumber(agent_id) or 0)
                except Exception:
                    live_login = 0
                if live_login > 0 and live_login != login:
                    continue

                result[login] = _VerifiedDonor(login, agent_id, skills)
            except Exception:
                continue

        # Stable deterministic order; distance first so an in-range nearby Monk wins.
        donors = list(result.values())
        donors.sort(
            key=lambda d: (
                Utils.Distance(Player.GetXY(), Agent.GetXY(d.agent_id))
                if Agent.IsValid(d.agent_id) else 999999.0,
                d.login,
            )
        )
        return donors

    def _find_donor(self) -> _VerifiedDonor | None:
        donors = self._candidate_donors()
        return donors[0] if donors else None

    def get_slot(self) -> int:
        return int(self._ensure_slot() or 0)

    def is_busy(self) -> bool:
        return str(self.state) != "idle"

    def can_start(self) -> bool:
        return bool(
            self.state == "idle"
            and monotonic() >= float(self.retry_not_before or 0.0)
        )

    def has_verified_donor(self) -> bool:
        return self._find_donor() is not None

    def _donor_still_valid(self) -> bool:
        if self.donor_login <= 0 or self.donor_agent <= 0:
            return False
        for donor in self._candidate_donors():
            if donor.login == self.donor_login and donor.agent_id == self.donor_agent:
                self.donor_skills = donor.skills
                return True
        return False

    def _current_target_is_verified_donor(self) -> bool:
        """The final safety gate. Para/HR and non-Mesmer Monks cannot pass."""
        current = int(Player.GetTargetID() or 0)
        if current <= 0 or current != int(self.donor_agent):
            return False
        if not self._live_roj_professions(current):
            return False
        if not self._in_range(current):
            return False
        if not self._donor_still_valid():
            return False
        return True

    def _reset(
        self,
        result: str,
        *,
        restore: bool = False,
        retry_delay_seconds: float = 0.0,
    ) -> None:
        old_target = int(self.previous_target or 0)
        self.state = "idle"
        self.donor_login = 0
        self.donor_agent = 0
        self.donor_skills = ()
        self.started_at = 0.0
        self.target_stable_since = 0.0
        self.target_change_attempts = 0
        self.dispatch_started = 0.0
        self.dispatch_result = ""
        self.copy_started = 0.0
        self.retry_not_before = monotonic() + max(0.0, float(retry_delay_seconds))
        self.last_result = result
        self._last_log_key = ""
        if restore and old_target > 0:
            try:
                Player.ChangeTarget(old_target)
            except Exception:
                pass
        self.previous_target = 0

    def observe(self) -> None:
        slot = self._ensure_slot()
        if slot <= 0:
            return
        try:
            current_skill = int(SkillBar.GetSkillIDBySlot(slot) or 0)
        except Exception:
            return

        # The physical slot is more authoritative than the queued callback's
        # bookkeeping.  In the Phase-2 logs the slot had already become RoJ,
        # but state was still ``dispatch_wait``; the old early-return then held
        # the whole Monk idle until the 20-second copy expired.
        if self.state in ("dispatch_wait", "observe_copy"):
            if current_skill == self.roj_id:
                self._log(
                    "MIMICRY_ROJ_VERIFIED_COPY_OK",
                    donor_login=int(self.donor_login),
                    donor_agent=int(self.donor_agent),
                    current_target=int(Player.GetTargetID() or 0),
                    slot=int(slot),
                    observed_from_state=str(self.state),
                )
                self._reset("copy_ok", restore=True)
                return

            if current_skill not in (0, self.arcane_id, self.roj_id):
                try:
                    copied_prof_id, copied_prof_name = Skill.GetProfession(current_skill)
                except Exception:
                    copied_prof_id, copied_prof_name = 0, ""
                self._log(
                    "MIMICRY_ROJ_VERIFIED_COPY_WRONG",
                    copied_skill_id=int(current_skill),
                    copied_profession_id=int(copied_prof_id or 0),
                    copied_profession=str(copied_prof_name or ""),
                    donor_login=int(self.donor_login),
                    donor_agent=int(self.donor_agent),
                    current_target=int(Player.GetTargetID() or 0),
                    slot=int(slot),
                )
                self._reset(f"wrong_copy:{current_skill}", restore=True)
                return

            if self.copy_started > 0 and monotonic() - self.copy_started >= self.COPY_TIMEOUT_SECONDS:
                self._log(
                    "MIMICRY_ROJ_VERIFIED_COPY_TIMEOUT",
                    donor_login=int(self.donor_login),
                    donor_agent=int(self.donor_agent),
                    current_target=int(Player.GetTargetID() or 0),
                    slot=int(slot),
                )
                self._reset("copy_timeout", restore=True)

    def _begin(self, donor: _VerifiedDonor) -> None:
        self.previous_target = int(Player.GetTargetID() or 0)
        self.donor_login = int(donor.login)
        self.donor_agent = int(donor.agent_id)
        self.donor_skills = donor.skills
        self.started_at = monotonic()
        self.target_stable_since = 0.0
        self.target_change_attempts = 0
        self.state = "acquire_target"
        self._log(
            "MIMICRY_ROJ_TARGET_LOCK_BEGIN",
            donor_login=int(donor.login),
            donor_agent=int(donor.agent_id),
            previous_target=int(self.previous_target),
            donor_skills=",".join(str(x) for x in donor.skills),
        )

    def run(self, build: Any):
        if False:
            yield None

        self.observe()

        slot = self._ensure_slot()
        if slot <= 0:
            return False

        try:
            slot_skill = int(SkillBar.GetSkillIDBySlot(slot) or 0)
        except Exception:
            return False

        # A copied elite already occupies the physical Mimicry slot.
        if slot_skill != self.arcane_id:
            return False

        # Once target acquisition starts, this controller OWNS the skill tick
        # until Mimicry is either dispatched or safely aborted.
        if self.state == "idle":
            if monotonic() < float(self.retry_not_before or 0.0):
                return False
            try:
                if not build.CanCastSkillID(self.arcane_id):
                    return False
            except Exception:
                if not Routines.Checks.Skills.CanCast():
                    return False

            donor = self._find_donor()
            if donor is None:
                self._log_once(
                    "no_donor",
                    "MIMICRY_ROJ_NO_VERIFIED_DONOR",
                    current_target=int(Player.GetTargetID() or 0),
                )
                return False
            self._begin(donor)
            return True

        if self.state == "acquire_target":
            if monotonic() - self.started_at >= self.ACQUIRE_TIMEOUT_SECONDS:
                self._log(
                    "MIMICRY_ROJ_TARGET_LOCK_TIMEOUT",
                    donor_login=int(self.donor_login),
                    donor_agent=int(self.donor_agent),
                    current_target=int(Player.GetTargetID() or 0),
                )
                self._reset(
                    "target_timeout",
                    restore=True,
                    retry_delay_seconds=self.RETRY_BACKOFF_SECONDS,
                )
                return True

            if not self._donor_still_valid():
                self._reset(
                    "donor_invalid",
                    restore=True,
                    retry_delay_seconds=self.RETRY_BACKOFF_SECONDS,
                )
                return True

            current = int(Player.GetTargetID() or 0)
            if current != self.donor_agent:
                if self.target_stable_since > 0.0:
                    self._log(
                        "MIMICRY_ROJ_TARGET_LOCK_ABORTED",
                        reason="confirmed_target_was_stolen",
                        donor_login=int(self.donor_login),
                        donor_agent=int(self.donor_agent),
                        current_target=int(current),
                    )
                    self._reset(
                        "target_stolen",
                        restore=True,
                        retry_delay_seconds=self.RETRY_BACKOFF_SECONDS,
                    )
                    return True

                self.target_stable_since = 0.0
                self.target_change_attempts += 1
                if self.target_change_attempts > self.MAX_TARGET_CHANGE_ATTEMPTS:
                    self._log(
                        "MIMICRY_ROJ_TARGET_LOCK_ABORTED",
                        reason="target_not_acquired",
                        donor_login=int(self.donor_login),
                        donor_agent=int(self.donor_agent),
                        current_target=int(current),
                        attempts=int(self.target_change_attempts),
                    )
                    self._reset(
                        "target_not_acquired",
                        restore=True,
                        retry_delay_seconds=self.RETRY_BACKOFF_SECONDS,
                    )
                    return True
                try:
                    # Queued target change is OK here because we DO NOT cast yet.
                    # A later tick must positively observe Player.GetTargetID().
                    Player.ChangeTarget(int(self.donor_agent))
                except Exception:
                    pass
                self._log_once(
                    f"targeting:{current}:{self.donor_agent}",
                    "MIMICRY_ROJ_TARGETING_DONOR",
                    donor_login=int(self.donor_login),
                    donor_agent=int(self.donor_agent),
                    current_target=int(current),
                )
                return True

            # Even though the ID matches, confirm the live target is Mo/Me.
            if not self._current_target_is_verified_donor():
                self.target_stable_since = 0.0
                return True

            now = monotonic()
            if self.target_stable_since <= 0:
                self.target_stable_since = now
                self._log(
                    "MIMICRY_ROJ_TARGET_CONFIRMED",
                    donor_login=int(self.donor_login),
                    donor_agent=int(self.donor_agent),
                    current_target=int(current),
                    live_professions="Monk/Mesmer",
                )
                return True

            if now - self.target_stable_since < self.TARGET_STABLE_SECONDS:
                return True

            # Revalidate CanCast only after the target has been stable.
            try:
                if not build.CanCastSkillID(self.arcane_id):
                    return True
            except Exception:
                if not Routines.Checks.Skills.CanCast():
                    return True

            self.state = "dispatch"
            return True

        if self.state == "dispatch":
            # NO CAST unless CURRENT TARGET is still the verified RoJ Monk.
            if not self._current_target_is_verified_donor():
                self.state = "acquire_target"
                self.target_stable_since = 0.0
                return True

            donor_id = int(self.donor_agent)
            donor_login = int(self.donor_login)
            slot_i = int(slot)
            self.dispatch_result = "queued"
            self.dispatch_started = monotonic()
            self.state = "dispatch_wait"

            def _guarded_current_target_cast():
                try:
                    current = int(Player.GetTargetID() or 0)
                    # Final in-game-thread gate: if Para/HR stole target, abort.
                    if current != donor_id:
                        self.dispatch_result = f"target_changed:{current}"
                        return
                    primary, secondary = Agent.GetProfessionIDs(current)
                    if (
                        self._as_int(primary) != self._as_int(Profession.Monk)
                        or self._as_int(secondary) != self._as_int(Profession.Mesmer)
                    ):
                        self.dispatch_result = f"not_roj_professions:{current}"
                        return
                    if not Agent.IsValid(current) or not Agent.IsAlive(current):
                        self.dispatch_result = f"invalid_target:{current}"
                        return

                    # Cast on CURRENT selected target, not on a passed target_agent_id.
                    PySkillbar.Skillbar().UseSkill(slot_i, 0)
                    self.dispatch_result = "issued"
                except Exception as exc:
                    self.dispatch_result = f"error:{type(exc).__name__}"

            PyGameThread.enqueue(_guarded_current_target_cast)
            self._log(
                "MIMICRY_ROJ_GUARDED_CAST_QUEUED",
                donor_login=donor_login,
                donor_agent=donor_id,
                current_target=int(Player.GetTargetID() or 0),
                policy="current_target_must_equal_verified_primary_monk_then_use_target_0",
            )
            return True

        if self.state == "dispatch_wait":
            result = str(self.dispatch_result or "")
            if result == "issued":
                self.copy_started = monotonic()
                self.state = "observe_copy"
                self._log(
                    "MIMICRY_ROJ_GUARDED_CAST_ISSUED",
                    donor_login=int(self.donor_login),
                    donor_agent=int(self.donor_agent),
                    current_target=int(Player.GetTargetID() or 0),
                )
                return True

            if result and result != "queued":
                self._log(
                    "MIMICRY_ROJ_GUARDED_CAST_ABORTED",
                    reason=result,
                    donor_login=int(self.donor_login),
                    donor_agent=int(self.donor_agent),
                    current_target=int(Player.GetTargetID() or 0),
                )
                self._reset(
                    f"dispatch_aborted:{result}",
                    restore=True,
                    retry_delay_seconds=self.RETRY_BACKOFF_SECONDS,
                )
                return True

            if monotonic() - self.dispatch_started >= self.DISPATCH_TIMEOUT_SECONDS:
                self._log(
                    "MIMICRY_ROJ_GUARDED_CAST_ABORTED",
                    reason="dispatch_timeout",
                    donor_login=int(self.donor_login),
                    donor_agent=int(self.donor_agent),
                    current_target=int(Player.GetTargetID() or 0),
                )
                self._reset(
                    "dispatch_timeout",
                    restore=True,
                    retry_delay_seconds=self.RETRY_BACKOFF_SECONDS,
                )
            return True

        if self.state == "observe_copy":
            # Keep this tick reserved while the copied-skill transition arrives.
            # Do not retarget to an enemy until copy success/wrong/timeout.
            return True

        return False
