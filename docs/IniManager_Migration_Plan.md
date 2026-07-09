# IniManager → Settings Migration Plan (LOCKED)

> Status: **locked by user approval**. This plan is fixed — it is not to be
> changed or extended once execution begins. It supersedes the requirement-only
> `IniManager_Migration_Handover.md` for execution purposes.

## Goal

Quit `IniManager` and stop using `IniHandler` for settings. All persisted
variables go through the PySettings-backed `Settings` class
(`Py4GWCoreLib/py4gwcorelib_src/Settings.py`): typed get/set with `default=`
and automatic persistence (no declaration, no explicit flush). Remove the
`ini_key` parameter from the `ImGui_Legacy` window wrappers.

## Backend readiness

`Settings` is already complete and needs **no new capability**:

- `get_bool/int/float/string(key, default=…)`, generic `get(key, default)`
- `set(key, value)` — writes in memory immediately, native debounced autosave
- `section("X")` views so callers drop a repeated prefix
- `account` (default) and `global` scope
- subfolder document names (`"bots/foo/config.ini"`)

## Scope

**98 distinct files** reference `IniManager`/`IniHandler` (9 inside
`Py4GWCoreLib` core, including the facade export). All are in scope.

## Phases

### Phase 1 — DONE
Window handling removed from `ImGui_Legacy.Begin` / `BeginWithClose` / `End`
(`Py4GWCoreLib/ImGui_Legacy_src/ImGuisrc.py`). Window layout is now owned by
imgui.ini.

### Phase 2 — Wrapper signatures
In `ImGui_Legacy_src/ImGuisrc.py`, remove `ini_key` from `Begin`,
`BeginWithClose`, `End`; remove the `save_vars` call and the `IniManager`
import from `End`. The wrappers become pure window begin/end.

### Phase 3 — Migrate all variable usage to `Settings` (98 files)

| Old (IniManager / IniHandler) | New (`Settings`) |
| --- | --- |
| `ensure_key(path, file)` | `Settings(f"{path}/{file}")` |
| `ensure_global_key(path, file)` | `Settings(f"{path}/{file}", scope="global")` |
| `IniHandler(fullpath)` used for settings | `Settings(name[, scope="global"])` |
| `add_bool/int/float/str(...)`, `load_once(...)` | **deleted** (no declaration/preload) |
| `getBool/Int/Float/Str(key, var, default, section=s)` | `cfg.section(s).get_bool/int/float/string(name, default)` |
| direct `read_bool/int/float/key(section, name, default)` | `cfg.section(section).get_*(name, default)` |
| `set(key, var, value, section=s)` + `save_vars(...)` | `cfg.section(s).set_bool/…(name, value)` (autosaved) |
| direct `write_key(section, name, value)` | `cfg.section(section).set_*(name, value)` |
| `if not INI_KEY: return` guards | **deleted** (PySettings stages until the account anchor resolves) |

### Phase 4 — Drop `ini_key` at Begin/End call sites
34 files call `ImGui_Legacy.Begin/BeginWithClose/End`; remove the `ini_key`
argument (positional or `ini_key=`). Overlaps heavily with Phase 3.

### Phase 5 — Quit `IniManager`
- Remove the facade export in `Py4GWCoreLib/__init__.py` (lines ~183 and ~234).
- Delete `Py4GWCoreLib/IniManager.py` (and its flush callback registration).
- Stop all IniHandler-for-settings usage.

### Phase 6 — Verify
No remaining `IniManager` / `add_*` / `save_vars` / `ini_key` references.
Spot-check one account-scoped and one global widget: value persists and
reloads correctly.

## Pre-decided constraints (from the handover; not revisited)

- **No on-disk data migration.** PySettings roots at `DLL/settings/<email>/…`;
  the old INI tree is not carried over. Users start from code defaults.
- **`.cfg` templates dropped.** Defaults now come from the `default=` args in
  `get_*`. The 5 seeded widgets (WidgetCatalog, InventoryPlus, WidgetManager)
  get their defaults in code during migration.

## Outcome & amendments (post-execution, per user direction)

- **In-scope migration complete.** All IniManager var-system + IniHandler-for-settings
  usage in scope moved to `Settings`. Verified: no stray
  `ensure_key`/`add_*`/`load_once`/`save_vars`, no `ImGui_Legacy.End(arg)`, no
  `Begin/BeginWithClose(ini_key=…)` outside the deferred file below.
- **`IniManager.py` NOT deleted this pass** (Phase 5 amended). It remains for the
  deferred `Pycons.py`; the `__init__.py` facade export stays with it.
- **Deferred (user: "address side ini handling later"):** `Pycons.py` (bespoke
  configparser + per-account IniHandler + presets) and `Messaging.py` (writes
  Pycons' account file). Left on IniManager/IniHandler.
- **Out of scope (user: cross-account only on Settings if in scope):** cross-account
  features keep direct `IniHandler` path writes — `InventoryPlus` "Copy to All
  Accounts", `Xunlaimanager` copy-from-account, `HeroAI/settings.py`
  resurrection-scroll. `IniHandler` (the low-level class) therefore stays.
- **`Py4GW.ini` → new `root` scope.** Hard rule: `Py4GW.ini` lives at the project
  root, shared by all accounts. Added `SettingsScope::Root` in the native project
  (`settings.h`/`settings.cpp`/`settings_bindings.cpp`) binding `<root>/<name>`
  (no `settings/` subfolder); repointed the 4 native `Open("Py4GW.ini")` sites to
  `Root`; documented `scope="root"` in `stubs/PySettings.pyi`; `Style Manager.py`
  now uses `Settings("Py4GW.ini", scope="root")`. **Requires a native DLL rebuild.**
- **Standalone `Py4GW_Launcher.py`** excluded (its own configparser `IniHandler`,
  runs outside the injected runtime).

## Main risk

`var_name` ≠ on-disk `name`: `getBool(key, var_name, …, section=s)` addresses
by `var_name`, but the disk key is the `name` from the matching `add_*` call.
So Phase 3 is per-file careful work — each file's `add_*` declarations must be
read to map `var_name → (section, name)`, not blind find/replace.

## Execution notes

- Core `Py4GWCoreLib` files (9) are migrated by hand.
- Widget/bot files run as batched sub-agent sweeps following the mapping table.
- **One `Settings` instance per file.** Construct it once — a module-level
  `cfg = Settings("path/file")` (or a single instance held on the script's main
  class) — and reuse `cfg` for every get/set. Do **not** rebuild
  `Settings(...)` on each call, and do not chain `Settings(name).section(...)`
  inline in hot paths. `PySettings` returns the same underlying document for a
  given `(name, scope)`, so the wrapper is just a thin, reusable handle.
- The old `ini_key` string (`"path/filename"`) is byte-identical to a
  `Settings` document name, so `WindowFactory.key()` and `FloatingIcon`'s string
  params are unchanged; only leaf get/set and `End()` calls move to `Settings`.
