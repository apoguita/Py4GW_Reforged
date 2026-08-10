# Item Mod System — Context & Reference

> **Status (2026-07-16):** Started as context-gathering (docs 01–05), then RE'd the game's
> mod system and built the new **`Item.Mods`** filter API on top of game-sourced data
> (docs 06–10). Docs 01–05 describe *what existed*; 06–10 are the RE + the new, game-derived
> mod layer that replaces the old `item_mods_src` / `Customization.Modifiers` for filtering.
> Nothing here is copied from a hand-authored JSON — see doc 10.

Guild Wars "item mods" (modifiers) are how every gameplay stat on an item is stored:
weapon damage, armor, requirements, prefixes ("Fiery"), suffixes ("of Fortitude"),
inscriptions, runes, and insignias are **all** encoded as a list of 32-bit modifier
words hanging off the item. Understanding — and *handling* — that list is the subject
of these docs.

## The one-paragraph mental model

Every item exposes **two independent data channels**:

1. **`item.modifiers`** — the authoritative gameplay data. A flat `list[ItemModifier]`,
   each a single 32-bit word packing `(identifier, arg1, arg2)`. This is where stats
   and upgrades actually live.
2. **The encoded name strings** (`GetNameEnc` / `GetCompleteNameEnc` /
   `GetSingleItemName` / `GetInfoString`) — the *display* channel: rarity color, the
   assembled "Fiery Sword of Fortitude" text, quantity. These are GW string-table
   codepoint arrays, decoded via a full RC4 + bit-unpack pipeline.

The mods (channel 1) are the source of truth. The encoded strings (channel 2) are only
for rendering names/tooltips. **Every mod system in this repo reads channel 1; they
differ enormously in how they turn those `(identifier, arg1, arg2)` triples into
meaning.**

## Document index

| File | Covers |
|------|--------|
| [`raw-modifier-layer.md`](raw-modifier-layer.md) | The C++ `ItemModifier` struct, exact bit layout, the `PyItem` binding surface, the **two different identifier conventions**, and the fact that the whole surface is **read-only**. |
| [`encoded-strings.md`](encoded-strings.md) | How encoded name/tooltip strings are sourced and decoded (`string_table.py`), and the inverse byte-*builder* (`encoded_strings.py` / `GWEncoded`). |
| [`current-python-system.md`](current-python-system.md) | The current `Py4GWCoreLib/item_mods_src/` system end-to-end: decode → parse → properties → upgrades. The **9,694-line** `upgrades.py` hierarchy. |
| [`frenkeylib-reference.md`](frenkeylib-reference.md) | The frenkeyLib `LootEx` **data-driven** model (JSON tables, generic matching) — the "adequate" reference — plus `marks_sources/mods_parser.py`. |
| [`comparison-and-painpoints.md`](comparison-and-painpoints.md) | Side-by-side of the two philosophies, the identifier-convention trap, what makes today's handling cumbersome, and the open gaps. |
| [`game-mod-engine-re.md`](game-mod-engine-re.md) | RE findings: the game's `CNameComposer`/`ProcessCodes` mod engine, the dumpable `Const*` label tables + per-`EItemType` table, and the plan to generate structured mod data from the client instead of a JSON. |
| [`game-mod-table.md`](game-mod-table.md) | The game's authoritative 390-entry mod table (`ConstItemPvp` unlock defs), struct layout, verified decodes, dumped to `tools/game_mod_table.py`. |
| [`native-name-binding.md`](native-name-binding.md) | Native binding (`PyItem.get_pvp_unlock_name_enc`) that names all 390 mods via the game's own composer — verified working; `game-mod-table-named.txt`. |
| [`item-catalogs.md`](item-catalogs.md) | **The whole universe** — the eight static item catalogs, their accessors, addresses, counts, and remaining passes. Tool-owned extraction data lives beside the debug widget, not in docs. |
| [`item-mods-api.md`](item-mods-api.md) | **The deliverable** — the `Item.Mods` filter API (self-contained, replaces `Customization.Modifiers`), the game-derived `VALUE_ARG` table + `ModId` constants, the 310-mod master list, and the in-client validator. |
| [`frenkeylib-consumer-contract-audit.md`](frenkeylib-consumer-contract-audit.md) | **Proposed migration contract** — makes Reforged the sole mod/rule authority; maps FrenkeyLib and Mark parser needs to public APIs, records owner gaps, and forbids raw-catalog fallback. |
| [`mod-system-research.md`](mod-system-research.md) | **Dedicated research + proposed enum design** — reconciles frenkey's JSON model, our `item_mods_src`, and `Examples/itemcompare.py` against live items: two-tier model, the identifier-convention trap, the empirical per-identifier formula (stable 60/62), the complete catalog-FK map, base-vs-upgrade unification, composite reconstruction, and the ER-style all-enum `ModDef` design (item's `list[int]` → FK match → formula → typed data). |
| [`item-mods-design.md`](item-mods-design.md) | **The agreed design** (supersedes 11's shape) — `Item.Mods` as a nested subclass replacing `Customization`: the two-axis model (effect-id vs named-upgrade + slots), declarative facts + one reader, the static `HasMod(item_id, mod, *values)` API with positional type-routed values, **exact-or-better direction-aware** matching, slots for salvage, dye split out to `Item.Dye`, data provenance, and the Customization→Properties/Mods/Dye migration table. |

## Where everything lives (quick map)

**C++ backend — `../Py4GW_Reforged_Native`**
- `include/GW/context/item.h:79-96` — `ItemModifier` struct + `Item.mod_struct` array.
- `src/GW/item/item_bindings.cpp:36-69,389-397` — the Python-bound `ItemModifier` class.
- `src/GW/item/item_bindings.cpp:212-488` — `PyItem` binding (`modifiers` list, enc-name getters, flags).
- `stubs/PyItem.pyi` — the type-stub surface the Python side consumes.

**Python — current system, `Py4GWCoreLib/item_mods_src/`**
- `decoded_modifier.py` — raw 32-bit word → `DecodedModifier`.
- `types.py` (1,231 lines) — `ModifierIdentifier` (~90), `ItemUpgradeId` (~400), `ItemUpgrade` tables.
- `item_modifier_parser.py` — the orchestrator.
- `upgrade_parser.py` — identifier → property factory + upgrade composition.
- `properties.py` (700 lines) — one `ItemProperty` dataclass per stat, each hand-building tooltip bytes.
- `upgrades.py` (**9,694 lines**) — one `Upgrade` subclass per prefix/suffix/inscription/rune/insignia.
- `item_mod.py` — the public API (`ItemMod.get_upgrade`, `get_item_upgrades`).

**Python — decode/build engine, `Py4GWCoreLib/native_src/internals/`**
- `string_table.py` — GW string-table decoder (RC4, bit-unpack, formatted-string tree).
- `encoded_strings.py` — `GWStringEncoded` + `GWEncoded` byte-template builder.

**Python wrappers / cache**
- `Py4GWCoreLib/Item.py:429-459` — `Item.Customization.Modifiers.GetModifiers(...)` and friends.
- `Py4GWCoreLib/GlobalCache/ItemCache.py:559-596` — cached mod getters (names cached, mods not).

**frenkeyLib reference — `Sources/frenkeyLib/`**
- `LootEx/models.py` — `ModifierInfo` / `ItemMod` / `Rune` / `WeaponMod` / `ItemModifiersInformation`.
- `LootEx/enum.py:235-272` — `ModType`, `ModifierValueArg`, `ModifierIdentifier`, `ModsModels`.
- `LootEx/data.py` — loads `weapon_mods.json` / `runes.json`.
- `Sources/marks_sources/mods_parser.py` — standalone JSON-driven matcher.

**Legacy / examples (the "old" pattern)**
- `Examples/mods.py`, `Examples/mod handler.py`, `Examples/ItemCompare.py` — hand-table decoders.

## Glossary

- **Modifier / mod** — one 32-bit word on an item: `(identifier, arg1, arg2)`.
- **Identifier** — which *kind* of modifier this is. Two conventions in the repo (see doc 01).
- **arg1 / arg2** — the two 8-bit payload bytes (e.g. armor value, attribute id, chance %).
- **Property** — a decoded, typed reading of a single modifier (Py4GWCoreLib term).
- **Upgrade** — a composed, named thing made of one or more modifiers: a prefix, suffix,
  inscription, rune, or insignia.
- **Inherent** — a stat that is intrinsic to a green/unique item rather than an applied upgrade.
- **Encoded string** — a GW string-table codepoint array for display text (not a mod).
