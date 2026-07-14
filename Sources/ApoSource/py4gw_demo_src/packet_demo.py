"""
Packet Sniffer section — live StoC/CToS capture, dereferenced log entries.

Shape mirrors ``player_demo.py``:
  * ``build_packet()`` reads the capture log through the ``SNIFFER`` wrapper (which wraps native
    ``PyPacketSniffer``), casts each ``PacketLogEntry`` FIELD-BY-FIELD (tick / direction / header /
    size / data), enriches with the wrapper's ``get_packet_name`` + ``decode_packet``, and returns
    a multi_block. A struct never reaches a renderer un-dereferenced.
  * ``draw_packet_view()`` renders the log and exposes the capture lifecycle (init / terminate /
    clear, per direction) as explicit trigger buttons. Reading the log is a passive read, safe
    once per frame.

Data path: ``Py4GWCoreLib.PacketSniffer.SNIFFER`` (facade over native ``PyPacketSniffer.PacketSniffer``).
The wrapper's direction argument routes ``both`` / ``StoC`` / ``CToS`` to the matching native method.

R2 coverage — PyPacketSniffer (module 20, 15 methods across 3 structs). Wired via SNIFFER:
  ``instance`` (used by the wrapper singleton), ``initialize`` / ``initialize_stoc`` /
  ``initialize_ctos`` (Init buttons, per direction), ``terminate`` / ``terminate_stoc`` /
  ``terminate_ctos`` (Terminate buttons), ``get_logs`` / ``get_stoc_logs`` / ``get_ctos_logs``
  (log read, per direction filter), ``clear_logs`` / ``clear_stoc_logs`` / ``clear_ctos_logs``
  (Clear buttons). PacketLogEntry fields deref'd: tick, direction, header, size, data.
  PacketDirection enum surfaced via the direction filter. Skipped: ``PacketLogEntry.__repr__``
  (dunder — replaced by explicit field deref).
"""

import PyImGui

from Py4GWCoreLib.PacketSniffer import SNIFFER

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Packet"

# both -> native *_logs/initialize/terminate/clear_logs ; StoC/CToS -> the *_stoc/*_ctos variants
_DIRECTIONS = ["both", "StoC", "CToS"]


class _State:
    dir_index: int = 0     # index into _DIRECTIONS for the Data-tab log filter
    action_index: int = 0  # index into _DIRECTIONS for the Actions-tab init/term/clear target
    max_rows: int = 100    # tail length shown in the log table


state = _State()


def _direction() -> str:
    return _DIRECTIONS[state.dir_index]


def _action_direction() -> str:
    return _DIRECTIONS[state.action_index]


# ---------------------------------------------------------------------------
# build_* — read log, deref every entry field, cast, return blocks
# ---------------------------------------------------------------------------
def build_packet():
    direction = _direction()
    entries = casts.safe(SNIFFER.get_logs, direction, default=[]) or []

    shown = entries[-state.max_rows:] if state.max_rows > 0 else list(entries)
    base = len(entries) - len(shown)

    summary = ui.kv_block("Capture", [
        ("Direction Filter", direction),
        ("Entries (for filter)", len(entries)),
        ("Rows Shown (tail)", len(shown)),
    ])

    headers = ["#", "Tick", "Dir", "Header", "Name", "Size", "Bytes", "Decoded"]
    rows = []
    for i, entry in enumerate(shown):
        # PacketLogEntry (dataclass) — explicit field deref, never repr the struct.
        e_dir = casts.safe(getattr, entry, "direction", default="?")
        header = casts.safe(getattr, entry, "header", default=0)
        size = casts.safe(getattr, entry, "size", default=0)
        data = casts.safe(getattr, entry, "data", default=b"") or b""
        tick = casts.safe(getattr, entry, "tick", default=0)
        name = casts.safe(SNIFFER.get_packet_name, e_dir, header, default="?")
        decoded = casts.safe(SNIFFER.decode_packet, e_dir, header, size, data, default="")
        rows.append((
            base + i,
            tick,
            e_dir,
            casts.hex_of(header, 4),
            name,
            size,
            len(data),
            decoded,
        ))

    return [summary, ui.multi_block("Packet Log", headers, rows)]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Capture control")
    state.action_index = PyImGui.combo("Target Direction", state.action_index, _DIRECTIONS)
    tgt = _action_direction()
    ui.action_button(f"Initialize ({tgt})", SNIFFER.initialize, tgt, key="pkt_init")
    PyImGui.same_line(0, 8)
    ui.action_button(f"Terminate ({tgt})", SNIFFER.terminate, tgt, key="pkt_term")
    PyImGui.same_line(0, 8)
    ui.action_button(f"Clear Logs ({tgt})", SNIFFER.clear_logs, tgt, key="pkt_clear")

    PyImGui.spacing()
    ui.section_header("Log view")
    state.dir_index = PyImGui.combo("Filter Direction", state.dir_index, _DIRECTIONS)
    state.max_rows = PyImGui.input_int("Max Rows (tail)", state.max_rows)
    if state.max_rows < 0:
        state.max_rows = 0


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_packet_view() -> None:
    blocks = build_packet()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("PacketTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
