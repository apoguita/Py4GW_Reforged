"""Widget browser — Windows-Explorer-style two-pane browser (the WM UI replacement).

Faithful to the approved HTML mock:
- **Address bar:** back / forward / up + a clickable **breadcrumb** (selection history).
- **Left pane:** search box, virtual **buckets** (All / Active / Favorites / Inactive), a
  separator, then the **folder tree** (folders only; caret expands, name selects).
- **Right pane:** the selected node's **subfolders** (click to drill in) **and its own
  widgets**. Each widget row: puzzle icon + name (click toggles; green when active) + a right
  cluster of ★ favorite, ⚙ configure, and 📌 pin.

Consumes ``manager.runtime`` (WidgetRuntime) + ``manager._pin_widget``. Kept light: a cheap
folder-tree rebuild from the metadata, plain selectables/rows, no per-frame snapshot churn.
"""

import PyImGui

try:  # real FontAwesome glyphs in-client; ASCII fallback keeps the module import-safe offline
    from Py4GWCoreLib.ImGui_Legacy_src.IconsFontAwesome5 import IconsFontAwesome5 as _IC
except Exception:  # pragma: no cover

    class _IC:
        ICON_ARROW_LEFT = "<"
        ICON_ARROW_RIGHT = ">"
        ICON_LEVEL_UP_ALT = "^"
        ICON_ANGLE_RIGHT = ">"
        ICON_CARET_RIGHT = "+"
        ICON_CARET_DOWN = "-"
        ICON_FOLDER = "[]"
        ICON_STAR = "*"
        ICON_COG = "cfg"
        ICON_THUMBTACK = "pin"
        ICON_SEARCH = "search"
        ICON_PUZZLE_PIECE = "-"
        ICON_PAUSE = "||"
        ICON_PLAY = ">"
        ICON_USERS = "@@"
        ICON_SYNC = "R"


_VIRTUALS = [("@all", "All"), ("@active", "Active"), ("@favorites", "Favorites"), ("@inactive", "Inactive")]
_VNAME = dict(_VIRTUALS)


class WidgetBrowser:
    """Transient UI state for the browser window (one instance, owned by the manager)."""

    def __init__(self) -> None:
        self.current = "@all"
        self.search = ""
        self.history = ["@all"]
        self.hist_index = 0
        self.expanded: set = set()      # folder paths expanded in the tree
        self._fav_cache: set = set()    # favorites snapshot for THIS frame (shared WM store)
        self.left_width = 170.0         # tree pane width (draggable splitter)

    # ---- navigation history ---------------------------------------------------------
    def _apply(self, sel: str) -> None:
        self.current = sel
        if not sel.startswith("@"):
            self.expanded.add(sel)

    def _navigate(self, sel: str) -> None:
        if sel == self.current:
            return
        del self.history[self.hist_index + 1:]
        self.history.append(sel)
        self.hist_index = len(self.history) - 1
        self._apply(sel)

    def _back(self) -> None:
        if self.hist_index > 0:
            self.hist_index -= 1
            self._apply(self.history[self.hist_index])

    def _forward(self) -> None:
        if self.hist_index < len(self.history) - 1:
            self.hist_index += 1
            self._apply(self.history[self.hist_index])

    def _up(self) -> None:
        if self.current.startswith("@"):
            return
        parts = self.current.split("/")
        parts.pop()
        self._navigate("/".join(parts) if parts else "@all")

    def _crumbs(self):
        if self.current.startswith("@"):
            return [(_VNAME.get(self.current, "All"), self.current)]
        out = [("All", "@all")]
        acc = ""
        for p in self.current.split("/"):
            acc = p if not acc else acc + "/" + p
            out.append((p, acc))
        return out

    # ---- tree + filters -------------------------------------------------------------
    def _build_tree(self, metas):
        root = {"name": "", "path": "", "folders": {}, "widgets": []}
        for m in metas:
            parts = [p for p in m.folder.split("/") if p] if m.folder else []
            node = root
            acc = ""
            for p in parts:
                acc = p if not acc else acc + "/" + p
                node = node["folders"].setdefault(p, {"name": p, "path": acc, "folders": {}, "widgets": []})
            node["widgets"].append(m)
        return root

    def _folder_at(self, tree, path):
        node = tree
        for p in path.split("/"):
            node = node["folders"].get(p)
            if node is None:
                return None
        return node

    def _bucket_ok(self, key: str, m) -> bool:
        if key == "@active":
            return m.enabled
        if key == "@inactive":
            return not m.enabled
        if key == "@favorites":
            return m.id in self._fav_cache
        return True

    def _search_ok(self, m) -> bool:
        q = self.search.lower().strip()
        return not q or q in m.name.lower() or q in m.category.lower() or q in m.id.lower()

    # ---- draw -----------------------------------------------------------------------
    def draw(self, manager) -> None:
        metas = manager.runtime.list_widgets()
        self._fav_cache = manager.runtime.list_favorites()   # read the shared WM favorites once/frame
        tree = self._build_tree(metas)

        PyImGui.set_next_window_size((560.0, 440.0), PyImGui.ImGuiCond.FirstUseEver)
        # movable/dockable; imgui.ini owns placement (no NoSavedSettings, no forced position)
        if PyImGui.begin("Widget browser##launchbar_browser", PyImGui.WindowFlags.Docking):
            self._draw_address(manager)
            PyImGui.separator()
            avail = PyImGui.get_content_region_avail()
            height = avail[1]
            self.left_width = max(120.0, min(avail[0] - 130.0, self.left_width))
            if PyImGui.begin_child("##br_left", (self.left_width, height), True):
                self.search = PyImGui.input_text("%s##br_search" % _IC.ICON_SEARCH, self.search)
                self._draw_buckets(metas)
                PyImGui.separator()
                self._draw_tree(tree, 0)
            PyImGui.end_child()
            PyImGui.same_line(0.0, 0.0)
            self._draw_splitter(height)
            PyImGui.same_line(0.0, 0.0)
            if PyImGui.begin_child("##br_right", (0.0, height), True):
                self._draw_details(manager, metas, tree)
            PyImGui.end_child()
        PyImGui.end()

    def _draw_splitter(self, height: float) -> None:
        PyImGui.push_style_color(PyImGui.ImGuiCol.Button, (1.0, 1.0, 1.0, 0.06))
        PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonHovered, (0.40, 0.55, 0.85, 0.5))
        PyImGui.push_style_color(PyImGui.ImGuiCol.ButtonActive, (0.40, 0.55, 0.85, 0.8))
        PyImGui.button("##br_split", 7.0, height)
        PyImGui.pop_style_color(3)
        if PyImGui.is_item_active():
            dx = PyImGui.get_mouse_drag_delta(0)[0]
            if dx != 0.0:
                self.left_width += dx
                PyImGui.reset_mouse_drag_delta(0)

    def _nav_button(self, label: str, enabled: bool, action) -> None:
        if not enabled:
            PyImGui.begin_disabled()
        if PyImGui.button(label):
            action()
        if not enabled:
            PyImGui.end_disabled()

    def _draw_address(self, manager) -> None:
        self._nav_button(_IC.ICON_ARROW_LEFT + "##br_back", self.hist_index > 0, self._back)
        PyImGui.same_line(0.0, 3.0)
        self._nav_button(_IC.ICON_ARROW_RIGHT + "##br_fwd", self.hist_index < len(self.history) - 1, self._forward)
        PyImGui.same_line(0.0, 3.0)
        self._nav_button(_IC.ICON_LEVEL_UP_ALT + "##br_up", not self.current.startswith("@"), self._up)

        # breadcrumb — every segment is a clickable button (Windows-Explorer / WM style)
        crumbs = self._crumbs()
        for i, (label, sel) in enumerate(crumbs):
            PyImGui.same_line(0.0, 6.0 if i == 0 else 1.0)
            text = ("/" + label) if i else label
            if PyImGui.small_button("%s##cr_%d" % (text, i)):
                self._navigate(sel)

        # global widget-manager actions (like the old WM toolbar) — right cluster
        PyImGui.same_line(0.0, 12.0)
        self._draw_global_actions(manager)
        PyImGui.same_line(0.0, 6.0)
        if PyImGui.small_button("Close##br_close"):
            manager.browser_open = False

    def _draw_global_actions(self, manager) -> None:
        """The old WM toolbar's global actions: reload all, pause/resume all, multibox pause."""

        rt = manager.runtime
        # reload all widgets
        if PyImGui.small_button(_IC.ICON_SYNC + "##br_reload"):
            rt.reload_all()
        if PyImGui.is_item_hovered():
            PyImGui.set_tooltip("Reload all widgets")
        # pause / resume every widget on this client
        PyImGui.same_line(0.0, 4.0)
        all_paused = rt.is_all_paused()
        glyph = _IC.ICON_PLAY if all_paused else _IC.ICON_PAUSE
        if all_paused:
            PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (0.98, 0.55, 0.35, 1.0))   # red-ish while all paused
        clicked_all = PyImGui.small_button("%s##br_pauseall" % glyph)
        if all_paused:
            PyImGui.pop_style_color(1)
        if clicked_all:
            rt.toggle_pause_all()
        if PyImGui.is_item_hovered():
            PyImGui.set_tooltip("Resume all widgets" if all_paused else "Pause all widgets")
        # pause / resume optional widgets on ALL accounts (multibox)
        PyImGui.same_line(0.0, 4.0)
        self._draw_multibox_toggle(manager)

    def _draw_multibox_toggle(self, manager) -> None:
        """Pause/resume every optional widget on ALL accounts (old WM 'Pause Non-Env' toggle).

        Delegates to WidgetHandler.toggle_optional_widgets_paused, which also broadcasts
        PauseWidgets/ResumeWidgets to the other accounts over shared memory.
        """
        rt = manager.runtime
        paused = rt.is_optional_paused()
        glyph = _IC.ICON_PLAY if paused else _IC.ICON_PAUSE
        if paused:
            PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (0.98, 0.70, 0.25, 1.0))   # amber while paused
        clicked = PyImGui.small_button("%s##br_multibox" % glyph)
        if paused:
            PyImGui.pop_style_color(1)
        if clicked:
            rt.toggle_optional_paused()
        if PyImGui.is_item_hovered():
            PyImGui.set_tooltip(
                "Resume optional widgets on all accounts" if paused else "Pause optional widgets on all accounts"
            )

    def _draw_buckets(self, metas) -> None:
        for key, name in _VIRTUALS:
            count = sum(1 for m in metas if self._bucket_ok(key, m))
            if PyImGui.selectable("%s (%d)##v_%s" % (name, count, key), self.current == key):
                self._navigate(key)

    def _draw_tree(self, node, depth: int) -> None:
        for key in sorted(node["folders"]):
            f = node["folders"][key]
            has_sub = bool(f["folders"])
            is_open = f["path"] in self.expanded
            PyImGui.set_cursor_pos_x(6.0 + depth * 14.0)
            if has_sub:
                caret = _IC.ICON_CARET_DOWN if is_open else _IC.ICON_CARET_RIGHT
                if PyImGui.small_button("%s##c_%s" % (caret, f["path"])):
                    self.expanded.discard(f["path"]) if is_open else self.expanded.add(f["path"])
                PyImGui.same_line(0.0, 3.0)
            else:
                PyImGui.dummy((16.0, 1.0))
                PyImGui.same_line(0.0, 3.0)
            if PyImGui.selectable("%s %s##f_%s" % (_IC.ICON_FOLDER, f["name"], f["path"]), self.current == f["path"]):
                self._navigate(f["path"])
            if has_sub and is_open:
                self._draw_tree(f, depth + 1)

    def _draw_details(self, manager, metas, tree) -> None:
        subs = []
        if self.search.strip():
            label = 'Search "%s"' % self.search.strip()
            items = [m for m in metas if self._search_ok(m)]
        elif self.current.startswith("@"):
            label = _VNAME.get(self.current, "All")
            items = [m for m in metas if self._bucket_ok(self.current, m)]
        else:
            node = self._folder_at(tree, self.current)
            label = self.current
            subs = [node["folders"][k] for k in sorted(node["folders"])] if node else []
            items = list(node["widgets"]) if node else []

        summary = "%s  -  %d widget(s)" % (label, len(items))
        if subs:
            summary += ", %d folder(s)" % len(subs)
        PyImGui.text_disabled(summary)
        PyImGui.separator()

        for f in subs:
            if PyImGui.selectable("%s %s##rf_%s" % (_IC.ICON_FOLDER, f["name"], f["path"])):
                self._navigate(f["path"])
        for m in sorted(items, key=lambda x: x.name.lower()):
            self._draw_widget_row(manager, m)
        if not subs and not items:
            PyImGui.text_disabled("No widgets here.")

    def _draw_widget_row(self, manager, m) -> None:
        PyImGui.push_id(m.id)
        iw = 24.0  # fixed icon-button width so ★ / ⚙ / 📌 stay in aligned columns
        avail_x = PyImGui.get_content_region_avail()[0]
        name_w = max(70.0, avail_x - (iw * 3.0 + 12.0))
        faved = m.id in self._fav_cache

        if m.enabled:
            PyImGui.push_style_color(PyImGui.ImGuiCol.Header, (0.27, 0.55, 0.33, 0.55))
        clicked = PyImGui.selectable("%s %s##n" % (_IC.ICON_PUZZLE_PIECE, m.name), m.enabled, 0, (name_w, 0.0))
        if m.enabled:
            PyImGui.pop_style_color(1)
        if clicked:
            manager.runtime.toggle(m.id)
        # tooltip: prefer the widget's OWN tooltip (each loaded widget can define one); only fall
        # back to a plain name/category/state tooltip when the widget has none.
        if PyImGui.is_item_hovered():
            if not manager.runtime.draw_tooltip(m.id):
                state = "Active - click to stop" if m.enabled else "Inactive - click to launch"
                PyImGui.begin_tooltip()
                PyImGui.text(m.name)
                PyImGui.text_disabled(m.category)
                PyImGui.text_disabled(state)
                PyImGui.end_tooltip()

        # favorite
        PyImGui.same_line(0.0, 4.0)
        if faved:
            PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (0.95, 0.77, 0.06, 1.0))
        if PyImGui.button(_IC.ICON_STAR + "##fav", iw, 0.0):
            manager.runtime.toggle_favorite(m.id)      # persist to the shared WM store
            self._fav_cache = manager.runtime.list_favorites()
        if faved:
            PyImGui.pop_style_color(1)

        # configure column — reserved even when the widget has no config (keeps ★/📌 aligned)
        PyImGui.same_line(0.0, 2.0)
        if m.configurable:
            if m.configuring:
                PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (0.40, 0.70, 1.0, 1.0))
            if PyImGui.button(_IC.ICON_COG + "##cfg", iw, 0.0):
                manager.runtime.set_configuring(m.id, not m.configuring)   # toggle: show / hide
            if m.configuring:
                PyImGui.pop_style_color(1)
        else:
            PyImGui.dummy((iw, 1.0))

        # pin
        PyImGui.same_line(0.0, 2.0)
        if PyImGui.button(_IC.ICON_THUMBTACK + "##pin", iw, 0.0):
            manager._pin_widget(m.id)
        PyImGui.pop_id()
