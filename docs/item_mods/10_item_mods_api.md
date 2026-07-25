# 10 — `Item.Mods` API (the mod read/filter layer)

The clean, game-sourced mod-read/filter layer that the whole RE effort was building toward.
Self-contained, reads the raw `ItemModifier` words directly, and **does not** depend on the
(deprecated, deleted) `Item.Customization.Modifiers` or the old `item_mods_src` parser.

> **This doc matches the live code** (`Py4GWCoreLib/Item.py` → `Item.Mods`, backed by
> `Py4GWCoreLib/mods_core.py` + `Py4GWCoreLib/mods_types.py`). Earlier drafts of this file
> described a `Has/HasAll/GetAll` API, a `Mod` value object, and `mod_ids.py` /
> `mods_value_args.py` — **none of those exist**. If you see them referenced anywhere, they are
> stale. The names below are the real ones.

## The API — `Py4GWCoreLib/Item.py`

Identifiers come from `ModifierIdentifier` (aliased `ModId`) in `Py4GWCoreLib/mods_types.py`.
The value axis is **type-routed**: an `IntEnum` narrows the *subtype*, a number is a *threshold*
(direction-aware — see below), a callable is a predicate on the value.

```python
# -- presence / matching --
Item.Mods.HasMod(item_id, mod, *values)   -> bool   # mod present, optionally value/subtype-filtered
Item.Mods.HasAllMods(item_id, modlist)    -> bool   # every entry matches
Item.Mods.HasAnyMods(item_id, modlist)    -> bool   # any entry matches
#   modlist entry = mod | (mod, *values)

# -- reads --
Item.Mods.GetMods(item_id)                -> list[ModId]      # distinct mod ids present
Item.Mods.GetValues(item_id, mod)         -> list[int]        # value(s) of first match ([] if none)
Item.Mods.GetSubtype(item_id, mod)        -> IntEnum | None   # attribute / damage type / species …
Item.Mods.GetRaw(item_id, mod)            -> (arg1, arg2) | None
Item.Mods.GetName(mod)                    -> str              # the mod's effect/base name

# -- applied upgrades (prefixes/suffixes/inscriptions/runes/insignias) --
Item.Mods.GetUpgrades(item_id)            -> list[(name, Slot)]
Item.Mods.GetUpgradeInSlot(item_id, slot) -> str | None
Item.Mods.HasUpgradeInSlot(item_id, slot) -> bool
Item.Mods.GetSlot(item_id, upgrade_name)  -> Slot | None
Item.Mods.IsMaxed(item_id, upgrade_name)  -> bool

# -- raw modifier words (diagnostics; replaces Customization.Modifiers.*) --
Item.Mods.GetModifiers(item_id)           -> list[ItemModifier]
Item.Mods.GetModifierCount(item_id)       -> int
Item.Mods.ModifierExists(item_id, ident)  -> bool
Item.Mods.GetModifierValues(item_id, ident) -> (arg, arg1, arg2)
```

`Slot` (from `mods_core`): `Inherent, Prefix, Suffix, Inscription, Rune, Insignia`.

### Value routing in `HasMod(item_id, mod, *values)`

Each extra arg is dispatched by its Python type:

- **`IntEnum`** → subtype filter (e.g. `Attribute.Marksmanship`, `DamageType.Piercing`).
- **number** → **"that value or better"**, not exact. Direction is the *mod's* metadata
  (`better_low`): requirement is lower-is-better (`9` ⇒ req ≤ 9); damage/armor/health are
  higher-is-better (`15` ⇒ ≥ 15). No per-call parameter, no lambda needed for the common case.
- **callable** → `predicate(value) -> bool`, for anything the threshold shorthand can't express.

### Usage

```python
from Py4GWCoreLib.Item import Item
from Py4GWCoreLib.mods_types import ModifierIdentifier as ModId
from Py4GWCoreLib.enums_src.GameData_enums import Attribute, DamageType

Item.Mods.HasMod(item_id, ModId.AttributeRequirement, Attribute.Marksmanship, 9)  # Marks req ≤ 9
Item.Mods.HasMod(item_id, ModId.Damage, 15, 28)                                   # dmg ≥ 15–28
Item.Mods.HasAllMods(item_id, [
    ModId.DamageTypeProperty,                       # present (any)
    (ModId.AttributeRequirement, 9),                # req 9 or better
])
vals = Item.Mods.GetValues(item_id, ModId.Damage)   # e.g. [15, 28]
```

## Why the value arg varies — and where it comes from (RE)

A mod word is `identifier(16) + arg1(8) + arg2(8)`, but **which arg holds the value varies per
identifier** — arg2 for most, arg1 for some, both for compound (subtype-carrying) mods. This is not
a formula: the game's `CNameComposer::ProcessCodes` (~118 KB, `0x80a7ecdb`–`0x80a9baac`) is a
per-identifier code dispatch, and handlers like `ProcessAttribute` (`0x80a7e5a0`) even use
non-byte-aligned bit extraction (`value = (code>>1)&0xFFFF` + flag bits). There is **no static
value-arg table** in the binary.

**We derive it from the game itself, not from a JSON.** The per-identifier read rule
(value arg, subtype enum, better-direction) is declared in the `_Def` table inside
`Py4GWCoreLib/mods_core.py` — matched against the numbers the game *displays*. `value_of`,
`subtype_of`, and `is_better` read that table; `Item.Mods` calls them.

- **Confidence:** the value/threshold axis is solid (from displayed numbers). The subtype axis
  (which arg holds the enum for a few damage-type/species/condition mods) may need targeted
  handler RE to be 100% — see docs 06/09.

## Live layout

| File | What |
|---|---|
| `Py4GWCoreLib/Item.py` (`Item.Mods`) | the public API above |
| `Py4GWCoreLib/mods_core.py` | the one decoder + `_Def` read-rule table + `Slot`; `decode_item`, `find`, `value_of`, `subtype_of`, `is_better`, `upgrades_on`, `describe_item`, `raw_dump` |
| `Py4GWCoreLib/mods_types.py` | `ModifierIdentifier` (`ModId`) — the identifier constants (~548 entries) |
| `docs/item_mods/catalogs/mod_identifiers.csv` | identifier → value-arg + example effects (reference) |
| `docs/item_mods/catalogs/mod_master_list.csv` | the 310 real mods (293 game-verified + 17 hand-PvE), sourced |

## Validate before building on it

`Widgets/Coding/Debug/Py4GW/Item.Mods Test.py` — hover any item; it shows the `Item.Mods` decode
(id / arg1 / arg2 / value / subtype) next to the game's composed info-string. Confirm the value
matches the number the game renders; if a row is off, fix that identifier's `_Def` in
`mods_core.py`.

## Regenerating
- The `_Def` read rules + `ModifierIdentifier` derive from `game_mod_table.py` (Ghidra dump) +
  `game_mod_table_named.txt` (native composer binding, doc 08). Re-run the small generators in
  `docs/item_mods/tools/` / the inline snippets after a game patch.
