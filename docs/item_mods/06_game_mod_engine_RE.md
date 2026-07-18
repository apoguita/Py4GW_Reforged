# 06 — The Game's Mod Engine (Reverse-Engineering Findings)

> **Status:** RE findings, 2026-07-15. Addresses are from the symbol-rich **`Gw.wasm`**
> reference image (the repo's RE convention — `Gw.exe` is stripped to `FUN_xxxxxxxx`).
> These are *reference* addresses for understanding + for a static dump; live runtime
> resolution (if ever needed) uses the pattern/assertion anchors the way
> `Py4GW_Reforged_Native/offsets/item.json` already does.

## TL;DR

The game turns an item's mod codes into its displayed name/description with a single
class, **`ItemCommon::CNameComposer`**. There is **no flat "mod table"** you can read in
one shot — the identifier→meaning mapping is a large code dispatch (`ProcessCodes`) that
calls small **emitter** functions, each of which looks up its label in a small,
**bounds-checked pointer-array table** (`Const*GetName/Text(enum)`). Those label tables,
and several discrete data tables (per-`EItemType` upgrade slots, item formulas, PvP
unlock arrays), **are** cleanly dumpable.

Practical upshot: the cleanest design reads the game's already-composed strings for
**display**, and dumps only the small **structured** tables it needs for the **filter
taxonomy** — no hand JSON, no 10k-line hierarchy.

## The engine: `ItemCommon::CNameComposer`

Namespace `ItemCommon` (`Gw/Const/ConstItem.cpp`, assertion string @ `0010b5bf`).

| Symbol | Gw.wasm addr | Role |
|---|---|---|
| `CNameComposer::Compose(..., EItemType, ..., unsigned long const* codes, wchar_t const** name, wchar_t const** completeName, wchar_t const** infoString)` | `80a9d32f` | Top-level: mod codes → the 3 encoded strings |
| `CNameComposer::ProcessCodes(unsigned long const*, ...)` | `80a7ecdb` | **The per-mod decode loop** (dispatch by identifier). *Too large to decompile whole → it is a big dispatch, not one table.* |
| `CNameComposer::ProcessAttribute(unsigned long, unsigned int*)` | `80a7e5a0` | Attribute-requirement handling |
| `CNameComposer::CompoundArmor(...)` | `80a7af3a` | Emits an "Armor: N / Armor +N" line |
| `CNameComposer::CompoundDamageAttribRestricted(uint, uint, ETextStr)` | `80a7c47b` | Emits damage / attribute-restricted lines (21 xrefs) |
| `CNameComposer::CompoundSkill(ESkill, uint, uint)` | `80a7cbeb` | Emits skill-related lines |
| `CNameComposer::StatementInc(EPriority, EColor, ETextStr, ETextStr, wchar_t const*, int)` | `80a9baaf` | Adds one statement fragment |
| `CNameComposer::FinalizeStatement()` | `80a7bbab` | Closes a statement (42 xrefs — the workhorse) |

**Flow:** `Compose` → `ProcessCodes` reads each `(identifier, arg1, arg2)` code →
dispatches by identifier to a `Compound*`/`Process*` emitter → the emitter resolves its
label via a `Const*` table (below) → `TextEncode`/`TextEncodeCat` assembles the encoded
output string. The result is stored on the item as `name_enc` / `complete_name_enc` /
`info_string` — the very strings our diagnostic already decodes.

## The label tables (`Const*` — the actual "mod tables")

`ProcessCodes`' callees include these enum→text lookups. Two were decompiled and confirmed
to be **clean, bounds-checked pointer arrays** of the form `return base[enum_index];`:

| Symbol | Gw.wasm addr | Array base | Count | Bounds assert |
|---|---|---|---|---|
| `ConstItemGetColorString(EItemColor)` | `818b2857` | `0x0019c3c0` | 14 (0..0xD) | `color < ITEM_COLORS` |
| `ConstGetCharDamageText(ECharDamage)` | `818b9a47` | `0x002796e0` | 14 (0..0xD) | `damage < arrsize(s_charDamage)` |
| `ConstItemGetDescriptionText(EItemDescription)` | `818b2c40` | array @ `0x0019da70`, 360 | — | ⚠ NOT stat labels — this is the "Use to…" **usable/consumable** description table (faction, alcohol, tomes). Irrelevant to weapon/armor mods. |
| `ConstAttribGetName(ECharAttrib)` | `818b0b50` | — | — | — |
| `ConstGetCharDamagePrefix(ECharDamage)` | `818b9921` | — | — | — |
| `ConstGetCharKind(ECharKind)` | `818b9c93` | — | — | — |
| `ConstGetCharKindSlaying(ECharKind)` | `818b9db9` | — | — | — |
| `ConstGetCharConditionName(ECharCondition)` | `818b97fb` | — | — | — |
| `ConstGetSkill(ESkill)` | `818b3d99` | — | — | — |

Each `Const*` is `base[index]` returning an `ETextStr` string-table **id** (a uint32 index
into gw.dat, not a pointer). Dumping one = read its base array + count (from the bounds
check). **Correction (validated by resolving the ids in-client):** these tables are the
**value vocabularies** that fill the *variable* slot of a mod description — damage type,
attribute, species (slaying), condition, rarity color. They do **not** contain the stat
concept words ("Armor", "Health", "Damage", "requirement"); those are emitted directly by
the `Compound*` functions and are keyed off the **mod identifier**, not a lookup enum.
`ConstItemGetDescriptionText(EItemDescription)` is unrelated — it's the usable/consumable
"Use to…" text. The genuinely useful dumps are `ECharDamage`, `ECharAttrib`,
`ECharKindSlaying`, `ECharCondition` — and each already maps 1:1 to an existing project
enum (`DamageType`, `Attribute`, `ItemBaneSpecies`, `Ailment`), now confirmed correct.

## Discrete data tables (directly dumpable)

### Per-`EItemType` upgrade-slot / capability table — `DAT_ram_0015c6fc`

Used by `ItemCommon::TestUpgradeCompatibility` (`80a76dac`):
`*(uint*)(&DAT_0015c6fc + itemType * 0x10) >> slotBit & 1`, with `slotBit ∈ {6,7,8}`
(prefix / suffix / inherent). **Stride 0x10 (16 bytes) per `EItemType`.** First `uint32`
= slot/capability bitmask. Raw dump (first records):

| EItemType | first uint32 | bits 6/7/8 → allowed upgrade slots |
|---|---|---|
| 0 | `0x00000000` | none |
| 1 | `0x00000400` | (bit 10 only) |
| 2 (Axe) | `0x000001E9` | prefix + suffix + inherent |
| 3 | `0x00000000` | none |
| 4 | `0x00000182` | — |
| 5 | `0x000001E9` | prefix + suffix + inherent |

(The other 3 dwords per record hold related metadata — type-name `ETextStr` id, default
flags — to be fully mapped by the dumper.) Count = number of `EItemType` values.

### Others (anchored in the Native project's `offsets/item.json`)

- **Item formulas** — `ConstItem.cpp`, assert `formula < ITEM_FORMULAS`.
- **PvP item-upgrade array** + **`pvp_item_upgrade_name_func`** — `ConstItemPvp.cpp`,
  `ITEM_PVP_UNLOCK_COUNT` / `ITEM_PVP_ITEM_COUNT`. The PvP unlock system enumerates every
  upgrade component, so this array + its name function is a second, independent source of
  `upgrade → name` data.

## Two identifier conventions — reconciled to the engine

- `ItemModifier.identifier() = mod >> 16` (16-bit) is the code the game's `ProcessCodes`
  dispatches on. This is frenkeyLib's convention.
- `item_mods_src` strips 4 more bits (`(mod>>20)&0x3FF`); the dropped nibble is the
  `param`/label field the game reads separately.
See [`01_raw_modifier_layer.md`](01_raw_modifier_layer.md) §5.

## What we still need to extract (the one hard part)

The **identifier → category/value-semantics** mapping lives inside `ProcessCodes`' dispatch
(which emitter each identifier calls, and which arg is the value). Because `ProcessCodes`
won't decompile in one shot, this is extracted by disassembling its dispatch (jump table or
identifier-range branches) and mapping each identifier to its emitter. This is the primary
job of the dumper (doc: see the dumper script, next step **(b)**).

## The verdict for the redesign

1. **Display** — read the game-composed `info_string` / `name_enc` (already works; authentic
   + localized). No RE needed at runtime.
2. **Filter taxonomy** — dump the small structured tables:
   - `identifier → {emitter/category, value-arg}` from `ProcessCodes`' dispatch,
   - per-`EItemType` upgrade-slot table (`0015c6fc`),
   - optionally the `Const*` enum→label arrays for language-independent pick-list labels.
3. **Freshness** — a Ghidra dumper regenerates all of it per patch → never stale, never
   "missing data," never a maintained-by-hand JSON. It's the game's own data.

## Reference: confirmed Gw.wasm addresses

```
Compose ...................... 80a9d32f
ProcessCodes ................. 80a7ecdb   (too big to decompile; = dispatch)
ProcessAttribute ............. 80a7e5a0
CompoundArmor ................ 80a7af3a
CompoundDamageAttribRestricted 80a7c47b
CompoundSkill ................ 80a7cbeb
StatementInc ................. 80a9baaf
FinalizeStatement ............ 80a7bbab
TestUpgradeCompatibility ..... 80a76dac
TestTargetType ............... 80a76ce5
GetEquipMask / GetEquipSlot .. 80a76c6d / 80a76caa
GetTypeName .................. 80a76cd1
ConstItemGetDescriptionText .. 818b2c40   (EItemDescription → text, master label table)
ConstAttribGetName ........... 818b0b50
ConstGetCharDamageText ....... 818b9a47   (array @ 002796e0, 14)
ConstGetCharDamagePrefix ..... 818b9921
ConstGetCharKind ............. 818b9c93
ConstGetCharKindSlaying ...... 818b9db9
ConstGetCharConditionName .... 818b97fb
ConstGetSkill ................ 818b3d99
ConstItemGetColorString ...... 818b2857   (array @ 0019c3c0, 14)
DAT per-EItemType caps ....... 0015c6fc   (stride 0x10)
ConstItem.cpp assert string .. 0010b5bf
```
