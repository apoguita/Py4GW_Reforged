"""
Grouped view registry for Py4GW DEMO 2.0 (reengineered).

Every non-PyImGui binding module has an EXPLICIT, hand-wired section (no reflection). Each Section
maps a display name to a zero-arg draw callable that renders INTO the host child region (no own
begin/end window) — the uniform panel shape. Sections build cast Blocks, render them, expose action
triggers, and offer a per-section "Dump to file" button (see diagnostics.py).

Add a new module's view here to make it appear in the sidebar.
"""

import PyImGui

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

# Flat name -> Section for dispatch.
_SECTIONS: "dict[str, Section]" = {
    s.name: s for _, sections in GROUPS for s in sections
}

_selected: str = "Map"


def get_selected() -> str:
    return _selected


def draw_sidebar() -> None:
    """Render the grouped, selectable navigation column (caller owns the child region)."""
    global _selected
    for group_name, sections in GROUPS:
        ui.text_muted(group_name)
        PyImGui.separator()
        PyImGui.indent(12.0)
        for section in sections:
            if PyImGui.selectable(
                section.name,
                _selected == section.name,
                PyImGui.SelectableFlags.NoFlag,
                (0.0, 0.0),
            ):
                _selected = section.name
        PyImGui.unindent(12.0)
        PyImGui.spacing()


def draw_content() -> None:
    """Render the currently-selected section (caller owns the child region)."""
    section = _SECTIONS.get(_selected)
    if section is None:
        ui.not_available(f"unknown section '{_selected}'")
        return
    try:
        section.draw()
    except Exception as e:  # noqa: BLE001 - keep the widget alive if one panel throws
        PyImGui.text_colored(f"Panel error in '{_selected}':", ui.ERR_COLOR)
        PyImGui.text_colored(f"{type(e).__name__}: {e}", ui.ERR_COLOR)
