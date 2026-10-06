# ============================================================
# HeroAI Consumable Auto Upkeep - Official Patch v06 - 2026-10-06
# - Based on the clean Official Patch v05 structure and the tested Personal v17 feature set.
# - One Auto switch: party leader click resets all injected party accounts ON/OFF;
#   any follower can override only its own account until the next leader reset.
# - Floating Consumables/Summoning window keeps its last dragged ImGui position.
# - Leader right-click on a consumable performs one manual party-use pass without
#   changing automatic icon selections; Summoning right-click broadcasts one use
#   attempt to every party account and lets the game enforce the one-summon limit.
# - Adds Lunar Fortune, Experience Scroll, Resurrection Scroll, and the 21-item
#   Summoning page with party-safe automatic coordination.
# - Uses official Item Models paths for Igneous, Lunar Fortune and Resurrection.
# ============================================================

from collections.abc import Callable
import ctypes
from enum import Enum
import math
import os
import random
import time
from typing import Optional
import PySystem
import PyImGui
from . import resurrection_scroll
from . import windows
from .cache_data import CacheData
from .commands import HeroAICommands
from .constants import NUMBER_OF_SKILLS, PARTY_WINDOW_HASH, SKILLBAR_WINDOW_HASH
from .settings import Settings
from .types import Docked, FramePosition
from .utils import IsHeroFlagged, SameMapAsAccount, SameMapOrPartyAsAccount

from Py4GWCoreLib import ImGui, Routines
from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE
from Py4GWCoreLib.GlobalCache.SharedMemory import AccountStruct, HeroAIOptionStruct, SharedMessageStruct
from Py4GWCoreLib.ImGui_src.IconsFontAwesome5 import IconsFontAwesome5
from Py4GWCoreLib.ImGui_src.Style import Style
from Py4GWCoreLib.ImGui_src.Textures import GameTexture, GameTexture, TextureState, ThemeTexture, ThemeTextures
from Py4GWCoreLib.ImGui_src.WindowModule import WindowModule
from Py4GWCoreLib.ImGui_src.types import Alignment, HorizontalAlignment, ImGuiStyleVar, StyleTheme, VerticalAlignment
from Py4GWCoreLib.Overlay import Overlay
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Item import has_active_party_summon, has_summoning_sickness
from Py4GWCoreLib.EnemyBlacklist import draw_blacklist_ui
from Py4GWCoreLib.UIManager import UIManager
from Py4GWCoreLib.enums_src.GameData_enums import Allegiance, Profession, ProfessionShort, Range
from Py4GWCoreLib.enums_src.IO_enums import Key
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.enums_src.Multiboxing_enums import SharedCommandType
from Py4GWCoreLib.py4gwcorelib_src.Color import Color
from Py4GWCoreLib.py4gwcorelib_src.Console import ConsoleLog
from Py4GWCoreLib.py4gwcorelib_src.Timer import ThrottledTimer, Timer
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings as NativeSettings
from Py4GWCoreLib.py4gwcorelib_src.Utils import Utils
from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import get_widget_handler
from Py4GWCoreLib.FrameTree import Frame, FrameId, FrameTree

class CachedSkillInfo:
    def __init__(self, skill_id: int):
        self.skill_id = skill_id
        self.name = GLOBAL_CACHE.Skill.GetNameFromWiki(skill_id)
        self.description = GLOBAL_CACHE.Skill.GetDescription(skill_id)
        self.texture_path = GLOBAL_CACHE.Skill.ExtraData.GetTexturePath(skill_id)
        
        if not os.path.exists(self.texture_path):
            self.texture_path = ""
        
        if not self.texture_path and self.skill_id != 0:
            self.texture_path = ThemeTexture.PlaceHolderTexture.texture
            
        self.is_elite = GLOBAL_CACHE.Skill.Flags.IsElite(skill_id)
        self.is_hex = GLOBAL_CACHE.Skill.Flags.IsHex(skill_id)
        self.is_title = GLOBAL_CACHE.Skill.Flags.IsTitle(skill_id)
        self.is_enchantment = GLOBAL_CACHE.Skill.Flags.IsEnchantment(skill_id)
        self.is_shout = GLOBAL_CACHE.Skill.Flags.IsShout(skill_id)
        self.is_skill = GLOBAL_CACHE.Skill.Flags.IsSkill(skill_id)
        self.is_condition = GLOBAL_CACHE.Skill.Flags.IsCondition(skill_id)
        
        self.adrenaline_cost = GLOBAL_CACHE.Skill.Data.GetAdrenaline(skill_id)

        frame_texture, texture_state, progress_color = get_frame_texture_for_effect(
            skill_id)
        self.frame_texture = frame_texture
        self.texture_state = texture_state
        self.progress_color = progress_color

        self.recharge_time = GLOBAL_CACHE.Skill.Data.GetRecharge(skill_id)


skill_cache: dict[int, CachedSkillInfo] = {}
message_cache : dict[str, dict[SharedCommandType, dict[int, tuple]]] = {}
template_popup_open: bool = False
template_account: str = ""
template_code = ""
configure_consumables_window_open: bool = False
configure_base_consumables_window_open: bool = False
# Official v06: draggable floating Consumables window with persistent ImGui position.
# FirstUseEver supplies only the very first default; afterward ImGui restores the
# user's last dragged location from its normal saved window settings.
_configure_consumables_popup_pending: bool = False
_configure_consumables_popup_anchor: tuple[float, float] = (20.0, 20.0)
_configure_consumables_popup_position_initialized: bool = False
_consumables_ui_page: str = "consumables"


def _live_hero_options(account_data: AccountStruct) -> HeroAIOptionStruct | None:
    """Resolve the live shared-memory HeroAI options for an account.

    Shared-memory structs are live views, so mutating them publishes the change
    to every client. The party-cache options are detached copies (see
    party_cache.detached_hero_ai_options) and must not be used as a write target.
    Hero slots share their owner's email, so they resolve by party number first.
    """
    if account_data.IsHero:
        return GLOBAL_CACHE.ShMem.GetHeroAIOptionsByPartyNumber(int(account_data.AgentPartyData.PartyPosition))
    live = GLOBAL_CACHE.ShMem.GetHeroAIOptionsFromEmail(account_data.AccountEmail)
    if live is not None:
        return live
    return GLOBAL_CACHE.ShMem.GetHeroAIOptionsByPartyNumber(int(account_data.AgentPartyData.PartyPosition))


widget_handler = get_widget_handler()
module_info = None

settings = Settings()
casting_animation_timer = Timer()
casting_animation_timer.Start()

dialog_throttle = ThrottledTimer(500)
party_throttle = ThrottledTimer(500)
party_search_throttle = ThrottledTimer(500)
party_member_frames : list[FramePosition] = []

commands = HeroAICommands()
gray_color = Color(150, 150, 150, 255)
MAX_CHILD_FRAMES = 50

class HealthState(Enum):
    Normal = Color(204, 0, 0, 255)
    Poisoned = Color(116, 116, 48, 255)
    Bleeding = Color(224, 119, 119, 255)
    DegenHexed = Color(196, 56, 150, 255)
    Disconnected = Color(54, 54, 54, 255)

def show_configure_consumables_window():
    global configure_consumables_window_open
    global _configure_consumables_popup_pending

    # True toggle from the HeroAI candy-cane button.
    if configure_consumables_window_open:
        configure_consumables_window_open = False
        _configure_consumables_popup_pending = False
        return

    # Official v06: do not recalculate a mouse-adjacent position here. On the
    # next draw we provide only a FirstUseEver default, allowing Dear ImGui's
    # normal saved window settings to restore the last dragged position.
    _configure_consumables_popup_pending = True
    configure_consumables_window_open = True

def show_base_configure_consumables_window():
    global configure_base_consumables_window_open
    configure_base_consumables_window_open = not configure_base_consumables_window_open
    
def is_base_configure_consumables_window_open() -> bool:
    global configure_base_consumables_window_open
    return configure_base_consumables_window_open

def is_party_window_open() -> bool:
    return Frame(FrameId.PartyFormation).exists
    
          
def get_frame_texture_for_effect(skill_id: int) -> tuple[(GameTexture), TextureState, int]:
    is_elite = GLOBAL_CACHE.Skill.Flags.IsElite(skill_id)
    texture_state = TextureState.Normal if not is_elite else TextureState.Active

    theme = ImGui.get_style().Theme if ImGui.get_style().Theme in ImGui.Textured_Themes else StyleTheme.Guild_Wars
    
    if not theme in ImGui.Textured_Themes:
        theme = StyleTheme.Guild_Wars

    if GLOBAL_CACHE.Skill.Flags.IsHex(skill_id):
        frame_texture = ThemeTextures.Effect_Frame_Hex.value.get_texture(theme)
        progress_color = Color(215, 31, 158, 255).color_int

    elif GLOBAL_CACHE.Skill.Flags.IsTitle(skill_id):
        frame_texture = ThemeTextures.Effect_Frame_Skill.value.get_texture(theme)
        progress_color = Color(75, 139, 69, 255).color_int

    elif GLOBAL_CACHE.Skill.Flags.IsEnchantment(skill_id):
        frame_texture = ThemeTextures.Effect_Frame_Enchantment.value.get_texture(theme)
        progress_color = Color(178, 225, 47, 255).color_int

        profession, _ = GLOBAL_CACHE.Skill.GetProfession(skill_id)
        if profession == Profession.Dervish:
            frame_texture = ThemeTextures.Effect_Frame_Blue.value.get_texture()
            progress_color = Color(74, 163, 193, 255).color_int

    elif GLOBAL_CACHE.Skill.Flags.IsCondition(skill_id):
        frame_texture = ThemeTextures.Effect_Frame_Condition.value.get_texture(theme)
        progress_color = Color(221, 175, 52, 255).color_int

    else:
        frame_texture = ThemeTextures.Effect_Frame_Skill.value.get_texture(theme)
        progress_color = Color(75, 139, 69, 255).color_int

    return frame_texture, texture_state, progress_color

def draw_health_bar(width: float, height: float, max_health: float, current_health: float, regen: float, state: HealthState = HealthState.Normal, deep_wound : bool = False, enchanted: bool = False, conditioned: bool = False, hexed: bool = False, has_weaponspell: bool = False) -> bool:
    style = ImGui.get_style()
    draw_textures = style.Theme in ImGui.Textured_Themes
    pips = Utils.calculate_health_pips(max_health, regen)

    if not draw_textures:
        xpos, ypos = PyImGui.get_cursor_pos()
        color = state.value
        style.PlotHistogram.push_color(color.rgb_tuple)
        style.FrameRounding.push_style_var(0)
        ImGui.progress_bar(current_health, width, height)
        style.FrameRounding.pop_style_var()
        style.PlotHistogram.pop_color()            
        PyImGui.set_cursor_pos((xpos, ypos))
    
    ImGui.dummy(width, height)

    fraction = (max(0.0, min(1.0, current_health))
                if max_health > 0 else 0.0)
    
    item_rect_min, item_rect_max, item_rect_size = ImGui.get_item_rect()

    width = item_rect_max[0] - item_rect_min[0]
    height = item_rect_max[1] - item_rect_min[1]
    item_rect = (item_rect_min[0], item_rect_min[1], width, height)

    progress_rect = (item_rect[0] + 1, item_rect[1] + 1,
                     (width - 2) * fraction, height - 2)
    background_rect = (
        item_rect[0] + 1, item_rect[1] + 1, width - 2, height - 2)
    cursor_rect = (item_rect[0] - 2 + (width - 2) * fraction, item_rect[1] + 1, 4, height -
                   2) if fraction > 0 else (item_rect[0] + (width - 2) * fraction, item_rect[1] + 1, 4, height - 2)

    if draw_textures:
        match state:
            case HealthState.Poisoned:
                health_bar_empty_texture = ThemeTextures.HealthBarPoisonedEmpty
                health_bar_fill_texture = ThemeTextures.HealthBarPoisonedFill
                health_bar_cursor_texture = ThemeTextures.HealthBarPoisonedCursor
            case HealthState.Bleeding:
                health_bar_empty_texture = ThemeTextures.HealthBarBleedingEmpty
                health_bar_fill_texture = ThemeTextures.HealthBarBleedingFill
                health_bar_cursor_texture = ThemeTextures.HealthBarBleedingCursor
            case HealthState.DegenHexed:        
                health_bar_empty_texture = ThemeTextures.HealthBarHexedEmpty
                health_bar_fill_texture = ThemeTextures.HealthBarHexedFill
                health_bar_cursor_texture = ThemeTextures.HealthBarHexedCursor
            case HealthState.Disconnected:
                health_bar_empty_texture = ThemeTextures.HealthBarDisconnectedEmpty
                health_bar_fill_texture = ThemeTextures.HealthBarDisconnectedFill
                health_bar_cursor_texture = ThemeTextures.HealthBarDisconnectedCursor
            case _:                
                health_bar_empty_texture = ThemeTextures.HealthBarEmpty
                health_bar_fill_texture = ThemeTextures.HealthBarFill
                health_bar_cursor_texture = ThemeTextures.HealthBarCursor
        
        health_bar_empty_texture.value.get_texture().draw_in_drawlist(
            background_rect[:2],
            background_rect[2:],
        )

        health_bar_fill_texture.value.get_texture().draw_in_drawlist(
            progress_rect[:2],
            progress_rect[2:],
        )

        if current_health * max_health != max_health:
            health_bar_cursor_texture.value.get_texture().draw_in_drawlist(
                cursor_rect[:2],
                cursor_rect[2:],
            )

    if deep_wound:
        deep_wound_rect = (
            item_rect[0] + (width * 0.8), item_rect[1] + 1, (width * 0.2) + 1, height - 2)
        
        ThemeTextures.HealthBarDeepWound.value.get_texture().draw_in_drawlist(
            deep_wound_rect[:2],
            deep_wound_rect[2:],
        )
        
        ThemeTextures.HealthBarDeepWoundCursor.value.get_texture().draw_in_drawlist(
            deep_wound_rect[:2],
            (2, deep_wound_rect[3]),
        )
        pass
    
    indicators = (enchanted, conditioned, hexed, has_weaponspell)
    if any(indicators):
        #weapon_spell, hexed, conditioned, enchanted
        x_offset = height + 2
        
        for i, indicator in enumerate(indicators):
            if indicator:
                indicator_texture = None
                match i:
                    case 0:
                        indicator_texture = ThemeTextures.HealthIdenticator_Enchanted
                    case 1:
                        indicator_texture = ThemeTextures.HealthIdenticator_Conditioned
                    case 2:
                        indicator_texture = ThemeTextures.HealthIdenticator_Hexed
                    case 3:
                        indicator_texture = ThemeTextures.HealthIdenticator_WeaponSpell
                        
                if indicator_texture:
                    indicator_texture.value.get_texture().draw_in_drawlist(
                        (item_rect[0] + item_rect[2] - x_offset, item_rect[1]),
                        (height, height),
                    )
                    
                x_offset += height + 2
        
        
    display_label = str(int(current_health * max_health))
    textsize = PyImGui.calc_text_size(display_label)
    text_rect = (item_rect[0] + ((width - textsize[0]) / 2), item_rect[1] +
                 ((height - textsize[1]) / 2) + 3, textsize[0], textsize[1])

    ImGui.push_font("Regular", 12)
    PyImGui.draw_list_add_text(
        text_rect[0],
        text_rect[1],
        style.Text.color_int,
        display_label,
    )
    ImGui.pop_font()

    if draw_textures:
        pip_texture = ThemeTextures.Pip_Regen if pips > 0 else ThemeTextures.Pip_Degen

        if pips > 0:
            pip_pos = text_rect[0] + text_rect[2] + 5

            for i in range(int(pips)):
                pip_texture.value.get_texture().draw_in_drawlist(
                    (pip_pos + (i * 8), item_rect[1]),
                    (10 * (height / 16), height),
                )

        elif pips < 0:
            pip_pos = text_rect[0] - 5 - 10

            for i in range(abs(int(pips))):
                pip_texture.value.get_texture().draw_in_drawlist(
                    (pip_pos - (i * 8), item_rect[1]),
                    (10 * (height / 16), height),
                )

        PyImGui.draw_list_add_rect(
            item_rect_min[0], item_rect_min[1], item_rect_min[0] + item_rect_size[0], item_rect_min[1] + item_rect_size[1], style.Border.color_int, 0, 0, 1
        )
        
    else:
        pip_char = IconsFontAwesome5.ICON_ANGLE_RIGHT if pips > 0 else IconsFontAwesome5.ICON_ANGLE_LEFT
        pip_string = "".join([pip_char for _ in range(abs(int(pips)))])

        ImGui.push_font("Regular", 8)
        if pips > 0:
            PyImGui.draw_list_add_text(
                text_rect[0] + text_rect[2] + 5,
                item_rect[1] + 3,
                style.Text.color_int,
                pip_string
            )
        elif pips < 0:
            text_size = PyImGui.calc_text_size(pip_string)
            PyImGui.draw_list_add_text(
                text_rect[0] - 5 - text_size[0],
                item_rect[1] + 3,
                style.Text.color_int,
                pip_string
            )
        ImGui.pop_font()
        
    return PyImGui.is_item_clicked(0)

def draw_energy_bar(width: float, height: float, max_energy: float, current_energy: float, regen: float) -> bool:
    style = ImGui.get_style()
    pips = Utils.calculate_energy_pips(max_energy, regen)
    has_valid_energy = 0.0 <= current_energy <= 1.0
    clamped_energy = max(0.0, min(1.0, current_energy)) if has_valid_energy else 0.0

    draw_textures = style.Theme in ImGui.Textured_Themes

    if not draw_textures:
        style.PlotHistogram.push_color((30, 94, 153, 255))
        style.FrameRounding.push_style_var(0)
        ImGui.progress_bar(clamped_energy, width, height)
        style.FrameRounding.pop_style_var()
        style.PlotHistogram.pop_color()
    else:
        ImGui.dummy(width, height)

    fraction = clamped_energy if max_energy > 0 else 0.0
    
    item_rect_min, item_rect_max, item_rect_size = ImGui.get_item_rect()

    width = item_rect_max[0] - item_rect_min[0]
    height = item_rect_max[1] - item_rect_min[1]
    item_rect = (item_rect_min[0], item_rect_min[1], width, height)

    progress_rect = (item_rect[0] + 1, item_rect[1] + 1,
                     (width - 2) * fraction, height - 2)
    background_rect = (
        item_rect[0] + 1, item_rect[1] + 1, width - 2, height - 2)
    cursor_rect = (item_rect[0] - 2 + (width - 2) * fraction, item_rect[1] + 1, 4, height -
                   2) if fraction > 0 else (item_rect[0] + (width - 2) * fraction, item_rect[1] + 1, 4, height - 2)

    if draw_textures:
        ThemeTextures.EnergyBarEmpty.value.get_texture().draw_in_drawlist(
            background_rect[:2],
            background_rect[2:],
        )

        ThemeTextures.EnergyBarFill.value.get_texture().draw_in_drawlist(
            progress_rect[:2],
            progress_rect[2:],
        )

        if has_valid_energy and current_energy * max_energy != max_energy:
            ThemeTextures.EnergyBarCursor.value.get_texture().draw_in_drawlist(
                cursor_rect[:2],
                cursor_rect[2:],
            )

    display_label = str(int(current_energy * max_energy)) if has_valid_energy else "--"
    textsize = PyImGui.calc_text_size(display_label)
    text_rect = (item_rect[0] + ((width - textsize[0]) / 2), item_rect[1] +
                 ((height - textsize[1]) / 2) + 3, textsize[0], textsize[1])

    ImGui.push_font("Regular", 12)
    PyImGui.draw_list_add_text(
        text_rect[0],
        text_rect[1],
        style.Text.color_int,
        display_label,
    )
    ImGui.pop_font()

    if draw_textures:
        pip_texture = ThemeTextures.Pip_Regen if pips > 0 else ThemeTextures.Pip_Degen

        if pips > 0:
            pip_pos = text_rect[0] + text_rect[2] + 5

            for i in range(int(pips)):
                pip_texture.value.get_texture().draw_in_drawlist(
                    (pip_pos + (i * 8), item_rect[1]),
                    (10 * (height / 16), height),
                )

        elif pips < 0:
            pip_pos = text_rect[0] - 5 - 10

            for i in range(abs(int(pips))):
                pip_texture.value.get_texture().draw_in_drawlist(
                    (pip_pos - (i * 8), item_rect[1]),
                    (10 * (height / 16), height),
                )

        PyImGui.draw_list_add_rect(
            item_rect_min[0], item_rect_min[1], item_rect_min[0] + item_rect_size[0], item_rect_min[1] + item_rect_size[1], style.Border.color_int, 0, 0, 1
        )
    else:
        pip_char = IconsFontAwesome5.ICON_ANGLE_RIGHT if pips > 0 else IconsFontAwesome5.ICON_ANGLE_LEFT
        pip_string = "".join([pip_char for _ in range(abs(int(pips)))])

        ImGui.push_font("Regular", 8)
        if pips > 0:
            PyImGui.draw_list_add_text(
                text_rect[0] + text_rect[2] + 5,
                item_rect[1] + 3,
                style.Text.color_int,
                pip_string
            )
        elif pips < 0:
            text_size = PyImGui.calc_text_size(pip_string)
            PyImGui.draw_list_add_text(
                text_rect[0] - 5 - text_size[0],
                item_rect[1] + 3,
                style.Text.color_int,
                pip_string
            )
        ImGui.pop_font()

    return PyImGui.is_item_clicked(0)

def DrawSquareCooldownEx(button_pos, button_size, progress, tint=0.1):
    """Smooth, non-overlapping, counter-clockwise square cooldown effect."""
    if isinstance(button_size, (int, float)):
        button_size = (button_size, button_size)

    if progress <= 0 or progress >= 1.0:
        return

    center_x = button_pos[0] + button_size[0] / 2.0
    center_y = button_pos[1] + button_size[1] / 2.0
    half_w = button_size[0] / 2.0
    half_h = button_size[1] / 2.0
    color = (int(255 * tint) << 24)

    # Angles
    start_angle = -math.pi / 2.0  # top center
    end_angle = start_angle - 2.0 * math.pi * progress

    # Pre-calculate points
    segments = max(32, min(64, int(64 + 128 * (1 - progress))))
    points = [(center_x, center_y)]

    # Function to compute intersection with square boundary
    def intersection(angle):
        dx, dy = math.cos(angle), math.sin(angle)
        tx = half_w / abs(dx) if dx != 0 else float("inf")
        ty = half_h / abs(dy) if dy != 0 else float("inf")
        t = min(tx, ty)
        return (center_x + dx * t, center_y + dy * t)

    # Always include corners at boundary crossings to prevent overlap
    # Define corner angles in CCW order (starting from top-right)
    corner_angles = [
        -math.pi / 4,     # top-right
        -3 * math.pi / 4,  # bottom-right
        -5 * math.pi / 4,  # bottom-left
        -7 * math.pi / 4,  # top-left
        -math.pi / 4 - 2 * math.pi  # wrap
    ]

    # Generate wedge path
    a = start_angle
    for corner in corner_angles:
        if end_angle < corner < a:
            points.append(intersection(corner))
        elif end_angle >= corner >= a:
            points.append(intersection(corner))
    # Uniform segment sampling for smoothness
    for i in range(segments + 1):
        angle = start_angle + (end_angle - start_angle) * (i / segments)
        points.append(intersection(angle))

    # Remove potential duplicates to prevent triangle overlap
    unique_points = []
    for p in points:
        if not unique_points or (abs(unique_points[-1][0] - p[0]) > 0.1 or abs(unique_points[-1][1] - p[1]) > 0.1):
            unique_points.append(p)

    # Draw filled triangle fan (no overlaps)
    for i in range(1, len(unique_points) - 1):
        x1, y1 = unique_points[0]
        x2, y2 = unique_points[i]
        x3, y3 = unique_points[i + 1]
        PyImGui.draw_list_add_triangle_filled(x1, y1, x2, y2, x3, y3, color)

def get_skill_target(account_data: AccountStruct, cached_skill: CachedSkillInfo) -> int | None:
    py_io = PyImGui.get_io()
    
    if not cached_skill or cached_skill.skill_id == 0:
        return None
    
    target_id = Player.GetTargetID()
    is_gadget = Agent.IsGadget(target_id)
    is_item = Agent.IsItem(target_id)
    
    if cached_skill.is_enchantment or cached_skill.is_shout:
        allegiance, _ = Agent.GetAllegiance(target_id) if target_id != 0 else (Allegiance.Neutral, None)
        
        if allegiance in [Allegiance.Ally, Allegiance.Minion, Allegiance.SpiritPet]:
            return target_id
        else:
            return Player.GetAgentID() if py_io.key_ctrl else account_data.AgentData.AgentID
    else:
        return Player.GetAgentID() if py_io.key_ctrl else target_id if not is_item and target_id else account_data.AgentData.AgentID

def draw_casting_animation(
    pos: tuple[float, float],
    size: tuple[float, float],
    min_alpha: int = 40
):
    """Draws lightweight concentric circles moving from outside toward the center (casting animation)."""
    global casting_animation_timer

    # Get elapsed time (ms â†’ s)
    t = casting_animation_timer.GetElapsedTime() / 1000.0

    # Animation parameters
    num_circles = 3               # number of simultaneous circles
    cycle_duration = 1.25         # seconds per full travel (outside â†’ center)
    max_radius = max(size) * 0.75 # start slightly outside item bounds
    min_radius = max(size) * 0.05 # small inner limit (center end)
    center_x = pos[0] + size[0] / 2
    center_y = pos[1] + size[1] / 2

    # Clamp the minimum alpha to valid range
    min_alpha = max(0, min(255, min_alpha))

    for i in range(num_circles):
        # Each circleâ€™s start offset â€” evenly staggered
        offset = i / num_circles

        # Normalized progress (0 â†’ 1), wraps every cycle
        progress = (t / cycle_duration + offset) % 1.0

        # Radius interpolates from max_radius â†’ min_radius
        radius = max_radius - (max_radius - min_radius) * progress

        # Alpha goes from 255 â†’ min_alpha (instead of fading to zero)
        alpha = int(min_alpha + (255 - min_alpha) * (1.0 - progress) ** 1.5)
        alpha = max(0, min(255, alpha))  # safety clamp

        # Optional subtle rotation effect
        swirl_angle = math.sin((t + i) * 2.0) * 0.1
        cx = center_x + math.cos(swirl_angle) * 0.0
        cy = center_y + math.sin(swirl_angle) * 0.0

        color = Color.from_tuple((0, 0, 0, alpha / 255.0))

        PyImGui.push_clip_rect(pos[0], pos[1], pos[0] + size[0], pos[1] + size[1], True)
        PyImGui.draw_list_add_circle(cx, cy, radius, color.color_int, 36, 6.0)
        PyImGui.pop_clip_rect()

def draw_skill_bar(height: float, account_data: AccountStruct, hero_options: Optional[HeroAIOptionStruct], message_queue: list[tuple[int, SharedMessageStruct]]):
    global skill_cache, messages
    style = ImGui.get_style()
    draw_textures = style.Theme in ImGui.Textured_Themes
    texture_theme = style.Theme if draw_textures else StyleTheme.Guild_Wars

    for slot, skill_info in enumerate(account_data.AgentData.Skillbar.Skills):
        
        if skill_info.Id not in skill_cache:
            skill_cache[skill_info.Id] = CachedSkillInfo(skill_info.Id)

        skill = skill_cache[skill_info.Id]
        skill_texture = skill.texture_path

        if not skill_texture:
            ImGui.dummy(height, height)
            item_rect_min = PyImGui.get_item_rect_min()

            PyImGui.draw_list_add_rect(
                item_rect_min[0],
                item_rect_min[1],
                item_rect_min[0] + height,
                item_rect_min[1] + height,
                Color(50, 50, 50, 255).color_int,
                0,
                0,
                2
            )
            PyImGui.same_line(0, 0)
            continue

        skill_recharge = skill_info.Recharge
        adrenaline = skill_info.Adrenaline
        enough_adrenaline = adrenaline >= skill.adrenaline_cost
        
        ImGui.image(skill_texture, (height, height), uv0=(
            0.0625, 0.0625) if draw_textures else (0, 0), uv1=(0.9375, 0.9375) if draw_textures else (1, 1))

        if PyImGui.is_item_hovered():
            show_skill_tooltip(skill)

        item_rect_min = PyImGui.get_item_rect_min()
        casting_skill = account_data.AgentData.Skillbar.CastingSkillID
        
        if skill_recharge > 0 and skill.recharge_time > 0:
                DrawSquareCooldownEx(
                    (item_rect_min[0], item_rect_min[1]),
                    height,
                    skill_recharge / (skill.recharge_time * 1000.0),
                    tint=0.6
                )

                text_size = PyImGui.calc_text_size(
                    f"{int(skill_recharge/1000)}")
                offset_x = (height - text_size[0]) / 2
                offset_y = (height - text_size[1]) / 2

                PyImGui.draw_list_add_text(
                    item_rect_min[0] + offset_x,
                    item_rect_min[1] + offset_y,
                    ImGui.get_style().Text.color_int,
                    f"{int(skill_recharge/1000)}"
                )
        elif casting_skill == skill.skill_id:
            draw_casting_animation(item_rect_min, (height, height))
        
        if not enough_adrenaline:             
            adrenaline_fraction = adrenaline / skill.adrenaline_cost if skill.adrenaline_cost > 0 else 0.0
            adrenaline_fraction = max(0.0, min(adrenaline_fraction, 1.0))  # Clamp between 0â€“1       
                   
            fill_rect = (item_rect_min[0], item_rect_min[1], height, height - (height * adrenaline_fraction))
            
            PyImGui.draw_list_add_rect_filled(
                fill_rect[0],
                fill_rect[1],
                fill_rect[0] + fill_rect[2],
                fill_rect[1] + fill_rect[3],
                Color(0, 0, 0, 150).color_int,
                0,
                0
            )
            
            PyImGui.draw_list_add_line(
                fill_rect[0],
                fill_rect[1] + fill_rect[3],
                fill_rect[0] + fill_rect[2],
                fill_rect[1] + fill_rect[3],
                Color(0, 0, 0, 255).color_int,
                1
            )
                
        if hero_options and not hero_options.Skills[slot]:
            hovered = PyImGui.is_item_hovered()
            ThemeTextures.Cancel.value.get_texture(texture_theme).draw_in_drawlist(
                PyImGui.get_item_rect_min(),
                (height, height),
                state=TextureState.Hovered if hovered else TextureState.Normal
            )

        account_email = Player.GetAccountEmail()
        queued_skill_messages = message_cache.get(account_email, {}).get(SharedCommandType.UseSkill, {})
        if queued_skill_messages:
            queued_skill_usage = {index: msg for index, msg in message_queue if msg.Command == SharedCommandType.UseSkill and msg.ReceiverEmail == account_email and msg.Params[1] == float(skill.skill_id) and index in queued_skill_messages}
                    
            if queued_skill_usage:
                hovered = PyImGui.is_item_hovered()
                ThemeTextures.Check.value.get_texture(texture_theme).draw_in_drawlist(
                    PyImGui.get_item_rect_min(),
                    (height, height),
                    state=TextureState.Hovered if hovered else TextureState.Normal
                )
            else:
                #delete all queued messages for this skill that were not found in new messages (probably failed)
                indices_to_delete = [index for index, msg in queued_skill_messages.items() if msg[1] == skill.skill_id]
                for index in indices_to_delete:
                    del queued_skill_messages[index]

        if PyImGui.is_item_clicked(0) and enough_adrenaline:
            io = PyImGui.get_io()
            if io.key_shift:
                if hero_options:
                    hero_options.Skills[slot] = not hero_options.Skills[slot]
                    live_options = _live_hero_options(account_data)
                    if live_options is not None:
                        live_options.Skills[slot] = hero_options.Skills[slot]

            else:
                target_id = get_skill_target(account_data, skill)
                
                if target_id is not None:
                    message_index = GLOBAL_CACHE.ShMem.SendMessage(Player.GetAccountEmail(
                    ), account_data.AccountEmail, SharedCommandType.UseSkill, (target_id, int(skill.skill_id)))

                    if account_data.AccountEmail not in message_cache:
                        message_cache[account_data.AccountEmail] = {}
                        
                    if SharedCommandType.UseSkill not in message_cache[account_data.AccountEmail]:
                        message_cache[account_data.AccountEmail][SharedCommandType.UseSkill] = {}

                    message_cache[account_data.AccountEmail][SharedCommandType.UseSkill][message_index] = (target_id, skill.skill_id)

        if draw_textures:
            texture_state = TextureState.Normal if not skill.is_elite else TextureState.Active

            ThemeTextures.Skill_Frame.value.get_texture(texture_theme).draw_in_drawlist(
                (item_rect_min[0], item_rect_min[1]),
                (height, height),
                state=texture_state
            )

        PyImGui.same_line(0, 0)

    pass 

def show_skill_tooltip(skill, show_usage=True):
    PyImGui.set_next_window_size((300, 0), PyImGui.ImGuiCond.Always)
    if ImGui.begin_tooltip():
        ImGui.push_font("Regular", 14)
        ImGui.text_colored(
                    f"{skill.name} (ID: {skill.skill_id})",
                    Color(227, 211, 165, 255).color_tuple                    
                )
        ImGui.pop_font()

        ImGui.separator()
        if skill.description:
            ImGui.text_wrapped(skill.description)
        
        if show_usage:
            PyImGui.spacing()
                    
            gray_color = Color(150, 150, 150, 255)
                    
            ImGui.push_font("Regular", 12)
            ImGui.text_colored(
                        "Click to use on current target",
                        gray_color.color_tuple                  
                    )
            PyImGui.set_cursor_pos_y(PyImGui.get_cursor_pos_y() - 2)
                    
            ImGui.text_colored(
                        "Ctrl + Click to use on self",
                        gray_color.color_tuple                
                    )
            PyImGui.set_cursor_pos_y(PyImGui.get_cursor_pos_y() - 2)
                    
            ImGui.text_colored(
                        "Shift + Click to toggle active/inactive",
                        gray_color.color_tuple              
                    )
            ImGui.pop_font()

        ImGui.end_tooltip() # Implementation of skill bar drawing logic goes here

def draw_buffs_bar(account_data: AccountStruct, win_pos: tuple, win_size: tuple, message_queue: list[tuple[int, SharedMessageStruct]], skill_size: float = 28):
    if not settings.ShowHeroEffects and not settings.ShowHeroUpkeeps:
        return

    style = ImGui.get_style()

    PyImGui.push_style_var(ImGuiStyleVar.WindowRounding,0.0)
    PyImGui.push_style_var_vec2(ImGuiStyleVar.WindowPadding, (0.0, 0.0))
    PyImGui.push_style_var(ImGuiStyleVar.WindowBorderSize,0.0)
    PyImGui.push_style_var_vec2(ImGuiStyleVar.WindowPadding, (0.0, 0.0))
    
    flags=( PyImGui.WindowFlags.NoCollapse | 
                PyImGui.WindowFlags.NoTitleBar |
                PyImGui.WindowFlags.NoScrollbar |
                PyImGui.WindowFlags.AlwaysAutoResize |
                PyImGui.WindowFlags.NoScrollWithMouse |
                PyImGui.WindowFlags.NoBringToFrontOnFocus |
                PyImGui.WindowFlags.NoResize |
                PyImGui.WindowFlags.NoBackground 
            ) 
    
    PyImGui.set_next_window_pos(
        (win_pos[0], win_pos[1] + win_size[1] + (13 if style.Theme == StyleTheme.Guild_Wars else 4)), PyImGui.ImGuiCond.Always)
    PyImGui.set_next_window_size((win_size[0], 0), PyImGui.ImGuiCond.Always)
    open = PyImGui.begin("##Buffs Bar" + account_data.AccountEmail, True, flags)
    PyImGui.pop_style_var(4)

    if open:
        draw_buffs_and_upkeeps(account_data, skill_size)
        
    PyImGui.end()
    pass  # Implementation of buffs bar drawing logic goes here

def draw_buffs_and_upkeeps(account_data: AccountStruct, skill_size: float = 28):
    style = ImGui.get_style()
    HARD_MODE_EFFECT_ID = 1912 
    
    effects = [effect for effect in account_data.AgentData.Buffs.Buffs if effect.Type == 2]
    upkeeps = [effect for effect in account_data.AgentData.Buffs.Buffs if effect.Type == 1]
    
    def draw_buff(effect: CachedSkillInfo, duration: float, remaining: float, draw_effect_frame: bool = True, skill_size: float = skill_size):
        if not effect.texture_path:
            ImGui.dummy(skill_size, skill_size)
        else:
            ImGui.image(effect.texture_path, (skill_size, skill_size), uv0=(0.125, 0.125) if not draw_effect_frame else (
                0.0625, 0.0625), uv1=(0.875, 0.875) if not draw_effect_frame else (0.9375, 0.9375))
            
        item_rect_min = PyImGui.get_item_rect_min()
        item_rect_max = PyImGui.get_item_rect_max()

        if draw_effect_frame:
            frame_texture, texture_state = effect.frame_texture, effect.texture_state
            frame_texture.draw_in_drawlist(
                (item_rect_min[0], item_rect_min[1]),
                (skill_size, skill_size),
                state=texture_state
            )

        if settings.ShowEffectDurations or settings.ShowShortEffectDurations:
            if duration > 0 and remaining and (not settings.ShowShortEffectDurations or remaining < 60000):
                progress_background_rect = (
                    item_rect_min[0] + 2, item_rect_max[1] - 4, item_rect_max[0] - 2, item_rect_max[1] - 1)

                PyImGui.draw_list_add_rect_filled(
                    progress_background_rect[0],
                    progress_background_rect[1],
                    progress_background_rect[2],
                    progress_background_rect[3],
                    Color(0, 0, 0, 255).color_int,
                    0,
                    0
                )

                progress_rect = (
                    progress_background_rect[0] + 1,
                    progress_background_rect[1] + 1,
                    progress_background_rect[2] - 2,
                    progress_background_rect[3] - 1
                )

                fraction = remaining / (duration * 1000.0)
                progress_width = (
                    progress_rect[2] - progress_rect[0]) * fraction
                PyImGui.draw_list_add_rect_filled(
                    progress_rect[0],
                    progress_rect[1],
                    progress_rect[0] + progress_width,
                    progress_rect[3],
                    effect.progress_color,
                    0,
                    0
                )

                remaining_text = f"{remaining/1000:.0f}" if remaining >= 1000 else f"{remaining/1000:.1f}".lstrip("0")
                    
                text_size = PyImGui.calc_text_size(remaining_text)
                offset_x = (skill_size - text_size[0]) / 2
                offset_y = (skill_size - text_size[1]) / 2

                PyImGui.draw_list_add_rect_filled(
                    item_rect_min[0] + offset_x - 1,
                    item_rect_min[1] + offset_y - 1,
                    item_rect_min[0] + offset_x + text_size[0] + 1,
                    item_rect_min[1] + offset_y + text_size[1] + 1,
                    Color(0, 0, 0, 150).color_int,
                    2,
                    0
                )
                PyImGui.draw_list_add_text(
                    item_rect_min[0] + offset_x,
                    item_rect_min[1] + offset_y,
                    style.Text.color_int,
                    remaining_text
                )


        if PyImGui.is_item_hovered():
            show_skill_tooltip(effect, show_usage=False)
    
    def draw_morale(morale : int, skill_size: float = skill_size):
        morale_display = f"{("+" if morale > 100 else "-")}{abs(100 - morale)}%"
        texture = ThemeTextures.DeathPenalty.value.get_texture() if morale < 100 else ThemeTextures.MoraleBoost.value.get_texture()
        ImGui.push_font("Regular", 11)            
        ImGui.dummy(skill_size, skill_size)
        item_rect_min = PyImGui.get_item_rect_min()
        item_rect_max = PyImGui.get_item_rect_max()
        
        item_rect = (item_rect_min[0], item_rect_min[1], item_rect_max[0] - item_rect_min[0], item_rect_max[1] - item_rect_min[1])
        texture.draw_in_drawlist(
            item_rect[:2],
            (skill_size, skill_size),
        )
        text_size = PyImGui.calc_text_size(morale_display)
        offset_x = (skill_size - text_size[0]) / 2
        offset_y = (skill_size - text_size[1])
        PyImGui.draw_list_add_text(
            item_rect[0] + offset_x,
            item_rect[1] + offset_y,
            Color(201, 188, 145, 255).color_int,
            morale_display
        )

        ImGui.pop_font()
        PyImGui.table_next_column()
    
    def draw_hardmode():
        # hardmode completed 1912
        if any(effect.SkillId == HARD_MODE_EFFECT_ID for effect in effects):
            if not HARD_MODE_EFFECT_ID in skill_cache:
                skill_cache[HARD_MODE_EFFECT_ID] = CachedSkillInfo(HARD_MODE_EFFECT_ID)

            to_kill = Map.GetFoesToKill()
            
            if to_kill > 0:
                texture = ThemeTextures.HardMode.value.get_texture(StyleTheme.Guild_Wars)
                pass
            else:
                texture = ThemeTextures.HardModeCompleted.value.get_texture(StyleTheme.Guild_Wars)
        
            ImGui.dummy(skill_size + 1, skill_size + 1)
            item_rect_min, item_rect_max, item_rect_size = ImGui.get_item_rect()
            texture.draw_in_drawlist(
                (item_rect_min[0], item_rect_min[1]),
                (skill_size + 1, skill_size + 1),
            )
                
            PyImGui.table_next_column()
        pass
    
    if settings.ShowHeroUpkeeps:
        ImGui.dummy(0, 24)
        PyImGui.same_line(0, 0)
        
        for index, upkeep in enumerate(upkeeps):
            if upkeep.SkillId == 0:
                continue

            if not upkeep.SkillId in skill_cache:
                skill_cache[upkeep.SkillId] = CachedSkillInfo(upkeep.SkillId)

            effect = skill_cache[upkeep.SkillId]
            duration = upkeep.Duration
            remaining = upkeep.Remaining

            draw_buff(effect, duration, remaining, False, 24)

        if any(upkeeps) and any(effects) and settings.ShowHeroEffects:
            PyImGui.new_line()
            PyImGui.set_cursor_pos_y(PyImGui.get_cursor_pos_y() - 4)

    if settings.ShowHeroEffects:     
        avail = PyImGui.get_content_region_avail()[0]
        style.CellPadding.push_style_var(0, 0)
        if ImGui.begin_table("##effects_table" + account_data.AccountEmail, max(1, round(avail / skill_size)), PyImGui.TableFlags.SizingFixedFit):
            PyImGui.table_next_row()
            PyImGui.table_next_column()
            
            if account_data.AgentData.Morale != 100 and account_data.AgentData.Morale != 0:
                draw_morale(account_data.AgentData.Morale, skill_size)
                            
            draw_hardmode()
            
            #get each effect with unique id and take the longest duration for that id
            player_effects = {}
            
            for index, effect in enumerate(effects):
                remaining = effect.Remaining
                duration = effect.Duration
                effect_id = effect.SkillId
                
                if not effect_id or effect_id == HARD_MODE_EFFECT_ID:
                    continue
                
                if not effect_id in skill_cache:
                    skill_cache[effect_id] = CachedSkillInfo(effect_id)
                    
                if not effect_id in player_effects:
                    player_effects[effect_id] = (skill_cache[effect_id], remaining, duration)
                
                else:
                    cached_effect, existing_remaining, existing_duration = player_effects[effect_id]
                    
                    if remaining > existing_remaining:
                        player_effects[effect_id] = (cached_effect, remaining, duration)
                        
            for effect_id, (effect, remaining, duration) in player_effects.items():
                row = PyImGui.table_get_row_index()
                if row > settings.MaxEffectRows - 1:
                    break
                
                draw_buff(effect, duration, remaining, True, 28)
                PyImGui.table_next_column()
            
            ImGui.end_table() 
        style.CellPadding.pop_style_var()
            
        PyImGui.new_line()

def enter_skill_template_code(account_data : AccountStruct):
    global template_popup_open, template_code, template_account
    
    if not template_popup_open:
        return
    
    if template_popup_open:
        PyImGui.open_popup("Enter Skill Template Code")
    
    # PyImGui.set_next_window_size((300, 100), PyImGui.ImGuiCond.Always)
    PyImGui.set_window_pos(500 , 100, PyImGui.ImGuiCond.Always)
    if PyImGui.begin_popup("Enter Skill Template Code"):
        template_code = ImGui.input_text("##template_code", template_code)

        if ImGui.button("Load"):
            GLOBAL_CACHE.ShMem.SendMessage(
                Player.GetAccountEmail(),
                account_data.AccountEmail,           
                SharedCommandType.LoadSkillTemplate,
                ExtraData=(template_code, 0, 0, 0)
            )
            
            template_popup_open = False
            PyImGui.close_current_popup() 
            
        PyImGui.same_line(0, 10)
        if ImGui.button("Cancel"):
            PyImGui.close_current_popup()             
            template_popup_open = False

        if PyImGui.is_mouse_clicked(0) and not PyImGui.is_any_item_hovered():
            PyImGui.close_current_popup()             
            template_popup_open = False
            
        PyImGui.end_popup()
        
def draw_buttons(account_data: AccountStruct, cached_data: CacheData, message_queue: list[tuple[int, SharedMessageStruct]], btn_size: float = 28):
    global message_cache
    style = ImGui.get_style()
    draw_textures = style.Theme in ImGui.Textured_Themes
    
    global template_popup_open, template_account
    is_explorable = Map.IsExplorable()
    if not ImGui.begin_child("##buttons" + account_data.AccountEmail, (84, 58), False,
                             PyImGui.WindowFlags.NoScrollbar | PyImGui.WindowFlags.NoScrollWithMouse):
        ImGui.end_child()
        return

    style = ImGui.get_style()
    same_map = Map.GetMapID() == account_data.AgentData.Map.MapID and Map.GetRegion()[0] == account_data.AgentData.Map.Region and Map.GetDistrict() == account_data.AgentData.Map.District
    player_email = Player.GetAccountEmail()
    account_email = account_data.AccountEmail

    btn_size = btn_size if draw_textures else btn_size - 1

    def is_queued(command: SharedCommandType, clear: bool = False) -> bool:
        cached_commands = message_cache.get(account_email, {}).get(command, {})

        if cached_commands:
            queued_commands = {index: msg for index, msg in message_queue if msg.Command == command and msg.ReceiverEmail == account_email and index in cached_commands} 
            if not queued_commands:
                if clear:
                    cached_commands.clear()
                           
            return len(queued_commands) > 0
        
        return False
            
    def draw_button(id_suffix: str, icon: str, tooltip: str, command: SharedCommandType, send_message: Callable[[], int] = lambda: False, get_status: Callable[[], bool] = lambda: False, new_line: bool = False):        
        """Reusable button creation logic with hover, icon, and tooltip."""
        btn_id = f"##{id_suffix}{account_email}"
        status = get_status()
        is_command_queued = is_queued(command, clear=True)
        
        if (draw_textures and PyImGui.invisible_button(btn_id, (btn_size, btn_size))) or (not draw_textures and ImGui.button(btn_id, btn_size, btn_size)):
            if is_command_queued:
                return               
            
            message_index = send_message()            
            if message_index > -1:
                if account_data.AccountEmail not in message_cache:
                    message_cache[account_data.AccountEmail] = {}
                    
                if command not in message_cache[account_data.AccountEmail]:
                    message_cache[account_data.AccountEmail][command] = {}
                
                message_cache[account_data.AccountEmail][command][message_index] = ()


        hovered = PyImGui.is_item_hovered()
        item_rect_min = PyImGui.get_item_rect_min()
        if draw_textures:
            ThemeTextures.HeroPanelButtonBase.value.get_texture().draw_in_drawlist(
                item_rect_min, (btn_size, btn_size),
                state=TextureState.Active if status else TextureState.Normal,
                tint=(255, 255, 255, 255) if hovered else (200, 200, 200, 255)
            )

        ImGui.push_font("Regular", 10)
        text_size = PyImGui.calc_text_size(icon)
        PyImGui.draw_list_add_text(
            item_rect_min[0] + (btn_size - text_size[0]) / 2,
            item_rect_min[1] + (btn_size - text_size[1]) / 2,
            style.Text.color_int,
            icon
        )
        ImGui.pop_font()
        
        if hovered:
            ImGui.show_tooltip(tooltip)
        
        if not new_line:
            PyImGui.same_line(0, 0 if draw_textures else 1)
        else:
            PyImGui.set_cursor_pos_y(PyImGui.get_cursor_pos_y() - 4)

    if not is_explorable:
        player_x, player_y = Player.GetXY()
        target_id = Player.GetTargetID() or Player.GetAgentID()
        summon_command = SharedCommandType.TravelToGuildHall if Map.IsGuildHall() else SharedCommandType.TravelToMap

        def invite_player():            
            if same_map:
                GLOBAL_CACHE.Party.Players.InvitePlayer(account_data.AgentData.CharacterName)
                return GLOBAL_CACHE.ShMem.SendMessage(
                    player_email,
                    account_email,
                    SharedCommandType.InviteToParty,
                    (account_data.AgentData.AgentID, 0, 0, 0),
                )

            return GLOBAL_CACHE.ShMem.SendMessage(
                player_email,
                account_email,
                summon_command,
                (
                    (0, 0, 0, 0)
                    if Map.IsGuildHall()
                    else (
                        Map.GetMapID(),
                        Map.GetRegion()[0],
                        Map.GetDistrict(),
                        Map.GetLanguage()[0],
                    )
                ),
            )
        
        def load_template():
            global template_popup_open, template_code, template_account
            template_popup_open = True  
            template_code = ""
            template_account = account_data.AccountEmail
            
            return -1       
            
        buttons = [
            (
                "pixel_stack",
                commands.PixelStack.icon,
                commands.PixelStack.name,
                SharedCommandType.PixelStack,
                lambda: GLOBAL_CACHE.ShMem.SendMessage(player_email, account_email, SharedCommandType.PixelStack, (player_x, player_y, 0, 0)),
                lambda: is_queued(SharedCommandType.PixelStack),
            ),
            (
                "interact",
                IconsFontAwesome5.ICON_HAND_POINT_RIGHT,
                "Interact with Target",
                SharedCommandType.InteractWithTarget,
                lambda: GLOBAL_CACHE.ShMem.SendMessage(player_email, account_email, SharedCommandType.InteractWithTarget, (target_id, 0, 0, 0)),
                lambda: is_queued(SharedCommandType.InteractWithTarget),
            ),
            (
                "dialog",
                IconsFontAwesome5.ICON_COMMENT_DOTS,
                "Dialog with Target",
                SharedCommandType.TakeDialogWithTarget,
                lambda: GLOBAL_CACHE.ShMem.SendMessage(player_email, account_email, SharedCommandType.TakeDialogWithTarget, (target_id, 0, 0, 0)),
                lambda: is_queued(SharedCommandType.TakeDialogWithTarget),
                True,
            ),
            (
                "load_template",
                IconsFontAwesome5.ICON_FILE_IMPORT,
                "Load Skill Template",
                SharedCommandType.LoadSkillTemplate,
                load_template,
                lambda: is_queued(SharedCommandType.LoadSkillTemplate),
            ),
            (
                "invite_summon",
                IconsFontAwesome5.ICON_USER_PLUS,
                "Invite" if same_map else "Summon",
                SharedCommandType.InviteToParty if same_map else summon_command,
                invite_player,
                lambda: is_queued(SharedCommandType.InviteToParty) if same_map else is_queued(summon_command),
            ),
            (
                "focus_client",
                IconsFontAwesome5.ICON_DESKTOP,
                "Focus client",
                SharedCommandType.SetWindowActive,
                lambda: GLOBAL_CACHE.ShMem.SendMessage(
                    player_email,
                    account_email,
                    SharedCommandType.SetWindowActive,
                    (0, 0, 0, 0),
                ),
                lambda: is_queued(SharedCommandType.SetWindowActive),
            ),
        ]


        for btn in buttons:
            draw_button(*btn)
        
        if template_account == account_data.AccountEmail and template_account:    
            enter_skill_template_code(account_data)  

    else:        
        player_x, player_y = Player.GetXY()
        target_id = Player.GetTargetID() or Player.GetAgentID()
        
        def flag_hero_account():
            from .ui_base import HeroAI_BaseUI
            party_pos = int(account_data.AgentPartyData.PartyPosition)
            hero_count = int(GLOBAL_CACHE.Party.GetHeroCount() or 0)
            HeroAI_BaseUI.capture_flag_all = False
            HeroAI_BaseUI.capture_hero_flag = True
            HeroAI_BaseUI.capture_hero_index = party_pos if account_data.IsHero else party_pos + hero_count
            return -1
        
        def clear_hero_flag():
            live_options = _live_hero_options(account_data)
            if live_options is not None:
                live_options.IsFlagged = False
                live_options.FlagPos.x = 0.0
                live_options.FlagPos.y = 0.0
                live_options.AllFlag.x = 0.0
                live_options.AllFlag.y = 0.0
                live_options.FlagFacingAngle = 0.0
            options = cached_data.party.options.get(account_data.AgentData.AgentID)
            if options:
                options.IsFlagged = False
                options.FlagPos.x = 0.0
                options.FlagPos.y = 0.0
                options.AllFlag.x = 0.0
                options.AllFlag.y = 0.0
                options.FlagFacingAngle = 0.0
            party_pos = int(account_data.AgentPartyData.PartyPosition)
            if 0 < party_pos <= GLOBAL_CACHE.Party.GetHeroCount():
                GLOBAL_CACHE.Party.Heroes.UnflagHero(party_pos)
            return -1
        
        buttons = [
            # (id_suffix, icon, tooltip, command, args)
            ("pixel_stack", IconsFontAwesome5.ICON_COMPRESS_ARROWS_ALT, "Pixel Stack",
             SharedCommandType.PixelStack, lambda: GLOBAL_CACHE.ShMem.SendMessage(player_email, account_email, SharedCommandType.PixelStack, (player_x, player_y, 0, 0)), lambda: is_queued(SharedCommandType.PixelStack)),

            ("interact", IconsFontAwesome5.ICON_HAND_POINT_RIGHT, "Interact with Target",
             SharedCommandType.InteractWithTarget, lambda: GLOBAL_CACHE.ShMem.SendMessage(player_email, account_email, SharedCommandType.InteractWithTarget, (target_id, 0, 0, 0)), lambda: is_queued(SharedCommandType.InteractWithTarget)),

            ("dialog", IconsFontAwesome5.ICON_COMMENT_DOTS, "Dialog with Target",
             SharedCommandType.TakeDialogWithTarget, lambda: GLOBAL_CACHE.ShMem.SendMessage(player_email, account_email, SharedCommandType.TakeDialogWithTarget, (target_id, 0, 0, 0)), lambda: is_queued(SharedCommandType.TakeDialogWithTarget), True),

            ("flag", IconsFontAwesome5.ICON_FLAG, "Flag Target",
             SharedCommandType.NoCommand, flag_hero_account, lambda: IsHeroFlagged(account_data.AgentPartyData.PartyPosition if account_data.IsHero else int(account_data.AgentPartyData.PartyPosition) + int(GLOBAL_CACHE.Party.GetHeroCount() or 0))),

            ("clear flag", IconsFontAwesome5.ICON_CIRCLE_XMARK, "Clear Flag",
             SharedCommandType.NoCommand, clear_hero_flag, lambda: False),
            
            ("focus client",
             IconsFontAwesome5.ICON_DESKTOP,
             "Focus client",
             SharedCommandType.SetWindowActive, lambda: GLOBAL_CACHE.ShMem.SendMessage(
                player_email,
                account_email,
                SharedCommandType.SetWindowActive,
                (0, 0, 0, 0),
             )),
        ]
        
        for btn in buttons:
            draw_button(*btn)
                        
    ImGui.end_child()

title_names: dict[str, str] = {}

def get_display_name(account_data: AccountStruct) -> str:    
    name = account_data.AgentData.CharacterName        
    titles = [
        "the Brave",
        "the Mighty",
        "the Swift",
        "the Cunning",
        "the Wise",
        "the Fearless",
        "the Valiant",
        "the Bold",
        "the Fierce",
        "the Gallant",
        "the Noble",
        "the Daring",
        "the Resolute",
        "the Stalwart",
        "the Intrepid",
        "the Dauntless",
        "the Adventurous",
        "the Courageous",
        "the Heroic",
        "the Legendary"
    ]
    
    if not name in title_names:
        title_names[name] = "Robin " + random.choice(titles)
        
    name = title_names[name]
    return name if settings.Anonymous_PanelNames else account_data.AgentData.CharacterName

def get_conditioned(account_data: AccountStruct) -> tuple[HealthState, bool, bool, bool, bool, bool]:
    buff_ids = [buff.SkillId for buff in account_data.AgentData.Buffs.Buffs]
    same_map = Map.GetMapID() == account_data.AgentData.Map.MapID and Map.GetRegion()[0] == account_data.AgentData.Map.Region and Map.GetDistrict() == account_data.AgentData.Map.District
    
    deep_wounded = 482 in buff_ids
    poisoned = 484 in buff_ids or 483 in buff_ids
    
    enchanted = Agent.IsEnchanted(account_data.AgentData.AgentID) if same_map else False
    conditioned = Agent.IsConditioned(account_data.AgentData.AgentID) if same_map else False
    hexed = Agent.IsHexed(account_data.AgentData.AgentID) if same_map else False
    has_weaponspell = Agent.IsWeaponSpelled(account_data.AgentData.AgentID) if same_map else False
        
    if poisoned:
        return HealthState.Poisoned, deep_wounded, enchanted, conditioned, hexed, has_weaponspell
    
    bleeding = 478 in buff_ids
    if bleeding:
        return HealthState.Bleeding, deep_wounded, enchanted, conditioned, hexed, has_weaponspell
    
    degen_hexed = Agent.IsDegenHexed(account_data.AgentData.AgentID) if same_map else False
    if degen_hexed:
        return HealthState.DegenHexed, deep_wounded, enchanted, conditioned, hexed, has_weaponspell
    
    return HealthState.Normal, deep_wounded, enchanted, conditioned, hexed, has_weaponspell

def draw_combined_hero_panel(account_data: AccountStruct, cached_data: CacheData, messages: list[tuple[int, SharedMessageStruct]], open: bool = True):
    window_info = settings.get_hero_panel_info(account_data.AccountEmail)
    if not window_info or not window_info.open:
        return
    
    options = cached_data.party.options.get(account_data.AgentData.AgentID)
    name = get_display_name(account_data)
    
    style = ImGui.get_style()
    ImGui.dummy(PyImGui.get_content_region_avail()[0], 22)
    
    item_rect_min = PyImGui.get_item_rect_min()
    item_rect_max = PyImGui.get_item_rect_max()
    item_rect = (item_rect_min[0], item_rect_min[1] + 5, item_rect_max[0] - item_rect_min[0], item_rect_max[1] - item_rect_min[1])
    
    ThemeTextures.HeaderLabelBackground.value.get_texture().draw_in_drawlist(
        item_rect[:2],
        item_rect[2:],
        tint=(225, 225, 225, 200) if style.Theme is StyleTheme.Guild_Wars else (255, 255, 255, 255)
    )
    
    text_size = PyImGui.calc_text_size(name)
    text_pos = (item_rect[0] + (item_rect[2] - text_size[0]) / 2, item_rect[1] + 2 + (item_rect[3] - text_size[1]) / 2)
    ImGui.push_font("Regular", 14)
    PyImGui.draw_list_add_text(
        text_pos[0],
        text_pos[1],
        style.Text.color_int,
        name
    )
    ImGui.pop_font()
    
    height = 28 if settings.ShowHeroSkills else 0
    height += 28 if settings.ShowHeroBars else 0
    height += 4 if settings.ShowHeroBars and settings.ShowHeroSkills else 0

    if height > 0:
        if ImGui.begin_child("##bars" + account_data.AccountEmail, (225, height)):
            curr_avail = PyImGui.get_content_region_avail()
            if settings.ShowHeroBars:
                health_state, deep_wounded, enchanted, conditioned, hexed, has_weaponspell = get_conditioned(account_data)
                
                health_clicked = draw_health_bar(curr_avail[0], 13, account_data.AgentData.Health.Max,
                                account_data.AgentData.Health.Current, account_data.AgentData.Health.Regen, health_state, deep_wounded, enchanted, conditioned, hexed, has_weaponspell)   
                                     
                PyImGui.set_cursor_pos_y(PyImGui.get_cursor_pos_y() - 4)
                
                energy_clicked = draw_energy_bar(curr_avail[0], 13, account_data.AgentData.Energy.Max,
                                account_data.AgentData.Energy.Current, account_data.AgentData.Energy.Regen)
                
                if health_clicked or energy_clicked:
                            if Map.GetMapID() == account_data.AgentData.Map.MapID:
                                Player.ChangeTarget(account_data.AgentData.AgentID)
                                
            if settings.ShowHeroSkills:
                if settings.ShowHeroBars:
                    PyImGui.set_cursor_pos_y(PyImGui.get_cursor_pos_y() - 4)
                
                draw_skill_bar(28, account_data, options, messages)

        ImGui.end_child()

    if (settings.ShowHeroBars or settings.ShowHeroSkills) and settings.ShowHeroButtons:
        PyImGui.same_line(0, 2)
        
    if settings.ShowHeroButtons:
        draw_buttons(account_data, cached_data, messages, 28)

    draw_buffs_and_upkeeps(account_data, 28)    

def draw_hero_panel(window: WindowModule, account_data: AccountStruct, cached_data: CacheData, messages: list[tuple[int, SharedMessageStruct]]):   
    window_info = settings.get_hero_panel_info(account_data.AccountEmail)
    if not window_info or not window_info.open:
        return
    
    window.open = window_info.open
    window.collapse = window_info.collapsed
    options = cached_data.party.options.get(account_data.AgentData.AgentID)
    
    global title_names
    style = ImGui.get_style()
    style.WindowPadding.push_style_var(4, 1)
    
    collapsed = window.collapse
    player_pos = Player.GetXY()
    hero_pos = (account_data.AgentData.Pos.x, account_data.AgentData.Pos.y)
    outside_compass_range = Utils.Distance(player_pos, hero_pos) > Range.Compass.value + 10
    
    if outside_compass_range:
        style.TitleBg.push_color((100, 0, 0, 150))
        style.WindowBg.push_color((100, 0, 0, 150))
    PyImGui.set_next_window_size(319, (69 if style.Theme is StyleTheme.Guild_Wars else 86) + 26 if options else 0)
    open = window.begin(None, PyImGui.WindowFlags.NoResize)
    # ConsoleLog("HeroAI", f"{window.window_size}")
    if outside_compass_range:
        style.WindowBg.pop_color()
        style.TitleBg.pop_color()
    style.WindowPadding.pop_style_var()

    prof_primary, prof_secondary = "", ""
    prof_primary = ProfessionShort(
        account_data.AgentData.Profession[0]).name if account_data.AgentData.Profession[0] != 0 else ""
    prof_secondary = ProfessionShort(
        account_data.AgentData.Profession[1]).name if account_data.AgentData.Profession[1] != 0 else ""
    win_size = PyImGui.get_window_size()
    win_pos = PyImGui.get_window_pos()

    text_pos = (win_pos[0] + 25, win_pos[1] - 23 +
                7) if style.Theme == StyleTheme.Guild_Wars else (win_pos[0] + 25, win_pos[1] + 7)

    PyImGui.push_clip_rect(
        win_pos[0], win_pos[1] - 20, win_size[0] - 30, 50, False)
    ImGui.push_font("Regular", 13)
        
    name = get_display_name(account_data)

    PyImGui.draw_list_add_text(text_pos[0], text_pos[1], style.Text.color_int,
                               f"{prof_primary}{("/" if prof_secondary else "")}{prof_secondary}{account_data.AgentData.Level} {name}")
    ImGui.pop_font()
    PyImGui.pop_clip_rect()

    pos = window.window_pos
    collapsed = window.collapse
    
    if open and window.open and not window.collapse:
        if style.Theme == StyleTheme.Guild_Wars:
            PyImGui.spacing()

        avail = PyImGui.get_content_region_avail()

        height = 28 if settings.ShowHeroSkills else 0
        height += 28 if settings.ShowHeroBars else 0
        height += 4 if settings.ShowHeroBars and settings.ShowHeroSkills else 0

        if height > 0:
            if ImGui.begin_child("##bars" + account_data.AccountEmail, (225, height)):
                curr_avail = PyImGui.get_content_region_avail()
                if settings.ShowHeroBars:
                    health_state, deep_wounded, enchanted, conditioned, hexed, has_weaponspell  = get_conditioned(account_data)
                    
                    health_clicked = draw_health_bar(curr_avail[0], 13, account_data.AgentData.Health.Max,
                                    account_data.AgentData.Health.Current, account_data.AgentData.Health.Regen, health_state, deep_wounded, enchanted, conditioned, hexed, has_weaponspell )
                    PyImGui.set_cursor_pos_y(PyImGui.get_cursor_pos_y() - 4)
                    energy_clicked = draw_energy_bar(curr_avail[0], 13, account_data.AgentData.Energy.Max,
                                                       account_data.AgentData.Energy.Current, account_data.AgentData.Energy.Regen)
                    if health_clicked or energy_clicked:
                        if Map.GetMapID() == account_data.AgentData.Map.MapID:
                            Player.ChangeTarget(account_data.AgentData.AgentID)
                            
                if settings.ShowHeroSkills:
                    if settings.ShowHeroBars:
                        PyImGui.set_cursor_pos_y(PyImGui.get_cursor_pos_y() - 4)
                    
                    draw_skill_bar(28, account_data, options, messages)

            ImGui.end_child()

        if (settings.ShowHeroBars or settings.ShowHeroSkills) and settings.ShowHeroButtons:
            PyImGui.same_line(0, 2)
            
        if settings.ShowHeroButtons:
            draw_buttons(account_data, cached_data, messages, 28)
        
        
        if options:
            opt_dict = {"Following" : options.Following, "Avoidance" : options.Avoidance, "Looting" : options.Looting, "Targeting" : options.Targeting, "Combat" : options.Combat}
        
            PyImGui.set_cursor_pos_y(PyImGui.get_cursor_pos_y() - 2)
            
            for name, value in opt_dict.items():
                ImGui.push_font("Regular", 10)
                active = ImGui.toggle_button(name + f"##{account_data.AccountEmail}", value, 319 / len(opt_dict) - 3, 20)
                ImGui.pop_font()
                
                if active != value:
                    ConsoleLog("HeroAI", f"Set {name} to {active} for hero {account_data.AgentData.CharacterName} | Party Position {account_data.AgentPartyData.PartyPosition}")
                    live_options = _live_hero_options(account_data)
                    if live_options is not None and hasattr(live_options, name):
                        setattr(live_options, name, active)
                    setattr(options, name, active)
                
                PyImGui.same_line(0, 2)

        
        draw_buffs_bar(account_data, win_pos, win_size, messages, 28)
        window.process_window()
    
    collapsed = PyImGui.is_window_collapsed()
    
    window.process_window()
    window.collapse = collapsed if style.Theme != StyleTheme.Guild_Wars else window.collapse
    
    if window.collapse != window_info.collapsed or window.changed or window.open != window_info.open:            
        if PySystem.Console.is_window_active():
            window_info.open = window.open
            window_info.collapsed = window.collapse
            window_info.x = round(window.window_pos[0])
            window_info.y = round(window.window_pos[1])
            
            settings.save_settings()
        
    window.end()
            
        
    pass  # Implementation of hero panel drawing logic goes here

def draw_button(id_suffix: str, icon: str, w : float = 0, h : float = 0, active : bool = False, enabled : bool = True) -> bool:       
    style = ImGui.get_style()
    draw_textures = style.Theme in ImGui.Textured_Themes    
    btn_id = f"##{id_suffix}"    
    clicked = (draw_textures and PyImGui.invisible_button(btn_id, (w, h))) or (not draw_textures and ImGui.button(btn_id, w, h))


    hovered = PyImGui.is_item_hovered()
    mouse_down = PyImGui.is_mouse_down(0)
    item_rect_min = PyImGui.get_item_rect_min()
    if draw_textures:
        ThemeTextures.HeroPanelButtonBase.value.get_texture().draw_in_drawlist(
            item_rect_min, (w, h),
            state=TextureState.Active if active else TextureState.Normal,
            tint=(255, 255, 255, 85) if not enabled else (255, 255, 255, 255) if hovered and mouse_down else (200, 200, 200, 255) if hovered else (175, 175, 175, 255)
        )

    ImGui.push_font("Regular", 10)
    text_size = PyImGui.calc_text_size(icon)
    PyImGui.draw_list_add_text(
        item_rect_min[0] + (w - text_size[0]) / 2,
        item_rect_min[1] + (h - text_size[1]) / 2,
        style.Text.color_int if enabled else Color(115, 115, 115, 255).color_int,
        icon
    )
    ImGui.pop_font()   
    return clicked and enabled

def send_command_to_all_heroes(accounts: list[AccountStruct], command: SharedCommandType, param: tuple = (), extra_data: tuple = (), include_self: bool = False):
    account_mail = Player.GetAccountEmail()
    for account in accounts:
        if not include_self and account.AccountEmail == account_mail:
            continue
        
        GLOBAL_CACHE.ShMem.SendMessage(
            account_mail,
            account.AccountEmail,
            command,
            param,
            ExtraData=extra_data
        )

# Category sentinels. Negative values are UI/runtime categories, never real item ModelIDs.
_TOWN_CAKE_SENTINEL = -10001
_LUNAR_FORTUNE_SENTINEL = -10002
_XP_SCROLL_SENTINEL = -10003
_RES_SCROLL_SENTINEL = -10004

consumables = [
    (ModelID.Essence_Of_Celerity, ("Assets\\Textures\\Consumables\\Trimmed\\Essence_of_Celerity.png", (ModelID.Essence_Of_Celerity.value, GLOBAL_CACHE.Skill.GetID("Essence_of_Celerity_item_effect"), 0, 0))),
    (ModelID.Grail_Of_Might, ("Assets\\Textures\\Consumables\\Trimmed\\Grail_of_Might.png", (ModelID.Grail_Of_Might.value, GLOBAL_CACHE.Skill.GetID("Grail_of_Might_item_effect"), 0, 0))),
    (ModelID.Armor_Of_Salvation, ("Assets\\Textures\\Consumables\\Trimmed\\Armor_of_Salvation.png", (ModelID.Armor_Of_Salvation.value, GLOBAL_CACHE.Skill.GetID("Armor_of_Salvation_item_effect"), 0, 0))),

    # Category buttons. The icon is only a visual representative; runtime can use
    # any supported item from that category that exists in THIS account's inventory.
    (ModelID.Dwarven_Ale, ("Assets\\Textures\\Consumables\\Trimmed\\Dwarven_Ale.png", (ModelID.Dwarven_Ale.value, 0, 0, 0))),
    (_TOWN_CAKE_SENTINEL, ("Assets\\Textures\\Item Models\\36681-Delicious_Cake.png", (0, 0, 0, 0))),
    (ModelID.Rainbow_Candy_Cane, ("Assets\\Textures\\Consumables\\Trimmed\\Rainbow_Candy_Cane.png", (ModelID.Rainbow_Candy_Cane.value, 0, ModelID.Honeycomb.value, 0))),

    # Death Penalty and Powerstone are event-driven. Pumpkin Cookie uses the same
    # icon group here but is continuous self-morale upkeep while enabled.
    (ModelID.Four_Leaf_Clover, ("Assets\\Textures\\Item Models\\22191-Four_Leaf_Clover.png", (0, 0, 0, 0))),
    (ModelID.Pumpkin_Cookie, ("Assets\\Textures\\Item Models\\28433-Pumpkin_Cookie.png", (ModelID.Pumpkin_Cookie.value, 0, 0, 0))),
    (ModelID.Powerstone_Of_Courage, ("Assets\\Textures\\Consumables\\Powerstone_of_Courage.png", (ModelID.Powerstone_Of_Courage.value, 0, 0, 0))),

    (ModelID.Birthday_Cupcake, ("Assets\\Textures\\Consumables\\Trimmed\\Birthday_Cupcake.png", (ModelID.Birthday_Cupcake.value, GLOBAL_CACHE.Skill.GetID("Birthday_Cupcake_skill"), 0, 0))),
    (ModelID.Candy_Apple, ("Assets\\Textures\\Consumables\\Trimmed\\Candy_Apple.png", (ModelID.Candy_Apple.value, GLOBAL_CACHE.Skill.GetID("Candy_Apple_skill"), 0, 0))),
    (ModelID.Candy_Corn, ("Assets\\Textures\\Consumables\\Trimmed\\Candy_Corn.png", (ModelID.Candy_Corn.value, GLOBAL_CACHE.Skill.GetID("Candy_Corn_skill"), 0, 0))),
    (ModelID.Golden_Egg, ("Assets\\Textures\\Consumables\\Trimmed\\Golden_Egg.png", (ModelID.Golden_Egg.value, GLOBAL_CACHE.Skill.GetID("Golden_Egg_skill"), 0, 0))),
    (ModelID.Slice_Of_Pumpkin_Pie, ("Assets\\Textures\\Consumables\\Trimmed\\Slice_of_Pumpkin_Pie.png", (ModelID.Slice_Of_Pumpkin_Pie.value, GLOBAL_CACHE.Skill.GetID("Pie_Induced_Ecstasy"), 0, 0))),
    (ModelID.War_Supplies, ("Assets\\Textures\\Consumables\\Trimmed\\War_Supplies.png", (ModelID.War_Supplies.value, GLOBAL_CACHE.Skill.GetID("Well_Supplied"), 0, 0))),

    (ModelID.Drake_Kabob, ("Assets\\Textures\\Consumables\\Trimmed\\Drake_Kabob.png", (ModelID.Drake_Kabob.value, GLOBAL_CACHE.Skill.GetID("Drake_Skin"), 0, 0))),
    (ModelID.Bowl_Of_Skalefin_Soup, ("Assets\\Textures\\Consumables\\Trimmed\\Bowl_of_Skalefin_Soup.png", (ModelID.Bowl_Of_Skalefin_Soup.value, GLOBAL_CACHE.Skill.GetID("Skale_Vigor"), 0, 0))),
    (ModelID.Pahnai_Salad, ("Assets\\Textures\\Consumables\\Trimmed\\Pahnai_Salad.png", (ModelID.Pahnai_Salad.value, GLOBAL_CACHE.Skill.GetID("Pahnai_Salad_item_effect"), 0, 0))),

    # Special grouped/event-driven buttons.
    (_LUNAR_FORTUNE_SENTINEL, ("Assets\\Textures\\Item Models\\29424-Lunar_Fortune.png", (0, 0, 0, 0))),
    (_XP_SCROLL_SENTINEL, ("Assets\\Textures\\Item Models\\05595-Scroll_of_Berserkers_Insight.png", (0, 0, 0, 0))),
    (_RES_SCROLL_SENTINEL, ("Assets\\Textures\\Item Models\\26501-Scroll_Of_Resurrection.png", (0, 0, 0, 0))),
]

# Per-account persistent auto-upkeep state. Every injected GW account keeps its
# own icon selection and its own account-level master switch.
_consumable_auto_settings = NativeSettings("HeroAI/ConsumableAuto.ini", "account")
_CONSUMABLE_AUTO_SECTION = "AutoUpkeep"
_CONSUMABLE_MASTER_SECTION = "Master"
_CONSUMABLE_ACCOUNT_MASTER_KEY = "enabled"

# Machine-global leader command. The LIVE party leader can reset every injected
# account to the same Auto ON/OFF state. Followers apply each command once, then
# remain free to override their own account locally until the leader clicks again.
_consumable_global_settings = NativeSettings("HeroAI/ConsumableAutoGlobal.ini", "global")
_CONSUMABLE_GLOBAL_MASTER_SECTION = "Master"
_CONSUMABLE_GLOBAL_MASTER_KEY = "enabled"
_CONSUMABLE_GLOBAL_COMMAND_TOGGLE_KEY = "command_toggle"
_CONSUMABLE_GLOBAL_RELOAD_INTERVAL_MS = 750
_consumable_global_last_reload_ms = 0
_consumable_global_last_command_toggle: bool | None = None

_CONSUMABLE_AUTO_MIN_INTERVAL_MS = 650
_consumable_auto_running: dict[str, bool] = {}
_consumable_auto_last_start_ms: dict[str, int] = {}

# Party-wide DP items. These affect the whole party and are coordinated through
# a single carrier account. Personal DP removers belong to the Pumpkin button.
_PARTY_DP_MODELS = (
    int(ModelID.Four_Leaf_Clover.value),
    int(ModelID.Oath_Of_Purity.value),
)

# Personal DP items used before Pumpkin Cookies while this character has DP.
_PERSONAL_DP_MODELS = (
    int(ModelID.Peppermint_Candy_Cane.value),
    int(ModelID.Refined_Jelly.value),
    int(ModelID.Wintergreen_Candy_Cane.value),
    int(ModelID.Shining_Blade_Ration.value),
)

# Party-wide morale items represented by the Rainbow Candy Cane icon.
_PARTY_MORALE_MODELS = (
    int(ModelID.Rainbow_Candy_Cane.value),
    int(ModelID.Honeycomb.value),
    int(ModelID.Elixir_Of_Valor.value),
    int(ModelID.Seal_Of_The_Dragon_Empire.value),
)

_LUNAR_FORTUNE_MODELS = (
    int(ModelID.Lunar_Fortune_2007_Pig.value),
    int(ModelID.Lunar_Fortune_2008_Rat.value),
    int(ModelID.Lunar_Fortune_2009_Ox.value),
    int(ModelID.Lunar_Fortune_2010_Tiger.value),
    int(ModelID.Lunar_Fortune_2011_Rabbit.value),
    int(ModelID.Lunar_Fortune_2012_Dragon.value),
    int(ModelID.Lunar_Fortune_2013_Snake.value),
    int(ModelID.Lunar_Fortune_2014_Horse.value),
    int(ModelID.Lunar_Fortune_2015_Sheep.value),
    int(ModelID.Lunar_Fortune_2016_Monkey.value),
    int(ModelID.Lunar_Fortune_2017_Rooster.value),
    int(ModelID.Lunar_Fortune_2018_Dog.value),
)
_LUNAR_BLESSING_EFFECT_ID = 1926
_LUNAR_FORTUNE_INTERVAL_MS = 120

# Party-wide experience-scroll group. Effects are authoritative; no local
# duration guessing is used. Skill IDs match the game's Insight effects.
_XP_SCROLL_MODELS = (
    int(ModelID.Scroll_Of_Berserkers_Insight.value),
    int(ModelID.Scroll_Of_The_Lightbringer.value),
    int(ModelID.Scroll_of_Slayers_Insight.value),
    int(ModelID.Scroll_Of_Heros_Insight.value),
    int(ModelID.Scroll_Of_Rampagers_Insight.value),
    int(ModelID.Scroll_Of_Hunters_Insight.value),
    int(ModelID.Scroll_Of_Adventurers_Insight.value),
)
_XP_INSIGHT_EFFECT_IDS = (765, 767, 768, 857, 894, 895, 1887)
_XP_SCROLL_CONFIRM_TIMEOUT_MS = 1800
_XP_SCROLL_CONFIRM_POLL_MS = 100
_XP_SCROLL_LOCK_STALE_SECONDS = 6.0
_xp_was_in_combat: dict[str, bool] = {}

_RES_SCROLL_MODEL_ID = int(ModelID.Scroll_Of_Resurrection.value)

# Summoning page. These are the 21 summon items currently exposed by Py4R's
# ModelID enum and bundled textures. The four newer Reforged Ascalonian horn
# variants are not assigned guessed IDs.
summoning_consumables = [
    (ModelID.Amber_Summon, "Assets\\Textures\\Item Models\\30961-Amber_Summoning_Stone.png", "Amber Summoning Stone"),
    (ModelID.Arctic_Summon, "Assets\\Textures\\Item Models\\Arctic_Summoning_Stone.png", "Arctic Summoning Stone"),
    (ModelID.Automaton_Summon, "Assets\\Textures\\Item Models\\30846-Automaton_Summoning_Stone.png", "Automaton Summoning Stone"),
    (ModelID.Celestial_Summon, "Assets\\Textures\\Item Models\\34176-Celestial_Summoning_Stone.png", "Celestial Summoning Stone"),
    (ModelID.Chitinous_Summon, "Assets\\Textures\\Item Models\\30959-Chitinous_Summoning_Stone.png", "Chitinous Summoning Stone"),
    (ModelID.Demonic_Summon, "Assets\\Textures\\Item Models\\30963-Demonic_Summoning_Stone.png", "Demonic Summoning Stone"),
    (ModelID.Fossilized_Summon, "Assets\\Textures\\Item Models\\30965-Fossilized_Summoning_Stone.png", "Fossilized Summoning Stone"),
    (ModelID.Frosty_Summon, "Assets\\Textures\\Item Models\\31023-Frosty_Summoning_Stone.png", "Frosty Summoning Stone"),
    (ModelID.Gelatinous_Summon, "Assets\\Textures\\Item Models\\30964-Gelatinous_Summoning_Stone.png", "Gelatinous Summoning Stone"),
    (ModelID.Ghastly_Summon, "Assets\\Textures\\Item Models\\32557-Ghastly_Summoning_Stone.png", "Ghastly Summoning Stone"),
    (ModelID.Igneous_Summoning_Stone, "Assets\\Textures\\Item Models\\30847-Igneous_Summoning_Stone.png", "Igneous Summoning Stone"),
    (ModelID.Imperial_Guard_Summon, "Assets\\Textures\\Item Models\\Imperial_Guard_Reinforcement_Order.png", "Imperial Guard Reinforcement Order"),
    (ModelID.Jadeite_Summon, "Assets\\Textures\\Item Models\\Jadeite_Summoning_Stone.png", "Jadeite Summoning Stone"),
    (ModelID.Legionnaire_Summoning_Crystal, "Assets\\Textures\\Item Models\\37810-Legionnaire_Summoning_Crystal.png", "Legionnaire Summoning Crystal"),
    (ModelID.Merchant_Summon, "Assets\\Textures\\Item Models\\Mercantile_Summoning_Stone.png", "Mercantile Summoning Stone"),
    (ModelID.Mischievous_Summon, "Assets\\Textures\\Item Models\\Mischievous_Summoning_Stone.png", "Mischievous Summoning Stone"),
    (ModelID.Mysterious_Summon, "Assets\\Textures\\Item Models\\Mysterious_Summoning_Stone.png", "Mysterious Summoning Stone"),
    (ModelID.Mystical_Summon, "Assets\\Textures\\Item Models\\Mystical_Summoning_Stone.png", "Mystical Summoning Stone"),
    (ModelID.Shining_Blade_Summon, "Assets\\Textures\\Item Models\\Shining_Blade_War_Horn.png", "Shining Blade War Horn"),
    (ModelID.Tengu_Summon, "Assets\\Textures\\Item Models\\30209-Tengu_Support_Flare.png", "Tengu Support Flare"),
    (ModelID.Zaishen_Summon, "Assets\\Textures\\Item Models\\Zaishen_Summoning_Stone.png", "Zaishen Summoning Stone"),
]
_SUMMON_AUTO_KEY = "__summoning_auto__"
_SUMMON_AUTO_MIN_INTERVAL_MS = 1000

# 3-point alcohol provides level-5 intoxication. Prevent another strong alcohol
# use while the first drink is still waiting for the client drunk-state update.
_STRONG_ALCOHOL_MODELS = {
    int(ModelID.Aged_Dwarven_Ale.value),
    int(ModelID.Aged_Hunters_Ale.value),
    int(ModelID.Bottle_Of_Grog.value),
    int(ModelID.Flask_Of_Firewater.value),
    int(ModelID.Keg_Of_Aged_Hunters_Ale.value),
    int(ModelID.Krytan_Brandy.value),
    int(ModelID.Spiked_Eggnog.value),
}
_ALCOHOL_STRONG_PENDING_MS = 3000
_alcohol_strong_pending_until_ms: dict[str, int] = {}

# Powerstone remains event-driven. Party DP is continuous and does not depend on
# the local account having just died or revived.
_EVENT_TRIGGER_MODELS = {
    int(ModelID.Powerstone_Of_Courage.value),
}
_consumable_event_state: dict[str, dict[str, int | bool]] = {}

def _is_live_party_leader() -> bool:
    try:
        return int(Player.GetAgentID() or 0) > 0 and int(Player.GetAgentID() or 0) == int(GLOBAL_CACHE.Party.GetPartyLeaderID() or 0)
    except Exception:
        return False


def _is_outpost_or_guild_hall() -> bool:
    try:
        if Map.IsGuildHall():
            return True
    except Exception:
        pass
    try:
        return bool(Map.IsOutpost())
    except Exception:
        return False


def _account_consumable_master_enabled() -> bool:
    return bool(_consumable_auto_settings.get_bool(
        _CONSUMABLE_MASTER_SECTION,
        _CONSUMABLE_ACCOUNT_MASTER_KEY,
        True,
    ))


def _set_account_consumable_master_enabled(enabled: bool) -> None:
    _consumable_auto_settings.set_bool(
        _CONSUMABLE_MASTER_SECTION,
        _CONSUMABLE_ACCOUNT_MASTER_KEY,
        bool(enabled),
    )


def _global_consumable_master_command(refresh: bool = True) -> tuple[bool, bool]:
    """Read the latest leader reset command as (enabled, command_toggle)."""
    global _consumable_global_last_reload_ms
    try:
        now_ms = int(Utils.GetBaseTimestamp())
        if refresh and not _is_live_party_leader():
            if now_ms - int(_consumable_global_last_reload_ms or 0) >= _CONSUMABLE_GLOBAL_RELOAD_INTERVAL_MS:
                _consumable_global_last_reload_ms = now_ms
                try:
                    _consumable_global_settings.reload()
                except Exception:
                    pass
        enabled = bool(_consumable_global_settings.get_bool(
            _CONSUMABLE_GLOBAL_MASTER_SECTION,
            _CONSUMABLE_GLOBAL_MASTER_KEY,
            True,
        ))
        command_toggle = bool(_consumable_global_settings.get_bool(
            _CONSUMABLE_GLOBAL_MASTER_SECTION,
            _CONSUMABLE_GLOBAL_COMMAND_TOGGLE_KEY,
            False,
        ))
        return enabled, command_toggle
    except Exception:
        return True, False


def _set_global_consumable_master_enabled(enabled: bool) -> None:
    """Leader-only one-shot reset command for every injected account."""
    global _consumable_global_last_command_toggle
    if not _is_live_party_leader():
        return
    try:
        current_toggle = bool(_consumable_global_settings.get_bool(
            _CONSUMABLE_GLOBAL_MASTER_SECTION,
            _CONSUMABLE_GLOBAL_COMMAND_TOGGLE_KEY,
            False,
        ))
    except Exception:
        current_toggle = False
    next_toggle = not current_toggle
    _consumable_global_settings.set_bool(
        _CONSUMABLE_GLOBAL_MASTER_SECTION,
        _CONSUMABLE_GLOBAL_MASTER_KEY,
        bool(enabled),
    )
    _consumable_global_settings.set_bool(
        _CONSUMABLE_GLOBAL_MASTER_SECTION,
        _CONSUMABLE_GLOBAL_COMMAND_TOGGLE_KEY,
        next_toggle,
    )
    # Force the leader's command to disk so follower clients can see it quickly.
    try:
        _consumable_global_settings.save()
    except Exception:
        pass
    _consumable_global_last_command_toggle = next_toggle


def _sync_consumable_master_from_leader() -> None:
    """Apply each leader reset command once; local overrides remain independent."""
    global _consumable_global_last_command_toggle
    enabled, command_toggle = _global_consumable_master_command(refresh=True)

    # On first observation, adopt the current command generation without replaying
    # an old command from a previous session. This preserves each account's saved
    # local override until the leader actually clicks the Auto button again.
    if _consumable_global_last_command_toggle is None:
        _consumable_global_last_command_toggle = command_toggle
        return

    if command_toggle == _consumable_global_last_command_toggle:
        return

    _consumable_global_last_command_toggle = command_toggle
    if not _is_live_party_leader():
        _set_account_consumable_master_enabled(enabled)


def _consumable_auto_key(model_id: ModelID | int) -> str:
    value = int(model_id.value if hasattr(model_id, "value") else model_id)
    if value == _TOWN_CAKE_SENTINEL:
        return "town_cake"
    if value == _LUNAR_FORTUNE_SENTINEL:
        return "lunar_fortune"
    if value == int(ModelID.Dwarven_Ale.value):
        return "alcohol"
    if value == int(ModelID.Rainbow_Candy_Cane.value):
        return "party_morale"
    if value == int(ModelID.Four_Leaf_Clover.value):
        return "death_penalty"
    if value == int(ModelID.Pumpkin_Cookie.value):
        return "pumpkin_cookie"
    if value == int(ModelID.Powerstone_Of_Courage.value):
        return "powerstone_of_courage"
    try:
        return str(ModelID(value).name).lower()
    except Exception:
        return f"model_{value}"


def _consumable_auto_enabled(model_id: ModelID | int) -> bool:
    return bool(_consumable_auto_settings.get_bool(
        _CONSUMABLE_AUTO_SECTION,
        _consumable_auto_key(model_id),
        False,
    ))


def _set_consumable_auto_enabled(model_id: ModelID | int, enabled: bool) -> None:
    _consumable_auto_settings.set_bool(
        _CONSUMABLE_AUTO_SECTION,
        _consumable_auto_key(model_id),
        bool(enabled),
    )


def _consumable_auto_label(model_id: ModelID | int) -> str:
    value = int(model_id.value if hasattr(model_id, "value") else model_id)
    if value == _TOWN_CAKE_SENTINEL:
        return "Town Cake"
    if value == _LUNAR_FORTUNE_SENTINEL:
        return "Lunar Fortune"
    if value == _XP_SCROLL_SENTINEL:
        return "Experience Scroll"
    if value == _RES_SCROLL_SENTINEL:
        return "Resurrection Scroll"
    if value == int(ModelID.Dwarven_Ale.value):
        return "Alcohol"
    if value == int(ModelID.Rainbow_Candy_Cane.value):
        return "Party Morale"
    if value == int(ModelID.Four_Leaf_Clover.value):
        return "Party DP"
    if value == int(ModelID.Pumpkin_Cookie.value):
        return "Pumpkin Cookie"
    if value == int(ModelID.Powerstone_Of_Courage.value):
        return "Powerstone of Courage"
    try:
        return ModelID(value).name.replace("_", " ")
    except Exception:
        return str(value)


def _get_consumable_event_state(account_email: str) -> dict[str, int | bool]:
    state = _consumable_event_state.get(account_email)
    if state is None:
        state = {
            "initialized": False,
            "was_explorable": False,
            "map_id": 0,
            "instance_uptime": 0,
            "local_dead_seen": False,
            "party_wipe_seen": False,
        }
        _consumable_event_state[account_email] = state
    return state


def _update_consumable_event_state(cached_data: CacheData, player_dead: bool) -> tuple[bool, bool, bool]:
    """Return (map_entry, local_revive, party_wipe_revive) for this account."""
    account_email = str(cached_data.account_email or Player.GetAccountEmail() or "")
    if not account_email:
        return False, False, False

    state = _get_consumable_event_state(account_email)
    is_explorable = bool(Map.IsExplorable())
    map_id = int(Map.GetMapID() or 0)
    instance_uptime = int(Map.GetInstanceUptime() or 0)
    try:
        party_defeated = bool(GLOBAL_CACHE.Party.IsPartyDefeated()) if is_explorable else False
    except Exception:
        party_defeated = False

    if not bool(state["initialized"]):
        state["initialized"] = True
        state["was_explorable"] = is_explorable
        state["map_id"] = map_id
        state["instance_uptime"] = instance_uptime
        state["local_dead_seen"] = bool(player_dead)
        state["party_wipe_seen"] = bool(party_defeated)
        # First observation is baseline only. This prevents script reloads in the
        # middle of an explorable from spending a Powerstone as a fake map entry.
        return False, False, False

    previous_explorable = bool(state["was_explorable"])
    previous_map_id = int(state["map_id"] or 0)
    previous_uptime = int(state["instance_uptime"] or 0)

    map_entry = bool(
        is_explorable
        and (
            not previous_explorable
            or map_id != previous_map_id
            or (previous_uptime > 0 and instance_uptime + 1500 < previous_uptime)
        )
    )

    if map_entry:
        state["local_dead_seen"] = False
        state["party_wipe_seen"] = False

    local_revive = False
    if is_explorable:
        if player_dead:
            state["local_dead_seen"] = True
        elif bool(state["local_dead_seen"]):
            local_revive = True
            state["local_dead_seen"] = False
    else:
        state["local_dead_seen"] = False

    party_wipe_revive = False
    if is_explorable:
        if party_defeated:
            state["party_wipe_seen"] = True
        elif bool(state["party_wipe_seen"]) and not player_dead:
            party_wipe_revive = True
            state["party_wipe_seen"] = False
    else:
        state["party_wipe_seen"] = False

    state["was_explorable"] = is_explorable
    state["map_id"] = map_id
    state["instance_uptime"] = instance_uptime
    return map_entry, local_revive, party_wipe_revive


def _use_first_available_once(model_ids: tuple[int, ...] | list[int]):
    """Use exactly one available item from the ordered model list."""
    if not Routines.Checks.Map.MapValid() or not Map.IsExplorable():
        yield from Routines.Yield.wait(250)
        return
    player_id = int(Player.GetAgentID() or 0)
    if player_id <= 0 or Agent.IsDead(player_id):
        yield from Routines.Yield.wait(250)
        return

    for model_id in model_ids:
        item_id = int(GLOBAL_CACHE.Inventory.GetFirstModelID(int(model_id)) or 0)
        if item_id:
            GLOBAL_CACHE.Inventory.UseItem(item_id)
            yield from Routines.Yield.wait(750)
            return
    yield from Routines.Yield.wait(250)


def _shared_party_min_morale() -> int | None:
    try:
        entries = GLOBAL_CACHE.ShMem.GetSharedPartyMorale() or []
        valid = [int(morale) for _, morale in entries if int(morale or 0) > 0]
        return min(valid) if valid else None
    except Exception:
        return None


def _run_event_consumable_once(model_id: ModelID | int, cached_data: CacheData):
    """Run one event-triggered consumable action and release its in-flight lock."""
    value = int(model_id.value if hasattr(model_id, "value") else model_id)
    key = _consumable_auto_key(value)
    _consumable_auto_running[key] = True
    try:
        if value == int(ModelID.Powerstone_Of_Courage.value):
            # Powerstone is party-wide. Stagger enabled accounts so an earlier
            # account can apply the +10 morale before later accounts re-check.
            try:
                party_position = max(0, int(getattr(cached_data.data, "party_position", 0) or 0))
            except Exception:
                party_position = 0
            if party_position > 0:
                yield from Routines.Yield.wait(min(party_position, 7) * 900)

            # If another enabled account already used a Powerstone for the same
            # event, the shared party morale should now be 110 and this account
            # should not spend a duplicate. If shared morale is unavailable, the
            # local account is still allowed to use its configured item.
            min_party_morale = _shared_party_min_morale()
            if min_party_morale is not None and min_party_morale >= 110:
                yield from Routines.Yield.wait(250)
                return

            yield from _use_first_available_once((int(ModelID.Powerstone_Of_Courage.value),))
            return
    finally:
        _consumable_auto_running[key] = False


def _schedule_event_consumable(model_id: ModelID | int, cached_data: CacheData) -> None:
    value = int(model_id.value if hasattr(model_id, "value") else model_id)
    if not _consumable_auto_enabled(value):
        return
    key = _consumable_auto_key(value)
    if _consumable_auto_running.get(key, False):
        return
    _consumable_auto_running[key] = True
    GLOBAL_CACHE.Coroutines.append(_run_event_consumable_once(value, cached_data))


def _upkeep_pumpkin_cookie():
    """Use personal DP removers first, then maintain this character at +10% with Pumpkin Cookies."""
    if not Routines.Checks.Map.MapValid() or not Map.IsExplorable():
        yield from Routines.Yield.wait(500)
        return

    player_id = int(Player.GetAgentID() or 0)
    if player_id <= 0 or Agent.IsDead(player_id):
        yield from Routines.Yield.wait(500)
        return

    morale = int(Player.GetMorale() or 0)
    if morale <= 0 or morale >= 110:
        yield from Routines.Yield.wait(500)
        return

    attempts = 0
    max_attempts = 20
    while morale < 110 and attempts < max_attempts:
        if not Routines.Checks.Map.MapValid() or not Map.IsExplorable() or Agent.IsDead(player_id):
            return

        item_id = 0

        # While DP exists, use self-only DP removers before spending Pumpkin Cookies.
        if morale < 100:
            for model_id in _PERSONAL_DP_MODELS:
                item_id = int(GLOBAL_CACHE.Inventory.GetFirstModelID(int(model_id)) or 0)
                if item_id:
                    break

        # No personal DP remover (or DP already cleared): use Pumpkin Cookies.
        if not item_id:
            item_id = int(GLOBAL_CACHE.Inventory.GetFirstModelID(int(ModelID.Pumpkin_Cookie.value)) or 0)

        if not item_id:
            break

        before_morale = morale
        GLOBAL_CACHE.Inventory.UseItem(item_id)
        attempts += 1
        yield from Routines.Yield.wait(750)

        if Agent.IsDead(player_id):
            return

        morale = int(Player.GetMorale() or 0)
        if morale <= before_morale:
            yield from Routines.Yield.wait(450)
            morale = int(Player.GetMorale() or 0)
            if morale <= before_morale:
                break

    yield from Routines.Yield.wait(250)


def _upkeep_town_cake_while_moving():
    """Use city-speed sweets only while the local character is actually moving."""
    if not Routines.Checks.Map.MapValid() or not _is_outpost_or_guild_hall():
        yield from Routines.Yield.wait(500)
        return

    player_id = int(Player.GetAgentID() or 0)
    if player_id <= 0 or Agent.IsDead(player_id):
        yield from Routines.Yield.wait(500)
        return

    # Toolbox-style behavior: arriving in town while stationary must not consume
    # anything. If the speed effect expires while stationary, wait until movement
    # resumes before consuming another sweet.
    if not Agent.IsMoving(player_id):
        yield from Routines.Yield.wait(250)
        return

    effect_ids = list(Routines.Yield.Upkeepers.CITY_SPEED_EFFECTS)
    if any(GLOBAL_CACHE.Effects.HasEffect(player_id, effect_id) for effect_id in effect_ids):
        yield from Routines.Yield.wait(500)
        return

    item_models = [
        int(model.value if hasattr(model, "value") else model)
        for model in Routines.Yield.Upkeepers.CITY_SPEED_ITEMS
    ]
    for model_id in item_models:
        item_id = int(GLOBAL_CACHE.Inventory.GetFirstModelID(model_id) or 0)
        if item_id:
            GLOBAL_CACHE.Inventory.UseItem(item_id)
            yield from Routines.Yield.wait(1000)
            return

    yield from Routines.Yield.wait(500)


def _upkeep_alcohol_with_strong_guard(target_alc_level: int = 2):
    """Preserve existing alcohol target behavior while preventing duplicate 3-point alcohol use."""
    import PyEffects

    if not Routines.Checks.Map.MapValid() or not Map.IsExplorable():
        yield from Routines.Yield.wait(500)
        return

    player_id = int(Player.GetAgentID() or 0)
    if player_id <= 0 or Agent.IsDead(player_id):
        yield from Routines.Yield.wait(500)
        return

    account_email = str(Player.GetAccountEmail() or "")
    now_ms = int(Utils.GetBaseTimestamp())
    drunk_level = int(PyEffects.PyEffects.GetAlcoholLevel() or 0)

    if drunk_level >= int(target_alc_level):
        if account_email:
            _alcohol_strong_pending_until_ms.pop(account_email, None)
        yield from Routines.Yield.wait(500)
        return

    # A strong drink was just used but the drunk-level snapshot has not caught up.
    pending_until = int(_alcohol_strong_pending_until_ms.get(account_email, 0) or 0)
    if pending_until > now_ms:
        yield from Routines.Yield.wait(min(500, max(100, pending_until - now_ms)))
        return
    if account_email and pending_until:
        _alcohol_strong_pending_until_ms.pop(account_email, None)

    alcohol_models = [
        int(model.value if hasattr(model, "value") else model)
        for model in Routines.Yield.Upkeepers.ALCOHOL_ITEMS
    ]

    # Keep the original target-level behavior for 1-point alcohol. Strong alcohol
    # gets a pending guard because one drink already supplies level-5 intoxication.
    while drunk_level < int(target_alc_level):
        selected_model = 0
        item_id = 0
        for model_id in alcohol_models:
            item_id = int(GLOBAL_CACHE.Inventory.GetFirstModelID(int(model_id)) or 0)
            if item_id:
                selected_model = int(model_id)
                break

        if not item_id:
            yield from Routines.Yield.wait(500)
            return

        GLOBAL_CACHE.Inventory.UseItem(item_id)

        if selected_model in _STRONG_ALCOHOL_MODELS:
            if account_email:
                _alcohol_strong_pending_until_ms[account_email] = int(Utils.GetBaseTimestamp()) + _ALCOHOL_STRONG_PENDING_MS

            # One strong drink is enough. Poll for the state update, but never
            # consume a second 3-point drink during this pass.
            elapsed = 0
            while elapsed < 2000:
                yield from Routines.Yield.wait(100)
                elapsed += 100
                updated_level = int(PyEffects.PyEffects.GetAlcoholLevel() or 0)
                if updated_level >= int(target_alc_level):
                    if account_email:
                        _alcohol_strong_pending_until_ms.pop(account_email, None)
                    return
                if updated_level > drunk_level:
                    # The first state change is visible, but keep the pending guard
                    # until target level is confirmed or the timeout expires.
                    drunk_level = updated_level
            return

        yield from Routines.Yield.wait(500)
        drunk_level = int(PyEffects.PyEffects.GetAlcoholLevel() or 0)

    yield from Routines.Yield.wait(500)



def _lunar_blessing_active() -> bool:
    try:
        player_id = int(Player.GetAgentID() or 0)
        return player_id > 0 and bool(
            GLOBAL_CACHE.Effects.HasEffect(player_id, int(_LUNAR_BLESSING_EFFECT_ID))
        )
    except Exception:
        return False


def _upkeep_lunar_fortune():
    """Rapidly open Lunar Fortunes until Lunar Blessing is detected."""
    if not Routines.Checks.Map.MapValid() or not Map.IsExplorable():
        yield from Routines.Yield.wait(500)
        return

    player_id = int(Player.GetAgentID() or 0)
    if player_id <= 0 or Agent.IsDead(player_id):
        yield from Routines.Yield.wait(500)
        return

    if _lunar_blessing_active():
        yield from Routines.Yield.wait(500)
        return

    # The blessing is uncommon, so use fortunes quickly. Split the 120 ms gap
    # into small polls so the moment Lunar Blessing appears we stop immediately.
    attempts = 0
    while attempts < 100:
        if (
            not Routines.Checks.Map.MapValid()
            or not Map.IsExplorable()
            or Agent.IsDead(player_id)
            or _lunar_blessing_active()
        ):
            return

        selected_item = 0
        for model_id in _LUNAR_FORTUNE_MODELS:
            selected_item = int(GLOBAL_CACHE.Inventory.GetFirstModelID(int(model_id)) or 0)
            if selected_item:
                break

        if not selected_item:
            yield from Routines.Yield.wait(500)
            return

        GLOBAL_CACHE.Inventory.UseItem(selected_item)
        attempts += 1

        elapsed = 0
        while elapsed < _LUNAR_FORTUNE_INTERVAL_MS:
            yield from Routines.Yield.wait(30)
            elapsed += 30
            if _lunar_blessing_active():
                return

    yield from Routines.Yield.wait(250)


def _special_lock_path(filename: str) -> str:
    try:
        projects_path = str(PySystem.Console.get_projects_path() or "").strip()
        if not projects_path:
            return ""
        lock_dir = os.path.join(projects_path, "Settings", "Global", "HeroAI")
        os.makedirs(lock_dir, exist_ok=True)
        return os.path.join(lock_dir, filename)
    except Exception:
        return ""


def _try_acquire_special_lock(filename: str, stale_seconds: float) -> tuple[str, str] | None:
    path = _special_lock_path(filename)
    if not path:
        return None
    token = f"{Player.GetAccountEmail()}|{os.getpid()}|{time.time_ns()}"
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, token.encode("utf-8", errors="ignore"))
            finally:
                os.close(fd)
            return (path, token)
        except FileExistsError:
            try:
                if (time.time() - os.path.getmtime(path)) > stale_seconds:
                    os.remove(path)
                    continue
            except Exception:
                pass
            return None
        except Exception:
            return None
    return None


def _release_special_lock(lock_info: tuple[str, str] | None) -> None:
    if not lock_info:
        return
    path, token = lock_info
    try:
        current = ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                current = handle.read().strip()
        except Exception:
            pass
        if not current or current == token:
            os.remove(path)
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _xp_insight_active() -> bool:
    """True if any real account in the current party reports an XP Insight effect."""
    effect_ids = set(int(v) for v in _XP_INSIGHT_EFFECT_IDS)

    # Local effect is the freshest signal.
    player_id = int(Player.GetAgentID() or 0)
    if player_id > 0:
        for skill_id in effect_ids:
            try:
                if GLOBAL_CACHE.Effects.HasEffect(player_id, skill_id):
                    return True
            except Exception:
                continue

    # Cross-account shared-memory scan makes the gate truly party-wide.
    try:
        self_email = str(Player.GetAccountEmail() or "")
        self_account = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(self_email) if self_email else None
        party_id = int(getattr(getattr(self_account, "AgentPartyData", None), "PartyID", 0) or 0)
        for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
            if not bool(getattr(account, "IsSlotActive", False)):
                continue
            if not bool(getattr(account, "IsAccount", False)) or bool(getattr(account, "IsHero", False)):
                continue
            account_party_id = int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)
            if party_id > 0 and account_party_id != party_id:
                continue
            buffs = getattr(getattr(account, "AgentData", None), "Buffs", None)
            for buff in getattr(buffs, "Buffs", []) or []:
                if int(getattr(buff, "SkillId", 0) or 0) in effect_ids:
                    return True
    except Exception:
        pass
    return False


def _experience_scroll_auto_generator():
    """On combat entry, let exactly one enabled carrier use one XP scroll."""
    if not Routines.Checks.Map.MapValid() or not Map.IsExplorable():
        return
    player_id = int(Player.GetAgentID() or 0)
    if player_id <= 0 or Agent.IsDead(player_id) or not Agent.IsInCombatStance(player_id):
        return
    if _xp_insight_active():
        return

    item_id = 0
    for model_id in _XP_SCROLL_MODELS:
        item_id = int(GLOBAL_CACHE.Inventory.GetFirstModelID(int(model_id)) or 0)
        if item_id:
            break
    if not item_id:
        return

    lock_info = None
    waited = 0
    while lock_info is None and waited < 2500:
        if _xp_insight_active():
            return
        if Agent.IsDead(player_id) or not Agent.IsInCombatStance(player_id):
            return
        lock_info = _try_acquire_special_lock(".xp_scroll_auto.lock", _XP_SCROLL_LOCK_STALE_SECONDS)
        if lock_info is not None:
            break
        yield from Routines.Yield.wait(100)
        waited += 100
    if lock_info is None:
        return
    try:
        if _xp_insight_active() or Agent.IsDead(player_id) or not Agent.IsInCombatStance(player_id):
            return

        item_id = 0
        for model_id in _XP_SCROLL_MODELS:
            item_id = int(GLOBAL_CACHE.Inventory.GetFirstModelID(int(model_id)) or 0)
            if item_id:
                break
        if not item_id:
            return

        GLOBAL_CACHE.Inventory.UseItem(item_id)
        elapsed = 0
        while elapsed < _XP_SCROLL_CONFIRM_TIMEOUT_MS:
            yield from Routines.Yield.wait(_XP_SCROLL_CONFIRM_POLL_MS)
            elapsed += _XP_SCROLL_CONFIRM_POLL_MS
            if _xp_insight_active():
                return
    finally:
        _release_special_lock(lock_info)


def _sync_resurrection_scroll_auto(enabled: bool) -> None:
    """Drive the existing HeroAI resurrection-scroll engine from the PCons icon."""
    try:
        cfg = resurrection_scroll._settings
        cfg.ensure_initialized()
        changed = False
        if bool(resurrection_scroll.is_enabled()) != bool(enabled):
            cfg.set_account_resurrection_scroll_enabled(bool(enabled))
            changed = True
        if bool(enabled) and cfg.get_account_resurrection_scroll_skip_if_res_available():
            cfg.set_account_resurrection_scroll_skip_if_res_available(False)
            changed = True
        if changed:
            try:
                resurrection_scroll._broadcast_local_state()
            except Exception:
                pass
    except Exception:
        pass


def _item_texture_path(model_id: int, fallback: str) -> str:
    """Resolve the actual carried item's GW.dat icon when possible."""
    try:
        if int(model_id) > 0:
            item_id = int(GLOBAL_CACHE.Inventory.GetFirstModelID(int(model_id)) or 0)
            if item_id:
                raw_file_id = int(GLOBAL_CACHE.Item.GetModelFileID(item_id) or 0)
                if raw_file_id > 0:
                    return f"gwdat://{raw_file_id}"
    except Exception:
        pass
    return fallback


def _summoning_auto_generator():
    """Use only THIS account's enabled summon, coordinated with one party-wide claim."""
    if not Routines.Checks.Map.MapValid() or not Map.IsExplorable():
        yield from Routines.Yield.wait(500)
        return

    player_id = int(Player.GetAgentID() or 0)
    if player_id <= 0 or Agent.IsDead(player_id):
        yield from Routines.Yield.wait(500)
        return

    try:
        if has_summoning_sickness(player_id):
            yield from Routines.Yield.wait(500)
            return
    except Exception:
        pass

    try:
        if has_active_party_summon(GLOBAL_CACHE.Party.GetOthers()):
            yield from Routines.Yield.wait(500)
            return
    except Exception:
        pass

    try:
        current_sp, _ = Player.GetSkillPointData()
        if int(current_sp or 0) <= 0:
            yield from Routines.Yield.wait(500)
            return
    except Exception:
        pass

    try:
        player_level = int(Agent.GetLevel(player_id) or 0)
    except Exception:
        player_level = 20

    selected_item_id = 0
    for model, _texture_path, _label in summoning_consumables:
        model_id = int(model.value)
        if not _consumable_auto_enabled(model_id):
            continue
        if model_id == int(ModelID.Igneous_Summoning_Stone.value) and player_level >= 20:
            continue
        item_id = int(GLOBAL_CACHE.Inventory.GetFirstModelID(model_id) or 0)
        if item_id:
            selected_item_id = item_id
            break

    if not selected_item_id:
        yield from Routines.Yield.wait(500)
        return

    lock_info = _try_acquire_special_lock(".summoning_auto.lock", 6.0)
    if lock_info is None:
        yield from Routines.Yield.wait(250)
        return

    try:
        try:
            if has_active_party_summon(GLOBAL_CACHE.Party.GetOthers()):
                return
        except Exception:
            pass
        try:
            if has_summoning_sickness(player_id):
                return
        except Exception:
            pass
        if Agent.IsDead(player_id):
            return

        GLOBAL_CACHE.Inventory.UseItem(selected_item_id)

        elapsed = 0
        while elapsed < 2500:
            yield from Routines.Yield.wait(100)
            elapsed += 100
            try:
                if has_active_party_summon(GLOBAL_CACHE.Party.GetOthers()):
                    return
            except Exception:
                pass
            try:
                if has_summoning_sickness(player_id):
                    return
            except Exception:
                pass
    finally:
        _release_special_lock(lock_info)

    yield from Routines.Yield.wait(250)

def _consumable_upkeep_generator(model_id: ModelID | int):
    value = int(model_id.value if hasattr(model_id, "value") else model_id)
    upkeepers = Routines.Yield.Upkeepers

    if value == _TOWN_CAKE_SENTINEL:
        return _upkeep_town_cake_while_moving()
    if value == _LUNAR_FORTUNE_SENTINEL:
        return _upkeep_lunar_fortune()
    if value == int(ModelID.Essence_Of_Celerity.value):
        return upkeepers.Upkeep_EssenceOfCelerity()
    if value == int(ModelID.Grail_Of_Might.value):
        return upkeepers.Upkeep_GrailOfMight()
    if value == int(ModelID.Armor_Of_Salvation.value):
        return upkeepers.Upkeep_ArmorOfSalvation()
    if value == int(ModelID.Dwarven_Ale.value):
        return _upkeep_alcohol_with_strong_guard(target_alc_level=2)
    if value == int(ModelID.Rainbow_Candy_Cane.value):
        return None
    if value == int(ModelID.Pumpkin_Cookie.value):
        return _upkeep_pumpkin_cookie()
    if value == int(ModelID.Birthday_Cupcake.value):
        return upkeepers.Upkeep_BirthdayCupcake()
    if value == int(ModelID.Candy_Apple.value):
        return upkeepers.Upkeep_CandyApple()
    if value == int(ModelID.Candy_Corn.value):
        return upkeepers.Upkeep_CandyCorn()
    if value == int(ModelID.Golden_Egg.value):
        return upkeepers.Upkeep_GoldenEgg()
    if value == int(ModelID.Slice_Of_Pumpkin_Pie.value):
        return upkeepers.Upkeep_SliceOfPumpkinPie()
    if value == int(ModelID.War_Supplies.value):
        return upkeepers.Upkeep_WarSupplies()
    if value == int(ModelID.Drake_Kabob.value):
        return upkeepers.Upkeep_DrakeKabob()
    if value == int(ModelID.Bowl_Of_Skalefin_Soup.value):
        return upkeepers.Upkeep_BowlOfSkalefinSoup()
    if value == int(ModelID.Pahnai_Salad.value):
        return upkeepers.Upkeep_PahnaiSalad()
    return None


_CONSET_AUTO_MODELS = {
    int(ModelID.Essence_Of_Celerity.value),
    int(ModelID.Grail_Of_Might.value),
    int(ModelID.Armor_Of_Salvation.value),
}

# Party-wide auto categories coordinated through one carrier account.
_PARTY_WIDE_AUTO_MODELS = {
    int(ModelID.Four_Leaf_Clover.value),
    int(ModelID.Rainbow_Candy_Cane.value),
}

_CONSET_EFFECT_BY_MODEL = {
    int(ModelID.Essence_Of_Celerity.value): int(GLOBAL_CACHE.Skill.GetID("Essence_of_Celerity_item_effect")),
    int(ModelID.Grail_Of_Might.value): int(GLOBAL_CACHE.Skill.GetID("Grail_of_Might_item_effect")),
    int(ModelID.Armor_Of_Salvation.value): int(GLOBAL_CACHE.Skill.GetID("Armor_of_Salvation_item_effect")),
}
_CONSET_SEARCH_INTERVAL_MS = 100
_CONSET_CONFIRM_TIMEOUT_MS = 1500
_CONSET_CONFIRM_POLL_MS = 100
_CONSET_LOCK_STALE_SECONDS = 8.0


def _get_consumable_params(model_id: int) -> tuple[int, int, int, int]:
    for entry_model, (_texture_path, params) in consumables:
        value = int(entry_model.value if hasattr(entry_model, "value") else entry_model)
        if value == int(model_id):
            return tuple(int(v) for v in params)
    return (0, 0, 0, 0)


def _conset_effect_active(model_id: int) -> bool:
    effect_id = int(_CONSET_EFFECT_BY_MODEL.get(int(model_id), 0) or 0)
    player_id = int(Player.GetAgentID() or 0)
    if effect_id <= 0 or player_id <= 0:
        return False
    try:
        return bool(GLOBAL_CACHE.Effects.HasEffect(player_id, effect_id))
    except Exception:
        return False


def _all_party_members_alive_for_conset() -> bool:
    """Conset can only be applied when the entire currently loaded party is alive."""
    try:
        if not Map.IsExplorable() or Map.IsMapLoading() or Map.IsInCinematic():
            return False
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0 or Agent.IsDead(player_id):
            return False
        return not bool(Routines.Checks.Party.IsPartyMemberDead())
    except Exception:
        return False


def _shared_account_has_model(account: AccountStruct, model_id: int) -> bool:
    """Read the account's shared inventory snapshot without commanding it to consume."""
    try:
        bags = getattr(account, "InventoryBags", None)
        if bags is None:
            return False
        for bag in bags.iter_bags():
            for slot in bag.Slots:
                if int(getattr(slot, "ModelID", 0) or 0) == int(model_id) and int(getattr(slot, "Quantity", 0) or 0) > 0:
                    return True
    except Exception:
        return False
    return False


def _conset_party_accounts(cached_data: CacheData) -> list[AccountStruct]:
    """Return real, active, same-party/same-map accounts in party-position order."""
    try:
        party_id = int(GLOBAL_CACHE.Party.GetPartyID() or getattr(cached_data.party, "party_id", 0) or 0)
    except Exception:
        party_id = int(getattr(cached_data.party, "party_id", 0) or 0)

    try:
        source = list(GLOBAL_CACHE.ShMem.GetAllAccountData() or [])
    except Exception:
        source = list(cached_data.party.accounts.values())

    result: list[AccountStruct] = []
    for account in source:
        try:
            if not bool(account.IsSlotActive) or not bool(account.IsAccount) or bool(account.IsHero):
                continue
            if party_id > 0 and int(account.AgentPartyData.PartyID or 0) != party_id:
                continue
            if not str(account.AccountEmail or ""):
                continue
            if not SameMapAsAccount(account):
                continue
            result.append(account)
        except Exception:
            continue

    result.sort(key=lambda account: (int(account.AgentPartyData.PartyPosition), str(account.AccountEmail).casefold()))
    return result


def _conset_lock_path() -> str:
    try:
        projects_path = str(PySystem.Console.get_projects_path() or "").strip()
        if not projects_path:
            return ""
        lock_dir = os.path.join(projects_path, "Settings", "Global", "HeroAI")
        os.makedirs(lock_dir, exist_ok=True)
        return os.path.join(lock_dir, ".conset_auto.lock")
    except Exception:
        return ""


def _try_acquire_conset_lock(account_email: str) -> tuple[str, str] | None:
    """Atomic cross-process lock so only one client coordinates Conset at a time."""
    path = _conset_lock_path()
    if not path:
        return None

    token = f"{account_email}|{os.getpid()}|{time.time_ns()}"
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, token.encode("utf-8", errors="ignore"))
            finally:
                os.close(fd)
            return (path, token)
        except FileExistsError:
            try:
                if (time.time() - os.path.getmtime(path)) > _CONSET_LOCK_STALE_SECONDS:
                    os.remove(path)
                    continue
            except Exception:
                pass
            return None
        except Exception:
            return None
    return None


def _release_conset_lock(lock_info: tuple[str, str] | None) -> None:
    if not lock_info:
        return
    path, token = lock_info
    try:
        current = ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                current = handle.read().strip()
        except Exception:
            pass
        if not current or current == token:
            os.remove(path)
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _wait_for_conset_effect(model_id: int):
    elapsed = 0
    while elapsed < _CONSET_CONFIRM_TIMEOUT_MS:
        if _conset_effect_active(model_id):
            return True
        yield from Routines.Yield.wait(_CONSET_CONFIRM_POLL_MS)
        elapsed += _CONSET_CONFIRM_POLL_MS
    return _conset_effect_active(model_id)


_PARTY_MORALE_LOCK_STALE_SECONDS = 8.0
_PARTY_MORALE_SEARCH_INTERVAL_MS = 100
_PARTY_MORALE_CONFIRM_TIMEOUT_MS = 1800
_PARTY_MORALE_CONFIRM_POLL_MS = 100


def _party_morale_lock_path() -> str:
    try:
        projects_path = str(PySystem.Console.get_projects_path() or "").strip()
        if not projects_path:
            return ""
        lock_dir = os.path.join(projects_path, "Settings", "Global", "HeroAI")
        os.makedirs(lock_dir, exist_ok=True)
        return os.path.join(lock_dir, ".party_morale_auto.lock")
    except Exception:
        return ""


def _try_acquire_party_morale_lock(account_email: str) -> tuple[str, str] | None:
    path = _party_morale_lock_path()
    if not path:
        return None
    token = f"{account_email}|{os.getpid()}|{time.time_ns()}"
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, token.encode("utf-8", errors="ignore"))
            finally:
                os.close(fd)
            return (path, token)
        except FileExistsError:
            try:
                if (time.time() - os.path.getmtime(path)) > _PARTY_MORALE_LOCK_STALE_SECONDS:
                    os.remove(path)
                    continue
            except Exception:
                pass
            return None
        except Exception:
            return None
    return None


def _release_party_morale_lock(lock_info: tuple[str, str] | None) -> None:
    if not lock_info:
        return
    path, token = lock_info
    try:
        current = ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                current = handle.read().strip()
        except Exception:
            pass
        if not current or current == token:
            os.remove(path)
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _party_min_morale_for_auto() -> int | None:
    shared = _shared_party_min_morale()
    if shared is not None:
        return int(shared)
    try:
        local = int(Player.GetMorale() or 0)
        return local if local > 0 else None
    except Exception:
        return None


def _party_pcon_params_for_model(model_id: int) -> tuple[int, int, int, int]:
    model_id = int(model_id)
    # Messaging.py in this baseline classifies Seal as self-morale. Pairing a
    # party-wide morale fallback makes the receiver use the party-morale gate,
    # while Seal remains the first item actually selected when it is present.
    if model_id == int(ModelID.Seal_Of_The_Dragon_Empire.value):
        return (model_id, 0, int(ModelID.Honeycomb.value), 0)
    return (model_id, 0, 0, 0)


def _wait_for_party_morale_increase(before_morale: int | None):
    if before_morale is None:
        yield from Routines.Yield.wait(1000)
        return True

    elapsed = 0
    while elapsed < _PARTY_MORALE_CONFIRM_TIMEOUT_MS:
        current = _party_min_morale_for_auto()
        if current is not None and int(current) > int(before_morale):
            return True
        yield from Routines.Yield.wait(_PARTY_MORALE_CONFIRM_POLL_MS)
        elapsed += _PARTY_MORALE_CONFIRM_POLL_MS
    current = _party_min_morale_for_auto()
    return current is not None and int(current) > int(before_morale)


def _use_party_model_from_one_carrier(model_id: int, cached_data: CacheData, before_morale: int | None):
    """Find one real account carrying model_id, command one use, and confirm party morale changed."""
    sender_email = str(cached_data.account_email or Player.GetAccountEmail() or "")
    params = _party_pcon_params_for_model(int(model_id))

    for account in _conset_party_accounts(cached_data):
        if not _shared_account_has_model(account, int(model_id)):
            yield from Routines.Yield.wait(_PARTY_MORALE_SEARCH_INTERVAL_MS)
            continue

        receiver_email = str(account.AccountEmail or "")
        if not receiver_email:
            yield from Routines.Yield.wait(_PARTY_MORALE_SEARCH_INTERVAL_MS)
            continue

        GLOBAL_CACHE.ShMem.SendMessage(
            sender_email,
            receiver_email,
            SharedCommandType.PCon,
            params,
        )

        if (yield from _wait_for_party_morale_increase(before_morale)):
            return True

        # Shared inventory snapshots may be stale after the last item in a stack.
        # Move to the next candidate only after the confirmation window completed.
        yield from Routines.Yield.wait(_PARTY_MORALE_SEARCH_INTERVAL_MS)

    return False


def _run_partywide_dp_once(cached_data: CacheData):
    """Use Clover/Oath from any carrier until every visible party member has no DP."""
    if not Routines.Checks.Map.MapValid() or not Map.IsExplorable():
        return

    lock_info = _try_acquire_party_morale_lock(str(cached_data.account_email or Player.GetAccountEmail() or ""))
    if lock_info is None:
        return

    try:
        attempts = 0
        while attempts < 16:
            before_morale = _party_min_morale_for_auto()
            if before_morale is None or before_morale >= 100:
                return

            used = False
            for model_id in _PARTY_DP_MODELS:
                if (yield from _use_party_model_from_one_carrier(model_id, cached_data, before_morale)):
                    used = True
                    attempts += 1
                    break

            if not used:
                return
    finally:
        _release_party_morale_lock(lock_info)


def _run_partywide_morale_once(cached_data: CacheData):
    """Maintain party morale to 110 using Rainbow/Honeycomb, then Elixir/Seal fallbacks."""
    if not Routines.Checks.Map.MapValid() or not Map.IsExplorable():
        return

    lock_info = _try_acquire_party_morale_lock(str(cached_data.account_email or Player.GetAccountEmail() or ""))
    if lock_info is None:
        return

    try:
        attempts = 0
        while attempts < 16:
            before_morale = _party_min_morale_for_auto()
            if before_morale is None or before_morale >= 110:
                return

            used = False
            for model_id in _PARTY_MORALE_MODELS:
                if (yield from _use_party_model_from_one_carrier(model_id, cached_data, before_morale)):
                    used = True
                    attempts += 1
                    break

            if not used:
                return
    finally:
        _release_party_morale_lock(lock_info)


def _run_partywide_conset_once(model_id: int, params: tuple[int, int, int, int], cached_data: CacheData):
    """Use one missing Conset item from the first party account that actually carries it."""
    model_id = int(model_id)
    if model_id not in _CONSET_AUTO_MODELS:
        return

    # Toolbox-style effect gate: an active Conset effect is authoritative.
    # Death/revival does not refresh these 30-minute party effects.
    if _conset_effect_active(model_id):
        return
    if not _all_party_members_alive_for_conset():
        return

    lock_info = _try_acquire_conset_lock(str(cached_data.account_email or Player.GetAccountEmail() or ""))
    if lock_info is None:
        return

    try:
        # Another account may have completed the use while this client waited for the lock.
        if _conset_effect_active(model_id):
            return
        if not _all_party_members_alive_for_conset():
            return

        sender_email = str(cached_data.account_email or Player.GetAccountEmail() or "")
        for account in _conset_party_accounts(cached_data):
            if _conset_effect_active(model_id):
                return
            if not _all_party_members_alive_for_conset():
                return

            # Carrier discovery is intentionally paced at 100 ms between accounts.
            if not _shared_account_has_model(account, model_id):
                yield from Routines.Yield.wait(_CONSET_SEARCH_INTERVAL_MS)
                continue

            receiver_email = str(account.AccountEmail or "")
            if not receiver_email:
                yield from Routines.Yield.wait(_CONSET_SEARCH_INTERVAL_MS)
                continue

            # Re-check the all-alive gate immediately before the actual use command.
            if not _all_party_members_alive_for_conset():
                return

            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                receiver_email,
                SharedCommandType.PCon,
                params,
            )

            # Keep a longer confirmation window after use; do not confuse the
            # requested 100 ms carrier-search interval with effect propagation.
            if (yield from _wait_for_conset_effect(model_id)):
                return

            # Shared inventory can be up to ~1.5 s old. If this candidate failed
            # to consume, move on only after the confirmation window completed.
            yield from Routines.Yield.wait(_CONSET_SEARCH_INTERVAL_MS)
    finally:
        _release_conset_lock(lock_info)


def _run_consumable_auto_once(model_id: ModelID | int, cached_data: CacheData):
    """Run one upkeep pass, then release this icon's in-flight lock."""
    value = int(model_id.value if hasattr(model_id, "value") else model_id)
    key = _consumable_auto_key(value)
    _consumable_auto_running[key] = True
    try:
        if value in _CONSET_AUTO_MODELS:
            params = _get_consumable_params(value)
            yield from _run_partywide_conset_once(value, params, cached_data)
            return

        if value == int(ModelID.Four_Leaf_Clover.value):
            yield from _run_partywide_dp_once(cached_data)
            return

        if value == int(ModelID.Rainbow_Candy_Cane.value):
            yield from _run_partywide_morale_once(cached_data)
            return

        generator = _consumable_upkeep_generator(value)
        if generator is not None:
            yield from generator
    finally:
        _consumable_auto_running[key] = False


def tick_consumable_upkeep(cached_data: CacheData) -> None:
    """Schedule continuous upkeep and one-shot map/death event consumables."""
    try:
        if not cached_data.account_email or cached_data.account_email != Player.GetAccountEmail():
            return
        if not Routines.Checks.Map.MapValid():
            return
        if Map.IsMapLoading() or Map.IsInCinematic():
            return

        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            return
        player_dead = bool(Agent.IsDead(player_id))

        # Track transitions even while a master switch is OFF. Events that occur
        # while automation is paused are not replayed later when it is re-enabled.
        map_entry, local_revive, party_wipe_revive = _update_consumable_event_state(
            cached_data,
            player_dead,
        )

        account_email = str(cached_data.account_email or Player.GetAccountEmail() or "")
        try:
            current_combat = bool(Agent.IsInCombatStance(player_id)) if not player_dead else False
        except Exception:
            current_combat = False
        previous_combat = _xp_was_in_combat.get(account_email, current_combat)
        entered_combat = bool(current_combat and not previous_combat)
        _xp_was_in_combat[account_email] = current_combat

        # Leader reset commands are one-shot. A follower may override its own Auto
        # state afterward; the next leader click resets the whole party again.
        _sync_consumable_master_from_leader()
        account_master = _account_consumable_master_enabled()
        _sync_resurrection_scroll_auto(
            bool(account_master and _consumable_auto_enabled(_RES_SCROLL_SENTINEL))
        )
        if not account_master:
            return

        is_explorable = bool(Map.IsExplorable())
        is_town = _is_outpost_or_guild_hall()

        if is_explorable and not player_dead:
            if map_entry or party_wipe_revive:
                _schedule_event_consumable(ModelID.Powerstone_Of_Courage, cached_data)

            if entered_combat and _consumable_auto_enabled(_XP_SCROLL_SENTINEL):
                xp_key = _consumable_auto_key(_XP_SCROLL_SENTINEL)
                if not _consumable_auto_running.get(xp_key, False):
                    _consumable_auto_running[xp_key] = True
                    def _run_xp_and_release():
                        try:
                            yield from _experience_scroll_auto_generator()
                        finally:
                            _consumable_auto_running[xp_key] = False
                    GLOBAL_CACHE.Coroutines.append(_run_xp_and_release())

        # Continuous upkeep categories (including Pumpkin Cookie morale upkeep) never run while dead.
        if player_dead:
            return

        now_ms = int(Utils.GetBaseTimestamp())
        for model_id, _ in consumables:
            value = int(model_id.value if hasattr(model_id, "value") else model_id)
            if (
                value == 0
                or value in _EVENT_TRIGGER_MODELS
                or value in (_XP_SCROLL_SENTINEL, _RES_SCROLL_SENTINEL)
                or not _consumable_auto_enabled(value)
            ):
                continue

            # Town Cake is intentionally the only category that runs in towns,
            # outposts and guild halls. Existing pcons/alcohol remain explorable.
            if value == _TOWN_CAKE_SENTINEL:
                if not is_town:
                    continue
            elif not is_explorable:
                continue

            key = _consumable_auto_key(value)
            if _consumable_auto_running.get(key, False):
                continue
            last_start = int(_consumable_auto_last_start_ms.get(key, 0) or 0)
            if now_ms - last_start < _CONSUMABLE_AUTO_MIN_INTERVAL_MS:
                continue

            _consumable_auto_last_start_ms[key] = now_ms
            _consumable_auto_running[key] = True
            GLOBAL_CACHE.Coroutines.append(_run_consumable_auto_once(value, cached_data))

        # Summoning page toggles share one scheduler so enabling several stones
        # can never dispatch multiple summons in the same tick.
        if is_explorable and any(
            _consumable_auto_enabled(int(model.value))
            for model, _texture_path, _label in summoning_consumables
        ):
            summon_key = _SUMMON_AUTO_KEY
            summon_last = int(_consumable_auto_last_start_ms.get(summon_key, 0) or 0)
            if (
                not _consumable_auto_running.get(summon_key, False)
                and now_ms - summon_last >= _SUMMON_AUTO_MIN_INTERVAL_MS
            ):
                _consumable_auto_last_start_ms[summon_key] = now_ms
                _consumable_auto_running[summon_key] = True

                def _run_summoning_and_release():
                    try:
                        yield from _summoning_auto_generator()
                    finally:
                        _consumable_auto_running[summon_key] = False

                GLOBAL_CACHE.Coroutines.append(_run_summoning_and_release())
    except Exception as exc:
        ConsoleLog("HeroAI", f"Consumable auto-upkeep tick error: {exc}", log=False)


_last_pcon_post_ms = 0

def _post_pcon_message(params, cached_data: CacheData):
    global _last_pcon_post_ms

    self_account = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(cached_data.account_email)
    if not self_account:
        return

    now_ms = int(Utils.GetBaseTimestamp())
    if now_ms - _last_pcon_post_ms < 100:
        return

    accounts = cached_data.party.accounts.values()
    sender_email = cached_data.account_email
    for account in accounts:
        GLOBAL_CACHE.ShMem.SendMessage(sender_email, account.AccountEmail, SharedCommandType.PCon, params)
    _last_pcon_post_ms = now_ms


def _manual_party_accounts(cached_data: CacheData) -> list[AccountStruct]:
    """Real same-map party accounts for leader manual one-shot item commands."""
    try:
        accounts = _conset_party_accounts(cached_data)
        if accounts:
            return accounts
    except Exception:
        pass

    result: list[AccountStruct] = []
    try:
        for account in cached_data.party.accounts.values():
            if not bool(account.IsSlotActive) or not bool(account.IsAccount) or bool(account.IsHero):
                continue
            if not str(account.AccountEmail or ""):
                continue
            result.append(account)
    except Exception:
        pass
    result.sort(key=lambda account: (int(account.AgentPartyData.PartyPosition), str(account.AccountEmail).casefold()))
    return result


def _first_shared_model_for_account(account: AccountStruct, model_ids) -> int:
    """Return the first carried model for one account using the supplied priority."""
    for raw_model in model_ids:
        model_id = int(raw_model.value if hasattr(raw_model, "value") else raw_model)
        if model_id > 0 and _shared_account_has_model(account, model_id):
            return model_id
    return 0


def _manual_exact_pcon_params(model_id: int) -> tuple[int, int, int, int]:
    """Use the existing exact-item PCon metadata when available."""
    model_id = int(model_id)
    params = _get_consumable_params(model_id)
    if int(params[0] or 0) == model_id:
        return tuple(int(v) for v in params)
    return (model_id, 0, 0, 0)


def _manual_send_exact_to_all(cached_data: CacheData, model_id: int, *, raw: bool = False) -> None:
    """Broadcast one exact item use attempt to every party account.

    raw=True deliberately strips effect/category metadata. Summoning manual mode
    uses this so every client simply attempts the selected stone once and lets the
    game itself enforce the one-active-summon rule.
    """
    model_id = int(model_id)
    if model_id <= 0:
        return
    params = (model_id, 0, 0, 0) if raw else _manual_exact_pcon_params(model_id)
    _post_pcon_message(params, cached_data)


def _manual_send_group_to_each(cached_data: CacheData, model_ids) -> None:
    """Each real party account uses at most one locally carried item from a category."""
    sender_email = str(cached_data.account_email or Player.GetAccountEmail() or "")
    if not sender_email:
        return
    for account in _manual_party_accounts(cached_data):
        model_id = _first_shared_model_for_account(account, model_ids)
        if model_id <= 0:
            continue
        GLOBAL_CACHE.ShMem.SendMessage(
            sender_email,
            str(account.AccountEmail),
            SharedCommandType.PCon,
            _manual_exact_pcon_params(model_id),
        )


def _manual_send_one_carrier(cached_data: CacheData, model_ids) -> None:
    """Use one item from one carrier only, with model-priority then party-position order."""
    sender_email = str(cached_data.account_email or Player.GetAccountEmail() or "")
    if not sender_email:
        return
    accounts = _manual_party_accounts(cached_data)
    for raw_model in model_ids:
        model_id = int(raw_model.value if hasattr(raw_model, "value") else raw_model)
        if model_id <= 0:
            continue
        for account in accounts:
            if not _shared_account_has_model(account, model_id):
                continue
            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                str(account.AccountEmail),
                SharedCommandType.PCon,
                _manual_exact_pcon_params(model_id),
            )
            return


def _manual_party_use_consumable_once(model_id: ModelID | int, cached_data: CacheData) -> None:
    """Leader right-click action for the main Consumables page.

    This is intentionally a manual one-shot path: it never changes auto toggles and
    does not enter the automatic upkeep state machines.
    """
    if not _is_live_party_leader():
        return

    value = int(model_id.value if hasattr(model_id, "value") else model_id)

    # Party-wide effects: one carrier only to avoid needless duplicate consumption.
    if value in _CONSET_AUTO_MODELS:
        _manual_send_one_carrier(cached_data, (value,))
        return
    if value == int(ModelID.Four_Leaf_Clover.value):
        _manual_send_one_carrier(cached_data, _PARTY_DP_MODELS)
        return
    if value == int(ModelID.Rainbow_Candy_Cane.value):
        _manual_send_one_carrier(cached_data, _PARTY_MORALE_MODELS)
        return
    if value == int(ModelID.Powerstone_Of_Courage.value):
        _manual_send_one_carrier(cached_data, (int(ModelID.Powerstone_Of_Courage.value),))
        return
    if value == _XP_SCROLL_SENTINEL:
        _manual_send_one_carrier(cached_data, _XP_SCROLL_MODELS)
        return
    if value == _RES_SCROLL_SENTINEL:
        _manual_send_one_carrier(cached_data, (_RES_SCROLL_MODEL_ID,))
        return

    # Grouped personal categories: every account picks one item it actually carries.
    if value == int(ModelID.Dwarven_Ale.value):
        try:
            _manual_send_group_to_each(cached_data, Routines.Yield.Upkeepers.ALCOHOL_ITEMS)
        except Exception:
            _manual_send_exact_to_all(cached_data, int(ModelID.Dwarven_Ale.value))
        return
    if value == _TOWN_CAKE_SENTINEL:
        try:
            _manual_send_group_to_each(cached_data, Routines.Yield.Upkeepers.CITY_SPEED_ITEMS)
        except Exception:
            pass
        return
    if value == _LUNAR_FORTUNE_SENTINEL:
        _manual_send_group_to_each(cached_data, _LUNAR_FORTUNE_MODELS)
        return

    # Normal personal item: every account gets one use attempt.
    if value > 0:
        _manual_send_exact_to_all(cached_data, value)


def _manual_party_use_summon_once(model_id: int, cached_data: CacheData) -> None:
    """Leader right-click Summoning action: all accounts directly try once.

    Per user requirement there is deliberately NO Active Summon precheck, NO
    Summoning Sickness pre-filter and NO claim/lock in this manual path. Guild Wars
    itself decides which attempt succeeds under its one-active-summon rule.
    """
    if not _is_live_party_leader():
        return
    _manual_send_exact_to_all(cached_data, int(model_id), raw=True)


def _use_all_cons(cached_data: CacheData):
    # Per-account consumables keep the original all-account one-shot behavior.
    # Conset is different: each missing party-wide effect is supplied by exactly
    # one account that actually carries the item, and only while everyone is alive.
    for model_id, (_texture_path, params) in consumables:
        value = int(model_id.value if hasattr(model_id, "value") else model_id)
        if value <= 0 or value == int(ModelID.Dwarven_Ale.value) or value in _EVENT_TRIGGER_MODELS:
            continue

        if value in _CONSET_AUTO_MODELS:
            yield from _run_partywide_conset_once(value, tuple(int(v) for v in params), cached_data)
            continue

        if value == int(ModelID.Four_Leaf_Clover.value):
            yield from _run_partywide_dp_once(cached_data)
            continue

        if value == int(ModelID.Rainbow_Candy_Cane.value):
            yield from _run_partywide_morale_once(cached_data)
            continue

        _post_pcon_message(params, cached_data)
        yield from Routines.Yield.wait(100)

#_post_pcon_message((ModelID.Essence_Of_Celerity.value, GLOBAL_CACHE.Skill.GetID("Essence_of_Celerity_item_effect"), 0, 0))

# UI-only inventory display cache. Inventory totals do not need to be scanned
# every render frame; 400 ms is responsive enough for stack changes without
# adding unnecessary inventory work to HeroAI's UI loop.
_CONSUMABLE_UI_COUNT_REFRESH_MS = 400
_consumable_ui_local_count_cache: dict[int, int] = {}
_consumable_ui_local_count_epoch_ms = 0


def _local_consumable_model_count(model_id: int) -> int:
    global _consumable_ui_local_count_epoch_ms
    model_id = int(model_id)
    now_ms = int(Utils.GetBaseTimestamp())
    if (
        not _consumable_ui_local_count_epoch_ms
        or now_ms - int(_consumable_ui_local_count_epoch_ms) >= _CONSUMABLE_UI_COUNT_REFRESH_MS
    ):
        _consumable_ui_local_count_cache.clear()
        _consumable_ui_local_count_epoch_ms = now_ms

    if model_id not in _consumable_ui_local_count_cache:
        try:
            _consumable_ui_local_count_cache[model_id] = max(
                0, int(GLOBAL_CACHE.Inventory.GetModelCount(model_id) or 0)
            )
        except Exception:
            _consumable_ui_local_count_cache[model_id] = 0
    return int(_consumable_ui_local_count_cache[model_id])


def _shared_account_model_count(account: AccountStruct, model_id: int) -> int:
    """Return one account's shared quantity for a model without summing other accounts."""
    try:
        total = 0
        bags = getattr(account, "InventoryBags", None)
        if bags is None:
            return 0
        for bag in bags.iter_bags():
            for slot in bag.Slots:
                if int(getattr(slot, "ModelID", 0) or 0) == int(model_id):
                    total += max(0, int(getattr(slot, "Quantity", 0) or 0))
        return int(total)
    except Exception:
        return 0


def _first_local_consumable_model(model_ids) -> tuple[int, int]:
    """Pick the first locally carried item using the same ordered priority as upkeep."""
    first_model = 0
    for raw_model in model_ids:
        model_id = int(raw_model.value if hasattr(raw_model, "value") else raw_model)
        if first_model == 0:
            first_model = model_id
        quantity = _local_consumable_model_count(model_id)
        if quantity > 0:
            return model_id, quantity
    return first_model, 0


def _first_party_carrier_model(cached_data: CacheData, model_ids) -> tuple[int, int]:
    """Mirror party-wide priority: model first, then the first real carrier account."""
    first_model = 0
    try:
        accounts = _conset_party_accounts(cached_data)
    except Exception:
        accounts = []

    for raw_model in model_ids:
        model_id = int(raw_model.value if hasattr(raw_model, "value") else raw_model)
        if first_model == 0:
            first_model = model_id
        for account in accounts:
            quantity = _shared_account_model_count(account, model_id)
            if quantity > 0:
                # Do not sum the same model across carriers. The auto logic will
                # use this first carrier, so display only this carrier's stack.
                return model_id, quantity

    # During early party-cache initialization, fall back to THIS account so the
    # UI still has a useful quantity instead of flashing an artificial zero.
    if not accounts and first_model:
        return first_model, _local_consumable_model_count(first_model)
    return first_model, 0


def _consumable_display_model_and_quantity(model_id: ModelID | int, cached_data: CacheData) -> tuple[int, int]:
    """Return the exact next-choice model and its single-stack/model quantity for this icon.

    Grouped categories intentionally do NOT total all supported items together.
    The selected model follows the same priority order as the corresponding
    upkeep routine. Party-wide categories show the first real carrier that the
    coordinator would command. Per-account categories show this account's stock.
    """
    value = int(model_id.value if hasattr(model_id, "value") else model_id)

    if value in _CONSET_AUTO_MODELS:
        return _first_party_carrier_model(cached_data, (value,))

    if value == int(ModelID.Four_Leaf_Clover.value):
        return _first_party_carrier_model(cached_data, _PARTY_DP_MODELS)

    if value == int(ModelID.Rainbow_Candy_Cane.value):
        return _first_party_carrier_model(cached_data, _PARTY_MORALE_MODELS)

    if value == int(ModelID.Pumpkin_Cookie.value):
        try:
            morale = int(Player.GetMorale() or 0)
        except Exception:
            morale = 100
        if 0 < morale < 100:
            selected_model, quantity = _first_local_consumable_model(_PERSONAL_DP_MODELS)
            if quantity > 0:
                return selected_model, quantity
        return (
            int(ModelID.Pumpkin_Cookie.value),
            _local_consumable_model_count(int(ModelID.Pumpkin_Cookie.value)),
        )

    if value == int(ModelID.Dwarven_Ale.value):
        try:
            return _first_local_consumable_model(Routines.Yield.Upkeepers.ALCOHOL_ITEMS)
        except Exception:
            return value, _local_consumable_model_count(value)

    if value == _TOWN_CAKE_SENTINEL:
        try:
            return _first_local_consumable_model(Routines.Yield.Upkeepers.CITY_SPEED_ITEMS)
        except Exception:
            return 0, 0

    if value == _LUNAR_FORTUNE_SENTINEL:
        return _first_local_consumable_model(_LUNAR_FORTUNE_MODELS)

    if value == _XP_SCROLL_SENTINEL:
        return _first_local_consumable_model(_XP_SCROLL_MODELS)

    if value == _RES_SCROLL_SENTINEL:
        return _RES_SCROLL_MODEL_ID, _local_consumable_model_count(_RES_SCROLL_MODEL_ID)

    return value, _local_consumable_model_count(value)


def _draw_consumable_master_button(label: str, enabled: bool, button_id: str, width: float = 118.0) -> bool:
    """Compact ON/OFF master button with clear green/red state."""
    if enabled:
        colors = (
            (0.10, 0.32, 0.13, 1.00),
            (0.14, 0.42, 0.18, 1.00),
            (0.08, 0.26, 0.10, 1.00),
        )
    else:
        colors = (
            (0.34, 0.10, 0.10, 1.00),
            (0.44, 0.14, 0.14, 1.00),
            (0.28, 0.08, 0.08, 1.00),
        )
    PyImGui.push_style_color(PyImGui.ImGuiCol.Button, colors[0])
    PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, colors[1])
    PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, colors[2])
    try:
        return PyImGui.button(f"{label}: {'ON' if enabled else 'OFF'}##{button_id}", width, 0)
    finally:
        PyImGui.pop_style_color(3)


def _draw_consumable_master_toggles(cached_data: CacheData, suffix: str) -> None:
    """Single Auto switch: leader resets party; followers toggle only themselves."""
    account_enabled = _account_consumable_master_enabled()
    if _draw_consumable_master_button("Auto", account_enabled, f"Auto{suffix}"):
        new_enabled = not account_enabled
        _set_account_consumable_master_enabled(new_enabled)
        if _is_live_party_leader():
            _set_global_consumable_master_enabled(new_enabled)


def _draw_consumable_toggle_grid(cached_data: CacheData, table_id: str) -> bool:
    """Draw consumable toggles; return True when an icon consumed a right-click."""
    right_click_handled = False
    style = ImGui.get_style()
    btn_size = 48  # Official v06: enlarged icon grid
    icon_inset = 4
    style.CellPadding.push_style_var(3, 3)
    try:
        if ImGui.begin_table(table_id, 7, PyImGui.TableFlags.SizingStretchProp):
            PyImGui.table_next_column()

            for model_id, (texture_path, _params) in consumables:
                if model_id == 0:
                    PyImGui.table_next_column()
                    continue

                active = _consumable_auto_enabled(model_id)
                PyImGui.push_style_color(PyImGui.ImGuiCol.Button, (0, 0, 0, 0))
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, (0, 0, 0, 0))
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, (0, 0, 0, 0))
                PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (0, 0, 0, 0))
                clicked = PyImGui.button(
                    f"##AutoConConfig {table_id} {int(model_id.value if hasattr(model_id, 'value') else model_id)}",
                    btn_size,
                    btn_size,
                )
                PyImGui.pop_style_color(4)

                icon_right_clicked = bool(PyImGui.is_item_hovered() and PyImGui.is_mouse_clicked(1))
                if icon_right_clicked:
                    right_click_handled = True
                    if _is_live_party_leader():
                        _manual_party_use_consumable_once(model_id, cached_data)

                if clicked:
                    active = not active
                    _set_consumable_auto_enabled(model_id, active)

                x, y = PyImGui.get_item_rect_min()
                ThemeTextures.Inventory_Slots.value.get_texture().draw_in_drawlist(
                    (x, y), (btn_size, btn_size)
                )

                _display_model, quantity = _consumable_display_model_and_quantity(model_id, cached_data)

                # Enabled status is a soft background, not a border. Keep every
                # item icon at normal brightness whether the toggle is ON or OFF.
                if active:
                    bg_color = (
                        Color(245, 205, 70, 72).color_int
                        if int(quantity) < 10
                        else Color(80, 220, 115, 62).color_int
                    )
                    PyImGui.draw_list_add_rect_filled(
                        x + 1,
                        y + 1,
                        x + btn_size - 1,
                        y + btn_size - 1,
                        bg_color,
                        3.0,
                        0,
                    )

                value = int(model_id.value if hasattr(model_id, 'value') else model_id)
                draw_texture_path = texture_path
                if value in (_LUNAR_FORTUNE_SENTINEL, _XP_SCROLL_SENTINEL):
                    draw_texture_path = _item_texture_path(int(_display_model), texture_path)
                elif value == _RES_SCROLL_SENTINEL:
                    # Official v06: use the corrected Item Models Scroll of Resurrection icon.
                    draw_texture_path = texture_path

                ImGui.DrawTextureInDrawList(
                    (x + icon_inset, y + icon_inset),
                    (btn_size - icon_inset * 2, btn_size - icon_inset * 2),
                    draw_texture_path,
                    tint=(255, 255, 255, 255),
                )

                # Quantity always stays visible. It represents only the exact
                # currently selected item, never the sum of a grouped category.
                quantity_text = str(max(0, int(quantity)))
                ImGui.push_font("Regular", 13)
                try:
                    text_w, text_h = PyImGui.calc_text_size(quantity_text)
                    text_x = x + btn_size - text_w - 3
                    text_y = y + btn_size - text_h - 2
                    PyImGui.draw_list_add_text(
                        text_x + 1,
                        text_y + 1,
                        Color(0, 0, 0, 230).color_int,
                        quantity_text,
                    )
                    PyImGui.draw_list_add_text(
                        text_x,
                        text_y,
                        Color(255, 255, 255, 255).color_int,
                        quantity_text,
                    )
                finally:
                    ImGui.pop_font()

                label = _consumable_auto_label(model_id)
                state = "ON" if active else "OFF"
                value = int(model_id.value if hasattr(model_id, 'value') else model_id)
                if value == int(ModelID.Dwarven_Ale.value):
                    extra = "\nUses any supported alcohol; maintains drunk level >= 2 in explorable areas."
                elif value == _TOWN_CAKE_SENTINEL:
                    extra = "\nUses city-speed sweets only while moving in town."
                elif value == int(ModelID.Rainbow_Candy_Cane.value):
                    extra = (
                        "\nRainbow/Honeycomb +5%; Elixir/Seal +10%."
                        "\nSeal also recharges skills."
                    )
                elif value == int(ModelID.Four_Leaf_Clover.value):
                    extra = "\nClover/Oath: clears party Death Penalty."
                elif value == int(ModelID.Pumpkin_Cookie.value):
                    extra = "\nUses DP removers first, then Pumpkin Cookies to +10%."
                elif value == int(ModelID.Powerstone_Of_Courage.value):
                    extra = (
                        "\nClears party DP and gives +10% morale."
                        "\nUses on map entry and after a full-party wipe."
                    )
                elif value == _LUNAR_FORTUNE_SENTINEL:
                    extra = "\nUses Lunar Fortunes until Lunar Blessing is active."
                elif value == _XP_SCROLL_SENTINEL:
                    extra = "\nUses one party XP scroll on combat entry only when no Insight effect is active."
                elif value == _RES_SCROLL_SENTINEL:
                    extra = "\nUses a Resurrection Scroll when an ally dies within Earshot."
                else:
                    extra = ""
                manual_hint = (
                    "\nRight-click: party uses once."
                    if _is_live_party_leader()
                    else "\nRight-click party-use is leader only."
                )
                ImGui.show_tooltip(
                    f"{label} - Auto upkeep {state}\n"
                    f"Left-click toggles THIS account only.{manual_hint}{extra}"
                )
                PyImGui.table_next_column()

            ImGui.end_table()
    finally:
        style.CellPadding.pop_style_var()
    return right_click_handled



def _draw_summoning_toggle_grid(cached_data: CacheData, table_id: str) -> bool:
    """Draw 21 summon toggles; return True when an icon consumed a right-click."""
    right_click_handled = False
    style = ImGui.get_style()
    btn_size = 48
    icon_inset = 4
    style.CellPadding.push_style_var(3, 3)
    try:
        if ImGui.begin_table(table_id, 7, PyImGui.TableFlags.SizingStretchProp):
            PyImGui.table_next_column()

            for model, texture_path, label in summoning_consumables:
                model_id = int(model.value)
                active = _consumable_auto_enabled(model_id)

                PyImGui.push_style_color(PyImGui.ImGuiCol.Button, (0, 0, 0, 0))
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, (0, 0, 0, 0))
                PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, (0, 0, 0, 0))
                PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (0, 0, 0, 0))
                clicked = PyImGui.button(
                    f"##AutoSummonConfig {table_id} {model_id}",
                    btn_size,
                    btn_size,
                )
                PyImGui.pop_style_color(4)

                icon_right_clicked = bool(PyImGui.is_item_hovered() and PyImGui.is_mouse_clicked(1))
                if icon_right_clicked:
                    right_click_handled = True
                    if _is_live_party_leader():
                        _manual_party_use_summon_once(model_id, cached_data)

                if clicked:
                    active = not active
                    _set_consumable_auto_enabled(model_id, active)

                x, y = PyImGui.get_item_rect_min()
                ThemeTextures.Inventory_Slots.value.get_texture().draw_in_drawlist(
                    (x, y), (btn_size, btn_size)
                )

                quantity = _local_consumable_model_count(model_id)
                if active:
                    bg_color = (
                        Color(245, 205, 70, 72).color_int
                        if int(quantity) < 10
                        else Color(80, 220, 115, 62).color_int
                    )
                    PyImGui.draw_list_add_rect_filled(
                        x + 1,
                        y + 1,
                        x + btn_size - 1,
                        y + btn_size - 1,
                        bg_color,
                        3.0,
                        0,
                    )

                if model_id == int(ModelID.Igneous_Summoning_Stone.value):
                    # Official v06: keep the corrected Item Models Igneous icon consistently.
                    draw_texture_path = texture_path
                else:
                    draw_texture_path = _item_texture_path(model_id, texture_path)
                ImGui.DrawTextureInDrawList(
                    (x + icon_inset, y + icon_inset),
                    (btn_size - icon_inset * 2, btn_size - icon_inset * 2),
                    draw_texture_path,
                    tint=(255, 255, 255, 255),
                )

                quantity_text = str(max(0, int(quantity)))
                ImGui.push_font("Regular", 13)
                try:
                    text_w, text_h = PyImGui.calc_text_size(quantity_text)
                    text_x = x + btn_size - text_w - 3
                    text_y = y + btn_size - text_h - 2
                    PyImGui.draw_list_add_text(
                        text_x + 1,
                        text_y + 1,
                        Color(0, 0, 0, 230).color_int,
                        quantity_text,
                    )
                    PyImGui.draw_list_add_text(
                        text_x,
                        text_y,
                        Color(255, 255, 255, 255).color_int,
                        quantity_text,
                    )
                finally:
                    ImGui.pop_font()

                state = "ON" if active else "OFF"
                manual_hint = (
                    "\nRight-click: all party accounts try this summon once."
                    if _is_live_party_leader()
                    else "\nRight-click party-use is leader only."
                )
                ImGui.show_tooltip(
                    f"{label} - Auto summon {state}\n"
                    "Left-click toggles THIS account only; auto mode still waits for no active summon and no Summoning Sickness."
                    f"{manual_hint}"
                )
                PyImGui.table_next_column()

            ImGui.end_table()
    finally:
        style.CellPadding.pop_style_var()
    return right_click_handled


def _draw_consumable_page_row(cached_data: CacheData, suffix: str) -> None:
    """Manual Use Cons plus one button to switch between Consumables and Summoning."""
    global _consumables_ui_page

    if PyImGui.button("Use Cons"):
        GLOBAL_CACHE.Coroutines.append(_use_all_cons(cached_data))

    PyImGui.same_line(0, 6)
    if _consumables_ui_page == "summoning":
        if PyImGui.button(f"< Consumables##ConPage{suffix}"):
            _consumables_ui_page = "consumables"
    else:
        if PyImGui.button(f"Summoning >##ConPage{suffix}"):
            _consumables_ui_page = "summoning"


def draw_consumables_window(cached_data: CacheData):
    global configure_consumables_window_open
    global _configure_consumables_popup_pending

    if not configure_consumables_window_open:
        return

    # Official v06: the default is applied only if this window has never had a
    # saved ImGui position. Otherwise ImGui restores the last dragged location.
    if _configure_consumables_popup_pending:
        PyImGui.set_next_window_pos(_configure_consumables_popup_anchor, PyImGui.ImGuiCond.FirstUseEver)
        _configure_consumables_popup_pending = False

    flags = (
        PyImGui.WindowFlags.NoTitleBar
        | PyImGui.WindowFlags.NoResize
        | PyImGui.WindowFlags.AlwaysAutoResize
        | PyImGui.WindowFlags.NoFocusOnAppearing
    )

    opened = PyImGui.begin(
        "Configure Consumables##HeroAIConsumablesFloating",
        True,
        flags,
    )

    right_click_handled = False
    if opened:
        _draw_consumable_master_toggles(cached_data, "Popup")
        _draw_consumable_page_row(cached_data, "Popup")

        if _consumables_ui_page == "summoning":
            right_click_handled = _draw_summoning_toggle_grid(cached_data, "##SummonAutoTablePopup")
        else:
            right_click_handled = _draw_consumable_toggle_grid(cached_data, "##ConAutoTablePopup")

    # Right-clicking an item icon is reserved for the leader's one-shot party use.
    # Right-clicking anywhere else keeps the existing quick-close behavior.
    if PyImGui.is_mouse_clicked(1) and not right_click_handled:
        configure_consumables_window_open = False

    PyImGui.end()

def draw_base_consumables_window(cached_data: CacheData):
    global configure_base_consumables_window_open

    if not configure_base_consumables_window_open:
        return

    _flags = PyImGui.WindowFlags(
        PyImGui.WindowFlags.NoTitleBar
        | PyImGui.WindowFlags.NoResize
        | PyImGui.WindowFlags.AlwaysAutoResize
        | PyImGui.WindowFlags.NoSavedSettings
    )
    if ImGui.Begin(ini_key=cached_data.consumables_ini_key, name="Configure Consumables", p_open=True, flags=_flags):
        _draw_consumable_master_toggles(cached_data, "Base")
        _draw_consumable_page_row(cached_data, "Base")

        if _consumables_ui_page == "summoning":
            _draw_summoning_toggle_grid(cached_data, "##SummonAutoTableBase")
        else:
            _draw_consumable_toggle_grid(cached_data, "##ConAutoTableBase")
        ImGui.End(cached_data.consumables_ini_key)


def draw_command_panel(window: WindowModule, cached_data: CacheData):
    style = ImGui.get_style()

    size = window.window_size
    style.WindowPadding.push_style_var(5, 5)
    
    info = settings.get_hero_panel_info(window.window_name)
    # if info:
    #     PyImGui.set_next_window_pos((info.x, info.y), PyImGui.ImGuiCond.Always)
        
    ##TODO: Fix global options
    if window.begin():        
        avail = PyImGui.get_content_region_avail()
        avail_x = avail[0]
        
        table_width = avail_x
        btn_size = (table_width / 5) - 4
        
        from .ui_base import HeroAI_BaseUI
        
        if ImGui.begin_child("##GlobalHeroOptionsChild",( table_width, (btn_size  * 2) - 6), False, PyImGui.WindowFlags.NoScrollbar | PyImGui.WindowFlags.NoScrollWithMouse):
            HeroAI_BaseUI.DrawPanelButtons("command_panel", cached_data.global_options, set_global=True)

        ImGui.end_child()                

        window.process_window()
        
        if window.changed:                
            if PySystem.Console.is_window_active():                
                window_info = settings.get_hero_panel_info(window.window_name)
                
                if window_info:
                    if not window_info in settings.HeroPanelPositions.values():
                        settings.HeroPanelPositions[window.window_name] = window_info
                        
                    window_info.x = round(window.window_pos[0])
                    window_info.y = round(window.window_pos[1])
                    window_info.collapsed = window.collapse
                    window_info.open = window.open                    
                    settings.save_settings()
            
    window.end()
    style.WindowPadding.pop_style_var()
    
    pass  # Implementation of command panel drawing logic goes here

hotbars : dict[str, WindowModule] = {}
configure_hotbar = None
assign_command_slot = None

# Offsets for different UI themes and hotbar positions
hotbar_offsets : dict[StyleTheme, dict[str, dict]] = {
    StyleTheme.Guild_Wars: {
        "PartyWindow": {
            HorizontalAlignment.LeftOf.name: -8,
            HorizontalAlignment.Left.name: 0,
            HorizontalAlignment.Center.name: 2,
            HorizontalAlignment.Right.name: 0,
            HorizontalAlignment.RightOf.name: 10,
            
            VerticalAlignment.Above.name: -4,
            VerticalAlignment.Below.name: 2,
            },
        "Skillbar": {
            HorizontalAlignment.LeftOf.name: -17,
            HorizontalAlignment.Left.name: -6,
            HorizontalAlignment.Center.name: 2,
            HorizontalAlignment.Right.name: 11,
            HorizontalAlignment.RightOf.name: 19,
            
            VerticalAlignment.Above.name: 5,
            VerticalAlignment.Top.name: 0,
            VerticalAlignment.Bottom.name: 8,
            VerticalAlignment.Below.name: 8,
            },
    },
    StyleTheme.Py4GW: {
        "PartyWindow": {
            HorizontalAlignment.LeftOf.name: -8,
            HorizontalAlignment.Left.name: 0,
            HorizontalAlignment.Center.name: 2,
            HorizontalAlignment.Right.name: 0,
            HorizontalAlignment.RightOf.name: 10,
            
            VerticalAlignment.Above.name: -4,
            VerticalAlignment.Below.name: 2,
            },
        "Skillbar": {
            HorizontalAlignment.LeftOf.name: -17,
            HorizontalAlignment.Left.name: -6,
            HorizontalAlignment.Center.name: 2,
            HorizontalAlignment.Right.name: 11,
            HorizontalAlignment.RightOf.name: 19,
            
            VerticalAlignment.Above.name: 5,
            VerticalAlignment.Top.name: 0,
            VerticalAlignment.Bottom.name: 8,
            VerticalAlignment.Below.name: 8,
            },
    },
    StyleTheme.Minimalus: {
        "PartyWindow": {
            HorizontalAlignment.LeftOf.name: -8,
            HorizontalAlignment.Left.name: 6,
            HorizontalAlignment.Center.name: 1,
            HorizontalAlignment.Right.name: -3,
            HorizontalAlignment.RightOf.name: 10,
            
            VerticalAlignment.Above.name: -1,
            VerticalAlignment.Top.name: -2,
            VerticalAlignment.Bottom.name: -10,
            VerticalAlignment.Below.name: -11,
            },
        "Skillbar": {
            HorizontalAlignment.LeftOf.name: 1,
            HorizontalAlignment.Left.name: 0,
            HorizontalAlignment.Center.name: 2,
            HorizontalAlignment.Right.name: 1,
            HorizontalAlignment.RightOf.name: 1,
            
            VerticalAlignment.Above.name: 1,
            VerticalAlignment.Top.name: 0,
            VerticalAlignment.Bottom.name: 1,
            VerticalAlignment.Below.name: 0,
            },
    },
}
    
def draw_hotbar(hotbar: Settings.CommandHotBar, cached_data: CacheData):
    global configure_hotbar
    style = ImGui.get_style()
    window = hotbars.get(hotbar.identifier, None)
    
    btn_size = hotbar.button_size
    rows = len(hotbar.commands)
    cols = max(1, max(len(row) for _, row in hotbar.commands.items()) if rows > 0 else 0)
    cell_spacing = (1, 1)
    
    style.CellPadding.push_style_var(cell_spacing[0], cell_spacing[1])

    height = max(btn_size, rows * (btn_size + cell_spacing[1]))
    width = max(btn_size, cols * (btn_size + cell_spacing[0]) - 1)
    
    if not window:
        window = WindowModule(hotbar.identifier, hotbar.identifier, window_pos=(hotbar.position[0], hotbar.position[1]), window_flags=PyImGui.WindowFlags(PyImGui.WindowFlags.NoTitleBar | PyImGui.WindowFlags.AlwaysAutoResize), can_close=False)
        hotbars[hotbar.identifier] = window
        
    if hotbar.docked is not Docked.Freely:
        window_width = window.window_size[0]
        window_height = window.window_size[1]
        
        window_half_size = (window_width / 2, window_height / 2)
        
        match hotbar.docked:
            case Docked.PartyWindow:
                party_frame = Frame(FrameId.PartyFormation)
                party_window = party_frame.coords() if party_frame.exists else None
                
                if party_window:
                    left, top, right, bottom = party_window
                    
                    offsets = hotbar_offsets.get(style.Theme, hotbar_offsets.get(StyleTheme.Py4GW, {})).get("PartyWindow", {})                    
                    x_offset = offsets.get(hotbar.alignment.horizontal.name, 0)
                    y_offset = offsets.get(hotbar.alignment.vertical.name, 0)
                    
                    x , y = ImGui.get_position_aligned(
                        hotbar.alignment,
                        (left, top),
                        (right - left, bottom - top),
                        (window_width, window_height),
                        (x_offset, y_offset))
                    
                    hotbar.position = (int(x), int(y))
                
            case Docked.Skillbar:
                skillbar_frame = Frame(FrameId.Skillbar)
                skillbar_window = skillbar_frame.coords() if skillbar_frame.exists else None
                if skillbar_window:
                    left, top, right, bottom = skillbar_window
                    
                    offsets = hotbar_offsets.get(style.Theme, hotbar_offsets.get(StyleTheme.Py4GW, {})).get("Skillbar", {})       
                    x_offset = offsets.get(hotbar.alignment.horizontal.name, 0)
                    y_offset = offsets.get(hotbar.alignment.vertical.name, 0)
                    
                    x , y = ImGui.get_position_aligned(
                        hotbar.alignment,
                        (left, top),
                        (right - left, bottom - top),
                        (window_width, window_height),
                        (x_offset, y_offset))
                    
                    hotbar.position = (int(x), int(y))
        
        PyImGui.set_next_window_pos(hotbar.position, PyImGui.ImGuiCond.Always)
           

    size = window.window_size
    style.WindowPadding.push_style_var(5, 5)
    draw_textures = style.Theme in ImGui.Textured_Themes
    
    if window.begin():
        explorable = Map.IsExplorable()
        
        is_window_active = PySystem.Console.is_window_active()

        if ImGui.begin_child("##HotbarCommandsChild" + hotbar.identifier, (width, height), False, PyImGui.WindowFlags.NoScrollbar | PyImGui.WindowFlags.NoScrollWithMouse):
            if PyImGui.is_rect_visible((width, height)):
                if ImGui.begin_table("##HotbarTable" + hotbar.identifier, cols, PyImGui.TableFlags.NoFlag, width=width, height=height):
                    PyImGui.table_next_row()
                    PyImGui.table_next_column()
                    
                    def draw_cmnd_tooltip(tooltip: str):
                        if PyImGui.is_item_hovered():
                            PyImGui.set_next_window_size((250, 0), PyImGui.ImGuiCond.Always)
                            if ImGui.begin_tooltip():
                                ImGui.text_wrapped(tooltip)
                                
                                ImGui.text_colored(
                                    "Shift + Left Click to configure hotbar",
                                    gray_color.color_tuple     ,
                                    12               
                                )
                                
                                ImGui.text_colored(
                                    "Ctrl + Left Click to assign command",
                                    gray_color.color_tuple      ,
                                    12               
                                )
                            
                                ImGui.end_tooltip()

                    for row, cmd_row in hotbar.commands.items():
                        for col, cmd_name in cmd_row.items():
                            cmd = commands.Commands.get(cmd_name, None)
                            if not cmd:
                                ImGui.dummy(btn_size, btn_size)
                                ImGui.push_font("Regular", 24)
                                text_size = PyImGui.calc_text_size("?")
                                item_rect_min = PyImGui.get_item_rect_min()
                                
                                text_x = item_rect_min[0] + (btn_size - text_size[0]) / 2
                                text_y = item_rect_min[1] + (btn_size - text_size[1]) / 2 + 2
                                PyImGui.draw_list_add_text(text_x, text_y, style.Text.color_int, "?")
                                ImGui.pop_font()
                                if draw_textures:
                                    ThemeTextures.Skill_Slot_Empty.value.get_texture().draw_in_drawlist(
                                        (item_rect_min[0] + 1, item_rect_min[1] + 1),
                                        (btn_size - 2, btn_size - 2),
                                        tint=(255, 255, 255, 255) if PyImGui.is_item_hovered() else (200, 200, 200, 255)
                                    )
                                else:
                                    PyImGui.draw_list_add_rect_filled(
                                        item_rect_min[0] + 1, 
                                        item_rect_min[1] + 1,
                                        item_rect_min[0] + btn_size - 2, 
                                        item_rect_min[1] + btn_size - 2,
                                        style.Button.opacity(0.3).color_int,
                                        style.FrameRounding.value1,
                                        0,
                                    )
                                    PyImGui.draw_list_add_rect(
                                        item_rect_min[0] + 1, 
                                        item_rect_min[1] + 1,
                                        item_rect_min[0] + btn_size - 2, 
                                        item_rect_min[1] + btn_size - 2,
                                        style.Button.color_int,
                                        style.FrameRounding.value1,
                                        0,
                                        1
                                    )

                            elif cmd.is_separator:
                                ImGui.dummy(btn_size, btn_size)
                                item_rect_min = PyImGui.get_item_rect_min()
                                if draw_textures:
                                    ThemeTextures.Skill_Slot_Empty.value.get_texture().draw_in_drawlist(
                                        (item_rect_min[0] + 1, item_rect_min[1] + 1),
                                        (btn_size - 2, btn_size - 2),
                                        tint=(255, 255, 255, 255) if PyImGui.is_item_hovered() else (200, 200, 200, 255)
                                    )
                                else:
                                    PyImGui.draw_list_add_rect_filled(
                                        item_rect_min[0] + 1, 
                                        item_rect_min[1] + 1,
                                        item_rect_min[0] + btn_size - 2, 
                                        item_rect_min[1] + btn_size - 2,
                                        style.Button.opacity(0.3).color_int,
                                        style.FrameRounding.value1,
                                        0,
                                    )
                                    PyImGui.draw_list_add_rect(
                                        item_rect_min[0] + 1, 
                                        item_rect_min[1] + 1,
                                        item_rect_min[0] + btn_size - 2, 
                                        item_rect_min[1] + btn_size - 2,
                                        style.Button.color_int,
                                        style.FrameRounding.value1,
                                        0,
                                        1
                                    )
                            else:
                                valid_map_type = True
                                if cmd.map_types and explorable:
                                    valid_map_type = "Explorable" in cmd.map_types
                                    
                                elif cmd.map_types and not explorable:
                                    valid_map_type = "Outpost" in cmd.map_types
                                    
                                if draw_button(cmd.name, cmd.icon, btn_size, btn_size, False, valid_map_type):
                                    if Map.IsExplorable():
                                        accounts = [acct for acct in cached_data.party.accounts.values()]
                                    else:
                                        accounts = [acct for acct in GLOBAL_CACHE.ShMem.GetAllAccountData() if SameMapOrPartyAsAccount(acct)]
                                        
                                    cmd(accounts)
                                

                            if PyImGui.is_item_clicked(0) and PyImGui.get_io().key_shift:
                                configure_hotbar = hotbar
                            
                            elif PyImGui.is_item_clicked(0) and PyImGui.get_io().key_ctrl:
                                global assign_command_slot
                                assign_command_slot = (hotbar.identifier, row, col)
                                
                            draw_cmnd_tooltip(cmd.tooltip if cmd else f"Unknown command '{cmd_name}'")
                            PyImGui.table_next_column()
                            
                    ImGui.end_table()
                
        ImGui.end_child()
        style.CellPadding.pop_style_var()


        # Free-floating hotbar position is delegated to ImGui's native persistence (imgui.ini);
        # it is no longer captured from get_window_pos() and written back to settings.
        # Anchored hotbars (Party/Skillbar/etc.) are still positioned live above.
            
    window.end()
    style.WindowPadding.pop_style_var()
    
def draw_command_select_popup():
    global assign_command_slot
    
    if assign_command_slot is None:
        return        
    
    style = ImGui.get_style()
    PyImGui.open_popup("Assign Command")
    PyImGui.set_next_window_size((250, 300), PyImGui.ImGuiCond.Always)
    
    if PyImGui.begin_popup("Assign Command"):
        is_appearing = PyImGui.is_window_appearing()
        if is_appearing:
            io = PyImGui.get_io()
            mouse_x, mouse_y = io.mouse_pos_x, io.mouse_pos_y
            PyImGui.set_window_pos(mouse_x, mouse_y - 170, PyImGui.ImGuiCond.Always)

        identifier, row, col = assign_command_slot[0], assign_command_slot[1], assign_command_slot[2]
        
        hotbar = settings.CommandHotBars.get(identifier, None)
        if not hotbar:
            assign_command_slot = None
            PyImGui.close_current_popup()
            return

        ImGui.text(f"Command Slot [{assign_command_slot[1]}|{assign_command_slot[2]}]")

        if ImGui.begin_child("##CommandSelectChild", (0, 0), True):
            for cmd_name, cmd in commands.Commands.items():
                PyImGui.begin_group()
                draw_button(cmd.name, cmd.icon, 32, 32)
                PyImGui.same_line(0, 5)
                ImGui.text_aligned(cmd_name, 0, 32, Alignment.MidLeft, 14)
                PyImGui.end_group()

                if PyImGui.is_item_clicked(0):
                    hotbar.commands[row][col] = cmd.name
                    settings.save_settings()
                    
                    assign_command_slot = None
                    PyImGui.close_current_popup()
                    
                ImGui.show_tooltip(cmd.description or cmd.tooltip)
            
        ImGui.end_child()
                    
        if not is_appearing and PyImGui.is_mouse_clicked(0) and not PyImGui.is_any_item_hovered() and not PyImGui.is_window_hovered():
            assign_command_slot = None
            PyImGui.close_current_popup()
            
        PyImGui.end_popup()

def draw_configure_hotbar():
    global configure_hotbar
    
    if configure_hotbar is None:
        return        
    
    style = ImGui.get_style()
    PyImGui.open_popup("Configure Hotbar")

    if PyImGui.begin_popup("Configure Hotbar"):
        is_appearing = PyImGui.is_window_appearing()
        if is_appearing:
            io = PyImGui.get_io()
            mouse_x, mouse_y = io.mouse_pos_x, io.mouse_pos_y
            PyImGui.set_window_pos(mouse_x, mouse_y - 80, PyImGui.ImGuiCond.Always)

        ImGui.text(f"Configure '{configure_hotbar.identifier}'")
        rows = len(configure_hotbar.commands)
        cols = max(1, max(len(row) for _, row in configure_hotbar.commands.items()) if rows > 0 else 0)
        
        button_size = ImGui.input_int("Button Size", configure_hotbar.button_size)
        if button_size != configure_hotbar.button_size and button_size >= 10 and button_size <= 256:
            configure_hotbar.button_size = button_size
            settings.save_settings()
        ImGui.show_tooltip("Size of each command button in pixels (10-256)")
            
        desired_rows = ImGui.input_int("Rows", rows)
        desired_cols = ImGui.input_int("Columns", cols)
        
        if desired_rows != rows or desired_cols != cols:
            new_commands = {}
            
            for r in range(desired_rows):
                new_commands[r] = {}
                for c in range(desired_cols):
                    if r in configure_hotbar.commands and c in configure_hotbar.commands[r]:
                        new_commands[r][c] = configure_hotbar.commands[r][c]
                    else:
                        new_commands[r][c] = "Empty"
                        
            configure_hotbar.commands = new_commands
            settings.save_settings()
                
        if not is_appearing and PyImGui.is_mouse_clicked(0) and not PyImGui.is_any_item_hovered() and not PyImGui.is_window_hovered():
            configure_hotbar = None
            PyImGui.close_current_popup()
            
        PyImGui.end_popup()

def draw_hotbars(cached_data: CacheData):
    for _, hotbar in settings.CommandHotBars.items():
        if hotbar.visible:
            draw_hotbar(hotbar, cached_data)
            
    draw_configure_hotbar()
    draw_command_select_popup()
    draw_consumables_window(cached_data)
    draw_base_consumables_window(cached_data)

dialog_open : bool = False
frame_coords : list[tuple[int, tuple[int, int, int, int]]] = []
dialog_coords : tuple[int, int, int, int] = (0, 0, 0, 0)
overlay = Overlay()

# Load user32.dll
user32 = ctypes.windll.user32

# Virtual-key code for left mouse button
VK_LBUTTON = 0x01

def is_left_pressed() -> bool:    
    return bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)

_left_was_pressed = False

def is_left_mouse_clicked() -> bool:
    """
    Returns True exactly once per full click (press â†’ release).
    False at all other times.
    """
    global _left_was_pressed
    
    # Is button physically down now?
    pressed = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
    
    # Detect release event (was pressed, now not pressed)
    clicked = _left_was_pressed and not pressed

    # Update state for next call
    _left_was_pressed = pressed

    return clicked
    
def draw_dialog_overlay(cached_data: CacheData, messages: list[tuple[int, SharedMessageStruct]]):
    global frame_coords, dialog_open, dialog_coords
    if not settings.ShowDialogOverlay:
        return
    
    own_data = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(cached_data.account_email)
    if own_data is None or not own_data.AgentPartyData.IsPartyLeader:
        return
    
    if dialog_throttle.IsExpired():
        dialog_throttle.Reset()
        dialog_open = UIManager.IsNPCDialogVisible()        
        frame_coords = UIManager.GetDialogButtonFrames() if dialog_open else []
            
    if not frame_coords or not dialog_open:
        return
    
    pyimgui_io = PyImGui.get_io()
    mouse_pos = (pyimgui_io.mouse_pos_x, pyimgui_io.mouse_pos_y)
    
    if PySystem.Console.is_window_active(): 
        sorted_frames = sorted(frame_coords, key=lambda x: (x[1][1], x[1][0]))  # Sort by Y, then X
               
        for i, (frame_id, frame) in enumerate(sorted_frames):                
            if ImGui.is_mouse_in_rect((frame[0], frame[1], frame[2] - frame[0], frame[3] - frame[1]), mouse_pos):                                
                if is_left_mouse_clicked() and pyimgui_io.key_ctrl:
                    accounts = [acc for acc in cached_data.party.accounts.values() if acc.AccountEmail != cached_data.account_email]
                    commands.send_automatic_dialog(accounts, i)
                    return
                else:
                    ImGui.begin_tooltip()
                    ImGui.text_colored(f"Ctrl + Click to select on all accounts.", gray_color.color_tuple, 12)
                    ImGui.end_tooltip()

    pass

def draw_skip_cutscene_overlay():
    in_cutscene = Map.IsInCinematic()
    
    if in_cutscene:
        pyimgui_io = PyImGui.get_io()
        mouse = (pyimgui_io.mouse_pos_x, pyimgui_io.mouse_pos_y)
        skip_cutscene_id = Frame(FrameId.ScreenFrame.C6.ScreenFrame.SkipCutsceneButton)
        
        frame_exists = skip_cutscene_id.exists
        if frame_exists:          
            frame = skip_cutscene_id.coords()
            
            if ImGui.is_mouse_in_rect((frame[0], frame[1], frame[2] - frame[0], frame[3] - frame[1]), mouse):                            
                if is_left_mouse_clicked() and pyimgui_io.key_ctrl:
                    current_account = Player.GetAccountEmail()
                    
                    if current_account:                
                        for account in GLOBAL_CACHE.ShMem.GetAllAccountData():
                            if account.AccountEmail != current_account:
                                
                                GLOBAL_CACHE.ShMem.SendMessage(
                                    current_account,
                                    account.AccountEmail,
                                    SharedCommandType.SkipCutscene,
                                    (0, 0, 0, 0),
                        )
                    
                else:
                    ImGui.begin_tooltip()
                    ImGui.text_colored(f"Ctrl + Click to skip cutscene on all accounts.", gray_color.color_tuple, 12)
                    ImGui.end_tooltip()                          

def draw_party_overlay(cached_data: CacheData, hero_windows : dict[str, WindowModule]):
    global party_member_frames
    
    main_account = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(Player.GetAccountEmail())
    if not main_account or not main_account.AgentPartyData.IsPartyLeader:
        return
    
    if party_throttle.IsExpired():
        party_throttle.Reset()
        party_member_frames = []
        if not Frame.party_list().exists:
            return

        for i in range(1, MAX_CHILD_FRAMES):
            member = Frame.party_member(i + 1)
            if not member.exists:
                continue

            party_member_frames.append(FramePosition(member))
            
        ## sort frames by Y
        party_member_frames.sort(key=lambda x: (x.position.top_on_screen, x.position.left_on_screen))  # Sort by Y, then X
    
    style = ImGui.get_style()
    texture = ThemeTextures.Hero_Panel_Toggle_Base.value.get_texture()
    
    if not party_member_frames:
        return
    
    for i, frame_info in enumerate(party_member_frames, start=1):      
        account = next((acc for acc in cached_data.party.accounts.values() if acc.AgentPartyData.PartyPosition == i - 1), None)
        
        if account and account.AccountEmail != Player.GetAccountEmail():
            if account.AgentPartyData.PartyID != main_account.AgentPartyData.PartyID or not SameMapOrPartyAsAccount(account):
                continue
            
            window_info = settings.get_hero_panel_info(account.AccountEmail)
            
            if window_info:        
                is_minimalus = style.Theme is StyleTheme.Minimalus  
                button_size = frame_info.position.bottom_on_screen - frame_info.position.top_on_screen + (0 if is_minimalus else -4)   
                button_rect = (
                    frame_info.position.right_on_screen - button_size + (0 if is_minimalus else 0), 
                    frame_info.position.bottom_on_screen - button_size + (-1 if is_minimalus else -2),
                    frame_info.position.right_on_screen,
                    frame_info.position.bottom_on_screen + (-3 if is_minimalus else 0)
                    )
                                            
                PyImGui.set_next_window_pos((frame_info.position.left_on_screen - 10, frame_info.position.top_on_screen - 10), PyImGui.ImGuiCond.Always)
                PyImGui.set_next_window_size((frame_info.position.right_on_screen - frame_info.position.left_on_screen + 20 , frame_info.position.bottom_on_screen - frame_info.position.top_on_screen +20), PyImGui.ImGuiCond.Always)
                flags = PyImGui.WindowFlags.NoTitleBar | PyImGui.WindowFlags.NoResize | PyImGui.WindowFlags.NoMove | PyImGui.WindowFlags.NoScrollbar | PyImGui.WindowFlags.NoSavedSettings | PyImGui.WindowFlags.NoFocusOnAppearing | PyImGui.WindowFlags.NoBackground
                
                if not ImGui.is_mouse_in_rect((*button_rect[:2], button_size, button_size)):
                    flags |= PyImGui.WindowFlags.NoMouseInputs
                    
                PyImGui.begin(f"##HeroAIPartyOverlay{i}", False, flags )
                
                draw_panel_toggle(i, account, button_rect, style, texture, window_info, is_minimalus, button_size)
                
                PyImGui.end()
                                    
            
    pass

def draw_panel_toggle(i, account : AccountStruct, button_rect : tuple[float, float, float, float], style : Style, texture : GameTexture, window_info : Settings.HeroPanelInfo | None, is_minimalus : bool, button_size : float, show_tooltip: bool = True):
    if not window_info:
        return
    
    bg_rect = (
                button_rect[0] + (2 if is_minimalus else 0),
                button_rect[1] + (2 if is_minimalus else 0),
                button_rect[2],
                button_rect[3] + (2 if is_minimalus else 0)
                )
                
    if is_minimalus:
        PyImGui.draw_list_add_rect_filled(
                        *bg_rect,
                        Color(0, 0, 0, 255).color_int,
                        style.FrameRounding.value1,
                        0
                        )
                
    hovered = ImGui.is_mouse_in_rect((*button_rect[:2], button_size, button_size))
    texture.draw_in_drawlist(
                    button_rect[:2],
                    (button_size, button_size),
                    state=TextureState.Active if window_info.open else TextureState.Normal,
                    tint=(255, 255, 255, 255) if hovered else (200, 200, 200, 255)
                    )
                
    text = str(i)
    text_size = PyImGui.calc_text_size(text)
                ## center align horizontally and vertically
    text_pos = (
                    button_rect[0] - 2 + (button_size - text_size[0]) / 2 + 2,
                    button_rect[1] + (button_size - text_size[1]) / 2 + 2
                    )
                
    PyImGui.draw_list_add_text(
                    text_pos[0],
                    text_pos[1],
                    style.Text.color_int,
                    text
                    )

    if hovered:
        if show_tooltip:
            ImGui.begin_tooltip()
            name = get_display_name(account)
            ImGui.text(f"{name}", 13)
            ImGui.text_colored(f"{account.AccountEmail if name == account.AgentData.CharacterName else f'{name.lower().replace(' ', '')}@mail.com'}", gray_color.color_tuple, 12)
            
            PyImGui.separator()
            ImGui.text_colored(f"Click to {"Hide" if window_info.open else "Show"} the hero panel", gray_color.color_tuple, 11)
            ImGui.end_tooltip()
        
        if PyImGui.is_mouse_clicked(0):  
            window_info.open = not window_info.open
            settings.save_settings()

show_accounts_in_party_search : bool = False
last_active_tab = None   # the tab handle last seen active
selected_account : str = ""

party_search : Optional[FramePosition] = None
player_tab : Optional[FramePosition] = None
hero_tab : Optional[FramePosition] = None
henchmen_tab : Optional[FramePosition] = None
active_tab : Optional[FramePosition] = None
active_tab_id : int = -1
is_player_tab : bool = True

def draw_tab_control(rect : tuple[float, float, float, float], label: str = "Accounts##PartySearchTab"):
    global show_accounts_in_party_search
    
    PyImGui.push_clip_rect(
        *rect,
        False
    )
    
    style = ImGui.get_style()
    #NON THEMED
    if style.Theme not in ImGui.Textured_Themes:
        ## Draw button/tab item frame and text
        
        pass
        
        
    #THEMED
        
    
    (ThemeTextures.Tab_Active if show_accounts_in_party_search else ThemeTextures.Tab_Inactive).value.get_texture().draw_in_drawlist(
        rect[:2],
        rect[2:],
    )

    display_label = ImGui.trim_text_to_width(label.split("##")[0], rect[2] - 2)        
    final_size = PyImGui.calc_text_size(display_label)
    final_w, final_h = final_size

    text_x = rect[0] + (rect[2] - final_w) / 2
    text_y = rect[1] + (rect[3] - final_h + (5 if show_accounts_in_party_search else 7)) / 2
    text_rect = (text_x, text_y, rect[2], rect[3])

    PyImGui.push_clip_rect(
        *text_rect,
        True
    )

    PyImGui.draw_list_add_text(
        text_x,
        text_y,
        style.Text.color_int,
        display_label,
    )

    PyImGui.pop_clip_rect()  
    
    if ImGui.is_mouse_in_rect(rect):
        if PyImGui.is_mouse_clicked(0):
            show_accounts_in_party_search = not show_accounts_in_party_search
            
    
    PyImGui.pop_clip_rect()
    return show_accounts_in_party_search

def draw_party_search_overlay(cached_data: CacheData):
    global show_accounts_in_party_search, last_active_tab, selected_account
    global party_search, player_tab, hero_tab, henchmen_tab, active_tab, is_player_tab
    
    if party_search_throttle.IsExpired():
        party_search_throttle.Reset()
            
        party_search_id = FrameTree.child_by_parent_hash(3199024334, [14])
        if not party_search_id.exists:
            party_search = None
            party_search_throttle.SetThrottleTime(500)
            return
        
        party_search = FramePosition(party_search_id)
        
        # The three tab children use runtime-only offsets.  They are deliberately
        # excluded from FrameId registry resolution, so walk them from the live
        # panel frame just as the legacy GetChildFrameID call did.
        players_tab_id = FrameTree.child_by_parent_hash(3199024334, [14, 0xFFFFFFFF])
        player_tab = FramePosition(players_tab_id)
            
        heroes_tab_id = FrameTree.child_by_parent_hash(3199024334, [14, 0xFFFFFFFE])
        hero_tab = FramePosition(heroes_tab_id)
        
        henchmen_tab_id = FrameTree.child_by_parent_hash(3199024334, [14, 0xFFFFFFFD])
        henchmen_tab = FramePosition(henchmen_tab_id)
            
        active_tab = next((tab for tab in [player_tab, hero_tab, henchmen_tab] if tab.position.content_top == max(
            player_tab.position.content_top,
            hero_tab.position.content_top,
            henchmen_tab.position.content_top
        )), player_tab)
        
        is_player_tab = (active_tab == player_tab)
               
    
    if not party_search or not player_tab or not hero_tab or not henchmen_tab or not active_tab:
        return
    
    party_search_throttle.SetThrottleTime(0)
    style = ImGui.get_style()
    style.WindowPadding.push_style_var(20, 20)
    style.HeaderHovered.push_color((200, 200, 200, 30))
    style.HeaderActive.push_color((200, 200, 200, 100))
    style.Header.push_color((200, 200, 200, 100))
    
    PyImGui.set_next_window_pos((party_search.position.left_on_screen, active_tab.position.bottom_on_screen + (8 if is_player_tab else 10)), PyImGui.ImGuiCond.Always)
    PyImGui.set_next_window_size((party_search.position.width_on_screen + 3, party_search.position.height_on_screen - (38 if is_player_tab else 40)), PyImGui.ImGuiCond.Always)
    flags = PyImGui.WindowFlags.NoTitleBar | PyImGui.WindowFlags.NoResize | PyImGui.WindowFlags.NoMove | PyImGui.WindowFlags.NoScrollbar | PyImGui.WindowFlags.NoSavedSettings | PyImGui.WindowFlags.NoFocusOnAppearing | PyImGui.WindowFlags.NoBackground
    
    if not show_accounts_in_party_search:
        flags |= PyImGui.WindowFlags.NoMouseInputs 
        
    open = PyImGui.begin("##PartySearchOverlay", show_accounts_in_party_search, flags)
    style.WindowPadding.pop_style_var()
    
    ImGui.push_font("Regular", 14)
    text_size = ImGui.calc_text_size("Accounts")
    
    tab_rect = (
        henchmen_tab.position.right_on_screen,
        henchmen_tab.position.top_on_screen + 2,
        text_size[0] + 25,
        (active_tab.position.height_on_screen) + (0 if show_accounts_in_party_search else -2)
    )
    
    if active_tab:
        if last_active_tab != active_tab.frame:
            show_accounts_in_party_search = False
            
        elif not ImGui.is_mouse_in_rect(tab_rect):
            if PyImGui.is_mouse_clicked(0):
                for tab in [player_tab, hero_tab, henchmen_tab]:
                    if tab and ImGui.is_mouse_in_rect((
                        tab.position.left_on_screen,
                        tab.position.top_on_screen,
                        tab.position.width_on_screen,
                        tab.position.height_on_screen
                    )):
                        active_tab_id = tab
                        show_accounts_in_party_search = False
                        break
            
        last_active_tab = active_tab.frame
    
    tab_open = draw_tab_control(tab_rect)
    
    
    ImGui.pop_font()
    
    if tab_open:
        PyImGui.draw_list_add_rect_filled(
            party_search.position.left_on_screen,
            party_search.position.top_on_screen,
            party_search.position.right_on_screen,
            party_search.position.bottom_on_screen,
            Color(0, 0, 0, 255).color_int,
            style.FrameRounding.value1,
            0,
        )
        
        sorted_by_profession = sorted(GLOBAL_CACHE.ShMem.GetAllAccountData(), key=lambda acc: (acc.AgentData.Profession[0], get_display_name(acc)), reverse=False)
        button_size  = 20
        texture = ThemeTextures.Hero_Panel_Toggle_Base.value.get_texture()
        mapid = Map.GetMapID()
        
        for i, account in enumerate(sorted_by_profession):
            window_info = settings.get_hero_panel_info(account.AccountEmail)
            
            if not window_info:
                continue
            
            name = get_display_name(account)
            prof_primary = ProfessionShort(
                account.AgentData.Profession[0]).name if account.AgentData.Profession[0] != 0 else ""
            prof_secondary = ProfessionShort(
                account.AgentData.Profession[1]).name if account.AgentData.Profession[1] != 0 else ""
            display_text = f"{prof_primary}{("/" if prof_secondary else "")}{prof_secondary}{account.AgentData.Level} {name} {f"[{Map.GetMapName(account.AgentData.Map.MapID)}]" if account.AgentData.Map.MapID != 0 and account.AgentData.Map.MapID != mapid else ''}"
            
            ImGui.dummy(button_size, button_size)
            draw_panel_toggle(
                i,
                account,
                (
                    PyImGui.get_item_rect_min()[0] - 2,
                    PyImGui.get_item_rect_min()[1] - 2,
                    PyImGui.get_item_rect_min()[0] + button_size,
                    PyImGui.get_item_rect_min()[1] + button_size
                ),
                style,
                texture,
                window_info,
                style.Theme is StyleTheme.Minimalus,
                button_size,
                # account.AccountEmail != cached_data.account_email
            )
            
            PyImGui.same_line(0, 5)            
            is_party_member = GLOBAL_CACHE.Party.IsPartyMember(account.AgentData.AgentID)
            selected = selected_account == account.AccountEmail
            
            if is_party_member:
                style.Text.push_color((200, 200, 200, 180))
            elif selected:
                style.Text.push_color((255, 238, 187, 255))
                
            
            _ = ImGui.selectable(f"{display_text}##PartySearchAccount_{account.AccountEmail}", selected_account == account.AccountEmail)
                        
            if is_party_member or selected:
                style.Text.pop_color()
            
            if account.AccountEmail != cached_data.account_email:
                ImGui.show_tooltip(f"Double Click to {'Kick from' if is_party_member else 'Invite to'} party\nSingle Click to select account for travel/invite")
                
            if PyImGui.is_item_clicked(0):
                if PyImGui.is_mouse_double_clicked(0):
                    sender_email = cached_data.account_email or ""
                        
                    if account.AccountEmail == sender_email:
                        continue
                    
                    same_map = Map.GetMapID() == account.AgentData.Map.MapID and Map.GetRegion()[0] == account.AgentData.Map.Region and Map.GetDistrict() == account.AgentData.Map.District and Map.GetLanguage()[0] == account.AgentData.Map.Language
                    
                    if same_map:
                        if not is_party_member:
                            # /invite needs the REAL name; name obfuscation may make the shared name an alias.
                            from Py4GWCoreLib.py4gwcorelib_src.system_settings.name_obfuscation.resolve import require_real_name
                            Player.SendChatCommand("invite " + require_real_name(account.AgentData.CharacterName))
                            GLOBAL_CACHE.ShMem.SendMessage(
                                sender_email,
                                account.AccountEmail,
                                SharedCommandType.InviteToParty,
                                (Player.GetAgentID(), 0, 0, 0)
                            )
                            
                        else:
                            Player.SendChatCommand("kick " +  account.AgentData.CharacterName)
                            
                    
                    else:
                        GLOBAL_CACHE.ShMem.SendMessage(
                            sender_email,
                            account.AccountEmail,
                            SharedCommandType.TravelToGuildHall if Map.IsGuildHall() else SharedCommandType.TravelToMap,
                            (
                                (0, 0, 0, 0)
                                if Map.IsGuildHall()
                                else (
                                    Map.GetMapID(),
                                    Map.GetRegion()[0],
                                    Map.GetDistrict(),
                                    Map.GetLanguage()[0],
                                )
                            ),
                        )
                    
                else:
                    selected_account = account.AccountEmail
        pass
    
    PyImGui.end()
    
    style.Header.pop_color()
    style.HeaderActive.pop_color()
    style.HeaderHovered.pop_color()
    
    pass


def draw_configure_window(module_name : str, configure_window : WindowModule):
    
    global module_info
    
    if not module_info:
        module_info = widget_handler.get_widget_info(module_name)
        
    configure_window.open = module_info.configuring if module_info else False
    
    if configure_window.begin():
        if ImGui.begin_tab_bar("##HeroAIConfigTabs"):
            if ImGui.begin_tab_item("General"):
                if ImGui.begin_child("##GeneralSettingsChild", (0, 0)):
                    show_party_panel_ui = ImGui.checkbox("Show Party Panel UI", settings.ShowPartyPanelUI)
                    if show_party_panel_ui != settings.ShowPartyPanelUI:
                        settings.ShowPartyPanelUI = show_party_panel_ui
                        settings.save_settings()
                        
                    show_control_panel_window = ImGui.checkbox("Show Control Panel Window", settings.ShowControlPanelWindow)
                    if show_control_panel_window != settings.ShowControlPanelWindow:
                        settings.ShowControlPanelWindow = show_control_panel_window
                        settings.save_settings()
                        
                    show_floating_targets = ImGui.checkbox("Show Floating Target Buttons", settings.ShowFloatingTargets)
                    if show_floating_targets != settings.ShowFloatingTargets:
                        settings.ShowFloatingTargets = show_floating_targets
                        settings.save_settings()

                    auto_call_targets = ImGui.checkbox("Auto Call Combat Targets", settings.AutoCallTargets)
                    if auto_call_targets != settings.AutoCallTargets:
                        settings.AutoCallTargets = auto_call_targets
                        settings.save_settings()

                    combat_range_modes = [
                        Settings.COMBAT_RANGE_MODE_PARTY_AGGRO,
                        Settings.COMBAT_RANGE_MODE_LEGACY,
                    ]
                    combat_range_labels = [Settings.COMBAT_RANGE_MODE_LABELS[mode] for mode in combat_range_modes]
                    current_combat_range_index = combat_range_modes.index(
                        Settings.normalize_combat_range_mode(settings.CombatRangeMode)
                    )
                    selected_combat_range_index = ImGui.combo(
                        "Combat range mode",
                        current_combat_range_index,
                        combat_range_labels,
                    )
                    if selected_combat_range_index != current_combat_range_index:
                        settings.CombatRangeMode = combat_range_modes[selected_combat_range_index]
                        settings.save_settings()
                    ImGui.show_tooltip("Party aggro uses leader/party-aware scan ranges. Legacy uses the old Earshot out-of-combat and Spellcast stay-alert behavior.")

                    show_command_panel = ImGui.checkbox("Show Global Config Panel", settings.ShowCommandPanel)
                    if show_command_panel != settings.ShowCommandPanel:
                        settings.ShowCommandPanel = show_command_panel
                        settings.save_settings()
                        
                    show_dialog_overlay = ImGui.checkbox("Show Dialog Overlay", settings.ShowDialogOverlay)
                    if show_dialog_overlay != settings.ShowDialogOverlay:
                        settings.ShowDialogOverlay = show_dialog_overlay
                        settings.save_settings()
                    ImGui.show_tooltip("Overlay buttons on NPC dialog with an invisible button for quick selection on all accounts by holding CTRL.\nOnly available to the party leader.\n\nThis is quite expensive due to UI queries, so only enable if needed.")
                        
                ImGui.end_child()
                ImGui.end_tab_item()
                
            if ImGui.begin_tab_item("Hero Panels"):      
                if ImGui.begin_child("##HeroPanelSettingsChild", (0, 0)):   
                    show_hero_panels = ImGui.checkbox("Show Hero Panels", settings.ShowHeroPanels)
                    if show_hero_panels != settings.ShowHeroPanels:
                        settings.ShowHeroPanels = show_hero_panels
                        settings.save_settings()
                                       
                    show_party_overlay = ImGui.checkbox("Show Party Overlay", settings.ShowPartyOverlay)
                    if show_party_overlay != settings.ShowPartyOverlay:
                        settings.ShowPartyOverlay = show_party_overlay
                        settings.save_settings()
                                       
                    show_party_search_overlay = ImGui.checkbox("Show Party Search Overlay", settings.ShowPartySearchOverlay)
                    if show_party_search_overlay != settings.ShowPartySearchOverlay:
                        settings.ShowPartySearchOverlay = show_party_search_overlay
                        settings.save_settings()
                                       
                    show_on_leader = ImGui.checkbox("Show only on Leader", settings.ShowPanelOnlyOnLeaderAccount)
                    if show_on_leader != settings.ShowPanelOnlyOnLeaderAccount:
                        settings.ShowPanelOnlyOnLeaderAccount = show_on_leader
                        settings.save_settings()
                    
                    show_leader_panel = ImGui.checkbox("Show Leader's Panel", settings.ShowLeaderPanel)
                    if show_leader_panel != settings.ShowLeaderPanel:
                        settings.ShowLeaderPanel = show_leader_panel
                        settings.save_settings()
                    
                    combine_panels = ImGui.checkbox("Combine Hero Panels", settings.CombinePanels)
                    if combine_panels != settings.CombinePanels:
                        settings.CombinePanels = combine_panels
                        settings.save_settings()
                        
                    anonymous_panel_names = ImGui.checkbox("Anonymous Panel Names", settings.Anonymous_PanelNames)
                    if anonymous_panel_names != settings.Anonymous_PanelNames:
                        settings.Anonymous_PanelNames = anonymous_panel_names
                        settings.save_settings()
                        
                    show_hero_buttons = ImGui.checkbox("Show Hero Buttons", settings.ShowHeroButtons)
                    if show_hero_buttons != settings.ShowHeroButtons:
                        settings.ShowHeroButtons = show_hero_buttons
                        settings.save_settings()
                        
                    show_hero_bars = ImGui.checkbox("Show Health and Energy", settings.ShowHeroBars)
                    if show_hero_bars != settings.ShowHeroBars:
                        settings.ShowHeroBars = show_hero_bars
                        settings.save_settings()
                            
                    show_hero_skills = ImGui.checkbox("Show Hero Skills", settings.ShowHeroSkills)
                    if show_hero_skills != settings.ShowHeroSkills:
                        settings.ShowHeroSkills = show_hero_skills
                        settings.save_settings()
                        
                    show_hero_upkeeps = ImGui.checkbox("Show Hero Upkeeps", settings.ShowHeroUpkeeps)
                    if show_hero_upkeeps != settings.ShowHeroUpkeeps:
                        settings.ShowHeroUpkeeps = show_hero_upkeeps
                        settings.save_settings()
                        
                    show_hero_effects = ImGui.checkbox("Show Hero Effects", settings.ShowHeroEffects)
                    if show_hero_effects != settings.ShowHeroEffects:
                        settings.ShowHeroEffects = show_hero_effects
                        settings.save_settings()
                        
                    max_effect_rows = ImGui.slider_int("Max Effect Rows", settings.MaxEffectRows, 1, 10)
                    if max_effect_rows != settings.MaxEffectRows and max_effect_rows >= 1 and max_effect_rows <= 10:
                        settings.MaxEffectRows = max_effect_rows
                        settings.save_settings()
                        
                    radio_value = 0 if not settings.ShowEffectDurations and not settings.ShowShortEffectDurations else (1 if settings.ShowShortEffectDurations else 2)

                    radio_value = ImGui.radio_button("Show no durations", radio_value, 0)
                    radio_value = ImGui.radio_button("Show short durations", radio_value, 1)
                    radio_value = ImGui.radio_button("Show all durations", radio_value, 2)

                    if radio_value == 0:
                        if settings.ShowEffectDurations or settings.ShowShortEffectDurations:
                            settings.ShowEffectDurations = False
                            settings.ShowShortEffectDurations = False
                            settings.save_settings()

                    elif radio_value == 1:
                        if settings.ShowEffectDurations or not settings.ShowShortEffectDurations:
                            settings.ShowEffectDurations = False
                            settings.ShowShortEffectDurations = True
                            settings.save_settings()

                    elif radio_value == 2:
                        if not settings.ShowEffectDurations or settings.ShowShortEffectDurations:
                            settings.ShowEffectDurations = True
                            settings.ShowShortEffectDurations = False
                            settings.save_settings()
            
                ImGui.end_child()
                ImGui.end_tab_item()                
                    
            if ImGui.begin_tab_item("Hotbars"):
                if ImGui.begin_child("##HotbarSettingsChild", (0, 0)):
                    PyImGui.text("Command Hotbars are deprecated.")
                    PyImGui.spacing()
                    PyImGui.text_wrapped(
                        "HeroAI hotbars have moved to the Launch Bar, which already offers a "
                        "configurable grid of buttons that run these same commands. Open the Launch "
                        "Bar editor and add commands from the \"HeroAI\" group in the function picker."
                    )
                    PyImGui.spacing()
                    PyImGui.separator()
                    PyImGui.spacing()

                    if settings.CommandHotBars:
                        PyImGui.text(f"You have {len(settings.CommandHotBars)} saved hotbar(s).")
                        PyImGui.spacing()
                        if ImGui.button("Import to Launch Bar", 220):
                            from .command_api import HeroAICommandAPI
                            HeroAICommandAPI().import_hotbars_to_launch_bar()
                        ImGui.show_tooltip("Recreate each saved hotbar as a Launch Bar, one tile per assigned command.")
                    else:
                        PyImGui.text_disabled("No saved hotbars to import.")
                ImGui.end_child()
                ImGui.end_tab_item()
            
            if ImGui.begin_tab_item("Blacklist"):
                if ImGui.begin_child("##BlacklistSettingsChild", (0, 0)):
                    draw_blacklist_ui()
                ImGui.end_child()
                ImGui.end_tab_item()

            if ImGui.begin_tab_item("Resurrection Scroll"):
                resurrection_scroll.draw_settings()
                ImGui.end_tab_item()

            if ImGui.begin_tab_item("Debug"):
                if ImGui.begin_child("##DebugSettingsChild", (0, 0)):
                    show_debug = ImGui.checkbox("Show Debug Window", settings.ShowDebugWindow)
                    if show_debug != settings.ShowDebugWindow:
                        settings.ShowDebugWindow = show_debug
                        settings.save_settings()
                        
                    print_debug = ImGui.checkbox("Print Debug Messages", settings.PrintDebug)
                    if print_debug != settings.PrintDebug:
                        settings.PrintDebug = print_debug
                        settings.save_settings()
                        
                ImGui.end_child()
                ImGui.end_tab_item()
                
            ImGui.end_tab_bar()
            
                
                            
    
    configure_window.end()  
    
    if not configure_window.open:
        wh = get_widget_handler()
        wh.set_widget_configuring(module_name, False)
          
    pass
