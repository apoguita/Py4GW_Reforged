"""Launch Bar host — renders ONE :class:`LaunchBar` with ImGui and handles its interaction.

One host owns one bar's transient UI state (animation, strip drag, tile drag, hover). Shared
cross-bar state (which bar is selected / in edit mode, which tile is selected, delete
confirmation) lives on the ``manager`` passed into :meth:`draw`, so the host never imports the
manager (no import cycle) and just duck-types the few attributes/methods it needs:

    manager.selected_id        -> str          (bar being configured in the settings window)
    manager.editing_id         -> str | None   (bar currently in edit mode)
    manager.selected_tile_id   -> str | None   (tile selected within the editing bar)
    manager.request_delete_bar(bar)            (opens the confirm modal)
    manager.open_editor(bar_id)                (shows the editor windows)
    manager.runtime                            (widget enumerate/toggle/configure)

RULE -- ONE context menu per bar. A launchpad is small and is routinely full, so any menu
that needs a particular patch of pixels (an empty cell, bare background) is a menu the
user cannot reach; and options split across several popups are options they cannot find.
There is therefore exactly one right-click provider, ``_context_menu``, opened by the
single ``begin_popup_context_window`` in :meth:`draw` from anywhere over the bar. It has a
fixed set of rows in a fixed order; rows that do not apply to the current target are
DISABLED, never hidden or reordered. Do not add ``begin_popup_context_item`` here -- give
the new target a hover latch and a row in ``_context_menu`` instead.

This pass is UI/layout only — tiles render as labeled placeholders; clicking one outside edit
mode does nothing yet (execution binding is a later pass).
"""

import os

import PyImGui

from .function_runtime import resolve_icon
from .model import BarSide
from .model import LaunchBar
from .model import Tile
from .model import model_revision
from .tween import AnimFloat

# repo root: .../Py4GWCoreLib/py4gwcorelib_src/launch_bar/host.py -> four dirs up
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_STRIP_HOVER_LIGHTEN = 0.45
_COLLAPSED_LIGHTEN = 0.28
_TILE_BORDER_LIGHTEN = 0.18
_ACCENT = (0.24, 0.48, 0.85, 1.0)  # selection outline / drop-ok
_ACTION_LABELS = {"browser": "WDG", "system_settings": "CFG"}  # face label fallback (no icon)
_ACTION_ICONS = {  # textured face per system action
    "browser": os.path.join(_ROOT, "python_icon.ico"),          # widget-explorer icon
    "system_settings": os.path.join(_ROOT, "Textures", "Icons", "cogs.png"),  # settings cog
}
_ACTION_TOOLTIP = {"browser": "Widget browser", "system_settings": "System settings"}


# ---- color helpers (operate on '#rrggbb') ---------------------------------------------
# Colors here are static strings reconverted every frame per bar/tile; cache the parse
# (and the lighten) by input so each unique value is computed once, not 60x/second.
_PARSE_HEX_CACHE: dict[str, tuple[int, int, int]] = {}
_LIGHTEN_CACHE: dict[tuple[str, float], str] = {}


def _parse_hex(value: str) -> tuple[int, int, int]:
    cached = _PARSE_HEX_CACHE.get(value)
    if cached is None:
        h = value.lstrip("#")
        cached = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        _PARSE_HEX_CACHE[value] = cached
    return cached


def _hex_rgba01(value: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    r, g, b = _parse_hex(value)
    return (r / 255.0, g / 255.0, b / 255.0, alpha)


def _hex_u32(value: str, alpha: int = 255) -> int:
    r, g, b = _parse_hex(value)
    return (alpha << 24) | (b << 16) | (g << 8) | r


def _rgba01_u32(r: float, g: float, b: float, a: float) -> int:
    return (int(a * 255) << 24) | (int(b * 255) << 16) | (int(g * 255) << 8) | int(r * 255)


def _lighten(value: str, amt: float) -> str:
    key = (value, amt)
    cached = _LIGHTEN_CACHE.get(key)
    if cached is None:
        r, g, b = _parse_hex(value)
        r = int(r + (255 - r) * amt)
        g = int(g + (255 - g) * amt)
        b = int(b + (255 - b) * amt)
        cached = "#%02x%02x%02x" % (r, g, b)
        _LIGHTEN_CACHE[key] = cached
    return cached


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
        # context menu: what the cursor is over this frame, and what was latched when the
        # bar's single right-click menu opened (see _context_menu)
        self._frame_hover_widget: str | None = None
        self._frame_hover_tile: str | None = None
        self._frame_hover_cell: tuple[int, int] | None = None
        self._ctx_widget_id: str | None = None
        self._ctx_tile_id: str | None = None
        self._ctx_cell: tuple[int, int] | None = None

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
        # what the cursor is over this frame, feeding the ONE context menu below
        self._frame_hover_widget = None  # widget tile (normal mode: enable/disable/configure)
        self._frame_hover_tile = None    # any tile (edit mode: grow/shrink/remove)
        self._frame_hover_cell = None    # empty grid cell (edit mode: add here)

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
            # THE bar's one and only right-click menu, in BOTH modes. It opens on
            # right-click ANYWHERE over the bar -- a tile, an empty cell, the strip, or
            # bare background -- because nothing here uses NoOpenOverItems and there are
            # no competing per-tile/per-cell popups. That is the point: the bar is tiny
            # and often completely full, so a menu that needs empty space is a menu you
            # cannot reach. The bar/editor block is always at the bottom, so edit mode is
            # never a trap -- you can always open the Editor, leave edit mode, or delete
            # the launchpad. Alpha=1.0 so the bar's idle-fade doesn't render it
            # near-invisible. The hovered target is latched while the popup is open so it
            # doesn't change if the cursor drifts off.
            menu_id = "##barmenu_%s" % bar.id
            if not PyImGui.is_popup_open(menu_id):
                self._ctx_widget_id = self._frame_hover_widget
                self._ctx_tile_id = self._frame_hover_tile
                self._ctx_cell = self._frame_hover_cell
            PyImGui.push_style_var(PyImGui.ImGuiStyleVar.Alpha, 1.0)
            if PyImGui.begin_popup_context_window(menu_id, PyImGui.PopupFlags.NoFlag):
                self._context_menu(manager, editing)
                PyImGui.end_popup()
            PyImGui.pop_style_var(1)
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

    def _ctx_label(self, tile, meta, cell) -> str:
        """One-line description of what the menu is currently pointed at."""

        if meta is not None:
            return meta.name or "widget"
        if tile is not None:
            return tile.name or ("%dx%d item" % (tile.w, tile.h))
        if cell is not None:
            return "empty cell %d,%d" % cell
        return "launchpad"

    def _context_menu(self, manager, editing) -> None:
        """Build the bar's single right-click menu.

        The menu has a FIXED shape: every entry is always present, in the same order,
        wherever you clicked and whichever mode the bar is in. Entries that cannot act on
        the current target are DISABLED, never removed. Nothing is hidden -- a menu that
        reshuffles itself by context is what made these options feel scattered and
        unreachable, and it makes the same click do different things on different frames.
        A greyed row still tells you the option exists; the header line says what the
        menu is pointed at, which is why a row is greyed.

        Enablement tracks only whether the action is genuinely possible for the target --
        never the edit-mode flag. Edit mode drives the grid overlay and drag/drop, not
        which menu entries you may use.
        """
        bar = self.bar
        runtime = getattr(manager, "runtime", None)
        wid = self._ctx_widget_id
        tile = bar.get_tile(self._ctx_tile_id) if self._ctx_tile_id else None
        meta = runtime.get(wid) if (runtime is not None and wid) else None
        cell = self._ctx_cell
        # Preset (auto-populated) bars rebuild their tiles from the live widget set every
        # frame, so hand edits to their layout cannot stick -> those rows are disabled.
        editable = bar.source == "manual"
        if tile is not None:
            manager.selected_tile_id = tile.id

        PyImGui.text_disabled("%s - %s" % (bar.name, self._ctx_label(tile, meta, cell)))
        PyImGui.separator()

        # ---- the widget under the cursor ----
        on = bool(meta and meta.enabled)
        if PyImGui.menu_item("Disable" if on else "Enable", "", False, meta is not None) and wid:
            if runtime is not None:
                runtime.toggle(wid)
        cfg = bool(meta and meta.configuring)
        if PyImGui.menu_item("Stop configuring" if cfg else "Configure", "", False,
                             bool(meta and meta.configurable)) and wid:
            if runtime is not None:
                runtime.set_configuring(wid, not cfg)
        PyImGui.separator()

        # ---- the item / empty cell under the cursor ----
        sizable = tile is not None and editable
        if PyImGui.menu_item("Grow width", "", False, sizable) and tile:
            bar.resize_tile(tile.id, tile.w + 1, tile.h)
        if PyImGui.menu_item("Shrink width", "", False, sizable) and tile:
            bar.resize_tile(tile.id, tile.w - 1, tile.h)
        if PyImGui.menu_item("Grow height", "", False, sizable) and tile:
            bar.resize_tile(tile.id, tile.w, tile.h + 1)
        if PyImGui.menu_item("Shrink height", "", False, sizable) and tile:
            bar.resize_tile(tile.id, tile.w, tile.h - 1)
        removable = bool(tile is not None and editable and tile.deletable)
        if PyImGui.menu_item("Remove item", "", False, removable) and tile:
            bar.remove_tile(tile.id)
            if manager.selected_tile_id == tile.id:
                manager.selected_tile_id = None
        if PyImGui.menu_item("Add item here", "", False, cell is not None and editable) and cell:
            t = bar.add_tile(1, 1, col=cell[0], row=cell[1])
            if t is not None:
                manager.selected_tile_id = t.id
        PyImGui.separator()

        # ---- the bar itself: ALWAYS reachable, whatever the cursor is over ----
        if PyImGui.menu_item("Editor...", "", False, True):
            manager.open_editor(bar.id)
        if PyImGui.menu_item("Stop editing" if editing else "Edit layout", "", False, True):
            manager.editing_id = None if editing else bar.id
            manager.selected_tile_id = None
        PyImGui.separator()
        # system bars are not deletable (the editor forbids it too) -> greyed, not hidden
        if PyImGui.menu_item("Delete launchpad", "", False, not bar.system):
            manager.request_delete_bar(bar)

    # ---- content (grid divisions + tiles) -------------------------------------------
    def _rev_cache(self, manager) -> None:
        """Rebuild this bar's static render data ONCE per change, not per frame.

        Tile geometry, parsed colors, AND the full per-tile draw spec (label, icon,
        tooltip, active overlay) are static between edits — "nothing changes that fast,
        everything else is static 99.9%". They are rebuilt only when the model
        (geometry/colors/layout, via ``model_revision``) or the widget set (enabled
        state/names, via the runtime revision) actually changes; every frame in between
        just replays the cached spec through one native IconTile call. Only action tiles
        recompute their active state per frame — it is not revision-tracked and is a
        cheap bool.

        Each spec entry is ``(label, texpath, tooltip, fill, outline, is_action, action,
        widget_id, function_id)``: the trailing keys drive click handling, ``is_action``
        marks the tiles whose overlay must be recomputed live.
        """
        runtime = getattr(manager, "runtime", None)
        funcs = getattr(manager, "functions", None)
        wrev = runtime.revision() if runtime is not None else 0
        sig = (model_revision(), wrev)
        if sig == getattr(self, "_cache_sig", None):
            return
        self._cache_sig = sig
        bar = self.bar
        self._geom = {t.id: bar.tile_rect(t) for t in bar.tiles}
        fa = bar.colors.face_a
        self._col_face = _hex_rgba01(bar.colors.face, fa)
        self._col_face_hover = _hex_rgba01(_lighten(bar.colors.face, 0.12), fa)
        self._col_face_active = _hex_rgba01(_lighten(bar.colors.face, 0.20), fa)
        mask = _hex_u32(bar.active_color, 77)
        outline = _hex_u32(bar.active_color, 255)
        self._col_ind_mask = mask
        self._col_ind_outline = outline
        ind_mask_on = bool(bar.ind_mask)
        ind_outline_on = bool(bar.ind_outline)

        spec = {}
        for tile in bar.tiles:
            meta = runtime.get(tile.widget_id) if (tile.widget_id and runtime is not None) else None
            fmeta = funcs.get(tile.function_id) if (tile.function_id and funcs is not None) else None
            action = tile.action
            label, texpath = self._tile_face(bar, tile, meta, fmeta)
            if meta is not None:
                active = bool(meta.enabled)
                state = "Active - click to stop" if active else "Inactive - click to launch"
                tooltip = "%s\n%s\n%s" % (meta.name, meta.category, state)
                fill = mask if (active and ind_mask_on) else 0
                ol = outline if (active and ind_outline_on) else 0
                spec[tile.id] = (label, texpath, tooltip, fill, ol, False, "", tile.widget_id, "")
            elif action:
                # active is dynamic for actions -> overlay recomputed per frame in _draw_tile
                tooltip = _ACTION_TOOLTIP.get(action, action)
                spec[tile.id] = (label, texpath, tooltip, 0, 0, True, action, "", "")
            elif fmeta is not None:
                path = "%s > %s" % (fmeta.group or "Uncategorized", fmeta.category or "General")
                tooltip = "%s\n%s\n%s" % (fmeta.name, path, fmeta.tooltip or "Click to run")
                spec[tile.id] = (label, texpath, tooltip, 0, 0, False, "", "", tile.function_id)
            else:
                spec[tile.id] = (label, texpath, "", 0, 0, False, "", "", "")
        self._spec = spec

    def _draw_content(self, manager, editing, content_off, win_pos) -> None:
        bar = self.bar
        ox, oy = content_off
        dl = PyImGui.get_window_draw_list()

        self._rev_cache(manager)  # geometry + colors + per-tile spec; rebuilt only on change

        if editing:
            self._draw_slot_grid(dl, win_pos, ox, oy)

        # Every tile in a bar shares the same face colors, so push them ONCE around the
        # loop instead of 3 push + 1 pop per tile (the button reads the current style).
        PyImGui.push_style_color(PyImGui.ImGuiCol.Button, self._col_face)
        PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, self._col_face_hover)
        PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, self._col_face_active)
        for tile in list(bar.tiles):
            self._draw_tile(manager, editing, tile, ox, oy, win_pos, dl)
        PyImGui.pop_style_color(3)

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
        # Everything static (geometry, label, icon, tooltip, widget-active overlay) was
        # precomputed in _rev_cache and is just replayed here through one native crossing.
        # Only action tiles refresh their overlay live (active state is not revision-tracked).
        spec = self._spec.get(tile.id)
        if spec is None:
            return  # tile not in the current rebuilt spec (transient) — skip this frame
        geom = self._geom.get(tile.id)
        if geom is None:
            geom = self.bar.tile_rect(tile)
        x, y, tw, th = geom
        cx, cy = ox + x, oy + y
        label, texpath, tooltip, fill, outline, is_action, action, widget_id, function_id = spec
        if is_action:
            active = manager.is_action_active(action) if action else False
            fill = self._col_ind_mask if (active and self.bar.ind_mask) else 0
            outline = self._col_ind_outline if (active and self.bar.ind_outline) else 0
        clicked = PyImGui.Ext.LaunchBar.IconTile(label, cx, cy, tw, th, texpath, False, tooltip, fill, outline)

        # No per-tile popup: the bar has ONE context menu (built in draw()). All this tile
        # does is record that the cursor is over it, in EITHER mode, so that menu can
        # enable this tile's rows (resize/remove, and widget enable/configure) instead of
        # greying them.
        if PyImGui.is_item_hovered():
            self._frame_hover_tile = tile.id
            if widget_id:
                self._frame_hover_widget = widget_id

        if editing:
            if clicked:
                manager.selected_tile_id = tile.id
            self._handle_tile_drag(manager, tile, win_pos, ox, oy)
            if manager.selected_tile_id == tile.id:
                x0, y0 = win_pos[0] + cx, win_pos[1] + cy
                dl.add_rect((x0, y0), (x0 + tw, y0 + th), _rgba01_u32(*_ACCENT), rounding=3.0, thickness=2.0)
        elif clicked:
            # normal mode: launch/toggle the widget, fire the system action, or run the function.
            # Click is rare, so resolve the runtime lazily here instead of per frame.
            if widget_id:
                runtime = getattr(manager, "runtime", None)
                if runtime is not None:
                    runtime.toggle(widget_id)
            elif action:
                manager.do_action(action)
            elif function_id:
                manager.invoke_function(function_id)

    def _tile_face(self, bar, tile, meta, fmeta):
        """Return ``(label, texture_path)`` for a tile's clickable face.

        A non-empty ``texture_path`` -> textured (icon) button; ``""`` -> plain label
        button (action label, function glyph/initials, widget initials, or placeholder).
        ``label`` always carries the unique ``##id`` suffix so ImGui keys the item.
        """
        tid = "##tile_%s_%s" % (bar.id, tile.id)
        if tile.action:
            icon = _ACTION_ICONS.get(tile.action)
            if icon:
                return tid, icon
            return "%s%s" % (_ACTION_LABELS.get(tile.action, "?"), tid), ""
        if tile.function_id:
            # tile.icon override wins; fall back to the catalog default; then to initials/"FN"
            glyph = resolve_icon(tile.icon) or (resolve_icon(fmeta.icon) if fmeta is not None else None)
            if glyph:
                return "%s%s" % (glyph, tid), ""
            label = (fmeta.name[:2].upper() if (fmeta is not None and fmeta.name) else "FN")
            return "%s%s" % (label, tid), ""
        if meta is None:
            return "%dx%d%s" % (tile.w, tile.h, tid), ""
        if meta.icon:
            return tid, meta.icon
        label = (meta.name[:2].upper() if meta.name else "?")
        return "%s%s" % (label, tid), ""

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
                # No per-cell popup either: record the cell so the bar's ONE context menu
                # can offer "Add 1x1 here", and draw a faint "+" hint on hover.
                if PyImGui.is_item_hovered():
                    self._frame_hover_cell = (col, row)
                    dl = PyImGui.get_window_draw_list()
                    hx = win_pos[0] + ox + cx + bar.cell / 2.0
                    hy = win_pos[1] + oy + cy + bar.cell / 2.0
                    col_u32 = _rgba01_u32(1.0, 1.0, 1.0, 0.5)
                    dl.add_line((hx - 3, hy), (hx + 3, hy), col_u32, 1.0)
                    dl.add_line((hx, hy - 3), (hx, hy + 3), col_u32, 1.0)
