# Launch Bar — ImGui Implementation Plan

Status: **planning — not yet implemented.** This document consolidates the locked UI
design (agreed via HTML sketches) and the concrete plan to build it in real ImGui in the
**Python layer** of `Py4GW_Reforged`. Execution bindings (what a button *does*) are
explicitly **out of scope** for this pass — this is UI/layout only.

This is a new, from-scratch project that replaces the disliked UI of `LaunchSurface.py`.
The old model layer (registry/layout/persistence) is not reused verbatim; we start clean but
keep the same good separation of *model* vs *host*.

---

## 1. Scope

**In scope (this pass):**
- One or more independent floating "launch bars" (launchpads) rendered as ImGui windows.
- A left/right/top/bottom **drag strip** (custom "title bar") that moves the window and
  click-collapses it toward its own edge.
- Idle **fade** (semi-transparent when not hovered) that restores to full on hover/drag.
- A **slot grid** per bar; tiles occupy arbitrary `W×H` slots (buttons and widgets are the
  same thing: a tile with a span).
- **Edit mode** showing slot divisions; normal mode hides them + fades.
- **Add / move / resize / delete** tiles — both direct-on-bar gestures and a settings UI,
  plus **right-click context menus** (ImGui makes this cheap).
- **Multi-bar management**: add / remove (with confirm) / select / per-bar edit.
- **Per-bar recoloring** of three surfaces only: background, drag bar, button face.
- **Global scale** per bar; every size derives from `base × scale`.

**Out of scope (later passes):**
- What a tile executes (widget-catalog launch, hand-crafted metadata calls). Tiles render as
  labeled placeholders for now.
- Tile icons/textures/labels beyond a placeholder (a follow-up pass).
- Persistence format finalization (see §9 — planned, but a stub is acceptable this pass).
- In-game context (map/party/combat projections), portals, clusters, presets.

**Not our job:** the **theme system**. The base look (borders, hover/active accents, fonts,
rounding) is owned by the existing `Style`/`StyleTheme`. We only push the **three per-bar
color overrides** on top of the active theme.

---

## 2. Source of truth for behavior

The approved interaction model is the locked HTML sketch (published artifact
"Launch Bar — …"). The concrete, agreed behaviors:

| Behavior | Locked decision |
|---|---|
| Container | Borderless window; narrow vertical/horizontal **strip** = drag handle ("title bar") |
| Handle side | Configurable L / R / T / B; strip auto-orients |
| Move | Drag the strip; instant (no easing) |
| Collapse | **Click** strip (no drag) folds window to just the strip; strip color goes a lighter shade |
| Collapse anchor | Window is anchored by the **strip's own edge** so collapse only shrinks content — the strip never moves; strip is inert during the fold animation |
| Idle fade | Not-edit → window at "idle opacity"; **hover or drag restores 100%** |
| Slots | Square cells; tiles span arbitrary `W×H`; grid size **uncapped** (e.g. 20×20) |
| Edit mode | Shows slot divisions + full opacity; normal mode hides divisions + fades |
| Add | Free-form: pick `W×H` (in slots), drop into first free block; or click an empty slot |
| Select | Click a tile |
| Move (grid) | Drag tile; snap to slots; green = fits / red = blocked/out-of-bounds; collision-checked |
| Resize | Per-tile `W`/`H` steppers (collision-checked) |
| Delete | ✕ on selected tile, Delete/Backspace key, or panel Remove |
| Multi-bar | Add / select / per-bar Edit; delete asks to **confirm (modal)** |
| Colors (per bar) | Background, Drag bar, Button face — override theme; collapsed shade + tile border derived |
| Scale | Per-bar `base × scale`; cell/gap/idle-opacity are settings (base values) |

ImGui adds one thing the HTML couldn't: **right-click context menus** on the bar and on
tiles, which become the primary fast path for add/remove/resize (the settings panel remains
for discoverability).

---

## 3. Toolkit — confirmed Python primitives

All confirmed present (see scan notes). Facade = `from Py4GWCoreLib.ImGui import ImGui`;
raw = `import PyImGui`; legacy = `from Py4GWCoreLib import ImGui_Legacy`.

**Windows / floating chrome**
- `with ImGui.window(name, flags=...) as w:` — `w.entered`, `w.draw` (window draw list),
  `w.pos`, `w.size`, `w.is_hovered`.
- Flags (`PyImGui.WindowFlags`): `NoTitleBar | NoResize | NoScrollbar | NoScrollWithMouse |
  NoCollapse | NoSavedSettings | NoBackground | NoFocusOnAppearing` (+ `NoMouseInputs` for a
  passthrough canvas). Docking is **opt-in** (`Docking = 1<<30`); default is non-dockable —
  so no `NoDocking` needed.
- (`set_next_window_detached(...)` exists for tear-off viewport windows, but per decision §11
  we use **plain in-window floating windows**, not detached.)
- **StyleConfig** (native-bound project theme container) + live `get_style()` with per-index
  `get_color`/`set_color` and `ScaleAllSizes` — the system theme. We read/inherit it; we push
  only our 3 per-bar overrides on top.
- `PyImGui.set_next_window_pos(pos, ImGuiCond.Always)`, `set_next_window_size(size, Always)`,
  `set_next_window_bg_alpha(alpha)`, `get_window_pos/size`.

**Drag / mouse**
- `is_window_hovered()`, `is_mouse_dragging(0)`, `get_mouse_drag_delta(0)`,
  `reset_mouse_drag_delta(0)`, `is_mouse_released(0)`, `get_mouse_pos`,
  `is_item_active/hovered/clicked(btn)` (btn 1 = right).

**Right-click menus**
- `with ImGui.popup_context_item(id):` / `popup_context_window(id):` (right-click handled
  for free) + `ImGui.menu_item(...)`; programmatic: `ImGui.open_popup(id)` + `with
  ImGui.popup(id):`.

**Draw list** (slot lines, drop-target rects, tile faces)
- Window scope: `w.draw`; overlays: `ImGui.fg_draw`. Methods: `add_rect_filled(p_min, p_max,
  u32, rounding, flags)`, `add_rect(...)`, `add_line(...)`, `add_text(pos, u32, str)`,
  `add_image(tex_id, ...)`. Colors are packed u32 (`ImGui.color_convert_float4_to_u32`).

**Per-bar recolor (only 3 surfaces)**
- `with ImGui.style.color(PyImGui.ImGuiCol.WindowBg, rgba):` for background.
- Strip + tile faces: draw with the drag/face colors directly via draw list (or push
  `Button`/`ChildBg` around tile widgets). Collapsed-strip shade + tile border are derived
  (lighten) in code.
- `with ImGui.style.var(PyImGui.ImGuiStyleVar.WindowPadding, (x,y)):` etc. as needed.
- Everything else inherits the active theme — we push nothing else.

**Scale / fonts**
- All px = `base * scale`. Fonts: legacy `ImGui.push_font("Bold"|"Regular", px)` /
  `ImGui.pop_font()` (auto-uses `push_font_scaled` for non-baked sizes), or raw
  `PyImGui.push_font_scaled(ImguiFonts.Regular_14.value, scale)`.

---

## 4. Addons / animation (native scan — DONE)

Backend is **ImGui 1.92.9 WIP, docking + multi-viewport branch, DX9**
(`Py4GW_Reforged_Native\third_party\imgui\imgui.h`). Docking is enabled by default;
viewports are runtime-toggleable.

**Vendored addons** (`third_party\imgui\addons\`), and their Python reachability:
- **ImAnim** (animation/easing/tween) → submodule **`PyImGui.anim`**, **partially bound**:
  `update_begin_frame()`, `gc()`, `set/get_global_time_scale()`, **`tween_float(...)`**,
  `oscillate(...)`, enum `Ease` (**only** Linear / InCubic / OutCubic / InOutCubic),
  `Policy` (Crossfade/Cut/Queue). Vec2/vec4/color tweens, spring/back/elastic/bezier,
  shake, scroll-to, and ~30 easings exist in C++ but are **not** bound.
- **ImHotKey** → `PyImGui.hotkey` (chorded shortcut editor) — relevant to a *later*
  shortcuts phase, not this pass.
- **imgui-filebrowser** → `PyImGui.filebrowser` — useful later for an icon/texture picker.
- **imgui_markdown** → `PyImGui.markdown.render(text)`; **imgui_club** memory editor
  → `PyImGui.memory_editor`. Not needed here.
- No implot / node-editor / ImGuizmo / knobs / toggle / spinner addons exist.

**Decision — animation:** use **`PyImGui.anim.tween_float`** with **OutCubic** for the two
animations we actually need — idle-fade **alpha** and collapse **progress (0→1)** — since
both are single scalars and we derive positions/sizes/anchor from the progress float. Call
`PyImGui.anim.update_begin_frame()` once per frame; `gc()` periodically. This avoids building
a custom tween and avoids needing the unbound vec/color variants. Animations must remain
**optional** (correct UI with them disabled). If we later want spring/elastic or vec/color
tweens, extend `bindings\addons.cpp::register_anim` in the Native project (out of scope now).

**Theming:** the project ships a bound **`StyleConfig`** style container + live `get_style()`
(`bindings\style.cpp`) — this is the "theming handled by the system." We do **not** touch it
beyond pushing our **three per-bar color overrides** (§?, background/drag/face) as scoped
`push_style_color` / draw-list colors on top of it.

**Font scaling caveat (1.92):** `set_window_font_scale` is a no-op stub in this build; the new
model uses `ImGuiStyle.FontScaleMain` / `FontScaleDpi` / `FontSizeBase`. `push_font_scaled`
is present in the Python stub — **verify live** which path actually scales tile-label text,
and standardize on it (likely `push_font_scaled` via the legacy `ImGui.push_font(family, px)`
helper, else drive `FontScaleMain`).

---

## 5. Architecture & module layout

Mirror the good `LaunchSurface` split (model testable without ImGui; host owns rendering),
but clean and scoped to the launch bar. Proposed package (project-owned, **not** under a
`.widget` discovery root):

```
LaunchBar.py                      # root entry: main() frame callback; builds manager + hosts
Py4GWCoreLib/py4gwcorelib_src/launch_bar/   # (if it grows beyond the root file)
    __init__.py
    model.py        # LaunchBarModel, Tile, grid math, occupancy/collision, colors, scale
    settings.py     # LaunchBarSettings — compose Settings; per-bar namespace serialize
    tween.py        # frame-time tween helper (or thin wrapper over a native addon)
    host.py         # LaunchBarHost — one ImGui host per bar (window, strip, grid, tiles)
    manager.py      # LaunchBarManager — N bars, add/remove/select, shared settings panel
    editor.py       # settings/editor window + right-click context menus
```

- **Model has no ImGui import.** Pure data + geometry: `columns, rows, base_cell, base_gap,
  base_pad, base_strip, scale, idle_opacity, side, colors{bg,drag,face}, pos, collapsed,
  tiles[]`. Grid/occupancy/collision (`can_place`, `first_free_block`) live here.
- **Host** renders exactly one bar's model; owns per-frame interaction (drag, collapse,
  edit gestures, right-click menus, draw-list grid).
- **Manager** owns the list of bars + the settings/editor window; routes "which bar is
  selected/editing"; add/remove with confirm.
- **Entry point** `LaunchBar.py` exposes `main()` (idempotent, launcher-invoked per frame),
  passive on import (no top-level execution — matches widget-shape rule).

---

## 6. Data model (per bar)

```
Tile      = { id, col, row, w, h }                      # kind/action added later
LaunchBar = {
  id, name, side ∈ {left,right,top,bottom},
  columns, rows,                                         # uncapped, min 1
  base_cell, base_gap, base_pad, base_strip,             # px base values (settings)
  scale, idle_opacity,
  colors = { bg, drag, face },                           # the only 3 overrides
  pos = anchored by strip edge (see §7), collapsed: bool,
  tiles: [Tile...]
}
```

Geometry helpers (model): `content_w/h = pad*2 + n*cell + (n-1)*gap` (× scale),
`tile_rect(t)`, `cells_of(t)`, `occupied(except_id)`, `can_place(t, c, r)`,
`first_free_block(w, h)`.

---

## 7. Rendering & interaction mapping

Each bar = **one ImGui window** (`NoTitleBar | NoResize | NoScrollbar | NoScrollWithMouse |
NoCollapse | NoSavedSettings`; `NoBackground` + manual bg draw, or `WindowBg` style + bg
alpha). Layout inside is computed by the model; we place widgets/draw at absolute cursor
positions.

| Locked behavior | ImGui implementation |
|---|---|
| Strip (drag handle) | An `invisible_button`/hovered region on the strip rect; `is_item_active()` + `is_mouse_dragging(0)` → move; a click with no drag → toggle collapse |
| Move window | Accumulate `get_mouse_drag_delta(0)` into stored pos; `set_next_window_pos(pos, Always)`; `reset_mouse_drag_delta` on release. Instant (no easing) |
| Collapse anchor | Store pos as the **strip-edge anchor**; window origin computed so the strip rect is invariant while content size animates → no jump |
| Strip inert during fold | Model `animating` flag (tween in progress) gates strip click/drag |
| Idle fade | `set_next_window_bg_alpha(full if is_window_hovered() or dragging else idle)`; tween the alpha |
| Slot grid (edit) | `w.draw.add_rect` per cell (dashed look = short segments or thin rects); only in edit mode |
| Empty-slot "+" add | Hover a slot rect → draw "+"; left-click empty slot → add 1×1; **right-click** → context menu (Add W×H…) |
| Tile | `image_button`/`button` (placeholder now) at the tile rect, sized `w×h` cells; face color from `colors.face` |
| Select tile | Click tile → `selected_tile_id` |
| Move tile (grid) | Drag tile in edit mode; compute snapped target cell from mouse; draw drop-target rect (green/red via `can_place`); commit on release |
| Resize / delete | Right-click tile → menu (Width ±, Height ±, Remove); also panel steppers; Delete key |
| Per-bar color | `with ImGui.style.color(WindowBg, bg)`; strip + tile faces drawn/pushed with `drag`/`face`; derived shades in code |
| Scale | All rects/fonts `× scale`; fonts via `push_font_scaled` |
| Right-click editing (new) | `with ImGui.popup_context_window(bar_id):` for bar-level (Add tile, Edit mode, Colors…); `with ImGui.popup_context_item(tile_id):` for tile-level (Resize, Remove) |

Editor/settings window (manager-owned): the bar list (add/remove/select/edit), and the
selected bar's settings (side, scale, cell, gap, idle opacity, columns, rows, 3 colors) +
tile list/inspector — mirrors the locked HTML panel. Delete-bar goes through a confirm
popup (`ImGui.popup_modal`).

---

## 8. Multi-bar

`LaunchBarManager` holds `bars[]`, `selected_id`, `editing_id`. Renders each bar's host each
frame, plus the settings window. Add spawns a bar with default settings at an offset;
remove requires modal confirm; only the `editing_id` bar shows divisions and accepts
edit gestures.

---

## 9. Persistence (planned, light this pass)

Per-bar namespace in the composed `Settings` document (one section per bar id), JSON for
tiles/colors. UI-only pass may keep bars in memory with a stub save; full serialization
(schema version, safe fallback) is a fast follow. No new settings subsystem — compose the
existing `Settings`.

---

## 10. Build phases (checklist)

1. **Model** — data + geometry + occupancy/collision; no ImGui. (unit-checkable)
2. **Single host** — one bar: window + strip + drag + collapse (edge-anchored) + idle fade.
3. **Slot grid + tiles** — draw grid in edit mode; render placeholder tiles at rects; scale.
4. **Edit gestures** — add (empty slot / free-form), select, drag-move (drop preview),
   delete; keyboard delete.
5. **Right-click menus** — bar-level and tile-level context menus for the above.
6. **Per-bar recolor** — the three color overrides + derived shades.
7. **Manager + settings window** — multi-bar list, per-bar settings, tile inspector, confirm modal.
8. **Tween** — collapse/fade/flash animations (or native addon if available).
9. **Persistence** — per-bar settings namespace.

Each phase is verified live in the injected client and iterated, per the project's
sketch→approve→ImGui→iterate workflow.

---

## 10a. Widget launching, browser, and binding (added)

The launch bar replaces the widget-manager **UI only**; it consumes the neutral runtime
`WidgetHandler` (`get_widget_handler()` in `Py4GWCoreLib/py4gwcorelib_src/WidgetManager.py`) +
`WidgetCatalog` metadata. A **future "main toolbar"** owns widget discovery + callback
bootstrap — out of scope here; our UI only needs *enumerate metadata* + *toggle*. Do not depend
on the manager UI modules being replaced (`Py4GW_widget_manager.py`,
`Widgets/WidgetCatalog/Py4GW_widget_catalog.py`, `Py4GWLibrary`).

**Runtime adapter (narrow surface, mirrors old `LaunchSurface.WidgetRuntimePort`):**
`get_widget_info(full_id) -> Widget`; `w.enabled`; `handler.enable_widget(w.plain_name)`;
`handler._request_disable_widget(w)` (System-safe); `handler.set_widget_configuring(w.plain_name, v)`.
Enumerate via `handler.widgets` (or `WidgetCatalog.snapshot_from_widgets`). Per-widget metadata:
`folder_script_name` (id), `name`, `image` (icon path), `category`, `tags`, `enabled`,
`has_configure_property`, `tooltip()` callable. Enabling a widget starts it (C++ `PyCallback`);
no widget loop needed. Favorites persist to `Favorites/favorites` (comma list of ids) under the
manager INI key — shared with the old UIs.

**Widget tile:** a `Tile` may bind a widget (`widget_id`). It renders the widget's **icon**
(`image_button` with `image` path) + hover **tooltip** (`tooltip()` or synthesized), toggles the
widget on **click in normal mode** (edit mode still moves/resizes), and shows an **active
indicator** when the widget is enabled.

**Active indicator (per bar, customizable):** an `active_color` plus two independent style
toggles — **outline** (a colored inset border + glow) and **mask** (a translucent color overlay);
either, both, or neither. Configured in the Colors section.

**Widget browser (the WM replacement, toned down):** a Windows-Explorer two-pane window —
left = search + virtual **buckets** (All / Active / Favorites / Inactive) + a **folder tree**
(folders = `widget_path`; a folder may hold **both** widgets and subfolders); right = the
selected node's **subfolders and its own widgets**. Address bar with **back / forward / up** +
clickable **breadcrumb** (selection history). Each widget row: icon · name · status dot ·
★ favorite · ⚙ configure, and click-to-toggle. Kept toned down (plain rows + collapsible
folders, no per-frame snapshot/tree rebuild, no custom-drawn gradient rows or per-frame text
measuring) — the current WM UIs are heavy there. The browser is a **non-deletable button** on
the main toolbar.

**Binding — approach A only (browser is the single picker):**
1. **Pin to toolbar** — a widget row's action (or right-click) pins it as a button on the
   *selected* launchpad.
2. **Assign widget…** — an unbound/empty tile's action opens the browser in **pick mode**
   (a "Pick a widget for this button" banner); clicking a widget binds it and returns to normal.
Approach B (inline mini-picker in the tile inspector) was **dropped** — the browser already has
search, so a second picker is redundant.

## 11. Open decisions

Resolved:
- **Animation source** → **ImAnim** via `PyImGui.anim.tween_float` (OutCubic); no custom
  tween, no binding extension. (§4)
- **Theming** → inherit `StyleConfig`; push only the 3 per-bar overrides. (§4)
- **Mouse passthrough** → **YES.** Each bar is its own interactive window sized to its grid,
  so screen areas **outside** any bar pass mouse through to the game automatically (no window
  there). The bar's own footprint (the faded panel, including empty cells) is a normal toolbar
  and consumes input over itself. (If per-empty-cell passthrough is ever wanted, fall back to
  the old NoMouseInputs-canvas + per-tile-window scheme — not needed now.)
- **Detached viewports** → **NO.** Bars are plain in-window floating windows (not
  `set_next_window_detached`), clamped to the game window.
- **Entry point** → **root `LaunchBar.py`** exposing `main()`/`draw()` (passive on import,
  launcher-invoked per frame). Not a `.widget`.

Still to confirm at coding:
- **Font scaling path**: `push_font_scaled` vs `FontScaleMain` (1.92) — pick after a live test.
```
