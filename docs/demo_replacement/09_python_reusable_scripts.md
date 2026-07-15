# Reusable Python Scripts (harvest candidates)

This inventory catalogs every existing demo/test/inspector-shaped Python script we can HARVEST
code from while building **DEMO 2.0** (the widget that exercises every Py4GW binding and data
getter live in-client). For each script it lists: path + purpose, which bindings/wrappers/contexts
it exercises, the concrete reusable functions/classes/patterns worth lifting (named), and how much
is directly portable vs. needs rework for the new Reforged surface / new `Py4GWCoreLib.ImGui` facade.

**Cross-cutting caveats (apply to almost every entry below):**

- **ImGui facade migration.** Nearly all of these use raw `PyImGui.*` calls plus the legacy
  `ImGui_Legacy` helper (`ImGui_Legacy.table`, `.push_font`, `.WindowModule`, `.Begin/End`,
  `.toggle_button`, `.DrawTexture`, `.FloatingIcon`, `.BeginWithClose`). Raw `PyImGui.*` calls port
  as-is (the facade sits *on top* of the same 1.92 `PyImGui`), but any `ImGui_Legacy.*` call must be
  re-expressed against the new `Py4GWCoreLib.ImGui` runtime singleton (`with ImGui.window(...) as
  scope:` etc.). No aliasing/bridging is allowed between the two facades.
- **Reforged renames already applied.** Prefer `PySystem.Console.*`, `PySystem.get_tick_count64()`,
  `PyGameThread.enqueue`, `PyOverlay.Vec2f`, `PyAgentEvents` (was `PyCombatEvents`), `PyDXOverlay`.
  Some scripts below still reference legacy names (e.g. CombatEventsTester imports `PyAgentEvents`
  but then calls `PyCombatEvents.GetCombatEventQueue()` — a live bug to fix on harvest).
- Every widget follows the passive shape: module-level state only, a frame-driven `main()`/`draw()`,
  a `MODULE_NAME`/`MODULE_ICON`, and usually a `tooltip()`.

---

## 1. UIManager / Frame inspection (the richest vein)

Four generations of the same frame-tree inspector exist, culminating in `Frame_Showcase`, which is
the single most valuable UIManager harvest source.

### `Widgets/Coding/Debug/Guild Wars/Frame_Showcase.py`  ★ TOP TARGET
- **Purpose:** Comprehensive UIManager feature explorer & tester (4 tabs: Frame Tree, UIManager API
  Tester, Log Monitor, Visual Toolkit) plus a per-frame `FrameInspector` with 6 sub-tabs and ~105
  raw fields. This is the modern, dataclass-based rewrite of Frame_Tester/RawFrame_Tester.
- **Bindings/contexts:** `PyUIManager.UIFrame` (all fields: position, relation, callbacks, ~105
  `fieldNN_0xNN`), the whole `Py4GWCoreLib.UIManager` wrapper surface, `PyOverlay`, `PyCallback`,
  `Settings`.
- **Reusable assets (name them):**
  - `FrameNode` / `FrameTree` — throttled hierarchy builder (`build_tree`, `THROTTLE_TREE_MS`),
    search filter (`_matches_search`, deferred `apply_filter`), color-coded node state
    (`choose_frame_color`), badges, right-click context menu, hover tooltip, inspector-open request
    queue (`drain_inspector_requests`). **Best frame-tree walker in the repo.**
  - `UIManagerAPITester` — a generic **"run any method with shared inputs, cache & color the
    result"** harness: `_exec`, `_run_button`, `_section_header`. It already enumerates ~80 UIManager
    methods grouped into Navigation / Tree Walkers / Properties / Geometry / Visibility / Label /
    Lists / Messages / IO Events / Preferences / Windows / Key Input / Interaction / Coords / Misc.
    This is the closest thing to "exercise every binding" already written — lift wholesale.
  - `LogMonitor` — diff-based tailing of `UIManager.GetFrameLogs()` / `GetUIMessageLogs()` /
    IO events into bounded `deque`s with auto-refresh throttle.
  - `VisualToolkit` — DrawFrame / DrawFrameOutline color-picker demo + Overlay/Popup frame browsers.
  - `FrameInspector` — per-frame deep view; helpers `_to_hex/_to_bin/_to_char`, `_raw_field_row`.
- **Portability:** High for logic; the raw-PyImGui rendering ports directly. `ImGui_Legacy.table`
  and `ImGui_Legacy.toggle_button` need facade re-expression. Uses correct Reforged
  `PySystem.Console.get_projects_path()`.

### `Widgets/Coding/Debug/Guild Wars/Frame_Tester.py`
- **Purpose:** Older frame-tree inspector + `InfoWindow` per-frame debugger (Frame Tree / Position /
  Relation / Callbacks / Extra Fields tabs) with alias JSON editing and `TestMouseAction`/
  `TestMouseClickAction` state-cycling buttons.
- **Bindings:** `PyUIManager.UIFrame`, `UIManager.GetFrameArray/DrawFrame/FrameClick/TestMouseAction/
  SaveEntryToJSON/GetEntryFromJSON`, `Overlay`.
- **Reusable assets:** `FrameNode.draw()` recursive colored tree; `InfoWindow` (alias save/load,
  frame-click + mouse-action test harness, hex/bin/char field table). Mostly superseded by
  Frame_Showcase — harvest the **mouse-action state-cycling** buttons if DEMO 2.0 wants to exercise
  `TestMouseAction`.
- **Portability:** Medium; superseded, `ImGui_Legacy.WindowModule` + `.table` need rework.

### `Widgets/Coding/Debug/Guild Wars/RawFrame_Tester.py`
- **Purpose:** Zero-dependency ("no unnecessary imports") frame tester — reimplements all UIManager
  helpers locally against raw `PyUIManager`/`PyOverlay`.
- **Reusable assets:** self-contained `RGBToNormal/RGBToColor/ColorToTuple/TupleToColor`,
  `toggle_button`, `table`, `ConstructFramePath`, `SaveEntryToJSON`/`GetEntryFromJSON`,
  `GetFrameCoords`, `DrawFrame` (uses `PyOverlay.Vec2f` + `DrawQuadFilled`). The **fullest raw-field
  dump** (~150 `fieldNN` rows incl. `field31_0x84` parameter array). Good reference for the complete
  UIFrame field list; otherwise superseded.
- **Portability:** High (already Reforged `PyOverlay.Vec2f`), but redundant with Frame_Showcase.

### `Widgets/Coding/Debug/Guild Wars/UI_Listener.py`  ★ listener demo
- **Purpose:** Two-tab listener for `UIManager.GetFrameLogs()` (frame-label log) and
  `GetUIMessageLogs()` (incoming/outgoing UI messages with WParam/LParam bytes).
- **Bindings/contexts:** `UIManager.GetFrameLogs/GetUIMessageLogs/ClearUIMessageLogs`,
  `enums_src.UI_enums.UIMessage`, `PySystem.get_tick_count64()`.
- **Reusable assets:**
  - `draw_multi_table(table_id, headers, rows)` — clean generic N-column scrollable table
    (BordersInnerH/V + RowBg + ScrollY + SizingStretchProp). **Lift as a shared table helper.**
  - `tick_to_timestamp()` + the `_anchor_walltime/_anchor_tick` anchor pattern — converts engine
    tick to HH:MM:SS without `datetime.now()` jitter. Reusable for any event/log view.
  - `UIMessage(message_id).name if ... else hex(...)` enum-name-or-hex idiom.
- **Portability:** High; raw PyImGui + Reforged tick API. Only `ImGui_Legacy` in the tooltip.

### `Widgets/Coding/Tools/Native Button Test Harness.py`
- **Purpose:** Creates a native GW window + native button via engine FrameProc (CtlBtnProc) with
  self-describing debug dumps. Demonstrates the game-thread-enqueue + scanner-resolution path.
- **Bindings:** `GWUI.CreateWindow`, `native_src.methods.ButtonMethods` (`create_native_button_sync`,
  `CtlBtnProc_Callback`, `FrameCreate_Func`, `CtlBtnSetTextLiteral_Func`), `PyGameThread.enqueue`,
  `UIManager.GetFrameByID/GetFrameCoords/DestroyUIComponentByFrameId`.
- **Reusable assets:** `_verify_scanners()` (NativeFunction `.is_valid()`/address status dict),
  `_frame_summary()`, `_list_children()`, `_scan_frame_tree()` recursive logger, the
  `PyGameThread.enqueue(_invoke)` + delayed `_schedule_report/_process_pending_reports` pattern for
  "do on game thread, read back after a delay." Good for a DEMO 2.0 "native UI creation" panel.
- **Portability:** High and already Reforged (`PyGameThread.enqueue`). Uses `PyImGui.begin(...)[0]`
  tuple form and `PyImGui.ImGuiWindowFlags_AlwaysAutoResize` (older flag name) — normalize on harvest.

---

## 2. Agent inspection / info (three near-identical copies)

### `Widgets/Coding/Debug/Guild Wars/Agent Info.py`  ★ agent viewer
- **Purpose:** Full agent inspector — nearest-agents table (player/enemy/ally/item/gadget/npc/target)
  + per-agent tabbed detail with Positional, Properties, Attributes, Living/Item/Gadget field tables
  and ~50 boolean status flags.
- **Bindings/contexts:** the entire `Agent.*` getter surface (Get{XYZ,Rotation*,Velocity*,NameTag,
  ModelScale1/2/3,Professions,Health,Energy,Allegiance,Weapon*,Effects,ModelState,TypeMap,
  Animation*,GadgetAgent*,ItemAgent*}), all `Is*/Has*` predicates, `AgentArray.Get*Array`,
  `Routines.Agents.GetNearest*`, `Allegiance` enum, `native_src.context.AgentContext.AgentStruct`.
- **Reusable assets:** `_format_agent_row`, `_colored_bool` (green/red tuple), `_get_type`,
  `_draw_agent_tab_item(agent_id)` (the exhaustive per-agent panel), the allegiance-combo →
  filtered `AgentArray` → id-mapped agent combo → `Set Target` selector. This is **the** agent-getter
  coverage panel; lift `_draw_agent_tab_item` almost verbatim into DEMO 2.0.
- **Portability:** High for the getter calls; `ImGui_Legacy.table`/`WindowModule`/`push_font` →
  facade. Note `Agent.GetEncNameStrByID` here vs `Agent.GetEncNameByID` in agent_demo (verify the
  Reforged name).

### `Sources/ApoSource/py4gw_demo_src/agent_demo.py`
- **Purpose:** The demo-package version of Agent Info — same `_draw_agent_tab_item`, but exposed as
  `draw_agents_view()` returning child regions (no own window) so it composes inside a host tab bar.
- **Reusable assets:** identical helpers; **preferred for DEMO 2.0** because it already drops the
  outer `PyImGui.begin/end` and uses `GWStringEncoded._format_name_encoded(Agent.GetEncNameByID(...))`
  for encoded-name display + clipboard copy. This "view function, not window" shape is the pattern
  DEMO 2.0 should copy for every subsystem panel.
- **Portability:** High; same facade caveat.

### `Widgets/Coding/Debug/Guild Wars/AccountData.py`
- **Purpose:** Aggregated per-account dashboard (Faction/Titles/Account/Quest Log/Player Data tabs),
  built from live `Agent`/`Player`/`Map` getters (not shared memory).
- **Bindings/contexts:** `Agent.*` general/flags/skillbar getters, `Player.GetMissions*/
  GetUnlockedCharacterSkills/GetControlledMinions/GetPlayerUUID`, `GLOBAL_CACHE.SkillBar`,
  `Sources/ApoSource/account_data_src/*` (RankData/FactionData/ExperienceData/TitleData/QuestData).
- **Reusable assets:** `AgentData.GeneralData/Flags/SkillbarData` update-model classes (a clean
  "gather-then-draw" split), the 32-bit bitfield expansion for missions/skills
  (`(mask >> bit) & 1` loops) + "copy completed to clipboard." Good template for a stateful
  data-model panel. Overlaps the SharedMem version below (which caches better).
- **Portability:** Medium; depends on `Sources/ApoSource/account_data_src` sub-packages.

---

## 3. Combat events / listener  ★ TOP TARGET

### `Widgets/Coding/Debug/Guild Wars/CombatEventsTester.py`
- **Purpose:** The definitive callback-loop + event-query demo. 6 tabs: Event Log, State Queries,
  Event History, Damage Tracker, Skill Recharges, Debug. Docstring is a copy-paste API cookbook.
- **Bindings/contexts:** `Py4GWCoreLib.CombatEvents` (`OnSkillActivated/OnSkillFinished/
  OnSkillInterrupted/OnAttackStarted/OnAftercastEnded/OnKnockdown/OnDamage/OnSkillRechargeStarted/
  OnSkillRecharged`, `ClearCallbacks`, `GetEvents/GetRecentSkills/GetRecentDamage/GetRecentHealing/
  GetRecentEffectRenewals`), `EventType`, `Agent.*` combat-state queries (`IsCasting/GetCastingSkillID/
  GetRemainingCastTime/IsKnockedDown/HasStance/GetObservedSkillbar/GetSkillsOnCooldown/
  IsCooldownEstimated`), `CombatEventQueue_src.helpers` internals (`_recharges/_disabled/_stances/
  _tracked_agents`).
- **Reusable assets:**
  - `EventLog` (bounded ring buffer with `add/get_recent`) and `TesterState` (all filter/tracker
    state in one object) — clean state containers.
  - `register_callbacks()`/`unregister_callbacks()` — the canonical **event-subscription loop**;
    lift directly for DEMO 2.0's events panel.
  - `on_damage` damage-fraction→actual-HP conversion, `get_event_color()` event-type color map,
    per-tab draw functions.
- **Portability:** Medium — **has a live bug**: `draw_event_log_tab` does `import PyAgentEvents` then
  calls `PyCombatEvents.GetCombatEventQueue()`. Under Reforged the module is `PyAgentEvents`; fix the
  call. Also `Agent.CanAct` is stubbed out (`can_act = True`). Otherwise raw-PyImGui, ports cleanly.

---

## 4. Map / Overlay drawing  ★ overlay demo

### `Sources/ApoSource/py4gw_demo_src/map_demo.py`  ★ TOP TARGET (overlay + map)
- **Purpose:** Map subsystem demo with Map/Data/Actions/Mission Map/Mini Map/World Map/Pregame tabs,
  and — importantly — the fullest **overlay drawing** showcase (2D frame outlines + 3D world-space
  flags/lines/triangles + map projections).
- **Bindings/contexts:** `Map.*` (all getters + `MissionMap`/`MiniMap`/`WorldMap`/`Pregame`
  sub-namespaces incl. `MapProjection.*` coordinate transforms), `Overlay()` (`BeginDraw/EndDraw/
  DrawQuad/DrawPoly/DrawLine3D/DrawTriangleFilled3D/FindZ`), `FrameInfo.DrawFrameOutline`, Pregame
  context struct (`native_src.context.PreGameContext`).
- **Reusable assets:**
  - `draw_kv_table` (from `helpers.py`) used everywhere — the go-to 2-col field/value table.
  - The `DisplayNode` dataclass (visible/color/thickness) + per-feature collapsing-header +
    checkbox + thickness slider + `color_edit4` + draw pattern — a **reusable "toggle a debug
    overlay" widget** repeated for outline/content/click/center/player. Lift this pattern for any
    DEMO 2.0 overlay toggle.
  - `DrawFlagAll(x,y)` nested helper — 3D flag draw via `FindZ` + `DrawLine3D` + `DrawTriangleFilled3D`.
    Best overlay-3D example in the harvest set.
  - `MapProjection` conversions (Normalized↔Screen↔World↔GamePos) demos.
- **Portability:** High; `Overlay` wrapper is already Reforged. Pure `draw_*_tab()` view functions,
  no own window — ideal composition shape.

### `Sources/ApoSource/py4gw_demo_src/helpers.py`
- **Purpose:** Shared helpers for the demo package.
- **Reusable assets:** `draw_kv_table(table_id, rows)` (fixed-width "Field" col + stretch "Value"),
  `DisplayNode`/`MapVars` config dataclasses, `VIEW_LIST`/`SECTION_INFO` view-registry pattern.
  `draw_kv_table` is the **single most reused table helper** across the demo package — make it a
  DEMO 2.0 primitive.
- **Portability:** High; pure PyImGui + Color/ColorPalette.

---

## 5. Settings / Preferences / Config

### `Widgets/Coding/Debug/Guild Wars/GameConfigViewer.py`  ★ preferences demo
- **Purpose:** GW engine config manager — General/Graphics/Sound/Control/Interface tabs reading &
  writing every game preference, plus keymapping (scan-code→VK), preference-ID probing, and
  per-`WindowID` debug windows.
- **Bindings/contexts:** `UIManager.Get/SetIntPreference`, `.Get/SetBoolPreference`,
  `.Get/SetEnumPreference`, `.Get/SetStringPreference`, `.GetKeyMappings/SetKeyMappings`,
  `.GetWindoPosition/IsWindowVisible/SetWindowVisible/SetWindowPosition`; enums `NumberPreference/
  FlagPreference/EnumPreference/Key/WindowID/ServerLanguage/...`; `PyOverlay` for window outlines.
- **Reusable assets:**
  - `Preferences` class with `_PREF_MAP` (name→(type, pref_enum, enum_cls, flipped)) + `Load/Get/
    GetWithEnum/Set` — a clean typed-preference model. **Lift for a DEMO 2.0 preferences panel.**
  - `probe_bool/int/enum_preferences(start,end,compare)` — scan-a-range + diff-vs-last-snapshot
    (great generic "find the pref ID" tool).
  - `CONTROL_MAP` / `INDEX_TO_VK` reference dicts (control-action names, scan→VK map).
  - `toggle_debug_window`/`draw_debug_window` per-WindowID position/visibility editor + overlay.
- **Portability:** High for the preference/window API; `Utils.TrueFalseColor`, `ColorPalette` port.
  Big static reference tables are pure data.

### `Widgets/Coding/ImGui/Icon Explorer.py`  ★ settings-persistence demo
- **Purpose:** FontAwesome icon browser with filter, favorites, columns, sort — persisted via
  `Settings`.
- **Bindings:** `IconsFontAwesome5` (glyph enumeration via `dir()`), `Settings` (native `PySettings`:
  `get_bool/get_int/get_str/set`, keyed by `Settings(path,"account").name`), `ImGui_Legacy.Begin/End`.
- **Reusable assets:** the **Settings load/save lifecycle** (`_load_settings`, `_save_setting`,
  one-time `initialized` guard, `INI_KEY` from `Settings(...).name`) — the canonical Reforged
  settings-persistence pattern; DEMO 2.0's settings panel should copy this. Plus grid-table + hover
  tooltip + favorites-set serialization to a comma string.
- **Portability:** High and already Reforged Settings-based. `ImGui_Legacy.Begin/End` → facade.

### `Widgets/Coding/Examples/FloatingIcon example.py`
- **Purpose:** Minimal example of a floating dockable icon that toggles a companion window.
- **Bindings:** `ImGui_Legacy.FloatingIcon`, `ImGui_Legacy.BeginWithClose`, `Settings`.
- **Reusable assets:** `_ensure_ini`/`_ensure_state` lazy-init pattern; `FloatingIcon` +
  `sync_begin_with_close` wiring; dual-INI (main + floating) persistence. Useful if DEMO 2.0 wants a
  floating launcher, but heavily `ImGui_Legacy`-bound — **needs full facade rework**.
- **Portability:** Low/medium (FloatingIcon is a legacy-facade construct).

---

## 6. Shared memory / multibox

### `Widgets/Coding/Debug/Py4GW/SharedMem Monitor.py`  ★ shared-memory + ping
- **Purpose:** Cross-process account dashboard reading `GLOBAL_CACHE.ShMem` — per-account tabs with
  Account Info / Hero AI / Faction / Titles / Available Characters / Player / Agent (health/xp).
- **Bindings/contexts:** `GLOBAL_CACHE.ShMem` (`GetAllAccountData/GetAllAccounts/GetNumActivePlayers/
  GetHeroesFromPlayers/GetPetsFromPlayers/GetHeroAIOptionsFromEmail/shm_name/size/max_num_players`),
  `AccountStruct`, `FactionStruct`, `TitleUnitStruct`; **`import PyPing`** (latency binding, though
  usage lives in Py4GW_DEMO — see §10).
- **Reusable assets:**
  - `begin_striped_table`/`end_striped_table` (row-bg style push/pop) — nice striped table helper.
  - `FactionNode`/`FactionData`/`TitleData`/`ExperienceData`/`HealthData`/`PlayerData`/`AgentData`
    render classes — each a self-contained `draw_content()` panel with progress bars, texture icons
    (`ImGui_Legacy.DrawTexture(Extended)`), and **cached bitfield expansion**
    (`_expand_bit_array` with raw-identity cache — better than AccountData's uncached loop).
  - Status-icon overlay on a progress bar via `DrawTextureExtended` UV atlas slicing.
  - Min-window-size enforcement idiom (`get_window_size`→`set_window_size`).
- **Portability:** High for ShMem calls; `ImGui_Legacy.DrawTexture*`/`push_font`/`show_tooltip` →
  facade. This is the best **texture-drawing** reference too (UV atlas + progress-bar icons).

---

## 7. Profiler / callbacks / action queue (engine internals)

### `Widgets/Coding/Debug/Py4GW/System Monitor.py`
- **Purpose:** Profiler metric-name catalog + usage visualizer (stacked usage bar, sparklines,
  grouped tables, per-entry detail window).
- **Bindings:** `PyProfiler.get_metric_names/get_reports/get_history/reset`, `ColorPalette`,
  `ThrottledTimer`.
- **Reusable assets:**
  - `ProfilerMetricNameCatalog` — portable, UI-free parse/index/group engine for profiler names
    (`refresh_from_live`, `filter_text`, `group_by_attr`, `build_usage_groups_by_display`).
  - **`_draw_sparkline(...)`** — draw-list area/line chart with time ticks + hover tooltip. **The
    reusable sparkline/chart primitive** for DEMO 2.0.
  - `_draw_top_usage_stacked_bar` (100% stacked bar w/ "Others" bucket, clickable segments),
    `_draw_usage_groups` (table + `progress_bar` styled columns), deterministic
    palette-color-per-entry (`_entry_color_name`, `_contrast_text_color32`).
- **Portability:** High (raw draw-list + PyImGui + Reforged `PyProfiler`). Zero `ImGui_Legacy`. The
  color/sparkline helpers are broadly reusable beyond profiling.

### `Widgets/Coding/Debug/Py4GW/Callback Monitor.py`
- **Purpose:** Lists engine callbacks grouped by Context (Update/Draw/Main) × Phase, with
  enable/pause toggles.
- **Bindings:** `PyCallback.PyCallback.GetCallbackInfo/PauseById/ResumeById/Clear`,
  `PyCallback.Context/Phase`, `Settings`, `ImGui_Legacy.Begin/End`.
- **Reusable assets:** the group→sort→table render of callback tuples `(id,name,phase,ctx,priority,
  order,enabled)`; per-row Toggle button. Good "callback registry" panel for DEMO 2.0.
- **Portability:** High for `PyCallback`; `ImGui_Legacy.Begin/End`+`Settings` INI_KEY init → facade.

### `Widgets/Coding/Debug/Py4GW/Action Queue Monitor.py`
- **Purpose:** Per-queue (ACTION/LOOT/MERCHANT/SALVAGE/IDENTIFY/FAST/TRANSITION) view of pending
  actions + history with reset/clear/copy.
- **Bindings:** `ActionQueueManager.GetAllActionNames/GetHistoryNames/ResetQueue/ClearHistory`.
- **Reusable assets:** compact tab-per-queue + scrollable child + copy-history-to-clipboard pattern.
  Small, clean, directly portable.
- **Portability:** High; only tooltip uses `ImGui_Legacy`.

---

## 8. Low-level / scanner / packets / dialog

### `Widgets/Coding/Examples/Low Level/Scanner Test.py`  ★ native-scan + ctypes demo
- **Purpose:** Demonstrates NativeFunction signature scanning, ctypes struct probing, raw UIMessage
  travel (kTravel via message vs. raw struct pointer).
- **Bindings/contexts:** `native_src.internals.native_function.NativeFunction/ScannerSection`,
  `Prototypes`, `gw_array.GW_Array`, `native_src.context.PreGameContext`, `UIManager.SendUIMessage/
  SendUIMessageRaw`, `ctypes` structs.
- **Reusable assets:** `NativeFunction(pattern=...,mask=...,offset=...,section=...,prototype=...)`
  declaration + safe-enqueued call idiom; `TravelStruct` + `Travel_struct` raw-pointer message send;
  **`draw_dword_probe_table`** (dec/hex/bytes/ascii/wchar/float reinterpretation + PTR heuristic) —
  a superb reusable memory-inspection table; `scan_for_gw_array`, `probe_login_character_offsets`.
- **Portability:** High for the ctypes/NativeFunction machinery (Reforged-native). The DWORD probe
  table is broadly reusable for any raw-struct dump panel.

### `Widgets/Coding/Debug/Guild Wars/PacketSnifferTester.py`  ★ packet listener demo
- **Purpose:** One-button StoC/CToS packet capture → buffer → dump to console.
- **Bindings:** `Py4GWCoreLib.PacketSniffer.SNIFFER` (`initialize/terminate/get_logs/clear_logs/
  get_packet_name/decode_packet`), `PySystem.Console.Log`.
- **Reusable assets:** `_drain_into_buffers` (direction-split into StoC/CToS lists), `_hex_preview`,
  start/stop/dump lifecycle. Minimal, clean, directly portable network-listener demo.
- **Portability:** High; already Reforged `PySystem.Console`.

### `Widgets/Coding/Tools/Active Dialog Viewer.py`
- **Purpose:** Shows the current active GW dialog, context dialog, and visible dialog buttons; can
  send an automatic dialog.
- **Bindings:** `Py4GWCoreLib.Dialog.get_active_dialog/get_active_dialog_buttons/
  _call_native_dialog_method`, `Player.SendAutomaticDialog`, `PyDialog.clear_cache`.
- **Reusable assets:** dialog-state read + per-button render with copy-hex + send; the
  was-active→now-inactive cache-clear guard. Small dialog-subsystem panel.
- **Portability:** High; already Reforged `PySystem.Console`/`Dialog`.

---

## 9. Skills

### `Widgets/Coding/Examples/Skills/SkillInfo.py`  ★ skill viewer + texture cards
- **Purpose:** "Skill Atlas" — hover-to-inspect skill card with textures, cost icons, progression
  parsing, wiki names, and a side-by-side compare table.
- **Bindings/contexts:** `GLOBAL_CACHE.Skill.*` (`GetName/GetNameFromWiki/GetDescription/
  GetConciseDescription/GetType/GetCampaign/ExtraData.GetTexturePath/Data.Get*/Attribute.*/Flags.*`),
  `PySkill.Skill` (raw fields), `GLOBAL_CACHE.SkillBar.GetHoveredSkillID`,
  `ImGui_Legacy.DrawTexture/image_toggle_button/push_font`, draw-list rect for card background.
- **Reusable assets:** `SkillData` gather-model + `DrawSkillCard`, per-cost `draw_*` icon+tooltip
  helpers, `resolve_skill_description` (regex `[!x...y!]` progression-tag resolver — genuinely
  useful), `GetProfessionColor` palette map, `FilterButton` image-toggle. Best **texture + skill
  data** harvest source.
- **Portability:** Medium; heavy `ImGui_Legacy.DrawTexture`/`push_font`/`image_toggle_button` use →
  facade rework, but the Skill-getter coverage and description resolver are gold.

---

## 10. Ping / latency (lives in the existing DEMO)

The dedicated ping demo is inside the existing `Widgets/Coding/Py4GW_DEMO.py` (covered by another
doc), but the harvestable snippet is small and worth isolating:

- **Binding:** `import PyPing` → `ping_handler = PyPing.PingHandler()`.
- **Reusable pattern:** `ping_handler.GetCurrentPing()/GetAveragePing()/GetMinPing()/GetMaxPing()`
  rendered in a 2-col table. Lift these four getters into DEMO 2.0's "Core Utilities/Latency" panel.
- Also referenced in `Widgets/Automation/Enhancements/HeroHelper.py` and a farmer bot if a
  live-usage example is needed.

---

## Also-noted (lower priority / not deeply analyzed)

- `Widgets/Coding/ImGui/Color Pallete.py` (`Color Palette Explorer`) and `Color Picker.py` — palette
  grid + color-picker demos; harvest if DEMO 2.0 wants a `ColorPalette` showcase.
- `Widgets/Coding/ImGui/ImGui Official DEMO.py` (`ImGui_Legacy DEMO`) — legacy-facade widget gallery;
  mostly obsolete under the new facade but a checklist of widgets to cover.
- `Widgets/Coding/Debug/Py4GW/SharedMem Isolation Manager.py`, `Widget Profiler.py` — infra monitors.
- `Widgets/Coding/Debug/Guild Wars/Quest Data.py` — quest-log inspector (pairs with AccountData).
- `Widgets/Coding/Examples/Low Level/…`, `Pathing/PathPlanner.py`, `Tools/Route Builder.py`,
  `Script Runner.py`, `Close Rejoinable.py`, `Automation/modular/Modular Tester.py` — task-specific,
  not core binding demos.
- `Py4GW DEMO 2.0.py` + `Py4GW_DEMO.py` — the two existing demos; noted, covered by a separate doc.

---

## Top harvest targets (ranked)

1. **`Frame_Showcase.py` → `UIManagerAPITester` + `FrameTree`/`FrameNode` + `FrameInspector`.**
   The closest existing thing to "exercise every binding": a generic run-method-and-show-result
   harness already covering ~80 UIManager methods, plus the best frame-tree walker and per-frame
   inspector. Single highest-value lift.
2. **`Agent Info.py` / `agent_demo.py` → `_draw_agent_tab_item` + nearest-agents selector.**
   Exhaustive Agent-getter coverage. Prefer the `agent_demo.py` "view function, no own window" shape.
3. **`CombatEventsTester.py` → `register_callbacks()` loop + `EventLog`/`TesterState` + query tabs.**
   The event-subscription/listener demo. (Fix the `PyAgentEvents` vs `PyCombatEvents` call on harvest.)
4. **`map_demo.py` → overlay `DisplayNode` toggle pattern + `DrawFlagAll` 3D draw + `MapProjection`.**
   Best overlay-drawing (2D + 3D world-space) and Map-getter coverage.
5. **`System Monitor.py` → `_draw_sparkline`, stacked-usage bar, deterministic palette helpers.**
   Reusable chart/color primitives (raw draw-list, zero legacy facade).
6. **`helpers.py::draw_kv_table` + `UI_Listener.py::draw_multi_table` + `SharedMem Monitor`
   striped-table helpers.** The shared table primitives every panel needs — standardize these first.
7. **`Scanner Test.py::draw_dword_probe_table`** — reusable raw-struct/DWORD inspection table
   (dec/hex/bytes/ascii/wchar/float + PTR heuristic) for any context/struct dump.
8. **`GameConfigViewer.py::Preferences` model + `probe_*_preferences`** — typed preference get/set
   coverage + ID-discovery probing.
9. **`Icon Explorer.py` Settings lifecycle + `SharedMem Monitor` `DrawTextureExtended` UV atlas** —
   the canonical Reforged settings-persistence pattern and best texture-drawing reference.
10. **`PacketSnifferTester.py` / `Active Dialog Viewer.py` / `Native Button Test Harness.py`** —
    small, clean, near-verbatim panels for packets, dialog, and native-UI-creation coverage.
