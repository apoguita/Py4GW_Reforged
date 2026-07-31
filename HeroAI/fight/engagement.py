"""Is the party actually FIGHTING — distinct from having enemies nearby.

InAggro is proximity: an enemy within 1012-1498u of anyone. You can walk past a
camp at 1400u, be "in aggro" the whole way, and never exchange a blow. Dropping
a fight zone on that would stop the party dead in open ground.

Engagement is blows being exchanged: something hostile is attacking or casting
inside a much tighter radius, or party health is going down.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from dataclasses import field

from Py4GWCoreLib import Agent
from Py4GWCoreLib import Range


@dataclass(slots=True)
class EngagementConfig:
    # Only enemies this close count. Deliberately far tighter than the aggro
    # scan radius — that is the whole point of the distinction.
    engage_radius: float = float(Range.Earshot.value)
    # Hold the zone through gaps between waves and through the moment every
    # enemy is briefly out of scan range. Without this the zone tears down mid
    # fight, the all-flag clears, and followers snap back to chasing the leader.
    disengage_hold_ms: int = 3000
    # Health loss across the party that counts as being under fire even when no
    # enemy is legible as attacking (ranged, spirits, degen).
    health_drop_fraction: float = 0.02


ENGAGEMENT_CFG = EngagementConfig()


@dataclass(slots=True)
class EngagementState:
    engaged: bool = False
    last_engaged_ms: int = 0
    last_party_health: dict[int, float] = field(default_factory=dict)

    def reset(self) -> None:
        self.engaged = False
        self.last_engaged_ms = 0
        self.last_party_health.clear()


def hostile_pressure(
    cfg: EngagementConfig,
    leader_xy: tuple[float, float],
    enemy_ids: list[int],
) -> bool:
    """An enemy close by that is actually swinging or casting."""
    for agent_id in enemy_ids:
        try:
            if not Agent.IsValid(agent_id) or Agent.IsDead(agent_id):
                continue
            x, y = Agent.GetXY(agent_id)
            if math.hypot(float(x) - leader_xy[0], float(y) - leader_xy[1]) > cfg.engage_radius:
                continue
            if Agent.IsAggressive(agent_id) or Agent.IsInCombatStance(agent_id):
                return True
        except Exception:
            continue
    return False


def party_under_fire(
    state: EngagementState,
    cfg: EngagementConfig,
    party_health: dict[int, float],
) -> bool:
    """Health going down anywhere in the party. Catches ranged pressure, degen
    and spirits, where nothing nearby ever reads as attacking."""
    under_fire = False
    for party_position, fraction in party_health.items():
        previous = state.last_party_health.get(party_position)
        if previous is not None and (previous - fraction) >= cfg.health_drop_fraction:
            under_fire = True
            break
    state.last_party_health = dict(party_health)
    return under_fire


def party_offensive(party_target_ids: dict[int, int], enemy_ids: list[int]) -> bool:
    """Someone in the party has an enemy targeted and is acting on it — we
    started this fight even if nothing has hit back yet."""
    enemy_set = set(int(e) for e in enemy_ids)
    for agent_id in party_target_ids.values():
        target = int(agent_id)
        if target and target in enemy_set:
            return True
    return False


def update_engagement(
    state: EngagementState,
    cfg: EngagementConfig,
    leader_xy: tuple[float, float],
    enemy_ids: list[int],
    party_health: dict[int, float],
    party_target_ids: dict[int, int],
    now_ms: int,
) -> bool:
    """Latched: rises instantly, falls only after disengage_hold_ms of quiet.

    Asymmetric on purpose — being late to form up costs a second, while tearing
    the zone down early drops everyone back into follow mid-fight.
    """
    active_now = (
        hostile_pressure(cfg, leader_xy, enemy_ids)
        or party_under_fire(state, cfg, party_health)
        or party_offensive(party_target_ids, enemy_ids)
    )

    if active_now:
        state.engaged = True
        state.last_engaged_ms = now_ms
        return True

    if state.engaged and (now_ms - state.last_engaged_ms) < cfg.disengage_hold_ms:
        return True

    state.engaged = False
    return False
