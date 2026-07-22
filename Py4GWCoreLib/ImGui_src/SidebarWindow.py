"""
SidebarWindow — a reusable "navigator" window: collapsible sidebar + content area.

A ``SidebarWindow`` renders a window split into two columns:

    ┌── Group (collapsible header) ──┐┌── content for the selected ────────┐
    │  ▼ Core                        ││  section: its context() runs here, │
    │      • System   (selected)     ││  OR a tab bar of its tabs, each of │
    │      • Scanner                 ││  which runs its own context()      │
    │  ▶ World & Map  (collapsed)    ││                                    │
    └────────────────────────────────┘└────────────────────────────────────┘

You describe *structure* — groups, sections, tabs — and bind each nav label to a
zero-argument **context function** (a renderer). The window owns everything else:
the window + child regions, collapsible group state, selection state (section and
tab), per-panel error isolation, markdown help, and an optional search filter.

Design goals
------------
* **Declarative:** you register (label -> context); the window shows the right one.
* **Stateful but queryable:** selection and group expand/collapse live in the
  window and are readable/settable (``selected``, ``select``, ``selected_tab``,
  ``is_group_open``, ``set_group_open``, ``expand_all``, ``collapse_all``) so a
  caller can persist them if it wants — without the class depending on any store.
* **Safe:** a context that raises renders its error inline and never tears down
  the window. Duplicate section/tab names across groups never collide (ids are
  namespaced).
* **Reusable:** layout, colors, collapsibility, default-open, indent, search and a
  selection callback are all configurable; nothing is hard-coded to one caller.

Public API (import as ``ImGui.SidebarWindow``)
----------------------------------------------
Build::

    win = ImGui.SidebarWindow("My Tool", collapsible_groups=True)
    core = win.add_group("Core")                       # -> Group
    win.add_section(core, "Overview", draw_overview, default=True)
    win.add_section(core, "Details")                   # no context -> hosts tabs
    win.add_tab("Details", "Stats", draw_stats)
    win.add_tab("Details", "Log", draw_log, help_file="log.md")

Render (once per frame)::

    win.draw()

Data model: ``Group`` (a collapsible header) -> ``Section`` (a sidebar item) ->
optional ``Tab`` (a content tab). ``Topic`` is a back-compatible alias of
``Section``; ``add_topic``/``add_topics`` still work.
"""
from __future__ import annotations

import os
from typing import Callable, Optional

import PyImGui

# A context/renderer: zero args, draws into the region the window already opened.
DrawFn = Callable[[], None]

# ImGuiCond values (no Cond enum is bound; these mirror imgui.h).
_COND_ALWAYS = 1
_COND_FIRST_USE_EVER = 4


class SidebarWindow:
    # --- palette (normalized 0..1 tuples; PyImGui.text_colored(text, color) order) ---
    MUTED_COLOR = (0.60, 0.60, 0.65, 1.0)
    ERR_COLOR = (0.90, 0.30, 0.30, 1.0)
    ACCENT_COLOR = (1.00, 0.78, 0.39, 1.0)

    # ======================================================================
    # region Data model
    # ======================================================================
    class Tab:
        """One tab inside a section's content area, bound to a context function."""

        __slots__ = ("name", "draw", "help", "help_file", "icon")

        def __init__(self, name: str, draw: DrawFn, help: Optional[str] = None,
                     help_file: Optional[str] = None, icon: str = ""):
            self.name = name
            self.draw = draw
            self.help = help
            self.help_file = help_file
            self.icon = icon

    class Section:
        """A sidebar item. Renders either a single ``draw`` context or its ``tabs``."""

        __slots__ = ("name", "draw", "tabs", "help", "help_file", "icon")

        def __init__(self, name: str, draw: Optional[DrawFn] = None,
                     tabs: "Optional[list[SidebarWindow.Tab]]" = None,
                     help: Optional[str] = None, help_file: Optional[str] = None,
                     icon: str = ""):
            self.name = name
            self.draw = draw
            self.tabs = list(tabs) if tabs else []
            self.help = help
            self.help_file = help_file
            self.icon = icon

    class Group:
        """A collapsible sidebar header holding an ordered list of sections."""

        __slots__ = ("name", "sections", "collapsible", "default_open", "icon")

        def __init__(self, name: str, collapsible: bool = True,
                     default_open: bool = True, icon: str = ""):
            self.name = name
            self.sections: "list[SidebarWindow.Section]" = []
            self.collapsible = collapsible
            self.default_open = default_open
            self.icon = icon

    # Back-compatible alias: earlier callers use ``SidebarWindow.Topic``.
    Topic = Section
    # endregion

    # ======================================================================
    # region Construction
    # ======================================================================
    def __init__(self, title: str, *, sidebar_width: float = 250.0,
                 content_width: float = 760.0, height: float = 720.0,
                 window_flags: Optional[int] = None, selected: Optional[str] = None,
                 show_help: bool = True, help_dir: str = "",
                 collapsible_groups: bool = True, default_open: bool = True,
                 indent_width: float = 12.0, show_search: bool = False,
                 on_select: "Optional[Callable[[str], None]]" = None,
                 on_close: "Optional[Callable[[], None]]" = None):
        self.title = title
        self.sidebar_width = float(sidebar_width)
        self.content_width = float(content_width)
        self.height = float(height)
        self.window_flags = int(window_flags) if window_flags is not None else int(PyImGui.WindowFlags.AlwaysAutoResize)
        self.show_help = bool(show_help)
        self.help_dir = help_dir
        self.collapsible_groups = bool(collapsible_groups)
        self.default_open = bool(default_open)
        self.indent_width = float(indent_width)
        self.show_search = bool(show_search)
        self.on_select = on_select
        self.on_close = on_close

        self._groups: "list[SidebarWindow.Group]" = []
        self._sections_by_name: "dict[str, SidebarWindow.Section]" = {}
        self._selected: Optional[str] = selected
        self._selected_tab: "dict[str, str]" = {}     # section name -> active tab
        self._group_open: "dict[str, bool]" = {}       # group name -> expanded?
        self._pending_open: "dict[str, bool]" = {}     # group name -> forced state (1 frame)
        self._help_open: "dict[str, bool]" = {}
        self._help_cache: "dict[str, str]" = {}
        self._search_text: str = ""
        self._safe_id = "".join(c if c.isalnum() else "_" for c in title) or "sidebarwin"
    # endregion

    # ======================================================================
    # region Building
    # ======================================================================
    def add_group(self, name: str, *, collapsible: Optional[bool] = None,
                  default_open: Optional[bool] = None, icon: str = "") -> "SidebarWindow.Group":
        """Create (or return the existing) group. Groups render as collapsible headers."""
        for g in self._groups:
            if g.name == name:
                return g
        grp = SidebarWindow.Group(
            name,
            collapsible=self.collapsible_groups if collapsible is None else bool(collapsible),
            default_open=self.default_open if default_open is None else bool(default_open),
            icon=icon,
        )
        self._groups.append(grp)
        self._group_open[name] = grp.default_open
        return grp

    def add_section(self, group: "SidebarWindow.Group | str", name: str,
                    context: Optional[DrawFn] = None, *,
                    tabs: "Optional[list[SidebarWindow.Tab]]" = None,
                    help: Optional[str] = None, help_file: Optional[str] = None,
                    icon: str = "", default: bool = False) -> "SidebarWindow.Section":
        """Add a sidebar section bound to its ``context`` function.

        Clicking the section auto-shows ``context``. Omit ``context`` (and later call
        :meth:`add_tab`) to make it a tabbed section. ``default=True`` selects it on
        first open.
        """
        grp = group if isinstance(group, SidebarWindow.Group) else self.add_group(group)
        section = SidebarWindow.Section(name, draw=context, tabs=tabs,
                                        help=help, help_file=help_file, icon=icon)
        grp.sections.append(section)
        self._sections_by_name[name] = section
        if default or self._selected is None:
            self._selected = name
        return section

    def add_tab(self, section: "SidebarWindow.Section | str", name: str,
                context: DrawFn, *, help: Optional[str] = None,
                help_file: Optional[str] = None, icon: str = "") -> "SidebarWindow.Tab":
        """Add a content tab bound to its ``context``. Selecting the tab auto-shows it.

        The first tab turns a section into a tabbed section (any single ``context``
        set via :meth:`add_section` is then unused). ``section`` may be a handle or a
        section name.
        """
        target = section if isinstance(section, SidebarWindow.Section) else self._sections_by_name.get(section)
        if target is None:
            raise KeyError(f"add_tab: no section named {section!r} (create it with add_section first)")
        tab = SidebarWindow.Tab(name, context, help=help, help_file=help_file, icon=icon)
        target.tabs.append(tab)
        return tab

    def add_sections(self, group: "SidebarWindow.Group | str",
                     sections: "list[SidebarWindow.Section]") -> None:
        for s in sections:
            grp = group if isinstance(group, SidebarWindow.Group) else self.add_group(group)
            grp.sections.append(s)
            self._sections_by_name[s.name] = s
            if self._selected is None:
                self._selected = s.name

    # --- back-compat aliases (older callers) ---
    def add_topic(self, group: "SidebarWindow.Group | str",
                  topic: "SidebarWindow.Section") -> "SidebarWindow.Section":
        self.add_sections(group, [topic])
        return topic

    def add_topics(self, group: "SidebarWindow.Group | str",
                   topics: "list[SidebarWindow.Section]") -> None:
        self.add_sections(group, topics)
    # endregion

    # ======================================================================
    # region Selection / state (queryable + settable; persist externally if wanted)
    # ======================================================================
    @property
    def selected(self) -> Optional[str]:
        return self._selected

    def select(self, name: str) -> None:
        if name in self._sections_by_name and name != self._selected:
            self._selected = name
            self._fire_select(name)

    def selected_tab(self, section: str) -> Optional[str]:
        """Active tab name for a tabbed section (updated as tabs are clicked)."""
        return self._selected_tab.get(section)

    def is_group_open(self, name: str) -> bool:
        return bool(self._group_open.get(name, self.default_open))

    def set_group_open(self, name: str, is_open: bool) -> None:
        self._group_open[name] = bool(is_open)
        self._pending_open[name] = bool(is_open)   # force it on the next frame

    def expand_all(self) -> None:
        for g in self._groups:
            self.set_group_open(g.name, True)

    def collapse_all(self) -> None:
        for g in self._groups:
            self.set_group_open(g.name, False)

    def _fire_select(self, name: str) -> None:
        if self.on_select is not None:
            try:
                self.on_select(name)
            except Exception:
                pass
    # endregion

    # ======================================================================
    # region Rendering
    # ======================================================================
    def draw(self) -> bool:
        """Render the whole window (begin + sidebar + content + end). Returns visibility."""
        res = PyImGui.begin(self.title, True, self.window_flags)
        if isinstance(res, tuple):
            visible = bool(res[0])
            still_open = bool(res[1]) if len(res) > 1 else True
        else:
            visible = bool(res)
            still_open = True
        if visible:
            PyImGui.begin_child(f"{self._safe_id}_sidebar", (self.sidebar_width, self.height), True, 0)
            self.draw_sidebar()
            PyImGui.end_child()

            PyImGui.same_line(0, -1)

            PyImGui.begin_child(f"{self._safe_id}_content", (self.content_width, self.height), False, 0)
            self.draw_content()
            PyImGui.end_child()
        PyImGui.end()
        # The title-bar close (X) sets the open flag false; forward it to the caller so external
        # visibility state (e.g. a launchpad toggle) stays in sync. No-op for callers without one.
        if not still_open and self.on_close is not None:
            try:
                self.on_close()
            except Exception:
                pass
        return visible

    def draw_sidebar(self) -> None:
        """Render the collapsible, grouped navigation column (caller owns the region)."""
        query = self._search_text.strip().lower()
        if self.show_search:
            self._search_text = PyImGui.input_text(f"##search_{self._safe_id}", self._search_text)
            PyImGui.spacing()

        for group in self._groups:
            sections = [s for s in group.sections if not query or query in s.name.lower()]
            if query and not sections:
                continue  # hide groups with no matches while searching
            self._draw_group(group, sections, searching=bool(query))

    def _draw_group(self, group: "SidebarWindow.Group", sections: "list[SidebarWindow.Section]",
                    searching: bool) -> None:
        header = self._with_icon(group.icon, group.name)
        if group.collapsible:
            # Source of truth is self._group_open; force it when a programmatic change
            # is pending or while a search is active (so matches are always visible),
            # otherwise let ImGui own the toggle and mirror the result back.
            if searching:
                PyImGui.set_next_item_open(True, _COND_ALWAYS)
            elif group.name in self._pending_open:
                PyImGui.set_next_item_open(self._pending_open.pop(group.name), _COND_ALWAYS)
            else:
                PyImGui.set_next_item_open(self._group_open.get(group.name, group.default_open),
                                           _COND_FIRST_USE_EVER)
            is_open = PyImGui.collapsing_header(f"{header}##g_{self._safe_id}_{group.name}",
                                                PyImGui.TreeNodeFlags.NoFlag)
            if not searching:
                self._group_open[group.name] = is_open
        else:
            PyImGui.text_colored(header, self.MUTED_COLOR)
            PyImGui.separator()
            is_open = True

        if is_open:
            PyImGui.indent(self.indent_width)
            for section in sections:
                self._draw_section_item(group, section)
            PyImGui.unindent(self.indent_width)
        PyImGui.spacing()

    def _draw_section_item(self, group: "SidebarWindow.Group",
                           section: "SidebarWindow.Section") -> None:
        # Namespace the id by group so duplicate section names never collide.
        label = f"{self._with_icon(section.icon, section.name)}##sec_{self._safe_id}_{group.name}_{section.name}"
        if PyImGui.selectable(label, self._selected == section.name,
                              PyImGui.SelectableFlags.NoFlag, (0.0, 0.0)):
            if section.name != self._selected:
                self._selected = section.name
                self._fire_select(section.name)

    def draw_content(self) -> None:
        """Render the currently-selected section (caller owns the region)."""
        section = self._sections_by_name.get(self._selected or "")
        if section is None:
            PyImGui.text_colored(f"Not available: unknown section '{self._selected}'", self.MUTED_COLOR)
            return
        self._draw_help(section, key=section.name)
        if section.tabs:
            self._draw_tabs(section)
        else:
            self._safe_call(section.draw, self._selected or section.name)

    def _draw_tabs(self, section: "SidebarWindow.Section") -> None:
        if PyImGui.begin_tab_bar(f"{self._safe_id}_tabs_{section.name}", PyImGui.TabBarFlags.NoFlag):
            for tab in section.tabs:
                if PyImGui.begin_tab_item(self._with_icon(tab.icon, tab.name), None, 0):
                    # ImGui only runs the selected tab's body — record which one.
                    self._selected_tab[section.name] = tab.name
                    self._draw_help(tab, key=f"{section.name}/{tab.name}")
                    self._safe_call(tab.draw, f"{section.name}/{tab.name}")
                    PyImGui.end_tab_item()
            PyImGui.end_tab_bar()
    # endregion

    # ======================================================================
    # region Help / rich text
    # ======================================================================
    def _draw_help(self, item: "SidebarWindow.Section | SidebarWindow.Tab", key: str) -> None:
        if not self.show_help:
            return
        text = self._help_text(item)
        if not text:
            return
        is_open = self._help_open.get(key, False)
        label = ("Hide Help" if is_open else "Help") + f"##help_{self._safe_id}_{key}"
        if PyImGui.button(label):
            is_open = not is_open
            self._help_open[key] = is_open
        if is_open:
            PyImGui.separator()
            self.render_markdown(text)
            PyImGui.separator()
            PyImGui.spacing()

    def _help_text(self, item: "SidebarWindow.Section | SidebarWindow.Tab") -> str:
        inline = getattr(item, "help", None)
        if inline:
            return str(inline)
        path = getattr(item, "help_file", None)
        if path:
            return self._load_help_file(str(path))
        return ""

    def _load_help_file(self, path: str) -> str:
        full = path
        if self.help_dir and not os.path.isabs(path):
            full = os.path.join(self.help_dir, path)
        if full in self._help_cache:
            return self._help_cache[full]
        try:
            with open(full, "r", encoding="utf-8") as fh:
                text = fh.read()
        except Exception:
            text = f"*Help file not found:* `{full}`"
        self._help_cache[full] = text
        return text

    @staticmethod
    def render_markdown(text: str) -> None:
        """Render markdown as rich text via the native addon; falls back to wrapped text."""
        md = getattr(PyImGui, "markdown", None)
        if md is not None and hasattr(md, "render"):
            try:
                md.render(text)
                return
            except Exception:
                pass
        PyImGui.text_wrapped(text)
    # endregion

    # ======================================================================
    # region Internals
    # ======================================================================
    @staticmethod
    def _with_icon(icon: str, text: str) -> str:
        return f"{icon}  {text}" if icon else text

    def _safe_call(self, fn: Optional[DrawFn], label: str) -> None:
        if fn is None:
            PyImGui.text_colored(f"'{label}' has no content function.", self.MUTED_COLOR)
            return
        try:
            fn()
        except Exception as e:  # keep the window alive if one panel throws
            PyImGui.text_colored(f"Panel error in '{label}':", self.ERR_COLOR)
            PyImGui.text_colored(f"{type(e).__name__}: {e}", self.ERR_COLOR)
    # endregion
