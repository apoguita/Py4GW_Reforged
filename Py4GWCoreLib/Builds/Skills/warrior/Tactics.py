from __future__ import annotations

from typing import TYPE_CHECKING

from Py4GWCoreLib import Player, Routines
from Py4GWCoreLib.BuildMgr import BuildCoroutine
from Py4GWCoreLib.Skill import Skill

if TYPE_CHECKING:
    from Py4GWCoreLib.BuildMgr import BuildMgr

__all__ = ["Tactics"]


class Tactics:
    def __init__(self, build: BuildMgr) -> None:
        self.build: BuildMgr = build

    #region T
    def To_the_Limit(self) -> BuildCoroutine:
        """Adrenaline generator: one strike per foe in earshot, plus max Health.

        Its whole value is the initial burst, which scales with how many foes
        are around, so it is held until we are actually in the fight rather than
        spent on the approach. Guarded on our own copy expiring: it is a shout,
        and recasting one before it ends skips the refrain renewal that fires
        when a shout ends on an ally.
        """
        to_the_limit_id: int = Skill.GetID("To_the_Limit")
        player_agent_id = Player.GetAgentID()

        if not self.build.IsSkillEquipped(to_the_limit_id):
            return False
        if not self.build.IsInAggro():
            return False
        if Routines.Checks.Agents.HasEffect(player_agent_id, to_the_limit_id):
            return False

        return (yield from self.build.CastSkillID(
            skill_id=to_the_limit_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion
