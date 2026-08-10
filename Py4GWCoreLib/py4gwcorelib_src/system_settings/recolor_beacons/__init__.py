"""Recolor & Beacons -- the marking feature. Decides what is **highlighted**.

Standalone: it does not depend on Loot Filters and Loot Filters does not depend on it. Each owns its
own master switch, and neither can be switched off from the other's section.

It **consumes**: filters and profiles from the Loot Filter Factory, beacon presets from the Beacons
module. It authors neither.

``recolor_beacons`` is the settled module name. ``item_filters`` is reserved for the full-fledged mod
filter class and must not be used here.
"""

from .controller import BLANK_ARGB
from .controller import RecolorBeacons
from .model import MarkConfig

__all__ = ["RecolorBeacons", "MarkConfig", "BLANK_ARGB"]
