# DEMO v2.0 — Modular `Py4GW DEMO 2.0.py`

**Entry file:** `Py4GW DEMO 2.0.py` (repo root, ~180 lines)
**Source package:** `Sources/ApoSource/py4gw_demo_src/`
**Status:** In-progress rewrite. Modern shape, but only ~3 of the ~13 v1 domains ported. The in-code tooltip still advertises the full v1 feature set (Merchant/Skill/Effect/Inventory/World Tools/Core Utilities) that is **not yet implemented** here.

---

## 1. File layout

| File | Lines | Role |
|---|---|---|
| `Py4GW DEMO 2.0.py` (root) | 180 | Widget entry point. Owns the single main window, the left-nav sidebar, the view router, `draw_agent_array_data()`, `tooltip()`, `main()`. |
| `py4gw_demo_src/__init__.py` | 0 | Empty package marker. |
| `py4gw_demo_src/helpers.py` | 102 | Shared state + widgets: `VIEW_LIST` (nav model), `SECTION_INFO`, `_selected_view`, `DisplayNode`/`MapVars`/`map_vars` config dataclasses, `draw_kv_table()` (the v2 replacement for `ImGui_Legacy.table`). |
| `py4gw_demo_src/map_demo.py` | 801 | All Map views. |
| `py4gw_demo_src/agent_demo.py` | 558 | Agents view (nearest table + per-agent inspector). |
| `py4gw_demo_src/pathing_map_demo.py` | 502 | `PathingMapRenderer` — geo/pathing canvas with pan/zoom, trapezoid rendering, click-to-path. |

## 2. Architecture

Single dockable window with **sidebar + content** layout (a real departure from v1's floating windows):

- `draw_window()` opens one `PyImGui.begin(MODULE_NAME, ...)` with `AlwaysAutoResize`.
- **Left panel** (`begin_child "left_panel"`, fixed 250×700): iterates `VIEW_LIST` (`list[(is_child, name)]`) as `PyImGui.selectable` rows; child rows are indented. Selection sets module-global `_selected_view`.
- **Right panel** (`begin_child "right_panel"`, 700×700): a router `if/elif _selected_view == ...` dispatches to the view's draw fn.
- View functions are imported from the `py4gw_demo_src` submodules.
- **Shared config** lives in `helpers.MapVars`/`map_vars` (dataclass tree of `DisplayNode(visible, color, thickness)` per overlay element) — a cleaner state model than v1's positional `values[]` lists.
- **`draw_kv_table(table_id, rows)`** is the v2 native-`PyImGui` key/value table primitive (BordersInnerV | RowBg | SizingStretchProp), replacing `ImGui_Legacy.table`. Note: `agent_demo.py` and `tooltip()` still fall back to `ImGui_Legacy` in places.

## 3. Coverage — views and backend surface

`VIEW_LIST` (helpers.py): `Map`, `Mission Map`, `Mini Map`, `World Map`, `Pregame Data`, `WIP Observing Matches Data`, `Geo Location and Pathing`, `AgentArray`, `Agents`.

| View | Draw fn | Backend surface exercised |
|---|---|---|
| **Map** (tabbed) | `map_demo.draw_map_data` → tabs | Info/Data/Actions/Mission/Mini/World/Pregame tabs. `Map.Get*` scalar fields (instance type, id/name, uptime via `FormatTime`, region/region-type/district/language, players-in-instance, campaign/continent, guild-hall, party sizes, foes, vanquish, cinematic, unlock flags, mission-maps-to, controlled outpost, world-map/pvp, level ranges, thumbnail, icon positions, file ids, name/description ids…). Actions: `SkipCinematic`, `TravelToRegion`, `TravelGH/LeaveGH`, `EnterChallenge/CancelEnterChallenge`. |
| **Mission Map** | `draw_mission_map_tab` | `Map.MissionMap.*` — `IsWindowOpen/OpenWindow/CloseWindow`, `GetFrameInfo` (→ `FrameInfo`, `DrawFrameOutline`), `GetFrameID`, `IsMouseOver`, window/contents coords, `GetScale/GetZoom/GetAdjustedZoom`, `GetCenter/GetMapScreenCenter`, `GetLastClickCoords/GetLastRightClickCoords`, `GetPanOffset`, and **`Map.MissionMap.MapProjection.*`** coordinate transforms (`NormalizedScreenToScreen/…ToWorldMap/…ToGamePos`, `GameMapToScreen`, `WorldMapToScreen`). Overlay draws (outline/content/click/right-click/center/player) via `Overlay().BeginDraw/DrawQuad/DrawPoly/DrawLine3D/DrawTriangleFilled3D/FindZ/EndDraw`. |
| **Mini Map** | `draw_mini_map_tab` | `Map.MiniMap.*` — parallel to Mission Map (window state, frame info, scale/zoom, click coords, pan, `MapProjection.ScreenToGamePos/GamePosToScreen`, overlay display options). |
| **World Map** | `draw_world_map_tab` | `Map.WorldMap.*` — window state, frame id, mouse-over, coords, zoom, click coords, `GetParams()` (uint32 array), `GetExtraData()` (dict). |
| **Pregame Data** | `draw_pregame_tab` | `Map.Pregame.*` — `GetAvailableCharacterList` (player_name/uuid/map_id/primary/secondary/campaign/level/is_pvp), `IsWindowOpen`, `LogoutToCharacterSelect`, `GetFrameID`, `GetChosenCharacterIndex`, `GetCharList`, and **`GetContextStruct()`** (raw ctypes pregame context: camera pitch/limits/scroll/rotation fields, chars_array m_buffer/capacity/size, self_link/list_head pointers…). Per-character raw struct fields incl. encoded name. |
| **WIP Observing Matches** | *(listed, not routed)* | Placeholder — no handler in the router. |
| **Geo Location and Pathing** | `pathing_map_demo.renderer.Draw_PathingMap_Window` | `Map.GetMapBoundaries`, `Map.Pathing.GetPathingMaps()` (trapezoid layers). Custom canvas: fit/pan/zoom transforms, bucket-merge + horizontal-strip merge of trapezoids, `PyImGui.draw_list_add_quad_filled/add_circle_filled/add_line`, IO for mouse wheel/drag/double-click. Double-click schedules pathfinding via `AutoPathing().get_path` pushed onto `GLOBAL_CACHE.Coroutines`. `Player.GetXY`. |
| **AgentArray** | `draw_agent_array_data` (in root) | `AgentArray.GetAgentArray/GetAllyArray/GetNeutralArray/GetEnemyArray/GetSpiritPetArray/GetMinionArray/GetNPCMinipetArray/GetItemArray/GetOwnedItemArray/GetGadgetArray/GetDeadAllyArray/GetDeadEnemyArray` (counts only). |
| **Agents** | `agent_demo.draw_agents_view` | Nearest table (`Routines.Agents.GetNearest*`, `Player.GetTargetID/GetAgentID`, `Agent.GetAgentByID` → **`AgentStruct`**). Allegiance combo filter → matching pre-filtered array. Per-agent tabbed inspector using **direct `Agent.*` wrappers** (positional/rotation/velocity/nametag, model scales, name properties, visual effects, terrain normal/ground for player, attributes) and type-specific Living/Item/Gadget field dumps. Uses `native_src.context.AgentContext` structs and `GWStringEncoded._format_name_encoded` for encoded names. `Player.ChangeTarget`, clipboard copy. |

## 4. What v2 does differently / better

- **Exercises the Reforged-native surface v1 never touched:** `native_src` ctypes context structs (`AgentStruct`, pregame `GetContextStruct`), the `Map.MissionMap/MiniMap/WorldMap/Pregame/Pathing` sub-namespaces, `MapProjection` coordinate math, `FrameInfo`, encoded-string decoding.
- **Modern UI:** one window, sidebar navigation, `draw_kv_table` on raw `PyImGui`, dataclass-based config state.
- **Deeper on Map & Agents:** far more Map fields, live overlay projection demos, a full interactive pathing canvas.

## 5. What v2 is missing vs v1 (the gap)

Not yet ported: **Player, Party, Item, Inventory, Skill, Skillbar, Effects, Merchant/Trading, Quest, Keystroke, Ping, Timer, Overlay-as-section, PyImGui widget demos.** The `tooltip()` advertises Merchant/Skill/Effect/Inventory/World-Tools/Core-Utilities but no view implements them. `WIP Observing Matches Data` is a stub. `agent_demo.py`/`tooltip()` still depend on `ImGui_Legacy`.
