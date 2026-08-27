from __future__ import annotations

import time

from Py4GWCoreLib import AgentArray, GLOBAL_CACHE, BuildMgr, Party, Profession, Range, Routines
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Builds.Skills import SkillsTemplate
from Py4GWCoreLib.Builds.Skills.AoEDangerPrediction import (
    avoid_active_aoe_if_needed,
    refresh_aoe_danger_zones,
)
from Py4GWCoreLib.Builds.Skills.BindingChainsCoordination import (
    packet_has_binding_chains,
    register_binding_chains_fired,
    release_binding_chains_reservation,
    reserve_binding_chains,
)
from Py4GWCoreLib.Builds.Skills.DangerInterruptClaim import (
    claim_best_dangerous_cast,
    get_casting_skill_id,
    interrupt_is_feasible,
    is_dangerous_cast,
    release_interrupt_claim,
    target_still_casting_skill,
)
from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import (
    get_team_cluster_anchor,
    get_team_cluster_members,
    is_support_or_caster,
)
from Py4GWCoreLib.HeroAI.targeting import GetAllAlliesArray
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Py4GWcorelib import Utils
from Py4GWCoreLib.Skill import Skill

Psychic_Instability_ID = Skill.GetID("Psychic_Instability")
Cry_of_Frustration_ID = Skill.GetID("Cry_of_Frustration")
Power_Drain_ID = Skill.GetID("Power_Drain")
Splinter_Weapon_ID = Skill.GetID("Splinter_Weapon")
Binding_Chains_ID = Skill.GetID("Binding_Chains")
Air_of_Superiority_ID = Skill.GetID("Air_of_Superiority")
Technobabble_ID = Skill.GetID("Technobabble")
Complicate_ID = Skill.GetID("Complicate")
Spirit_Light_ID = Skill.GetID("Spirit_Light")

Heroic_Refrain_ID = Skill.GetID("Heroic_Refrain")
Soul_Twisting_ID = Skill.GetID("Soul_Twisting")

POWER_DRAIN_NORMAL_THRESHOLD = 0.70
POWER_DRAIN_CRITICAL_THRESHOLD = 0.30
TECHNOBABBLE_MIN_HEALTH = 0.10
PI_TECHNOBABBLE_DELAY_MS = 650.0


class Psychic_Instability_Wastrels(BuildMgr):
    """PI shutdown Mesmer for the shared RoJway target packet."""

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="HR RoJ - Psychic Instability Cluster Control",
            required_primary=Profession.Mesmer,
            template_code="AAAAAAAAAAAAAAAA",
            required_skills=[
                Psychic_Instability_ID,
                Technobabble_ID,
                Complicate_ID,
            ],
            optional_skills=[
                Cry_of_Frustration_ID,
                Power_Drain_ID,
                Splinter_Weapon_ID,
                Binding_Chains_ID,
                Air_of_Superiority_ID,
                Spirit_Light_ID,
            ],
        )
        if match_only:
            return

        # This controller owns all supported slots so generic HeroAI cannot
        # peel an interrupt or offensive support cast away from team focus.
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skills: SkillsTemplate = SkillsTemplate(self)
        self._last_pi_cast_ms: float = 0.0
        self._last_pi_anchor: int = 0

    @staticmethod
    def _now_ms() -> float:
        return time.monotonic() * 1000.0

    @staticmethod
    def _log_rotation_event(event: str, **fields: object) -> None:
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug

            CombatDebug.log_event(str(event), **fields)
        except Exception:
            pass

    @staticmethod
    def _distance_to_player(agent_id: int) -> float:
        try:
            return float(Utils.Distance(Player.GetXY(), Agent.GetXY(int(agent_id))))
        except Exception:
            return 999999.0

    @staticmethod
    def _current_energy_absolute() -> float:
        try:
            player_id = int(Player.GetAgentID() or 0)
            return float(Agent.GetEnergy(player_id)) * float(Agent.GetMaxEnergy(player_id))
        except Exception:
            return 0.0

    @staticmethod
    def _current_energy_fraction() -> float:
        try:
            return float(Agent.GetEnergy(Player.GetAgentID()))
        except Exception:
            return 0.0

    @staticmethod
    def _skill_energy_cost(skill_id: int) -> float:
        try:
            player_id = int(Player.GetAgentID() or 0)
            return max(
                0.0,
                float(Routines.Checks.Skills.GetEnergyCostWithEffects(int(skill_id), player_id)),
            )
        except Exception:
            return 0.0

    def _get_native_pi_slot(self) -> int:
        try:
            return int(GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Psychic_Instability_ID) or 0)
        except Exception:
            return 0

    def _focus_packet(self, role: str) -> tuple[int, list[int]]:
        anchor = int(
            get_team_cluster_anchor(
                filter_range=Range.Spellcast.value,
                minimum_enemies=2,
                consumer_role=f"pi_{role}",
            )
            or 0
        )
        if anchor <= 0:
            return 0, []

        members = get_team_cluster_members(
            anchor,
            radius=Range.Adjacent.value,
            filter_range=Range.Spellcast.value,
        )
        members = [
            int(enemy_id)
            for enemy_id in members
            if int(enemy_id or 0) > 0 and Agent.IsValid(int(enemy_id)) and Agent.IsAlive(int(enemy_id))
        ]
        if anchor not in members and Agent.IsValid(anchor) and Agent.IsAlive(anchor):
            members.append(anchor)
        return anchor, sorted(set(members))

    def _target_still_in_focus(
        self,
        target_id: int,
        expected_anchor: int,
        *,
        require_casting_skill_id: int = 0,
    ) -> bool:
        if target_id <= 0 or expected_anchor <= 0:
            return False
        anchor, members = self._focus_packet("final_cast_check")
        if anchor != int(expected_anchor) or int(target_id) not in members:
            return False
        if require_casting_skill_id > 0:
            return target_still_casting_skill(int(target_id), int(require_casting_skill_id))
        return bool(Agent.IsValid(target_id) and Agent.IsAlive(target_id))

    def _target_still_scattered_cleanup_cast(
        self,
        target_id: int,
        casting_skill_id: int,
    ) -> bool:
        """Permit PI off the damage anchor only while no real packet exists."""
        if int(target_id or 0) <= 0 or int(casting_skill_id or 0) <= 0:
            return False
        anchor, members = self._focus_packet("scattered_final_cast_check")
        if anchor <= 0 or len(members) > 1:
            return False
        try:
            if not Agent.IsValid(int(target_id)) or not Agent.IsAlive(int(target_id)):
                return False
        except Exception:
            return False
        if self._distance_to_player(int(target_id)) > float(Range.Spellcast.value):
            return False
        return target_still_casting_skill(int(target_id), int(casting_skill_id))

    @staticmethod
    def _packet_near_count(target_id: int, members: list[int]) -> int:
        try:
            target_xy = Agent.GetXY(int(target_id))
            return sum(
                1
                for enemy_id in members
                if Utils.Distance(target_xy, Agent.GetXY(int(enemy_id))) <= float(Range.Adjacent.value)
            )
        except Exception:
            return 1

    @staticmethod
    def _casting_count_near(
        target_id: int,
        candidates: list[tuple[int, int]],
    ) -> int:
        try:
            target_xy = Agent.GetXY(int(target_id))
            return sum(
                1
                for enemy_id, _skill_id in candidates
                if Utils.Distance(target_xy, Agent.GetXY(int(enemy_id))) <= float(Range.Nearby.value)
            )
        except Exception:
            return 0

    @staticmethod
    def _health_fraction(agent_id: int) -> float:
        try:
            return float(Agent.GetHealth(int(agent_id)))
        except Exception:
            return 0.0

    @staticmethod
    def _is_boss(agent_id: int) -> bool:
        try:
            return bool(Agent.HasBossGlow(int(agent_id)))
        except Exception:
            return False

    def _pi_ready_for_opening(self) -> bool:
        slot = self._get_native_pi_slot()
        if not (1 <= slot <= 8):
            return False
        try:
            return bool(self.CanCastSkillSlot(slot))
        except Exception:
            return False

    @staticmethod
    def _is_spell_or_chant(skill_id: int) -> bool:
        if int(skill_id or 0) <= 0:
            return False
        try:
            flags = GLOBAL_CACHE.Skill.Flags
            # Spell subtypes are exposed separately by the native API.
            return bool(
                flags.IsSpell(skill_id)
                or flags.IsChant(skill_id)
                or flags.IsHex(skill_id)
                or flags.IsEnchantment(skill_id)
                or flags.IsWeaponSpell(skill_id)
                or flags.IsItemSpell(skill_id)
                or flags.IsWell(skill_id)
                or flags.IsWard(skill_id)
                or flags.IsGlyph(skill_id)
            )
        except Exception:
            return False

    def _casting_candidates(
        self,
        members: list[int],
        *,
        spell_or_chant_only: bool = False,
        include_dangerous: bool = True,
    ) -> list[tuple[int, int]]:
        candidates: list[tuple[int, int]] = []
        for enemy_id in members:
            casting_skill_id = int(get_casting_skill_id(int(enemy_id)) or 0)
            if casting_skill_id <= 0:
                continue
            if spell_or_chant_only and not self._is_spell_or_chant(casting_skill_id):
                continue
            if not include_dangerous and is_dangerous_cast(int(enemy_id)):
                continue
            candidates.append((int(enemy_id), casting_skill_id))

        candidates.sort(
            key=lambda item: (
                -int(is_dangerous_cast(int(item[0]))),
                -self._packet_near_count(int(item[0]), members),
                -int(is_support_or_caster(int(item[0]))),
                self._distance_to_player(int(item[0])),
                int(item[0]),
            )
        )
        return candidates

    def _claim_focus_dangerous_cast(
        self,
        *,
        anchor: int,
        members: list[int],
        interrupter_skill_id: int,
        spell_or_chant_only: bool = False,
    ) -> tuple[int, int, bool]:
        member_set = set(int(enemy_id) for enemy_id in members)

        def _validator(enemy_id: int, casting_skill_id: int) -> bool:
            if int(enemy_id) not in member_set:
                return False
            if spell_or_chant_only and not self._is_spell_or_chant(int(casting_skill_id)):
                return False
            return True

        target_id, casting_skill_id = claim_best_dangerous_cast(
            range_value=int(Range.Spellcast.value),
            interrupter_skill_id=int(interrupter_skill_id),
            validator=_validator,
        )
        target_id = int(target_id or 0)
        casting_skill_id = int(casting_skill_id or 0)
        if target_id <= 0 or casting_skill_id <= 0:
            return 0, 0, False
        if not self._target_still_in_focus(
            target_id,
            anchor,
            require_casting_skill_id=casting_skill_id,
        ):
            release_interrupt_claim(target_id, casting_skill_id, reason="pi_focus_changed")
            return 0, 0, False
        return target_id, casting_skill_id, True

    def _pick_interrupt_target(
        self,
        *,
        anchor: int,
        members: list[int],
        interrupter_skill_id: int,
        spell_or_chant_only: bool = False,
    ) -> tuple[int, int, bool]:
        target_id, casting_skill_id, claimed = self._claim_focus_dangerous_cast(
            anchor=anchor,
            members=members,
            interrupter_skill_id=interrupter_skill_id,
            spell_or_chant_only=spell_or_chant_only,
        )
        if target_id > 0:
            return target_id, casting_skill_id, claimed

        # Do not bypass another account's dangerous-cast claim.
        candidates = self._casting_candidates(
            members,
            spell_or_chant_only=spell_or_chant_only,
            include_dangerous=False,
        )
        if not candidates:
            return 0, 0, False
        target_id, casting_skill_id = candidates[0]
        return int(target_id), int(casting_skill_id), False

    def _pick_scattered_cleanup_pi_target(self, anchor: int) -> tuple[int, int, bool]:
        """Interrupt the best live cast when isolated enemies are spread out.

        Reserved dangerous casts keep the central ordering (resurrection,
        protection/healing, then lethal shutdown). If none is claimable, PI
        first takes any ordinary skill on the shared cleanup target and only
        then an ordinary cast from another isolated enemy.
        """

        def _scattered_validator(enemy_id: int, casting_skill_id: int) -> bool:
            return self._target_still_scattered_cleanup_cast(
                int(enemy_id),
                int(casting_skill_id),
            )

        target_id, casting_skill_id = claim_best_dangerous_cast(
            range_value=int(Range.Spellcast.value),
            interrupter_skill_id=int(Psychic_Instability_ID),
            validator=_scattered_validator,
        )
        target_id = int(target_id or 0)
        casting_skill_id = int(casting_skill_id or 0)
        if target_id > 0 and casting_skill_id > 0:
            if self._target_still_scattered_cleanup_cast(target_id, casting_skill_id):
                return target_id, casting_skill_id, True
            release_interrupt_claim(
                target_id,
                casting_skill_id,
                reason="pi_scattered_focus_changed",
            )

        try:
            enemy_ids = AgentArray.GetEnemyArray() or []
            enemy_ids = AgentArray.Filter.ByDistance(
                enemy_ids,
                Player.GetXY(),
                Range.Spellcast.value,
            )
        except Exception:
            enemy_ids = []

        ordinary_casts: list[tuple[tuple[int, int, float, int], int, int]] = []
        for enemy_id in enemy_ids:
            enemy_id = int(enemy_id or 0)
            casting_skill_id = int(get_casting_skill_id(enemy_id) or 0)
            if casting_skill_id <= 0:
                continue
            # A dangerous cast with no returned claim may already belong to
            # another account. Never bypass that reservation as an "ordinary"
            # cast on the fallback path.
            if is_dangerous_cast(enemy_id):
                continue
            try:
                if Agent.IsKnockedDown(enemy_id):
                    continue
            except Exception:
                pass
            ordinary_casts.append((
                (
                    0 if enemy_id == int(anchor) else 1,
                    -int(is_support_or_caster(enemy_id)),
                    self._distance_to_player(enemy_id),
                    enemy_id,
                ),
                enemy_id,
                casting_skill_id,
            ))

        if not ordinary_casts:
            return 0, 0, False
        ordinary_casts.sort(key=lambda item: item[0])
        _rank, target_id, casting_skill_id = ordinary_casts[0]
        if not self._target_still_scattered_cleanup_cast(target_id, casting_skill_id):
            return 0, 0, False
        return int(target_id), int(casting_skill_id), False

    def _cast_interrupt_slot(
        self,
        *,
        slot: int,
        expected_skill_id: int,
        target_id: int,
        casting_skill_id: int,
        anchor: int,
        claimed: bool,
        source: str,
        scattered_cleanup: bool = False,
    ):
        if not (1 <= int(slot) <= 8):
            if claimed:
                release_interrupt_claim(target_id, casting_skill_id, reason="invalid_skill_slot")
            return False
        try:
            visible_skill_id = int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(int(slot)) or 0)
        except Exception:
            visible_skill_id = 0
        if visible_skill_id != int(expected_skill_id):
            if claimed:
                release_interrupt_claim(target_id, casting_skill_id, reason="slot_skill_changed")
            return False
        if not self.CanCastSkillSlot(int(slot)):
            if claimed:
                release_interrupt_claim(target_id, casting_skill_id, reason="slot_not_castable")
            return False
        if not interrupt_is_feasible(int(target_id), int(expected_skill_id)):
            if claimed:
                release_interrupt_claim(target_id, casting_skill_id, reason="interrupt_not_feasible")
            return False
        def _final_target_usable() -> bool:
            if bool(scattered_cleanup):
                return self._target_still_scattered_cleanup_cast(
                    int(target_id),
                    int(casting_skill_id),
                )
            return self._target_still_in_focus(
                int(target_id),
                int(anchor),
                require_casting_skill_id=int(casting_skill_id),
            )

        if not _final_target_usable():
            if claimed:
                release_interrupt_claim(target_id, casting_skill_id, reason="final_focus_changed")
            return False

        previous_enemy_target = int(Player.GetTargetID() or 0)
        did_cast = yield from self.CastSkillSlot(
            int(slot),
            extra_condition=_final_target_usable,
            log=False,
            aftercast_delay=180,
            target_agent_id=int(target_id),
        )
        if not did_cast:
            if claimed:
                release_interrupt_claim(target_id, casting_skill_id, reason="cast_command_rejected")
            return False

        try:
            yield from self.RestoreEnemyTarget(previous_enemy_target)
        except Exception:
            pass
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug

            CombatDebug.register_interrupt_fired(int(target_id), int(casting_skill_id), int(expected_skill_id))
        except Exception:
            pass
        self._log_rotation_event(
            "PI_CONTROL_INTERRUPT_CAST",
            target_id=int(target_id),
            enemy_skill_id=int(casting_skill_id),
            our_skill_id=int(expected_skill_id),
            source=str(source),
            team_anchor=int(anchor),
            claimed=bool(claimed),
            scattered_cleanup=bool(scattered_cleanup),
            policy=(
                "pi_scattered_cast_priority_without_damage_focus_change"
                if scattered_cleanup
                else "pi_first_shared_packet_control"
            ),
        )
        if int(expected_skill_id) == int(Psychic_Instability_ID):
            self._last_pi_cast_ms = self._now_ms()
            self._last_pi_anchor = int(anchor)
        return True

    def _cast_pi_from_slot(self, slot: int, *, source: str):
        anchor, members = self._focus_packet(f"{source}_target")
        if anchor <= 0 or not members:
            return False
        scattered_cleanup = bool(len(members) <= 1)
        if scattered_cleanup:
            target_id, casting_skill_id, claimed = self._pick_scattered_cleanup_pi_target(
                anchor,
            )
        else:
            target_id, casting_skill_id, claimed = self._pick_interrupt_target(
                anchor=anchor,
                members=members,
                interrupter_skill_id=Psychic_Instability_ID,
            )
        if target_id <= 0:
            return False
        return (
            yield from self._cast_interrupt_slot(
                slot=int(slot),
                expected_skill_id=Psychic_Instability_ID,
                target_id=target_id,
                casting_skill_id=casting_skill_id,
                anchor=anchor,
                claimed=claimed,
                source=(f"{source}_scattered_cleanup" if scattered_cleanup else source),
                scattered_cleanup=scattered_cleanup,
            )
        )

    def _optional_energy_reserve(self) -> float:
        if self._pi_ready_for_opening():
            return self._skill_energy_cost(Psychic_Instability_ID)
        return 0.0

    def _can_spend_optional_energy(self, skill_id: int) -> bool:
        return bool(
            self._current_energy_absolute() + 0.01
            >= self._skill_energy_cost(skill_id) + self._optional_energy_reserve()
        )

    def _cast_power_drain(self, *, critical_only: bool = False):
        if not self.IsSkillEquipped(Power_Drain_ID):
            return False
        if not self.CanCastSkillID(Power_Drain_ID):
            return False
        threshold = POWER_DRAIN_CRITICAL_THRESHOLD if critical_only else POWER_DRAIN_NORMAL_THRESHOLD
        if self._current_energy_fraction() > threshold:
            return False

        anchor, members = self._focus_packet("power_drain")
        if anchor <= 0:
            return False
        target_id, casting_skill_id, claimed = self._pick_interrupt_target(
            anchor=anchor,
            members=members,
            interrupter_skill_id=Power_Drain_ID,
            spell_or_chant_only=True,
        )
        if target_id <= 0:
            return False
        slot = int(GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Power_Drain_ID) or 0)
        return (
            yield from self._cast_interrupt_slot(
                slot=slot,
                expected_skill_id=Power_Drain_ID,
                target_id=target_id,
                casting_skill_id=casting_skill_id,
                anchor=anchor,
                claimed=claimed,
                source="critical_energy" if critical_only else "energy_supply",
            )
        )

    def _cast_cry_of_frustration(self, *, multi_only: bool):
        if not self.IsSkillEquipped(Cry_of_Frustration_ID):
            return False
        if not self.CanCastSkillID(Cry_of_Frustration_ID):
            return False

        anchor, members = self._focus_packet("cry")
        if anchor <= 0:
            return False
        all_candidates = self._casting_candidates(members)
        if not all_candidates:
            return False

        target_id, casting_skill_id, claimed = self._claim_focus_dangerous_cast(
            anchor=anchor,
            members=members,
            interrupter_skill_id=Cry_of_Frustration_ID,
        )
        casting_count = 0
        if target_id > 0:
            casting_count = self._casting_count_near(int(target_id), all_candidates)
            if multi_only and casting_count < 2:
                release_interrupt_claim(
                    int(target_id),
                    int(casting_skill_id),
                    reason="reserve_single_danger_for_complicate",
                )
                target_id = 0
                casting_skill_id = 0
                claimed = False

        if target_id <= 0:
            # Never bypass another account's dangerous-cast claim. Ordinary
            # Cry is reserved for two or more simultaneous casts in its area.
            non_dangerous = self._casting_candidates(members, include_dangerous=False)
            ranked = sorted(
                non_dangerous,
                key=lambda item: (
                    -self._casting_count_near(int(item[0]), non_dangerous),
                    -self._packet_near_count(int(item[0]), members),
                    int(item[0]),
                ),
            )
            if not ranked:
                return False
            target_id, casting_skill_id = ranked[0]
            casting_count = self._casting_count_near(int(target_id), non_dangerous)
            if casting_count < 2:
                return False
            claimed = False

        if not self._can_spend_optional_energy(Cry_of_Frustration_ID):
            if claimed:
                release_interrupt_claim(
                    int(target_id),
                    int(casting_skill_id),
                    reason="pi_energy_reserved",
                )
            return False
        slot = int(GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Cry_of_Frustration_ID) or 0)
        return (
            yield from self._cast_interrupt_slot(
                slot=slot,
                expected_skill_id=Cry_of_Frustration_ID,
                target_id=int(target_id),
                casting_skill_id=int(casting_skill_id),
                anchor=anchor,
                claimed=bool(claimed),
                source=("multi_cast_after_pi" if casting_count >= 2 else "dangerous_single_fallback"),
            )
        )

    def _cast_complicate(self):
        if not self.IsSkillEquipped(Complicate_ID):
            return False
        if not self.CanCastSkillID(Complicate_ID):
            return False

        anchor, members = self._focus_packet("complicate")
        if anchor <= 0:
            return False
        target_id, casting_skill_id, claimed = self._claim_focus_dangerous_cast(
            anchor=anchor,
            members=members,
            interrupter_skill_id=Complicate_ID,
        )
        source = "dangerous_skill_area_disable"
        if target_id <= 0:
            # PI has already received the first chance at every activation. On
            # its recharge, Complicate may also disable an ordinary skill from
            # a real caster/support target. Requiring packet footprint avoids
            # spending it on random melee filler merely because something is
            # animating.
            if self._pi_ready_for_opening():
                return False
            ordinary_candidates = [
                (int(enemy_id), int(skill_id))
                for enemy_id, skill_id in self._casting_candidates(
                    members,
                    include_dangerous=False,
                )
                if is_support_or_caster(int(enemy_id))
                and (
                    len(members) <= 1
                    or self._packet_near_count(int(enemy_id), members) >= 2
                )
            ]
            if not ordinary_candidates:
                return False
            target_id, casting_skill_id = ordinary_candidates[0]
            claimed = False
            source = "ordinary_support_packet_disable"
        if not self._can_spend_optional_energy(Complicate_ID):
            if claimed:
                release_interrupt_claim(
                    int(target_id),
                    int(casting_skill_id),
                    reason="pi_energy_reserved",
                )
            return False

        slot = int(GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Complicate_ID) or 0)
        return (
            yield from self._cast_interrupt_slot(
                slot=slot,
                expected_skill_id=Complicate_ID,
                target_id=int(target_id),
                casting_skill_id=int(casting_skill_id),
                anchor=anchor,
                claimed=bool(claimed),
                source=str(source),
            )
        )

    def _cast_technobabble(self):
        if not self.IsSkillEquipped(Technobabble_ID):
            return False
        if not self.CanCastSkillID(Technobabble_ID):
            return False
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False
        if self._pi_ready_for_opening():
            # Keep PI's first-refusal on an enemy that is already activating a
            # skill, but do not leave Technobabble dormant just because PI is
            # ready.  If the packet is not currently casting, Technobabble may
            # pre-emptively Daze the caster cluster; PI remains ready for the
            # first real activation after the one-second Technobabble cast.
            try:
                anchor_probe, members_probe = self._focus_packet("technobabble_precheck")
                active_casts = sum(
                    1 for enemy_id in members_probe
                    if int(get_casting_skill_id(int(enemy_id)) or 0) > 0
                )
            except Exception:
                active_casts = 1
            if active_casts > 0:
                return False
        if not self._can_spend_optional_energy(Technobabble_ID):
            return False

        anchor, members = self._focus_packet("technobabble")
        if anchor <= 0 or not members:
            return False

        elapsed_since_pi = self._now_ms() - float(self._last_pi_cast_ms or 0.0)
        if int(anchor) == int(self._last_pi_anchor) and 0.0 <= elapsed_since_pi < PI_TECHNOBABBLE_DELAY_MS:
            # Let most of PI's knockdown elapse before the one-second cast so
            # Dazed remains active when the packet stands up again.
            return False

        ranked: list[tuple[int, int, int, int, int, float, float, int]] = []
        target_metrics: dict[int, tuple[int, int, int, int]] = {}
        for candidate_id in members:
            candidate_id = int(candidate_id)
            if self._is_boss(candidate_id):
                continue
            health = self._health_fraction(candidate_id)
            if health <= TECHNOBABBLE_MIN_HEALTH:
                continue
            try:
                candidate_xy = Agent.GetXY(candidate_id)
                affected = [
                    int(enemy_id)
                    for enemy_id in members
                    if Utils.Distance(candidate_xy, Agent.GetXY(int(enemy_id))) <= float(Range.Adjacent.value)
                ]
            except Exception:
                affected = [candidate_id]

            caster_count = sum(1 for enemy_id in affected if is_support_or_caster(enemy_id))
            casting_count = sum(1 for enemy_id in affected if int(get_casting_skill_id(enemy_id) or 0) > 0)
            dangerous_count = sum(1 for enemy_id in affected if is_dangerous_cast(enemy_id))

            if len(members) <= 1:
                if dangerous_count <= 0 and not is_support_or_caster(candidate_id):
                    continue
            elif caster_count < 1 and casting_count < 2 and dangerous_count <= 0:
                continue

            affected_count = len(affected)
            target_metrics[candidate_id] = (
                affected_count,
                caster_count,
                casting_count,
                dangerous_count,
            )
            ranked.append(
                (
                    -dangerous_count,
                    -casting_count,
                    -caster_count,
                    -affected_count,
                    -int(is_support_or_caster(candidate_id)),
                    -health,
                    self._distance_to_player(candidate_id),
                    candidate_id,
                )
            )

        if not ranked:
            return False
        ranked.sort()
        target_id = int(ranked[0][7])
        affected_count, caster_count, casting_count, dangerous_count = target_metrics[target_id]

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Technobabble_ID,
            target_agent_id=target_id,
            extra_condition=lambda: (
                self._target_still_in_focus(target_id, anchor)
                and not self._is_boss(target_id)
                and self._health_fraction(target_id) > TECHNOBABBLE_MIN_HEALTH
            ),
            log=False,
            aftercast_delay=180,
        )
        if did_cast:
            self._log_rotation_event(
                "PI_TECHNOBABBLE_CAST",
                target_id=int(target_id),
                team_anchor=int(anchor),
                packet_size=len(members),
                affected_count=int(affected_count),
                caster_count=int(caster_count),
                casting_count=int(casting_count),
                dangerous_count=int(dangerous_count),
                policy="after_pi_central_non_boss_daze_one_caster_minimum",
            )
            return True
        return False

    def _party_and_nearby_ally_ids(self) -> list[int]:
        ally_ids: set[int] = set()
        try:
            for member in Party.GetPlayers() or []:
                login_number = int(getattr(member, "login_number", 0) or 0)
                agent_id = int(Party.Players.GetAgentIDByLoginNumber(login_number) or 0)
                if agent_id > 0:
                    ally_ids.add(agent_id)
        except Exception:
            pass
        try:
            for agent_id in GetAllAlliesArray(Range.Spellcast.value) or []:
                agent_id = int(agent_id or 0)
                if agent_id > 0:
                    ally_ids.add(agent_id)
        except Exception:
            pass
        return sorted(ally_ids)

    @staticmethod
    def _shared_skill_ids_by_agent() -> dict[int, set[int]]:
        result: dict[int, set[int]] = {}
        try:
            for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
                agent_data = getattr(account, "AgentData", None)
                agent_id = int(getattr(agent_data, "AgentID", 0) or 0)
                if agent_id <= 0:
                    continue
                skillbar = getattr(agent_data, "Skillbar", None)
                result[agent_id] = {
                    int(getattr(skill, "Id", 0) or 0)
                    for skill in getattr(skillbar, "Skills", ()) or ()
                    if int(getattr(skill, "Id", 0) or 0) > 0
                }
        except Exception:
            pass
        return result

    def _get_hr_and_st_agent_ids(self) -> tuple[int, int]:
        shared_skills = self._shared_skill_ids_by_agent()
        try:
            paragon_id = int(getattr(Profession.Paragon, "value", Profession.Paragon))
            ritualist_id = int(getattr(Profession.Ritualist, "value", Profession.Ritualist))
        except Exception:
            return 0, 0

        hr_candidates: list[tuple[int, float, int]] = []
        st_candidates: list[tuple[int, float, int]] = []
        for agent_id in self._party_and_nearby_ally_ids():
            if not Agent.IsValid(agent_id) or not Agent.IsAlive(agent_id):
                continue
            try:
                primary, _secondary = Agent.GetProfessions(agent_id)
                primary_id = int(getattr(primary, "value", primary) or 0)
            except Exception:
                continue
            skill_ids = shared_skills.get(agent_id, set())
            if primary_id == paragon_id:
                hr_candidates.append(
                    (
                        0 if Heroic_Refrain_ID in skill_ids else 1,
                        self._distance_to_player(agent_id),
                        int(agent_id),
                    )
                )
            elif primary_id == ritualist_id:
                has_st_effect = False
                try:
                    has_st_effect = bool(Routines.Checks.Agents.HasEffect(int(agent_id), int(Soul_Twisting_ID)))
                except Exception:
                    pass
                st_candidates.append(
                    (
                        0 if Soul_Twisting_ID in skill_ids or has_st_effect else 1,
                        self._distance_to_player(agent_id),
                        int(agent_id),
                    )
                )

        hr_candidates.sort()
        st_candidates.sort()
        hr_id = int(hr_candidates[0][2]) if hr_candidates else 0
        st_id = int(st_candidates[0][2]) if st_candidates else 0
        return hr_id, st_id

    @staticmethod
    def _has_weapon_spell(agent_id: int) -> bool:
        try:
            return bool(Agent.IsWeaponSpelled(int(agent_id)))
        except Exception:
            return False

    def _cast_splinter_on_hr_then_st(self):
        if not self.IsSkillEquipped(Splinter_Weapon_ID):
            return False
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False
        if not self._can_spend_optional_energy(Splinter_Weapon_ID):
            return False

        slot = int(GLOBAL_CACHE.SkillBar.GetSlotBySkillID(Splinter_Weapon_ID) or 0)
        if not (1 <= slot <= 8):
            return False
        try:
            if not self.IsSharedSkillToggleEnabled(slot):
                return False
        except Exception:
            pass
        if not Routines.Checks.Skills.IsSkillSlotReady(slot):
            return False
        if not Routines.Checks.Skills.HasEnoughEnergy(Player.GetAgentID(), Splinter_Weapon_ID):
            return False

        hr_id, st_id = self._get_hr_and_st_agent_ids()
        target_id = 0
        target_role = ""
        if hr_id > 0 and not self._has_weapon_spell(hr_id):
            target_id = hr_id
            target_role = "hr_player"
        elif st_id > 0 and not self._has_weapon_spell(st_id):
            target_id = st_id
            target_role = "soul_twisting"
        if target_id <= 0:
            return False
        if self._distance_to_player(target_id) > float(Range.Spellcast.value):
            return False

        # Direct slot use avoids HeroAI's incorrect AllyMartial weapon gate.
        previous_enemy_target = int(Player.GetTargetID() or 0)
        try:
            GLOBAL_CACHE.SkillBar.UseSkill(int(slot), target_agent_id=int(target_id), aftercast_delay=180)
            self._mark_local_cast_pending(180)
            self.SetTickSuccess()
        except Exception:
            return False

        try:
            yield from self.RestoreEnemyTarget(previous_enemy_target)
        except Exception:
            pass
        self._log_rotation_event(
            "PI_SPLINTER_CAST",
            target_id=int(target_id),
            target_role=str(target_role),
            hr_id=int(hr_id),
            st_id=int(st_id),
            policy="hr_first_then_st_support_window",
        )
        return True

    def _binding_chains_target_still_valid(self, expected_anchor_id: int) -> bool:
        anchor, members = self._focus_packet("binding_chains_final_check")
        return bool(
            int(anchor) == int(expected_anchor_id)
            and len(members) >= 2
            and Agent.IsValid(int(anchor))
            and Agent.IsAlive(int(anchor))
            and not packet_has_binding_chains(members)
        )

    def _cast_binding_chains_on_focus(self):
        """Fallback snare for the ST while preserving PI/interrupt priority."""
        if not self.IsSkillEquipped(Binding_Chains_ID):
            return False
        if not self.IsInAggro() or not self.CanCastSkillID(Binding_Chains_ID):
            return False
        if not self._can_spend_optional_energy(Binding_Chains_ID):
            return False

        anchor, members = self._focus_packet("binding_chains")
        if anchor <= 0 or len(members) < 2:
            return False
        if not any(self._health_fraction(enemy_id) > 0.10 for enemy_id in members):
            return False
        reservation = reserve_binding_chains(
            anchor_id=int(anchor),
            member_ids=members,
            role="pi",
        )
        if reservation is None:
            return False

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Binding_Chains_ID,
            target_agent_id=int(anchor),
            extra_condition=lambda: self._binding_chains_target_still_valid(int(anchor)),
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            register_binding_chains_fired(
                reservation,
                source="pi_fallback_after_control",
            )
            self._log_rotation_event(
                "PI_BINDING_CHAINS_ROJ_PACKET",
                target_id=int(anchor),
                team_anchor=int(anchor),
                packet_size=len(members),
                packet_key=int(reservation.packet_key),
                policy="st_primary_pi_delayed_fallback_after_all_control",
            )
            return True
        release_binding_chains_reservation(
            reservation,
            reason="pi_cast_command_rejected_or_focus_changed",
        )
        return False

    def _cast_spirit_light(self, *, health_threshold: float):
        if not self.IsSkillEquipped(Spirit_Light_ID):
            return False
        if not self.CanCastSkillID(Spirit_Light_ID):
            return False
        did_cast = yield from self.skills.Ritualist.RestorationMagic.Spirit_Light(
            health_threshold=float(health_threshold),
        )
        if did_cast:
            self._log_rotation_event(
                "PI_SPIRIT_LIGHT_HEAL",
                threshold=round(float(health_threshold), 3),
                policy="emergency_30_then_support_68",
            )
            return True
        return False

    def _cast_air_of_superiority(self):
        if not self.IsSkillEquipped(Air_of_Superiority_ID):
            return False
        if not (self.IsInAggro() or self.IsCloseToAggro()):
            return False
        if not self._can_spend_optional_energy(Air_of_Superiority_ID):
            return False
        did_cast = yield from self.skills.Any.PvE.Air_of_Superiority()
        if did_cast:
            self._log_rotation_event(
                "PI_AIR_OF_SUPERIORITY_CAST",
                policy="supported_recharge_filler_only",
            )
            return True
        return False

    def _run_local_skill_logic(self):
        refresh_aoe_danger_zones()
        if avoid_active_aoe_if_needed(role="psychic_instability", allow_actions_at_safe_hold=True):
            return True

        close_pressure = bool(self.IsInAggro() or self.IsCloseToAggro())
        if not Routines.Checks.Skills.CanCast():
            return False
        if not close_pressure:
            return False

        # PI remains the control opener, except for a genuinely critical ally.
        # Spirit Light is intentionally checked with a low emergency threshold
        # before PI so the hybrid controller can still save a collapsing target.
        if (yield from self._cast_spirit_light(health_threshold=0.30)):
            return True

        native_pi_cost = self._skill_energy_cost(Psychic_Instability_ID)
        if (
            self._current_energy_fraction() <= POWER_DRAIN_CRITICAL_THRESHOLD
            and self._current_energy_absolute() + 0.01 < native_pi_cost
            and (yield from self._cast_power_drain(critical_only=True))
        ):
            return True

        # PI owns the first valid enemy activation in the authoritative packet.
        native_slot = self._get_native_pi_slot()
        if (
            1 <= native_slot <= 8
            and Routines.Checks.Skills.IsSkillSlotReady(native_slot)
            and (yield from self._cast_pi_from_slot(native_slot, source="opener"))
        ):
            return True

        # Once PI has had first refusal, the hybrid support role gets a normal
        # healing window before optional secondary shutdown.
        if (yield from self._cast_spirit_light(health_threshold=0.68)):
            return True

        # Cry owns real simultaneous casts. Single casts remain available to
        # the energy-supply and area-disable checks below.
        if (yield from self._cast_cry_of_frustration(multi_only=True)):
            return True

        # Power Drain is checked before single-target shutdown so it can
        # actually service low energy. PI and a real multi-Cry have already had
        # first refusal, so this does not break the control opener.
        if (yield from self._cast_power_drain(critical_only=False)):
            return True

        if (yield from self._cast_complicate()):
            return True

        # If Complicate is unavailable, Cry may still save a dangerous single
        # cast instead of waiting for an artificial multi-cast condition.
        if (yield from self._cast_cry_of_frustration(multi_only=False)):
            return True

        if (yield from self._cast_technobabble()):
            return True

        # Supported skills only run in a free main-rotation window.
        if (yield from self._cast_binding_chains_on_focus()):
            return True
        if (yield from self._cast_splinter_on_hr_then_st()):
            return True
        if (yield from self._cast_air_of_superiority()):
            return True

        return False
