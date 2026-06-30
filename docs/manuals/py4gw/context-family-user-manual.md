# Context Family User Manual

This manual covers the context-data header family under `include/GW/context`.

These headers define the raw Guild Wars data structures that higher-level managers consume. They are not manager APIs; they are the typed layout surface behind `GW::Context`.

Important headers in the family include:

- `account.h`
- `agent.h`
- `attribute.h`
- `camera.h`
- `character.h`
- `cinematic.h`
- `friend_list.h`
- `gadget.h`
- `game.h`
- `gameplay.h`
- `guild.h`
- `hero.h`
- `item.h`
- `map.h`
- `match.h`
- `npc.h`
- `party.h`
- `pathing.h`
- `player.h`
- `pregame.h`
- `quest.h`
- `skill.h`
- `text_parser.h`
- `title.h`
- `trade.h`
- `world.h`

How to use them:

1. Get the root pointer through `GW::Context`.
2. Work with the typed structures exposed by the relevant header.
3. Prefer manager APIs when the operation is behavioral rather than structural.

Examples:

- use `Context::AgentContext` or types from `agent.h` for raw agent-state traversal
- use `Context::ItemContext` for raw inventory structures
- use `Context::WorldContext` for broad world-state inspection

Use this family when you need direct structural access to runtime state.
