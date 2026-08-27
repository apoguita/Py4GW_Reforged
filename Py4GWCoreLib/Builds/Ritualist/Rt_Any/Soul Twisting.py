from dataclasses import dataclass

from Py4GWCoreLib import Agent, Player, Profession, Routines, BuildMgr, AgentArray, GLOBAL_CACHE, Range, SpiritModelID
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI as HeroAIBuild
from Py4GWCoreLib.Builds.Skills import HexRemovalPriority, SkillsTemplate
from Py4GWCoreLib.Builds.Skills.AoEDangerPrediction import (
    avoid_active_aoe_if_needed,
    get_player_active_aoe_context,
    is_aoe_escape_safe_hold_active,
    is_position_in_active_aoe,
    refresh_aoe_danger_zones,
)
from Py4GWCoreLib.Builds.Skills.BindingChainsCoordination import (
    packet_has_binding_chains,
    register_binding_chains_fired,
    release_binding_chains_reservation,
    reserve_binding_chains,
)


Soul_Twisting_ID = Skill.GetID("Soul_Twisting")
Boon_of_Creation_ID = Skill.GetID("Boon_of_Creation")
Shelter_ID = Skill.GetID("Shelter")
Union_ID = Skill.GetID("Union")
Displacement_ID = Skill.GetID("Displacement")
Earthbind_ID = Skill.GetID("Earthbind")
Binding_Chains_ID = Skill.GetID("Binding_Chains")
Spirit_Siphon_ID = Skill.GetID("Spirit_Siphon")
Splinter_Weapon_ID = Skill.GetID("Splinter_Weapon")
Summon_Spirits_kurzick_ID = Skill.GetID("Summon_Spirits_kurzick")
Summon_Spirits_luxon_ID = Skill.GetID("Summon_Spirits_luxon")
Armor_of_Unfeeling_ID = Skill.GetID("Armor_of_Unfeeling")
Spirits_Gift_ID = Skill.GetID("Spirits_Gift")
Breath_of_the_Great_Dwarf_ID = Skill.GetID("Breath_of_the_Great_Dwarf")
Ebon_Vanguard_Assassin_Support_ID = Skill.GetID("Ebon_Vanguard_Assassin_Support")
Ebon_Battle_Standard_of_Wisdom_ID = Skill.GetID("Ebon_Battle_Standard_of_Wisdom")
I_Am_Unstoppable_ID = Skill.GetID("I_Am_Unstoppable")
Air_of_Superiority_ID = Skill.GetID("Air_of_Superiority")
Remove_Hex_ID = Skill.GetID("Remove_Hex")

# Read-only view of the RoJ team's active five-second cluster leases. Keeping
# the shared numeric key here avoids importing the Monk build (whose filename
# contains spaces) and does not create a dependency on any Keystone build.
ROJ_CLUSTER_COVERAGE_LOCK_ID = 0x524F4A43
ROJ_BINDING_OPENING_MAX_COVERAGE = 2


@dataclass(slots=True)
class _SoulTwistingSnapshot:
    in_aggro: bool = False
    close_to_aggro: bool = False
    pre_spirit_setup: bool = False
    player_energy_pct: float = 1.0


class Soul_Twisting(BuildMgr):
    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Soul Twisting - RoJ Team Support Phase 3.2 Crash Safe",
            required_primary=Profession.Ritualist,
            template_code="OAOj4MgMJPYTr3jDAAAAAAAAAA",
            required_skills=[
                Soul_Twisting_ID,
                Shelter_ID,
                Union_ID,
            ],
            optional_skills=[
                Boon_of_Creation_ID,
                Displacement_ID,
                Earthbind_ID,
                Binding_Chains_ID,
                Spirit_Siphon_ID,
                Summon_Spirits_kurzick_ID,
                Summon_Spirits_luxon_ID,
                Armor_of_Unfeeling_ID,
                Spirits_Gift_ID,
                Breath_of_the_Great_Dwarf_ID,
                Ebon_Vanguard_Assassin_Support_ID,
                Ebon_Battle_Standard_of_Wisdom_ID,
                I_Am_Unstoppable_ID,
                Air_of_Superiority_ID,
                Remove_Hex_ID,
            ],
        )
        if match_only:
            return

        self.SetFallback("HeroAI", HeroAIBuild(standalone_fallback=True))
        self._last_idle_weapon_attack_tick: int = 0
        self._last_idle_weapon_target_id: int = 0
        self.SetBlockedSkills([
            Soul_Twisting_ID,
            Boon_of_Creation_ID,
            Shelter_ID,
            Union_ID,
            Displacement_ID,
            Earthbind_ID,
            Binding_Chains_ID,
            Spirit_Siphon_ID,
            Summon_Spirits_kurzick_ID,
            Summon_Spirits_luxon_ID,
            Armor_of_Unfeeling_ID,
            Spirits_Gift_ID,
            Breath_of_the_Great_Dwarf_ID,
            Ebon_Vanguard_Assassin_Support_ID,
            Ebon_Battle_Standard_of_Wisdom_ID,
            I_Am_Unstoppable_ID,
            Air_of_Superiority_ID,
            Remove_Hex_ID,
        ])
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skills: SkillsTemplate = SkillsTemplate(self)

    def _has_enemy_near_position(self, position: tuple[float, float] | None, max_distance: float) -> bool:
        if not position:
            return False

        max_distance_sq = max_distance * max_distance
        px, py = position

        for enemy_id in AgentArray.GetEnemyArray() or []:
            if not Agent.IsAlive(enemy_id):
                continue

            enemy_pos = Agent.GetXY(enemy_id)
            if not enemy_pos:
                continue

            dx = px - enemy_pos[0]
            dy = py - enemy_pos[1]
            if (dx * dx + dy * dy) <= max_distance_sq:
                return True

        return False

    def _nearest_enemy_distance_to_position(self, position: tuple[float, float] | None) -> float:
        """Return distance to the nearest living enemy, or a very large value.

        Summon Spirits teleports the protection package onto the Ritualist.  This
        helper is therefore used as a hard backline safety gate: a valid spirit
        package must never be dragged onto a Ritualist who is standing in the
        enemy front line.
        """
        if not position:
            return 99999.0
        px, py = position
        nearest = 99999.0
        for enemy_id in AgentArray.GetEnemyArray() or []:
            try:
                if not Agent.IsAlive(enemy_id):
                    continue
                enemy_pos = Agent.GetXY(enemy_id)
                if not enemy_pos:
                    continue
                dx = float(px) - float(enemy_pos[0])
                dy = float(py) - float(enemy_pos[1])
                distance = (dx * dx + dy * dy) ** 0.5
                if distance < nearest:
                    nearest = distance
            except Exception:
                continue
        return float(nearest)

    def _summon_spirits_backline_safe(self, *, reason: str) -> bool:
        """Only allow a spirit pull when the ST is clearly behind the front.

        We deliberately use a little more than Earshot-like spacing.  If an enemy
        is closer than this, leaving Shelter/Union/Displacement planted behind the
        team is safer than teleporting them into melee/AoE range.
        """
        min_enemy_distance = 1100.0
        nearest = self._nearest_enemy_distance_to_position(Player.GetXY())
        if nearest >= min_enemy_distance:
            return True
        self._log_st_aoe_event(
            "ST_SPIRIT_PULL_BLOCKED_FRONTLINE",
            reason=str(reason),
            nearest_enemy=f"{float(nearest):.1f}",
            required_distance=f"{float(min_enemy_distance):.1f}",
        )
        return False

    _CORE_SPIRIT_MODELS = {
        SpiritModelID.SHELTER,
        SpiritModelID.UNION,
        SpiritModelID.DISPLACEMENT,
        SpiritModelID.EARTHBIND,
    }

    def _summon_spirits_skill_id(self) -> int:
        if self.IsSkillEquipped(Summon_Spirits_kurzick_ID):
            return int(Summon_Spirits_kurzick_ID or 0)
        if self.IsSkillEquipped(Summon_Spirits_luxon_ID):
            return int(Summon_Spirits_luxon_ID or 0)
        return 0

    def _get_owned_core_spirits(self, max_distance: float | None = Range.Spellcast.value) -> list[int]:
        player_agent_id = Player.GetAgentID()
        try:
            spirit_array = AgentArray.GetSpiritPetArray()
            if max_distance is not None:
                spirit_array = AgentArray.Filter.ByDistance(spirit_array, Player.GetXY(), float(max_distance))
            spirit_array = AgentArray.Filter.ByCondition(
                spirit_array,
                lambda agent_id: Agent.IsAlive(agent_id) and Agent.IsSpawned(agent_id),
            )
        except Exception:
            return []

        owned_spirits: list[int] = []
        ownerless_spirits: list[int] = []
        nearby_spirits: list[int] = []
        for spirit_id in spirit_array or []:
            try:
                model_value = Agent.GetPlayerNumber(spirit_id)
                if model_value not in SpiritModelID._value2member_map_:
                    continue
                if SpiritModelID(model_value) not in self._CORE_SPIRIT_MODELS:
                    continue
                nearby_spirits.append(spirit_id)

                owner_id = Agent.GetOwnerID(spirit_id)
                if owner_id == player_agent_id:
                    owned_spirits.append(spirit_id)
                elif owner_id == 0:
                    ownerless_spirits.append(spirit_id)
            except Exception:
                continue

        if owned_spirits:
            return owned_spirits
        if ownerless_spirits:
            return ownerless_spirits
        return nearby_spirits

    def _core_spirit_distance_stats(self) -> tuple[list[int], float, float]:
        """Return all owned core spirits plus nearest/farthest distance to the ST."""
        spirits = self._get_owned_core_spirits(max_distance=None)
        if not spirits:
            return [], 0.0, 0.0
        distances: list[float] = []
        px, py = Player.GetXY()
        for spirit_id in spirits:
            try:
                sx, sy = Agent.GetXY(spirit_id)
                distances.append(((float(px) - float(sx)) ** 2 + (float(py) - float(sy)) ** 2) ** 0.5)
            except Exception:
                continue
        if not distances:
            return spirits, 0.0, 0.0
        return spirits, min(distances), max(distances)

    def _cast_summon_spirits_for_follow(self) -> bool:
        """Travel/post-combat reposition only; never drag safe spirits into combat.

        The core package may remain behind while its Spirit-range protection still
        covers the engagement.  During an active fight this routine intentionally
        does nothing.  The package is moved after combat/travel, or by the separate
        low-health/AoE rescue paths when that is actually necessary.
        """
        if False:
            yield

        skill_id = self._summon_spirits_skill_id()
        if skill_id <= 0 or not self.CanCastSkillID(skill_id):
            return False

        spirits, _nearest, farthest = self._core_spirit_distance_stats()
        if not spirits:
            return False

        # Any living enemy within Spirit range of the Ritualist means the party is
        # still in/at the current engagement. Keep the protection package planted
        # in the backline instead of teleporting it onto the moving ST.
        if self._has_enemy_near_position(Player.GetXY(), Range.Spirit.value):
            return False

        follow_threshold = 1850.0
        if float(farthest) < follow_threshold:
            return False
        if not self._summon_spirits_backline_safe(reason="post_combat_follow"):
            return False

        did_cast = yield from self.CastSkillID(
            skill_id=skill_id,
            log=False,
            aftercast_delay=180,
        )
        if did_cast:
            self._log_st_aoe_event(
                "ST_SPIRIT_POST_COMBAT_REPOSITION",
                core_count=len(spirits),
                farthest_distance=f"{float(farthest):.1f}",
                threshold=f"{float(follow_threshold):.1f}",
            )
        return bool(did_cast)

    def _cast_summon_spirits_at_safe_aoe_hold(self) -> bool:
        """After the ST escapes an AoE, pull its core spirits onto the safe position."""
        if False:
            yield

        skill_id = self._summon_spirits_skill_id()
        if skill_id <= 0 or not self.CanCastSkillID(skill_id):
            return False

        spirits, _nearest, farthest = self._core_spirit_distance_stats()
        if not spirits:
            return False

        exposed = 0
        for spirit_id in spirits:
            try:
                if is_position_in_active_aoe(
                    Agent.GetXY(spirit_id),
                    padding=80.0,
                    critical_only=False,
                ):
                    exposed += 1
            except Exception:
                continue

        if exposed <= 0 and float(farthest) < 450.0:
            return False

        did_cast = yield from self.CastSkillID(
            skill_id=skill_id,
            log=False,
            aftercast_delay=180,
        )
        if did_cast:
            self._log_st_aoe_event(
                "ST_AOE_SAFE_SPIRIT_PULL",
                core_count=len(spirits),
                exposed_count=int(exposed),
                farthest_distance=f"{float(farthest):.1f}",
            )
        return bool(did_cast)

    def _has_enemy_pressure_near_core_spirits(self, spirit_ids: list[int]) -> bool:
        positions: list[tuple[float, float]] = []
        try:
            player_xy = Player.GetXY()
            if player_xy:
                positions.append(player_xy)
        except Exception:
            pass
        for spirit_id in spirit_ids or []:
            try:
                spirit_xy = Agent.GetXY(spirit_id)
                if spirit_xy:
                    positions.append(spirit_xy)
            except Exception:
                continue
        return any(self._has_enemy_near_position(position, Range.Spirit.value) for position in positions)

    def _log_st_aoe_event(self, event: str, **fields) -> None:
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                str(event),
                account=str(Player.GetAccountEmail() or ""),
                **fields,
            )
        except Exception:
            pass

    def _cast_summon_spirits_for_aoe_rescue(self) -> bool:
        """Rescue planted core spirits only when they are inside a danger field.

        This is deliberately narrower than travel repositioning.  Pulling safe
        Shelter/Union away from the party merely because the ST was targeted
        would be harmful; exposed spirits, however, should be moved to the
        stable safe-hold point before replacements are planted.
        """
        if False:
            yield

        skill_id = self._summon_spirits_skill_id()
        if skill_id <= 0:
            return False
        spirits = self._get_owned_core_spirits(Range.Spellcast.value)
        if len(spirits) < 2:
            return False

        exposed = []
        for spirit_id in spirits:
            try:
                if is_position_in_active_aoe(
                    Agent.GetXY(spirit_id),
                    padding=80.0,
                    critical_only=False,
                ):
                    exposed.append(int(spirit_id))
            except Exception:
                continue
        if not exposed:
            return False

        did_cast = yield from self.CastSkillID(
            skill_id=skill_id,
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            self._log_st_aoe_event(
                "ST_AOE_SPIRIT_RESCUE",
                exposed_count=len(exposed),
                core_count=len(spirits),
            )
        return did_cast

    def _cast_summon_spirits_for_core_heal(self) -> bool:
        if False:
            yield

        skill_id = self._summon_spirits_skill_id()
        if skill_id <= 0:
            return False

        # Use Summon Spirits only as an optional emergency spirit-sustain tool.
        # Do not use it merely for travelling/repositioning in this build, because
        # pulling Shelter/Union/Displacement to the wrong spot can be worse than
        # leaving them planted.
        spirits = self._get_owned_core_spirits(Range.Spellcast.value)
        if len(spirits) < 2:
            return False
        low_core_spirits = [spirit_id for spirit_id in spirits if float(Agent.GetHealth(spirit_id) or 0.0) < 0.30]
        if not low_core_spirits:
            return False
        if not self._has_enemy_pressure_near_core_spirits(spirits):
            return False

        # Low-health spirits are worth rescuing, but never by teleporting the
        # package into melee range. Wait until the ST is back in a safe backline
        # position; otherwise the old planted spirits remain the safer option.
        if not self._summon_spirits_backline_safe(reason="low_core_health"):
            return False

        did_cast = yield from self.CastSkillID(
            skill_id=skill_id,
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            self._log_st_aoe_event(
                "ST_SPIRIT_LOW_HP_SAFE_PULL",
                low_count=len(low_core_spirits),
                core_count=len(spirits),
            )
        return bool(did_cast)

    def _is_pre_spirit_setup_needed(self) -> bool:
        # The normal HeroAI close-to-aggro gate is deliberately conservative.
        # For a no-Summon-Spirits ST bar, Shelter/Union/Displacement/Earthbind
        # should be planted before the party leader actually eats the first
        # damage packet. Use a wider leader/player scan, but only when enemies
        # are still realistically near the next engagement.
        if self.IsInAggro() or self.IsCloseToAggro():
            return True

        pre_spirit_range = Range.Spirit.value
        if self._has_enemy_near_position(Player.GetXY(), pre_spirit_range):
            return True

        try:
            from Py4GWCoreLib.Party import Party

            leader_id = int(Party.GetPartyLeaderID() or 0)
            if leader_id > 0 and Agent.IsValid(leader_id):
                if self._has_enemy_near_position(Agent.GetXY(leader_id), pre_spirit_range):
                    return True
        except Exception:
            pass

        return False

    def _get_bar_snapshot(self) -> _SoulTwistingSnapshot:
        snapshot = _SoulTwistingSnapshot()
        snapshot.in_aggro = bool(self.IsInAggro())
        snapshot.close_to_aggro = snapshot.in_aggro or self.IsCloseToAggro()
        snapshot.pre_spirit_setup = snapshot.close_to_aggro or self._is_pre_spirit_setup_needed()
        snapshot.player_energy_pct = float(Agent.GetEnergy(Player.GetAgentID()))
        return snapshot

    @staticmethod
    def _game_tick() -> int:
        try:
            import PySystem

            return int(PySystem.get_tick_count64() or 0)
        except Exception:
            return 0

    def _coordination_group_id(self) -> int:
        try:
            party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
            if party_id > 0:
                return party_id
        except Exception:
            pass
        try:
            email = str(Player.GetAccountEmail() or "").strip()
            if email:
                return int(GLOBAL_CACHE.ShMem.GetAccountGroupByEmail(email) or 0)
        except Exception:
            pass
        return 0

    def _roj_cluster_coverage_count(self, anchor_agent_id: int) -> int:
        """Read the current RoJ carpet depth without reserving any RoJ lane."""
        try:
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength,
                WhiteboardLockKind,
                WhiteboardReentryPolicy,
            )

            now_tick = self._game_tick()
            if now_tick <= 0 or int(anchor_agent_id or 0) <= 0:
                return 0
            return int(GLOBAL_CACHE.ShMem.CountLocks(
                int(WhiteboardLockKind.SKILL_TARGET),
                int(ROJ_CLUSTER_COVERAGE_LOCK_ID),
                int(anchor_agent_id),
                int(self._coordination_group_id()),
                "",
                int(now_tick),
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            ) or 0)
        except Exception:
            return 0

    def _pick_idle_weapon_target(self) -> int:
        """ST spear follows the exact same team packet/cleanup target."""
        try:
            from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import get_team_cluster_anchor
            return int(get_team_cluster_anchor(
                filter_range=Range.Spellcast.value,
                minimum_enemies=2,
                consumer_role="st_idle_weapon",
            ) or 0)
        except Exception:
            return 0

    def _get_roj_team_focus_packet(self) -> tuple[int, list[int]]:
        """Return the exact shared RoJway packet; never invent a local target."""
        try:
            from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import (
                get_team_cluster_anchor,
                get_team_cluster_members,
            )

            anchor = int(get_team_cluster_anchor(
                filter_range=Range.Spellcast.value,
                minimum_enemies=2,
                consumer_role="st_binding_chains",
            ) or 0)
            if anchor <= 0 or not Agent.IsValid(anchor) or not Agent.IsAlive(anchor):
                return 0, []
            members = [
                int(agent_id)
                for agent_id in get_team_cluster_members(
                    anchor,
                    radius=Range.Adjacent.value,
                    filter_range=Range.Spellcast.value,
                )
                if int(agent_id or 0) > 0
                and Agent.IsValid(int(agent_id))
                and Agent.IsAlive(int(agent_id))
            ]
        except Exception:
            return 0, []

        if anchor not in members:
            members.append(anchor)
        return anchor, sorted(set(members))

    def _binding_chains_target_still_valid(self, expected_anchor_id: int) -> bool:
        anchor, members = self._get_roj_team_focus_packet()
        return bool(
            int(anchor) == int(expected_anchor_id)
            and len(members) >= 2
            and Agent.IsValid(int(anchor))
            and Agent.IsAlive(int(anchor))
            and not packet_has_binding_chains(members)
        )

    def _cast_binding_chains_for_roj(self, *, player_energy_pct: float) -> bool:
        """Snare the RoJ opening, or re-snare foes trying to leave the carpet."""
        if False:
            yield
        if not self.IsSkillEquipped(Binding_Chains_ID):
            return False
        if not self.IsInAggro() or float(player_energy_pct) < 0.35:
            return False
        if not self.CanCastSkillID(Binding_Chains_ID):
            return False

        anchor, members = self._get_roj_team_focus_packet()
        if anchor <= 0 or len(members) < 2:
            return False
        roj_coverage = int(self._roj_cluster_coverage_count(anchor))
        moving_members = 0
        for member_id in members:
            try:
                if Agent.IsMoving(int(member_id)):
                    moving_members += 1
            except Exception:
                continue
        # The first two RoJs are the ideal opening window. If core-spirit work
        # delayed the ST, Binding Chains is still useful later only while at
        # least one foe is actually trying to leave the ground fields.
        opening_window = roj_coverage <= ROJ_BINDING_OPENING_MAX_COVERAGE
        if not opening_window and moving_members <= 0:
            return False
        reservation = reserve_binding_chains(
            anchor_id=int(anchor),
            member_ids=members,
            role="st",
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
                source="st_after_core_spirits",
            )
            self._log_st_aoe_event(
                "ST_BINDING_CHAINS_ROJ_PACKET",
                target_id=int(anchor),
                packet_size=int(len(members)),
                packet_key=int(reservation.packet_key),
                roj_coverage_before=int(roj_coverage),
                moving_members=int(moving_members),
                opening_window=bool(opening_window),
                packet_members=",".join(str(int(agent_id)) for agent_id in members),
                policy="st_primary_coordinated_after_core_opening_or_moving_packet",
            )
            return True
        release_binding_chains_reservation(
            reservation,
            reason="st_cast_command_rejected_or_focus_changed",
        )
        return False

    def _cast_evas_on_roj_focus(self, *, player_energy_pct: float) -> bool:
        """Keep the ST's only foe-targeted PvE summon on the team packet."""
        if False:
            yield
        if not self.IsSkillEquipped(Ebon_Vanguard_Assassin_Support_ID):
            return False
        if float(player_energy_pct) < 0.40:
            return False
        if not self.CanCastSkillID(Ebon_Vanguard_Assassin_Support_ID):
            return False

        anchor, _members = self._get_roj_team_focus_packet()
        if anchor <= 0:
            return False
        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Ebon_Vanguard_Assassin_Support_ID,
            target_agent_id=int(anchor),
            extra_condition=lambda: int(self._get_roj_team_focus_packet()[0]) == int(anchor),
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            self._log_st_aoe_event(
                "ST_EVAS_TEAM_FOCUS",
                target_id=int(anchor),
                policy="same_authoritative_packet_and_cleanup_no_local_fallback",
            )
            return True
        return False


    def _idle_weapon_autoattack(self) -> bool:
        """Free ST DPS only after the entire protection/support rotation is idle.

        Intentionally weapon-type agnostic: a staff, spear or wand may attack.
        This function remains the final action in the ST rotation, so it never
        gets priority over Soul Twisting, spirits, cleanses, support or energy.
        """
        try:
            from Py4GWCoreLib import get_game_tick
            now = int(get_game_tick() or 0)
        except Exception:
            now = 0
        if now > 0 and now - int(self._last_idle_weapon_attack_tick or 0) < 650:
            return False
        if not self.IsInAggro():
            return False

        target_id = int(self._pick_idle_weapon_target() or 0)
        if target_id <= 0:
            return False
        try:
            if not Agent.IsValid(target_id) or not Agent.IsAlive(target_id):
                return False
        except Exception:
            return False

        try:
            if int(Player.GetTargetID() or 0) != target_id:
                yield from Routines.Yield.Agents.ChangeTarget(target_id)
            Player.Interact(target_id, False)
            self._last_idle_weapon_attack_tick = int(now)
            self._last_idle_weapon_target_id = int(target_id)
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "ST_IDLE_WEAPON_ATTACK",
                    target_id=int(target_id),
                    splinter_active=bool(
                        Routines.Checks.Agents.HasEffect(
                            Player.GetAgentID(),
                            Splinter_Weapon_ID,
                            exact_weapon_spell=True,
                        )
                    ),
                    policy="only_after_full_st_rotation_idle_weapon_agnostic",
                )
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _dangerous_caster_precast_needed(self) -> bool:
        try:
            from Py4GWCoreLib.Builds.Skills.CombatSense import dangerous_aoe_caster_cluster
            dangerous, _anchor, _members = dangerous_aoe_caster_cluster(
                range_value=Range.Spellcast.value,
                minimum_dangerous_casters=2,
            )
            return bool(dangerous)
        except Exception:
            return False

    def _run_local_skill_logic(self):
        refresh_aoe_danger_zones()

        # Meteor Shower and other knockdown fields can prevent the Ritualist
        # from ever reaching safety.  Use the instant self-protection first when
        # available, then move on the next tick.  Pure damage fields do not need
        # this detour; the ST leaves them immediately.
        aoe_context = get_player_active_aoe_context(padding=70.0, critical_only=True)
        if aoe_context is not None:
            control = str(aoe_context.get("control", "damage"))
            try:
                from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
                preescape_iau_enabled = SimplePowerSettings.is_feature_enabled(
                    "st_aoe_preescape_knockdown_immunity", True
                )
            except Exception:
                preescape_iau_enabled = True
            if (
                preescape_iau_enabled
                and control in ("repeated_knockdown", "knockdown")
                and int(aoe_context.get("remaining_ms", 0) or 0) > 650
                and self.IsSkillEquipped(I_Am_Unstoppable_ID)
                and Routines.Checks.Skills.CanCast()
                and not Routines.Checks.Agents.HasEffect(Player.GetAgentID(), I_Am_Unstoppable_ID)
            ):
                if (yield from self.skills.Any.NoAttribute.I_Am_Unstoppable()):
                    self._log_st_aoe_event(
                        "ST_AOE_PREESCAPE_IAU",
                        skill_id=int(aoe_context.get("skill_id", 0) or 0),
                        control=control,
                        remaining_ms=int(aoe_context.get("remaining_ms", 0) or 0),
                    )
                    return True

        # While still inside the field or travelling to the escape point, AoE
        # movement owns the tick.  Once the stable safe point is reached, allow
        # this ST rotation to run even though normal Follow remains suspended.
        try:
            from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
            safe_hold_setup_enabled = SimplePowerSettings.is_feature_enabled(
                "st_aoe_safe_hold_spirit_setup", True
            )
        except Exception:
            safe_hold_setup_enabled = True

        if avoid_active_aoe_if_needed(
            role="st",
            allow_actions_at_safe_hold=bool(safe_hold_setup_enabled),
        ):
            return True

        safe_aoe_hold = bool(
            safe_hold_setup_enabled and is_aoe_escape_safe_hold_active(role="st")
        )

        if not Routines.Checks.Skills.CanCast():
            yield from Routines.Yield.wait(100)
            return False

        snapshot = self._get_bar_snapshot()
        if safe_aoe_hold:
            snapshot.pre_spirit_setup = True
            snapshot.close_to_aggro = True
        if not snapshot.pre_spirit_setup:
            return False

        # Emergency cleanse always wins. Do not let long spirit casts delay a
        # dangerous hex removal when the team is already near combat.
        if (yield from self.skills.Monk.NoAttribute.Remove_Hex(min_priority=HexRemovalPriority.HIGH)):
            return True

        # Hochnäsigkeit / Air of Superiority should be up before kills start.
        # It is preferred over Mighty Was Vorizun for this setup because BiP +
        # Soul Twisting normally covers energy, while Air can accelerate the
        # whole bar during kill chains.
        if (
            not safe_aoe_hold
            and self.IsSkillEquipped(Air_of_Superiority_ID)
            and (yield from self.skills.Any.PvE.Air_of_Superiority())
        ):
            return True

        # Outside an AoE escape episode, use IAU proactively under pressure.
        # During safe hold it would only delay the core spirit rebuild.
        if (
            not safe_aoe_hold
            and snapshot.in_aggro
            and (yield from self.skills.Any.NoAttribute.I_Am_Unstoppable())
        ):
            return True

        if safe_aoe_hold and (yield from self._cast_summon_spirits_at_safe_aoe_hold()):
            return True

        # Travel/post-combat follow only. During combat the core protection
        # package is deliberately allowed to remain behind the front line while
        # its effects still cover the fight.
        if not safe_aoe_hold and (yield from self._cast_summon_spirits_for_follow()):
            return True

        # Core ST setup. This can now start earlier than normal close-to-aggro:
        # as soon as enemies are in the wider pre-spirit scan around the party
        # leader/player. Every binding ritual below is still gated inside
        # Communing: Soul Twisting must be active, and an existing nearby copy
        # of the same spirit blocks wasteful recasts.
        if (yield from self.skills.Ritualist.SpawningPower.Soul_Twisting()):
            return True

        # ST self-energy: Spirit Siphon is optional/supported. Use it before the
        # expensive core rebuild only when energy is actually becoming limiting.
        # Emergency cleanse, AoE escape and Soul Twisting itself remain above it.
        if (
            self.IsSkillEquipped(Spirit_Siphon_ID)
            and snapshot.player_energy_pct <= 0.65
            and (yield from self.skills.Ritualist.ChannelingMagic.Spirit_Siphon(max_self_energy_pct=0.65))
        ):
            self._log_st_aoe_event(
                "ST_SPIRIT_SIPHON",
                energy_before=f"{float(snapshot.player_energy_pct):.4f}",
                policy="self_energy_before_core_rebuild",
            )
            return True

        # Optional spirit heal: only if Summon Spirits is equipped and core
        # spirits are already planted, damaged, and still under enemy pressure.
        # Missing core spirits are handled by the normal Shelter/Union/etc. recast
        # chain below.
        if (yield from self._cast_summon_spirits_for_core_heal()):
            return True

        # Dangerous caster packet: accelerate defensive spirit setup.
        # This does not gate Para/Mesmer offense; ST simply services protection first.
        if self._dangerous_caster_precast_needed():
            if self.IsSkillEquipped(Shelter_ID) and (yield from self.skills.Ritualist.Communing.Shelter()):
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event("DANGEROUS_CASTER_ST_PRECAST", skill="Shelter")
                except Exception:
                    pass
                return True
            if self.IsSkillEquipped(Union_ID) and (yield from self.skills.Ritualist.Communing.Union()):
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event("DANGEROUS_CASTER_ST_PRECAST", skill="Union")
                except Exception:
                    pass
                return True
            if self.IsSkillEquipped(Displacement_ID) and (yield from self.skills.Ritualist.Communing.Displacement()):
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event("DANGEROUS_CASTER_ST_PRECAST", skill="Displacement")
                except Exception:
                    pass
                return True

        if (yield from self.skills.Ritualist.Communing.Shelter()):
            return True

        if (yield from self.skills.Ritualist.Communing.Union()):
            return True

        if (yield from self.skills.Ritualist.Communing.Displacement()):
            return True

        if (yield from self.skills.Ritualist.Communing.Earthbind()):
            return True

        # Offensive support starts only after Shelter/Union/Displacement/
        # Earthbind are serviced. Binding Chains targets the same authoritative
        # packet as RoJ; its nearby snare keeps moving foes inside the five-second
        # ground fields without ever replacing the ST's defensive obligations.
        if (yield from self._cast_binding_chains_for_roj(
            player_energy_pct=float(snapshot.player_energy_pct),
        )):
            return True

        # Once the important core spirits exist, protect them. Armor targeting
        # avoids repeatedly refreshing the same spirit while another core spirit
        # is still unprotected.
        if (yield from self.skills.Ritualist.Communing.Armor_of_Unfeeling()):
            return True

        if (yield from self.skills.Ritualist.SpawningPower.Spirits_Gift()):
            return True

        # Boon is useful if equipped, but it should not delay Shelter/Union/
        # Displacement/Earthbind. With BiP in the team it is lower priority.
        if snapshot.player_energy_pct >= 0.35 and (yield from self.skills.Ritualist.SpawningPower.Boon_of_Creation()):
            return True

        if (
            snapshot.player_energy_pct >= 0.50
            and (yield from self.skills.Monk.NoAttribute.Remove_Hex(
                min_priority=HexRemovalPriority.MEDIUM,
            ))
        ):
            return True

        if not snapshot.in_aggro:
            return False

        if (yield from self._cast_evas_on_roj_focus(
            player_energy_pct=float(snapshot.player_energy_pct),
        )):
            return True

        if (yield from self.skills.Any.NoAttribute.Ebon_Battle_Standard_of_Wisdom()):
            return True

        if (yield from self.skills.Any.NoAttribute.Breath_of_the_Great_Dwarf()):
            return True

        if snapshot.player_energy_pct >= 0.70 and (yield from self.skills.Monk.NoAttribute.Remove_Hex()):
            return True

        # Absolutely last priority: if every ST/protection/support action above
        # had nothing to do, use the currently equipped weapon for free pressure.
        # Staff is explicitly supported; an attack is never started instead of a
        # needed spirit/support cast because every such action is checked first.
        if (yield from self._idle_weapon_autoattack()):
            return True

        return False
