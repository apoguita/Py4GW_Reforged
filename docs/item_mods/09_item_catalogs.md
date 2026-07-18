# 09 — Item Catalogs (the whole universe)

Every static item-related catalog in the client, dumped from `Gw.wasm` and formatted.
Regenerate with the Ghidra inline dumper + `tools/format_catalogs.py`.

## Files

- `catalogs/raw_item_catalogs.json` — raw dump of every catalog (fields as hex uint32).
- `catalogs/<name>.csv` — one clean CSV per catalog (below).
- `tools/format_catalogs.py` — offline: raw JSON → CSVs (merges real mod codes into `pvp_unlocks`).

## The catalogs

| Catalog | CSV | Accessor (Gw.wasm) | Array base | Count | Stride | Kind | Status |
|---|---|---|---|---|---|---|---|
| Colors | `colors.csv` | `ConstItemGetColorString` @818b2857 | `0x0019c3c0` | 14 | 4 | text-id | ids ✓, text ✓ (resolved) |
| Attributes | `attributes.csv` | `ConstItemGetAttributeText` @818b2b19 | `0x0019d1b0` | 559 | 4 | text-id | ids ✓, **text pending** |
| Descriptions | `descriptions.csv` | `ConstItemGetDescriptionText` @818b2c40 | `0x0019da70` | 360 | 4 | text-id | ids ✓, text ✓ (usable "Use to…" strings) |
| **Formulas** (crafting recipes) | `formulas.csv` | `ConstItemGetFormulaDef` @818b2d67 | `0x0019e010` | 1498 | 20 | struct | **done** — price (float f00) + ingredients `[element:qty]` (via `formulas_recipes.json`) |
| Elements (materials) | `elements.csv` | `ConstItemGetElementDefClient` @818b2e8f | `0x001a5520` | 41 | 12 | struct | `name_id` (text) + f04/f08 |
| Books | `books.csv` | `ConstItemGetBookDefClient` @818b2fb6 | `0x001a5710` | 33 | 28 | struct | raw fields (low priority) |
| PvP base items | `pvp_items.csv` | `ConstItemPvpGetItemDef` @818b3398 | `0x001b2950` | 343 | 36 | struct | partial fields named |
| **PvP unlocks (mods)** | `pvp_unlocks.csv` | `ConstItemPvpGetUnlockDef` @818b34bf | `0x001b5990` | 390 | 40 | struct | **fully done** — upgrade_id + real codes + names (see doc 07/08) |

Char-enum label tables (damage types, char-attributes, species, conditions) were dumped
separately — see `tools/game_mod_tables.py` + `game_mod_tables_resolved.txt` (doc 06).

## The two-stage pipeline (why strings need the game)

The `ConstItem*` tables store **string ids** (ETextStr — pointers into `gw.dat`), not words.
`gw.dat` only loads in the running client, so strings must be fetched in-game. Two stages:

1. **Offline (Ghidra):** dump the structure → `raw_item_catalogs.json` + `formulas_recipes.json`
   (ids, numbers, codes, struct fields).
2. **In-game (one widget):** run **`Dump Item Catalogs`** (`Widgets/Coding/Debug/Py4GW/`) — it
   resolves every ETextStr id to its word via the string table, composes the 390 mod names via the
   native binding, and writes the **finished, string-filled** CSVs into `catalogs/`. This is the
   single script that completes the catalogs.

(`tools/format_catalogs.py` is an offline preview that produces the same CSVs *without* strings; the
in-game widget supersedes it for the final output. Earlier per-purpose resolvers — `Resolve Mod
Tables`, `Dump Named Mod Table`, `Resolve Catalog Text` — are now folded into `Dump Item Catalogs`.)

## Status

- **Done:** discovery; raw dump of all 8 catalogs; CSV formatting; the **mod table** fully
  interpreted (codes + names); **formulas** fully interpreted (crafting recipes: price +
  ingredients); **elements** labeled.
- **One user action left:** run **`Dump Item Catalogs`** in-game → writes the finished,
  string-filled CSVs (all text resolved, mod names composed).
- **Optional / low-priority remaining:** name the remaining `books` and `pvp_items` struct fields;
  locate + dump `ITEM_MODELS` / `ITEM_MATERIALS` / `ITEM_TYPES` (no simple `ConstItemGet*` accessor —
  reached via other systems).

## Regeneration

1. In Ghidra (Gw.wasm), run the inline dumper (the Java block that writes `raw_item_catalogs.json`;
   `GHIDRA_MCP_ALLOW_SCRIPTS=1`). Addresses above; re-verify per game patch.
2. `python docs/item_mods/tools/format_catalogs.py` → CSVs.
3. In-client, run **Resolve Mod Tables** / **Dump Named Mod Table** for the text/name layers.
