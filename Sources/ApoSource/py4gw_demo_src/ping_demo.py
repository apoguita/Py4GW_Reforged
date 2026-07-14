"""
Ping / Latency section — native ``PyPing.PingHandler`` stats.

Shape mirrors ``player_demo.py`` (the canonical template):
  * ``build_ping()`` constructs (lazily) a ``PyPing.PingHandler``, reads its four latency
    getters through ``casts.safe`` and returns display Blocks. The handler is a native
    ``Py*`` object — its getters are called explicitly, never repr'd (casts M4 rule).
  * ``draw_ping_view()`` renders those blocks, exposes the handler lifecycle (recreate /
    terminate) as explicit trigger buttons, and offers the per-section Dump button.

Data path: ``PyPing.PingHandler`` (native ``GW::ping::PingTracker``). No wrapper class exists;
the demo constructs the native handler directly (R1 §13).

R2 coverage — PyPing (module 23, single class ``PingHandler``, 6 members):
  Wired: ``__init__`` (handler construction), ``GetCurrentPing``, ``GetAveragePing``,
  ``GetMinPing``, ``GetMaxPing`` (all read into the stats block each frame), ``Terminate``
  (Actions button; recreate re-runs ``__init__`` which re-registers the PING_REPLY callback).
  Skipped: none — all 6 bound members are exercised. The handler exposes no bound data
  members (all private), so there are no struct fields to deref.
"""

import PyImGui

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Ping"

_handler = None
_load_error = ""


class _State:
    pass


state = _State()


# ---------------------------------------------------------------------------
# Native handler lifecycle (lazy — a missing binding degrades gracefully)
# ---------------------------------------------------------------------------
def _get_handler():
    global _handler, _load_error
    if _handler is None and not _load_error:
        try:
            import PyPing  # embedded module — only present in-client

            _handler = PyPing.PingHandler()
        except Exception as e:  # noqa: BLE001 - surface the error, keep the widget alive
            _load_error = f"{type(e).__name__}: {e}"
    return _handler


def _recreate_handler():
    """Terminate the current tracker (if any) and construct a fresh one."""
    global _handler, _load_error
    if _handler is not None:
        try:
            _handler.Terminate()
        except Exception:  # noqa: BLE001
            pass
    _handler = None
    _load_error = ""
    return _get_handler() is not None


def _terminate_handler():
    global _handler
    if _handler is not None:
        _handler.Terminate()
        _handler = None
    return True


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def build_ping():
    handler = _get_handler()
    if handler is None:
        return [ui.kv_block("Ping / Latency", [("Status", f"PyPing unavailable — {_load_error}")])]
    rows = [
        ("Current Ping (ms)", casts.safe(handler.GetCurrentPing)),
        ("Average Ping (ms)", casts.safe(handler.GetAveragePing)),
        ("Min Ping (ms)", casts.safe(handler.GetMinPing)),
        ("Max Ping (ms)", casts.safe(handler.GetMaxPing)),
    ]
    return [ui.kv_block("Ping / Latency (PyPing.PingHandler)", rows)]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("Handler lifecycle")
    ui.text_muted(
        "Latency getters are polled live in the Data tab. Recreate re-runs the ctor, "
        "which re-registers the PING_REPLY callback and resets the rolling history."
    )
    ui.action_button("Recreate Handler", _recreate_handler, key="ping_recreate")
    PyImGui.same_line(0, 8)
    ui.action_button("Terminate Handler", _terminate_handler, key="ping_terminate")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_ping_view() -> None:
    blocks = build_ping()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("PingTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
