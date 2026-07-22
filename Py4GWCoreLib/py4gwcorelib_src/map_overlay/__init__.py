"""Map Overlay — the unified, mode-switchable map overlay core.

A single overlay that draws agent markers, range rings, spirit auras, terrain and
interaction onto **either** the compass (rotating) **or** the mission-map (axis-aligned)
frame — exactly one mode active at a time. It is the from-scratch replacement for the two
near-duplicate widgets ``Compass +`` and ``Mission Map +``.

Layered like ``launch_bar``: :mod:`.model` is pure data + taxonomy (no ImGui, no live-game
imports); the render / projection / agent / interaction / persistence layers (added in later
passes) consume it. See ``docs/map_overlay_merge/`` for the design.
"""

from .host import MapOverlay
from .host import get_overlay
from .host import toggle_mode
from .model import CustomMarker
from .model import MarkerStyle
from .model import OverlayConfig
from .model import OverlayMode
from .model import Ring
from .model import SpiritCategory
from .model import SpiritInfo
from .model import SpiritRangeClass
from .model import classify_spirit

__all__ = [
    "MapOverlay",
    "get_overlay",
    "toggle_mode",
    "OverlayMode",
    "OverlayConfig",
    "MarkerStyle",
    "Ring",
    "CustomMarker",
    "SpiritInfo",
    "SpiritCategory",
    "SpiritRangeClass",
    "classify_spirit",
]
