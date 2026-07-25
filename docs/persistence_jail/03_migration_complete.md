# Persistence Path-Jail — Completion Report

Status of the "everything goes through `Settings`/`JsonFactory`; both hard-jailed to `settings/`/
`json/`" work. **All live in-client config/state persistence is migrated.** What remains is a set of
intrinsic exceptions that either need a Native-side primitive or an explicit owner decision.

## 1. Foundation — the unbypassable jail (DONE; needs a Native build)

`Py4GW_Reforged_Native`:
- `scope="root"` removed from the entire binding API (`settings_bindings.cpp` + `json_factory_bindings.cpp`
  `ParseScope` reject it). `JsonScope::Root` deleted outright.
- `SettingsManager::Open` no longer binds Root (redirects+logs). The single root file `Py4GW.ini` is
  reachable ONLY via the hardcoded, path-less `SettingsManager::OpenPy4GWIni()` → `PySettings.py4gw_ini()`
  → `Settings.py4gw_ini()`. The 4 internal native callers were repointed to it.
- Defensive: account/global were already jailed (sanitize strips `..`/drive segments). With Root gone,
  no `(name, scope)` can escape `settings/`/`json/`.

Python wrappers (`Settings`/`JsonFactory`) reject any scope but `account`/`global`; stubs + docstrings
updated. **Owner must build Native** for the native half to take effect (Python half is already live).

## 2. Migrated (all Pyright-clean; START CLEAN — no legacy reads)

| Area | Files | Store |
|---|---|---|
| Bot hero configs | 7 title/vanquish bots | `JsonFactory("Widgets/Bots/<Bot>/Heroes.json")` account |
| GW widgets | Travel, Layout Manager, LootManager, InventoryPlus | JsonFactory (account; layouts/exports global) |
| Automation | CombatPrep, Dhuum Helper, Underworld | JsonFactory; `EquippedArmor.json` shared **global** |
| System | Enemy Tracker | global JsonFactory, per-path journal-merge (lock deleted) |
| System | Style Manager + `ImGui_src/Style.py` | per-theme `Styles/<name>.json` global |
| Core lib | `UIManager` frame aliases, `modular/hero_setup_model` | global / account JsonFactory |
| HeroAI | `hex_removal_config` | account JsonFactory (hand-rolled JSONC serializer deleted) |
| Parallel classes | LootEx `Settings`, MultiBoxing `Settings`, Pycons profile store | now delegate to / use the sanctioned classes; own file I/O removed |
| Cross-account | TeamInventoryViewer, Xunlaimanager | shared global doc / `copy_document_to_account` API |
| Recorders/misc | AlcoholProc, Simple*Recorder, ItemHandling configs, AgentEnemyDebugDump | JsonFactory |
| File-IPC | aC Blessing flag-files, Pycons/EnemyTracker lock files | removed (native locking / no live consumer) |

Bugs fixed in passing: `JsonFactory.delete("")` is a native no-op — theme deletion silently failed;
corrected to `set_json("", {})`. Pycons legacy `shutil.copy2` config-migration copies removed.

## 3. Intrinsic exceptions (cannot become `Settings`/`JsonFactory` docs)

These are NOT oversights — each needs a Native change or an owner decision:

1. **Bundled read-only catalogs** — `skill_descriptions.json`, theme `*.default.json`, `items.json`
   (3.9 MB), `runes.json`, `modelid_drop_data.json`, `merchant_rules_catalog.json`, LootEx scraped
   data, BT recipes, `.md` help. `JsonFactory::Open` binds strictly under `json/`; there is no
   primitive to read a shipped file at its source-tree location, and START CLEAN forbids seeding from
   it (= data loss). **Fix: add a Native read-only "bundled file" primitive, or ship each as a
   `json/Defaults/` seed template (done for LootManager's two tables).**
2. **User-directed export/import to a user-CHOSEN path** — Enemy Tracker bundle, Outpostrunner route
   export. Can't be a jail doc by definition; left working.
3. **`DBMgr` sqlite** — the sanctioned exception; reworked later (absorb the Pathing cache here).
4. **`Pathing.py` pickle navmesh cache** — binary compute-cache with tuple keys; group with the DB rework.
5. **Source-code editors** — HeroAi Skill Editor, Bot_Factory, Script Runner read/write `.py` source.
6. **Module/route discovery** — `os.listdir` of script dirs (Vanquish/Runner/Zaishen route pickers,
   InventoryPlus "Copy to All Accounts"). Not config; should use ShMem for account rosters.
7. **External tooling** — the launcher, bridge/MCP stack (`bridge_*.py`, `py4gw_mcp_server.py`,
   `BridgeRuntime/`) are separate non-injected processes; they cannot import the embedded modules.
8. **Dev/debug dumps & offline tools** — `Widgets/Coding/Debug/*`, root `frame_viewer`/`context_diagnostic`,
   `modular_data/tools`, texture scrapers. Dev-only.

## 4. Needs an owner decision (destructive — not done unilaterally)

- **Delete the deprecated `Legacy code and tests/` archive?** It still contains `configparser`/raw
  handlers; migrating dead code is pointless — recommend deletion.
- **Delete the dead `shared_state_ctypes.py` + `Dialog Sync(non working).py`?** A parallel
  shared-memory + file-lock IPC whose only consumer is non-working; cross-account state should be ShMem.
- **Feature removals from START CLEAN** (flagged): bots' "Import Team From another bot", hex_removal's
  paste-import, Xunlai copy inverted pull→push, Enemy Tracker in-memory cross-account merge → journal-merge.
