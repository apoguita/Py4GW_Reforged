"""Launchpad host callback (moved out of Py4GW_widget_manager).

The launchpad (LaunchBar) is the widget-manager UI. It renders through its own
native Draw callback named "Launchpad" -- separate from the host -- so the
profiler attributes it to a "Launchpad" metric rather than folding it into the
host's per-frame work.

It is NOT a WidgetManager widget, but it opts into profiling the same way any
callback can: the render is routed through ProfilingRegistry.runcall_scope (so an
on-demand cProfile capture can time it), and the name is declared profilable via
ProfilingRegistry().register(). That is what lets tools like the System Monitor
offer a deep profile of the launchpad without treating it as a widget.
"""

import PyCallback

from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

LAUNCHPAD_CALLBACK_NAME = "Launchpad"

_registered = False


def _log(msg: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log(LAUNCHPAD_CALLBACK_NAME, msg, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


def _draw_launchpad() -> None:
    """Render the launchpad. When a capture is active (ProfilingRegistry.enabled),
    route the call through runcall_scope so the cProfile target registered for
    "Launchpad:draw" is hit; otherwise call it directly (no profiling overhead)."""
    try:
        from Py4GWCoreLib.py4gwcorelib_src.launch_bar import app
    except Exception as exc:
        _log("launchpad import error: %s" % exc)
        return

    reg = ProfilingRegistry()
    try:
        if reg.enabled:
            reg.runcall_scope("widgets", "%s:draw" % LAUNCHPAD_CALLBACK_NAME, app.main)
        else:
            app.main()
    except Exception as exc:
        _log("launchpad render error: %s" % exc)


def register_launchpad_once() -> None:
    """Register the launchpad Draw callback and declare it profilable, once.

    Idempotent across host resets (drops any stale registration first) and kept
    independent of the settings bootstrap -- the launchpad must render even if
    settings fail.
    """
    global _registered
    if _registered:
        return
    try:
        PyCallback.PyCallback.RemoveByName(LAUNCHPAD_CALLBACK_NAME)
        PyCallback.PyCallback.Register(
            LAUNCHPAD_CALLBACK_NAME,
            PyCallback.Phase.Update,
            _draw_launchpad,
            priority=99,
            context=PyCallback.Context.Draw,
        )
        ProfilingRegistry().register(LAUNCHPAD_CALLBACK_NAME)
        _registered = True
    except Exception as exc:
        _log("launchpad callback registration error (will retry): %s" % exc)
