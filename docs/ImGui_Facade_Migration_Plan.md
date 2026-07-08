# ImGui Facade Migration Plan

## Document Purpose

This document is an implementation-grade migration specification for the new `Py4GWCoreLib.ImGui` API.

Its purpose is to let a future implementation pass redesign the new ImGui facade with minimal ambiguity. It is intentionally more detailed than a normal design note. The goal is that the next model should be able to read this file and know:

- what the new API is trying to become
- what problems in the current design are being solved
- what invariants must hold during and after the migration
- what class/interface structure is recommended
- what internal responsibilities each layer should own
- what migration order should be followed
- what compatibility behavior is acceptable during the transition
- what concrete method names and object shapes are recommended

This document is about the **new Reforged ImGui API only**.


## Scope of This Migration

This migration covers:

- the public `Py4GWCoreLib.ImGui` facade
- the new runtime object defined around `ImGui_src/_core.py`
- the scope/context-manager layer in `ImGui_src/_scopes.py`
- the introduction of grouped sub-surfaces such as `style`, `input`, and `state`
- safer stack management and validation
- explicit, structured scope results

This migration does **not** cover:

- `ImGui_Legacy`
- legacy theme or texture systems
- compatibility aliasing between legacy and new APIs
- arbitrary shuffling of wrappers between files with no behavior improvement


## Non-Negotiable Constraints

These are hard constraints for the migration.

1. `Py4GWCoreLib.ImGui` is the new API only.
2. `Py4GWCoreLib.ImGui_Legacy` is the legacy API only.
3. No aliasing, fallback, or implicit bridging is allowed between the two systems.
4. The migration must improve API safety and authoring ergonomics, not simply regroup existing wrappers into different files.
5. The new API should optimize for structured, readable, scope-based usage.
6. The public surface should reflect behavior and intent, not the internal source-file layout.
7. State and safety tracking should be owned by the runtime instance, not by ad hoc module globals.


## Current State Analysis

### Files currently involved

- [Py4GWCoreLib/ImGui.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui.py:1)
- [Py4GWCoreLib/ImGui_src/_core.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_core.py:1)
- [Py4GWCoreLib/ImGui_src/_scopes.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_scopes.py:1)
- [Py4GWCoreLib/ImGui_src/_layout.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_layout.py:1)
- [Py4GWCoreLib/ImGui_src/_text.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_text.py:1)
- [Py4GWCoreLib/ImGui_src/_widgets.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_widgets.py:1)
- [Py4GWCoreLib/ImGui_src/_input.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_input.py:1)
- [Py4GWCoreLib/ImGui_src/_items.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_items.py:1)
- [Py4GWCoreLib/ImGui_src/_window.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_window.py:1)
- [Py4GWCoreLib/ImGui_src/_tree_tables.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_tree_tables.py:1)
- [Py4GWCoreLib/ImGui_src/_popups.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_popups.py:1)
- [Py4GWCoreLib/ImGui_src/_docking.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_docking.py:1)
- [Py4GWCoreLib/ImGui_src/_system.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui_src/_system.py:1)

### What is already pointing in the right direction

The current `_core.py` class already exposes scope-friendly helpers such as:

- `window()`
- `child()`
- `group()`
- `disabled()`
- `menu()`
- `popup()`
- `table()`
- `tree_node()`

This is the correct overall direction. The important insight is already present: raw `begin/end` style APIs should be turned into context-managed structural blocks.

### What is currently inadequate

The current design is still too close to raw ImGui mechanics.

Primary problems:

1. Some scopes in `_scopes.py` unconditionally call `end_*()` even when the `begin_*()` call may have failed or returned false.
2. The scope result API relies too heavily on `__bool__` rather than explicit semantics like `.entered`.
3. The current facade module is more of an index than a real public interface.
4. Stack-based operations like style pushes and ID pushes are wrapped, but not centrally tracked by the runtime.
5. Naming still exposes stack mechanics where the user should see temporary intent scopes.
6. There is no dedicated notion of runtime-owned UI state for common immediate-mode pain points.


## High-Level Design Goal

The end-state API should feel like a structured UI authoring toolkit, not a direct re-export of `PyImGui`.

The target authoring experience is:

```python
from Py4GWCoreLib.ImGui import ImGui

ui = ImGui.default

with ui.window('Party', open=show_party) as win:
    show_party = win.open
    if not win.entered:
        return

    ui.text('Members')

    with ui.table('members', 3) as table:
        if table.entered:
            ...
```

And:

```python
with ui.id(agent_id), ui.style.color(PyImGui.Col.Text, (1, 0, 0, 1)):
    ui.text('Danger')
```

And eventually:

```python
search = ui.state.text('inventory.search')
enabled = ui.state.bool('inventory.enabled', default=True)
```

The end-state design should prioritize:

- structural safety
- explicitness
- discoverability
- exception safety
- runtime-managed temporary state
- readable local styling and nesting


## Public API Concept

The runtime object should become the main product.

The module-level class in [Py4GWCoreLib/ImGui.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui.py:1) should expose:

- `ImGui.default`
- `ImGui.create()`

The runtime object returned by these should expose:

- structural scope factories
- widgets
- grouped sub-surfaces
- state helpers
- safety helpers


## Recommended Public Surface

The following is the recommended conceptual shape. The exact file split may vary, but the **public surface** should resemble this.

### Structural scopes

- `ui.window(...)`
- `ui.child(...)`
- `ui.group()`
- `ui.menu_bar()`
- `ui.main_menu_bar()`
- `ui.menu(...)`
- `ui.popup(...)`
- `ui.popup_modal(...)`
- `ui.popup_context_item(...)`
- `ui.popup_context_window(...)`
- `ui.popup_context_void(...)`
- `ui.tooltip()`
- `ui.table(...)`
- `ui.tab_bar(...)`
- `ui.tab_item(...)`
- `ui.combo(...)`
- `ui.list_box(...)`
- `ui.drag_drop_source(...)`
- `ui.drag_drop_target()`
- `ui.tree_node(...)`
- `ui.multi_select(...)`

### Local stack scopes

- `ui.style.color(...)`
- `ui.style.var(...)`
- `ui.font(...)`
- `ui.item_width(...)`
- `ui.text_wrap(...)`
- `ui.item_flag(...)`
- `ui.button_repeat(...)`
- `ui.id(...)`
- `ui.clip_rect(...)`
- `ui.disabled(...)`

### Layout helpers

- `ui.separator()`
- `ui.same_line(...)`
- `ui.new_line()`
- `ui.spacing()`
- `ui.indent(...)`
- `ui.unindent(...)`
- `ui.dummy(...)`

### Text helpers

- `ui.text(...)`
- `ui.text_colored(...)`
- `ui.text_disabled(...)`
- `ui.text_wrapped(...)`
- `ui.bullet_text(...)`
- `ui.label_text(...)`

### Widget helpers

- `ui.button(...)`
- `ui.small_button(...)`
- `ui.invisible_button(...)`
- `ui.arrow_button(...)`
- `ui.checkbox(...)`
- `ui.radio_button(...)`
- `ui.selectable(...)`
- `ui.progress_bar(...)`

### Input helpers

- `ui.input.text(...)`
- `ui.input.text_with_hint(...)`
- `ui.input.text_multiline(...)`
- `ui.input.float(...)`
- `ui.input.float2(...)`
- `ui.input.float3(...)`
- `ui.input.float4(...)`
- `ui.input.int(...)`
- `ui.input.int2(...)`
- `ui.input.int3(...)`
- `ui.input.int4(...)`
- `ui.input.double(...)`
- `ui.input.combo(...)`
- `ui.input.list_box(...)`

### State helpers

- `ui.state.bool(...)`
- `ui.state.text(...)`
- `ui.state.int(...)`
- `ui.state.float(...)`
- `ui.state.choice(...)`
- `ui.state.get(...)`
- `ui.state.set(...)`
- `ui.state.reset(...)`

### Safety helpers

- `ui.scoped(...)`
- `ui.frame(...)`


## Recommended Naming Policy

### Scope names should describe temporary context, not raw stack mechanics

Good:

- `font(...)`
- `id(...)`
- `style.color(...)`
- `style.var(...)`
- `item_width(...)`

Avoid as primary API:

- `push_font(...)`
- `push_style_color(...)`
- `push_style_var(...)`

Reason:

Users should think in terms of temporary context, not stack primitives.

### Widget methods should remain action-oriented

Examples:

- `button(...)`
- `checkbox(...)`
- `text(...)`
- `input.text(...)`

### Compatibility naming

Old names may exist temporarily as compatibility aliases, but they should not define the long-term mental model.


## Runtime Object Responsibilities

The runtime object should be the center of the system.

### It should own:

- access to `PyImGui` IO/style/viewport/font properties
- all scope factories
- all sub-surfaces
- temporary UI state storage
- stack tracking
- optional frame-level diagnostics

### It should not:

- depend on legacy systems
- be a passive bundle of unrelated static helpers
- leak internal source-file organization into the public contract


## Recommended Class Skeletons

The following skeletons are not meant to be copied literally, but they define the target structure and responsibilities.

### 1. Public module facade

File target:

- [Py4GWCoreLib/ImGui.py](/C:/Users/Apo/Py4GW_Reforged/Py4GWCoreLib/ImGui.py:1)

Recommended shape:

```python
from .ImGui_src._runtime import ImGuiRuntime


class ImGui:
    """
    Public facade for the standalone Reforged ImGui API.

    - `ImGui.default` is the shared runtime instance.
    - `ImGui.create()` creates a new isolated runtime instance.
    - This module is intentionally separate from ImGui_Legacy.
    """

    default: ImGuiRuntime = ImGuiRuntime()

    @staticmethod
    def create() -> ImGuiRuntime:
        return ImGuiRuntime()


__all__ = ['ImGui']
```

Important intent:

- the public module should become small and authoritative
- it should expose the public contract, not an index of mixin files


### 2. Main runtime

File target:

- recommended either to evolve `_core.py` into this role, or introduce `_runtime.py`

Recommended skeleton:

```python
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
    def __init__(self):
        self._io = None
        self._style_obj = None
        self._viewport = None
        self._font_obj = None

        self._stack_tracker = _StackTracker()
        self._state_store = _StateStore()

        self.style = _StyleSurface(self)
        self.input = _InputSurface(self)
        self.state = _StateSurface(self)

    @property
    def io(self):
        ...

    @property
    def style_obj(self):
        ...

    @property
    def viewport(self):
        ...

    @property
    def font_obj(self):
        ...

    @property
    def fg_draw(self):
        ...

    @property
    def bg_draw(self):
        ...

    def frame(self):
        return _FrameScope(self)

    def scoped(self, *scopes):
        return _CompositeScope(*scopes)

    # structural scopes
    def window(self, name: str, open=None, flags: int = 0):
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

    def table(self, str_id: str, columns: int, *, flags: int = 0, outer_size=(0, 0), inner_width: float = 0.0):
        return _TableScope(self, str_id, columns, flags, outer_size, inner_width)

    def tab_bar(self, str_id: str, *, flags: int = 0):
        return _TabBarScope(self, str_id, flags)

    def tab_item(self, label: str, *, flags: int = 0, closable: bool = False):
        return _TabItemScope(self, label, flags, closable)

    def combo(self, label: str, preview: str, *, flags: int = 0):
        return _ComboScope(self, label, preview, flags)

    def list_box(self, label: str, *, size=(0, 0)):
        return _ListBoxScope(self, label, size)

    def drag_drop_source(self, *, flags: int = 0):
        return _DragDropSourceScope(self, flags)

    def drag_drop_target(self):
        return _DragDropTargetScope(self)

    def tree_node(self, label: str, *, flags: int = 0):
        return _TreeNodeScope(self, label, flags)

    def multi_select(self, *, flags: int = 0, selection_size: int = -1, items_count: int = -1):
        return _MultiSelectScope(self, flags, selection_size, items_count)

    # local stack scopes
    def font(self, idx: int = 0):
        return _FontScope(self, idx)

    def item_width(self, width: float):
        return _ItemWidthScope(self, width)

    def text_wrap(self, pos: float = 0.0):
        return _TextWrapScope(self, pos)

    def item_flag(self, option: int, enabled: bool):
        return _ItemFlagScope(self, option, enabled)

    def button_repeat(self, repeat: bool):
        return _ButtonRepeatScope(self, repeat)

    def id(self, value):
        return _IDScope(self, value)

    def clip_rect(self, x: float, y: float, w: float, h: float, *, intersect: bool = True):
        return _ClipRectScope(self, x, y, w, h, intersect)

    # compatibility aliases, temporary
    def push_font(self, idx: int = 0):
        return self.font(idx)

    def combo_scope(self, label: str, preview: str, *, flags: int = 0):
        return self.combo(label, preview, flags=flags)

    def list_box_scope(self, label: str, *, size=(0, 0)):
        return self.list_box(label, size=size)

    def id_scope(self, value):
        return self.id(value)
```

Key design intent:

- one runtime object owns everything meaningful
- sub-surfaces are properties bound to the runtime instance
- scope objects receive the runtime instance so they can report stack activity


### 3. Scope result types

Recommended skeleton:

```python
class ScopeResult:
    def __init__(self, runtime: 'ImGuiRuntime', entered: bool):
        self._runtime = runtime
        self.entered = entered

    def __bool__(self) -> bool:
        # compatibility only
        return self.entered

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
    def viewport(self):
        return PyImGui.get_window_viewport()

    @property
    def cursor(self):
        return PyImGui.get_cursor_pos()

    @property
    def scroll_x(self):
        return PyImGui.get_scroll_x()

    @property
    def scroll_y(self):
        return PyImGui.get_scroll_y()
```

```python
class CloseableScopeResult(ScopeResult):
    def __init__(self, runtime: 'ImGuiRuntime', entered: bool, open: bool):
        super().__init__(runtime, entered)
        self.open = open
```

Important note:

Short term, one shared result type is acceptable for convenience.

Long term, if necessary, the implementation may split specialized result types such as:

- `WindowScopeResult`
- `TableScopeResult`
- `PopupScopeResult`

But this is not required for the first pass.


### 4. Internal scope base classes

These should live in `_scopes.py`.

Recommended conceptual skeleton:

```python
class _BaseScope:
    def __init__(self, runtime: 'ImGuiRuntime'):
        self._runtime = runtime
```

```python
class _AlwaysEndScope(_BaseScope):
    def __init__(self, runtime: 'ImGuiRuntime'):
        super().__init__(runtime)
        self._entered = False

    def _begin(self):
        raise NotImplementedError

    def _end(self):
        raise NotImplementedError

    def __enter__(self):
        result = self._begin()
        self._entered = True
        return result

    def __exit__(self, exc_type, exc, tb):
        if self._entered:
            self._end()
```

```python
class _ConditionalEndScope(_BaseScope):
    def __init__(self, runtime: 'ImGuiRuntime'):
        super().__init__(runtime)
        self._entered = False

    def _begin(self):
        raise NotImplementedError

    def _end(self):
        raise NotImplementedError

    def __enter__(self):
        result = self._begin()
        self._entered = bool(result.entered if hasattr(result, 'entered') else result)
        return result

    def __exit__(self, exc_type, exc, tb):
        if self._entered:
            self._end()
```

Intent:

- unconditional scope endings are always performed after a successful entry
- conditional endings occur only if the scope actually opened/entered


### 5. Example: window scope

Recommended skeleton:

```python
class _WindowScope(_AlwaysEndScope):
    def __init__(self, runtime: 'ImGuiRuntime', name: str, open, flags: int):
        super().__init__(runtime)
        self._name = name
        self._open = open
        self._flags = flags

    def _begin(self):
        entered, still_open = PyImGui.begin(self._name, self._open, self._flags)
        return CloseableScopeResult(self._runtime, entered=entered, open=still_open)

    def _end(self):
        PyImGui.end()
```


### 6. Example: menu scope

Recommended skeleton:

```python
class _MenuScope(_ConditionalEndScope):
    def __init__(self, runtime: 'ImGuiRuntime', label: str, enabled: bool):
        super().__init__(runtime)
        self._label = label
        self._enabled = enabled

    def _begin(self):
        entered = PyImGui.begin_menu(self._label, self._enabled)
        return ScopeResult(self._runtime, entered=entered)

    def _end(self):
        PyImGui.end_menu()
```


### 7. Example: style color scope

Recommended skeleton:

```python
class _StyleColorScope(_AlwaysEndScope):
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
```


### 8. Style surface

Recommended skeleton:

```python
class _StyleSurface:
    def __init__(self, runtime: 'ImGuiRuntime'):
        self._runtime = runtime

    def color(self, idx: int, color):
        return _StyleColorScope(self._runtime, idx, color)

    def var(self, idx: int, value):
        return _StyleVarScope(self._runtime, idx, value)
```


### 9. Input surface

Recommended skeleton:

```python
class _InputSurface:
    def __init__(self, runtime: 'ImGuiRuntime'):
        self._runtime = runtime

    def text(self, label: str, text: str = '', flags: int = 0) -> str:
        return PyImGui.input_text(label, text, flags)

    def text_with_hint(self, label: str, hint: str, text: str = '', flags: int = 0) -> str:
        return PyImGui.input_text_with_hint(label, hint, text, flags)

    def text_multiline(self, label: str, text: str = '', size=(0, 0), flags: int = 0) -> str:
        return PyImGui.input_text_multiline(label, text, size, flags)

    def int(self, label: str, value: int, step: int = 1, step_fast: int = 100, flags: int = 0) -> int:
        return PyImGui.input_int(label, value, step, step_fast, flags)

    def float(self, label: str, value: float, step: float = 0.0, step_fast: float = 0.0, fmt: str = '%.3f', flags: int = 0) -> float:
        return PyImGui.input_float(label, value, step, step_fast, fmt, flags)
```

Intent:

- input grouping is about discoverability and API coherence
- it does not require removing all top-level convenience wrappers immediately


### 10. State store and state surface

Recommended skeleton:

```python
class _StateStore:
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
```

```python
class _StateSurface:
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
```

Important design note:

State is runtime-local, not module-global.


### 11. Stack tracker

Recommended skeleton:

```python
class _StackTracker:
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
```


### 12. Composite scope helper

Recommended skeleton:

```python
from contextlib import ExitStack


class _CompositeScope:
    def __init__(self, *scopes):
        self._scopes = scopes
        self._stack = ExitStack()

    def __enter__(self):
        for scope in self._scopes:
            self._stack.enter_context(scope)
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._stack.__exit__(exc_type, exc, tb)
```


### 13. Frame scope

Recommended skeleton:

```python
class _FrameScope:
    def __init__(self, runtime: 'ImGuiRuntime'):
        self._runtime = runtime
        self._snapshot = None

    def __enter__(self):
        self._snapshot = self._runtime._stack_tracker.snapshot()
        return self

    def __exit__(self, exc_type, exc, tb):
        diff = self._runtime._stack_tracker.diff(self._snapshot)
        if diff:
            # replace with project logging strategy
            raise RuntimeError(f'ImGui stack imbalance detected: {diff}')
```

In production, logging may be preferable to throwing, but this is the conceptual safety mechanism.


## Scope Classification Table

The following classification should guide implementation.

### Always-end scopes

- `_WindowScope`
- `_ChildScope`
- `_GroupScope`
- `_DisabledScope`
- `_TooltipScope`
- `_StyleColorScope`
- `_StyleVarScope`
- `_FontScope`
- `_ItemWidthScope`
- `_TextWrapScope`
- `_ItemFlagScope`
- `_ButtonRepeatScope`
- `_IDScope`
- `_ClipRectScope`

### Conditional-end scopes

- `_MenuBarScope`
- `_MainMenuBarScope`
- `_MenuScope`
- `_PopupScope`
- `_PopupModalScope`
- `_PopupContextItemScope`
- `_PopupContextWindowScope`
- `_PopupContextVoidScope`
- `_TableScope`
- `_TabBarScope`
- `_TabItemScope`
- `_ComboScope`
- `_ListBoxScope`
- `_DragDropSourceScope`
- `_DragDropTargetScope`
- `_TreeNodeScope`
- `_MultiSelectScope`


## Detailed Migration Plan

This section defines the exact recommended order of work.

### Phase 1: Correctness-first scope rewrite

Target files:

- `_scopes.py`
- `_core.py`

Tasks:

1. Introduce explicit result types.
2. Introduce unconditional vs conditional scope base classes.
3. Refactor all existing scope classes to inherit from the appropriate base.
4. Make window results explicitly expose `.entered` and `.open`.
5. Keep temporary `__bool__` compatibility if helpful.

Expected outcome:

- structural begin/end correctness improves before any major ergonomic reshaping


### Phase 2: Runtime-owned tracking and grouped surfaces

Target files:

- `_core.py` or new `_runtime.py`

Tasks:

1. Add `_StackTracker`.
2. Add `_StateStore`.
3. Add `style`, `input`, and `state` sub-surfaces.
4. Pass runtime references into all scope factories.
5. Start migrating stack scopes to report push/pop events.

Expected outcome:

- runtime becomes the actual owner of state and safety


### Phase 3: Public API naming cleanup

Target files:

- `_core.py`
- `ImGui.py`

Tasks:

1. Add preferred intent-based names:
   - `font`
   - `id`
   - `combo`
   - `list_box`
2. Keep temporary aliases:
   - `push_font`
   - `id_scope`
   - `combo_scope`
   - `list_box_scope`
3. Add `style.color` and `style.var` as preferred paths.

Expected outcome:

- the API starts to read like a toolkit instead of a translated C binding


### Phase 4: Composition and frame-safety helpers

Target files:

- runtime implementation
- scope helpers

Tasks:

1. Add `ui.scoped(...)`
2. Add `ui.frame()`
3. Add mismatch diagnostics

Expected outcome:

- localized style setup becomes cleaner
- stack corruption becomes diagnosable


### Phase 5: Public facade simplification

Target files:

- `ImGui.py`

Tasks:

1. Make the module-level class authoritative and small.
2. Expose only:
   - `ImGui.default`
   - `ImGui.create()`
3. Move explanatory docs into the module/class docstrings.

Expected outcome:

- `ImGui.py` becomes the clear entry point rather than an index of internals


### Phase 6: Compatibility review and cleanup

Tasks:

1. Audit any early new-API call sites.
2. Switch them to preferred names if they exist.
3. Remove deprecated compatibility aliases only after confirming adoption.


## Compatibility Policy During Migration

Compatibility is acceptable only where it smooths transition inside the new API.

### Acceptable temporary compatibility

- `push_font(...)` delegates to `font(...)`
- `style_color(...)` delegates to `style.color(...)`
- `style_var(...)` delegates to `style.var(...)`
- `combo_scope(...)` delegates to `combo(...)`
- `list_box_scope(...)` delegates to `list_box(...)`
- `id_scope(...)` delegates to `id(...)`
- `bool(scope_result)` delegates to `scope_result.entered`

### Unacceptable compatibility

- any alias from `ImGui` to `ImGui_Legacy`
- importing legacy theme, texture, or helper systems into the new facade
- keeping awkward names as the public primary path indefinitely


## Recommended Documentation To Add During Implementation

The next implementation pass should add internal documentation while coding.

### `ImGui.py`

Needs:

- module docstring
- explanation that this is the standalone Reforged API
- explanation that it is intentionally separate from legacy

### Runtime class

Needs:

- docstring describing the runtime as the owner of structural UI, state, and safety tracking

### Result classes

Needs:

- explicit documentation for `.entered`
- explicit documentation for `.open`
- note that `__bool__` is compatibility-only if retained

### Scope classes

Needs:

- indication of whether the scope is unconditional-end or conditional-end


## Acceptance Criteria

The migration should be considered complete only if all of the following are true.

### Correctness

- conditional containers do not call `end_*()` unless they were actually entered
- every scope remains exception-safe
- closeable results expose `.open`
- normal scope results expose `.entered`

### Ergonomics

- common code reads naturally:
  - `with ui.window(...)`
  - `with ui.table(...)`
  - `with ui.style.color(...)`
  - `with ui.id(...)`
- push/pop implementation detail is not the primary naming model
- no confusing module-level aliases are required

### Safety

- stack-like scopes are runtime-tracked
- mismatch diagnostics exist
- frame validation exists

### Conceptual clarity

- `ImGui.py` is a true public entry point
- the runtime object is the main conceptual API
- the new facade remains fully isolated from `ImGui_Legacy`


## Risks and Pitfalls

### Risk 1: Over-fragmenting the public API

Too many tiny namespaces will hurt discoverability. The grouped surfaces should be meaningful and few.

### Risk 2: Solving naming without solving correctness

Renaming methods before fixing scope semantics would produce a prettier but still unsafe API.

### Risk 3: Runtime state accidentally becoming global

State must be owned by the runtime instance, not module-level dicts.

### Risk 4: Generic result objects becoming semantically muddy forever

Shared result objects are acceptable short term, but the implementation should remain open to future refinement.

### Risk 5: Hidden re-coupling to legacy functionality

This migration must not reintroduce old legacy concepts into the new API.


## Recommended End-State Example

This example captures the intended direction.

```python
from Py4GWCoreLib.ImGui import ImGui

ui = ImGui.default


def draw_party_window(show_party: bool) -> bool:
    with ui.frame():
        with ui.window('Party', open=show_party) as win:
            show_party = win.open
            if not win.entered:
                return show_party

            search = ui.state.text('party.search')
            ui.text('Members')

            with ui.scoped(
                ui.id('party.members'),
                ui.style.var(PyImGui.StyleVar.CellPadding, (4, 2)),
            ):
                with ui.table('members', 3) as table:
                    if table.entered:
                        ...

    return show_party
```

This is the design target:

- structured
- explicit
- state-aware
- stack-safe
- readable


## Final Directive For The Next Implementation Pass

The next implementation pass should follow this exact intent:

1. Rebuild `_scopes.py` around unconditional versus conditional end behavior.
2. Introduce explicit result objects with `.entered` and `.open`.
3. Make the runtime own stacks, state, and grouped surfaces.
4. Add `style`, `input`, and `state` as coherent sub-surfaces.
5. Add `scoped(...)` and `frame(...)`.
6. Make `ImGui.py` the public contract, not merely an index.
7. Keep total separation from `ImGui_Legacy`.

