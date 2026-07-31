"""Where the party would run if this fight goes wrong.

Plotted while a zone is active and published for the overlay. NOTHING consumes
it — the pin is placed by zone.py exactly as before. This is the map you want to
already have when the formation ends up backed into geometry, not a second
opinion about where to stand.

Two sources. A radial navmesh scan over the full circle handles "where can we go
from right here" — deliberately not restricted to the retreat arc, because
against a wall the only opening is often forward or along it. But a straight
probe reaches about a spellcast and cannot see round a corner, which caps how
far the formation can be pulled back.

So the party's own footprints are the second source, and the long one: walkable
by construction, correct about doglegs, and budgeted out to compass range. That
is what makes a genuinely long retreat possible instead of a 1200u shuffle.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from enum import IntEnum

from Py4GWCoreLib import Range

from .breadcrumbs import Breadcrumbs
from .breadcrumbs import path_back
from .breadcrumbs import path_length
from .breadcrumbs import sample_at

# "Can a body stand here." Optional: with no probe the radial half is skipped
# and the backtrack stands alone — footprints need no probing.
TerrainProbe = Callable[[tuple[float, float]], bool]


@dataclass(slots=True)
class EscapeConfig:
    # How far a straight probe is worth trusting. Not a limit on the retreat --
    # the backtrack below is what carries a long one.
    max_route_distance: float = float(Range.Spellcast.value)
    # The backtrack is walked ground, so it is bounded by how much history is
    # kept rather than by how far a ray stays legible.
    max_backtrack_distance: float = float(Range.Compass.value)
    # Shorter than this is a shuffle, not an escape.
    min_useful_distance: float = 400.0

    ray_step: float = math.radians(15.0)
    probe_step: float = 160.0

    open_weight: float = 1.0
    clear_weight: float = 0.9
    # Straight back, away from the pack. Weighted like clear_weight rather than
    # like home, because a route that heads past the enemies to reach open
    # ground is not an escape however open that ground is — pulling the party
    # backwards off a bad fight beats finding the roomiest place to have it.
    #
    # It does not veto forward: a fully walled backward direction falls under
    # min_useful_distance and drops out, which is what still lets the party
    # break out sideways or through when it is genuinely pinned.
    away_weight: float = 0.9
    # Below this the enemy centroid sits inside the party and the bearing away
    # from it is noise. Same failure, same threshold, as ZoneConfig's
    # min_facing_baseline.
    min_away_baseline: float = float(Range.Area.value)
    # Intentionally well below clear_weight, because weights alone do not order
    # these terms — weight times how much the term actually VARIES does. Home
    # alignment swings the full 0..1 across a circle of candidates while clear
    # rarely swings more than half that, so a home weight anywhere near clear's
    # lets "roughly homeward" outvote "not full of enemies", and the route plots
    # a diagonal that skirts the pack blocking the way back instead of the empty
    # ground behind us.
    home_weight: float = 0.35
    # Two corridors 15 deg apart score almost identically, so without this the
    # drawn route spins on every refresh and cannot be read at a glance.
    sticky_weight: float = 0.45
    # Walked ground is evidence; a probed ray is an inference. The bonus is what
    # makes the backtrack the default answer and the scan the fallback.
    trail_confidence: float = 0.25

    # Enemy influence on a sampled point falls linearly to zero at this range.
    # Spellcast rather than something tighter: the question a route has to
    # answer is "will we still be in trouble when we get there", and a caster
    # reaches this far. At 900 a route ending just outside a five-man pack
    # scored as perfectly clean.
    threat_radius: float = float(Range.Spellcast.value)
    threat_saturation: float = 3.0

    replot_interval_ms: int = 1000


ESCAPE_CFG = EscapeConfig()


class EscapeSource(IntEnum):
    RADIAL = 1
    BACKTRACK = 2


@dataclass(slots=True)
class EscapeRoute:
    origin: tuple[float, float]
    axis: float
    waypoint: tuple[float, float]
    distance: float
    score: float
    source: EscapeSource = EscapeSource.RADIAL
    # Full polyline. Two points for a radial ray, a dogleg for a backtrack. The
    # give-ground step walks this, so it is load-bearing, not decoration.
    path: list[tuple[float, float]] = field(default_factory=list)


@dataclass(slots=True)
class EscapeState:
    route: EscapeRoute | None = None
    last_plot_ms: int = 0
    # A plot ran and found nothing worth calling a route. Distinct from "no plot
    # yet" and from "no terrain data", which a null route alone cannot say.
    boxed_in: bool = False
    terrain_known: bool = False

    def clear(self) -> None:
        self.route = None
        self.last_plot_ms = 0
        self.boxed_in = False
        self.terrain_known = False


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def alignment(axis: float, reference: float) -> float:
    return (1.0 + math.cos(axis - reference)) / 2.0


def home_axis(party_xy: tuple[float, float], safe_xy: tuple[float, float] | None) -> float | None:
    if safe_xy is None:
        return None
    dx = safe_xy[0] - party_xy[0]
    dy = safe_xy[1] - party_xy[1]
    if math.hypot(dx, dy) < 0.001:
        return None
    return math.atan2(dy, dx)


def away_axis(
    cfg: EscapeConfig,
    party_xy: tuple[float, float],
    enemy_positions: list[tuple[float, float]],
) -> float | None:
    """Bearing straight away from the enemy mass, or None when they are on top
    of the party and there is no such thing."""
    if not enemy_positions:
        return None
    centre_x = sum(p[0] for p in enemy_positions) / len(enemy_positions)
    centre_y = sum(p[1] for p in enemy_positions) / len(enemy_positions)
    dx = party_xy[0] - centre_x
    dy = party_xy[1] - centre_y
    if math.hypot(dx, dy) < cfg.min_away_baseline:
        return None
    return math.atan2(dy, dx)


def threat_at(cfg: EscapeConfig, point: tuple[float, float], enemy_positions: list[tuple[float, float]]) -> float:
    total = 0.0
    for x, y in enemy_positions:
        distance = math.hypot(x - point[0], y - point[1])
        if distance < cfg.threat_radius:
            total += 1.0 - (distance / cfg.threat_radius)
    return total


def outer_threat(
    cfg: EscapeConfig,
    path: list[tuple[float, float]],
    enemy_positions: list[tuple[float, float]],
) -> float:
    """Mean threat over the far half of the route.

    Only the far half, because enemies standing on the party are equally close
    to every candidate route: they add the same constant to all of them and
    discriminate nothing. Where the route ENDS is the whole question.

    Takes the polyline rather than a bearing so a dogleg backtrack is sampled
    where it actually goes, not where its straight-line bearing would put it.
    """
    length = path_length(path)
    if length < 0.001:
        return threat_at(cfg, path[-1], enemy_positions)
    fractions = (0.5, 0.75, 1.0)
    return sum(threat_at(cfg, sample_at(path, length * f), enemy_positions) for f in fractions) / len(fractions)


def route_score(
    cfg: EscapeConfig,
    path: list[tuple[float, float]],
    axis: float,
    open_fraction: float,
    home: float | None,
    away: float | None,
    enemy_positions: list[tuple[float, float]],
    previous_axis: float | None,
) -> float:
    clear = 1.0 - clamp01(outer_threat(cfg, path, enemy_positions) / cfg.threat_saturation)
    open_fraction = clamp01(open_fraction)
    total = (cfg.open_weight * open_fraction) + (cfg.clear_weight * clear)
    weights = cfg.open_weight + cfg.clear_weight
    total += cfg.away_weight * (alignment(axis, away) if away is not None else 0.5)
    weights += cfg.away_weight
    # Neutral rather than absent when there is no safe spot: dropping the term
    # would rescale every other score and make runs incomparable across the
    # moment one appears.
    total += cfg.home_weight * (alignment(axis, home) if home is not None else 0.5)
    weights += cfg.home_weight
    if previous_axis is not None:
        total += cfg.sticky_weight * alignment(axis, previous_axis)
        weights += cfg.sticky_weight
    return total / weights


def open_distance(
    cfg: EscapeConfig,
    probe: TerrainProbe,
    origin: tuple[float, float],
    axis: float,
    wanted: float,
) -> float:
    cos_axis = math.cos(axis)
    sin_axis = math.sin(axis)
    reached = 0.0
    travelled = cfg.probe_step
    while travelled < wanted:
        if not probe((origin[0] + (cos_axis * travelled), origin[1] + (sin_axis * travelled))):
            return reached
        reached = travelled
        travelled += cfg.probe_step
    if not probe((origin[0] + (cos_axis * wanted), origin[1] + (sin_axis * wanted))):
        return reached
    return wanted


def plot_escape(
    state: EscapeState,
    cfg: EscapeConfig,
    party_xy: tuple[float, float],
    enemy_positions: list[tuple[float, float]],
    safe_xy: tuple[float, float] | None,
    now_ms: int,
    probe: TerrainProbe | None = None,
    trail: Breadcrumbs | None = None,
) -> EscapeRoute | None:
    if state.last_plot_ms and (now_ms - state.last_plot_ms) < cfg.replot_interval_ms:
        return state.route
    state.last_plot_ms = now_ms
    state.terrain_known = probe is not None

    home = home_axis(party_xy, safe_xy)
    away = away_axis(cfg, party_xy, enemy_positions)
    previous_axis = state.route.axis if state.route is not None else None
    best: EscapeRoute | None = None

    origin = (float(party_xy[0]), float(party_xy[1]))

    # The long option. Needs no probe -- the party walked every metre of it --
    # so it is also the only route available when the navmesh is unusable.
    if trail is not None:
        crumbs = path_back(trail, party_xy, cfg.max_backtrack_distance)
        length = path_length(crumbs)
        if length >= cfg.min_useful_distance:
            endpoint = crumbs[-1]
            axis = math.atan2(endpoint[1] - origin[1], endpoint[0] - origin[0])
            score = (
                route_score(
                    cfg,
                    crumbs,
                    axis,
                    length / cfg.max_backtrack_distance,
                    home,
                    away,
                    enemy_positions,
                    previous_axis,
                )
                + cfg.trail_confidence
            )
            best = EscapeRoute(origin, axis, endpoint, length, score, EscapeSource.BACKTRACK, crumbs)

    if probe is not None:
        rays = max(1, int(round((2.0 * math.pi) / cfg.ray_step)))
        for index in range(rays):
            axis = index * cfg.ray_step
            reach = open_distance(cfg, probe, party_xy, axis, cfg.max_route_distance)
            if reach < cfg.min_useful_distance:
                continue
            waypoint = (
                origin[0] + (math.cos(axis) * reach),
                origin[1] + (math.sin(axis) * reach),
            )
            ray = [origin, waypoint]
            score = route_score(
                cfg, ray, axis, reach / cfg.max_route_distance, home, away, enemy_positions, previous_axis
            )
            if best is None or score > best.score:
                best = EscapeRoute(origin, axis, waypoint, reach, score, EscapeSource.RADIAL, ray)

    state.route = best
    # Only a search that actually had terrain to search can report being boxed
    # in. Without a probe the backtrack may still have answered, and if it did
    # not, the honest report is "no data" — which the caller words differently.
    state.boxed_in = best is None and probe is not None
    return best
