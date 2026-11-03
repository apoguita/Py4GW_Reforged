"""Compatibility repairs for text editing in affected PyImGui builds.

Some embedded builds deliver printable characters to ImGui but omit the
Backspace and Ctrl+A editing events.  Patch the three text entry functions at
module import time so every widget benefits, including widgets that call
PyImGui directly instead of the higher-level ImGui facade.
"""

from __future__ import annotations

import ctypes
import time
from typing import Any, Callable, cast

import PyImGui


_VK_BACK = 0x08
_VK_A = 0x41
_VK_CONTROL = 0x11
_PATCH_MARKER = "_py4gw_text_edit_compat_v1"
_PATCH_VERSION = 3
_selection_owner: str | None = None
_active_owner: str | None = None
_last_wants_text = False
_key_state: dict[int, tuple[bool, float, float]] = {}


def _down(vk: int) -> bool:
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
    except Exception:
        return False


def _pressed_or_repeated(vk: int) -> bool:
    """Return one press, then normal text-editor style key repeats."""
    now = time.monotonic()
    down = _down(vk)
    was_down, pressed_at, repeated_at = _key_state.get(vk, (False, 0.0, 0.0))
    fire = False
    if down and not was_down:
        fire = True
        pressed_at = repeated_at = now
    elif down and now - pressed_at >= 0.35 and now - repeated_at >= 0.05:
        fire = True
        repeated_at = now
    elif not down:
        pressed_at = repeated_at = 0.0
    _key_state[vk] = (down, pressed_at, repeated_at)
    return fire


def _replacement_after_select_all(before: str, after: str) -> str | None:
    if after == before:
        return None
    if after.startswith(before):
        return after[len(before):]
    if after.endswith(before):
        return after[:-len(before)] if before else after

    prefix = 0
    limit = min(len(before), len(after))
    while prefix < limit and before[prefix] == after[prefix]:
        prefix += 1
    suffix = 0
    while (
        suffix < len(before) - prefix
        and suffix < len(after) - prefix
        and before[-1 - suffix] == after[-1 - suffix]
    ):
        suffix += 1
    end = len(after) - suffix if suffix else len(after)
    inserted = after[prefix:end]
    return inserted if inserted else after


def _wrap(name: str, original: Callable[..., str]) -> Callable[..., str]:
    def wrapped(*args: Any, **kwargs: Any) -> str:
        global _active_owner, _last_wants_text, _selection_owner

        label = str(args[0] if args else kwargs.get("label", ""))
        text_index = 2 if name == "input_text_with_hint" else 1
        if len(args) > text_index:
            before = str(args[text_index])
        else:
            before = str(kwargs.get("text", ""))

        result = original(*args, **kwargs)
        after = str(result)

        try:
            item_id = int(PyImGui.get_item_id())
        except Exception:
            item_id = 0
        owner = f"{name}:{item_id or label}"

        try:
            item_engaged = bool(PyImGui.is_item_active() or PyImGui.is_item_focused())
        except Exception:
            item_engaged = False
        try:
            clicked_here = bool(
                PyImGui.is_item_hovered() and PyImGui.is_mouse_clicked(0)
            )
        except Exception:
            clicked_here = False
        try:
            wants_text = bool(PyImGui.get_io().want_text_input)
        except Exception:
            wants_text = False

        # Some embedded backends never expose active/focused for InputText.
        # A hovered left click identifies the field directly; the rising edge
        # of want_text_input is a fallback for builds where item hover is also
        # incomplete. Keep that owner while ImGui requests text input.
        text_started_here = wants_text and not _last_wants_text
        if item_engaged or clicked_here or text_started_here:
            _active_owner = owner
        elif not wants_text and _active_owner == owner:
            _active_owner = None
        _last_wants_text = wants_text

        if not item_engaged and not (wants_text and _active_owner == owner):
            return after

        ctrl_down = _down(_VK_CONTROL)
        a_pressed = _pressed_or_repeated(_VK_A)
        if ctrl_down and a_pressed:
            _selection_owner = owner
            return before

        if _pressed_or_repeated(_VK_BACK):
            if _selection_owner == owner:
                _selection_owner = None
                return ""
            # If native ImGui already changed the value, do not delete twice.
            return after if after != before else before[:-1]

        if _selection_owner == owner and after != before:
            _selection_owner = None
            replacement = _replacement_after_select_all(before, after)
            return after if replacement is None else replacement

        return after

    setattr(wrapped, _PATCH_MARKER, True)
    setattr(wrapped, "_py4gw_text_edit_compat_version", _PATCH_VERSION)
    setattr(wrapped, "_py4gw_original", original)
    wrapped.__name__ = getattr(original, "__name__", name)
    wrapped.__doc__ = getattr(original, "__doc__", None)
    return wrapped


def _unwrap_original(function: Callable[..., str]) -> Callable[..., str]:
    original = getattr(function, "_py4gw_original", None)
    if callable(original):
        return cast(Callable[..., str], original)

    # Version 1 did not expose __wrapped__. Recover its closed-over native
    # function once so a widget reload can upgrade the patch without a full
    # PY4GW process restart.
    try:
        freevars = function.__code__.co_freevars
        closure = function.__closure__ or ()
        cells = {name: cell.cell_contents for name, cell in zip(freevars, closure)}
        original = cells.get("original")
        if callable(original):
            return cast(Callable[..., str], original)
    except Exception:
        pass
    return function


def install(force: bool = False) -> None:
    for name in ("input_text", "input_text_with_hint", "input_text_multiline"):
        original = getattr(PyImGui, name, None)
        if original is None:
            continue
        installed_version = int(getattr(original, "_py4gw_text_edit_compat_version", 0) or 0)
        if not force and installed_version == _PATCH_VERSION:
            continue
        if getattr(original, _PATCH_MARKER, False):
            original = _unwrap_original(original)
        setattr(PyImGui, name, _wrap(name, original))
