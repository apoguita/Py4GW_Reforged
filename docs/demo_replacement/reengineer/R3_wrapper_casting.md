# R3 — Wrapper Casting Recipes (raw return → proper cast → readable fields)

**Purpose.** The current debug tool's central defect is that when a binding returns a
struct/object/handle, it renders a raw **memory address** (or a bare int id) instead of the
casted, field-level data. This document is the reference for the reengineered tool: for each
domain it gives the **cast recipe** — *raw binding return → the proper cast → readable fields,
with enum-name resolution* — and explicitly flags every **"address / bare-id instead of object"
trap** (a value that is meaningless on its own and MUST be passed to another call or dereferenced
through a context struct).

Companion docs (read alongside): `docs/demo_replacement/08_contexts.md` (context struct
inventory & layouts) and `docs/demo_replacement/10_python_wrapper_api.md` (per-domain public API
surface). This doc adds the *how the cast happens* layer those two omit.

---

## 0. The four cast mechanisms used across the whole codebase

Every readable value in Py4GW is produced by one (or a chain) of these four mechanisms. The
reengineered tool should implement each as a rendering strategy and pick per field.

### M1 — ctypes reinterpret cast: `pointer → POINTER(Struct).contents` (Context path)
A raw 32-bit address becomes a populated struct with named fields via ctypes. This is the
canonical fix for "address instead of object". Machinery
(`native_src/context/CharContext.py:227-230`):

```python
CharContext._cached_ctx = cast(ptr, POINTER(CharContextStruct)).contents
```

- **Where `ptr` comes from:** the Native DLL publishes a `Pointers_SHMemStruct` over shared
  memory (`native_src/ShMem/structs/PointersSSM.py`). Each context facade reads its field from
  `SystemShaMemMgr.get_pointers_struct().<Field>` in a `_update_ptr()` that runs every frame on a
  `PyCallback` `PreUpdate` phase (`CharContext.py:217-241`). Two contexts pattern-scan instead
  (`InstanceInfo`, `AgentArray`).
- **How a demo reads it:** `Facade.get_context()` returns the cached `.contents` struct, or the
  unified facade `GWContext.<Name>.GetContext()` / `.IsValid()` (`Context.py:35-46`). Both return
  the *same* ctypes struct.
- **Nested pointers deref the same way:** struct fields typed `POINTER(SubStruct)` expose a
  `@property` that returns `self.<field>_ptr.contents` (e.g. `CharContext.progress_bar`,
  `CharContext.py:176-181`). A null pointer → the property returns `None`.
- **Snapshot pattern:** many structs offer `.snapshot()` returning a frozen `@dataclass` deep-copy
  (e.g. `DyeInfoStruct.snapshot()`, `ItemDataStruct.snapshot()` in `AgentContext.py:38-76`) — a
  Python-owned copy safe to hold past the frame.

### M2 — Enum int → human name (the `Enum(int)` → `_Names[enum]` idiom)
A raw int field is wrapped in an `IntEnum`, then a parallel `_Names` dict (or the enum's `.name`)
maps it to a display string. Canonical example (`Agent.GetProfessionNames`, `Agent.py:797-807`):

```python
from .enums_src.GameData_enums import Profession, Profession_Names
profession = Profession(living.primary)          # int -> IntEnum
prof_name  = Profession_Names[profession]        # IntEnum -> str
```

Wrappers typically return the **`(id, name)` tuple** so both are visible (e.g.
`Agent.GetAllegiance` → `(int, str)`, `Agent.py:1420-1433`; `Map.GetRegion` → `(id, name)`,
`Map.py:259-268`). Guard against `ValueError` for unknown ints → `"Unknown"`.

- **Enum source of truth:** `Py4GWCoreLib/enums_src/*.py` (18 files), re-exported by
  `Py4GWCoreLib/enums.py`. The `_Names` dicts live next to their enums (e.g. `Profession_Names`,
  `ProfessionShort_Names`, `Weapon_Names`, `AllegianceNames` in `GameData_enums.py`;
  `InstanceTypeName`, `ServerRegionName`, `RegionTypeName`, `CampaignName`, `ContinentName` in
  `Map_enums.py`/`Region_enums.py`; `outposts`/`explorables` map-id→name in `Map_enums.py`).
- **Native-side variant:** some handles carry their own `.GetName()` and `.ToInt()` (see M4);
  those bypass the Python `_Names` dict.
- **Tool implication:** a generic renderer can key on field name → known enum type and resolve the
  int to a name. Build a field→enum registry from `enums.py`.

### M3 — Encoded wide-string decode (`*_encoded_str` / `*_str`)
GW stores names/messages as *encoded* wide strings. Structs expose paired accessors: the raw
encoded form and a decoded readable form (`CharContext.player_name_encoded_str` vs
`player_name_str`, `CharContext.py:182-192`). Helpers (`native_src/internals/helpers.py`):
- `read_wstr(ptr)` → `ctypes.wstring_at` a `wchar_t*`.
- `encoded_wstr_to_str(s)` → escapes GW control chars to readable `\xXXXX`.
For agent names the pipeline differs: `PyAgent.get_agent_enc_name(id)` returns raw bytes, decoded
via `native_src/internals/string_table.decode` (`Agent.GetNameByID`, `Agent.py:142-147`).
**Tool implication:** always render both encoded and decoded; a raw `wchar_t*` field is an address
until `read_wstr`.

### M4 — Native handle → accessor calls (`Py*` binding objects)
Bindings-path wrappers build a **handle from a bare int id** (`PyItem.PyItem(item_id)`,
`PySkill.Skill(skill_id)`, `PyEffects.PyEffects(agent_id)`, `PyCamera.PyCamera()`). The handle
carries **no data** until you call an accessor. Handles often nest: a field is itself a handle
requiring a further call (`skill.id.GetName()`, `skill.type.id`). See per-domain traps.
**Tool implication:** never `repr()` a `Py*` handle — it prints an address. Enumerate its known
accessors and call them.

---

## 1. Context path (ctypes structs) — `native_src/context/*.py` + `Context.py`

**Cast recipe (M1).** `GWContext.<Name>.GetContext()` → the ctypes struct (already
`.contents`-dereferenced and cached per frame). Fields are read directly; sub-pointers via their
`.<name>` property; arrays via `GW_Array` / `GW_TList` view helpers; strings via M3.

- **Facade:** `Context.py` `GWContext` exposes 15 contexts as nested `_GWContextBase[TStruct]`
  classes, each with `GetPtr()`, `GetContext()`, `IsValid()` (`Context.py:25-115`). `InstanceInfo`
  additionally exposes `GetMapInfo() → AreaInfoStruct` (`Context.py:82-86`).
- **Not in `GWContext` (raw-only):** `GameContext` (no facade — manual
  `cast(SSM.GameContext, POINTER(GameContextStruct)).contents`) and `TextParser` (derived from
  `GameContext + 0x18`). See `08_contexts.md §GameContext / §TextParser`.
- **Array element deref:** `GW_Array_View(arr, T)` iterates an `Array<T*>` (derefs each pointer
  element); `GW_Array_Value_View(arr, T).to_list()` iterates an `Array<T>` value array;
  `GW_TList_View(list, T)` walks an intrusive linked list. Element structs expose their own
  `.contents` via a property (e.g. `CharContext.observer_matches`, `CharContext.py:167-175`,
  returns `[ptr.contents for ptr in ptrs]`).

**Full struct layouts, SSM field names, and sub-struct trees are catalogued in
`08_contexts.md`** (do not duplicate here). The casting-relevant summary:

| Trap in context path | What the raw value is | Proper cast |
|---|---|---|
| A context pointer field (e.g. `GameContextStruct.map_context`) | a `uint32` address | `cast(ptr, POINTER(MapContextStruct)).contents` |
| `POINTER(SubStruct)` field (`progress_bar_ptr`) | address | `.progress_bar` property → `.contents` (or `None`) |
| `POINTER(c_wchar)` field (`team_name1_ptr`) | address | `.team_name1_str` (M3: `read_wstr`+decode) |
| `GW_Array` field | `{buffer_ptr, capacity, size}` | `.<name>` property → `GW_Array[_Value]_View(...).to_list()` |
| `GW_TList` field | intrusive list head | `.<name>` property → `GW_TList_View(...)` |
| encoded `wchar[N]` field | packed encoded bytes | `.<name>_str` (M3 decode) |
| enum-typed `uint32` (e.g. `AreaInfoStruct.campaign`, `region`) | int | M2 `Enum(int)` + `_Names` dict |

> Most `WorldContext` array properties return `None` outside an instance — render lazily and
> tolerate `None`/`[]`.

---

## 2. Agent — `Agent.py`

**Backend.** Wraps `PyAgent` module functions + reads `AgentStruct`/`AgentLivingStruct`/
`AgentItemStruct`/`AgentGadgetStruct` from the Context path (via `AgentArray`). Per-frame property
cache invalidated on `PreUpdate` (`Agent.py:45-60`).

**Cast recipe.**
1. `Agent.GetAgentByID(id)` → base `AgentStruct` (from `AgentArray.GetAgentByID`, `Agent.py:62-71`;
   the array ptr is resolved by pattern scan, not SSM).
2. **Reinterpret-cast to the concrete subtype** via the native struct's own cast methods — this is
   the key widening step (`Agent.py:84-139`):
   - `agent.GetAsAgentLiving()` → `AgentLivingStruct` (players/NPCs/monsters) —
     `Agent.GetLivingAgentByID`.
   - `agent.GetAsAgentItem()` → `AgentItemStruct` (dropped items).
   - `agent.GetAsAgentGadget()` → `AgentGadgetStruct` (signposts/chests).
   The correct subtype is determined by `AgentStruct.type` (bitfield: item `0x400` / gadget
   `0x200` / else living). A tool must pick the cast from `type`, else it shows only base fields.
3. **Read fields** off the living struct (`living.hp`, `living.energy`, `living.primary`, …).
4. **Resolve enums (M2):**
   - Professions: `Profession(living.primary)` + `Profession_Names[...]`
     (`GetProfessionNames`, `Agent.py:790-807`); short form via `ProfessionShort`/
     `ProfessionShort_Names` (`Agent.py:809-826`).
   - Allegiance: `Allegiance(living.allegiance)` + `AllegianceNames.get(...)` →
     `(id, name)` (`Agent.py:1420-1433`).
5. **Names (M3):** `PyAgent.get_agent_enc_name(id)` (raw bytes) → `string_table.decode(...)`
   (`GetNameByID`, `Agent.py:142-147`). Encoded debug form via `GetEncNameStrByID`
   (`Agent.py:161-179`).
6. **Coordinates:** `GetXY`/`GetXYZ`/`GetZPlane` read `pos` (`GamePos`); velocity (`Vec2f`),
   terrain normal (`Vec3f`), name-tag XYZ read struct vector fields directly.

**Traps (address / bare-id instead of object):**
- **The base `AgentStruct` is the trap the current tool hits.** Rendering `GetAgentByID` shows only
  base fields (or a struct address); the rich data lives in the `AgentLivingStruct` you only get
  after `GetAsAgentLiving()`. Always widen by `type`.
- `GetOwnerID` / `GetCastingTarget` / target ids etc. return **bare agent ids** — meaningless
  until passed back to `Agent.*` (`GetNameByID`, etc.).
- Many combat/stance/target getters are **stubbed** (hard-return `0/False/[]` pending the
  CombatEvents migration) — see `10_python_wrapper_api.md §Agent`. The tool should mark these
  "not yet wired", not display `0` as real.

---

## 3. AgentArray — `AgentArray.py`

**Cast recipe.** Array getters read from shared memory
(`SystemShaMemMgr.get_agent_array_wrapper`) and return **flat `list[int]` of agent ids**;
single-agent lookup (`GetAgentByID`) returns an `AgentStruct` via the Context path. The
`AgentArrayStruct` (Context path) builds cached allegiance lists
(`GetAllyArray/GetEnemyArray/GetItemAgentArray/…`, see `08_contexts.md §AgentContext`).
Manipulation/Sort/Filter/Routines sub-namespaces are pure in-Python transforms over id lists.

**Trap:** every element is a **bare agent id** — an inspector shows `[123, 456, …]`, not agents.
Each must be fed to `Agent.*` to become readable. This is the array analog of the Agent trap.

---

## 4. Player — `Player.py`

**Backend.** Reads the **Context path** (`GWContext.Char / World / Party`) for nearly all data;
`PyPlayer` (`player_instance`) only for a few live values + action/chat. Getters `@frame_cache`d.
No `GLOBAL_CACHE.Player` exists.

**Cast recipe.**
- **Context deref + de-obfuscation (dominant idiom):**
  ```python
  if (world_ctx := GWContext.World.GetContext()) is None: return 0   # Player.py:358-360
  return max(world_ctx.morale, world_ctx.morale_dupe)                # "dupe" pairs -> max()
  ```
  Faction/experience/level/kurzick/luxon all use the `max(value, value_dupe)` de-obfuscation
  (e.g. `GetKurzickData`, `Player.py:533-536`). Char fields: `GetPlayerNumber`
  (`Player.py:89-91`), email via `char_ctx.player_email_str` (M3, `Player.py:285`).
- **Enum (M2) — only one:** `PlayerStatus.from_value(status).display_name` (friend-list status),
  in `GetPlayerStatusNameFromValue` (`Player.py:23-25`) and `GetPlayerStatusName`
  (`Player.py:661-667`, resolving the raw int from the Methods-path `PlayerMethods.GetPlayerStatus`).
  Profession/title/faction are returned as **raw ints**, not names.
- **Names:** `GetName` does not read a name field — it passes the own agent id to
  `Agent.GetNameByID(...)` (`Player.py:190-199`).

**Traps:**
- `GetTitleArrayRaw()` (`Player.py:602-613`) returns raw `TitleStruct` objects (addresses if
  printed). `GetTitleArray()` (`Player.py:617-631`) returns only **indices**, and
  `GetActiveTitleID()` (`Player.py:580-600`) / `GetTitle(title_id)` (`Player.py:634-646`) treat
  `title_id` as an **array index**, not a game id.
- `GetControlledMinions()` (`Player.py:482-496`) → `list[(agent_id, count)]` — `agent_id` is a bare
  handle.
- `GetAgentID` / `GetTargetID` / `GetObservingID` return **bare agent ids** (feed to `Agent.*`).
- `GetPlayerUUID()` → 4-int tuple, meaningless until formatted (`_format_uuid_as_email`,
  `Player.py:60-68`).
- Missions getters return raw `world_ctx.*` **bitfield array handles**, not decoded names.

---

## 5. Item — `Item.py`

**Cast recipe (M4 + M2).** `Item.item_instance(item_id)` → `PyItem.PyItem(item_id)`
(`Item.py:44-51`) — a handle **rebuilt from a bare int every call**; no data until a field read.
- **Type (native name):** `GetItemType` → `(item_type.ToInt(), item_type.GetName())`
  (`Item.py:114-117`) — name from native `ItemTypeClass.GetName()`. Callers re-wrap the int with
  the Python `ItemType(...)` IntEnum for predicates (`Item.py:123, 268`).
- **Rarity (native enum):** `Item.Rarity.GetRarity` → `(rarity.value, rarity.name)`
  (`Item.py:192-196`); predicates compare `.name == "White"` etc.
- **Attribute (M2):** `GetRequirement` returns `(requirement.attribute, level)` where `.attribute`
  is the `Attribute` enum, produced by `ItemModifierParser(...).get_properties()` (`Item.py:264-276`).
- **DyeColor:** `GetDyeColor` walks modifiers and returns the first non-zero `mod.GetArg1()` as a
  raw `DyeColor` int (`Item.py:172-190`).

**Traps (this domain is the richest source of the bug):**
- **`PyItem(item_id)` handle** — repr shows an address; every getter reinstantiates it.
- **Three distinct id spaces, not interchangeable:** `item_id`, `agent_id` (`.agent_id`),
  `agent_item_id` (`.agent_item_id`). Item↔agent linkage requires a **bag scan**
  (`GetItemByAgentID`, `Item.py:79-97`).
- **`model_id` / `model_file_id` are non-unique type ids** — resolved only by scanning bags
  (`GetItemIdFromModelID`, `Item.py:63-77`) or expanding composite tables
  (`GetCompositeModelIDs`/`GetTrueModelFileID`, `Item.py:141-165`).
- **Modifiers are opaque bit-packed structs** (`List[ItemModifier]`) — readable only after
  `GetArg*/GetIdentifier` or full `ItemModifierParser` parsing (`Item.py:436-459, 278-314`). A
  tool printing the modifier list shows objects, not the packed mod values.

---

## 6. ItemArray — `ItemArray.py`

**Cast recipe.** Produces **flat `list[int]` of item_ids** by iterating
`PyInventory.Bag(bag_enum.value, bag_enum.name).GetItems()` and taking `item.item_id`
(`ItemArray.py:28-55`). Bag ints → local `Bag` enum via `Bag(bag_id)` (`ItemArray.py:9-26`).
Filter/Sort dynamically dispatch to `Item.*` by attribute-name string (`getattr(Item, attr)`),
so typed values come from the referenced `Item` method.

**Traps:** every element is a **bare item_id** — meaningless until fed to
`Item.item_instance(item_id)`. `GetBag` returns a live `PyInventory.Bag` **handle**, not item data.
Note **two parallel Bag enums** with different member names: `Bag` (`Item.py:16`, used here) vs
`Bags` (`Item_enums.py:43`, used by Inventory).

---

## 7. Inventory — `Inventory.py`

**Cast recipe.** Two raw handles: `PyInventory.PyInventory()` (gold/space/actions) and per-bag
`PyInventory.Bag(...)`. Bag membership via the `Bags` IntEnum (`Item_enums.py:43`). Item-level
typing delegated to `Item`/`ItemArray`; gold/space are plain ints. Salvage-dialog code resolves
**UIFrame handles → screen geometry** (`PyUIManager.UIFrame(frame_id).position.left_on_screen`…,
`Inventory.py:549-569`), with frame ids from `UIManager.GetFrameIDBy*`.

**Traps:**
- **`item_id` vs `agent_id` at API boundaries:** `PickUpItem(item_id)` explicitly `# (not agent_id)`
  (`Inventory.py:1300-1309`); `EquipItem(item_id, agent_id)` takes **both** (`Inventory.py:1322-1331`).
- **model_id counting = full bag scan** (`GetModelCount*`, `Inventory.py:165-235`).
- **`FindItemBagAndSlot(item_id)`** derives (bag, slot) by scanning — not stored on the handle
  (`Inventory.py:1423-1444`).
- Move/deposit/withdraw join stacks by **model_id across freshly-read bag handles**
  (`Inventory.py:1446-1592`).
- **Frame ids are transient handles** — re-validated with `UIManager.FrameExists` before each use.

---

## 8. Merchant / Trading — `Merchant.py`

**Cast recipe.** The **thinnest wrapper — essentially no casting, no enum decoding.**
`Trading.merchant_instance()` → `PyMerchant.PyMerchant()`. All list getters return raw
`list[int]` of item_ids; quote getters return ints; transaction state a bool. `TradingNPCType`/
`TraderType` enums exist (`Item_enums.py:218-230`) but are **not used** here.

**Traps:**
- **Offered-item lists are bare `list[int]` item_ids** — pass each to `Item.item_instance(...)`.
- **Quote is an async request→poll handshake, not a return value:** `RequestQuote(item_id)` /
  `RequestSellQuote(item_id)` return `None`; the price appears later via `GetQuotedItemID()` +
  `GetQuotedValue()` (`Merchant.py:28-45, 69-87`). A tool that calls `RequestQuote` and expects a
  price gets nothing.
- Buy/Sell take `(item_id, cost)` as separate ints (caller supplies quoted value).
- Crafter/Collector `GetOfferedItems` alias `get_merchant_item_list()` (same binding call).

---

## 9. Skill — `Skill.py`

**Cast recipe (M4 native-handle chain + one M2 dict + local JSON).**
`Skill.skill_instance(skill_id)` → `PySkill.Skill(skill_id)` (`Skill.py:17-19`), rebuilt each call.
Fields include **nested handles** `.id: SkillID`, `.type: SkillType`, `.profession: Profession`.
- **Name:** `GetName` → `skill_instance.id.GetName()` (double hop: `.id` is a `SkillID` handle,
  `.GetName()` the native string) (`Skill.py:22-24`). Raw int via `.id.id` (`GetID`,
  `Skill.py:66-68`).
- **Type:** `GetType` → `(type.id, type.GetName())` (`Skill.py:82-85`). All `Is*` flag helpers
  (`Skill.py:262-405`) string-compare `GetType(id)[1]`.
- **Profession:** `GetProfession` → `(profession.ToInt(), profession.GetName())`
  (`Skill.py:94-97`).
- **Campaign (the only Python dict, M2):** `GetCampaign` → `CampaignName.get(campaign, "Unknown")`
  (`Skill.py:87-92`; `Region_enums.py`).
- **Local JSON:** `skill_descriptions.json` (cached in `Skill._desc_cache`, `Skill.py:9-15`) feeds
  `GetNameFromWiki`/`GetURL`/`GetDescription`/`GetProgressionData`. Texture path via
  `SkillTextureMap` dict (`Texture_enums.py`), `ExtraData.GetTexturePath` (`Skill.py:499-503`).

**Traps:**
- `PySkill.Skill(skill_id)` handle — address if printed.
- Nested handles: `.id` (need `.id.id` or `.id.GetName()`), `.type` (need `.type.id`/
  `.type.GetName()`), `.profession` (need `.ToInt()`/`.GetName()`).
- `Attribute.GetAttribute` (`Skill.py:180-184`) returns the raw `AttributeClass` **handle with no
  cast** — leaks the object straight through.

---

## 10. Skillbar — `Skillbar.py`

**Cast recipe.** `PySkillbar.Skillbar()` (rebuilt per call, reads local player bar).
`GetSkillIDBySlot` → `skillbar.GetSkill(slot).id.id` — the double `.id.id` unwraps
`SkillbarSkill → SkillID → int` (`Skillbar.py:109-119`). Stays in the int domain; defers naming
to `Skill`.

**Traps:**
- `GetSkillData(slot)` (`Skillbar.py:137-146`) returns the **raw `SkillbarSkill` object** (address
  if printed); its `.id` is a `SkillID` object needing `.id.id`.
- `GetHeroSkillbar(hero_index)` returns `List[SkillbarSkill]` — a list of handles.
- Naming asymmetry: `GetHoveredSkillID` does return a plain int, but `GetSkillData` returns a
  handle — the tool must know which is which.

---

## 11. Effect — `Effect.py`

**Cast recipe.** `Effects.get_instance(agent_id)` → `PyEffects.PyEffects(agent_id)`
(`Effect.py:6-14`). Producers `GetEffects() → List[EffectType]` and `GetBuffs() → List[BuffType]`
return native structs whose fields (`skill_id`, `buff_id`, `time_remaining`, `attribute_level`)
are the readable surface. **No enum-name casting at all** — everything stays numeric.

**Traps — the classic id-space split:**
- A buff (`BuffType`) has BOTH `skill_id` (producing skill) and `buff_id` (runtime instance
  handle). `GetBuffID(skill_id)` translates: match `buff.skill_id`, return `buff.buff_id`
  (`Effect.py:138-149`). **`DropBuff(buff_id)` requires the `buff_id`, NOT the skill_id**
  (`Effect.py:16-25`) — passing a skill_id silently fails.
- Effects are keyed by `skill_id` (`EffectExists`/`GetEffectTimeRemaining`, `Effect.py:88-136`) —
  a different key than buffs' `buff_id`. `EffectType` also carries an unused `effect_id`.
- `PyEffects(agent_id)` instance is an address; only its list contents are real data.

---

## 12. Quest — `Quest.py`

**Cast recipe.** `Quest.quest_instance()` → `PyQuest.PyQuest()`. `get_quest_data(quest_id)` returns
a `QuestData` struct (raw ids + `marker_x/y` floats + already-resolved strings). No enum casting;
readability comes from an **async request/ready/get triad**.

**Traps — the async-id trap:**
- `GetActiveQuest`/`GetQuestLogIds` return **bare quest_id ints** (`Quest.py:8-15, 85-92`) — no
  synchronous name/description.
- Every text field is a **3-call triad driven in order:** `RequestQuest*` (fire async) →
  `IsQuest*Ready` (poll) → `GetQuest*` (read). For Name/Description/Objectives/Location/NPC
  (`Quest.py:105-243`). Calling `GetQuestName` before the request → empty/stale; a tool that just
  calls the getter reports the quest as nameless. `RequestQuestInfo` is the umbrella prefetch
  (`Quest.py:94-103`).
- `GetQuestData(quest_id)` returns the raw `QuestData` object; string fields populated only after
  requests complete.

---

## 13. Map — `Map.py`

**Cast recipe.** Three sources: **Char context** (`current_map_id`, district, language), the
**InstanceInfo→AreaInfo deref** (`GWContext.InstanceInfo().GetMapInfo() → AreaInfoStruct`), and
**module-level `{int:str}` dict tables** for names.
- **Enum name dicts (M2), all returning `(id, name)`:** `GetInstanceTypeName` →
  `InstanceTypeName.get(...)` (`Map.py:63-67`); `GetRegion` → `ServerRegionName[...]`
  (`Map.py:259-268`); `GetRegionType` → `RegionTypeName[...]`; `GetLanguage` →
  `ServerLanguageName[...]`; `GetCampaign` → `CampaignName[...]`; `GetContinent` →
  `ContinentName[...]` (`Map.py:408-435`).
- **Map name (id → lookup table):** `GetMapName(map_id)` looks the id up in `outposts` /
  `explorables` dicts (`Map.py:141-160`); `GetMapID()` alone is a bare int (`Map.py:118-124`).
  Seasonal variants: `GetBaseMapID`/`GetAllMapVariants` (`Map.py:186-226`).
- **AreaInfo deref idiom:** `ai = GWContext.InstanceInfo().GetMapInfo(); if None: return 0; return
  ai.<field>` (e.g. `GetMaxPartySize`, `GetFlags`). `GetUnloadedMapInfo(map_id)` is the
  Methods-path escape hatch returning an `AreaInfoStruct` for any map (`Map.py:695-702`).

**Traps:**
- **`GetNameID()` / `GetDescriptionID()`** (`Map.py:654-668`) return raw **string-table ids**, not
  text — must be handed to a string decoder. Map never resolves these itself.
- `GetMapID()` needs `GetMapName` lookup; `GetThumbnailID`/`GetFileID*`/`GetControlledOutpostID`/
  `GetMissionMapsTo` return raw asset/handle ids.
- `IsMapUnlocked` bit-indexes a raw **bitfield array handle** (`world_ctx.unlocked_maps`,
  `Map.py:491-515`).
- `GetInstanceType()` returns a raw int — call `GetInstanceTypeName()` for the string.

---

## 14. Camera — `Camera.py`

**Cast recipe.** Thin passthrough over `PyCamera.PyCamera()` fields. **Near-zero enum content** —
floats, vectors, one handle. Vector fields unpacked to float tuples: `GetPosition` →
`position.x, position.y, position.z` (`Camera.py:171-176`); same for `GetLookAtTarget` etc.

**Trap:** `GetLookAtAgentID()` (`Camera.py:12-17`) returns a bare **agent handle** — feed to
`Agent.*`. Everything else is directly meaningful floats.

---

## 15. GlobalCache getters — do they cast richer? **No.**

**Answer to the R3 question:** `GLOBAL_CACHE.<Domain>` getters do **not** return richer casted
objects than the base wrappers. They **mirror** the same returns with added throttled caching and
action-queue-backed setters.
- Cache objects exist only for a subset: `Camera, Effects, Item, Inventory, Trading, Party, Quest,
  Skill, SkillBar, ShMem` (`GlobalCache/GlobalCache.py:29-46`). **No `PlayerCache`, no `MapCache`**
  — callers hit the base `Player`/`Map` wrappers directly (which self-memoize via `@frame_cache`).
- Example: `CameraCache.GetPosition` returns `self._camera_instance.position.x, .y, .z` — identical
  to `Camera.GetPosition`. Same `look_at_agent_id` handle trap.
- The only value-add is **lifecycle**: (a) the cached `Py*` context refreshed on a ~150ms throttle
  (`GlobalCache.py:78`); (b) setters routed through `ActionQueueManager` instead of direct calls.

**Implication for the tool:** the "richness" (enum→name, `(id,name)` tuples, context deref,
string-table lookups) is applied **once, in the base `Py4GWCoreLib` wrappers**. The reengineered
tool should call the **base wrappers**, not the raw `Py*` bindings, and not expect GlobalCache to
upgrade a raw pointer/id into a resolved object — the traps below are present identically at both
layers.

---

## 16. Top casting patterns (implement these as renderer strategies)

1. **Reinterpret cast (M1):** `cast(ptr, POINTER(Struct)).contents` turns an address into a
   named-field struct. Nested pointers deref via `.<name>` properties; null → `None`. This is the
   direct fix for the tool's core defect. Source of ptrs: `Pointers_SHMemStruct` over shared
   memory, or pattern scan (`AgentArray`, `InstanceInfo`).
2. **Subtype widening:** a base struct/handle must be widened before rich fields exist —
   `AgentStruct.GetAsAgentLiving/Item/Gadget()` chosen by `type`; `PyItem` type/rarity via native
   `.GetName()`. Rendering the base only = the current bug.
3. **Enum int → name (M2):** `EnumType(int)` then `EnumType_Names[enum]` (or native `.GetName()`),
   returned as an `(id, name)` tuple. Build a field→enum registry from `enums.py` /
   `enums_src/*.py`.
4. **Encoded string decode (M3):** render both `*_encoded_str` and `*_str`
   (`read_wstr` + `encoded_wstr_to_str`, or `string_table.decode` for agent names).
5. **Handle → accessor calls (M4):** never `repr()` a `Py*` handle; enumerate and call its
   accessors. Handles nest (`skill.id.GetName()`, `skill.type.id`).
6. **Array/list view deref:** `GW_Array_View`/`GW_Array_Value_View`/`GW_TList_View` +
   per-element `.contents`.

## 17. Biggest "address / bare-id instead of object" traps (rank-ordered)

1. **Context pointer fields** (`GameContextStruct.*_context`, `progress_bar_ptr`, `*_ptr`) — raw
   `uint32` addresses; must be `cast(POINTER(Struct)).contents`. (§1)
2. **Base `AgentStruct` without widening** — the demo's most visible failure; rich data needs
   `GetAsAgentLiving()` selected by `type`. (§2)
3. **`Py*` handles built from a bare int** (`PyItem(item_id)`, `PySkill.Skill(id)`,
   `PyEffects(agent_id)`) — repr = address; data only via accessors, and accessors nest. (§5, §9, §11)
4. **Cross-id linkage that requires another call/scan:** `item_id` vs `agent_id` vs
   `agent_item_id`; `model_id` needing a bag scan; buff `skill_id` vs `buff_id`; title/minion
   agent ids; camera/target `look_at_agent_id`. A bare id renders as a number. (§5, §7, §11, §4, §14)
5. **String-table ids** (`Map.GetNameID`/`GetDescriptionID`, agent enc names) — ints that decode
   to text only through a string decoder. (§13, §2/M3)
6. **Async request/poll values** (Merchant quotes, Quest text triads) — the value is not the return
   of the call you made; it arrives on a *later* getter after a request + ready poll. (§8, §12)
7. **Raw struct/bitfield array handles** (`Player.GetTitleArrayRaw`, missions/`unlocked_maps`
   bitfields, `Skillbar.GetSkillData`) — objects/arrays printed as addresses; index/decode needed. (§4, §10, §13)
8. **Stubbed getters** returning `0/False/[]` (Agent combat/target set) — not real data; mark as
   "not yet wired". (§2)
