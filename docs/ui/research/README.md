# UI Research

This topic owns native UI investigation that supports the UI subsystem. These
records are research evidence, not an independent `RE` taxonomy.

Authority order for claims here: the owning native source and a live injected
client first, then records marked `runtime-verified`, then decompiler-derived
records, then the handovers and recipes below.

## Native control records

| Record | Kind | Status |
|---|---|---|
| `native-dialog-host-owner-contract.md` | research — instanced-dialog owner contract, `CCtlLayout` size pass, close path, pattern-table escaping rules, record-based host landing | current (decompiler-verified, host landed and built; not yet in-client verified) |
| `native-button-pipeline.md` | research — creation reference and per-control recipes | current for the working button; its address tables and the "content page" model are superseded |
| `native-dialog-layout-process.md` | research — 8-phase build spec for control-hosting windows | current as a model; its `UiCtlContentPageProc` derivation is wrong (see the owner-contract record) |
| `native-ui-controls-handover.md` | records — honest per-control status and dead-ends | current for status; EXE addresses are stale |
| `ui-controls-master-catalog.md` | reference — discovered control FrameProcs | current |
| `ui-elements-creation-recipes.md`, `ui-frame-system-mapping.md` | research/reference — per-control recipes and GWCA↔WASM↔EXE mapping | as labelled inside each record |

The EXE address tables in the July records were verified against a `06-14-2026`
client. The installed client is newer and its code layout differs, so resolve
engine functions by byte pattern or assertion string, never by a recorded
address. WASM addresses and symbol names in those records still hold.

## Harnesses and scratch material

- `probes/` contains the live reproducible native UI harnesses.
- `probes/tools/` contains the two current in-client harnesses.
- Superseded findings, exploratory probe scripts, scratch tools, and captured
  logs are preserved under `../../archive/ui/research/`; see
  `../../archive/README.md` for the full retired-material index.

Use the owning native source and live injected-client reproduction to determine
current behavior.
