# 10 — `Item.Mods` API (the mod filter)

The clean, game-sourced mod-read/filter layer that the whole RE effort was building toward.
Self-contained, reads the raw `ItemModifier` words directly, and **does not** depend on the
(deprecated) `Item.Customization.Modifiers`.

## The API — `Py4GWCoreLib/Item.py`

```python
Item.Mods.GetAll(item_id)                 -> list[Mod]
Item.Mods.Get(item_id, modid)             -> Mod | None
Item.Mods.GetValue(item_id, modid)        -> int | None
Item.Mods.Has(item_id, modid, value=None) -> bool
Item.Mods.HasAll(item_id, modlist)        -> bool   # modlist = [modid | (modid, value), ...]
Item.Mods.HasAny(item_id, modlist)        -> bool
```

`Mod` (module-level value object):
```python
Mod: id, arg1, arg2, arg, upgrade_id, raw
  .value    -> the mod's value in the correct arg (per VALUE_ARG; see below)
  .subtype  -> arg1 for compound ('both') mods (attribute / damage type / species), else None
  .matches(value) -> None=any, int=exact (== .value), callable=predicate(mod)
```

- **`modid`** = the game modifier identifier, `GetIdentifier()` = `mod >> 16` (game-native; not
  the stripped/legacy convention).
- **`value`** = `None` (presence) / `int` (exact) / `callable` (thresholds & ranges).

### Usage
```python
from Py4GWCoreLib.Item import Item
from Py4GWCoreLib.mod_ids import ModId

Item.Mods.HasAny(item_id, [ModId.LIFE_DRAINING_HEALTH_REGENERATION])   # has Vampiric
Item.Mods.HasAll(item_id, [(ModId.ARMOR, lambda v: v >= 8)])           # armor bonus >= 8
lvl = Item.Mods.GetValue(item_id, ModId.ARMOR)                         # exact value
```

## Why `.value` needs a table — and where it comes from (RE)

A mod word is `identifier(16) + arg1(8) + arg2(8)`, but **which arg holds the value varies per
identifier** — arg2 for most, arg1 for some, both for compound mods. This is not a formula: the
game's `CNameComposer::ProcessCodes` (~118 KB, `0x80a7ecdb`–`0x80a9baac`) is a per-identifier code
dispatch, and handlers like `ProcessAttribute` (`0x80a7e5a0`) even use non-byte-aligned bit
extraction (`value = (code>>1)&0xFFFF` + flag bits). There is **no static value-arg table** in the
binary — which is exactly why hand-authored JSONs carry a `modifier_value_arg` per mod.

**We derive it from the game itself, not from a JSON:** match the numbers the game *displays*
(`game_mod_table_named.txt`) back to the raw code args (`game_mod_table.py`). Result → 37 arg2,
27 arg1, 18 both. That is `Py4GWCoreLib/mods_value_args.py` (`VALUE_ARG`), which `Mod.value` uses.

- **Confidence:** the value/threshold axis is solid (from displayed numbers). The subtype axis
  (which arg holds the enum for a few damage-type/species/condition mods) may need targeted
  handler RE to be 100% — see docs 06/09.

## Supporting artifacts (all game-derived, no JSON)

| File | What |
|---|---|
| `Py4GWCoreLib/mods_value_args.py` | `VALUE_ARG` — identifier → which arg is the value |
| `Py4GWCoreLib/mod_ids.py` | `ModId` IntEnum — 82 identifier constants, names from the game's own effect text (first pass; rename as used) |
| `docs/item_mods/catalogs/mod_identifiers.csv` | identifier → value-arg + example effects (the reference) |
| `docs/item_mods/catalogs/mod_master_list.csv` | the 310 real mods (293 game-verified + 17 hand-PvE), sourced |

## Validate before building on it

`Widgets/Coding/Debug/Py4GW/Item.Mods Test.py` — hover any item; it shows `Item.Mods` decode
(id / arg1 / arg2 / `.value` / `.subtype`) next to the game's composed info-string. Confirm
`.value` matches the number the game renders; if a row is off, fix that identifier in
`mods_value_args.py`.

## Regenerating
- `mods_value_args.py` + `mod_ids.py` + `mod_identifiers.csv` derive from `game_mod_table.py`
  (Ghidra dump) + `game_mod_table_named.txt` (native composer binding, doc 08). Re-run the
  small generators in `docs/item_mods/tools/` / the inline snippets after a game patch.
