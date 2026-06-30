# Memory LLM Manual

## Goal

This manual records the current state of `GW/memory`.

It is a placeholder subsystem boundary, not a real public module in the current repo state.

## Current Repo State

At the time of this manual:

- `include/GW/memory` contains no public headers
- `src/GW/memory` contains no implementation files

## Agent Guidance

Do not fabricate a GW-specific memory API here.

If a task concerns memory behavior, inspect the real base-layer systems first:

- `memory_manager`
- `memory_patcher`
- `scanner`
- `patterns`

Only create a dedicated `GW/memory` manual from implementation evidence after that subsystem actually exists.
