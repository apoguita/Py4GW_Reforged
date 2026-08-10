# Map Overlay Merge — Package Shape (Design Phase)

> Decisions settled: config scope **`account`**; core is a **`Py4GWCoreLib` package**;
> modes are **mutually exclusive** (Compass frame *or* Mission-map frame, never both);
> catalog **icon = a map icon**. This doc pins the package's placement and module split by
> **complying with the nearest in-repo precedent**: `py4gwcorelib_src/launch_bar/`.

## Precedent: `launch_bar/`

`launch_bar` is the repo's most recent from-scratch UI package. Observed conventions:

- **Placement:** under `Py4GWCoreLib/py4gwcorelib_src/` (support-infra layer), **not** a
  top-level domain facade. It is imported by its deep path
  (`from Py4GWCoreLib.py4gwcorelib_src.launch_bar.launchpad import ...`) — **no** re-export
  in `Py4GWCoreLib/__init__.py`.
- **Strict layered split:** `model` (pure data, no ImGui/Py4GW, offline-importable) →
  `host` (renders ONE thing, owns transient UI state) → `manager` (coordination + editor
  windows) → `persistence` (durable per-**account** `Settings`, lazy-imported, import-safe
  offline) → supporting modules (`browser`, `function_runtime`, `tween`, …).
- **`__init__.py`** re-exports only the public model/entry classes.
- Docstrings state each module's boundary explicitly (e.g. "No ImGui and no Py4GW imports").

**We comply in shape and form:** same placement, same layering discipline, same
persistence pattern, same deep-path import (no top-level facade).

## Placement

```
Py4GWCoreLib/py4gwcorelib_src/map_overlay/
```

Imported by the thin widget host via
`from Py4GWCoreLib.py4gwcorelib_src.map_overlay.host import MapOverlay` (exact names TBD).

## Module split (proposal — refined during build)

| Module | Role | Boundary (imports) | Mirrors launch_bar |
|---|---|---|---|
| `__init__.py` | Re-export public surface: `MapOverlay`, `OverlayMode`, `OverlayConfig` | — | `__init__.py` |
| `model.py` | **Pure data**: `OverlayMode{COMPASS,MISSION}`, `MarkerStyle`, `Ring`, `CustomMarker`, classification constants (chest/gadget ids, pet model ids, area/earshot sets), the **single spirit table** (name/model_id/skill_id/color/range-class), unit-point shape geometry | No ImGui, no Py4GW — offline-importable/testable | `model.py` |
| `projection.py` | Projection **strategy**: `RotatingProjection` (compass → `Map.MiniMap.MapProjection`, rotation from `GetRotation`) and `AxisAlignedProjection` (mission → `Map.MissionMap.MapProjection` math + mega-zoom). Common iface: `game_to_screen` / `screen_to_game` / `gwinch_to_pixels` / per-frame `refresh()`; per-map boundary cache | `Map` | (new; game-facing adapter) |
| `shapes.py` | **Rotation-capable** shape registry (Mission Map OO set + Compass `Star`/`Tear2`), draw-list helpers, shape-instance + color→int caches. Every shape rotates by a **final angle** the caller supplies | `PyImGui` | (part of `host` there) |
| `agents.py` | **Data-oriented agent pass**: single struct read (`Agent.GetAgentByID` → `GetAsAgentLiving`), classify via `model` tables, emit draw commands. Handles spirits/auras, boss glow, item rarity, npc/minipet/merchant, gadget/chest, pet, culling | `Agent`, `AgentArray`, `Item`, `Player` | (new) |
| `terrain.py` | `DXOverlay` pathing/terrain render; mask shape param (**circular** compass vs **rectangular** mission), invert, mega-zoom fill, per-map geometry-built cache | `DXOverlay`, `Map` | (new) |
| `interaction.py` | Targeting (marker hit-test → `ChangeTarget`) + movement **modes**: `SimpleMove` (click→`Player.Move`) and `NavMeshSnap` (right-click snap, waypoint queue, BT MoveTo coroutine, danger-pause, arrival, stop) | `Player`, `Pathing`, `Routines`, BT | (new) |
| `persistence.py` | Account `Settings` load/save of the `OverlayConfig` superset in the widget's **own** ini (e.g. `Widgets/Guild Wars/Screen Overlays/Map Overlay +.ini`). Also provides **opt-in import** readers that parse a legacy `Compass +.ini` / `Mission Map +.ini` and return an `OverlayConfig` to merge in on user request. Lazy `Settings` import, import-safe offline | lazy `Settings` | `persistence.py` |
| `host.py` | Renders **ONE** overlay for the active mode; owns transient/frame state; wires projection+shapes+agents+terrain+interaction; floating strips (move toggle, coords, map-id, mega-zoom slider) + detached-mode window | `PyImGui`, siblings | `host.py` |
| `config_ui.py` | The `configure()` editor: grouped markers, rings, custom markers, terrain, snap, position/detached | `PyImGui`, siblings | `manager.py` editor |

The mode difference collapses to **four options** consumed by `host`: projection choice,
mask shape, rotation on/off, and which extra features mount (mega-zoom + navmesh-snap =
mission; detached + north-lock + ring-editor + culling = compass). One mode is live at a time.

## The widget host (thin)

```
Widgets/Guild Wars/Screen Overlays/Map Overlay +.py   (name TBD)
```

Passive on import, frame-driven (`main`/`draw`/`configure`/`tooltip`) per
`widget-script-shape`. It reads the selected `OverlayMode` from config and delegates to
`MapOverlay`. One catalog entry, map icon.

## Naming / migration / cleanup

- **Widget name/icon:** **"Map Overlay"** (locked), `Assets/Textures/Module_Icons/Map Overlay.png`
  (a map icon).
- **Its own ini, no auto-migration.** The new widget owns and writes a fresh config from
  defaults — it never silently touches the legacy files. A clean install "just works" with
  no import.
- **Opt-in import in the config UI.** `config_ui.py` exposes explicit actions —
  *Import Mission Map settings* and *Import Compass settings* — that read the corresponding
  legacy ini via `persistence.py`'s import readers and merge the values into the current
  config (then autosave to the widget's own ini). Importing is a user choice, per source,
  and can be skipped entirely.
- **Retire the old widgets by relocation, not deletion.** Move `Compass +.py` and
  `Mission Map +.py` **as-is** into `Legacy code and tests/Deprecated but working/` (alongside
  the other deprecated-but-working widgets). Their legacy `.ini`s stay where users have them
  so the opt-in import can still find them; their `Assets/Textures/Module_Icons` PNGs move with them
  or are left dormant. Do this only once the unified widget is verified in-client.

## Closed / deferred questions

- **Rotation-correctness of shapes** — *closed as non-issue.* Shapes rotate by a final angle
  supplied by the caller; compass passes `map_rotation + agent_facing`, mission passes
  `agent_facing` (rotation 0). The only residual is cosmetic: shapes that currently ignore
  facing (Square/SignPost/Lock/Scale/Penta) won't spin with the compass — acceptable, revisit
  only if it looks wrong.
- **"Both modes on" behavior** — *moot;* modes are mutually exclusive.
- **One-vs-per-mode draw windows** — *moot;* one mode draws at a time.
