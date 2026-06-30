# MemoryPatcher User Manual

`PY4GW::MemoryPatcher` applies and restores small byte patches in process memory.

Main API in `include/base/memory_patcher.h`:

- `SetPatch(...)`
- `SetRedirect(...)`
- `TogglePatch(bool enabled)`
- `TogglePatch()`
- `Reset()`
- `IsValid()`
- `GetIsActive()`
- `DisableHooks()`
- `EnableHooks()`

Typical usage:

1. configure the patch with `SetPatch()` or `SetRedirect()`
2. activate it with `TogglePatch(true)`
3. restore/reset it during shutdown

Important behavior:

- patchers are tracked globally
- global enable/disable walks all tracked patchers
- active patchers should normally be restored before subsystem teardown
