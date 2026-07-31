"""Skillbar+ settings hosted by the System Settings Skills & Casting category."""

from typing import cast

import PyImGui

from Py4GWCoreLib import ImGui
from Py4GWCoreLib import Utils
from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE
from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.Skillbar import SkillBar

from .controller import SkillbarPlusController
from .controller import get_controller


_MUTED = (0.60, 0.60, 0.65, 1.0)


def _set(controller: SkillbarPlusController, key: str, value: object) -> None:
    controller.set_option(key, value)


def _edit_color(label: str, color: int) -> int:
    edited = PyImGui.color_edit4(label, Utils.ColorToTuple(color))
    return Utils.TupleToColor(cast(tuple[float, float, float, float], edited))


def _draw_skillbar(controller: SkillbarPlusController) -> None:
    config = controller.config
    PyImGui.text_wrapped("Recharge timers, effect backgrounds, and duration bars drawn over the in-game skillbar.")
    PyImGui.separator()
    value = PyImGui.slider_int("Recharge font size", config.skill_font_size, 10, 100)
    if value != config.skill_font_size:
        _set(controller, "skill_font_size", value)
    enabled = PyImGui.checkbox("Draw background colors", config.draw_background)
    if enabled != config.draw_background:
        _set(controller, "draw_background", enabled)
    if config.draw_background:
        color = _edit_color("Under skill effect", config.background_color)
        if color != config.background_color:
            _set(controller, "background_color", color)
        color = _edit_color("Skill effect nearly expired", config.near_expiry_color)
        if color != config.near_expiry_color:
            _set(controller, "near_expiry_color", color)
        threshold = PyImGui.input_int("Nearly expired threshold (s)", config.near_expiry_threshold)
        if threshold != config.near_expiry_threshold:
            _set(controller, "near_expiry_threshold", threshold)
    durations = PyImGui.checkbox("Draw effect durations on skillbar", config.draw_durations)
    if durations != config.draw_durations:
        _set(controller, "draw_durations", durations)
    if config.draw_durations:
        value = PyImGui.slider_int("Duration font size", config.duration_font_size, 4, 30)
        if value != config.duration_font_size:
            _set(controller, "duration_font_size", value)
        color = _edit_color("Duration bar background", config.duration_background)
        if color != config.duration_background:
            _set(controller, "duration_background", color)
        color = _edit_color("Duration bar foreground", config.duration_foreground)
        if color != config.duration_foreground:
            _set(controller, "duration_foreground", color)
        offset = PyImGui.input_int("Duration bar Y offset", config.duration_offset)
        if offset != config.duration_offset:
            _set(controller, "duration_offset", offset)


def _draw_effects(controller: SkillbarPlusController) -> None:
    config = controller.config
    PyImGui.text_wrapped("Show remaining durations on the game's active-effect frames.")
    value = PyImGui.slider_int("Effects font size", config.effects_font_size, 5, 50)
    if value != config.effects_font_size:
        _set(controller, "effects_font_size", value)
    color = _edit_color("Background", config.effects_background)
    if color != config.effects_background:
        _set(controller, "effects_background", color)


def _draw_autocast(controller: SkillbarPlusController) -> None:
    config = controller.config
    enabled = PyImGui.checkbox(
        "Enable Alt + right-click on a skill to toggle autocasting", config.auto_cast_alt_right_click
    )
    if enabled != config.auto_cast_alt_right_click:
        _set(controller, "auto_cast_alt_right_click", enabled)
    if not Map.IsMapReady():
        PyImGui.text_colored("Enter a map to choose autocast slots.", _MUTED)
        return
    PyImGui.text_wrapped(
        "Green skill icons are queued for the runtime autocast loop. These selections reset on map change."
    )
    icon_size = 36
    offset = icon_size + 24
    for index in range(8):
        if controller.autocast_slots[index]:
            PyImGui.push_style_color(PyImGui.ImGuiCol.Button, (0, 0.70, 0, 1))
            PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, (0, 0.85, 0, 1))
            PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, (0, 0.90, 0, 1))
        else:
            PyImGui.push_style_color(PyImGui.ImGuiCol.Button, (0.2, 0.2, 0.2, 1))
            PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, (0.3, 0.3, 0.3, 1))
            PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, (0.4, 0.4, 0.4, 1))
        texture_path = GLOBAL_CACHE.Skill.ExtraData.GetTexturePath(SkillBar.GetSkillIDBySlot(index + 1))
        if texture_path:
            if ImGui.ImageButton("##skillbar_plus_slot_%d" % index, texture_path, icon_size, icon_size):
                controller.autocast_slots[index] = not controller.autocast_slots[index]
            PyImGui.same_line(offset, -1)
            offset += icon_size + 14
        PyImGui.pop_style_color(3)


def add_sections(win, group) -> None:
    """Add Skillbar+ as a tabbed section in the Skills & Casting category."""

    controller = get_controller()
    win.add_section(group, "Skillbar +")
    win.add_tab("Skillbar +", "Skillbar", lambda c=controller: _draw_skillbar(c))
    win.add_tab("Skillbar +", "Effects", lambda c=controller: _draw_effects(c))
    win.add_tab("Skillbar +", "Auto Cast", lambda c=controller: _draw_autocast(c))
