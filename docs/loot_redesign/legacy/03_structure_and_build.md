# Loot Config — Structure & Build Order

The shape of the code and the order to build it. Mirrors `agent_recolor`. See `01` for the design,
`02` for how looting works today.

> **NOT BUILT.** An implementation of this plan was written and then **fully reverted** (it was
> grounded on the wrong catalog). Nothing below exists in the tree. Verified ground truth is in `02`.

## Module layout (mirror `agent_recolor`)

New package `Py4GWCoreLib/py4gwcorelib_src/loot/` (name TBD), same four-file split as `agent_recolor`:

| file | holds | depends on |
|---|---|---|
| `model.py` | **pure data + serialization**: `Condition`, `Filter`, `MarkRule`, and the config container (rarity toggles, List selection, Materials selection, Filters, mark rules). `to_dict`/`from_dict`. No ImGui / Settings / native imports. | nothing game-side |
| `catalog.py` | the **derived data layer**: enumerate `ModelID` + textures + the **grouping table** → the List's groups; `MaterialMap` + the **salvage table** → the Materials surface. One place that turns the shipped tables into what the engine + UI read. | the two data tables |
| `store.py` | **persistence**, global + per-account. NB `agent_recolor` uses **`Settings` for BOTH scopes on one `.ini`** (rules json-dumped into a single key) and never touches `JsonFactory` — mirror that unless the structured global half justifies `JsonFactory` (open call, see `01`). | Settings (± JsonFactory) |
| `controller.py` | the **singleton engine (the brain)**: holds the config; **produces the loot array** (read each ground item once, run the four surfaces, return the ids); **pushes the recolour rules** to native when the config changes (not per-frame — see below); runs the **beacon** pass; holds the **transitional runtime state** (bot adds, skip list — never saved); handles the **cross-account reload** message. | model, catalog, store, Item.Mods, AgentRecolor |
| `config_ui.py` | the **System Settings editor** (`add_sections`: List / Materials / Filters / Marking) **and** the **quick-access window** (`draw_quick_access`, two view modes). Only transient UI buffers live here. | controller |
| `data/` | the two shipped tables: `grouping.json` (category→items) and `salvage.json` (item→materials). | — |

**Supporting changes outside the package:**
- `Lootconfig_src.py`: `LootConfig` becomes a **thin facade over the controller** — keeps
  `GetfilteredLootArray(...)` and the runtime-add methods (`AddToWhitelist`, `AddItemIDToBlacklist` =
  the actor's skip list) so the ~20 callers are untouched.
- `AgentRecolor.py`: add the **item** surface (`EnableItems` + the `set_item_*_color` wrappers) —
  native already has it, the wrapper doesn't.
- `system_settings/model.py` + `config_ui.py`: register a **`loot` category** (the lazy-import/error-
  surfaced branch, like `agents`).
- `Widgets/System/Messaging.py` + `Multiboxing_enums.py`: add a **loot-reload command** + its route. **`SharedCommandType` is an `IntEnum` of `auto()` — member ORDER IS THE WIRE FORMAT.** Append the new member at the END (after `SetResurrectionScroll`), never mid-list, or every later ordinal shifts and breaks running clients. `SendMessage` is point-to-point (4 floats + 4 strings max); fan-out is a `GetAllAccountData()` loop.
- Beacon: build the helper from **`loot_beam.py`** (`class LootBeam`, per-instance, can draw several); `light_beacon.py` is a single-instance tuning harness with module globals. Both run native calls at import — move those out.

## How the pieces answer the two jobs
- **Loot array (decision):** a consumer calls `LootConfig().GetfilteredLootArray(distance)` → facade →
  `controller.filtered_loot(distance)`: snapshot each eligible ground item once (`PyItem` + one
  `mods_core.decode_item`), test the four surfaces (rarity / List / Materials-via-salvage-table /
  Filters), return the ids. **No walking, no "when".**
- **Recolour (applied, not scanned):** when the config changes, push the rule table to native
  (`set_item_rarity_color` / `set_item_type_color` / `set_item_model_color` / `set_item_name_color`,
  plus per-item setters). The game's own item-label detour matches and colours each item at render
  time, with native precedence `agent_id > item_id > model_id > name > type > rarity`. **No per-frame
  Python pass.** (Unlike agents, which do need one.)
- **Beacon (drawn):** the only per-frame part — each frame, ground items matching a beacon rule, capped
  to the nearest few, drawn by the lifted beacon renderer.

## Build order

1. **Data tables** — extract + **your review**. The catalog base is **`modelid_drop_data.json` (403,
   what the Loot Manager actually reads)**, merged with the 7 `LootGroups`-only items, the 5 dead names
   fixed, and a decision on the ~25 placeholder ids; keep `drop_info`. Plus `salvage.json` (from
   frenkey `items.json`, the clean `item → material ids`). These are the foundation.
2. **`model.py`** — the config shapes + serialization. Pure and testable.
3. **Engine core** (`controller.filtered_loot` + read-once snapshot + the four-surface test) and the
   **`LootConfig` facade** wiring, keeping `GetfilteredLootArray`. Validate against real ground items
   with the dump widget — **no UI, no marking, no persistence yet.** Nothing downstream breaks here.
4. **`store.py`** — global ruleset + per-account toggles (mirror `agent_recolor/store.py`).
5. **`catalog.py`** — derive the List (ModelID + textures + grouping) and Materials (MaterialMap +
   salvage table).
6. **`config_ui.py` editor** — List / Materials / Filters tabs in System Settings; register the
   category.
7. **Quick-access window** — the two view modes (texture grid / checkbox table) + the user-configurable
   subset; opened from the settings module, drawn by the always-on host.
8. **Marking** — surface the item setters in `AgentRecolor.py`; add the mark rules (keyed rarity /
   type / model / name / item_id / agent_id) and push them to native on change; remember it is
   **double-gated** (`master_enable` + `item_enable`). Then the beacon pass (from `loot_beam.py`,
   nearest-N cap). Marking tab in the editor.
9. **Cross-account reload** — the message command + route + broadcast-on-save.
10. **Cleanup** — the dead `multibox_loot`/`allow_unasigned_loot` params can only be *removed* if all
    18/8 keyword call sites are updated in the same change; otherwise keep them accepted-and-ignored.
    Retire the old Loot Manager / Inventory+ config paths once the new editor covers them.

Each step is usable on its own: after step 3 the game loots exactly as before but through the new
engine; every step after only adds.

---

## Migration — getting from today to the new class

The build order above says how to *construct* it. This says how to *switch over*. Both existing menus
and the legacy catalogs are live, so the switch has real dependencies.

### M1. Hard dependency: `LootGroups` cannot simply be deleted
`Py4GWCoreLib/py4gwcorelib_src/AutoInventoryHandler.py:458` iterates `LootConfig().LootGroups` and reads
**`m.value`** off each `ModelID` member (`:466`) to build its "don't deposit event items" set, filtered
by a hardcoded category list (`:449-455`: Alcohol, Sweets, Party, Death Penalty Removal, Reward
Trophies→Special Events). InvPlus (`LootModule.py:102`) also iterates it.
**DECIDED — no compatibility view.** `AutoInventoryHandler` and InvPlus are **repointed at the new
class** in the same change. We do not keep a `LootGroups`-shaped shim alive to avoid touching callers.
(The only thing to carry across is the *contract* those callers need: `AutoInventoryHandler` wants a
set of model ids for a chosen set of categories — give it that directly, cleanly.)

### M2. Existing user settings — decide explicitly
Per-account saved state today: `Widgets/LootManager/loot_config.json` (ticked items + blacklist) and
`Widgets/LootManager/rarity_filter_data.json` (the 6 rarity flags), both account-scoped
(`LootManager.py:41-42`). The new class stores its own shapes. **DECIDED — wipe them.** Old settings are not migrated and not imported. We are replacing the system,
not upgrading it; users re-tick. Do not write an import shim.

### M3. Retirement order of the old surfaces
Both old menus mutate the **same singleton**, so during the overlap the last writer wins and
`load_loot_config()` (`LootManager.py:84,141-149`) actively rebuilds the whitelist from its own catalog
— it will overwrite the new class's state. **Do not run old and new editors side by side.** Order:
1. new engine + facade in place (old menus still work, unchanged behaviour);
2. new editor complete and verified;
3. **retire the Loot Manager widget** (move to `Legacy code and tests/`) — this is the switch;
4. decide InvPlus's loot panel: repoint it at the new class, or drop the panel. *Open —
   it is the preferred UI style, so repointing is the likely answer.*

### M4. Catalog retirement
After the one-time merge into the new id-dict (`01`), retire `modelid_drop_data.json` and (subject to
M1) `LootGroups`. Also delete the dead paths this exposes: `Widgets/Config/loot_window.ini`
(`LootManager.py:29`, read, never written) and `MerchantRules.py:56-58,6804-6826`, whose
`DROP_DATA_PATH` points at the now-deleted `Widgets/Data/` and silently returns 0.

### M5. Behaviour parity to preserve at the switch
- `loot_gold_coins` does nothing in the engine; the Loot Manager compensates by whitelisting the model
  (`LootManager.py:138,154,169,441`) and **InvPlus does not**. The new class must make the toggle
  actually work, so this compensation can disappear.
- Keep `GetfilteredLootArray` signature-compatible (M6) and keep calling `is_loot_lock_blocked`.
- The skip-list write-back (`AddItemIDToBlacklist` from `Messaging.py:1692,1713,1742,1756`) is the only
  coupling from the pickup machinery into the class — it must keep working, keyed by **agent id**.

### M6. Callers — change them all, no compatibility patches
**DECIDED.** The dead `multibox_loot` / `allow_unasigned_loot` params are **removed**, and all 20 call
sites are updated in the same change (18 pass the first, 8 the second, by keyword). Likewise the
misspelling is not preserved. No accepted-and-ignored parameters, no facade shims, no deprecated
aliases anywhere: if a caller is wrong for the new API, fix the caller.

### M7. Rollback
Everything new lives in one package plus a rewritten `Lootconfig_src.py`. Reverting = restore that file
from git, delete the package, un-register the settings category / message route, and move the Loot
Manager widget back. Keep it that shape so a bad switch is one revert, not an unpick.

---

## Notes carried over from the reverted attempt

> **Superseded on the numbers.** The counts below came from a merge that used `LootGroups` as the base
> and silently dropped the placeholder-id items. The authoritative catalog facts — 403 vs 395, the
> 388/7/15 reconciliation, the 5 dead names, the ~25 placeholder ids, the 41 missing textures — are in
> **`02 §1` and `§7`**. The *approach* below (merge both, fix the misspellings, keep `drop_info`) stands.

### Data notes for the review pass
The grouping table is the **merge of BOTH legacy catalogs**, not one of them. The old Loot Manager
widget used `modelid_drop_data.json` (403 rows, with `drop_info`); the core library used the separate
`LootGroups` dict (395). Taking either alone loses items — the merge is the point of killing the
duplication. As shipped:

- **11 categories, 52 subgroups, 377 items** — the widget catalog's order/structure, plus anything only
  `LootGroups` had.
- **5 misspellings fixed** (they were dead toggles in the old UI, matching nothing):
  `Curved_Mintaur_Horn`→`Curved_Minotaur_Horn`, `Dregde_Charm`→`Dredge_Charm`,
  `Dregde_Manifesto`→`Dredge_Manifesto`, `Oni_Taloon`→`Oni_Talon`, `Plauge_Idol`→`Plague_Idol`.
- **`drop_info` preserved for 376 items** in `LootDropInfo.json` and shown in the hover tooltip
  ("Dropped from: …"), as the old widget did.
- **27 entries dropped** because their `ModelID` is a placeholder, not a real id (the enum marks them
  *"Dummy modelid's to insure no LootManager Crash — will be changed to correct value"*): Animal_Hide,
  Bleached_Shell, Dark_Claw, Plague_Idol, Vampiric_Fang, … They could never match a real drop. They
  need real ids before they can come back.
- One duplicate remains by nature: model `817` is in Trophies/K and /O because `Oni_Claw` is an enum
  **alias** of `Keen_Oni_Claw`.
- Trophies' 23 subgroups are alphabet buckets (A, B, C…) — preserved as-is, but worth regrouping
  semantically during your review.
- Salvage: armor is intentionally absent (grabbed by rarity, per `01`).

### UI invariant (a regression to not repeat)
The catalog is rendered **two levels deep everywhere** — category → subgroup → items, with all/none at
both levels. An early build flattened each category into a single grid (one wall of 218 trophies);
that is a functional regression versus the old widget and is explicitly not allowed.
