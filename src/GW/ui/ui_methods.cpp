#include "base/error_handling.h"

#include "GW/ui/ui.h"

#include "GW/context/context.h"
#include "GW/context/text_parser.h"
#include "GW/game_thread/game_thread.h"

#include "base/hooker.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <string>

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

struct UIMessageCallbackEntry {
    int altitude;
    PY4GW::HookEntry* entry;
    UIMessageCallback callback;
};

struct FrameUIMessageCallbackEntry {
    int altitude;
    PY4GW::HookEntry* entry;
    FrameUIMessageCallback callback;
};

struct CreateUIComponentCallbackEntry {
    int altitude;
    PY4GW::HookEntry* entry;
    CreateUIComponentCallback callback;
};

extern SendUIMessageFn g_send_ui_message_original;
extern SendFrameUIMessageFn g_send_frame_ui_message_original;
extern CreateHashFromWcharFn g_create_hash_from_wchar_func;
extern GetChildFrameIdFn g_get_child_frame_id_func;
extern GetRootFrameFn g_get_root_frame_func;
extern CreateUIComponentFn g_create_ui_component_func;
extern DestroyUIComponentFn g_destroy_ui_component_func;
extern TypedComponentPassthroughFn g_typed_component_passthrough_func;
extern FrameNewSubclassFn g_frame_new_subclass_func;
extern GetStringPreferenceFn g_get_string_preference_func;
extern GetFlagPreferenceFn g_get_flag_preference_func;
extern GetEnumPreferenceFn g_get_enum_preference_func;
extern GetNumberPreferenceFn g_get_number_preference_func;
extern SetStringPreferenceFn g_set_string_preference_func;
extern SetFlagPreferenceFn g_set_flag_preference_func;
extern SetEnumPreferenceFn g_set_enum_preference_func;
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
extern uint32_t g_create_flat_button_dialog_subclass_type;
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
extern CRITICAL_SECTION g_callback_mutex;
extern bool g_callback_mutex_initialized;
extern std::unordered_map<UIMessage, std::vector<UIMessageCallbackEntry>> g_ui_message_callbacks;
extern std::unordered_map<UIMessage, std::vector<FrameUIMessageCallbackEntry>> g_frame_ui_message_callbacks;
extern std::vector<CreateUIComponentCallbackEntry> g_create_ui_component_callbacks;
extern bool g_open_links;
extern SetWindowVisibleFn g_set_window_visible_func;
extern SetWindowPositionFn g_set_window_position_func;
extern DrawOnCompassFn g_draw_on_compass_func;
extern LoadSettingsFn g_load_settings_func;
extern TitleBinarySearchFn g_title_binary_search_func;
extern GetTitleFn g_get_title_func;
extern ValidateAsyncDecodeStrFn g_validate_async_decode_str_func;

}  // namespace GW::ui

namespace {

using namespace GW;

struct AsyncBuffer {
    void* buffer = nullptr;
    size_t size = 0;
};

constexpr wchar_t TERM_FINAL = 0x0000;
constexpr wchar_t TERM_INTERMEDIATE = 0x0001;
constexpr wchar_t CONCAT_CODED = 0x0002;
constexpr wchar_t CONCAT_LITERAL = 0x0003;
constexpr wchar_t STRING_CHAR_FIRST = 0x0010;
constexpr wchar_t WORD_VALUE_BASE = 0x0100;
constexpr wchar_t WORD_BIT_MORE = 0x8000;
constexpr wchar_t WORD_VALUE_RANGE = WORD_BIT_MORE - WORD_VALUE_BASE;

ui::Frame* GetButtonActionFrame() {
    auto* frame = ui::GetFrameByLabel(L"Game");
    return frame ? ui::GetChildFrame(frame, 6) : nullptr;
}

template <typename T>
ui::Frame* ValueFrame(T* this_ptr) {
    return reinterpret_cast<ui::Frame*>(reinterpret_cast<uintptr_t>(this_ptr) + sizeof(void*));
}

uint32_t FrameField(const ui::Frame* frame, uintptr_t offset) {
    return *reinterpret_cast<const uint32_t*>(reinterpret_cast<uintptr_t>(frame) + offset);
}

template <typename TValue>
bool SendValueChangedMessage(ui::Frame* frame, const TValue& value) {
    if (!frame) {
        return false;
    }

    ui::packet::ValueChangedPacket<TValue> packet = {};
    packet.child_offset_id = FrameField(frame, 0xBC);
    packet.frame_id = FrameField(frame, 0xB8);
    packet.field_8 = 7;
    packet.value = value;
    return ui::SendFrameUIMessage(ui::GetParentFrame(frame), ui::UIMessage(static_cast<uint32_t>(0x31)), &packet, nullptr);
}

void __cdecl CallbackCopyChar(void* param, const wchar_t* value) {
    PY4GW_ASSERT(param && value);
    auto* buffer = static_cast<AsyncBuffer*>(param);
    auto* output = static_cast<char*>(buffer->buffer);
    for (size_t i = 0; i < buffer->size; ++i) {
        output[i] = static_cast<char>(value[i] & 0x7F);
        if (!value[i]) {
            break;
        }
    }
    delete buffer;
}

void __cdecl CallbackCopyWchar(void* param, const wchar_t* value) {
    PY4GW_ASSERT(param && value);
    auto* buffer = static_cast<AsyncBuffer*>(param);
    wcsncpy_s(static_cast<wchar_t*>(buffer->buffer), buffer->size, value, _TRUNCATE);
    delete buffer;
}

void __cdecl CallbackCopyWstring(void* param, const wchar_t* value) {
    PY4GW_ASSERT(param && value);
    auto* output = static_cast<std::wstring*>(param);
    output->assign(value);
}

std::vector<ui::UIMessageCallbackEntry> CopyUiCallbacks(ui::UIMessage message_id) {
    std::vector<ui::UIMessageCallbackEntry> copy;
    if (!ui::g_callback_mutex_initialized) {
        return copy;
    }

    ::EnterCriticalSection(&ui::g_callback_mutex);
    const auto found = ui::g_ui_message_callbacks.find(message_id);
    if (found != ui::g_ui_message_callbacks.end()) {
        copy = found->second;
    }
    ::LeaveCriticalSection(&ui::g_callback_mutex);
    return copy;
}

std::vector<ui::FrameUIMessageCallbackEntry> CopyFrameCallbacks(ui::UIMessage message_id) {
    std::vector<ui::FrameUIMessageCallbackEntry> copy;
    if (!ui::g_callback_mutex_initialized) {
        return copy;
    }

    ::EnterCriticalSection(&ui::g_callback_mutex);
    const auto found = ui::g_frame_ui_message_callbacks.find(message_id);
    if (found != ui::g_frame_ui_message_callbacks.end()) {
        copy = found->second;
    }
    ::LeaveCriticalSection(&ui::g_callback_mutex);
    return copy;
}

bool RawSendUiMessage(ui::UIMessage message_id, void* wparam, void* lparam) {
    if (!ui::g_send_ui_message_original) {
        return false;
    }

    if ((static_cast<uint32_t>(message_id) & 0x30000000U) == 0x30000000U) {
        return true;
    }

    PY4GW::HookBase::EnterHook();
    ui::g_send_ui_message_original(message_id, wparam, lparam);
    PY4GW::HookBase::LeaveHook();
    return true;
}

bool EncChrIsControlCharacter(wchar_t value) {
    return value == TERM_FINAL ||
        value == TERM_INTERMEDIATE ||
        value == CONCAT_CODED ||
        value == CONCAT_LITERAL;
}

bool EncChrIsParam(wchar_t value) {
    return value >= 0x101 && value <= 0x10F;
}

bool EncChrIsParamSegment(wchar_t value) {
    return value >= 0x10A && value <= 0x10C;
}

bool EncChrIsParamLiteral(wchar_t value) {
    return value >= 0x107 && value <= 0x109;
}

bool EncChrIsParamNumeric(wchar_t value) {
    return EncChrIsParam(value) && !EncChrIsParamLiteral(value) && !EncChrIsParamSegment(value);
}

bool EncStrValidateTerminatedLiteral(const wchar_t*& data, const wchar_t* term) {
    while (data < term) {
        const wchar_t value = *data++;
        if (value < STRING_CHAR_FIRST) {
            return value == TERM_INTERMEDIATE;
        }
    }
    return false;
}

bool EncStrValidateSingleWord(const wchar_t*& data, const wchar_t* term) {
    wchar_t value = 0;
    do {
        value = *data++;
        if ((value & ~WORD_BIT_MORE) < WORD_VALUE_BASE) {
            return false;
        }
    } while (value & WORD_BIT_MORE);
    return data < term;
}

bool EncStrValidateWord(const wchar_t*& data, const wchar_t* term) {
    if (!EncStrValidateSingleWord(data, term)) {
        return false;
    }
    if (!(*data & WORD_BIT_MORE)) {
        return true;
    }
    return EncStrValidateSingleWord(data, term);
}

bool EncStrValidate(const wchar_t*& data, const wchar_t* term) {
    bool first_loop = true;
    while (data < term) {
        wchar_t value = 0;
        if (!first_loop) {
            value = *data++;
            if (value == TERM_FINAL) {
                return data == term;
            }
            if (value == TERM_INTERMEDIATE) {
                return data < term;
            }
            if (value == CONCAT_LITERAL) {
                if (EncStrValidateTerminatedLiteral(data, term)) {
                    continue;
                }
                return false;
            }
        }

        if (!EncStrValidateWord(data, term)) {
            return false;
        }

        while (data < term && !EncChrIsControlCharacter(*data)) {
            value = *data++;
            if (EncChrIsParam(value)) {
                if (EncChrIsParamLiteral(value)) {
                    if (!EncStrValidateTerminatedLiteral(data, term)) {
                        return false;
                    }
                } else if (EncChrIsParamSegment(value)) {
                    if (!EncStrValidate(data, term)) {
                        return false;
                    }
                } else if (EncChrIsParamNumeric(value)) {
                    if (!EncStrValidateSingleWord(data, term)) {
                        return false;
                    }
                } else {
                    return false;
                }
            }
        }

        first_loop = false;
    }
    return false;
}

bool PrefsInitialised() {
    const auto addr = Context::GetPreferencesInitializedAddress();
    return addr && *reinterpret_cast<const uint32_t*>(addr) == 1;
}

auto* NumberPreferenceOptions() {
    return Context::GetNumberPreferenceOptions();
}

auto* EnumPreferenceOptions() {
    return Context::GetEnumPreferenceOptions();
}

auto* FrameArray() {
    return Context::GetFrameArray();
}

auto* CurrentTooltipPtr() {
    return Context::GetCurrentTooltipPtr();
}

uint32_t ClampPreference(Constants::NumberPreference pref, uint32_t value) {
    auto* options = NumberPreferenceOptions();
    if (!(options && PrefsInitialised() && pref < Constants::NumberPreference::Count)) {
        return value;
    }
    const auto& info = options[static_cast<uint32_t>(pref)];
    if ((info.flags & 0x1) != 0 && info.clamp_proc) {
        return info.clamp_proc(static_cast<uint32_t>(pref), value);
    }
    return value;
}

}  // namespace

namespace GW::ui {

Frame* FrameRelation::GetFrame() {
    return reinterpret_cast<Frame*>(reinterpret_cast<uintptr_t>(this) - offsetof(Frame, relation));
}

Frame* FrameRelation::GetParent() const {
    return parent ? reinterpret_cast<Frame*>(reinterpret_cast<uintptr_t>(parent) - offsetof(Frame, relation)) : nullptr;
}

Frame* GetRootFrame() {
    return g_get_root_frame_func ? g_get_root_frame_func() : nullptr;
}

Frame* GetFrameById(uint32_t frame_id) {
    auto* frame_array = FrameArray();
    if (!(frame_array && frame_id < frame_array->size())) {
        return nullptr;
    }
    return (*frame_array)[frame_id];
}

Frame* GetParentFrame(Frame* frame) {
    return frame ? frame->relation.GetParent() : nullptr;
}

Frame* GetChildFrame(Frame* parent, uint32_t child_offset) {
    if (!(g_get_child_frame_id_func && parent)) {
        return nullptr;
    }
    return GetFrameById(g_get_child_frame_id_func(parent->frame_id, child_offset));
}

Frame* GetChildFrame(Frame* parent, std::initializer_list<uint32_t> child_offsets) {
    if (!(g_get_child_frame_id_func && parent)) {
        return nullptr;
    }
    uint32_t id = parent->frame_id;
    for (uint32_t child_offset : child_offsets) {
        id = g_get_child_frame_id_func(id, child_offset);
        if (!id) {
            return nullptr;
        }
    }
    return GetFrameById(id);
}

Frame* GetRelatedFrameById(uint32_t frame_id, Constants::FrameChild relation_kind, uint32_t start_after_id) {
    Frame* frame = GetFrameById(frame_id);
    if (!frame) {
        return nullptr;
    }

    Frame* start_after = start_after_id ? GetFrameById(start_after_id) : nullptr;
    switch (relation_kind) {
        case Constants::FrameChild::FirstChild:
        case Constants::FrameChild::LastChild: {
            auto* frame_array = FrameArray();
            if (!frame_array) {
                return nullptr;
            }
            Frame* best = nullptr;
            uint32_t best_offset = relation_kind == Constants::FrameChild::FirstChild ? 0xFFFFFFFFu : 0;
            const uint32_t start_offset = start_after
                ? start_after->child_offset_id
                : (relation_kind == Constants::FrameChild::FirstChild ? 0 : 0xFFFFFFFFu);
            for (auto* candidate : *frame_array) {
                if (!candidate || candidate->relation.GetParent() != frame) {
                    continue;
                }
                const uint32_t offset = candidate->child_offset_id;
                if (relation_kind == Constants::FrameChild::FirstChild) {
                    if (offset > start_offset && offset < best_offset) {
                        best = candidate;
                        best_offset = offset;
                    }
                } else if (offset < start_offset && offset > best_offset) {
                    best = candidate;
                    best_offset = offset;
                }
            }
            return best;
        }
        case Constants::FrameChild::NextSibling:
        case Constants::FrameChild::PrevSibling: {
            auto* frame_array = FrameArray();
            if (!frame_array) {
                return nullptr;
            }
            Frame* parent = frame->relation.GetParent();
            if (!parent) {
                return nullptr;
            }
            const uint32_t my_offset = frame->child_offset_id;
            Frame* best = nullptr;
            uint32_t best_offset = relation_kind == Constants::FrameChild::NextSibling ? 0xFFFFFFFFu : 0;
            for (auto* candidate : *frame_array) {
                if (!candidate || candidate == frame || candidate->relation.GetParent() != parent) {
                    continue;
                }
                const uint32_t offset = candidate->child_offset_id;
                if (relation_kind == Constants::FrameChild::NextSibling) {
                    if (offset > my_offset && offset < best_offset) {
                        best = candidate;
                        best_offset = offset;
                    }
                } else if (offset < my_offset && offset > best_offset) {
                    best = candidate;
                    best_offset = offset;
                }
            }
            return best;
        }
    }
    return nullptr;
}

Frame* GetRelatedFrame(Frame* frame, Constants::FrameChild relation_kind, Frame* start_after) {
    if (!frame) {
        return nullptr;
    }
    return GetRelatedFrameById(frame->frame_id, relation_kind, start_after ? start_after->frame_id : 0);
}

uint32_t GetHashByLabel(const wchar_t* frame_label) {
    return (g_create_hash_from_wchar_func && frame_label)
        ? g_create_hash_from_wchar_func(frame_label, -1)
        : 0;
}

uint32_t GetHashByLabel(const std::string& label) {
    if (!g_create_hash_from_wchar_func) {
        return 0;
    }
    const std::wstring wide_label(label.begin(), label.end());
    return g_create_hash_from_wchar_func(wide_label.c_str(), -1);
}

Frame* GetFrameByLabel(const wchar_t* frame_label) {
    const uint32_t hash = GetHashByLabel(frame_label);
    auto* frame_array = FrameArray();
    if (!(hash && frame_array)) {
        return nullptr;
    }
    for (auto* frame : *frame_array) {
        if (frame && frame->relation.frame_hash_id == hash) {
            return frame;
        }
    }
    return nullptr;
}

uint32_t GetFrameIDByLabel(const wchar_t* frame_label) {
    Frame* frame = GetFrameByLabel(frame_label);
    return frame ? frame->frame_id : 0;
}

uint32_t GetFrameIDByHash(uint32_t hash) {
    auto* frame_array = FrameArray();
    if (!(hash && frame_array)) {
        return 0;
    }
    for (uint32_t frame_id = 0; frame_id < frame_array->size(); ++frame_id) {
        auto* frame = (*frame_array)[frame_id];
        if (frame && frame->relation.frame_hash_id == hash) {
            return frame_id;
        }
    }
    return 0;
}

uint32_t GetChildFrameID(uint32_t parent_hash, std::vector<uint32_t> child_offsets) {
    if (!g_get_child_frame_id_func) {
        return 0;
    }
    uint32_t id = GetFrameIDByHash(parent_hash);
    if (!id) {
        return 0;
    }
    if (child_offsets.empty()) {
        return id;
    }
    for (uint32_t child_offset : child_offsets) {
        id = g_get_child_frame_id_func(id, child_offset);
        if (!id) {
            return 0;
        }
    }
    return id;
}

Frame* GetChildFromNameHash(Frame* parent, uint32_t name_hash) {
    auto* frame_array = FrameArray();
    if (!(parent && name_hash && frame_array)) {
        return nullptr;
    }
    for (auto* frame : *frame_array) {
        if (frame && frame->relation.GetParent() == parent && frame->relation.frame_hash_id == name_hash) {
            return frame;
        }
    }
    return nullptr;
}

std::vector<uint32_t> GetOverlayFrames() {
    std::vector<uint32_t> result;
    auto* frame_array = FrameArray();
    if (!frame_array) {
        return result;
    }
    for (auto* frame : *frame_array) {
        if (frame && frame->IsCreated()) {
            result.push_back(frame->frame_id);
        }
    }
    return result;
}

std::vector<uint32_t> GetPopupFrames() {
    std::vector<uint32_t> result;
    auto* frame_array = FrameArray();
    if (!frame_array) {
        return result;
    }
    for (auto* frame : *frame_array) {
        if (frame && frame->IsCreated()) {
            result.push_back(frame->frame_id);
        }
    }
    return result;
}

uint32_t GetFrameLayer(Frame* frame) {
    return frame ? frame->field10_0x28 : 0;
}

bool SetFrameLayer(Frame* frame, uint32_t layer) {
    if (!frame) {
        return false;
    }
    frame->field10_0x28 = layer;
    return true;
}

bool IsAncestorOf(Frame* frame, Frame* other) {
    if (!(frame && other)) {
        return false;
    }
    Frame* parent = other->relation.GetParent();
    while (parent) {
        if (parent == frame) {
            return true;
        }
        parent = parent->relation.GetParent();
    }
    return false;
}

uint32_t GetFrameCode(Frame* frame) {
    return frame ? frame->frame_id : 0;
}

bool GetFrameMinSize(Frame* frame, float* width, float* height) {
    if (!frame) {
        return false;
    }
    if (width) {
        *width = *reinterpret_cast<const float*>(reinterpret_cast<uintptr_t>(frame) + 0x50);
    }
    if (height) {
        *height = *reinterpret_cast<const float*>(reinterpret_cast<uintptr_t>(frame) + 0x54);
    }
    return true;
}

bool GetFrameClientBorder(Frame* frame, float* left, float* top, float* right, float* bottom) {
    if (!frame) {
        return false;
    }
    if (left)   *left   = *reinterpret_cast<const float*>(reinterpret_cast<uintptr_t>(frame) + 0x58);
    if (top)    *top    = *reinterpret_cast<const float*>(reinterpret_cast<uintptr_t>(frame) + 0x5C);
    if (right)  *right  = *reinterpret_cast<const float*>(reinterpret_cast<uintptr_t>(frame) + 0x60);
    if (bottom) *bottom = *reinterpret_cast<const float*>(reinterpret_cast<uintptr_t>(frame) + 0x64);
    return true;
}

bool GetFrameClipRect(Frame* frame, float* left, float* top, float* right, float* bottom) {
    if (!frame) {
        return false;
    }
    if (left) {
        *left = frame->position.content_left;
    }
    if (top) {
        *top = frame->position.content_top;
    }
    if (right) {
        *right = frame->position.content_right;
    }
    if (bottom) {
        *bottom = frame->position.content_bottom;
    }
    return true;
}

bool GetFramePositionEx(Frame* frame, float* x, float* y, float* w, float* h, uint32_t* flags) {
    if (!frame) {
        return false;
    }
    if (x) {
        *x = frame->position.screen_left;
    }
    if (y) {
        *y = frame->position.screen_bottom;
    }
    if (w) {
        *w = frame->position.screen_right - frame->position.screen_left;
    }
    if (h) {
        *h = frame->position.screen_top - frame->position.screen_bottom;
    }
    if (flags) {
        *flags = frame->position.flags;
    }
    return true;
}

bool GetFrameNativeSize(Frame* frame, float* width, float* height) {
    if (!frame) {
        return false;
    }
    if (width) {
        *width = frame->position.screen_right - frame->position.screen_left;
    }
    if (height) {
        *height = frame->position.screen_top - frame->position.screen_bottom;
    }
    return true;
}

void* GetFrameContext(Frame* frame) {
    if (!frame) {
        return nullptr;
    }
    auto* callbacks = reinterpret_cast<GW::GWArray<FrameInteractionCallback>*>(&frame->frame_callbacks);
    if (!callbacks->valid() || !callbacks->size()) {
        return nullptr;
    }
    for (size_t i = callbacks->size(); i > 0; --i) {
        auto& callback = callbacks->at(i - 1);
        if (callback.uictl_context) {
            return callback.uictl_context;
        }
    }
    return nullptr;
}

uint32_t CreateUIComponent(uint32_t parent_frame_id, uint32_t component_flags, uint32_t tab_index, UIInteractionCallback event_callback, void* wparam, const wchar_t* component_label) {
    if (!g_create_ui_component_func) {
        return 0;
    }
    return g_create_ui_component_func(
        parent_frame_id,
        component_flags,
        tab_index,
        reinterpret_cast<void*>(event_callback),
        reinterpret_cast<wchar_t*>(wparam),
        const_cast<wchar_t*>(component_label));
}

uint32_t CreateUIComponent(uint32_t frame_id, uint32_t component_flags, uint32_t tab_index, UIInteractionCallback event_callback, wchar_t* name_enc, wchar_t* component_label) {
    if (!g_create_ui_component_func) {
        return 0;
    }
    return g_create_ui_component_func(
        frame_id,
        component_flags,
        tab_index,
        reinterpret_cast<void*>(event_callback),
        name_enc,
        component_label);
}

bool DestroyUIComponent(Frame* frame) {
    if (!(frame && frame->IsCreated() && g_destroy_ui_component_func)) {
        return false;
    }
    PY4GW::HookBase::EnterHook();
    const bool result = g_destroy_ui_component_func(frame->frame_id);
    PY4GW::HookBase::LeaveHook();
    return result;
}

bool AddFrameUIInteractionCallback(Frame* frame, UIInteractionCallback callback, void* wparam) {
    if (!(frame && frame->IsCreated() && callback)) {
        return false;
    }
    auto* callbacks = reinterpret_cast<GW::GWArray<FrameInteractionCallback>*>(&frame->frame_callbacks);
    if (!(callbacks->valid() && callbacks->size() < callbacks->capacity())) {
        return false;
    }
    auto& entry = callbacks->m_buffer[callbacks->m_size++];
    entry.callback = callback;
    entry.uictl_context = wparam;
    entry.h0008 = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(wparam));
    return true;
}

bool TriggerFrameRedraw(Frame* frame) {
    if (!(frame && frame->IsCreated())) {
        return false;
    }
    return SendFrameUIMessage(frame, UIMessage::kRefreshContent, nullptr, nullptr);
}

bool SelectDropdownOption(Frame* frame, uint32_t value) {
    if (!frame) {
        return false;
    }

    auto* context = reinterpret_cast<int*>(GetFrameContext(frame));
    uint32_t index = value;
    if (context) {
        bool has_value_mapping = false;
        for (int entry = *context, end = *context + context[2] * 0x20; entry != end; entry += 0x20) {
            if (*reinterpret_cast<int*>(entry + 8) != 0) {
                has_value_mapping = true;
                break;
            }
        }

        if (has_value_mapping) {
            bool found = false;
            for (uint32_t i = 0; i < static_cast<uint32_t>(context[2]); ++i) {
                if (*reinterpret_cast<uint32_t*>(*context + 8 + i * 0x20) == value) {
                    index = i;
                    found = true;
                    break;
                }
            }
            if (!found) {
                return false;
            }
        }
    }

    void* validated_context = GetFrameContext(frame);
    if (!(validated_context && index < *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(validated_context) + 8))) {
        return false;
    }
    if (!SendFrameUIMessage(frame, UIMessage(static_cast<uint32_t>(0x61)), reinterpret_cast<void*>(index), nullptr)) {
        return false;
    }

    ui::packet::ValueChangedPacket<uint32_t> packet = {};
    packet.child_offset_id = frame->child_offset_id;
    packet.frame_id = frame->frame_id;
    packet.field_8 = 7;
    packet.value = index;
    return SendFrameUIMessage(GetParentFrame(frame), UIMessage(static_cast<uint32_t>(0x31)), &packet, nullptr);
}

bool SetFrameMargins(Frame* frame, uint32_t flags, float size[4], float input_mask[4], uint32_t type) {
    if (!(frame && g_typed_component_passthrough_func)) {
        return false;
    }
    PY4GW::HookBase::EnterHook();
    g_typed_component_passthrough_func(
        reinterpret_cast<void*>(frame->frame_id),
        reinterpret_cast<void*>(flags),
        size,
        input_mask,
        reinterpret_cast<void*>(type));
    PY4GW::HookBase::LeaveHook();
    return true;
}

Frame* CreateButtonFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* name_enc, wchar_t* component_label) {
    InitializeTypedComponentCallbacks();
    if (!g_button_frame_callback) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(parent_frame_id, component_flags, child_index, g_button_frame_callback, name_enc, component_label);
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateButtonFrame(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* name_enc, wchar_t* component_label) {
    return parent ? CreateButtonFrame(parent->frame_id, component_flags, child_index, name_enc, component_label) : nullptr;
}

Frame* CreateCtlButtonFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* name_enc, wchar_t* component_label) {
    InitializeTypedComponentCallbacks();
    if (!g_ctl_button_proc_callback) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(parent_frame_id, component_flags, child_index, g_ctl_button_proc_callback, name_enc, component_label);
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateCtlButtonFrame(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* name_enc, wchar_t* component_label) {
    return parent ? CreateCtlButtonFrame(parent->frame_id, component_flags, child_index, name_enc, component_label) : nullptr;
}

Frame* CreateFlatButtonWithClick(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* label_text, bool enable_click) {
    InitializeTypedComponentCallbacks();
    if (!g_ctl_button_proc_callback) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    (void)enable_click;
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(parent_frame_id, component_flags, child_index, g_ctl_button_proc_callback, nullptr, label_text);
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateFlatButtonWithClick(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* label_text, bool enable_click) {
    return parent ? CreateFlatButtonWithClick(parent->frame_id, component_flags, child_index, label_text, enable_click) : nullptr;
}

Frame* CreateTextButtonFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* caption, wchar_t* component_label) {
    InitializeTypedComponentCallbacks();
    if (!g_text_button_frame_callback) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(parent_frame_id, component_flags, child_index, g_text_button_frame_callback, caption, component_label);
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateTextButtonFrame(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* caption, wchar_t* component_label) {
    return parent ? CreateTextButtonFrame(parent->frame_id, component_flags, child_index, caption, component_label) : nullptr;
}

Frame* CreateCheckboxFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* name_enc, wchar_t* component_label) {
    auto* button = CreateButtonFrame(parent_frame_id, component_flags | 0x8000, child_index, name_enc, component_label);
    return button ? reinterpret_cast<Frame*>(reinterpret_cast<uintptr_t>(button) - 4) : nullptr;
}

Frame* CreateCheckboxFrame(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* name_enc, wchar_t* component_label) {
    return parent ? CreateCheckboxFrame(parent->frame_id, component_flags, child_index, name_enc, component_label) : nullptr;
}

Frame* CreateScrollableFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, void* page_context, wchar_t* component_label) {
    InitializeTypedComponentCallbacks();
    if (!g_scrollable_frame_callback) {
        return nullptr;
    }
    TypedScrollablePageContext default_page_context{};
    default_page_context.field_4 = reinterpret_cast<void*>(g_frame_list_callback);
    auto* resolved_page_context = page_context ? reinterpret_cast<TypedScrollablePageContext*>(page_context) : &default_page_context;
    if (!resolved_page_context->field_4) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(
        parent_frame_id,
        component_flags | 0x20000,
        child_index,
        g_scrollable_frame_callback,
        reinterpret_cast<wchar_t*>(resolved_page_context),
        component_label);
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateScrollableFrame(Frame* parent, uint32_t component_flags, uint32_t child_index, void* page_context, wchar_t* component_label) {
    return parent ? CreateScrollableFrame(parent->frame_id, component_flags, child_index, page_context, component_label) : nullptr;
}

Frame* CreateTextLabelFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* name_enc, wchar_t* component_label) {
    InitializeTypedComponentCallbacks();
    if (!g_text_label_frame_callback) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(parent_frame_id, component_flags, child_index, g_text_label_frame_callback, name_enc, component_label);
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateTextLabelFrame(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* name_enc, wchar_t* component_label) {
    return parent ? CreateTextLabelFrame(parent->frame_id, component_flags, child_index, name_enc, component_label) : nullptr;
}

Frame* CreateDropdownFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* component_label) {
    InitializeTypedComponentCallbacks();
    if (!g_dropdown_frame_callback) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(parent_frame_id, component_flags, child_index, g_dropdown_frame_callback, nullptr, component_label);
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateDropdownFrame(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* component_label) {
    return parent ? CreateDropdownFrame(parent->frame_id, component_flags, child_index, component_label) : nullptr;
}

Frame* CreateSliderFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* component_label) {
    InitializeTypedComponentCallbacks();
    if (!g_slider_frame_callback) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(parent_frame_id, component_flags, child_index, g_slider_frame_callback, nullptr, component_label);
    if (frame_id && g_slider_frame_wrapper_callback && g_frame_new_subclass_func) {
        g_frame_new_subclass_func(frame_id, reinterpret_cast<void*>(g_slider_frame_wrapper_callback), 0);
    }
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateSliderFrame(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* component_label) {
    return parent ? CreateSliderFrame(parent->frame_id, component_flags, child_index, component_label) : nullptr;
}

Frame* CreateEditableTextFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* component_label) {
    InitializeTypedComponentCallbacks();
    if (!g_editable_text_frame_callback) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(parent_frame_id, component_flags, child_index, g_editable_text_frame_callback, nullptr, component_label);
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateEditableTextFrame(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* component_label) {
    return parent ? CreateEditableTextFrame(parent->frame_id, component_flags, child_index, component_label) : nullptr;
}

Frame* CreateProgressBar(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* component_label) {
    InitializeTypedComponentCallbacks();
    if (!g_progress_bar_callback) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(parent_frame_id, component_flags, child_index, g_progress_bar_callback, nullptr, component_label);
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateProgressBar(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* component_label) {
    return parent ? CreateProgressBar(parent->frame_id, component_flags, child_index, component_label) : nullptr;
}

Frame* CreateTabsFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index, wchar_t* component_label) {
    InitializeTypedComponentCallbacks();
    if (!g_tabs_frame_callback) {
        return nullptr;
    }
    auto* parent = GetFrameById(parent_frame_id);
    if (!parent) {
        return nullptr;
    }
    while (GetChildFrame(parent, child_index)) {
        ++child_index;
    }
    const uint32_t frame_id = CreateUIComponent(parent_frame_id, component_flags, child_index, g_tabs_frame_callback, nullptr, component_label);
    return frame_id ? GetFrameById(frame_id) : nullptr;
}

Frame* CreateTabsFrame(Frame* parent, uint32_t component_flags, uint32_t child_index, wchar_t* component_label) {
    return parent ? CreateTabsFrame(parent->frame_id, component_flags, child_index, component_label) : nullptr;
}

bool ButtonClick(Frame* btn_frame) {
    if (!(btn_frame && btn_frame->IsCreated())) {
        return false;
    }

    Frame* parent_frame = GetParentFrame(btn_frame);
    if (!(parent_frame && parent_frame->IsCreated())) {
        return false;
    }

    packet::MouseAction action{};
    action.frame_id = btn_frame->child_offset_id;
    action.child_offset_id = btn_frame->child_offset_id;

    struct ButtonParam {
        uint32_t unk;
        uint32_t wparam;
        uint32_t lparam;
    };

    ButtonParam button_param{0, btn_frame->field105_0x1c4, 0};
    action.wparam = &button_param;
    action.current_state = packet::ActionState::MouseUp;

    return SendFrameUIMessage(parent_frame, UIMessage::kMouseClick2, &action);
}

bool TestMouseAction(uint32_t frame_id, uint32_t current_state, uint32_t wparam, uint32_t lparam) {
    Frame* target_frame = GetFrameById(frame_id);
    if (!(target_frame && target_frame->IsCreated())) {
        return false;
    }

    Frame* parent_frame = GetParentFrame(target_frame);
    if (!(parent_frame && parent_frame->IsCreated())) {
        return false;
    }

    packet::MouseAction action{};
    action.frame_id = target_frame->child_offset_id;
    action.child_offset_id = target_frame->child_offset_id;

    struct ButtonParam {
        uint32_t unk;
        uint32_t wparam;
        uint32_t lparam;
    };

    ButtonParam button_param{0, wparam, lparam};
    action.wparam = &button_param;
    action.current_state = current_state;

    return SendFrameUIMessage(parent_frame, UIMessage::kMouseClick2, &action);
}

bool TestMouseClickAction(uint32_t frame_id, uint32_t current_state, uint32_t wparam, uint32_t lparam) {
    Frame* target_frame = GetFrameById(frame_id);
    if (!(target_frame && target_frame->IsCreated())) {
        return false;
    }

    Frame* parent_frame = GetParentFrame(target_frame);
    if (!(parent_frame && parent_frame->IsCreated())) {
        return false;
    }

    packet::MouseAction action{};
    action.frame_id = target_frame->child_offset_id;
    action.child_offset_id = target_frame->child_offset_id;

    struct ButtonParam {
        uint32_t unk;
        uint32_t wparam;
        uint32_t lparam;
    };

    ButtonParam button_param{0, wparam, lparam};
    action.wparam = &button_param;
    action.current_state = current_state;

    return SendFrameUIMessage(parent_frame, UIMessage::kMouseClick, &action);
}

bool SendFrameUIMessage(Frame* frame, UIMessage message_id, void* wparam, void* lparam) {
    if (!(g_send_frame_ui_message_original && frame && frame->frame_callbacks.size())) {
        return false;
    }

    auto callbacks = CopyFrameCallbacks(message_id);
    if (callbacks.empty()) {
        PY4GW::HookBase::EnterHook();
        g_send_frame_ui_message_original(&frame->frame_callbacks, nullptr, message_id, wparam, lparam);
        PY4GW::HookBase::LeaveHook();
        return true;
    }

    PY4GW::HookStatus status;
    auto it = callbacks.begin();
    const auto end = callbacks.end();
    while (it != end) {
        if (it->altitude > 0) {
            break;
        }
        it->callback(&status, frame, message_id, wparam, lparam);
        ++status.altitude;
        ++it;
    }

    const bool result = !status.blocked;
    if (result) {
        PY4GW::HookBase::EnterHook();
        g_send_frame_ui_message_original(&frame->frame_callbacks, nullptr, message_id, wparam, lparam);
        PY4GW::HookBase::LeaveHook();
    }

    while (it != end) {
        it->callback(&status, frame, message_id, wparam, lparam);
        ++status.altitude;
        ++it;
    }
    return result;
}

bool SendUIMessage(UIMessage message_id, void* wparam, void* lparam, bool skip_hooks) {
    if (skip_hooks) {
        return RawSendUiMessage(message_id, wparam, lparam);
    }

    auto callbacks = CopyUiCallbacks(message_id);
    if (callbacks.empty()) {
        return RawSendUiMessage(message_id, wparam, lparam);
    }

    PY4GW::HookStatus status;
    auto it = callbacks.begin();
    const auto end = callbacks.end();
    while (it != end) {
        if (it->altitude > 0) {
            break;
        }
        it->callback(&status, message_id, wparam, lparam);
        ++status.altitude;
        ++it;
    }

    const bool result = !status.blocked && RawSendUiMessage(message_id, wparam, lparam);
    while (it != end) {
        it->callback(&status, message_id, wparam, lparam);
        ++status.altitude;
        ++it;
    }
    return result;
}

bool Keydown(ControlAction key, Frame* target) {
    packet::KeyAction action{key};
    return SendFrameUIMessage(target ? target : GetButtonActionFrame(), UIMessage::kKeyDown, &action);
}

bool Keyup(ControlAction key, Frame* target) {
    packet::KeyAction action{key};
    return SendFrameUIMessage(target ? target : GetButtonActionFrame(), UIMessage::kKeyUp, &action);
}

bool Keypress(ControlAction key, Frame* target) {
    if (!Keydown(key, target)) {
        return false;
    }
    game_thread::Enqueue([key, target] {
        Keyup(key, target);
    });
    return true;
}

GW::Constants::Language GetTextLanguage() {
    return static_cast<GW::Constants::Language>(GetPreference(Constants::NumberPreference::TextLanguage));
}

uint32_t GetPreference(Constants::EnumPreference pref) {
    return g_get_enum_preference_func && PrefsInitialised() && pref < Constants::EnumPreference::Count
        ? g_get_enum_preference_func(static_cast<uint32_t>(pref))
        : 0;
}

uint32_t GetPreferenceOptions(Constants::EnumPreference pref, uint32_t** options_out) {
    auto* options = EnumPreferenceOptions();
    if (!(options && pref < Constants::EnumPreference::Count)) {
        return 0;
    }
    const auto& info = options[static_cast<uint32_t>(pref)];
    if (options_out) {
        *options_out = info.options;
    }
    return info.options_count;
}

uint32_t GetPreference(Constants::NumberPreference pref) {
    return g_get_number_preference_func && PrefsInitialised() && pref < Constants::NumberPreference::Count
        ? g_get_number_preference_func(static_cast<uint32_t>(pref))
        : 0;
}

wchar_t* GetPreference(Constants::StringPreference pref) {
    return g_get_string_preference_func && PrefsInitialised() && pref < Constants::StringPreference::Count
        ? g_get_string_preference_func(static_cast<uint32_t>(pref))
        : nullptr;
}

bool GetPreference(Constants::FlagPreference pref) {
    return g_get_flag_preference_func && PrefsInitialised() && pref < Constants::FlagPreference::Count
        ? g_get_flag_preference_func(static_cast<uint32_t>(pref))
        : false;
}

bool SetPreference(Constants::EnumPreference pref, uint32_t value) {
    if (!(g_set_enum_preference_func && PrefsInitialised() && g_get_enum_preference_func && pref < Constants::EnumPreference::Count)) {
        return false;
    }
    if (!game_thread::IsInGameThread()) {
        game_thread::Enqueue([pref, value] {
            SetPreference(pref, value);
        });
        return true;
    }

    uint32_t* options = nullptr;
    const uint32_t options_count = GetPreferenceOptions(pref, &options);
    size_t i = 0;
    while (i < options_count) {
        if (options[i] == value) {
            break;
        }
        ++i;
    }
    if (i == options_count) {
        return false;
    }

    switch (pref) {
        case Constants::EnumPreference::AntiAliasing:
            if (value == 2) {
                value = 1;
            }
            break;
        case Constants::EnumPreference::TerrainQuality:
        case Constants::EnumPreference::ShaderQuality:
            if (value == 0) {
                value = 1;
            }
            break;
        default:
            break;
    }

    g_set_enum_preference_func(static_cast<uint32_t>(pref), value);

    game_thread::Enqueue([pref] {
        uint32_t current_value = GetPreference(pref);
        switch (pref) {
            case Constants::EnumPreference::AntiAliasing:
                g_set_graphics_renderer_value_func(nullptr, 2, 5, current_value);
                g_set_graphics_renderer_value_func(nullptr, 0, 5, current_value);
                break;
            case Constants::EnumPreference::ShaderQuality:
                g_set_graphics_renderer_value_func(nullptr, 2, 9, current_value);
                g_set_graphics_renderer_value_func(nullptr, 0, 9, current_value);
                break;
            case Constants::EnumPreference::ShadowQuality:
                g_set_in_game_shadow_quality_func(current_value);
                break;
            case Constants::EnumPreference::TerrainQuality:
                g_set_in_game_static_preference_func(2, current_value);
                g_trigger_terrain_rerender_func();
                break;
            case Constants::EnumPreference::Reflections:
                g_set_in_game_static_preference_func(1, current_value);
                break;
            case Constants::EnumPreference::InterfaceSize:
                g_set_in_game_ui_scale_func(current_value);
                break;
            default:
                break;
        }
    });

    return true;
}

bool SetPreference(Constants::NumberPreference pref, uint32_t value) {
    if (!PrefsInitialised()) {
        return false;
    }
    if (!game_thread::IsInGameThread()) {
        game_thread::Enqueue([pref, value] {
            SetPreference(pref, value);
        });
        return true;
    }

    value = ClampPreference(pref, value);
    const bool ok = g_set_number_preference_func && pref < Constants::NumberPreference::Count
        ? (g_set_number_preference_func(static_cast<uint32_t>(pref), value), true)
        : false;
    if (!ok) {
        return false;
    }

    game_thread::Enqueue([pref] {
        uint32_t current_value = GetPreference(pref);
        switch (pref) {
            case Constants::NumberPreference::EffectsVolume:
                if (g_set_volume_func) {
                    g_set_volume_func(0, static_cast<float>(current_value) / 100.f);
                }
                break;
            case Constants::NumberPreference::DialogVolume:
                if (g_set_volume_func) {
                    g_set_volume_func(4, static_cast<float>(current_value) / 100.f);
                }
                break;
            case Constants::NumberPreference::BackgroundVolume:
                if (g_set_volume_func) {
                    g_set_volume_func(1, static_cast<float>(current_value) / 100.f);
                }
                break;
            case Constants::NumberPreference::MusicVolume:
                if (g_set_volume_func) {
                    g_set_volume_func(3, static_cast<float>(current_value) / 100.f);
                }
                break;
            case Constants::NumberPreference::UIVolume:
                if (g_set_volume_func) {
                    g_set_volume_func(2, static_cast<float>(current_value) / 100.f);
                }
                break;
            case Constants::NumberPreference::MasterVolume:
                if (g_set_master_volume_func) {
                    g_set_master_volume_func(static_cast<float>(current_value) / 100.f);
                }
                break;
            case Constants::NumberPreference::FullscreenGamma:
                g_set_graphics_renderer_value_func(nullptr, 2, 0x4, current_value);
                g_set_graphics_renderer_value_func(nullptr, 0, 0x4, current_value);
                break;
            case Constants::NumberPreference::TextureQuality:
                g_set_graphics_renderer_value_func(nullptr, 2, 0xD, current_value);
                g_set_graphics_renderer_value_func(nullptr, 0, 0xD, current_value);
                break;
            case Constants::NumberPreference::RefreshRate:
                g_set_graphics_renderer_value_func(nullptr, 2, 0x8, current_value);
                g_set_graphics_renderer_value_func(nullptr, 0, 0x8, current_value);
                break;
            case Constants::NumberPreference::UseBestTextureFiltering:
                g_set_graphics_renderer_value_func(nullptr, 2, 0xC, current_value);
                g_set_graphics_renderer_value_func(nullptr, 0, 0xC, current_value);
                break;
            case Constants::NumberPreference::ScreenBorderless:
                g_set_graphics_renderer_value_func(nullptr, 2, 0x10, current_value);
                break;
            case Constants::NumberPreference::WindowPosX:
                g_set_graphics_renderer_value_func(nullptr, 2, 6, current_value);
                break;
            case Constants::NumberPreference::WindowPosY:
                g_set_graphics_renderer_value_func(nullptr, 2, 7, current_value);
                break;
            case Constants::NumberPreference::WindowSizeX:
                g_set_graphics_renderer_value_func(nullptr, 2, 0xA, current_value);
                break;
            case Constants::NumberPreference::WindowSizeY:
                g_set_graphics_renderer_value_func(nullptr, 2, 0xB, current_value);
                break;
            case Constants::NumberPreference::ScreenSizeX:
                g_set_graphics_renderer_value_func(nullptr, 0, 0xA, current_value);
                break;
            case Constants::NumberPreference::ScreenSizeY:
                g_set_graphics_renderer_value_func(nullptr, 0, 0xB, current_value);
                break;
            default:
                break;
        }
    });

    return true;
}

bool SetPreference(Constants::StringPreference pref, wchar_t* value) {
    if (!(g_set_string_preference_func && PrefsInitialised() && pref < Constants::StringPreference::Count)) {
        return false;
    }
    if (!game_thread::IsInGameThread()) {
        game_thread::Enqueue([pref, value] {
            SetPreference(pref, value);
        });
        return true;
    }
    g_set_string_preference_func(static_cast<uint32_t>(pref), value);
    return true;
}

bool SetPreference(Constants::FlagPreference pref, bool value) {
    if (!(g_set_flag_preference_func && PrefsInitialised() && pref < Constants::FlagPreference::Count)) {
        return false;
    }
    if (!game_thread::IsInGameThread()) {
        game_thread::Enqueue([pref, value] {
            SetPreference(pref, value);
        });
        return true;
    }
    g_set_flag_preference_func(static_cast<uint32_t>(pref), value);
    switch (pref) {
        case Constants::FlagPreference::IsWindowed: {
            uint32_t pref_value = value ? 2 : 0;
            uint32_t renderer_value = g_get_game_renderer_mode_func ? g_get_game_renderer_mode_func(0) : 0;
            if (g_set_game_renderer_mode_func && pref_value != renderer_value) {
                g_set_game_renderer_mode_func(0, pref_value);
            }
            break;
        }
        default:
            break;
    }
    return true;
}

void SetOpenLinks(bool toggle) {
    g_open_links = toggle;
}

Context::WindowPosition* GetWindowPosition(WindowID window_id) {
    auto* window_positions = Context::GetWindowPositionsArray();
    return (window_positions && window_id < WindowID_Count)
        ? &window_positions[window_id]
        : nullptr;
}

bool SetWindowVisible(WindowID window_id, bool is_visible) {
    if (!(g_set_window_visible_func && window_id < WindowID_Count)) {
        return false;
    }
    g_set_window_visible_func(window_id, is_visible ? 1U : 0U, nullptr, nullptr);
    return true;
}

bool SetWindowPosition(WindowID window_id, Context::WindowPosition* info) {
    if (!(g_set_window_position_func && window_id < WindowID_Count)) {
        return false;
    }
    g_set_window_position_func(window_id, info, nullptr, nullptr);
    return true;
}

bool DrawOnCompass(unsigned session_id, unsigned point_count, CompassPoint* points) {
    if (!g_draw_on_compass_func) {
        return false;
    }
    g_draw_on_compass_func(session_id, point_count, points);
    return true;
}

void LoadSettings(size_t size, uint8_t* data) {
    if (g_load_settings_func) {
        g_load_settings_func(static_cast<uint32_t>(size), data);
    }
}

ArrayByte* GetSettings() {
    return reinterpret_cast<ArrayByte*>(Context::GetGameSettingsAddress());
}

bool GetIsUIDrawn() {
    auto* ui_drawn = reinterpret_cast<uint32_t*>(Context::GetUIDrawnAddress());
    return ui_drawn ? (*ui_drawn == 0) : true;
}

bool GetIsShiftScreenShot() {
    auto* shift_screen = reinterpret_cast<uint32_t*>(Context::GetShiftScreenAddress());
    return shift_screen ? (*shift_screen != 0) : false;
}

bool GetIsWorldMapShowing() {
    auto* world_map_state = reinterpret_cast<uint32_t*>(Context::GetWorldMapStateAddress());
    return world_map_state ? ((*world_map_state & 0x80000U) != 0) : false;
}

bool SetFrameVisible(Frame* frame, bool flag) {
    if (!frame) {
        return false;
    }
    if (flag) {
        frame->frame_state &= ~0x200u;
        frame->frame_state |= 0x2u;
    } else {
        frame->frame_state |= 0x200u;
        frame->frame_state &= ~0x2u;
    }
    return true;
}

bool SetFrameDisabled(Frame* frame, bool flag) {
    if (!frame) {
        return false;
    }
    if (flag) {
        frame->frame_state |= 0x10u;
    } else {
        frame->frame_state &= ~0x10u;
    }
    return true;
}

bool SetFrameOpacity(Frame* frame, float opacity, float fade_time) {
    if (!frame) {
        return false;
    }
    if (opacity < 0.0f) {
        opacity = 0.0f;
    }
    if (opacity > 1.0f) {
        opacity = 1.0f;
    }
    *reinterpret_cast<float*>(reinterpret_cast<uintptr_t>(frame) + 0x30) = opacity;
    (void)fade_time;
    return true;
}

bool ShowFrame(Frame* frame, bool show) {
    return SetFrameVisible(frame, show);
}

const wchar_t* GetFrameTitle(Frame* frame) {
    const auto title_table_addr = Context::GetTitleTableAddress();
    if (!(frame && g_get_title_func && g_title_binary_search_func && title_table_addr)) {
        return nullptr;
    }

    const uint32_t nonclient = *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(frame) + 0xCC);
    if (!nonclient) {
        return nullptr;
    }

    uint32_t result_entry = 0;
    const uint32_t found = g_title_binary_search_func(
        reinterpret_cast<void*>(title_table_addr),
        nullptr,
        reinterpret_cast<void*>(nonclient),
        &result_entry);
    if (!(found && result_entry)) {
        return nullptr;
    }

    const uint32_t title_count = *reinterpret_cast<uint32_t*>(result_entry + 0x1C);
    if (title_count == 0) {
        return nullptr;
    }

    return g_get_title_func(reinterpret_cast<void*>(nonclient));
}

uint32_t GetParentFrameId(Frame* frame) {
    if (!frame) {
        return 0;
    }
    auto* parent = frame->relation.GetParent();
    return parent ? parent->frame_id : 0;
}

float GetFrameOpacity(Frame* frame) {
    return frame ? *reinterpret_cast<float*>(reinterpret_cast<uintptr_t>(frame) + 0x30) : 0.0f;
}

uint32_t GetFrameUserParam(Frame* frame) {
    return frame ? frame->field105_0x1c4 : 0;
}

bool GetFrameStateBit(Frame* frame, uint32_t bit) {
    return frame && (frame->frame_state & bit) != 0;
}

uint32_t GetFrameLimit() {
    uint32_t frame_limit = g_command_line_number_buffer
        ? g_command_line_number_buffer[static_cast<uint32_t>(Constants::NumberCommandLineParameter::FPS)]
        : 0;
    uint32_t vsync_enabled = g_get_graphics_renderer_value_func ? g_get_graphics_renderer_value_func(nullptr, 0xF) : 0;
    uint32_t monitor_refresh_rate = g_get_graphics_renderer_value_func ? g_get_graphics_renderer_value_func(nullptr, 0x16) : 0;
    if (!frame_limit) {
        switch (GetPreference(Constants::EnumPreference::FrameLimiter)) {
            case 1:
                frame_limit = 30;
                break;
            case 2:
                frame_limit = 60;
                break;
            case 3:
                frame_limit = monitor_refresh_rate;
                break;
            default:
                break;
        }
    }
    if (vsync_enabled && monitor_refresh_rate && frame_limit > monitor_refresh_rate) {
        frame_limit = monitor_refresh_rate;
    }
    return frame_limit;
}

bool SetFrameLimit(uint32_t value) {
    return g_command_line_number_buffer
        ? (g_command_line_number_buffer[static_cast<uint32_t>(Constants::NumberCommandLineParameter::FPS)] = value, true)
        : false;
}

std::vector<std::tuple<uint32_t, uint32_t, uint32_t, uint32_t>> GetFrameHierarchy() {
    std::vector<std::tuple<uint32_t, uint32_t, uint32_t, uint32_t>> hierarchy;
    auto* frame_array = FrameArray();
    if (!frame_array) {
        return hierarchy;
    }
    for (auto* frame : *frame_array) {
        if (!(frame && frame->IsCreated() && frame->IsVisible())) {
            continue;
        }
        Frame* parent = frame->relation.GetParent();
        hierarchy.emplace_back(
            parent ? parent->relation.frame_hash_id : 0,
            frame->relation.frame_hash_id,
            parent ? parent->frame_id : 0,
            frame->frame_id);
    }
    return hierarchy;
}

std::vector<std::pair<uint32_t, uint32_t>> GetFrameCoordsByHash(uint32_t frame_hash) {
    std::vector<std::pair<uint32_t, uint32_t>> coords;
    uint32_t frame_id = GetFrameIDByHash(frame_hash);
    if (!frame_id) {
        return coords;
    }
    Frame* frame = GetFrameById(frame_id);
    if (!frame) {
        return coords;
    }
    coords.emplace_back(static_cast<uint32_t>(frame->position.screen_left), static_cast<uint32_t>(frame->position.screen_top));
    coords.emplace_back(static_cast<uint32_t>(frame->position.screen_right), static_cast<uint32_t>(frame->position.screen_bottom));
    return coords;
}

std::vector<uint32_t> GetFrameArray() {
    std::vector<uint32_t> frame_ids;
    auto* frame_array = FrameArray();
    if (!frame_array) {
        return frame_ids;
    }
    frame_ids.reserve(frame_array->size());
    for (uint32_t frame_id = 0; frame_id < frame_array->size(); ++frame_id) {
        if ((*frame_array)[frame_id]) {
            frame_ids.push_back(frame_id);
        }
    }
    return frame_ids;
}

ButtonFrame* ButtonFrame::Create(uint32_t parent_frame_id, uint32_t flags, uint32_t child_offset_id, const wchar_t* button_label, const wchar_t* frame_label) {
    return reinterpret_cast<ButtonFrame*>(CreateButtonFrame(parent_frame_id, flags, child_offset_id, const_cast<wchar_t*>(button_label), const_cast<wchar_t*>(frame_label)));
}

bool ButtonFrame::GetLabel(const wchar_t** enc_string) {
    auto* context = GetFrameContext(this);
    if (context && *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 0xC)) {
        if (enc_string) {
            *enc_string = *reinterpret_cast<const wchar_t**>(reinterpret_cast<uintptr_t>(context) + 4);
        }
        return true;
    }
    return false;
}

bool ButtonFrame::SetLabel(const wchar_t* enc_string) {
    return enc_string && SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5C)), const_cast<wchar_t*>(enc_string), nullptr);
}

bool ButtonFrame::Click() {
    return MouseAction(packet::ActionState::MouseDown) && MouseAction(packet::ActionState::MouseUp);
}

bool ButtonFrame::MouseAction(packet::ActionState action) {
    if ((frame_state & 0x214) != 4) {
        return false;
    }
    auto* parent = GetParentFrame(this);
    if (!(parent && ((parent->frame_state >> 2) & 1) != 0)) {
        return false;
    }

    packet::ButtonMouseActionPacket packet = {};
    packet.frame_id = frame_id;
    packet.child_offset_id = child_offset_id;
    packet.current_state = action;
    packet.wparam = &packet.field_14;
    return SendFrameUIMessage(parent, UIMessage(static_cast<uint32_t>(0x31)), &packet, nullptr);
}

bool ButtonFrame::DoubleClick() {
    return MouseAction(packet::ActionState::MouseDoubleClick);
}

uint32_t FrameWithValue::GetValue() {
    return 0;
}

bool FrameWithValue::SetValue(uint32_t) {
    return false;
}

CheckboxFrame* CheckboxFrame::Create(uint32_t parent_frame_id, uint32_t flags, uint32_t child_offset_id, const wchar_t* text_label_enc_string, const wchar_t* frame_label) {
    return reinterpret_cast<CheckboxFrame*>(CreateCheckboxFrame(parent_frame_id, flags, child_offset_id, const_cast<wchar_t*>(text_label_enc_string), const_cast<wchar_t*>(frame_label)));
}

bool CheckboxFrame::IsChecked() {
    int checked = 0;
    SendFrameUIMessage(ValueFrame(this), UIMessage(static_cast<uint32_t>(0x58)), nullptr, &checked);
    return checked == 1;
}

bool CheckboxFrame::SetChecked(bool checked) {
    int current = 0;
    auto* frame = ValueFrame(this);
    SendFrameUIMessage(frame, UIMessage(static_cast<uint32_t>(0x58)), nullptr, &current);
    if ((current == 1) != checked) {
        return SendFrameUIMessage(frame, UIMessage(static_cast<uint32_t>(0x57)), reinterpret_cast<void*>(static_cast<uintptr_t>(checked)), nullptr);
    }
    return true;
}

uint32_t CheckboxFrame::GetValue() {
    return IsChecked() ? 1u : 0u;
}

bool CheckboxFrame::SetValue(uint32_t value) {
    return SetChecked(value != 0);
}

DropdownFrame* DropdownFrame::Create(uint32_t parent_frame_id, uint32_t flags, uint32_t child_offset_id, const wchar_t* frame_label) {
    return reinterpret_cast<DropdownFrame*>(CreateDropdownFrame(parent_frame_id, flags, child_offset_id, const_cast<wchar_t*>(frame_label)));
}

std::vector<uint32_t> DropdownFrame::GetOptions() {
    std::vector<uint32_t> options;
    auto* frame = ValueFrame(this);
    auto* context = reinterpret_cast<int*>(GetFrameContext(frame));
    if (!context) {
        return options;
    }

    bool has_value_mapping = false;
    for (int entry = *context, end = *context + context[2] * 0x20; entry != end; entry += 0x20) {
        if (*reinterpret_cast<int*>(entry + 8) != 0) {
            has_value_mapping = true;
            break;
        }
    }

    for (uint32_t index = 0; index < static_cast<uint32_t>(context[2]); ++index) {
        if (has_value_mapping) {
            options.push_back(*reinterpret_cast<uint32_t*>(*context + 8 + index * 0x20));
        } else {
            options.push_back(index);
        }
    }
    return options;
}

bool DropdownFrame::SelectOption(uint32_t value) {
    return ui::SelectDropdownOption(ValueFrame(this), value);
}

bool DropdownFrame::SelectIndex(uint32_t index) {
    auto* frame = ValueFrame(this);
    auto* context = GetFrameContext(frame);
    if (!(context && index < *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 8))) {
        return false;
    }
    if (!SendFrameUIMessage(frame, UIMessage(static_cast<uint32_t>(0x61)), reinterpret_cast<void*>(index), nullptr)) {
        return false;
    }
    return SendValueChangedMessage(frame, index);
}

bool DropdownFrame::AddOption(const wchar_t* label_enc_string, uint32_t value) {
    struct AddOptionArgs {
        const wchar_t* label_enc_string;
        uint32_t value;
    } args = {label_enc_string, value};
    return label_enc_string && SendFrameUIMessage(ValueFrame(this), UIMessage(static_cast<uint32_t>(0x57)), &args, nullptr);
}

bool DropdownFrame::GetCount(uint32_t* count) {
    auto* context = GetFrameContext(ValueFrame(this));
    if (!(context && count)) {
        return false;
    }
    *count = *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 8);
    return true;
}

bool DropdownFrame::GetOptionValue(uint32_t index, uint32_t* value) {
    if (!value) {
        return false;
    }
    auto options = GetOptions();
    if (index >= options.size()) {
        return false;
    }
    *value = HasValueMapping() ? options[index] : index;
    return true;
}

bool DropdownFrame::GetOptionIndex(uint32_t value, uint32_t* index) {
    if (!index) {
        return false;
    }
    auto options = GetOptions();
    if (HasValueMapping()) {
        for (uint32_t i = 0; i < options.size(); ++i) {
            if (options[i] == value) {
                *index = i;
                return true;
            }
        }
        return false;
    }
    if (value >= options.size()) {
        return false;
    }
    *index = value;
    return true;
}

bool DropdownFrame::GetSelectedIndex(uint32_t* index) {
    auto* context = GetFrameContext(ValueFrame(this));
    if (!(context && index)) {
        return false;
    }
    *index = *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 0x58);
    return true;
}

bool DropdownFrame::HasValueMapping() {
    auto* context = reinterpret_cast<int*>(GetFrameContext(ValueFrame(this)));
    if (!context) {
        return false;
    }
    for (int entry = *context, end = *context + context[2] * 0x20; entry != end; entry += 0x20) {
        if (*reinterpret_cast<int*>(entry + 8) != 0) {
            return true;
        }
    }
    return false;
}

uint32_t DropdownFrame::GetValue() {
    auto* context = GetFrameContext(ValueFrame(this));
    if (!context) {
        return 0;
    }
    uint32_t value = 0;
    return GetOptionValue(*reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 0x58), &value) ? value : 0;
}

bool DropdownFrame::SetValue(uint32_t value) {
    return SelectOption(value);
}

SliderFrame* SliderFrame::Create(uint32_t parent_frame_id, uint32_t flags, uint32_t child_offset_id, const wchar_t* frame_label) {
    return reinterpret_cast<SliderFrame*>(CreateSliderFrame(parent_frame_id, flags, child_offset_id, const_cast<wchar_t*>(frame_label)));
}

bool SliderFrame::GetValue(uint32_t* selected_value) {
    return SendFrameUIMessage(ValueFrame(this), UIMessage(static_cast<uint32_t>(0x58)), selected_value, nullptr);
}

bool SliderFrame::SetValue(uint32_t value) {
    auto* frame = ValueFrame(this);
    auto* context = GetFrameContext(frame);
    if (!(context &&
        *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 0xC) <= value &&
        value <= *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 0x10))) {
        return false;
    }
    SendFrameUIMessage(frame, UIMessage(static_cast<uint32_t>(0x57)), reinterpret_cast<void*>(value), nullptr);
    return SendValueChangedMessage(frame, value);
}

uint32_t SliderFrame::GetValue() {
    uint32_t value = 0;
    if (!SendFrameUIMessage(ValueFrame(this), UIMessage(static_cast<uint32_t>(0x58)), &value, nullptr)) {
        value = 0;
    }
    return value;
}

EditableTextFrame* EditableTextFrame::Create(uint32_t parent_frame_id, uint32_t flags, uint32_t child_offset_id, const wchar_t* frame_label) {
    return reinterpret_cast<EditableTextFrame*>(CreateEditableTextFrame(parent_frame_id, flags, child_offset_id, const_cast<wchar_t*>(frame_label)));
}

const wchar_t* EditableTextFrame::GetValue() {
    auto* context = GetFrameContext(this);
    return context ? *reinterpret_cast<const wchar_t**>(reinterpret_cast<uintptr_t>(context) + 0x48) : nullptr;
}

bool EditableTextFrame::SetValue(const wchar_t* value) {
    if (!(value && SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5E)), const_cast<wchar_t*>(value), nullptr))) {
        return false;
    }
    return SendValueChangedMessage(this, value);
}

bool EditableTextFrame::SetMaxLength(uint32_t max_length) {
    return max_length && SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5A)), reinterpret_cast<void*>(max_length), nullptr);
}

bool EditableTextFrame::IsReadOnly() {
    uint32_t state = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(this)) & 0xFFFFFFu;
    SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x56)), reinterpret_cast<void*>(reinterpret_cast<uintptr_t>(&state) + 3), nullptr);
    return reinterpret_cast<uint8_t*>(&state)[3] != 0;
}

bool EditableTextFrame::SetReadOnly(bool readonly) {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5B)), reinterpret_cast<void*>(static_cast<uintptr_t>(readonly)), nullptr);
}

ProgressBar* ProgressBar::Create(uint32_t parent_frame_id, uint32_t flags, uint32_t child_offset_id, const wchar_t* frame_label) {
    return reinterpret_cast<ProgressBar*>(CreateProgressBar(parent_frame_id, flags, child_offset_id, const_cast<wchar_t*>(frame_label)));
}

uint32_t ProgressBar::GetValue() {
    uint32_t value = 0;
    SendFrameUIMessage(ValueFrame(this), UIMessage(static_cast<uint32_t>(0x56)), nullptr, &value);
    return value;
}

bool ProgressBar::SetValue(uint32_t value) {
    return SendFrameUIMessage(ValueFrame(this), UIMessage(static_cast<uint32_t>(0x58)), reinterpret_cast<void*>(value), nullptr);
}

bool ProgressBar::SetMax(uint32_t value) {
    return SendFrameUIMessage(ValueFrame(this), UIMessage(static_cast<uint32_t>(0x5A)), reinterpret_cast<void*>(value), nullptr);
}

bool ProgressBar::SetColorId(uint32_t color_id) {
    return color_id < 9 && SendFrameUIMessage(ValueFrame(this), UIMessage(static_cast<uint32_t>(0x65)), reinterpret_cast<void*>(color_id), nullptr);
}

bool ProgressBar::SetStyle(Constants::ProgressBarStyle style) {
    PY4GW_ASSERT(style <= Constants::ProgressBarStyle::kOlive);
    return SendFrameUIMessage(ValueFrame(this), UIMessage(static_cast<uint32_t>(100)), reinterpret_cast<void*>(static_cast<uintptr_t>(style)), nullptr);
}

TextLabelFrame* TextLabelFrame::Create(uint32_t parent_frame_id, uint32_t flags, uint32_t child_offset_id, const wchar_t* text_label_enc_string, const wchar_t* frame_label) {
    return reinterpret_cast<TextLabelFrame*>(CreateTextLabelFrame(parent_frame_id, flags, child_offset_id, const_cast<wchar_t*>(text_label_enc_string), const_cast<wchar_t*>(frame_label)));
}

const wchar_t* TextLabelFrame::GetEncodedLabel() {
    auto* context = GetFrameContext(this);
    if (context && *reinterpret_cast<int*>(reinterpret_cast<uintptr_t>(context) + 0xC) != 0) {
        return *reinterpret_cast<const wchar_t**>(reinterpret_cast<uintptr_t>(context) + 4);
    }
    return nullptr;
}

const wchar_t* TextLabelFrame::GetDecodedLabel() {
    auto* context = GetFrameContext(this);
    if (context && *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 0xC) != 0) {
        const auto* enc = *reinterpret_cast<const wchar_t**>(reinterpret_cast<uintptr_t>(context) + 4);
        const auto len = wcslen(enc) + 1;
        if (len < *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 0xC)) {
            return enc + len;
        }
    }
    return nullptr;
}

bool TextLabelFrame::SetLabel(const wchar_t* enc_string) {
    return enc_string && SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5C)), const_cast<wchar_t*>(enc_string), nullptr);
}

bool TextLabelFrame::SetFont(uint32_t font_id) {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(100)), reinterpret_cast<void*>(font_id), nullptr);
}

const wchar_t* MultiLineTextLabelFrame::GetEncodedLabel() {
    return TextLabelFrame::GetEncodedLabel();
}

const wchar_t* MultiLineTextLabelFrame::GetDecodedLabel() {
    auto* context = GetFrameContext(this);
    if (context && *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 0xC) != 0) {
        const auto* enc = *reinterpret_cast<const wchar_t**>(reinterpret_cast<uintptr_t>(context) + 4);
        const auto len = wcslen(enc) + 1;
        if (len < *reinterpret_cast<uint32_t*>(reinterpret_cast<uintptr_t>(context) + 0xC)) {
            return enc + len;
        }
    }
    return nullptr;
}

bool MultiLineTextLabelFrame::SetLabel(const wchar_t* enc_string) {
    return enc_string && SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5C)), const_cast<wchar_t*>(enc_string), nullptr);
}

TabsFrame* TabsFrame::Create(uint32_t parent_frame_id, uint32_t flags, uint32_t child_offset_id, const wchar_t* frame_label) {
    return reinterpret_cast<TabsFrame*>(CreateTabsFrame(parent_frame_id, flags, child_offset_id, const_cast<wchar_t*>(frame_label)));
}

Frame* TabsFrame::AddTab(const wchar_t* tab_name_enc, uint32_t flags, uint32_t child_offset_id, UIInteractionCallback callback, void* wparam) {
    struct AddTabArgs {
        const wchar_t* tab_name_enc;
        uint32_t flags;
        uint32_t child_offset_id;
        UIInteractionCallback callback;
        void* wparam;
    } args = {tab_name_enc, flags, child_offset_id, callback, wparam};
    uint32_t frame_id = 0;
    SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x56)), &args, &frame_id);
    return GetFrameById(frame_id);
}

bool TabsFrame::DisableTab(uint32_t tab_id) {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x57)), reinterpret_cast<void*>(tab_id), nullptr);
}

bool TabsFrame::EnableTab(uint32_t tab_id) {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x58)), reinterpret_cast<void*>(tab_id), nullptr);
}

bool TabsFrame::RemoveTab(uint32_t tab_id) {
    auto* tab_frame = GetChildFrame(this, tab_id);
    Frame* button_frame = nullptr;
    if (tab_frame) {
        auto* shadow = GetChildFrame(this, tab_frame->frame_id);
        if (shadow == tab_frame) {
            button_frame = GetChildFrame(this, ~tab_frame->frame_id);
        }
    }
    if (!DestroyUIComponent(tab_frame)) {
        return false;
    }
    return DestroyUIComponent(button_frame);
}

bool TabsFrame::GetCurrentTabIndex(uint32_t* tab_id) {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x59)), nullptr, tab_id);
}

bool TabsFrame::GetTabFrameId(uint32_t tab_id, uint32_t* frame_id) {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5A)), reinterpret_cast<void*>(tab_id), frame_id);
}

bool TabsFrame::GetIsTabEnabled(uint32_t tab_id, uint32_t* is_enabled) {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5C)), reinterpret_cast<void*>(tab_id), is_enabled);
}

Frame* TabsFrame::GetTabByLabel(const wchar_t* label) {
    if (!(label && label[0])) {
        return nullptr;
    }
    for (uint32_t tab_index = 0; tab_index < 10; ++tab_index) {
        uint32_t tab_frame_id = 0;
        if (!SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5A)), reinterpret_cast<void*>(tab_index), &tab_frame_id)) {
            continue;
        }
        auto* tab_frame = GetFrameById(tab_frame_id);
        if (!tab_frame) {
            continue;
        }
        auto* mirror = GetChildFrame(this, tab_frame->frame_id);
        if (mirror != tab_frame) {
            continue;
        }
        auto* button_frame = GetChildFrame(this, ~tab_frame->frame_id);
        if (!button_frame) {
            continue;
        }
        auto* context = GetFrameContext(button_frame);
        const wchar_t* button_label = nullptr;
        if (context && *reinterpret_cast<int*>(reinterpret_cast<uintptr_t>(context) + 0xC) != 0) {
            button_label = *reinterpret_cast<const wchar_t**>(reinterpret_cast<uintptr_t>(context) + 4);
        }
        if (!(button_label && button_label[0])) {
            continue;
        }
        if (wcscmp(button_label, label) == 0) {
            return tab_frame;
        }
    }
    return nullptr;
}

Frame* TabsFrame::GetCurrentTab() {
    void* current_index = nullptr;
    if (!SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x59)), nullptr, &current_index)) {
        return nullptr;
    }
    uint32_t current_tab_frame_id = 0;
    if (!SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5A)), current_index, &current_tab_frame_id)) {
        return nullptr;
    }
    return GetFrameById(current_tab_frame_id);
}

bool TabsFrame::ChooseTab(Frame* tab_frame) {
    if (!tab_frame) {
        return false;
    }
    auto* token = reinterpret_cast<void*>(tab_frame->frame_id);
    uint32_t out = 0;
    if (!SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5A)), token, &out)) {
        return false;
    }
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5D)), token, nullptr);
}

bool TabsFrame::ChooseTab(uint32_t tab_index) {
    uint32_t out = 0;
    if (!SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5A)), reinterpret_cast<void*>(tab_index), &out)) {
        return false;
    }
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5D)), reinterpret_cast<void*>(tab_index), nullptr);
}

ButtonFrame* TabsFrame::GetTabButton(Frame* tab_frame) {
    if (!tab_frame) {
        return nullptr;
    }
    auto* mirror = GetChildFrame(this, tab_frame->frame_id);
    if (mirror != tab_frame) {
        return nullptr;
    }
    return reinterpret_cast<ButtonFrame*>(GetChildFrame(this, ~tab_frame->frame_id));
}

ScrollableFrame* ScrollableFrame::Create(uint32_t parent_frame_id, uint32_t flags, uint32_t child_offset_id, ScrollablePageContext* context, const wchar_t* frame_label) {
    return reinterpret_cast<ScrollableFrame*>(CreateScrollableFrame(parent_frame_id, flags, child_offset_id, context, const_cast<wchar_t*>(frame_label)));
}

bool ScrollableFrame::SetSortHandler(SortHandler sort_handler) {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x7FFFFFF4)), reinterpret_cast<void*>(sort_handler), nullptr);
}

ScrollableFrame::SortHandler ScrollableFrame::GetSortHandler() {
    auto* page = GetChildFrame(this, 0);
    page = GetChildFrame(page, 0);
    auto* context = GetFrameContext(page);
    return context ? *reinterpret_cast<SortHandler*>(reinterpret_cast<uintptr_t>(context) + 0xC) : nullptr;
}

bool ScrollableFrame::ClearItems() {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x56)), nullptr, nullptr);
}

bool ScrollableFrame::RemoveItem(uint32_t child_offset_id) {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x58)), reinterpret_cast<void*>(child_offset_id), nullptr);
}

bool ScrollableFrame::AddItem(uint32_t flags, uint32_t child_offset_id, UIInteractionCallback callback) {
    struct AddItemArgs {
        uint32_t flags;
        uint32_t child_offset_id;
        UIInteractionCallback callback;
        void* reserved;
        uint32_t sentinel;
    } args = {flags, child_offset_id, callback, nullptr, 0};
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x57)), &args.flags, &args.reserved);
}

uint32_t ScrollableFrame::GetItemFrameId(uint32_t child_offset_id) {
    uint32_t frame_id = 0;
    SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5B)), reinterpret_cast<void*>(child_offset_id), &frame_id);
    return frame_id;
}

bool ScrollableFrame::GetSelectedValue(uint32_t* selected_value) {
    uint64_t selected = 0;
    const bool ok = SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x67)), nullptr, &selected);
    if (!ok) {
        return false;
    }
    if (selected_value) {
        *selected_value = static_cast<uint32_t>(selected >> 32);
    }
    return static_cast<uint32_t>(selected) != 0;
}

uint32_t ScrollableFrame::GetFirstChildFrameId(uint32_t* offset_of_child_out) {
    struct IterateArgs {
        uint32_t mode;
        uint32_t reserved;
        uint32_t** out_ptr;
        uint32_t* offset_out;
    } args = {2, 0, &offset_of_child_out, offset_of_child_out};
    offset_of_child_out = nullptr;
    if (!SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x59)), &args.mode, nullptr)) {
        return 0;
    }
    return reinterpret_cast<uint32_t>(offset_of_child_out);
}

uint32_t ScrollableFrame::GetNextChildFrameId(uint32_t frame_id, uint32_t* offset_of_child_out) {
    struct IterateArgs {
        uint32_t mode;
        uint32_t frame_id;
        uint32_t* frame_id_io;
        uint32_t* offset_out;
    } args = {0, frame_id, reinterpret_cast<uint32_t*>(&frame_id), offset_of_child_out};
    frame_id = 0;
    if (!SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x59)), &args.mode, nullptr)) {
        return 0;
    }
    return frame_id;
}

uint32_t ScrollableFrame::GetLastChildFrameId(uint32_t* offset_of_child_out) {
    struct IterateArgs {
        uint32_t mode;
        uint32_t reserved;
        uint32_t** out_ptr;
        uint32_t* offset_out;
    } args = {3, 0, &offset_of_child_out, offset_of_child_out};
    offset_of_child_out = nullptr;
    if (!SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x59)), &args.mode, nullptr)) {
        return 0;
    }
    return reinterpret_cast<uint32_t>(offset_of_child_out);
}

uint32_t ScrollableFrame::GetPrevChildFrameId(uint32_t frame_id, uint32_t* offset_of_child_out) {
    struct IterateArgs {
        uint32_t mode;
        uint32_t frame_id;
        uint32_t* frame_id_io;
        uint32_t* offset_out;
    } args = {1, frame_id, reinterpret_cast<uint32_t*>(&frame_id), offset_of_child_out};
    frame_id = 0;
    if (!SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x59)), &args.mode, nullptr)) {
        return 0;
    }
    return frame_id;
}

bool ScrollableFrame::GetItemRect(uint32_t child_offset_id, float rect[4]) {
    return SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x5C)), reinterpret_cast<void*>(child_offset_id), rect);
}

bool ScrollableFrame::GetCount(uint32_t* size) {
    if (!size) {
        return false;
    }
    *size = GetItems(nullptr, 0);
    return true;
}

uint32_t ScrollableFrame::GetItems(uint32_t* child_frame_id_buffer, uint32_t buffer_len) {
    auto* out_buffer = child_frame_id_buffer;
    struct GetItemsArgs {
        uint32_t mode;
        uint32_t reserved;
        uint32_t** frame_id_ptr;
        uint32_t reserved_2;
        ScrollableFrame* self;
    } args = {};
    args.mode = 2;
    args.frame_id_ptr = &child_frame_id_buffer;
    args.reserved_2 = 0;
    args.self = this;
    child_frame_id_buffer = nullptr;

    uint32_t count = 0;
    if (!SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x59)), &args.mode, nullptr) || !child_frame_id_buffer) {
        return 0;
    }

    auto* current_frame_id = child_frame_id_buffer;
    while (current_frame_id) {
        auto* frame = GetFrameById(reinterpret_cast<uint32_t>(current_frame_id));
        if (!frame) {
            return count;
        }

        args.mode = 0;
        args.reserved = frame->frame_id;
        args.frame_id_ptr = &child_frame_id_buffer;
        args.reserved_2 = 0;
        child_frame_id_buffer = nullptr;
        const bool ok = SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x59)), &args.mode, nullptr);
        auto* next_frame_id = ok ? child_frame_id_buffer : nullptr;

        if (((frame->frame_state >> 9) & 1) == 0) {
            if (out_buffer && count < buffer_len) {
                out_buffer[count] = frame->frame_id;
            }
            ++count;
        }
        current_frame_id = next_frame_id;
    }

    return count;
}

Frame* ScrollableFrame::GetPage() {
    auto* page = GetChildFrame(this, 0);
    return GetChildFrame(page, 0);
}

Frame* ScrollableFrame::SetPage(ScrollablePageContext* context) {
    SendFrameUIMessage(this, UIMessage(static_cast<uint32_t>(0x7FFFFFF5)), context, nullptr);
    return GetPage();
}

void AsyncDecodeStr(const wchar_t* enc_str, char* buffer, size_t size) {
    auto* async_buffer = new AsyncBuffer{buffer, size};
    AsyncDecodeStr(enc_str, &CallbackCopyChar, async_buffer);
}

void AsyncDecodeStr(const wchar_t* enc_str, wchar_t* buffer, size_t size) {
    auto* async_buffer = new AsyncBuffer{buffer, size};
    AsyncDecodeStr(enc_str, &CallbackCopyWchar, async_buffer);
}

void AsyncDecodeStr(const wchar_t* enc_str, DecodeStr_Callback callback, void* callback_param, GW::Constants::Language language_id) {
    if (!(g_validate_async_decode_str_func && enc_str && callback)) {
        if (callback) {
            callback(callback_param, L"");
        }
        return;
    }

    if (!IsValidEncStr(enc_str)) {
        callback(callback_param, L"!!!");
        return;
    }

    Context::TextParser* text_parser = Context::GetTextParser();
    if (!text_parser) {
        callback(callback_param, L"");
        return;
    }

    const auto previous_language = text_parser->language_id;
    if (language_id != GW::Constants::Language::Unknown) {
        text_parser->language_id = language_id;
    }
    g_validate_async_decode_str_func(enc_str, callback, callback_param);
    text_parser->language_id = previous_language;
}

void AsyncDecodeStr(const wchar_t* enc_str, std::wstring* out, GW::Constants::Language language_id) {
    AsyncDecodeStr(enc_str, &CallbackCopyWstring, out, language_id);
}

bool IsValidEncStr(const wchar_t* enc_str) {
    if (!enc_str) {
        return false;
    }

    const wchar_t* term = enc_str;
    while (*term != TERM_FINAL && *term != 0) {
        ++term;
    }
    ++term;

    const wchar_t* data = enc_str;
    if (!EncStrValidate(data, term)) {
        return false;
    }
    return data == term;
}

bool UInt32ToEncStr(uint32_t value, wchar_t* buffer, size_t count) {
    const int cases_required = static_cast<int>((value + WORD_VALUE_RANGE - 1) / WORD_VALUE_RANGE);
    if (cases_required + 1 > static_cast<int>(count)) {
        return false;
    }

    buffer[cases_required] = 0;
    for (int i = cases_required - 1; i >= 0; --i) {
        buffer[i] = WORD_VALUE_BASE + (value % WORD_VALUE_RANGE);
        value /= WORD_VALUE_RANGE;
        if (i != cases_required - 1) {
            buffer[i] |= WORD_BIT_MORE;
        }
    }
    return true;
}

uint32_t EncStrToUInt32(const wchar_t* enc_str) {
    uint32_t value = 0;
    do {
        PY4GW_ASSERT(*enc_str >= WORD_VALUE_BASE);
        value *= WORD_VALUE_RANGE;
        value += (*enc_str & ~WORD_BIT_MORE) - WORD_VALUE_BASE;
    } while (*enc_str++ & WORD_BIT_MORE);
    return value;
}

TooltipInfo* GetCurrentTooltip() {
    auto* current_tooltip_ptr = CurrentTooltipPtr();
    return current_tooltip_ptr && *current_tooltip_ptr ? **current_tooltip_ptr : nullptr;
}

void RegisterUIMessageCallback(PY4GW::HookEntry* entry, UIMessage message_id, const UIMessageCallback& callback, int altitude) {
    if (!(g_callback_mutex_initialized && entry)) {
        return;
    }

    ::EnterCriticalSection(&g_callback_mutex);
    auto& callbacks = g_ui_message_callbacks[message_id];
    callbacks.erase(
        std::remove_if(callbacks.begin(), callbacks.end(), [entry](const UIMessageCallbackEntry& value) {
            return value.entry == entry;
        }),
        callbacks.end());
    auto it = callbacks.begin();
    while (it != callbacks.end() && it->altitude <= altitude) {
        ++it;
    }
    callbacks.insert(it, UIMessageCallbackEntry{altitude, entry, callback});
    ::LeaveCriticalSection(&g_callback_mutex);
}

void RemoveUIMessageCallback(PY4GW::HookEntry* entry, UIMessage message_id) {
    if (!(g_callback_mutex_initialized && entry)) {
        return;
    }

    ::EnterCriticalSection(&g_callback_mutex);
    if (message_id == UIMessage::kNone) {
        for (auto& [_, callbacks] : g_ui_message_callbacks) {
            callbacks.erase(
                std::remove_if(callbacks.begin(), callbacks.end(), [entry](const UIMessageCallbackEntry& value) {
                    return value.entry == entry;
                }),
                callbacks.end());
        }
    } else {
        auto found = g_ui_message_callbacks.find(message_id);
        if (found != g_ui_message_callbacks.end()) {
            auto& callbacks = found->second;
            callbacks.erase(
                std::remove_if(callbacks.begin(), callbacks.end(), [entry](const UIMessageCallbackEntry& value) {
                    return value.entry == entry;
                }),
                callbacks.end());
        }
    }
    ::LeaveCriticalSection(&g_callback_mutex);
}

void RegisterFrameUIMessageCallback(PY4GW::HookEntry* entry, UIMessage message_id, const FrameUIMessageCallback& callback, int altitude) {
    if (!(g_callback_mutex_initialized && entry)) {
        return;
    }

    ::EnterCriticalSection(&g_callback_mutex);
    auto& callbacks = g_frame_ui_message_callbacks[message_id];
    callbacks.erase(
        std::remove_if(callbacks.begin(), callbacks.end(), [entry](const FrameUIMessageCallbackEntry& value) {
            return value.entry == entry;
        }),
        callbacks.end());
    auto it = callbacks.begin();
    while (it != callbacks.end() && it->altitude <= altitude) {
        ++it;
    }
    callbacks.insert(it, FrameUIMessageCallbackEntry{altitude, entry, callback});
    ::LeaveCriticalSection(&g_callback_mutex);
}

void RemoveFrameUIMessageCallback(PY4GW::HookEntry* entry) {
    if (!(g_callback_mutex_initialized && entry)) {
        return;
    }

    ::EnterCriticalSection(&g_callback_mutex);
    for (auto& [_, callbacks] : g_frame_ui_message_callbacks) {
        callbacks.erase(
            std::remove_if(callbacks.begin(), callbacks.end(), [entry](const FrameUIMessageCallbackEntry& value) {
                return value.entry == entry;
            }),
            callbacks.end());
    }
    ::LeaveCriticalSection(&g_callback_mutex);
}

void RegisterKeydownCallback(PY4GW::HookEntry* entry, const KeyCallback& callback) {
    RegisterFrameUIMessageCallback(entry, UIMessage::kKeyDown, [callback](PY4GW::HookStatus* status, const Frame*, UIMessage, void* wparam, void*) {
        callback(status, *static_cast<uint32_t*>(wparam));
    });
}

void RemoveKeydownCallback(PY4GW::HookEntry* entry) {
    RemoveFrameUIMessageCallback(entry);
}

void RegisterKeyupCallback(PY4GW::HookEntry* entry, const KeyCallback& callback) {
    RegisterFrameUIMessageCallback(entry, UIMessage::kKeyUp, [callback](PY4GW::HookStatus* status, const Frame*, UIMessage, void* wparam, void*) {
        callback(status, *static_cast<uint32_t*>(wparam));
    });
}

void RemoveKeyupCallback(PY4GW::HookEntry* entry) {
    RemoveFrameUIMessageCallback(entry);
}

void RegisterCreateUIComponentCallback(PY4GW::HookEntry* entry, const CreateUIComponentCallback& callback, int altitude) {
    if (!(g_callback_mutex_initialized && entry)) {
        return;
    }

    ::EnterCriticalSection(&g_callback_mutex);
    g_create_ui_component_callbacks.erase(
        std::remove_if(g_create_ui_component_callbacks.begin(), g_create_ui_component_callbacks.end(), [entry](const CreateUIComponentCallbackEntry& value) {
            return value.entry == entry;
        }),
        g_create_ui_component_callbacks.end());
    auto it = g_create_ui_component_callbacks.begin();
    while (it != g_create_ui_component_callbacks.end() && it->altitude <= altitude) {
        ++it;
    }
    g_create_ui_component_callbacks.insert(it, CreateUIComponentCallbackEntry{altitude, entry, callback});
    ::LeaveCriticalSection(&g_callback_mutex);
}

void RemoveCreateUIComponentCallback(PY4GW::HookEntry* entry) {
    if (!(g_callback_mutex_initialized && entry)) {
        return;
    }

    ::EnterCriticalSection(&g_callback_mutex);
    g_create_ui_component_callbacks.erase(
        std::remove_if(g_create_ui_component_callbacks.begin(), g_create_ui_component_callbacks.end(), [entry](const CreateUIComponentCallbackEntry& value) {
            return value.entry == entry;
        }),
        g_create_ui_component_callbacks.end());
    ::LeaveCriticalSection(&g_callback_mutex);
}

bool GetCommandLinePref(const wchar_t* label, wchar_t** out) {
    if (!(g_get_command_line_string_func && label && out)) {
        return false;
    }
    *out = g_get_command_line_string_func(
        *reinterpret_cast<const uint32_t*>(label));
    return *out != nullptr;
}

bool GetCommandLinePref(const wchar_t* label, uint32_t* out) {
    if (!(g_get_command_line_number_func && label && out)) {
        return false;
    }
    *out = g_get_command_line_number_func(
        *reinterpret_cast<const uint32_t*>(label));
    return true;
}

bool SetCommandLinePref(const wchar_t* label, wchar_t* value) {
    if (!(g_get_command_line_string_func && g_command_line_number_buffer && label && value)) {
        return false;
    }
    const uint32_t param_id = *reinterpret_cast<const uint32_t*>(label);
    g_command_line_number_buffer[param_id] = reinterpret_cast<uint32_t>(value);
    return true;
}

bool SetCommandLinePref(const wchar_t* label, uint32_t value) {
    if (!(g_command_line_number_buffer && label)) {
        return false;
    }
    const uint32_t param_id = *reinterpret_cast<const uint32_t*>(label);
    g_command_line_number_buffer[param_id] = value;
    return true;
}

}  // namespace GW::ui
