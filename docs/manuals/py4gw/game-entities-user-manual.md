# Game Entities User Manual

## Purpose

`GW/game_entities` is currently a named subsystem directory without a public API surface in this repository state.

At the time of writing:

- `include/GW/game_entities` has no public headers
- `src/GW/game_entities` has no source files

## What This Means

This subsystem is currently a placeholder or reserved area, not a usable manager or data-layer contract.

Do not assume there is an entity abstraction layer here yet. Use the existing documented surfaces instead:

- `agent` for live agent access and actions
- `context` and the context-family headers for raw game-state structures
- `item`, `player`, `party`, and other managers for subsystem-specific behavior

## Guidance

If this subsystem becomes real later:

1. define the public headers first
2. keep the scope distinct from `agent` and `context`
3. add a real subsystem manual once the API exists
