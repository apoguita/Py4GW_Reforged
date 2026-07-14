# Coverage Matrix — v1 vs v2 vs Backend

Rows are backend domains (native `Py*` module → Python wrapper). Columns show whether each demo exercises the domain and how deeply. This is the map for deciding what a replacement must cover.

Legend: ✅ covered · ⚠️ partial/shallow · ❌ absent · 🆕 v2-only new surface

| Domain | Native module | Wrapper | DEMO v1 | DEMO v2 | Notes |
|---|---|---|---|---|---|
| Map (scalar/instance) | `PyMap` | `Map.py` | ⚠️ basic instance + travel + outpost/explorable | ✅ deep (all Get* fields, actions) | v2 far more complete |
| Map — Mission Map | `PyMap` | `Map.MissionMap` | ❌ | 🆕✅ frame info, projection, overlay | v2-only |
| Map — Mini Map | `PyMap` | `Map.MiniMap` | ❌ | 🆕✅ | v2-only |
| Map — World Map | `PyMap` | `Map.WorldMap` | ❌ | 🆕✅ params/extra data | v2-only |
| Map — Pregame/char-select | `PyMap`/PreGameContext | `Map.Pregame` | ❌ | 🆕✅ context struct dump | v2-only |
| Map — Pathing/navmesh | `PyPathing` | `Pathing.py`, `Map.Pathing` | ❌ | 🆕✅ trapezoid canvas + AutoPathing | v2-only |
| Agent (single) | `PyAgent` | `Agent.py` | ✅ living/item/gadget inspector | ✅ deeper + AgentStruct | both strong |
| AgentArray | (derived) | `AgentArray.py` | ⚠️ used for nearest/sort | ⚠️ counts + filter combo | neither exhaustive |
| native context structs | contexts | `native_src/context/*` | ❌ | 🆕✅ AgentStruct, Pregame ctx | v2 introduces struct-path testing |
| Player | `PyPlayer` | `Player.py` | ✅ data/titles/faction/methods | ❌ | **v2 gap** |
| Party (players/heroes/henchmen/pets) | `PyParty` | `Party.py` | ✅ full | ❌ | **v2 gap** |
| Item (data/rarity/mods/dye) | `PyItem` | `Item.py` | ✅ full | ❌ | **v2 gap** |
| Inventory | `PyInventory` | `Inventory.py` | ✅ kits/gold/salvage/xunlai | ❌ | **v2 gap** |
| Skill (static data) | `PySkill` | `Skill.py` | ✅ data/attr/flags/anim/extra | ❌ | **v2 gap** |
| Skillbar (live) | `PySkillbar` | `Skillbar.py` | ✅ slots + hero bars | ❌ | **v2 gap** |
| Effects/Buffs | `PyEffects` | `Effect.py` | ✅ buffs/effects/drop | ❌ | **v2 gap** |
| Merchant/Trader/Crafter/Collector | `PyMerchant` | `Merchant.py` | ✅ all four types | ❌ | **v2 gap** |
| Trade (player↔player) | `PyTrade` | (none dedicated) | ❌ | ❌ | **neither** |
| Quest | `PyQuest` | `Quest.py` | ⚠️ active/set/abandon | ❌ | thin in v1, absent v2 |
| Keystroke/Mouse | `PyKeystroke`/`PyMouse` | `Keystroke.py` | ✅ press/release/push | ❌ | **v2 gap** |
| Overlay (ImGui) | `PyOverlay` | `Overlay.py` | ✅ rings/text/mouse-world | ✅ used within Map views | both |
| DXOverlay | `PyDXOverlay` | `DXOverlay.py` | ❌ | ❌ | **neither** |
| Camera | `PyCamera` | `Camera.py` | ❌ | ❌ | **neither** |
| Chat | `PyChat` | (via Player) | ⚠️ via Player.SendChat* | ❌ | indirect only |
| Dialog | `PyDialog` | `Dialog.py` | ⚠️ Player.SendDialog | ❌ | indirect only |
| UIManager / GWUI | `PyUIManager` | `UIManager.py`,`GWUI.py` | ❌ | 🆕⚠️ FrameInfo via Map | mostly untested |
| Texture | `PyTexture` | `TextureManager`… | ❌ (icons only) | ❌ | **neither** |
| Guild | `PyGuild` | (none) | ❌ | ❌ | **neither** |
| Friend list | `PyFriendList` | (none) | ❌ | ❌ | **neither** |
| Packet sniffer | `PyPacketSniffer` | `PacketSniffer.py` | ❌ | ❌ | **neither** |
| Agent events / listeners | `PyAgentEvents`/`PyListeners` | `CombatEvents.py` | ❌ | ❌ | **neither** (separate `CombatEventsTester` widget) |
| Ping/latency | `PyPing` | (inline) | ✅ stats | ❌ | **v2 gap** |
| System/Console | `PySystem` | `Py4GWCoreLib` | ✅ logging everywhere | ⚠️ prints | both |
| Settings | `PySettings` | `Settings` | ❌ | ❌ | **neither** |
| Camera/Render/Profiler | `PyRender`/`PyProfiler` | — | ❌ | ❌ | **neither** |
| PyImGui widgets | `PyImGui` | `ImGui`/`ImGui_Legacy` | ✅ selectables/inputs/tables/misc/official | ⚠️ uses new API but no widget gallery | v1 has a gallery; separate `ImGui Official DEMO` widget exists |

## Headline takeaways

1. **v2 is a partial rewrite.** It re-implements Map + Agents on the *new* surface and adds map sub-namespaces, native context structs, projection math and a pathing canvas that v1 never touched — but drops ~10 domains v1 covered.
2. **A replacement must merge both:** v2's modular shell + native-surface depth, plus v1's breadth (Player, Party, Item, Inventory, Skill, Skillbar, Effects, Merchant, Quest, Keystroke, Ping).
3. **Large untested backend area in BOTH demos:** `PyTrade`, `PyCamera`, `PyDXOverlay`, `PyDialog` (direct), `PyUIManager`/`GWUI`, `PyTexture`, `PyGuild`, `PyFriendList`, `PyPacketSniffer`, `PyAgentEvents`/`PyListeners`, `PySettings`, `PyProfiler`, `PyRender`, `PyNameObfuscator`, `PyAgentRecolor`, `PyChat` (direct). A true "test every CPP binding" tool would need these too.
