"""Beacons -- the beacon effect and its presets, as a standalone authoring module.

It owns the effect, the presets, their storage and their editor. **Recolor & Beacons consumes it**:
that feature picks a preset to use, it does not host this editor and does not own these presets.

The rule, now applied twice: an authoring surface stands on its own; a feature consumes what it
produces. Neither feature owns filters, profiles, beacon effects or presets.

A script may **consume** a preset; it may never author one. Presets are definitions, so -- unlike the
two feature configurations -- there is no live copy here for a script to dirty.
"""

from .effect import BeaconRenderer
from .effect import renderer
from .model import BASE_NAME
from .model import BEACON_GROUPS
from .model import EMITTER_GROUPS
from .model import BeaconPreset
from .model import Emitter
from .model import base_preset
from .model import make_emitter

__all__ = [
    "BeaconPreset", "Emitter", "BeaconRenderer",
    "base_preset", "make_emitter", "renderer",
    "BASE_NAME", "BEACON_GROUPS", "EMITTER_GROUPS",
]
