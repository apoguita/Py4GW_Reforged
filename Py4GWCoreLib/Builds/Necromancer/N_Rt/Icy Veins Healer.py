from Py4GWCoreLib import Profession, Range, Routines
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib import Player, GLOBAL_CACHE
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build
from Py4GWCoreLib.HeroAI.targeting import GetAllAlliesArray
from Py4GWCoreLib import BuildMgr
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Builds.Skills import SkillsTemplate
from Py4GWCoreLib.Builds.Skills.DangerInterruptClaim import (
    get_dangerous_casts_in_range,
)
from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import (
    get_team_cluster_anchor, get_team_cluster_members, pick_unhexed_blood_bond_target,
)
from Py4GWCoreLib.Builds.Skills.AoEDangerPrediction import (
    avoid_active_aoe_if_needed,
    refresh_aoe_danger_zones,
)

Blood_is_Power_ID = Skill.GetID("Blood_is_Power")
Blood_Ritual_ID = Skill.GetID("Blood_Ritual")
Spirit_Siphon_ID = Skill.GetID("Spirit_Siphon")
Signet_of_Lost_Souls_ID = Skill.GetID("Signet_of_Lost_Souls")
Mend_Body_and_Soul_ID = Skill.GetID("Mend_Body_and_Soul")
Spirit_Light_ID = Skill.GetID("Spirit_Light")
Protective_Was_Kaolai_ID = Skill.GetID("Protective_Was_Kaolai")
Vital_Weapon_ID = Skill.GetID("Vital_Weapon")
Wielders_Boon_ID = Skill.GetID("Wielders_Boon")
Mending_Grip_ID = Skill.GetID("Mending_Grip")
Spirit_Transfer_ID = Skill.GetID("Spirit_Transfer")
Life_ID = Skill.GetID("Life")
You_Are_All_Weaklings_ID = Skill.GetID("You_Are_All_Weaklings")
Enfeebling_Blood_ID = Skill.GetID("Enfeebling_Blood")
Recovery_ID = Skill.GetID("Recovery")
Breath_of_the_Great_Dwarf_ID = Skill.GetID("Breath_of_the_Great_Dwarf")
Recuperation_ID = Skill.GetID("Recuperation")
Blood_Bond_ID = Skill.GetID("Blood_Bond")
Ebon_Vanguard_Assassin_Support_ID = Skill.GetID("Ebon_Vanguard_Assassin_Support")
Air_of_Superiority_ID = Skill.GetID("Air_of_Superiority")
Great_Dwarf_Weapon_ID = Skill.GetID("Great_Dwarf_Weapon")
Icy_Veins_ID = Skill.GetID("Icy_Veins")
Necrosis_ID = Skill.GetID("Necrosis")
Pain_Inverter_ID = Skill.GetID("Pain_Inverter")
Technobabble_ID = Skill.GetID("Technobabble")
Signet_of_Corruption_Kurzick_ID = Skill.GetID("Signet_of_Corruption_Kurzick")
Signet_of_Corruption_Luxon_ID = Skill.GetID("Signet_of_Corruption_Luxon")


class Icy_Veins_Healer(BuildMgr):
    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Icy Veins Healer",
            required_primary=Profession.Necromancer,
            required_secondary=Profession.Ritualist,
            template_code="OAhjQkGZIP3hqq0EAAAAAAAAAA",
            required_skills=[
                Icy_Veins_ID,
                Mend_Body_and_Soul_ID,
            ],
            optional_skills=[
                Icy_Veins_ID,
                Necrosis_ID,
                Technobabble_ID,
                Pain_Inverter_ID,
                Signet_of_Corruption_Kurzick_ID,
                Signet_of_Corruption_Luxon_ID,
                Blood_is_Power_ID,
                Blood_Ritual_ID,
                Spirit_Siphon_ID,
                Signet_of_Lost_Souls_ID,
                Spirit_Light_ID,
                Protective_Was_Kaolai_ID,
                Vital_Weapon_ID,
                Wielders_Boon_ID,
                Mending_Grip_ID,
                Spirit_Transfer_ID,
                Life_ID,
                You_Are_All_Weaklings_ID,
                Enfeebling_Blood_ID,
                Recovery_ID,
                Breath_of_the_Great_Dwarf_ID,
                Recuperation_ID,
                Blood_Bond_ID,
                Ebon_Vanguard_Assassin_Support_ID,
                Air_of_Superiority_ID,
                Great_Dwarf_Weapon_ID,
            ],
        )


        # Signet of Lost Souls is optional in this variant.
        # Some bars replace it with Great Dwarf Weapon; requiring SoLS would
        # make the BiP build fail to match and fall back to generic HeroAI.

        # Simple-power BiP policy for the Keystone/SoJ team:
        # keep the original, proven HeroAI target resolver, but make BiP
        # eligible for allies below 70% energy instead of the stock 40%.
        # This avoids the over-complicated custom target scan that could fail
        # to find valid allies, while still giving energy much earlier.
        blood_is_power = self.GetCustomSkill(Blood_is_Power_ID)
        if blood_is_power is not None:
            blood_is_power.Conditions.LessEnergy = 0.70

        blood_ritual = self.GetCustomSkill(Blood_Ritual_ID)
        if blood_ritual is not None:
            # Test-mode replacement for BiP on the existing N/Rt.
            # Same early-support threshold; the normal ally resolver chooses
            # the energy-needy valid caster.
            blood_ritual.Conditions.LessEnergy = 0.70

        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skills: SkillsTemplate = SkillsTemplate(self)

        # Energy/BiP telemetry only. These fields never influence targeting,
        # healing priorities, BiP thresholds, Recuperation or any cast decision.
        self._energy_telemetry_last_tick: int = 0
        self._energy_telemetry_low_state: dict[int, int] = {}
        # Icy Veins telemetry only; never influences target selection.
        # target_id -> (cast_tick, target_hp_at_cast, packet_size_at_cast)
        self._icy_veins_last_targets: dict[int, tuple[int, float, int]] = {}
        self._blood_ritual_last_attempt_tick: int = 0
        self._blood_ritual_attempt_interval_ms: int = 600

    @staticmethod
    def _blood_bond_martial_profession(agent_id: int) -> bool:
        try:
            primary, _secondary = Agent.GetProfessions(int(agent_id))
            primary_id = int(getattr(primary, "value", primary) or 0)
            martial = {
                int(getattr(Profession.Warrior, "value", Profession.Warrior)),
                int(getattr(Profession.Ranger, "value", Profession.Ranger)),
                int(getattr(Profession.Assassin, "value", Profession.Assassin)),
                int(getattr(Profession.Dervish, "value", Profession.Dervish)),
                int(getattr(Profession.Paragon, "value", Profession.Paragon)),
            }
            return primary_id in martial
        except Exception:
            return False

    @staticmethod
    def _skill_is_spell(skill_id: int) -> bool:
        try:
            return bool(Skill.Flags.IsSpell(int(skill_id or 0)))
        except Exception:
            return False

    def _smart_blood_bond_target(self) -> tuple[int, str]:
        """Prepare non-spell enemies for Signet of Disruption.

        Spells can already be interrupted without a hex, so Blood Bond is spent
        first on dangerous non-spell activations. If none is active, it goes to
        the best unhexed martial packet so one adjacent Blood Bond cast can
        prepare several likely non-spell users.
        """
        if not self.IsSkillEquipped(Blood_Bond_ID):
            return 0, ""
        if not self.IsInAggro():
            return 0, ""

        # First priority: a currently dangerous non-spell skill that the Mesmers
        # could interrupt immediately once the target is hexed.
        try:
            for enemy_id, enemy_skill_id in get_dangerous_casts_in_range(Range.Spellcast.value):
                enemy_id = int(enemy_id or 0)
                enemy_skill_id = int(enemy_skill_id or 0)
                if enemy_id <= 0 or enemy_skill_id <= 0:
                    continue
                if self._skill_is_spell(enemy_skill_id):
                    continue
                if not Routines.Checks.Agents.IsAlive(enemy_id):
                    continue
                try:
                    if Agent.IsHexed(enemy_id):
                        continue
                except Exception:
                    pass
                return enemy_id, "dangerous_nonspell_activation"
        except Exception:
            pass

        # Predictive fallback: martial cluster, because those bars are most
        # likely to expose attacks/stances/other non-spell activations.
        try:
            target = int(Routines.Targeting.PickClusteredTarget(
                cluster_radius=Range.Adjacent.value,
                preferred_condition=lambda agent_id: (
                    self._blood_bond_martial_profession(int(agent_id))
                    and not Agent.IsHexed(int(agent_id))
                ),
                filter_radius=Range.Spellcast.value,
            ) or 0)
            if target > 0:
                return target, "predictive_martial_cluster"
        except Exception:
            pass
        return 0, ""

    def _try_interrupt_support_blood_bond(self):
        if not self.IsSkillEquipped(Blood_Bond_ID):
            return False
        if not self.CanCastSkillID(Blood_Bond_ID):
            return False
        target_id, reason = self._smart_blood_bond_target()
        target_id = int(target_id or 0)
        if target_id <= 0:
            return False
        try:
            if Agent.IsHexed(target_id):
                return False
        except Exception:
            pass

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Blood_Bond_ID,
            target_agent_id=target_id,
            extra_condition=lambda: (
                Routines.Checks.Agents.IsAlive(target_id)
                and not Agent.IsHexed(target_id)
            ),
            log=False,
            aftercast_delay=200,
        )
        if did_cast:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "BIP_BLOOD_BOND_INTERRUPT_SUPPORT",
                    target_id=int(target_id),
                    reason=str(reason),
                    policy="nonspell_first_then_martial_cluster",
                )
            except Exception:
                pass
            return True
        return False


    @staticmethod
    def _telemetry_agent_name(agent_id: int) -> str:
        try:
            name = str(Agent.GetName(int(agent_id)) or "")
            if name:
                return name
        except Exception:
            pass
        return f"agent_{int(agent_id or 0)}"

    @staticmethod
    def _telemetry_professions(agent_id: int) -> tuple[int, int]:
        try:
            primary, secondary = Agent.GetProfessions(int(agent_id))
            return (
                int(getattr(primary, "value", primary) or 0),
                int(getattr(secondary, "value", secondary) or 0),
            )
        except Exception:
            return (0, 0)

    def _telemetry_combat_state(self) -> tuple[bool, int, int]:
        """Broad read-only combat state for logging.

        Unlike the combat AI, telemetry deliberately accepts either nearby foes
        or the shared team focus as evidence that the party is fighting.
        """
        enemy_count = int(self._enemy_count_in_combat_range() or 0)
        try:
            team_anchor = int(get_team_cluster_anchor() or 0)
        except Exception:
            team_anchor = 0
        return bool(enemy_count > 0 or team_anchor > 0), enemy_count, team_anchor

    def _track_team_energy(self) -> None:
        """Sample team energy during combat without changing any AI decision.

        Periodic samples are throttled to one pass every 1.5 seconds. Low-energy
        threshold transitions are logged at 50%, 30% and 20%.
        """
        try:
            from Py4GWCoreLib import get_game_tick
            now = int(get_game_tick() or 0)
        except Exception:
            return
        if now <= 0:
            return

        in_combat, enemy_count, team_anchor = self._telemetry_combat_state()
        if not in_combat:
            # Reset transition state between fights so a new low-energy episode
            # in the next fight is visible.
            self._energy_telemetry_low_state.clear()
            return

        if (
            self._energy_telemetry_last_tick > 0
            and now - int(self._energy_telemetry_last_tick) < 1500
        ):
            return
        self._energy_telemetry_last_tick = now

        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
        except Exception:
            return

        try:
            ally_ids = list(GetAllAlliesArray(Range.Spellcast.value) or [])
        except Exception:
            ally_ids = []

        self_id = int(Player.GetAgentID() or 0)
        if self_id > 0 and self_id not in ally_ids:
            ally_ids.append(self_id)

        seen: set[int] = set()
        for ally_id in ally_ids:
            ally_id = int(ally_id or 0)
            if ally_id <= 0 or ally_id in seen:
                continue
            seen.add(ally_id)
            try:
                if not Agent.IsValid(ally_id) or not Agent.IsAlive(ally_id):
                    continue
                energy_pct = float(Agent.GetEnergy(ally_id))
            except Exception:
                continue

            primary_id, secondary_id = self._telemetry_professions(ally_id)
            name = self._telemetry_agent_name(ally_id)

            is_self = bool(int(ally_id) == int(self_id))
            try:
                max_energy = int(Agent.GetMaxEnergy(ally_id) or 0)
            except Exception:
                max_energy = 0
            CombatDebug.log_event(
                "TEAM_ENERGY_SAMPLE",
                agent_id=int(ally_id),
                name=str(name),
                primary_profession=int(primary_id),
                secondary_profession=int(secondary_id),
                energy_pct=f"{float(energy_pct):.4f}",
                max_energy=int(max_energy),
                is_self=bool(is_self),
                locally_reliable=bool(is_self or max_energy > 0),
                enemy_count=int(enemy_count),
                team_anchor=int(team_anchor),
            )

            # Encode the deepest active threshold as 0/50/30/20.
            current_state = 0
            if energy_pct < 0.20:
                current_state = 20
            elif energy_pct < 0.30:
                current_state = 30
            elif energy_pct < 0.50:
                current_state = 50

            previous_state = int(self._energy_telemetry_low_state.get(ally_id, 0) or 0)
            if current_state != previous_state:
                if current_state > 0:
                    CombatDebug.log_event(
                        "TEAM_ENERGY_LOW_ENTER",
                        agent_id=int(ally_id),
                        name=str(name),
                        threshold_pct=int(current_state),
                        energy_pct=f"{float(energy_pct):.4f}",
                    )
                elif previous_state > 0:
                    CombatDebug.log_event(
                        "TEAM_ENERGY_LOW_EXIT",
                        agent_id=int(ally_id),
                        name=str(name),
                        previous_threshold_pct=int(previous_state),
                        energy_pct=f"{float(energy_pct):.4f}",
                    )
                self._energy_telemetry_low_state[ally_id] = int(current_state)

    def _pick_priority_blood_ritual_target(self) -> tuple[int, float]:
        """Choose an energy-needy, TOUCH-REACHABLE priority player.

        Priority: ST -> HR Para -> real SoJ Monk -> Keystone Mesmer.
        Shared-memory energy is preferred because it is reliable for multibox
        accounts. Targets outside Blood Ritual touch range are skipped instead
        of generating hundreds of futile cast attempts.
        """
        try:
            from Py4GWCoreLib.HeroAI.utils import GetEnergyValues
            from Py4GWCoreLib.Py4GWcorelib import Utils
        except Exception:
            GetEnergyValues = None
            Utils = None

        try:
            allies = list(GetAllAlliesArray() or [])
        except Exception:
            allies = []

        ritualist_id = int(getattr(Profession.Ritualist, "value", Profession.Ritualist))
        paragon_id = int(getattr(Profession.Paragon, "value", Profession.Paragon))
        monk_id = int(getattr(Profession.Monk, "value", Profession.Monk))
        mesmer_id = int(getattr(Profession.Mesmer, "value", Profession.Mesmer))
        self_xy = Player.GetXY()

        ranked = []
        for aid in allies:
            aid = int(aid or 0)
            if aid <= 0 or aid == int(Player.GetAgentID() or 0):
                continue
            try:
                if not Routines.Checks.Agents.IsAlive(aid):
                    continue
                energy = float(GetEnergyValues(aid)) if GetEnergyValues else -1.0
                if energy < 0.0:
                    energy = float(Agent.GetEnergy(aid))
                if energy < 0.0 or energy >= 0.70:
                    continue

                # Blood Ritual is touch range. Never queue an impossible target.
                if Utils is not None:
                    distance = float(Utils.Distance(self_xy, Agent.GetXY(aid)))
                else:
                    ax, ay = Agent.GetXY(aid)
                    dx = float(self_xy[0]) - float(ax)
                    dy = float(self_xy[1]) - float(ay)
                    distance = float((dx * dx + dy * dy) ** 0.5)
                if distance > float(Range.Touch.value) * 1.10:
                    continue

                primary, secondary = Agent.GetProfessions(aid)
                primary_id = int(getattr(primary, "value", primary) or 0)
                secondary_id = int(getattr(secondary, "value", secondary) or 0)
            except Exception:
                continue

            if primary_id == ritualist_id:
                prio = 0
            elif primary_id == paragon_id:
                prio = 1
            elif primary_id == monk_id or secondary_id == monk_id:
                prio = 2
            elif primary_id == mesmer_id:
                prio = 3
            else:
                continue

            ranked.append((prio, energy, distance, aid))

        if not ranked:
            return (0, -1.0)
        ranked.sort(key=lambda x: (int(x[0]), float(x[1]), float(x[2]), int(x[3])))
        _prio, energy, _distance, aid = ranked[0]
        return int(aid), float(energy)

    def _try_priority_blood_ritual(self):
        """Low-noise safety BR: only reachable ally <70%, max ~1.7 checks/sec."""
        if not self.IsSkillEquipped(Blood_Ritual_ID) or not self.CanCastSkillID(Blood_Ritual_ID):
            return False

        try:
            from Py4GWCoreLib.Builds.Skills.DangerInterruptClaim import get_game_tick
            now = int(get_game_tick() or 0)
        except Exception:
            now = 0
        if (
            now > 0
            and int(self._blood_ritual_last_attempt_tick or 0) > 0
            and now - int(self._blood_ritual_last_attempt_tick) < int(self._blood_ritual_attempt_interval_ms)
        ):
            return False

        target_id, energy_before = self._pick_priority_blood_ritual_target()
        if target_id <= 0:
            return False
        self._blood_ritual_last_attempt_tick = int(now)

        # Direct cast is now safe because we have already proven touch range.
        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Blood_Ritual_ID,
            target_agent_id=int(target_id),
            extra_condition=lambda tid=int(target_id): (
                Routines.Checks.Agents.IsAlive(tid)
                and float(Agent.GetEnergy(tid)) < 0.72
            ),
            log=False,
            aftercast_delay=150,
        )
        if did_cast:
            self._log_successful_blood_ritual_cast(int(target_id), float(energy_before))
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "BLOOD_RITUAL_SMART_CAST",
                    target_id=int(target_id),
                    target_energy_before=f"{float(energy_before):.4f}",
                    policy="shared_energy_touch_reachable_priority_throttled",
                )
            except Exception:
                pass
            return True
        return False


    def _resolve_blood_ritual_target_for_telemetry(self) -> tuple[int, float]:
        try:
            custom = self.GetCustomSkill(Blood_Ritual_ID)
            target_id = int(self.ResolveAllyTarget(Blood_Ritual_ID, custom) or 0)
        except Exception:
            target_id = 0
        energy_pct = -1.0
        if target_id > 0:
            try:
                energy_pct = float(Agent.GetEnergy(target_id))
            except Exception:
                pass
        return target_id, energy_pct

    def _log_successful_blood_ritual_cast(self, target_id: int, target_energy_before: float) -> None:
        # Keep Blood Ritual logs focused on the energy consumers we are
        # evaluating: Keystone Mesmers, HR Paragon, ST Ritualist and the real
        # SoJ Monk account. Do not log RoJ Monk hero, Fire Ele hero or MM hero.
        try:
            primary_id, _secondary_id = self._telemetry_professions(target_id)
            mesmer_id = int(getattr(Profession.Mesmer, "value", Profession.Mesmer))
            paragon_id = int(getattr(Profession.Paragon, "value", Profession.Paragon))
            ritualist_id = int(getattr(Profession.Ritualist, "value", Profession.Ritualist))
            monk_id = int(getattr(Profession.Monk, "value", Profession.Monk))
            keep_log = primary_id in (mesmer_id, paragon_id, ritualist_id)
            if primary_id == monk_id:
                keep_log = bool(Agent.IsPlayer(int(target_id)))
            if not keep_log:
                return
        except Exception:
            return

        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            in_combat, enemy_count, team_anchor = self._telemetry_combat_state()
            self_energy = float(Agent.GetEnergy(Player.GetAgentID()))
            primary_id, secondary_id = self._telemetry_professions(target_id)
            CombatDebug.log_event(
                "BLOOD_RITUAL_CAST_PROFILE",
                target_id=int(target_id or 0),
                target_name=str(self._telemetry_agent_name(target_id)),
                target_primary_profession=int(primary_id),
                target_secondary_profession=int(secondary_id),
                target_energy_before=f"{float(target_energy_before):.4f}",
                support_self_energy=f"{float(self_energy):.4f}",
                in_combat=bool(in_combat),
                enemy_count=int(enemy_count),
                team_anchor=int(team_anchor),
            )
        except Exception:
            pass

    def _resolve_bip_target_for_telemetry(self) -> tuple[int, float]:
        """Mirror the existing BiP resolver for logging only."""
        try:
            custom = self.GetCustomSkill(Blood_is_Power_ID)
            target_id = int(self.ResolveAllyTarget(Blood_is_Power_ID, custom) or 0)
        except Exception:
            target_id = 0

        energy_pct = -1.0
        if target_id > 0:
            try:
                energy_pct = float(Agent.GetEnergy(target_id))
            except Exception:
                pass
        return int(target_id), float(energy_pct)

    def _log_successful_bip_cast(
        self,
        target_id: int,
        target_energy_before: float,
    ) -> None:
        """Record exactly where a successful BiP cast was aimed."""
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            in_combat, enemy_count, team_anchor = self._telemetry_combat_state()
            self_energy = float(Agent.GetEnergy(Player.GetAgentID()))
            primary_id, secondary_id = self._telemetry_professions(target_id)
            CombatDebug.log_event(
                "BIP_CAST_PROFILE",
                target_id=int(target_id or 0),
                target_name=str(self._telemetry_agent_name(target_id)),
                target_primary_profession=int(primary_id),
                target_secondary_profession=int(secondary_id),
                target_energy_before=f"{float(target_energy_before):.4f}",
                bip_self_energy=f"{float(self_energy):.4f}",
                in_combat=bool(in_combat),
                enemy_count=int(enemy_count),
                team_anchor=int(team_anchor),
            )
        except Exception:
            pass

    def _bip_target_waiting(self) -> bool:
        try:
            custom = self.GetCustomSkill(Blood_is_Power_ID)
            return int(self.ResolveAllyTarget(Blood_is_Power_ID, custom) or 0) > 0
        except Exception:
            return False

    def _enemy_count_in_combat_range(self) -> int:
        """Count live foes around the BiP, independent of packet adjacency.

        Recuperation is party sustain, so gating it on one Adjacent-size packet
        was too strict in spread-out fights such as Urgoz.
        """
        try:
            enemies = Routines.Agents.GetFoesInRange(Range.Spellcast.value) or []
            return sum(
                1
                for enemy_id in enemies
                if int(enemy_id or 0) > 0
                and Agent.IsValid(int(enemy_id))
                and Agent.IsAlive(int(enemy_id))
            )
        except Exception:
            try:
                from Py4GWCoreLib import AgentArray
                enemies = AgentArray.GetEnemyArray()
                enemies = AgentArray.Filter.ByDistance(
                    enemies, Player.GetXY(), Range.Spellcast.value
                )
                return sum(
                    1
                    for enemy_id in enemies or []
                    if Agent.IsValid(int(enemy_id)) and Agent.IsAlive(int(enemy_id))
                )
            except Exception:
                return 0

    def _urgent_bip_energy_need(self, threshold: float = 0.45) -> bool:
        """Do not spend the cast window on Recuperation if someone is critically low.

        Normal BiP duty (70% threshold) is attempted immediately before this
        check.  This guard is only for cases where BiP could not fire yet but an
        ally is genuinely energy-starved.
        """
        try:
            for ally_id in GetAllAlliesArray(Range.Spellcast.value) or []:
                ally_id = int(ally_id or 0)
                if ally_id <= 0 or not Agent.IsValid(ally_id) or not Agent.IsAlive(ally_id):
                    continue
                if float(Agent.GetEnergy(ally_id)) < float(threshold):
                    return True
        except Exception:
            pass
        return False

    def _try_recuperation_teamfight(self):
        """Keep Recuperation up for the whole duration of every real fight.

        BiP itself is still attempted immediately before this function in the
        priority chain.  Once combat exists, Recuperation is treated as a
        persistent team buff: if our Recuperation spirit is missing/dead and
        the skill is ready with enough energy, cast it.  BuildMgr's normal
        CanCastSkillID/SpiritBuffExists checks prevent duplicate recasts.
        """
        if not self.IsSkillEquipped(Recuperation_ID):
            return False

        # Do not rely on IsInAggro/IsCloseToAggro here. Support characters can
        # stand far enough behind the frontline that those flags stay false
        # even though the party is already fighting.
        enemy_count = self._enemy_count_in_combat_range()
        try:
            team_anchor = int(get_team_cluster_anchor() or 0)
        except Exception:
            team_anchor = 0

        combat_active = bool(enemy_count > 0 or team_anchor > 0)
        if not combat_active:
            return False

        # Blood Ritual priority is preserved because Blood is Power is evaluated before
        # this function.  If Recuperation cannot be paid for, CanCastSkillID
        # fails cleanly and the rest of the BiP rotation continues.
        if not self.CanCastSkillID(Recuperation_ID):
            return False

        did_cast = yield from self.CastSpiritSkillID(
            skill_id=Recuperation_ID,
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "BIP_RECUPERATION_FORCED_UP",
                    enemy_count=int(enemy_count),
                    team_anchor=int(team_anchor),
                    policy="keep_up_whenever_combat_active_after_bip",
                )
            except Exception:
                pass
            return True
        return False

    def _try_spirit_siphon_teamfight(self):
        if not self.IsSkillEquipped(Spirit_Siphon_ID):
            return False
        try:
            if Agent.GetEnergy(Player.GetAgentID()) >= 0.82:
                return False
        except Exception:
            pass
        return (yield from self.skills.Ritualist.ChannelingMagic.Spirit_Siphon(
            max_self_energy_pct=0.82, drain_cooldown_s=12.0,
            spirit_partition=1, spirit_partition_count=2
        ))

    def _try_team_packet_blood_bond(self):
        if not self.IsSkillEquipped(Blood_Bond_ID) or not self.CanCastSkillID(Blood_Bond_ID):
            return False
        target_id = int(pick_unhexed_blood_bond_target() or 0)
        if target_id <= 0:
            return False
        return (yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Blood_Bond_ID,
            target_agent_id=target_id,
            extra_condition=lambda: Routines.Checks.Agents.IsAlive(target_id) and not Agent.IsHexed(target_id),
            log=False,
            aftercast_delay=200,
        ))

    def _cast_technobabble_dangerous_caster(self):
        """Use Technobabble on any genuinely dangerous caster in team focus.

        Do NOT require the whole packet to already be classified as a
        dangerous-caster cluster. The previous version did that and could miss
        the exact cast window on the Necro client even though other clients
        detected the packet as dangerous.

        Candidate must:
        - belong to the authoritative team packet/cleanup focus
        - be alive and above 20% HP
        - be a caster threat or currently casting a dangerous skill

        Priority:
        current dangerous cast > caster score > offensive score > threat.
        """
        if not self.IsSkillEquipped(Technobabble_ID) or not self.CanCastSkillID(Technobabble_ID):
            return False

        try:
            from Py4GWCoreLib.Builds.Skills import CombatSense, EnemyKnowledge

            anchor = int(get_team_cluster_anchor(
                consumer_role="technobabble_necro",
            ) or 0)
            if anchor <= 0:
                return False

            members = get_team_cluster_members(anchor) or [anchor]
            sensed = {
                int(e.agent_id): e
                for e in CombatSense.refresh(
                    range_value=Range.Spellcast.value,
                    throttle_ms=45,
                )
            }

            ranked = []
            for aid in members:
                aid = int(aid or 0)
                e = sensed.get(aid)
                if e is None or not Routines.Checks.Agents.IsAlive(aid):
                    continue
                hp = float(e.health)
                if hp <= 0.20:
                    continue

                try:
                    roles = EnemyKnowledge.role_scores(aid)
                    caster = int(roles.get("caster", 0))
                    offense = int(roles.get("offense", 0))
                    healer = int(roles.get("healer", 0))
                except Exception:
                    caster = offense = healer = 0

                live_danger = bool(
                    e.is_casting
                    and int(e.casting_skill_id or 0) in CombatSense.AOE_SHUTDOWN_SKILL_IDS
                )

                # Much more practical than the old "2 dangerous casters in
                # packet" gate. One dangerous Ele/Mesmer is enough to justify
                # Technobabble.
                caster_threat = bool(
                    live_danger
                    or caster >= 55
                    or (
                        int(e.primary_profession) in (
                            int(getattr(Profession.Elementalist, "value", Profession.Elementalist)),
                            int(getattr(Profession.Mesmer, "value", Profession.Mesmer)),
                            int(getattr(Profession.Necromancer, "value", Profession.Necromancer)),
                            int(getattr(Profession.Monk, "value", Profession.Monk)),
                            int(getattr(Profession.Ritualist, "value", Profession.Ritualist)),
                        )
                        and int(e.threat_score) >= 55
                    )
                    or int(e.threat_score) >= 80
                )
                if not caster_threat:
                    continue

                ranked.append((
                    -int(live_danger),
                    -int(caster),
                    -int(offense),
                    -int(e.threat_score),
                    int(healer),
                    -hp,
                    aid,
                ))

            if not ranked:
                return False

            ranked.sort()
            target = int(ranked[0][6])
        except Exception:
            return False

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Technobabble_ID,
            target_agent_id=target,
            extra_condition=lambda tid=target: Routines.Checks.Agents.IsAlive(tid),
            log=False,
            aftercast_delay=120,
        )
        if did_cast:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "TECHNOBABBLE_DANGEROUS_CASTER",
                    target_id=int(target),
                    policy="single_dangerous_caster_in_authoritative_focus",
                )
            except Exception:
                pass
            return True
        return False

    def _cast_pain_inverter_best_target(self):
        """Selective but usable Pain Inverter for HM pressure.

        Keep it off trash, but do not require extreme threat scores. It may fire
        on a healthy enemy inside the authoritative team packet when that enemy
        is either:
          - actively casting a known dangerous damage/shutdown skill, OR
          - a clearly offensive/caster threat by EnemyKnowledge.

        Healers/passive support and nearly-dead enemies remain excluded.
        """
        if not self.IsSkillEquipped(Pain_Inverter_ID) or not self.CanCastSkillID(Pain_Inverter_ID):
            return False

        try:
            from Py4GWCoreLib.Builds.Skills import CombatSense, EnemyKnowledge

            anchor = int(get_team_cluster_anchor(
                consumer_role="pain_inverter_healer",
            ) or 0)
            if anchor <= 0:
                return False

            members = get_team_cluster_members(anchor) or [anchor]
            sensed = {
                int(e.agent_id): e
                for e in CombatSense.refresh(
                    range_value=Range.Spellcast.value,
                    throttle_ms=60,
                )
            }

            ranked = []
            for aid in members:
                aid = int(aid or 0)
                e = sensed.get(aid)
                if e is None or not Routines.Checks.Agents.IsAlive(aid):
                    continue

                hp = float(e.health)
                # Give Pain Inverter enough lifetime to return damage.
                if hp <= 0.30:
                    continue

                try:
                    roles = EnemyKnowledge.role_scores(aid)
                    healer = int(roles.get("healer", 0))
                    support = int(roles.get("support", 0))
                    caster = int(roles.get("caster", 0))
                    offense = int(roles.get("offense", 0))
                except Exception:
                    healer = support = caster = offense = 0

                current_skill = int(e.casting_skill_id or 0)
                dangerous_now = bool(
                    e.is_casting
                    and (
                        current_skill in CombatSense.AOE_SHUTDOWN_SKILL_IDS
                        or int(e.threat_score) >= 80
                        or offense >= 60
                        or caster >= 70
                    )
                )

                # Balanced gate: substantially lower than the previous
                # 115/90/100 thresholds, but still not generic filler.
                dangerous_profile = bool(
                    int(e.threat_score) >= 80
                    or offense >= 60
                    or caster >= 70
                )

                # Pure healer/passive support is still a bad Pain Inverter use.
                if healer >= 70 and not dangerous_now and offense < 70:
                    continue
                if support >= 110 and not dangerous_now and offense < 70 and caster < 80:
                    continue

                if not (dangerous_now or dangerous_profile):
                    continue

                ranked.append((
                    -int(dangerous_now),
                    -int(offense),
                    -int(e.threat_score),
                    -int(caster),
                    -hp,
                    aid,
                ))

            if not ranked:
                return False

            ranked.sort()
            target = int(ranked[0][5])
        except Exception:
            return False

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Pain_Inverter_ID,
            target_agent_id=target,
            extra_condition=lambda tid=target: Routines.Checks.Agents.IsAlive(tid),
            log=False,
            aftercast_delay=120,
        )
        if did_cast:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "PAIN_INVERTER_SMART_CAST",
                    target_id=int(target),
                    policy="balanced_dangerous_enemy_only",
                )
            except Exception:
                pass
            return True
        return False

    def _track_icy_veins_outcomes(self) -> None:
        """Read-only telemetry for Icy Veins death-proc quality."""
        if not getattr(self, "_icy_veins_last_targets", None):
            return
        try:
            from Py4GWCoreLib.Builds.Skills.DangerInterruptClaim import get_game_tick
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            now = int(get_game_tick() or 0)
        except Exception:
            return

        done = []
        for target_id, data in list(self._icy_veins_last_targets.items()):
            cast_tick, hp_at_cast, packet_size_at_cast = data
            alive = False
            try:
                alive = bool(Routines.Checks.Agents.IsAlive(int(target_id)))
            except Exception:
                alive = False

            # If the target died/disappeared soon after the cast, record how
            # useful the death packet still was at that moment.
            if not alive:
                nearby_alive = 0
                try:
                    from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import get_team_cluster_members
                    members = get_team_cluster_members(int(target_id), filter_range=Range.Spellcast.value) or []
                    for aid in members:
                        aid = int(aid or 0)
                        if aid <= 0 or aid == int(target_id):
                            continue
                        if Routines.Checks.Agents.IsAlive(aid):
                            nearby_alive += 1
                except Exception:
                    nearby_alive = 0

                CombatDebug.log_event(
                    "ICY_VEINS_TARGET_DIED",
                    target_id=int(target_id),
                    ms_after_cast=max(0, int(now) - int(cast_tick or 0)),
                    target_hp_at_cast=f"{float(hp_at_cast):.4f}",
                    packet_size_at_cast=int(packet_size_at_cast),
                    nearby_alive_at_death=int(nearby_alive),
                    policy="death_proc_quality",
                )
                done.append(target_id)
                continue

            # Stop tracking stale casts after 40 s; no useful death proc in window.
            if now > 0 and cast_tick > 0 and now - cast_tick > 40000:
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "ICY_VEINS_EXPIRED_NO_DEATH",
                        target_id=int(target_id),
                        target_hp_at_cast=f"{float(hp_at_cast):.4f}",
                        packet_size_at_cast=int(packet_size_at_cast),
                    )
                except Exception:
                    pass
                done.append(target_id)

        for target_id in done:
            self._icy_veins_last_targets.pop(int(target_id), None)

    def _log_icy_veins_cast(self, target_id: int) -> None:
        try:
            from Py4GWCoreLib.Builds.Skills.DangerInterruptClaim import get_game_tick
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            now = int(get_game_tick() or 0)
        except Exception:
            now = 0

        hp = -1.0
        packet_size = 0
        try:
            hp = float(Agent.GetHealth(int(target_id)))
        except Exception:
            pass
        try:
            members = get_team_cluster_members(int(target_id), filter_range=Range.Spellcast.value) or []
            packet_size = len(members)
        except Exception:
            packet_size = 0

        self._icy_veins_last_targets[int(target_id)] = (
            int(now),
            float(hp),
            int(packet_size),
        )
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "ICY_VEINS_CAST",
                target_id=int(target_id),
                target_hp=f"{float(hp):.4f}",
                packet_size=int(packet_size),
                policy="lowest_hp_member_of_authoritative_packet",
            )
        except Exception:
            pass

    def _run_local_skill_logic(self):
        refresh_aoe_danger_zones()
        self._track_icy_veins_outcomes()

        # Read-only telemetry. This does not influence the combat controller.
        self._track_team_energy()

        if not Routines.Checks.Skills.CanCast():
            return False

        pressure = self.IsInAggro()
        close_pressure = self.IsInAggro() or self.IsCloseToAggro()

        if self.IsSkillEquipped(Spirit_Light_ID) and (yield from self.skills.Ritualist.RestorationMagic.Spirit_Light(health_threshold=0.30)):
            return True
        if (yield from self.skills.Ritualist.RestorationMagic.Mend_Body_and_Soul(health_threshold=0.40)):
            return True

        # Optional safety energy support. Only feeds the real high-priority
        # consumers when they actually fall below 70% energy.
        if (yield from self._try_priority_blood_ritual()):
            return True

        if close_pressure and self.IsSkillEquipped(Air_of_Superiority_ID) and (yield from self.skills.Any.PvE.Air_of_Superiority()):
            return True

        if pressure and (yield from self._cast_pain_inverter_best_target()):
            return True

        # Offensive package for the Icy Veins variant.
        # Icy Veins is placed on the authoritative team focus, but preferably
        # on the lowest-health member of that same packet so its death trigger
        # is likely to fire while nearby enemies are still alive.
        # Dangerous-caster opener for the Necro:
        # Technobabble first (Dazed/control), then Icy Veins on the next pass.
        # This does not gate ST/Para/Mesmer actions on their own clients.
        if pressure and (yield from self._cast_technobabble_dangerous_caster()):
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "TECHNOBABBLE_BEFORE_ICY_VEINS",
                    policy="dangerous_caster_opener",
                )
            except Exception:
                pass
            return True

        if pressure and self.IsSkillEquipped(Icy_Veins_ID) and self.CanCastSkillID(Icy_Veins_ID):
            icy_target = 0
            try:
                anchor = int(get_team_cluster_anchor(consumer_role="icy_veins_healer") or 0)
                members = get_team_cluster_members(anchor) if anchor > 0 else []
                candidates = [int(eid) for eid in (members or [anchor]) if int(eid or 0) > 0 and Routines.Checks.Agents.IsAlive(int(eid))]
                if candidates:
                    candidates.sort(key=lambda eid: (float(Agent.GetHealth(eid)), int(eid)))
                    icy_target = int(candidates[0])
            except Exception:
                icy_target = 0
            if icy_target > 0:
                if (yield from self.CastSkillIDAndRestoreTarget(
                    skill_id=Icy_Veins_ID,
                    target_agent_id=icy_target,
                    extra_condition=lambda tid=icy_target: Routines.Checks.Agents.IsAlive(tid),
                    log=False,
                    aftercast_delay=150,
                )):
                    self._log_icy_veins_cast(int(icy_target))
                    return True

        if pressure and (yield from self._try_recuperation_teamfight()):
            return True

        if pressure and (yield from self._try_spirit_siphon_teamfight()):
            return True

        if pressure and (yield from self._try_team_packet_blood_bond()):
            return True

        if self.IsSkillEquipped(Life_ID) and (yield from self.skills.Ritualist.RestorationMagic.Life()):
            return True

        if (yield from self.skills.Ritualist.RestorationMagic.Mend_Body_and_Soul(cleanse_blind_martial=True)):
            return True
        if (yield from self.skills.Ritualist.RestorationMagic.Mend_Body_and_Soul(cleanse_cripple_melee=True)):
            return True

        if self.IsSkillEquipped(Spirit_Light_ID) and (yield from self.skills.Ritualist.RestorationMagic.Spirit_Light(health_threshold=0.68)):
            return True
        if (yield from self.skills.Ritualist.RestorationMagic.Mend_Body_and_Soul(health_threshold=0.75)):
            return True

        # Cheap offensive filler. Never invent a separate target: use the exact
        # authoritative cluster/cleanup focus shared by the rest of KeySoJway.
        if pressure and self.IsSkillEquipped(Necrosis_ID) and self.CanCastSkillID(Necrosis_ID):
            necrosis_target = 0
            try:
                necrosis_target = int(get_team_cluster_anchor(consumer_role="necrosis_healer") or 0)
            except Exception:
                necrosis_target = 0
            if necrosis_target > 0 and Routines.Checks.Agents.IsAlive(necrosis_target):
                # Necrosis only pays off on a hexed or conditioned foe.
                valid_necrosis = False
                try:
                    valid_necrosis = bool(Agent.IsHexed(necrosis_target) or Agent.IsConditioned(necrosis_target))
                except Exception:
                    try:
                        valid_necrosis = bool(Agent.IsHexed(necrosis_target))
                    except Exception:
                        valid_necrosis = False
                if valid_necrosis:
                    if (yield from self.CastSkillIDAndRestoreTarget(
                        skill_id=Necrosis_ID,
                        target_agent_id=necrosis_target,
                        extra_condition=lambda tid=necrosis_target: Routines.Checks.Agents.IsAlive(tid),
                        log=False,
                        aftercast_delay=100,
                    )):
                        return True

        return False

