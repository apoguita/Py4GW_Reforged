"""System Settings > Items controls for Xunlai and Colorize only."""

import PyImGui

from Py4GWCoreLib.py4gwcorelib_src.Color import Color

from . import model
from .controller import InventorySettingsController, get_controller

MUTED = (0.66, 0.67, 0.70, 1.0)
WARN = (0.86, 0.65, 0.28, 1.0)


def _rgba(color: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    return Color(*color).to_tuple_normalized()


def _to_color(value) -> tuple[int, int, int, int]:
    return tuple(Color.from_tuple_normalized(tuple(value)).to_tuple())


def add_sections(win, group) -> None:
    controller = get_controller()
    win.add_section(group, "Open Xunlai Vault", lambda: _draw_xunlai(controller))
    win.add_section(group, "Colorize", lambda: _draw_colorize(controller))


def _draw_xunlai(controller: InventorySettingsController) -> None:
    settings = controller.settings()
    PyImGui.text_wrapped("Open the Xunlai Vault without enabling an automatic handler.")
    visible = settings.context_menu_xunlai
    next_visible = PyImGui.checkbox("Show Open Xunlai in item context menu##items_xunlai_menu", visible)
    if next_visible != visible:
        settings.context_menu_xunlai = next_visible
        controller.save_settings()
    if PyImGui.button("Open Xunlai Vault##items_xunlai"):
        controller.open_xunlai()
    status = controller.xunlai_status()
    if status:
        PyImGui.text_colored(status, MUTED)


def _draw_colorize(controller: InventorySettingsController) -> None:
    colorize = controller.settings().colorize
    changed = False
    colorize.enabled, changed = _checkbox("Enable Colorize##items_colorize", colorize.enabled, changed)
    colorize.context_menu_toggle, changed = _checkbox(
        "Show Colorize toggle in item context menu##items_colorize_menu", colorize.context_menu_toggle, changed)
    PyImGui.text_colored("Bags and the regular inventory are monitored as the same item sources. If both are open, both are tinted.", MUTED)
    PyImGui.separator()
    PyImGui.text("Render targets")
    for label, attr in (("ImGui frame", "imgui_frame"), ("ImGui outline", "imgui_outline"),
                        ("Native frame", "native_frame"), ("Native outline", "native_outline")):
        value = bool(getattr(colorize, attr))
        next_value = PyImGui.checkbox("%s##items_%s" % (label, attr), value)
        if next_value != value:
            setattr(colorize, attr, next_value)
            changed = True
    if colorize.native_outline:
        PyImGui.text_colored("Native outline is not available from the current native UI binding; the option is recorded but has no effect.", WARN)
    PyImGui.separator()
    PyImGui.text("Rarities")
    for rarity in model.RARITIES:
        enabled = bool(colorize.rarities.get(rarity, False))
        next_enabled = PyImGui.checkbox("%s##items_rarity_%s" % (rarity, rarity), enabled)
        if next_enabled != enabled:
            colorize.rarities[rarity] = next_enabled
            changed = True
        picked = _to_color(PyImGui.color_edit4("%s color##items_color_%s" % (rarity, rarity), _rgba(colorize.colors[rarity])))
        if picked != colorize.colors[rarity]:
            colorize.colors[rarity] = picked
            changed = True
    if changed:
        controller.save_settings()


def _checkbox(label: str, value: bool, changed: bool) -> tuple[bool, bool]:
    next_value = PyImGui.checkbox(label, value)
    return bool(next_value), changed or next_value != value
