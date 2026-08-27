from dataclasses import dataclass

from Py4GWCoreLib import Profession
from Py4GWCoreLib import Range
from Py4GWCoreLib import Routines
from Py4GWCoreLib.Builds.Any.HeroAI import HeroAI_Build
from Py4GWCoreLib import BuildMgr
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill
from Py4GWCoreLib.Skillbar import SkillBar
from Py4GWCoreLib.Builds.Skills import HexRemovalPriority, SkillsTemplate
from Py4GWCoreLib.Builds.Skills.KeystoneSoJMimicry import KeystoneSoJMimicry
from Py4GWCoreLib.Builds.Skills.AoEDangerPrediction import (
    avoid_active_aoe_if_needed,
    is_aoe_escape_safe_hold_active,
    is_position_in_active_aoe,
    refresh_aoe_danger_zones,
)
from Py4GWCoreLib.Builds.Skills.DangerInterruptClaim import (
    claim_best_dangerous_cast,
    clear_interrupt_approach_movement,
    danger_sort_key,
    get_casting_skill_id as get_danger_casting_skill_id,
    get_dangerous_casts_in_range,
    get_enemy_cast_remaining_ms,
    get_game_tick,
    interrupt_is_feasible,
    is_dangerous_cast,
    is_lethal_aoe_skill,
    has_dangerous_cast_in_range,
    mark_interrupt_approach_movement_active,
    post_interrupt_claim,
    release_interrupt_claim,
    target_still_casting_skill as danger_target_still_casting_skill,
)
from Py4GWCoreLib.Builds.Skills.ExecutionFocus import (
    is_execution_focus_target,
    pick_execution_focus_target,
)
from Py4GWCoreLib.Builds.Skills.CryOfFrustrationCoordination import (
    reserve_best_cry_packet,
    release_cry_reservation,
    register_cry_fired,
)

Symbolic_Celerity_ID = Skill.GetID("Symbolic_Celerity")
Symbolic_Posture_ID = Skill.GetID("Symbolic_Posture")
Keystone_Signet_ID = Skill.GetID("Keystone_Signet")
Unnatural_Signet_ID = Skill.GetID("Unnatural_Signet")
Signet_of_Clumsiness_ID = Skill.GetID("Signet_of_Clumsiness")
Smite_Hex_ID = Skill.GetID("Smite_Hex")
Hex_Eater_Signet_ID = Skill.GetID("Hex_Eater_Signet")
Castigation_Signet_ID = Skill.GetID("Castigation_Signet")
Bane_Signet_ID = Skill.GetID("Bane_Signet")
Signet_of_Rage_ID = Skill.GetID("Signet_of_Rage")
Breath_of_the_Great_Dwarf_ID = Skill.GetID("Breath_of_the_Great_Dwarf")
Blood_Ritual_ID = Skill.GetID("Blood_Ritual")
Animate_Bone_Fiend_ID = Skill.GetID("Animate_Bone_Fiend")
Animate_Bone_Horror_ID = Skill.GetID("Animate_Bone_Horror")
Animate_Bone_Minions_ID = Skill.GetID("Animate_Bone_Minions")
Animate_Flesh_Golem_ID = Skill.GetID("Animate_Flesh_Golem")
Animate_Shambling_Horror_ID = Skill.GetID("Animate_Shambling_Horror")
Animate_Vampiric_Horror_ID = Skill.GetID("Animate_Vampiric_Horror")
Death_Nova_ID = Skill.GetID("Death_Nova")
Cry_of_Frustration_ID = Skill.GetID("Cry_of_Frustration")
Power_Drain_ID = Skill.GetID("Power_Drain")
Tryptophan_Signet_ID = Skill.GetID("Tryptophan_Signet")
Signet_of_Sorrow_ID = Skill.GetID("Signet_of_Sorrow")
Signet_of_Disruption_ID = Skill.GetID("Signet_of_Disruption")
Signet_of_Weariness_ID = Skill.GetID("Signet_of_Weariness")
Signet_of_Corruption_Kurzick_ID = Skill.GetID("Signet_of_Corruption_kurzick")
Signet_of_Corruption_Luxon_ID = Skill.GetID("Signet_of_Corruption_luxon")
Arcane_Mimicry_ID = Skill.GetID("Arcane_Mimicry")
Signet_of_Judgment_ID = Skill.GetID("Signet_of_Judgment")
Air_of_Superiority_ID = Skill.GetID("Air_of_Superiority")
Mantra_of_Inscriptions_ID = Skill.GetID("Mantra_of_Inscriptions")
Mantra_of_Signets_ID = Skill.GetID("Mantra_of_Signets")
Mistrust_ID = Skill.GetID("Mistrust")

# Keystone Signet does NOT interrupt the foe directly targeted by the next
# signet. It interrupts every *other* foe adjacent to that target. Therefore an
# emergency Keystone interrupt needs a living proxy foe adjacent to the real
# dangerous caster. These foe-targeted signets are ordered by practical value;
# dedicated direct interrupts are still attempted before this proxy layer.
KEYSTONE_PROXY_INTERRUPT_SIGNET_ORDER = (
    Signet_of_Clumsiness_ID,
    Unnatural_Signet_ID,
    Signet_of_Sorrow_ID,
    Signet_of_Corruption_Kurzick_ID,
    Signet_of_Corruption_Luxon_ID,
    Signet_of_Weariness_ID,
    Tryptophan_Signet_ID,
    Castigation_Signet_ID,
    Bane_Signet_ID,
)

# Damage fallback for copied Signet of Judgment: if every valid target is already
# knocked down, still cast it when the target packet is valuable enough. This
# value counts total alive enemies in adjacent range, including the target.
SIGNET_OF_JUDGMENT_DAMAGE_CLUSTER_MIN = 2

# Signet of Sorrow becomes much stronger once enemies are standing near a
# corpse/dead pet.  Use a conservative nearby-radius check to prefer those
# targets first, but still allow Sorrow as fallback damage when Corruption and
# other packet signets are unavailable.
SORROW_CORPSE_SEARCH_RANGE = Range.Nearby.value
SORROW_CORPSE_TARGET_SCAN_THROTTLE_MS = 250

# Short per-skill/target locks reduce three Keystone Mesmers firing the same
# packet signet on the exact same enemy at the exact same moment.  This is
# intentionally short: it staggers casts without slowing the build down.
PACKET_SIGNET_TARGET_LOCK_MS = 900
# Shared cross-skill distribution key. All normal offensive Keystone signets
# use the same target lock so different signets from different Mesmers spread
# across members of the selected packet instead of piling onto one enemy.
# Emergency direct/proxy interrupts bypass this optimization.
KEYSTONE_SIGNET_DISTRIBUTION_LOCK_ID = 0x4B535447
MISTRUST_DISTRIBUTION_LOCK_ID = 0x4D495354
MISTRUST_TARGET_LOCK_MS = 6200
# SoJ uses occupancy levels instead of a single exclusive claim. This lets the
# first wave cover every cluster member once, then distributes extra casts as
# evenly as possible (3 targets / 4 casts -> 2/1/1) without ever blocking.
SOJ_BALANCED_CLAIM_BASE_ID = 0x534F4A30
SOJ_BALANCED_CLAIM_LEVELS = 8
SOJ_BALANCED_CLAIM_MS = 1750
# One short finisher claim lets a single Keystone Mesmer delete an isolated
# <=15% enemy while the other Mesmers keep applying packet pressure.
EXECUTION_FINISHER_LOCK_ID = 0x4558464E
EXECUTION_FINISHER_LOCK_MS = 850

# Signet of Disruption team coordination.
# The interrupt itself is never reserved: a dangerous valid activation gets
# first refusal, otherwise the signet can be spent as useful Keystone pressure.
# Shared skillbar readiness is used to let the next ready Mesmer go first.
DISRUPTION_AVAILABILITY_LOG_MS = 3000

# Setup ranges for Keystone Mesmers. Symbolic Celerity / Symbolic Posture / Air
# can be prepared a little earlier because their duration is not consumed by
# the short final approach into the pull. Arcane Mimicry starts its 20s copied
# SoJ window immediately after the copy succeeds, so it must not be cast from
# far away. It is now allowed a bit earlier than the previous very tight 0.65
# window, so the copied SoJ is already available when the Mesmers touch the
# enemy group, without wasting too much of the 20s timer while running in.
# Offensive signets still require normal spellcast-range targets.
SYMBOLIC_PRECAST_SETUP_RANGE = float(Range.Spellcast.value) * 0.90
KEYSTONE_PRECAST_SETUP_RANGE = float(Range.Spellcast.value) * 0.78

# Two-stance synchronization. A Mantra should not be paid/cast only to be
# cancelled by Symbolic Posture a fraction of a second later. Once the current
# signet packet is genuinely spent, hold the Mantra if the next
# Symbolic-Posture -> Keystone window is at most this far away.
MANTRA_SYMBOLIC_SYNC_WINDOW_MS = 3000

# Health telemetry is deliberately asynchronous and read-only: it never waits
# inside the combat rotation. We sample shortly after the signet's nominal
# activation completes. The observed delta is useful for A/B comparison but is
# explicitly not source-attributed (incoming damage/external heals can overlap).
SIGNET_HEALTH_PROBE_GRACE_MS = 250
SIGNET_HEALTH_PROBE_MIN_DELAY_MS = 350
SIGNET_HEALTH_PROBE_MAX_QUEUE = 24

# Team-wide damage focus. The Simple Power version should make Keystone Mesmers,
# the SoJ Monk and the Ineptitude Mesmer prefer the same enemy packet instead
# of splitting between two nearby groups. SoJ is treated primarily as AoE packet
# damage; fresh knockdown is a bonus, not a reason to hold the skill forever.
POWER_CLUSTER_MIN_ENEMIES = 2
POWER_CLUSTER_RADIUS = Range.Adjacent.value
POWER_CLUSTER_FILTER_RANGE = Range.Spellcast.value

# Tryptophan Signet is packet-control, not opening damage. Do not fire it
# into loose runners. First application requires a compact/settled packet;
# later applications may spread it to unhexed enemies inside the same packet.
TRYPTOPHAN_OPENING_MIN_CLUSTER_ENEMIES = 2
TRYPTOPHAN_REPEAT_MIN_CLUSTER_ENEMIES = 2
TRYPTOPHAN_SETTLED_MOVING_RATIO_MAX = 0.45
TRYPTOPHAN_CLOSE_CAST_DISTANCE = Range.Nearby.value

# Elite-mission override: in Urgoz' Warren the German "Krummrinde" is
# the English "Twisted Bark". These enemies maintain room-wide effects,
# so they should be killed before the normal Simple-Power cluster logic.
ELITE_PRIORITY_TARGET_NAMES = ("twisted bark", "krummrinde", "crooked bark")


# Bounded lethal-AoE interrupt approach.  A Mesmer may close only the small
# gap needed to enter casting range; it never chases deep into the enemy group.
INTERRUPT_APPROACH_DEFAULT_MAX_EXTRA = 420.0
INTERRUPT_APPROACH_DEFAULT_LEADER_TETHER = 1200.0
INTERRUPT_APPROACH_CAST_STANDOFF = float(Range.Spellcast.value) - 70.0
INTERRUPT_APPROACH_SCAN_RANGE = float(Range.Spellcast.value) + 500.0
INTERRUPT_APPROACH_MOVE_COOLDOWN_MS = 140
INTERRUPT_APPROACH_MOVEMENT_SPEED_GW_S = 288.0
INTERRUPT_APPROACH_PATH_FACTOR = 1.15
INTERRUPT_APPROACH_FINAL_MARGIN_MS = 120
INTERRUPT_APPROACH_ARRIVAL_PADDING = 25.0

# Crash-safe dangerous-skill priority. This intentionally avoids the heavy
# generic Skill.Data / profession / AoE metadata checks from the experimental
# dangerous-interrupt version. It only compares the enemy's current casting
# skill against a fixed allow-list of high-value skills. If any API lookup fails,
# this path simply returns False and falls back to the stable normal rotation.
_SAFE_DANGER_INTERRUPT_SKILL_NAMES = (
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

_SAFE_DANGER_INTERRUPT_SKILL_IDS = frozenset(
    int(skill_id)
    for skill_id in (Skill.GetID(name) for name in _SAFE_DANGER_INTERRUPT_SKILL_NAMES)
    if int(skill_id or 0) > 0
)

_SAFE_DANGER_INTERRUPT_PRIORITY = {
    skill_id: index for index, skill_id in enumerate(_SAFE_DANGER_INTERRUPT_SKILL_IDS)
}


@dataclass(slots=True)
class _KeystoneBarSnapshot:
    in_aggro: bool = False
    close_to_aggro: bool = False
    precombat_setup: bool = False
    symbolic_setup: bool = False
    has_symbolic_celerity: bool = False
    has_symbolic_posture: bool = False
    has_keystone_signet: bool = False
    enemy_casting: bool = False
    enemy_in_spellcast: bool = False
    attacking_enemy_in_spellcast: bool = False

    @property
    def symbolic_celerity_needed(self) -> bool:
        return not self.has_symbolic_celerity

    @property
    def symbolic_posture_needed(self) -> bool:
        return self.has_symbolic_celerity and not self.has_symbolic_posture

    @property
    def keystone_signet_needed(self) -> bool:
        return self.has_symbolic_celerity and not self.has_keystone_signet


@dataclass(slots=True)
class _InterruptApproachState:
    active: bool = False
    target_agent_id: int = 0
    cast_target_id: int = 0
    enemy_skill_id: int = 0
    our_skill_id: int = 0
    mode: str = "direct"
    started_tick: int = 0
    last_move_tick: int = 0
    destination: tuple[float, float] | None = None


class KeystoneSignet(BuildMgr):
    def __init__(self, match_only: bool = False):
        super().__init__(
            name="Keystone Signet",
            required_primary=Profession.Mesmer,
            template_code="OQITEZJZVSpYHEqQsGAAAAAAAAA",
            required_skills=[
                Symbolic_Celerity_ID,
                Keystone_Signet_ID,
                Unnatural_Signet_ID,
            ],
            optional_skills=[
                Symbolic_Posture_ID,
                Signet_of_Clumsiness_ID,
                Smite_Hex_ID,
                Hex_Eater_Signet_ID,
                Castigation_Signet_ID,
                Bane_Signet_ID,
                Signet_of_Rage_ID,
                Breath_of_the_Great_Dwarf_ID,
                Blood_Ritual_ID,
                Animate_Bone_Fiend_ID,
                Animate_Bone_Horror_ID,
                Animate_Bone_Minions_ID,
                Animate_Flesh_Golem_ID,
                Animate_Shambling_Horror_ID,
                Animate_Vampiric_Horror_ID,
                Death_Nova_ID,
                Cry_of_Frustration_ID,
                Power_Drain_ID,
                Tryptophan_Signet_ID,
                Signet_of_Sorrow_ID,
                Signet_of_Disruption_ID,
                Signet_of_Weariness_ID,
                Signet_of_Corruption_Kurzick_ID,
                Signet_of_Corruption_Luxon_ID,
                Arcane_Mimicry_ID,
                Signet_of_Judgment_ID,
                Air_of_Superiority_ID,
                Mantra_of_Inscriptions_ID,
                Mantra_of_Signets_ID,
                Mistrust_ID,
            ],
        )
        if match_only:
            return

        self.SetFallback("HeroAI", HeroAI_Build(standalone_fallback=True))
        self.SetSkillCastingFn(self._run_local_skill_logic)
        self.skills: SkillsTemplate = SkillsTemplate(self)
        self._soj_mimicry = KeystoneSoJMimicry()

        # Rotation state: Keystone may be pre-cast once before the pull, but the
        # reset part of the cycle should only happen after at least one real
        # non-Keystone signet has been spent. This prevents pointless Keystone
        # spam near a group and avoids resetting after zero useful signets.
        self._precombat_keystone_primed: bool = False
        self._non_keystone_signet_cast_since_last_keystone: bool = False
        self._interrupt_approach = _InterruptApproachState()
        # Zero-idle target cache: only avoids repeating the same full enemy scan
        # several times inside the same short decision window. It never blocks a
        # cast; stale/invalid targets are revalidated before use.
        self._zero_idle_cache_tick: int = 0
        self._zero_idle_cache_targets: tuple[int, ...] = ()
        self._disruption_opening_spent: bool = False

        # Signet of Disruption telemetry only; never influences combat behavior.
        self._sod_ready_since_tick: int = 0
        self._sod_was_ready: bool = False
        self._sod_last_sample_tick: int = 0
        self._sod_last_team_ready_count: int = -1

        # Full signet telemetry. Read-only instrumentation: these values never
        # participate in target selection, claims, priorities or casting.
        self._signet_ready_since: dict[int, int] = {}
        self._signet_was_ready: dict[int, bool] = {}
        self._signet_last_sample: dict[int, int] = {}
        self._mimicry_soj_equipped_since: int = 0
        self._mimicry_soj_was_equipped: bool = False
        # Rotation-stall diagnostics only.
        self._stall_last_log_tick: int = 0
        # Sorrow can instant-recharge near a corpse. Keep that turbo behavior,
        # but do not let an endless Sorrow chain starve already-ready Unnatural
        # or Corruption for 10-20 seconds (seen in live logs).
        self._sorrow_turbo_streak: int = 0

        # Keystone Mantra A/B telemetry. Both Mantra of Inscriptions and
        # Mantra of Signets are supported by the same controller. Only the
        # stance actually equipped on this account is used.
        self._mantra_active_id: int = 0
        self._mantra_active_since_tick: int = 0
        self._mantra_last_profile_signet_tick: int = 0
        self._mantra_profile_signet_count: int = 0
        self._mantra_conflict_logged: bool = False
        self._mantra_sync_last_log_tick: int = 0

        # Asynchronous health probes for the Mantra-of-Signets A/B test.
        # Entries are sampled later from _run_local_skill_logic; combat flow is
        # never blocked waiting for a heal measurement.
        self._signet_health_probe_seq: int = 0
        self._pending_signet_health_probes: list[dict] = []

    def _has_enemy_near_position(self, position: tuple[float, float] | None, max_distance: float) -> bool:
        if not position:
            return False

        max_distance_sq = max_distance * max_distance
        px, py = position

        try:
            from Py4GWCoreLib import AgentArray

            for enemy_id in AgentArray.GetEnemyArray() or []:
                try:
                    if not Agent.IsValid(enemy_id) or not Agent.IsAlive(enemy_id):
                        continue

                    enemy_pos = Agent.GetXY(enemy_id)
                    if not enemy_pos:
                        continue

                    dx = px - enemy_pos[0]
                    dy = py - enemy_pos[1]
                    if (dx * dx + dy * dy) <= max_distance_sq:
                        return True
                except Exception:
                    continue
        except Exception:
            return False

        return False

    def _has_enemy_near_player_or_leader(self, max_distance: float) -> bool:
        if self._has_enemy_near_position(Player.GetXY(), max_distance):
            return True

        try:
            from Py4GWCoreLib.Party import Party

            leader_id = int(Party.GetPartyLeaderID() or 0)
            if leader_id > 0 and Agent.IsValid(leader_id):
                if self._has_enemy_near_position(Agent.GetXY(leader_id), max_distance):
                    return True
        except Exception:
            pass

        return False

    def _is_symbolic_setup_needed(self) -> bool:
        # Symbolic Celerity, Symbolic Posture and Air of Superiority should be
        # prepared shortly before a pull, but not maintained permanently while
        # walking around with no enemy pressure nearby.
        if self.IsInAggro() or self.IsCloseToAggro():
            return True
        return self._has_enemy_near_player_or_leader(SYMBOLIC_PRECAST_SETUP_RANGE)

    def _is_precombat_setup_needed(self) -> bool:
        # Arcane Mimicry and the first Keystone prime are deliberately later
        # than the Symbolic/Air setup stage, but not as late as the previous
        # ultra-tight window. Arcane Mimicry copies immediately and the 20s SoJ
        # timer starts right away, so this is a near-contact compromise: early
        # enough to have copied SoJ ready on first contact, late enough to avoid
        # burning the timer while still running across open space.
        if self.IsInAggro() or self.IsCloseToAggro():
            return True
        return self._has_enemy_near_player_or_leader(KEYSTONE_PRECAST_SETUP_RANGE)

    def _get_bar_snapshot(self) -> _KeystoneBarSnapshot:
        player_id = Player.GetAgentID()
        in_aggro = bool(self.IsInAggro())
        close_to_aggro = in_aggro or self.IsCloseToAggro()
        symbolic_setup = close_to_aggro or self._is_symbolic_setup_needed()
        precombat_setup = close_to_aggro or self._is_precombat_setup_needed()
        snapshot = _KeystoneBarSnapshot(
            in_aggro=in_aggro,
            close_to_aggro=close_to_aggro,
            precombat_setup=precombat_setup,
            symbolic_setup=symbolic_setup,
            has_symbolic_celerity=Routines.Checks.Effects.HasBuff(player_id, Symbolic_Celerity_ID),
            has_symbolic_posture=Routines.Checks.Effects.HasBuff(player_id, Symbolic_Posture_ID),
            has_keystone_signet=Routines.Checks.Effects.HasBuff(player_id, Keystone_Signet_ID),
        )

        # Offensive signets still need an enemy in normal spellcast range. The
        # wider precombat setup only prepares the bar; it does not make the
        # Mesmers blow signets from spirit range.
        if not precombat_setup:
            return snapshot

        snapshot.enemy_in_spellcast = bool(Routines.Agents.GetNearestEnemy(Range.Spellcast.value))
        # Use the shared native-event candidate view as well as the legacy live
        # targeting query. This lets the emergency path enter on the earliest
        # Reforged cast signal while final claim/cast checks still require the
        # enemy to be genuinely casting.
        snapshot.enemy_casting = bool(
            has_dangerous_cast_in_range(Range.Spellcast.value)
            or Routines.Targeting.GetEnemyCasting(Range.Spellcast.value)
        )
        snapshot.attacking_enemy_in_spellcast = bool(Routines.Targeting.GetEnemyAttacking(Range.Spellcast.value))
        return snapshot

    @staticmethod
    def _skillbar_skill_ids(account) -> list[int]:
        agent_data = getattr(account, "AgentData", None)
        skillbar = getattr(agent_data, "Skillbar", None)
        skills = getattr(skillbar, "Skills", []) if skillbar is not None else []
        result: list[int] = []
        for skill in skills:
            try:
                skill_id = int(getattr(skill, "Id", 0) or 0)
            except Exception:
                skill_id = 0
            if skill_id > 0:
                result.append(skill_id)
        return result

    @staticmethod
    def _skillbar_has_skill(account, skill_id: int) -> bool:
        return int(skill_id) in KeystoneSignet._skillbar_skill_ids(account)

    @staticmethod
    def _skillbar_has_other_elite_than_signet_of_judgment(account) -> bool:
        """Prevent Arcane Mimicry from targeting temporary SoJ copies.

        Shared memory may expose a copied Signet of Judgment on another
        Mesmer/ally. If that ally's real elite is Keystone or another elite,
        Arcane Mimicry would copy that real elite instead of the desired SoJ.
        Therefore a valid donor must show SoJ and no other elite skill.
        """
        for skill_id in KeystoneSignet._skillbar_skill_ids(account):
            if skill_id == Signet_of_Judgment_ID:
                continue
            if skill_id == Keystone_Signet_ID:
                return True
            try:
                if Skill.Flags.IsElite(skill_id):
                    return True
            except Exception:
                continue
        return False

    def _is_valid_signet_of_judgment_mimicry_account(self, account) -> bool:
        if not self._skillbar_has_skill(account, Signet_of_Judgment_ID):
            return False

        # Hard safety rule: never use a donor whose visible bar contains
        # Keystone or any other elite besides Signet of Judgment. This stops
        # rare cases where Arcane Mimicry targets another Keystone Mesmer that
        # temporarily exposes a copied SoJ in shared memory.
        if self._skillbar_has_other_elite_than_signet_of_judgment(account):
            return False

        return True

    def _is_arcane_mimicry_donor_in_cast_range(self, target_agent_id: int) -> bool:
        try:
            return self._distance_to_player(int(target_agent_id)) <= float(Range.Spellcast.value)
        except Exception:
            return False

    def _is_valid_signet_of_judgment_mimicry_target(self, target_agent_id: int) -> bool:
        """Validate only the real-player SoJ account; heroes are never donors."""
        if target_agent_id <= 0 or target_agent_id == int(Player.GetAgentID() or 0):
            return False
        if not Routines.Checks.Agents.IsAlive(target_agent_id):
            return False
        if not self._is_arcane_mimicry_donor_in_cast_range(target_agent_id):
            return False
        for account in self._candidate_signet_of_judgment_accounts():
            agent_data = getattr(account, "AgentData", None)
            account_agent_id = int(getattr(agent_data, "AgentID", 0) or 0)
            if account_agent_id != int(target_agent_id):
                continue
            return bool(
                self._is_monk_profession_account(account)
                and self._is_valid_signet_of_judgment_mimicry_account(account)
            )
        return False


    def _is_monk_profession_account(self, account) -> bool:
        agent_data = getattr(account, "AgentData", None)
        professions = getattr(agent_data, "Profession", (0, 0))
        monk_value = int(getattr(Profession.Monk, "value", Profession.Monk))
        try:
            return int(professions[0] or 0) == monk_value or int(professions[1] or 0) == monk_value
        except Exception:
            return False

    def _candidate_signet_of_judgment_accounts(self):
        """Yield party players and their heroes that expose a shared skillbar.

        Arcane Mimicry must target the real Signet of Judgment holder. Shared
        memory can contain both account players and hero slots; this checks both.
        """
        from Py4GWCoreLib import GLOBAL_CACHE
        from Py4GWCoreLib.HeroAI.utils import SameMapOrPartyAsAccount

        own_party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
        seen_agent_ids: set[int] = set()

        for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
            if not getattr(account, "IsSlotActive", False) or getattr(account, "IsIsolated", False):
                continue
            if not SameMapOrPartyAsAccount(account):
                continue

            account_party_id = int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)
            if own_party_id > 0 and account_party_id != own_party_id:
                continue

            agent_data = getattr(account, "AgentData", None)
            owner_agent_id = int(getattr(agent_data, "AgentID", 0) or 0)
            if owner_agent_id > 0 and owner_agent_id not in seen_agent_ids:
                seen_agent_ids.add(owner_agent_id)
                yield account

            for hero_account in GLOBAL_CACHE.ShMem.GetHeroesFromPlayers(owner_agent_id) or []:
                if not getattr(hero_account, "IsSlotActive", False) or getattr(hero_account, "IsIsolated", False):
                    continue
                if not SameMapOrPartyAsAccount(hero_account):
                    continue

                hero_agent_data = getattr(hero_account, "AgentData", None)
                hero_agent_id = int(getattr(hero_agent_data, "AgentID", 0) or 0)
                if hero_agent_id <= 0 or hero_agent_id in seen_agent_ids:
                    continue
                seen_agent_ids.add(hero_agent_id)
                yield hero_account

    @staticmethod
    def _local_hero_skill_ids(hero_position: int) -> list[int]:
        """Read a regular local hero bar directly from the current Reforged API."""
        result: list[int] = []
        try:
            for hero_skill in SkillBar.GetHeroSkillbar(int(hero_position)) or []:
                try:
                    skill_id = int(getattr(getattr(hero_skill, "id", None), "id", 0) or 0)
                except Exception:
                    skill_id = 0
                if skill_id > 0:
                    result.append(skill_id)
        except Exception:
            pass
        return result

    @classmethod
    def _local_hero_is_real_soj_donor(cls, hero_position: int) -> bool:
        skills = cls._local_hero_skill_ids(hero_position)
        if Signet_of_Judgment_ID not in skills:
            return False
        # Arcane Mimicry copies the target's elite. Reject bars with another elite
        # so a temporary/shared SoJ observation cannot make us copy the wrong elite.
        for skill_id in skills:
            if skill_id == Signet_of_Judgment_ID:
                continue
            try:
                if Skill.Flags.IsElite(skill_id):
                    return False
            except Exception:
                continue
        return True

    def _find_local_hero_with_signet_of_judgment(self) -> int:
        """Fallback/direct path for ordinary heroes owned by this game client.

        Shared-memory hero publication can lag or omit a hero depending on the
        multibox topology. Reading Party + GetHeroSkillbar makes Mimicry work with
        a normal hero as the SoJ donor as requested by testers.
        """
        best_agent_id = 0
        best_distance = float("inf")
        try:
            heroes = Party.GetHeroes() or []
        except Exception:
            heroes = []

        # Hero positions in the current API are 1..7.
        for hero_position, hero in enumerate(heroes, start=1):
            try:
                agent_id = int(getattr(hero, "agent_id", 0) or 0)
            except Exception:
                agent_id = 0
            if agent_id <= 0:
                continue
            if not Routines.Checks.Agents.IsAlive(agent_id):
                continue
            if not self._local_hero_is_real_soj_donor(hero_position):
                continue
            try:
                distance = float(self._distance_to_player(agent_id))
            except Exception:
                continue
            if distance > float(Range.Spellcast.value):
                continue
            if distance < best_distance:
                best_distance = distance
                best_agent_id = agent_id
        return best_agent_id

    def _find_ally_with_signet_of_judgment(self) -> int:
        """Find ONLY a verified real-player SoJ donor from shared account data.

        Local Monk heroes are intentionally excluded so Arcane Mimicry can never
        copy Ray of Judgment or another hero elite.
        """
        own_agent_id = int(Player.GetAgentID() or 0)
        candidates: list[tuple[float, int]] = []
        for account in self._candidate_signet_of_judgment_accounts():
            agent_data = getattr(account, "AgentData", None)
            target_agent_id = int(getattr(agent_data, "AgentID", 0) or 0)
            if target_agent_id <= 0 or target_agent_id == own_agent_id:
                continue
            if not self._is_monk_profession_account(account):
                continue
            if not Routines.Checks.Agents.IsAlive(target_agent_id):
                continue
            if not self._is_arcane_mimicry_donor_in_cast_range(target_agent_id):
                continue
            if not self._is_valid_signet_of_judgment_mimicry_account(account):
                continue
            try:
                distance = float(self._distance_to_player(target_agent_id))
            except Exception:
                distance = float(Range.Spellcast.value)
            candidates.append((distance, target_agent_id))
        if not candidates:
            return 0
        candidates.sort(key=lambda item: (item[0], item[1]))
        return int(candidates[0][1])


    def _cast_arcane_mimicry_for_signet_of_judgment(self, snapshot: _KeystoneBarSnapshot):
        """Arcane Mimicry is hard-wired to the verified real-player SoJ Monk.

        No random Monk probing and no hero fallback are allowed.
        """
        try:
            self._soj_mimicry._update_context_and_observe()
        except Exception:
            pass

        if not snapshot.precombat_setup:
            return False
        if not self.IsSkillEquipped(Arcane_Mimicry_ID):
            return False

        # Already copied: never overwrite the copied elite.
        try:
            tracked_slot = int(getattr(self._soj_mimicry.state, "mimicry_slot", 0) or 0)
            if tracked_slot > 0:
                current_id = int(SkillBar.GetSkillIDBySlot(tracked_slot) or 0)
                if current_id and current_id != Arcane_Mimicry_ID:
                    return False
        except Exception:
            pass

        target_id = int(self._find_ally_with_signet_of_judgment() or 0)
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "MIMICRY_SOJ_GATE",
                donor_id=int(target_id),
                donor_found=bool(target_id > 0),
                arcane_ready=bool(self.CanCastSkillID(Arcane_Mimicry_ID)),
                precombat_setup=bool(snapshot.precombat_setup),
                policy="real_player_soj_only_no_hero_fallback",
            )
        except Exception:
            pass

        if target_id <= 0 or not self.CanCastSkillID(Arcane_Mimicry_ID):
            return False

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Arcane_Mimicry_ID,
            target_agent_id=int(target_id),
            extra_condition=lambda tid=int(target_id): (
                self._is_valid_signet_of_judgment_mimicry_target(tid)
            ),
            log=False,
            aftercast_delay=250,
        )
        if not did_cast:
            return False

        try:
            from time import monotonic
            self._soj_mimicry.state.begin_probe(int(target_id), now=monotonic())
        except Exception:
            pass
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "MIMICRY_SOJ_DONOR_CAST",
                target_id=int(target_id),
                policy="real_player_soj_only_no_hero_fallback",
            )
        except Exception:
            pass
        return True


    def _get_equipped_keystone_mantra_id(self) -> int:
        """Return the selected Mantra stance for this Keystone account.

        A character can only maintain one stance. If both Mantras are equipped
        accidentally, prefer Mantra of Inscriptions and emit a one-time debug
        marker so the bar configuration is visible in the combat log.
        """
        has_inscriptions = bool(
            Mantra_of_Inscriptions_ID > 0 and self.IsSkillEquipped(Mantra_of_Inscriptions_ID)
        )
        has_signets = bool(
            Mantra_of_Signets_ID > 0 and self.IsSkillEquipped(Mantra_of_Signets_ID)
        )
        if has_inscriptions and has_signets:
            if not self._mantra_conflict_logged:
                self._mantra_conflict_logged = True
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "KEYSTONE_MANTRA_CONFIG_CONFLICT",
                        selected_id=int(Mantra_of_Inscriptions_ID),
                        selected_name="Mantra_of_Inscriptions",
                        policy="one_stance_only_prefer_inscriptions",
                    )
                except Exception:
                    pass
            return int(Mantra_of_Inscriptions_ID)
        if has_inscriptions:
            return int(Mantra_of_Inscriptions_ID)
        if has_signets:
            return int(Mantra_of_Signets_ID)
        return 0

    def _active_keystone_mantra_id(self) -> int:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            return 0
        for mantra_id in (Mantra_of_Inscriptions_ID, Mantra_of_Signets_ID):
            mantra_id = int(mantra_id or 0)
            if mantra_id <= 0:
                continue
            try:
                if Routines.Checks.Effects.HasBuff(player_id, mantra_id):
                    return mantra_id
            except Exception:
                continue
        return 0

    @staticmethod
    def _keystone_mantra_name(mantra_id: int) -> str:
        mantra_id = int(mantra_id or 0)
        if mantra_id == int(Mantra_of_Inscriptions_ID):
            return "Mantra_of_Inscriptions"
        if mantra_id == int(Mantra_of_Signets_ID):
            return "Mantra_of_Signets"
        return "none"

    def _track_keystone_mantra_state(self) -> None:
        """Read-only stance uptime telemetry for the A/B test."""
        now = int(get_game_tick() or 0)
        if now <= 0:
            return
        active_id = int(self._active_keystone_mantra_id() or 0)
        previous_id = int(self._mantra_active_id or 0)
        if active_id == previous_id:
            return
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            if previous_id > 0:
                CombatDebug.log_event(
                    "KEYSTONE_MANTRA_UPTIME_END",
                    mantra_id=previous_id,
                    mantra_name=self._keystone_mantra_name(previous_id),
                    uptime_ms=max(0, now - int(self._mantra_active_since_tick or now)),
                )
            if active_id > 0:
                CombatDebug.log_event(
                    "KEYSTONE_MANTRA_UPTIME_START",
                    mantra_id=active_id,
                    mantra_name=self._keystone_mantra_name(active_id),
                )
        except Exception:
            pass
        self._mantra_active_id = active_id
        self._mantra_active_since_tick = now if active_id > 0 else 0

    def _skill_recharge_remaining_ms(self, skill_id: int) -> int:
        """Return live remaining recharge in milliseconds, or -1 if unknown."""
        skill_id = int(skill_id or 0)
        if skill_id <= 0 or not self.IsSkillEquipped(skill_id):
            return -1
        try:
            slot = int(SkillBar.GetSlotBySkillID(skill_id) or 0)
            if not (1 <= slot <= 8):
                return -1
            skill_data = SkillBar.GetSkillData(slot)
            return max(0, int(getattr(skill_data, "get_recharge", 0) or 0))
        except Exception:
            return -1

    def _should_defer_mantra_for_symbolic_sync(
        self, snapshot: _KeystoneBarSnapshot
    ) -> tuple[bool, int, int, int]:
        """Avoid a short-lived Mantra immediately before the next Posture reset.

        The defer is intentionally narrow: it is allowed only after the current
        non-Keystone signet packet has actually been spent/unusable. Therefore a
        ready damage signet is never held just to wait for Symbolic Posture.
        """
        if not snapshot.symbolic_setup or snapshot.has_symbolic_posture:
            return False, -1, -1, -1
        if not self.IsSkillEquipped(Symbolic_Posture_ID):
            return False, -1, -1, -1
        if not self.IsSkillEquipped(Keystone_Signet_ID):
            return False, -1, -1, -1
        # Keep this deliberately simple and low-risk. If Symbolic Posture +
        # Keystone will both be available within the narrow sync window, do not
        # spend 5E on a Mantra that would be cancelled almost immediately.
        # No target scans, packet walks or asynchronous work are performed here.

        posture_ms = int(self._skill_recharge_remaining_ms(Symbolic_Posture_ID))
        keystone_ms = int(self._skill_recharge_remaining_ms(Keystone_Signet_ID))
        if posture_ms < 0 or keystone_ms < 0:
            return False, posture_ms, keystone_ms, -1

        combo_ready_ms = max(posture_ms, keystone_ms)
        should_defer = bool(combo_ready_ms <= int(MANTRA_SYMBOLIC_SYNC_WINDOW_MS))
        return should_defer, posture_ms, keystone_ms, combo_ready_ms

    def _log_mantra_symbolic_sync_defer(
        self, posture_ms: int, keystone_ms: int, combo_ready_ms: int
    ) -> None:
        """Throttle stance-sync telemetry so a 3s wait does not flood the log."""
        now = int(get_game_tick() or 0)
        if now <= 0:
            return
        if now - int(self._mantra_sync_last_log_tick or 0) < 900:
            return
        self._mantra_sync_last_log_tick = now
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "KEYSTONE_MANTRA_SYNC_DEFER",
                symbolic_posture_recharge_ms=int(posture_ms),
                keystone_recharge_ms=int(keystone_ms),
                combo_ready_ms=int(combo_ready_ms),
                sync_window_ms=int(MANTRA_SYMBOLIC_SYNC_WINDOW_MS),
                policy="do_not_waste_mantra_before_imminent_symbolic_keystone",
            )
        except Exception:
            pass

    @staticmethod
    def _player_health_snapshot() -> tuple[float, int, int]:
        """Return (health_fraction, max_hp, current_hp) for telemetry only."""
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            return 0.0, 0, 0
        try:
            health_fraction = float(Agent.GetHealth(player_id) or 0.0)
        except Exception:
            health_fraction = 0.0
        try:
            max_hp = int(Agent.GetMaxHealth(player_id) or 0)
        except Exception:
            max_hp = 0
        health_fraction = max(0.0, min(1.0, health_fraction))
        current_hp = int(round(health_fraction * max_hp)) if max_hp > 0 else 0
        return health_fraction, max_hp, current_hp

    def _queue_signet_health_probe(
        self,
        *,
        skill_id: int,
        target_id: int,
        mantra_id: int,
        reason: str,
        path: str,
        health_fraction_before: float,
        max_hp_before: int,
        hp_before: int,
    ) -> int:
        """Queue a post-activation HP sample without delaying combat decisions."""
        now = int(get_game_tick() or 0)
        if now <= 0:
            return 0
        try:
            activation_ms = int(round(max(0.0, float(Skill.Data.GetActivation(skill_id))) * 1000.0))
        except Exception:
            activation_ms = 0
        sample_delay_ms = max(
            int(SIGNET_HEALTH_PROBE_MIN_DELAY_MS),
            int(activation_ms + SIGNET_HEALTH_PROBE_GRACE_MS),
        )

        self._signet_health_probe_seq += 1
        probe_id = int(self._signet_health_probe_seq)
        self._pending_signet_health_probes.append(
            {
                "probe_id": probe_id,
                "skill_id": int(skill_id),
                "target_id": int(target_id),
                "mantra_id": int(mantra_id),
                "reason": str(reason),
                "path": str(path),
                "cast_tick": int(now),
                "activation_ms": int(activation_ms),
                "due_tick": int(now + sample_delay_ms),
                "health_fraction_before": float(health_fraction_before),
                "max_hp_before": int(max_hp_before),
                "hp_before": int(hp_before),
            }
        )
        if len(self._pending_signet_health_probes) > int(SIGNET_HEALTH_PROBE_MAX_QUEUE):
            self._pending_signet_health_probes = self._pending_signet_health_probes[
                -int(SIGNET_HEALTH_PROBE_MAX_QUEUE):
            ]
        return probe_id

    def _process_pending_signet_health_probes(self) -> None:
        """Emit due post-cast HP samples; never blocks or changes cast priority."""
        if not self._pending_signet_health_probes:
            return
        now = int(get_game_tick() or 0)
        if now <= 0:
            return

        remaining: list[dict] = []
        due: list[dict] = []
        for probe in self._pending_signet_health_probes:
            if now >= int(probe.get("due_tick", now + 1) or now + 1):
                due.append(probe)
            else:
                remaining.append(probe)
        self._pending_signet_health_probes = remaining
        if not due:
            return

        health_fraction_after, max_hp_after, hp_after = self._player_health_snapshot()
        active_mantra_after = int(self._active_keystone_mantra_id() or 0)
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
        except Exception:
            return

        for probe in due:
            hp_before = int(probe.get("hp_before", 0) or 0)
            max_hp_before = int(probe.get("max_hp_before", 0) or 0)
            observed_delta_hp = int(hp_after - hp_before) if max_hp_after > 0 and max_hp_before > 0 else 0
            missing_hp_before = max(0, max_hp_before - hp_before)
            mantra_id = int(probe.get("mantra_id", 0) or 0)
            CombatDebug.log_event(
                "SIGNET_HEALTH_PROBE_RESULT",
                probe_id=int(probe.get("probe_id", 0) or 0),
                skill_id=int(probe.get("skill_id", 0) or 0),
                skill_name=str(self._telemetry_signet_name(int(probe.get("skill_id", 0) or 0))),
                target_id=int(probe.get("target_id", 0) or 0),
                reason=str(probe.get("reason", "")),
                path=str(probe.get("path", "")),
                mantra_id=int(mantra_id),
                mantra_name=self._keystone_mantra_name(mantra_id),
                mantra_of_signets_at_cast=bool(mantra_id == int(Mantra_of_Signets_ID)),
                mantra_id_at_sample=int(active_mantra_after),
                mantra_name_at_sample=self._keystone_mantra_name(active_mantra_after),
                cast_to_sample_ms=max(0, now - int(probe.get("cast_tick", now) or now)),
                nominal_activation_ms=int(probe.get("activation_ms", 0) or 0),
                health_fraction_before=float(probe.get("health_fraction_before", 0.0) or 0.0),
                health_fraction_after=float(health_fraction_after),
                hp_before=int(hp_before),
                hp_after=int(hp_after),
                max_hp_before=int(max_hp_before),
                max_hp_after=int(max_hp_after),
                missing_hp_before=int(missing_hp_before),
                observed_delta_hp=int(observed_delta_hp),
                observed_positive_delta_hp=max(0, int(observed_delta_hp)),
                source_attribution="observed_delta_not_source_attributed",
            )

    def _should_gate_signet_spend_for_mantra(
        self,
        snapshot: _KeystoneBarSnapshot,
        should_reset_signets: bool,
        should_cast_keystone: bool,
    ) -> bool:
        """Hold the first signet for a ready Mantra setup, never for cooldown.

        Symbolic Posture is also a stance, so it and a Mantra cannot coexist.
        If a Keystone prime/reset is pending, let Symbolic Posture -> Keystone
        happen first. The Mantra is then applied immediately before the damage
        signet packet. If the Mantra itself is on recharge, normal signet DPS is
        never stalled waiting for it.
        """
        mantra_id = int(self._get_equipped_keystone_mantra_id() or 0)
        if mantra_id <= 0 or not snapshot.symbolic_setup:
            return False
        if self._active_keystone_mantra_id() == mantra_id:
            return False
        if snapshot.has_symbolic_posture or should_reset_signets or should_cast_keystone:
            return True
        return bool(self._is_skill_strictly_ready(mantra_id))

    def _cast_keystone_mantra_setup(
        self, snapshot: _KeystoneBarSnapshot, *, reason: str = "pre_signet_packet"
    ):
        """Apply the equipped Mantra immediately before the signet burst.

        This deliberately waits until Symbolic Posture has been consumed by the
        Keystone prime/reset so the two stances do not cancel each other.
        """
        if not snapshot.symbolic_setup:
            return False
        mantra_id = int(self._get_equipped_keystone_mantra_id() or 0)
        if mantra_id <= 0:
            return False
        if self._active_keystone_mantra_id() == mantra_id:
            return False
        if snapshot.has_symbolic_posture:
            return False
        if not self._is_skill_strictly_ready(mantra_id):
            return False

        defer, posture_ms, keystone_ms, combo_ready_ms = (
            self._should_defer_mantra_for_symbolic_sync(snapshot)
        )
        if defer:
            self._log_mantra_symbolic_sync_defer(
                posture_ms, keystone_ms, combo_ready_ms
            )
            return False

        did_cast = False
        if mantra_id == int(Mantra_of_Inscriptions_ID):
            did_cast = yield from self.skills.Mesmer.InspirationMagic.Mantra_of_Inscriptions()
        elif mantra_id == int(Mantra_of_Signets_ID):
            did_cast = yield from self.skills.Mesmer.InspirationMagic.Mantra_of_Signets()
        if not did_cast:
            return False

        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "KEYSTONE_MANTRA_CAST",
                mantra_id=int(mantra_id),
                mantra_name=self._keystone_mantra_name(mantra_id),
                reason=str(reason),
                symbolic_posture_equipped=bool(self.IsSkillEquipped(Symbolic_Posture_ID)),
                policy="symbolic_posture_then_keystone_then_mantra_then_signets",
            )
        except Exception:
            pass
        return True

    def _cast_air_of_superiority_setup(self, snapshot: _KeystoneBarSnapshot):
        """Keep Air of Superiority active before the Keystone signet burst starts.

        Air is not treated as part of the signet spending cycle. It is a
        snowball setup buff: cast it in the Symbolic setup window shortly before the first offensive packet
        and refresh it only when the normal PvE helper says the effect is absent
        or about to expire. If Air randomly recharges the bar after kills, the
        existing Keystone rotation will naturally spend ready signets again
        before using Keystone as the next reset.
        """
        if not snapshot.symbolic_setup:
            return False
        if not self.IsSkillEquipped(Air_of_Superiority_ID):
            return False
        return (yield from self.skills.Any.PvE.Air_of_Superiority())


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

    def _get_player_enemy_target(self) -> int:
        try:
            target_agent_id = int(Player.GetTargetID() or 0)
        except Exception:
            return 0
        if self._is_valid_power_cluster_enemy(target_agent_id):
            return target_agent_id
        return 0

    def _single_target_cleanup_target(self) -> int:
        """Return the sole relevant enemy in offensive range, otherwise 0.

        This is intentionally strict: cleanup mode activates only when exactly
        one valid enemy remains in the normal offensive scan. It removes AoE /
        enemy-casting gates from safe foe-targeted damage signets, but does not
        relax interrupt, heal, or conditional-control requirements.
        """
        try:
            from Py4GWCoreLib import AgentArray
            enemies = [
                int(agent_id)
                for agent_id in (AgentArray.GetEnemyArray() or [])
                if self._is_valid_power_cluster_enemy(int(agent_id))
            ]
        except Exception:
            enemies = []

        if len(enemies) != 1:
            return 0

        only_enemy = int(enemies[0])
        # Manual target receives preference only if it is that same valid
        # remaining enemy; there is no force-target behaviour here.
        player_target = self._get_player_enemy_target()
        if player_target == only_enemy:
            return int(player_target)
        return only_enemy


    def _get_zero_idle_enemy_targets(self, *, cache_ms: int = 140) -> tuple[int, ...]:
        """Return ONLY members of the authoritative team focus packet.

        In cleanup this is exactly one target. If the team resolver has no
        target, return an empty tuple; never fall back to another enemy.
        """
        try:
            from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import (
                get_team_cluster_anchor,
                get_team_cluster_members,
            )
            anchor = int(get_team_cluster_anchor(
                filter_range=Range.Spellcast.value,
                minimum_enemies=POWER_CLUSTER_MIN_ENEMIES,
                consumer_role="keystone_zero_idle_pool",
            ) or 0)
            if anchor <= 0:
                return ()
            members = tuple(
                int(aid) for aid in get_team_cluster_members(
                    anchor,
                    filter_range=Range.Spellcast.value,
                )
                if int(aid or 0) > 0 and self._is_valid_power_cluster_enemy(int(aid))
            )
            return tuple(sorted(set(members or (anchor,))))
        except Exception:
            return ()

    def _get_zero_idle_damage_target(self, skill_id: int) -> tuple[int, str]:
        """Immediate signet target inside the one authoritative team focus only."""
        targets = self._get_zero_idle_enemy_targets()
        if not targets:
            return 0, "no_authoritative_target"

        anchor = int(self._get_power_cluster_anchor() or 0)
        # Cleanup/single target: every Mesmer must hit the exact same enemy.
        if len(targets) <= 1:
            return int(targets[0]), "hard_cleanup_focus"

        # Packet mode: distribution is allowed ONLY among members of this packet.
        target_set = set(int(x) for x in targets)
        try:
            if int(skill_id) == int(Unnatural_Signet_ID):
                preferred = int(self._get_offensive_signet_target(claim_target=True) or 0)
            else:
                preferred = int(self._get_monk_damage_signet_target(int(skill_id), claim_target=True) or 0)
        except Exception:
            preferred = 0
        if preferred in target_set and self._is_valid_power_cluster_enemy(preferred):
            return int(preferred), "distributed_inside_authoritative_packet"

        # Claims may all be occupied. Do not leave the packet: use the canonical
        # anchor if valid, otherwise the lowest valid member.
        if anchor in target_set and self._is_valid_power_cluster_enemy(anchor):
            return int(anchor), "packet_claim_bypass_anchor"
        return int(min(targets)), "packet_claim_bypass_member"

    def _is_elite_priority_target(self, target_agent_id: int) -> bool:
        if not self._is_valid_power_cluster_enemy(target_agent_id):
            return False
        try:
            name = str(Agent.GetNameByID(int(target_agent_id)) or "").strip().lower()
        except Exception:
            return False
        return any(priority_name in name for priority_name in ELITE_PRIORITY_TARGET_NAMES)

    def _get_elite_priority_target(self) -> int:
        """Hard-focus mission objects like Urgoz Twisted Bark before packs.

        This is intentionally name-based and tiny: it only overrides the
        cluster target if the special target is alive and in normal offensive
        range. Otherwise the usual Simple-Power cluster spike is unchanged.
        """


        player_target = self._get_player_enemy_target()
        if player_target and self._is_elite_priority_target(player_target):
            return int(player_target)

        try:
            from Py4GWCoreLib import AgentArray
            enemies = AgentArray.GetEnemyArray()
            enemies = AgentArray.Filter.ByDistance(enemies, Player.GetXY(), POWER_CLUSTER_FILTER_RANGE)
            enemies = AgentArray.Filter.ByCondition(
                enemies,
                lambda agent_id: self._is_elite_priority_target(int(agent_id)),
            )
            candidates = [int(agent_id) for agent_id in enemies or []]
        except Exception:
            candidates = []

        if not candidates:
            return 0

        candidates.sort(key=lambda agent_id: (
            -self._count_signet_of_judgment_adjacent_enemies(agent_id) if hasattr(self, '_count_signet_of_judgment_adjacent_enemies') else -self._count_adjacent_enemies(agent_id) if hasattr(self, '_count_adjacent_enemies') else -self._count_nearby_alive_enemies(agent_id, POWER_CLUSTER_RADIUS),
            self._distance_to_player(agent_id),
            int(agent_id),
        ))
        return int(candidates[0])

    def _get_power_cluster_anchor(self, *, minimum_enemies: int = POWER_CLUSTER_MIN_ENEMIES) -> int:
        """Use the one authoritative KeySoJway packet/cleanup resolver."""
        try:
            from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import get_team_cluster_anchor
            return int(get_team_cluster_anchor(
                filter_range=POWER_CLUSTER_FILTER_RANGE,
                minimum_enemies=int(minimum_enemies),
                consumer_role="keystone_mesmer",
            ) or 0)
        except Exception:
            return 0


    def _get_power_cluster_members(self, anchor_agent_id: int) -> list[int]:
        if not self._is_valid_power_cluster_enemy(anchor_agent_id):
            return []
        try:
            from Py4GWCoreLib import AgentArray
            enemies = AgentArray.GetEnemyArray()
            enemies = AgentArray.Filter.ByDistance(enemies, Agent.GetXY(anchor_agent_id), POWER_CLUSTER_RADIUS)
            enemies = AgentArray.Filter.ByCondition(
                enemies,
                lambda agent_id: self._is_valid_power_cluster_enemy(int(agent_id)),
            )
            members = [int(agent_id) for agent_id in enemies or []]
        except Exception:
            members = [int(anchor_agent_id)]

        if int(anchor_agent_id) not in members:
            members.append(int(anchor_agent_id))

        members = [agent_id for agent_id in members if self._is_valid_power_cluster_enemy(agent_id)]
        members.sort(key=lambda agent_id: (
            self._distance_to_player(agent_id),
            int(agent_id),
        ))
        return members

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

    def _is_attacking_enemy_safe(self, agent_id: int) -> bool:
        try:
            return bool(Routines.Checks.Agents.IsAttacking(agent_id))
        except Exception:
            try:
                return bool(Agent.IsAttacking(agent_id))
            except Exception:
                return False

    def _is_execution_finisher_claimed(self, target_agent_id: int) -> bool:
        if int(target_agent_id or 0) <= 0:
            return False
        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength, WhiteboardLockKind, WhiteboardLockMode,
                WhiteboardReentryPolicy,
            )
            now_tick = self._get_game_tick()
            if now_tick <= 0:
                return False
            shmem = GLOBAL_CACHE.ShMem
            if hasattr(shmem, 'SweepExpiredIntents'):
                shmem.SweepExpiredIntents(now_tick)
            return bool(shmem.IsLockBlocked(
                int(WhiteboardLockKind.SKILL_TARGET),
                int(EXECUTION_FINISHER_LOCK_ID),
                int(target_agent_id),
                self._get_signet_of_judgment_group_id(),
                str(Player.GetAccountEmail() or '').strip(),
                now_tick,
                int(WhiteboardLockMode.EXCLUSIVE),
                1,
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            ))
        except Exception:
            return False

    def _claim_execution_finisher(self, target_agent_id: int) -> bool:
        if int(target_agent_id or 0) <= 0 or self._is_execution_finisher_claimed(target_agent_id):
            return False
        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength, WhiteboardLockKind, WhiteboardLockMode,
                WhiteboardReentryPolicy,
            )
            now_tick = self._get_game_tick()
            if now_tick <= 0:
                return True
            return GLOBAL_CACHE.ShMem.PostLock(
                str(Player.GetAccountEmail() or '').strip(),
                int(WhiteboardLockKind.SKILL_TARGET),
                int(EXECUTION_FINISHER_LOCK_ID),
                int(target_agent_id),
                now_tick + int(EXECUTION_FINISHER_LOCK_MS),
                self._get_signet_of_judgment_group_id(),
                int(WhiteboardLockMode.EXCLUSIVE),
                1,
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            ) != -1
        except Exception:
            # Fail-open preserves damage if shared memory is unavailable.
            return True

    def _get_execution_finisher_target(self) -> int:
        target = int(pick_execution_focus_target(
            range_value=POWER_CLUSTER_FILTER_RANGE,
            health_threshold=0.15,
        ) or 0)
        if target <= 0:
            return 0
        if self._is_execution_finisher_claimed(target):
            return 0
        return target if self._claim_execution_finisher(target) else 0

    def _get_offensive_signet_target(self, *, claim_target: bool = True) -> int:
        # One Mesmer cleanly finishes an isolated <=15% enemy. The other
        # Mesmers continue damaging the best cluster instead of overkilling it.
        finisher = self._get_execution_finisher_target()
        if finisher:
            return int(finisher)

        # Use the same packet distribution lock for every normal offensive
        # signet. This keeps all Mesmers inside one valuable cluster while
        # spreading their individual signets over different packet members.
        target_agent_id = self._get_packet_signet_target(
            Unnatural_Signet_ID,
            claim_target=bool(claim_target),
        )
        if target_agent_id:
            return int(target_agent_id)
        # A real packet exists but all of its members are briefly reserved by
        # other Keystone signets. Do not bypass the shared lock and pile onto
        # one target; let the rotation continue and retry after the short lock.
        if self._get_power_cluster_anchor():
            return 0
        return 0

    def _get_attacking_power_cluster_target(self, *, claim_target: bool = True) -> int:
        anchor_agent_id = self._get_power_cluster_anchor()
        if anchor_agent_id:
            attacking = [
                int(enemy_id) for enemy_id in self._get_power_cluster_members(anchor_agent_id)
                if self._is_attacking_enemy_safe(enemy_id)
            ]
            attacking.sort(key=lambda enemy_id: (
                1 if self._is_packet_signet_target_claimed(Unnatural_Signet_ID, enemy_id) else 0,
                -self._count_signet_of_judgment_adjacent_enemies(enemy_id),
                self._distance_to_player(enemy_id),
                enemy_id,
            ))
            for enemy_id in attacking:
                if self._is_packet_signet_target_claimed(Unnatural_Signet_ID, enemy_id):
                    continue
                if claim_target and not self._claim_packet_signet_target(Unnatural_Signet_ID, enemy_id):
                    continue
                return int(enemy_id)
            # Keep distribution strict inside a real cluster. A short retry is
            # better than bypassing the lock and duplicating another signet.
            return 0
        try:
            fallback = int(Routines.Targeting.GetEnemyAttacking(Range.Spellcast.value) or 0)
        except Exception:
            fallback = 0
        if fallback and (not claim_target or self._claim_packet_signet_target(Unnatural_Signet_ID, fallback)):
            return fallback
        return 0

    @staticmethod
    def _is_moving_enemy_safe(agent_id: int) -> bool:
        try:
            return bool(Agent.IsMoving(int(agent_id)))
        except Exception:
            return False

    @staticmethod
    def _has_tryptophan_effect(agent_id: int) -> bool:
        try:
            return bool(Routines.Checks.Agents.HasEffect(int(agent_id), Tryptophan_Signet_ID))
        except Exception:
            return False

    def _is_tryptophan_opening_window(self, anchor_agent_id: int, members: list[int]) -> bool:
        """Return True only when the first Tryptophan cast will hit a real packet.

        This prevents the Ebon slow hex from being spent on one or two early
        runners and splitting the pull. A compact packet is accepted when it is
        already fighting/settled, or when it is still moving but close enough to
        the party to be treated as one incoming group.
        """
        if not anchor_agent_id or len(members) < TRYPTOPHAN_OPENING_MIN_CLUSTER_ENEMIES:
            return False

        # If the packet already has Tryptophan, allow spreading/refreshing it.
        if any(self._has_tryptophan_effect(agent_id) for agent_id in members):
            return True

        if any(self._is_attacking_enemy_safe(agent_id) for agent_id in members):
            return True

        moving_count = sum(1 for agent_id in members if self._is_moving_enemy_safe(agent_id))
        moving_ratio = float(moving_count) / max(1.0, float(len(members)))
        if moving_ratio <= TRYPTOPHAN_SETTLED_MOVING_RATIO_MAX:
            return True

        # Accept a fully moving packet only once it is already close to the team.
        # This covers enemies running into the ball without tagging only the
        # first straggler at the edge of spellcast range.
        return self._distance_to_player(anchor_agent_id) <= float(TRYPTOPHAN_CLOSE_CAST_DISTANCE)

    def _count_tryptophan_adjacent_enemies(self, target_agent_id: int) -> int:
        if target_agent_id <= 0:
            return 0
        try:
            from Py4GWCoreLib import AgentArray

            enemies = AgentArray.GetEnemyArray()
            enemies = AgentArray.Filter.ByDistance(enemies, Agent.GetXY(target_agent_id), Range.Adjacent.value)
            enemies = AgentArray.Filter.ByCondition(
                enemies,
                lambda agent_id: self._is_valid_power_cluster_enemy(int(agent_id)),
            )
            return int(len(enemies or []))
        except Exception:
            try:
                return int(Routines.Targeting.CountNearbyEnemies(target_agent_id, Range.Adjacent.value) or 0)
            except Exception:
                return 0

    def _get_tryptophan_signet_target(self) -> int:
        if not self.IsSkillEquipped(Tryptophan_Signet_ID):
            return 0
        if not self.CanCastSkillID(Tryptophan_Signet_ID):
            return 0

        anchor_agent_id = self._get_power_cluster_anchor(minimum_enemies=POWER_CLUSTER_MIN_ENEMIES)
        if not anchor_agent_id:
            return 0

        members = self._get_power_cluster_members(anchor_agent_id)
        if not members:
            return 0

        affected_members = [agent_id for agent_id in members if self._has_tryptophan_effect(agent_id)]
        affected_count = len(affected_members)

        if affected_count <= 0 and not self._is_tryptophan_opening_window(anchor_agent_id, members):
            return 0

        minimum_cluster = (
            TRYPTOPHAN_REPEAT_MIN_CLUSTER_ENEMIES
            if affected_count > 0
            else TRYPTOPHAN_OPENING_MIN_CLUSTER_ENEMIES
        )
        candidates = [
            agent_id for agent_id in members
            if self._count_tryptophan_adjacent_enemies(agent_id) >= minimum_cluster
        ]
        if not candidates:
            return 0

        # Once the packet is already tagged, spread the hex to an untagged
        # member inside the same adjacent group instead of refreshing the same
        # target immediately. If every member is tagged, refresh on the best
        # packet center.
        if affected_count > 0:
            untagged = [agent_id for agent_id in candidates if not self._has_tryptophan_effect(agent_id)]
            if untagged:
                candidates = untagged

        def rank(agent_id: int) -> tuple[int, int, int, float, int]:
            has_tryptophan = 1 if self._has_tryptophan_effect(agent_id) else 0
            moving = 1 if self._is_moving_enemy_safe(agent_id) else 0
            return (
                has_tryptophan,
                -self._count_tryptophan_adjacent_enemies(agent_id),
                moving,
                self._distance_to_player(agent_id),
                int(agent_id),
            )

        candidates.sort(key=rank)
        return int(candidates[0])

    @staticmethod
    def _get_game_tick() -> int:
        try:
            import Py4GW
            return int(Py4GW.Game.get_tick_count64() or 0)
        except Exception:
            return 0

    def _get_signet_of_judgment_group_id(self) -> int:
        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
            if party_id > 0:
                return party_id

            own_email = str(Player.GetAccountEmail() or '').strip()
            if own_email:
                for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
                    if str(getattr(account, 'AccountEmail', '') or '').strip() != own_email:
                        continue
                    return int(getattr(account, 'IsolationGroupID', 0) or 0)
        except Exception:
            pass
        return 0

    @staticmethod
    def _soj_balanced_lock_id(level: int) -> int:
        return int(SOJ_BALANCED_CLAIM_BASE_ID) + max(0, int(level))

    def _get_signet_of_judgment_claim_count(self, target_agent_id: int) -> int:
        """Return the number of short active SoJ reservations on a target.

        Each occupancy level has its own lock id.  This stays compatible with
        the existing shared-memory API while allowing balanced duplicate casts
        instead of a binary claimed/unclaimed decision.
        """
        if int(target_agent_id or 0) <= 0:
            return SOJ_BALANCED_CLAIM_LEVELS
        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength, WhiteboardLockKind, WhiteboardLockMode,
                WhiteboardReentryPolicy,
            )
            shmem = GLOBAL_CACHE.ShMem
            now_tick = self._get_game_tick()
            if now_tick <= 0:
                return 0
            if hasattr(shmem, 'SweepExpiredIntents'):
                shmem.SweepExpiredIntents(now_tick)
            count = 0
            for level in range(SOJ_BALANCED_CLAIM_LEVELS):
                if shmem.IsLockBlocked(
                    int(WhiteboardLockKind.SKILL_TARGET),
                    self._soj_balanced_lock_id(level),
                    int(target_agent_id),
                    self._get_signet_of_judgment_group_id(),
                    str(Player.GetAccountEmail() or '').strip(),
                    now_tick,
                    int(WhiteboardLockMode.EXCLUSIVE),
                    1,
                    int(WhiteboardReentryPolicy.NON_REENTRANT),
                    int(WhiteboardClaimStrength.HARD),
                ):
                    count += 1
            return count
        except Exception:
            return 0

    def _is_signet_of_judgment_target_claimed(self, target_agent_id: int) -> bool:
        return self._get_signet_of_judgment_claim_count(target_agent_id) > 0

    def _claim_signet_of_judgment_target(self, target_agent_id: int) -> bool:
        """Reserve the next free occupancy level; never block a valid SoJ cast."""
        if int(target_agent_id or 0) <= 0:
            return False
        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength, WhiteboardLockKind, WhiteboardLockMode,
                WhiteboardReentryPolicy,
            )
            shmem = GLOBAL_CACHE.ShMem
            now_tick = self._get_game_tick()
            if now_tick <= 0:
                return True
            if hasattr(shmem, 'SweepExpiredIntents'):
                shmem.SweepExpiredIntents(now_tick)
            for level in range(SOJ_BALANCED_CLAIM_LEVELS):
                lock_id = self._soj_balanced_lock_id(level)
                blocked = shmem.IsLockBlocked(
                    int(WhiteboardLockKind.SKILL_TARGET), lock_id, int(target_agent_id),
                    self._get_signet_of_judgment_group_id(),
                    str(Player.GetAccountEmail() or '').strip(), now_tick,
                    int(WhiteboardLockMode.EXCLUSIVE), 1,
                    int(WhiteboardReentryPolicy.NON_REENTRANT),
                    int(WhiteboardClaimStrength.HARD),
                )
                if blocked:
                    continue
                if hasattr(shmem, 'PostLock'):
                    posted = shmem.PostLock(
                        str(Player.GetAccountEmail() or '').strip(),
                        int(WhiteboardLockKind.SKILL_TARGET), lock_id, int(target_agent_id),
                        now_tick + int(SOJ_BALANCED_CLAIM_MS),
                        self._get_signet_of_judgment_group_id(),
                        int(WhiteboardLockMode.EXCLUSIVE), 1,
                        int(WhiteboardReentryPolicy.NON_REENTRANT),
                        int(WhiteboardClaimStrength.HARD),
                    )
                    if posted != -1:
                        return True
            # More simultaneous casts than tracked levels is extremely unlikely;
            # damage uptime still wins, so allow the cast without a reservation.
            return True
        except Exception:
            return True

    def _is_packet_signet_target_claimed(self, skill_id: int, target_agent_id: int) -> bool:
        if int(skill_id or 0) <= 0 or int(target_agent_id or 0) <= 0:
            return False

        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength,
                WhiteboardLockKind,
                WhiteboardLockMode,
                WhiteboardReentryPolicy,
            )

            now_tick = self._get_game_tick()
            if now_tick <= 0:
                return False
            shmem = GLOBAL_CACHE.ShMem
            if hasattr(shmem, 'SweepExpiredIntents'):
                shmem.SweepExpiredIntents(now_tick)
            return bool(shmem.IsLockBlocked(
                int(WhiteboardLockKind.SKILL_TARGET),
                int(KEYSTONE_SIGNET_DISTRIBUTION_LOCK_ID),
                int(target_agent_id),
                self._get_signet_of_judgment_group_id(),
                str(Player.GetAccountEmail() or '').strip(),
                now_tick,
                int(WhiteboardLockMode.EXCLUSIVE),
                1,
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            ))
        except Exception:
            return False

    def _claim_packet_signet_target(self, skill_id: int, target_agent_id: int, *, lock_ms: int = PACKET_SIGNET_TARGET_LOCK_MS) -> bool:
        if int(skill_id or 0) <= 0 or int(target_agent_id or 0) <= 0:
            return False
        if self._is_packet_signet_target_claimed(skill_id, target_agent_id):
            return False

        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength,
                WhiteboardLockKind,
                WhiteboardLockMode,
                WhiteboardReentryPolicy,
            )

            now_tick = self._get_game_tick()
            if now_tick <= 0:
                return True
            return GLOBAL_CACHE.ShMem.PostLock(
                str(Player.GetAccountEmail() or '').strip(),
                int(WhiteboardLockKind.SKILL_TARGET),
                int(KEYSTONE_SIGNET_DISTRIBUTION_LOCK_ID),
                int(target_agent_id),
                now_tick + int(lock_ms),
                self._get_signet_of_judgment_group_id(),
                int(WhiteboardLockMode.EXCLUSIVE),
                1,
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            ) != -1
        except Exception:
            # Fail-open: target staggering is optimization only.  If shared memory
            # is unavailable, do not block the damage rotation.
            return True

    def _is_mistrust_target_claimed(self, target_agent_id: int) -> bool:
        if int(target_agent_id or 0) <= 0:
            return False
        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength, WhiteboardLockKind, WhiteboardLockMode,
                WhiteboardReentryPolicy,
            )
            now_tick = self._get_game_tick()
            if now_tick <= 0:
                return False
            shmem = GLOBAL_CACHE.ShMem
            if hasattr(shmem, 'SweepExpiredIntents'):
                shmem.SweepExpiredIntents(now_tick)
            return bool(shmem.IsLockBlocked(
                int(WhiteboardLockKind.SKILL_TARGET),
                int(MISTRUST_DISTRIBUTION_LOCK_ID),
                int(target_agent_id),
                self._get_signet_of_judgment_group_id(),
                str(Player.GetAccountEmail() or '').strip(),
                now_tick,
                int(WhiteboardLockMode.EXCLUSIVE),
                1,
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            ))
        except Exception:
            return False

    def _claim_mistrust_target(self, target_agent_id: int) -> bool:
        if int(target_agent_id or 0) <= 0:
            return False
        if self._is_mistrust_target_claimed(target_agent_id):
            return False
        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            from Py4GWCoreLib.enums_src.Whiteboard_enums import (
                WhiteboardClaimStrength, WhiteboardLockKind, WhiteboardLockMode,
                WhiteboardReentryPolicy,
            )
            now_tick = self._get_game_tick()
            if now_tick <= 0:
                return True
            return GLOBAL_CACHE.ShMem.PostLock(
                str(Player.GetAccountEmail() or '').strip(),
                int(WhiteboardLockKind.SKILL_TARGET),
                int(MISTRUST_DISTRIBUTION_LOCK_ID),
                int(target_agent_id),
                now_tick + int(MISTRUST_TARGET_LOCK_MS),
                self._get_signet_of_judgment_group_id(),
                int(WhiteboardLockMode.EXCLUSIVE),
                1,
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            ) != -1
        except Exception:
            return True

    def _get_mistrust_target(self) -> tuple[int, str]:
        """Select a useful, non-duplicated Mistrust target.

        Mistrust is deliberately *not* a zero-idle filler.  It is only spent on
        a foe that is currently casting or on a high-confidence caster profile
        likely to cast soon.  Teamwide claims and the local tracker remain hard
        for Mistrust, because duplicating the hex on one foe usually wastes a
        slot while another caster remains uncovered.
        """
        anchor = int(self._get_power_cluster_anchor() or 0)
        if anchor <= 0:
            return 0, "no_cluster"

        active_candidates = []
        predictive_candidates = []
        for enemy_id in self._get_power_cluster_members(anchor):
            try:
                health = float(Agent.GetHealth(enemy_id))
                if health <= 0.15:
                    continue
            except Exception:
                health = 1.0

            # Unlike damage signets, Mistrust claims are intentionally hard:
            # never stack it just to avoid idle time.
            if self._is_mistrust_target_claimed(enemy_id):
                continue
            try:
                from Py4GWCoreLib.Builds.Skills import MistrustTracker
                if MistrustTracker.is_target_tracked(enemy_id):
                    continue
            except Exception:
                pass

            try:
                casting = bool(Agent.IsCasting(enemy_id))
            except Exception:
                casting = False

            primary, secondary = self._get_enemy_professions_safe(enemy_id)
            try:
                caster_prof_ids = {
                    int(getattr(Profession.Monk, 'value', Profession.Monk)),
                    int(getattr(Profession.Mesmer, 'value', Profession.Mesmer)),
                    int(getattr(Profession.Necromancer, 'value', Profession.Necromancer)),
                    int(getattr(Profession.Elementalist, 'value', Profession.Elementalist)),
                    int(getattr(Profession.Ritualist, 'value', Profession.Ritualist)),
                }
                caster_prof = primary in caster_prof_ids or secondary in caster_prof_ids
            except Exception:
                caster_prof = False

            try:
                from Py4GWCoreLib.Builds.Skills import EnemyKnowledge
                knowledge_priority = int(EnemyKnowledge.mistrust_priority(enemy_id))
            except Exception:
                knowledge_priority = 0

            adjacent = int(self._count_signet_of_judgment_adjacent_enemies(enemy_id))
            distance = float(self._distance_to_player(enemy_id))
            score = (
                -knowledge_priority,
                -adjacent,
                distance,
                -health,
                int(enemy_id),
            )

            if casting:
                active_candidates.append((score, int(enemy_id)))
            elif caster_prof and knowledge_priority >= 20:
                # Predictive opening/uptime cast: only known, worthwhile casters.
                # This allows early coverage without throwing Mistrust onto melee
                # or unknown enemies where it is likely to expire unused.
                predictive_candidates.append((score, int(enemy_id)))

        selected_pool = active_candidates if active_candidates else predictive_candidates
        reason = "active_caster" if active_candidates else "predictive_known_caster"
        selected_pool.sort(key=lambda item: item[0])
        for _, enemy_id in selected_pool:
            if self._claim_mistrust_target(enemy_id):
                return int(enemy_id), reason
        return 0, "no_useful_unclaimed_target"


    def _has_corpse_near_agent(self, target_agent_id: int, *, radius: float = SORROW_CORPSE_SEARCH_RANGE) -> bool:
        if int(target_agent_id or 0) <= 0:
            return False
        try:
            from Py4GWCoreLib.Py4GWcorelib import Utils

            target_xy = Agent.GetXY(int(target_agent_id))
            for corpse_id in Routines.Agents.GetCorpses(float(POWER_CLUSTER_FILTER_RANGE) + float(radius)) or []:
                try:
                    if int(corpse_id or 0) <= 0 or not Agent.IsValid(int(corpse_id)):
                        continue
                    if Utils.Distance(target_xy, Agent.GetXY(int(corpse_id))) <= float(radius):
                        return True
                except Exception:
                    continue
        except Exception:
            return False
        return False

    def _rank_packet_signet_targets(self, anchor_agent_id: int, *, skill_id: int, require_corpse: bool = False) -> list[int]:
        members = self._get_power_cluster_members(anchor_agent_id) if anchor_agent_id else []
        if not members and anchor_agent_id:
            members = [int(anchor_agent_id)]
        members = [agent_id for agent_id in members if self._is_valid_power_cluster_enemy(agent_id)]
        if not members:
            return []

        if require_corpse:
            members = [agent_id for agent_id in members if self._has_corpse_near_agent(agent_id)]
            if not members:
                return []

        def rank(agent_id: int) -> tuple[int, int, int, int, int, float, int]:
            claimed = 1 if self._is_packet_signet_target_claimed(int(skill_id), int(agent_id)) else 0
            corpse = 1 if self._has_corpse_near_agent(int(agent_id)) else 0
            dangerous = 1 if self._is_safe_dangerous_cast(int(agent_id)) else 0
            support = 1 if self._is_monk_or_ritualist_enemy(int(agent_id)) else 0
            adjacent_count = self._count_signet_of_judgment_adjacent_enemies(int(agent_id))
            return (
                claimed,            # prefer an unclaimed member for short stagger
                -corpse,            # corpse-adjacent first for Sorrow instant recharge chance
                -dangerous,         # then dangerous casts/support inside the packet
                -support,
                -adjacent_count,    # then best packet center / AoE value
                self._distance_to_player(int(agent_id)),
                int(agent_id),
            )

        members.sort(key=rank)
        return members

    def _get_packet_signet_target(self, skill_id: int, *, require_corpse: bool = False, claim_target: bool = False) -> int:
        anchor_agent_id = self._get_power_cluster_anchor()
        if not anchor_agent_id:
            return 0

        ranked = self._rank_packet_signet_targets(anchor_agent_id, skill_id=int(skill_id), require_corpse=require_corpse)
        if not ranked:
            return 0

        # In real packets, spread all normal offensive signets across
        # different members using one shared cross-skill lock.  In cleanup/single-target mode, allow the same
        # target so the team keeps finishing instead of waiting for no reason.
        packet_size = self._count_signet_of_judgment_adjacent_enemies(anchor_agent_id)
        if packet_size >= POWER_CLUSTER_MIN_ENEMIES:
            for target_agent_id in ranked:
                if self._is_packet_signet_target_claimed(int(skill_id), int(target_agent_id)):
                    continue
                if claim_target and not self._claim_packet_signet_target(int(skill_id), int(target_agent_id)):
                    continue
                return int(target_agent_id)
            return 0

        target_agent_id = int(ranked[0])
        if claim_target:
            self._claim_packet_signet_target(int(skill_id), target_agent_id)
        return target_agent_id

    def _get_sorrow_signet_target(self, *, require_corpse: bool, claim_target: bool) -> int:
        if not self.IsSkillEquipped(Signet_of_Sorrow_ID):
            return 0
        return self._get_packet_signet_target(
            Signet_of_Sorrow_ID,
            require_corpse=bool(require_corpse),
            claim_target=bool(claim_target),
        )

    def _get_monk_damage_signet_target(self, skill_id: int, *, claim_target: bool = True) -> int:
        """Fast target selection for Castigation/Bane Signet.

        Prefer an attacking member of the shared cluster because both Monk
        signets gain their full conditional value there.  Never idle waiting
        for an attacker: if none is available, immediately spend the signet on
        the best free member of the same packet.  The existing cross-skill
        packet claim spreads Castigation and Bane across different foes.
        """
        anchor_agent_id = int(self._get_power_cluster_anchor() or 0)
        if anchor_agent_id <= 0:
            return 0
        ranked = self._rank_packet_signet_targets(anchor_agent_id, skill_id=int(skill_id))
        if not ranked:
            return 0

        attacking = []
        fallback = []
        for target_agent_id in ranked:
            try:
                is_attacking = bool(Agent.IsAttacking(int(target_agent_id)))
            except Exception:
                is_attacking = False
            (attacking if is_attacking else fallback).append(int(target_agent_id))

        packet_size = self._count_signet_of_judgment_adjacent_enemies(anchor_agent_id)
        ordered = attacking + fallback
        if packet_size >= POWER_CLUSTER_MIN_ENEMIES:
            for target_agent_id in ordered:
                if self._is_packet_signet_target_claimed(int(skill_id), int(target_agent_id)):
                    continue
                if claim_target and not self._claim_packet_signet_target(int(skill_id), int(target_agent_id)):
                    continue
                return int(target_agent_id)
            return 0

        target_agent_id = int(ordered[0])
        if claim_target:
            self._claim_packet_signet_target(int(skill_id), target_agent_id)
        return target_agent_id

    def _is_signet_of_judgment_base_target_usable(self, target_agent_id: int, *, check_claimed: bool = True) -> bool:
        if target_agent_id <= 0:
            return False

        try:
            if not Agent.IsValid(target_agent_id):
                return False
            if not Agent.IsAlive(target_agent_id):
                return False
        except Exception:
            return False

        if check_claimed and self._is_signet_of_judgment_target_claimed(target_agent_id):
            return False

        return True

    @staticmethod
    def _is_signet_of_judgment_target_knocked_down(target_agent_id: int) -> bool:
        try:
            return bool(Routines.Checks.Agents.IsKnockedDown(target_agent_id))
        except Exception:
            return False

    def _count_signet_of_judgment_adjacent_enemies(self, target_agent_id: int) -> int:
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

    def _is_signet_of_judgment_control_target_usable(self, target_agent_id: int, *, check_claimed: bool = True) -> bool:
        if not self._is_signet_of_judgment_base_target_usable(target_agent_id, check_claimed=check_claimed):
            return False
        return not self._is_signet_of_judgment_target_knocked_down(target_agent_id)

    def _is_signet_of_judgment_damage_target_usable(self, target_agent_id: int, *, check_claimed: bool = False) -> bool:
        if not self._is_signet_of_judgment_base_target_usable(target_agent_id, check_claimed=check_claimed):
            return False
        return self._count_signet_of_judgment_adjacent_enemies(target_agent_id) >= SIGNET_OF_JUDGMENT_DAMAGE_CLUSTER_MIN

    def _is_signet_of_judgment_cast_target_usable(self, target_agent_id: int) -> bool:
        if not self._is_signet_of_judgment_base_target_usable(target_agent_id, check_claimed=False):
            return False
        if self._distance_to_player(target_agent_id) > float(POWER_CLUSTER_FILTER_RANGE):
            return False
        if self._is_elite_priority_target(target_agent_id):
            return True
        if is_execution_focus_target(target_agent_id):
            return True

        # Simple Power behavior: SoJ is primarily an AoE packet damage skill,
        # but copied SoJ should still be spent on cleanup/single targets when
        # no real packet is available. In single-target mode the Whiteboard
        # claim staggers multiple Keystone Mesmers onto the same enemy instead
        # of wasting all casts in the exact same moment.
        return True

    def _score_signet_of_judgment_target(self, target_agent_id: int, player_pos):
        try:
            from Py4GWCoreLib.Py4GWcorelib import Utils
            distance = Utils.Distance(player_pos, Agent.GetXY(target_agent_id))
        except Exception:
            distance = 0
        nearby_count = self._count_signet_of_judgment_adjacent_enemies(target_agent_id)
        try:
            from Py4GWCoreLib.Builds.Skills import EnemyKnowledge
            threat = int(EnemyKnowledge.threat_bonus(target_agent_id))
        except Exception:
            threat = 0
        return (-nearby_count, -threat, distance)

    def _pick_signet_of_judgment_target(self, validator, *, check_claimed_for_picker: bool) -> int:
        try:
            target_agent_id = Routines.Targeting.PickClusteredTarget(
                cluster_radius=Range.Adjacent.value,
                preferred_condition=lambda agent_id: validator(
                    int(agent_id),
                    check_claimed=check_claimed_for_picker,
                ),
                filter_radius=Range.Spellcast.value,
            )
            if target_agent_id:
                return int(target_agent_id)
        except Exception:
            pass

        try:
            from Py4GWCoreLib import AgentArray

            player_pos = Player.GetXY()
            enemies = AgentArray.GetEnemyArray()
            enemies = AgentArray.Filter.ByDistance(enemies, player_pos, Range.Spellcast.value)
            enemies = AgentArray.Filter.ByCondition(
                enemies,
                lambda agent_id: validator(
                    int(agent_id),
                    check_claimed=check_claimed_for_picker,
                ),
            )
            if not enemies:
                return 0

            return int(sorted(enemies, key=lambda agent_id: self._score_signet_of_judgment_target(int(agent_id), player_pos))[0])
        except Exception:
            return 0

    def _rank_signet_of_judgment_cluster_members(self, anchor_agent_id: int) -> list[int]:
        members = self._get_power_cluster_members(anchor_agent_id)
        if not members:
            return []

        def rank(agent_id: int) -> tuple[int, int, int, float, int]:
            claimed = self._get_signet_of_judgment_claim_count(agent_id)
            dangerous = 1 if self._is_safe_dangerous_cast(agent_id) else 0
            support = 1 if self._is_monk_or_ritualist_enemy(agent_id) else 0
            standing = 1 if not self._is_signet_of_judgment_target_knocked_down(agent_id) else 0
            return (
                claimed,          # lowest occupancy first, then balanced duplicate casts
                -dangerous,       # dangerous cast inside the packet first
                -support,         # then Monk/Ritu inside the packet
                -standing,        # then fresh KD if available
                self._distance_to_player(agent_id),
                int(agent_id),
            )

        members.sort(key=rank)
        return members

    def _get_signet_of_judgment_target(self, *, claim_target: bool = False) -> int:
        def claim_or_zero(target_agent_id: int) -> int:
            if not target_agent_id:
                return 0
            if claim_target and not self._claim_signet_of_judgment_target(target_agent_id):
                return 0
            return int(target_agent_id)

        priority_target = self._get_elite_priority_target()
        if priority_target and self._is_signet_of_judgment_cast_target_usable(priority_target):
            # Mission-priority targets should be deleted first. These are treated
            # like shared single-target mode: everyone stays on the priority
            # target, but the claim staggers copied SoJ casts.
            return claim_or_zero(priority_target)

        # Team packet mode: choose the same enemy group as the team. If there is
        # a real packet, reserve different members inside the packet so copied
        # SoJ pressure is spread across the ball. If only one/scattered target is
        # available, all Keystone Mesmers use the same anchor and the Whiteboard
        # claim simply staggers the casts instead of blocking SoJ completely.
        anchor_agent_id = self._get_power_cluster_anchor()
        if anchor_agent_id and self._is_signet_of_judgment_cast_target_usable(anchor_agent_id):
            members = self._rank_signet_of_judgment_cluster_members(anchor_agent_id)
            packet_size = self._count_signet_of_judgment_adjacent_enemies(anchor_agent_id)

            if packet_size < SIGNET_OF_JUDGMENT_DAMAGE_CLUSTER_MIN or len(members) <= 1:
                return claim_or_zero(anchor_agent_id)

            for target_agent_id in members:
                if not self._is_signet_of_judgment_cast_target_usable(target_agent_id):
                    continue
                claimed_target = claim_or_zero(target_agent_id)
                if claimed_target:
                    return claimed_target

            # Every useful member is already claimed. Damage uptime is more
            # important than a perfect stagger: immediately fall back to the
            # best valid member instead of idling until the short claim expires.
            for target_agent_id in members:
                if self._is_signet_of_judgment_cast_target_usable(target_agent_id):
                    return int(target_agent_id)
            return int(anchor_agent_id)

        # No authoritative team target: do not peel to another enemy.
        return 0

    def _cast_copied_signet_of_judgment(self, snapshot: _KeystoneBarSnapshot):
        if not self.IsSkillEquipped(Signet_of_Judgment_ID):
            return False
        if not snapshot.enemy_in_spellcast:
            return False

        target_agent_id = self._get_signet_of_judgment_target(claim_target=True)
        if not target_agent_id:
            return False

        cast_condition = lambda: self._is_signet_of_judgment_cast_target_usable(target_agent_id)

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Signet_of_Judgment_ID,
            target_agent_id=target_agent_id,
            extra_condition=cast_condition,
            log=False,
            aftercast_delay=250,
        )
        if did_cast:
            self._note_non_keystone_signet_cast()
            self._log_primary_signet_cast(
                Signet_of_Judgment_ID,
                target_agent_id,
                reason="copied_soj_aggressive_cluster_or_cleanup",
                path="mimicry_copied_soj",
            )
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                current_target = int(Player.GetTargetID() or 0)
                CombatDebug.log_event(
                    "MIMICRY_SOJ_CAST",
                    target_id=int(target_agent_id),
                    current_target_after_cast=int(current_target),
                    target_is_valid_enemy=bool(target_agent_id > 0 and Routines.Checks.Agents.IsAlive(target_agent_id)),
                    copied_window_age_ms=(
                        max(0, int(get_game_tick() or 0) - int(self._mimicry_soj_equipped_since))
                        if self._mimicry_soj_equipped_since > 0 else -1
                    ),
                )
            except Exception:
                pass
            try:
                from Py4GWCoreLib.Builds.Skills import Telemetry
                Telemetry.count("keystone.copied_soj_cast")
            except Exception:
                pass
        return did_cast

    @staticmethod
    def _get_safe_casting_skill_id(target_agent_id: int) -> int:
        return get_danger_casting_skill_id(target_agent_id)

    def _is_safe_dangerous_cast(self, target_agent_id: int) -> bool:
        return is_dangerous_cast(target_agent_id)

    def _safe_danger_interrupt_sort_key(self, target_agent_id: int, player_pos):
        return danger_sort_key(target_agent_id, player_pos)

    def _pick_safe_dangerous_interrupt_target(self, *, interrupter_skill_id: int = 0, validator=None) -> tuple[int, int]:
        return claim_best_dangerous_cast(
            range_value=Range.Spellcast.value,
            interrupter_skill_id=int(interrupter_skill_id or 0),
            validator=validator,
        )

    def _target_still_casting_safe_skill(self, target_agent_id: int, casting_skill_id: int) -> bool:
        return danger_target_still_casting_skill(target_agent_id, casting_skill_id)

    def _is_keystone_proxy_target_usable(
        self,
        proxy_agent_id: int,
        dangerous_caster_id: int,
        signet_skill_id: int,
    ) -> bool:
        """True when a foe-targeted signet will proc Keystone onto the caster."""
        proxy_agent_id = int(proxy_agent_id or 0)
        dangerous_caster_id = int(dangerous_caster_id or 0)
        signet_skill_id = int(signet_skill_id or 0)
        if proxy_agent_id <= 0 or dangerous_caster_id <= 0 or signet_skill_id <= 0:
            return False
        if proxy_agent_id == dangerous_caster_id:
            # Keystone affects all *other* adjacent foes, not the signet target.
            return False
        if not self._is_valid_power_cluster_enemy(proxy_agent_id):
            return False
        try:
            if not Agent.IsValid(dangerous_caster_id) or not Agent.IsAlive(dangerous_caster_id):
                return False
            from Py4GWCoreLib.Py4GWcorelib import Utils
            if Utils.Distance(Agent.GetXY(proxy_agent_id), Agent.GetXY(dangerous_caster_id)) > float(Range.Adjacent.value):
                return False
        except Exception:
            return False
        # The signet's own conditional rider may be weak on this proxy, but
        # Keystone still triggers because the signet targets a foe. Emergency
        # interrupt value therefore overrides normal damage/attack conditions.
        return True

    def _keystone_adjacent_danger_casts(self, signet_target_id: int) -> list[tuple[int, int]]:
        """Return dangerous casts Keystone would interrupt around this target.

        Keystone affects every *other* foe adjacent to the signet target.  The
        target itself is intentionally excluded, even when it is casting.
        """
        signet_target_id = int(signet_target_id or 0)
        if signet_target_id <= 0:
            return []
        try:
            from Py4GWCoreLib import AgentArray
            from Py4GWCoreLib.Py4GWcorelib import Utils

            target_xy = Agent.GetXY(signet_target_id)
            covered: list[tuple[int, int]] = []
            for enemy_id in AgentArray.GetEnemyArray() or []:
                enemy_id = int(enemy_id or 0)
                if enemy_id <= 0 or enemy_id == signet_target_id:
                    continue
                if not Agent.IsValid(enemy_id) or not Agent.IsAlive(enemy_id):
                    continue
                if Utils.Distance(target_xy, Agent.GetXY(enemy_id)) > float(Range.Adjacent.value):
                    continue
                casting_skill_id = int(get_danger_casting_skill_id(enemy_id) or 0)
                if casting_skill_id <= 0 or not is_dangerous_cast(enemy_id):
                    continue
                covered.append((enemy_id, casting_skill_id))
            covered.sort(key=lambda item: danger_sort_key(int(item[0]), Player.GetXY()))
            return covered
        except Exception:
            return []

    @staticmethod
    def _register_keystone_coverage(
        signet_target_id: int,
        our_skill_id: int,
        covered_casts: list[tuple[int, int]],
    ) -> None:
        """Track every dangerous cast covered by one Keystone signet proc."""
        unique: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for caster_id, enemy_skill_id in covered_casts or []:
            key = (int(caster_id or 0), int(enemy_skill_id or 0))
            if key[0] <= 0 or key[1] <= 0 or key in seen:
                continue
            seen.add(key)
            unique.append(key)
        if not unique:
            return
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "KEYSTONE_AOE_INTERRUPT_COVERAGE",
                signet_target_id=int(signet_target_id),
                our_skill_id=int(our_skill_id),
                covered_count=len(unique),
                covered=";".join(f"{caster_id}:{skill_id}" for caster_id, skill_id in unique),
            )
            for caster_id, enemy_skill_id in unique:
                CombatDebug.register_interrupt_fired(
                    int(caster_id), int(enemy_skill_id), int(our_skill_id)
                )
        except Exception:
            pass

    def _pick_keystone_proxy_target(self, dangerous_caster_id: int, signet_skill_id: int) -> int:
        """Pick the best signet target adjacent to, but different from, caster."""
        try:
            from Py4GWCoreLib import AgentArray
            enemies = AgentArray.GetEnemyArray()
            enemies = AgentArray.Filter.ByDistance(
                enemies,
                Player.GetXY(),
                float(Range.Spellcast.value),
            )
            candidates = [
                int(agent_id)
                for agent_id in enemies or []
                if self._is_keystone_proxy_target_usable(
                    int(agent_id), int(dangerous_caster_id), int(signet_skill_id)
                )
            ]
        except Exception:
            candidates = []
        if not candidates:
            return 0
        def proxy_sort_key(agent_id: int):
            covered = self._keystone_adjacent_danger_casts(int(agent_id))
            best_priority = min(
                (danger_sort_key(int(caster_id), Player.GetXY())[0] for caster_id, _ in covered),
                default=9999,
            )
            return (
                -len(covered),
                int(best_priority),
                -self._count_signet_of_judgment_adjacent_enemies(int(agent_id)),
                self._distance_to_player(int(agent_id)),
                int(agent_id),
            )

        candidates.sort(key=proxy_sort_key)
        return int(candidates[0])

    def _cast_keystone_proxy_interrupt(self, snapshot: _KeystoneBarSnapshot):
        """Spend a ready foe-targeted signet to trigger Keystone AoE interrupt.

        The global claim is made against the real dangerous caster, while the
        actual signet is cast on an adjacent proxy. Outcome logging also tracks
        the real caster, so native `interrupted/stopped/finished` results remain
        meaningful.
        """
        if not snapshot.has_keystone_signet or not snapshot.enemy_casting:
            return False

        for signet_skill_id in KEYSTONE_PROXY_INTERRUPT_SIGNET_ORDER:
            signet_skill_id = int(signet_skill_id or 0)
            if signet_skill_id <= 0 or not self.IsSkillEquipped(signet_skill_id):
                continue
            if not self.CanCastSkillID(signet_skill_id):
                continue

            proxy_cache: dict[int, int] = {}

            def has_proxy(enemy_id: int, cast_id: int) -> bool:
                proxy_id = self._pick_keystone_proxy_target(int(enemy_id), signet_skill_id)
                if proxy_id > 0:
                    proxy_cache[int(enemy_id)] = int(proxy_id)
                    return True
                return False

            dangerous_caster_id, casting_skill_id = self._pick_safe_dangerous_interrupt_target(
                interrupter_skill_id=signet_skill_id,
                validator=has_proxy,
            )
            if dangerous_caster_id <= 0 or casting_skill_id <= 0:
                continue

            proxy_agent_id = int(proxy_cache.get(int(dangerous_caster_id), 0) or 0)
            if proxy_agent_id <= 0:
                proxy_agent_id = self._pick_keystone_proxy_target(
                    int(dangerous_caster_id), signet_skill_id
                )
            if proxy_agent_id <= 0:
                release_interrupt_claim(
                    dangerous_caster_id,
                    casting_skill_id,
                    reason="keystone_proxy_missing",
                )
                continue

            keystone_covered_casts = self._keystone_adjacent_danger_casts(proxy_agent_id)
            did_cast = yield from self.CastSkillIDAndRestoreTarget(
                skill_id=signet_skill_id,
                target_agent_id=proxy_agent_id,
                extra_condition=lambda: (
                    self._target_still_casting_safe_skill(
                        dangerous_caster_id, casting_skill_id
                    )
                    and self._is_keystone_proxy_target_usable(
                        proxy_agent_id, dangerous_caster_id, signet_skill_id
                    )
                    and Routines.Checks.Effects.HasBuff(
                        Player.GetAgentID(), Keystone_Signet_ID
                    )
                ),
                log=False,
                aftercast_delay=250,
            )
            if did_cast:
                self._note_non_keystone_signet_cast()
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "KEYSTONE_PROXY_INTERRUPT_FIRED",
                        caster_id=int(dangerous_caster_id),
                        enemy_skill_id=int(casting_skill_id),
                        proxy_id=int(proxy_agent_id),
                        our_skill_id=int(signet_skill_id),
                    )
                except Exception:
                    pass
                # The proc can stop several dangerous casts at once. Register
                # every caster that was adjacent to the proxy when the command
                # was sent, not only the primary claimed caster.
                self._register_keystone_coverage(
                    proxy_agent_id, signet_skill_id, keystone_covered_casts
                )
                return True

            release_interrupt_claim(
                dangerous_caster_id,
                casting_skill_id,
                reason="keystone_proxy_not_fired",
            )

        return False

    @staticmethod
    def _approach_direct_interrupt_ids() -> tuple[int, ...]:
        return tuple(
            int(skill_id)
            for skill_id in (Power_Drain_ID, Cry_of_Frustration_ID, Signet_of_Disruption_ID)
            if int(skill_id or 0) > 0
        )

    def _ready_direct_approach_interrupt_skill(self) -> int:
        for skill_id in self._approach_direct_interrupt_ids():
            try:
                if self.IsSkillEquipped(int(skill_id)) and self.CanCastSkillID(int(skill_id)):
                    return int(skill_id)
            except Exception:
                continue
        return 0

    @staticmethod
    def _shared_skillbar_has_ready_skill(account, skill_ids: tuple[int, ...]) -> bool:
        try:
            agent_data = getattr(account, "AgentData", None)
            skillbar = getattr(agent_data, "Skillbar", None)
            if skillbar is None or int(getattr(skillbar, "CastingSkillID", 0) or 0) > 0:
                return False
            wanted = set(int(x) for x in skill_ids if int(x or 0) > 0)
            for skill in getattr(skillbar, "Skills", ()) or ():
                if int(getattr(skill, "Id", 0) or 0) not in wanted:
                    continue
                if float(getattr(skill, "Recharge", 0.0) or 0.0) <= 0.0:
                    return True
            return False
        except Exception:
            return False

    @staticmethod
    def _shared_skillbar_contains(account, skill_id: int) -> bool:
        try:
            skillbar = getattr(getattr(account, "AgentData", None), "Skillbar", None)
            return any(
                int(getattr(skill, "Id", 0) or 0) == int(skill_id)
                for skill in (getattr(skillbar, "Skills", ()) or ())
            )
        except Exception:
            return False

    def _is_selected_approach_mesmer(
        self,
        target_agent_id: int,
        cast_target_id: int,
        our_skill_id: int,
        *,
        require_keystone: bool,
    ) -> bool:
        """Elect the closest approach-capable account deterministically.

        Any account with a ready direct interrupt already inside normal range
        gets first refusal.  Otherwise only accounts that can execute this exact
        approach plan (direct skill or Keystone proxy signet) are ranked.
        """
        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            from Py4GWCoreLib.Py4GWcorelib import Utils

            own_email = str(Player.GetAccountEmail() or "").strip()
            own_party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
            caster_xy = Agent.GetXY(int(target_agent_id))
            cast_target_xy = Agent.GetXY(int(cast_target_id))
            direct_ids = self._approach_direct_interrupt_ids()
            approach_candidates: list[tuple[float, str]] = []

            for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
                if not bool(getattr(account, "IsSlotActive", False)):
                    continue
                if bool(getattr(account, "IsIsolated", False)):
                    continue
                party_id = int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)
                if own_party_id > 0 and party_id > 0 and party_id != own_party_id:
                    continue
                agent_data = getattr(account, "AgentData", None)
                agent_id = int(getattr(agent_data, "AgentID", 0) or 0)
                if agent_id <= 0 or not Agent.IsValid(agent_id) or not Agent.IsAlive(agent_id):
                    continue

                # A ready direct interrupt in normal caster range always wins.
                if self._shared_skillbar_has_ready_skill(account, direct_ids):
                    if float(Utils.Distance(Agent.GetXY(agent_id), caster_xy)) <= float(Range.Spellcast.value):
                        return False

                if not self._shared_skillbar_has_ready_skill(account, (int(our_skill_id),)):
                    continue
                if require_keystone:
                    if not self._shared_skillbar_contains(account, Keystone_Signet_ID):
                        continue
                    try:
                        if not Routines.Checks.Effects.HasBuff(agent_id, Keystone_Signet_ID):
                            continue
                    except Exception:
                        continue
                distance = float(Utils.Distance(Agent.GetXY(agent_id), cast_target_xy))
                if distance <= float(Range.Spellcast.value):
                    return False
                if distance > float(INTERRUPT_APPROACH_SCAN_RANGE):
                    continue
                email = str(getattr(account, "AccountEmail", "") or "").strip()
                if email:
                    approach_candidates.append((distance, email))

            if not approach_candidates or not own_email:
                return False
            approach_candidates.sort(key=lambda item: (float(item[0]), str(item[1])))
            return str(approach_candidates[0][1]) == own_email
        except Exception:
            return False

    def _pick_keystone_proxy_target_for_approach(
        self,
        dangerous_caster_id: int,
        signet_skill_id: int,
    ) -> int:
        """Find an adjacent proxy even while it is just outside our cast range."""
        try:
            from Py4GWCoreLib import AgentArray
            from Py4GWCoreLib.Py4GWcorelib import Utils
            caster_xy = Agent.GetXY(int(dangerous_caster_id))
            candidates = []
            for enemy_id in AgentArray.GetEnemyArray() or []:
                enemy_id = int(enemy_id or 0)
                if enemy_id <= 0 or enemy_id == int(dangerous_caster_id):
                    continue
                if not Agent.IsValid(enemy_id) or not Agent.IsAlive(enemy_id):
                    continue
                enemy_xy = Agent.GetXY(enemy_id)
                if Utils.Distance(enemy_xy, caster_xy) > float(Range.Adjacent.value):
                    continue
                player_distance = float(Utils.Distance(Player.GetXY(), enemy_xy))
                if player_distance > float(INTERRUPT_APPROACH_SCAN_RANGE):
                    continue
                covered = self._keystone_adjacent_danger_casts(enemy_id)
                candidates.append((
                    -len(covered),
                    player_distance,
                    int(enemy_id),
                ))
            if not candidates:
                return 0
            candidates.sort()
            return int(candidates[0][2])
        except Exception:
            return 0

    def _ready_keystone_proxy_approach_plan(self, dangerous_caster_id: int) -> tuple[int, int]:
        try:
            if not Routines.Checks.Effects.HasBuff(Player.GetAgentID(), Keystone_Signet_ID):
                return (0, 0)
        except Exception:
            return (0, 0)
        for signet_skill_id in KEYSTONE_PROXY_INTERRUPT_SIGNET_ORDER:
            signet_skill_id = int(signet_skill_id or 0)
            if signet_skill_id <= 0:
                continue
            try:
                if not self.IsSkillEquipped(signet_skill_id) or not self.CanCastSkillID(signet_skill_id):
                    continue
            except Exception:
                continue
            proxy_id = self._pick_keystone_proxy_target_for_approach(
                int(dangerous_caster_id), signet_skill_id
            )
            if proxy_id > 0:
                return (signet_skill_id, int(proxy_id))
        return (0, 0)

    @staticmethod
    def _approach_settings() -> tuple[float, float, int]:
        max_extra = float(INTERRUPT_APPROACH_DEFAULT_MAX_EXTRA)
        leader_tether = float(INTERRUPT_APPROACH_DEFAULT_LEADER_TETHER)
        move_cooldown = int(INTERRUPT_APPROACH_MOVE_COOLDOWN_MS)
        try:
            from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
            max_extra = float(SimplePowerSettings.get_value(
                "interrupt_approach_max_extra_distance", max_extra
            ))
            leader_tether = float(SimplePowerSettings.get_value(
                "interrupt_approach_leader_tether", leader_tether
            ))
            move_cooldown = int(SimplePowerSettings.get_value(
                "interrupt_approach_move_cooldown_ms", move_cooldown
            ))
        except Exception:
            pass
        return (
            max(120.0, min(650.0, max_extra)),
            max(700.0, min(1800.0, leader_tether)),
            max(80, min(350, move_cooldown)),
        )

    @staticmethod
    def _approach_destination(target_agent_id: int) -> tuple[tuple[float, float], float, float] | None:
        try:
            from Py4GWCoreLib.Py4GWcorelib import Utils
            player_xy = Player.GetXY()
            target_xy = Agent.GetXY(int(target_agent_id))
            distance = float(Utils.Distance(player_xy, target_xy))
            if distance <= 0.001:
                return None
            advance = max(0.0, distance - float(INTERRUPT_APPROACH_CAST_STANDOFF))
            ux = (float(target_xy[0]) - float(player_xy[0])) / distance
            uy = (float(target_xy[1]) - float(player_xy[1])) / distance
            destination = (
                float(player_xy[0]) + ux * (advance + float(INTERRUPT_APPROACH_ARRIVAL_PADDING)),
                float(player_xy[1]) + uy * (advance + float(INTERRUPT_APPROACH_ARRIVAL_PADDING)),
            )
            return destination, distance, advance
        except Exception:
            return None

    @staticmethod
    def _approach_within_leader_tether(destination: tuple[float, float], leader_tether: float) -> bool:
        try:
            from Py4GWCoreLib.Party import Party
            from Py4GWCoreLib.Py4GWcorelib import Utils
            leader_id = int(Party.GetPartyLeaderID() or 0)
            if leader_id <= 0 or not Agent.IsValid(leader_id):
                return True
            leader_xy = Agent.GetXY(leader_id)
            # Do not let an already separated account chase farther away.
            if Utils.Distance(Player.GetXY(), leader_xy) > float(leader_tether) + 180.0:
                return False
            return Utils.Distance(destination, leader_xy) <= float(leader_tether)
        except Exception:
            return False

    @staticmethod
    def _approach_interrupt_budget_ms(our_skill_id: int) -> int:
        activation_ms = 750
        ping_ms = 100
        try:
            from Py4GWCoreLib.HeroAI import interrupt as reforged_interrupt
            fast_casting_level = int(reforged_interrupt._get_player_fast_casting_level() or 0)
            try:
                activation_s, _ = Routines.Checks.Skills.apply_fast_casting(
                    int(our_skill_id), int(fast_casting_level)
                )
                activation_ms = max(0, int(float(activation_s) * 1000.0))
            except Exception:
                activation_ms = max(0, int(float(Skill.Data.GetActivation(int(our_skill_id)) or 0.0) * 1000.0))
            try:
                ping_ms = int(reforged_interrupt._PING_HANDLER.GetCurrentPing() or 100)
            except Exception:
                ping_ms = 100
        except Exception:
            try:
                activation_ms = max(0, int(float(Skill.Data.GetActivation(int(our_skill_id)) or 0.0) * 1000.0))
            except Exception:
                pass
        if ping_ms <= 0:
            ping_ms = 100
        return int(activation_ms) + int(float(ping_ms) * 1.2) + int(INTERRUPT_APPROACH_FINAL_MARGIN_MS)

    def _find_lethal_aoe_approach_candidate(self):
        try:
            from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
            if not SimplePowerSettings.is_feature_enabled("lethal_aoe_interrupt_approach", True):
                return None
        except Exception:
            pass

        direct_skill_id = self._ready_direct_approach_interrupt_skill()
        max_extra, leader_tether, _ = self._approach_settings()
        candidates = []
        for target_agent_id, enemy_skill_id in get_dangerous_casts_in_range(
            int(INTERRUPT_APPROACH_SCAN_RANGE)
        ):
            try:
                target_agent_id = int(target_agent_id)
                enemy_skill_id = int(enemy_skill_id)
                if not is_lethal_aoe_skill(enemy_skill_id):
                    continue
                if not danger_target_still_casting_skill(target_agent_id, enemy_skill_id):
                    continue

                mode = "direct"
                our_skill_id = int(direct_skill_id or 0)
                cast_target_id = int(target_agent_id)
                if our_skill_id <= 0:
                    our_skill_id, cast_target_id = self._ready_keystone_proxy_approach_plan(
                        int(target_agent_id)
                    )
                    mode = "keystone_proxy"
                if our_skill_id <= 0 or cast_target_id <= 0:
                    continue

                info = self._approach_destination(cast_target_id)
                if info is None:
                    continue
                destination, distance, advance = info
                if distance <= float(Range.Spellcast.value) - 15.0:
                    continue
                if advance > float(max_extra):
                    continue
                if not self._approach_within_leader_tether(destination, leader_tether):
                    continue
                if is_position_in_active_aoe(destination, padding=45.0, critical_only=False):
                    continue
                remaining_ms = get_enemy_cast_remaining_ms(target_agent_id, enemy_skill_id)
                if remaining_ms is None:
                    continue
                run_ms = int(
                    (float(advance) / float(INTERRUPT_APPROACH_MOVEMENT_SPEED_GW_S))
                    * 1000.0
                    * float(INTERRUPT_APPROACH_PATH_FACTOR)
                )
                total_budget = run_ms + self._approach_interrupt_budget_ms(our_skill_id)
                if int(remaining_ms) < int(total_budget):
                    continue
                if not self._is_selected_approach_mesmer(
                    target_agent_id,
                    cast_target_id,
                    our_skill_id,
                    require_keystone=(mode == "keystone_proxy"),
                ):
                    continue
                candidates.append((
                    int(remaining_ms),
                    float(distance),
                    int(target_agent_id),
                    int(cast_target_id),
                    int(enemy_skill_id),
                    int(our_skill_id),
                    str(mode),
                    destination,
                    int(total_budget),
                ))
            except Exception:
                continue

        if not candidates:
            return None
        # Urgent feasible AoE first; nearest caster is the stable tie-breaker.
        candidates.sort(key=lambda item: (int(item[0]), float(item[1]), int(item[2])))
        return candidates[0]

    def _clear_interrupt_approach(
        self,
        *,
        reason: str = "",
        release_claim: bool = True,
        log_abort: bool = True,
    ) -> None:
        state = self._interrupt_approach
        if state.active and release_claim:
            release_interrupt_claim(
                int(state.target_agent_id),
                int(state.enemy_skill_id),
                reason=str(reason or "approach_released"),
            )
        if state.active and reason and log_abort:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "INTERRUPT_APPROACH_ABORT",
                    caster_id=int(state.target_agent_id),
                    enemy_skill_id=int(state.enemy_skill_id),
                    our_skill_id=int(state.our_skill_id),
                    reason=str(reason),
                )
            except Exception:
                pass
        self._interrupt_approach = _InterruptApproachState()
        # Zero-idle target cache: only avoids repeating the same full enemy scan
        # several times inside the same short decision window. It never blocks a
        # cast; stale/invalid targets are revalidated before use.
        self._zero_idle_cache_tick: int = 0
        self._zero_idle_cache_targets: tuple[int, ...] = ()
        clear_interrupt_approach_movement()

    def _start_interrupt_approach(self, candidate) -> bool:
        (
            remaining_ms,
            _distance,
            target_agent_id,
            cast_target_id,
            enemy_skill_id,
            our_skill_id,
            mode,
            destination,
            total_budget,
        ) = candidate
        if not post_interrupt_claim(
            int(target_agent_id),
            int(enemy_skill_id),
            int(our_skill_id),
            claim_duration_ms=max(600, int(remaining_ms) + 320),
        ):
            return False
        now = int(get_game_tick() or 0)
        self._interrupt_approach = _InterruptApproachState(
            active=True,
            target_agent_id=int(target_agent_id),
            cast_target_id=int(cast_target_id),
            enemy_skill_id=int(enemy_skill_id),
            our_skill_id=int(our_skill_id),
            mode=str(mode),
            started_tick=now,
            last_move_tick=0,
            destination=(float(destination[0]), float(destination[1])),
        )
        mark_interrupt_approach_movement_active(target_agent_id, enemy_skill_id)
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "INTERRUPT_APPROACH_START",
                caster_id=int(target_agent_id),
                enemy_skill_id=int(enemy_skill_id),
                our_skill_id=int(our_skill_id),
                mode=str(mode),
                cast_target_id=int(cast_target_id),
                remaining_ms=int(remaining_ms),
                budget_ms=int(total_budget),
                destination=f"{float(destination[0]):.1f},{float(destination[1]):.1f}",
            )
        except Exception:
            pass
        return True

    def _process_lethal_aoe_interrupt_approach(self):
        state = self._interrupt_approach
        if not state.active:
            candidate = self._find_lethal_aoe_approach_candidate()
            if candidate is None or not self._start_interrupt_approach(candidate):
                clear_interrupt_approach_movement()
                return False
            state = self._interrupt_approach

        target_agent_id = int(state.target_agent_id)
        cast_target_id = int(state.cast_target_id or state.target_agent_id)
        enemy_skill_id = int(state.enemy_skill_id)
        our_skill_id = int(state.our_skill_id)
        mode = str(state.mode or "direct")
        if not danger_target_still_casting_skill(target_agent_id, enemy_skill_id):
            self._clear_interrupt_approach(reason="cast_ended")
            return False
        if not is_lethal_aoe_skill(enemy_skill_id):
            self._clear_interrupt_approach(reason="no_longer_lethal")
            return False
        if cast_target_id <= 0 or not Agent.IsValid(cast_target_id) or not Agent.IsAlive(cast_target_id):
            self._clear_interrupt_approach(reason="cast_target_invalid")
            return False
        if mode == "keystone_proxy":
            try:
                from Py4GWCoreLib.Py4GWcorelib import Utils
                if not Routines.Checks.Effects.HasBuff(Player.GetAgentID(), Keystone_Signet_ID):
                    self._clear_interrupt_approach(reason="keystone_expired")
                    return False
                if Utils.Distance(Agent.GetXY(cast_target_id), Agent.GetXY(target_agent_id)) > float(Range.Adjacent.value):
                    self._clear_interrupt_approach(reason="proxy_moved")
                    return False
            except Exception:
                self._clear_interrupt_approach(reason="proxy_validation_failed")
                return False
        if not self.IsSkillEquipped(our_skill_id) or not self.CanCastSkillID(our_skill_id):
            self._clear_interrupt_approach(reason="interrupt_not_ready")
            return False

        max_extra, leader_tether, move_cooldown = self._approach_settings()
        info = self._approach_destination(cast_target_id)
        if info is None:
            self._clear_interrupt_approach(reason="missing_target_position")
            return False
        destination, distance, advance = info
        state.destination = destination
        if advance > float(max_extra):
            self._clear_interrupt_approach(reason="caster_moved_too_far")
            return False
        if not self._approach_within_leader_tether(destination, leader_tether):
            self._clear_interrupt_approach(reason="leader_tether")
            return False
        if is_position_in_active_aoe(destination, padding=45.0, critical_only=False):
            self._clear_interrupt_approach(reason="approach_destination_unsafe")
            return False

        remaining_ms = get_enemy_cast_remaining_ms(target_agent_id, enemy_skill_id)
        if remaining_ms is None:
            self._clear_interrupt_approach(reason="missing_cast_timer")
            return False
        run_ms = int(
            (max(0.0, float(advance)) / float(INTERRUPT_APPROACH_MOVEMENT_SPEED_GW_S))
            * 1000.0
            * float(INTERRUPT_APPROACH_PATH_FACTOR)
        )
        if int(remaining_ms) < run_ms + self._approach_interrupt_budget_ms(our_skill_id):
            self._clear_interrupt_approach(reason="no_time_remaining")
            return False

        mark_interrupt_approach_movement_active(target_agent_id, enemy_skill_id)

        if float(distance) <= float(Range.Spellcast.value) - 10.0:
            timing_feasible = (
                int(remaining_ms) >= self._approach_interrupt_budget_ms(our_skill_id)
                if mode == "keystone_proxy"
                else interrupt_is_feasible(target_agent_id, our_skill_id)
            )
            if not Routines.Checks.Skills.CanCast() or not timing_feasible:
                # Keep the claim only while there is still a realistic window.
                if int(remaining_ms) <= self._approach_interrupt_budget_ms(our_skill_id):
                    self._clear_interrupt_approach(reason="in_range_but_too_late")
                    return False
                return True

            keystone_covered_casts = (
                self._keystone_adjacent_danger_casts(cast_target_id)
                if (
                    mode == "keystone_proxy"
                    or our_skill_id == int(Signet_of_Disruption_ID)
                )
                and Routines.Checks.Effects.HasBuff(Player.GetAgentID(), Keystone_Signet_ID)
                else []
            )
            did_cast = yield from self.CastSkillIDAndRestoreTarget(
                skill_id=our_skill_id,
                target_agent_id=cast_target_id,
                extra_condition=lambda: (
                    danger_target_still_casting_skill(target_agent_id, enemy_skill_id)
                    and self._distance_to_player(cast_target_id) <= float(Range.Spellcast.value)
                    and (
                        mode != "keystone_proxy"
                        or Routines.Checks.Effects.HasBuff(Player.GetAgentID(), Keystone_Signet_ID)
                    )
                ),
                log=False,
                aftercast_delay=250,
            )
            if did_cast:
                if mode == "keystone_proxy" or our_skill_id == int(Signet_of_Disruption_ID):
                    self._note_non_keystone_signet_cast()
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.register_interrupt_fired(
                        target_agent_id, enemy_skill_id, our_skill_id
                    )
                    CombatDebug.log_event(
                        "INTERRUPT_APPROACH_FIRED",
                        caster_id=int(target_agent_id),
                        enemy_skill_id=int(enemy_skill_id),
                        our_skill_id=int(our_skill_id),
                        mode=str(mode),
                        cast_target_id=int(cast_target_id),
                        approach_ms=max(0, int(get_game_tick()) - int(state.started_tick)),
                    )
                except Exception:
                    pass
                if mode == "keystone_proxy":
                    try:
                        from Py4GWCoreLib.Builds.Skills import CombatDebug
                        CombatDebug.log_event(
                            "KEYSTONE_PROXY_INTERRUPT_FIRED",
                            caster_id=int(target_agent_id),
                            enemy_skill_id=int(enemy_skill_id),
                            proxy_id=int(cast_target_id),
                            our_skill_id=int(our_skill_id),
                            source="interrupt_approach",
                        )
                    except Exception:
                        pass
                if keystone_covered_casts:
                    self._register_keystone_coverage(
                        cast_target_id, our_skill_id, keystone_covered_casts
                    )
                # Keep the shared claim until its normal expiry/outcome window.
                self._clear_interrupt_approach(
                    reason="",
                    release_claim=False,
                    log_abort=False,
                )
                return True

            self._clear_interrupt_approach(reason="cast_command_failed")
            return False

        try:
            if Routines.Checks.Agents.IsKnockedDown(Player.GetAgentID()):
                return True
        except Exception:
            pass
        try:
            if Agent.IsCasting(Player.GetAgentID()):
                return True
        except Exception:
            pass

        now = int(get_game_tick() or 0)
        if int(state.last_move_tick or 0) <= 0 or now - int(state.last_move_tick) >= int(move_cooldown):
            Player.Move(float(destination[0]), float(destination[1]))
            state.last_move_tick = int(now)
        return True


    @staticmethod
    def _signet_of_disruption_can_interrupt(target_agent_id: int, enemy_skill_id: int) -> bool:
        """Signet of Disruption always interrupts spells; any skill if foe is hexed."""
        target_agent_id = int(target_agent_id or 0)
        enemy_skill_id = int(enemy_skill_id or 0)
        if target_agent_id <= 0 or enemy_skill_id <= 0:
            return False
        try:
            if Skill.Flags.IsSpell(enemy_skill_id):
                return True
        except Exception:
            pass
        try:
            return bool(Agent.IsHexed(target_agent_id))
        except Exception:
            return False

    @staticmethod
    def _telemetry_signet_name(skill_id: int) -> str:
        names = {
            int(Signet_of_Judgment_ID): "copied_soj",
            int(Unnatural_Signet_ID): "unnatural",
            int(Signet_of_Sorrow_ID): "sorrow",
            int(Signet_of_Corruption_Kurzick_ID): "corruption_kurzick",
            int(Signet_of_Corruption_Luxon_ID): "corruption_luxon",
            int(Bane_Signet_ID): "bane_ruins",
            int(Signet_of_Disruption_ID): "disruption",
            int(Castigation_Signet_ID): "castigation",
        }
        return names.get(int(skill_id or 0), f"skill_{int(skill_id or 0)}")

    def _telemetry_skill_target_state(self, skill_id: int) -> tuple[int, str]:
        """Read-only best-effort explanation for a ready signet not firing yet.

        This intentionally avoids claims and never mutates combat state.
        """
        skill_id = int(skill_id or 0)
        if skill_id <= 0:
            return 0, "invalid_skill"

        try:
            if not self._sod_combat_active():
                return 0, "no_combat"
        except Exception:
            return 0, "no_combat"

        try:
            if skill_id == int(Signet_of_Judgment_ID):
                target_id = int(self._get_signet_of_judgment_target(claim_target=False) or 0)
                if target_id > 0:
                    return target_id, "target_available"
                return 0, "no_valid_soj_target"

            if skill_id == int(Unnatural_Signet_ID):
                target_id, reason = self._get_unnatural_signet_fast_target()
                target_id = int(target_id or 0)
                if target_id > 0:
                    return target_id, f"target_available:{reason}"
                return 0, f"no_valid_unnatural_target:{reason}"

            if skill_id == int(Signet_of_Sorrow_ID):
                target_id = int(self._get_sorrow_signet_target(require_corpse=True, claim_target=False) or 0)
                if target_id > 0:
                    return target_id, "target_available:corpse_turbo"
                target_id, reason = self._get_zero_idle_damage_target(skill_id)
                target_id = int(target_id or 0)
                if target_id > 0:
                    return target_id, f"target_available:normal:{reason}"
                return 0, "no_valid_sorrow_target"

            if skill_id in (int(Signet_of_Corruption_Kurzick_ID), int(Signet_of_Corruption_Luxon_ID)):
                target_id, reason = self._get_zero_idle_damage_target(skill_id)
                target_id = int(target_id or 0)
                if target_id > 0:
                    return target_id, f"target_available:{reason}"
                return 0, "no_valid_corruption_target"

            if skill_id == int(Bane_Signet_ID):
                target_id, reason = self._get_zero_idle_damage_target(skill_id)
                target_id = int(target_id or 0)
                if target_id > 0:
                    return target_id, f"target_available:{reason}"
                return 0, f"no_valid_bane_target:{reason}"

            if skill_id == int(Castigation_Signet_ID):
                target_id, reason = self._get_zero_idle_damage_target(skill_id)
                target_id = int(target_id or 0)
                if target_id > 0:
                    return target_id, f"target_available:{reason}"
                return 0, f"no_valid_castigation_target:{reason}"

            if skill_id == int(Signet_of_Disruption_ID):
                # Do not invoke the interrupt claim path from telemetry.  Only
                # record whether a normal filler/damage target exists.
                snapshot = self._get_bar_snapshot()
                target_id, reason = self._get_signet_of_disruption_filler_target(snapshot)
                target_id = int(target_id or 0)
                if target_id > 0:
                    return target_id, f"target_available:{reason}"
                if snapshot.enemy_casting:
                    return 0, "enemy_casting_but_no_legal_or_feasible_target"
                return 0, "no_interrupt_or_useful_filler_target"
        except Exception as exc:
            return 0, f"telemetry_probe_error:{type(exc).__name__}"

        return 0, "unsupported"

    def _track_primary_signet_idle(self) -> None:
        """Low-overhead ready/idle telemetry for all Keystone offensive signets.

        One sample per ready skill per second.  The function is deliberately
        read-only and may be removed without changing combat behavior.
        """
        now = int(get_game_tick() or 0)
        if now <= 0:
            return

        combat_active = bool(self._sod_combat_active())
        tracked = (
            int(Signet_of_Judgment_ID),
            int(Unnatural_Signet_ID),
            int(Bane_Signet_ID),
            int(Signet_of_Disruption_ID),
                Signet_of_Sorrow_ID,
                Signet_of_Corruption_Kurzick_ID,
            Signet_of_Corruption_Luxon_ID,
            int(Castigation_Signet_ID),
        )

        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
        except Exception:
            return

        for skill_id in tracked:
            if skill_id <= 0:
                continue

            equipped = bool(self.IsSkillEquipped(skill_id))
            ready_now = bool(equipped and self._is_skill_strictly_ready(skill_id))
            was_ready = bool(self._signet_was_ready.get(skill_id, False))

            if not combat_active or not equipped:
                self._signet_ready_since.pop(skill_id, None)
                self._signet_last_sample.pop(skill_id, None)
                self._signet_was_ready[skill_id] = ready_now
                continue

            skill_name = self._telemetry_signet_name(skill_id)

            if ready_now and not was_ready:
                self._signet_ready_since[skill_id] = now
                self._signet_last_sample[skill_id] = now
                target_id, block_reason = self._telemetry_skill_target_state(skill_id)
                CombatDebug.log_event(
                    "SIGNET_READY_ENTER",
                    skill_id=int(skill_id),
                    skill_name=str(skill_name),
                    target_id=int(target_id),
                    state=str(block_reason),
                )

            elif ready_now:
                ready_since = int(self._signet_ready_since.get(skill_id, now) or now)
                last_sample = int(self._signet_last_sample.get(skill_id, 0) or 0)
                if now - last_sample >= 1000:
                    self._signet_last_sample[skill_id] = now
                    target_id, block_reason = self._telemetry_skill_target_state(skill_id)
                    CombatDebug.log_event(
                        "SIGNET_READY_SAMPLE",
                        skill_id=int(skill_id),
                        skill_name=str(skill_name),
                        idle_ms=max(0, now - ready_since),
                        target_id=int(target_id),
                        state=str(block_reason),
                    )

            elif was_ready:
                ready_since = int(self._signet_ready_since.get(skill_id, now) or now)
                CombatDebug.log_event(
                    "SIGNET_READY_EXIT",
                    skill_id=int(skill_id),
                    skill_name=str(skill_name),
                    idle_ms=max(0, now - ready_since),
                )
                self._signet_ready_since.pop(skill_id, None)
                self._signet_last_sample.pop(skill_id, None)

            self._signet_was_ready[skill_id] = ready_now

    def _log_primary_signet_cast(
        self,
        skill_id: int,
        target_id: int,
        reason: str,
        path: str,
    ) -> None:
        """Uniform cast event for post-run DPS/idle analysis."""
        skill_id = int(skill_id or 0)
        target_id = int(target_id or 0)
        if skill_id <= 0:
            return
        if skill_id != int(Signet_of_Sorrow_ID):
            self._sorrow_turbo_streak = 0
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            now = int(get_game_tick() or 0)
            ready_since = int(self._signet_ready_since.get(skill_id, 0) or 0)
            idle_ms = max(0, now - ready_since) if now > 0 and ready_since > 0 else 0
            active_mantra_id = int(self._active_keystone_mantra_id() or 0)
            previous_signet_tick = int(self._mantra_last_profile_signet_tick or 0)
            signet_gap_ms = (
                max(0, now - previous_signet_tick)
                if now > 0 and previous_signet_tick > 0
                else 0
            )
            self._mantra_last_profile_signet_tick = now
            self._mantra_profile_signet_count += 1
            health_fraction_before, max_hp_before, hp_before = self._player_health_snapshot()
            missing_hp_before = max(0, int(max_hp_before - hp_before))
            mantra_signets_active = bool(active_mantra_id == int(Mantra_of_Signets_ID))
            CombatDebug.log_event(
                "SIGNET_CAST_PROFILE",
                skill_id=int(skill_id),
                skill_name=str(self._telemetry_signet_name(skill_id)),
                target_id=int(target_id),
                ready_idle_ms=int(idle_ms),
                reason=str(reason),
                path=str(path),
                mantra_id=int(active_mantra_id),
                mantra_name=self._keystone_mantra_name(active_mantra_id),
                mantra_active=bool(active_mantra_id > 0),
                signet_gap_ms=int(signet_gap_ms),
                signet_cast_index=int(self._mantra_profile_signet_count),
                health_probe_id=0,
                telemetry_mode="passive_precast_only",
                mantra_signets_heal_opportunity=bool(mantra_signets_active and missing_hp_before > 0),
                mantra_signets_missing_hp_before=int(missing_hp_before) if mantra_signets_active else 0,
                player_health_fraction_at_cast_request=float(health_fraction_before),
                player_hp_at_cast_request=int(hp_before),
                player_max_hp_at_cast_request=int(max_hp_before),
                missing_hp_at_cast_request=int(missing_hp_before),
                # Backward-compatible legacy field. It was historically named
                # "after" even though the sample is taken at cast request.
                player_health_pct_after=float(health_fraction_before),
            )
        except Exception:
            pass

    def _track_mimicry_soj_window(self) -> None:
        """Track the copied SoJ lifetime separately from ordinary signet timing."""
        now = int(get_game_tick() or 0)
        if now <= 0:
            return
        equipped_now = bool(self.IsSkillEquipped(Signet_of_Judgment_ID))
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
        except Exception:
            return

        if equipped_now and not self._mimicry_soj_was_equipped:
            self._mimicry_soj_equipped_since = now
            current_target = int(Player.GetTargetID() or 0)
            CombatDebug.log_event(
                "MIMICRY_SOJ_WINDOW_START",
                current_target_id=int(current_target),
                target_is_valid_enemy=bool(current_target > 0 and Routines.Checks.Agents.IsAlive(current_target)),
            )

        elif not equipped_now and self._mimicry_soj_was_equipped:
            lived_ms = (
                max(0, now - int(self._mimicry_soj_equipped_since))
                if self._mimicry_soj_equipped_since > 0
                else 0
            )
            CombatDebug.log_event(
                "MIMICRY_SOJ_WINDOW_END",
                window_ms=int(lived_ms),
            )
            self._mimicry_soj_equipped_since = 0

        self._mimicry_soj_was_equipped = equipped_now

    def _log_rotation_stall(self, gate: str, snapshot=None) -> None:
        """Read-only diagnostic for visible Mesmer idle windows."""
        try:
            if not self._sod_combat_active():
                return
            now = int(get_game_tick() or 0)
            if now <= 0:
                return
            if self._stall_last_log_tick > 0 and now - int(self._stall_last_log_tick) < 750:
                return
            tracked = (
                int(Signet_of_Judgment_ID),
                int(Unnatural_Signet_ID),
                int(Bane_Signet_ID),
                int(Signet_of_Disruption_ID),
                int(Castigation_Signet_ID),
            )
            ready, usable, states = [], [], []
            for skill_id in tracked:
                if skill_id <= 0 or not self.IsSkillEquipped(skill_id):
                    continue
                if not self._is_skill_strictly_ready(skill_id):
                    continue
                ready.append(int(skill_id))
                target_id, state = self._telemetry_skill_target_state(skill_id)
                states.append(f"{self._telemetry_signet_name(skill_id)}:{state}:{int(target_id or 0)}")
                if int(target_id or 0) > 0 and str(state).startswith("target_available"):
                    usable.append(int(skill_id))
            if not usable:
                return
            self._stall_last_log_tick = now
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "MESMER_ROTATION_STALL",
                gate=str(gate),
                ready_skills=",".join(str(x) for x in ready),
                usable_skills=",".join(str(x) for x in usable),
                states="|".join(states),
                current_target_id=int(Player.GetTargetID() or 0),
                global_can_cast=bool(Routines.Checks.Skills.CanCast()),
                enemy_casting=bool(getattr(snapshot, "enemy_casting", False)) if snapshot is not None else False,
                enemy_in_spellcast=bool(getattr(snapshot, "enemy_in_spellcast", False)) if snapshot is not None else False,
                precombat_setup=bool(getattr(snapshot, "precombat_setup", False)) if snapshot is not None else False,
            )
        except Exception:
            pass

    def _sod_combat_active(self) -> bool:
        try:
            if self.IsInAggro() or self.IsCloseToAggro():
                return True
        except Exception:
            pass
        try:
            from Py4GWCoreLib import AgentArray
            for enemy_id in AgentArray.GetEnemyArray() or []:
                enemy_id = int(enemy_id or 0)
                if enemy_id <= 0:
                    continue
                if not Agent.IsValid(enemy_id) or not Agent.IsAlive(enemy_id):
                    continue
                if self._distance_to_player(enemy_id) <= float(Range.Spellcast.value):
                    return True
        except Exception:
            pass
        return False

    def _track_sod_ready_idle(self) -> None:
        """Telemetry only: measure ready-but-unused Signet of Disruption time."""
        if not self.IsSkillEquipped(Signet_of_Disruption_ID):
            self._sod_ready_since_tick = 0
            self._sod_was_ready = False
            return

        now = int(get_game_tick() or 0)
        if now <= 0:
            return

        ready_now = bool(self._is_skill_strictly_ready(Signet_of_Disruption_ID))
        if not self._sod_combat_active():
            self._sod_ready_since_tick = 0
            self._sod_was_ready = ready_now
            self._sod_last_sample_tick = 0
            self._sod_last_team_ready_count = -1
            return

        team_ready_count = len(self._disruption_ready_accounts())
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
        except Exception:
            return

        if ready_now and not self._sod_was_ready:
            self._sod_ready_since_tick = now
            self._sod_last_sample_tick = now
            self._sod_last_team_ready_count = int(team_ready_count)
            CombatDebug.log_event(
                "SOD_READY_ENTER",
                ready_count=int(team_ready_count),
                combat_active=True,
            )

        elif ready_now:
            if self._sod_ready_since_tick <= 0:
                self._sod_ready_since_tick = now
            idle_ms = max(0, now - int(self._sod_ready_since_tick))
            if (
                self._sod_last_sample_tick <= 0
                or now - int(self._sod_last_sample_tick) >= 1000
                or int(team_ready_count) != int(self._sod_last_team_ready_count)
            ):
                self._sod_last_sample_tick = now
                self._sod_last_team_ready_count = int(team_ready_count)
                CombatDebug.log_event(
                    "SOD_READY_SAMPLE",
                    idle_ms=int(idle_ms),
                    ready_count=int(team_ready_count),
                    combat_active=True,
                )

        elif self._sod_was_ready:
            idle_ms = max(0, now - int(self._sod_ready_since_tick)) if self._sod_ready_since_tick > 0 else 0
            CombatDebug.log_event(
                "SOD_READY_EXIT",
                idle_ms=int(idle_ms),
                ready_count=int(team_ready_count),
                combat_active=True,
            )
            self._sod_ready_since_tick = 0
            self._sod_last_sample_tick = 0
            self._sod_last_team_ready_count = int(team_ready_count)

        self._sod_was_ready = ready_now

    def _log_sod_cast_consumed(self, reason: str, target_id: int = 0, enemy_skill_id: int = 0) -> None:
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            now = int(get_game_tick() or 0)
            idle_ms = max(0, now - int(self._sod_ready_since_tick)) if now > 0 and self._sod_ready_since_tick > 0 else 0
            CombatDebug.log_event(
                "SOD_CAST_CONSUMED",
                reason=str(reason),
                target_id=int(target_id or 0),
                enemy_skill_id=int(enemy_skill_id or 0),
                ready_idle_ms=int(idle_ms),
                ready_count_before=int(len(self._disruption_ready_accounts())),
            )
        except Exception:
            pass

    def _disruption_ready_accounts(self):
        """Return active party accounts with a ready Signet of Disruption."""
        ready = []
        try:
            from Py4GWCoreLib import GLOBAL_CACHE
            own_party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
            for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
                if not bool(getattr(account, "IsSlotActive", False)):
                    continue
                if bool(getattr(account, "IsIsolated", False)):
                    continue
                party_id = int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)
                if own_party_id > 0 and party_id > 0 and party_id != own_party_id:
                    continue
                email = str(getattr(account, "AccountEmail", "") or "").strip()
                if not email:
                    continue
                if self._shared_skillbar_has_ready_skill(account, (int(Signet_of_Disruption_ID),)):
                    ready.append((email, account))
        except Exception:
            return []
        ready.sort(key=lambda item: str(item[0]))
        return ready

    def _disruption_filler_turn_ready(self) -> tuple[bool, int, int]:
        """No-reserve coordination.

        Ready Signets of Disruption are never held back for round-robin timing.
        Shared readiness is still reported for logs, but every ready Mesmer may
        act immediately. Cross-account interrupt claims prevent duplicate
        interrupts on the same activation.
        """
        own_email = str(Player.GetAccountEmail() or "").strip()
        ready = self._disruption_ready_accounts()
        emails = [str(item[0]) for item in ready]
        try:
            rank = emails.index(own_email)
        except ValueError:
            rank = 0
        self._disruption_filler_wait_since = 0
        return True, max(0, rank), len(emails)

    def _cast_signet_of_disruption_interrupt_first(self, snapshot: _KeystoneBarSnapshot):
        """Interrupt any feasible legal activation before all offensive rotation.

        Dangerous casts are ranked first, but an otherwise ordinary spell is
        still interrupted if the signet is ready and the timing is feasible.
        Non-spell skills are eligible only while the foe is hexed.
        """
        if not self.IsSkillEquipped(Signet_of_Disruption_ID):
            return False
        if not self._is_skill_strictly_ready(Signet_of_Disruption_ID):
            return False

        try:
            from Py4GWCoreLib import AgentArray
            candidates = []
            player_xy = Player.GetXY()
            for enemy_id in AgentArray.GetEnemyArray() or []:
                enemy_id = int(enemy_id or 0)
                if enemy_id <= 0:
                    continue
                try:
                    if not Agent.IsValid(enemy_id) or not Agent.IsAlive(enemy_id):
                        continue
                except Exception:
                    continue
                if self._distance_to_player(enemy_id) > float(Range.Spellcast.value):
                    continue

                enemy_skill_id = int(get_danger_casting_skill_id(enemy_id) or 0)
                if enemy_skill_id <= 0:
                    continue
                if not self._signet_of_disruption_can_interrupt(enemy_id, enemy_skill_id):
                    continue
                if not interrupt_is_feasible(enemy_id, Signet_of_Disruption_ID):
                    continue

                dangerous = bool(is_dangerous_cast(enemy_id))
                remaining = get_enemy_cast_remaining_ms(enemy_id, enemy_skill_id)
                remaining_sort = int(remaining) if remaining is not None else 999999
                candidates.append((
                    0 if dangerous else 1,
                    remaining_sort,
                    danger_sort_key(enemy_id, player_xy),
                    enemy_id,
                    enemy_skill_id,
                ))
        except Exception:
            return False

        if not candidates:
            return False

        candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        for _danger_rank, _remaining, _sort_key, target_id, enemy_skill_id in candidates:
            target_id = int(target_id)
            enemy_skill_id = int(enemy_skill_id)

            # Shared claim is the only coordination gate. There is no timer,
            # reservation or round-robin wait.
            try:
                if not post_interrupt_claim(
                    target_id, enemy_skill_id, Signet_of_Disruption_ID
                ):
                    continue
            except Exception:
                # Claim system is fail-open only when unavailable; the local
                # cast condition below still protects against stale activations.
                pass

            did_cast = yield from self.CastSkillIDAndRestoreTarget(
                skill_id=Signet_of_Disruption_ID,
                target_agent_id=target_id,
                extra_condition=lambda tid=target_id, sid=enemy_skill_id: (
                    self._target_still_casting_safe_skill(tid, sid)
                    and self._signet_of_disruption_can_interrupt(tid, sid)
                    and interrupt_is_feasible(tid, Signet_of_Disruption_ID)
                ),
                log=False,
                aftercast_delay=40,
            )
            if not did_cast:
                try:
                    release_interrupt_claim(target_id, enemy_skill_id)
                except Exception:
                    pass
                continue

            self._note_non_keystone_signet_cast()
            self._log_sod_cast_consumed("interrupt_first", target_id, enemy_skill_id)
            self._log_primary_signet_cast(
                Signet_of_Disruption_ID,
                target_id,
                reason=f"interrupt_skill_{int(enemy_skill_id)}",
                path="disruption_interrupt_first",
            )
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "KEYSTONE_DISRUPTION_INTERRUPT_FIRST",
                    target_id=int(target_id),
                    enemy_skill_id=int(enemy_skill_id),
                    dangerous=bool(_danger_rank == 0),
                    remaining_ms=int(_remaining),
                    policy="any_feasible_interrupt_before_all_no_reserve",
                )
                CombatDebug.register_interrupt_fired(
                    int(target_id),
                    int(enemy_skill_id),
                    int(Signet_of_Disruption_ID),
                )
            except Exception:
                pass
            return True

        return False

    def _cast_signet_of_disruption_opening(self, snapshot: _KeystoneBarSnapshot):
        """Open a fresh enemy packet with Signet of Disruption."""
        if self._disruption_opening_spent:
            return False
        if not self.IsSkillEquipped(Signet_of_Disruption_ID):
            return False
        if not self._is_skill_strictly_ready(Signet_of_Disruption_ID):
            return False

        target_id, reason = self._get_zero_idle_damage_target(int(Signet_of_Disruption_ID))
        target_id = int(target_id or 0)
        if target_id <= 0:
            return False

        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Signet_of_Disruption_ID,
            target_agent_id=target_id,
            log=False,
            aftercast_delay=40,
        )
        if not did_cast:
            return False

        self._disruption_opening_spent = True
        self._note_non_keystone_signet_cast()
        self._log_sod_cast_consumed("opening", target_id, 0)
        self._log_primary_signet_cast(
            Signet_of_Disruption_ID,
            target_id,
            reason="opening",
            path="disruption_opening",
        )
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "KEYSTONE_DISRUPTION_OPENING_CAST",
                target_id=int(target_id),
                reason=str(reason),
                policy="open_each_packet_distributed_no_reserve",
            )
        except Exception:
            pass
        return True

    def _get_signet_of_disruption_filler_target(self, snapshot: _KeystoneBarSnapshot) -> tuple[int, str]:
        """Useful non-emergency use: interrupt any legal activation, else Keystone AoE."""
        # First use it on any current legal activation, even if it is below the
        # reserved-danger threshold. This converts filler casts into real control.
        try:
            from Py4GWCoreLib import AgentArray
            candidates = []
            for enemy_id in AgentArray.GetEnemyArray() or []:
                enemy_id = int(enemy_id or 0)
                if enemy_id <= 0 or not Agent.IsValid(enemy_id) or not Agent.IsAlive(enemy_id):
                    continue
                if self._distance_to_player(enemy_id) > float(Range.Spellcast.value):
                    continue
                enemy_skill_id = int(get_danger_casting_skill_id(enemy_id) or 0)
                if enemy_skill_id <= 0:
                    continue
                if not self._signet_of_disruption_can_interrupt(enemy_id, enemy_skill_id):
                    continue
                candidates.append((
                    0 if is_dangerous_cast(enemy_id) else 1,
                    danger_sort_key(enemy_id, Player.GetXY()),
                    enemy_id,
                ))
            if candidates:
                candidates.sort(key=lambda item: (item[0], item[1], item[2]))
                return int(candidates[0][2]), "active_interruptable_skill"
        except Exception:
            pass

        # FULL-SPAM policy: once no legal interrupt exists, Signet of Disruption
        # is pure pressure. Spend it on any valid zero-idle damage target.
        # Interrupt-first remains absolute above this branch.
        target_id, reason = self._get_zero_idle_damage_target(int(Signet_of_Disruption_ID))
        target_id = int(target_id or 0)
        if target_id > 0:
            return target_id, f"full_spam_{reason}"
        return 0, ""

    def _cast_signet_of_disruption_filler(self, snapshot: _KeystoneBarSnapshot):
        """Spend Signet of Disruption immediately when no interruptable activation exists."""
        if not self._is_skill_strictly_ready(Signet_of_Disruption_ID):
            self._disruption_filler_wait_since = 0
            return False

        target_id, reason = self._get_signet_of_disruption_filler_target(snapshot)
        target_id = int(target_id or 0)
        if target_id <= 0:
            self._disruption_filler_wait_since = 0
            return False

        # No round-robin hold: every Mesmer may spend a ready SoD immediately
        # when the interrupt-first scan found nothing legal.
        rank, ready_count = 0, 1

        enemy_skill_id = int(get_danger_casting_skill_id(target_id) or 0)
        direct_interrupt = bool(
            enemy_skill_id > 0
            and self._signet_of_disruption_can_interrupt(target_id, enemy_skill_id)
        )
        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Signet_of_Disruption_ID,
            target_agent_id=target_id,
            extra_condition=(
                (lambda: self._target_still_casting_safe_skill(target_id, enemy_skill_id))
                if direct_interrupt else None
            ),
            log=False,
            aftercast_delay=40,
        )
        if not did_cast and direct_interrupt:
            # The activation disappeared between target selection and the real
            # signet fire window. Do not burn a controller pass waiting for the
            # next tick: immediately fall back to a normal full-spam damage
            # target while SoD is still ready.
            fallback_target, fallback_reason = self._get_zero_idle_damage_target(
                int(Signet_of_Disruption_ID)
            )
            fallback_target = int(fallback_target or 0)
            if fallback_target > 0 and self._is_skill_strictly_ready(Signet_of_Disruption_ID):
                did_cast = yield from self.CastSkillIDAndRestoreTarget(
                    skill_id=Signet_of_Disruption_ID,
                    target_agent_id=fallback_target,
                    log=False,
                    aftercast_delay=40,
                )
                if did_cast:
                    target_id = int(fallback_target)
                    enemy_skill_id = 0
                    direct_interrupt = False
                    reason = f"same_pass_stale_interrupt_fallback_{fallback_reason}"
                    try:
                        from Py4GWCoreLib.Builds.Skills import CombatDebug
                        CombatDebug.log_event(
                            "SOD_STALE_INTERRUPT_SAME_PASS_FALLBACK",
                            target_id=int(target_id),
                            reason=str(reason),
                        )
                    except Exception:
                        pass

        if not did_cast:
            return False

        self._note_non_keystone_signet_cast()
        self._log_sod_cast_consumed("rotation_filler", target_id, enemy_skill_id)
        self._log_primary_signet_cast(
            Signet_of_Disruption_ID,
            target_id,
            reason=str(reason),
            path="disruption_rotation_filler",
        )
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "KEYSTONE_DISRUPTION_ROTATION_CAST",
                target_id=int(target_id),
                enemy_skill_id=int(enemy_skill_id),
                direct_interrupt=bool(direct_interrupt),
                reason=str(reason),
                ready_rank=int(rank),
                ready_count=int(ready_count),
                policy="no_reserve_immediate_filler",
            )
            if direct_interrupt:
                CombatDebug.register_interrupt_fired(
                    int(target_id), int(enemy_skill_id), int(Signet_of_Disruption_ID)
                )
        except Exception:
            pass
        return True

    def _log_disruption_team_availability(self) -> None:
        """Low-rate one-account log for the key metric: at least one interrupt ready."""
        if not self.IsSkillEquipped(Signet_of_Disruption_ID):
            return
        now = int(get_game_tick() or 0)
        if now <= 0:
            return
        last = int(getattr(self, "_disruption_availability_log_tick", 0) or 0)
        if last > 0 and now - last < int(DISRUPTION_AVAILABILITY_LOG_MS):
            return
        try:
            ready = self._disruption_ready_accounts()
            from Py4GWCoreLib import GLOBAL_CACHE
            own_email = str(Player.GetAccountEmail() or "").strip()
            all_users = []
            own_party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
            for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
                if not bool(getattr(account, "IsSlotActive", False)) or bool(getattr(account, "IsIsolated", False)):
                    continue
                party_id = int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)
                if own_party_id > 0 and party_id > 0 and party_id != own_party_id:
                    continue
                if not self._shared_skillbar_contains(account, Signet_of_Disruption_ID):
                    continue
                email = str(getattr(account, "AccountEmail", "") or "").strip()
                if email:
                    all_users.append(email)
            all_users = sorted(set(all_users))
            if not all_users or own_email != all_users[0]:
                return
            self._disruption_availability_log_tick = now
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "KEYSTONE_DISRUPTION_AVAILABILITY",
                ready_count=len(ready),
                total_count=len(all_users),
                any_ready=bool(ready),
            )
        except Exception:
            pass

    def _current_shared_cluster_members(self) -> set[int]:
        """Return the single current team packet. Empty means cleanup/no packet."""
        try:
            anchor = int(self._get_power_cluster_anchor() or 0)
            if anchor <= 0:
                return set()
            from Py4GWCoreLib import AgentArray
            arr = AgentArray.GetEnemyArray()
            arr = AgentArray.Filter.ByDistance(
                arr, Agent.GetXY(anchor), Range.Adjacent.value
            )
            return {
                int(aid) for aid in (arr or [])
                if int(aid or 0) > 0
                and Agent.IsValid(int(aid))
                and Agent.IsAlive(int(aid))
            }
        except Exception:
            return set()

    def _cast_opportunistic_offcluster_interrupt(self, snapshot: _KeystoneBarSnapshot):
        """No reserve, no claim, no approach.

        Only detour from the shared damage packet when a skill is ALREADY ready
        and an off-packet enemy is currently casting:
          - an offensive/dangerous caster skill, or
          - a resurrection.
        Heal/protection casts do NOT pull the Mesmers off the packet.
        If nothing can be fired immediately, normal packet/cleanup damage
        continues in the same controller pass.
        """
        if not snapshot.enemy_casting:
            return False

        try:
            from Py4GWCoreLib.Builds.Skills import CombatSense
            enemies = CombatSense.refresh(
                range_value=Range.Spellcast.value,
                throttle_ms=45,
            )
            cluster_members = self._current_shared_cluster_members()
            candidates = []
            for e in enemies:
                aid = int(e.agent_id)
                sid = int(e.casting_skill_id or 0)
                if aid <= 0 or sid <= 0 or aid in cluster_members:
                    continue

                # Never detour for normal heal/prot. Resurrection is explicitly
                # allowed; offensive shutdown/damage is allowed.
                if sid in CombatSense.PROT_HEAL_SKILL_IDS and sid not in CombatSense.REZ_SKILL_IDS:
                    continue
                is_rez = sid in CombatSense.REZ_SKILL_IDS
                is_offense = sid in CombatSense.AOE_SHUTDOWN_SKILL_IDS
                if not (is_rez or is_offense):
                    continue
                candidates.append((
                    0 if is_rez else 1,
                    -int(e.threat_score),
                    int(aid),
                    int(sid),
                ))
        except Exception:
            return False

        if not candidates:
            return False
        candidates.sort()

        for _kind, _threat, caster_id, enemy_skill_id in candidates:
            # 1) SoD direct interrupt if it is already ready.
            if (
                self._is_skill_strictly_ready(Signet_of_Disruption_ID)
                and self._signet_of_disruption_can_interrupt(caster_id, enemy_skill_id)
                and interrupt_is_feasible(caster_id, Signet_of_Disruption_ID)
            ):
                did_cast = yield from self.CastSkillIDAndRestoreTarget(
                    skill_id=Signet_of_Disruption_ID,
                    target_agent_id=int(caster_id),
                    extra_condition=lambda cid=int(caster_id), sid=int(enemy_skill_id): (
                        self._target_still_casting_safe_skill(cid, sid)
                        and self._signet_of_disruption_can_interrupt(cid, sid)
                    ),
                    log=False,
                    aftercast_delay=40,
                )
                if did_cast:
                    self._note_non_keystone_signet_cast()
                    try:
                        from Py4GWCoreLib.Builds.Skills import CombatDebug
                        CombatDebug.register_interrupt_fired(
                            int(caster_id), int(enemy_skill_id), int(Signet_of_Disruption_ID)
                        )
                        CombatDebug.log_event(
                            "KEYSTONE_OPPORTUNISTIC_OFFCLUSTER_INTERRUPT",
                            mode="sod_direct",
                            target_id=int(caster_id),
                            enemy_skill_id=int(enemy_skill_id),
                            policy="ready_now_no_reserve_no_claim_no_approach",
                        )
                    except Exception:
                        pass
                    return True

            # 2) Copied SoJ may directly KD the current offensive/rez caster.
            if (
                self._is_skill_strictly_ready(Signet_of_Judgment_ID)
                and self._is_signet_of_judgment_control_target_usable(
                    int(caster_id), check_claimed=False
                )
            ):
                did_cast = yield from self.CastSkillIDAndRestoreTarget(
                    skill_id=Signet_of_Judgment_ID,
                    target_agent_id=int(caster_id),
                    extra_condition=lambda cid=int(caster_id), sid=int(enemy_skill_id): (
                        self._target_still_casting_safe_skill(cid, sid)
                        and self._is_signet_of_judgment_control_target_usable(
                            cid, check_claimed=False
                        )
                    ),
                    log=False,
                    aftercast_delay=40,
                )
                if did_cast:
                    self._note_non_keystone_signet_cast()
                    try:
                        from Py4GWCoreLib.Builds.Skills import CombatDebug
                        CombatDebug.register_interrupt_fired(
                            int(caster_id), int(enemy_skill_id), int(Signet_of_Judgment_ID)
                        )
                        CombatDebug.log_event(
                            "KEYSTONE_OPPORTUNISTIC_OFFCLUSTER_INTERRUPT",
                            mode="copied_soj_direct",
                            target_id=int(caster_id),
                            enemy_skill_id=int(enemy_skill_id),
                            policy="ready_now_no_reserve_no_claim_no_approach",
                        )
                    except Exception:
                        pass
                    return True

            # 3) Bane/Ruins can opportunistically trigger Keystone through an
            # adjacent proxy if Keystone is active. No waiting if no proxy exists.
            if snapshot.has_keystone_signet and self._is_skill_strictly_ready(Bane_Signet_ID):
                proxy_id = int(self._pick_keystone_proxy_target(
                    int(caster_id), int(Bane_Signet_ID)
                ) or 0)
                if proxy_id > 0:
                    did_cast = yield from self.CastSkillIDAndRestoreTarget(
                        skill_id=Bane_Signet_ID,
                        target_agent_id=int(proxy_id),
                        extra_condition=lambda cid=int(caster_id), sid=int(enemy_skill_id), pid=int(proxy_id): (
                            self._target_still_casting_safe_skill(cid, sid)
                            and self._is_keystone_proxy_target_usable(
                                pid, cid, Bane_Signet_ID
                            )
                        ),
                        log=False,
                        aftercast_delay=40,
                    )
                    if did_cast:
                        self._note_non_keystone_signet_cast()
                        try:
                            from Py4GWCoreLib.Builds.Skills import CombatDebug
                            CombatDebug.register_interrupt_fired(
                                int(caster_id), int(enemy_skill_id), int(Bane_Signet_ID)
                            )
                            CombatDebug.log_event(
                                "KEYSTONE_OPPORTUNISTIC_OFFCLUSTER_INTERRUPT",
                                mode="bane_keystone_proxy",
                                target_id=int(caster_id),
                                proxy_id=int(proxy_id),
                                enemy_skill_id=int(enemy_skill_id),
                                policy="ready_now_no_reserve_no_claim_no_approach",
                            )
                        except Exception:
                            pass
                        return True

        return False

    def _cast_coordinated_cry_of_frustration(self):
        """Use optional Cry as a high-value packet interrupt without duplicate Cry casts.

        This path is active only when Cry of Frustration is actually equipped, so
        the normal Corruption/Sorrow/Unnatural Keystone bar is unchanged. A Cry
        may briefly cast at a dangerous off-focus packet; CastSkillIDAndRestoreTarget
        returns the Mesmer to the team's canonical focus immediately afterwards.
        """
        if int(Cry_of_Frustration_ID or 0) <= 0:
            return False
        if not self.IsSkillEquipped(Cry_of_Frustration_ID):
            return False
        if not self.CanCastSkillID(Cry_of_Frustration_ID):
            return False

        reservation = reserve_best_cry_packet()
        if reservation is None:
            return False

        target_id = int(reservation.target_id)
        enemy_skill_id = int(reservation.enemy_skill_id)
        did_cast = yield from self.CastSkillIDAndRestoreTarget(
            skill_id=Cry_of_Frustration_ID,
            target_agent_id=target_id,
            extra_condition=lambda: (
                int(get_danger_casting_skill_id(target_id) or 0) == enemy_skill_id
                and interrupt_is_feasible(target_id, Cry_of_Frustration_ID)
            ),
            log=False,
            aftercast_delay=40,
        )
        if did_cast:
            register_cry_fired(reservation, source="keystone")
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "KEYSTONE_CRY_PACKET_INTERRUPT",
                    target_id=int(target_id),
                    enemy_skill_id=int(enemy_skill_id),
                    packet_key=int(reservation.packet_key),
                    covered_count=int(len(reservation.covered_casts)),
                    policy="dangerous_packet_first_then_restore_canonical_focus",
                )
            except Exception:
                pass
            return True

        release_cry_reservation(reservation, reason="keystone_cry_not_fired")
        return False

    def _cast_safe_dangerous_interrupt(self, snapshot: _KeystoneBarSnapshot):
        """Coordinated direct, Keystone-proxy and SoJ emergency interrupts."""
        if not snapshot.enemy_casting:
            return False

        # Dedicated direct interrupts get first refusal.
        for skill_id, mark_signet_spent in (
            (Power_Drain_ID, False),
            (Cry_of_Frustration_ID, False),
            (Signet_of_Disruption_ID, True),
        ):
            if skill_id <= 0 or not self.IsSkillEquipped(skill_id):
                continue
            if not self.CanCastSkillID(skill_id):
                continue

            disruption_validator = (
                (lambda enemy_id, enemy_skill_id: self._signet_of_disruption_can_interrupt(
                    int(enemy_id), int(enemy_skill_id)
                ))
                if int(skill_id) == int(Signet_of_Disruption_ID)
                else None
            )
            target_agent_id, casting_skill_id = self._pick_safe_dangerous_interrupt_target(
                interrupter_skill_id=skill_id,
                validator=disruption_validator,
            )
            if target_agent_id <= 0 or casting_skill_id <= 0:
                continue

            keystone_covered_casts = (
                self._keystone_adjacent_danger_casts(target_agent_id)
                if mark_signet_spent and snapshot.has_keystone_signet
                else []
            )
            did_cast = yield from self.CastSkillIDAndRestoreTarget(
                skill_id=skill_id,
                target_agent_id=target_agent_id,
                extra_condition=lambda: self._target_still_casting_safe_skill(
                    target_agent_id, casting_skill_id
                ),
                log=False,
                aftercast_delay=250,
            )
            if did_cast:
                if mark_signet_spent:
                    self._note_non_keystone_signet_cast()
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.register_interrupt_fired(
                        target_agent_id, casting_skill_id, skill_id
                    )
                except Exception:
                    pass
                if keystone_covered_casts:
                    self._register_keystone_coverage(
                        target_agent_id, skill_id, keystone_covered_casts
                    )
                return True

            release_interrupt_claim(
                target_agent_id,
                casting_skill_id,
                reason="keystone_direct_not_fired",
            )

        # While Keystone is active, an ordinary signet on an adjacent proxy can
        # interrupt the dangerous caster. This was missing from the old planner.
        if (yield from self._cast_keystone_proxy_interrupt(snapshot)):
            return True

        # Slow control fallback only after direct/proxy options had their chance.
        skill_id = int(Signet_of_Judgment_ID or 0)
        if (
            skill_id > 0
            and self.IsSkillEquipped(skill_id)
            and snapshot.enemy_in_spellcast
            and self.CanCastSkillID(skill_id)
        ):
            target_agent_id, casting_skill_id = self._pick_safe_dangerous_interrupt_target(
                interrupter_skill_id=skill_id,
                validator=lambda enemy_id, cast_id: self._is_signet_of_judgment_control_target_usable(
                    enemy_id, check_claimed=False
                ),
            )
            if target_agent_id > 0 and casting_skill_id > 0:
                self._claim_signet_of_judgment_target(target_agent_id)
                keystone_covered_casts = (
                    self._keystone_adjacent_danger_casts(target_agent_id)
                    if snapshot.has_keystone_signet
                    else []
                )
                did_cast = yield from self.CastSkillIDAndRestoreTarget(
                    skill_id=skill_id,
                    target_agent_id=target_agent_id,
                    extra_condition=lambda: (
                        self._target_still_casting_safe_skill(
                            target_agent_id, casting_skill_id
                        )
                        and self._is_signet_of_judgment_control_target_usable(
                            target_agent_id, check_claimed=False
                        )
                    ),
                    log=False,
                    aftercast_delay=250,
                )
                if did_cast:
                    self._note_non_keystone_signet_cast()
                    try:
                        from Py4GWCoreLib.Builds.Skills import CombatDebug
                        CombatDebug.register_interrupt_fired(
                            target_agent_id, casting_skill_id, skill_id
                        )
                    except Exception:
                        pass
                    if keystone_covered_casts:
                        self._register_keystone_coverage(
                            target_agent_id, skill_id, keystone_covered_casts
                        )
                    return True
                release_interrupt_claim(
                    target_agent_id,
                    casting_skill_id,
                    reason="keystone_soj_not_fired",
                )

        return False

    def _has_hexed_ally_for_hex_eater(self) -> bool:
        """A ready Hex Eater should not block Keystone if nobody is hexed."""
        try:
            from Py4GWCoreLib import AgentArray
            for ally_id in AgentArray.GetAllyArray():
                if Routines.Checks.Agents.IsAlive(ally_id) and Routines.Checks.Agents.IsHexed(ally_id):
                    return True
        except Exception:
            return False
        return False

    def _ready_signet_should_block_keystone_reset(self, skill_id: int, snapshot: _KeystoneBarSnapshot) -> bool:
        """A ready signet blocks Keystone reset only if it is usable now."""
        if skill_id == Hex_Eater_Signet_ID:
            return self._has_hexed_ally_for_hex_eater()

        if skill_id == Signet_of_Disruption_ID:
            # Do not hold Keystone hostage for an idle isolated foe. Disruption
            # blocks reset only when it can interrupt something now or can
            # generate useful Keystone packet pressure.
            target_id, _reason = self._get_signet_of_disruption_filler_target(snapshot)
            return int(target_id or 0) > 0

        if skill_id in (Signet_of_Clumsiness_ID, Castigation_Signet_ID, Bane_Signet_ID):
            # FULL-SPAM damage signets (including Bane/Ruins): no reserve.
            # A ready damage signet is spent on any valid zero-idle target before
            # Keystone is allowed to reset the bar.
            return self._get_zero_idle_damage_target(int(skill_id))[0] > 0

        if skill_id == Signet_of_Judgment_ID:
            return self._get_signet_of_judgment_target(claim_target=False) > 0

        if skill_id == Tryptophan_Signet_ID:
            return snapshot.enemy_in_spellcast and self._get_tryptophan_signet_target() > 0

        if skill_id in (
            Unnatural_Signet_ID,
            Signet_of_Sorrow_ID,
            Signet_of_Weariness_ID,
            Signet_of_Corruption_Kurzick_ID,
            Signet_of_Corruption_Luxon_ID,
        ):
            return self._get_zero_idle_damage_target(int(skill_id))[0] > 0

        # Unknown optional signets are treated conservatively: if they are ready,
        # try to spend them before Keystone resets.
        return True

    def _all_other_equipped_signets_spent_or_unusable(self, snapshot: _KeystoneBarSnapshot) -> bool:
        other_signet_found = False
        for slot in range(1, 9):
            skill_id = int(SkillBar.GetSkillIDBySlot(slot) or 0)
            if skill_id == 0 or skill_id == Keystone_Signet_ID:
                continue
            if not Skill.Flags.IsSignet(skill_id):
                continue

            other_signet_found = True

            if not Routines.Checks.Skills.IsSkillSlotReady(slot):
                continue

            if self._ready_signet_should_block_keystone_reset(skill_id, snapshot):
                return False

        return other_signet_found

    def _note_non_keystone_signet_cast(self) -> None:
        self._non_keystone_signet_cast_since_last_keystone = True

    def _note_keystone_reset_cast(self) -> None:
        # After Keystone is used as the reset, start a fresh spending cycle.
        self._non_keystone_signet_cast_since_last_keystone = False
        self._precombat_keystone_primed = False

    def _note_keystone_prime_cast(self, snapshot: _KeystoneBarSnapshot) -> None:
        # Outside combat, allow only one pre-pull prime while close to the group.
        # In combat, Keystone may still be maintained for its offensive effect,
        # but this must not clear the spent-signet flag used for reset timing.
        if not snapshot.enemy_in_spellcast:
            self._precombat_keystone_primed = True

    def _has_spent_non_keystone_signet(self) -> bool:
        if self._non_keystone_signet_cast_since_last_keystone:
            return True

        # Fallback for cases where this build logic started mid-combat or a
        # signet was cast by another path: if any equipped non-Keystone signet
        # is on recharge, consider the current cycle as spent.
        for slot in range(1, 9):
            skill_id = int(SkillBar.GetSkillIDBySlot(slot) or 0)
            if skill_id == 0 or skill_id == Keystone_Signet_ID:
                continue
            if not Skill.Flags.IsSignet(skill_id):
                continue
            if not Routines.Checks.Skills.IsSkillSlotReady(slot):
                return True

        return False

    def _should_cast_keystone_signet(self, snapshot: _KeystoneBarSnapshot) -> bool:
        if not snapshot.precombat_setup or not snapshot.has_symbolic_celerity or snapshot.has_keystone_signet:
            return False

        # Once an enemy is in spellcast range, keep Keystone ready for the
        # offensive signet package.
        if snapshot.enemy_in_spellcast:
            return snapshot.keystone_signet_needed

        # Before the pull: prime Keystone once in the expanded setup radius,
        # but do not spam it while waiting near an enemy group.
        return snapshot.keystone_signet_needed and not self._precombat_keystone_primed

    def _should_reset_signets_with_keystone(self, snapshot: _KeystoneBarSnapshot) -> bool:
        if not snapshot.close_to_aggro or not snapshot.has_symbolic_celerity:
            return False
        # Never reset over a genuinely ready primary damage signet.
        if self._has_ready_primary_damage_signet():
            return False
        if not self._has_spent_non_keystone_signet():
            return False
        return self._all_other_equipped_signets_spent_or_unusable(snapshot)

    def _is_skill_strictly_ready(self, skill_id: int) -> bool:
        """Check the exact equipped slot, recharge and normal cast gates.

        This avoids decision/log attempts for a skill whose ID exists but whose
        actual slot is still recharging (important around Arcane Mimicry slot
        replacement and Keystone resets).
        """
        skill_id = int(skill_id or 0)
        if skill_id <= 0 or not self.IsSkillEquipped(skill_id):
            return False
        try:
            slot = int(SkillBar.GetSlotBySkillID(skill_id) or 0)
            if not (1 <= slot <= 8):
                return False
            if not Routines.Checks.Skills.IsSkillSlotReady(slot):
                return False
        except Exception:
            return False
        return bool(self.CanCastSkillID(skill_id))

    def _get_unnatural_signet_fast_target(self) -> tuple[int, str]:
        """Prefer a hexed/enchanted target for Unnatural's adjacent bonus.

        If none exists, immediately fall back to the normal zero-idle target;
        the unconditional primary damage is still worth casting.
        """
        enemies = self._get_zero_idle_enemy_targets()
        enhanced = []
        for enemy_id in enemies:
            try:
                if Agent.IsHexed(enemy_id) or Agent.IsEnchanted(enemy_id):
                    enhanced.append(int(enemy_id))
            except Exception:
                continue
        if enhanced:
            enhanced.sort(key=lambda enemy_id: (
                -self._count_signet_of_judgment_adjacent_enemies(enemy_id),
                self._distance_to_player(enemy_id),
                int(enemy_id),
            ))
            return int(enhanced[0]), "hexed_or_enchanted_aoe"
        return self._get_zero_idle_damage_target(int(Unnatural_Signet_ID))

    def _cast_immediate_primary_damage_signet(self, snapshot: _KeystoneBarSnapshot):
        """Hard fast-path: SoJ -> Unnatural -> Bane -> Castigation.

        Castigation is optional and is included only when it is equipped. The
        path runs before Keystone reset logic, so Keystone cannot reset while an
        equipped offensive signet is genuinely ready and a valid enemy exists.
        Claims only influence target preference; they never block this path.
        """
        # Dynamic throughput order:
        #   SoJ first.  Sorrow gets a special corpse-confirmed turbo lane because
        #   the nearby-corpse condition can instantly recharge it; otherwise
        #   Unnatural is the reliable 10s-recharge damage signet and must not be
        #   starved behind ordinary Sorrow/Corruption filler casts.
        #
        # The corpse-Sorrow attempt is handled before this loop.
        if self._is_skill_strictly_ready(int(Signet_of_Judgment_ID or 0)):
            target_id = int(self._get_signet_of_judgment_target(claim_target=True) or 0)
            if target_id > 0 and Routines.Checks.Agents.IsAlive(target_id):
                did_cast = yield from self.CastSkillIDAndRestoreTarget(
                    skill_id=int(Signet_of_Judgment_ID),
                    target_agent_id=target_id,
                    log=False,
                    aftercast_delay=40,
                )
                if did_cast:
                    self._note_non_keystone_signet_cast()
                    self._log_primary_signet_cast(
                        int(Signet_of_Judgment_ID), target_id,
                        reason="balanced_soj_first", path="strict_primary_damage",
                    )
                    return True

        if self._is_skill_strictly_ready(int(Signet_of_Sorrow_ID or 0)):
            sorrow_target = int(self._get_sorrow_signet_target(require_corpse=True, claim_target=True) or 0)
            if sorrow_target > 0 and Routines.Checks.Agents.IsAlive(sorrow_target):
                did_cast = yield from self.CastSkillIDAndRestoreTarget(
                    skill_id=int(Signet_of_Sorrow_ID),
                    target_agent_id=sorrow_target,
                    log=False,
                    aftercast_delay=40,
                )
                if did_cast:
                    self._note_non_keystone_signet_cast()
                    self._log_primary_signet_cast(
                        int(Signet_of_Sorrow_ID), sorrow_target,
                        reason="corpse_instant_recharge_turbo", path="strict_primary_damage",
                    )
                    try:
                        from Py4GWCoreLib.Builds.Skills import CombatDebug
                        CombatDebug.log_event(
                            "KEYSTONE_SORROW_TURBO_CAST",
                            skill_id=int(Signet_of_Sorrow_ID),
                            target_id=int(sorrow_target),
                            policy="corpse_sorrow_before_unnatural",
                        )
                    except Exception:
                        pass
                    return True

        for skill_id in (
            Unnatural_Signet_ID,
            Signet_of_Corruption_Kurzick_ID,
            Signet_of_Corruption_Luxon_ID,
            Signet_of_Sorrow_ID,
            Bane_Signet_ID,
            Castigation_Signet_ID,
        ):
            skill_id = int(skill_id or 0)
            if not self._is_skill_strictly_ready(skill_id):
                continue

            if skill_id == int(Signet_of_Judgment_ID):
                target_id = int(self._get_signet_of_judgment_target(claim_target=True) or 0)
                reason = "balanced_soj_first"
            elif skill_id == int(Unnatural_Signet_ID):
                target_id, reason = self._get_unnatural_signet_fast_target()
                target_id = int(target_id or 0)
            else:
                target_id, reason = self._get_zero_idle_damage_target(skill_id)
                target_id = int(target_id or 0)

            if target_id <= 0 or not Routines.Checks.Agents.IsAlive(target_id):
                continue

            did_cast = yield from self.CastSkillIDAndRestoreTarget(
                skill_id=skill_id,
                target_agent_id=target_id,
                log=False,
                aftercast_delay=40,
            )
            if did_cast:
                self._note_non_keystone_signet_cast()
                self._log_primary_signet_cast(
                    skill_id,
                    target_id,
                    reason=str(reason),
                    path="strict_primary_damage",
                )
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "KEYSTONE_STRICT_DAMAGE_CAST",
                        skill_id=skill_id,
                        target_id=target_id,
                        reason=str(reason),
                        policy="zero_idle_soj_unnatural_bane_castigation_before_keystone",
                    )
                except Exception:
                    pass
                return True
        return False

    def _should_defer_sorrow_turbo(self) -> tuple[bool, str]:
        """Bound corpse-Sorrow turbo so other high-value ready signets still fire."""
        if int(getattr(self, "_sorrow_turbo_streak", 0) or 0) < 1:
            return False, "first_turbo_allowed"

        # A real Unnatural AoE is worth interleaving immediately.
        if self._is_skill_strictly_ready(int(Unnatural_Signet_ID or 0)):
            try:
                target_id, reason = self._get_unnatural_signet_fast_target()
                if int(target_id or 0) > 0 and "hexed_or_enchanted_aoe" in str(reason or ""):
                    return True, "ready_unnatural_aoe"
            except Exception:
                pass

        # Corruption may not sit ready indefinitely behind an instant-recharging
        # Sorrow loop. After ~1.0s ready, interleave it once, then turbo can resume.
        now = int(get_game_tick() or 0)
        for cid in (int(Signet_of_Corruption_Kurzick_ID or 0), int(Signet_of_Corruption_Luxon_ID or 0)):
            if cid <= 0 or not self.IsSkillEquipped(cid) or not self._is_skill_strictly_ready(cid):
                continue
            since = int(self._signet_ready_since.get(cid, 0) or 0)
            if since > 0 and now - since >= 1000:
                return True, "corruption_ready_1000ms"

        # Even without the two cases above, never allow more than two corpse turbo
        # casts in a row while another damage signet is ready.
        if int(getattr(self, "_sorrow_turbo_streak", 0) or 0) >= 2:
            for sid in (int(Unnatural_Signet_ID or 0), int(Signet_of_Corruption_Kurzick_ID or 0), int(Signet_of_Corruption_Luxon_ID or 0)):
                if sid > 0 and self.IsSkillEquipped(sid) and self._is_skill_strictly_ready(sid):
                    return True, "max_two_turbo_then_interleave"
        return False, "turbo_continue"

    def _cast_full_throughput_signet_spam(self, snapshot: _KeystoneBarSnapshot):
        """Maximum-throughput foe-signet rotation.

        Priority:
            copied Signet of Judgment
            -> Signet of Sorrow when a corpse can trigger instant recharge
            -> Unnatural Signet on a real enhanced AoE packet
            -> otherwise Signet of Corruption before single-target Unnatural
            -> ordinary Signet of Sorrow
            -> backward-compatible filler signets

        There is deliberately NO interrupt planning, reservation, claim wait,
        dangerous-cast detour, round-robin hold, or "wait for a cast" gate here.
        If a signet is ready and a legal enemy target exists, fire it now.
        """
        dangerous_caster_packet = False
        try:
            from Py4GWCoreLib.Builds.Skills.CombatSense import dangerous_aoe_caster_cluster
            dangerous_caster_packet, _danger_anchor, _danger_members = dangerous_aoe_caster_cluster(
                range_value=Range.Spellcast.value,
                minimum_dangerous_casters=2,
            )
        except Exception:
            dangerous_caster_packet = False

        # SoJ remains absolute priority.  After SoJ, corpse-confirmed Sorrow
        # is allowed to turbo-loop; without that instant-recharge condition,
        # Unnatural is intentionally ahead of Corruption and ordinary Sorrow.
        if self._is_skill_strictly_ready(int(Signet_of_Judgment_ID or 0)):
            target_id = int(self._get_signet_of_judgment_target(claim_target=True) or 0)
            if target_id > 0 and Routines.Checks.Agents.IsAlive(target_id):
                did_cast = yield from self.CastSkillIDAndRestoreTarget(
                    skill_id=int(Signet_of_Judgment_ID), target_agent_id=target_id,
                    log=False, aftercast_delay=40,
                )
                if did_cast:
                    self._note_non_keystone_signet_cast()
                    self._log_primary_signet_cast(
                        int(Signet_of_Judgment_ID), target_id,
                        reason="full_spam_soj", path="full_throughput",
                    )
                    return True

        if self._is_skill_strictly_ready(int(Signet_of_Sorrow_ID or 0)):
            defer_turbo, defer_reason = self._should_defer_sorrow_turbo()
            if not defer_turbo:
                sorrow_target = int(self._get_sorrow_signet_target(require_corpse=True, claim_target=True) or 0)
                if sorrow_target > 0 and Routines.Checks.Agents.IsAlive(sorrow_target):
                    did_cast = yield from self.CastSkillIDAndRestoreTarget(
                        skill_id=int(Signet_of_Sorrow_ID), target_agent_id=sorrow_target,
                        log=False, aftercast_delay=40,
                    )
                    if did_cast:
                        self._note_non_keystone_signet_cast()
                        self._sorrow_turbo_streak = int(getattr(self, "_sorrow_turbo_streak", 0) or 0) + 1
                        self._log_primary_signet_cast(
                            int(Signet_of_Sorrow_ID), int(sorrow_target),
                            reason="corpse_instant_recharge_turbo", path="sorrow_turbo",
                        )
                        try:
                            from Py4GWCoreLib.Builds.Skills import CombatDebug
                            CombatDebug.log_event(
                                "KEYSTONE_SORROW_TURBO_CAST",
                                skill_id=int(Signet_of_Sorrow_ID),
                                target_id=int(sorrow_target),
                                turbo_streak=int(self._sorrow_turbo_streak),
                                policy="bounded_turbo_interleave_unnatural_corruption",
                            )
                        except Exception:
                            pass
                        return True
            else:
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "KEYSTONE_SORROW_TURBO_DEFER",
                        reason=str(defer_reason),
                        turbo_streak=int(getattr(self, "_sorrow_turbo_streak", 0) or 0),
                        policy="interleave_ready_high_value_signet",
                    )
                except Exception:
                    pass

        # Adaptive Corruption/Unnatural lane.  Unnatural keeps priority when it
        # has a real hexed/enchanted AoE packet (its best use case).  Otherwise
        # Corruption goes first so it cannot sit ready for 5-7 seconds during
        # small packets/cleanup while Unnatural is only providing single-target
        # pressure.  This preserves the strong Unnatural cluster spam measured
        # in the current logs while recovering otherwise wasted Corruption casts.
        unnatural_probe_target = 0
        unnatural_probe_reason = ""
        if self._is_skill_strictly_ready(int(Unnatural_Signet_ID or 0)):
            try:
                unnatural_probe_target, unnatural_probe_reason = self._get_unnatural_signet_fast_target()
                unnatural_probe_target = int(unnatural_probe_target or 0)
                unnatural_probe_reason = str(unnatural_probe_reason or "")
            except Exception:
                unnatural_probe_target, unnatural_probe_reason = 0, ""

        unnatural_has_real_aoe = False
        if unnatural_probe_target > 0 and "hexed_or_enchanted_aoe" in unnatural_probe_reason:
            try:
                unnatural_has_real_aoe = (
                    int(self._count_signet_of_judgment_adjacent_enemies(unnatural_probe_target) or 0) >= 1
                )
            except Exception:
                unnatural_has_real_aoe = True

        corruption_ids = (
            Signet_of_Corruption_Kurzick_ID,
            Signet_of_Corruption_Luxon_ID,
        )
        # Moderate anti-starvation: preserve fresh Unnatural AoE priority, but if
        # Corruption has already been ready for 2.5s, spend it before another AoE
        # Unnatural. This targets the long live-log outliers without disturbing
        # the excellent median/zero-idle Unnatural behavior.
        now_tick = int(get_game_tick() or 0)
        aged_corruption = False
        for cid in corruption_ids:
            cid = int(cid or 0)
            if cid <= 0 or not self.IsSkillEquipped(cid) or not self._is_skill_strictly_ready(cid):
                continue
            since = int(self._signet_ready_since.get(cid, 0) or 0)
            if since > 0 and now_tick - since >= 2500:
                aged_corruption = True
                break
        if unnatural_has_real_aoe and not aged_corruption:
            adaptive_damage_order = (Unnatural_Signet_ID,) + corruption_ids
            adaptive_policy = "unnatural_aoe_before_fresh_corruption"
        else:
            adaptive_damage_order = corruption_ids + (Unnatural_Signet_ID,)
            adaptive_policy = (
                "aged_corruption_2500ms_before_unnatural"
                if aged_corruption else "corruption_before_single_target_unnatural"
            )

        for skill_id in adaptive_damage_order + (
            Signet_of_Sorrow_ID,
            # Backward-compatible fallbacks: if an older bar still equips one
            # of these, it is also allowed to spam immediately.
            Signet_of_Disruption_ID,
            Bane_Signet_ID,
            Castigation_Signet_ID,
        ):
            skill_id = int(skill_id or 0)
            if skill_id <= 0 or not self.IsSkillEquipped(skill_id):
                continue
            if not self._is_skill_strictly_ready(skill_id):
                continue

            if skill_id == int(Signet_of_Judgment_ID):
                target_id = int(self._get_signet_of_judgment_target(claim_target=True) or 0)
                reason = "full_spam_soj"
            elif skill_id == int(Signet_of_Sorrow_ID):
                # Me/N MAX-SPAM: no waiting for a corpse condition. Cast as soon
                # as the signet is ready. If a nearby corpse causes the skill to
                # recharge instantly, it returns to the top of this priority
                # list on the next controller pass and is fired again.
                target_id, sorrow_target_reason = self._get_zero_idle_damage_target(skill_id)
                target_id = int(target_id or 0)
                reason = f"full_spam_sorrow_{sorrow_target_reason}"
            elif skill_id in (
                int(Signet_of_Corruption_Kurzick_ID),
                int(Signet_of_Corruption_Luxon_ID),
            ):
                # Do not wait for the 'perfect' hex/condition packet. The base
                # signet + Keystone pressure is valuable immediately; existing
                # conditions/hexes only improve the result.
                target_id, corruption_target_reason = self._get_zero_idle_damage_target(skill_id)
                target_id = int(target_id or 0)
                reason = f"full_spam_corruption_{corruption_target_reason}_{adaptive_policy}"
            elif skill_id == int(Signet_of_Disruption_ID):
                # Backward-compatible SoD: unconditional pressure if still equipped.
                target_id, sod_target_reason = self._get_zero_idle_damage_target(skill_id)
                target_id = int(target_id or 0)
                reason = f"full_spam_sod_unconditional_{sod_target_reason}"
            elif skill_id == int(Unnatural_Signet_ID):
                if unnatural_probe_target > 0:
                    target_id = int(unnatural_probe_target)
                    reason = str(unnatural_probe_reason or "zero_idle")
                else:
                    target_id, reason = self._get_unnatural_signet_fast_target()
                    target_id = int(target_id or 0)
                reason = f"full_spam_{reason}_{adaptive_policy}"
            else:
                target_id, reason = self._get_zero_idle_damage_target(skill_id)
                target_id = int(target_id or 0)
                reason = f"full_spam_{reason}"

            if target_id <= 0 or not Routines.Checks.Agents.IsAlive(target_id):
                continue

            enemy_skill_before = 0
            try:
                if Agent.IsCasting(int(target_id)):
                    enemy_skill_before = int(Agent.GetCastingSkillID(int(target_id)) or 0)
            except Exception:
                enemy_skill_before = 0

            did_cast = yield from self.CastSkillIDAndRestoreTarget(
                skill_id=skill_id,
                target_agent_id=target_id,
                log=False,
                aftercast_delay=40,
            )
            if not did_cast:
                continue

            self._note_non_keystone_signet_cast()

            # Diagnostic only: if the enemy was casting when this MAX-SPAM
            # signet was fired, follow that activation for a short window and
            # classify whether the cast stopped after our hit.
            if enemy_skill_before > 0:
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.register_interrupt_fired(
                        int(target_id),
                        int(enemy_skill_before),
                        int(skill_id),
                    )
                    CombatDebug.log_event(
                        "INTERRUPT_CANDIDATE_FIRED",
                        target_id=int(target_id),
                        enemy_skill_id=int(enemy_skill_before),
                        source_skill_id=int(skill_id),
                        policy="max_spam_no_reservation_measure_only",
                    )
                except Exception:
                    pass

            if dangerous_caster_packet and int(skill_id) == int(Signet_of_Judgment_ID):
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "DANGEROUS_CASTER_SOJ_OPENER",
                        target_id=int(target_id),
                        policy="soj_first_no_team_offense_gate",
                    )
                except Exception:
                    pass

            self._log_primary_signet_cast(
                skill_id,
                target_id,
                reason=str(reason),
                path="full_throughput_spam",
            )
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "KEYSTONE_FULL_SPAM_CAST",
                    skill_id=int(skill_id),
                    target_id=int(target_id),
                    reason=str(reason),
                    policy="soj_sod_ruin_unnatural_immediate_no_interrupt_logic",
                )
            except Exception:
                pass
            return True

        return False

    def _has_ready_primary_damage_signet(self) -> bool:
        """Return True while a high-value offensive signet can be fired now.

        With four Keystone Mesmers, reserving a ready offensive signet for a
        hypothetical future interrupt costs more pressure than it saves. Claims
        and interrupt planning therefore must not delay SoJ, Unnatural, Bane, or
        an equipped Castigation Signet.
        """
        for skill_id in (
            Signet_of_Judgment_ID,
            Signet_of_Sorrow_ID,
            Signet_of_Corruption_Kurzick_ID,
            Signet_of_Corruption_Luxon_ID,
            Unnatural_Signet_ID,
            Bane_Signet_ID,
            Castigation_Signet_ID,
        ):
            skill_id = int(skill_id or 0)
            if skill_id <= 0 or not self.IsSkillEquipped(skill_id):
                continue
            if self._is_skill_strictly_ready(skill_id):
                return True
        return False

    def _run_local_skill_logic(self):
        refresh_aoe_danger_zones()
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.verify_interrupt_outcomes()
        except Exception:
            pass

        # Read-only profiling. No combat decision depends on these calls.
        self._track_sod_ready_idle()
        self._track_primary_signet_idle()
        self._track_mimicry_soj_window()
        self._track_keystone_mantra_state()
        # No asynchronous HP probe polling here. Mantra telemetry is passive and
        # piggybacks on the existing signet cast profile only.
        # Confirmed/provisionally committed danger always beats an interrupt
        # approach.  Normally the approach claim exists before the 90% pre-arm
        # point, so this branch is reached only when the interrupt path failed.
        if avoid_active_aoe_if_needed(role="keystone", allow_actions_at_safe_hold=True):
            self._clear_interrupt_approach(
                reason="aoe_escape_override", release_claim=True, log_abort=True
            )
            return True

        # No interrupt-approach movement/reservation in this build. Interrupts
        # are purely opportunistic: the signet must already be ready and the
        # caster must already be in usable range.
        safe_aoe_hold = is_aoe_escape_safe_hold_active(role="keystone")
        self._clear_interrupt_approach(
            reason="opportunistic_only_no_approach",
            release_claim=True,
            log_abort=False,
        )

        if not Routines.Checks.Skills.CanCast():
            self._log_rotation_stall("global_can_cast_false")
            return False

        snapshot = self._get_bar_snapshot()
        if not snapshot.precombat_setup:
            self._precombat_keystone_primed = False
            self._non_keystone_signet_cast_since_last_keystone = False

        player_energy_pct = float(Agent.GetEnergy(Player.GetAgentID()))
        should_reset_signets = self._should_reset_signets_with_keystone(snapshot)
        should_cast_keystone = self._should_cast_keystone_signet(snapshot)
        # Aggressive packet-pressure policy:
        # Do not require an enemy to already be inside the old spellcast snapshot
        # before spending ready signets.  A real nearby fight is enough.  This
        # removes the 2-3s ready-idle windows seen in HM Urgoz while preserving
        # the absolute interrupt-first branch above all damage use.
        combat_pressure = bool(
            snapshot.enemy_in_spellcast
            or snapshot.enemy_casting
            or self.IsInAggro()
            or self.IsCloseToAggro()
        )
        can_spend_non_keystone_signets = bool(
            combat_pressure
            and not self._should_gate_signet_spend_for_mantra(
                snapshot, should_reset_signets, should_cast_keystone
            )
        )
        if not combat_pressure:
            self._disruption_opening_spent = False
        single_cleanup_target = self._single_target_cleanup_target()
        single_target_cleanup = bool(single_cleanup_target)

        # Optional Cry of Frustration variant. When a Keystone Mesmer equips Cry
        # instead of Corruption, high-value enemy casts get first refusal before
        # the normal signet throughput lane. Cross-account packet reservations
        # prevent two Cry holders from firing into the same AoE packet, while a
        # second spatially separate dangerous packet can be interrupted in parallel.
        if snapshot.enemy_casting and (yield from self._cast_coordinated_cry_of_frustration()):
            return True

        # FULL-THROUGHPUT TEST:
        # Signet of Disruption interrupt intelligence is intentionally disabled.
        # is treated as ordinary pressure and is never held for an enemy cast.
        # The first ready foe-targeted signet in the fixed priority is fired now.
        self._log_disruption_team_availability()
        if can_spend_non_keystone_signets:
            if (yield from self._cast_full_throughput_signet_spam(snapshot)):
                return True


        if self.IsSkillEquipped(Animate_Flesh_Golem_ID) and (yield from self.skills.Necromancer.DeathMagic.Animate_Flesh_Golem()):
            return True

        if self.IsSkillEquipped(Animate_Bone_Fiend_ID) and (yield from self.skills.Necromancer.DeathMagic.Animate_Bone_Fiend()):
            return True

        if self.IsSkillEquipped(Animate_Bone_Horror_ID) and (yield from self.skills.Necromancer.DeathMagic.Animate_Bone_Horror()):
            return True

        if self.IsSkillEquipped(Animate_Bone_Minions_ID) and (yield from self.skills.Necromancer.DeathMagic.Animate_Bone_Minions()):
            return True

        if self.IsSkillEquipped(Animate_Shambling_Horror_ID) and (yield from self.skills.Necromancer.DeathMagic.Animate_Shambling_Horror()):
            return True

        if self.IsSkillEquipped(Animate_Vampiric_Horror_ID) and (yield from self.skills.Necromancer.DeathMagic.Animate_Vampiric_Horror()):
            return True

        if (yield from self.skills.Monk.SmitingPrayers.Smite_Hex(min_priority=HexRemovalPriority.HIGH)):
            return True

        if (
            snapshot.symbolic_setup
            and snapshot.symbolic_celerity_needed
            and (yield from self.skills.Mesmer.FastCasting.Symbolic_Celerity())
        ):
            return True

        # Air of Superiority is pre-burst setup for Keystone Mesmers. Cast it
        # before Arcane Mimicry / Keystone / offensive signets, but do not make
        # it part of the signet-reset accounting.
        if (yield from self._cast_air_of_superiority_setup(snapshot)):
            return True

        # Symbolic Posture is a setup stance and does not end until a signet is
        # successfully activated. Cast it shortly before the Arcane Mimicry /
        # Keystone window so the first Keystone Signet benefits without wasting
        # the copied SoJ timer while running in.
        if (
            snapshot.precombat_setup
            and self.IsSkillEquipped(Symbolic_Posture_ID)
            and snapshot.symbolic_posture_needed
            and self.CanCastSkillID(Keystone_Signet_ID)
        ):
            if (yield from self.skills.Mesmer.FastCasting.Symbolic_Posture()):
                return True

        if (yield from self._cast_arcane_mimicry_for_signet_of_judgment(snapshot)):
            return True

        if should_reset_signets and snapshot.has_symbolic_posture:
            if (yield from self.skills.Mesmer.FastCasting.Keystone_Signet(allow_existing_effect=True)):
                self._note_keystone_reset_cast()
                return True

        if (
            should_reset_signets
            and self.IsSkillEquipped(Symbolic_Posture_ID)
            and snapshot.symbolic_posture_needed
            and self.CanCastSkillID(Keystone_Signet_ID)
        ):
            if (yield from self.skills.Mesmer.FastCasting.Symbolic_Posture()):
                return True

        if should_reset_signets and (
            yield from self.skills.Mesmer.FastCasting.Keystone_Signet(allow_existing_effect=True)
        ):
            self._note_keystone_reset_cast()
            return True

        if snapshot.has_symbolic_posture and should_cast_keystone:
            if (yield from self.skills.Mesmer.FastCasting.Keystone_Signet()):
                self._note_keystone_reset_cast()
                return True

        # Mantra A/B setup. Do this only after any pending Symbolic Posture ->
        # Keystone action. Both Mantras are stances, so casting one before
        # Symbolic Posture would immediately throw the Mantra away.
        if not should_reset_signets and not should_cast_keystone:
            if (yield from self._cast_keystone_mantra_setup(snapshot)):
                return True

        # Hex Eater Signet is ally-targeted, so it is reserved for real hex removal.
        # It must not be used as a Keystone filler: Keystone's AoE damage/interrupt
        # only applies to signets that target a foe, and a ready Hex Eater with no
        # hexed ally should not delay the Keystone reset cycle.
        if (
            can_spend_non_keystone_signets
            and self.IsSkillEquipped(Hex_Eater_Signet_ID)
            and self._has_hexed_ally_for_hex_eater()
        ):
            if (yield from self.skills.Mesmer.InspirationMagic.Hex_Eater_Signet()):
                self._note_non_keystone_signet_cast()
                return True

        if self.IsSkillEquipped(Breath_of_the_Great_Dwarf_ID) and (yield from self.skills.Any.NoAttribute.Breath_of_the_Great_Dwarf()):
            return True

        if self.IsSkillEquipped(Blood_Ritual_ID) and (yield from self.skills.Necromancer.BloodMagic.Blood_Ritual()):
            return True

        if not snapshot.precombat_setup:
            self._log_rotation_stall("end_of_combat_rotation_no_action", snapshot)
            return False

        if (
            should_cast_keystone
            and self.IsSkillEquipped(Symbolic_Posture_ID)
            and snapshot.symbolic_posture_needed
            and self.CanCastSkillID(Keystone_Signet_ID)
        ):
            if (yield from self.skills.Mesmer.FastCasting.Symbolic_Posture()):
                return True

        if should_cast_keystone and (yield from self.skills.Mesmer.FastCasting.Keystone_Signet()):
            self._note_keystone_prime_cast(snapshot)
            return True

        if self.IsSkillEquipped(Death_Nova_ID) and (yield from self.skills.Necromancer.DeathMagic.Death_Nova()):
            return True

        if (
            can_spend_non_keystone_signets
            and (yield from self._cast_copied_signet_of_judgment(snapshot))
        ):
            return True

        # Aggressive damage-signets: once setup, emergency interrupts and copied
        # SoJ have been handled, spend every ready foe-targeted damage signet
        # immediately. Do not wait for a caster, an attacker, a perfect packet,
        # or a free distribution claim. Claims remain a preferred target hint,
        # but they are never allowed to create combat idle time.
        if can_spend_non_keystone_signets:
            aggressive_signet_order = (
                Unnatural_Signet_ID,
                Bane_Signet_ID,
                Castigation_Signet_ID,
            )
            for aggressive_skill_id in aggressive_signet_order:
                if aggressive_skill_id <= 0:
                    continue
                if not self.IsSkillEquipped(aggressive_skill_id):
                    continue
                if not self._is_skill_strictly_ready(aggressive_skill_id):
                    continue

                aggressive_target_id, zero_idle_reason = self._get_zero_idle_damage_target(
                    int(aggressive_skill_id)
                )
                if aggressive_target_id <= 0:
                    continue

                did_cast = yield from self.CastSkillIDAndRestoreTarget(
                    skill_id=int(aggressive_skill_id),
                    target_agent_id=int(aggressive_target_id),
                    log=False,
                    aftercast_delay=40,
                )
                if did_cast:
                    self._note_non_keystone_signet_cast()
                    try:
                        from Py4GWCoreLib.Builds.Skills import CombatDebug
                        CombatDebug.log_event(
                            "KEYSTONE_SIGNET_FAST_CAST",
                            skill_id=int(aggressive_skill_id),
                            target_id=int(aggressive_target_id),
                            reason=str(zero_idle_reason),
                            enemy_count=int(len(self._get_zero_idle_enemy_targets())),
                            policy="damage_first_no_reserve",
                        )
                    except Exception:
                        pass
                    return True

        # Exactly the Keystone Mesmers that equip Mistrust use this path.
        # A dedicated team lock spreads the two casts across different offensive
        # casters inside the same selected cluster. It does not consume the
        # Keystone signet-reset cycle because Mistrust is a spell, not a signet.
        if (
            self.IsSkillEquipped(Mistrust_ID)
            and self._is_skill_strictly_ready(Mistrust_ID)
        ):
            # Damage signets above are never delayed for Mistrust. Once they are
            # spent/unavailable, use Mistrust intelligently: active caster first,
            # otherwise a known high-value caster likely to cast soon.
            mistrust_target, mistrust_reason = self._get_mistrust_target()
            if mistrust_target and (yield from self.CastSkillIDAndRestoreTarget(
                skill_id=Mistrust_ID,
                target_agent_id=mistrust_target,
                log=False,
                aftercast_delay=120,
            )):
                try:
                    from Py4GWCoreLib.Builds.Skills import MistrustTracker
                    MistrustTracker.register_cast(
                        source_id=int(Player.GetAgentID() or 0),
                        target_id=int(mistrust_target),
                        duration_ms=int(MISTRUST_TARGET_LOCK_MS),
                    )
                except Exception:
                    pass
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "KEYSTONE_MISTRUST_CAST",
                        target_id=int(mistrust_target),
                        reason=str(mistrust_reason),
                        policy="distributed_meaningful_only",
                    )
                except Exception:
                    pass
                return True

        # V26.5 single-target cleanup:
        # When exactly one relevant foe remains, do not wait for AoE packet or
        # enemy-casting conditions before spending safe foe-targeted damage
        # signets. Conditional control signets still keep their own requirements.
        if can_spend_non_keystone_signets and single_target_cleanup:
            cleanup_skill_order = (
                Unnatural_Signet_ID,
                Signet_of_Sorrow_ID,
                Signet_of_Corruption_Kurzick_ID,
                Signet_of_Corruption_Luxon_ID,
                Signet_of_Weariness_ID,
            )
            for cleanup_skill_id in cleanup_skill_order:
                if cleanup_skill_id <= 0:
                    continue
                if not self.IsSkillEquipped(cleanup_skill_id):
                    continue
                if not self.CanCastSkillID(cleanup_skill_id):
                    continue
                did_cast = yield from self.CastSkillIDAndRestoreTarget(
                    skill_id=cleanup_skill_id,
                    target_agent_id=int(single_cleanup_target),
                    log=False,
                    aftercast_delay=250,
                )
                if did_cast:
                    self._note_non_keystone_signet_cast()
                    try:
                        from Py4GWCoreLib.Builds.Skills import CombatDebug
                        CombatDebug.log_event(
                            "KEYSTONE_SINGLE_TARGET_CLEANUP",
                            target_id=int(single_cleanup_target),
                            skill_id=int(cleanup_skill_id),
                        )
                    except Exception:
                        pass
                    return True

        if (
            can_spend_non_keystone_signets
            and self.IsSkillEquipped(Tryptophan_Signet_ID)
            and snapshot.enemy_in_spellcast
        ):
            target_agent_id = self._get_tryptophan_signet_target()
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Tryptophan_Signet_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                return True

        # Signet of Sorrow is strongest when the target is near a corpse/dead pet,
        # because it can instantly recharge.  Prefer corpse-boosted packet targets
        # before Corruption; if no corpse target exists, spend Corruption first
        # for reliable opening AoE, then use Sorrow as fallback filler later.
        if (
            can_spend_non_keystone_signets
            and snapshot.enemy_in_spellcast
            and self.IsSkillEquipped(Signet_of_Sorrow_ID)
        ):
            target_agent_id = self._get_sorrow_signet_target(require_corpse=True, claim_target=True)
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Signet_of_Sorrow_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                try:
                    from Py4GWCoreLib.Builds.Skills import Telemetry
                    Telemetry.count("keystone.sorrow_cast")
                except Exception:
                    pass
                return True

        # Optional tuning: aggressive Sorrow mode spends Sorrow as general
        # Keystone filler before Corruption even when no corpse is confirmed.
        # Default remains normal to preserve reliable Corruption opening AoE.
        try:
            from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
            _sorrow_aggressive = str(SimplePowerSettings.get_value("keystone_sorrow_priority", "normal")).lower() == "aggressive"
        except Exception:
            _sorrow_aggressive = False
        if (
            _sorrow_aggressive
            and can_spend_non_keystone_signets
            and snapshot.enemy_in_spellcast
            and self.IsSkillEquipped(Signet_of_Sorrow_ID)
        ):
            target_agent_id = self._get_sorrow_signet_target(require_corpse=False, claim_target=True)
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Signet_of_Sorrow_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                try:
                    from Py4GWCoreLib.Builds.Skills import Telemetry
                    Telemetry.count("keystone.sorrow_cast")
                    Telemetry.count("keystone.sorrow_aggressive_cast")
                except Exception:
                    pass
                return True

        if (
            can_spend_non_keystone_signets
            and snapshot.enemy_in_spellcast
            and self.IsSkillEquipped(Signet_of_Corruption_Kurzick_ID)
        ):
            target_agent_id = self._get_packet_signet_target(Signet_of_Corruption_Kurzick_ID, claim_target=True)
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Signet_of_Corruption_Kurzick_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                try:
                    from Py4GWCoreLib.Builds.Skills import Telemetry
                    Telemetry.count("keystone.corruption_cast")
                except Exception:
                    pass
                return True

        if (
            can_spend_non_keystone_signets
            and snapshot.enemy_in_spellcast
            and self.IsSkillEquipped(Signet_of_Corruption_Luxon_ID)
        ):
            target_agent_id = self._get_packet_signet_target(Signet_of_Corruption_Luxon_ID, claim_target=True)
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Signet_of_Corruption_Luxon_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                try:
                    from Py4GWCoreLib.Builds.Skills import Telemetry
                    Telemetry.count("keystone.corruption_cast")
                except Exception:
                    pass
                return True

        if (
            can_spend_non_keystone_signets
            and snapshot.enemy_in_spellcast
            and self.IsSkillEquipped(Signet_of_Weariness_ID)
        ):
            target_agent_id = self._get_packet_signet_target(Signet_of_Weariness_ID, claim_target=True) or self._get_offensive_signet_target()
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Signet_of_Weariness_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                return True

        if (
            can_spend_non_keystone_signets
            and snapshot.enemy_in_spellcast
            and self.IsSkillEquipped(Signet_of_Sorrow_ID)
        ):
            target_agent_id = self._get_sorrow_signet_target(require_corpse=False, claim_target=True)
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Signet_of_Sorrow_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                try:
                    from Py4GWCoreLib.Builds.Skills import Telemetry
                    Telemetry.count("keystone.sorrow_cast")
                except Exception:
                    pass
                return True

        if player_energy_pct >= 0.50 and (yield from self.skills.Monk.SmitingPrayers.Smite_Hex(min_priority=HexRemovalPriority.MEDIUM)):
            return True

        if (
            can_spend_non_keystone_signets
            and snapshot.enemy_in_spellcast
        ):
            target_agent_id = self._get_offensive_signet_target()
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Unnatural_Signet_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                return True

        if (
            can_spend_non_keystone_signets
            and self.IsSkillEquipped(Signet_of_Clumsiness_ID)
            and snapshot.attacking_enemy_in_spellcast
        ):
            target_agent_id = self._get_attacking_power_cluster_target()
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Signet_of_Clumsiness_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                return True

        if (
            can_spend_non_keystone_signets
            and snapshot.enemy_in_spellcast
            and self.IsSkillEquipped(Castigation_Signet_ID)
            and self.CanCastSkillID(Castigation_Signet_ID)
        ):
            target_agent_id = self._get_monk_damage_signet_target(Castigation_Signet_ID, claim_target=True)
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Castigation_Signet_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "KEYSTONE_MONK_SIGNET_CAST",
                        skill_id=int(Castigation_Signet_ID),
                        target_id=int(target_agent_id),
                        target_attacking=bool(Agent.IsAttacking(int(target_agent_id))),
                        fallback_non_attacker=not bool(Agent.IsAttacking(int(target_agent_id))),
                    )
                except Exception:
                    pass
                return True

        if (
            can_spend_non_keystone_signets
            and snapshot.enemy_in_spellcast
            and self.IsSkillEquipped(Bane_Signet_ID)
            and self.CanCastSkillID(Bane_Signet_ID)
        ):
            target_agent_id = self._get_monk_damage_signet_target(Bane_Signet_ID, claim_target=True)
            if target_agent_id and (yield from self.CastSkillIDAndRestoreTarget(skill_id=Bane_Signet_ID, target_agent_id=target_agent_id, log=False, aftercast_delay=250)):
                self._note_non_keystone_signet_cast()
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "KEYSTONE_MONK_SIGNET_CAST",
                        skill_id=int(Bane_Signet_ID),
                        target_id=int(target_agent_id),
                        target_attacking=bool(Agent.IsAttacking(int(target_agent_id))),
                        fallback_non_attacker=not bool(Agent.IsAttacking(int(target_agent_id))),
                    )
                except Exception:
                    pass
                return True

        return False
