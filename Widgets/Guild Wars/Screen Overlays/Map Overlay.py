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

_commands_registered = False


def _chat_map(args, raw):
    """/map — toggle the Map Overlay widget on/off. /map toggle — switch mission map <-> compass."""
    sub = args[0].lower() if args else ""
    if sub == "toggle":
        # Switch the overlay MODE (mission map <-> compass).
        from Py4GWCoreLib.py4gwcorelib_src.map_overlay import toggle_mode

        toggle_mode()
    else:
        # Bare /map: toggle the WIDGET on/off.
        from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import get_widget_handler

        handler = get_widget_handler()
        if handler.is_widget_enabled(MODULE_NAME):
            handler.disable_widget(MODULE_NAME)
        else:
            handler.enable_widget(MODULE_NAME)


def _ensure_commands():
    global _commands_registered
    if _commands_registered:
        return
    try:
        from Py4GWCoreLib.ChatCommands import ChatCommands

        ChatCommands.register(
            "map", _chat_map,
            help="/map toggles the Map Overlay widget; /map toggle switches mission map <-> compass.",
        )
        _commands_registered = True
    except Exception as e:
        PySystem.Console.Log(MODULE_NAME, f"chat command register failed: {e}", PySystem.Console.MessageType.Error)


def draw() -> None:
    try:
        _ensure_commands()
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
