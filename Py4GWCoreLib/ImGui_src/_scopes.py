from typing import TypeAlias
import PyImGui

StyleVarVec2: TypeAlias = tuple[float, float]
StyleVarValue: TypeAlias = float | int | StyleVarVec2 | list[float]


class _ScopeResult:
    def __init__(self, visible: bool):
        self._visible = visible
    def __bool__(self) -> bool: return self._visible
    @property
    def visible(self) -> bool: return self._visible
    @property
    def draw(self): return PyImGui.get_window_draw_list()
    @property
    def pos(self): return PyImGui.get_window_pos()
    @property
    def size(self): return PyImGui.get_window_size()
    @property
    def width(self): return PyImGui.get_window_width()
    @property
    def height(self): return PyImGui.get_window_height()
    @property
    def content_region(self): return PyImGui.get_content_region_avail()
    @property
    def dpi_scale(self): return PyImGui.get_window_dpi_scale()
    @property
    def viewport(self): return PyImGui.get_window_viewport()
    @property
    def is_appearing(self): return PyImGui.is_window_appearing()
    @property
    def is_collapsed(self): return PyImGui.is_window_collapsed()
    @property
    def is_focused(self): return PyImGui.is_window_focused()
    @property
    def is_hovered(self): return PyImGui.is_window_hovered()
    @property
    def cursor(self): return PyImGui.get_cursor_pos()
    @property
    def cursor_x(self): return PyImGui.get_cursor_pos_x()
    @property
    def cursor_y(self): return PyImGui.get_cursor_pos_y()
    @property
    def cursor_screen(self): return PyImGui.get_cursor_screen_pos()
    @property
    def cursor_start(self): return PyImGui.get_cursor_start_pos()
    @property
    def scroll_x(self): return PyImGui.get_scroll_x()
    @property
    def scroll_y(self): return PyImGui.get_scroll_y()
    @property
    def scroll_max_x(self): return PyImGui.get_scroll_max_x()
    @property
    def scroll_max_y(self): return PyImGui.get_scroll_max_y()


class _CloseableResult(_ScopeResult):
    def __init__(self, visible: bool, still_open: bool):
        super().__init__(visible)
        self._still_open = still_open
    @property
    def still_open(self) -> bool: return self._still_open


class _WindowScope:
    def __init__(self, name, p_open, flags):
        self._name = name; self._p_open = p_open; self._flags = flags
    def __enter__(self):
        v, s = PyImGui.begin(self._name, self._p_open, self._flags)
        return _CloseableResult(v, s)
    def __exit__(self, *_): PyImGui.end()

class _ChildScope:
    def __init__(self, id, size, child_flags, window_flags):
        self._id = id; self._size = size; self._child_flags = child_flags; self._window_flags = window_flags
    def __enter__(self):
        return _ScopeResult(PyImGui.begin_child(self._id, self._size, self._child_flags, self._window_flags))
    def __exit__(self, *_): PyImGui.end_child()

class _GroupScope:
    def __enter__(self): PyImGui.begin_group()
    def __exit__(self, *_): PyImGui.end_group()

class _DisabledScope:
    def __init__(self, state): self._state = state
    def __enter__(self): PyImGui.begin_disabled(self._state)
    def __exit__(self, *_): PyImGui.end_disabled()

class _MenuBarScope:
    def __enter__(self): return _ScopeResult(PyImGui.begin_menu_bar())
    def __exit__(self, *_): PyImGui.end_menu_bar()

class _MainMenuBarScope:
    def __enter__(self): return _ScopeResult(PyImGui.begin_main_menu_bar())
    def __exit__(self, *_): PyImGui.end_main_menu_bar()

class _MenuScope:
    def __init__(self, label, enabled): self._label = label; self._enabled = enabled
    def __enter__(self): return _ScopeResult(PyImGui.begin_menu(self._label, self._enabled))
    def __exit__(self, *_): PyImGui.end_menu()

class _PopupScope:
    def __init__(self, str_id, flags): self._str_id = str_id; self._flags = flags
    def __enter__(self): return _ScopeResult(PyImGui.begin_popup(self._str_id, self._flags))
    def __exit__(self, *_): PyImGui.end_popup()

class _PopupModalScope:
    def __init__(self, name, open, flags): self._name = name; self._open = open; self._flags = flags
    def __enter__(self): return _ScopeResult(PyImGui.begin_popup_modal(self._name, self._open, self._flags))
    def __exit__(self, *_): PyImGui.end_popup()

class _PopupContextItemScope:
    def __init__(self, str_id, flags): self._str_id = str_id; self._flags = flags
    def __enter__(self): return _ScopeResult(PyImGui.begin_popup_context_item(self._str_id, self._flags))
    def __exit__(self, *_): PyImGui.end_popup()

class _PopupContextWindowScope:
    def __init__(self, str_id, flags): self._str_id = str_id; self._flags = flags
    def __enter__(self): return _ScopeResult(PyImGui.begin_popup_context_window(self._str_id, self._flags))
    def __exit__(self, *_): PyImGui.end_popup()

class _PopupContextVoidScope:
    def __init__(self, str_id, flags): self._str_id = str_id; self._flags = flags
    def __enter__(self): return _ScopeResult(PyImGui.begin_popup_context_void(self._str_id, self._flags))
    def __exit__(self, *_): PyImGui.end_popup()

class _TooltipScope:
    def __enter__(self): PyImGui.begin_tooltip()
    def __exit__(self, *_): PyImGui.end_tooltip()

class _TableScope:
    def __init__(self, str_id, columns, flags, outer_size, inner_width):
        self._str_id = str_id; self._columns = columns; self._flags = flags
        self._outer_size = outer_size; self._inner_width = inner_width
    def __enter__(self):
        return _ScopeResult(PyImGui.begin_table(self._str_id, self._columns, self._flags, self._outer_size, self._inner_width))
    def __exit__(self, *_): PyImGui.end_table()

class _TabBarScope:
    def __init__(self, str_id, flags): self._str_id = str_id; self._flags = flags
    def __enter__(self): return _ScopeResult(PyImGui.begin_tab_bar(self._str_id, self._flags))
    def __exit__(self, *_): PyImGui.end_tab_bar()

class _TabItemScope:
    def __init__(self, label, flags, closable): self._label = label; self._flags = flags; self._closable = closable
    def __enter__(self):
        if self._closable:
            v, s = PyImGui.begin_tab_item_closable(self._label, True, self._flags)
            return _CloseableResult(v, s)
        return _ScopeResult(PyImGui.begin_tab_item(self._label, None, self._flags))
    def __exit__(self, *_): PyImGui.end_tab_item()

class _ComboScope:
    def __init__(self, label, preview, flags): self._label = label; self._preview = preview; self._flags = flags
    def __enter__(self): return _ScopeResult(PyImGui.begin_combo(self._label, self._preview, self._flags))
    def __exit__(self, *_): PyImGui.end_combo()

class _ListBoxScope:
    def __init__(self, label, size): self._label = label; self._size = size
    def __enter__(self): return _ScopeResult(PyImGui.begin_list_box(self._label, self._size))
    def __exit__(self, *_): PyImGui.end_list_box()

class _DragDropSourceScope:
    def __init__(self, flags): self._flags = flags
    def __enter__(self): return _ScopeResult(PyImGui.begin_drag_drop_source(self._flags))
    def __exit__(self, *_): PyImGui.end_drag_drop_source()

class _DragDropTargetScope:
    def __enter__(self): return _ScopeResult(PyImGui.begin_drag_drop_target())
    def __exit__(self, *_): PyImGui.end_drag_drop_target()

class _TreeNodeScope:
    def __init__(self, label, flags): self._label = label; self._flags = flags
    def __enter__(self):
        self._open = PyImGui.tree_node_ex(self._label, self._flags)
        return _ScopeResult(self._open)
    def __exit__(self, *_):
        if self._open: PyImGui.tree_pop()

class _MultiSelectScope:
    def __init__(self, flags, selection_size, items_count):
        self._flags = flags; self._selection_size = selection_size; self._items_count = items_count
    def __enter__(self):
        return _ScopeResult(PyImGui.begin_multi_select(self._flags, self._selection_size, self._items_count))
    def __exit__(self, *_): PyImGui.end_multi_select()

class _StyleColorScope:
    def __init__(self, idx, color): self._idx = idx; self._color = color
    def __enter__(self): PyImGui.push_style_color(self._idx, self._color)
    def __exit__(self, *_): PyImGui.pop_style_color()

class _StyleVarScope:
    def __init__(self, idx: int, value: StyleVarValue):
        self._idx = idx; self._value = value
    def __enter__(self):
        if isinstance(self._value, (tuple, list)):
            if len(self._value) != 2:
                raise ValueError('style_var vec2 values must contain exactly 2 elements')
            PyImGui.push_style_var_vec2(self._idx, (float(self._value[0]), float(self._value[1])))
        else:
            PyImGui.push_style_var(self._idx, float(self._value))
    def __exit__(self, *_): PyImGui.pop_style_var()

class _FontScope:
    def __init__(self, idx): self._idx = idx
    def __enter__(self): PyImGui.push_font(self._idx)
    def __exit__(self, *_): PyImGui.pop_font()

class _ItemWidthScope:
    def __init__(self, width): self._width = width
    def __enter__(self): PyImGui.push_item_width(self._width)
    def __exit__(self, *_): PyImGui.pop_item_width()

class _TextWrapScope:
    def __init__(self, pos): self._pos = pos
    def __enter__(self): PyImGui.push_text_wrap_pos(self._pos)
    def __exit__(self, *_): PyImGui.pop_text_wrap_pos()

class _ItemFlagScope:
    def __init__(self, option, enabled): self._option = option; self._enabled = enabled
    def __enter__(self): PyImGui.push_item_flag(self._option, self._enabled)
    def __exit__(self, *_): PyImGui.pop_item_flag()

class _ButtonRepeatScope:
    def __init__(self, repeat): self._repeat = repeat
    def __enter__(self): PyImGui.push_button_repeat(self._repeat)
    def __exit__(self, *_): PyImGui.pop_button_repeat()

class _IDScope:
    def __init__(self, value): self._value = value
    def __enter__(self):
        if isinstance(self._value, int): PyImGui.push_id_int(self._value)
        else: PyImGui.push_id(str(self._value))
    def __exit__(self, *_): PyImGui.pop_id()

class _ClipRectScope:
    def __init__(self, x, y, w, h, intersect):
        self._x = x; self._y = y; self._w = w; self._h = h; self._intersect = intersect
    def __enter__(self):
        PyImGui.push_clip_rect(self._x, self._y, self._w, self._h, self._intersect)
    def __exit__(self, *_): PyImGui.pop_clip_rect()
