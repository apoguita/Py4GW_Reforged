#include "base/error_handling.h"

#include "GW/context/context.h"
#include "GW/context/chat.h"
#include "GW/context/game.h"
#include "GW/context/render.h"
#include "GW/context/ui.h"
#include "GW/context/world.h"

#include "base/CrashHandler.h"
#include "base/patterns.h"

namespace GW::Context {

uintptr_t g_base_ptr = 0;
uintptr_t g_pregame_context_addr = 0;
uintptr_t g_gameplay_context_addr = 0;
uintptr_t g_friend_list_addr = 0;
uintptr_t g_agent_array_addr = 0;
uintptr_t g_player_agent_id_addr = 0;
GW::Constants::ServerRegion* g_region_id_addr = nullptr;
AreaInfo* g_area_info_addr = nullptr;
MapTypeInstanceInfo* g_map_type_instance_infos = nullptr;
uint32_t g_map_type_instance_infos_size = 0;
uintptr_t g_instance_info_ptr = 0;
InstanceInfo* g_instance_info = nullptr;
Skill* g_skill_array_addr = nullptr;
AttributeInfo* g_attribute_array_addr = nullptr;
uintptr_t g_world_map_state_addr = 0;
uintptr_t g_preferences_initialized_addr = 0;
uintptr_t g_title_table_addr = 0;
TitleClientData* g_title_data_addr = nullptr;
uintptr_t g_ui_drawn_addr = 0;
uintptr_t g_shift_screen_addr = 0;
uintptr_t g_game_settings_addr = 0;
EnumPreferenceInfo* g_enum_preference_options_addr = nullptr;
NumberPreferenceInfo* g_number_preference_options_addr = nullptr;
GW::GWArray<ui::Frame*>* g_frame_array = nullptr;
ui::TooltipInfo*** g_current_tooltip_ptr = nullptr;
WindowPosition* g_window_positions_array = nullptr;
MissionMapContext* g_mission_map_context = nullptr;
WorldMapContext* g_world_map_context = nullptr;
SalvageSessionInfo* g_salvage_context = nullptr;
uint32_t* g_storage_open_addr = nullptr;
GW::GWArray<PvPItemUpgradeInfo> g_unlocked_pvp_item_upgrade_array;
GW::GWArray<PvPItemInfo> g_pvp_item_array;
GW::GWArray<CompositeModelInfo>* g_composite_model_info_array = nullptr;
ItemFormula* g_item_formulas = nullptr;
uint32_t g_item_formula_count = 0;
ChatBuffer** g_chat_buffer_addr = nullptr;
uint32_t* g_is_typing_frame_id = nullptr;
GwDxContext* g_dx_context = nullptr;
uintptr_t g_window_handle_ptr = 0;
Camera* g_camera = nullptr;

}  // namespace GW::Context

namespace {

bool g_initialized = false;

bool ResolveBasePointer() {
    CrashContextScope context("startup", "context", "resolve_base_ptr");
    return PY4GW::Patterns::Resolve("context.base_ptr", &GW::Context::g_base_ptr);
}

bool ResolveGameplayContextPointer() {
    CrashContextScope context("startup", "context", "resolve_gameplay_context_ptr");
    return PY4GW::Patterns::Resolve("context.gameplay_context_addr", &GW::Context::g_gameplay_context_addr);
}

bool ResolvePreGameContextPointer() {
    CrashContextScope context("startup", "context", "resolve_pregame_context_ptr");
    return PY4GW::Patterns::Resolve("context.pregame_context_addr", &GW::Context::g_pregame_context_addr);
}

}  // namespace

namespace GW::Context {

bool Initialize() {
    CrashContextScope context("startup", "context", "initialize");
    if (g_initialized) {
        return true;
    }

    PY4GW_ASSERT(PY4GW::Scanner::Initialize());
    PY4GW_ASSERT(PY4GW::Patterns::Initialize());

    if (!ResolveBasePointer()) {
        g_base_ptr = 0;
        return false;
    }
    if (!ResolveGameplayContextPointer()) {
        g_base_ptr = 0;
        g_gameplay_context_addr = 0;
        return false;
    }
    if (!ResolvePreGameContextPointer()) {
        g_base_ptr = 0;
        g_gameplay_context_addr = 0;
        g_pregame_context_addr = 0;
        return false;
    }

    g_initialized = true;
    return true;
}

void Shutdown() {
    CrashContextScope context("shutdown", "context", "shutdown");
    g_base_ptr = 0;
    g_pregame_context_addr = 0;
    g_gameplay_context_addr = 0;
    g_friend_list_addr = 0;
    g_agent_array_addr = 0;
    g_player_agent_id_addr = 0;
    g_region_id_addr = nullptr;
    g_area_info_addr = nullptr;
    g_map_type_instance_infos = nullptr;
    g_map_type_instance_infos_size = 0;
    g_instance_info_ptr = 0;
    g_instance_info = nullptr;
    g_skill_array_addr = nullptr;
    g_attribute_array_addr = nullptr;
    g_world_map_state_addr = 0;
    g_preferences_initialized_addr = 0;
    g_title_table_addr = 0;
    g_title_data_addr = nullptr;
    g_ui_drawn_addr = 0;
    g_shift_screen_addr = 0;
    g_game_settings_addr = 0;
    g_enum_preference_options_addr = nullptr;
    g_number_preference_options_addr = nullptr;
    g_frame_array = nullptr;
    g_current_tooltip_ptr = nullptr;
    g_window_positions_array = nullptr;
    g_mission_map_context = nullptr;
    g_world_map_context = nullptr;
    g_salvage_context = nullptr;
    g_storage_open_addr = nullptr;
    g_unlocked_pvp_item_upgrade_array.m_buffer = nullptr;
    g_unlocked_pvp_item_upgrade_array.m_size = 0;
    g_pvp_item_array.m_buffer = nullptr;
    g_pvp_item_array.m_size = 0;
    g_composite_model_info_array = nullptr;
    g_item_formulas = nullptr;
    g_item_formula_count = 0;
    g_chat_buffer_addr = nullptr;
    g_is_typing_frame_id = nullptr;
    g_dx_context = nullptr;
    g_window_handle_ptr = 0;
    g_camera = nullptr;
    g_initialized = false;
}

}  // namespace GW::Context
