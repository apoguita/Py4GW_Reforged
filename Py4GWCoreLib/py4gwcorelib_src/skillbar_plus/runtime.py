"""Skillbar+ runtime: the complete overlay and autocast implementation.

This module is driven by the native callback registered by :mod:`controller`.  It deliberately
does not depend on a widget script; System Settings boots the controller directly.
"""

import ctypes
import math

import PyImGui
import PyOverlay

from Py4GWCoreLib import ImGui
from Py4GWCoreLib import Utils
from Py4GWCoreLib.FrameTree import Frame
from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE
from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.Party import Party
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Routines import Routines
from Py4GWCoreLib.Skillbar import SkillBar
from Py4GWCoreLib.UIManager import UIManager
from Py4GWCoreLib.py4gwcorelib_src.Color import Color
from Py4GWCoreLib.py4gwcorelib_src.Timer import Timer

from . import model


_USER32 = ctypes.WinDLL("user32", use_last_error=True)


def _is_key_pressed(vk_code: int) -> bool:
    return bool(_USER32.GetAsyncKeyState(vk_code) & 0x8000)


class SkillsPlusRuntime:
    def __init__(self, config: model.SkillbarPlusConfig) -> None:
        self.config = config
        self.overlay = PyOverlay.Overlay()
        self.coords: list[tuple[int, int, int, int]] = []
        self.duration_bar_height = 20
        self.skill_height = 100

    def clear(self) -> None:
        self.coords = []

    def get_skill_frames(self) -> None:
        coords: list[tuple[int, int, int, int]] = []
        for index in range(8):
            frame_id = Frame.skill(index + 1)
            if frame_id.exists:
                coords.append(frame_id.coords())
        self.coords = coords if len(coords) == 8 else []

    @staticmethod
    def draw_text(caption: str, text: str, x: float, y: float, width: float, height: float) -> None:
        PyImGui.set_next_window_pos(x, y)
        PyImGui.set_next_window_size(width, height)
        flags = (
            PyImGui.WindowFlags.NoCollapse
            | PyImGui.WindowFlags.NoTitleBar
            | PyImGui.WindowFlags.NoScrollbar
            | PyImGui.WindowFlags.NoScrollWithMouse
            | PyImGui.WindowFlags.NoBackground
            | PyImGui.WindowFlags.NoMouseInputs
            | PyImGui.WindowFlags.AlwaysAutoResize
        )
        PyImGui.push_style_var(ImGui.ImGuiStyleVar.WindowRounding, 0)
        PyImGui.push_style_var(ImGui.ImGuiStyleVar.WindowBorderSize, 0)
        PyImGui.push_style_var_vec2(ImGui.ImGuiStyleVar.WindowPadding, (0, 0))
        if PyImGui.begin(caption, flags):
            PyImGui.text(text)
        PyImGui.end()
        PyImGui.pop_style_var(3)

    def draw_background(self, coords: tuple[int, int, int, int], color: int) -> None:
        left, top, right, bottom = coords
        self.overlay.DrawQuadFilled(
            PyOverlay.Vec2f(left, top),
            PyOverlay.Vec2f(right, top),
            PyOverlay.Vec2f(right, bottom),
            PyOverlay.Vec2f(left, bottom),
            color,
        )

    def draw_duration_bar(
        self, identifier: str, coords: tuple[int, int, int, int], duration: float, remaining: float
    ) -> None:
        if duration <= 0:
            return
        ImGui.push_font("Regular", self.config.duration_font_size)
        percentage = remaining / duration
        display_remaining = math.floor(remaining) if remaining > 1 else round(remaining, 1)
        text_width, text_height = PyImGui.calc_text_size(str(display_remaining))
        left, top, right, bottom = coords
        self.skill_height = bottom - top
        top += self.config.duration_offset
        bottom = top + int(text_height * 0.75 + 4)
        self.duration_bar_height = bottom - top
        self.overlay.DrawQuadFilled(
            PyOverlay.Vec2f(left, top),
            PyOverlay.Vec2f(right, top),
            PyOverlay.Vec2f(right, bottom + 2),
            PyOverlay.Vec2f(left, bottom + 2),
            self.config.duration_background,
        )
        bar_length = int(((right - 1) - (left + 1)) * percentage)
        self.overlay.DrawQuadFilled(
            PyOverlay.Vec2f(left + 1, top + 1),
            PyOverlay.Vec2f(left + bar_length, top + 1),
            PyOverlay.Vec2f(left + bar_length, bottom + 1),
            PyOverlay.Vec2f(left + 1, bottom + 1),
            self.config.duration_foreground,
        )
        width = right - left
        height = bottom - top
        text_width += 4
        text_height = text_height * 0.75 + 4
        self.draw_text(
            identifier,
            str(display_remaining),
            left + (width - text_width) / 2,
            3 + top + (height - text_height) / 2,
            text_width,
            text_height,
        )
        ImGui.pop_font()

    def draw(self) -> None:
        self.overlay.BeginDraw()
        try:
            if not self.coords:
                return
            for index in range(8):
                if self.config.draw_background or self.config.draw_durations:
                    skill_id = GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(index + 1)
                    duration = 0.0
                    remaining = 0.0
                    for effect in GLOBAL_CACHE.Effects.GetEffects(Player.GetAgentID()):
                        if effect.skill_id == skill_id:
                            duration = effect.duration
                            remaining = effect.time_remaining / 1000
                            break

                    if remaining and remaining < 50000:
                        if self.config.draw_background:
                            color = self.config.near_expiry_color
                            if remaining > self.config.near_expiry_threshold + 1:
                                color = self.config.background_color
                            elif remaining > self.config.near_expiry_threshold:
                                bg_color = tuple(int(c * 255) for c in Utils.ColorToTuple(self.config.background_color))
                                near_color = tuple(int(c * 255) for c in Utils.ColorToTuple(self.config.near_expiry_color))
                                amount = 1 - (remaining - self.config.near_expiry_threshold)
                                color = Color(*bg_color).shift(Color(*near_color), amount).to_color()
                            self.draw_background(self.coords[index], color)
                        if self.config.draw_durations:
                            self.draw_duration_bar(f"duration{index}", self.coords[index], duration, remaining)

                recharge = GLOBAL_CACHE.SkillBar.GetSkillData(index + 1).get_recharge / 1000
                recharge = math.floor(recharge) if recharge > 1 else round(recharge, 1)
                if 1000 > recharge > 0:
                    left, top, right, bottom = self.coords[index]
                    width = right - left
                    height = bottom - top
                    ImGui.push_font("Regular", self.config.skill_font_size)
                    text_width, text_height = PyImGui.calc_text_size(str(recharge))
                    text_height *= 0.75
                    self.draw_text(
                        f"skill{index}",
                        str(recharge),
                        left + (width - text_width) / 2,
                        top + (height - text_height) / 2,
                        text_width,
                        text_height,
                    )
                    ImGui.pop_font()
        finally:
            self.overlay.EndDraw()


class EffectsPlusRuntime:
    def __init__(self, config: model.SkillbarPlusConfig) -> None:
        self.config = config

    @staticmethod
    def draw_text(caption: str, text: str, x: float, y: float, width: float, height: float, color: int) -> None:
        PyImGui.set_next_window_pos(x, y)
        PyImGui.set_next_window_size(width, height)
        flags = (
            PyImGui.WindowFlags.NoCollapse
            | PyImGui.WindowFlags.NoTitleBar
            | PyImGui.WindowFlags.NoScrollbar
            | PyImGui.WindowFlags.NoScrollWithMouse
            | PyImGui.WindowFlags.AlwaysAutoResize
        )
        PyImGui.push_style_color(PyImGui.ImGuiCol.WindowBg, Utils.ColorToTuple(color))
        PyImGui.push_style_var(ImGui.ImGuiStyleVar.WindowRounding, 0)
        PyImGui.push_style_var(ImGui.ImGuiStyleVar.WindowBorderSize, 0)
        PyImGui.push_style_var_vec2(ImGui.ImGuiStyleVar.WindowPadding, (2, 2))
        if PyImGui.begin(caption, flags):
            PyImGui.text(text)
        PyImGui.end()
        PyImGui.pop_style_color(1)
        PyImGui.pop_style_var(3)

    def draw(self) -> None:
        active: list[tuple[int, Frame, float]] = []
        for effect in GLOBAL_CACHE.Effects.GetEffects(Player.GetAgentID()):
            effect_frame = Frame.effect(effect.skill_id)
            if not effect_frame.exists:
                continue
            time_remaining = effect.time_remaining / 1000
            if time_remaining > 30 * 60:
                continue
            display_remaining = math.floor(time_remaining) if time_remaining > 1 else round(time_remaining, 1)
            active.append((effect.skill_id, effect_frame, display_remaining))

        for skill_id in {entry[0] for entry in active}:
            newest = max((entry for entry in active if entry[0] == skill_id), key=lambda entry: entry[2])
            _skill_id, frame_id, time_remaining = newest
            _, _, right, bottom = frame_id.coords()
            self_font_size = self.config.effects_font_size
            ImGui.push_font("Regular", self_font_size)
            text = str(time_remaining)
            text_width, text_height = PyImGui.calc_text_size(text)
            text_width += 4
            text_height = text_height * 0.75 + 4
            self.draw_text(
                f"effect{skill_id}",
                text,
                right - text_width,
                bottom - text_height,
                text_width,
                text_height,
                self.config.effects_background,
            )
            ImGui.pop_font()


class AutoCastRuntime:
    def __init__(self, config: model.SkillbarPlusConfig, slots: list[bool]) -> None:
        self.config = config
        self.slots = slots
        self.cast_timer = Timer()
        self.cast_timer.Start()
        self.click_timer = Timer()
        self.click_timer.Start()

    def can_queue(self, slot: int) -> bool:
        return self.cast_timer.HasElapsed(150) and Routines.Checks.Skills.IsSkillSlotReady(slot) and Routines.Checks.Skills.CanCast()

    def cast(self) -> None:
        for index in range(8):
            if not self.slots[index] or not self.can_queue(index + 1):
                continue
            player_id = Player.GetAgentID()
            skill_id = GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(index + 1)
            if (
                Routines.Checks.Skills.HasEnoughEnergy(player_id, skill_id)
                and Routines.Checks.Skills.HasEnoughAdrenaline(player_id, skill_id)
                and Routines.Checks.Skills.HasEnoughLife(player_id, skill_id)
            ):
                self.cast_timer.Reset()
                GLOBAL_CACHE.SkillBar.UseSkill(index + 1)

    def toggle_hovered_skill(self) -> None:
        if not PyImGui.get_io().key_alt or not _is_key_pressed(2) or not self.config.auto_cast_alt_right_click:
            return
        if not self.click_timer.HasElapsed(200):
            return
        skill_id = SkillBar.GetHoveredSkillID()
        if not skill_id:
            return
        slot = SkillBar.GetSlotBySkillID(skill_id)
        if 1 <= slot <= 8:
            self.slots[slot - 1] = not self.slots[slot - 1]
            self.click_timer.Reset()


class SkillbarPlusRuntime:
    def __init__(self, config: model.SkillbarPlusConfig, slots: list[bool]) -> None:
        self.config = config
        self.slots = slots
        self.skills = SkillsPlusRuntime(config)
        self.effects = EffectsPlusRuntime(config)
        self.auto = AutoCastRuntime(config, slots)

    def reset_map_state(self) -> None:
        self.skills.clear()
        self.slots[:] = [False] * 8

    def draw(self) -> None:
        if Map.IsMapLoading():
            self.reset_map_state()
        if not (
            Map.IsMapReady()
            and Map.IsExplorable()
            and Party.IsPartyLoaded()
            and not Map.IsInCinematic()
            and not UIManager.IsWorldMapShowing()
        ):
            return
        if not self.skills.coords:
            self.skills.get_skill_frames()
        self.skills.draw()
        self.effects.draw()
        self.auto.cast()
        self.auto.toggle_hovered_skill()
