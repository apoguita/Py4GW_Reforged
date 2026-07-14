"""
Dialog section — active NPC dialog, buttons, catalog/query, event logs & callback journal.

Shape (see player_demo.py, the canonical template):
  * ``build_dialog()`` calls the Dialog wrapper + the native ``PyDialog`` static surface,
    CASTS/dereferences every struct field-by-field via ``casts``, and returns display Blocks.
    No dialog struct/handle ever reaches a renderer un-dereferenced (R1 §4 / R3 M4).
  * ``draw_dialog_view()`` builds once, offers the per-section Dump-to-file button, then a
    tab bar: ``Data`` (ui.draw_blocks) + ``Actions`` (explicit trigger buttons, never auto-fired).

Data path: ``Py4GWCoreLib.Dialog`` wrapper (sanitizes text + inline-choice fallback) for the
active dialog & its buttons; the native ``PyDialog.PyDialog`` static class for the catalog,
per-dialog reads, decode status, event logs, and the callback journal. Send actions route through
``Player`` (action-queue backed).

R2 coverage — PyDialog (39 rows).
  Struct constructors (rows 1-7: DialogInfo/ActiveDialogInfo/DialogButtonInfo/DialogTextDecodedInfo/
  DialogEventLog/DialogCallbackJournalEntry/PyDialog ``__init__``) are SKIPPED as callables — we
  consume instances returned by the getters and deref their fields, never construct them.
  Getters wired (deref'd): is_dialog_available(8), get_dialog_info(9), get_last_selected_dialog_id(10),
  get_active_dialog(11), get_active_dialog_buttons(12), is_dialog_active(13), is_dialog_displayed(14),
  enumerate_available_dialogs(15), get_dialog_text_decoded(16), is_dialog_text_decode_pending(17),
  get_dialog_text_decode_status(18), read_dialog_flags(19), read_dialog_frame_type(20),
  read_dialog_event_handler(21), read_dialog_content_id(22), read_dialog_property_id(23),
  get_dialog_event_logs(24), get_dialog_event_logs_received(25), get_dialog_event_logs_sent(26),
  get_dialog_callback_journal(30), get_dialog_callback_journal_received(31),
  get_dialog_callback_journal_sent(32).
  Action/mutators wired (Actions tab): clear_dialog_event_logs(27),
  clear_dialog_event_logs_received(28), clear_dialog_event_logs_sent(29),
  clear_dialog_callback_journal(33), clear_dialog_callback_journal_received(34),
  clear_dialog_callback_journal_sent(35), clear_dialog_callback_journal_filtered(36),
  clear_cache(37), initialize(38), terminate(39).
  Send actions (Player wrapper): SendDialog, SendRawDialog, SendAutomaticDialog, and the
  ``dialog take`` chat command (SendChatCommand).
"""

import PyImGui

from Py4GWCoreLib import Agent
from Py4GWCoreLib import Dialog
from Py4GWCoreLib.Player import Player

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Dialog"
_MAX_ROWS = 100  # cap unbounded log/journal tables so a busy session never floods the panel

# Native module handle, guarded so the section survives an offline / no-binding interpreter.
try:  # pragma: no cover - runtime specific
    import PyDialog as _PyDialogModule

    _PD = _PyDialogModule.PyDialog
except Exception:  # noqa: BLE001 - offline: no embedded binding
    _PD = None


class _State:
    dialog_hex: str = "0x84"          # query id (Data) + Send Dialog (Actions)
    button_number: int = 0            # SendAutomaticDialog visible-button index
    raw_dialog_id: int = 0x84         # SendRawDialog (kSendAgentDialog)
    filter_npc_uid: str = ""          # clear_dialog_callback_journal_filtered args
    filter_incoming: int = -1         # -1 = None, 0 = outgoing, 1 = incoming
    filter_message_id: int = -1       # -1 = None
    filter_event_type: str = ""


state = _State()


# ---------------------------------------------------------------------------
# Helpers (explicit, hand-wired — no reflection/dir())
# ---------------------------------------------------------------------------
def _pd_call(method_name: str, default, *args):
    """Call one explicitly-named ``PyDialog`` static method, guarded.

    Mirrors the wrapper's own ``_call_native_dialog_method``: the caller always passes a constant
    method name (no discovery), and any binding gap (offline, native-only method absent from the
    stub, or a raising getter) degrades to ``default``.
    """
    if _PD is None:
        return default
    fn = getattr(_PD, method_name, None)
    if not callable(fn):
        return default
    return casts.safe(fn, *args, default=default)


def _parse_dialog_id(text) -> int:
    try:
        s = str(text).strip().lower()
        return int(s, 16) if s.startswith("0x") else int(s or 0)
    except (TypeError, ValueError):
        return 0


def _agent_name(agent_id) -> str:
    if not agent_id:
        return "-"
    return casts.safe(Agent.GetNameByID, agent_id, default="?")


def _bytes_hex(raw) -> str:
    try:
        return " ".join(f"{int(b) & 0xFF:02X}" for b in (raw or []))
    except (TypeError, ValueError):
        return str(raw)


def _field(obj, name, default="<n/a>"):
    """Deref one struct field explicitly (never repr the whole struct)."""
    return casts.safe(getattr, obj, name, default=default)


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _active_block():
    active = casts.safe(Dialog.get_active_dialog)  # ActiveDialogInfo | None (wrapper: sanitized)
    rows = [
        ("Is Dialog Active", casts.yesno(_pd_call("is_dialog_active", False))),
        ("Last Selected Dialog ID", casts.hex_of(_pd_call("get_last_selected_dialog_id", 0))),
    ]
    if active is None:
        rows.append(("Active Dialog", "None"))
    else:
        did = _field(active, "dialog_id", 0)
        cdid = _field(active, "context_dialog_id", 0)
        agent_id = _field(active, "agent_id", 0)
        rows.extend([
            ("Dialog ID", f"{casts.hex_of(did)} ({did})"),
            ("Context Dialog ID", f"{casts.hex_of(cdid)} ({cdid})"),
            ("Agent ID", casts.id_name(agent_id, _agent_name(agent_id))),
            ("Dialog ID Authoritative", casts.yesno(_field(active, "dialog_id_authoritative", False))),
            ("Message", _field(active, "message", "")),
            ("Raw Message", _field(active, "raw_message", "")),
        ])
    return ui.kv_block("Active Dialog", rows)


def _buttons_block():
    buttons = casts.safe(Dialog.get_active_dialog_buttons, default=[]) or []  # list[DialogButtonInfo]
    headers = ["#", "Dialog ID", "Icon", "Message", "Decoded", "Decode Pending"]
    rows = []
    for i, btn in enumerate(buttons[:_MAX_ROWS]):
        did = _field(btn, "dialog_id", 0)
        rows.append((
            i,
            f"{casts.hex_of(did)} ({did})",
            _field(btn, "button_icon", 0),
            _field(btn, "message", ""),
            _field(btn, "message_decoded", ""),
            casts.yesno(_field(btn, "message_decode_pending", False)),
        ))
    title = f"Active Dialog Buttons ({len(buttons)})"
    return ui.multi_block(title, headers, rows)


def _query_block():
    did = _parse_dialog_id(state.dialog_hex)
    info = _pd_call("get_dialog_info", None, did)  # DialogInfo
    rows = [
        ("Query Dialog ID", f"{casts.hex_of(did)} ({did})"),
        ("Is Available", casts.yesno(_pd_call("is_dialog_available", False, did))),
        ("Is Displayed", casts.yesno(_pd_call("is_dialog_displayed", False, did))),
        ("Text Decoded", str(_pd_call("get_dialog_text_decoded", "", did))),
        ("Text Decode Pending", casts.yesno(_pd_call("is_dialog_text_decode_pending", False, did))),
        ("read_dialog_flags", casts.flags(_pd_call("read_dialog_flags", 0, did))),
        ("read_dialog_frame_type", _pd_call("read_dialog_frame_type", 0, did)),
        ("read_dialog_event_handler", casts.ptr(_pd_call("read_dialog_event_handler", 0, did))),
        ("read_dialog_content_id", _pd_call("read_dialog_content_id", 0, did)),
        ("read_dialog_property_id", _pd_call("read_dialog_property_id", 0, did)),
    ]
    if info is None:
        rows.append(("get_dialog_info", "None"))
    else:
        agent_id = _field(info, "agent_id", 0)
        rows.extend([
            ("info.dialog_id", casts.hex_of(_field(info, "dialog_id", 0))),
            ("info.flags", casts.flags(_field(info, "flags", 0))),
            ("info.frame_type", _field(info, "frame_type", 0)),
            ("info.event_handler", casts.ptr(_field(info, "event_handler", 0))),
            ("info.content_id", _field(info, "content_id", 0)),
            ("info.property_id", _field(info, "property_id", 0)),
            ("info.agent_id", casts.id_name(agent_id, _agent_name(agent_id))),
            ("info.content", _field(info, "content", "")),
        ])
    return ui.kv_block("Dialog Query (set ID in Actions tab)", rows)


def _catalog_block():
    dialogs = _pd_call("enumerate_available_dialogs", []) or []  # list[DialogInfo]
    headers = ["Dialog ID", "Flags", "Frame", "Handler", "Content ID", "Property ID", "Agent", "Content"]
    rows = []
    for info in dialogs[:_MAX_ROWS]:
        agent_id = _field(info, "agent_id", 0)
        rows.append((
            casts.hex_of(_field(info, "dialog_id", 0)),
            casts.hex_of(_field(info, "flags", 0)),
            _field(info, "frame_type", 0),
            casts.ptr(_field(info, "event_handler", 0)),
            _field(info, "content_id", 0),
            _field(info, "property_id", 0),
            casts.id_name(agent_id, _agent_name(agent_id)),
            _field(info, "content", ""),
        ))
    return ui.multi_block(f"Available Dialogs ({len(dialogs)})", headers, rows)


def _decode_status_block():
    statuses = _pd_call("get_dialog_text_decode_status", []) or []  # list[DialogTextDecodedInfo]
    headers = ["Dialog ID", "Pending", "Text"]
    rows = []
    for st in statuses[:_MAX_ROWS]:
        rows.append((
            casts.hex_of(_field(st, "dialog_id", 0)),
            casts.yesno(_field(st, "pending", False)),
            _field(st, "text", ""),
        ))
    return ui.multi_block(f"Text Decode Status ({len(statuses)})", headers, rows)


def _event_logs_block():
    logs = _pd_call("get_dialog_event_logs", []) or []  # list[DialogEventLog]
    recv = _pd_call("get_dialog_event_logs_received", []) or []
    sent = _pd_call("get_dialog_event_logs_sent", []) or []
    counts = ui.kv_block("Event Log Counts", [
        ("Total", len(logs)),
        ("Received", len(recv)),
        ("Sent", len(sent)),
    ])
    headers = ["Tick", "Msg ID", "Incoming", "Frame Msg", "Frame ID", "wparam bytes", "lparam bytes"]
    rows = []
    for log in logs[:_MAX_ROWS]:
        rows.append((
            _field(log, "tick", 0),
            casts.hex_of(_field(log, "message_id", 0)),
            casts.yesno(_field(log, "incoming", False)),
            casts.yesno(_field(log, "is_frame_message", False)),
            casts.hex_of(_field(log, "frame_id", 0)),
            _bytes_hex(_field(log, "w_bytes", [])),
            _bytes_hex(_field(log, "l_bytes", [])),
        ))
    table = ui.multi_block(f"Dialog Event Logs ({len(logs)})", headers, rows)
    return [counts, table]


def _journal_block():
    journal = _pd_call("get_dialog_callback_journal", []) or []  # list[DialogCallbackJournalEntry]
    recv = _pd_call("get_dialog_callback_journal_received", []) or []
    sent = _pd_call("get_dialog_callback_journal_sent", []) or []
    counts = ui.kv_block("Callback Journal Counts", [
        ("Total", len(journal)),
        ("Received", len(recv)),
        ("Sent", len(sent)),
    ])
    headers = [
        "Tick", "Msg ID", "In", "Dialog ID", "Ctx ID", "Agent", "Map", "Model",
        "Auth", "Ctx Inferred", "NPC UID", "Event", "Text",
    ]
    rows = []
    for e in journal[:_MAX_ROWS]:
        agent_id = _field(e, "agent_id", 0)
        rows.append((
            _field(e, "tick", 0),
            casts.hex_of(_field(e, "message_id", 0)),
            casts.yesno(_field(e, "incoming", False)),
            casts.hex_of(_field(e, "dialog_id", 0)),
            casts.hex_of(_field(e, "context_dialog_id", 0)),
            casts.id_name(agent_id, _agent_name(agent_id)),
            _field(e, "map_id", 0),
            _field(e, "model_id", 0),
            casts.yesno(_field(e, "dialog_id_authoritative", False)),
            casts.yesno(_field(e, "context_dialog_id_inferred", False)),
            _field(e, "npc_uid", ""),
            _field(e, "event_type", ""),
            _field(e, "text", ""),
        ))
    table = ui.multi_block(f"Dialog Callback Journal ({len(journal)})", headers, rows)
    return [counts, table]


def build_dialog():
    blocks = [
        _active_block(),
        _buttons_block(),
        _query_block(),
        _catalog_block(),
        _decode_status_block(),
    ]
    blocks.extend(_event_logs_block())
    blocks.extend(_journal_block())
    return blocks


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Send Dialog / Take")
    state.dialog_hex = PyImGui.input_text("Dialog ID (hex, e.g. 0x84)", state.dialog_hex)
    ui.action_button("Send Dialog", Player.SendDialog, state.dialog_hex, key="send_dialog")
    PyImGui.same_line(0, 8)
    ui.action_button("Send Raw Dialog", Player.SendRawDialog, _parse_dialog_id(state.dialog_hex), key="send_raw")
    state.button_number = PyImGui.input_int("Visible Button #", state.button_number)
    ui.action_button("Send Automatic Dialog", Player.SendAutomaticDialog, state.button_number, key="auto_dialog")
    PyImGui.same_line(0, 8)
    ui.action_button("Dialog Take (chat cmd)", Player.SendChatCommand, "dialog take", key="dialog_take")

    PyImGui.spacing()
    ui.section_header("Event Logs (native maintainers)")
    ui.action_button("Clear Event Logs", _pd_action, "clear_dialog_event_logs", key="clr_logs")
    PyImGui.same_line(0, 8)
    ui.action_button("Clear Received", _pd_action, "clear_dialog_event_logs_received", key="clr_logs_recv")
    PyImGui.same_line(0, 8)
    ui.action_button("Clear Sent", _pd_action, "clear_dialog_event_logs_sent", key="clr_logs_sent")

    PyImGui.spacing()
    ui.section_header("Callback Journal")
    ui.action_button("Clear Journal", _pd_action, "clear_dialog_callback_journal", key="clr_jnl")
    PyImGui.same_line(0, 8)
    ui.action_button("Clear Received", _pd_action, "clear_dialog_callback_journal_received", key="clr_jnl_recv")
    PyImGui.same_line(0, 8)
    ui.action_button("Clear Sent", _pd_action, "clear_dialog_callback_journal_sent", key="clr_jnl_sent")

    PyImGui.spacing()
    ui.section_header("Clear Journal (filtered)")
    state.filter_npc_uid = PyImGui.input_text("NPC UID ('' = any)", state.filter_npc_uid)
    state.filter_incoming = PyImGui.input_int("Incoming (-1 any / 0 out / 1 in)", state.filter_incoming)
    state.filter_message_id = PyImGui.input_int("Message ID (-1 = any)", state.filter_message_id)
    state.filter_event_type = PyImGui.input_text("Event Type ('' = any)", state.filter_event_type)
    ui.action_button("Clear Filtered", _clear_journal_filtered, key="clr_jnl_filt")

    PyImGui.spacing()
    ui.section_header("Cache / Lifecycle")
    ui.action_button("Clear Cache", _pd_action, "clear_cache", key="clr_cache")
    PyImGui.same_line(0, 8)
    ui.action_button("Initialize", _pd_action, "initialize", key="pd_init")
    PyImGui.same_line(0, 8)
    ui.action_button("Terminate", _pd_action, "terminate", key="pd_term")


def _pd_action(method_name: str):
    """Fire one explicitly-named PyDialog mutator; raise if the binding is missing."""
    if _PD is None:
        raise RuntimeError("PyDialog binding unavailable")
    fn = getattr(_PD, method_name, None)
    if not callable(fn):
        raise RuntimeError(f"PyDialog.{method_name} unavailable")
    return fn()


def _clear_journal_filtered():
    if _PD is None:
        raise RuntimeError("PyDialog binding unavailable")
    npc_uid = state.filter_npc_uid or None
    incoming = None if state.filter_incoming < 0 else bool(state.filter_incoming)
    message_id = None if state.filter_message_id < 0 else int(state.filter_message_id)
    event_type = state.filter_event_type or None
    return _PD.clear_dialog_callback_journal_filtered(
        npc_uid=npc_uid,
        incoming=incoming,
        message_id=message_id,
        event_type=event_type,
    )


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_dialog_view() -> None:
    blocks = build_dialog()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("DialogTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
