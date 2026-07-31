# Native inventory-slot tinting

## Result

Guild Wars already tints the background model of an item slot.  It uses the
ordinary renderer primitive `GrModelSetColor`, not a screen-space overlay.  A
native hook can therefore apply an arbitrary ARGB colour to an individual item
frame after the game rebuilds it.  The tint remains clipped, scaled, and faded
with the game's UI.

This is the native route for an Inventory+ "colorize"/marking feature.  It is
not the existing DX overlay rectangle used by the Python widget.

## Confirmed mapping

| Purpose | Gw.wasm (symbols) | Gw.exe (stripped) | Confidence |
| --- | --- | --- | --- |
| Item-frame content rebuild (`OnFrameContentAdd`) | `CItemImageFrame::OnFrameContentAdd` | `FUN_004d9fc0` / `0x004d9fc0` | High |
| Item-frame model construction | `CItemImageFrame::BuildIconModel` + background build | `FUN_004d8960` / `0x004d8960` | High |
| `GrModelSetColor(HGrModel_tag*, Color4b const&)` | `ram:8016eace` | `FUN_00668e80` / `0x00668e80` | High |

`FUN_004d9fc0` is the concrete **hook target**. It releases and rebuilds the
background and icon models, applies the stock rarity colour, and submits the
fresh handles to frame content. The former rarity-colour anchor was inside
this function; subtracting `0x174` incorrectly resolved the old paint symbol
to the same address and caused MinHook's `MH_ERROR_ALREADY_CREATED` when a
second content hook was added. The obsolete paint pattern/resolver is removed;
one content detour now handles both models.

The original is a `__thiscall` routine with one stack argument (`ret 4`); use a
fastcall-shaped detour when hooking it:

```cpp
// Actual target consumes the final content payload stack argument and ignores EDX.
using ItemImageFrameContentAddFn = void(__fastcall*)(void* item_image_frame,
                                                      void* edx,
                                                      const void* content_msg);

// `GrModelSetColor` is cdecl and receives a pointer to a Color4b/ARGB word.
using GrModelSetColorFn = void(__cdecl*)(void* hgr_model,
                                         const uint32_t* argb);
```

## CItemImageFrame fields used here

These are confirmed in both binaries for this path.  Treat the rest of the
instance as unmodelled.

| Offset | Field |
| --- | --- |
| `+0x04` | owning slot frame id |
| `+0x20` | slot state/style flags |
| `+0x2c` | background `HGrModel_tag*` (the tint target) |
| `+0x34` | icon `HGrModel_tag*` (rebuilt texture model) |
| `+0x38` | overlay model |
| `+0x54` | item id (passed to `ItemCliGetData`) |
| `+0x68` | item source mode: `0` normal, `1` PvP item definition |

`+0x2c` is valid only after the original target has run.  Do not cache the
model handle: item moves, bag changes, and content rebuilds can replace it.

## What the stock path does

The stock code sets the background colour to opaque white unless the item
rarity-border preference is enabled (`PrefGetFlag(0x58)`,
`FlagPreference.ItemRarityBorder`).  When enabled, normal-item flags choose:

| Condition | ARGB |
| --- | --- |
| `flags & 0x10` and `flags & 0x10000000` | `0xFFED1C24` red |
| `flags & 0x10` otherwise | `0xFF00FF00` green |
| `flags & 0x400000` | `0xFFAF78FF` purple |
| `flags & 0x20000` | `0xFFFFD232` gold |
| otherwise | `0xFFFFFFFF` white |

It then invokes `GrModelSetColor(this + 0x2c, &color)` and adds the model to
frame-content layer 1.  This proves the desired per-slot tint primitive is
already renderer-native and alpha-capable (`0x80RRGGBB` is a suitable
semi-transparent starting point for visual testing).

## Reforged-Native implementation specification

Put this in the `GW::ui` module (not Python/ctypes).  Expose a small managed
rule store keyed by **slot frame id**:

```text
set_inventory_slot_tint(frame_id: uint32, argb: uint32)
clear_inventory_slot_tint(frame_id: uint32) -> bool
clear_inventory_slot_tints()
```

Frame-id keys mean a caller tints the exact resolved slot, rather than every
occurrence of an item id.  An item-id convenience API may translate to frame
ids in Python, but should not be the native hook's identity.

Detour sequence:

1. Call the original `CItemImageFrame::OnFrameContentAdd` function first.
2. Read `frame_id` from `this+0x04`; look it up in a copy-on-write snapshot.
   The paint detour must never take a mutex.
3. If a rule exists and `this+0x2c` is non-null, call
   `GrModelSetColor(model, &rule_argb)`.
4. On set/clear, queue one redraw for that frame through the existing UI
   redraw path so the change is visible immediately.

Always call the original.  Install/enable the detour only while the feature
has at least one rule (or use the established master-enable gate); the empty
case must be a cheap pass-through.  Reapplying after the original is essential:
the game's own rebuild path otherwise overwrites a colour on the next paint.

The callback runs on the game/UI thread.  Binding mutations must be marshalled
to that thread or publish an immutable rule snapshot, following
`GW::agent_recolor`'s lock-free detour pattern.  Never expose the raw model
handle to Python.

## Offset entry

The old rarity-colour anchor is intentionally not present in
`Py4GW_Reforged_Native/offsets/ui.json`: it is inside
`CItemImageFrame::OnFrameContentAdd` and resolving it with `-0x174` produced a
duplicate hook target. The active offset scans the unique content-add prologue:

```json
"item_image_frame_content_add_anchor": {
  "pattern": "\\x55\\x8B\\xEC\\x83\\xEC\\x24\\x56\\x8B\\x75\\x08\\x57\\x8B\\xF9\\xF6\\x06\\x20",
  "mask": "xxxxxxxxxxxxxxxx",
  "offset": "0x0",
  "section": "text"
}
```

The resolver scans this prologue directly. `GrModelSetColor` still needs its
own resolver; do not hard-code its address in production.

## Test plan

1. Enable the stock `ItemRarityBorder` preference as a visual sanity check.
2. Add one opaque, obvious tint to a known inventory-slot frame and confirm it
   colours the slot background without covering the icon/text.
3. Replace it with an alpha value (for example `0x80FF8000`) and confirm the
   result scales, clips, and fades with the inventory window.
4. Move, stack, identify, and swap bags while the rule remains active.  The
   tint must survive each repaint/rebuild, and clearing the rule must restore
   the stock colour on the next queued redraw.

## Saturation follow-up: shader constant path (WASM-first RE)

### Opacity result (validated)

The icon texture was not merely suffering from the tint colour.  Stock
`CItemImageFrame::OnFrameContentAdd` calls `GrModelSetAlpha` on `this+0x34`
with `0xC0` for ordinary icons (and `0xFF` for the highlighted state).  The
EXE setter is `FUN_00644660`; WASM is `ram:8016e345`.  The native test now
exposes this as the first “Frame opacity boost” checkbox and applies alpha
`0xFF` to the background model `+0x2c`.  This is renderer-native, remains
clipped with the inventory frame, and does not cover tooltips.

The first direct `GrModelSetAlpha` prologue pattern was not accepted by the live
scanner (`scan returned null`) even though it matched the reference Ghidra image.
The offset was replaced with a call-site resolver: it anchors on the already
working `CItemImageFrame::OnFrameContentAdd` function, finds the `push icon; call
GrModelSetAlpha` sequence within that function, and resolves the relative call
target. After deploying the rebuilt DLL and matching `offsets/ui.json`,
`alpha_resolved` must be `true`; only then can `background_alpha_calls` or
`icon_alpha_calls` increase.

The alpha setter is now also reapplied from the existing paint hook for the
background model.  The content callback runs after the frame content is
published, and the UI layer can rewrite model alpha while assembling its draw
list; paint-time reapplication is the correct ordering for the first checkbox.

The first material-constant probes were rejected: short stripped-EXE prologues
matched several unrelated renderer functions.  No material setter or constant
ID is enabled until a unique call-site/data anchor is found; this avoids the
earlier `UINT32_MAX`/invalid-material crash path.

### Next RE target: the border material

WASM `CItemImageFrame::BuildIconModel` (`ram:81149b63`) separates the two
targets.  The frame/border model at `this+0x2c` is created with the class-global
material `DAT_ram_005a9f14`; the item icon at `this+0x34` uses the per-frame
material created by `CreateIconMaterial` (`this+0x28`).  Therefore the preferred
next target is `CItemImageFrame::OnFrameClassInitialize`
(`ram:8114c9e0`): identify the unique creation/data path for
`DAT_ram_005a9f14`, then map that call site to the stripped EXE.  This should
reveal the border shader/material constant that controls its blend opacity.

Only after that material map is proven initialized should we use
`GrModelSetMaterialConstant` (`ram:80171599`, EXE wrapper `0x00645070`).

`GrModelSetColor` is the correct native tint primitive, but it only writes the
8-bit model colour.  It cannot make a channel brighter than 255 and the stock
border shader blends that colour with the UI.  The item **icon** has a second,
stronger path:

| Purpose | Gw.wasm (symbols) | Gw.exe (stripped) |
| --- | --- | --- |
| Set a four-float material constant | `GrModelSetMaterialConstant` `ram:80171599` | wrapper `FUN_00645070` / `0x00645070` |
| Internal model constant map write | `CIGrModel::SetMaterialConstant` `ram:8016756b` | `FUN_006470c0` / `0x006470c0` |
| Resolve a material-constant ID by name | `GrMaterialConstantGetId` (calls `DdiShaderGetConstantId`) | wrapper `FUN_00664680` / `0x00664680` (`FUN_00664480(name, 1)`) |
| Item-icon material program | `CItemImageFrame::CreateIconMaterial` `ram:8114a556` | corresponding stripped routine |

`CreateIconMaterial` uses texture operation `7` and the material program global
`DAT_ram_020003e2`.  That program is created during `IMdlTexInitialize` with
the named constant `grConstColor`.  The EXE equivalent is the initialization
call at `FUN_00790100`:

```text
DAT_00f26f08 = FUN_006646b0(0, 0x68, &DAT_00a78580, 0xc,
                            &PTR_s_grConstColor_00bf7c08);
```

The public EXE wrapper is **cdecl** and takes `(HGrModel, submodel_index,
constant_id, Coord4f*)`; it resolves the `grmd` handle and then enters the
internal `__thiscall` map writer.  The constant ID must be obtained at runtime
from the material/shader constant registry; it must not be left at the
`UINT32_MAX` diagnostic sentinel or hard-coded across builds.  Writing values
such as `{1.5, 1.5, 1.5, 1.0}` is therefore a real shader-level experiment,
but only after both the ID and the icon model's material map are proven valid.

This was prototyped as an optional icon-only “pop” mode alongside the existing
ARGB retint.  The shader setter was tested only after the original
`OnFrameContentAdd` routine rebuilds the model, uses submodel `0`, and reports
the resolved constant ID/call count.  Static tracing proves the setter's ABI and
the exact icon construction order: `CreateIconMaterial` stores the material at
`this+0x28`, then `BuildIconModel` creates the icon `HGrModel` at `this+0x34`;
`OnFrameContentAdd` submits it afterward.  This makes `BuildIconModel` the
correct future timing candidate, not a late paint callback.  It still does not
prove that the inventory icon's texture material consumes `grConstColor`; the
known setter callers are world/effect model code, not `CItemImageFrame`.

Current safety status: the material-constant call is disabled again.  The
public wrapper is confirmed `__cdecl`, while only its internal map writer is
`__thiscall`.  The frame's `+0x34` icon model and valid constant-map state still
need to be proven at the earlier build point.  The stable direct model-colour
path remains enabled while that evidence is collected.

## Troubleshooting history and non-obvious findings

This section records the failed approaches so future changes do not repeat
them.

### Resolver and hook failures

* The first rarity-colour anchor was treated as a paint-function anchor and
  resolved to null after `to_function_start`; that optional resolver was
  disabled.  The anchor is not a separate paint routine.
* Ghidra showed the rarity-color code at `0x004da134` is inside
  `CItemImageFrame::OnFrameContentAdd` (`FUN_004d9fc0`).  Subtracting `0x174`
  therefore resolved the same function twice.
* Installing both the old paint hook and the content hook produced
  `MH_STATUS = 3` (`MH_ERROR_ALREADY_CREATED`).  There must be exactly one
  MinHook registration for this target.  The active resolver scans the
  content-function prologue directly and installs only that hook.

### Stable path

The working path is:

1. Resolve and hook `FUN_004d9fc0` once.
2. Call the original first so the game rebuilds `+0x2c` and `+0x34`.
3. Apply `GrModelSetColor` to the fresh background model at `this+0x2c`.
4. Optionally call the same color primitive on `this+0x34`; this is safe but
   does not prove that the icon's texture shader consumes the model color.

Model handles must never be cached across rebuilds.  The diagnostics
`paint_calls`, `model_hits`, `icon_model_hits`, `color_calls`, and
`icon_color_calls` show that this path executes; they do not guarantee that
the icon shader uses the written value.

### Brightness observations

Brightness currently multiplies each 8-bit RGB channel and clamps it to 255.
It cannot make an already saturated channel brighter:

* `0xFFFF00FF` is unchanged at every brightness above `1.0`.
* `0xFFCEFF00` reaches the same clamped value at approximately `1.24` and
  remains unchanged at `1.35` or `3.0`.
* White and neutral gray have no hue/saturation to amplify and may have poor
  contrast against the inventory background.

Test with a midrange, non-neutral color such as `#5080C0`, and rebuild/toggle
the inventory after changing the slider.  The slider only updates the value
used on the next content rebuild; it does not safely mutate already-submitted
GPU handles.  The test widget displays the computed channel-clamped ARGB value.

### Isolated border-model probe

The test widget now exposes **Border model probe (fixed magenta)**.  This is a
diagnostic-only switch, not a proposed final effect: after the original
content rebuild returns, it calls the already validated `GrModelSetColor` on
the live `CItemImageFrame +0x2c` model only when that frame has an explicit
tint rule, using `0xFFFF00FF`.  It does not use cached handles or affect
untinted inventory slots.
It does not touch alpha or material constants.  `border_probe_calls` counts
the successful model writes and `border_probe_enabled` reports the switch state.
The paint detour is intentionally not installed in the current stable build,
so a nonzero `paint_calls` counter alone does not mean the paint hook ran.

This creates the next safe test surface:

* if the selected tinted border turns unmistakably magenta, `+0x2c` is
  confirmed as the visible border model and the next RE target is its shared
  material from `CItemImageFrame::OnFrameClassInitialize` (`DAT_ram:005a9f14`);
* if the counter rises but the border does not change, the visible opacity is
  supplied by a later material/texture pass and we should trace that shared
  material rather than add more model-color calls.

No new offset was created for this probe.  It reuses the existing content hook.
Disable it and rebuild the inventory to restore the normal selected-item tint.

The constant-ID diagnostic now has its own safe offset as well:
`ui.gr_material_constant_get_id_func` uses the unique complete EXE wrapper at
`0x00664680` (`GrMaterialConstantGetId`, WASM `ram:802fb180`).  The native
module asks it for `grConstColor` during startup and retries after the first
live content rebuild, then reports the ID in diagnostics.  A
resolved ID is evidence that the engine registry knows the name; it is not
evidence that a particular item-frame material has an initialized constant
map.  The material setter therefore remains disabled until the border model's
map is proven separately.

### Shader/material experiment and crashes

The current evidence is sufficient to reject two earlier assumptions: the
shader setter is not a `__thiscall` export, and the last crash did not test a
valid constant ID.  The safe next experiment is therefore a diagnostic-only
resolution of `FUN_00664680("grConstColor")`, followed by a hook at
`BuildIconModel` if that ID resolves.  No material write should be enabled
until the diagnostic reports a real ID (not `0xFFFFFFFF`) and the model is
still between creation and `OnFrameContentAdd` submission.

Both candidate anchors are unique in the current EXE image: the
`BuildIconModel` prologue scans only at `0x004d8960`, and the
`GrMaterialConstantGetId` wrapper prologue scans only at `0x00664680`.

WASM/EXE analysis confirms the public wrapper and inner method have distinct
ABIs:

```cpp
using GrModelSetMaterialConstantFn = void(__cdecl*)(
    void* model, uint32_t submodel_index, uint32_t constant_id,
    const float* coord4f);
```

Two distinct failures were observed:

* The earlier cdecl crash interpretation was incorrect: `FUN_00645070` is the
  cdecl wrapper and explicitly moves the dereferenced model into `ECX` before
  calling `FUN_006470c0`.
* The subsequent test used the `UINT32_MAX` sentinel as the constant ID (the
  diagnostics showed `4294967295`), so it was not a valid `grConstColor`
  experiment.  A later `__thiscall` attempt reached `grint.h(164) Assertion:
  ptr`; that call was both ABI-wrong for the public wrapper and made after
  content submission.

The constant-ID resolver and setter are now resolved, but the write remains
strictly guarded.  A new offset, `ui.gr_model_set_material_constant_anchor`,
anchors the actual EXE wrapper tail and resolves the setter by `-0x63`.  The
content hook first validates the live border handle's `CIGrModel` map
read-only (`+0x9c/+0xa4`, submodel `+0x58/+0x60`, 0x14-byte entries) and only
updates an existing `grConstColor` entry.  Missing maps/IDs produce zero
writes; they never trigger allocation.  The setter call count is exposed as
`material_constant_calls`, and `border_material_map_valid` plus
`border_material_constant_count` explain why it did or did not run.

The root test script is intentionally single-purpose now:
`inventory_slot_tint_test.py` has one checkbox for the guarded border material
brightness experiment, one brightness slider, and the selected/hovered item
controls.  It disables the old alpha/icon/probe experiments while testing, so
any visual change is attributable to the material path.

### Diagnostic interpretation

The safe current state should report:

```text
hook_installed=True
content_hook_installed=True
color_calls > 0
icon_color_calls may be > 0
icon_constant_calls=0
material_constant_resolved=False
constant_id_resolved=False
```

`pop_enabled` and `shader_pop_enabled` are legacy icon/alpha flags and are
forced off by the current test script.  `material_pop_enabled` is the guarded
border-material gate; `material_constant_calls > 0` is the only evidence that
the shader constant setter actually ran.  A stack naming
`OnItemImageFrameContentAdd` with a `grint.h` assertion is a native handle/ABI
regression, not a Python item-ID or selector problem.

The first live material test resolved `material_constant_id=26` and
`material_setter_resolved=True`, but reported `border_material_map_valid=False`
and zero writes.  That result can mean the border model's constant array was
empty, not necessarily invalid: `CIGrModel::SetMaterialConstant` is designed
to allocate the first entry.  The guard now accepts an empty, structurally
valid map and lets the native setter initialize it; malformed model/submodel
layouts remain blocked.

### Safe retest checklist

1. Restart the client and reinject the rebuilt DLL; copying a new file does
   not replace an already-loaded DLL.  Deploy the matching `offsets/ui.json`
   beside that DLL as well: the native resolver loads JSON from the injected
   module's directory, not from this source checkout.  If the DLL is running
   from `F:\GW\GW1`, its `F:\GW\GW1\offsets\ui.json` must contain both
   `gr_material_constant_get_id_func` and the newly-created
   `gr_model_set_material_constant_anchor` entries.
2. Confirm `content_hook_installed=True` before applying a rule.
3. Test one item with an opaque midrange color, then toggle/reopen inventory.
4. Change brightness and rebuild again; compare the widget's effective ARGB
   readout and diagnostics.
5. Enable the single “border material brightness” checkbox, apply one item,
   close/reopen the inventory, and compare brightness 1.0 versus 4.0.  If
   `border_material_map_valid=False` or `material_constant_calls=0`, the
   material is not exposing `grConstColor` and the test has safely answered
   that target; do not infer a Python/item-ID failure.  If a new crash occurs,
   save the `*-gwtext.txt`, `*-stack.txt`, and diagnostics before retesting.
