# DEMO 2.0 Build Plan — Every Module → A View

Synthesis of docs 06–10. Goal: finish DEMO 2.0 so it exercises **every** binding module, wrapper getter, and context. This maps each backend module to a demo section, names the **data path** to use, the **existing script to harvest from**, and a **phase/priority**.

Scope tally to cover: **23 gameplay bindings** (doc 06) + **17 infra/IO bindings** (doc 07, PyImGui deferred) + **18 contexts** (doc 08), surfaced through **25 wrappers** (doc 10). DEMO 2.0 today covers only Map, Agents, AgentArray, Pathing.

---

## 0. Foundation (do first — shared primitives)

Standardize these before adding sections; nearly every panel depends on them.

| Primitive | Source to lift | Notes |
|---|---|---|
| View registry / sidebar | current `helpers.py` `VIEW_LIST`/`SECTION_INFO`; extend to grouped tree | Sidebar needs **grouping** (see §4) — flat list won't scale to ~35 sections. |
| `draw_kv_table` (2-col field/value) | `py4gw_demo_src/helpers.py` | The base table. Make it a demo primitive. |
| `draw_multi_table` (N-col scrollable) | `UI_Listener.py` | For logs/arrays. |
| striped table | `SharedMem Monitor.py` `begin/end_striped_table` | |
| `draw_dword_probe_table` (dec/hex/bytes/ascii/wchar/float + PTR heuristic) | `Scanner Test.py` | For raw context/struct dumps (§3). |
| `_draw_sparkline` + stacked bar + deterministic palette | `System Monitor.py` | For ping/profiler/live-metric panels. Zero legacy facade. |
| "run-a-method, cache & color the result" harness | `Frame_Showcase.py` `UIManagerAPITester` (`_exec`/`_run_button`/`_section_header`) | **The generic getter/action test pattern** — generalize beyond UIManager into the demo's core. |
| `_colored_bool` green/red | `Agent Info.py` | Boolean predicate display everywhere. |
| "not available in this context" affordance | ad hoc in v1/`map_demo` | One consistent helper: gate panels on outpost/explorable/map-ready/window-open/hard-mode. |
| tick→timestamp anchor | `UI_Listener.py` `tick_to_timestamp` | For event/log views (no `datetime.now()` jitter). |
| Settings persistence lifecycle | `Icon Explorer.py` (`_load_settings`/`_save_setting`, `INI_KEY` from `Settings(...).name`) | Canonical Reforged `PySettings` pattern. See [[settings-self-throttled]]. |
| **ImGui facade migration** | — | Re-express every `ImGui_Legacy.*` call against `Py4GWCoreLib.ImGui`; raw `PyImGui.*` ports as-is. No bridging. `agent_demo.py`/`tooltip()` still leak legacy. See [[imgui-migration-dropped-bindings]]. |

**Panel shape rule:** every section is a `draw_*_view()` **function that draws into the host child region** (no own `begin/end`), like `agent_demo.draw_agents_view` — never a floating window (v1's mistake).

---

## 1. Phase 1 — Restore v1 breadth on the new surface

Domains v1 covered that v2 dropped. Highest value: brings the demo back to feature parity.

| Section | Bindings | Data path | Harvest from | Getters/Actions |
|---|---|---|---|---|
| **Player** | PyPlayer | `Player.*` (context path) + `GLOBAL_CACHE` | v1 `ShowPlayerWindow`; `AccountData.py` player tab | data/titles/faction (get) · dialog/chat/whisper/target/interact/move/deposit (act) |
| **Party** | PyParty | `Party.*` (Players/Heroes/Henchmen/Pets) | v1 `ShowPartyWindow` | roster (get) · invite/kick/flag/behavior/tick/mode (act) |
| **Item** | PyItem | `Item.*` (Rarity/Properties/Type/Usage/Customization/Modifiers/Dye) | v1 `ShowItemDataWindow`; `SkillInfo.py` texture-card style | mostly get · RequestName (async) |
| **Inventory** | PyInventory | `Inventory.*` + `GLOBAL_CACHE.Inventory` | v1 `ShowInventoryWindow` | kits/gold/first-* (get) · identify/salvage/xunlai (act) |
| **Skill** | PySkill | `Skill.*` (Data/Attribute/Flags/Animations/ExtraData) | `SkillInfo.py` ★ (cards, textures, progression resolver); v1 `ShowSkillDataWindow` | pure get; ~60 fields |
| **Skillbar** | PySkillbar | `Skillbar.*` + `GLOBAL_CACHE.SkillBar` | v1 `ShowSkillbarWindow` (+ hero bars) | slots (get) · UseSkill/HeroUseSkill (act) |
| **Effects/Buffs** | PyEffects | `Effect.*` + `GLOBAL_CACHE.Effects` | v1 `ShowEffectsWindow` | buffs/effects (get) · DropBuff (act) |
| **Merchant/Trade(NPC)** | PyMerchant | `GLOBAL_CACHE.Trading.*` (Trader/Merchant/Crafter/Collector) | v1 `ShowMerchantWindow` | offered items/quotes (get) · buy/sell/craft/exchange (act) |
| **Quest** | PyQuest | `Quest.*` + `GLOBAL_CACHE.Quest` | v1 `ShowQuestWindow`; `Quest Data.py` | active/log (get, async strings) · set/abandon (act) |

---

## 2. Phase 2 — Net-new backend (never demoed in v1 OR v2)

The large untested surface. Each becomes a new section; most have a ready harvest source.

| Section | Bindings | Data path | Harvest from | Notes |
|---|---|---|---|---|
| **UI Frames / UIManager** ★ | PyUIManager | `UIManager.*`, `GWUI` | `Frame_Showcase.py` ★ (`UIManagerAPITester`, `FrameTree`, `FrameInspector`) | Biggest binding surface (~130 methods). Frame tree + generic method tester + log monitor + visual toolkit. |
| **Preferences / Game Config** | PyUIManager prefs | `UIManager.Get/Set*Preference`, key mappings, window pos/vis | `GameConfigViewer.py` ★ (`Preferences` model, `probe_*`) | Typed pref get/set + ID probing. |
| **Combat Events / Listeners** ★ | PyAgentEvents, PyListeners | `CombatEvents.*` | `CombatEventsTester.py` ★ (`register_callbacks`, `EventLog`, query tabs) | Fix `PyAgentEvents` vs `PyCombatEvents.GetCombatEventQueue()` bug on harvest. |
| **Overlay (2D/3D)** | PyOverlay | `Overlay()` | `map_demo.py` `DisplayNode`/`DrawFlagAll`; v1 area-rings | Toggleable debug-draw showcase. |
| **DXOverlay** | PyDXOverlay | `DXOverlay.*` | v1 (none) — build fresh from doc 07 | DirectX primitives/text; pair with Overlay section. |
| **Textures** | PyTexture | `TextureManager`/`ImGui` draw | `SharedMem Monitor.py` (UV atlas, `DrawTextureExtended`), `SkillInfo.py` | Load .dat + file textures, atlas slicing. |
| **Keystroke / Mouse** | PyKeystroke, PyMouse | `Keystroke.*` | v1 `ShowPy4GW_Window_main` keystroke table | press/release/push + mouse inject. |
| **Ping / Latency** | PyPing | `PyPing.PingHandler` | v1 (4 getters); `System Monitor` sparkline | current/avg/min/max + sparkline. |
| **Camera** | PyCamera | `Camera.*` | build fresh (doc 10 shows getters+actions) | pos/yaw/pitch (get) · control (act). |
| **Dialog** | PyDialog | `Dialog.*` | `Active Dialog Viewer.py` ★ | active dialog + buttons + send. |
| **Player Trade (P2P)** | PyTrade | (no wrapper — call binding) | build fresh (8 funcs, doc 06) | needs a partner; gate on trade-open. |
| **Packet Sniffer** | PyPacketSniffer | `PacketSniffer.SNIFFER` | `PacketSnifferTester.py` ★ | start/stop/dump StoC/CToS. |
| **Callbacks** | PyCallback | `PyCallback` | `Callback Monitor.py` ★ | registry + pause/resume. |
| **Profiler** | PyProfiler | `PyProfiler` | `System Monitor.py` ★ | metric catalog + charts. |
| **Game Thread** | PyGameThread | `PyGameThread.enqueue` | `Native Button Test Harness.py` | enqueue + read-back-after-delay demo. |
| **Scanner / Native funcs** | PyScanner | `native_src` NativeFunction | `Scanner Test.py` ★ (`draw_dword_probe_table`) | signature scan + ctypes probe. |
| **Settings** | PySettings | `Settings` | `Icon Explorer.py` ★ | get/set + persistence lifecycle. |
| **System / Console** | PySystem | `PySystem.*` | v1 logging; doc 07 submodules | Console/env/window/script-control/widget-manager subs. |
| **Guild** | PyGuild | (no wrapper) | build fresh (5 funcs) | small. |
| **Friend List** | PyFriendList | (no wrapper) | build fresh | small. |
| **Name Obfuscator** | PyNameObfuscator | — | build fresh | anonymization toggle. |
| **Agent Recolor** | PyAgentRecolor | — | build fresh | model recolor demo. |
| **Chat (direct)** | PyChat | (v1 via Player) | build fresh (14 funcs) | send/receive channels. |
| **Render** | PyRender | — | build fresh | present-hook state (read-only). |

---

## 3. Phase 3 — Context path panel

A dedicated **Contexts** section that dumps every `native_src/context` reader via `draw_dword_probe_table`, choosing raw-struct or wrapper-facade per context (doc 08).

- **Wrapper-exposed (15)** via `GWContext.GetContext()`/`.IsValid()`: AccAgent, AgentArray, AvailableCharacterArray, Char, Cinematic, Gameplay, Guild, InstanceInfo, Map, MissionMap, Party, PreGame, ServerRegion, World, WorldMap — show through the friendly facade.
- **Raw-only (2):** GameContext (no facade; via `SSM.GameContext`), TextParser — show raw struct.
- Reuse the Pregame context dump already in `map_demo.draw_pregame_tab` as the template.

---

## 4. Proposed sidebar taxonomy (grouped)

Flat `VIEW_LIST` won't scale to ~35 sections. Group by native-module family:

```
Core / System      → System, Settings, Callbacks, Profiler, GameThread, Scanner, Render
World & Map        → Map, MissionMap, MiniMap, WorldMap, Pregame, Pathing, Contexts
Agents             → AgentArray, Agents, AgentRecolor, NameObfuscator
Combat & Skills    → Skill, Skillbar, Effects, CombatEvents/Listeners
Items & Inventory  → Item, Inventory, Textures
Party & Social     → Party, Guild, FriendList, Chat
Trading & NPC      → Merchant, Trade(P2P), Dialog, Quest
Player             → Player, Ping, Keystroke/Mouse
UI & Frames        → UIManager/Frames, Preferences
Rendering          → Overlay, DXOverlay
Low-level / RE     → Scanner, PacketSniffer
Deferred           → ImGui gallery (§5)
```

---

## 5. Deferred — ImGui gallery (own pass)

Per user: **PyImGui + addons is a later, dedicated pass.** Doc 07 has the high-level map (8 binding files, ~359 core funcs, 6 addon submodules, ~204 enum values). v1's `ShowPyImGuiDemoWindow` (selectables/inputs/tables/misc + `show_demo_window`) and `ImGui Official DEMO.py` are the checklist when that pass starts. Not in the main build.

---

## 6. Suggested execution order

1. **Foundation (§0)** — primitives + facade migration + grouped sidebar. Nothing else lands cleanly without this.
2. **Phase 1 (§1)** — parity restore; each maps to a v1 `Show*Window` to port (view-function shape, new facade).
3. **Phase 2 high-value (§2)** — UIManager/Frames, CombatEvents, Preferences, Overlay, Ping, Dialog, PacketSniffer, Settings, Profiler/Callbacks (all have ★ harvest sources).
4. **Phase 2 fresh-build (§2)** — Camera, Trade, Guild, FriendList, Chat, Render, NameObfuscator, AgentRecolor, DXOverlay, Textures, Scanner, GameThread, System.
5. **Phase 3 (§3)** — Contexts panel.
6. **Deferred (§5)** — ImGui gallery pass.

Each section is independently shippable once Foundation exists — good for incremental, one-at-a-time delivery (matches [[launchbar-iterative-workflow]] preference: basics first, one feature at a time).

---

## 6b. Safety model (learned from a client crash)

**Never auto-invoke bindings on render.** A native binding can dereference invalid memory and
crash the *client* with an access violation (`0xc0000005`) that Python `try/except` (and thus
`probe()`) **cannot** catch. The first Access Tester build called every getter via reflection
every frame (an `ok_count` loop + the probe table both calling all entries) — clicking it reached
`Player.GetInstanceUptime → Agent.GetInstanceUptime → UIManager.GetFPSLimit →
PyUIManager.get_frame_limit()` and crashed. `get_frame_limit()` itself is fine (the frame limiter
calls it once/frame); the fault was auto-hammering arbitrary bindings from inside the draw pass.

Rules now enforced:
- **`draw_probe_table` is opt-in**: nothing is called on render; each getter runs only on its
  per-row **Run** button (or an explicit **Run all**, which carries a "may crash" warning). Results
  are cached in `ui._probe_cache`.
- **No bulk auto-call loops** (`sum(... probe ...)` etc.) — removed.
- Curated data tables still call their small, hand-picked getter set once/frame (same as any
  widget); only the comprehensive reflection grids are gated behind explicit Run.

## 7. Progress log

**Package:** `Sources/ApoSource/py4gw_demo_src/`. Entry: `Py4GW DEMO 2.0.py`. **No `ImGui_Legacy`** — raw `PyImGui` only. ImGui addons deferred to their own pass.

Done:
- **§0 Foundation** — `ui.py`: `draw_kv_table`, `draw_multi_table`, `colored_bool`, `section_header`/`text_muted`, and the **access-probe harness** (`probe`, `draw_probe_table`, `action_button`, `not_available`) + reflection `auto_probe_entries(cls)` that auto-discovers a wrapper's no-arg getters. `registry.py`: grouped sidebar + router (each section is a `draw_*_view()` into the host child region; per-panel try/except keeps the widget alive). Root entry rewired to grouped nav; legacy-free tooltip.
- **De-legacy** — `agent_demo.py` `ImGui_Legacy.table` → `ui.draw_multi_table`; legacy import + dead `WindowModule` removed.
- **Core / System** — `access_tester.py`: generic **Binding Access Tester** (pick a wrapper → auto-probe every no-arg getter live; OK/ERR grid). Introspects Player/Map/Party/Inventory/Quest/Camera/AgentArray/Effects.
- **Phase 1 sections** (probe-first + curated tables + action buttons): `player_demo.py` (Player), `party_demo.py` (Party), `inventory_demo.py` (Inventory), `quest_demo.py` (Quest, incl. async string request/ready/get), `effect_demo.py` (Effects, player-bound). All syntax-checked via `py_compile`.

Then (also done, same build):
- **Access harness extensions** — `auto_probe_entries(cls)` now also matches snake_case native getters; `probe_entries_1arg(cls, arg)` binds a subject id to every one-arg getter (powers Item/Skill sub-namespace probes and the UIManager per-frame inspector).
- **Phase 1 complete** — `item_demo` (subject id = hovered; probes Item + Rarity/Properties/Type/Usage/Customization), `skill_demo` (subject id = hovered; probes Skill + Data/Attribute/Flags/Animations/ExtraData), `skillbar_demo` (slots + use-skill actions), `merchant_demo` (Trader/Merchant/Crafter/Collector tabs).
- **Phase 2** — `camera_demo` (getter-rich probe + control), `dialog_demo` (active dialog + buttons + send), `ping_demo` (PyPing, lazy), `packet_demo` (PacketSniffer SNIFFER lifecycle), `combatevents_demo` (queue control + query probe), `overlay_demo` (world-space area rings + target marker), `uimanager_demo` (no-arg probe + generic per-frame inspector via 1-arg prober + logs).
- **Raw Bindings Explorer** (`raw_bindings_demo`) — pick any native `Py*` module (System/Profiler/Callback/Scanner/GameThread/Guild/FriendList/Chat/Trade/Render/Texture/Settings/NameObfuscator/AgentRecolor/DXOverlay/…) and access-probe its no-arg getters. This gives the remaining infra modules test coverage without a hand-built panel each.
- **Phase 3 Contexts** (`contexts_demo`) — GWContext facade path: per-context GetPtr (pointer source) + IsValid + full ctypes struct-field dump for all 15 facade contexts. GameContext/TextParser (raw-only) + ShMem-sourced contexts noted for a follow-up.

Then (also done, same build): dedicated panels for **Callbacks** (PyCallback), **Profiler** (PyProfiler), **Scanner** (PyScanner section ranges + IsValidPtr), **Settings** (PySettings document dump), **Preferences** (UIManager Get/Set*Preference by id), **Keystroke** (PyKeystroke.PyKeyHandler). Plus a `make_module_view(name)` factory in `raw_bindings_demo` that gives **every remaining native module its own sidebar section** via failure-safe getter-probing + action/class listing: **System, GameThread, Guild, FriendList, Chat, Trade(P2P), DXOverlay, Textures, Render, AgentRecolor, NameObfuscator**.

**Status: 44 sections registered — build plan complete.** Coverage: all **23 gameplay `Py*` modules** and ~**15 infra modules** each have a section; **Contexts** panel dumps all 15 facade contexts (pointer + struct). Every module is at minimum access-probeable; ~28 have hand-built curated+action panels.

Deferred / follow-up polish (not blocking coverage — each module already has a section): **PyImGui gallery** (deferred by user), rich Frame-tree tester (`Frame_Showcase.py`), Profiler sparklines (`System Monitor.py`), DXOverlay/Texture *draw* showcases (currently getter-probe only), dedicated Mouse panel, GWUI native-window creation (`Native Button Test Harness.py`), and the raw/ShMem-sourced contexts (GameContext/TextParser + `GLOBAL_CACHE.ShMem`). Verification is in-client only (offline = `py_compile`, all green).
