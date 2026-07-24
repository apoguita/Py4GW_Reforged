# Persistence Path-Jail — Repo-Wide Audit & Plan

**Goal:** `Settings` (INI) and `JsonFactory` (JSON) become the *only* way anything in the repo
touches disk, and both are hard-confined — in the **Python wrappers and the Native C++ managers** —
to writing **only under `settings/` and `json/`**. Every ad-hoc handler (`open`/`json`/
`configparser`/`pickle`/…) is migrated. Mandate from the owner: *migrate everything — new, old, or
deprecated; nothing bypasses the classes.*

Extends the standing rule: *JSON only via JsonFactory, INI only via Settings; never raw
json/open/configparser.*

---

## 1. Root cause of the current leak

Native commit **`fcdf903` "bugfixes"** (`Py4GW_Reforged_Native`) did two things:

1. Changed `SanitizeRelativePath` from bare `std::filesystem::path(name).filename()` (collapse to a
   single filename) to a **folder-preserving** relative subpath — `"Widgets/Data/foo.ini"` now stays
   nested.
2. Added **`SettingsScope::Root`**, which binds to `GetModuleDirectory() / sanitized` — the **bare
   game folder**, not under `settings/`. `json_factory.cpp` mirrors it exactly.

`account` and `global` scopes remain jailed (sanitize drops `..` and drive-colon segments, so a
nested name can only nest *deeper inside* `settings/`/`json/`). **`root` scope is the only escape**,
and it lets `Settings("Widgets/Data/foo.ini", "root")` write straight into `Widgets/Data/`.

## 2. The jail design (both layers)

**Locked decision:** `Py4GW.ini` at the project root is the **single sanctioned exception** — the
only file permitted outside `settings/`/`json/`. It is a real cross-process contract: the external
launcher (`Py4GW_Reforged_Launcher/launcher_core/gw1_launch.py`) writes its `autoexec_script` key,
and `Style Manager.py` reads it in-client.

Native (`SettingsManager::Open` / `JsonFactory::Open`):
- Collapse `root` scope to a **hardcoded allow-list of exactly `Py4GW.ini`**. Any other root-scoped
  name (especially one containing a subfolder) is rejected/redirected — no more arbitrary root writes.
- Add a defensive assertion in `Bind()`: after computing the final absolute path, verify it is
  lexically under `<moduleDir>/settings` or `<moduleDir>/json` (or is the one allow-listed root
  file). If not, refuse to bind and log — belt-and-suspenders even if a future scope is added.

Python (`Settings` / `JsonFactory`):
- Reject/normalize `scope="root"` for anything other than the allow-listed file, mirroring native so
  violations surface at the call site during development, not silently at the C++ boundary.

## 3. Migration inventory (by tree)

### 3a. `Py4GWCoreLib/`
**A — migrate:**
- `ImGui_src/Style.py:341/347/374` — theme files `Styles/<name>.json` (open+json) → **JsonFactory**.
- `UIManager.py:225/235/248/267` — `frame_aliases.json` read/rewrite → **JsonFactory (Global)**.
- `modular/hero_setup_model.py:152/162/179` — per-account hero config JSON → **JsonFactory**.

**Exceptions (not INI/JSON-shaped):**
- `database_src/DBMgr.py` — full **sqlite** engine + `.db/.db-wal/.db-shm` backups, plus a
  user-invoked DB↔JSON export/import. Cannot become a Settings/JsonFactory document.
- `Pathing.py:407/430` — **pickle** binary navmesh cache (`navmesh_<map>.bin`). Regenerable binary.

**D — already compliant:** `name_obfuscation/store.py`, `agent_recolor/store.py`,
`launch_bar/persistence.py` (Settings-backed; JSON only encoded *into* an INI key).

### 3b. `Widgets/` (~23 sites, 13 widgets)
**A — migrate to JsonFactory:**
- `Guild Wars/Travel.py:57/85` — `Widgets/Config/Travel.json`.
- `Guild Wars/Customization/Layout Manager.py:185/196` — `Widgets/Config/window_layouts.json`.
- `Items & Loot/LootManager.py:102/134` (loot_config.json) **and `:84/111` writing user thresholds
  into `Widgets/Data/rarity_filter_data.json`** — stop writing to `Widgets/Data`.
- `Items & Loot/MerchantRules.py` (5839/6368/6408 + backups 6258/6266/6354) — big hand-rolled
  per-account profile store with atomic temp+fsync+os.replace and `.bak` snapshots.
- `System/Enemy Tracker.py` — cross-account `EnemyData/EnemyTrackerData.json` +
  `EnemyTrackerNames.*.json` with a **hand-rolled `O_EXCL` cross-process lock** → **JsonFactory
  (Global)** — *verify Global-scope cross-process lock parity before removing the lock*.
- `Automation/Multiboxing/CombatPrep.py:162/174/192` — `formation_hotkey.json`.
- `Automation/Enhancements/Dhuum Helper.py:59/81` **and** `Bots/Missions/Core/Underworld.py:2623/2640`
  — shared `Widgets/Config/EquippedArmor.json` → one shared JsonFactory doc.
- `Underworld.py:2457/2994` — `UnderworldBot_quest_times.json`.
- **7 bots share one identical `"<BOT> Heroes.json"`-next-to-.py pattern** (Mount Qinkai, Asura,
  Vanguard, Sunspear, Norn, Deldrimor, Lightbringer) → **one shared JsonFactory helper**.
- `System/Style Manager.py:529` — presets to a **relative** `Styles/` path (cwd-bug) → JsonFactory.
- `Items & Loot/TeamInventoryViewer.py:454` — raw `open()` of *another account's* JsonFactory file
  (writes already compliant) → read peers via `PyJson`/JsonFactory.
- `Items & Loot/Xunlaimanager.py:121/170` — hand-rolls the Settings folder layout to copy a foreign
  account's `xunlai_manager.ini` → route the cross-account copy through Settings.

**B — legit bundled reads (no action):** shipped catalogs/tables (Nick_cycles, modelid_drop_data,
runes, merchant_rules_catalog, skill catalogs), reading `.py` source for AST/exec.

### 3c. `HeroAI/`, `Sources/`, `Bots/`
**A — migrate:**
- `Sources/frenkeyLib/MultiBoxing/settings.py` — **own parallel `Settings` class** → `Widgets/Config/
  MultiBoxing/settings.json` + `Layouts/<name>.json`. Migrate settings→Settings, layouts→JsonFactory;
  delete the parallel class.
- `Sources/frenkeyLib/LootEx/*` — **own parallel `Settings` class** + profiles + scraped data.
  *See decision D4: LootEx is already slated for replacement by `docs/loot_redesign/`.*
- `HeroAI/hex_removal_src/hex_removal_config.py` — per email+char JSONC (hand-rolled comment
  stripping) → **JsonFactory** (drop the JSONC serializer).
- `Sources/frenkeyLib/ItemHandling/{RuleConfig,Rules/profile,Items/ItemData}.py` → JsonFactory.
- `Bots/marks_coding_corner/AlcoholProc.py` → JsonFactory/Settings.

**D — already compliant:** `SulfurousRunner/settings.py`, `PartyQuestLog/settings.py` (local class
that *delegates to* the sanctioned Settings); assorted `Sources/ApoSource/*`, InvPlus modules.

## 4. Rules (owner-locked — no further exception debate)

- **Only two exceptions exist**, both intrinsic, not conveniences:
  1. `Py4GW.ini` at the project root — reached ONLY via the hardcoded, path-less accessor
     (`Settings.py4gw_ini()` / native `OpenPy4GWIni()`). No `root` scope exists anymore.
  2. The external launcher (`Py4GW_Reforged_Launcher/`) — a separate, non-injected process that
     physically cannot load the embedded modules; it keeps its own handlers, confined to its folder.
- **Everything else migrates to `Settings`/`JsonFactory`.** No parallel config classes, no overrides,
  no side projects.
- **START CLEAN.** Do not write migration code that reads old files from outside the jail (that read
  is itself a bypass). Delete legacy-import / legacy-path-fallback code; config regenerates fresh
  under `settings/`/`json/`.
- Stores that are genuinely not INI/JSON (sqlite DB in DBMgr, pickle navmesh cache in Pathing, IPC
  lock/flag files, append-only logs) still need reworking to comply — tracked as open technical items,
  not granted a standing "governed exception".

## 5. Proposed rollout (after decisions land)

1. **Native jail first** (Reforged_Native): allow-list `root`→`Py4GW.ini`, `Bind()` path assertion,
   Python wrapper guard. Owner builds; confirm. *Nothing else is safe to rely on until this lands.*
2. **Shared bot-hero helper** — one JsonFactory-backed helper; convert the 7 title/vanquish bots +
   `EquippedArmor.json` sharers. Highest ratio of sites-fixed per change.
3. **Plain widget config** — Travel, Layout Manager, LootManager, CombatPrep, Style Manager,
   Underworld state (direct JsonFactory swaps).
4. **Core lib** — Style.py, UIManager frame aliases, hero_setup_model.
5. **Heavy stores** — MerchantRules profile store, Enemy Tracker (after lock-parity check).
6. **frenkeyLib MultiBoxing** parallel-Settings removal; LootEx per D4.
7. **Launcher** per E1.
8. **Exceptions** — codify E2/E3 as governed exceptions (own folder, documented) or rework per rulings.
9. Final sweep: re-run the audit greps to prove zero raw handlers remain outside the sanctioned
   exceptions.
