from __future__ import annotations

from typing import TYPE_CHECKING

from Py4GWCoreLib.BuildMgr import BuildCoroutine
from Py4GWCoreLib import GLOBAL_CACHE, Player, Routines
from Py4GWCoreLib.Skill import Skill

if TYPE_CHECKING:
    from Py4GWCoreLib.BuildMgr import BuildMgr

__all__ = ["Command"]


class Command:
    def __init__(self, build: BuildMgr) -> None:
        self.build: BuildMgr = build

    #region B
    def Bladeturn_Refrain(self, *, max_target_range: float | None = None) -> BuildCoroutine:
        return (yield from self.build.SpreadEchoToAlly(
            Skill.GetID("Bladeturn_Refrain"),
            max_range=max_target_range,
        ))
    #endregion

    #region C
    def Cant_Touch_This(self, *, min_remaining_ms: int = 1500) -> BuildCoroutine:
        """Anti-touch party shout.

        min_remaining_ms is how much of the running shout we are willing to
        throw away by recasting early. Callers maintaining refrains should
        pass 0.

        Inferred, not confirmed in an injected client: a shout replaced before
        it expires is believed not to fire the "a chant or shout ends" trigger
        that reapplies an echo, so recasting early would silently skip a refrain
        renewal for the whole party. What the shipped data actually states is
        only the positive half - skill_descriptions.json describes a refrain as
        renewed "whenever a chant or shout ends on that ally". The rest comes
        from the PvX build notes. Every "let it expire first" guard on the
        Paragon refrain bar rests on this, so it is the one assumption to settle
        first if the rotation misbehaves in game.
        """
        cant_touch_this_id: int = Skill.GetID("Cant_Touch_This")
        player_agent_id = Player.GetAgentID()

        if not self.build.IsSkillEquipped(cant_touch_this_id):
            return False
        if not self.build.IsInAggro():
            return False

        if Routines.Checks.Agents.HasEffect(player_agent_id, cant_touch_this_id):
            if min_remaining_ms <= 0:
                # Presence is authoritative, the remaining time is not:
                # GetEffectTimeRemaining only scans the effect list while
                # HasEffect also accepts the buff list, so a shout reported as a
                # buff reads 0 here. A caller asking us never to clip the shout
                # would then clip it on every recharge - the exact failure this
                # parameter exists to prevent.
                return False
            remaining_ms = int(GLOBAL_CACHE.Effects.GetEffectTimeRemaining(player_agent_id, cant_touch_this_id) or 0)
            if remaining_ms > min_remaining_ms:
                return False

        return (yield from self.build.CastSkillID(
            skill_id=cant_touch_this_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion

    #region F
    def Fall_Back(self) -> BuildCoroutine:
        """Party-wide out-of-combat run speed.

        Ends on the affected ally's next attack, so it is only worth casting
        while the party is travelling. "Incoming!" is the same non-stacking
        speed buff, and BuildMgr does not enforce the CustomSkill
        Conditions.SharedEffects link, so the overlap is checked here.
        """
        fall_back_id: int = Skill.GetID("Fall_Back")
        incoming_id: int = Skill.GetID("Incoming")
        player_agent_id = Player.GetAgentID()

        if not self.build.IsSkillEquipped(fall_back_id):
            return False
        if self.build.IsInAggro() or self.build.IsCloseToAggro():
            return False
        if Routines.Checks.Agents.HasEffect(player_agent_id, fall_back_id):
            return False
        if Routines.Checks.Agents.HasEffect(player_agent_id, incoming_id):
            return False

        return (yield from self.build.CastSkillID(
            skill_id=fall_back_id,
            log=False,
            aftercast_delay=250,
        ))

    def Find_Their_Weakness(self) -> BuildCoroutine:
        """Hands the next attack of one martial ally a big bonus plus Deep Wound."""
        find_their_weakness_id: int = Skill.GetID("Find_Their_Weakness")
        find_their_weakness = self.build.GetCustomSkill(find_their_weakness_id)

        if not self.build.IsInAggro():
            return False
        # Before resolving an ally: that walks the party several times and this
        # runs every tick, while the chant is on recharge for most of them.
        if not self.build.CanCastSkillID(find_their_weakness_id):
            return False

        target_agent_id = self.build.ResolveAllyTargetInRange(
            find_their_weakness_id,
            find_their_weakness,
        )
        if not target_agent_id:
            return False

        return (yield from self.build.CastSkillIDAndRestoreTarget(
            skill_id=find_their_weakness_id,
            target_agent_id=target_agent_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion

    #region G
    def Go_for_the_Eyes(self) -> BuildCoroutine:
        """Party-wide critical hit chance, and the bar's cheapest energy engine.

        Leadership refunds energy per ally a shout affects, so this pays for
        itself several times over in a full party. Guarded on our own copy
        expiring rather than on recharge: replacing a running shout skips the
        refrain renewal that fires when a shout ends.
        """
        go_for_the_eyes_id: int = Skill.GetID("Go_for_the_Eyes")
        player_agent_id = Player.GetAgentID()

        if not self.build.IsSkillEquipped(go_for_the_eyes_id):
            return False
        if not self.build.IsInAggro():
            return False
        if Routines.Checks.Agents.HasEffect(player_agent_id, go_for_the_eyes_id):
            return False

        return (yield from self.build.CastSkillID(
            skill_id=go_for_the_eyes_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion

    #region S
    def Stand_Your_Ground(self) -> BuildCoroutine:
        stand_your_ground_id: int = Skill.GetID("Stand_Your_Ground")
        player_agent_id = Player.GetAgentID()

        if not self.build.IsSkillEquipped(stand_your_ground_id):
            return False
        if not self.build.IsInAggro():
            return False
        if Routines.Checks.Agents.HasEffect(player_agent_id, stand_your_ground_id):
            return False

        return (yield from self.build.CastSkillID(
            skill_id=stand_your_ground_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion
