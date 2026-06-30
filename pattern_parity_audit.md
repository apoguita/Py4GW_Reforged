# Pattern Parity Audit

Baseline for parity checks:

- Legacy project: `C:\Users\Apo\Py4GW`
- Legacy resolver sources: `vendor/gwca/Source/*Mgr.cpp`

## Checked Modules

## Assert Inventory Cross-Check Progress

This section is narrower than the resolver audit above. It checks whether the
legacy module-level `Logger::AssertAddress(...)` inventories have matching
current runtime/exported pointer surfaces, not just matching JSON resolver
definitions.

### `ui`

Status:

- Legacy asserted pointer inventory is now accounted for in current `ui` runtime surface.
- The previously missing `AsyncDecodeStringPtr` and `GetCommandLineNumber_Func`
  surfaces have been restored.

Notes:

- This pass is about pointer/address surface parity. It does not yet claim full
  hook-wiring parity for every legacy optional hook site.

### `chat`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `PrintChatMessage_Func`
  - `UICallback_ChatLogLine_Func`
  - `GetSenderColor_Func`
  - `GetMessageColor_Func`
  - `SendChat_Func`
  - `StartWhisper_Func`
  - `RecvWhisper_Func`
  - `AddToChatLog_Func`
  - `ChatBuffer_Addr`
  - `IsTyping_FrameId`
  - `UICallback_AssignEditableText_Func`

No missing current runtime/exported pointer surfaces were found in this pass.

### `item`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `SalvageStart_Func`
  - `IdentifyItem_Func`
  - `OnSalvagePopup_UICallback_Func`
  - `item_formulas`
  - `storage_open_addr`
  - `ItemClick_Func`
  - `EquipItem_Func`
  - `UseItem_Func`
  - `MoveItem_Func`
  - `DropGold_Func`
  - `DropItem_Func`
  - `ChangeEquipmentVisibility_Func`
  - `ChangeGold_Func`
  - `OpenLockedChest_Func`
  - `PingWeaponSet_Func`
  - `SalvageSessionCancel_Func`
  - `SalvageSessionComplete_Func`
  - `SalvageMaterials_Func`
  - `unlocked_pvp_item_upgrade_array.m_buffer`
  - `unlocked_pvp_item_upgrade_array.m_size`
  - `GetPvPItemUpgradeInfoName_Func`
  - `DestroyItem_Func`

No missing current runtime/exported pointer surfaces were found in this pass.

### `party`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `TickButtonUICallback`
  - `SetDifficulty_Func`
  - `PartySearchSeek_Func`
  - `PartySearchButtonCallback_Func`
  - `PartyWindowButtonCallback_Func`
  - `PartyPlayerMember_UICallback`
  - `SetReadyStatus_Func`
  - `FlagHeroAgent_Func`
  - `FlagAll_Func`
  - `SetHeroBehavior_Func`
  - `LockPetTarget_Func`
  - `CommandHotKeyDisableAi_Func`

Notes:

- Legacy also logs transient local scan anchors:
  - `FlagAgent address`
  - `PetTarget address`
  - `CommandHotKeyDisableAi address`
- These are intermediate local scan results in legacy `PartyMgr.cpp`, not
  exported/persisted module pointers. Current code preserves the recovered final
  function pointers, which is the meaningful runtime surface.

### `agent`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `AgentArrayPtr`
  - `PlayerAgentIdPtr`
  - `MoveTo_Func`
  - `ChangeTarget_Func`
  - `SendAgentDialog_Func`
  - `SendGadgetDialog_Func`
  - `CallTarget_Func`

### `camera`

Status:

- Legacy asserted runtime surfaces are present in current code:
  - `scan_cam_class`
  - `patch_fog.GetAddress()`
  - `patch_cam_update.GetAddress()`

Notes:

- Current camera module stores the camera pointer as `g_camera`.
- Current camera patch surfaces are preserved as `g_patch_fog` and `g_patch_cam_update`
  rather than exposing raw patch addresses separately.

### `effects`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `PostProcessEffect_Func`
  - `DropBuff_Func`

### `events`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `SendEventMessage_Func`

### `friend_list`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `FriendList_Addr`
  - `FriendEventHandler_Func`
  - `SetOnlineStatus_Func`
  - `AddFriend_Func`
  - `RemoveFriend_Func`

### `game_thread`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `LeaveGameThread_Func`

### `context`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `base_ptr`
  - `GameplayContext_addr`
  - `PreGameContext_addr`

### `map`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `MissionMap_UICallback_Func`
  - `WorldMap_UICallback_Func`
  - `map_type_instance_infos`
  - `region_id_addr`
  - `area_info_addr`
  - `InstanceInfoPtr`
  - `QueryAltitude_Func`
  - `EnterChallengeMission_Func`
  - `CancelEnterChallengeMission_Func`

Notes:

- Current code keeps the two UI callback function pointers as internal module
  statics rather than public globals, but they remain concrete runtime pointer
  surfaces and are still hooked/enabled/disabled/removed in parity with legacy.

### `merchant`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `TransactItem_Func`
  - `RequestQuote_Func`

### `player`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `RemoveActiveTitle_Func`
  - `SetActiveTitle_Func`
  - `DepositFaction_Func`
  - `title_data`

### `quest`

Status:

- Legacy asserted final pointers are present in current runtime surface:
  - `AbandonQuest_Func`
  - `SetActiveQuest_Func`
  - `RequestQuestData_Func`
  - `RequestQuestInfo_Func`

### `render`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\RenderMgr.cpp`

Status:

- `window_handle_ptr`: parity
- `end_scene_target`: parity
- `get_transform_target`: parity
- `screen_capture_target`: parity
- `reset_target`: drift found and fixed

Drift found:

- Legacy resolves reset with `Scanner::ToFunctionStart(Scanner::Find(...), 0xFFF)`.
- Refactor had moved `0xFFF` into the pattern scan offset in `offsets/render.json`, which changed the anchor before function-start recovery.
- Fixed by restoring `"offset": "0x0"` for `render.reset_target`.

### `agent`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\AgentMgr.cpp`

Status:

- `change_target_anchor`: parity
- `agent_array_ref`: parity
- `player_agent_id_ref`: parity
- `send_dialog_callsite`: parity
- `move_to_callsite`: parity
- `do_world_action_anchor`: parity
- `call_target_sender`: parity

No mismatches found in the current JSON resolver semantics for the checked agent patterns.

### `ui`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\UIMgr.cpp`

Confirmed parity:

- `frame_array_anchor`
- `world_map_state`
- `send_frame_ui_message_by_id`
- `create_hash_from_wchar`
- `get_child_frame_id_anchor`
- `find_related_frame`
- `get_root_frame`
- `send_ui_message`
- `load_settings`
- `ui_drawn_anchor`
- `shift_screenshot`
- `set_tooltip`
- `game_settings_addr`
- `set_window_visible`
- `validate_async_decode`
- `draw_on_compass`
- `create_ui_component`
- `frame_new_subclass_assertion`
- `frame_new_subclass_fallback`
- `preferences_initialized`
- `enum_preference_info`
- `number_preference_info`
- `set_string_preference`
- `preference_quality_anchor`
- `set_in_game_shadow_quality`
- `set_in_game_ui_scale`
- `set_volume`
- `set_master_volume`
- `get_graphics_renderer_value`
- `set_graphics_renderer_value`
- `set_game_renderer_mode`
- `game_renderer_metrics`
- `command_line_number`
- `build_login_struct_callsite`

Drift found:

- `destroy_ui_component.assertion_file`
  - Legacy: `\\Code\\Gw\\Ui\\Frame\\FrApi.cpp`
  - Refactor had: `\\Code\\Engine\\Frame\\FrApi.cpp`
  - Fixed to the legacy path.

Additional fixes applied after initial audit:

- `get_command_line_number_func`
  - Legacy resolves `GetCommandLineNumber_Func` from the `command_line_number` assertion and uses the same recovered function body that exposes `CommandLineNumber_Buffer`.
  - Refactor previously exposed `g_get_command_line_number_func` in code but never resolved it.
  - Fixed by adding `ui.get_command_line_number_func` and wiring it through `ResolveCommandLineFunctions()`.
- Title helper fallback behavior
  - Legacy falls back to hardcoded addresses for `GetTitle_Func`, `TitleBinarySearch_Func`, and `TitleTable_Addr` when dynamic extraction fails.
  - Fixed by restoring that fallback behavior in `src/GW/ui/ui_patterns.cpp`.
- UI shutdown cleanup
  - `ui::Exit()` now also clears `g_get_command_line_flag_func`, `g_get_command_line_string_func`, and `g_get_command_line_number_func` so command-line helper state is torn down consistently.
- `async_decode_string_func`
  - Legacy resolves `AsyncDecodeStringPtr` from `"\x57\x83\x7e\x30\x00\x74\x14\x68\xc9"` and carries it as a native pointer surface.
  - Refactor previously resolved only `validate_async_decode_str_func`.
  - Fixed by adding `ui.async_decode_string_func` and restoring the corresponding exported runtime pointer in `ui`.

### `memory`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\MemoryMgr.cpp`

Status:

- `skill_timer_anchor`: parity
- `window_handle_ptr`: parity
- `personal_dir_target`: parity
- `gw_version_anchor`: parity
- `mem_alloc_helper`: parity
- `mem_realloc_helper`: parity
- `mem_free_anchor`: parity

No mismatches found in the checked memory patterns and resolver steps.

### `map`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\MapMgr.cpp`

Status:

- `skip_cinematic`: parity
- `region_id_ref`: parity
- `area_info_ref`: parity
- `instance_info_ref`: parity
- `query_altitude_callsite`: parity
- `bypass_tolerance_patch`: parity
- `enter_challenge_anchor`: parity
- `map_type_instance_infos_ref`: parity
- `world_map_ui_callback`: parity
- `mission_map_ui_callback`: parity

No mismatches found in the checked map patterns and resolver steps.

### `skillbar`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\SkillbarMgr.cpp`

Status:

- `skill_array_ref`: parity
- `attribute_array_ref`: parity
- `use_skill_func_callsite`: parity
- `templates_helpers_assertion`: parity

No mismatches found in the checked skillbar patterns and resolver steps.

### `chat`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\ChatMgr.cpp`

Status:

- `get_sender_color_func`: parity
- `get_message_color_func`: parity
- `send_chat_func`: parity
- `start_whisper_func`: parity
- `add_to_chat_log_func`: parity
- `chat_buffer_addr`: parity
- `recv_whisper_func`: parity
- `print_chat_message_anchor`: parity
- `is_typing_assertion`: parity
- `is_typing_frame_id_sub`: parity
- `uicallback_assign_editable_text`: parity
- `uicallback_chat_log_assertion`: parity
- `chat_timestamps_patch`: parity

No mismatches found in the checked chat patterns and resolver steps.

### `friend_list`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\FriendListMgr.cpp`

Status:

- `friend_list_anchor`: parity
- `friend_list_scan`: parity
- `friend_event_handler`: parity
- `set_online_status`: parity
- `add_friend`: parity
- `remove_friend_anchor`: parity
- `remove_friend_call`: parity

No mismatches found in the checked friend list patterns and resolver steps.

### `item`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\ItemMgr.cpp`

Status:

- `storage_open_ptr`: parity
- `item_click_func`: parity
- `use_item_func`: parity
- `equip_item_assertion`: parity
- `move_item_assertion`: parity
- `drop_item_func`: parity
- `salvage_popup_assertion`: parity
- `drop_gold_salvage_assertion`: parity
- `salvage_start_assertion`: parity
- `identify_item_assertion`: parity
- `destroy_item_func`: parity
- `change_equipment_visibility_func`: parity
- `change_gold_func`: parity
- `open_locked_chest_func`: parity
- `ping_weapon_set_assertion`: parity
- `pvp_item_upgrade_array_assertion`: parity
- `pvp_item_array_assertion`: parity
- `composite_model_info_array_assertion`: parity
- `pvp_item_upgrade_name_func`: parity
- `item_formulas_assertion`: parity

Notes:

- Legacy uses backward `FindInRange` scans from the `drop_gold_salvage_assertion` anchor to recover salvage callsites.
- Current resolver engine preserves reverse-range scan behavior because `Scanner::FindInRange()` and `ToFunctionStart()` still operate with `start > end` in the same way as legacy `GWCA`.

No mismatches found in the checked item patterns and resolver steps.

### `party`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\PartyMgr.cpp`

Status:

- `set_difficulty_callsite`: parity
- `party_search_seek_func_ref`: parity
- `party_search_button_callback_assertion`: parity
- `party_window_button_callback_ref`: parity
- `party_player_member_ui_callback_assertion`: parity
- `set_ready_status_assertion`: parity
- `flag_hero_agent_func_ref`: parity
- `flag_all_inner_call_ref`: parity
- `flag_all_func_inner_call_ref`: parity
- `set_hero_behavior_callsite`: parity
- `command_hotkey_disable_ai_ref`: parity

Additional confirmation:

- `tick_button_ui_callback_ref`: parity

Notes:

- Legacy resolves `TickButtonUICallback` with `Scanner::Find("\\x05\\xfb\\x0b\\x01\\x00", "xxxxx")` and `ToFunctionStart(..., 0xFFF)`.
- Current resolver matches that contract.

### `player`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\PlayerMgr.cpp`

Status:

- `set_active_title_anchor`: parity
- `set_active_title_call`: parity
- `remove_active_title_signature`: parity
- `deposit_faction_callsite`: parity
- `title_data_ref`: parity

No mismatches found in the checked player patterns and resolver steps.

### `quest`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\QuestMgr.cpp`

Status:

- `request_anchor`: parity
- `request_data_call`: parity
- `abandon_quest_ref`: parity
- `set_active_quest_sig`: parity

No mismatches found in the checked quest patterns and resolver steps.

### `camera`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\CameraMgr.cpp`

Status:

- `camera_ptr_anchor`: parity
- `camera_ptr_scan`: parity
- `fog_patch`: parity
- `camera_update_patch_vs2017`: parity
- `camera_update_patch_vs2022`: parity

No mismatches found in the checked camera patterns and resolver steps.

### `merchant`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\MerchantMgr.cpp`

Drift found:

- Legacy uses the scanned address directly for:
  - `TransactItem_Func = Scanner::Find(..., -0x7F)`
  - `RequestQuote_func = Scanner::Find(..., -0x35)`
- Refactor had wrapped both in `ToFunctionStart()`.
- Fixed by changing both resolvers to return the scanned address directly with `validate_section(text)`.

Status after fix:

- `transact_item_target`: parity
- `request_quote_target`: parity

### `events`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\EventMgr.cpp`

Status:

- `send_event_message_callsite`: parity

No mismatches found in the checked events patterns and resolver steps.

### `effects`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\EffectMgr.cpp`

Status:

- `post_process_target`: parity
- `drop_buff_callsite`: parity

No mismatches found in the checked effects patterns and resolver steps.

### `stoc`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\StoCMgr.cpp`

Status:

- `handler_table_pointer`: parity

Notes:

- Legacy consumes the resolved handler-table pointer to derive `game_server_handlers` from nested structures at runtime.
- Current resolver parity covers the pointer source itself, which is the pattern-resolved contract.
- The raw legacy pointer surface is now preserved explicitly as `g_handler_table_addr`, in addition to the derived `g_game_server_handlers`.

### `game_thread`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\GameThreadMgr.cpp`

Status:

- `leave_game_thread_target`: parity

No mismatches found in the checked game thread patterns and resolver steps.

### `context`

Legacy source:

- `C:\Users\Apo\Py4GW\vendor\gwca\Source\GWCA.cpp`

Status:

- `base_ptr_ref`: parity
- `gameplay_context_ref`: parity
- `pregame_context_ref`: parity

No mismatches found in the checked context patterns and resolver steps.

## Next Modules To Audit

- No additional confirmed parity gaps remain from the current resolver audit plus the legacy `Logger::AssertAddress(...)` inventory cross-check.
- Any future work should be driven by new runtime evidence rather than by an unproven assumption that an asserted legacy pointer surface is still missing.
