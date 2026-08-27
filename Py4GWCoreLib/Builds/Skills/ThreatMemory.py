"""Short-lived adaptive enemy threat memory.

The memory learns only from observed dangerous casts.  It does not infer damage
packets that Reforged has not exposed reliably to Python.  Repeated healers,
rezzers and AoE casters gain a decaying bonus used by targeting and interrupt
ranking.  State is bounded and pruned aggressively for eight-account use.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time

MEMORY_HALF_LIFE_MS = 8000
MEMORY_RETENTION_MS = 22000
MAX_MEMORY_SCORE = 260.0
MAX_TARGETING_BONUS = 150
MAX_INTERRUPT_BONUS = 18

@dataclass(slots=True)
class ThreatRecord:
    score: float
    last_update_ms: int
    cast_count: int = 0
    rez_count: int = 0
    heal_count: int = 0
    aoe_count: int = 0

_RECORDS: dict[int, ThreatRecord] = {}
_ACTIVE_CASTS: set[tuple[int, int]] = set()


def now_ms() -> int:
    try:
        import PySystem
        return int(PySystem.get_tick_count64() or 0)
    except Exception:
        try:
            return int(time.monotonic() * 1000.0)
        except Exception:
            return 0


def _decayed_score(record: ThreatRecord, now: int) -> float:
    age = max(0, int(now) - int(record.last_update_ms))
    if age <= 0:
        return float(record.score)
    factor = math.pow(0.5, float(age) / float(MEMORY_HALF_LIFE_MS))
    return float(record.score) * factor


def _weight_for_category(category: str, base_score: int) -> float:
    category = str(category)
    multiplier = {
        "resurrection": 1.45,
        "lethal_aoe": 1.25,
        "party_heal": 1.18,
        "hard_protection": 1.15,
        "hard_shutdown": 1.10,
        "major_heal": 1.05,
    }.get(category, 0.80)
    return max(4.0, float(base_score) * 0.23 * multiplier)


def record_cast(agent_id: int, skill_id: int, *, base_score: int, category: str) -> None:
    aid = int(agent_id or 0)
    sid = int(skill_id or 0)
    if aid <= 0 or sid <= 0 or int(base_score) <= 0:
        return
    now = now_ms()
    old = _RECORDS.get(aid)
    score = _decayed_score(old, now) if old is not None else 0.0
    if old is None:
        old = ThreatRecord(score=0.0, last_update_ms=now)
    old.score = min(MAX_MEMORY_SCORE, score + _weight_for_category(category, int(base_score)))
    old.last_update_ms = now
    old.cast_count += 1
    if category == "resurrection":
        old.rez_count += 1
    if category in {"major_heal", "party_heal", "heal_cleanse"}:
        old.heal_count += 1
    if category in {"lethal_aoe", "packet_pressure", "hard_shutdown"}:
        old.aoe_count += 1
    _RECORDS[aid] = old


def observe_current_casts(casts: tuple[tuple[int, int], ...] | list[tuple[int, int]]) -> None:
    """Record each cast once, even though the fast scanner sees it many times."""
    global _ACTIVE_CASTS
    current = {(int(a), int(s)) for a, s in casts if int(a or 0) > 0 and int(s or 0) > 0}
    new_casts = current.difference(_ACTIVE_CASTS)
    if new_casts:
        try:
            from Py4GWCoreLib.Builds.Skills import DangerousSkillPriorities as DSP
            for aid, sid in new_casts:
                score = DSP.get_base_score(sid, 0)
                if score > 0:
                    record_cast(aid, sid, base_score=score, category=DSP.get_category(sid))
        except Exception:
            pass
    _ACTIVE_CASTS = current


def get_raw_score(agent_id: int) -> float:
    aid = int(agent_id or 0)
    record = _RECORDS.get(aid)
    if record is None:
        return 0.0
    now = now_ms()
    if now - int(record.last_update_ms) > MEMORY_RETENTION_MS:
        _RECORDS.pop(aid, None)
        return 0.0
    return max(0.0, _decayed_score(record, now))


def get_targeting_bonus(agent_id: int) -> int:
    return min(MAX_TARGETING_BONUS, int(get_raw_score(agent_id) * 0.75))


def get_interrupt_bonus(agent_id: int) -> int:
    return min(MAX_INTERRUPT_BONUS, int(get_raw_score(agent_id) / 11.0))


def prune(live_agent_ids: set[int] | list[int] | tuple[int, ...] = ()) -> None:
    now = now_ms()
    live = {int(x) for x in live_agent_ids if int(x or 0) > 0}
    for aid, record in list(_RECORDS.items()):
        if (live and aid not in live) or now - int(record.last_update_ms) > MEMORY_RETENTION_MS:
            _RECORDS.pop(aid, None)
    if live:
        global _ACTIVE_CASTS
        _ACTIVE_CASTS = {(a, s) for a, s in _ACTIVE_CASTS if a in live}


def reset() -> None:
    _RECORDS.clear()
    _ACTIVE_CASTS.clear()
