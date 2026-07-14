"""
Profiler section — native ``PyProfiler`` performance counters (metric names, per-metric reports,
sample history + manual start/end timing and reset).

Shape mirrors ``player_demo`` exactly:
  * ``build_profiler()`` calls the module free functions, CASTS each value (report percentiles ->
    ``casts.f3``) and returns display Blocks. Reports are plain 7-tuples (not structs); each field is
    dereferenced by position, never repr'd whole.
  * ``draw_profiler_view()`` exposes reset + manual start/end timing as explicit trigger buttons.

Data path: native ``PyProfiler`` module — module-level free functions only (no bound class /
handle), so there is no handle to instantiate and ``handle_rows`` does not apply here. Report row =
(name, min, avg, p50, p95, p99, max).

R2 coverage — PyProfiler (6/6):
  Data getters wired: get_metric_names, get_reports, get_history.
  Actions wired: reset, start, end.
  Skipped: none.
"""

import PyImGui
import PyProfiler

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Profiler"


class _State:
    metric_index: int = 0
    metric_name: str = ""
    timing_name: str = "demo_metric"


state = _State()


def _metric_names() -> "list[str]":
    names = casts.safe(PyProfiler.get_metric_names, default=[]) or []
    return [str(n) for n in names]


def _selected_metric() -> str:
    """Free-text field wins when set; otherwise the combo selection."""
    if state.metric_name:
        return state.metric_name
    names = _metric_names()
    if names and 0 <= state.metric_index < len(names):
        return names[state.metric_index]
    return ""


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _metric_names_block():
    names = _metric_names()
    rows = [(i, name) for i, name in enumerate(names)]
    return ui.multi_block(f"Metric Names ({len(rows)})", ["#", "Name"], rows)


def _reports_block():
    reports = casts.safe(PyProfiler.get_reports, default=[]) or []
    headers = ["Name", "Min", "Avg", "P50", "P95", "P99", "Max"]
    rows = []
    for report in reports:
        try:
            name, mn, avg, p50, p95, p99, mx = report
        except (TypeError, ValueError):
            rows.append((str(report), "", "", "", "", "", ""))
            continue
        rows.append(
            (
                str(name),
                casts.f3(mn),
                casts.f3(avg),
                casts.f3(p50),
                casts.f3(p95),
                casts.f3(p99),
                casts.f3(mx),
            )
        )
    return ui.multi_block(f"Reports ({len(rows)})", headers, rows)


def _history_block():
    metric = _selected_metric()
    if not metric:
        return ui.kv_block("Sample History", [("Selected Metric", "<none>")])
    history = casts.safe(PyProfiler.get_history, metric, default=[]) or []
    rows = [(i, casts.f3(v)) for i, v in enumerate(history)]
    return ui.multi_block(f"Sample History — '{metric}' ({len(rows)})", ["#", "Value"], rows)


def build_profiler():
    return [_metric_names_block(), _reports_block(), _history_block()]


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _draw_actions():
    ui.section_header("History selection")
    names = _metric_names()
    if names:
        PyImGui.push_item_width(240)
        state.metric_index = PyImGui.combo("Metric", state.metric_index, names)
        PyImGui.pop_item_width()
    else:
        ui.text_muted("No metrics reported by get_metric_names().")
    state.metric_name = PyImGui.input_text("Metric name (overrides combo when set)", state.metric_name)
    ui.text_muted(f"Selected: {_selected_metric() or '<none>'}")

    PyImGui.spacing()
    ui.section_header("Manual timing")
    state.timing_name = PyImGui.input_text("Timing metric name", state.timing_name)
    ui.action_button("Start", PyProfiler.start, state.timing_name, key="prof_start")
    PyImGui.same_line(0, 8)
    ui.action_button("End", PyProfiler.end, state.timing_name, key="prof_end")

    PyImGui.spacing()
    ui.section_header("Reset")
    ui.action_button("Reset (clear all history)", PyProfiler.reset, key="prof_reset")


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_profiler_view() -> None:
    blocks = build_profiler()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("ProfilerTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
