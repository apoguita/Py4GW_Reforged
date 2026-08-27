from __future__ import annotations

"""Arcane Mimicry target discovery for Keystone Mesmers.

The controller probes primary-Monk party members one at a time.  It confirms a
Monk only when Arcane Mimicry's own skill-bar slot becomes Signet of Judgment.
A different copied elite rejects only the Monk that was successfully probed.
Failed casts, timeouts and unreadable skill-bar states never reject a Monk.
"""

from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Callable, Iterable


@dataclass(slots=True)
class SoJMimicryState:
    """Pure state machine; intentionally independent of Py4GW for testing."""

    map_id: int = 0
    monk_signature: tuple[int, ...] = ()
    mimicry_slot: int = 0
    confirmed_soj_monk: int = 0
    rejected_monk_ids: set[int] = field(default_factory=set)
    pending_monk_id: int = 0
    pending_since: float = 0.0
    last_result: str = "idle"

    def reset_discovery(self, *, reason: str) -> None:
        self.mimicry_slot = 0
        self.confirmed_soj_monk = 0
        self.rejected_monk_ids.clear()
        self.pending_monk_id = 0
        self.pending_since = 0.0
        self.last_result = f"reset:{reason}"

    def update_context(self, map_id: int, monk_ids: Iterable[int]) -> bool:
        """Reset only when a real map/Monk-party context changes."""
        signature = tuple(sorted({int(agent_id) for agent_id in monk_ids if int(agent_id) > 0}))
        map_id = int(map_id or 0)

        if self.map_id == 0 and not self.monk_signature:
            self.map_id = map_id
            self.monk_signature = signature
            return False

        map_changed = bool(map_id and self.map_id and map_id != self.map_id)
        team_changed = signature != self.monk_signature
        if not map_changed and not team_changed:
            if map_id:
                self.map_id = map_id
            return False

        self.map_id = map_id or self.map_id
        self.monk_signature = signature
        self.reset_discovery(reason="map" if map_changed else "team")
        return True

    def begin_probe(self, monk_id: int, *, now: float) -> None:
        self.pending_monk_id = int(monk_id)
        self.pending_since = float(now)
        self.last_result = f"probe:{int(monk_id)}"

    def clear_pending_unknown(self, *, reason: str) -> None:
        """Clear a failed/unreadable probe without blacklisting its target."""
        target_id = self.pending_monk_id
        self.pending_monk_id = 0
        self.pending_since = 0.0
        self.last_result = f"unknown:{target_id}:{reason}"

    def observe_slot(
        self,
        *,
        current_skill_id: int,
        arcane_mimicry_id: int,
        signet_of_judgment_id: int,
        now: float,
        pending_timeout_seconds: float,
        is_elite_skill: Callable[[int], bool | None] | None = None,
    ) -> str:
        """Classify the copied skill after a probe.

        Returns one of: ``idle``, ``pending``, ``confirmed``, ``rejected`` or
        ``unknown``.  A Monk is rejected only when a non-SoJ copied elite is
        positively visible in Arcane Mimicry's original slot.
        """
        if not self.pending_monk_id:
            return "idle"

        current_skill_id = int(current_skill_id or 0)
        arcane_mimicry_id = int(arcane_mimicry_id or 0)
        signet_of_judgment_id = int(signet_of_judgment_id or 0)
        target_id = int(self.pending_monk_id)

        if current_skill_id == signet_of_judgment_id and signet_of_judgment_id:
            self.confirmed_soj_monk = target_id
            self.rejected_monk_ids.discard(target_id)
            self.pending_monk_id = 0
            self.pending_since = 0.0
            self.last_result = f"confirmed:{target_id}"
            return "confirmed"

        replacement_visible = bool(
            current_skill_id
            and current_skill_id != arcane_mimicry_id
            and current_skill_id != signet_of_judgment_id
        )
        if replacement_visible:
            elite_status: bool | None = None
            if is_elite_skill is not None:
                try:
                    elite_status = is_elite_skill(current_skill_id)
                except Exception:
                    elite_status = None

            # Unknown API support is treated as a copied elite because Arcane
            # Mimicry's own slot visibly changed. A definite non-elite is not.
            if elite_status is not False:
                self.rejected_monk_ids.add(target_id)
                self.pending_monk_id = 0
                self.pending_since = 0.0
                self.last_result = f"rejected:{target_id}:{current_skill_id}"
                return "rejected"

        if float(now) - self.pending_since >= float(pending_timeout_seconds):
            self.clear_pending_unknown(reason="timeout")
            return "unknown"

        return "pending"


class KeystoneSoJMimicry:
    """Runtime adapter around :class:`SoJMimicryState`."""

    def __init__(self, *, pending_timeout_seconds: float = 5.0) -> None:
        self.state = SoJMimicryState()
        self.pending_timeout_seconds = max(1.0, float(pending_timeout_seconds))
        self._arcane_mimicry_id = 0
        self._signet_of_judgment_id = 0

    @property
    def confirmed_soj_monk(self) -> int:
        return self.state.confirmed_soj_monk

    @property
    def rejected_monk_ids(self) -> frozenset[int]:
        return frozenset(self.state.rejected_monk_ids)

    def status(self) -> dict[str, Any]:
        """Small diagnostic snapshot suitable for logging/debug panels."""
        return {
            "map_id": self.state.map_id,
            "monks": self.state.monk_signature,
            "mimicry_slot": self.state.mimicry_slot,
            "confirmed_soj_monk": self.state.confirmed_soj_monk,
            "rejected_monk_ids": tuple(sorted(self.state.rejected_monk_ids)),
            "pending_monk_id": self.state.pending_monk_id,
            "last_result": self.state.last_result,
        }

    @staticmethod
    def _as_int(value: Any) -> int:
        try:
            return int(getattr(value, "value", value))
        except Exception:
            return 0

    def _resolve_skill_ids(self) -> tuple[int, int]:
        if self._arcane_mimicry_id and self._signet_of_judgment_id:
            return self._arcane_mimicry_id, self._signet_of_judgment_id

        from Py4GWCoreLib.Skill import Skill

        self._arcane_mimicry_id = int(Skill.GetID("Arcane_Mimicry") or 0)
        self._signet_of_judgment_id = int(Skill.GetID("Signet_of_Judgment") or 0)
        return self._arcane_mimicry_id, self._signet_of_judgment_id

    def _party_agent_ids(self) -> list[int]:
        """Return actual party agents, excluding pets/minions/allied NPCs."""
        from Py4GWCoreLib import Party

        result: list[int] = []

        try:
            for player in Party.GetPlayers() or []:
                login_number = int(getattr(player, "login_number", 0) or 0)
                agent_id = int(Party.Players.GetAgentIDByLoginNumber(login_number) or 0)
                if agent_id:
                    result.append(agent_id)
        except Exception:
            pass

        for getter_name in ("GetHeroes", "GetHenchmen"):
            try:
                getter = getattr(Party, getter_name)
                for member in getter() or []:
                    agent_id = int(getattr(member, "agent_id", 0) or 0)
                    if agent_id:
                        result.append(agent_id)
            except Exception:
                continue

        # Compatibility fallback for older Py4GW builds whose party wrappers do
        # not expose all member types. Profession filtering below still applies.
        if not result:
            try:
                from Py4GWCoreLib import AgentArray

                result.extend(int(agent_id) for agent_id in (AgentArray.GetAllyArray() or []))
            except Exception:
                pass

        return sorted(set(result))

    def _party_primary_monks(self) -> list[int]:
        from Py4GWCoreLib import Agent, Player, Profession

        self_id = int(Player.GetAgentID() or 0)
        monk_profession_id = self._as_int(Profession.Monk)
        monks: list[int] = []

        for agent_id in self._party_agent_ids():
            if not agent_id or agent_id == self_id:
                continue
            try:
                primary, _secondary = Agent.GetProfessionIDs(agent_id)
                if self._as_int(primary) == monk_profession_id:
                    monks.append(int(agent_id))
            except Exception:
                continue

        return sorted(set(monks))

    @staticmethod
    def _is_alive_and_in_range(agent_id: int) -> bool:
        from Py4GWCoreLib import Agent, Player, Range, Utils

        try:
            if not Agent.IsValid(agent_id) or not Agent.IsAlive(agent_id):
                return False
            return Utils.Distance(Player.GetXY(), Agent.GetXY(agent_id)) <= float(Range.Spellcast.value)
        except Exception:
            return False

    @staticmethod
    def _is_elite_skill(skill_id: int) -> bool | None:
        """Return None when the installed API has no elite flag helper."""
        try:
            from Py4GWCoreLib import GLOBAL_CACHE

            return bool(GLOBAL_CACHE.Skill.Flags.IsElite(int(skill_id)))
        except Exception:
            return None

    def _update_context_and_observe(self) -> tuple[int, int]:
        from Py4GWCoreLib import Map
        from Py4GWCoreLib.Skillbar import SkillBar

        arcane_mimicry_id, signet_of_judgment_id = self._resolve_skill_ids()
        map_id = int(Map.GetMapID() or 0)
        party_loaded = True
        try:
            from Py4GWCoreLib import Party

            party_loaded = bool(Party.IsPartyLoaded())
        except Exception:
            pass

        # Do not erase a valid discovery state during map/party loading frames.
        if map_id and party_loaded:
            monks = self._party_primary_monks()
            self.state.update_context(map_id, monks)

        if not self.state.mimicry_slot and arcane_mimicry_id:
            self.state.mimicry_slot = int(SkillBar.GetSlotBySkillID(arcane_mimicry_id) or 0)

        if self.state.pending_monk_id and self.state.mimicry_slot:
            current_skill_id = int(SkillBar.GetSkillIDBySlot(self.state.mimicry_slot) or 0)
            self.state.observe_slot(
                current_skill_id=current_skill_id,
                arcane_mimicry_id=arcane_mimicry_id,
                signet_of_judgment_id=signet_of_judgment_id,
                now=monotonic(),
                pending_timeout_seconds=self.pending_timeout_seconds,
                is_elite_skill=self._is_elite_skill,
            )

        return arcane_mimicry_id, signet_of_judgment_id

    def _pick_target(self) -> int:
        confirmed = int(self.state.confirmed_soj_monk or 0)
        if confirmed:
            # A confirmed SoJ Monk remains authoritative. Temporary death/range
            # issues do not clear it and do not trigger probing of another Monk.
            return confirmed if self._is_alive_and_in_range(confirmed) else 0

        for monk_id in self.state.monk_signature:
            if monk_id in self.state.rejected_monk_ids:
                continue
            if self._is_alive_and_in_range(monk_id):
                return int(monk_id)
        return 0

    @staticmethod
    def _yield_result(value: Any):
        if hasattr(value, "__next__") or hasattr(value, "send"):
            return (yield from value)
        return value

    @staticmethod
    def _can_cast(build: Any, skill_id: int) -> bool:
        try:
            checker = getattr(build, "CanCastSkillID", None)
            if checker is not None:
                return bool(checker(skill_id))
        except Exception:
            return False

        try:
            from Py4GWCoreLib import Routines

            return bool(Routines.Checks.Skills.CanCast())
        except Exception:
            return True

    def run(self, build: Any, *, allow_cast: bool = True):
        """Probe/cast once. Use as ``yield from controller.run(build)``.

        The method returns True only when it issued or completed an Arcane
        Mimicry cast. Observation/classification itself returns False so normal
        Keystone skill logic can continue on the same tick.
        """
        from Py4GWCoreLib.Skillbar import SkillBar

        arcane_mimicry_id, _signet_of_judgment_id = self._update_context_and_observe()
        if not arcane_mimicry_id or not self.state.mimicry_slot:
            return False
        if self.state.pending_monk_id:
            return False
        if not allow_cast:
            # Observation/context maintenance still runs outside the setup
            # window, but no new Mimicry cast is issued.
            return False

        current_skill_id = int(SkillBar.GetSkillIDBySlot(self.state.mimicry_slot) or 0)
        if current_skill_id != arcane_mimicry_id:
            # A copied elite is still occupying Arcane Mimicry's slot.
            return False

        target_id = self._pick_target()
        if not target_id or not self._can_cast(build, arcane_mimicry_id):
            return False

        cast_fn = getattr(build, "CastSkillIDAndRestoreTarget", None)
        if cast_fn is not None:
            try:
                result = cast_fn(
                    skill_id=arcane_mimicry_id,
                    target_agent_id=target_id,
                    log=False,
                    aftercast_delay=250,
                )
                casted = yield from self._yield_result(result)
                if casted is False:
                    return False
                self.state.begin_probe(target_id, now=monotonic())
                return True
            except Exception:
                # Fall through to the stable low-level SkillBar call.
                pass

        try:
            SkillBar.UseSkill(self.state.mimicry_slot, target_id)
        except Exception:
            return False

        # Low-level UseSkill has no success return. The slot-change observation
        # decides later; timeout means unknown and never rejects the Monk.
        self.state.begin_probe(target_id, now=monotonic())
        return True


def install_keystone_soj_mimicry(
    controller_class: type,
    *,
    method_name: str = "_run_local_skill_logic",
    build_attribute: str | None = None,
) -> None:
    """Idempotently wrap a Keystone build/controller skill-decision method.

    ``build_attribute=None`` means the wrapped object itself is the BuildMgr.
    For a central controller that stores it as ``self.build``, pass
    ``build_attribute="build"``.
    """
    marker = f"_soj_mimicry_installed_{method_name}"
    if getattr(controller_class, marker, False):
        return

    original = getattr(controller_class, method_name, None)
    if original is None:
        raise AttributeError(
            f"{controller_class.__name__} has no method {method_name!r}"
        )

    def _yield_compatible(value: Any):
        if hasattr(value, "__next__") or hasattr(value, "send"):
            return (yield from value)
        return value

    def _patched(self: Any, *args: Any, **kwargs: Any):
        tracker = getattr(self, "_keystone_soj_mimicry", None)
        if tracker is None:
            tracker = KeystoneSoJMimicry()
            setattr(self, "_keystone_soj_mimicry", tracker)

        build = getattr(self, build_attribute, None) if build_attribute else self
        if build is not None and (yield from tracker.run(build)):
            return True

        return (yield from _yield_compatible(original(self, *args, **kwargs)))

    setattr(controller_class, method_name, _patched)
    setattr(controller_class, marker, True)
