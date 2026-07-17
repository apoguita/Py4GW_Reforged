# 11 — Item-Mod System: Research & Design (for approval)

> Status: **research + proposed design, no code written.** This document is the dedicated
> analysis of the modifier system as it exists in three references — frenkey's JSON model,
> our own `item_mods_src`, and your prior `Examples/itemcompare.py` — reconciled with what
> live items actually contain. It ends with a concrete enum-based design and the decisions
> that need your sign-off before anything is built.
>
> Goal restated: **an item yields a list of int modifier words → match each by identifier
> (a foreign key) → apply that mod's formula → produce resolved data** (value + typed
> subtype), on which filters like *"shield, req ≤ 9, Tactics"* are trivial.

---

## Part A — How the system actually works

### A1. There are exactly two tiers of object

| Tier | What it is | Key |
|---|---|---|
| **Raw word (atom)** | one 32-bit `ItemModifier`: `identifier(16) \| arg1(8) \| arg2(8)` | `identifier` = **int** (`mod >> 16`) |
| **Named mod (composite)** | an applied prefix/suffix/inscription/rune/insignia, OR an inherent base stat, made of **1–3 raw words** | a **name** (string) |

An item is a flat `list[raw word]`. A named mod is recognised when *all* of its constituent
raw words are present. This two-tier split is consistent across all three references — it is
the backbone of any correct design.

### A2. Identifier convention — pick game-native, and know the trap

Three conventions exist in the repo for the same modifier:

| Convention | Formula | Example (Requirement) | Used by |
|---|---|---|---|
| **game-native** | `mod >> 16` | `0x2798` (10136) | frenkey JSON, `itemcompare.py`, `ModId`, live items |
| stripped | `(mod >> 20) & 0x3FF` = `native >> 4` | `0x279` | `item_mods_src` |
| — | — | — | — |

**Recommendation: game-native (`mod >> 16`).** It is what your `itemcompare.py` already uses,
what frenkey's raw words use, and what the live `PyItem.modifiers` yield. The stripped form is
**lossy** — `0x27E8 / 0x27E9 / 0x27EA` (three distinct Health variants) all collapse to `0x27E`.
Never mix the two; convert only at a boundary if we ever touch `item_mods_src`.

### A3. The atom's formula = "which arg is the value, which arg is an enum index"

A raw word's two bytes are **not** interchangeable. Per identifier, each arg plays one role:

- a **numeric value** (armor 8, chance 20%, req level 9, health 30), or
- a **foreign key** — an *index into a catalog enum* (attribute id, damage type, species), or
- a **fixed discriminator / selector** (the "Fiery" word: arg1 = the damage type it converts to), or
- **unused**.

frenkey encodes this per raw word as `ModifierValueArg ∈ {Arg1, Arg2, Fixed, None_}` plus
`Min`/`Max` bounds on the value arg. Your `itemcompare.py` encodes the same thing as a per-arg
**eval function** (identity `Value()` vs a catalog lookup `GetAttributeName`/`GetDamageType`/…)
plus a **representation** template. **They are the same model expressed two ways.**

### A4. The formula is stable per identifier (the fact that makes an enum model viable)

Empirical result from mining `weapon_mods.json` + `runes.json` (355 named mods, 479 raw words,
**62 distinct identifiers**):

- **60 of 62 identifiers use exactly ONE `ModifierValueArg`** → a single formula keyed by
  identifier is correct for them.
- **Only 2 are inconsistent** and need a per-mod override, not a per-identifier one:
  - `0x22D8` (Energy): `Fixed`×1, `Arg2`×3
  - `0x2532`: `Fixed`×1, `None_`×3

This is the load-bearing finding: **a per-identifier formula table is sound**, with two named
exceptions. Everything else keys cleanly off the identifier.

### A5. Catalog foreign keys — the COMPLETE map

Across all three references the enum-indexed arg is **always arg1**, and the enum is chosen by
identifier. The full set (game-native hex):

| Catalog enum | Identifiers (native hex) | Meaning | Where the enum lives |
|---|---|---|---|
| **Attribute** (46) | `0x2418`, `0x28A8`, `0x21E8` | requirement / rune / +1 attribute | `enums.py` ✓ |
| **DamageType** (17) | `0x24B8`, `0xA118`, `0x2118` | damage type / armor-vs-type | `enums.py` ✓ |
| **species** (11) | `0x2148`, `0x8080` | "vs. / of \<species\>slaying" | `ItemBaneSpecies` in `item_mods_src` ⚠ |
| **Ailment** / **Reduced_Ailment** (8) | `0x2468`, `0x2478`, `0x2858` | lengthen/reduce condition | `enums.py` ✓ |
| **Inscription** (15) | `0xA532` (inscription-name word) | which inscription | `enums.py` ✓ |
| **Weapon** / **ItemType** | `0x25B8` (target item type) | which item type the mod applies to | `enums.py` ✓ |

Every catalog already exists as an enum. The **only** placement wart: the species catalog
(`ItemBaneSpecies`, equivalent to frenkey's `EnemyType`) lives in `item_mods_src/types.py`, not
in `GameData_enums.py`, and isn't re-exported. One relocation decision (§B-D4).

### A6. Base stats and upgrades share ONE identifier space

Base/inherent stats (requirement, damage, damage type, armor, energy) are **not** stored in any
JSON — they exist only as raw words on the live item, and both frenkey and `item_mods_src`
decode them through the **same** identifier table as upgrades. Their formulas (verified against
live items and `item_mods_src/upgrade_parser.py`):

| Base stat | native id | formula |
|---|---|---|
| Requirement | `0x2798` | subtype = `Attribute(arg1)`, value = arg2 (req level) |
| Damage (range) | `0xA7A8` | **range** = (min=arg2, max=arg1); damage **type is a separate word** |
| Damage type | `0x24B8` | subtype = `DamageType(arg1)` |
| Shield/base armor | `0xA7B8` | value = arg1 |
| Energy (base) | `0x27C8` | value = arg1 |
| Item identity | `0xC000` | **not a stat** — strips to `Empty`; drop it |

General rule that answers *"why arg1 vs arg2"*: **base/inherent stats carry the value in arg1**
(and the selector in arg1 too); **bonus/conditional mods carry the magnitude in arg2** and the
qualifier (threshold / damage-type / species / chance) in arg1. Documented exceptions exist
(HealthPlus, ArmorPenetration) — they are why we store the formula rather than derive it.

### A7. Composites reconstruct by cross-referencing sibling words

A named mod's display pulls values from its sibling raw words **by identifier**:

- frenkey template grammar: `{argN}` (this word) and `{argN[ID]}` (the sibling word whose
  identifier == ID). Only two shapes exist in the shipped data.
- The same mechanism is what joins **Damage** (`0xA7A8`) to its **DamageType** (`0x24B8`) to
  render "Chaos Dmg: 11-21" — two separate words, one line.
- Composite sizes observed: 1 word (248 mods), 2 words (90), 3 words (17). The recurring 3-word
  shape is `variable-stat word` + `Fixed selector` + `None_ reference word`.

Your `itemcompare.py` does **not** model this join — it hand-wires damage-type + range + req in
the consumer (lines 1120-1170). That's the one place the new design must be stronger than yours.

---

## Part B — Proposed design (enum-based, centered on your `itemcompare.py`)

### B1. The shape, in one sentence

An **enum of identifiers** (game-native), each member carrying a **formula** = per-arg roles +
catalog foreign keys; a resolver that takes an item's `list[int]`, matches each by identifier,
applies the formula, and yields typed `ResolvedMod(value, subtype, …)`; a thin composite layer
that joins sibling words for display/reconstruction.

### B2. ER model

```
   CATALOGS (existing enums — the lookup tables / dimension tables)
   Attribute · DamageType · Ailment · Reduced_Ailment · Inscription · Weapon · ItemType · Species
        ▲  FK (ArgSpec.catalog)
        │
   ┌───────────────────────────┐        ┌──────────────────────────────┐
   │        ModDef             │◄────────│   RawWord (runtime atom)      │
   │  (one per identifier; PK) │ ident   │   identifier:int, arg1, arg2  │
   ├───────────────────────────┤ (FK)    ├──────────────────────────────┤
   │ id        : int  (mod>>16)│         │ → resolve() via its ModDef →  │
   │ name      : str           │         │   ResolvedMod(value, subtype, │
   │ arg1      : ArgSpec       │         │                is_maxed, raw) │
   │ arg2      : ArgSpec        │        └──────────────────────────────┘
   │ kind      : Base|Upgrade  │                     ▲ 1..3 words
   │ template  : str (display) │                     │ compose
   └───────────────────────────┘        ┌──────────────────────────────┐
            ▲ referenced by             │        NamedMod               │
            └────────────────────────── │  words:[RawWord], display,    │
                                        │  reconstruct an item's mods    │
                                        └──────────────────────────────┘

   ArgSpec = (role, catalog?)
     role ∈ { VALUE, RANGE_MIN, RANGE_MAX, CATALOG, THRESHOLD, CHANCE, FIXED, UNUSED }
     catalog = an enum class (Attribute / DamageType / …) when role == CATALOG, else None
```

- **`ModDef`** replaces *all four* current scattered sources (`VALUE_ARG`, `ModId`,
  `mods_metadata`, and the itemcompare lambdas) with one record.
- **`ArgSpec`** is your `itemcompare.py` per-arg idea (label + eval) made typed: the `role`
  says how to read the arg, the `catalog` is the **foreign key** (a real enum class). Resolving
  an arg is `catalog(arg)` when it's a FK, else the raw int — nothing is ever read against a
  catalog it doesn't belong to (this is what eliminates the `dmg#21` class of bug).

### B3. The resolve algorithm (your consume-loop, cleaned up)

```
resolve_item(mods: list[int]) -> list[ResolvedMod]:
    for word in mods:
        ident = word >> 16
        d = MODDEFS.get(ident)              # FK lookup (PK match); None → skip/opaque
        if d is None: continue
        r = ResolvedMod(def=d, arg1=(word>>8)&0xFF, arg2=word&0xFF)
        # value: from the arg the formula names (or a range)
        # subtype: d.arg1.catalog(arg1) etc. when that arg is a CATALOG FK
        yield r
```

That is exactly `itemcompare.py` lines 1056-1071 — `find_modifier(identifier)` → apply per-arg
formula → produce data — but keyed off a typed `ModDef` instead of lambda soup, and with the
catalog as a real FK.

### B4. Filter API (your actual end goal)

```
Item.Mods.has(item, ModId.Requirement, Attribute.Tactics, level<=9)
Item.Mods.has_all(item, [(ModId.ShieldArmor, 16), (ModId.Requirement, Attribute.Tactics)])
```

A filter matches on `(identifier, subtype?, value/predicate?)`. Because `subtype` is a typed
catalog member, "req 9 Tactics" is `identifier==Requirement AND subtype==Attribute.Tactics AND
value<=9` — no string parsing, no name matching.

### B5. Data provenance — no hardcoded guesses

The `ModDef` table is **generated once**, not hand-typed:

- **which arg is the value / min-max / fixed** → from the empirical mining of frenkey's
  `weapon_mods.json` + `runes.json` (the per-identifier `ModifierValueArg`, stable for 60/62).
- **base-stat formulas** (requirement/damage/armor/energy/type) → from `item_mods_src/
  upgrade_parser.py` (already RE'd) + live-item confirmation.
- **catalog FK per identifier** → from the complete map in A5 (three references agree).
- **names** → the game's own composer (the 294-entry `game_mod_table_named.txt`) for upgrades;
  `ModifierIdentifier` for base stats.

Frenkey/`item_mods_src` are the **reference data source**; the structure is our Pythonic ER
model; runtime never parses JSON — it queries enums and dataclasses.

---

## Part C — Decisions needed before building

1. **Identifier convention** — confirm **game-native `mod >> 16`** as the single PK convention.
2. **Is the identifier the enum?** Two options:
   - (a) `ModId(IntEnum)` members ARE the identifiers, and a parallel `MODDEFS[ModId] -> ModDef`
     table holds the formula; or
   - (b) a single `ModDef` dataclass registry keyed by int, with `ModId` as a thin name alias.
   (Recommend **b** — keeps the enum small and the formula data in one dataclass table.)
3. **Composite handling scope now** — do we build the full `{argN[ID]}` sibling-join for display
   in v1, or only the base-stat join (damage↔type) needed for filters, and defer upgrade-display
   to the enc-strings (which already render perfectly)? (Recommend: **filters + base-stat join
   now; lean on enc-strings for pretty display**, since display was never the pain point.)
4. **Species catalog placement** — move `ItemBaneSpecies` into `GameData_enums.py` and re-export,
   or reference it in place from `item_mods_src`?
5. **The 2 inconsistent identifiers** (`0x22D8`, `0x2532`) — per-mod override table, or treat
   them as opaque/None? (They're an Energy variant and a reference word — low stakes.)
6. **Home + cleanup** — where does this live (`Py4GWCoreLib/…`), and do we delete the now-obsolete
   `mods_value_args.py` / `mod_ids.py` / `mods_metadata.py` as it subsumes them?

Nothing is built until these are settled.
