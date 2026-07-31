"""Turning a wanted position into one a body can stand in AND walk to.

Standing and reaching are separate questions and the navmesh answers them with
separate calls. A point can sit squarely on the mesh and still be a ledge, a
balcony or the far side of a wall — on-mesh, and impossible to enter. Checking
only `contains` publishes those, and followers walk into geometry forever.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


class NavMeshLike(Protocol):
    def contains(self, x: float, y: float, margin: float) -> bool: ...

    def has_line_of_sight(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        margin: float,
        step_dist: float,
    ) -> bool: ...


@dataclass(slots=True)
class PlacementConfig:
    # Matches followpos_contains_margin: the inset that decides a position is
    # publishable should be the one that decides where it gets nudged to.
    margin: float = 20.0
    los_margin: float = 20.0
    # has_line_of_sight samples INTERIOR points only, so its 200u default does
    # nothing whatsoever on a hop shorter than that and steps clean over whole
    # walls on longer ones. 100 is what makes it a wall test rather than a
    # formality, and it is the cost knob: probes scale as distance / step.
    los_step: float = 100.0
    # How far a pin may be nudged before the formation it belongs to is a
    # fiction. Past the last ring the caller's own fallback is more honest.
    ring_radii: tuple[float, ...] = (100.0, 200.0, 300.0, 400.0)
    ring_samples: int = 8


PLACEMENT_CFG = PlacementConfig()


def standable(navmesh: NavMeshLike, point: tuple[float, float], cfg: PlacementConfig) -> bool:
    return bool(navmesh.contains(float(point[0]), float(point[1]), cfg.margin))


def walkable_from(
    navmesh: NavMeshLike,
    origin: tuple[float, float],
    point: tuple[float, float],
    cfg: PlacementConfig,
) -> bool:
    return bool(navmesh.has_line_of_sight(origin, point, cfg.los_margin, cfg.los_step))


def ring_points(cfg: PlacementConfig, centre: tuple[float, float]):
    """Rings outward, each rotated half a step off the last so successive rings
    do not resample the same bearings."""
    step = (2.0 * math.pi) / max(1, cfg.ring_samples)
    for index, radius in enumerate(cfg.ring_radii):
        offset = (step / 2.0) if (index % 2) else 0.0
        for sample in range(cfg.ring_samples):
            angle = offset + (sample * step)
            yield (centre[0] + (math.cos(angle) * radius), centre[1] + (math.sin(angle) * radius))


def resolve_placement(
    navmesh: NavMeshLike,
    desired: tuple[float, float],
    origin: tuple[float, float],
    cfg: PlacementConfig = PLACEMENT_CFG,
) -> tuple[float, float] | None:
    """Closest point to `desired` that is on the mesh AND reachable from `origin`.

    None when there is no such point, so callers fall back to their anchor. An
    earlier draft returned the best on-mesh-but-unreachable candidate here on
    the grounds that it matched what was published before the check existed —
    which is precisely the bug: a pin on a ledge across a chasm is on the mesh,
    and publishing it walks a follower into geometry until the fight ends.
    Standing on the anchor is worse formation and a better outcome.

    The cost is that an over-strict line of sight now collapses a slot onto the
    anchor instead of pathing it into a wall. That failure is visible on the
    overlay and self-corrects; the one it replaces does neither.
    """
    if standable(navmesh, desired, cfg) and walkable_from(navmesh, origin, desired, cfg):
        return (float(desired[0]), float(desired[1]))

    for point in ring_points(cfg, desired):
        if standable(navmesh, point, cfg) and walkable_from(navmesh, origin, point, cfg):
            return point

    return None
