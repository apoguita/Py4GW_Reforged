# IniHandler → Settings Removal Plan

Status: **DONE** (2026-07-09). Shared `Py4GWCoreLib/py4gwcorelib_src/IniHandler.py`
**deleted**; facade exports removed (`Py4GWcorelib.py __all__`, `_legacy_facade.py`,
`ImGui_Legacy.py`). 41 consumers migrated to `Settings`.
- **Pycons.py** keeps a ConfigParser approach (per decision "leave it be") — it now owns
  a **local copy** of the `IniHandler` class (inlined at module top), decoupled from the
  shared one.
- **Messaging.py** imports that local copy from Pycons (`from Widgets.Automation.Helpers.Pycons import IniHandler`),
  which preserves its path-based cross-account write at line 869.
- **Py4GW_Launcher.py** untouched (own class, external).

### Open follow-up (regression to decide on)
- **InventoryPlus "copy to all accounts"** was mechanically moved to `Settings(..., "account")`,
  which targets only the CURRENT account — so that feature no longer writes to *other*
  accounts' files. Fix by giving that one call a path-based writer (like Messaging's), or
  drop the feature. Everything else is functionally equivalent.

Known follow-ups surfaced during the sweep:
- **InventoryPlus "copy to all accounts"** and **Messaging line 869** do cross-account
  writes by absolute path; account-scoped `Settings` targets only the current account,
  so those two call sites need a deliberate decision (they no longer write other accounts').
- **HeartsOfTheNorth** kept the `Accounts/{email}` segment inside a `global`-scope name
  (functionally per-account); tidy to `account` scope later if desired.
- **frenkey PartyQuestLog/SulfurousRunner** define their own `class Settings`; migrated
  via `from ...Settings import Settings as NativeSettings` to avoid shadowing.
- Leftover IniHandler **comments** in Loot_reader, Frog Scepter, SoO, Xunlaimanager (harmless).


Goal: delete the low-level `Py4GWCoreLib/py4gwcorelib_src/IniHandler.py` (a plain
`ConfigParser` file wrapper) and move every consumer onto the native-backed
`Settings` class. Enforces a single settings surface repo-wide.

## What IniHandler is

188-line `ConfigParser` wrapper, constructed with a **raw file path**. mtime-based
auto-reload (picks up external edits → multibox visibility), writes immediately on
`write_key`, recreates on corruption. That's the whole class.

## API mapping (near 1:1 to Settings)

| IniHandler | Settings |
|---|---|
| `IniHandler(path)` | `Settings(name, scope)` |
| `read_key(s,k,d)` | `get_str(s,k,d)` |
| `read_int(s,k,d)` | `get_int(s,k,d)` |
| `read_float(s,k,d)` | `get_float(s,k,d)` |
| `read_bool(s,k,d)` | `get_bool(s,k,d)` |
| `write_key(s,k,v)` | `set(s,k,v)` |
| `delete_key(s,k)` | `delete(s,k)` |
| `delete_section(s)` | `delete_section(s)` |
| `list_sections()` | `sections()` |
| `list_keys(s)` | `items(s)` |
| `has_key(s,k)` | `has(s,k)` |
| `clone_section(a,b)` | `clone_section(a,b)` |
| `reload()` | `reload()` |
| `save(config)` | `save()` (no-arg) ⚠ rework needed |

**Settings `name` convention:** the ini's path relative to the projects root,
forward slashes, keeping the `.ini` filename — e.g. `IniHandler(".../Widgets/Config/Compass +.ini")`
→ `Settings("Widgets/Config/Compass +.ini", scope)`. (Matches `WindowFactory`,
`EnemyBlacklist` usage.) Data relocates to `settings/<scope>/<name>`; old raw-path
files are orphaned once (users reset to defaults on first run — accepted).

## Scope rulings (case-by-case; default = global)

### account (per-account data)
- `Widgets/Guild Wars/Items & Loot/Xunlaimanager.py` (path already `Settings/{account}/…`)
- `Sources/ApoSource/InvPlus/XunlaiModule.py`
- `Widgets/Guild Wars/Items & Loot/InventoryPlus.py` (per-account blacklist / `GetAccountEmail()`)
- `Widgets/System/Messaging.py` (per-account Pycons opt-ins; **line 869 message-driven cross-account write = special case**)
- `Widgets/Automation/Helpers/Pycons.py` (per-account pcon config + opt-ins; profile/cache are sub-files of the same store; **5× `save(config)` reworked to `set()`**)
- `HeroAI/settings.py` → `account_ini_handler` (`Accounts/<email>/HeroAI.ini`)

### root
- `Widgets/Guild Wars/Customization/Style Manager.py` → the `IniHandler("Py4GW.ini")` handler only (`[settings] force_theme_override`, theme)

### global (everything else — shared UI / behavior config)
All remaining widgets/bots/helpers, plus:
- `HeroAI/settings.py` main `ini_handler` (`Widgets/Config/HeroAI.ini`) + `HeroAI.ini` factory
- `Style Manager.py` own config
- frenkey `PartyQuestLog/settings.py`, `SulfurousRunner/settings.py`
- ApoSource `ColorizeModule.py`
- **Legacy/examples (in scope so they don't break):** `Auto Inv.py`, `OLD_Py4GW_widget_manager.py`, `PCons.py`, `Inventory Plus rework.py`, `widget manager_backup/Py4GW_widget_manager.py`, `Loot_reader.py` (commented), `YAVBMain.py`

### Untouched (out of scope)
- `Py4GW_Launcher.py` — its **own** `IniHandler` class, runs **external** (no injected DLL → no native `PySettings`). Leave entirely.

## Execution order
1. Global sweep — straightforward widgets + legacy (construct→`Settings(..., "global")`, rename calls, swap import).
2. Account files — Xunlaimanager, XunlaiModule, InventoryPlus.
3. HeroAI — two handlers (global + account).
4. Style Manager — config global, `Py4GW.ini` → root.
5. Pycons — account; rework 5× `save(config)`.
6. Messaging — account; special-case the message-driven write.
7. Remove 3 facade exports (`Py4GWcorelib.py __all__`, `_legacy_facade.py`, `ImGui_Legacy.py`) → delete `IniHandler.py`.

## Edge cases / notes
- Consumers that use the raw `ConfigParser` returned by `reload()`/mutated for `save(config)` (mainly Pycons) must switch to direct `get_*`/`set` calls.
- Verify native `Settings` gives cross-instance (multibox) visibility for handlers that relied on IniHandler's mtime reload.
- `EnemyBlacklist.py` is NOT a consumer (only a doc comment mentions IniHandler; already on Settings).
