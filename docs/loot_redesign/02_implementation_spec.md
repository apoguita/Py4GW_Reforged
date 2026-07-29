# Implementation specification — the *how*

`01_class.md` says **what** the system does. It is sound and owner-approved. It is not enough to build
from, and that is why two implementations failed: every gap in the *how* became a decision taken at the
keyboard, by me, silently.

This document exists to remove that possibility.

---

## The hard rule

> **No decisions may be made during implementation.**
>
> If a question arises while writing code — what a control looks like, where a value is stored, which
> of two orderings wins, what happens when a list is empty — **implementation stops**. The question
> comes back here, is answered by the owner, is written down, and only then does coding resume.
>
> "I'll pick something sensible and flag it later" is the exact behaviour that produced two reverts.
> A reasonable-looking guess is worse than a halt, because it ships and looks finished.

**Corollaries:**

1. **Nothing is built that this document does not specify.** If a surface is not spelled out here, it
   is not written — not even a placeholder, because placeholders shipped last time (letter-tiles
   standing in for textures, an integer box standing in for the mods picker).
2. **A feature is not "implemented" until its authoring surface works.** A correct data model behind an
   unreachable UI counts as **not done**. That single judgement error accounts for most of the audit.
3. **Every step has a written acceptance check** *before* it is built, and it is demonstrated, not
   asserted.

---

## Why this is needed — the evidence

From `legacy/reverted_audit_vs_plan.md`, every one of these was a decision the plan did not cover and I took
anyway:

| what I decided unilaterally | consequence |
|---|---|
| Profiles need no UI yet | `save_profiles` never called; the whole feature inert |
| Presets need no editor | one hard-coded beacon, `save_presets` never called |
| `mods_any` can wait | the OR half of a settled decision unreachable |
| Nicholas pinned dates can wait | "any cycle, any date" unreachable |
| Criteria can be typed as integers | catalog and enums present but unused, in 5 places |
| Icons can be two letters of the name | the entire two-view cost argument voided |
| Quick access = whole categories | "add what they want" not delivered |
| Marking gets its own ordering | two orderings where the plan described one |
| `filter_ids` alongside profiles | two overlapping concepts for one idea |

Nine decisions. **Zero** were surfaced before they shipped.

---

## The absolute rule: a script NEVER persists

> **Whatever a script does lives in memory. It never reaches disk. Never.**

Not "is discouraged from", not "is cleaned up later" — there is no path from a script's change to a
writer. This is the invariant the whole design rests on, and everything else about live state is a
mechanical consequence of it:

**Every piece a script can touch is doubled: a persisted copy and a live copy.** The persisted copy is
the user's, written only by the user through System Settings. The live copy is what actually runs.
A script writes only the live copy.

| piece | can a script change it? | doubled? |
|---|---|---|
| Loot Filters — active profile, toggles, hand lists, blacklist | yes | **yes** |
| Recolor & Beacons — active profile, outcomes, budget | yes | **yes** |
| Loot Filter Factory — filters, profiles | **no** (structure is forbidden — see H2) | no |
| Beacons — presets | **no** | no |

Only the two feature configurations need a live copy, because they are the only things a script can
reach. The Factory and the Beacons module hold definitions a script may consume but never author, so
there is nothing there for a script to dirty.

**Consequences, all derived rather than decided:**

- **Reset discards the live copy and re-copies from persisted.** Per feature, since each has its own.
- **A restart is a reset** — the live copy never existed on disk, so it comes back as stock by
  construction, not by cleanup.
- **Saving is never something a script triggers.** There is no "save" on the live copy; it is not a
  thing that can be written.
- **The diff is live vs persisted**, per feature. It is what the label and the detail window show.
- **A crash loses nothing**, because there was nothing of the user's to lose.

The user's configuration is therefore intact at all times, by construction and not by discipline.

## Terminology — say what you mean

**A "filter" is the composite resolver**, not a single evaluation.

One filter is the whole thing: its criteria composed together, resolving to one yes/no for an item.
A single condition inside it — a model id, a requirement, an upgrade — is a **criterion**, never "a
filter".

This distinction matters because the two are constantly confused, and confusing them produces wrong
questions. Asking "which order do the filters resolve in" sounds sensible if a filter is one
condition; it is close to meaningless when a filter is a complete resolver that matches its own items
independently.

| term | means |
|---|---|
| **criterion** | one condition — a model id, an item type, an upgrade, a requirement |
| **filter** | the **composite resolver** — criteria composed, yields one verdict per item |
| **profile** | a named set of filters |

## Decision register — to be settled BEFORE any code

Each entry needs an owner ruling. Options are listed to make answering fast; "something else" is always
available. Nothing here is a recommendation — recommending is how the last two attempts drifted.

### A · Filter authoring

#### A1 — Model id input · **SETTLED**

**Both paths exist**, taken from Inventory+, because they serve different needs:

| path | reference | used for | search |
|---|---|---|---|
| **textured grid** | `InvPlus/LootModule.py:101-140` — browse group → subgroup, 3-column table of 48x48 `image_toggle_button` with the item name wrapped underneath | the **curated** catalog: a known, visually recognisable set | **no** — a curated list is small once browsed to its subgroup, so it needs no search tools |
| **two-pane picker** | `InvPlus/AutoHandlerModule.py:119-190` — search box, Contains / Starts With radio, left pane = every `ModelID` member sorted by name, right pane = the chosen set; click left to add, click right to remove | reaching **any** model id in the enum, including the ones never catalogued | **yes** — this is a flat search over everything |

Rule of thumb that follows: **flat list + search for the whole enum; curated list browsed, no search.**

Whatever else in the reference proves useful is kept; nothing is copied for its own sake.

**A1a — the picker is INLINE.** It sits inside the filter editor, always visible; not a modal popup
as in the reference. The user sees the rule and the picker at the same time.

**A1b — the model id is shown.** Each row carries the numeric id, as the reference does
(`Iron_Ingot (948)`). The id is the thing the game matches on and stays visible to the user.

**Names are prettified everywhere** — `Iron Ingot`, not `Iron_Ingot`. The grid already does this
(`' '.join(w.capitalize() for w in name.split('_'))`); the picker does it too, so a row reads
`Iron Ingot (948)`. The raw enum spelling is never shown.

**A1 is closed.**



#### A2 — Item type input · **SETTLED**

Same shape as A1: **inline two-pane picker**, rows read `Name (id)`, names prettified.

**Every type that can drop is filterable, grouped. Anything that cannot drop gets no filter at all.**

**Umbrella enum members are never filterable entries.** `Weapon`, `MartialWeapon`,
`SpellcastingWeapon`, `OffhandOrShield`, `EquippableItem`, `Unknown` are *definitions*
(`ITEM_TYPE_META_TYPES`), not things a user picks. Offering them beside the concrete types would let
one filter be written two ways — `MartialWeapon` versus Axe+Sword+… — which is duplicated flags.

> **No group may duplicate another group's flags.**

**Weapons are ONE flat group.** The martial / spellcasting / offhand subdivision the enum describes is
*not* surfaced; the user sees the weapon list, not its internal taxonomy.

**A2c — the Weapons group is the 11.** It uses the broader definition (`WEAPON_TYPES` /
`EquippableItem`): the 9 weapons **plus Offhand and Shield**. The enum's narrower `ItemType.Weapon` (9)
is not used here. The enum's self-contradiction is **not** fixed as part of this work — see
`docs/pending_fixes.md` PF-1.

**Non-weapon groups · APPROVED:**

| group | types |
|---|---|
| **Armor** | Chestpiece, Headpiece, Leggings, Boots, Gloves |
| **Upgrades** | Rune_Mod |
| **Miniatures** | Minipet |
| **Consumables** | Usable, Kit, Scroll |
| **Currency & tokens** | Gold_Coin, CC_Shards, Materials_Zcoins |
| **Materials & salvage** | Salvage, Trophy |
| **Keys & quest** | Key, Quest_Item, Storybook |
| **Cosmetic** | Dye, Costume, Costume_Headpiece |
| **Containers** | Bag, Bundle |
| **Event** | Present |

---

## Presentation — the house rule · **SETTLED**

> **One structure, many renderings.**
>
> **Uniform:** collapsible headers are the structural device *everywhere*. That is what makes the whole
> system feel like one thing.
>
> **Varying:** what sits *inside* a header is chosen to fit the data. There is no single presentation
> that fits every surface, and forcing one is a mistake.

**Owner's worked examples:**

| the data | the rendering | why |
|---|---|---|
| **few options** — e.g. the rarity toggles | tree with checkboxes | a handful of entries; nothing more is needed |
| **a large set** | **grid of toggle buttons** | a checkbox *list* becomes too long to read or scroll |
| **models that have textures** | **grid of textured toggle buttons** | the texture identifies the item faster than its name |
| **the same set, for users unwilling to pay the render cost** | **grid of checkboxes** | same layout, cheap cells — the texture is the only thing dropped |

This is what the two-view toggle already settled in the plan actually *is*: the container and the
layout stay put, and only the cell changes. It is not two different screens.

**Consequence for A2's picker:** item types have no textures, so a textured grid is not available to
them; the choice there is between a checkbox list and a checkbox grid, under collapsible headers per
group.

### All four renderings are built; the USER chooses · **SETTLED**

**We do not assign a rendering per surface.** All four are implemented, and the user picks their own
styling. The choice is theirs, not a design decision baked in per screen.

The four:

1. **checkbox list** (tree)
2. **checkbox grid**
3. **toggle-button grid**
4. **textured toggle-button grid**

Collapsible headers remain the container in every case — only the cell changes.

**P1 — the choice is PER SURFACE**, so a user may have textured grids for materials and a checkbox
list for trophies. The Quick Access tab in System Settings carries buttons to **apply one rendering to
every surface at once**, for a user who wants uniformity without setting it eleven times.

**P2 — all configuration lives in System Settings. The quick access configures nothing.**

> The quick access is *quick access*, not configuration. It **follows** the rules configured elsewhere.

**This supersedes an earlier decision in the plan.** `01_class.md` recorded that the display-mode
toggle and its cost warning are reachable from *both* the quick access and the settings. That no longer
holds: heavy configuration is settings-only, and the quick access carries no config controls. The
plan's earlier wording is superseded by this entry.

**P3 — a missing texture renders the "no texture" texture.** No rendering is ever hidden or disabled
for lack of textures. The asset already exists — `Textures/Item Models/0-File_Not_found.png`, which
`get_texture_for_model` (`enums_src/Texture_enums.py:12-22`) already returns as its fallback for any
model id it cannot resolve. So the textured grid is offered on every surface, and shows the placeholder
where there is nothing to show.

The rule is settled; which rendering each surface gets is not. Surfaces needing an assignment:

- rarity toggles (+ gold coins)
- the catalog hand lists (387 rows, group -> subgroup)
- materials · salvage targets · dyes
- Nicholas selections
- the item-type picker (~35 across ~11 groups)
- the model-id picker (whole `ModelID` enum, flat + search)
- the blacklist
- filter list · marking rule list · profile list · beacon preset list
#### A3 · A4 — dye colours and salvage materials · **SETTLED**

**No special treatment.** 13 dye colours and 36 materials are unremarkable list sizes — there are
longer lists already. They are ordinary surfaces: collapsible headers, and whichever of the four
renderings the user chose. No bespoke picker, no separate design.

#### A5 · A6 — mod conditions · **SETTLED: copy the playground**

**The reference is `Widgets/Coding/Debug/Py4GW/Item Mods Playground.py:206-280`** — the existing
script that already exemplifies filtering items by mods. Its shape is copied, not reinvented.

**Conditions are slot-based upgrade pickers, never modifier ids.** `_build_lists()` (`:59-74`) derives
five curated lists from `mods_upgrades.UPGRADE_SLOT` + `mods_core.Slot`:

| list | derivation |
|---|---|
| **Prefixes** | slot == Prefix, name lacks "Insignia" |
| **Insignias** | slot == Prefix, name contains "Insignia" |
| **Suffixes** | slot == Suffix, name lacks "Rune" |
| **Runes** | slot == Suffix, name contains "Rune" |
| **Inscriptions** | slot == Inscription |

Each is a `combo` with **`(any)` at index 0**, names prettified via `mods_core._pretty`, sorted
alphabetically. Matching is `internal_name in Item.Mods.GetUpgrades(item_id)`.

So the user picks **"Sundering"**, not identifier 42. *(The reverted build shipped a raw integer box
here. That is the single clearest example of ignoring an existing, working reference.)*

**Dedicated controls beside the upgrade combos:**

- **Item type** — a `combo`, pre-filtered to `is_weapon_type() or is_armor_type()`; only types that can
  carry mods appear.
- **Requirement** — checkbox **"Requirement at most"** + `slider_int(0..13)`. Phrased *at most*, which
  is match-or-better for a `better_low` mod.
- **Max damage** — checkbox, "Require max damage (for its req)".

**Match-or-better is confirmed by the reference itself** — its header reads *"exactly how the matching
(exact-or-better) behaves"*. One value, never a min/max range.

**AND/OR is ONE radio pair over the whole rule** — not per condition, and not two sections:

```python
mode = PyImGui.radio_button("Match ALL (AND)", mode, 0)
mode = PyImGui.radio_button("Match ANY (OR)",  mode, 1)
```

> **This supersedes the plan.** `01_class.md` has `mods_all` / `mods_any` as two separate lists on a
> rule. The playground instead has one flat criteria set with a single ALL/ANY mode. The playground
> wins, because it is the module that actually filters items by mods.
>
> It also corrects something I asserted from `agent_recolor` — that System Settings never uses an
> AND/OR control and expresses any-of/all-of by section label. True of `agent_recolor`, false here.

**A8 (live preview) is answered by the same reference** — it shows a verdict and a per-criterion
breakdown:

```
ITEM MATCHES        (all of 4 criteria)
  [x] type is Axe
  [ ] requirement 9 <= 8
```

That is the shape the filter editor's preview takes.
#### A7 — filter identity and duplication · **SETTLED**

**Filters can be duplicated.** Copying a filter as a starting point is the fine-tuning workflow; making
it impossible would make development and tuning painful.

**A filter is anchored by a short sequential number. The title is a label, never a key.**

A filter is *composite* — no criterion is guaranteed to be present — so nothing in its content can
identify it. That leaves the title or an id, and the title cannot be the key: keying by title forces
titles to be unique (so duplication needs a rename) and makes renaming cascade through every profile
and marking rule that points at the filter. So: **a plain sequential number, and titles are free to
repeat and to be renamed.**

**No uuid.** The reverted build proposed one, copied from `agent_recolor` (`controller.py:110`), and
justified it with cross-account id collision. That justification is wrong twice over: the pool is a
single global store, and the concurrency case is not real (below). A 32-character random hex makes the
stored JSON unreadable and buys nothing. See `docs/pending_fixes.md` PF-4.

*On the concurrency question, which was investigated rather than assumed:* global documents really do
have concurrent writers — `JsonFactory.py:37-40` says Global saves take a cross-process lock and merge
a write journal, *"only same-path writes race, last-writer-wins"*. In principle two clients could each
compute `max+1` and mint the same number. **In practice this is discounted:** the system is a
multi-account setup driven by **one person** — a single user at one keyboard — so two accounts
authoring filters in the same instant is not a real scenario. `max(existing) + 1` is therefore
sufficient, and no account prefix or timestamp scheme is warranted.
#### A8 — live preview · **SETTLED by the reference**

**Yes** — the playground already does it, and its shape is copied
(`Item Mods Playground.py:268-279`): a verdict line plus a per-criterion breakdown, so the user sees
not just *whether* it matches but *which condition failed*.

```
ITEM MATCHES              (all of 4 criteria)
  [x] type is Axe
  [ ] requirement 9 <= 8
```

**Chunk A is closed.**

### B · Profiles · **SETTLED**

#### What a profile is

**A named set of filters.** "Caster", "Ranger", "Melee", "Necromancer" — a profile groups the filters
that belong together for a way of playing. One or several filters each.

Sharing across accounts is the point of them: with many accounts, a profile composed once should be
usable everywhere, which is why profiles are global.

#### Navigation — collapsible headers, not tabs · **SETTLED**

**Use collapsible headers.** Tabs are preferred *in principle*, but only when there are few of them —
a long row of tabs is worse than no tabs, and this would be a long row.

> **This supersedes the plan.** `01_class.md` settled *"top tabs, one category per tab"* for the quick
> access. That is replaced: **groups are stacked collapsible headers**, which is the house rule
> everywhere else anyway. The quick access stops being the one surface with its own navigation idiom.

Collapsed, the whole window is one line per group — so a user with six groups sees six lines and opens
the one they want.



**The quick access gets no lobby and no drill-down.** Adding a landing page would make it a menu, and
then it is not a quick access any more. Whatever the user put there is **immediately reachable and
immediately togglable** — that is the entire point of the window.

**It has no scale problem to solve.** The quick access holds *only what the user chose to put in it* —
a handful of groups and filters. The eleven-group, 403-entry problem lives in **System Settings**,
which is where navigation belongs. Do not import a settings-sized problem into a window that does not
have it.

*A note on tabs, so it is not revisited:* **ImGui has no multi-row tab bar.** Verified against the
vendored upstream (`third_party/imgui/imgui.h`, `enum ImGuiTabBarFlags_`) — the only overflow policies
are Shrink, Scroll and Mixed, and nothing in `imgui_widgets.cpp` wraps tabs. The Python stub already
mirrors every upstream flag, so there is nothing unexposed to bind: a real multi-row tab bar would have
to be **written** as a new ImGui addon in the Native tree. That is a generic toolkit item, not loot
work. If the quick access ever outgrows one row of tabs, the settled house rule already answers it —
collapsible headers, stacked.

#### F1 — bulk actions · **SETTLED**

**`all` / `clear` at every level where it applies** — group, category, and anywhere else a bulk toggle
is meaningful. Not only at the lowest level.

*(Written in the settled vocabulary: a **category** contains **groups**. See F · Naming.)*

#### F2 — one shared renderer, and its own callback · **SETTLED**

**Two separate things, both settled:**

**What draws a hand list: ONE shared renderer.** The settings surface and the quick access render the
same groups, with the same four layouts, the same collapsible headers and the same bulk actions — so
they call the same function. A fix or a new layout lands in both at once and they cannot drift apart.

**What drives the drawing: the quick access owns its own callback.** It registers its own draw pass
(`PyCallback.Register(name, Phase.Update, fn, context=Context.Draw)`, as `agent_recolor` already does
for its data pass) rather than being drawn from another module's `draw()`. The window is therefore
independent — it renders whether or not System Settings is open, and does not ride on the settings
widget's frame.

*(The reverted build got this wrong in the most basic way: the quick access had no caller at all, so
it never appeared. Owning a callback removes the class of bug entirely.)*

#### Naming · **SETTLED**

| piece | name | what it is |
|---|---|---|
| the shared factory | **Loot Filter Factory** (`loot_filter_factory`) | filter definitions, profiles, the store, the editor |
| the loot feature | **Loot Filters** (`loot_filters`) | decides what is **wanted** |
| the marking feature | **Recolor & Beacons** (`recolor_beacons`) | decides what is **highlighted** |

**`item_filters` is reserved** — that name belongs to the full-fledged **mod filter class**, a separate
thing. The reverted build used `item_filters` for the shared core; that was wrong and must not be
reused.

#### Ownership — the Loot Filter Factory owns it; both features CONSUME

**Neither Loot Filters nor Recolor & Beacons owns the filters, the profiles, the store or the editor.**
Both are consumers of the Loot Filter Factory, the same way they are consumers of the matcher.

| piece | owns | consumes |
|---|---|---|
| **Loot Filter Factory** | filter definitions, profiles, store, editor | — |
| **Loot Filters** | the outcome *wanted* | the Factory |
| **Recolor & Beacons** | the outcome *recolour and/or beacon* | the Factory |

**The editor is its own surface.** It is **not embedded in either feature**. The Loot Filter Factory
has its own handling and its own place; the two features simply **inherit** the filters and profiles it
produces.

So the **Items** category in System Settings holds **three** subcategories, not two:

| subcategory | what the user does there |
|---|---|
| **Loot Filter Factory** | authors filters and profiles — create, read, update, delete |
| **Loot Filters** | selects a profile; its own toggles, hand lists, blacklist |
| **Recolor & Beacons** | selects a profile; binds colour / beacon outcomes |

A consumer *selects*; it never hosts the authoring UI. That is what makes "both features consume"
literally true rather than a description of an embedding arrangement.

**Chunk B is closed.**

#### B1 · B5 — contents, and one concept only

A profile contains **filters**. Nothing else — not toggles, not hand lists, not rarity switches. Those
are per-account settings and a profile is a global definition; putting per-account data inside a
shared object would stop two accounts running one profile with different toggles.

**There is exactly one concept.** The active set *is* a profile. The reverted build's loose
per-account `filter_ids` list, which did the same job alongside the profile mechanism, does not exist.

#### B2 — where it is edited

**System Settings, always.** That is the main UI. The quick access is quick access — it never edits
profiles or filters, it follows what was configured.

#### B3 — operations

**Regular CRUD**: create, read, update, delete.

#### B4 · B6 — one active profile PER FEATURE

**Each feature has its own active profile, one at a time.** Loot may run "Caster" while
Recolor & Beacons runs something else; both selections draw from the same shared pool.

The selection is a per-account setting (definitions global, selections local — the rule already
settled). Recolor & Beacons has profiles by the same mechanism, not a separate one.

#### Script-facing API — consumers only

*(supersedes the plan's broader "a script may change anything in live")*

**"Consumers only" is about FILTERS and PROFILES — not about entries.** A script may still add a model
id or an item id; that was settled in the plan and is not narrowed here. See H2.

### C · Beacon presets

#### C0 — the beacon is its own module · **SETTLED**

**Beacons are a separate module, embedded in no feature's UI** — the same arrangement as the Loot
Filter Factory.

It owns the beacon effect, the presets, their storage and their editor. **Recolor & Beacons consumes
it**: it selects a preset to use, it does not host the editor and does not own the presets.

So the **Items** category now holds **four** subcategories:

| subcategory | what the user does there |
|---|---|
| **Loot Filter Factory** | authors filters and profiles |
| **Beacons** | authors beacon presets — the effect editor |
| **Loot Filters** | selects a profile; toggles, hand lists, blacklist |
| **Recolor & Beacons** | selects a profile; binds colour / beacon outcomes, picking a preset |

The rule this follows, now applied twice: **an authoring surface stands on its own; a feature
consumes what it produces.** Neither feature owns filters, profiles, beacon effects or presets.

*A consequence worth noting:* because the beacon module is independent of Recolor & Beacons, a beacon
preset can be authored and previewed with the marking feature switched off entirely.

#### C1 · C2 — scope and controls · **SETTLED**

**Use the current beacon, and expose every parameter, exactly as the test script does.**
`light_beacon.py` is the reference for the controls as well as the effect.

Most users will only ever change the beam colours — **but full control is available**, so a user can
mix and match into their own marker. Nothing is pruned for being "probably unused".

**The reference supplies the widget, label and range for every parameter**, so none of that is
invented:

| parameter kind | control | source |
|---|---|---|
| beam shape / blend | `combo` — *"crossed quads" / "cone (glow)"*, *"alpha" / "additive" / "max (colored glow)"* | `:371-372` |
| cone sides | `slider_int` 3–48 | `:374` |
| glow strength · width · softness | `slider_float` 0–1 · 1–5 · `slider_int` 1–10 | `:375-377` |
| crossed quads | `slider_int` 1–8 | `:379` |
| **the four colours** | `color_edit4` — *"alpha = opacity"* | `:380-382`, disc likewise |
| centre height, height, widths, ground, rings | `slider_float` with the reference's ranges | `:383-384`+ |
| **every emitter parameter** | `slider_float(key, min, max)` driven by `EMITTER_GROUPS` | `:333-336` |
| emitter enabled / additive | `checkbox` | `:328-330` |
| emitter mode | `combo` — *"ballistic" / "orbital"* | `:331` |
| emitter colour | `color_edit4` | `:332` |

Emitters render as **one collapsing header each**, id-suffixed by index so two emitters with the same
name cannot collide (`_emitter_ui`, `:320-337`) — which is also the house layout rule.

**Conditional controls follow the reference:** cone sides and the glow trio appear only for the cone
shape; crossed-quads count only for the quads shape (`:373-379`).

**Two parameters do not carry over:**

- **`rows`** — dead. It sits in the reference's state and `_draw` never reads it. Verified, not
  assumed.
- **`anchor_mode` / `anchor_x` / `anchor_y` / `anchor_set`** — alive in the reference, but they pin a
  beacon to a fixed world position. An item beacon follows its drop, so they are not applicable.

*Note on judging what is inert:* the emitter parameters cannot be assessed by reading Python.
`_apply_emitter` (`:239-249`) loops `EMITTER_GROUPS` and `setattr`s every key onto the C++ emitter
config, so a parameter can look unread in Python while doing work in the particle system. That is why
none were pruned on suspicion.


#### C3 · C4 · C5 — a full editor · **SETTLED**

Not a parameter dump: the Beacons module is a **full editor**, with the affordances that make tweaking
bearable. **All of the below are built.**

**Presets**

- create · rename · **duplicate** · delete
- **presets are GLOBAL** — shared across accounts, like filters and profiles
- **the base beacon is the default and is protected from deletion** — there is always something to
  fall back to
- **reset this preset to the base** — one action undoes a session of fiddling
- **export to file / import from file** — files, **never the clipboard** (the rule from
  `docs/pending_fixes.md` PF-4)
- **no thumbnails** in the picker

**Emitters**

- add · remove · **duplicate** · reorder · rename
- **solo / mute**, the way an audio mixer does — isolate one emitter to see what it actually
  contributes. This is also the practical answer to *"not every parameter does something visually"*:
  the user can see it, rather than us guessing which to prune.

**Live preview**

- draws on the **player's position**, as the reference does, so it works with no drop nearby
- **freeze / play** — stop the animation to judge a static gradient
- optionally on a **picked target**, to see it on a real item

**Tweaking**

- **reset a single parameter** to its default
- **copy a colour between the three beam stops and the disc** — most edits are colour, and re-picking
  the same colour four times is the main irritation
- **randomise** a preset or an emitter — a starting point rather than a blank slate
- a **swatch row of the rarity colours** (white / blue / purple / gold / green) so a marker can match
  a rarity in one click

**Cost feedback**

- a live **particles-per-second figure** for the preset. The user owns the beacon budget (max live
  beacons, distance limit, cheap shape), so they should see what a preset costs *before* running
  twenty of them.

**Chunk C is closed.**

### D · Nicholas · **SETTLED**

**The default is the current week.** A user who never opens this gets this week's Nicholas item and
nothing else — the common case needs no configuration.

**Beyond that, the user picks the dates they want to monitor with a date-picker control** — a control
in the same sense as a colour picker. Several dates may be active at once alongside the current week.

That is all this is. A picked date resolves to that week's item; nothing recurs, nothing expires.

**Not related:** the **Calendar widget** (`Widgets/Guild Wars/Calendar.py`) is an *event* calendar, a
different feature. It is not the model for this surface and is not ported.

*Implementation note, separate from the UI:* resolving a date to its cycle entry is still needed. The
cycle is 140 entries, all Mondays, exactly 7 days apart, so any date resolves by modular arithmetic —
and the shipped list must **never** be rebound or grown while doing it (the legacy
`expand_cycle_if_needed` mutates a module global; that bug does not carry over).

**No new control is built.** There is no date picker in `PyImGui` today — nothing in
`stubs/PyImGui.pyi`, nothing in `ImGui_src`. Rather than build one, **the user enters the date with
ordinary controls**. Plain inputs, the date is read from them, done.

Any date entered is normalised to the Monday of its week before resolving, since the schedule is
weekly — so the user need not land on a Monday for it to work.

**Chunk D is closed.**

### E · Quick access · **SETTLED**

#### What it holds

**Groups and filters. There is nothing else to toggle.**

- **groups** — the hand-crafted lists: rarities, materials, dyes, **Nicholas**, trophies, keys and the
  rest
- **filters** — the composite resolvers from the Loot Filter Factory, switched on or off

**The user configures which groups and which filters appear**, Nicholas included. The unit is a group
or a filter — not individual catalog entries.

#### Where that configuration happens

**In System Settings**, like everything else. The quick access configures nothing; it shows what was
configured and lets the user toggle it. *(Already settled under the presentation house rule.)*

#### Appearance

**Already settled — four layouts, the user decides**, per surface, with uniform-apply buttons in
settings:

1. **checkbox list**
2. **checkbox grid**
3. **toggle-button grid** — a button carrying the item's **text**
4. **textured toggle-button grid**

**Where there is no texture, the cell is a toggle button with text.** *(A missing texture inside the
textured layout still falls back to `0-File_Not_found.png` via `get_texture_for_model` — the two are
different things: layout 3 is a choice, the placeholder is a safety net.)*

Collapsible headers remain the container in all four.

**Chunk E is closed.**

### F · Hand lists

#### Levels · **SETTLED**

**The meaningful second level stays. Trophies' alphabetical split is dropped from the data and done at
render time.**

Measured against the catalog rather than assumed — of **52 subgroups, 23 are alphabetical and all 23
are inside Trophies**. The other **29, across the remaining 10 groups, are real taxonomy**:

| group | second level | kind |
|---|---|---|
| Trophies | `A` … `W` (23) | **alphabetical — an index, not a taxonomy** |
| Materials | Common / Rare | meaningful |
| Keys | Core / Prophecies / Factions / Nightfall | meaningful |
| Tomes | Normal / Elite | meaningful |
| Scrolls | Common XP / Rare XP / Passage | meaningful |
| Alcohol · Sweets · Party | 1 / 2 / 3 / 50 Points | meaningful |
| Reward Trophies | Prophecies / Nightfall / Eye Of North / Winds Of Change / Special Events | meaningful |
| Quest Items | Map Pieces / Keys / Dungeon quest items | meaningful |
| Death Penalty Removal | Lucky Points | meaningful |

So:

- the **`subgroup` field survives for 10 groups** and carries only meaningful distinctions
- **Trophies has no subgroups at all** in the data — its 244 entries are one group
- **alphabetical banding is a rendering concern**: sort by name and band the list at draw time. No
  data structure, no second hierarchy level, nothing to maintain.

*Why this matters beyond tidiness:* the alphabetical split was the only thing forcing a general
two-level system with 23 headers over one group. Removing it from the data means the hierarchy exists
only where it means something, and the trophies index costs nothing to change later.

#### Naming · **SETTLED**

**A category contains groups.** The two levels are renamed so the taxonomy reads the same way
everywhere:

| level | was | **is now** | count | examples |
|---|---|---|---|---|
| top | `group` | **category** | 11 | Trophies, Materials, Keys, Tomes, Alcohol, … |
| second | `subgroup` | **group** | 29 | Materials -> Common / Rare · Keys -> Core / Prophecies / Factions / Nightfall |

This makes the two containers parallel, which is the point:

| container | contains |
|---|---|
| **profile** | filters |
| **category** | groups |

**The catalog's field names change with it** — `group` -> `category`, `subgroup` -> `group`. Since the
catalog is package data authored by us, that is a rename in the source, not a migration of user data.

*Reminder of what this interacts with:* Trophies has **no groups** — its alphabetical A…W split was
dropped from the data and is done at render time. So the second level exists for 10 of the 11
categories and carries only meaningful distinctions.

**Chunk F is closed.**

### G · Marking · **SETTLED**

#### What the module is

**A profile holds many filters. Each filter *is* a recolour or a beacon.** The outcome is part of the
filter — it is not a separate "rule" that binds an outcome onto a filter afterwards.

**Each filter resolves its own items, independently.** Multiple filters resolve multiple items. They
are not queued against each other and they are not competing for one drop.

That is the whole module: recolour an item, put a beacon over it.

#### Collisions

**We do not solve collisions.** If a user writes contradicting filters, that is their choice. No
conflict detection, no warnings, no precedence system to configure, no explanation of which filter
won.

*Determinism is still required* — an item carries one colour and must not flicker between frames — but
that is an implementation consequence, not a feature and not something surfaced to the user.

#### Where marking's filters come from

A filter is the **composite resolver**, and composite resolvers are authored in the **Loot Filter
Factory**. A marking profile draws its filters from there, and each one **is** a recolour or a beacon
within that profile.

So chunk B holds unchanged: the Factory owns the composite resolvers; the outcome — recolour or
beacon — is what the marking profile attaches to each. Recolor & Beacons authors no filters of its
own.

#### Correction to an earlier framing

Two questions were asked here from a wrong premise and are withdrawn:

- *"pick an existing filter, then bind an outcome to it?"* — there is no binding step; a filter carries
  its outcome.
- *"which of the two orders resolves colour?"* — filters resolve independently, so there is no queue
  to order. The audit's "two competing orderings" finding was a symptom of the reverted build having
  invented the binding step in the first place.

### H · Feature level

#### H1 — master switch · **SETTLED**

**Yes. The Loot Filters feature has a master on/off switch, in its own Loot Filters section.**

Symmetric with Recolor & Beacons, which already has one. Each feature is standalone, so each owns its
own switch — neither can be turned off from the other's section, and neither depends on the other
being on.

*(In the reverted build `Loot.enabled` existed in the class and nothing exposed it, so the feature
could not be turned off at all.)*
#### H2 — the script surface · **SETTLED**

**The line is between *entries* and *structure*.**

| a script MAY | a script MAY NOT |
|---|---|
| **add a model id** | **create a profile** |
| **add an item id** | **create a set of filters** |
| toggle anything off (or on) | author, rename or delete a filter |
| change the active profile | persist anything |
| report a failed pickup | — |

**Adding a model or an item is imperative and stays.** A script has to handle special cases — a bot
farming one drop needs that drop wanted — and the plan already settled this: *a script may hand the
class **data** — a model id, an item id — values, never something that decides.*

**What is forbidden is structure**: creating profiles, creating sets of filters, and thereby using the
library as a bypass — disable everything the user configured, install your own ruling, and run it
through the class as a proxy.

**On the residual risk, stated plainly:** injecting model ids *can* be abused into a bypass — a script
could add a hundred models and approximate its own filter. **We accept that; there is not much to be
done about it** without removing the capability that makes scripts useful. The guard is against
*structural* substitution, not against every conceivable misuse.

Everything a script does remains **live-only** and is discarded by a reset or a restart.

### I · Presentation

The house rules, all settled in place as they came up:

- **secondary text** — mid gray via `text_colored`, never `text_disabled` (too dim to read)
- **collapsible headers** — the universal container; the structure is uniform, the cell varies
- **`###` ids** wherever a visible label carries a count or state, or the widget loses its state
- **four renderings**, chosen by the user per surface, with uniform-apply buttons in settings
- **bulk `all` / `clear`** at every level where it applies
- **authoring surfaces stand alone**; a feature consumes what they produce

No further rules are being invented up front. Anything else is decided when a surface actually needs
it, and recorded here at that point.

**Chunk I is closed.**

---

## Build order — with gates

Rewritten from `01_class.md`'s build order, with the missing part added: **each step states its
acceptance check up front, and the step is not complete until that check is demonstrated.**

| # | step | acceptance check |
|---|---|---|
| 0 | Native rebuild | `set_item_agent_colors` callable from Python |
| 1 | Package data | counts asserted; every model id resolves or is listed as a defect |
| 2 | Shared filter core | a rule round-trips through storage and matches a known item |
| 3 | **Filter authoring UI** | *a filter can be created, edited and deleted entirely from the UI* |
| 4 | Loot feature | each HAS-ANY input verified individually; blacklist vetoes all |
| 5 | Loot UI + quick access | every surface reachable and persistent across a restart |
| 6 | Profiles | a profile can be created, selected, and observed changing behaviour |
| 7 | Beacon class + preset editor | a preset can be edited and the change seen in game |
| 8 | Marking feature + UI | a rule recolours and beacons a known drop |
| 9 | Migration | callers moved, bypasses gone, old widget retired |
| 10 | LootEx | migrated onto the surface, not severed |

**Note the reordering.** Authoring (3) comes before the feature that consumes it (4), and profiles (6)
and the preset editor (7) are *steps*, not afterthoughts. In the reverted build they were neither, so
they were never built.

---

## Status

**Nothing is implemented. Nothing may be implemented until the register above is answered.**

The register is the work item. Answer it in any order and at any pace; each answer gets written into
this document as settled, and the specification section is then written from the answers.
