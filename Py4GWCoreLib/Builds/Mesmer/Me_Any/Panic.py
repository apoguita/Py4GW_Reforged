from dataclasses import dataclass

from Py4GWCoreLib import Agent, AgentArray, Player, Profession, Range, Routines, BuildMgr, GLOBAL_CACHE
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI as HeroAIBuild
from Py4GWCoreLib.Builds.Skills import HexRemovalPriority, SkillsTemplate
from Py4GWCoreLib.Builds.Skills.CryOfFrustrationCoordination import (
    reserve_best_cry_packet,
    release_cry_reservation,
    register_cry_fired,
    is_enemy_cry_covered,
)


Air_of_Superiority_ID = Skill.GetID("Air_of_Superiority")
Panic_ID = Skill.GetID("Panic")
Mistrust_ID = Skill.GetID("Mistrust")
Ebon_Vanguard_Assassin_Support_ID = Skill.GetID("Ebon_Vanguard_Assassin_Support")
Cry_of_Pain_ID = Skill.GetID("Cry_of_Pain")
Unnatural_Signet_ID = Skill.GetID("Unnatural_Signet")
Cry_of_Frustration_ID = Skill.GetID("Cry_of_Frustration")
Overload_ID = Skill.GetID("Overload")
Power_Drain_ID = Skill.GetID("Power_Drain")
Energy_Tap_ID = Skill.GetID("Energy_Tap")
Recuperation_ID = Skill.GetID("Recuperation")
Mend_Body_and_Soul_ID = Skill.GetID("Mend_Body_and_Soul")
Spirit_Light_ID = Skill.GetID("Spirit_Light")
Shatter_Hex_ID = Skill.GetID("Shatter_Hex")
Flesh_of_My_Flesh_ID = Skill.GetID("Flesh_of_My_Flesh")
Breath_of_the_Great_Dwarf_ID = Skill.GetID("Breath_of_the_Great_Dwarf")
Ebon_Battle_Standard_of_Courage_ID = Skill.GetID("Ebon_Battle_Standard_of_Courage")
Ebon_Battle_Standard_of_Honor_ID = Skill.GetID("Ebon_Battle_Standard_of_Honor")
Tryptophan_Signet_ID = Skill.GetID("Tryptophan_Signet")


@dataclass(slots=True)
class _PanicBarSnapshot:
    in_aggro: bool = False
    enemy_in_spellcast: bool = False
    enemy_casting: bool = False
    enemy_casting_spell: bool = False
    enemy_casting_spell_or_chant: bool = False
    player_energy_pct: float = 1.0


class Panic(BuildMgr):
    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Panic",
            required_primary=Profession.Mesmer,
            template_code="OQBDAssjJ0QOM9AAAAAAAAA",
            required_skills=[
                Panic_ID,
                Cry_of_Frustration_ID,
                Mistrust_ID,
            ],
            optional_skills=[
                Air_of_Superiority_ID,
                Ebon_Vanguard_Assassin_Support_ID,
                Cry_of_Pain_ID,
                Unnatural_Signet_ID,
                Power_Drain_ID,
                Energy_Tap_ID,
                Recuperation_ID,
                Mend_Body_and_Soul_ID,
                Spirit_Light_ID,
                Shatter_Hex_ID,
                Overload_ID,
                Flesh_of_My_Flesh_ID,
                Breath_of_the_Great_Dwarf_ID,
                Ebon_Battle_Standard_of_Courage_ID,
                Ebon_Battle_Standard_of_Honor_ID,
                Tryptophan_Signet_ID,
            ],
        )
        if match_only:
            return

        self.SetFallback("HeroAI", HeroAIBuild(standalone_fallback=True))
        self.SetBlockedSkills([
            Air_of_Superiority_ID,
            Panic_ID,
            Mistrust_ID,
            Ebon_Vanguard_Assassin_Support_ID,
            Cry_of_Pain_ID,
            Unnatural_Signet_ID,
            Cry_of_Frustration_ID,
            Overload_ID,
            Power_Drain_ID,
            Energy_Tap_ID,
            Recuperation_ID,
            Mend_Body_and_Soul_ID,
            Spirit_Light_ID,
            Shatter_Hex_ID,
            Ebon_Battle_Standard_of_Courage_ID,
            Ebon_Battle_Standard_of_Honor_ID,
            Tryptophan_Signet_ID,
        ])
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skills: SkillsTemplate = SkillsTemplate(self)

    def _get_bar_snapshot(self) -> _PanicBarSnapshot:
        snapshot = _PanicBarSnapshot()
        snapshot.in_aggro = bool(self.IsInAggro())
        snapshot.player_energy_pct = float(Agent.GetEnergy(Player.GetAgentID()))

        if not snapshot.in_aggro:
            return snapshot

        snapshot.enemy_in_spellcast = bool(Routines.Agents.GetNearestEnemy(Range.Spellcast.value))
        if snapshot.enemy_in_spellcast:
            snapshot.enemy_casting = bool(Routines.Targeting.GetEnemyCasting(Range.Spellcast.value))
            snapshot.enemy_casting_spell = bool(Routines.Targeting.GetEnemyCastingSpell(Range.Spellcast.value))
            snapshot.enemy_casting_spell_or_chant = bool(Routines.Targeting.GetEnemyCastingSpellOrChant(Range.Spellcast.value))

        return snapshot

    @staticmethod
    def _combat_log(event: str, **fields) -> None:
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(str(event), **fields)
        except Exception:
            pass

    def _team_packet(self) -> tuple[int, list[int]]:
        """Return the canonical KeySoJway packet/cleanup target for this Mesmer.

        The Panic Mesmer deliberately consumes the same TeamCombatFocus resolver
        as Keystone, Fire Ele and MM.  It may choose a better *member* inside the
        packet for an AoE/interrupt cast, but it never peels onto another group.
        """
        try:
            from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import (
                get_team_cluster_anchor,
                get_team_cluster_members,
            )
            anchor = int(get_team_cluster_anchor(
                filter_range=float(Range.Spellcast.value),
                minimum_enemies=2,
                consumer_role="panic_mesmer",
            ) or 0)
            if anchor <= 0:
                return 0, []
            members = list(get_team_cluster_members(
                anchor,
                radius=float(Range.Nearby.value),
                filter_range=float(Range.Spellcast.value),
            ) or [])
            if not members and Agent.IsValid(anchor) and Agent.IsAlive(anchor):
                members = [anchor]
            return anchor, [int(x) for x in members]
        except Exception:
            return 0, []

    @staticmethod
    def _packet_centrality(enemy_id: int) -> int:
        try:
            from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import count_adjacent_enemies
            return int(count_adjacent_enemies(
                int(enemy_id), radius=float(Range.Nearby.value)
            ) or 0)
        except Exception:
            return 0

    @staticmethod
    def _is_support_or_caster(enemy_id: int) -> bool:
        try:
            from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import is_support_or_caster
            return bool(is_support_or_caster(int(enemy_id)))
        except Exception:
            try:
                return bool(Agent.IsCaster(int(enemy_id)))
            except Exception:
                return False

    def _pick_packet_member(self, members: list[int], *, require_casting: bool = False,
                            spell_or_chant_only: bool = False, prefer_caster: bool = True) -> int:
        candidates: list[int] = []
        for enemy_id in members:
            try:
                enemy_id = int(enemy_id)
                if enemy_id <= 0 or not Agent.IsValid(enemy_id) or not Agent.IsAlive(enemy_id):
                    continue
                if require_casting and not Agent.IsCasting(enemy_id):
                    continue
                if spell_or_chant_only:
                    casting_skill_id = int(Agent.GetCastingSkillID(enemy_id) or 0)
                    if casting_skill_id <= 0:
                        continue
                    if not (GLOBAL_CACHE.Skill.Flags.IsSpell(casting_skill_id)
                            or GLOBAL_CACHE.Skill.Flags.IsChant(casting_skill_id)):
                        continue
                candidates.append(enemy_id)
            except Exception:
                continue
        if not candidates:
            return 0

        def rank(enemy_id: int):
            try:
                caster = bool(Agent.IsCaster(enemy_id))
            except Exception:
                caster = False
            try:
                hp = float(Agent.GetHealth(enemy_id))
            except Exception:
                hp = 1.0
            # Caster/support first, then the member covering the most Nearby foes.
            # HP is only a late tie-breaker; cluster efficiency wins.
            return (
                -int(caster if prefer_caster else False),
                -int(self._is_support_or_caster(enemy_id)),
                -int(self._packet_centrality(enemy_id)),
                hp,
                enemy_id,
            )

        candidates.sort(key=rank)
        return int(candidates[0])

    def _try_recuperation_pre_fight(self):
        """Pre-cast/refresh Recuperation for a real 3+ enemy packet.

        This is intentionally before the offensive opener.  BuildMgr's spirit
        duplicate guard prevents wasting the cast when a live Recuperation is
        already in earshot (including one supplied by another team member).
        """
        if not self.IsSkillEquipped(Recuperation_ID):
            return False
        if not (self.IsCloseToAggro() or self.IsInAggro()):
            return False

        anchor, members = self._team_packet()
        if anchor <= 0 or len(members) < 3:
            return False
        if not self.CanCastSkillID(Recuperation_ID):
            return False

        did_cast = yield from self.CastSpiritSkillID(
            skill_id=Recuperation_ID,
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            self._combat_log(
                "PANIC_RECUPERATION_PRE_FIGHT",
                target_id=int(anchor),
                packet_size=int(len(members)),
                policy="precast_or_refresh_before_3plus_packet",
            )
            return True
        return False

    def _try_mend_body_and_soul_heroai(self):
        """Run Mend Body and Soul with the original HeroAI-style priorities.

        The Panic rotation is intentionally busy. Leaving MBaS only to the fallback
        can starve healing while Panic/interrupt actions keep succeeding. Handle it
        locally with HeroAI's normal 70% heal threshold and its condition-cleanse
        behavior when a spirit is in earshot.
        """
        if not self.IsSkillEquipped(Mend_Body_and_Soul_ID):
            return False
        if not self.CanCastSkillID(Mend_Body_and_Soul_ID):
            return False

        try:
            from Py4GWCoreLib.HeroAI.targeting import TargetLowestAlly
            target_id = int(TargetLowestAlly(
                filter_skill_id=Mend_Body_and_Soul_ID,
                distance=Range.Spellcast.value,
            ) or 0)
        except Exception:
            target_id = 0

        if target_id <= 0 or not Agent.IsValid(target_id) or not Agent.IsAlive(target_id):
            return False

        try:
            target_hp = float(Agent.GetHealth(target_id))
        except Exception:
            target_hp = 1.0

        try:
            spirit_exists = bool(Routines.Agents.GetNearestSpirit(Range.Earshot.value))
        except Exception:
            spirit_exists = False
        try:
            conditioned = bool(Routines.Checks.Agents.IsConditioned(target_id))
        except Exception:
            conditioned = False

        # Stock HeroAI metadata for MBaS uses LessLife = 0.70. A nearby spirit
        # also enables the skill's condition removal, so conditioned allies are
        # valid even above the pure-healing threshold.
        reason = ""
        if target_hp < 0.70:
            reason = "heroai_heal_below_70"
        elif spirit_exists and conditioned:
            reason = "heroai_condition_cleanse_with_spirit"
        else:
            return False

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Mend_Body_and_Soul_ID,
            target_agent_id=target_id,
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            self._combat_log(
                "PANIC_MEND_BODY_SOUL_HEROAI",
                target_id=int(target_id),
                target_hp=round(float(target_hp), 3),
                spirit_exists=bool(spirit_exists),
                conditioned=bool(conditioned),
                reason=reason,
                policy="heroai_70pct_or_condition_with_spirit",
            )
            return True
        return False


    def _try_spirit_light_heal(self, *, health_threshold: float) -> bool:
        """Use Spirit Light as a real team heal without starving Panic offense.

        The shared RestorationMagic helper already handles the Spirit Light
        sacrifice safety rule and normal ally targeting. We only control the
        urgency threshold here.
        """
        if not self.IsSkillEquipped(Spirit_Light_ID):
            return False
        if not self.CanCastSkillID(Spirit_Light_ID):
            return False
        did_cast = yield from self.skills.Ritualist.RestorationMagic.Spirit_Light(
            health_threshold=float(health_threshold),
        )
        if did_cast:
            self._combat_log(
                "PANIC_SPIRIT_LIGHT_HEAL",
                threshold=round(float(health_threshold), 3),
                policy="emergency_30_then_normal_68",
            )
            return True
        return False

    def _find_any_caster_cluster(self) -> tuple[int, list[int], int]:
        """Find any real 2+ caster/support group in spellcast range.

        This path is deliberately independent of dangerous-cast scoring. Panic is
        valuable because *any* caster group can repeatedly trigger it, not only a
        group currently using a skill classified as dangerous.
        """
        try:
            enemies = list(AgentArray.GetEnemyArray() or [])
            enemies = AgentArray.Filter.ByDistance(
                enemies, Player.GetXY(), float(Range.Spellcast.value)
            )
            enemies = [
                int(eid) for eid in enemies or []
                if int(eid or 0) > 0 and Agent.IsValid(int(eid)) and Agent.IsAlive(int(eid))
            ]
        except Exception:
            return 0, [], 0

        caster_ids = [eid for eid in enemies if self._is_support_or_caster(eid)]
        if len(caster_ids) < 2:
            return 0, [], 0

        best_target = 0
        best_members: list[int] = []
        best_caster_count = 0
        best_rank = None

        for center_id in caster_ids:
            try:
                center_xy = Agent.GetXY(int(center_id))
                nearby_all = AgentArray.Filter.ByDistance(
                    enemies, center_xy, float(Range.Nearby.value)
                )
                nearby_all = [int(eid) for eid in nearby_all or []]
                nearby_casters = [eid for eid in nearby_all if self._is_support_or_caster(eid)]
                caster_count = len(nearby_casters)
                if caster_count < 2:
                    continue
                # First maximize affected casters, then total foes caught by Panic.
                # Stable agent id is only a deterministic tie-breaker.
                rank = (caster_count, len(nearby_all), -int(center_id))
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best_target = int(center_id)
                    best_members = nearby_all
                    best_caster_count = int(caster_count)
            except Exception:
                continue

        return int(best_target), list(best_members), int(best_caster_count)

    def _try_panic_team_packet(self):
        if not self.IsSkillEquipped(Panic_ID) or not self.CanCastSkillID(Panic_ID):
            return False

        # Hard Panic preference: ANY 2+ caster/support group, regardless of
        # dangerous-cast classification. This runs before the normal shared
        # packet resolver so a harmless-looking caster pack is never skipped.
        caster_target, caster_members, caster_count = self._find_any_caster_cluster()
        if caster_target > 0 and caster_count >= 2:
            target_id = int(caster_target)
            anchor = int(caster_target)
            members = list(caster_members)
            mode = "caster_cluster"
        else:
            anchor, members = self._team_packet()
            if anchor <= 0 or not members:
                return False

            # No 2+ caster group exists: retain the normal team packet behavior.
            if len(members) <= 1:
                target_id = int(anchor)
                mode = "cleanup"
            else:
                target_id = self._pick_packet_member(members, prefer_caster=True) or int(anchor)
                mode = "cluster"

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Panic_ID,
            target_agent_id=int(target_id),
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            if mode != "caster_cluster":
                caster_count = 0
                for enemy_id in members:
                    try:
                        caster_count += int(bool(self._is_support_or_caster(int(enemy_id))))
                    except Exception:
                        pass
            self._combat_log(
                "PANIC_TEAM_PACKET_CAST",
                target_id=int(target_id),
                anchor_id=int(anchor),
                packet_size=int(len(members)),
                caster_count=int(caster_count),
                mode=str(mode),
                policy="any_2plus_caster_cluster_first_then_team_packet",
            )
            return True
        return False

    def _try_cry_of_frustration_team_packet(self):
        if not self.IsSkillEquipped(Cry_of_Frustration_ID) or not self.CanCastSkillID(Cry_of_Frustration_ID):
            return False

        # First refusal: the same cross-account high-value packet coordinator
        # used by optional Keystone Cry bars. This lets Panic + Keystone Cry
        # holders split across separate dangerous packets without double-Crying
        # one cluster. CastSkillIDAndRestoreTarget preserves the team's focus.
        reservation = reserve_best_cry_packet()
        if reservation is not None:
            target_id = int(reservation.target_id)
            did_cast = yield from self.CastSkillIDAndRestoreTarget(
                skill_id=Cry_of_Frustration_ID,
                target_agent_id=target_id,
                log=False,
                aftercast_delay=250,
            )
            if did_cast:
                register_cry_fired(reservation, source="panic")
                self._combat_log(
                    "PANIC_CRY_DANGER_PACKET",
                    target_id=int(target_id),
                    packet_key=int(reservation.packet_key),
                    covered_count=int(len(reservation.covered_casts)),
                    policy="shared_cry_packet_coordination_then_restore_focus",
                )
                return True
            release_cry_reservation(reservation, reason="panic_cry_not_fired")

        # Existing Panic behavior stays intact for ordinary casts inside the
        # shared team packet. Only skip a target that is still covered by a
        # freshly fired/reserved high-value Cry packet.
        anchor, members = self._team_packet()
        if anchor <= 0 or not members:
            return False
        candidates = [int(x) for x in members if not is_enemy_cry_covered(int(x))]
        if not candidates:
            return False
        target_id = self._pick_packet_member(
            candidates,
            require_casting=True,
            prefer_caster=True,
        )
        if target_id <= 0:
            return False
        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Cry_of_Frustration_ID,
            target_agent_id=int(target_id),
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            self._combat_log(
                "PANIC_CRY_TEAM_PACKET",
                target_id=int(target_id),
                anchor_id=int(anchor),
                packet_size=int(len(members)),
                policy="interrupt_inside_shared_packet_respect_cry_coverage",
            )
            return True
        return False

    def _energy_tap_diag(self, reason: str, **fields) -> None:
        try:
            now = int(self._get_game_tick() or 0) if hasattr(self, "_get_game_tick") else 0
        except Exception:
            now = 0
        try:
            last = int(getattr(self, "_last_energy_tap_diag_tick", 0) or 0)
            last_reason = str(getattr(self, "_last_energy_tap_diag_reason", "") or "")
            if reason != last_reason or now <= 0 or now - last >= 2500:
                self._combat_log("PANIC_ENERGY_TAP_DIAG", reason=str(reason), **fields)
                self._last_energy_tap_diag_tick = now
                self._last_energy_tap_diag_reason = str(reason)
        except Exception:
            pass

    def _try_energy_tap_team_packet(self, *, energy_threshold_pct: float = 0.90):
        """Use Energy Tap as the Power-Spike replacement / energy refill.

        Panic and real interrupt opportunities still win. After those, Energy Tap
        may refill at <=90% Energy so it is not needlessly dormant for long periods.
        """
        try:
            equipped = bool(self.IsSkillEquipped(Energy_Tap_ID))
        except Exception:
            equipped = False
        if not equipped:
            self._energy_tap_diag("not_equipped", skill_id=int(Energy_Tap_ID))
            return False
        try:
            can_cast = bool(self.CanCastSkillID(Energy_Tap_ID))
        except Exception:
            can_cast = False
        if not can_cast:
            # Only log this while the skill itself is ready; cooldown is normal.
            try:
                ready = bool(Routines.Checks.Skills.IsSkillIDReady(Energy_Tap_ID))
            except Exception:
                ready = False
            if ready:
                self._energy_tap_diag("ready_but_cannot_cast", skill_id=int(Energy_Tap_ID))
            return False
        try:
            energy_pct = float(Agent.GetEnergy(Player.GetAgentID()))
        except Exception:
            energy_pct = 1.0
        if energy_pct > float(energy_threshold_pct):
            return False

        anchor, members = self._team_packet()
        if anchor <= 0 or not members:
            self._energy_tap_diag(
                "no_team_packet", energy_pct=round(float(energy_pct), 3),
                threshold_pct=round(float(energy_threshold_pct), 3),
            )
            return False
        target_id = self._pick_packet_member(members, require_casting=False, prefer_caster=True)
        if target_id <= 0:
            self._energy_tap_diag(
                "no_target", anchor_id=int(anchor), packet_size=int(len(members)),
                energy_pct=round(float(energy_pct), 3),
            )
            return False
        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Energy_Tap_ID, target_agent_id=int(target_id), log=False, aftercast_delay=250,
        )
        if did_cast:
            self._combat_log(
                "PANIC_ENERGY_TAP", target_id=int(target_id), anchor_id=int(anchor),
                packet_size=int(len(members)), energy_pct=round(float(energy_pct), 3),
                threshold_pct=round(float(energy_threshold_pct), 3),
                policy="after_panic_cry_interrupts_caster_preferred",
            )
            return True
        self._energy_tap_diag(
            "cast_attempt_failed", target_id=int(target_id), anchor_id=int(anchor),
            packet_size=int(len(members)), energy_pct=round(float(energy_pct), 3),
        )
        return False

    def _try_power_drain_team_packet(self, *, energy_threshold_pct: float = 0.70):
        if not self.IsSkillEquipped(Power_Drain_ID) or not self.CanCastSkillID(Power_Drain_ID):
            return False
        try:
            energy_pct = float(Agent.GetEnergy(Player.GetAgentID()))
        except Exception:
            energy_pct = 1.0
        if energy_pct > float(energy_threshold_pct):
            return False

        anchor, members = self._team_packet()
        if anchor <= 0 or not members:
            return False
        target_id = self._pick_packet_member(
            members,
            require_casting=True,
            spell_or_chant_only=True,
            prefer_caster=True,
        )
        if target_id <= 0:
            return False
        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Power_Drain_ID,
            target_agent_id=int(target_id),
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            self._combat_log(
                "PANIC_POWER_DRAIN_ENERGY",
                target_id=int(target_id),
                anchor_id=int(anchor),
                packet_size=int(len(members)),
                energy_pct=round(float(energy_pct), 3),
                threshold_pct=round(float(energy_threshold_pct), 3),
                policy="energy_interrupt_inside_shared_packet",
            )
            return True
        return False

    def _try_unnatural_team_packet(self):
        """Spend Unnatural Signet only as a post-control damage filler.

        The Panic Mesmer is the team's secondary healer/control slot.  This helper
        therefore never competes with healing, Panic, Cry or Power Drain.  When it
        finally gets a free action, prefer a hexed/enchanted member of the shared
        team packet so Unnatural produces its adjacent AoE instead of wandering to
        an unrelated target.  A packet member/anchor fallback is still allowed so
        the filler does not idle in cleanup.
        """
        if not self.IsSkillEquipped(Unnatural_Signet_ID):
            return False
        if not self.CanCastSkillID(Unnatural_Signet_ID):
            return False

        anchor, members = self._team_packet()
        candidates = [int(x) for x in (members or []) if int(x or 0) > 0]
        if int(anchor or 0) > 0 and int(anchor) not in candidates:
            candidates.insert(0, int(anchor))
        if not candidates:
            try:
                nearest = int(Routines.Agents.GetNearestEnemy(Range.Spellcast.value) or 0)
            except Exception:
                nearest = 0
            if nearest > 0:
                candidates = [nearest]

        if not candidates:
            return False

        def _valid(aid: int) -> bool:
            try:
                return bool(Agent.IsValid(aid) and Agent.IsAlive(aid))
            except Exception:
                return False

        candidates = [aid for aid in candidates if _valid(aid)]
        if not candidates:
            return False

        # AoE condition first; then canonical anchor/packet order.
        aoe = []
        for aid in candidates:
            try:
                if Agent.IsHexed(aid) or Agent.IsEnchanted(aid):
                    aoe.append(aid)
            except Exception:
                pass
        target = int((aoe or candidates)[0])
        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Unnatural_Signet_ID,
            target_agent_id=target,
            log=False,
            aftercast_delay=200,
        )
        if did_cast:
            self._combat_log(
                "PANIC_UNNATURAL_FILLER",
                target_id=int(target),
                packet_anchor=int(anchor or 0),
                packet_size=int(len(candidates)),
                aoe_condition=bool(target in aoe),
                policy="heal_control_first_then_packet_unnatural",
            )
            return True
        return False

    def _run_local_skill_logic(self):
        if not Routines.Checks.Skills.CanCast():
            yield from Routines.Yield.wait(100)
            return False

        snapshot = self._get_bar_snapshot()

        # Large-packet setup: Recuperation first, then Panic as the offensive opener.
        if (yield from self._try_recuperation_pre_fight()):
            return True

        # Hochnäsigkeit / Air of Superiority is a setup snowball buff, like on
        # the Keystone Mesmers.  Use it around contact when equipped; the shared
        # PvE helper handles effect/recharge gating, so it cannot be spammed.
        if (snapshot.in_aggro or self.IsCloseToAggro()) and self.IsSkillEquipped(Air_of_Superiority_ID):
            if (yield from self.skills.Any.PvE.Air_of_Superiority()):
                self._combat_log("PANIC_AIR_OF_SUPERIORITY_SETUP", policy="pre_burst_snowball")
                return True

        if (yield from self.skills.Any.NoAttribute.Breath_of_the_Great_Dwarf()):
            return True

        # Emergency direct heal first. Spirit Light is the fastest way to stop
        # an ally from dropping while the Panic bar is busy with interrupts.
        if (yield from self._try_spirit_light_heal(health_threshold=0.30)):
            return True

        # Keep MBaS on HeroAI-style healing/cleanse behavior, but execute it
        # inside the local Panic loop so the busy interrupt rotation cannot
        # starve team healing.
        if (yield from self._try_mend_body_and_soul_heroai()):
            return True

        # Normal Spirit Light pass. This is deliberately below MBaS so MBaS can
        # clean conditions while healing, but still above offensive Panic logic.
        if (yield from self._try_spirit_light_heal(health_threshold=0.68)):
            return True

        if self.IsSkillEquipped(Flesh_of_My_Flesh_ID):
            dead_ally_id = Routines.Agents.GetDeadAlly(Range.Spellcast.value) or 0
            if dead_ally_id and (yield from self.CastSkillIDAndRestoreTarget(
                skill_id=Flesh_of_My_Flesh_ID,
                target_agent_id=dead_ally_id,
                log=False,
                aftercast_delay=250,
            )):
                return True

        if self.IsSkillEquipped(Ebon_Battle_Standard_of_Courage_ID) and (yield from self.skills.Any.NoAttribute.Ebon_Battle_Standard_of_Courage()):
            return True

        if self.IsSkillEquipped(Ebon_Battle_Standard_of_Honor_ID) and (yield from self.skills.Any.NoAttribute.Ebon_Battle_Standard_of_Honor()):
            return True

        if not snapshot.in_aggro:
            return False

        # Emergency energy floor is the only thing allowed to precede Panic.
        if snapshot.enemy_casting_spell_or_chant and (yield from self._try_power_drain_team_packet(energy_threshold_pct=0.30)):
            return True

        if (yield from self.skills.Mesmer.DominationMagic.Shatter_Hex(min_priority=HexRemovalPriority.HIGH)):
            return True

        if snapshot.enemy_in_spellcast and (yield from self.skills.Any.PvE.Ebon_Vanguard_Assassin_Support()):
            return True
        
        if self.IsSkillEquipped(Tryptophan_Signet_ID) and (yield from self.skills.Any.PvE.Tryptophan_Signet()):
            return True

        # Core control rotation: Panic -> Cry of Frustration -> Power Drain.
        # Panic is retried whenever recharge is ready, refreshing/maintaining the
        # hex on the current packet instead of being treated as a one-shot opener.
        if snapshot.enemy_in_spellcast and (yield from self._try_panic_team_packet()):
            return True

        if snapshot.enemy_casting and (yield from self._try_cry_of_frustration_team_packet()):
            return True

        if snapshot.enemy_casting_spell_or_chant and (yield from self._try_power_drain_team_packet()):
            return True

        if snapshot.player_energy_pct >= 0.50 and (yield from self.skills.Mesmer.DominationMagic.Shatter_Hex(min_priority=HexRemovalPriority.MEDIUM)):
            return True

        if snapshot.enemy_casting_spell and (yield from self.skills.Mesmer.DominationMagic.Mistrust()):
            return True

        if snapshot.enemy_casting and (yield from self.skills.Mesmer.DominationMagic.Overload()):
            return True

        if snapshot.enemy_casting and (yield from self.skills.Any.PvE.Cry_of_Pain(require_mesmer_hex=True)):
            return True

        # Pure filler: only after healing and the complete Panic/Cry/Power-Drain
        # control lane had first refusal.
        if snapshot.enemy_in_spellcast and (yield from self._try_unnatural_team_packet()):
            return True

        if snapshot.enemy_in_spellcast and (yield from self.skills.Any.PvE.Cry_of_Pain()):
            return True

        if snapshot.player_energy_pct >= 0.70 and (yield from self.skills.Mesmer.DominationMagic.Shatter_Hex()):
            return True

        yield
