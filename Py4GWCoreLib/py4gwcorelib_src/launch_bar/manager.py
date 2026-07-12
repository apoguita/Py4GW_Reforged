"""Launch Bar manager — owns N bars and the editor windows.

The editor is HIDDEN by default. It is opened by right-clicking a bar and choosing
"Editor..." (which calls :meth:`open_editor`). While open it shows two windows:

- **Settings** (tabs, one per launchpad): a tab bar plus collapsible "Layout" and "Colors"
  sections; sliders are paired with typed number inputs; colors use ``color_edit4`` (RGBA, so
  transparency is part of the widget).
- **Items** (dedicated, roomy): each button/tile is a collapsible header you expand to edit
  its span/position or remove it.

Every destructive action (delete tile, delete launchpad, shrinking the grid so tiles no
longer fit) routes through one generic confirmation modal. UI/layout only.
"""

import math

import PyImGui

from .browser import WidgetBrowser
from .function_runtime import FunctionRuntime
from .function_runtime import list_icons
from .function_runtime import resolve_icon
from .host import LaunchBarHost
from .model import BarSide
from .model import LaunchBarSet
from .model import Tile
from .widget_runtime import WidgetRuntime

_SIDES = [(BarSide.LEFT, "L"), (BarSide.RIGHT, "R"), (BarSide.TOP, "T"), (BarSide.BOTTOM, "B")]


def _parse_hex(value: str) -> tuple[int, int, int]:
    h = value.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _to_hex(r: int, g: int, b: int) -> str:
    clamp = lambda v: max(0, min(255, int(v)))
    return "#%02x%02x%02x" % (clamp(r), clamp(g), clamp(b))


class LaunchBarManager:
    def __init__(self, bar_set: LaunchBarSet) -> None:
        self.bar_set = bar_set
        self.hosts: dict = {}
        self.runtime = WidgetRuntime()     # enumerate/toggle widgets (safe if runtime absent)
        self.functions = FunctionRuntime()  # enumerate/invoke catalog functions (fire-and-forget)
        self.browser = WidgetBrowser()     # Explorer-style widget browser window
        self.selected_id = bar_set.bars[0].id if bar_set.bars else ""
        self.editing_id = None
        self.selected_tile_id = None
        self.new_tile_w = 1
        self.new_tile_h = 1
        self.editor_open = False           # hidden until a bar's right-click "Editor..."
        self.browser_open = False          # widget browser window (toggled by the system button)
        # Confirmation modal — EXACT shape of InventoryPlus._draw_destroy_confirmation_modal:
        # a pending flag that opens the popup once, plus the message/label/action to run on Yes.
        self._confirm_pending = False
        self._confirm_text = ""
        self._confirm_ok_label = ""
        self._confirm_action = None
        self._add_bar_menu_pending = False   # "+" tab / toolbar add button -> open the template menu
        self.assign_tile_id = None           # tile whose inline binding picker is open
        self.assign_mode = "widget"          # which picker is open: "widget" | "function" | "icon"
        self.assign_search = ""              # search text in the widget/function picker
        self.icon_search = ""                # search text in the Font Awesome icon picker
        self._icon_cache = None              # cached (name, glyph) list for the icon picker
        for bar in bar_set.bars:
            self._ensure_host(bar)

    # ---- lifecycle ------------------------------------------------------------------
    def _ensure_host(self, bar) -> LaunchBarHost:
        host = self.hosts.get(bar.id)
        if host is None:
            host = LaunchBarHost(bar)
            self.hosts[bar.id] = host
        return host

    def open_editor(self, bar_id: str) -> None:
        self.editor_open = True
        self.selected_id = bar_id

    # ---- system-action tiles (e.g. the widget-browser button) -----------------------
    def is_action_active(self, action) -> bool:
        return action == "browser" and self.browser_open

    def do_action(self, action) -> None:
        if action == "browser":
            self.browser_open = not self.browser_open

    # ---- function tiles (fire-and-forget calls from the catalog) ---------------------
    def invoke_function(self, function_id) -> None:
        self.functions.invoke(function_id)

    _PRESET_NAMES = {"active": "Active", "favorites": "Favorites"}

    def add_bar(self, source: str = "manual"):
        n = len(self.bar_set.bars)
        palette = [
            ("#0f1013", "#0a0a0a", "#2b2b31"),
            ("#101a14", "#0b140d", "#1f3a2a"),
            ("#141018", "#0d0a12", "#332740"),
            ("#181410", "#120d0a", "#3a2a1f"),
        ][n % 4]
        kwargs = {"x": 320.0 + n * 26.0, "y": 150.0 + n * 40.0}
        if source in self._PRESET_NAMES:
            kwargs["name"] = self._PRESET_NAMES[source]
        bar = self.bar_set.add(**kwargs)
        bar.colors.bg, bar.colors.drag, bar.colors.face = palette
        if source in self._PRESET_NAMES:
            bar.source = source
            # compact 2:1 default sized to the current item count; user can reshape later
            bar.columns = self._compact_cols(len(self._preset_items(source)))
            self._sync_preset_bar(bar)
        self._ensure_host(bar)
        self.selected_id = bar.id
        return bar

    # ---- preset (auto-populated) bars -----------------------------------------------
    @staticmethod
    def _compact_cols(count: int) -> int:
        """Columns for a compact ~2:1 (twice as wide as tall) grid holding ``count`` items."""

        return max(2, int(round(math.sqrt(max(1, count) * 2))))

    def _preset_items(self, source: str) -> list:
        """Live, ordered widget metas backing a preset bar (empty for manual/unknown)."""

        metas = self.runtime.list_widgets()
        if source == "active":
            picked = [m for m in metas if m.enabled]
        elif source == "favorites":
            favs = self.runtime.list_favorites()
            picked = [m for m in metas if m.id in favs]
        else:
            return []
        return sorted(picked, key=lambda m: (m.name or m.id).lower())

    def _sync_preset_bar(self, bar) -> None:
        """Rebuild a preset bar's tiles row-major from its live source (compact packing)."""

        items = self._preset_items(bar.source)
        cols = max(1, bar.columns)
        bar.rows = max(1, math.ceil(len(items) / cols)) if items else 1
        bar.tiles = [
            Tile(id="a%d" % i, col=i % cols, row=i // cols, w=1, h=1, name=m.name, widget_id=m.id, deletable=False)
            for i, m in enumerate(items)
        ]

    def _sync_preset_bars(self) -> None:
        for bar in self.bar_set.bars:
            if bar.source != "manual":
                self._sync_preset_bar(bar)

    def _remove_bar(self, bar_id: str) -> None:
        ok = self.bar_set.remove(bar_id)
        self._log("_remove_bar(id=%s) removed=%s -> %d bar(s) left" % (bar_id, ok, len(self.bar_set.bars)))
        self.hosts.pop(bar_id, None)
        if self.selected_id == bar_id:
            self.selected_id = self.bar_set.bars[0].id if self.bar_set.bars else ""
        if self.editing_id == bar_id:
            self.editing_id = None
            self.selected_tile_id = None

    def selected_bar(self):
        return self.bar_set.get(self.selected_id)

    def _log(self, msg: str) -> None:
        """Emit to the Py4GW console (safe no-op when running offline)."""

        try:
            import PySystem

            PySystem.Console.Log("LaunchBar", msg, PySystem.Console.MessageType.Info)
        except Exception:
            pass

    # ---- confirmations --------------------------------------------------------------
    def _ask(self, text, ok_label, action) -> None:
        """Queue a confirmation (drawn by _draw_confirmation_modal). Mirrors the InventoryPlus
        trigger: raise a pending flag and stash the message/label/action for the modal to use."""

        self._confirm_pending = True
        self._confirm_text = text
        self._confirm_ok_label = ok_label
        self._confirm_action = action

    def request_delete_bar(self, bar) -> None:
        self._log('request_delete_bar("%s" id=%s) -> queuing confirm modal' % (bar.name, bar.id))
        self._ask(
            'Delete launchpad "%s" and its %d item(s)? This cannot be undone.' % (bar.name, len(bar.tiles)),
            "Delete",
            lambda: self._remove_bar(bar.id),
        )

    def _confirm_delete_tile(self, bar, tile_id) -> None:
        tile = bar.get_tile(tile_id)
        size = ("%dx%d" % (tile.w, tile.h)) if tile is not None else ""
        self._ask(
            "Remove the %s item? This cannot be undone." % size,
            "Remove",
            lambda: self._do_delete_tile(bar, tile_id),
        )

    def _do_delete_tile(self, bar, tile_id) -> None:
        bar.remove_tile(tile_id)
        if self.selected_tile_id == tile_id:
            self.selected_tile_id = None

    # ---- per-frame ------------------------------------------------------------------
    def draw(self, now_ms: float) -> None:
        self._sync_preset_bars()   # active/favorites bars follow the live widget set each frame
        for bar in list(self.bar_set.bars):
            self._ensure_host(bar).draw(self, now_ms)
        if self.editor_open:
            self._draw_settings()
            self._draw_items()
        if self.browser_open:
            self._draw_browser()
        # Widget-manager lifecycle the launchpad now owns (moved off Py4GW_widget_manager):
        # render any open configure() panels + the System-widget disable confirmation modal.
        self.runtime.draw_configuring()
        self.runtime.draw_disable_confirmation()
        self._persist()

    # ---- persistence (account Settings document) ------------------------------------
    def _persist(self) -> None:
        """Mirror the current state into the Settings document each frame.

        We do NOT throttle or force-save: ``Settings.set`` dedups an unchanged value (so a frame
        with no changes writes nothing), and the native settings system is self-throttled — it owns
        the debounced disk write and the shutdown flush. See ``Settings`` for the contract.
        """
        try:
            from .persistence import save_state

            save_state(self.bar_set.to_dict())
        except Exception:
            pass

    # ---- shared widgets -------------------------------------------------------------
    def _num_row(self, label, value, lo, hi, is_int=False, fmt="%.2f"):
        """A slider paired with a typed number input; returns the clamped value."""

        PyImGui.text(label)
        PyImGui.push_item_width(120.0)
        if is_int:
            v = PyImGui.slider_int("##%s_s" % label, int(value), int(lo), int(hi))
        else:
            v = PyImGui.slider_float("##%s_s" % label, float(value), float(lo), float(hi))
        PyImGui.pop_item_width()
        PyImGui.same_line(0.0, 6.0)
        PyImGui.push_item_width(58.0)
        if is_int:
            v = PyImGui.input_int("##%s_n" % label, int(v), 0, 0)
        else:
            v = PyImGui.input_float("##%s_n" % label, float(v), 0.0, 0.0, fmt)
        PyImGui.pop_item_width()
        return max(lo, min(hi, v))

    def _stepper(self, label, value):
        """Label + [-][value][+]; returns the new value (unchanged if no button pressed)."""

        result = value
        PyImGui.text("%s: %d" % (label, value))
        PyImGui.same_line(0.0, 6.0)
        if PyImGui.button("-##%s_m" % label):
            result = value - 1
        PyImGui.same_line(0.0, 3.0)
        if PyImGui.button("+##%s_p" % label):
            result = value + 1
        return result

    def _color_row(self, label, hex_value, alpha):
        r, g, b = _parse_hex(hex_value)
        nr, ng, nb, na = PyImGui.color_edit4(label, (r / 255.0, g / 255.0, b / 255.0, float(alpha)))
        return _to_hex(nr * 255, ng * 255, nb * 255), na

    def _color_row3(self, label, hex_value):
        r, g, b = _parse_hex(hex_value)
        nr, ng, nb = PyImGui.color_edit3(label, (r / 255.0, g / 255.0, b / 255.0))
        return _to_hex(nr * 255, ng * 255, nb * 255)

    # ---- settings window (tabs) -----------------------------------------------------
    def _draw_settings(self) -> None:
        # WindowFlags.Docking is the opt-in dockable bit (1<<30); without it DefaultWindowFlags
        # injects NoDocking. No NoSavedSettings: this is a movable/dockable window, so imgui.ini
        # owns its placement + dock layout (project decision) and remembers it across sessions.
        flags = PyImGui.WindowFlags.Docking
        PyImGui.set_next_window_size((278.0, 540.0), PyImGui.ImGuiCond.FirstUseEver)
        PyImGui.set_next_window_pos((16.0, 16.0), PyImGui.ImGuiCond.FirstUseEver)
        if PyImGui.begin("Launch Bars##launchbar_settings", flags):
            # --- toolbar: add / close (delete lives on each tab's X now) ----
            if PyImGui.button("+ Add launchpad##lb_add"):
                self._add_bar_menu_pending = True
            PyImGui.same_line(0.0, 6.0)
            if PyImGui.button("Close editor##lb_close"):
                self.editor_open = False
            PyImGui.separator()
            if PyImGui.begin_tab_bar("launchbar_tabs"):
                for bar in list(self.bar_set.bars):
                    # System bar: no close X. Every other bar: closable tab -> X asks to delete.
                    if bar.system:
                        visible, still_open = PyImGui.begin_tab_item("%s##tab_%s" % (bar.name, bar.id)), True
                    else:
                        visible, still_open = PyImGui.begin_tab_item_closable("%s##tab_%s" % (bar.name, bar.id), True, 0)
                    if visible:
                        self.selected_id = bar.id
                        self._draw_bar_tab(bar)
                        PyImGui.end_tab_item()
                    if not still_open:   # the tab's X was clicked
                        self._log('tab X clicked on "%s" (id=%s)' % (bar.name, bar.id))
                        self.request_delete_bar(bar)
                # "+" pseudo-tab to add a launchpad (opens the template menu)
                if PyImGui.tab_item_button("+##launchbar_addtab"):
                    self._add_bar_menu_pending = True
                PyImGui.end_tab_bar()

            # Add-launchpad menu — guarded open (like the confirm modal) so open_popup + begin_popup
            # run at the SAME window id-stack level, AFTER the tab bar. Never opened from inside it.
            if self._add_bar_menu_pending:
                PyImGui.open_popup("launchbar_add_bar")
                self._add_bar_menu_pending = False
            if PyImGui.begin_popup("launchbar_add_bar"):
                PyImGui.text_disabled("Add launchpad")
                if PyImGui.menu_item("Empty bar"):
                    self.add_bar()
                PyImGui.separator()
                if PyImGui.menu_item("Active widgets (auto)"):
                    self.add_bar("active")
                if PyImGui.menu_item("Favorites (auto)"):
                    self.add_bar("favorites")
                PyImGui.end_popup()

            # Confirm modal INSIDE this window so open_popup + begin_popup_modal share the same
            # id-stack level (Dear ImGui requirement). All confirm triggers live in the editor.
            self._draw_confirmation_modal()
        PyImGui.end()

    def _draw_bar_tab(self, bar) -> None:
        PyImGui.push_id(bar.id)

        if PyImGui.collapsing_header("Layout"):
            PyImGui.text("Handle side")
            for side, glyph in _SIDES:
                PyImGui.same_line(0.0, 4.0)
                tag = "[%s]" % glyph if bar.side == side else " %s " % glyph
                if PyImGui.button("%s##side_%s" % (tag, side.value)):
                    self._ensure_host(bar).set_side(side)
            bar.scale = self._num_row("Scale", bar.scale, 0.8, 3.5, fmt="%.2f")
            bar.base_cell = self._num_row("Cell (px)", bar.base_cell, 12, 48, is_int=True)
            bar.base_gap = self._num_row("Gap (px)", bar.base_gap, 0, 8, is_int=True)
            bar.idle_opacity = self._num_row("Idle opacity", bar.idle_opacity, 0.15, 1.0, fmt="%.2f")
            nc = self._stepper("Columns", bar.columns)
            if nc != bar.columns:
                self._apply_grid_dim(bar, "columns", nc)
            nr = self._stepper("Rows", bar.rows)
            if nr != bar.rows:
                self._apply_grid_dim(bar, "rows", nr)

        if PyImGui.collapsing_header("Colors"):
            bar.colors.bg, bar.colors.bg_a = self._color_row("Background", bar.colors.bg, bar.colors.bg_a)
            bar.colors.drag, bar.colors.drag_a = self._color_row("Drag bar", bar.colors.drag, bar.colors.drag_a)
            bar.colors.face, bar.colors.face_a = self._color_row("Button face", bar.colors.face, bar.colors.face_a)
            PyImGui.separator()
            bar.active_color = self._color_row3("Active indicator", bar.active_color)
            bar.ind_outline = PyImGui.checkbox("Outline##ind", bar.ind_outline)
            PyImGui.same_line(0.0, 10.0)
            bar.ind_mask = PyImGui.checkbox("Mask##ind", bar.ind_mask)

        PyImGui.separator()
        editing = self.editing_id == bar.id
        if PyImGui.button(("Edit mode: ON" if editing else "Edit mode: OFF") + "##em"):
            self.editing_id = None if editing else bar.id
            self.selected_tile_id = None
        if len(self.bar_set.bars) > 1 and not bar.system:
            if PyImGui.button("Delete this launchpad##delbar"):
                self.request_delete_bar(bar)

        PyImGui.pop_id()

    def _apply_grid_dim(self, bar, dim, new_value) -> None:
        new_value = max(1, int(new_value))
        current = getattr(bar, dim)
        if new_value == current:
            return
        if bar.source != "manual":
            # auto bars re-pack to fit every frame — no tiles are ever "dropped"
            setattr(bar, dim, new_value)
            return
        if new_value < current:
            nc = new_value if dim == "columns" else bar.columns
            nr = new_value if dim == "rows" else bar.rows
            dropped = [t for t in bar.tiles if t.col + t.w > nc or t.row + t.h > nr]
            if dropped:
                self._ask(
                    "Reducing to %dx%d removes %d item(s) that no longer fit. Continue?" % (nc, nr, len(dropped)),
                    "Shrink & remove",
                    lambda: self._do_shrink(bar, dim, new_value),
                )
                return
        setattr(bar, dim, new_value)

    def _do_shrink(self, bar, dim, new_value) -> None:
        setattr(bar, dim, int(new_value))
        removed = bar.clamp_tiles()
        if self.selected_tile_id in removed:
            self.selected_tile_id = None

    # ---- items window (dedicated, roomy) --------------------------------------------
    def _draw_items(self) -> None:
        bar = self.selected_bar()
        if bar is None:
            return
        flags = PyImGui.WindowFlags.Docking   # movable/dockable; imgui.ini owns placement
        PyImGui.set_next_window_size((266.0, 540.0), PyImGui.ImGuiCond.FirstUseEver)
        PyImGui.set_next_window_pos((306.0, 16.0), PyImGui.ImGuiCond.FirstUseEver)
        if PyImGui.begin("Items##launchbar_items", flags):
            PyImGui.text("%s  -  %d item(s)" % (bar.name, len(bar.tiles)))
            if bar.source != "manual":
                # auto-populated: content follows the live set; only width is user-controlled
                PyImGui.text_disabled("Auto-populated from %s widgets." % bar.source)
                PyImGui.text_disabled("Buttons appear/disappear with the live set;")
                PyImGui.text_disabled("set the width in Layout > Columns.")
                PyImGui.separator()
                for tile in list(bar.tiles):
                    PyImGui.text(tile.name or tile.widget_id or "?")
                PyImGui.end()
                return
            self.new_tile_w = max(1, self._stepper("New W", self.new_tile_w))
            self.new_tile_h = max(1, self._stepper("New H", self.new_tile_h))
            if PyImGui.button("+ Add item##additem"):
                tile = bar.add_tile(self.new_tile_w, self.new_tile_h)
                if tile is not None:
                    self.editing_id = bar.id
                    self.selected_tile_id = tile.id
            PyImGui.separator()
            for tile in list(bar.tiles):
                PyImGui.push_id(tile.id)
                if tile.name:
                    label = tile.name
                elif tile.action:
                    label = "<action:%s>" % tile.action
                elif tile.function_id:
                    label = "<fn:%s>" % tile.function_id
                else:
                    label = "<empty>"
                if PyImGui.collapsing_header("%s  -  %dx%d  (%d,%d)" % (label, tile.w, tile.h, tile.col, tile.row)):
                    self.selected_tile_id = tile.id
                    self.editing_id = bar.id
                    # --- binding: link a widget to this button (inline search picker) ---
                    self._draw_tile_binding(tile)
                    PyImGui.separator()
                    nw = self._stepper("Width", tile.w)
                    if nw != tile.w:
                        bar.resize_tile(tile.id, nw, tile.h)
                    nh = self._stepper("Height", tile.h)
                    if nh != tile.h:
                        bar.resize_tile(tile.id, tile.w, nh)
                    nx = self._stepper("X", tile.col)
                    if nx != tile.col:
                        bar.move_tile(tile.id, nx, tile.row)
                    ny = self._stepper("Y", tile.row)
                    if ny != tile.row:
                        bar.move_tile(tile.id, tile.col, ny)
                    if tile.deletable and PyImGui.button("Remove item##rmitem"):
                        self._confirm_delete_tile(bar, tile.id)
                PyImGui.pop_id()
        PyImGui.end()

    # ---- widget browser (Explorer two-pane, in browser.py) --------------------------
    def _draw_browser(self) -> None:
        self.browser.draw(self)

    def _pin_widget(self, widget_id) -> None:
        """Approach A: pin a widget from the browser as a NEW button on the selected launchpad."""

        bar = self.selected_bar()
        if bar is None:
            return
        tile = bar.add_tile(1, 1)
        if tile is not None:
            self._bind_tile(tile, widget_id)
            self.selected_tile_id = tile.id

    # ---- bind a widget / function / icon to an EXISTING tile ------------------------
    # widget_id and function_id are mutually exclusive; binding one clears the other.
    def _bind_tile(self, tile, widget_id) -> None:
        tile.function_id = None
        tile.icon = None
        tile.widget_id = widget_id
        meta = self.runtime.get(widget_id)
        tile.name = meta.name if meta is not None else widget_id

    def _bind_function(self, tile, function_id) -> None:
        tile.widget_id = None
        tile.function_id = function_id
        fmeta = self.functions.get(function_id)
        tile.name = fmeta.name if fmeta is not None else function_id
        # seed the tile's icon from the catalog default (user can override via the icon picker)
        tile.icon = fmeta.icon if fmeta is not None else None

    def _find_tile(self, tile_id):
        for bar in self.bar_set.bars:
            t = bar.get_tile(tile_id)
            if t is not None:
                return t
        return None

    def start_assign(self, tile_id, mode="widget") -> None:
        """Open an inline picker for this tile. ``mode`` = "widget" | "function" | "icon"."""

        self.assign_tile_id = tile_id
        self.assign_mode = mode
        self.assign_search = ""
        self.icon_search = ""

    def cancel_assign(self) -> None:
        self.assign_tile_id = None

    def assign_widget(self, widget_id) -> None:
        """Bind the picked widget to the tile whose picker is open, then close it."""

        tile = self._find_tile(self.assign_tile_id) if self.assign_tile_id else None
        if tile is not None:
            self._bind_tile(tile, widget_id)
            self.selected_tile_id = tile.id
            self._log("assigned widget %s to tile %s" % (widget_id, tile.id))
        self.assign_tile_id = None

    def assign_function(self, function_id) -> None:
        """Bind the picked catalog function to the tile whose picker is open, then close it."""

        tile = self._find_tile(self.assign_tile_id) if self.assign_tile_id else None
        if tile is not None:
            self._bind_function(tile, function_id)
            self.selected_tile_id = tile.id
            self._log("assigned function %s to tile %s" % (function_id, tile.id))
        self.assign_tile_id = None

    def set_tile_icon(self, tile, icon_name) -> None:
        """Override a function tile's Font Awesome glyph, then close the icon picker."""

        tile.icon = icon_name
        self.assign_tile_id = None

    def clear_tile_binding(self, tile) -> None:
        tile.widget_id = None
        tile.function_id = None
        tile.icon = None
        tile.name = ""

    def _icon_entries(self):
        """Cached ``(name, glyph)`` list for the icon picker (built once, empty offline)."""

        if self._icon_cache is None:
            self._icon_cache = list_icons()
        return self._icon_cache

    def _draw_tile_binding(self, tile) -> None:
        """Bind a widget or a catalog function to this button via inline search pickers."""

        if tile.action:
            PyImGui.text_disabled("System action: %s" % tile.action)
            return
        assigning = self.assign_tile_id == tile.id
        if not assigning:
            if tile.widget_id:
                PyImGui.text("Widget: %s" % (tile.name or tile.widget_id))
                if PyImGui.button("Change widget...##chgw"):
                    self.start_assign(tile.id, "widget")
                PyImGui.same_line(0.0, 6.0)
                if PyImGui.button("Clear##clrbind"):
                    self.clear_tile_binding(tile)
                return
            if tile.function_id:
                fmeta = self.functions.get(tile.function_id)
                PyImGui.text("Function: %s" % (tile.name or (fmeta.name if fmeta else tile.function_id)))
                glyph = resolve_icon(tile.icon)
                PyImGui.text_disabled("Icon: %s %s" % (glyph or "", tile.icon or "(default)"))
                if PyImGui.button("Change function...##chgf"):
                    self.start_assign(tile.id, "function")
                PyImGui.same_line(0.0, 6.0)
                if PyImGui.button("Change icon...##chgi"):
                    self.start_assign(tile.id, "icon")
                PyImGui.same_line(0.0, 6.0)
                if PyImGui.button("Clear##clrbind"):
                    self.clear_tile_binding(tile)
                return
            PyImGui.text_disabled("No binding.")
            if PyImGui.button("Assign widget...##asgw"):
                self.start_assign(tile.id, "widget")
            PyImGui.same_line(0.0, 6.0)
            if PyImGui.button("Assign function...##asgf"):
                self.start_assign(tile.id, "function")
            return
        # --- an inline picker is open for this tile: dispatch by mode ---
        if self.assign_mode == "function":
            self._draw_function_picker()
        elif self.assign_mode == "icon":
            self._draw_icon_picker(tile)
        else:
            self._draw_widget_picker()
        if PyImGui.button("Cancel##canasg"):
            self.cancel_assign()

    def _draw_widget_picker(self) -> None:
        self.assign_search = PyImGui.input_text("Search##asgsearch", self.assign_search)
        q = self.assign_search.lower().strip()
        if PyImGui.begin_child("##asglist", (0.0, 130.0), True):
            shown = 0
            for m in sorted(self.runtime.list_widgets(), key=lambda x: (x.name or x.id).lower()):
                if q and q not in (m.name or "").lower() and q not in m.id.lower():
                    continue
                if PyImGui.selectable("%s##pick_%s" % (m.name or m.id, m.id), False, 0, (0.0, 0.0)):
                    self.assign_widget(m.id)
                shown += 1
            if shown == 0:
                PyImGui.text_disabled("No widgets match.")
        PyImGui.end_child()

    def _draw_function_picker(self) -> None:
        self.assign_search = PyImGui.input_text("Search##asgfsearch", self.assign_search)
        q = self.assign_search.lower().strip()
        if PyImGui.begin_child("##asgflist", (0.0, 220.0), True):
            # build group -> category -> [functions], applying the search filter
            tree: dict = {}
            for f in self.functions.list_functions():
                if q and q not in f.name.lower() and q not in f.id.lower() \
                        and q not in (f.category or "").lower() and q not in (f.group or "").lower():
                    continue
                g = f.group or "Uncategorized"
                c = f.category or "General"
                tree.setdefault(g, {}).setdefault(c, []).append(f)
            if not tree:
                PyImGui.text_disabled("No functions match. Add some in functions_catalog.py.")
            for g in sorted(tree, key=str.lower):                 # top-level group
                PyImGui.text_disabled(g)
                for c in sorted(tree[g], key=str.lower):          # subcategory under the group
                    PyImGui.indent(10)
                    PyImGui.text_disabled(c)
                    PyImGui.indent(10)
                    for f in sorted(tree[g][c], key=lambda x: x.name.lower()):
                        glyph = resolve_icon(f.icon)
                        label = ("%s  %s" % (glyph, f.name)) if glyph else f.name
                        if PyImGui.selectable("%s##pickf_%s" % (label, f.id), False, 0, (0.0, 0.0)):
                            self.assign_function(f.id)
                    PyImGui.unindent(10)
                    PyImGui.unindent(10)
        PyImGui.end_child()

    def _draw_icon_picker(self, tile) -> None:
        self.icon_search = PyImGui.input_text("Search##asgisearch", self.icon_search)
        q = self.icon_search.lower().strip()
        cols = 6
        if PyImGui.begin_child("##asgilist", (0.0, 210.0), True):
            shown = 0
            if PyImGui.begin_table("##icongrid", cols, 0):
                col = 0
                for name, glyph in self._icon_entries():
                    if q and q not in name.lower():
                        continue
                    if col == 0:
                        PyImGui.table_next_row(0, 30)
                    PyImGui.table_set_column_index(col)
                    if PyImGui.button("%s##ic_%s" % (glyph, name), 0.0, 0.0):
                        self.set_tile_icon(tile, name)
                    if PyImGui.is_item_hovered():
                        PyImGui.set_item_tooltip(name)
                    shown += 1
                    col = (col + 1) % cols
                PyImGui.end_table()
            if shown == 0:
                PyImGui.text_disabled("No icons match." if self._icon_entries() else "Icons unavailable offline.")
        PyImGui.end_child()

    # ---- confirmation modal (centered, blocks all other input) ----------------------
    def _draw_confirmation_modal(self) -> None:
        # EXACT clone of InventoryPlus._draw_destroy_confirmation_modal (a proven widget modal):
        #   if pending: open_popup(ID); pending = False       # open ONCE
        #   if not begin_popup_modal(ID, True, AlwaysAutoResize): return
        #   <message>; separator; Yes-button + No-button, each close_current_popup(); end_popup()
        # No get_io / set_next_window_pos / centering — none of that exists in the working version.
        # MUST be called from inside a real window (see _draw_settings) so open_popup and
        # begin_popup_modal share the same id-stack level.
        if self._confirm_pending:
            PyImGui.open_popup("LaunchBarConfirm")
            self._confirm_pending = False

        if not PyImGui.begin_popup_modal("LaunchBarConfirm", True, PyImGui.WindowFlags.AlwaysAutoResize):
            return

        PyImGui.text(self._confirm_text)
        PyImGui.separator()

        if PyImGui.button("%s##confirm_ok" % (self._confirm_ok_label or "OK"), 80, 0):
            action = self._confirm_action
            self._confirm_action = None
            PyImGui.close_current_popup()
            self._log("confirm OK -> running action")
            if action:
                action()
        PyImGui.same_line(0, -1)
        if PyImGui.button("Cancel##confirm_no", 80, 0):
            self._confirm_action = None
            PyImGui.close_current_popup()

        PyImGui.end_popup()
