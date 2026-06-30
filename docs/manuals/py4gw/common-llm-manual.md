# Common LLM Manual

## Goal

This manual is for agents modifying the shared `GW/common` layer.

This layer is a contract surface. Most changes here are high blast radius because many managers, hooks, and packet handlers depend on the same definitions.

## Scope

Primary headers:

- `include/GW/common/gw_array.h`
- `include/GW/common/gw_list.h`
- `include/GW/common/game_pos.h`
- `include/GW/common/opcodes.h`
- `include/GW/common/stoc.h`
- `include/GW/common/constants/*.h`

Treat these as shared schema and utility headers, not manager modules.

## Required Mental Model

`GW/common` contains:

- memory layout wrappers
- packet layout definitions
- shared enums and IDs
- simple math helpers

Its job is to make other modules type-correct and layout-correct.

It should not accumulate initialization logic, scanner logic, or manager lifecycle logic.

## High-Risk Areas

### Memory Layout Wrappers

`GWArray<T>` and `GwList<T>` mirror game-owned structures.

Do not:

- add ownership semantics
- insert extra fields
- change field order
- change assertion behavior casually

Any layout drift here can silently corrupt many consumers.

### Packet Structures

`stoc.h` is effectively a protocol schema file.

Do not:

- reorder fields
- widen or narrow integer types
- change packing assumptions implicitly
- reinterpret packet types without validating against real call sites

### Constants

Enums and ID catalogs are externally meaningful values, not cosmetic names.

Do not:

- renumber enums
- replace strong enums with raw integers
- merge unrelated ID domains

## Preferred Change Shapes

Safe changes usually look like:

- adding documentation comments
- adding missing enum values with verified numeric constants
- adding helper functions that do not alter layout
- reusing existing vector or ID types in manager code

Risky changes usually look like:

- rewriting containers
- changing packet bases
- changing `GamePos`, `Vec2f`, or `Vec3f` semantics in ways that alter existing arithmetic expectations

## How To Work With This Layer

When a manager needs a type change:

1. confirm the shared type really belongs in `GW/common`
2. inspect every public consumer you can find
3. preserve binary compatibility
4. keep behavior minimal

When a manager only needs new behavior, prefer implementing it in the manager instead of expanding this shared layer unnecessarily.

## Packet/Schema Discipline

For `opcodes.h` and `stoc.h`:

- treat names as lookup aids over fixed wire values
- keep definitions mechanical and explicit
- avoid mixing behavior with schema

If packet handling needs new logic, place it in StoC or manager code, not in the common schema headers.

## Container Discipline

For `GWArray<T>` and `GwList<T>`:

- preserve current field layout and iterator expectations
- assume data may become stale between reads because ownership is external
- prefer bounds checks at call sites before `at()`

If you need safer access patterns, wrap usage in manager code instead of mutating the core container contract unless the change is truly global and validated.

## Geometry Discipline

For `game_pos.h`:

- reuse existing vector math instead of duplicating vector structs elsewhere
- preserve conversion and operator behavior unless there is a strong compatibility reason
- avoid introducing heavy math dependencies into this header

## What To Preserve

Always preserve:

- struct size and field order where memory layout matters
- enum numeric stability
- low-level header-only usability
- separation between schema and behavior

This layer should remain boring, explicit, and stable.
