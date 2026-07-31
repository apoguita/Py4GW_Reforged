"""Where the party has physically been, kept out to compass range.

The radial scan can only see as far as a straight probe stays on the mesh, which
caps a retreat at about a spellcast and cannot see around a corner at all. A
party backing out of a bad fight usually needs to go further than that, and the
way it came is the only long path that is walkable by construction and costs
nothing to find.

Budgeted by DISTANCE, not by point count. The guarantee that matters is "at
least compass range of history", and a point cap quietly becomes a shorter
guarantee whenever the party happens to move in small steps.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from dataclasses import field

from Py4GWCoreLib import Range


@dataclass(slots=True)
class BreadcrumbConfig:
    # Compass range: a retreat has to be able to leave the fight entirely, and
    # anything shorter caps how far back the formation can be pulled.
    max_path_length: float = float(Range.Compass.value)
    # Standing still must not fill the buffer with near-identical points, which
    # would make the lookback terminate a few units behind the party.
    min_sample_distance: float = 120.0
    # A jump beyond this is a map change or a teleport, not walking. Everything
    # recorded belongs to a place the party is no longer in.
    max_step_distance: float = 2000.0


BREADCRUMB_CFG = BreadcrumbConfig()


@dataclass(slots=True)
class Breadcrumbs:
    # Oldest first, newest last.
    points: list[tuple[float, float]] = field(default_factory=list)

    def clear(self) -> None:
        self.points.clear()


def path_length(points: list[tuple[float, float]]) -> float:
    return sum(
        math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]) for i in range(1, len(points))
    )


def sample_at(path: list[tuple[float, float]], distance: float) -> tuple[float, float]:
    """The point `distance` along the polyline, clamped to its far end."""
    if not path:
        return (0.0, 0.0)
    travelled = 0.0
    for index in range(1, len(path)):
        previous = path[index - 1]
        current = path[index]
        step = math.hypot(current[0] - previous[0], current[1] - previous[1])
        if step < 0.001:
            continue
        if (travelled + step) >= distance:
            scale = (distance - travelled) / step
            return (
                previous[0] + ((current[0] - previous[0]) * scale),
                previous[1] + ((current[1] - previous[1]) * scale),
            )
        travelled += step
    return path[-1]


def prune(trail: Breadcrumbs, cfg: BreadcrumbConfig) -> None:
    while len(trail.points) > 2 and path_length(trail.points) > cfg.max_path_length:
        trail.points.pop(0)


def sample(trail: Breadcrumbs, cfg: BreadcrumbConfig, party_xy: tuple[float, float]) -> None:
    x = float(party_xy[0])
    y = float(party_xy[1])

    if not trail.points:
        trail.points.append((x, y))
        return

    last_x, last_y = trail.points[-1]
    step = math.hypot(x - last_x, y - last_y)

    if step > cfg.max_step_distance:
        trail.clear()
        trail.points.append((x, y))
        return

    if step < cfg.min_sample_distance:
        return

    trail.points.append((x, y))
    prune(trail, cfg)


def nearest_index(trail: Breadcrumbs, party_xy: tuple[float, float]) -> int:
    best = 0
    best_distance = float("inf")
    for index, (x, y) in enumerate(trail.points):
        distance = math.hypot(x - party_xy[0], y - party_xy[1])
        if distance < best_distance:
            best_distance = distance
            best = index
    return best


def path_back(
    trail: Breadcrumbs,
    party_xy: tuple[float, float],
    wanted: float,
) -> list[tuple[float, float]]:
    """Polyline from the party back along its own footprints, up to `wanted`.

    Joins the trail at its NEAREST crumb and walks toward older ones, rather
    than starting from the newest. The newest crumb is wherever the party last
    was, which after any withdrawal is between it and the fight — walking from
    there marched the route forward into the enemies before it turned around,
    and the first step of a retreat followed it straight back in.

    Starts at the party itself so the route begins where everyone is standing:
    up to min_sample_distance of real movement is never recorded.
    """
    path = [(float(party_xy[0]), float(party_xy[1]))]
    if wanted <= 0.0 or not trail.points:
        return path

    travelled = 0.0
    for index in range(nearest_index(trail, party_xy), -1, -1):
        x, y = trail.points[index]
        previous = path[-1]
        step = math.hypot(float(x) - previous[0], float(y) - previous[1])
        if step < 0.001:
            continue
        if (travelled + step) >= wanted:
            scale = (wanted - travelled) / step
            path.append(
                (
                    previous[0] + ((float(x) - previous[0]) * scale),
                    previous[1] + ((float(y) - previous[1]) * scale),
                )
            )
            break
        travelled += step
        path.append((float(x), float(y)))
    return path
