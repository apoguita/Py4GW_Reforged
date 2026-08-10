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
    or m.startswith("Py4GWCoreLib.py4gwcorelib_src.system_settings.name_obfuscation")
    or m.startswith("Py4GWCoreLib.py4gwcorelib_src.system_settings.agent_recolor")
    or m.startswith("Py4GWCoreLib.py4gwcorelib_src.system_settings.window_renamer")
    or m.startswith("Py4GWCoreLib.py4gwcorelib_src.system_settings.map_utilities")
    or m.startswith("Py4GWCoreLib.py4gwcorelib_src.system_settings.title_on_map_load")
]:
    del sys.modules[_name]

from Py4GWCoreLib.py4gwcorelib_src.system_settings import get_controller

OPTIONAL = False

MODULE_NAME = "System Settings"
MODULE_ICON = "Assets\\Textures\\Module_Icons\\Py4GW.png"

_controller = get_controller()
_inventory_controller = None
_applied = False


def draw() -> None:
    global _applied, _inventory_controller
    try:
        if not _applied:
            # Register the persisted options with the native side once (idempotent thereafter).
            _controller.apply_all_to_native()
            # Skillbar+ is a retired widget. Its complete runtime is booted here as a native,
            # profiled callback so no Guild Wars widget script is needed anymore.
            try:
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.skillbar_plus import get_controller as _sbp_get

                _sbp_get().register()
            except Exception as skillbar_error:
                PySystem.Console.Log(MODULE_NAME, "Skillbar+ boot failed: %s" % skillbar_error,
                                     PySystem.Console.MessageType.Error)
            try:
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.camera_smoothing import get_controller as _camera_get

                _camera_get().register()
            except Exception as camera_error:
                PySystem.Console.Log(MODULE_NAME, "Camera smoothing boot failed: %s" % camera_error,
                                     PySystem.Console.MessageType.Error)
            try:
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.window_renamer import get_controller as _renamer_get

                _renamer_get().register()
            except Exception as renamer_error:
                PySystem.Console.Log(MODULE_NAME, "Window Renamer boot failed: %s" % renamer_error,
                                     PySystem.Console.MessageType.Error)
            try:
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.map_utilities import get_controller as _map_utils_get

                _map_utils_get().register()
            except Exception as map_utils_error:
                PySystem.Console.Log(MODULE_NAME, "Map Utilities boot failed: %s" % map_utils_error,
                                     PySystem.Console.MessageType.Error)
            try:
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.title_on_map_load import get_controller as _title_get

                _title_get().register()
            except Exception as title_error:
                PySystem.Console.Log(MODULE_NAME, "Title On Map Load boot failed: %s" % title_error,
                                     PySystem.Console.MessageType.Error)
            # Also register the persisted name-obfuscation alias set (global/multi-account) at boot.
            try:
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.name_obfuscation import get_controller as _no_get

                _no_get().apply_to_native()
            except Exception:
                pass
            # Boot the agent-recolor engine: if this account has it enabled, register the
            # profiled data-phase callback and turn on the native hooks.
            try:
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.agent_recolor import get_controller as _ar_get

                _ar_get().boot()
            except Exception:
                pass
            # Boot the loot system. Each piece registers its own callback, so each is
            # independently driven and none rides on this widget's frame:
            #   Loot Filters      -- a data pass (map-change housekeeping)
            #   the quick access  -- its own DRAW pass, so the window cannot end up with no caller
            #   Recolor & Beacons -- a data pass (colour push) and a draw pass (beacons)
            # Booted separately so one failing still leaves the others running.
            try:
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters import LootFilters
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters import quick_access

                LootFilters().register()
                quick_access.register()
            except Exception as loot_error:
                PySystem.Console.Log(MODULE_NAME, "Loot Filters boot failed: %s" % loot_error,
                                     PySystem.Console.MessageType.Error)
            try:
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.recolor_beacons import RecolorBeacons

                RecolorBeacons().register()
            except Exception as mark_error:
                PySystem.Console.Log(MODULE_NAME, "Recolor & Beacons boot failed: %s" % mark_error,
                                     PySystem.Console.MessageType.Error)
            try:
                from Py4GWCoreLib.py4gwcorelib_src.system_settings.inventory import get_controller as _inventory_get

                _inventory_controller = _inventory_get()
                _inventory_controller.boot()
            except Exception as inventory_error:
                PySystem.Console.Log(MODULE_NAME, "Items migration boot failed: %s" % inventory_error,
                                     PySystem.Console.MessageType.Error)
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
