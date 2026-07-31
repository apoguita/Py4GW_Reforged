"""The last place the party was genuinely safe, latched to a single point.

Replaces a 32-point breadcrumb trail. The escape destination was never really
"900u back along wherever we wandered" — a lookback like that can double back on
itself, cut the corner of a room the party only skirted, or land on ground that
was already inside an aggro bubble. One remembered point that was provably quiet
is smaller and more truthful.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True)
class SafeSpotConfig:
    # Closer to the fight than this and the direction it implies is noise rather
    # than an approach. Same threshold, for the same reason, as the lookback it
    # replaces.
    min_usable_distance: float = 300.0
    # A jump beyond this is a map change or a teleport, not walking, so the
    # remembered point belongs to a place the party is no longer standing in.
    max_step_distance: float = 2000.0


SAFE_CFG = SafeSpotConfig()


@dataclass(slots=True)
class SafeSpot:
    xy: tuple[float, float] | None = None

    def clear(self) -> None:
        self.xy = None


def update_safe_spot(
    spot: SafeSpot,
    cfg: SafeSpotConfig,
    party_xy: tuple[float, float],
    party_in_aggro: bool,
) -> None:
    """Follow the party while nothing is near them; freeze on first contact.

    Gated on aggro, not on engagement. Engagement only rises once blows are
    being exchanged, and a party can walk most of the way through an aggro
    bubble before that happens — the spot it would remember is one nobody was
    ever safe in.

    The staleness check runs even while in aggro, so zoning straight into a
    fight discards the point from the previous map instead of pointing the
    escape at it.
    """
    if spot.xy is not None:
        drift = math.hypot(party_xy[0] - spot.xy[0], party_xy[1] - spot.xy[1])
        if drift > cfg.max_step_distance:
            spot.clear()

    if party_in_aggro:
        return
    spot.xy = (float(party_xy[0]), float(party_xy[1]))


def approach_from(
    spot: SafeSpot,
    cfg: SafeSpotConfig,
    reference_xy: tuple[float, float],
) -> tuple[float, float] | None:
    """The safe spot, or None when it sits too close to `reference` to describe a
    direction at all. Callers must have a fallback — same contract as before."""
    if spot.xy is None:
        return None
    if math.hypot(reference_xy[0] - spot.xy[0], reference_xy[1] - spot.xy[1]) < cfg.min_usable_distance:
        return None
    return spot.xy
