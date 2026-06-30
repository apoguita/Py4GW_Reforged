# Memory User Manual

## Purpose

`GW/memory` is currently a named subsystem directory without public headers or source files in this repository state.

At the time of writing:

- `include/GW/memory` has no public headers
- `src/GW/memory` has no source files

## What To Use Instead

For current memory-related behavior, use the documented base systems:

- `memory-manager`
- `memory-patcher`
- `scanner`
- `patterns`

There is no separate Guild Wars memory manager surface under `GW/memory` yet.

## Guidance

Treat this directory as reserved until it gains real code and a public interface.
