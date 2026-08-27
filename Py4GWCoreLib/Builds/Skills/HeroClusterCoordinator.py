"""Silent shared target coordinator for owned Guild Wars heroes.

No visible party call-target is sent. Dedicated hero controllers import
:func:`get_shared_cluster_anchor` and share the same execution/cluster anchor
inside the local Reforged process. Native-only unsupported heroes remain under
the normal Guild Wars AI and are intentionally not force-targeted.
"""
from __future__ import annotations

from Py4GWCoreLib import Agent, AgentArray, Map, Party, Player, Range, Routines, Utils

_CAST_RANGE = float(Range.Spellcast.value)
_SCAN_INTERVAL_MS = 250
_ANCHOR_HOLD_MS = 2600
_GLOBAL_ANCHOR_MAX_AGE_MS = 3200

_LAST_SCAN_MS = 0
_LAST_TARGET_ID = 0
_GLOBAL_ANCHOR_ID = 0
_GLOBAL_ANCHOR_TICK = 0
_RUNTIME_LOGGED = False
_ANCHOR_CACHE: dict[int, tuple[int, int]] = {}


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


def _distance(a_id: int, b_id: int) -> float:
    try:
        return float(Utils.Distance(Agent.GetXY(int(a_id)), Agent.GetXY(int(b_id))))
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


def _agent_name(agent_id: int) -> str:
    """Return an agent name through the Reforged-compatible API."""
    try:
        return str(Agent.GetNameByID(int(agent_id)) or "").strip()
    except Exception:
        return ""


def _valid_enemy(agent_id: int, *, origin_agent_id: int = 0, range_value: float = _CAST_RANGE) -> bool:
    try:
        aid = int(agent_id or 0)
        if aid <= 0 or not Agent.IsValid(aid) or not Agent.IsAlive(aid):
            return False
        origin = int(origin_agent_id or Player.GetAgentID() or 0)
        if origin > 0 and _distance(origin, aid) > float(range_value):
            return False
        return True
    except Exception:
        return False


def count_enemies_around(
    anchor_id: int,
    *,
    origin_agent_id: int = 0,
    radius: float = float(Range.Nearby.value),
    range_value: float = _CAST_RANGE,
) -> int:
    try:
        center = Agent.GetXY(int(anchor_id))
        return sum(
            1
            for enemy_id in AgentArray.GetEnemyArray() or []
            if _valid_enemy(int(enemy_id), origin_agent_id=origin_agent_id, range_value=range_value)
            and Utils.Distance(center, Agent.GetXY(int(enemy_id))) <= float(radius)
        )
    except Exception:
        return 0


def cluster_members(
    anchor_id: int,
    *,
    origin_agent_id: int = 0,
    radius: float = float(Range.Nearby.value),
    range_value: float = _CAST_RANGE,
) -> list[int]:
    try:
        center = Agent.GetXY(int(anchor_id))
    except Exception:
        return []
    members: list[int] = []
    for enemy_id in AgentArray.GetEnemyArray() or []:
        enemy_id = int(enemy_id)
        try:
            if not _valid_enemy(enemy_id, origin_agent_id=origin_agent_id, range_value=range_value):
                continue
            if Utils.Distance(center, Agent.GetXY(enemy_id)) <= float(radius):
                members.append(enemy_id)
        except Exception:
            continue
    members.sort(key=lambda enemy_id: (_health(enemy_id), enemy_id))
    return members



_ELITE_PRIORITY_TARGET_NAMES = ("twisted bark", "krummrinde", "crooked bark")

def _elite_priority_target(*, origin_agent_id: int = 0, range_value: float = _CAST_RANGE) -> int:
    """Hard-prioritize Urgoz room objects such as Twisted Bark/Krummrinde."""
    origin = int(origin_agent_id or Player.GetAgentID() or 0)
    matches: list[int] = []
    for enemy_id in AgentArray.GetEnemyArray() or []:
        enemy_id = int(enemy_id)
        if not _valid_enemy(enemy_id, origin_agent_id=origin, range_value=range_value):
            continue
        try:
            name = _agent_name(enemy_id).lower()
        except Exception:
            name = ''
        if any(token in name for token in _ELITE_PRIORITY_TARGET_NAMES):
            matches.append(enemy_id)
    matches.sort(key=lambda enemy_id: (_health(enemy_id), _distance(origin, enemy_id), enemy_id))
    return int(matches[0]) if matches else 0

def get_shared_cluster_anchor(
    *,
    origin_agent_id: int = 0,
    range_value: float = _CAST_RANGE,
    minimum_enemies: int = 2,
    prefer_execution: bool = True,
) -> int:
    """Heroes obey the exact same team target. No local fallback is permitted."""
    try:
        from Py4GWCoreLib.Builds.Skills.TeamCombatFocus import get_team_cluster_anchor
        shared = int(get_team_cluster_anchor(
            filter_range=float(range_value),
            minimum_enemies=int(minimum_enemies),
            consumer_role="hero",
        ) or 0)
        if shared > 0 and _valid_enemy(
            shared,
            origin_agent_id=int(origin_agent_id or Player.GetAgentID() or 0),
            range_value=float(range_value),
        ):
            return int(shared)
    except Exception:
        pass
    return 0

def run(*, enabled: bool = True) -> None:
    """Maintain a silent shared anchor for the local account's hero controllers.

    No ``Player.CallTarget`` is used.  This deliberately removes the visible
    target ping and prevents party-target changes from competing with manual
    mouse/keyboard control.
    """
    global _LAST_SCAN_MS, _LAST_TARGET_ID, _GLOBAL_ANCHOR_ID, _GLOBAL_ANCHOR_TICK, _RUNTIME_LOGGED
    if not enabled:
        _LAST_TARGET_ID = 0
        _GLOBAL_ANCHOR_ID = 0
        _GLOBAL_ANCHOR_TICK = 0
        return
    try:
        if not Map.IsExplorable() or not Party.IsPartyLoaded():
            return
        if int(Player.GetAgentID() or 0) != int(Party.GetPartyLeaderID() or 0):
            return
        hero_count = len(list(Party.GetHeroes() or []))
    except Exception:
        return
    if hero_count <= 0:
        return

    now_ms = _now_ms()
    if now_ms - int(_LAST_SCAN_MS) < int(_SCAN_INTERVAL_MS):
        return
    _LAST_SCAN_MS = int(now_ms)
    if not _RUNTIME_LOGGED:
        _RUNTIME_LOGGED = True
        _log('HERO_CLUSTER_SILENT_COORDINATOR_ACTIVE', hero_count=int(hero_count))

    anchor_id = int(get_shared_cluster_anchor(
        origin_agent_id=int(Player.GetAgentID() or 0),
        range_value=_CAST_RANGE,
    ) or 0)
    if anchor_id <= 0:
        _GLOBAL_ANCHOR_ID = 0
        _GLOBAL_ANCHOR_TICK = int(now_ms)
        return

    changed = int(anchor_id) != int(_GLOBAL_ANCHOR_ID)
    _GLOBAL_ANCHOR_ID = int(anchor_id)
    _GLOBAL_ANCHOR_TICK = int(now_ms)
    if changed:
        _LAST_TARGET_ID = int(anchor_id)
        _log(
            'HERO_CLUSTER_ANCHOR_UPDATED',
            target_id=int(anchor_id),
            target=_agent_name(int(anchor_id)) or '?',
            nearby=int(count_enemies_around(
                anchor_id,
                origin_agent_id=int(Player.GetAgentID() or 0),
            )),
            hero_count=int(hero_count),
        )

