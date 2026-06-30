# Error Handling User Manual

## Purpose

`include/base/error_handling.h` is the thin compatibility layer that defines the project assertion macro used across the codebase.

Today it maps:

- `GWCA_ASSERT(expr)` -> `PY4GW_ASSERT(expr)`

This keeps older GWCA-style call sites aligned with the project's panic and assertion system.

## Why It Exists

Many shared headers and game-facing structs still use `GWCA_ASSERT`.

This header lets those call sites:

- keep their existing shape
- route failures into Py4GW's assertion and panic handling
- avoid mixing multiple assertion systems

## Practical Guidance

Use `GWCA_ASSERT` in shared GW-facing headers that already follow that convention.

Use `PY4GW_ASSERT` directly when working in Py4GW-specific code that does not need the compatibility alias.

## Safe Modification Rules

1. Keep assertion routing centralized.
2. Do not make failed assertions silent.
3. Do not introduce competing assertion macros without a real compatibility reason.
