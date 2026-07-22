"""Launch Bar — package entry point (boot + per-frame render).

Passive on import: importing this module only defines functions; nothing renders or touches the
game until the launchpad host callback calls :func:`main` once per frame.

This is the entry/orchestration module for the from-scratch configurable floating toolbar that
replaced the old ``LaunchSurface`` UI. It owns the persistent :class:`LaunchBarManager` instance
(``_manager``) and ties the package together; the data model, host and manager live in the sibling
modules of this package. See ``docs/LaunchBar_ImGui_Implementation_Plan.md``.

Note: this module is named ``app`` (not ``LaunchBar``) on purpose — the package already exports a
``LaunchBar`` *class* from :mod:`.model`; this is the launch-bar *application*, a different thing.
"""

_manager = None
_boot_failed = False


def _now_ms() -> float:
    try:
        import PySystem

        return float(PySystem.get_tick_count64())
    except Exception:
        return 0.0


def _log(msg: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log("LaunchBar", msg, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


def _ensure_action_tile(bar, action: str, name: str) -> None:
    """Guarantee a non-deletable tile bound to a mandatory system ``action`` exists on ``bar``.

    Idempotent, and RETROACTIVE: existing users already have a persisted system bar (with the
    widget-browser button but not newer mandatory buttons), so on boot we add any missing one. If
    the bar has no free slot, the grid is expanded along its major axis first, so a mandatory
    button always fits rather than being silently dropped.
    """

    if any(t.action == action for t in bar.tiles):
        return
    if bar.first_free_block(1, 1) is None:
        # Full bar — grow the launchpad to make room (a +1 on the major axis always frees a slot).
        if bar.is_horizontal:
            bar.columns = bar.columns + 1
        else:
            bar.rows = bar.rows + 1
    tile = bar.add_tile(1, 1)
    if tile is not None:
        tile.action = action
        tile.name = name
        tile.deletable = False


def _ensure_system_bar(bar_set) -> None:
    """Guarantee a non-deletable System bar carrying the fixed system buttons exists.

    The System bar is persisted like any other, so on a restored state it's already present; this
    fabricates one only on first run. Either way it then ensures every fixed system button — the
    widget browser and the library-settings cog — is present, so existing users pick up new system
    buttons on their next boot without losing their bar.
    """

    sysbar = next((b for b in bar_set.bars if b.system), None)
    if sysbar is None:
        sysbar = bar_set.add(name="System", x=340.0, y=120.0)
        sysbar.system = True
    # Migrate legacy action ids on already-persisted system bars so the ensure below recognises the
    # existing button (rather than adding a duplicate): the settings action was renamed
    # library_settings -> system_settings.
    for t in sysbar.tiles:
        if t.action == "library_settings":
            t.action = "system_settings"
            t.name = "Settings"
    _ensure_action_tile(sysbar, "browser", "Widgets")
    _ensure_action_tile(sysbar, "system_settings", "Settings")


def _default_bar_set(LaunchBarSet):
    """A sane first-run launchpad: one user bar with a couple of placeholder tiles.

    The System bar is added by :func:`_ensure_system_bar` afterwards, so this only seeds the
    user-facing bar. Kept trivial so it can never itself fail.
    """

    bar_set = LaunchBarSet()
    bar = bar_set.add(x=340.0, y=200.0)
    bar.add_tile(1, 1)
    bar.add_tile(2, 1)
    return bar_set


def _clamp_bars_on_screen(bar_set) -> None:
    """Self-heal bar placement: keep every bar's anchor inside the current viewport.

    A saved x/y from a different resolution (or a bar dragged to the very edge, e.g. x=-1)
    can leave the bar invisible or unreachable. This nudges the anchor back into view with a
    small margin. No-op if the display size isn't available yet (never breaks boot).
    """

    try:
        import PyImGui

        io = PyImGui.get_io()
        dw = float(getattr(io, "display_size_x", 0) or 0)
        dh = float(getattr(io, "display_size_y", 0) or 0)
    except Exception:
        return
    if dw <= 1.0 or dh <= 1.0:
        return
    margin = 8.0
    for bar in bar_set.bars:
        try:
            x = float(getattr(bar, "x", 0.0))
            y = float(getattr(bar, "y", 0.0))
            # keep the anchor (and thus the drag strip) reachable: at least `margin` from each
            # edge, and never past `display - margin - 48` so a corner always stays on-screen.
            bar.x = min(max(x, margin), max(margin, dw - margin - 48.0))
            bar.y = min(max(y, margin), max(margin, dh - margin - 48.0))
        except Exception:
            continue


def _boot() -> None:
    """Create the manager + restore/seed bars once. Idempotent (the launcher calls per frame)."""

    global _manager, _boot_failed
    if _manager is not None or _boot_failed:
        return
    try:
        # Live-iteration aid: the package's INTERNAL modules are sys.modules-cached, so a widget
        # reload would otherwise reuse their stale code. Purge them so each boot re-imports edits.
        # Keep this entry module and the launchpad host: they own persistent state (the manager
        # instance below and the native Draw registration), so purging them would re-boot per frame.
        import sys

        _pkg = "Py4GWCoreLib.py4gwcorelib_src.launch_bar"
        _keep = {"%s.app" % _pkg, "%s.launchpad" % _pkg}
        for _name in [m for m in list(sys.modules) if m.startswith(_pkg) and m not in _keep]:
            del sys.modules[_name]

        from Py4GWCoreLib.py4gwcorelib_src.launch_bar.manager import LaunchBarManager
        from Py4GWCoreLib.py4gwcorelib_src.launch_bar.model import LaunchBarSet
        from Py4GWCoreLib.py4gwcorelib_src.launch_bar.persistence import load_state

        # Load persisted state DEFENSIVELY: missing/empty/corrupt settings must never keep the
        # launchpad from coming up — this is the cornerstone of the UI. Any problem falls back to
        # a fresh default, so the System bar always exists.
        bar_set = None
        try:
            state = load_state()
            if state:
                bar_set = LaunchBarSet.from_dict(state)
        except Exception as exc:
            _log("state load failed, using default launchpad: %s" % exc)
            bar_set = None
        if bar_set is None or not getattr(bar_set, "bars", None):
            bar_set = _default_bar_set(LaunchBarSet)

        _ensure_system_bar(bar_set)      # System bar guaranteed to exist
        _clamp_bars_on_screen(bar_set)   # and every bar guaranteed reachable on-screen

        # editor + edit mode start OFF; the user opens the editor via a bar's right-click "Editor..."
        _manager = LaunchBarManager(bar_set)
    except Exception as exc:  # only a hard code error latches (avoids per-frame spam); settings
        _boot_failed = True   # problems are handled above and never reach here
        _log("Boot failed: %s" % exc)


def add_function_bar(name, layout):
    """Import a grid of function tiles as a new launch bar. Public entry for external systems.

    ``layout`` is a list of ``(col, row, function_id, display_name)``. Boots the launchpad if it is
    not up yet, then delegates to :meth:`LaunchBarManager.import_function_bar`. Returns the new bar,
    or ``None`` if the launchpad could not boot or the layout was empty. Used by HeroAI's
    hotbar-import button to fold its deprecated CommandHotBars into the launch bar.
    """
    _boot()
    if _manager is None:
        return None
    return _manager.import_function_bar(name, layout)


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
