# Python Wrapper API Surface (per-domain getters & actions)

This document is the per-domain content checklist for the demo/test widget. It inventories the
**public** API of every domain wrapper base class under `Py4GWCoreLib/`: the classes and nested
sub-namespaces a script touches, and for each the public methods a script calls — marked **getter**
(data to display) or **action** (a button that mutates/queues/sends).

How to read it:
- **getter** = read-only, safe to poll each frame; this is the demo's main content.
- **action** = mutates game state, sends a UI message, queues via `ActionQueueManager`, or draws.
  These become buttons (usually gated behind a confirm / requires-target).
- Each wrapper notes its **backend**: whether it calls a native `Py*` binding directly, reads the
  shared-memory **Context path** (`GWContext.*` ctypes structs), and whether a **`GLOBAL_CACHE.<X>`**
  cached mirror likely exists (the demo may show both paths).
- Private `_underscore` helpers are omitted. Combat-event getters on `Agent` that are currently
  **stubbed** (hard-return `0`/`False`/`[]` pending the CombatEvents migration) are flagged.

Wrappers covered: Agent, AgentArray, Player, Map, Inventory, Item, ItemArray, Skill, Skillbar,
Effect, Party, Merchant (Trading), Quest, Camera, Overlay, DXOverlay, Keystroke, Pathing, Dialog,
UIManager, GWUI, PacketSniffer, CombatEvents, Scanner, Context.

---

## Agent.py

**Backend:** wraps native `PyAgent` module functions + reads `AgentStruct`/`AgentLivingStruct`/
`AgentItemStruct`/`AgentGadgetStruct` from the Context path (via `AgentArray`/`GWContext.World`).
Per-frame property cache invalidated on `PreUpdate`. Cache mirror: **`GLOBAL_CACHE.Agent`** exists.
Almost the entire surface is **getters keyed by `agent_id`** — the demo's richest data source. There
are **no mutating actions** here (targeting/interaction live on `Player`).

### Agent (identity / lookup)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Agent | IsValid | getter | True if agent exists |
| Agent | GetAgentByID | getter | Raw AgentStruct for an id |
| Agent | GetLivingAgentByID | getter | AgentLivingStruct view |
| Agent | GetItemAgentByID | getter | AgentItemStruct view |
| Agent | GetGadgetAgentByID | getter | AgentGadgetStruct view |
| Agent | GetNameByID / RequestName | getter | Decoded display name |
| Agent | IsNameReady | getter | True if name resolved |
| Agent | GetEncNameByID | getter | Encoded name bytes |
| Agent | GetEncNameStrByID | getter | Encoded name as debug string |
| Agent | GetAgentIDByName | getter | First agent id by partial name |
| Agent | GetAgentIDByEncString | getter | Agent id by encoded-name string |
| Agent | GetModelIDByEncString | getter | Model id by encoded-name string |

### Agent (living: stats / state)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Agent | GetAttributes / GetAttributesDict | getter | Attribute structs / {id:level} |
| Agent | GetInstanceFrames / GetInstanceUptime | getter | Instance timer (frames / ms) |
| Agent | GetAgentEffects | getter | Effects bitfield |
| Agent | GetTypeMap / GetModelState | getter | Type map / model state |
| Agent | GetModelID / GetPlayerNumber / GetLoginNumber | getter | Model / player / login number |
| Agent | IsLiving / IsItem / IsGadget | getter | Agent type predicates |
| Agent | IsSpirit / IsPet / IsMinion | getter | Allegiance-derived predicates |
| Agent | GetOwnerID | getter | Owner agent id |
| Agent | GetXY / GetXYZ / GetZPlane | getter | Position |
| Agent | GetNameTagXYZ | getter | Name-tag world coords |
| Agent | GetModelScale1/2/3 | getter | Model width/height triples |
| Agent | GetNameProperties / GetVisualEffects | getter | Name props / visual effects |
| Agent | GetTerrainNormalXYZ / GetGround | getter | Terrain normal / ground height |
| Agent | GetAnimationCode / GetAnimationType / GetAnimationSpeed / GetAnimationID | getter | Animation data |
| Agent | GetWeaponItemType / GetOffhandItemType | getter | Weapon/offhand item types |
| Agent | GetWeaponAttackSpeed / GetAttackSpeedModifier | getter | Attack speed data |
| Agent | GetAgentModelType / GetTransmogNPCID | getter | Model type / transmog id |
| Agent | GetGuildID / GetTeamID | getter | Guild / team id |
| Agent | GetRotationAngle / GetRotationCos / GetRotationSin | getter | Rotation |
| Agent | GetVelocityXY | getter | Velocity |
| Agent | GetProfessions / GetProfessionNames / GetProfessionShortNames / GetProfessionIDs | getter | Professions (ids / names) |
| Agent | GetLevel | getter | Level |
| Agent | GetEnergy / GetMaxEnergy / GetEnergyRegen / GetEnergyPips | getter | Energy stats |
| Agent | GetHealth / GetMaxHealth / GetHealthRegen / GetHealthPips | getter | Health stats |
| Agent | GetProfessionsTexturePaths | getter | Profession icon file paths |

### Agent (condition / combat predicates)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Agent | IsMoving / IsIdle / IsDead / IsAlive | getter | Movement / life state |
| Agent | IsKnockedDown / IsBleeding / IsCrippled / IsDeepWounded / IsPoisoned / IsConditioned | getter | Condition predicates |
| Agent | IsEnchanted / IsHexed / IsDegenHexed / IsWeaponSpelled | getter | Buff/hex predicates |
| Agent | IsExploitable / IsExploitableCorpse / IsUsedCorpse / IsExploitedCorpse / IsDeadByTypeMap | getter | Corpse/exploit state |
| Agent | IsInCombatStance / IsAggressive / IsAttacking / IsCasting | getter | Combat activity |
| Agent | GetCastingSkillID | getter | Skill id being cast |
| Agent | HasBossGlow / HasQuest / IsBeingObserved / IsSpawned | getter | Misc flags |
| Agent | GetWeaponType / GetWeaponExtraData / IsHoldingItem | getter | Weapon info |
| Agent | IsMartial / IsCaster / IsMelee / IsRanged | getter | Weapon-class predicates |
| Agent | GetDaggerStatus | getter | Dagger attack status |
| Agent | GetAllegiance | getter | (id, name) allegiance |
| Agent | IsPlayer / IsNPC | getter | Player vs NPC |
| Agent | GetNPCModelByID / GetNPCFlags / IsFleshy | getter | NPC model data |
| Agent | IsFemale / IsHidingCape / CanBeViewedInPartyWindow | getter | Cosmetic/UI flags |
| Agent | GetOvercast | getter | Overcast value |
| Agent | CanAct | getter | **Stubbed** → always True |
| Agent | HasStance / GetStanceID / GetStanceCooldown | getter | **Stubbed** → 0/False |
| Agent | GetTarget / GetCastingTarget / GetAttackTarget | getter | **Stubbed** → 0 |
| Agent | GetRemainingCastTime / GetRemainingRechargeTime / GetKnockDownTimeRemaining | getter | **Stubbed** → 0 |
| Agent | IsTargeted / GetAgetsTargeting | getter | **Stubbed** → False/[] |
| Agent | IsSkillOnCooldown / IsCooldownEstimated / GetSkillsOnCooldown | getter | **Stubbed** → False/[] |
| Agent | GetRecentHealingReceived / GetRecentHealingDealt / HasEffectRenewed / GetObservedSkillbar | getter | **Stubbed** → [] |

### Agent (item-agent getters)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Agent | GetItemAgentOwnerID / GetItemAgentItemID / GetItemAgentExtraType / GetItemAgenth00CC | getter | Item-agent fields |

### Agent (gadget-agent getters)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Agent | GetGadgetID / GetGadgetAgentID / GetGadgetAgentExtraType | getter | Gadget id / fields |
| Agent | GetGadgetAgenth00C4 / GetGadgetAgenth00C8 / GetGadgetAgenth00D4 | getter | Raw gadget fields |

---

## AgentArray.py

**Backend:** array getters read from **shared memory** (`SystemShaMemMgr.get_agent_array_wrapper`);
single-agent lookup via the Context path. Cache mirror: **`GLOBAL_CACHE.AgentArray`** exists. The
sub-namespaces (Manipulation / Sort / Filter / Routines) are pure in-Python transforms — great demo
material for chaining "get array → filter → sort".

### AgentArray (prefiltered arrays)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| AgentArray | GetAgentArray | getter | Full unfiltered agent id list |
| AgentArray | GetAllyArray / GetNeutralArray / GetEnemyArray | getter | Allegiance-filtered arrays |
| AgentArray | GetSpiritPetArray / GetMinionArray / GetNPCMinipetArray | getter | Spirit/pet/minion/NPC arrays |
| AgentArray | GetItemArray / GetOwnedItemArray / GetGadgetArray | getter | Item / owned-item / gadget arrays |
| AgentArray | GetDeadAllyArray / GetDeadEnemyArray | getter | Dead ally / enemy arrays |
| AgentArray | GetAgentByID | getter | AgentStruct by id |

### AgentArray.Manipulation
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| AgentArray.Manipulation | Merge | getter | Union of two arrays |
| AgentArray.Manipulation | Subtract | getter | Set difference |
| AgentArray.Manipulation | Intersect | getter | Intersection |

### AgentArray.Sort
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| AgentArray.Sort | ByAttribute | getter | Sort by an `Agent` getter name |
| AgentArray.Sort | ByCondition | getter | Sort by a key func |
| AgentArray.Sort | ByDistance | getter | Sort by distance to a point |
| AgentArray.Sort | ByHealth | getter | Sort by HP |

### AgentArray.Filter
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| AgentArray.Filter | ByAttribute | getter | Filter by an `Agent` attribute (+negate) |
| AgentArray.Filter | ByCondition | getter | Filter by a predicate func |
| AgentArray.Filter | ByDistance | getter | Filter within/outside a radius |

### AgentArray.Routines
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| AgentArray.Routines | DetectLargestAgentCluster | getter | Agent id nearest the largest cluster center |

---

## Player.py

**Backend:** reads the Context path (`GWContext.Char/World/Party`) for data; mutations queue through
`ActionQueueManager` → native `PlayerMethods`/`PyPlayer`. Cache mirror: **`GLOBAL_CACHE.Player`**
exists. Getters are `@frame_cache`-decorated. Rich mix of self-data getters and chat/targeting
actions — the demo's "self" panel plus a big button set.

### Player (identity / self data)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Player | player_instance | getter | Raw PyPlayer instance |
| Player | GetPlayerNumber / GetLoginNumber / GetPartyNumber | getter | Player / login / party number |
| Player | IsPlayerLoaded | getter | True if player loaded & connected |
| Player | GetAgentID / GetAgent | getter | Own agent id / struct |
| Player | GetName | getter | Character name |
| Player | GetXY | getter | Own position |
| Player | GetTargetID / GetObservingID | getter | Current target / observed agent |
| Player | GetAccountName / GetAccountEmail / GetPlayerUUID | getter | Account identity |
| Player | GetInstanceUptime | getter | Instance uptime |
| Player | GetRankData / GetTournamentRewardPoints | getter | PvP rank / tournament points |
| Player | GetMorale / GetExperience / GetLevel / GetSkillPointData | getter | Morale / xp / level / skill points |
| Player | GetAccountFlags / IsDhuumsCovenant / IsMelandrusAccord / IsReforged | getter | Account-mode flags |
| Player | GetMissionsCompleted / GetMissionsBonusCompleted / GetMissionsCompletedHM / GetMissionsBonusCompletedHM | getter | Mission completion lists |
| Player | GetControlledMinions | getter | (agent_id, count) minions |
| Player | GetLearnableCharacterSkills / GetUnlockedCharacterSkills | getter | Skill unlock lists |
| Player | GetKurzickData / GetLuxonData / GetImperialData / GetBalthazarData | getter | Faction (current/total/max) |
| Player | GetActiveTitleID / GetTitleArrayRaw / GetTitleArray / GetTitle | getter | Title data |
| Player | GetPlayerStatus / GetPlayerStatusName | getter | Friend-list status |
| Player | ResolvePlayerStatus / GetPlayerStatusNameFromValue | getter | Status enum helpers |
| Player | IsChatHistoryReady / GetChatHistory / IsTyping | getter | Chat state |

### Player (actions)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Player | SetPlayerStatus | action | Set friend-list status |
| Player | ChangeTarget | action | Change current target |
| Player | CallTarget | action | Broadcast a call-target to party |
| Player | Interact | action | Interact with an agent |
| Player | Move | action | Move to (x,y,zplane) |
| Player | DepositFaction | action | Deposit Kurzick/Luxon faction |
| Player | RemoveActiveTitle / SetActiveTitle | action | Clear / set active title |
| Player | SendRawDialog | action | Send raw agent dialog |
| Player | BuySkill / UnlockBalthazarSkill | action | Skill trainer / Balthazar unlock |
| Player | SendDialog / SendAutomaticDialog | action | Send dialog choice |
| Player | RequestChatHistory | action | Request chat history |
| Player | SendChatCommand / SendChat / SendWhisper | action | Send chat / command / whisper |
| Player | SendFakeChat / SendFakeChatColored | action | Inject local-only chat lines |
| Player | FormatChatMessage | getter | Wrap message in color tags |

---

## Map.py

**Backend:** reads Context path (`GWContext.*`); mutations queue native `MapMethods`; some window ops
delegate to `GLOBAL_CACHE.Coroutines`/Keybinds. Getters `@frame_cache`-decorated. Cache mirror:
**`GLOBAL_CACHE.Map`** exists. **Richest sub-namespace tree in the codebase** — MissionMap / MiniMap
(each with a full `MapProjection` coordinate-conversion suite) / WorldMap / Pregame / Pathing(+Quad).

### Map (top-level)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Map | IsMapDataLoaded / IsMapReady / IsMapLoading | getter | Load-state predicates |
| Map | GetInstanceType / GetInstanceTypeName | getter | Instance type |
| Map | IsOutpost / IsExplorable / IsObservingMatch | getter | Instance-kind predicates |
| Map | GetMapID / GetMapName / GetMapIDByName | getter | Map id / name lookup |
| Map | GetOutpostIDs / GetOutpostNames | getter | All outpost ids / names |
| Map | GetBaseMapID / GetAllMapVariants / IsMapIDMatch | getter | Seasonal-variant resolution |
| Map | GetInstanceUptime | getter | Instance uptime |
| Map | GetRegion / GetRegionType / GetDistrict / GetLanguage | getter | Region / district / language |
| Map | GetAmountOfPlayersInInstance | getter | Player count |
| Map | GetMaxPartySize / GetMinPartySize / GetMaxPlayerSize / GetMinPlayerSize | getter | Party/player size limits |
| Map | GetFoesKilled / GetFoesToKill / IsVanquishCompleted / IsVanquishComplete / IsVanquishable | getter | Vanquish progress |
| Map | IsInCinematic | getter | In cinematic |
| Map | GetCampaign / GetContinent | getter | Campaign / continent |
| Map | HasEnterChallengeButton / IsOnWorldMap / IsPVP / IsGuildHall | getter | Map-kind flags |
| Map | IsMapUnlocked / IsUnlockable / GetFlags | getter | Unlock state / flags |
| Map | GetMinLevel / GetMaxLevel / GetThumbnailID / GetControlledOutpostID | getter | Level range / misc ids |
| Map | GetFractionMission / GetNeededPQ / HasMissionMapsTo / GetMissionMapsTo | getter | Mission linkage |
| Map | GetIconPosition / GetIconStartPosition / GetIconStartDupePosition / GetIconEndPosition / GetIconEndDupePosition | getter | Travel-icon coords |
| Map | GetFileID / GetFileID1 / GetFileID2 / GetNameID / GetDescriptionID | getter | Raw ids |
| Map | GetMissionChronology / GetHAChronology | getter | Chronology values |
| Map | GetUnloadedMapInfo | getter | AreaInfo for any map id |
| Map | IsEnteringChallenge | getter | Enter-challenge in progress |
| Map | GetMapWorldMapBounds / GetMapBoundaries | getter | Map bounds (world / game space) |
| Map | SkipCinematic | action | Skip cinematic |
| Map | Travel / TravelToDistrict / TravelToRegion | action | Travel to map / district / region |
| Map | TravelGH / LeaveGH | action | Guild Hall travel |
| Map | EnterChallenge / CancelEnterChallenge / ConfirmEnterChallenge | action | Challenge-mission buttons |

### Map.MissionMap  (+ Map.MissionMap.MapProjection)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Map.MissionMap | GetFrameID / GetFrameInfo / IsWindowOpen | getter | Frame handles / open state |
| Map.MissionMap | OpenWindow / CloseWindow | action | Toggle mission map |
| Map.MissionMap | IsMouseOver / GetLastClickCoords / GetLastRightClickCoords | getter | Mouse/click state |
| Map.MissionMap | GetMissionMapWindowCoords / GetMissionMapContentsCoords | getter | Window / contents rects |
| Map.MissionMap | GetScale / GetZoom / GetAdjustedZoom / GetCenter / GetPanOffset / GetMapScreenCenter | getter | Viewport geometry |
| Map.MissionMap.MapProjection | GamePosToWorldMap / WorldMapToGamePos / WorldMapToScreen / ScreenToWorldMap | getter | Coordinate conversions |
| Map.MissionMap.MapProjection | GameMapToScreen / ScreenToGameMap / NormalizedScreenToScreen / ScreenToNormalizedScreen | getter | Coordinate conversions |
| Map.MissionMap.MapProjection | NormalizedScreenToWorldMap / NormalizedScreenToGamePos / GamePosToNormalizedScreen | getter | Coordinate conversions |
| Map.MissionMap.MapProjection | GamePosToScreen / ScreenToGamePos / WorldPosToMissionMapScreen / ScreenToWorldPos | getter | Coordinate conversions |

### Map.MiniMap  (+ Map.MiniMap.MapProjection)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Map.MiniMap | GetFrameInfo / GetFrameID / IsWindowOpen | getter | Frame handles / open state |
| Map.MiniMap | OpenWindow / CloseWindow | action | Show/hide compass |
| Map.MiniMap | IsMouseOver / GetLastClickCoords / GetLastRightClickCoords / GetWindowCoords | getter | Mouse/click/window state |
| Map.MiniMap | IsLocked / GetPanOffset / GetScale / GetRotation / GetZoom / GetMapScreenCenter | getter | Compass geometry |
| Map.MiniMap.MapProjection | (same 14 conversions as MissionMap) + WorldPosToMiniMapScreen | getter | Coordinate conversions |
| Map.MiniMap.MapProjection | ComputedPathingGeometryToScreen | getter | Pathing geometry → compass |

### Map.WorldMap
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Map.WorldMap | GetFrameID / GetFrameInfo / IsWindowOpen | getter | Frame handles / open state |
| Map.WorldMap | OpenWindow / CloseWindow | action | Toggle world map |
| Map.WorldMap | IsMouseOver / GetLastClickCoords / GetLastRightClickCoords / GetWindowCoords | getter | Mouse/click/window state |
| Map.WorldMap | GetZoom / GetParams / GetExtraData | getter | Zoom / params / raw struct |

### Map.Pregame
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Map.Pregame | GetFrameID / GetFrameInfo / IsWindowOpen | getter | Frame handles / open state |
| Map.Pregame | GetChosenCharacterIndex / GetContextStruct / GetCharList / GetAvailableCharacterList | getter | Char-select data |
| Map.Pregame | InCharacterSelectScreen | getter | At char-select |
| Map.Pregame | LogoutToCharacterSelect | action | Logout to char-select |

### Map.Pathing  (+ Map.Pathing.Quad)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Map.Pathing | GetPathingMaps / GetPathingMapsRaw | getter | Pathing maps (live / raw) |
| Map.Pathing | ClearPathingCache / ForceReloadNavMesh | action | Clear cache / rebuild navmesh |
| Map.Pathing | GetAvailableMapIds / GetSpawns / GetTravelPortals | getter | Offline map ids / spawns / portals |
| Map.Pathing | WorldToScreen | getter | World → screen |
| Map.Pathing | GetComputedGeometry / GetScreenComputedGeometry / GetShiftedComputedGeometry / GetshiftedScreenComputedGeometry | getter | Trapezoid geometry variants |
| Map.Pathing | GetMapQuads / IsPointInPathing / IsScreenPointInPathing | getter | Quads / point-in-pathing tests |
| Map.Pathing.Quad | GetPoints / GetScreenPoints / GetShiftedPoints / GetShiftedScreenPoints | getter | Quad corner points |

---

## Inventory.py

**Backend:** mixes native `PyInventory` (identify/salvage/move/gold) with `UIManager` frame scraping
for salvage dialogs; composes `Item`/`ItemArray`. Mutations call `PyInventory` or `ActionQueueManager`.
Cache mirror: **`GLOBAL_CACHE.Inventory`** exists. Balanced getter/action set — the demo's "bags" panel
with a wall of action buttons.

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Inventory | inventory_instance | getter | Raw PyInventory instance |
| Inventory | GetInventorySpace / GetStorageSpace / GetFreeSlotCount | getter | Slot counts |
| Inventory | GetZeroFilledStorageArray | getter | Flat storage item_id list |
| Inventory | GetItemCount / GetModelCount | getter | Count in bags 1-4 by item / model |
| Inventory | GetModelCountInStorage / GetModelCountInMaterialStorage / GetModelCountInEquipped | getter | Count by model in storage/materials/equipped |
| Inventory | GetFirstIDKit / GetFirstUnidentifiedItem | getter | First ID kit / unid item |
| Inventory | GetFirstSalvageKit / GetFirstSalvageableItem | getter | First salvage kit / salvageable item |
| Inventory | GetHoveredItemID | getter | Currently hovered item id |
| Inventory | GetGoldOnCharacter / GetGoldInStorage | getter | Gold amounts |
| Inventory | FindItemBagAndSlot | getter | (bag, slot) of item |
| Inventory | IsStorageOpen / IsSalvageChoiceMaterialConfirmVisible / IsSalvageChoiceDialogVisible | getter | Storage/salvage-dialog state |
| Inventory | IdentifyItem / IdentifyFirst | action | Identify item(s) |
| Inventory | SalvageItem / SalvageFirst | action | Salvage item(s) |
| Inventory | AcceptSalvageMaterialsWindow / HandleSalvageChoiceMaterialConfirmDialog / HandleSalvageChoiceDialog | action | Auto-handle salvage dialogs |
| Inventory | OpenXunlaiWindow | action | Open Xunlai storage |
| Inventory | PickUpItem / DropItem / EquipItem / UseItem / DestroyItem | action | Item ops |
| Inventory | DepositGold / WithdrawGold / DropGold | action | Gold ops |
| Inventory | MoveItem / DepositItemToStorage / WithdrawItemFromStorage | action | Move / storage transfer |

---

## Item.py

**Backend:** native `PyItem`/`PyInventory` bindings (`item_instance` → `PyItem.PyItem(item_id)`) plus
`item_mods_src` parsers. **Pure read surface — all getters, no actions** (except `RequestName`, a name
network request). Cache mirror: **`GLOBAL_CACHE.Item`** exists. Deep nested tree:
Rarity / Properties / Type / Usage / Customization(+Modifiers) / Trade / Filter(Dye,Weapon).

### Item (top-level)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Item | item_instance | getter | Build PyItem for item_id |
| Item | GetAgentID / GetAgentItemID / GetItemByAgentID | getter | Item↔agent linkage |
| Item | GetItemIdFromModelID | getter | item_id from model_id in bags |
| Item | RequestName / IsNameReady / GetName | getter/action | Name (RequestName = action) |
| Item | GetItemType / IsArmorType / IsWeapon | getter | Type classification |
| Item | GetModelID / GetModelFileID / GetCompositeModelIDs / GetTrueModelFileID | getter | Model ids |
| Item | GetSlot / GetDyeColor | getter | Slot / dye color |

### Item.Rarity
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Item.Rarity | GetRarity / IsWhite / IsBlue / IsPurple / IsGold / IsGreen | getter | Rarity value + predicates |

### Item.Properties
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Item.Properties | IsCustomized / IsEquipped / GetValue / GetQuantity / GetProfession / GetInteraction | getter | Core item props |
| Item.Properties | GetRequirement / GetDamage / GetArmor / GetEnergy | getter | Weapon/armor stats |

### Item.Type
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Item.Type | IsWeapon / IsArmor / IsInventoryItem / IsStorageItem | getter | Type-flag predicates |
| Item.Type | IsMaterial / IsRareMaterial / IsZCoin / IsTome | getter | Material/currency predicates |

### Item.Usage
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Item.Usage | IsUsable / GetUses / IsIdentified | getter | Usability / identify state |
| Item.Usage | IsSalvageable / IsMaterialSalvageable | getter | Salvage predicates |
| Item.Usage | IsSalvageKit / IsLesserKit / IsExpertSalvageKit / IsPerfectSalvageKit / IsIDKit | getter | Kit-type predicates |

### Item.Customization  (+ Item.Customization.Modifiers)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Item.Customization | IsInscription / IsInscribable / IsPrefixUpgradable / IsSuffixUpgradable | getter | Inscription/upgrade slots |
| Item.Customization | GetDyeInfo / GetItemFormula / IsStackable / IsSparkly | getter | Dye / formula / flags |
| Item.Customization | GetUpgrade / HasUpgrades / HasInherentUpgrades / HasUpgradeType / HasUpgrade | getter | Upgrade queries |
| Item.Customization | GetUpgrades / GetPrefixUpgrade / GetSuffixUpgrade / GetInscriptionUpgrade / GetInherentUpgrades | getter | Upgrade accessors |
| Item.Customization.Modifiers | GetModifierCount / GetModifiers / ModifierExists / GetModifierValues | getter | Raw modifier access |

### Item.Trade / Item.Filter (+ Dye, Weapon)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Item.Trade | IsOfferedInTrade / IsTradable | getter | Trade state |
| Item.Filter.Dye | IsDyeColor | getter | Item is a given dye color |
| Item.Filter.Weapon | IsMaxDamage | getter | Weapon at max damage for req |

---

## ItemArray.py

**Backend:** native `PyInventory.Bag` iteration; composes `Bag`/`Item`. Pure query/transform getters.
Cache mirror: **`GLOBAL_CACHE.ItemArray`** exists. Core getters `@frame_cache`-decorated.

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| ItemArray | CreateBagList / GetAllBags / GetBag | getter | Bag enum helpers |
| ItemArray | GetItemArray | getter | Item ids across bags |
| ItemArray.Filter | ByAttribute / ByCondition | getter | Filter items |
| ItemArray.Manipulation | Merge / Subtract / Intersect | getter | Set ops on item arrays |
| ItemArray.Sort | SortByAttribute / SortByCondition | getter | Sort item arrays |

---

## Skill.py

**Backend:** native `PySkill.Skill(skill_id)` + local `skill_descriptions.json`. Pure read surface —
**all getters** (no actions; casting lives on `Skillbar`). Cache mirror: **`GLOBAL_CACHE.Skill`** exists.
Nested tree: Data / Attribute / Flags / Animations / ExtraData.

### Skill (top-level)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Skill | skill_instance | getter | Raw PySkill instance |
| Skill | GetName / GetNameFromWiki / GetURL | getter | Name / wiki name / url |
| Skill | GetProgressionData | getter | Progression tuples |
| Skill | GetID | getter | Resolve skill id |
| Skill | GetDescription / GetConciseDescription | getter | Descriptions |
| Skill | GetType / GetCampaign / GetProfession | getter | (id,name) classification |

### Skill.Data
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Skill.Data | GetCombo / GetComboReq / GetWeaponReq / GetOvercast | getter | Combo / weapon / overcast |
| Skill.Data | GetEnergyCost / GetHealthCost / GetAdrenaline / GetAdrenalineA / GetAdrenalineB | getter | Costs |
| Skill.Data | GetActivation / GetAftercast / GetRecharge / GetRecharge2 / GetAoERange | getter | Timing / range |

### Skill.Attribute
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Skill.Attribute | GetAttribute / GetScale / GetBonusScale / GetDuration | getter | Attribute + 0/15-pt scales |

### Skill.Flags
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Skill.Flags | IsTouchRange / IsElite / IsHalfRange / IsPvP / IsPvE / IsPlayable / IsStacking / IsNonStacking / IsUnused | getter | Property-flag predicates |
| Skill.Flags | IsHex / IsBounty / IsScroll / IsStance / IsSpell / IsEnchantment / IsSignet / IsCondition / IsWell / IsSkill / IsWard / IsGlyph / IsTitle | getter | Skill-type predicates |
| Skill.Flags | IsAttack / IsShout / IsSkill2 / IsPassive / IsEnvironmental / IsPreparation / IsPetAttack / IsTrap / IsRitual / IsEnvironmentalTrap | getter | Skill-type predicates |
| Skill.Flags | IsItemSpell / IsWeaponSpell / IsForm / IsChant / IsEchoRefrain / IsDisguise | getter | Skill-type predicates |

### Skill.Animations
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Skill.Animations | GetEffects / GetSpecial / GetConstEffect | getter | Effect ids |
| Skill.Animations | GetCasterOverheadAnimationID / GetCasterBodyAnimationID / GetTargetBodyAnimationID / GetTargetOverheadAnimationID | getter | Animation ids |
| Skill.Animations | GetProjectileAnimationID / GetIconFileID | getter | Projectile anim / icon ids |

### Skill.ExtraData
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Skill.ExtraData | GetCondition / GetTitle / GetIDPvP / GetTarget / GetSkillEquipType / GetSkillArguments | getter | Misc extra fields |
| Skill.ExtraData | GetNameID / GetConcise / GetDescriptionID / GetTexturePath | getter | String ids / icon path |

---

## Skillbar.py  (class `SkillBar`)

**Backend:** native `PySkillbar.Skillbar()` each call. Cache mirror: **`GLOBAL_CACHE.SkillBar`** exists.
Mix of skillbar getters and cast actions.

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| SkillBar | GetSkillbar / GetZeroFilledSkillbar | getter | Skill ids (list / slot dict) |
| SkillBar | GetHeroSkillbar | getter | Hero skillbar |
| SkillBar | GetSkillIDBySlot / GetSlotBySkillID / GetSkillData | getter | Slot↔skill lookup |
| SkillBar | GetHoveredSkillID | getter | Hovered skill id |
| SkillBar | IsSkillUnlocked / IsSkillLearnt | getter | Unlock / learnt state |
| SkillBar | GetAgentID / GetDisabled / GetCasting | getter | Owner / disabled / casting |
| SkillBar | LoadSkillTemplate / LoadHeroSkillTemplate | action | Load skill template |
| SkillBar | UseSkill / UseSkillTargetless | action | Cast a slot |
| SkillBar | HeroUseSkill | action | Hero casts a skill |
| SkillBar | ChangeHeroSecondary | action | Change hero secondary profession |

---

## Effect.py  (class `Effects`)

**Backend:** native `PyEffects.PyEffects(agent_id)`. Cache mirror: **`GLOBAL_CACHE.Effects`** exists.
Mostly getters keyed by agent_id + two actions.

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Effects | get_instance | getter | Raw PyEffects instance |
| Effects | GetBuffs / GetEffects / GetBuffCount / GetEffectCount | getter | Active buff/effect lists + counts |
| Effects | BuffExists / EffectExists / HasEffect | getter | Presence predicates |
| Effects | EffectAttributeLevel / GetEffectTimeRemaining / GetBuffID | getter | Effect detail |
| Effects | GetAlcoholLevel | getter | Player alcohol level |
| Effects | DropBuff | action | Drop a maintained buff |
| Effects | ApplyDrunkEffect | action | Apply drunk visual effect |

---

## Party.py

**Backend:** native `PyParty.PyParty()` (getters `@frame_cache`d) + Player/Agent/World for some data.
Cache mirror: **`GLOBAL_CACHE.Party`** exists. Big nested tree: Players / Heroes / Henchmen / Pets.

### Party (top-level)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Party | party_instance | getter | Raw PyParty instance |
| Party | GetPartyID / GetPartyLeaderID / GetOwnPartyNumber / GetPartyTarget | getter | Party ids / target |
| Party | GetPlayers / GetHeroes / GetHenchmen / GetOthers | getter | Member lists |
| Party | GetPartySize / GetPlayerCount / GetHeroCount / GetHenchmanCount / GetHeroIndex | getter | Counts / index |
| Party | IsHardModeUnlocked / IsHardMode / IsNormalMode | getter | Mode state |
| Party | IsPartyDefeated / IsPartyLoaded / IsPlayerLoaded / IsPartyLeader | getter | State predicates |
| Party | GetPartyMorale | getter | Per-member morale |
| Party | IsAllTicked / IsPlayerTicked | getter | Ready/tick state |
| Party | SetTickasToggle / SetTicked / ToggleTicked | action | Ready/tick control |
| Party | SetHardMode / SetNormalMode | action | Switch mode |
| Party | SearchParty / SearchPartyCancel / SearchPartyReply / RespondToPartyRequest | action | Party search / requests |
| Party | ReturnToOutpost / LeaveParty | action | Return / leave |

### Party.Players
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Party.Players | GetAgentIDByLoginNumber / GetPlayerNameByLoginNumber / GetPartyNumberFromLoginNumber / GetLoginNumberByAgentID | getter | Login↔agent↔name lookups |
| Party.Players | InvitePlayer / KickPlayer | action | Invite / kick player |

### Party.Heroes
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Party.Heroes | GetHeroAgentIDByPartyPosition / GetHeroIDByAgentID / GetHeroIDByPartyPosition / GetHeroIdByName / GetHeroNameById / GetNameByAgentID / GetHeroPartyPositionByAgentID | getter | Hero id/name/position lookups |
| Party.Heroes | GetTargetIDByAgentID | getter | Hero locked target |
| Party.Heroes | IsHeroFlagged / IsAllFlagged / GetAllFlag | getter | Flag state |
| Party.Heroes | AddHero / AddHeroByName / KickHero / KickHeroByName / KickAllHeroes | action | Add/remove heroes |
| Party.Heroes | UseSkill / SetSkillAIEnabled / SetHeroBehavior | action | Hero skill / AI / behavior |
| Party.Heroes | FlagHero / FlagAllHeroes / UnflagHero / UnflagAllHeroes | action | Flag control |

### Party.Henchmen
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Party.Henchmen | AddHenchman / KickHenchman | action | Add/remove henchman |

### Party.Pets
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Party.Pets | GetPetBehavior / GetPetInfo / GetPetID | getter | Pet state |
| Party.Pets | SetPetBehavior | action | Set pet behavior |

---

## Merchant.py  (class `Trading`)

**Backend:** native `PyMerchant.PyMerchant()` (some list getters `@frame_cache`d). Cache mirror:
**`GLOBAL_CACHE.Trading`** exists. Nested tree: Trader / Merchant / Crafter / Collector.

### Trading (top-level)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Trading | merchant_instance / IsTransactionComplete | getter | Raw instance / transaction state |

### Trading.Trader
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Trading.Trader | GetQuotedItemID / GetQuotedValue / GetOfferedItems / GetOfferedItems2 | getter | Quote / offered items |
| Trading.Trader | RequestQuote / RequestSellQuote / BuyItem / SellItem | action | Quote / buy / sell |

### Trading.Merchant / Crafter / Collector
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Trading.Merchant | GetOfferedItems | getter | Merchant item list |
| Trading.Merchant | BuyItem / SellItem | action | Buy / sell |
| Trading.Crafter | GetOfferedItems | getter | Crafter item list |
| Trading.Crafter | CraftItem | action | Craft from materials |
| Trading.Collector | GetOfferedItems | getter | Collector item list |
| Trading.Collector | ExchangeItem | action | Exchange at collector |

---

## Quest.py

**Backend:** native `PyQuest.PyQuest()`. Cache mirror: **`GLOBAL_CACHE.Quest`** exists. Uses async
request/ready/get triads (Request* = action, Is*Ready + Get* = getters).

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Quest | quest_instance | getter | Raw PyQuest instance |
| Quest | GetActiveQuest / GetQuestData / GetQuestLog / GetQuestLogIds | getter | Active quest / log |
| Quest | IsQuestCompleted / IsQuestPrimary / IsMissionMapQuestAvailable | getter | Quest predicates |
| Quest | SetActiveQuest / AbandonQuest | action | Set / abandon quest |
| Quest | RequestQuestInfo / RequestQuestName / RequestQuestDescription / RequestQuestObjectives / RequestQuestLocation / RequestQuestNPC | action | Async info requests |
| Quest | IsQuestNameReady / GetQuestName | getter | Name |
| Quest | IsQuestDescriptionReady / GetQuestDescription | getter | Description |
| Quest | IsQuestObjectivesReady / GetQuestObjectives | getter | Objectives |
| Quest | IsQuestLocationReady / GetQuestLocation | getter | Location |
| Quest | IsQuestNPCReady / GetQuestNPC | getter | NPC |

---

## Camera.py

**Backend:** native `PyCamera.PyCamera()` (`camera_instance`). Cache mirror: **`GLOBAL_CACHE.Camera`**
exists (docstrings reference `GLOBAL_CACHE.Camera.IsPointInFOV`). Single class, no sub-namespaces.

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Camera | camera_instance | getter | Raw PyCamera instance |
| Camera | GetLookAtAgentID / GetMaxDistance / GetMaxDistance2 | getter | Look-at / distance |
| Camera | GetYaw / GetCurrentYaw / GetYawRightClick / GetYawRightClick2 / GetYawToGo | getter | Yaw values |
| Camera | GetPitch / GetPitchRightClick / GetPitchToGo | getter | Pitch values |
| Camera | GetCameraZoom / GetDistance2 / GetDistanceToGo / GetAccelerationConstant | getter | Zoom / distance / accel |
| Camera | GetTimeSinceLastKeyboardRotation / GetTimeSinceLastMouseRotation / GetTimeSinceLastMouseMove / GetTimeSinceLastAgentSelection | getter | Idle timers |
| Camera | GetTimeInTheMap / GetTimeInTheDistrict | getter | Time counters |
| Camera | GetPosition / GetCameraPositionToGo / GetCameraPositionInverted / GetCameraPositionInvertedToGo | getter | Position vectors |
| Camera | GetLookAtTarget / GetAtTargetToGo | getter | Look-at target |
| Camera | GetFieldOfView / GetFielsOfView2 | getter | FOV |
| Camera | GetCameraUnlock | getter | Unlock state |
| Camera | SetYaw / SetPitch / SetMaxDistance / SetFieldOfView / SetCameraUnlock / SetFog | action | Set camera params |
| Camera | ForwardMovement / VerticalMovement / SideMovement / RotateMovement | action | Move / rotate camera |
| Camera | ComputeCameraPos / UpdateCameraPos / SetCameraPosition / SetLookAtTarget | action | Position control |
| Camera | IsPointInFOV | getter | Point-in-FOV test (expensive) |

---

## Overlay.py

**Backend:** native `PyOverlay.Overlay()` singleton. **No GLOBAL_CACHE equivalent** — immediate-mode
draw surface used directly. Two getters + a large **action** (draw) API. Note `PyOverlay` Reforged
uses `Vec2f`/`Vec3f`.

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Overlay | IsMouseClicked / GetMouseCoords / GetMouseWorldPos | getter | Mouse state |
| Overlay | WorldToScreen / FindZ / GetDisplaySize | getter | Projection / display |
| Overlay | RefreshDrawList / BeginDraw / EndDraw | action | Draw-scope control |
| Overlay | DrawLine / DrawLine3D | action | Lines |
| Overlay | DrawTriangle(3D) / DrawTriangleFilled(3D) | action | Triangles |
| Overlay | DrawQuad(3D) / DrawQuadFilled(3D) | action | Quads |
| Overlay | DrawPoly(3D) / DrawPolyFilled / DrawPolyFilledRelative / DrawPolyFilled3D | action | Polygons |
| Overlay | DrawCubeOutline / DrawCubeFilled | action | Cubes |
| Overlay | DrawStar / DrawStarFilled | action | Stars |
| Overlay | DrawText / DrawText3D | action | Text |
| Overlay | PushClipRect / PopClipRect | action | Clip rect |
| Overlay | DrawTexture / DrawTextureExtended / DrawTexturedRect / DrawTexturedRectExtended | action | Textures |
| Overlay | DrawTextureInForegound / DrawTextureInDrawList / UpkeepTextures | action | Texture list mgmt |
| Overlay | ImageButton / ImageButtonExtended | action | Image buttons |

---

## DXOverlay.py

**Backend:** native `PyDXOverlay.DXOverlay()` (`self.renderer`) + `PyOverlay` for projection. **No
GLOBAL_CACHE equivalent** — low-level D3D geometry renderer. Nested via instance attributes
`.screen_space` / `.world_space` / `.mask`.

### DXOverlay (top-level)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| DXOverlay | WorldToScreen / FindZ | getter | Projection |
| DXOverlay | set_primitives / build_pathing_trapezoid_geometry / inverse_rendering / render | action | Geometry / render |
| DXOverlay | ApplyStencilMask / ResetStencilMask / SaveGeometryToFile | action | Stencil / save |
| DXOverlay | DrawLine(3D) / DrawTriangle(Filled)(3D) / DrawQuad(Filled)(3D) / DrawPoly(Filled)(3D) | action | 2D/3D primitives |
| DXOverlay | DrawCubeOutline / DrawCubeFilled | action | Cubes |
| DXOverlay | DrawTexture / DrawTexture3D / DrawQuadTextured3D | action | Textures |

### DXOverlay.screen_space / .world_space / .mask
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| DXOverlay.screen_space | set_screen_space / set_zoom_x / set_zoom_y / set_zoom / set_pan / set_rotation | action | Screen-space transform |
| DXOverlay.world_space | set_world_space / set_zoom_x / set_zoom_y / set_zoom / set_pan / set_scale / set_rotation | action | World-space transform |
| DXOverlay.mask | set_circular_mask / set_mask_radius / set_mask_center / set_rectangle_mask / set_rectangle_mask_bounds | action | Clipping masks |

---

## Keystroke.py  (`py4gwcorelib_src/Keystroke.py`)

**Backend:** native `PyKeystroke.PyKeyHandler()` (Reforged rename of legacy `PyScanCodeKeystroke`).
**No GLOBAL_CACHE equivalent** — direct input injection. All actions except the instance getter.

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Keystroke | keystroke_instance | getter | Raw PyKeyHandler instance |
| Keystroke | Press / Release / PressAndRelease | action | Single-key input |
| Keystroke | PressCombo / ReleaseCombo / PressAndReleaseCombo | action | Multi-key combos |

---

## Pathing.py

**Backend:** mixed — native `PyPathing.PathPlanner`/`PathStatus` for fast planning, but the bulk is a
pure-Python NavMesh/BSP/A* engine reaching game data via `Map.Pathing.GetPathingMaps()`. **No
GLOBAL_CACHE equivalent** — this IS the pathfinding engine; scripts mainly touch the `AutoPathing`
singleton (often via Routines). More engine than thin wrapper.

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| AutoPathing | get_navmesh | getter | Cached NavMesh for current map |
| AutoPathing | get_path / get_path_to | getter/action | Compute path (generator) |
| AutoPathing | load_pathing_maps | action | Load/cache navmesh (generator) |
| AutoPathing | clear_navmesh_cache / force_reload_navmesh | action | Clear / rebuild navmesh |
| NavMesh | find_trapezoid_id_by_coord / find_nearest_trapezoid_id / find_nearest_reachable / contains | getter | Point→trapezoid lookups |
| NavMesh | get_position / get_neighbors / get_adjacent_side / get_transition_cost | getter | Graph queries |
| NavMesh | has_line_of_sight / smooth_path_by_los / touching | getter | LOS / adjacency |
| NavMesh | create_portal / create_all_local_portals / save_to_file / load_from_file | action | Build / persist graph |
| TrapezoidBSP | find / find_with_margin | getter | BSP point lookup |
| AStar | heuristic / get_path | getter | Heuristic / result |
| AStar | search | action | Run A* search |
| (module) | chaikin_smooth_path / densify_path2d | getter | Path post-processing |

---

## Dialog.py

**Backend:** native `PyDialog.PyDialog` (defensive wrappers) + pure-Python text parsing. Module-level
functions + two data classes (no wrapper class, no sub-namespaces). No GLOBAL_CACHE facade.

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| (module) | get_active_dialog | getter | Current ActiveDialogInfo or None |
| (module) | get_active_dialog_buttons | getter | List of DialogButtonInfo |
| (module) | sanitize_dialog_text | getter | Strip tags/control chars |
| (module) | extract_inline_dialog_choices_from_text | getter | Parse `<a=id>` inline choices |
| ActiveDialogInfo | (dataclass) | getter | Parsed active-dialog view |
| DialogButtonInfo | (dataclass) | getter | Parsed dialog-button view |

*(Dialog send actions live on `Player.SendDialog` / `Player.SendAutomaticDialog` and
`UIManager.ClickDialogButton`.)*

---

## UIManager.py

**Backend:** native `PyUIManager.UIManager`/`UIFrame` + `PyOverlay`/`PyCallback`. **No GLOBAL_CACHE
equivalent** — this is the canonical UI-frame surface. Very large flat API plus a `FrameInfo`
descriptor and a family of high-level window helper classes (Inventory/Xunlai/Merchant/Salvage/etc.).

### UIManager (frame tree / lookup)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| UIManager | GetFrameByID / GetFrameIDByLabel / GetFrameIDByHash / GetHashByLabel / GetFrameIDByCustomLabel | getter | Frame lookup |
| UIManager | ConstructFramePath / GetFrameHierarchy / GetFrameArray / GetRootFrameID | getter | Frame path / tree |
| UIManager | GetChildFrameByFrameId / GetChildFramePathByFrameId / GetChildFrameID / GetAllChildFrameIDs / GetChildFrameIdFromNameHash | getter | Child navigation |
| UIManager | GetFirstChildFrameID / GetLastChildFrameID / GetNextChildFrameID / GetPrevChildFrameID / GetRelatedFrameID | getter | Sibling/child navigation |
| UIManager | GetParentFrameID / GetParentFrameIdDirect / GetParentID / IsAncestorOf | getter | Parent navigation |
| UIManager | GetItemFrameID / GetTabFrameID / GetOverlayFrameIDs / GetPopupFrameIDs | getter | Item/tab/overlay/popup ids |
| UIManager | SortFramesByVerticalPosition | getter | Sort frames top→bottom |

### UIManager (frame properties / state)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| UIManager | GetFrameContext / GetFrameNameHash / GetFrameLabel / GetFrameCode / GetFrameLayer / GetUserParam | getter | Frame attributes |
| UIManager | GetTextLabelEncoded / GetTextLabelDecoded / GetFrameTitleText | getter | Frame text |
| UIManager | GetFrameMinSize / GetFrameClientBorder / GetFrameClipRect / GetFramePositionEx / GetFrameNativeSize | getter | Frame geometry |
| UIManager | GetFrameCoords / GetContentFrameCoords / GetFrameCoordsByHash / GetViewPortScale / GetViewportDimensions | getter | Screen coords / viewport |
| UIManager | IsFrameCreated / IsVisible / FrameExists / IsMouseOver / GetStateBit / GetOpacity | getter | Frame state |
| UIManager | SetFrameLayer / SetVisible / SetDisabled / SetOpacity / ShowFrame | action | Frame visibility/layer |

### UIManager (IO events / input)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| UIManager | RegisterFrameIOEventCallback / UnregisterFrameIOEventCallback / RegisterFrameIOCallbacks / GetIOEventsForFrame | getter/action | Frame IO event tracking |
| UIManager | Keydown / Keyup / Keypress | action | Send key events to frame |
| UIManager | GetKeyMappings / SetKeyMappings | getter/action | Key mappings |

### UIManager (messages / draw / debug)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| UIManager | SendUIMessage / SendUIMessageRaw / SendFrameUIMessage / SendFrameUIMessageWString | action | Send UI messages |
| UIManager | FrameClick / TestMouseAction / TestMouseClickAction | action | Synthetic clicks/mouse |
| UIManager | DrawFrame / DrawFrameOutline / ColorFrames / DrawOnCompass | action | Overlay debug draw |
| UIManager | GetFrameLogs / ClearFrameLogs / GetUIMessageLogs / ClearUIMessageLogs | getter/action | Frame/message logs |

### UIManager (encoded strings / preferences / misc)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| UIManager | AsyncDecodeStr / IsValidEncStr / IsValidEncBytes / UInt32ToEncStr / EncStrToUInt32 | getter | Encoded-string helpers |
| UIManager | GetTextLanguage / IsWorldMapShowing / IsUIDrawn / IsShiftScreenshot / GetCurrentTooltipAddress | getter | Client/UI state |
| UIManager | GetFPSLimit / SetFPSLimit / SetOpenLinks | getter/action | FPS / link prefs |
| UIManager | GetPreferenceOptions / GetEnumPreference / GetIntPreference / GetStringPreference / GetBoolPreference | getter | Read preferences |
| UIManager | SetEnumPreference / SetIntPreference / SetStringPreference / SetBoolPreference | action | Set preferences |
| UIManager | LoadSettings / GetSettings | getter/action | UI settings blob |
| UIManager | GetWindoPosition / IsWindowVisible / SetWindowVisible / SetWindowPosition | getter/action | Window position/visibility |
| UIManager | IsLockedChestWindowVisible / IsNPCDialogVisible | getter | Dialog visibility |
| UIManager | GetDialogButtonIDs / GetDialogButtonCount / GetDialogButtonFrames | getter | Dialog buttons |
| UIManager | FindDialogOffset / ClickDialogButton / ConfirmMaxAmountDialog | action | Dialog interaction |

### UIManager.FrameInfo (descriptor dataclass)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| FrameInfo | GetFrameID / FrameExists / GetCoords / GetContentCoords / GetViewPortScale / GetViewportDimensions / IsMouseOver / GetIOEvents | getter | Per-frame accessors |
| FrameInfo | update_frame_id / DrawFrame / DrawFrameOutline / FrameClick | action | Refresh / draw / click |

### UIManager high-level window helpers (all IsOpen = getter, rest mostly actions)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| InventoryBagWindow / InventoryBagsWindow | IsOpen / GetBagFrame / GetBagSlotFrames / GetInventorySlotFrames | getter | Inventory bag frames |
| XunlaiStorageWindow | IsOpen / GetTabFrame / GetActiveTab* / GetTabSlotFrames / GetMaterialFrame / GetStorageSlotFrames | getter | Storage frames |
| XunlaiStorageWindow | ClickDepositAllMaterials | action | Deposit-all-materials |
| SkillTrainerWindow / TraderWindow / MerchantWindow / CrafterWindow | IsOpen / Close | getter/action | Vendor window state/close |
| CollectorWindow | IsOpen / Confirm / Close | getter/action | Collector exchange |
| CrafterWindow | IsCustomizeTabOpen / CustomizeWeapon | getter/action | Crafter customize |
| UpgradeWindow | IsOpen / Cancel / Confirm | getter/action | Upgrade-extract |
| SalvageOptionsWindow | IsOpen / GetSalvageOptionFrame / IsOptionVisible / Cancel / Confirm / SelectOption / SelectAndConfirmOption | getter/action | Salvage options |
| SalvageConfirmationPopup / LesserSalvageWindow / ExpertSalvageUnidentifiedWindow / AnySalvageWindow | IsOpen / Cancel / Confirm | getter/action | Salvage confirm dialogs |

*(`WindowFrame`/`WindowFrames` is a data catalog of known-frame `FrameInfo` constants — no methods.)*

---

## GWUI.py

**Backend:** native `PyUIManager.UIManager` + low-level `NativeFunction` bridges + `Scanner`. **No
GLOBAL_CACHE equivalent** — a toolkit that constructs real in-game GW window controls (distinct from
the ImGui overlay). Create* = actions; Is*/Get* = getters.

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| GWUI | CreateWindow / DestroyWindow / ClearInputTargets | action | Window lifecycle |
| GWUI | CreatePanel / CreateScrollableContent / AddTextItem / CreateScrollableWindow | action | Panels / text lists |
| GWUI | CreateButtonList / CreateButton | action | Buttons |
| GWUI | IsButtonPushed / IsButtonClicked | getter | Button state |
| GWUI | CreateCheckbox / SetChecked | action | Checkbox |
| GWUI | IsChecked | getter | Checkbox state |
| GWUI | CreateRadioGroup / SetRadioSelection | action | Radio group |
| GWUI | GetRadioSelection | getter | Radio selection |
| GWUI | CreateHyperlinkList / CreateHyperlink / SetHyperlinkColor / SetHyperlinkHoverColor / SetHyperlinkText | action | Hyperlinks |
| GWUI | GetClickedHyperlink | getter | Clicked hyperlink |
| GWUI | CreateEditBox / SetEditBoxText / SetEditBoxMaxLength | action | Edit box |
| GWUI | GetEditBoxText | getter | Edit box text |
| GWUI | CreateProgressBar / SetProgressBarPercent / SetProgressBarValue / SetProgressBarMax | action | Progress bar |
| GWUI | CreateTabs / AddTab / SelectTab | action | Tabs |
| GWUI | GetActiveTab / GetTabBodyFrame / IsTabChanged | getter | Tab state |
| GWUI | CreateSlider / SetSliderValue / DestroySlider | action | Slider |
| GWUI | GetSliderValue | getter | Slider value |
| GWUI | CreateGroupHeader / SetGroupHeaderOpen / SetGroupHeaderText / RegisterGroupSection / UpdateGroupSections | action | Collapsible groups |
| GWUI | IsGroupHeaderOpen | getter | Group state |
| GWUI | create_dropdown / create_slider / create_editable_text / create_progress_bar / create_tabs / CtlFrameListCreateItem / FrameNewSubclass | action | Low-level native control creation |

---

## PacketSniffer.py  (singleton `SNIFFER`)

**Backend:** native `PyPacketSniffer.PacketSniffer` singleton + pure-Python decoders. No GLOBAL_CACHE.
Public dataclass `PacketLogEntry` (direction/tick/header/size/data, no methods).

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| PacketSniffer | instance | getter | Get singleton |
| PacketSniffer | get_logs | getter | Captured packet entries |
| PacketSniffer | get_packet_name / decode_packet | getter | Name / decode a packet |
| PacketSniffer | initialize / terminate | action | Start / stop sniffing |
| PacketSniffer | clear_logs | action | Clear capture buffer |

---

## CombatEvents.py  (`COMBAT_EVENTS`, `CombatEventQueue`)

**Backend:** native `PyCombatEvents.GetCombatEventQueue()` (Reforged `PyAgentEvents`) + Python callback
layer via `PyCallback`. No GLOBAL_CACHE.

### CombatEventQueue (raw queue)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| CombatEventQueue | GetQueue / IsInitialized / PeekEvents / PeekEventTuples / GetMaxEvents / GetQueueSize | getter | Queue state / peek |
| CombatEventQueue | GetAndClearEvents / GetAndClearEventTuples | getter/action | Drain events |
| CombatEventQueue | Initialize / Terminate / SetMaxEvents | action | Queue lifecycle |

### CombatEvents (managed)
| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| CombatEvents | GetEvents / GetRecentDamage / GetRecentHealing / GetRecentEffectRenewals / GetRecentSkills | getter | Processed event queries |
| CombatEvents | ClearEvents / ClearCallbacks / ClearRechargeData | action | Clear buffers/callbacks |
| CombatEvents | OnSkillActivated / OnSkillFinished / OnSkillInterrupted / OnAttackStarted / OnKnockdown / OnDamage / OnHealing / OnEffectRenewed / OnAftercastEnded / OnSkillRechargeStarted / OnSkillRecharged | action | Register callbacks |
| CombatEvents | Update / Enable / Disable | action | Callback tick lifecycle |

---

## Scanner.py

**Backend:** thin wrapper over native `PyScanner.PyScanner`. No GLOBAL_CACHE — low-level RE/pattern
scanning primitive. Public enum `ScannerSection` (TEXT/RDATA/DATA).

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| Scanner | Initialize | action | Init scanner for a module |
| Scanner | Find / FindInRange / FindAssertion | getter | Pattern search |
| Scanner | GetSectionAddressRange / IsValidPtr | getter | Section range / ptr check |
| Scanner | FunctionFromNearCall / ToFunctionStart | getter | Call/function resolution |
| Scanner | FindUseOfAddress / FindNthUseOfAddress | getter | Address xrefs |
| Scanner | FindUseOfStringA / FindNthUseOfStringA / FindUseOfStringW / FindNthUseOfStringW | getter | String xrefs |

---

## Context.py  (`GWContext`)

**Backend:** the raw **Context path** — reads ctypes structs from shared memory via per-context facades
in `native_src/context/*`. Not bindings, not GLOBAL_CACHE — this IS the layer higher tiers cache.
**All getters (read-only).** Every sub-context exposes the same three: `GetPtr` (native pointer int),
`GetContext` (ctypes struct or None), `IsValid` (present?).

| class / sub-namespace | method | getter/action | purpose |
|---|---|---|---|
| GWContext.AccAgent | GetPtr / GetContext / IsValid | getter | Account-agent context |
| GWContext.AgentArray | GetPtr / GetContext / IsValid | getter | Agent-array context |
| GWContext.AvailableCharacterArray | GetPtr / GetContext / IsValid | getter | Available-characters context |
| GWContext.Char | GetPtr / GetContext / IsValid | getter | Character context |
| GWContext.Cinematic | GetPtr / GetContext / IsValid | getter | Cinematic context |
| GWContext.Gameplay | GetPtr / GetContext / IsValid | getter | Gameplay context |
| GWContext.Guild | GetPtr / GetContext / IsValid | getter | Guild context |
| GWContext.InstanceInfo | GetPtr / GetContext / IsValid / GetMapInfo | getter | Instance-info (+ current map AreaInfo) |
| GWContext.Map | GetPtr / GetContext / IsValid | getter | Map context |
| GWContext.MissionMap | GetPtr / GetContext / IsValid | getter | Mission-map context |
| GWContext.Party | GetPtr / GetContext / IsValid | getter | Party context |
| GWContext.PreGame | GetPtr / GetContext / IsValid | getter | Pre-game (char-select) context |
| GWContext.ServerRegion | GetPtr / GetContext / IsValid | getter | Server-region context |
| GWContext.World | GetPtr / GetContext / IsValid | getter | World context |
| GWContext.WorldMap | GetPtr / GetContext / IsValid | getter | World-map context |
