# Common User Manual

## Purpose

`GW/common` is the shared data layer used by multiple Guild Wars managers and modules.

It does not own initialization or shutdown. Instead, it provides:

- low-level container wrappers for game memory
- vector and position types
- packet opcode and StoC structure definitions
- constants and ID catalogs used across the codebase

Use this layer when you need the game-facing data shapes that managers operate on.

## Main Headers

Public headers in this layer:

- `include/GW/common/gw_array.h`
- `include/GW/common/gw_list.h`
- `include/GW/common/game_pos.h`
- `include/GW/common/opcodes.h`
- `include/GW/common/stoc.h`
- `include/GW/common/constants/constants.h`
- `include/GW/common/constants/agent_ids.h`
- `include/GW/common/constants/item_ids.h`
- `include/GW/common/constants/maps.h`
- `include/GW/common/constants/quest_ids.h`
- `include/GW/common/constants/skills.h`

## Containers

### `GWArray<T>`

`GWArray<T>` models a game-owned contiguous buffer.

Important behavior:

- `valid()` only means the buffer pointer is non-null
- `size()` and `capacity()` come from game memory
- `at()` and `operator[]` assert on invalid access
- `clear()` only mutates the wrapper size field, so do not treat it like an owning STL container

Typical usage:

```cpp
auto* agents = GW::agent::GetAgentArray();
if (!agents || !agents->valid()) {
    return nullptr;
}
if (agent_id >= agents->size()) {
    return nullptr;
}
return agents->at(agent_id);
```

### `GwList<T>`

`GwList<T>` and `GwLink<T>` model linked structures found in game memory.

Use them when the underlying game structure is actually list-backed. Do not convert them into copied vectors unless you have a real reason.

## Math And Position Types

`game_pos.h` provides:

- `Vec2f`
- `Vec3f`
- `GamePos`
- `Mat4x3f`
- helper math such as distance, norm, normalize, and rotate

Use these types for game coordinates instead of introducing duplicate vector structs.

Important detail:

- `GamePos` is a 2D coordinate plus `zplane`
- `Vec2f` and `Vec3f` provide arithmetic operators for simple spatial math

## Packet And Opcode Definitions

`opcodes.h` and `stoc.h` define shared protocol data used by the networking and StoC systems.

Use them when:

- decoding or handling StoC packets
- mapping packet headers to typed structures
- sharing packet layouts between managers and hooks

Do not put packet handling logic into this layer. This layer is schema, not behavior.

## Constants And IDs

`constants/constants.h` and the related ID headers provide:

- professions
- attributes
- bags and storage panes
- allegiances
- server regions and languages
- dialog IDs
- range constants
- title IDs
- map, skill, quest, item, and agent ID catalogs

Prefer these enums and constants over handwritten literals.

Example:

```cpp
if (agent->allegiance == GW::Constants::Allegiance::Enemy) {
    // hostile target path
}
```

## Practical Guidance

Use `GW/common` when:

- you need a shared type already defined by the project
- you are interpreting game memory layouts
- multiple modules need the same enum or ID list

Avoid changing this layer casually because many managers depend on it indirectly.

## Safe Modification Rules

When editing shared headers here:

1. Preserve binary layout of structs used for game memory or packets.
2. Preserve enum numeric values.
3. Do not replace game containers with owning STL containers.
4. Keep helper behavior lightweight and unsurprising.
5. Assume changes may affect many managers at once.
