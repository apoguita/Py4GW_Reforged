# AGENTS.md

- No repo-level CI/test runner is configured: no `.github/workflows`, no `pytest`/`tox` config, no `Makefile`, and `requirements.txt` is empty. Verify with targeted scripts instead of guessing a global command.
- `pyproject.toml` only configures formatting. Preserve Black at `line-length = 120`, keep single quotes if already present (`skip-string-normalization = true`), and keep `isort`'s one-import-per-line style (`force_single_line = true`).
- `pyrightconfig.json` only sets `stubPath = ./stubs` and suppresses missing module source noise. Use `pyright` only if it is installed in the environment.
- README explicitly targets Python 3.13.0 32-bit for injected/runtime work. Do not casually switch interpreter versions when debugging launcher or injection issues.
- `Py4GWCoreLib/__init__.py` is a broad convenience facade, not a minimal import surface: it manually appends system `site-packages`, re-exports most high-level modules, and redirects `sys.stdout`/`sys.stderr` into the Py4GW console. Avoid treating `import Py4GWCoreLib` as a neutral import when debugging startup/import side effects.

## Backend: legacy GWCA → Reforged Native (active migration)

- The `Py4GW.dll` this Python library loads is built by a **separate sibling C++ project, `Py4GW_Reforged_Native`** (`../Py4GW_Reforged_Native`) — a 32-bit injected DLL that embeds CPython (pybind11), hooks D3D9, and renders ImGui. It is a ground-up rework **replacing the legacy GWCA backend**, itself under parity migration (GWCA managers → `GW/<module>/`). Build there is CMake (`cmake -S . -B build -A Win32` / `vs2022-win32` presets) — no build command from this Python repo applies to it.
- This Python library reaches the game via **two data paths**: the **bindings path** (`Py*` embedded modules, type-stubbed in `stubs/*.pyi`) and the **context path** (ctypes structs from shared memory, read by `Py4GWCoreLib/native_src/context/*.py`).
- The library is being repointed from the legacy GWCA-era binding surface to the Reforged Native surface; session log in `docs/migration_to_reforged/`. Assume Reforged names in new code: `Py2DRenderer`→`PyDXOverlay`, `PyCombatEvents`→`PyAgentEvents`, `PyPointers` retired, `Py4GW.Console.*`→`PySystem.Console.*`, `Py4GW.Game.*`→`PySystem`/`PyGameThread`, `Point2D/3D`→`Vec2f/Vec3f`, `PyScanCodeKeystroke`→`PyKeyHandler`. Reforged `Py*` classes favor getter methods + module-level functions over legacy data fields.
- `Py4GWCoreLib.ImGui` is being rebuilt as a new Reforged-only facade (specs: `docs/ImGui_Facade_Migration_Plan.md`, `docs/ImGui_Implementation_Correction_Instructions.md`); strictly separate from `ImGui_Legacy`, single `ImGui = ImGuiRuntime()` singleton.

## Docs Hierarchy

- `docs/Py4GW_Conceptual_Model.md` is the canonical architecture/source-of-truth document for project layers and terminology.
- `docs/MCP_bridge.md` is the MCP-facing bridge planning summary; use it for bridge/MCP modeling, not as the primary architecture source.
- `BridgeRuntime/README.md` is the operator/runtime usage reference for daemon + injected bridge client + CLI.
- `docs/Py4GW_Model_Features_Detail.txt` is a derived plain-text export for quick scanning, not a separate authority.
- `docs/widget_manager_and_catalog.md` is the highest-value reference before changing widget discovery, widget metadata defaults, `WidgetHandler`, or `WidgetCatalog` behavior.

## RE (Reverse Engineering) — `docs/RE/`

- **WASM-first workflow (do this by default).** Reverse-engineer on `/Gw.wasm` first, then map the confirmed result to `/Gw.exe`. The WASM retains full debug symbols (`CCharAgent::GetConsiderColor`, `FrameCreate`, `CtlTextMl::Markup`, …), so behaviour, control flow, struct fields, and call chains are far faster and less error-prone to read there. The EXE is stripped (`FUN_xxxxxxxx`) — only enter it at the **end**, to resolve the concrete address the injector needs. Reading architecture in the EXE first is slow and mistake-prone. Watch for genuine ABI differences (WASM `call_indirect` table indices vs. x86 real pointers; possible `Color4b`/struct channel-order repacks) — the architecture transfers, but re-confirm low-level calling/ABI details on the EXE. When calling Ghidra MCP tools, always pass the explicit `program` path (the project has multiple same-named `Gw.exe` images; a name-omitted call silently hits the wrong one). See `docs/RE/CPP_WASM_MAPPING.md` for the translation procedure.
- **Authoritative C++ backend is now `Py4GW_Reforged_Native`, not GWCA.** The migrated managers live at `../Py4GW_Reforged_Native/src/GW/<module>/` + `include\GW\<module>\` (each module declares named ownership of every resolved symbol; `<module>_patterns.cpp` holds the `Resolve*` functions), and runtime addresses come from `Py4GW_Reforged_Native\offsets\<module>.json` (byte patterns/masks + step resolvers), **not** hardcoded. See that repo's `docs/06-pattern-json-system.md`, `docs/module-migration-guide.md`, and `docs/gwca-manager-dependency-map.md`. The legacy GWCA tree at `../Py4GW/vendor/gwca` still exists and is a useful cross-reference for how a subsystem worked pre-Reforged, but it is no longer the source of truth. The `Gw.exe`/`Gw.wasm` address tables below describe the actual game and remain valid regardless of wrapper.
- **Start with `docs/RE/reverse_engineering_reference.md`** — the comprehensive library reference. Covers the three-layer architecture (Python `native_src`, C++ GWCA, Ghidra), key function catalogs with EXE↔WASM↔CPP mappings, bridging techniques, UI message dispatch architecture, and workflows for adding new functions.
- `docs/RE/CPP_WASM_MAPPING.md` — the full CPP↔WASM↔EXE translation procedure with worked examples and pitfall notes.
- `docs/RE/rosetta_stone.txt` — GwA2 (AutoIt) to Py4GW function mapping reference.
- `docs/RE/gw_combat_ai_reverse_engineering.md` — combat AI RE analysis.
- `docs/RE/native_gw_ui_function_catalog.json` — catalog of native GW UI functions with addresses.
- `docs/RE/native_gw_window_creation_investigation.md` — window proc creation RE.
- `docs/RE/native_ui_title_and_encoded_string_reference.md` — UI title and encoding reference.
- `docs/agent_name_tag_color.md` — **feature/usage guide** for `PyAgentTagColor` (recolor agent name tags natively): Python API, ARGB color format, examples, gotchas. SHIPPED & validated in-client.
- `docs/RE/name_tag_color_reverse_engineering.md` — the RE behind it: agent/item name-tag color pipeline, the `GetConsiderColor` resolver detour recipe/ABI (hook the resolver `FUN_007f02e0`; the wrapper `FUN_007d9cf0` is only an anchor), allegiance→ARGB table, and item-rarity markup. Native module: `Py4GW/src/py_agent_tag_color.cpp`. In-client test harness: `tests/name_tag_color/name_tag_color_test.py`.

### RE Tool Locations

| Layer | Path | Key Files |
|-------|------|-----------|
| **C++ (Reforged Native, primary)** | `../Py4GW_Reforged_Native/src/GW/<module>/` + `include\GW\<module>\` | `<module>.cpp`/`.h`, `<module>_patterns.cpp` (`Resolve*` fns) |
| **C++ pattern/offset data** | `../Py4GW_Reforged_Native/offsets/` | `agent.json`, `ui.json`, `native_ui.json`, … (byte patterns + resolvers) |
| **C++ (legacy GWCA, cross-ref only)** | `../Py4GW/vendor/gwca` | `Source/AgentMgr.cpp`, `Include/GWCA/Managers/AgentMgr.h` |
| **Python native** | `Py4GWCoreLib\native_src\` | `methods/PlayerMethods.py`, `internals/native_function.py` |
| **Python Scanner** | `Py4GWCoreLib\Scanner.py` | FindAssertion, FindInRange, ToFunctionStart |
| **Ghidra EXE** | `/Gw.exe(Symbols)` via MCP | 18,017 functions, x86:LE:32, base `0x00400000` |
| **Ghidra WASM** | `/Gw.wasm` via MCP | 18,004 functions, Wasm:LE:32, base `ram:80000000` |

### Key Function Mappings (quick reference)

| GWCA Name | WASM Symbol | EXE Address |
|-----------|-------------|-------------|
| `DoWorldActon_Func` | `CoreActionExecuteWorldAction` | `0x0050e5e0` |
| `CallTarget_Func` | `CharCliPlayerOrderAlertSimple` | `0x00917740` |
| `ChangeTarget_Func` | `IAgentView::SetSelections` | `0x007e0f60` |
| `MoveTo_Func` | `IUi::Game::Walk*` | `0x00534fa0` |
| `SendAgentDialog_Func` | (thunk) | `0x008105b0` |

Full catalog with sub-function breakdowns in `docs/RE/reverse_engineering_reference.md`.

### UI Message System

The game uses a **hash table** (`THashTable<IFrame::Msg::CHandler>` at `DAT_ram_005a0338`) for message dispatch, not a switch statement. Messages fall into three ranges:
- `0x00–0x55` — base frame lifecycle
- `0x100000xx` — server→client notifications (~90 mapped, ~15 unknown, ~6 newly discovered via WASM)
- `0x300000xx` — client→server commands (~30 mapped, all send-to-server actions)

The authoritative UIMessage enum is now the migrated `enum class UIMessage : uint32_t` in `../Py4GW_Reforged_Native/include/GW/common/constants/ui.h` (aliased as `GW::ui::UIMessage` in `include\GW\ui\ui.h`). The legacy GWCA enum at `../Py4GW/vendor/gwca/Include/GWCA/Managers/UIMgr.h` remains a cross-reference. To discover missing messages, either hook the send path at runtime (Reforged Native registers UI-message callbacks; legacy GWCA hooked `SendUIMessage_Func`) or run a Ghidra script against WASM callers of `FrameMsgSendRegistered`. Full procedure including the script is in `docs/RE/reverse_engineering_reference.md` Section 4.

### RE Tool Locations

| Layer | Path | Key Files |
|-------|------|-----------|
| **C++ (Reforged Native, primary)** | `../Py4GW_Reforged_Native/src/GW/<module>/` + `include\GW\<module>\` | `<module>.cpp`/`.h`, `<module>_patterns.cpp` (`Resolve*` fns) |
| **C++ pattern/offset data** | `../Py4GW_Reforged_Native/offsets/` | `agent.json`, `ui.json`, `native_ui.json`, … (byte patterns + resolvers) |
| **C++ (legacy GWCA, cross-ref only)** | `../Py4GW/vendor/gwca` | `Source/AgentMgr.cpp`, `Include/GWCA/Managers/AgentMgr.h` |
| **Python native** | `Py4GWCoreLib\native_src\` | `methods/PlayerMethods.py`, `internals/native_function.py` |
| **Python Scanner** | `Py4GWCoreLib\Scanner.py` | FindAssertion, FindInRange, ToFunctionStart |
| **Ghidra EXE** | `/Gw.exe(Symbols)` via MCP | 18,017 functions, x86:LE:32, base `0x00400000` |
| **Ghidra WASM** | `/Gw.wasm` via MCP | 18,004 functions, Wasm:LE:32, base `ram:80000000` |

### Key Function Mappings (quick reference)

| GWCA Name | WASM Symbol | EXE Address |
|-----------|-------------|-------------|
| `DoWorldActon_Func` | `CoreActionExecuteWorldAction` | `0x0050e5e0` |
| `CallTarget_Func` | `CharCliPlayerOrderAlertSimple` | `0x00917740` |
| `ChangeTarget_Func` | `IAgentView::SetSelections` | `0x007e0f60` |
| `MoveTo_Func` | `IUi::Game::Walk*` | `0x00534fa0` |
| `SendAgentDialog_Func` | (thunk) | `0x008105b0` |

Full catalog with sub-function breakdowns in `docs/RE/reverse_engineering_reference.md`.

## Entry Points

- `Py4GW_widget_manager.py` is the in-client widget bootstrap: it creates the manager INI key, runs widget discovery, and hands off to `Widgets/WidgetCatalog/Py4GW_widget_catalog.py`.
- `Py4GW_Launcher.py` is the external launcher/injector UI.
- Bridge stack wiring is split across:
  - injected widget: `Widgets/Coding/Tools/Bridge Client.py`
  - daemon: `bridge_daemon.py`
  - operator CLI: `bridge_cli.py`
- MCP adapter entrypoint is `py4gw_mcp_server.py`; it talks to the daemon over stdio->daemon bridging rather than directly to injected clients.
- Bridge defaults are verified in code: widget server `127.0.0.1:47811`, control server `127.0.0.1:47812`, and the CLI targets control port `47812` by default.
- `Sources/modular_bot/` contains the real ModularBot implementation. Files under `Widgets/Automation/modularbot/` are mostly thin wrappers that expose those tools/prebuilts through Widget Manager.

## Focused Checks

- Bridge help / argument discovery:
  - `python "bridge_daemon.py" --help`
  - `python "bridge_cli.py" --help`
- MCP adapter help / surface discovery:
  - `python "py4gw_mcp_server.py" --help`
- ModularBot docs coverage check:
  - `python "Sources/modular_bot/tools/validate_modular_docs.py"`

## Repo-Specific Gotchas

- For architecture questions, prefer module-specific imports and docs over the broad `Py4GWCoreLib` facade. The conceptual model treats `Py4GWCoreLib` as the single Python-facing source-of-truth layer, `py4gwcorelib_src` as support infrastructure, and `GLOBAL_CACHE` as a derivative consumer/cache layer.
- The current MCP adapter intentionally exposes a narrow safe tool set over daemon control, not generic arbitrary bridge calls: `list_clients`, `list_namespaces`, `list_commands`, `describe_runtime`, `get_map_state`, `get_player_state`, and `list_agents`.
- Widget discovery is folder-based, not file-based: `WidgetHandler` walks `Widgets/`, and only folders containing a `.widget` marker are discovery roots; every `.py` file in that same folder is loaded as a widget.
- Widget metadata defaults are non-obvious and come from `Py4GWCoreLib/py4gwcorelib_src/WidgetManager.py`: `MODULE_CATEGORY` defaults to the first `widget_path` segment, `MODULE_TAGS` defaults to all path segments, and `OPTIONAL` defaults to `False` only for `System` and `Py4GW` categories.
- Before touching follow-system code, read `FOLLOW_REFACTOR_HANDOVER.md`.
- `Py4GWCoreLib/GlobalCache/SharedMemory.py` is startup-sensitive and currently imports `HeroAI.follow.leader_publish` directly. Do not replace that with broad package-root imports.
- `HeroAI/follow/__init__.py` intentionally exports nothing. Import exact submodules such as `HeroAI.follow.leader_publish`, not `HeroAI.follow`.
- Avoid committing local runtime/config churn unless the task is specifically about them: `Py4GW.ini`, `Py4GW_Launcher.ini`, and `Py4GW_injection_log.txt`. README documents `git update-index --skip-worktree` for those files.
