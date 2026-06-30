# Py4GW Manuals

This folder contains subsystem manuals for Py4GW internals that need both:

- user-oriented guidance for developers working in the repository
- LLM-oriented guidance for agents that need to modify or extend the subsystem safely

Current manuals:

- `agent-user-manual.md`
- `agent-llm-manual.md`
- `camera-user-manual.md`
- `camera-llm-manual.md`
- `chat-user-manual.md`
- `chat-llm-manual.md`
- `common-user-manual.md`
- `common-llm-manual.md`
- `constants-user-manual.md`
- `constants-llm-manual.md`
- `context-user-manual.md`
- `context-llm-manual.md`
- `context-family-user-manual.md`
- `context-family-llm-manual.md`
- `crashhandler-user-manual.md`
- `crashhandler-llm-manual.md`
- `effects-user-manual.md`
- `effects-llm-manual.md`
- `error-handling-user-manual.md`
- `error-handling-llm-manual.md`
- `events-user-manual.md`
- `events-llm-manual.md`
- `file-scanner-user-manual.md`
- `file-scanner-llm-manual.md`
- `friend-list-user-manual.md`
- `friend-list-llm-manual.md`
- `game-thread-user-manual.md`
- `game-thread-llm-manual.md`
- `game-entities-user-manual.md`
- `game-entities-llm-manual.md`
- `guild-user-manual.md`
- `guild-llm-manual.md`
- `guildwars-user-manual.md`
- `guildwars-llm-manual.md`
- `hook-types-user-manual.md`
- `hook-types-llm-manual.md`
- `hooker-user-manual.md`
- `hooker-llm-manual.md`
- `item-user-manual.md`
- `item-llm-manual.md`
- `logger-user-manual.md`
- `logger-llm-manual.md`
- `map-user-manual.md`
- `map-llm-manual.md`
- `memory-user-manual.md`
- `memory-llm-manual.md`
- `memory-manager-user-manual.md`
- `memory-manager-llm-manual.md`
- `memory-patcher-user-manual.md`
- `memory-patcher-llm-manual.md`
- `merchant-user-manual.md`
- `merchant-llm-manual.md`
- `panic-user-manual.md`
- `panic-llm-manual.md`
- `party-user-manual.md`
- `party-llm-manual.md`
- `patterns-user-manual.md`
- `patterns-llm-manual.md`
- `player-user-manual.md`
- `player-llm-manual.md`
- `process-manager-user-manual.md`
- `process-manager-llm-manual.md`
- `python-runtime-user-manual.md`
- `python-runtime-llm-manual.md`
- `quest-user-manual.md`
- `quest-llm-manual.md`
- `render-user-manual.md`
- `render-llm-manual.md`
- `scanner-user-manual.md`
- `scanner-llm-manual.md`
- `skillbar-user-manual.md`
- `skillbar-llm-manual.md`
- `skills-user-manual.md`
- `skills-llm-manual.md`
- `stoc-user-manual.md`
- `stoc-llm-manual.md`
- `timer-user-manual.md`
- `timer-llm-manual.md`
- `trade-user-manual.md`
- `trade-llm-manual.md`
- `ui-user-manual.md`
- `ui-llm-manual.md`

Scope:

- `Patterns` covers the JSON-backed pointer resolution system in `include/base/patterns.h` and `src/base/patterns.cpp`.
- `CrashHandler` covers crash capture, sidecar generation, optional dump generation, and crash context tracking in `include/base/CrashHandler.h` and `src/base/CrashHandler.cpp`.
- `game_entities`, `memory`, and `skills` document currently empty GW subsystem directories so the manual set still reflects the named repo surface accurately.
