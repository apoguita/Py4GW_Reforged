# Hooker User Manual

`PY4GW::HookBase` is the MinHook-backed hook management layer.

Main API in `include/base/hooker.h`:

- `Initialize()`
- `Deinitialize()`
- `EnableHooks(void* target = nullptr)`
- `DisableHooks(void* target = nullptr)`
- `CreateHook(...)`
- `CreateHookRaw(...)`
- `RemoveHook(...)`
- `EnterHook()`
- `LeaveHook()`
- `GetInHookCount()`

There is also a templated `THook<T>` wrapper for typed detour/retour flows.

Use it for:

- function detours
- tracked hook enable/disable operations
- hook nesting accounting

Typical pattern:

1. initialize hooker
2. create hooks
3. enable hooks
4. disable/remove hooks during shutdown
5. deinitialize hooker
