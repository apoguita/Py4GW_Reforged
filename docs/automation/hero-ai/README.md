# HeroAI Documentation Map

This folder contains subsystem records for HeroAI combat, interrupt decisions,
and UI composition. They are grouped by ownership, while their individual
categories remain distinct in the documentation index.

## Authority and status

- `heroai-combat-handover.md` is a performance and decision-pipeline handover;
  verify its optimization claims against current `Py4GWCoreLib/HeroAI/` and routine sources.
- `hero-ai-interrupt-feasibility.md` documents the two evaluator gates, logging,
  and known heuristic limitations. It explicitly records parked inaccuracies;
  do not treat a SUCCESS log as proof of a real interrupt without the stated
  event/duration evidence.
- `hero-ai-ui-inventory.md` inventories overlapping HeroAI UI surfaces for
  redesign. It is an inventory and comparison record, not the implementation
  authority for ImGui, LaunchBar, or native UI behavior.
- `follower-resolves-unstuck.md` documents the per-follower smart-unstuck
  state machine, detour generation, runtime integration, and diagnostics.
- Current `Py4GWCoreLib/HeroAI/`, `Py4GWCoreLib/`, `Sources/`, and injected-client evidence
  outrank these handovers and inventories.

## Review order

1. Read the record matching the affected subsystem.
2. Inspect the owning HeroAI or Py4GWCoreLib implementation.
3. For UI changes, consult the relevant `docs/ui/` authority map as well.
4. For combat/interrupt changes, verify frame cost, event availability, and
   runtime logs before claiming behavior.
