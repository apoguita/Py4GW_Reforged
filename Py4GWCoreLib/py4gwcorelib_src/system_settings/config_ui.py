"""System Settings UI — builds the options window from the catalog.

Renders through the shared :class:`ImGui.SidebarWindow` helper (the same window the Hello World
demo uses): one collapsible **group per Category**, one **section per Listener**, and each
section's content is that listener's enable checkbox + its sub-options. All state lives in the
controller, so these draw callables just read/write it.
"""

import PyImGui

from Py4GWCoreLib import ImGui

from . import model

_INFRA_COLOR = (0.95, 0.75, 0.35, 1.0)
_MUTED_COLOR = (0.60, 0.60, 0.65, 1.0)


def _glyph(icon_name: str) -> str:
    """Resolve a Font Awesome constant NAME to its glyph char (empty string if unavailable)."""
    if not icon_name:
        return ""
    try:
        from Py4GWCoreLib.ImGui_src.IconsFontAwesome5 import IconsFontAwesome5

        glyph = getattr(IconsFontAwesome5, icon_name, "")
        return glyph if isinstance(glyph, str) else ""
    except Exception:
        return ""


def _draw_option(controller, cat: "model.Category", lsn: "model.Listener", opt) -> None:
    value = controller.option_value(lsn, opt)
    tag = "##%s_%s" % (lsn.name, opt.key)
    if isinstance(opt, model.IntOption):
        new_val = PyImGui.slider_int(opt.label + tag, int(value), opt.min, opt.max)
        if new_val != int(value):
            controller.set_option(cat.key, lsn, opt, int(new_val))
    else:
        new_val = PyImGui.checkbox(opt.label + tag, bool(value))
        if new_val != bool(value):
            controller.set_option(cat.key, lsn, opt, bool(new_val))


def _draw_listener(controller, cat: "model.Category", lsn: "model.Listener") -> None:
    on = controller.is_enabled(lsn)
    new_on = PyImGui.checkbox("Enabled##en_%s" % lsn.name, on)
    if new_on != on:
        controller.set_listener_enabled(cat.key, lsn, new_on)

    if lsn.help:
        PyImGui.spacing()
        PyImGui.text_wrapped(lsn.help)
    if lsn.infra:
        PyImGui.text_colored("Data feed — other widgets may depend on this.", _INFRA_COLOR)

    if lsn.options:
        PyImGui.spacing()
        PyImGui.separator()
        PyImGui.text_colored("Options", _MUTED_COLOR)
        if not new_on:
            PyImGui.text_colored("(enable the listener to use these)", _MUTED_COLOR)
        for opt in lsn.options:
            _draw_option(controller, cat, lsn, opt)


def build_window(controller) -> "ImGui.SidebarWindow":
    """Construct the settings :class:`SidebarWindow` from the catalog (pure construction)."""
    win = ImGui.SidebarWindow(
        "System Settings",
        sidebar_width=240.0,
        content_width=520.0,
        height=560.0,
        collapsible_groups=True,
        show_search=True,
        on_close=controller.close,   # the window's X hides it (same as toggling the cog off)
    )
    for cat in model.CATALOG:
        group = win.add_group(cat.title, icon=_glyph(cat.icon))
        for lsn in cat.listeners:
            # Bind each section to its own listener via default args (avoid late-binding capture).
            win.add_section(
                group,
                lsn.label,
                (lambda c=controller, ca=cat, ls=lsn: _draw_listener(c, ca, ls)),
            )
    return win
