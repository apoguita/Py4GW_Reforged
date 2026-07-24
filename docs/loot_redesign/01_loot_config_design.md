# Loot Config — Redesign

The design for replacing the current loot filter. Written to be read before any code is written.
Language is kept plain on purpose.

---

## 1. What this is, and what is wrong today

The loot filter decides which items lying on the ground the character should walk over and pick up.
The current class (`Py4GWCoreLib/py4gwcorelib_src/Lootconfig_src.py`, `LootConfig`) works but has
grown three problems we are fixing:

1. **It can only ask two questions about an item** — "what is its exact model?" and "what is its
   rarity?". Everything else an item tells us (its kind, its worth, its stack size, its dye colour,
   its requirement and damage) it ignores. Because model is the only fine-grained tool, the config
   is forced to list items one by one — a 403-entry hand-typed catalog, plus an 853-line duplicate
   of the same list inside the core library.
2. **A plugin can overrule your settings without you knowing.** The old class lets code register a
   hidden function (`AddCustomItemCheck`) that runs last and can turn a "no" into a "yes". It is not
   shown anywhere, not saved, and cannot be switched off from the interface. In practice one plugin
   (frenkey's LootEx) uses it to run an entire parallel loot engine that can make any client pick up
   things your settings said to leave.
3. **Dyes and item types don't actually work.** The interface writes a dye list that the filter
   never reads, and there is no way at all to say "pick up all trophies" without naming all 244.

This redesign keeps everything the current class can do, adds the missing questions, and removes the
hidden override.

---

## 2. What the game actually lets us see (measured, not assumed)

This was established from live dumps of real ground items (see `ground_item_dump.log`, produced by
`Widgets/Coding/Debug/Py4GW/Ground Item Dump.py`). The key finding:

- **An item on the ground and the same item in your bag are the same thing.** We dumped one item in
  both places: of 85 fields, only 3 differed, and all three were "where does it live" (agent id,
  bag slot, in-inventory flag). Nothing about the item itself changes on pickup.
- **The real dividing line is identified vs unidentified**, and loot is always unidentified when you
  decide whether to grab it. So:
  - **Always readable** (even unidentified, on the floor): item type, rarity (except Blue — see
    below), model, merchant value, stack quantity, dye colour, the built-in weapon facts
    (requirement, damage, damage type, weapon subtype), owner, and the item flags (salvageable,
    material, rare material, stackable, tome, …).
  - **Never readable until identified**: prefix/suffix/inscription upgrades, and the composed
    display name. **A loot filter can never depend on these**, because loot is unidentified.
- **All five rarities read correctly on the floor — confirmed.** Blue is derived by the game from
  the item's composed `single_item_name`, and the ground dumps showed that field **is populated on
  ground items** (`0x42` on the bow, `0x3D` on the dye), so blue detection is evaluable without
  picking the item up. White/Purple/Gold/Green were already confirmed. Nothing about rarity is
  pending.
- **An immutable item can be read once.** Because a ground item never changes, we read its facts a
  single time and reuse them (see §8).

---

## 3. The system has two parts

**Part A — the catalog (models and categories).** A hand-curated list of specific items and the
groups they belong to. This is the "I want *this exact item*" surface — Vaettir Essence, Star Bow,
Black Dye. It stays, and it will be large (hundreds of entries). Ticking a model means "pick this
model up".

**Part B — the filters.** A small number of general rules that describe items by their qualities
rather than by name — "all golds", "any trophy", "worth over 100 gold", "a bow at requirement 8 or
better". This is the versatile part, and it is what removes the need to enumerate hundreds of items
by hand.

The two parts work together by the single rule in §4.

---

## 4. The decision: any match means pick up

There is **no ranking and no override.** An item is picked up if **any** of the following is true:

- its model is ticked in the catalog, **or**
- any one filter matches it.

If nothing matches, it is left on the ground.

This flat rule is what removes the plugin-override problem by construction. There are no special
positions in the list, so nothing can outrank anything. A plugin, if we ever want one, is just
another filter with a name and a tick box — it has no more power than a filter you wrote yourself.
This is the retrofit for the old hidden custom checks: same ability to contribute a decision, but
visible, named, toggleable, and unable to force a pickup past a filter.

---

## 5. A filter is several conditions, all of which must hold

This is the versatile core, and it deliberately mirrors the mod-filter scheme we already have
(`Item.Mods`, see `docs/item_mods/10_item_mods_api.md`). **We reuse that class — we do not build a
second matcher next to it.**

One filter is a set of conditions. **Every condition in the filter must be true** for the filter to
match (they are combined with AND). Different filters are independent (combined with OR, per §4).

Your example — *"a gold bow named Star Bow at requirement 8"* — is **one** filter with four
conditions:

```
Filter "Gold Star Bows":
    rarity   = Gold
    type     = Bow
    model    = Star Bow
    requirement ≤ 8
```

### How a condition is written

Conditions come in two flavours that share one style:

- **Item-fact conditions** — type, rarity, model, value, quantity, dye colour, owner.
- **Mod conditions** — requirement, damage, damage type, weapon subtype, and anything else the mod
  layer can already read. These are written **exactly** as `Item.Mods.HasMod(item_id, mod, *values)`
  already accepts them, because that is the function the filter calls.

The value after a condition is **routed by its type**, identical to the mod API:

- an **enum** narrows the subtype — `Attribute.Marksmanship`, `DamageType.Piercing`;
- a **number** means **"that value or better"**, where "better" is the fact's own direction —
  requirement is lower-is-better (`8` means req ≤ 8), damage/value/quantity are higher-is-better
  (`100` means ≥ 100);
- a **callable** is a custom test, for the rare case the shortcut can't express.

The point of copying this scheme: there is **one** way to write a condition, whether it is about the
item itself or its mods, and the common cases need no lambda. "Or better" and the correct direction
come for free from the fact's metadata — exactly as they already do for mods.

### Exceptions live on the filter, not in a separate list

A filter can carry exceptions, so "everything gold except two named items" is still one filter and
still obeys "any match = pick up":

```
Filter "Golds":
    when   rarity = Gold
    unless model in { Spear of Archemorus, Urn of Saint Viktor }
```

The filter matches when every `when` condition holds and no `unless` condition holds. There is no
second "never" list that outranks anything — the exception is simply part of what that filter means.

### The vocabulary of item-fact keys

Item facts get the same treatment mods already have: a single table where each key declares what
type its value is, which enum its subtype uses (if any), and which direction counts as "better".
Mods already have this; item facts join it, so both are written the same way. Initial keys:

| key | value | direction |
|---|---|---|
| type | `ItemType` (incl. meta-types like Weapon → Axe/Sword/Bow/…) | exact / membership |
| rarity | `Rarity` | exact / membership |
| model | `ModelID` | exact / membership |
| value | number (merchant value) | higher is better |
| quantity | number (stack size) | higher is better |
| dye colour | `DyeColor`, via `Item.Dye` (not the raw mod) | exact / membership |
| owner | mine / unassigned / other | (handled as a gate, see §7) |
| salvages-into | `ModelID` material | membership |

Mod-based keys (requirement, damage, damage type, weapon subtype, armor, energy …) are the
`ModifierIdentifier` constants, used through `Item.Mods` unchanged.

---

## 6. Reading each item once

An unidentified ground item cannot change while it lies there, so the class reads its facts **once**
into a small record (type, rarity, model, value, quantity, dye colour, owner, plus the mod facts it
needs) and reuses that record for the rest of the map instance. This replaces the current code,
which re-reads each item from the game about a dozen times, for every item, every frame — on a path
HeroAI runs continuously. Reading once is both faster and removes a class of "half-read item" bugs.

---

## 7. Two things that are gates, not filters

These are not preferences, so they are not part of the filter set:

- **May I take it (ownership).** Whether the item is mine, unassigned, or belongs to another player,
  plus the existing shared-memory loot lock that stops two accounts fighting over the same drop.
- **Can I take it (space and reach).** Free bag slots and distance.

Keeping these separate is deliberate: today they are tangled inside the same function as the
preferences, which is why multibox behaviour and loot preferences can't be reasoned about apart.

**The one-off skip list stays too, and stays outside the filters.** When the pickup routine fails to
reach a particular item it records that item so it stops retrying it forever. This is bookkeeping the
routine does for itself, not something you configure. `Messaging.py` writes to it; `Environment
Upkeeper` clears it.

---

## 8. Runtime additions from bots

Bots can still add items to loot while running — this is preserved. What changes is that a bot's
additions are kept **apart from your saved configuration**: they are temporary, they clear when you
change map (item ids reset per instance anyway), and they never get written to your config file.
The interface can show, e.g., "4 items added by VaettirBot", so you can see what a bot is doing to
your filter. (Today a bot's additions land in the same list as your own choices and can be saved to
disk, so a bot can quietly alter your saved config.)

---

## 9. Where it lives, and the interface

The class lives in **System Settings** (`Py4GWCoreLib/py4gwcorelib_src/system_settings/…`), as its
own category, following the same pattern the name-obfuscation and agent-recolor features already use
(a `SidebarWindow` category built from a controller / model / persistence split).

- **In System Settings** (the full editor): the **rules** (filters) and the **models/categories**
  catalog. This is where you set things up carefully — searching the catalog, editing a filter's
  conditions, adding exceptions.
- **A separate pop-up window** for **quick access**: the handful of things you flip on and off
  during play without opening the full settings — the equivalent of today's rarity toggles, plus any
  filter you want at hand. This window is opened and handled from the System Settings category.

Two interface requirements carried from the analysis, to be detailed in a later UI doc:

- **The catalog needs search (type-to-find).** Hundreds of toggles are only workable if you can type
  a name and jump to it, instead of walking a group tree. This is the main reason the current
  interface is painful; the count is not the problem, the lack of search is.
- **The catalog should derive names and icons from `ModelID` + the texture folder**, not re-type
  them. The current hand-typed catalog has ~12 dead entries from spelling mistakes
  (`Curved_Mintaur_Horn`, `Dregde_Charm`, …) that tick but do nothing. Deriving from the enum makes
  that impossible and gives every catalogued item its picture for free (90% of the current set
  already has a texture on disk).

The one thing that genuinely must stay hand-maintained is the **grouping** — which models belong to
which category. Everything else (id, name, icon) is derived.

---

## 10. What stays working (compatibility)

Existing callers keep working. The class keeps its query entry point
(`GetfilteredLootArray(distance, multibox_loot, allow_unassigned_loot)`) and the runtime-add methods
that bots use. Ownership and the loot lock stay where they are. Roughly two dozen call sites
(HeroAI, Messaging, the bots, the botting framework, the routines) are unaffected by the internal
change.

---

## 11. Adjacent clean-ups this depends on

Two existing duplicates in `Item.py` should be resolved so the filter uses the correct read:

- **`Item.GetDyeColor`** (raw "first non-zero mod arg") duplicates and is less safe than
  **`Item.Dye.GetColor`** (guarded, reads the dye struct). On a non-dye item the raw one returns
  garbage (it returned the Marksmanship attribute id on a bow). The dye-colour filter key must use
  `Item.Dye`. Five callers exist for the raw one; de-duplicating them is a separate small pass.
- **`Item.Properties.IsMaxDamage` / `DAMAGE_RANGES`** is broken above requirement 9 (the table only
  covers 0–9, so a req-11 weapon always reads "not max"). "Max damage" should be expressed as a mod
  condition (`Damage ≥ …`) via `Item.Mods`, not this table.

---

## 12. Visual marking layer (recolor, fade, hide, beacon)

On top of deciding *what to pick up*, the config can **mark** items on the ground so you can see
them. This is a separate layer: **marking never changes what is picked up.** A "hidden" item is
still on the floor and can still be picked up if a filter matches it — hiding only blanks its label.

Each filter (and each rarity/type/model, since those are filters) can optionally carry:

- **a recolour** — the colour of the item's floating name label, and/or
- **a beacon** — a light beam at the item's position.

Both are optional and independent; the user decides per filter. Keep the options basic — the common
case is "recolour greens", set from the quick-access pop-up.

### Recolour / fade / hide — uses the existing native store

The native backend (`PyAgentRecolor`) **already has a full ground-item recolour store** — it recolours
the item's floating name label. It keys on, in this precedence order:

```
agent_id  >  item_id  >  model_id  >  name  >  type  >  rarity
```

and the colour is `0xAARRGGBB` where the **alpha byte is a fade/hide channel**: `0xFF` solid,
`0x01–0xFE` dimmer, `0x00` = label hidden. So all three effects — recolour, fade, hide — are one
native mechanism. The only missing piece is the **Python wrapper**: `AgentRecolor.py` currently
exposes Agents and Gadgets but **not Items**; the item setters
(`SetItemRarityColor` / `SetItemTypeColor` / `SetItemModelColor` / `SetItemIdColor` / … ) need
surfacing, then the loot config drives them from its filters.

**Why marking has precedence when pickup does not.** Picking up is a yes/no vote, so "any filter
matches" (OR) is right. But an item can only be *one* colour, so when two filters would mark the same
item, one must win — that is what the precedence order above is for. Same items, two questions: "take
it?" is OR; "which colour?" picks a single winner.

**"Hide" (block) means hide the label only.** We cannot stop an item from dropping; hiding sets the
label alpha to `0x00` so it is invisible on the ground. It does **not** affect pickup — that stays a
filter decision.

### Fade with distance — 10 steps, threshold-based

The name label dims with distance so far-off marks are faint and nearby ones are bright. The compass
range is 10,000 units, divided into **10 fade steps**. An item's marker alpha is recomputed **only
when the item crosses a step boundary**, not every frame — so a marked item sitting still costs
nothing, and a moving one updates at most ~10 times as it approaches.

Because distance is per-item (two green items at different ranges need different alpha), the
distance-fade path drives the **per-item** setter (`SetItemIdColor` / `SetItemAgentColor`) with the
filter's base colour and the current step's alpha. A plain solid recolour with fade off can use the
cheaper class-keyed setter (`SetItemRarityColor` etc.) and never recompute. "Hide" is absolute —
alpha `0x00` at every distance, no stepping.

### Beacon — the light-beam marker

A beacon is a world-space light beam + ground glow + particles drawn at the item's position, from
the existing `light_beacon.py` renderer (`PyParticles` + `PyDXOverlay.draw_shaded_3d`). Its saved
`state` defaults are the **purple preset** — the intended look for marking purple-rarity drops — and
ship as the example preset. A filter that has a beacon draws that preset at each matching item.

A beacon is a per-item render, so it is heavier than a recolour. It needs a cap (e.g. only the
nearest N marked items get a live beacon) so a field full of drops can't flood the renderer. Per
filter the options stay basic: beacon on/off, and which saved preset.

### Where it's set

- **Full editor (System Settings):** per-filter recolour (colour, fade on/off, hide) and beacon
  (on/off, preset).
- **Quick-access pop-up:** the everyday toggles — e.g. recolour greens, beacon on gold — without
  opening the editor.

---

## 13. Scope and cross-account updates (messaging, not files)

### One shared ruleset, per-account toggles — exactly like Agent Recolor

The config is **global-scoped with local toggles**, the same split Agent Recolor uses
(`store.py`: a global rule list + a per-account enable). Multibox accounts run on one machine and
share its disk, so "global" is genuinely one shared set.

- **Global scope** — the filters, the catalog selections, and the marking config (recolour/beacon
  per filter). One machine-wide set, stored as JSON in a **global-scope `Settings` document**
  (like `Widgets/System/Agent Recolor.ini` at global scope). Intricate rules are authored once, not
  replicated per account, and the file is trivially shareable/exportable.
- **Account scope** — the **master enable** and the **local quick-toggles** (which rarities are on,
  marking on/off, and the like). Each account opts into the feature and flips its own quick toggles,
  even though the ruleset is shared. Same document, account scope.

So: *what to loot* is shared; *whether this account is looting, and its quick toggles* is local.

### Cross-account updates go over messaging, replacing the file-mtime polling

The old loot manager made **every account poll two JSON files' modification times every 2 seconds**
to notice edits and reload. That is replaced by messaging:

- When an account edits and saves the shared ruleset, it **broadcasts a "loot config changed"
  message**; each receiver reloads the global file. No polling, no per-frame `os.path.getmtime`.
- Because accounts share the disk, the message is only a **nudge** — the rules travel via the shared
  global file; the message just says "re-read it". There is no need to pack rules into the message
  or chunk them. (This is simpler than `MerchantRules`, which chunks because it shares whole
  profiles across a request/result handshake.)
- **Commands** already ride messaging: `SharedCommandType.PickUpLoot` exists and is handled in
  `Widgets/System/Messaging.py`. The redesign adds one command type for the update notification
  (e.g. `LootConfigUpdated`).
- **`Messaging.py` only routes.** Its handler calls the loot module's reload entry point; the loot
  module owns its own file reading and config. Messaging carries the notification, never the file
  handling. (This is the standing repo rule that `Messaging.py` does no config/file I/O.)

### What is not shared

- The master enable and per-account quick-toggles stay local.
- Bot runtime additions stay local and transient — they never touch the shared file (§8).
- The one-off unreachable-item skip list is local runtime bookkeeping (§7).

---

## 14. Status — built and settled

Everything in this design is implemented (see `03_parity_audit.md` for the feature-by-feature
status). Rarity (all five, incl. blue) is confirmed readable on the ground; persistence, messaging,
the UI, and the visual marking layer are all in. The one measurement not separately taken is the
armor *value* mod on an unidentified armor piece — but that only affects an armor-value condition;
armor by type + rarity + model works regardless, and the ground/bag equivalence (§2) means it reads
the same as in a bag if needed.

(The UI — System Settings editor tabs + the toggleable quick-access floating window — is in
`02_loot_ui.md`.)

---

## 15. Suggested build order

1. **The decision core**, standalone: read an item once, run the filters, return what to pick up —
   plus the existing query/add methods so nothing breaks. Testable against real items with the dump
   widget. No interface, no saving, no catalog work yet.
2. The catalog, derived from `ModelID` + textures + the grouping table.
3. Persistence: global-scope ruleset + per-account toggles (mirror Agent Recolor's `store.py`).
4. The System Settings category (rules + models) and the quick-access pop-up.
5. The visual marking layer: expose the item setters in `AgentRecolor.py`, drive recolour/fade/hide
   from filters (distance-fade in 10 steps), then beacons from `light_beacon.py` presets.
6. Cross-account updates: add the `LootConfigUpdated` command type + a `Messaging.py` route that
   calls the loot module's reload; broadcast on save.
