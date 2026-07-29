# Persistence Migration Spec — how to convert every file

Canonical rules for replacing ad-hoc file handlers with the two jailed classes. Follow this exactly
so every converted file behaves the same way.

## The only sanctioned persistence

- **JSON** → `from Py4GWCoreLib import JsonFactory` (or `from Py4GWCoreLib.py4gwcorelib_src.JsonFactory
  import JsonFactory`). Structured/nested data, lists, per-key trees.
- **INI/flat config** → `from Py4GWCoreLib import Settings` (or `...py4gwcorelib_src.Settings import
  Settings`). Flat `(section, key) -> value`.
- **Nothing else may touch disk.** No `open`, `json.load/dump`, `configparser`, `pickle`, `codecs`,
  `Path.read_text/write_text`, `shutil` copies of config, `os.remove/rename` of data files.

### No IPC / cross-account comms through files — use `Messaging`
Absolutely no inter-process signaling or cross-account communication via files (flag files, `.lock`
files used as signals, `.fd`/temp handshake files, files written by one account and read by another).
- **Cross-account / cross-client comms** → the `Messaging` class (routes messages; no file I/O). Owning
  module holds its config; values spread via message payloads.
- **Cross-process write safety** (multibox writing the same shared file) is already handled natively:
  use **`global` scope** and the factory takes a cross-process lock + journal-merge for you. Delete the
  hand-rolled `O_EXCL`/lock-file dances entirely — do not replace them, remove them.
- A file read by one account from another account's folder is forbidden (never read another account's
  file); move that data to `global` scope or send it over `Messaging`.

### The only exceptions (do NOT migrate these)
1. `DBMgr` (sqlite) — `Py4GWCoreLib/database_src/DBMgr.py`. Reworked later; leave its file I/O.
2. `Py4GW.ini` — reached ONLY via `Settings.py4gw_ini()` (no `scope="root"` anywhere; it now raises).
3. The external launcher `Py4GW_Reforged_Launcher/` — separate non-injected process; out of scope.

## Scope choice
- **`account`** (default) — per-account / per-character preferences and state. Lands under
  `settings|json/<email>/<name>`. Use for almost everything a single player configures.
- **`global`** — data shared across every account/client on the machine (cross-account DBs, shared
  profiles, machine-wide prefs). Lands under `.../Global/<name>`.

## Document naming
The `name` is a relative subpath under the scope folder; keep it descriptive and stable. Mirror the
widget's identity, e.g. `JsonFactory("Widgets/Travel.json")`, `Settings("Widgets/CombatPrep.ini")`.
Folders in the name are preserved (nested under the jail). Do NOT prefix with `Widgets/Config` or
`Widgets/Data` — those were the old bypass locations; the jail already namespaces by scope.

## START CLEAN — mandatory
- **Delete** legacy-import / legacy-path-fallback code. Do NOT read an old file from `Widgets/Config`,
  `Widgets/Data`, the project root, or next to the widget to seed the new store — that read is itself
  a jail bypass. Users start clean; the document self-seeds from defaults or empty.
- Remove now-dead helpers: `os.path.join(...)` path builders, `os.makedirs`, lock files, `.tmp`/
  `.bak` atomic-write dances, directory-listing enumeration. The native side already does atomic
  writes, cross-process locking (global scope), and autosave.
- Remove now-unused imports (`os`, `json`, `configparser`, `pickle`, `shutil`) if nothing else uses
  them. Pyright will flag leftovers.

## API cheat-sheet

### JsonFactory (self-persisting singleton; never call save() in normal flow)
```python
cfg = JsonFactory("Widgets/Travel.json")          # account scope (default)
cfg = JsonFactory("EnemyTracker.json", "global")   # cross-account

cfg.get(path, default)          # typed by default's type; never raises
cfg.get_json(path, default)     # subtree as dict/list; "" path = whole doc
cfg.set(path, scalar)           # bool/int/float/str leaf; autosaved; dedups
cfg.set_json(path, dict_or_list)# whole subtree
cfg.append(path, value)         # push onto an array
cfg.has(path) / cfg.delete(path) / cfg.keys(path) / cfg.size(path) / cfg.items(path)
```
Path is a slash address into the tree: `"ui/window/pos/x"`, `"waypoints/0/x"`.

### Settings (self-persisting singleton)
```python
cfg = Settings("Widgets/CombatPrep.ini")           # account scope (default)
cfg.get_str/get_int/get_float/get_bool(section, key, default)   # never raise
cfg.set(section, key, value)                        # stringified, autosaved, dedups
cfg.items(section) -> {k: v}; cfg.sections(); cfg.keys(section); cfg.has/delete/delete_section
```

## Worked conversion (before → after)

Before (raw JSON to Widgets/Config, hand-rolled load/save):
```python
import os, json
CFG = os.path.join("Widgets", "Config", "Travel.json")
def load():
    if os.path.exists(CFG):
        with open(CFG) as f: return json.load(f)
    return {"favorites": [], "pos": [100, 100]}
def save(data):
    with open(CFG, "w") as f: json.dump(data, f)
```
After (jailed, self-persisting, start-clean — no legacy read, no file dance):
```python
from Py4GWCoreLib import JsonFactory
_cfg = JsonFactory("Widgets/Travel.json")           # account scope
def get_favorites(): return _cfg.get_json("favorites", [])
def set_favorites(v): _cfg.set_json("favorites", v)  # autosaved
def get_pos():        return _cfg.get_json("pos", [100, 100])
def set_pos(v):       _cfg.set_json("pos", v)
```

## Verify each file
Run `npx pyright <file>` and resolve every diagnostic the change introduces (pre-existing unrelated
errors may remain — note them, don't chase them). Then confirm no raw handler remains in the file.
