# Context User Manual

`GW::Context` is the aggregate access layer for Guild Wars runtime state.

Public API in `include/GW/context/context.h`:

- `Initialize()`
- `Shutdown()`
- `GetGameContext()`
- `GetPreGameContext()`
- `GetWorldContext()`
- `GetPartyContext()`
- `GetCharContext()`
- `GetGuildContext()`
- `GetItemContext()`
- `GetAgentContext()`
- `GetMapContext()`
- `GetAccountContext()`
- `GetTradeContext()`
- `GetGameplayContext()`
- `GetTextParser()`
- `GetControlledCharacterId()`

The aggregate surface fronts the context-family headers under `include/GW/context`, such as:

- `account.h`
- `agent.h`
- `game.h`
- `gameplay.h`
- `guild.h`
- `item.h`
- `map.h`
- `party.h`
- `player.h`
- `pregame.h`
- `quest.h`
- `trade.h`
- `world.h`

Use `GW::Context` when you need raw state structures rather than manager-style behavior.
