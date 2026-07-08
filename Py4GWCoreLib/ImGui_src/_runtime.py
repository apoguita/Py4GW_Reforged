"""Runtime class and supporting infrastructure for the Reforged ImGui facade.

``ImGuiRuntime`` is the assembled API surface: it composes all domain mixins,
owns scope factories, sub-surfaces, stack tracking, and runtime-persistent state.

Sub-surfaces:
    ``.style`` — ``_StyleSurface``   (``.color()``, ``.var()``, ``.text_color()``)
    ``.input`` — ``_InputSurface``   (``.text()``, ``.int()``, ``.float()``, etc.)
    ``.state`` — ``_StateSurface``   (``.bool()``, ``.text()``, ``.int()``, ``.float()``, etc.)

Tracking:
    ``._stack_tracker`` — ``_StackTracker``  (push/pop with underflow detection)
    ``._state_store``   — ``_StateStore``    (runtime-persistent key-value state)

Public entry point: ``from Py4GWCoreLib.ImGui import ImGui``
"""

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
    ScopeResult,
    CloseableScopeResult,
    _WindowScope,
    _ChildScope,
    _GroupScope,
    _DisabledScope,
    _MenuBarScope,
    _MainMenuBarScope,
    _MenuScope,
    _PopupScope,
    _PopupModalScope,
    _PopupContextItemScope,
    _PopupContextWindowScope,
    _PopupContextVoidScope,
    _TooltipScope,
    _TableScope,
    _TabBarScope,
    _TabItemScope,
    _ComboScope,
    _ListBoxScope,
    _DragDropSourceScope,
    _DragDropTargetScope,
    _TreeNodeScope,
    _MultiSelectScope,
    _StyleColorScope,
    _StyleVarScope,
    _FontScope,
    _ItemWidthScope,
    _TextWrapScope,
    _ItemFlagScope,
    _ButtonRepeatScope,
    _IDScope,
    _ClipRectScope,
    _CompositeScope,
    _FrameScope,
)


# ═══════════════════════════════════════════════════════════════════════
#  Stack Tracker
# ═══════════════════════════════════════════════════════════════════════

class _StackTracker:
    """Tracks push/pop pairings for stack-based ImGui operations.

    Severity policy (locked):
        ``pop(kind)`` raises ``RuntimeError`` on underflow (programmer error).
        Frame-level imbalance is logged, not raised, by default.
    """

    def __init__(self):
        self._depths: dict[str, int] = {}
        self._history: list[tuple[str, str]] = []

    def push(self, kind: str):
        self._depths[kind] = self._depths.get(kind, 0) + 1
        self._history.append(('push', kind))

    def pop(self, kind: str):
        current = self._depths.get(kind, 0)
        if current <= 0:
            raise RuntimeError(f'ImGui stack underflow for {kind}')
        self._depths[kind] = current - 1
        self._history.append(('pop', kind))

    def snapshot(self) -> dict[str, int]:
        return dict(self._depths)

    def diff(self, before: dict[str, int]) -> dict[str, tuple[int, int]]:
        result = {}
        all_keys = set(before) | set(self._depths)
        for key in all_keys:
            old = before.get(key, 0)
            new = self._depths.get(key, 0)
            if old != new:
                result[key] = (old, new)
        return result


# ═══════════════════════════════════════════════════════════════════════
#  State Store
# ═══════════════════════════════════════════════════════════════════════

class _StateStore:
    """Runtime-persistent key-value store for UI state.

    State survives across frames for the lifetime of the ``ImGuiRuntime``
    instance. Use ``reset(key)`` or ``clear()`` for manual lifecycle control.
    """

    def __init__(self):
        self._values: dict[object, object] = {}

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value
        return value

    def ensure(self, key, default):
        if key not in self._values:
            self._values[key] = default
        return self._values[key]

    def reset(self, key):
        self._values.pop(key, None)

    def clear(self):
        self._values.clear()


# ═══════════════════════════════════════════════════════════════════════
#  Sub-surfaces
# ═══════════════════════════════════════════════════════════════════════

class _StyleSurface:
    """Grouped style sub-surface: ``ImGui.style.color(...)``, ``ImGui.style.var(...)``, ``ImGui.text_color(...)``.

    ``.color(idx, color)`` and ``.var(idx, value)`` are the low-level escape hatches.
    ``.text_color(color)`` is the preferred semantic shortcut for a common pattern.
    """

    def __init__(self, runtime: 'ImGuiRuntime'):
        self._runtime = runtime

    def color(self, idx: int, color):
        return _StyleColorScope(self._runtime, idx, color)

    def var(self, idx: int, value):
        return _StyleVarScope(self._runtime, idx, value)

    def text_color(self, color):
        return _StyleColorScope(self._runtime, PyImGui.Col.Text, color)


class _InputSurface:
    """Grouped input sub-surface: ``ImGui.input.text(...)``, ``ImGui.input.int(...)``, etc.

    Thin aliases over the flat ``_InputStateMethods`` for discoverability.
    The flat methods remain available directly on the runtime.
    """

    def __init__(self, runtime: 'ImGuiRuntime'):
        self._runtime = runtime

    def text(self, label: str, text: str = '', flags: int = 0):
        return PyImGui.input_text(label, text, flags)

    def text_with_hint(self, label: str, hint: str, text: str = '', flags: int = 0):
        return PyImGui.input_text_with_hint(label, hint, text, flags)

    def text_multiline(self, label: str, text: str = '', size=(0, 0), flags: int = 0):
        return PyImGui.input_text_multiline(label, text, size, flags)

    def int(self, label: str, value: int, step: int = 1, step_fast: int = 100, flags: int = 0):
        return PyImGui.input_int(label, value, step, step_fast, flags)

    def float(self, label: str, value: float, step: float = 0.0, step_fast: float = 0.0,
              fmt: str = '%.3f', flags: int = 0):
        return PyImGui.input_float(label, value, step, step_fast, fmt, flags)


class _StateSurface:
    """Grouped state sub-surface: ``ImGui.state.bool(...)``, ``ImGui.state.text(...)``, etc.

    Delegates to the runtime's ``_StateStore``. Keys should be qualified
    (e.g. ``'widget_name.field'``) to avoid collisions between unrelated callers.
    """

    def __init__(self, runtime: 'ImGuiRuntime'):
        self._runtime = runtime

    def get(self, key, default=None):
        return self._runtime._state_store.get(key, default)

    def set(self, key, value):
        return self._runtime._state_store.set(key, value)

    def reset(self, key):
        self._runtime._state_store.reset(key)

    def bool(self, key, default=False) -> bool:
        return self._runtime._state_store.ensure(key, bool(default))

    def text(self, key, default='') -> str:
        return self._runtime._state_store.ensure(key, str(default))

    def int(self, key, default=0) -> int:
        return self._runtime._state_store.ensure(key, int(default))

    def float(self, key, default=0.0) -> float:
        return self._runtime._state_store.ensure(key, float(default))

    def choice(self, key, default=None):
        return self._runtime._state_store.ensure(key, default)


# ═══════════════════════════════════════════════════════════════════════
#  ImGuiRuntime — the assembled API surface
# ═══════════════════════════════════════════════════════════════════════

class ImGuiRuntime(
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
    """Assembled runtime for the Reforged ImGui API.

    Owns scope factories, sub-surfaces, stack tracking, and runtime-persistent
    state. Composed from all domain mixins via multiple inheritance.

    Public entry: ``from Py4GWCoreLib.ImGui import ImGui``
    where ``ImGui`` is the module-level shared instance of this class.
    """

    def __init__(self):
        super().__init__()
        self._io = None
        self._style_obj = None
        self._viewport = None
        self._font_obj = None

        self._stack_tracker = _StackTracker()
        self._state_store = _StateStore()

        self.style = _StyleSurface(self)
        self.input = _InputSurface(self)
        self.state = _StateSurface(self)

    # ── C++ accessors (renamed to not collide with sub-surfaces) ──

    @property
    def io(self):
        if self._io is None:
            self._io = PyImGui.get_io()
        return self._io

    @property
    def style_obj(self):
        if self._style_obj is None:
            self._style_obj = PyImGui.get_style()
        return self._style_obj

    @property
    def viewport(self):
        if self._viewport is None:
            self._viewport = PyImGui.get_main_viewport()
        return self._viewport

    @property
    def font_obj(self):
        if self._font_obj is None:
            self._font_obj = PyImGui.get_font()
        return self._font_obj

    @property
    def fg_draw(self):
        return PyImGui.get_foreground_draw_list()

    @property
    def bg_draw(self):
        return PyImGui.get_background_draw_list()

    # ── Safety helpers ──

    def frame(self):
        return _FrameScope(self)

    def scoped(self, *scopes):
        return _CompositeScope(*scopes)

    # ── Structural scope factories ──

    def window(self, name: str, *, open=None, flags: int = 0):
        return _WindowScope(self, name, open, flags)

    def child(self, id: str, *, size=(0, 0), child_flags: int = 0, window_flags: int = 0):
        return _ChildScope(self, id, size, child_flags, window_flags)

    def group(self):
        return _GroupScope(self)

    def disabled(self, state: bool = True):
        return _DisabledScope(self, state)

    def menu_bar(self):
        return _MenuBarScope(self)

    def main_menu_bar(self):
        return _MainMenuBarScope(self)

    def menu(self, label: str, *, enabled: bool = True):
        return _MenuScope(self, label, enabled)

    def popup(self, str_id: str, *, flags: int = 0):
        return _PopupScope(self, str_id, flags)

    def popup_modal(self, name: str, *, open=None, flags: int = 0):
        return _PopupModalScope(self, name, open, flags)

    def popup_context_item(self, str_id: str | None = None, *, popup_flags: int = 0):
        return _PopupContextItemScope(self, str_id, popup_flags)

    def popup_context_window(self, str_id: str | None = None, *, popup_flags: int = 0):
        return _PopupContextWindowScope(self, str_id, popup_flags)

    def popup_context_void(self, str_id: str | None = None, *, popup_flags: int = 0):
        return _PopupContextVoidScope(self, str_id, popup_flags)

    def tooltip(self):
        return _TooltipScope(self)

    def table(self, str_id: str, columns: int, *, flags: int = 0,
              outer_size=(0, 0), inner_width: float = 0.0):
        return _TableScope(self, str_id, columns, flags, outer_size, inner_width)

    def tab_bar(self, str_id: str, *, flags: int = 0):
        return _TabBarScope(self, str_id, flags)

    def tab_item(self, label: str, *, flags: int = 0, closable: bool = False):
        return _TabItemScope(self, label, flags, closable)

    def drag_drop_source(self, *, flags: int = 0):
        return _DragDropSourceScope(self, flags)

    def drag_drop_target(self):
        return _DragDropTargetScope(self)

    def tree_node(self, label: str, *, flags: int = 0):
        return _TreeNodeScope(self, label, flags)

    def multi_select(self, *, flags: int = 0, selection_size: int = -1, items_count: int = -1):
        return _MultiSelectScope(self, flags, selection_size, items_count)

    # ── Local stack scope factories ──

    def font(self, idx: int = 0):
        return _FontScope(self, idx)

    def text_color(self, color):
        return self.style.text_color(color)

    def id(self, value):
        return _IDScope(self, value)

    def combo(self, label: str, preview: str, *, flags: int = 0):
        return _ComboScope(self, label, preview, flags)

    def list_box(self, label: str, *, size=(0, 0)):
        return _ListBoxScope(self, label, size)

    def item_width(self, width: float):
        return _ItemWidthScope(self, width)

    def text_wrap(self, pos: float = 0.0):
        return _TextWrapScope(self, pos)

    def item_flag(self, option: int, enabled: bool):
        return _ItemFlagScope(self, option, enabled)

    def button_repeat(self, repeat: bool):
        return _ButtonRepeatScope(self, repeat)

    def clip_rect(self, x: float, y: float, w: float, h: float, *, intersect: bool = True):
        return _ClipRectScope(self, x, y, w, h, intersect)
