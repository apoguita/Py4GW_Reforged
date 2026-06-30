# Logger User Manual

`Logger` is the shared text logging subsystem.

Main API in `include/base/logger.h`:

- `LogInfo`
- `LogWarning`
- `LogError`
- `LogOk`
- `LogDebug`
- `LogNotice`
- `LogPerformance`
- `LogHook`
- generic `Log(...)`
- `SetLogFile(...)`
- `GetEntries()`
- `ClearEntries()`
- assertion helpers for addresses and hooks

Behavior:

- stores recent entries in memory
- optionally appends to a log file
- always emits to `OutputDebugStringA`

Use it for user-visible operational logging. Do not use it from unsafe detach-time paths such as arbitrary `DllMain` teardown.
