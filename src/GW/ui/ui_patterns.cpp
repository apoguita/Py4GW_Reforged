#include "base/error_handling.h"

#include "GW/ui/ui.h"

#include "base/logger.h"

namespace GW::Context {
extern uintptr_t g_world_map_state_addr;
extern uintptr_t g_preferences_initialized_addr;
extern uintptr_t g_title_table_addr;
extern uintptr_t g_ui_drawn_addr;
extern uintptr_t g_shift_screen_addr;
extern uintptr_t g_game_settings_addr;
extern EnumPreferenceInfo* g_enum_preference_options_addr;
extern NumberPreferenceInfo* g_number_preference_options_addr;
extern GW::GWArray<ui::Frame*>* g_frame_array;
extern ui::TooltipInfo*** g_current_tooltip_ptr;
extern WindowPosition* g_window_positions_array;
}

namespace {

constexpr uintptr_t kLegacyGetTitleFallback = 0x00645B70;
constexpr uintptr_t kLegacyTitleBinarySearchFallback = 0x00645A60;
constexpr uintptr_t kLegacyTitleTableFallback = 0x00BEC7FC;

}  // namespace

namespace GW::ui {

using SendUIMessageFn = void(__cdecl*)(UIMessage message_id, void* wparam, void* lparam);
using SendFrameUIMessageFn = void(__fastcall*)(GW::GWArray<UIInteractionCallback>* callbacks, void* edx, UIMessage message_id, void* wparam, void* lparam);
using SendFrameUIMessageByIdFn = void(__cdecl*)(uint32_t frame_id, UIMessage message_id, void* wparam, void* lparam);
using CreateHashFromWcharFn = uint32_t(__cdecl*)(const wchar_t* value, int seed);
using GetChildFrameIdFn = uint32_t(__cdecl*)(uint32_t parent_frame_id, uint32_t child_offset);
using FindRelatedFrameFn = uint32_t(__cdecl*)(uint32_t frame_id, uint32_t relation_kind, uint32_t start_after_id);
using GetRootFrameFn = Frame*(__cdecl*)();
using LoadSettingsFn = void(__cdecl*)(uint32_t size, uint8_t* data);
using SetWindowVisibleFn = void(__cdecl*)(uint32_t window_id, uint32_t is_visible, void* wparam, void* lparam);
using SetWindowPositionFn = void(__cdecl*)(uint32_t window_id, Context::WindowPosition* info, void* wparam, void* lparam);
using ValidateAsyncDecodeStrFn = void(__cdecl*)(const wchar_t* value, DecodeStr_Callback callback, void* wparam);
using DoAsyncDecodeStrFn = uint32_t(__fastcall*)(void* ecx, void* edx, wchar_t* encoded_str, DecodeStr_Callback callback, void* wparam);
using TitleBinarySearchFn = uint32_t(__fastcall*)(void* table, void* edx, void* key, uint32_t* result_entry);
using GetTitleFn = const wchar_t*(__fastcall*)(void* nonclient);
using DrawOnCompassFn = void(__cdecl*)(uint32_t session_id, uint32_t point_count, CompassPoint* points);
using CreateUIComponentFn = uint32_t(__cdecl*)(uint32_t frame_id, uint32_t component_flags, uint32_t tab_index, void* event_callback, wchar_t* name_enc, wchar_t* component_label);
using DestroyUIComponentFn = bool(__cdecl*)(uint32_t frame_id);
using FrameNewSubclassFn = uint32_t(__cdecl*)(uint32_t frame_id, void* subclass_proc, uint32_t msg_id);
using SetTooltipFn = void(__cdecl*)(TooltipInfo** tooltip);
using TypedComponentPassthroughFn = void(__cdecl*)(void* param_1, void* param_2, void* param_3, void* param_4, void* param_5);
using GetFlagPreferenceFn = bool(__cdecl*)(uint32_t flag_pref_id);
using SetFlagPreferenceFn = void(__cdecl*)(uint32_t flag_pref_id, bool value);
using GetStringPreferenceFn = wchar_t*(__cdecl*)(uint32_t string_pref_id);
using SetStringPreferenceFn = void(__cdecl*)(uint32_t string_pref_id, wchar_t* value);
using GetEnumPreferenceFn = uint32_t(__cdecl*)(uint32_t choice_pref_id);
using SetEnumPreferenceFn = void(__cdecl*)(uint32_t choice_pref_id, uint32_t value);
using GetNumberPreferenceFn = uint32_t(__cdecl*)(uint32_t number_pref_id);
using SetNumberPreferenceFn = void(__cdecl*)(uint32_t number_pref_id, uint32_t value);
using GetGraphicsRendererValueFn = uint32_t(__cdecl*)(void* graphics_renderer_ptr, uint32_t metric_id);
using SetGraphicsRendererValueFn = void(__cdecl*)(void* graphics_renderer, uint32_t renderer_mode, uint32_t metric_id, uint32_t value);
using GetGameRendererModeFn = uint32_t(__cdecl*)(uint32_t game_renderer_context);
using SetGameRendererModeFn = void(__cdecl*)(uint32_t game_renderer_context, uint32_t game_renderer_mode);
using GetGameRendererMetricFn = uint32_t(__cdecl*)(uint32_t game_renderer_context, uint32_t game_renderer_mode, uint32_t metric_key);
using SetInGameShadowQualityFn = void(__cdecl*)(uint32_t value);
using SetInGameStaticPreferenceFn = void(__cdecl*)(uint32_t static_preference_id, uint32_t value);
using TriggerTerrainRerenderFn = void(__cdecl*)();
using SetInGameUIScaleFn = void(__cdecl*)(uint32_t value);
using SetVolumeFn = void(__cdecl*)(uint32_t volume_id, float amount);
using SetMasterVolumeFn = void(__cdecl*)(float amount);

extern SendFrameUIMessageFn g_send_frame_ui_message_func;
extern SendFrameUIMessageByIdFn g_send_frame_ui_message_by_id_func;
extern CreateHashFromWcharFn g_create_hash_from_wchar_func;
extern GetChildFrameIdFn g_get_child_frame_id_func;
extern FindRelatedFrameFn g_find_related_frame_func;
extern GetRootFrameFn g_get_root_frame_func;
extern SendUIMessageFn g_send_ui_message_func;
extern LoadSettingsFn g_load_settings_func;
extern SetTooltipFn g_set_tooltip_func;
extern SetWindowVisibleFn g_set_window_visible_func;
extern SetWindowPositionFn g_set_window_position_func;
extern ValidateAsyncDecodeStrFn g_validate_async_decode_str_func;
extern DoAsyncDecodeStrFn g_async_decode_string_func;
extern TitleBinarySearchFn g_title_binary_search_func;
extern GetTitleFn g_get_title_func;
extern DrawOnCompassFn g_draw_on_compass_func;
extern CreateUIComponentFn g_create_ui_component_func;
extern DestroyUIComponentFn g_destroy_ui_component_func;
extern FrameNewSubclassFn g_frame_new_subclass_func;
extern TypedComponentPassthroughFn g_typed_component_passthrough_func;
extern GetStringPreferenceFn g_get_string_preference_func;
extern GetFlagPreferenceFn g_get_flag_preference_func;
extern GetEnumPreferenceFn g_get_enum_preference_func;
extern GetNumberPreferenceFn g_get_number_preference_func;
extern SetStringPreferenceFn g_set_string_preference_func;
extern SetEnumPreferenceFn g_set_enum_preference_func;
extern SetFlagPreferenceFn g_set_flag_preference_func;
extern SetNumberPreferenceFn g_set_number_preference_func;
extern SetInGameStaticPreferenceFn g_set_in_game_static_preference_func;
extern TriggerTerrainRerenderFn g_trigger_terrain_rerender_func;
extern SetInGameShadowQualityFn g_set_in_game_shadow_quality_func;
extern SetInGameUIScaleFn g_set_in_game_ui_scale_func;
extern SetVolumeFn g_set_volume_func;
extern SetMasterVolumeFn g_set_master_volume_func;
extern GetGraphicsRendererValueFn g_get_graphics_renderer_value_func;
extern SetGraphicsRendererValueFn g_set_graphics_renderer_value_func;
extern SetGameRendererModeFn g_set_game_renderer_mode_func;
extern GetGameRendererModeFn g_get_game_renderer_mode_func;
extern GetGameRendererMetricFn g_get_game_renderer_metric_func;
extern uint32_t* g_command_line_number_buffer;
extern GetFlagPreferenceFn g_get_command_line_flag_func;
extern GetStringPreferenceFn g_get_command_line_string_func;
extern GetNumberPreferenceFn g_get_command_line_number_func;
extern UIInteractionCallback g_button_frame_callback;
extern UIInteractionCallback g_ctl_button_proc_callback;
extern UIInteractionCallback g_text_button_frame_callback;
extern UIInteractionCallback g_scrollable_frame_callback;
extern UIInteractionCallback g_text_label_frame_callback;
extern UIInteractionCallback g_frame_list_callback;
extern UIInteractionCallback g_dropdown_frame_callback;
extern UIInteractionCallback g_slider_frame_callback;
extern UIInteractionCallback g_slider_frame_wrapper_callback;
extern UIInteractionCallback g_editable_text_frame_callback;
extern UIInteractionCallback g_progress_bar_callback;
extern UIInteractionCallback g_tabs_frame_callback;
extern bool g_typed_component_callbacks_initialized;

bool ResolveFrameArray() {
    CrashContextScope context("startup", "ui", "resolve_frame_array");
    return PY4GW::Patterns::Resolve("ui.frame_array_addr", &Context::g_frame_array);
}

bool ResolveWorldMapState() {
    CrashContextScope context("startup", "ui", "resolve_world_map_state");
    return PY4GW::Patterns::Resolve("ui.world_map_state_addr", &Context::g_world_map_state_addr);
}

bool ResolveSendFrameUiMessage() {
    CrashContextScope context("startup", "ui", "resolve_send_frame_ui_message");
    return PY4GW::Patterns::Resolve("ui.send_frame_ui_message_by_id_func", &g_send_frame_ui_message_by_id_func) &&
        PY4GW::Patterns::Resolve("ui.send_frame_ui_message_func", &g_send_frame_ui_message_func);
}

bool ResolveCreateHashFromWchar() {
    CrashContextScope context("startup", "ui", "resolve_create_hash_from_wchar");
    return PY4GW::Patterns::Resolve("ui.create_hash_from_wchar_func", &g_create_hash_from_wchar_func);
}

bool ResolveGetChildFrameId() {
    CrashContextScope context("startup", "ui", "resolve_get_child_frame_id");
    return PY4GW::Patterns::Resolve("ui.get_child_frame_id_func", &g_get_child_frame_id_func);
}

bool ResolveFindRelatedFrame() {
    CrashContextScope context("startup", "ui", "resolve_find_related_frame");
    return PY4GW::Patterns::Resolve("ui.find_related_frame_func", &g_find_related_frame_func);
}

bool ResolveGetRootFrame() {
    CrashContextScope context("startup", "ui", "resolve_get_root_frame");
    return PY4GW::Patterns::Resolve("ui.get_root_frame_func", &g_get_root_frame_func);
}

bool ResolveSendUiMessage() {
    CrashContextScope context("startup", "ui", "resolve_send_ui_message");
    return PY4GW::Patterns::Resolve("ui.send_ui_message_func", &g_send_ui_message_func);
}

bool ResolveLoadSettings() {
    CrashContextScope context("startup", "ui", "resolve_load_settings");
    return PY4GW::Patterns::Resolve("ui.load_settings_func", &g_load_settings_func);
}

bool ResolveUiDrawn() {
    CrashContextScope context("startup", "ui", "resolve_ui_drawn");
    return PY4GW::Patterns::Resolve("ui.ui_drawn_addr", &Context::g_ui_drawn_addr);
}

bool ResolveShiftScreenshot() {
    CrashContextScope context("startup", "ui", "resolve_shift_screenshot");
    return PY4GW::Patterns::Resolve("ui.shift_screenshot_addr", &Context::g_shift_screen_addr);
}

bool ResolveSetTooltip() {
    CrashContextScope context("startup", "ui", "resolve_set_tooltip");
    return PY4GW::Patterns::Resolve("ui.set_tooltip_func", &g_set_tooltip_func) &&
        PY4GW::Patterns::Resolve("ui.current_tooltip_ptr", &Context::g_current_tooltip_ptr);
}

bool ResolveGameSettings() {
    CrashContextScope context("startup", "ui", "resolve_game_settings");
    return PY4GW::Patterns::Resolve("ui.game_settings_addr", &Context::g_game_settings_addr);
}

bool ResolveWindowHelpers() {
    CrashContextScope context("startup", "ui", "resolve_window_helpers");
    return PY4GW::Patterns::Resolve("ui.set_window_visible_func", &g_set_window_visible_func) &&
        PY4GW::Patterns::Resolve("ui.set_window_position_func", &g_set_window_position_func) &&
        PY4GW::Patterns::Resolve("ui.window_positions_array", &Context::g_window_positions_array);
}

bool ResolveValidateAsyncDecode() {
    CrashContextScope context("startup", "ui", "resolve_async_decode");
    return PY4GW::Patterns::Resolve("ui.validate_async_decode_str_func", &g_validate_async_decode_str_func) &&
        PY4GW::Patterns::Resolve("ui.async_decode_string_func", &g_async_decode_string_func);
}

bool ResolveTitleHelpers() {
    CrashContextScope context("startup", "ui", "resolve_title_helpers");
    const bool title_ok = PY4GW::Patterns::Resolve("ui.get_title_func", &g_get_title_func);
    const bool table_ok = PY4GW::Patterns::Resolve("ui.title_table_addr", &Context::g_title_table_addr);
    const bool binary_ok = PY4GW::Patterns::Resolve("ui.title_binary_search_func", &g_title_binary_search_func);

    if (!g_get_title_func) {
        Logger::Instance().LogWarning("[ui] Falling back to legacy GetTitle_Func hardcoded address.", "ui");
        g_get_title_func = reinterpret_cast<GetTitleFn>(kLegacyGetTitleFallback);
    }
    if (!g_title_binary_search_func) {
        Logger::Instance().LogWarning("[ui] Falling back to legacy TitleBinarySearch_Func hardcoded address.", "ui");
        g_title_binary_search_func = reinterpret_cast<TitleBinarySearchFn>(kLegacyTitleBinarySearchFallback);
    }
    if (!Context::g_title_table_addr) {
        Logger::Instance().LogWarning("[ui] Falling back to legacy TitleTable_Addr hardcoded address.", "ui");
        Context::g_title_table_addr = kLegacyTitleTableFallback;
    }

    return (title_ok && table_ok && binary_ok) ||
        (g_get_title_func && g_title_binary_search_func && Context::g_title_table_addr);
}

bool ResolveDrawOnCompass() {
    CrashContextScope context("startup", "ui", "resolve_draw_on_compass");
    return PY4GW::Patterns::Resolve("ui.draw_on_compass_func", &g_draw_on_compass_func);
}

bool ResolveCreateUiComponent() {
    CrashContextScope context("startup", "ui", "resolve_create_ui_component");
    return PY4GW::Patterns::Resolve("ui.create_ui_component_func", &g_create_ui_component_func) &&
        PY4GW::Patterns::Resolve("ui.destroy_ui_component_func", &g_destroy_ui_component_func);
}

bool ResolveFrameNewSubclass() {
    CrashContextScope context("startup", "ui", "resolve_frame_new_subclass");
    return PY4GW::Patterns::Resolve("ui.frame_new_subclass_func", &g_frame_new_subclass_func);
}

bool ResolveTypedComponentPassthrough() {
    CrashContextScope context("startup", "ui", "resolve_typed_component_passthrough");
    return PY4GW::Patterns::Resolve("ui.typed_component_passthrough_func", &g_typed_component_passthrough_func);
}

bool ResolvePreferenceReaders() {
    CrashContextScope context("startup", "ui", "resolve_preference_readers");
    PY4GW::Patterns::Resolve("ui.preferences_initialized_addr", &Context::g_preferences_initialized_addr);
    PY4GW::Patterns::Resolve("ui.get_string_preference_func", &g_get_string_preference_func);
    PY4GW::Patterns::Resolve("ui.get_flag_preference_func", &g_get_flag_preference_func);
    PY4GW::Patterns::Resolve("ui.get_enum_preference_func", &g_get_enum_preference_func);
    PY4GW::Patterns::Resolve("ui.get_number_preference_func", &g_get_number_preference_func);
    PY4GW::Patterns::Resolve("ui.enum_preference_options_addr", &Context::g_enum_preference_options_addr);
    PY4GW::Patterns::Resolve("ui.number_preference_options_addr", &Context::g_number_preference_options_addr);
    return true;
}

bool ResolvePreferenceWriters() {
    CrashContextScope context("startup", "ui", "resolve_preference_writers");
    PY4GW::Patterns::Resolve("ui.set_string_preference_func", &g_set_string_preference_func);
    PY4GW::Patterns::Resolve("ui.set_enum_preference_func", &g_set_enum_preference_func);
    PY4GW::Patterns::Resolve("ui.set_flag_preference_func", &g_set_flag_preference_func);
    PY4GW::Patterns::Resolve("ui.set_number_preference_func", &g_set_number_preference_func);
    PY4GW::Patterns::Resolve("ui.set_in_game_static_preference_func", &g_set_in_game_static_preference_func);
    PY4GW::Patterns::Resolve("ui.trigger_terrain_rerender_func", &g_trigger_terrain_rerender_func);
    PY4GW::Patterns::Resolve("ui.set_in_game_shadow_quality_func", &g_set_in_game_shadow_quality_func);
    PY4GW::Patterns::Resolve("ui.set_in_game_ui_scale_func", &g_set_in_game_ui_scale_func);
    PY4GW::Patterns::Resolve("ui.set_volume_func", &g_set_volume_func);
    PY4GW::Patterns::Resolve("ui.set_master_volume_func", &g_set_master_volume_func);
    PY4GW::Patterns::Resolve("ui.get_graphics_renderer_value_func", &g_get_graphics_renderer_value_func);
    PY4GW::Patterns::Resolve("ui.set_graphics_renderer_value_func", &g_set_graphics_renderer_value_func);
    PY4GW::Patterns::Resolve("ui.set_game_renderer_mode_func", &g_set_game_renderer_mode_func);
    PY4GW::Patterns::Resolve("ui.get_game_renderer_mode_func", &g_get_game_renderer_mode_func);
    PY4GW::Patterns::Resolve("ui.get_game_renderer_metric_func", &g_get_game_renderer_metric_func);
    PY4GW::Patterns::Resolve("ui.command_line_number_buffer", &g_command_line_number_buffer);
    return true;
}

bool ResolveCommandLineFunctions() {
    CrashContextScope context("startup", "ui", "resolve_command_line_functions");
    PY4GW::Patterns::Resolve("ui.get_command_line_flag_func", &g_get_command_line_flag_func);
    PY4GW::Patterns::Resolve("ui.get_command_line_string_func", &g_get_command_line_string_func);
    PY4GW::Patterns::Resolve("ui.get_command_line_number_func", &g_get_command_line_number_func);
    return true;
}

bool TryResolveTypedComponentCallbacks() {
    CrashContextScope context("runtime", "ui", "resolve_typed_component_callbacks");
    if (g_typed_component_callbacks_initialized) {
        return true;
    }
    PY4GW::Patterns::Resolve("ui.button_frame_callback_func", &g_button_frame_callback);
    PY4GW::Patterns::Resolve("ui.ctl_button_proc_callback_func", &g_ctl_button_proc_callback);
    PY4GW::Patterns::Resolve("ui.text_button_frame_callback_func", &g_text_button_frame_callback);
    PY4GW::Patterns::Resolve("ui.text_label_frame_callback_func", &g_text_label_frame_callback);
    PY4GW::Patterns::Resolve("ui.scrollable_frame_callback_func", &g_scrollable_frame_callback);
    PY4GW::Patterns::Resolve("ui.frame_list_callback_func", &g_frame_list_callback);
    PY4GW::Patterns::Resolve("ui.dropdown_frame_callback_func", &g_dropdown_frame_callback);
    PY4GW::Patterns::Resolve("ui.slider_frame_callback_func", &g_slider_frame_callback);
    PY4GW::Patterns::Resolve("ui.slider_frame_wrapper_callback_func", &g_slider_frame_wrapper_callback);
    PY4GW::Patterns::Resolve("ui.editable_text_frame_callback_func", &g_editable_text_frame_callback);
    PY4GW::Patterns::Resolve("ui.progress_bar_callback_func", &g_progress_bar_callback);
    PY4GW::Patterns::Resolve("ui.tabs_frame_callback_func", &g_tabs_frame_callback);

    g_typed_component_callbacks_initialized = true;
    return true;
}

}  // namespace GW::ui
