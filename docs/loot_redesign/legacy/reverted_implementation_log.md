# Reverted implementation log — historical record only

**This describes code that no longer exists.** Two implementations were built from `01_class.md` and
both were reverted; the working tree is back at HEAD. Kept only for what it records about the *data* —
catalog defects, placeholder model ids, the dye subsystem — none of which is design.

Not a source of decisions. The plan is `../01_class.md`; the how is `../02_implementation_spec.md`.

---

## Implementation log — REVERTED, kept as a record

> **Everything below describes code that no longer exists.** Two implementations were built from this
> plan and both were reverted; the working tree is back at HEAD. The log is retained because it records
> what was *learned* (the catalog defects, the dye subsystem, the placeholder model ids), not because
> any of it is present. See `02_audit_vs_plan.md` for why it failed and `03_implementation_spec.md`
> for the rule that replaced it.

## Implementation log

*(what is built, and what the build revealed)*

### Step 1 -- package data · DONE

`Py4GWCoreLib/py4gwcorelib_src/item_catalog/` — `catalog.py`, `materials.py`, `dyes.py`,
`nicholas.py`. Package data, versioned with the code; nothing read from the JSON store or from
frenkey's library at runtime.

**What the extraction found — 30 of the 403 catalog rows could never have matched a drop:**

- **12 did not resolve against the `ModelID` enum at all**;
- **18 resolved to placeholder values** written into the enum itself — ids like `1236547896911`,
  far outside the valid range, which no drop can ever carry.

**14 were recovered** by name from the bundled item metadata (10 exact, 4 after correcting misspellings
in the catalog's own text: *Mintaur*→Minotaur, *Dregde*→Dredge, *Fledglin*→Fledgling,
*Taloon*→Talon). Two near-matches were **rejected** as different items: "Bleached Shell"→"Bleached
Skull" and "Kuskale Claw"→"Skale Claw".

**16 remain genuinely unresolvable** — they exist in the scraped wiki data as real trophies with
`model_id: None`, so no source in this repository knows their id. Per the decision they ship in
`UNRESOLVED`, visible as defects rather than as dead rows that look functional.

**Dyes have their own subsystem, and it is not the mods surface.** Two facts, both load-bearing:

- **Every dye shares one model id** — `Vial_Of_Dye` (146). There is no per-colour model id, which is
  why the legacy runtime-generated `ModelID.<Colour>_Dye` entries could never match anything.
- **Identification is by `ItemType.Dye`, and the colour comes from `Item.Dye`** (`Item.py:634-673`),
  which owns dye reads: an item carries a tint and **four** dye channels, and `Item.Dye.GetColor`
  resolves a dyed item's `dye1` first, falling back to a vial's own colour. `Item.Dye.IsColor` tests
  the **item type**, not the model id.

So the model id is documentation, **not** the discriminator — matching on 146 would be fragile and
would also wrongly admit anything else sharing that model. The first implementation used the raw
modifier scan (`Item.GetDyeColor`) and a model-id test; both were replaced by
`item_catalog.dyes.is_dye()` / `color_of()`, which route through `Item.Dye`. Verified 5/5 offline,
including a guard that fails if the raw scan is called at all.

**Nicholas** ported without the global-mutation bug: the schedule is 140 consecutive Mondays, so any
date resolves by modular arithmetic and the shared list is never touched. Verified: wraps forward and
backward, cycle unmutated, and the cache recomputes on exactly a week change or a selection change.

### Step 2 -- shared filtering core · DONE

`Py4GWCoreLib/py4gwcorelib_src/item_filters/` — `model.py` (`Rule`, `ModCriterion`: criteria only, no
outcome, no callables), `matcher.py` (all evaluation, `any_match` / `first_match`), `store.py` (global
shared list). Owned by neither feature.

`mods_all` / `mods_any` mirror `HasAllMods` / `HasAnyMods`. Mod criteria are stored as ints rather than
enum members so they survive serialisation; the matcher compares `int(subtype_of(...))` and uses the
mod's own `better_low` for direction.

### Step 3 -- Loot feature · DONE

`Py4GWCoreLib/py4gwcorelib_src/loot/` — `model.py` (the config class, instantiated twice), `store.py`
(Settings for flat account values, JsonFactory for account id lists and global profiles),
`controller.py` (the `Loot` singleton).

**Verified offline against stubs, 17/17 checks:** each HAS-ANY input sufficient on its own (hand list,
added model, added item id, dye colour, rarity toggle, gold coins); **gold coins honoured from the
toggle and not by writing into any list**; the blacklist vetoing an item wanted by three separate
inputs; map change clearing id-keyed entries while leaving model entries; live never touching stock;
and reset restoring stock exactly.

`GetLootArray` carries `@frame_cache`; both dead parameters are gone.

---

### Step 4 -- Beacons and Recolor & Beacons · DONE

`Py4GWCoreLib/py4gwcorelib_src/recolor_beacons/` — `beacons.py` (pooled, addressable `BeaconPool`),
`model.py` (`MarkingOutcome`, `MarkingConfig`), `store.py`, `controller.py` (the `Marking` singleton),
`config_ui.py`.

Geometry follows the tuned reference exactly, and its state ships as `DEFAULT_PRESET`. Two costs the
reference kept per-process are **per-beacon** here, because a pool holds many at once: the
ground-profile cache (a single shared one would be evicted every frame) and the emitter handles.

**Verified offline, 14/14 checks:** alpha carrying the mode (solid / fade / **blank**), the default
preset matching the tuned purple gradient, geometry building without a renderer, and the pool reusing
slots across churn rather than reallocating.

**Still requires the Native rebuild** for `set_item_agent_colors`.

### Step 5 -- UI · DONE

`loot/config_ui.py`, `loot/quick_access.py`, `recolor_beacons/config_ui.py`, plus a new **Items**
category in `system_settings/model.py` holding both features as subcategories, built independently in
`system_settings/config_ui.py` so a failure in one still leaves the other usable.

Quick access is structure A: top tabs, one category per tab, collapsible headers (with `###` ids, since
their labels carry counts), two views with the cost warning in both surfaces, contextual search, the
live label, resizable from 300 x 300.

### Step 5a -- wiring the quick access · DONE *(missed on the first pass)*

The quick-access module existed but **nothing called it and nothing could open it**, so it never
appeared in game. Three things were missing, all of them specified:

1. **A host.** `Widgets/System/System Settings.py` is the always-on widget; it now boots both
   features (independently, since they are standalone) and calls `quick_access.draw()` every frame.
   The quick access is deliberately **not** tied to the settings window -- it is the surface the user
   keeps open while playing.
2. **A way to configure it.** A **Quick Access tab** in the Loot section: open/close, the display-mode
   toggle with its cost warning, which surfaces appear, and their order.
3. **Persistence.** Per the layout, `[quick access]` in the account INI holds `surfaces`,
   `icon_view`, `window_open` and `live_window_open` -- flat account values, so `Settings` rather
   than a document.

   **Whether the window is open is a setting, not session state.** The first cut left it in memory,
   which forced the user into System Settings to re-open it every session. It now persists, including
   when closed via the window's own X, so a quick access left open comes back open.

   **One display mode, not two.** The settings section had grown its own per-group icon/name toggle,
   in memory and separate from the quick access's. That contradicted the decision that the display
   mode is a single setting reachable from both surfaces; the settings section now reads and writes
   the same persisted value.

   Verified 6/6 across a simulated restart: defaults on a fresh install, then surfaces, view mode and
   open state all surviving a re-read.

The new packages were also added to the widget's dev-reload purge list, so edits are picked up on
reload rather than being masked by `sys.modules` caching.

*Also:* `text_disabled` is too dim to read; secondary text throughout these three UI modules uses
`text_colored` with a mid gray instead.

### Step 5b -- Materials vs "Salvages to" · DONE

An ImGui *"2 visible items with conflicting id"* error surfaced the real gap. The surface list was
`["Rarities", "Materials", "Dyes", "Nicholas"] + catalog groups`, and **"Materials" is also a catalog
group** -- so it was listed twice, rendering two checkboxes with one id and two identically named tabs.

The fix is not just deduplication: **they are two different things, and both are needed.**

| surface | means |
|---|---|
| **Materials** | want the material itself **when it drops** |
| **Salvages to** | want any item that **breaks down into** that material |

The second did not exist. Added as `LootConfig.salvage_target_ids` -- membership, like the other hand
lists -- threaded through the config copy, the diff, persistence, and `wants()` as another HAS-ANY
input, with a tab in both the quick access and the settings section.

**The bundled salvage data does not gate the choice.** It records 34 of the 36 materials as salvage
outputs, and the first cut hid the other five. That was wrong: the dataset is incomplete -- items do
salvage into materials it does not record -- so it is evidence, not an authority on what is possible.
**All 36 are selectable**; the data informs the tooltip (*"N known items salvage into this"*, or that
none are recorded) and nothing more. Bolt of Damask, Deldrimor Steel Ingot, Elonian Leather Square,
Glob of Ectoplasm and Obsidian Shard are reachable again.

**Quick selection per subgroup.** Every subgroup carries **all** / **clear** buttons -- catalog
subgroups, materials, salvage targets and dyes, in both the quick access and the settings section.

The surface list is now deduplicated as well, so a catalog group can never collide with a
purpose-built surface again. Verified: 15 unique surfaces, no repeats.

### Step 6 & 7 -- migration · DONE

- **20 call sites** retrofitted to `Loot().GetLootArray(distance)`; both dead parameters gone. No
  caller of the old name remains.
- **Failure reporting routed through the class**: `Messaging.py` (4 direct blacklist writes) and
  `routines_src/yield_src/items.py` (both failure paths) now call `report_failed`.
- **Four private skip-lists removed** — `DervFeatherFarm`, `DervCOFFarm`, `DervDustFarm`,
  `VaettirMarksMods`.
- **Destructive bot verbs removed** at both layers (`helpers_src/Items.py`,
  `subclases_src/ITEMS_src.py`), replaced by an additive surface: add model, add item id, blacklist
  model, report failure, reset. Direct `ClearItemIDBlacklist` callers now use `reset_live()`.
- **Loot Manager retired** to `Legacy code and tests/loot_manager_retired/`, with a README recording
  which behaviours deliberately did not carry forward.
- **LootEx migrated, not severed**: its `AddCustomItemCheck` hook is gone; it now contributes model ids
  as data and resets live when its run ends.

Everything above is Pyright-clean, and every touched file compiles.

---
