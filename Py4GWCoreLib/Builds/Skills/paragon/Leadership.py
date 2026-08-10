from __future__ import annotations

from typing import TYPE_CHECKING

from Py4GWCoreLib.BuildMgr import BuildCoroutine
from Py4GWCoreLib import GLOBAL_CACHE, Player, Routines
from Py4GWCoreLib.Skill import Skill

if TYPE_CHECKING:
    from Py4GWCoreLib.BuildMgr import BuildMgr

__all__ = ["Leadership"]


class Leadership:
    def __init__(self, build: BuildMgr) -> None:
        self.build: BuildMgr = build

    def _get_leadership_level(self) -> int:
        from Py4GWCoreLib import Agent

        player_agent_id = Player.GetAgentID()
        attributes = Agent.GetAttributes(player_agent_id)
        leadership = next((attribute for attribute in attributes if attribute.GetName() == "Leadership"), None)
        return int(getattr(leadership, "level", 0) or 0)

    @staticmethod
    def _get_effect_attribute_level(skill_id: int) -> int:
        player_agent_id = Player.GetAgentID()
        effect = next(
            (
                item
                for item in GLOBAL_CACHE.Effects.GetEffects(player_agent_id)
                if item.skill_id == skill_id
            ),
            None,
        )
        return int(getattr(effect, "attribute_level", 0) or 0)

    def _heroic_refrain_needs_self_bootstrap(self, heroic_refrain_id: int) -> bool:
        player_agent_id = Player.GetAgentID()
        if not Routines.Checks.Agents.HasEffect(player_agent_id, heroic_refrain_id):
            return True

        leadership_level = self._get_leadership_level()
        if leadership_level >= 20:
            return False

        cast_level = self._get_effect_attribute_level(heroic_refrain_id)
        return cast_level > 0 and leadership_level > cast_level

    #region H
    def Heroic_Refrain(self) -> BuildCoroutine:
        heroic_refrain_id: int = Skill.GetID("Heroic_Refrain")
        heroic_refrain = self.build.GetCustomSkill(heroic_refrain_id)

        if not self.build.IsSkillEquipped(heroic_refrain_id):
            return False

        player_agent_id = Player.GetAgentID()
        if self._heroic_refrain_needs_self_bootstrap(heroic_refrain_id):
            return (yield from self.build.CastSkillIDAndRestoreTarget(
                skill_id=heroic_refrain_id,
                target_agent_id=player_agent_id,
                log=False,
                aftercast_delay=250,
            ))
        if not Routines.Checks.Agents.HasEffect(player_agent_id, heroic_refrain_id):
            return (yield from self.build.CastSkillIDAndRestoreTarget(
                skill_id=heroic_refrain_id,
                target_agent_id=player_agent_id,
                log=False,
                aftercast_delay=250,
            ))

        target_agent_id = self.build.ResolveAllyTarget(
            heroic_refrain_id,
            heroic_refrain,
        )
        if not target_agent_id:
            return False

        return (yield from self.build.CastSkillIDAndRestoreTarget(
            skill_id=heroic_refrain_id,
            target_agent_id=target_agent_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion

    #region A
    def Anthem_of_Flame(self) -> BuildCoroutine:
        anthem_of_flame_id: int = Skill.GetID("Anthem_of_Flame")
        player_agent_id = Player.GetAgentID()

        if not self.build.IsSkillEquipped(anthem_of_flame_id):
            return False
        if Routines.Checks.Agents.HasEffect(player_agent_id, anthem_of_flame_id):
            return False

        return (yield from self.build.CastSkillID(
            skill_id=anthem_of_flame_id,
            target_agent_id=player_agent_id,
            log=False,
            aftercast_delay=250,
        ))

    def Aggressive_Refrain(self) -> BuildCoroutine:
        """Apply the 25% IAS echo once; the bar's shouts keep it up from there.

        Not gated on aggro. Aggressive Refrain is reapplied every time a chant
        or shout ends on us, so on any bar carrying shouts it never drops once
        it lands - which means holding it back until combat buys nothing. The
        -20 armor is permanent either way, and waiting only costs us the attack
        speed for the opening of every fight.
        """
        aggressive_refrain_id: int = Skill.GetID("Aggressive_Refrain")
        player_agent_id = Player.GetAgentID()

        if not self.build.IsSkillEquipped(aggressive_refrain_id):
            return False
        if Routines.Checks.Agents.HasEffect(player_agent_id, aggressive_refrain_id):
            return False

        return (yield from self.build.CastSkillID(
            skill_id=aggressive_refrain_id,
            target_agent_id=player_agent_id,
            log=False,
            aftercast_delay=250,
        ))

    def Angelic_Protection(
        self,
        *,
        health_threshold: float | None = None,
    ) -> BuildCoroutine:
        from Py4GWCoreLib.Agent import Agent

        angelic_protection_id: int = Skill.GetID("Angelic_Protection")
        angelic_protection = self.build.GetCustomSkill(angelic_protection_id)

        if not self.build.IsSkillEquipped(angelic_protection_id):
            return False
        if not self.build.IsInAggro():
            return False

        threshold: float = (
            health_threshold
            if health_threshold is not None
            else float(angelic_protection.Conditions.LessLife or 0.75)
        )
        threshold = max(0.0, min(1.0, threshold))

        target_agent_id = self.build.ResolvePreferredAllyTarget(
            angelic_protection_id,
            angelic_protection,
            validator=lambda agent_id: Agent.IsAlive(agent_id) and Agent.GetHealth(agent_id) < threshold,
        )
        if not target_agent_id:
            return False

        return (yield from self.build.CastSkillIDAndRestoreTarget(
            skill_id=angelic_protection_id,
            target_agent_id=target_agent_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion

    #region M
    def Make_Your_Time(self) -> BuildCoroutine:
        from Py4GWCoreLib import Agent, AgentArray, Range
        from Py4GWCoreLib.HeroAI.utils import IsPartyMember

        make_your_time_id: int = Skill.GetID("Make_Your_Time")
        player_agent_id = Player.GetAgentID()

        if not self.build.IsSkillEquipped(make_your_time_id):
            return False

        if not (self.build.IsInAggro() or self.build.IsCloseToAggro()):
            return False

        candidates = AgentArray.GetAllyArray() + AgentArray.GetSpiritPetArray()
        candidates = AgentArray.Filter.ByDistance(candidates, Player.GetXY(), Range.Earshot.value)
        candidates = AgentArray.Filter.ByCondition(candidates, lambda a: Agent.IsAlive(a) and IsPartyMember(a))
        if len(candidates) < 3:
            return False

        return (yield from self.build.CastSkillID(
            skill_id=make_your_time_id,
            target_agent_id=player_agent_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion

    #region T
    def Theyre_on_Fire(self) -> BuildCoroutine:
        theyre_on_fire_id: int = Skill.GetID("Theyre_on_Fire")
        player_agent_id = Player.GetAgentID()

        if not self.build.IsSkillEquipped(theyre_on_fire_id):
            return False
        if Routines.Checks.Agents.HasEffect(player_agent_id, theyre_on_fire_id):
            return False

        return (yield from self.build.CastSkillID(
            skill_id=theyre_on_fire_id,
            target_agent_id=player_agent_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion
