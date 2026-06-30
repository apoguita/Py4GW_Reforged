# Constants LLM Manual

## Goal

This manual is for agents changing or extending `GW/common/constants`.

These headers are shared truth tables for the rest of the project. A wrong value here propagates everywhere.

## Scope

Primary files:

- `include/GW/common/constants/constants.h`
- `include/GW/common/constants/agent_ids.h`
- `include/GW/common/constants/item_ids.h`
- `include/GW/common/constants/maps.h`
- `include/GW/common/constants/quest_ids.h`
- `include/GW/common/constants/skills.h`

## Required Mental Model

This layer is data, not behavior.

Its job is to provide:

- stable numeric enums
- named fixed IDs
- lightweight helper mappings such as profession acronyms

If you are tempted to add logic-heavy code here, it probably belongs elsewhere.

## High-Risk Changes

Do not casually:

- renumber enum values
- reorder values when ordinal meaning matters
- change underlying enum widths
- replace strongly named IDs with raw integers in callers

`Profession`, `Attribute`, `Bag`, `Allegiance`, `Language`, `District`, and related values are consumed widely. Numeric drift is a real behavioral regression.

## Preferred Change Shapes

Good changes:

- add missing verified IDs
- add missing enum values with explicit numbers when needed
- add narrow helpers that map existing constants to display data
- update call sites to use existing constants instead of magic numbers

Bad changes:

- converting constants into a dynamic registry
- adding manager logic
- inferring values instead of using verified IDs

## Helper Discipline

`constants.h` already contains lightweight helpers such as profession acronym functions and range namespaces.

If adding helpers:

- keep them pure
- keep them header-friendly
- keep them obviously derived from existing constants

Do not add helpers that pull in heavyweight dependencies or runtime state.

## Range Usage

The `Range` and `SqrRange` namespaces exist for a reason.

Prefer:

- `Range::*` when comparing real distances
- `SqrRange::*` when comparing squared distances

Do not mix the two silently.

## ID Catalog Discipline

Files like `maps.h`, `skills.h`, and `quest_ids.h` are catalog headers.

When updating them:

1. preserve naming consistency
2. preserve verified numeric values
3. avoid speculative additions

If the source of truth is uncertain, stop and verify before editing.

## What To Preserve

Always preserve:

- numeric stability
- low-friction inclusion across the project
- separation between constant data and manager behavior

This layer should remain explicit, static, and predictable.
