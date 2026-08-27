from __future__ import annotations

from Py4GWCoreLib import AgentArray, Profession, Range
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player

DEFAULT_FILTER_RANGE = Range.Spellcast.value
DEFAULT_CLUSTER_RADIUS = Range.Adjacent.value

def _distance(agent_id: int) -> float:
    try:
        from Py4GWCoreLib.Py4GWcorelib import Utils
        return float(Utils.Distance(Player.GetXY(), Agent.GetXY(int(agent_id))))
    except Exception:
        return 999999.0

def _valid(agent_id: int, filter_range: float = DEFAULT_FILTER_RANGE) -> bool:
    try:
        return int(agent_id or 0) > 0 and Agent.IsValid(int(agent_id)) and Agent.IsAlive(int(agent_id)) and _distance(int(agent_id)) <= float(filter_range)
    except Exception:
        return False

def enemy_professions(agent_id: int) -> tuple[int, int]:
    try:
        p, s = Agent.GetProfessions(int(agent_id))
        return int(getattr(p, "value", p) or 0), int(getattr(s, "value", s) or 0)
    except Exception:
        return (0, 0)

def is_support_or_caster(agent_id: int) -> bool:
    p, s = enemy_professions(agent_id)
    ids = {
        int(getattr(Profession.Monk, "value", Profession.Monk)),
        int(getattr(Profession.Ritualist, "value", Profession.Ritualist)),
        int(getattr(Profession.Mesmer, "value", Profession.Mesmer)),
        int(getattr(Profession.Elementalist, "value", Profession.Elementalist)),
        int(getattr(Profession.Necromancer, "value", Profession.Necromancer)),
    }
    return p in ids or s in ids

def count_adjacent_enemies(agent_id: int, radius: float = DEFAULT_CLUSTER_RADIUS) -> int:
    if not _valid(agent_id):
        return 0
    try:
        arr = AgentArray.GetEnemyArray()
        arr = AgentArray.Filter.ByDistance(arr, Agent.GetXY(int(agent_id)), float(radius))
        arr = AgentArray.Filter.ByCondition(arr, lambda eid: Agent.IsValid(eid) and Agent.IsAlive(eid))
        return len(arr or [])
    except Exception:
        return 0

def get_team_cluster_anchor(
    *,
    filter_range: float = DEFAULT_FILTER_RANGE,
    minimum_enemies: int = 2,
    consumer_role: str = "",
) -> int:
    """Only authoritative KeySoJway focus source.

    If the canonical cluster / cleanup resolver has no valid target, return 0.
    There is intentionally NO nearest-enemy or local deterministic fallback:
    an offensive consumer must wait rather than peel onto another packet.
    """
    anchor = 0
    mode = "none"
    try:
        from Py4GWCoreLib.Builds.Skills.CombatSense import (
            pick_special_priority_target,
            pick_locked_low_hp_finisher,
            pick_pressure_anchor,
            pick_single_target_anchor,
        )
        anchor = int(pick_special_priority_target(range_value=float(filter_range)) or 0)
        if anchor > 0:
            mode = "krummrinde"
        else:
            anchor = int(pick_locked_low_hp_finisher(
                range_value=float(filter_range), hp_threshold=0.10
            ) or 0)
            if anchor > 0:
                mode = "low_hp_finish"
            else:
                anchor = int(pick_pressure_anchor(
                    range_value=float(filter_range),
                    minimum_enemies=int(minimum_enemies),
                    player_target=0,
                ) or 0)
                if anchor > 0:
                    mode = "cluster"
                else:
                    anchor = int(pick_single_target_anchor(
                        range_value=float(filter_range),
                        player_target=0,
                        assignment_slot=None,
                        consumer_role=str(consumer_role or "party"),
                    ) or 0)
                    if anchor > 0:
                        mode = "cleanup"
    except Exception:
        anchor = 0
        mode = "resolver_error"

    if not _valid(anchor, filter_range):
        anchor = 0
        if mode != "resolver_error":
            mode = "none"

    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        members = get_team_cluster_members(anchor, filter_range=float(filter_range)) if anchor > 0 else []
        CombatDebug.log_event(
            "TEAM_FOCUS_DECISION",
            target_id=int(anchor),
            mode=str(mode),
            packet_size=int(len(members)),
            packet_members=",".join(str(int(x)) for x in sorted(members)),
            consumer_role=str(consumer_role or "party"),
            policy="hard_authoritative_no_local_fallback",
        )
    except Exception:
        pass
    return int(anchor)

def get_team_cluster_members(anchor_agent_id: int, *, radius: float = DEFAULT_CLUSTER_RADIUS, filter_range: float = DEFAULT_FILTER_RANGE) -> list[int]:
    if not _valid(anchor_agent_id, filter_range):
        return []
    try:
        arr = AgentArray.GetEnemyArray()
        arr = AgentArray.Filter.ByDistance(arr, Agent.GetXY(int(anchor_agent_id)), float(radius))
        arr = [int(eid) for eid in arr or [] if _valid(int(eid), filter_range)]
    except Exception:
        arr = [int(anchor_agent_id)]
    if int(anchor_agent_id) not in arr:
        arr.append(int(anchor_agent_id))
    return sorted(set(arr))

def pick_lamentation_target(*, cleanup_dangerous_only: bool = True) -> int:
    anchor = get_team_cluster_anchor()
    if anchor <= 0:
        return 0
    members = get_team_cluster_members(anchor)
    if len(members) <= 1 and cleanup_dangerous_only and not is_support_or_caster(anchor):
        return 0
    members.sort(key=lambda eid: (-count_adjacent_enemies(eid), -int(is_support_or_caster(eid)), _distance(eid), eid))
    return members[0] if members else anchor

def pick_unhexed_blood_bond_target() -> int:
    anchor = get_team_cluster_anchor()
    if anchor <= 0:
        return 0
    members = get_team_cluster_members(anchor) or [anchor]
    candidates = []
    for eid in members:
        try:
            if Agent.IsHexed(eid):
                continue
        except Exception:
            pass
        candidates.append(eid)
    if not candidates:
        return 0
    martial_ids = {
        int(getattr(Profession.Warrior, "value", Profession.Warrior)),
        int(getattr(Profession.Ranger, "value", Profession.Ranger)),
        int(getattr(Profession.Assassin, "value", Profession.Assassin)),
        int(getattr(Profession.Dervish, "value", Profession.Dervish)),
        int(getattr(Profession.Paragon, "value", Profession.Paragon)),
    }
    def rank(eid: int):
        p, _s = enemy_professions(eid)
        return (-int(is_support_or_caster(eid)), -int(p in martial_ids), -count_adjacent_enemies(eid), _distance(eid), eid)
    candidates.sort(key=rank)
    return candidates[0]
