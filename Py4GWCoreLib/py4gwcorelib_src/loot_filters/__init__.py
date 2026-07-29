"""Loot Filters -- deciding what loot is wanted.

Standalone: it does not import Recolor & Beacons and does not need it enabled. The filters and
profiles it uses belong to the **Loot Filter Factory**, which it consumes; it owns neither.

Scope, deliberately narrow: this decides **what is wanted**. It never walks, targets, picks up, or
decides *when* looting is appropriate.
"""

from .controller import LootFilters
from .model import LootConfig

__all__ = ["LootConfig", "LootFilters"]
