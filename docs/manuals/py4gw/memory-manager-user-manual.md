# MemoryManager User Manual

`PY4GW::MemoryManager` exposes a small set of scanned runtime services.

Main API in `include/base/memory_manager.h`:

- `Scan()`
- `GetGWVersion()`
- `GetSkillTimer()`
- `GetGWWindowHandle()`
- `MemAlloc(...)`
- `MemRealloc(...)`
- `MemFree(...)`

This subsystem is a consumer of the scanner/pattern stack. It does not manage general-purpose application memory; it resolves and forwards Guild Wars runtime helpers.

Use it when code needs:

- the game version
- skill timer access
- the Guild Wars window handle
- GW-compatible allocation helpers
