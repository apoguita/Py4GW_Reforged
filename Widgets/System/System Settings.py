"""System Settings — always-on System widget that persists & applies library-wide options.

Thin host: all behaviour lives in ``Py4GWCoreLib.py4gwcorelib_src.system_settings``. As a System
widget it is non-optional (``OPTIONAL = False``) and runs every frame from startup, so it can
register the persisted options with the native side once at boot. The options window is hidden by
default and never shows just because the widget runs — it is toggled from the System launchpad's
undeletable cog button (launch-bar action ``"system_settings"``).

Passive on import: building the shared controller only loads persisted values; nothing renders and
no native call happens until ``draw()`` runs on the frame loop.
"""

import sys

import PyImGui
import PySystem

# Dev-reload aid: the system_settings and name_obfuscation implementations are library modules
# (under Py4GWCoreLib), so Python caches them in sys.modules — a widget reload re-runs THIS file but
# would otherwise keep the stale cached package code AND the controller's cached window. Purge them
# so each reload rebuilds from current source. (Mirrors LaunchBar._boot's purge.)
for _name in [
    m for m in list(sys.modules)
    if m.startswith("Py4GWCoreLib.py4gwcorelib_src.system_settings")
    or m.startswith("Py4GWCoreLib.py4gwcorelib_src.name_obfuscation")
    or m.startswith("Py4GWCoreLib.py4gwcorelib_src.agent_recolor")
]:
    del sys.modules[_name]

from Py4GWCoreLib.py4gwcorelib_src.system_settings import get_controller

OPTIONAL = False

MODULE_NAME = "System Settings"
MODULE_ICON = "Textures\\Module_Icons\\Py4GW.png"

_controller = get_controller()
_applied = False


def draw() -> None:
    global _applied
    try:
        if not _applied:
            # Register the persisted options with the native side once (idempotent thereafter).
            _controller.apply_all_to_native()
            # Also register the persisted name-obfuscation alias set (global/multi-account) at boot.
            try:
                from Py4GWCoreLib.py4gwcorelib_src.name_obfuscation import get_controller as _no_get

                _no_get().apply_to_native()
            except Exception:
                pass
            # Boot the agent-recolor engine: if this account has it enabled, register the
            # profiled data-phase callback and turn on the native hooks.
            try:
                from Py4GWCoreLib.py4gwcorelib_src.agent_recolor import get_controller as _ar_get

                _ar_get().boot()
            except Exception:
                pass
            # Register the chat-command framework built-ins (/help) once, now that native is up.
            try:
                from Py4GWCoreLib.ChatCommands import ChatCommands

                ChatCommands.boot()
            except Exception:
                pass
            _applied = True
        # Renders the options window only while it is toggled open (via the launchpad cog).
        _controller.draw()
    except Exception as e:
        PySystem.Console.Log(MODULE_NAME, str(e), PySystem.Console.MessageType.Error)


def tooltip() -> None:
    PyImGui.begin_tooltip()
    PyImGui.text_colored("System Settings", (1.0, 0.78, 0.39, 1.0))
    PyImGui.separator()
    PyImGui.text("Configure & persist library-wide options (native game-event listeners).")
    PyImGui.text("Applied at startup; toggle the window from the System bar's cog button.")
    PyImGui.end_tooltip()


if __name__ == "__main__":
    draw()
