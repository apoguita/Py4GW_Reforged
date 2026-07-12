"""Launch Bar host — renders ONE :class:`LaunchBar` with ImGui and handles its interaction.

One host owns one bar's transient UI state (animation, strip drag, tile drag, hover). Shared
cross-bar state (which bar is selected / in edit mode, which tile is selected, delete
confirmation) lives on the ``manager`` passed into :meth:`draw`, so the host never imports the
manager (no import cycle) and just duck-types the few attributes/methods it needs:

    manager.selected_id        -> str          (bar being configured in the settings window)
    manager.editing_id         -> str | None   (bar currently in edit mode)
    manager.selected_tile_id   -> str | None   (tile selected within the editing bar)
    manager.request_delete_bar(bar)            (opens the confirm modal)

This pass is UI/layout only — tiles render as labeled placeholders; clicking one outside edit
mode does nothing yet (execution binding is a later pass).
"""

import os

import PyImGui

from .function_runtime import resolve_icon
from .model import BarSide
from .model import LaunchBar
from .model import Tile
from .tween import AnimFloat

# repo root: .../Py4GWCoreLib/py4gwcorelib_src/launch_bar/host.py -> four dirs up
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_STRIP_HOVER_LIGHTEN = 0.45
_COLLAPSED_LIGHTEN = 0.28
_TILE_BORDER_LIGHTEN = 0.18
_ACCENT = (0.24, 0.48, 0.85, 1.0)  # selection outline / drop-ok
_ACTION_LABELS = {"browser": "WDG"}      # short face label for a system-action tile (icon fallback)
_ACTION_ICONS = {"browser": os.path.join(_ROOT, "python_icon.ico")}  # widget-explorer icon
_ACTION_TOOLTIP = {"browser": "Widget browser"}


# ---- color helpers (operate on '#rrggbb') ---------------------------------------------
def _parse_hex(value: str) -> tuple[int, int, int]:
    h = value.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex_rgba01(value: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    r, g, b = _parse_hex(value)
    return (r / 255.0, g / 255.0, b / 255.0, alpha)


def _hex_u32(value: str, alpha: int = 255) -> int:
    r, g, b = _parse_hex(value)
    return (alpha << 24) | (b << 16) | (g << 8) | r


def _rgba01_u32(r: float, g: float, b: float, a: float) -> int:
    return (int(a * 255) << 24) | (int(b * 255) << 16) | (int(g * 255) << 8) | int(r * 255)


def _lighten(value: str, amt: float) -> str:
    r, g, b = _parse_hex(value)
    r = int(r + (255 - r) * amt)
    g = int(g + (255 - g) * amt)
    b = int(b + (255 - b) * amt)
    return "#%02x%02x%02x" % (r, g, b)


class LaunchBarHost:
    """Renders and drives one launch bar."""

    def __init__(self, bar: LaunchBar) -> None:
        self.bar = bar
        self._collapse = AnimFloat(1.0 if bar.collapsed else 0.0)
        self._alpha = AnimFloat(bar.idle_opacity)
        self._hovered_prev = False
        # strip interaction
        self._strip_was_active = False
        self._strip_pressed = False
        self._strip_moved = False
        self._press_x = 0.0
        self._press_y = 0.0
        # tile drag
        self._drag_tile_id = None
        self._drag_moved = False
        self._grab_c = 0
        self._grab_r = 0
        self._drag_target = None  # (col, row, ok)

    # ---- geometry -------------------------------------------------------------------
    def _geometry(self, p: float):
        """Return (W, H, strip_rect, content_off) for collapse progress p (0 open .. 1 folded)."""

        bar = self.bar
        cw, ch = bar.content_size()
        strip = bar.strip
        if bar.is_horizontal:
            along = cw * (1.0 - p)
            w, h = strip + along, ch
            if bar.side == BarSide.LEFT:
                return w, h, (0.0, 0.0, strip, h), (strip, 0.0)
            return w, h, (w - strip, 0.0, strip, h), (0.0, 0.0)
        along = ch * (1.0 - p)
        w, h = cw, strip + along
        if bar.side == BarSide.TOP:
            return w, h, (0.0, 0.0, w, strip), (0.0, strip)
        return w, h, (0.0, h - strip, w, strip), (0.0, 0.0)

    def _topleft(self, w: float, h: float) -> tuple[float, float]:
        bar = self.bar
        x = bar.x - w if bar.side == BarSide.RIGHT else bar.x
        y = bar.y - h if bar.side == BarSide.BOTTOM else bar.y
        return (x, y)

    def set_side(self, new_side: BarSide) -> None:
        """Move the strip to another edge while keeping the bar visually in place."""

        bar = self.bar
        if bar.side == new_side:
            return
        p = self._collapse.current
        w, h, _, _ = self._geometry(p)
        left, top = self._topleft(w, h)
        right, bottom = left + w, top + h
        bar.side = new_side
        bar.x = right if new_side == BarSide.RIGHT else left
        bar.y = bottom if new_side == BarSide.BOTTOM else top

    # ---- main draw ------------------------------------------------------------------
    def draw(self, manager, now_ms: float) -> None:
        bar = self.bar
        editing = manager.editing_id == bar.id

        # animations (alpha uses previous frame's hover to avoid a chicken/egg with begin)
        self._collapse.set_target(1.0 if bar.collapsed else 0.0, now_ms)
        p = self._collapse.update(now_ms)
        full = self._hovered_prev or self._strip_pressed or editing
        self._alpha.set_target(1.0 if full else bar.idle_opacity, now_ms)
        alpha = self._alpha.update(now_ms)

        w, h, strip_rect, content_off = self._geometry(p)
        topleft = self._topleft(w, h)

        PyImGui.set_next_window_pos(topleft, PyImGui.ImGuiCond.Always)
        PyImGui.set_next_window_size((w, h), PyImGui.ImGuiCond.Always)

        flags = (
            PyImGui.WindowFlags.NoTitleBar
            | PyImGui.WindowFlags.NoResize
            | PyImGui.WindowFlags.NoMove
            | PyImGui.WindowFlags.NoScrollbar
            | PyImGui.WindowFlags.NoScrollWithMouse
            | PyImGui.WindowFlags.NoCollapse
            | PyImGui.WindowFlags.NoSavedSettings
            | PyImGui.WindowFlags.NoFocusOnAppearing
        )
        # Alpha style var fades the whole window (bg + tiles + text) uniformly = the idle fade.
        PyImGui.push_style_var(PyImGui.ImGuiStyleVar.Alpha, alpha)
        PyImGui.push_style_color(PyImGui.ImGuiCol.WindowBg, _hex_rgba01(bar.colors.bg, bar.colors.bg_a))
        PyImGui.push_style_var_vec2(PyImGui.ImGuiStyleVar.WindowPadding, (0.0, 0.0))
        PyImGui.push_style_var(PyImGui.ImGuiStyleVar.WindowRounding, 3.0)
        # let the window shrink to the strip on collapse (default WindowMinSize ~32x32 would
        # otherwise leave a slab of window background as a stub past the strip)
        PyImGui.push_style_var_vec2(PyImGui.ImGuiStyleVar.WindowMinSize, (1.0, 1.0))

        opened = PyImGui.begin("##LaunchBar_%s" % bar.id, flags)
        if opened:
            win_pos = PyImGui.get_window_pos()
            self._hovered_prev = PyImGui.is_window_hovered()
            self._draw_strip(manager, strip_rect, win_pos, p, now_ms, alpha)
            if p < 0.999:
                self._draw_content(manager, editing, content_off, win_pos)
            # bar menu opens on right-click ANYWHERE over the bar window (not just the strip).
            # Tiles/empty-cells in edit mode still get their own item menus first.
            if PyImGui.begin_popup_context_window("##barmenu_%s" % bar.id):
                self._bar_menu(manager)
                PyImGui.end_popup()
        PyImGui.end()

        PyImGui.pop_style_var(4)
        PyImGui.pop_style_color(1)

    # ---- strip (drag handle + collapse + bar context menu) --------------------------
    def _draw_strip(self, manager, strip_rect, win_pos, p, now_ms, alpha) -> None:
        bar = self.bar
        sx, sy, sw, sh = strip_rect
        collapsed = bar.collapsed

        base = bar.colors.drag
        if self._strip_was_active or (self._hovered_prev and self._point_in(strip_rect)):
            color = _lighten(base, _STRIP_HOVER_LIGHTEN)
        elif collapsed:
            color = _lighten(base, _COLLAPSED_LIGHTEN)
        else:
            color = base

        a8 = max(0, min(255, int(255 * alpha * bar.colors.drag_a)))
        dl = PyImGui.get_window_draw_list()
        x0, y0 = win_pos[0] + sx, win_pos[1] + sy
        x1, y1 = x0 + sw, y0 + sh
        dl.add_rect_filled((x0, y0), (x1, y1), _hex_u32(color, a8), rounding=2.0)
        self._draw_grip_dots(dl, (x0, y0, sw, sh), alpha)

        PyImGui.set_cursor_pos((sx, sy))
        PyImGui.invisible_button("##strip_%s" % bar.id, (sw, sh))

        # drag to move / click to collapse — inert while the fold animates
        active = PyImGui.is_item_active()
        if not self._collapse.animating:
            if active and not self._strip_was_active:
                self._strip_pressed = True
                self._strip_moved = False
                self._press_x, self._press_y = bar.x, bar.y
                manager.selected_id = bar.id
            if active and PyImGui.is_mouse_dragging(0, 4.0):
                dx, dy = PyImGui.get_mouse_drag_delta(0, 4.0)
                bar.x = self._press_x + dx
                bar.y = self._press_y + dy
                self._strip_moved = True
            if self._strip_was_active and not active:
                if self._strip_pressed and not self._strip_moved:
                    bar.collapsed = not bar.collapsed
                    self._collapse.set_target(1.0 if bar.collapsed else 0.0, now_ms)
                self._strip_pressed = False
        self._strip_was_active = active

    def _draw_grip_dots(self, dl, rect, alpha=1.0) -> None:
        x, y, w, h = rect
        cx, cy = x + w / 2.0, y + h / 2.0
        col = _rgba01_u32(0.78, 0.80, 0.85, 0.6 * alpha)
        horizontal = w > h
        for i in (-1, 0, 1):
            if horizontal:
                dl.add_circle_filled((cx + i * 4.0, cy), 1.2, col, 6)
            else:
                dl.add_circle_filled((cx, cy + i * 4.0), 1.2, col, 6)

    def _point_in(self, rect) -> bool:
        return True  # coarse; refined hover handled by is_window_hovered

    def _bar_menu(self, manager) -> None:
        bar = self.bar
        if PyImGui.menu_item("Editor..."):
            manager.open_editor(bar.id)
        editing = manager.editing_id == bar.id
        if PyImGui.menu_item("Stop editing" if editing else "Edit layout"):
            manager.editing_id = None if editing else bar.id
            manager.selected_tile_id = None
        PyImGui.separator()
        if PyImGui.menu_item("Delete launchpad"):
            manager.request_delete_bar(bar)

    # ---- content (grid divisions + tiles) -------------------------------------------
    def _draw_content(self, manager, editing, content_off, win_pos) -> None:
        bar = self.bar
        ox, oy = content_off
        dl = PyImGui.get_window_draw_list()

        if editing:
            self._draw_slot_grid(dl, win_pos, ox, oy)

        for tile in list(bar.tiles):
            self._draw_tile(manager, editing, tile, ox, oy, win_pos, dl)

        if editing:
            self._draw_empty_cells(manager, ox, oy, win_pos)
            if self._drag_target is not None:
                self._draw_drop_target(dl, win_pos, ox, oy)

    def _draw_slot_grid(self, dl, win_pos, ox, oy) -> None:
        bar = self.bar
        col_u32 = _rgba01_u32(1.0, 1.0, 1.0, 0.16)
        for row in range(bar.rows):
            for col in range(bar.columns):
                cx, cy = bar.cell_origin(col, row)
                x0 = win_pos[0] + ox + cx
                y0 = win_pos[1] + oy + cy
                dl.add_rect((x0, y0), (x0 + bar.cell, y0 + bar.cell), col_u32, rounding=2.0, thickness=1.0)

    def _draw_tile(self, manager, editing, tile: Tile, ox, oy, win_pos, dl) -> None:
        bar = self.bar
        x, y, tw, th = bar.tile_rect(tile)
        cx, cy = ox + x, oy + y
        runtime = getattr(manager, "runtime", None)
        funcs = getattr(manager, "functions", None)
        meta = runtime.get(tile.widget_id) if (tile.widget_id and runtime is not None) else None
        fmeta = funcs.get(tile.function_id) if (tile.function_id and funcs is not None) else None
        action = tile.action
        active = meta.enabled if meta is not None else (manager.is_action_active(action) if action else False)

        fa = bar.colors.face_a
        PyImGui.push_style_color(PyImGui.ImGuiCol.Button, _hex_rgba01(bar.colors.face, fa))
        PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, _hex_rgba01(_lighten(bar.colors.face, 0.12), fa))
        PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, _hex_rgba01(_lighten(bar.colors.face, 0.20), fa))
        PyImGui.set_cursor_pos((cx, cy))
        clicked = self._tile_button(bar, tile, meta, fmeta, tw, th)
        PyImGui.pop_style_color(3)

        # widget / action / function tiles: tooltip (+ active indicator for stateful kinds).
        # Functions are fire-and-forget, so they never light the active indicator.
        if meta is not None:
            state = "Active - click to stop" if active else "Inactive - click to launch"
            PyImGui.set_item_tooltip("%s\n%s\n%s" % (meta.name, meta.category, state))
        elif action:
            PyImGui.set_item_tooltip(_ACTION_TOOLTIP.get(action, action))
        elif fmeta is not None:
            path = "%s > %s" % (fmeta.group or "Uncategorized", fmeta.category or "General")
            PyImGui.set_item_tooltip("%s\n%s\n%s" % (fmeta.name, path, fmeta.tooltip or "Click to run"))
        if active:
            self._draw_active_indicator(dl, win_pos[0] + cx, win_pos[1] + cy, tw, th)

        if editing and PyImGui.begin_popup_context_item("##tilemenu_%s_%s" % (bar.id, tile.id)):
            self._tile_menu(manager, tile)
            PyImGui.end_popup()

        if editing:
            if clicked:
                manager.selected_tile_id = tile.id
            self._handle_tile_drag(manager, tile, win_pos, ox, oy)
            if manager.selected_tile_id == tile.id:
                x0, y0 = win_pos[0] + cx, win_pos[1] + cy
                dl.add_rect((x0, y0), (x0 + tw, y0 + th), _rgba01_u32(*_ACCENT), rounding=3.0, thickness=2.0)
        elif clicked:
            # normal mode: launch/toggle the widget, fire the system action, or run the function
            if meta is not None:
                runtime.toggle(tile.widget_id)
            elif action:
                manager.do_action(action)
            elif tile.function_id:
                manager.invoke_function(tile.function_id)

    def _tile_button(self, bar, tile, meta, fmeta, tw, th) -> bool:
        """Draw the tile's clickable face: action icon/label, function glyph, widget icon, or placeholder."""

        if tile.action:
            icon = _ACTION_ICONS.get(tile.action)
            if icon:
                from Py4GWCoreLib._legacy_facade import ImGui_Legacy

                return ImGui_Legacy.image_button("##tile_%s_%s" % (bar.id, tile.id), icon, tw, th)
            label = _ACTION_LABELS.get(tile.action, "?")
            return PyImGui.button("%s##tile_%s_%s" % (label, bar.id, tile.id), tw, th)
        if tile.function_id:
            # tile.icon override wins; fall back to the catalog default; then to initials/"FN"
            glyph = resolve_icon(tile.icon) or (resolve_icon(fmeta.icon) if fmeta is not None else None)
            if glyph:
                return PyImGui.button("%s##tile_%s_%s" % (glyph, bar.id, tile.id), tw, th)
            label = (fmeta.name[:2].upper() if (fmeta is not None and fmeta.name) else "FN")
            return PyImGui.button("%s##tile_%s_%s" % (label, bar.id, tile.id), tw, th)
        if meta is None:
            return PyImGui.button("%dx%d##tile_%s_%s" % (tile.w, tile.h, bar.id, tile.id), tw, th)
        if meta.icon and os.path.isfile(meta.icon):
            from Py4GWCoreLib._legacy_facade import ImGui_Legacy

            return ImGui_Legacy.image_button("##tile_%s_%s" % (bar.id, tile.id), meta.icon, tw, th)
        label = (meta.name[:2].upper() if meta.name else "?")
        return PyImGui.button("%s##tile_%s_%s" % (label, bar.id, tile.id), tw, th)

    def _draw_active_indicator(self, dl, sx, sy, tw, th) -> None:
        bar = self.bar
        if bar.ind_mask:
            dl.add_rect_filled((sx, sy), (sx + tw, sy + th), _hex_u32(bar.active_color, 77), rounding=3.0)
        if bar.ind_outline:
            dl.add_rect((sx, sy), (sx + tw, sy + th), _hex_u32(bar.active_color, 255), rounding=3.0, thickness=2.0)

    def _tile_menu(self, manager, tile: Tile) -> None:
        bar = self.bar
        manager.selected_tile_id = tile.id
        if PyImGui.menu_item("Grow width"):
            bar.resize_tile(tile.id, tile.w + 1, tile.h)
        if PyImGui.menu_item("Shrink width"):
            bar.resize_tile(tile.id, tile.w - 1, tile.h)
        if PyImGui.menu_item("Grow height"):
            bar.resize_tile(tile.id, tile.w, tile.h + 1)
        if PyImGui.menu_item("Shrink height"):
            bar.resize_tile(tile.id, tile.w, tile.h - 1)
        if tile.deletable:
            PyImGui.separator()
            if PyImGui.menu_item("Remove tile"):
                bar.remove_tile(tile.id)
                if manager.selected_tile_id == tile.id:
                    manager.selected_tile_id = None

    def _handle_tile_drag(self, manager, tile: Tile, win_pos, ox, oy) -> None:
        bar = self.bar
        active = PyImGui.is_item_active()
        if active and PyImGui.is_mouse_dragging(0, 6.0):
            mx, my = PyImGui.get_mouse_pos()
            grid_x = win_pos[0] + ox + bar.pad
            grid_y = win_pos[1] + oy + bar.pad
            step = bar.cell + bar.gap
            if self._drag_tile_id != tile.id:
                self._drag_tile_id = tile.id
                self._grab_c = int((mx - grid_x) // step) - tile.col
                self._grab_r = int((my - grid_y) // step) - tile.row
                manager.selected_tile_id = tile.id
            col = int((mx - grid_x) // step) - self._grab_c
            row = int((my - grid_y) // step) - self._grab_r
            col = max(0, min(bar.columns - tile.w, col))
            row = max(0, min(bar.rows - tile.h, row))
            ok = bar.can_place(tile.w, tile.h, col, row, except_id=tile.id)
            self._drag_target = (col, row, ok, tile.w, tile.h)
        elif self._drag_tile_id == tile.id and not active:
            if self._drag_target is not None:
                col, row, ok, _, _ = self._drag_target
                if ok:
                    bar.move_tile(tile.id, col, row)
            self._drag_tile_id = None
            self._drag_target = None

    def _draw_drop_target(self, dl, win_pos, ox, oy) -> None:
        bar = self.bar
        col, row, ok, tw_cells, th_cells = self._drag_target
        cx, cy = bar.cell_origin(col, row)
        x0 = win_pos[0] + ox + cx
        y0 = win_pos[1] + oy + cy
        w = tw_cells * bar.cell + (tw_cells - 1) * bar.gap
        h = th_cells * bar.cell + (th_cells - 1) * bar.gap
        color = _rgba01_u32(0.35, 0.66, 0.42, 0.9) if ok else _rgba01_u32(0.81, 0.36, 0.36, 0.9)
        fill = _rgba01_u32(0.35, 0.66, 0.42, 0.18) if ok else _rgba01_u32(0.81, 0.36, 0.36, 0.18)
        dl.add_rect_filled((x0, y0), (x0 + w, y0 + h), fill, rounding=3.0)
        dl.add_rect((x0, y0), (x0 + w, y0 + h), color, rounding=3.0, thickness=2.0)

    def _draw_empty_cells(self, manager, ox, oy, win_pos) -> None:
        bar = self.bar
        occupied = bar.occupied_cells()
        for row in range(bar.rows):
            for col in range(bar.columns):
                if (col, row) in occupied:
                    continue
                cx, cy = bar.cell_origin(col, row)
                PyImGui.set_cursor_pos((ox + cx, oy + cy))
                if PyImGui.invisible_button("##cell_%s_%d_%d" % (bar.id, col, row), (bar.cell, bar.cell)):
                    t = bar.add_tile(1, 1, col=col, row=row)
                    if t is not None:
                        manager.selected_tile_id = t.id
                if PyImGui.begin_popup_context_item("##cellmenu_%s_%d_%d" % (bar.id, col, row)):
                    if PyImGui.menu_item("Add 1x1 here"):
                        t = bar.add_tile(1, 1, col=col, row=row)
                        if t is not None:
                            manager.selected_tile_id = t.id
                    PyImGui.end_popup()
                # a faint "+" hint on hover
                if PyImGui.is_item_hovered():
                    dl = PyImGui.get_window_draw_list()
                    hx = win_pos[0] + ox + cx + bar.cell / 2.0
                    hy = win_pos[1] + oy + cy + bar.cell / 2.0
                    col_u32 = _rgba01_u32(1.0, 1.0, 1.0, 0.5)
                    dl.add_line((hx - 3, hy), (hx + 3, hy), col_u32, 1.0)
                    dl.add_line((hx, hy - 3), (hx, hy + 3), col_u32, 1.0)
