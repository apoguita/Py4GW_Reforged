# ImGui Implementation Correction Instructions

## Purpose

This document is a corrective handoff for the already-performed ImGui implementation pass.

It exists because the current code is close to the approved design, but it still violates one of the most important architectural rules:

- there must be exactly one singleton runtime
- that singleton must be `Py4GWCoreLib.ImGui.ImGui`
- no secondary `ImGui`
- no secondary `ui`
- no alternate public construction/import path

This is not a fresh design proposal. The design has already been approved in
[docs/ImGui_Facade_Migration_Plan.md](docs/ImGui_Facade_Migration_Plan.md:1).

This document explains exactly what still needs to be corrected in the implementation so it adheres to that approved plan.


## Current Status

### What is correct already

The current implementation already matches the plan in these important ways:

- [Py4GWCoreLib/ImGui.py](Py4GWCoreLib/ImGui.py:1) is now a thin public facade
- [Py4GWCoreLib/ImGui_src/_runtime.py](Py4GWCoreLib/ImGui_src/_runtime.py:1) exists and owns the assembled runtime
- [Py4GWCoreLib/ImGui_src/_scopes.py](Py4GWCoreLib/ImGui_src/_scopes.py:1) uses explicit result objects with `.entered`
- `_StateStore` is runtime-persistent
- `_StackTracker` underflow raises immediately
- frame imbalance logs instead of raising by default
- semantic helper `text_color(...)` exists
- direct public usage through `ImGui.window(...)`, `ImGui.text(...)`, and `ImGui.state.*(...)` exists

### What is still wrong

The implementation still exposes more than one runtime path.

That is the defect this correction pass must eliminate.


## Non-Negotiable Final Rule

After the correction pass, the implementation must satisfy all of the following:

1. There is only one shared runtime instance.
2. That instance lives in [Py4GWCoreLib/ImGui.py](Py4GWCoreLib/ImGui.py:1).
3. It is exposed as:

```python
ImGui = ImGuiRuntime()
```

4. No other module may expose another `ImGui` singleton instance.
5. No other module may expose `ui = ...`.
6. No other module may present itself as an alternative public facade.


## Why This Matters

The new approved design is singleton-runtime based.

That means these runtime-owned systems must all refer to the same object:

- `_StateStore`
- `_StackTracker`
- grouped surfaces like `style`, `input`, and `state`
- future cached state or diagnostic state

If another module creates another runtime instance, then the design is broken even if the syntax still "works".

Examples of what goes wrong if two instances survive:

- `ImGui.state.bool('x')` and `ImGui_src.ui.state.bool('x')` would not share state
- stack tracking would be split across instances
- debugging would become harder because behavior would depend on which import path a caller used
- the public API would no longer have a single authoritative entry point


## Files That Must Be Corrected

### 1. [Py4GWCoreLib/ImGui.py](Py4GWCoreLib/ImGui.py:1)

This file is already conceptually correct.

It should remain the one and only public singleton facade:

```python
from .ImGui_src._runtime import ImGuiRuntime

ImGui = ImGuiRuntime()

__all__ = ['ImGui']
```

Do not expand it again.

Do not turn it back into:

- an import index
- a static wrapper hub
- a constructor facade
- a dual-path facade with `default`, `create`, or `ui`


### 2. [Py4GWCoreLib/ImGui_src/__init__.py](Py4GWCoreLib/ImGui_src/__init__.py:1)

This file is currently wrong.

Current problem:

- it aliases `ImGuiRuntime as ImGui`
- it creates `ui = ImGui()`

That means it creates a second runtime instance and a second public-looking access path.

This must be removed.

#### Required correction

Replace the file content with one of these two shapes.

Preferred minimal shape:

```python
"""Internal package for the Reforged ImGui implementation."""
```

Acceptable internal-convenience shape:

```python
"""Internal package for the Reforged ImGui implementation."""

from ._runtime import ImGuiRuntime

__all__ = ['ImGuiRuntime']
```

#### Explicitly forbidden content

Do not leave any of the following:

```python
from ._runtime import ImGuiRuntime as ImGui
ui = ImGui()
```

Do not expose:

- `ImGui`
- `ui`
- a shared instance
- a convenience singleton

This package must be internal-only after the correction.


### 3. [Py4GWCoreLib/ImGui_src/_core.py](Py4GWCoreLib/ImGui_src/_core.py:1)

This file may remain as a compatibility shim, but only as a type shim, not as a facade.

Current problem:

- it currently re-exports `ImGuiRuntime as ImGui`

That keeps another symbolic facade alive, even if it is not the main one.

#### Required correction

Replace it with this shape:

```python
"""Deprecated compatibility shim for the Reforged ImGui runtime.

Import from ``._runtime`` in new internal code.
"""

from ._runtime import ImGuiRuntime

__all__ = ['ImGuiRuntime']
```

#### Explicitly forbidden content

Do not alias:

```python
from ._runtime import ImGuiRuntime as ImGui
```

Do not instantiate anything there.

Do not expose:

- `ImGui`
- `ui`
- a facade object

This file is allowed only as a temporary internal compatibility layer.


### 4. [Py4GWCoreLib/ImGui_src/_runtime.py](Py4GWCoreLib/ImGui_src/_runtime.py:1)

This file is mostly correct and should remain the actual implementation owner.

Only one public-contract cleanup is still recommended.

#### Recommended correction

Current method:

```python
def window(self, name: str, p_open=None, *, open=None, flags: int = 0):
    resolved_open = p_open if p_open is not None else open
    return _WindowScope(self, name, resolved_open, flags)
```

Approved facade contract:

```python
def window(self, name: str, *, open=None, flags: int = 0):
    return _WindowScope(self, name, open, flags)
```

#### Why this should change

The new facade is supposed to present a clean project-facing API.

`p_open` is raw-binding leakage from lower-level naming and should not remain part of the new primary surface unless there is a very strong backward-compatibility reason.

This is not as severe as the duplicate-singleton problem, but it should still be corrected for full adherence.


## Exact Correction Sequence

The next model should apply the corrections in this exact order.

### Step 1. Fix `ImGui_src/__init__.py`

Reason:

- this is the actual duplicate-runtime bug
- removing it first eliminates split-state risk immediately

Action:

1. Delete the current contents.
2. Replace them with the preferred minimal internal package docstring, or the allowed `ImGuiRuntime`-only internal export.
3. Ensure there is no `ImGui = ...` and no `ui = ...`.

### Step 2. Fix `_core.py`

Reason:

- this removes the second symbolic facade path
- it keeps `_core.py` compatible as an internal shim without letting it masquerade as the public contract

Action:

1. Replace `ImGuiRuntime as ImGui` with `ImGuiRuntime`.
2. Add `__all__ = ['ImGuiRuntime']`.
3. Keep the deprecation wording.

### Step 3. Tighten `_runtime.py.window()`

Reason:

- this cleans the remaining public API drift

Action:

1. Remove `p_open`.
2. Keep only keyword `open`.
3. Pass `open` directly into `_WindowScope`.

### Step 4. Verify no duplicate singleton remains

Run a repo search and verify all of the following:

- no `ui = ImGui()` remains under `Py4GWCoreLib/ImGui_src`
- no `ImGui = ImGuiRuntime()` exists outside `Py4GWCoreLib/ImGui.py`
- no `ImGuiRuntime as ImGui` remains in `_core.py` or `ImGui_src/__init__.py`


## Verification Checklist

After the corrections, verify these points explicitly.

### Singleton verification

Expected true:

- [Py4GWCoreLib/ImGui.py](Py4GWCoreLib/ImGui.py:1) contains `ImGui = ImGuiRuntime()`

Expected false everywhere else:

- `ui = ImGui()`
- `ImGuiRuntime as ImGui`
- `ImGui = ImGuiRuntime()` outside `Py4GWCoreLib/ImGui.py`

### Import-surface verification

Expected public import:

```python
from Py4GWCoreLib.ImGui import ImGui
```

Expected non-public/internal-only:

- `Py4GWCoreLib.ImGui_src`
- `Py4GWCoreLib.ImGui_src._core`
- `Py4GWCoreLib.ImGui_src._runtime`

### Behavior verification

These should still work after cleanup:

```python
from Py4GWCoreLib.ImGui import ImGui

ImGui.text('hello')

with ImGui.window('Party') as win:
    if not win.entered:
        return
```

```python
value = ImGui.state.bool('demo.flag', default=True)
```

```python
with ImGui.text_color((1, 0, 0, 1)) as color_scope:
    if color_scope.entered:
        ImGui.text('Danger')
```


## What Not To Reopen

The correction pass must not reopen these already-settled decisions:

- do not bring back `ImGui.default`
- do not bring back `ImGui.create()`
- do not bring back `ui = ImGui()`
- do not turn `ImGui.py` into a large import index again
- do not switch back to constructor-based usage
- do not reintroduce any bridge to `ImGui_Legacy`


## Definition Of Done

The correction pass is complete only if:

1. exactly one singleton runtime remains
2. that singleton is `Py4GWCoreLib.ImGui.ImGui`
3. `ImGui_src/__init__.py` no longer exports `ImGui` or `ui`
4. `_core.py` no longer exports `ImGui`
5. the public usage model remains direct `ImGui.window(...)`, `ImGui.text(...)`, `ImGui.state.*(...)`
6. the implementation still compiles


## Final Instruction To The Next Model

Do not redesign anything.

Do not discuss alternatives.

Do not re-open the singleton decision.

Perform a narrow correction pass whose only goal is to remove duplicate singleton/runtime exposure and bring the implementation back into full alignment with the approved facade contract.
