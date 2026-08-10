---
name: py4gw-docs-navigation
description: Use when Py4GW work spans an unfamiliar subsystem, documentation move, review, or migration and the agent must locate the current owner, evidence, and relevant records before acting.
---

# Py4GW Documentation Navigation

Establish evidence and ownership before changing Py4GW. Route work to the
smallest relevant documentation set; do not make documentation more
authoritative than source code or live runtime behavior.

## Scope

- Owns orientation, source selection, documentation-path changes, and evidence
  routing.
- Does not replace the runtime, native-migration, UI, bridge, or verification
  skill once the target layer is known.

## Workflow

1. Identify the target layer: Python/CoreLib, native DLL, Guild Wars runtime or
   RE, ImGui/UI, automation, persistence, integration, or agent workflow.
2. Read `docs/README.md` and `docs/maintenance/documentation-style-guide.md`,
   then the matching topic map:
   - `architecture/` for stack-wide orientation and project records.
   - `game-client/research/` for client-wide native/runtime investigation.
   - `ui/` for PyImGui, widgets, overlay, frame tree, launch surfaces, and
     UI-specific native research.
   - `automation/` for behavior trees, HeroAI, builds, or gameplay automation.
   - `persistence/` for Settings, JsonFactory, and database work.
   - `bridge/` for bridge, shared-memory, or MCP boundaries.
   - `architecture/records/reforged-migration/` for parity or migration history.
   - `items/modifiers/` or `loot/redesign/` for item and loot work.
   - `py4gw-ai/` for repository skills, instruction-system guidance, or agent workflows.
3. Read only the cited subsystem record needed for the task. Use
   `documentation-index.md` as a route map, not to establish behavior.
4. Confirm the owner in current source, stubs, build configuration, and, when
   relevant, `Py4GW_Reforged_Native`. Treat legacy Py4GW/GWCA as parity evidence.
5. For runtime-dependent claims, distinguish source proof from live injected
   client proof and request or inspect reproducible runtime evidence as needed.

## Authority Rules

Apply this order when records disagree:

1. Current owning implementation, stubs, and build configuration.
2. Reproducible runtime observation, injection logs, and tests.
3. Canonical architecture and subsystem maps.
4. Plans, handovers, audits, postmortems, and research.
5. Legacy compatibility references.

Label conclusions as verified, inferred, proposed, or unresolved. Do not turn a
plan, a historical handover, or a generated catalog into a current contract.

## Task-Specific Guards

- For native, hooking, or offset work, start in `docs/game-client/research/` and inspect the
  sibling native repository before proposing a Python workaround.
- For persistence, read `docs/persistence/README.md` before touching a storage
  path or API; Settings and JsonFactory are ownership boundaries.
- For behavior-tree or multibox failures, separate broken read-side state from
  working action paths before changing caller logic.
- For documentation changes, update the nearest `README.md` map and preserve
  source provenance and status labels.

## Completion Report

Report the owning layer, current source and documentation records consulted,
evidence status, relevant legacy reference if any, and the next required
specialist workflow or safe action.
