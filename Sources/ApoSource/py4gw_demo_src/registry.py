"""
Grouped view registry for Py4GW DEMO 2.0 (reengineered).

Every non-PyImGui binding module has an EXPLICIT, hand-wired section (no reflection). Each Section
maps a display name to a zero-arg draw callable that renders INTO the host child region (no own
begin/end window) — the uniform panel shape. Sections build cast Blocks, render them, expose action
triggers, and offer a per-section "Dump to file" button (see diagnostics.py).

Add a new module's view here to make it appear in the sidebar.
"""

import os

import PyImGui

from Py4GWCoreLib import ImGui

from . import ui

# World & Map (kept-good originals)
from . import map_demo
from . import agent_demo
from . import agentarray_demo
from .pathing_map_demo import renderer as _pathing_renderer

# Player / Party / Social
from . import player_demo
from . import party_demo
from . import guild_demo
from . import friendlist_demo
from . import chat_demo

# Items & Inventory
from . import inventory_demo
from . import item_demo

# Combat & Skills
from . import skill_demo
from . import skillbar_demo
from . import effect_demo

# Trading & NPC
from . import merchant_demo
from . import trade_demo
from . import dialog_demo
from . import quest_demo

# Agents cosmetics
from . import agentrecolor_demo
from . import nameobfuscator_demo

# Rendering & Camera
from . import overlay_demo
from . import dxoverlay_demo
from . import textures_demo
from . import render_demo
from . import camera_demo

# UI & Frames
from . import uimanager_demo
from . import preferences_demo

# Input
from . import keystroke_demo
from . import mouse_demo

# Core / System
from . import system_demo
from . import gamethread_demo
from . import py4gwcore_demo
from . import scanner_demo
from . import callback_demo
from . import listeners_demo
from . import profiler_demo
from . import settings_demo
from . import ping_demo
from . import packet_demo
from . import combatevents_demo

# Contexts
from . import contexts_demo


class Section:
    __slots__ = ("name", "draw")

    def __init__(self, name: str, draw):
        self.name = name
        self.draw = draw


# Ordered groups -> sections.
GROUPS: "list[tuple[str, list[Section]]]" = [
    ("Core / System", [
        Section("System (PySystem)", system_demo.draw_system_view),
        Section("Game Thread", gamethread_demo.draw_gamethread_view),
        Section("Py4GW / SharedMemory", py4gwcore_demo.draw_py4gwcore_view),
        Section("Scanner", scanner_demo.draw_scanner_view),
        Section("Callbacks", callback_demo.draw_callback_view),
        Section("Listeners", listeners_demo.draw_listeners_view),
        Section("Profiler", profiler_demo.draw_profiler_view),
        Section("Settings", settings_demo.draw_settings_view),
        Section("Ping / Latency", ping_demo.draw_ping_view),
        Section("Packet Sniffer", packet_demo.draw_packet_view),
        Section("Combat Events", combatevents_demo.draw_combatevents_view),
    ]),
    ("World & Map", [
        Section("Map", map_demo.draw_map_data),
        Section("Mission Map", map_demo.draw_mission_map_tab),
        Section("Mini Map", map_demo.draw_mini_map_tab),
        Section("World Map", map_demo.draw_world_map_tab),
        Section("Pregame", map_demo.draw_pregame_tab),
        Section("Geo & Pathing", _pathing_renderer.Draw_PathingMap_Window),
    ]),
    ("Contexts", [
        Section("Native Contexts", contexts_demo.draw_contexts_view),
    ]),
    ("Agents", [
        Section("Agent Array", agentarray_demo.draw_agent_array_data),
        Section("Agents", agent_demo.draw_agents_view),
        Section("Agent Recolor", agentrecolor_demo.draw_agentrecolor_view),
        Section("Name Obfuscator", nameobfuscator_demo.draw_nameobfuscator_view),
    ]),
    ("Player", [
        Section("Player", player_demo.draw_player_view),
    ]),
    ("Party & Social", [
        Section("Party", party_demo.draw_party_view),
        Section("Guild", guild_demo.draw_guild_view),
        Section("Friend List", friendlist_demo.draw_friendlist_view),
        Section("Chat", chat_demo.draw_chat_view),
    ]),
    ("Items & Inventory", [
        Section("Inventory", inventory_demo.draw_inventory_view),
        Section("Item", item_demo.draw_item_view),
    ]),
    ("Combat & Skills", [
        Section("Skill", skill_demo.draw_skill_view),
        Section("Skillbar", skillbar_demo.draw_skillbar_view),
        Section("Effects / Buffs", effect_demo.draw_effects_view),
    ]),
    ("Trading & NPC", [
        Section("Merchant / Trading", merchant_demo.draw_merchant_view),
        Section("Trade P2P", trade_demo.draw_trade_view),
        Section("Dialog", dialog_demo.draw_dialog_view),
        Section("Quest", quest_demo.draw_quest_view),
    ]),
    ("UI & Frames", [
        Section("UIManager / Frames", uimanager_demo.draw_uimanager_view),
        Section("Preferences", preferences_demo.draw_preferences_view),
    ]),
    ("Input", [
        Section("Keystroke", keystroke_demo.draw_keystroke_view),
        Section("Mouse", mouse_demo.draw_mouse_view),
    ]),
    ("Rendering & Camera", [
        Section("Overlay", overlay_demo.draw_overlay_view),
        Section("DXOverlay", dxoverlay_demo.draw_dxoverlay_view),
        Section("Textures", textures_demo.draw_textures_view),
        Section("Render", render_demo.draw_render_view),
        Section("Camera", camera_demo.draw_camera_view),
    ]),
]

# The reusable sidebar/content window, built from the GROUPS registry above.
# Nav, selection, per-panel error isolation, content tabs and markdown help are
# all handled by ImGui.SidebarWindow; this module only supplies the topic data.
_HELP_DIR = os.path.join(os.path.dirname(__file__), "help")

_WINDOW = ImGui.SidebarWindow(
    "Py4GW DEMO 2.0",
    sidebar_width=250.0,
    content_width=760.0,
    height=720.0,
    selected="Map",
    help_dir=_HELP_DIR,
    show_search=True,
)

_about_cache: str = ""


def _draw_about() -> None:
    """Render the About/help markdown as rich text (demonstrates help files)."""
    global _about_cache
    if not _about_cache:
        try:
            with open(os.path.join(_HELP_DIR, "about.md"), "r", encoding="utf-8") as fh:
                _about_cache = fh.read()
        except Exception:
            _about_cache = "# Py4GW DEMO 2.0\n\nHelp file `help/about.md` not found."
    ImGui.SidebarWindow.render_markdown(_about_cache)


# A "Guide" group with a rich-text (markdown) topic, demonstrating help files.
_WINDOW.add_topic(_WINDOW.add_group("Guide"), ImGui.SidebarWindow.Topic("About", draw=_draw_about))

# Every hand-wired Section becomes a Topic in its group.
for _group_name, _sections in GROUPS:
    _grp = _WINDOW.add_group(_group_name)
    for _section in _sections:
        _WINDOW.add_topic(_grp, ImGui.SidebarWindow.Topic(_section.name, draw=_section.draw))

# Keep "Map" as the initial selection (add_topic set it to "About" first).
_WINDOW.select("Map")


def get_window() -> "ImGui.SidebarWindow":
    return _WINDOW


def get_selected() -> str:
    return _WINDOW.selected or ""


def draw_sidebar() -> None:
    """Back-compat: render just the nav column (caller owns the child region)."""
    _WINDOW.draw_sidebar()


def draw_content() -> None:
    """Back-compat: render just the selected section (caller owns the child region)."""
    _WINDOW.draw_content()
