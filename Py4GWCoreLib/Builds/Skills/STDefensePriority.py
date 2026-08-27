"""Bounded ST/spirits protection priority for shared packet targeting.

This module never creates a permanent split target.  It only adds a short-lived
priority when the Soul Twisting ritualist or several owned core spirits are
under immediate local pressure.  The normal densest enemy packet remains the
main target and wins whenever it is materially larger.
"""
from __future__ import annotations

from Py4GWCoreLib import AgentArray, GLOBAL_CACHE, Range, Skill, Utils
from Py4GWCoreLib.Agent import Agent

_SCAN_INTERVAL_MS = 180
_ST_CACHE_MS = 800
_PRESSURE_RADIUS = float(Range.Area.value)
_SPIRIT_LOSS_WINDOW_MS = 7000
_PRIORITY_HOLD_MS = 1600

_SOUL_TWISTING_ID = int(Skill.GetID("Soul_Twisting") or 0)
_CORE_SKILL_IDS = frozenset(
    int(Skill.GetID(name) or 0)
    for name in ("Shelter", "Union", "Displacement", "Earthbind")
    if int(Skill.GetID(name) or 0) > 0
)
_CORE_MODEL_VALUES = frozenset((2883, 2884, 2885, 2886))
try:
    from Py4GWCoreLib import SpiritModelID
    _CORE_MODEL_VALUES = frozenset(
        int(getattr(model, "value", model))
        for model in (
            SpiritModelID.SHELTER,
            SpiritModelID.UNION,
            SpiritModelID.DISPLACEMENT,
            SpiritModelID.EARTHBIND,
        )
    )
except Exception:
    pass

_LAST_SCAN_MS = 0
_LAST_ST_LOOKUP_MS = 0
_ST_AGENT_ID = 0
_LAST_SPIRITS: dict[int, tuple[tuple[float, float], float]] = {}
_RECENT_LOSSES: list[int] = []
_PRIORITY_TARGET_ID = 0
_PRIORITY_UNTIL_MS = 0
_PRIORITY_BONUS = 0
_PRIORITY_REASON = ""
_LAST_LOG_STATE: tuple[int, int, str] = (0, 0, "")


def _now_ms() -> int:
    try:
        import PySystem
        return int(PySystem.get_tick_count64() or 0)
    except Exception:
        import time
        return int(time.monotonic() * 1000.0)


def _log(event: str, **fields) -> None:
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.log_event(str(event), **fields)
    except Exception:
        pass


def _skillbar_ids(account) -> set[int]:
    try:
        skills = account.AgentData.Skillbar.Skills
    except Exception:
        return set()
    out: set[int] = set()
    for skill in skills or []:
        try:
            sid = int(getattr(skill, "Id", 0) or 0)
        except Exception:
            sid = 0
        if sid > 0:
            out.add(sid)
    return out


def _iter_party_accounts():
    try:
        from Py4GWCoreLib.HeroAI.utils import SameMapOrPartyAsAccount
        own_party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
        seen: set[int] = set()
        for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
            if not getattr(account, "IsSlotActive", False) or getattr(account, "IsIsolated", False):
                continue
            if not SameMapOrPartyAsAccount(account):
                continue
            party_id = int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)
            if own_party_id > 0 and party_id != own_party_id:
                continue
            agent_id = int(getattr(getattr(account, "AgentData", None), "AgentID", 0) or 0)
            if agent_id > 0 and agent_id not in seen:
                seen.add(agent_id)
                yield account
            for hero in GLOBAL_CACHE.ShMem.GetHeroesFromPlayers(agent_id) or []:
                if not getattr(hero, "IsSlotActive", False) or getattr(hero, "IsIsolated", False):
                    continue
                if not SameMapOrPartyAsAccount(hero):
                    continue
                hero_id = int(getattr(getattr(hero, "AgentData", None), "AgentID", 0) or 0)
                if hero_id > 0 and hero_id not in seen:
                    seen.add(hero_id)
                    yield hero
    except Exception:
        return


def _find_st_agent(now_ms: int) -> int:
    global _LAST_ST_LOOKUP_MS, _ST_AGENT_ID
    if _ST_AGENT_ID > 0 and now_ms - int(_LAST_ST_LOOKUP_MS) < _ST_CACHE_MS:
        try:
            if Agent.IsValid(_ST_AGENT_ID) and Agent.IsAlive(_ST_AGENT_ID):
                return int(_ST_AGENT_ID)
        except Exception:
            pass
    _LAST_ST_LOOKUP_MS = int(now_ms)
    _ST_AGENT_ID = 0
    if _SOUL_TWISTING_ID <= 0:
        return 0
    for account in _iter_party_accounts() or []:
        skills = _skillbar_ids(account)
        if _SOUL_TWISTING_ID not in skills:
            continue
        if len(skills.intersection(_CORE_SKILL_IDS)) < 2:
            continue
        try:
            aid = int(account.AgentData.AgentID or 0)
        except Exception:
            aid = 0
        if aid > 0:
            _ST_AGENT_ID = aid
            return aid
    return 0


def _xy(agent_id: int) -> tuple[float, float] | None:
    try:
        pos = Agent.GetXY(int(agent_id))
        return (float(pos[0]), float(pos[1])) if pos else None
    except Exception:
        return None


def _distance_xy(a, b) -> float:
    try:
        return float(Utils.Distance(a, b))
    except Exception:
        return 999999.0


def _owned_core_spirits(st_agent_id: int) -> dict[int, tuple[tuple[float, float], float]]:
    result: dict[int, tuple[tuple[float, float], float]] = {}
    for spirit_id in AgentArray.GetSpiritPetArray() or []:
        try:
            sid = int(spirit_id or 0)
            if sid <= 0 or not Agent.IsAlive(sid) or not Agent.IsSpawned(sid):
                continue
            if int(Agent.GetOwnerID(sid) or 0) != int(st_agent_id):
                continue
            model = int(Agent.GetPlayerNumber(sid) or 0)
            if model not in _CORE_MODEL_VALUES:
                continue
            pos = _xy(sid)
            if pos is None:
                continue
            result[sid] = (pos, float(Agent.GetHealth(sid) or 0.0))
        except Exception:
            continue
    return result


def _enemy_active(enemy) -> bool:
    return bool(getattr(enemy, "is_attacking", False) or getattr(enemy, "is_casting", False))


def _near_any(enemy, positions: list[tuple[float, float]], radius: float = _PRESSURE_RADIUS) -> bool:
    pos = getattr(enemy, "xy", None)
    if not pos:
        return False
    return any(_distance_xy(pos, center) <= float(radius) for center in positions)


def get_priority(enemies) -> tuple[int, int, str]:
    """Return ``(target_id, score_bonus, reason)`` for bounded ST protection.

    Bonus 0 means no override.  Moderate pressure can only overcome a tie;
    severe repeated spirit loss can overcome roughly one enemy of packet size,
    but a materially larger cluster remains the main focus.
    """
    global _LAST_SCAN_MS, _LAST_SPIRITS, _RECENT_LOSSES
    global _PRIORITY_TARGET_ID, _PRIORITY_UNTIL_MS, _PRIORITY_BONUS, _PRIORITY_REASON, _LAST_LOG_STATE

    now = _now_ms()
    enemy_ids = {int(getattr(e, "agent_id", 0) or 0) for e in (enemies or [])}
    if now - int(_LAST_SCAN_MS) < _SCAN_INTERVAL_MS:
        if (
            int(_PRIORITY_TARGET_ID) > 0
            and int(_PRIORITY_TARGET_ID) in enemy_ids
            and now < int(_PRIORITY_UNTIL_MS)
        ):
            return int(_PRIORITY_TARGET_ID), int(_PRIORITY_BONUS), str(_PRIORITY_REASON)
        return 0, 0, ""
    _LAST_SCAN_MS = int(now)

    st_id = _find_st_agent(now)
    if st_id <= 0:
        _LAST_SPIRITS = {}
        _RECENT_LOSSES.clear()
        _PRIORITY_TARGET_ID = 0
        _PRIORITY_UNTIL_MS = 0
        _PRIORITY_BONUS = 0
        _PRIORITY_REASON = ""
        return 0, 0, ""

    st_pos = _xy(st_id)
    current_spirits = _owned_core_spirits(st_id)
    spirit_positions = [pos for pos, _hp in current_spirits.values()]
    positions = ([st_pos] if st_pos else []) + spirit_positions

    enemy_list = list(enemies or [])
    active_pressure = [e for e in enemy_list if _enemy_active(e) and _near_any(e, positions)]
    all_close = [e for e in enemy_list if _near_any(e, positions)]

    # Count a disappeared core spirit as a combat loss only when it was already
    # damaged or active enemies remained at its last position.  This filters
    # ordinary expiry/map cleanup while still catching rapid focus deaths.
    for spirit_id, (last_pos, last_hp) in list(_LAST_SPIRITS.items()):
        if spirit_id in current_spirits:
            continue
        enemies_at_old_spirit = [e for e in enemy_list if _near_any(e, [last_pos])]
        active_at_old_spirit = [e for e in enemies_at_old_spirit if _enemy_active(e)]
        if float(last_hp) < 0.80 or len(active_at_old_spirit) >= 2:
            _RECENT_LOSSES.append(int(now))
    _LAST_SPIRITS = current_spirits
    _RECENT_LOSSES[:] = [tick for tick in _RECENT_LOSSES if now - int(tick) <= _SPIRIT_LOSS_WINDOW_MS]

    st_active = [e for e in active_pressure if st_pos and _near_any(e, [st_pos])]
    spirit_active = [e for e in active_pressure if spirit_positions and _near_any(e, spirit_positions)]
    recent_losses = len(_RECENT_LOSSES)

    severity = 0
    reason = ""
    if len(st_active) >= 4 or len(spirit_active) >= 4 or (recent_losses >= 2 and len(all_close) >= 2):
        severity = 2
        reason = "repeated_spirit_loss" if recent_losses >= 2 else "heavy_st_spirit_pressure"
    elif len(st_active) >= 3 or len(spirit_active) >= 3:
        severity = 1
        reason = "st_spirit_pressure"

    pressure_candidates = active_pressure or (all_close if recent_losses >= 2 else [])
    if severity <= 0 or not pressure_candidates:
        if (
            int(_PRIORITY_TARGET_ID) > 0
            and int(_PRIORITY_TARGET_ID) in enemy_ids
            and now < int(_PRIORITY_UNTIL_MS)
        ):
            return int(_PRIORITY_TARGET_ID), int(_PRIORITY_BONUS), str(_PRIORITY_REASON)
        _PRIORITY_TARGET_ID = 0
        _PRIORITY_BONUS = 0
        _PRIORITY_REASON = ""
        return 0, 0, ""

    def sort_key(enemy):
        cluster = max(int(getattr(enemy, "adjacent_count", 1)), int(getattr(enemy, "predicted_adjacent_count", 1)))
        threat = int(getattr(enemy, "threat_score", 0))
        health = float(getattr(enemy, "health", 1.0))
        active = 1 if _enemy_active(enemy) else 0
        return (-cluster, -active, -threat, health, int(getattr(enemy, "agent_id", 0)))

    pressure_candidates.sort(key=sort_key)
    chosen = int(getattr(pressure_candidates[0], "agent_id", 0) or 0)
    if chosen <= 0:
        return 0, 0, ""
    _PRIORITY_TARGET_ID = int(chosen)
    _PRIORITY_UNTIL_MS = int(now) + _PRIORITY_HOLD_MS
    bonus = 3000 if severity >= 2 else 1500
    _PRIORITY_BONUS = int(bonus)
    _PRIORITY_REASON = str(reason)
    state = (int(chosen), int(severity), str(reason))
    if state != _LAST_LOG_STATE:
        _LAST_LOG_STATE = state
        _log(
            "ST_DEFENSE_PRIORITY_ACTIVE",
            target_id=int(chosen),
            severity=int(severity),
            reason=str(reason),
            st_attackers=len(st_active),
            spirit_attackers=len(spirit_active),
            recent_spirit_losses=int(recent_losses),
        )
    return int(chosen), int(bonus), str(reason)


def reset() -> None:
    global _LAST_SCAN_MS, _LAST_ST_LOOKUP_MS, _ST_AGENT_ID, _LAST_SPIRITS
    global _PRIORITY_TARGET_ID, _PRIORITY_UNTIL_MS, _PRIORITY_BONUS, _PRIORITY_REASON, _LAST_LOG_STATE
    _LAST_SCAN_MS = 0
    _LAST_ST_LOOKUP_MS = 0
    _ST_AGENT_ID = 0
    _LAST_SPIRITS = {}
    _RECENT_LOSSES.clear()
    _PRIORITY_TARGET_ID = 0
    _PRIORITY_UNTIL_MS = 0
    _PRIORITY_BONUS = 0
    _PRIORITY_REASON = ""
    _LAST_LOG_STATE = (0, 0, "")
