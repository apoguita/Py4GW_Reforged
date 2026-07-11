# IniManager Migration — Handover (Requirement Only)

> This document states **the requirement and intent** for the task. It
> deliberately contains **no analysis, conclusions, approach, or step plan** —
> the previous attempt's reasoning was discarded as unreliable. The next session
> must research the code independently before proposing how to do this.

## Intent

Replace `IniManager` (`Py4GWCoreLib/IniManager.py`) with a settings system built
on the native `PySettings` embedded module, exposed through a Python class.

## Requirement

1. **New settings class.** A Python class (`Settings`, at
   `Py4GWCoreLib/py4gwcorelib_src/Settings.py`) that provides streamlined,
   programmatic typed accessors — get/set for bool, int, float, string — backed
   by the native `PySettings` module. It should take over the settings-file
   access role currently served through `IniManager`.

2. **Support subfolders.** `IniManager` organizes settings into subfolders under
   the account directory. The `PySettings`-based system must support the same
   subfolder layout.

3. **Remove window handling from `IniManager`.** The window-persistence variables
   and logic in `IniManager` (window position/size/collapsed state) are to be
   removed. Per the requirement, window layout is now persisted by imgui's
   per-account ini (`imgui.ini`), so `IniManager` should no longer manage it.


## Relevant files (pointers, not conclusions)

- `Py4GWCoreLib/IniManager.py` — the class to be replaced. Contains window-config
  methods (`begin_window_config`, `mark_begin_success`, `track_window_collapsed`,
  `IsWindowCollapsed`, `end_window_config`) and a variable-management surface.
- `Py4GWCoreLib/py4gwcorelib_src/Settings.py` — the new Python wrapper class.
- `Py4GWCoreLib/ImGui_Legacy_src/ImGuisrc.py` — the `ImGui_Legacy` `Begin` /
  `BeginWithClose` / `End` wrappers currently call `IniManager`'s window methods.
- `stubs/PySettings.pyi` — Python stub for the native `PySettings` module.
- `../Py4GW_Reforged_Native/docs/settings-ini-design.md` — native settings design.
- `../Py4GW_Reforged_Native/src/settings/` — native `PySettings` implementation
  and pybind bindings.

## Current repo state to be aware of (facts, evaluate independently)

Work touched the repo during the discarded attempt. Verify each before relying on it:

- `Py4GWCoreLib/py4gwcorelib_src/Settings.py` exists (typed-accessor wrapper).
- `stubs/PySettings.pyi` exists.
- `../Py4GW_Reforged_Native/src/settings/settings.cpp` was changed to allow
  subfolder paths in document names; the DLL was rebuilt and a probe wrote a
  nested file successfully. (Not yet committed — confirm.)
- `test_settings_subfolder.py` (repo root) is a probe widget for that change.
- `Py4GWCoreLib/IniManager.py` and `ImGuisrc.py` are at their last committed
  state (an edit was made and reverted).

## Constraints

- Do not migrate or preserve existing on-disk settings data unless explicitly
  asked; the user has not required data migration.
- Keep changes scoped strictly to this requirement. Do not introduce adjacent
  systems or refactors that were not requested.
- Confirm the approach with the user before making code changes.
