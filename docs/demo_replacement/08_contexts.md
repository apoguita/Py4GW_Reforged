# Context Path — Native Structs & ctypes Readers

This is a completeness checklist for the **context path** of Py4GW Reforged: the
ctypes `Structure` mirrors of Guild Wars memory "contexts" that a demo/test widget
can enumerate and display. Unlike the *bindings path* (`Py*` callable modules),
these are **raw shared-memory reads** — each Python file in
`Py4GWCoreLib/native_src/context/` defines one or more `ctypes.Structure` classes
that overlay a game struct in-process, plus a small **facade class** that resolves
the pointer once per frame and hands back a cached instance.

## How a context is obtained (the common pattern)

Every context file follows the same shape:

- A `*Struct(Structure)` (ctypes overlay) — the actual layout.
- A **facade class** (`ClassName`) with class-level state:
  - `get_ptr() -> int` — raw address of the context.
  - `get_context() -> *Struct | None` — the cached ctypes instance (this is what a demo reads).
  - `_update_ptr()` — resolves the pointer, usually from
    `SystemShaMemMgr.get_pointers_struct()` (the `Pointers_SHMemStruct` published
    by the Native DLL over shared memory — see below), then
    `cast(ptr, POINTER(*Struct)).contents`.
  - `enable()/disable()` — register/unregister `_update_ptr` on a `PyCallback`
    `PreUpdate` phase. **Each module calls `ClassName.enable()` at import time**, so
    simply importing the module (or `Py4GWCoreLib.Context`) keeps the cache warm.

Two contexts do **not** use the shared-memory pointer table and instead pattern-scan:
- `InstanceInfo` — via `InstanceInfo_GetPtr` `NativeSymbol` (SSM value is a code-ref, not the struct).
- `AgentArray` — via `AgentArray_GetPtr` `NativeSymbol`.

### The shared-memory pointer table

`Py4GWCoreLib/native_src/ShMem/structs/PointersSSM.py` → `Pointers_SHMemStruct`
lists every context pointer the DLL publishes (all `c_void_p`):

`MissionMapContext, WorldMapContext, GameplayContext, InstanceInfo, MapContext,
GameContext, PreGameContext, WorldContext, CharContext, AgentContext,
CinematicContext, GuildContext, AvailableCharacters, PartyContext,
ServerRegionContext, Camera`.

Accessed as `SystemShaMemMgr.get_pointers_struct().<Field>`.

### The friendly wrapper — `GWContext`

`Py4GWCoreLib/Context.py` exposes a **unified facade `GWContext`** over almost every
context. Each nested class derives from `_GWContextBase[TStruct]` and offers:
- `GWContext.<Name>.GetContext() -> TStruct | None`
- `GWContext.<Name>.IsValid() -> bool`

So a demo can call **either** the raw facade (`MapContext.get_context()`) **or** the
wrapper (`GWContext.Map.GetContext()`) — they return the same `*Struct`. The wrapper
is the recommended entry point for a demo because it's a single import
(`from Py4GWCoreLib.Context import GWContext`) covering all contexts uniformly.

`GWContext` members: `AccAgent, AgentArray, AvailableCharacterArray, Char, Cinematic,
Gameplay, Guild, InstanceInfo (+ GetMapInfo()), Map, MissionMap, Party, PreGame,
ServerRegion, World, WorldMap`.

**Not in `GWContext`:** `GameContext` and `TextParser` — reachable only through their
own module facades (`GameContext` has no facade at all; see its section).

## Shared sub-struct / helper types

These are reused across many contexts. Layouts live in `native_src/internals/`.

| Type | File | Layout | Meaning |
|---|---|---|---|
| `Vec2f` | `internals/types.py` | 2× `c_float` (`x,y`) | 2D position/vector (with operators, `to_tuple`) |
| `Vec3f` | `internals/types.py` | 3× `c_float` (`x,y,z`) | 3D position/vector |
| `GamePos` | `internals/types.py` | `c_float x,y` + `c_uint32 zplane` | GW ground position (x,y + z-plane index) |
| `GW_BaseArray` | `internals/gw_array.py` | `void* m_buffer, u32 m_capacity, u32 m_size` (0x0C) | GWCA `BaseArray<T>` |
| `GW_Array` | `internals/gw_array.py` | `GW_BaseArray` + `u32 m_param` (0x10) | GWCA `Array<T>` |
| `GW_Array_View(arr, T)` | `internals/gw_array.py` | — | Iterates an `Array<T*>` (pointer array): derefs each element |
| `GW_Array_Value_View(arr, T)` | `internals/gw_array.py` | — | Iterates an `Array<T>` (value array); `.to_list()` |
| `GW_TLink` | `internals/gw_list.py` | `void* prev_link, void* next_node` | GWCA `TLink<T>` intrusive-list node |
| `GW_TList` | `internals/gw_list.py` | `u32 offset` + `GW_TLink link` (0x0C) | GWCA `TList<T>` head; walk with `GW_TList_View(list, T)` |
| `read_wstr(ptr)` | `internals/helpers.py` | — | Reads a null-terminated `wchar_t*` |
| `encoded_wstr_to_str(s)` | `internals/helpers.py` | — | Escapes GW-encoded control chars → readable `\xXXXX` string |

**Encoded strings:** GW stores names/messages as *encoded* wide strings. Structs expose
paired accessors: `*_encoded_str` (raw) and `*_str` (decoded via `encoded_wstr_to_str`).
A demo should show both.

## C++ authority

The authoritative layouts live in `Py4GW_Reforged_Native/include/GW/context/*.h`
(namespace `GW::Context`). Header→context map:

| Header | Covers |
|---|---|
| `agent.h` | `Agent`/`AgentItem`/`AgentGadget`/`AgentLiving`, `MapAgent`, `AgentMovement`, `AgentSummaryInfo`, `AgentContext` |
| `account.h` | `AccountContext` (0x138), `AvailableCharacterInfo`, `AccountUnlockedCount` |
| `character.h` | `CharContext` (0x440) |
| `world.h` | `WorldContext` |
| `map.h` | `MapContext`, `MissionMapContext`, `WorldMapContext`, `PropsContext`, `MissionMapSubContext(2)` |
| `party.h` | `PartyContext` (0x58) |
| `guild.h` | `GuildContext` (0x3BC) |
| `gameplay.h` | `GameplayContext` |
| `game.h` | `GameContext` (+ fwd-decls of all sub-contexts) |
| `pregame.h` | `PreGameContext` |
| `cinematic.h` | `Cinematic` |
| `text_parser.h` | `TextParser` |
| `skill.h` | `Skillbar`, `SkillbarSkill`, `SkillbarCast`, `AgentEffects`, `Buff`, `Effect` |
| `quest.h` | `Quest` |
| `context.h` | forward declarations + `GameContext` accessors |

InstanceInfo and ServerRegion have no dedicated header of the same name (resolved by
pattern scan / small SSM value respectively).

---

# Context inventory

Legend for "Reader": **SSM** = pointer from `Pointers_SHMemStruct`; **scan** = pattern
scan `NativeSymbol`; **derived** = resolved from another context.

---

## GameContext  — the root context

- **Python:** `native_src/context/GameContext.py` → `GameContextStruct` (0x5C).
- **C++:** `game.h` → `GW::Context::GameContext`.
- **Reader:** SSM field `GameContext`. **No facade class** — there's no
  `GameContext.get_context()`. Read it manually:
  `cast(SSM.GameContext, POINTER(GameContextStruct)).contents`. `TextParser` does
  exactly this to reach `text_parser`.
- **Wrapper-exposed?** **No** (not in `GWContext`). Raw-only.

This is the hub: every field below `+0x08` is a `uint32` pointer to another context.

| Field | Type | Meaning |
|---|---|---|
| `h0000`,`h0004` | `c_void_p` | unknown |
| `agent_context` | u32 | → AgentContext* (+0x08) |
| `map_context` | u32 | → MapContext* (+0x14) |
| `text_parser` | u32 | → TextParser* (+0x18) |
| `account_context` | u32 | → AccountContext* (+0x28) |
| `world_context` | u32 | → WorldContext* (+0x2C) |
| `cinematic` | u32 | → Cinematic* (+0x30) |
| `gadget_context` | u32 | → GadgetContext* (+0x38) |
| `guild_context` | u32 | → GuildContext* (+0x3C) |
| `item_context` | u32 | → ItemContext* (+0x40) |
| `char_context` | u32 | → CharContext* (+0x44) |
| `party_context` | u32 | → PartyContext* (+0x4C) |
| `trade_context` | u32 | → TradeContext* (+0x58) |

---

## AgentContext (agents + AgentArray)

- **Python:** `native_src/context/AgentContext.py` — the biggest file. Defines the
  agent object hierarchy and the `AgentArray` facade (NOT the account-level
  AgentContext; that's the *next* section).
- **C++:** `agent.h` → `Agent`, `AgentItem`, `AgentGadget`, `AgentLiving`.
- **Reader:** `AgentArray` facade, ptr via **scan** (`AgentArray_GetPtr`), *not* SSM.
- **Wrapper-exposed?** **Yes** — `GWContext.AgentArray.GetContext()` returns
  `AgentArrayStruct`. Agent lookups: `AgentArray.GetAgentByID(id)` →
  `AgentStruct`. (The full `Agent`/`Player`/`AgentArray` wrapper classes in
  `Py4GWCoreLib` provide the ergonomic API on top.)

Structures defined:

| Struct | Base | Notes / total |
|---|---|---|
| `AgentStruct` | Structure | Base agent, fields to +0xB4. Has `snapshot()` + `GetAsAgentItem/Gadget/Living()` casts |
| `AgentLivingStruct` | `AgentStruct` | 0x1C4 — players/NPCs/monsters (largest) |
| `AgentItemStruct` | `AgentStruct` | 0xD4 — dropped items |
| `AgentGadgetStruct` | `AgentStruct` | 0xE4 — signposts/chests/etc |
| `AgentArrayStruct` | Structure | wraps `GW_Array agent_array` (`Array<Agent*>`), builds allegiance caches |
| `EquipmentStruct` + `ItemDataStruct`, `DyeInfoStruct`, unions | | weapon/armor model info on living agents |
| `TagInfoStruct` | | guild tag (guild_id/primary/secondary/level) |
| `VisibleEffectStruct` | | enchant/weapon-spell display effects (via `GW_TList`) |

Key `AgentStruct` fields: `agent_id`, `pos` (`GamePos`), `z`, `rotation_angle`,
`type` (bitfield: item 0x400 / gadget 0x200 / living), `velocity` (`Vec2f`),
`terrain_normal` (`Vec3f`), box widths/heights, `visual_effects`.

Key `AgentLivingStruct` fields: `hp`/`max_hp`, `energy`/`max_energy`, `hp_pips`,
`level`, `primary`/`secondary`, `team_id`, `allegiance` (1 ally…6 npc/minipet),
`login_number` (player if ≠0), `player_number`, `agent_model_type`, `weapon_type`,
`skill`, `model_state`, `effects`/`type_map` bitfields, `equipment`, `tags`,
`visible_effects`. Dozens of boolean props (`is_dead`, `is_moving`, `is_casting`,
`is_enchanted`, `is_bleeding`, …) decode `effects`/`type_map`/`model_state`.

`AgentArrayStruct` accessors: `raw_agents`, `GetAgentByID`, and cached lists
`GetAgentArray/GetAllyArray/GetEnemyArray/GetNeutralArray/GetSpiritPetArray/
GetMinionArray/GetNPCMinipetArray/GetItemAgentArray/GetOwnedItemAgentArray/
GetGadgetAgentArray/GetDeadAllyArray/GetDeadEnemyArray`.

Sub-structs referenced: `GamePos`, `Vec2f/Vec3f`, `GW_Array`, `GW_TLink`, `GW_TList`.

---

## AccAgentContext (account/instance-level agent context)

- **Python:** `native_src/context/AccAgentContext.py` → `AccAgentContextStruct`.
- **C++:** `agent.h` → `GW::Context::AgentContext` (yes — the confusingly-named one;
  Python renamed it "Acc" to avoid clashing with the agent-object `AgentContext.py`).
- **Reader:** `AccAgentContext` facade, SSM field **`AgentContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.AccAgent.GetContext()`.

Notable fields (mostly `GW_Array<void*>` scratch arrays + link fields):

| Field | Type | Meaning |
|---|---|---|
| `agent_summary_info_array` | `GW_Array` | `Array<AgentSummaryInfo>` (name/gadget metadata) |
| `agent_movement_array` | `GW_Array` | `Array<AgentMovement*>` — indexed by agent id |
| `instance_timer` | u32 (+0x1AC) | instance frame timer (map-change detection) |
| `rand1`,`rand2` | u32 | randomized values used by textparser |

Sub-structs: `AgentSummaryInfo` (+`AgentSummaryInfoSub` with encoded gadget name),
`AgentMovement` (agent_id, `moving1/2` stuck flags, `Vec3f` positions).
Helper props: `valid_agents_ids` (agents with a non-null movement entry),
`agent_summary_info_list`, `agent_movement_ptrs`.

---

## AccountContext / AvailableCharacterContext

- **Python:** `native_src/context/AvailableCharacterContext.py` →
  `AvailableCharacterArrayStruct` + `AvailableCharacterStruct`.
- **C++:** `account.h` → `AccountContext` (0x138) / `AvailableCharacterInfo`.
- **Reader:** `AvailableCharacterArray` facade, SSM field **`AvailableCharacters`**.
- **Wrapper-exposed?** **Yes** — `GWContext.AvailableCharacterArray.GetContext()`.

`AvailableCharacterArrayStruct` = one `GW_Array` (`available_characters_array`),
`.available_characters_list` → `list[AvailableCharacterStruct]`.

`AvailableCharacterStruct` fields: `uuid` (4×u32), `player_name_enc`
(`wchar[20]`), plus a `props[17]` block decoded via bit-props:
`map_id`, `primary`, `secondary`, `campaign`, `level`, `is_pvp`.

---

## CharContext

- **Python:** `native_src/context/CharContext.py` → `CharContextStruct` (0x440, asserted).
- **C++:** `character.h` → `CharContext` (0x440, static_assert).
- **Reader:** `CharContext` facade, SSM field **`CharContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.Char.GetContext()`.

| Field | Type | Meaning |
|---|---|---|
| `player_name_enc` | `wchar[20]` | player character name (encoded) |
| `player_email_ptr` | `wchar[64]` | account email (encoded) |
| `player_uuid` | 4×u32 | character UUID |
| `map_id` | u32 | `GW::Constants::MapID` |
| `current_map_id` / `observe_map_id` | u32 | active / observed map |
| `current_map_type` / `observe_map_type` | u32 | map type |
| `is_explorable` | u32 | explorable flag |
| `district_number` | i32 | district |
| `language` | u32 | `GW::Constants::Language` |
| `player_number` | u32 | agent/player number |
| `token1`/`token2` | u32 | world id / player id |
| `world_flags`,`player_flags` | u32 | flags |
| `progress_bar_ptr` | `ProgressBar*` | cast-bar/progress (pips, color, `progress` 0..1) |
| `observer_matches_array` | `GW_Array` | `Array<ObserverMatch*>` (observer mode) |

Sub-structs: `ProgressBar` (0x2C), `ObserverMatch` (+`ObserverMatchFlags`, team-name ptrs).

---

## WorldContext  — by far the largest context

- **Python:** `native_src/context/WorldContext.py` → `WorldContextStruct` (very large).
- **C++:** `world.h` → `WorldContext`.
- **Reader:** `WorldContext` facade, SSM field **`WorldContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.World.GetContext()`.

Holds the bulk of per-character/party live state. Dozens of `GW_Array` members, each
with a decoding property. Highlights:

| Property | Element struct | Meaning |
|---|---|---|
| `account_info` | `AccountInfoStruct` | account name, PvP wins/losses/rating/rank |
| `message_buff` / `dialog_buff` | `wchar` | chat/dialog buffers |
| `merch_items` / `merch_items2` | u32 | merchant item ids |
| `map_agents` | `MapAgentStruct` | per-agent hp/energy/effects (party-window data) |
| `party_allies` | `PartyAllyStruct` | ally agent/composite ids |
| `party_attributes` | `PartyAttributeStruct` | 54× `AttributeStruct` per agent |
| `party_effects` | `AgentEffectsStruct` | buffs + effects per agent (`Buff`/`Effect`) |
| `quest_log` | `QuestStruct` | quests (id, name/npc/desc encoded, `marker` GamePos) |
| `active_quest_id` | u32 | current quest |
| `mission_objectives` | `MissionObjectiveStruct` | objective text/type |
| `hero_flags` / `hero_info` | `HeroFlagStruct`/`HeroInfoStruct` | hero flagging + roster |
| `henchmen_agent_ids` | u32 | henchmen ids |
| `pets` | `PetInfoStruct` | pet name/model/behavior |
| `party_skillbars` | `SkillbarStruct` | 8× `SkillbarSkillStruct` + cast queue |
| `party_profession_states` | `ProfessionStateStruct` | primary/secondary/unlocked professions |
| `players` | `PlayerStruct` | player roster (name, professions, flags) |
| `npc_models` | `NPC_ModelStruct` | NPC/hero/henchman model info + flags |
| `titles` / `title_tiers` | `TitleStruct`/`TitleTierStruct` | title progression |
| `mission_map_icons` | `MissionMapIconStruct` | minimap icons |
| `agent_name_info` | `AgentNameInfoStruct` | agent display names |
| faction/xp scalars | u32 (many) | `experience`, `current_kurzick/luxon/imperial/balth`, `current_skill_points`, `morale`, `level`, `max_*`, `foes_killed/to_kill`, all with `_dupe` mirrors |
| `all_flag` | `Vec3f` | "flag all" command position |
| `controlled_minions` | `ControlledMinionsStruct` | minion counts |
| `missions_completed/bonus(_hm)`, `unlocked_maps`, `vanquished_areas` | u32 | progression bitlists |
| `learnable/unlocked/duplicated_character_skills` | u32/`DupeSkillStruct` | skill unlocks |

Sub-structs defined in this file (all reusable): `AccountInfoStruct`, `MapAgentStruct`
(+ effect bit-props), `PartyAllyStruct`, `AttributeStruct`, `PartyAttributeStruct`,
`EffectStruct`, `BuffStruct`, `AgentEffectsStruct`, `QuestStruct`,
`MissionObjectiveStruct`, `HeroFlagStruct`, `HeroInfoStruct`, `ControlledMinionsStruct`,
`PartyMemberMoraleInfoStruct`, `PartyMoraleLinkStruct`, `PlayerControlledCharacterStruct`,
`ProfessionStateStruct`, `SkillbarSkillStruct`, `SkillbarCastStruct`, `SkillbarStruct`,
`DupeSkillStruct`, `AgentNameInfoStruct`, `MissionMapIconStruct`, `PetInfoStruct`,
`NPC_ModelStruct`, `PlayerStruct`, `TitleStruct`, `TitleTierStruct`.

> A demo should treat this context as expandable/lazy — most array properties return
> `None` outside an instance. `vanquished_areas` currently early-returns `None` (guarded off).

---

## MapContext (+ pathing / props)

- **Python:** `native_src/context/MapContext.py` → `MapContextStruct` (0x138).
- **C++:** `map.h` → `MapContext`.
- **Reader:** `MapContext` facade, SSM field **`MapContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.Map.GetContext()`, plus static helpers on
  the facade: `MapContext.GetPathingMaps()`, `GetPathingMapsRaw()`, `GetSpawns()`,
  `GetTravelPortals()`, `ClearPathingCache()`. (The `Py4GWCoreLib.Map` module wraps
  further.)

| Field | Type | Meaning |
|---|---|---|
| `map_type` | u32 | map type (<4) |
| `start_pos` / `end_pos` | `Vec2f` | map bounds |
| `spawns1/2/3_array` | `GW_Array` | `SpawnEntryStruct` → `.spawns1/2/3` (`SpawnPoint`) |
| `path_ptr` | `PathContextStruct*` | pathfinding state (`.path`) |
| `props_ptr` | `PropsContextStruct*` | runtime props (`.props`) |
| `map_id` | u32 | `GW::Constants::MapID` |
| `terrain`,`zones` | `c_void_p` | terrain/zone blobs |

Large sub-struct tree (pathing): `PathContextStruct` → `MapStaticDataStruct` →
`PathingMapStruct` → `PathingTrapezoidStruct`, `SinkNodeStruct`, `XNodeStruct`,
`YNodeStruct`, `PortalStruct`, `NodeStruct`, plus `BlockingPropStruct`. Props tree:
`PropsContextStruct` → `MapPropStruct`, `PropModelInfoStruct`, `PropByTypeStruct`,
`RecObjectStruct`. Snapshot dataclasses (`PathingMap`, `Portal`, `SpawnPoint`,
`TravelPortal`, etc.) provide Python-owned copies. Uses `GW_Array`, `GW_BaseArray`,
`GW_TList`, `Vec2f/Vec3f`.

---

## MissionMapContext

- **Python:** `native_src/context/MissionMapContext.py` → `MissionMapContextStruct` (0x48).
- **C++:** `map.h` → `MissionMapContext`.
- **Reader:** `MissionMapContext` facade, SSM field **`MissionMapContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.MissionMap.GetContext()`.

| Field | Type | Meaning |
|---|---|---|
| `size` | `Vec2f` | minimap widget size |
| `last_mouse_location` | `Vec2f` | last mouse pos on minimap |
| `frame_id` | u32 | UI frame id |
| `player_mission_map_pos` | `Vec2f` | player marker position |
| `h0020` | `GW_Array` | `Array<MissionMapSubContext*>` → `.subcontexts` |
| `h003c` | `MissionMapSubContext2*` | pan/zoom sub-context → `.subcontext2` |

`MissionMapSubContext2` (0x58): `player_mission_map_pos`, `mission_map_size`,
`mission_map_pan_offset(2)`.

---

## WorldMapContext

- **Python:** `native_src/context/WorldMapContext.py` → `WorldMapContextStruct` (0x224).
- **C++:** `map.h` → `WorldMapContext`.
- **Reader:** `WorldMapContext` facade, SSM field **`WorldMapContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.WorldMap.GetContext()`. (`Py4GWCoreLib.Map`
  has a WorldMap dump helper.)

Mostly unknown floats. Meaningful fields:

| Field | Type | Meaning |
|---|---|---|
| `frame_id` | u32 | UI frame id |
| `zoom` | float (+0x38) | world-map zoom level |
| `top_left` / `bottom_right` | `Vec2f` | visible world-map rect |
| `params` | `u32[0x6D]` | large trailing blob (unknown) |

---

## PartyContext

- **Python:** `native_src/context/PartyContext.py` → `PartyContextStruct`.
- **C++:** `party.h` → `PartyContext` (0x58).
- **Reader:** `PartyContext` facade, SSM field **`PartyContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.Party.GetContext()`. (`Py4GWCoreLib.Party`
  is the ergonomic wrapper.)

| Field | Type | Meaning |
|---|---|---|
| `flag` | u32 | party flags → `in_hard_mode`, `is_defeated`, `is_party_leader` props |
| `request_list` / `sending_list` | `GW_TList` | incoming/outgoing invites → `.request`/`.sending` |
| `parties_array` | `GW_Array` | `Array<PartyInfoStruct*>` → `.parties` |
| `player_party_ptr` | `PartyInfoStruct*` | your party → `.player_party` |
| `party_search_array` | `GW_Array` | `Array<PartySearch*>` → `.party_searches` |

Sub-structs: `PartyInfoStruct` (party_id + `players`/`henchmen`/`heroes`/`others` arrays
+ `invite_link` TLink), `PlayerPartyMember` (login_number, `is_connected`/`is_ticked`),
`HeroPartyMember` (agent_id, owner, hero_id, level), `HenchmanPartyMember`,
`PartySearchStruct` (search metadata + `message`/`party_leader` encoded strings).

---

## GuildContext

- **Python:** `native_src/context/GuildContext.py` → `GuildContextStruct`.
- **C++:** `guild.h` → `GuildContext` (0x3BC).
- **Reader:** `GuildContext` facade, SSM field **`GuildContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.Guild.GetContext()`.

| Field | Type | Meaning |
|---|---|---|
| `player_name_enc` | `wchar[20]` | your character name (encoded) |
| `player_guild_index` | u32 | index into `guild_array` |
| `player_gh_key` | `GHKey` | your guild hall key |
| `player_guild_rank` | u32 | your rank |
| `announcement_enc` | `wchar[256]` | guild announcement (encoded) |
| `announcement_author_enc` | `wchar[20]` | announcement author |
| `factions_outpost_guilds_array` | `GW_Array` | `Array<TownAlliance>` → `.factions_outpost_guilds` |
| `kurzick_town_count`/`luxon_town_count` | u32 | faction town control |
| `player_guild_history_array` | `GW_Array` | `Array<GuildHistoryEvent*>` |
| `guild_array_array` | `GW_Array` | `Array<Guild*>` → `.guild_array` |
| `player_roster_array` | `GW_Array` | `Array<GuildPlayer*>` → `.player_roster` |

Sub-structs: `GHKey` (4-byte key + hex string), `CapeDesign`, `TownAlliance`,
`GuildHistoryEvent`, `Guild` (name/tag/rank/faction/cape), `GuildPlayer`
(invited/current/inviter/promoter names, member_type, status, offline).

---

## GameplayContext

- **Python:** `native_src/context/GameplayContext.py` → `GameplayContextStruct` (0x78, asserted).
- **C++:** `gameplay.h` → `GameplayContext`.
- **Reader:** `GameplayContext` facade, SSM field **`GameplayContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.Gameplay.GetContext()`.

Mostly opaque. One meaningful field:

| Field | Type | Meaning |
|---|---|---|
| `h0000` | `u32[0x13]` | unknown block |
| `mission_map_zoom` | `c_float` | mission-map zoom factor |
| `unk` | `u32[10]` | unknown tail |

---

## InstanceInfo

- **Python:** `native_src/context/InstanceInfoContext.py` → `InstanceInfoStruct`.
- **C++:** no header of this name (built from `AreaInfo`/map-dimensions RE).
- **Reader:** `InstanceInfo` facade, **pattern scan** `InstanceInfo_GetPtr` (SSM value is
  a code-ref, not the struct — noted in code).
- **Wrapper-exposed?** **Yes** — `GWContext.InstanceInfo.GetContext()`, and the wrapper
  adds `GetMapInfo() -> AreaInfoStruct`. Heavily consumed by `Py4GWCoreLib.Map`/`Context`.

| Field | Type | Meaning |
|---|---|---|
| `instance_type` | u32 | `GW::Constants::InstanceType` (0 outpost,1 explorable,2 loading) |
| `current_map_info_ptr` | `AreaInfoStruct*` | area/map metadata → `.current_map_info` |
| `terrain_info1_ptr`/`terrain_info2_ptr` | `MapDimensionsStruct*` | map extents |
| `terrain_count` | u32 | terrain block count |

`AreaInfoStruct` is rich: `campaign`, `continent`, `region`, `type`, `flags`,
`min/max_party_size`, `min/max_level`, `mission_maps_to`, `x/y` map-icon position,
`name_id`/`description_id`, plus flag props (`is_pvp`, `is_guild_hall`,
`is_vanquishable_area`, `has_enter_button`, `is_on_world_map`, …).
`MapDimensionsStruct`: `start_x/y`, `end_x/y`.

---

## ServerRegionContext

- **Python:** `native_src/context/ServerRegionContext.py` → `ServerRegionStruct`.
- **C++:** no dedicated header.
- **Reader:** `ServerRegion` facade, SSM field **`ServerRegionContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.ServerRegion.GetContext()`; also used in
  `Py4GWCoreLib.Map` for region name lookup.

Tiny — a single field:

| Field | Type | Meaning |
|---|---|---|
| `region_id` | `c_int32` | server region id (→ `ServerRegionName`) |

---

## Cinematic (CinematicContext)

- **Python:** `native_src/context/CinematicContext.py` → `CinematicStruct`.
- **C++:** `cinematic.h` → `Cinematic`.
- **Reader:** `Cinematic` facade, SSM field **`CinematicContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.Cinematic.GetContext()`.

Minimal stub — two unknown u32 (`h0000`, `h0004`). Mainly a presence/validity signal
(are we in a cinematic).

---

## PreGameContext (login/character-select screen)

- **Python:** `native_src/context/PreGameContext.py` → `PreGameContextStruct` (0x100, asserted).
- **C++:** `pregame.h` → `PreGameContext`.
- **Reader:** `PreGameContext` facade, SSM field **`PreGameContext`**.
- **Wrapper-exposed?** **Yes** — `GWContext.PreGame.GetContext()`, **and** the
  `Py4GWCoreLib.Map.Pregame` nested class exposes `GetContextStruct()`, `GetFrameID()`,
  `GetFrameInfo()`, char-list helpers.

| Field | Type | Meaning |
|---|---|---|
| `frame_id` | u32 | UI frame id |
| `scene_type` | u32 | login scene type |
| a large `camera_*`/`scroll_*` float block | `c_float` | login-screen camera/scroll animation state |
| `max_characters` | u32 | character slot count |
| `chosen_character_index` | i32 | selected char |
| `preview_character_index` / `pending_character_index` | i32 | preview / pending selection |
| `chars_array` | `GW_BaseArray` | `.chars_list` → `list[LoginCharacter]` |
| `char_creation_flag`, `create_slot_index` | i32 | char-creation state |

`LoginCharacter` (0x78, asserted): `appearance_packed`, `pvp_flag`, guild GUID (4×u32),
items TArray (`items_data/capacity/count`), `level`, `current_map_id`,
`primary_profession`, `profession_enum`, `char_model_ptr`,
`character_name_enc` (`wchar[20]` → `.character_name`).

---

## TextParser (TextContext)

- **Python:** `native_src/context/TextContext.py` → `TextParserStruct` (0x1D4) +
  `TextFileSlotStruct`, `LanguageSlotStruct`.
- **C++:** `text_parser.h` → `TextParser`.
- **Reader:** `TextParser` facade — **derived**: resolves `GameContext` from SSM, then
  reads `GameContextStruct.text_parser` (+0x18). On first resolve it kicks off the
  string-table load for `language_id`.
- **Wrapper-exposed?** **No** (not in `GWContext`). Raw-only via `TextParser.get_context()`.

| Field | Type | Meaning |
|---|---|---|
| `dec_start_ptr`/`dec_end_ptr` | u32 | decode buffer window |
| `language_slots` | `LanguageSlotStruct[11]` (+0x064) | per-language file-slot metadata |
| `entries_per_file` | u32 (+0x148) | 1024 |
| `language_id` | u32 (+0x1D0) | `GW::Constants::Language` |

`TextParserStruct.get_file_slot(slot_idx, language)` → `TextFileSlotStruct`
(`file_hash`, `lang_id`, `start_index`, `end_index`). Used to map string ids → dat files.

---

# Summary matrix

| Context (Python facade) | Struct | Reader | SSM field | `GWContext` member |
|---|---|---|---|---|
| `GameContext.py` (no facade) | `GameContextStruct` | manual SSM cast | `GameContext` | — (raw only) |
| `AgentArray` | `AgentArrayStruct` (+Agent hierarchy) | scan | — | `AgentArray` |
| `AccAgentContext` | `AccAgentContextStruct` | SSM | `AgentContext` | `AccAgent` |
| `AvailableCharacterArray` | `AvailableCharacterArrayStruct` | SSM | `AvailableCharacters` | `AvailableCharacterArray` |
| `CharContext` | `CharContextStruct` | SSM | `CharContext` | `Char` |
| `WorldContext` | `WorldContextStruct` | SSM | `WorldContext` | `World` |
| `MapContext` | `MapContextStruct` | SSM | `MapContext` | `Map` |
| `MissionMapContext` | `MissionMapContextStruct` | SSM | `MissionMapContext` | `MissionMap` |
| `WorldMapContext` | `WorldMapContextStruct` | SSM | `WorldMapContext` | `WorldMap` |
| `PartyContext` | `PartyContextStruct` | SSM | `PartyContext` | `Party` |
| `GuildContext` | `GuildContextStruct` | SSM | `GuildContext` | `Guild` |
| `GameplayContext` | `GameplayContextStruct` | SSM | `GameplayContext` | `Gameplay` |
| `InstanceInfo` | `InstanceInfoStruct` | scan | (n/a) | `InstanceInfo` |
| `ServerRegion` | `ServerRegionStruct` | SSM | `ServerRegionContext` | `ServerRegion` |
| `Cinematic` | `CinematicStruct` | SSM | `CinematicContext` | `Cinematic` |
| `PreGameContext` | `PreGameContextStruct` | SSM | `PreGameContext` | `PreGame` |
| `TextParser` | `TextParserStruct` | derived (GameContext+0x18) | via `GameContext` | — (raw only) |

**Demo recommendation:** import `from Py4GWCoreLib.Context import GWContext`; iterate the
15 wrapper members calling `.IsValid()` / `.GetContext()`; for `GameContext` and
`TextParser` fall back to their module facades. Render encoded-string fields via both
`*_encoded_str` and `*_str`, and expand `GW_Array`/`GW_TList` members lazily through
their `.<name>` decoding properties (they return `None`/`[]` when not in an instance).
