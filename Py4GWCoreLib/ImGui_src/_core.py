import PyImGui

from ._layout import _LayoutMethods
from ._text import _TextMethods
from ._widgets import _WidgetMethods
from ._color_image import _ColorImageMethods
from ._tree_tables import _TreeTableMethods
from ._popups import _PopupMenuMethods
from ._input import _InputStateMethods
from ._items import _ItemMethods
from ._window import _WindowMethods
from ._docking import _DockingMethods
from ._system import _SystemMethods
from ._scopes import (
    _ScopeResult, _CloseableResult,
    _WindowScope, _ChildScope, _GroupScope, _DisabledScope,
    _MenuBarScope, _MainMenuBarScope, _MenuScope,
    _PopupScope, _PopupModalScope, _PopupContextItemScope,
    _PopupContextWindowScope, _PopupContextVoidScope, _TooltipScope,
    _TableScope, _TabBarScope, _TabItemScope,
    _ComboScope, _ListBoxScope,
    _DragDropSourceScope, _DragDropTargetScope,
    _TreeNodeScope, _MultiSelectScope,
    _StyleColorScope, _StyleVarScope, _FontScope,
    _ItemWidthScope, _TextWrapScope, _ItemFlagScope,
    _ButtonRepeatScope, _IDScope, _ClipRectScope,
)


class ImGui(
    _LayoutMethods,
    _TextMethods,
    _WidgetMethods,
    _ColorImageMethods,
    _TreeTableMethods,
    _PopupMenuMethods,
    _InputStateMethods,
    _ItemMethods,
    _WindowMethods,
    _DockingMethods,
    _SystemMethods,
):
    def __init__(self):
        self._io = None
        self._style = None
        self._viewport = None
        self._font = None

    @property
    def io(self):
        if self._io is None: self._io = PyImGui.get_io()
        return self._io

    @property
    def style(self):
        if self._style is None: self._style = PyImGui.get_style()
        return self._style

    @property
    def viewport(self):
        if self._viewport is None: self._viewport = PyImGui.get_main_viewport()
        return self._viewport

    @property
    def font(self):
        if self._font is None: self._font = PyImGui.get_font()
        return self._font

    @property
    def fg_draw(self):
        return PyImGui.get_foreground_draw_list()

    @property
    def bg_draw(self):
        return PyImGui.get_background_draw_list()

    def window(self, name: str, p_open=None, *, open=None, flags: int = 0):
        resolved_open = p_open if p_open is not None else open
        return _WindowScope(name, resolved_open, flags)

    def child(self, id: str, *, size=(0, 0), child_flags: int = 0, window_flags: int = 0):
        return _ChildScope(id, size, child_flags, window_flags)

    def group(self):
        return _GroupScope()

    def disabled(self, state: bool = True):
        return _DisabledScope(state)

    def menu_bar(self):
        return _MenuBarScope()

    def main_menu_bar(self):
        return _MainMenuBarScope()

    def menu(self, label: str, *, enabled: bool = True):
        return _MenuScope(label, enabled)

    def popup(self, str_id: str, *, flags: int = 0):
        return _PopupScope(str_id, flags)

    def popup_modal(self, name: str, *, open=None, flags: int = 0):
        return _PopupModalScope(name, open, flags)

    def popup_context_item(self, str_id: str | None = None, *, popup_flags: int = 0):
        return _PopupContextItemScope(str_id, popup_flags)

    def popup_context_window(self, str_id: str | None = None, *, popup_flags: int = 0):
        return _PopupContextWindowScope(str_id, popup_flags)

    def popup_context_void(self, str_id: str | None = None, *, popup_flags: int = 0):
        return _PopupContextVoidScope(str_id, popup_flags)

    def tooltip(self):
        return _TooltipScope()

    def table(self, str_id: str, columns: int, *, flags: int = 0,
              outer_size=(0, 0), inner_width: float = 0.0):
        return _TableScope(str_id, columns, flags, outer_size, inner_width)

    def tab_bar(self, str_id: str, *, flags: int = 0):
        return _TabBarScope(str_id, flags)

    def tab_item(self, label: str, *, flags: int = 0, closable: bool = False):
        return _TabItemScope(label, flags, closable)

    def combo_scope(self, label: str, preview: str, *, flags: int = 0):
        return _ComboScope(label, preview, flags)

    def list_box_scope(self, label: str, *, size=(0, 0)):
        return _ListBoxScope(label, size)

    def drag_drop_source(self, *, flags: int = 0):
        return _DragDropSourceScope(flags)

    def drag_drop_target(self):
        return _DragDropTargetScope()

    def tree_node(self, label: str, *, flags: int = 0):
        return _TreeNodeScope(label, flags)

    def multi_select(self, *, flags: int = 0, selection_size: int = -1, items_count: int = -1):
        return _MultiSelectScope(flags, selection_size, items_count)

    def style_color(self, idx: int, color):
        return _StyleColorScope(idx, color)

    def style_var(self, idx: int, value):
        return _StyleVarScope(idx, value)

    def push_font(self, idx: int = 0):
        return _FontScope(idx)

    def item_width(self, width: float):
        return _ItemWidthScope(width)

    def text_wrap(self, pos: float = 0.0):
        return _TextWrapScope(pos)

    def item_flag(self, option: int, enabled: bool):
        return _ItemFlagScope(option, enabled)

    def button_repeat(self, repeat: bool):
        return _ButtonRepeatScope(repeat)

    def id_scope(self, value):
        return _IDScope(value)

    def clip_rect(self, x: float, y: float, w: float, h: float, *, intersect: bool = True):
        return _ClipRectScope(x, y, w, h, intersect)
