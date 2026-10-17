"""Loot Filters -- deciding what loot is wanted.

Standalone: it does not import Recolor & Beacons and does not need it enabled. The filters and
filter sets it uses belong to the **Loot Filter Factory**, which it consumes; it owns neither.

Scope, deliberately narrow: this decides **what is wanted**. It never walks, targets, picks up, or
decides *when* looting is appropriate.

Hot-reload note
---------------
Consumers intentionally import ``LootFilters`` from this package facade rather
than caching ``controller.LootFilters``.  The facade resolves the controller
class at call time so a Py4GW hot reload cannot leave long-lived modules such as
BT.Items, Headless HeroAI or Messaging bound to an obsolete singleton class.
"""

from .model import LootConfig


def LootFilters():
    """Return the current live LootFilters singleton.

    Resolve the controller class on every call.  Py4GW can hot-reload
    ``controller.py`` while consumers remain loaded; caching the class here
    would create parallel singleton generations with different ``live`` state.
    """
    from .controller import LootFilters as ControllerLootFilters

    return ControllerLootFilters()


__all__ = ["LootConfig", "LootFilters"]
