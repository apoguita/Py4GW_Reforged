from __future__ import annotations

from dataclasses import dataclass

from Py4GWCoreLib import Range
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill

# Central Simple-Power dangerous-cast interrupt coordination.
# Design goal: scan often enough to catch real threats, but keep the hot path
# cheap. The scan uses only stable Agent casting data and a fixed skill allow-list.
DANGER_INTERRUPT_SCAN_THROTTLE_MS = 75
DANGER_INTERRUPT_MIN_CLAIM_MS = 900
DANGER_INTERRUPT_MAX_CLAIM_MS = 1750
DANGER_INTERRUPT_DEFAULT_CLAIM_MS = 1100
DANGER_INTERRUPT_DYNAMIC_MIN_CLAIM_MS = 500
DANGER_INTERRUPT_CAST_END_GRACE_MS = 240

# Local per-process movement ownership for a Mesmer that is making a short,
# bounded approach to interrupt a lethal AoE caster.  The follower runtime
# reads this state so normal formation movement cannot overwrite the approach.
# Expiry is intentionally short and must be refreshed every approach tick.
_INTERRUPT_APPROACH_ACTIVE_UNTIL_TICK: int = 0
_INTERRUPT_APPROACH_TARGET_ID: int = 0
_INTERRUPT_APPROACH_ENEMY_SKILL_ID: int = 0


# Ordered by practical priority: resurrection/recovery first, then prot, then
# large AoE/shutdown/pressure. This prevents a Meteor Shower from stealing the
# only ready interrupt while a resurrection or Protective Spirit is going off.
DANGER_INTERRUPT_SKILL_NAMES: tuple[str, ...] = (
    # Priority 0: Resurrection / hard recovery. These are the highest value
    # interrupts because one missed cast can reset the whole spike.
    "Death_Pact_Signet", "Flesh_of_My_Flesh", "Renew_Life", "Restore_Life",
    "Resurrection_Chant", "Resurrection_Signet", "Rebirth", "Light_of_Dwayna",
    "Unyielding_Aura", "Vengeance", "Signet_of_Return", "Sunspear_Rebirth_Signet",

    # Priority 1: Hard protection / defensive swing skills that can make the
    # focused packet survive too long or protect dangerous NPC balls.
    "Aegis", "Protective_Spirit", "Spirit_Bond", "Shield_of_Absorption",
    "Life_Sheath", "Mark_of_Protection", "Shielding_Hands", "Guardian",
    "Protective_Bond", "Life_Barrier", "Life_Bond", "Reversal_of_Fortune",
    "Shield_Guardian", "Aura_of_Stability", "Weapon_of_Warding",
    "Weapon_of_Shadow", "Xinraes_Weapon", "Xinrae's_Weapon",
    "Protective_Was_Kaolai", "Shelter", "Union", "Displacement", "Life",
    "Preservation", "Recuperation", "Recovery", "Weapon_of_Remedy",

    # Priority 2: Big heals / party recovery / condition-hex reset. These are
    # less wipe-dangerous than Meteor Shower, but they waste the team's spike.
    "Word_of_Healing", "Patient_Spirit", "Dwaynas_Kiss", "Dwayna's_Kiss",
    "Orison_of_Healing", "Heal_Other", "Healing_Touch", "Healing_Seed",
    "Seed_of_Life", "Gift_of_Health", "Jameis_Gaze", "Jamei's_Gaze",
    "Ethereal_Light", "Healing_Ribbon", "Heal_Party", "Infuse_Health",
    "Heavens_Delight", "Heaven's_Delight", "Divine_Healing", "Heal_Area",
    "Healing_Burst", "Healing_Light", "Light_of_Deliverance",
    "Karei's_Healing_Circle", "Kareis_Healing_Circle", "Restore_Condition",
    "Mend_Condition", "Mend_Ailment", "Convert_Hexes", "Deny_Hexes",
    "Purge_Signet", "Spirit_Light", "Mend_Body_and_Soul", "Spirit_Transfer",
    "Soothing_Memories", "Wielders_Boon", "Wielder's_Boon", "Vengeful_Weapon",
    "Resilient_Weapon", "Generous_Was_Tsungrai", "Mend_Soul", "Life",

    # Priority 3: Elementalist / armor-ignoring / large packet AoE, especially
    # the skills that punish a tight Simple-Power cluster.
    "Meteor_Shower", "Savannah_Heat", "Searing_Heat", "Rodgorts_Invocation",
    "Rodgort's_Invocation", "Deep_Freeze", "Maelstrom", "Earthquake",
    "Churning_Earth", "Sandstorm", "Fire_Storm", "Eruption", "Meteor",
    "Invoke_Lightning", "Chain_Lightning", "Obsidian_Flame", "Mind_Burn",
    "Mind_Freeze", "Shatterstone", "Teinais_Heat", "Teinai's_Heat",
    "Bed_of_Coals", "Mirror_of_Ice", "Thunderclap", "Shockwave", "Dragon's_Stomp",
    "Dragons_Stomp", "Unsteady_Ground", "Sliver_Armor", "Ward_Against_Harm",
    "Ward_Against_Melee", "Ward_Against_Foes", "Ward_Against_Elements",

    # Priority 4: Mesmer shutdown / punishment. These do not always wipe the
    # party instantly, but they can destroy the team's cast chain.
    "Panic", "Energy_Surge", "Mistrust", "Cry_of_Frustration", "Power_Block",
    "Psychic_Instability", "Visions_of_Regret", "Backfire", "Empathy",
    "Shame", "Diversion", "Power_Leak", "Power_Drain", "Leech_Signet",
    "Complicate", "Arcane_Conundrum", "Migraine", "Ineptitude", "Clumsiness",
    "Wandering_Eye", "Shared_Burden", "Frustration", "Hex_Eater_Vortex",

    # Priority 5: Necromancer packet pressure / melee punishment / corpse bombs.
    "Spiteful_Spirit", "Spoil_Victor", "Mark_of_Pain", "Barbs",
    "Feast_of_Corruption", "Rising_Bile", "Putrid_Explosion", "Discord",
    "Life_Siphon", "Soul_Barbs", "Insidious_Parasite", "Defile_Defenses",
    "Enfeebling_Blood", "Weaken_Armor", "Price_of_Failure", "Reckless_Haste",
    "Tainted_Flesh", "Order_of_Pain", "Order_of_the_Vampire",

    # Priority 6: Monk smite/control and hard knockdown/control from other bars.
    "Ray_of_Judgment", "Signet_of_Judgment", "Shield_of_Judgment", "Bane_Signet",
    "Symbol_of_Wrath", "Scourge_Healing", "Balthazar's_Aura", "Balthazars_Aura",
    "Stoning", "Gale", "Shock", "Yeti_Smash", "Crushing_Blow", "Wild_Blow",

    # Priority 7: Ritualist offensive spirit pressure / shutdown spirits.
    "Pain", "Bloodsong", "Shadowsong", "Dissonance", "Wanderlust", "Anguish",
    "Destruction", "Doom", "Signet_of_Spirits", "Ancestors_Rage",
    "Ancestor's_Rage", "Spirit_Rift", "Clamor_of_Souls", "Caretaker's_Charge",
    "Caretakers_Charge",

    # Priority 8: Ranger / nature ritual swing skills that can punish balling
    # or slow the spike. Edge of Extinction is included because it can snowball
    # hard in dense fights.
    "Edge_of_Extinction", "Frozen_Soil", "Greater_Conflagration",
    "Broad_Head_Arrow",
)


def _build_ordered_skill_ids(skill_names: tuple[str, ...]) -> tuple[int, ...]:
    ordered: list[int] = []
    seen: set[int] = set()
    for skill_name in skill_names:
        try:
            skill_id = int(Skill.GetID(skill_name) or 0)
        except Exception:
            skill_id = 0
        if skill_id <= 0 or skill_id in seen:
            continue
        seen.add(skill_id)
        ordered.append(skill_id)
    return tuple(ordered)


try:
    from Py4GWCoreLib.Builds.Skills import DangerousSkillPriorities as _DSP
    DANGER_INTERRUPT_SKILL_IDS = _DSP.get_registered_skill_ids(_DSP.DEFAULT_RESERVED_INTERRUPT_THRESHOLD)
    DANGER_INTERRUPT_SKILL_IDS_ORDERED = tuple(sorted(
        DANGER_INTERRUPT_SKILL_IDS,
        key=lambda sid: (-_DSP.get_base_score(int(sid), 0), int(sid)),
    ))
except Exception:
    _DSP = None
    DANGER_INTERRUPT_SKILL_IDS_ORDERED = _build_ordered_skill_ids(DANGER_INTERRUPT_SKILL_NAMES)
    DANGER_INTERRUPT_SKILL_IDS = frozenset(DANGER_INTERRUPT_SKILL_IDS_ORDERED)
DANGER_INTERRUPT_PRIORITY = {
    skill_id: index for index, skill_id in enumerate(DANGER_INTERRUPT_SKILL_IDS_ORDERED)
}

# Phase 9: practical severity tiers.  These are deliberately separate from the
# long allow-list order so a small heal cannot outrank a party-wiping AoE merely
# because its name appeared earlier in the file.
_REZ_NAMES = (
    "Death_Pact_Signet", "Flesh_of_My_Flesh", "Renew_Life",
    "Restore_Life", "Resurrection_Chant", "Resurrection_Signet",
    "Rebirth", "Light_of_Dwayna", "Unyielding_Aura", "Vengeance",
    "Signet_of_Return", "Sunspear_Rebirth_Signet",
)
_LETHAL_AOE_NAMES = (
    "Meteor_Shower", "Savannah_Heat", "Searing_Heat", "Teinais_Heat",
    "Teinai's_Heat", "Bed_of_Coals", "Ray_of_Judgment", "Fire_Storm",
    "Maelstrom", "Churning_Earth", "Sandstorm", "Eruption",
    "Deep_Freeze", "Earthquake", "Dragon's_Stomp", "Dragons_Stomp",
    "Unsteady_Ground", "Shockwave", "Invoke_Lightning", "Spirit_Rift",
)
_HARD_PROT_NAMES = (
    "Aegis", "Protective_Spirit", "Spirit_Bond", "Shield_of_Absorption",
    "Life_Sheath", "Mark_of_Protection", "Aura_of_Stability",
    "Weapon_of_Warding", "Shelter", "Union", "Displacement",
    "Protective_Was_Kaolai",
)
_MAJOR_HEAL_NAMES = (
    "Word_of_Healing", "Heal_Party", "Infuse_Health", "Healing_Burst",
    "Light_of_Deliverance", "Heavens_Delight", "Heaven's_Delight",
    "Divine_Healing", "Restore_Condition", "Mend_Body_and_Soul",
    "Spirit_Light", "Spirit_Transfer",
)
_HARD_SHUTDOWN_NAMES = (
    "Panic", "Energy_Surge", "Mistrust", "Cry_of_Frustration",
    "Power_Block", "Psychic_Instability", "Backfire", "Shame",
    "Diversion", "Migraine", "Broad_Head_Arrow", "Frozen_Soil",
    "Dissonance", "Wanderlust", "Signet_of_Judgment",
    "Shield_of_Judgment", "Gale",
)

_REZ_IDS = frozenset(_build_ordered_skill_ids(_REZ_NAMES))
_LETHAL_AOE_IDS = frozenset(_build_ordered_skill_ids(_LETHAL_AOE_NAMES))
_HARD_PROT_IDS = frozenset(_build_ordered_skill_ids(_HARD_PROT_NAMES))
_MAJOR_HEAL_IDS = frozenset(_build_ordered_skill_ids(_MAJOR_HEAL_NAMES))
_HARD_SHUTDOWN_IDS = frozenset(_build_ordered_skill_ids(_HARD_SHUTDOWN_NAMES))

@dataclass(frozen=True, slots=True)
class _InterruptProfile:
    activation_ms: int
    recharge_ms: int
    is_fast: bool
    is_slow: bool
    is_scarce: bool


def _danger_tier(skill_id: int) -> int:
    sid = int(skill_id or 0)
    try:
        if _DSP is not None:
            score = int(_DSP.get_base_score(sid, 0))
            if score >= 108:
                return 6
            if score >= 102:
                return 5
            if score >= 96:
                return 4
            if score >= 90:
                return 3
            if score >= 80:
                return 2
            return 1
    except Exception:
        pass
    if sid in _REZ_IDS:
        return 6
    if sid in _LETHAL_AOE_IDS:
        return 5
    if sid in _HARD_PROT_IDS:
        return 4
    if sid in _MAJOR_HEAL_IDS:
        return 3
    if sid in _HARD_SHUTDOWN_IDS:
        return 2
    return 1


def _interrupt_profile(interrupter_skill_id: int) -> _InterruptProfile:
    sid = int(interrupter_skill_id or 0)
    activation_ms = 750
    recharge_ms = 10000
    try:
        activation_ms = max(0, int(float(Skill.Data.GetActivation(sid) or 0.0) * 1000.0))
    except Exception:
        pass
    try:
        recharge_ms = max(0, int(float(Skill.Data.GetRecharge(sid) or 0.0) * 1000.0))
    except Exception:
        pass
    return _InterruptProfile(
        activation_ms=int(activation_ms),
        recharge_ms=int(recharge_ms),
        is_fast=bool(activation_ms <= 500),
        is_slow=bool(activation_ms >= 1000),
        is_scarce=bool(recharge_ms >= 15000),
    )

_SCAN_CACHE: dict[str, object] = {
    "tick": 0,
    "range_value": 0,
    "player_xy": None,
    "candidates": (),
}

# Cross-process whiteboard posting is not an atomic check-and-set operation.
# A deterministic micro-stagger gives one account time to publish first and
# removes the duplicate claims observed in the combat logs.
_CLAIM_ELECTION_FIRST_SEEN: dict[tuple[int, int], int] = {}
_CLAIM_ELECTION_STEP_MS = 18
_CLAIM_ELECTION_MAX_AGE_MS = 8000

# Quality-aware election delays. A real direct interrupt gets first refusal;
# Keystone proxy signets follow almost immediately; Signet of Judgment is the
# reliable but slow fallback. This prevents a slow SoJ claim from blocking a
# ready Power Drain / Cry / Signet of Disruption on another account.
_DIRECT_INTERRUPT_FIRST_IDS = frozenset(_build_ordered_skill_ids((
    "Cry_of_Frustration", "Cry_of_Pain", "Power_Drain", "Power_Spike",
    "Leech_Signet", "Power_Leak", "Complicate",
)))
_DIRECT_INTERRUPT_SECOND_IDS = frozenset(_build_ordered_skill_ids((
    "Signet_of_Disruption",
)))
_SLOW_CONTROL_INTERRUPT_IDS = frozenset(_build_ordered_skill_ids((
    "Signet_of_Judgment", "Bane_Signet", "Technobabble",
)))


def _interrupt_election_base_delay_ms(interrupter_skill_id: int) -> int:
    sid = int(interrupter_skill_id or 0)
    if sid in _DIRECT_INTERRUPT_FIRST_IDS:
        return 0
    if sid in _DIRECT_INTERRUPT_SECOND_IDS:
        return 10
    if sid in _SLOW_CONTROL_INTERRUPT_IDS:
        return 85
    try:
        # Under Keystone Signet, an ordinary foe-targeted signet can interrupt
        # another dangerous caster adjacent to its target. Give those proxy
        # signets priority over SoJ, but behind dedicated direct interrupts.
        if sid > 0 and Skill.Flags.IsSignet(sid):
            return 28
    except Exception:
        pass
    return 55


def get_game_tick() -> int:
    try:
        import PySystem
        tick = int(PySystem.get_tick_count64() or 0)
        if tick > 0:
            return tick
    except Exception:
        pass
    try:
        import Py4GW
        return int(Py4GW.Game.get_tick_count64() or 0)
    except Exception:
        return 0

def _owner_context() -> tuple[str, int]:
    try:
        from Py4GWCoreLib import GLOBAL_CACHE
        email = str(Player.GetAccountEmail() or "").strip()
        if not email:
            return "", 0
        try:
            group_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
        except Exception:
            group_id = 0
        if group_id > 0:
            return email, group_id
        try:
            group_id = int(GLOBAL_CACHE.ShMem.GetAccountGroupByEmail(email) or 0)
        except Exception:
            group_id = 0
        if group_id > 0:
            return email, group_id
        try:
            for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
                if str(getattr(account, "AccountEmail", "") or "").strip() == email:
                    return email, int(getattr(account, "IsolationGroupID", 0) or 0)
        except Exception:
            pass
        return email, 0
    except Exception:
        return "", 0


def _enemy_cast_remaining_ms(target_agent_id: int, casting_skill_id: int) -> int | None:
    """Return estimated enemy cast time remaining, or None when unavailable.

    Reforged's CastObserver is preferred through CombatSense.  The established
    polling timestamp remains the fallback inside CombatSense, so this helper
    does not create another enemy scan.
    """
    try:
        from Py4GWCoreLib.Builds.Skills import CombatSense

        activation_ms = int(CombatSense.get_cast_activation_ms_for_agent(int(target_agent_id), int(casting_skill_id), 1000))
        elapsed_ms = int(CombatSense.get_cast_seen_ms(int(target_agent_id), int(casting_skill_id)))
        if activation_ms <= 0:
            return None
        return max(0, activation_ms - max(0, elapsed_ms))
    except Exception:
        return None


def _skill_claim_duration_ms(
    interrupter_skill_id: int = 0,
    target_agent_id: int = 0,
    casting_skill_id: int = 0,
) -> int:
    """Choose a lock lifetime long enough for this attempt, but not longer.

    The old fixed 0.9-1.75 second lock could remain active after a short cast
    had already completed or been interrupted.  That briefly blocked a fresh
    recast of the same skill by the same enemy.  When cast timing is available,
    cap the lock shortly after the predicted cast end; otherwise preserve the
    previous conservative duration.
    """
    duration = DANGER_INTERRUPT_DEFAULT_CLAIM_MS
    try:
        from Py4GWCoreLib import GLOBAL_CACHE
        activation_ms = int(float(GLOBAL_CACHE.Skill.Data.GetActivation(int(interrupter_skill_id)) or 0.0) * 1000)
        aftercast_ms = int(float(GLOBAL_CACHE.Skill.Data.GetAftercast(int(interrupter_skill_id)) or 0.0) * 1000)
        duration = activation_ms + aftercast_ms + 300
    except Exception:
        pass

    duration = max(DANGER_INTERRUPT_MIN_CLAIM_MS, min(DANGER_INTERRUPT_MAX_CLAIM_MS, int(duration)))
    remaining_ms = _enemy_cast_remaining_ms(int(target_agent_id), int(casting_skill_id))
    if remaining_ms is None:
        return int(duration)

    cast_end_cap = max(
        DANGER_INTERRUPT_DYNAMIC_MIN_CLAIM_MS,
        int(remaining_ms) + DANGER_INTERRUPT_CAST_END_GRACE_MS,
    )
    dynamic_duration = max(
        DANGER_INTERRUPT_DYNAMIC_MIN_CLAIM_MS,
        min(int(duration), int(cast_end_cap)),
    )
    try:
        from Py4GWCoreLib.Builds.Skills import Telemetry
        Telemetry.count("interrupt.dynamic_claim_duration")
    except Exception:
        pass
    return int(dynamic_duration)


def get_casting_skill_id(agent_id: int) -> int:
    try:
        agent_id = int(agent_id or 0)
        if agent_id <= 0:
            return 0
        if not Agent.IsValid(agent_id) or not Agent.IsAlive(agent_id):
            return 0
        if not Agent.IsCasting(agent_id):
            return 0
        return int(Agent.GetCastingSkillID(agent_id) or 0)
    except Exception:
        return 0


def is_dangerous_cast(agent_id: int) -> bool:
    return get_casting_skill_id(agent_id) in DANGER_INTERRUPT_SKILL_IDS


def target_still_casting_skill(agent_id: int, casting_skill_id: int) -> bool:
    return int(agent_id or 0) > 0 and int(casting_skill_id or 0) > 0 and get_casting_skill_id(agent_id) == int(casting_skill_id)


def _distance_to_player(agent_id: int, player_xy=None) -> float:
    try:
        from Py4GWCoreLib.Py4GWcorelib import Utils
        if player_xy is None:
            player_xy = Player.GetXY()
        return float(Utils.Distance(player_xy, Agent.GetXY(agent_id)))
    except Exception:
        return 0.0


def danger_sort_key(agent_id: int, player_xy=None) -> tuple[int, float, int]:
    skill_id = get_casting_skill_id(agent_id)
    priority = DANGER_INTERRUPT_PRIORITY.get(skill_id, 9999)
    return (priority, _distance_to_player(agent_id, player_xy), int(agent_id))


def _scan_dangerous_casts(range_value: int = Range.Spellcast.value) -> tuple[tuple[int, int], ...]:
    """Return cached tuple of (enemy_id, casting_skill_id) in danger priority order."""
    now = get_game_tick()
    try:
        player_xy = Player.GetXY()
    except Exception:
        player_xy = None

    cached_tick = int(_SCAN_CACHE.get("tick") or 0)
    scan_throttle_ms = int(DANGER_INTERRUPT_SCAN_THROTTLE_MS)
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        scan_throttle_ms = int(SimplePowerSettings.get_value("danger_interrupt_scan_throttle_ms", scan_throttle_ms))
    except Exception:
        pass
    if (
        now > 0
        and cached_tick > 0
        and now - cached_tick < scan_throttle_ms
        and int(_SCAN_CACHE.get("range_value") or 0) == int(range_value)
    ):
        return tuple(_SCAN_CACHE.get("candidates") or ())

    candidates: list[tuple[int, int]] = []
    used_combat_sense = False

    # Prefer the shared CombatSense cache.  This avoids repeated full enemy
    # scans across builds and skips very-late short casts that are unlikely to
    # be interrupted in time.  If CombatSense successfully reports no valid
    # candidate, do not immediately rescan locally and re-add the late cast;
    # only use the local scan when CombatSense is disabled or failed.
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        if SimplePowerSettings.is_feature_enabled("combat_sense_cache", True):
            from Py4GWCoreLib.Builds.Skills import CombatSense
            used_combat_sense = True
            candidates = list(CombatSense.get_dangerous_cast_candidates(
                range_value=float(range_value),
                dangerous_skill_ids=DANGER_INTERRUPT_SKILL_IDS,
                priority_map=DANGER_INTERRUPT_PRIORITY,
            ))
    except Exception:
        candidates = []
        used_combat_sense = False

    if not candidates and not used_combat_sense:
        try:
            from Py4GWCoreLib import AgentArray
            enemies = AgentArray.GetEnemyArray()
            enemies = AgentArray.Filter.ByDistance(enemies, player_xy, int(range_value))
        except Exception:
            enemies = []

        for enemy_id in enemies or []:
            try:
                enemy_id = int(enemy_id or 0)
                if enemy_id <= 0:
                    continue
                casting_skill_id = get_casting_skill_id(enemy_id)
                if casting_skill_id in DANGER_INTERRUPT_SKILL_IDS:
                    candidates.append((enemy_id, casting_skill_id))
            except Exception:
                continue

        candidates.sort(key=lambda item: danger_sort_key(item[0], player_xy))
    result = tuple(candidates)
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug, DangerousSkillPriorities as DSP
        CombatDebug.tick()
        for debug_agent_id, debug_skill_id in result:
            CombatDebug.mark_dangerous_cast(
                int(debug_agent_id),
                int(debug_skill_id),
                score=int(DSP.get_base_score(int(debug_skill_id))),
            )
            try:
                from Py4GWCoreLib.Builds.Skills import CombatSense
                CombatDebug.log_cast_source(
                    int(debug_agent_id),
                    int(debug_skill_id),
                    CombatSense.get_cast_source(int(debug_agent_id), int(debug_skill_id)),
                    CombatSense.get_cast_start_tick(int(debug_agent_id), int(debug_skill_id)),
                )
            except Exception:
                pass
    except Exception:
        pass
    _SCAN_CACHE["tick"] = now
    _SCAN_CACHE["range_value"] = int(range_value)
    _SCAN_CACHE["player_xy"] = player_xy
    _SCAN_CACHE["candidates"] = result
    return result


def _active_account_emails(interrupter_skill_id: int = 0) -> list[str]:
    """Return live same-group contenders, preferably with this skill ready.

    The previous election ranked every connected account, including accounts
    without an interrupt. With eight clients that could add hundreds of
    milliseconds. Shared skillbar data lets us stagger only genuine contenders.
    """
    try:
        from Py4GWCoreLib import GLOBAL_CACHE
        own_email, own_group = _owner_context()
        all_live: list[str] = []
        skill_ready: list[str] = []
        wanted_sid = int(interrupter_skill_id or 0)
        for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
            email = str(getattr(account, "AccountEmail", "") or "").strip()
            if not email:
                continue
            account_group = int(getattr(account, "IsolationGroupID", 0) or 0)
            if own_group > 0 and account_group > 0 and account_group != own_group:
                continue
            agent_data = getattr(account, "AgentData", None)
            agent_id = int(getattr(agent_data, "AgentID", 0) or 0)
            if agent_id > 0:
                try:
                    if not Agent.IsValid(agent_id) or not Agent.IsAlive(agent_id):
                        continue
                except Exception:
                    pass
            all_live.append(email)
            if wanted_sid <= 0:
                continue
            try:
                skillbar = getattr(agent_data, "Skillbar", None)
                if int(getattr(skillbar, "CastingSkillID", 0) or 0) > 0:
                    continue
                for skill in getattr(skillbar, "Skills", ()) or ():
                    if int(getattr(skill, "Id", 0) or 0) != wanted_sid:
                        continue
                    if float(getattr(skill, "Recharge", 0.0) or 0.0) <= 0.0:
                        skill_ready.append(email)
                    break
            except Exception:
                pass
        preferred = sorted(set(skill_ready))
        if own_email and own_email in preferred:
            return preferred
        return sorted(set(all_live))
    except Exception:
        return []


def _claim_election_ready(
    target_agent_id: int,
    casting_skill_id: int,
    now_tick: int,
    interrupter_skill_id: int = 0,
) -> tuple[bool, int]:
    """Deterministically stagger accounts before posting one shared claim.

    The best interrupt class gets first refusal; equal skills are staggered by 18 ms.  If the first
    account lacks a feasible/ready interrupt, the next one takes over shortly
    afterwards.  This avoids the non-atomic ``IsLockBlocked`` + ``PostLock``
    race without adding a costly cross-process handshake.
    """
    key = (int(target_agent_id), int(casting_skill_id))
    for old_key, first_tick in list(_CLAIM_ELECTION_FIRST_SEEN.items()):
        if int(now_tick) - int(first_tick) > _CLAIM_ELECTION_MAX_AGE_MS:
            _CLAIM_ELECTION_FIRST_SEEN.pop(old_key, None)
    first_seen = int(_CLAIM_ELECTION_FIRST_SEEN.setdefault(key, int(now_tick)))
    email, _ = _owner_context()
    emails = _active_account_emails(int(interrupter_skill_id or 0))
    base_delay = _interrupt_election_base_delay_ms(int(interrupter_skill_id or 0))
    if not email or email not in emails or len(emails) <= 1:
        required_delay = int(base_delay)
        return int(now_tick) - first_seen >= required_delay, required_delay
    seed = ((int(target_agent_id) * 1103515245) ^ (int(casting_skill_id) * 2654435761)) & 0x7FFFFFFF
    offset = seed % len(emails)
    ordered = emails[offset:] + emails[:offset]
    rank = ordered.index(email)
    required_delay = int(base_delay) + int(rank) * _CLAIM_ELECTION_STEP_MS
    return int(now_tick) - first_seen >= required_delay, required_delay


def _matching_interrupt_locks(target_agent_id: int, casting_skill_id: int, group_id: int, now_tick: int):
    try:
        from Py4GWCoreLib import GLOBAL_CACHE
        from Py4GWCoreLib.enums_src.Whiteboard_enums import WhiteboardLockKind
        all_accounts = GLOBAL_CACHE.ShMem.GetAllAccounts()
        out = []
        for slot, intent in all_accounts.GetActiveIntents() or []:
            if int(getattr(intent, "ExpiresAtTick", 0) or 0) <= int(now_tick):
                continue
            if int(getattr(intent, "KindID", 0) or 0) != int(WhiteboardLockKind.INTERRUPT_TARGET):
                continue
            if int(getattr(intent, "SkillID", 0) or 0) != int(casting_skill_id):
                continue
            if int(getattr(intent, "TargetAgentID", 0) or 0) != int(target_agent_id):
                continue
            if int(getattr(intent, "IsolationGroupID", 0) or 0) != int(group_id):
                continue
            out.append((int(slot), intent))
        return out
    except Exception:
        return []


def _verify_interrupt_claim_owner(target_agent_id: int, casting_skill_id: int, now_tick: int) -> bool:
    email, group_id = _owner_context()
    if not email:
        return True
    locks = _matching_interrupt_locks(target_agent_id, casting_skill_id, group_id, now_tick)
    if not locks:
        return True
    winner_slot, winner = min(
        locks,
        key=lambda pair: (int(getattr(pair[1], "PostedAtTick", 0) or 0), str(getattr(pair[1], "OwnerEmail", "") or ""), int(pair[0])),
    )
    winner_email = str(getattr(winner, "OwnerEmail", "") or "")
    if winner_email == email:
        return True
    try:
        from Py4GWCoreLib import GLOBAL_CACHE
        from Py4GWCoreLib.enums_src.Whiteboard_enums import WhiteboardLockKind
        GLOBAL_CACHE.ShMem.GetAllAccounts().ClearLockByOwnerKindTarget(
            email, int(WhiteboardLockKind.INTERRUPT_TARGET), int(target_agent_id), int(group_id)
        )
    except Exception:
        pass
    return False


def _is_interrupt_claim_blocked(target_agent_id: int, casting_skill_id: int, now_tick: int | None = None) -> bool:
    if int(target_agent_id or 0) <= 0 or int(casting_skill_id or 0) <= 0:
        return True
    try:
        from Py4GWCoreLib import GLOBAL_CACHE
        from Py4GWCoreLib.enums_src.Whiteboard_enums import (
            WhiteboardClaimStrength,
            WhiteboardLockKind,
            WhiteboardLockMode,
            WhiteboardReentryPolicy,
        )

        email, group_id = _owner_context()
        if not email:
            return False
        if now_tick is None:
            now_tick = get_game_tick()
        if now_tick <= 0:
            return False
        shmem = GLOBAL_CACHE.ShMem
        if hasattr(shmem, "SweepExpiredIntents"):
            shmem.SweepExpiredIntents(now_tick)
        return bool(shmem.IsLockBlocked(
            int(WhiteboardLockKind.INTERRUPT_TARGET),
            int(casting_skill_id),
            int(target_agent_id),
            int(group_id),
            email,
            int(now_tick),
            int(WhiteboardLockMode.EXCLUSIVE),
            1,
            int(WhiteboardReentryPolicy.NON_REENTRANT),
            int(WhiteboardClaimStrength.HARD),
        ))
    except Exception:
        # Fail open: a broken whiteboard must not disable interrupts.
        return False


def post_interrupt_claim(
    target_agent_id: int,
    casting_skill_id: int,
    interrupter_skill_id: int = 0,
    *,
    claim_duration_ms: int | None = None,
) -> bool:
    """Reserve one dangerous cast. True means this build may attempt the interrupt.

    Lock key: WhiteboardLockKind.INTERRUPT_TARGET + current enemy casting skill +
    enemy agent. That means exactly one account should react to that exact cast.
    """
    if int(target_agent_id or 0) <= 0 or int(casting_skill_id or 0) <= 0:
        return False
    now = get_game_tick()
    ready, delay_ms = _claim_election_ready(
        int(target_agent_id), int(casting_skill_id), int(now), int(interrupter_skill_id or 0)
    )
    if not ready:
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "INTERRUPT_CLAIM_DEFERRED", caster_id=int(target_agent_id),
                enemy_skill_id=int(casting_skill_id), delay_ms=int(delay_ms),
            )
        except Exception:
            pass
        return False
    if _is_interrupt_claim_blocked(int(target_agent_id), int(casting_skill_id), now):
        return False
    try:
        from Py4GWCoreLib import GLOBAL_CACHE
        from Py4GWCoreLib.enums_src.Whiteboard_enums import (
            WhiteboardClaimStrength,
            WhiteboardLockKind,
            WhiteboardLockMode,
            WhiteboardReentryPolicy,
        )

        email, group_id = _owner_context()
        if not email or now <= 0:
            return True
        if claim_duration_ms is None:
            duration_ms = _skill_claim_duration_ms(
                int(interrupter_skill_id or 0),
                int(target_agent_id),
                int(casting_skill_id),
            )
        else:
            # A bounded approach may need longer than the normal activation-only
            # lock.  Cap it at five seconds and never extend past an obviously
            # stale cast window.
            duration_ms = max(500, min(5000, int(claim_duration_ms)))
        expires_at_tick = now + int(duration_ms)
        shmem = GLOBAL_CACHE.ShMem
        if hasattr(shmem, "PostLock"):
            slot = shmem.PostLock(
                email,
                int(WhiteboardLockKind.INTERRUPT_TARGET),
                int(casting_skill_id),
                int(target_agent_id),
                int(expires_at_tick),
                int(group_id),
                int(WhiteboardLockMode.EXCLUSIVE),
                1,
                int(WhiteboardReentryPolicy.NON_REENTRANT),
                int(WhiteboardClaimStrength.HARD),
            )
            if int(slot) == -1:
                return False
            if not _verify_interrupt_claim_owner(int(target_agent_id), int(casting_skill_id), int(now)):
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "INTERRUPT_CLAIM_LOST", caster_id=int(target_agent_id),
                        enemy_skill_id=int(casting_skill_id), owner=email,
                    )
                except Exception:
                    pass
                return False
            return True
        if hasattr(shmem, "PostIntent"):
            return shmem.PostIntent(
                email,
                int(casting_skill_id),
                int(target_agent_id),
                int(expires_at_tick),
                int(group_id),
            ) != -1
    except Exception:
        return True
    return True


def release_interrupt_claim(
    target_agent_id: int,
    casting_skill_id: int = 0,
    *,
    reason: str = "not_fired",
) -> bool:
    """Immediately release this account's claim when no cast command was sent.

    A failed CanCast/validator/target check must not block the other accounts for
    the remainder of the lock lifetime. The shared-memory clear operation is
    owner-scoped, so another account's valid claim is never removed.
    """
    if int(target_agent_id or 0) <= 0:
        return False
    try:
        from Py4GWCoreLib import GLOBAL_CACHE
        from Py4GWCoreLib.enums_src.Whiteboard_enums import WhiteboardLockKind

        email, group_id = _owner_context()
        if not email:
            return True
        all_accounts = GLOBAL_CACHE.ShMem.GetAllAccounts()
        cleared = all_accounts.ClearLockByOwnerKindTarget(
            email,
            int(WhiteboardLockKind.INTERRUPT_TARGET),
            int(target_agent_id),
            int(group_id),
        )
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "INTERRUPT_CLAIM_RELEASED",
                caster_id=int(target_agent_id),
                enemy_skill_id=int(casting_skill_id or 0),
                reason=str(reason or "not_fired"),
            )
        except Exception:
            pass
        return bool(cleared is None or cleared)
    except Exception:
        # Fail open. Expiry remains the final safety net.
        return False


def has_dangerous_cast_in_range(range_value: int = Range.Spellcast.value) -> bool:
    """True while any registered dangerous enemy cast is live in range."""
    try:
        return bool(_scan_dangerous_casts(int(range_value)))
    except Exception:
        return False



def get_dangerous_casts_in_range(range_value: int = Range.Spellcast.value) -> tuple[tuple[int, int], ...]:
    """Public read-only view used by bounded interrupt-approach logic."""
    try:
        return tuple(_scan_dangerous_casts(int(range_value)))
    except Exception:
        return ()


def get_enemy_cast_remaining_ms(target_agent_id: int, casting_skill_id: int) -> int | None:
    """Public wrapper around the shared native-event cast timer."""
    return _enemy_cast_remaining_ms(int(target_agent_id), int(casting_skill_id))


def is_lethal_aoe_skill(skill_id: int) -> bool:
    """True only for the party-threatening AoE set used by chase interrupts."""
    return int(skill_id or 0) in _LETHAL_AOE_IDS


def is_interrupt_claim_blocked(target_agent_id: int, casting_skill_id: int) -> bool:
    """Public best-effort shared-claim check; failures remain fail-open."""
    return _is_interrupt_claim_blocked(int(target_agent_id), int(casting_skill_id))


def interrupt_is_feasible(target_agent_id: int, interrupter_skill_id: int) -> bool:
    """Public exact in-range timing check used at the end of an approach."""
    return _reforged_interrupt_is_feasible(int(target_agent_id), int(interrupter_skill_id))


def mark_interrupt_approach_movement_active(
    target_agent_id: int,
    casting_skill_id: int,
    *,
    hold_ms: int = 450,
) -> None:
    """Refresh local movement ownership while a Mesmer closes interrupt range."""
    global _INTERRUPT_APPROACH_ACTIVE_UNTIL_TICK
    global _INTERRUPT_APPROACH_TARGET_ID
    global _INTERRUPT_APPROACH_ENEMY_SKILL_ID
    now = get_game_tick()
    if now <= 0:
        return
    _INTERRUPT_APPROACH_ACTIVE_UNTIL_TICK = int(now) + max(100, int(hold_ms))
    _INTERRUPT_APPROACH_TARGET_ID = int(target_agent_id or 0)
    _INTERRUPT_APPROACH_ENEMY_SKILL_ID = int(casting_skill_id or 0)


def clear_interrupt_approach_movement() -> None:
    global _INTERRUPT_APPROACH_ACTIVE_UNTIL_TICK
    global _INTERRUPT_APPROACH_TARGET_ID
    global _INTERRUPT_APPROACH_ENEMY_SKILL_ID
    _INTERRUPT_APPROACH_ACTIVE_UNTIL_TICK = 0
    _INTERRUPT_APPROACH_TARGET_ID = 0
    _INTERRUPT_APPROACH_ENEMY_SKILL_ID = 0


def is_interrupt_approach_movement_active() -> bool:
    """True only while the current process has a freshly refreshed approach."""
    now = get_game_tick()
    if now <= 0 or int(_INTERRUPT_APPROACH_ACTIVE_UNTIL_TICK) <= int(now):
        clear_interrupt_approach_movement()
        return False
    return int(_INTERRUPT_APPROACH_TARGET_ID) > 0 and int(_INTERRUPT_APPROACH_ENEMY_SKILL_ID) > 0


def _target_is_knocked_down(target_agent_id: int) -> bool:
    """Return True when the enemy is already disabled by a knockdown.

    Simple-Power creates frequent knockdowns through Signet of Judgment and
    Keystone chains.  During the short client-state transition, an enemy can
    still appear to be casting even though the cast has already been cancelled.
    Suppressing a new interrupt claim in that window avoids wasting a dedicated
    interrupt on a cast the team has already stopped.
    """
    try:
        from Py4GWCoreLib import Routines
        return bool(Routines.Checks.Agents.IsKnockedDown(int(target_agent_id)))
    except Exception:
        return False


def _reforged_interrupt_is_feasible(target_agent_id: int, interrupter_skill_id: int) -> bool:
    """Use Reforged's native interrupt timing model when available.

    The helper accounts for observed enemy cast progress, our activation time,
    Fast Casting, range, ping and a reaction margin.  It intentionally fails
    open so the established CombatSense path remains usable if Reforged changes
    an internal API or the timing observer has not seen this cast yet.
    """
    if int(target_agent_id or 0) <= 0 or int(interrupter_skill_id or 0) <= 0:
        return True
    try:
        from Py4GWCoreLib.HeroAI import interrupt as reforged_interrupt

        try:
            fast_casting_level = int(reforged_interrupt._get_player_fast_casting_level() or 0)
        except Exception:
            fast_casting_level = 0

        try:
            ping_ms = int(reforged_interrupt._PING_HANDLER.GetCurrentPing() or 0)
        except Exception:
            ping_ms = 100
        if ping_ms <= 0:
            ping_ms = 100

        return bool(reforged_interrupt.is_interrupt_feasible(
            int(target_agent_id),
            int(interrupter_skill_id),
            int(fast_casting_level),
            int(ping_ms),
            reaction_margin_ms=90,
            debug=False,
        ))
    except Exception:
        return True

def _candidate_interrupt_score(
    target_agent_id: int,
    casting_skill_id: int,
    interrupter_skill_id: int,
) -> float:
    """Score one cast for the specific ready interrupt skill.

    Phase 9 contributes danger severity and practical impact.  Phase 10 adds
    role fit: fast interrupts are reserved for urgent short windows, slower
    control skills prefer longer casts, and long-recharge interrupts are not
    spent on low-tier pressure unless nothing better exists.
    """
    sid = int(casting_skill_id or 0)
    tier = _danger_tier(sid)
    contextual_priority = 0
    try:
        from Py4GWCoreLib.Builds.Skills import DangerousSkillPriorities as DSP
        from Py4GWCoreLib.Builds.Skills import ThreatMemory
        enemy_for_context = None
        try:
            from Py4GWCoreLib.Builds.Skills import CombatSense
            enemy_for_context = CombatSense.get_enemy_sense(int(target_agent_id), range_value=Range.Spellcast.value)
        except Exception:
            pass
        contextual_priority = DSP.contextual_score(
            sid,
            adjacent_enemies=int(enemy_for_context.adjacent_count) if enemy_for_context is not None else 1,
            enemy_low_health=bool(enemy_for_context is not None and float(enemy_for_context.health) <= 0.35),
            threat_memory_bonus=ThreatMemory.get_interrupt_bonus(int(target_agent_id)),
        )
    except Exception:
        contextual_priority = tier * 16
    score = float(contextual_priority * 1000)

    remaining_ms = _enemy_cast_remaining_ms(int(target_agent_id), sid)
    profile = _interrupt_profile(int(interrupter_skill_id or 0))
    try:
        from Py4GWCoreLib.Builds.Skills import CombatSense
        enemy = CombatSense.get_enemy_sense(int(target_agent_id), range_value=Range.Spellcast.value)
    except Exception:
        enemy = None

    if enemy is not None:
        score += float(min(6, max(0, int(enemy.adjacent_count) - 1)) * 220)
        score += float(max(0, int(enemy.threat_score)) * 3)
        score -= min(1800.0, float(enemy.distance_to_player) * 0.65)

    if remaining_ms is not None:
        remaining = max(0, int(remaining_ms))
        landing_budget = int(profile.activation_ms) + 180
        slack = remaining - landing_budget
        # Urgent but feasible casts deserve immediate attention.
        if 0 <= slack <= 450:
            score += 1800.0 if profile.is_fast else 600.0
        elif slack < 0:
            score -= 10000.0
        elif profile.is_slow and remaining >= 1200:
            score += 700.0
        elif profile.is_fast and remaining <= 900:
            score += 500.0

    # Preserve scarce/long-recharge interrupts for important casts.  This is a
    # score penalty, not a hard block, so the team still reacts if it is the only
    # available answer.
    if profile.is_scarce and tier <= 2:
        score -= 4200.0
    elif profile.is_scarce and tier == 3:
        score -= 1200.0

    # Stable tie-breaker, avoiding oscillation between equal candidates.
    score -= float(int(target_agent_id) % 997) * 0.001
    return float(score)


def _rank_candidates_for_interrupter(
    candidates: tuple[tuple[int, int], ...],
    interrupter_skill_id: int,
) -> tuple[tuple[int, int], ...]:
    ranked = list(candidates)
    ranked.sort(
        key=lambda item: _candidate_interrupt_score(
            int(item[0]), int(item[1]), int(interrupter_skill_id or 0)
        ),
        reverse=True,
    )
    return tuple(ranked)


def claim_best_dangerous_cast(
    *,
    range_value: int = Range.Spellcast.value,
    interrupter_skill_id: int = 0,
    validator=None,
) -> tuple[int, int]:
    """Pick and reserve the best dangerous cast for this one interrupt attempt."""
    candidates = _rank_candidates_for_interrupter(
        _scan_dangerous_casts(int(range_value)), int(interrupter_skill_id or 0)
    )
    for target_agent_id, casting_skill_id in candidates:
        try:
            try:
                from Py4GWCoreLib.Builds.Skills import DangerousSkillPriorities as DSP
                from Py4GWCoreLib.Builds.Skills import SimplePowerSettings, ThreatMemory, CombatSense
                enemy_ctx = CombatSense.get_enemy_sense(int(target_agent_id), range_value=Range.Spellcast.value)
                final_priority = DSP.contextual_score(
                    int(casting_skill_id),
                    adjacent_enemies=int(enemy_ctx.adjacent_count) if enemy_ctx is not None else 1,
                    enemy_low_health=bool(enemy_ctx is not None and float(enemy_ctx.health) <= 0.35),
                    threat_memory_bonus=ThreatMemory.get_interrupt_bonus(int(target_agent_id)),
                )
                min_score = int(SimplePowerSettings.get_value("danger_interrupt_min_score", 80))
                if int(final_priority) < int(min_score):
                    continue
            except Exception:
                pass
            # Do not reserve an interrupt for a cast already cancelled by the
            # team's SoJ/Keystone knockdown chain.  Reforged can briefly retain
            # the old casting state for one frame after the knockdown lands.
            if _target_is_knocked_down(int(target_agent_id)):
                try:
                    from Py4GWCoreLib.Builds.Skills import Telemetry
                    Telemetry.count("interrupt.knockdown_suppressed")
                except Exception:
                    pass
                continue
            if _is_interrupt_claim_blocked(target_agent_id, casting_skill_id):
                try:
                    from Py4GWCoreLib.Builds.Skills import Telemetry
                    Telemetry.count("interrupt.claim_blocked")
                except Exception:
                    pass
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "INTERRUPT_SKIPPED", reason="already_claimed",
                        caster_id=int(target_agent_id), enemy_skill_id=int(casting_skill_id),
                        our_skill_id=int(interrupter_skill_id or 0),
                    )
                except Exception:
                    pass
                continue
            if validator is not None and not bool(validator(target_agent_id, casting_skill_id)):
                continue
            if int(interrupter_skill_id or 0) > 0 and not _reforged_interrupt_is_feasible(
                int(target_agent_id), int(interrupter_skill_id)
            ):
                try:
                    from Py4GWCoreLib.Builds.Skills import Telemetry
                    Telemetry.count("interrupt.infeasible_skipped")
                except Exception:
                    pass
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "INTERRUPT_SKIPPED", reason="not_feasible",
                        caster_id=int(target_agent_id), enemy_skill_id=int(casting_skill_id),
                        our_skill_id=int(interrupter_skill_id or 0),
                    )
                except Exception:
                    pass
                continue
            # Re-read immediately before posting. If the enemy changed casts, skip.
            if get_casting_skill_id(target_agent_id) != int(casting_skill_id):
                continue
            if not post_interrupt_claim(target_agent_id, casting_skill_id, interrupter_skill_id):
                continue
            try:
                from Py4GWCoreLib.Builds.Skills import Telemetry
                Telemetry.count("interrupt.claim_posted")
                Telemetry.count(f"interrupt.tier_{_danger_tier(int(casting_skill_id))}")
                Telemetry.event("interrupt_claim", str(int(casting_skill_id)))
            except Exception:
                pass
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.mark_interrupt_claim(
                    int(target_agent_id), int(casting_skill_id), int(interrupter_skill_id or 0)
                )
            except Exception:
                pass
            return (int(target_agent_id), int(casting_skill_id))
        except Exception:
            continue
    try:
        from Py4GWCoreLib.Builds.Skills import Telemetry
        Telemetry.count("interrupt.no_candidate")
    except Exception:
        pass
    return (0, 0)
