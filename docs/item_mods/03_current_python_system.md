# 03 — The Current Python System (`Py4GWCoreLib/item_mods_src/`)

This is the mod system the library ships today. It is thorough and type-rich, but it is
also the "cumbersome" thing this effort is about: a **9,694-line** upgrade hierarchy plus a
**700-line** properties file, most of which is hand-written class-per-upgrade boilerplate
and magic-byte tooltip encoding.

## Pipeline overview

```
item.modifiers (list[PyItem.ItemModifier])          ← raw 32-bit words
        │  Item.Customization.Modifiers.GetModifiers(item_id)      (Item.py:436)
        ▼
DecodedModifier.from_runtime(mod)                    ← bit-strip each word
        │                                            (decoded_modifier.py:44)
        ▼
ItemModifierParser(runtime_modifiers, rarity)        ← orchestrator
        │  _decode()  → list[DecodedModifier]        (item_modifier_parser.py)
        │  _build_properties()
        ▼
get_property_factory()[identifier](mod, mods, rarity)  ← identifier → typed property
        │                                            (upgrade_parser.py:81)
        ▼
list[ItemProperty]   (ArmorProperty, DamageProperty, PrefixProperty, …)
        │            + composed Upgrade objects       (properties.py, upgrades.py)
        ▼
ItemMod.get_item_upgrades(item_id) → (prefix, suffix, inscription, [inherent])
                                                     (item_mod.py:110)
```

## 1. `DecodedModifier` — bit-strip the raw word

`decoded_modifier.py:44` `from_runtime(modifier)`:

```python
runtime_identifier = modifier.GetIdentifier()          # mod >> 16
stripped_identifier = (runtime_identifier >> 4) & 0x3FF # ← 10-bit id (see doc 01 §5)
if stripped_identifier not in ModifierIdentifier._value2member_map_:
    return None                                         # unknown mods are DROPPED
raw = _parse_raw_bits(modifier.GetModBits())            # parse the 32-bit binary string
identifier = ModifierIdentifier(stripped_identifier)
param_value = ItemModifierParam((runtime_identifier >> 16) & 0xF)   # ⚠ see note
upgrade_id  = ItemUpgradeId(raw & 0xFFFF) if (raw & 0xFFFF) in ... else ItemUpgradeId.Unknown
flags       = (raw >> 30) & 0x3
arg1, arg2  = modifier.GetArg1(), modifier.GetArg2()
arg         = (arg1 << 8) | arg2
```

Fields: `identifier, param, arg1, arg2, arg, raw_bits, upgrade_id, flags, raw_identifier`.

Two things to know:
- Mods whose stripped identifier isn't in the `ModifierIdentifier` enum are **silently
  dropped** — the enum is a hard allow-list.
- ⚠️ **Likely latent bug:** `param_value = (runtime_identifier >> 16) & 0xF`. Since
  `runtime_identifier` is already `mod >> 16` (a 16-bit value), `>> 16` again is always `0`,
  so `param` is always `LabelInName`. The 4 bits that actually carry the param are the ones
  stripped in `stripped_identifier` (`& 0xF` of `runtime_identifier`). This should be flagged
  for verification (see doc 05).

## 2. `types.py` — the taxonomy (1,231 lines)

- `ModifierIdentifier(IntEnum)` (`:39`, ~90 members) — the **10-bit stripped** identifiers:
  `Armor1=0x27b`, `AttributeRequirement=0x279`, `Damage=0x27a`, `Energy=0x27c`,
  `HighlySalvageable=0x260`, `TargetItemType=0x25b`, `Upgrade=0x240`, `AttributeRune=0x21e`,
  plus the full family of conditional stats (`ArmorPlusEnchanted`, `DamagePlusVsSpecies`,
  `EnergyPlusWhileBelow`, …).
- `ItemUpgradeId(IntEnum)` (`:128`, ~400 members) — every concrete upgrade id: weapon
  prefixes/suffixes **per weapon type** (`Fiery_Sword=0x0090`, `Vampiric_Axe=0x00A7`,
  `OfFortitude_Sword=0x00DD`), all inscriptions (`ToThePain=0x016A`, …), insignias
  (`Survivor=0x01E6`, `Knights=0x01F9`, …), runes (`OfSuperiorVigor=0x0101`,
  `OfMinorSwordsmanship=0x1401`, …), and `AppliesTo*Rune` pairs.
- `ItemUpgrade(Enum)` (`:604`) — maps a logical name → `{ItemType: ItemUpgradeId}`
  (e.g. `Fiery`, `Vampiric`, `OfEnchanting`, `OfTheProfession`), so one logical upgrade
  resolves to the right id per weapon type.
- Support: `ItemUpgradeType` (`Prefix/Suffix/Inscription/Inherent/UpgradeRune/AppliesToRune`),
  `ItemBaneSpecies`, `ItemModifierParam`, `ModifierType`.

## 3. `properties.py` — one dataclass per stat (700 lines)

Each `ItemProperty` subclass models one decoded stat and, crucially, **hand-builds its
tooltip bytes** via `GWEncoded`. Example (`properties.py:100`):

```python
@dataclass
class ArmorPlus(ItemProperty):
    armor: int
    def create_encoded_description(self) -> GWStringEncoded:
        return GWEncoded._bonus_plus_num(self.get_text_color(), GWEncoded.ARMOR_BYTES, self.armor, "Armor")
```

…and more elaborate ones are raw byte arrays, e.g. `ArmorPenetration` (`:85`) or
`DamageProperty` (`:638`):

```python
encoded_bytes = bytes([*GWEncoded.ITEM_BASIC, 0x89, 0xA, 0xA, 0x1, 0x4E, 0xA, 0x1, 0x0,
                       0xB, 0x1, *damage_bytes, 0x1, 0x1, self.min_damage, 0x1, 0x2, 0x1,
                       self.max_damage, 0x1, 0x1, 0x0])
```

There are ~70 such classes: `ArmorProperty`, `EnergyProperty`, `DamageProperty`,
`AttributeRequirement`, all the `ArmorPlus*/DamagePlus*/EnergyPlus*/HealthPlus*` conditional
variants, `Furious`, `HalvesCastingTime*`, `HealthStealOnHit`, plus the upgrade-carrier
properties `PrefixProperty`, `SuffixProperty`, `InscriptionProperty`, `InherentProperty`,
`UpgradeRuneProperty`, `AppliesToRuneProperty`, `TargetItemTypeProperty`, `BowTypeProperty`.

## 4. `upgrade_parser.py` — identifier → property, and upgrade composition

- `get_property_factory()` (`:81`) — a big dict mapping each `ModifierIdentifier` to a
  lambda that constructs the right `ItemProperty` from `(mod, all_mods, rarity)`. This is
  the switchboard from raw identifier to typed stat.
- For the two "upgrade" identifiers (`AttributeRune`, `Upgrade`), the factory tries to
  compose an `Upgrade` as Prefix → Inscription → Suffix → UpgradeRune → AppliesToRune,
  falling back to `UnknownUpgradeProperty` (`:161-176`).
- `get_upgrade()` (`:45`) — finds candidate `Upgrade` subclasses via `has_id(upgrade_id)`,
  calls `compose_from_modifiers` on each, and picks the **most specific** match by
  `get_specificity_score()` (count of fixed instructions, then MRO depth).

## 5. `upgrades.py` — the 9,694-line hierarchy

The `Upgrade` base class (`:161`) is a dataclass with a **declarative instruction system**:
each concrete upgrade declares an `upgrade_info` tuple of `ranged()` / `fixed()`
`Instruction`s that pull values from matched properties into upgrade fields. Example
(`:638`):

```python
@dataclass(eq=False)
class BarbedUpgrade(IncreaseConditionDurationUpgrade):
    id = ItemUpgrade.Barbed
    condition = Ailment.Bleeding
    upgrade_info = (
        fixed(identifier=ModifierIdentifier.IncreaseConditionDuration, target="condition",
              fixed_value=Ailment.Bleeding,
              value_getter=property_value(IncreaseConditionDuration, lambda p: p.condition)),
    )
```

Composition machinery on the base class:
- `compose_from_modifiers()` (`:237`) — instantiate, run `_pre_compose`, match property
  modifiers to instructions, apply each (bail out to `None` if any instruction fails),
  `_post_compose`, refresh encoded strings.
- `_match_property_modifiers()` (`:287`) — greedily binds each instruction's identifier to
  an unused modifier.
- `has_id`, `get_specificity_score`, plus serialization (`to_dict`/`from_dict`), equality
  (`_comparison_data`), and encoded-name/description generation.

Category structure:
- `WeaponUpgrade` → `WeaponPrefix` / `WeaponSuffix`; helper bases `DamageTypeUpgrade`,
  `IncreaseConditionDurationUpgrade`, `OfAttributeUpgrade`.
- `ArmorUpgrade` → `Insignia` (`mod_type=Prefix`) and `Rune` (`mod_type=Suffix`) — runes and
  insignias are distinguished by `mod_type` and both require `mod.identifier ==
  ModifierIdentifier.Upgrade` to compose (`:7196-7209`). `AttributeRune` adds cross-modifier
  validation against the preceding `AppliesToRune` mod (`:7211-7239`).
- `Inherent` classes model green/unique intrinsic stats; many are named after the in-game
  inscription phrase they mirror (`CastOutTheUnclean`, `LeafOnTheWind`, …).

Registries (built at import by scanning `globals()` for concrete leaf subclasses —
`:9636-9694`):
- `_UPGRADES` — all composable non-inherent upgrades.
- `_INHERENT_UPGRADES` — inherent upgrades, sorted by instruction count for match priority.

## 6. `item_modifier_parser.py` — the orchestrator

`ItemModifierParser(runtime_modifiers, rarity)`:
- `_decode()` — `DecodedModifier.from_runtime` over each raw mod (dropping unknowns).
- `_build_properties()` — run each decoded mod through the property factory; when a
  prefix/suffix/inscription is produced, mark its sub-modifiers "handled"; then match
  remaining unhandled mods against `_INHERENT_UPGRADES` to build `InherentProperty` objects.
- `get_properties() -> list[ItemProperty]`.

## 7. `item_mod.py` — the public API

- `ItemMod.get_item_upgrades(item_id) -> (prefix, suffix, inscription, inherent_list)`
  (`:110`, `@frame_cache`) — the high-level "what's on this item" call.
- `ItemMod.get_upgrade(item_id, UpgradeTypeOrInstance)` (`:52`) — typed fetch of a single
  upgrade, e.g. `if (u := ItemMod.get_upgrade(item_id, FuriousUpgrade)) and u.chance == 20:`.
- `get_target_item_type(item_id)` (`:146`).
- Green items: `validated_upgrades()` marks upgrades `is_inherent` for Rarity.Green.

## 8. Wrapper surface — `Item.py`

`Item.Customization.Modifiers` (`Item.py:429`):
- `GetModifiers(item_id)` → `item.modifiers` (`:436`)
- `GetModifierCount`, `ModifierExists(item_id, identifier)`, `GetModifierValues(item_id,
  identifier) -> (arg, arg1, arg2)`.

`Item.Properties` derives stats through the parser: `GetRequirement` (`:265`), `GetDamage`
(`:279`), `GetArmor` (`:293`), `GetEnergy` (`:305`). `Item.Customization` also exposes
`GetUpgrade/GetPrefixUpgrade/GetSuffixUpgrade/GetInscriptionUpgrade/GetInherentUpgrades`
delegating to `ItemMod`.

`GlobalCache/ItemCache.py:559-596` mirrors the mod getters (no mod caching; names cached).

## What this system does well

- Fully typed upgrades with named fields (`.chance`, `.armor_penetration`, `.health`).
- Authentic, localized tooltip text (round-trips through the real GW string table).
- Rich composition (multi-modifier upgrades, inherent detection, specificity scoring).

## What makes it cumbersome (short version — full in doc 05)

- **9,694 lines** of hand-written class-per-upgrade + **700 lines** of per-stat classes,
  most of it magic-byte tooltip encoding.
- Adding one new upgrade means: an `ItemUpgradeId`, an `ItemUpgrade` mapping, a subclass with
  an `upgrade_info` tuple, and often a hand-encoded tooltip byte sequence.
- Unknown mods are dropped; the taxonomy is a hard allow-list requiring constant maintenance.
- The identifier convention differs from every other tool in the repo (doc 01 §5).
- A likely-dead `param` computation (§1) suggests the bit handling isn't fully exercised.
