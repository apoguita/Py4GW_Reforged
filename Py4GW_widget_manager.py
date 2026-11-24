"""Py4GW widget host — the always-on script the C++ DLL runs (`g_widget_host`).

The DLL calls this module's ``main()`` **every draw frame** (via ExecuteDraw, which runs both
``draw()`` and ``main()``). It has two jobs now:

  1. **Bootstrap once** — resolve the manager settings key, discover widgets, apply the saved
     enabled-state (forcing System widgets on). Widgets then run via their C++ PyCallbacks.
  2. **Render the launchpad every frame** — the launchpad (LaunchBar) is the widget-manager UI,
     and this always-on host is where it must be drawn (HEAD drew the old WM UI here). Without
     this the launchpad has no host and nothing appears on screen.

Both are made bulletproof: a missing/broken settings file must never stop the launchpad — the
cornerstone UI — from rendering.
"""

import os

import PyImGui


MODULE_NAME = "Widget Manager"

Settings = None
WidgetHandler = None
register_launchpad_once = None
widget_manager = None

INI_KEY = ""
INI_PATH = "Widgets/WidgetManager"
INI_FILENAME = "WidgetManager.ini"


def _log(msg: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log(MODULE_NAME, msg, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


def get_widget_handler():
    """Return the shared handler while preserving the host's legacy import API."""

    if widget_manager is None and not _ensure_runtime():
        raise RuntimeError("Widget Manager is not ready: no ImGui context")
    return widget_manager


def _ensure_runtime() -> bool:
    """Bind the core widget runtime only after the native ImGui context exists."""

    global Settings, WidgetHandler, register_launchpad_once, widget_manager
    if widget_manager is not None:
        return True

    try:
        PyImGui.StyleConfig()
    except RuntimeError as exc:
        if "no imgui context" in str(exc).casefold():
            return False
        raise

    from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings as _Settings
    from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import WidgetHandler as _WidgetHandler
    from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import get_widget_handler as _get_widget_handler
    from Py4GWCoreLib.py4gwcorelib_src.launch_bar.launchpad import (
        register_launchpad_once as _register_launchpad_once,
    )

    Settings = _Settings
    WidgetHandler = _WidgetHandler
    register_launchpad_once = _register_launchpad_once
    widget_manager = _get_widget_handler()
    return True


def _bootstrap_once() -> None:
    """Resolve settings + discover widgets + apply saved state. Retries each frame until done."""

    global INI_KEY
    if INI_KEY:
        return
    if Settings is None or widget_manager is None:
        return
    try:
        if not os.path.exists(INI_PATH):
            os.makedirs(INI_PATH, exist_ok=True)

        cfg = Settings(f"{INI_PATH}/{INI_FILENAME}", "account")
        key = cfg.name
        if not key:
            return  # settings not ready yet — retry next frame (launchpad still renders below)

        # Order is load-bearing: MANAGER_INI_KEY must be set before discovery (it reads each
        # widget's saved-enabled state during load), then _apply_ini_configuration re-applies
        # and force-enables System widgets.
        INI_KEY = key
        widget_manager.MANAGER_INI_KEY = INI_KEY
        widget_manager.discover()
        widget_manager.enable_all = bool(cfg.get_bool("Configuration", "enable_all", True))
        widget_manager._apply_ini_configuration()
    except Exception as exc:
        _log("bootstrap error (will retry): %s" % exc)


def update():
    return  # widgets run via C++ callbacks; nothing on the update loop here


def draw():
    return  # nothing here; the launchpad renders via its own registered Draw callback


def main():
    """Register the launchpad and bootstrap once the draw context is ready."""

    if not _ensure_runtime():
        return
    get_widget_handler()
    assert register_launchpad_once is not None
    register_launchpad_once()
    _bootstrap_once()


if __name__ == "__main__":
    main()
