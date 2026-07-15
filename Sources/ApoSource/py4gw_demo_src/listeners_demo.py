"""
Listeners section — native ``PyListeners`` runtime toggles for game-event listeners
(list / enable / disable / toggle / set_enabled / is_enabled) PLUS a per-listener data view.

Shape mirrors ``player_demo`` exactly:
  * ``build_listeners()`` calls the module free functions, CASTS each value (enabled -> yes/no via
    ``casts.yesno``) and returns display Blocks. For every registered listener it ALSO appends a
    data block read through that listener's OWN data module (verified in the native source), so the
    tab shows not just names/enabled state but the actual buffered data each listener holds.
  * ``draw_listeners_view()`` exposes enable/disable/toggle/set_enabled as explicit trigger buttons
    ("register" a listener = enable it; "poll" = the live list re-read every frame in the Data tab).

Data path — the ``PyListeners`` module is toggle-only (no data getters); each concrete listener
surfaces its buffered state through a SEPARATE embedded module (confirmed in the native source):
  * listener ``"merchant"``      -> ``PyMerchant.PyMerchant`` static getters
      (native ``PY4GW::listeners::MerchantListener``; getters delegate to that singleton —
       src/GW/merchant/merchant_bindings.cpp:179-211, include/listeners/listeners.h:44-76).
  * listener ``"agent_events"``  -> ``PyAgentEvents`` free functions
      (native ``PY4GW::listeners::AgentEventsListener`` ring buffer —
       src/listeners/agent_events_bindings.cpp:57-63, include/listeners/agent_events_listener.h:104-147).
      The full DECODED event log lives in the CombatEvents tab; here we show a compact tail + counts.

R2 coverage — PyListeners (6/6): list, is_enabled, enable, disable, toggle, set_enabled.
Per-listener data getters used (read-only, verified in native source):
  PyMerchant: get_quoted_item_id, get_quoted_value, is_transaction_complete,
              get_trader_item_list, get_merchant_item_list.
  PyAgentEvents: is_enabled, get_event_count, get_capacity, peek_events (non-draining).
"""

import PyImGui
import PyListeners

from . import casts
from . import combatevents_demo
from . import diagnostics
from . import ui

_SECTION = "Listeners"

# How many of the newest agent events to show in the compact per-listener tail.
_EVENT_TAIL = 8


class _State:
    selected_index: int = 0
    name: str = ""
    set_enabled_flag: bool = True


state = _State()

# Lazy handles to the per-listener data modules (embedded — only present in-client).
_merchant_cls = None
_merchant_err = ""
_agent_events_mod = None
_agent_events_err = ""


def _names() -> "list[str]":
    names = casts.safe(PyListeners.list, default=[]) or []
    return [str(n) for n in names]


def _selected_name() -> str:
    """Combo selection wins; fall back to the free-text name field."""
    names = _names()
    if names and 0 <= state.selected_index < len(names):
        return names[state.selected_index]
    return state.name


def _merchant():
    """The ``PyMerchant.PyMerchant`` class (static getters delegate to the merchant listener)."""
    global _merchant_cls, _merchant_err
    if _merchant_cls is None and not _merchant_err:
        try:
            import PyMerchant  # embedded module — only present in-client

            _merchant_cls = PyMerchant.PyMerchant
        except Exception as e:  # noqa: BLE001
            _merchant_err = f"{type(e).__name__}: {e}"
    return _merchant_cls


def _agent_events():
    global _agent_events_mod, _agent_events_err
    if _agent_events_mod is None and not _agent_events_err:
        try:
            import PyAgentEvents  # embedded module — only present in-client

            _agent_events_mod = PyAgentEvents
        except Exception as e:  # noqa: BLE001
            _agent_events_err = f"{type(e).__name__}: {e}"
    return _agent_events_mod


# ---------------------------------------------------------------------------
# Per-listener data blocks — each read through that listener's OWN data module.
# ---------------------------------------------------------------------------
def _merchant_data_blocks():
    """Merchant listener state via PyMerchant static getters (merchant_bindings.cpp:206-211)."""
    cls = _merchant()
    if cls is None:
        return [ui.kv_block("merchant — data", [("Status", f"PyMerchant unavailable — {_merchant_err}")])]

    trader_items = casts.safe(cls.get_trader_item_list, default=[]) or []
    merchant_items = casts.safe(cls.get_merchant_item_list, default=[]) or []
    rows = [
        ("Quoted Item ID", casts.safe(cls.get_quoted_item_id, default=0)),
        ("Quoted Value", casts.safe(cls.get_quoted_value, default=0)),
        ("Transaction Complete", casts.yesno(casts.safe(cls.is_transaction_complete))),
        ("Trader Offered Items", len(trader_items)),
        ("Merchant/Window Items", len(merchant_items)),
        ("(full view)", "see the Merchant tab"),
    ]
    return [ui.kv_block("merchant — data (PyMerchant)", rows)]


def _agent_events_data_blocks():
    """Agent-events ring-buffer summary via PyAgentEvents (agent_events_bindings.cpp:57-63)."""
    mod = _agent_events()
    if mod is None:
        return [ui.kv_block("agent_events — data", [("Status", f"PyAgentEvents unavailable — {_agent_events_err}")])]

    events = casts.safe(mod.peek_events, default=[]) or []
    status = ui.kv_block("agent_events — data (PyAgentEvents)", [
        ("Is Enabled", casts.yesno(casts.safe(mod.is_enabled))),
        ("Event Count (buffered)", casts.safe(mod.get_event_count, default=0)),
        ("Capacity", casts.safe(mod.get_capacity, default=0)),
        ("(full decoded log)", "see the CombatEvents tab"),
    ])

    tail = events[-_EVENT_TAIL:] if _EVENT_TAIL > 0 else list(events)
    base = len(events) - len(tail)
    headers = ["#", "Type", "Agent", "Value", "Target"]
    rows = []
    for i, e in enumerate(tail):
        # PyRawAgentEvent — explicit field deref (never repr the handle); reuse the
        # verified id->name table already hand-wired in combatevents_demo.
        rows.append((
            base + i,
            combatevents_demo._type_name(casts.safe(getattr, e, "event_type", default=0)),
            casts.safe(getattr, e, "agent_id", default=0),
            casts.safe(getattr, e, "value", default=0),
            casts.safe(getattr, e, "target_id", default=0),
        ))
    return [status, ui.multi_block(f"agent_events — latest {len(rows)} (peek)", headers, rows)]


# Registry: listener name -> data-block builder. A listener whose name is not here
# is toggle-only from this tab's perspective (no readable data surfaced).
_DATA_BUILDERS = {
    "merchant": _merchant_data_blocks,
    "agent_events": _agent_events_data_blocks,
}


def _data_blocks_for(name):
    builder = _DATA_BUILDERS.get(name)
    if builder is None:
        return [ui.kv_block(f"{name} — data", [("Data", "no Python-readable data getter for this listener")])]
    return builder()


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _listeners_block():
    names = _names()
    rows = []
    for name in names:
        rows.append((name, casts.yesno(casts.safe(PyListeners.is_enabled, name))))
    return ui.multi_block(f"Listeners ({len(rows)})", ["Name", "Enabled"], rows)


def build_listeners():
    blocks = [_listeners_block()]
    for name in _names():
        blocks.extend(_data_blocks_for(name))
    return blocks


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    names = _names()
    ui.section_header("Target listener")
    if names:
        PyImGui.push_item_width(240)
        state.selected_index = PyImGui.combo("Listener", state.selected_index, names)
        PyImGui.pop_item_width()
    else:
        ui.text_muted("No listeners reported by list().")
    state.name = PyImGui.input_text("Name (overrides combo when set)", state.name)
    target = _selected_name()
    ui.text_muted(f"Target: {target or '<none>'}")

    PyImGui.spacing()
    ui.section_header("Toggle")
    ui.action_button("Enable", PyListeners.enable, target, key="lsn_enable")
    PyImGui.same_line(0, 8)
    ui.action_button("Disable", PyListeners.disable, target, key="lsn_disable")
    PyImGui.same_line(0, 8)
    ui.action_button("Toggle", PyListeners.toggle, target, key="lsn_toggle")

    PyImGui.spacing()
    ui.section_header("Set / query")
    state.set_enabled_flag = PyImGui.checkbox("Enabled", state.set_enabled_flag)
    ui.action_button("Set Enabled", PyListeners.set_enabled, target, state.set_enabled_flag, key="lsn_set")
    PyImGui.same_line(0, 8)
    ui.action_button("Is Enabled", PyListeners.is_enabled, target, key="lsn_is")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_listeners_view() -> None:
    blocks = build_listeners()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("ListenersTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
