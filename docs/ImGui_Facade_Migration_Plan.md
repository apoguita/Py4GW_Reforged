# ImGui Facade Migration Plan

## Document Purpose

This document is an implementation-grade migration specification for the new `Py4GWCoreLib.ImGui` API.

This file is the reconciled source of truth. If earlier intake notes, planning notes, or stale proposal fragments disagree with this document, this document wins.

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

- [Py4GWCoreLib/ImGui.py](Py4GWCoreLib/ImGui.py:1)
- [Py4GWCoreLib/ImGui_src/_core.py](Py4GWCoreLib/ImGui_src/_core.py:1)
- [Py4GWCoreLib/ImGui_src/_scopes.py](Py4GWCoreLib/ImGui_src/_scopes.py:1)
- [Py4GWCoreLib/ImGui_src/_layout.py](Py4GWCoreLib/ImGui_src/_layout.py:1)
- [Py4GWCoreLib/ImGui_src/_text.py](Py4GWCoreLib/ImGui_src/_text.py:1)
- [Py4GWCoreLib/ImGui_src/_widgets.py](Py4GWCoreLib/ImGui_src/_widgets.py:1)
- [Py4GWCoreLib/ImGui_src/_input.py](Py4GWCoreLib/ImGui_src/_input.py:1)
- [Py4GWCoreLib/ImGui_src/_items.py](Py4GWCoreLib/ImGui_src/_items.py:1)
- [Py4GWCoreLib/ImGui_src/_window.py](Py4GWCoreLib/ImGui_src/_window.py:1)
- [Py4GWCoreLib/ImGui_src/_tree_tables.py](Py4GWCoreLib/ImGui_src/_tree_tables.py:1)
- [Py4GWCoreLib/ImGui_src/_popups.py](Py4GWCoreLib/ImGui_src/_popups.py:1)
- [Py4GWCoreLib/ImGui_src/_docking.py](Py4GWCoreLib/ImGui_src/_docking.py:1)
- [Py4GWCoreLib/ImGui_src/_system.py](Py4GWCoreLib/ImGui_src/_system.py:1)

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

with ImGui.window('Party', open=show_party) as win:
    show_party = win.open
    if not win.entered:
        return

    ImGui.text('Members')

    with ImGui.table('members', 3) as table:
        if table.entered:
            ...
```

For local modifiers, readability should take priority over compactness. This means the API should **not** teach chained one-line context managers like `with ImGui.id(...), ImGui.style.color(...):` as the normal usage pattern.

The preferred style should instead look like one of these:

```python
with ImGui.id(agent_id):
    with ImGui.text_color((1, 0, 0, 1)):
        ImGui.text('Danger')
```

And eventually:

```python
search = ImGui.state.text('inventory.search')
enabled = ImGui.state.bool('inventory.enabled', default=True)
```

The end-state design should prioritize:

- structural safety
- explicitness
- discoverability
- exception safety
- runtime-managed temporary state
- readable local styling and nesting

The key readability rule is:

- structural containers such as `window`, `table`, `popup`, and `tree_node` should use `with`
- local visual or ID modifiers should favor explicit semantic names
- comma-joined multi-context-manager one-liners should not be the primary documented style
- every scoped construct should follow one common evaluation rule


## Common Evaluation Rule

This API should adopt one cohesive rule across all scoped elements:

- every `with ImGui.*(...) as scope:` returns a scope result object
- every scope result exposes `entered: bool`
- the caller checks `if not scope.entered:` or `if scope.entered:` consistently
- no scope should silently switch to a different control-flow contract

This means the design should not mix:

```python
with ImGui.window('Party') as win:
    if not win.entered:
        return
```

with:

```python
with ImGui.table('members', 3):
    ...
```

That inconsistency would make the API harder to learn than a slightly more explicit common pattern.

### Required consequence

All scopes must participate in the same public protocol.

Examples:

```python
with ImGui.window('Party', open=show_party) as win:
    if not win.entered:
        show_party = win.open
        return
    show_party = win.open
    ...
```

```python
with ImGui.table('members', 3) as table:
    if not table.entered:
        return
    ...
```

```python
with ImGui.id('party.members') as id_scope:
    if not id_scope.entered:
        return
    ...
```

For scopes like `id`, `item_width`, or `text_color`, `entered` will effectively always be `True`, but they should still expose the same result protocol so the system remains uniform.


## Final Decisions Locked By This Plan

The next implementation pass should treat the following points as settled decisions, not open design questions.

### 1. The evaluation property name is `entered`

The public evaluation property is:

- `scope.entered`

Do not rename it to:

- `active`
- `rendered`
- `opened`
- `ok`
- `should_render`

Reason:

- `entered` is already used throughout this plan
- it maps well to ImGui begin/end semantics
- it is short, explicit, and neutral enough to work across all scope kinds

### 2. Window and closeable scopes expose `.open`

For scopes that conceptually own an open/close flag, the public result property is:

- `scope.open`

This applies to:

- `window(...)`
- `popup_modal(...)`
- any future closeable scope type

The first migration should keep the state-copy pattern explicit:

```python
with ImGui.window('Party', open=show_party) as win:
    if not win.entered:
        show_party = win.open
        return show_party
    show_party = win.open
    ...
```

Do not introduce alternative first-pass contracts such as:

- mutating external variables by reference
- callback-based `on_close`
- hidden runtime auto-writeback
- key-bound `open_state=` abstractions

Those can be explored later, but they are explicitly out of scope for this migration.

### 3. The implementation should introduce `_runtime.py`

The runtime class should live in:

- [Py4GWCoreLib/ImGui_src/_runtime.py](Py4GWCoreLib/ImGui_src/_runtime.py:1)

Reason:

- `_core.py` currently carries historical meaning
- the new design is no longer just a "core helper"
- `_runtime.py` makes the ownership model obvious to future maintainers

`_core.py` may temporarily remain as a compatibility forwarding module during migration, but the target ownership should move to `_runtime.py`.

### 4. The public calling shape is direct `ImGui.*(...)`

The preferred public call style is:

```python
from Py4GWCoreLib.ImGui import ImGui

ImGui.text('Hello')

with ImGui.window('Party') as win:
    if not win.entered:
        return
    ...
```

This plan does not approve these as the primary public style:

- `ui = ImGui()`
- `with ImGui().window(...)`
- `ui = ImGui`

Reason:

- the user explicitly wants direct calls with no alias
- the resulting shape is closer to `PyImGui`
- it keeps the public call sites shorter and more discoverable

Architectural consequence:

- `ImGui` is the singleton shared runtime object exposed by the module
- `ImGuiRuntime` remains the internal assembled implementation type
- runtime-owned state such as `_StateStore` and `_StackTracker` therefore lives on that shared runtime object

### 4.1 `ImGui.create()` is not part of the approved design

This migration does not approve:

- `ImGui.create()`

Not even as an "advanced" or secondary public API.

Reason:

- it conflicts with the chosen direct-call singleton shape
- it reintroduces a second construction story for the same API
- it weakens the clarity of `ImGui` as the one public runtime object
- if isolated runtimes are ever needed for internal testing or experiments, that can remain an internal `ImGuiRuntime` concern rather than a public facade feature

So the public contract is:

- `from Py4GWCoreLib.ImGui import ImGui`
- call `ImGui.window(...)`, `ImGui.text(...)`, `ImGui.state.*(...)`, etc.
- do not expose `ImGui.create()` from the facade

### 5. The primary usage model remains `with`

This migration does not replace the context-manager model with callbacks, lambdas, decorators, or builder-style deferred trees.

The official model is:

- `with` for structural scopes
- `with` for temporary local modifiers
- one common `scope.entered` rule everywhere

Reason:

- it directly models begin/end and push/pop symmetry
- it gives exception safety naturally
- it is the clearest Python feature for scoped temporary UI state

### 6. Explicit nesting is the preferred readability policy

The documented preferred style is:

```python
with ImGui.id('party.members') as id_scope:
    if not id_scope.entered:
        return
    with ImGui.item_width(140) as width_scope:
        if not width_scope.entered:
            return
        with ImGui.table('members', 3) as table:
            if not table.entered:
                return
            ...
```

The migration must not pivot to:

- comma-joined multi-context-manager one-liners as the main style
- opaque bundling helpers like `ImGui.local(...)` as the main style
- "magic" scopes that silently suppress caller evaluation only for some scope kinds

### 7. The first migration is allowed to be explicit rather than clever

The goal of the first implementation pass is:

- correctness
- consistency
- readability

It is not:

- minimum line count
- minimum nesting depth
- aggressive abstraction of every repetitive immediate-mode pattern

If a design choice is between "slightly verbose but obvious" and "short but mentally dense", prefer the obvious form.

### 8. `_StateStore` is runtime-persistent, not frame-local

`_StateStore` lives for the lifetime of the `ImGuiRuntime` instance.

That means:

- `ImGui.state.bool('key')` returns persistent runtime-owned state
- `ImGui.state.text('key')` returns persistent runtime-owned state
- `ImGui.frame()` does not clear state
- state is cleared only by explicit calls such as `ImGui.state.reset(key)` or `ImGui.state.clear()`

Reason:

- frame-local state would make the helper nearly useless for real immediate-mode authoring
- the whole point of `ImGui.state.*(...)` is to reduce repetitive caller-side persistence boilerplate

### 9. `_StackTracker` uses two different severities for two different failures

The policy is:

- immediate underflow in `_StackTracker.pop(...)` is a programmer error and should raise `RuntimeError`
- end-of-frame imbalance detected by `ImGui.frame()` should log by default, not raise, unless a future strict mode is deliberately added

Reason:

- underflow means the implementation attempted an impossible pop and should fail fast
- frame imbalance diagnostics are valuable in production-style UI rendering and should not necessarily tear down rendering immediately

So the first migration should implement:

- `pop(kind)` -> raises on underflow
- `frame().__exit__(...)` -> logs imbalance through project logging, does not raise by default

### 10. `_CompositeScope.entered` aggregates with logical `all`

`ImGui.scoped(...)` must follow the same public rule as every other scope.

That means:

- the object returned from `with ImGui.scoped(...) as scope:` must expose `scope.entered`
- `scope.entered` is `True` only if every nested sub-scope entered successfully
- in other words, composite evaluation is `all(child.entered for child in children)`

This also means `_CompositeScope.__enter__()` should not return raw `self` without an `entered` contract. It should return a result object or itself with a fully defined `.entered`.

### 11. Font naming is intentionally split by role

The public naming split is:

- `ImGui.font(font_handle)` or `ImGui.font(font_obj)` -> temporary font scope factory
- `ImGui.font_obj` -> current font getter/property

Reason:

- `font(...)` reads naturally as "use this font temporarily"
- `font_obj` is clearly a getter-like data/property name, not a scope factory

The implementation pass should not rename `ImGui.font(...)` to `push_font(...)` as the primary path.

### 12. `ImGui_src/__init__.py` is internal-only after migration

Its role after migration should be one of the following:

- a minimal internal convenience re-export for `ImGui_src`
- or an almost-empty package marker

It must not become:

- a second public entry point
- the preferred import surface for users
- a parallel facade competing with `Py4GWCoreLib.ImGui`

Documentation and examples should always point to:

- `from Py4GWCoreLib.ImGui import ImGui`

The shared runtime model is the approved public contract for this migration.


## Public API Concept

The runtime object should become the main product.

The module-level facade in [Py4GWCoreLib/ImGui.py](Py4GWCoreLib/ImGui.py:1) should expose:

- `ImGui`

The exported `ImGui` object should expose:

- structural scope factories
- widgets
- grouped sub-surfaces
- state helpers
- safety helpers


## Recommended Public Surface

The following is the recommended conceptual shape. The exact file split may vary, but the **public surface** should resemble this.

### Structural scopes

- `ImGui.window(...)`
- `ImGui.child(...)`
- `ImGui.group()`
- `ImGui.menu_bar()`
- `ImGui.main_menu_bar()`
- `ImGui.menu(...)`
- `ImGui.popup(...)`
- `ImGui.popup_modal(...)`
- `ImGui.popup_context_item(...)`
- `ImGui.popup_context_window(...)`
- `ImGui.popup_context_void(...)`
- `ImGui.tooltip()`
- `ImGui.table(...)`
- `ImGui.tab_bar(...)`
- `ImGui.tab_item(...)`
- `ImGui.combo(...)`
- `ImGui.list_box(...)`
- `ImGui.drag_drop_source(...)`
- `ImGui.drag_drop_target()`
- `ImGui.tree_node(...)`
- `ImGui.multi_select(...)`

### Local stack scopes

- `ImGui.style.color(...)`
- `ImGui.style.var(...)`
- `ImGui.font(...)`
- `ImGui.text_color(...)`
- `ImGui.item_width(...)`
- `ImGui.text_wrap(...)`
- `ImGui.item_flag(...)`
- `ImGui.button_repeat(...)`
- `ImGui.id(...)`
- `ImGui.clip_rect(...)`
- `ImGui.disabled(...)`

### Layout helpers

- `ImGui.separator()`
- `ImGui.same_line(...)`
- `ImGui.new_line()`
- `ImGui.spacing()`
- `ImGui.indent(...)`
- `ImGui.unindent(...)`
- `ImGui.dummy(...)`

### Text helpers

- `ImGui.text(...)`
- `ImGui.text_colored(...)`
- `ImGui.text_disabled(...)`
- `ImGui.text_wrapped(...)`
- `ImGui.bullet_text(...)`
- `ImGui.label_text(...)`

### Widget helpers

- `ImGui.button(...)`
- `ImGui.small_button(...)`
- `ImGui.invisible_button(...)`
- `ImGui.arrow_button(...)`
- `ImGui.checkbox(...)`
- `ImGui.radio_button(...)`
- `ImGui.selectable(...)`
- `ImGui.progress_bar(...)`

### Input helpers

- `ImGui.input.text(...)`
- `ImGui.input.text_with_hint(...)`
- `ImGui.input.text_multiline(...)`
- `ImGui.input.float(...)`
- `ImGui.input.float2(...)`
- `ImGui.input.float3(...)`
- `ImGui.input.float4(...)`
- `ImGui.input.int(...)`
- `ImGui.input.int2(...)`
- `ImGui.input.int3(...)`
- `ImGui.input.int4(...)`
- `ImGui.input.double(...)`
- `ImGui.input.combo(...)`
- `ImGui.input.list_box(...)`

### State helpers

- `ImGui.state.bool(...)`
- `ImGui.state.text(...)`
- `ImGui.state.int(...)`
- `ImGui.state.float(...)`
- `ImGui.state.choice(...)`
- `ImGui.state.get(...)`
- `ImGui.state.set(...)`
- `ImGui.state.reset(...)`

### Safety helpers

- `ImGui.scoped(...)`
- `ImGui.frame(...)`


## Readability Policy

This migration should explicitly optimize for readable call sites, not just fewer lines.

### Preferred patterns

#### Structural scopes

Structural UI containers should use explicit `with` blocks:

```python
with ImGui.window('Party', open=show_party) as win:
    if not win.entered:
        show_party = win.open
        return
    ...
```

```python
with ImGui.table('members', 3) as table:
    if not table.entered:
        return
    ...
```

This is one of the strongest parts of the proposal and should remain central.

#### Single local modifier

If there is only one local modifier, a direct scope is clear:

```python
with ImGui.text_color((1, 0, 0, 1)) as color_scope:
    if not color_scope.entered:
        return
    ImGui.text('Danger')
```

#### Two local modifiers

If there are only one or two modifiers, nested scopes are preferable to a compressed one-liner:

```python
with ImGui.id(agent_id) as id_scope:
    if not id_scope.entered:
        return
    with ImGui.text_color((1, 0, 0, 1)) as color_scope:
        if not color_scope.entered:
            return
        ImGui.text('Danger')
```

This is longer than `with ImGui.id(...), ImGui.text_color(...):`, but significantly easier to read.

#### Many local modifiers

When local setup becomes noisy, still prefer explicit nested scopes over opaque shorthand unless a helper proves clearly more readable in real usage:

```python
with ImGui.id(agent_id) as id_scope:
    if not id_scope.entered:
        return
    with ImGui.item_width(120) as width_scope:
        if not width_scope.entered:
            return
        with ImGui.text_color((1, 0, 0, 1)) as color_scope:
            if not color_scope.entered:
                return
            ImGui.text('Danger')
```

### Discouraged patterns

The following should be considered legal-but-discouraged, and should not be used in primary examples:

```python
with ImGui.id(agent_id), ImGui.style.color(PyImGui.Col.Text, (1, 0, 0, 1)):
    ImGui.text('Danger')
```

Reason:

- it compresses too much state setup into one line
- it makes the code look clever rather than clear
- it exposes low-level styling mechanics in places where the reader likely only cares about intent

### Design consequence

The API should provide semantic helpers for common local styling so that callers do not constantly need to write low-level `style.color(enum, value)` code.

Recommended semantic helpers include:

- `ImGui.text_color(color)`
- `ImGui.item_width(width)`
- `ImGui.alpha(value)` if useful
- `ImGui.enabled()` / `ImGui.disabled(...)`


## Recommended Naming Policy

### Scope names should describe temporary context, not raw stack mechanics

Good:

- `font(...)`
- `id(...)`
- `style.color(...)`
- `style.var(...)`
- `text_color(...)`
- `item_width(...)`

Avoid as primary API:

- `push_font(...)`
- `push_style_color(...)`
- `push_style_var(...)`

Reason:

Users should think in terms of temporary context, not stack primitives.

### Semantic aliases should exist for common styling cases

Low-level `ImGui.style.color(enum, value)` should remain available, but it should not be the only readable way to express common intent.

Recommended semantic wrappers:

- `ImGui.text_color(color)` wraps `ImGui.style.color(PyImGui.Col.Text, color)`
- `ImGui.disabled(...)` remains semantic and clear
- optionally more semantic wrappers may be added later if real usage justifies them

The goal is not to create dozens of tiny aliases for every enum. The goal is to cover the small number of style intents that appear constantly in real UI code.

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

- [Py4GWCoreLib/ImGui.py](Py4GWCoreLib/ImGui.py:1)

Recommended shape:

```python
from .ImGui_src._runtime import ImGuiRuntime

ImGui = ImGuiRuntime()


__all__ = ['ImGui']
```

Important intent:

- the public module should become small and authoritative
- it should expose the public contract, not an index of mixin files
- its small size is intentional, not a sign that it is "empty"

Why one import is enough:

- `_runtime.py` is where the full runtime type is assembled
- `ImGuiRuntime` already pulls together mixins, scope factories, grouped surfaces, state helpers, and safety helpers
- callers do not need those internal pieces re-exported separately from `ImGui.py`
- once `ImGui` is imported, the entire API is reachable through that object

The key mental model is:

- `ImGui.py` is the public door
- `ImGuiRuntime` is the actual house
- `ImGui` is the one shared house instance the user walks into

So this is correct:

```python
from Py4GWCoreLib.ImGui import ImGui

with ImGui.window('Party') as win:
    ...
```

And this is the intended consequence:

- `ImGui.window(...)`
- `ImGui.table(...)`
- `ImGui.text(...)`
- `ImGui.input.text(...)`
- `ImGui.style.color(...)`
- `ImGui.state.bool(...)`

all work because the shared runtime object owns the full assembled API.

What `ImGui.py` must not become again:

- a shallow import hub that re-exports many unrelated internals
- a second copy of runtime assembly logic
- a misleading "index" whose size is padded just to look substantial

Its value is not in having many lines. Its value is in being the single, stable, obvious import path for the new API.


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

    def text_color(self, color):
        return self.style.text_color(color)

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
- common local styling should have semantic wrappers so callers do not have to think in raw enum terms
- explicit nested local scopes are preferred over opaque grouped shorthand
- all scope-returning APIs must share the same caller-side `.entered` contract


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
- both categories still expose the same public `.entered` evaluation rule


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

    def text_color(self, color):
        return _StyleColorScope(self._runtime, PyImGui.Col.Text, color)
```

Intent:

- `style.color(...)` remains the low-level escape hatch
- `text_color(...)` is the preferred readable API for a very common case


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
State is runtime-persistent across frames until explicitly reset or cleared.


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

Severity policy:

- underflow is an exception
- end-of-frame imbalance is a diagnostic log by default


### 12. Composite scope helper

Recommended skeleton:

```python
from contextlib import ExitStack


class _CompositeScope:
    def __init__(self, *scopes):
        self._scopes = scopes
        self._stack = ExitStack()
        self.entered = True

    def __enter__(self):
        for scope in self._scopes:
            result = self._stack.enter_context(scope)
            entered = getattr(result, 'entered', bool(result))
            self.entered = self.entered and bool(entered)
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._stack.__exit__(exc_type, exc, tb)
```

Important usage note:

- `ImGui.scoped(...)` should exist as a power tool
- it should not be the primary usage pattern shown in introductory examples
- primary examples should prefer explicit nested scopes
- its `.entered` value is the logical `all(...)` of the child scopes it entered


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
            self._runtime._log_stack_imbalance(diff)
```

The default contract for the first migration is:

- log imbalance at frame end
- do not raise by default
- reserve hard-fail behavior for immediate underflow and future optional strict mode


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
5. Make every scoped API participate in the same public `.entered` evaluation rule, even where entered is mechanically always `True`.
6. Keep temporary `__bool__` compatibility if helpful.

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
   - `text_color`
2. Keep temporary aliases:
   - `push_font`
   - `id_scope`
   - `combo_scope`
   - `list_box_scope`
3. Add `style.color` and `style.var` as preferred paths.
4. Explicitly avoid using comma-joined multi-scope `with` examples in docs.

Expected outcome:

- the API starts to read like a toolkit instead of a translated C binding
- common local modifier usage becomes clearer instead of denser


### Phase 4: Composition and frame-safety helpers

Target files:

- runtime implementation
- scope helpers

Tasks:

1. Add `ImGui.scoped(...)`
2. Add `ImGui.frame()`
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
   - `ImGui`
3. Move explanatory docs into the module/class docstrings.

Expected outcome:

- `ImGui.py` becomes the clear entry point rather than an index of internals
- callers use the shared runtime through `ImGui`


### Phase 6: Compatibility review and cleanup

Tasks:

1. Audit any early new-API call sites.
2. Switch them to preferred names if they exist.
3. Remove deprecated compatibility aliases only after confirming adoption.


## File-By-File Execution Map

This section is the concrete implementation map the next model should follow.

### [Py4GWCoreLib/ImGui.py](Py4GWCoreLib/ImGui.py:1)

Target responsibility:

- public entry point only
- exports `ImGui`
- instantiates one shared `ImGuiRuntime` object
- exposes that object as `ImGui`

Must not contain:

- legacy imports
- raw wrapper re-exports from many internal modules
- UI behavior logic
- alternative public import stories that bypass the facade

### [Py4GWCoreLib/ImGui_src/_runtime.py](Py4GWCoreLib/ImGui_src/_runtime.py:1)

Target responsibility:

- owns `ImGuiRuntime`
- owns grouped surfaces
- owns runtime state store
- owns stack tracker
- owns top-level scope factories
- acts as the conceptual center of the API

Must absorb from current `_core.py`:

- the runtime/mixin composition role
- current top-level scope factories
- current runtime-owned properties and helpers

### [Py4GWCoreLib/ImGui_src/_core.py](Py4GWCoreLib/ImGui_src/_core.py:1)

Target responsibility during migration:

- temporary compatibility shim only, if needed

End-state preference:

- either removed
- or reduced to a minimal forwarding import with a clear deprecation comment

### [Py4GWCoreLib/ImGui_src/_scopes.py](Py4GWCoreLib/ImGui_src/_scopes.py:1)

Target responsibility:

- scope result classes
- base scope classes
- unconditional-end scopes
- conditional-end scopes
- composite scope helper
- frame validation scope

Must be rewritten around:

- explicit `entered`
- explicit `open`
- correct end-call behavior
- runtime tracker hooks

### Existing feature modules under `ImGui_src/`

Files:

- `_layout.py`
- `_text.py`
- `_widgets.py`
- `_input.py`
- `_items.py`
- `_window.py`
- `_tree_tables.py`
- `_popups.py`
- `_docking.py`
- `_system.py`

Target responsibility:

- keep mixin-style direct wrappers and high-level helper methods grouped by domain
- avoid letting them own lifecycle policy
- defer scope semantics to `_runtime.py` and `_scopes.py`

Rule:

- feature modules should define behavior-facing methods
- scope lifecycle correctness should not be duplicated separately inside each feature module

### [Py4GWCoreLib/ImGui_src/__init__.py](Py4GWCoreLib/ImGui_src/__init__.py:1)

Target responsibility:

- internal package convenience only, if retained

Must not become:

- a public import target for documentation
- a second facade
- the place where runtime policy is defined

### Optional new helper modules

These are acceptable if they simplify the implementation:

- `_state.py`
- `_style_surface.py`
- `_input_surface.py`
- `_tracking.py`

They are optional because the public API shape matters more than the private file split.


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


## Compatibility Matrix

This table freezes the preferred canonical names versus allowed temporary aliases.

| Canonical API | Temporary Compatibility Alias | Keep Long-Term |
|---|---|---|
| `ImGui.font(...)` | `ImGui.push_font(...)` | No |
| `ImGui.style.color(...)` | `ImGui.style_color(...)` | No |
| `ImGui.style.var(...)` | `ImGui.style_var(...)` | No |
| `ImGui.combo(...)` | `ImGui.combo_scope(...)` | No |
| `ImGui.list_box(...)` | `ImGui.list_box_scope(...)` | No |
| `ImGui.id(...)` | `ImGui.id_scope(...)` | No |
| `scope.entered` | `bool(scope)` | No |
| `ImGui.window(...)` | `ImGui().window(...)` | No |
| `ImGui.window(...)` | `ui.window(...)` as primary documented style | No |
| `ImGui.font_obj` | alternate public getter names invented during migration | No |

Rule:

- the left column is the documented API
- the middle column is migration-only
- the right column should remain `No` unless this document is revised deliberately

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
  - `with ImGui.window(...)`
  - `with ImGui.table(...)`
  - `with ImGui.text_color(...)`
  - `with ImGui.id(...)`
- every scoped construct follows the same explicit `.entered` evaluation rule
- push/pop implementation detail is not the primary naming model
- no confusing module-level aliases are required
- the documented style avoids comma-joined multi-context-manager one-liners for local modifiers

### Safety

- stack-like scopes are runtime-tracked
- mismatch diagnostics exist
- frame validation exists

### Conceptual clarity

- `ImGui.py` is a true public entry point
- the runtime object is the main conceptual API
- the new facade remains fully isolated from `ImGui_Legacy`


## Canonical Usage Patterns

These examples are the blessed usage style for the first migration. New examples and early adopters should follow them unless this document is intentionally revised.

### 1. Standard window

```python
with ImGui.window('Party', open=show_party) as win:
    if not win.entered:
        show_party = win.open
        return show_party
    show_party = win.open

    ImGui.text('Members')
```

### 2. Window plus table

```python
with ImGui.window('Party', open=show_party) as win:
    if not win.entered:
        show_party = win.open
        return show_party
    show_party = win.open

    with ImGui.table('members', 3) as table:
        if not table.entered:
            return show_party
        ...
```

### 3. Local semantic modifier

```python
with ImGui.text_color((1, 0, 0, 1)) as color_scope:
    if not color_scope.entered:
        return
    ImGui.text('Danger')
```

### 4. Explicit nested local setup

```python
with ImGui.id('party.members') as id_scope:
    if not id_scope.entered:
        return
    with ImGui.item_width(140) as width_scope:
        if not width_scope.entered:
            return
        with ImGui.table('members', 3) as table:
            if not table.entered:
                return
            ...
```

### 5. Runtime state usage

```python
search = ImGui.state.text('party.search')
enabled = ImGui.state.bool('party.enabled', default=True)
selected_index = ImGui.state.int('party.selected_index', default=0)
```

### 6. Advanced composition helper

`ImGui.scoped(...)` is allowed, but it is not the primary teaching style.

Example:

```python
with ImGui.scoped(ImGui.id('party.members'), ImGui.item_width(140)) as scope:
    if not scope.entered:
        return
    ...
```

This helper exists for advanced composition, not as the default readability story.


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


def draw_party_window(show_party: bool) -> bool:
    with ImGui.frame():
        with ImGui.window('Party', open=show_party) as win:
            if not win.entered:
                show_party = win.open
                return show_party
            show_party = win.open

            search = ImGui.state.text('party.search')
            ImGui.text('Members')

            with ImGui.id('party.members') as id_scope:
                if not id_scope.entered:
                    return show_party
                with ImGui.item_width(140) as width_scope:
                    if not width_scope.entered:
                        return show_party
                    with ImGui.table('members', 3) as table:
                        if not table.entered:
                            return show_party
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
3. Enforce one common caller-side evaluation rule for every scoped API.
4. Make the runtime own stacks, state, and grouped surfaces.
5. Add `style`, `input`, and `state` as coherent sub-surfaces.
6. Add semantic local helpers such as `text_color(...)`.
7. Add `scoped(...)` and `frame(...)`, but treat `scoped(...)` as an advanced helper rather than the primary readability story.
8. Make `ImGui.py` the public contract, not merely an index.
9. Keep total separation from `ImGui_Legacy`.
10. Implement the file ownership described in `File-By-File Execution Map`.
11. Treat `Canonical Usage Patterns` as the documentation source of truth for examples.
12. Do not invent alternative evaluation/property naming during implementation.
