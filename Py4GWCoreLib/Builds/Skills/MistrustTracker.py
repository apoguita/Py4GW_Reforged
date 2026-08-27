from __future__ import annotations

"""Low-overhead Mistrust diagnostics without damage/effect event hooks.

The tracker only consumes the already-enabled safe cast lifecycle events and
live Agent state.  It never registers native callbacks itself and never reads
combat agents from inside a callback.

Results are intentionally conservative:
- ``cast_observed`` means the hexed foe began a cast during the tracking window.
- ``cast_interrupted/stopped/finished`` records the native outcome of that cast.
- ``expired_unused`` means no cast was observed before the local window ended.
It does not claim exact damage or guaranteed Mistrust activation.
"""

from dataclasses import dataclass

TRACK_WINDOW_MS = 6200
LOG_COOLDOWN_MS = 900


@dataclass(slots=True)
class _Record:
    source_id: int
    target_id: int
    applied_ms: int
    expires_ms: int
    observed_skill_id: int = 0
    observed_start_ms: int = 0
    last_log_ms: int = 0


_RECORDS: dict[tuple[int, int], _Record] = {}
_LAST_OUTCOME_SYNC_MS: int = 0


def _now_ms() -> int:
    try:
        import PySystem
        return int(PySystem.get_tick_count64() or 0)
    except Exception:
        try:
            import time
            return int(time.monotonic() * 1000.0)
        except Exception:
            return 0


def _log(event: str, **fields) -> None:
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.log_event(str(event), **fields)
    except Exception:
        pass


def register_cast(source_id: int, target_id: int, duration_ms: int = TRACK_WINDOW_MS) -> None:
    source_id, target_id = int(source_id or 0), int(target_id or 0)
    if source_id <= 0 or target_id <= 0:
        return
    now = _now_ms()
    key = (source_id, target_id)
    _RECORDS[key] = _Record(
        source_id=source_id,
        target_id=target_id,
        applied_ms=now,
        expires_ms=now + max(1000, int(duration_ms or TRACK_WINDOW_MS)),
    )
    _log("MISTRUST_TRACK_CAST", source_id=source_id, target_id=target_id, expires_ms=int(duration_ms or TRACK_WINDOW_MS))


def is_target_tracked(target_id: int) -> bool:
    target_id = int(target_id or 0)
    if target_id <= 0:
        return False
    tick()
    return any(int(rec.target_id) == target_id for rec in _RECORDS.values())


def _target_alive(target_id: int) -> bool:
    try:
        from Py4GWCoreLib.Agent import Agent
        return bool(Agent.IsValid(int(target_id)) and Agent.IsAlive(int(target_id)))
    except Exception:
        return False


def _active_cast_for(target_id: int):
    try:
        from Py4GWCoreLib.Builds.Skills import ReforgedSupport
        return ReforgedSupport.get_recent_cast(int(target_id), max_age_ms=8000)
    except Exception:
        return None


def tick(live_agent_ids=()) -> None:
    """Advance local records; safe to call frequently because work is tiny."""
    global _LAST_OUTCOME_SYNC_MS
    if not _RECORDS:
        return
    now = _now_ms()
    live = {int(x) for x in live_agent_ids if int(x or 0) > 0}

    outcomes = ()
    try:
        from Py4GWCoreLib.Builds.Skills import ReforgedSupport
        outcomes = ReforgedSupport.get_recent_cast_outcomes(max_age_ms=9000)
    except Exception:
        outcomes = ()

    for key, rec in list(_RECORDS.items()):
        if live and rec.target_id not in live:
            _log("MISTRUST_TRACK_RESULT", source_id=rec.source_id, target_id=rec.target_id, result="target_gone", observed_skill_id=rec.observed_skill_id)
            _RECORDS.pop(key, None)
            continue
        if not _target_alive(rec.target_id):
            _log("MISTRUST_TRACK_RESULT", source_id=rec.source_id, target_id=rec.target_id, result="target_dead_or_invalid", observed_skill_id=rec.observed_skill_id)
            _RECORDS.pop(key, None)
            continue

        if rec.observed_skill_id <= 0:
            cast = _active_cast_for(rec.target_id)
            if cast:
                skill_id, _target, start_ms, _duration_s = cast
                if int(start_ms or 0) >= int(rec.applied_ms or 0):
                    rec.observed_skill_id = int(skill_id or 0)
                    rec.observed_start_ms = int(start_ms or now)
                    if now - rec.last_log_ms >= LOG_COOLDOWN_MS:
                        rec.last_log_ms = now
                        _log("MISTRUST_CAST_OBSERVED", source_id=rec.source_id, target_id=rec.target_id, enemy_skill_id=rec.observed_skill_id)

        if rec.observed_skill_id > 0:
            matched = None
            for ts, caster_id, skill_id, result in outcomes:
                if int(ts) < int(rec.observed_start_ms or rec.applied_ms):
                    continue
                if int(caster_id) == int(rec.target_id) and int(skill_id or 0) in (0, int(rec.observed_skill_id)):
                    matched = str(result)
                    break
            if matched:
                _log(
                    "MISTRUST_TRACK_RESULT",
                    source_id=rec.source_id,
                    target_id=rec.target_id,
                    enemy_skill_id=rec.observed_skill_id,
                    result=f"cast_{matched}",
                )
                _RECORDS.pop(key, None)
                continue

        if now >= int(rec.expires_ms):
            result = "expired_after_cast_observed" if rec.observed_skill_id > 0 else "expired_unused"
            _log("MISTRUST_TRACK_RESULT", source_id=rec.source_id, target_id=rec.target_id, enemy_skill_id=rec.observed_skill_id, result=result)
            _RECORDS.pop(key, None)


def reset() -> None:
    _RECORDS.clear()
