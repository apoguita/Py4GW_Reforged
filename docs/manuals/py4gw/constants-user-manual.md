# Constants User Manual

## Purpose

`GW/common/constants` is the shared catalog of game enums, IDs, and fixed values used across Py4GW.

This layer gives you named values for:

- professions and attributes
- allegiances and item types
- bag and storage identifiers
- regions, languages, and districts
- dialog IDs and effect IDs
- map, skill, quest, item, and agent IDs

Use it to avoid scattering magic numbers through managers and bindings.

## Main Header

Most shared enums live in:

- `include/GW/common/constants/constants.h`

Additional ID catalogs live in:

- `agent_ids.h`
- `item_ids.h`
- `maps.h`
- `quest_ids.h`
- `skills.h`

## Common Examples

Profession checks:

```cpp
if (player->primary == GW::Constants::Profession::Mesmer) {
    // mesmer-specific handling
}
```

Allegiance checks:

```cpp
if (agent->allegiance == GW::Constants::Allegiance::Enemy) {
    // hostile target
}
```

Range checks:

```cpp
if (GW::GetSquareDistance(a, b) <= GW::Constants::SqrRange::Spellcast) {
    // within spell range
}
```

## Notable Groups

Useful groups inside `constants.h` include:

- `Campaign`
- `Difficulty`
- `InstanceType`
- `Profession`
- `Attribute`
- `Bag`
- `Allegiance`
- `ItemType`
- `HeroID`
- `TitleID`
- `ServerRegion`
- `Language`
- `District`
- `Range`
- `SqrRange`
- `DialogID`
- `EffectID`
- `Camera`

## Practical Guidance

Prefer named constants when:

- comparing game state
- building filters
- mapping user-facing values
- writing bindings or docs

Avoid raw literals like `0x3` for allegiance or `1248.0f` for spell range when a named constant already exists.

## Safe Usage Rules

1. Use the matching enum domain for the value you need.
2. Do not assume unrelated IDs share a numbering scheme.
3. Preserve enum casts where code expects byte-sized or integer-sized values.
4. Prefer `SqrRange` for squared-distance comparisons to avoid unnecessary square roots.
