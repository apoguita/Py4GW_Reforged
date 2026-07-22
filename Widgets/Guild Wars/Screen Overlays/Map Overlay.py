"""Map Overlay — unified agent + terrain overlay for the mission map OR the compass.

Thin widget host: all behaviour lives in the reusable core at
``Py4GWCoreLib.py4gwcorelib_src.map_overlay``. Pick a mode in the config; the two modes are
mutually exclusive. Replaces the legacy ``Mission Map +`` and ``Compass +`` widgets.
"""

import PySystem

from Py4GWCoreLib.py4gwcorelib_src.map_overlay import get_overlay

MODULE_NAME = "Map Overlay"
MODULE_ICON = "Textures\\Module_Icons\\Map Overlay.png"

# Use the shared process-wide instance so the launch-bar "toggle mode" command drives the very
# same overlay this widget renders (see map_overlay.get_overlay / toggle_mode).
_overlay = get_overlay()


def draw() -> None:
    try:
        _overlay.draw()
    except Exception as e:
        PySystem.Console.Log(MODULE_NAME, str(e), PySystem.Console.MessageType.Error)


def configure() -> None:
    try:
        _overlay.configure()
    except Exception as e:
        PySystem.Console.Log(MODULE_NAME, str(e), PySystem.Console.MessageType.Error)


def tooltip() -> None:
    _overlay.tooltip()


if __name__ == "__main__":
    draw()
