"""Read-only parity probe for HeroAI's Show Party Panel UI frames.

Press the button once on each client.  The widget logs the legacy native
lookups beside the migrated FrameTree handles, without drawing or modifying a
Guild Wars frame.
"""

from __future__ import annotations

import PyImGui
import PySystem
import PyUIManager

from Py4GWCoreLib import GLOBAL_CACHE, Map, Player, Utils
from Py4GWCoreLib.FrameTree import Frame, FrameId, FrameTree

MODULE_NAME = "Party Search Frame Diagnostics"
MODULE_ICON = "Assets/Textures/Module_Icons/Debug.png"

PARTY_SEARCH_WINDOW_HASH = 3199024334
PARTY_SEARCH_PANEL_OFFSETS = [14]
PLAYERS_TAB_OFFSETS = [14, 0xFFFFFFFF]
HEROES_TAB_OFFSETS = [14, 0xFFFFFFFE]
HENCHMEN_TAB_OFFSETS = [14, 0xFFFFFFFD]

_report: list[str] = ["Press Run diagnostics to log the native and FrameTree results."]
_draw_outlines = False


def _safe_int(getter) -> int:
    try:
        return int(getter() or 0)
    except Exception:
        return 0


def _frame_summary(label: str, frame: Frame, native_id: int) -> str:
    resolved_id = _safe_int(lambda: frame.frame_id)
    try:
        exists = frame.exists
        created = frame.is_created
        visible = frame.is_visible
        usable = frame.is_usable
        coords = frame.coords()
    except Exception as error:
        return f"{label}: native={native_id} frame-error={type(error).__name__}: {error}"

    return (
        f"{label}: native={native_id} resolved={resolved_id} "
        f"match={native_id == resolved_id} exists={exists} created={created} "
        f"visible={visible} usable={usable} coords={coords} "
        f"snapshot-known={FrameTree.known(native_id) if native_id else False}"
    )


def _raw_summary(label: str, frame_id: int) -> str:
    if not frame_id:
        return f"{label}: native id=0"

    try:
        raw = PyUIManager.UIFrame(frame_id)
        position = raw.position
        coords = (
            int(position.left_on_screen),
            int(position.top_on_screen),
            int(position.right_on_screen),
            int(position.bottom_on_screen),
        )
        return (
            f"{label} raw: id={frame_id} created={bool(raw.is_created)} "
            f"visible={bool(raw.is_visible)} coords={coords} "
            f"hash={int(raw.frame_hash or 0)} code={int(raw.child_offset_id or 0)}"
        )
    except Exception as error:
        return f"{label} raw: id={frame_id} error={type(error).__name__}: {error}"


def _heroai_runtime_summary() -> list[str]:
    """Read the loaded HeroAI widget's state without changing it."""
    try:
        from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import get_widget_handler

        widget = next(
            (
                candidate
                for candidate in get_widget_handler().widgets.values()
                if candidate.folder_script_name.replace("\\", "/").endswith("/HeroAI.py")
            ),
            None,
        )
        if widget is None:
            return ["HeroAI widget: not discovered by WidgetManager"]

        from Py4GWCoreLib.HeroAI.windows import HeroAI_FloatingWindows

        module = widget.module
        cached_data = getattr(module, "cached_data", None)
        show_party_search_overlay = HeroAI_FloatingWindows.settings.ShowPartySearchOverlay
        selected_tab = HeroAI_FloatingWindows.selected_tab.name
        party_slot = GLOBAL_CACHE.Party.GetOwnPartyNumber()

        lines = [
            (
                f"HeroAI widget: enabled={widget.enabled} paused={widget.is_paused} "
                f"module-loaded={module is not None}"
            ),
            (
                f"HeroAI state: show-party-search-overlay={show_party_search_overlay} "
                f"selected-tab={selected_tab} "
                f"party-slot={party_slot}"
            ),
        ]

        lines.append(
            "Expected feature path: draw_party_search_overlay -> "
            f"{'draw attempt' if show_party_search_overlay else 'skipped at ShowPartySearchOverlay gate'}"
        )
        return lines
    except Exception as error:
        return [f"HeroAI runtime state: error={type(error).__name__}: {error}"]


def _build_report() -> list[str]:
    FrameTree.ensure()

    native_root = _safe_int(
        lambda: PyUIManager.UIManager.get_frame_id_by_hash(PARTY_SEARCH_WINDOW_HASH)
    )
    native_panel = _safe_int(
        lambda: PyUIManager.UIManager.get_child_frame_id(
            PARTY_SEARCH_WINDOW_HASH, PARTY_SEARCH_PANEL_OFFSETS
        )
    )
    native_players_tab = _safe_int(
        lambda: PyUIManager.UIManager.get_child_frame_id(
            PARTY_SEARCH_WINDOW_HASH, PLAYERS_TAB_OFFSETS
        )
    )
    native_heroes_tab = _safe_int(
        lambda: PyUIManager.UIManager.get_child_frame_id(
            PARTY_SEARCH_WINDOW_HASH, HEROES_TAB_OFFSETS
        )
    )
    native_henchmen_tab = _safe_int(
        lambda: PyUIManager.UIManager.get_child_frame_id(
            PARTY_SEARCH_WINDOW_HASH, HENCHMEN_TAB_OFFSETS
        )
    )

    registry_root = Frame(FrameId.PartySearchWindow)
    registry_panel = Frame(FrameId.PartySearchWindow.Panel)

    direct_root = FrameTree.by_hash(PARTY_SEARCH_WINDOW_HASH)
    direct_panel = FrameTree.child_by_parent_hash(
        PARTY_SEARCH_WINDOW_HASH, PARTY_SEARCH_PANEL_OFFSETS
    )
    direct_players_tab = FrameTree.child_by_parent_hash(
        PARTY_SEARCH_WINDOW_HASH, PLAYERS_TAB_OFFSETS
    )
    direct_heroes_tab = FrameTree.child_by_parent_hash(
        PARTY_SEARCH_WINDOW_HASH, HEROES_TAB_OFFSETS
    )
    direct_henchmen_tab = FrameTree.child_by_parent_hash(
        PARTY_SEARCH_WINDOW_HASH, HENCHMEN_TAB_OFFSETS
    )

    return [
        "=== Party Panel Frame Diagnostics ===",
        (
            f"account={Player.GetAccountEmail()!r} party-slot="
            f"{GLOBAL_CACHE.Party.GetOwnPartyNumber()} map-ready={Map.IsMapReady()} "
            f"outpost={Map.IsOutpost()} explorable={Map.IsExplorable()}"
        ),
        f"party-search-hash={PARTY_SEARCH_WINDOW_HASH} panel-path={PARTY_SEARCH_PANEL_OFFSETS}",
        _raw_summary("root", native_root),
        _raw_summary("panel", native_panel),
        _raw_summary("players-tab", native_players_tab),
        _raw_summary("heroes-tab", native_heroes_tab),
        _raw_summary("henchmen-tab", native_henchmen_tab),
        _frame_summary("registry root", registry_root, native_root),
        _frame_summary("registry panel", registry_panel, native_panel),
        _frame_summary("direct root", direct_root, native_root),
        _frame_summary("direct panel", direct_panel, native_panel),
        _frame_summary("direct players-tab", direct_players_tab, native_players_tab),
        _frame_summary("direct heroes-tab", direct_heroes_tab, native_heroes_tab),
        _frame_summary("direct henchmen-tab", direct_henchmen_tab, native_henchmen_tab),
        *_heroai_runtime_summary(),
        "=== End Party Panel Frame Diagnostics ===",
    ]


def _run_diagnostics() -> None:
    global _report
    _report = _build_report()
    for line in _report:
        PySystem.Console.Log(MODULE_NAME, line, PySystem.Console.MessageType.Info)


def _draw_party_frame_outlines() -> None:
    """Draw the exact frames the party-panel feature uses; no game-frame writes."""
    root = FrameTree.by_hash(PARTY_SEARCH_WINDOW_HASH)
    panel = FrameTree.child_by_parent_hash(
        PARTY_SEARCH_WINDOW_HASH, PARTY_SEARCH_PANEL_OFFSETS
    )
    root.draw_outline(Utils.RGBToColor(0, 255, 255, 255), 2.0)
    panel.draw_outline(Utils.RGBToColor(0, 255, 0, 255), 3.0)


def main() -> None:
    global _draw_outlines

    PyImGui.set_next_window_size((760, 360), PyImGui.ImGuiCond.FirstUseEver)
    if PyImGui.begin(MODULE_NAME, True):
        PyImGui.text("Read-only probe. It does not draw or modify any game frame.")
        PyImGui.text("Run it once on each multibox client, then copy each console block.")
        if PyImGui.button("Run native frame diagnostics"):
            _run_diagnostics()
        _draw_outlines = PyImGui.checkbox(
            "Draw Party Search outlines (cyan=root, green=panel anchor)",
            _draw_outlines,
        )
        PyImGui.separator()
        for line in _report:
            PyImGui.text_wrapped(line)
    PyImGui.end()

    if _draw_outlines:
        _draw_party_frame_outlines()


if __name__ == "__main__":
    main()
