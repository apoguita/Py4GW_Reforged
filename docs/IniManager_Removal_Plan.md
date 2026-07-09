# IniManager Removal Plan (delete the shell, callers use Settings directly)

> Status: **EXECUTED.** `IniManager.py` deleted, its `__init__` export removed,
> all ~60 caller files migrated to direct `Settings` calls (`Settings.ensure_key`/
> `ensure_global_key`/`find` + `get_*`/`set`). Zero `IniManager` tokens remain
> outside `Legacy code and tests/`; every touched file compiles. Needs in-client
> verification. One bug caught during removal: the widget-catalog enable state is
> keyed `enabled` on disk (not `<id>__enabled`) — fixed by hand in `WidgetManager.py`.
>
> Original plan below. Precondition met: `IniManager` is already a thin shell
> over `Settings` (see `IniManager_Gut_To_Settings_Plan.md`, done + verified). This
> plan removes the shell entirely — every caller moves to `Settings` directly and
> `IniManager.py` is deleted. Scope is still **IniManager only**; the ~41 scripts
> that construct their own `IniHandler` are a separate future migration.

## Scope

- **64 files** reference `IniManager`.
- **Window integration:** `ImGui_Legacy.Begin` (37) / `BeginWithClose` (7) /
  `End` (58) are keyed by `ini_key` and call IniManager's window methods.
- The `ini_key` string (`"path/filename"`) is **byte-identical** to a `Settings`
  document name, so `WindowFactory.key()` and FloatingIcon string params are
  unchanged — only leaf get/set and the window calls move.

## The two categories per call

### DELETE — no longer needed (the whole declaration/staging machinery)

`Settings` needs no declaration, no preload, no explicit flush. Remove every:

- `add_bool/int/float/str(...)`
- `load_once(key)`
- `save_vars(key)`
- the `ConfigNode`/`ini_handler`/`_get_node` reach-ins (replaced by the `Settings`
  object itself)

### MIGRATE — plain rename to `Settings`

| IniManager | → `Settings` (with `cfg = Settings(name, scope)`) |
|---|---|
| `ensure_key(path, file)` | `cfg = Settings(f"{path}/{file}", "account")` |
| `ensure_global_key(path, file)` | `cfg = Settings(f"{path}/{file}", "global")` |
| `getBool/Int/Float/Str(k, var, default, section=s)` | `cfg.get_bool/int/float/str(s, name, default)` |
| `get(k, var, default, section=s)` | `cfg.get(s, name, default)` |
| `set(k, var, value, section=s)` | `cfg.set(s, name, value)` |
| `read_key/int/float/bool(k, section, name, default)` | `cfg.get_str/int/float/bool(section, name, default)` |
| `write_key(k, section, name, value)` | `cfg.set(section, name, value)` |
| `delete_key` / `delete_section` | `cfg.delete(section, name)` / `cfg.delete_section(section)` |
| `has_key` / `list_sections` / `list_keys` | `cfg.has(section, name)` / `cfg.sections()` / `cfg.items(section)` |
| `clone_section` | `cfg.clone_section(src, dst)` |
| `_get_node(k).ini_handler.<X>` | `cfg.<X>` directly |

Construct `cfg` **once** (module-level or on the widget's state object) and reuse
it — `Settings(name, scope)` returns the same cached instance anyway.

## Special cases (the careful, per-file work)

1. **`var_name` ≠ on-disk `name`.** The migrate table above uses the on-disk
   `name`, but callers pass `var_name`. Where they differ — proven cases:
   `pet_color`→`[Marker.pet] color`, `draw_move_path`→`DrawMovePath`(→disk
   `drawmovepath`) — you must read each file's `add_*` declarations to map
   `var_name → (section, name)`. **Not a blind find/replace.** Files where
   `var_name == name` (the majority) are mechanical.
2. **Window config (Begin/End) — already ported, not re-engineered.** `Settings`
   already owns the `[Window config]` keys and the `begin/end_window_config`
   helpers, and the shell already routes `ImGui_Legacy.Begin/End` through them.
   Removal just repoints those wrappers from
   `IniManager().begin_window_config(ini_key)` to the `Settings` for that
   `ini_key` — same behavior, same file, no imgui move.
3. **Readiness / deferral — keep as-is.** Callers keep their existing
   `if not INI_KEY: return` deferral shape; it just guards constructing `cfg`
   (`Settings(name, "account")`) until the account is ready, exactly like
   `ensure_key` returning `""` did. Global docs bind immediately. No new pattern.
4. **The 5 reach-in files** (`HeroAI/follow/editor.py`,
   `HeroAI/follow/leader_publish.py`, `HeroAI/ui_base.py`,
   `Py4GWCoreLib/EnemyBlacklist.py`, `Widgets/WidgetCatalog/Py4GW_widget_catalog.py`)
   use `_get_node()`, `_handlers`, and vestigial fields — rewrite them to hold a
   `Settings` object and drop the vestigial pokes.

## Phases

1. **Window wrappers:** repoint `ImGui_Legacy.Begin/BeginWithClose/End` from
   `IniManager()` to the `Settings` for that `ini_key` (mechanical — same window
   helpers, already in `Settings`).
2. **Caller sweep (64 files):** apply the migrate table + delete the declaration
   machinery. Batch by directory; each file's `add_*` block is read first to build
   its `var_name → (section, name)` map. Keep each caller's existing readiness
   deferral shape.
3. **The 5 reach-in files:** rewrite onto `Settings` directly.
4. **Delete `IniManager.py`** and its facade export in `Py4GWCoreLib/__init__.py`.
5. **Verify.**

## Verification

- `git grep -n "\bIniManager\b"` returns nothing (outside `Legacy code and tests`).
- No `add_*` / `load_once` / `save_vars` / `ensure_key` / `ini_key=` remain.
- In-client: the same checks as the shell migration — WidgetManager slash-sections,
  account settings load synchronously, Mission Map slug vars, windows restore, no
  crashes.

## Not re-engineered (kept exactly as-is)

- Window config — stays in `Settings` (already ported); wrappers just repoint.
- Readiness/deferral — callers keep their current guard shape.
- Storage paths, sections, keys, values — unchanged.

## Only real question

**Sweep mechanism:** hand-migrate the ~9 core `Py4GWCoreLib` files; run the
widget/bot files as batched sub-agent sweeps against the mapping table, each
verified for its `var_name`→`name` map. That's a *how-to-execute* choice, not a
design change.

## Out of scope (unchanged)

The ~41 scripts that construct their own `IniHandler` and the manual `ConfigParser`
handling — a separate future migration.
