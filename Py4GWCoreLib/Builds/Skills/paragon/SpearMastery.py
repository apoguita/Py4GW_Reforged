from __future__ import annotations

from typing import TYPE_CHECKING

from Py4GWCoreLib import Routines
from Py4GWCoreLib.BuildMgr import BuildCoroutine
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill

if TYPE_CHECKING:
    from Py4GWCoreLib.BuildMgr import BuildMgr

__all__ = ["SpearMastery"]


class SpearMastery:
    def __init__(self, build: BuildMgr) -> None:
        self.build: BuildMgr = build

    def _resolve_spear_target(self, skill_id: int) -> int:
        if not self.build.CanCastSkillID(skill_id):
            return 0
        target_acquired, _ = self.build._resolve_target("EnemyInjured")
        if not target_acquired:
            return 0
        return self.build.current_target_id

    #region M
    def Mighty_Throw(self) -> BuildCoroutine:
        mighty_throw_id: int = Skill.GetID("Mighty_Throw")
        target_agent_id = self._resolve_spear_target(mighty_throw_id)
        if not target_agent_id:
            return False

        return (yield from self.build.CastSkillIDAndRestoreTarget(
            skill_id=mighty_throw_id,
            target_agent_id=target_agent_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion

    #region S
    def Spear_of_Redemption(self) -> BuildCoroutine:
        """Spear attack that strips a condition from us when it misses.

        Worth throwing while blinded, which is the reason PvX carries it: a
        blinded attack misses, and the miss is what removes the Blindness.
        """
        spear_of_redemption_id: int = Skill.GetID("Spear_of_Redemption")
        target_agent_id = self._resolve_spear_target(spear_of_redemption_id)
        if not target_agent_id:
            return False

        return (yield from self.build.CastSkillIDAndRestoreTarget(
            skill_id=spear_of_redemption_id,
            target_agent_id=target_agent_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion

    #region V
    def Vicious_Attack(self, *, require_critical_buff: bool = False) -> BuildCoroutine:
        """Spear attack that applies Deep Wound on a critical hit.

        With require_critical_buff set, it is held until "Go for the Eyes!" is
        up on us - that shout is what turns the conditional Deep Wound into a
        reliable one, and it is why PvX pairs the two.
        """
        vicious_attack_id: int = Skill.GetID("Vicious_Attack")

        if require_critical_buff:
            go_for_the_eyes_id: int = Skill.GetID("Go_for_the_Eyes")
            if self.build.IsSkillEquipped(go_for_the_eyes_id) and not Routines.Checks.Agents.HasEffect(
                Player.GetAgentID(),
                go_for_the_eyes_id,
            ):
                return False

        target_agent_id = self._resolve_spear_target(vicious_attack_id)
        if not target_agent_id:
            return False

        return (yield from self.build.CastSkillIDAndRestoreTarget(
            skill_id=vicious_attack_id,
            target_agent_id=target_agent_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion
