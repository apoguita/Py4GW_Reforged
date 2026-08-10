# Py4GW Project Context

This document is the supplemental project-knowledge layer for the compact
`AGENTS.md` and `CLAUDE.md` files. It contains concrete Py4GW facts, paths,
ownership rules, migration notes, and verification references that should not
be forced into the generic agent-behavior file.

This is context, not a replacement for the active instruction files. Use the
most specific current source available; treat historical plans, handovers, and
legacy trees as evidence with an explicit status rather than as automatic
runtime truth.

## Project-Specific Reference

For concrete project paths, commands, migration parity, persistence,
reverse-engineering, bridge, widget, ImGui, and runtime facts, read this
document when relevant. It supplements the behavioral rules in `AGENTS.md` and
the other current Py4GW AI guides; it does not replace them.

## Extraction coverage

This file is the active destination for concrete project facts removed from
the compact `AGENTS.md`/`CLAUDE.md` behavior rules. The archival companion
`project-specific-context-recovered.md` preserves the previous tracked
`AGENTS.md` verbatim and records unique facts recovered from the former local
`CLAUDE.md`; use it when provenance or wording from the original rules matters.
Do not add provider-specific prompt behavior here: this document is for
Py4GW facts, ownership, paths, interfaces, runtime evidence, and project
workflow constraints.

## Project-specific engineering constraints

- Prefer existing Py4GW code, owning abstractions, and approved libraries;
  adapt or extend them instead of duplicating or replacing working behavior.
- Fix root causes at the lowest responsible layer. If the Python layer cannot
  provide the correct fix, follow the owning native C++/DLL path rather than
  masking the defect with a workaround.
- Do not use monkey patches, external method replacement, method shadowing,
  hidden wrappers, or competing override paths as architecture. Preserve one
  authoritative owner and one explicit integration path.
- Do not perform destructive Git or filesystem actions without explicit user
  authorization for the exact target and scope; never commit unless requested.
- Keep project development history, implementation attempts, evidence,
  assumptions, failures, successes, and unresolved issues in persistent
  Markdown records. Records preserve knowledge across agent sessions but do
  not override current source or runtime evidence.
- Python scripts use the established frame lifecycle: `update()` is the
  non-UI callback and `draw()`/`main()` are UI callbacks when present; these
  are per-frame entry points, not one-time startup hooks. Scripts in scope use
  the standard PyImGui window skeleton, with explicit exemptions for headless,
  library, test, or native-only modules.
- Debug and test diagnostics must be attributable and readable at the console,
  including the relevant inputs, state, expected/observed result, function or
  lifecycle stage, and failure context. For injected-client failures, request
  the client crash log and correlate it with the injection log before drawing
  root-cause conclusions.

## Scope and source authority

- Primary Python project: `C:\\Users\\Apo\\Py4GW_Reforged`.
- Related native project: `C:\\Users\\Apo\\Py4GW_Reforged_Native`.
- Legacy Python parity tree: `C:\\Users\\Apo\\Py4GW_python_files` (read-only reference).
- Legacy GWCA-era project: `C:\\Users\\Apo\\Py4GW`; its `vendor/gwca` tree is a cross-reference only.
- Related reverse-engineering project: `C:\\Users\\Apo\\D3CA` when a task explicitly uses it.
- Current implementation and runtime evidence outrank plans, handovers, generated exports, names, memory, and legacy code.
- Distinguish `current`, `legacy`, `planned`, `abandoned`, `historical`, and
  `runtime-verified` claims when reading project material.

## Runtime and architecture facts

- `Py4GW.dll` is a Windows-only 32-bit injected DLL. It embeds CPython through
  pybind11, hooks D3D9, and renders a Dear ImGui overlay inside Guild Wars.
- Injected/runtime work targets Python 3.13.0 32-bit. Changing the interpreter
  version casually can crash the Guild Wars client.
- The Python-facing architecture has two data paths:
  - bindings: embedded `Py*` modules with type stubs under `stubs/`;
  - context: ctypes structures read from shared memory under
    `Py4GWCoreLib/native_src/context/`.
- The practical layer stack is Guild Wars process/native bindings,
  `Py4GWCoreLib/` as the Python source-of-truth layer,
  `Py4GWCoreLib/py4gwcorelib_src/` support infrastructure,
  `GLOBAL_CACHE`/shared-memory consumers, and combat-automation schedulers.
- When an owning API provides an action queue, active operations route through
  that queue instead of direct writes.
- `Py4GWCoreLib/__init__.py` is a broad convenience facade: it appends system
  `site-packages`, re-exports high-level modules, and redirects stdout/stderr
  to the Py4GW console. Treat importing it as potentially side-effectful.

## Native migration and API parity

- The authoritative native backend is `Py4GW_Reforged_Native`, not legacy
  GWCA. Native managers live under `src/GW/<module>/` and
  `include/GW/<module>/`; named symbol ownership and `Resolve*` functions are
  declared by each module.
- Runtime addresses come from
  `Py4GW_Reforged_Native/offsets/<module>.json` byte patterns, masks, and step
  resolvers, not hard-coded addresses. Native build and migration references
  live in that sibling repository's `docs/` directory, especially
  `docs/06-pattern-json-system.md`, `docs/module-migration-guide.md`, and
  `docs/gwca-manager-dependency-map.md`.
- The native build is CMake-owned by the sibling project; use its Win32 CMake
  presets or `cmake -S . -B build -A Win32` from that project. A build command
  from this Python repository does not build the authoritative DLL.
- The Python library is being repointed from legacy GWCA bindings to the
  Reforged Native surface. For new code, use the Reforged names where the
  owning source confirms them:

  | Legacy | Reforged/current |
  |---|---|
  | `Py2DRenderer` | `PyDXOverlay` |
  | `PyCombatEvents` | `PyAgentEvents` |
  | `PyPointers` | retired |
  | `Py4GW.Console.*` | `PySystem.Console.*` |
  | `Py4GW.Game.*` | `PySystem` / `PyGameThread` |
  | `Point2D` / `Point3D` | `Vec2f` / `Vec3f` |
  | `PyScanCodeKeystroke` | `PyKeyHandler` |

- Reforged `Py*` classes generally favor getter methods and module-level
  functions over legacy public data fields. Confirm each symbol in stubs and
  native bindings before using it.
- Compare a current Python file with its legacy twin before changing behavior
  that may be parity-sensitive; do not infer migration behavior from one file.
- Native changes cross the Python/C++ boundary and require ABI, conversion,
  ownership, callback, exception, calling-convention, and lifetime review.

## Persistence and storage facts

The persistence policy is a project hard rule:

- INI and flat configuration use `Settings` in
  `Py4GWCoreLib/py4gwcorelib_src/Settings.py`, backed by native `PySettings`.
- JSON and structured data use `JsonFactory` in
  `Py4GWCoreLib/py4gwcorelib_src/JsonFactory.py`, backed by native `PyJson`.
- `Settings` and `JsonFactory` are mandatory persistence jail boundaries, not
  convenience APIs. No other handler, wrapper, protocol, provider,
  repository, adapter, or bypass may replace, hide, or duplicate their
  persistence access, even when it delegates internally to the owning class.
- The owning class enforces storage roots, valid scopes, path handling,
  account/global isolation, native locking, autosave, and the Python/native
  persistence contract. These guarantees are the reason feature code must
  use the classes directly.
- Account-scoped INI documents remain under `settings/<email>/<name>` and
  global INI documents under `settings/Global/<name>`. Account-scoped JSON
  documents remain under `json/<email>/<name>` and global JSON documents under
  `json/Global/<name>`. JSON has no root scope; the only project-root
  exception is `Py4GW.ini` through `Settings.py4gw_ini()`.
- Both are self-persisting singletons keyed by `(name, scope)`. Valid scopes
  are `account` and `global`; there is no `root` scope.
- `Py4GW.ini` is accessed only through the path-less `Settings.py4gw_ini()` accessor.
- Do not replace these classes with raw `open`, `json.load`/`json.dump`,
  `configparser`, `pickle`, `codecs.open`, `Path.read_text`/`write_text`,
  hand-rolled locking/atomic writes, or file-based IPC between accounts.
- Cross-account communication uses `GLOBAL_CACHE.ShMem`; shared values belong
  in `global` scope rather than another account's files.
- If `Settings`, `JsonFactory`, or their native backends lack a required
  primitive, stop the feature work and report the capability gap to the owner.
  Do not add an extension, raw handler, or private persistence abstraction in
  the feature change. Only a separately approved persistence-infrastructure
  change may modify the owning implementation, and it must preserve the
  folder jail.
- The sanctioned non-class disk access is `Py4GWCoreLib/database_src/DBMgr.py`
  for SQLite, plus external processes that cannot load embedded modules (the
  launcher and bridge/MCP stack).
- `docs/persistence/` and `docs/persistence/audit/` contain the migration,
  audit, and rationale records for this boundary.

## Documentation authority map

- `docs/architecture/reference/py4-gw-conceptual-model.md` is the canonical architecture and
  terminology reference.
- `docs/bridge/mcp/mcp-bridge.md` is the MCP-facing planning summary; use
  `py4gw_bridge/README.md` for daemon, injected client, CLI, and operator
  usage.
- `docs/architecture/reference/py4-gw-model-features-detail.txt` is a derived quick-scan export, not a
  separate authority.
- `docs/ui/widget-manager/widget-manager-and-catalog.md` is the high-value reference before
  changing widget discovery, metadata defaults, `WidgetHandler`, or
  `WidgetCatalog`.
- `docs/architecture/records/reforged-migration/` records the ongoing legacy-GWCA to
  Reforged-Native migration.
- Read subsystem handovers before changes in their area, including
  `FOLLOW_REFACTOR_HANDOVER.md`, `DBMGR_HANDOVER.md`,
  `ui/widget-manager/widget-manager-and-catalog.md`, `automation/behavior-trees/bottingtree-and-bt-routines-guide.md`,
  `heroai-combat-handover.md`, and `settings_database_cache_model.md`.
- The documentation index at `docs/documentation-index.md` is a navigation aid;
  it does not override an owning implementation or an explicit status record.

## Reverse-engineering facts and workflow

- Use a WASM-first workflow: inspect `/Gw.wasm` for symbols, control flow,
  fields, and call chains, then map the confirmed result to `/Gw.exe` only to
  resolve the concrete injected address. Reconfirm x86 ABI details at the EXE
  boundary.
- When calling Ghidra MCP tools, always pass the explicit `program` path;
  multiple similarly named `Gw.exe` programs exist.
- Start with `docs/game-client/research/reverse-engineering-reference.md`, then use
  `docs/game-client/research/cpp-wasm-mapping.md` for translation procedure and
  `docs/game-client/research/rosetta-stone.txt` for GwA2/AutoIt mappings.
- Native reverse-engineering sources are under
  `Py4GW_Reforged_Native/src/GW/<module>/`,
  `Py4GW_Reforged_Native/include/GW/<module>/`, and
  `Py4GW_Reforged_Native/offsets/`.
- Legacy GWCA cross-reference sources are under
  `Py4GW/vendor/gwca/Source/` and `Py4GW/vendor/gwca/Include/`.
- Python native bindings are under `Py4GWCoreLib/native_src/`; scanner helpers
  are in `Py4GWCoreLib/Scanner.py` (`FindAssertion`, `FindInRange`,
  `ToFunctionStart`).
- Ghidra references are `/Gw.exe(Symbols)` (x86 LE 32-bit, base `0x00400000`)
  and `/Gw.wasm` (Wasm LE 32-bit, base `ram:80000000`).

### Stable function-reference examples

| GWCA name | WASM symbol | EXE address |
|---|---|---|
| `DoWorldActon_Func` | `CoreActionExecuteWorldAction` | `0x0050e5e0` |
| `CallTarget_Func` | `CharCliPlayerOrderAlertSimple` | `0x00917740` |
| `ChangeTarget_Func` | `IAgentView::SetSelections` | `0x007e0f60` |
| `MoveTo_Func` | `IUi::Game::Walk*` | `0x00534fa0` |
| `SendAgentDialog_Func` | thunk | `0x008105b0` |

### UI message facts

- Guild Wars UI dispatch uses a hash table
  `THashTable<IFrame::Msg::CHandler>` at `DAT_ram_005a0338`, not a switch.
- Message ranges are `0x00-0x55` for base frame lifecycle,
  `0x100000xx` for server-to-client notifications, and `0x300000xx` for
  client-to-server commands.
- The authoritative enum is the migrated `enum class UIMessage : uint32_t`
  in `Py4GW_Reforged_Native/include/GW/common/constants/ui.h`, aliased through
  `include/GW/ui/ui.h`; the GWCA enum is cross-reference only.
- Missing messages can be investigated through the registered native send path
  or Ghidra callers of `FrameMsgSendRegistered`.

### Additional RE references

- `docs/ui/research/native-gw-window-creation-investigation.md` covers window creation;
  and `docs/ui/research/native-ui-title-and-encoded-string-reference.md` covers title
  and encoded-string handling.
- `docs/ui/name-tag-colors/feature-guide.md` is the historical usage guide for
  `PyAgentTagColor` (Python API, ARGB format, and in-client validation).
  `docs/ui/name-tag-colors/reverse-engineering.md` records the native name-tag
  pipeline, `GetConsiderColor` resolver detour/ABI, allegiance-to-ARGB table,
  and item-rarity markup. The current Python surface is `AgentRecolor` /
  `PyAgentRecolor` under `Py4GWCoreLib/AgentRecolor.py`,
  `Py4GWCoreLib/py4gwcorelib_src/system_settings/agent_recolor/`, and
  `stubs/PyAgentRecolor.pyi`; the historical native implementation reference
  is `Py4GW/src/py_agent_tag_color.cpp`. Its in-client test harness is
  `tests/name_tag_color/name_tag_color_test.py`.

## ImGui and script runtime facts

- Py4GW scripts use the embedded `PyImGui` module for immediate-mode rendering;
  inspect existing scripts and stubs for the supported surface.
- The project helper wrapper is exported from `Py4GWCoreLib/ImGui.py`, which
  imports `ImGui` from `Py4GWCoreLib/ImGui_src/ImGuisrc.py`. Existing scripts
  commonly use `from Py4GWCoreLib import ImGui` or
  `from Py4GWCoreLib.ImGui import ImGui` alongside `import PyImGui`.
- `ImGui_Legacy` and the abandoned `ImGuiRuntime` facade are not active
  implementations. Historical facade plans live under `docs/ui/imgui/`.
- The normal script frame callbacks are `update()` for non-UI work and
  `draw()`/`main()` for UI work when present; each callback can run once per
  frame. Confirm the loader's callback contract before changing lifecycle code.
- Widget discovery is folder-based: a `Widgets/` folder is a discovery root
  only when it contains a `.widget` marker, and every Python file in that folder
  can load as a widget.
- Widget metadata defaults come from
  `Py4GWCoreLib/py4gwcorelib_src/WidgetManager.py`: `MODULE_CATEGORY` defaults
  to the first `widget_path` segment, `MODULE_TAGS` defaults to all path
  segments, and `OPTIONAL` defaults to `False` except for `System` and
  `Py4GW` categories.
- `Py4GWCoreLib/HeroAI/follow/__init__.py` intentionally exports nothing; import exact
  submodules such as `Py4GWCoreLib.HeroAI.follow.leader_publish`.
- `Py4GWCoreLib/GlobalCache/SharedMemory.py` is startup-sensitive and imports
  that exact submodule; do not broaden the package-root import.

## Entry points, bridge, and focused checks

- `Py4GW_widget_manager.py` bootstraps in-client widgets, creates the manager
  INI key, runs widget discovery, and hands off to
  `Widgets/WidgetCatalog/Py4GW_widget_catalog.py`.
- `Py4GW_Launcher.py` is the external launcher/injector UI.
- Bridge flow: `Widgets/Coding/Tools/Bridge Client.py` -> `py4gw_bridge/daemon.py`
  -> `py4gw_bridge/cli.py`.
- `py4gw_bridge/mcp_server.py` is the MCP adapter; it bridges to the daemon over stdio
  rather than directly to injected clients.
- The MCP adapter intentionally exposes a narrow safe surface rather than
  arbitrary bridge calls: `list_clients`, `list_namespaces`, `list_commands`,
  `describe_runtime`, `get_map_state`, `get_player_state`, and `list_agents`.
- Bridge defaults are the widget server `127.0.0.1:47811` and control server
  `127.0.0.1:47812`; the CLI defaults to control port `47812`.
- `Sources/modular_bot/` is authoritative for ModularBot; widget copies are
  mostly wrappers.
- Focused checks include:
  - `python -m py4gw_bridge.daemon --help`
  - `python -m py4gw_bridge.cli --help`
  - `python -m py4gw_bridge.mcp_server --help`
  - `python "Sources/modular_bot/tools/validate_modular_docs.py"`
  - `python "Widgets/Data/test_merchant_rules_regression.py"`
  - applicable standalone root `test_*.py` scripts
- There is no repository-wide CI, pytest/tox configuration, Makefile, or
  global test runner. Use targeted checks and report what was actually run.
- `requirements.txt` is empty. `pyproject.toml` configures Black with line
  length 120 and keeps existing string choices
  (`skip-string-normalization = true`); isort uses one-import-per-line style
  (`force_single_line = true`).
- `pyrightconfig.json` sets `stubPath = ./stubs` and suppresses missing-module
  source noise. Pyright/Pylance is required for changed Python when available;
  `py_compile` alone is insufficient.

## Runtime evidence and failure records

- For injected-client failures, request the crash log from the injected-client
  folder and correlate it with the injection log, timestamps, build/runtime
  context, and reproduction steps.
- Preserve observed logs separately from interpretations. A crash log is
  evidence, not proof of a root cause until correlated with the native,
  Python, and runtime boundaries involved.
- Do not commit local runtime/config churn such as `Py4GW.ini`,
  `Py4GW_Launcher.ini`, or `py4-gw-injection-log.txt` unless the task explicitly
  concerns those files. The README documents the repository's
  `git update-index --skip-worktree` convention for local runtime/config files.

## Historical provenance

- `project-specific-context-recovered.md` preserves the previous tracked
  `AGENTS.md` verbatim and reconstructed unique `CLAUDE.md` facts. Keep it as
  an archival source while this document is the concise, active context map.
- Historical design and migration documents remain useful evidence but do not
  prove that a proposed facade, API, or runtime feature exists today.
