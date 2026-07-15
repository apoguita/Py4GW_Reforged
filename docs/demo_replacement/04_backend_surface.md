# Backend Surface Inventory

What the demos are (or should be) exercising. Two code bases: the **Python wrapper/datasource layer** (`Py4GW_Reforged/Py4GWCoreLib`) and the **C++ Native DLL** (`Py4GW_Reforged_Native`) that publishes the `Py*` pybind11 modules. This is the target list for a "test every backend capability" tool.

---

## A. Python domain wrappers — `Py4GWCoreLib\`

Each wraps a native `Py*` binding and/or the `GLOBAL_CACHE`.

| Wrapper | Role | Backs onto |
|---|---|---|
| `Agent.py` | single-agent queries (pos, health, model, state, target) | `PyAgent` |
| `AgentArray.py` | bulk agent-array retrieval + filter/sort (allies, enemies, by distance) | derived from `PyAgent` |
| `Player.py` | local player identity/actions (movement, interact, chat) | `PyPlayer` |
| `Map.py` | map/instance info, travel, load state, mission/mini/world map, pregame, pathing | `PyMap`, `PyPathing` |
| `Inventory.py` | bag/slot model, move/stack/salvage/identify | `PyInventory` |
| `Item.py` / `ItemArray.py` | per-item data (type/mods/rarity/value/dye); item-array enumeration | `PyItem` |
| `Skill.py` | static skill data (id/type/profession/costs) | `PySkill` |
| `Skillbar.py` | live skillbar slots, recharge, use-skill | `PySkillbar` |
| `SkillManager.py` | higher-level casting/rotation orchestration | (composite) |
| `Effect.py` | buffs/effects/conditions on agents | `PyEffects` |
| `Party.py` | party/hero/henchman roster, invites | `PyParty` |
| `Merchant.py` | merchant/trader/collector transactions | `PyMerchant` |
| `Quest.py` (+`quest_data.py`) | quest log, active quest, markers | `PyQuest` |
| `Camera.py` | camera position/yaw/pitch + control | `PyCamera` |
| `Overlay.py` | ImGui overlay drawing | `PyOverlay` |
| `DXOverlay.py` | DirectX overlay primitives/text | `PyDXOverlay` |
| `Keystroke.py` | keyboard/mouse input injection | `PyKeystroke`/`PyMouse`/`PyKeyHandler` |
| `Scanner.py` | memory pattern scanner / offset resolution | `PyScanner` |
| `Pathing.py` | pathfinding / navmesh queries | `PyPathing` |
| `Dialog.py` (+`DialogCatalog.py`) | NPC dialog send/answer | `PyDialog` |
| `UIManager.py` / `GWUI.py` | native GW UI frame/element interaction | `PyUIManager` |
| `PacketSniffer.py` | STOC/CTOS packet hooks | `PyPacketSniffer` |
| `CombatEvents.py` (+`CombatEventQueue_src/`) | combat/agent event stream | `PyAgentEvents`/`PyListeners` |
| `Context.py` | high-level context accessor bridging `native_src/context` | contexts |
| `Routines.py` (+`routines_src/`) | reusable action routines/yield helpers | composite |
| `Botting*.py`, `BuildMgr.py`, `HotkeyManager.py`, `EnemyBlacklist.py`, `Database.py` | frameworks (FSM/BT, builds, hotkeys, persistence) | composite |
| `ImGui.py` / `ImGui_Legacy.py` | new + legacy ImGui facades | `PyImGui` |
| `Py4GWcorelib.py` (+`py4gwcorelib_src/`) | core utils (Timer, Color, ConsoleLog, Vector) | — |
| `enums.py`, `model_data.py`, `item_data/`, `quest_data.py` | static data tables / enums | — |

> Note: there is **no** standalone `Trading.py`. `GLOBAL_CACHE.Trading` routes to `Merchant.py`/`PyMerchant`; player-to-player trade is a separate `PyTrade` (native `src/GW/trade/`) with no dedicated wrapper.

## B. `native_src\context\` — ctypes struct readers (the "Context path")

Direct ctypes reads over GW memory (bypassing the binding methods):
`AgentContext`, `AccAgentContext`, `GameContext`, `GameplayContext`, `CharContext`, `WorldContext`, `WorldMapContext`, `MissionMapContext`, `MapContext`, `PartyContext`, `InstanceInfoContext`, `ServerRegionContext`, `GuildContext`, `CinematicContext`, `TextContext`, `PreGameContext`, `AvailableCharacterContext`.

DEMO v2 is the first to test this path (`AgentStruct`, pregame `GetContextStruct()`); v1 does not touch it.

## C. `GlobalCache\` — the `GLOBAL_CACHE` cached consumer layer

- `GlobalCache.py` — central façade; `SharedMemory.py` (+`shared_memory_src/`) — transport.
- Sub-caches: `AgentCache*`, `PartyCache`, `SkillbarCache`, `SkillCache`, `EffectCache`, `InventoryCache`, `ItemCache`, `MerchantCache`, `QuestCache`, `CameraCache`.
- `Whiteboard`/`WhiteboardLocks` — cross-script shared state; `HexRemovalPriority`.
- `shared_memory_src/` publishes ctypes structs into shared memory (AgentDataStruct, AgentPartyStruct, AllAccounts/AccountStruct, Attributes/Buff/Energy/Health/Experience/Faction/Rank/Titles, InventoryBag(s)/Slot, Map/MissionData/QuestLog, Skillbar/UnlockedSkills, KeyStruct, SharedMessageStruct, Globals).

DEMO v1 is overwhelmingly `GLOBAL_CACHE.*`-based. v2 leans on direct wrappers + context structs.

## D. C++ `Py*` binding modules — `Py4GW_Reforged_Native\src\`

Registered in `src\base\python_runtime.cpp` (~lines 401–438). The authoritative "list of everything the DLL exposes."

**Infra:** `PySystem` (console/env/window/lifecycle), `PySettings`, `PyProfiler`, `PyCallback`, `PyListeners`/`PyAgentEvents`, `PyScanner`, `PyGameThread`, `SharedMemory` submodule.
**GW domain:** `PyAgent`, `PyAgentRecolor`, `PyCamera`, `PyChat`, `PyEffects`, `PyFriendList`, `PyGuild`, `PyItem`, `PyInventory`, `PyMap`, `PyMerchant`, `PyNameObfuscator`, `PyPacketSniffer`, `PyParty`, `PyPathing`, `PyPing`, `PyPlayer`, `PyQuest`, `PyRender`, `PySkill`, `PySkillbar`, `PyTrade`, `PyUIManager`, `PyTexture`, `PyDialog`.
**Rendering/IO:** `PyOverlay`, `PyDXOverlay`, `PyKeystroke`/`PyMouse` (`PyKeyHandler`), `PyImGui` (+ `src\imgui\bindings\*`: types, enums, io, style, drawlist, addons — filebrowser, hotkey, markdown, memory_editor, anim, text_editor).

Binding files live beside each manager, e.g. `src\GW\agent\agent_bindings.cpp`, `src\GW\map\map_bindings.cpp`, `src\overlay\overlay_bindings.cpp`, `src\virtual_input\virtual_input_bindings.cpp`, `src\imgui\imgui_bindings.cpp`.

## E. C++ `GW/` managers — `Py4GW_Reforged_Native\src\GW\<module>\` + `include\GW\<module>\`

Namespace-scoped singletons (e.g. `GW::agent` aka `GW::Agents`). One primary header per module:
`agent`, `agent_recolor`, `camera`, `chat`, `dialog`, `effects`, `events`, `friend_list`, `game_thread`, `guild`, `item` (item+inventory), `map`, `merchant`, `name_obfuscator`, `native_ui`, `packet_sniffer`, `party`, `pathing`, `ping`, `player`, `quest`, `render`, `shared_memory`, `skillbar` (+`skill_names.h`), `stoc`, `textures` (`TextureManager` + arenanet_texture/file_parser + gw_dat_reader/unpack), `trade`, `ui`.
Plus `common/` (game_pos, gw_array, gw_list, opcodes, stoc, constants) and `context/` (native struct headers the Python `native_src/context/*.py` mirror).

**Entry points:** `src\base\python_runtime.cpp` (master binding registrar, the `Py*` name list), top-level `src\Py4GW.cpp` / `include\Py4GW.h`. Supporting subsystems: `src\base\` (python_runtime, scanner, CrashHandler), `src\system\`, `src\settings\`, `src\profiler\`, `src\overlay\`, `src\virtual_input\`, `src\listeners\`, `src\callback\`, `src\imgui\`.
