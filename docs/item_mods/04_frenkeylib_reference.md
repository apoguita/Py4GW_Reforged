# 04 — frenkeyLib Reference (`LootEx` + `mods_parser`)

frenkeyLib contains the implementation the user considers "adequate." It takes the opposite
approach to `item_mods_src`: instead of a code hierarchy, it is **data-driven** — a small set
of generic dataclasses matched against **JSON tables** (`weapon_mods.json`, `runes.json`)
whose names were scraped from the live game. This doc documents that model as a reference
for the redesign.

There are two independent mod subsystems in `Sources/frenkeyLib`:
- **`LootEx/`** — the full data-driven engine (this doc's focus).
- **`ItemHandling/`** — a leaner layer that **delegates** parsing to `Py4GWCoreLib.item_mods_src`
  (see §6). It does *not* re-implement decoding.

> Note: `LootEx/weaponmods.py` (the obvious-sounding file) is a **5-entry experimental stub**,
> not the production model. The real model lives in `LootEx/models.py`. Ignore `weaponmods.py`.

## 1. Identifier convention (differs from item_mods_src — see doc 01 §5)

frenkeyLib keys on the **full 16-bit** `GetIdentifier()` (= `mod >> 16`).
`LootEx/enum.py:260-272`:

```python
class ModifierIdentifier(IntEnum):
    None_               = 0
    Requirement         = 10136   # 0x2798
    Damage              = 42920   # 0xA7A8
    Damage_NoReq        = 42120
    DamageType          = 9400
    ShieldArmor         = 42936
    TargetItemType      = 9656
    RuneAttribute       = 8680    # 0x21E8
    HealthLoss          = 8408
    ImprovedVendorValue = 9720
    HighlySalvageable   = 9736
```

Only ~11 identifiers are special-cased. **Everything else is matched generically** (by
comparing the full `(identifier, arg1, arg2)` triple to table rows) rather than by having a
class per identifier.

## 2. Bit handling

`BaseModifierInfo` (`models.py:758-790`) — the arg packing, matching the C++ layout:

```python
def __post_init__(self):  self.arg = (self.arg1 << 8) | self.arg2
@staticmethod
def unpack_arg(arg): return (arg >> 8) & 0xFF, arg & 0xFF
@staticmethod
def pack_arg(a1, a2): return (a1 << 8) | a2
```

Other conversions:
- `Util.get_mod_mask` (`utility.py:39-68`) — 4-byte hex "mod mask": Byte0=arg2, Byte1=arg1,
  Bytes2-3=identifier (little-endian).
- `Util.parse_modifier_from_hex` (`utility.py:483-496`) — `identifier=int(hex[0:4],16)`,
  `arg=int(hex[4:8],16)`, then `unpack_arg`.
- `ItemMod.decode_binary_identifier` (`models.py:848-869`) — base64 blob: byte0 = `ModType`,
  then repeating 5-byte records `[3-byte BE identifier][2-byte BE arg]`. Used for
  serialized/stored mod identities.

## 3. The data model (all generic dataclasses)

Classification enums (`enum.py:235-258`):
- **`ModType`**: `None_=0, Inherent=1, Prefix=2, Suffix=3` — the core prefix/suffix/inherent axis.
- **`ModifierValueArg`**: `None_=-1, Arg1=0, Arg2=1, Fixed=2` — which arg carries the variable value.
- **`ModsModels`** (`enum.py:74-99`) — upgrade-component **model IDs** (the physical mod items):
  `AxeGrip=905`, `SwordHilt=897`, `StaffHead=896`, `FocusCore=15551`, inscription bases
  `Inscription_Weapon=15542`, `Inscription_MartialWeapon=15540`, etc.

Core rows:
- **`ModifierInfo`** (`models.py:792-806`) — one atomic modifier row:
  `identifier, arg1, arg2, arg, modifier_value_arg, min, max`.
- **`ItemMod`** (base, `models.py:808-1091`) — a named mod:
  `identifier:str, names:dict[ServerLanguage,str], descriptions:dict[...], mod_type:ModType,
  modifiers:list[ModifierInfo], upgrade_exists`. Derives `name/full_name/description/applied_name`.
  `get_modifier_range()` returns the `IntRange(min,max)` of the first variable modifier.
- **`Rune`** (`models.py:1093-1271`) — models **runes AND insignias**, disambiguated by
  `mod_type` (`Suffix` = rune, `Prefix` = insignia). Adds `profession, rarity, model_id,
  texture_file, inventory_icon`. `matches_modifiers(triples) -> (matched, maxed)`
  (`:1165-1214`).
- **`WeaponMod`** (`models.py:1273-1365`) — weapon prefix/suffix/inherent **AND inscription**
  (flagged by `names[English].startswith('"')`, since inscriptions are quoted). Adds
  `target_types:list[ItemType]`, `item_mods:dict[ItemType, ModsModels]`,
  `item_type_specific:dict[ItemType, BaseModifierInfo]`.

Runtime match wrappers:
- **`BaseModInfo`** (`models.py:1397-1421`) — `Mod, Modifiers:list[tuple[int,int,int]],
  IsMaxed, Value, Arg1, Arg2, Description`.
- **`RuneModInfo`** (`:1423-1449`) — `.Rune`; `get_from_modifiers()` scans `data.Runes.values()`.
- **`WeaponModInfo`** (`:1451-1707`) — `.WeaponMod`; **sequential ordered matching** of a
  weapon mod's `modifiers` against the item's modifier sequence + `item_type_specific`
  disambiguation.
- **`ItemModifiersInformation`** (`:1709-1816`) — the aggregate produced from a raw mod list:
  `target_item_type, damage, shield_armor, requirements, attribute, is_highly_salvageable,
  has_increased_value`, plus `runes/max_runes/runes_to_keep/runes_to_sell`,
  `weapon_mods/max_weapon_mods/weapon_mods_to_keep`, combined `mods`. Entry points
  `populate_from_modifiers()` / static `GetModsFromModifiers()`.

## 4. Names, descriptions, categories

- Names live per-mod in `names:dict[ServerLanguage,str]`, resolved by
  `get_name/get_full_name/get_applied_name` with English fallback. Server language via
  `UIManager.GetIntPreference(TextLanguage)` (`utility.py:498-502`).
- `applied_name` strips the item's base name with language-specific regex so only the mod
  name remains (separate rune vs insignia patterns — `models.py:1121-1163`).
- Descriptions substitute `{arg1}`, `{arg2}`, `{arg1[<identifier>]}`, `{min}`, `{max}`
  placeholders, resolving enum args (Attribute / DamageType / EnemyType) via small identifier
  tables (`models.py:926-934`).
- Name **scraping**: `data_collection.py:244-352` parses live localized item names with
  `ModType`-specific regex and writes results back into `data.Weapon_Mods[...].names`,
  tracking dirty entries — i.e. the tables are grown from the game at runtime.

## 5. Downstream usage

- **Attach to item**: `Cached_Item.__init__` (`cache.py:102-120`) calls
  `ItemModifiersInformation.GetModsFromModifiers(...)` and copies rune/weapon-mod/keep/sell
  lists onto the item.
- **Keep/sell**: runes via `settings.profile.runes.get(id).valuable/should_sell`; weapon mods
  kept only if `IsMaxed` **and** enabled for that item type in the profile
  (`models.py:1792-1803`).
- **Salvage** (`salvaging.py:71-255`): decides confirmation from present `ModType`s, picks the
  kit by `SalvageOption`, and names the exact prefix/suffix/inherent being extracted.
- **Rules** (`weapon_rule.py:53-91`, `skin_rule.py:125-182`): rules store `mods:dict[str,
  ModInfo]` keyed by identifier and validate an inherent mod's `Value` within `[min,max]`.
- **Data loading** (`data.py:938-1049`): `data.Weapon_Mods` / `data.Runes` from
  `weapon_mods.json` / `runes.json` (+ per-account overrides), via `WeaponMod.from_json` /
  `Rune.from_json`.

## 6. `ItemHandling/` — delegates to item_mods_src

`ItemHandling/Items/item_snapshot.py:217-243` does **not** decode mods itself:

```python
modifiers = Item.Customization.Modifiers.GetModifiers(self.id)
parser = ItemModifierParser(modifiers, self.rarity)         # Py4GWCoreLib.item_mods_src
properties = parser.get_properties()
prefix, suffix, inscription, inherent = ItemMod.get_item_upgrades_from_properties(properties, self.rarity)
```

So `ItemHandling` is a consumer of the *current* system, while `LootEx` is a parallel,
self-contained one. `ItemHandling/Items/ItemData.py:338-481` holds the authoritative
`DAMAGE_RANGES` table (per weapon type, req 0-9).

## 7. `Sources/marks_sources/mods_parser.py`

A standalone, JSON-driven matcher ("stolen from Frenkey") — the same model as `LootEx`,
condensed into one file. Parses `(identifier, arg1, arg2)` triples against a `ModDatabase`
from `runes.json` / `weapon_mods.json`. Enums `ModifierValueArg`, `ModifierIdentifier`
(`Requirement=10136`, `RuneAttribute=8680`, …), `ModType`. Entry point
`parse_modifiers(modifiers, item_type, model_id, db) -> ParsedModifierResult` (`:664`) with
`.prefix/.suffix/.inherent/.inscription/.all_mods/.summary()`. A good compact template.

## Why this is the "adequate" reference

- One generic model instead of a class per upgrade; new mods are **data**, not code.
- Names/descriptions are localized and scraped from the game, not hand-encoded.
- Explicit runtime match wrappers with `IsMaxed` / `Value`, purpose-built for loot decisions.
- Clear prefix/suffix/inherent axis (`ModType`) and value-arg model (`ModifierValueArg`).

Its limitations vs `item_mods_src`: fewer typed fields (values are generic `Arg1/Arg2`), less
exhaustive coverage of niche conditional stats, and it relies on external JSON tables staying
in sync with the game.
