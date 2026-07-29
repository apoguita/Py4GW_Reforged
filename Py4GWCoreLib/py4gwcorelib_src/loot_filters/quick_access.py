"""The loot quick access -- a window you keep open while playing.

**It configures nothing.** Everything it shows was chosen in System Settings; here the user only
toggles. That is what keeps it a *quick access* rather than a second settings screen.

**It holds groups and filters. There is nothing else to toggle.**

**No tabs and no lobby.** Surfaces are stacked **collapsible headers** -- the house container
everywhere else, so this stops being the one surface with its own navigation idiom. A lobby would make
it a menu; a tab row cannot hold eleven surfaces at the 300 x 300 minimum, and ImGui has no multi-row
tab bar. Collapsed, the window is one line per surface.

**It owns its own draw pass.** Registered as a callback rather than drawn from another module's
``draw()``, so it renders whether or not System Settings is open -- and cannot silently have no caller.

**It is an ordinary window.** Position, size and whether it is collapsed belong to imgui and persist
through ``imgui.ini`` like every other window's; nothing here manages them, and no window flags are
set. The single thing this module persists is *shown or not shown* -- the checkbox in System
Settings -- because that is a user setting rather than window placement.

Rendering is the **shared renderer**, the same one settings uses, so a fix lands in both.
"""

import PyImGui

from ...ImGui import ImGui
from . import renderer
from . import store
from . import surfaces as surface_defs
from .controller import LootFilters

GRAY = renderer.GRAY
_CB_NAME = "loot_quick_access"

_state: dict = {"loaded": False, "surfaces": [], "open": False, "live_open": False, "registered": False}


def _ensure_loaded() -> None:
    if not _state["loaded"]:
        chosen, _layout, window_open = store.load_quick_access()
        _state["surfaces"] = chosen
        _state["open"] = window_open
        _state["loaded"] = True


def _persist() -> None:
    store.save_quick_access(_state["surfaces"], "", bool(_state["open"]))


def surfaces_list() -> list[str]:
    _ensure_loaded()
    return list(_state["surfaces"])


#: The settings surface calls this to show what is currently chosen.
surfaces = surfaces_list


def set_surfaces(names) -> None:
    """Replace what the quick access shows. The user's choice, and it persists."""
    _ensure_loaded()
    allowed = surface_defs.names()
    _state["surfaces"] = [n for n in names if n in allowed]
    _persist()


def is_open() -> bool:
    _ensure_loaded()
    return bool(_state["open"])


def toggle(open_it: bool | None = None) -> None:
    """Open or close the window. Persisted -- it reopens next session if left open."""
    _ensure_loaded()
    _state["open"] = (not _state["open"]) if open_it is None else bool(open_it)
    _persist()


def _edit(loot: LootFilters, surface: str, entry_id: int, on: bool) -> None:
    """A user edit: persisted is what is saved, live kept in step so it applies now."""
    surface_defs.apply_to(surface, loot.persisted, entry_id, on)
    surface_defs.apply_to(surface, loot.live, entry_id, on)
    loot.save()


def _draw_live_label(loot: LootFilters) -> None:
    if loot.is_stock():
        return
    PyImGui.separator()
    PyImGui.text_colored("A script is changing these settings", (0.88, 0.77, 0.55, 1.0))
    PyImGui.same_line(0, 6)
    if PyImGui.small_button("details##qa_live"):
        _state["live_open"] = True
    PyImGui.same_line(0, 4)
    if PyImGui.small_button("reset##qa_live_reset"):
        loot.reset_live()


def _draw_live_window(loot: LootFilters) -> None:
    """The detail view -- its own window, opened on demand."""
    if not _state["live_open"]:
        return
    visible, still_open = PyImGui.begin_with_close("Loot - live state", True)
    if not still_open:
        _state["live_open"] = False
    if visible:
        if loot.is_stock():
            PyImGui.text("Running exactly what you saved.")
        else:
            PyImGui.text("Differences from your saved configuration:")
            PyImGui.separator()
            for line in loot.live_diff():
                PyImGui.bullet_text(line)
            PyImGui.separator()
            if PyImGui.button("Reset to saved##live_reset"):
                loot.reset_live()
        if PyImGui.button("Close##live_close"):
            _state["live_open"] = False
    PyImGui.end()


def draw() -> None:
    """Render the quick access. Called from this module's own callback."""
    _ensure_loaded()
    if not _state["open"]:
        return
    loot = LootFilters()

    # Resizable, with the agreed 300 x 300 floor.
    PyImGui.set_next_window_size_constraints((300.0, 300.0), (1400.0, 1200.0))
    # `begin_with_close` returns (visible, still_open) as two DISTINCT answers, and they must not
    # be conflated: `visible` is False when the window is merely COLLAPSED, while `still_open` is
    # False only when the user clicked the X. Treating "not visible" as "closed" made collapsing
    # the window persist it shut, so it never came back.
    #
    # Position, size and collapsed state are imgui's to remember (imgui.ini), exactly as for every
    # other window. Nothing here manages them.
    visible, still_open = PyImGui.begin_with_close("Loot - Quick Access", True)
    if not still_open and _state["open"]:
        toggle(False)
    if visible:
        for surface in _state["surfaces"]:
            if surface == surface_defs.NICHOLAS:
                _draw_nicholas(loot)
                continue
            layout = store.load_layout_for(surface, surface_defs.default_layout(surface))
            renderer.draw_section(
                "qa_" + surface.replace(" ", "_"), surface,
                surface_defs.groups_for(surface, loot.persisted),
                surface_defs.selected_set(surface, loot.persisted),
                lambda entry_id, on, s=surface: _edit(loot, s, entry_id, on),
                layout, surface_defs.tooltip_for(surface),
            )

        active = loot.active_filters()
        if active:
            if PyImGui.collapsing_header("Filters  (%d)###qa_filters" % len(active)):
                PyImGui.text_colored("From the profile in use. Edited in System Settings.", GRAY)
                for rule in active:
                    PyImGui.text_colored("  - %s" % rule.name, GRAY)

        _draw_live_label(loot)
    PyImGui.end()

    _draw_live_window(loot)


def _draw_nicholas(loot: LootFilters) -> None:
    """Nicholas is a toggle of weeks, not a list of entries -- so it draws itself."""
    import datetime

    rows = surface_defs.nicholas_rows(loot.persisted, datetime.date.today())
    if not PyImGui.collapsing_header("Nicholas  (%d)###qa_nick" % len(rows)):
        return
    for _selection, label, _is_current in rows:
        PyImGui.text_colored("  " + label, GRAY)
    if not rows:
        PyImGui.text_colored("  none - add dates in System Settings", GRAY)


# ---------------------------------------------------------------- driving


def register() -> None:
    """Own the draw pass, so the window can never be left with no caller."""
    try:
        import PyCallback

        from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

        PyCallback.PyCallback.RemoveByName(_CB_NAME)  # idempotent across reloads
        PyCallback.PyCallback.Register(_CB_NAME, PyCallback.Phase.Update, _pass,
                                       priority=99, context=PyCallback.Context.Draw)
        ProfilingRegistry().register(_CB_NAME)
        _state["registered"] = True
    except Exception:
        pass


def unregister() -> None:
    try:
        import PyCallback

        PyCallback.PyCallback.RemoveByName(_CB_NAME)
    except Exception:
        pass
    _state["registered"] = False


def _pass() -> None:
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

        registry = ProfilingRegistry()
        if registry.enabled:
            registry.runcall_scope("widgets", "%s:draw" % _CB_NAME, draw)
            return
    except Exception:
        pass
    draw()
