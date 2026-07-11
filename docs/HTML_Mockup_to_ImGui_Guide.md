# HTML Mockup → ImGui: Porting Guide

A practical guide for turning an approved **HTML mockup** into a working **Py4GW ImGui** UI,
plus the hard-won gotchas from the Launch Bar build. Read this before starting a new
mockup-driven feature; it will save you the same debugging loop.

Companion docs: `LaunchBar_ImGui_Implementation_Plan.md` (a worked example of the plan format),
and the binding stubs at `stubs/PyImGui.pyi` (useful but **not fully trustworthy** — see §4).

---

## 1. The workflow (why HTML first)

We design in HTML because it iterates in seconds (edit → refresh in a browser) and lets the
user *feel* the interaction before we spend time in the slow in-client loop. HTML is only ever
a **sketch to agree on behavior** — never the source of truth. The loop:

1. **Sketch** one small feature in a single self-contained HTML file; publish as an Artifact.
2. **Iterate** on the HTML with the user until the look/feel is approved. Keep the sketch
   *honest to what ImGui can actually do* (see §3) — don't promise CSS tricks we can't rebuild.
3. **Port** that feature to real ImGui in the Python layer.
4. **Verify** as much as possible offline (§5), then run in the injected client and iterate on
   what the user sees. Errors land in repo-root `runtime_log.txt`.
5. Move to the next feature. One feature at a time; get approval before moving on.

Keep the HTML mockup around — it is the behavior spec you port against.

---

## 2. Architecture pattern (model / host / manager / root)

Mirror this split for any non-trivial ImGui feature:

- **`model.py`** — pure data + geometry + rules. **No ImGui, no Py4GW imports.** Importable and
  unit-testable from a plain interpreter. All collision/layout/serialization lives here.
- **`host.py`** — renders one instance with ImGui; owns per-frame interaction state (drag,
  animation, hover). Imports `PyImGui`.
- **`manager.py`** — coordinates N instances + the settings/editor window; holds cross-instance
  UI state (selection, edit mode) and passes itself into each host's `draw`.
- **root `Feature.py`** — the launcher entry point. Passive on import; boots once; renders.

Keep the package's `__init__.py` importing **only the model** so the package stays importable
without ImGui (the offline test in §5 depends on this).

---

## 3. HTML/CSS → ImGui translation table

| HTML/CSS concept | ImGui (PyImGui) approach |
|---|---|
| A floating panel (`position: absolute; left/top`) | A window: `set_next_window_pos((x,y), ImGuiCond.Always)` + `set_next_window_size((w,h), Always)` + `begin(name, flags)` / `end()`. You own the position — recompute and re-set it every frame. |
| No title bar / chrome | `WindowFlags.NoTitleBar \| NoResize \| NoMove \| NoScrollbar \| NoScrollWithMouse \| NoCollapse \| NoSavedSettings \| NoFocusOnAppearing`. (`NoMove` because you position it yourself.) |
| `background: color` on the panel | `push_style_color(ImGuiCol.WindowBg, (r,g,b,a))`. Per-instance recolor = push your own color; leave the rest to the theme. |
| `opacity` (fade the whole panel) | `push_style_var(ImGuiStyleVar.Alpha, alpha)` around the window. **Not** `set_next_window_bg_alpha` — that only fades the background, not the widgets. Draw-list colors are *not* affected by the Alpha var — bake `alpha` into their `a` byte yourself. |
| `padding: 0` | `push_style_var_vec2(ImGuiStyleVar.WindowPadding, (0,0))`. |
| `border-radius` | `push_style_var(ImGuiStyleVar.WindowRounding, r)`; draw-list rects take a `rounding=` kwarg. |
| A button with hover/active states | `button(label, w, h)`; per-state colors via `push_style_color(ImGuiCol.Button / ButtonHovered / ButtonActive, ...)`. |
| An icon button / textured button | legacy `ImGui_Legacy.image_button(id, texture_path, w, h)` or draw-list `add_image(tex_id, p_min, p_max)`. |
| A clickable region with no visible chrome (drag handle, empty cell) | `invisible_button(str_id, (w, h))` — **size is a tuple**. Then read `is_item_active()` / `is_item_hovered()`. |
| Right-click context menu | `with`-free: after an item, `if begin_popup_context_item(id): ... menu_item(...) ; end_popup()`. Right-click is handled for free. |
| Drawing grid lines / outlines / overlays (CSS borders, dashed cells) | draw list: `dl = get_window_draw_list()`; `dl.add_rect(p_min, p_max, col, rounding=, thickness=)`, `add_rect_filled(..., rounding=)`, `add_line`, `add_circle_filled`. Colors are packed **u32** `IM_COL32` (`r \| g<<8 \| b<<16 \| a<<24`). |
| Dragging an element by the mouse | On the handle item: `if is_item_active() and is_mouse_dragging(0, threshold): dx,dy = get_mouse_drag_delta(0, threshold)`; add to a stored press-anchor. Distinguish a click from a drag with a movement threshold + an `is_item_active` press/release edge (see §6). |
| Sliders / number inputs / color pickers | `slider_float(label, v, lo, hi)`, `slider_int(...)`, `input_int(label, v)`, `color_edit3(label, (r,g,b))` — all return the (possibly changed) value. |
| Unique element identity (React keys, DOM ids) | Every interactive item needs a **unique ImGui ID**. Append `##<stable-unique-suffix>` to the label (e.g. `"2x2##tile_%s_%s" % (bar_id, tile_id)`). Empty/duplicate labels collide. |
| CSS transitions / animation | No CSS. Drive values from frame time yourself (a tiny ease-out tween keyed by a monotonic ms clock from `PySystem.get_tick_count64()`), or use the bound `PyImGui.anim.tween_float` (OutCubic). Animate a single 0→1 progress and derive positions/sizes from it. |
| `overflow: hidden` clipping to a box | draw-list `push_clip_rect(min, max, intersect=True)` / `pop_clip_rect`, or a child window. |

---

## 4. Gotchas (the expensive ones)

**The stubs are NOT 100% faithful to the compiled binding.** `stubs/PyImGui.pyi` is a forward
declaration and has been wrong about argument order. When an optional-arg call fails at runtime,
**pass those args by keyword** — it is immune to ordering.
- Example that bit us: `DrawList.add_rect` — real order is `(p_min, p_max, col, rounding,
  thickness, flags)`, the stub listed `(rounding, flags, thickness)`. Fix: `add_rect(a, b, col,
  rounding=2.0, thickness=1.0)`.

**The launcher calls BOTH `main()` and `draw()` if both are defined** → everything renders twice
per frame → ImGui **ID-conflict** warnings and **doubled** UI. Expose **exactly one** entry point.

**`invisible_button` takes a size *tuple***: `invisible_button(str_id, (w, h))`, not `(w, h)`.

**Idle fade:** `set_next_window_bg_alpha` only fades the background. To fade the whole panel
(bg + widgets + text) use `push_style_var(ImGuiStyleVar.Alpha, alpha)`. Draw-list primitives
ignore it — multiply their alpha byte manually.

**Collapsing a window leaves a background "stub"** because the default `WindowMinSize` (~32×32)
won't let it shrink smaller. Push it down: `push_style_var_vec2(ImGuiStyleVar.WindowMinSize,
(1,1))`. (Note: `set_next_window_size_constraints((1,1), …)` did **not** override this floor in
our build — the style var did.)

**Keeping a fixed edge while resizing (e.g. collapse toward a strip):** you set both pos and
size every frame, so anchor by the fixed edge. Store the anchored-edge coordinates; each frame
compute the window top-left from `anchor` and the current size (`topleft.x = anchor.x - width`
when anchored on the right; `- height` when anchored on the bottom). This removes any position
compensation and there is no jump.

**Dataclasses + `from __future__ import annotations`** can crash under the launcher's synthetic
`<string>` module / isolated loading (`sys.modules.get(cls.__module__)` is `None`). Use ordinary
runtime-resolvable annotations in model modules; don't add the future import.

**ID uniqueness:** `label##suffix` hashes the whole string for the ID. Make the suffix stable and
unique (instance id + item id). In loops, either suffix per iteration or `push_id`/`pop_id`.

**Font scaling (ImGui 1.92):** `set_window_font_scale` is a no-op; use `push_font_scaled(font,
scale)` (or the legacy `ImGui_Legacy.push_font(family, px)`), or `FontScaleMain`. Verify live.

**Everything is `base × scale`.** Never hard-code pixel sizes; store base values in settings and
multiply by a scale factor each frame (cells, gaps, padding, strip, fonts).

---

## 5. Verification recipe (before the live run)

Do all three, in order — they catch progressively more without the game:

1. **Model unit test (offline).** The model has no ImGui import, so exercise its geometry and
   rules from a plain interpreter (load the file in isolation via `importlib` to skip the heavy
   `Py4GWCoreLib` facade; register it in `sys.modules` so dataclass annotation resolution works).

2. **Signature check against the stub.** `grep` `stubs/PyImGui.pyi` for every function/enum you
   call; confirm arg shapes and enum member names. Treat it as a hint, not gospel (§4) — prefer
   keyword args for optional params.

3. **Mock-`PyImGui` execution (offline).** Inject a fake `PyImGui` module into `sys.modules`
   whose functions mirror the stub signatures and return neutral values (windows open, no
   clicks/hover). Load `host`/`manager` under a synthetic package and run `draw()` for several
   frames — in edit mode, all orientations, a collapse, add/remove, the confirm dialog. This
   catches missing attributes, wrong arg counts, and — crucially — **style push/pop imbalance**
   (assert the pushed color/var stacks return to zero; an imbalance is a classic ImGui crash).

Then run in the client and iterate on `runtime_log.txt` errors one at a time.

---

## 6. Reusable snippets

**Color helpers** (mockups use `#rrggbb`; ImGui wants float RGBA or packed u32):
```python
def _parse_hex(v):            # "#rrggbb" -> (r,g,b) 0..255
    h = v.lstrip("#"); return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
def _hex_rgba01(v, a=1.0):    # -> (r,g,b,a) 0..1  for push_style_color
    r,g,b = _parse_hex(v); return (r/255, g/255, b/255, a)
def _hex_u32(v, a=255):       # -> IM_COL32 int  for draw-list
    r,g,b = _parse_hex(v); return (a<<24)|(b<<16)|(g<<8)|r
def _lighten(v, amt):         # derived shades (hover/collapsed/border)
    r,g,b = _parse_hex(v)
    return "#%02x%02x%02x" % (int(r+(255-r)*amt), int(g+(255-g)*amt), int(b+(255-b)*amt))
```

**Click vs. drag on a handle** (a click collapses; a drag moves — both from one item):
```python
PyImGui.invisible_button("##handle_%s" % obj.id, (w, h))
active = PyImGui.is_item_active()
if active and not self._was_active:                 # press edge
    self._pressed, self._moved = True, False
    self._press = (obj.x, obj.y)
if active and PyImGui.is_mouse_dragging(0, 4.0):    # drag past threshold
    dx, dy = PyImGui.get_mouse_drag_delta(0, 4.0)
    obj.x, obj.y = self._press[0] + dx, self._press[1] + dy
    self._moved = True
if self._was_active and not active:                 # release edge
    if self._pressed and not self._moved:
        toggle_collapse()
    self._pressed = False
self._was_active = active
```

**Idle fade that restores on hover** (uses last frame's hover to avoid a begin() chicken-egg):
```python
full = self._hovered_prev or self._pressed or editing
self._alpha.set_target(1.0 if full else obj.idle_opacity, now_ms)
alpha = self._alpha.update(now_ms)
PyImGui.push_style_var(PyImGui.ImGuiStyleVar.Alpha, alpha)   # ... begin window ...
# inside: self._hovered_prev = PyImGui.is_window_hovered()
```

**Right-click menu on an item:**
```python
PyImGui.button("Label##%s" % item_id, w, h)
if PyImGui.begin_popup_context_item("##menu_%s" % item_id):
    if PyImGui.menu_item("Do a thing"): do_thing()
    PyImGui.end_popup()
```

---

## 7. Checklist for a new mockup-driven feature

- [ ] HTML sketch approved (behavior spec).
- [ ] Model module written, no ImGui import, offline unit test passing.
- [ ] Host/manager written; every interactive item has a unique `##suffix`.
- [ ] All sizes are `base × scale`; colors pushed per-instance, theme untouched otherwise.
- [ ] Signatures checked vs stub; optional draw-list args passed by keyword.
- [ ] Mock-`PyImGui` run passes with balanced style stacks.
- [ ] Exactly one launcher entry point (`main()` **or** `draw()`, not both).
- [ ] Live run; iterate on `runtime_log.txt`; confirm look/feel vs the mockup with the user.
