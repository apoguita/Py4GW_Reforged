# Overlay 3D drawing — performance issues

Troubleshooting record, not a description of how the overlay works. Two problems found and
fixed, one still open.

Status: **paused**. The client freeze and the FindZ overhead are fixed and confirmed.
DXOverlay drawing being ~6x slower than ImGui is still unexplained — see `PF-5` in
`docs/pending_fixes.md`.

Covers work across both repos: `Py4GW_Reforged` (Python) and `Py4GW_Reforged_Native` (C++).

---

## 1. The original problem — SOLVED

**Symptom:** aC library scripts froze the client when drawing in the 3D world. Other
libraries drew fine.

**Cause:** `Py4GWCoreLib/DXOverlay.py` constructs a *new native* renderer on every
`DXOverlay()`. Under Reforged, any overlay whose `Draw*3D` is called appends to its own draw
list and lazily calls `GW::world_render::RegisterDraw([this]...)` — and `DXOverlay` has no
destructor, so that registration outlives the object. Code shaped like

```python
for i in range(len(points) - 1):
    DXOverlay().DrawLine3D(...)      # new native renderer per segment, per frame
```

registered one never-removed world-pass callback *per line per frame*, each holding a
dangling `this` that the render thread then invoked on every world pass.

**Why it was fine before:** legacy `Py2DRenderer::DrawLine3D`
(`C:\Users\Apo\Py4GW\src\py_2d_renderer.cpp:725`) drew immediately through a global device
and owned nothing. An instance was a shell, so building one per call cost an allocation and
nothing else. Reforged made an overlay a *resource*; the Python wrapper kept the legacy
habit.

**Fix:** every call site now holds one long-lived overlay. No shared class was changed for
this.

| File | Change |
|---|---|
| `Widgets/Automation/Bots/Runners/Outpostrunner v1.0.py` | module-level `dx_renderer` |
| `Py4GWCoreLib/botting_src/subclases_src/UI_src.py` | lazily cached `self._path_overlay` |
| `Sources/frenkeyLib/SulfurousRunner/ui.py` | module-level `path_overlay` |
| `navmesh_debug.py` | module-level `_path_overlay` |
| `Examples/autopathing-library test.py` | module-level `path_overlay` |
| `Legacy code and tests/Pathing/a-star-*.py` (5 files) | module-level `path_overlay` |
| `Legacy code and tests/Deprecated but working/Factions Leveler.py` | module-level |
| `Legacy code and tests/Deprecated but working/cupcake_mantainer.py` | class-level cache |

Nothing in the repo constructs an overlay per draw any more.

---

## 2. FindZ overhead — SOLVED

`Overlay::findZ` was the dominant cost behind heavy 3D drawing, for two reasons.

**a) The migration turned on a path legacy had disabled.** Legacy `findZ`
(`Py4GW\src\py_overlay.cpp:253`) did ONE `QueryZ` at the player's plane and had the
multi-plane version commented out; its binding exposed no `multi_plane` argument at all.
Reforged's `overlay_bindings.cpp:78` defaults `multi_plane=true`, which costs one altitude
query per floor layer. Every Python caller got it silently because `Py4GWCoreLib/Overlay.py`
passed only three args. **This default was left as-is** — multi-plane support is wanted.

**b) `autoz` was being dropped.** `Overlay.DrawPoly3D` accepted `autoz` and never forwarded
it; `DrawPolyFilled3D` had no such parameter. With it on, the native side resolves the ground
at **every segment vertex** (`overlay.cpp:904,924`), so a 24-segment marker did 24 `findZ`.
Both now forward it.

**Fix (built and confirmed by the user — "the overhead was removed"):** a result cache in
`Overlay::findZ` for the `multi_plane=true` path, in
`Py4GW_Reforged_Native/src/overlay/overlay.cpp`.

- key = `(x, y)` **truncated to whole units** (nearby points share an entry; ground height
  barely moves over one unit and the result only feeds overlay drawing)
- cleared when the map id changes — map geometry is fixed for the life of an instance
- covers **both** overlay surfaces, because `DXOverlay` holds an `Overlay` member and its 3D
  draws call the same `findZ`, including all the per-vertex ground snapping

Not cached: `multi_plane=false` (a single cheap query that depends on the player's plane),
`FindZBatch`, `FindZPlane`, the `GroundZ*` specialists. None are on the drawing hot path.

---

## 3. STILL OPEN — DirectX drawing is ~6× slower than ImGui

**Symptom:** BottingTree path drawing runs at 60 fps on the ImGui surface and **9 fps** on
DXOverlay. Measured with the toggles described in section 4.

**What has been ruled out, by test:**

- **Not occlusion.** Splitting the surface toggle from the occlusion toggle showed DirectX is
  slow *with occlusion off too*. The depth test is not the cost.
- **Not fill/rasterisation.** DirectX draws 1-pixel unantialiased lines; ImGui draws thick
  antialiased ones. Less pixel work, still 6× slower.
- **Not draw-call count.** A batching change (section 5) reduced submissions to ~4 per drain
  and did **not** fix it.

**The leading unmeasured suspect:** how many times the queue is replayed per frame.

`GW::world_render` runs its callbacks at DDI opcode **`0x1E`, not at present**
(`world_render.cpp:87`; the comment explains 0x0F/present is too late because depth is
already discarded). `0x1E` fires *multiple times per frame*. Every time it does,
`DXOverlay::OccludedTick` deep-copies the whole command list (`local = m_draw_list`, N
`std::function` copies, each heap-allocating) and **re-executes every command** — recomputing
lerps, calling `findZ`, rebuilding vertices — before the batched flush. Batching removed the
submissions but left all of that per-pass work in place.

60 → 9 fps is ~94 ms added per frame. With a few hundred commands, that is the right order
for a few dozen replays per frame.

### Next step (this is where work stopped)

Measure the replay multiplier. The dispatcher already counts it:

```python
import PyWorldRender
print(PyWorldRender.get_diagnostics())
```

Format (`world_render.cpp:434`):

```
installed=%d enabled=%d draw_op=0x%X dispatch=%u drawn=%u cbs=%u dev_ddi=0x%08X dev_gw=0x%08X shaders=%u
SCAN best_op=0x%X best_ratio(pass/total permil)=%u max_total=%u
op_pass(pass\total): 0x..=n/m ...
```

`drawn` = present count (frames), `cbs` = times callbacks were invoked (drains). Sample twice
a second or two apart while a path is drawing in DirectX mode; **`Δcbs / Δdrawn` is the
multiplier.**

- ratio ≈ 1 → the per-pass replay is not the cause; look elsewhere, and instrument rather
  than reason.
- ratio ≫ 1 → that is the whole problem. The fix is to build the vertex batch **once per
  frame** and only *submit* it on each pass, instead of re-running every command every time.

A small widget to print this live was requested but **not written** — that is the first
concrete task if this resumes.

---

## 4. BottingTree move-path drawing — current behaviour

`Py4GWCoreLib/botting_tree_src/ui.py`, options under "Draw Move Path Debug Options".

- **Draw with DirectX** (`draw_move_path_directx`, default off) — surface: ImGui vs DXOverlay
- **Use Occlusion (DirectX only)** (`draw_move_path_occluded`, default off) — passes
  `use_occlusion` to the DX calls

Geometry is identical in both DirectX modes, so the second checkbox changes only the depth
test. That is deliberate — it is what isolated occlusion as *not* the cause.

Other behaviour:

- **Lines hug the terrain** in both modes: each segment is subdivided every
  `_GROUND_SAMPLE_UNITS` (100) world units, capped at `_GROUND_SAMPLE_MAX_STEPS` (24), and the
  ground sampled at each step. Terrain-hugging is geometry and needs no occlusion — an
  important distinction that was conflated early on.
- **Player coords use `multi_plane=False`** — the player's own plane is authoritative, so no
  multi-plane search is needed. Route waypoints keep it on, their plane being unknown.
- **Occluded geometry is lifted** `_OCCLUDED_FLOOR_OFFSET` (15) units. Smaller z is UP, and
  `floor_offset` subtracts. Without it, geometry sitting exactly on the terrain is coplanar
  and z-fights, which on a thin line reads as *missing*. SulfurousRunner lifts by 50,
  Outpostrunner by 125.
- **DX markers are capped** at `_OCCLUDED_MARKER_LIMIT` (10) nearest waypoints, at
  `_OCCLUDED_MARKER_SEGMENTS` (8) segments, drawn as rings not filled discs. Beyond the cap
  they fall back to the batched ImGui marker. **Set `_OCCLUDED_MARKER_LIMIT = 0` to put all
  markers back on ImGui** — a one-line escape if DX mode misbehaves.
- Labels always stay on ImGui; DXOverlay has no text primitive.

These caps are workarounds for section 3. **Once that is solved they should all come out** —
unlimited markers at 24 segments, matching the ImGui look.

---

## 5. Native changes currently in the tree

`Py4GW_Reforged_Native`:

| File | Change | Status |
|---|---|---|
| `src/overlay/overlay.cpp` | `findZ` result cache (section 2) | **built, confirmed working** |
| `include/overlay/dx_overlay.h`, `src/overlay/dx_overlay.cpp` | 3D draw batching | **built, did NOT fix the perf problem** |

The batching change makes `DrawLine3D`, `DrawPoly3D` and `DrawPolyFilled3D` append vertices to
four buffers (lines/triangles × occluded/not) during a drain; `FlushBatches` then does
`Setup3DView` once and issues one `DrawPrimitiveUP` per non-empty group. It is correct and
strictly reduces submissions, but it did not recover the framerate, so **it is unvalidated as
a fix** — keep or revert as preferred. Nothing depends on it.

---

## 6. Attempted and REVERTED — do not redo from this document

All in `Py4GW_Reforged_Native`, all measured neutral or worse, all backed out:

1. **Shared DXOverlay draw list** — consolidating the list *and* the registration. Caused
   cross-producer thrash: `EnqueueDraw` clears the list on the first append after a pass, so a
   shared list lets whichever producer runs first wipe the others.
2. **Plane-list cache + single-plane fast path + 64×64 coverage grid + map-context hoist** —
   no perceivable improvement.
3. **Two-table, player-plane-aware findZ cache** — regression. The simple truncated-key cache
   that eventually worked is much smaller.
4. **Shared world-render registration with per-instance lists** — regression.

Lesson recorded: these were all reasoned about rather than measured, from an environment that
cannot build or profile the project. Measure first; ship one change per build; state exactly
what else is already live in that build.

---

## 7. Architecture facts worth keeping

Established by reading source during this work; several contradict reasonable assumptions.

- **Widget `main()` runs on the RENDER thread.** `python_runtime.cpp:262` `ExecuteDraw()`
  calls `draw()` and `main()`, and is invoked from `DrawLoop` (`Py4GW.cpp:345`). Only
  `update()` runs on the `Sleep(10)` loop. So the deferred draw queue is **not** a thread
  bridge — it exists only to move the draw into the world pass for depth.
- **ImGui and DXOverlay are opposite submission models.** `Overlay::DrawLine3D`
  (`overlay.cpp:729`) is `WorldToScreen` + `drawList->AddLine` — it appends to a CPU buffer
  that the backend submits once per frame. `DXOverlay::DrawLine3D` submits per primitive.
  Same DirectX device; the gap is batching, not the API.
- **`DrawPolyFilled3D` is one draw call per *triangle*** and `DrawPoly3D` one per ring
  sub-segment, so segment count is a direct draw-call multiplier.
- **`DrawPoly3D`/`DrawPolyFilled3D` call `findZ` per vertex regardless of `autoZ`** — `autoZ`
  only controls the centre z (`dx_overlay.cpp:1429` vs `1459-1461`).
- **`Py4GWCoreLib/DXOverlay.py` adds `+100` to centre z** in the poly wrappers. Smaller z is
  up, so that pushes the shape *down*. Looks like a migration bug; not investigated.
- **BottingTree draws through ImGui `Overlay`, not `DXOverlay`** by default. Any DXOverlay
  work is irrelevant to it unless the DirectX toggle is on.
