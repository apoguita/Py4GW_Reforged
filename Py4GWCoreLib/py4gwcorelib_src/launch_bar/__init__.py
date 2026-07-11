"""Launch Bar — a project-owned, configurable floating toolbar ("launchpad") UI.

This package is the from-scratch replacement for the presentation layer of the old
``LaunchSurface``. It follows a strict model / host / manager split:

- :mod:`.model` — pure data + grid geometry + collision. No ImGui, no Py4GW imports;
  importable and unit-testable from a plain interpreter.
- ``host`` / ``manager`` (added in later phases) — ImGui rendering and multi-bar
  coordination.

See ``docs/LaunchBar_ImGui_Implementation_Plan.md`` for the authoritative plan. This pass
is UI/layout only: what a tile *executes* is intentionally out of scope.
"""

from .model import BarColors
from .model import BarSide
from .model import LaunchBar
from .model import LaunchBarSet
from .model import Tile

__all__ = [
    "BarSide",
    "BarColors",
    "Tile",
    "LaunchBar",
    "LaunchBarSet",
]
