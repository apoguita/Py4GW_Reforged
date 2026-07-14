# C++ Bindings — GW Gameplay Domain

Complete inventory of every pybind binding in the Py4GW Reforged Native GW gameplay modules (`src/GW/<module>/*_bindings.cpp`), for building a demo/test widget that exercises every binding and data getter. Legend for the **Kind** column: **getter** = reads state, **action** = mutates/sends (queue a button in the demo), **ctor/handle** = constructor or handle, **field** = data attribute.

Registered module names come from `src/base/python_runtime.cpp` (the import list). Modules covered here: `PyAgent`, `PyAgentRecolor`, `PyCamera`, `PyChat`, `PyDialog`, `PyEffects`, `PyFriendList`, `PyGuild`, `PyItem`, `PyInventory`, `PyMap`, `PyMerchant`, `PyNameObfuscator`, `PyPacketSniffer`, `PyParty`, `PyPathing`, `PyPing`, `PyPlayer`, `PyQuest`, `PySkill`, `PySkillbar`, `PyTrade`, `PyUIManager`. Note: **`stoc` exposes NO bindings** (no `*_bindings.cpp`; it feeds `PyPacketSniffer`).

---

## PyAgent (`agent/agent_bindings.cpp`)

### Enum
- `ProfessionType` — 11 values (None, Warrior … Dervish).

### class `Profession`
| member | kind | signature/return | purpose |
|---|---|---|---|
| `__init__()` / `(int)` / `(str)` | ctor | | build from prof id or name |
| `GetName` | getter | str | profession name |
| `ToInt` | getter | int | profession id |
| `Set` | action | (prof:int) | set profession |
| `Get` | getter | ProfessionType | enum value |
| `__eq__`/`__ne__` | getter | bool | comparison |

### class `PyAgent`
| member | kind | signature/return | purpose |
|---|---|---|---|
| `__init__()` / `(agent_id)` | ctor/handle | | wrap an agent id |
| `GetContext` | action | | no-op refresh (fields are live) |
| `GetAgentID` | getter | int | agent id |
| `GetPlayerNumber` | getter | int | login/player number |
| `GetName` | getter | str | encoded name → ascii |
| `GetPrimary` / `GetSecondary` | getter | int | primary/secondary prof |
| `GetLevel` | getter | int | level |
| `GetHP` | getter | float | hp fraction |
| `GetRotation` | getter | float | rotation angle |
| `GetPos` | getter | tuple(x,y,z) | world position |
| `GetIsLiving`/`GetIsDead`/`GetIsMoving`/`GetIsAttacking`/`GetIsKnockedDown`/`GetIsCasting` | getter | bool | living-state flags |
| `GetAllegiance` | getter | int | allegiance |
| `GetIsGadget`/`GetIsItem` | getter | bool | type flags |
| `GetTargetId` (static) | getter | int | current target |
| `GetControlledCharacterId` (static) | getter | int | own char |
| `GetObservingId` (static) | getter | int | observed agent |

### Module free functions
| member | kind | signature | purpose |
|---|---|---|---|
| `send_dialog` | action | (dialog_id) | send NPC dialog |
| `get_observing_id` / `get_controlled_character_id` / `get_target_id` | getter | ()→int | ids |
| `get_amount_of_players_in_instance` | getter | ()→int | player count |
| `is_observing` | getter | ()→bool | observer mode |
| `change_target` | action | (agent_id)→bool | change target (queued) |
| `move` | action | (x,y,zplane=0) | move-to |
| `interact_agent` | action | (agent_id, call_target=False) | interact |
| `call_target` | action | (agent_id) | call target |
| `get_player_name_by_login_number` | getter | (login_number)→str | |
| `get_agent_id_by_login_number` | getter | (login_number)→int | |
| `get_hero_agent_id` | getter | (hero_index)→int | |
| `get_agent_enc_name` | getter | (agent_id)→bytes | raw encoded name |
| `get_agent_is_targettable` | getter | (agent_id)→bool | |

---

## PyAgentRecolor (`agent_recolor/agent_recolor_bindings.cpp`)
Name-tag color override (ARGB). All module-level functions; no classes/enums.

| member | kind | signature | purpose |
|---|---|---|---|
| `enable` / `disable` | action | () | toggle override detour |
| `is_enabled` / `is_hook_installed` | getter | ()→bool | state |
| `set_agent_color` | action | (agent_id, argb) | per-agent color |
| `remove_agent_color` | action | (agent_id)→bool | drop rule |
| `set_allegiance_color` | action | (allegiance, argb) | category color |
| `remove_allegiance_color` | action | (allegiance)→bool | drop rule |
| `clear_rules` | action | () | drop all overrides |
| `get_agent_rules` / `get_allegiance_rules` | getter | | rule stores |
| `read_consider_color` | getter | (agent_id)→ARGB | game-computed color (read-only) |
| `get_diagnostics` | getter | ()→dict | counters dict |
| `reset_diagnostics` | action | () | zero counters |

---

## PyCamera (`camera/camera_bindings.cpp`)

### class `Point3D` (Vec3 helper)
Fields `x`,`y`,`z` (readwrite floats); default ctor.

### class `PyCamera`
Constructed with default ctor (snapshots via `GetContext`). **Data fields (readwrite)**: `look_at_agent_id`, `yaw`, `pitch`, `camera_zoom`, `max_distance`, `yaw_right_click`, `yaw_right_click2`, `pitch_right_click`, `distance2`, `acceleration_constant`, `field_of_view`, `field_of_view2`, `h0024` (list), `h0070` (list), and Point3D positions `position`, `camera_pos_to_go`, `cam_pos_inverted`, `cam_pos_inverted_to_go`, `look_at_target`, `look_at_to_go`.

| method | kind | signature | purpose |
|---|---|---|---|
| `GetContext` | getter | () | refresh snapshot from camera ctx |
| `SetYaw`/`SetPitch` | action | (val) | rotate (queued) |
| `SetMaxDist` | action | (dist) | max distance |
| `SetFieldOfView` | action | (fov) | FOV |
| `UnlockCam` | action | (unlock) | free-cam toggle |
| `GetCameraUnlock` | getter | ()→bool | free-cam state |
| `ForwardMovement`/`VerticalMovement`/`SideMovement`/`RotateMovement` | action | (amount…) | move free cam |
| `ComputeCameraPos` | getter | ()→tuple | compute cam pos |
| `UpdateCameraPos` | action | () | push cam pos |
| `SetCameraPos`/`SetLookAtTarget` | action | (x,y,z) | set pos/target |
| `SetFog` | action | (fog) | fog toggle |

### Module free functions
`forward_movement`, `vertical_movement`, `rotate_movement`, `side_movement` (actions); `set_max_dist(dist=900)`, `set_field_of_view(fov)`, `unlock_cam(flag)`, `set_fog(flag)` (actions); `compute_cam_pos(dist=0)→tuple`, `update_camera_pos()` (action); getters `get_field_of_view()→float`, `get_yaw()→float`, `get_camera_unlock()→bool`, `get_context_ptr()→int`.

---

## PyChat (`chat/chat_bindings.cpp`)
All module-level functions; no classes/enums.

| member | kind | signature | purpose |
|---|---|---|---|
| `force_redraw_chat_log` | action | () | redraw log |
| `get_is_typing` | getter | ()→bool | typing state |
| `send_chat` | action | (channel:int, msg) | send to channel |
| `send_chat_by_name` | action | (from, msg) | whisper by name |
| `write_chat` | action | (channel, message) | local write |
| `write_chat_ex` | action | (channel, message, sender) | local write w/ sender |
| `toggle_timestamps` | action | (enable) | |
| `set_timestamps_format` | action | (use_24h, show_seconds=False) | |
| `set_timestamps_color` | action | (r,g,b) | |
| `set_sender_color` | action | (channel, r,g,b) | |
| `set_message_color` | action | (channel, r,g,b) | |
| `send_fake_chat` | action | (channel, message) | inject fake line |
| `send_fake_chat_colored` | action | (channel, message, r,g,b) | inject colored line |

---

## PyDialog (`dialog/dialog_bindings.cpp`)

### Data classes (all `def_readwrite` fields, default ctor)
- `DialogInfo`: `dialog_id`, `flags`, `frame_type`, `event_handler`, `content_id`, `property_id`, `content`, `agent_id`.
- `ActiveDialogInfo`: `dialog_id`, `context_dialog_id`, `agent_id`, `dialog_id_authoritative`, `message`.
- `DialogButtonInfo`: `dialog_id`, `button_icon`, `message`, `message_decoded`, `message_decode_pending`.
- `DialogTextDecodedInfo`: `dialog_id`, `text`, `pending`.
- `DialogEventLog`: `tick`, `message_id`, `incoming`, `is_frame_message`, `frame_id`, `w_bytes`, `l_bytes`.
- `DialogCallbackJournalEntry`: `tick`, `message_id`, `incoming`, `dialog_id`, `context_dialog_id`, `agent_id`, `map_id`, `model_id`, `dialog_id_authoritative`, `context_dialog_id_inferred`, `npc_uid`, `event_type`, `text`.

### class `PyDialog` (all `def_static`)
| member | kind | signature/return | purpose |
|---|---|---|---|
| `is_dialog_available` | getter | (dialog_id)→bool | |
| `get_dialog_info` | getter | (dialog_id)→DialogInfo | |
| `get_last_selected_dialog_id` | getter | ()→int | |
| `get_active_dialog` | getter | ()→ActiveDialogInfo | |
| `get_active_dialog_buttons` | getter | ()→[DialogButtonInfo] | |
| `is_dialog_active` | getter | ()→bool | |
| `is_dialog_displayed` | getter | (dialog_id)→bool | |
| `enumerate_available_dialogs` | getter | ()→list | |
| `get_dialog_text_decoded` | getter | (dialog_id)→DialogTextDecodedInfo | |
| `is_dialog_text_decode_pending` | getter | (dialog_id)→bool | |
| `get_dialog_text_decode_status` | getter | ()→ | |
| `read_dialog_flags`/`read_dialog_frame_type`/`read_dialog_event_handler`/`read_dialog_content_id`/`read_dialog_property_id` | getter | (dialog_id) | catalog reads |
| `get_dialog_event_logs`/`_received`/`_sent` | getter | ()→[DialogEventLog] | packet logs |
| `clear_dialog_event_logs`/`_received`/`_sent` | action | () | clear logs |
| `get_dialog_callback_journal`/`_received`/`_sent` | getter | ()→[DialogCallbackJournalEntry] | callback journal |
| `clear_dialog_callback_journal`/`_received`/`_sent` | action | () | clear journal |
| `clear_dialog_callback_journal_filtered` | action | (npc_uid?, incoming?, message_id?, event_type?) | filtered clear |
| `clear_cache` | action | () | clear cache |
| `initialize` / `terminate` | action | () | lifecycle |

---

## PyEffects (`effects/effects_bindings.cpp`)

### Data classes (all `def_readonly`)
- `EffectType`: `skill_id`, `attribute_level`, `effect_id`, `agent_id`, `duration`, `timestamp`, `time_elapsed`, `time_remaining`.
- `BuffType`: `skill_id`, `buff_id`, `target_agent_id`.

### class `PyEffects` (ctor `(agent_id)`)
| member | kind | signature/return | purpose |
|---|---|---|---|
| `GetEffects` | getter | ()→[EffectType] | agent effects |
| `GetBuffs` | getter | ()→[BuffType] | agent buffs |
| `GetEffectCount`/`GetBuffCount` | getter | ()→int | counts |
| `EffectExists`/`BuffExists` | getter | (skill_id)→bool | presence |
| `DropBuff` | action | (skill_id) | drop buff |
| `GetAlcoholLevel` (static) | getter | ()→int | |
| `ApplyDrunkEffect` (static) | action | (intensity=0, tint=0) | |

### Module free functions
`get_alcohol_level()→int` (getter); `get_drunk_af(intensity, tint)` (action); `drop_buff(buff_id)` (action); `effect_count(agent_id)→int`, `buff_count(agent_id)→int`, `effect_exists(agent_id, skill_id)→bool`, `buff_exists(agent_id, skill_id)→bool`, `get_effects(agent_id)→[EffectType]`, `get_buffs(agent_id)→[BuffType]` (getters).

---

## PyFriendList (`friend_list/friend_list_bindings.cpp`)
All module-level functions.

| member | kind | signature | purpose |
|---|---|---|---|
| `get_number_of_friends` | getter | (friend_type=1)→int | |
| `get_number_of_ignores`/`_partners`/`_traders` | getter | ()→int | |
| `get_my_status` | getter | ()→int | own status |
| `set_friend_list_status` | action | (status)→bool | set status (queued) |
| `add_friend` | action | (name, alias="")→bool | |
| `add_ignore` | action | (name, alias="")→bool | |

---

## PyGuild (`guild/guild_bindings.cpp`)
All module-level functions.

| member | kind | signature | purpose |
|---|---|---|---|
| `get_player_guild_index` | getter | ()→int | |
| `get_player_guild_announcement` | getter | ()→str | |
| `get_player_guild_announcer` | getter | ()→str | |
| `travel_gh` | action | ()→bool | travel to guild hall |
| `leave_gh` | action | ()→bool | leave guild hall |

---

## PyItem (`item/item_bindings.cpp`)

### class `ItemModifier` (ctor `(uint32)`)
Getters: `GetIdentifier`, `GetArg1`, `GetArg2`, `GetArg`, `IsValid`→bool, `GetModBits`→str, `ToString`→str.

### enum `Rarity` — 5 values (White, Blue, Purple, Gold, Green).

### class `ItemTypeClass` (ctor `(int)`)
`ToInt`, `GetName`, `__eq__`, `__ne__`.

### class `DyeColorClass` (ctor `(int)`)
`ToInt`, `ToString`, `__eq__`, `__ne__`.

### class `DyeInfo` (default ctor, `def_readonly`)
Fields `dye_tint`, `dye1`..`dye4` (DyeColorClass); method `ToString`.

### class `PyItem` (ctor `(item_id)`) — main data class
Methods: `GetContext` (getter refresh), `RequestName` (action, async), `IsItemNameReady`→bool, `GetName`→str, `GetInfoString`/`GetNameEnc`/`GetCompleteNameEnc`/`GetSingleItemName`→bytes (getters), `IsItemValid(id)`→bool, `GetCompositeModelIDs` (static)→[int].
**`def_readonly` fields (all getters)**: `item_id`, `agent_id`, `agent_item_id`, `name`, `modifiers` ([ItemModifier]), `is_customized`, `item_type` (ItemTypeClass), `dye_info` (DyeInfo), `value`, `interaction`, `model_id`, `model_file_id`, `item_formula`, `is_material_salvageable`, `quantity`, `equipped`, `profession`, `slot`, `is_stackable`, `is_inscribable`, `is_material`, `is_zcoin`, `rarity` (Rarity), `uses`, `is_id_kit`, `is_salvage_kit`, `is_tome`, `is_lesser_kit`, `is_expert_salvage_kit`, `is_perfect_salvage_kit`, `is_weapon`, `is_armor`, `is_salvageable`, `is_inventory_item`, `is_storage_item`, `is_rare_material`, `is_offered_in_trade`, `is_sparkly`, `is_identified`, `is_prefix_upgradable`, `is_suffix_upgradable`, `is_usable`, `is_tradable`, `is_inscription`, `is_rarity_blue`, `is_rarity_purple`, `is_rarity_green`, `is_rarity_gold`.

### Module free functions
| member | kind | signature | purpose |
|---|---|---|---|
| `use_item_by_id` | action | (item_id)→bool | |
| `equip_item_by_id` | action | (item_id, agent_id=0)→bool | |
| `drop_item_by_id` | action | (item_id, quantity)→bool | |
| `pick_up_item_by_id` | action | (item_id, call_target=0)→bool | |
| `move_item` | action | (item_id, bag_id, slot, quantity=0)→bool | |
| `use_item_by_model_id` | action | (model_id, bag_start=1, bag_end=4)→bool | |
| `count_item_by_model_id` | getter | (model_id, bag_start=1, bag_end=4)→int | |
| `get_gold_amount_on_character` / `get_gold_amount_in_storage` | getter | ()→int | |
| `drop_gold` | action | (amount=1)→bool | |
| `deposit_gold` / `withdraw_gold` | action | (amount=0)→int | |
| `change_gold` | action | (character_gold, storage_gold)→bool | |
| `salvage_start` | action | (salvage_kit_id, item_id)→bool | |
| `identify_item` | action | (identification_kit_id, item_id)→bool | |
| `salvage_session_cancel` / `salvage_session_done` | action | ()→bool | |
| `destroy_item` | action | (item_id)→bool | |
| `salvage_materials` | action | ()→bool | |
| `open_xunlai_window` | action | (anniversary_pane_unlocked=True) | |
| `get_storage_page` | getter | ()→int | |
| `get_is_storage_open` | getter | ()→bool | |
| `can_access_xunlai_chest` | getter | ()→bool | |
| `get_material_storage_stack_size` | getter | ()→int | |

---

## PyInventory (`item/inventory_bindings.cpp`)

### class `Bag` (ctor `(id, name="")`)
Methods: `GetItems`→list[dict] (getter), `GetItemCount`→int, `GetSize`→int, `GetContext` (getter refresh). `def_readonly` fields: `id`, `name`, `container_item`, `items_count`, `is_inventory_bag`, `is_storage_bag`, `is_material_storage`.

### class `PyInventory` (default ctor)
| member | kind | signature | purpose |
|---|---|---|---|
| `OpenXunlaiWindow` | action | () | open storage (queued) |
| `GetIsStorageOpen` | getter | ()→bool | |
| `PickUpItem` | action | (item_id, call_target=False) | |
| `DropItem` | action | (item_id, quantity=1) | |
| `EquipItem` | action | (item_id, agent_id) | |
| `UseItem` | action | (item_id) | |
| `DestroyItem` | action | (item_id) | |
| `IdentifyItem` | action | (id_kit_id, item_id) | |
| `GetHoveredItemID` | getter | ()→int | |
| `GetGoldAmount` / `GetGoldAmountInStorage` | getter | ()→int | |
| `DepositGold`/`WithdrawGold`/`DropGold` | action | (amount) | |
| `MoveItem` | action | (item_id, bag_id, slot, quantity=1) | |
| `Salvage` | action | (salv_kit_id, item_id) | |
| `AcceptSalvageWindow` | action | () | click salvage confirm |

### Module free functions
`get_bag(bag_id)→dict` (getter, dict-based bag snapshot with `items` list); `get_hovered_item_id()→int` (getter); `salvage(salv_kit_id, item_id)` (action); `accept_salvage_window()` (action).

---

## PyMap (`map/map_bindings.cpp`)
All module-level functions; no classes/enums. (Includes a RAW collision raycast bridge.)

| member | kind | signature | purpose |
|---|---|---|---|
| `travel` | action | (map_id, region=-2, district_number=0, language=0) | map travel |
| `travel_to_district` | action | (map_id, district=0, district_number=0) | travel to district |
| `map_test_start` | action | (map_id, alt_map_id, number=2, count=3, delay_ms=0, timeout_ms=10000, message_id=…) | test harness |
| `map_test_stop` | action | () | |
| `map_test_get_status` | getter | ()→str | |
| `map_test_is_active` | getter | ()→bool | |
| `map_test_get_count` | getter | ()→int | |
| `enter_challenge` / `cancel_enter_challenge` | action | ()→bool | |
| `query_altitude` | getter | (x, y, radius=100)→tuple(result, altitude, nx, ny, nz) | terrain altitude/normal |
| `get_is_map_loaded` | getter | ()→bool | |
| `get_map_id` | getter | ()→int | |
| `get_is_map_unlocked` | getter | (map_id)→bool | |
| `get_region` / `get_language` | getter | ()→int | |
| `get_is_observing` | getter | ()→bool | |
| `get_district` | getter | ()→int | |
| `get_instance_time` | getter | ()→int | |
| `get_instance_type` | getter | ()→int | |
| `get_foes_killed` / `get_foes_to_kill` | getter | ()→int | |
| `get_is_in_cinematic` | getter | ()→bool | |
| `skip_cinematic` | action | ()→bool | |
| `region_from_district` / `language_from_district` | getter | (district)→int | |
| `RayCast` | getter | (start, unit_dir)→tuple(has_hit, x,y,z, prop_layer) | raw combined raycast |
| `RayCastTerrain` | getter | (start, end)→tuple(has_hit, frac) | raw terrain raycast |
| `RayCastInteractive` | getter | (start, unit_dir, max_range)→tuple(has_hit, dist, prop_id, n_scanned) | interactive-prop probe |
| `GetProps` | getter | ()→list of (prop_id, x,y,z, is_interactive, rec_count) | enumerate props |
| `GetPropGeometry` | getter | (prop_id)→list of (matrix12, tris_local) | prop collision mesh |

---

## PyMerchant (`merchant/merchant_bindings.cpp`)

### class `PyMerchant` (default ctor; all `def_static`)
| member | kind | signature | purpose |
|---|---|---|---|
| `trader_buy_item` | action | (item_id, cost)→bool | trader buy |
| `trader_sell_item` | action | (item_id, price)→bool | trader sell |
| `trader_request_quote` | action | (item_id)→bool | buy quote |
| `trader_request_sell_quote` | action | (item_id)→bool | sell quote |
| `merchant_buy_item` | action | (item_id, cost)→bool | |
| `merchant_sell_item` | action | (item_id, price)→bool | |
| `crafter_buy_item` | action | (item_id, cost, give_item_ids, give_item_quantities)→bool | |
| `collector_buy_item` | action | (item_id, cost, give_item_ids, give_item_quantities)→bool | |
| `get_trader_item_list` | getter | ()→[int] | trader items |
| `get_trader_item_list2` | getter | ()→[int] | (always empty, legacy) |
| `get_merchant_item_list` | getter | ()→[int] | merchant window items |
| `get_quoted_value` | getter | ()→int | last quote gold |
| `get_quoted_item_id` | getter | ()→int | last quote item |
| `is_transaction_complete` | getter | ()→bool | |
| `update` | action | () | legacy no-op |

### Module free functions
`transact_items(type, gold_give=0, give_item_ids=[], give_quantities=[], gold_recv=0, recv_item_ids=[], recv_quantities=[])→bool` (action); `request_quote(type, give_item_ids=[], recv_item_ids=[])→bool` (action).

---

## PyNameObfuscator (`name_obfuscator/name_obfuscator_bindings.cpp`)

### class `ObservedPlayer` (`def_readonly`)
Fields: `player_number`, `agent_id`, `real_name`, `display_name`, `aliased`.

### Module free functions
| member | kind | signature | purpose |
|---|---|---|---|
| `enable`/`disable` | action | () | toggle obfuscation |
| `is_enabled` / `is_map_ready` | getter | ()→bool | |
| `set_alias` | action | (real_name, fake_name) | register alias |
| `remove_alias` | action | (real_name)→bool | |
| `clear_aliases` / `clear` | action | () | drop all aliases |
| `alias_count` | getter | ()→int | |
| `get_aliases` | getter | ()→ | alias map |
| `get_real_name` | getter | (display_name)→str | reverse resolve |
| `get_display_name` | getter | (real_name)→str | resolve |
| `require_real_name` | getter | (name)→str | resolve or passthrough |
| `set_surface_enabled` | action | (surface, enabled)→bool | toggle name surface |
| `is_surface_enabled` | getter | (surface)→bool | |
| `list_surfaces` | getter | ()→list | |
| `scrub_guild_roster` / `scrub_guild_identity` | action | ()→int | scrub guild data |
| `clear_observed_cache` | action | () | |
| `observed_count` | getter | ()→int | |
| `get_observed_players` | getter | ()→[ObservedPlayer] | |
| `get_diagnostics` | getter | ()→dict | ~30 counters |
| `reset_diagnostics` | action | () | |

---

## PyPacketSniffer (`packet_sniffer/packet_sniffer_bindings.cpp`)

### enum `PacketDirection` — 2 values (StoC, CToS; `export_values`).

### class `PacketLogEntry` (default ctor, `def_readonly`)
Fields: `tick`, `direction` (PacketDirection), `header`, `size`, `data`; plus `__repr__`.

### class `PacketSniffer`
| member | kind | signature | purpose |
|---|---|---|---|
| `instance` (static) | ctor/handle | ()→PacketSniffer | singleton |
| `initialize`/`initialize_stoc`/`initialize_ctos` | action | ()→bool | start capture |
| `terminate`/`terminate_stoc`/`terminate_ctos` | action | () | stop capture |
| `get_logs`/`get_stoc_logs`/`get_ctos_logs` | getter | ()→[PacketLogEntry] | |
| `clear_logs`/`clear_stoc_logs`/`clear_ctos_logs` | action | () | |

---

## PyParty (`party/party_bindings.cpp`) — large surface

### enum `HeroType` — 38 values (None, Norgu … ZeiRi incl. 8 Mercenary heroes).

### class `Hero` (ctor `(int)` or `(str)`)
`GetID`→int, `GetName`→str, `GetProfession`→int (getters); `FlagHero(idx)`→bool (action); `__eq__`/`__ne__`/`__repr__`.

### class `PartyTick` (ctor `(ticked=False)`)
`IsTicked`→bool (getter), `SetTicked(ticked)` (action), `ToggleTicked` (action), `SetTickToggle(enable)` (action).

### PartyMember structs (`def_readwrite`, constructible)
- `PlayerPartyMember`: `login_number`, `called_target_id`, `is_connected`, `is_ticked`.
- `HeroPartyMember`: `agent_id`, `owner_player_id`, `hero_id`, `level`, `primary`, `secondary`.
- `HenchmanPartyMember`: `agent_id`, `profession`, `level`.
- `PetInfo` (ctor `(owner_agent_id)`, `def_readonly`): `agent_id`, `owner_agent_id`, `pet_name`, `model_file_id1`, `model_file_id2`, `behavior`, `locked_target_id`.

### class `PyParty` (default ctor)
| method | kind | signature | purpose |
|---|---|---|---|
| `GetContext` | getter | () | refresh snapshot |
| `ReturnToOutpost` | action | ()→bool | |
| `SetHardMode` | action | (flag)→bool | |
| `RespondToPartyRequest` | action | (party_id, accept)→bool | |
| `AddHero`/`KickHero` | action | (hero_id)→bool | |
| `KickAllHeroes` | action | ()→bool | |
| `AddHenchman`/`KickHenchman` | action | (henchman_id)→bool | |
| `KickPlayer`/`InvitePlayer` | action | (player_id)→bool | |
| `LeaveParty` | action | ()→bool | |
| `FlagHero` | action | (agent_id, x, y)→bool | |
| `FlagAllHeroes` | action | (x, y)→bool | |
| `UnflagHero` | action | (agent_id)→bool | |
| `UnflagAllHeroes` | action | ()→bool | |
| `IsHeroFlagged`/`IsAllFlagged` | getter | ()→bool | |
| `GetAllFlagX`/`GetAllFlagY` | getter | ()→float | |
| `GetHeroAgentID` | getter | (hero_index)→int | |
| `GetAgentHeroID` | getter | (agent_id)→int | |
| `GetAgentIDByLoginNumber` | getter | (login_number)→int | |
| `GetPlayerNameByLoginNumber` | getter | (login_number)→str | |
| `SearchParty` | action | (search_type, advertisement)→bool | |
| `SearchPartyCancel` | action | ()→bool | |
| `SearchPartyReply` | action | (accept)→bool | |
| `SetHeroBehavior` | action | (agent_id, behavior) | |
| `SetPetBehavior` | action | (behaviour, lock_target_id) | |
| `GetPetInfo` | getter | (owner_agent_id)→PetInfo | |
| `GetIsPlayerTicked` | getter | (player_id)→bool | |
| `UseHeroSkill` | action | (hero_id, skill_slot, target_id) | |
| `SetHeroSkillAIEnabled` | action | (hero_agent_id, skill_slot, enabled)→bool | |
| `GetPartyContextPtr` | getter | ()→int | raw ptr |

`def_readwrite` fields: `party_id`, `players` ([PlayerPartyMember]), `heroes` ([HeroPartyMember]), `henchmen` ([HenchmanPartyMember]), `others` ([int]), `is_in_hard_mode`, `is_hard_mode_unlocked`, `party_size`, `party_player_count`, `party_hero_count`, `party_henchman_count`, `is_party_defeated`, `is_party_loaded`, `is_party_leader`, `tick`.

### Module free functions
Actions: `set_tick_toggle(enable)`, `tick(flag=True)→bool`, `set_hard_mode(flag)→bool`, `return_to_outpost()→bool`, `respond_to_party_request(party_id, accept)→bool`, `leave_party()→bool`, `add_hero(hero_id)→bool`, `kick_hero(hero_id)→bool`, `kick_all_heroes()→bool`, `add_henchman(agent_id)→bool`, `kick_henchman(agent_id)→bool`, `invite_player_by_id(player_id)→bool`, `invite_player_by_name(player_name)→bool`, `kick_player(player_id)→bool`, `flag_hero(hero_index, x, y)→bool`, `flag_hero_agent(agent_id, x, y)→bool`, `unflag_hero(hero_index)→bool`, `flag_all(x, y)→bool`, `unflag_all()→bool`, `set_hero_behavior(agent_id, behavior)→bool`, `set_hero_skill_ai_enabled(hero_agent_id, skill_slot, enabled)→bool`, `set_pet_behavior(behavior, lock_target_id=0)→bool`, `search_party(search_type, advertisement="")→bool`, `search_party_cancel()→bool`, `search_party_reply(accept)→bool`.
Getters: `get_party_size()`, `get_party_player_count()`, `get_party_hero_count()`, `get_party_henchman_count()`→int; `get_is_party_defeated()`, `get_is_party_in_hard_mode()`, `get_is_hard_mode_unlocked()`, `get_is_party_ticked()`→bool; `get_is_player_ticked(player_index=0xFFFFFFFF)→bool`, `get_is_player_loaded(player_index=0xFFFFFFFF)→bool`, `get_is_party_loaded()→bool`, `get_is_leader()→bool`; `get_hero_agent_id(hero_index)→int`, `get_agent_hero_id(agent_id)→int`.

---

## PyPathing (`pathing/pathing_bindings.cpp`)

### enum `PathStatus` — 4 values (Idle, Pending, Ready, Failed; `export_values`).

### class `PathPlanner` (default ctor = ctor/handle)
| member | kind | signature | purpose |
|---|---|---|---|
| `plan` | action | (start_x,y,z, goal_x,y,z) | submit async plan |
| `compute_immediate` | getter | (start_x,y,z, goal_x,y,z)→[(x,y,z)] | synchronous path |
| `get_status` | getter | ()→PathStatus | |
| `is_ready` | getter | ()→bool | |
| `was_successful` | getter | ()→bool | |
| `get_path` | getter | ()→[(x,y,z)] | planned path |
| `reset` | action | () | back to Idle |

---

## PyPing (`ping/ping_bindings.cpp`)

### class `PingHandler` (default ctor = ctor/handle)
`Terminate` (action); `GetCurrentPing`, `GetAveragePing`, `GetMinPing`, `GetMaxPing` (getters→int).

---

## PyPlayer (`player/player_bindings.cpp`)

### class `PyPlayer` (default ctor; snapshots on construct)
Methods: `GetContext` (getter refresh); `SendDialog(dialog_id)` (action); `ChangeTarget(target_id)→bool` (action); `InteractAgent(agent_id, call_target)→bool` (action); `CallTarget(agent_id)→bool` (action); `IsAgentIDValid(agent_id)→bool` (getter); `GetChatHistory()→[str]` (getter); `RequestChatHistory()` (action, async); `IsChatHistoryReady()→bool` (getter); `Istyping()→bool` (getter); `SendChatCommand(msg)` (action); `SendChat(channel, msg)` (action); `SendWhisper(name, msg)` (action); `SendFakeChat(channel, message)` (action); `SendFakeChatColored(channel, message, r,g,b)` (action); `GetPlayerStatus()→int` (getter); `SetPlayerStatus(status)→bool` (action).

**`def_readonly` fields (getters)**: `id`, `agent`, `target_id`, `mouse_over_id`, `observing_id`, `account_name`, `account_email`, `player_uuid`, `wins`, `losses`, `rating`, `qualifier_points`, `rank`, `tournament_reward_points`, `morale`, `party_morale`, `experience`, `level`, `current_kurzick`/`total_earned_kurzick`/`max_kurzick`, `current_luxon`/`total_earned_luxon`/`max_luxon`, `current_imperial`/`total_earned_imperial`/`max_imperial`, `current_balth`/`total_earned_balth`/`max_balth`, `current_skill_points`, `total_earned_skill_points`, `missions_completed`, `missions_bonus`, `missions_completed_hm`, `missions_bonus_hm`, `controlled_minions`, `unlocked_maps`, `learnable_character_skills`, `unlocked_character_skills`.

### enum `PlayerStatus` — 4 values (Offline, Online, DND, Away).

### Module free functions
| member | kind | signature | purpose |
|---|---|---|---|
| `set_active_title` | action | (title_id)→bool | |
| `remove_active_title` | action | ()→bool | |
| `get_active_title_id` | getter | ()→int | |
| `deposit_faction` | action | (allegiance)→bool | |
| `get_player_agent_id` | getter | (player_id)→int | |
| `get_amount_of_players_in_instance` | getter | ()→int | |
| `get_player_number` | getter | ()→int | |
| `get_player_name` | getter | (player_id=0)→str | |
| `change_second_profession` | action | (profession, hero_index=0)→bool | |
| `get_title_ids` | getter | ()→list | |

---

## PyQuest (`quest/quest_bindings.cpp`)

### class `QuestData` (default ctor, `def_readwrite`)
Fields: `quest_id`, `log_state`, `location`, `name`, `npc`, `map_from`, `marker_x`, `marker_y`, `h0024`, `map_to`, `description`, `objectives`, `is_completed`, `is_current_mission_quest`, `is_area_primary`, `is_primary`.

### class `PyQuest` (default ctor; all `def_static`)
| member | kind | signature | purpose |
|---|---|---|---|
| `set_active_quest_id` | action | (quest_id)→bool | |
| `get_active_quest_id` | getter | ()→int | |
| `abandon_quest_id` | action | (quest_id)→bool | |
| `is_quest_completed`/`is_quest_primary` | getter | (quest_id)→bool | |
| `is_mission_map_quest_available` | getter | ()→bool | |
| `get_quest_data` | getter | (quest_id)→QuestData | |
| `get_quest_log` | getter | ()→[QuestData] | |
| `get_quest_log_ids` | getter | ()→[int] | |
| `request_quest_info` | action | (quest_id, update_markers=False)→bool | |
| `request_quest_name`/`_description`/`_objectives`/`_location`/`_npc` | action | (quest_id) | async decode |
| `is_quest_name_ready`/`_description_ready`/`_objectives_ready`/`_location_ready`/`_npc_ready` | getter | (quest_id)→bool | |
| `get_quest_name`/`_description`/`_objectives`/`_location`/`_npc` | getter | (quest_id)→str | |

### Module free functions
Mirror the static class: `set_active_quest_id`, `abandon_quest_id` (actions); `get_active_quest_id`→int (getter); `request_quest_info(quest_id, update_markers=False)→bool` (action); `get_quest_entry_group_name(quest_id)→str` (getter); `is_quest_completed`/`is_quest_primary`/`is_mission_map_quest_available`/`get_quest_log_ids` (getters); the 5 async triads `request_quest_name/description/objectives/location/npc` (actions) + `is_*_ready`/`get_*` (getters).

---

## PySkill (`skillbar/skill_bindings.cpp`) — skill constant data

### class `SkillID` (ctor `()`/`(id)`/`(skillname)`)
`__eq__`/`__ne__`, `GetName`→str (getter), `id` (`def_readonly`).

### class `SkillType` (ctor `()`/`(int)`)
`__eq__`/`__ne__`, `GetName`→str, `id`.

### class `SkillProfession` (ctor `()`/`(id)`)
`ToInt`→int, `GetName`→str, `id`.

### class `Skill` (ctor `()`/`(id)`/`(skillname)`; snapshots via GetContext)
Method `GetContext` (getter refresh). ~60 `def_readonly` fields (all getters): `id` (SkillID), `campaign`, `type` (SkillType), `special`, `combo_req`, `effect1`, `condition`, `effect2`, `weapon_req`, `profession` (SkillProfession), `attribute`, `title`, `id_pvp`, `combo`, `target`, `skill_equip_type`, `overcast`, `energy_cost`, `health_cost`, `adrenaline`, `activation`, `aftercast`, `duration_0pts`, `duration_15pts`, `recharge`, `skill_arguments`, `scale_0pts`, `scale_15pts`, `bonus_scale_0pts`, `bonus_scale_15pts`, `aoe_range`, `const_effect`, `caster_overhead_animation_id`, `caster_body_animation_id`, `target_body_animation_id`, `target_overhead_animation_id`, `projectile_animation1_id`, `projectile_animation2_id`, `icon_file_id`, `icon_file2_id`, `icon_file_hi_res_id`, `name_id`, `concise`, `description_id`, `is_touch_range`, `is_elite`, `is_half_range`, `is_pvp`, `is_pve`, `is_playable`, `is_stacking`, `is_non_stacking`, `is_unused`, `adrenaline_a`, `adrenaline_b`, `recharge2`, `h0004`, `h0032`, `h0037`.

No module-level free functions or enums.

---

## PySkillbar (`skillbar/skillbar_bindings.cpp`)

### class `SkillbarSkill` (one slot; read-only)
`id` (`def_property_readonly`→ PySkill.SkillID), `adrenaline_a`, `adrenaline_b`, `recharge`, `event` (`def_readonly`), `get_recharge` (`def_property_readonly`). All getters.

### class `Skillbar` (default ctor; snapshots player skillbar)
Read-only props: `agent_id`, `disabled`, `casting`, `skills` (list[SkillbarSkill]) — getters.
| method | kind | signature | purpose |
|---|---|---|---|
| `GetContext` | getter | () | refresh snapshot |
| `GetSkill` | getter | (slot 1-8)→SkillbarSkill | |
| `LoadSkillTemplate` | action | (skill_template)→bool | |
| `LoadHeroSkillTemplate` | action | (hero_index, skill_template)→bool | |
| `UseSkill` | action | (slot, target=0)→bool | |
| `UseSkillTargetless` | action | (slot)→bool | point-blank cast |
| `HeroUseSkill` | action | (target_agent_id, skill_number, hero_idx)→bool | |
| `ChangeHeroSecondary` | action | (hero_index, profession)→bool | |
| `GetHeroSkillbar` | getter | (hero_index)→list[SkillbarSkill] | |
| `GetHoveredSkill` | getter | ()→int | hovered skill id |
| `IsSkillUnlocked`/`IsSkillLearnt` | getter | (skill_id)→bool | |

### Module free functions
Getters: `get_skill_slot(skill_id)→int`, `get_is_skill_unlocked(skill_id)→bool`, `get_is_skill_learnt(skill_id)→bool`, `get_skill_profession(skill_id)→int`, `get_skill_icon_file_id(skill_id)→int`, `get_skill_icon_file_id_hi_res(skill_id)→int`, `get_attribute_profession(attribute_id)→int`, `get_hovered_skill_id()→int`, `encode_skill_template(hero_index=0)→str`, `decode_skill_template(template)→dict`.
Actions: `use_skill(slot, target=0)→bool`, `point_blank_use_skill(slot)→bool`, `use_skill_by_id(skill_id, target=0)→bool`, `change_second_profession(profession, hero_index=0)→bool`, `load_skill_template(template, hero_index=0)→bool`, `load_skillbar(skill_ids, hero_index=0)→bool`, `set_attributes(attribute_ids, attribute_values, hero_index=0)→bool`, `hero_use_skill(target_agent_id, skill_number, hero_index)→bool`.

---

## PyTrade (`trade/trade_bindings.cpp`)
All module-level functions.

| member | kind | signature | purpose |
|---|---|---|---|
| `open_trade_window` | action | (agent_id)→bool | |
| `accept_trade` | action | ()→bool | |
| `cancel_trade` | action | ()→bool | |
| `change_offer` | action | ()→bool | |
| `submit_offer` | action | (gold)→bool | |
| `remove_item` | action | (slot)→bool | |
| `offer_item` | action | (item_id, quantity=0)→bool | |
| `is_item_offered` | getter | (item_id)→bool | |

---

## PyUIManager (`ui/ui_bindings.cpp`) — very large surface (~130 static methods)

### Low-level wrapper classes
- `UIInteractionCallback` (`def_readwrite`): `callback_address`, `uictl_context`, `h0008`; method `get_address`.
- `FramePosition` (default ctor, `def_readwrite`): `top`, `left`, `bottom`, `right`, `content_top/left/bottom/right`, `unknown`, `scale_factor`, `viewport_width`, `viewport_height`, `screen_top/left/bottom/right`, `top_on_screen`, `left_on_screen`, `bottom_on_screen`, `right_on_screen`, `width_on_screen`, `height_on_screen`, `viewport_scale_x`, `viewport_scale_y`.
- `FrameRelation` (default ctor, `def_readwrite`): `parent_id`, `field67_0x124`, `field68_0x128`, `frame_hash_id`, `siblings`.
- `UIFrame` (ctor `(int frame_id)`): a full 1:1 native-frame snapshot; readable/writable named fields `frame_id`, `parent_id`, `frame_hash`, `visibility_flags`, `type`, `template_type`, `position` (FramePosition), `relation` (FrameRelation), `is_created`, `is_visible`, `frame_layout`, `frame_callbacks` ([UIInteractionCallback]), `child_offset_id`, `frame_state`, plus ~90 raw `fieldNN_0xNN` offset fields; method `get_context` (getter refresh).

### class `UIManager` (shim; all `def_static`)

**Global state / language** (getters): `get_text_language()→int`, `is_world_map_showing()→bool`, `is_ui_drawn()→bool`, `is_shift_screenshot()→bool`.

**Built-in windows** (WindowID): `is_window_visible(window_id)→bool` (getter), `get_window_position(window_id)→tuple|None` (getter), `set_window_visible(window_id, is_visible)` (action — bound twice), `set_open_links(toggle)` (action), `get_frame_limit()→int` (getter), `set_frame_limit(value)` (action).

**Frame tree traversal / discovery** (getters unless noted): `get_root_frame_id()`, `get_frame_array()`, `get_frame_id_by_label(label)`, `get_frame_id_by_hash(hash)`, `get_hash_by_label(label)`, `get_child_frame_by_frame_id(parent_frame_id, child_offset)`, `get_child_frame_path_by_frame_id(parent_frame_id, child_offsets)`, `get_child_frame_id(parent_hash, child_offsets)`, `get_child_frame_id_from_name_hash(parent_frame_id, name_hash)`, `get_parent_frame_id(frame_id)`, `get_parent_frame_id_direct(frame_id)`, `get_related_frame_id(frame_id, relation_kind, start_after=0)`, `get_first_child_frame_id(parent_frame_id)`, `get_last_child_frame_id(parent_frame_id)`, `get_next_child_frame_id(frame_id)`, `get_prev_child_frame_id(frame_id)`, `get_item_frame_id(parent_frame_id, index)`, `get_overlay_frame_ids()`, `get_popup_frame_ids()`, `get_frame_hierarchy()`, `get_frame_coords_by_hash(frame_hash)`, `is_ancestor_of_by_frame_id(frame_id, ancestor_id)→bool`, `frame_exists_by_frame_id(frame_id)→bool`, `get_frame_snapshot(frame_id)→dict` (replaces legacy UIFrame class).

**Frame metadata / geometry** (getters): `get_frame_context(frame_id)→int`, `get_frame_layer_by_frame_id(frame_id)`, `set_frame_layer_by_frame_id(frame_id, layer)` (action), `get_frame_code_by_frame_id(frame_id)`, `get_frame_min_size_by_frame_id(frame_id)→tuple`, `get_frame_client_border_by_frame_id(frame_id)→tuple`, `get_frame_clip_rect_by_frame_id(frame_id)→tuple`, `get_frame_position_ex_by_frame_id(frame_id)→tuple`, `get_frame_native_size_by_frame_id(frame_id)→tuple`, `get_frame_title_by_frame_id(frame_id)→str`, `get_frame_label_by_frame_id(frame_id)→str`, `get_frame_user_param_by_frame_id(frame_id)`, `get_frame_state_bit_by_frame_id(frame_id, bit)`, `get_frame_opacity_by_frame_id(frame_id)`.

**Frame state setters** (actions, queued): `set_frame_visible_by_frame_id(frame_id, is_visible)`, `set_frame_disabled_by_frame_id(frame_id, is_disabled)`, `set_frame_opacity_by_frame_id(frame_id, opacity, fade_time=0)`, `show_frame_by_frame_id(frame_id, show)`, `trigger_frame_redraw_by_frame_id(frame_id)`, `add_frame_ui_interaction_callback_by_frame_id(frame_id, callback_address, wparam=0)`, `destroy_ui_component_by_frame_id(frame_id)`.

**Preferences**: getters `get_preference_options(pref)→[int]`, `get_enum_preference(pref)`, `get_int_preference(pref)`, `get_bool_preference(pref)`, `get_string_preference(pref)→str`; actions `set_enum_preference(pref, value)`, `set_int_preference(pref, value)`, `set_bool_preference(pref, value)`, `set_string_preference(pref, value)`.

**UI messages / input** (actions): `SendUIMessage(msgid, values, skip_hooks=False)→bool`, `SendUIMessageRaw(msgid, wparam, lparam=0, skip_hooks=False)→bool`, `SendFrameUIMessage(frame_id, message_id, wparam, lparam=0)`, `SendFrameUIMessageWString(frame_id, message_id, text)`, `button_click(frame_id)`, `button_double_click(frame_id)`, `test_mouse_action(frame_id, current_state, wparam=0, lparam=0)`, `test_mouse_click_action(frame_id, current_state, wparam=0, lparam=0)`, `key_down(key, frame_id=0)`, `key_up(key, frame_id=0)`, `key_press(key, frame_id=0)`.

**Enc-string helpers** (getters): `is_valid_enc_str(enc_str)→bool`, `uint32_to_enc_str(value)→str`, `enc_str_to_uint32(enc_str)→int`.

**Widget creation (native component factories)** (actions, return new frame_id): `create_ui_component_by_frame_id`, `create_ui_component_raw_by_frame_id`, `create_button_frame_by_frame_id`, `create_ctl_button_frame_by_frame_id`, `create_text_button_frame_by_frame_id`, `create_flat_button_with_click_by_frame_id`, `create_checkbox_frame_by_frame_id`, `create_scrollable_frame_by_frame_id`, `create_text_label_frame_by_frame_id`, `create_dropdown_frame_by_frame_id`, `create_slider_frame_by_frame_id`, `create_editable_text_frame_by_frame_id`, `create_progress_bar_by_frame_id`, `create_tabs_frame_by_frame_id`.

**Typed widget families** (by frame_id):
- Button: `get_button_label_by_frame_id`→str (getter), `set_button_label_by_frame_id(label)` (action), `button_mouse_action_by_frame_id(action_state)` (action).
- Checkbox: `is_checkbox_checked_by_frame_id`→bool (getter), `set_checkbox_checked_by_frame_id(checked)` (action), `get_checkbox_value_by_frame_id`→int (getter), `set_checkbox_value_by_frame_id(value)` (action).
- Dropdown: getters `get_dropdown_options_by_frame_id`, `get_dropdown_count_by_frame_id`, `get_dropdown_option_value_by_frame_id(index)`, `get_dropdown_option_index_by_frame_id(value)`, `get_dropdown_selected_index_by_frame_id`, `dropdown_has_value_mapping_by_frame_id`, `get_dropdown_value_by_frame_id`; actions `select_dropdown_option_by_frame_id(value)`, `select_dropdown_index_by_frame_id(index)`, `add_dropdown_option_by_frame_id(label_enc, value)`, `set_dropdown_value_by_frame_id(value)`.
- Slider: `get_slider_value_by_frame_id`→int (getter), `set_slider_value_by_frame_id(value)` (action).
- Editable text: `get_editable_text_value_by_frame_id`→str (getter), `set_editable_text_value_by_frame_id(value)` (action), `set_editable_text_max_length_by_frame_id(max_length)` (action), `is_editable_text_read_only_by_frame_id`→bool (getter), `set_editable_text_read_only_by_frame_id(read_only)` (action), `set_read_only_by_frame_id(is_read_only)` (action), `is_read_only_by_frame_id`→bool (getter).
- Progress bar: `get_progress_bar_value_by_frame_id`→int (getter), `set_progress_bar_value_by_frame_id(value)` / `set_progress_bar_max_by_frame_id(value)` / `set_progress_bar_color_id_by_frame_id(color_id)` / `set_progress_bar_style_by_frame_id(style)` (actions).
- Text labels: `get_text_label_encoded_by_frame_id`→str, `get_text_label_decoded_by_frame_id`→str (getters); `set_text_label_by_frame_id(label)`, `set_label_by_frame_id(label)`, `set_multiline_label_by_frame_id(label)`, `set_text_label_font_by_frame_id(font_id)` (actions).
- Tabs: actions `add_tab_by_frame_id(...)`, `disable_tab_by_frame_id(tab_id)`, `enable_tab_by_frame_id(tab_id)`, `remove_tab_by_frame_id(tab_id)`, `choose_tab_by_tab_frame_id(tab_frame_id)`, `choose_tab_by_index_by_frame_id(tab_index)`; getters `get_current_tab_index_by_frame_id`, `get_tab_frame_id_by_frame_id(tab_id)`, `get_tab_frame_id(index)`, `get_is_tab_enabled_by_frame_id(tab_id)`, `get_tab_by_label_by_frame_id(label)`, `get_current_tab_by_frame_id`, `get_tab_button_by_frame_id(tab_frame_id)`.
- Scrollable: actions `clear_scrollable_items_by_frame_id`, `remove_scrollable_item_by_frame_id(child_offset_id)`, `add_scrollable_item_by_frame_id(flags, child_offset_id, callback_address=0)`; getters `get_scrollable_item_frame_id_by_frame_id(child_offset_id)`, `get_scrollable_selected_value_by_frame_id`, `get_scrollable_first_child_frame_id_by_frame_id`, `get_scrollable_next_child_frame_id_by_frame_id(child_frame_id)`, `get_scrollable_last_child_frame_id_by_frame_id`, `get_scrollable_prev_child_frame_id_by_frame_id(child_frame_id)`, `get_scrollable_item_rect_by_frame_id(child_offset_id)→tuple`, `get_scrollable_count_by_frame_id`, `get_scrollable_items_by_frame_id`→[int], `get_scrollable_page_by_frame_id`.

---

## Notes for the demo builder
- **Data getters vs actions**: getters can be shown live each frame; action rows should render as buttons (many actions are `game_thread::Enqueue`-queued and safe to call, but they mutate/send — gate them behind a click).
- **Async getters** (Item `RequestName`/`IsItemNameReady`/`GetName`; Player chat history; all Quest `request_*`/`is_*_ready`/`get_*`): the demo must call the `request_*` action, poll the `is_*_ready` getter, then read the value.
- **Getters returning complex structs to trace**: `PyDialog` (6 struct types), `PyEffects` (EffectType/BuffType), `PyItem` (ItemModifier/ItemTypeClass/DyeInfo/DyeColorClass), `PyParty` (PlayerPartyMember/HeroPartyMember/HenchmanPartyMember/PetInfo), `PyQuest` (QuestData), `PySkillbar` (SkillbarSkill), `PySkill` (SkillID/SkillType/SkillProfession), `PyUIManager` (UIFrame/FramePosition/FrameRelation, plus `get_frame_snapshot`→dict), `PyInventory.get_bag`→dict, `PyNameObfuscator` (ObservedPlayer + diagnostics dict), `PyPacketSniffer` (PacketLogEntry).
