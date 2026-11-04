# Native Dialog Host — Owner Contract

Status: current
Scope: instanced content-dialog hosting, the `CCtlLayout` size pass, and the native close path
Authority: decompilation of the `Gw.wasm` program in the analyzed Ghidra project
(`third time`, `/Gw.wasm`)

This record answers the three questions left open by
`native-dialog-layout-process.md` and `native-ui-controls-handover.md`: **who owns the
control-hosting instance, how the layout pass is actually pumped, and how the native
`[X]` tears a window down.** Every call count and constant below comes from the
decompiler output named in `## Reproduce`; nothing here is in-client verified yet.

Evidence levels used below: **verified** = read from decompiler output; **inferred** =
consistent with the decompiled shape but not proven; **unresolved** = not established.

## 1. The owner contract — `TCtlInstance<T>::MsgProc`

The dispatcher that hosts a dialog's controls is `TCtlInstance<T>::MsgProc`. Two
independent dialogs were decompiled and show the same contract:

- `TCtlInstance<IUi::NDlgOptionGroupGeneral::CDlgOptGeneral>::MsgProc` @ `ram:80fd90ff`
- `TCtlInstance<IUi::DlgOptionGroupSnd::CDlgOptionSound>::MsgProc` @ `ram:81003794`

**Where the instance lives (verified).** `TCtlInstance<T>::Ptr(FrameMsgHdr const&)` is
the accessor, and its decompilation is unambiguous:

```c
piVar4 = *(int **)(param1 + 8);   // hdr.param — the FrameCreate `userdata` argument
if (piVar4 == 0) ErrorAssertion("hdr.param == NULL || *hdr.param != NULL");
piVar4 = (int *)*piVar4;          // *hdr.param — the instance pointer
if (piVar4 == 0) ErrorAssertion("!*hdr.param");
return piVar4;
```

So the slot is **`FrameMsgHdr + 0x08`** (`hdr.param`, the 5th `FrameCreate` argument), and
the instance is reached by one dereference: `instance = *(hdr.param)`. Both assertion
strings are in the template header `Engine\Controls\CtlInstance.h` (the Sound build
records the same header under a longer mixed path). The frame userdata is therefore
**a pointer to a slot**, not the instance itself.

**What `MsgProc` does per message (verified call sets).**

| Phase | Calls made |
|---|---|
| create | `MemAlloc` ×1, `CCtlLayout::CCtlLayout()` ×1, `CCtlLayout::SetFrameId(uint)` ×1, `T::OnFrameCreate` ×1 |
| after create | `CCtlLayout::Clear()` (General ×2, Sound ×0), `FrameScheduleSize(uint)` ×2, `FrameNativeSizeChanged(uint)` ×2 |
| size | `CCtlLayout::Size(Rect4f*)` ×1, `CCtlLayout::SizeQuery(Coord2f const&)` ×1 |
| notify | `T::OnFrameNotify` ×1 |
| destroy | `T::~T()` ×1, `operator delete` ×1, `Ui::CLayout::~CLayout()` ×1 |
| always | `FrameMsgCallBase` ×2, `TCtlInstance<T>::Ptr` ×1, `ErrorAssertion` ×88 |

Read together with `Ptr`, the create path is: the engine calls the proc with `hdr.param`
pointing at a null slot; `MsgProc` `MemAlloc`s the instance, stores it through that slot,
constructs the embedded layout, pins it to the frame, runs the class's `OnFrameCreate`
(which `FrameCreate`s every control), then `Clear()`s and requests the size pass.
Teardown is `~T` + `operator delete`.

**The create case decoded (verified).** The msg-9 arm of
`TCtlInstance<CDlgOptGeneral>::MsgProc` decompiles to:

```c
piVar6 = MemAlloc(0xd4, 0, "…/Engine/Controls/CtlInstance.h", 0xaf);  // instance = 0xD4 bytes
piVar6[1] = 0;
*piVar6   = (int)&DAT_ram_00179b38;        // +0x00 vtable, construction form
param1_03 = CCtlLayout__CCtlLayout__(piVar6 + 2);   // +0x08 = embedded CCtlLayout
*piVar6   = (int)&DAT_ram_00179b2c;        // +0x00 vtable, final form
… zero/0x80-fill the member block …
*(int **)param1[2] = piVar6;               // *hdr.param = instance
assert(*hdr.param == piVar6);              // CtlInstance.h line 0xb1
piVar6[1]      = *param1;                  // +0x04 = frameId
CCtlLayout::SetFrameId(param1_03, *hdr.param);
```

This settles the instance layout the July records could only guess at:

| Instance offset | Contents |
|---|---|
| `+0x00` | vtable — set twice: `DAT_ram_00179b38` during construction, then `DAT_ram_00179b2c` |
| `+0x04` | frame id (also written by `CCtlLayout::SetFrameId`) |
| `+0x08` | **embedded `CCtlLayout`** — the July "instance+8" claim is correct |
| `+0x20` … `+0xC0` | 11 × 16-byte members (stride `0x10`), each holding a pointer that `~T` frees — consistent with the per-language decoded-name buffers used by `OnFrameTextResolved` |
| size | **`0xD4` (212) bytes**, confirmed by both `MemAlloc(0xd4, …)` and `operator delete(ptr, 0xd4)` |

The instance is reached by exactly one dereference of `hdr.param`, and `MsgProc` asserts its
own store with `*hdr.param == instance` before use.

**Control creation happens inside `T::OnFrameCreate`, as direct children (verified).**
`CDlgOptGeneral::OnFrameCreate` calls `FrameCreate` **42×** and `CtlBtnCheck` **25×**;
`CDlgOptionSound::OnFrameCreate` calls `FrameCreate` **23×**. The checkbox state is
seeded with `CtlBtnCheck`, matching the July recipe. The `Check*`/`*Slider`/`*DropList`
strings on the General create path (`CheckShowKoreanRatings`, `CheckMouseDisableWalk`,
`CameraFovSlider`, `FilterDropList`, `LanguagesDropList`, `PregameSceneDropList`, …) are
the real child names, with layout style `0x10000` present in the create path.

### 1.1 Message ids and payload geometry (verified)

An earlier reading of this session assumed the dispatcher's arms were reconstructed as
switch *case indices* rather than ids. That was wrong, and the correction matters: the
dispatcher loads `msg_id = msg[1]` and compares it against **real** message ids. Mapping
each arm to the call it guards gives:

| Id | Arm body | Meaning |
|---|---|---|
| `0x09` | `MemAlloc(0xd4, …)` then `OnFrameCreate` | **create** |
| `0x0b` | `~content_class()` then `operator delete(ptr, 0xd4)` | **destroy** |
| `0x37` | `CCtlLayout::Size(Rect4f*)` | **size** |
| `0x38` | `CCtlLayout::SizeQuery(Coord2f const&)`, `OnFrameTextResolved` | **size query** |
| `0x31` | `OnFrameNotify` | notify |
| `0x20` | re-populate content, then `FrameScheduleSize` + `FrameNativeSizeChanged` | refresh / rebuild |
| `0x50` | `FrameMsgCallBase` | chain to base |

So the four constants Py4GW already used (`0x09`, `0x0b`, `0x37`, `0x38`) are confirmed, and
two more arms are now known (`0x31` notify, `0x20` refresh).

**Payload geometry for the size arms** — read off the same arms, and easy to get wrong:

- `0x37`: the incoming `Rect4f` is **inline at `wparam + 8`** (read as two 8-byte chunks).
- `0x38`: `wparam + 8` holds a **pointer** to the output `Coord2f`; the arm writes the
  result through it.

Passing `wparam` itself to the layout is off by eight bytes. The host applies the `+8`
offsets; they come from a pos-stack-noisy decompile, so they are the most likely remaining
detail to need one runtime nudge.

## 2. The layout machinery

### 2.1 `CCtlLayout` object layout (verified)

From `CCtlLayout::CCtlLayout()` @ `ram:80dfa34c`, `SetFrameId`, and `Clear()`:

| Offset | Field |
|---|---|
| `+0x00` | vtable `DAT_ram_00167118` |
| `+0x04` | frame id (written by `SetFrameId(uint)`) |
| `+0x08` | pointer to node array (`m_nodes`, `TArray<Ui::CLayout::SizeNode*>`) |
| `+0x10` | node count |
| `+0x14` | capacity granularity, initialised to `0x40` |

`Clear()` frees each non-null node via `CBaseSpareList::Free` on spare list
`DAT_ram_005a8580` with **node size `0x2C`**, then zeroes the count. So a layout node is
**0x2C bytes**, allocated from a spare list — the July records never had this number.

### 2.2 `CCtlLayout` is a translation facade over `Ui::CLayout` (verified)

| `CCtlLayout` verb | Forwards to |
|---|---|
| `Size(Rect4f*)` | `Ui::CLayout::Size(Rect4f*)` |
| `SizeQuery(Coord2f const&)` | `Ui::CLayout::SizeQuery(Coord2f const&)` |
| `Child(uint, ELayoutH, ELayoutV, int)` | `Ui::CLayout::Child(uint, uint, Coord2f const&, Ui::CLayout::EDimsType)` |
| `Column(ELayoutH, ELayoutV, int)` | `Ui::CLayout::Column(uint, Coord2f const&, EDimsType)` |
| `Row(ELayoutH, ELayoutV, int)` | `Ui::CLayout::Row(uint, Coord2f const&, EDimsType)` |
| `Gap(float, ELayoutH, ELayoutV)` | `Ui::CLayout::Gap(float, uint)` |
| `End()` | appends into `m_nodes` (`TArray<SizeNode*>::AdjustSizeChunked`) |

`Child`/`Column`/`Row` translate the `ELayoutH`/`ELayoutV` pair through tables
`DAT_ram_0016711c` / `DAT_ram_0016712c` and have a switch assertion
`No valid case for switch variable 'hPlace'` — so an out-of-range `ELayoutH` aborts in
`Engine/Controls/CtlLayout.cpp`. The July note about those two tables is **correct**.

**The tables read (verified).** Reading memory at those addresses gives four dwords each,
which is what the "no valid case" switch implies (four legal placements per axis):

| Table | Entry 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `DAT_ram_0016711c` (H) | `0x4` | `0x2` | `0x8` | `0x20` |
| `DAT_ram_0016712c` (V) | `0x10` | `0x2` | `0x1` | `0x40` |

The two arrays sit adjacent (V is H + `0x10`). `DAT_ram_00167118`, which the ctor stores into
`+0x00`, begins with `0xA9B` followed by the same flag sequence — treat it as layout metadata,
not as a conventional function-pointer vtable.

**The stretch bits are applied in code, and are now verified.** An earlier revision of this
record noted that the July "+0x80 H-stretch / +0x100 V-stretch" rule was *not* present in
either table and left it unverified. It is confirmed: the alignment translator
(`FUN_006072B0`, `0x006072B0` on the current client) switches on the H value (four cases),
switches on the V value (four cases), and then, only when `expand != 0`, ORs `0x80` when
H is not the "keep" case and `0x100` when V is not. So four legal values per axis is
confirmed, and the stretch bits come from code rather than from the tables — exactly the
possibility previously flagged.

### 2.3 The real layout trees (verified call counts)

`CDlgOptGeneral::OnCtlLayout` @ `ram:80fd3338`: `Column` ×3, `End` ×3, `Row` ×1,
`LayoutSliders` ×2, `LayoutCheckboxes` ×2, constants `0x3ef33333` (≈0.475),
`0x3f000000` (0.5), `0x40400000` (3.0), `0x41a00000` (20.0).

`CDlgOptGeneral::LayoutSliders(layout, 3.0f)`: `FrameGetChild` ×8,
`FrameGetNativeSize` ×8, `Row` ×8, `Child` ×17, `Gap` ×1, `End` ×8 — i.e. one
`Row`/`End` pair per slider, each row holding a label `Child` plus a slider `Child`
sized from its own native size, then `End`.

`CDlgOptGeneral::LayoutCheckboxes(layout, 3.0f)`: `Child` ×25 and `Gap` ×25 — one
`Gap` and one `Child` per checkbox, matching a flat vertical stack with 3 px gaps.

`CDlgOptionSound::OnCtlLayout` @ `ram:810026b2` reproduces the same shape (3× `Column`,
3× `End`, 1× `Row`, 2× each helper), so this is the archetype, not a General quirk.

### 2.4 The size pump is a rect operation, not a message (verified)

- `FrameScheduleSize(uint)` @ `ram:809a92ea` = `IFrame::CRect::ScheduleSize(frame + 0xD0, 1)`
- `FrameNativeSizeChanged(uint)` @ `ram:809a918e` = `IFrame::CRect::NotifyNativeSizeChanged(frame + 0xD0)`
- both resolve the frame with `IFrame::CMsg::GetFrame(id)` and assert
  `frameId && prop->frameId` in `Engine/Frame/FrApi.cpp`

So the rect lives at **`frame + 0xD0`**, and the pump flags that rect for re-layout; the
engine then delivers the size messages that reach `CCtlLayout::Size`/`SizeQuery`. The
July wording ("`FrameScheduleSize` is the pump that converts the built tree into applied
rects") is directionally right but describes a rect-scheduling call, not a dispatch.

### 2.5 The `CtlLayout` cluster on the current client (verified)

`CCtlLayout`'s translation unit was located on the analyzed image by following the `m_nodes`
literal and by its class-name string, and the `__thiscall` convention is confirmed there (the
decompiler renders the receiver as `in_ECX`, matching the host's typedefs).

| Address (VA) | Identification | Evidence |
|---|---|---|
| `0x00606FA0` | **`CCtlLayout::Clear()`** | body is node-for-node identical to the WASM twin: iterate `[this+8]` for `[this+0x10]` entries, free each non-null at size **`0x2C`** via the spare list, then zero `[this+0x10]` |
| `0x006072B0` | alignment translator | two 4-case switches (H then V) plus the `\|0x80` / `\|0x100` stretch bits under `expand != 0` |
| `0x00607130` | `FixGapMarginFlags` (probable) | masks the incoming flag word with `0xFFFFFFD1` / `0xFFFFFFAC` around the `0x100` test |
| `0x006070F0` | `End()` candidate | zero stack params, asserts the node count is non-zero before touching the array |
| `0x00606E60`, `0x00607040`, `0x006073F0` | tree builders | each allocates a `0x2C` node with a distinct kind tag at `+0x28` (1, 2, 3) |

**A working string anchor for this family (verified).** The node allocator passes the class
name literal `?AVSizeNode@CLayout@Ui…` at `0x00C08194`, and — unlike the file-path literals
in §5.1 — this one **is** referenced, from `FUN_00606E60`. So `SizeNode`-allocating code can
be anchored on that string when a byte pattern is inconvenient.

Patterns for the three best-identified functions are landed in `offsets/ui.json` as
`ctl_layout_clear`, `ctl_layout_align_translator` and `ctl_layout_fix_gap_margin_flags`
(each matching exactly once), and `CCtlLayout::Clear` is wired into the host's resolver.

**Round 12 — the facade is identified, and the host design is now confirmed on x86.**

The two `MsgProc` implementations were isolated by intersecting three sets: 167 functions call
the layout ctor, 47 reference the `hdr.param` assertion, and only **6** call `Clear`. Two
functions sit in all three — `FUN_004D7490` and `FUN_00505FA0` — and decompiling them yielded
the whole facade through their shared callees:

| Function | Identity | Evidence |
|---|---|---|
| `0x006075A0` | **`CCtlLayout::SetFrameId`** | 13-byte body: `mov [ecx+4], eax; ret 4` — matches the WASM and §2.1 exactly |
| `0x006075E0` | **`CCtlLayout::Size(Rect4f*)`** | asserts `frameId != 0`, converts the rect to (w,h), calls `SizeInternal` with flags `0x100` |
| `0x00607E80` | **`CCtlLayout::SizeQuery`** | zeroes the output on an empty tree, clamps constraints to `100000`, writes a `Coord2f` through its out pointer |
| `0x00607710` | `SizeInternal` | recursive |
| `0x00607F90` | `SizeQueryInternal` | calls the verified `FrameGetNativeSize` |

All five are landed (`ctl_layout_set_frame_id`, `ctl_layout_size`, `ctl_layout_size_query`,
`ctl_layout_size_internal`, `ctl_layout_size_query_internal`) and the first three are wired
into the host. **Five of the seven host prerequisites are now real**: ctor, `SetFrameId`,
`Clear`, `Size`, `SizeQuery`. Only the size pump (`FrameScheduleSize` /
`FrameNativeSizeChanged`) remains, so `Ready()` is still false and the dispatcher stays a
pass-through.

**The x86 dispatcher confirms four deductions the host was built on.** Its arms read:

```c
case 0x37:  // size
  local_10 = param_2[3]; local_c = param_2[4]; local_8 = param_2[5];
  FUN_006075e0(&local_14);                       // CCtlLayout::Size(&rect)

case 0x38:  // size query
  thunk_FUN_0064c680(param_1, param_2, param_3); // chain to base FIRST
  FUN_00607e80(&local_c, param_2);               // SizeQuery(&out, wparam)
  if (local_c != 0.0) { *(float *)param_2[2] = local_c; ... }
```

1. The size rect really is **inline at `wparam + 8`** (`param_2[2..5]`), matching
   `kSizeParmOffset`.
2. The query's output pointer really is **`*(wparam + 8)`** (`param_2[2]`), written through
   as 8 bytes — the round-7 deduction holds.
3. The `constraints` argument is **the message pointer itself** (`param_2`), which is why the
   host now passes `wparam` there; the earlier single-argument typedef was wrong and is fixed.
4. The create path stores the instance with **`*(instance_slot) = puVar2`** where
   `param_1[2]` is the slot, and sets `instance+4` from `*param_1` — exactly the host's
   `*slot = instance` and `instance->frame_id = msg[0]`.

It also corroborates the instance allocation line-for-line: the engine calls
`FUN_0047f490("P:\\Code\\Engine\\Controls\\CtlInstance.h", 0xaf)` — the **same file and the
same line `0xaf`** the WASM showed for `MemAlloc(0xd4, …)`. And the two-stage vtable is
visible in x86: the layout ctor runs, then the content class overwrites `+0x00` with its own
vtable (`PTR_FUN_0094d1a0` / `PTR_FUN_00951050`).

**One July puzzle now has a mechanism.** Their notes record the anchor-6 setter
(`0x0062F770`) asserting with code `0x238` on a slider. `0x238` is `CCtlLayout::Size`'s own
inverted-rect validation — `if (rect.x1 < rect.x0 || rect.y1 < rect.y0) assert(0x238)` — so
that crash was the layout refusing an inverted rect, not a slider-specific defect.

**Still to find:** `FrameScheduleSize` and `FrameNativeSizeChanged`.

**Round 13 — the rect payload confirmed explicitly, plus what does *not* work.**

The second dispatcher's size arm spells the payload out, which settles the host's offset
beyond argument:

```c
case 0x37:
  local_14 = param_2[2]; local_10 = param_2[3];
  local_c  = (float)param_2[4]; local_8 = (float)param_2[5];
  FUN_006075e0(&local_14);                       // CCtlLayout::Size(&rect)
```

Four consecutive floats at `wparam + 8` — exactly `kSizeParmOffset`, with the inline (not
indirect) interpretation. Also identified from the same arms: **`FUN_004A0AF0` is
`TCtlInstance<T>::Ptr`** — every arm calls it with the message pointer and gets the instance
back, which is the accessor the host reimplements inline. The destroy arm reads:

```c
case 0xb:
  iVar4 = Ptr(param_1);
  if (iVar4 != 0) { layout_dtor(); free(iVar4, 0x5c); }    // per-class instance size
```

Note the instance size there is `0x5C`, not the General dialog's `0xD4` — instance size is
per content class, so the host's `kInstanceSize` is right for a General-style host and wrong
in general.

**Three dead ends, recorded so they are not re-tried:**

1. **Assertion line immediates.** The WASM showed the pump asserting with `0x833` / `0x828`,
   and `Scanner::FindAssertion` implies a `mov ecx, imm32` (line) shape — but scanning for
   `B9 33 08 00 00` and `B9 28 08 00 00` finds nothing. Those values were pos-stack artifacts
   in the WASM rendering, not line numbers.
2. **`[reg+0xD0]` accesses** (the frame `CRect` offset): 102 distinct functions touch it, so
   the signature does not discriminate.
3. **The FrApi-TU small functions.** `FUN_00631290` / `FUN_006312D0` looked like the pump
   (frame id + assert + one extra call) but the helper they call, `FUN_0063BC70`, is a
   `CState::Set(which, value)` switch over cases 0–4 — they are state setters.

Also note neither identified dispatcher calls the pump: in both, `case 0x20` falls through to
the generic base-chain group. So these two are *not* the General-options dispatcher, whose
0x20 arm does the refresh plus size pump.

**Round 14 — the size pump found, and all seven prerequisites are now real.**

The route that worked: every one of the six functions that call `CCtlLayout::Clear` follows
the *same* sequence afterwards —

```c
FUN_00606fa0();                    // CCtlLayout::Clear
(**(code **)*puVar4)(puVar4 + 2);  // virtual call with instance+8 (the layout) — rebuild tree
FUN_006349c0(puVar4[1]);           // called with instance+4 == the frame id
FUN_00634660(puVar4[1]);           // same
```

Two functions invoked with the frame id, in sequence, immediately after the layout tree is
rebuilt. Decompiling them settles it:

```c
FUN_006349C0(frameId):  if (!frameId) assert(0x833);  GetFrame(frameId);  CRect::ScheduleSize(1);
FUN_00634660(frameId):  if (!frameId) assert(0x828);  GetFrame(frameId);  CRect::NotifyNativeSizeChanged();
```

Those assertion line numbers — **`0x833` and `0x828`** — are exactly the values the WASM
decompilation showed for `FrameScheduleSize` and `FrameNativeSizeChanged`. So:

| Function | Identity |
|---|---|
| `0x006349C0` | **`FrameScheduleSize(uint)`** |
| `0x00634660` | **`FrameNativeSizeChanged(uint)`** |
| `0x0064D2C0` | `IFrame::CMsg::GetFrame(uint)`, called by both (and by the whole FrApi family) |

Both are landed (`frame_schedule_size`, `frame_native_size_changed`) and wired into the host.

**All seven host prerequisites are now identified, landed and wired**: the layout ctor,
`SetFrameId`, `Clear`, `Size`, `SizeQuery`, `FrameScheduleSize`, `FrameNativeSizeChanged` —
plus `FrameMsgCallBase`, which was already there. Every one of the eight resolvers the host
requests exists in both offsets copies and resolves **uniquely** against the installed
client, so `Ready()` becomes true and the dispatcher takes ownership on create.

**A correction to the resolver system falls out of this (actionable).** The extracted pump
bytes show this build's assertion shape:

```text
push <LINE> ; mov edx, <FILE pointer> ; mov ecx, <MESSAGE pointer>
```

but `FileScanner::FindAssertion` builds `push <message>; mov edx, <file>; mov ecx, <line>`
(`"\x68????\xBA????\xB9????"`, with the message address written into the third operand). The
line and message operands are therefore swapped relative to the real encoding. That would
make assertion-anchored resolvers match only by luck, and it also explains round 13's dead
end #1: scanning for `mov ecx, 0x833` found nothing because the line is **pushed**, and `0x833`
appears as `68 33 08 00 00`. Anyone repairing assertion anchors should start here.

**Still not verified:** anything at runtime. The message ids, the payload offsets, the
allocator pairing and the whole owning path have only ever been read from a disassembly, never
executed. `Ready()` flipping true is a prediction from pattern resolution, not an observation.

## 3. Chrome, content page, and the close path

**Real names (verified).** The July records use two analyst-coined names that do not exist
in the client. The real symbols are:

| July name | Real symbol | Address |
|---|---|---|
| `IUi::UiCtlDlgBaseProc` | `IUi::UiCtlDlgMsgProc` | `ram:80e586ff` |
| `IUi::UiCtlContentPageProc` | **no such function — see below** | — |
| `IUi::PopCloser` | `IUi::PopCloser` | `ram:80e5cf57` |

`UiCtlDlgMsgProc` is a pass-through: `FrameGamepadEnable`, `FrameGamepadEnterCursorMode`
and `FrameMsgCallBase` ×3, i.e. it chains most messages to the base proc.

**The `[X]` closer proc (verified).** `IUi::UiCtlDlgCloserProc` @ `ram:80e5e206` calls
`FrameClose(uint)` ×1, `FrameContentAddImage` ×1, `GrBuildSolidMaterial` ×1,
`FrameGetPosition` ×1 and `HandleClose(HObject_tag*)` ×1, with source
`Gw/Ui/Controls/UiCtlDlg.cpp`. It paints its own glyph and routes the close through
**`FrameClose`** — an entry point distinct from `FrameDestroy` that the July records never
identified.

**`PopCloser` (verified).** `IUi::PopCloser(uint)` @ `ram:80e5cf57` calls
`FrameGetChild` ×17, `FrameDestroy` ×9, `FrameGetParent` ×1 and `FrameMouseEnable` ×1 —
consistent with scanning the page band, destroying the topmost page(s), and re-arming
mouse on the revealed page. The July model of `PopCloser` is **confirmed**; its
"re-arm prevents the dangling hot-item" explanation remains **inferred**.

**The July content-page proc does not exist (verified).** The records derived
`ResolveUiCtlContentPageProc` as EXE `0x00876740` = `IUi::UiCtlDlgProc` − `0x140`, with
WASM twin `ram:80e588cd`. That address is **not a function entry** in `Gw.wasm`: it falls
inside `UiCtlDlgMsgProc` (`ram:80e586ff` … `ram:80e58a0d`). Installing it as a proc jumps
mid-function — the same defect class as the `0x00851180`-is-not-a-proc finding, and a
sufficient explanation for the recorded "`CreateContentPageByFrameId` crashes
standalone". The `CtlView` host path is the real alternative:
`CtlView::CView::OnFrameCreate` @ `ram:80e49fbb` calls `FrameCreate` ×2,
`FrameDestroyChildren`, `FrameGetChild`, `FrameMouseEnable`, `FrameSetView` and
`FrameTestStyles` ×4, with the `CTL_VIEW_STYLE_*` assertions in `Engine/Controls/CtlView.cpp`.

### 3.1 The edit Border sibling (verified)

The July handover prescribed a sibling border frame for edit boxes but never showed where it
came from. It comes from the email form — `IUi::Account::CEmail::OnFrameCreate` @
`ram:80faf332`, the same function the July records cite. Its decompiled call set contains
exactly one of each of the four calls the recipe needs, alongside the border's own name
string and the password style flag:

| Call | Count | Role in the recipe |
|---|---|---|
| `FrameCreate(parent, style, childId, proc, userdata, name)` | 20× | the form's controls, `"Border"` among the names |
| `FrameSetLayer(uint, int)` | 1× | puts the border behind the edit |
| `FrameSetSubclassFlags(uint, proc, uint, uint)` | 1× | the `0x10` inset-box flag |
| `FrameMouseEnable(uint, uint, uint)` | 1× | click-through so the edit keeps focus |
| `CtlEditSetMaxCharCount(uint, uint)` | 2× | per-edit length cap |
| `FramePlaceChildren(uint, wchar_t const*)` | 1× | arranges the form's children |
| `FrameNewSubclass(uint, proc, uint)` | 2× | subclassing |

Strings on the path are `ActCrEmail`, **`Border`**, `EmailEdit`, `EmailVerifyEdit`,
`PasswordEdit`, `PasswordVerifyEdit` (plus the `Error*`/`*Text` rows), and the constant
`0x1000000` — the password style the July note names — is present in the same function.
So the four-step border recipe in `native-dialog-layout-process.md` is **corroborated by the
game's own edit form**, including the `0x10` subclass flag and the layer/mouse inversion.
The border proc itself, `IUi::UiCtlBorderProc` @ `ram:80e02ef0`, paints the 9-slice box with
`FrameContentAddImageTemplate` ×3 plus `GrModelSetColor`, and chains to base.

## 4. Corrections ledger (July records → verified state)

| July claim | Verified state |
|---|---|
| instance lives in "frame userdata `frame[2]`" | instance is at **`*(FrameMsgHdr+0x08)`** — the `FrameCreate` `userdata` argument is a pointer to a slot holding the instance; `MsgProc` writes it and self-checks with `*hdr.param == instance` |
| instance embeds a `CCtlLayout` | **confirmed**: the ctor calls `CCtlLayout::CCtlLayout(instance + 8)`. Instance is `0xD4` bytes with vtable at `+0x00` and frameId at `+0x04`. Whether `CCtlLayout` itself derives from `Ui::CLayout` is still **unresolved** |
| `CCtlLayout` node array at `+8`/`+0x10` | correct; add node size **0x2C**, capacity `0x40` at `+0x14`, vtable `DAT_ram_00167118` |
| align flag tables `DAT_0016711c` / `0016712c` | correct; contents now read (4 entries each). The separate "+0x80 / +0x100 stretch when `expand != 0`" note is **not** in those tables and stays **unverified** |
| `FrameScheduleSize` pumps the size pass | correct, and it is `IFrame::CRect::ScheduleSize(frame+0xD0, 1)`; `FrameNativeSizeChanged` is `CRect::NotifyNativeSizeChanged(frame+0xD0)` |
| `UiCtlContentPageProc` (composite root − `0x140`) | **does not exist** — that address is mid-function; source of the standalone content-page crash |
| `UiCtlDlgBaseProc` | real name is `UiCtlDlgMsgProc`; it mostly chains to base |
| `PopCloser` scans the band and re-arms | confirmed (17× `FrameGetChild`, 9× `FrameDestroy`, 1× `FrameMouseEnable`) |
| `[X]` close path unknown / needs `PopCloser` wiring | `UiCtlDlgCloserProc` is the closer proc and calls **`FrameClose`** |
| checkbox state seeded via `CtlBtnCheck` | confirmed (25× in the General create path) |
| edit needs a sibling `UiCtlBorderProc` "Border" frame with layer/`0x10`-subclass/mouse-inversion | **confirmed** in `CEmail::OnFrameCreate` — one `FrameSetLayer`, one `FrameSetSubclassFlags`, one `FrameMouseEnable`, the `"Border"` name, and the `0x1000000` password style |
| file paths renamed `Gw/Ui/Frame` → `Engine/Frame` | **partial**: `Engine/Frame/FrApi.cpp`, `Engine/Controls/CtlLayout.cpp`, `Engine/Controls/CtlInstance.h` use the new form, but `Gw/Ui/Controls/UiCtlDlg.cpp` and `Gw/Ui/Dialog/DlgOptGeneral.cpp` keep the old one — name-based resolvers must accept both |
| "the host resolvers verify against the installed client" (an earlier revision of this record) | **false, and the check that produced it was circular.** The merge scripts hand-escaped pattern text with `-replace '\\','\\\\'` on input that was *already* escaped, so every pattern they wrote carried `\\xNN` (two backslashes) where the scanner's unescaper requires `\xNN` (one). The health check decoded those files with the same wrong assumption, so it reported the broken entries as healthy. 404 tokens per copy were repaired; see §5.2 |
| "the create path cannot carry a per-window registration" (an assumption made while designing the host) | **false** — see §7.1: `CreateUIComponent` *is* `FrameCreate`, and its 5th argument is the `create_param` the engine hands the proc as `msg[2]` |

## 5. Address caveat (read before using any EXE address)

The WASM layer of the July records is sound: all 24 sampled documented WASM addresses map
exactly to the documented symbols.

**Correction (round 9).** An earlier revision of this section claimed the installed client
had a *different code layout* and that every documented EXE address fell outside `.text`.
That was wrong, and it was my error: section header `VirtualAddress` values are **RVAs**, and
the tooling added the image base only sometimes, so reported "addresses" were 0x400000 low.
The image base is `0x00400000` (PE optional header), `.text` really spans
`0x00401000`–`0x0093A36E`, and with the base applied the documented addresses land inside it
and close to their targets:

| Symbol | Documented (06-14) | Measured (09-30) | Delta |
|---|---|---|---|
| `CtlBtnProc` | `0x0060F4F0` | `0x00614A60` | +0x5570 |
| core `FrameCreate` pattern | `0x0062BFC0` | `0x00631537` | +0x5577 |
| `UiCtlDlgProc` | `0x00876880` | `0x0087D340` | +0x6AC0 |
| `UiCtlPageProc` | `0x00885590` | `0x0088C050` | +0x6AC0 |

So the client **was** rebuilt since June, but the drift is a routine ~22–27 KB shift, not the
wholesale relayout previously described. The operational conclusion is unchanged and now
correctly grounded: hardcoded addresses still go stale on every client update, byte patterns
survive, and the port must resolve by pattern rather than by a recorded address.

### 5.1 Prefer byte patterns over string anchors on this build (verified)

Pattern scanning against this image is reliable. The whole table verifies: **42/42 byte
patterns match and 25/25 assertion anchors are present.**

**String-address anchoring is not reliable**, because some literals are referenced by
nothing at all. That conclusion now rests on correct evidence — re-checked with Ghidra
against the analyzed image (true VAs), after the RVA error described above invalidated the
first pass's numbers:

| Literal | Occurrences | References (Ghidra, whole image) |
|---|---|---|
| `Engine\Controls\CtlLayout.cpp` | 1 @ `0x00A59D00` | **none** |
| `hPlace` | 1 @ `0x00A5A117` | **none** |
| `ActCrEmail` | 1 @ `0x00B9F926` | **none** |
| `m_nodes` | 4 | **2 referenced** (from `FUN_00606e60`, `FUN_006070f0`), 2 not |

So the property is per-literal, not a blanket rule: some assertion strings are reachable
directly from code, others are not reachable at all in the file. A literal that is genuinely
in use having no reference is another face of the same file/runtime gap — `.data` carries
5.6 MB of virtual size against 92 KB of file-backed bytes, so part of the image is built at
load time. Note the earlier revision of this section cited the UTF-16 frame name `EmailEdit`
as the zero-reference example; that specific claim was measured with the faulty arithmetic
and has been dropped rather than restated.

### 5.2 Pattern text escaping — one backslash, and never hand-roll it

A pattern in `offsets/*.json` must **decode** (as JSON) to a value of the form

```
\x55\x8B\xEC\x83\xEC\x10        <- ONE backslash before each `x`
```

The JSON *text* therefore needs a doubled backslash, because `\x` is not a legal JSON escape:

```json
"pattern": "\\x55\\x8B\\xEC"
```

Two independent failures came out of getting this wrong:

1. **Doubled escaping.** Scripts that spliced patterns into the table by hand applied
   `-replace '\\', '\\\\'` to values that were already escaped, producing four backslashes in the
   text and two after decoding. Every affected resolver failed at startup with
   `scan returned null` while the file-level health check — which decoded with the same wrong
   assumption — reported them healthy. The scripts now collapse any run of backslashes to one and
   let `ConvertTo-Json` do the escaping, so they are correct for any input quoting and safe to
   re-run. The fix is data-only: the DLL reads this table at runtime, so repairing the JSON arms
   the resolvers with no rebuild.
2. **Masks must match the decoded byte count**, not the text length. A mask of 18 `x` vs a
   19-byte pattern silently shortens the comparison, because the scanner uses `strlen(mask)` as
   the pattern length. Always count from the *decoded* value.

`_ghidra/scripts/verify_patterns.ps1` is the replacement check and is deliberately strict: it
rejects any pattern that is not a pure `\xNN` stream, asserts `strlen(mask)` equals the decoded
byte count, and re-scans the real image, reporting `unique` / `missing` / `ambiguous` / `defective`
separately. Unlike the earlier check it cannot "verify" a malformed table, because it never trusts
the text it did not decode itself.

### 5.3 Patterns must be loader-invariant (wildcard the relocated bytes)

This build's assert macro embeds absolute addresses:
`push <LINE>; mov edx,<FILE ptr>; mov ecx,<MESSAGE ptr>`. Those immediates are **base
relocations**. The client maps at `0x00FD0000`, not the preferred `0x400000`, so the PE loader
rewrites them at map time — meaning a pattern containing them matches the pristine file and can
**never** match at runtime.

That is precisely what happened to three of the nine host natives. In-client,
`Patterns::Resolve` reported

```
Pointer resolution failed: ui.frame_schedule_size_func      step=scan_target reason=scan returned null
Pointer resolution failed: ui.frame_native_size_changed_func step=scan_target reason=scan returned null
Pointer resolution failed: ui.layout_dtor_func              step=scan_target reason=scan returned null
[dialog-host] resolved mask 0x1E9/0x1FF
```

while a file-based check called all three healthy. The immediates at fault were `0x00A5D92C`
(the shared assert *file* pointer) and `0x00A59CF0`.

**Rule: wildcard (`?`) every pattern byte the loader rewrites.** Wildcarding makes a pattern
loader-invariant, and only then are a file scan and a runtime scan *guaranteed* to agree — which
is the property that makes file-based verification sound in the first place. Four patterns were
affected and are now fixed, each still matching exactly once:
`ctl_layout_align_translator` (offsets 21–23), `layout_dtor` (10–13),
`frame_schedule_size` and `frame_native_size_changed` (16–19, 21–23).

`verify_patterns.ps1` now parses `.reloc` and reports the condition as `loader-dependent`, so this
class of bug cannot recur silently.

A caution worth keeping: **"live bytes match the file" proves nothing if the patterns sampled
contain no relocated bytes.** The four addresses checked earlier in this work were all in that
category, which is why the check agreed and the conclusion was still wrong. Always audit for
relocated bytes; do not infer safety from a spot check.

## 6. What this unblocks

1. The host dispatcher can now be written against a known contract: `MemAlloc` an instance,
   store it through `*(hdr.param)`, build/clear the `CCtlLayout` node tree, `SetFrameId`,
   run `OnFrameCreate`, then request the size pass with `FrameScheduleSize` +
   `FrameNativeSizeChanged`.
2. The layout tree shapes are known, including the per-row `FrameGetNativeSize` measurement
   that keeps a slider inside its column.
3. The close path has a named target: route `[X]` through `FrameClose` so `PopCloser` runs
   (rather than destroying children out from under the chrome).
4. The content-page approach must be abandoned as specified; the `CtlView` host path is the
   evidence-backed alternative.
5. The instance is a concrete, allocatable object: `0xD4` bytes, vtable at `+0x00`, frame id
   at `+0x04`, `CCtlLayout` at `+0x08`. A Py4GW-authored dispatcher can reproduce it exactly
   instead of guessing at "an instance of some size".

Still open: whether `CCtlLayout` derives from `Ui::CLayout`, the meaning of each
`ELayoutH`/`ELayoutV` value (the flag bits are known, the enum names are not), and in-client
confirmation. The message ids are settled (§1.1). The code changes belong in
`Py4GW_Reforged_Native`, which is outside this repository.

## 7. Implementation appendix — what the landing needs

**The existing resolver table is healthy on the current client (verified).** Every byte
pattern in `Py4GW_Reforged_Native/offsets/ui.json` still matches the installed `Gw.exe`
(42 patterns, 0 missing) and all 25 assertion anchors are still present as strings. So no
re-anchoring of existing entries is required; only the new host machinery needs entries.

**Verified assertion anchors on the current client.** These strings are present in
`F:\GW\GW1\Gw.exe` (ASCII) and can anchor the new resolvers:

| Anchor string | Anchors |
|---|---|
| `m_nodes.Count() - 1` | a `CtlLayout.cpp` method — **reachable**, referenced from `FUN_00606E60` / `FUN_006070F0` |
| `hdr.param == NULL || *hdr.param != NULL`, `!*hdr.param` | `TCtlInstance<T>::Ptr` / `MsgProc` (`Engine\Controls\CtlInstance.h`) |
| `CTL_VIEW_STYLE_SCROLL_ON_BOTTOM` | `CtlView::CView::OnFrameCreate` |
| `No valid case for switch variable 'hPlace'` | **not usable as an anchor** — the literal has no reference anywhere in the image (see §5.1) |
| `Engine\Controls\CtlLayout.cpp`, `Gw\Ui\Account\ActCrEmail.cpp` | **not usable as anchors** — file-path literals with no reference in the image |

That last point matters: two anchors an earlier revision of this appendix recommended are
dead. Anything anchored on a file-path literal or on `hPlace` will resolve nothing, so the
`CtlLayout` verbs and the `ActCrEmail` edit form must be found structurally (by their call
shapes) rather than by string anchor.

Note the mixed path separators and namespaces: resolvers must accept both the `Engine\…`
and `Gw\Ui\…` forms, because the client still contains both.

**Deriving an anchor: three traps that produce false negatives (learned the hard way).**

1. **Search a literal, not a substring.** The address the engine references is the
   *literal's start*, which can be several bytes before the substring you are looking for.
2. **A literal can occur more than once**, and only one occurrence may be referenced — with
   `m_nodes`, two of four occurrences are referenced and two are not. Enumerate every
   occurrence and try every candidate start in the ~32 bytes before it.
3. **Search for the true VA, not the RVA.** Section header `VirtualAddress` values are
   relative to the image base (`0x00400000` here). Searching for RVA bytes finds nothing and
   mimics "this literal is unreferenced" — this exact mistake produced several false
   negatives in an earlier revision of this document and a wrong drift claim in §5.
4. **References are not always from code.** Assertion machinery also stores
   `{file pointer, message pointer, line}` descriptors in pointer tables, and some of those
   tables sit inside the `.text` range, so a literal may need a `dereference` step rather
   than a bare `scan`.

The cleanest way to settle any of this is Ghidra on the analyzed image rather than manual
byte arithmetic: `_ghidra/scripts/FindStringRefs.java` reports every reference to a literal
with the containing function, and worked as the authority for §5.1.

The one derivation completed end-to-end resolves a `CtlLayout.cpp` assert literal at
`0x00A59E7C` back to its referencing functions `FUN_00606E60` and `FUN_006070F0`. An earlier
revision of this section reported that derivation as literal `0x00659F20` →
function `0x002572F0`; **those numbers were withdrawn** — they came from RVA-based scanning
and the attribution was spurious.

A 24-byte pattern was extracted at that address and is kept for completeness, **but it is
currently unattributed** — the earlier claim that this is a `CtlLayout` method came from the
withdrawn derivation. Verify what it is before relying on it:

```text
\x55\x8B\xEC\x8B\x45\x08\x56\x57\x85\xC0\x74\x5F\xFF\x35\x04\x2C\xA6\x00\x50\xE8\x38\x8B\xE1\xFF
```

Its `mov eax,[ebp+8]` prologue means it takes a stack argument, so it is not
`CCtlLayout::End` (which takes none).

**Resolvers still to add** — `FrameMsgCallBase`, `FrameGetNativeSize`, `SetHoverTarget`,
`ClearFocusFrame`, `FrameSetPositionPosSize`, `CtlTextSelectableProc`, `CtlFrameListSelectableProc`,
`CtlFrameListSelectableGetSelection`, `UiCtlPageProc`, `PlainContainerProc` are **already
landed** (see §8). Outstanding: `FrameScheduleSize`, `FrameNativeSizeChanged`, the
`CCtlLayout` verbs (ctor / `SetFrameId` / `Clear` / `Size` / `SizeQuery` / `Child` / `Row` /
`Column` / `Gap` / `End`), `Ui::CLayout::Size` / `SizeQuery`, `FrameClose`, `PopCloser`,
`UiCtlDlgCloserProc`, `UiCtlDlgMsgProc`, `UiCtlBorderProc`, `FrameSetLayer`,
`FrameSetSubclassFlags`, `FrameMouseEnable`, `FramePlaceChildren`.

Four of those are already derived and verified, and ship as a reviewable package in
`_re_session/native_dialog_host_patch/` (host header, JSON additions, compile check): a
`patterns`/`resolvers` fragment for `frame_msg_call_base`, `frame_get_native_size`,
`set_hover_target` and `ctl_text_selectable_proc`, each matching exactly once in the
installed client. The host header compiles clean under MSVC x86 `/W4`. The package README
lists what it does *not* verify — chiefly the message ids and the allocator pairing — and
the remaining natives still needing derivation.

**Dispatcher shape.** The authored host must present the engine the same contract as
`TCtlInstance<T>::MsgProc`:

```c
void __cdecl HostProc(FrameMsgHdr const& hdr, void const* a, void* b);
//  create : instance = *(hdr.param); if null, MemAlloc(0xD4) + vtable + frameId,
//           CCtlLayout-construct at instance+8, SetFrameId, run the content builder,
//           then FrameScheduleSize + FrameNativeSizeChanged
//  size   : CCtlLayout::Size / ::SizeQuery on the embedded layout
//  notify : content-class notify handler
//  destroy: content dtor, operator delete, then chain to base
//  default: FrameMsgCallBase(hdr, a, b)
```

Still unverified and left to the implementer: the numeric message ids behind the size and
notify arms (the decompiled switch was reconstructed as case indices, not ids), and
in-client behaviour. Compile-level checking is possible in this environment (VS 2022 plus
the configured `build/` tree); in-client verification needs the injected game client and
belongs to the repository owner.

### 7.1 The create handoff — what is carried in the message (measured)

**Confirmed by measurement.** `CreateUIComponent`'s 4th argument **is** the frame proc. A host
dispatcher installed there receives, in order, `msg[1] == 0x5`, `0x4` (class declaration, with
`msg[0] == 0` — no frame id yet), then `0x9` (create) with the new **frame id in `msg[0]`**, then
`0x32`, `0xA`, `0x15`, `0x38` (size query) and `0x34`. That independently confirms the message-id
readings in §1.1 against a live client.

**Falsified by the same run.** The 5th argument is **not** exposed as `hdr.param`. In the create
message the host observed `msg[2] == 0x4AEBCD3C`, an engine-owned pointer constant for that frame
and not the value passed in; and `get_frame_user_param_by_frame_id` reads **0**. So the earlier
claim in this section — that `CreateUIComponent`'s 5th argument becomes `msg[2]` and can carry a
host record — is **wrong for this path**, and any design keyed on it will never find its record.
Consequences that were paid for in-client:

- The record was never matched, so no instance was allocated and the frame's param stayed empty.
- The engine's destroy path then dereferenced that empty slot and crashed the client:
  `Memory at address 0000019b could not be read`, null base + frame field `0x19B`, on the
  `destroy_host_window` path.

**What the host uses instead.** Identity comes from `msg[0]`, the frame id, which is authoritative
and always present from the create message onward. The host publishes a record before creating,
marks it as the in-flight create, and binds it to the id learned from `msg[0]`. Every later
message is matched by id. This needs no global lookup at create time and does not depend on
`hdr.param` at all.

**Still unresolved, deliberately not guessed:** what argument 5 actually is (Py4GW types it
`wchar_t*` and the wrappers name it `name_enc`, which suggests an encoded-name/caption payload
rather than user data), and what `msg[2]` actually points at. Neither is needed for ownership now
that identity comes from `msg[0]`.

## 8. Landing status

The first slice is now **landed in `Py4GW_Reforged_Native` and compiles**:

| Path | Change |
|---|---|
| `include/GW/ui/native_dialog_host.h` | new — the host API, instance geometry, dispatcher declaration |
| `src/GW/ui/native_dialog_host.cpp` | new — resolver wiring, dispatcher, host registry (picked up by the existing `src/*.cpp` glob, so no CMake change). **Superseded**: the frame-id registry assumed a frame id exists at create time, which it does not; see §7.1 and §8 |
| `src/GW/ui/ui.cpp` | two lines — include plus `try_resolve("ResolveDialogHostNatives", …)` |
| `offsets/ui.json` | additive — 10 patterns and 10 resolvers (the four host ones plus six legacy ones: `clear_focus_frame`, `frame_set_position_pos_size`, `ui_ctl_page_proc`, `plain_container_proc`, `ctl_frame_list_selectable_proc`, `ctl_frame_list_selectable_get_selection`) |

`cmake --build build --config RelWithDebInfo` completes with no diagnostics and produces
`Py4GW.dll`. The build was deployed to the launcher's injection path
(`Py4GW_Reforged/Py4GW.dll`) with a timestamped backup beside it.

**Two `offsets/ui.json` copies must stay in sync (easy to miss).** `Patterns::Initialize`
reads `GetModuleDirectory()/offsets`, and the launcher injects the DLL from the mod root,
so at runtime the effective table is `Py4GW_Reforged/offsets/ui.json` — *not* the native
repo's copy. A pattern added only to the native repo resolves nothing in-game. Both copies
now carry the same 79 patterns / 94 resolvers and are byte-identical; the runtime copy verifies
50/50 patterns and 25/25 anchors against the installed client (see §5.2 for the escaping defect
that made the older copy silently unresolvable, and §8 for the current numbers).

Behaviour to expect on injection: `ResolveDialogHostNatives` logs
`[dialog-host] resolved mask 0x1FF/0x1FF; ownership available` when all nine natives resolved,
and names the unresolved bits otherwise. The earlier revision passed `export_to_disk = false` to
`LogInfo`, which is why no such line ever reached the client log; the call now uses the default
(`true`).

**All nine host natives now resolve in principle**, and the pattern table is repaired and
re-verified (50 unique hits, 0 missing, 0 defective, 0 loader-dependent, 25 assertion anchors; one
pre-existing ambiguity remains in a renderer entry, `gr_model_set_color_anchor`, which this work
does not touch). The 13 host-critical patterns each match exactly once, every resulting VA
independently equals the address derived from Ghidra, and none embeds a loader-rewritten byte:

| native | VA | bit |
|---|---|---|
| `CtlLayout::Clear` | `0x00606FA0` | 6 |
| `CtlLayout` ctor | `0x00606D60` | 3 |
| `CtlLayout` dtor | `0x00606DA0` | 4 |
| align translator | `0x006072B0` | — |
| `FixGapMarginFlags` | `0x00607130` | — |
| `SetFrameId` | `0x006075A0` | 5 |
| `Size` | `0x006075E0` | 7 |
| `SizeQuery` | `0x00607E80` | 8 |
| `SizeInternal` | `0x00607710` | — |
| `SizeQueryInternal` | `0x00607F90` | — |
| `FrameScheduleSize` | `0x006349C0` | 1 |
| `FrameNativeSizeChanged` | `0x00634660` | 2 |
| `FrameMsgCallBase` | `0x0064C680` | 0 |

Two independent derivations agreeing — pattern scan and Ghidra — is the strongest offline check
available, and the earlier circular health report could not make it. It is still **not** a runtime
observation: the first injection of the previous table read `resolved mask 0x1E9/0x1FF` because of
the loader-dependent bytes described in §5.3, which the file check had blessed. The table now
satisfies both checks, and `0x1FF` is the expected result — but that expectation is a prediction
until a client reports it.

**Landed in `Py4GW_Reforged_Native`:**

| Path | Change |
|---|---|
| `include/GW/ui/native_dialog_host.h` | rewritten to the record design; adds the layout dtor native and real entry-point signatures |
| `src/GW/ui/native_dialog_host.cpp` | rewritten — ownership is keyed off the frame's own param slot, the way `TCtlInstance<T>::Ptr` does it, instead of a frame-id table. A frame-id table is possible but needs a separate "pending config" channel: the configuration must be supplied before the `FrameCreate` call, while the id only arrives during it as `msg[0]`. (An earlier revision of this record overstated that as impossible; the id *does* exist by the time the proc is called.) |
| `src/GW/ui/ui_bindings.cpp` | six `UIManager` statics: `dialog_host_ready`, `dialog_host_resolved_mask`, `dialog_host_window_count`, `dialog_host_proc_address`, `create_dialog_host_window`, `destroy_dialog_host_window` |
| `offsets/ui.json` (both copies) | 404 wrongly-escaped tokens repaired per copy; one mask/byte-count defect fixed |

Implementation details that are deliberate, not incidental:

- **Destroy ordering.** The record is freed *after* the chain to `FrameMsgCallBase`, because the
  base proc receives the same message and may still read `hdr.param`; freeing it in the destroy
  arm would be a use-after-free.
- **Validity gate.** `msg[2]` is checked against the live table (plus the in-flight create
  record) before being reinterpreted, so a foreign or stale param becomes a no-op instead of a
  garbage `Instance*` reaching the layout calls.
- **Table slot reserved before create**, so a post-create failure cannot leave the engine holding
  a record that was already freed.
- **Layout teardown** runs `Ui::CLayout::~CLayout()` on the embedded layout, matching the
  engine's `~T`; skipping it leaks the node array.
- **Capability bits must not gate ownership.** `Ready()` tests a *subset*
  (`(mask & kRequiredMask) == kRequiredMask`), never the whole mask for equality. Adding the
  geometry bit (bit 9) to the mask silently disabled the entire owning path because the gate was an
  equality test: in-client the log read
  `resolved mask 0x3FF/0x1FF; ownership unavailable (pass-through)` immediately followed by
  `unresolved bits 0x0` — every native resolved, and ownership still refused. That pair of lines is
  contradictory on its face, which is how it was caught; the diagnostic now reports ownership and
  geometry separately (`ownership …; geometry …`) so the contradiction cannot hide again. Learn the
  general lesson: when a mask gains a bit, every equality comparison against it is a latent
  regression.
- **Game-thread requirement (and a hazard this exposed).** `game_thread::Enqueue` invokes its
  callback *inline* only when `g_in_game_thread` is set, and otherwise pushes it onto a singleshot
  queue. Several pre-existing bindings capture their result by reference (`&result`) and read it
  straight after the enqueue, which is correct only on the inline path and is a write through a
  dangling stack pointer on the deferred one.
  **Measured in-client: `IsInGameThread()` is FALSE inside script `main()`.** Scripts do not run on
  the game thread, so a create issued from Python is always queued, and any binding of this shape
  returns `0` from Python while still performing its work a tick later. An earlier revision of this
  record wrongly advised calling from `main()`/`draw()` to get the frame id back — a smoke test on
  2026-10-12 disproved it (the create returned `0` and the log then showed
  `host window created: frame 15`). The host API is therefore **asynchronous by contract**: the
  create returns `0` meaning *queued*, and callers poll `dialog_host_last_frame_id()` /
  `dialog_host_window_count()`. The host bindings also own their result storage in a `shared_ptr`
  so the off-thread path cannot dangle.

`cmake --build build --config RelWithDebInfo` completes with no diagnostics (exit 0) and produces
`Py4GW.dll`, 13,728,768 bytes, sha256 `4CC142A3…`. It is deployed to the launcher's injection
path with a timestamped backup beside it.

**Runtime status: the owning path executed in-client on 2026-10-12 01:24:34.** This is the first
time the recovered contract has run against a live client, and it covers the whole create-phase
contract:

```
[dialog-host] record 0x26564168 published at slot 0 (parent 1, flags 0x300)
[dialog-host] proc msg[0]=0  msg[1]=0x5 msg[2]=0x00000000
[dialog-host] proc msg[0]=0  msg[1]=0x4 msg[2]=0x00000000          <- class declaration, pre-id
[dialog-host] proc msg[0]=15 msg[1]=0x9 msg[2]=0x078A1524          <- create, id in msg[0]
[dialog-host] frame 15 OWNED: instance 0x2CFE82C0, layout 0x2CFE82C8, size pass scheduled
[dialog-host] proc msg[0]=15 msg[1]=0x37 ...                       <- size message handled
```

Verified by observation, not inference: instance allocated (0xD4 bytes); the embedded
`CCtlLayout` constructed at exactly `instance + 8`; `SetFrameId` and `Clear` run; the size pass
scheduled; and a subsequent `0x37` size message dispatched through the size arm. Message ids
`0x4`/`0x9`/`0x37`/`0x38` are confirmed live against §1.1. Note `record 0x26564168` differs from
`msg[2] 0x078A1524`, which is the measurement behind §7.1's correction.

**Still not verified:** anything *visual*. The frame measures `0x0` and nothing draws, which is
expected — no content means no layout nodes (§9). Also unverified: the `build_layout` hook's
placement (called between `Clear()` and the size schedule, chosen from the decompiled sequence but
not confirmed useful), and teardown.

**Open bug — engine destroy faults.** `GW::ui::DestroyUIComponent` crashes inside Gw.exe:
`Memory at address 0000019b could not be read`, on the `destroy_host_window` path (crash bundles
`py4gw-20261012-004710` and `-011523`). An earlier revision blamed the empty instance slot and
wrote it through `hdr.param` accordingly; the fault **persisted** after that fix and after the
instance was confirmed allocated, so the cause is not yet established. `+0x19B` lies beyond the
0xD4-byte instance (a `Frame` is 0x1C8), so the dereferenced object may be the frame rather than
the instance — unresolved. Destruction is deliberately disabled in the smoke test until this is
settled, so each run leaves one invisible frame behind (cleared by restarting the client).

Also note the build carries unrelated uncommitted changes that were already in the native tree
(`character.h`, `map.h`, `CrashHandler.*`, `Py4GW.cpp`, `agent_recolor.json`).

**Remaining work:** `FileScanner::FindAssertion` still builds its operand sequence as
`push msg; mov edx,file; mov ecx,line`, while this build's assert macro is
`push <LINE>; mov edx,<FILE ptr>; mov ecx,<MESSAGE ptr>` — line and message operands are swapped,
so assertion anchors match only by luck. Host patterns are byte-pattern-based and unaffected, but
the 25 assertion anchors in the table are worth migrating or fixing.

## 9. What a visible window still requires (measured)

The owner contract is proven (§8), and a child control can be created and parented to an owned
host frame. Measured in-client on 2026-10-12 01:45:

- `create_text_label_frame_by_frame_id(285, 0x300, 0, "", "Py4GW host")` returned frame **286**
  synchronously, and `get_child_frame_by_frame_id(285, 0)` found it at **child_offset 0** — so
  parenting and child indexing both work, and the child create did not crash.
- The host (285) and the child (286) each report `rect = (0,0,0,0)` and `native_size = (0,0)`.
  The label did **not** self-size, and nothing draws.

Then, with geometry applied through the resolved anchor-6 facade (host frame 19, child frame 20,
2026-10-12 21:25):

- The host reads `rect = (200, 200, 280, 160)`, `native_size = (280, 160)`; the child reads
  `rect = (220, 220, 140, 24)`, `native_size = (140, 24)`. **The geometry stuck** — the parent's
  layout pass did not reset it, confirming that the anchor-6 route is the right primitive and that a
  plain `FrameSetSize` was correctly avoided.
- The child was given `(20, 20)` and landed at `(220, 220)` — parent origin plus relative offset,
  which is the anchor-6 semantic, so child positioning works without any layout-tree population.
- The rect's flag/anchor field reads **6**, exactly the constant `FUN_0064f980` writes to `rect+8`.
  That is a third independent confirmation of the Ghidra finding, after the pattern bytes and the
  decompiled body.
- No crash, and messages `0x1`, `0x8`, `0x15`, `0x37`, `0x34` kept arriving.

Three requirements remain, in dependency order:

1. **Geometry.** Nothing ever gives the frame's `CRect` (at `frame+0xD0`) a rect. The repo's own
   notes (`docs/RE/ui_elements_creation_recipes.md:28`, `docs/RE/native_button_pipeline.md:54`)
   warn that a plain `FrameSetSize` is overwritten by the parent's layout pass back to 0×0 →
   invisible, and recommend instead the **anchor-6 setter**, which forwards to
   `IFrame::CRect::SetPosition(frame+0xD0, pos, size, anchor=6)`. The migrated module exposes
   geometry **getters only** — a grep for `SetFrameSize|FrameSetPosition|ResizeFrame|SetFrameRect`
   across `Py4GW_Reforged_Native` matches only `.md` files — so a native must be added.
   **Resolved by Ghidra on 2026-10-12.** The setter is
   `FUN_00634cc0(frameId, Coord2f* pos, Coord2f* size)`: `assert frameId != 0` (line `0x840`), then
   `GetFrame(frameId)` (`0x0064D2C0`, already resolved by the host), then
   `CRect::SetPosition(frame+0xD0, pos, size, 6)`. That inner setter is
   `FUN_0064f980(float* pos, float* size, uint anchor)` (`__thiscall`), which writes the rect as
   anchor `+8`, x `+0xc`, y `+0x10`, w `+0x14`, h `+0x18`, and asserts `0x238` on an inverted
   container rect — the same assert the button-pipeline notes recorded for this path. The harvested
   pattern `frame_set_position_pos_size` anchors on that very prologue, and its bytes decode to
   exactly that entry (`push ebp; mov ebp,esp; mov eax,[ebp+8]; test eax,eax; jnz; push 0x840`), so
   byte pattern and decompiler agree — which is why no new pattern was needed.
   **Both addresses the older notes gave for geometry are wrong:** `0x0062F770` is `+0x90` inside
   `FUN_0062f6e0` (a linked-list insert) and `0x0062f9a0` is `+0xe0` inside `FUN_0062f8c0` (a
   buffer/stream reader). Neither is a geometry setter; binding either would have been a crash.
   Confirmed in the same pass: `FUN_00606fa0` is `CCtlLayout::Clear` (frees each 0x2C node, zeroes
   `count` at `+0x10`), and `FUN_00607170` is the node-adding verb — it allocates
   `new(0x2c, "?AVSizeNode@CLayout@Ui@@")`, stores the frame id at `node+4`, flags at `+0x24`, with
   the align translator `0x606072B0` inside it. Landed as `DialogHost::SetFrameRect` plus the
   `dialog_host_set_frame_rect` binding; the native reports as mask bit 9, deliberately outside the
   `0x1FF` that `Ready()` requires, so missing geometry cannot disable ownership.
2. **Content that paints.** A bare container has no background art, and a label needs geometry plus
   its font/scale path before it draws.
3. **Chrome/notify**, if a dialog-looking window is wanted — the subclass-proc path in §3.

Also measured, and worth knowing independently of the host: the pre-existing
`create_*_frame_by_frame_id` widget creators call `GW::ui::Create*` **directly, without
`game_thread::Enqueue`**, so they mutate engine UI state on the Python thread and return a real id
synchronously — unlike the host's own create, which queues and returns 0. That inconsistency is
pre-existing, not introduced here, and it is UB-adjacent. It is recorded rather than changed,
because altering it would change the behaviour of the whole widget API.

## Reproduce

Decompilation was produced with Ghidra 12.0.4 headless against the already-analyzed
program `/Gw.wasm` in the project `third time`, opened read-only. The WebAssembly loader
comes from the `ghidra-wasm-plugin` user extension; a headless run needs that extension
visible in the settings directory in use.

- Input: `Gw.wasm`, 28,893,607 bytes, mtime 2026-05-20,
  sha256 `F023FD913DF87956A48B5CF1DCB52D…` (recompute with `Get-FileHash`).
- Scripts (kept in the workspace scratch area, not committed):
  `_ghidra/scripts/DumpDecomp.java` (decompiles by symbol substring),
  `DumpSignature.java` (emits the per-function call/constant/string signature used above),
  `DumpData.java` (raw bytes/dwords at an address, used for the align tables),
  `DumpSymbols.java` (symbol dump), `wasm_names.ps1` (name-section extractor).
- Outputs: `_ghidra/out/owner_dump_ro.c`, `_ghidra/out/signatures.txt`,
  `_ghidra/out/edit_border_sig.txt`, `_ghidra/out/wasm_symbols.txt`,
  `_ghidra/out/resolver_health.txt`. These are large generated catalogs and stay with the
  tool; they are not documentation.
- The resolver-health table is produced by
  `_ghidra/scripts/resolver_health.ps1 -Json <offsets.json> -Exe <Gw.exe>`; it re-checks
  every pattern and assertion anchor against whatever client image is passed, so it doubles
  as the drift check after a game update. **Prefer `_ghidra/scripts/verify_patterns.ps1`**
  (same arguments): it decodes patterns strictly and reports `unique` / `missing` / `ambiguous` /
  `defective` separately, whereas `resolver_health.ps1` shares an escaping assumption with the
  code that writes the table and so once reported a wholly malformed table as healthy (§5.2).
- Anchor derivation is `_ghidra/scripts/find_anchor.ps1 -Exe <Gw.exe> -Strings <literals>`;
  it implements the occurrence-scan described above and prints a uniqueness-checked pattern
  per candidate function. Outputs land in `_ghidra/out/anchors*.txt`.
- Notes: full auto-analysis of this module is impractical (it scans the WASM linear
  memory); decompiling selected symbols from the pre-analyzed program is the working
  method. The decompiler renders the Emscripten pos-stack discipline as bogus branches on
  `&stack0x00000000`, which is why the call/constant signature is a more reliable reading
  than the raw C bodies.
