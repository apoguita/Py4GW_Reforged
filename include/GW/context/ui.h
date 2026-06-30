#pragma once

#include "base/error_handling.h"

#include "GW/common/constants/agent.h"
#include "GW/common/constants/chat.h"
#include "GW/common/constants/constants.h"
#include "GW/common/game_pos.h"
#include "GW/common/gw_array.h"
#include "GW/context/agent.h"

#include <cstdint>
#include <Windows.h>

namespace GW::ui {
enum ControlAction : uint32_t;
struct Frame;
struct TooltipInfo;
struct CompassPoint;
namespace packet {
enum ActionState : uint32_t;
}
}

namespace GW::Context {

struct Effect;
struct SkillTemplate;
struct WindowPosition;

struct AgentNameTagInfo {
    /* +h0000 */ uint32_t agent_id;
    /* +h0004 */ uint32_t h0002;
    /* +h0008 */ uint32_t h0003;
    /* +h000C */ wchar_t* name_enc;
    /* +h0010 */ uint8_t h0010;
    /* +h0011 */ uint8_t h0012;
    /* +h0012 */ uint8_t h0013;
    /* +h0013 */ uint8_t background_alpha;
    /* +h0014 */ uint32_t text_color;
    /* +h0014 */ uint32_t label_attributes;
    /* +h001C */ uint8_t font_style;
    /* +h001D */ uint8_t underline;
    /* +h001E */ uint8_t h001E;
    /* +h001F */ uint8_t h001F;
    /* +h0020 */ wchar_t* extra_info_enc;
};

struct MapEntryMessage {
    wchar_t* title;
    wchar_t* subtitle;
};

struct DialogBodyInfo {
    uint32_t type;
    uint32_t agent_id;
    wchar_t* message_enc;
};

struct DialogButtonInfo {
    uint32_t button_icon;
    wchar_t* message;
    uint32_t dialog_id;
    uint32_t skill_id;
};

struct ChangeTargetUIMsg {
    uint32_t manual_target_id;
    uint32_t h0008;
    uint32_t auto_target_id;
    uint32_t h0010;
    uint32_t current_target_id;
    uint32_t h0018;
};

struct FloatingWindow {
    void* unk1;
    wchar_t* name;
    uint32_t unk2;
    uint32_t unk3;
    uint32_t save_preference;
    uint32_t unk4;
    uint32_t unk5;
    uint32_t unk6;
    uint32_t window_id;
};
static_assert(sizeof(FloatingWindow) == 0x24, "FloatingWindow size mismatch");

struct EnumPreferenceInfo {
    wchar_t* name;
    uint32_t options_count;
    uint32_t* options;
    uint32_t unk;
    uint32_t pref_type;
};

struct NumberPreferenceInfo {
    wchar_t* name;
    uint32_t flags;
    uint32_t h000C;
    uint32_t h0010;
    uint32_t(__cdecl* clamp_proc)(uint32_t pref_id, uint32_t original_value);
    void* mapping_proc;
};

using ScrollableSortHandler = int(__cdecl*)(uint32_t frame_id_1, uint32_t frame_id_2);

struct MouseCoordsClickPacket {
    float offset_x;
    float offset_y;
    uint32_t h0008;
    uint32_t h000c;
    uint32_t* h0010;
    uint32_t h0014;
};

struct IdentifyItemPacket {
    uint32_t item_id;
    uint32_t kit_id;
};

struct ShowXunlaiChestPacket {
    uint32_t h0000 = 0;
    bool storage_pane_unlocked = true;
    bool anniversary_pane_unlocked = true;
};

struct MoveItemPacket {
    uint32_t item_id;
    uint32_t to_bag_index;
    uint32_t to_slot;
    uint32_t prompt;
};

struct ResizePacket {
    uint32_t h0000 = 0xffffffff;
    float content_width;
    float content_height;
    float h000c = 0;
    float h0010 = 0;
    float content_width2;
    float content_height2;
    float margin_x;
    float margin_y;
};

struct TomeSkillSelectionPacket {
    uint32_t item_id;
    uint32_t h0004;
    uint32_t h0008;
};

struct MeasureContentPacket {
    float max_width;
    float max_height;
    float* size_output;
    uint32_t flags;
};

struct SetLayoutPacket {
    float field_0x0;
    float field_0x4;
    float field_0x8;
    float field_0xc;
    float available_width;
    float available_height;
};

struct SetAgentProfessionPacket {
    AgentID agent_id;
    uint32_t primary;
    uint32_t secondary;
};

struct WeaponSwapPacket {
    uint32_t weapon_bar_frame_id;
    uint32_t weapon_set_id;
};

struct WeaponSetChangedPacket {
    uint32_t h0000;
    uint32_t h0004;
    uint32_t h0008;
    uint32_t h000c;
};

struct ChangeTargetPacket {
    AgentID evaluated_target_id;
    bool has_evaluated_target_changed;
    AgentID auto_target_id;
    bool has_auto_target_changed;
    AgentID manual_target_id;
    bool has_manual_target_changed;
};

struct SendLoadSkillTemplatePacket {
    AgentID agent_id;
    SkillTemplate* skill_template;
};

struct SetRendererValuePacket {
    uint32_t renderer_mode;
    uint32_t metric_id;
    uint32_t value;
};

struct EffectAddPacket {
    AgentID agent_id;
    Effect* effect;
};

struct AgentSpeechBubblePacket {
    AgentID agent_id;
    wchar_t* message;
    uint32_t h0008;
    uint32_t h000c;
};

struct AgentStartCastingPacket {
    AgentID agent_id;
    Constants::SkillID skill_id;
    float duration;
    uint32_t h000c;
};

struct SendCallTargetPacket {
    Constants::CallTargetType call_type;
    AgentID agent_id;
};

struct PreStartSalvagePacket {
    uint32_t item_id;
    uint32_t kit_id;
};

struct PrintChatMessagePacket {
    chat::Channel channel;
    wchar_t* message;
    FILETIME timestamp;
    uint32_t is_reprint;
};

struct ServerActiveQuestChangedPacket {
    Constants::QuestID quest_id;
    GamePos marker;
    uint32_t h0024;
    Constants::MapID map_id;
    uint32_t log_state;
};

struct PartyShowConfirmDialogPacket {
    uint32_t ui_message_to_send_to_party_frame;
    uint32_t prompt_identitifier;
    wchar_t* prompt_enc_str;
};

struct UIPositionChangedPacket {
    uint32_t window_id;
    WindowPosition* position;
};

struct PartySearchInvitePacket {
    uint32_t source_party_search_id;
    uint32_t dest_party_search_id;
};

struct PostProcessingEffectPacket {
    uint32_t tint;
    float amount;
};

struct LogoutPacket {
    uint32_t unknown;
    uint32_t character_select;
};

struct KeyActionPacket {
    ui::ControlAction gw_key;
    uint32_t h0004 = 0x4000;
    uint32_t h0008 = 6;
};

struct MouseClickPacket {
    uint32_t mouse_button;
    uint32_t is_doubleclick;
    uint32_t unknown_type_screen_pos;
    uint32_t h000c;
    uint32_t h0010;
};

struct MouseActionPacket {
    uint32_t frame_id;
    uint32_t child_offset_id;
    uint32_t current_state;
    void* wparam = nullptr;
    void* lparam = nullptr;
};

template <typename TValue>
struct ValueChangedPacket {
    uint32_t child_offset_id;
    uint32_t frame_id;
    uint32_t field_8;
    TValue value;
    uint32_t field_10;
};

struct ChatLogLinePacket {
    wchar_t* message;
    chat::Channel channel;
    FILETIME timestamp;
};

struct UIChatMessage {
    uint32_t channel;
    wchar_t* message;
    uint32_t channel2;
};

struct InteractAgentPacket {
    AgentID agent_id;
    bool call_target;
};

struct SendChangeTargetPacket {
    AgentID target_id;
    AgentID auto_target_id;
};

struct GetColorPacket {
    chat::Color* color;
    chat::Channel channel;
};

struct SendLoadSkillbarPacket {
    AgentID agent_id;
    uint32_t* skill_ids;
};

struct SendPingWeaponSetPacket {
    AgentID agent_id;
    uint32_t weapon_item_id;
    uint32_t offhand_item_id;
};

struct SendMoveItemPacket {
    uint32_t item_id;
    uint32_t quantity;
    uint32_t bag_id;
    uint32_t slot;
};

struct MerchantTransactionInfo {
    uint32_t item_count = 0;
    uint32_t* item_ids = nullptr;
    uint32_t* item_quantities = nullptr;
};

struct MerchantQuoteInfo {
    uint32_t unknown = 0;
    uint32_t item_count = 0;
    uint32_t* item_ids = nullptr;
};

struct VendorWindowPacket {
    Constants::TransactionType transaction_type;
    uint32_t unk;
    AgentID merchant_agent_id;
    uint32_t is_pending;
};

struct VendorQuotePacket {
    uint32_t item_id;
    uint32_t price;
};

struct VendorItemsPacket {
    Constants::TransactionType transaction_type;
    uint32_t item_ids_count;
    uint32_t* item_ids_buffer1;
    uint32_t* item_ids_buffer2;
};

struct SendMerchantRequestQuotePacket {
    Constants::TransactionType type;
    uint32_t unknown;
    MerchantQuoteInfo give;
    MerchantQuoteInfo recv;
};

struct SendMerchantTransactItemPacket {
    Constants::TransactionType type;
    uint32_t gold_give;
    MerchantTransactionInfo give;
    uint32_t gold_recv;
    MerchantTransactionInfo recv;
};

struct SendChatMessagePacket {
    wchar_t* message;
    AgentID agent_id;
};

struct LogChatMessagePacket {
    wchar_t* message;
    chat::Channel channel;
};

struct RecvWhisperPacket {
    uint32_t transaction_id;
    wchar_t* from;
    wchar_t* message;
};

struct StartWhisperPacket {
    wchar_t* player_name;
};

struct SendUseItemPacket {
    uint32_t item_id;
    uint16_t quantity;
};

struct CompassDrawPacket {
    uint32_t player_number;
    uint32_t session_id;
    uint32_t number_of_points;
    ui::CompassPoint* points;
};

struct ButtonMouseActionPacket {
    uint32_t frame_id;
    uint32_t child_offset_id;
    ui::packet::ActionState current_state;
    uint32_t* wparam;
    uint32_t field_10;
    uint32_t field_14;
    uint32_t field_18;
};

struct PreferenceFlagChangedPacket {
    Constants::FlagPreference preference_id;
    uint32_t new_value;
};

struct PreferenceValueChangedPacket {
    Constants::NumberPreference preference_id;
    uint32_t new_value;
};

struct PreferenceEnumChangedPacket {
    Constants::EnumPreference preference_id;
    uint32_t enum_index;
};

using WriteToChatLogPacket = UIChatMessage;

struct PlayerChatMessagePacket {
    chat::Channel channel;
    wchar_t* message;
    uint32_t player_number;
};

struct WriteToChatLogWithSenderPacket {
    uint32_t channel;
    wchar_t* message;
    wchar_t* sender_enc;
};

struct AllyOrGuildMessagePacket {
    chat::Channel channel;
    wchar_t* message;
    wchar_t* sender;
    wchar_t* guild_tag;
};

struct ObjectiveAddPacket {
    uint32_t objective_id;
    wchar_t* name;
    uint32_t type;
};

struct ObjectiveCompletePacket {
    uint32_t objective_id;
};

struct ObjectiveUpdatedPacket {
    uint32_t objective_id;
};

struct ItemUpdatedPacket {
    uint32_t item_id;
    uint32_t model_file_id;
    uint32_t type;
    uint32_t unk1;
    uint32_t extra_id;
    uint32_t materials;
    uint32_t unk2;
    uint32_t interaction;
    uint32_t price;
    uint32_t model_id;
    uint32_t quantity;
    wchar_t* enc_name;
    uint32_t mod_struct_size;
    uint32_t* mod_struct;
};

struct InventorySlotUpdatedPacket {
    uint32_t unk;
    uint32_t item_id;
    uint32_t bag_index;
    uint32_t slot_id;
};

struct SendWorldActionPacket {
    Constants::WorldActionId action_id;
    AgentID agent_id;
    bool suppress_call_target;
};

struct WindowPosition {
    uint32_t state;
    GW::Vec2f p1;
    GW::Vec2f p2;

    bool visible() const { return (state & 0x1) != 0; }
    float xAxis(float ratio) const { return p1.x + (p2.x - p1.x) * ratio; }
    float yAxis(float ratio) const { return p1.y + (p2.y - p1.y) * ratio; }
    GW::Vec2f left() const { return GW::Vec2f(p1.x, yAxis(0.5f)); }
    GW::Vec2f right() const { return GW::Vec2f(p2.x, yAxis(0.5f)); }
    GW::Vec2f top() const { return GW::Vec2f(xAxis(0.5f), p1.y); }
    GW::Vec2f bottom() const { return GW::Vec2f(xAxis(0.5f), p2.y); }
    float width() const { return p2.x - p1.x; }
    float height() const { return p2.y - p1.y; }
};

uintptr_t GetWorldMapStateAddress();
uintptr_t GetPreferencesInitializedAddress();
uintptr_t GetTitleTableAddress();
uintptr_t GetUIDrawnAddress();
uintptr_t GetShiftScreenAddress();
uintptr_t GetGameSettingsAddress();
EnumPreferenceInfo* GetEnumPreferenceOptions();
NumberPreferenceInfo* GetNumberPreferenceOptions();
GW::GWArray<ui::Frame*>* GetFrameArray();
ui::TooltipInfo*** GetCurrentTooltipPtr();
WindowPosition* GetWindowPositionsArray();

}  // namespace GW::Context
