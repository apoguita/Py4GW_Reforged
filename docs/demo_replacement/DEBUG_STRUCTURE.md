# Debug Structure & Workflow (DEMO 2.0 migration bug-fixing)

Reference map so I don't get confused while fixing migration bugs surfaced by DEMO 2.0.

## Projects

| Role | Path | Notes |
|---|---|---|
| **Current Python (Reforged)** | `C:\Users\Apo\Py4GW_Reforged` | The project we are building/fixing. Bugs here = migration errors. |
| **Current C++ (Reforged Native)** | `C:\Users\Apo\Py4GW_Reforged_Native` | The new DLL exposing `Py*` bindings. Some bugs are here (native). |
| **LEGACY Python (good access) #1** | `C:\Users\Apo\Py4GW_python_files` | Has `Py4GWCoreLib/` — the reference for correct data handling. |
| **LEGACY project (good access) #2** | `C:\Users\Apo\Py4GW` | Legacy full project (GWCA-era). Reference for correct access. |

**Crash logs:** `F:\GW\GW1\crashes\` — always the **latest** timestamped folder. Each has
`*-pytrace.txt` (Python stack), `*.json` (fault code/context), `*-stack.txt`, `*-gwtext.txt`.

### ⚠️ Offsets: TWO copies — fix the RUNTIME one
Pattern/offset JSONs are loaded at **startup from disk**, from `GetModuleDirectory()/offsets`
(`src/base/patterns.cpp:661`) — i.e. **next to `Py4GW.dll`**, which is
`C:\Users\Apo\Py4GW_Reforged\offsets\` (the Python project). The Native source copy
`C:\Users\Apo\Py4GW_Reforged_Native\offsets\` is source-of-truth but only reaches runtime via a
build copy step, which can be **stale**. So:
- An offset fix must be applied to **`Py4GW_Reforged\offsets\*.json`** (runtime) to take effect.
- Keep the Native source copy in sync too.
- **No DLL rebuild needed** for an offsets-only change — just **restart the client** (JSON is
  re-read at startup). Rebuild is only for C++ changes.

## Core principle (from user)

**Legacy and Reforged run against the exact same `Gw.exe` — every address and offset MUST be
identical.** The *only* thing the migration changed is that offsets are now expressed in JSON
step-lists instead of C++ scanner calls. The JSON must reproduce the legacy resolution
**step-for-step**; it is a re-expression, never a re-derivation. Therefore: **any difference
between the legacy resolution logic and the JSON steps IS the bug.** Fix = make the JSON match
legacy exactly (same assertion/pattern, same +offsets, same deref/to-function-start ops, same
byte math). Do not invent or "improve" offsets.

## Workflow per failing feature

1. Read the latest crash folder's `-pytrace.txt` + `.json`.
2. Trace the Reforged call chain (wrapper → wrapper → `Py*` binding).
3. Compare each hop against the **legacy** implementation (both legacy projects) — legacy has
   correct access, so a divergence marks the migration error.
4. Fix on the correct side (Python wrapper in Reforged, or native C++ in Reforged_Native).
5. **Never auto-invoke bindings on render** (see 11_build_plan §6b) — a native fault crashes the
   client uncatchably. Demo probes are opt-in (Run buttons).

## Log of failing features

| Feature | Crash | Root cause | Fix | Status |
|---|---|---|---|---|
| `Player.GetInstanceUptime` | `0xc0000005` reading `0x6a5756cc` at `GW::ui::GetFrameLimit +0xC` (`ui_methods.cpp:1706`, the `g_command_line_number_buffer[FPS]` read) | **Native pattern drift.** Python wrappers are byte-identical to legacy. `offsets/ui.json → command_line_number_buffer` scanned the `command_line_number` assertion anchor and did `+0x29` on the **raw assertion address**, missing a `to_function_start` step. GWCA does `ToFunctionStart(FindAssertion(...)) + 0x29`. So the deref hit the wrong location → garbage pointer → crash. (Sibling `get_command_line_number_func` applies `to_function_start`; the buffer pattern forgot it. `+0xC0` bytes == GWCA `+= 0x30` uint32 elems — that part was fine.) | Inserted `to_function_start` step before `+0x29`. Applied to **BOTH** `Py4GW_Reforged_Native/offsets/ui.json` (source) **and** `Py4GW_Reforged/offsets/ui.json` (runtime, next to the DLL — the one actually read). First attempt only fixed the source copy → identical crash; runtime copy was stale (Jun 29). **No rebuild needed — restart client.** | FIX APPLIED to runtime (awaiting client restart) |

| `Party.IsAllTicked` (+ all `.tick.*`) | `AttributeError: 'bool' has no attribute 'IsTicked'` | Native `PyParty::tick` was declared `bool` (legacy `py_party.h:200` = `PartyTick tick = false;` — an object). Wrapper is identical to legacy and calls `.tick.IsTicked()`. | `party_bindings.cpp`: `bool tick` → `PartyTick tick`; made `PartyTick(bool)` ctor non-explicit (legacy parity, allows `tick = false`). **Needs C++ rebuild.** | FIX APPLIED (rebuild) |
| Camera: `GetDistanceToGo`, `GetMaxDistance2`, `GetPitchToGo`, `GetYawToGo`, `GetTimeInThe{Map,District}`, `GetTimeSinceLast{KeyboardRotation,MouseRotation,MouseMove,AgentSelection}` | `AttributeError: PyCamera.PyCamera has no attribute <field>` | Native `PyCamera` struct HAS these 10 fields and `GetContext()` populates them, but the 10 `def_readwrite` bindings were **omitted** (Reforged jumped `acceleration_constant`→`field_of_view`; legacy binds all 10 in between). | `camera_bindings.cpp`: added the 10 `def_readwrite` lines between `acceleration_constant` and `field_of_view`, matching legacy order. **Needs C++ rebuild.** | FIX APPLIED (rebuild) |
| Merchant: **all** transactions (`trader/merchant buy/sell`, `request_quote/sell_quote`, `crafter/collector`) silently no-op (works in true GWCA legacy) | No crash — malformed transaction, server rejects → nothing happens; offered-item getters still work (separate `listeners::Merchant` path) | **give/recv slots swapped vs legacy `py_merchant.h`.** BUY = give gold + RECEIVE item (item id → `recv`); SELL = GIVE item + receive gold (item id → `give`). `merchant_bindings.cpp` had it reversed (buy put item in `give`, sell in `recv`); quotes reversed the same way; Crafter/Collector left `recv` **empty** (dropped the crafted/exchanged `item_id` that legacy puts in `recv.item_ids`). Everything else (patterns/offsets/`TransactionType` enum 0x1..0xD/`TransactionInfo`+`QuoteInfo` layout/packet struct/UIMessage `0x30000000\|0x6,0x7`/init wiring/callback store) is byte-identical to legacy. | `merchant_bindings.cpp`: rebuilt the 8 transaction methods to EXACT legacy py_merchant.h shape (live `&item->item_id`, `count`+`cost*count`, explicit field assignment, crafter/collector use incoming `.data()` + `&item_id`, no added guards/copies). **Needed C++ rebuild.** | ✅ CONFIRMED WORKING (user tested 2026-07-12 after rebuild) |

### Fix-location cheat sheet
- **Offset/address wrong** → edit `Py4GW_Reforged/offsets/<mod>.json` (runtime) + Native source copy; **restart only**.
- **Binding missing / wrong type / struct field** → edit `Py4GW_Reforged_Native/src/GW/<mod>/*_bindings.cpp`; **needs rebuild**.
- **Python wrapper** → rarely the cause (usually byte-identical to legacy); check first but expect native.

### Method notes
- Wrapper chain: `Player.GetInstanceUptime` → `Agent.GetInstanceUptime(agent_id)` → `UIManager.GetFPSLimit()` → `PyUIManager.UIManager.get_frame_limit()` → native `GW::ui::GetFrameLimit()`.
- Native `GetFrameLimit` reads `g_command_line_number_buffer[FPS]` (resolved from `offsets/ui.json`) and calls `g_get_graphics_renderer_value_func(nullptr, 0xF/0x16)` (both null-checked, so a null func ptr is safe — the fault was the buffer pointer).
- No other Native code calls `GetFrameLimit` — the only caller is the Python binding, which is why nothing else surfaced this.
