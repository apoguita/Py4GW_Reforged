#include "base/error_handling.h"

#include "GW/context/account.h"
#include "GW/context/agent.h"
#include "GW/context/character.h"
#include "GW/context/camera.h"
#include "GW/context/chat.h"
#include "GW/context/context.h"
#include "GW/context/friend_list.h"
#include "GW/context/game.h"
#include "GW/context/gameplay.h"
#include "GW/context/guild.h"
#include "GW/context/item.h"
#include "GW/context/item.h"
#include "GW/context/map.h"
#include "GW/context/party.h"
#include "GW/context/pregame.h"
#include "GW/context/render.h"
#include "GW/context/text_parser.h"
#include "GW/context/trade.h"
#include "GW/context/ui.h"
#include "GW/context/world.h"

namespace GW::Context {

extern uintptr_t g_base_ptr;
extern uintptr_t g_pregame_context_addr;
extern uintptr_t g_gameplay_context_addr;
extern uintptr_t g_friend_list_addr;
extern uintptr_t g_agent_array_addr;
extern uintptr_t g_player_agent_id_addr;
extern GW::Constants::ServerRegion* g_region_id_addr;
extern AreaInfo* g_area_info_addr;
extern MapTypeInstanceInfo* g_map_type_instance_infos;
extern uint32_t g_map_type_instance_infos_size;
extern uintptr_t g_instance_info_ptr;
extern InstanceInfo* g_instance_info;
extern Skill* g_skill_array_addr;
extern AttributeInfo* g_attribute_array_addr;
extern uintptr_t g_world_map_state_addr;
extern uintptr_t g_preferences_initialized_addr;
extern uintptr_t g_title_table_addr;
extern TitleClientData* g_title_data_addr;
extern uintptr_t g_ui_drawn_addr;
extern uintptr_t g_shift_screen_addr;
extern uintptr_t g_game_settings_addr;
extern EnumPreferenceInfo* g_enum_preference_options_addr;
extern NumberPreferenceInfo* g_number_preference_options_addr;
extern GW::GWArray<ui::Frame*>* g_frame_array;
extern ui::TooltipInfo*** g_current_tooltip_ptr;
extern WindowPosition* g_window_positions_array;
extern MissionMapContext* g_mission_map_context;
extern WorldMapContext* g_world_map_context;
extern SalvageSessionInfo* g_salvage_context;
extern uint32_t* g_storage_open_addr;
extern GW::GWArray<PvPItemUpgradeInfo> g_unlocked_pvp_item_upgrade_array;
extern GW::GWArray<PvPItemInfo> g_pvp_item_array;
extern GW::GWArray<CompositeModelInfo>* g_composite_model_info_array;
extern ItemFormula* g_item_formulas;
extern uint32_t g_item_formula_count;
extern ChatBuffer** g_chat_buffer_addr;
extern uint32_t* g_is_typing_frame_id;
extern GwDxContext* g_dx_context;
extern uintptr_t g_window_handle_ptr;
extern Camera* g_camera;

}  // namespace GW::Context

namespace GW::Context {

GameContext* GetGameContext() {
    auto** base_context = g_base_ptr ? *reinterpret_cast<uintptr_t***>(g_base_ptr) : nullptr;
    return base_context ? reinterpret_cast<GameContext*>(base_context[0x6]) : nullptr;
}

PreGameContext* GetPreGameContext() {
    return g_pregame_context_addr ? *reinterpret_cast<PreGameContext**>(g_pregame_context_addr) : nullptr;
}

WorldContext* GetWorldContext() {
    GameContext* game_context = GetGameContext();
    return game_context ? game_context->world : nullptr;
}

PartyContext* GetPartyContext() {
    GameContext* game_context = GetGameContext();
    return game_context ? game_context->party : nullptr;
}

CharContext* GetCharContext() {
    GameContext* game_context = GetGameContext();
    return game_context ? game_context->character : nullptr;
}

GuildContext* GetGuildContext() {
    GameContext* game_context = GetGameContext();
    return game_context ? game_context->guild : nullptr;
}

ItemContext* GetItemContext() {
    GameContext* game_context = GetGameContext();
    return game_context ? game_context->items : nullptr;
}

AgentContext* GetAgentContext() {
    GameContext* game_context = GetGameContext();
    return game_context ? game_context->agent : nullptr;
}

AgentArray* GetAgentArray() {
    auto* agents = reinterpret_cast<AgentArray*>(g_agent_array_addr);
    return agents && agents->valid() ? agents : nullptr;
}

uint32_t GetObservingId() {
    return g_player_agent_id_addr ? *reinterpret_cast<uint32_t*>(g_player_agent_id_addr) : 0;
}

MapContext* GetMapContext() {
    GameContext* game_context = GetGameContext();
    return game_context ? game_context->map : nullptr;
}

GW::Constants::ServerRegion* GetRegionIdPtr() {
    return g_region_id_addr;
}

AreaInfo* GetAreaInfoArray() {
    return g_area_info_addr;
}

MapTypeInstanceInfo* GetMapTypeInstanceInfos() {
    return g_map_type_instance_infos;
}

uint32_t GetMapTypeInstanceInfosSize() {
    return g_map_type_instance_infos_size;
}

uintptr_t GetInstanceInfoPtr() {
    return g_instance_info_ptr;
}

InstanceInfo* GetInstanceInfo() {
    return g_instance_info;
}

Skill* GetSkillArray() {
    return g_skill_array_addr;
}

AttributeInfo* GetAttributeInfoArray() {
    return g_attribute_array_addr;
}

uintptr_t GetWorldMapStateAddress() {
    return g_world_map_state_addr;
}

uintptr_t GetPreferencesInitializedAddress() {
    return g_preferences_initialized_addr;
}

uintptr_t GetTitleTableAddress() {
    return g_title_table_addr;
}

uintptr_t GetUIDrawnAddress() {
    return g_ui_drawn_addr;
}

uintptr_t GetShiftScreenAddress() {
    return g_shift_screen_addr;
}

uintptr_t GetGameSettingsAddress() {
    return g_game_settings_addr;
}

EnumPreferenceInfo* GetEnumPreferenceOptions() {
    return g_enum_preference_options_addr;
}

NumberPreferenceInfo* GetNumberPreferenceOptions() {
    return g_number_preference_options_addr;
}

GW::GWArray<ui::Frame*>* GetFrameArray() {
    return g_frame_array && g_frame_array->valid() ? g_frame_array : nullptr;
}

ui::TooltipInfo*** GetCurrentTooltipPtr() {
    return g_current_tooltip_ptr;
}

WindowPosition* GetWindowPositionsArray() {
    return g_window_positions_array;
}

AccountContext* GetAccountContext() {
    GameContext* game_context = GetGameContext();
    return game_context ? game_context->account : nullptr;
}

TradeContext* GetTradeContext() {
    GameContext* game_context = GetGameContext();
    return game_context ? game_context->trade : nullptr;
}

GameplayContext* GetGameplayContext() {
    return g_gameplay_context_addr ? *reinterpret_cast<GameplayContext**>(g_gameplay_context_addr) : nullptr;
}

TextParser* GetTextParser() {
    GameContext* game_context = GetGameContext();
    return game_context ? game_context->text_parser : nullptr;
}

MerchItemArray* GetMerchantItemsArray() {
    auto* world = GetWorldContext();
    return world && world->merch_items.valid() ? &world->merch_items : nullptr;
}

MapAgentArray* GetMapAgentArray() {
    auto* world = GetWorldContext();
    return world ? &world->map_agents : nullptr;
}

AgentEffectsArray* GetPartyEffectsArray() {
    auto* world = GetWorldContext();
    return world && world->party_effects.valid() ? &world->party_effects : nullptr;
}

SkillbarArray* GetSkillbarArray() {
    auto* world = GetWorldContext();
    return world && world->skillbar.valid() ? &world->skillbar : nullptr;
}

MissionMapIconArray* GetMissionMapIconArray() {
    auto* world = GetWorldContext();
    return world && world->mission_map_icons.valid() ? &world->mission_map_icons : nullptr;
}

NPCArray* GetNPCArray() {
    auto* world = GetWorldContext();
    return world && world->npcs.valid() ? &world->npcs : nullptr;
}

PlayerArray* GetPlayerArray() {
    auto* world = GetWorldContext();
    return world && world->players.valid() ? &world->players : nullptr;
}

TitleArray* GetTitleArray() {
    auto* world = GetWorldContext();
    return world && world->titles.valid() ? &world->titles : nullptr;
}

TitleClientData* GetTitleClientData() {
    return g_title_data_addr;
}

GuildArray* GetGuildArray() {
    auto* guild = GetGuildContext();
    return guild && guild->guilds.valid() ? &guild->guilds : nullptr;
}

ItemArray* GetItemArray() {
    auto* item_context = GetItemContext();
    return item_context && item_context->item_array.valid() ? &item_context->item_array : nullptr;
}

Inventory* GetInventory() {
    auto* item_context = GetItemContext();
    return item_context ? item_context->inventory : nullptr;
}

Bag** GetBagArray() {
    auto* inventory = GetInventory();
    return inventory ? inventory->bags : nullptr;
}

uint32_t* GetStorageOpenAddress() {
    return g_storage_open_addr;
}

GW::GWArray<PvPItemUpgradeInfo>* GetPvPItemUpgradeArray() {
    return g_unlocked_pvp_item_upgrade_array.valid() ? &g_unlocked_pvp_item_upgrade_array : nullptr;
}

GW::GWArray<PvPItemInfo>* GetPvPItemInfoArray() {
    return g_pvp_item_array.valid() ? &g_pvp_item_array : nullptr;
}

GW::GWArray<CompositeModelInfo>* GetCompositeModelInfoArrayPtr() {
    return g_composite_model_info_array;
}

ItemFormula* GetItemFormulas() {
    return g_item_formulas;
}

uint32_t GetItemFormulaCount() {
    return g_item_formula_count;
}

ChatBuffer** GetChatBufferAddress() {
    return g_chat_buffer_addr;
}

uint32_t* GetIsTypingFrameIdAddress() {
    return g_is_typing_frame_id;
}

GwDxContext* GetRenderContext() {
    return g_dx_context;
}

uintptr_t GetWindowHandlePtrAddress() {
    return g_window_handle_ptr;
}

GW::Constants::QuestID GetActiveQuestId() {
    auto* world = GetWorldContext();
    return world ? world->active_quest_id : static_cast<GW::Constants::QuestID>(0);
}

QuestLog* GetQuestLog() {
    auto* world = GetWorldContext();
    return world && world->quest_log.valid() ? &world->quest_log : nullptr;
}

Camera* GetCamera() {
    return g_camera;
}

FriendList* GetFriendList() {
    return g_friend_list_addr ? reinterpret_cast<FriendList*>(g_friend_list_addr) : nullptr;
}

MissionMapContext* GetMissionMapContext() {
    return g_mission_map_context;
}

WorldMapContext* GetWorldMapContext() {
    return g_world_map_context;
}

SalvageSessionInfo* GetSalvageSessionInfo() {
    return g_salvage_context;
}

uint32_t GetControlledCharacterId() {
    WorldContext* world = GetWorldContext();
    return world && world->playerControlledChar ? world->playerControlledChar->agent_id : 0;
}

}  // namespace GW::Context
