"""Scope classes for the Reforged ImGui facade.

All scope classes follow the same public contract:
- Every ``__enter__`` returns a result with ``.entered: bool``.
- Closeable scopes additionally expose ``.open: bool``.
- ``__bool__`` is temporary compatibility only.

Scope base hierarchy:
- ``_BaseScope``        — stores runtime reference
- ``_AlwaysEndScope``   — always calls ``_end()`` if entered (window, child, push/pop scopes)
- ``_ConditionalEndScope`` — calls ``_end()`` only if begin returned truthy (menus, popups, tables)
"""

from contextlib import ExitStack
from typing import TypeAlias

import PyImGui

StyleVarVec2: TypeAlias = tuple[float, float]
StyleVarValue: TypeAlias = float | int | StyleVarVec2 | list[float]


# ═══════════════════════════════════════════════════════════════════════
#  Result types
# ═══════════════════════════════════════════════════════════════════════

class ScopeResult:
    """Result from a non-closeable scope context manager.

    Primary API:
        ``scope.entered`` — ``True`` if the scope's begin succeeded.
        ``__bool__`` — compatibility alias for ``.entered``.

    Window-scoped properties are available only while the scope is active.
    """

    def __init__(self, runtime: 'ImGuiRuntime', entered: bool):
        self._runtime = runtime
        self.entered = entered

    def __bool__(self) -> bool:
        """Compatibility alias for ``.entered``."""
        return self.entered

    # ── Window-scoped properties ──

    @property
    def draw(self):
        return PyImGui.get_window_draw_list()

    @property
    def pos(self):
        return PyImGui.get_window_pos()

    @property
    def size(self):
        return PyImGui.get_window_size()

    @property
    def width(self):
        return PyImGui.get_window_width()

    @property
    def height(self):
        return PyImGui.get_window_height()

    @property
    def content_region(self):
        return PyImGui.get_content_region_avail()

    @property
    def dpi_scale(self):
        return PyImGui.get_window_dpi_scale()

    @property
    def viewport(self):
        return PyImGui.get_window_viewport()

    @property
    def is_appearing(self):
        return PyImGui.is_window_appearing()

    @property
    def is_collapsed(self):
        return PyImGui.is_window_collapsed()

    @property
    def is_focused(self):
        return PyImGui.is_window_focused()

    @property
    def is_hovered(self):
        return PyImGui.is_window_hovered()

    @property
    def cursor(self):
        return PyImGui.get_cursor_pos()

    @property
    def cursor_x(self):
        return PyImGui.get_cursor_pos_x()

    @property
    def cursor_y(self):
        return PyImGui.get_cursor_pos_y()

    @property
    def cursor_screen(self):
        return PyImGui.get_cursor_screen_pos()

    @property
    def cursor_start(self):
        return PyImGui.get_cursor_start_pos()

    @property
    def scroll_x(self):
        return PyImGui.get_scroll_x()

    @property
    def scroll_y(self):
        return PyImGui.get_scroll_y()

    @property
    def scroll_max_x(self):
        return PyImGui.get_scroll_max_x()

    @property
    def scroll_max_y(self):
        return PyImGui.get_scroll_max_y()


class CloseableScopeResult(ScopeResult):
    """Result from a closeable scope (window, popup_modal, tab_item closable).

    Adds ``.open`` — the post-frame open/close state.
    """

    def __init__(self, runtime: 'ImGuiRuntime', entered: bool, open: bool):
        super().__init__(runtime, entered)
        self.open = open


# ═══════════════════════════════════════════════════════════════════════
#  Base classes
# ═══════════════════════════════════════════════════════════════════════

class _BaseScope:
    """Base for all scopes. Stores the runtime reference."""

    def __init__(self, runtime: 'ImGuiRuntime'):
        self._runtime = runtime


class _AlwaysEndScope(_BaseScope):
    """Scope that always calls ``_end()`` after a successful ``_begin()``.

    Used for: window, child, group, disabled, tooltip, style color/var,
    font, item_width, text_wrap, item_flag, button_repeat, id, clip_rect.
    """

    def __init__(self, runtime: 'ImGuiRuntime'):
        super().__init__(runtime)
        self._entered = False

    def _begin(self):
        """Override: perform ImGui begin/push and return a result object."""
        raise NotImplementedError

    def _end(self):
        """Override: perform ImGui end/pop."""
        raise NotImplementedError

    def __enter__(self):
        result = self._begin()
        self._entered = True
        return result

    def __exit__(self, exc_type, exc, tb):
        if self._entered:
            self._end()


class _ConditionalEndScope(_BaseScope):
    """Scope that calls ``_end()`` only if ``_begin()`` returned truthy.

    Used for: menus, popups, tables, tab bars, combos, list boxes,
    drag-drop sources/targets, tree nodes, multi-select.
    """

    def __init__(self, runtime: 'ImGuiRuntime'):
        super().__init__(runtime)
        self._entered = False

    def _begin(self):
        """Override: perform ImGui begin and return a result object."""
        raise NotImplementedError

    def _end(self):
        """Override: perform ImGui end."""
        raise NotImplementedError

    def __enter__(self):
        result = self._begin()
        entered = result.entered if hasattr(result, 'entered') else bool(result)
        self._entered = bool(entered)
        return result

    def __exit__(self, exc_type, exc, tb):
        if self._entered:
            self._end()


# ═══════════════════════════════════════════════════════════════════════
#  Always-end scopes
# ═══════════════════════════════════════════════════════════════════════

class _WindowScope(_AlwaysEndScope):
    """``with ImGui.window(...) as win:`` — closeable structural scope."""

    def __init__(self, runtime: 'ImGuiRuntime', name: str, p_open, flags: int):
        super().__init__(runtime)
        self._name = name
        self._p_open = p_open
        self._flags = flags

    def _begin(self):
        entered, still_open = PyImGui.begin(self._name, self._p_open, self._flags)
        return CloseableScopeResult(self._runtime, entered=entered, open=still_open)

    def _end(self):
        PyImGui.end()


class _ChildScope(_AlwaysEndScope):
    """``with ImGui.child(...) as child:`` — child window scope."""

    def __init__(self, runtime: 'ImGuiRuntime', id: str, size, child_flags: int, window_flags: int):
        super().__init__(runtime)
        self._id = id
        self._size = size
        self._child_flags = child_flags
        self._window_flags = window_flags

    def _begin(self):
        entered = PyImGui.begin_child(self._id, self._size, self._child_flags, self._window_flags)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_child()


class _GroupScope(_AlwaysEndScope):
    """``with ImGui.group():`` — always-entered scope."""

    def _begin(self):
        PyImGui.begin_group()
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.end_group()


class _DisabledScope(_AlwaysEndScope):
    """``with ImGui.disabled(state=True):`` — always-entered scope."""

    def __init__(self, runtime: 'ImGuiRuntime', state: bool = True):
        super().__init__(runtime)
        self._state = state

    def _begin(self):
        PyImGui.begin_disabled(self._state)
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.end_disabled()


class _TooltipScope(_AlwaysEndScope):
    """``with ImGui.tooltip():`` — always-entered scope."""

    def _begin(self):
        PyImGui.begin_tooltip()
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.end_tooltip()


class _StyleColorScope(_AlwaysEndScope):
    """``with ImGui.style.color(idx, color):`` — push/pop style color with tracker."""

    def __init__(self, runtime: 'ImGuiRuntime', idx: int, color):
        super().__init__(runtime)
        self._idx = idx
        self._color = color

    def _begin(self):
        PyImGui.push_style_color(self._idx, self._color)
        self._runtime._stack_tracker.push('style_color')
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.pop_style_color()
        self._runtime._stack_tracker.pop('style_color')


class _StyleVarScope(_AlwaysEndScope):
    """``with ImGui.style.var(idx, value):`` — push/pop style var with tracker.

    Automatically dispatches to ``push_style_var`` or ``push_style_var_vec2``
    based on whether ``value`` is a float/int or a tuple/list.
    """

    def __init__(self, runtime: 'ImGuiRuntime', idx: int, value: StyleVarValue):
        super().__init__(runtime)
        self._idx = idx
        self._value = value

    def _begin(self):
        if isinstance(self._value, (tuple, list)):
            if len(self._value) != 2:
                raise ValueError('style_var vec2 values must contain exactly 2 elements')
            PyImGui.push_style_var_vec2(self._idx, (float(self._value[0]), float(self._value[1])))
        else:
            PyImGui.push_style_var(self._idx, float(self._value))
        self._runtime._stack_tracker.push('style_var')
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.pop_style_var()
        self._runtime._stack_tracker.pop('style_var')


class _FontScope(_AlwaysEndScope):
    """``with ImGui.font(idx):`` — push/pop font with tracker."""

    def __init__(self, runtime: 'ImGuiRuntime', idx: int = 0):
        super().__init__(runtime)
        self._idx = idx

    def _begin(self):
        PyImGui.push_font(self._idx)
        self._runtime._stack_tracker.push('font')
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.pop_font()
        self._runtime._stack_tracker.pop('font')


class _ItemWidthScope(_AlwaysEndScope):
    """``with ImGui.item_width(width):`` — push/pop item width with tracker."""

    def __init__(self, runtime: 'ImGuiRuntime', width: float):
        super().__init__(runtime)
        self._width = width

    def _begin(self):
        PyImGui.push_item_width(self._width)
        self._runtime._stack_tracker.push('item_width')
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.pop_item_width()
        self._runtime._stack_tracker.pop('item_width')


class _TextWrapScope(_AlwaysEndScope):
    """``with ImGui.text_wrap(pos):`` — push/pop text wrap with tracker."""

    def __init__(self, runtime: 'ImGuiRuntime', pos: float = 0.0):
        super().__init__(runtime)
        self._pos = pos

    def _begin(self):
        PyImGui.push_text_wrap_pos(self._pos)
        self._runtime._stack_tracker.push('text_wrap')
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.pop_text_wrap_pos()
        self._runtime._stack_tracker.pop('text_wrap')


class _ItemFlagScope(_AlwaysEndScope):
    """``with ImGui.item_flag(option, enabled):`` — push/pop item flag with tracker."""

    def __init__(self, runtime: 'ImGuiRuntime', option: int, enabled: bool):
        super().__init__(runtime)
        self._option = option
        self._enabled = enabled

    def _begin(self):
        PyImGui.push_item_flag(self._option, self._enabled)
        self._runtime._stack_tracker.push('item_flag')
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.pop_item_flag()
        self._runtime._stack_tracker.pop('item_flag')


class _ButtonRepeatScope(_AlwaysEndScope):
    """``with ImGui.button_repeat(repeat):`` — push/pop button repeat with tracker."""

    def __init__(self, runtime: 'ImGuiRuntime', repeat: bool):
        super().__init__(runtime)
        self._repeat = repeat

    def _begin(self):
        PyImGui.push_button_repeat(self._repeat)
        self._runtime._stack_tracker.push('button_repeat')
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.pop_button_repeat()
        self._runtime._stack_tracker.pop('button_repeat')


class _IDScope(_AlwaysEndScope):
    """``with ImGui.id(value):`` — push/pop ID with tracker.

    Dispatches to ``push_id_int`` or ``push_id(str)`` based on type.
    """

    def __init__(self, runtime: 'ImGuiRuntime', value):
        super().__init__(runtime)
        self._value = value

    def _begin(self):
        if isinstance(self._value, int):
            PyImGui.push_id_int(self._value)
        else:
            PyImGui.push_id(str(self._value))
        self._runtime._stack_tracker.push('id')
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.pop_id()
        self._runtime._stack_tracker.pop('id')


class _ClipRectScope(_AlwaysEndScope):
    """``with ImGui.clip_rect(x, y, w, h):`` — push/pop clip rect with tracker."""

    def __init__(self, runtime: 'ImGuiRuntime', x: float, y: float, w: float, h: float, *, intersect: bool = True):
        super().__init__(runtime)
        self._x = x
        self._y = y
        self._w = w
        self._h = h
        self._intersect = intersect

    def _begin(self):
        PyImGui.push_clip_rect(self._x, self._y, self._w, self._h, self._intersect)
        self._runtime._stack_tracker.push('clip_rect')
        return ScopeResult(self._runtime, entered=True)

    def _end(self):
        PyImGui.pop_clip_rect()
        self._runtime._stack_tracker.pop('clip_rect')


# ═══════════════════════════════════════════════════════════════════════
#  Conditional-end scopes
# ═══════════════════════════════════════════════════════════════════════

class _MenuBarScope(_ConditionalEndScope):
    """``with ImGui.menu_bar() as mb:`` — conditional-end (only if begin succeeded)."""

    def _begin(self):
        entered = PyImGui.begin_menu_bar()
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_menu_bar()


class _MainMenuBarScope(_ConditionalEndScope):
    """``with ImGui.main_menu_bar() as mmb:`` — conditional-end."""

    def _begin(self):
        entered = PyImGui.begin_main_menu_bar()
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_main_menu_bar()


class _MenuScope(_ConditionalEndScope):
    """``with ImGui.menu(label) as m:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', label: str, enabled: bool = True):
        super().__init__(runtime)
        self._label = label
        self._enabled = enabled

    def _begin(self):
        entered = PyImGui.begin_menu(self._label, self._enabled)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_menu()


class _PopupScope(_ConditionalEndScope):
    """``with ImGui.popup(str_id) as pp:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', str_id: str, flags: int = 0):
        super().__init__(runtime)
        self._str_id = str_id
        self._flags = flags

    def _begin(self):
        entered = PyImGui.begin_popup(self._str_id, self._flags)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_popup()


class _PopupModalScope(_ConditionalEndScope):
    """``with ImGui.popup_modal(name) as pm:`` — closeable conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', name: str, open, flags: int = 0):
        super().__init__(runtime)
        self._name = name
        self._open = open
        self._flags = flags

    def _begin(self):
        entered, still_open = PyImGui.begin_popup_modal(self._name, self._open, self._flags)
        return CloseableScopeResult(self._runtime, entered=entered, open=still_open)

    def _end(self):
        PyImGui.end_popup()


class _PopupContextItemScope(_ConditionalEndScope):
    """``with ImGui.popup_context_item(...) as pci:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', str_id: str | None = None, popup_flags: int = 0):
        super().__init__(runtime)
        self._str_id = str_id
        self._popup_flags = popup_flags

    def _begin(self):
        entered = PyImGui.begin_popup_context_item(self._str_id, self._popup_flags)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_popup()


class _PopupContextWindowScope(_ConditionalEndScope):
    """``with ImGui.popup_context_window(...) as pcw:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', str_id: str | None = None, popup_flags: int = 0):
        super().__init__(runtime)
        self._str_id = str_id
        self._popup_flags = popup_flags

    def _begin(self):
        entered = PyImGui.begin_popup_context_window(self._str_id, self._popup_flags)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_popup()


class _PopupContextVoidScope(_ConditionalEndScope):
    """``with ImGui.popup_context_void(...) as pcv:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', str_id: str | None = None, popup_flags: int = 0):
        super().__init__(runtime)
        self._str_id = str_id
        self._popup_flags = popup_flags

    def _begin(self):
        entered = PyImGui.begin_popup_context_void(self._str_id, self._popup_flags)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_popup()


class _TableScope(_ConditionalEndScope):
    """``with ImGui.table(id, columns) as t:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', str_id: str, columns: int, flags: int = 0,
                 outer_size=(0, 0), inner_width: float = 0.0):
        super().__init__(runtime)
        self._str_id = str_id
        self._columns = columns
        self._flags = flags
        self._outer_size = outer_size
        self._inner_width = inner_width

    def _begin(self):
        entered = PyImGui.begin_table(self._str_id, self._columns, self._flags,
                                       self._outer_size, self._inner_width)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_table()


class _TabBarScope(_ConditionalEndScope):
    """``with ImGui.tab_bar(str_id) as tb:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', str_id: str, flags: int = 0):
        super().__init__(runtime)
        self._str_id = str_id
        self._flags = flags

    def _begin(self):
        entered = PyImGui.begin_tab_bar(self._str_id, self._flags)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_tab_bar()


class _TabItemScope(_ConditionalEndScope):
    """``with ImGui.tab_item(label, closable=...) as ti:`` — conditional-end.

    Returns ``CloseableScopeResult`` when closable, ``ScopeResult`` otherwise.
    """

    def __init__(self, runtime: 'ImGuiRuntime', label: str, flags: int = 0, closable: bool = False):
        super().__init__(runtime)
        self._label = label
        self._flags = flags
        self._closable = closable

    def _begin(self):
        if self._closable:
            entered, still_open = PyImGui.begin_tab_item_closable(self._label, True, self._flags)
            return CloseableScopeResult(self._runtime, entered=entered, open=still_open)
        entered = PyImGui.begin_tab_item(self._label, None, self._flags)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_tab_item()


class _ComboScope(_ConditionalEndScope):
    """``with ImGui.combo(label, preview) as c:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', label: str, preview: str, flags: int = 0):
        super().__init__(runtime)
        self._label = label
        self._preview = preview
        self._flags = flags

    def _begin(self):
        entered = PyImGui.begin_combo(self._label, self._preview, self._flags)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_combo()


class _ListBoxScope(_ConditionalEndScope):
    """``with ImGui.list_box(label) as lb:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', label: str, size=(0, 0)):
        super().__init__(runtime)
        self._label = label
        self._size = size

    def _begin(self):
        entered = PyImGui.begin_list_box(self._label, self._size)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_list_box()


class _DragDropSourceScope(_ConditionalEndScope):
    """``with ImGui.drag_drop_source(flags) as dds:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', flags: int = 0):
        super().__init__(runtime)
        self._flags = flags

    def _begin(self):
        entered = PyImGui.begin_drag_drop_source(self._flags)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_drag_drop_source()


class _DragDropTargetScope(_ConditionalEndScope):
    """``with ImGui.drag_drop_target() as ddt:`` — conditional-end."""

    def _begin(self):
        entered = PyImGui.begin_drag_drop_target()
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_drag_drop_target()


class _TreeNodeScope(_ConditionalEndScope):
    """``with ImGui.tree_node(label) as tn:`` — conditional-end (calls tree_pop)."""

    def __init__(self, runtime: 'ImGuiRuntime', label: str, flags: int = 0):
        super().__init__(runtime)
        self._label = label
        self._flags = flags

    def _begin(self):
        entered = PyImGui.tree_node_ex(self._label, self._flags)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.tree_pop()


class _MultiSelectScope(_ConditionalEndScope):
    """``with ImGui.multi_select(...) as ms:`` — conditional-end."""

    def __init__(self, runtime: 'ImGuiRuntime', flags: int = 0, selection_size: int = -1, items_count: int = -1):
        super().__init__(runtime)
        self._flags = flags
        self._selection_size = selection_size
        self._items_count = items_count

    def _begin(self):
        entered = PyImGui.begin_multi_select(self._flags, self._selection_size, self._items_count)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_multi_select()


# ═══════════════════════════════════════════════════════════════════════
#  Composition helpers
# ═══════════════════════════════════════════════════════════════════════

class _CompositeScope:
    """``with ImGui.scoped(...) as cs:`` — compose multiple scopes into one.

    ``.entered`` is ``all(...)`` across child scopes.
    Uses ``ExitStack`` to guarantee correct unwinding on partial failures.
    """

    def __init__(self, *scopes):
        self._scopes = scopes
        self._stack = ExitStack()
        self.entered = True

    def __enter__(self):
        for scope in self._scopes:
            result = self._stack.enter_context(scope)
            child_entered = getattr(result, 'entered', bool(result))
            self.entered = self.entered and bool(child_entered)
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._stack.__exit__(exc_type, exc, tb)


class _FrameScope:
    """``with ImGui.frame():`` — diagnostics wrapper for a single render frame.

    Snapshots the stack tracker at entry and logs any imbalance at exit.
    Nested frames raise ``RuntimeError`` — one frame per render call.

    Severity: imbalance logged by default (non-fatal).
    """

    _frame_depth = 0

    def __init__(self, runtime: 'ImGuiRuntime'):
        self._runtime = runtime
        self._snapshot = None

    def __enter__(self):
        if _FrameScope._frame_depth > 0:
            raise RuntimeError('Nested ImGui.frame() is not supported')
        _FrameScope._frame_depth += 1
        self._snapshot = self._runtime._stack_tracker.snapshot()
        return ScopeResult(self._runtime, entered=True)

    def __exit__(self, exc_type, exc, tb):
        _FrameScope._frame_depth -= 1
        diff = self._runtime._stack_tracker.diff(self._snapshot)
        if diff:
            import logging
            logging.warning(f'ImGui stack imbalance detected at frame exit: {diff}')
