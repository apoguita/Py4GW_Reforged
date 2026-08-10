# Map Overlay Merge — Analysis (Context Phase)

> Status: **context / analysis phase**. No code has been changed. This document captures
> what the two existing widgets do, how they differ, what each does better, and the agreed
> direction for a merged solution. Design details live in `feature-inventory.md` (the
> union of features that must survive) and will grow into a design doc next.

## The two widgets

Both are the **same widget** — an agent + feature overlay painted on top of a Guild Wars UI
frame — implemented twice by two different authors in two different paradigms.

| | Compass + | Mission Map + |
|---|---|---|
| File | `Widgets/Guild Wars/Screen Overlays/Compass +.py` | `Widgets/Guild Wars/Screen Overlays/Mission Map +.py` |
| Size | ~960 lines | ~2115 lines |
| Author(s) | jtmele1 / frenkey (contrib: Apo, RyanNuttall) | Apo (contrib: Searinox, Dharmantrix, aC) |
| Target frame | Compass / minimap frame | Mission-map frame |
| **Rotates?** | **Yes** — follows camera yaw (or north-lock) | **No** — pans/zooms only |
| Projection used | `Map.MiniMap.MapProjection.*` (rotation-aware, native) | Hand-inlined copy of `Map.MissionMap.MapProjection` math |

**Rotation is the only fundamental behavioral difference.** Everything else — markers, rings,
spirit auras, click-to-target, terrain/pathing render, config — is the same job done twice.

## The shared spine (duplicated in intent, divergent in code)

1. **Shape drawing.** Both draw Circle / Tear / Square / etc. markers.
   - Compass: inline `if/elif` on a shape string inside `DrawAgent` (`Compass +.py:378`),
     rotation folded in per-shape via `cos/sin`.
   - Mission Map: OO `Shape` hierarchy + registry (`Mission Map +.py:490`–`797`) —
     `Triangle, Circle, Teardrop, Square, Penta, Tear, SignPost, Lock, Scale` — plus a
     shape-instance cache (`DrawMarkerCached`) and a color→int cache (`ColorToIntCached`).

2. **Agent iteration + classification.** Both walk the same `AgentArray.Get*Array()` sets
   (gadget, spirit/pet, neutral, minion, enemy, ally, npc/minipet, player, item) and pick a
   marker per agent kind. The decision logic (spirit detection, boss glow, item rarity,
   NPC vs minipet, chest vs gadget) is duplicated with variations.
   - Compass: `DrawAgents` (`Compass +.py:464`).
   - Mission Map: `DrawFrame` (`Mission Map +.py:1500`).

3. **Per-agent data read.** *Key quality divergence.*
   - Compass makes **many wrapper calls per agent per frame** — `Agent.GetXY`, `IsLiving`,
     `GetPlayerNumber`, `IsAlive`, `GetRotationAngle`, `HasBossGlow`… each a binding
     round-trip, sometimes calling `Agent.GetXY`/`Player.GetAgentID` more than once.
   - Mission Map reads the **struct once** via `Agent.GetAgentByID(id)` →
     `obj.GetAsAgentLiving()` and touches fields directly (`living.hp`, `living.is_dead`,
     `living.player_number`, `obj.rotation_angle`, `obj.pos.x`). This is the correct
     Reforged-native (context-path) pattern.

4. **Config model + persistence.**
   - Compass: `Marker` + `Ring` (`Compass +.py:18`,`32`), dict-keyed; manual
     `LoadConfig`/`SaveConfig` with explicit `ini.set()` per field and a **Save button**;
     scope `"global"`.
   - Mission Map: `ConfigItem` + `Config`/`GLOBAL_CONFIGS` (`Mission Map +.py:803`–`899`),
     grouped (Party/Hostile/World/Spirits); **auto-write on change** through `Settings`;
     scope `"account"`. (Matches current house style — see `inimanager-settings-migration`,
     `settings-self-throttled`.)

5. **Projection.** Same transform family. Compass calls the native rotation-aware
   `Map.MiniMap.MapProjection.GamePosToScreen` (`Map.py:1702`). Mission Map re-inlines the
   axis-aligned `Map.MissionMap.MapProjection` math as `RawGamePosToScreen` /
   `RawScreenToRawGamePos` / `RawGwinchToPixels` (`Mission Map +.py:162`–`238`), fetching the
   transform params (pan/scale/zoom/center/bounds) **once per frame** and caching boundaries
   per map-id. The inlined copy is a perf win but risks silent drift from the library math.

6. **Rings / aggro / spirit auras.** Both draw range circles.
   - Compass: a configurable `Ring` list + editor (Touch…Compass), plus spirit-range fills.
   - Mission Map: hardcoded aggro bubble + compass ring + spirit auras.

7. **Pathing / terrain render.** Both use `DXOverlay` to render pathing geometry with a mask.
   - Compass: **circular** mask, invert toggle (`DrawPathing`, `Compass +.py:347`).
   - Mission Map: **rectangular** mask, invert, mega-zoom fill, per-map geometry-built cache
     (`update` + `_draw_terrain`, `Mission Map +.py:1289`,`1564`).

8. **Click handling.**
   - Compass: alt-click → `Player.Move`; marker click → `Player.ChangeTarget`
     (`CheckClick` + hit-tests in `DrawAgent`).
   - Mission Map: left-click → capture/copy coords; right-click → **NavMesh snap-move with a
     shift-click waypoint queue**, BT MoveTo coroutine, path preview, danger-pause, arrival
     detection, stop button (`Mission Map +.py:1374`–`1495`, `_snap_*` helpers).

9. **Boilerplate.** Near-identical `tooltip()` / `main()` / `draw()` / error handling. Note a
   copy-paste bug: **both** tooltips are titled "Mission Map +" (`Compass +.py:761`).

## Which does each part better

**Mission Map is the stronger engineering base:**
- Data-oriented single-struct agent read (correct native pattern).
- Caches transform/frame, boundaries/map-id, shapes, and packed colors.
- OO shape registry is cleaner and extensible.
- Auto-save `Settings` on `"account"` scope — current convention.
- Unique features: NavMesh snap-move + waypoint queue, terrain mega-zoom, coords-copy strip,
  map-id strip.

**Compass has better product thinking in places:**
- Rotation (structurally required) via the clean native projection call.
- **Custom markers by model-id** + "Get from Target" — a genuinely nice feature Mission Map
  lacks.
- Richer spirit taxonomy (ranger / ritualist{spirit,longbow,earshot,area} / vanguard) and
  profession-colored boss glow.
- Detached/floating mode, always-point-north, culling slider, per-ring editor, spirit-range
  alpha.

**Where inexperience shows (both):**
- Compass uses **class-level attributes as instance state** (defines everything on the
  `Compass` class, instantiates once) — fragile shared state.
- Compass does per-property binding calls and repeated `Player.GetAgentID()` in a hot loop.
- Mission Map **re-implements projection math** instead of extending the native
  `MapProjection` to accept cached params — copy vs library can drift.
- Both **hardcode a giant spirit list independently** — two sources of truth for the same
  game data (`Mission Map +.py:67` `SPIRIT_BUFFS` vs `Compass +.py:126` spirit sets).
- Duplicated tooltip/main/error boilerplate, plus the mislabeled Compass tooltip.

## Agreed direction (decisions taken)

1. **One widget, two mutually-exclusive modes.** A single widget file with a mode selector —
   *Compass frame* **or** *Mission-map frame* — with **only one active at a time**. They are
   **not** run simultaneously ("both on" is out of scope). This is how they have always
   behaved for users; keeping them exclusive preserves that and removes every
   "what happens when both overlays are active" question. One catalog entry, not two.
2. **Reusable core lives in `Py4GWCoreLib`.** The overlay is a generic **map overlay** — it
   is neither "compass" nor "mission map" — so the core package belongs in `Py4GWCoreLib`
   (source-of-truth layer), reusable by other widgets/bots, not buried in a single widget
   file. The widget becomes a thin host that instantiates the core bound to the selected
   frame.
3. **Fresh core, both as references.** Design the core from first principles per the
   `redesign-ignore-current-usage` / `ui-redesign-not-iteration` principles; treat both
   existing files purely as feature/behavior references — do **not** port either wholesale.
4. **Context doc first** (this folder), then design, then build — iterative, one piece at a
   time.

### Feature sets per mode

Each mode **mounts its historical feature set** (see `feature-inventory.md`): compass mode
keeps rotation / detached / north-lock / culling / ring editor; mission mode keeps
mega-zoom / navmesh-snap+queue / coords & map-id strips. Because both now sit on one shared,
capability-complete core, cross-pollinating a feature later (e.g. offering navmesh-snap in
compass mode) becomes trivial — but it is **not** forced now, and defaults stay familiar.

## Implications for the fresh core

The single-widget / two-exclusive-modes target (core in `Py4GWCoreLib`) means the core must
cleanly separate:

- **Projection strategy** — one interface (`game_to_screen` / `screen_to_game` /
  `gwinch_to_pixels`), two backings: *rotating* (compass) and *axis-aligned + mega-zoom*
  (mission map). Both should delegate to the native `Map.*.MapProjection` rather than
  re-inlining, with a per-frame param cache.
- **Shape renderer** — one registry where every shape honors both a per-agent `offset_angle`
  and an overall map `rotation` (folds Compass's rotation need into Mission Map's registry).
- **Agent pass** — one data-oriented iteration (single struct read) producing draw commands
  from a **shared classification table** backed by a **single spirit data source**.
- **Config** — one schema + one auto-save `Settings` store; a superset of both (per-marker
  color/accent/fill/size, rings, custom-by-model-id, terrain, snap, detached). Scope
  question below.
- **Interaction** — target-on-click always; movement mode pluggable (simple move vs
  navmesh-snap+queue), shared across both frames.
- **Per-mode mount** — the two modes differ only in: projection choice, mask shape
  (circular vs rectangular), rotation on/off, and which extra features apply (mega-zoom &
  navmesh-snap are mission-map-centric; detached & north-lock are compass-centric). These
  become **mode options**, not separate code paths. Only one mode is live at a time.

## Open questions to resolve in the design phase

- **Settings scope + migration.** Mission Map uses `"account"`, Compass uses `"global"`.
  Pick one (likely `"account"`), and decide whether/how to import existing `.ini`s so users
  don't lose their tuned configs.
- **Shared spirit source.** The single spirit table lives in `Py4GWCoreLib` alongside the
  core (since the package moves there anyway); decide whether it also feeds range
  classification.
- **Rotation-capable shapes.** Confirm every merged shape looks correct under arbitrary map
  rotation (Mission Map shapes were only ever exercised at rotation 0).
- **`Py4GWCoreLib` package shape.** Exact module path/name (e.g. `Py4GWCoreLib/map_overlay/`
  or a `MapOverlay` surface), and how it exposes projection / shapes / agent-pass / config /
  interaction without dragging widget-only concerns into the core layer.
- **Catalog entry / naming / icon** for the unified widget, and what happens to the two old
  `.py` files and their `Assets/Textures/Module_Icons` assets.

### Resolved by the exclusivity + Py4GWCoreLib decisions
- ~~Feature applicability when "both" is on~~ — moot; modes are mutually exclusive.
- ~~One draw window vs per-frame windows when both active~~ — moot; only one mode draws.

## Key source references

- Compass core: `Compass +.py` — `Position.Update:81`, `DrawRangeRings:328`,
  `DrawPathing:347`, `DrawAgent:378`, `DrawAgents:464`, `Draw:672`, `CheckClick:716`,
  `Update:729`, `configure:793`.
- Mission Map core: `Mission Map +.py` — projection `162`–`238`, shapes `490`–`797`,
  configs `803`–`899`, settings `929`–`965`, `MissionMap` class `969`+, snap helpers
  `347`–`455` & `1077`–`1495`, `DrawFrame:1500`, `configure:1941`, `draw:2058`.
- Native projection surfaces: `Py4GWCoreLib/Map.py` — `MissionMap.MapProjection:1081`,
  `MiniMap.MapProjection:1559` (rotation-aware `GamePosToScreen:1702`,
  `ComputedPathingGeometryToScreen:1784`).
