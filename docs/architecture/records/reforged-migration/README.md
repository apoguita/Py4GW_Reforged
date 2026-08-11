# Reforged Migration Records

This folder contains migration-session records and parity/severance analysis.

- `session-01-intake.md` and `session-01-complete.md` record one migration
  session and its conclusions.
- `frenkeylib-severance-audit.md` records dependency and compatibility findings.
- `frenkeylib-layered-migration-plan.md` is the proposed staged plan that makes
  `Item.Mods` the sole item-mod owner while FrenkeyLib and Mark become consumers.
- `frenkeylib-stage-0-cutover-ledger.md` records the current source reachability,
  item-mod call cutovers, and explicit inventory-control exclusions for that plan.

Use this folder with the owning current Python and native sources. Session logs
are historical evidence and cannot establish current runtime behavior alone.
