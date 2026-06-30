# Skills User Manual

## Purpose

`GW/skills` is currently a named subsystem directory without public headers or source files in this repository state.

At the time of writing:

- `include/GW/skills` has no public headers
- `src/GW/skills` has no source files

## What To Use Instead

For current skill-related behavior, use:

- `skillbar` for the active public manager surface
- `context` and context-family headers for raw skill-related state
- `common/constants/skills.h` for skill IDs

## Guidance

Treat `GW/skills` as reserved until it exposes a real public contract.
