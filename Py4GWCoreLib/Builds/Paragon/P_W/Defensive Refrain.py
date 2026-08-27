from Py4GWCoreLib import Profession
from Py4GWCoreLib import Range
from Py4GWCoreLib import Routines
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build
from Py4GWCoreLib import BuildMgr
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Skills import SkillsTemplate
from Py4GWCoreLib.Builds.Skills.AoEDangerPrediction import (
    avoid_active_aoe_if_needed,
    is_aoe_escape_safe_hold_active,
    refresh_aoe_danger_zones,
)
from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import (
    get_team_cluster_anchor, get_team_cluster_members, is_support_or_caster,
)

Heroic_Refrain_ID = Skill.GetID("Heroic_Refrain")
Theyre_on_Fire_ID = Skill.GetID("Theyre_on_Fire")
Anthem_of_Flame_ID = Skill.GetID("Anthem_of_Flame")
Hasty_Refrain_ID = Skill.GetID("Hasty_Refrain")
Aggressive_Refrain_ID = Skill.GetID("Aggressive_Refrain")
Stand_Your_Ground_ID = Skill.GetID("Stand_Your_Ground")
Go_for_the_Eyes_ID = Skill.GetID("Go_for_the_Eyes")
For_Great_Justice_ID = Skill.GetID("For_Great_Justice")
Theres_Nothing_to_Fear_ID = Skill.GetID("Theres_Nothing_to_Fear")
Save_Yourselves_luxon_ID = Skill.GetID("Save_Yourselves_luxon")
Save_Yourselves_kurzick_ID = Skill.GetID("Save_Yourselves_kurzick")
Never_Surrender_ID = Skill.GetID("Never_Surrender")
Blazing_Finale_ID = Skill.GetID("Blazing_Finale")
Purifying_Finale_ID = Skill.GetID("Purifying_Finale")
Bladeturn_Refrain_ID = Skill.GetID("Bladeturn_Refrain")
Mending_Refrain_ID = Skill.GetID("Mending_Refrain")
Ebon_Vanguard_Assassin_Support_ID = Skill.GetID("Ebon_Vanguard_Assassin_Support")
Ebon_Battle_Standard_of_Wisdom_ID = Skill.GetID("Ebon_Battle_Standard_of_Wisdom")
Protectors_Defense_ID = Skill.GetID("Protectors_Defense")
Cant_Touch_This_ID = Skill.GetID("Cant_Touch_This")
Make_Your_Time_ID = Skill.GetID("Make_Your_Time")
Angelic_Protection_ID = Skill.GetID("Angelic_Protection")
Signet_of_Synergy_ID = Skill.GetID("Signet_of_Synergy")
Glowing_Signet_ID = Skill.GetID("Glowing_Signet")
Burning_ID = Skill.GetID("Burning")
Great_Dwarf_Weapon_ID = Skill.GetID("Great_Dwarf_Weapon")
Splinter_Weapon_ID = Skill.GetID("Splinter_Weapon")

# The HR Paragon follows the exact shared RoJway packet for spear auto-attacks.
# TeamCombatFocus itself owns cluster selection, priority cleanup and low-health
# continuation; no independent execution or nearest-enemy override is allowed.
POWER_CLUSTER_MIN_ENEMIES = 2
POWER_CLUSTER_RADIUS = Range.Adjacent.value
POWER_CLUSTER_FILTER_RANGE = Range.Spellcast.value
SAFE_HOLD_SPEAR_ATTACK_RANGE = max(0.0, float(Range.Spear.value) - 90.0)
GLOWING_SIGNET_ENERGY_THRESHOLD = 0.70

_SAFE_DANGER_CAST_SKILL_NAMES = (
    # Elementalist / AoE pressure
    "Meteor_Shower", "Savannah_Heat", "Searing_Heat", "Rodgorts_Invocation",
    "Rodgort's_Invocation", "Deep_Freeze", "Maelstrom", "Earthquake",
    "Churning_Earth", "Sandstorm", "Fire_Storm", "Eruption",
    "Invoke_Lightning", "Chain_Lightning", "Obsidian_Flame",
    # Mesmer shutdown / pressure
    "Panic", "Energy_Surge", "Mistrust", "Cry_of_Frustration",
    "Visions_of_Regret", "Backfire", "Empathy", "Shame", "Diversion",
    # Necromancer pressure
    "Spiteful_Spirit", "Spoil_Victor", "Mark_of_Pain", "Barbs",
    "Feast_of_Corruption", "Rising_Bile", "Putrid_Explosion",
    # Monk / Ritualist control, prot, heal, resurrection
    "Ray_of_Judgment", "Signet_of_Judgment", "Shield_of_Judgment",
    "Aegis", "Protective_Spirit", "Spirit_Bond", "Word_of_Healing",
    "Heal_Area", "Heavens_Delight", "Divine_Healing",
    "Restore_Life", "Resurrection_Chant", "Flesh_of_My_Flesh",
    "Death_Pact_Signet", "Renew_Life",
)

_SAFE_DANGER_CAST_SKILL_IDS = frozenset(
    int(skill_id)
    for skill_id in (Skill.GetID(name) for name in _SAFE_DANGER_CAST_SKILL_NAMES)
    if int(skill_id or 0) > 0
)


class Paragon_Refrain(BuildMgr):
    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Defensive Refrain - RoJ Team Focus Phase 3.10 Purifying Support",
            required_primary=Profession.Paragon,
            required_secondary=Profession.Warrior,
            template_code="OQGkUNlnpiy0ZNQYPWNm72G4VhoH",
            required_skills=[
                Heroic_Refrain_ID,
                Theyre_on_Fire_ID,
                Theres_Nothing_to_Fear_ID,
            ],
            optional_skills=[
                Anthem_of_Flame_ID,
                Save_Yourselves_luxon_ID,
                Save_Yourselves_kurzick_ID,
                Hasty_Refrain_ID,
                Never_Surrender_ID,
                Aggressive_Refrain_ID,
                Stand_Your_Ground_ID,
                Go_for_the_Eyes_ID,
                For_Great_Justice_ID,
                Blazing_Finale_ID,
                Purifying_Finale_ID,
                Bladeturn_Refrain_ID,
                Mending_Refrain_ID,
                Ebon_Vanguard_Assassin_Support_ID,
                Ebon_Battle_Standard_of_Wisdom_ID,
                Protectors_Defense_ID,
                Cant_Touch_This_ID,
                Make_Your_Time_ID,
                Angelic_Protection_ID,
                Signet_of_Synergy_ID,
                Glowing_Signet_ID,
            ],
        )
        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skills: SkillsTemplate = SkillsTemplate(self)
        self._last_gdw_spear_target: int = 0

    def _distance_to_player(self, target_agent_id: int) -> float:
        try:
            from Py4GWCoreLib.Py4GWcorelib import Utils
            return float(Utils.Distance(Player.GetXY(), Agent.GetXY(target_agent_id)))
        except Exception:
            return 999999.0

    def _is_valid_power_cluster_enemy(self, target_agent_id: int) -> bool:
        try:
            target_agent_id = int(target_agent_id or 0)
            if target_agent_id <= 0:
                return False
            if not Agent.IsValid(target_agent_id) or not Agent.IsAlive(target_agent_id):
                return False
            return self._distance_to_player(target_agent_id) <= float(POWER_CLUSTER_FILTER_RANGE)
        except Exception:
            return False

    def _count_adjacent_enemies(self, target_agent_id: int) -> int:
        if target_agent_id <= 0:
            return 0
        try:
            from Py4GWCoreLib import AgentArray

            target_xy = Agent.GetXY(target_agent_id)
            enemies = AgentArray.GetEnemyArray()
            enemies = AgentArray.Filter.ByDistance(enemies, target_xy, Range.Adjacent.value)
            enemies = AgentArray.Filter.ByCondition(
                enemies,
                lambda agent_id: Agent.IsValid(agent_id) and Agent.IsAlive(agent_id),
            )
            return int(len(enemies))
        except Exception:
            try:
                return int(Routines.Targeting.CountNearbyEnemies(target_agent_id, Range.Adjacent.value) or 0)
            except Exception:
                return 0

    def _get_power_cluster_anchor(self, *, minimum_enemies: int = POWER_CLUSTER_MIN_ENEMIES) -> int:
        """Use the one authoritative RoJway packet/cleanup resolver."""
        try:
            from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import get_team_cluster_anchor
            return int(get_team_cluster_anchor(
                filter_range=POWER_CLUSTER_FILTER_RANGE,
                minimum_enemies=int(minimum_enemies),
                consumer_role="hr_paragon",
            ) or 0)
        except Exception:
            return 0


    def _get_power_cluster_members(self, anchor_agent_id: int) -> list[int]:
        if not self._is_valid_power_cluster_enemy(anchor_agent_id):
            return []
        try:
            members = [
                int(agent_id)
                for agent_id in get_team_cluster_members(
                    int(anchor_agent_id),
                    radius=POWER_CLUSTER_RADIUS,
                    filter_range=POWER_CLUSTER_FILTER_RANGE,
                )
                if self._is_valid_power_cluster_enemy(int(agent_id))
            ]
        except Exception:
            members = [int(anchor_agent_id)]

        if int(anchor_agent_id) not in members:
            members.append(int(anchor_agent_id))
        return sorted(set(
            agent_id for agent_id in members
            if self._is_valid_power_cluster_enemy(agent_id)
        ))

    @staticmethod
    def _get_enemy_professions_safe(agent_id: int) -> tuple[int, int]:
        try:
            if agent_id <= 0 or not Agent.IsValid(agent_id) or not Agent.IsAlive(agent_id):
                return (0, 0)
            primary, secondary = Agent.GetProfessions(agent_id)
            primary_id = int(getattr(primary, 'value', primary) or 0)
            secondary_id = int(getattr(secondary, 'value', secondary) or 0)
            return (primary_id, secondary_id)
        except Exception:
            return (0, 0)

    def _is_monk_or_ritualist_enemy(self, agent_id: int) -> bool:
        primary, secondary = self._get_enemy_professions_safe(agent_id)
        try:
            monk_id = int(getattr(Profession.Monk, 'value', Profession.Monk))
            ritualist_id = int(getattr(Profession.Ritualist, 'value', Profession.Ritualist))
        except Exception:
            return False
        return primary in (monk_id, ritualist_id) or secondary in (monk_id, ritualist_id)

    @staticmethod
    def _is_knocked_down_safe(agent_id: int) -> bool:
        try:
            return bool(Routines.Checks.Agents.IsKnockedDown(agent_id))
        except Exception:
            return False

    @staticmethod
    def _get_safe_casting_skill_id(target_agent_id: int) -> int:
        try:
            target_agent_id = int(target_agent_id or 0)
            if target_agent_id <= 0:
                return 0
            if not Agent.IsValid(target_agent_id) or not Agent.IsAlive(target_agent_id):
                return 0
            if not Agent.IsCasting(target_agent_id):
                return 0
            return int(Agent.GetCastingSkillID(target_agent_id) or 0)
        except Exception:
            return 0

    def _is_safe_dangerous_cast(self, target_agent_id: int) -> bool:
        return self._get_safe_casting_skill_id(target_agent_id) in _SAFE_DANGER_CAST_SKILL_IDS

    def _has_splinter_weapon(self) -> bool:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            return False
        try:
            return bool(Routines.Checks.Agents.HasEffect(player_id, Splinter_Weapon_ID, exact_weapon_spell=True))
        except Exception:
            try:
                return bool(Agent.IsWeaponSpelled(player_id))
            except Exception:
                return False

    def _has_great_dwarf_weapon(self) -> bool:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0 or int(Great_Dwarf_Weapon_ID or 0) <= 0:
            return False
        try:
            if Routines.Checks.Effects.HasBuff(player_id, Great_Dwarf_Weapon_ID):
                return True
        except Exception:
            pass
        try:
            if Routines.Checks.Agents.HasEffect(player_id, Great_Dwarf_Weapon_ID):
                return True
        except Exception:
            pass
        return False

    def _pick_cluster_spear_target(self) -> int:
        anchor = int(self._get_power_cluster_anchor() or 0)
        if anchor <= 0 or not self._is_valid_power_cluster_enemy(anchor):
            return 0

        members = self._get_power_cluster_members(anchor)
        if not members:
            return 0
        if len(members) <= 1 or not self._has_splinter_weapon():
            return int(anchor)

        member_set = set(int(agent_id) for agent_id in members)

        def neighbours(agent_id: int) -> list[int]:
            try:
                from Py4GWCoreLib import AgentArray
                arr = AgentArray.GetEnemyArray()
                arr = AgentArray.Filter.ByDistance(arr, Agent.GetXY(agent_id), Range.Adjacent.value)
                return [int(eid) for eid in arr or [] if int(eid) in member_set and int(eid) != int(agent_id) and Agent.IsValid(eid) and Agent.IsAlive(eid)]
            except Exception:
                return []

        def rank(agent_id: int):
            near = neighbours(agent_id)
            priority_splashes = sum(1 for eid in near if is_support_or_caster(eid) or self._is_safe_dangerous_cast(eid))
            direct_priority_penalty = 1 if (is_support_or_caster(agent_id) or self._is_safe_dangerous_cast(agent_id)) else 0
            anchor_tie_break = 0 if int(agent_id) == int(anchor) else 1
            return (-len(near), -priority_splashes, direct_priority_penalty, anchor_tie_break, self._distance_to_player(agent_id), int(agent_id))

        members.sort(key=rank)
        return int(members[0])

    def _auto_attack_cluster_spear_target(self, *, stationary_only: bool = False):
        if False:
            yield

        try:
            target_agent_id = self._pick_cluster_spear_target()
        except Exception:
            target_agent_id = 0
        if not target_agent_id or not self._is_valid_power_cluster_enemy(target_agent_id):
            return False

        try:
            player_id = Player.GetAgentID()
            if not self.CanProcess() or self._is_local_cast_pending() or Agent.IsHoldingItem(player_id):
                return False

            # Never let an automatic spear re-issue fight the player's keyboard
            # or mouse movement.  Once movement stops, normal auto-attacking
            # resumes on the next eligible tick.
            try:
                if Agent.IsMoving(player_id):
                    return False
            except Exception:
                pass

            if stationary_only and self._distance_to_player(target_agent_id) > float(SAFE_HOLD_SPEAR_ATTACK_RANGE):
                return False

            self._refresh_auto_attack_timing()
            if not self._need_auto_attack_reissue():
                return False

            if Player.GetTargetID() != target_agent_id:
                yield from Routines.Yield.Agents.ChangeTarget(target_agent_id)

            Player.Interact(target_agent_id, False)
            try:
                if self._has_splinter_weapon():
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    from Py4GWCoreLib import AgentArray

                    anchor = int(self._get_power_cluster_anchor() or 0)
                    members = self._get_power_cluster_members(anchor) if anchor > 0 else []
                    member_set = set(int(eid) for eid in members)

                    adjacent = 0
                    priority_adjacent = 0
                    arr = AgentArray.GetEnemyArray()
                    arr = AgentArray.Filter.ByDistance(
                        arr,
                        Agent.GetXY(target_agent_id),
                        Range.Adjacent.value,
                    )
                    for enemy_id in arr or []:
                        enemy_id = int(enemy_id or 0)
                        if enemy_id <= 0 or enemy_id == int(target_agent_id):
                            continue
                        if member_set and enemy_id not in member_set:
                            continue
                        if not Agent.IsValid(enemy_id) or not Agent.IsAlive(enemy_id):
                            continue
                        adjacent += 1
                        if is_support_or_caster(enemy_id) or self._is_safe_dangerous_cast(enemy_id):
                            priority_adjacent += 1

                    CombatDebug.log_event(
                        "SPLINTER_SPEAR_ATTACK",
                        target_id=int(target_agent_id),
                        team_anchor=int(anchor),
                        packet_size=int(len(members)),
                        adjacent_targets=int(adjacent),
                        priority_adjacent_targets=int(priority_adjacent),
                        cleanup_focus=bool(len(members) <= 1),
                        policy="phase3_1_exact_team_packet_splinter_geometry_no_fallback",
                    )
            except Exception:
                pass
            self.current_target_id = int(target_agent_id)
            self._last_gdw_spear_target = int(target_agent_id)
            self._refresh_auto_attack_timing()
            self._auto_attack_timer.SetThrottleTime(max(0, self._auto_attack_time))
            self._auto_attack_timer.Reset()
            return True
        except Exception:
            return False

    def _cast_evas_on_team_focus(self):
        """Keep the Paragon's foe-targeted summon on RoJ cluster/cleanup."""
        if False:
            yield
        if not self.IsSkillEquipped(Ebon_Vanguard_Assassin_Support_ID):
            return False
        if not self.CanCastSkillID(Ebon_Vanguard_Assassin_Support_ID):
            return False

        anchor = int(self._get_power_cluster_anchor() or 0)
        if anchor <= 0 or not self._is_valid_power_cluster_enemy(anchor):
            return False
        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Ebon_Vanguard_Assassin_Support_ID,
            target_agent_id=int(anchor),
            extra_condition=lambda: int(self._get_power_cluster_anchor() or 0) == int(anchor),
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug

                CombatDebug.log_event(
                    "HR_PARA_EVAS_TEAM_FOCUS",
                    target_id=int(anchor),
                    policy="phase3_1_exact_cluster_and_cleanup_no_local_fallback",
                )
            except Exception:
                pass
            return True
        return False

    def _energy_fraction(self) -> float:
        try:
            return float(Agent.GetEnergy(Player.GetAgentID()))
        except Exception:
            return 0.0

    def _core_refrain_setup_complete(self) -> bool:
        """True only when the mandatory HR core no longer needs immediate work.

        Heroic Refrain helper itself handles self bootstrap and ally spreading.
        If it returns False in the rotation pass, there is no immediately valid
        HR target left to service. They're on Fire is maintained separately.
        """
        try:
            if self.IsSkillEquipped(Theyre_on_Fire_ID):
                if not Routines.Checks.Agents.HasEffect(Player.GetAgentID(), Theyre_on_Fire_ID):
                    return False
        except Exception:
            return False
        return True

    def _cast_optional_refrain_with_energy_gate(self):
        """Spread optional refrains only after HR core and with >=50% energy.

        Re-check energy every pass. This naturally spaces echo application:
        one cast -> return -> next pass checks energy again.
        """
        if self._energy_fraction() < 0.50:
            return False
        if not self._core_refrain_setup_complete():
            return False

        if self.IsSkillEquipped(Bladeturn_Refrain_ID):
            if (yield from self.skills.Paragon.Command.Bladeturn_Refrain()):
                return True

        if self.IsSkillEquipped(Mending_Refrain_ID):
            if (yield from self.skills.Paragon.Motivation.Mending_Refrain()):
                return True

        return False

    def _is_valid_signet_of_synergy_target(
        self,
        target_agent_id: int,
        *,
        health_threshold: float,
    ) -> bool:
        player_agent_id = int(Player.GetAgentID() or 0)
        target_agent_id = int(target_agent_id or 0)
        if target_agent_id <= 0 or target_agent_id == player_agent_id:
            return False
        try:
            return bool(
                Agent.IsValid(target_agent_id)
                and Agent.IsAlive(target_agent_id)
                and Routines.Party.IsPartyMember(target_agent_id)
                and float(Agent.GetHealth(target_agent_id)) < float(health_threshold)
            )
        except Exception:
            return False

    def _cast_signet_of_synergy(self):
        """Use the free optional heal without delaying critical protection."""
        if not self.IsSkillEquipped(Signet_of_Synergy_ID):
            return False
        if not self.IsInAggro() or not self.CanCastSkillID(Signet_of_Synergy_ID):
            return False

        # The team already has dedicated Monks. A 72% threshold makes this a
        # useful free stabiliser rather than a cast-time tax on every small HP
        # fluctuation. Angelic Protection remains above it for real emergencies.
        health_threshold = 0.72
        target_agent_id = int(
            self.ResolveRankedPartyAllyTarget(
                Signet_of_Synergy_ID,
                validator=lambda agent_id: self._is_valid_signet_of_synergy_target(
                    int(agent_id),
                    health_threshold=health_threshold,
                ),
                rank_key=lambda agent_id: (
                    float(Agent.GetHealth(int(agent_id))),
                    self._distance_to_player(int(agent_id)),
                    int(agent_id),
                ),
            )
            or 0
        )
        if target_agent_id <= 0:
            return False

        player_agent_id = int(Player.GetAgentID() or 0)
        try:
            self_unenchanted = not bool(
                Routines.Checks.Agents.IsEnchanted(player_agent_id)
            )
        except Exception:
            self_unenchanted = False
        target_health_before = float(Agent.GetHealth(target_agent_id))
        self_health_before = float(Agent.GetHealth(player_agent_id))

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Signet_of_Synergy_ID,
            target_agent_id=int(target_agent_id),
            extra_condition=lambda: self._is_valid_signet_of_synergy_target(
                int(target_agent_id),
                health_threshold=health_threshold,
            ),
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug

                CombatDebug.log_event(
                    "HR_SIGNET_OF_SYNERGY_CAST",
                    target_id=int(target_agent_id),
                    target_health=f"{target_health_before:.4f}",
                    self_health=f"{self_health_before:.4f}",
                    self_heal_eligible=bool(self_unenchanted),
                    policy="lowest_party_ally_below_72_after_angelic_emergency",
                )
            except Exception:
                pass
            return True
        return False

    def _is_valid_glowing_signet_target(self, target_agent_id: int) -> bool:
        """Only accept a live, in-range, burning enemy from team focus."""
        target_agent_id = int(target_agent_id or 0)
        if not self._is_valid_power_cluster_enemy(target_agent_id):
            return False
        if int(Burning_ID or 0) <= 0:
            return False
        try:
            return bool(
                Routines.Checks.Agents.HasEffect(
                    int(target_agent_id),
                    int(Burning_ID),
                )
            )
        except Exception:
            return False

    def _cast_glowing_signet_for_energy(self):
        """Recover energy at <=70% without peeling away from team focus."""
        if not self.IsSkillEquipped(Glowing_Signet_ID):
            return False
        if not self.IsInAggro() or not self.CanCastSkillID(Glowing_Signet_ID):
            return False

        energy_before = float(self._energy_fraction())
        if energy_before > float(GLOWING_SIGNET_ENERGY_THRESHOLD):
            return False

        anchor = int(self._get_power_cluster_anchor() or 0)
        if anchor <= 0:
            return False
        members = self._get_power_cluster_members(anchor)
        burning_members = [
            int(enemy_id)
            for enemy_id in members
            if self._is_valid_glowing_signet_target(int(enemy_id))
        ]
        if not burning_members:
            return False

        # Prefer the exact team anchor; otherwise use the closest burning
        # member of that same packet. Never fall back to an unrelated enemy.
        burning_members.sort(
            key=lambda enemy_id: (
                0 if int(enemy_id) == int(anchor) else 1,
                self._distance_to_player(int(enemy_id)),
                int(enemy_id),
            )
        )
        target_agent_id = int(burning_members[0])

        def _still_valid() -> bool:
            return bool(
                self._energy_fraction() <= float(GLOWING_SIGNET_ENERGY_THRESHOLD)
                and int(self._get_power_cluster_anchor() or 0) == int(anchor)
                and self._is_valid_glowing_signet_target(int(target_agent_id))
            )

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Glowing_Signet_ID,
            target_agent_id=int(target_agent_id),
            extra_condition=_still_valid,
            log=False,
            aftercast_delay=180,
        )
        if did_cast:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug

                CombatDebug.log_event(
                    "HR_GLOWING_SIGNET_CAST",
                    target_id=int(target_agent_id),
                    team_anchor=int(anchor),
                    packet_size=int(len(members)),
                    energy_before=f"{energy_before:.4f}",
                    threshold=f"{GLOWING_SIGNET_ENERGY_THRESHOLD:.2f}",
                    policy="below_70_burning_authoritative_packet_energy_recovery",
                )
            except Exception:
                pass
            return True
        return False

    def _cast_go_for_the_eyes_energy_engine(self):
        """Use the optional adrenaline shout as a free Leadership battery."""
        if not self.IsSkillEquipped(Go_for_the_Eyes_ID):
            return False
        energy_before = float(self._energy_fraction())
        did_cast = yield from self.skills.Paragon.Command.Go_for_the_Eyes()
        if did_cast:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug

                CombatDebug.log_event(
                    "HR_GO_FOR_THE_EYES_CAST",
                    energy_before=f"{energy_before:.4f}",
                    policy="optional_adrenaline_shout_leadership_energy_engine",
                )
            except Exception:
                pass
            return True
        return False

    def _is_valid_purifying_finale_target(self, target_agent_id: int) -> bool:
        """Only protect a conditioned real party member inside shout range."""
        target_agent_id = int(target_agent_id or 0)
        if target_agent_id <= 0:
            return False
        try:
            return bool(
                Agent.IsValid(target_agent_id)
                and Agent.IsAlive(target_agent_id)
                and Routines.Party.IsPartyMember(target_agent_id)
                and self._distance_to_player(target_agent_id) <= float(Range.Earshot.value)
                and Routines.Checks.Agents.IsConditioned(target_agent_id)
                and not Routines.Checks.Agents.HasEffect(
                    target_agent_id,
                    Purifying_Finale_ID,
                )
            )
        except Exception:
            return False

    def _cast_purifying_finale_on_conditioned_ally(self):
        """Apply the finale on demand, never as a full-party pre-cast."""
        if not self.IsSkillEquipped(Purifying_Finale_ID):
            return False
        if not self.IsInAggro() or not self.CanCastSkillID(Purifying_Finale_ID):
            return False

        target_agent_id = int(
            self.ResolveRankedPartyAllyTarget(
                Purifying_Finale_ID,
                validator=lambda agent_id: self._is_valid_purifying_finale_target(
                    int(agent_id)
                ),
                rank_key=lambda agent_id: (
                    float(Agent.GetHealth(int(agent_id))),
                    -float(self.GetPartyHealthDelta(int(agent_id))),
                    self._distance_to_player(int(agent_id)),
                    int(agent_id),
                ),
            )
            or 0
        )
        if target_agent_id <= 0:
            return False

        target_health_before = float(Agent.GetHealth(target_agent_id))
        energy_before = float(self._energy_fraction())
        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Purifying_Finale_ID,
            target_agent_id=int(target_agent_id),
            extra_condition=lambda: self._is_valid_purifying_finale_target(
                int(target_agent_id)
            ),
            log=False,
            aftercast_delay=180,
        )
        if did_cast:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug

                CombatDebug.log_event(
                    "HR_PURIFYING_FINALE_CAST",
                    target_id=int(target_agent_id),
                    target_health=f"{target_health_before:.4f}",
                    energy_before=f"{energy_before:.4f}",
                    policy="conditioned_party_member_lowest_health_no_pet_no_precast",
                )
            except Exception:
                pass
            return True
        return False

    def _run_local_skill_logic(self):
        refresh_aoe_danger_zones()
        # Global movement override: movement must be evaluated before
        # CanCast/emergency rotations.  This lets knocked-down or interrupted
        # accounts receive a fresh escape command as soon as they can move.
        if avoid_active_aoe_if_needed(role="hr_paragon", allow_actions_at_safe_hold=True):
            return True

        if not Routines.Checks.Skills.CanCast():
            yield from Routines.Yield.wait(100)
            return False


        safe_aoe_hold = is_aoe_escape_safe_hold_active(role="hr_paragon")
        # At the safe hold point only, keep throwing spears at enemies already
        # in weapon range. In normal combat the attack remains the final action
        # so it cannot run ahead of HR/support maintenance.
        if safe_aoe_hold:
            yield from self._auto_attack_cluster_spear_target(stationary_only=True)

        if self.IsSkillEquipped(Heroic_Refrain_ID) and (yield from self.skills.Paragon.Leadership.Heroic_Refrain()):
            return True

        if self.IsSkillEquipped(Theyre_on_Fire_ID) and (yield from self.skills.Paragon.Leadership.Theyre_on_Fire()):
            return True

        if self.IsSkillEquipped(Anthem_of_Flame_ID) and (yield from self.skills.Paragon.Leadership.Anthem_of_Flame()):
            return True

        # Optional echo/refrain spreading is deliberately delayed until the
        # mandatory HR core is serviced and energy has recovered to >=50%.
        if (yield from self._cast_optional_refrain_with_energy_gate()):
            return True

        if not self.IsInAggro():
            return False

        if self.IsSkillEquipped(Angelic_Protection_ID) and (
            yield from self.skills.Paragon.Leadership.Angelic_Protection(
                health_threshold=0.30
            )
        ):
            return True

        if (yield from self._cast_signet_of_synergy()):
            return True

        if self.IsSkillEquipped(Theres_Nothing_to_Fear_ID) and (
            yield from self.skills.Any.NoAttribute.Theres_Nothing_to_Fear()
        ):
            return True

        # Both energy tools stay behind the mandatory HR/defensive core.
        # The free adrenaline shout gets first refusal; Glowing Signet then
        # recovers energy only if the Para is still at or below 70%.
        if (yield from self._cast_go_for_the_eyes_energy_engine()):
            return True

        if (yield from self._cast_glowing_signet_for_energy()):
            return True

        if self.IsSkillEquipped(Aggressive_Refrain_ID) and (yield from self.skills.Paragon.Leadership.Aggressive_Refrain()):
            return True

        if self.IsSkillEquipped(For_Great_Justice_ID) and (yield from self.skills.Warrior.NoAttribute.For_Great_Justice()):
            return True

        if self.IsSkillEquipped(Make_Your_Time_ID) and (yield from self.skills.Paragon.Leadership.Make_Your_Time()):
            return True

        if self.IsSkillEquipped(Save_Yourselves_luxon_ID) and (yield from self.skills.Any.NoAttribute.Save_Yourselves_luxon()):
            return True

        if self.IsSkillEquipped(Save_Yourselves_kurzick_ID) and (yield from self.skills.Any.NoAttribute.Save_Yourselves_kurzick()):
            return True

        if self.IsSkillEquipped(Stand_Your_Ground_ID) and (yield from self.skills.Paragon.Command.Stand_Your_Ground()):
            return True

        if self.IsSkillEquipped(Cant_Touch_This_ID) and (yield from self.skills.Paragon.Command.Cant_Touch_This()):
            return True

        if self.IsSkillEquipped(Hasty_Refrain_ID) and (yield from self.skills.Paragon.Motivation.Hasty_Refrain()):
            return True

        if self.IsSkillEquipped(Never_Surrender_ID) and (yield from self.skills.Paragon.Motivation.Never_Surrender()):
            return True

        if self.IsSkillEquipped(Blazing_Finale_ID) and (yield from self.skills.Paragon.Motivation.Blazing_Finale()):
            return True

        if self.IsSkillEquipped(Protectors_Defense_ID) and (yield from self.skills.Warrior.NoAttribute.Protectors_Defense()):
            return True

        if (yield from self._cast_evas_on_team_focus()):
            return True

        if self.IsSkillEquipped(Ebon_Battle_Standard_of_Wisdom_ID) and (yield from self.skills.Any.NoAttribute.Ebon_Battle_Standard_of_Wisdom()):
            return True

        # Purifying Finale is demand-only filler behind the RoJ recharge
        # standard. It never delays the standard at a fresh combat opening and
        # never spreads across healthy allies in advance.
        if (yield from self._cast_purifying_finale_on_conditioned_ally()):
            return True

        if (yield from self._auto_attack_cluster_spear_target(
            stationary_only=bool(safe_aoe_hold)
        )):
            return True

        # Every declared Para skill was handled above. Mark an otherwise idle
        # combat pass as owned so the generic fallback cannot retarget the
        # spear to a called/nearest enemy outside TeamCombatFocus.
        return True
