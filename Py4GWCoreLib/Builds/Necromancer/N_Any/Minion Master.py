from __future__ import annotations

import math

from Py4GWCoreLib import Agent, AgentArray, BuildMgr, Profession, Range, Routines
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build
from Py4GWCoreLib.Builds.Skills import SkillsTemplate
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.enums_src.GameData_enums import Attribute


MASOCHISM_ID = Skill.GetID("Masochism")
SIGNET_OF_LOST_SOULS_ID = Skill.GetID("Signet_of_Lost_Souls")
ANIMATE_BONE_FIEND_ID = Skill.GetID("Animate_Bone_Fiend")
ANIMATE_BONE_HORROR_ID = Skill.GetID("Animate_Bone_Horror")
ANIMATE_BONE_MINIONS_ID = Skill.GetID("Animate_Bone_Minions")
ANIMATE_FLESH_GOLEM_ID = Skill.GetID("Animate_Flesh_Golem")
ANIMATE_SHAMBLING_HORROR_ID = Skill.GetID("Animate_Shambling_Horror")
ANIMATE_VAMPIRIC_HORROR_ID = Skill.GetID("Animate_Vampiric_Horror")
AURA_OF_THE_LICH_ID = Skill.GetID("Aura_of_the_Lich")

GUARANTEED_MINION_SKILL_IDS = [
    ANIMATE_BONE_FIEND_ID,
    ANIMATE_BONE_HORROR_ID,
    ANIMATE_BONE_MINIONS_ID,
    ANIMATE_FLESH_GOLEM_ID,
    ANIMATE_SHAMBLING_HORROR_ID,
    ANIMATE_VAMPIRIC_HORROR_ID,
    AURA_OF_THE_LICH_ID,
]

ORDINARY_ANIMATE_SKILLS = [
    (ANIMATE_BONE_FIEND_ID, "Animate_Bone_Fiend"),
    (ANIMATE_BONE_HORROR_ID, "Animate_Bone_Horror"),
    (ANIMATE_BONE_MINIONS_ID, "Animate_Bone_Minions"),
    (ANIMATE_SHAMBLING_HORROR_ID, "Animate_Shambling_Horror"),
    (ANIMATE_VAMPIRIC_HORROR_ID, "Animate_Vampiric_Horror"),
]

FLESH_GOLEM_MODEL_ID = 2795
MINION_MASTER_MATCH_PRIORITY = 100


def minion_cap_for_death_magic(death_magic_rank: int) -> int:
    """Return the PvE controlled-minion cap for a Death Magic rank."""
    return 2 + max(0, int(death_magic_rank)) // 2


def controlled_minion_count(
    controlled_minions: list[tuple[int, int]],
    owner_agent_id: int,
) -> int:
    """Read one master's repeated world count without multiplying records."""
    return max((
        max(0, int(minion_count))
        for agent_id, minion_count in controlled_minions
        if int(agent_id) == int(owner_agent_id)
    ), default=0)


class Minion_Master(BuildMgr):
    """Own the summon-order contract for any bar with a guaranteed minion skill."""

    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Minion Master",
            required_primary=Profession(0),
            required_secondary=Profession(0),
            template_code="",
            required_skills=GUARANTEED_MINION_SKILL_IDS,
            optional_skills=[MASOCHISM_ID],
        )
        # Any immediate, guaranteed minion creator identifies the build family.
        self.minimum_required_match = 1
        self._summon_energy_reserve = 0

        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
        self.SetSkillCastingFn(self._run_minion_master)
        self.skillbook = SkillsTemplate(self)

    def ScoreMatch(
        self,
        current_primary=None,
        current_secondary=None,
        current_skills: list[int] | None = None,
    ) -> int:
        """Make any guaranteed minion skill authoritative regardless of profession.

        The shared registry otherwise compares only raw skill-hit counts.  A
        Minion Master bar with one animate skill must not lose ownership merely
        because several utility skills happen to resemble another build.
        """
        score = super().ScoreMatch(
            current_primary=current_primary,
            current_secondary=current_secondary,
            current_skills=current_skills,
        )
        if score < 0:
            return score
        return MINION_MASTER_MATCH_PRIORITY + score

    def GetBlockedSkills(self) -> list[int]:
        blocked_skills = super().GetBlockedSkills()
        reserve = max(0, int(self._summon_energy_reserve))
        if reserve <= 0:
            return blocked_skills

        player_agent_id = Player.GetAgentID()
        current_energy = (
            Agent.GetEnergy(player_agent_id) * Agent.GetMaxEnergy(player_agent_id)
        )
        spendable_energy = max(0.0, current_energy - reserve)
        for skill_id in self._get_current_skills():
            energy_cost = Routines.Checks.Skills.GetEnergyCostWithEffects(
                skill_id,
                player_agent_id,
            )
            if energy_cost <= spendable_energy or skill_id in blocked_skills:
                continue
            blocked_skills.append(skill_id)
        return blocked_skills

    def _death_magic_rank(self) -> int:
        attributes = Agent.GetAttributes(Player.GetAgentID())
        death_magic = next(
            (
                attribute
                for attribute in attributes
                if int(getattr(attribute, "attribute_id", -1))
                == int(Attribute.DeathMagic)
            ),
            None,
        )
        return int(getattr(death_magic, "level", 0) or 0)

    def _has_owned_flesh_golem(self) -> bool:
        player_agent_id = Player.GetAgentID()
        for minion_agent_id in AgentArray.GetMinionArray() or []:
            if not Agent.IsAlive(minion_agent_id):
                continue
            if Agent.GetOwnerID(minion_agent_id) != player_agent_id:
                continue
            if Agent.GetPlayerNumber(minion_agent_id) == FLESH_GOLEM_MODEL_ID:
                return True
        return False

    def _equipped_corpse_animation_ids(self) -> list[int]:
        corpse_skill_ids = [
            ANIMATE_FLESH_GOLEM_ID,
            *(skill_id for skill_id, _ in ORDINARY_ANIMATE_SKILLS),
        ]
        return [
            skill_id
            for skill_id in corpse_skill_ids
            if self.IsSkillEquipped(skill_id)
        ]

    def _needs_guaranteed_summon(
        self,
        *,
        has_corpse: bool,
        minion_count: int,
        desired_cap: int,
    ) -> bool:
        if minion_count >= desired_cap:
            return False
        if has_corpse and self._equipped_corpse_animation_ids():
            return True
        return (
            self.IsSkillEquipped(AURA_OF_THE_LICH_ID)
            and Routines.Checks.Skills.IsSkillIDReady(AURA_OF_THE_LICH_ID)
        )

    def _summon_reserve_cost(self, has_corpse: bool) -> int:
        player_agent_id = Player.GetAgentID()
        candidate_ids = self._equipped_corpse_animation_ids() if has_corpse else []
        if (
            self.IsSkillEquipped(AURA_OF_THE_LICH_ID)
            and Routines.Checks.Skills.IsSkillIDReady(AURA_OF_THE_LICH_ID)
        ):
            candidate_ids.append(AURA_OF_THE_LICH_ID)
        costs = [
            Routines.Checks.Skills.GetEnergyCostWithEffects(
                skill_id,
                player_agent_id,
            )
            for skill_id in candidate_ids
        ]
        return int(math.ceil(min(costs))) if costs else 0

    def _run_minion_master(self):
        self._summon_energy_reserve = 0
        if not Routines.Checks.Skills.CanCast():
            return False

        exploitable_corpses = list(
            Routines.Agents.GetExploitableCorpses(Range.Spellcast.value) or []
        )
        has_corpse = bool(exploitable_corpses)
        controlled_minions = list(Player.GetControlledMinions() or [])
        minion_count = controlled_minion_count(
            controlled_minions,
            Player.GetAgentID(),
        )
        death_magic_rank = self._death_magic_rank()
        current_cap = minion_cap_for_death_magic(death_magic_rank)
        player_agent_id = Player.GetAgentID()
        masochism_equipped = self.IsSkillEquipped(MASOCHISM_ID)
        masochism_active = (
            masochism_equipped
            and Routines.Checks.Agents.HasEffect(player_agent_id, MASOCHISM_ID)
        )
        desired_cap = current_cap
        if masochism_equipped and not masochism_active:
            desired_cap = minion_cap_for_death_magic(death_magic_rank + 2)
        needs_summon = self._needs_guaranteed_summon(
            has_corpse=has_corpse,
            minion_count=minion_count,
            desired_cap=desired_cap,
        )

        # Do not spend a corpse at the lower Death Magic rank. If Masochism is
        # equipped, wait for it to become active before committing any summon.
        # Also maintain it in combat and whenever the extra cap is protecting
        # an eleventh minion; masking it from fallback must not drop the army.
        if masochism_equipped:
            if not masochism_active:
                extra_minion_needs_boost = minion_count > current_cap
                maintain_for_combat = self.IsInAggro() or self.IsCloseToAggro()
                if needs_summon or extra_minion_needs_boost or maintain_for_combat:
                    if (yield from self.CastSkillID(
                        skill_id=MASOCHISM_ID,
                        log=False,
                        aftercast_delay=250,
                    )):
                        return True
                    if needs_summon:
                        # The summon contract owns this tick.  Do not let the
                        # generic fallback spend energy while waiting for the
                        # attribute boost that determines minion level/cap.
                        return True

        if not needs_summon:
            return False

        if (
            has_corpse
            and self.IsSkillEquipped(ANIMATE_FLESH_GOLEM_ID)
            and not self._has_owned_flesh_golem()
            and self.CanCastSkillID(ANIMATE_FLESH_GOLEM_ID)
            and (yield from self.skillbook.Necromancer.DeathMagic.Animate_Flesh_Golem())
        ):
            return True

        # Aura of the Lich guarantees one Bone Horror even with no corpse. It
        # also consumes every corpse in earshot, so Flesh Golem gets first use.
        if self.IsSkillEquipped(AURA_OF_THE_LICH_ID) and self.CanCastSkillID(AURA_OF_THE_LICH_ID) and (
            yield from self.CastSkillID(
                skill_id=AURA_OF_THE_LICH_ID,
                log=False,
                aftercast_delay=250,
            )
        ):
            return True

        if has_corpse:
            for skill_id, helper_name in ORDINARY_ANIMATE_SKILLS:
                if not self.IsSkillEquipped(skill_id):
                    continue
                if not self.CanCastSkillID(skill_id):
                    continue
                helper = getattr(self.skillbook.Necromancer.DeathMagic, helper_name)
                if (yield from helper()):
                    return True

        # Signet of Lost Souls is free and is the bar's intended recovery tool.
        # Give it the only fallback-like action permitted while corpses and an
        # open minion slot exist; if there is no sub-50% target, wait for natural
        # regeneration/recharge instead of spending the reserve on utility.
        if self.IsSkillEquipped(SIGNET_OF_LOST_SOULS_ID) and (
            yield from self.skillbook.Necromancer.SoulReaping.Signet_of_Lost_Souls()
        ):
            return True

        # Let fallback act only with energy above the next summon cost.
        self._summon_energy_reserve = self._summon_reserve_cost(has_corpse)
        return False
