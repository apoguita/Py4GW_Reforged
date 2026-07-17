# 07 — The Game's Mod Table (extracted)

> **This is the deliverable:** the game's own authoritative item-mod table, extracted from
> the client — no hand-authored JSON involved. Addresses from `Gw.wasm`.

## Source in the client

Two static arrays in `ConstItemPvp.cpp`, reached by these accessors:

| Accessor | Array | Stride | Count | Contents |
|---|---|---|---|---|
| `ConstItemPvpGetUnlockDef(idx)` @ `818b34bf` | `DAT@0x001b5990` | `0x28` | `0x186` = **390** | **the mod table** — every upgrade component (weapon prefixes/suffixes, runes, insignias, inscriptions) |
| `ConstItemPvpGetItemDef(idx)` @ `818b3398` | `DAT@0x001b2950` | `0x24` | `0x157` = 343 | base PvP items (weapon/armor skins) — not yet dumped |

Each is bounds-checked (`unlockIndex < ITEM_PVP_UNLOCK_COUNT` / `index < ITEM_PVP_ITEM_COUNT`).

## Unlock-def struct (0x28 / 40 bytes)

| Offset | Field | Notes |
|---|---|---|
| `+0x00` | `model_id` | the upgrade component's item model id |
| `+0x04` | `name_id` | ETextStr id (base component name, e.g. "Axe Haft") |
| `+0x10` | `mask` | item-type / slot bitmask |
| `+0x1c` | *(not a description id)* | ⚠ earlier assumed to be a description ETextStr id — WRONG. Resolving it yields unrelated strings. The mod's name/description is **not stored**; it is composed from the codes by `CNameComposer` at runtime. Field's true meaning still unknown (increments per variant; possibly an internal/sort id). |
| `+0x20` | `cnt` | number of mod-code words (seen: 3 or 5) |
| `+0x24` | `codes_ptr` | → parallel mod-code array (`DAT@0x001ba480`), `cnt` × uint32 |

The **mod codes** are ordinary 32-bit modifier words (`identifier = word>>16`, `arg1 = bits 8-15`,
`arg2 = bits 0-7`). Layout per unlock: `codes[0]` = the **Upgrade** modifier (identifier `0x2408`)
whose low 16 bits are the **`upgrade_id`**; middle code(s) = `TooltipDescription` (`0x2530`/`0x2532`);
the remaining code(s) = the **effect** (damage type, attribute, +enchant, etc.).

## Verified decodes (from raw bytes — nothing hand-authored)

| idx | upgrade_id | codes | meaning |
|---|---|---|---|
| 1–4 | `0x81`–`0x84` | `…24B8 0300/0B00/0400/0500` | **Icy/Ebon/Shocking/Fiery Axe Haft** (DamageType Cold/Earth/Lightning/Fire) |
| 17–19 | `0x99`–`0x9B` | `…23B8 0005` | **Furious** (axe/hammer/sword) |
| 22–25 | `0xAF` | `…21E8 0001/0201/0101/0301` | **Minor Mesmer Rune** of Fast Casting / Domination / Illusion / Inspiration (`AttributeRune`, arg1=attribute) |
| 48–51 | `0xB5` | `…21E8 …02, …20D8 0023` | **Major Mesmer Rune** — attribute +2 **and −35 Health** (`HealthMinus` arg2=0x23) |
| 151 | `0xE2` | `…22B8 000A` | **of Enchanting** (sword) = `IncreaseEnchantmentDuration` — *the "+enchant" modifier* |
| 158 | `0x101` | `…27EA 02C2` | **Superior Vigor** rune |
| 289 | `0x16A` | `…2238 000A, …2018 000A` | **To the Pain** inscription (+damage%, −armor while attacking) |
| 290 | `0x1E6` | `…26D8 0500` | **Survivor** insignia |

The `upgrade_id`s match the existing `ItemUpgradeId` enum values — i.e. the RE **validates** that
enum against the game. Coverage: **390 unlocks / 294 distinct upgrade_ids**, all categories.

## Dumped output

- `docs/item_mods/tools/game_mod_table.py` — `MOD_UNLOCKS`, one dict per unlock:
  `{i, model, name_id, desc_id, mask, cnt, upgrade_id, codes[]}`.
- Regenerate per patch via the inline Ghidra dumper (needs `GHIDRA_MCP_ALLOW_SCRIPTS=1`).

## Remaining to make it usable

The display name/description is **not a lookup** — the game composes it from `codes` via
`CNameComposer`. `name_id` gives only the base component ("Axe Haft", "Mesmer Rune", "Insignia").
To get the exact names for all 390:

1. **(recommended) Bind the game's composer.** `ItemCliPvpUnlockGetName(idx, …, codes, &name, &desc)`
   @ `80ac4095` (or `CNameComposer::Compose` @ `80a9d32f`) takes the unlock's mod codes and returns
   the exact name + description. Add a thin binding in the Native `Py4GW.dll`; then dump names by
   running each unlock's codes through it. Authoritative, no reimplementation.
2. **(alternative) Reproduce composition in Python** from `codes` + the dumped label tables
   (`ECharDamagePrefix`, `ECharAttrib`, …). Works for the regular families; risks diverging from the
   game on edge cases (≈ reimplementing `ProcessCodes`).
3. Independently, `codes[last]` already gives the matchable **effect signature** via the existing
   modifier decode (identifier + args), so filtering by effect works now even before names.
4. Optionally dump the 343-entry base-item table the same way.
