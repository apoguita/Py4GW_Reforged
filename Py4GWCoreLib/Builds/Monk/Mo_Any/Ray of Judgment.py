from __future__ import annotations

import time

from Py4GWCoreLib import AgentArray, GLOBAL_CACHE
from Py4GWCoreLib import Profession
from Py4GWCoreLib import Range
from Py4GWCoreLib import Routines
from Py4GWCoreLib import BuildMgr
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Skills import HexRemovalPriority, SkillsTemplate
from Py4GWCoreLib.Builds.Skills.RoJVerifiedTargetMimicry import RoJVerifiedTargetMimicry
from Py4GWCoreLib.Builds.Skills.AoEDangerPrediction import (
    avoid_active_aoe_if_needed,
    refresh_aoe_danger_zones,
)


Ray_of_Judgment_ID = Skill.GetID("Ray_of_Judgment")
Arcane_Mimicry_ID = Skill.GetID("Arcane_Mimicry")
Auspicious_Incantation_ID = Skill.GetID("Auspicious_Incantation")
Symbol_of_Wrath_ID = Skill.GetID("Symbol_of_Wrath")
Bane_Signet_ID = Skill.GetID("Bane_Signet")  # German: Siegel des Ruins
Patient_Spirit_ID = Skill.GetID("Patient_Spirit")
Dwaynas_Kiss_ID = Skill.GetID("Dwaynas_Kiss")
Cure_Hex_ID = Skill.GetID("Cure_Hex")
Shield_of_Absorption_ID = Skill.GetID("Shield_of_Absorption")
Smite_Hex_ID = Skill.GetID("Smite_Hex")
Air_of_Superiority_ID = Skill.GetID("Air_of_Superiority")
Arcane_Echo_ID = Skill.GetID("Arcane_Echo")
Reversal_of_Damage_ID = Skill.GetID("Reversal_of_Damage")


# Conservative dangerous-cast list. This intentionally mirrors the stable
# Keystone safe version: explicit SkillID checks only, no broad metadata scans.
_SAFE_DANGER_CAST_SKILL_NAMES = (
    # Elementalist / AoE pressure
    "Meteor_Shower", "Savannah_Heat", "Searing_Heat", "Rodgorts_Invocation",
    "Rodgort's_Invocation", "Deep_Freeze", "Maelstrom", "Earthquake",
    "Churning_Earth", "Sandstorm", "Fire_Storm", "Eruption",
    "Invoke_Lightning", "Chain_Lightning", "Obsidian_Flame",
    # Mesmer shutdown / pressure
    "Panic", "Energy_Surge", "Mistrust", "Cry_of_Frustration",
    "Visions_of_Regret", "Backfire", "Empathy", "Shame", "Diversion",
    # Necromancer pressure
    "Spiteful_Spirit", "Spoil_Victor", "Mark_of_Pain", "Barbs",
    "Feast_of_Corruption", "Rising_Bile", "Putrid_Explosion",
    # Monk / Ritualist control, prot, heal, resurrection
    "Ray_of_Judgment", "Signet_of_Judgment", "Shield_of_Judgment",
    "Aegis", "Protective_Spirit", "Spirit_Bond", "Word_of_Healing",
    "Heal_Area", "Heavens_Delight", "Divine_Healing",
    "Restore_Life", "Resurrection_Chant", "Flesh_of_My_Flesh",
    "Death_Pact_Signet", "Renew_Life",
)

_SAFE_HEALER_FOCUS_SKILL_NAMES = (
    # Monk healing
    "Patient_Spirit", "Dwaynas_Kiss", "Dwayna's_Kiss", "Orison_of_Healing",
    "Healing_Breeze", "Heal_Other", "Healing_Touch", "Healing_Seed",
    "Seed_of_Life", "Gift_of_Health", "Jameis_Gaze", "Jamei's_Gaze",
    "Ethereal_Light", "Healing_Ribbon", "Heal_Party", "Light_of_Dwayna",
    "Infuse_Health", "Healing_Hands",
    # Monk protection / condition / hex control
    "Reversal_of_Fortune", "Shielding_Hands", "Guardian", "Shield_of_Absorption",
    "Life_Sheath", "Mark_of_Protection", "Shield_Guardian", "Mend_Ailment",
    "Mend_Condition", "Draw_Conditions", "Restore_Condition", "Remove_Hex",
    "Convert_Hexes", "Deny_Hexes", "Holy_Veil",
    # Ritualist healing / protection
    "Spirit_Light", "Mend_Body_and_Soul", "Spirit_Transfer", "Soothing_Memories",
    "Wielders_Boon", "Wielder's_Boon", "Weapon_of_Warding", "Weapon_of_Shadow",
    "Vengeful_Weapon", "Resilient_Weapon", "Protective_Was_Kaolai",
    "Life", "Preservation", "Recuperation", "Recovery", "Shelter", "Union", "Displacement",
)

_SAFE_DANGER_CAST_SKILL_IDS = frozenset(
    int(skill_id)
    for skill_id in (Skill.GetID(name) for name in _SAFE_DANGER_CAST_SKILL_NAMES)
    if int(skill_id or 0) > 0
)

_SAFE_HEALER_FOCUS_SKILL_IDS = frozenset(
    int(skill_id)
    for skill_id in (Skill.GetID(name) for name in _SAFE_HEALER_FOCUS_SKILL_NAMES)
    if int(skill_id or 0) > 0
)

# TeamCombatFocus owns the decision between a real packet and sequential
# cleanup.  It is a shared RoJway resolver and does not require a Keystone
# Mesmer to be present. A two-enemy minimum is the only local input it receives.
ROJ_ACCEPTABLE_PACKET_MIN = 2

# Shared RoJ carpet coordination.  Ray of Judgment is a five-second ground
# effect, so a 5250 ms lease describes real coverage rather than only the cast
# animation.  The 930 ms lane is the already runtime-proven multibox cadence:
# one new ray roughly every second, spread inside TeamCombatFocus' one packet.
ROJ_TEAM_CAST_LANE_MS = 930
ROJ_COVERAGE_WINDOW_MS = 5250
# The real normal cap is adaptive (3/4/6 depending on packet size). Seven is
# only the absolute semaphore ceiling for one urgent expiring copy or the
# requested <=5% finisher on a large packet.
ROJ_MAX_CLUSTER_EMERGENCY_COVERAGE = 7
ROJ_MAX_TARGET_COVERAGE = 3
ROJ_LOW_HP_FINISH_THRESHOLD = 0.05
ROJ_HARD_FOCUS_THRESHOLD = 0.10
ROJ_TEAM_LANE_LOCK_ID = 0x524F4A4C
ROJ_CLUSTER_COVERAGE_LOCK_ID = 0x524F4A43
ROJ_TARGET_COVERAGE_LOCK_ID = 0x524F4A54
ROJ_LOW_HP_FINISH_LOCK_ID = 0x524F4A46
ROJ_LANE_ELECTION_STEP_MS = 22
ROJ_LANE_ELECTION_MAX_AGE_MS = 1500

# Symbol follows the same authoritative packet and distribution rules. It is
# deliberately a small filler budget and also counts existing RoJ coverage,
# while RoJ never counts Symbol; therefore an optional Symbol can never reserve
# or block a required RoJ layer.
SYMBOL_TEAM_CAST_LANE_MS = 680
SYMBOL_MAX_CLUSTER_COVERAGE = 2
SYMBOL_MAX_TARGET_COVERAGE = 1
SYMBOL_TEAM_LANE_LOCK_ID = 0x53594D4C
SYMBOL_CLUSTER_COVERAGE_LOCK_ID = 0x53594D43
SYMBOL_TARGET_COVERAGE_LOCK_ID = 0x53594D54
SYMBOL_LANE_ELECTION_STEP_MS = 18

# Bane Signet is instant damage plus conditional control, not another ground
# field.  Its short leases only stagger accounts during the one-second
# activation; they never count as RoJ/Symbol coverage and therefore cannot
# reserve or delay a ready native/copied RoJ.
BANE_TEAM_CAST_LANE_MS = 420
BANE_TARGET_RESERVATION_MS = 1150
BANE_TEAM_LANE_LOCK_ID = 0x42414E4C
BANE_TARGET_LOCK_ID = 0x42414E54
BANE_LANE_ELECTION_STEP_MS = 16

# The protected native-first sequence spans several real cast animations plus
# Mimicry's verified target acquisition. While it is active no support/filler
# skill is allowed to enter between its steps.
ROJ_CHAIN_TIMEOUT_MS = 15000.0
ROJ_ECHO_COPY_APPEAR_TIMEOUT_MS = 5000.0
ROJ_TEMP_COPY_DURATION_MS = 20000.0
ROJ_TEMP_COPY_REQUIRED_CASTS = 2
ROJ_TEMP_COPY_URGENT_WINDOW_MS = 3000.0
ROJ_TEMP_COPY_CAST_GUARD_MS = 6000.0
ROJ_CHAIN_STEP_AFTERCAST_MS = 250
ROJ_NATIVE_ECHO_PREARM_SAFETY_MS = 650.0
ROJ_NATIVE_ECHO_PREARM_WINDOW_MS = 1250.0
ROJ_CHAIN_IDLE = "idle"
ROJ_CHAIN_NATIVE_ROJ = "native_roj"
ROJ_CHAIN_MIMICRY = "mimicry"
ROJ_CHAIN_ECHO = "echo"
ROJ_CHAIN_MIMICRY_ROJ = "mimicry_roj"
ROJ_CHAIN_NATIVE_ECHO_SETUP = "native_echo_setup"
ROJ_CHAIN_NATIVE_ECHO_ROJ = "native_echo_roj"
ROJ_CHAIN_ECHO_COPY = "echo_copy"

# Urgoz override: German "Krummrinde" = English "Twisted Bark". These
# targets maintain room-wide effects and should be deleted before normal packet
# logic.
ELITE_PRIORITY_TARGET_NAMES = ("twisted bark", "krummrinde", "crooked bark")


class Ray_of_Judgment(BuildMgr):
    def __init__(self, match_only: bool = False):
        super().__init__(
            name="HR RoJ - Adaptive Team Focus Phase 3.7 Bane Filler",
            required_primary=Profession.Monk,
            required_secondary=Profession.Mesmer,
            template_code="OwAAAAAAAAAAAAAAAAAAAAAA",
            required_skills=[
                Ray_of_Judgment_ID,
                Arcane_Echo_ID,
                Arcane_Mimicry_ID,
            ],
            optional_skills=[
                Auspicious_Incantation_ID,
                Symbol_of_Wrath_ID,
                Bane_Signet_ID,
                Air_of_Superiority_ID,
                Reversal_of_Damage_ID,
                Patient_Spirit_ID,
                Dwaynas_Kiss_ID,
                Cure_Hex_ID,
                Smite_Hex_ID,
                Shield_of_Absorption_ID,
            ],
        )
        if match_only:
            return

        # This build owns every supported slot locally; there is deliberately
        # no generic HeroAI fallback.  Mimicry is dispatched only by the strict
        # verified-native-RoJ controller below.
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skills: SkillsTemplate = SkillsTemplate(self)
        self._roj_mimicry = RoJVerifiedTargetMimicry()
        self._roj_chain_state = ROJ_CHAIN_IDLE
        self._roj_chain_started_ms = 0.0
        self._roj_chain_seed_cast_ms = 0.0
        self._roj_chain_native_target_id = 0
        self._roj_chain_echo_slot = 0
        self._last_ray_of_judgment_target_id = 0
        self._last_ray_of_judgment_cast_ts_ms = 0.0
        self._native_roj_slot = int(
            GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Ray_of_Judgment_ID) or 0
        )
        self._arcane_echo_home_slot = int(
            GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Arcane_Echo_ID) or 0
        )
        self._arcane_mimicry_home_slot = int(
            GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Arcane_Mimicry_ID) or 0
        )
        self._roj_copy_slots: dict[int, dict[str, int | float | str]] = {}
        self._mimicry_energy_wait_logged = False
        self._last_coordination_wait_reason = ""
        self._last_coordination_wait_log_ms = 0.0
        self._roj_lane_first_seen: dict[int, int] = {}
        self._symbol_lane_first_seen: dict[int, int] = {}
        self._bane_lane_first_seen: dict[int, int] = {}

    def ScoreMatch(
        self,
        current_primary=None,
        current_secondary=None,
        current_skills: list[int] | None = None,
    ) -> int:
        """Keep the contract while Echo and/or Mimicry display copied RoJ.

        HeroAI includes the live skill IDs in its contract signature and
        re-scores the bar whenever a slot changes.  During Arcane Echo the bar
        temporarily contains two or three RoJ IDs and is missing one or both
        copy-skill IDs.  Without this narrow normalization the resolver would
        hand control back to generic HeroAI while copied RoJs must be spent.

        The normal/initial match remains strict: RoJ, Arcane Echo and Arcane
        Mimicry are all required.  Only impossible-to-equip duplicate RoJs may
        stand in for currently transformed Echo/Mimicry slots.
        """
        score = super().ScoreMatch(
            current_primary=current_primary,
            current_secondary=current_secondary,
            current_skills=current_skills,
        )
        if score >= 0:
            return int(score)

        skills = list(current_skills) if current_skills is not None else self._get_current_skills()
        missing_copy_skills = [
            skill_id
            for skill_id in (Arcane_Echo_ID, Arcane_Mimicry_ID)
            if int(skill_id) not in skills
        ]
        temporary_roj_copies = max(0, skills.count(int(Ray_of_Judgment_ID)) - 1)
        if not missing_copy_skills or temporary_roj_copies < len(missing_copy_skills):
            return int(score)

        normalized_skills: list[int] = []
        seen_native_roj = False
        replacement_index = 0
        for skill_id in skills:
            skill_id = int(skill_id or 0)
            if skill_id == int(Ray_of_Judgment_ID):
                if seen_native_roj and replacement_index < len(missing_copy_skills):
                    normalized_skills.append(int(missing_copy_skills[replacement_index]))
                    replacement_index += 1
                    continue
                seen_native_roj = True
            normalized_skills.append(skill_id)

        return int(super().ScoreMatch(
            current_primary=current_primary,
            current_secondary=current_secondary,
            current_skills=normalized_skills,
        ))

    @staticmethod
    def _now_ms() -> float:
        return time.monotonic() * 1000.0

    def _get_native_roj_slot(self) -> int:
        slot = int(getattr(self, "_native_roj_slot", 0) or 0)
        if 1 <= slot <= 8:
            return slot
        slot = int(GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Ray_of_Judgment_ID) or 0)
        if 1 <= slot <= 8:
            self._native_roj_slot = slot
        return slot

    def _get_echo_home_slot(self) -> int:
        slot = int(getattr(self, "_arcane_echo_home_slot", 0) or 0)
        if 1 <= slot <= 8:
            return slot
        slot = int(GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Arcane_Echo_ID) or 0)
        if 1 <= slot <= 8:
            self._arcane_echo_home_slot = slot
        return slot

    def _get_mimicry_home_slot(self) -> int:
        slot = int(getattr(self, "_arcane_mimicry_home_slot", 0) or 0)
        if 1 <= slot <= 8:
            return slot
        try:
            slot = int(self._roj_mimicry.get_slot() or 0)
        except Exception:
            slot = 0
        if 1 <= slot <= 8:
            self._arcane_mimicry_home_slot = slot
        return slot

    def _temporary_roj_source(self, slot: int) -> str:
        if int(slot) == self._get_echo_home_slot():
            return "arcane_echo"
        if int(slot) == self._get_mimicry_home_slot():
            return "arcane_mimicry"
        return "temporary_copy"

    def _refresh_temporary_roj_slots(self) -> None:
        primary_slot = self._get_native_roj_slot()
        now_ms = self._now_ms()
        active_slots: set[int] = set()

        for slot in range(1, 9):
            if slot == primary_slot:
                continue
            try:
                if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) or 0) != int(
                    Ray_of_Judgment_ID
                ):
                    continue
            except Exception:
                continue

            active_slots.add(slot)
            if slot not in self._roj_copy_slots:
                source = self._temporary_roj_source(slot)
                self._roj_copy_slots[slot] = {
                    "source": source,
                    "first_seen_ms": now_ms,
                    "casts": 0,
                }
                self._log_rotation_event(
                    "ROJ_PHASE2_TEMP_COPY_OBSERVED",
                    slot=int(slot),
                    source=source,
                )

        for slot in list(self._roj_copy_slots):
            if slot in active_slots:
                continue
            state = self._roj_copy_slots.pop(slot)
            cast_count = int(state.get("casts", 0) or 0)
            self._log_rotation_event(
                "ROJ_PHASE2_TEMP_COPY_ENDED",
                slot=int(slot),
                source=str(state.get("source", "temporary_copy")),
                casts=cast_count,
                minimum_met=bool(cast_count >= ROJ_TEMP_COPY_REQUIRED_CASTS),
            )

    def _record_temporary_roj_cast(self, slot: int, target_agent_id: int = 0) -> None:
        self._refresh_temporary_roj_slots()
        state = self._roj_copy_slots.get(int(slot))
        if state is None:
            return
        cast_count = int(state.get("casts", 0) or 0) + 1
        state["casts"] = cast_count
        now_ms = self._now_ms()
        first_seen_ms = float(state.get("first_seen_ms", now_ms) or now_ms)
        remaining_ms = max(
            0.0,
            ROJ_TEMP_COPY_DURATION_MS - (now_ms - first_seen_ms),
        )
        self._log_rotation_event(
            "ROJ_PHASE2_TEMP_COPY_CAST",
            slot=int(slot),
            source=str(state.get("source", "temporary_copy")),
            ordinal=cast_count,
            minimum_met=bool(cast_count >= ROJ_TEMP_COPY_REQUIRED_CASTS),
            target_id=int(target_agent_id or 0),
            remaining_ms=round(remaining_ms, 1),
        )

    def _get_ready_temporary_roj_slot(self) -> int:
        self._refresh_temporary_roj_slots()
        now_ms = self._now_ms()
        candidates: list[tuple[tuple[float, ...], int]] = []

        for slot, state in self._roj_copy_slots.items():
            if not Routines.Checks.Skills.IsSkillSlotReady(int(slot)):
                continue
            first_seen_ms = float(state.get("first_seen_ms", now_ms) or now_ms)
            remaining_ms = max(0.0, ROJ_TEMP_COPY_DURATION_MS - (now_ms - first_seen_ms))
            cast_count = int(state.get("casts", 0) or 0)
            urgent = remaining_ms <= ROJ_TEMP_COPY_URGENT_WINDOW_MS
            sort_key = (
                0.0 if cast_count < ROJ_TEMP_COPY_REQUIRED_CASTS else 1.0,
                0.0 if urgent else 1.0,
                remaining_ms if urgent else 999999.0,
                float(cast_count),
                first_seen_ms,
                float(slot),
            )
            candidates.append((sort_key, int(slot)))

        if not candidates:
            return 0
        candidates.sort(key=lambda item: item[0])
        return int(candidates[0][1])

    def _has_unfulfilled_temporary_roj(self) -> bool:
        self._refresh_temporary_roj_slots()
        return any(
            int(state.get("casts", 0) or 0) < ROJ_TEMP_COPY_REQUIRED_CASTS
            for state in self._roj_copy_slots.values()
        )

    def _unfulfilled_temporary_roj_count(self) -> int:
        self._refresh_temporary_roj_slots()
        return sum(
            1
            for state in self._roj_copy_slots.values()
            if int(state.get("casts", 0) or 0) < ROJ_TEMP_COPY_REQUIRED_CASTS
        )

    def _should_bypass_whiteboard_for_temporary_roj(self, slot: int) -> bool:
        """Do not let a short-lived required copy expire behind a team claim."""
        self._refresh_temporary_roj_slots()
        state = self._roj_copy_slots.get(int(slot))
        if state is None:
            return False
        if int(state.get("casts", 0) or 0) >= ROJ_TEMP_COPY_REQUIRED_CASTS:
            return False
        now_ms = self._now_ms()
        first_seen_ms = float(state.get("first_seen_ms", now_ms) or now_ms)
        remaining_ms = ROJ_TEMP_COPY_DURATION_MS - (now_ms - first_seen_ms)
        return bool(remaining_ms <= ROJ_TEMP_COPY_CAST_GUARD_MS)

    @staticmethod
    def _distance_sq(a: tuple[float, float], b: tuple[float, float]) -> float:
        try:
            dx = float(a[0]) - float(b[0])
            dy = float(a[1]) - float(b[1])
            return dx * dx + dy * dy
        except Exception:
            return 0.0

    @staticmethod
    def _game_tick() -> int:
        try:
            import PySystem

            return int(PySystem.get_tick_count64() or 0)
        except Exception:
            return 0

    def _coordination_group_id(self) -> int:
        try:
            party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
            if party_id > 0:
                return party_id
        except Exception:
            pass
        try:
            email = str(Player.GetAccountEmail() or "").strip()
            if email:
                return int(GLOBAL_CACHE.ShMem.GetAccountGroupByEmail(email) or 0)
        except Exception:
            pass
        return 0

    @staticmethod
    def _coordination_owner_email() -> str:
        """Use a lease owner that BuildMgr's cast-intent cleanup cannot erase.

        BuildMgr clears the real account owner's short cast intent when an
        activation finishes.  Coverage leases describe the five-second ground
        field and therefore deliberately use a namespaced owner in the same
        isolation group; they expire normally through the whiteboard sweeper.
        """
        try:
            email = str(Player.GetAccountEmail() or "").strip()
        except Exception:
            email = ""
        return f"{email}#roj_phase3" if email else ""

    @staticmethod
    def _ready_skill_account_emails(skill_id: int) -> list[str]:
        """Return live same-party accounts whose shared bar exposes this ready skill."""
        try:
            from Py4GWCoreLib.HeroAI.utils import SameMapOrPartyAsAccount
        except Exception:
            SameMapOrPartyAsAccount = None

        try:
            own_party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
        except Exception:
            own_party_id = 0
        ready: list[str] = []
        try:
            accounts = GLOBAL_CACHE.ShMem.GetAllAccountData() or []
        except Exception:
            accounts = []
        for account in accounts:
            try:
                if not bool(getattr(account, "IsSlotActive", False)):
                    continue
                if bool(getattr(account, "IsIsolated", False)):
                    continue
                if SameMapOrPartyAsAccount is not None and not SameMapOrPartyAsAccount(account):
                    continue
                account_party_id = int(
                    getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0
                )
                if own_party_id > 0 and account_party_id != own_party_id:
                    continue
                email = str(getattr(account, "AccountEmail", "") or "").strip()
                if not email:
                    continue
                skillbar = getattr(getattr(account, "AgentData", None), "Skillbar", None)
                for skill in getattr(skillbar, "Skills", ()) or ():
                    if int(getattr(skill, "Id", 0) or 0) != int(skill_id):
                        continue
                    if float(getattr(skill, "Recharge", 0.0) or 0.0) <= 0.0:
                        ready.append(email)
                        break
            except Exception:
                continue

        try:
            own_email = str(Player.GetAccountEmail() or "").strip()
        except Exception:
            own_email = ""
        # The local bar was checked immediately before this election. Shared
        # skillbar snapshots may legitimately lag it by one update.
        if own_email and own_email not in ready:
            ready.append(own_email)
        return sorted(set(ready))

    def _lane_election_ready(
        self,
        *,
        election_key: int,
        skill_id: int,
        step_ms: int,
        first_seen: dict[int, int],
        salt_a: int,
        salt_b: int,
        now_tick: int,
    ) -> bool:
        key = int(election_key or 1)
        now = int(now_tick or 0)
        for old_key, first_tick in list(first_seen.items()):
            if now - int(first_tick) > ROJ_LANE_ELECTION_MAX_AGE_MS:
                first_seen.pop(old_key, None)
        started = int(first_seen.setdefault(key, now))

        try:
            own_email = str(Player.GetAccountEmail() or "").strip()
        except Exception:
            own_email = ""
        emails = self._ready_skill_account_emails(int(skill_id))
        if not own_email or own_email not in emails or len(emails) <= 1:
            return True

        seed = ((key * int(salt_a)) ^ (self._coordination_group_id() * int(salt_b))) & 0x7FFFFFFF
        offset = seed % len(emails)
        ordered = emails[offset:] + emails[:offset]
        rank = int(ordered.index(own_email))
        return now - started >= rank * max(1, int(step_ms))

    def _coordination_lock_count(self, key_id: int, target_id: int, *, now_tick: int = 0) -> int:
        if int(target_id or 0) < 0:
            return 0
        try:
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength,
                WhiteboardLockKind,
                WhiteboardReentryPolicy,
            )

            now = int(now_tick or self._game_tick())
            if now <= 0:
                return 0
            return int(GLOBAL_CACHE.ShMem.CountLocks(
                int(WhiteboardLockKind.SKILL_TARGET),
                int(key_id),
                int(target_id),
                int(self._coordination_group_id()),
                "",
                now,
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            ) or 0)
        except Exception:
            return 0

    def _post_coordination_lock(
        self,
        key_id: int,
        target_id: int,
        duration_ms: int,
        *,
        max_holders: int,
        now_tick: int,
    ) -> bool:
        try:
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength,
                WhiteboardLockKind,
                WhiteboardLockMode,
                WhiteboardReentryPolicy,
            )

            owner = self._coordination_owner_email()
            if not owner or int(now_tick) <= 0:
                return False
            return bool(GLOBAL_CACHE.ShMem.PostLock(
                owner,
                int(WhiteboardLockKind.SKILL_TARGET),
                int(key_id),
                int(target_id),
                int(now_tick) + int(duration_ms),
                int(self._coordination_group_id()),
                int(WhiteboardLockMode.SEMAPHORE),
                max(1, int(max_holders)),
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            ) != -1)
        except Exception:
            return False

    @staticmethod
    def _enemy_health(target_agent_id: int) -> float:
        try:
            return float(Agent.GetHealth(int(target_agent_id)))
        except Exception:
            return 1.0

    def _get_authoritative_roj_packet(
        self,
        *,
        consumer_role: str,
    ) -> tuple[int, list[int], bool]:
        """Return TeamCombatFocus' one packet and whether it is hard focus.

        There is intentionally no local nearest-enemy fallback. Cleanup,
        mission priority and the <=10% previous-focus rule all remain owned by
        the shared resolver. No Keystone build has to be in the team.
        """
        try:
            from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import (
                get_team_cluster_anchor,
                get_team_cluster_members,
            )

            anchor = int(get_team_cluster_anchor(
                filter_range=Range.Spellcast.value,
                minimum_enemies=ROJ_ACCEPTABLE_PACKET_MIN,
                consumer_role=str(consumer_role or "roj"),
            ) or 0)
            if anchor <= 0 or not self._is_enemy_alive_valid(anchor):
                return 0, [], False
            members = [
                int(agent_id)
                for agent_id in get_team_cluster_members(
                    anchor,
                    radius=Range.Adjacent.value,
                    filter_range=Range.Spellcast.value,
                )
                if self._is_enemy_alive_valid(int(agent_id))
            ]
        except Exception:
            return 0, [], False

        if anchor not in members:
            members.append(anchor)
        members = sorted(set(members))
        hard_focus = bool(
            len(members) <= 1
            or self._is_elite_priority_target(anchor)
            or self._enemy_health(anchor) <= ROJ_HARD_FOCUS_THRESHOLD
        )
        if hard_focus:
            members = [anchor]
        return anchor, members, hard_focus

    @staticmethod
    def _roj_coverage_policy(
        packet_size: int,
        hard_focus: bool,
    ) -> tuple[int, int, int]:
        """Return normal cluster, emergency cluster and normal target caps.

        Six staggered leases are required to keep a large packet continuously
        carpeted: ceil(5250 / 930) == 6. Small packets deliberately receive
        less coverage to avoid spending all fifteen available RoJ slots on two
        foes. Cleanup stays concentrated, but never exceeds three RoJs on the
        single authoritative target.
        """
        size = max(1, int(packet_size or 0))
        if bool(hard_focus) or size <= 1:
            return 3, 3, 3
        if size == 2:
            return 3, 4, 2
        if size <= 4:
            return 4, 5, 2
        return 6, 7, 2

    def _log_coordination_wait(self, reason: str, **fields) -> None:
        now_ms = self._now_ms()
        previous_reason = str(getattr(self, "_last_coordination_wait_reason", "") or "")
        previous_ms = float(getattr(self, "_last_coordination_wait_log_ms", 0.0) or 0.0)
        if reason == previous_reason and now_ms - previous_ms < 900.0:
            return
        self._last_coordination_wait_reason = str(reason)
        self._last_coordination_wait_log_ms = now_ms
        self._log_rotation_event("ROJ_PHASE3_COORDINATION_WAIT", reason=str(reason), **fields)

    def _reserve_roj_cast(
        self,
        *,
        anchor_agent_id: int,
        target_agent_id: int,
        packet_size: int,
        hard_focus: bool,
        allow_cluster_overflow: bool,
    ) -> tuple[bool, str]:
        now_tick = self._game_tick()
        if now_tick <= 0:
            return True, "clock_unavailable_fail_open"
        if not self._coordination_owner_email():
            return True, "owner_unavailable_fail_open"
        try:
            GLOBAL_CACHE.ShMem.SweepExpiredIntents(now_tick)
        except Exception:
            pass

        lane_count = self._coordination_lock_count(
            ROJ_TEAM_LANE_LOCK_ID,
            0,
            now_tick=now_tick,
        )
        if lane_count > 0:
            return False, "team_lane_930ms"

        normal_cluster_cap, emergency_cluster_cap, normal_target_cap = (
            self._roj_coverage_policy(int(packet_size), bool(hard_focus))
        )
        low_hp_finisher = self._enemy_health(target_agent_id) <= ROJ_LOW_HP_FINISH_THRESHOLD
        target_cap = (
            ROJ_MAX_TARGET_COVERAGE
            if bool(hard_focus) or low_hp_finisher
            else int(normal_target_cap)
        )

        target_count = self._coordination_lock_count(
            ROJ_TARGET_COVERAGE_LOCK_ID,
            int(target_agent_id),
            now_tick=now_tick,
        )
        if target_count >= target_cap:
            return False, f"target_coverage_cap_{int(target_cap)}"

        cluster_count = self._coordination_lock_count(
            ROJ_CLUSTER_COVERAGE_LOCK_ID,
            int(anchor_agent_id),
            now_tick=now_tick,
        )
        if cluster_count >= emergency_cluster_cap:
            return False, f"cluster_emergency_coverage_cap_{int(emergency_cluster_cap)}"
        if low_hp_finisher:
            if self._coordination_lock_count(
                ROJ_LOW_HP_FINISH_LOCK_ID,
                int(anchor_agent_id),
                now_tick=now_tick,
            ) > 0:
                return False, "low_hp_finisher_already_covered"
        elif cluster_count >= normal_cluster_cap and not allow_cluster_overflow:
            return False, f"cluster_coverage_cap_{int(normal_cluster_cap)}"

        # Elect by the shared packet state, not by the locally preferred
        # member.  Different monks may have different previous targets, but
        # they must still contend for one global RoJ cast lane.
        election_key = (int(anchor_agent_id) << 3) ^ int(cluster_count)
        if not self._lane_election_ready(
            election_key=election_key,
            skill_id=Ray_of_Judgment_ID,
            step_ms=ROJ_LANE_ELECTION_STEP_MS,
            first_seen=self._roj_lane_first_seen,
            salt_a=1103515245,
            salt_b=2654435761,
            now_tick=now_tick,
        ):
            return False, "team_lane_election_wait"
        # The preferred account may have posted during this account's small,
        # deterministic rank delay.
        if self._coordination_lock_count(
            ROJ_TEAM_LANE_LOCK_ID,
            0,
            now_tick=now_tick,
        ) > 0:
            return False, "team_lane_930ms"

        posted_lane = self._post_coordination_lock(
            ROJ_TEAM_LANE_LOCK_ID,
            0,
            ROJ_TEAM_CAST_LANE_MS,
            max_holders=1,
            now_tick=now_tick,
        )
        if not posted_lane:
            return False, "team_lane_post_failed"
        posted_finisher = True
        if low_hp_finisher:
            posted_finisher = self._post_coordination_lock(
                ROJ_LOW_HP_FINISH_LOCK_ID,
                int(anchor_agent_id),
                ROJ_COVERAGE_WINDOW_MS,
                max_holders=1,
                now_tick=now_tick,
            )
            if not posted_finisher:
                return False, "low_hp_finisher_post_failed"
        posted_target = self._post_coordination_lock(
            ROJ_TARGET_COVERAGE_LOCK_ID,
            int(target_agent_id),
            ROJ_COVERAGE_WINDOW_MS,
            max_holders=ROJ_MAX_TARGET_COVERAGE,
            now_tick=now_tick,
        )
        if not posted_target:
            return False, "target_coverage_post_failed"
        posted_cluster = self._post_coordination_lock(
            ROJ_CLUSTER_COVERAGE_LOCK_ID,
            int(anchor_agent_id),
            ROJ_COVERAGE_WINDOW_MS,
            max_holders=ROJ_MAX_CLUSTER_EMERGENCY_COVERAGE,
            now_tick=now_tick,
        )
        if not posted_cluster:
            return False, "cluster_coverage_post_failed"

        self._log_rotation_event(
            "ROJ_PHASE3_CAST_RESERVED",
            target_id=int(target_agent_id),
            anchor_id=int(anchor_agent_id),
            target_coverage_before=int(target_count),
            cluster_coverage_before=int(cluster_count),
            packet_size=int(packet_size),
            target_cap=int(target_cap),
            normal_cluster_cap=int(normal_cluster_cap),
            emergency_cluster_cap=int(emergency_cluster_cap),
            low_hp_finisher=bool(low_hp_finisher),
            urgent_copy_overflow=bool(
                allow_cluster_overflow and cluster_count >= normal_cluster_cap
            ),
        )
        return True, "reserved"

    def _reserve_symbol_cast(
        self,
        *,
        anchor_agent_id: int,
        target_agent_id: int,
        packet_size: int,
        hard_focus: bool,
    ) -> tuple[bool, str]:
        now_tick = self._game_tick()
        if now_tick <= 0:
            return True, "clock_unavailable_fail_open"
        if not self._coordination_owner_email():
            return True, "owner_unavailable_fail_open"
        try:
            GLOBAL_CACHE.ShMem.SweepExpiredIntents(now_tick)
        except Exception:
            pass

        if self._coordination_lock_count(
            SYMBOL_TEAM_LANE_LOCK_ID,
            0,
            now_tick=now_tick,
        ) > 0:
            return False, "symbol_team_lane_680ms"
        normal_cluster_cap, _emergency_cluster_cap, normal_target_cap = (
            self._roj_coverage_policy(int(packet_size), bool(hard_focus))
        )
        target_count = self._coordination_lock_count(
            SYMBOL_TARGET_COVERAGE_LOCK_ID,
            int(target_agent_id),
            now_tick=now_tick,
        )
        if target_count >= SYMBOL_MAX_TARGET_COVERAGE:
            return False, "symbol_target_filler_cap_1"
        roj_target_count = self._coordination_lock_count(
            ROJ_TARGET_COVERAGE_LOCK_ID,
            int(target_agent_id),
            now_tick=now_tick,
        )
        combined_target_cap = (
            ROJ_MAX_TARGET_COVERAGE if bool(hard_focus) else int(normal_target_cap)
        )
        if target_count + roj_target_count >= combined_target_cap:
            return False, f"combined_target_coverage_cap_{int(combined_target_cap)}"
        cluster_count = self._coordination_lock_count(
            SYMBOL_CLUSTER_COVERAGE_LOCK_ID,
            int(anchor_agent_id),
            now_tick=now_tick,
        )
        if cluster_count >= SYMBOL_MAX_CLUSTER_COVERAGE:
            return False, "symbol_cluster_filler_cap_2"
        roj_cluster_count = self._coordination_lock_count(
            ROJ_CLUSTER_COVERAGE_LOCK_ID,
            int(anchor_agent_id),
            now_tick=now_tick,
        )
        if cluster_count + roj_cluster_count >= normal_cluster_cap:
            return False, f"combined_cluster_coverage_cap_{int(normal_cluster_cap)}"

        election_key = (int(anchor_agent_id) << 2) ^ int(cluster_count)
        if not self._lane_election_ready(
            election_key=election_key,
            skill_id=Symbol_of_Wrath_ID,
            step_ms=SYMBOL_LANE_ELECTION_STEP_MS,
            first_seen=self._symbol_lane_first_seen,
            salt_a=214013,
            salt_b=2531011,
            now_tick=now_tick,
        ):
            return False, "symbol_team_lane_election_wait"
        if self._coordination_lock_count(
            SYMBOL_TEAM_LANE_LOCK_ID,
            0,
            now_tick=now_tick,
        ) > 0:
            return False, "symbol_team_lane_680ms"

        posted_lane = self._post_coordination_lock(
            SYMBOL_TEAM_LANE_LOCK_ID,
            0,
            SYMBOL_TEAM_CAST_LANE_MS,
            max_holders=1,
            now_tick=now_tick,
        )
        if not posted_lane:
            return False, "symbol_team_lane_post_failed"

        posted_target = self._post_coordination_lock(
            SYMBOL_TARGET_COVERAGE_LOCK_ID,
            int(target_agent_id),
            ROJ_COVERAGE_WINDOW_MS,
            max_holders=SYMBOL_MAX_TARGET_COVERAGE,
            now_tick=now_tick,
        )
        if not posted_target:
            return False, "symbol_target_coverage_post_failed"
        posted_cluster = self._post_coordination_lock(
            SYMBOL_CLUSTER_COVERAGE_LOCK_ID,
            int(anchor_agent_id),
            ROJ_COVERAGE_WINDOW_MS,
            max_holders=SYMBOL_MAX_CLUSTER_COVERAGE,
            now_tick=now_tick,
        )
        if not posted_cluster:
            return False, "symbol_cluster_coverage_post_failed"
        self._log_rotation_event(
            "ROJ_PHASE3_1_SYMBOL_RESERVED",
            target_id=int(target_agent_id),
            anchor_id=int(anchor_agent_id),
            packet_size=int(packet_size),
            roj_target_coverage_before=int(roj_target_count),
            symbol_target_coverage_before=int(target_count),
            roj_cluster_coverage_before=int(roj_cluster_count),
            symbol_cluster_coverage_before=int(cluster_count),
            combined_target_cap=int(combined_target_cap),
            combined_cluster_cap=int(normal_cluster_cap),
        )
        return True, "reserved"

    def _reserve_bane_cast(
        self,
        *,
        anchor_agent_id: int,
        target_agent_id: int,
    ) -> tuple[bool, str]:
        """Stagger Bane without sharing any RoJ/Symbol coverage budget."""
        now_tick = self._game_tick()
        if now_tick <= 0:
            return True, "clock_unavailable_fail_open"
        if not self._coordination_owner_email():
            return True, "owner_unavailable_fail_open"
        try:
            GLOBAL_CACHE.ShMem.SweepExpiredIntents(now_tick)
        except Exception:
            pass

        if self._coordination_lock_count(
            BANE_TEAM_LANE_LOCK_ID,
            0,
            now_tick=now_tick,
        ) > 0:
            return False, "bane_team_lane_420ms"
        if self._coordination_lock_count(
            BANE_TARGET_LOCK_ID,
            int(target_agent_id),
            now_tick=now_tick,
        ) > 0:
            return False, "bane_target_activation_reserved"

        election_key = (int(anchor_agent_id) << 3) ^ int(target_agent_id)
        if not self._lane_election_ready(
            election_key=election_key,
            skill_id=Bane_Signet_ID,
            step_ms=BANE_LANE_ELECTION_STEP_MS,
            first_seen=self._bane_lane_first_seen,
            salt_a=1664525,
            salt_b=1013904223,
            now_tick=now_tick,
        ):
            return False, "bane_team_lane_election_wait"
        if self._coordination_lock_count(
            BANE_TEAM_LANE_LOCK_ID,
            0,
            now_tick=now_tick,
        ) > 0:
            return False, "bane_team_lane_420ms"

        if not self._post_coordination_lock(
            BANE_TEAM_LANE_LOCK_ID,
            0,
            BANE_TEAM_CAST_LANE_MS,
            max_holders=1,
            now_tick=now_tick,
        ):
            return False, "bane_team_lane_post_failed"
        if not self._post_coordination_lock(
            BANE_TARGET_LOCK_ID,
            int(target_agent_id),
            BANE_TARGET_RESERVATION_MS,
            max_holders=1,
            now_tick=now_tick,
        ):
            return False, "bane_target_reservation_post_failed"

        self._log_rotation_event(
            "ROJ_PHASE3_7_BANE_RESERVED",
            target_id=int(target_agent_id),
            anchor_id=int(anchor_agent_id),
            policy="short_stagger_only_no_roj_coverage",
        )
        return True, "reserved"

    @staticmethod
    def _is_enemy_alive_valid(agent_id: int) -> bool:
        try:
            agent_id = int(agent_id or 0)
            return bool(agent_id > 0 and Agent.IsValid(agent_id) and Agent.IsAlive(agent_id))
        except Exception:
            return False

    @staticmethod
    def _get_safe_casting_skill_id(agent_id: int) -> int:
        try:
            agent_id = int(agent_id or 0)
            if agent_id <= 0:
                return 0
            if not Agent.IsValid(agent_id) or not Agent.IsAlive(agent_id):
                return 0
            if not Agent.IsCasting(agent_id):
                return 0
            return int(Agent.GetCastingSkillID(agent_id) or 0)
        except Exception:
            return 0

    @staticmethod
    def _healer_profession_ids() -> set[int]:
        result: set[int] = set()
        for profession in (Profession.Monk, Profession.Ritualist):
            try:
                result.add(int(getattr(profession, "value", profession)))
            except Exception:
                continue
        return result

    @staticmethod
    def _get_enemy_professions_safe(agent_id: int) -> tuple[int, int]:
        try:
            if not Ray_of_Judgment._is_enemy_alive_valid(agent_id):
                return (0, 0)
            primary, secondary = Agent.GetProfessions(agent_id)
            primary_id = int(getattr(primary, "value", primary) or 0)
            secondary_id = int(getattr(secondary, "value", secondary) or 0)
            return (primary_id, secondary_id)
        except Exception:
            return (0, 0)

    def _is_healer_profession_enemy(self, agent_id: int) -> bool:
        primary, secondary = self._get_enemy_professions_safe(agent_id)
        healer_professions = self._healer_profession_ids()
        return primary in healer_professions or secondary in healer_professions

    def _is_safe_dangerous_cast(self, agent_id: int) -> bool:
        return self._get_safe_casting_skill_id(agent_id) in _SAFE_DANGER_CAST_SKILL_IDS

    def _is_healer_support_cast(self, agent_id: int) -> bool:
        casting_skill_id = self._get_safe_casting_skill_id(agent_id)
        return casting_skill_id in _SAFE_HEALER_FOCUS_SKILL_IDS or casting_skill_id in _SAFE_DANGER_CAST_SKILL_IDS

    def _is_healer_focus_target(self, agent_id: int) -> bool:
        if not self._is_enemy_alive_valid(agent_id):
            return False
        return self._is_healer_profession_enemy(agent_id) or self._is_healer_support_cast(agent_id)

    def _count_adjacent_enemies(self, target_agent_id: int) -> int:
        if target_agent_id <= 0:
            return 0
        try:
            target_xy = Agent.GetXY(target_agent_id)
            enemies = AgentArray.GetEnemyArray()
            enemies = AgentArray.Filter.ByDistance(enemies, target_xy, Range.Adjacent.value)
            enemies = AgentArray.Filter.ByCondition(
                enemies,
                lambda agent_id: Agent.IsValid(agent_id) and Agent.IsAlive(agent_id),
            )
            return int(len(enemies))
        except Exception:
            try:
                return int(Routines.Targeting.CountNearbyEnemies(target_agent_id, Range.Adjacent.value) or 0)
            except Exception:
                return 0

    def _get_ready_ray_of_judgment_slot(self) -> tuple[int, int]:
        """Return (ready_slot, native_slot), always spending copies first."""
        primary_slot = self._get_native_roj_slot()
        if not primary_slot:
            return (0, 0)

        copied_slot = self._get_ready_temporary_roj_slot()
        if copied_slot:
            return (int(copied_slot), int(primary_slot))

        if Routines.Checks.Skills.IsSkillSlotReady(primary_slot):
            return (int(primary_slot), int(primary_slot))
        return (0, int(primary_slot))


    def _is_elite_priority_target(self, target_agent_id: int) -> bool:
        if not self._is_enemy_alive_valid(target_agent_id):
            return False
        try:
            name = str(Agent.GetNameByID(int(target_agent_id)) or "").strip().lower()
        except Exception:
            return False
        return any(priority_name in name for priority_name in ELITE_PRIORITY_TARGET_NAMES)

    def _get_roj_candidate_packet(
        self,
        *,
        exclude_target_id: int = 0,
        allow_cluster_overflow: bool = False,
        consumer_role: str = "roj_damage",
    ) -> tuple[int, list[int], bool, int]:
        anchor, members, hard_focus = self._get_authoritative_roj_packet(
            consumer_role=str(consumer_role),
        )
        if anchor <= 0 or not members:
            self._last_roj_selection_reason = "no_authoritative_target"
            return 0, [], False, 0

        packet_size = int(len(members))
        normal_cluster_cap, emergency_cluster_cap, normal_target_cap = (
            self._roj_coverage_policy(packet_size, bool(hard_focus))
        )

        now_tick = self._game_tick()
        cluster_coverage = self._coordination_lock_count(
            ROJ_CLUSTER_COVERAGE_LOCK_ID,
            int(anchor),
            now_tick=now_tick,
        )
        final_covered = self._coordination_lock_count(
            ROJ_LOW_HP_FINISH_LOCK_ID,
            int(anchor),
            now_tick=now_tick,
        ) > 0
        try:
            player_pos = Player.GetXY()
        except Exception:
            player_pos = (0.0, 0.0)

        ranked: list[tuple[tuple[int, int, int, int, int, int, float, float, int], int]] = []
        saturated_targets = 0
        low_hp_already_finished = 0
        for target_agent_id in members:
            target_agent_id = int(target_agent_id or 0)
            if not self._is_enemy_alive_valid(target_agent_id):
                continue
            target_coverage = self._coordination_lock_count(
                ROJ_TARGET_COVERAGE_LOCK_ID,
                target_agent_id,
                now_tick=now_tick,
            )
            health = self._enemy_health(target_agent_id)
            low_hp_finisher = health <= ROJ_LOW_HP_FINISH_THRESHOLD
            target_cap = (
                ROJ_MAX_TARGET_COVERAGE
                if bool(hard_focus) or low_hp_finisher
                else int(normal_target_cap)
            )
            if target_coverage >= target_cap:
                saturated_targets += 1
                continue
            if low_hp_finisher and final_covered:
                low_hp_already_finished += 1
                continue
            if cluster_coverage >= emergency_cluster_cap:
                continue
            if (
                cluster_coverage >= normal_cluster_cap
                and not low_hp_finisher
                and not allow_cluster_overflow
            ):
                continue

            try:
                distance_sq = self._distance_sq(player_pos, Agent.GetXY(target_agent_id))
            except Exception:
                distance_sq = 0.0
            rank = (
                0 if low_hp_finisher else 1,
                int(target_coverage),
                1 if (
                    int(exclude_target_id or 0) > 0
                    and target_agent_id == int(exclude_target_id)
                    and len(members) > 1
                ) else 0,
                -int(self._is_safe_dangerous_cast(target_agent_id)),
                -int(self._is_healer_focus_target(target_agent_id)),
                -int(self._count_adjacent_enemies(target_agent_id)),
                float(health),
                float(distance_sq),
                int(target_agent_id),
            )
            ranked.append((rank, target_agent_id))

        if not ranked:
            if saturated_targets >= len(members):
                reason = f"packet_targets_saturated_cap_{int(normal_target_cap)}"
            elif low_hp_already_finished >= len(members):
                reason = "low_hp_finisher_already_covered"
            elif cluster_coverage >= emergency_cluster_cap:
                reason = f"cluster_emergency_coverage_cap_{int(emergency_cluster_cap)}"
            elif cluster_coverage >= normal_cluster_cap and not allow_cluster_overflow:
                reason = f"cluster_coverage_cap_{int(normal_cluster_cap)}"
            else:
                reason = "authoritative_packet_has_no_usable_member"
            self._last_roj_selection_reason = reason
            return anchor, [], hard_focus, packet_size

        ranked.sort(key=lambda item: item[0])
        self._last_roj_selection_reason = "selected"
        return anchor, [int(item[1]) for item in ranked], hard_focus, packet_size

    def _get_roj_candidates(
        self,
        exclude_target_id: int = 0,
        *,
        allow_cluster_overflow: bool = False,
    ) -> list[int]:
        _anchor, candidates, _hard_focus, _packet_size = self._get_roj_candidate_packet(
            exclude_target_id=int(exclude_target_id or 0),
            allow_cluster_overflow=bool(allow_cluster_overflow),
            consumer_role="roj_candidate_probe",
        )
        return candidates

    def _pick_ray_of_judgment_target(self, *, exclude_target_id: int = 0) -> int:
        return self._pick_ray_of_judgment_target_immediately(
            exclude_target_id=int(exclude_target_id or 0),
        )

    def _pick_ray_of_judgment_target_immediately(self, *, exclude_target_id: int = 0) -> int:
        """Pick immediately, but only inside the shared authoritative focus."""
        _anchor, candidates, _hard_focus, _packet_size = self._get_roj_candidate_packet(
            exclude_target_id=int(exclude_target_id or 0),
            consumer_role="roj_immediate",
        )
        return int(candidates[0]) if candidates else 0

    def _is_ray_of_judgment_final_target_usable(
        self,
        target_agent_id: int,
        *,
        expected_anchor_id: int = 0,
    ) -> bool:
        if not self._is_enemy_alive_valid(target_agent_id):
            return False
        anchor, members, _hard_focus = self._get_authoritative_roj_packet(
            consumer_role="roj_final_cast_check",
        )
        if anchor <= 0:
            return False
        if int(expected_anchor_id or 0) > 0 and anchor != int(expected_anchor_id):
            return False
        return int(target_agent_id) in set(int(member) for member in members)

    def _cast_ray_of_judgment_smart(
        self,
        *,
        exclude_target_id: int = 0,
        immediate: bool = False,
        required_slot: int = 0,
    ):
        if not self.IsSkillEquipped(Ray_of_Judgment_ID):
            return False
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False

        primary_slot = self._get_native_roj_slot()
        if required_slot:
            ready_slot = int(required_slot)
            if not (1 <= ready_slot <= 8):
                return False
            if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(ready_slot) or 0) != int(Ray_of_Judgment_ID):
                return False
            if not Routines.Checks.Skills.IsSkillSlotReady(ready_slot):
                return False
        else:
            ready_slot, primary_slot = self._get_ready_ray_of_judgment_slot()
        if not ready_slot:
            return False

        if not self.CanCastSkillSlot(ready_slot):
            return False

        urgent_copy_overflow = bool(
            int(ready_slot) != int(primary_slot)
            and self._should_bypass_whiteboard_for_temporary_roj(int(ready_slot))
        )
        anchor_agent_id, candidates, hard_focus, packet_size = self._get_roj_candidate_packet(
            exclude_target_id=int(exclude_target_id or 0),
            allow_cluster_overflow=urgent_copy_overflow,
            consumer_role="roj_protected" if immediate else "roj_free",
        )
        if not candidates:
            self._log_coordination_wait(
                str(getattr(self, "_last_roj_selection_reason", "no_target") or "no_target"),
                anchor_id=int(anchor_agent_id or 0),
                slot=int(ready_slot),
                source=(
                    "native"
                    if int(ready_slot) == int(primary_slot)
                    else self._temporary_roj_source(int(ready_slot))
                ),
            )
            return False
        target_agent_id = int(candidates[0])

        previous_enemy_target = int(Player.GetTargetID() or 0)
        if previous_enemy_target != target_agent_id:
            yield from Routines.Yield.Agents.ChangeTarget(target_agent_id)

        if not self._is_ray_of_judgment_final_target_usable(
            target_agent_id,
            expected_anchor_id=int(anchor_agent_id),
        ):
            yield from self.RestoreEnemyTarget(previous_enemy_target)
            return False
        if not self.CanCastSkillSlot(ready_slot):
            yield from self.RestoreEnemyTarget(previous_enemy_target)
            return False

        reserved, reserve_reason = self._reserve_roj_cast(
            anchor_agent_id=int(anchor_agent_id),
            target_agent_id=int(target_agent_id),
            packet_size=int(packet_size),
            hard_focus=bool(hard_focus),
            allow_cluster_overflow=urgent_copy_overflow,
        )
        if not reserved:
            self._log_coordination_wait(
                reserve_reason,
                anchor_id=int(anchor_agent_id),
                target_id=int(target_agent_id),
                slot=int(ready_slot),
            )
            yield from self.RestoreEnemyTarget(previous_enemy_target)
            return False

        if (
            int(ready_slot) != int(primary_slot)
            and int(exclude_target_id or 0) > 0
            and target_agent_id != int(exclude_target_id)
        ):
            self._log_rotation_event(
                "ROJ_PHASE2_TEMP_COPY_ALTERNATE_TARGET",
                slot=int(ready_slot),
                target_id=int(target_agent_id),
                source=self._temporary_roj_source(int(ready_slot)),
                policy="phase3_authoritative_packet_distribution",
            )
        if urgent_copy_overflow:
            self._log_rotation_event(
                "ROJ_PHASE2_TEMP_COPY_WHITEBOARD_BYPASS",
                slot=int(ready_slot),
                target_id=int(target_agent_id),
                source=self._temporary_roj_source(int(ready_slot)),
                policy="urgent_copy_may_exceed_cluster_coverage_only",
            )

        GLOBAL_CACHE.SkillBar.UseSkill(
            int(ready_slot),
            target_agent_id=int(target_agent_id),
            aftercast_delay=250,
        )
        self._mark_local_cast_pending(250)
        self.SetTickSuccess()
        yield from self.RestoreEnemyTarget(previous_enemy_target)
        cast_result = True

        if cast_result:
            self._last_ray_of_judgment_target_id = target_agent_id
            self._last_ray_of_judgment_cast_ts_ms = self._now_ms()
            self._last_coordination_wait_reason = ""
            if int(ready_slot) != int(primary_slot):
                self._record_temporary_roj_cast(
                    int(ready_slot),
                    target_agent_id=int(target_agent_id),
                )
            self._log_rotation_event(
                "ROJ_PHASE3_CAST_COMMITTED",
                target_id=int(target_agent_id),
                anchor_id=int(anchor_agent_id),
                slot=int(ready_slot),
                source=(
                    "native"
                    if int(ready_slot) == int(primary_slot)
                    else self._temporary_roj_source(int(ready_slot))
                ),
                hard_focus=bool(hard_focus),
                packet_size=int(packet_size),
            )
        return cast_result

    @staticmethod
    def _log_rotation_event(event: str, **fields) -> None:
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug

            CombatDebug.log_event(event, **fields)
        except Exception:
            pass

    @staticmethod
    def _has_self_effect(skill_id: int) -> bool:
        try:
            return bool(Routines.Checks.Agents.HasEffect(Player.GetAgentID(), int(skill_id)))
        except Exception:
            return False

    def _is_roj_chain_active(self) -> bool:
        return str(self._roj_chain_state) != ROJ_CHAIN_IDLE

    def _reset_roj_chain(self, reason: str) -> None:
        previous_state = str(self._roj_chain_state)
        self._roj_chain_state = ROJ_CHAIN_IDLE
        self._roj_chain_started_ms = 0.0
        self._roj_chain_seed_cast_ms = 0.0
        self._roj_chain_native_target_id = 0
        self._roj_chain_echo_slot = 0
        self._mimicry_energy_wait_logged = False
        if previous_state != ROJ_CHAIN_IDLE:
            self._log_rotation_event(
                "ROJ_PHASE1_CHAIN_RESET",
                previous_state=previous_state,
                reason=str(reason),
            )

    def _expire_roj_chain_if_needed(self) -> bool:
        if not self._is_roj_chain_active():
            return False
        # Once Echo has visibly become RoJ, keep the protected lane until that
        # copy is cast or its explicit appearance timeout resolves the state.
        if self._roj_chain_state == ROJ_CHAIN_ECHO_COPY:
            return False
        elapsed_ms = self._now_ms() - float(self._roj_chain_started_ms or 0.0)
        if elapsed_ms < ROJ_CHAIN_TIMEOUT_MS:
            return False
        self._reset_roj_chain("timeout")
        return True

    def _can_afford_roj_echo_chain(
        self,
        *,
        with_auspicious: bool,
        cast_auspicious: bool = True,
    ) -> bool:
        """Avoid starting Echo when the following RoJ would stall on energy."""
        try:
            player_id = int(Player.GetAgentID() or 0)
            current_energy = float(Agent.GetEnergy(player_id)) * float(
                Agent.GetMaxEnergy(player_id)
            )
            echo_cost = max(
                0.0,
                float(Routines.Checks.Skills.GetEnergyCostWithEffects(
                    Arcane_Echo_ID,
                    player_id,
                )),
            )
            roj_cost = max(
                0.0,
                float(Routines.Checks.Skills.GetEnergyCostWithEffects(
                    Ray_of_Judgment_ID,
                    player_id,
                )),
            )
            if with_auspicious:
                auspicious_cost = 0.0
                if cast_auspicious:
                    auspicious_cost = max(
                        0.0,
                        float(Routines.Checks.Skills.GetEnergyCostWithEffects(
                            Auspicious_Incantation_ID,
                            player_id,
                        )),
                    )
                # Even at rank 0, Auspicious returns 110% of Echo's cost. Keep
                # enough energy for Echo, the Mimicry RoJ seed, and Echo's RoJ
                # copy so both temporary slots can still recharge once inside
                # their 20-second lifetime.
                minimum_refund = echo_cost * 1.10
                required_energy = (
                    auspicious_cost
                    + echo_cost
                    + max(0.0, (2.0 * roj_cost) - minimum_refund)
                )
            else:
                required_energy = echo_cost + (2.0 * roj_cost)
            max_energy = float(Agent.GetMaxEnergy(player_id) or 0.0)
            if max_energy > 0.0:
                required_energy = min(required_energy, max_energy)
            return current_energy + 0.01 >= required_energy
        except Exception:
            # If an energy API is unavailable, retain the normal per-skill
            # CanCast checks rather than disabling the build.
            return True

    @staticmethod
    def _current_energy_absolute() -> float:
        try:
            player_id = int(Player.GetAgentID() or 0)
            return float(Agent.GetEnergy(player_id)) * float(Agent.GetMaxEnergy(player_id))
        except Exception:
            return 0.0

    @staticmethod
    def _skill_energy_cost(skill_id: int) -> float:
        try:
            player_id = int(Player.GetAgentID() or 0)
            return max(
                0.0,
                float(Routines.Checks.Skills.GetEnergyCostWithEffects(
                    int(skill_id),
                    player_id,
                )),
            )
        except Exception:
            return 0.0

    def _temporary_roj_energy_reserve(self) -> float:
        return float(self._unfulfilled_temporary_roj_count()) * self._skill_energy_cost(
            Ray_of_Judgment_ID
        )

    def _mimicry_opening_energy_requirement(self) -> float:
        # Mimicry itself plus its first copied RoJ are mandatory.  Keep one
        # additional RoJ cost for every older temporary copy that still needs
        # its second cast.  This prevents Mimicry from draining the Echo copy
        # only seconds before that copy's 20-second lifetime ends.
        return (
            self._skill_energy_cost(Arcane_Mimicry_ID)
            + self._skill_energy_cost(Ray_of_Judgment_ID)
            + self._temporary_roj_energy_reserve()
        )

    def _can_afford_mimicry_opening(self) -> bool:
        requirement = self._mimicry_opening_energy_requirement()
        if requirement <= 0.0:
            return True
        return self._current_energy_absolute() + 0.01 >= requirement

    def _can_afford_native_first_opening(self) -> bool:
        """Start the protected copy chain only when native RoJ cannot drain it."""
        requirement = (
            self._skill_energy_cost(Ray_of_Judgment_ID)
            + self._mimicry_opening_energy_requirement()
        )
        if requirement <= 0.0:
            return True
        return self._current_energy_absolute() + 0.01 >= requirement

    def _mimicry_native_slot_ready(self) -> bool:
        slot = self._get_mimicry_home_slot()
        if not (1 <= slot <= 8):
            return False
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) or 0) != int(
            Arcane_Mimicry_ID
        ):
            return False
        return bool(Routines.Checks.Skills.IsSkillSlotReady(slot))

    def _should_reserve_for_mimicry_energy(self) -> bool:
        if not self._mimicry_native_slot_ready():
            return False
        if self._can_afford_mimicry_opening():
            return False
        try:
            max_energy = float(Agent.GetMaxEnergy(Player.GetAgentID()))
        except Exception:
            max_energy = 0.0
        requirement = self._mimicry_opening_energy_requirement()
        if max_energy > 0.0 and requirement > max_energy + 0.01:
            return False
        try:
            return bool(self._roj_mimicry.has_verified_donor())
        except Exception:
            return False

    def _can_spend_optional_energy(self, skill_id: int) -> bool:
        reserve = self._temporary_roj_energy_reserve()
        cost = self._skill_energy_cost(skill_id)
        if cost <= 0.0 and reserve <= 0.0:
            return True
        return self._current_energy_absolute() + 0.01 >= cost + reserve

    def _should_use_auspicious_for_chain(self) -> bool:
        return bool(
            self.IsSkillEquipped(Auspicious_Incantation_ID)
            and not self._has_self_effect(Auspicious_Incantation_ID)
            and self.CanCastSkillID(Auspicious_Incantation_ID)
            and self._can_afford_roj_echo_chain(
                with_auspicious=True,
                cast_auspicious=True,
            )
        )

    @staticmethod
    def _slot_recharge_remaining_ms(slot: int) -> float | None:
        """Return the live remaining recharge, not the raw cast timestamp."""
        if not (1 <= int(slot) <= 8):
            return None
        try:
            skillbar_data = GLOBAL_CACHE.SkillBar.GetSkillData(int(slot))
            recharge = getattr(skillbar_data, "get_recharge", None)
            if callable(recharge):
                recharge = recharge()
            if recharge is None:
                return None
            return max(0.0, float(recharge))
        except Exception:
            return None

    @staticmethod
    def _skill_activation_ms(skill_id: int) -> float:
        try:
            return max(
                0.0,
                float(GLOBAL_CACHE.Skill.Data.GetActivation(int(skill_id)) or 0.0)
                * 1000.0,
            )
        except Exception:
            return 0.0

    def _native_echo_prearm_window_ms(
        self,
        *,
        cast_auspicious: bool,
    ) -> tuple[float, float]:
        """Window that lets setup finish before native RoJ becomes ready.

        Starting later would make the Monk finish Echo while an already-ready
        native RoJ waits. Starting much earlier merely turns Echo into another
        protected idle lane, so both sides of the window are intentional.
        """
        setup_skill_ids = [Arcane_Echo_ID]
        if cast_auspicious:
            setup_skill_ids.insert(0, Auspicious_Incantation_ID)
        setup_ms = sum(
            self._skill_activation_ms(skill_id) + ROJ_CHAIN_STEP_AFTERCAST_MS
            for skill_id in setup_skill_ids
        )
        earliest_ms = setup_ms + ROJ_NATIVE_ECHO_PREARM_SAFETY_MS
        latest_ms = earliest_ms + ROJ_NATIVE_ECHO_PREARM_WINDOW_MS
        return earliest_ms, latest_ms

    def _mimicry_route_expected_before_native(self, native_recharge_ms: float) -> bool:
        """Keep Mimicry preferred when it will recharge before native RoJ."""
        mimicry_slot = self._get_mimicry_home_slot()
        if not (1 <= mimicry_slot <= 8):
            return False
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(mimicry_slot) or 0) != int(
            Arcane_Mimicry_ID
        ):
            return False
        mimicry_recharge_ms = self._slot_recharge_remaining_ms(mimicry_slot)
        if mimicry_recharge_ms is None or mimicry_recharge_ms > native_recharge_ms:
            return False
        try:
            return bool(
                self._roj_mimicry.can_start()
                and self._roj_mimicry.has_verified_donor()
            )
        except Exception:
            return False

    def _get_native_echo_fallback_plan(
        self,
    ) -> tuple[bool, float, float, float] | None:
        """Plan Echo for native RoJ only when Mimicry cannot cover this cycle."""
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return None
        if self._has_self_effect(Arcane_Echo_ID):
            return None
        if self._has_unfulfilled_temporary_roj():
            return None

        native_slot = self._get_native_roj_slot()
        echo_slot = self._get_echo_home_slot()
        if not (1 <= native_slot <= 8 and 1 <= echo_slot <= 8):
            return None
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(native_slot) or 0) != int(
            Ray_of_Judgment_ID
        ):
            return None
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(echo_slot) or 0) != int(
            Arcane_Echo_ID
        ):
            return None

        # A ready native RoJ is never held for setup. The free lane casts it
        # before this planner is called; this duplicate guard closes races.
        if Routines.Checks.Skills.IsSkillSlotReady(native_slot):
            return None
        native_recharge_ms = self._slot_recharge_remaining_ms(native_slot)
        if native_recharge_ms is None or native_recharge_ms <= 0.0:
            return None
        if not Routines.Checks.Skills.IsSkillSlotReady(echo_slot):
            return None
        if not self.CanCastSkillID(Arcane_Echo_ID):
            return None

        use_auspicious = self._should_use_auspicious_for_chain()
        auspicious_is_active = self._has_self_effect(Auspicious_Incantation_ID)
        if not self._can_afford_roj_echo_chain(
            with_auspicious=bool(use_auspicious or auspicious_is_active),
            cast_auspicious=bool(use_auspicious),
        ):
            return None

        earliest_ms, latest_ms = self._native_echo_prearm_window_ms(
            cast_auspicious=bool(use_auspicious),
        )
        if not (earliest_ms <= native_recharge_ms <= latest_ms):
            return None
        # Donor discovery is intentionally inside the narrow timing window;
        # it walks shared party data and does not belong in every combat tick.
        if self._mimicry_route_expected_before_native(native_recharge_ms):
            return None
        if not self._pick_ray_of_judgment_target_immediately():
            return None
        return use_auspicious, native_recharge_ms, earliest_ms, latest_ms

    def _can_begin_native_first_roj_chain(self) -> bool:
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False
        if self._has_self_effect(Arcane_Echo_ID):
            return False
        if self._has_unfulfilled_temporary_roj():
            return False

        native_slot = self._get_native_roj_slot()
        mimicry_slot = self._get_mimicry_home_slot()
        echo_slot = self._get_echo_home_slot()
        if not all(1 <= slot <= 8 for slot in (native_slot, mimicry_slot, echo_slot)):
            return False
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(native_slot) or 0) != int(
            Ray_of_Judgment_ID
        ):
            return False
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(mimicry_slot) or 0) != int(
            Arcane_Mimicry_ID
        ):
            return False
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(echo_slot) or 0) != int(Arcane_Echo_ID):
            return False
        if not all(
            Routines.Checks.Skills.IsSkillSlotReady(slot)
            for slot in (native_slot, mimicry_slot, echo_slot)
        ):
            return False
        if not self._can_afford_native_first_opening():
            return False
        if not self._roj_mimicry.can_start():
            return False
        if not self._roj_mimicry.has_verified_donor():
            return False

        # Native RoJ is still the first cast, but only enter the protected lane
        # when every copy component is ready to follow it.
        return bool(self._pick_ray_of_judgment_target_immediately())

    def _can_begin_mimicry_echo_chain(self) -> bool:
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False
        if self._has_self_effect(Arcane_Echo_ID):
            return False

        mimicry_slot = self._get_mimicry_home_slot()
        echo_slot = self._get_echo_home_slot()
        if not (1 <= mimicry_slot <= 8 and 1 <= echo_slot <= 8):
            return False
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(mimicry_slot) or 0) != int(
            Ray_of_Judgment_ID
        ):
            return False
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(echo_slot) or 0) != int(Arcane_Echo_ID):
            return False
        if not Routines.Checks.Skills.IsSkillSlotReady(mimicry_slot):
            return False
        if not self.CanCastSkillID(Arcane_Echo_ID):
            return False

        use_auspicious = self._should_use_auspicious_for_chain()
        auspicious_is_active = self._has_self_effect(Auspicious_Incantation_ID)
        if not self._can_afford_roj_echo_chain(
            with_auspicious=bool(use_auspicious or auspicious_is_active),
            cast_auspicious=bool(use_auspicious),
        ):
            return False
        return bool(self._pick_ray_of_judgment_target_immediately())

    def _cast_arcane_echo_chain_step(
        self,
        *,
        next_state: str = ROJ_CHAIN_MIMICRY_ROJ,
    ):
        if self._has_self_effect(Arcane_Echo_ID):
            self._roj_chain_state = str(next_state)
            return False
        if not self.IsSkillEquipped(Arcane_Echo_ID):
            self._reset_roj_chain("echo_slot_missing")
            return False
        if not self.CanCastSkillID(Arcane_Echo_ID):
            return False

        did_cast = yield from self.CastSkillID(
            skill_id=Arcane_Echo_ID,
            log=False,
            aftercast_delay=ROJ_CHAIN_STEP_AFTERCAST_MS,
        )
        if did_cast:
            self._roj_chain_state = str(next_state)
            self._log_rotation_event(
                "ROJ_PHASE1_ARCANE_ECHO_CAST",
                echo_slot=int(self._roj_chain_echo_slot),
                next_state=str(next_state),
            )
            return True
        return False

    def _begin_native_first_roj_chain(self):
        self._roj_chain_state = ROJ_CHAIN_NATIVE_ROJ
        self._roj_chain_started_ms = self._now_ms()
        self._roj_chain_seed_cast_ms = 0.0
        self._roj_chain_native_target_id = 0
        self._roj_chain_echo_slot = self._get_echo_home_slot()
        self._log_rotation_event(
            "ROJ_PHASE1_CHAIN_START",
            echo_slot=int(self._roj_chain_echo_slot),
            mimicry_slot=int(self._get_mimicry_home_slot()),
            order=(
                "native_roj>arcane_mimicry>auspicious>arcane_echo>"
                "mimicry_roj>echo_roj"
            ),
        )
        return (yield from self._advance_roj_echo_chain())

    def _begin_mimicry_echo_chain(self):
        self._roj_chain_state = ROJ_CHAIN_ECHO
        self._roj_chain_echo_slot = self._get_echo_home_slot()

        use_auspicious = self._should_use_auspicious_for_chain()
        self._log_rotation_event(
            "ROJ_PHASE3_MIMICRY_ECHO_SETUP",
            echo_slot=int(self._roj_chain_echo_slot),
            mimicry_slot=int(self._get_mimicry_home_slot()),
            auspicious=bool(use_auspicious),
        )

        # Auspicious is supported, never required: use it when ready, otherwise
        # continue directly with the required Echo -> RoJ pair.
        if use_auspicious:
            did_cast = yield from self.CastSkillID(
                skill_id=Auspicious_Incantation_ID,
                log=False,
                aftercast_delay=ROJ_CHAIN_STEP_AFTERCAST_MS,
            )
            if did_cast:
                self._log_rotation_event("ROJ_PHASE1_AUSPICIOUS_CAST")
                return True

        return (yield from self._cast_arcane_echo_chain_step())

    def _begin_native_echo_fallback(
        self,
        *,
        use_auspicious: bool,
        native_recharge_ms: float,
        earliest_ms: float,
        latest_ms: float,
    ):
        self._roj_chain_state = ROJ_CHAIN_NATIVE_ECHO_SETUP
        self._roj_chain_started_ms = self._now_ms()
        self._roj_chain_seed_cast_ms = 0.0
        self._roj_chain_native_target_id = 0
        self._roj_chain_echo_slot = self._get_echo_home_slot()
        self._log_rotation_event(
            "ROJ_PHASE3_6_NATIVE_ECHO_FALLBACK_START",
            echo_slot=int(self._roj_chain_echo_slot),
            native_slot=int(self._get_native_roj_slot()),
            native_recharge_ms=round(float(native_recharge_ms), 1),
            earliest_ms=round(float(earliest_ms), 1),
            latest_ms=round(float(latest_ms), 1),
            auspicious=bool(use_auspicious),
            order="auspicious_if_ready>arcane_echo>native_roj>echo_roj",
        )

        if use_auspicious:
            did_cast = yield from self.CastSkillID(
                skill_id=Auspicious_Incantation_ID,
                log=False,
                aftercast_delay=ROJ_CHAIN_STEP_AFTERCAST_MS,
            )
            if did_cast:
                self._log_rotation_event(
                    "ROJ_PHASE3_6_NATIVE_ECHO_AUSPICIOUS_CAST"
                )
                return True

        return (yield from self._advance_roj_echo_chain())

    def _resume_existing_echo_if_needed(self) -> bool:
        """Recover a safe Mimicry or near-ready native seed for active Echo."""
        if self._is_roj_chain_active() or not self._has_self_effect(Arcane_Echo_ID):
            return False

        echo_slot = self._get_echo_home_slot()
        mimicry_slot = self._get_mimicry_home_slot()
        if not (1 <= echo_slot <= 8):
            return False
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(echo_slot) or 0) != int(Arcane_Echo_ID):
            return False

        if 1 <= mimicry_slot <= 8:
            mimicry_skill_id = int(
                GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(mimicry_slot) or 0
            )
            if (
                mimicry_skill_id == int(Ray_of_Judgment_ID)
                and Routines.Checks.Skills.IsSkillSlotReady(mimicry_slot)
                and self._pick_ray_of_judgment_target_immediately()
            ):
                self._roj_chain_state = ROJ_CHAIN_MIMICRY_ROJ
                self._roj_chain_started_ms = self._now_ms()
                self._roj_chain_seed_cast_ms = 0.0
                self._roj_chain_native_target_id = 0
                self._roj_chain_echo_slot = echo_slot
                self._log_rotation_event(
                    "ROJ_PHASE1_CHAIN_RESUMED",
                    echo_slot=int(echo_slot),
                    mimicry_slot=int(mimicry_slot),
                    seed_source="arcane_mimicry",
                )
                return True

        native_slot = self._get_native_roj_slot()
        if not (1 <= native_slot <= 8):
            return False
        if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(native_slot) or 0) != int(
            Ray_of_Judgment_ID
        ):
            return False
        native_recharge_ms = self._slot_recharge_remaining_ms(native_slot)
        _, latest_ms = self._native_echo_prearm_window_ms(cast_auspicious=False)
        if (
            not Routines.Checks.Skills.IsSkillSlotReady(native_slot)
            and (native_recharge_ms is None or native_recharge_ms > latest_ms)
        ):
            return False
        if not self._pick_ray_of_judgment_target_immediately():
            return False

        self._roj_chain_state = ROJ_CHAIN_NATIVE_ECHO_ROJ
        self._roj_chain_started_ms = self._now_ms()
        self._roj_chain_seed_cast_ms = 0.0
        self._roj_chain_native_target_id = 0
        self._roj_chain_echo_slot = echo_slot
        self._log_rotation_event(
            "ROJ_PHASE3_6_NATIVE_ECHO_CHAIN_RESUMED",
            echo_slot=int(echo_slot),
            native_slot=int(native_slot),
            native_recharge_ms=(
                round(float(native_recharge_ms), 1)
                if native_recharge_ms is not None
                else -1.0
            ),
            seed_source="native_roj",
        )
        return True

    def _advance_roj_echo_chain(self):
        if not self._is_roj_chain_active():
            return False
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            self._reset_roj_chain("combat_ended")
            return False
        if self._expire_roj_chain_if_needed():
            return False

        if self._roj_chain_state == ROJ_CHAIN_NATIVE_ROJ:
            native_slot = self._get_native_roj_slot()
            if not (1 <= native_slot <= 8):
                self._reset_roj_chain("native_roj_slot_missing")
                return False
            if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(native_slot) or 0) != int(
                Ray_of_Judgment_ID
            ):
                self._reset_roj_chain("native_roj_slot_changed")
                return False
            if not Routines.Checks.Skills.IsSkillSlotReady(native_slot):
                self._reset_roj_chain("native_roj_not_ready")
                return False

            did_cast = yield from self._cast_ray_of_judgment_smart(
                immediate=True,
                required_slot=native_slot,
            )
            if did_cast:
                self._roj_chain_native_target_id = int(
                    self._last_ray_of_judgment_target_id
                )
                self._roj_chain_state = ROJ_CHAIN_MIMICRY
                self._log_rotation_event(
                    "ROJ_PHASE3_NATIVE_OPENING_CAST",
                    target_id=int(self._roj_chain_native_target_id),
                    next_step="verified_arcane_mimicry",
                )
                return True
            return False

        if self._roj_chain_state == ROJ_CHAIN_MIMICRY:
            mimicry_slot = self._get_mimicry_home_slot()
            if not (1 <= mimicry_slot <= 8):
                self._reset_roj_chain("mimicry_slot_missing")
                return False
            mimicry_skill_id = int(
                GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(mimicry_slot) or 0
            )
            if mimicry_skill_id == int(Ray_of_Judgment_ID):
                self._mimicry_energy_wait_logged = False
                if self._has_self_effect(Arcane_Echo_ID):
                    self._roj_chain_state = ROJ_CHAIN_MIMICRY_ROJ
                    return False
                if self._can_begin_mimicry_echo_chain():
                    self._log_rotation_event(
                        "ROJ_PHASE3_MIMICRY_COPY_READY",
                        mimicry_slot=int(mimicry_slot),
                        seed_for="arcane_echo",
                    )
                    return (yield from self._begin_mimicry_echo_chain())
                return False
            if mimicry_skill_id != int(Arcane_Mimicry_ID):
                self._reset_roj_chain(
                    f"mimicry_wrong_copy_observed:{mimicry_skill_id}"
                )
                return False

            mimicry_busy = bool(self._roj_mimicry.is_busy())
            if mimicry_busy:
                return bool((yield from self._roj_mimicry.run(self)))

            mimicry_can_start = bool(self._roj_mimicry.can_start())
            donor_available = bool(self._roj_mimicry.has_verified_donor())
            if not mimicry_can_start or not donor_available:
                self._reset_roj_chain("verified_mimicry_donor_unavailable")
                return False

            if not self._can_afford_mimicry_opening():
                if self._should_reserve_for_mimicry_energy():
                    if not self._mimicry_energy_wait_logged:
                        self._log_rotation_event(
                            "ROJ_PHASE2_MIMICRY_ENERGY_RESERVE",
                            current_energy=round(self._current_energy_absolute(), 2),
                            required_energy=round(
                                self._mimicry_opening_energy_requirement(),
                                2,
                            ),
                            native_roj_already_cast=True,
                        )
                        self._mimicry_energy_wait_logged = True
                    return False
                self._reset_roj_chain("mimicry_energy_unreachable")
                return False

            self._mimicry_energy_wait_logged = False
            if (yield from self._roj_mimicry.run(self)):
                return True
            if not self._roj_mimicry.is_busy():
                last_result = str(
                    getattr(self._roj_mimicry, "last_result", "") or "not_started"
                )
                self._reset_roj_chain(f"mimicry_{last_result}")
            return False

        if self._roj_chain_state == ROJ_CHAIN_ECHO:
            return (yield from self._cast_arcane_echo_chain_step())

        if self._roj_chain_state == ROJ_CHAIN_NATIVE_ECHO_SETUP:
            native_slot = self._get_native_roj_slot()
            if not (1 <= native_slot <= 8):
                self._reset_roj_chain("native_echo_native_slot_missing")
                return False
            if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(native_slot) or 0) != int(
                Ray_of_Judgment_ID
            ):
                self._reset_roj_chain("native_echo_native_slot_changed")
                return False

            # Hard non-delay guarantee: if Auspicious used the remaining lead
            # time, abandon Echo setup and cast native RoJ immediately.
            if Routines.Checks.Skills.IsSkillSlotReady(native_slot):
                self._reset_roj_chain("native_roj_preempted_echo_setup")
                did_cast = yield from self._cast_ray_of_judgment_smart(
                    immediate=True,
                    required_slot=native_slot,
                )
                if did_cast:
                    self._log_rotation_event(
                        "ROJ_PHASE3_6_NATIVE_ROJ_PREEMPTED_ECHO_SETUP",
                        target_id=int(self._last_ray_of_judgment_target_id),
                        native_slot=int(native_slot),
                    )
                return did_cast

            return (yield from self._cast_arcane_echo_chain_step(
                next_state=ROJ_CHAIN_NATIVE_ECHO_ROJ,
            ))

        if self._roj_chain_state == ROJ_CHAIN_NATIVE_ECHO_ROJ:
            native_slot = self._get_native_roj_slot()
            if not (1 <= native_slot <= 8):
                self._reset_roj_chain("native_echo_seed_slot_missing")
                return False
            if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(native_slot) or 0) != int(
                Ray_of_Judgment_ID
            ):
                self._reset_roj_chain("native_echo_seed_slot_changed")
                return False
            if not self._has_self_effect(Arcane_Echo_ID):
                self._reset_roj_chain("native_echo_effect_not_active")
                return False
            if not Routines.Checks.Skills.IsSkillSlotReady(native_slot):
                return False

            did_cast = yield from self._cast_ray_of_judgment_smart(
                immediate=True,
                required_slot=native_slot,
            )
            if did_cast:
                self._roj_chain_native_target_id = int(
                    self._last_ray_of_judgment_target_id
                )
                self._roj_chain_state = ROJ_CHAIN_ECHO_COPY
                self._roj_chain_seed_cast_ms = self._now_ms()
                self._log_rotation_event(
                    "ROJ_PHASE3_6_NATIVE_ECHO_SEED_CAST",
                    target_id=int(self._roj_chain_native_target_id),
                    native_slot=int(native_slot),
                    echo_slot=int(self._roj_chain_echo_slot),
                )
                return True
            return False

        if self._roj_chain_state == ROJ_CHAIN_MIMICRY_ROJ:
            mimicry_slot = self._get_mimicry_home_slot()
            if not (1 <= mimicry_slot <= 8):
                self._reset_roj_chain("mimicry_seed_slot_missing")
                return False
            if int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(mimicry_slot) or 0) != int(
                Ray_of_Judgment_ID
            ):
                self._reset_roj_chain("mimicry_seed_copy_lost")
                return False
            if not Routines.Checks.Skills.IsSkillSlotReady(mimicry_slot):
                return False

            did_cast = yield from self._cast_ray_of_judgment_smart(
                exclude_target_id=int(self._roj_chain_native_target_id),
                immediate=True,
                required_slot=mimicry_slot,
            )
            if did_cast:
                self._roj_chain_state = ROJ_CHAIN_ECHO_COPY
                self._roj_chain_seed_cast_ms = self._now_ms()
                self._log_rotation_event(
                    "ROJ_PHASE3_MIMICRY_ECHO_SEED_CAST",
                    target_id=int(self._last_ray_of_judgment_target_id),
                    native_target_id=int(self._roj_chain_native_target_id),
                    mimicry_slot=int(mimicry_slot),
                    echo_slot=int(self._roj_chain_echo_slot),
                )
                return True
            return False

        if self._roj_chain_state == ROJ_CHAIN_ECHO_COPY:
            echo_slot = int(self._roj_chain_echo_slot or 0)
            copied_skill_id = int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(echo_slot) or 0)
            if copied_skill_id == int(Ray_of_Judgment_ID):
                if not Routines.Checks.Skills.IsSkillSlotReady(echo_slot):
                    return False
                did_cast = yield from self._cast_ray_of_judgment_smart(
                    exclude_target_id=int(self._last_ray_of_judgment_target_id),
                    immediate=True,
                    required_slot=echo_slot,
                )
                if did_cast:
                    copied_target_id = int(self._last_ray_of_judgment_target_id)
                    self._log_rotation_event(
                        "ROJ_PHASE1_ECHO_COPY_CAST",
                        target_id=copied_target_id,
                        echo_slot=echo_slot,
                    )
                    self._reset_roj_chain("echo_copy_spent")
                    return True
                return False

            copy_wait_ms = self._now_ms() - float(self._roj_chain_seed_cast_ms or 0.0)
            if copy_wait_ms >= ROJ_ECHO_COPY_APPEAR_TIMEOUT_MS:
                self._reset_roj_chain("echo_copy_not_observed")
            return False

        self._reset_roj_chain("unknown_state")
        return False

    def _cast_patient_spirit_smart(self):
        if not self.IsSkillEquipped(Patient_Spirit_ID):
            return False
        if not self._can_spend_optional_energy(Patient_Spirit_ID):
            return False
        if not self.CanCastSkillID(Patient_Spirit_ID):
            return False
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False

        patient = self.GetCustomSkill(Patient_Spirit_ID)
        threshold = max(0.0, min(1.0, float(patient.Conditions.LessLife or 0.70)))
        target_agent_id = self.ResolveRankedPartyAllyTarget(
            Patient_Spirit_ID,
            patient,
            validator=lambda agent_id: (
                Agent.IsAlive(agent_id)
                and float(Agent.GetHealth(agent_id)) <= threshold
                and not Routines.Checks.Agents.HasEffect(agent_id, Patient_Spirit_ID)
            ),
            rank_key=lambda agent_id: (
                float(Agent.GetHealth(agent_id)),
                -float(self.GetPartyHealthDelta(agent_id)),
            ),
        )
        if not target_agent_id:
            return False
        return (yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Patient_Spirit_ID,
            target_agent_id=int(target_agent_id),
            log=False,
            aftercast_delay=250,
        ))

    def _cast_reversal_of_damage_smart(self):
        if not self.IsSkillEquipped(Reversal_of_Damage_ID):
            return False
        if not self._can_spend_optional_energy(Reversal_of_Damage_ID):
            return False
        if not self.CanCastSkillID(Reversal_of_Damage_ID):
            return False
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False

        reversal = self.GetCustomSkill(Reversal_of_Damage_ID)
        threshold = max(0.0, min(1.0, float(reversal.Conditions.LessLife or 0.80)))
        pressure_cache: dict[int, tuple[int, int]] = {}

        def pressure_counts(agent_id: int) -> tuple[int, int]:
            cached = pressure_cache.get(int(agent_id))
            if cached is not None:
                return cached
            try:
                x, y = Agent.GetXY(agent_id)
                enemies = Routines.Agents.GetFilteredEnemyArray(x, y, Range.Touch.value)
                enemies = AgentArray.Filter.ByCondition(
                    enemies,
                    lambda enemy_id: Agent.IsValid(enemy_id) and Agent.IsAlive(enemy_id),
                )
                melee_count = sum(
                    1 for enemy_id in (enemies or [])
                    if Routines.Checks.Agents.IsMelee(enemy_id)
                )
                result = (int(melee_count), int(len(enemies or [])))
            except Exception:
                result = (0, 0)
            pressure_cache[int(agent_id)] = result
            return result

        target_agent_id = self.ResolveRankedPartyAllyTarget(
            Reversal_of_Damage_ID,
            reversal,
            validator=lambda agent_id: (
                Agent.IsAlive(agent_id)
                and float(Agent.GetHealth(agent_id)) <= threshold
                and pressure_counts(agent_id)[1] > 0
                and not Routines.Checks.Agents.HasEffect(agent_id, Reversal_of_Damage_ID)
            ),
            rank_key=lambda agent_id: (
                -pressure_counts(agent_id)[0],
                -pressure_counts(agent_id)[1],
                float(Agent.GetHealth(agent_id)),
            ),
        )
        if not target_agent_id:
            return False
        return (yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Reversal_of_Damage_ID,
            target_agent_id=int(target_agent_id),
            log=False,
            aftercast_delay=250,
        ))

    def _cast_supported_party_skill(self):
        """Use optional support only while the RoJ lane has no pending work."""
        if (
            self.IsSkillEquipped(Cure_Hex_ID)
            and self._can_spend_optional_energy(Cure_Hex_ID)
        ):
            if (yield from self.skills.Monk.HealingPrayers.Cure_Hex(
                min_priority=HexRemovalPriority.HIGH,
            )):
                self._log_rotation_event("ROJ_PHASE1_SUPPORT_CAST", skill_id=Cure_Hex_ID)
                return True

        if (
            self.IsSkillEquipped(Smite_Hex_ID)
            and self._can_spend_optional_energy(Smite_Hex_ID)
        ):
            if (yield from self.skills.Monk.SmitingPrayers.Smite_Hex(
                min_priority=HexRemovalPriority.HIGH,
            )):
                self._log_rotation_event("ROJ_PHASE1_SUPPORT_CAST", skill_id=Smite_Hex_ID)
                return True

        if (
            self.IsSkillEquipped(Shield_of_Absorption_ID)
            and self._can_spend_optional_energy(Shield_of_Absorption_ID)
        ):
            if (yield from self.skills.Monk.ProtectionPrayers.Shield_of_Absorption()):
                self._log_rotation_event(
                    "ROJ_PHASE1_SUPPORT_CAST",
                    skill_id=Shield_of_Absorption_ID,
                )
                return True

        if (yield from self._cast_reversal_of_damage_smart()):
            self._log_rotation_event(
                "ROJ_PHASE1_SUPPORT_CAST",
                skill_id=Reversal_of_Damage_ID,
            )
            return True

        if (yield from self._cast_patient_spirit_smart()):
            self._log_rotation_event("ROJ_PHASE1_SUPPORT_CAST", skill_id=Patient_Spirit_ID)
            return True

        if (
            self.IsSkillEquipped(Dwaynas_Kiss_ID)
            and self._can_spend_optional_energy(Dwaynas_Kiss_ID)
        ):
            if (yield from self.skills.Monk.HealingPrayers.Dwaynas_Kiss()):
                self._log_rotation_event("ROJ_PHASE1_SUPPORT_CAST", skill_id=Dwaynas_Kiss_ID)
                return True

        # Medium-priority hexes are cleaned only with a healthy energy reserve;
        # low-value hexes cannot consume the energy intended for the next chain.
        try:
            player_energy_pct = float(Agent.GetEnergy(Player.GetAgentID()))
        except Exception:
            player_energy_pct = 0.0
        if player_energy_pct >= 0.55:
            if (
                self.IsSkillEquipped(Cure_Hex_ID)
                and self._can_spend_optional_energy(Cure_Hex_ID)
            ):
                if (yield from self.skills.Monk.HealingPrayers.Cure_Hex(
                    min_priority=HexRemovalPriority.MEDIUM,
                )):
                    self._log_rotation_event("ROJ_PHASE1_SUPPORT_CAST", skill_id=Cure_Hex_ID)
                    return True
            if (
                self.IsSkillEquipped(Smite_Hex_ID)
                and self._can_spend_optional_energy(Smite_Hex_ID)
            ):
                if (yield from self.skills.Monk.SmitingPrayers.Smite_Hex(
                    min_priority=HexRemovalPriority.MEDIUM,
                )):
                    self._log_rotation_event("ROJ_PHASE1_SUPPORT_CAST", skill_id=Smite_Hex_ID)
                    return True
        return False

    @staticmethod
    def _is_target_attacking_safe(target_agent_id: int) -> bool:
        try:
            return bool(Agent.IsAttacking(int(target_agent_id)))
        except Exception:
            return False

    @staticmethod
    def _is_target_knocked_down_safe(target_agent_id: int) -> bool:
        try:
            return bool(Agent.IsKnockedDown(int(target_agent_id)))
        except Exception:
            return False

    def _get_bane_target(self) -> tuple[int, int, bool, int]:
        """Prefer an active attacker, then damage the shared cleanup focus."""
        anchor, members, hard_focus = self._get_authoritative_roj_packet(
            consumer_role="roj_bane",
        )
        if anchor <= 0 or not members:
            return 0, 0, False, 0

        now_tick = self._game_tick()
        try:
            player_pos = Player.GetXY()
        except Exception:
            player_pos = (0.0, 0.0)

        ranked: list[tuple[tuple[int, int, int, int, int, float, float, int], int]] = []
        for target_agent_id in members:
            target_agent_id = int(target_agent_id or 0)
            if not self._is_enemy_alive_valid(target_agent_id):
                continue
            # A short target lease is enough to spread simultaneous signets.
            # On a single cleanup target it expires quickly, so the remaining
            # Monks can continue using Bane one after another.
            if self._coordination_lock_count(
                BANE_TARGET_LOCK_ID,
                target_agent_id,
                now_tick=now_tick,
            ) > 0:
                continue
            attacking = self._is_target_attacking_safe(target_agent_id)
            knocked_down = self._is_target_knocked_down_safe(target_agent_id)
            try:
                distance_sq = self._distance_sq(player_pos, Agent.GetXY(target_agent_id))
            except Exception:
                distance_sq = 0.0
            ranked.append((
                (
                    0 if attacking and not knocked_down else 1,
                    0 if not knocked_down else 1,
                    -int(self._is_safe_dangerous_cast(target_agent_id)),
                    -int(self._is_healer_focus_target(target_agent_id)),
                    -int(self._count_adjacent_enemies(target_agent_id)),
                    float(self._enemy_health(target_agent_id)),
                    float(distance_sq),
                    int(target_agent_id),
                ),
                target_agent_id,
            ))

        if not ranked:
            return anchor, 0, hard_focus, len(members)
        ranked.sort(key=lambda item: item[0])
        return anchor, int(ranked[0][1]), hard_focus, len(members)

    def _cast_bane_signet_smart(self):
        if not self.IsSkillEquipped(Bane_Signet_ID):
            return False
        if not self.CanCastSkillID(Bane_Signet_ID):
            return False
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False

        slot = int(GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Bane_Signet_ID) or 0)
        if not (1 <= slot <= 8) or not self.CanCastSkillSlot(slot):
            return False
        anchor_agent_id, target_agent_id, hard_focus, packet_size = self._get_bane_target()
        if anchor_agent_id <= 0 or target_agent_id <= 0:
            return False

        previous_enemy_target = int(Player.GetTargetID() or 0)
        if previous_enemy_target != target_agent_id:
            yield from Routines.Yield.Agents.ChangeTarget(target_agent_id)
        if not self._is_ray_of_judgment_final_target_usable(
            target_agent_id,
            expected_anchor_id=anchor_agent_id,
        ):
            yield from self.RestoreEnemyTarget(previous_enemy_target)
            return False
        if not self.CanCastSkillSlot(slot):
            yield from self.RestoreEnemyTarget(previous_enemy_target)
            return False

        reserved, reason = self._reserve_bane_cast(
            anchor_agent_id=int(anchor_agent_id),
            target_agent_id=int(target_agent_id),
        )
        if not reserved:
            self._log_coordination_wait(
                reason,
                anchor_id=int(anchor_agent_id),
                target_id=int(target_agent_id),
            )
            yield from self.RestoreEnemyTarget(previous_enemy_target)
            return False

        target_attacking = self._is_target_attacking_safe(target_agent_id)
        target_knocked_down = self._is_target_knocked_down_safe(target_agent_id)
        GLOBAL_CACHE.SkillBar.UseSkill(
            int(slot),
            target_agent_id=int(target_agent_id),
            aftercast_delay=250,
        )
        self._mark_local_cast_pending(250)
        self.SetTickSuccess()
        yield from self.RestoreEnemyTarget(previous_enemy_target)
        self._log_rotation_event(
            "ROJ_PHASE3_7_BANE_CAST",
            target_id=int(target_agent_id),
            anchor_id=int(anchor_agent_id),
            packet_size=int(packet_size),
            hard_focus=bool(hard_focus),
            target_attacking=bool(target_attacking),
            damage_only_fallback=bool(not target_attacking or target_knocked_down),
            policy="supported_filler_only_roj_never_held",
        )
        return True

    def _get_symbol_target(self) -> tuple[int, int, bool, int]:
        anchor, members, hard_focus = self._get_authoritative_roj_packet(
            consumer_role="roj_symbol",
        )
        if anchor <= 0 or not members:
            return 0, 0, False, 0

        packet_size = int(len(members))
        normal_cluster_cap, _emergency_cluster_cap, normal_target_cap = (
            self._roj_coverage_policy(packet_size, bool(hard_focus))
        )
        now_tick = self._game_tick()
        symbol_cluster_coverage = self._coordination_lock_count(
            SYMBOL_CLUSTER_COVERAGE_LOCK_ID,
            int(anchor),
            now_tick=now_tick,
        )
        if symbol_cluster_coverage >= SYMBOL_MAX_CLUSTER_COVERAGE:
            return anchor, 0, hard_focus, packet_size
        roj_cluster_coverage = self._coordination_lock_count(
            ROJ_CLUSTER_COVERAGE_LOCK_ID,
            int(anchor),
            now_tick=now_tick,
        )
        if symbol_cluster_coverage + roj_cluster_coverage >= normal_cluster_cap:
            return anchor, 0, hard_focus, packet_size
        try:
            player_pos = Player.GetXY()
        except Exception:
            player_pos = (0.0, 0.0)

        ranked: list[tuple[tuple[int, int, int, int, int, int, float, int], int]] = []
        for target_agent_id in members:
            target_agent_id = int(target_agent_id or 0)
            if not self._is_enemy_alive_valid(target_agent_id):
                continue
            # The requested <=5% finisher belongs to RoJ itself.  Symbol does
            # not add another five-second field to an already finished target.
            if self._enemy_health(target_agent_id) <= ROJ_LOW_HP_FINISH_THRESHOLD:
                continue
            symbol_coverage = self._coordination_lock_count(
                SYMBOL_TARGET_COVERAGE_LOCK_ID,
                target_agent_id,
                now_tick=now_tick,
            )
            if symbol_coverage >= SYMBOL_MAX_TARGET_COVERAGE:
                continue
            roj_coverage = self._coordination_lock_count(
                ROJ_TARGET_COVERAGE_LOCK_ID,
                target_agent_id,
                now_tick=now_tick,
            )
            combined_target_cap = (
                ROJ_MAX_TARGET_COVERAGE if bool(hard_focus) else int(normal_target_cap)
            )
            if symbol_coverage + roj_coverage >= combined_target_cap:
                continue
            try:
                distance_sq = self._distance_sq(player_pos, Agent.GetXY(target_agent_id))
            except Exception:
                distance_sq = 0.0
            ranked.append((
                (
                    int(symbol_coverage + roj_coverage),
                    int(symbol_coverage),
                    int(roj_coverage),
                    -int(self._is_safe_dangerous_cast(target_agent_id)),
                    -int(self._is_healer_focus_target(target_agent_id)),
                    -int(self._count_adjacent_enemies(target_agent_id)),
                    float(distance_sq),
                    int(target_agent_id),
                ),
                target_agent_id,
            ))

        if not ranked:
            return anchor, 0, hard_focus, packet_size
        ranked.sort(key=lambda item: item[0])
        return anchor, int(ranked[0][1]), hard_focus, packet_size

    def _cast_symbol_of_wrath_smart(self):
        if not self.IsSkillEquipped(Symbol_of_Wrath_ID):
            return False
        if not self._can_spend_optional_energy(Symbol_of_Wrath_ID):
            return False
        if not self.CanCastSkillID(Symbol_of_Wrath_ID):
            return False
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False

        slot = int(GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Symbol_of_Wrath_ID) or 0)
        if not (1 <= slot <= 8) or not self.CanCastSkillSlot(slot):
            return False
        anchor_agent_id, target_agent_id, hard_focus, packet_size = self._get_symbol_target()
        if anchor_agent_id <= 0 or target_agent_id <= 0:
            return False

        previous_enemy_target = int(Player.GetTargetID() or 0)
        if previous_enemy_target != target_agent_id:
            yield from Routines.Yield.Agents.ChangeTarget(target_agent_id)
        if not self._is_ray_of_judgment_final_target_usable(
            target_agent_id,
            expected_anchor_id=anchor_agent_id,
        ) or self._enemy_health(target_agent_id) <= ROJ_LOW_HP_FINISH_THRESHOLD:
            yield from self.RestoreEnemyTarget(previous_enemy_target)
            return False
        if not self.CanCastSkillSlot(slot):
            yield from self.RestoreEnemyTarget(previous_enemy_target)
            return False

        reserved, reason = self._reserve_symbol_cast(
            anchor_agent_id=int(anchor_agent_id),
            target_agent_id=int(target_agent_id),
            packet_size=int(packet_size),
            hard_focus=bool(hard_focus),
        )
        if not reserved:
            self._log_coordination_wait(
                reason,
                anchor_id=int(anchor_agent_id),
                target_id=int(target_agent_id),
            )
            yield from self.RestoreEnemyTarget(previous_enemy_target)
            return False

        GLOBAL_CACHE.SkillBar.UseSkill(
            int(slot),
            target_agent_id=int(target_agent_id),
            aftercast_delay=250,
        )
        self._mark_local_cast_pending(250)
        self.SetTickSuccess()
        yield from self.RestoreEnemyTarget(previous_enemy_target)
        self._log_rotation_event(
            "ROJ_PHASE1_SYMBOL_CAST",
            target_id=int(target_agent_id),
            anchor_id=int(anchor_agent_id),
            cluster_hits=int(self._count_adjacent_enemies(target_agent_id)),
            hard_focus=bool(hard_focus),
            packet_size=int(packet_size),
            policy="phase3_1_same_focus_combined_coverage_filler_only",
        )
        return True

    def _run_local_skill_logic(self):
        self._refresh_temporary_roj_slots()
        try:
            self._roj_mimicry.observe()
        except Exception:
            pass

        refresh_aoe_danger_zones()
        if avoid_active_aoe_if_needed(role="roj", allow_actions_at_safe_hold=True):
            return True

        close_pressure = bool(self.IsInAggro() or self.IsCloseToAggro())
        self._expire_roj_chain_if_needed()
        if self._is_roj_chain_active() and not close_pressure:
            self._reset_roj_chain("combat_ended")

        # Once started, the protected lane owns every cast opportunity until
        # native RoJ, verified Mimicry, Echo, and both copied RoJs have
        # resolved. No supported skill can interleave.
        if self._is_roj_chain_active():
            if not Routines.Checks.Skills.CanCast():
                return False
            if (yield from self._advance_roj_echo_chain()):
                return True
            if self._is_roj_chain_active():
                return False

        # Target acquisition and guarded Mimicry dispatch own the tick until
        # the physical Mimicry slot is positively observed as RoJ or aborted.
        try:
            mimicry_busy = bool(self._roj_mimicry.is_busy())
        except Exception:
            mimicry_busy = False
        if mimicry_busy:
            if (yield from self._roj_mimicry.run(self)):
                return True
            if self._roj_mimicry.is_busy():
                return False

        if not Routines.Checks.Skills.CanCast():
            return False

        if close_pressure:
            # Recover an already active Echo before considering any other skill.
            self._resume_existing_echo_if_needed()
            if self._is_roj_chain_active():
                if (yield from self._advance_roj_echo_chain()):
                    return True
                return False

            # Any temporary RoJ that is ready is more urgent than setup or the
            # native slot.  This is what gives both 20-second copies a realistic
            # first and second cast inside RoJ's 15-second recharge window.
            ready_copy_slot = self._get_ready_temporary_roj_slot()
            if ready_copy_slot:
                if (yield from self._cast_ray_of_judgment_smart(
                    immediate=True,
                    required_slot=ready_copy_slot,
                )):
                    return True
                if self._get_roj_candidates():
                    return False

            # Main rotation: native RoJ first, then verified Mimicry, optional
            # Auspicious, Echo, Mimicry-RoJ seed, and Echo-copy RoJ. The full
            # chain starts only when its copy slots and donor are ready; if not,
            # the free lane below still spends native RoJ immediately.
            if self._can_begin_native_first_roj_chain():
                if (yield from self._begin_native_first_roj_chain()):
                    return True
                if self._is_roj_chain_active():
                    return False

            # Never hold a ready RoJ merely because the complete copy chain is
            # unavailable. A temporary copy is selected before the native slot.
            ready_roj_slot, native_roj_slot = self._get_ready_ray_of_judgment_slot()
            if ready_roj_slot:
                # Native RoJ remains free-running when energy permits, but it
                # may not consume the reserve for a temporary copy's required
                # second cast.  A ready temporary copy was already handled
                # above and always keeps priority.
                if (
                    int(ready_roj_slot) == int(native_roj_slot)
                    and not self._can_spend_optional_energy(Ray_of_Judgment_ID)
                ):
                    return False
                if (yield from self._cast_ray_of_judgment_smart(immediate=True)):
                    self._log_rotation_event(
                        "ROJ_PHASE1_FREE_ROJ_CAST",
                        target_id=int(self._last_ray_of_judgment_target_id),
                        slot=int(ready_roj_slot),
                    )
                    return True
                # A legal target exists but another cast gate (for example a
                # short team claim) still holds: do not let support reorder RoJ.
                if self._get_roj_candidates():
                    return False

            # Mimicry remains the preferred copy route. If it cannot be ready
            # for this native-RoJ cycle, pre-arm Echo only inside the measured
            # setup window. This block is intentionally after the free-ready
            # lane: an already-ready native RoJ never waits for Echo.
            native_echo_plan = self._get_native_echo_fallback_plan()
            if native_echo_plan is not None:
                (
                    use_auspicious,
                    native_recharge_ms,
                    earliest_ms,
                    latest_ms,
                ) = native_echo_plan
                if (yield from self._begin_native_echo_fallback(
                    use_auspicious=bool(use_auspicious),
                    native_recharge_ms=float(native_recharge_ms),
                    earliest_ms=float(earliest_ms),
                    latest_ms=float(latest_ms),
                )):
                    return True
                if self._is_roj_chain_active():
                    return False

        # All remaining skills are supported-only.  They run only when no Echo
        # chain or ready RoJ is waiting for the cast lane.
        if (yield from self._cast_supported_party_skill()):
            return True

        # Bane is additive control/damage only.  Every ready native/copied RoJ
        # and every protected Mimicry/Echo step has already had first refusal.
        if close_pressure and (yield from self._cast_bane_signet_smart()):
            return True

        if close_pressure and (yield from self._cast_symbol_of_wrath_smart()):
            return True

        if (
            close_pressure
            and self.IsSkillEquipped(Air_of_Superiority_ID)
            and self._can_spend_optional_energy(Air_of_Superiority_ID)
            and (yield from self.skills.Any.PvE.Air_of_Superiority())
        ):
            self._log_rotation_event(
                "ROJ_PHASE1_AIR_OF_SUPERIORITY_CAST",
                policy="supported_filler_only",
            )
            return True

        # Generic HeroAI never receives these slots; every Mimicry dispatch is
        # owned by the verified native-RoJ controller above.
        return False
