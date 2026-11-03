# Native dialog host — landing package (proposal)

Status: proposed. Nothing here has been applied to `Py4GW_Reforged_Native`, and none of it
is runtime-verified. It is a reviewable slice so the landing does not have to start from a
blank page.

Evidence for every claim below lives in
`docs/ui/research/native-dialog-host-owner-contract.md` (decompiler-verified against
`Gw.wasm`, 28,893,607 bytes, sha256 `F023FD91…`).

## Contents

| File | What it is |
|---|---|
| `native_dialog_host.h` | The missing "owner": an authored FrameProc that owns a `0xD4` instance, an embedded `CCtlLayout`, and the size pass. |
| `offsets_ui_additions.json` | Four `patterns` + four `resolvers` entries to merge into `offsets/ui.json`. |
| `compile_check.cpp` | Tiny TU used to compile-check the header. |

## What is actually verified

- **`native_dialog_host.h` compiles.** MSVC 14.44 x86, `cl /Zs /std:c++20 /EHsc /W4`,
  exit code 0, no diagnostics. (`__thiscall` in the native typedefs requires the x86
  target, not x64.)
- **The four patterns in the JSON match exactly once** in the installed client
  (`F:\GW\GW1\Gw.exe`, sha256 `8E50EDFB…`, 2026-09-30). Addresses are **true VAs**
  (image base `0x00400000` applied — an earlier revision of this file listed RVAs, which are
  `0x400000` low):

  | Entry | Source of the pattern | Match |
  |---|---|---|
  | `frame_msg_call_base` | legacy `py_ui.h` `ResolveFrameMsgCallBase` | `0x0064C680` |
  | `frame_get_native_size` | legacy `ResolveFrameGetNativeSize` | `0x006327F0` |
  | `set_hover_target` | legacy `ResolveSetHoverTarget` | `0x00636220` |
  | `ctl_text_selectable_proc` | legacy `ResolveCtlTextSelectableProc` | `0x0061D340` |

  These four entries (plus six more harvested the same way) are now landed directly in
  `Py4GW_Reforged_Native/offsets/ui.json` and the runtime copy, so this package's JSON is
  superseded for them; it is kept as the reviewable record.
- **The JSON parses** and uses only ops supported by `src/base/patterns.cpp`
  (`scan`, `dereference`, `add`, `to_function_start`, `function_from_near_call`,
  `find_use_of_string`, `read_u32`, `divide`, `validate_section`).

## What is NOT verified — read before applying

1. **Message ids.** The create/size/notify/destroy arms in the dispatcher are keyed on
   `0x09 / 0x37 / 0x38 / 0x0b` because those are the ids Py4GW already documents. The
   decompilation recovered those arms as switch *case indices*, not ids. Confirm them
   against a live client before trusting the dispatcher.
2. **Allocator.** The engine allocates the instance with its own `MemAlloc(size, 0, file,
   line)` and frees it with a sized `operator delete`. `Natives::mem_alloc` / `mem_free`
   must be set to a matching pair; mixing Py4GW's allocator with the engine's free (or the
   reverse) is a crash.
3. **Runtime behaviour — entirely untested.** Nothing here has been run in a client. The
   `[X]` close path in particular still needs the `FrameClose` / `PopCloser` natives, which
   do not have verified patterns yet (see below).
4. **`Instance::vtable` is left null.** Our instance only has to satisfy *our* dispatcher;
   the engine's own chrome procs chain to base without reading the param slot. If a future
   host attaches engine procs that *do* read it, this becomes a real layout constraint.

## Still to derive (the honest remainder)

These natives have no verified pattern yet, so the dispatcher cannot run end-to-end:

- `CCtlLayout` ctor / `SetFrameId` / `Clear` / `Size` / `SizeQuery` / `Child` / `Row` /
  `Column` / `Gap` / `End`
- `FrameScheduleSize`, `FrameNativeSizeChanged`
- `FrameClose`, `PopCloser`, `UiCtlDlgCloserProc`, `UiCtlDlgMsgProc`, `UiCtlBorderProc`
- `FrameSetLayer`, `FrameSetSubclassFlags`, `FrameMouseEnable`, `FramePlaceChildren`
- per-control seeding: `CtlBtnCheck`, `CtlEditSetMaxCharCount`, the `CtlDropList*` family

Anchors available for deriving them (all confirmed present in the current image):

**Author new entries as byte patterns, not string anchors.** On this image, pattern scanning
is reliable (32/32 of `ui.json`'s patterns match, and five legacy `py_ui.h` patterns match
uniquely), but string-address anchoring is not: the frame-name literal `EmailEdit` — which
the game must pass to `FrameCreate` as a pointer — has **zero** address references anywhere
in the file, and `No valid case for switch variable 'hPlace'` has zero as well. See
§5.1 of the findings doc. A byte pattern can also be verified statically, which an
assertion anchor cannot.

- `"m_nodes.Count() - 1"` → a `CtlLayout.cpp` method; one derivation already reached
  `0x002572F0` with a unique 24-byte pattern (recorded in the findings doc).
- `No valid case for switch variable 'hPlace'` → `CCtlLayout::Child` / `::Row` / `::Column`.
  Its reference is **via a pointer table**, so the resolver needs a `dereference` step, not
  a bare `scan`: scanning for a direct code reference returns nothing and looks like a
  false negative.
- File-path anchors per family: `Engine\Controls\CtlLayout.cpp`, `Engine\Frame\FrApi.cpp`,
  `Gw\Ui\Controls\UiCtlDlg.cpp`, `Gw\Ui\Account\ActCrEmail.cpp`.

Tooling for the derivation is in the ignored scratch tree:
`_ghidra/scripts/find_anchor.ps1` (occurrence-scan, fixes the substring/duplicate traps),
`_ghidra/scripts/resolver_health.ps1` (re-checks every entry against a chosen image).

## How to apply, if you want it

1. Merge the two objects from `offsets_ui_additions.json` into `offsets/ui.json`
   (`patterns` and `resolvers` sections).
2. Drop `native_dialog_host.h` into the UI module, resolve the natives named in
   `DialogHost::Natives`, and call `SetContentCallbacks(...)` for each window you host.
3. Build (`cmake --build build --config RelWithDebInfo`) and run in a client. I could not
   do either: the game is not running, and this package was authored outside the native
   repository.
