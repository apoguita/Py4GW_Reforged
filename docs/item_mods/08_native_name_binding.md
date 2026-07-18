# 08 — Native binding: name the mod table via the game's composer

The mod name/description is **composed by the game from the mod codes** (doc 07), not stored
as a lookup. To get exact names for all 390 unlocks, we bind the game's own composer.

## Verified call chain (RE, Gw.wasm)

`CUnlockMgr::ItemGetName` reads the static unlock def's count (`+0x20`) and codes (`+0x24`)
and calls `ItemCliPvpUnlockGetName(id, flag, count, codes, &name, &desc)` @ `0x80ac4095`,
which pulls context via `PropGet(0x10)`, the base name/mask from `ConstItemPvpGetUnlockDef(id)`
@ `0x818b34bf`, and runs `CNameComposer::Compose`. Outputs are **encoded** wchar strings
(same format as item `name_enc`/`info_string`) → decode with `string_table`.

This path uses the **static** table + a fallback, so it names any of the 390 regardless of
account unlock state. (The pre-existing `g_pvp_item_upgrade_name_func` path is guarded to the
account's *unlocked* array, so it can't cover all 390 — hence the two new functions.)

## C++ changes (Py4GW_Reforged_Native) — DONE, needs rebuild

- `offsets/item.json` — two assertion-anchored resolvers:
  `const_item_pvp_get_unlock_def_func` (anchor `ConstItemPvp.cpp` + `unlockIndex < ITEM_PVP_UNLOCK_COUNT`)
  and `item_cli_pvp_unlock_get_name_func` (anchor `ItCliApi.cpp` + same assert), via `to_function_start`.
- `item.cpp` / `item_patterns.cpp` / `item_methods.cpp` — fn-pointer typedefs + globals + `Resolve*`
  wired into `Init()`, nulled on shutdown (same convention as the other item funcs).
- `item_methods.cpp` / `item.h` — `GetPvpUnlockCount()` (= 390) and
  `GetPvpUnlockEncodedName(idx, &name, &desc)` (reads def `+0x20`/`+0x24`, calls the game func).
- `item_bindings.cpp` — Python surface:
  - `PyItem.get_pvp_unlock_count() -> int`
  - `PyItem.get_pvp_unlock_name_enc(idx) -> (List[int] name_enc, List[int] desc_enc)`
- `stubs/PyItem.pyi` — stub decls (Python repo).

Fn signatures used (assumed **`__cdecl`** — verify at runtime; wrong convention would fault the call):
```cpp
using ConstItemPvpGetUnlockDefFn = const uint32_t*(__cdecl*)(uint32_t unlock_index);
using ItemCliPvpUnlockGetNameFn  = void(__cdecl*)(uint32_t unlock_index, uint32_t flag,
                                     uint32_t code_count, const uint32_t* codes,
                                     wchar_t** name_out, wchar_t** description_out);
```

## How to use (after rebuild)

1. Build `Py4GW.dll` (`cmake --build --preset vs2022-win32-relwithdebinfo`).
2. In-client, run the **Dump Named Mod Table** widget
   (`Widgets/Coding/Debug/Py4GW/Dump Named Mod Table.py`) — it loops 0..389, calls the binding,
   decodes the encoded name/desc, and writes `tools/game_mod_table_named.txt` with each mod's
   game-composed name + description alongside its upgrade_id and codes.

## Risks / verify points

- **Calling convention** (`__cdecl` assumed) — if the dump faults or returns garbage, this is the
  first suspect.
- **Game-thread/context** — these are `Cli` funcs needing `PropGet(0x10)` context + the string
  table; call in-game. (If needed, wrap in `PyGameThread.enqueue`.)
- If both are wrong to bind directly, fall back to reproducing `Compose`'s inputs exactly as
  `ItemCliPvpUnlockGetName` sets them (doc 07 emitter chain).
