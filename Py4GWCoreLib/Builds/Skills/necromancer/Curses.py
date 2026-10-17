from __future__ import annotations

from typing import TYPE_CHECKING

from Py4GWCoreLib.BuildMgr import BuildCoroutine
from Py4GWCoreLib import GLOBAL_CACHE, Range, Routines, Utils
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill

if TYPE_CHECKING:
    from Py4GWCoreLib.HeroAI.custom_skill_src.skill_types import CustomSkill
    from Py4GWCoreLib.BuildMgr import BuildMgr

__all__ = ["Curses"]


class Curses:
    def __init__(self, build: BuildMgr) -> None:
        self.build: BuildMgr = build

    #region P
    def Poisoned_Heart(self) -> BuildCoroutine:
        """Self-cast Poisoned Heart while a foe stands within "nearby" range.

        Poisoned Heart poisons foes around the caster and the caster itself
        (which Contagion spreads). Cast only while the caster is not already
        poisoned, so it re-applies the self-Poison once it lapses; its recharge
        prevents spam.
        """
        poisoned_heart_id: int = Skill.GetID("Poisoned_Heart")

        if not self.build.IsSkillEquipped(poisoned_heart_id):
            return False
        if not Routines.Agents.GetNearestEnemy(Range.Nearby.value):
            return False
        if Agent.IsPoisoned(Player.GetAgentID()):
            return False

        return (yield from self.build.CastSkillID(
            skill_id=poisoned_heart_id,
            log=False,
            aftercast_delay=250,
        ))
    #endregion

    #region E
    def Enfeebling_Blood(self) -> BuildCoroutine:
        enfeebling_blood_id: int = Skill.GetID("Enfeebling_Blood")
        enfeebling_blood: CustomSkill = self.build.GetCustomSkill(enfeebling_blood_id)

        def _can_safely_cast_enfeebling_blood() -> bool:
            return Agent.GetHealth(Player.GetAgentID()) > enfeebling_blood.Conditions.SacrificeHealth

        if not self.build.IsSkillEquipped(enfeebling_blood_id):
            return False
        if not _can_safely_cast_enfeebling_blood():
            return False
        if not (yield from self.build.AcquireTarget(target_type="EnemyClustered")):
            return False

        return (yield from self.build.CastSkillID(
            skill_id=enfeebling_blood_id,
            extra_condition=_can_safely_cast_enfeebling_blood,
            log=False,
            aftercast_delay=250,
            target_agent_id=self.build.current_target_id,
        ))
    #endregion

    #region M
    def Mark_of_Pain(
        self,
        *,
        min_adjacent_enemies: int = 2,
        min_target_health: float = 0.30,
    ) -> BuildCoroutine:
        """Cast Mark of Pain on a durable enemy standing inside a useful pack.

        The target itself does not take Mark of Pain's splash damage, so avoid
        isolated or nearly-dead foes. Prefer the player's current target when it
        already anchors a valid pack; otherwise choose the eligible enemy with
        the most adjacent enemies.
        """
        mark_of_pain_id: int = Skill.GetID("Mark_of_Pain")

        if not self.build.IsSkillEquipped(mark_of_pain_id):
            return False
        if not self.build.IsInAggro():
            return False

        player_pos = Player.GetXY()
        enemies = Routines.Agents.GetFilteredEnemyArray(
            player_pos[0],
            player_pos[1],
            Range.Spellcast.value,
        )
        if not enemies:
            return False

        def _eligible(agent_id: int) -> bool:
            return (
                Agent.IsAlive(agent_id)
                and Agent.GetHealth(agent_id) > min_target_health
                and not Routines.Checks.Agents.HasEffect(agent_id, mark_of_pain_id)
            )

        candidates = [agent_id for agent_id in enemies if _eligible(agent_id)]
        if not candidates:
            return False

        def _adjacent_enemy_count(agent_id: int) -> int:
            target_xy = Agent.GetXY(agent_id)
            return sum(
                1
                for other_id in enemies
                if other_id != agent_id
                and Agent.IsAlive(other_id)
                and Utils.Distance(target_xy, Agent.GetXY(other_id)) <= Range.Adjacent.value
            )

        valid_candidates = [
            agent_id
            for agent_id in candidates
            if _adjacent_enemy_count(agent_id) >= min_adjacent_enemies
        ]
        if not valid_candidates:
            return False

        current_target_id = Player.GetTargetID()
        if current_target_id in valid_candidates:
            target_agent_id = current_target_id
        else:
            target_agent_id = max(
                valid_candidates,
                key=lambda agent_id: (
                    _adjacent_enemy_count(agent_id),
                    Agent.GetHealth(agent_id),
                ),
            )

        return (yield from self.build.CastSkillIDAndRestoreTarget(
            skill_id=mark_of_pain_id,
            target_agent_id=target_agent_id,
            extra_condition=lambda: _eligible(target_agent_id),
            log=False,
            aftercast_delay=250,
        ))
    #endregion


    #region S
    def Spiteful_Spirit(self, *, exclude_target_id: int = 0, min_target_health: float = 0.20) -> BuildCoroutine:
        """Cast Spiteful Spirit on a high-value active foe in a cluster.

        Targeting rules:
        - only while in aggro;
        - never overwrite an existing Spiteful Spirit effect;
        - prefer foes that are currently attacking or casting;
        - among valid foes, prefer the most clustered target;
        - optionally exclude the previous target for Arcane Echo's copied cast.

        The ready-slot scan mirrors the proven Ray of Judgment / Arcane Echo
        pattern: after Arcane Echo copies SS, the original SS slot can be on
        cooldown while the copied SS lives in a second ready slot.
        """
        spiteful_spirit_id: int = Skill.GetID("Spiteful_Spirit")

        if not self.build.IsSkillEquipped(spiteful_spirit_id):
            return False
        if not self.build.IsInAggro():
            return False

        primary_slot = GLOBAL_CACHE.SkillBar.GetSlotBySkillID(spiteful_spirit_id)
        if not primary_slot:
            return False

        if Routines.Checks.Skills.IsSkillSlotReady(primary_slot):
            ready_slot = primary_slot
        else:
            ready_slot = 0
            for slot in range(1, 9):
                if slot == primary_slot:
                    continue
                if GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) == spiteful_spirit_id:
                    if Routines.Checks.Skills.IsSkillSlotReady(slot):
                        ready_slot = slot
                        break
            if not ready_slot:
                return False

        def _eligible(agent_id: int) -> bool:
            if exclude_target_id and agent_id == exclude_target_id:
                return False
            if Agent.GetHealth(agent_id) <= min_target_health:
                return False
            if Routines.Checks.Agents.HasEffect(agent_id, spiteful_spirit_id):
                return False
            return True

        # SS only produces value while the victim acts. Prefer attacking/casting
        # foes rather than blindly hexing a passive body in the ball.
        target_agent_id = Routines.Targeting.PickClusteredTarget(
            cluster_radius=Range.Adjacent.value,
            preferred_condition=lambda agent_id: (
                _eligible(agent_id)
                and (Agent.IsAttacking(agent_id) or Agent.IsCasting(agent_id))
            ),
            filter_radius=Range.Spellcast.value,
        )
        if not target_agent_id:
            return False

        if ready_slot == primary_slot:
            cast_result = yield from self.build.CastSkillIDAndRestoreTarget(
                skill_id=spiteful_spirit_id,
                target_agent_id=target_agent_id,
                extra_condition=lambda: _eligible(target_agent_id),
                log=False,
                aftercast_delay=250,
            )
        else:
            # Arcane Echo copy: CastSkillID would resolve the on-cooldown primary
            # slot first, so use the ready duplicate slot directly.
            previous_enemy_target = Player.GetTargetID()
            if previous_enemy_target != target_agent_id:
                yield from Routines.Yield.Agents.ChangeTarget(target_agent_id)

            if not _eligible(target_agent_id):
                yield from self.build.RestoreEnemyTarget(previous_enemy_target)
                return False

            GLOBAL_CACHE.SkillBar.UseSkill(
                ready_slot,
                target_agent_id=target_agent_id,
                aftercast_delay=250,
            )
            self.build._mark_local_cast_pending(250)
            self.build.SetTickSuccess()
            yield from self.build.RestoreEnemyTarget(previous_enemy_target)
            cast_result = True

        if cast_result:
            self.build._last_spiteful_spirit_target_id = target_agent_id

        return cast_result
    #endregion

    #region W
    def Weaken_Armor(self) -> BuildCoroutine:
        weaken_armor_id: int = Skill.GetID("Weaken_Armor")
        cracked_armor_id: int = Skill.GetID("Cracked_Armor")

        if not self.build.IsSkillEquipped(weaken_armor_id):
            return False

        target_agent_id = Routines.Targeting.PickClusteredTarget(
            Range.Adjacent.value,
            preferred_condition=lambda agent_id: not Routines.Checks.Agents.HasEffect(agent_id, cracked_armor_id),
            filter_radius=Range.Spellcast.value,
        )
        if not target_agent_id:
            return False
        if Routines.Checks.Agents.HasEffect(target_agent_id, cracked_armor_id):
            return False

        return (yield from self.build.CastSkillID(
            skill_id=weaken_armor_id,
            log=False,
            aftercast_delay=250,
            target_agent_id=target_agent_id,
            extra_condition=lambda: not Routines.Checks.Agents.HasEffect(target_agent_id, cracked_armor_id),
        ))
    #endregion
