# Skills LLM Manual

## Goal

This manual documents the current repo state of `GW/skills`.

The directory exists, but there is no public subsystem surface there yet.

## Current Repo State

At the time of this manual:

- `include/GW/skills` contains no public headers
- `src/GW/skills` contains no implementation files

## Agent Guidance

Do not infer a skill manager from the directory name alone.

Use the actual documented surfaces instead:

- `skillbar` for active skill operations
- `context` for raw state
- `constants` for skill IDs

If this directory later gains real code, document that implementation directly rather than extending this placeholder note.
