# R2 — Authoritative Binding Method Inventory

**Purpose.** This is the *explicit, authoritative checklist* for the reengineered Py4GW binding-exerciser / debug tool. It enumerates EVERY shared binding method/function of EVERY embedded `Py*` module, cross-referenced against two sources of truth:

1. **Type stubs** — `C:\Users\Apo\Py4GW_Reforged\stubs\*.pyi` (the forward-declaration surface).
2. **Native C++ pybind11 bindings** — the real runtime surface in `C:\Users\Apo\Py4GW_Reforged_Native\src\...` (`*_bindings.cpp`) plus the `include\GW\...` headers that define the struct/class return types.

The tool must exercise the **native** surface (that is what actually exists at runtime); the stub column tells you what a caller *thinks* exists. Where they disagree, the "Stub vs Native disagreements" block flags a migration gap.

For struct-returning methods, the tool must render the **fields** (the "Struct return types & fields" tables), not the object address.

---

## Authoritative module registry

The canonical list of embedded modules is `kEmbeddedModules[]` in
`C:\Users\Apo\Py4GW_Reforged_Native\src\base\python_runtime.cpp` (lines 399-439).
**38 modules** are imported at startup, plus the `Py4GW` root module (with its `SharedMemory` submodule).

| # | Module (import name) | Native binding file | Primary stub | Section |
|---|----------------------|---------------------|--------------|---------|
| — | `Py4GW` (+ `.SharedMemory`) | `src\base\python_runtime.cpp` (PYBIND11_EMBEDDED_MODULE) | none | Root module (below) |
| 1 | `PySystem` | `src\system\system_bindings.cpp` (+ `system_methods.cpp`) | `PySystem.pyi` | b6 |
| 2 | `PySettings` | `src\settings\settings_bindings.cpp` | `PySettings.pyi` | b6 |
| 3 | `PyProfiler` | `src\profiler\profiler_bindings.cpp` | — (none) | b6 |
| 4 | `PyCallback` | `src\callback\callback_bindings.cpp` | `PyCallback.pyi` | b6 |
| 5 | `PyListeners` | `src\listeners\listeners_bindings.cpp` | — (none) | b6 |
| 6 | `PyAgent` | `src\GW\agent\agent_bindings.cpp` | `PyAgent.pyi` | b1 |
| 7 | `PyAgentRecolor` | `src\GW\agent_recolor\agent_recolor_bindings.cpp` | `PyAgentTagColor.pyi` | b1 |
| 8 | `PyCamera` | `src\GW\camera\camera_bindings.cpp` | `PyCamera.pyi` | b5 |
| 9 | `PyChat` | `src\GW\chat\chat_bindings.cpp` | — (none) | b2 |
| 10 | `PyAgentEvents` | `src\listeners\agent_events_bindings.cpp` | `PyAgentEvents.pyi` (legacy `PyCombatEvents.pyi`) | b1 |
| 11 | `PyEffects` | `src\GW\effects\effects_bindings.cpp` | `PyEffects.pyi` | b1 |
| 12 | `PyFriendList` | `src\GW\friend_list\friend_list_bindings.cpp` | — (none) | b2 |
| 13 | `PyGameThread` | `src\GW\game_thread\game_thread_bindings.cpp` | `PyGameThread.pyi` | b6 |
| 14 | `PyGuild` | `src\GW\guild\guild_bindings.cpp` | — (none) | b2 |
| 15 | `PyItem` | `src\GW\item\item_bindings.cpp` | `PyItem.pyi` | b3 |
| 16 | `PyInventory` | `src\GW\item\inventory_bindings.cpp` | `PyInventory.pyi` | b3 |
| 17 | `PyMap` | `src\GW\map\map_bindings.cpp` | — (none) | b5 |
| 18 | `PyMerchant` | `src\GW\merchant\merchant_bindings.cpp` | `PyMerchant.pyi` | b3 |
| 19 | `PyNameObfuscator` | `src\GW\name_obfuscator\name_obfuscator_bindings.cpp` | — (none) | b5 |
| 20 | `PyPacketSniffer` | `src\GW\packet_sniffer\packet_sniffer_bindings.cpp` | `PyPacketSniffer.pyi` | b5 |
| 21 | `PyParty` | `src\GW\party\party_bindings.cpp` | `PyParty.pyi` | b2 |
| 22 | `PyPathing` | `src\GW\pathing\pathing_bindings.cpp` | `PyPathing.pyi` | b5 |
| 23 | `PyPing` | `src\GW\ping\ping_bindings.cpp` | — (none) | b5 |
| 24 | `PyPlayer` | `src\GW\player\player_bindings.cpp` | `PyPlayer.pyi` | b2 |
| 25 | `PyQuest` | `src\GW\quest\quest_bindings.cpp` | `PyQuest.pyi` | b4 |
| 26 | `PyRender` | `src\GW\render\render_bindings.cpp` | — (none) | b7 |
| 27 | `PyScanner` | `src\base\scanner_bindings.cpp` | `PyScanner.pyi` | b6 |
| 28 | `PySkill` | `src\GW\skillbar\skill_bindings.cpp` | `PySkill.pyi` | b4 |
| 29 | `PySkillbar` | `src\GW\skillbar\skillbar_bindings.cpp` | `PySkillbar.pyi` | b4 |
| 30 | `PyTrade` | `src\GW\trade\trade_bindings.cpp` | `PyTrading.pyi` | b3 |
| 31 | `PyUIManager` | `src\GW\ui\ui_bindings.cpp` (+ `native_ui.h`) | `PyUIManager.pyi` | b8 |
| 32 | `PyTexture` | `src\GW\textures\texture_bindings.cpp` | — (none) | b7 |
| 33 | `PyDialog` | `src\GW\dialog\dialog_bindings.cpp` | `PyDialog.pyi` (+ retired `PyDialogCatalog.pyi`) | b4 |
| 34 | `PyOverlay` | `src\overlay\overlay_bindings.cpp` | `PyOverlay.pyi` | b7 |
| 35 | `PyDXOverlay` | `src\overlay\dx_overlay_bindings.cpp` | `PyDXOverlay.pyi` (legacy `Py2DRenderer.pyi`) | b7 |
| 36 | `PyKeystroke` | `src\virtual_input\virtual_input_bindings.cpp` | `PyKeystroke.pyi` | b7 |
| 37 | `PyMouse` | `src\virtual_input\virtual_input_bindings.cpp` | — (none) | b7 |
| 38 | `PyImGui` | `src\imgui\imgui_bindings.cpp` (+ `bindings\*.cpp`) | `PyImGui.pyi` (legacy `ImGui_Py.pyi`) | b9 |

### Task-listed subdirs that have NO `Py*` binding module

The reengineer prompt listed the `include\GW\` subdirs. Three of them are **not** exposed as a callable binding module and should be understood, not exercised as methods:

- **`context`** — `include\GW\context\*.h` are ctypes-mirrored shared-memory struct layouts (agent/map/world/party/etc.). They are read by the Python `native_src/context/*` readers via shared memory, **not** bound as pybind11 methods. `src\GW\context\context.cpp` populates them; no `context_bindings.cpp` exists.
- **`stoc`** — `include\GW\common\stoc.h` + `src\GW\stoc\stoc.cpp` is the server-to-client packet dispatch plumbing consumed internally by `PyPacketSniffer`/`PyListeners`; no standalone binding module.
- **`events`** — `include\GW\events\events.h` + `src\GW\events\events.cpp` back the `PyAgentEvents` and `PyListeners` modules; there is no separate `PyEvents` module.
- **`native_ui`** — `include\GW\native_ui\native_ui.h` is folded into the `PyUIManager` surface (`ui_bindings.cpp`); it is not a separate module. Note ~85 legacy `native_ui` methods are stub-only / unbound (see PyUIManager section).

### Retired / renamed stubs (present in `stubs\` but not 1:1 with a live module)

- `PyPointers.pyi` — **RETIRED** (pointers now come from shared memory; no binding).
- `Py2DRenderer.pyi` — legacy name for `PyDXOverlay`.
- `PyCombatEvents.pyi` — legacy name; the live surface is `PyAgentEvents`. NOTE: its `PyCombatEventQueue`/`PyRawCombatEvent`/`EventType` symbols are **not** present in `PyListeners` — that stub describes a surface that no live module implements (see PyListeners + PyAgentEvents sections).
- `PyAgentTagColor.pyi` — stub filename for the `PyAgentRecolor` module.
- `PyTrading.pyi` — stub describes a fictional PascalCase class; live `PyTrade` is snake_case free functions (major mismatch, see PyTrade).
- `PyDialogCatalog.pyi` — retired; merged into `PyDialog`.
- `ImGui_Py.pyi` — a *different, thinner legacy* `ImGui_Py` module, not the live `PyImGui` (see PyImGui section).

---

## Py4GW root module (`src\base\python_runtime.cpp`, `PYBIND11_EMBEDDED_MODULE(Py4GW, ...)`)

Reduced per the Reforged migration to `version()` + a `SharedMemory` submodule.

| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | `version` | free fn (`Py4GW`) | `() -> str` (returns `"0.1.0"`) | NO-ARG getter | - |
| 2 | `is_ready` | `Py4GW.SharedMemory` | `() -> bool` | NO-ARG getter | - |
| 3 | `get_name` | `Py4GW.SharedMemory` | `() -> str` | NO-ARG getter | - |
| 4 | `get_size` | `Py4GW.SharedMemory` | `() -> int` | NO-ARG getter | - |
| 5 | `get_sequence` | `Py4GW.SharedMemory` | `() -> int` (header sequence, 0 if none) | NO-ARG getter | - |

---

## Reading the per-module sections

Each section below follows a uniform template:
- **Methods / Functions** table — every `m.def` / `cls.def` with owner, signature, **arg category** (`NO-ARG getter` | `subject-id (<which id>)` | `other-args(...)` | `action/mutator (void/queues)`), and whether it returns a bound struct.
- **Struct return types & fields** table — every `py::class_` with its `def_readwrite`/`def_readonly`/`def_property` members (what the tool must render).
- **Stub vs Native disagreements** — migration gaps.

Sections are grouped by extraction batch (b1–b9) purely for provenance; every module in the registry above appears exactly once.

---


# R2 Batch 1 — Method Inventory (PyAgent, PyAgentRecolor, PyAgentEvents, PyEffects)

## PyAgent
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\agent\agent_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyAgent.pyi
- Module shape: mix — `ProfessionType` enum + `Profession` class + `PyAgent` class + 15 module-level free functions.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | \_\_init\_\_ | Profession.method | `(prof: int \| str = 0) -> None` | other-args(prof) | - |
| 2 | GetName | Profession.method | `() -> str` | NO-ARG getter | - |
| 3 | ToInt | Profession.method | `() -> int` | NO-ARG getter | - |
| 4 | Set | Profession.method | `(prof: int) -> None` | other-args(prof) | - |
| 5 | Get | Profession.method | `() -> ProfessionType` | NO-ARG getter | ProfessionType (enum) |
| 6 | \_\_eq\_\_ | Profession.method | `(o: Profession) -> bool` | other-args(o) | - |
| 7 | \_\_ne\_\_ | Profession.method | `(o: Profession) -> bool` | other-args(o) | - |
| 8 | \_\_init\_\_ | PyAgent.method | `(agent_id: int = 0) -> None` | subject-id (agent_id) | - |
| 9 | GetContext | PyAgent.method | `() -> None` | NO-ARG getter (no-op) | - |
| 10 | GetAgentID | PyAgent.method | `() -> int` | NO-ARG getter | - |
| 11 | GetPlayerNumber | PyAgent.method | `() -> int` | NO-ARG getter | - |
| 12 | GetName | PyAgent.method | `() -> str` | NO-ARG getter | - |
| 13 | GetPrimary | PyAgent.method | `() -> int` | NO-ARG getter | - |
| 14 | GetSecondary | PyAgent.method | `() -> int` | NO-ARG getter | - |
| 15 | GetLevel | PyAgent.method | `() -> int` | NO-ARG getter | - |
| 16 | GetHP | PyAgent.method | `() -> float` | NO-ARG getter | - |
| 17 | GetRotation | PyAgent.method | `() -> float` | NO-ARG getter | - |
| 18 | GetPos | PyAgent.method | `() -> Tuple[float, float, float]` | NO-ARG getter | - (tuple) |
| 19 | GetIsLiving | PyAgent.method | `() -> bool` | NO-ARG getter | - |
| 20 | GetIsDead | PyAgent.method | `() -> bool` | NO-ARG getter | - |
| 21 | GetIsMoving | PyAgent.method | `() -> bool` | NO-ARG getter | - |
| 22 | GetIsAttacking | PyAgent.method | `() -> bool` | NO-ARG getter | - |
| 23 | GetIsKnockedDown | PyAgent.method | `() -> bool` | NO-ARG getter | - |
| 24 | GetIsCasting | PyAgent.method | `() -> bool` | NO-ARG getter | - |
| 25 | GetAllegiance | PyAgent.method | `() -> int` | NO-ARG getter | - |
| 26 | GetIsGadget | PyAgent.method | `() -> bool` | NO-ARG getter | - |
| 27 | GetIsItem | PyAgent.method | `() -> bool` | NO-ARG getter | - |
| 28 | GetTargetId | PyAgent.method (static) | `() -> int` | NO-ARG getter | - |
| 29 | GetControlledCharacterId | PyAgent.method (static) | `() -> int` | NO-ARG getter | - |
| 30 | GetObservingId | PyAgent.method (static) | `() -> int` | NO-ARG getter | - |
| 31 | send_dialog | free fn | `(dialog_id: int) -> bool` | subject-id (dialog_id) | - |
| 32 | get_observing_id | free fn | `() -> int` | NO-ARG getter | - |
| 33 | get_controlled_character_id | free fn | `() -> int` | NO-ARG getter | - |
| 34 | get_target_id | free fn | `() -> int` | NO-ARG getter | - |
| 35 | get_amount_of_players_in_instance | free fn | `() -> int` | NO-ARG getter | - |
| 36 | is_observing | free fn | `() -> bool` | NO-ARG getter | - |
| 37 | change_target | free fn | `(agent_id: int) -> bool` | action/mutator (queues to game thread) | - |
| 38 | move | free fn | `(x: float, y: float, zplane: int = 0) -> bool` | action/mutator | - |
| 39 | interact_agent | free fn | `(agent_id: int, call_target: bool = False) -> bool` | action/mutator (queues) | - |
| 40 | call_target | free fn | `(agent_id: int) -> bool` | action/mutator (queues) | - |
| 41 | get_player_name_by_login_number | free fn | `(login_number: int) -> str` | subject-id (login_number) | - |
| 42 | get_agent_id_by_login_number | free fn | `(login_number: int) -> int` | subject-id (login_number) | - |
| 43 | get_hero_agent_id | free fn | `(hero_index: int) -> int` | subject-id (hero_index) | - |
| 44 | get_agent_enc_name | free fn | `(agent_id: int) -> List[int]` | subject-id (agent_id) | - (raw UTF-16LE bytes) |
| 45 | get_agent_is_targettable | free fn | `(agent_id: int) -> bool` | subject-id (agent_id) | - |

Note: constructors listed once each; `Profession.__init__` has three native `py::init` overloads (`<>`, `<int>`, `<const std::string&>`); `PyAgent.__init__` has two (`<>`, `<uint32_t>`).

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| ProfessionType (enum) | None | int=0 | enum value |
| ProfessionType (enum) | Warrior | int | enum value |
| ProfessionType (enum) | Ranger | int | enum value |
| ProfessionType (enum) | Monk | int | enum value |
| ProfessionType (enum) | Necromancer | int | enum value |
| ProfessionType (enum) | Mesmer | int | enum value |
| ProfessionType (enum) | Elementalist | int | enum value |
| ProfessionType (enum) | Assassin | int | enum value |
| ProfessionType (enum) | Ritualist | int | enum value |
| ProfessionType (enum) | Paragon | int | enum value |
| ProfessionType (enum) | Dervish | int | enum value |
| Profession | (constructors + methods only — no exposed data fields) | — | def / def(py::init) |
| PyAgent | (methods only — no def_readwrite/readonly data fields; `agent_id` C++ member is NOT exposed) | — | def / def_static |

### Stub vs Native disagreements
- `Profession.__eq__` / `Profession.__ne__` — present in native (`.def("__eq__"...)`, `.def("__ne__"...)`), NOT declared in stub. (Stub omits both dunders.)
- Otherwise in sync: all `PyAgent` methods, statics, and all 15 free functions match the stub signatures exactly. Stub's `ProfessionType.None_` maps to native enum value `None` (Python keyword-avoidance rename).

---

## PyAgentRecolor
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\agent_recolor\agent_recolor_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyAgentTagColor.pyi  (NOTE: stub filename is `PyAgentTagColor.pyi`, native module name is `PyAgentRecolor`)
- Module shape: module-level free functions only (no bound classes/structs).

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | enable | free fn | `() -> None` | action/mutator | - |
| 2 | disable | free fn | `() -> None` | action/mutator | - |
| 3 | is_enabled | free fn | `() -> bool` | NO-ARG getter | - |
| 4 | is_hook_installed | free fn | `() -> bool` | NO-ARG getter | - |
| 5 | set_agent_color | free fn | `(agent_id: int, argb: int) -> None` | action/mutator | - |
| 6 | remove_agent_color | free fn | `(agent_id: int) -> bool` | action/mutator (subject agent_id) | - |
| 7 | set_allegiance_color | free fn | `(allegiance: int, argb: int) -> None` | action/mutator | - |
| 8 | remove_allegiance_color | free fn | `(allegiance: int) -> bool` | action/mutator | - |
| 9 | clear_rules | free fn | `() -> None` | action/mutator | - |
| 10 | get_agent_rules | free fn | `() -> dict[int, int]` | NO-ARG getter | - (dict) |
| 11 | get_allegiance_rules | free fn | `() -> dict[int, int]` | NO-ARG getter | - (dict) |
| 12 | read_consider_color | free fn | `(agent_id: int) -> int` | subject-id (agent_id) | - |
| 13 | get_diagnostics | free fn | `() -> dict[str, object]` | NO-ARG getter | - (dict) |
| 14 | reset_diagnostics | free fn | `() -> None` | action/mutator | - |

### Struct return types & fields
No `py::class_` registered. `get_diagnostics` returns a `py::dict` assembled inline with keys: `initialized`, `hook_installed`, `enabled`, `resolver_calls_seen`, `agent_rule_hits`, `allegiance_rule_hits`, `last_agent_id`, `last_color` (sourced from `AgentRecolor::GetDiagnostics()`). `get_agent_rules` / `get_allegiance_rules` return `std::map`-backed dicts (`agent_id -> ARGB`, `allegiance -> ARGB`).

### Stub vs Native disagreements
In sync. All 14 functions match one-to-one (names, params, returns). Stub documents allegiance ids 1..6 and ARGB format; native docstrings match.

---

## PyAgentEvents
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\listeners\agent_events_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyAgentEvents.pyi  (legacy compare: C:\Users\Apo\Py4GW_Reforged\stubs\PyCombatEvents.pyi)
- Module shape: mix — `PyEventType` submodule of int constants + `PyRawAgentEvent` class + 7 module-level free functions.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | \_\_init\_\_ | PyRawAgentEvent.method | `() -> None` | NO-ARG | - |
| 2 | \_\_repr\_\_ | PyRawAgentEvent.method | `() -> str` | NO-ARG getter | - |
| 3 | as_tuple | PyRawAgentEvent.method | `() -> Tuple[int, int, int, int, int, float]` | NO-ARG getter | - (tuple: timestamp,event_type,agent_id,value,target_id,float_value) |
| 4 | enable | free fn | `() -> None` | action/mutator | - |
| 5 | disable | free fn | `() -> None` | action/mutator | - |
| 6 | is_enabled | free fn | `() -> bool` | NO-ARG getter | - |
| 7 | get_and_clear_events | free fn | `() -> List[PyRawAgentEvent]` | action/mutator (drains buffer) | PyRawAgentEvent[] |
| 8 | peek_events | free fn | `() -> List[PyRawAgentEvent]` | NO-ARG getter | PyRawAgentEvent[] |
| 9 | get_event_count | free fn | `() -> int` | NO-ARG getter | - |
| 10 | get_capacity | free fn | `() -> int` | NO-ARG getter | - |

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| PyRawAgentEvent (native `RawAgentEvent`, include\listeners\agent_events_listener.h) | timestamp | int (uint64) | def_readonly |
| PyRawAgentEvent | event_type | int (uint32) | def_readonly |
| PyRawAgentEvent | agent_id | int (uint32) | def_readonly |
| PyRawAgentEvent | value | int (uint32) | def_readonly |
| PyRawAgentEvent | target_id | int (uint32) | def_readonly |
| PyRawAgentEvent | float_value | float | def_readonly |
| PyRawAgentEvent | agent_max_hp | int (uint32) | def_readonly |
| PyRawAgentEvent | agent_max_energy | int (uint32) | def_readonly |
| PyRawAgentEvent | target_max_hp | int (uint32) | def_readonly |
| PyRawAgentEvent | target_max_energy | int (uint32) | def_readonly |
| PyRawAgentEvent | \_\_init\_\_ / \_\_repr\_\_ / as_tuple | — | def method |
| PyEventType (submodule, not a class) | 33 int attrs (see below) | int (uint32) | `types.attr(name)=value` via X-macro |

`PyEventType` constants (from `GW_AGENT_EVENT_TYPES`, include\listeners\agent_events_listener.h): SKILL_ACTIVATED=1, ATTACK_SKILL_ACTIVATED=2, SKILL_STOPPED=3, SKILL_FINISHED=4, ATTACK_SKILL_FINISHED=5, INTERRUPTED=6, INSTANT_SKILL_ACTIVATED=7, ATTACK_SKILL_STOPPED=8, ATTACK_STARTED=13, ATTACK_STOPPED=14, MELEE_ATTACK_FINISHED=15, DISABLED=16, KNOCKED_DOWN=17, CASTTIME=18, DAMAGE=30, CRITICAL=31, ARMOR_IGNORING=32, HEALING=33, CURRENT_HEALTH=34, CURRENT_ENERGY=35, HEALTH_REGEN_CHANGE=36, ENERGY_REGEN_CHANGE=37, REACHED_MAXHP=38, EFFECT_APPLIED=40, EFFECT_REMOVED=41, EFFECT_ON_TARGET=42, EFFECT_RENEWED=43, ENERGY_GAINED=50, ENERGY_SPENT=51, SKILL_DAMAGE=60, SKILL_ACTIVATE_PACKET=70, SKILL_RECHARGE=80, SKILL_RECHARGED=81.

### Stub vs Native disagreements
- `PyRawAgentEvent.__repr__` — present in native (`.def("__repr__"...)`), not declared in stub (harmless; dunder).
- `PyEventType` stub is an empty placeholder `class PyEventType: pass` (comment: "populated at runtime"). Native exposes it as a **submodule** with 33 int attributes. Stub gives no attribute type hints, so all 33 event-type constants are untyped to the checker.
- Otherwise in sync: all 10 methods/functions and all 10 `PyRawAgentEvent` fields match the stub.
- **vs legacy PyCombatEvents.pyi**: legacy exposed `EventType` (plain class of ~30 constants, no CURRENT_HEALTH/CURRENT_ENERGY/HEALTH_REGEN_CHANGE/ENERGY_REGEN_CHANGE/REACHED_MAXHP additions), a `PyRawCombatEvent` (6 fields only — no max_hp/max_energy), and a stateful `PyCombatEventQueue` class (Initialize/Terminate/GetAndClearEvents/PeekEvents/GetQueueSize/SetMaxEvents/GetMaxEvents/IsInitialized) plus `GetCombatEventQueue()`. The Reforged module drops the queue class entirely in favor of module-level `get_and_clear_events`/`peek_events`/`get_event_count`/`get_capacity`, renames `EventType`→`PyEventType` (submodule), renames `PyRawCombatEvent`→`PyRawAgentEvent` (adds 4 max_hp/max_energy readonly fields), and adds `enable`/`disable`/`is_enabled` toggles. Five new event codes added (34–38).

---

## PyEffects
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\effects\effects_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyEffects.pyi
- Module shape: mix — `EffectType` class + `BuffType` class + `PyEffects` (wrapper) class + 9 module-level free functions.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | get_alcohol_level | free fn | `() -> int` | NO-ARG getter | - |
| 2 | get_drunk_af | free fn | `(intensity: int, tint: int) -> None` | action/mutator | - |
| 3 | drop_buff | free fn | `(buff_id: int) -> <bool/None>` | action/mutator (subject buff_id) | - |
| 4 | effect_count | free fn | `(agent_id: int) -> int` | subject-id (agent_id) | - |
| 5 | buff_count | free fn | `(agent_id: int) -> int` | subject-id (agent_id) | - |
| 6 | effect_exists | free fn | `(agent_id: int, skill_id: int) -> bool` | other-args(agent_id, skill_id) | - |
| 7 | buff_exists | free fn | `(agent_id: int, skill_id: int) -> bool` | other-args(agent_id, skill_id) | - |
| 8 | get_effects | free fn | `(agent_id: int) -> List[EffectType]` | subject-id (agent_id) | EffectType[] |
| 9 | get_buffs | free fn | `(agent_id: int) -> List[BuffType]` | subject-id (agent_id) | BuffType[] |
| 10 | \_\_init\_\_ | PyEffects.method | `(agent_id: int) -> None` | subject-id (agent_id) | - |
| 11 | GetEffects | PyEffects.method | `() -> List[EffectType]` | NO-ARG getter | EffectType[] |
| 12 | GetBuffs | PyEffects.method | `() -> List[BuffType]` | NO-ARG getter | BuffType[] |
| 13 | GetEffectCount | PyEffects.method | `() -> int` | NO-ARG getter | - |
| 14 | GetBuffCount | PyEffects.method | `() -> int` | NO-ARG getter | - |
| 15 | EffectExists | PyEffects.method | `(skill_id: int) -> bool` | other-args(skill_id) | - |
| 16 | BuffExists | PyEffects.method | `(skill_id: int) -> bool` | other-args(skill_id) | - |
| 17 | DropBuff | PyEffects.method | `(skill_id: int) -> None` | action/mutator | - |
| 18 | GetAlcoholLevel | PyEffects.method (static) | `() -> int` | NO-ARG getter | - |
| 19 | ApplyDrunkEffect | PyEffects.method (static) | `(intensity: int = 0, tint: int = 0) -> None` | action/mutator | - |

Note: `drop_buff` native lambda `return GW::effects::DropBuff(buff_id);` — returns whatever `DropBuff` returns (not annotated in stub; stub omits the free `drop_buff`/`get_drunk_af`/`effect_count`/`buff_count`/`effect_exists`/`buff_exists`/`get_effects`/`get_buffs` functions entirely — see disagreements). `PyEffects.DropBuff` native arg is named `skill_id` but forwards to `DropBuff(buff_id)`.

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| EffectType (native `PyEffectType`, defined inline in cpp) | skill_id | int | def_readonly |
| EffectType | attribute_level | int (uint32) | def_readonly |
| EffectType | effect_id | int (uint32) | def_readonly |
| EffectType | agent_id | int (uint32) | def_readonly |
| EffectType | duration | float | def_readonly |
| EffectType | timestamp | int (uint32) | def_readonly |
| EffectType | time_elapsed | int (uint32) | def_readonly |
| EffectType | time_remaining | int (uint32) | def_readonly |
| BuffType (native `PyBuffType`, inline in cpp) | skill_id | int | def_readonly |
| BuffType | buff_id | int (uint32) | def_readonly |
| BuffType | target_agent_id | int (uint32) | def_readonly |
| PyEffects (native `PyEffectsWrapper`, inline in cpp) | (methods only — `agent_id` C++ member NOT exposed as field) | — | def / def_static |

Underlying source structs (`GW::effects` Context::Effect / Context::Buff in GW/effects/effects.h) are NOT bound directly; `get_effects`/`get_buffs`/`GetEffects`/`GetBuffs` copy fields into the inline `PyEffectType`/`PyBuffType` snapshots. `time_elapsed`/`time_remaining` are computed via `e.GetTimeElapsed()`/`e.GetTimeRemaining()`.

### Stub vs Native disagreements
- Free functions present in native but MISSING from stub: `get_alcohol_level`, `get_drunk_af`, `drop_buff`, `effect_count`, `buff_count`, `effect_exists`, `buff_exists`, `get_effects`, `get_buffs` (all 9 module-level functions are undocumented in the stub — stub only declares the three classes).
- Constructor signature drift: native `EffectType`/`BuffType` are `def_readonly` snapshot classes with **no user-facing constructor bound**; the stub declares `EffectType.__init__(skill_id, ..., time_remaining)` and `BuffType.__init__(skill_id, buff_id, target_agent_id)` — these constructors do NOT exist in native (calling them would fail). Fields (readonly) otherwise match.
- `PyEffects` class methods are in sync (all 10 match). `ApplyDrunkEffect` native defaults `intensity=0, tint=0` match stub defaults absent in stub signature (stub lists them required — minor drift).
- `DropBuff` return: stub says `-> None`; native `PyEffects.DropBuff` lambda returns void (in sync), but free `drop_buff` returns `DropBuff`'s value and is unstubbed.


---


# R2 Batch 2 — Method Inventory (PyPlayer, PyParty, PyChat, PyFriendList, PyGuild)

Note: For all five modules, every `py::class_` bound is a wrapper struct defined **inline in the bindings .cpp** (namespace-local), not an external `GW/<module>/*.h` struct. The underlying `GW::player::`, `GW::party::`, `GW::chat::`, `GW::friend_list::`, `GW::guild::` symbols are C++ free functions that are *called* but not themselves bound. So no `include/GW/**` struct is directly exposed to Python.

---

## PyPlayer
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\player\player_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PyPlayer.pyi`
- Module shape: mix — one bound class `PyPlayer` + one enum `PlayerStatus` + 10 module-level free functions

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | `__init__` | PyPlayer.method | `() -> None` (calls GetContext) | NO-ARG getter | - |
| 2 | GetContext | PyPlayer.method | `() -> None` | action/mutator (refreshes fields) | - |
| 3 | SendDialog | PyPlayer.method | `(dialog_id: int) -> None` | other-args(dialog_id) | - |
| 4 | ChangeTarget | PyPlayer.method | `(target_id: int) -> bool` | subject-id (target agent id) | - |
| 5 | InteractAgent | PyPlayer.method | `(agent_id: int, call_target: bool) -> bool` | subject-id (agent id) + other-args(call_target) | - |
| 6 | CallTarget | PyPlayer.method | `(agent_id: int) -> bool` | subject-id (agent id) / action(queues) | - |
| 7 | IsAgentIDValid | PyPlayer.method | `(agent_id: int) -> bool` | subject-id (agent id) | - |
| 8 | GetChatHistory | PyPlayer.method | `() -> List[str]` | NO-ARG getter | - |
| 9 | RequestChatHistory | PyPlayer.method | `() -> None` | action/mutator (spawns thread) | - |
| 10 | IsChatHistoryReady | PyPlayer.method | `() -> bool` | NO-ARG getter | - |
| 11 | Istyping | PyPlayer.method | `() -> bool` | NO-ARG getter | - |
| 12 | SendChatCommand | PyPlayer.method | `(msg: str) -> None` | other-args(msg) / action | - |
| 13 | SendChat | PyPlayer.method | `(channel: str, msg: str) -> None` | other-args(channel,msg) / action | - |
| 14 | SendWhisper | PyPlayer.method | `(name: str, msg: str) -> None` | other-args(name,msg) / action | - |
| 15 | SendFakeChat | PyPlayer.method | `(channel: int, message: str) -> None` | other-args(channel,message) / action | - |
| 16 | SendFakeChatColored | PyPlayer.method | `(channel: int, message: str, r: int, g: int, b: int) -> None` | other-args(channel,message,r,g,b) / action | - |
| 17 | GetPlayerStatus | PyPlayer.method | `() -> int` | NO-ARG getter | - |
| 18 | SetPlayerStatus | PyPlayer.method | `(status: int) -> bool` | other-args(status) / action(queues) | - |
| 19 | set_active_title | free fn | `(title_id: int) -> bool` | other-args(title_id) / action | - |
| 20 | remove_active_title | free fn | `() -> bool` | action/mutator (void-ish) | - |
| 21 | get_active_title_id | free fn | `() -> int` | NO-ARG getter | - |
| 22 | deposit_faction | free fn | `(allegiance: int) -> bool` | other-args(allegiance) / action | - |
| 23 | get_player_agent_id | free fn | `(player_id: int) -> int` | subject-id (player id) | - |
| 24 | get_amount_of_players_in_instance | free fn | `() -> int` | NO-ARG getter | - |
| 25 | get_player_number | free fn | `() -> int` | NO-ARG getter | - |
| 26 | get_player_name | free fn | `(player_id: int = 0) -> str` | subject-id (player id, dflt 0) | - |
| 27 | change_second_profession | free fn | `(profession: int, hero_index: int = 0) -> bool` | other-args(profession,hero_index) / action | - |
| 28 | get_title_ids | free fn | `() -> list` | NO-ARG getter | - |

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| PyPlayer | id | int | def_readonly |
| PyPlayer | agent | int | def_readonly |
| PyPlayer | target_id | int | def_readonly |
| PyPlayer | mouse_over_id | int | def_readonly |
| PyPlayer | observing_id | int | def_readonly |
| PyPlayer | account_name | str | def_readonly |
| PyPlayer | account_email | str | def_readonly |
| PyPlayer | player_uuid | uint32_t[4] (Tuple[int,int,int,int]) | def_readonly |
| PyPlayer | wins | int | def_readonly |
| PyPlayer | losses | int | def_readonly |
| PyPlayer | rating | int | def_readonly |
| PyPlayer | qualifier_points | int | def_readonly |
| PyPlayer | rank | int | def_readonly |
| PyPlayer | tournament_reward_points | int | def_readonly |
| PyPlayer | morale | int | def_readonly |
| PyPlayer | party_morale | List[Tuple[int,int]] | def_readonly |
| PyPlayer | experience | int | def_readonly |
| PyPlayer | level | int | def_readonly |
| PyPlayer | current_kurzick | int | def_readonly |
| PyPlayer | total_earned_kurzick | int | def_readonly |
| PyPlayer | max_kurzick | int | def_readonly |
| PyPlayer | current_luxon | int | def_readonly |
| PyPlayer | total_earned_luxon | int | def_readonly |
| PyPlayer | max_luxon | int | def_readonly |
| PyPlayer | current_imperial | int | def_readonly |
| PyPlayer | total_earned_imperial | int | def_readonly |
| PyPlayer | max_imperial | int | def_readonly |
| PyPlayer | current_balth | int | def_readonly |
| PyPlayer | total_earned_balth | int | def_readonly |
| PyPlayer | max_balth | int | def_readonly |
| PyPlayer | current_skill_points | int | def_readonly |
| PyPlayer | total_earned_skill_points | int | def_readonly |
| PyPlayer | missions_completed | List[int] | def_readonly |
| PyPlayer | missions_bonus | List[int] | def_readonly |
| PyPlayer | missions_completed_hm | List[int] | def_readonly |
| PyPlayer | missions_bonus_hm | List[int] | def_readonly |
| PyPlayer | controlled_minions | List[Tuple[int,int]] | def_readonly |
| PyPlayer | unlocked_maps | List[int] (C++ field `unlocked_map`) | def_readonly |
| PyPlayer | learnable_character_skills | List[int] | def_readonly |
| PyPlayer | unlocked_character_skills | List[int] | def_readonly |
| PlayerStatus (enum) | Offline=0, Online=1, DND=2, Away=3 | IntEnum (GW::Constants::FriendStatus) | py::enum_ .value |

### Stub vs Native disagreements
- **In sync** on all methods/fields. Field python name `unlocked_maps` correctly maps to C++ member `unlocked_map` in both.
- Native-only (not surfaced but harmless): C++ struct has a private `ResetContext()` helper — not bound, correctly absent from stub.
- Note: `mouse_over_id` is a bound field but `GetContext()` never populates it (always 0); documentation-only, not a stub disagreement.

---

## PyParty
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\party\party_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PyParty.pyi`
- Module shape: mix — enum `HeroType` + 6 bound classes (`Hero`, `PartyTick`, `PlayerPartyMember`, `HeroPartyMember`, `HenchmanPartyMember`, `PetInfo`, `PyParty`) + 45 module-level free functions

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | `__init__(int)` | Hero.method | `(hero_id: int) -> None` | other-args(hero_id) | - |
| 2 | `__init__(str)` | Hero.method | `(name: str) -> None` | other-args(name) | - |
| 3 | GetID | Hero.method | `() -> int` | NO-ARG getter | - |
| 4 | GetName | Hero.method | `() -> str` | NO-ARG getter | - |
| 5 | GetProfession | Hero.method | `() -> int` | NO-ARG getter | - |
| 6 | FlagHero | Hero.method | `(idx: int) -> bool` | other-args(idx) / action(keypress) | - |
| 7 | `__eq__` | Hero.method | `(o: Hero) -> bool` | other-args(o) | - |
| 8 | `__ne__` | Hero.method | `(o: Hero) -> bool` | other-args(o) | - |
| 9 | `__repr__` | Hero.method | `() -> str` | NO-ARG getter | - |
| 10 | `__init__` | PartyTick.method | `(ticked: bool = False) -> None` | other-args(ticked) | - |
| 11 | IsTicked | PartyTick.method | `() -> bool` | NO-ARG getter | - |
| 12 | SetTicked | PartyTick.method | `(ticked: bool) -> None` | other-args(ticked) / mutator | - |
| 13 | ToggleTicked | PartyTick.method | `() -> None` | action/mutator | - |
| 14 | SetTickToggle | PartyTick.method | `(enable: bool) -> None` | other-args(enable) / action | - |
| 15 | `__init__` | PlayerPartyMember.method | `(login_number=0, called_target_id=0, is_connected=False, is_ticked=False) -> None` | other-args | - |
| 16 | `__init__` | HeroPartyMember.method | `(agent_id=0, owner_player_id=0, hero_id=0, level=0) -> None` | other-args | - |
| 17 | `__init__` | HenchmanPartyMember.method | `(agent_id=0, profession=0, level=0) -> None` | other-args | - |
| 18 | `__init__` | PetInfo.method | `(owner_agent_id: int) -> None` | subject-id (owner agent id) | - |
| 19 | `__init__` | PyParty.method | `() -> None` (calls GetContext) | NO-ARG getter | - |
| 20 | GetContext | PyParty.method | `() -> None` | action/mutator (refreshes fields) | - |
| 21 | ReturnToOutpost | PyParty.method | `() -> bool` | action/mutator | - |
| 22 | SetHardMode | PyParty.method | `(flag: bool) -> bool` | other-args(flag) / action | - |
| 23 | RespondToPartyRequest | PyParty.method | `(party_id: int, accept: bool) -> bool` | subject-id (party id) + other-args(accept) | - |
| 24 | AddHero | PyParty.method | `(hero_id: int) -> bool` | subject-id (hero id) / action | - |
| 25 | KickHero | PyParty.method | `(hero_id: int) -> bool` | subject-id (hero id) / action | - |
| 26 | KickAllHeroes | PyParty.method | `() -> bool` | action/mutator | - |
| 27 | AddHenchman | PyParty.method | `(henchman_id: int) -> bool` | subject-id (henchman id) / action | - |
| 28 | KickHenchman | PyParty.method | `(henchman_id: int) -> bool` | subject-id (henchman id) / action | - |
| 29 | KickPlayer | PyParty.method | `(player_id: int) -> bool` | subject-id (player id) / action | - |
| 30 | InvitePlayer | PyParty.method | `(player_id: int) -> bool` | subject-id (player id) / action | - |
| 31 | LeaveParty | PyParty.method | `() -> bool` | action/mutator | - |
| 32 | FlagHero | PyParty.method | `(agent_id: int, x: float, y: float) -> bool` | subject-id (agent id) + other-args(x,y) | - |
| 33 | FlagAllHeroes | PyParty.method | `(x: float, y: float) -> bool` | other-args(x,y) / action | - |
| 34 | UnflagHero | PyParty.method | `(agent_id: int) -> bool` | subject-id (agent id) / action | - |
| 35 | UnflagAllHeroes | PyParty.method | `() -> bool` | action/mutator | - |
| 36 | IsHeroFlagged | PyParty.method | `(hero: int) -> bool` | subject-id (hero) | - |
| 37 | IsAllFlagged | PyParty.method | `() -> bool` | NO-ARG getter | - |
| 38 | GetAllFlagX | PyParty.method | `() -> float` | NO-ARG getter | - |
| 39 | GetAllFlagY | PyParty.method | `() -> float` | NO-ARG getter | - |
| 40 | GetHeroAgentID | PyParty.method | `(hero_index: int) -> int` | subject-id (hero index) | - |
| 41 | GetAgentHeroID | PyParty.method | `(agent_id: int) -> int` | subject-id (agent id) | - |
| 42 | GetAgentIDByLoginNumber | PyParty.method | `(login_number: int) -> int` | subject-id (login number) | - |
| 43 | GetPlayerNameByLoginNumber | PyParty.method | `(login_number: int) -> str` | subject-id (login number) | - |
| 44 | SearchParty | PyParty.method | `(search_type: int, advertisement: str) -> bool` | other-args(search_type,advertisement) / action | - |
| 45 | SearchPartyCancel | PyParty.method | `() -> bool` | action/mutator | - |
| 46 | SearchPartyReply | PyParty.method | `(accept: bool) -> bool` | other-args(accept) / action | - |
| 47 | SetHeroBehavior | PyParty.method | `(agent_id: int, behavior: int) -> None` | subject-id (agent id) + other-args(behavior) | - |
| 48 | SetPetBehavior | PyParty.method | `(behavior: int, lock_target_id: int) -> None` | other-args(behaviour,lock_target_id) / action | - |
| 49 | GetPetInfo | PyParty.method | `(owner_agent_id: int) -> PetInfo` | subject-id (owner agent id) | **PetInfo** |
| 50 | GetIsPlayerTicked | PyParty.method | `(player_id: int) -> bool` | subject-id (player id) | - |
| 51 | UseHeroSkill | PyParty.method | `(hero_id: int, skill_slot: int, target_id: int) -> None` | other-args(hero_id,skill_slot,target_id) / action(queues) | - |
| 52 | SetHeroSkillAIEnabled | PyParty.method | `(hero_agent_id: int, skill_slot: int, enabled: bool) -> bool` | subject-id (hero agent id) + other-args | - |
| 53 | GetPartyContextPtr | PyParty.method | `() -> int` | NO-ARG getter (raw ptr) | - |
| 54 | set_tick_toggle | free fn | `(enable: bool) -> None` | other-args(enable) / action | - |
| 55 | tick | free fn | `(flag: bool = True) -> bool` | other-args(flag) / action | - |
| 56 | get_party_size | free fn | `() -> int` | NO-ARG getter | - |
| 57 | get_party_player_count | free fn | `() -> int` | NO-ARG getter | - |
| 58 | get_party_hero_count | free fn | `() -> int` | NO-ARG getter | - |
| 59 | get_party_henchman_count | free fn | `() -> int` | NO-ARG getter | - |
| 60 | get_is_party_defeated | free fn | `() -> bool` | NO-ARG getter | - |
| 61 | get_is_party_in_hard_mode | free fn | `() -> bool` | NO-ARG getter | - |
| 62 | get_is_hard_mode_unlocked | free fn | `() -> bool` | NO-ARG getter | - |
| 63 | get_is_party_ticked | free fn | `() -> bool` | NO-ARG getter | - |
| 64 | get_is_player_ticked | free fn | `(player_index: int = 0xFFFFFFFF) -> bool` | subject-id (player index) | - |
| 65 | get_is_player_loaded | free fn | `(player_index: int = 0xFFFFFFFF) -> bool` | subject-id (player index) | - |
| 66 | get_is_party_loaded | free fn | `() -> bool` | NO-ARG getter | - |
| 67 | get_is_leader | free fn | `() -> bool` | NO-ARG getter | - |
| 68 | set_hard_mode | free fn | `(flag: bool) -> bool` | other-args(flag) / action | - |
| 69 | return_to_outpost | free fn | `() -> bool` | action/mutator | - |
| 70 | respond_to_party_request | free fn | `(party_id: int, accept: bool) -> bool` | subject-id (party id) + other-args(accept) | - |
| 71 | leave_party | free fn | `() -> bool` | action/mutator | - |
| 72 | add_hero | free fn | `(hero_id: int) -> bool` | subject-id (hero id) / action | - |
| 73 | kick_hero | free fn | `(hero_id: int) -> bool` | subject-id (hero id) / action | - |
| 74 | kick_all_heroes | free fn | `() -> bool` | action/mutator | - |
| 75 | add_henchman | free fn | `(agent_id: int) -> bool` | subject-id (agent id) / action | - |
| 76 | kick_henchman | free fn | `(agent_id: int) -> bool` | subject-id (agent id) / action | - |
| 77 | invite_player_by_id | free fn | `(player_id: int) -> bool` | subject-id (player id) / action | - |
| 78 | invite_player_by_name | free fn | `(player_name: str) -> bool` | other-args(player_name) / action | - |
| 79 | kick_player | free fn | `(player_id: int) -> bool` | subject-id (player id) / action | - |
| 80 | flag_hero | free fn | `(hero_index: int, x: float, y: float) -> bool` | subject-id (hero index) + other-args(x,y) | - |
| 81 | flag_hero_agent | free fn | `(agent_id: int, x: float, y: float) -> bool` | subject-id (agent id) + other-args(x,y) | - |
| 82 | unflag_hero | free fn | `(hero_index: int) -> bool` | subject-id (hero index) / action | - |
| 83 | flag_all | free fn | `(x: float, y: float) -> bool` | other-args(x,y) / action | - |
| 84 | unflag_all | free fn | `() -> bool` | action/mutator | - |
| 85 | set_hero_behavior | free fn | `(agent_id: int, behavior: int) -> bool` | subject-id (agent id) + other-args(behavior) | - |
| 86 | set_hero_skill_ai_enabled | free fn | `(hero_agent_id: int, skill_slot: int, enabled: bool) -> bool` | subject-id (hero agent id) + other-args | - |
| 87 | set_pet_behavior | free fn | `(behavior: int, lock_target_id: int = 0) -> bool` | other-args(behavior,lock_target_id) / action | - |
| 88 | get_hero_agent_id | free fn | `(hero_index: int) -> int` | subject-id (hero index) | - |
| 89 | get_agent_hero_id | free fn | `(agent_id: int) -> int` | subject-id (agent id) | - |
| 90 | search_party | free fn | `(search_type: int, advertisement: str = "") -> bool` | other-args(search_type,advertisement) / action | - |
| 91 | search_party_cancel | free fn | `() -> bool` | action/mutator | - |
| 92 | search_party_reply | free fn | `(accept: bool) -> bool` | other-args(accept) / action | - |

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| HeroType (enum) | NoHero..ZeiRi (39 values incl. Merc1-8) | IntEnum (GW::Constants::HeroID) | py::enum_ .value |
| Hero | GetID / GetName / GetProfession / FlagHero / `__eq__` / `__ne__` / `__repr__` | methods | def method (no data fields exposed) |
| PartyTick | IsTicked / SetTicked / ToggleTicked / SetTickToggle | methods | def method (backing `ticked` bool not exposed as field) |
| PlayerPartyMember | login_number | int | def_readwrite |
| PlayerPartyMember | called_target_id | int | def_readwrite |
| PlayerPartyMember | is_connected | bool | def_readwrite |
| PlayerPartyMember | is_ticked | bool | def_readwrite |
| HeroPartyMember | agent_id | int | def_readwrite |
| HeroPartyMember | owner_player_id | int | def_readwrite |
| HeroPartyMember | hero_id | int | def_readwrite |
| HeroPartyMember | level | int | def_readwrite |
| HeroPartyMember | primary | int | def_readwrite |
| HeroPartyMember | secondary | int | def_readwrite |
| HenchmanPartyMember | agent_id | int | def_readwrite |
| HenchmanPartyMember | profession | int | def_readwrite |
| HenchmanPartyMember | level | int | def_readwrite |
| PetInfo | agent_id | int | def_readonly |
| PetInfo | owner_agent_id | int | def_readonly |
| PetInfo | pet_name | str | def_readonly |
| PetInfo | model_file_id1 | int | def_readonly |
| PetInfo | model_file_id2 | int | def_readonly |
| PetInfo | behavior | int | def_readonly |
| PetInfo | locked_target_id | int | def_readonly |
| PyParty | party_id | int | def_readwrite |
| PyParty | players | List[PlayerPartyMember] | def_readwrite |
| PyParty | heroes | List[HeroPartyMember] | def_readwrite |
| PyParty | henchmen | List[HenchmanPartyMember] | def_readwrite |
| PyParty | others | List[int] | def_readwrite |
| PyParty | is_in_hard_mode | bool | def_readwrite |
| PyParty | is_hard_mode_unlocked | bool | def_readwrite |
| PyParty | party_size | int | def_readwrite |
| PyParty | party_player_count | int | def_readwrite |
| PyParty | party_hero_count | int | def_readwrite |
| PyParty | party_henchman_count | int | def_readwrite |
| PyParty | is_party_defeated | bool | def_readwrite |
| PyParty | is_party_loaded | bool | def_readwrite |
| PyParty | is_party_leader | bool | def_readwrite |
| PyParty | tick | PartyTick | def_readwrite |

### Stub vs Native disagreements
- **Enum value drift**: stub `HeroType` lists 38 names starting `NoHero`; native binds name **`"None"`** (not `NoHero`) for `HeroID::NoHero`, plus all others. Stub uses `NoHero` — the Python-visible attribute is actually `HeroType.None` (native) which the stub calls `NoHero`. Real mismatch — code doing `HeroType.None` works at runtime but stub advertises `HeroType.NoHero`.
- **Stub-only field**: `PlayerPartyMember`/others match. All PyParty data fields present in both.
- **Method present in native, missing in stub method list**: `Hero.__eq__`, `Hero.__ne__`, `Hero.__repr__` bound natively but not declared in stub `Hero` (dunder omission — minor). `PartyTick` fully in sync.
- **Otherwise in sync**: all 45 free functions and all PyParty methods match stub (arg names + defaults incl. `player_index=0xFFFFFFFF`, `set_pet_behavior lock_target_id=0`, `search_party advertisement=""`).
- Naming: native method name is `SetPetBehavior` bound to C++ `SetPetBehaviour` impl; stub declares `SetPetBehavior` — in sync at Python level.

---

## PyChat
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\chat\chat_bindings.cpp`
- Stub: NONE
- Module shape: module-level free functions only (no classes/enums bound)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | force_redraw_chat_log | free fn | `() -> None` | action/mutator | - |
| 2 | get_is_typing | free fn | `() -> bool` | NO-ARG getter | - |
| 3 | send_chat | free fn | `(channel: int, msg: str) -> None` | other-args(channel,msg) / action | - |
| 4 | send_chat_by_name | free fn | `(from: str, msg: str) -> None` | other-args(from,msg) / action | - |
| 5 | write_chat | free fn | `(channel: int, message: str) -> None` | other-args(channel,message) / action | - |
| 6 | write_chat_ex | free fn | `(channel: int, message: str, sender: str) -> None` | other-args(channel,message,sender) / action | - |
| 7 | toggle_timestamps | free fn | `(enable: bool) -> None` | other-args(enable) / action | - |
| 8 | set_timestamps_format | free fn | `(use_24h: bool, show_seconds: bool = False) -> None` | other-args(use_24h,show_seconds) / action | - |
| 9 | set_timestamps_color | free fn | `(r: int, g: int, b: int) -> None` | other-args(r,g,b) / action | - |
| 10 | set_sender_color | free fn | `(channel: int, r: int, g: int, b: int) -> None` | other-args(channel,r,g,b) / action | - |
| 11 | set_message_color | free fn | `(channel: int, r: int, g: int, b: int) -> None` | other-args(channel,r,g,b) / action | - |
| 12 | send_fake_chat | free fn | `(channel: int, message: str) -> None` | other-args(channel,message) / action | - |
| 13 | send_fake_chat_colored | free fn | `(channel: int, message: str, r: int, g: int, b: int) -> None` | other-args(channel,message,r,g,b) / action | - |

### Struct return types & fields
None — no `py::class_` or `py::enum_` registered. (Note: `channel` args map to `GW::chat::Channel` enum in C++, but the enum itself is NOT exposed to Python; callers pass raw ints.)

### Stub vs Native disagreements
- No stub — native-only module.

---

## PyFriendList
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\friend_list\friend_list_bindings.cpp`
- Stub: NONE
- Module shape: module-level free functions only (no classes/enums bound)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | get_number_of_friends | free fn | `(friend_type: int = 1) -> int` | other-args(friend_type) | - |
| 2 | get_number_of_ignores | free fn | `() -> int` | NO-ARG getter | - |
| 3 | get_number_of_partners | free fn | `() -> int` | NO-ARG getter | - |
| 4 | get_number_of_traders | free fn | `() -> int` | NO-ARG getter | - |
| 5 | get_my_status | free fn | `() -> int` | NO-ARG getter | - |
| 6 | set_friend_list_status | free fn | `(status: int) -> bool` | other-args(status) / action(queues) | - |
| 7 | add_friend | free fn | `(name: str, alias: str = "") -> bool` | other-args(name,alias) / action(queues) | - |
| 8 | add_ignore | free fn | `(name: str, alias: str = "") -> bool` | other-args(name,alias) / action(queues) | - |

### Struct return types & fields
None — no `py::class_` or `py::enum_` registered. (`friend_type`→`GW::Constants::FriendType`, `status`→`GW::Constants::FriendStatus` cast internally; enums not exposed here — note `PlayerStatus` enum lives in the PyPlayer module instead.)

### Stub vs Native disagreements
- No stub — native-only module.

---

## PyGuild
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\guild\guild_bindings.cpp`
- Stub: NONE
- Module shape: module-level free functions only (no classes/enums bound)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | get_player_guild_index | free fn | `() -> int` | NO-ARG getter | - |
| 2 | get_player_guild_announcement | free fn | `() -> str` | NO-ARG getter | - |
| 3 | get_player_guild_announcer | free fn | `() -> str` | NO-ARG getter | - |
| 4 | travel_gh | free fn | `() -> bool` | action/mutator (queues) | - |
| 5 | leave_gh | free fn | `() -> bool` | action/mutator (queues) | - |

### Struct return types & fields
None — no `py::class_` or `py::enum_` registered.

### Stub vs Native disagreements
- No stub — native-only module.


---


# R2_b3 — PyItem / PyInventory / PyMerchant / PyTrade method inventory

## PyItem
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\item\item_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyItem.pyi
- Module shape: mix (data class `PyItem` + helper classes `ItemModifier`/`ItemTypeClass`/`DyeColorClass`/`DyeInfo` + `Rarity` enum + module-level free functions)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | `__init__` | ItemModifier.method | `(identifier: int) -> None` (native `py::init<uint32_t>()`) | other-args(mod_value) | - |
| 2 | GetIdentifier | ItemModifier.method | `() -> int` | NO-ARG getter | - |
| 3 | GetArg1 | ItemModifier.method | `() -> int` | NO-ARG getter | - |
| 4 | GetArg2 | ItemModifier.method | `() -> int` | NO-ARG getter | - |
| 5 | GetArg | ItemModifier.method | `() -> int` | NO-ARG getter | - |
| 6 | IsValid | ItemModifier.method | `() -> bool` | NO-ARG getter | - |
| 7 | GetModBits | ItemModifier.method | `() -> int` (native returns `std::string`) | NO-ARG getter | - |
| 8 | ToString | ItemModifier.method | `() -> str` | NO-ARG getter | - |
| 9 | `__init__` | ItemTypeClass.method | `(item_type: int) -> None` (native `py::init<int>()`) | other-args(type_value) | - |
| 10 | ToInt | ItemTypeClass.method | `() -> int` | NO-ARG getter | - |
| 11 | GetName | ItemTypeClass.method | `() -> str` | NO-ARG getter | - |
| 12 | `__eq__` | ItemTypeClass.method | `(other) -> bool` | other-args(other) | - |
| 13 | `__ne__` | ItemTypeClass.method | `(other) -> bool` | other-args(other) | - |
| 14 | `__init__` | DyeColorClass.method | `(dye_color: int) -> None` (native `py::init<int>()`) | other-args(color_value) | - |
| 15 | ToInt | DyeColorClass.method | `() -> int` | NO-ARG getter | - |
| 16 | ToString | DyeColorClass.method | `() -> str` | NO-ARG getter | - |
| 17 | `__eq__` | DyeColorClass.method | `(other) -> bool` | other-args(other) | - |
| 18 | `__ne__` | DyeColorClass.method | `(other) -> bool` | other-args(other) | - |
| 19 | `__init__` | DyeInfo.method | `() -> None` (native `py::init<>()`) | NO-ARG getter | - |
| 20 | ToString | DyeInfo.method | `() -> str` | NO-ARG getter | - |
| 21 | `__init__` | PyItem.method | `(item_id: int) -> None` (native `py::init<int>()`, calls GetContext) | subject-id (item_id) | - |
| 22 | GetContext | PyItem.method | `() -> None` | action/mutator (refreshes fields) | - |
| 23 | RequestName | PyItem.method | `() -> None` (spawns detached thread) | action/mutator (async name fetch) | - |
| 24 | IsItemNameReady | PyItem.method | `() -> bool` | NO-ARG getter | - |
| 25 | GetName | PyItem.method | `() -> str` | NO-ARG getter | - |
| 26 | GetInfoString | PyItem.method | `() -> List[int]` (native `std::vector<uint8_t>`) | NO-ARG getter | - |
| 27 | GetNameEnc | PyItem.method | `() -> List[int]` (native `std::vector<uint8_t>`) | NO-ARG getter | - |
| 28 | GetCompleteNameEnc | PyItem.method | `() -> List[int]` (native `std::vector<uint8_t>`) | NO-ARG getter | - |
| 29 | GetSingleItemName | PyItem.method | `() -> List[int]` (native `std::vector<uint8_t>`) | NO-ARG getter | - |
| 30 | IsItemValid | PyItem.method | `(item_id: int) -> bool` | subject-id (item_id) | - |
| 31 | GetCompositeModelIDs | PyItem.method (`def_static`) | `(item_id: int) -> List[int]` (native arg is `model_file_id`) | subject-id (model_file_id) | - |
| 32 | use_item_by_id | free fn | `(item_id: int) -> bool` | subject-id (item_id) | - |
| 33 | equip_item_by_id | free fn | `(item_id: int, agent_id: int = 0) -> bool` | subject-id (item_id) + other-args(agent_id) | - |
| 34 | drop_item_by_id | free fn | `(item_id: int, quantity: int = 1) -> bool` (native: `quantity` has NO default) | subject-id (item_id) + other-args(quantity) | - |
| 35 | pick_up_item_by_id | free fn | `(item_id: int, call_target: int = 0) -> bool` | subject-id (item_id) + other-args(call_target) | - |
| 36 | move_item | free fn | `(item_id: int, bag_id: int, slot: int, quantity: int = 0) -> bool` | subject-id (item_id) + other-args(bag_id,slot,quantity) | - |
| 37 | use_item_by_model_id | free fn | `(model_id: int, bag_start: int = 1, bag_end: int = 4) -> bool` | subject-id (model_id) + other-args(bag range) | - |
| 38 | count_item_by_model_id | free fn | `(model_id: int, bag_start: int = 1, bag_end: int = 4) -> int` | subject-id (model_id) + other-args(bag range) | - |
| 39 | get_gold_amount_on_character | free fn | `() -> int` | NO-ARG getter | - |
| 40 | get_gold_amount_in_storage | free fn | `() -> int` | NO-ARG getter | - |
| 41 | drop_gold | free fn | `(amount: int = 1) -> bool` | action/mutator | - |
| 42 | deposit_gold | free fn | `(amount: int = 0) -> int` | action/mutator | - |
| 43 | withdraw_gold | free fn | `(amount: int = 0) -> int` | action/mutator | - |
| 44 | change_gold | free fn | `(character_gold: int, storage_gold: int) -> bool` | action/mutator | - |
| 45 | salvage_start | free fn | `(salvage_kit_id: int, item_id: int) -> bool` | subject-id (item_id/kit_id) | - |
| 46 | identify_item | free fn | `(identification_kit_id: int, item_id: int) -> bool` | subject-id (item_id/kit_id) | - |
| 47 | salvage_session_cancel | free fn | `() -> bool` | action/mutator | - |
| 48 | salvage_session_done | free fn | `() -> bool` | action/mutator | - |
| 49 | destroy_item | free fn | `(item_id: int) -> bool` | subject-id (item_id) | - |
| 50 | salvage_materials | free fn | `() -> bool` | action/mutator | - |
| 51 | open_xunlai_window | free fn | `(anniversary_pane_unlocked: bool = True) -> None` | action/mutator | - |
| 52 | get_storage_page | free fn | `() -> int` | NO-ARG getter | - |
| 53 | get_is_storage_open | free fn | `() -> bool` | NO-ARG getter | - |
| 54 | can_access_xunlai_chest | free fn | `() -> bool` | NO-ARG getter | - |
| 55 | get_material_storage_stack_size | free fn | `() -> int` | NO-ARG getter | - |

### Struct return types & fields
(No method returns a bound struct; structs below are the classes registered in the module and used as field types / constructible values.)

| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| ItemModifier | (methods only — see table above) | — | def method |
| Rarity (enum) | White | int=0 | py::enum_ value |
| Rarity (enum) | Blue | int=1 | py::enum_ value |
| Rarity (enum) | Purple | int=2 | py::enum_ value |
| Rarity (enum) | Gold | int=3 | py::enum_ value |
| Rarity (enum) | Green | int=4 | py::enum_ value |
| ItemTypeClass | (methods only) | — | def method |
| DyeColorClass | (methods only) | — | def method |
| DyeInfo (PyDyeInfo) | dye_tint | int (uint8_t) | def_readonly |
| DyeInfo (PyDyeInfo) | dye1 | DyeColorClass | def_readonly |
| DyeInfo (PyDyeInfo) | dye2 | DyeColorClass | def_readonly |
| DyeInfo (PyDyeInfo) | dye3 | DyeColorClass | def_readonly |
| DyeInfo (PyDyeInfo) | dye4 | DyeColorClass | def_readonly |
| PyItem (PyItemData) | item_id | int | def_readonly |
| PyItem | agent_id | int | def_readonly |
| PyItem | agent_item_id | int | def_readonly |
| PyItem | name | str | def_readonly (never populated by GetContext; use GetName()) |
| PyItem | modifiers | List[ItemModifier] | def_readonly |
| PyItem | is_customized | bool | def_readonly |
| PyItem | item_type | ItemTypeClass | def_readonly |
| PyItem | dye_info | DyeInfo | def_readonly |
| PyItem | value | int | def_readonly |
| PyItem | interaction | int (uint32_t) | def_readonly |
| PyItem | model_id | int (uint32_t) | def_readonly |
| PyItem | model_file_id | int (uint32_t) | def_readonly |
| PyItem | item_formula | int | def_readonly |
| PyItem | is_material_salvageable | int | def_readonly |
| PyItem | quantity | int | def_readonly |
| PyItem | equipped | int | def_readonly |
| PyItem | profession | int | def_readonly |
| PyItem | slot | int | def_readonly |
| PyItem | is_stackable | bool | def_readonly |
| PyItem | is_inscribable | bool | def_readonly |
| PyItem | is_material | bool | def_readonly |
| PyItem | is_zcoin | bool | def_readonly |
| PyItem | rarity | Rarity | def_readonly |
| PyItem | uses | int | def_readonly |
| PyItem | is_id_kit | bool | def_readonly |
| PyItem | is_salvage_kit | bool | def_readonly |
| PyItem | is_tome | bool | def_readonly |
| PyItem | is_lesser_kit | bool | def_readonly |
| PyItem | is_expert_salvage_kit | bool | def_readonly |
| PyItem | is_perfect_salvage_kit | bool | def_readonly |
| PyItem | is_weapon | bool | def_readonly |
| PyItem | is_armor | bool | def_readonly |
| PyItem | is_salvageable | bool | def_readonly |
| PyItem | is_inventory_item | bool | def_readonly |
| PyItem | is_storage_item | bool | def_readonly |
| PyItem | is_rare_material | bool | def_readonly |
| PyItem | is_offered_in_trade | bool | def_readonly |
| PyItem | is_sparkly | bool | def_readonly |
| PyItem | is_identified | bool | def_readonly |
| PyItem | is_prefix_upgradable | bool | def_readonly |
| PyItem | is_suffix_upgradable | bool | def_readonly |
| PyItem | is_usable | bool | def_readonly |
| PyItem | is_tradable | bool | def_readonly |
| PyItem | is_inscription | bool | def_readonly |
| PyItem | is_rarity_blue | bool | def_readonly |
| PyItem | is_rarity_purple | bool | def_readonly |
| PyItem | is_rarity_green | bool | def_readonly |
| PyItem | is_rarity_gold | bool | def_readonly |

### Stub vs Native disagreements
- native-only (missing from stub entirely): free functions `pick_up_item_by_id`, `move_item`, `use_item_by_model_id`, `count_item_by_model_id`, `get_gold_amount_on_character`, `get_gold_amount_in_storage`, `drop_gold`, `deposit_gold`, `withdraw_gold`, `change_gold`, `salvage_start`, `identify_item`, `salvage_session_cancel`, `salvage_session_done`, `destroy_item`, `salvage_materials`, `open_xunlai_window`, `get_storage_page`, `get_is_storage_open`, `can_access_xunlai_chest`, `get_material_storage_stack_size`. Stub only lists `use_item_by_id`, `equip_item_by_id`, `drop_item_by_id`.
- native-only member: `PyItem.model_file_id` field is bound (`def_readonly`) but the stub DOES list it — actually in sync. (No drift.)
- signature drift: `drop_item_by_id` — stub declares `quantity: int = 1` but native `py::arg("quantity")` has NO default (required arg).
- signature/semantics drift: `PyItem.GetCompositeModelIDs(item_id)` — stub param named `item_id`, native param is `model_file_id` (different meaning; expects a model file id not item id).
- return-type drift: `ItemModifier.GetModBits` stub says `-> int`, native returns `std::string` (str). Same for the module doc — GetModBits is a bit-string.
- stub-only helper method absence: native `ItemModifier` binds only `GetIdentifier/GetArg1/GetArg2/GetArg/IsValid/GetModBits/ToString`; it does NOT bind `GetIdentifierBits/GetArg1Bits/GetArg2Bits/GetArgBits` (those C++ methods exist but are unbound) — stub correctly omits them. In sync on that point.

---

## PyInventory
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\item\inventory_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyInventory.pyi
- Module shape: mix (classes `Bag` + `PyInventory` + module-level free functions)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | `__init__` | Bag.method | `(bag_id: int, bag_name: str = "") -> None` | other-args(bag_id,name) | - |
| 2 | GetItems | Bag.method | `() -> List[Dict[str, Any]]` (py::list of dicts: item_id/slot/model_id/quantity) | NO-ARG getter | - |
| 3 | GetItemCount | Bag.method | `() -> int` | NO-ARG getter | - |
| 4 | GetSize | Bag.method | `() -> int` | NO-ARG getter | - |
| 5 | GetContext | Bag.method | `() -> None` | action/mutator (refreshes fields) | - |
| 6 | `__init__` | PyInventory.method | `() -> None` | NO-ARG getter | - |
| 7 | OpenXunlaiWindow | PyInventory.method | `() -> None` (queues via game_thread) | action/mutator (queues) | - |
| 8 | GetIsStorageOpen | PyInventory.method | `() -> bool` | NO-ARG getter | - |
| 9 | PickUpItem | PyInventory.method | `(item_id: int, call_target: bool = False) -> bool` (native returns void; queues) | subject-id (item_id) / action (queues) | - |
| 10 | DropItem | PyInventory.method | `(item_id: int, quantity: int = 1) -> bool` (native void; queues) | subject-id (item_id) / action | - |
| 11 | EquipItem | PyInventory.method | `(item_id: int, agent_id: int) -> bool` (native void; queues) | subject-id (item_id,agent_id) / action | - |
| 12 | UseItem | PyInventory.method | `(item_id: int) -> bool` (native void; queues) | subject-id (item_id) / action | - |
| 13 | DestroyItem | PyInventory.method | `(item_id: int) -> bool` (native void; queues) | subject-id (item_id) / action | - |
| 14 | IdentifyItem | PyInventory.method | `(id_kit_id: int, item_id: int) -> bool` (native void; queues) | subject-id (item_id,kit) / action | - |
| 15 | GetHoveredItemID | PyInventory.method | `() -> int` | NO-ARG getter | - |
| 16 | GetGoldAmount | PyInventory.method | `() -> int` | NO-ARG getter | - |
| 17 | GetGoldAmountInStorage | PyInventory.method | `() -> int` | NO-ARG getter | - |
| 18 | DepositGold | PyInventory.method | `(amount: int) -> int` (native void; queues) | action/mutator (queues) | - |
| 19 | WithdrawGold | PyInventory.method | `(amount: int) -> int` (native void; queues) | action/mutator (queues) | - |
| 20 | DropGold | PyInventory.method | `(amount: int) -> bool` (native void; queues) | action/mutator (queues) | - |
| 21 | MoveItem | PyInventory.method | `(item_id: int, bag_id: int, slot: int, quantity: int = 1) -> bool` (native void; queues) | subject-id (item_id) / action | - |
| 22 | Salvage | PyInventory.method | `(salv_kit_id: int, item_id: int) -> None` (runs SalvageStart directly, not queued) | subject-id (item_id,kit) / action | - |
| 23 | AcceptSalvageWindow | PyInventory.method | `() -> None` (queues UI ButtonClick) | action/mutator (queues) | - |
| 24 | get_bag | free fn | `(bag_id: int) -> dict` (snapshot dict incl. `items` list) | subject-id (bag_id) | - |
| 25 | get_hovered_item_id | free fn | `() -> int` | NO-ARG getter | - |
| 26 | salvage | free fn | `(salv_kit_id: int, item_id: int) -> None` (runs SalvageStart directly) | subject-id (item_id,kit) / action | - |
| 27 | accept_salvage_window | free fn | `() -> None` (queues UI ButtonClick) | action/mutator (queues) | - |

### Struct return types & fields
(No method returns a bound struct — `GetItems`/`get_bag` return plain py::list/py::dict. Bound class field members:)

| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| Bag | id | int | def_readonly |
| Bag | name | str | def_readonly |
| Bag | container_item | int | def_readonly |
| Bag | items_count | int | def_readonly |
| Bag | is_inventory_bag | bool | def_readonly |
| Bag | is_storage_bag | bool | def_readonly |
| Bag | is_material_storage | bool | def_readonly |
| PyInventory | (no data members; methods only) | — | def method |

`get_bag` dict keys: `id`, `items_count`, `container_item`, `size`, `is_inventory_bag`, `is_storage_bag`, `is_material_storage`, `items` (list of `{item_id, slot, model_id, quantity}`).
`Bag.GetItems` list entries: `{item_id, slot, model_id, quantity}`.

### Stub vs Native disagreements
- return-type drift (widespread): stub annotates most `PyInventory` mutators as returning `bool`/`int` (`PickUpItem`, `DropItem`, `EquipItem`, `UseItem`, `DestroyItem`, `IdentifyItem`, `DepositGold`, `WithdrawGold`, `DropGold`, `MoveItem`), but native methods all return `void` (they enqueue onto the game thread). Only `GetIsStorageOpen`/getters genuinely return values.
- Otherwise method set is In sync (stub header comments correctly note `IsSalvaging`/`IsSalvageTransactionDone`/`FinishSalvage`/`GetItemByIndex`/`FindItemById` are absent from Reforged).

---

## PyMerchant
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\merchant\merchant_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyMerchant.pyi
- Module shape: mix (class `PyMerchant` with all-static methods + 2 module-level free functions)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | `__init__` | PyMerchant.method | `() -> None` | NO-ARG getter | - |
| 2 | trader_buy_item | PyMerchant.method (`def_static`) | `(item_id: int, cost: int) -> bool` (queues) | subject-id (item_id) / action | - |
| 3 | trader_sell_item | PyMerchant.method (`def_static`) | `(item_id: int, price: int) -> bool` (queues) | subject-id (item_id) / action | - |
| 4 | trader_request_quote | PyMerchant.method (`def_static`) | `(item_id: int) -> bool` (queues) | subject-id (item_id) / action | - |
| 5 | trader_request_sell_quote | PyMerchant.method (`def_static`) | `(item_id: int) -> bool` (queues) | subject-id (item_id) / action | - |
| 6 | merchant_buy_item | PyMerchant.method (`def_static`) | `(item_id: int, cost: int) -> bool` (queues) | subject-id (item_id) / action | - |
| 7 | merchant_sell_item | PyMerchant.method (`def_static`) | `(item_id: int, price: int) -> bool` (queues) | subject-id (item_id) / action | - |
| 8 | crafter_buy_item | PyMerchant.method (`def_static`) | `(item_id: int, cost: int, give_item_ids: List[int], give_item_quantities: List[int]) -> bool` (runs directly) | subject-id (item_id) + other-args(lists) / action | - |
| 9 | collector_buy_item | PyMerchant.method (`def_static`) | `(item_id: int, cost: int, give_item_ids: List[int], give_item_quantities: List[int]) -> bool` (runs directly) | subject-id (item_id) + other-args(lists) / action | - |
| 10 | get_trader_item_list | PyMerchant.method (`def_static`) | `() -> List[int]` | NO-ARG getter | - |
| 11 | get_trader_item_list2 | PyMerchant.method (`def_static`) | `() -> List[int]` (always empty; legacy never populated) | NO-ARG getter | - |
| 12 | get_merchant_item_list | PyMerchant.method (`def_static`) | `() -> List[int]` | NO-ARG getter | - |
| 13 | get_quoted_value | PyMerchant.method (`def_static`) | `() -> int` | NO-ARG getter | - |
| 14 | get_quoted_item_id | PyMerchant.method (`def_static`) | `() -> int` | NO-ARG getter | - |
| 15 | is_transaction_complete | PyMerchant.method (`def_static`) | `() -> bool` | NO-ARG getter | - |
| 16 | update | PyMerchant.method (`def_static`) | `() -> None` (no-op; state refreshed by listeners) | action/mutator (no-op) | - |
| 17 | transact_items | free fn | `(type: int, gold_give: int = 0, give_item_ids: list = [], give_quantities: list = [], gold_recv: int = 0, recv_item_ids: list = [], recv_quantities: list = []) -> bool` | other-args(txn type + lists) / action | - |
| 18 | request_quote | free fn | `(type: int, give_item_ids: list = [], recv_item_ids: list = []) -> bool` | other-args(txn type + lists) / action | - |

### Struct return types & fields
No `py::class_` structs are exposed with data members. `PyMerchant` binds only static methods (no fields). `GW::Context::MerchantTransactionInfo` / `MerchantQuoteInfo` are used internally only and are NOT bound to Python. No method returns a bound struct.

| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| PyMerchant | (no data members; all `def_static` methods) | — | def_static method |

### Stub vs Native disagreements
- native-only (missing from stub): module-level free functions `transact_items` and `request_quote` are not in the stub at all.
- signature/binding drift: stub declares all `PyMerchant` methods as instance methods (`def trader_buy_item(self, ...)`), but native binds them via `def_static` (they take no `self`). Callable both ways in practice, but stub misrepresents them as instance methods.
- Method name set otherwise In sync.

---

## PyTrade
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\trade\trade_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyTrading.pyi
- Module shape: module-level free functions only (no classes bound). NOTE: module name is `PyTrade`; stub file `PyTrading.pyi` declares a class `PyTrading` (mismatch — see disagreements).

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | open_trade_window | free fn | `(agent_id: int) -> bool` (queues OpenTradeWindow; always returns True) | subject-id (agent_id) / action | - |
| 2 | accept_trade | free fn | `() -> bool` | action/mutator | - |
| 3 | cancel_trade | free fn | `() -> bool` | action/mutator | - |
| 4 | change_offer | free fn | `() -> bool` | action/mutator | - |
| 5 | submit_offer | free fn | `(gold: int) -> bool` | action/mutator | - |
| 6 | remove_item | free fn | `(slot: int) -> bool` | subject-id (slot) / action | - |
| 7 | offer_item | free fn | `(item_id: int, quantity: int = 0) -> bool` | subject-id (item_id) / action | - |
| 8 | is_item_offered | free fn | `(item_id: int) -> bool` (native: `IsItemOffered(item_id) != nullptr`) | subject-id (item_id) | - |

### Struct return types & fields
No `py::class_` registered in this module. No struct returned (`is_item_offered` collapses the pointer result to bool). No fields.

### Stub vs Native disagreements
- MAJOR shape mismatch: native module is `PyTrade` exposing **snake_case free functions**; the stub `PyTrading.pyi` declares a **class `PyTrading` with PascalCase static methods** (`OpenTradeWindow`, `AcceptTrade`, `CancelTrade`, `ChangeOffer`, `SubmitOffer`, `RemoveItem`, `OfferItem`, `IsItemOffered`, plus `GetItemOffered`, `IsTradeOffered`, `IsTradeInitiated`, `IsTradeAccepted`). The stub does not describe the actual native binding at all.
- native-only: free functions `open_trade_window`, `accept_trade`, `cancel_trade`, `change_offer`, `submit_offer`, `remove_item`, `offer_item`, `is_item_offered` — none appear (by name/casing) in the stub.
- stub-only: `GetItemOffered`, `IsTradeOffered`, `IsTradeInitiated`, `IsTradeAccepted` — not bound in native at all. `OpenTradeWindow`/`AcceptTrade`/etc. PascalCase names not bound either.
- return-type drift: stub `OpenTradeWindow -> None`; native `open_trade_window -> bool`.


---


# R2 Batch b4 — PySkill / PySkillbar / PyQuest / PyDialog method inventory

## PySkill
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\skillbar\skill_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PySkill.pyi`
- Module shape: class(es) only — four bound classes (`SkillID`, `SkillType`, `SkillProfession`, `Skill`); no module-level free functions. All data is populated eagerly at construction from `GW::skillbar::GetSkillConstantData`.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | `__init__` | `SkillID.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 2 | `__init__` | `SkillID.__init__` | `(id: int) -> None` | subject-id (skill_id) | - |
| 3 | `__init__` | `SkillID.__init__` | `(skillname: str) -> None` | other-args(name str) | - |
| 4 | `__eq__` | `SkillID.__eq__` | `(other: int) -> bool` | other-args(int) | - |
| 5 | `__ne__` | `SkillID.__ne__` | `(other: int) -> bool` | other-args(int) | - |
| 6 | `GetName` | `SkillID.GetName` | `() -> str` | NO-ARG getter | - |
| 7 | `__init__` | `SkillType.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 8 | `__init__` | `SkillType.__init__` | `(type_id: int) -> None` | subject-id (type_id) | - |
| 9 | `__eq__` | `SkillType.__eq__` | `(other: int) -> bool` | other-args(int) | - |
| 10 | `__ne__` | `SkillType.__ne__` | `(other: int) -> bool` | other-args(int) | - |
| 11 | `GetName` | `SkillType.GetName` | `() -> str` | NO-ARG getter | - |
| 12 | `__init__` | `SkillProfession.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 13 | `__init__` | `SkillProfession.__init__` | `(id: int) -> None` | subject-id (profession_id) | - |
| 14 | `ToInt` | `SkillProfession.ToInt` | `() -> int` | NO-ARG getter | - |
| 15 | `GetName` | `SkillProfession.GetName` | `() -> str` | NO-ARG getter | - |
| 16 | `__init__` | `Skill.__init__` | `() -> None` | NO-ARG getter (ctor; calls GetContext) | - |
| 17 | `__init__` | `Skill.__init__` | `(id: int) -> None` | subject-id (skill_id) | - |
| 18 | `__init__` | `Skill.__init__` | `(skillname: str) -> None` | other-args(name str) | - |
| 19 | `GetContext` | `Skill.GetContext` | `() -> None` | action/mutator (refreshes fields from constant data) | - |

Note: `SkillProfession` class is native-only (see disagreements). All `Skill`/`SkillID`/`SkillType` data is exposed as `def_readonly` fields (see struct table), not methods.

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|---|---|---|---|
| SkillID | id | int | def_readonly |
| SkillType | id | int | def_readonly |
| SkillProfession | id | int | def_readonly |
| Skill | id | SkillID | def_readonly |
| Skill | campaign | int | def_readonly |
| Skill | type | SkillType | def_readonly |
| Skill | special | int | def_readonly |
| Skill | combo_req | int | def_readonly |
| Skill | effect1 | int | def_readonly |
| Skill | condition | int | def_readonly |
| Skill | effect2 | int | def_readonly |
| Skill | weapon_req | int | def_readonly |
| Skill | profession | SkillProfession | def_readonly |
| Skill | attribute | int | def_readonly |
| Skill | title | int | def_readonly |
| Skill | id_pvp | int | def_readonly |
| Skill | combo | int | def_readonly |
| Skill | target | int | def_readonly |
| Skill | skill_equip_type | int | def_readonly |
| Skill | overcast | int | def_readonly |
| Skill | energy_cost | int | def_readonly |
| Skill | health_cost | int | def_readonly |
| Skill | adrenaline | int | def_readonly |
| Skill | activation | float | def_readonly |
| Skill | aftercast | float | def_readonly |
| Skill | duration_0pts | int | def_readonly |
| Skill | duration_15pts | int | def_readonly |
| Skill | recharge | int | def_readonly |
| Skill | skill_arguments | int | def_readonly |
| Skill | scale_0pts | int | def_readonly |
| Skill | scale_15pts | int | def_readonly |
| Skill | bonus_scale_0pts | int | def_readonly |
| Skill | bonus_scale_15pts | int | def_readonly |
| Skill | aoe_range | float | def_readonly |
| Skill | const_effect | float | def_readonly |
| Skill | caster_overhead_animation_id | int | def_readonly |
| Skill | caster_body_animation_id | int | def_readonly |
| Skill | target_body_animation_id | int | def_readonly |
| Skill | target_overhead_animation_id | int | def_readonly |
| Skill | projectile_animation1_id | int | def_readonly |
| Skill | projectile_animation2_id | int | def_readonly |
| Skill | icon_file_id | int | def_readonly |
| Skill | icon_file2_id | int | def_readonly |
| Skill | icon_file_hi_res_id | int | def_readonly |
| Skill | name_id | int | def_readonly |
| Skill | concise | int | def_readonly |
| Skill | description_id | int | def_readonly |
| Skill | is_touch_range | bool | def_readonly |
| Skill | is_elite | bool | def_readonly |
| Skill | is_half_range | bool | def_readonly |
| Skill | is_pvp | bool | def_readonly |
| Skill | is_pve | bool | def_readonly |
| Skill | is_playable | bool | def_readonly |
| Skill | is_stacking | bool | def_readonly |
| Skill | is_non_stacking | bool | def_readonly |
| Skill | is_unused | bool | def_readonly |
| Skill | adrenaline_a | int | def_readonly (vestigial, always 0) |
| Skill | adrenaline_b | int | def_readonly (vestigial, always 0) |
| Skill | recharge2 | int | def_readonly (vestigial, always 0) |
| Skill | h0004 | int (uint32) | def_readonly |
| Skill | h0032 | int | def_readonly |
| Skill | h0037 | int | def_readonly |

### Stub vs Native disagreements
- **native-only class**: `SkillProfession` (with `ToInt`/`GetName`/`id`) is registered in native but NOT declared in the stub.
- **native-only ctor arg name**: `SkillID(name)` ctor uses `py::arg("skillname")` — stub matches. `SkillType` int ctor has NO `py::arg` name in native (stub calls it `skilltype`); positional only, minor.
- **type drift on `Skill` fields**: stub types `Skill.profession: Profession` and `Skill.attribute: AttributeClass` (imported from `PyAgent`), but native returns `profession` as a bound `SkillProfession` object and `attribute` as a plain `int`. The `.attribute` is documented in the cpp as a first-pass simplification (raw id, no wrapper).
- **field order**: stub lists `icon_file_hi_res_id` before `icon_file_id`/`icon_file2_id`; native registers `icon_file_id`, `icon_file2_id`, `icon_file_hi_res_id` in that order. Cosmetic only (all keyword-accessible).
- Otherwise all `Skill` fields and both `GetName`/`GetContext` are in sync.

---

## PySkillbar
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\skillbar\skillbar_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PySkillbar.pyi`
- Module shape: mix — two bound classes (`SkillbarSkill`, `Skillbar`) plus 15 module-level free functions.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | `id` (prop) | `SkillbarSkill.id` | `-> PySkill.SkillID` | NO-ARG getter (property) | SkillID (PySkill) |
| 2 | `get_recharge` (prop) | `SkillbarSkill.get_recharge` | `-> int` | NO-ARG getter (property) | - |
| 3 | `__init__` | `Skillbar.__init__` | `() -> None` | NO-ARG getter (ctor; snapshots player skillbar) | - |
| 4 | `agent_id` (prop) | `Skillbar.agent_id` | `-> int` | NO-ARG getter (property) | - |
| 5 | `disabled` (prop) | `Skillbar.disabled` | `-> int` | NO-ARG getter (property) | - |
| 6 | `casting` (prop) | `Skillbar.casting` | `-> int` | NO-ARG getter (property) | - |
| 7 | `skills` (prop) | `Skillbar.skills` | `-> List[SkillbarSkill]` | NO-ARG getter (property) | SkillbarSkill[] |
| 8 | `GetContext` | `Skillbar.GetContext` | `() -> None` | action/mutator (refresh snapshot) | - |
| 9 | `GetSkill` | `Skillbar.GetSkill` | `(slot: int) -> SkillbarSkill` | other-args(slot 1-8) | SkillbarSkill |
| 10 | `GetSkills`* | `Skillbar.skills` backing fn | `() -> list` | NO-ARG getter | SkillbarSkill[] |
| 11 | `LoadSkillTemplate` | `Skillbar.LoadSkillTemplate` | `(skill_template: str) -> bool` | other-args(template str) | - |
| 12 | `LoadHeroSkillTemplate` | `Skillbar.LoadHeroSkillTemplate` | `(hero_index: int, skill_template: str) -> bool` | other-args(hero_index, template) | - |
| 13 | `UseSkill` | `Skillbar.UseSkill` | `(slot: int, target: int = 0) -> bool` | action/mutator (queues UseSkill) | - |
| 14 | `UseSkillTargetless` | `Skillbar.UseSkillTargetless` | `(slot: int) -> bool` | action/mutator (queues point-blank) | - |
| 15 | `HeroUseSkill` | `Skillbar.HeroUseSkill` | `(target_agent_id: int, skill_number: int, hero_idx: int) -> bool` | action/mutator (queues keypress) | - |
| 16 | `ChangeHeroSecondary` | `Skillbar.ChangeHeroSecondary` | `(hero_index: int, profession: int) -> bool` | action/mutator | - |
| 17 | `GetHeroSkillbar` | `Skillbar.GetHeroSkillbar` | `(hero_index: int) -> List[SkillbarSkill]` | subject-id (hero_index) | SkillbarSkill[] |
| 18 | `GetHoveredSkill` | `Skillbar.GetHoveredSkill` | `() -> int` | NO-ARG getter | - |
| 19 | `IsSkillUnlocked` | `Skillbar.IsSkillUnlocked` | `(skill_id: int) -> bool` | subject-id (skill_id) | - |
| 20 | `IsSkillLearnt` | `Skillbar.IsSkillLearnt` | `(skill_id: int) -> bool` | subject-id (skill_id) | - |
| 21 | `get_skill_slot` | free fn | `(skill_id: int) -> int` | subject-id (skill_id) | - |
| 22 | `use_skill` | free fn | `(slot: int, target: int = 0) -> bool` | action/mutator (queues) | - |
| 23 | `point_blank_use_skill` | free fn | `(slot: int) -> bool` | action/mutator (queues) | - |
| 24 | `use_skill_by_id` | free fn | `(skill_id: int, target: int = 0) -> bool` | action/mutator | - |
| 25 | `get_is_skill_unlocked` | free fn | `(skill_id: int) -> bool` | subject-id (skill_id) | - |
| 26 | `get_is_skill_learnt` | free fn | `(skill_id: int) -> bool` | subject-id (skill_id) | - |
| 27 | `get_skill_profession` | free fn | `(skill_id: int) -> int` | subject-id (skill_id) | - |
| 28 | `get_skill_icon_file_id` | free fn | `(skill_id: int) -> int` | subject-id (skill_id) | - |
| 29 | `get_skill_icon_file_id_hi_res` | free fn | `(skill_id: int) -> int` | subject-id (skill_id) | - |
| 30 | `get_attribute_profession` | free fn | `(attribute_id: int) -> int` | subject-id (attribute_id) | - |
| 31 | `change_second_profession` | free fn | `(profession: int, hero_index: int = 0) -> bool` | action/mutator | - |
| 32 | `load_skill_template` | free fn | `(template: str, hero_index: int = 0) -> bool` | action/mutator | - |
| 33 | `load_skillbar` | free fn | `(skill_ids: list, hero_index: int = 0) -> bool` | action/mutator (list of skill ids, max 8) | - |
| 34 | `set_attributes` | free fn | `(attribute_ids: list, attribute_values: list, hero_index: int = 0) -> bool` | action/mutator | - |
| 35 | `encode_skill_template` | free fn | `(hero_index: int = 0) -> str` | other-args(hero_index) | - |
| 36 | `decode_skill_template` | free fn | `(template: str) -> dict` | other-args(template str) → dict{profession, secondary_profession, skills[8], attributes[{id,level}]} | - |
| 37 | `get_hovered_skill_id` | free fn | `() -> int` | NO-ARG getter | - |
| 38 | `hero_use_skill` | free fn | `(target_agent_id: int, skill_number: int, hero_index: int) -> bool` | action/mutator (queues keypress) | - |

*Row 10 (`GetSkills`) is the C++ backing method for the `skills` property; not separately exposed as a callable name — it only surfaces as the `skills` read-only property (row 7). Counted informationally, not as a distinct Python attribute.

### Struct return types & fields
`SkillbarSkill` is bound directly on `GW::Context::SkillbarSkill` (header `include\GW\context\skill.h`, struct at line 91). `Skillbar` (`PySkillbarObject`) exposes all data via properties (listed as methods above), not `def_readwrite`.

| Struct/Class | Member | Type | Binding kind |
|---|---|---|---|
| SkillbarSkill | id | PySkill.SkillID | def_property_readonly (lambda → imports PySkill.SkillID from `s.skill_id`) |
| SkillbarSkill | adrenaline_a | int (uint32) | def_readonly |
| SkillbarSkill | adrenaline_b | int (uint32) | def_readonly |
| SkillbarSkill | recharge | int (uint32) | def_readonly |
| SkillbarSkill | event | int (uint32) | def_readonly |
| SkillbarSkill | get_recharge | int | def_property_readonly (lambda → `s.GetRecharge()`) |
| Skillbar | agent_id | int | def_property_readonly (lambda → `data.agent_id`) |
| Skillbar | disabled | int | def_property_readonly (lambda → `data.disabled`) |
| Skillbar | casting | int | def_property_readonly (lambda → `data.casting`) |
| Skillbar | skills | List[SkillbarSkill] | def_property_readonly (→ GetSkills) |

Underlying `GW::Context::SkillbarSkill` fields not exposed: `skill_id` is exposed only wrapped as `id` (SkillID). Underlying `Skillbar` snapshot has more raw fields (`h00A8`, `h00B4`, `skills[8]`) but only agent_id/disabled/casting/skills are surfaced.

### Stub vs Native disagreements
- **return-type drift on actions**: stub types `UseSkill -> None` and `UseSkillTargetless -> None`, but native returns `bool` (always `true`). Also `HeroUseSkill` returns bool in both — in sync.
- **native-only free functions**: the ENTIRE free-function surface (rows 21–38, 15 functions) is absent from the stub — the stub only declares the `SkillbarSkill` and `Skillbar` classes. Missing: `get_skill_slot`, `use_skill`, `point_blank_use_skill`, `use_skill_by_id`, `get_is_skill_unlocked`, `get_is_skill_learnt`, `get_skill_profession`, `get_skill_icon_file_id`, `get_skill_icon_file_id_hi_res`, `get_attribute_profession`, `change_second_profession`, `load_skill_template`, `load_skillbar`, `set_attributes`, `encode_skill_template`, `decode_skill_template`, `get_hovered_skill_id`, `hero_use_skill`.
- **stub-only ctor for SkillbarSkill**: stub declares `SkillbarSkill.__init__(id, adrenaline_a=0, ...)`, but native registers NO constructor for `SkillbarSkill` (it is only produced internally as snapshot data). Stub-only.
- Class methods on `Skillbar` are otherwise in sync (names/args match).

---

## PyQuest
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\quest\quest_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PyQuest.pyi`
- Module shape: mix — `QuestData` data class, `PyQuest` static-method class (27 static methods), plus a parallel free-function surface (18 module-level functions). Same operations exposed both as `PyQuest.<static>` and as `m.<free fn>`.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | `__init__` | `QuestData.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 2 | `__init__` | `PyQuest.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 3 | `set_active_quest_id` | `PyQuest.set_active_quest_id` (static) | `(quest_id: int) -> bool` | action/mutator (queues) | - |
| 4 | `get_active_quest_id` | `PyQuest.get_active_quest_id` (static) | `() -> int` | NO-ARG getter | - |
| 5 | `abandon_quest_id` | `PyQuest.abandon_quest_id` (static) | `(quest_id: int) -> bool` | action/mutator (queues) | - |
| 6 | `is_quest_completed` | `PyQuest.is_quest_completed` (static) | `(quest_id: int) -> bool` | subject-id (quest_id) | - |
| 7 | `is_quest_primary` | `PyQuest.is_quest_primary` (static) | `(quest_id: int) -> bool` | subject-id (quest_id) | - |
| 8 | `is_mission_map_quest_available` | `PyQuest.is_mission_map_quest_available` (static) | `() -> bool` | NO-ARG getter | - |
| 9 | `get_quest_data` | `PyQuest.get_quest_data` (static) | `(quest_id: int) -> QuestData` | subject-id (quest_id) | QuestData |
| 10 | `get_quest_log` | `PyQuest.get_quest_log` (static) | `() -> list[QuestData]` | NO-ARG getter | QuestData[] |
| 11 | `get_quest_log_ids` | `PyQuest.get_quest_log_ids` (static) | `() -> list[int]` | NO-ARG getter | - |
| 12 | `request_quest_info` | `PyQuest.request_quest_info` (static) | `(quest_id: int, update_markers: bool = False) -> bool` | other-args(quest_id, update_markers) | - |
| 13 | `request_quest_name` | `PyQuest.request_quest_name` (static) | `(quest_id: int) -> None` | subject-id (quest_id, async kick) | - |
| 14 | `is_quest_name_ready` | `PyQuest.is_quest_name_ready` (static) | `(quest_id: int) -> bool` | subject-id (quest_id) | - |
| 15 | `get_quest_name` | `PyQuest.get_quest_name` (static) | `(quest_id: int) -> str` | subject-id (quest_id) | - |
| 16 | `request_quest_description` | `PyQuest.request_quest_description` (static) | `(quest_id: int) -> None` | subject-id (quest_id, async kick) | - |
| 17 | `is_quest_description_ready` | `PyQuest.is_quest_description_ready` (static) | `(quest_id: int) -> bool` | subject-id (quest_id) | - |
| 18 | `get_quest_description` | `PyQuest.get_quest_description` (static) | `(quest_id: int) -> str` | subject-id (quest_id) | - |
| 19 | `request_quest_objectives` | `PyQuest.request_quest_objectives` (static) | `(quest_id: int) -> None` | subject-id (quest_id, async kick) | - |
| 20 | `is_quest_objectives_ready` | `PyQuest.is_quest_objectives_ready` (static) | `(quest_id: int) -> bool` | subject-id (quest_id) | - |
| 21 | `get_quest_objectives` | `PyQuest.get_quest_objectives` (static) | `(quest_id: int) -> str` | subject-id (quest_id) | - |
| 22 | `request_quest_location` | `PyQuest.request_quest_location` (static) | `(quest_id: int) -> None` | subject-id (quest_id, async kick) | - |
| 23 | `is_quest_location_ready` | `PyQuest.is_quest_location_ready` (static) | `(quest_id: int) -> bool` | subject-id (quest_id) | - |
| 24 | `get_quest_location` | `PyQuest.get_quest_location` (static) | `(quest_id: int) -> str` | subject-id (quest_id) | - |
| 25 | `request_quest_npc` | `PyQuest.request_quest_npc` (static) | `(quest_id: int) -> None` | subject-id (quest_id, async kick) | - |
| 26 | `is_quest_npc_ready` | `PyQuest.is_quest_npc_ready` (static) | `(quest_id: int) -> bool` | subject-id (quest_id) | - |
| 27 | `get_quest_npc` | `PyQuest.get_quest_npc` (static) | `(quest_id: int) -> str` | subject-id (quest_id) | - |
| 28 | `set_active_quest_id` | free fn | `(quest_id: int) -> bool` | action/mutator (queues) | - |
| 29 | `abandon_quest_id` | free fn | `(quest_id: int) -> bool` | action/mutator (queues) | - |
| 30 | `get_active_quest_id` | free fn | `() -> int` | NO-ARG getter | - |
| 31 | `request_quest_info` | free fn | `(quest_id: int, update_markers: bool = False) -> bool` | other-args | - |
| 32 | `get_quest_entry_group_name` | free fn | `(quest_id: int) -> str` | subject-id (quest_id) | - |
| 33 | `is_quest_completed` | free fn | `(quest_id: int) -> bool` | subject-id (quest_id) | - |
| 34 | `is_quest_primary` | free fn | `(quest_id: int) -> bool` | subject-id (quest_id) | - |
| 35 | `is_mission_map_quest_available` | free fn | `() -> bool` | NO-ARG getter | - |
| 36 | `get_quest_log_ids` | free fn | `() -> list[int]` | NO-ARG getter | - |
| 37 | `request_quest_name` | free fn | `(quest_id: int) -> None` | subject-id (async kick) | - |
| 38 | `is_quest_name_ready` | free fn | `(quest_id: int) -> bool` | subject-id | - |
| 39 | `get_quest_name` | free fn | `(quest_id: int) -> str` | subject-id | - |
| 40 | `request_quest_description` | free fn | `(quest_id: int) -> None` | subject-id (async kick) | - |
| 41 | `is_quest_description_ready` | free fn | `(quest_id: int) -> bool` | subject-id | - |
| 42 | `get_quest_description` | free fn | `(quest_id: int) -> str` | subject-id | - |
| 43 | `request_quest_objectives` | free fn | `(quest_id: int) -> None` | subject-id (async kick) | - |
| 44 | `is_quest_objectives_ready` | free fn | `(quest_id: int) -> bool` | subject-id | - |
| 45 | `get_quest_objectives` | free fn | `(quest_id: int) -> str` | subject-id | - |
| 46 | `request_quest_location` | free fn | `(quest_id: int) -> None` | subject-id (async kick) | - |
| 47 | `is_quest_location_ready` | free fn | `(quest_id: int) -> bool` | subject-id | - |
| 48 | `get_quest_location` | free fn | `(quest_id: int) -> str` | subject-id | - |
| 49 | `request_quest_npc` | free fn | `(quest_id: int) -> None` | subject-id (async kick) | - |
| 50 | `is_quest_npc_ready` | free fn | `(quest_id: int) -> bool` | subject-id | - |
| 51 | `get_quest_npc` | free fn | `(quest_id: int) -> str` | subject-id | - |

### Struct return types & fields
`QuestData` is a module-local C++ struct (defined in the .cpp, not a GW context struct). Note: `GetQuest`/`GetQuestLog` only populate `quest_id, log_state, map_from, map_to, marker_x, marker_y, is_completed, is_primary`; the string fields (`location/name/npc/description/objectives`) and `is_current_mission_quest/is_area_primary/h0024` are default-empty (filled by the async request/get path, not by `get_quest_data`).

| Struct/Class | Member | Type | Binding kind |
|---|---|---|---|
| QuestData | quest_id | int (uint32) | def_readwrite |
| QuestData | log_state | int (uint32) | def_readwrite |
| QuestData | location | str | def_readwrite |
| QuestData | name | str | def_readwrite |
| QuestData | npc | str | def_readwrite |
| QuestData | map_from | int (uint32) | def_readwrite |
| QuestData | marker_x | float | def_readwrite |
| QuestData | marker_y | float | def_readwrite |
| QuestData | h0024 | int (uint32) | def_readwrite |
| QuestData | map_to | int (uint32) | def_readwrite |
| QuestData | description | str | def_readwrite |
| QuestData | objectives | str | def_readwrite |
| QuestData | is_completed | bool | def_readwrite |
| QuestData | is_current_mission_quest | bool | def_readwrite |
| QuestData | is_area_primary | bool | def_readwrite |
| QuestData | is_primary | bool | def_readwrite |

### Stub vs Native disagreements
- **native-only free-function surface**: none of the 24 module-level free functions (rows 28–51) are in the stub — the stub only declares `QuestData` and the `PyQuest` static class. Notably `get_quest_entry_group_name` (free fn, row 32) has NO `PyQuest.` static equivalent and is entirely stub-absent.
- **return-type drift**: stub types `PyQuest.set_active_quest_id -> None`, `abandon_quest_id -> None`, and the five `request_quest_*` statics as `-> None`; native `set_active_quest_id`/`abandon_quest_id` return `bool`. The `request_quest_*` methods do return `None` (in sync). 
- **QuestData field order**: stub orders `map_from, map_to, marker_x, marker_y, h0024, description...`; native registers `map_from, marker_x, marker_y, h0024, map_to, description...`. All keyword-accessible; cosmetic.
- Otherwise the `PyQuest` static-method surface matches the stub 1:1 (names/args).

---

## PyDialog
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\dialog\dialog_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PyDialog.pyi` (also compared: `C:\Users\Apo\Py4GW_Reforged\stubs\PyDialogCatalog.pyi`)
- Module shape: mix — six bound data structs (`DialogInfo`, `ActiveDialogInfo`, `DialogButtonInfo`, `DialogTextDecodedInfo`, `DialogEventLog`, `DialogCallbackJournalEntry`) plus one static-method class `PyDialog` (35 static methods). Merged module: absorbs the retired `PyDialogCatalog` surface. All functions delegate to `GW::dialog::*` namespace functions.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | `__init__` | `DialogInfo.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 2 | `__init__` | `ActiveDialogInfo.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 3 | `__init__` | `DialogButtonInfo.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 4 | `__init__` | `DialogTextDecodedInfo.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 5 | `__init__` | `DialogEventLog.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 6 | `__init__` | `DialogCallbackJournalEntry.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 7 | `__init__` | `PyDialog.__init__` | `() -> None` | NO-ARG getter (ctor) | - |
| 8 | `is_dialog_available` | `PyDialog` (static) | `(dialog_id: int) -> bool` | subject-id (dialog_id) | - |
| 9 | `get_dialog_info` | `PyDialog` (static) | `(dialog_id: int) -> DialogInfo` | subject-id (dialog_id) | DialogInfo |
| 10 | `get_last_selected_dialog_id` | `PyDialog` (static) | `() -> int` | NO-ARG getter | - |
| 11 | `get_active_dialog` | `PyDialog` (static) | `() -> ActiveDialogInfo` | NO-ARG getter | ActiveDialogInfo |
| 12 | `get_active_dialog_buttons` | `PyDialog` (static) | `() -> List[DialogButtonInfo]` | NO-ARG getter | DialogButtonInfo[] |
| 13 | `is_dialog_active` | `PyDialog` (static) | `() -> bool` | NO-ARG getter | - |
| 14 | `is_dialog_displayed` | `PyDialog` (static) | `(dialog_id: int) -> bool` | subject-id (dialog_id) | - |
| 15 | `enumerate_available_dialogs` | `PyDialog` (static) | `() -> List[DialogInfo]` | NO-ARG getter | DialogInfo[] |
| 16 | `get_dialog_text_decoded` | `PyDialog` (static) | `(dialog_id: int) -> str` | subject-id (dialog_id) | - |
| 17 | `is_dialog_text_decode_pending` | `PyDialog` (static) | `(dialog_id: int) -> bool` | subject-id (dialog_id) | - |
| 18 | `get_dialog_text_decode_status` | `PyDialog` (static) | `() -> List[DialogTextDecodedInfo]` | NO-ARG getter | DialogTextDecodedInfo[] |
| 19 | `read_dialog_flags` | `PyDialog` (static) | `(dialog_id: int) -> int` | subject-id (dialog_id) | - |
| 20 | `read_dialog_frame_type` | `PyDialog` (static) | `(dialog_id: int) -> int` | subject-id (dialog_id) | - |
| 21 | `read_dialog_event_handler` | `PyDialog` (static) | `(dialog_id: int) -> int` | subject-id (dialog_id) | - |
| 22 | `read_dialog_content_id` | `PyDialog` (static) | `(dialog_id: int) -> int` | subject-id (dialog_id) | - |
| 23 | `read_dialog_property_id` | `PyDialog` (static) | `(dialog_id: int) -> int` | subject-id (dialog_id) | - |
| 24 | `get_dialog_event_logs` | `PyDialog` (static) | `() -> List[DialogEventLog]` | NO-ARG getter | DialogEventLog[] |
| 25 | `get_dialog_event_logs_received` | `PyDialog` (static) | `() -> List[DialogEventLog]` | NO-ARG getter | DialogEventLog[] |
| 26 | `get_dialog_event_logs_sent` | `PyDialog` (static) | `() -> List[DialogEventLog]` | NO-ARG getter | DialogEventLog[] |
| 27 | `clear_dialog_event_logs` | `PyDialog` (static) | `() -> None` | action/mutator | - |
| 28 | `clear_dialog_event_logs_received` | `PyDialog` (static) | `() -> None` | action/mutator | - |
| 29 | `clear_dialog_event_logs_sent` | `PyDialog` (static) | `() -> None` | action/mutator | - |
| 30 | `get_dialog_callback_journal` | `PyDialog` (static) | `() -> List[DialogCallbackJournalEntry]` | NO-ARG getter | DialogCallbackJournalEntry[] |
| 31 | `get_dialog_callback_journal_received` | `PyDialog` (static) | `() -> List[DialogCallbackJournalEntry]` | NO-ARG getter | DialogCallbackJournalEntry[] |
| 32 | `get_dialog_callback_journal_sent` | `PyDialog` (static) | `() -> List[DialogCallbackJournalEntry]` | NO-ARG getter | DialogCallbackJournalEntry[] |
| 33 | `clear_dialog_callback_journal` | `PyDialog` (static) | `() -> None` | action/mutator | - |
| 34 | `clear_dialog_callback_journal_received` | `PyDialog` (static) | `() -> None` | action/mutator | - |
| 35 | `clear_dialog_callback_journal_sent` | `PyDialog` (static) | `() -> None` | action/mutator | - |
| 36 | `clear_dialog_callback_journal_filtered` | `PyDialog` (static) | `(npc_uid: Optional[str] = None, incoming: Optional[bool] = None, message_id: Optional[int] = None, event_type: Optional[str] = None) -> None` | action/mutator (filtered) | - |
| 37 | `clear_cache` | `PyDialog` (static) | `() -> None` | action/mutator | - |
| 38 | `initialize` | `PyDialog` (static) | `() -> bool` | action/mutator (lifecycle) | - |
| 39 | `terminate` | `PyDialog` (static) | `() -> None` | action/mutator (lifecycle → Shutdown) | - |

### Struct return types & fields
All six structs are bound directly on `GW::dialog::*` structs (header `include\GW\dialog\dialog.h`), all fields `def_readwrite`.

| Struct/Class | Member | Type | Binding kind |
|---|---|---|---|
| DialogInfo | dialog_id | int (uint32) | def_readwrite |
| DialogInfo | flags | int (uint32) | def_readwrite |
| DialogInfo | frame_type | int (uint32) | def_readwrite |
| DialogInfo | event_handler | int (uint32) | def_readwrite |
| DialogInfo | content_id | int (uint32) | def_readwrite |
| DialogInfo | property_id | int (uint32) | def_readwrite |
| DialogInfo | content | str (from std::wstring) | def_readwrite |
| DialogInfo | agent_id | int (uint32) | def_readwrite |
| ActiveDialogInfo | dialog_id | int (uint32) | def_readwrite |
| ActiveDialogInfo | context_dialog_id | int (uint32) | def_readwrite |
| ActiveDialogInfo | agent_id | int (uint32) | def_readwrite |
| ActiveDialogInfo | dialog_id_authoritative | bool | def_readwrite |
| ActiveDialogInfo | message | str (from std::wstring) | def_readwrite |
| DialogButtonInfo | dialog_id | int (uint32) | def_readwrite |
| DialogButtonInfo | button_icon | int (uint32) | def_readwrite |
| DialogButtonInfo | message | str | def_readwrite |
| DialogButtonInfo | message_decoded | str | def_readwrite |
| DialogButtonInfo | message_decode_pending | bool | def_readwrite |
| DialogTextDecodedInfo | dialog_id | int (uint32) | def_readwrite |
| DialogTextDecodedInfo | text | str | def_readwrite |
| DialogTextDecodedInfo | pending | bool | def_readwrite |
| DialogEventLog | tick | int (uint64) | def_readwrite |
| DialogEventLog | message_id | int (uint32) | def_readwrite |
| DialogEventLog | incoming | bool | def_readwrite |
| DialogEventLog | is_frame_message | bool | def_readwrite |
| DialogEventLog | frame_id | int (uint32) | def_readwrite |
| DialogEventLog | w_bytes | List[int] (vector<uint8_t>) | def_readwrite |
| DialogEventLog | l_bytes | List[int] (vector<uint8_t>) | def_readwrite |
| DialogCallbackJournalEntry | tick | int (uint64) | def_readwrite |
| DialogCallbackJournalEntry | message_id | int (uint32) | def_readwrite |
| DialogCallbackJournalEntry | incoming | bool | def_readwrite |
| DialogCallbackJournalEntry | dialog_id | int (uint32) | def_readwrite |
| DialogCallbackJournalEntry | context_dialog_id | int (uint32) | def_readwrite |
| DialogCallbackJournalEntry | agent_id | int (uint32) | def_readwrite |
| DialogCallbackJournalEntry | map_id | int (uint32) | def_readwrite |
| DialogCallbackJournalEntry | model_id | int (uint32) | def_readwrite |
| DialogCallbackJournalEntry | dialog_id_authoritative | bool | def_readwrite |
| DialogCallbackJournalEntry | context_dialog_id_inferred | bool | def_readwrite |
| DialogCallbackJournalEntry | npc_uid | str | def_readwrite |
| DialogCallbackJournalEntry | event_type | str | def_readwrite |
| DialogCallbackJournalEntry | text | str | def_readwrite |

### Stub vs Native disagreements
- **native-only static methods** (present in native, absent from `PyDialog.pyi`): the five catalog reader methods `read_dialog_flags`, `read_dialog_frame_type`, `read_dialog_event_handler`, `read_dialog_content_id`, `read_dialog_property_id`. The stub jumps from `get_dialog_text_decode_status` straight to `get_dialog_event_logs`.
- **return-type drift**: stub types `initialize() -> None`; native binds `&GW::dialog::Initialize` which returns `bool`. `terminate` maps to `Shutdown` (void) — in sync.
- **PyDialogCatalog.pyi comparison**: `PyDialogCatalog` is a RETIRED separate module; its 7 methods (`is_dialog_available`, `get_dialog_info`, `enumerate_available_dialogs`, `get_dialog_text_decoded`, `is_dialog_text_decode_pending`, `get_dialog_text_decode_status`, `clear_cache`) all have equivalents merged into `PyDialog`. Note the catalog stub types `get_dialog_info -> dict[str, Any]` and `get_dialog_text_decode_status -> List[dict[str,Any]]`, whereas merged `PyDialog` returns the strongly-typed `DialogInfo` / `List[DialogTextDecodedInfo]`. No native module named `PyDialogCatalog` is registered in this cpp (the `PyDialogCatalog.pyi` is orphaned/legacy).
- Otherwise the ~30 shared `PyDialog` static methods and all six struct field sets are in sync with the stub.


---


# R2 Batch 5 — Py* Binding Method Inventory

Modules: PyMap, PyCamera, PyPathing, PyPing, PyPacketSniffer, PyNameObfuscator

---

## PyMap
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\map\map_bindings.cpp
- Stub: NONE
- Module shape: module-level free functions only (no py::class_ registered)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | travel | free fn | `travel(map_id: int, region: int = -2, district_number: int = 0, language: int = 0) -> <GW::map::Travel ret>` | other-args(map_id, region, district_number, language) | - |
| 2 | travel_to_district | free fn | `travel_to_district(map_id: int, district: int = 0, district_number: int = 0) -> <GW::map::Travel ret>` | other-args(map_id, district, district_number) | - |
| 3 | map_test_start | free fn | `map_test_start(map_id: int, alt_map_id: int, number: int = 2, count: int = 3, delay_ms: int = 0, timeout_ms: int = 10000, message_id: int = 0x10000098) -> None` | action/mutator (void) | - |
| 4 | map_test_stop | free fn | `map_test_stop() -> None` | action/mutator (void) | - |
| 5 | map_test_get_status | free fn | `map_test_get_status() -> str` | NO-ARG getter | - |
| 6 | map_test_is_active | free fn | `map_test_is_active() -> bool` | NO-ARG getter | - |
| 7 | map_test_get_count | free fn | `map_test_get_count() -> int` | NO-ARG getter | - |
| 8 | enter_challenge | free fn | `enter_challenge() -> bool` | action/mutator (bool) | - |
| 9 | cancel_enter_challenge | free fn | `cancel_enter_challenge() -> bool` | action/mutator (bool) | - |
| 10 | query_altitude | free fn | `query_altitude(x: float, y: float, radius: float = 100.0) -> tuple(result:int, altitude:float, nx:float, ny:float, nz:float)` | other-args(x, y, radius) | - (tuple) |
| 11 | get_is_map_loaded | free fn | `get_is_map_loaded() -> bool` | NO-ARG getter | - |
| 12 | get_map_id | free fn | `get_map_id() -> int` | NO-ARG getter | - |
| 13 | get_is_map_unlocked | free fn | `get_is_map_unlocked(map_id: int) -> bool` | other-args(map_id) | - |
| 14 | get_region | free fn | `get_region() -> int` | NO-ARG getter | - |
| 15 | get_language | free fn | `get_language() -> int` | NO-ARG getter | - |
| 16 | get_is_observing | free fn | `get_is_observing() -> bool` | NO-ARG getter | - |
| 17 | get_district | free fn | `get_district() -> int` | NO-ARG getter | - |
| 18 | get_instance_time | free fn | `get_instance_time() -> int` | NO-ARG getter | - |
| 19 | get_instance_type | free fn | `get_instance_type() -> int` | NO-ARG getter | - |
| 20 | get_foes_killed | free fn | `get_foes_killed() -> int` | NO-ARG getter | - |
| 21 | get_foes_to_kill | free fn | `get_foes_to_kill() -> int` | NO-ARG getter | - |
| 22 | get_is_in_cinematic | free fn | `get_is_in_cinematic() -> bool` | NO-ARG getter | - |
| 23 | skip_cinematic | free fn | `skip_cinematic() -> bool` | action/mutator (bool) | - |
| 24 | region_from_district | free fn | `region_from_district(district: int) -> int` | other-args(district) | - |
| 25 | language_from_district | free fn | `language_from_district(district: int) -> int` | other-args(district) | - |
| 26 | RayCast | free fn | `RayCast(start: list[float,3], unit_dir: list[float,3]) -> tuple(has_hit:bool, hit_x:float, hit_y:float, hit_z:float, prop_layer:int)` | other-args(start, unit_dir) | - (tuple) |
| 27 | RayCastTerrain | free fn | `RayCastTerrain(start: list[float,3], end: list[float,3]) -> tuple(has_hit:bool, frac:float)` | other-args(start, end) | - (tuple) |
| 28 | RayCastInteractive | free fn | `RayCastInteractive(start: list[float,3], unit_dir: list[float,3], max_range: float) -> tuple(has_hit:bool, dist:float, prop_id:int, n_scanned:int)` | other-args(start, unit_dir, max_range) | - (tuple) |
| 29 | GetProps | free fn | `GetProps() -> list[tuple(prop_id:int, x:float, y:float, z:float, is_interactive:bool, rec_count:int)]` | NO-ARG getter | - (list of tuples) |
| 30 | GetPropGeometry | free fn | `GetPropGeometry(prop_id: int) -> list[tuple(matrix12:tuple[12 floats], tris_local:list[tuple[9 floats]])]` | other-args(prop_id) | - (list of tuples) |

### Struct return types & fields
No `py::class_` registered. All aggregate returns are `py::tuple` / `py::list` (built ad-hoc in the lambdas); there are no bound struct types to enumerate.

### Stub vs Native disagreements
- No stub exists (`stubs/PyMap.pyi` not present). Native-only entirely — 30 free functions, all undocumented at stub level.

---

## PyCamera
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\camera\camera_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyCamera.pyi
- Module shape: mix — two bound classes (`Point3D`, `PyCamera`) + module-level free functions

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | __init__ | Point3D.__init__ | `Point3D() -> None` (native init<>; stub adds x/y/z defaults) | action/mutator (ctor) | - |
| 2 | __init__ | PyCamera.__init__ | `PyCamera() -> None` (ctor calls GetContext) | action/mutator (ctor) | - |
| 3 | GetContext | PyCamera.GetContext | `GetContext() -> None` (refreshes fields from live camera context) | action/mutator (refresh, void) | - |
| 4 | SetYaw | PyCamera.SetYaw | `SetYaw(_yaw: float) -> None` | action/mutator (queues via game_thread) | - |
| 5 | SetPitch | PyCamera.SetPitch | `SetPitch(_pitch: float) -> None` | action/mutator (queues) | - |
| 6 | SetMaxDist | PyCamera.SetMaxDist | `SetMaxDist(dist: float) -> None` | action/mutator (queues) | - |
| 7 | SetFieldOfView | PyCamera.SetFieldOfView | `SetFieldOfView(fov: float) -> None` | action/mutator (queues) | - |
| 8 | UnlockCam | PyCamera.UnlockCam | `UnlockCam(unlock: bool) -> None` | action/mutator (queues) | - |
| 9 | GetCameraUnlock | PyCamera.GetCameraUnlock | `GetCameraUnlock() -> bool` | NO-ARG getter | - |
| 10 | ForwardMovement | PyCamera.ForwardMovement | `ForwardMovement(amount: float, true_forward: bool) -> None` | action/mutator (queues) | - |
| 11 | VerticalMovement | PyCamera.VerticalMovement | `VerticalMovement(amount: float) -> None` | action/mutator (queues) | - |
| 12 | SideMovement | PyCamera.SideMovement | `SideMovement(amount: float) -> None` | action/mutator (queues) | - |
| 13 | RotateMovement | PyCamera.RotateMovement | `RotateMovement(angle: float) -> None` | action/mutator (queues) | - |
| 14 | ComputeCameraPos | PyCamera.ComputeCameraPos | `ComputeCameraPos() -> tuple(x:float, y:float, z:float)` (stub says `-> Point3D`) | NO-ARG getter | - (tuple; stub claims Point3D) |
| 15 | UpdateCameraPos | PyCamera.UpdateCameraPos | `UpdateCameraPos() -> None` | action/mutator (queues) | - |
| 16 | SetCameraPos | PyCamera.SetCameraPos | `SetCameraPos(x: float, y: float, z: float) -> None` | action/mutator (queues) | - |
| 17 | SetLookAtTarget | PyCamera.SetLookAtTarget | `SetLookAtTarget(x: float, y: float, z: float) -> None` | action/mutator (queues) | - |
| 18 | SetFog | PyCamera.SetFog | `SetFog(fog: bool) -> None` | action/mutator (queues) | - |
| 19 | forward_movement | free fn | `forward_movement(amount: float, true_forward: bool = False) -> None` | action/mutator (direct, void) | - |
| 20 | vertical_movement | free fn | `vertical_movement(amount: float) -> None` | action/mutator (void) | - |
| 21 | rotate_movement | free fn | `rotate_movement(angle: float) -> None` | action/mutator (void) | - |
| 22 | side_movement | free fn | `side_movement(amount: float) -> None` | action/mutator (void) | - |
| 23 | set_max_dist | free fn | `set_max_dist(dist: float = 900.0) -> None` | action/mutator (void) | - |
| 24 | set_field_of_view | free fn | `set_field_of_view(fov: float) -> None` | action/mutator (void) | - |
| 25 | compute_cam_pos | free fn | `compute_cam_pos(dist: float = 0.0) -> tuple(x:float, y:float, z:float)` | other-args(dist) | - (tuple) |
| 26 | update_camera_pos | free fn | `update_camera_pos() -> None` | action/mutator (void) | - |
| 27 | get_field_of_view | free fn | `get_field_of_view() -> float` | NO-ARG getter | - |
| 28 | get_yaw | free fn | `get_yaw() -> float` | NO-ARG getter | - |
| 29 | unlock_cam | free fn | `unlock_cam(flag: bool) -> None` | action/mutator (void) | - |
| 30 | get_camera_unlock | free fn | `get_camera_unlock() -> bool` | NO-ARG getter | - |
| 31 | set_fog | free fn | `set_fog(flag: bool) -> None` | action/mutator (void) | - |
| 32 | get_context_ptr | free fn | `get_context_ptr() -> int` (uintptr of camera context) | NO-ARG getter | - |

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| Point3D (native `PyCamera::Vec3`) | x | float | def_readwrite |
| Point3D | y | float | def_readwrite |
| Point3D | z | float | def_readwrite |
| Point3D | __init__ | ctor | def (py::init<>) |
| PyCamera | look_at_agent_id | int (uint32_t) | def_readwrite |
| PyCamera | yaw | float | def_readwrite |
| PyCamera | pitch | float | def_readwrite |
| PyCamera | camera_zoom | float | def_readwrite |
| PyCamera | max_distance | float | def_readwrite |
| PyCamera | yaw_right_click | float | def_readwrite |
| PyCamera | yaw_right_click2 | float | def_readwrite |
| PyCamera | pitch_right_click | float | def_readwrite |
| PyCamera | distance2 | float | def_readwrite |
| PyCamera | acceleration_constant | float | def_readwrite |
| PyCamera | time_since_last_keyboard_rotation | float | def_readwrite |
| PyCamera | time_since_last_mouse_rotation | float | def_readwrite |
| PyCamera | time_since_last_mouse_move | float | def_readwrite |
| PyCamera | time_since_last_agent_selection | float | def_readwrite |
| PyCamera | time_in_the_map | float | def_readwrite |
| PyCamera | time_in_the_district | float | def_readwrite |
| PyCamera | yaw_to_go | float | def_readwrite |
| PyCamera | pitch_to_go | float | def_readwrite |
| PyCamera | dist_to_go | float | def_readwrite |
| PyCamera | max_distance2 | float | def_readwrite |
| PyCamera | field_of_view | float | def_readwrite |
| PyCamera | field_of_view2 | float | def_readwrite |
| PyCamera | h0024 | list[int] (vector<uint32_t>, size 4) | def_readwrite |
| PyCamera | h0070 | list[float] (vector<float>, size 2) | def_readwrite |
| PyCamera | position | Point3D | def_readwrite |
| PyCamera | camera_pos_to_go | Point3D | def_readwrite |
| PyCamera | cam_pos_inverted | Point3D | def_readwrite |
| PyCamera | cam_pos_inverted_to_go | Point3D | def_readwrite |
| PyCamera | look_at_target | Point3D | def_readwrite |
| PyCamera | look_at_to_go | Point3D | def_readwrite |

Note: native struct also has private/non-bound fields (`h0004`, `h0008`, `h000C`, `h0014`, `current_yaw`) that are NOT exposed via def_readwrite. `current_yaw` is populated in GetContext but not bound.

### Stub vs Native disagreements
- **Signature drift**: `ComputeCameraPos` — native returns a `py::tuple(x,y,z)`; stub declares `-> Point3D`. Same for the free fn `compute_cam_pos` which native returns as tuple; stub declares `-> Tuple[float, float, float]` (correct for the free fn).
- **Stub-only convenience**: `Point3D.__init__(x, y, z)` has defaulted args in the stub, but native binds only `py::init<>()` (no-arg). Calling `Point3D(1,2,3)` at runtime would fail despite the stub.
- **Native-only (missing from stub)**: none among free functions — all 14 free fns present. All class members present in stub EXCEPT `max_distance2`, `yaw_to_go`, `pitch_to_go`, `dist_to_go`, and the movement/time fields `time_since_last_agent_selection`, `time_in_the_map`, `time_in_the_district`, `time_since_last_keyboard_rotation`, `time_since_last_mouse_rotation`, `time_since_last_mouse_move` — these are def_readwrite in native but ABSENT from the stub's attribute list.
- Otherwise class methods align 1:1.

---

## PyPathing
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\pathing\pathing_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyPathing.pyi
- Module shape: mix — one enum (`PathStatus`) + one bound class (`PathPlanner`)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | __init__ | PathPlanner.__init__ | `PathPlanner() -> None` | action/mutator (ctor) | - |
| 2 | plan | PathPlanner.plan | `plan(start_x: float, start_y: float, start_z: float, goal_x: float, goal_y: float, goal_z: float) -> None` | other-args(start/goal xyz); queues to game thread | - |
| 3 | compute_immediate | PathPlanner.compute_immediate | `compute_immediate(start_x, start_y, start_z, goal_x, goal_y, goal_z) -> list[tuple(float,float,float)]` | other-args(start/goal xyz) | - (list of tuples) |
| 4 | get_status | PathPlanner.get_status | `get_status() -> PathStatus` | NO-ARG getter | - (enum PathStatus) |
| 5 | is_ready | PathPlanner.is_ready | `is_ready() -> bool` | NO-ARG getter | - |
| 6 | was_successful | PathPlanner.was_successful | `was_successful() -> bool` | NO-ARG getter | - |
| 7 | get_path | PathPlanner.get_path | `get_path() -> list[tuple(float,float,float)]` (return_value_policy::reference) | NO-ARG getter | - (list of tuples) |
| 8 | reset | PathPlanner.reset | `reset() -> None` | action/mutator (void) | - |

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| PathStatus (enum) | Idle | 0 | enum value |
| PathStatus | Pending | 1 | enum value |
| PathStatus | Ready | 2 | enum value |
| PathStatus | Failed | 3 | enum value |
| PathPlanner | (no data members bound) | - | class with 8 defs only |

`get_path` / `compute_immediate` return `std::vector<std::tuple<float,float,float>>` — auto-converted to Python `list[tuple]` via `pybind11/stl.h`; no bound struct.

### Stub vs Native disagreements
- Identical surface. All 8 methods + enum present in both. `PathStatus` bound as `py::enum_` (native) matching stub `class PathStatus(Enum)`. No drift.

---

## PyPing
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\ping\ping_bindings.cpp
- Stub: NONE
- Module shape: single bound class `PingHandler` (native type `GW::ping::PingTracker`)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | __init__ | PingHandler.__init__ | `PingHandler() -> None` (PingTracker ctor; default history_size=10; registers PING_REPLY callback) | action/mutator (ctor) | - |
| 2 | Terminate | PingHandler.Terminate | `Terminate() -> None` | action/mutator (void) | - |
| 3 | GetCurrentPing | PingHandler.GetCurrentPing | `GetCurrentPing() -> int` (uint32_t) | NO-ARG getter | - |
| 4 | GetAveragePing | PingHandler.GetAveragePing | `GetAveragePing() -> int` | NO-ARG getter | - |
| 5 | GetMinPing | PingHandler.GetMinPing | `GetMinPing() -> int` | NO-ARG getter | - |
| 6 | GetMaxPing | PingHandler.GetMaxPing | `GetMaxPing() -> int` | NO-ARG getter | - |

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| PingHandler (GW::ping::PingTracker) | (no data members bound) | - | class; 5 methods + ctor |

All private data (`ping_history_`, `ping_index_`, `history_size_`, `ping_count_`, `is_initialized_`, `ping_callback_`) is unbound. `Initialize()` (public in header) is NOT bound — only `Terminate` and the 4 getters. Return values are plain `uint32_t`; no bound struct returned.

### Stub vs Native disagreements
- No stub exists (`stubs/PyPing.pyi` not present). Native-only. Note the native class `PingTracker` is exposed under the Python name `PingHandler`. The header-public `Initialize()` is intentionally not bound.

---

## PyPacketSniffer
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\packet_sniffer\packet_sniffer_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyPacketSniffer.pyi
- Module shape: mix — one enum (`PacketDirection`) + two bound classes (`PacketLogEntry`, `PacketSniffer` [facade])

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | __init__ | PacketLogEntry.__init__ | `PacketLogEntry() -> None` | action/mutator (ctor) | - |
| 2 | __repr__ | PacketLogEntry.__repr__ | `__repr__() -> str` | NO-ARG getter (dunder) | - |
| 3 | instance | PacketSniffer.instance | `instance() -> PacketSniffer` (static, return_value_policy::reference) | NO-ARG getter (static) | PacketSniffer |
| 4 | initialize | PacketSniffer.initialize | `initialize() -> bool` | action/mutator (bool) | - |
| 5 | initialize_stoc | PacketSniffer.initialize_stoc | `initialize_stoc() -> bool` | action/mutator (bool) | - |
| 6 | initialize_ctos | PacketSniffer.initialize_ctos | `initialize_ctos() -> bool` | action/mutator (bool) | - |
| 7 | terminate | PacketSniffer.terminate | `terminate() -> None` | action/mutator (void) | - |
| 8 | terminate_stoc | PacketSniffer.terminate_stoc | `terminate_stoc() -> None` | action/mutator (void) | - |
| 9 | terminate_ctos | PacketSniffer.terminate_ctos | `terminate_ctos() -> None` | action/mutator (void) | - |
| 10 | get_logs | PacketSniffer.get_logs | `get_logs() -> list[PacketLogEntry]` | NO-ARG getter | PacketLogEntry (list) |
| 11 | get_stoc_logs | PacketSniffer.get_stoc_logs | `get_stoc_logs() -> list[PacketLogEntry]` | NO-ARG getter | PacketLogEntry (list) |
| 12 | get_ctos_logs | PacketSniffer.get_ctos_logs | `get_ctos_logs() -> list[PacketLogEntry]` | NO-ARG getter | PacketLogEntry (list) |
| 13 | clear_logs | PacketSniffer.clear_logs | `clear_logs() -> None` | action/mutator (void) | - |
| 14 | clear_stoc_logs | PacketSniffer.clear_stoc_logs | `clear_stoc_logs() -> None` | action/mutator (void) | - |
| 15 | clear_ctos_logs | PacketSniffer.clear_ctos_logs | `clear_ctos_logs() -> None` | action/mutator (void) | - |

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| PacketDirection (enum) | StoC | 0 | enum value |
| PacketDirection | CToS | 1 | enum value |
| PacketLogEntry | tick | int (uint64_t) | def_readonly |
| PacketLogEntry | direction | PacketDirection | def_readonly |
| PacketLogEntry | header | int (uint32_t) | def_readonly |
| PacketLogEntry | size | int (uint32_t) | def_readonly |
| PacketLogEntry | data | list[int] (vector<uint8_t>) | def_readonly |
| PacketLogEntry | __repr__ | method | def |
| PacketSniffer (facade) | instance | static method | def_static |
| PacketSniffer | (no data members) | - | 12 methods |

### Stub vs Native disagreements
- **Stub-only / missing enum member typing**: stub declares `PacketDirection` as a plain class with class-attrs (`StoC`/`CToS`) rather than an `Enum`; native binds it as `py::enum_` with `export_values()`. Functionally close; the stub loses enum semantics and doesn't expose the values as module-level names (native `export_values()` also injects `StoC`/`CToS` at module scope — not reflected in stub).
- **Native-only**: `PacketLogEntry.__repr__` is bound in native but not declared in stub (expected — dunder).
- Otherwise `PacketSniffer` methods and `PacketLogEntry` fields align 1:1.

---

## PyNameObfuscator
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\name_obfuscator\name_obfuscator_bindings.cpp
- Stub: NONE
- Module shape: mix — one bound class (`ObservedPlayer`, read-only data) + module-level free functions (all forwarding to `NameObfuscator::Instance()`)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | enable | free fn | `enable() -> None` | action/mutator (void) | - |
| 2 | disable | free fn | `disable() -> None` | action/mutator (void) | - |
| 3 | is_enabled | free fn | `is_enabled() -> bool` | NO-ARG getter | - |
| 4 | is_map_ready | free fn | `is_map_ready() -> bool` | NO-ARG getter | - |
| 5 | set_alias | free fn | `set_alias(real_name: str, fake_name: str) -> None` | other-args(real_name, fake_name) | - |
| 6 | remove_alias | free fn | `remove_alias(real_name: str) -> bool` | other-args(real_name) | - |
| 7 | clear_aliases | free fn | `clear_aliases() -> None` | action/mutator (void) | - |
| 8 | clear | free fn | `clear() -> None` (alias of clear_aliases) | action/mutator (void) | - |
| 9 | alias_count | free fn | `alias_count() -> int` (uint32_t) | NO-ARG getter | - |
| 10 | get_aliases | free fn | `get_aliases() -> dict[str, str]` (map<wstring,wstring>) | NO-ARG getter | - (dict) |
| 11 | get_real_name | free fn | `get_real_name(display_name: str) -> str` | other-args(display_name) | - |
| 12 | get_display_name | free fn | `get_display_name(real_name: str) -> str` | other-args(real_name) | - |
| 13 | require_real_name | free fn | `require_real_name(name: str) -> str` | other-args(name) | - |
| 14 | set_surface_enabled | free fn | `set_surface_enabled(surface: str, enabled: bool) -> bool` | other-args(surface, enabled) | - |
| 15 | is_surface_enabled | free fn | `is_surface_enabled(surface: str) -> bool` | other-args(surface) | - |
| 16 | list_surfaces | free fn | `list_surfaces() -> list[str]` | NO-ARG getter | - (list) |
| 17 | scrub_guild_roster | free fn | `scrub_guild_roster() -> int` | action/mutator (returns count) | - |
| 18 | scrub_guild_identity | free fn | `scrub_guild_identity() -> int` | action/mutator (returns guilds changed) | - |
| 19 | clear_observed_cache | free fn | `clear_observed_cache() -> None` | action/mutator (void) | - |
| 20 | observed_count | free fn | `observed_count() -> int` (uint32_t) | NO-ARG getter | - |
| 21 | get_observed_players | free fn | `get_observed_players() -> list[ObservedPlayer]` | NO-ARG getter | ObservedPlayer (list) |
| 22 | get_diagnostics | free fn | `get_diagnostics() -> dict[str, int/bool]` | NO-ARG getter | - (dict, keys below) |
| 23 | reset_diagnostics | free fn | `reset_diagnostics() -> None` | action/mutator (void) | - |

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| ObservedPlayer | player_number | int (uint32_t) | def_readonly |
| ObservedPlayer | agent_id | int (uint32_t) | def_readonly |
| ObservedPlayer | real_name | str (wstring) | def_readonly |
| ObservedPlayer | display_name | str (wstring) | def_readonly |
| ObservedPlayer | aliased | bool | def_readonly |

`get_diagnostics()` returns an ad-hoc `py::dict` (NOT a bound struct) with keys: `initialized`, `player_join_hook_registered`, `class_observer_hook_registered`, `enabled`, `current_map_ready`, `player_packets_seen`, `player_packets_empty_name`, `player_packets_disabled`, `player_packets_map_not_ready`, `observed_captures`, `observed_trylock_skips`, `alias_hits`, `class_observer_hits`, `message_global_hits`, `item_custom_hits`, `mercenary_hits`, `mercenary_self_skips`, `guild_info_hits`, `party_search_hits`, `acct_name_hits`, `acct_name_self_skips`, `score_summary_hits`, `score_summary_mode_skips`, `score_summary_self_skips`, `guild_charname_hits`, `guild_identity_hits`, `guild_invite_hits`, `guild_motd_hits`, `own_name_hits`, `reverse_alias_collisions`. (30 keys; bools for the first 5, uint32 for the rest.)

`get_aliases()` returns `std::map<wstring,wstring>` → Python `dict[str,str]` (stl.h auto-convert).

### Stub vs Native disagreements
- No stub exists (`stubs/PyNameObfuscator.pyi` not present). Native-only — 23 free functions + `ObservedPlayer` read-only class. Note `clear` is a bound duplicate alias of `clear_aliases`. Native `NameObfuscator` C++ class methods (LookupReverse, ScrubGuildRoster body, packet handlers, etc.) are NOT directly bound — only the free-function facade above is exposed.


---


# R2_b6 — Py* Binding Method Inventory (batch 6)

Modules: PySystem, PySettings, PyProfiler, PyCallback, PyListeners, PyGameThread, PyScanner.

---

## PySystem
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\system\system_bindings.cpp`
- Helper impl: `C:\Users\Apo\Py4GW_Reforged_Native\src\system\system_methods.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PySystem.pyi`
- Module shape: mix — module-level free functions + one bound class (`ConsoleMessage`) + one enum (`MessageType`) + five nested submodules (`Console`, `environment`, `window`, `script_control`, `widget_manager`).

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | get_tick_count64 | free fn | `() -> int` | NO-ARG getter | - |
| 2 | get_shared_memory_name | free fn | `() -> str` (std::wstring) | NO-ARG getter | - |
| 3 | get_credits | free fn | `() -> str` | NO-ARG getter | - |
| 4 | get_license | free fn | `() -> str` | NO-ARG getter | - |
| 5 | change_working_directory | free fn | `(path: str) -> bool` | other-args(path) | - |
| 6 | request_shutdown_prompt | free fn | `() -> None` | action/mutator (void) | - |
| 7 | cancel_shutdown_prompt | free fn | `() -> None` | action/mutator (void) | - |
| 8 | is_shutdown_prompt_pending | free fn | `() -> bool` | NO-ARG getter | - |
| 9 | in_character_select_screen | free fn | `() -> bool` | NO-ARG getter | - |
| 10 | has_account_email | free fn | `() -> bool` | NO-ARG getter | - |
| 11 | get_account_email | free fn | `() -> str` | NO-ARG getter | - |
| 12 | get_settings_directory | free fn | `() -> str` | NO-ARG getter | - |
| 13 | Log | Console.Log | `(sender: str, message: str, message_type: MessageType = Info) -> None` | action/mutator (void) | - |
| 14 | get_projects_path | Console.get_projects_path | `() -> str` | NO-ARG getter | - |
| 15 | get_gw_window_handle | Console.get_gw_window_handle | `() -> int` (uintptr_t) | NO-ARG getter | - |
| 16 | write | Console.write | `(module_name: str, message: str, level: str = "INFO") -> None` | action/mutator (void) | - |
| 17 | write | Console.write | `(module_name: str, message: str, message_type: MessageType) -> None` (overload) | action/mutator (void) | - |
| 18 | get_messages | Console.get_messages | `() -> List[ConsoleMessage]` | NO-ARG getter | ConsoleMessage |
| 19 | get_messages | Console.get_messages | `(message_type: MessageType) -> List[ConsoleMessage]` (overload) | other-args(message_type) | ConsoleMessage |
| 20 | filter_messages | Console.filter_messages | `(module_name: str="", level: str="", contains: str="") -> List[ConsoleMessage]` | other-args(module_name,level,contains) | ConsoleMessage |
| 21 | clear_messages | Console.clear_messages | `() -> None` | action/mutator (void) | - |
| 22 | set_output_to_file | Console.set_output_to_file | `(enabled: bool) -> None` | action/mutator (void) | - |
| 23 | get_output_to_file | Console.get_output_to_file | `() -> bool` | NO-ARG getter | - |
| 24 | set_draw_console | Console.set_draw_console | `(enabled: bool) -> None` | action/mutator (void) | - |
| 25 | get_draw_console | Console.get_draw_console | `() -> bool` | NO-ARG getter | - |
| 26 | set_draw_compact_console | Console.set_draw_compact_console | `(enabled: bool) -> None` | action/mutator (void) | - |
| 27 | get_draw_compact_console | Console.get_draw_compact_console | `() -> bool` | NO-ARG getter | - |
| 28 | toggle_console | Console.toggle_console | `() -> None` | action/mutator (void) | - |
| 29 | toggle_compact_console | Console.toggle_compact_console | `() -> None` | action/mutator (void) | - |
| 30 | get_gw_window_handle | environment.get_gw_window_handle | `() -> int` | NO-ARG getter | - |
| 31 | get_projects_path | environment.get_projects_path | `() -> str` | NO-ARG getter | - |
| 32 | resize_window | window.resize_window | `(width: int, height: int) -> None` | other-args(width,height) | - |
| 33 | move_window_to | window.move_window_to | `(x: int, y: int) -> None` | other-args(x,y) | - |
| 34 | set_window_geometry | window.set_window_geometry | `(x, y, width, height: int) -> None` | other-args(x,y,width,height) | - |
| 35 | get_window_rect | window.get_window_rect | `() -> Tuple[int,int,int,int]` | NO-ARG getter | - |
| 36 | get_client_rect | window.get_client_rect | `() -> Tuple[int,int,int,int]` | NO-ARG getter | - |
| 37 | set_window_active | window.set_window_active | `() -> None` | action/mutator (void) | - |
| 38 | set_window_title | window.set_window_title | `(title: str) -> None` (std::wstring) | action/mutator (void) | - |
| 39 | is_window_active | window.is_window_active | `() -> bool` | NO-ARG getter | - |
| 40 | is_window_minimized | window.is_window_minimized | `() -> bool` | NO-ARG getter | - |
| 41 | is_window_in_background | window.is_window_in_background | `() -> bool` | NO-ARG getter | - |
| 42 | set_borderless | window.set_borderless | `(enable: bool) -> None` | action/mutator (void) | - |
| 43 | set_always_on_top | window.set_always_on_top | `(enable: bool) -> None` | action/mutator (void) | - |
| 44 | flash_window | window.flash_window | `(repeat_count: int = 1) -> None` | action/mutator (void) | - |
| 45 | request_attention | window.request_attention | `() -> None` | action/mutator (void) | - |
| 46 | get_z_order | window.get_z_order | `() -> int` | NO-ARG getter | - |
| 47 | set_z_order | window.set_z_order | `(insert_after: int = 0) -> None` | action/mutator (void) | - |
| 48 | send_window_to_back | window.send_window_to_back | `() -> None` | action/mutator (void) | - |
| 49 | bring_window_to_front | window.bring_window_to_front | `() -> None` | action/mutator (void) | - |
| 50 | transparent_click_through | window.transparent_click_through | `(enable: bool) -> None` | action/mutator (void) | - |
| 51 | adjust_window_opacity | window.adjust_window_opacity | `(alpha: int) -> None` | action/mutator (void) | - |
| 52 | hide_window | window.hide_window | `() -> None` | action/mutator (void) | - |
| 53 | show_window | window.show_window | `() -> None` (impl `ShowWindowAgain`) | action/mutator (void) | - |
| 54 | load | script_control.load | `(path: str) -> bool` | other-args(path) | - |
| 55 | run | script_control.run | `() -> bool` | action/mutator | - |
| 56 | stop | script_control.stop | `() -> None` | action/mutator (void) | - |
| 57 | pause | script_control.pause | `() -> None` | action/mutator (void) | - |
| 58 | resume | script_control.resume | `() -> None` | action/mutator (void) | - |
| 59 | status | script_control.status | `() -> str` | NO-ARG getter | - |
| 60 | defer_load_and_run | script_control.defer_load_and_run | `(path: str, delay_ms: int = 1000) -> None` | action/mutator (void) | - |
| 61 | defer_stop_load_and_run | script_control.defer_stop_load_and_run | `(path: str, delay_ms: int = 1000) -> None` | action/mutator (void) | - |
| 62 | defer_stop_and_run | script_control.defer_stop_and_run | `(delay_ms: int = 1000) -> None` | action/mutator (void) | - |
| 63 | start | widget_manager.start | `() -> None` | action/mutator (void) | - |
| 64 | stop | widget_manager.stop | `() -> None` | action/mutator (void) | - |
| 65 | status | widget_manager.status | `() -> str` | NO-ARG getter | - |

Note: `Console.MessageType` is an attribute alias to `PySystem.MessageType` (`console.attr("MessageType") = m.attr("MessageType")`), not a method.

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|---|---|---|---|
| ConsoleMessage | timestamp | str | def_readonly |
| ConsoleMessage | display_timestamp | str | def_readonly |
| ConsoleMessage | module_name | str | def_readonly |
| ConsoleMessage | level | str | def_readonly |
| ConsoleMessage | message_type | MessageType | def_readonly |
| ConsoleMessage | message | str | def_readonly |
| ConsoleMessage | __repr__ | `(self) -> str` | def method (lambda) |
| MessageType (enum) | Info / Warning / Error / Debug / Success / Performance / Notice / Hook | int | py::enum_ values |

### Stub vs Native disagreements
- Signature drift — `window.set_window_title`: native takes `std::wstring` and passes **no doc string** (only `py::arg("title")`); stub types it `title: str`. Functionally consistent.
- `Console.write` — native registers **two overloads** (level-string and MessageType); the stub collapses them into a single `write(module_name, message, level_or_type)`. Semantically equivalent.
- `Console.get_messages` — native has two overloads (no-arg + `message_type`); stub uses one signature with `Optional[MessageType] = None`. Equivalent surface.
- Otherwise stub and native are in agreement across all 65 entries, the `ConsoleMessage` class, and the `MessageType` enum.

---

## PySettings
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\settings\settings_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PySettings.pyi`
- Module shape: mix — one bound class `settings` (over `PY4GW::IniFile`, held via `unique_ptr<…, py::nodelete>`) plus 6 module-level free functions. Note: bound Python name is `settings`, not `PySettings`.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | __init__ | settings.__init__ | `(name: str, scope: str = "account") -> settings` | other-args(name,scope) | settings |
| 2 | write | settings.write | `(key: str, value: bool) -> None` (overload) | action/mutator (void) | - |
| 3 | write | settings.write | `(key: str, value: int) -> None` (`long long` overload) | action/mutator (void) | - |
| 4 | write | settings.write | `(key: str, value: float) -> None` (`double` overload) | action/mutator (void) | - |
| 5 | write | settings.write | `(key: str, value: str) -> None` (overload) | action/mutator (void) | - |
| 6 | read | settings.read | `(key: str, default: Any = "") -> Any` | other-args(key,default/type-token) | - |
| 7 | save | settings.save | `() -> bool` | action/mutator | - |
| 8 | reload | settings.reload | `() -> bool` | action/mutator | - |
| 9 | is_dirty | settings.is_dirty | `() -> bool` | NO-ARG getter | - |
| 10 | is_bound | settings.is_bound | `() -> bool` | NO-ARG getter | - |
| 11 | path | settings.path | `() -> str` | NO-ARG getter | - |
| 12 | has_key | settings.has_key | `(key: str) -> bool` | other-args(key) | - |
| 13 | keys | settings.keys | `(section: str = "settings") -> list[str]` | other-args(section) | - |
| 14 | sections | settings.sections | `() -> list[str]` | NO-ARG getter | - |
| 15 | delete | settings.delete | `(key: str) -> bool` | action/mutator | - |
| 16 | delete_section | settings.delete_section | `(section: str) -> bool` | action/mutator | - |
| 17 | set | settings.set | `(section: str, key: str, value: bool) -> None` (overload) | action/mutator (void) | - |
| 18 | set | settings.set | `(section: str, key: str, value: int) -> None` (`long long`) | action/mutator (void) | - |
| 19 | set | settings.set | `(section: str, key: str, value: float) -> None` (`double`) | action/mutator (void) | - |
| 20 | set | settings.set | `(section: str, key: str, value: str) -> None` (overload) | action/mutator (void) | - |
| 21 | get | settings.get | `(section: str, key: str, default: Any = "") -> Any` | other-args(section,key,default/token) | - |
| 22 | has | settings.has | `(section: str, key: str) -> bool` | other-args(section,key) | - |
| 23 | remove | settings.remove | `(section: str, key: str) -> bool` | action/mutator | - |
| 24 | items | settings.items | `(section: str) -> list[tuple[str,str]]` | other-args(section) | - |
| 25 | copy_document_to_account | free fn | `(name: str, target_email: str) -> bool` | other-args(name,target_email) | - |
| 26 | copy_section_to_account | free fn | `(name: str, section: str, target_email: str) -> bool` | other-args | - |
| 27 | copy_keys_to_account | free fn | `(name: str, section: str, keys: list[str], target_email: str) -> bool` | other-args | - |
| 28 | apply_section_to_account | free fn | `(name: str, section: str, values: list[tuple[str,str]], target_email: str) -> bool` | other-args | - |
| 29 | is_anchored | free fn | `() -> bool` | NO-ARG getter | - |
| 30 | get_settings_directory | free fn | `() -> str` | NO-ARG getter | - |

Notes: `write`/`read` split `"section/key"` on `/` (flat key → default section `"settings"`); `set`/`get`/`has`/`remove` take section and key as separate args and never parse a delimiter. `read`/`get` accept either a default value (type-inferred getter) or a Python type token (`bool`/`int`/`float`/`str`).

### Struct return types & fields
No `py::class_` with data fields; the only bound class `settings` (`PY4GW::IniFile`) exposes methods only (all `cls.def` methods/lambdas — no `def_readwrite`/`def_readonly`). `__init__` returns a raw pointer into `SettingsManager::Instance().Open(...)` (nodelete holder). No struct field tables applicable.

### Stub vs Native disagreements
- Fully consistent. Stub `settings.__init__`/`write`/`read`/`set`/`get`/`has`/`remove`/`items`/`keys`/`sections`/`delete`/`delete_section`/`save`/`reload`/`is_dirty`/`is_bound`/`path`/`has_key` all match the native overload set, and all 6 module-level free functions are present in both. Stub uses union `bool|int|float|str` where native uses discrete overloads — equivalent surface.

---

## PyProfiler
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\profiler\profiler_bindings.cpp`
- Stub: NONE
- Module shape: module-level free functions only (thin wrapper over static `PY4GW::Profiler`).

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | get_metric_names | free fn | `() -> list[str]` | NO-ARG getter | - |
| 2 | get_reports | free fn | `() -> list[tuple[str,float,float,float,float,float,float]]` (name,min,avg,p50,p95,p99,max) | NO-ARG getter | - |
| 3 | get_history | free fn | `(metric_name: str) -> list[float]` | other-args(metric_name) | - |
| 4 | reset | free fn | `() -> None` | action/mutator (void) | - |
| 5 | start | free fn | `(name: str) -> None` | action/mutator (void) | - |
| 6 | end | free fn | `(name: str) -> None` (lambda; internally stamps `System::GetTickCount64()`) | action/mutator (void) | - |

### Struct return types & fields
No `py::class_` registered. `get_reports` returns a list of plain 7-element tuples (not a bound struct); `MetricData`/`StartPoint` structs in `include\profiler\profiler.h` are C++-internal and not exposed to Python.

### Stub vs Native disagreements
- No stub file exists (`PyProfiler.pyi` absent). All 6 functions native-only by definition. Return shapes reconstructed from `include\profiler\profiler.h`: `CalculateReportAll()` → `vector<tuple<string,double×6>>`, `GetMetricNames()` → `vector<string>`, `GetMetricHistory()` → `vector<double>`.

---

## PyCallback
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\callback\callback_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PyCallback.pyi`
- Module shape: one bound class `PyCallback` (all `def_static`) + two exported enums (`Phase`, `Context`).

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | Register | PyCallback.Register | `(name: str, fn: Callable[[],Any], phase: Phase, priority: int = 99, context: Context = Context.Draw) -> int` | other-args(name,fn,phase,priority,context) | - |
| 2 | RemoveById | PyCallback.RemoveById | `(id: int) -> None` | subject-id (callback id) | - |
| 3 | RemoveByName | PyCallback.RemoveByName | `(name: str) -> None` | other-args(name) | - |
| 4 | PauseById | PyCallback.PauseById | `(id: int) -> None` | subject-id (callback id) | - |
| 5 | ResumeById | PyCallback.ResumeById | `(id: int) -> None` | subject-id (callback id) | - |
| 6 | IsPaused | PyCallback.IsPaused | `(id: int) -> bool` | subject-id (callback id) | - |
| 7 | IsRegistered | PyCallback.IsRegistered | `(id: int) -> bool` | subject-id (callback id) | - |
| 8 | Clear | PyCallback.Clear | `() -> None` | action/mutator (void) | - |
| 9 | GetCallbackInfo | PyCallback.GetCallbackInfo | `() -> list[tuple]` | NO-ARG getter | - |

### Struct return types & fields
No data-field `py::class_`. `PyCallback` is bound with `def_static` methods only. Enums:
| Struct/Class | Member | Type | Binding kind |
|---|---|---|---|
| Phase (enum) | PreUpdate / Data / Update | int | py::enum_ (export_values) |
| Context (enum) | Update / Draw / Main | int | py::enum_ (export_values) |

`GetCallbackInfo` returns `list[tuple]` (opaque tuple shape; not a bound struct).

### Stub vs Native disagreements
- Fully consistent. All 9 static methods, both enums and all enum members present in both stub and native with matching signatures and defaults (`priority=99`, `context=Context.Draw`).

---

## PyListeners
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\listeners\listeners_bindings.cpp`
- Stub: NONE (compared against `stubs\PyCombatEvents.pyi` — see disagreements)
- Module shape: module-level free functions only (runtime toggles for native game-event listeners).

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | list | free fn | `() -> list[str]` | NO-ARG getter | - |
| 2 | enable | free fn | `(name: str) -> bool` | other-args(name) | - |
| 3 | disable | free fn | `(name: str) -> bool` | other-args(name) | - |
| 4 | toggle | free fn | `(name: str) -> bool` | other-args(name) | - |
| 5 | set_enabled | free fn | `(name: str, enabled: bool) -> bool` | other-args(name,enabled) | - |
| 6 | is_enabled | free fn | `(name: str) -> bool` | other-args(name) | - |

(Return types from `include\listeners\listeners.h`: `GetListenerNames() -> vector<string>`; `Enable/Disable/Toggle/SetEnabled/IsEnabled -> bool`.)

### Struct return types & fields
No `py::class_` registered — this module binds only free toggle functions. No struct field tables applicable.

### Stub vs Native disagreements
- No `PyListeners.pyi` stub exists — all 6 functions native-only.
- **No overlap with `PyCombatEvents.pyi`.** That stub describes an entirely different surface (`EventType` constants, `PyRawCombatEvent`, `PyCombatEventQueue`, `GetCombatEventQueue()`) — a combat-event *queue* API, not the listener-toggle registry. None of those symbols appear in `listeners_bindings.cpp`, and none of PyListeners' 6 toggle functions appear in `PyCombatEvents.pyi`. The stub belongs to a different (packet/combat-event) binding module, not this one.

---

## PyGameThread
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\game_thread\game_thread_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PyGameThread.pyi`
- Module shape: module-level free functions only.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | clear_calls | free fn | `() -> None` | action/mutator (void) | - |
| 2 | is_in_game_thread | free fn | `() -> bool` | NO-ARG getter | - |
| 3 | enqueue | free fn | `(fn: Callable[[],Any]) -> None` | action/mutator (queues) | - |

Notes: `enqueue` is a no-op unless `MapReady()` (map loaded and instance type != Loading); the callable runs later on the GW game thread with the GIL acquired, wrapped in a shared_ptr whose deleter re-acquires the GIL for GIL-safe teardown; callback exceptions are logged to console (`PyGameThread` / `MessageType::Error`) rather than swallowed.

### Struct return types & fields
No `py::class_` registered. No struct field tables applicable.

### Stub vs Native disagreements
- Fully consistent. All 3 functions present in both with matching signatures. Stub documents the GIL/map-ready semantics that the native lambda implements.

---

## PyScanner
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\base\scanner_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PyScanner.pyi`
- Module shape: one bound class `PyScanner` (all `def_static`, wrapping the static `PY4GW::Scanner`). Section args are raw uint8 indices (0=.text, 1=.rdata, 2=.data).

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | Initialize | PyScanner.Initialize | `(module_name: str = "") -> None` | other-args(module_name) | - |
| 2 | Find | PyScanner.Find | `(pattern: bytes, mask: str, offset: int, section: int) -> int` | other-args(pattern,mask,offset,section) | - |
| 3 | FindInRange | PyScanner.FindInRange | `(pattern: bytes, mask: str, offset: int, start: int, end: int) -> int` | other-args | - |
| 4 | FunctionFromNearCall | PyScanner.FunctionFromNearCall | `(call_instruction_address: int, check_valid_ptr: bool = True) -> int` | other-args(call_addr,check_valid_ptr) | - |
| 5 | ToFunctionStart | PyScanner.ToFunctionStart | `(address: int, scan_range: int = 0xFF) -> int` | other-args(address,scan_range) | - |
| 6 | IsValidPtr | PyScanner.IsValidPtr | `(address: int, section: int) -> bool` | other-args(address,section) | - |
| 7 | FindUseOfAddress | PyScanner.FindUseOfAddress | `(address: int, offset: int, section: int) -> int` | other-args | - |
| 8 | FindNthUseOfAddress | PyScanner.FindNthUseOfAddress | `(address: int, nth: int, offset: int, section: int) -> int` | other-args | - |
| 9 | FindUseOfStringA | PyScanner.FindUseOfStringA | `(string: str, offset: int, section: int) -> int` | other-args | - |
| 10 | FindUseOfStringW | PyScanner.FindUseOfStringW | `(string: str, offset: int, section: int) -> int` (std::wstring) | other-args | - |
| 11 | FindNthUseOfStringA | PyScanner.FindNthUseOfStringA | `(string: str, nth: int, offset: int, section: int) -> int` | other-args | - |
| 12 | FindNthUseOfStringW | PyScanner.FindNthUseOfStringW | `(string: str, nth: int, offset: int, section: int) -> int` (std::wstring) | other-args | - |
| 13 | FindAssertion | PyScanner.FindAssertion | `(assertion_file: str, assertion_msg: str, line_number: int = 0, offset: int = 0) -> int` | other-args | - |
| 14 | GetSectionAddressRange | PyScanner.GetSectionAddressRange | `(section: int) -> tuple[int,int]` | other-args(section) | - |
| 15 | GetScanStatus | PyScanner.GetScanStatus | `() -> dict` ({"scans": {name:addr}, "hooks": {name:status}}) | NO-ARG getter | - |

Note: `Find`, `FindInRange`, and the address/string-use scanners are registered **without** explicit `py::arg` names (positional only); only `Initialize`, `FindAssertion`, and `GetSectionAddressRange` declare named args in native.

### Struct return types & fields
No data-field `py::class_`. `PyScanner` binds `def_static` methods only. Returns are primitives: `int` (uintptr_t addresses), `bool`, `tuple[int,int]` (`GetSectionAddressRange`), and `dict` (`GetScanStatus`, built with nested `scans`/`hooks` sub-dicts). No struct field tables applicable.

### Stub vs Native disagreements
- **Native-only:** `GetScanStatus` — bound in native (returns a dict of scan/hook results) but **absent from the stub**.
- Signature drift — `GetSectionAddressRange`: native returns `py::make_tuple(start, end)` (always a 2-tuple); stub types it `Optional[tuple[int,int]]` (implies possible `None`). Native never returns None.
- The other 13 methods match between stub and native (names, defaults `check_valid_ptr=True`, `scan_range=0xFF`, `line_number=0`, `offset=0`, `module_name=""`).


---


# R2_b7 — Method Inventory: PyRender, PyOverlay, PyDXOverlay, PyTexture, PyKeystroke, PyMouse

Sources read in full:
- `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\render\render_bindings.cpp`
- `C:\Users\Apo\Py4GW_Reforged_Native\src\overlay\overlay_bindings.cpp` + header `C:\Users\Apo\Py4GW_Reforged_Native\include\overlay\overlay.h`
- `C:\Users\Apo\Py4GW_Reforged_Native\src\overlay\dx_overlay_bindings.cpp`
- `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\textures\texture_bindings.cpp`
- `C:\Users\Apo\Py4GW_Reforged_Native\src\virtual_input\virtual_input_bindings.cpp`
- Struct header `C:\Users\Apo\Py4GW_Reforged_Native\include\GW\common\game_pos.h` (Vec2f/Vec3f)
- Stubs: `PyOverlay.pyi`, `PyDXOverlay.pyi`, legacy `Py2DRenderer.pyi`, `PyKeystroke.pyi`

Note on struct returns: `GW::Vec2f`/`GW::Vec3f` are the only bound structs returned by value; overlay coordinate methods return them (per `overlay.h`). Texture funcs return `int` (uint64 D3D9 texture pointer handle). PyRender returns primitives only.

---

## PyRender
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\render\render_bindings.cpp`
- Stub: NONE
- Module shape: module-level free functions only (no classes)

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | get_is_in_render_loop | free fn | `() -> bool` | NO-ARG getter | - |
| 2 | get_is_fullscreen | free fn | `() -> int` | NO-ARG getter | - |
| 3 | get_viewport_width | free fn | `() -> int` (uint32_t) | NO-ARG getter | - |
| 4 | get_viewport_height | free fn | `() -> int` (uint32_t) | NO-ARG getter | - |
| 5 | get_field_of_view | free fn | `() -> float` | NO-ARG getter | - |

### Struct return types & fields
None (all scalars).

### Stub vs Native disagreements
- No stub exists. All 5 functions are native-only by definition. Consumers get no type hints.

---

## PyOverlay
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\overlay\overlay_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PyOverlay.pyi`
- Module shape: classes only — `Vec2f`, `Vec3f`, `Overlay`, `ScreenOverlay`

### Methods / Functions

**Vec2f / Vec3f constructors**
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | __init__ | Vec2f | `() -> None` | action/ctor | Vec2f |
| 2 | __init__ | Vec2f | `(x: float, y: float) -> None` | other-args(x,y) | Vec2f |
| 3 | __init__ | Vec3f | `() -> None` | action/ctor | Vec3f |
| 4 | __init__ | Vec3f | `(x: float, y: float, z: float = 0.0) -> None` | other-args(x,y,z) | Vec3f |

**Overlay** (`ImU32 color` shown as `int`; `from`/`to`/`p*`/`center`/`position` are `Vec2f` for 2D methods, `Vec3f` for `*3D`)
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 5 | __init__ | Overlay.method | `() -> None` | action/ctor | Overlay |
| 6 | RefreshDrawList | Overlay.method | `() -> None` | action/mutator | - |
| 7 | GetMouseCoords | Overlay.method | `() -> Vec2f` | NO-ARG getter | Vec2f |
| 8 | FindZ | Overlay.method | `(x: float, y: float, pz: int = 0) -> float` | other-args(x,y,pz) | - |
| 9 | FindZPlane | Overlay.method | `(x: float, y: float, z: int = 0) -> int` (uint32) | other-args(x,y,z) | - |
| 10 | WorldToScreen | Overlay.method | `(x: float, y: float, z: float) -> Vec2f` | other-args(x,y,z) | Vec2f |
| 11 | GetMouseWorldPos | Overlay.method | `() -> Vec3f` | NO-ARG getter | Vec3f |
| 12 | GamePosToWorldMap | Overlay.method | `(x: float, y: float) -> Vec2f` | other-args(x,y) | Vec2f |
| 13 | WorldMapToGamePos | Overlay.method | `(x: float, y: float) -> Vec2f` | other-args(x,y) | Vec2f |
| 14 | WorldMapToScreen | Overlay.method | `(x: float, y: float) -> Vec2f` | other-args(x,y) | Vec2f |
| 15 | ScreenToWorldMap | Overlay.method | `(x: float, y: float) -> Vec2f` | other-args(x,y) | Vec2f |
| 16 | GameMapToScreen | Overlay.method | `(x: float, y: float) -> Vec2f` | other-args(x,y) | Vec2f |
| 17 | ScreenToGameMapPos | Overlay.method | `(x: float, y: float) -> Vec2f` | other-args(x,y) | Vec2f |
| 18 | NormalizedScreenToScreen | Overlay.method | `(norm_x: float, norm_y: float) -> Vec2f` | other-args(norm_x,norm_y) | Vec2f |
| 19 | ScreenToNormalizedScreen | Overlay.method | `(screen_x: float, screen_y: float) -> Vec2f` | other-args(screen_x,screen_y) | Vec2f |
| 20 | NormalizedScreenToWorldMap | Overlay.method | `(norm_x: float, norm_y: float) -> Vec2f` | other-args(norm_x,norm_y) | Vec2f |
| 21 | NormalizedScreenToGameMap | Overlay.method | `(norm_x: float, norm_y: float) -> Vec2f` | other-args(norm_x,norm_y) | Vec2f |
| 22 | GamePosToNormalizedScreen | Overlay.method | `(x: float, y: float) -> Vec2f` | other-args(x,y) | Vec2f |
| 23 | BeginDraw | Overlay.method | `() -> None` (overload 1) | action/mutator | - |
| 24 | BeginDraw | Overlay.method | `(name: str) -> None` (overload 2) | other-args(name) | - |
| 25 | BeginDraw | Overlay.method | `(name: str, x: float, y: float, width: float, height: float) -> None` (overload 3) | other-args(name,x,y,width,height) | - |
| 26 | EndDraw | Overlay.method | `() -> None` | action/mutator | - |
| 27 | DrawLine | Overlay.method | `(from: Vec2f, to: Vec2f, color: int = 0xFFFFFFFF, thickness: float = 1.0) -> None` | other-args | - |
| 28 | DrawLine3D | Overlay.method | `(from: Vec3f, to: Vec3f, color: int = 0xFFFFFFFF, thickness: float = 1.0) -> None` | other-args | - |
| 29 | DrawTriangle | Overlay.method | `(p1: Vec2f, p2: Vec2f, p3: Vec2f, color: int = 0xFFFFFFFF, thickness: float = 1.0) -> None` | other-args | - |
| 30 | DrawTriangle3D | Overlay.method | `(p1: Vec3f, p2: Vec3f, p3: Vec3f, color: int = 0xFFFFFFFF, thickness: float = 1.0) -> None` | other-args | - |
| 31 | DrawTriangleFilled | Overlay.method | `(p1: Vec2f, p2: Vec2f, p3: Vec2f, color: int = 0xFFFFFFFF) -> None` | other-args | - |
| 32 | DrawTriangleFilled3D | Overlay.method | `(p1: Vec3f, p2: Vec3f, p3: Vec3f, color: int = 0xFFFFFFFF) -> None` | other-args | - |
| 33 | DrawQuad | Overlay.method | `(p1: Vec2f, p2: Vec2f, p3: Vec2f, p4: Vec2f, color: int = 0xFFFFFFFF, thickness: float = 1.0) -> None` | other-args | - |
| 34 | DrawQuad3D | Overlay.method | `(p1: Vec3f, p2: Vec3f, p3: Vec3f, p4: Vec3f, color: int = 0xFFFFFFFF, thickness: float = 1.0) -> None` | other-args | - |
| 35 | DrawQuadFilled | Overlay.method | `(p1: Vec2f, p2: Vec2f, p3: Vec2f, p4: Vec2f, color: int = 0xFFFFFFFF) -> None` | other-args | - |
| 36 | DrawQuadFilled3D | Overlay.method | `(p1: Vec3f, p2: Vec3f, p3: Vec3f, p4: Vec3f, color: int = 0xFFFFFFFF) -> None` | other-args | - |
| 37 | DrawPoly | Overlay.method | `(center: Vec2f, radius: float, color: int = 0xFFFFFFFF, numSegments: int = 12, thickness: float = 1.0) -> None` | other-args | - |
| 38 | DrawPoly3D | Overlay.method | `(center: Vec3f, radius: float, color: int = 0xFFFFFFFF, numSegments: int = 12, thickness: float = 1.0, autoZ: bool = True) -> None` | other-args | - |
| 39 | DrawPolyFilled | Overlay.method | `(center: Vec2f, radius: float, color: int = 0xFFFFFFFF, numSegments: int = 12) -> None` | other-args | - |
| 40 | DrawPolyFilled3D | Overlay.method | `(center: Vec3f, radius: float, color: int = 0xFFFFFFFF, numSegments: int = 12, autoZ: bool = True) -> None` | other-args | - |
| 41 | DrawCubeOutline | Overlay.method | `(center: Vec3f, size: float, color: int = 0xFFFFFFFF, thickness: float = 1.0) -> None` | other-args | - |
| 42 | DrawCubeFilled | Overlay.method | `(center: Vec3f, size: float, color: int = 0xFFFFFFFF) -> None` | other-args | - |
| 43 | DrawText | Overlay.method | `(position: Vec2f, text: str, color: int = 0xFFFFFFFF, centered: bool = True, scale: float = 1.0) -> None` (native `DrawText2D`) | other-args | - |
| 44 | DrawText3D | Overlay.method | `(position3D: Vec3f, text: str, color: int = 0xFFFFFFFF, autoZ: bool = True, centered: bool = True, scale: float = 1.0) -> None` | other-args | - |
| 45 | GetDisplaySize | Overlay.method | `() -> Vec2f` | NO-ARG getter | Vec2f |
| 46 | IsMouseClicked | Overlay.method | `(button: int = 0) -> bool` | other-args(button) | - |
| 47 | PushClipRect | Overlay.method | `(x: float, y: float, x2: float, y2: float) -> None` | other-args | - |
| 48 | PopClipRect | Overlay.method | `() -> None` | action/mutator | - |
| 49 | DrawTexture | Overlay.method | `(path: str, width: float = 32.0, height: float = 32.0) -> None` (overload 1) | other-args | - |
| 50 | DrawTexture | Overlay.method | `(path: str, size: tuple = (32,32), uv0: tuple = (0,0), uv1: tuple = (1,1), tint: tuple = (255,255,255,255), border_col: tuple = (0,0,0,0)) -> None` (overload 2) | other-args | - |
| 51 | DrawTexturedRect | Overlay.method | `(x: float, y: float, width: float, height: float, texture_path: str) -> None` (overload 1) | other-args | - |
| 52 | DrawTexturedRect | Overlay.method | `(pos: tuple, size: tuple, texture_path: str, uv0: tuple = (0,0), uv1: tuple = (1,1), tint: tuple = (255,255,255,255)) -> None` (overload 2) | other-args | - |
| 53 | UpkeepTextures | Overlay.method | `(timeout: int = 30) -> None` | other-args(timeout) | - |
| 54 | ImageButton | Overlay.method | `(caption: str, file_path: str, width: float = 32.0, height: float = 32.0, frame_padding: int = 0) -> bool` (overload 1) | other-args | - |
| 55 | ImageButton | Overlay.method | `(caption: str, file_path: str, size: tuple = (32,32), uv0: tuple = (0,0), uv1: tuple = (1,1), bg_color: tuple = (0,0,0,0), tint_color: tuple = (255,255,255,255), frame_padding: int = 0) -> bool` (overload 2) | other-args | - |
| 56 | DrawTextureInForegound | Overlay.method | `(pos: tuple = (0,0), size: tuple = (100,100), texture_path: str = "", uv0: tuple = (0,0), uv1: tuple = (1,1), tint: tuple = (255,255,255,255)) -> None` | other-args | - |
| 57 | DrawTextureInDrawlist | Overlay.method | `(pos: tuple = (0,0), size: tuple = (100,100), texture_path: str = "", uv0: tuple = (0,0), uv1: tuple = (1,1), tint: tuple = (255,255,255,255)) -> None` | other-args | - |

**ScreenOverlay**
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 58 | __init__ | ScreenOverlay | `() -> None` | action/ctor | ScreenOverlay |
| 59 | create_overlay | ScreenOverlay.method | `(ms: int = 0, destroy: bool = False) -> None` (native `CreatePrimary`) | other-args(ms,destroy) | - |
| 60 | destroy | ScreenOverlay.method | `() -> None` | action/mutator | - |
| 61 | show | ScreenOverlay.method | `(show: bool) -> None` | other-args(show) | - |
| 62 | begin | ScreenOverlay.method | `() -> None` | action/mutator | - |
| 63 | draw_rect | ScreenOverlay.method | `(x: float, y: float, w: float, h: float, argb: int, thickness: float = 1.0) -> None` | other-args | - |
| 64 | draw_rect_filled | ScreenOverlay.method | `(x: float, y: float, w: float, h: float, argb: int) -> None` | other-args | - |
| 65 | draw_text_box | ScreenOverlay.method | `(x: float, y: float, w: float, h: float, text: str, argb: int, px_size: float, family: str = "Segoe UI", hcenter: bool = False, vcenter: bool = False) -> None` | other-args | - |
| 66 | end | ScreenOverlay.method | `() -> None` (native `End`, presents via UpdateLayeredWindow) | action/mutator | - |
| 67 | get_desktop_size | ScreenOverlay.method | `() -> tuple[int,int]` (width, height) | NO-ARG getter | - |
| 68 | set_auto_expire | ScreenOverlay.method | `(ms: int, destroy: bool = False) -> None` | other-args(ms,destroy) | - |

### Struct return types & fields
| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| Vec2f | x | float | def_readwrite |
| Vec2f | y | float | def_readwrite |
| Vec3f | x | float | def_readwrite |
| Vec3f | y | float | def_readwrite |
| Vec3f | z | float | def_readwrite |

(Overlay / ScreenOverlay are handle classes with methods only — no bound data members. Header `game_pos.h` Vec2f/Vec3f have many operator overloads/free helpers, but ONLY x/y/z are exposed to Python.)

### Stub vs Native disagreements
- **Stub is drastically incomplete / wrong.** `PyOverlay.pyi` `Overlay` declares only `Begin, End, DrawPoint, DrawLine, DrawRect, DrawRectFilled` — none of which match the real bindings except loosely `DrawLine`.
  - Stub-only (do NOT exist natively on Overlay): `Begin`, `End`, `DrawPoint`, `DrawRect`, `DrawRectFilled`. (Native uses `BeginDraw`/`EndDraw`; `DrawRect*`/`DrawPoint` do not exist on `Overlay`.)
  - Stub `DrawLine(x1,y1,x2,y2,color,thickness)` — signature drift; native is `DrawLine(from: Vec2f, to: Vec2f, color, thickness)`.
  - Native-only (missing from stub): all 50+ real `Overlay` methods (coordinate conversions, `BeginDraw` overloads, all Draw* 2D/3D shapes, texture/ImageButton APIs, clip-rect, mouse queries).
  - `Vec2f`/`Vec3f` classes: stub matches native (x/y[/z] + ctor).
  - `ScreenOverlay`: stub covers `create_overlay, destroy, show, begin, draw_rect, draw_rect_filled` but is **missing** `draw_text_box`, `end`, `get_desktop_size`, `set_auto_expire`.

---

## PyDXOverlay
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\overlay\dx_overlay_bindings.cpp`
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PyDXOverlay.pyi` (legacy compare: `Py2DRenderer.pyi`)
- Module shape: single class `DXOverlay`

### Methods / Functions
(2D positional args are `tuple[float,float]`; 3D are `tuple[float,float,float]`; `color`/`int_tint` are `int`.)
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | __init__ | DXOverlay | `() -> None` | action/ctor | DXOverlay |
| 2 | set_primitives | DXOverlay.method | `(primitives, draw_color: int = 0xFFFFFFFF) -> None` | other-args | - |
| 3 | build_pathing_trapezoid_geometry | DXOverlay.method | `(color: int = 0xFF00FF00) -> None` | other-args(color) | - |
| 4 | inverse_rendering | DXOverlay.method | `(enabled: bool) -> None` | other-args(enabled) | - |
| 5 | set_world_zoom_x | DXOverlay.method | `(zoom: float) -> None` | other-args(zoom) | - |
| 6 | set_world_zoom_y | DXOverlay.method | `(zoom: float) -> None` | other-args(zoom) | - |
| 7 | set_world_pan | DXOverlay.method | `(x: float, y: float) -> None` | other-args(x,y) | - |
| 8 | set_world_rotation | DXOverlay.method | `(r: float) -> None` | other-args(r) | - |
| 9 | set_world_space | DXOverlay.method | `(enabled: bool) -> None` | other-args(enabled) | - |
| 10 | set_world_scale | DXOverlay.method | `(scale: float) -> None` | other-args(scale) | - |
| 11 | set_screen_offset | DXOverlay.method | `(x: float, y: float) -> None` | other-args(x,y) | - |
| 12 | set_screen_zoom_x | DXOverlay.method | `(zoom: float) -> None` | other-args(zoom) | - |
| 13 | set_screen_zoom_y | DXOverlay.method | `(zoom: float) -> None` | other-args(zoom) | - |
| 14 | set_screen_rotation | DXOverlay.method | `(r: float) -> None` | other-args(r) | - |
| 15 | set_circular_mask | DXOverlay.method | `(enabled: bool) -> None` | other-args(enabled) | - |
| 16 | set_circular_mask_radius | DXOverlay.method | `(radius: float) -> None` | other-args(radius) | - |
| 17 | set_circular_mask_center | DXOverlay.method | `(x: float, y: float) -> None` | other-args(x,y) | - |
| 18 | set_rectangle_mask | DXOverlay.method | `(enabled: bool) -> None` | other-args(enabled) | - |
| 19 | set_rectangle_mask_bounds | DXOverlay.method | `(x: float, y: float, width: float, height: float) -> None` | other-args | - |
| 20 | render | DXOverlay.method | `() -> None` | action/mutator | - |
| 21 | DrawLine | DXOverlay.method | `(from: tuple, to: tuple, color: int = 0xFFFFFFFF, thickness: float = 1.0) -> None` | other-args | - |
| 22 | DrawTriangle | DXOverlay.method | `(p1, p2, p3, color: int = 0xFFFFFFFF, thickness: float = 1.0) -> None` | other-args | - |
| 23 | DrawTriangleFilled | DXOverlay.method | `(p1, p2, p3, color: int = 0xFFFFFFFF) -> None` | other-args | - |
| 24 | DrawQuad | DXOverlay.method | `(p1, p2, p3, p4, color: int = 0xFFFFFFFF, thickness: float = 1.0) -> None` | other-args | - |
| 25 | DrawQuadFilled | DXOverlay.method | `(p1, p2, p3, p4, color: int = 0xFFFFFFFF) -> None` | other-args | - |
| 26 | DrawPoly | DXOverlay.method | `(center, radius: float, color: int = 0xFFFFFFFF, segments: int = 3, thickness: float = 1.0) -> None` | other-args | - |
| 27 | DrawPolyFilled | DXOverlay.method | `(center, radius: float, color: int = 0xFFFFFFFF, segments: int = 3) -> None` | other-args | - |
| 28 | DrawCubeOutline | DXOverlay.method | `(center, size, color: int = 0xFFFFFFFF, use_occlusion: bool = True) -> None` | other-args | - |
| 29 | DrawCubeFilled | DXOverlay.method | `(center, size, color: int = 0xFFFFFFFF, use_occlusion: bool = True) -> None` | other-args | - |
| 30 | DrawLine3D | DXOverlay.method | `(from, to, color: int = 0xFFFFFFFF, use_occlusion: bool = True, segments: int = 16, floor_offset: float = 0.0) -> None` | other-args | - |
| 31 | DrawTriangle3D | DXOverlay.method | `(p1, p2, p3, color: int = 0xFFFFFFFF, use_occlusion: bool = True, edge_segments: int = 16, floor_offset: float = 0.0) -> None` | other-args | - |
| 32 | DrawTriangleFilled3D | DXOverlay.method | `(p1, p2, p3, color: int = 0xFFFFFFFF, use_occlusion: bool = True, edge_segments: int = 16, floor_offset: float = 0.0) -> None` | other-args | - |
| 33 | DrawQuad3D | DXOverlay.method | `(p1, p2, p3, p4, color: int = 0xFFFFFFFF, use_occlusion: bool = True, edge_segments: int = 16, floor_offset: float = 0.0) -> None` | other-args | - |
| 34 | DrawQuadFilled3D | DXOverlay.method | `(p1, p2, p3, p4, color: int = 0xFFFFFFFF, use_occlusion: bool = True, segments: int = 16, floor_offset: float = 0.0) -> None` | other-args | - |
| 35 | DrawPoly3D | DXOverlay.method | `(center, radius: float, color: int = 0xFFFFFFFF, numSegments: int = 3, autoZ: bool = True, use_occlusion: bool = True, segments: int = 16, floor_offset: float = 0.0) -> None` | other-args | - |
| 36 | DrawPolyFilled3D | DXOverlay.method | `(center, radius: float, color: int = 0xFFFFFFFF, numSegments: int = 3, autoZ: bool = True, use_occlusion: bool = True, segments: int = 16, floor_offset: float = 0.0) -> None` | other-args | - |
| 37 | Setup3DView | DXOverlay.method | `() -> None` | action/mutator | - |
| 38 | ApplyStencilMask | DXOverlay.method | `() -> None` | action/mutator | - |
| 39 | ResetStencilMask | DXOverlay.method | `() -> None` | action/mutator | - |
| 40 | DrawTexture | DXOverlay.method | `(file_path: str, screen_pos_x: float, screen_pos_y: float, width: float = 100.0, height: float = 100.0, int_tint: int = 0xFFFFFFFF) -> None` | other-args | - |
| 41 | DrawTexture3D | DXOverlay.method | `(file_path: str, world_pos_x: float, world_pos_y: float, world_pos_z: float, width: float = 100.0, height: float = 100.0, use_occlusion: bool = True, int_tint: int = 0xFFFFFFFF) -> None` | other-args | - |
| 42 | DrawQuadTextured3D | DXOverlay.method | `(file_path: str, p1, p2, p3, p4, use_occlusion: bool = True, int_tint: int = 0xFFFFFFFF) -> None` | other-args | - |
| 43 | SaveGeometryToFile | DXOverlay.method | `(filename: str, min_x: float, min_y: float, max_x: float, max_y: float) -> None` | other-args | - |

### Struct return types & fields
None — `DXOverlay` is a handle class with methods only; no bound data members. No struct returned by value (all methods return `None`; `set_primitives` accepts geometry, does not return a struct).

### Stub vs Native disagreements
- `PyDXOverlay.pyi` **matches native exactly** (43 methods, same names/args/order/defaults). The only cosmetic note: `SaveGeometryToFile` stub returns `None`, matching native `void` (legacy `Py2DRenderer.pyi` returned `int`).
- vs legacy `Py2DRenderer.pyi` (retired name): renamed class `Py2DRenderer` → `DXOverlay`; legacy used `PyOverlay.Point2D/Point3D` params (now plain float tuples); legacy `set_mask_radius`/`set_mask_center` renamed to `set_circular_mask_radius`/`set_circular_mask_center`; new-native adds `render` present in both but legacy lacked `set_screen_offset`? (present in both). Legacy `SaveGeometryToFile -> int`; native now returns `None`. `set_primitives` legacy took `List[List[Point2D]]`; native takes an opaque `primitives` arg.

---

## PyTexture
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\GW\textures\texture_bindings.cpp`
- Stub: NONE
- Module shape: module-level free functions only. All return an ImGui texture handle = D3D9 texture pointer as an int (uint64), `0` when not ready. Usable with `PyImGui.image()`.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | get_file_texture | free fn | `(path: str) -> int` | other-args(path) | - (returns handle int) |
| 2 | get_dat_texture | free fn | `(key: str) -> int` (`gwdat://<file_id>` routes to GW.dat reader) | other-args(key) | - |
| 3 | get_texture_by_file_id | free fn | `(file_id: int) -> int` (async; 0 until upload completes) | subject-id (GW.dat file_id) | - |
| 4 | get_colored_model_texture | free fn | `(model_file_id: int, dye_tint: int = 0, dye1: int = 0, dye2: int = 0, dye3: int = 0, dye4: int = 0) -> int` | other-args (subject model_file_id + dyes) | - |
| 5 | cleanup_old_textures | free fn | `(timeout_seconds: int = 30) -> None` | action/mutator | - |

### Struct return types & fields
None. Return values are raw `uint64_t` handles (reinterpret_cast of `IDirect3DTexture9*`), not bound structs.

### Stub vs Native disagreements
- No stub exists. All 5 functions are native-only; consumers get no type hints. Return type is documented via module docstring only.

---

## PyKeystroke
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\virtual_input\virtual_input_bindings.cpp` (the `PyKeystroke` embedded module block, lines 9–23)
- Stub: `C:\Users\Apo\Py4GW_Reforged\stubs\PyKeystroke.pyi`
- Module shape: single class `PyKeyHandler` (registered on the `PyKeystroke` module). Note: despite arg name `virtualKeyCode`, docstrings say scan codes.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | __init__ | PyKeyHandler | `() -> None` | action/ctor | PyKeyHandler |
| 2 | PressKey | PyKeyHandler.method | `(virtualKeyCode: int) -> None` (native `press_key`) | other-args(virtualKeyCode) | - |
| 3 | ReleaseKey | PyKeyHandler.method | `(virtualKeyCode: int) -> None` (native `release_key`) | other-args(virtualKeyCode) | - |
| 4 | PushKey | PyKeyHandler.method | `(virtualKeyCode: int) -> None` (native `push_key`) | other-args(virtualKeyCode) | - |
| 5 | PressKeyCombo | PyKeyHandler.method | `(keys: List[int]) -> None` (native `press_key_combo`) | other-args(keys) | - |
| 6 | ReleaseKeyCombo | PyKeyHandler.method | `(keys: List[int]) -> None` (native `release_key_combo`) | other-args(keys) | - |
| 7 | PushKeyCombo | PyKeyHandler.method | `(keys: List[int]) -> None` (native `push_key_combo`) | other-args(keys) | - |

### Struct return types & fields
None. `PyKeyHandler` has methods only; no bound data members. No struct returned.

### Stub vs Native disagreements
- `PyKeystroke.pyi` `PyKeyHandler` **matches native exactly** (6 methods + ctor, same names/args). No `PyMouse` in this stub (PyMouse has no stub — see below).

---

## PyMouse
- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\virtual_input\virtual_input_bindings.cpp` (the separate `PyMouse` embedded module block, lines 25–39)
- Stub: NONE
- Module shape: single class `PyMouse` (`MouseHandler`), registered on its own `PyMouse` module.

### Methods / Functions
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | __init__ | PyMouse | `() -> None` | action/ctor | PyMouse |
| 2 | MoveMouse | PyMouse.method | `(x, y) -> None` (relative to client window) | other-args(x,y) | - |
| 3 | Click | PyMouse.method | `(button: int = 0, x: int = 0, y: int = 0) -> None` | other-args(button,x,y) | - |
| 4 | DoubleClick | PyMouse.method | `(button: int = 0, x: int = 0, y: int = 0) -> None` | other-args(button,x,y) | - |
| 5 | Scroll | PyMouse.method | `(delta, x: int = 0, y: int = 0) -> None` | other-args(delta,x,y) | - |
| 6 | PressButton | PyMouse.method | `(button: int = 0, x: int = 0, y: int = 0) -> None` | other-args(button,x,y) | - |
| 7 | ReleaseButton | PyMouse.method | `(button: int = 0, x: int = 0, y: int = 0) -> None` | other-args(button,x,y) | - |

### Struct return types & fields
None. `PyMouse` (MouseHandler) has methods only; no bound data members. No struct returned.

### Stub vs Native disagreements
- No stub exists. All methods native-only; consumers get no type hints. `PyKeystroke.pyi` header comment mentions "PyMouse module available" but provides no class definition for it.


---


## PyUIManager
- Native binding: C:\Users\Apo\Py4GW_Reforged_Native\src\GW\ui\ui_bindings.cpp
- Stub: C:\Users\Apo\Py4GW_Reforged\stubs\PyUIManager.pyi
- Headers: include\GW\ui\ui.h ; include\GW\native_ui\native_ui.h ; include\GW\context\ui.h
- Module shape: **class-only mix** — 5 bound `py::class_` types. Four are snapshot/value structs (`UIInteractionCallback`, `FramePosition`, `FrameRelation`, `UIFrame`); the fifth, `UIManager` (backed by empty `UIManagerShim`), is a namespace-class holding **156 unique `def_static` methods** (`set_window_visible` is bound twice, so 157 registrations). There are **no module-level free functions** — everything hangs off a class. `UIFrame` and `UIInteractionCallback` also carry one instance method each.
- IMPORTANT SCOPE NOTE: The cpp binds ONLY the migrated `GW::ui` surface. The stub also declares the legacy `native_ui` custom subsystems (frame logs, devtext hosting, window clones/title hooks, controller anchors, frame-list item swarm, key mappings, compass, settings blob, tooltip address, edit-box/slider/progress controls, etc.) which are **NOT ported / NOT bound** — these are stub-only (see disagreements). The cpp source comment (lines 14-21) and native_ui.h explicitly document this gap.

### Methods / Functions

#### Snapshot / value-struct instance methods
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 1 | get_address | UIInteractionCallback.get_address | `() -> int` | NO-ARG getter | - |
| 2 | get_context | UIFrame.get_context | `() -> None` (refresh snapshot from live frame) | action/mutator (refreshes self) | - |

#### UIManager static methods — Global state / language / windows
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 3 | get_text_language | UIManager | `() -> int` | NO-ARG getter | - |
| 4 | is_world_map_showing | UIManager | `() -> bool` | NO-ARG getter | - |
| 5 | is_ui_drawn | UIManager | `() -> bool` | NO-ARG getter | - |
| 6 | is_shift_screenshot | UIManager | `() -> bool` | NO-ARG getter | - |
| 7 | is_window_visible | UIManager | `(window_id:int) -> bool` | subject-id (window_id) | - |
| 8 | get_window_position | UIManager | `(window_id:int) -> tuple(l,t,r,b)|None` (stub: `list[int]`) | subject-id (window_id) | - |
| 9 | set_window_visible | UIManager | `(window_id:int, is_visible:bool) -> bool` (queues) | action/mutator (queues) | - |
| 10 | set_open_links | UIManager | `(toggle:bool) -> bool` (queues; stub `None`) | action/mutator (queues) | - |
| 11 | get_frame_limit | UIManager | `() -> int` | NO-ARG getter | - |
| 12 | set_frame_limit | UIManager | `(value:int) -> bool` (queues; stub `None`) | action/mutator (queues) | - |

#### UIManager static methods — Frame tree traversal / discovery
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 13 | get_root_frame_id | UIManager | `() -> int` | NO-ARG getter | - |
| 14 | get_frame_array | UIManager | `() -> List[int]` | NO-ARG getter | - |
| 15 | get_frame_id_by_label | UIManager | `(label:str) -> int` | other-args(label) | - |
| 16 | get_frame_id_by_hash | UIManager | `(hash:int) -> int` | subject-id (hash) | - |
| 17 | get_hash_by_label | UIManager | `(label:str) -> int` | other-args(label) | - |
| 18 | get_child_frame_by_frame_id | UIManager | `(parent_frame_id:int, child_offset:int) -> int` | subject-id + offset | - |
| 19 | get_child_frame_path_by_frame_id | UIManager | `(parent_frame_id:int, child_offsets:List[int]) -> int` | subject-id + path | - |
| 20 | get_child_frame_id | UIManager | `(parent_hash:int, child_offsets:List[int]) -> int` | subject-id (hash) + path | - |
| 21 | get_child_frame_id_from_name_hash | UIManager | `(parent_frame_id:int, name_hash:int) -> int` | subject-id + hash | - |
| 22 | get_parent_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 23 | get_parent_frame_id_direct | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 24 | get_related_frame_id | UIManager | `(frame_id:int, relation_kind:int, start_after:int=0) -> int` | subject-id + relation | - |
| 25 | get_first_child_frame_id | UIManager | `(parent_frame_id:int) -> int` | subject-id (frame_id) | - |
| 26 | get_last_child_frame_id | UIManager | `(parent_frame_id:int) -> int` | subject-id (frame_id) | - |
| 27 | get_next_child_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 28 | get_prev_child_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 29 | get_item_frame_id | UIManager | `(parent_frame_id:int, index:int) -> int` | subject-id + index | - |
| 30 | get_overlay_frame_ids | UIManager | `() -> List[int]` | NO-ARG getter | - |
| 31 | get_popup_frame_ids | UIManager | `() -> List[int]` | NO-ARG getter | - |
| 32 | get_frame_hierarchy | UIManager | `() -> List[Tuple[int,int,int,int]]` | NO-ARG getter | - |
| 33 | get_frame_coords_by_hash | UIManager | `(frame_hash:int) -> List[Tuple[int,int]]` | subject-id (hash) | - |
| 34 | is_ancestor_of_by_frame_id | UIManager | `(frame_id:int, ancestor_id:int) -> bool` | subject-id + subject-id | - |
| 35 | frame_exists_by_frame_id | UIManager | `(frame_id:int) -> bool` | subject-id (frame_id) | - |
| 36 | **get_frame_snapshot** (native-only) | UIManager | `(frame_id:int) -> dict` (frame_id/parent/hash/layout/flags/type/state + nested `position` & `relation` dicts) | subject-id (frame_id) | dict (not a bound struct) |

#### UIManager static methods — Frame metadata / geometry
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 37 | get_frame_context | UIManager | `(frame_id:int) -> int` (uintptr) | subject-id (frame_id) | - |
| 38 | get_frame_layer_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 39 | set_frame_layer_by_frame_id | UIManager | `(frame_id:int, layer:int) -> bool` (queues) | action/mutator (queues) | - |
| 40 | get_frame_code_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 41 | get_frame_min_size_by_frame_id | UIManager | `(frame_id:int) -> Tuple[float,float]` | subject-id (frame_id) | - |
| 42 | get_frame_client_border_by_frame_id | UIManager | `(frame_id:int) -> Tuple[float,float,float,float]` | subject-id (frame_id) | - |
| 43 | get_frame_clip_rect_by_frame_id | UIManager | `(frame_id:int) -> Tuple[float,float,float,float]` | subject-id (frame_id) | - |
| 44 | get_frame_position_ex_by_frame_id | UIManager | `(frame_id:int) -> Tuple[float,float,float,float,int]` | subject-id (frame_id) | - |
| 45 | get_frame_native_size_by_frame_id | UIManager | `(frame_id:int) -> Tuple[float,float]` | subject-id (frame_id) | - |
| 46 | get_frame_title_by_frame_id | UIManager | `(frame_id:int) -> str` (wide) | subject-id (frame_id) | - |
| 47 | get_frame_label_by_frame_id | UIManager | `(frame_id:int) -> str` (utf8) | subject-id (frame_id) | - |
| 48 | get_frame_user_param_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 49 | get_frame_state_bit_by_frame_id | UIManager | `(frame_id:int, bit:int) -> bool` | subject-id + bit | - |
| 50 | get_frame_opacity_by_frame_id | UIManager | `(frame_id:int) -> float` | subject-id (frame_id) | - |

#### UIManager static methods — Frame state setters
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 51 | set_frame_visible_by_frame_id | UIManager | `(frame_id:int, is_visible:bool) -> bool` (queues) | action/mutator (queues) | - |
| 52 | set_frame_disabled_by_frame_id | UIManager | `(frame_id:int, is_disabled:bool) -> bool` (queues) | action/mutator (queues) | - |
| 53 | set_frame_opacity_by_frame_id | UIManager | `(frame_id:int, opacity:float, fade_time:float=0.0) -> bool` (queues) | action/mutator (queues) | - |
| 54 | show_frame_by_frame_id | UIManager | `(frame_id:int, show:bool) -> bool` (queues) | action/mutator (queues) | - |
| 55 | trigger_frame_redraw_by_frame_id | UIManager | `(frame_id:int) -> bool` (queues) | action/mutator (queues) | - |
| 56 | add_frame_ui_interaction_callback_by_frame_id | UIManager | `(frame_id:int, callback_address:int, wparam:int=0) -> bool` (queues) | action/mutator (queues) | - |
| 57 | destroy_ui_component_by_frame_id | UIManager | `(frame_id:int) -> bool` (queues) | action/mutator (queues) | - |

#### UIManager static methods — Preferences
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 58 | get_preference_options | UIManager | `(pref:int) -> List[int]` | subject-id (pref enum) | - |
| 59 | get_enum_preference | UIManager | `(pref:int) -> int` | subject-id (pref) | - |
| 60 | get_int_preference | UIManager | `(pref:int) -> int` | subject-id (pref) | - |
| 61 | get_bool_preference | UIManager | `(pref:int) -> bool` | subject-id (pref) | - |
| 62 | get_string_preference | UIManager | `(pref:int) -> str` | subject-id (pref) | - |
| 63 | set_enum_preference | UIManager | `(pref:int, value:int) -> bool` (stub `None`) | action/mutator | - |
| 64 | set_int_preference | UIManager | `(pref:int, value:int) -> bool` (stub `None`) | action/mutator | - |
| 65 | set_bool_preference | UIManager | `(pref:int, value:bool) -> bool` (stub `None`) | action/mutator | - |
| 66 | set_string_preference | UIManager | `(pref:int, value:str) -> bool` (stub `None`) | action/mutator | - |

#### UIManager static methods — UI messages / input
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 67 | SendUIMessage | UIManager | `(msgid:int, values:List[int], skip_hooks:bool=False) -> bool` | other-args (packs 16-word POD) | - |
| 68 | SendUIMessageRaw | UIManager | `(msgid:int, wparam:int, lparam:int=0, skip_hooks:bool=False) -> bool` | other-args | - |
| 69 | SendFrameUIMessage | UIManager | `(frame_id:int, message_id:int, wparam:int, lparam:int=0) -> bool` (queues) | action/mutator (queues) | - |
| 70 | SendFrameUIMessageWString | UIManager | `(frame_id:int, message_id:int, text:str) -> bool` (queues) | action/mutator (queues) | - |
| 71 | button_click | UIManager | `(frame_id:int) -> None` (queues; cpp returns true) | action/mutator (queues) | - |
| 72 | button_double_click | UIManager | `(frame_id:int) -> None` (queues) | action/mutator (queues) | - |
| 73 | test_mouse_action | UIManager | `(frame_id:int, current_state:int, wparam:int=0, lparam:int=0) -> None` (queues) | action/mutator (queues) | - |
| 74 | test_mouse_click_action | UIManager | `(frame_id:int, current_state:int, wparam:int=0, lparam:int=0) -> None` (queues) | action/mutator (queues) | - |
| 75 | key_down | UIManager | `(key:int, frame_id:int=0) -> None` (queues) | action/mutator (queues) | - |
| 76 | key_up | UIManager | `(key:int, frame_id:int=0) -> None` (queues) | action/mutator (queues) | - |
| 77 | key_press | UIManager | `(key:int, frame_id:int=0) -> None` (queues) | action/mutator (queues) | - |

#### UIManager static methods — Enc-string helpers
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 78 | is_valid_enc_str | UIManager | `(enc_str:str) -> bool` | other-args(enc_str) | - |
| 79 | uint32_to_enc_str | UIManager | `(value:int) -> str` | other-args(value) | - |
| 80 | enc_str_to_uint32 | UIManager | `(enc_str:str) -> int` | other-args(enc_str) | - |

#### UIManager static methods — Windows (duplicate registration)
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| — | set_window_visible (2nd bind, cpp:995) | UIManager | `(window_id:int, is_visible:bool) -> bool` (queues) — SAME name as #9, bound twice | action/mutator (queues) | - |

#### UIManager static methods — Widget creation (native component factories)
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 81 | create_ui_component_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int, event_callback:int, name_enc:str="", component_label:str="") -> int` (queues) | action/mutator (queues, returns new frame_id) | - |
| 82 | create_ui_component_raw_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int, event_callback:int, wparam:int=0, component_label:str="") -> int` (queues) | action/mutator (queues) | - |
| 83 | create_button_frame_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, name_enc:str="", component_label:str="") -> int` | action/mutator | - |
| 84 | **create_ctl_button_frame_by_frame_id** (native-only) | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, name_enc:str="", component_label:str="") -> int` | action/mutator | - |
| 85 | create_text_button_frame_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, caption:str="", component_label:str="") -> int` | action/mutator | - |
| 86 | **create_flat_button_with_click_by_frame_id** (native-only) | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, label_text:str="", enable_click:bool=False) -> int` | action/mutator | - |
| 87 | create_checkbox_frame_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, name_enc:str="", component_label:str="") -> int` | action/mutator | - |
| 88 | create_scrollable_frame_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, component_label:str="") -> int` (stub adds `page_context:int` arg) | action/mutator | - |
| 89 | create_text_label_frame_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, name_enc:str="", component_label:str="") -> int` | action/mutator | - |
| 90 | create_dropdown_frame_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, component_label:str="") -> int` | action/mutator | - |
| 91 | create_slider_frame_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, component_label:str="") -> int` | action/mutator | - |
| 92 | create_editable_text_frame_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, component_label:str="") -> int` | action/mutator | - |
| 93 | create_progress_bar_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, component_label:str="") -> int` | action/mutator | - |
| 94 | create_tabs_frame_by_frame_id | UIManager | `(parent_frame_id:int, component_flags:int, child_index:int=0, component_label:str="") -> int` | action/mutator | - |

#### UIManager static methods — Button
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 95 | get_button_label_by_frame_id | UIManager | `(frame_id:int) -> str` | subject-id (frame_id) | - |
| 96 | set_button_label_by_frame_id | UIManager | `(frame_id:int, enc_label:str) -> bool` | action/mutator | - |
| 97 | button_mouse_action_by_frame_id | UIManager | `(frame_id:int, action_state:int) -> bool` | action/mutator | - |

#### UIManager static methods — Checkbox
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 98 | is_checkbox_checked_by_frame_id | UIManager | `(frame_id:int) -> bool` | subject-id (frame_id) | - |
| 99 | set_checkbox_checked_by_frame_id | UIManager | `(frame_id:int, checked:bool) -> bool` | action/mutator | - |
| 100 | get_checkbox_value_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 101 | set_checkbox_value_by_frame_id | UIManager | `(frame_id:int, value:int) -> bool` | action/mutator | - |

#### UIManager static methods — Dropdown
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 102 | get_dropdown_options_by_frame_id | UIManager | `(frame_id:int) -> List[int]` | subject-id (frame_id) | - |
| 103 | select_dropdown_option_by_frame_id | UIManager | `(frame_id:int, value:int) -> bool` (queues) | action/mutator (queues) | - |
| 104 | select_dropdown_index_by_frame_id | UIManager | `(frame_id:int, index:int) -> bool` (queues) | action/mutator (queues) | - |
| 105 | add_dropdown_option_by_frame_id | UIManager | `(frame_id:int, label_enc:str, value:int) -> bool` (queues) | action/mutator (queues) | - |
| 106 | get_dropdown_count_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 107 | get_dropdown_option_value_by_frame_id | UIManager | `(frame_id:int, index:int) -> int` | subject-id + index | - |
| 108 | get_dropdown_option_index_by_frame_id | UIManager | `(frame_id:int, value:int) -> int` | subject-id + value | - |
| 109 | get_dropdown_selected_index_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 110 | dropdown_has_value_mapping_by_frame_id | UIManager | `(frame_id:int) -> bool` | subject-id (frame_id) | - |
| 111 | get_dropdown_value_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 112 | set_dropdown_value_by_frame_id | UIManager | `(frame_id:int, value:int) -> bool` | action/mutator | - |

#### UIManager static methods — Slider
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 113 | get_slider_value_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 114 | set_slider_value_by_frame_id | UIManager | `(frame_id:int, value:int) -> bool` (queues) | action/mutator (queues) | - |

#### UIManager static methods — Editable text
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 115 | get_editable_text_value_by_frame_id | UIManager | `(frame_id:int) -> str` | subject-id (frame_id) | - |
| 116 | set_editable_text_value_by_frame_id | UIManager | `(frame_id:int, value:str) -> bool` (queues) | action/mutator (queues) | - |
| 117 | set_editable_text_max_length_by_frame_id | UIManager | `(frame_id:int, max_length:int) -> bool` (queues) | action/mutator (queues) | - |
| 118 | is_editable_text_read_only_by_frame_id | UIManager | `(frame_id:int) -> bool` | subject-id (frame_id) | - |
| 119 | set_editable_text_read_only_by_frame_id | UIManager | `(frame_id:int, read_only:bool) -> bool` (queues) | action/mutator (queues) | - |
| 120 | set_read_only_by_frame_id | UIManager | `(frame_id:int, is_read_only:bool) -> bool` (queues) | action/mutator (queues) | - |
| 121 | is_read_only_by_frame_id | UIManager | `(frame_id:int) -> bool` | subject-id (frame_id) | - |

#### UIManager static methods — Progress bar
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 122 | get_progress_bar_value_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 123 | set_progress_bar_value_by_frame_id | UIManager | `(frame_id:int, value:int) -> bool` (queues) | action/mutator (queues) | - |
| 124 | set_progress_bar_max_by_frame_id | UIManager | `(frame_id:int, value:int) -> bool` (queues) | action/mutator (queues) | - |
| 125 | set_progress_bar_color_id_by_frame_id | UIManager | `(frame_id:int, color_id:int) -> bool` (queues) | action/mutator (queues) | - |
| 126 | set_progress_bar_style_by_frame_id | UIManager | `(frame_id:int, style:int) -> bool` (queues) | action/mutator (queues) | - |

#### UIManager static methods — Text labels
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 127 | get_text_label_encoded_by_frame_id | UIManager | `(frame_id:int) -> str` | subject-id (frame_id) | - |
| 128 | get_text_label_decoded_by_frame_id | UIManager | `(frame_id:int) -> str` | subject-id (frame_id) | - |
| 129 | set_text_label_by_frame_id | UIManager | `(frame_id:int, enc_label:str) -> bool` (queues) | action/mutator (queues) | - |
| 130 | set_label_by_frame_id | UIManager | `(frame_id:int, enc_label:str) -> bool` (queues; ButtonFrame::SetLabel) | action/mutator (queues) | - |
| 131 | set_multiline_label_by_frame_id | UIManager | `(frame_id:int, enc_label:str) -> bool` (queues) | action/mutator (queues) | - |
| 132 | set_text_label_font_by_frame_id | UIManager | `(frame_id:int, font_id:int) -> bool` (queues) | action/mutator (queues) | - |

#### UIManager static methods — Tabs
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 133 | add_tab_by_frame_id | UIManager | `(frame_id:int, tab_name_enc:str, flags:int, child_offset_id:int, callback_address:int=0, wparam:int=0) -> int` (queues) | action/mutator (queues) | - |
| 134 | disable_tab_by_frame_id | UIManager | `(frame_id:int, tab_id:int) -> bool` (queues) | action/mutator (queues) | - |
| 135 | enable_tab_by_frame_id | UIManager | `(frame_id:int, tab_id:int) -> bool` (queues) | action/mutator (queues) | - |
| 136 | remove_tab_by_frame_id | UIManager | `(frame_id:int, tab_id:int) -> bool` (queues) | action/mutator (queues) | - |
| 137 | get_current_tab_index_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 138 | get_tab_frame_id_by_frame_id | UIManager | `(frame_id:int, tab_id:int) -> int` | subject-id + tab_id | - |
| 139 | get_tab_frame_id | UIManager | `(parent_frame_id:int, index:int) -> int` | subject-id + index | - |
| 140 | get_is_tab_enabled_by_frame_id | UIManager | `(frame_id:int, tab_id:int) -> bool` (stub `int`) | subject-id + tab_id | - |
| 141 | get_tab_by_label_by_frame_id | UIManager | `(frame_id:int, label:str) -> int` | subject-id + label | - |
| 142 | get_current_tab_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 143 | choose_tab_by_tab_frame_id | UIManager | `(frame_id:int, tab_frame_id:int) -> bool` (queues) | action/mutator (queues) | - |
| 144 | choose_tab_by_index_by_frame_id | UIManager | `(frame_id:int, tab_index:int) -> bool` (queues) | action/mutator (queues) | - |
| 145 | get_tab_button_by_frame_id | UIManager | `(frame_id:int, tab_frame_id:int) -> int` | subject-id + tab_frame_id | - |

#### UIManager static methods — Scrollable
| # | Name | Owner | Signature | Arg category | Returns-struct |
|---|------|-------|-----------|--------------|----------------|
| 146 | clear_scrollable_items_by_frame_id | UIManager | `(frame_id:int) -> bool` | action/mutator | - |
| 147 | remove_scrollable_item_by_frame_id | UIManager | `(frame_id:int, child_offset_id:int) -> bool` (queues) | action/mutator (queues) | - |
| 148 | add_scrollable_item_by_frame_id | UIManager | `(frame_id:int, flags:int, child_offset_id:int, callback_address:int=0) -> bool` (queues) | action/mutator (queues) | - |
| 149 | get_scrollable_item_frame_id_by_frame_id | UIManager | `(frame_id:int, child_offset_id:int) -> int` | subject-id + offset | - |
| 150 | get_scrollable_selected_value_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 151 | get_scrollable_first_child_frame_id_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 152 | get_scrollable_next_child_frame_id_by_frame_id | UIManager | `(frame_id:int, child_frame_id:int) -> int` | subject-id + child_frame_id | - |
| 153 | get_scrollable_last_child_frame_id_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 154 | get_scrollable_prev_child_frame_id_by_frame_id | UIManager | `(frame_id:int, child_frame_id:int) -> int` | subject-id + child_frame_id | - |
| 155 | get_scrollable_item_rect_by_frame_id | UIManager | `(frame_id:int, child_offset_id:int) -> Tuple[float,float,float,float]` (stub `List[float]`) | subject-id + offset | - |
| 156 | get_scrollable_count_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |
| 157 | get_scrollable_items_by_frame_id | UIManager | `(frame_id:int) -> List[int]` | subject-id (frame_id) | - |
| 158 | get_scrollable_page_by_frame_id | UIManager | `(frame_id:int) -> int` | subject-id (frame_id) | - |

Total distinct bound callables: **156 unique UIManager static methods** (157 registrations counting the duplicate `set_window_visible`) + 2 struct instance methods (`UIFrame.get_context`, `UIInteractionCallback.get_address`).

### Struct return types & fields

These are the bound Python classes. Note none are RETURNED by any UIManager method (all methods return ints/tuples/dicts/lists/bool/str); `UIFrame`/`FramePosition`/`FrameRelation`/`UIInteractionCallback` are constructed directly Python-side (`UIFrame(frame_id)`) and read as cached snapshots. `get_frame_snapshot` returns a plain `dict` (not one of these classes). The debug tool must render `UIFrame` (with nested `FramePosition`/`FrameRelation`/`List[UIInteractionCallback]`) and the `get_frame_snapshot` dict.

| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| UIInteractionCallback | (constructor) | `__init__()` | def(py::init<>) |
| UIInteractionCallback | callback_address | int (uintptr) | def_readwrite |
| UIInteractionCallback | uictl_context | int (uintptr) | def_readwrite |
| UIInteractionCallback | h0008 | int (uint32) | def_readwrite |
| UIInteractionCallback | get_address | `() -> int` | def method |
| FramePosition | (constructor) | `__init__()` | def(py::init<>) |
| FramePosition | top | int | def_readwrite |
| FramePosition | left | int | def_readwrite |
| FramePosition | bottom | int | def_readwrite |
| FramePosition | right | int | def_readwrite |
| FramePosition | content_top | int | def_readwrite |
| FramePosition | content_left | int | def_readwrite |
| FramePosition | content_bottom | int | def_readwrite |
| FramePosition | content_right | int | def_readwrite |
| FramePosition | unknown | float | def_readwrite |
| FramePosition | scale_factor | float | def_readwrite |
| FramePosition | viewport_width | float | def_readwrite |
| FramePosition | viewport_height | float | def_readwrite |
| FramePosition | screen_top | float | def_readwrite |
| FramePosition | screen_left | float | def_readwrite |
| FramePosition | screen_bottom | float | def_readwrite |
| FramePosition | screen_right | float | def_readwrite |
| FramePosition | top_on_screen | int | def_readwrite |
| FramePosition | left_on_screen | int | def_readwrite |
| FramePosition | bottom_on_screen | int | def_readwrite |
| FramePosition | right_on_screen | int | def_readwrite |
| FramePosition | width_on_screen | int | def_readwrite |
| FramePosition | height_on_screen | int | def_readwrite |
| FramePosition | viewport_scale_x | float | def_readwrite |
| FramePosition | viewport_scale_y | float | def_readwrite |
| FrameRelation | (constructor) | `__init__()` | def(py::init<>) |
| FrameRelation | parent_id | int | def_readwrite |
| FrameRelation | field67_0x124 | int | def_readwrite |
| FrameRelation | field68_0x128 | int | def_readwrite |
| FrameRelation | frame_hash_id | int | def_readwrite |
| FrameRelation | siblings | List[int] | def_readwrite |
| UIFrame | (constructor) | `__init__(frame_id:int)` | def(py::init<int>) |
| UIFrame | frame_id | int | def_readwrite |
| UIFrame | parent_id | int | def_readwrite |
| UIFrame | frame_hash | int | def_readwrite |
| UIFrame | visibility_flags | int | def_readwrite |
| UIFrame | type | int | def_readwrite |
| UIFrame | template_type | int | def_readwrite |
| UIFrame | position | FramePosition | def_readwrite |
| UIFrame | relation | FrameRelation | def_readwrite |
| UIFrame | is_created | bool | def_readwrite |
| UIFrame | is_visible | bool | def_readwrite |
| UIFrame | frame_layout | int | def_readwrite |
| UIFrame | child_offset_id | int | def_readwrite |
| UIFrame | frame_callbacks | List[UIInteractionCallback] | def_readwrite |
| UIFrame | frame_state | int | def_readwrite |
| UIFrame | field1_0x0 | int | def_readwrite |
| UIFrame | field2_0x4 | int | def_readwrite |
| UIFrame | field3_0xc | int | def_readwrite |
| UIFrame | field4_0x10 | int | def_readwrite |
| UIFrame | field5_0x14 | int | def_readwrite |
| UIFrame | field7_0x1c | int | def_readwrite |
| UIFrame | field10_0x28 | int | def_readwrite |
| UIFrame | field11_0x2c | int | def_readwrite |
| UIFrame | field12_0x30 | int | def_readwrite |
| UIFrame | field13_0x34 | int | def_readwrite |
| UIFrame | field14_0x38 | int | def_readwrite |
| UIFrame | field15_0x3c | int | def_readwrite |
| UIFrame | field16_0x40 | int | def_readwrite |
| UIFrame | field17_0x44 | int | def_readwrite |
| UIFrame | field18_0x48 | int | def_readwrite |
| UIFrame | field19_0x4c | int | def_readwrite |
| UIFrame | field20_0x50 | int | def_readwrite |
| UIFrame | field21_0x54 | int | def_readwrite |
| UIFrame | field22_0x58 | int | def_readwrite |
| UIFrame | field23_0x5c | int | def_readwrite |
| UIFrame | field24_0x60 | int | def_readwrite |
| UIFrame | field24a_0x64 | int | def_readwrite |
| UIFrame | field24b_0x68 | int | def_readwrite |
| UIFrame | field25_0x6c | int | def_readwrite |
| UIFrame | field26_0x70 | int | def_readwrite |
| UIFrame | field27_0x74 | int | def_readwrite |
| UIFrame | field28_0x78 | int | def_readwrite |
| UIFrame | field29_0x7c | int | def_readwrite |
| UIFrame | field30_0x80 | int | def_readwrite |
| UIFrame | field31_0x84 | List[int] (pointer addrs) | def_readwrite |
| UIFrame | field32_0x94 | int | def_readwrite |
| UIFrame | field33_0x98 | int | def_readwrite |
| UIFrame | field34_0x9c | int | def_readwrite |
| UIFrame | field35_0xa0 | int | def_readwrite |
| UIFrame | field36_0xa4 | int | def_readwrite |
| UIFrame | field40_0xc0 | int | def_readwrite |
| UIFrame | field41_0xc4 | int | def_readwrite |
| UIFrame | field42_0xc8 | int | def_readwrite |
| UIFrame | field43_0xcc | int | def_readwrite |
| UIFrame | field44_0xd0 | int | def_readwrite |
| UIFrame | field45_0xd4 | int | def_readwrite |
| UIFrame | field63_0x11c | int | def_readwrite |
| UIFrame | field64_0x120 | int | def_readwrite |
| UIFrame | field65_0x124 | int | def_readwrite |
| UIFrame | field73_0x144 | int | def_readwrite |
| UIFrame | field74_0x148 | int | def_readwrite |
| UIFrame | field75_0x14c | int | def_readwrite |
| UIFrame | field76_0x150 | int | def_readwrite |
| UIFrame | field77_0x154 | int | def_readwrite |
| UIFrame | field78_0x158 | int | def_readwrite |
| UIFrame | field79_0x15c | int | def_readwrite |
| UIFrame | field80_0x160 | int | def_readwrite |
| UIFrame | field81_0x164 | int | def_readwrite |
| UIFrame | field82_0x168 | int | def_readwrite |
| UIFrame | field83_0x16c | int | def_readwrite |
| UIFrame | field84_0x170 | int | def_readwrite |
| UIFrame | field85_0x174 | int | def_readwrite |
| UIFrame | field86_0x178 | int | def_readwrite |
| UIFrame | field87_0x17c | int | def_readwrite |
| UIFrame | field88_0x180 | int | def_readwrite |
| UIFrame | field89_0x184 | int | def_readwrite |
| UIFrame | field90_0x188 | int | def_readwrite |
| UIFrame | field92_0x190 | int | def_readwrite |
| UIFrame | field93_0x194 | int | def_readwrite |
| UIFrame | field94_0x198 | int | def_readwrite |
| UIFrame | field95_0x19c | int | def_readwrite |
| UIFrame | field96_0x1a0 | int | def_readwrite |
| UIFrame | field97_0x1a4 | int | def_readwrite |
| UIFrame | field98_0x1a8 | int | def_readwrite |
| UIFrame | field100_0x1b0 | int | def_readwrite |
| UIFrame | field101_0x1b4 | int | def_readwrite |
| UIFrame | field102_0x1b8 | int | def_readwrite |
| UIFrame | field103_0x1bc | int | def_readwrite |
| UIFrame | field104_0x1c0 | int | def_readwrite |
| UIFrame | field105_0x1c4 | int | def_readwrite |
| UIFrame | get_context | `() -> None` | def method |
| UIManager (UIManagerShim) | — | (no data members; container for 157 static defs) | py::class_ |

**`get_frame_snapshot` dict shape** (not a bound class, but the debug tool must render it): top-level keys `frame_id, parent_id, frame_hash, frame_layout, visibility_flags, type, template_type, child_offset_id, frame_state, is_created, is_visible, is_disabled`; nested `position` dict (top,left,bottom,right,content_top/left/bottom/right,unknown,scale_factor,viewport_width,viewport_height,screen_top/left/bottom/right,top/left/bottom/right_on_screen,width/height_on_screen,viewport_scale_x/y); nested `relation` dict (parent_id,field67_0x124,field68_0x128,frame_hash_id,siblings:list). If the frame is missing it returns only `{frame_id, is_created:False, is_visible:False}`.

### Stub vs Native disagreements

**Native-only (bound in cpp, MISSING from stub) — 3:**
- `get_frame_snapshot(frame_id) -> dict` — the intended replacement for the `UIFrame` class per its docstring, yet undocumented in the stub.
- `create_ctl_button_frame_by_frame_id(...)`
- `create_flat_button_with_click_by_frame_id(...)`

**Stub-only (declared in .pyi, NOT bound in cpp) — ~85 methods.** These are the legacy `native_ui` custom subsystems the cpp header comment (lines 14-21) and native_ui.h say are NOT ported. Calling any of them raises `AttributeError` at runtime. Grouped:
- Logging: `get_frame_logs`, `clear_frame_logs`, `get_ui_message_logs`, `clear_ui_message_logs`.
- Window/frame construction extras: `create_labeled_frame_by_frame_id`, `create_window_by_frame_id`, `find_available_child_slot`, `CreateNativeWindow`, `create_titled_window_clone`, `create_titled_empty_window`, `create_content_panel_by_frame_id`, `create_scrollable_text_window`.
- Devtext hosting: `ensure_devtext_source`, `open_devtext_window`, `get_devtext_frame_id`, `restore_devtext_source`.
- Content-host / teardown: `resolve_observed_content_host_by_frame_id`, `clear_frame_children_recursive_by_frame_id`, `clear_window_contents_by_frame_id`, `collapse_window_by_frame_id`, `destroy_window_safely_by_frame_id`, `clear_ui_input_targets`.
- Controller/anchor geometry: `set_frame_controller_anchor_margins_by_frame_id_ex`, `queue_frame_controller_update_by_frame_id`, `process_frame_controller_update_by_frame_id`, `choose_anchor_flags_for_desired_rect`, `restore_window_rect_by_frame_id`, `set_frame_margins_by_frame_id`.
- Title hooks (native_ui::title_hook): `set_next_created_window_title`, `clear_next_created_window_title`, `has_next_created_window_title`, `is_window_title_hook_installed`, `get_last_applied_window_title_frame_id`, `get_last_applied_window_title`, `set_frame_title_by_frame_id`.
- Text-label byte/suffix helpers: `get_text_label_encoded_bytes_by_frame_id`, `set_text_label_bytes_by_frame_id`, `append_text_label_encoded_suffix_by_frame_id`, `append_text_label_plain_suffix_by_frame_id`, `create_text_label_frame_with_plain_text_by_frame_id`, `create_text_label_frame_from_template_by_frame_id`, `get_text_label_create_payload_diagnostics_by_template_frame_id`.
- Enc/settings/tooltip/compass/keymap: `async_decode_str`, `is_valid_enc_bytes`, `draw_on_compass`, `load_settings`, `get_settings`, `get_current_tooltip_address`, `get_key_mappings`, `set_key_mappings`, `set_window_position`.
- Button/scrollable/slider extras: `is_button_pushed_by_frame_id`, `set_scrollable_sort_handler_by_frame_id`, `get_scrollable_sort_handler_by_frame_id`, `set_scrollable_page_by_frame_id`, `set_slider_range_by_frame_id`.
- Frame-list item swarm (2026-06-04 block): `ctl_frame_list_create_item_by_frame_id`, `frame_new_subclass_by_frame_id`, `create_scrollable_content_by_frame_id`, `add_text_item_to_frame_list_by_frame_id`, `add_button_item_to_frame_list_by_frame_id`, `add_flat_button_item_to_frame_list_by_frame_id`, `add_control_item_by_frame_id`, `create_control_child_by_frame_id`, `set_frame_list_no_stretch_by_frame_id`, `create_checkbox_child_by_frame_id`, `set_frame_list_selection_by_frame_id`, `add_clickable_text_button_to_selectable_list`, `set_text_button_color_by_frame_id`, `set_text_button_hover_color_by_frame_id`, `set_text_button_text_by_frame_id`, `create_edit_box_child_by_frame_id`, `set_edit_box_text_by_frame_id`, `set_edit_box_max_length_by_frame_id`, `ensure_edit_caret_material`, `is_edit_caret_material_ready`, `create_progress_bar_child_by_frame_id`, `set_progress_bar_percent_by_frame_id`, `get_progress_bar_max_by_frame_id`, `set_progress_bar_increments_per_second_by_frame_id`, `set_progress_bar_overlay_text_by_frame_id`, `create_tabs_as_list_item_by_frame_id`, `add_tab_to_page_by_frame_id`, `tab_set_active_by_frame_id`, `tab_get_active_by_frame_id`, `tab_get_body_frame_by_frame_id`, `set_tab_enabled_by_frame_id`, `create_slider_control_by_frame_id`, `destroy_slider_control_by_frame_id`, `add_group_header_item_to_frame_list_by_frame_id`, `ctl_frame_list_show_item_by_frame_id`, `group_header_get_is_open_by_frame_id`, `group_header_set_is_open_by_frame_id`, `group_header_set_text_by_frame_id`, `create_selectable_scrollable_content_by_frame_id`, `get_frame_list_selection_by_frame_id`.

**Signature / return-type drift (bound both places but disagree):**
- Many queued mutators are typed `-> None` in the stub but the cpp lambdas `return true` (`-> bool`): `set_open_links`, `set_frame_limit`, `button_click`, `button_double_click`, `test_mouse_action`, `test_mouse_click_action`, `key_down`, `key_up`, `key_press`, `set_window_visible`, and the four `set_*_preference` (cpp returns the `SetPreference` bool; stub says `None`).
- `get_window_position`: cpp returns a 4-tuple `(left,top,right,bottom)` or `None`; stub declares `-> list[int]`.
- `get_scrollable_item_rect_by_frame_id`: cpp returns a 4-`float` tuple; stub declares `-> List[float]`.
- `get_is_tab_enabled_by_frame_id`: cpp returns `bool`; stub declares `-> int`.
- `create_scrollable_frame_by_frame_id`: stub adds a `page_context:int` parameter that the bound lambda does not accept (it always passes `nullptr`).
- `get_related_frame_id` `start_after` default is `0` in cpp; stub uses `...`. Similar `= ...` vs concrete-default cosmetic mismatches across the create_* factories.
- Arg-name drift: `add_frame_ui_interaction_callback_by_frame_id` cpp `callback_address`/stub `event_callback`; `add_tab_by_frame_id` cpp `frame_id,child_offset_id,callback_address`/stub `tabs_frame_id,child_index,callback`; scrollable/tab methods use `child_offset_id`/`child_frame_id` in cpp vs `child_index`/`current_child_frame_id` in stub.
- `set_window_visible` is registered **twice** in the cpp (lines 678 and 995) with identical signature — the second wins; harmless but redundant.


---


## PyImGui

- Native binding: `C:\Users\Apo\Py4GW_Reforged_Native\src\imgui\imgui_bindings.cpp` (module root, `PYBIND11_EMBEDDED_MODULE(PyImGui, m)`), plus registrars in `src\imgui\bindings\{types,enums,style,drawlist,docking,io,addons}.cpp`.
- Stubs: `C:\Users\Apo\Py4GW_Reforged\stubs\PyImGui.pyi` (963 lines, current Reforged surface), `C:\Users\Apo\Py4GW_Reforged\stubs\ImGui_Py.pyi` (978 lines, legacy/auto-generated — a *different, smaller* module `ImGui_Py`, not `PyImGui`).
- Module shape: ~330 module-level free functions + bound classes (`Vec2`, `Vec4`, `TableColumnSortSpecs`, `TableSortSpecs`, `ImGuiStyle`, `StyleConfig`, `ImGuiIO`, `DrawList`) + ~30 enum types + 6 addon submodules (`filebrowser`, `hotkey`, `markdown`, `memory_editor`, `anim`, `text_editor`) + `docking`/`drawlist`/`io` folded flat into the root module (not sub-modules).

Registration order in `imgui_bindings.cpp`: `register_types` → `register_enums` → sort-spec classes → `register_style` → all window/widget/etc. m.def blocks → `register_docking` → `register_io` (get_io) → `register_drawlist` → `register_addons`.

---

### Methods / Functions

Arg category legend: **scalar** (numbers/bool/str/ints), **vec/tuple** (ImVec2/ImVec4/tuple/list), **array** (fixed std::array N→tuple), **list** (Python list/vector), **flags** (int enum), **callback/obj** (py::object/Any/buffer), **none** (no args). "Returns-struct" = returns a bound class/tuple rather than a scalar.

#### imgui_bindings.cpp — WINDOW / lifecycle
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 1 | begin | mod | (name:str, dockable:bool=False) -> bool | scalar | no |
| 2 | begin | mod | (name:str, flags:int, dockable:bool=False) -> bool | scalar/flags | no |
| 3 | begin | mod | (name:str, p_open:object=None, flags:int=0, dockable:bool=False) -> tuple(bool,bool) | scalar/obj | tuple |
| 4 | begin_with_close | mod | (name:str, p_open:bool, flags:int=0) -> tuple(bool,bool) | scalar | tuple |
| 5 | end | mod | () -> None | none | no |
| 6 | begin_child | mod | (id:str, size:Vec2=(0,0), border:int=0, flags:int=0) -> bool (always True) | vec/flags | no |
| 7 | end_child | mod | () -> None | none | no |
| 8 | begin_group | mod | () -> None | none | no |
| 9 | end_group | mod | () -> None | none | no |
| 10 | begin_disabled | mod | (disabled:bool=True) -> None | scalar | no |
| 11 | end_disabled | mod | () -> None | none | no |

#### WINDOW SETUP
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 12 | set_next_window_pos | mod | (x:float, y:float, cond:int=0) -> None | scalar | no |
| 13 | set_next_window_pos | mod | (pos:Vec2, cond:int=0, pivot:Vec2=(0,0)) -> None | vec | no |
| 14 | set_next_window_size | mod | (width:float, height:float, cond:int=0) -> None | scalar | no |
| 15 | set_next_window_size | mod | (size:Vec2, cond:int=0) -> None | vec | no |
| 16 | set_next_window_size_constraints | mod | (size_min:Vec2, size_max:Vec2) -> None | vec | no |
| 17 | set_next_window_content_size | mod | (size:Vec2) -> None | vec | no |
| 18 | set_next_window_collapsed | mod | (collapsed:bool, cond:int=0) -> None | scalar | no |
| 19 | set_next_window_focus | mod | () -> None | none | no |
| 20 | set_next_window_bg_alpha | mod | (alpha:float) -> None | scalar | no |
| 21 | set_next_window_scroll | mod | (scroll:Vec2) -> None | vec | no |
| 22 | set_next_window_viewport | mod | (viewport_id:int) -> None | scalar | no |
| 23 | set_next_window_detached | mod | (detached:bool=True, no_taskbar_icon:bool=False, no_decoration:bool=False, top_level:bool=True) -> None | scalar | no |
| 24 | set_next_window_main_viewport | mod | () -> None | none | no |
| 25 | set_window_pos | mod | (x:float, y:float, cond:int=0) -> None | scalar | no |
| 26 | set_window_pos | mod | (pos:Vec2, cond:int=0) -> None | vec | no |
| 27 | set_window_size | mod | (width:float, height:float, cond:int=0) -> None | scalar | no |
| 28 | set_window_size | mod | (size:Vec2, cond:int=0) -> None | vec | no |
| 29 | set_window_collapsed | mod | (collapsed:bool, cond:int=0) -> None | scalar | no |
| 30 | set_window_focus | mod | (name:str) -> None | scalar | no |

#### WINDOW QUERY
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 31 | get_window_pos | mod | () -> Vec2 | none | tuple/vec |
| 32 | get_window_size | mod | () -> Vec2 | none | tuple/vec |
| 33 | get_window_width | mod | () -> float | none | no |
| 34 | get_window_height | mod | () -> float | none | no |
| 35 | get_content_region_avail | mod | () -> Vec2 | none | tuple/vec |
| 36 | is_window_appearing | mod | () -> bool | none | no |
| 37 | is_window_collapsed | mod | () -> bool | none | no |
| 38 | is_window_focused | mod | (flags:int=0) -> bool | flags | no |
| 39 | is_window_hovered | mod | (flags:int=0) -> bool | flags | no |
| 40 | is_rect_visible | mod | (size:Vec2) -> bool | vec | no |

#### LAYOUT
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 41 | separator | mod | () -> None | none | no |
| 42 | separator_text | mod | (label:str) -> None | scalar | no |
| 43 | same_line | mod | (offset_from_start_x:float=0.0, spacing:float=-1.0) -> None | scalar | no |
| 44 | spacing | mod | () -> None | none | no |
| 45 | new_line | mod | () -> None | none | no |
| 46 | dummy | mod | (size:Vec2) -> None | vec | no |
| 47 | indent | mod | (indent_w:float=0.0) -> None | scalar | no |
| 48 | unindent | mod | (indent_w:float=0.0) -> None | scalar | no |
| 49 | align_text_to_frame_padding | mod | () -> None | none | no |
| 50 | get_frame_height | mod | () -> float | none | no |
| 51 | get_frame_height_with_spacing | mod | () -> float | none | no |
| 52 | get_font_size | mod | () -> float | none | no |

#### FONT switching / scaling
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 53 | push_font | mod | (font_index:int=0) -> None | scalar | no |
| 54 | pop_font | mod | () -> None | none | no |
| 55 | push_font_scaled | mod | (font_index:int, scale:float=1.0) -> None | scalar | no |
| 56 | pop_font_scaled | mod | () -> None | none | no |
| 57 | push_style_font | mod | (style:int, size:float=0.0) -> None | scalar | no | **native-only; not in PyImGui.pyi** |
| 58 | push_font_size | mod | (size:float) -> None | scalar | no | **native-only** |
| 59 | get_global_font_scale | mod | () -> float | none | no | **native-only** |
| 60 | set_global_font_scale | mod | (scale:float) -> None | scalar | no | **native-only** |

#### TEXT
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 61 | text_unformatted | mod | (text:str, text_end:str=None) -> None | scalar | no |
| 62 | text_link | mod | (label:str) -> bool | scalar | no |
| 63 | text_link_open_url | mod | (label:str, url:str=None) -> bool | scalar | no |
| 64 | TextV | mod | (fmt:str, args:List[str]) -> None | list | no | **native-only** |
| 65 | TextColoredV | mod | (color:Vec4, fmt:str, args:List[str]) -> None | vec/list | no | **native-only** |
| 66 | TextDisabledV | mod | (fmt:str, args:List[str]) -> None | list | no | **native-only** |
| 67 | TextWrappedV | mod | (fmt:str, args:List[str]) -> None | list | no | **native-only** |
| 68 | LabelTextV | mod | (label:str, fmt:str, args:List[str]) -> None | list | no | **native-only** |
| 69 | BulletTextV | mod | (fmt:str, args:List[str]) -> None | list | no | **native-only** |
| 70 | text | mod | (text:str) -> None | scalar | no |
| 71 | text_colored | mod | (color:Vec4, text:str) -> None | vec | no |
| 72 | text_colored | mod | (r:float,g:float,b:float,a:float, text:str) -> None | scalar | no |
| 73 | text_colored | mod | (text:str, color:Vec4) -> None (legacy order) | vec | no |
| 74 | text_disabled | mod | (text:str) -> None | scalar | no |
| 75 | text_wrapped | mod | (text:str) -> None | scalar | no |
| 76 | bullet_text | mod | (text:str) -> None | scalar | no |
| 77 | label_text | mod | (label:str, text:str) -> None | scalar | no |

#### WIDGETS
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 78 | button | mod | (label:str, size:Vec2=(0,0)) -> bool | vec | no |
| 79 | button | mod | (label:str, width:float=0.0, height:float=0.0) -> bool | scalar | no |
| 80 | small_button | mod | (label:str) -> bool | scalar | no |
| 81 | invisible_button | mod | (str_id:str, size:Vec2, flags:int=0) -> bool | vec/flags | no |
| 82 | arrow_button | mod | (str_id:str, dir:int) -> bool | scalar | no |
| 83 | checkbox | mod | (label:str, value:bool) -> bool (returns new state) | scalar | no |
| 84 | radio_button | mod | (label:str, value:int, v_button:int) -> int | scalar | no |
| 85 | progress_bar | mod | (fraction:float, size_arg_x:float=-1.0, size_arg_y:float=0.0, overlay:str=None) -> None | scalar | no |
| 86 | bullet | mod | () -> None | none | no |
| 87 | checkbox_flags | mod | (label:str, flags:int, flags_value:int) -> int | flags | no |

#### SLIDERS
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 88 | slider_float | mod | (label, v:float, v_min, v_max, format="%.3f", flags=0) -> float | scalar | no |
| 89 | slider_int | mod | (label, v:int, v_min, v_max, format="%d", flags=0) -> int | scalar | no |
| 90 | slider_angle | mod | (label, v_rad, v_degrees_min=-360, v_degrees_max=360, format="%.0f deg", flags=0) -> float | scalar | no |
| 91 | v_slider_float | mod | (label, size:Vec2, v, v_min, v_max, format="%.3f", flags=0) -> float | vec/scalar | no |
| 92 | v_slider_int | mod | (label, size:Vec2, v, v_min, v_max, format="%d", flags=0) -> int | vec/scalar | no |
| 93 | slider_float2 | mod | (label, v:(f,f), v_min, v_max, format, flags) -> tuple2 | array | tuple |
| 94 | slider_float3 | mod | (label, v:(f,f,f), ...) -> tuple3 | array | tuple |
| 95 | slider_float4 | mod | (label, v:(f,f,f,f), ...) -> tuple4 | array | tuple |
| 96 | slider_int2 | mod | (label, v:(i,i), ...) -> tuple2 | array | tuple |
| 97 | slider_int3 | mod | (label, v:(i,i,i), ...) -> tuple3 | array | tuple |
| 98 | slider_int4 | mod | (label, v:(i,i,i,i), ...) -> tuple4 | array | tuple |

#### DRAGS
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 99 | drag_float | mod | (label, v, v_speed=1, v_min=0, v_max=0, format="%.3f", flags=0) -> float | scalar | no |
| 100 | drag_float_range2 | mod | (label, v_current_min, v_current_max, v_speed, v_min, v_max, format, format_max=None, flags) -> tuple2 | scalar | tuple |
| 101 | drag_int | mod | (label, v, v_speed=1, v_min=0, v_max=0, format="%d", flags=0) -> int | scalar | no |
| 102 | drag_int_range2 | mod | (label, v_current_min, v_current_max, ...) -> tuple2 | scalar | tuple |
| 103 | drag_float2 | mod | (label, v:(f,f), v_speed, v_min, v_max, format, flags) -> tuple2 | array | tuple |
| 104 | drag_float3 | mod | (label, v:(f,f,f), ...) -> tuple3 | array | tuple |
| 105 | drag_float4 | mod | (label, v:(f,f,f,f), ...) -> tuple4 | array | tuple |
| 106 | drag_int2 | mod | (label, v:(i,i), ...) -> tuple2 | array | tuple |
| 107 | drag_int3 | mod | (label, v:(i,i,i), ...) -> tuple3 | array | tuple |
| 108 | drag_int4 | mod | (label, v:(i,i,i,i), ...) -> tuple4 | array | tuple |

#### INPUT
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 109 | input_float | mod | (label, v, step=0, step_fast=0, format="%.3f", flags=0) -> float | scalar | no |
| 110 | input_float2 | mod | (label, v:(f,f), format, flags) -> tuple2 | array | tuple |
| 111 | input_float3 | mod | (label, v:(f,f,f), ...) -> tuple3 | array | tuple |
| 112 | input_float4 | mod | (label, v:(f,f,f,f), ...) -> tuple4 | array | tuple |
| 113 | input_int | mod | (label, v, step=1, step_fast=100, flags=0) -> int | scalar | no |
| 114 | input_int2 | mod | (label, v:(i,i), flags) -> tuple2 | array | tuple |
| 115 | input_int3 | mod | (label, v:(i,i,i), flags) -> tuple3 | array | tuple |
| 116 | input_int4 | mod | (label, v:(i,i,i,i), flags) -> tuple4 | array | tuple |
| 117 | input_double | mod | (label, v, step=0, step_fast=0, format="%.6f", flags=0) -> float | scalar | no |
| 118 | input_text | mod | (label, text="", flags=0) -> str (256-byte buf) | scalar | no |
| 119 | input_text_with_hint | mod | (label, hint, text="", flags=0) -> str (256-byte buf) | scalar | no |
| 120 | input_text_multiline | mod | (label, text="", size:Vec2=(0,0), flags=0) -> str (2048-byte buf) | vec | no |

#### COMBO / LIST BOX
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 121 | begin_combo | mod | (label, preview_value, flags=0) -> bool | scalar | no |
| 122 | end_combo | mod | () -> None | none | no |
| 123 | combo | mod | (label, current_item:int, items:List[str]) -> int | list | no |
| 124 | begin_list_box | mod | (label, size:Vec2=(0,0)) -> bool | vec | no |
| 125 | end_list_box | mod | () -> None | none | no |
| 126 | list_box | mod | (label, current_item:int, items:List[str], height_in_items=-1) -> int | list | no |

#### SELECTABLE
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 127 | selectable | mod | (label, selected=False, flags=0, size:Vec2=(0,0)) -> bool | vec/flags | no |

#### COLOR
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 128 | color_edit3 | mod | (label, col:(f,f,f), flags=0) -> tuple3 | array | tuple |
| 129 | color_edit4 | mod | (label, col:(f,f,f,f), flags=0) -> tuple4 | array | tuple |
| 130 | color_picker3 | mod | (label, col:(f,f,f), flags=0) -> tuple3 | array | tuple |
| 131 | color_picker4 | mod | (label, col:(f,f,f,f), flags=0) -> tuple4 | array | tuple |
| 132 | color_button | mod | (desc_id, col:Vec4, flags=0, size:Vec2=(0,0)) -> bool | vec | no |
| 133 | set_color_edit_options | mod | (flags:int) -> None | flags | no |
| 134 | color_convert_u32_to_float4 | mod | (in:int) -> Vec4 | scalar | tuple/vec |
| 135 | color_convert_float4_to_u32 | mod | (in:Vec4) -> int | vec | no |
| 136 | color_convert_rgb_to_hsv | mod | (r,g,b) -> tuple3 | scalar | tuple |
| 137 | color_convert_hsv_to_rgb | mod | (h,s,v) -> tuple3 | scalar | tuple |
| 138 | get_color_u32 | mod | (idx:int, alpha_mul:float=1.0) -> int | scalar | no |
| 139 | get_color_u32_vec4 | mod | (col:Vec4) -> int | vec | no |
| 140 | get_style_color_vec4 | mod | (idx:int) -> Vec4 | scalar | tuple/vec |

#### IMAGE
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 141 | image | mod | (tex_id:int, size:Vec2, uv0=(0,0), uv1=(1,1)) -> None | vec | no |
| 142 | image_with_bg | mod | (tex_id, size, uv0, uv1, bg_col:Vec4=(0,0,0,0), tint_col:Vec4=(1,1,1,1)) -> None | vec | no |
| 143 | image_button | mod | (str_id, tex_id, size, uv0, uv1, bg_col, tint_col) -> bool | vec | no |

#### TREE / COLLAPSING
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 144 | tree_node | mod | (label:str) -> bool | scalar | no |
| 145 | tree_node_ex | mod | (label:str, flags:int=0) -> bool | flags | no |
| 146 | tree_pop | mod | () -> None | none | no |
| 147 | tree_push | mod | (str_id:str) -> None | scalar | no |
| 148 | tree_push_ptr | mod | (ptr_id:int) -> None | scalar | no |
| 149 | get_tree_node_to_label_spacing | mod | () -> float | none | no |
| 150 | set_next_item_open | mod | (is_open:bool, cond:int=0) -> None | scalar | no |
| 151 | set_next_item_storage_id | mod | (storage_id:int) -> None | scalar | no |
| 152 | tree_node_get_open | mod | (storage_id:int) -> bool | scalar | no |
| 153 | collapsing_header | mod | (label:str, flags:int=0) -> bool | flags | no |

#### TABS
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 154 | begin_tab_bar | mod | (str_id, flags=0) -> bool | flags | no |
| 155 | end_tab_bar | mod | () -> None | none | no |
| 156 | begin_tab_item | mod | (label, p_open=None, flags=0) -> bool | scalar | no |
| 157 | begin_tab_item_closable | mod | (label, p_open:bool=True, flags=0) -> tuple(bool,bool) | scalar | tuple |
| 158 | end_tab_item | mod | () -> None | none | no |
| 159 | tab_item_button | mod | (label, flags=0) -> bool | flags | no |
| 160 | set_tab_item_closed | mod | (tab_or_docked_window_label:str) -> None | scalar | no |

#### TABLES
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 161 | begin_table | mod | (str_id, column:int, flags=0, outer_size:Vec2=(0,0), inner_width=0.0) -> bool | vec/flags | no |
| 162 | begin_table | mod | (str_id, column:int, flags=0, width=0.0, height=0.0) -> bool | scalar | no |
| 163 | end_table | mod | () -> None | none | no |
| 164 | table_next_row | mod | (row_flags=0, min_row_height=0.0) -> None | flags | no |
| 165 | table_next_column | mod | () -> bool | none | no |
| 166 | table_set_column_index | mod | (column_n:int) -> bool | scalar | no |
| 167 | table_setup_column | mod | (label, flags=0, init_width_or_weight=0.0, user_id=0) -> None | flags | no |
| 168 | table_setup_scroll_freeze | mod | (cols:int, rows:int) -> None | scalar | no |
| 169 | table_headers_row | mod | () -> None | none | no |
| 170 | table_header | mod | (label:str) -> None | scalar | no |
| 171 | table_angled_headers_row | mod | () -> None | none | no |
| 172 | table_get_column_count | mod | () -> int | none | no |
| 173 | table_get_column_index | mod | () -> int | none | no |
| 174 | table_get_row_index | mod | () -> int | none | no |
| 175 | table_get_column_name | mod | (column_n:int=-1) -> str | scalar | no |
| 176 | table_get_column_flags | mod | (column_n:int=-1) -> int | scalar | no |
| 177 | table_get_hovered_column | mod | () -> int | none | no |
| 178 | table_set_column_enabled | mod | (column_n:int, v:bool) -> None | scalar | no |
| 179 | table_set_bg_color | mod | (target:int, color:int, column_n:int=-1) -> None | scalar | no |
| 180 | table_get_sort_specs | mod | () -> Optional[TableSortSpecs] (by ref) | none | **class** |
| 181 | clear_sort_specs_dirty | mod | (specs) -> None | obj | no |

#### LEGACY COLUMNS
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 182 | columns | mod | (count:int=1, id:str=None, borders:bool=True) -> None | scalar | no |
| 183 | next_column | mod | () -> None | none | no |
| 184 | end_columns | mod | () -> None (resets to 1 col) | none | no |
| 185 | set_column_width | mod | (column_index:int, width:float) -> None | scalar | no |
| 186 | set_column_offset | mod | (column_index:int, offset_x:float) -> None | scalar | no |
| 187 | get_column_index | mod | () -> int | none | no |
| 188 | get_column_width | mod | (column_index:int=-1) -> float | scalar | no |
| 189 | get_column_offset | mod | (column_index:int=-1) -> float | scalar | no |
| 190 | get_columns_count | mod | () -> int | none | no |

#### MENUS
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 191 | begin_menu_bar | mod | () -> bool | none | no |
| 192 | end_menu_bar | mod | () -> None | none | no |
| 193 | begin_main_menu_bar | mod | () -> bool | none | no |
| 194 | end_main_menu_bar | mod | () -> None | none | no |
| 195 | begin_menu | mod | (label, enabled:bool=True) -> bool | scalar | no |
| 196 | end_menu | mod | () -> None | none | no |
| 197 | menu_item | mod | (label, shortcut=None, selected=False, enabled=True) -> bool | scalar | no |

#### POPUPS / TOOLTIPS
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 198 | open_popup | mod | (str_id, popup_flags=0) -> None | flags | no |
| 199 | open_popup_on_item_click | mod | (str_id=None, popup_flags=0) -> None | flags | no |
| 200 | begin_popup | mod | (str_id, flags=0) -> bool | flags | no |
| 201 | end_popup | mod | () -> None | none | no |
| 202 | end_popup_modal | mod | () -> None (alias to EndPopup) | none | no |
| 203 | begin_popup_modal | mod | (name, p_open=None, flags=0) -> bool | scalar | no |
| 204 | close_current_popup | mod | () -> None | none | no |
| 205 | begin_popup_context_item | mod | (str_id=None, popup_flags=0) -> bool | flags | no |
| 206 | begin_popup_context_window | mod | (str_id=None, popup_flags=0) -> bool | flags | no |
| 207 | begin_popup_context_void | mod | (str_id=None, popup_flags=0) -> bool | flags | no |
| 208 | is_popup_open | mod | (str_id, flags=0) -> bool | flags | no |
| 209 | begin_tooltip | mod | () -> None (bool in ImGui) | none | no |
| 210 | end_tooltip | mod | () -> None | none | no |
| 211 | set_tooltip | mod | (fmt:str) -> None | scalar | no |
| 212 | show_tooltip | mod | (text:str) -> None (guards IsItemHovered) | scalar | no |
| 213 | begin_item_tooltip | mod | () -> None | none | no |
| 214 | set_item_tooltip | mod | (fmt:str) -> None | scalar | no |

#### CURSOR
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 215 | get_cursor_pos | mod | () -> Vec2 | none | tuple/vec |
| 216 | set_cursor_pos | mod | (local_pos:Vec2) -> None | vec | no |
| 217 | get_cursor_pos_x | mod | () -> float | none | no |
| 218 | set_cursor_pos_x | mod | (local_x:float) -> None | scalar | no |
| 219 | get_cursor_pos_y | mod | () -> float | none | no |
| 220 | set_cursor_pos_y | mod | (local_y:float) -> None | scalar | no |
| 221 | get_cursor_screen_pos | mod | () -> Vec2 | none | tuple/vec |
| 222 | set_cursor_screen_pos | mod | (pos:Vec2) -> None | vec | no |
| 223 | get_cursor_start_pos | mod | () -> Vec2 | none | tuple/vec |

#### SCROLLING
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 224 | get_scroll_x | mod | () -> float | none | no |
| 225 | get_scroll_y | mod | () -> float | none | no |
| 226 | get_scroll_max_x | mod | () -> float | none | no |
| 227 | get_scroll_max_y | mod | () -> float | none | no |
| 228 | set_scroll_x | mod | (scroll_x:float) -> None | scalar | no |
| 229 | set_scroll_y | mod | (scroll_y:float) -> None | scalar | no |
| 230 | set_scroll_here_x | mod | (center_x_ratio:float=0.5) -> None | scalar | no |
| 231 | set_scroll_here_y | mod | (center_y_ratio:float=0.5) -> None | scalar | no |
| 232 | set_scroll_from_pos_x | mod | (local_x, center_x_ratio=0.5) -> None | scalar | no |
| 233 | set_scroll_from_pos_y | mod | (local_y, center_y_ratio=0.5) -> None | scalar | no |

#### ITEM QUERY
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 234 | is_item_hovered | mod | (flags:int=0) -> bool | flags | no |
| 235 | is_item_active | mod | () -> bool | none | no |
| 236 | is_item_focused | mod | () -> bool | none | no |
| 237 | is_item_clicked | mod | (mouse_button:int=0) -> bool | scalar | no |
| 238 | is_item_visible | mod | () -> bool | none | no |
| 239 | is_item_edited | mod | () -> bool | none | no |
| 240 | is_item_activated | mod | () -> bool | none | no |
| 241 | is_item_deactivated | mod | () -> bool | none | no |
| 242 | is_item_deactivated_after_edit | mod | () -> bool | none | no |
| 243 | is_item_toggled_open | mod | () -> bool | none | no |
| 244 | is_any_item_hovered | mod | () -> bool | none | no |
| 245 | is_any_item_active | mod | () -> bool | none | no |
| 246 | is_any_item_focused | mod | () -> bool | none | no |
| 247 | get_item_id | mod | () -> int | none | no |
| 248 | get_item_rect_min | mod | () -> Vec2 | none | tuple/vec |
| 249 | get_item_rect_max | mod | () -> Vec2 | none | tuple/vec |
| 250 | get_item_rect_size | mod | () -> Vec2 | none | tuple/vec |
| 251 | get_item_flags | mod | () -> int | none | no |
| 252 | set_item_default_focus | mod | () -> None | none | no |
| 253 | set_nav_cursor_visible | mod | (visible:bool) -> None | scalar | no |
| 254 | set_next_item_width | mod | (item_width:float) -> None | scalar | no |
| 255 | set_next_item_allow_overlap | mod | () -> None | none | no |

#### ID / FOCUS
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 256 | push_id | mod | (str_id:str) -> None | scalar | no |
| 257 | push_id_int | mod | (int_id:int) -> None | scalar | no |
| 258 | pop_id | mod | () -> None | none | no |
| 259 | get_id | mod | (str_id:str) -> int | scalar | no |
| 260 | get_id_int | mod | (int_id:int) -> int | scalar | no |
| 261 | set_keyboard_focus_here | mod | (offset:int=0) -> None | scalar | no |

#### KEYBOARD
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 262 | is_key_down | mod | (key:int) -> bool (ImGuiKey code) | scalar | no |
| 263 | is_key_pressed | mod | (key:int, repeat:bool=True) -> bool | scalar | no |
| 264 | is_key_released | mod | (key:int) -> bool | scalar | no |
| 265 | is_key_chord_pressed | mod | (key_chord:int) -> bool | scalar | no |
| 266 | get_key_name | mod | (key:int) -> str | scalar | no |
| 267 | get_key_pressed_amount | mod | (key:int, repeat_delay:float, rate:float) -> int | scalar | no |
| 268 | set_next_frame_want_capture_keyboard | mod | (want_capture_keyboard:bool) -> None | scalar | no |
| 269 | shortcut | mod | (key_chord:int, flags:int=0) -> bool | flags | no |
| 270 | set_next_item_shortcut | mod | (key_chord:int, flags:int=0) -> None | flags | no |
| 271 | set_item_key_owner | mod | (key:int) -> None | scalar | no |

#### MOUSE
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 272 | set_mouse_cursor | mod | (cursor_type:int) -> None | scalar | no |
| 273 | get_mouse_cursor | mod | () -> int | none | no |
| 274 | get_mouse_pos | mod | () -> Vec2 | none | tuple/vec |
| 275 | get_mouse_pos_on_opening_current_popup | mod | () -> Vec2 | none | tuple/vec |
| 276 | is_mouse_down | mod | (button:int) -> bool | scalar | no |
| 277 | is_mouse_clicked | mod | (button:int, repeat:bool=False) -> bool | scalar | no |
| 278 | is_mouse_released | mod | (button:int) -> bool | scalar | no |
| 279 | is_mouse_double_clicked | mod | (button:int) -> bool | scalar | no |
| 280 | is_mouse_released_with_delay | mod | (button:int, delay:float) -> bool | scalar | no |
| 281 | is_mouse_dragging | mod | (button:int, lock_threshold:float=-1.0) -> bool | scalar | no |
| 282 | is_mouse_hovering_rect | mod | (r_min:Vec2, r_max:Vec2, clip:bool=True) -> bool | vec | no |
| 283 | is_any_mouse_down | mod | () -> bool | none | no |
| 284 | is_mouse_pos_valid | mod | (mouse_pos:Vec2=(-FLT_MAX,-FLT_MAX)) -> bool | vec | no |
| 285 | get_mouse_clicked_count | mod | (button:int) -> int | scalar | no |
| 286 | get_mouse_drag_delta | mod | (button:int=0, lock_threshold:float=-1.0) -> Vec2 | scalar | tuple/vec |
| 287 | reset_mouse_drag_delta | mod | (button:int=0) -> None | scalar | no |
| 288 | set_next_frame_want_capture_mouse | mod | (want_capture_mouse:bool) -> None | scalar | no |

#### STYLE (push/pop)
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 289 | push_style_color | mod | (idx:int, col:Vec4) -> None | vec | no |
| 290 | push_style_color_u32 | mod | (idx:int, col_u32:int) -> None | scalar | no |
| 291 | pop_style_color | mod | (count:int=1) -> None | scalar | no |
| 292 | push_style_var | mod | (idx:int, val:float) -> None | scalar | no |
| 293 | push_style_var_vec2 | mod | (idx:int, val:Vec2) -> None | vec | no |
| 294 | push_style_var_x | mod | (idx:int, val_x:float) -> None | scalar | no |
| 295 | push_style_var_y | mod | (idx:int, val_y:float) -> None | scalar | no |
| 296 | pop_style_var | mod | (count:int=1) -> None | scalar | no |
| 297 | push_item_flag | mod | (option:int, enabled:bool) -> None | scalar | no |
| 298 | pop_item_flag | mod | () -> None | none | no |
| 299 | push_item_width | mod | (item_width:float) -> None | scalar | no |
| 300 | pop_item_width | mod | () -> None | none | no |
| 301 | calc_item_width | mod | () -> float | none | no |
| 302 | push_text_wrap_pos | mod | (wrap_local_pos_x:float=0.0) -> None | scalar | no |
| 303 | pop_text_wrap_pos | mod | () -> None | none | no |
| 304 | push_button_repeat | mod | (repeat:bool) -> None | scalar | no |
| 305 | pop_button_repeat | mod | () -> None | none | no |
| 306 | style_colors_dark | mod | (dst=None) -> None | obj | no |
| 307 | style_colors_light | mod | (dst=None) -> None | obj | no |
| 308 | style_colors_classic | mod | (dst=None) -> None | obj | no |
| 309 | get_style_color_name | mod | (idx:int) -> str | scalar | no |

#### CLIP RECT (module-level)
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 310 | push_clip_rect | mod | (clip_rect_min:Vec2, clip_rect_max:Vec2, intersect_with_current_clip_rect:bool) -> None | vec | no |
| 311 | push_clip_rect | mod | (x, y, width, height, intersect) -> None | scalar | no |
| 312 | pop_clip_rect | mod | () -> None | none | no |

#### FONT metrics
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 313 | get_text_line_height | mod | () -> float | none | no |
| 314 | get_text_line_height_with_spacing | mod | () -> float | none | no |
| 315 | calc_text_size | mod | (text, text_end=None, hide_text_after_double_hash=False, wrap_width=-1.0) -> Vec2 | scalar | tuple/vec |
| 316 | get_font | mod | () -> Any (ImFont by ref) | none | obj |
| 317 | get_font_tex_uv_white_pixel | mod | () -> Vec2 | none | tuple/vec |
| 318 | set_window_font_scale | mod | (s:float) -> None (OBSOLETE no-op) | scalar | no |

#### CLIPBOARD / LOG / TIME
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 319 | get_clipboard_text | mod | () -> str | none | no |
| 320 | set_clipboard_text | mod | (text:str) -> None | scalar | no |
| 321 | log_to_tty | mod | (auto_open_depth:int=-1) -> None | scalar | no |
| 322 | log_to_file | mod | (auto_open_depth=-1, filename=None) -> None | scalar | no |
| 323 | log_to_clipboard | mod | (auto_open_depth=-1) -> None | scalar | no |
| 324 | log_buttons | mod | () -> None | none | no |
| 325 | log_finish | mod | () -> None | none | no |
| 326 | get_time | mod | () -> float | none | no |
| 327 | get_frame_count | mod | () -> int | none | no |

#### INI
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 328 | load_ini_settings_from_disk | mod | (ini_filename:str) -> None | scalar | no |
| 329 | load_ini_settings_from_memory | mod | (ini_data:str, ini_size:int=0) -> None | scalar | no |
| 330 | save_ini_settings_to_disk | mod | (ini_filename:str) -> None | scalar | no |
| 331 | save_ini_settings_to_memory | mod | () -> str | none | no |

#### DRAG & DROP
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 332 | begin_drag_drop_source | mod | (flags:int=0) -> bool | flags | no |
| 333 | set_drag_drop_payload | mod | (type:str, data:Any, sz:int, cond:int=0) -> bool | obj | no |
| 334 | end_drag_drop_source | mod | () -> None | none | no |
| 335 | begin_drag_drop_target | mod | () -> bool | none | no |
| 336 | accept_drag_drop_payload | mod | (type:str, flags:int=0) -> Any (by ref) | flags | obj |
| 337 | end_drag_drop_target | mod | () -> None | none | no |
| 338 | get_drag_drop_payload | mod | () -> Any (by ref) | none | obj |

#### DOCKING / VIEWPORT (module-level in imgui_bindings.cpp; toggles from PY4GW::imgui)
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 339 | is_docking_enabled | mod | () -> bool | none | no |
| 340 | set_docking_enabled | mod | (enabled:bool) -> None | scalar | no |
| 341 | is_multi_viewport_enabled | mod | () -> bool | none | no |
| 342 | set_multi_viewport_enabled | mod | (enabled:bool) -> None | scalar | no |
| 343 | has_multi_viewport_support | mod | () -> bool | none | no |
| 344 | get_main_viewport | mod | () -> Any (by ref) | none | obj |
| 345 | get_window_viewport | mod | () -> Any (by ref) | none | obj |
| 346 | get_window_dpi_scale | mod | () -> float | none | no |

#### PLOTTING
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 347 | plot_lines | mod | (label, values:List[float], values_offset=0, overlay_text=None, scale_min=FLT_MAX, scale_max=FLT_MAX, graph_size:Vec2=(0,0)) -> None | list/vec | no |
| 348 | plot_histogram | mod | (label, values:List[float], ...) -> None | list/vec | no |
| 349 | value_bool | mod | (prefix:str, v:bool) -> None | scalar | no |
| 350 | value_int | mod | (prefix:str, v:int) -> None | scalar | no |
| 351 | value_uint | mod | (prefix:str, v:int) -> None | scalar | no |
| 352 | value_float | mod | (prefix:str, v:float, float_format=None) -> None | scalar | no |

#### DEBUG
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 353 | show_demo_window | mod | () -> None | none | no |
| 354 | show_metrics_window | mod | () -> None | none | no |
| 355 | show_debug_log_window | mod | () -> None | none | no |
| 356 | show_id_stack_tool_window | mod | () -> None | none | no |
| 357 | show_about_window | mod | () -> None | none | no |
| 358 | show_style_editor | mod | () -> None | none | no |
| 359 | show_style_selector | mod | (label:str) -> None | scalar | no |
| 360 | show_font_selector | mod | (label:str) -> None | scalar | no |
| 361 | show_user_guide | mod | () -> None | none | no |
| 362 | get_version | mod | () -> str | none | no |
| 363 | debug_flash_style_color | mod | (idx:int) -> None | scalar | no |
| 364 | debug_start_item_picker | mod | () -> None | none | no |
| 365 | debug_text_encoding | mod | (text:str) -> None | scalar | no |

#### MULTI-SELECT
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 366 | begin_multi_select | mod | (flags:int=0, selection_size:int=-1, items_count:int=-1) -> bool | flags | no |
| 367 | end_multi_select | mod | () -> None | none | no |

#### types.cpp — color helpers (module-level)
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 368 | color | mod | (r,g,b,a=1.0) -> int (pack 0..1 floats -> 0xAABBGGRR ImU32) | scalar | no | **native-only; not in stub** |
| 369 | color_u32 | mod | (r,g,b,a=255) -> int (pack 0..255 ints -> ImU32) | scalar | no | **native-only; not in stub** |

#### style.cpp — module-level
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 370 | get_style | mod | () -> ImGuiStyle (live, by ref) | none | **class** |

#### io.cpp — module-level
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 371 | get_io | mod | () -> ImGuiIO handle | none | **class** |

#### drawlist.cpp — module-level accessors + flat legacy helpers
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 372 | get_window_draw_list | mod | () -> DrawList (by ref) | none | **class** |
| 373 | get_foreground_draw_list | mod | () -> DrawList (by ref) | none | **class** |
| 374 | get_background_draw_list | mod | () -> DrawList (by ref) | none | **class** |
| 375 | draw_list_add_line | mod | (x1,y1,x2,y2,col,thickness=1.0) -> None | scalar | no |
| 376 | draw_list_add_rect | mod | (x1,y1,x2,y2,col,rounding=0,rounding_corners_flags=0,thickness=1.0) -> None | scalar | no |
| 377 | draw_list_add_rect_filled | mod | (x1,y1,x2,y2,col,rounding=0,rounding_corners_flags=0) -> None | scalar | no |
| 378 | draw_list_add_circle | mod | (x,y,radius,col,num_segments=0,thickness=1.0) -> None | scalar | no |
| 379 | draw_list_add_circle_filled | mod | (x,y,radius,col,num_segments=0) -> None | scalar | no |
| 380 | draw_list_add_text | mod | (x,y,col,text) -> None | scalar | no |
| 381 | draw_list_add_triangle | mod | (x1,y1,x2,y2,x3,y3,col,thickness=1.0) -> None | scalar | no |
| 382 | draw_list_add_triangle_filled | mod | (x1,y1,x2,y2,x3,y3,col) -> None | scalar | no |
| 383 | draw_list_add_quad | mod | (x1..y4,col,thickness=1.0) -> None | scalar | no |
| 384 | draw_list_add_quad_filled | mod | (x1..y4,col) -> None | scalar | no |

#### docking.cpp — module-level (register_docking)
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 385 | dock_space | mod | (id:int, size:Vec2=(0,0), flags:int=0) -> int | vec/flags | no |
| 386 | dock_space_over_viewport | mod | (dockspace_id:int=0, flags:int=0) -> int | flags | no |
| 387 | set_next_window_dock_id | mod | (dock_id:int, cond:int=0) -> None | scalar | no |
| 388 | get_window_dock_id | mod | () -> int | none | no |
| 389 | is_window_docked | mod | () -> bool | none | no |
| 390 | dock_builder_dock_window | mod | (window_name:str, node_id:int) -> None | scalar | no |
| 391 | dock_builder_add_node | mod | (node_id:int=0, flags:int=0) -> int | flags | no |
| 392 | dock_builder_remove_node | mod | (node_id:int) -> None | scalar | no |
| 393 | dock_builder_remove_node_child_nodes | mod | (node_id:int) -> None | scalar | no |
| 394 | dock_builder_remove_node_docked_windows | mod | (node_id:int, clear_settings_refs:bool=True) -> None | scalar | no |
| 395 | dock_builder_set_node_pos | mod | (node_id:int, pos:Vec2) -> None | vec | no |
| 396 | dock_builder_set_node_size | mod | (node_id:int, size:Vec2) -> None | vec | no |
| 397 | dock_builder_split_node | mod | (node_id, split_dir:int, size_ratio_for_node_at_dir:float) -> tuple(int,int) | scalar | tuple |
| 398 | dock_builder_finish | mod | (node_id:int) -> None | scalar | no |

#### addons.cpp — submodule free functions
| # | Name | Owner | Signature | Arg cat | Returns-struct |
|---|------|-------|-----------|---------|----------------|
| 399 | hotkey.edit | PyImGui.hotkey | (hotkeys:list[HotKey], popup_label:str) -> None | list/obj | no |
| 400 | hotkey.key_lib | PyImGui.hotkey | (keys:int) -> str | scalar | no |
| 401 | markdown.render | PyImGui.markdown | (text:str) -> None | scalar | no |
| 402 | anim.update_begin_frame | PyImGui.anim | () -> None | none | no |
| 403 | anim.gc | PyImGui.anim | (max_age_frames:int=600) -> None | scalar | no |
| 404 | anim.set_global_time_scale | PyImGui.anim | (scale:float) -> None | scalar | no |
| 405 | anim.get_global_time_scale | PyImGui.anim | () -> float | none | no |
| 406 | anim.tween_float | PyImGui.anim | (id, channel_id, target, duration, ease=OutCubic, policy=Crossfade, dt=0.0, init_value=0.0) -> float | scalar/flags | no |
| 407 | anim.oscillate | PyImGui.anim | (id, amplitude, frequency, wave_type=0, phase=0.0, dt=0.0) -> float | scalar | no |

---

### Bound classes / struct types & fields

| Struct/Class | Member | Type | Binding kind |
|--------------|--------|------|--------------|
| **Vec2** (`ImVec2`, types.cpp) | x | float | def_readwrite |
| | y | float | def_readwrite |
| | __init__ | ()/(x,y)/(sequence) | init | 
| | __len__/__getitem__/__iter__/__repr__/__eq__ | — | dunder | 
| **Vec4** (`ImVec4`) | x,y,z,w | float | def_readwrite (4) |
| | __init__ | ()/(x,y,z,w)/(sequence) | init |
| | __len__/__getitem__/__iter__/__repr__ | — | dunder |
| **TableColumnSortSpecs** (`ImGuiTableColumnSortSpecs`) | ColumnIndex | int | def_property_readonly |
| | SortDirection | int | def_property_readonly |
| **TableSortSpecs** (`ImGuiTableSortSpecs`) | SpecsCount | int | def_readonly |
| | SpecsDirty | bool | def_readonly |
| | Specs | TableColumnSortSpecs (by ref) | def_property_readonly |
| **ImGuiStyle** (live, style.cpp) | Alpha, DisabledAlpha | float | def_readwrite |
| | FontSizeBase, FontScaleMain, FontScaleDpi | float | def_readwrite (1.92 font scaling) |
| | WindowPadding | Vec2 | def_readwrite |
| | WindowRounding, WindowBorderSize | float | def_readwrite |
| | WindowMinSize, WindowTitleAlign | Vec2 | def_readwrite |
| | WindowMenuButtonPosition | int/ImGuiDir | def_readwrite |
| | ChildRounding, ChildBorderSize | float | def_readwrite |
| | PopupRounding, PopupBorderSize | float | def_readwrite |
| | FramePadding | Vec2 | def_readwrite |
| | FrameRounding, FrameBorderSize | float | def_readwrite |
| | ItemSpacing, ItemInnerSpacing, CellPadding, TouchExtraPadding | Vec2 | def_readwrite |
| | IndentSpacing, ColumnsMinSpacing, ScrollbarSize, ScrollbarRounding, GrabMinSize, GrabRounding, LogSliderDeadzone | float | def_readwrite |
| | TabRounding, TabBorderSize, TabCloseButtonMinWidthUnselected | float | def_readwrite |
| | ColorButtonPosition | int/ImGuiDir | def_readwrite |
| | ButtonTextAlign, SelectableTextAlign | Vec2 | def_readwrite |
| | SeparatorTextBorderSize | float | def_readwrite |
| | SeparatorTextAlign, SeparatorTextPadding | Vec2 | def_readwrite |
| | DisplayWindowPadding, DisplaySafeAreaPadding | Vec2 | def_readwrite |
| | MouseCursorScale | float | def_readwrite |
| | AntiAliasedLines, AntiAliasedLinesUseTex, AntiAliasedFill | bool | def_readwrite |
| | CurveTessellationTol, CircleTessellationMaxError | float | def_readwrite |
| | HoverStationaryDelay, HoverDelayShort, HoverDelayNormal | float | def_readwrite |
| | HoverFlagsForTooltipMouse, HoverFlagsForTooltipNav | int | def_readwrite |
| | get_color(idx)->Vec4, set_color(idx,col), ScaleAllSizes(scale), __init__() | — | methods |
| **StyleConfig** (snapshot editor, style.cpp) | Pull(), Push(), Reset() | — | methods |
| | Alpha, DisabledAlpha | float | def_readwrite |
| | WindowPadding, WindowMinSize, WindowTitleAlign | array2 | def_readwrite |
| | WindowRounding, WindowBorderSize | float | def_readwrite |
| | WindowMenuButtonPosition | int | def_readwrite |
| | ChildRounding, ChildBorderSize, PopupRounding, PopupBorderSize | float | def_readwrite |
| | FramePadding | array2 | def_readwrite |
| | FrameRounding, FrameBorderSize | float | def_readwrite |
| | ItemSpacing, ItemInnerSpacing, CellPadding, TouchExtraPadding | array2 | def_readwrite |
| | IndentSpacing, ColumnsMinSpacing, ScrollbarSize, ScrollbarRounding, GrabMinSize, GrabRounding, LogSliderDeadzone | float | def_readwrite |
| | TabRounding, TabBorderSize, TabCloseButtonMinWidthUnselected, SeparatorTextBorderSize | float | def_readwrite |
| | ColorButtonPosition | int | def_readwrite |
| | ButtonTextAlign, SelectableTextAlign, SeparatorTextAlign, SeparatorTextPadding | array2 | def_readwrite |
| | DisplayWindowPadding, DisplaySafeAreaPadding | array2 | def_readwrite |
| | MouseCursorScale | float | def_readwrite |
| | AntiAliasedLines, AntiAliasedLinesUseTex, AntiAliasedFill | bool | def_readwrite |
| | CurveTessellationTol, CircleTessellationMaxError | float | def_readwrite |
| | Colors[ImGuiCol_COUNT] | array4[] | internal (get_color/set_color accessors) |
| | get_color(idx)->tuple4, set_color(idx,r,g,b,a) | — | methods |
| **ImGuiIO** (IOHandle live view, io.cpp) | display_size | Vec2 | def_property_readonly |
| | display_size_x/_y | float | def_property_readonly |
| | delta_time, framerate | float | def_property_readonly |
| | mouse_pos | Vec2 | def_property_readonly |
| | mouse_pos_x/_y, mouse_pos_prev_x/_y | float | def_property_readonly |
| | mouse_wheel, mouse_wheel_h | float | def_property_readonly |
| | key_ctrl, key_shift, key_alt, key_super | bool | def_property_readonly |
| | want_capture_mouse, want_capture_keyboard, want_text_input, want_set_mouse_pos, want_save_ini_settings | bool | def_property_readonly |
| | backend_flags | int | def_property_readonly |
| | metrics_render_vertices, metrics_render_indices, metrics_active_windows | int | def_property_readonly |
| | config_flags | int | def_property (rw) |
| | mouse_draw_cursor | bool | def_property (rw) |
| | ini_saving_rate, mouse_double_click_time, mouse_drag_threshold | float | def_property (rw) |
| | config_docking_no_split, config_docking_with_shift, config_windows_move_from_title_bar_only, config_input_text_cursor_blink | bool | def_property (rw) |
| | config_dpi_scale_fonts, config_dpi_scale_viewports | bool | def_property (rw) — **native-only; not in stub** |
| | mouse_down(button), add_config_flag(f), remove_config_flag(f), has_config_flag(f), has_backend_flag(f) | — | methods |
| **DrawList** (`ImDrawList`, drawlist.cpp) | push_clip_rect(clip_min,clip_max,intersect=False) | — | method |
| | push_clip_rect_full_screen(), pop_clip_rect() | — | methods |
| | get_clip_rect_min()->Vec2, get_clip_rect_max()->Vec2 | — | methods |
| | add_line(p1,p2,col,thickness=1) | — | method |
| | add_line_h(min_x,max_x,y,col,thickness=1) | — | method — **native-only** |
| | add_line_v(x,min_y,max_y,col,thickness=1) | — | method — **native-only** |
| | add_rect(p_min,p_max,col,rounding=0,thickness=1,flags=0) | — | method (NB: thickness before flags — 1.92 order) |
| | add_rect_filled(p_min,p_max,col,rounding=0,flags=0) | — | method |
| | add_rect_filled_multi_color(p_min,p_max,ul,ur,br,bl) | — | method — **native-only** |
| | add_quad / add_quad_filled | — | methods |
| | add_triangle / add_triangle_filled | — | methods |
| | add_circle / add_circle_filled | — | methods |
| | add_ngon(center,radius,col,num_segments,thickness=1) / add_ngon_filled | — | methods — **native-only** |
| | add_ellipse(center,radius,col,rot=0,num_segments=0,thickness=1) / add_ellipse_filled | — | methods — **native-only** |
| | add_text(pos,col,text) | — | method |
| | add_bezier_cubic / add_bezier_quadratic | — | methods |
| | add_polyline(points,col,thickness,flags=0) | — | method |
| | add_convex_poly_filled(points,col) | — | method |
| | add_concave_poly_filled(points,col) | — | method — **native-only** |
| | path_clear, path_line_to, path_fill_convex, path_stroke | — | methods |
| | path_arc_to, path_arc_to_fast | — | methods |
| | path_elliptical_arc_to(center,radius,rot,a_min,a_max,num_segments=0) | — | method — **native-only** |
| | path_bezier_cubic_curve_to, path_bezier_quadratic_curve_to, path_rect | — | methods |
| | channels_split(count), channels_merge(), channels_set_current(n) | — | methods — **native-only (stub lacks channel API + prim_* + push/pop_texture_id + add_image*)** |
| **filebrowser.FileBrowser** (addons.cpp) | show_file_dialog(label,mode,size=(0,0),valid_types="*.*") | — | method |
| | set_current_path(path), get_current_path(), set_use_modal(modal) | — | methods |
| | selected_fn, selected_path, ext | str | def_readwrite |
| **hotkey.HotKey** (addons.cpp) | name | str | def_readwrite |
| | lib | str | def_readwrite |
| | keys | uint | def_readwrite |
| | __init__(name,lib="",keys=0), __repr__ | — | methods |
| **memory_editor.MemoryEditor** (addons.cpp) | read_only | bool | def_readwrite (ReadOnly) |
| | open | bool | def_readwrite (Open) |
| | draw_contents(data:buffer, base_addr=0) | — | method |
| | draw_window(title, data:buffer, base_addr=0) | — | method |
| **text_editor.TextEditor** (addons.cpp) | render(title,size=(0,0),border=False), set_focus() | — | methods |
| | set_text, get_text, clear_text, is_empty, get_line_count, get_line_text(line) | — | methods |
| | set_language(name), get_language_name, has_language | — | methods |
| | set_dark_palette, set_light_palette | — | methods |
| | set_read_only_enabled/is_read_only_enabled | — | methods |
| | set_show_line_numbers_enabled/is_..., set_show_whitespaces_enabled/is_... | — | methods |
| | set_auto_indent_enabled/is_..., set_tab_size/get_tab_size | — | methods |
| | cut, copy, paste, undo, redo, can_undo, can_redo | — | methods |
| | set_cursor(line,column), get_cursor_position()->tuple, select_all, select_line(line), clear_cursors | — | methods |
| | scroll_to_line(line,alignment=0) | — | method |
| | select_first/next/all_occurrence(s)_of(text,case_sensitive=True,whole_word=False) | — | methods |
| | open_find_replace_window, close_find_replace_window | — | methods |

Note: the `_FileBrowser`/`_FileBrowserModule` classes in PyImGui.pyi model the filebrowser submodule; the stub does NOT declare `hotkey`, `markdown`, `memory_editor`, `anim`, or `text_editor` submodules at all (they appear only as comment lines 938-942).

---

### Enum types

| Enum type | pybind name | Source | Notes |
|-----------|-------------|--------|-------|
| ImGuiSortDirection | SortDirection | enums.cpp | plain enum |
| ImGuiConfigFlags_ | ConfigFlags | enums.cpp | flags (bitwise ops) |
| ImGuiBackendFlags_ | BackendFlags | enums.cpp | flags |
| ImGuiWindowFlags_ | WindowFlags | enums.cpp | flags; includes fabricated `Docking` bit (1<<30) + `NoDocking` |
| ImGuiChildFlags_ | ChildFlags | enums.cpp | flags |
| ImGuiInputTextFlags_ | InputTextFlags | enums.cpp | flags; native adds CallbackResize/CallbackEdit/WordWrap |
| ImGuiTreeNodeFlags_ | TreeNodeFlags | enums.cpp | flags |
| ImGuiPopupFlags_ | PopupFlags | enums.cpp | flags |
| ImGuiSelectableFlags_ | SelectableFlags | enums.cpp | flags |
| ImGuiComboFlags_ | ComboFlags | enums.cpp | flags; aliased as `ImGuiComboFlags` |
| ImGuiTabBarFlags_ | TabBarFlags | enums.cpp | flags; native has FittingPolicyMixed/Shrink/Mask_/Default_ |
| ImGuiTabItemFlags_ | TabItemFlags | enums.cpp | flags |
| ImGuiFocusedFlags_ | FocusedFlags | enums.cpp | flags |
| ImGuiHoveredFlags_ | HoveredFlags | enums.cpp | flags (stub adds ForNavigation, native does not list it) |
| ImGuiDockNodeFlags_ | DockNodeFlags | enums.cpp | flags |
| ImGuiDragDropFlags_ | DragDropFlags | enums.cpp | flags |
| ImGuiSliderFlags_ | SliderFlags | enums.cpp | flags; native has InvalidMask_ |
| ImGuiButtonFlags_ | ButtonFlags | enums.cpp | flags |
| ImGuiTableFlags_ | TableFlags | enums.cpp | flags; native has BordersH/BordersV/NoBordersInBodyUntilResize |
| ImGuiTableColumnFlags_ | TableColumnFlags | enums.cpp | flags; native has IsEnabled/IsVisible/IsSorted/IsHovered |
| ImGuiTableRowFlags_ | TableRowFlags | enums.cpp | flags |
| ImDrawFlags_ | DrawFlags | enums.cpp | flags; native has RoundCornersDefault |
| ImGuiColorEditFlags_ | ColorEditFlags | enums.cpp | flags |
| ImGuiCond_ | ImGuiCond | enums.cpp | flags |
| ImGuiMouseButton_ | MouseButton | enums.cpp | plain enum |
| ImGuiMouseCursor_ | MouseCursor | enums.cpp | plain enum (native has Count) |
| ImGuiCol_ | ImGuiCol | enums.cpp | plain enum (color-slot indices) |
| ImGuiStyleVar_ | ImGuiStyleVar | enums.cpp | plain enum |
| ImGuiDir | Dir | docking.cpp | plain enum (split directions) |
| imgui_addons::...::DialogMode | filebrowser.DialogMode | addons.cpp | SELECT/OPEN/SAVE |
| iam_ease_type | anim.Ease | addons.cpp | Linear/InCubic/OutCubic/InOutCubic |
| iam_policy | anim.Policy | addons.cpp | Crossfade/Cut/Queue |

Total enum types: **~33** (30 in enums.cpp + Dir + filebrowser.DialogMode + anim.Ease + anim.Policy).

Extra module attribute aliases (enums.cpp): `m.attr("ImGuiComboFlags")` = ComboFlags; `m.attr("ImGuiWindowFlags_AlwaysAutoResize")` = WindowFlags.AlwaysAutoResize.

---

### Stub vs Native disagreements

**A. Two different modules.** `PyImGui.pyi` documents the real Reforged `PyImGui` embedded module. `ImGui_Py.pyi` is an auto-generated stub for a *separate, legacy `ImGui_Py` module* (the old ImGui_Legacy surface) — it is NOT a stub of PyImGui. It has different, thinner signatures (e.g. `checkbox`→bool "new state", `slider_float`→bool changed, `text_colored(label,color)`, `dummy(width,height)` scalar not vec, `push_style_color(idx,col:float)`), simpler single-param `begin`/`begin_table`/`tree_node`, and a class-style enum surface (`WindowFlags.NoTitleBar: int`). Several PyImGui functions are absent from ImGui_Py (drags, most input variants, viewport/docking, multi-select, addons) and a few ImGui_Py names have no PyImGui equivalent (`text_ex`, `push_allow_keyboard_focus`/`pop_allow_keyboard_focus`, `get_content_region_max`, `get_window_content_region_min/max`, `mouse_double_click_max_dist`/`app_focus_lost`/`ini_filename`/`log_filename`/`metrics_active_allocations` IO fields). Treat ImGui_Py.pyi as the legacy module, not as documentation of PyImGui.

**B. Native functions MISSING from PyImGui.pyi** (present in .cpp, absent in stub):
- Font: `push_style_font`, `push_font_size`, `get_global_font_scale`, `set_global_font_scale` (#57-60).
- Text format helpers: `TextV`, `TextColoredV`, `TextDisabledV`, `TextWrappedV`, `LabelTextV`, `BulletTextV` (#64-69).
- Color packing: `color`, `color_u32` (types.cpp #368-369).
- IO fields: `config_dpi_scale_fonts`, `config_dpi_scale_viewports`.
- ImGuiStyle fields: `FontSizeBase`, `FontScaleMain`, `FontScaleDpi`, `WindowMenuButtonPosition`, `LogSliderDeadzone`, `TabCloseButtonMinWidthUnselected`, `HoverStationaryDelay`, `HoverDelayShort`, `HoverDelayNormal`, `HoverFlagsForTooltipMouse`, `HoverFlagsForTooltipNav`, plus `get_color`/`set_color`/`ScaleAllSizes`/`__init__` methods — the stub only exposes a read-only `StyleConfig` view, not the live `ImGuiStyle` class.
- DrawList methods: `add_line_h`, `add_line_v`, `add_rect_filled_multi_color`, `add_ngon`, `add_ngon_filled`, `add_ellipse`, `add_ellipse_filled`, `add_concave_poly_filled`, `path_elliptical_arc_to`, `channels_split`/`channels_merge`/`channels_set_current`.
- Addon submodules entirely undeclared in stub: `hotkey`, `markdown`, `memory_editor`, `anim`, `text_editor` (and their classes/functions #399-407) — only `filebrowser` is stubbed.

**C. Stub declares members NOT in native** (stub-only, will fail at runtime):
- DrawList methods `add_image`, `add_image_rounded`, `add_image_quad`, `prim_reserve`, `prim_quad_uv`, `prim_rect`, `prim_rect_uv`, `push_texture_id`, `pop_texture_id` — declared in PyImGui.pyi (lines 115-126) but the native `register_drawlist` binds NONE of these. (Module-level `image`/`image_button`/`image_with_bg` DO exist; the DrawList-method image/prim/texture-id family does not.)
- `HoveredFlags.ForNavigation` (stub line 378) is not bound in enums.cpp.
- Stub `set_window_font_scale(s)` exists natively but is an OBSOLETE no-op (does nothing).

**D. Enum value drift** (native richer than stub): TableFlags (+BordersH/BordersV/NoBordersInBodyUntilResize), TableColumnFlags (+IsEnabled/IsVisible/IsSorted/IsHovered), InputTextFlags (+CallbackResize/CallbackEdit/WordWrap), TabBarFlags (+FittingPolicyMixed/Shrink/Mask_/Default_), SliderFlags (+InvalidMask_), DrawFlags (+RoundCornersDefault), MouseCursor (+Count). Stub `ConfigFlags` lists `NavNoCaptureKeyboard=8` which native also binds. Stub enum classes are `IntEnum` with hand-written integer values; native uses live ImGui enum constants — a value-by-value audit is advisable but spot values match.

**E. Behavioral notes worth flagging:** `begin_child` always returns True (paired end_child safety); `input_text` capped at 256 bytes, `input_text_multiline` at 2048; `begin` has 3 overloads collapsing on `p_open` type; the fabricated `WindowFlags.Docking` (1<<30) is stripped before reaching ImGui and drives opt-in docking (default = NoDocking injected).

**Totals:** ~407 bound callables (≈370 module-level free functions across imgui_bindings/types/style/io/drawlist/docking + ~9 addon submodule functions + class methods not separately numbered), 8 top-level bound classes (Vec2, Vec4, TableColumnSortSpecs, TableSortSpecs, ImGuiStyle, StyleConfig, ImGuiIO, DrawList) + 5 addon classes (FileBrowser, HotKey, MemoryEditor, TextEditor, + PyHotKey internal), ~33 enum types.


---
