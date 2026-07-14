# R1 — Original Demo Patterns (gold-standard call + cast + render recipes)

Purpose: capture the EXPLICIT patterns the original demos use to **access → cast → render** every
domain of game data, so DEMO 2.0's reengineer can mirror them faithfully. This is a per-method
reference, not an auto-discovery/reflection design. The whole point is that the good originals
**dereference struct returns into named fields and typed values** instead of printing raw objects.

Sources read in full:
- `Widgets/Coding/Py4GW_DEMO.py` — v1 legacy monolith (13 domains). Uses `ImGui_Legacy.table()` + `GLOBAL_CACHE.*`.
- `Py4GW DEMO 2.0.py` — v2 host (left nav child + right content child, `registry.draw_sidebar/draw_content`).
- `Sources/ApoSource/py4gw_demo_src/map_demo.py` — **model module** (proper, non-shortcut).
- `Sources/ApoSource/py4gw_demo_src/agent_demo.py` — **model module** (proper, non-shortcut).
- `Sources/ApoSource/py4gw_demo_src/pathing_map_demo.py` — **model module** (canvas render).
- `Sources/ApoSource/py4gw_demo_src/helpers.py` — `draw_kv_table` + `MapVars`/`DisplayNode` config.
- `Sources/ApoSource/py4gw_demo_src/registry.py` — grouped section dispatch.
- `Sources/ApoSource/py4gw_demo_src/ui.py` — v2 shared primitives (`draw_kv_table`, `draw_multi_table`, probe harness, `fmt_value`, reflection). **This is where the current tool's "raw address" divergence originates.**

---

## 0. The two rendering primitives (the whole casting story hinges on these)

### 0a. Legacy: `ImGui_Legacy.table(id, headers, data)`
v1 builds a Python `list[tuple]` of already-formatted cells and hands it to `ImGui_Legacy.table`.
Casting is done inline in the tuple construction, e.g.:
```python
headers = ["Value", "Data"]
data = [
    ("Current Ping:", current_ping),
    ("Elapsed Time:", elapsed_time),
]
ImGui_Legacy.table("PingHandler info", headers, data)
```

### 0b. Reforged model: `helpers.draw_kv_table` / `ui.draw_kv_table` / `ui.draw_multi_table`
Both do the same thing: iterate rows, `PyImGui.text_unformatted(str(cell))` per cell. Signatures:
```python
draw_kv_table(table_id: str, rows: list[tuple[str, str|int|float]])   # 2-col Field/Value
draw_multi_table(table_id: str, headers: list[str], rows: list[tuple]) # N-col
```
**Critical:** both stringify with `str(cell)`. So the CAST must happen in the row-building code,
BEFORE the cell reaches the table. The model modules always pass pre-formatted strings:
`f"[{Map.GetMapID()}] - {Map.GetMapName()}"`, `f"({agent.pos.x:.2f}, {agent.pos.y:.2f}, {agent.z:.2f})"`.

### 0c. THE DIVERGENCE (root cause of "structs render as raw memory addresses")
`ui.fmt_value(v)` (used by the probe harness / reflection path) does:
```python
if isinstance(v, float):        s = f"{v:.3f}"
elif isinstance(v, (list,tuple)): s = f"{type(v).__name__}[{len(v)}] {v!r}"
elif isinstance(v, bytes):      s = v.hex()
else:                           s = repr(v) if not isinstance(v, str) else v
```
For a pybind11 struct (an `AgentStruct`, `TitleData`, `PetInfo`, gadget/item structs, dye objects,
`FrameInfo`, context structs) none of these branches match, so it falls to `repr(v)` →
`<PyAgent.AgentStruct object at 0x0000ABCD>`. The good demos NEVER pass a struct to a generic
formatter — they read `.field` and format each field. **The reengineer must do the same: per-struct
explicit field extraction, not a generic `str()`/`repr()` on the struct.** The probe/auto-discovery
harness (`auto_probe_entries`, `probe_entries_1arg`, `fmt_value`) is the anti-pattern to replace with
explicit per-method recipes.

---

## 1. Map / World

Model file: `map_demo.py` (this is the reference every other domain should look like).

### Access + cast — enum/id pairs resolved to `[id] - name`
`Map.Get*` that return a `(id, name)` tuple are ALWAYS unpacked into `[{id}] - {name}`:
```python
("Instance Type", Map.GetInstanceTypeName()),
("Current Map",   f"[{Map.GetMapID()}] - {Map.GetMapName()}"),
("Region",        f"[{Map.GetRegion()[0]}] - {Map.GetRegion()[1]}"),
("Region Type",   f"[{Map.GetRegionType()[0]}] - {Map.GetRegionType()[1]}"),
("Campaign",      f"[{Map.GetCampaign()[0]}] - {Map.GetCampaign()[1]}"),
("Continent",     f"[{Map.GetContinent()[0]}] - {Map.GetContinent()[1]}"),
("Language",      f"[{Map.GetLanguage()[0]}] - {Map.GetLanguage()[1]}"),
```
Time is cast with `FormatTime(Map.GetInstanceUptime(), 'hh:mm:ss:ms')` (from
`Py4GWCoreLib.py4gwcorelib_src.Timer`). v1 instead used `time.strftime('%H:%M:%S', time.gmtime(ms/1000))`.
An id that names another map is expanded: `f"{Map.GetMissionMapsTo()} - {Map.GetMapName(Map.GetMissionMapsTo())}"`.

Bools are just interpolated (`f"{Map.IsVanquishable()}"`) → "True"/"False". (v1's `ShowPyImGuiExtraMaplWindow`
used the nicer `f"{'Yes' if Map.HasEnterChallengeButton() else 'No'}"` idiom.)

### Iterate-all patterns
- `Map.WorldMap.GetParams()` → list of uint32; iterate with index into a 2-col table:
  ```python
  for i, val in enumerate(params):
      PyImGui.table_next_row(); PyImGui.table_next_column(); PyImGui.text(f"[{i:03d}]")
      PyImGui.table_next_column(); PyImGui.text(f"{val}")
  ```
- `Map.WorldMap.GetExtraData()` → dict; iterate `.items()` into a 2-col table.
- `Map.Pregame.GetAvailableCharacterList()` / `GetCharList()` → iterate `char` objects; each field is
  read explicitly (`char.player_name`, `char.map_id`, `char.primary`, `char.level`, `char.is_pvp`).
  Professions/campaign resolved via lookup dicts:
  `Profession_Names.get(Profession(char.primary), 'Unknown')`,
  `CampaignName.get(Campaign(char.campaign).value, 'Unknown')`.

### Struct casting — the pregame context (best "deref a big struct" example)
`Map.Pregame.GetContextStruct()` returns a ctypes-ish struct with ~50 named fields. The demo reads
EACH field by name into KV rows, with two helper casts:
```python
def _fmt_ptr(value) -> str:      # pointers as hex, not raw int
    return '0x0' if not value else f'0x{int(value):08X}'
rows = [
    ("scene_controller_iface", _fmt_ptr(context.scene_controller_iface)),
    ("camera_pitch_current",   f'{context.camera_pitch_current}'),
    ("RESERVED_0x1C",          f'{list(context.RESERVED_0x1C)}'),   # array → list()
    ("chars_array.m_buffer",   _fmt_ptr(context.chars_array.m_buffer)),  # nested struct field
    ...
]
```
Nested arrays are cast with `list(...)`; a byte GUID with `char.guild_guid.hex().upper()`.
**Takeaway for reengineer:** a struct panel = an explicit hand-written list of `(name, f"{struct.field}")`
rows, with `_fmt_ptr` for pointer-ish ints and `list()` for fixed arrays.

### Render frames / overlay (mission map, mini map)
`Map.MissionMap.GetFrameInfo()` returns a `FrameInfo` object stored in `map_vars.MissionMap.frame_info`;
its methods are called directly (`_FI.DrawFrameOutline(color.to_color(), thickness)`). Coordinate
projections use `Map.MissionMap.MapProjection.NormalizedScreenToScreen/…ToWorldMap/…ToGamePos(nx, ny)`.
Colors come from `Color`/`ColorPalette`; `.to_tuple_normalized()` for imgui pickers, `.to_color()` for
overlay draws. `DisplayNode` (in helpers) bundles `visible/color/thickness`.

### Actions
Action buttons here are plain `if PyImGui.button(...): Map.Travel(id)` /
`Map.TravelToRegion(map_id, region, district, language)` / `Map.EnterChallenge()` /
`Map.SkipCinematic()` etc., gated on state (`if not Map.IsInCinematic(): ...`).

---

## 2. Agents (living / item / gadget)

Model file: `agent_demo.py` (the gold standard for per-agent field extraction and colored bools).

### Nearest-entity acquisition (Reforged way)
```python
player        = Agent.GetAgentByID(Player.GetAgentID() or 0)          # -> AgentStruct | None
nearest_enemy = Agent.GetAgentByID(Routines.Agents.GetNearestEnemy() or 0)
nearest_ally  = Agent.GetAgentByID(Routines.Agents.GetNearestAlly() or 0)
nearest_item  = Agent.GetAgentByID(Routines.Agents.GetNearestItem() or 0)
nearest_gadget= Agent.GetAgentByID(Routines.Agents.GetNearestGadget() or 0)
nearest_npc   = Agent.GetAgentByID(Routines.Agents.GetNearestNPC() or 0)
target        = Agent.GetAgentByID(Player.GetTargetID() or 0)
```
(v1 legacy did it via `AgentArray.GetEnemyArray()` → `AgentArray.Sort.ByDistance(arr,(px,py))` →
`next(iter(arr), 0)`. Both patterns are valid; Reforged prefers `Routines.Agents.GetNearest*`.)

### Struct → row cast (`AgentStruct`)
The demo imports the struct types and treats `GetAgentByID` as returning a typed struct:
```python
from Py4GWCoreLib.native_src.context.AgentContext import AgentStruct, AgentLivingStruct, AgentItemStruct, AgentGadgetStruct
def _get_type(agent: AgentStruct) -> str:
    if agent.is_living_type: return "Living"
    if agent.is_item_type:   return "Item"
    if agent.is_gadget_type: return "Gadget"
    return "Unknown"
def _format_agent_row(label, agent: AgentStruct | None) -> tuple:
    if agent is None: return (label, "N/A", "N/A", "N/A", "N/A")
    return (label, agent.agent_id, Agent.GetNameByID(agent.agent_id),
            f"({agent.pos.x:.2f}, {agent.pos.y:.2f}, {agent.z:.2f})", _get_type(agent))
```
Note position comes from the nested `agent.pos.x/.y` + `agent.z` — explicit field deref, never `str(agent)`.

### Colored bool rendering (the good UX)
```python
def _colored_bool(value: bool) -> Tuple[int,int,int,int]:
    return Color(0,255,0,255).to_tuple() if value else Color(255,0,0,255).to_tuple()
PyImGui.text_colored("Is Living", _colored_bool(Agent.IsLiving(_AGENT_ID)))
```
Applied to dozens of status flags (Is Bleeding/Conditioned/Crippled/Dead/Enchanted/Hexed/Moving/
Casting/Attacking/Player/NPC…), each on its own `table_next_column()`. This is the pattern the
reengineer should reuse for every boolean field instead of printing "True".

### Wrapper getters used (living agent) — explicit, one call per cell
Positional: `Agent.GetXYZ(id)[0..2]`, `Agent.GetZPlane(id)`, `Agent.GetRotationAngle/Cos/Sin(id)`,
`Agent.GetVelocityXY(id)`, `Agent.GetNameTagXYZ(id)`, `Agent.GetTerrainNormalXYZ(id)` (player-only),
`Agent.GetGround(id)`. All `:.2f`.
Model/props: `Agent.GetModelScale1/2/3(id)` (→ width,height tuple), `Agent.GetNameProperties(id)`
and `Agent.GetVisualEffects(id)` rendered as **dec + `hex(...)` + `bin(...)`** across 3 columns.
Living: `GetOwnerID`, `GetPlayerNumber`, `GetAnimationCode`, `GetProfessions(id)`→(primary,secondary)
paired with `GetProfessionNames(id)` → `f"[{primary}] {primary_name}"`, `GetLevel`, `GetEnergy`,
`GetMaxEnergy`, `GetEnergyRegen`, `GetHealth`, `GetMaxHealth`, `GetHealthRegen`, `GetLoginNumber`,
`GetDaggerStatus`, `GetAllegiance(id)` → `f"{...[0]} ({...[1]})"`, `GetWeaponType(id)` → `(id,name)`,
`GetWeaponItemType`, `GetOffhandItemType`, `GetWeaponExtraData(id)` → tuple indexed `[0]`,`[2]`,
`GetCastingSkillID`, `GetOvercast`, `GetAnimationType/Speed/Code/ID`, `GetWeaponAttackSpeed`,
`GetAttackSpeedModifier`, `GetAgentModelType`, `GetTransmogNPCID`, `GetGuildID`, `GetTeamID`,
`GetAgentEffects/GetModelState/GetTypeMap(id)` each shown as dec+hex+bin.

### Item-agent / gadget-agent fields (explicit accessors)
Item: `Agent.GetItemAgentOwnerID/ItemID/ExtraType/h00CC(id)` (extra_type & h00CC as dec+hex+bin).
Gadget: `Agent.GetGadgetAgentID/ExtraType/h00C4/h00C8(id)`, and `Agent.GetGadgetAgenth00D4(id)`
iterated `for idx, h00D4 in enumerate(...)` with dec/hex/bin per element.
(v1 legacy used object returns instead: `Agent.GetItemAgentByID(id)` → `.agent_id/.owner/.item_id/.h00CC/.extra_type`;
`Agent.GetGadgetAgentByID(id)` → `.gadget_id/.extra_type/.h00C4/.h00C8/.h00D4[]`. Same fields, object vs. flat getters.)

### Encoded name + clipboard
`Agent.GetEncNameByID(id)` → `GWStringEncoded._format_name_encoded(...)`; copy via
`PyImGui.set_clipboard_text(...)`.

### Allegiance-filtered iterate-all (targeting combo)
```python
combo_items = ["All"] + [a.name for a in Allegiance if a != Allegiance.Unknown]
# then map selection to the right pre-filtered array:
AgentArray.GetAllyArray()/GetNeutralArray()/GetEnemyArray()/GetSpiritPetArray()/GetMinionArray()/GetNPCMinipetArray()
# build "id - name" combo:
for agent_id in agent_ids:
    agent = Agent.GetAgentByID(agent_id)
    if agent and agent.agent_id != 0:
        combo_items.append(f"{agent.agent_id} - {Agent.GetNameByID(agent.agent_id)}")
```
Per-agent detail is rendered in a `begin_tab_bar` with one `begin_tab_item` per nearest category,
each calling `_draw_agent_tab_item(agent_id)`.

---

## 3. AgentArray (concept + arrays)

v1 `ShowAgentArrayWindow` is only descriptive text. The real arrays used across demos:
`GetAgentArray`, `GetAllyArray`, `GetNeutralArray`, `GetEnemyArray`, `GetSpiritPetArray`,
`GetMinionArray`, `GetNPCMinipetArray`, `GetItemArray`, `GetGadgetArray`.
Manipulation/sort helpers: `AgentArray.Sort.ByDistance(arr, (x,y))`,
`AgentArray.Manipulation.Subtract(arr, [id])`, then `next(iter(arr), 0)` for the closest.

---

## 4. Player

v1 `ShowPlayerWindow`. Common:
```python
posx, posy = Player.GetXY()
data = [("Agent ID:", Player.GetAgentID()), ("Name:", Player.GetName()),
        ("XY:", f"({posx:.2f}, {posy:.2f})"), ("Target ID:", Player.GetTargetID()),
        ("Observing ID:", Player.GetObservingID())]
```
**Multi-return tuples unpacked into many rows** (canonical Player pattern):
```python
rank, rating, qualifier_points, wins, losses = Player.GetRankData()
current_skill_points, total_earned_skill_points = Player.GetSkillPointData()
current_kurzick, total_earned_kurzick, max_kurzick = Player.GetKurzickData()
# ...Luxon/Imperial/Balthazar identical shape...
account_name = Player.GetAccountName(); account_email = Player.GetAccountEmail()
```
Single getters: `GetTournamentRewardPoints`, `GetMorale`, `GetExperience`.

### Title struct cast + enum-name resolution
```python
current_title = Player.GetActiveTitleID()
title_data = Player.GetTitle(current_title)          # struct, may be None → guard
if title_data is None: PyImGui.text("No active title"); ...
props = title_data.props; current_points = title_data.current_points
current_title_tier_index = title_data.current_title_tier_index
# ...points_needed_current_rank / next_title_tier_index / max_title_rank / is_percentage_based / has_tiers...
title_name = TITLE_NAME.get(TitleID(current_title), "Unknown")   # id -> enum -> name dict
```
Actions: `Player.SendDialog(int(hex_input,16))`, `Player.SendChatCommand("dialog take")`,
`Player.SendChat('#', text)`, `Player.SendWhisper(name,"Hello")`, `Player.ChangeTarget(id)`,
`Player.Interact(id, call_target=False)`, `Player.Move(x,y)`,
`Player.DepositFaction(FactionAllegiance.Kurzick.value)`, `Player.SetActiveTitle(TitleID.Norn.value)`,
`Player.RemoveActiveTitle()`.

---

## 5. Party (players / heroes / henchmen / others / pets)

v1 `ShowPartyWindow`. Scalar block via `GLOBAL_CACHE.Party.*`:
`GetPartyID`, `GetPartyLeaderID`, `GetPartySize`, `GetPlayerCount`, `GetHeroCount`,
`GetHenchmanCount`, `IsHardMode`/`IsNormalMode`/`IsHardModeUnlocked`, `IsPartyDefeated`,
`IsPartyLoaded`, `IsPartyLeader`, `IsAllTicked`, `IsPlayerTicked(party_number)`.
Login/party number chain:
```python
login_number = GLOBAL_CACHE.Party.Players.GetLoginNumberByAgentID(Player.GetAgentID())
party_number = GLOBAL_CACHE.Party.Players.GetPartyNumberFromLoginNumber(login_number)
```

### Iterate-all members with per-object field cast
Players — `for player in GLOBAL_CACHE.Party.GetPlayers():` read `player.login_number`,
`player.called_target_id`, `player.is_connected`, `player.is_ticked`; name via
`GLOBAL_CACHE.Party.Players.GetPlayerNameByLoginNumber(login_number)`; bools shown as `'Yes'/'No'`.
Heroes — `for hero in GLOBAL_CACHE.Party.GetHeroes():` read `hero.hero_id.GetID()` (nested obj →
`.GetID()`), `hero.agent_id`, `hero.owner_player_id`, `hero.level`,
`hero.primary.GetName()`/`hero.secondary.GetName()` (profession objects → `.GetName()`); name via
`GLOBAL_CACHE.Party.Heroes.GetHeroNameById(hero_id)`.
Henchmen — `henchman.agent_id`, `henchman.level`, `henchman.profession.GetName()`.
Others — `GLOBAL_CACHE.Party.GetOthers()` returns bare ids; name via `Agent.GetNameByID(id)`.
Pet — `pet = GLOBAL_CACHE.Party.Pets.GetPetInfo(Player.GetAgentID())` struct → `.agent_id`,
`.owner_agent_id`, `.pet_name`, `.model_file_id1/2`, `.behavior`, `.locked_target_id`.
Actions: `Party.Players.Invite/KickPlayer(id)`, `Party.Heroes.AddHero/KickHero(id)`,
`AddHeroByName/KickHeroByName(name)`, `KickAllHeroes()`, `FlagHero(id,x,y)`,
`SetHeroBehavior(id, 0|1|2)`, `Party.Pets.SetPetBehavior(mode, lock_target_id)`,
`Party.ToggleTicked()`, `Party.SetHardMode/SetNormalMode()`.
Note `PyParty.Hero(name).GetID()` constructs a hero from a name string.

---

## 6. Item (per-item deep data)

v1 `ShowItemDataWindow(item_id)` — id-driven, subclassed accessors, all via `GLOBAL_CACHE.Item.*`.
Type/name: `GetItemType(id)` → `(type_id, type_name)` rendered `f"{id} - {name}"`; `GetModelID`,
`GetModelFileID`, `GetSlot`, `GetAgentID`, `GetAgentItemID`. Name is request-based
(`GLOBAL_CACHE.Item.RequestName(id)` then `GetName(id)`), cached in a dict.
- Rarity: `Item.Rarity.GetRarity(id)` → `(id,name)`, plus `IsWhite/IsBlue/IsPurple/IsGold/IsGreen(id)`
  used to override the display name.
- Properties: `Item.Properties.IsCustomized/GetValue/GetQuantity/IsEquipped/GetProfession/GetInteraction(id)`;
  `GetInteraction` also shown as `bin(...)`.
- Type: `Item.Type.IsWeapon/IsArmor/IsInventoryItem/IsStorageItem/IsMaterial/IsZCoin/IsTome(id)`.
- Usage: `Item.Usage.IsUsable/GetUses/IsSalvageable/IsMaterialSalvageable/IsSalvageKit/IsLesserKit/
  IsExpertSalvageKit/IsPerfectSalvageKit/IsIDKit/IsIdentified(id)`.
- Customization: `IsInscription/IsInscribable/IsPrefixUpgradable/IsSuffixUpgradable/GetItemFormula/
  IsStackable/IsSparkly(id)`; formula shown dec + `hex()` + `bin()`; interaction via
  `format_binary_grouped(value, 4)` helper (groups bits in nibbles).

### Struct/collection casts
Modifiers — `Item.Customization.Modifiers.GetModifiers(id)` list; `GetModifierCount(id)`; per modifier
call methods: `.GetIdentifier()`, `.IsValid()`, `.GetArg()/.GetArg1()/.GetArg2()`, each rendered
dec/hex/bin (4-col table per modifier).
Dye — `Item.Customization.GetDyeInfo(id)` struct → `.dye_tint`, `.dye1..dye4`; each dye object →
`.ToInt()` and `.ToString()` (id + name columns).

---

## 7. Inventory

v1 `ShowInventoryWindow`, all `GLOBAL_CACHE.Inventory.*`:
`GetHoveredItemID`, `GetFirstIDKit`, `GetFirstSalvageKit`, `GetFirstUnidentifiedItem`,
`GetFirstSalvageableItem`, `GetGoldOnCharacter`, `GetGoldInStorage` (gold cast with a
`format_currency(amount)` helper: `plat = amount//1000; gold = amount%1000`), `IsStorageOpen`.
Actions: `IdentifyFirst()`, `SalvageItem(item_id, kit_id)`, `OpenXunlaiWindow()`; salvage-UI accept via
`PyInventory.PyInventory().AcceptSalvageWindow()`.

---

## 8. Skill (common / data / attribute / flags / animations / extradata)

v1 `ShowSkillDataWindow(skill_id)`, id-driven `GLOBAL_CACHE.Skill.*`.
Common: `GetName(id)`, `GetType(id)`→(id,name), `GetCampaign(id)`→(id,name),
`GetProfession(id)`→(id,name), all rendered `f"{id} - {name}"`.
Data: `Skill.Data.GetCombo/GetComboReq/GetWeaponReq/GetOvercast/GetEnergyCost/GetHealthCost/
GetAdrenaline/GetAdrenalineA/GetAdrenalineB/GetActivation/GetAftercast/GetRecharge/GetRecharge2/
GetAoERange(id)`.
Attribute: `Skill.Attribute.GetAttribute(id)` struct → `.GetName()`, `.level`, `.level_base`;
`GetScale(id)`→(scale0,scale15); `GetBonusScale(id)`; `GetDuration(id)`.
Flags: ~38 booleans `Skill.Flags.IsTouchRange/IsElite/IsHex/IsSpell/IsEnchantment/…(id)` (full list in
source lines ~694-773) — each a KV row.
Animations: `Skill.Animations.GetEffects(id)`→(e1,e2), `GetSpecial/GetConstEffect/
GetCasterOverheadAnimationID/GetCasterBodyAnimationID/GetTargetBodyAnimationID/
GetTargetOverheadAnimationID(id)`, `GetProjectileAnimationID(id)`→(a1,a2), `GetIconFileID(id)`→(f1,f2).
ExtraData: `Skill.ExtraData.GetCondition/GetTitle/GetIDPvP/GetTarget/GetSkillEquipType/
GetSkillArguments/GetNameID/GetConcise/GetDescriptionID(id)`.
Hovered: `GLOBAL_CACHE.SkillBar.GetHoveredSkillID()` + `Skill.GetName(id).replace("_"," ")`.
Skill objects can also be built directly: `PySkill.Skill(skill_id).id.GetName()` (used in Effects).

---

## 9. Skillbar (own + heroes)

v1 `ShowSkillbarWindow`. Own bar — iterate slots 1..8:
```python
for skill_slot in range(1, 9):
    skill_id = GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(skill_slot)
    skill_name = GLOBAL_CACHE.Skill.GetName(skill_id)
    skill = GLOBAL_CACHE.SkillBar.GetSkillData(skill_slot)   # struct
    # fields: skill.adrenaline_a, skill.adrenaline_b, skill.recharge, skill.event
    GLOBAL_CACHE.SkillBar.UseSkill(skill_slot)               # action
```
Heroes — `GLOBAL_CACHE.Party.GetHeroes()`; `hero.hero_id.GetID()`, `hero.agent_id`; hero bar via
`GLOBAL_CACHE.SkillBar.GetHeroSkillbar(hero_index)` → list of skill structs; per skill
`skill.id.id`, `.adrenaline_a/.adrenaline_b/.recharge/.event`; action
`GLOBAL_CACHE.SkillBar.HeroUseSkill(agent_id, skill_slot, hero_index)`.

---

## 10. Effects / Buffs

v1 `ShowEffectsWindow`, `GLOBAL_CACHE.Effects.*`:
```python
buff_list   = GLOBAL_CACHE.Effects.GetBuffs(Player.GetAgentID())
effect_list = GLOBAL_CACHE.Effects.GetEffects(Player.GetAgentID())
# effect struct: effect.effect_id, effect.skill_id, effect.duration, effect.attribute_level, effect.time_remaining
#   name via PySkill.Skill(effect.skill_id).id.GetName()
# buff struct:   buff.buff_id, buff.skill_id, buff.target_agent_id ; name same way
```
Action: `GLOBAL_CACHE.Effects.DropBuff(buff_id)`.

---

## 11. Merchant / Trading (Trader / Merchant / Crafter / Collector)

v1 `ShowMerchantWindow`, `GLOBAL_CACHE.Trading.*`:
`Trading.Trader.GetOfferedItems()` / `Trading.Merchant.GetOfferedItems()` → id lists iterated into a
5-wide table (`for index,item in enumerate(list): if index%5==0: table_next_row(); table_set_column_index(index%5)`).
`Trading.Trader.GetQuotedItemID()/GetQuotedValue()`, `Trading.IsTransactionComplete()`,
`Inventory.GetHoveredItemID()`.
Actions: `Trader.RequestQuote/RequestSellQuote/BuyItem/SellItem(item_id[,cost])`;
`Merchant.BuyItem/SellItem(id,cost)`; `Crafter.CraftItem(id, cost, trade_item_list, quantity_list)`;
`Collector.ExchangeItem(id, cost, trade_item_list, quantity_list)`.

---

## 12. Quest

v1 `ShowQuestWindow`: `GLOBAL_CACHE.Quest.GetActiveQuest()`, `SetActiveQuest(id)`, `AbandonQuest(id)`.
(Minimal in v1 — a fuller quest struct panel is a reengineer opportunity.)

---

## 13. Py4GW core utilities (Keystroke / Ping / Timer / Overlay)

v1 `ShowPy4GW_Window_main`.
- Keystroke: `key_names = [k.name for k in Key]`; `selected_key = Key[name]`;
  `Keystroke.Press/Release/PressAndRelease(selected_key.value)`.
- Ping: `ping_handler = PyPing.PingHandler()`; `GetCurrentPing/GetAveragePing/GetMinPing/GetMaxPing()`.
- Timer: `timer_instance = Timer()`; `GetElapsedTime/IsStopped/IsRunning/IsPaused/HasElapsed(ms)`;
  `Start/Stop/Pause/Resume()`.
- Overlay: `Overlay().GetMouseCoords()`, `GetMouseWorldPos()` (returns x,y,z), `FindZ(x,y)`,
  `WorldToScreen(x,y,z)`, `DrawPoly3D(x,y,z,radius,color=0xAARRGGBB,numsegments,thickness)`,
  `DrawText3D(...)`, `DrawLine(...)`. Area rings use literal radii (Touch=144…Compass=5000).

---

## 14. Pathing map (canvas rendering, not tables)

Model file: `pathing_map_demo.py`. `Map.GetMapBoundaries()` → (min_x,min_y,max_x,max_y);
`Map.Pathing.GetPathingMaps()` → layers, each `layer.trapezoids` with fields `XTL/XTR/XBL/XBR/YT/YB`.
Rendering is `PyImGui.draw_list_add_quad_filled(...)` after world→screen `scale_coords`, with pan/zoom
from `PyImGui.get_io()` (`io.mouse_wheel`, `io.mouse_pos_x/y`, `is_mouse_dragging`,
`get_mouse_drag_delta`). Player dot via `Player.GetXY()` → `scale_coords(...,flip_y=True)` →
`draw_list_add_circle_filled`. Pathfinding via `AutoPathing().get_path(p1,p2)` scheduled onto
`GLOBAL_CACHE.Coroutines`. Overlay draws wrapped in `Overlay().BeginDraw()/EndDraw()`.

---

## 15. v2 host + section shape (how the reengineer wires panels)

`Py4GW DEMO 2.0.py`: `draw_window()` opens ONE window, a left `begin_child("left_panel")` calling
`registry.draw_sidebar()` and a right `begin_child("right_panel")` calling `registry.draw_content()`.
`registry.GROUPS` maps group → `Section(name, zero_arg_draw_callable)`; each section draws INTO the
host child (no own `begin`/`end` window). `draw_content` wraps the call in try/except and prints a red
`Panel error` line — so one panel throwing never kills the widget. **Every domain panel is a
`draw_*_view()`/`draw_*_tab()` that renders directly; no per-panel window management.**

---

## 16. Diagnostics / dump-to-file — PRIOR ART (thin)

- **No file-dump / dump-to-disk exists in any demo.** Nothing writes a `.txt`/`.json` diagnostics file.
- Closest prior art is **clipboard copy**: `agent_demo` uses `PyImGui.set_clipboard_text(...)` for
  encoded name and position ("Copy to Clipboard" buttons).
- Error handling everywhere is console-only: v1 wraps each `Show*` in
  `try/except` → `PySystem.Console.Log(module_name, msg, PySystem.Console.MessageType.Error); raise`;
  v2 `ui.probe()`/`action_button` capture `f"{type(e).__name__}: {e}"` into a `ProbeResult` and render
  red inline. The `main()` catch-all also logs `traceback.format_exc()` to the console.
- **Reengineer requirement (per-section "dump diagnostics to file") is genuinely new** — model its
  content on the exact row lists documented above (build the same `(field, value)`/multi-col rows the
  panel renders, then write them out), and reuse `_fmt_ptr`/dec-hex-bin/`.GetName()`/enum-dict casts so
  the dumped values are the readable ones, not raw struct reprs.

---

## 17. Where the CURRENT tool diverges (checklist for the reengineer)

1. **Generic `str()`/`repr()` on structs** (`ui.fmt_value`, `draw_multi_table`/`draw_kv_table` cells).
   Structs (`AgentStruct`, `TitleData`, `PetInfo`, dye/modifier objects, `FrameInfo`, context structs)
   fall through to `repr()` → `<... object at 0x...>`. FIX: explicit per-field extraction like the model
   modules (`f"{struct.field}"`, `_fmt_ptr` for pointers, `list()` for arrays, `.GetName()`/lookup dicts
   for enums).
2. **Reflection/auto-discovery** (`auto_probe_entries`, `probe_entries_1arg`, `_one_arg_getter_names`) —
   replaced by hand-written per-method recipes here. Auto-probe cannot know a getter returns a struct or
   an `(id,name)` tuple, so it can't cast it. Every domain above gives the explicit list to enumerate.
3. **Bools printed as "True/False"** via generic stringify. FIX: `_colored_bool(...)` +
   `PyImGui.text_colored`, as `agent_demo` does.
4. **`(id, name)` tuples printed as `('12', 'Foo')`**. FIX: unpack to `f"[{id}] - {name}"` (map_demo idiom).
5. **Integers that are bitfields printed as plain dec** (name properties, visual effects, effects,
   model state, type map, item formula/interaction). FIX: render dec + `hex()` + `bin()` (agent_demo/item).
6. **No enum-name resolution** for professions/campaign/title/allegiance. FIX: lookup dicts
   (`Profession_Names`, `CampaignName`, `TITLE_NAME`) and `Enum(value).name`, plus struct `.GetName()`.
</content>
