"""
Mouse section — native ``PyMouse.PyMouse`` (MouseHandler). NEW section; native-only, no stub.

Data path: the ``PyMouse`` embedded module (present only in-client). The handle is instantiated
explicitly and lazily; there is NO reflection — every R2 method is wired by hand. ``PyMouse`` has
no stub and NO getters/data members (it is a pure ACTION api), so the Data tab reports handler
availability + the currently-configured button/coords/delta, and each binding is an explicit
``ui.action_button`` trigger under the Actions tab (fires on click, never on render).

Coordinates are relative to the client window; ``button`` follows the ``MouseButton`` enum
(Left=0, Right=1, Middle=2). All click/press/release/scroll args default to 0 natively.

R2 coverage — PyMouse wired: __init__ (explicit ctor), MoveMouse, Click, DoubleClick, Scroll,
PressButton, ReleaseButton. Skipped: none.
"""

import PyImGui

from Py4GWCoreLib import MouseButton

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Mouse"

# Explicit handle (never reflected). Lazily built because PyMouse only exists in-client.
_handler = None
_err = ""

_BUTTON_NAMES = [b.name for b in MouseButton]


def _get_handler():
    global _handler, _err
    if _handler is None and not _err:
        try:
            import PyMouse  # embedded module — only present in-client, native-only (no stub)

            _handler = PyMouse.PyMouse()
        except Exception as e:  # noqa: BLE001 - surface, don't crash
            _err = f"{type(e).__name__}: {e}"
    return _handler


class _State:
    button_index: int = 0
    x: int = 0
    y: int = 0
    scroll_delta: int = 120


state = _State()


def _button_value():
    try:
        return int(MouseButton[_BUTTON_NAMES[state.button_index]].value)
    except (IndexError, KeyError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# build_* — PyMouse is a pure COMMAND GENERATOR (no getters). The "blocks" only capture the
# currently-configured command for the dump file; the tab is a command panel, not a state reader.
# ---------------------------------------------------------------------------
def build_mouse():
    handler = _get_handler()
    button = _button_value()
    try:
        button_name = MouseButton(button).name
    except (ValueError, TypeError):
        button_name = "?"
    rows = [
        ("Handler", "PyMouse ready" if handler is not None else f"unavailable — {_err}"),
        ("Configured Button", casts.id_name(button, button_name)),
        ("Configured Coords (x, y)", casts.vec(state.x, state.y, nd=0)),
        ("Configured Scroll Delta", state.scroll_delta),
    ]
    return [ui.kv_block("Configured Command (PyMouse has no readable state — it emits commands)", rows)]


# ---------------------------------------------------------------------------
# Command controls — every button GENERATES a mouse command (fired on click only)
# ---------------------------------------------------------------------------
def _draw_commands():
    handler = _get_handler()
    if handler is None:
        ui.not_available(f"PyMouse unavailable — {_err}")
        return

    ui.text_muted("PyMouse generates mouse input. Set a target, then click a command to emit it.")
    ui.section_header("Target (relative to client window)")
    state.button_index = PyImGui.combo("Button", state.button_index, _BUTTON_NAMES)
    button = _button_value()
    state.x = PyImGui.input_int("X", state.x)
    state.y = PyImGui.input_int("Y", state.y)

    PyImGui.spacing()
    ui.section_header("Move")
    ui.action_button("Move Mouse", handler.MoveMouse, state.x, state.y, key="ms_move")

    PyImGui.spacing()
    ui.section_header("Click / Press / Release")
    ui.action_button("Click", handler.Click, button, state.x, state.y, key="ms_click")
    PyImGui.same_line(0, 6)
    ui.action_button("Double Click", handler.DoubleClick, button, state.x, state.y, key="ms_dclick")
    ui.action_button("Press Button", handler.PressButton, button, state.x, state.y, key="ms_press")
    PyImGui.same_line(0, 6)
    ui.action_button("Release Button", handler.ReleaseButton, button, state.x, state.y, key="ms_release")

    PyImGui.spacing()
    ui.section_header("Scroll")
    state.scroll_delta = PyImGui.input_int("Delta", state.scroll_delta)
    ui.action_button("Scroll", handler.Scroll, state.scroll_delta, state.x, state.y, key="ms_scroll")


# ---------------------------------------------------------------------------
# draw_*_view — command generator (no Data tab; PyMouse has no state to read)
# ---------------------------------------------------------------------------
def draw_mouse_view() -> None:
    blocks = build_mouse()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    _draw_commands()
