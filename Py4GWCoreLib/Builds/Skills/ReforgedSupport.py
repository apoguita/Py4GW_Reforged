from __future__ import annotations

"""Reforged native combat-event bridge with safe polling fallbacks.

Native PyAgentEvents timestamps are preferred for cast starts, exact CASTTIME
packets are retained when available, and live Agent state remains the final
truth before an interrupt is fired.
"""

import math
from collections import deque

_CASTS: dict[int, tuple[int, int, int]] = {}          # caster -> skill,target,start
_CAST_DURATIONS_MS: dict[tuple[int, int], int] = {}  # (caster,skill) -> exact total
_PENDING_CASTTIME: dict[int, tuple[int, int]] = {}   # caster -> duration,tick
_OUTCOMES: deque[tuple[int, int, int, str]] = deque(maxlen=512)
_DAMAGE: deque[tuple[int, int, int, float, int]] = deque(maxlen=1024)
ENABLE_DAMAGE_EVENTS = False  # stability-first: cast events only in production
_REGISTERED = False
_INIT_ERROR = ""
_EVENT_COUNT = 0
_PATH_CACHE: dict[tuple[int, int, int, int, int], tuple[int, bool, float]] = {}
_PATH_CACHE_TTL_MS = 1200


def _tick() -> int:
    try:
        import PySystem
        return int(PySystem.get_tick_count64() or 0)
    except Exception:
        try:
            import Py4GW
            return int(Py4GW.Game.get_tick_count64() or 0)
        except Exception:
            return 0


def _on_skill_activated(caster_id: int, skill_id: int, target_id: int, event_tick: int = 0) -> None:
    """Record the earliest packet for a cast and avoid duplicate timestamp reset."""
    global _EVENT_COUNT
    caster_id, skill_id = int(caster_id or 0), int(skill_id or 0)
    if caster_id <= 0 or skill_id <= 0:
        return

    now = int(event_tick or _tick())
    target_id = int(target_id or 0)
    active = _CASTS.get(caster_id)
    if active and int(active[0]) == skill_id:
        old_skill, old_target, old_start = active
        _CASTS[caster_id] = (
            int(old_skill),
            target_id or int(old_target),
            min(int(old_start or now), int(now or old_start)),
        )
    else:
        if active:
            _CAST_DURATIONS_MS.pop((caster_id, int(active[0])), None)
        _CASTS[caster_id] = (skill_id, target_id, now)

    pending = _PENDING_CASTTIME.pop(caster_id, None)
    if pending:
        duration_ms, captured_tick = pending
        if not now or not captured_tick or now - captured_tick <= 750:
            _CAST_DURATIONS_MS[(caster_id, skill_id)] = int(duration_ms)
    _EVENT_COUNT += 1


def _on_cast_time(caster_id: int, skill_id: int, duration_seconds: float) -> None:
    """Capture the exact native cast duration, including cast-time modifiers."""
    global _EVENT_COUNT
    caster_id, skill_id = int(caster_id or 0), int(skill_id or 0)
    try:
        duration_ms = int(float(duration_seconds or 0.0) * 1000.0)
    except Exception:
        duration_ms = 0
    if caster_id <= 0 or duration_ms <= 0:
        return

    active = _CASTS.get(caster_id)
    if skill_id <= 0 and active:
        skill_id = int(active[0])
    if skill_id > 0:
        _CAST_DURATIONS_MS[(caster_id, skill_id)] = duration_ms
    else:
        _PENDING_CASTTIME[caster_id] = (duration_ms, _tick())
    _EVENT_COUNT += 1


def _finish(caster_id: int, skill_id: int, outcome: str) -> None:
    global _EVENT_COUNT
    caster_id, skill_id = int(caster_id or 0), int(skill_id or 0)
    active = _CASTS.get(caster_id)
    if skill_id <= 0 and active:
        skill_id = int(active[0])
    if active is None or skill_id <= 0 or int(active[0]) == skill_id:
        _CASTS.pop(caster_id, None)
    if caster_id > 0 and skill_id > 0:
        _CAST_DURATIONS_MS.pop((caster_id, skill_id), None)
    _PENDING_CASTTIME.pop(caster_id, None)
    _OUTCOMES.append((_tick(), caster_id, skill_id, str(outcome)))
    _EVENT_COUNT += 1


def _on_skill_finished(caster_id: int, skill_id: int) -> None:
    _finish(caster_id, skill_id, "finished")


def _on_skill_stopped(caster_id: int, skill_id: int) -> None:
    _finish(caster_id, skill_id, "stopped")


def _on_skill_interrupted(caster_id: int, skill_id: int) -> None:
    _finish(caster_id, skill_id, "interrupted")


def _on_damage(target_id: int, source_id: int, damage_fraction: float, skill_id: int) -> None:
    global _EVENT_COUNT
    _DAMAGE.append((
        _tick(), int(target_id or 0), int(source_id or 0),
        float(damage_fraction or 0.0), int(skill_id or 0),
    ))
    _EVENT_COUNT += 1


def ensure_initialized() -> bool:
    global _REGISTERED, _INIT_ERROR
    if _REGISTERED:
        return True
    try:
        from Py4GWCoreLib.CombatEvents import CombatEvents, CombatEventQueue
        if not CombatEventQueue.IsAvailable():
            _INIT_ERROR = "native event backend unavailable; using frame observer/polling fallback"
            return False
        if not CombatEvents.Enable():
            _INIT_ERROR = "native event backend could not initialize; using fallback"
            return False
        if hasattr(CombatEvents, "OnSkillActivatedTimed"):
            CombatEvents.OnSkillActivatedTimed(_on_skill_activated)
        else:
            CombatEvents.OnSkillActivated(_on_skill_activated)
        CombatEvents.OnCastTime(_on_cast_time)
        CombatEvents.OnSkillFinished(_on_skill_finished)
        CombatEvents.OnSkillStopped(_on_skill_stopped)
        CombatEvents.OnSkillInterrupted(_on_skill_interrupted)
        if ENABLE_DAMAGE_EVENTS:
            CombatEvents.OnDamage(_on_damage)
        _REGISTERED = True
        _INIT_ERROR = ""
        try:
            import PySystem
            PySystem.Console.Log(
                "HeroAI Events",
                f"Cast event bridge active via {CombatEventQueue.GetBackendName()}",
                PySystem.Console.MessageType.Info,
            )
        except Exception:
            pass
        return True
    except Exception as exc:
        _INIT_ERROR = repr(exc)
        return False


def get_active_casts(max_age_ms: int = 8000) -> tuple[tuple[int, int, int, int, str], ...]:
    ensure_initialized()
    now = _tick()
    out: list[tuple[int, int, int, int, str]] = []
    for caster_id, (skill_id, target_id, start_tick) in list(_CASTS.items()):
        if now and start_tick and now - start_tick > int(max_age_ms):
            _CASTS.pop(caster_id, None)
            _CAST_DURATIONS_MS.pop((int(caster_id), int(skill_id)), None)
            continue
        out.append((int(caster_id), int(skill_id), int(target_id), int(start_tick), "native_event"))
    out.sort(key=lambda item: (item[3], item[0], item[1]))
    return tuple(out)


def get_recent_cast(caster_id: int, max_age_ms: int = 8000) -> tuple[int, int, int, float] | None:
    caster_id = int(caster_id or 0)
    for aid, sid, target, start, _ in reversed(get_active_casts(max_age_ms=max_age_ms)):
        if aid == caster_id:
            duration_s = float(_CAST_DURATIONS_MS.get((aid, sid), 0)) / 1000.0
            return (sid, target, start, duration_s)
    return None


def get_cast_target_id(caster_id: int, expected_skill_id: int = 0) -> int:
    cast = get_recent_cast(caster_id)
    if not cast:
        return 0
    skill_id, target_id, _, _ = cast
    if expected_skill_id and int(skill_id) != int(expected_skill_id):
        return 0
    return int(target_id or 0)


def get_cast_duration_ms(caster_id: int, skill_id: int) -> int:
    """Return exact native CASTTIME for the active cast, or zero if unknown."""
    ensure_initialized()
    return max(0, int(_CAST_DURATIONS_MS.get((int(caster_id), int(skill_id)), 0) or 0))


def get_cast_outcome(caster_id: int, skill_id: int, since_tick: int) -> str | None:
    ensure_initialized()
    caster_id, skill_id, since_tick = int(caster_id or 0), int(skill_id or 0), int(since_tick or 0)
    for ts, aid, sid, result in reversed(_OUTCOMES):
        if ts < since_tick:
            break
        if aid == caster_id and (skill_id <= 0 or sid in (0, skill_id)):
            return result
    return None



def get_recent_cast_outcomes(max_age_ms: int = 8000) -> tuple[tuple[int, int, int, str], ...]:
    """Return recent cast finish/stop/interrupt events without damage hooks.

    This is safe for threat learning and Mistrust/interrupt diagnostics.  It
    intentionally exposes only compact immutable tuples and never dereferences
    combat agents from inside the native callback.
    """
    ensure_initialized()
    now = _tick()
    out: list[tuple[int, int, int, str]] = []
    for item in reversed(_OUTCOMES):
        ts = int(item[0])
        if now and ts and now - ts > int(max_age_ms):
            break
        out.append((ts, int(item[1]), int(item[2]), str(item[3])))
    out.reverse()
    return tuple(out)

def get_recent_damage_events(max_age_ms: int = 2000) -> tuple[tuple[int, int, int, float, int], ...]:
    ensure_initialized()
    now = _tick()
    out = []
    for item in reversed(_DAMAGE):
        ts = int(item[0])
        if now and ts and now - ts > int(max_age_ms):
            break
        out.append(item)
    out.reverse()
    return tuple(out)


def get_observed_cast_elapsed_ms(agent_id: int, skill_id: int) -> int | None:
    now = _tick()
    for caster_id, observed_skill_id, _, start_tick, _ in reversed(get_active_casts()):
        if caster_id == int(agent_id) and observed_skill_id == int(skill_id):
            return max(0, now - int(start_tick)) if now and start_tick else 0
    try:
        from HeroAI.interrupt import cast_observer
        observed = cast_observer.elapsed_ms(int(agent_id), int(skill_id))
        return None if observed is None else max(0, int(observed))
    except Exception:
        return None


def get_cast_source(agent_id: int, skill_id: int) -> str:
    for caster_id, observed_skill_id, _, _, source in reversed(get_active_casts()):
        if caster_id == int(agent_id) and observed_skill_id == int(skill_id):
            return source
    try:
        from HeroAI.interrupt import cast_observer
        if cast_observer.elapsed_ms(int(agent_id), int(skill_id)) is not None:
            return "frame_observer"
    except Exception:
        pass
    return "polling_fallback"


def get_cast_start_tick(agent_id: int, skill_id: int) -> int:
    for caster_id, observed_skill_id, _, start_tick, _ in reversed(get_active_casts()):
        if caster_id == int(agent_id) and observed_skill_id == int(skill_id):
            return int(start_tick or 0)
    return 0


def raw_event_status() -> dict[str, int | bool | str]:
    initialized = ensure_initialized()
    queue_size = 0
    backend = "unavailable"
    try:
        from Py4GWCoreLib.CombatEvents import CombatEventQueue
        queue_size = int(CombatEventQueue.GetQueueSize() or 0)
        backend = str(CombatEventQueue.GetBackendName())
    except Exception:
        pass
    return {
        "initialized": bool(initialized),
        "backend": backend,
        "queue_size": queue_size,
        "native_events": int(_EVENT_COUNT),
        "active_casts": len(_CASTS),
        "exact_casttimes": len(_CAST_DURATIONS_MS),
        "damage_events_enabled": bool(ENABLE_DAMAGE_EVENTS),
        "damage_events": len(_DAMAGE),
        "error": _INIT_ERROR,
    }


def path_quality(start: tuple[float, float], goal: tuple[float, float]) -> tuple[bool, float]:
    """Optional Reforged path validation retained for non-movement callers."""
    now = _tick()
    try:
        from Py4GWCoreLib.Agent import Agent
        from Py4GWCoreLib.Player import Player
        z = float(Agent.GetZPlane(Player.GetAgentID()) or 0.0)
    except Exception:
        z = 0.0
    key = (round(start[0] / 40), round(start[1] / 40), round(goal[0] / 40), round(goal[1] / 40), int(z))
    cached = _PATH_CACHE.get(key)
    if cached and (not now or now - cached[0] <= _PATH_CACHE_TTL_MS):
        return cached[1], cached[2]
    try:
        import PyPathing
        planner = PyPathing.PathPlanner()
        path = list(planner.compute_immediate(float(start[0]), float(start[1]), z, float(goal[0]), float(goal[1]), z) or [])
        if not path:
            result = (False, float("inf"))
        else:
            length = 0.0
            px, py = float(start[0]), float(start[1])
            for point in path:
                x, y = float(point[0]), float(point[1])
                length += math.hypot(x - px, y - py)
                px, py = x, y
            endpoint_error = math.hypot(px - float(goal[0]), py - float(goal[1]))
            result = (endpoint_error <= 220.0, length + endpoint_error)
    except Exception:
        result = (False, float("inf"))
    _PATH_CACHE[key] = (now, result[0], result[1])
    return result


ensure_initialized()
