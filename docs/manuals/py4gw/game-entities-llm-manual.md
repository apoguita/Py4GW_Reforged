# Game Entities LLM Manual

## Goal

This manual documents the current state of `GW/game_entities`.

Right now it is only a named directory boundary. It does not expose a public contract.

## Current Repo State

At the time of this manual:

- there are no public headers under `include/GW/game_entities`
- there are no implementation files under `src/GW/game_entities`

## Agent Guidance

Do not invent a subsystem contract here just because the directory exists.

If a task needs entity behavior today, route through the documented existing surfaces:

- `agent`
- `context`
- `common`

If this directory later gains real code:

1. inspect the new headers and sources
2. determine whether it is a manager, data layer, or support layer
3. write proper manuals from the actual implementation, not the directory name
