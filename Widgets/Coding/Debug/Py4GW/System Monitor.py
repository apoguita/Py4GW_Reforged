from typing import Any

import PyImGui
import PyProfiler
from Py4GWCoreLib import UIManager, ThrottledTimer, Color, ColorPalette, ImGui
from Py4GWCoreLib import ProfilingRegistry, SimpleProfiler, WidgetHandler

MODULE_NAME = "System Monitor"
MODULE_ICON = "Assets/Textures/Module_Icons/Monitor Diagnostic.png"
MODULE_CATEGORY = "Coding"
MODULE_TAGS = ["performance", "profiler", "fps", "frametime", "flame graph", "monitor", "debug"]
# Replaces the legacy "System Monitor" and "Widget Profiler" -- keep both as aliases
# so searches for the old names still find this widget.
MODULE_ALIASES = ["Widget Profiler", "System Monitor UI"]
OPTIONAL = True


class SystemInfo:
    target_fps: int = 0        # configured frame limit (0 = unlimited)
    fps: float = 0.0           # actual frames per second (smoothed)
    ms_per_frame: float = 0.0  # actual time for one whole frame
    ms_used: float = 0.0       # time all scripts / widgets consume per frame
    widgets: list[tuple[str, float]] = []  # (widget, ms) per widget, sorted desc
    bar_labels: list[str] = []             # cached stacked-bar segment labels
    bar_values: list[float] = []           # cached stacked-bar segment values (ms)
    widget_colors: dict[str, Color] = {}   # widget name -> its stacked-bar segment Color

#tells if the widget has been initialized or not, so we can avoid reinitializing it every frame
initialized = False

system_info = SystemInfo()

# Which metric the view focuses on: 0 = whole frame, 1 = scripts only.
selected_view: int = 1

# Widget whose detail window is open ("" = none). Set by clicking a bar segment
# or a table row; both feed this one value, so both open the same window.
selected_widget: str = ""

# get_reports() recomputes percentiles for every tracked metric, so only sample
# that heavier total on a throttle; fps / frame-time are cheap and stay live.
_usage_timer = ThrottledTimer(1000)

# Palette colors resolved ONCE at import. ColorPalette.GetColor() rebuilds a
# ~95-entry lookup map on every call (and allocates a tuple), so calling it per
# frame -- as the header colors did -- is the main reason this window cost more
# than the original, which caches every palette lookup. Resolve the fixed set once.
_COL_GREEN = ColorPalette.GetColor("GWGreen").to_tuple_normalized()
_COL_GOLD = ColorPalette.GetColor("Gold").to_tuple_normalized()
_COL_RED = ColorPalette.GetColor("Red").to_tuple_normalized()
_COL_DARKRED = ColorPalette.GetColor("DarkRed").to_tuple_normalized()
_COL_DARKCYAN = ColorPalette.GetColor("DarkCyan").to_tuple_normalized()
_TRACK_COLOR = ColorPalette.GetColor("GwDisabled")  # progress-bar track (Color proxy)
_SEL_HEADER = ColorPalette.GetColor("DodgerBlue").opacity(0.55).to_tuple_normalized()        # selected row
_SEL_HEADER_HOVER = ColorPalette.GetColor("DodgerBlue").opacity(0.30).to_tuple_normalized()  # hovered row

# Phase colors for the detail window (Draw / Main / Update), matching the mockup.
_PHASE_COLORS = {
    "Draw": ColorPalette.GetColor("DodgerBlue").to_tuple_normalized(),
    "Main": ColorPalette.GetColor("Gold").to_tuple_normalized(),
    "Update": ColorPalette.GetColor("LightGreen").to_tuple_normalized(),
}

# Detail window: cache the selected widget's metrics. get_reports() recomputes
# percentiles for every metric in C++, so never call it per frame while the
# window is open -- rebuild only when the selection changes or on this throttle.
_detail_timer = ThrottledTimer(500)
_detail_widget: str = ""
_detail_metrics: list[tuple[str, float, float, float]] = []
_detail_total: float = 0.0
_detail_phase_totals: dict[str, float] = {"Draw": 0.0, "Main": 0.0, "Update": 0.0}
_detail_history: list[float] = []      # dominant metric's sample history (sparkline)
_detail_spark_label: str = ""          # raw name of the metric shown in the sparkline

# On-demand deep profile (ported from Widget Profiler): a cProfile capture of one
# widget's callbacks over N frames, rendered as an ImPlot flame graph. Only works
# for real WidgetManager widgets (keyed by folder_script_name, which equals the
# entry name); native subsystem entries have no cProfile path.
_PROFILE_DURATION = 120  # default capture length (frames); user-adjustable at runtime
_PROFILE_PHASES = ("update", "draw", "main")
_FLAME_MAX_DEPTH = 10
_FLAME_MIN_FRAC = 0.004  # skip cells narrower than 0.4% of the current view

_profile_frames: int = _PROFILE_DURATION  # frames the NEXT capture will run (input field)
_prof_active: Any = None                  # SimpleProfiler while a capture runs, else None
_prof_target: str = ""                    # widget being captured
_prof_frames_left: int = 0
_prof_total: int = _PROFILE_DURATION      # frames the RUNNING capture will process

_flame_widget: str = ""    # widget the current flame result is for
_flame_error: str = ""     # non-empty -> show this message instead of a graph
_flame_stats: dict = {}    # func_key -> (cc, nc, self_ns, cum_ns, callers)
_flame_names: dict = {}    # func_key -> display name
_flame_callees: dict = {}  # func_key -> [(callee_key, edge_cum, edge_count)]
_flame_roots: list = []    # [(func_key, cum_ns)] top-level, sorted desc
_flame_zoom = None         # zoomed func_key, or None for the roots
_flame_cells: list = []    # laid-out cells: (key, x0, x1, depth, self_ms, cum_ms, edge_calls, cidx)
_flame_depth: int = 0
_flame_frames: int = _PROFILE_DURATION  # frames the CURRENT flame result was captured over
_flame_hovered = None      # func_key hovered last frame (highlights all its cells)
_FLAME_HL = (1.0, 1.0, 1.0, 1.0)  # white highlight border

# Flame cell colors: a cohesive cold ramp (deep violet-blue -> teal -> sky),
# all resolved from ColorPalette once, then hashed per func key for variety.
_FLAME_PALETTE = [
    ColorPalette.GetColor(_n).to_tuple_normalized()
    for _n in ("MidnightViolet", "DarkBlue", "SlateBlue", "DodgerBlue", "Teal", "DarkCyan", "Turquoise", "SkyBlue")
]


def _refresh_usage() -> tuple[list[tuple[str, float]], float]:
    """Group profiler metrics into per-widget totals + the overall total (ms).

    The callback scheduler names each metric "<Context>.Callback.<Phase>.<widget>",
    so splitting on '.' (max 3 times) isolates the widget/callback name; a widget's
    Draw/Main/Update phases are summed into one number. Metrics that are not
    callbacks keep their raw name. Each metric is a leaf, so the averages add up to
    the total with no double counting.
    """
    # Widgets that are no longer enabled still return stale samples for up to the
    # native window (~60s), so exclude them here -- otherwise a just-closed widget
    # keeps polluting the totals/table. Native subsystem metrics (not widgets) are
    # always kept.
    known = WidgetHandler().widgets
    per_widget: dict[str, float] = {}
    total = 0.0
    for report in PyProfiler.get_reports():
        # report = (name, min, avg, p50, p95, p99, max)  -- all milliseconds
        name = report[0]
        avg = report[2]
        parts = name.split(".", 3)
        is_callback = len(parts) == 4 and parts[1] == "Callback"
        widget = parts[3] if is_callback else name
        if is_callback and widget in known and not known[widget].enabled:
            continue  # closed / disabled widget -> stale data, drop it
        total += avg
        per_widget[widget] = per_widget.get(widget, 0.0) + avg
    rows = sorted(per_widget.items(), key=lambda kv: kv[1], reverse=True)
    return rows, total


def _rebuild_bar_cache() -> None:
    """Precompute the stacked-bar segments once per data refresh (top 10 + others).

    draw() runs every frame but system_info.widgets only changes on the 1s throttle,
    so the grouping is done here, not in the hot path.
    """
    rows = system_info.widgets
    labels = [name for name, _ms in rows[:10]]
    values = [ms for _name, ms in rows[:10]]
    others = sum(ms for _name, ms in rows[10:])
    if others > 0.0:
        labels.append("others")
        values.append(others)
    system_info.bar_labels = labels
    system_info.bar_values = values


def _rebuild_detail(widget: str) -> None:
    """Rebuild every cached field for the widget detail window (throttled).

    Groups the widget's metrics into: a per-phase (Draw/Main/Update) avg total for
    the breakdown bars, the full (label, avg, p95, max) list for the table, and the
    heaviest single metric's sample history for the sparkline.
    """
    global _detail_metrics, _detail_total, _detail_phase_totals
    global _detail_history, _detail_spark_label

    metrics: list[tuple[str, float, float, float]] = []
    phase_totals = {"Draw": 0.0, "Main": 0.0, "Update": 0.0}
    total = 0.0
    dominant_raw = ""
    dominant_avg = -1.0
    for report in PyProfiler.get_reports():
        nm = report[0]
        parts = nm.split(".", 3)
        is_callback = len(parts) == 4 and parts[1] == "Callback"
        wname = parts[3] if is_callback else nm
        if wname != widget:
            continue
        avg = report[2]
        total += avg
        context = parts[0] if is_callback else ""
        if context in phase_totals:
            phase_totals[context] += avg
        label = f"{parts[0]}.{parts[2]}" if is_callback else nm  # e.g. "Draw.Update"
        metrics.append((label, avg, report[4], report[6]))
        if avg > dominant_avg:
            dominant_avg = avg
            dominant_raw = nm
    metrics.sort(key=lambda m: m[1], reverse=True)

    _detail_metrics = metrics
    _detail_total = total
    _detail_phase_totals = phase_totals
    _detail_spark_label = dominant_raw
    hist = [float(v) for v in PyProfiler.get_history(dominant_raw)] if dominant_raw else []
    # Native samples once per 6 frames, so the 600-sample buffer spans ~60s only at
    # 60 fps (longer at lower fps). Trim to the last 60 s by the current cadence so
    # the sparkline is always a 60-second window.
    if system_info.fps > 0.0 and hist:
        n60 = max(2, int(system_info.fps * 60.0 / 6.0))
        hist = hist[-n60:]
    _detail_history = hist


def update() -> None:
    global _prof_frames_left, system_info, initialized

    # Deep-profile countdown (runs every tick, outside the usage throttle).
    if _prof_active is not None:
        _prof_frames_left -= 1
        if _prof_frames_left <= 0:
            _finish_profile()

    if system_info.target_fps == 0:
        system_info.target_fps = UIManager.GetFPSLimit()

    if _usage_timer.IsExpired() or not initialized:
        io = PyImGui.get_io()
        fps = io.framerate
        system_info.fps = fps
        system_info.ms_per_frame = (1000.0 / fps) if fps > 0.0 else 0.0

        system_info.widgets, system_info.ms_used = _refresh_usage()
        _rebuild_bar_cache()
        _usage_timer.Reset()
        initialized = True


def _fps_color(fps: float) -> tuple:
    """Palette color for an fps reading (cached constants, no per-frame lookup).

    green > 58 | yellow 55-58 | red 50-54 | dark red below 50.
    """
    if fps > 58.0:
        return _COL_GREEN
    if fps > 54.0:
        return _COL_GOLD
    if fps > 49.0:
        return _COL_RED
    return _COL_DARKRED


def _total_time_color(pct: float) -> tuple:
    """Palette color for the used-% figure (cached constants)."""
    if pct <= 25.0:
        return _COL_GREEN
    if pct <= 50.0:
        return _COL_GOLD
    if pct <= 75.0:
        return _COL_RED
    return _COL_DARKRED


def _draw_usage_bar(axis_max: float) -> str | None:
    """A stacked horizontal share bar drawn with ImPlot (PlotBarGroups).

    Segments come from the cached bar data (rebuilt once per data refresh), so this
    only lays them out + hit-tests -- no per-frame grouping. `axis_max` sets the X
    range: the whole-frame budget (leaves headroom) or the total widget time (fills
    100%). Returns the widget name whose segment was clicked this frame (or None);
    hovering a segment shows a tooltip.
    """
    labels = system_info.bar_labels
    values = system_info.bar_values
    if not labels or axis_max <= 0.0:
        return None
    implot = PyImGui.implot

    clicked: str | None = None
    # Decoration-free bar. Inputs stay enabled so hover works; the Cond_Always
    # limits below re-lock the view every frame, so pan/zoom can't drift.
    if implot.begin_plot("##usage_share", 340.0, 42.0, implot.Flags_CanvasOnly):
        no_dec = implot.AxisFlags_NoDecorations
        implot.setup_axes(None, None, no_dec, no_dec)
        implot.setup_axis_limits(implot.X1, 0.0, axis_max, implot.Cond_Always)
        implot.setup_axis_limits(implot.Y1, -0.5, 0.5, implot.Cond_Always)
        spec = implot.make_spec(flags=implot.BarGroupsFlags_Stacked | implot.BarGroupsFlags_Horizontal)
        implot.plot_bar_groups(labels, values, len(values), 1, 1.0, 0.0, spec)

        # Capture each segment's colormap color, keyed by widget name, so the table
        # rows can tint their progress bars with the same per-widget color. Queried
        # inside the plot (same colormap the bar just used), so it matches exactly.
        # Color proxies each colormap value (a list from the binding) into the
        # codebase's Color type; to_tuple_normalized() then yields a real tuple,
        # which push_style_color accepts (a raw list does not).
        seg_colors: dict[str, Color] = {}
        for idx, seg_lbl in enumerate(labels):
            seg_colors[seg_lbl] = Color.from_tuple_normalized(implot.get_colormap_color(idx))
        system_info.widget_colors = seg_colors

        # Resolve the hovered segment from the mouse x (in plot coordinates).
        if implot.is_plot_hovered():
            mouse_x = implot.get_plot_mouse_pos().x
            acc = 0.0
            for lbl, val in zip(labels, values):
                if acc <= mouse_x < acc + val:
                    share = (val / axis_max * 100.0) if axis_max > 0.0 else 0.0
                    PyImGui.set_tooltip(f"{lbl}\n{val:.3f} ms  ({share:.1f}%)")
                    if PyImGui.is_mouse_clicked(0):
                        clicked = lbl
                    break
                acc += val
        implot.end_plot()
    return clicked


def _draw_sparkline(id_str: str, values: list[float], height: float, line_col: tuple) -> None:
    """A filled ImPlot sparkline: a line over a shaded area, y-range pinned to data."""
    if len(values) < 2:
        return
    implot = PyImGui.implot
    vmin = min(values)
    vmax = max(values)
    if vmax <= vmin:
        vmax = vmin + 1e-6
    pad = (vmax - vmin) * 0.1
    if implot.begin_plot(id_str, -1.0, height, implot.Flags_CanvasOnly | implot.Flags_NoInputs):
        no_dec = implot.AxisFlags_NoDecorations
        implot.setup_axes(None, None, no_dec, no_dec)
        implot.setup_axis_limits(implot.X1, 0.0, float(len(values) - 1), implot.Cond_Always)
        implot.setup_axis_limits(implot.Y1, vmin - pad, vmax + pad, implot.Cond_Always)
        implot.plot_shaded("##fill", values, vmin - pad, 1.0, 0.0,
                           implot.make_spec(fill_col=line_col, fill_alpha=0.18))
        implot.plot_line("##line", values, 1.0, 0.0,
                         implot.make_spec(line_col=line_col, line_weight=1.6))
        implot.end_plot()


# ── deep profile: capture + ImPlot flame graph ────────────────────────────────

def _func_display_name(filename: str, funcname: str) -> str:
    if filename == '~':
        return funcname
    base = filename.rsplit('\\', 1)[-1].rsplit('/', 1)[-1]
    if base.endswith('.py'):
        base = base[:-3]
    return f"{base}.{funcname}"


def _start_profile(widget: str) -> None:
    """Begin a cProfile capture of `widget`'s callbacks (update/draw/main).

    Enables the ProfilingRegistry and registers one SimpleProfiler for each phase
    key so the widget loop routes those callbacks through it. No-op with an error
    message if the entry is not a real WidgetManager widget.
    """
    global _prof_active, _prof_target, _prof_frames_left, _prof_total
    global _flame_widget, _flame_cells, _flame_error, _flame_zoom
    _flame_zoom = None
    if not ProfilingRegistry().is_registered(widget):
        _flame_widget = widget
        _flame_cells = []
        _flame_error = "Not registered for profiling - no cProfile capture available."
        return
    reg = ProfilingRegistry()
    prof = SimpleProfiler()
    reg.enabled = True
    for phase in _PROFILE_PHASES:
        reg.cprofile_targets[f"{widget}:{phase}"] = prof  # type: ignore[assignment]
    _prof_total = max(1, _profile_frames)
    _prof_active = prof
    _prof_target = widget
    _prof_frames_left = _prof_total
    _flame_error = ""


def _finish_profile() -> None:
    """Stop the capture and convert the SimpleProfiler data into flame-graph state."""
    global _prof_active, _prof_frames_left, _flame_frames
    global _flame_stats, _flame_names, _flame_callees, _flame_roots, _flame_widget, _flame_error

    reg = ProfilingRegistry()
    prof = _prof_active
    wid = _prof_target
    _prof_active = None
    _prof_frames_left = 0
    for phase in _PROFILE_PHASES:
        reg.cprofile_targets.pop(f"{wid}:{phase}", None)
    if not reg.cprofile_targets:
        reg.enabled = False
    if prof is None:
        return

    # stats: {key: [nc, self_ns, cum_ns]} -> all_stats[key] = (cc, nc, self, cum, callers)
    all_stats: dict = {}
    for key, (nc, self_ns, cum_ns) in prof.stats.items():
        callers = {ck: tuple(cv) for ck, cv in prof.callers.get(key, {}).items()}
        all_stats[key] = (nc, nc, self_ns, cum_ns, callers)

    names: dict = {k: _func_display_name(k[0], k[2]) for k in all_stats}

    # callees: parent -> [(callee, edge_cum, edge_count)] in first-seen call order
    callees: dict = {}
    children_set: set = set()
    edge_seq = prof.edge_order
    for func_key, (cc, nc, tt, ct, callers) in all_stats.items():
        for caller_key, (edge_count, edge_cum) in callers.items():
            callees.setdefault(caller_key, []).append((func_key, edge_cum, edge_count))
            children_set.add(func_key)
    for k in callees:
        callees[k].sort(key=lambda c: edge_seq.get((k, c[0]), 0))

    # roots = the widget's own top-level functions (promoted from infra/ghost parents)
    _INFRA_BASES = {'Profiling.py', 'WidgetManager.py', 'traceback.py', 'System Monitor.py'}
    w = WidgetHandler().widgets.get(wid)
    widget_script = w.script_path.replace("/", "\\") if w else ""
    seen_roots: set = set()
    widget_roots: list = []

    def _is_infra(k) -> bool:
        if k[0] in ('~', '<string>'):
            return True
        base = k[0].rsplit('\\', 1)[-1].rsplit('/', 1)[-1]
        return base in _INFRA_BASES

    infra_parents = set(callees.keys()) - set(all_stats.keys())
    for k in all_stats:
        if _is_infra(k) and k in callees:
            infra_parents.add(k)
    for parent_key in infra_parents:
        for callee_key, _edge_ct, _edge_n in callees[parent_key]:
            if callee_key in seen_roots or _is_infra(callee_key):
                continue
            if callee_key[0].replace("/", "\\") == widget_script:
                widget_roots.append((callee_key, all_stats[callee_key][3]))
                seen_roots.add(callee_key)
    for k in all_stats:
        if k in children_set or k in seen_roots or _is_infra(k):
            continue
        widget_roots.append((k, all_stats[k][3]))
        seen_roots.add(k)
    widget_roots.sort(key=lambda r: r[1], reverse=True)

    _flame_stats = all_stats
    _flame_names = names
    _flame_callees = callees
    _flame_roots = widget_roots
    _flame_widget = wid
    _flame_frames = _prof_total
    _flame_error = "" if widget_roots else "No call data captured (widget did not run a profiled phase)."
    _build_flame_cells()


def _build_flame_cells() -> None:
    """Lay the captured call graph out as flame cells in normalized x (0..1) and
    integer depth, honouring the current zoom. ImPlot maps these to pixels, so the
    layout is resolution-independent (no pixel math, unlike the draw-list icicle)."""
    global _flame_cells, _flame_depth
    raw = _flame_stats
    callees = _flame_callees
    frames = _flame_frames

    if _flame_zoom is not None and _flame_zoom in raw:
        top = [(_flame_zoom, raw[_flame_zoom][3])]
    else:
        top = _flame_roots
    total_ct = sum(ct for _, ct in top) or 1.0

    cells: list = []
    # level items: (key, x0, x1, edge_calls, parent_cidx, prev_sib_cidx)
    current: list = []
    x = 0.0
    prev_sib = -1
    for key, ct in top:
        w = ct / total_ct
        if w >= _FLAME_MIN_FRAC:
            nc_root = raw[key][1] if key in raw else 0
            current.append((key, x, x + w, nc_root, -1, prev_sib))
            prev_sib = _flame_color_idx(key, -1, prev_sib)
        x += w

    max_depth = 0
    for depth in range(_FLAME_MAX_DEPTH):
        if not current:
            break
        max_depth = depth + 1
        nxt: list = []
        for key, x0, x1, edge_calls, parent_cidx, prev_sib_cidx in current:
            entry = raw.get(key)
            if entry is None:
                continue
            _cc, _nc, tt, ct, _callers = entry
            cidx = _flame_color_idx(key, parent_cidx, prev_sib_cidx)
            cells.append((key, x0, x1, depth, tt / frames / 1_000_000, ct / frames / 1_000_000, edge_calls, cidx))
            kids = callees.get(key)
            if not kids or ct <= 0:
                continue
            span = x1 - x0
            cx = x0
            child_prev_sib = -1
            for callee_key, edge_ct, edge_n in kids:
                cw = (edge_ct / ct) * span
                if cw >= _FLAME_MIN_FRAC:
                    nxt.append((callee_key, cx, cx + cw, edge_n, cidx, child_prev_sib))
                    child_prev_sib = _flame_color_idx(callee_key, cidx, child_prev_sib)
                cx += cw
        current = nxt

    _flame_cells = cells
    _flame_depth = max_depth


def _flame_color_idx(key, parent_idx: int, prev_sib_idx: int) -> int:
    """Palette index for a cell, shifted so it avoids its parent's and previous
    sibling's colors -- keeps adjacent cells distinguishable (as the original did)."""
    n = len(_FLAME_PALETTE)
    idx = hash(key) % n
    avoid = {parent_idx, prev_sib_idx}
    while idx in avoid:
        idx = (idx + 1) % n
    return idx


def _print_flame_summary() -> None:
    """Dump the captured profile to the console (parity with the original)."""
    frames = _flame_frames
    print(f"=== System Monitor: Deep Profile for {_flame_widget} ===")
    print(f"FramesCaptured={frames} RootCount={len(_flame_roots)} Zoomed={'yes' if _flame_zoom is not None else 'no'}")
    if _flame_roots:
        print("Top roots by cumulative/frame:")
        for root_key, ct in _flame_roots[:10]:
            print(f"  - {_flame_names.get(root_key, str(root_key))}: cum={ct / frames / 1_000_000:.3f}ms/frame")
    sorted_funcs = sorted(_flame_stats.items(), key=lambda it: it[1][3], reverse=True)
    print("Top functions by cumulative/frame:")
    for func_key, (_cc, nc, tt, ct, _callers) in sorted_funcs[:25]:
        print(f"  - {_flame_names.get(func_key, str(func_key))}: "
              f"self={tt / frames / 1_000_000:.3f}ms/frame cum={ct / frames / 1_000_000:.3f}ms/frame "
              f"calls/frame={nc / frames:.2f}")


def _draw_flame() -> None:
    """Render the flame cells with ImPlot: filled rects + labels, hover tooltip
    (self / cum / calls-per-frame), same-function highlight, click-to-zoom, zoom-out
    and a console Print Summary -- the original icicle's feature set."""
    global _flame_zoom, _flame_hovered
    if not _flame_cells:
        PyImGui.text("No call data captured.")
        return
    implot = PyImGui.implot
    frames = _flame_frames
    depth = max(_flame_depth, 1)
    prev_hovered = _flame_hovered

    # toolbar: zoom-out (when zoomed) + print summary + caption
    if _flame_zoom is not None:
        if PyImGui.small_button("Zoom Out"):
            _flame_zoom = None
            _build_flame_cells()
        PyImGui.same_line(0, 8)
    if PyImGui.small_button("Print Summary"):
        _print_flame_summary()
    PyImGui.same_line(0, 8)
    PyImGui.text(f"{len(_flame_roots)} roots - {frames} frames - click to zoom")

    height = min(640.0, max(70.0, depth * 32.0))
    clicked_key = None
    new_hovered = None
    if implot.begin_plot("##flame", 600.0, height, implot.Flags_CanvasOnly | implot.Flags_NoLegend):
        no_dec = implot.AxisFlags_NoDecorations
        implot.setup_axes(None, None, no_dec, no_dec | implot.AxisFlags_Invert)
        implot.setup_axis_limits(implot.X1, 0.0, 1.0, implot.Cond_Always)
        implot.setup_axis_limits(implot.Y1, 0.0, float(depth), implot.Cond_Always)

        for i, cell in enumerate(_flame_cells):
            key, x0, x1, d, _self_ms, _cum_ms, _edge_calls, cidx = cell
            is_hl = prev_hovered is not None and key == prev_hovered
            spec = implot.make_spec(fill_col=_FLAME_PALETTE[cidx], fill_alpha=1.0 if is_hl else 0.95,
                                    flags=implot.ItemFlags_NoLegend | implot.ItemFlags_NoFit)
            implot.plot_shaded_between(f"##fc{i}", [float(x0), float(x1)],
                                       [float(d), float(d)], [float(d) + 1.0, float(d) + 1.0], spec)
            if is_hl:  # white outline on every cell of the hovered function
                border = implot.make_spec(line_col=_FLAME_HL, line_weight=2.0,
                                          flags=implot.LineFlags_Loop | implot.ItemFlags_NoLegend | implot.ItemFlags_NoFit)
                implot.plot_line_xy(f"##hl{i}", [float(x0), float(x1), float(x1), float(x0)],
                                    [float(d), float(d), float(d) + 1.0, float(d) + 1.0], border)
            width = x1 - x0
            if width > 0.05:
                label = _flame_names.get(key, "?")
                implot.plot_text(label[:int(width / 0.012)], (x0 + x1) * 0.5, d + 0.5)

        if implot.is_plot_hovered():
            mp = implot.get_plot_mouse_pos()
            mx, my = mp.x, mp.y
            for cell in _flame_cells:
                key, x0, x1, d, self_ms, cum_ms, edge_calls, _cidx = cell
                if x0 <= mx < x1 and d <= my < d + 1:
                    new_hovered = key
                    nc = _flame_stats[key][1] if key in _flame_stats else edge_calls
                    tip = (f"{_flame_names.get(key, '?')}\n"
                           f"self {self_ms:.3f} ms  |  cum {cum_ms:.3f} ms\n"
                           f"{edge_calls / frames:.1f} calls/frame")
                    if nc != edge_calls:
                        tip += f"  ({nc / frames:.1f} from all callers)"
                    PyImGui.set_tooltip(tip)
                    if PyImGui.is_mouse_clicked(0):
                        clicked_key = key
                    break
        implot.end_plot()

    _flame_hovered = new_hovered
    if clicked_key is not None:
        _flame_zoom = clicked_key
        _build_flame_cells()


def _analyzable_reason(name: str) -> str:
    """Return '' if the entry can be deep-profiled, else why not.

    An entry is profilable only if its runner wraps the call through the profiling
    registry (runcall_scope) and declared itself via ProfilingRegistry.register().
    At startup that's the widgets; non-widget callbacks that add the same wrapper
    register too. Native callbacks that don't register can't produce a call graph.
    """
    if not ProfilingRegistry().is_registered(name):
        return "Not registered for profiling - no cProfile call graph available."
    return ""


def _frames_input() -> None:
    """Compact input to set how many frames the next capture will process."""
    global _profile_frames
    PyImGui.set_next_item_width(80)
    _profile_frames = min(5000, max(10, PyImGui.input_int("frames", _profile_frames, 10, 60, 0)))


def _draw_widget_window() -> None:
    """Shared detail popup for the selected widget: its per-phase metric breakdown.

    Opened by clicking a bar segment or a table row (both set `selected_widget`).
    The per-metric numbers come from a cache rebuilt only when the selection changes
    or the detail throttle expires -- get_reports() is too heavy to call per frame.
    Placeholder content -- swap for whatever the detail view should really show.
    """
    global selected_widget, _detail_widget
    if not selected_widget:
        return

    PyImGui.set_next_window_size((460, 520), PyImGui.ImGuiCond.FirstUseEver)
    flags = PyImGui.WindowFlags.NoCollapse | PyImGui.WindowFlags.AlwaysAutoResize
    visible, still_open = PyImGui.begin_with_close(f"{selected_widget}##widget_detail", True, flags)
    if not still_open:
        selected_widget = ""

    if visible:
        if selected_widget != _detail_widget or _detail_timer.IsExpired():
            _detail_widget = selected_widget
            _rebuild_detail(selected_widget)
            _detail_timer.Reset()

        wcolor = system_info.widget_colors.get(selected_widget)
        spark_col = wcolor.to_tuple_normalized() if wcolor is not None else _PHASE_COLORS["Draw"]

        # summary line
        of_frame = (_detail_total / system_info.ms_per_frame * 100.0) if system_info.ms_per_frame > 0.0 else 0.0
        PyImGui.text(f"{_detail_total:.3f} ms / frame")
        PyImGui.same_line(0, 8)
        PyImGui.text(f"{of_frame:.1f}% of frame  |  {len(_detail_metrics)} metrics")
        PyImGui.separator()
        # ── history sparkline of the heaviest metric ──
        PyImGui.text("HISTORY")
        if len(_detail_history) >= 2:
            sp = _detail_spark_label.split(".", 3)
            spark_name = f"{sp[0]}.{sp[2]}" if len(sp) == 4 else _detail_spark_label
            PyImGui.text(spark_name)
            PyImGui.same_line(0, 8)
            PyImGui.text(f"min {min(_detail_history):.3f} - max {max(_detail_history):.3f}")
            _draw_sparkline("##spark", _detail_history, 58.0, spark_col)
        else:
            PyImGui.text("No history samples yet.")
        PyImGui.spacing()
        PyImGui.separator()

        # ── full metrics table ──
        PyImGui.text("METRICS")
        flags = int(PyImGui.TableFlags.RowBg | PyImGui.TableFlags.Borders | PyImGui.TableFlags.SizingStretchProp)
        if PyImGui.begin_table("widget_metrics", 4, flags):
            PyImGui.table_setup_column("phase")
            PyImGui.table_setup_column("avg")
            PyImGui.table_setup_column("p95")
            PyImGui.table_setup_column("max")
            PyImGui.table_headers_row()
            for label, avg, p95, mx in _detail_metrics:
                PyImGui.table_next_row()
                PyImGui.table_set_column_index(0)
                PyImGui.text(label)
                PyImGui.table_set_column_index(1)
                PyImGui.text(f"{avg:.3f}")
                PyImGui.table_set_column_index(2)
                PyImGui.text(f"{p95:.3f}")
                PyImGui.table_set_column_index(3)
                PyImGui.text(f"{mx:.3f}")
            PyImGui.end_table()
        PyImGui.spacing()
        PyImGui.separator()

        # ── detailed profile: on-demand cProfile capture -> ImPlot flame graph ──
        PyImGui.text("DETAILED PROFILE")
        if _prof_active is not None and _prof_target == selected_widget:
            done = _prof_total - _prof_frames_left
            PyImGui.push_style_color(PyImGui.ImGuiCol.PlotHistogram, _PHASE_COLORS["Main"])
            PyImGui.push_style_color(PyImGui.ImGuiCol.FrameBg, _TRACK_COLOR.to_tuple_normalized())
            PyImGui.progress_bar(done / _prof_total if _prof_total else 0.0, -1.0, 0.0, f"capturing {done}/{_prof_total}")
            PyImGui.pop_style_color(2)
        elif _prof_active is not None:
            PyImGui.text(f"Busy capturing {_prof_target}...")
        elif _flame_widget == selected_widget and _flame_error:
            PyImGui.text(_flame_error)
            if PyImGui.button("Run Detailed Profile"):
                _start_profile(selected_widget)
            PyImGui.same_line(0, 8)
            _frames_input()
        elif _flame_widget == selected_widget and _flame_cells:
            if PyImGui.button("Re-run"):
                _start_profile(selected_widget)
            PyImGui.same_line(0, 8)
            _frames_input()
            _draw_flame()
        else:
            reason = _analyzable_reason(selected_widget)
            if reason:
                PyImGui.text(reason)
            else:
                if PyImGui.button("Run Detailed Profile"):
                    _start_profile(selected_widget)
                PyImGui.same_line(0, 8)
                _frames_input()

    PyImGui.end()


def tooltip() -> None:
    """Hover tooltip shown by the widget manager / launchpad."""
    PyImGui.begin_tooltip()
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored("System Monitor", Color(255, 200, 100, 255).to_tuple_normalized())
    ImGui.pop_font()
    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.text("Live per-widget frame cost: fps, frame time and usage share.")
    PyImGui.text("Click an entry for a phase breakdown, 60s history and metrics.")
    PyImGui.text("Run a detailed cProfile capture, rendered as an ImPlot flame graph.")
    PyImGui.spacing()
    PyImGui.end_tooltip()


def draw() -> None:
    global selected_view, selected_widget

    if not PyImGui.begin("System Monitor", PyImGui.WindowFlags.AlwaysAutoResize):
        PyImGui.end()
        return

    # ── header: current fps / target, whole-frame time, script time ──
    PyImGui.text_colored(f"{system_info.fps:.0f} FPS", _fps_color(system_info.fps))
    PyImGui.same_line()
    target = system_info.target_fps
    PyImGui.text_colored(f"/ {target if target > 0 else 'unlimited'}", _COL_DARKCYAN)
    PyImGui.same_line()
    PyImGui.text(f"| {system_info.ms_per_frame:.2f} ms/frame")
    PyImGui.same_line()
    used_pct = (system_info.ms_used / system_info.ms_per_frame * 100.0) if system_info.ms_per_frame > 0.0 else 0.0
    PyImGui.text_colored(f"|  Used {system_info.ms_used:.2f} ms ({used_pct:.0f}%)", _total_time_color(used_pct))

    PyImGui.separator()

    # ── pick what the per-widget % means (the two modes you described) ──
    #   0 = share of the whole frame  ->  widget_ms / frame_ms
    #   1 = share of all widget work  ->  widget_ms / total widget_ms
    selected_view = PyImGui.radio_button("% of frame", selected_view, 0)
    PyImGui.same_line()
    selected_view = PyImGui.radio_button("% of widget work", selected_view, 1)

    denom = system_info.ms_per_frame if selected_view == 0 else system_info.ms_used

    PyImGui.same_line()
    if PyImGui.button("Reset Statistics"):
        PyProfiler.reset()
        system_info.widgets, system_info.ms_used = _refresh_usage()
        _rebuild_bar_cache()

    PyImGui.separator()

    # ── usage share: a stacked bar, one colored segment per widget (ImPlot) ──
    picked = _draw_usage_bar(denom)
    PyImGui.same_line()
    if PyImGui.button("Print Report"):
        for name, ms in system_info.widgets:
            pct = (ms / denom * 100.0) if denom > 0.0 else 0.0
            print(f"{name}: {ms:.3f} ms ({pct:.1f}%)")
            
    PyImGui.spacing()

    # ── top widgets by time this frame, with the chosen % ──
    table_flags = int(PyImGui.TableFlags.RowBg | PyImGui.TableFlags.SizingFixedFit)
    # NOTE: ImGui persists column layout in imgui.ini keyed by this table ID.
    # If you reorder/rename columns and they still show the old layout, bump this
    # ID string (or delete the table's entry from imgui.ini) to force a fresh read.
    if PyImGui.begin_table("top_widgets_v2", 3, table_flags):
        PyImGui.table_setup_column("widget")
        PyImGui.table_setup_column("ms")
        PyImGui.table_setup_column("%")
        PyImGui.table_headers_row()

        # Lighten the selected/hovered row -- the default Header color is nearly the
        # same as the dark theme background, so selection was almost invisible.
        PyImGui.push_style_color(PyImGui.ImGuiCol.Header, _SEL_HEADER)
        PyImGui.push_style_color(PyImGui.ImGuiCol.HeaderHovered, _SEL_HEADER_HOVER)
        for i, (name, ms) in enumerate(system_info.widgets[:15]):  # top 15
            pct = (ms / denom * 100.0) if denom > 0.0 else 0.0
            PyImGui.table_next_row()

            # column 0 (widget) doubles as the whole-row click target
            PyImGui.table_set_column_index(0)
            if PyImGui.selectable(f"{name}##row{i}", selected_widget == name,
                                  PyImGui.SelectableFlags.SpanAllColumns, (0.0, 0.0)):
                picked = name

            PyImGui.table_set_column_index(1)
            PyImGui.text(f"{ms:.3f}")

            # column 2 (%): a progress bar tinted with THIS widget's stacked-bar
            # color, so the bar and the table share one color per widget. Rows past
            # the bar's top-10 fall into "others" and share that segment's color.
            # A fixed width is required -- AlwaysAutoResize collapses a -1 bar to 0.
            PyImGui.table_set_column_index(2)
            row_color = system_info.widget_colors.get(name)
            if row_color is None:
                row_color = system_info.widget_colors.get("others", _TRACK_COLOR)
            PyImGui.push_style_color(PyImGui.ImGuiCol.PlotHistogram, row_color.to_tuple_normalized())
            PyImGui.push_style_color(PyImGui.ImGuiCol.FrameBg, _TRACK_COLOR.to_tuple_normalized())
            PyImGui.progress_bar(min(pct / 100.0, 1.0), 90.0, 0.0, f"{pct:.0f}%")
            PyImGui.pop_style_color(2)
        PyImGui.pop_style_color(2)  # Header / HeaderHovered pushed before the loop
        PyImGui.end_table()

    # A click on a real segment or row toggles the shared detail window.
    if picked is not None and picked != "others":
        selected_widget = "" if selected_widget == picked else picked

    PyImGui.end()

    # Shared per-widget detail window (only while a widget is selected).
    _draw_widget_window()


if __name__ == "__main__":
    update()
