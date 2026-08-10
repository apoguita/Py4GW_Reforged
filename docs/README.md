# Py4GW Documentation Guide

This directory is the project knowledge base. It is organized by the reader's
topic, not by the author, migration batch, or investigation method.
Documentation is evidence and navigation; it does not replace the owning
source, native implementation, or live runtime observation.

Read `maintenance/documentation-style-guide.md` before adding, renaming, or
moving documentation. It defines the required topic, naming, status,
provenance, and maintenance rules.

## Start Here

| Task | Read first |
|---|---|
| Orient to the Python/native/runtime stack | `architecture/` |
| Investigate a game-client or native-runtime fact | `game-client/research/` |
| Change PyImGui, widgets, or overlay code | `ui/` |
| Change bots, behavior trees, HeroAI, or builds | `automation/` |
| Change Settings, JsonFactory, or database use | `persistence/` |
| Change bridge, shared memory, or MCP behavior | `bridge/` |
| Continue a Reforged migration | `architecture/records/reforged-migration/` and the owning source |
| Work on item modifiers or game-derived catalogs | `items/modifiers/` |
| Work on loot behavior or its redesign | `loot/redesign/` |
| Validate the demo replacement | `validation/demo/` |
| Work with Py4GW AI guidance or agent workflows | `py4gw-ai/` |

## Specialized Records

- `ui/map-overlay/` records the proposed map-overlay consolidation.
- `automation/behavior-trees/modular-json/` records the modular JSON behavior-tree
  architecture.
- `persistence/audit/` preserves the storage-boundary audit and migration history.
- `py4gw-ai/reference/` contains prompt-pattern references, not active
  repository rules.

## Authority And Status

Use this order when sources disagree:

1. Current owning implementation, stubs, and build configuration.
2. Runtime observation, injection logs, and reproducible tests.
3. Canonical architecture and subsystem maps in this directory.
4. Plans, handovers, audits, postmortems, and research records.
5. Legacy Py4GW/GWCA material, which is parity evidence only.

Every new or materially revised document should state whether it is current,
historical, proposed, generated, or runtime-verified. Do not infer current
behavior from an unlabelled plan or a file name.

## Navigation Rules

- Read a directory `README.md` before opening a large record in that directory.
- Keep subsystem knowledge in its owning topic folder; use the root only for
  navigation.
- Do not store datasets, export tables, or generated catalogs here. Put them
  with the tool or runtime owner; the document records their provenance and
  refresh procedure in prose.
- Preserve superseded findings as historical evidence; do not silently rewrite
  them into current claims.
- Update the relevant directory map and this index when a reviewed move changes
  a top-level documentation route.

`documentation-index.md` is a short human-maintained route map, not an
authority or machine-readable database. The folder maps and source documents
define meaning and status.
