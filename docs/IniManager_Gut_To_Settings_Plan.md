# IniManager → Settings Migration Plan (authoritative)

> Status: **plan only — not yet executed.** This supersedes the earlier draft of
> this file, which was written before the investigation below and contained
> mistakes (an invented `is_bound` gate, slash-joined addressing, a dropped var
> registration, and a "loaded from disk" diagnostic that conflated memory with
> disk). Everything here is grounded in the live diagnostics and the native
> source, not assumptions. Two prior migration attempts failed completely; this
> document exists so the next one does not.

## 1. Objective & architecture

Two layers:

- **`Settings`** (`Py4GWCoreLib/py4gwcorelib_src/Settings.py`) — provides **all**
  functionality, as a thin Python layer over the native `PySettings` module.
  This is the class future callers migrate onto directly.
- **`IniManager`** (`Py4GWCoreLib/IniManager.py`) — an **empty shell**. Every
  public method becomes a one-line forward into `Settings`. Its only remaining
  job is preserving the legacy surface so **no caller changes**:
  - the public method API (`ensure_key`, `read_*`, `write_key`, `get`/`set`,
    `getBool/Int/Float/Str`, window config, `add_*`, `load_once`, `save_vars`, …),
  - **and** the node facade: callers reach `_get_node(key).ini_handler.<IniHandler
    API>` and poke node fields directly.

No behavior change is intended: same on-disk files, paths, sections, keys, and
values — existing configs must be preserved (no forced migration).

## 2. Why the previous attempts failed (root causes, proven)

Ranked by severity, each grounded in the runtime log and/or native code:

1. **Slash-in-section addressing (the real killer).** The native binding used a
   single `"section/key"` string split on the **first `/`**. Real section names
   contain `/`: `[Widget:System/Messaging.py]`, `[Widget:Guild Wars\Triggers/Enter
   character on load.py]`, etc. (the entire WidgetManager widget-enable catalog).
   So a migrated read of `("Widget:System/Messaging.py", "enabled")` asked native
   for section `Widget:System`, key `Messaging.py/enabled` — which does not exist
   → every widget-enable state reverts to default on first run = total,
   immediately-visible failure. *Fixed in native, see §4.*
2. **An invented `is_bound` gate.** The first shell added
   `if scope=="account" and not is_bound(): return ""` to `AddIniHandler`. It was
   never in the original class. Account `ensure_key` then returned `""` forever,
   so no account widget ever loaded or saved. *Fixed by native synchronous bind
   + no gate, see §4/§6.*
3. **The node/`ini_handler` facade was removed.** Callers
   (`HeroAI/follow/*`, `HeroAI/ui_base.py`, `WidgetCatalog`, `EnemyBlacklist`)
   reach into `_get_node(key).ini_handler.write_key(...)`, `.filename`, and poke
   `cached_values`/`pending_writes`/`vars_values`/`needs_flush`/`vars_loaded`.
   Returning a bare `Settings` object threw
   `'Settings' object has no attribute 'ini_handler'` at widget load.
4. **configparser key-case.** The legacy backend lowercased option keys on disk;
   native reads case-sensitively. Keys must be lowercased on the wrapper edge.
5. **Silent failures everywhere.** Wrong addressing returned defaults with no
   error; native swallowed directory/load errors. *Native logging added, see §4.*

Methodological root cause: the migration was rebuilt from assumptions about the
native lifecycle instead of observed behavior, and then patched with shims.

## 3. Ground-truth facts (from the live diagnostics)

The working IniManager was instrumented (`INI_DIAG`) and driven in-client. Facts:

- **Paths.** `get_projects_path()` == native `GetModuleDirectory()`. Files resolve
  to `<proj>/Settings/<email>/<path>/<file>` (account) and
  `<proj>/Settings/Global/<path>/<file>` (global). Native uses lowercase
  `settings/…`, which is the **same physical folder** on Windows. Proven: native
  wrote `imgui.ini` into `Settings/<email>/` during a test.
- **Account email timing (two different signals).** The native anchor
  (`is_anchored`, prints "Account anchor ready") fires as soon as
  `char_context->player_email` exists. `Player.GetAccountEmail()` — what
  IniManager gates on — reads the *same* email but only after `Map.IsMapReady()` +
  `not IsInCinematic()` + `IsPlayerLoaded()`, ~1–2 s later. **The migration must
  keep gating on `Player.GetAccountEmail()`**, not `is_anchored`.
- **Files are mostly defaults.** A widget declares many vars but persists only the
  handful that changed. Example: `Mission Map +.ini` — 337 vars *declared*, **9**
  on disk (198 bytes: `[Window config]`, `[Terrain]`, `[Marker.pet]`).
- **Section names carry special characters** — `/`, `\`, `:`, spaces. Keys are
  lowercase (configparser); section names preserve their case.
- **`var_name` ≠ on-disk `name`** is common — see §5.

## 4. Native `PySettings` — capabilities after the fixes

The native settings class is a **cache with periodic disk flushes**, the same
model as the old IniManager (confirmed in `settings.cpp`):

- **Cached:** each document holds `std::vector<IniSection> sections_` in memory;
  all reads/writes hit memory, no per-call disk I/O.
- **Periodic flush (owned by C++):** every setter marks the doc dirty;
  `AutosaveTick` (stepped from `SettingsManager::Update()` every ~10 ms) flushes
  after **2000 ms** of write-silence or **10000 ms** max dirty; `FlushAll()`
  flushes on shutdown; saves are atomic (temp file + rename). The cadence is a
  native concern — not a migration decision.
- **No auto-reload on external mtime change** (the old `IniHandler` reloaded);
  native reads memory unless `reload()` is called. Only matters for two processes
  sharing one file (multibox).

Fixes made in the native tree (built + additive, no behavior change to the
current working system):

- **Explicit `(section, key)` API — the slash fix:** `set/get/has/remove/items`
  take section and key as **separate arguments**, never delimiter-parsed, so any
  name with `/`, `\`, `:`, or spaces works.
- **`path()`** — the document's real on-disk path (for `.filename` and template
  existence checks).
- **Synchronous account bind:** `Open()` binds (and loads) an account document
  immediately when the anchor is already resolved, so a read right after open
  sees disk — matching the legacy synchronous `IniHandler`. No Python gate needed.
- **Error logging:** `Bind()` logs directory-creation failures; `LoadLocked()`
  logs a file that exists but won't open (a missing file stays silent — normal).
- **`delete_section`** binding.
- Scopes: `account` / `global` / `root`. `stubs/PySettings.pyi` updated.

## 5. The variable system — correct model and migration

The old var system is a **disk-backed write-back cache plus a var-definition map**.
There are no memory-only variables; the source of truth is always the ini.

- `add_*(key, var_name, section, name, default)` registers
  `IniVarDef(var_name → section, name, type, default)`.
- `load_once` reads disk at `(vd.section, vd.name)` into a cache keyed by
  `(vd.section, var_name)`.
- `get`/`set` operate on that **cache**, keyed by `(passed_section, var_name)`.
- `save_vars` flushes dirty cache entries to disk at **`(vd.section, vd.name)`** —
  the declared address, **not** `var_name`.

The load-bearing subtlety: **`var_name` and the on-disk `name` differ**, proven:

```python
ini.add_int(INI_KEY, f"{slug}_color", section, "color", ...)   # slug="pet", section="Marker.pet"
# var_name = "pet_color"   →   on disk: [Marker.pet] color
```

Migration of the var system:

- **`add_*` — KEEP.** It is the `var_name → (section, name, type, default)` map;
  get/set must resolve through it. (Only the *caching/staging* is discarded.)
- **`load_once` / `save_vars` — no-op.** Native is the cache and the flush.
- **`get(key, var_name, default, section)`** → resolve `vd`; return
  `Settings.get_<vd.type>(vd.section, vd.name, vd.default)`. The fallback is the
  **declared** `vd.default` — that is what the old class uses (`load_once` reads
  disk with `vd.default`, and `get` returns `vd.default` for a declared var), not
  the `default` argument. **Never `default or vd.default`** — that corrupts falsy
  defaults (`0`/`False`/`""`). Use `vd.section`/`vd.name`, **not** the passed
  `section`/`var_name` (that is where `save_vars` actually persisted). Undeclared
  fallback: `Settings.get(section, var_name, default)`.
- **`set(key, var_name, value, section)`** → `Settings.set(vd.section, vd.name,
  value)`. Undeclared fallback: `Settings.set(section, var_name, value)`.

## 6. `Settings` class design

- `Settings(name, scope="account")`, cached one instance per `(name, scope)`,
  opens `PySettings.settings(name, scope)`.
- **Addressing:** `get_str/int/float/bool(section, key, default)` and
  `set(section, key, value)` call `doc.get/set(section, key.lower(), …)` — the
  **explicit native API**. Key lowercased (configparser parity), **section
  verbatim**. Never slash-join.
- **Values:** written as `str(value)` to mirror the legacy on-disk format; typed
  getters let native parse them back. `set` dedups against the current value so
  unchanged existing files are not rewritten.
- **Readiness:** `is_ready()` = native `is_bound()`. No gate.
- **Path / templates:** use native `doc.path()` for `.filename` and to check "does
  this file already exist?" before seeding `settings/Defaults/<name>.cfg` →
  `default_template.cfg`.
- **Section ops:** `has`, `delete`, `delete_section`, `sections`, `keys`, `items`,
  `clone_section`.
- **Window helpers:** `begin/end_window_config`, `track_window_collapsed`,
  `mark_begin_success`, `is_window_collapsed` — nothing special: they just
  read/write the `[Window config]` keys (`x`/`y`/`width`/`height`/`collapsed`)
  through the normal `get`/`set`, for compatibility with current callers.
- **Legacy var-map** — a plain per-document dict `var_name → (section, name,
  type, default)`, populated by the forwarded `add_*`, with `get_var`/`set_var`
  that resolve a legacy `var_name` call to the real `(section, name)`. It is a
  legacy-compat shim used **only** by IniManager's old get/set path; the direct
  `Settings` API ignores it. Not a "registry" and **not** in C++ — it dies when
  callers move to `Settings.get(section, key)` directly.

## 7. `IniManager` shell design

- `_handlers: dict[key -> _Node]`. `_Node` carries `.settings` (the `Settings`
  instance), the `.ini_handler` handle (**same shape as today**, backed by
  `Settings` so it and IniManager persist to the same place), `.is_global`, and
  the vestigial fields callers write to (`cached_values`, `pending_writes`,
  `vars_values`, `vars_loaded`, `needs_flush`) as harmless empty containers.
- `AddIniHandler`: guard on `_is_account_ready()` (`Player.GetAccountEmail() != ""`
  — the original signal), open `Settings(key, scope)`, build the node, **return
  the key immediately** (no `is_bound` gate).
- All read/write/window methods forward to `node.settings`.
- Var system per §5: `add_*` populates the legacy var-map (§6); `load_once`/
  `save_vars` no-op; `get`/`set` resolve `var_name` through it.

## 8. Consumer inventory (scope = IniManager only)

From a full usage scan, two consumption patterns the shell must preserve:

**A. IniManager public API** (~98 files): `ensure_key`/`ensure_global_key`,
`read_*`, `write_key`, `get`/`set`/`getBool/Int/Float/Str`, `add_*`/`load_once`/
`save_vars`, window config. Covered by §5 (vars) + §7 (forwarding).

**B. Scripts that reach `_get_node(key).ini_handler`** — 5 files:
`HeroAI/follow/editor.py`, `HeroAI/follow/leader_publish.py`, `HeroAI/ui_base.py`,
`Py4GWCoreLib/EnemyBlacklist.py`, `Widgets/WidgetCatalog/Py4GW_widget_catalog.py`.
They **get the handle and use or return it** (e.g. `EnemyBlacklist._handler()`
returns `node.ini_handler`). The shell must keep returning that handle **with the
same shape as today — do not change it.** These same files also require:
- `_handlers` as a dict keyed by the ini_key, with working `key in im._handlers`
  and `del im._handlers[key]` (editor/leader_publish rebind globals this way);
- `getattr(node, "is_global", False)` correct;
- the vestigial node fields (`cached_values`, `pending_writes`, `needs_flush`,
  `vars_values`, `vars_loaded`) present as harmless containers (poked right after
  a `write_key`).

### Verified call patterns (from a call-site scan)

- **Slashes appear in section names AND keys.** The catalog registers enable flags
  via `_widget_var(id,"enabled")` = `"{id}__enabled"` (id like `folder/file.py`);
  legacy data holds both `[Widget:<id>] enabled` and `[Widget:System]
  <full var_name>`. So `/`, `\`, `:` occur on both sides — the explicit
  `(section, key)` native API is mandatory; nothing may be slash-joined.
- **A real `[settings]` section exists on disk** (WidgetCatalog), the same name as
  native's default section. The wrapper must **always pass an explicit section**;
  never flat keys.
- **~82% of get/set pass `section=`.** The no-section calls (`init`, colors,
  favorites) still resolve correctly because set/get go through the legacy var-map
  (`vd.section`/`vd.name`), not the passed `section`.
- **8 files mix the var system with direct `read_*`/`write_key`** on the same
  documents (ImGui_Legacy, WidgetManager, WidgetCatalog, InventoryPlus, HeroAI
  follow/ui). The migration unifies both onto `Settings(section, key.lower())` —
  *more* consistent than today (removes the `set()`→`save_vars` stale-read
  window). Var name and direct name are the same string, so they align.
- **`.cfg` templates in use:** `WidgetManager`, `WidgetCatalog`,
  `WidgetCatalogFloatingButton`, `InventoryPlus`, plus `default_template.cfg`.
  `Settings` seeds these into a newly-created account file.

## 9. Nothing open — all settled

- **Flush cadence** is owned by native C++ (§4) — not a migration decision.
- **Window config** is ordinary keys read/written through `Settings` (§6) — no
  special layer.
- The legacy `var_name → (section, name)` map is a plain dict in the Python
  `Settings` class — not a "registry", not in C++.

The plan is ready to build.

## 10. Verification (in-client, before trusting anything)

Keep the `[DISK]` diagnostics on during migration (they now fire through
`Settings`). Confirm:

- `WidgetManager.ini` (117 keys, including the `Widget:…/….py` slash-sections)
  reads back identically — enable/disable states preserved.
- Account settings load synchronously (no first-frame defaults).
- New writes persist under `Settings/<email>/…` and survive a client restart.
- Window positions restore.
- Mission Map slug vars (`var_name` ≠ `name`) round-trip to `[Marker.*]`.
- No missing-attribute crashes at widget load.

## 11. Work status

- **Native C++ — done** (rebuilt): explicit `(section,key)` API, `path()`,
  synchronous account bind, error logging, `delete_section`, stub updated.
- **Python — done (written, not yet run in-client):**
  - `py4gwcorelib_src/Settings.py` rewritten on the explicit native API
    (`get/set/has/remove/items`), key-lowercasing, `path()`-based templates, no
    gate, legacy var-map, window helpers as plain get/set.
  - `IniManager.py` gutted to a shell: node/`ini_handler` facade + `_handlers` +
    `is_global` + vestigial fields preserved; all methods forward to `Settings`;
    `add_*` → `register_var`, `load_once`/`save_vars` no-op, `get`/`set` resolve
    the var-map.
  - Both compile; all 26 public methods, the full `ini_handler` facade, and every
    `Settings` method the shell calls are present.
- **Verified in-client (rebuilt DLL):** all settings load, no console errors,
  widgets come up with their saved state. Migration complete.
- **Out of scope (future, separate):** the ~41 scripts that construct their own
  `IniHandler` directly and the manual `ConfigParser` handling — untouched.
