"""
UIManager / Frames section — the underlying UI-integration system (not a visual ImGui panel).

R4 flagged the old version as a total rewrite: PyUIManager (156 methods) had been reduced to two
blank reflection grids. This rebuilds it explicitly around a subject frame_id: a frame inspector,
tree navigation, global UI state, encoded-string tools, the frame/message logs, and the mutating
actions (visibility/opacity/layer/click/message-send/FPS) as explicit trigger buttons.

Data path: the ``UIManager`` wrapper (static methods over PyUIManager). The preference API
(Get/SetEnum/Int/String/Bool + keymap) is covered by the dedicated Preferences section; the bag/
storage/salvage window helper namespaces are exercised from the Inventory section.

R2 coverage — frame tree/inspect/message/encode/state/log methods wired explicitly below.
"""

import PyImGui

from Py4GWCoreLib.UIManager import UIManager

from . import casts
from . import diagnostics
from . import ui

_SECTION = "UIManager"


class _State:
    frame_id: int = 0
    msg_id: int = 0
    wparam: int = 0
    lparam: int = 0
    opacity: float = 1.0
    layer: int = 0
    fps_limit: int = 0
    enc_text: str = ""


state = _State()

# Opt-in snapshots. Walking the frame tree (children) and the log arrays every frame calls native
# getters on many transient frame ids; as the game UI mutates, a walked id goes stale and the native
# getter dereferences freed memory -> uncatchable access violation (client crash "some time after
# opening"). So the tree walk + logs are captured only on an explicit button click and cached here.
# Opt-in snapshot. EVERY frame-id getter (inspector, tree walk, logs, richer globals) runs only on an
# explicit button click — never per-frame. A single native frame getter on an edge/stale id can hard-
# crash the client with an access violation that Python try/except (casts.safe) CANNOT catch, which is
# why selecting the tab crashed. On select we render only a tiny always-safe subset (getters other
# widgets already call every frame); the rest lives here until the user clicks "Read Frame Data".
_snapshot_blocks: "list" = []


# ---------------------------------------------------------------------------
# build_* blocks
# ---------------------------------------------------------------------------
def _safe_globals_block():
    # Only getters that are already called safely every frame elsewhere in the library.
    rows = [
        ("Root Frame ID", casts.safe(UIManager.GetRootFrameID)),
        ("Text Language", casts.safe(UIManager.GetTextLanguage)),
        ("UI Drawn", casts.yesno(casts.safe(UIManager.IsUIDrawn))),
        ("FPS Limit", casts.safe(UIManager.GetFPSLimit)),
    ]
    return ui.kv_block("Global UI State (live-safe subset — click 'Read Frame Data' for the rest)", rows)


def _full_globals_block():
    rows = [
        ("Root Frame ID", casts.safe(UIManager.GetRootFrameID)),
        ("Text Language", casts.safe(UIManager.GetTextLanguage)),
        ("UI Drawn", casts.yesno(casts.safe(UIManager.IsUIDrawn))),
        ("World Map Showing", casts.yesno(casts.safe(UIManager.IsWorldMapShowing))),
        ("Shift Screenshot", casts.yesno(casts.safe(UIManager.IsShiftScreenshot))),
        ("NPC Dialog Visible", casts.yesno(casts.safe(UIManager.IsNPCDialogVisible))),
        ("Locked Chest Visible", casts.yesno(casts.safe(UIManager.IsLockedChestWindowVisible))),
        ("FPS Limit", casts.safe(UIManager.GetFPSLimit)),
        ("Current Tooltip Address", casts.ptr(casts.safe(UIManager.GetCurrentTooltipAddress, default=0))),
    ]
    return ui.kv_block("Global UI State", rows)


def _inspector_block(fid):
    rows = [
        ("Frame ID", fid),
        ("Exists", casts.yesno(casts.safe(UIManager.FrameExists, fid))),
        ("Is Frame Created", casts.yesno(casts.safe(UIManager.IsFrameCreated, fid))),
        ("Is Visible", casts.yesno(casts.safe(UIManager.IsVisible, fid))),
        ("Is Mouse Over", casts.yesno(casts.safe(UIManager.IsMouseOver, fid))),
        ("Label", casts.safe(UIManager.GetFrameLabel, fid)),
        ("Title Text", casts.safe(UIManager.GetFrameTitleText, fid)),
        ("Text Label (decoded)", casts.safe(UIManager.GetTextLabelDecoded, fid)),
        ("Text Label (encoded)", casts.safe(UIManager.GetTextLabelEncoded, fid)),
        ("Frame Context", casts.ptr(casts.safe(UIManager.GetFrameContext, fid, default=0))),
        ("Name Hash", casts.flags(casts.safe(UIManager.GetFrameNameHash, fid, default=0))),
        ("Frame Code", casts.flags(casts.safe(UIManager.GetFrameCode, fid, default=0))),
        ("Layer", casts.safe(UIManager.GetFrameLayer, fid)),
        ("Opacity", casts.f2(casts.safe(UIManager.GetOpacity, fid, default=0.0))),
        ("User Param", casts.safe(UIManager.GetUserParam, fid)),
        ("Coords (L,T,R,B)", str(casts.safe(UIManager.GetFrameCoords, fid))),
        ("Content Coords", str(casts.safe(UIManager.GetContentFrameCoords, fid))),
        ("Position Ex", str(casts.safe(UIManager.GetFramePositionEx, fid))),
        ("Native Size", str(casts.safe(UIManager.GetFrameNativeSize, fid))),
        ("Min Size", str(casts.safe(UIManager.GetFrameMinSize, fid))),
        ("Client Border", str(casts.safe(UIManager.GetFrameClientBorder, fid))),
        ("Clip Rect", str(casts.safe(UIManager.GetFrameClipRect, fid))),
        ("Viewport Scale", str(casts.safe(UIManager.GetViewPortScale, fid))),
        ("Viewport Dimensions", str(casts.safe(UIManager.GetViewportDimensions, fid))),
        ("Frame Path", casts.safe(UIManager.ConstructFramePath, fid)),
    ]
    return ui.kv_block(f"Frame Inspector (frame {fid})", rows)


def _tree_children_block(fid):
    tree_rows = [
        ("Parent Frame ID", casts.safe(UIManager.GetParentFrameID, fid)),
        ("Parent ID (direct)", casts.safe(UIManager.GetParentFrameIdDirect, fid)),
        ("First Child", casts.safe(UIManager.GetFirstChildFrameID, fid)),
        ("Last Child", casts.safe(UIManager.GetLastChildFrameID, fid)),
        ("Next Sibling", casts.safe(UIManager.GetNextChildFrameID, fid)),
        ("Prev Sibling", casts.safe(UIManager.GetPrevChildFrameID, fid)),
    ]
    child_rows = []
    child = casts.safe(UIManager.GetFirstChildFrameID, fid, default=0)
    guard = 0
    while child and guard < 128:
        child_rows.append((
            child,
            casts.safe(UIManager.GetFrameLabel, child),
            casts.yesno(casts.safe(UIManager.IsVisible, child)),
            str(casts.safe(UIManager.GetFrameCoords, child)),
        ))
        nxt = casts.safe(UIManager.GetNextChildFrameID, child, default=0)
        if nxt == child:
            break
        child = nxt
        guard += 1
    return [
        ui.kv_block(f"Tree Navigation (frame {fid})", tree_rows),
        ui.multi_block(f"Children ({len(child_rows)})", ["Frame ID", "Label", "Visible", "Coords"], child_rows),
    ]


def _logs_blocks():
    frame_logs = casts.safe(UIManager.GetFrameLogs, default=[]) or []
    msg_logs = casts.safe(UIManager.GetUIMessageLogs, default=[]) or []
    frows = [tuple(str(c) for c in entry) for entry in frame_logs[-60:]]
    mrows = [tuple(str(c) for c in entry) for entry in msg_logs[-60:]]
    return [
        ui.kv_block("Logs", [("Frame Logs (rows)", len(frows)), ("UI Message Logs (rows)", len(mrows))]),
        ui.multi_block("Frame Logs (last 60)", ["A", "B", "C"], frows),
        ui.multi_block("UI Message Logs (last 60)", ["msgid", "type", "b1", "b2", "n", "wparams", "lparams"], mrows),
    ]


def snapshot_all():
    """Opt-in: read ALL frame-id getters once (full globals + inspector + tree + logs). Click-only."""
    global _snapshot_blocks
    fid = state.frame_id or casts.safe(UIManager.GetRootFrameID, default=0)
    blocks = [_full_globals_block(), _inspector_block(fid)]
    blocks.extend(_tree_children_block(fid))
    blocks.extend(_logs_blocks())
    _snapshot_blocks = blocks


def build_uimanager():
    # Live path calls ONLY the safe global subset — every frame-id getter is deferred to snapshot_all().
    return [_safe_globals_block()] + list(_snapshot_blocks)


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Subject Frame")
    state.frame_id = PyImGui.input_int("Frame ID (0 = root)", state.frame_id)
    if PyImGui.button("Load Root"):
        state.frame_id = casts.safe(UIManager.GetRootFrameID, default=0)
    PyImGui.same_line(0, 8)
    if PyImGui.button("Read Frame Data (inspector + tree + logs)"):
        snapshot_all()
    ui.text_muted("All frame-id getters run on click only — calling them every frame can hard-crash the client (uncatchable).")

    PyImGui.spacing()
    ui.section_header("Frame Mutators (act on Subject Frame)")
    ui.action_button("Set Visible (on)", UIManager.SetVisible, state.frame_id, True, key="vis_on")
    PyImGui.same_line(0, 8)
    ui.action_button("Set Visible (off)", UIManager.SetVisible, state.frame_id, False, key="vis_off")
    ui.action_button("Set Disabled (on)", UIManager.SetDisabled, state.frame_id, True, key="dis_on")
    PyImGui.same_line(0, 8)
    ui.action_button("Set Disabled (off)", UIManager.SetDisabled, state.frame_id, False, key="dis_off")
    state.opacity = PyImGui.input_float("Opacity", state.opacity)
    ui.action_button("Set Opacity", UIManager.SetOpacity, state.frame_id, state.opacity, key="set_opacity")
    state.layer = PyImGui.input_int("Layer", state.layer)
    ui.action_button("Set Frame Layer", UIManager.SetFrameLayer, state.frame_id, state.layer, key="set_layer")
    ui.action_button("Frame Click", UIManager.FrameClick, state.frame_id, key="frame_click")

    PyImGui.spacing()
    ui.section_header("UI Messages")
    state.msg_id = PyImGui.input_int("Message ID", state.msg_id)
    state.wparam = PyImGui.input_int("wparam", state.wparam)
    state.lparam = PyImGui.input_int("lparam", state.lparam)
    ui.action_button("Send UI Message Raw", UIManager.SendUIMessageRaw, state.msg_id, state.wparam, state.lparam, key="send_raw")
    ui.action_button("Send Frame UI Message", UIManager.SendFrameUIMessage, state.frame_id, state.msg_id, state.wparam, state.lparam, key="send_frame")

    PyImGui.spacing()
    ui.section_header("Encoded Strings")
    state.enc_text = PyImGui.input_text("Text / Enc", state.enc_text)
    ui.action_button("Is Valid Enc Str", UIManager.IsValidEncStr, state.enc_text, key="is_enc")
    PyImGui.same_line(0, 8)
    ui.action_button("Async Decode", UIManager.AsyncDecodeStr, state.enc_text, key="dec_enc")
    ui.action_button("EncStr -> UInt32", UIManager.EncStrToUInt32, state.enc_text, key="enc_to_u32")

    PyImGui.spacing()
    ui.section_header("Global")
    state.fps_limit = PyImGui.input_int("FPS Limit", state.fps_limit)
    ui.action_button("Set FPS Limit", UIManager.SetFPSLimit, state.fps_limit, key="set_fps")
    ui.action_button("Clear Frame Logs", UIManager.ClearFrameLogs, key="clr_frame_logs")
    PyImGui.same_line(0, 8)
    ui.action_button("Clear UI Message Logs", UIManager.ClearUIMessageLogs, key="clr_msg_logs")


def draw_uimanager_view() -> None:
    blocks = build_uimanager()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("UIManagerTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
