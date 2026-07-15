"""
Chat section — is-typing state + a channel reference, and the full send/write/color/timestamp
action surface.

Shape (see player_demo.py, the canonical template):
  * ``build_chat()`` calls the native ``PyChat`` free functions (only ``get_is_typing`` is a
    read-only getter), CASTS values via ``casts``, and returns display Blocks. ``PyChat`` binds
    only module-level free functions — no ``py::class_``/``py::enum_`` and no struct returns are
    exposed to Python (the C++ ``Context::ChatBuffer*`` / ``GetChatLog`` accessors are NOT bound),
    so there is no handle to instantiate and no chat-log struct to deref here. The ``Channel`` enum
    is likewise not bound — callers pass raw ints, mirrored locally for a readable reference table.
  * ``draw_chat_view()`` builds once, offers the per-section Dump-to-file button, then a tab bar:
    ``Data`` (ui.draw_blocks) + ``Actions`` (explicit trigger buttons, never auto-fired).

Data paths:
  * native ``PyChat`` module (free functions only) — is-typing getter + the send/write/color
    action surface.
  * ``GWContext.World`` (M1 context path) — the chat/dialog compose buffers
    (``WorldContext.message_buff`` / ``dialog_buff``, both ``Array<wchar_t>``) ARE reachable.

Genuinely NOT reachable from Python: the chat LOG ring buffer. ``GW::Context::ChatBuffer``
(include/GW/context/chat.h — a 0x200-entry ring of ``ChatMessage{channel, timestamp, message}``)
is reached only through the unbound ``GetChatBufferAddress()`` module function; it has NO
shared-memory pointer (see PointersSSM) and NO ctypes reader, so there is no handle to it here.
The async chat history text is exposed elsewhere as ``Player.RequestChatHistory`` /
``Player.GetChatHistory`` (see player_demo.py), a separate PyPlayer mechanism, not PyChat.

R2 coverage — PyChat (13 methods, ALL wired):
  Data getter (Data tab): get_is_typing(2).
  Action/mutators (Actions tab): force_redraw_chat_log(1), send_chat(3), send_chat_by_name(4),
  write_chat(5), write_chat_ex(6), toggle_timestamps(7), set_timestamps_format(8),
  set_timestamps_color(9), set_sender_color(10), set_message_color(11), send_fake_chat(12),
  send_fake_chat_colored(13).
  Skipped: none — the whole bound surface is wired.
"""

import PyImGui

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Chat"

# Native module handle, guarded so the section survives an offline / no-binding interpreter.
try:  # pragma: no cover - runtime specific
    import PyChat as _PyChat
except Exception:  # noqa: BLE001 - offline: no embedded binding
    _PyChat = None

# Context facade, guarded the same way (registers a context callback on import).
try:  # pragma: no cover - runtime specific
    from Py4GWCoreLib.Context import GWContext as _GWContext
except Exception:  # noqa: BLE001 - offline: no context path
    _GWContext = None

# GW::chat::Channel is NOT bound to Python; mirror it locally for a readable reference / casts.
# (include/GW/common/constants/chat.h)
_CHANNEL_NAMES = {
    0: "ALLIANCE",
    1: "ALLIES",
    2: "GWCA1",
    3: "ALL",
    4: "GWCA2",
    5: "MODERATOR",
    6: "EMOTE",
    7: "WARNING",
    8: "GWCA3",
    9: "GUILD",
    10: "GLOBAL",
    11: "GROUP",
    12: "TRADE",
    13: "ADVISORY",
    14: "WHISPER",
}


# ---------------------------------------------------------------------------
# Helpers (explicit, hand-wired — no reflection/dir())
# ---------------------------------------------------------------------------
def _chat_call(fn_name: str, default, *args):
    """Call one explicitly-named ``PyChat`` free function, guarded."""
    if _PyChat is None:
        return default
    fn = getattr(_PyChat, fn_name, None)
    if not callable(fn):
        return default
    return casts.safe(fn, *args, default=default)


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _state_block():
    if _PyChat is None:
        return ui.text_block("Chat", "PyChat binding unavailable (offline / not injected).")
    rows = [
        ("Is Typing", casts.yesno(_chat_call("get_is_typing", False))),
    ]
    return ui.kv_block("Chat State", rows)


def _buffers_block():
    """WorldContext chat/dialog compose buffers — the only chat context reachable from Python.

    ``message_buff`` / ``dialog_buff`` are ``Array<wchar_t>`` on WorldContextStruct
    (native_src/context/WorldContext.py); their ``*_buff`` properties return a list of single
    chars (or None), which we join field-by-field into the shown string.
    """
    if _GWContext is None:
        return ui.text_block("Chat Buffers (GWContext.World)", "Context path unavailable (offline).")
    ctx = casts.safe(_GWContext.World.GetContext, default=None)
    if ctx is None:
        return ui.text_block(
            "Chat Buffers (GWContext.World)",
            "WorldContext not available in this state (offline / not injected / no pointer yet).",
        )
    message_chars = casts.safe(getattr, ctx, "message_buff", default=None)
    dialog_chars = casts.safe(getattr, ctx, "dialog_buff", default=None)
    message_str = "".join(str(c) for c in message_chars) if message_chars else ""
    dialog_str = "".join(str(c) for c in dialog_chars) if dialog_chars else ""
    rows = [
        ("message_buff (len)", len(message_chars) if message_chars else 0),
        ("message_buff (text)", message_str if message_str else "(empty)"),
        ("dialog_buff (len)", len(dialog_chars) if dialog_chars else 0),
        ("dialog_buff (text)", dialog_str if dialog_str else "(empty)"),
    ]
    return ui.kv_block("Chat / Dialog Buffers (WorldContext.message_buff / dialog_buff)", rows)


def _unavailable_block():
    return ui.text_block(
        "Chat Log — not exposed to Python",
        "The chat LOG ring buffer (GW::Context::ChatBuffer: 0x200 entries of channel + FILETIME "
        "timestamp + message) has no shared-memory pointer and no ctypes reader, so it cannot be "
        "read here. For log text use Player.RequestChatHistory / Player.GetChatHistory (see the "
        "Player section) — a separate PyPlayer mechanism.",
    )


def _channels_block():
    headers = ["Channel ID", "Name"]
    rows = [(cid, name) for cid, name in sorted(_CHANNEL_NAMES.items())]
    return ui.multi_block("Channel Reference (pass raw int to actions)", headers, rows)


def build_chat():
    blocks = [_state_block()]
    blocks.append(_buffers_block())
    blocks.append(_unavailable_block())
    blocks.append(_channels_block())
    return blocks


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
class _State:
    channel: int = 3                # send/write channel (3 = ALL)
    message: str = "hello"          # message body
    sender: str = ""                # write_chat_ex / send_chat_by_name sender name
    use_24h: int = 1                # set_timestamps_format
    show_seconds: int = 0           # set_timestamps_format
    timestamps_on: int = 1          # toggle_timestamps
    color_r: int = 255
    color_g: int = 255
    color_b: int = 255


state = _State()


def _draw_actions():
    ui.section_header("Send / Write")
    ui.text_muted("Channel: see the reference table on the Data tab (raw int).")
    state.channel = PyImGui.input_int("Channel", state.channel)
    state.message = PyImGui.input_text("Message", state.message)
    state.sender = PyImGui.input_text("Sender / From", state.sender)
    ui.action_button("Send Chat", _chat_action, "send_chat", state.channel, state.message, key="send_chat")
    PyImGui.same_line(0, 8)
    ui.action_button(
        "Send Chat By Name", _chat_action, "send_chat_by_name", state.sender, state.message, key="send_by_name"
    )
    ui.action_button("Write Chat", _chat_action, "write_chat", state.channel, state.message, key="write_chat")
    PyImGui.same_line(0, 8)
    ui.action_button(
        "Write Chat Ex", _chat_action, "write_chat_ex", state.channel, state.message, state.sender, key="write_ex"
    )
    ui.action_button(
        "Send Fake Chat", _chat_action, "send_fake_chat", state.channel, state.message, key="fake_chat"
    )
    ui.action_button("Force Redraw Chat Log", _chat_action, "force_redraw_chat_log", key="redraw")

    PyImGui.spacing()
    ui.section_header("Colors (RGB 0-255)")
    state.color_r = PyImGui.input_int("R", state.color_r)
    state.color_g = PyImGui.input_int("G", state.color_g)
    state.color_b = PyImGui.input_int("B", state.color_b)
    ui.action_button(
        "Send Fake Chat (colored)", _chat_action, "send_fake_chat_colored",
        state.channel, state.message, state.color_r, state.color_g, state.color_b, key="fake_colored"
    )
    ui.action_button(
        "Set Sender Color", _chat_action, "set_sender_color",
        state.channel, state.color_r, state.color_g, state.color_b, key="sender_color"
    )
    PyImGui.same_line(0, 8)
    ui.action_button(
        "Set Message Color", _chat_action, "set_message_color",
        state.channel, state.color_r, state.color_g, state.color_b, key="message_color"
    )
    ui.action_button(
        "Set Timestamps Color", _chat_action, "set_timestamps_color",
        state.color_r, state.color_g, state.color_b, key="ts_color"
    )

    PyImGui.spacing()
    ui.section_header("Timestamps")
    state.timestamps_on = PyImGui.input_int("Enable (0/1)", state.timestamps_on)
    ui.action_button(
        "Toggle Timestamps", _chat_action, "toggle_timestamps", bool(state.timestamps_on), key="toggle_ts"
    )
    state.use_24h = PyImGui.input_int("24h (0/1)", state.use_24h)
    state.show_seconds = PyImGui.input_int("Show Seconds (0/1)", state.show_seconds)
    ui.action_button(
        "Set Timestamps Format", _chat_action, "set_timestamps_format",
        bool(state.use_24h), bool(state.show_seconds), key="ts_format"
    )


def _chat_action(fn_name: str, *args):
    """Fire one explicitly-named PyChat action; raise if the binding is missing."""
    if _PyChat is None:
        raise RuntimeError("PyChat binding unavailable")
    fn = getattr(_PyChat, fn_name, None)
    if not callable(fn):
        raise RuntimeError(f"PyChat.{fn_name} unavailable")
    return fn(*args)


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_chat_view() -> None:
    blocks = build_chat()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("ChatTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
