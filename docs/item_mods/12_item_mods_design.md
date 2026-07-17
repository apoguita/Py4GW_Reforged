# 12 — `Item.Mods`: Agreed Design

> This is the **settled design** for the mod read/filter subsystem, distilled from the whole
> design conversation. It supersedes the exploratory shape in `11_mod_system_research.md`
> (research) and `mod_defs_sketch.py` (an early sketch that predates the final API). Where a
> point still needs the user's final word it is marked **[pending]**.

`Item.Mods` is the subsystem that reads an item's modifier words and answers questions about
them. It **replaces** `Item.Customization.Modifiers` and the old `item_mods_src` upgrade layer.

## 1. Where it lives (structure)

- **`Item.Mods`** — a nested subclass inside `Item` (`Py4GWCoreLib/Item.py`), alongside
  `Item.Properties` / `Item.Type` / `Item.Usage`. It is **not** a separate top-level package.
  Mods are a subsystem *of items*, so they live under `Item`.
- **Data** (the mod table) lives in a plain **data module inside the existing items package** —
  imported by `Item.Mods`. A data file is not the rejected "mods package"; it's just where the facts
  sit. The table is **migrated by hand from the existing `item_mods_src` code** (`ItemUpgrade` etc.,
  see §7) — reshaped/renamed, not produced by any script. **No generator, no converter, no JSON.**
- **Dye → `Item.Dye`** (a *separate* subclass, not Mods). Research showed a dyed item's colour
  lives in a dedicated `DyeInfo` struct (tint + 4 channels), **not** in the modifier list — only a
  dye *vial's* colour rides in a mod. So dye is its own channel. See §6.
- **Non-mod helpers** that were under `Customization` move to `Item.Properties` (`GetItemFormula`,
  `IsStackable`, `IsSparkly` — done; `Trade.*` and `Filter.Weapon.IsMaxDamage` — pending). See §8.

## 2. The mental model — two axes of "mod"

A **mod** (what the user names and filters) is a **named mod** — `of Enchanting`, `Vampiric`,
`Requirement`, `Armor` — and that is what a `ModId` member is. Under it, an item is a flat
`list[int]` of 32-bit words (`identifier(16) | arg1(8) | arg2(8)`), and **a named mod is made of
one or more of those component words.** This is exactly how frenkey's `weapon_mods.json` /
`runes.json` model it (an `ItemMod` owns a `list[ModifierInfo]`), and we adopt that data.

### Component roles (from frenkey's `ModifierValueArg`)
Each component word carries a **role** that says what it contributes:

| role | source tag | contribution |
|---|---|---|
| **VARIABLE** | `Arg1` / `Arg2` | the value that **rolls** — *the filterable value*, and what `IsMaxed` checks |
| **FIXED** | `Fixed` | a **constant side-effect** that always comes with the mod (attached, not filtered) |
| **REFERENCE** | `None_` | a structural/plumbing word — **ignored** |

Worked from real data:
- **of Enchanting** → 1 VARIABLE component (`0x22B8 Arg2`, 1–20%). Name = effect = one mod.
- **Vampiric Strength** → 1 VARIABLE (`0x2238`, the value) + 1 FIXED (`0x20E8`, Health −1 side-effect).
- **Zealous** → 2 FIXED (Zeal +1, Energy −1) + 1 REFERENCE (`0x2530`). *(no variable → presence-only.)*

frenkey's own `get_modifier_range()` encodes this rule: it takes "the first component that is neither
`Fixed` nor `None_`" as *the* value. We use the same rule.

### Two families, one interface
- **Named upgrades** — prefixes / suffixes / inscriptions / runes / insignias. Have a **slot**
  (salvage needs it). Data from frenkey. Per-weapon components (the 8 *of Enchanting* grips) **fold
  into the one named mod** — they share the variable effect.
- **Base / inherent stats** — requirement, damage, armor, energy. **No slot.** Data from
  `item_mods_src/upgrade_parser.py` + live items.

Both answer the same questions (name, value, slot?, is_maxed) through the same API.

## 3. The data — declarative facts, one reader

Every `ModId` maps to a **`ModDef` of pure facts** — no per-mod code except a rare escape hatch
(only ~2 irregular mods). A `ModDef` carries its name, its slot (or none), and its **component
list**; each component declares its role and, where an arg is an enum index, the **catalog** (a
real existing enum) it foreign-keys into:

```
Field(role, catalog?)                  role ∈ VALUE | CATALOG | RANGE_MIN | RANGE_MAX | UNUSED
Component(identifier, kind, arg1, arg2, min, max, better_dir)   kind ∈ VARIABLE | FIXED | REFERENCE
ModDef(name, slot, components: list[Component])
```

- **Catalogs are the enums we already have**: `Attribute`, `DamageType`, `Ailment`,
  `Reduced_Ailment`, `Inscription`, `Weapon`, `ItemType`, `ItemBaneSpecies` (species). An arg is
  only ever resolved through the catalog it genuinely belongs to. The enum-index arg is **always
  arg1** (confirmed across three references).
- **One shared reader** matches an item's raw words against the `ModDef` component lists (frenkey's
  composite match, kept clean), then reads the **VARIABLE component** as the value + `IsMaxed`,
  keeps **FIXED** components as attached side-effects, and drops **REFERENCE** words. No lambda soup.
- **One shared renderer** produces English text (validator / pick-list label only).

## 4. The API (static, flat — the codebase idiom `Namespace.Method(item_id)`)

**No rich `ResolvedMod` object.** Each concept is its own single-purpose method; `GetMods` returns
plain ids, and everything else is a lookup keyed by `(item_id, mod_id)`.

```python
Item.Mods.GetMods(item_id)                 -> list[ModId]      # the mods present, as ids
Item.Mods.GetName(mod_id)                  -> str              # resolve the name from an id
Item.Mods.GetValues(item_id, mod_id)       -> list[int]        # ALWAYS a list: [8] single, [11,22] range
Item.Mods.IsMaxed(item_id, mod_id)         -> bool             # the variable component at its max roll
Item.Mods.GetRaw(item_id, mod_id)          -> tuple            # raw (arg1, arg2) if needed
Item.Mods.HasMod(item_id, mod, *values)    -> bool             # presence + optional value filter
Item.Mods.HasAnyMods(item_id, modlist)     -> bool
Item.Mods.HasAllMods(item_id, modlist)     -> bool
```

- `mod` = a `ModId` member (recommended) **or** a raw int — interchangeable (`ModId` is an
  `IntEnum`).
- `GetValues` is **one method, always a list** (most mods → 1 element). There is no `GetValue`
  singular — a caller never has to know in advance how many values a mod has.
- **Presence vs filtered:** no `*values` → "does this mod exist?"; with values → exists **and**
  values match.

### Passing filter values — positional, type-routed
An **enum** argument is a *subtype*; a **number** argument is a *value threshold*. You pass only
the fields you care about:

```python
Item.Mods.HasMod(item, ModId.ArmorVsDamage, DamageType.Piercing, 8)  # type Piercing, amount 8+
Item.Mods.HasMod(item, ModId.ShieldArmor, 16)                        # armor 16+
Item.Mods.HasMod(item, ModId.Enchanting)                             # presence only
Item.Mods.HasAllMods(item, [
    ModId.Enchanting,
    (ModId.ShieldArmor, 16),
    (ModId.Requirement, Attribute.Tactics, 9),
])
```

Multi-*number* mods (e.g. weapon damage `min`/`max`, ambiguous by position) use **keyword** args.
A **lambda** is an escape hatch, rarely needed now (see §5). Lists/dicts add nothing over these.

### Slots (for salvage) — **[surface to define now]**
```python
Item.Mods.GetSlot(item, mod)         -> Slot              # Prefix|Suffix|Inscription|Inherent|Rune|Insignia
Item.Mods.GetUpgrades(item)          -> dict[Slot, ModId]  # which mod fills each slot
Item.Mods.IsMaxed(item, mod)         -> bool
Item.Mods.SalvageableUpgrades(item)  -> list[ModId]
```
The salvage window presents extractable upgrades **by slot**, so each mod must resolve its slot.
When this is proven in, `Item.Customization` (which owns this today) is deleted.

## 4b. Reading an item — the recipe (how the reader works, in plain steps)

Worked example: a **Fiery Sword of Enchanting** (req 9 Swordsmanship, 15–22 fire damage).

1. **Get the raw words.** The item gives a `list[int]`; each word splits into a *kind* number
   (`identifier = word >> 16`) plus `arg1` / `arg2`.
2. **Sort each word into one of three piles:**
   - **Barcode word** (`identifier == 0x2408`, the Upgrade marker) → its low 16 bits are an *upgrade
     id*; look it up in `UPGRADE_TO_MODID` (built by inverting `ItemUpgrade`) → a **named mod**
     (`Fiery`, `OfEnchanting`).
   - **Base-stat word** (its identifier is a known base stat: Requirement, Damage, DamageType,
     Armor…) → a **base mod** directly.
   - **Junk** (item-identity `0xC000`, `None_` reference words) → ignore.
   Result = the **names**: `Fiery`, `OfEnchanting`, `Requirement`, `Damage`, `DamageType`.
3. **Resolve each value** using the mod's `ModDef`: find its VARIABLE component word among the raw
   words and read the right arg, running catalog lookups where an arg is an enum index —
   `Requirement`: arg1 20 → `Attribute.Swordsmanship`, arg2 9 → level; `DamageType`: arg1 5 →
   `DamageType.Fire`; `OfEnchanting`: value 20.
4. **Everything is built on this one pass:** `GetMods` = the names (step 2); `GetValues` = a mod's
   number (step 3); `GetSlot` = the barcode's prefix/suffix; `IsMaxed` = value at top of its range;
   `HasMod` = filter over this list.

**Key simplifier:** the barcode is a *direct lookup* — the reader never guesses which upgrade a set
of words is; the game states it, and `ItemUpgrade` already maps barcode → name.

## 5. Matching semantics — exact-or-better, **direction-aware**

Filters exist to find the *best* stats, so a passed number means **"that value or better,"** not
exact. "Better" has a **per-mod direction**:
- armor / damage / health / most values → **higher** is better (`value ≥ N`).
- **requirement → lower** is better ("req 9 or better" = `req ≤ 9`).

Each `ModDef` stores its `better_dir` (the mod's **metadata** decides higher-vs-lower, not a
per-call parameter), and `HasMod` applies it. This is why day-to-day filtering needs **no lambdas**
— a plain number already means "N or better." **Confirmed.**

## 6. Dye — its own subclass `Item.Dye` (not Mods) — **researched**

**Two separate dye things, neither is JSON, both read-only:**
1. A **dyed item's colours** — a dedicated 3-byte field on the item (`DyeInfo`): `dye_tint` +
   four 4-bit `DyeColor` channels (`dye1`–`dye4`). Primary colour = `dye1`. **Not a modifier** —
   its own slot on the item (native `item.h` +0x21).
2. A **dye vial's colour** — stored in one of the vial's mods; `GetDyeColor` reads it (used by loot
   filters like "grab Black dye").

**Findings:**
- Colours are **already the `DyeColor` enum** (NoColor, Blue, Green, …) — nothing to migrate to an
  enum, and **no JSON** is involved anywhere.
- **Read-only** — there is **no "apply dye" action** anywhere in the Python or native code, so
  `Item.Dye` only *reads* dye.
- The reads already exist, just scattered: `GetDyeColor` (vial), `GetDyeInfo` (channels + tint),
  `Filter.Dye.IsDyeColor`, and `DyeColor.from_dye_info` (primary colour).

**`Item.Dye` (small):**
```python
Item.Dye.GetColor(item_id)                 -> DyeColor        # the item's / vial's primary colour
Item.Dye.GetChannels(item_id)              -> (tint, [DyeColor x4])
Item.Dye.IsColor(item_id, DyeColor.Black)  -> bool            # loot-filter check
```
Migration = gather the existing reads under `Item.Dye`, repoint current callers (a loot manager, a
farmer, the demo, `ItemCache`), keyed by `DyeColor`. No research gaps remain.

## 7. Data provenance — a MIGRATION of existing code, no JSON anywhere

This is a **migration, not a conversion**. The mod data already lives in Python in `item_mods_src`
— we **reshape it** into the new enums/catalogs. There is **no JSON** at build time or runtime.

**We keep the DATA, we throw away the CONVOLUTED CODE.** Two different things:

*Data we reshape (rename into the new enums/tables):*
- **`ItemUpgrade` (enum)** — already the named mods **grouped by weapon type**, e.g.
  `Icy = {Axe: Icy_Axe, Bow: Icy_Bow, ...}`. This is the core of the new `ModId` + the per-weapon
  fold + the `UPGRADE_TO_MODID` lookup — it already exists, we rename/reshape it.
- **`ItemUpgradeId` (enum)** — the per-weapon upgrade ids (the "barcodes" `GetMods` reads).
- **`ModifierIdentifier` (enum)** — the effect/base-stat identifiers.

*Convoluted code we mine once, then DELETE (do NOT migrate its structure):*
- **`upgrade_parser.py`** — `get_property_factory()` is ~90 lambdas, each building a dedicated
  class (`ArmorPlus`, `ArmorPlusCasting`, `ArmorPlusVsDamage`…) with `rarity`/tooltip plumbing. But
  every lambda only encodes **two facts**: which arg is the value, which arg is a catalog. We **read
  those two facts per id** into our plain data table and delete the file.
- **`properties.py`** (~90 near-identical property classes) and **`upgrades.py`** (9,694 lines) —
  the machinery those lambdas build. **Deleted**, replaced by our data table + one reader. This is
  our own design — *match id → read arg → return value* — not frenkey's per-property-class model.

Frenkey's JSON was only a *reference for understanding*, never a data source. Result: pure Python
enums + a small catalog table + one reader. **Nothing parses JSON; nothing keeps the convoluted
parser.**

Frenkey / `item_mods_src` are the **reference data source**; the structure is our Pythonic model.

## 8. Migration & cleanup

| Item | From | To | Status |
|---|---|---|---|
| `GetItemFormula` / `IsStackable` / `IsSparkly` | `Customization` | `Properties` | **done** (delegating shims left) |
| `Trade.IsOfferedInTrade` / `IsTradable` | `Trade` class | `Properties` (dissolve `Trade`) | pending |
| `Filter.Weapon.IsMaxDamage` | `Filter` | `Properties` | pending |
| `Filter.Dye.IsDyeColor` | `Filter` | `Item.Dye` | pending (after dye research) |
| `Customization.Modifiers.*` + upgrade layer | `Customization` | `Item.Mods` | the core build |
| `mods_value_args.py`, `mod_ids.py`, `mods_metadata.py` | — | folded into the data module, then **deleted** | pending |
| **`Item.Customization` class (whole thing)** | — | **DELETED** once emptied | the goal |

Vanity single-helper subclasses (`Trade`, `Filter`) are dissolved: every helper lives where it
belongs (`Properties` for item facts, `Mods` for mods, `Dye` for dye).

### `Item.Customization` — removed entirely (this is what we're replacing)

`Item.Customization` is the class the whole redesign exists to retire. Its members are relocated,
then the class is **deleted**:

| member(s) | goes to |
|---|---|
| `Modifiers.GetModifiers / GetModifierCount / ModifierExists / GetModifierValues` | `Item.Mods` (`GetMods` / `HasMod` / `GetRaw`) |
| `GetUpgrade / GetUpgrades / GetPrefixUpgrade / GetSuffixUpgrade / GetInscriptionUpgrade / GetInherentUpgrades` | `Item.Mods` (slots) |
| `HasUpgrades / HasInherentUpgrades / HasUpgradeType / HasUpgrade` | `Item.Mods` (`HasMod` + slots) |
| `GetItemFormula / IsStackable / IsSparkly` | `Item.Properties` (**done**, shims left) |
| `GetDyeInfo` | `Item.Dye` |
| `IsInscription / IsInscribable / IsPrefixUpgradable / IsSuffixUpgradable` (slot flags) | read from the item directly where a caller needs them — **not** re-wrapped just to keep them |

After every member is repointed and its callers updated, the `Item.Customization` class is removed
from `Item.py`.

### Build order (nothing breaks mid-flight)

1. Reshape `types.py` enums → `ModId` / `Slot` / catalogs; add `DyeColor.Mixed = 1`.
2. Build the data table (mine facts from `upgrades.py` / `properties.py` / `upgrade_parser.py`).
3. Build the one reader + the flat `Item.Mods` API (+ slots) and the small `Item.Dye`.
4. Validate against live items (oracle check) until values match the game.
5. **Repoint callers**: `Item.Customization.*` users → `Item.Mods` / `Item.Properties` / `Item.Dye`;
   `frenkey item_snapshot.py` (imports `properties.py`) → the new surface.
6. **Delete**: `Item.Customization` class, the `item_mods_src` package, and
   `mods_value_args.py` / `mod_ids.py` / `mods_metadata.py`.

### `item_mods_src` teardown — the whole legacy package (12,132 lines, 596 classes)

It is frenkey-style over-engineering (515 upgrade classes + 81 property classes to answer "match id
→ return value"). The entire package is replaced by a small data table + one reader + the API.

| file | lines | fate |
|---|---|---|
| `types.py` | 1,230 | **reshape** — its enums (`ItemUpgrade`, `ItemUpgradeId`, `ModifierIdentifier`, `ItemBaneSpecies`) become the new `ModId` / `Slot` / catalogs. Keep the data. |
| `upgrades.py` | 9,694 (515 cls) | **mine → delete** — read each upgrade's effect/value/slot into the table, delete the classes. |
| `properties.py` | 700 (81 cls) | **mine → delete** — read "which arg per property" into the table, delete. |
| `upgrade_parser.py` | 176 | **mine → delete** — the id→arg facts into the table, delete. |
| `item_mod.py` | 161 | **replace** — old public API → `Item.Mods`. |
| `item_modifier_parser.py` | 91 | **replace** — orchestrator → the one reader. |
| `decoded_modifier.py` | 75 | **replace** — the one reader (game-native, not the lossy stripped convention). |

**Order:** build `Item.Mods` → repoint the outside callers (`Customization` delegates here;
frenkey's `item_snapshot.py` imports `properties.py`) → **then** delete the package. Nothing breaks
mid-flight. Outcome: ~12,000 lines → a few hundred.

## 9. No multi-language

Matching is structural (never by text), and display already comes from the game's encoded strings
in any language. So the mod system stores **no** translations. The one English descriptor we render
exists only as an **oracle validator** (render our text → diff vs the game's enc-string, to prove
the formulas are correct) and to label the pick-list UI.

## 10. Quality rule

Every `.py` in this subsystem is type-checked with **Pylance/Pyright** before it's considered done
(`npx --yes pyright "<path>"`) — `py_compile` alone misses type/name/import errors. See `CLAUDE.md`.

## Settled in this pass
- `ModId` = **named mods** (of Enchanting, Vampiric, Requirement…), one id per mod; per-weapon
  components fold in. Not raw effect-ids, not upgrade_ids — the mod *by its name*.
- Frenkey's `ItemMod`/component data is **included** (§2/§3/§7): component list + role
  (VARIABLE/FIXED/REFERENCE) + roll range. The VARIABLE component is the filterable value.
- Flat API (§4): `GetMods`/`GetName`/`GetValues`(always a list)/`IsMaxed`/`GetRaw`/`HasMod`. No
  `ResolvedMod` object, no `GetValue` singular.
- Values (§4/§5): positional type-routed, **exact-or-better, direction-aware**.

## Design status — COMPLETE

Both remaining questions are resolved:
1. **"or better" direction** → **Option A**: the mod's metadata (`better_dir`) decides higher-vs-lower;
   requirement = lower, everything else = higher. No per-call parameter.
2. **duplicate / not-found** → the obvious defaults (no special handling): `HasMod` true if **any**
   instance matches; `GetValues` on a missing mod → `[]`; unknown mod → `False`. The only "duplicate"
   case is the same mod with different subtypes (e.g. Armor vs Piercing *and* vs Slashing), handled
   naturally by the subtype filter.

Everything is settled and specified: the model (§2), data & migration source (§3, §7), the read
recipe (§4b), the flat API (§4), slots (§4), matching (§5), dye (§6), and the full
Customization + `item_mods_src` teardown with build order (§8). Nothing reads JSON. **Ready to build.**
