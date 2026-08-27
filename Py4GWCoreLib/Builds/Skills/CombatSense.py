"""Shared lightweight combat-sense cache for Simple-Power HeroAI builds.

Purpose:
- Scan enemies once per short tick instead of letting every build repeat the
  same expensive target/cast/cluster analysis.
- Provide cheap helper decisions for dangerous casts, low-HP execution targets,
  threat-aware cluster anchors, and light movement prediction.

Compatibility:
- Uses only public/stable Py4GW Python-layer calls that exist in the uploaded
  Py4GW-main baseline: Agent, AgentArray, Player, Range, Skill, Profession.
- Fails open: if one API value is missing at runtime, callers fall back to their
  previous local logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from Py4GWCoreLib import AgentArray, Profession, Range, Routines, GLOBAL_CACHE
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill

SENSE_SCAN_THROTTLE_MS = 110
CAST_SCAN_THROTTLE_MS = 45
MOVEMENT_HISTORY_MAX_AGE_MS = 900
PREDICTION_HORIZON_MS = 550

# Lightweight danger tiers.  The exact interrupt allow-list remains in
# DangerInterruptClaim.py; this module keeps a smaller broad threat model for
# scoring and target selection.
_REZ_SKILL_NAMES = (
    "Death_Pact_Signet", "Flesh_of_My_Flesh", "Renew_Life",
    "Restore_Life", "Resurrection_Chant", "Resurrection_Signet", "Rebirth",
    "Light_of_Dwayna", "Unyielding_Aura", "Vengeance", "Signet_of_Return",
)
_PROT_HEAL_SKILL_NAMES = (
    "Aegis", "Protective_Spirit", "Spirit_Bond", "Shield_of_Absorption",
    "Life_Sheath", "Mark_of_Protection", "Guardian", "Weapon_of_Warding",
    "Shelter", "Union", "Displacement", "Life", "Preservation", "Recuperation",
    "Word_of_Healing", "Heal_Party", "Healing_Burst", "Infuse_Health",
    "Heaven's_Delight", "Heavens_Delight", "Divine_Healing", "Restore_Condition",
    "Mend_Body_and_Soul", "Spirit_Light", "Protective_Was_Kaolai",
)
_AOE_SHUTDOWN_SKILL_NAMES = (
    "Meteor_Shower", "Savannah_Heat", "Searing_Heat", "Teinai's_Heat",
    "Teinais_Heat", "Bed_of_Coals", "Ray_of_Judgment", "Fire_Storm",
    "Maelstrom", "Churning_Earth", "Sandstorm", "Eruption", "Deep_Freeze",
    "Earthquake", "Dragon's_Stomp", "Dragons_Stomp", "Unsteady_Ground",
    "Panic", "Energy_Surge", "Cry_of_Frustration", "Mistrust", "Power_Block",
    "Psychic_Instability", "Backfire", "Shame", "Diversion", "Spiteful_Spirit",
    "Mark_of_Pain", "Barbs", "Spoil_Victor", "Putrid_Explosion",
)


def _skill_ids(names: Iterable[str]) -> frozenset[int]:
    ids: set[int] = set()
    for name in names:
        try:
            sid = int(Skill.GetID(name) or 0)
        except Exception:
            sid = 0
        if sid > 0:
            ids.add(sid)
    return frozenset(ids)

REZ_SKILL_IDS = _skill_ids(_REZ_SKILL_NAMES)
PROT_HEAL_SKILL_IDS = _skill_ids(_PROT_HEAL_SKILL_NAMES)
AOE_SHUTDOWN_SKILL_IDS = _skill_ids(_AOE_SHUTDOWN_SKILL_NAMES)

@dataclass(frozen=True, slots=True)
class EnemySense:
    agent_id: int
    xy: tuple[float, float]
    predicted_xy: tuple[float, float]
    distance_to_player: float
    health: float
    adjacent_count: int
    predicted_adjacent_count: int
    is_casting: bool
    casting_skill_id: int
    is_attacking: bool
    is_moving: bool
    primary_profession: int
    secondary_profession: int
    threat_score: int
    kill_score: int

_LAST_SCAN_TICK: int = 0
_LAST_RANGE: float = 0.0
_LAST_PLAYER_XY: tuple[float, float] | None = None
_LAST_ENEMIES: tuple[EnemySense, ...] = ()
_HISTORY: dict[int, tuple[int, tuple[float, float]]] = {}
_CAST_FIRST_SEEN: dict[tuple[int, int], int] = {}
_LAST_CAST_SCAN_TICK: int = 0
_LAST_CAST_RANGE: float = 0.0
_LAST_CASTS: tuple[tuple[int, int], ...] = ()
_CAST_SOURCE: dict[tuple[int, int], str] = {}
_CAST_START_TICK: dict[tuple[int, int], int] = {}

# Static enemy metadata caches. Profession data does not change during an
# agent's lifetime, so asking the game API for it every 90 ms is wasted work.
# Entries are removed as soon as the agent leaves the live enemy set, which also
# protects against recycled agent IDs on later spawns/maps.
_PROFESSION_CACHE: dict[int, tuple[int, int]] = {}
_PROFESSION_ROLE_IDS: tuple[int, int, int, int, int] | None = None

# Brief lock used only for isolated stragglers.  It prevents the team from
# bouncing between several single enemies when tiny health/threat changes alter
# their sort order.  Cluster targeting and low-HP execution still override this
# path before pick_single_target_anchor() is called.
_SINGLE_TARGET_LOCK_ID: int = 0
_SINGLE_TARGET_LOCK_UNTIL_MS: int = 0
SINGLE_TARGET_LOCK_MS = 1400
_CLEANUP_LOG_STATE: dict[int, tuple[str, int, int]] = {}
CLEANUP_LOG_MIN_INTERVAL_MS = 2500

# Global execution lock. Once the team selects an enemy below the execution
# threshold, every account/controller stays on that target until it dies, is
# healed above the threshold, or leaves usable range. This prevents bouncing
# between several isolated low-HP stragglers.
_EXECUTION_LOCK_ID: int = 0

# Short pressure-anchor lock. This keeps all offensive builds committed to the
# same useful packet for a brief burst window instead of changing anchor every
# tactical refresh when two clusters have nearly identical scores.
_PRESSURE_ANCHOR_LOCK_ID: int = 0
_PRESSURE_ANCHOR_LOCK_UNTIL_MS: int = 0
_PRESSURE_ANCHOR_LOCK_SCORE: int = 0
PRESSURE_ANCHOR_LOCK_MS = 950
PRESSURE_ANCHOR_BREAK_MARGIN = 420

# Healer-spike memory.  Cluster damage remains the default; an isolated support
# target only overrides it when that target is actively and repeatedly
# preventing kills.  Resurrection casts are handled by the interrupt layer and
# deliberately do not trigger a full-team target switch.
HEALER_PRESSURE_WINDOW_MS = 7000
HEALER_PRESSURE_REPEAT_CASTS = 2
HEALER_PRESSURE_CURRENT_STRONG_BONUS = 2
_HEALER_PRESSURE_EVENTS: dict[int, list[int]] = {}



def now_ms() -> int:
    try:
        import PySystem
        return int(PySystem.get_tick_count64() or 0)
    except Exception:
        try:
            import Py4GW
            return int(Py4GW.Game.get_tick_count64() or 0)
        except Exception:
            try:
                import time
                return int(time.monotonic() * 1000.0)
            except Exception:
                return 0


def _xy(agent_id: int) -> tuple[float, float] | None:
    try:
        xy = Agent.GetXY(int(agent_id))
        if not xy:
            return None
        return (float(xy[0]), float(xy[1]))
    except Exception:
        return None


def shared_team_origin_xy() -> tuple[float, float] | None:
    """Use party-slot 0 shared-memory position as the common combat origin.

    Every multibox client therefore filters the same enemy universe instead of
    filtering around its own slightly different XY position. If shared memory
    is unavailable, fall back to the local player position.
    """
    try:
        account = GLOBAL_CACHE.ShMem.GetAccountDataFromPartyNumber(0)
        if account is not None:
            agent_data = getattr(account, "AgentData", None)
            pos = getattr(agent_data, "Pos", None)
            x = float(getattr(pos, "x", 0.0) or 0.0)
            y = float(getattr(pos, "y", 0.0) or 0.0)
            if abs(x) > 0.001 or abs(y) > 0.001:
                return (x, y)
    except Exception:
        pass
    return player_xy()


def player_xy() -> tuple[float, float] | None:
    try:
        xy = Player.GetXY()
        if not xy:
            return None
        return (float(xy[0]), float(xy[1]))
    except Exception:
        return None


def distance_xy(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    try:
        if not a or not b:
            return 999999.0
        dx = float(a[0]) - float(b[0])
        dy = float(a[1]) - float(b[1])
        return float((dx * dx + dy * dy) ** 0.5)
    except Exception:
        return 999999.0


def _health(agent_id: int) -> float:
    try:
        return float(Routines.Checks.Agents.GetHealth(int(agent_id)))
    except Exception:
        try:
            return float(Agent.GetHealth(int(agent_id)))
        except Exception:
            return 1.0


def _professions(agent_id: int) -> tuple[int, int]:
    aid = int(agent_id or 0)
    if aid <= 0:
        return (0, 0)
    cached = _PROFESSION_CACHE.get(aid)
    if cached is not None:
        return cached
    try:
        primary, secondary = Agent.GetProfessions(aid)
        result = (
            int(getattr(primary, "value", primary) or 0),
            int(getattr(secondary, "value", secondary) or 0),
        )
    except Exception:
        result = (0, 0)
    _PROFESSION_CACHE[aid] = result
    return result


def _profession_ids() -> tuple[int, int, int, int, int]:
    global _PROFESSION_ROLE_IDS
    if _PROFESSION_ROLE_IDS is not None:
        return _PROFESSION_ROLE_IDS
    try:
        _PROFESSION_ROLE_IDS = (
            int(getattr(Profession.Monk, "value", Profession.Monk)),
            int(getattr(Profession.Ritualist, "value", Profession.Ritualist)),
            int(getattr(Profession.Mesmer, "value", Profession.Mesmer)),
            int(getattr(Profession.Elementalist, "value", Profession.Elementalist)),
            int(getattr(Profession.Necromancer, "value", Profession.Necromancer)),
        )
    except Exception:
        _PROFESSION_ROLE_IDS = (0, 0, 0, 0, 0)
    return _PROFESSION_ROLE_IDS


def _is_alive_enemy(agent_id: int) -> bool:
    try:
        aid = int(agent_id or 0)
        return aid > 0 and Agent.IsValid(aid) and Agent.IsAlive(aid)
    except Exception:
        return False


def _current_casting_skill_id(agent_id: int) -> int:
    try:
        aid = int(agent_id or 0)
        if aid <= 0 or not Agent.IsValid(aid) or not Agent.IsAlive(aid):
            return 0
        if not Agent.IsCasting(aid):
            return 0
        return int(Agent.GetCastingSkillID(aid) or 0)
    except Exception:
        return 0


def _predict_xy(agent_id: int, current_xy: tuple[float, float], now: int) -> tuple[float, float]:
    try:
        old = _HISTORY.get(int(agent_id))
        _HISTORY[int(agent_id)] = (int(now), current_xy)
        if not old:
            return current_xy
        old_tick, old_xy = old
        dt = max(1, int(now) - int(old_tick))
        if dt > MOVEMENT_HISTORY_MAX_AGE_MS:
            return current_xy
        vx = (float(current_xy[0]) - float(old_xy[0])) / float(dt)
        vy = (float(current_xy[1]) - float(old_xy[1])) / float(dt)
        horizon = float(PREDICTION_HORIZON_MS)
        return (float(current_xy[0]) + vx * horizon, float(current_xy[1]) + vy * horizon)
    except Exception:
        return current_xy


def _count_neighbors(agent_id: int, xy_value: tuple[float, float], enemy_xy: dict[int, tuple[float, float]], radius: float) -> int:
    count = 0
    try:
        for other_id, other_xy in enemy_xy.items():
            if int(other_id) <= 0:
                continue
            if distance_xy(xy_value, other_xy) <= float(radius):
                count += 1
    except Exception:
        pass
    return int(count)


def _threat_score(agent_id: int, primary: int, secondary: int, casting_skill_id: int, is_casting: bool, adjacent_count: int) -> int:
    score = 0
    if is_casting and int(casting_skill_id or 0) > 0:
        try:
            from Py4GWCoreLib.Builds.Skills import DangerousSkillPriorities as DSP
            base = DSP.get_base_score(int(casting_skill_id), 0)
            score += int(base * 1.8)
        except Exception:
            if casting_skill_id in REZ_SKILL_IDS:
                score += 260
            elif casting_skill_id in PROT_HEAL_SKILL_IDS:
                score += 190
            elif casting_skill_id in AOE_SHUTDOWN_SKILL_IDS:
                score += 165

    monk, ritualist, mesmer, elementalist, necromancer = _profession_ids()
    profs = (int(primary), int(secondary))
    if monk and monk in profs:
        score += 90
    if ritualist and ritualist in profs:
        score += 75
    if mesmer and mesmer in profs:
        score += 55
    if elementalist and elementalist in profs:
        score += 50
    if necromancer and necromancer in profs:
        score += 40
    score += min(60, max(0, int(adjacent_count) - 1) * 15)

    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings, ThreatMemory
        if SimplePowerSettings.is_feature_enabled("adaptive_threat_memory", True):
            score += int(ThreatMemory.get_targeting_bonus(int(agent_id)))
    except Exception:
        pass
    try:
        from Py4GWCoreLib.Builds.Skills import EnemyKnowledge
        EnemyKnowledge.observe(int(agent_id), int(casting_skill_id or 0))
        score += int(EnemyKnowledge.threat_bonus(int(agent_id)))
        if int(casting_skill_id or 0) > 0:
            EnemyKnowledge.log_profile_if_changed(int(agent_id))
    except Exception:
        pass
    return int(score)


def refresh(range_value: float = Range.Spellcast.value, throttle_ms: int = SENSE_SCAN_THROTTLE_MS) -> tuple[EnemySense, ...]:
    global _LAST_SCAN_TICK, _LAST_RANGE, _LAST_PLAYER_XY, _LAST_ENEMIES

    try:
        from Py4GWCoreLib.Builds.Skills import EnemyKnowledge
        EnemyKnowledge.sync_event_outcomes()
    except Exception:
        pass

    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        if int(throttle_ms) == int(SENSE_SCAN_THROTTLE_MS):
            throttle_ms = SimplePowerSettings.get_combat_sense_throttle(int(throttle_ms))
    except Exception:
        pass

    now = now_ms()
    pxy = shared_team_origin_xy()
    if not pxy:
        return _LAST_ENEMIES
    if now > 0 and _LAST_SCAN_TICK > 0 and now - _LAST_SCAN_TICK < int(throttle_ms) and abs(float(_LAST_RANGE) - float(range_value)) < 0.001:
        return _LAST_ENEMIES

    try:
        enemy_ids = AgentArray.GetEnemyArray()
        enemy_ids = AgentArray.Filter.ByDistance(enemy_ids, pxy, float(range_value))
    except Exception:
        enemy_ids = []

    live_ids: list[int] = []
    current_xy: dict[int, tuple[float, float]] = {}
    predicted_xy: dict[int, tuple[float, float]] = {}
    for enemy_id in enemy_ids or []:
        try:
            aid = int(enemy_id or 0)
            if not _is_alive_enemy(aid):
                continue
            xyv = _xy(aid)
            if not xyv:
                continue
            live_ids.append(aid)
            current_xy[aid] = xyv
            predicted_xy[aid] = _predict_xy(aid, xyv, now)
        except Exception:
            continue

    current_live = set(live_ids)
    for aid in list(_HISTORY.keys()):
        if aid not in current_live:
            _HISTORY.pop(aid, None)
    for aid in list(_PROFESSION_CACHE.keys()):
        if aid not in current_live:
            _PROFESSION_CACHE.pop(aid, None)
    try:
        from Py4GWCoreLib.Builds.Skills import ThreatMemory
        ThreatMemory.prune(current_live)
    except Exception:
        pass
    try:
        from Py4GWCoreLib.Builds.Skills import EnemyKnowledge
        EnemyKnowledge.prune(current_live)
    except Exception:
        pass
    try:
        from Py4GWCoreLib.Builds.Skills import MistrustTracker
        MistrustTracker.tick(current_live)
    except Exception:
        pass

    enemies: list[EnemySense] = []
    seen_casts: set[tuple[int, int]] = set()
    for aid in live_ids:
        try:
            xyv = current_xy[aid]
            pxyv = predicted_xy[aid]
            casting_skill_id = _current_casting_skill_id(aid)
            is_casting = casting_skill_id > 0
            if is_casting:
                key = (aid, casting_skill_id)
                seen_casts.add(key)
                _CAST_FIRST_SEEN.setdefault(key, now)
            primary, secondary = _professions(aid)
            adjacent = _count_neighbors(aid, xyv, current_xy, Range.Adjacent.value)
            predicted_adjacent = _count_neighbors(aid, pxyv, predicted_xy, Range.Adjacent.value)
            try:
                moving = bool(Agent.IsMoving(aid))
            except Exception:
                moving = distance_xy(xyv, pxyv) > 45.0
            try:
                attacking = bool(Agent.IsAttacking(aid))
            except Exception:
                attacking = False
            health = _health(aid)
            threat = _threat_score(aid, primary, secondary, casting_skill_id, is_casting, adjacent)
            kill_score = int((1.0 - max(0.0, min(1.0, health))) * 100.0) + threat // 3 + adjacent * 8
            enemies.append(EnemySense(
                agent_id=aid,
                xy=xyv,
                predicted_xy=pxyv,
                distance_to_player=distance_xy(pxy, xyv),
                health=health,
                adjacent_count=int(adjacent),
                predicted_adjacent_count=int(predicted_adjacent),
                is_casting=is_casting,
                casting_skill_id=int(casting_skill_id),
                is_attacking=attacking,
                is_moving=moving,
                primary_profession=int(primary),
                secondary_profession=int(secondary),
                threat_score=int(threat),
                kill_score=int(kill_score),
            ))
        except Exception:
            continue

    for key in list(_CAST_FIRST_SEEN.keys()):
        if key not in seen_casts:
            _CAST_FIRST_SEEN.pop(key, None)

    _LAST_SCAN_TICK = now
    _LAST_RANGE = float(range_value)
    _LAST_PLAYER_XY = pxy
    _LAST_ENEMIES = tuple(enemies)
    try:
        from Py4GWCoreLib.Builds.Skills import Telemetry
        Telemetry.count("combatsense.scans")
        Telemetry.count("combatsense.enemies_seen", len(_LAST_ENEMIES))
    except Exception:
        pass
    return _LAST_ENEMIES


def get_cast_seen_ms(agent_id: int, skill_id: int) -> int:
    """Return elapsed cast time, preferring Reforged's frame observer.

    The local CombatSense timestamp remains the fallback, preserving behavior
    when HeroAI.interrupt is unavailable or has not observed the cast yet.
    """
    try:
        from Py4GWCoreLib.Builds.Skills import ReforgedSupport
        observed = ReforgedSupport.get_observed_cast_elapsed_ms(
            int(agent_id or 0), int(skill_id or 0)
        )
        if observed is not None:
            try:
                from Py4GWCoreLib.Builds.Skills import Telemetry
                Telemetry.count("reforged.cast_observer_hit")
            except Exception:
                pass
            return max(0, int(observed))
    except Exception:
        pass

    now = now_ms()
    first = int(_CAST_FIRST_SEEN.get((int(agent_id), int(skill_id))) or now)
    try:
        from Py4GWCoreLib.Builds.Skills import Telemetry
        Telemetry.count("reforged.cast_observer_fallback")
    except Exception:
        pass
    return max(0, int(now) - first)


def get_cast_activation_ms(skill_id: int, fallback_ms: int = 1000) -> int:
    try:
        activation_s = float(Skill.Data.GetActivation(int(skill_id)) or 0.0)
        if activation_s > 0:
            return max(250, int(activation_s * 1000))
    except Exception:
        pass
    try:
        from Py4GWCoreLib import GLOBAL_CACHE
        activation_s = float(GLOBAL_CACHE.Skill.Data.GetActivation(int(skill_id)) or 0.0)
        if activation_s > 0:
            return max(250, int(activation_s * 1000))
    except Exception:
        pass
    return int(fallback_ms)


def get_cast_activation_ms_for_agent(agent_id: int, skill_id: int, fallback_ms: int = 1000) -> int:
    """Return exact native CASTTIME for this cast, falling back to skill data."""
    try:
        from Py4GWCoreLib.Builds.Skills import ReforgedSupport
        exact_ms = int(ReforgedSupport.get_cast_duration_ms(int(agent_id), int(skill_id)) or 0)
        if exact_ms > 0:
            return max(1, exact_ms)
    except Exception:
        pass
    return get_cast_activation_ms(int(skill_id), int(fallback_ms))


def refresh_casts(
    *,
    range_value: float = Range.Spellcast.value,
    throttle_ms: int = CAST_SCAN_THROTTLE_MS,
) -> tuple[tuple[int, int], ...]:
    """Fast cast scan with native-event-first timing and polling fallback.

    Native Reforged activation events provide a shared start timestamp when
    available.  Live Agent state remains the final truth and fills any gaps, so
    missing or incomplete events never disable interrupts.
    """
    global _LAST_CAST_SCAN_TICK, _LAST_CAST_RANGE, _LAST_CASTS

    now = now_ms()
    if (
        now > 0
        and _LAST_CAST_SCAN_TICK > 0
        and now - _LAST_CAST_SCAN_TICK < int(throttle_ms)
        and abs(float(_LAST_CAST_RANGE) - float(range_value)) < 0.001
    ):
        return _LAST_CASTS

    try:
        from Py4GWCoreLib.Builds.Skills import EnemyKnowledge
        EnemyKnowledge.sync_event_outcomes()
    except Exception:
        pass
    enemies = refresh(range_value=range_value, throttle_ms=SENSE_SCAN_THROTTLE_MS)
    enemy_ids = {int(enemy.agent_id) for enemy in enemies}
    casts: list[tuple[int, int]] = []
    seen_casts: set[tuple[int, int]] = set()

    # Native activation events first. Validate against the live cast state to
    # avoid retaining a stale event after a stop/finish packet was lost.
    try:
        from Py4GWCoreLib.Builds.Skills import ReforgedSupport
        for aid, sid, target_id, start_tick, source in ReforgedSupport.get_active_casts():
            aid, sid = int(aid), int(sid)
            if aid not in enemy_ids or sid <= 0:
                continue
            live_sid = _current_casting_skill_id(aid)
            if live_sid != sid:
                continue
            key = (aid, sid)
            if key in seen_casts:
                continue
            seen_casts.add(key)
            casts.append(key)
            _CAST_FIRST_SEEN[key] = int(start_tick or now)
            _CAST_START_TICK[key] = int(start_tick or 0)
            _CAST_SOURCE[key] = str(source or "native_event")
    except Exception:
        pass

    # Poll every cached nearby enemy as the reliable fallback and to catch casts
    # whose native packet was not exposed.
    for enemy in enemies:
        try:
            aid = int(enemy.agent_id)
            sid = _current_casting_skill_id(aid)
            if sid <= 0:
                continue
            key = (aid, sid)
            if key in seen_casts:
                continue
            seen_casts.add(key)
            casts.append(key)
            _CAST_FIRST_SEEN.setdefault(key, now)
            _CAST_START_TICK.setdefault(key, 0)
            try:
                from Py4GWCoreLib.Builds.Skills import ReforgedSupport
                _CAST_SOURCE[key] = ReforgedSupport.get_cast_source(aid, sid)
            except Exception:
                _CAST_SOURCE[key] = "polling_fallback"
        except Exception:
            continue

    for key in list(_CAST_FIRST_SEEN.keys()):
        if key not in seen_casts:
            _CAST_FIRST_SEEN.pop(key, None)
            _CAST_SOURCE.pop(key, None)
            _CAST_START_TICK.pop(key, None)

    _LAST_CAST_SCAN_TICK = now
    _LAST_CAST_RANGE = float(range_value)
    _LAST_CASTS = tuple(casts)
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings, ThreatMemory
        if SimplePowerSettings.is_feature_enabled("adaptive_threat_memory", True):
            ThreatMemory.observe_current_casts(_LAST_CASTS)
    except Exception:
        pass
    try:
        from Py4GWCoreLib.Builds.Skills import Telemetry
        Telemetry.count("combatsense.fast_cast_scans")
    except Exception:
        pass
    return _LAST_CASTS


def get_cast_source(agent_id: int, skill_id: int) -> str:
    return str(_CAST_SOURCE.get((int(agent_id), int(skill_id)), "polling_fallback"))


def get_cast_start_tick(agent_id: int, skill_id: int) -> int:
    return int(_CAST_START_TICK.get((int(agent_id), int(skill_id)), 0) or 0)


def get_dangerous_cast_candidates(
    *,
    range_value: float = Range.Spellcast.value,
    dangerous_skill_ids: frozenset[int] | set[int] | tuple[int, ...] = (),
    priority_map: dict[int, int] | None = None,
    min_remaining_ms: int = 140,
) -> tuple[tuple[int, int], ...]:
    """Return dangerous casts using the fast cast scheduler.

    This function intentionally performs only broad ordering.  The final
    priority/role fit is calculated in DangerInterruptClaim for the specific
    interrupt skill that is currently ready.
    """
    ids = set(int(x) for x in dangerous_skill_ids or () if int(x or 0) > 0)
    prio = priority_map or {}
    tactical = {
        int(e.agent_id): e
        for e in refresh(range_value=range_value, throttle_ms=SENSE_SCAN_THROTTLE_MS)
    }
    out: list[tuple[tuple[int, float, int], tuple[int, int]]] = []
    for aid, sid in refresh_casts(range_value=range_value, throttle_ms=CAST_SCAN_THROTTLE_MS):
        try:
            if sid <= 0 or (ids and sid not in ids):
                continue
            activation_ms = get_cast_activation_ms_for_agent(aid, sid, 1000)
            elapsed = get_cast_seen_ms(aid, sid)
            remaining = int(activation_ms) - int(elapsed)
            hard_floor_ms = 90
            practical_min = int(min_remaining_ms) if activation_ms <= 1500 else hard_floor_ms
            if remaining < practical_min:
                continue
            enemy = tactical.get(int(aid))
            threat = int(enemy.threat_score) if enemy else 0
            distance = float(enemy.distance_to_player) if enemy else 999999.0
            priority = int(prio.get(sid, 9999))
            out.append(((priority, -threat, distance, int(aid)), (int(aid), int(sid))))
        except Exception:
            continue
    out.sort(key=lambda item: item[0])
    return tuple(item[1] for item in out)


def _densest_cluster_member_ids(enemies: tuple[EnemySense, ...] | list[EnemySense], minimum_enemies: int = 2) -> set[int]:
    """Return members of the currently densest adjacent packet.

    ``adjacent_count`` includes the anchor itself, therefore a value of 2 is a
    real two-enemy cluster.  Current positions dominate; prediction is only a
    tie-breaker so the team does not abandon an already formed packet.
    """
    enemy_list = list(enemies or [])
    valid = [e for e in enemy_list if int(e.adjacent_count) >= int(minimum_enemies)]
    if not valid:
        return set()
    valid.sort(key=lambda e: (-int(e.adjacent_count), -int(e.predicted_adjacent_count), -int(e.threat_score), float(e.distance_to_player), int(e.agent_id)))
    anchor = valid[0]
    members = {
        int(e.agent_id)
        for e in enemy_list
        if distance_xy(anchor.xy, e.xy) <= float(Range.Adjacent.value)
    }
    return members if len(members) >= int(minimum_enemies) else set()



_URGOZ_BARK_NAMES = frozenset({
    "krummrinde",
    "twisted bark",
})


def _safe_agent_name(agent_id: int) -> str:
    try:
        name = str(Agent.GetNameByID(int(agent_id)) or "").strip().lower()
        if name:
            return name
    except Exception:
        pass
    try:
        name = str(Agent.GetName(int(agent_id)) or "").strip().lower()
        if name:
            return name
    except Exception:
        pass
    return ""


def is_urgoz_bark(agent_id: int) -> bool:
    """True for the Urgoz environmental-effect target in DE/EN clients."""
    try:
        aid = int(agent_id or 0)
        if aid <= 0 or not Agent.IsValid(aid) or not Agent.IsAlive(aid):
            return False
        return _safe_agent_name(aid) in _URGOZ_BARK_NAMES
    except Exception:
        return False


def pick_special_priority_target(
    *,
    range_value: float = Range.Spellcast.value,
) -> int:
    """ABSOLUTE Urgoz encounter override shared by all project controllers.

    Krummrinde / Twisted Bark is priority #1 whenever it is alive/selectable and
    near the active fight. It overrides packet size, healer priority, cleanup,
    execution and all ordinary target scoring. We deliberately scan a broader
    aggro envelope than the caller's normal spellcast target range so a nearby
    Bark cannot lose merely because another packet is slightly closer.
    """
    scan_range = max(float(range_value), float(Range.Earshot.value))
    try:
        enemies = refresh(range_value=scan_range, throttle_ms=SENSE_SCAN_THROTTLE_MS)
    except Exception:
        enemies = ()
    candidates = [
        e for e in enemies
        if is_urgoz_bark(int(e.agent_id))
        and float(e.distance_to_player) <= scan_range
    ]
    if not candidates:
        return 0
    candidates.sort(key=lambda e: (float(e.distance_to_player), int(e.agent_id)))
    chosen = int(candidates[0].agent_id)
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.tick()
        CombatDebug.mark_focus(chosen, reason="urgoz_twisted_bark_hard_priority")
        CombatDebug.log_event(
            "URGOZ_BARK_PRIORITY",
            target_id=int(chosen),
            name=str(_safe_agent_name(chosen)),
        )
    except Exception:
        pass
    return chosen



def pick_locked_low_hp_finisher(
    *,
    range_value: float = Range.Spellcast.value,
    hp_threshold: float = 0.10,
) -> int:
    """Finish the current/previous focus at <=10% HP before changing packets.

    This is intentionally NOT a global low-HP search. Only an already locked
    team focus qualifies, so random damaged enemies elsewhere cannot pull the
    team away from the next packet.
    """
    candidates = []
    for aid in (
        int(_PRESSURE_ANCHOR_LOCK_ID or 0),
        int(_SINGLE_TARGET_LOCK_ID or 0),
        int(_EXECUTION_LOCK_ID or 0),
    ):
        if aid > 0 and aid not in candidates:
            candidates.append(aid)

    for aid in candidates:
        try:
            if not Agent.IsValid(aid) or not Agent.IsAlive(aid):
                continue
            hp = float(Agent.GetHealth(aid))
            if hp <= 0.0 or hp > float(hp_threshold):
                continue
            if Distance(Player.GetAgentID(), aid) > float(range_value):
                continue
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "LOCKED_LOW_HP_FINISH",
                    target_id=int(aid),
                    hp=f"{float(hp):.4f}",
                    threshold=f"{float(hp_threshold):.4f}",
                    policy="finish_previous_focus_before_new_cluster",
                )
            except Exception:
                pass
            return int(aid)
        except Exception:
            continue
    return 0


def pick_execution_focus_target(
    *,
    range_value: float = Range.Spellcast.value,
    health_threshold: float = 0.15,
    prefer_player_target: bool = True,
) -> int:
    """Return a global low-HP execution target before normal cluster logic.

    Enemies below the threshold are deliberately allowed to override the main
    packet even when they are isolated.  The lowest-health reachable enemy is
    finished first, then the team immediately returns to the normal densest
    cluster.  A short lock keeps all clients/controllers on the same straggler
    instead of alternating between several low-HP enemies.
    """
    global _EXECUTION_LOCK_ID

    special_target = int(pick_special_priority_target(range_value=float(range_value)) or 0)
    if special_target > 0:
        return special_target

    enemies = refresh(range_value=range_value)
    threshold = float(health_threshold)

    # Keep the current execution target while it remains a valid sub-threshold
    # enemy in range. This produces a clean kill sequence for 2-3 stragglers.
    if int(_EXECUTION_LOCK_ID) > 0:
        for enemy in enemies:
            if (
                int(enemy.agent_id) == int(_EXECUTION_LOCK_ID)
                and 0.0 < float(enemy.health) < threshold
            ):
                return int(_EXECUTION_LOCK_ID)

    candidates = [
        enemy for enemy in enemies
        if 0.0 < float(enemy.health) < threshold
    ]
    if not candidates:
        _EXECUTION_LOCK_ID = 0
        return 0

    # Lowest HP first.  At equal HP, finish dangerous/healing enemies first;
    # packet membership and distance are only tie-breakers.
    candidates.sort(key=lambda enemy: (
        float(enemy.health),
        -int(enemy.threat_score),
        -int(enemy.adjacent_count),
        int(enemy.agent_id),
        float(enemy.distance_to_player),
    ))
    chosen = int(candidates[0].agent_id)
    _EXECUTION_LOCK_ID = chosen
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.tick()
        CombatDebug.mark_focus(chosen, reason="execution_low_hp_global")
    except Exception:
        pass
    return chosen


def pick_healer_spike_target(
    *,
    range_value: float = Range.Spellcast.value,
) -> int:
    """Return a healer/protection target only when it is actively stopping kills.

    This is intentionally not a profession-only priority.  A Monk standing
    idle never beats a useful two/three-enemy packet.  The override activates
    for a current high-value heal/protection cast or for repeated support casts
    observed inside a short rolling window.  Resurrection is excluded because
    the interrupt coordinator can stop it without pulling the full team off the
    damage packet.
    """
    now = now_ms()
    enemies = refresh(range_value=range_value, throttle_ms=SENSE_SCAN_THROTTLE_MS)
    live_ids = {int(e.agent_id) for e in enemies}

    # Drop stale/recycled agents and old events.
    cutoff = int(now) - int(HEALER_PRESSURE_WINDOW_MS)
    for aid in list(_HEALER_PRESSURE_EVENTS.keys()):
        if aid not in live_ids:
            _HEALER_PRESSURE_EVENTS.pop(aid, None)
            continue
        recent = [tick for tick in _HEALER_PRESSURE_EVENTS.get(aid, []) if int(tick) >= cutoff]
        if recent:
            _HEALER_PRESSURE_EVENTS[aid] = recent
        else:
            _HEALER_PRESSURE_EVENTS.pop(aid, None)

    candidates: list[tuple[int, float, float, int]] = []
    for enemy in enemies:
        aid = int(enemy.agent_id)
        sid = int(enemy.casting_skill_id or 0)
        current_support = sid in PROT_HEAL_SKILL_IDS and sid not in REZ_SKILL_IDS
        if current_support:
            events = _HEALER_PRESSURE_EVENTS.setdefault(aid, [])
            # One cast is observed over several scans; record it only once per
            # practical cast window.
            if not events or int(now) - int(events[-1]) >= 650:
                events.append(int(now))

        count = len(_HEALER_PRESSURE_EVENTS.get(aid, []))
        if not current_support and count < int(HEALER_PRESSURE_REPEAT_CASTS):
            continue

        # Current support action is urgent; repeated support proves that this
        # target is extending the fight.  Lower health and higher threat break
        # ties so a nearly dead healer is cleanly finished.
        pressure = count + (int(HEALER_PRESSURE_CURRENT_STRONG_BONUS) if current_support else 0)
        candidates.append((
            -int(pressure),
            float(enemy.health),
            float(enemy.distance_to_player),
            aid,
        ))

    if not candidates:
        return 0
    candidates.sort()
    chosen = int(candidates[0][3])
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.tick()
        CombatDebug.mark_focus(chosen, reason="active_repeated_healer_spike")
    except Exception:
        pass
    return chosen



def dangerous_aoe_caster_cluster(
    *,
    range_value: float = Range.Spellcast.value,
    minimum_dangerous_casters: int = 2,
) -> tuple[bool, int, tuple[int, ...]]:
    """Detect a caster-heavy canonical packet before/at engage."""
    enemies=list(refresh(range_value=float(range_value), throttle_ms=60))
    if not enemies:
        return (False,0,())
    packets={}
    for e in enemies:
        members=tuple(sorted(
            int(o.agent_id) for o in enemies
            if distance_xy(e.xy,o.xy) <= float(Range.Adjacent.value)
        ))
        if len(members)>=2:
            packets[members]=members
    if not packets:
        return (False,0,())
    members=sorted(packets.values(),key=lambda sig:(-len(sig),sig))[0]
    by_id={int(e.agent_id):e for e in enemies}
    try:
        _monk,_rit,mesmer_id,ele_id,necro_id=_profession_ids()
    except Exception:
        mesmer_id=ele_id=necro_id=0
    dangerous=0
    for aid in members:
        e=by_id.get(int(aid))
        if e is None:
            continue
        live_danger=bool(e.is_casting and int(e.casting_skill_id or 0) in AOE_SHUTDOWN_SKILL_IDS)
        caster_profile=bool(
            int(e.primary_profession) in (mesmer_id,ele_id,necro_id)
            and int(e.threat_score)>=55
        )
        if live_danger or caster_profile or int(e.threat_score)>=100:
            dangerous += 1
    anchor=int(members[0]) if members else 0
    flag=bool(dangerous>=int(minimum_dangerous_casters))
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.log_event(
            "DANGEROUS_CASTER_CLUSTER",
            target_id=anchor,
            packet_size=len(members),
            dangerous_casters=int(dangerous),
            is_dangerous=flag,
            packet_members=",".join(str(int(x)) for x in members),
            policy="two_plus_caster_or_live_aoe_threat",
        )
    except Exception:
        pass
    return (flag,anchor,tuple(int(x) for x in members))


def pick_pressure_anchor(
    *,
    range_value: float = Range.Spellcast.value,
    minimum_enemies: int = 2,
    player_target: int = 0,
    prefer_player_target_margin: int = 40,
) -> int:
    """Return one canonical packet anchor for every KeySoJway consumer.

    This deliberately avoids local target, threat, cast-state, movement
    prediction and distance tie-breaks. Those inputs can differ slightly
    between multibox clients and were the source of split packet decisions.

    Packet choice is now deterministic:
      Krummrinde -> <=10% locked finisher -> largest current adjacent packet ->
      lexicographically smallest packet signature.
    The anchor is the lowest agent id inside that chosen packet.
    """
    global _PRESSURE_ANCHOR_LOCK_ID, _PRESSURE_ANCHOR_LOCK_UNTIL_MS
    global _PRESSURE_ANCHOR_LOCK_SCORE

    special_target = int(pick_special_priority_target(range_value=float(range_value)) or 0)
    if special_target > 0:
        return special_target

    finisher = int(pick_locked_low_hp_finisher(
        range_value=float(range_value),
        hp_threshold=0.10,
    ) or 0)
    if finisher > 0:
        return finisher

    enemies = list(refresh(range_value=range_value, throttle_ms=70))
    if not enemies:
        _PRESSURE_ANCHOR_LOCK_ID = 0
        _PRESSURE_ANCHOR_LOCK_UNTIL_MS = 0
        _PRESSURE_ANCHOR_LOCK_SCORE = 0
        return 0

    # Current geometry only. Build canonical packet signatures so two clients
    # looking at the same enemies cannot select different centers of one ball.
    packets: dict[tuple[int, ...], tuple[int, ...]] = {}
    for e in enemies:
        members = tuple(sorted(
            int(o.agent_id) for o in enemies
            if distance_xy(e.xy, o.xy) <= float(Range.Adjacent.value)
        ))
        if len(members) >= int(minimum_enemies):
            packets[members] = members

    if not packets:
        _PRESSURE_ANCHOR_LOCK_ID = 0
        _PRESSURE_ANCHOR_LOCK_UNTIL_MS = 0
        _PRESSURE_ANCHOR_LOCK_SCORE = 0
        return 0

    # Largest packet first. Equal-size packets are resolved by the complete
    # sorted ID signature, never by local player position or transient threat.
    ordered = sorted(packets.values(), key=lambda sig: (-len(sig), sig))
    chosen_members = ordered[0]
    anchor = int(chosen_members[0])

    _PRESSURE_ANCHOR_LOCK_ID = anchor
    _PRESSURE_ANCHOR_LOCK_UNTIL_MS = 0
    _PRESSURE_ANCHOR_LOCK_SCORE = int(len(chosen_members))

    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.tick()
        CombatDebug.mark_focus(anchor, reason="canonical_cluster")
        CombatDebug.log_event(
            "TEAM_CANONICAL_CLUSTER",
            target_id=int(anchor),
            packet_size=int(len(chosen_members)),
            packet_members=",".join(str(x) for x in chosen_members),
            shared_origin_x=round(float(shared_team_origin_xy()[0]), 1) if shared_team_origin_xy() else 0.0,
            shared_origin_y=round(float(shared_team_origin_xy()[1]), 1) if shared_team_origin_xy() else 0.0,
            policy="shared_party0_origin_largest_packet_then_id_signature",
        )
    except Exception:
        pass
    return anchor

def pick_single_target_anchor(
    *,
    range_value: float = Range.Spellcast.value,
    player_target: int = 0,
    assignment_slot: int | None = None,
    consumer_role: str = "",
) -> int:
    """Hard sequential cleanup shared by every account and hero.

    Order:
      1) Krummrinde / Twisted Bark
      2) <=10% previous packet survivor
      3) healers
      4) dangerous casters / active resurrection
      5) support
      6) rest

    Once a cleanup target is selected, _SINGLE_TARGET_LOCK_ID remains on that
    exact enemy until it dies/leaves the valid enemy set. There is no timed
    handoff, local player-target override, assignment split or HP re-ranking.
    """
    global _SINGLE_TARGET_LOCK_ID, _SINGLE_TARGET_LOCK_UNTIL_MS

    special_target = int(pick_special_priority_target(range_value=float(range_value)) or 0)
    if special_target > 0:
        _SINGLE_TARGET_LOCK_ID = int(special_target)
        return special_target

    finisher = int(pick_locked_low_hp_finisher(
        range_value=float(range_value),
        hp_threshold=0.10,
    ) or 0)
    if finisher > 0:
        _SINGLE_TARGET_LOCK_ID = int(finisher)
        return finisher

    enemies = list(refresh(range_value=range_value, throttle_ms=70))
    if not enemies:
        _SINGLE_TARGET_LOCK_ID = 0
        _SINGLE_TARGET_LOCK_UNTIL_MS = 0
        return 0

    # Cleanup only when no 2+ adjacent packet remains.
    if any(int(e.adjacent_count) >= 2 for e in enemies):
        _SINGLE_TARGET_LOCK_ID = 0
        _SINGLE_TARGET_LOCK_UNTIL_MS = 0
        return 0

    by_id = {int(e.agent_id): e for e in enemies}
    locked = by_id.get(int(_SINGLE_TARGET_LOCK_ID or 0))
    if locked is not None:
        chosen = int(locked.agent_id)
        mode = "locked_cleanup"
    else:
        def knowledge(e: EnemySense) -> tuple[int, int, int, int]:
            try:
                from Py4GWCoreLib.Builds.Skills import EnemyKnowledge
                scores = EnemyKnowledge.role_scores(int(e.agent_id))
                return (
                    int(scores.get("healer", 0)),
                    int(scores.get("support", 0)),
                    int(scores.get("caster", 0)),
                    int(scores.get("offense", 0)),
                )
            except Exception:
                return (0, 0, 0, 0)

        ranked = []
        for e in enemies:
            healer, support, caster, offense = knowledge(e)
            is_rez = bool(e.is_casting and int(e.casting_skill_id or 0) in REZ_SKILL_IDS)
            if healer >= 70:
                category = 0
                mode_name = "healer_focus"
            elif caster >= 75 or offense >= 70 or is_rez:
                category = 1
                mode_name = "dangerous_caster_focus"
            elif support >= 105:
                category = 2
                mode_name = "support_focus"
            else:
                category = 3
                mode_name = "sequential_focus"

            # Stable role scores + ID only. Never health/distance/manual target.
            ranked.append((
                int(category),
                -int(healer),
                -int(caster),
                -int(offense),
                -int(support),
                int(e.agent_id),
                str(mode_name),
            ))

        ranked.sort()
        best = ranked[0]
        chosen = int(best[5])
        mode = str(best[6])
        _SINGLE_TARGET_LOCK_ID = chosen

    _SINGLE_TARGET_LOCK_UNTIL_MS = 0
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.tick()
        CombatDebug.mark_focus(chosen, reason="hard_sequential_cleanup")
        CombatDebug.log_event(
            "TEAM_SEQUENTIAL_CLEANUP",
            target_id=int(chosen),
            mode=str(mode),
            enemy_count=int(len(enemies)),
            consumer_role=str(consumer_role or "party"),
            policy="hard_lock_until_dead_healer_caster_support_rest",
        )
    except Exception:
        pass
    return chosen

def get_enemy_sense(agent_id: int, *, range_value: float = Range.Spellcast.value) -> EnemySense | None:
    aid = int(agent_id or 0)
    if aid <= 0:
        return None
    for e in refresh(range_value=range_value):
        if int(e.agent_id) == aid:
            return e
    return None
