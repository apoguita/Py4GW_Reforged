# Loot Config — Redesign

Replaces the current Loot Manager class with one that is easy to handle. Written from how looting
actually works (audit in `02_how_it_works_today.md`). Plain language on purpose.

## What this class does — and only this

- **Watches the ground items** and produces the **loot array** — the list of items worth grabbing.
- **Decides the marking** — which items/categories get a recoloured label and/or a light beacon, and
  applies it.

**It does NOT** pick items up, decide *when* it is safe to loot, or handle salvage/vendor/inventory —
those are involved and already handled by other code. It keeps the one method everything already calls
to get the array, so nothing downstream changes.

---

## The settled design is settled

Research exists to **serve** the decisions below, never to reopen them. A newly-discovered capability is
a candidate *condition* for the Filters, not a reason to restructure a surface. In particular:

- **The hand List stays.** Trophies, consumables, tonics and event items are tracked **by identity**,
  individually and as whole groups. The fact that an item *also* carries a type or a value does not
  replace the List — "all trophies" and "these three trophies" are both required, and the List is what
  makes the second one possible.
- **No invented thresholds.** Numbers like "worth ≥ 100g" are examples of what a *user* may type into a
  condition. They are not defaults, not design, and not to be written into the spec.
- **No opinionated meta-filters.** Things like "max damage" are not a paradigm for weapon selection; at
  most they are one condition among others, and only if the user asks for them. Do not elevate a helper
  found in the codebase into a design concept.
- Anything that would change a settled decision goes to the owner as a question, not into the doc.

---

## HARD RULE — scripts may never change your settings

**Only the user, through the UI, may change the saved loot config. Nothing a script does is ever
persisted.** This is one of the core reasons for the rework: today any bot, routine or widget can reach
into the shared singleton and permanently rewrite the user's loot policy.

**This happens today, and it is data loss.** `Widgets/Automation/Bots/Missions/Dungeons/SoO.py:2446,2459`,
`Frog Scepter bot.py:2260,2273`, `routines_src/behaviourtrees_src/items.py:946` and
`Bots/Example Bots/VaettirBot (Sequential).py:490,493` all mutate the same singleton that the Loot
Manager then persists to `loot_config.json` (`LootManager.py:71-74`). Run a dungeon bot and its
blacklist edits silently become your permanent configuration, with no undo.

### Two layers, and only one of them is saved

| layer | who writes it | lifetime | persisted |
|---|---|---|---|
| **Permanent policy** — the List, materials, filters, rarities, marking | **the user, via the editor / quick window only** | until the user changes it | **yes** |
| **Transient (run) layer** — everything a script does while operating: force-loot this model, ignore that drop, skip an unreachable item | scripts, bots, routines, the pickup machinery | the session / map instance | **never** |

**The decision is the union of both** — a script can *add* to what gets looted for the duration of its
run, and can *exclude* for the duration of its run, but it cannot edit what the user saved.

### Consequences for the API (non-negotiable)
- **The script-facing surface contains no persistent mutation at all.** Not "discouraged" — not
  present. A bot must not be *able* to write the saved config, so this cannot be a convention that
  erodes.
- Every script-facing add/deny/skip writes to the **transient layer** and is cleared automatically
  (map change / run end). That includes bot "blacklisting" — a run-scoped exclusion, **not** a
  permanent one.
- The persistent surface is reachable only from the config/UI side of the class.
- A bot therefore needs no snapshot/restore ritual: it cannot damage anything to begin with.

### And there must be NO bypasses
The rule is worthless if code can simply route around the class. **Every loot decision in the repo goes
through this class** — no private loot arrays, no hand-rolled "which items should I grab" helpers, no
parallel skip-lists, no second filter engine. Known bypasses today (each exists *because* the class was
inadequate, and each must be removed and routed through the new one):
- `Bots/marks_coding_corner/utils/loot_utils.py:77-110` — its own `get_valid_loot_array`, bypassing
  `LootConfig` completely, with a hand-coded "black and white dyes only" rule because dye filtering
  does not work.
- `Bots/marks_coding_corner/DervFeatherFarm.py` / `VaettirMarksMods.py` — private `item_id_blacklist`
  lists, kept because the class offers no failed-pickup feedback.
- *(NOT a bypass — corrected)* `routines_src/behaviourtrees_src/items.py:958-1041` calls
  `LootConfig().GetfilteredLootArray()` at `:983` and `:1029`. It runs its own **pickup** loop
  (target / interact / lock), which is exactly the intended split: this class decides, others pick
  up. It is a legitimate consumer and stays.
- Bots carrying their own `LootConfigclass` of UI booleans (`VaettirBot`, `Examples/Loot_reader.py`).
- `Sources/frenkeyLib` — a whole parallel loot engine (out of scope for the rewrite, but it must not be
  the reason the class stays weak).

A bypass is a bug report about this class: whatever the bypass does, the class must be able to do.

---

## How looting actually works (the workflow this class serves)

*Owner's description of the real activity. Everything below in this doc exists to serve this; if a
design decision does not make sense against this section, the design is wrong.*

**Drops and ownership.** Items drop on the ground. A drop is either **assigned to us**, assigned to
**someone else**, or assigned to **no one**. We may only take **ours or unassigned** — everything else
is off-limits before any preference applies.

**Rarity: 6 tiers, 5 that matter.** Gray and white behave identically (treat as *white*), then blue,
purple, gold, green. **The overwhelming majority of drops are white**, so the universe of whites one
*might* want is enormous — that is precisely why hand lists exist. Trying to describe those wants as
individual rules would be unmanageable.

**What the tiers are for.**
- **Purple and better** are weapons and armour carrying **runes / mods**. An **unidentified** item does
  **not** expose all its mods — only basic data from some of them. This is why the filter can only rely
  on the inherent facts (see the Filters section), never on prefix/suffix/inscription upgrades.
- Mods are extracted with an **expert kit**; a **lesser kit** instead breaks the item down into
  **materials**.
- **Most whites also recycle into materials.**

**Trophies.** Some whites are **trophies** — they serve a purpose, so we actively seek them. There are a
lot of them, and we want to track them **individually or as a whole group**. This is the reason a hand
list is the right tool, not a failure of the filters. Trophies can also be recycled into materials if
desired.

**Other drop kinds we do describe:** consumables, event items, tonics, and similar — these are named in
the config too.

**What we deliberately do NOT enumerate:** every salvageable white that is *not* a trophy. Those are
only worth vendoring or turning into materials, so they are reached by a *property* (rarity, or
"salvages into X"), never by a hand-typed list.

**Nick's items** are a **scheduled rotation of trophies** — a dated subset we want to track for the
current week. The Loot Manager already does this, badly.

**Consequence for the design:** the surfaces below are not arbitrary. Rarity is the broad switch for
"all whites / all golds"; hand lists exist because the trophy/consumable/event set is huge and
identity-based; materials exist so the un-enumerated salvage whites are reachable by their *output*;
filters exist for everything describable by a property. They add together because a real loot decision
is "any of these reasons is enough".

---

## Two separate systems for "what to grab" — they stay separate

There are two independent ways to say "I want this," and they are kept distinct in **both the code and
the menu**. A hand-picked specific item and a property filter are different things: they need to be
told apart, and they need to be shown differently (especially for quick access). They are never merged.

### System 1 — The List (hand-picked specific items)

> **Requirement that overrides everything else here: it must be EASY.** Adding an item to a list must
> not be cumbersome, and **there must be no separate step to "register" the item anywhere** — no
> catalog entry to author, no second file to keep in sync, no name/id typed twice. Both existing UIs
> fail this (that is *why* they are being replaced, not just how they look): the Loot Manager needs an
> entry hand-written into `modelid_drop_data.json` (name + model_id + group + subgroup + drop_info)
> before an item can even be ticked, and InvPlus needs it hand-added to the `LootGroups` dict. That
> double-registration is the source of the half-added items, the 5 dead misspellings and the drift
> between the two catalogs. **Neither catalog is a good design to inherit — only their data is worth
> salvaging.**
>
> **The list is NOT "the whole `ModelID` enum".** That enum is ~1069 members covering every model in
> the game — most are not lootable, ~28 carry placeholder ids that can never match a drop, and putting
> it on screen would be useless. A **curated set is unavoidable**. What must go away is the *cost* of
> curating it: today adding one trophy means authoring a 5-field row in a JSON **and** a separate entry
> in a Python dict. The target is **one entry in one place** — an id under a group — with name and icon
> derived from the enum and nothing else to keep in sync.

The curated items you want **by identity**, that no property describes:
- Trophies, consumables, tonics, event items.
- Organised in **two levels — category → subgroup → items** (Keys → Core/Prophecies/Factions/
  Nightfall, Materials → Common/Rare, Tomes → Normal/Elite, Trophies → A–W). **The subgroups are
  never flattened away**, anywhere they are shown (editor and quick window): a category rendered as
  one long list is exactly what the catalog exists to prevent. You tick an item, a subgroup, or a
  whole category.
- **The data shape: a plain dict / JSON of ids — nothing else.** (Owner's call, and it is the whole
  point of "easy to handle".)

  ```
  { "Trophies": { "A": [id, id, …], "B": [ … ] },
    "Keys":     { "Core Keys": [ … ], … } }
  ```

  **Adding an item = appending one id to one list.** No 5-field row, no name to type, no lookup table
  to keep in sync. `name` and icon are **derived** from `ModelID` + the texture folder at display time.
  This is exactly the shape `LootGroups` already has — the problem was never that shape, it was having
  **two** catalogs and the Loot Manager's 5-field rows on top of it.

  The legacy catalogs are **salvageable data, not the design**: `modelid_drop_data.json` (403, what the
  Loot Manager reads, `LootManager.py:44`) and `LootGroups` (395, what InvPlus reads) are merged **once**
  into this one dict — fixing the 5 dead names and deciding the ~25 placeholder-id items on the way
  (`02 §1`) — and then both are retired.

- **`drop_info` is dropped — deliberately, not lost.** The old catalog carried a "Dropped from: …"
  string per entry (`LootManager.py:613-619`), but it is not wanted: it is not worth the field, and it
  is one of the five per-row fields whose upkeep is exactly what makes the current catalog cumbersome.
  It is **not** to be "restored" later as a fix. The tooltip shows the derived name (and salvage output
  where we have it); nothing else.
- **Textures are NOT guaranteed.** `get_texture_for_model` never fails, but **41 of 403 items have no
  texture file** and render the `0-File_Not_found.png` sentinel — including *every* Elite Tome, *every*
  Passage Scroll, *every* Map Piece and 7 of 8 Quest-Item Keys (`02 §7`). A texture-only grid would show
  41 identical blank tiles, so the grid needs a name/label fallback.
- Every item icon shows a **hover tooltip with its data**.
- **Nick's rotating items — CONSUME the Calendar's handling, do not reimplement it.**
  `Widgets/Guild Wars/Calendar.py:100` already exposes **`get_nicholas_for_day(day: date) -> dict | None`**,
  which normalises to Monday, rolls the cycle on demand (`expand_cycle_if_needed`, `:66-97`) and returns
  the entry — including a real **`model_id`**. The loot class asks it for a date and reads `model_id`.
  No date maths, no cycle rotation, no name-matching, and no choosing between datasets on our side.
  (The Loot Manager's own `Nick_cycles.json` path matches by display *name* and silently loses 20 of 137
  items — that is exactly the reimplementation we are not repeating.)
  **Decided: move the Nicholas handling into the library where it belongs** — the cycle logic
  (`get_nicholas_for_day`, `expand_cycle_if_needed`) moves out of the Calendar *widget* into
  `Py4GWCoreLib` next to the data it operates on (`NICHOLAS_CYCLE` already lives in
  `enums_src/Calendar_enums.py`). Calendar then consumes the library helper instead of owning it, and
  the loot class consumes the same helper. **One implementation, in the library; two consumers.** No
  widget-imports-widget, and no third copy of the date maths.
  In the full editor the user controls **any cycle and any date**; in the quick-access window they just
  toggle **the current week's** items.
- This is the "I want THESE exact things" surface. It is a big, searchable grid of icons.

### System 2 — The Filters (property rules)
The rules that describe items **by quality**, so you never enumerate. This is the "I want anything that
IS like this" surface: a small editor of rules.

**It is the item-mod system, reused.** `Item.Mods` already solves exactly this problem, so a Filter is
shaped like a mod query — same structure, same value rules:

| item mods (`Item.py`) | loot filters |
|---|---|
| `HasMod(item_id, mod, *values)` — one condition | **one condition** = `(key, *values)` |
| `HasAllMods(item_id, modlist)` — **every entry must match** | **a Filter = a list of conditions, all must match** |
| entry = `mod` \| `(mod, *values)` | condition = `key` \| `(key, *values)` |

- **A Filter** = a name + an on/off + **a list of conditions, all of which must match** (the AND is
  `HasAllMods`). Different Filters are independent (any one matching is enough — §Putting them
  together).
- **A condition's values are type-routed exactly as `HasMod` does it** (`Item.py:127-165`):
  - an **enum** narrows the subtype — `Attribute.Marksmanship`, `DamageType.Fire`, `ItemType.Bow`,
    `DyeColor.Black`;
  - a **number** means **"that value or better"**, and the direction comes from the key's own metadata
    (`better_low` in `mods_core._Def`) — requirement is lower-is-better, damage/armor/worth are
    higher-is-better. No min/max pairs, no "or better" checkbox;
  - **multi-value keys match positionally** (e.g. Damage's `[min, max]`), same as `_values_match`;
  - **no value** = presence only ("has this mod at all").
- **Keys are of two kinds, written identically:**
  - a **mod** (`ModId`) → evaluated by `Item.Mods.HasMod`;
  - an **item fact** (`rarity`, `type`, `model`, `worth`, `quantity`, `dye`, `salvages_into`) →
    evaluated by its own reader (§`02`). The fact keys get the **same small metadata table** the mods
    have (value type, direction, subtype enum), so "or better" and subtypes work the same for both.
- **No callables.** `HasMod` accepts a predicate as an escape hatch; **Filters do not** — a filter must
  save as plain data and must never be able to override a decision from code.

**On disk** a Filter is just that list, e.g.
`{"name":"Gold Star Bows","on":true,"when":[["rarity","Gold"],["type","Bow"],["model","Star_Bow"],["requirement","Marksmanship",9]]}`

### Rarity — the broad quick switches
White / blue / purple / gold / green (+ gold coins) as simple on/off toggles — the everyday
quick-access. The broadest stroke: turn "white" on and every white is in, no list or filter needed.

### Materials — a tick-list, like the List, but matched by salvage output
The crafting materials (Bone, Iron Ingot, …) shown **the same way the trophies are** — a textured grid
or a checkbox table — where you tick the materials you want. An item is grabbed if it **salvages into
any ticked material**. It looks like the List (a tick-list of things) but behaves like a filter (it
matches on a property), which is why it is its own surface. Needs the salvage table (below).

### Putting them together
An eligible item (ours or unassigned, not locked by another account) is grabbed if **any** of these
says yes: a **rarity** switch it matches is on, **or** it is ticked in the **List**, **or** it salvages
into a ticked **Material**, **or** it matches a **Filter**. Four surfaces, added together, never merged.
Not being on the List does not mean unwanted — rarity, a material, or a filter can still bring it in.

## Marking — its own separate layer, driven by a callback

Recolour and beacon are driven **by criteria too** (a rarity, an item type, one specific item, or a
name match), but **independent of pickup**: you can mark without grabbing, and grab without marking.

*Marking a whole **group** (e.g. "all Trophies") is supported in the editor, but the native table has no
concept of our groups — so a group rule is **expanded into one model rule per item in that group** when
it is pushed. Purely an implementation detail; the user just picks the group.*

### Recolour — we push RULES, the game applies them (no per-frame scan)

**Items work differently from agents, and this is the important part.** For agents, the Python
controller scans the agent array every frame and pushes explicit `{agent_id: colour}` pairs. **Items do
not work that way.** The native side keeps its own item rule table and does the matching itself, inside
a detour on the game's own item-label function (`Detour_ItemGetTextData` →
`AgentRecolor::OnItemGetTextData`, `src/GW/agent_recolor/agent_recolor.cpp:99` and **`:640`**):

- We **set rules once, when the config changes** — `set_item_rarity_color(rarity, argb)`,
  `set_item_type_color`, `set_item_model_color`, `set_item_name_color` (plus `set_item_id_color` /
  `set_item_agent_color` to target one specific item instance). Rules are re-snapshotted natively only
  on mutation (`RebuildItemSnapshotLocked`), never on a timer.
- Whenever the game draws an item's label, the detour looks the item up against those rules and
  colours it. **No Python loop over ground items, no per-frame push, nothing to throttle.**
- **Precedence is native and fixed:** `agent_id > item_id > model_id > name > type > rarity`, first
  match wins (`:661-700`). Matching is lock-free; fetching the snapshot pointer takes one brief mutex
  (`:644-648`).
- **Alpha is the fade/hide channel:** `0xFF` solid, mid values dim, and **`0x00` blanks the label
  entirely** (`:703-707`).

**Three preconditions that are easy to miss:**
1. **Double-gated** — item recolour needs **both** `master_enable()` (`:801-802`) *and* `item_enable()`
   (checked first thing, `:641`). Setting rules alone does nothing.
2. **Not always true-RGB** — until an item's name decodes (async, a frame or two per item kind) the
   colour falls back to one of GW's ~7 palette colours (`PyAgentRecolor.pyi:14-19`).
3. **The model / name / type / rarity tiers silently no-op** if `GetItemById` fails (`:669,676`); only
   the agent_id and item_id tiers work without a resolved item. Name rules are lowercased substrings
   matched in **insertion order**.

**What this means for the design:** marking rules are **keyed by what the native table understands** —
**six keys**: rarity, item type, model, name substring, plus the two instance keys item_id and agent_id.
That is the vocabulary you asked for ("recolour a special item, or a whole category"), which is why the
native was built with those keys. Marking rules are therefore **not** the same thing as the
multi-condition Filters of System 2, and **priority is not ours to order — the native precedence above
decides the winner** (use a narrower key to beat a broader one).

### Beacon — entirely ours to draw
The game engine draws **no** beacon; it only recolours the name label. So the beacon is our own 3D
render and *is* a per-frame pass: each frame, take the ground items matching a beacon rule, cap to the
nearest few (a beacon is expensive), and draw.

**Which file to use: `light_beacon.py`.** It is the tested one — its `state` defaults (`:63-94`) are the
**configured purple-drop preset**, i.e. the look that was actually tried and approved. That preset is
the point; do not substitute a different renderer and re-tune colours.

Two mechanical facts to handle when lifting it (they do not change the choice): it keeps its config in
module globals (`state` `:63`, `_emitters` `:27`, `_profile_cache` `:171`) and draws **one** beacon per
call at one position, so drawing the nearest N means calling it per position (and giving the ground
cache a per-position key); and it runs native calls at import (`:22-23`), which must move into an
init/draw path. `loot_beam.py` is a separate, untested experiment — reference only.

**Missing pieces on our side:** expose the **item** recolour functions on the Python wrapper — today
`AgentRecolor.py` has no item setters at all, though `MasterEnable`/`MasterDisable`/`ClearAllRules`
already do affect items — and lift a beacon renderer. **Nothing in production drives either** (the only
existing callers are a test harness and the demo, and the demo bypasses the wrapper with a direct
`import PyAgentRecolor`).

## Saves itself — global config, per-account toggles

**How `agent_recolor` actually does it** (verified — the earlier claim here was wrong): it uses
**`Settings` for BOTH scopes on ONE `.ini` document** — `Settings("Widgets/System/Agent Recolor.ini",
"global")` and `Settings(..., "account")` (`agent_recolor/store.py:20,23-38`). The rule list is
`json.dumps`'d into a **single key** (`[rules] list`, `:42-52`); the toggles are plain bools in
`[general]` (`:77-91`). **It never imports `JsonFactory`.** And `name_obfuscation` is **global-only**
(`store.py:14,21`) — it is *not* an example of the split at all.

Our split (same shape, structured data may justify `JsonFactory` for the global half — an open call):
- **Global** (shared across all accounts on the machine): the **common data and the rules** — the List,
  the Filters, the recolour/beacon rules.
- **Per-account**: the **local settings and toggles** — master on/off, which rarities are on, and each
  account's quick-access customisation.

Stored through the sanctioned jailed store (`JsonFactory` global + `Settings` account) and loaded by
the class itself — no caller-owned save/load like today.

**Transitional values are runtime-only and are NEVER saved.** Anything added at runtime — a bot adding
a model mid-run, the picker's skip-list of items it couldn't reach — lives in memory for that session
only and never touches the saved loot list. That is what makes it transitional. (Item ids are per
instance anyway.)

## It owns the system — it is not a facade
**The new class TAKES OWNERSHIP of the loot singleton.** It *is* the system: the process-wide loot
authority that everything talks to. It is not a wrapper over `LootConfig`, not a facade preserving an
old surface, and there is no legacy object left underneath. `Lootconfig_src.py` as it exists today is
replaced, not adapted.

Callers still ask it for the loot array and still own the *when* and the *walking* — but they are
updated to the new API where it differs. Old surface is not preserved for its own sake.

**Deprecated options are removed, and the callers are changed.** `multibox_loot` /
`allow_unasigned_loot` are no-ops (the leader/follower block is a triple-quoted string,
`Lootconfig_src.py:777-787`). They are **deleted**, and all 20 call sites are updated in the same change
(18 pass the first, 8 the second, by keyword; the misspelling is not preserved). **No compatibility
patches** — no ignored params, no shims, no aliases.

**The loot lock must still be consulted by the new class.** Contention is *posted* by the grabbers, but
`GetfilteredLootArray` **itself calls `is_loot_lock_blocked`** (`Lootconfig_src.py:717,729`) for
unassigned items. Dropping that call silently removes cross-account contention from the filter.

## Cross-account rule updates (messaging)
The config is global — one shared set — so the rules already travel via the shared file, but the other
accounts don't *know* it changed. So when one account edits the rules, it **sends a message to the other
accounts to reload**, and each account's loot module re-reads the shared rules live. This uses the
messaging system the same way `MerchantRules` does: a command routed by `Widgets/System/Messaging.py`
(which only routes — the loot module owns the reload). This is the only multibox concern that belongs to
this class.

## Materials data — two separate things (don't confuse them)
1. **The material list** (which materials exist, to pick from) — **we already have this:** `MaterialMap`
   in `Py4GWCoreLib/enums_src/Item_enums.py:267` (`ModelID → name`: Bone, Iron Ingot, Amber Chunk, …).
   No gap — the "materials" filter's picker uses it. (Frenkey's `LootEx/data/materials.json` is just a
   scraped copy of the same fixed ~30–40-material set; not needed.)
2. **The per-item salvage mapping** (which materials a *given item* yields) — **this we do not have.**
   The client never exposes it: all 45 `PyItem` fields were checked and none names a material; the only
   salvage entry points are actions. The two readers that DO exist are **`Item.Type.IsMaterial`**
   (`Item.py:564`, "is this item itself a material") and **`Item.Usage.IsMaterialSalvageable`**
   (`Item.py:600`, a bare yes/no) — **note: NOT `Item.Properties.*`, which has no salvage member.**
   The **common** material is whatever the item is *made of* (cloth robes → cloth, wooden branch →
   wood), a per-model fact, so it must come from data. The only source is frenkey's scraped
   `items.json` (keyed item-type → model-id, each with `common_salvage`/`rare_salvage` = the material
   ModelIDs; e.g. Abbot's Robes → common Bolt of Cloth, rare Bolt of Linen/Silk; amounts unscraped).
   **We extract only the clean minimal table** — `model_id → { common: [material ModelID], rare:
   [material ModelID] }`, dropping all the names/descriptions/wiki/amount noise — stored our own way.
   With `MaterialMap` (id→name) that answers both directions ("does item X give bone" and, inverted,
   "which items give bone"). **"Salvages into materials (any)" already works** with no table via
   `Item.Properties.IsMaterialSalvageable`.

**Decided: build the clean table** ("any material" is useless — nearly every drop salvages into
*something*). With it, materials become a **toggleable list, textured and tabled the same as the
trophies** (§ the List's two view modes): you tick the materials you want (Bone, Iron, …), and an item
is grabbed if it salvages into **any ticked material**. It's a fourth pickup surface, list-style in the
UI, salvage-filter in behaviour.

**Coverage is enough.** Frenkey's data covers ~2,000 items — the white salvage items, trophies, and
weapons, i.e. exactly the things you'd filter by material. **Armor is intentionally left uncovered:**
you grab armor by rarity, never by "salvages into cloth", so its missing salvage data doesn't matter.
If any gap ever needs filling, the source is the wiki's **"Contains \<material\>"** category pages
(e.g. `Contains_hide`) — the inverse index of the same facts, which frenkey already links per item
(`wiki_url`).

---

## The menu — full editor in System Settings + a compact pop-up

> **The existing features are fine.** This is not a feature redesign — the rework is the *class* and
> the *data*, plus modernising the presentation. Keep what the current menus do; change how it looks
> and how the data behind it is maintained.
>
> **Presentation to follow: Inventory+'s grid**, not the Loot Manager's list. The texture grid /
> checkbox cells are the preferred surface (`InvPlus/LootModule.py:106-136` — 3-column table,
> `image_toggle_button` 48×48, wrapped label); the Loot Manager's `tree_node` → checkbox rows
> (`LootManager.py:572-622`) is the crude one being left behind. Everything else about the Loot
> Manager's *functionality* — rarity toggles, Nick, select/deselect all, the viewers — stays.

The class is reworked to live in **System Settings**, the same way `agent_recolor` / `name_obfuscation`
do: its own category, built from `model.py` / `store.py` / `controller.py` / `config_ui.py` and
attached via `add_sections(win, group)` + the lazy-import branch in `system_settings/config_ui.py`.

**Full editor (in System Settings) — the careful-setup surface, holds everything:**
- the **Filters** (property rules),
- the **List** in full — every group: trophies, event items, materials, consumables, tonics,
  **Nick's items**, and the rest,
- the **rarities**,
- the **recolour and beacon rules** (authored here; the callback above applies them).

**Quick-access window — a plain window (built like the other modules), opened from the settings
module, for in-play use:**
- **Fully configurable — the user decides what goes in it.** Nothing is hardcoded. Anything the config
  holds can be surfaced here, picked from the full editor:
  - **rarity** switches,
  - **item type**,
  - any **List group or subgroup** — trophies, event items, keys, consumables, tonics, …,
  - **materials**,
  - **Nick's** current-week toggle,
  - and **individual filters** (a filter the user wants at hand gets a toggle here, same as anything else).

  The editor provides the picker for this; the choice is **per account** (one player's quick bar need
  not match another's). Ship sensible defaults so it is useful before anyone configures it, but every
  one of them is removable. Everything not chosen stays in the full editor.
- It must be **compact but functional** — the opposite of today's tree of hundreds of rows. The look
  to copy is **Inventory+**: textures, buttons packed in a grid so each takes little space.
- **Two view modes the user picks between**, trading graphics cost for density:
  1. **Texture grid** — Inventory+-style icon buttons (nicer, heavier to render);
  2. **Checkbox table** — plain rows of checkboxes (lighter, cheaper), for users who don't want the
     texture overhead.
- The balance to hit: **data-dense but a lean window, with good UX** — enough on screen to be useful
  mid-play, small enough to leave up, quick to read.

Search over the item grid is still the biggest single usability add wherever the grid appears.

---

## The two data tables (extracted, pending your review)

Both are **drafts extracted from existing data**; neither is final until you clean them, and the cleaned
versions become the single source (they then ship in the package's `data/` folder).

| table | what it is | source | status |
|---|---|---|---|
| **grouping** (item → category) | which item sits in which group (Trophies, Consumables, Tonics, …) — the one hand-maintained piece | the old `LootGroups` dict (`Lootconfig_src.py:9-531`, ~400 items) | not yet extracted |
| **salvage** (item → materials) | `model_id → { common: [material ModelID], rare: [material ModelID] }` | frenkey's scraped `items.json`, stripped of all name/description/wiki/amount noise | **extracted** → `salvage_mapping.json` (ids only, the real artefact) + `salvage_mapping_review.json` (same data with names, for reading). ~2,000 items, 34 materials. Armor deliberately absent (grabbed by rarity). |

The two `salvage_mapping*.json` files in this folder are **review drafts, not runtime data** — once you
approve, the id-only one moves into the package and the review copy is deleted.

## Still open (small, not blocking the first steps)

1. **Gold coins** — a specific model, not a rarity, and today's toggle is broken (set, never read). Keep
   it as its own switch beside the rarity toggles?
2. **The Inventory+ embedded loot panel** — the standalone Loot Manager window is replaced by the
   System Settings editor; does the InvPlus panel get repointed at the new class, or removed?
3. **The skip-list id bug** — today it is stored by one id and checked by another
   (`02` §1). Fix it in the new engine (recommended) or reproduce as-is?

## Status
Design settled. Steps 1–3 of the build order (`03`) are fully specified and safe to start; the three
items above only affect later steps.
