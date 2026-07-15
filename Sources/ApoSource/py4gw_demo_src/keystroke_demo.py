"""
Keystroke section — native ``PyKeystroke.PyKeyHandler`` (converted to the DEMO 2.0 template).

Data path: the ``PyKeystroke`` embedded module (present only in-client). The handle is
instantiated explicitly and lazily; there is NO reflection — every R2 method is wired by hand.
This is an ACTION api (KeyHandler has no getters/data members), so the Data tab only reports
handler availability + the currently-selected key/combo, and every binding is an explicit
``ui.action_button`` trigger under the Actions tab (fires on click, never on render).

Input note: despite the native arg name ``virtualKeyCode``, the bindings' docstrings say scan
codes. We drive them with the values the ``Key`` enum exposes (``Key[name].value``), following
the R1 recipe (§13): ``key_names = [k.name for k in Key]`` -> ``Key[name]`` -> ``.value``.

R2 coverage — PyKeyHandler wired: __init__ (explicit ctor), PressKey, ReleaseKey, PushKey,
PressKeyCombo, ReleaseKeyCombo, PushKeyCombo. Skipped: none.
"""

import PyImGui

from Py4GWCoreLib import Key

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Keystroke"

# Explicit handle (never reflected). Lazily built because PyKeystroke only exists in-client.
_handler = None
_err = ""

# Key enum names for the selector (canonical members; aliases are not iterated by Enum).
_KEY_NAMES = [k.name for k in Key]


def _get_handler():
    global _handler, _err
    if _handler is None and not _err:
        try:
            import PyKeystroke  # embedded module — only present in-client

            _handler = PyKeystroke.PyKeyHandler()
        except Exception as e:  # noqa: BLE001 - surface, don't crash
            _err = f"{type(e).__name__}: {e}"
    return _handler


class _State:
    key_index: int = 0
    combo_text: str = "17,87"  # Ctrl + W


state = _State()


def _selected_key():
    """Return the currently-selected ``Key`` member (guarded), or None."""
    try:
        return Key[_KEY_NAMES[state.key_index]]
    except (IndexError, KeyError):
        return None


def _selected_value():
    key = _selected_key()
    return None if key is None else key.value


def _parse_combo(text):
    """Parse the comma/space-separated combo field into a list[int] of key codes."""
    codes = []
    for tok in str(text).replace(",", " ").split():
        try:
            codes.append(int(tok, 16) if tok.lower().startswith("0x") else int(tok))
        except (TypeError, ValueError):
            continue
    return codes


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def build_keystroke():
    handler = _get_handler()
    key = _selected_key()
    value = _selected_value()
    combo = _parse_combo(state.combo_text)
    rows = [
        ("Handler", "PyKeyHandler ready" if handler is not None else f"unavailable — {_err}"),
        ("Selected Key", "None" if key is None else key.name),
        ("Selected Value", "None" if value is None else casts.flags(value)),
        ("Combo Field", state.combo_text),
        ("Combo Codes", f"[{len(combo)}] {combo}"),
    ]
    return [ui.kv_block("Keystroke", rows)]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    handler = _get_handler()
    if handler is None:
        ui.not_available(f"PyKeystroke unavailable — {_err}")
        return

    ui.section_header("Single Key")
    state.key_index = PyImGui.combo("Key", state.key_index, _KEY_NAMES)
    value = _selected_value()
    ui.text_muted(f"key value (scan/VK): {value}")
    ui.action_button("Press Key", handler.PressKey, value, key="ks_press")
    PyImGui.same_line(0, 6)
    ui.action_button("Release Key", handler.ReleaseKey, value, key="ks_release")
    PyImGui.same_line(0, 6)
    ui.action_button("Push Key", handler.PushKey, value, key="ks_push")

    PyImGui.spacing()
    ui.section_header("Key Combo")
    state.combo_text = PyImGui.input_text("Codes (e.g. 17,87 = Ctrl+W)", state.combo_text)
    combo = _parse_combo(state.combo_text)
    ui.text_muted(f"parsed: {combo}")
    ui.action_button("Press Combo", handler.PressKeyCombo, combo, key="ks_press_combo")
    PyImGui.same_line(0, 6)
    ui.action_button("Release Combo", handler.ReleaseKeyCombo, combo, key="ks_release_combo")
    PyImGui.same_line(0, 6)
    ui.action_button("Push Combo", handler.PushKeyCombo, combo, key="ks_push_combo")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_keystroke_view() -> None:
    blocks = build_keystroke()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("KeystrokeTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
