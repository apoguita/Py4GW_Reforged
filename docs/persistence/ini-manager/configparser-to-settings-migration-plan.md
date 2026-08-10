# Raw configparser → Settings Migration Plan

Status: **COMPLETE** (2026-07-10) — **`configparser` is fully removed from the active
tree** (`grep -rl configparser` over Widgets/Sources/Py4GWCoreLib/HeroAI = 0). Pycons
`IniHandler` class deleted; profiles now go through the `_SettingsBackedIni` adapter at
**root scope** (same on-disk location); the legacy-config import reads via native Settings
(root scope); the profile-sync value builder uses a tiny `_DictSection` instead of a
throwaway `ConfigParser`. Only `Py4GW_Launcher.py` (external process) keeps its own INI
class. **Needs a native rebuild** (new `apply_section_to_account`) + a live test.

Final piece of the settings-surface consolidation (after `Database.Settings`,
`IniManager`, and `IniHandler`). Goal: remove remaining direct `configparser`
usage. The surviving uses are **not all "settings"** — some are ad-hoc IPC — so
each is classified before touching it.

## The core distinction (the earlier plan missed this)

Two separate mechanisms exist; do not conflate them:

- **Transient coordination** — one client telling others to *act now*. Belongs in
  the **messaging class**: `GLOBAL_CACHE.ShMem.SendMessage(sender, receiver,
  SharedCommandType.X, params)` to send; `Widgets/System/Messaging.py` drains via
  `GLOBAL_CACHE.ShMem.GetNextMessage(...)` and dispatches. Template:
  `SharedCommandType.GetBlessing` handler (`Messaging.py:770`) — leader broadcasts,
  each receiver runs the routine locally and marks it running/finished.
- **Durable config** — persistent per-account or install-wide preferences. Belongs
  in **Settings** (native `PySettings`), scope `account` or `global`.

Native `Settings` is **in-memory, not cross-process fresh**: `Get*` reads the cached
doc (`settings_methods.cpp:29-49`), writes flush via autosave after 2s quiet / 10s
max (`settings.cpp:19-20`). Therefore a cross-process signal **must not** live in
Settings — it goes through the messaging class. (This retires the previous plan's
"verify cross-process freshness" blocker: the answer is "no, and it doesn't matter,
because signals don't belong there.")

## Inventory & verdicts

| File | configparser role | Verdict |
|---|---|---|
| `Widgets/Automation/Enhancements/Heroic Refrain.py` | `_read_ini`/`read_run_flag`/`write_run_flag` + `LEADER_UI`/`PER_CLIENT_UI`/`AUTO_RUN_ALL` | ✅ **DONE** — was all DEAD CODE; block + `import configparser` deleted. |
| ~~`Widgets/Automation/Helpers/Blessed.py`~~ | `[BlessingRun] Enabled` run-flag + `[Settings]`/`AutoRunAll` config | ✅ **DEPRECATED** — moved to `Legacy code and tests/Deprecated but working/Get Blessed/`; its configparser leaves the active tree with it. |
| `Widgets/Automation/Helpers/Pycons.py` | inlined `IniHandler`: account cfg, generic cfg, profiles preset files | **migrate config** (account/global); **profiles stay file-based**; couples to Messaging.py |
| `Widgets/System/Messaging.py` | borrows Pycons' `IniHandler` to read/write ini | **remove ALL file I/O** — delegate config to the domain module; relay values via message payloads |
| `Py4GW_Launcher.py` | own IniHandler | ⛔ excluded — external process, no injected DLL / no native PySettings |
| `Legacy code and tests/widget_manager(indie widgets folder)/*` | legacy indie widget manager | ⬜ deprecated tree, ignore |

## Per-target detail

### 1. Heroic Refrain — dead code (do first, zero risk)
`read_run_flag`/`write_run_flag` are defined but never called; `LEADER_UI`/
`PER_CLIENT_UI`/`AUTO_RUN_ALL` are assigned at module level but never read (verified
by grep). The `global _running, _last_flag, _consumed` in `on_imgui_render` names
vars that don't exist. No file, no message, no external importer. **Delete the whole
INI block + `import configparser` + the stray `global` line.**

### 2. Blessed — DEPRECATED (moved to legacy, not migrated)
Decision: Get Blessed is no longer needed (achievable by other means), so the widget
was moved to `Legacy code and tests/Deprecated but working/Get Blessed/Blessed.py`
rather than migrated. Its configparser usage (run-flag + config keys) leaves the active
tree with it. Dangling consumers to handle by "other means":
- `Widgets/Automation/Bots/Vanquish/PyQuishAI.py` — `get_widget_info("Blessed")` now
  returns `None`; already guarded (`if blessed:`), so blessing steps become no-ops.
- `Py4GWCoreLib/botting_src/subclases_src/INTERACT_src.py:156` — `from Widgets.Blessed
  import Get_Blessed` (the botting `INTERACT.GetBlessing` step). Path was already stale
  (`Widgets.Blessed` ≠ actual location); remove/replace when convenient.

### 3. Pycons (+ Messaging.py) — the large, coupled unit
Pycons already uses ShMem messaging for its transient sync (`SharedCommandType.Pycons`,
sent from `Pycons.py:7852/7898/7951`); its files hold only durable config:
- Window UI files → **already** on `Settings(..., "account")`. Done.
- Account config `Pycons_{email_hash}.ini` (`_resolve_account_ini_path`) → **account**
  scope. Native binds the account doc itself, so the manual email-hash filename becomes
  redundant.
- Generic config `Pycons.ini` (`_resolve_generic_ini_path`) → **global** scope.
- Profiles `Profiles/{id}.ini` → **file-based preset manager** (import/export/rename/
  delete/enumerate-dir). No clean Settings equivalent → **stays file-based** (revisit
  separately if desired).
### 3a. Messaging.py — remove all file I/O (architectural rule) — ✅ DONE
Messaging must **only handle messaging**: no config reads, no file writes. It imported
Pycons' `IniHandler` at three sites; all three inverted:

- **`UseItem` gating** (`Messaging.py:2082-2146`) — reads `team_consume_opt_in`,
  `mbdp_receiver_require_enabled`, `selected_*`/`enabled_*` **and** carries the MB/DP
  model→key table (Pycons domain knowledge leaked into Messaging). Move all of it behind
  one Pycons API, e.g. `Pycons.pycons_should_consume_broadcast_item(model_id) -> bool`.
  Messaging keeps only messaging plumbing (mark running/finished, self-loop guard,
  generic safety checks, the item use) and calls that function. The config read then
  lives in Pycons, where it migrates to Settings.
- **`report_salvage_kits` write** (`Messaging.py:869`) — writes a sender-supplied ini
  path/section/key. **No file write in Messaging.** The salvage-kit count is a value to
  spread back to the caller: reply to `message.SenderEmail` via a message payload (ack/
  result message, like `pycons_send_sync_result_message`); the **calling platform** owns
  persisting it. No in-repo sender exists, so if it proves dead, delete the branch.
- After both, Messaging drops `from ...Pycons import IniHandler` /
  `resolve_pycons_account_ini_path` entirely.

Rules (general, beyond this file):
- Messaging never touches disk. Config-dependent decisions → delegate to the owning
  module. Pure informational output → **console, never a file**. A value that must
  spread → return it via a message payload; the sender's platform handles it.

### 3b. Pycons config coupling (now removed by 3a) — ✅ DONE
Because 3a moved the config read into Pycons (`pycons_should_consume_broadcast_item` +
`_pycons_mbdp_model_key_map`), there is **no cross-widget ini coupling left** — nobody
but Pycons reads Pycons' account doc. Pycons can migrate independently.

### 3c. Pycons internal `IniHandler` → `Settings` — ⬜ NOT a mechanical swap (198 sites)
`IniHandler`/read/write appears ~198× in Pycons. It splits into **three categories**,
and only the first maps cleanly to native Settings:

1. **Own-account main config** — ✅ **DONE.** `_get_ini_handler()` now returns a
   `_SettingsBackedIni` adapter (IniHandler-shaped facade over native
   `Settings("Widgets/Pycons/Pycons.Config.ini", "account")`), so all ~126 `read_*` +
   `write_key` sites and the `config = reload(); config.set(...); save(config)` pattern
   run on native Settings **unchanged**. Native owns throttling/dirty/autosave, so the
   Python `_save_timer` in `save_if_dirty_throttled` was removed (the cheap `_dirty` gate
   stays). A **one-time legacy import** copies the old `Pycons_<hash>.ini` `[Pycons]`
   section into Settings so existing users keep their config. The old path machinery
   (`_ini_path_cache`/`_resolve_*`/`_is_generic_ini_path`) is **kept** because the profile
   subsystem still reads it; it's now vestigial for the main config (cleanup later).
   **Unverified offline — needs a live test.**
2. **Cross-account "team" state — MESSAGING only (no shared memory, no files).** Two
   sites reach into *other* accounts' ini files by email→path:
   - `_set_team_opt_in_for_accounts` (`3207-3223`) **writes** `team_consume_opt_in` into
     every same-party account's ini.
   - `_load_team_flags_for_email` (`8404-8419`) **reads** any account's `team_broadcast`/
     `team_consume_opt_in`.
   This is a niche toggle. **Do NOT add shared-memory fields for it** (schema growth is a
   coordinated-restart, client-crash-on-mismatch hazard — not worth it for a toggle) and
   **do NOT read another account's file.** Use the existing messaging (unlimited msgs
   back and forth):
   - Each account announces its own `team_broadcast`/`team_consume_opt_in` to same-party
     accounts via a message when it changes (and on join); receivers **cache** it locally
     (email → flags). `_load_team_flags_for_email` reads that local cache, not a file.
   - The "leader turns team-calls on for everyone" **action** → a message to each
     follower; the follower flips its **own** flag (its own config) and re-announces.
   - The durable *preference* still lives in the account's **own** config (Settings after
     category 1) — never another account's.

   **✅ DONE (messaging).** Extended the existing `SharedCommandType.Pycons` opcode channel
   with `PYCONS_SYNC_OPCODE_ANNOUNCE_TEAM_FLAGS` (each account announces its own flags to
   same-party accounts every ~1s; receivers cache in `_team_flags_cache`) and
   `PYCONS_SYNC_OPCODE_SET_TEAM_OPT_IN` (leader-toggle → follower flips its own opt-in +
   re-announces). `_load_team_flags_for_email` now reads own `cfg` or the cache (no file);
   `_set_team_opt_in_for_accounts` sends messages (no file). No shared-memory change, no
   Messaging.py change. **Unverified offline — needs a live multibox smoke test.**
   *Profile/settings sync — ✅ **DONE.** `_pycons_sync_write_categories_to_account` and
   `_pycons_write_profile_to_account` no longer write another account's file. They build
   the section's key/values (same transforms; the profile path uses a throwaway in-memory
   configparser purely as a value builder) and push them via the native
   `Settings.apply_section_to_account(section, mapping, target_email)` API. The target
   picks them up via the existing `RELOAD_CONFIG` message, whose handler now calls
   `settings.reload()` (native is in-memory). Native copy/apply API added in
   `Py4GW_Reforged_Native/settings/`: `copy_document_to_account` / `copy_section_to_account`
   / `copy_keys_to_account` (copy from own doc) + `apply_section_to_account` (caller-supplied
   mapping). **`apply_section_to_account` was added AFTER the last rebuild → needs another
   native build.***
3. **Profile preset files** (`2437/2515/7818/7894`) → arbitrary named import/export/
   rename/delete files. No Settings equivalent → **stay file-based**.

Sequence: (1) own-config → Settings; (2) move team flags to ShMem (publish own + read
others) and make the leader-toggle a message; (3) leave profiles on files. Large and
offline-unverifiable — a dedicated pass, not a blind swap.

### Principle (applies repo-wide)
In-game / live / cross-account data → **shared memory** (already carries party, members,
buffs, morale, inventory, aggro…). Durable per-account preferences → **Settings** (own
account). Never read another account's *file* for live state; never store live game data
in a file.

## Migration order (dependency-aware)
1. ✅ **Heroic Refrain** — dead block deleted.
2. ✅ **Blessed** — deprecated to legacy (not migrated).
3. ✅ **Messaging.py** — all file I/O removed; delegates to Pycons.
4. ✅ **Pycons team flags** — moved to messaging.
5. ✅ **Pycons main config** — native Settings via `_SettingsBackedIni` adapter + one-time
   legacy import.
6. ✅ **Pycons profile/settings sync** — native `apply_section_to_account`; no cross-account
   file writes. Profile *files* stay configparser by design.

## Excluded / out of scope
- `Py4GW_Launcher.py` — external, cannot reach native PySettings.
- Legacy indie widget-manager tree — deprecated.

---
Note: reuse the `NativeSettings` alias pattern for any widget that defines its own
`Settings` class (name collision fixed that way in the IniHandler migration).
