"""
Combat / Agent Events section — native ``PyAgentEvents`` capture buffer.

FIX: the legacy ``PyCombatEvents`` stub (EventType / PyRawCombatEvent / PyCombatEventQueue) is
orphaned — no live module implements it. The live surface is ``PyAgentEvents``: an event-type
constant submodule (``PyEventType``), a ``PyRawAgentEvent`` struct, and 7 module-level functions
(R2). This section wires that live surface directly.

Shape mirrors ``player_demo.py``:
  * ``build_combatevents()`` reads capture status + drains-free ``peek_events()`` and derefs each
    ``PyRawAgentEvent`` FIELD-BY-FIELD (all 10 readonly fields), resolving ``event_type`` to a name
    via the hand-wired ``PyEventType`` table. Peek is a passive read, safe once per frame.
  * ``draw_combatevents_view()`` renders the log and exposes the buffer lifecycle (enable / disable /
    drain) as explicit trigger buttons.

Data path: ``PyAgentEvents`` (native ``PY4GW::listeners::AgentEvents``). Lazy import so a missing
binding degrades gracefully.

R2 coverage — PyAgentEvents (module 10, 10 members across 2 structs). Wired:
  ``enable`` / ``disable`` (Actions), ``is_enabled`` (status), ``peek_events`` (live log, non-draining),
  ``get_and_clear_events`` (Drain action), ``get_event_count`` + ``get_capacity`` (status).
  PyRawAgentEvent fields deref'd: timestamp, event_type, agent_id, value, target_id, float_value,
  agent_max_hp, agent_max_energy, target_max_hp, target_max_energy. PyEventType — all 33 constants
  hand-wired into ``_EVENT_TYPE_NAMES`` for id->name resolution + the type filter.
  Skipped: ``PyRawAgentEvent.as_tuple`` (redundant with explicit field deref — noted, not used),
  ``__init__`` / ``__repr__`` (dunders).
"""

import PyImGui

from . import casts
from . import diagnostics
from . import ui

_SECTION = "CombatEvents"

# Hand-wired from R2 (GW_AGENT_EVENT_TYPES X-macro). NO reflection on the PyEventType submodule.
_EVENT_TYPE_NAMES = {
    1: "SKILL_ACTIVATED",
    2: "ATTACK_SKILL_ACTIVATED",
    3: "SKILL_STOPPED",
    4: "SKILL_FINISHED",
    5: "ATTACK_SKILL_FINISHED",
    6: "INTERRUPTED",
    7: "INSTANT_SKILL_ACTIVATED",
    8: "ATTACK_SKILL_STOPPED",
    13: "ATTACK_STARTED",
    14: "ATTACK_STOPPED",
    15: "MELEE_ATTACK_FINISHED",
    16: "DISABLED",
    17: "KNOCKED_DOWN",
    18: "CASTTIME",
    30: "DAMAGE",
    31: "CRITICAL",
    32: "ARMOR_IGNORING",
    33: "HEALING",
    34: "CURRENT_HEALTH",
    35: "CURRENT_ENERGY",
    36: "HEALTH_REGEN_CHANGE",
    37: "ENERGY_REGEN_CHANGE",
    38: "REACHED_MAXHP",
    40: "EFFECT_APPLIED",
    41: "EFFECT_REMOVED",
    42: "EFFECT_ON_TARGET",
    43: "EFFECT_RENEWED",
    50: "ENERGY_GAINED",
    51: "ENERGY_SPENT",
    60: "SKILL_DAMAGE",
    70: "SKILL_ACTIVATE_PACKET",
    80: "SKILL_RECHARGE",
    81: "SKILL_RECHARGED",
}

_events_mod = None
_load_error = ""


class _State:
    type_filter: int = 0  # 0 = all; otherwise a PyEventType value
    max_rows: int = 100


state = _State()


def _events():
    global _events_mod, _load_error
    if _events_mod is None and not _load_error:
        try:
            import PyAgentEvents  # embedded module — only present in-client

            _events_mod = PyAgentEvents
        except Exception as e:  # noqa: BLE001
            _load_error = f"{type(e).__name__}: {e}"
    return _events_mod


def _type_name(event_type) -> str:
    try:
        et = int(event_type)
    except (TypeError, ValueError):
        return str(event_type)
    return f"[{et}] {_EVENT_TYPE_NAMES.get(et, 'Unknown')}"


def _filter_label() -> str:
    return "All" if not state.type_filter else _type_name(state.type_filter)


# ---------------------------------------------------------------------------
# build_* — read status + peek buffer, deref every event field, return blocks
# ---------------------------------------------------------------------------
def build_combatevents():
    mod = _events()
    if mod is None:
        return [ui.kv_block("Agent Events", [("Status", f"PyAgentEvents unavailable — {_load_error}")])]

    status = ui.kv_block("Capture", [
        ("Is Enabled", casts.yesno(casts.safe(mod.is_enabled))),
        ("Event Count (buffered)", casts.safe(mod.get_event_count)),
        ("Capacity", casts.safe(mod.get_capacity)),
        ("Type Filter", _filter_label()),
    ])

    events = casts.safe(mod.peek_events, default=[]) or []
    if state.type_filter:
        events = [e for e in events if casts.safe(getattr, e, "event_type", default=None) == state.type_filter]

    shown = events[-state.max_rows:] if state.max_rows > 0 else list(events)
    base = len(events) - len(shown)

    headers = [
        "#", "Timestamp", "Type", "Agent", "Value", "Target", "Float",
        "A.MaxHP", "A.MaxEn", "T.MaxHP", "T.MaxEn",
    ]
    rows = []
    for i, e in enumerate(shown):
        # PyRawAgentEvent — explicit field deref (never repr the handle).
        rows.append((
            base + i,
            casts.safe(getattr, e, "timestamp", default=0),
            _type_name(casts.safe(getattr, e, "event_type", default=0)),
            casts.safe(getattr, e, "agent_id", default=0),
            casts.safe(getattr, e, "value", default=0),
            casts.safe(getattr, e, "target_id", default=0),
            casts.f2(casts.safe(getattr, e, "float_value", default=0.0)),
            casts.safe(getattr, e, "agent_max_hp", default=0),
            casts.safe(getattr, e, "agent_max_energy", default=0),
            casts.safe(getattr, e, "target_max_hp", default=0),
            casts.safe(getattr, e, "target_max_energy", default=0),
        ))

    return [status, ui.multi_block("Agent Event Log (peek)", headers, rows)]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _drain():
    """Drain the buffer via get_and_clear_events; report how many were discarded."""
    mod = _events()
    if mod is None:
        return "unavailable"
    drained = mod.get_and_clear_events() or []
    return f"drained {len(drained)}"


def _draw_actions():
    mod = _events()
    ui.section_header("Capture control")
    if mod is None:
        ui.not_available(f"PyAgentEvents unavailable — {_load_error}")
        return
    ui.text_muted(
        "The listener is enabled by default at startup. peek_events (Data tab) reads without "
        "draining; Drain calls get_and_clear_events to empty the buffer."
    )
    ui.action_button("Enable", mod.enable, key="ce_enable")
    PyImGui.same_line(0, 8)
    ui.action_button("Disable", mod.disable, key="ce_disable")
    PyImGui.same_line(0, 8)
    ui.action_button("Drain (get_and_clear)", _drain, key="ce_drain")

    PyImGui.spacing()
    ui.section_header("Log view")
    state.type_filter = PyImGui.input_int("Type Filter (0 = all)", state.type_filter)
    if state.type_filter < 0:
        state.type_filter = 0
    ui.text_muted(_filter_label())
    state.max_rows = PyImGui.input_int("Max Rows (tail)", state.max_rows)
    if state.max_rows < 0:
        state.max_rows = 0


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_combatevents_view() -> None:
    blocks = build_combatevents()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("CombatEventsTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
