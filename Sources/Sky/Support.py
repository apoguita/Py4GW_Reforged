from __future__ import annotations

import webbrowser

import PyImGui


KOFI_URL = "https://ko-fi.com/itz_sky"
SUPPORT_LABEL = "♥ Support Sky"


def open_support_page() -> None:
    """Open Sky's Ko-fi page in the user's default web browser."""
    try:
        webbrowser.open(KOFI_URL)
    except Exception:
        # Support must never interfere with the bot runtime.
        pass


def draw_support_button(
    *,
    label: str = SUPPORT_LABEL,
    unique_id: str = "SkyKoFiSupport",
) -> None:
    """Draw the optional support button without affecting bot execution."""
    if PyImGui.button(f"{label}##{unique_id}"):
        open_support_page()

    if PyImGui.is_item_hovered():
        if PyImGui.begin_tooltip():
            PyImGui.text("Support Sky on Ko-fi")
            PyImGui.text(KOFI_URL)
            PyImGui.end_tooltip()


def attach_botting_tree_support(tree) -> None:
    """Add the support button to the native BottingTree control row.

    This is intentionally implemented outside Py4GWCoreLib so only scripts that
    explicitly opt in display Sky's Ko-fi button. The BottingTree UI currently
    places its first separator immediately after Start, or after Stop/Pause.
    We intercept only that separator while the native main child is rendered,
    draw the support button on the same line, then restore PyImGui immediately.
    """
    ui = getattr(tree, "UI", None)
    if ui is None or getattr(ui, "_sky_kofi_support_attached", False):
        return

    original_draw_main_child = getattr(ui, "_draw_main_child", None)
    if not callable(original_draw_main_child):
        return

    def _draw_main_child_with_support(*args, **kwargs):
        original_separator = PyImGui.separator
        inject_support = True

        def _separator_with_support(*separator_args, **separator_kwargs):
            nonlocal inject_support
            if inject_support:
                inject_support = False
                PyImGui.same_line(0.0, -1.0)
                draw_support_button(unique_id="SkyKoFiBottingTree")
            return original_separator(*separator_args, **separator_kwargs)

        PyImGui.separator = _separator_with_support
        try:
            return original_draw_main_child(*args, **kwargs)
        finally:
            PyImGui.separator = original_separator

    ui._sky_kofi_support_original_draw_main_child = original_draw_main_child
    ui._draw_main_child = _draw_main_child_with_support
    ui._sky_kofi_support_attached = True
