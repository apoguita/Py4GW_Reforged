# The Loot Class — design

Built fresh, guided by the owner. Nothing enters this document unless the owner has stated it or
explicitly confirmed it. Prior material is in `legacy/` and is **not** a source of decisions.

**Rules for this document**
- Owner-stated decisions only. No inferred design, no proposals presented as decisions.
- Facts about the existing code may be cited as *evidence*, never as a reason to change a decision.
- Anything unresolved is listed under **Open** and stays there until the owner settles it.

---

## Purpose

*(confirmed)*

The single authority on what loot is wanted.

It watches ground items and answers two questions: **which nearby items should be picked up** (the loot
array), and **which items get a recoloured label or a beacon**.

It never walks, interacts, picks up, or decides *when* it is safe to loot — other code owns that.

Only the user changes its saved configuration, through its UI. Scripts may add transient, run-scoped
entries that are never saved.

Every loot decision in the repo goes through it.

---

## Two modes: PERSISTED and LIVE

*(confirmed)*

| | **Persisted (stock)** | **Live** |
|---|---|---|
| what it is | the user's configuration and filters, on disk | what the class is actually running right now |
| who writes it | **the user, through the UI. Nobody else.** | stock, plus anything scripts have added |
| lifetime | until the user changes it | the session / the run |
| scripts | **cannot write it at all** | may read it **and change it freely** |

**Live starts as an exact copy of stock.** A script may then change anything in it. Because nothing a
script does is persisted, the stock config is always intact and always recoverable.

**Stock vs modified is observable.** The class can always answer: *am I running stock, or has this been
changed?* — and *what* differs. Since a script may change any switch, switch profile and add entries,
what is surfaced is a **difference from stock**, not merely a list of additions.

### How it is surfaced *(confirmed)*

**The label appears in both the quick access and the settings.** *(confirmed)* Not one or the other —
the quick access is what the user has in front of them while playing, and the settings is where they go
to change things, so both must say when what they are looking at is not what is running.

| | |
|---|---|
| **Always visible, when live differs from stock — in *both* surfaces** | a **label**: *"a script is changing these settings"* — no attribution needed, no detail, just the fact |
| **On demand** | a **separate window** showing the configuration currently being handled in live |

*This also covers the standalone case:* **Recolor & Beacons has no quick access**, so its label lives in
its settings section — which works precisely because the label is a settings-surface element too, not a
quick-access-only one.

That split is deliberate: the always-on part must be cheap and impossible to miss, while the detail —
what actually differs — is opened only when the user wants it. The label is the notification; there is
no separate alert, and no announcement on every change (a script may touch settings continuously).

*Structural consequence:* to show what differs, the class holds the **stock snapshot in memory
alongside live** for the whole session. That is what makes both the label and the detail view possible,
and it is also what the one-action reset restores from.

**Live is never reset automatically.** A script's operation may span several maps, so a map change is
not a valid boundary and neither is anything else the class could guess. Live simply **stays active
until something resets it**. Three things end it:

- **the user resets it** from the UI — always available;
- **a script resets it** at runtime, when it knows its own run is over;
- **a restart** — nothing live was ever persisted, so the class comes back on stock.

**Because nothing expires on its own, visibility is the safeguard.** The class must make it plain when
it is **not** running stock — the user should be able to notice, see what differs, and clear it in one
action. A modified live state that nobody can see is the failure case this design is guarding against.

---

## What the class does

**1. Watches the ground.** It looks at the ground items around the player and evaluates them against the
current configuration.

**2. Produces the loot array.** Its primary output: which nearby items are worth picking up. Consumers
take that answer and act on it.

**3. ~~Decides and applies the marking.~~ — MOVED OUT.** *(superseded: marking is a **separate
class**; see *Two classes, not one*.)* Marking remains independent of pickup — an item can be marked
without being wanted, and wanted without being marked — but it is no longer this class's job.

**4. Owns the configuration.** The permanent loot policy is its own — it holds it, loads it and saves it
itself. It does not depend on a widget being loaded to have settings, and no other component owns or
persists loot state.

**5. Owns its own transient state.** Run-scoped entries and failed-pickup suppression live inside the
class and are applied inside its own evaluation, with a lifetime it manages. Consumers do not keep loot
state of their own.

**6. Is the single authority.** Every loot decision in the repo comes from it. There are no private loot
filters, no parallel loot arrays, no second opinion.

### The class exposes consumers — never generators or evaluators

*(confirmed — this is the actual principle; earlier framings about wiping and toggling were too literal)*

**What must be prevented is a script injecting rules that are evaluated somewhere else.** The class
exposes surfaces that **consume** its decisions. It exposes nothing that lets a script supply the
**evaluation** itself.

**Data in, decisions out. Never logic in.**

- A script may hand the class **data** — a model id, an item id, the criteria of a filter. Values.
- A script may **never** hand the class **something that decides** — a callback, a predicate, a lambda,
  a rule whose matching code lives outside the class.
- **All evaluation happens inside the class**, over data the class owns, using the class's own matcher.

**The current class violates this directly.** `AddCustomItemCheck(check_function)`
(`Lootconfig_src.py:671`) stores a **callable** in `custom_item_checks` and the class invokes it at
`:846`. The verdict is produced by code the class does not own; the class merely relays it. That is an
**external evaluator living inside the class**, and it is the thing being designed out.

**Why this makes the `Rule` shape the right one.** A `Rule` (`agent_recolor/model.py:64-90`) is **pure
data** — fields and values, no behaviour. The matching logic lives in the module that owns the rules.
A script adding a filter is therefore adding a *specification*, not an evaluator: it describes **what**
to match, and the class alone decides **how** matching is performed and what the answer means.

**The test for any future API:** does this let a caller state *what they want*, or does it let a caller
supply *how to decide*? The first is a consumer. The second is an evaluator and must not exist.

*(The live/persisted boundary is a separate and complementary guarantee: it governs **durability** —
nothing a script changes outlives the session. This rule governs **authority** — no ruling ever
originates outside the class.)*

### The user's model is the stored model

*(confirmed)*

**What the user sees must be what is actually stored and evaluated.** A rarity toggle is a rarity
toggle — it must **never** be implemented by writing entries into a list. If toggling purple rarity
turns into a whitelist change, then the thing the user manipulates and the thing the class stores are
different objects, and every guarantee about "the user's configuration" becomes ambiguous.

*This is the general form of a defect already found twice:* the gold-coin toggle secretly injecting
`ModelID.Gold_Coins` into the whitelist (`LootManager.py:137-138`, `:152-154`, `:168-169`, `:438-443`),
and the per-item `rarity_filter` flag that meant "do not clear me" (`:759`). Both are the same mistake —
a control whose stored representation is something other than what it claims to be.

### Two classes, not one

*(confirmed)*

**Loot and marking are two separate classes**, surfaced as **two subcategories under the Items
category** in System Settings:

| subcategory | class | owns |
|---|---|---|
| **Loot** | the loot class | what is **wanted** — the loot array |
| **Recolor & Beacons** | the marking class | what is **highlighted** — label colour, BLANK, and beacons |

Everything already decided about marking — HAS-ANY resolution, order resolving colour and preset, the
bulk `(agent_id, colour)` push, BLANK via full transparency, the pooled beacon singleton,
user-configured beacon budget — belongs to the **marking class**.

**They are different features and are not linked.** Marking began inside the looting class, but it is
its own feature.

**Each one must be standalone.** *(confirmed)* Neither feature depends on the other: **Recolor & Beacons
works with the loot feature absent or switched off, and the loot feature works with marking absent or
switched off.** Neither may import the other, and neither may require the other to be enabled.

**So there are three pieces, not two:**

| piece | role |
|---|---|
| **the shared filtering core** | the `Rule` shape, the criteria vocabulary, the operators, HAS-ANY resolution, ordering, and the **shared filter store** |
| **the Loot feature** | decides what is **wanted** — standalone |
| **the Recolor & Beacons feature** | decides what is **highlighted** — standalone |

**The core is owned by neither feature.** It cannot live inside the loot class with marking reaching
into it, because that would make marking depend on loot. It is a common component both build on, and it
is where "they share most functionality" is actually expressed.

**Colouring and beaconing are the same procedure.** An item is chosen to be marked by **filter criteria**
— exactly as items are chosen to be looted — and **on match a marking filter may recolour, beacon, or
both**. The two outputs are checkboxes on the marking filter, not two separate mechanisms.

**Both features use the same filtering, and the filters live in a shared area.** *(confirmed)* Filters
are **global-scoped** either way, so there is no reason to duplicate them per feature: **one shared
store of filter definitions**, usable by both.

*What this means concretely:*
- **A filter is criteria — nothing else.** It describes *what matches*. It does not carry what happens
  on a match.

  > **Read with G, so this is not misread as a contradiction:** a "filter" is the **composite
  > resolver**, authored in the Loot Filter Factory as criteria only. The **outcome** is what a
  > feature's profile attaches to it. So *"each marking filter is a recolour or a beacon"* and *"a
  > filter is criteria only"* describe the same object from opposite ends — the Factory's definition,
  > and a profile's use of it.
- **Each feature binds its own outcome** to the filters it uses: the loot feature's outcome is *wanted*;
  the marking feature's outcome is *recolour and/or beacon* (the two checkboxes). The same filter can
  therefore be used by both without either feature inheriting the other's behaviour.
- **"Different features, not linked"** still holds: using the same criteria definition is not the same
  as sharing behaviour. Neither feature's outcome leaks into the other, and each keeps its own profiles
  and its own ordering.

*What is shared:* the `Rule` shape, the criteria vocabulary, the equal-or-better / contains operators,
HAS-ANY resolution, user ordering — **and the filter definitions themselves**, in a shared global area.

### What it does not do
- It does not walk to items, target them, interact with them, or pick them up.
- It does not decide *when* looting is appropriate (combat, danger, bag space, pacing).
- It does not identify, salvage, vendor, or manage inventory.

---

## What scripts may access

A script (bot, routine, widget) interacts with the class in three ways, and **only** these: it asks
questions, it adds entries to the list, and it reports failures.

### 1. It asks questions

- **"What is worth grabbing near me?"** — the loot array.
- **"Is there anything worth grabbing?"** — a cheap yes/no, for code that only needs to gate movement or
  decide whether to start a loot cycle.
- **"Is this specific drop still wanted?"** — a single-item check.
- **"Should I pick up this one?"** — a per-item verdict, for code holding one candidate.

### 2. It changes the LIVE state — and only the live state

**A script may never persist anything. Never — whatever it does is in memory and no change of its
ever reaches disk.** That part is absolute and unchanged.

> **Refined since:** *"a script may change anything"* is too broad. The line is between **entries** and
> **structure**: a script **may** add a model id or an item id and toggle things, and **may not**
> create profiles or sets of filters. See `implementation-spec.md` H2.

A script may:

| | example |
|---|---|
| **change any switch** | turn a rarity toggle on or off for the duration of its run |
| **use any profile** | switch which profile is in use |
| **add entries** | a **model id**, an **item id**, or a **filter** |
| **add blacklist entries** | including reporting a drop it could not pick up |

**All of it lands in LIVE. None of it is written to disk.** The persisted configuration is the user's
alone — it is changed only by the user, only through the UI.

**Where the safety comes from.** Not from restricting what a script may touch, but from **the mode
boundary itself**: nothing a script does outlives the session, so the stock configuration is intact by
construction and is always a valid restore point. A misbehaving script can make a mess of a session; it
can never change what the user chose and can never damage a setup. Recovery is always the same single
action — reset live back to persisted.

**Reading the live state.** A script may inspect what is currently running — including whether the
class is on stock or has extras on top — so script activity is visible rather than mysterious.

**Recovery is always reset-to-persisted.** Nothing rebuilds a live state entry by entry, and no script
can reconstruct what the user had. The single recovery action is the **reset to stock** defined above
(user reset, script reset, or restart), and it works for exactly one reason: **the persisted config is
never writable by a script**, so it is always intact and always a valid restore point. That makes stock
the **recovery source**, not merely the default — a second, independent reason it must stay
script-unwritable.

**Wiping stays prohibited — but for the right reason.** *(confirmed)* Not because it is unrecoverable
(the live/persisted split fixes that), but because **a wipe is the mechanism by which a script nils the
class** — see *What this is actually protecting against* below. Adjusting the live state is fine;
zeroing it out so nothing of the class's own ruling remains is not. These destructive operations exist
today as first-class bot steps and do not carry forward:

| exposed today | where |
|---|---|
| `ClearWhitelist` | `Py4GWCoreLib/botting_src/helpers_src/Items.py:73-78` |
| `ClearBlacklist` | `Items.py:81-86` |
| `ClearDyeWhitelist` | `Items.py:155` |
| `RemoveFromWhitelist` | `Items.py:70`; also `Sources/ApoSource/InvPlus/LootModule.py:129` |
| `RemoveFromBlacklist` | `Items.py:54` |
| `SetProperties` — overwrites all five toggles at once | `Bots/Example Bots/VaettirBot (Sequential).py:467` |

### 3. It reports back

- **"I could not get this one."** The class records the failure and stops offering that drop, applying
  the suppression inside its own evaluation. Scripts do not keep their own lists of failed items.

### What scripts may never do

- **Save anything to disk.** This is the one absolute. **The only configuration and filters that
  persist are the ones the user sets manually in the UI.** A script may change the live state freely;
  it may never make that change outlive the session, and therefore needs no save/restore ritual.
- **Filter loot themselves.** No private loot arrays, no hand-rolled "should I take this", no separate
  skip-lists, no second filter. If a script needs something the class cannot express, that is a gap in
  the class to be fixed — not a reason to work around it.
- **Toggle the user's settings.** Read-only, always.
- **Depend on the user's settings** to make their own decisions.

---

## What we are actually filtering

*(owner's framing — the design follows from this, not the other way round)*

Drops fall into a few kinds, and **what we can ask about each kind is different**. Loot is always
unidentified, so the data available at decision time is what shapes each surface.

**This table says what is *informative* about each kind — it does NOT restrict which filters may be
used on it.** Every filter applies to every item; the point is only that some facts tell you a lot about
one kind and nothing about another.

| kind | what is actually informative about it, unidentified |
|---|---|
| **Armor** | little beyond identity — runes are the reason to take it, but nothing about them is visible unidentified |
| **Weapons** | **mods** — the one kind that exposes real per-drop detail before identifying |
| **Consumables, keys, event items, and the like** | it is simply that item or not — identity is the whole answer |
| **Dyes** | their own small structure (the colour) |
| **White items — the majority of all drops** | they are **salvageables and trophies**; both can be salvaged into materials |

Notes that follow from this:
- **Runes are salvaged out of armor**, which is why armor is worth taking at all — but nothing about the
  runes is visible on an unidentified drop, so it cannot be filtered on.
- **The hand-crafted lists organise trophies, dyes, event items, keys and similar.** They exist because
  those things are identified by *being that item*, not by any property.
- **Whites are the bulk of the universe.** They are reached either by being a listed trophy, or by what
  they salvage into.

## Filters

### Two categories, and only two

*(confirmed)*

| | **Hand-crafted** | **Configurable** |
|---|---|---|
| what it is | curated lists — trophies, event items, keys, dyes, materials and the like | filters the user builds |
| why it exists | those things are identified by **being that item**; no property describes them | the item exposes real data, so a condition can describe it |
| who authors it | us, shipped with the class | the user, in the UI |
| the user's control | toggles entries and groups on and off | writes the condition |

Both are needed and neither replaces the other. This was settled early and is not reopened: a
configurable filter cannot express "is a trophy", and a hand list cannot express "requirement 7-8".

### Configurable filters take the form of the mods handling

*(confirmed — this is the central structural decision)*

The configurable filters are **built in the shape of the existing mod handling**, so the library has
**one cohesive way of handling filters** rather than a second, unrelated grammar invented for loot.

**The mods handling is the *form*, not the *scope*.** Mods are one subject a filter can talk about — the
richest one, and the reason the shape was worth adopting — but **value and everything else we can read
are filtered the same way, through the same structure**. There is no separate mechanism for "the
non-mod ones".

*Evidence this fits:* the mods surface is already value-routed and already carries the AND/OR pair the
filters need — `HasMod` (`Py4GWCoreLib/Item.py:127`), `HasAllMods` (`:168`), `HasAnyMods` (`:179`), over
`mods_core.py` / `mods_types.py`. The composition rule stated above is the shape that surface already
has, not a new mechanism.

### What the configurable filters cover

**Everything about an item we can read, in one vocabulary applied to any item.** Not a per-category
allowance, and **not a closed list** — the aim is to cover as much of what an item exposes as we
usefully can. Named so far:

- **mods** — the richest subject, and where the shape comes from;
- **value** — worth more than X gold (new; we do not have this today);
- **type**, **model**, **name**;
- **salvages into a given material** — take it for what it breaks down into (new). This is what makes the
  huge un-listed salvageable-white population reachable without enumerating any of it;
- **dye colour**.

These are examples of the vocabulary, not its limit. Anything else an item exposes that is worth
filtering on belongs here too, and is expressed the same way.

**Filters are composite** *(this section is about the **configurable** branch only — the hand-crafted
lists are membership, never composition).* Conditions combine with **AND** *and* **OR** — not one or the other — so a
filter can be as detailed as needed: a weapon type *and* a requirement, or one material *or* another.

**Subjects mix freely inside one filter.** A single filter may combine conditions from completely
different subjects. The owner's example, which the design must support:

> item **type**, **and** name **contains** …, **and** **value** …, **and** a **requirement**, on a weapon.

That is four conditions from four different families in one filter. Consequence: filters are **not**
organised into per-family groups ("weapon filters", "value filters"); there is one condition list and
any subject may appear in it.

**A condition is a subject *and* how it is compared.** The same example makes this explicit — those four
do not match the same way: `name` is a **contains**, `value` and `req` are **equal-or-better**, `type` is
simply the item being that thing.

### The operator set is closed: equal-or-better, and contains

*(confirmed)*

There are only two, and neither is a free choice — each follows from the subject:

| | applies to | meaning |
|---|---|---|
| **equal or better** | every numeric subject | **there is no exact-equals.** A number always means *this or better* |
| **contains** | **names only** | substring match. **No other subject supports it** — a contains does not make sense on anything else |

**`equals` is not an operator.** Numbers are never matched exactly, and identity subjects like `type` or
`model` are not a comparison at all — the item either is that thing or it is not. There is nothing for
the user to choose there.

### Numeric conditions: same ruling as the mods — "that or better"

*(confirmed)*

A numeric condition means **"that value or better"**, exactly as the mods already work — and **each
subject declares its own direction of "better"**:

| subject | better is |
|---|---|
| weapon **requirement** | **lower** |
| **value** | **higher** |
| … | whatever that subject declares |

This is not a new mechanism. The mods system already does precisely this: `better_low` is a per-mod
declaration (`Py4GWCoreLib/mods_core.py:58` — *"requirement etc. -> lower is better"*), Requirement is
declared with `better_low=True` (`mods_core.py:85`), and the comparison routes on it
(`Item.py:152-160`, via `mods_core.is_better`, `:255`). The decision is to **extend that same
per-subject declaration to every numeric subject**, so `value` is simply a subject whose direction is
*higher*.

Consequence: the class does not carry a table of hard-coded comparison rules. Each subject carries its
own, the way each mod already does.

---

## The hand-crafted lists

### Two independent hand-crafted rules — never conflate them

*(confirmed — this was stated after the two were wrongly mixed once)*

The hand-crafted branch is **not one rule**. It holds at least two kinds, and they are **independent**:

| | **the rarity toggles** | **the hand lists** |
|---|---|---|
| what it says | take whites / blues / purples / golds / greens | take *these specific items* |

**Neither gates the other, and the absence of one does not invalidate the rest.** The user can say
*"pick up no whites at all, except the ones I configured under trophies, or keys, or whatever"* — and
both halves of that sentence must hold at once. A hand-list entry stands on its own merit; it is not
conditional on the rarity toggle for its rarity being on.

*Evidence the existing behaviour already matches this:* in `GetfilteredLootArray` the whitelists are
checked at `Lootconfig_src.py:811-817` and append **unconditionally**, *before* rarity is consulted at
`:819-843`. A whitelisted trophy is therefore taken today even with `loot_whites` off.

### Composition belongs to the configurable branch only

*(confirmed)*

The **AND / OR composition** decided under *Filters* applies to the **configurable filters and nothing
else**. The hand-crafted lists are **membership** — an item is on a list or it is not. They are not
composed, not combined with operators, and not expressed as conditions.

### Ground truth — what exists today *(evidence, not design)*

Verified against the live data, `json/Global/Widgets/LootManager/modelid_drop_data.json`, read at
`Widgets/Guild Wars/Items & Loot/LootManager.py:44`.

**Shape.** A **flat list of 403 records**. Each record is
`{name, model_id, group, subgroup, drop_info}` — all five present on all 403. The two-level
category -> subgroup structure is **derived from the `group`/`subgroup` string fields**, not stored as a
tree. `model_id` is a **string** (`"ModelID.Bottle_Of_Rice_Wine"`) that must resolve against the
`ModelID` enum; unresolvable strings are the source of the entries that never match anything.

**Inventory — 11 groups, 52 subgroups, 403 items:**

| group | items | subgroups |
|---|---|---|
| **Trophies** | 244 | `A` `B` `C` … `W` — **alphabetical, 23 of them** |
| Materials | 36 | Common Materials (11), Rare Materials (25) |
| Keys | 24 | Core (3), Prophecies (8), Factions (7), Nightfall (6) |
| Tomes | 20 | Normal (10), Elite (10) |
| Quest Items | 18 | Map Pieces (4), Keys (8), Dungeon quest items (6) |
| Alcohol | 15 | 1 Points (10), 3 Points (4), 50 Points (1) |
| Reward Trophies | 15 | Prophecies (1), Nightfall (4), Eye Of North (2), Winds Of Change (1), Special Events (7) |
| Sweets | 13 | 1 Points (7), 2 Points (5), 50 Points (1) |
| Scrolls | 10 | Common XP (3), Rare XP (3), Passage (4) |
| Party | 7 | 1 Points (4), 2 Points (2), 50 Points (1) |
| Death Penalty Removal | 1 | Lucky Points (1) |

**Two facts that bear on any decision here:**

1. **Trophies is 60% of the catalog and its subgroups are an alphabetical index, not a taxonomy.**
   23 of the 52 subgroups are single letters. For the largest group, the second level carries no
   meaning — which is why the surface reads as hundreds of undifferentiated rows.
2. **Dyes are not in the catalog.** They are generated at runtime by iterating the `DyeColor` enum into
   a synthetic `Dyes` / `Colors` group (`LootManager.py:262-274`), with a fabricated
   `model_id` string `f"ModelID.{dye.name}_Dye"`. So the hand lists today come from **two different
   sources**, not one.

*(Also on disk and separate again: the Nicholas cycle data. Prior verified note: use `NICHOLAS_CYCLE`,
which carries `model_id`, rather than name-matching `Nick_cycles.json`.)*

### Decisions

**1. Trophy subgrouping stays alphabetical.** *(confirmed)*

There is **no metadata to organise trophies by other than their names**, so no better grouping is
available. Alphabetical is not chosen because it is good; it stands because nothing else exists to
distinguish one trophy from another. Any different organisation would require new metadata to be
authored first.

**Two axes were considered and are closed — do not raise either again:**

- **Rarity.** *All trophies are white*, so rarity cannot tell one trophy from another. Nothing more
  than that — it does **not** mean the rarity toggle covers trophies; see *Two independent
  hand-crafted rules* below.
- **A model-id based lookup** over universal salvage metadata:
  `model id -> {common, rare} materials`). **Model ids span the entire item universe, not trophies** —
  that data is universal item metadata, not trophy metadata, so it cannot organise trophies. Raising it
  was a mistake; it is recorded here only so it is not proposed a third time.

**2. Nothing is generated at runtime.** *(confirmed)*

**Dyes and everything else are catalog data.** The current behaviour — building the `Dyes` group by
looping the `DyeColor` enum at setup and fabricating `model_id` strings
(`LootManager.py:262-274`) — does not carry forward. There is **one source** for the hand lists, and it
is the data, not code that manufactures entries at startup.

**3. `model_id` need not be a string, but must resolve to the enum.** *(confirmed)*

The stored form is free — it does not have to be the `"ModelID.Xxx"` string it is today. What is
required is that **every entry resolves against the `ModelID` enum**. An entry that does not resolve is
a defect, not a silently-inert row: today's unresolvable strings are exactly why some catalog entries
never match any drop.

---

## The rarity toggles

### Ground truth *(evidence)*

Five toggles — **white, blue, purple, gold, green** — plain booleans, evaluated at
`Lootconfig_src.py:820-843` as five independent *"is this rarity **and** is its switch on -> take"*
checks, with no interaction between them. Order of authority in the current filter: blacklists
hard-block (`:804-808`), then hand lists take unconditionally (`:811-817`), then rarity
(`:819-843`), then custom checks (`:846`).

### Decisions

**1. Gold coins is a real toggle and must work.** *(confirmed)*

The user must be able to toggle **gold coins alongside any rarity** — it is an independent switch, not
an alternative to them, and combining it with any rarity selection is valid.

*How it actually behaves today — chased through the code:*

**The toggle works, but by injecting into the hand list.** Turning it on does not enable a gold-coin
rule; it **adds `ModelID.Gold_Coins` to the whitelist**, at four sync points, all inside the widget:
`LootManager.py:137-138`, `:152-154`, `:168-169`, and the checkbox at `:438-443`. The filter then
takes coins through `IsWhitelisted` (`Lootconfig_src.py:815`) — the hand-list branch.

*Three defects follow from that, and none of it carries forward:*

1. **A rarity-side switch mutates the hand list.** This is exactly the conflation of the two
   independent rules forbidden above. `:443` even calls `RemoveFromWhitelist(coin_mid)` on untoggle,
   which would silently delete a gold-coin entry the **user** had added by hand.
2. **It only works when the widget is loaded.** All four sync points live in `LootManager.py`. Any
   consumer using `LootConfig()` directly sees `loot_gold_coins = True` and gets **no coins**, because
   `GetfilteredLootArray` never reads the flag. This is the most likely cause of the feature appearing
   silently deactivated.
3. **The one piece of real gold-coin logic in the filter is unreachable.** `Lootconfig_src.py:751`,
   hardcoded `return True` and ignoring the toggle, inside `IsValidLeaderItem` — whose only caller is
   the leader/follower block at `:777-787`, which is **inside a triple-quoted string**, i.e.
   commented-out. It never executes.

**Decision — the gold handling changes; it does not survive the migration.** *(confirmed)*

Gold coins are honoured **by the class itself, driven by the toggle**, with:
- **no widget involvement** — it must work for any consumer of the class, with no widget loaded;
- **no writing into the hand list** — the toggle never adds or removes a whitelist entry, so it can
  never destroy an entry the user put there;
- **no reliance on the commented-out leader/follower path.**

Porting the current mechanism forward is explicitly ruled out.

### The loot lock — structure the class must respect *(evidence)*

Gold coins are **always unassigned** (`owner_id == 0`), so which account may take one is coordinated.
**The class does not own that coordination — it only observes it.**

- **There is no gold-specific lock.** There is one general **loot lock**, keyed by item agent id, over
  ShMem: `is_loot_lock_blocked` (`WhiteboardLocks.py:576`), `post_loot_lock` (`:616`),
  `clear_loot_lock` (`:658`), `filter_unlocked_loot_items` (`:604`).
- **It targets exactly the unassigned case** (`owner_id == 0`) — the gold-coin case by definition.
- **Claiming belongs to the pickup path**, not here: `Widgets/System/Messaging.py:1682`,
  `Py4GWCoreLib/routines_src/yield_src/items.py:265`, `:350`,
  `Py4GWCoreLib/routines_src/Sequential.py:602`.
- **The class reads it, read-only**, inside `IsValidItem` (`Lootconfig_src.py:729`), to drop items
  another account has already claimed. That consultation must be preserved — dropping it breaks
  multi-account contention.

**2. Scope: toggles are account-scoped.** *(confirmed; refined later — see *Profiles and scope*)*

The toggles are **per account**. (Consistent with today: `rarity_filter_data.json` is opened with no
scope argument and `JsonFactory.__new__` defaults to `'account'`, `JsonFactory.py:89`.) The 403-entry
catalog is shipped reference data and is not part of this.

**Superseding note:** the scope rule is not uniform across the whole singleton. **Filters are global**;
**profiles and toggles are per account.** See *Profiles and scope* below.

**3. The per-item `rarity_filter` flag is dropped.** *(confirmed)*

**It is not a feature.** It does not carry forward in any form.

*What it was* — a second boolean grafted onto every catalog row at runtime alongside `enabled`
(`LootManager.py:256`, `:271`), persisted into the user's config (`:71-73`) and exports (`:178-181`).
It is **not** in the shipped catalog, whose rows carry only `name, model_id, group, subgroup,
drop_info`, and it appears in **no design document**.

*Why it is not a feature* — of the seven sites that touch it (`:111`, `:114`, `:221`, `:225`, `:256`,
`:271`, `:759`), **six only write or initialise it**. The single read is the *Clear Whitelist* button
(`:759`), and even there the effect is **cosmetic**: `ClearWhitelist()` on the line above has already
wiped the real whitelist for every row, protected or not. The flag spares only the **checkbox**, which
then re-adds the item on the next whitelist rebuild (`:141-149`). It desynchronises the display from
the filter and protects nothing. `Lootconfig_src.py` has never heard of it.

---

## The blacklists

### Ground truth *(evidence)*

Three exist today, and they are not alike:

| list | holds | role | persisted |
|---|---|---|---|
| `blacklist` | **model ids** | **the strongest rule in the system** — evaluated first (`Lootconfig_src.py:807`), before hand lists and before rarity, so a blacklisted model beats an explicitly whitelisted one | yes |
| `item_id_blacklist` | **agent ids** (despite the name) | failed-pickup suppression | no — transient |
| `dye_blacklist` | dye ids | **none — zero readers anywhere** (`Lootconfig_src.py:655-668`) | — |

*On `item_id_blacklist`:* `GetfilteredLootArray` returns **agent ids**; `Messaging.py:1678-1684` carries
them in variables named `candidate_item_id` / `item_id` and stores them via `AddItemIDToBlacklist`
(`:1692`, `:1713`, `:1742`, `:1756`); the filter reads back with an agent id (`:804`). It works because
both sides are consistently "wrong" about the name. Cleared by `Environment Upkeeper.py:97`,
`Bots/marks_coding_corner/VoltaicSpearTeamFarm.py:197`, and bot step `Items.py:130`.

*On `dye_blacklist`:* `AutoInventoryHandler.py:520` has its own unrelated `deposit_dyes_blacklist`; it
is not this list.

### Decisions

**1. The dye blacklist is dropped.** *(confirmed)*

**Dyes are covered by a hand-crafted list.** A separate dye blacklist is not needed and does not carry
forward. It has no readers today in any case.

**2. Identity is by model id, and by item id as well.** *(confirmed)*

**The model id is the one we use** — the primary identity for a loot rule. **The item id is also
useful** and is kept: it is how a rule names *one specific drop* rather than a kind of item.

**3. For ground drops, "item id" means the agent — this is the game's model, not a defect.** *(confirmed)*

A dropped item **is an agent** in the game's own mental model, so the id that identifies one specific
drop is the agent id. The fact that `item_id_blacklist` holds agent ids is therefore **accepted and
intentional**. It is not to be "fixed" by renaming it into a different concept.

*Consequence to resolve in implementation:* the two lists must then agree on that id space, and today
they do not — `item_id_blacklist` is read with the **agent id** (`:804`) while `item_id_whitelist` is
read with a **real item id** (`:811`, from `item_data.item_id`). A script that takes an id out of the
loot array (an agent id) and adds it to the item-id whitelist will therefore never match. The
bot-facing helpers (`Items.py:90`, `:114`) pass through whatever the caller hands them, so nothing
catches it.

---

## The whitelists

### Ground truth *(evidence)*

Three exist today:

| list | holds | read at | populated by |
|---|---|---|---|
| `item_id_whitelist` | real item ids | `Lootconfig_src.py:811`, first | only bot helper `Items.py:90` |
| `whitelist` | model ids | `:815` | the enabled catalog rows (`LootManager.py:142-149`) + gold-coin injection |
| `dye_whitelist` | dye ids | **never read** | UI only |

Both live lists append **unconditionally** and therefore beat rarity.

**Dyes cannot be picked up at all today — severed twice, independently:**
1. `IsDyeWhitelisted` (`Lootconfig_src.py:648`) has **zero callers**; the filter never consults it. The
   list is only saved (`LootManager.py:182`), defaulted (`:292`) and displayed (`:666`).
2. The model-whitelist rebuild **excludes them by group** — `item.get("enabled") and
   item.get("group") != "Dyes"` (`LootManager.py:143`).

The dye surface is therefore UI-only: a user can tick dyes, see them listed and save them, and no dye
will ever enter a loot array.

*Also at the end of the chain:* `custom_item_checks`, a list of arbitrary callables evaluated last
(`:846`, added via `AddCustomItemCheck`, `:671`), with one user —
`Sources/frenkeyLib/LootEx/loot_handling.py:50`.

### Decisions

**1. There is no whitelist as a concept.** *(confirmed)*

**Whitelisting is a *result*, not a rule.** The hand-crafted lists and the filters already decide what
is wanted — an item is wanted because a list entry is on, or because a filter matched. A separate
whitelist sitting above them is redundant and does not carry forward.

**2. What survives is direct addition — by model id, or by item id.** *(confirmed)*

The one thing a whitelist was still needed for is **naming something directly**:

| add | means |
|---|---|
| **a model id** | want this kind of item |
| **an item id** | want this one specific drop (an agent, per the game's model) |

This is the same surface scripts may add to (see *What scripts may access*) — the difference is only
that the user's additions persist and a script's do not.

**3. Custom item checks are dropped — no overrides.** *(confirmed)*

`custom_item_checks` is an **override**, and overrides are not wanted. A list of arbitrary callables
that can declare any item wanted, evaluated last (`Lootconfig_src.py:846`, registered via
`AddCustomItemCheck`, `:671`), is precisely the "second opinion" the single-authority rule forbids. It
does not carry forward in any form.

*What this affects:* this hook is **frenkey's LootEx entire loot integration**. `loot_handling.py:50`
registers `Should_Loot_Item` as the check — and the same `Start()` also writes into the user's blacklist
directly (`:52-53`, `AddToBlacklist(6102)`, `AddToBlacklist(6104)`). So LootEx today both installs an
override **and** writes user configuration. Both are disallowed under the new rules.

**Decision — LootEx is migrated, not severed.** *(confirmed)* It comes onto the new surface — filters
and additive entries — like every other consumer. It is **not** to be left cut off, disabled, or
working around the class. **Scheduled at the end**, after the class itself is in place.

**4. The dye whitelist is dropped.** *(confirmed)*

Dyes are a **hand-crafted list**, like trophies and keys. They need no list mechanism of their own —
which also removes both of the severances above, since dyes stop being a special case excluded from
the normal path.

---

## Marking — recolour and beacons

*(designed from the ground up. The existing implementation is **not** the basis for this section.)*

### What it is

**One feature: highlighting important loot.** Recolour and light beacon are two expressions of the same
thing, not two systems.

### Decisions

**1. Marking uses virtually the same filters as the loot decision.** *(confirmed)*

The same filter surface answers both *"do I want this?"* and *"should this be highlighted?"*. Marking
does not get a filter language of its own.

**2. The hand-crafted lists collapse for marking.** *(confirmed)*

For marking purposes the curated lists are **collapsed down to the match kinds** — model id, name, type,
rarity and the like. Marking works on those, not on the list structure.

**3. Delivery is one array of `(agent_id, color)`, sent at once.** *(confirmed)*

Agent recolour already works by sending **a list of `(agent_id, colour)` pairs**. **Item marking works
exactly the same way:** the class prepares the whole coloured array and sends it over in a single call.

Consequences, which are the point of choosing this shape:
- **The class resolves everything itself.** All matching, all priority, all conflict resolution happen
  in the class, which then emits one already-decided colour per agent.
- **Priority is therefore ours to define**, not something inherited from the backend. Because the class
  ships resolved per-agent colours, whatever ordering the user configures is honoured — the backend is
  only painting the answer, never choosing between rules.

#### Backend gap — the batch call does not exist for items *(verified)*

The `(agent_id, colour)` bulk contract exists and is documented in the header, **but only for agents and
gadgets**:

> *"Bulk replace: swap the WHOLE per-agent store to exactly `rules` (agent_id, argb). Python computes
> the full matched set each pass and hands it over in one call; ids not present are dropped."*
> — `Py4GW_Reforged_Native/include/GW/agent_recolor/agent_recolor.h:129-133`

`SetGadgetColors` has the same contract (`:157`). **Ground items (`:166-178`) have no bulk form** — only
per-id `SetItemAgentColor` (`:172`). Confirmed at the binding layer too: `set_agent_colors`
(`src/GW/agent_recolor/agent_recolor_bindings.cpp:33`) and `set_gadget_colors` (`:65`) exist; for items
there is only `set_item_agent_color` (`:87`). The stub matches (`stubs/PyAgentRecolor.pyi:59`, `:103`
batch; `:131` singular).

**GAP CLOSED — the batch path now exists at every layer.** *(implemented; awaiting a Native rebuild)*

| layer | added |
|---|---|
| header | `void SetItemAgentColors(const std::vector<std::pair<uint32_t,uint32_t>>& rules);` — `agent_recolor.h`, ground-items section |
| implementation | `AgentRecolor::SetItemAgentColors` — `agent_recolor.cpp`, mirrors `SetAgentColors` exactly (lock, clear `item_agent_rules_`, refill, `RebuildItemSnapshotLocked`) |
| binding | `m.def("set_item_agent_colors", ...)` — `agent_recolor_bindings.cpp` |
| stub | `set_item_agent_colors(rules: list[tuple[int, int]]) -> None` — `stubs/PyAgentRecolor.pyi` |
| wrapper | `AgentRecolor.SetItemColors(rules)`, plus `EnableItems` / `AreItemsEnabled` / `ClearItemRules` — `Py4GWCoreLib/AgentRecolor.py`, which previously had **no item surface at all** |

Semantics match `SetAgentColors`: ids not present are dropped, and the item_id / model / name / type /
rarity stores are left untouched.

**Still requires a Native rebuild before it is callable at runtime** (done manually by the owner).

**Confirmed: only the bulk call is wanted.** The per-kind item setters (`set_item_model_color`, `set_item_name_color`,
`set_item_type_color`, `set_item_rarity_color`) remain unexposed in the Python wrapper. They exist in
the binding and stub, and stay unexposed. Under this design the class resolves matching itself and
pushes resolved per-agent colours, so the bulk call is the whole delivery surface.

**4. Beacons need a class of their own.** *(confirmed)*

`light_beacon.py` is the **reference for the effect that is wanted** — it is a test script for tuning
those effects, and its saved state is a worked example: **a beacon for a purple item**
(beam gradient `[0.73,0.53,0.93]` -> `[0.51,0.05,0.98]` -> `[0.16,0.00,0.32]`, with a matching ground
disc). A class is needed to handle beacons.

### Marking specifics

*(confirmed)*

**5. Marking resolves exactly like pickup — HAS-ANY.** Colouring is decided the same way as wanting: if
any rule matches, it applies. There is **no class-imposed precedence** between rules and no "topmost
wins" ranking to configure. **Conflicts are the user's to manage through their own profiles and
filters**, not something the class arbitrates.

*Implementation note:* one agent can only carry one colour, so when several rules match the result must
still be **deterministic** (never flickering between frames). Deterministic, but deliberately not a
user-facing priority system.

**6. Colour and beacon are independent choices, both explicit.** A rule carries **two checkboxes** —
*colour this* and *beacon this* — and the user decides each. A rule may do either, both, or neither.
Marking and colouring are **sister features**, not one feature with a variant.

**7. Transparency is a first-class feature: BLANK.** *(confirmed — and it must not be left implicit)*

Sending a **fully transparent colour blanks the item** — it disappears from the loot labels the user
sees on screen. This is a real capability and must be **surfaced as a named feature**, not left as
something a user only discovers by knowing that alpha `0x00` happens to do it.

Stated uses: **hiding unwanted drops**, **hiding loot not assigned to us**, and anything else the user
wants gone from view. It is a *visual* action only — blanking a label does not change whether the item
is wanted.

**8. Beacon cost is configured by the user, not capped by us.** The user sets:
- a **maximum number of live beacons**;
- **distance filtering** — beacons only within a chosen range;
- optionally a **very low-cost shape for distant beacons** (a cheap stand-in instead of the full effect);
- **the particles and the entire appearance**.

The class does not impose a hidden budget; it gives the controls and the user decides the trade-off.

**9. The beacon class is an optimised singleton, with beacons reusable and addressable.** Beacons are
not created and destroyed ad hoc — they are **pooled and reused**, and each is **addressable** so it can
be updated, moved or released without rebuilding it. The class is built for the cost this feature
carries.

**10. The reference config is the default, not the only option.** `light_beacon.py`'s tuned state is
**the preferences that are wanted** and ships as the default. **The user must be able to configure their
own** — every part of the anatomy below is exposed, not baked in.

### What a beacon consists of *(evidence, from the tuned reference)*

From `light_beacon.py:63-94` (state) and `:30-51` (emitter surface) — this is the shape a beacon class
has to carry:

| part | parameters |
|---|---|
| **beam** | shape (crossed quads / cone), quads, segments, blend mode (alpha / additive / MAX), glow strength, glow scale, glow shells, mid stop, **three gradient colours** (base / mid / top), height, base width, top width, rows |
| **ground** | disc colour, disc radius, rings, ring speed, ring thickness, ground lift (anti-clip), additive flag |
| **behaviour** | anchor mode (fixed world position vs. follow), anchor x/y, pulse |
| **emitters** | a **list** of independent particle emitters, each a full config: enabled, mode, additive, colour, plus emit *(rate)*, launch *(dir x/y/z, speed, speed var, spread)*, physics *(gravity x/y/z, drag, turbulence)*, orbit *(radius, radius var, radius end, spin, rise, height)*, shape *(spawn radius, radial speed, stretch)*, life/size *(life, life var, size, size var, size end, hot frac)* |

---

## Nicholas the Traveller items

*(confirmed)* **They are trophies on a schedule.** The user may want to farm **this week's, next week's,
or any** week's item — so the class must resolve the Nicholas item for an arbitrary date, not just today.

**The cycle is already handled by the Calendar widget; port that to Py4GWCoreLib and use it.** No new
implementation, no duplicated data.

### Mechanics *(confirmed)*

**1. Both forms exist — relative and pinned.**

| form | stores | behaviour |
|---|---|---|
| **relative** | the intent (e.g. *the current week*) | **re-resolves as time passes** — never a fixed model id |
| **pinned** | a specific week / date | always that week's item, regardless of today |

A resolved model id is **never** what gets stored for a relative selection; it would go stale every
Monday.

**2. Several may be active at once.** Nicholas selection is a **set**, not one choice — this week's and
next week's and any pinned weeks can all be on together, which is what makes farming ahead possible.

**3. Rollover is immediate — and the result is cached.** When the week turns over, a relative selection
re-resolves **at once**, mid-session, with no restart. A long-running bot therefore changes what it
collects the moment the week rolls.

**The resolved model ids are cached; they are not recomputed per evaluation.** The value changes at most
once a week, so walking the cycle on every pass would be pure waste. The cache is invalidated by exactly
two things:

- **the week changing** — a trivial check (today's Monday vs the cached Monday), not a cycle walk;
- **the selection changing** — the user or a script turning a week on or off.

That preserves immediate rollover at effectively zero cost: the per-evaluation work is a date
comparison, and the cycle is walked only when it actually produces a different answer.

**4. It feeds the same HAS-ANY.** A Nicholas match is simply another reason an item is wanted, with **no
special precedence**. It is still subject to the blacklist veto like everything else.

**Consequence for the implementation:** what is stored for a relative selection is the **intent**, never
a resolved model id — but resolution itself happens **once per week**, into the cache. The porting trap
below still matters: a resolver that mutates and grows the shared cycle would corrupt it on every
cache refill.

### What is where *(evidence)*

- **The data is already in corelib.** `NICHOLAS_CYCLE` lives in `Py4GWCoreLib.enums`; the widget merely
  imports it (`Widgets/Guild Wars/Calendar.py:19`).
- **The logic is in the widget** — two functions, and these are what gets ported:
  - `expand_cycle_if_needed(day)` (`Calendar.py:66-97`) — extends the cycle backwards or forwards in
    whole cycle lengths so **any** date resolves.
  - `get_nicholas_for_day(day)` (`:100-116`) — normalises to the Monday, expands, returns the entry.

**Trap to fix while porting:** `expand_cycle_if_needed` declares `global NICHOLAS_CYCLE` (`:68`) and
**rebinds it**, mutating shared module state and growing the list on every out-of-range query. Moved
into corelib as-is, that would mutate the shared cycle for every consumer and grow without bound. The
ported version must resolve a date without mutating the shared dataset.

*Cross-reference available:* frenkey's `Sources/frenkeyLib/LootEx/data/items.json` carries a
`nick_index` field on **137 items**.

---

## Materials

*(confirmed)* **The material list comes from frenkey's metadata — extract the list of materials that
are obtained from items.** No hand-authoring.

### Sources *(evidence)*

- `Sources/frenkeyLib/LootEx/data/materials.json` — **36 materials**, keyed by `ModelID`, with
  multilingual names.
- `Sources/frenkeyLib/LootEx/data/items.json` — **3689 items** across 35 item types. Each record
  carries `common_salvage` and `rare_salvage`, shaped
  `{material name: {amount, min_amount, max_amount, model_id, name}}`. **2028** items have a common
  salvage entry, **1095** a rare one.

### Extracted result

**34 distinct materials are obtainable from items.** The common/rare split is clean per material — a
given material is one or the other, never both:

| | materials |
|---|---|
| **common salvage** (11) | Iron Ingot (876 items), Wood Plank (789), Pile of Glittering Dust (473), Bone (229), Granite Slab (214), Tanned Hide Square (160), Bolt of Cloth (109), Chitin Fragment (63), Plant Fiber (43), Scale (26), Feather (14) |
| **rare salvage** (23) | Steel Ingot (765), Bolt of Silk (84), Bolt of Linen (81), Leather Square (65), Spiritwood Plank (58), Monstrous Eye (35), Monstrous Fang (24), Roll of Parchment (21), Tempered Glass Vial (16), Ruby (15), Monstrous Claw (13), Diamond (12), Sapphire (11), Lump of Charcoal (7), Vial of Ink (6), Fur Square (5), Jadeite Shard (4), Amber Chunk (3), Roll of Vellum (3), Onyx Gemstone (3), + Gold/Silver/Copper Zaishen Coin |

### Materials are also a pickup surface *(confirmed)*

**A hand-crafted list is needed for picking up materials as drops in their own right** — separate from
using materials as the *target* of a salvages-into filter. Both exist: what an item breaks down into,
and wanting the material itself when it drops.

*This data already exists.* The catalog's **Materials** group is exactly these 36 items
(Common Materials 11, Rare Materials 25) and matches `materials.json` item-for-item — the only
differences are capitalisation (`Bolt Of Cloth` vs `Bolt of Cloth`). It was a gap in the discussion, not
in the data.

### Frenkey data is copied in, never referenced *(confirmed)*

**The needed data is copied into this project.** The class does **not** read from
`Sources/frenkeyLib/LootEx/data/*.json` at runtime — no cross-project dependency on another library's
files. Extraction happens once and the result becomes our own data.

### The catalogs are package data, not JSON *(confirmed — this overrides any earlier wording)*

**The class must not use JSON for its catalogs.** `JsonFactory` exists for **user-generated data**, and
the JSON store is **gitignored**. The catalogs — the item catalog, the materials list, the salvage
mapping, the Nicholas data — are **part of the package**: enums, dicts, Python source, shipped and
version-controlled with the code.

*Verified, and this is exactly what broke the previous attempt:* `.gitignore:53` ignores `json/**`, and
**`git ls-files json` returns zero tracked files** — `json/Defaults/` included. The 403-item catalog
therefore exists only on the machine that generated it; a fresh clone has **no catalog at all**. That is
why the earlier build ran against empty `{}` documents, and it is unfixable inside the JSON store.

**The split is by ownership, not by convenience:**

| | lives as | why |
|---|---|---|
| **Catalogs / reference data** | **package data** (enums, dicts, Python) | shipped, versioned, identical for everyone, never edited by a user |
| **The user's configuration** | `Settings` / `JsonFactory`, account-scoped | user-generated, per-account, legitimately gitignored |

**Two reconciliations to be aware of:**
- **5 of the 36 are never a salvage output** — Bolt of Damask (927), Glob of Ectoplasm (930), Elonian
  Leather Square (943), Obsidian Shard (945), Deldrimor Steel Ingot (950). They are crafted or drop
  directly, so they cannot back a *salvages-into* filter.
- **3 salvage outputs are not in `materials.json`** — the Zaishen coins (31202 / 31203 / 31204), which
  are not crafting materials.

---

## Failed-pickup suppression

*(investigated on request — the suppression **is** happening, but not only in this layer)*

It exists in **three places**, and the class is only one of them:

**1. In the class.** `item_id_blacklist` (holding **agent** ids) is consulted at
`Lootconfig_src.py:804`. But it is populated **from outside** — the pickup path reaches in:
`Widgets/System/Messaging.py:1692` (loot exit reason), `:1713` (path-follow failed), `:1742` (timeout),
`:1756` (exit reason again). Cleared by `Widgets/System/Environment Upkeeper.py:97`,
`Bots/marks_coding_corner/VoltaicSpearTeamFarm.py:197`, and bot step
`botting_src/helpers_src/Items.py:130`.

**2. In the standard pickup routine, privately.** `LootItemsWithMaxAttempts`
(`routines_src/yield_src/items.py:325-419`) keeps its **own** `failed_items` list (`:340`), appending on
unreachable (`:381`) and after `max_attempts` (`:404`) — then **returns** it (`:419`). **The class is
never told.** Failure knowledge flows *out* of the system instead of *in*.

**3. In individual bots, privately again.** `Bots/marks_coding_corner/DervFeatherFarm.py:61` keeps a
module-global `item_id_blacklist = []` and grows it from the returned failures (`:167-169`).

**This confirms the rule already recorded** under *What scripts may access* (3): a script **reports** a
failure and the class applies the suppression inside its own evaluation. Layers 2 and 3 are exactly the
private skip-lists that must not survive.

### Decision — suppression is not a separate mechanism *(confirmed)*

**All of this functionality is achieved by adding an item or a model to the blacklist.** There is no
dedicated suppression store, no parallel skip-list, no second concept to design: *"I could not get
this one"* is simply **a blacklist entry**, by item (this one specific drop) or by model (this kind).

Consequences:
- **The `item_id_blacklist` as a distinct store disappears.** Suppression and the user's blacklist are
  the same list, differing only in who added the entry and whether it persists.
- **The addition is LIVE, never persisted.** A script reporting a failure is adding to the live
  blacklist. It never touches the user's saved blacklist — that would be writing user configuration,
  which is forbidden. A restart or a reset-to-stock clears every suppression, by construction.
- **The additive verb covers both directions.** A script may add an entry meaning *want this* and an
  entry meaning *do not offer this again*. Both are additive, both are live-only, and neither can
  remove or alter anything the user configured.

### Decision — id-based blacklist entries are cleared on map change *(confirmed)*

**Agent ids and item ids do not survive a map change** — the numbers are per-instance and mean nothing
in the next map. Carrying them across would suppress an unrelated drop that happens to reuse the id.

- **Cleared on map change:** every entry keyed by **agent id** or **item id**.
- **Not cleared:** entries keyed by **model id** — a model id is stable, so it stays until the user or a
  reset removes it.

This is a correctness rule, not a policy choice, and it applies regardless of who added the entry.

---

## Rule resolution

*(confirmed)*

**1. The blacklist is the strongest rule, because its job is to inhibit every other rule.** If an entry
is blacklisted, nothing else can bring it back — not a hand list, not a filter, not a direct addition,
not a rarity toggle. It is an absolute veto, evaluated first.

**2. Everything else does not fight — it is a HAS-ANY.** The positive rules are not ranked against each
other and there is no precedence contest between them. An item is wanted if **any** of them says so:

> blacklisted -> **never**.
> otherwise: hand list **or** filter **or** direct addition **or** rarity toggle -> **wanted**.

This is why the earlier "first match wins" framing was wrong, and why the two independent hand-crafted
rules can coexist without one suppressing the other: they are all inputs to the same OR.

---

## Filters are Rules — the same pattern the rest of the library uses

*(confirmed)*

**Filters have names, can be toggled, and can be configured — exactly like the rules already handled in
other System Settings modules, such as the agent recolour filters.** The goal is **one cohesive
filtering system** across the library, not a loot-specific invention.

### The pattern to mirror *(evidence)*

`Py4GWCoreLib/py4gwcorelib_src/system_settings/agent_recolor/model.py:64-90`:

```python
@dataclass
class Rule:
    id: str                       # stable id (UI selection / removal)
    name: str = "New rule"        # user-facing label
    enabled: bool = True          # individually toggleable
    ...
    color_rgb: int = 0xFF0000
    mode: str = MODE_SOLID        # SOLID | FADE | HIDE
    alpha: int = 0x40             # only when mode == FADE
    # criteria, as fields on the rule:
    kinds: List[str]              # any-of
    model_ids: List[int]          # any-of
    professions: List[int]        # any-of
    name_substr: Optional[str]    # case-insensitive substring
    level_min / level_max, hp_min / hp_max
    states: List[str]             # all-of
    agent_id: Optional[int]       # pin one specific agent
```

**What this settles by adoption:**
- **Identity:** every filter is `id` + `name` + `enabled` — nameable, individually switchable, removable.
- **Composition is per-criterion, not an expression tree.** List criteria are *any-of*, and a criterion
  like `states` is *all-of*. Multiple criteria on one rule combine as AND. That is how the earlier
  "composite, AND *and* OR" decision is expressed concretely, and it matches the mods surface
  (`HasAllMods` / `HasAnyMods`).
- **Marking mode is already modelled** — `mode` = SOLID / FADE / HIDE plus `alpha` maps exactly onto the
  native item recolour's alpha semantics (`0x00` blanks the label, low alpha fades it).
- **Pinning one instance** — `agent_id` is the precedent for our item-id entry.

### Profiles and scope

*(confirmed)*

**There are multiple filters, and multiple profiles.** A profile holds its own set of filters, so
different profiles can run entirely different filtering.

**The scope split is by what the thing *is*, not by which module owns it:**

**The line is between a *definition* and its *use*: definitions are shared, selections are local.**

| | scope | why |
|---|---|---|
| **The filters themselves** | **global** | a **shared pool** — a filter written once is available everywhere |
| **Profiles** | **global** | a profile is a definition too — **so profiles can be shared** between accounts, not rebuilt per account |
| **Which profile an account uses** | **per account** | the *usage* of a profile is local: each account runs whichever it wants |
| **Toggles** | **per account** | rarity switches, hand-list entries and everything else this account switched on |

So a filter is authored once into the global pool, profiles are composed once and shared, and each
account only chooses **which** profile it runs plus its own toggles. Nothing an account selects affects
another account, and no account can lose a filter or profile another account authored.

**Scripts may change the profile at runtime — never persistently.** *(confirmed)* A script can switch
which profile is in use while it runs. Like every other live change it is **not saved**: the profile the
user chose is untouched on disk, and a reset-to-stock or a restart returns to it. **Persisting a profile
choice is the user's alone.**

### Persistence precedent from the same module *(evidence)*

`agent_recolor/store.py`: **one document**, `Widgets/System/Agent Recolor.ini`, via **`Settings`** —
used at **both scopes**, `global` for the rules and `account` for the toggles — with the rules
serialised as **JSON text stored inside the INI** (`rules_to_json` / `rules_from_json`, `:55-59`).
**This precedent matches the decision above** — that module also keeps its **rules global** and its
**toggles per account**. The loot class extends the same shape with **profiles** (per account) between
the two.

---

## The loot-array query — what the topic is

*(explanation; the decision is still open)*

Every consumer calls one method. Today:
`LootConfig().GetfilteredLootArray(distance, multibox_loot, allow_unasigned_loot)` (`:714`).

| parameter | status |
|---|---|
| `distance` | **real** — how far to look (default `Range.SafeCompass`) |
| `multibox_loot` | **dead** — appears only in the signature (`:714`), never referenced in the body. **18 callers pass it by keyword.** |
| `allow_unasigned_loot` | **dead** — referenced only at `:755` and `:782`, both inside the commented-out leader/follower block. **8 callers pass it.** |

**Their intent was absorbed and became mandatory**, which is why they are inert rather than merely
unused: cross-account coordination is now the **loot lock**, consulted unconditionally at `:729`; and
unassigned items are now accepted outright by `IsValidItem` (`:731` allows `owner_id == 0`).

**Decision — both dead parameters are removed.** *(confirmed)* `multibox_loot` and
`allow_unasigned_loot` do not carry forward. Their behaviour is already unconditional, so removing them
changes nothing at runtime and only removes the illusion of control.

**All call sites are retrofitted.** The 20 existing `GetfilteredLootArray` callers are updated as part
of the migration — 18 pass `multibox_loot` and 8 pass `allow_unasigned_loot`, **by keyword**, so they
fail loudly rather than silently if missed. That is the desired outcome: no caller keeps passing a flag
that means nothing.

---

## Persistence layout

*(confirmed — option **(b)**: split by shape, within the two sanctioned classes)*

**`Settings` for flat values, `JsonFactory` for structured collections.** Both are the mandated
persistence classes; the split is by what the data *is*, matching the definition/selection split above.

**Not persisted at all:** the catalogs (package data — enums/dicts in source), anything a script
changed (live only), and any **item-id or agent-id** entry (those numbers do not survive a map change).

### Global — shared definitions, `JsonFactory("…", "global")`

| document | holds |
|---|---|
| the **shared filter store** | every `Rule`: id, name, enabled, **criteria only** — used by both features |
| **profiles** | per feature — name, which filters compose them, and that feature's outcome per filter (marking: the recolour / beacon checkboxes) |
| **beacon presets** | the full beacon anatomy, including the variable-length emitter list; ships with the tuned reference config as the default |

These are collections with nested, variable-length structure — genuinely documents, not settings
values. `set_json` also dedups unchanged subtrees (`Widgets/System/Enemy Tracker.py:162`), which matters
while a preset is being edited live.

### Account — selections and toggles

**`Settings` (one INI, account scope) — flat values only:**

| section | holds |
|---|---|
| general | which profile is in use; master enables |
| rarity | white, blue, purple, gold, green, **gold coins** |
| beacons | max live beacons, distance limit, low-cost-shape settings |
| quick access | display mode (texture grid / checkbox table), which surfaces are shown |
| nicholas | which cycle/weeks configuration |

**`JsonFactory("…", "account")` — the account's id lists**, which are structured despite being simple:

| document | holds |
|---|---|
| the account's **selections** | enabled hand-list **model ids** (hundreds), blacklist **model ids**, direct-addition **model ids** |

### Notes

- **Document names follow the existing convention** — the module lives under System Settings, so
  `Widgets/System/…` as with `Widgets/System/Agent Recolor.ini`.
- **Where this diverges from the agent_recolor precedent, and why:** that module stores its whole rule
  list as a JSON string inside one INI key (`store.py:46`, `:52`). That is fine for a handful of rules;
  loot carries hundreds of hand-list ids and deeply nested beacon presets, which would become large
  opaque blobs in INI values. The *pattern* (global definitions, account toggles, `Rule` as pure data)
  is kept; only the container differs.

---

## Filter ordering

*(confirmed — option **(b)**)*

**Filters carry an explicit user-controlled order, and it resolves exactly two things.**

| | resolved by | why |
|---|---|---|
| **Is it wanted?** | **HAS-ANY** — order irrelevant | any enabled matching rule is enough |
| **Beacon on or off?** | **HAS-ANY** — order irrelevant | a boolean; any matching rule with the box ticked turns it on |
| **Which colour?** | **topmost matching rule wins** | one agent can carry only one colour |
| **Which beacon preset?** | **topmost matching rule wins** | single-valued, same problem |

**This is not a priority system for the loot decision.** Order has **no effect** on whether an item is
picked up, and none on whether a beacon appears. It exists solely as the conflict resolver for the two
outcomes that cannot hold more than one value.

**Why an explicit order rather than an internal tiebreak:** a single-valued outcome needs *some*
deterministic winner or the label would flicker between frames. Making that order **the user's** is what
gives substance to "conflicts are the user's to manage" — a user who sees the wrong colour reorders the
list, instead of having to rewrite the criteria of a rule that is otherwise correct.

Cost: one position per rule. The user reorders in the UI; the order lives with the filter pool, which is
global, so a reordering is shared like the filters themselves.

---

## The class API

*(confirmed)*

### Shape: live and persisted are two instances of the same config class

**The configuration is a class; the singleton holds two instances of it** — **stock** (what is persisted)
and **live** (what is actually running). They are the same type, not two different structures.

Everything the two-mode design needs falls out of that:

| operation | becomes |
|---|---|
| **live starts as a copy of stock** | instantiate live from stock |
| **reset to stock** | replace live with a fresh copy of stock |
| **am I modified?** | compare the two instances |
| **what differs?** | the diff of the two instances — feeds the quick-access detail view |
| **a script changes something** | it changes the **live** instance; stock is untouched and unreachable |
| **the user changes something** | the UI changes **stock**, which is the only one that is saved |

No separate "overlay" or "extras" bookkeeping is needed, and there is no way for a live change to leak
into stock, because they are simply different objects.

### Driving: a registered callback, declared to the perf monitor

Marking must be pushed whether or not anyone asks for a loot array, so the class is **driven by a
callback**, exactly as other System Settings modules are
(`agent_recolor/controller.py:168-207`):

- `PyCallback.PyCallback.RemoveByName(name)` first — idempotent across reloads;
- `PyCallback.PyCallback.Register(name, PyCallback.Phase.Data, fn, priority=…, context=PyCallback.Context.Update)`;
- **`ProfilingRegistry().register(name)` — declare it profilable to the perf monitor**;
- the callback body routes through `reg.runcall_scope("widgets", f"{name}:data", …)` when a capture is
  active, so the cost is attributable;
- unregistered by `RemoveByName` when switched off.

The callback owns the pass: evaluate, then push the resolved `(agent_id, colour)` array in one call.

### Query: cached per frame

**Queries are cached per frame — there is no recomputation within a frame.** This uses the existing
decorator, `@frame_cache(category=…, source_lib=…)`
(`py4gwcorelib_src/FrameCache.py:131`, exported as `frame_cache` from `Py4GWCoreLib`). Two consumers
asking in the same frame walk the agent array once.

### Surfaces

**Query (consumers).** The loot array — **renamed to `GetLootArray`** — taking `distance` only, with
`multibox_loot` and `allow_unasigned_loot` gone. Plus the cheap *"is there anything worth grabbing"*
boolean, *"is this specific drop still wanted"*, and the per-item verdict.

**Live mutation (scripts).** Change any switch, use any profile, add a model id / item id / filter, add
a blacklist entry, report a failed pickup. Every one of these acts on the **live** instance.

**Introspection.** Stock-or-modified, and the diff — required by the quick-access label and its detail
view.

**Reset.** Live back to stock, one action, available to the user and to a script.

**Marking.** Applied by the class from its own callback. It is **not** a query — no consumer asks for
colours.

**Persistence.** Saving belongs to stock alone, and only the UI reaches it.

---

## The UI

*(confirmed so far — layout is not yet defined)*

### Where it lives

Under the **Items** category in System Settings, as **two subcategories**: **Loot**, and
**Recolor & Beacons** — one per class.

*Wiring precedent:* a custom `Category(key=…, title=…, icon=…, listeners=())` whose sections are built
by the owning package's `config_ui.add_sections(win, group)`, lazily imported, with a build failure
surfaced as a **visible placeholder section** rather than an empty one
(`system_settings/config_ui.py:135-161`; `model.py:130-141`).

### The quick-access window

**The quick access is for looting options only.** *(confirmed)* **Recolor & Beacons has no quick
access** — it is configured in System Settings and nowhere else. This does not weaken either feature's
standalone status: the quick access is a convenience surface belonging to the loot feature, not a shared
dependency.

**It is a window** — opened from the settings module — and **the user configures what goes in it**.
Contents are the user's choice, added freely; nothing is fixed.

**On a fresh install it shows:**

- **rarities**
- **materials**
- **dyes**
- **Nicholas items**

**It also carries the live-state label** — *"a script is changing these settings"* — whenever live
differs from stock. The same label appears in the settings surface.

### Presenting the hand-crafted lists — two views

*(confirmed. This applies to the **hand-crafted lists**; filters are presented differently.)*

The hand lists are the dense data — hundreds of entries — so how they are drawn is the whole problem
the current tree gets wrong.

| view | what it is | trade-off |
|---|---|---|
| **grid of textured icons** | the **most compact** presentation possible | **UI-heavy** — many textures to render |
| **matrix of names** | the next best thing: the same grid, text instead of textures | far cheaper, less compact |

**The user toggles between the two views.** Textures are assumed resolved. This is the Inventory+ style
— a dense grid of small targets — and explicitly **not** the hundreds-of-rows tree the current Loot
Manager shows.

**This is where the tooltip comes from.** In the icon view an icon alone does not identify the item, so
**every icon carries a hover tooltip** showing its data. The tooltip is not decoration — it is what
makes the compact view usable at all.

> ~~**The view toggle is reachable from both the quick access and the settings.**~~ **SUPERSEDED** —
> all configuration lives in **System Settings**; the quick access configures nothing and only follows
> what was set. See `implementation-spec.md` P2.

**Filters are presented differently** — they are named, ordered rules, not a dense grid of items, so
neither of these two views applies to them.

### Layout foundation — tabs, in both surfaces

*(confirmed)*

**Tabs are used in the quick access as well as in the settings**, so **the screen is never cluttered
with every option at once** — one surface is visible at a time.

**Appealing, but not fancy.** These are **quick-access buttons**. The layout should look good and stay
compact; it is not a showcase.

> ~~**Structure chosen (round 1): top tabs.**~~ **SUPERSEDED** — see `implementation-spec.md`
> "Navigation — collapsible headers, not tabs". Groups are **stacked collapsible headers**, not a tab
> strip: a long row of tabs is worse than none, and ImGui has no multi-row tab bar. This also stops the
> quick access being the one surface with its own navigation idiom.

**One tab = one category. No nested tabs.** *(confirmed)* A tab holds a category and shows its items
directly — no sub-tabs and no subgroup picker.

**Where a visual subgroup is genuinely needed, use a collapsible header.** *(confirmed)* The catalog's
own second level (`Materials -> Common / Rare`, `Keys -> 4 campaigns`, `Trophies -> A…W`) can be carried
by collapsible headers **inside** the tab, each holding its group. That is the only nesting device —
headers, not tabs, and only where a subgroup actually helps.

*Implementation note:* a collapsing header whose visible label carries a **count or state** must use a
`###id` suffix, not `##id`, or it loses its open/closed state every time the count changes.

**A search box, where it earns its place.** *(confirmed)* Its purpose is to **locate an entry faster**
in a large category. It is **not useful on small groups**, so it is not shown where it would only take
space — a six-entry Rarities tab does not need one. No fixed threshold is set here; the rule is that it
appears where the category is large enough for finding an entry to be a real problem.

**The window is resizable by the user, minimum 300 x 300.** *(confirmed)* The layout must work at that
minimum and make use of extra space when the user grows it.

### The live view

**A separate window with the details** of what is currently running in live — not a tab inside the
quick access.

### Not yet defined

- **The layout detail.** The foundation is set (tabs, compact, not fancy); the arrangement within a tab
  is being worked out from structural sketches.
- ~~**Tooltip content.**~~ **Settled**: every icon carries a hover tooltip showing the item's data —
  that is what makes the icon view usable at all, since an icon does not identify itself.
- **The System Settings section breakdown** within each of the two subcategories.

---

## Build order

*(confirmed)*

**0 · Native rebuild.** `SetItemAgentColors` is written at every layer but not compiled. Gates step 4
only; earlier steps proceed without it.

**1 · Package data.** The catalogs as **source**: item catalog (403), materials (36, with the 34 salvage
outputs), the salvage mapping, dyes, and the Nicholas resolver ported out of `Calendar.py` **without**
the global-mutation bug. *First, because its absence is silent* — this is exactly what broke the
previous attempt, and everything downstream is untestable against empty data.

**2 · Shared filtering core.** `Rule`, the criteria vocabulary, equal-or-better with per-subject
direction, names-only `contains`, HAS-ANY, ordering, and the global filter store. **Owned by neither
feature.** Both features are blocked on it.

**3 · Loot feature.** Stock/live instances, `GetLootArray` and the query forms, blacklist veto, hand
lists, rarity toggles with working gold coins, Nicholas with its weekly cache, direct additions,
map-change clearing of id entries, the loot-lock read, callback registration with the perf monitor,
`frame_cache`, profiles, persistence.

**4 · Beacon class, then Recolor & Beacons.** Beacon first — pooled, addressable singleton from the
`light_beacon.py` reference — since the marking feature configures it. **Requires step 0.**

**5 · UI.** The two System Settings subcategories, the loot quick access, the live-detail window.

**6 · Migration.** Retrofit the 20 callers to `GetLootArray` with the dead parameters gone; remove the
bypasses — the private `failed_items` list (`routines_src/yield_src/items.py`), `DervFeatherFarm`'s
module-global skip list, the destructive bot steps (`botting_src/helpers_src/Items.py`), and
`Messaging.py` writing the class's blacklist directly; retire the Loot Manager widget to legacy.

**7 · LootEx.** Migrated onto filters and additive entries — **not severed**.

**Notes on ordering:** steps 3 and 4 are genuinely independent once 2 exists, since the features are
standalone by decision. Step 6 should not be deferred far — until the callers are retrofitted, the old
`LootConfig` and the new class coexist and the single-authority guarantee is nominally violated.

---

---

## Open

*(nothing outstanding at the level of **what**)*

Every decision this plan records is settled. What remains is **how** to build it, and that is a
separate document by design: see `implementation-spec.md`, which carries the decision register
that must be answered before any code is written.

This plan is the *what*. It does not authorise implementation on its own.

