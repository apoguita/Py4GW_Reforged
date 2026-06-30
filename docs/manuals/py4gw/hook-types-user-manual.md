# Hook Types User Manual

## Purpose

`include/base/hook_types.h` defines small shared types used by the hook system.

It provides:

- `PY4GW::HookEntry`
- `PY4GW::HookStatus`
- `PY4GW::HookCallback<Ts...>`

These are support types for hook registration and callback execution.

## Main Types

### `HookStatus`

`HookStatus` is passed into hook callbacks so a callback can communicate control state.

Current fields:

- `blocked`
- `altitude`

The exact meaning depends on the hook site, but the shape is shared across the hook layer.

### `HookCallback`

`HookCallback<Ts...>` is the standard callback signature:

```cpp
std::function<void(HookStatus* status, Ts...)>
```

That means callbacks receive:

1. a mutable `HookStatus*`
2. the hook-specific payload parameters

## Practical Guidance

Use these types when:

- defining new hook APIs
- storing callback signatures
- wiring new hook dispatch code

Avoid inventing alternate callback signatures unless the hook system genuinely requires a different contract.

## Safe Modification Rules

1. Keep callback signatures consistent with the hooker subsystem.
2. Do not change `HookStatus` fields casually.
3. Treat these as shared ABI-like support types inside the project.
