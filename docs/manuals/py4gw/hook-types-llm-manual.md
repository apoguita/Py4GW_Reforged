# Hook Types LLM Manual

## Goal

This manual is for agents changing `include/base/hook_types.h`.

These types are small, but they define the shared contract between hook infrastructure and hook consumers.

## Current Contract

The header defines:

- an empty `HookEntry` marker type
- `HookStatus { blocked, altitude }`
- `HookCallback<Ts...>` as `std::function<void(HookStatus* status, Ts...)>`

This should stay aligned with `hooker` behavior.

## What To Preserve

Always preserve:

- the callback-first control channel through `HookStatus*`
- field compatibility for `HookStatus`
- signature consistency between hook registration and dispatch

## Safe Change Shapes

Safe changes:

- documentation improvements
- carefully coordinated extensions to hook metadata when all call sites are updated together

Unsafe changes:

- changing callback parameter order
- removing `HookStatus*`
- changing `blocked` semantics implicitly
- expanding this file into a second hook framework

## Coordination Rule

If you change this header, inspect `hooker` and all hook consumers in the same change. This file is not safe to edit in isolation unless the change is purely descriptive.
