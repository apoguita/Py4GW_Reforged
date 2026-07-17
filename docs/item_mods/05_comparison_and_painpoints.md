# 05 — Comparison & Pain Points

This doc frames *why* the current item-mod handling is cumbersome. It is descriptive, not
prescriptive — it does not propose the new design, it lays out the facts the new design has
to reckon with.

## 1. Two philosophies, side by side

| | `Py4GWCoreLib/item_mods_src` (current) | frenkeyLib `LootEx` (reference) |
|---|---|---|
| Approach | **Code-driven** — a class per upgrade | **Data-driven** — JSON tables + generic dataclasses |
| Size | `upgrades.py` **9,694** lines + `properties.py` **700** + `types.py` **1,231** | `models.py` mod section ~1,000 lines + JSON |
| Identifier convention | 10-bit stripped `(mod>>20)&0x3FF` | full 16-bit `mod>>16` |
| Identifier count | ~90 `ModifierIdentifier` + ~400 `ItemUpgradeId` (hard allow-list) | ~11 special-cased; rest generic |
| Adding a new mod | new enum id + `ItemUpgrade` mapping + `Upgrade` subclass + `upgrade_info` + hand-encoded tooltip bytes | add a row to `weapon_mods.json` / `runes.json` |
| Typed fields | Yes — `.chance`, `.armor_penetration`, `.health`, … | Generic — `Value`, `Arg1`, `Arg2`, `IsMaxed` |
| Tooltip text | Re-encodes stats to GW string bytes, decodes back (authentic, localized) | Placeholder substitution into scraped localized names |
| Names source | Hand-built encoded byte fragments | Scraped from the live game into JSON |
| Unknown mods | **Dropped** (allow-list) | Kept generically (still a triple) |
| Coverage | Exhaustive incl. niche conditionals | Good for loot-relevant mods; thinner on niche stats |
| Built for | Full typed inspection / tooltips | Loot / salvage / rule decisions |

Neither is what's wanted: the current one is exhaustive but enormous and rigid; the
reference is compact and flexible but loses typed richness and depends on external JSON.

## 2. The identifier-convention trap

The single biggest source of confusion. Both systems read the same 32-bit word, but:

```
raw word:      identifier(16) | arg1(8) | arg2(8)
frenkeyLib id: mod >> 16                          → e.g. 0x2798 "Requirement"
item_mods_src: (mod >> 20) & 0x3FF                → e.g. 0x279  "AttributeRequirement"
               (drops the low 4-bit "param" nibble: LabelInName=0x0 / Description=0x8)
```

Same physical mod, two different integer identifiers, two disjoint enum tables, two disjoint
name tables. You **cannot** copy an identifier from one system to the other without the
`>>4 & 0x3FF` conversion. Any new system must pick one convention and document it at the top.

## 3. Concrete pain points in the current system

1. **Class explosion.** `upgrades.py` is 9,694 lines: one `dataclass` per upgrade
   (`BarbedUpgrade`, `FuriousUpgrade`, `RuneOfMinorVigor`, every insignia, every inscription,
   every attribute rune). `properties.py` adds ~70 stat classes. Most of the volume is
   boilerplate.

2. **Magic-byte tooltip encoding.** Every property/upgrade hand-builds GW string-table bytes,
   e.g. `bytes([*GWEncoded.ITEM_BASIC, 0x89, 0xA, 0xA, 0x1, 0x4E, 0xA, ...])`. These are
   unreadable, error-prone, and duplicated across dozens of classes. This is the direct cost
   of the "round-trip through the real string table" choice (doc 02 §3).

3. **High cost to add anything.** A new upgrade needs edits in ≥3 files: an `ItemUpgradeId`
   enum entry, an `ItemUpgrade` `{ItemType: id}` mapping, and an `Upgrade` subclass with an
   `upgrade_info` instruction tuple — plus usually a hand-encoded tooltip.

4. **Hard allow-list drops data.** `DecodedModifier.from_runtime` returns `None` for any mod
   whose stripped identifier isn't in the `ModifierIdentifier` enum
   (`decoded_modifier.py:51-53`). Unknown or new mods vanish silently rather than surfacing as
   "unknown."

5. **Likely-dead `param` computation.** `param_value = (runtime_identifier >> 16) & 0xF`
   (`decoded_modifier.py:57`) always evaluates to `0`/`LabelInName`, because
   `runtime_identifier` is already `mod >> 16`. The real param bits are the low nibble that
   `stripped_identifier` discards. **Flag for verification** — if `param` matters anywhere,
   it's silently always `LabelInName`.

6. **Redundant bit work across the C++/Python boundary.** C++ already exposes
   `GetIdentifier/GetArg1/GetArg2/GetArg`. Python ignores most of that and re-parses
   `GetModBits()` (a 32-char **string**) back into an int to recover `upgrade_id`/`flags`
   (`decoded_modifier.py:54`). Passing bits as a decimal string and re-parsing them is a smell.

7. **No mod caching.** `GetModifiers` returns the live list each call; parsing/upgrade
   composition runs on demand (partly mitigated by `@frame_cache` on `get_item_upgrades`).

8. **Two decoders in the tree.** `native_src/internals/string_table.py` and
   `frenkeyLib/Core/encoded_names.py` are near-duplicate string-table decoders.

9. **Two mod models in the tree.** `item_mods_src` and `LootEx/models.py` (+
   `marks_sources/mods_parser.py`) are three parallel implementations of "decode a mod."
   `ItemHandling` consumes the first; `LootEx` uses its own; examples use ad-hoc tables.

10. **Async name gotcha.** Any tooltip/name is `""` on first request and appears a frame
    later (doc 02 §2). UIs must tolerate this.

## 4. What is fundamentally fixed vs. free to change

**Fixed (game/backend reality):**
- The 32-bit `(identifier, arg1, arg2)` word layout (doc 01 §1).
- Mods are **read-only** — no add/remove/edit API exists in Python or C++ (doc 01 §6).
  "Applying a mod" = driving the game's salvage/identify/apply-upgrade actions.
- Encoded names decode asynchronously through the `gw.dat` string table (doc 02).
- Mods (stats) and encoded names (display) are separate channels.

**Free to change (all Python):**
- The identifier convention and taxonomy.
- Whether upgrades are code (classes) or data (tables) — or a hybrid.
- How tooltip text is produced (hand-encoded bytes vs. scraped names vs. plain formatting).
- Whether unknown mods are dropped or surfaced.
- Caching strategy.
- How many parallel implementations exist (consolidation opportunity).

## 5. Open questions for the redesign conversation

These are the decisions the user's "what I need" will resolve — captured here, not answered:

- **Convention:** standardize on `mod >> 16` (frenkeyLib/game-native) or the stripped 10-bit
  id? Whichever, one convention, stated once.
- **Data vs. code:** table-driven mods (like `LootEx`) with an optional typed overlay for the
  handful of mods that benefit from named fields?
- **Tooltips:** keep authentic string-table round-tripping, or accept simpler formatted text
  and reserve encoded strings for names only?
- **Unknown mods:** surface as first-class "unknown (identifier, arg1, arg2)" instead of
  dropping?
- **Consolidation:** one decoder, one mod model — retire the duplicates?
- **Scope:** what does the user actually need to *do* with mods (filter loot? compare items?
  build salvage rules? display tooltips?) — that determines how much typed richness is worth
  keeping from `item_mods_src`.

> When the redesign direction is chosen, add a `06_redesign.md` here and link it from the
> README.
