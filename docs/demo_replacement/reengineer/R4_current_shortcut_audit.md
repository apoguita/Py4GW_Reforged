# R4 — Current DEMO 2.0 Shortcut Audit

Ruthless punch-list of every shortcut, blank-list, address-only render, and reflection/auto-discovery
hack in the CURRENT `Sources/ApoSource/py4gw_demo_src/` implementation. Scope: all section files
**except** the known-good `map_demo.py`, `agent_demo.py`, `pathing_map_demo.py`, `helpers.py`.

Two systemic defects sit under almost everything below and are the reason for the reengineer:

1. **The probe grid renders BLANK on load.** `ui.draw_probe_table()` calls nothing on render —
   every row shows `—` until the user clicks a per-row `probe` button or `Run all`. Any section whose
   only real content is an "Access Probe" tab therefore shows an empty status grid until manually
   poked. This is deliberate (a faulty binding can crash the client), but it means those sections
   present **no data at all** by default.
2. **Nothing writes diagnostics to a file.** Not one section, and not the harness. `ui.py` has no
   file I/O; `probe`/`action_button`/`draw_probe_table` results live only in in-memory dicts
   (`_probe_cache`, `_action_results`) and vanish on reload. A tool whose entire purpose is "test
   access to every binding" produces zero durable output. (File-diag column below is "No" for every
   row — stated once here rather than repeated.)

Reflection/auto-discovery primitives that are the core of the shortcut problem (all in `ui.py`):
- `auto_probe_entries(cls)` — `dir()` + prefix-match (`Get/Is/Has/Count/get_/is_/has_/count_`) +
  `inspect.signature` to pick zero-required-arg callables. No hand list, no per-method knowledge.
- `probe_entries_1arg(cls, arg)` — same, for one-required-arg getters, all bound to a single id.
- `raw_bindings_demo.make_module_view(name)` — a factory that turns ANY module name into a section
  using `auto_probe_entries` + a `getattr`/`dir()` "other callables" dump. Used for **13** sidebar
  sections (see registry).
- `contexts_demo` — `vars(GWContext)` reflection to discover facade classes, then
  `type(struct)._fields_` + `getattr` to dump ctypes fields.

---

## Audit table

Legend — Render: **real** = casts/formats live typed fields; **address** = shows raw pointers/ints;
**blank** = probe grid empty until user clicks; **mixed** = some real rows + a blank probe grid.
Coverage % is the fraction of the target module's *meaningful* surface (getters + actions) the
section actually wires or displays, distinct from what reflection *could* enumerate on click.

| Section | Module | Render quality | Reflection? | Coverage % | File-diag? | Verdict |
|---|---|---|---|---|---|---|
| Binding Access Tester | 9 wrappers (Player/Map/Party/Inventory/Quest/Camera/AgentArray/Effects/SkillBar) | blank | **Yes — `auto_probe_entries` only** | ~40% (no-arg getters only; zero actions, zero arg-getters) | No | **Total rewrite** — a generic reflection dump masquerading as coverage of 9 modules |
| Raw Bindings Explorer | 20 Py* modules via combo | blank | **Yes — `auto_probe_entries` per selected module** | ~15% (only module-level no-arg fns; most surfaces are class-based → empty) | No | **Total rewrite** |
| Ping / Latency | `PyPing.PingHandler` | real (4 values, but blank until probed) | No | ~80% (4 getters; that is the whole handler) | No | Salvageable |
| Combat Events | `CombatEvents` / `CombatEventQueue` | mixed (3 real queue rows + blank probe) | **Yes — `auto_probe_entries(CombatEvents)`** | ~50% (control actions + queue rows real; event queries hidden behind reflection) | No | Salvageable w/ rework |
| Packet Sniffer | `PacketSniffer.SNIFFER` | real (log table renders live) | No | ~70% (init/term/clear + logs; decode/per-type filters absent) | No | Salvageable |
| Callbacks | `PyCallback.PyCallback` | real (registry table live) | No | ~60% (pause/resume/clear + info; register/trigger absent) | No | Salvageable |
| Profiler | `PyProfiler` | real but `getattr(mod, x, lambda...)` guessed API | No (but defensive `getattr` fallbacks = API guessing) | ~50% (no stub; names/reports/reset only) | No | Salvageable w/ verification |
| Scanner | `Scanner` / `ScannerSection` | address (section ranges as `0x…`; that is correct here) | No | ~70% (ranges + IsValidPtr + init; scan/find methods absent) | No | Salvageable |
| Settings | `PySettings` | real (doc/section/items dump) | No (but `getattr` fallbacks for env fns) | ~55% (read-only inspect; no set/write path) | No | Salvageable |
| System (PySystem) | `PySystem` | blank | **Yes — `make_module_view`** | ~10% (whatever no-arg getters exist; likely near-empty) | No | **Total rewrite** |
| Game Thread (PyGameThread) | `PyGameThread` | blank / likely empty | **Yes — `make_module_view`** | ~5% (enqueue is action-shaped, not a getter → "surface is class-based" message) | No | **Total rewrite** |
| Agent Array | `AgentArray` | mixed (real Counts kv-table + blank probe) | Partial — hand list `_ARRAYS` (12), no reflection | ~85% of array getters (but zero non-array AgentArray surface) | No | Salvageable (Counts table is genuinely good) |
| Agent Recolor (PyAgentRecolor) | `PyAgentRecolor` | blank | **Yes — `make_module_view`** | ~10% (class-based; recolor is action API → empty getter grid) | No | **Total rewrite** |
| Name Obfuscator (PyNameObfuscator) | `PyNameObfuscator` | blank | **Yes — `make_module_view`** | ~10% | No | **Total rewrite** |
| Player | `Player` | mixed (Identity/Progression real kv-tables; Actions real; Access Probe blank hand-list) | No (hand `_GETTERS` of 29) | ~70% getters shown live + broad actions; some getters only in probe tab | No | **Salvageable — best-in-class template** |
| Party | `Party` | mixed (Summary + Rosters real; probe tab reflection) | **Yes — `auto_probe_entries(Party)` for probe tab** | ~65% (good summary; probe tab is reflection filler) | No | Salvageable |
| Guild (PyGuild) | `PyGuild` | blank | **Yes — `make_module_view`** | ~10% | No | **Total rewrite** |
| Friend List (PyFriendList) | `PyFriendList` | blank | **Yes — `make_module_view`** | ~10% | No | **Total rewrite** |
| Chat (PyChat) | `PyChat` | blank | **Yes — `make_module_view`** | ~10% | No | **Total rewrite** |
| Inventory | `Inventory` (41 methods) | mixed (9-field summary + 5 actions real; probe tab reflection) | **Yes — `auto_probe_entries(Inventory)` for probe tab** | ~35% (summary hits ~9/41; bags/slots/item enumeration absent) | No | **Total rewrite** (grossly under-covers a 41-method module) |
| Item | `Item` + 5 nested classes | mixed (7-field Common real; sub-namespaces reflection) | **Yes — `probe_entries_1arg` + `getattr` over `_SUBSPACES`** | ~50% (Common real; Rarity/Properties/Type/Usage/Customization are blank 1-arg reflection) | No | Salvageable w/ rework (subject-id pattern is sound) |
| Skill | `Skill` + 5 nested classes | mixed (5-field Common real; sub-namespaces reflection) | **Yes — `probe_entries_1arg` + `getattr` over `_SUBSPACES`** | ~45% (Data/Attribute/Flags/Animations/ExtraData blank until probed) | No | Salvageable w/ rework |
| Skillbar | `SkillBar` | mixed (8 slot rows real; probe tab reflection) | **Yes — `auto_probe_entries(SkillBar)` for probe tab** | ~50% (slots + use-skill real; rest reflection) | No | Salvageable |
| Effects / Buffs | `Effects` | real (player-bound kv-table + hand probe list) | No (hand entries, but only 5) | ~40% (player-bound only; no per-agent/other-agent, no effect decode) | No | Salvageable w/ rework |
| Merchant / Trading | `Trading` (Trader/Merchant/Crafter/Collector) | mixed (GetOfferedItems per tab + actions real) | No | ~55% (shows only `GetOfferedItems`; misses `GetOfferedItems2`; Crafter `CraftItem` passes empty lists) | No | Salvageable w/ rework |
| Camera | `Camera` | blank (State tab is pure probe) + real Control actions | **Yes — `auto_probe_entries(Camera)` for State tab** | ~50% (all state hidden behind reflection/click; controls real) | No | Salvageable w/ rework |
| Dialog | `Dialog` (+`Player.SendDialog`) | real (active dialog + buttons table live) | No | ~70% (active dialog + send; take/dialog-at absent) | No | Salvageable |
| Quest | `Quest` | mixed (Summary + Inspect real; probe tab reflection) | **Yes — `auto_probe_entries(Quest)` for probe tab** | ~70% (good inspect coverage) | No | Salvageable |
| UIManager / Frames | `UIManager` (187 methods) | blank (no-arg probe) + blank (1-arg frame probe) + real Logs | **Yes — `auto_probe_entries` AND `probe_entries_1arg`** | ~20% (both main tabs are reflection; nothing rendered until click) | No | **Total rewrite** (187-method module reduced to two blank reflection grids) |
| Preferences | `UIManager` preference API | real (typed get + options + set + keymap) | No (hand type map) | ~75% (typed pref read/write covered well) | No | **Salvageable — good template** |
| Native Contexts | `GWContext` (15 facades) | address (Pointer as `0x…`) + real struct-field dump | **Yes — `vars(GWContext)` + `_fields_`/`getattr` dump** | ~85% of facade contexts; GameContext/TextParser explicitly deferred | No | Salvageable (field dump is genuinely useful; reflection here is defensible) |
| Keystroke | `PyKeystroke.PyKeyHandler` | real (press/release/push actions) | No | ~90% (whole handler is 3 methods) | No | Salvageable |
| Trade P2P (PyTrade) | `PyTrade` | blank | **Yes — `make_module_view`** | ~10% | No | **Total rewrite** |
| DXOverlay (PyDXOverlay) | `PyDXOverlay` | blank | **Yes — `make_module_view`** | ~5% (draw API is class/action based → empty getter grid) | No | **Total rewrite** |
| Textures (PyTexture) | `PyTexture` | blank | **Yes — `make_module_view`** | ~5% | No | **Total rewrite** |
| Render (PyRender) | `PyRender` | blank | **Yes — `make_module_view`** | ~5% | No | **Total rewrite** |
| Overlay | `Overlay` | real (mouse kv-table + live world-space ring/target draws) | No | ~40% (rings + target marker + mouse; large Draw* API subset) | No | **Salvageable — genuinely functional** |

---

## Worst offenders

1. **`make_module_view` sections (13 of them).** PySystem, PyGameThread, PyAgentRecolor,
   PyNameObfuscator, PyGuild, PyFriendList, PyChat, PyTrade, PyDXOverlay, PyTexture, PyRender —
   plus the "Raw Bindings Explorer" and "Binding Access Tester" which are the same idea with a
   dropdown. These are the single largest shortcut: one 22-line factory stamps out a whole third
   of the sidebar. Each renders a **blank** probe grid of "no-arg module-level getters," and because
   almost all of these modules are **class/constructor/action-based**, `auto_probe_entries` returns
   an empty list → the section shows *"No zero-arg module-level getters (surface is class-based)"*
   and a comma-joined dump of callable names. That is a section-that-covers-nothing. Every one of
   these is a **total rewrite** requiring real per-class instantiation and per-method wiring.

2. **UIManager (187 methods → two blank reflection grids).** The biggest real module in the demo is
   reduced to `auto_probe_entries` (no-arg) and `probe_entries_1arg` against a single frame id, both
   blank until clicked. No frame tree, no child/parent navigation, no message send. Total rewrite.

3. **Inventory (41 methods → 9-field summary).** Under-covers by design; the "Access Probe" tab is
   reflection filler that hides the gap. No bag/slot/item enumeration at all. Total rewrite.

4. **The universal blank-probe pattern.** ~15 sections' primary or only content is a
   `draw_probe_table` that shows `—` for every row until manually run. On first open, these sections
   look empty/broken. Even where a section has a good real table (Player, Party, Skillbar, Quest,
   Camera), an "Access Probe" tab is bolted on as reflection padding rather than curated coverage.

5. **Zero file diagnostics, repo-wide.** For a tool sold as "test access to every binding and see
   which resolve," the complete absence of any exported/logged result is a structural miss — nothing
   survives a reload, nothing can be diffed across builds.

## Total rewrites vs salvageable

**Total rewrites (14):** Binding Access Tester, Raw Bindings Explorer, System (PySystem),
Game Thread (PyGameThread), Agent Recolor, Name Obfuscator, Guild, Friend List, Chat, Inventory,
UIManager/Frames, Trade P2P, DXOverlay, Textures, Render. (All 13 `make_module_view`/dropdown
reflection sections + Inventory + UIManager.)

**Good templates to keep/generalize (4):** **Player** (real Identity/Progression tables + curated
action buttons — the shape every module should follow), **Preferences** (typed get/set with options),
**Overlay** (actually exercises world-space drawing), **Native Contexts** (real ctypes field dump;
reflection is defensible here because struct fields are uniform).

**Salvageable with rework (the remainder):** Ping, Combat Events, Packet Sniffer, Callbacks,
Profiler, Scanner, Settings, Agent Array, Party, Item, Skill, Skillbar, Effects, Merchant, Camera,
Dialog, Quest, Keystroke. Common rework: replace the bolted-on reflection "Access Probe" tabs with
curated live tables, and add durable/file diagnostics.

**Cross-cutting fixes for the reengineer:** (a) render live values by default instead of blank
probe grids (keep click-to-run only for the handful of genuinely crash-prone bindings, flagged
explicitly); (b) delete `make_module_view` and hand-write each Py* module section against its real
class API; (c) treat `auto_probe_entries`/`probe_entries_1arg` as a *supplementary* completeness
check, never as a section's primary content; (d) add a file-backed diagnostic export to the harness.
