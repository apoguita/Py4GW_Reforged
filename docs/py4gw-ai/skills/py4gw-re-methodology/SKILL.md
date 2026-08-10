---
name: py4gw-re-methodology
description: Use when a Py4GW task requires reverse engineering Guild Wars client behavior, a native function, memory layout, offset, hook, packet path, or UI message path before a native or Python change is proposed.
---

# Py4GW Reverse Engineering Methodology

## Scope

- Own evidence-led static analysis and the mapping from game-client behavior to
  the current Reforged Native owner.
- Do not treat a legacy GWCA symbol, an address from another client build, or a
  static finding as proof that the injected client is safe to modify.
- Do not send runtime actions, install hooks, add offsets, or edit native code
  without explicit user scope and the applicable runtime or migration workflow.

## Evidence Order

1. The exact client build and current Reforged Native owner, headers, offsets,
   and build configuration.
2. `docs/game-client/research/reverse-engineering-reference.md` and the
   relevant current subsystem research record.
3. Ghidra evidence from an explicitly selected program.
4. Runtime observations and logs, when static analysis cannot prove behavior.
5. Legacy GWCA/Python code as terminology and parity evidence only.

## Workflow

1. Define the behavior, client build, affected subsystem, required confidence,
   and whether the task is static analysis, a proposed change, or a live test.
2. Start in `docs/game-client/research/`; then identify the current native
   owner before pursuing a legacy implementation.
3. Select the Ghidra `program` explicitly for every operation. Do not rely on
   an active program when multiple images have similar names.
4. Analyze the named `Gw.wasm` path first. Establish control flow, structures,
   constants, and callers before entering stripped `Gw.exe` code.
5. Map to `Gw.exe` only after the behavior is understood. Use a stable unique
   anchor (for example an assertion, error string, or distinctive constant),
   then reconfirm ABI, calling convention, return ownership, and data layout.
6. Record each conclusion as verified, inferred, proposed, or unresolved;
   distinguish the game-client finding from the wrapper owner and from
   live-client proof.

## Completion Report

Report the client build/program, evidence chain, current owner, relevant
symbols or offsets, confidence, compatibility risk, and the smallest safe next
analysis or verification step.
