# 01 — The Raw Modifier Layer (C++ backend + PyItem binding)

This is the foundation everything else sits on: the single 32-bit word that *is* a mod,
how it's exposed to Python, and two traps that make downstream code confusing — the
**two identifier conventions** and the **read-only** nature of the whole surface.

## 1. The `ItemModifier` struct — one 32-bit word

Backend struct — `../Py4GW_Reforged_Native/include/GW/context/item.h:79-88`:

```cpp
struct ItemModifier {
    uint32_t mod = 0;

    uint32_t identifier() const { return mod >> 16; }                 // high 16 bits
    uint32_t arg1()       const { return (mod & 0x0000FF00) >> 8; }   // bits 8..15
    uint32_t arg2()       const { return (mod & 0x000000FF); }        // bits 0..7
    uint32_t arg()        const { return (mod & 0x0000FFFF); }        // low 16 bits
    operator bool()       const { return mod != 0; }
};
static_assert(sizeof(ItemModifier) == 0x4, "ItemModifier size mismatch");
```

Bit layout of the single `mod` word:

```
 31                16 15         8 7          0
+--------------------+-----------+-----------+
|     identifier     |   arg1    |   arg2    |
+--------------------+-----------+-----------+
|<---- mod >> 16 --->|<------- arg (low 16) ->|
```

- `identifier` = `mod >> 16`
- `arg1` = bits 8–15, `arg2` = bits 0–7
- `arg` = low 16 bits (arg1·256 + arg2)
- "valid" = the word is non-zero

Each item owns a heap array of these — `include/GW/context/item.h:90-96`:

```cpp
/* +h0010 */ ItemModifier* mod_struct;      // array of mods
/* +h0014 */ uint32_t      mod_struct_size; // element count
```

The backend lookup helper (`src/GW/context/item.cpp:48-56`) just linear-scans that array
for a matching `identifier()`. Several PyItem-visible booleans/values are derived by
finding a specific mod and reading its args — e.g. `uses` from mod `0x2458` arg2, kit
type from mod `0x25E8` arg1, rare-material from mod `0x2508` arg1.

## 2. The Python-bound `ItemModifier` class

Important subtlety: the class exposed to Python is **not** the backend struct above. It's
a self-contained "SafeItemModifier" over a raw `uint32_t`, in an anonymous namespace —
`src/GW/item/item_bindings.cpp:36-69`, registered at `389-397`:

```cpp
py::class_<ItemModifier>(m, "ItemModifier")
    .def(py::init<uint32_t>())
    .def("GetIdentifier", &ItemModifier::GetIdentifier)  // mod >> 16
    .def("GetArg1",       &ItemModifier::GetArg1)         // (mod & 0xFF00) >> 8
    .def("GetArg2",       &ItemModifier::GetArg2)         // mod & 0xFF
    .def("GetArg",        &ItemModifier::GetArg)          // mod & 0xFFFF
    .def("IsValid",       &ItemModifier::IsValid)         // mod != 0
    .def("GetModBits",    &ItemModifier::GetModBits)      // 32-char MSB-first binary string
    .def("ToString",      &ItemModifier::ToString);       // "Modifier ID: .. Arg1: .. Arg2: .."
```

The bit math is identical to the backend struct. Notes:
- The constructor takes the **raw 32-bit word**.
- `GetModBits()` returns the full 32 bits as a binary **string** (the Python side parses it
  back to an int — see doc 03).
- C++ also has `GetIdentifierBits`/`GetArg1Bits`/… but only `GetModBits` is bound.
- There is **no setter** and no mutator anywhere. This is a read-only value type.

Type stub: `stubs/PyItem.pyi:14-22`.

## 3. `PyItem.modifiers` — the list

`src/GW/item/item_bindings.cpp:272-275` fills the list once per `GetContext()`:

```cpp
modifiers.clear();
for (uint32_t i = 0; i < item->mod_struct_size; ++i)
    modifiers.emplace_back(item->mod_struct[i].mod);   // raw .mod word
```

Exposed `def_readonly("modifiers", ...)` (`:445`). So `PyItem.modifiers` is a plain
Python list of the value-type above, rebuilt from live game memory each refresh. There is
**no** mod caching (the Python `ItemCache` caches decoded *names*, never mods —
`GlobalCache/ItemCache.py:559-596`).

## 4. Mod/inscription flags on PyItem

These are **not** read from the mod list — they come from the item's `interaction` bitmask
(and one from the encoded name). Set in `GetContext()` (`item_bindings.cpp:289-320`):

| PyItem field | Backend derivation |
|---|---|
| `is_inscribable` | `(interaction & 0x08000000) != 0` |
| `is_prefix_upgradable` | `((interaction >> 14) & 1) == 0` |
| `is_suffix_upgradable` | `((interaction >> 15) & 1) == 0` |
| `is_inscription` | `(interaction & 0x25000000) == 0x25000000` |
| `is_identified` | `(interaction & 1) != 0` |
| `is_rarity_blue` | `single_item_name[0] == 0xA3F` (**encoded-name** first codepoint, not interaction) |
| `is_rarity_purple/green/gold` | `interaction & 0x400000 / 0x10 / 0x20000` |

## 5. ⚠️ Two identifier conventions (the biggest trap)

Both mod systems in this repo key off "the identifier" — but they mean **different bit
ranges of the same word**:

- **frenkeyLib** (and the legacy examples) use the raw 16-bit `GetIdentifier()` = `mod >> 16`.
  Its `ModifierIdentifier` enum values are the full 16-bit numbers, e.g.
  `Requirement = 10136 = 0x2798`, `Damage = 42920 = 0xA7A8`.
- **Py4GWCoreLib `item_mods_src`** strips **4 more bits**: `stripped = (GetIdentifier() >> 4) & 0x3FF`
  = `(mod >> 20) & 0x3FF`. Its `ModifierIdentifier` enum values are these 10-bit numbers,
  e.g. `AttributeRequirement = 0x279`, `Damage = 0x27A`.

They are the same underlying identifiers at different strip levels:

```
0x2798 >> 4 & 0x3FF = 0x279   (frenkeyLib "Requirement"  ⇔  Py4GWCoreLib "AttributeRequirement")
0xA7A8 >> 4 & 0x3FF = 0x27A   (frenkeyLib "Damage"       ⇔  Py4GWCoreLib "Damage")
```

The low nibble that Py4GWCoreLib discards is the **param / label** field
(`ItemModifierParam`: `LabelInName = 0x0`, `Description = 0x8` — `item_mods_src/types.py:26`).
So `0x2798` = identifier `0x279` with param `0x8` (Description).

**Consequence:** you cannot mix identifier tables between the two systems, and any new
system has to pick a convention and state it loudly. See doc 05 for the full trap writeup
(including a likely-latent bug in how Py4GWCoreLib extracts `param`).

## 6. The surface is entirely READ-ONLY

There is **no API — Python or C++ — to add, remove, or edit a modifier.**

- `ItemModifier` (both struct and bound class) exposes only getters; the bound class holds
  a private `uint32_t` with no setter.
- `PyItem.modifiers` is `def_readonly` and rebuilt from memory each refresh.
- Backend `Item::GetModifier()` returns a pointer for *reading*; nothing writes `mod_struct`.
- The only mod-related *matching* op is read-only: `GetItemByModelIdAndModifiers`
  (`item_methods.cpp:207-224`) `memcmp`s a caller-supplied mod array to find a matching item.

Item *actions* that exist are gameplay operations, not mod edits: `use_item_by_id`,
`equip_item_by_id`, `drop_item_by_id`, `salvage_start`, `identify_item`, `destroy_item`,
gold ops, storage ops (`item_bindings.cpp:490-594`). To *change* an item's mods in-game you
must salvage / identify / apply an upgrade component through the game's own flow — there is
no direct mod-write.

> **Design implication:** anything the redesign does with mods is a **read + interpret**
> problem, not a mutation problem. "Applying a mod" means driving the game's salvage/apply
> actions, not writing bits.

## 7. Relevant enums in the C++ headers

- `Rarity` (`include/GW/common/constants/item.h:17-23`): `White, Blue, Purple, Gold, Green`.
- `DyeColor` (`constants/item.h:25-39`), `BagType` (`:7-14`).
- `ItemType` (`include/GW/common/constants/constants.h:137-142`): `Salvage, Axe=2, …, Shield=24, Staff=26, Sword, Daggers=32, Scythe=35, Spear`.
- **No** dedicated enum of mod/upgrade identifiers exists in C++ — identifiers appear as
  bare hex literals in `item.cpp`. All identifier *taxonomy* lives on the Python side.
