"""Launch Bar — project entry point (root script).

Passive on import: importing this module only defines functions; nothing renders or touches the
game until the Py4GW launcher calls :func:`main` (or :func:`draw`) once per frame.

This is the new, from-scratch configurable floating toolbar that replaces the old
``LaunchSurface`` UI. This pass is UI/layout only — tiles are placeholders and do not execute
anything yet. See ``docs/LaunchBar_ImGui_Implementation_Plan.md``.
"""

_manager = None
_boot_failed = False


def _now_ms() -> float:
    try:
        import PySystem

        return float(PySystem.get_tick_count64())
    except Exception:
        return 0.0


def _ensure_system_bar(bar_set) -> None:
    """Guarantee a non-deletable System bar carrying the widget-browser button exists.

    The System bar is persisted like any other, so on a restored state it's already present;
    this only fabricates one on first run or if a saved state somehow lacks it.
    """

    if any(b.system for b in bar_set.bars):
        return
    sysbar = bar_set.add(name="System", x=340.0, y=120.0)
    sysbar.system = True
    browser_tile = sysbar.add_tile(1, 1)
    if browser_tile is not None:
        browser_tile.action = "browser"
        browser_tile.name = "Widgets"
        browser_tile.deletable = False


def _boot() -> None:
    """Create the manager + restore/seed bars once. Idempotent (the launcher calls per frame)."""

    global _manager, _boot_failed
    if _manager is not None or _boot_failed:
        return
    try:
        # Live-iteration aid: these modules live under Py4GWCoreLib, so a widget reload would
        # otherwise reuse the cached (stale) code. Purge them so each reload picks up edits.
        import sys

        for _name in [m for m in list(sys.modules) if m.startswith("Py4GWCoreLib.py4gwcorelib_src.launch_bar")]:
            del sys.modules[_name]

        from Py4GWCoreLib.py4gwcorelib_src.launch_bar.manager import LaunchBarManager
        from Py4GWCoreLib.py4gwcorelib_src.launch_bar.model import LaunchBarSet
        from Py4GWCoreLib.py4gwcorelib_src.launch_bar.persistence import load_state

        state = load_state()
        if state:
            # restore the user's saved launchpads/tiles/colors/placement
            bar_set = LaunchBarSet.from_dict(state)
        else:
            # first run: a normal user launchpad with a couple of placeholder tiles
            bar_set = LaunchBarSet()
            bar = bar_set.add(x=340.0, y=200.0)
            bar.add_tile(1, 1)
            bar.add_tile(2, 1)

        _ensure_system_bar(bar_set)

        manager = LaunchBarManager(bar_set)
        # editor + edit mode start OFF; the user opens the editor via a bar's right-click "Editor..."
        _manager = manager
    except Exception as exc:  # a broken boot must not spam the game loop
        _boot_failed = True
        try:
            import PySystem

            PySystem.Console.Log("LaunchBar", "Boot failed: %s" % exc, PySystem.Console.MessageType.Error)
        except Exception:
            pass


def main() -> None:
    """Sole per-frame entry: boot once, then render all bars + the settings window.

    IMPORTANT: expose exactly ONE entry point. The Py4GW launcher invokes *both* ``main()``
    and ``draw()`` when both exist, which would render every window/item twice per frame —
    causing ImGui ID-conflict warnings and doubled editor elements. So there is no public
    ``draw()`` here.
    """

    _boot()
    if _manager is None:
        return
    _manager.draw(_now_ms())
