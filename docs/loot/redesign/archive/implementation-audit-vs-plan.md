# Audit — the REVERTED implementation vs. the plan

**Historical.** The implementation audited here was deleted; the tree is back at HEAD. Retained as the
evidence base for `../implementation-spec.md` — it is the record of *which decisions leaked into
the implementation phase*, which is the failure the spec exists to prevent.

---


Every decision in `class.md` checked against the code. Verified by inspection and by targeted
searches, not from memory. Three categories: **implemented as planned**, **missing**, **implemented
differently**.

---

## 1. Implemented as planned

| decision | where | verified |
|---|---|---|
| Catalogs are package data, never JSON | `system_settings/loot_filters/catalog.py` | 387 rows + 16 `UNRESOLVED`; nothing read from the JSON store |
| Shared core owned by neither feature | `item_filters/` | neither feature imports the other |
| `Rule` is criteria only, no outcome, no callables | `item_filters/model.py` | no callable fields; outcomes live in each feature |
| Blacklist = absolute veto, everything else HAS-ANY | `loot/controller.py:201` | 17/17 offline checks |
| stock / live are two instances of one class | `loot/model.py`, `controller.py` | `copy()`, `reset_live()`, `diff()` |
| Scripts change live only, never stock | `controller.py` | every mutator writes `self.live` |
| Gold coins honoured from the toggle, no list injection | `controller.py` `_is_gold_coin` | verified |
| Agent/item ids cleared on map change, never persisted | `model.clear_session_ids`, `store.py` | verified |
| Loot lock read-only | `controller._candidates` | `is_loot_lock_blocked` consulted only |
| `GetLootArray(distance)`, dead params gone | `controller.py:280` | 20 callers retrofitted |
| Query cached per frame | `@frame_cache` | applied |
| Callback registered + declared to the perf monitor | `controller.register` | `ProfilingRegistry().register` |
| Persistence split (option b) | `loot/store.py`, `recolor_beacons/store.py` | Settings=flat, JsonFactory=structured |
| Dyes via `ItemType.Dye` + `Item.Dye` | `system_settings/loot_filters/dyes.py` | 5/5 checks, raw scan guarded against |
| Marking: one bulk `(agent_id, colour)` push | `recolor_beacons/controller._apply` | `SetItemColors` |
| BLANK as a first-class outcome | `model.MarkingOutcome.argb` | 14/14 checks |
| Beacons pooled, addressable, user-budgeted | `beacons.BeaconPool` | slot reuse verified |
| Nicholas: relative + pinned, several at once, cached | `system_settings/loot_filters/nicholas.py` | wrap + cache verified |
| Materials **and** "Salvages to" as distinct surfaces | `loot/*` | both present |
| Migration: bypasses removed, LootManager retired, LootEx migrated | repo-wide | 0 old-name callers, 0 private skip-lists |
| Filter editor embedded by **both** features | `item_filters/config_ui.py` | both `add_sections` embed it |
| UI shell: tabs, one category per tab, `###` headers, two views, contextual search, live label in both surfaces, 300×300 | `loot/quick_access.py` | present |

---

## 2. MISSING — in the plan, absent from the code

### 2.1 Profiles have no UI whatsoever — **the largest gap**

The plan devotes a whole section to profiles: global shareable definitions, the user composes them,
an account selects one, a script may switch it.

**Reality:** `store.load_profiles()` / `save_profiles()` exist and `Loot.use_profile()` exists, but
**`save_profiles` is never called from anywhere** and there is no UI to create, name, compose,
rename, delete or select a profile. The Recolor & Beacons feature has a `profile` field and **no
profile storage at all**.

Effect: profiles are unreachable. The feature is inert.

### 2.2 Beacon presets cannot be edited

The plan: *"The reference config is the default, not the only option… the user must be able to
configure their own — every part of the anatomy below is exposed, not baked in."*

**Reality:** the UI offers a **combo to pick a preset** and nothing else. No editing of beam shape,
gradient colours, glow, height, ground disc, rings, pulse, or the emitter list. **`save_presets()` is
never called.** Users get exactly one shipped preset.

### 2.3 `mods_any` — the OR half — is not editable

The plan settled composition as AND *and* OR. `Rule.mods_any` exists and the matcher honours it, but
the editor only edits `mods_all`. The OR half is unreachable from the UI.

### 2.4 Nicholas pinned dates are unreachable

The plan: *"from settings the user controls any cycle and can pick any date"*. The model supports it
(`NicholasSelection.pinned`), but **no UI constructs one**. Only relative offsets (this week, next
week, in two weeks) are exposed. There is no date picker and no cycle browser.

### 2.5 The script API is narrower than the plan

The plan: a script may **change any switch** and **use any profile**. The class supports both
(`set_rarity`, `use_profile`), but the bot-facing helper exposes only: add model, add item id,
blacklist model, report failure, reset. **`use_profile` and `set_rarity` are not reachable from the
bot API.**

### 2.6 The icon view is not textures

The plan: *"the most compact way of presenting the data is a grid of textured icons"*, *"assume all
textures are resolved"*. **Reality:** the grid renders buttons showing the **first two letters of the
item name**. The tooltip is correct; the icon is a placeholder. The whole cost/benefit argument for
two view modes does not currently apply, because the expensive mode is not expensive — or useful.

### 2.7 Quick-access customisation is per-category, not per-entry

The plan: *"the user configures what goes in it… add what they want"*. **Reality:** whole surfaces
only. A user cannot assemble a quick access of, say, six specific trophies.

### 2.8 Model-id and item-type criteria are raw integer text boxes

Same failure class as the mods box that was just corrected: `model_ids`, `item_types`, `dye_colors`
and `salvages_into` are typed as comma-separated integers. There is no picker from the catalog, the
`ItemType` enum, or the dye/material lists — all of which exist as package data.

### 2.9 The Loot feature has no enable/disable switch in the UI

`Loot.enabled` exists and is checked in the pass, but nothing exposes it. Marking has one; loot does
not.

---

## 3. Implemented differently from the plan

### 3.1 Two competing orderings for marking

The plan: the **user's filter order** resolves the colour and the beacon preset, and `first_match`
was built in the shared matcher for exactly that.

**Reality:** `Marking.resolve` iterates `self.live.outcomes` — the marking rule list's own order —
and hand-rolls the loop, using neither `first_match` nor `any_match`. So marking order is the
*outcome list* order while loot uses the *filter pool* order (`filter_store.ordered`). Two orderings
now exist where the plan described one.

### 3.2 `filter_ids` duplicates what a profile is

`LootConfig.filter_ids` is an ad-hoc per-account list of active filters — effectively an unnamed
profile. With the real profile mechanism unused (2.1), there are two overlapping concepts.

### 3.3 The Materials catalog group is reachable by two paths

The catalog's own `Materials` group (36 rows) is editable in the settings **Catalog** tab *and* in the
**Materials** tab, both writing `enabled_model_ids`. Consistent, but duplicated.

### 3.4 The marking UI reaches into a private attribute

`config_ui.draw_beacons` calls `marking._pool.available()`.

---

## 4. Not implemented because it is blocked

**The Native rebuild.** `SetItemAgentColors` exists in header, implementation, binding, stub and
wrapper, but the DLL has to be rebuilt before item recolouring or beacons can run at all.

---

## 5. Honest summary

The **decision layer** — resolution order, live/stock, persistence, catalogs, the standalone split,
migration — is implemented and verified.

The **authoring layer** is where the gaps are, and they share one shape: *the data model supports the
decision, the UI does not expose it.* Profiles, beacon presets, `mods_any`, pinned Nicholas dates,
per-entry quick access, and textured icons are all cases where the plan was implemented underneath and
left unreachable above. That is why the system can look complete in code review and feel absent in
use.
