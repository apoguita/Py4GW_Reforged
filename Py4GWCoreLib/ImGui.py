"""Facade for the standalone Reforged ImGui API.

This module is intentionally isolated from ``ImGui_Legacy``.
Legacy callers must import ``ImGui_Legacy`` explicitly.
"""

from .ImGui_src import ui as _ui
from .ImGui_src._color_image import _ColorImageMethods
from .ImGui_src._core import ImGui as _ImGuiRuntime
from .ImGui_src._docking import _DockingMethods
from .ImGui_src._input import _InputStateMethods
from .ImGui_src._items import _ItemMethods
from .ImGui_src._layout import _LayoutMethods
from .ImGui_src._popups import _PopupMenuMethods
from .ImGui_src._scopes import _ChildScope
from .ImGui_src._scopes import _ButtonRepeatScope
from .ImGui_src._scopes import _ClipRectScope
from .ImGui_src._scopes import _CloseableResult
from .ImGui_src._scopes import _ComboScope
from .ImGui_src._scopes import _DisabledScope
from .ImGui_src._scopes import _DragDropSourceScope
from .ImGui_src._scopes import _DragDropTargetScope
from .ImGui_src._scopes import _FontScope
from .ImGui_src._scopes import _GroupScope
from .ImGui_src._scopes import _IDScope
from .ImGui_src._scopes import _ItemFlagScope
from .ImGui_src._scopes import _ItemWidthScope
from .ImGui_src._scopes import _ListBoxScope
from .ImGui_src._scopes import _MainMenuBarScope
from .ImGui_src._scopes import _MenuBarScope
from .ImGui_src._scopes import _MenuScope
from .ImGui_src._scopes import _MultiSelectScope
from .ImGui_src._scopes import _PopupContextItemScope
from .ImGui_src._scopes import _PopupContextVoidScope
from .ImGui_src._scopes import _PopupContextWindowScope
from .ImGui_src._scopes import _PopupModalScope
from .ImGui_src._scopes import _PopupScope
from .ImGui_src._scopes import _ScopeResult
from .ImGui_src._scopes import _StyleColorScope
from .ImGui_src._scopes import _StyleVarScope
from .ImGui_src._scopes import _TabBarScope
from .ImGui_src._scopes import _TabItemScope
from .ImGui_src._scopes import _TableScope
from .ImGui_src._scopes import _TextWrapScope
from .ImGui_src._scopes import _TooltipScope
from .ImGui_src._scopes import _TreeNodeScope
from .ImGui_src._scopes import _WindowScope
from .ImGui_src._system import _SystemMethods
from .ImGui_src._text import _TextMethods
from .ImGui_src._tree_tables import _TreeTableMethods
from .ImGui_src._widgets import _WidgetMethods
from .ImGui_src._window import _WindowMethods


class _MethodGroups:
    Layout = _LayoutMethods
    Text = _TextMethods
    Widgets = _WidgetMethods
    ColorImage = _ColorImageMethods
    TreeTables = _TreeTableMethods
    Popups = _PopupMenuMethods
    Input = _InputStateMethods
    Items = _ItemMethods
    Window = _WindowMethods
    Docking = _DockingMethods
    System = _SystemMethods


class _Scopes:
    Result = _ScopeResult
    CloseableResult = _CloseableResult
    Window = _WindowScope
    Child = _ChildScope
    Group = _GroupScope
    Disabled = _DisabledScope
    MenuBar = _MenuBarScope
    MainMenuBar = _MainMenuBarScope
    Menu = _MenuScope
    Popup = _PopupScope
    PopupModal = _PopupModalScope
    PopupContextItem = _PopupContextItemScope
    PopupContextWindow = _PopupContextWindowScope
    PopupContextVoid = _PopupContextVoidScope
    Tooltip = _TooltipScope
    Table = _TableScope
    TabBar = _TabBarScope
    TabItem = _TabItemScope
    Combo = _ComboScope
    ListBox = _ListBoxScope
    DragDropSource = _DragDropSourceScope
    DragDropTarget = _DragDropTargetScope
    TreeNode = _TreeNodeScope
    MultiSelect = _MultiSelectScope
    StyleColor = _StyleColorScope
    StyleVar = _StyleVarScope
    Font = _FontScope
    ItemWidth = _ItemWidthScope
    TextWrap = _TextWrapScope
    ItemFlag = _ItemFlagScope
    ButtonRepeat = _ButtonRepeatScope
    ID = _IDScope
    ClipRect = _ClipRectScope


class ImGui:
    """Facade/index for the new ImGui runtime and its grouped helper surfaces."""

    Runtime = _ImGuiRuntime
    Methods = _MethodGroups
    Scopes = _Scopes
    ui = _ui
    default = _ui

    @staticmethod
    def create() -> _ImGuiRuntime:
        return _ImGuiRuntime()

__all__ = ['ImGui']
