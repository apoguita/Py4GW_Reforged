from __future__ import annotations

from Py4GWCoreLib import Agent
from Py4GWCoreLib import BuildMgr
from Py4GWCoreLib import Party
from Py4GWCoreLib import Player
from Py4GWCoreLib import Profession
from Py4GWCoreLib import Routines
from Py4GWCoreLib import Skill
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build


INVOKE_LIGHTNING_ID = Skill.GetID("Invoke_Lightning")
INTENSITY_ID = Skill.GetID("Intensity")
AIR_ATTUNEMENT_ID = Skill.GetID("Air_Attunement")
ELEMENTAL_LORD_KURZICK_ID = Skill.GetID("Elemental_Lord_kurzick")
ELEMENTAL_LORD_LUXON_ID = Skill.GetID("Elemental_Lord_luxon")
LIGHTNING_STRIKE_ID = Skill.GetID("Lightning_Strike")
SOUL_IGNITION_ID = Skill.GetID("Soul_Ignition") or 3446


class Invoke_Lightning_Air(BuildMgr):
    """Shared visible/headless controller for Invoke Lightning air bars."""

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Invoke Lightning Air",
            required_primary=Profession.Elementalist,
            required_skills=[INVOKE_LIGHTNING_ID],
            optional_skills=[
                INTENSITY_ID,
                AIR_ATTUNEMENT_ID,
                ELEMENTAL_LORD_KURZICK_ID,
                ELEMENTAL_LORD_LUXON_ID,
                SOUL_IGNITION_ID,
            ],
        )
        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
        self.SetOOCFn(self._run_ooc)
        self.SetCombatFn(self._run_combat)

    def _maintain_self_enchantment(self, skill_id: int):
        if not self.IsSkillEquipped(skill_id):
            return False
        player_id = Player.GetAgentID()
        missing = lambda: not Routines.Checks.Agents.HasEffect(player_id, skill_id)
        if not missing():
            return False
        return (yield from self.CastSkillID(
            skill_id,
            extra_condition=missing,
            log=False,
            aftercast_delay=250,
        ))

    def _run_upkeep(self):
        if (yield from self._maintain_self_enchantment(AIR_ATTUNEMENT_ID)):
            return True

        for elemental_lord_id in (
            ELEMENTAL_LORD_KURZICK_ID,
            ELEMENTAL_LORD_LUXON_ID,
        ):
            if elemental_lord_id and (
                yield from self._maintain_self_enchantment(elemental_lord_id)
            ):
                return True

        return False

    def _pick_established_damage_target(self) -> int:
        """Use the fight HeroAI already selected; never acquire one for an AoE."""
        for target_id in (
            int(Party.GetPartyTarget() or 0),
            int(Player.GetTargetID() or 0),
        ):
            if not self._is_valid_enemy_target_candidate(target_id):
                continue
            _, allegiance = Agent.GetAllegiance(target_id)
            if allegiance == "Enemy":
                return target_id
        return 0

    def _can_afford_pair(self, payload_skill_id: int) -> bool:
        player_id = Player.GetAgentID()
        current_energy = Agent.GetEnergy(player_id) * Agent.GetMaxEnergy(player_id)
        intensity_cost = Routines.Checks.Skills.GetEnergyCostWithEffects(
            INTENSITY_ID,
            player_id,
        )
        payload_cost = Routines.Checks.Skills.GetEnergyCostWithEffects(
            payload_skill_id,
            player_id,
        )
        return current_energy >= intensity_cost + payload_cost

    def _pick_intensity_payload(
        self,
        *,
        reserve_intensity_energy: bool,
    ) -> tuple[int, int]:
        if self.CanCastSkillID(INVOKE_LIGHTNING_ID):
            target_id = self._pick_established_damage_target()
            if target_id and (
                not reserve_intensity_energy
                or self._can_afford_pair(INVOKE_LIGHTNING_ID)
            ):
                return INVOKE_LIGHTNING_ID, target_id

        if self.IsSkillEquipped(LIGHTNING_STRIKE_ID) and self.CanCastSkillID(
            LIGHTNING_STRIKE_ID
        ):
            target_id = self._pick_established_damage_target()
            if target_id and (
                not reserve_intensity_energy
                or self._can_afford_pair(LIGHTNING_STRIKE_ID)
            ):
                return LIGHTNING_STRIKE_ID, target_id

        return 0, 0

    def _cast_intensity_payload(self):
        player_id = Player.GetAgentID()
        if not Routines.Checks.Agents.HasEffect(player_id, INTENSITY_ID):
            return False

        payload_skill_id, target_id = self._pick_intensity_payload(
            reserve_intensity_energy=False,
        )
        if not payload_skill_id or not target_id:
            return False
        return (yield from self.CastSkillIDAndRestoreTarget(
            payload_skill_id,
            target_id,
            log=False,
            aftercast_delay=250,
        ))

    def _cast_intensity_for_ready_payload(self):
        if not self.IsSkillEquipped(INTENSITY_ID):
            return False
        if not self.CanCastSkillID(INTENSITY_ID):
            return False
        if Routines.Checks.Agents.HasEffect(Player.GetAgentID(), INTENSITY_ID):
            return False

        payload_skill_id, _ = self._pick_intensity_payload(
            reserve_intensity_energy=True,
        )
        if not payload_skill_id:
            return False
        return (yield from self.CastSkillID(
            INTENSITY_ID,
            log=False,
            aftercast_delay=250,
        ))

    def _cast_invoke(self):
        if not self.CanCastSkillID(INVOKE_LIGHTNING_ID):
            return False
        target_id = self._pick_established_damage_target()
        if not target_id:
            return False
        return (yield from self.CastSkillIDAndRestoreTarget(
            INVOKE_LIGHTNING_ID,
            target_id,
            log=False,
            aftercast_delay=250,
        ))

    def _run_ooc(self):
        if not Routines.Checks.Skills.CanCast():
            return False
        return (yield from self._run_upkeep())

    def _run_combat(self):
        if not Routines.Checks.Skills.CanCast():
            return False

        if (yield from self._run_upkeep()):
            return True

        if not self.IsInAggro():
            return False

        if (yield from self._cast_intensity_payload()):
            return True

        if (yield from self._cast_intensity_for_ready_payload()):
            return True

        if (yield from self._cast_invoke()):
            return True

        # Generic HeroAI owns every remaining bar skill and normal combat.
        return False
