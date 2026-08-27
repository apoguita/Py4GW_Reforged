"""Shared low-health execution target helper for Simple-Power builds.

This module is intentionally small and cheap: it only scans enemies in normal
spellcast range for targets at or below the configured health threshold. It is
used as a short override before normal packet/cluster targeting, so damaged
stragglers are finished before they can be healed back up.
"""

from Py4GWCoreLib import Range
from Py4GWCoreLib import Routines
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player

EXECUTION_FOCUS_HEALTH_THRESHOLD = 0.15
EXECUTION_FOCUS_SCAN_THROTTLE_MS = 150

_last_scan_tick: int = 0
_cached_target_id: int = 0
_cached_threshold: float = EXECUTION_FOCUS_HEALTH_THRESHOLD
_cached_range: float = Range.Spellcast.value


def _now_ms() -> int:
    try:
        import Py4GW
        return int(Py4GW.Game.get_tick_count64() or 0)
    except Exception:
        try:
            import time
            return int(time.monotonic() * 1000.0)
        except Exception:
            return 0


def _enemy_health(agent_id: int) -> float:
    try:
        return float(Routines.Checks.Agents.GetHealth(int(agent_id)))
    except Exception:
        try:
            return float(Agent.GetHealth(int(agent_id)))
        except Exception:
            return 1.0


def _is_alive_valid_enemy(agent_id: int) -> bool:
    try:
        agent_id = int(agent_id or 0)
        if agent_id <= 0:
            return False
        if not Agent.IsValid(agent_id) or not Agent.IsAlive(agent_id):
            return False
        return True
    except Exception:
        return False


def _distance_to_player(agent_id: int) -> float:
    try:
        from Py4GWCoreLib.Py4GWcorelib import Utils
        return float(Utils.Distance(Player.GetXY(), Agent.GetXY(int(agent_id))))
    except Exception:
        return 999999.0


def _count_adjacent_enemies(agent_id: int) -> int:
    try:
        from Py4GWCoreLib import AgentArray
        enemies = AgentArray.GetEnemyArray()
        enemies = AgentArray.Filter.ByDistance(enemies, Agent.GetXY(int(agent_id)), Range.Adjacent.value)
        enemies = AgentArray.Filter.ByCondition(
            enemies,
            lambda enemy_id: _is_alive_valid_enemy(int(enemy_id)),
        )
        return int(len(enemies or []))
    except Exception:
        try:
            return int(Routines.Targeting.CountNearbyEnemies(int(agent_id), Range.Adjacent.value) or 0)
        except Exception:
            return 0


def is_execution_focus_target(agent_id: int, *, health_threshold: float = EXECUTION_FOCUS_HEALTH_THRESHOLD) -> bool:
    """True if the enemy is a valid low-health execution target."""
    if not _is_alive_valid_enemy(agent_id):
        return False
    health = _enemy_health(agent_id)
    return 0.0 < health < float(health_threshold)


def _cached_target_still_valid(range_value: float, health_threshold: float) -> bool:
    if _cached_target_id <= 0:
        return False
    if abs(float(_cached_threshold) - float(health_threshold)) > 0.001:
        return False
    if abs(float(_cached_range) - float(range_value)) > 0.001:
        return False
    if not is_execution_focus_target(_cached_target_id, health_threshold=health_threshold):
        return False
    return _distance_to_player(_cached_target_id) <= float(range_value)


def pick_execution_focus_target(
    *,
    range_value: float = Range.Spellcast.value,
    health_threshold: float = EXECUTION_FOCUS_HEALTH_THRESHOLD,
    prefer_player_target: bool = True,
) -> int:
    """Pick the best low-health enemy to execute before returning to packets.

    Priority:
    1. Player's current target, if it is already below threshold.
    2. Lowest-health valid enemy in normal offensive range, even outside a packet.
    3. Ties prefer dangerous enemies, then packet membership and distance.

    The scan is throttled locally to avoid adding heavy per-tick work.
    """
    global _last_scan_tick, _cached_target_id, _cached_threshold, _cached_range

    range_value = float(range_value)
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        if abs(float(health_threshold) - float(EXECUTION_FOCUS_HEALTH_THRESHOLD)) < 0.001:
            health_threshold = SimplePowerSettings.get_execution_threshold(float(health_threshold))
    except Exception:
        pass
    health_threshold = float(health_threshold)

    # Prefer the shared CombatSense cache when available.  If it is enabled
    # and successfully returns no execution target, avoid doing a second local
    # enemy scan in the same tick.  Fall back only when the cache is disabled
    # or raises at runtime.
    used_combat_sense = False
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        if SimplePowerSettings.is_feature_enabled("combat_sense_cache", True):
            from Py4GWCoreLib.Builds.Skills import CombatSense
            used_combat_sense = True
            sensed_target = CombatSense.pick_execution_focus_target(
                range_value=range_value,
                health_threshold=health_threshold,
                prefer_player_target=prefer_player_target,
            )
            if int(sensed_target or 0) > 0:
                _cached_target_id = int(sensed_target)
                _cached_threshold = health_threshold
                _cached_range = range_value
                _last_scan_tick = _now_ms()
                try:
                    from Py4GWCoreLib.Builds.Skills import Telemetry
                    Telemetry.count("execution.focus_target")
                except Exception:
                    pass
                return int(sensed_target)
            _cached_target_id = 0
            _cached_threshold = health_threshold
            _cached_range = range_value
            _last_scan_tick = _now_ms()
            return 0
    except Exception:
        used_combat_sense = False

    if prefer_player_target:
        try:
            player_target = int(Player.GetTargetID() or 0)
        except Exception:
            player_target = 0
        if (
            player_target > 0
            and is_execution_focus_target(player_target, health_threshold=health_threshold)
            and _distance_to_player(player_target) <= range_value
        ):
            _cached_target_id = int(player_target)
            _cached_threshold = health_threshold
            _cached_range = range_value
            _last_scan_tick = _now_ms()
            try:
                from Py4GWCoreLib.Builds.Skills import Telemetry
                Telemetry.count("execution.focus_target")
            except Exception:
                pass
            return int(player_target)

    now = _now_ms()
    if now > 0 and _last_scan_tick > 0 and (now - _last_scan_tick) < EXECUTION_FOCUS_SCAN_THROTTLE_MS:
        if _cached_target_still_valid(range_value, health_threshold):
            return int(_cached_target_id)

    try:
        from Py4GWCoreLib import AgentArray
        enemies = AgentArray.GetEnemyArray()
        enemies = AgentArray.Filter.ByDistance(enemies, Player.GetXY(), range_value)
        enemies = AgentArray.Filter.ByCondition(
            enemies,
            lambda enemy_id: is_execution_focus_target(int(enemy_id), health_threshold=health_threshold),
        )
        candidates = [int(enemy_id) for enemy_id in enemies or []]
    except Exception:
        candidates = []

    if not candidates:
        _cached_target_id = 0
        _cached_threshold = health_threshold
        _cached_range = range_value
        _last_scan_tick = now
        return 0

    candidates.sort(key=lambda enemy_id: (
        _enemy_health(enemy_id),
        -_count_adjacent_enemies(enemy_id),
        _distance_to_player(enemy_id),
        int(enemy_id),
    ))

    _cached_target_id = int(candidates[0])
    _cached_threshold = health_threshold
    _cached_range = range_value
    _last_scan_tick = now
    try:
        from Py4GWCoreLib.Builds.Skills import Telemetry
        Telemetry.count("execution.focus_target")
    except Exception:
        pass
    return int(candidates[0])
