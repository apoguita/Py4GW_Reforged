# Py4GW Skill Catalog

Status: current catalog; OpenCode consolidation completed on 2026-08-06
Scope: repository-local `docs/py4gw-ai/skills/` workflows
Authority: `AGENTS.md`, current skill files, and `skill-authoring-guide.md`

## Active Foundation Skills

| Skill | Use for | Do not use for |
|---|---|---|
| `py4gw-docs-navigation` | Unfamiliar subsystem, broad review, migration orientation, or documentation move | Replacing a specialist workflow after the owner is known. |
| `py4gw-runtime-investigation` | Injected-client symptom, crash, state mismatch, or read/action divergence | A code change without first identifying a runtime fault boundary. |
| `py4gw-native-migration` | Legacy GWCA/Python parity and migration to Reforged Native | Treating legacy implementation as the current owner. |
| `py4gw-ui-imgui` | Widget, overlay, PyImGui, input, popup, window state, or native UI work | Web-style layout assumptions or unrelated bridge work. |
| `py4gw-bridge-mcp` | Bridge daemon/widget/CLI/shared-memory/MCP schema and runtime-control boundary work | Adding an unreviewed parallel command path. |
| `py4gw-change-verification` | Focused test, build, review, completion, or residual-risk reporting | Pretending a global CI command exists. |
| `py4gw-task-guidance` | Broad, ambiguous, or under-specified work that needs a bounded task shape | Requiring an intake ceremony for a clear small change. |
| `py4gw-re-methodology` | Static RE of Guild Wars behavior, offsets, hooks, packets, or UI messages | Treating a legacy address or static result as live-client proof. |

The primary ApoBot agent owns user communication, planning, edits, and final
synthesis. A skill supplies a workflow; it is not a second agent and does not
transfer accountability.

The workflow documents live beside the rest of the Py4GW AI guidance at
`skills/<name>/SKILL.md`. Read the matching workflow when its task goal
applies; the documents are not runtime assets or application dependencies.

## Trigger Fixtures

Use these as lightweight positive/negative routing checks whenever a skill is
changed. They test selection and workflow boundaries; they do not claim to be a
full model evaluation harness.

| Expected skill | Positive prompt | Nearby negative prompt |
|---|---|---|
| `py4gw-docs-navigation` | "Which current sources own this unfamiliar persistence migration? Do not edit." | "The game target getter returns zero while a target is visibly selected." |
| `py4gw-runtime-investigation` | "Investigate why `Player.GetTargetID()` returns zero in the live client. Do not change code." | "Port the old target getter binding to Reforged Native." |
| `py4gw-native-migration` | "Map legacy `SendDialog` behavior to its current Reforged Native owner and bridge contract." | "The dialog is open but active button enumeration is zero at runtime." |
| `py4gw-ui-imgui` | "Review this widget popup's focus and persistent-window-state behavior." | "Add a daemon command to list bridge namespaces." |
| `py4gw-bridge-mcp` | "Review a new MCP command for the bridge daemon; define its schema and runtime-action risk." | "Check whether this changed Python module passes its focused tests." |
| `py4gw-change-verification` | "Choose and run focused checks for this bridge change; report what remains unverified." | "Design the UI's popup lifecycle and input ownership." |
| `py4gw-task-guidance` | "I want an inventory migration, but I do not know which files or behavior should change." | "Fix this named typo in the current README." |
| `py4gw-re-methodology` | "Trace the Guild Wars UI-message path before adding a native hook." | "Run the focused checks for this completed Python change." |

## OpenCode Consolidation Record

The ignored `.opencode/` workspace was removed after this catalog and its
current owners absorbed its useful, verified material. It is not a source of
active instructions or task state.

| Former OpenCode material | Current owner or disposition | Reason |
|---|---|---|
| WASM-first analysis, explicit Ghidra program selection, EXE confirmation | `py4gw-re-methodology` plus `docs/game-client/research/` | Reconciled with current Reforged Native ownership and live-proof limits. |
| Bridge entry points, default ports, narrow MCP surface | `py4gw-bridge-mcp` plus `docs/bridge/` | Refreshed against current source; no arbitrary runtime-command capability was retained. |
| Compact intake, research, plan, and verification patterns | `py4gw-task-guidance`, `py4gw-change-verification`, and the root contract | Retained as proportionate guidance, not mandatory task files or approval gates. |
| Role prompts, model routing, duplicate core/docs skills, command wrappers, packages, and old task transcripts | Retired | Platform-specific, duplicated by current owners, stale, or unsuitable as active context. |

## How to Invoke a Skill

Mention the workflow explicitly when the task is safety-sensitive or when a
nearby workflow could plausibly match:

```text
Use $py4gw-runtime-investigation to investigate this target/dialog state
regression. Do not modify code or send live-client actions.
```

```text
Use $py4gw-native-migration to map this legacy Python API to Reforged Native.
Return the owning module, bridge contract, and required checks before editing.
```

Normal task language should still trigger the correct skill when its goal is
unambiguous. Explicit invocation is a useful seatbelt, not an admission that
the car has no brakes.
