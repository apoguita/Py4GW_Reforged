# DEMO 2.0 — Reengineer Spec (APPROVAL GATE)

This is the design contract for the complete reengineer of the Py4GW binding debug/visualization
tool. **No code is written until this is approved.** It is synthesized from the four research
artifacts in this folder:

- **R1** — gold-standard call → cast → render recipes from the original v1 demo + the known-good v2
  modules (`map_demo`, `agent_demo`, `pathing_map_demo`).
- **R2** — authoritative per-module method inventory (~1,500 methods across 38 `Py*` modules) — the
  100% coverage checklist.
- **R3** — the wrapper casting layer (how a raw struct/pointer/handle becomes readable fields).
- **R4** — ruthless audit of the current shortcut-heavy build.

---

## 0. Goals & non-negotiables (from the user)

1. **This is a debug/visualization tool to exercise and LOG the backend.** Its job is to *provide
   the elements* so the user can invoke every shared method and capture its result to file. The user
   drives testing at their own pace; the tool never drives a test process.
2. **Cover EVERY shared method** of every module (except PyImGui — deferred), not a subset.
3. **No auto-discovery / reflection.** Delete `auto_probe_entries`, `probe_entries_1arg`,
   `make_module_view`, and the `fmt_value`/`repr` fallback. Every method is wired by hand from the
   R2 checklist, using the R1/R3 cast recipe. Reflection is not even a "supplementary" fallback.
4. **Cast structs into real objects — never show a bare address.** Every struct return is
   dereferenced into named fields; enums resolve to names; bitfields render dec/hex/bin; pointers
   render as `0x%08X`; `(id, name)` tuples render `[id] - name`.
5. **Per-section "Dump to file" diagnostics** — a manual button per section, writing a readable
   snapshot to a **root-level `./demo_diagnostics/`** folder (NOT inside the source tree). The dump
   reuses the exact same casts the panel renders, so the log is readable, not raw reprs.
6. **Never auto-invoke crash-prone bindings on render.** Curated known-safe getters called once/frame
   are fine (the original demos do this). Genuinely crash-prone bindings are click-to-run and flagged.
7. **Faithful to the originals** (`Py4GW_DEMO.py`, DEMO 2.0's good modules) in shape and idiom.

---

## 1. Architecture

### 1.1 Package: `Sources/ApoSource/py4gw_demo_src/`

**Kept as-is (already correct, per R1/R4):**
- `map_demo.py`, `agent_demo.py`, `pathing_map_demo.py`, `helpers.py`

**Rewritten:**
- `ui.py` → the **render/cast kit** (below). Generic `fmt_value`/`repr` fallback and the entire
  probe/reflection harness are **removed**.
- `registry.py` → grouped sidebar + dispatch, unchanged in shape but pointing at the new sections.

**New infrastructure:**
- `diagnostics.py` → the file-dump kit (below).
- `casts.py` → the shared cast strategies from R3 (M1–M4): struct widening, enum→name registry,
  encoded-string decode, handle-accessor helpers, `ptr`/`bitfield`/`id_name` formatters.

**Deleted (reflection shortcuts):**
- `raw_bindings_demo.py` (the `make_module_view` factory — 13 blank sections), `access_tester.py`.
- The reflection "Access Probe" tabs inside every `*_demo.py` are removed; those files are rewritten
  as explicit curated sections (see §4).

### 1.2 Section contract (every section obeys this)

Each domain lives in one module `<name>_view.py` exposing:

```python
def build_<name>() -> list[Block]      # pure: calls getters, casts, returns display blocks
def draw_<name>_view() -> None         # renders build_<name>() into host child + action buttons + Dump button
```

- `Block` = `(title: str, kind: str, rows: list[tuple])` where `kind` ∈ {`kv`, `multi`, `bools`}.
  Rows are **already-cast strings** (the cast happens in `build_*`, never in the renderer — R1 §0).
- `draw_*_view` renders the blocks, then renders **action/mutator buttons** (explicit triggers, never
  auto-fired), then a single **"⧉ Dump to file"** button wired to `diagnostics.dump(name, build_*())`.
- No section opens its own window; all draw into the host child. `registry.draw_content` keeps the
  per-section `try/except` so one panel can't kill the widget (R1 §15).

Because `build_*` returns the same blocks the panel shows AND the dump serializes, **render and dump
never diverge** — the log is exactly what's on screen, fully cast.

### 1.3 Render/cast kit — `ui.py` + `casts.py`

`ui.py` (renderers only, all consume pre-cast strings):
- `kv_table(id, rows)` — 2-col Field/Value.
- `multi_table(id, headers, rows)` — N-col.
- `bool_grid(id, items)` — colored `text_colored` green/red per bool (agent_demo idiom, R1 §2).
- `text_muted`, `not_available`, section headers.
- **Removed:** `fmt_value`, `draw_probe_table`, `probe`, `action_button`, `auto_probe_entries`,
  `probe_entries_1arg`, `_probe_cache`.

`casts.py` (the R3 mechanisms, used by every `build_*`):
- `ptr(v) -> "0x%08X"` (R1 `_fmt_ptr`).
- `id_name(id, name) -> "[id] - name"`; `id_name_tuple(t)` for `(id,name)` returns.
- `bitfield(v) -> (dec, hex, bin)` for the 3-col dec/hex/bin render.
- `enum_name(EnumType, value)` → resolves via `enums_src` `_Names` dicts, guards `ValueError`→"Unknown".
- `widen_agent(agent)` → picks `GetAsAgentLiving/Item/Gadget()` by `type` (R3 §2 — the #2 trap).
- `decode_enc(...)` → M3 encoded-string decode (both encoded + decoded forms).
- `handle_fields(handle, accessors)` → M4: call a known accessor list on a `Py*` handle, never repr it.

### 1.4 Diagnostics kit — `diagnostics.py`

- `dump(section_name: str, blocks: list[Block]) -> str` — serializes blocks to readable text and
  writes `./demo_diagnostics/<section>_<stamp>.txt` (stamp = `PySystem.get_tick_count64()`, falling
  back to a module-level incrementing counter). Returns the path; logs it to the Py4GW console.
- All file I/O wrapped in `try/except`; a failed write logs an error, never crashes the widget.
- Folder is created lazily on first dump (root-level `./demo_diagnostics/`).
- Format: a header (`section`, stamp, map/instance line), then each block's title + its rows as
  aligned `field : value` lines. Same cast strings as the panel.
- **Manual only** (per your decision): one button per section. No auto-log, no global dump-all.

### 1.5 Data-source rule (R3 §15)

All enrichment (enum→name, `(id,name)`, context deref, string-table lookup) lives **once in the base
`Py4GWCoreLib` wrappers**. GlobalCache does NOT cast richer. So `build_*` calls the **base wrappers**
(`Agent.*`, `Player.*`, `Map.*`, …), not raw `Py*` bindings and not GlobalCache — except where a
section's explicit purpose is to exercise the raw binding surface (Context path, Scanner, Callbacks,
etc.), which read the native structs directly per R3 §1.

---

## 2. Coverage model (how "every method" is satisfied)

Per R2, each module's methods fall into three buckets; each has a fixed rendering treatment:

| Bucket | Treatment | Auto-invoked on render? |
|---|---|---|
| **Data getter** (no-arg or subject-id) | Live row in a `build_*` block, fully cast | Yes — once/frame, known-safe (like original demos) |
| **Action / mutator** (queues action, returns void/bool) | Explicit labeled **trigger button**, with input fields for its args | **No** — user clicks to fire |
| **Crash-prone / unverified getter** (flagged in R2/R3, e.g. stubbed combat getters) | Click-to-run row, marked "not yet wired" | **No** — explicit run |

Subject-id modules (Item, Skill, Effects, Agent, UIManager frames) get a **subject selector** at the
top (an id input + "nearest/hovered/target" convenience pickers per R1), then every subject-bound
getter renders for that id. This is how a 55-method Item module is fully exercised without reflection.

Coverage is verified against R2: each `<name>_view.py` carries a comment block listing the R2 method
names it wires, so a diff against R2 shows any gap.

---

## 3. Section groups (sidebar) — every module except PyImGui

Modules and counts from R2. "Wrapper" = base `Py4GWCoreLib` module used; "raw" = native `Py*` read
directly (Context/infra surface). Verdict from R4.

### Core / System
| Section | Module(s) (R2 count) | Source | Notes |
|---|---|---|---|
| System | PySystem (65) | raw | Console, tick, threads, env — explicit per-fn; was blank `make_module_view` |
| Game Thread | PyGameThread (3) | raw | enqueue is an action → trigger button |
| Scanner | PyScanner (15) | raw | ranges + IsValidPtr + scan/find (find methods were absent) |
| Callbacks | PyCallback (9) | raw | registry table + register/trigger actions |
| Profiler | PyProfiler (6) | raw | verify API (no stub — R4 flagged `getattr` guessing) |
| Settings | PySettings (30) | raw | add the set/write path (was read-only) |
| Ping / Latency | PyPing (6) | wrapper | render live (was blank until probed) |
| Packet Sniffer | PyPacketSniffer (15) | raw | add decode / per-type filters |
| Combat Events | PyAgentEvents (10) | raw | **fix orphaned stub** — live surface is `PyAgentEvents`/`PyRawAgentEvent`, not `PyCombatEvents` (R2) |
| Listeners | PyListeners (6) | raw | new — not currently a section |

### World & Map (KEEP map_demo/pathing — already gold)
| Section | Module (R2) | Source | Notes |
|---|---|---|---|
| Map / Mission / Mini / World / Pregame | PyMap (30) via `Map` | wrapper | keep `map_demo.py` |
| Geo & Pathing | PyPathing (8) | wrapper | keep `pathing_map_demo.py` |

### Contexts
| Section | Module | Source | Notes |
|---|---|---|---|
| Native Contexts | GWContext (15 facades) | raw (M1) | keep field-dump; add GameContext/TextParser (R3 §1) |

### Agents (KEEP agent_demo — gold)
| Section | Module (R2) | Source | Notes |
|---|---|---|---|
| Agent Array | AgentArray | wrapper | keep Counts table; ids feed `Agent.*` |
| Agents | PyAgent (45) via `Agent` | wrapper | keep `agent_demo.py`; ensure `widen_agent` covers item/gadget |
| Agent Recolor | PyAgentRecolor (14) | raw | recolor is action API → trigger buttons (was blank) |
| Name Obfuscator | PyNameObfuscator (23) | raw | explicit (was blank) |

### Player
| Section | Module (R2) | Source | Notes |
|---|---|---|---|
| Player | PyPlayer (28) via `Player` | wrapper | **best-in-class template** — extend to full 28 + title struct cast |

### Party & Social
| Section | Module (R2) | Source | Notes |
|---|---|---|---|
| Party | PyParty (92) via `Party` | wrapper | rosters (players/heroes/henchmen/others/pet) + all tick/mode/flag actions |
| Guild | PyGuild (5) | raw | explicit (was blank) |
| Friend List | PyFriendList (8) | raw | explicit (was blank) |
| Chat | PyChat (13) | raw | send/history actions (was blank) |

### Items & Inventory
| Section | Module (R2) | Source | Notes |
|---|---|---|---|
| Inventory | PyInventory (27) via `Inventory` | wrapper | **total rewrite** — bag/slot enumeration, not a 9-field summary |
| Item | PyItem (55) via `Item` | wrapper | subject-id selector; all sub-namespaces explicit (Rarity/Properties/Type/Usage/Customization/modifiers/dye) |

### Combat & Skills
| Section | Module (R2) | Source | Notes |
|---|---|---|---|
| Skill | PySkill (19) via `Skill` | wrapper | subject-id; Data/Attribute/Flags/Animations/ExtraData explicit |
| Skillbar | PySkillbar (38) via `SkillBar` | wrapper | own bar slots 1-8 + hero bars; `GetSkillData` struct cast |
| Effects / Buffs | PyEffects (19) via `Effects` | wrapper | per-agent selector; buff vs effect id-space split (R3 §11) |

### Trading & NPC
| Section | Module (R2) | Source | Notes |
|---|---|---|---|
| Merchant / Trading | PyMerchant (18) via `Trading` | wrapper | Trader/Merchant/Crafter/Collector; async quote handshake (R3 §8); add `GetOfferedItems2` |
| Trade P2P | PyTrade (8) | raw | explicit (was blank); note stub is fictional (R2) |
| Dialog | PyDialog (39) via `Dialog` | wrapper | active dialog + buttons + take/dialog-at |
| Quest | PyQuest (51) via `Quest` | wrapper | async request/ready/get triad per text field (R3 §12) |

### UI & Frames
| Section | Module (R2) | Source | Notes |
|---|---|---|---|
| UIManager / Frames | PyUIManager (156) | wrapper/raw | **total rewrite** — frame tree + parent/child nav + frame snapshot + message send; ~85 stub methods are unbound legacy (R2) — wire only the real surface |
| Preferences | UIManager preference API | wrapper | **good template** — keep typed get/set |

### Input
| Section | Module (R2) | Source | Notes |
|---|---|---|---|
| Keystroke | PyKeystroke (6) | wrapper | keep (press/release/push) |
| Mouse | PyMouse (6) | raw | new — not currently a section |

### Rendering & Camera
| Section | Module (R2) | Source | Notes |
|---|---|---|---|
| Overlay | PyOverlay (68) via `Overlay` | wrapper | **good template** — extend Draw* coverage; note stub lists wrong methods (R2) |
| DXOverlay | PyDXOverlay (43) | raw | draw API is class/action → trigger buttons + a draw canvas (was blank) |
| Textures | PyTexture (5) | raw | explicit (was blank) |
| Render | PyRender (5) | raw | explicit (was blank) |
| Camera | PyCamera (32) via `Camera` | wrapper | all state floats live + control actions (was blank state tab) |

### Root
| Section | Module (R2) | Notes |
|---|---|---|
| Py4GW / SharedMemory | Py4GW root (5) | version + SharedMemory surface |

**Deferred (explicit, per your instruction):** `PyImGui` (~407 methods) — dedicated gallery pass later.

**No standalone module (documented, not sections):** `context`, `stoc`, `events`, `native_ui` (R2).

---

## 4. Per-section rewrite status (from R4)

- **Total rewrites (14):** System, Game Thread, Agent Recolor, Name Obfuscator, Guild, Friend List,
  Chat, Trade P2P, DXOverlay, Textures, Render, Inventory, UIManager. (Plus deletion of Binding
  Access Tester + Raw Bindings Explorer — their coverage is redistributed into the real per-module
  sections above.)
- **Good templates kept & extended (4):** Player, Preferences, Overlay, Native Contexts.
- **Salvage-with-rework (rest):** replace bolted-on reflection probe tabs with curated live tables +
  full method coverage + the Dump button. (Ping, Combat Events, Packet Sniffer, Callbacks, Profiler,
  Scanner, Settings, Agent Array, Party, Item, Skill, Skillbar, Effects, Merchant, Camera, Dialog,
  Quest, Keystroke.)
- **New sections added:** Listeners, Mouse, Py4GW/SharedMemory.

---

## 5. Migration gaps to surface (from R2), not paper over

The tool should visibly mark these rather than showing wrong/empty data:
- **Native-only (no stub):** PyChat, PyFriendList, PyGuild, PyMap, PyPing, PyNameObfuscator, PyRender,
  PyTexture, PyMouse, PyProfiler, PyListeners — wire from the native `*_bindings.cpp`, not the stub.
- **Stub-only free-fn surfaces missing:** PyEffects (9), PyItem (21), PySkillbar (18), PyQuest (24)
  free functions absent from stubs — include them.
- **Fictional / wrong stubs:** `PyTrading.pyi` (nonexistent class), `PyOverlay.pyi` (~50 real methods
  missing), `PyUIManager.pyi` (~85 unbound legacy methods), `PyCombatEvents.pyi` (orphaned — use
  `PyAgentEvents`). Wire the real native surface; ignore the fictional stubs.
- **Return-type drift:** many Inventory/UIManager/Skillbar/Quest mutators are `-> None` in stubs but
  `bool` in native — render the real bool result.

---

## 6. Build order (each phase = compilable + independently testable by the user)

Testing is the user's; each phase just delivers self-contained testable sections.

1. **Foundation:** `casts.py`, `ui.py` (render kit), `diagnostics.py`, `registry.py` rewire. No
   behavior change to the kept-good sections yet — verify they still render.
2. **Templates first (prove the pattern):** rewrite Player to the full contract (build/draw/dump),
   confirm the shape, then apply it outward.
3. **Salvage-with-rework** domain sections (wrapper-backed): Party, Item, Skill, Skillbar, Effects,
   Inventory, Merchant, Dialog, Quest, Camera, Overlay.
4. **Raw/native sections:** System, Game Thread, Scanner, Callbacks, Listeners, Profiler, Settings,
   Ping, Packet Sniffer, Combat Events, Guild, Friend List, Chat, Trade, Agent Recolor, Name
   Obfuscator, DXOverlay, Textures, Render, Mouse, Py4GW/SharedMemory.
5. **UIManager / Frames** (the 156-method rewrite) last — largest, needs the frame-tree UI.

Each delivered file is `py_compile`-clean before hand-off; runtime verification is yours (open the
section, exercise it, use the Dump button, send me the log).

---

## 7. What I will NOT do

- No reflection/auto-discovery anywhere.
- No auto-firing of actions or crash-prone bindings on render.
- No writing logs into the source tree.
- No touching anything outside `Sources/ApoSource/py4gw_demo_src/`, the root `Py4GW DEMO 2.0.py`,
  and the new root `./demo_diagnostics/` output folder.
- No builds (native DLL is yours to build).

---

## Open items for your approval

1. Package layout (§1.1): `casts.py` + `diagnostics.py` as new files, `ui.py` reduced to a render
   kit, reflection files deleted. OK?
2. Section list (§3): every non-ImGui module gets a section, plus new Listeners / Mouse /
   Py4GW-SharedMemory. Any you want dropped or merged?
3. Build order (§6): foundation → Player template → salvage domains → raw sections → UIManager. OK,
   or a different first target?
