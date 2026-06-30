#pragma once

#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/hook_types.h"
#include "base/logger.h"
#include "base/patterns.h"
#include "GW/common/constants/constants.h"
#include "GW/common/constants/ui.h"
#include "GW/common/game_pos.h"
#include "GW/common/gw_array.h"
#include "GW/common/gw_list.h"
#include "GW/context/agent.h"
#include "GW/context/skill.h"
#include "GW/context/ui.h"
#include "GW/render/render.h"

// Forward declarations for types from headers that include ui.h (circular dependency)
namespace GW::Context {
    struct SkillTemplate;
}

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <initializer_list>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>
#include <Windows.h>

namespace GW::ui {
    using UIMessage = Constants::UIMessage;

    enum WindowID : uint32_t {
        WindowID_Dialogue1 = 0x0,
        WindowID_Dialogue2 = 0x1,
        WindowID_MissionGoals = 0x2,
        WindowID_DropBundle = 0x3,
        WindowID_Chat = 0x4,
        WindowID_InGameClock = 0x6,
        WindowID_Compass = 0x7,
        WindowID_DamageMonitor = 0x8,
        WindowID_PerformanceMonitor = 0xB,
        WindowID_EffectsMonitor = 0xC,
        WindowID_Hints = 0xD,
        WindowID_MissionStatusAndScoreDisplay = 0xF,
        WindowID_Notifications = 0x11,
        WindowID_Skillbar = 0x14,
        WindowID_SkillMonitor = 0x15,
        WindowID_UpkeepMonitor = 0x17,
        WindowID_SkillWarmup = 0x18,
        WindowID_Menu = 0x1A,
        WindowID_EnergyBar = 0x1C,
        WindowID_ExperienceBar = 0x1D,
        WindowID_HealthBar = 0x1E,
        WindowID_TargetDisplay = 0x1F,
        WindowID_MissionProgress = 0xE,
        WindowID_TradeButton = 0x21,
        WindowID_WeaponBar = 0x22,
        WindowID_Hero1 = 0x33,
        WindowID_Hero2 = 0x34,
        WindowID_Hero3 = 0x35,
        WindowID_Hero = 0x36,
        WindowID_SkillsAndAttributes = 0x38,
        WindowID_Friends = 0x3A,
        WindowID_Guild = 0x3B,
        WindowID_Help = 0x3D,
        WindowID_Inventory = 0x3E,
        WindowID_VaultBox = 0x3F,
        WindowID_InventoryBags = 0x40,
        WindowID_MissionMap = 0x42,
        WindowID_Observe = 0x44,
        WindowID_Options = 0x45,
        WindowID_PartyWindow = 0x48, // NB: state flag is ignored for party window, but position is still good
        WindowID_PartySearch = 0x49,
        WindowID_QuestLog = 0x4F,
        WindowID_Merchant = 0x5C,
        WindowID_Hero4 = 0x5E,
        WindowID_Hero5 = 0x5F,
        WindowID_Hero6 = 0x60,
        WindowID_Hero7 = 0x61,
        WindowID_Count = 0x66
    };

    enum ControlAction : uint32_t {
        ControlAction_None = 0,
        ControlAction_Screenshot = 0xAE,
        // Panels
        ControlAction_CloseAllPanels = 0x85,
        ControlAction_ToggleInventoryWindow = 0x8B,
        ControlAction_OpenScoreChart = 0xBD,
        ControlAction_OpenTemplateManager = 0xD3,
        ControlAction_OpenSaveEquipmentTemplate = 0xD4,
        ControlAction_OpenSaveSkillTemplate = 0xD5,
        ControlAction_OpenParty = 0xBF,
        ControlAction_OpenGuild = 0xBA,
        ControlAction_OpenFriends = 0xB9,
        ControlAction_ToggleAllBags = 0xB8,
        ControlAction_OpenMissionMap = 0xB6,
        ControlAction_OpenBag2 = 0xB5,
        ControlAction_OpenBag1 = 0xB4,
        ControlAction_OpenBelt = 0xB3,
        ControlAction_OpenBackpack = 0xB2,
        ControlAction_OpenSkillsAndAttributes = 0x8F,
        ControlAction_OpenQuestLog = 0x8E,
        ControlAction_OpenWorldMap = 0x8C,
        ControlAction_OpenHero = 0x8A,

        // Weapon sets
        ControlAction_CycleEquipment = 0x86,
        ControlAction_ActivateWeaponSet1 = 0x81,
        ControlAction_ActivateWeaponSet2,
        ControlAction_ActivateWeaponSet3,
        ControlAction_ActivateWeaponSet4,

        ControlAction_DropItem = 0xCD, // drops bundle item >> flags, ashes, etc

        // Chat
        ControlAction_CharReply = 0xBE,
        ControlAction_OpenChat = 0xA1,
        ControlAction_OpenAlliance = 0x88,

        ControlAction_ReverseCamera = 0x90,
        ControlAction_StrafeLeft = 0x91,
        ControlAction_StrafeRight = 0x92,
        ControlAction_TurnLeft = 0xA2,
        ControlAction_TurnRight = 0xA3,
        ControlAction_MoveBackward = 0xAC,
        ControlAction_MoveForward = 0xAD,
        ControlAction_CancelAction = 0xAF,
        ControlAction_Interact = 0x80,
        ControlAction_ReverseDirection = 0xB1,
        ControlAction_Autorun = 0xB7,
        ControlAction_Follow = 0xCC,

        // Targeting
        ControlAction_TargetPartyMember1 = 0x96,
        ControlAction_TargetPartyMember2,
        ControlAction_TargetPartyMember3,
        ControlAction_TargetPartyMember4,
        ControlAction_TargetPartyMember5,
        ControlAction_TargetPartyMember6,
        ControlAction_TargetPartyMember7,
        ControlAction_TargetPartyMember8,
        ControlAction_TargetPartyMember9 = 0xC6,
        ControlAction_TargetPartyMember10,
        ControlAction_TargetPartyMember11,
        ControlAction_TargetPartyMember12,

        ControlAction_TargetNearestItem = 0xC3,
        ControlAction_TargetNextItem = 0xC4,
        ControlAction_TargetPreviousItem = 0xC5,
        ControlAction_TargetPartyMemberNext = 0xCA,
        ControlAction_TargetPartyMemberPrevious = 0xCB,
        ControlAction_TargetAllyNearest = 0xBC,
        ControlAction_ClearTarget = 0xE3,
        ControlAction_TargetSelf = 0xA0, // also 0x96
        ControlAction_TargetPriorityTarget = 0x9F,
        ControlAction_TargetNearestEnemy = 0x93,
        ControlAction_TargetNextEnemy = 0x95,
        ControlAction_TargetPreviousEnemy = 0x9E,

        ControlAction_ShowOthers = 0x89,
        ControlAction_ShowTargets = 0x94,

        ControlAction_CameraZoomIn = 0xCE,
        ControlAction_CameraZoomOut = 0xCF,

        // Party/Hero commands
        ControlAction_ClearPartyCommands = 0xDB,
        ControlAction_CommandParty = 0xD6,
        ControlAction_CommandHero1,
        ControlAction_CommandHero2,
        ControlAction_CommandHero3,
        ControlAction_CommandHero4 = 0x102,
        ControlAction_CommandHero5,
        ControlAction_CommandHero6,
        ControlAction_CommandHero7,

        ControlAction_OpenHero1PetCommander = 0xE0,
        ControlAction_OpenHero2PetCommander,
        ControlAction_OpenHero3PetCommander,
        ControlAction_OpenHero4PetCommander = 0xFE,
        ControlAction_OpenHero5PetCommander,
        ControlAction_OpenHero6PetCommander,
        ControlAction_OpenHero7PetCommander,
        ControlAction_OpenHeroCommander1 = 0xDC,
        ControlAction_OpenHeroCommander2,
        ControlAction_OpenHeroCommander3,
        ControlAction_OpenHeroCommander4 = 0x126,
        ControlAction_OpenHeroCommander5,
        ControlAction_OpenHeroCommander6,
        ControlAction_OpenHeroCommander7,

        ControlAction_Hero1Skill1 = 0xE5,
        ControlAction_Hero1Skill2,
        ControlAction_Hero1Skill3,
        ControlAction_Hero1Skill4,
        ControlAction_Hero1Skill5,
        ControlAction_Hero1Skill6,
        ControlAction_Hero1Skill7,
        ControlAction_Hero1Skill8,
        ControlAction_Hero2Skill1,
        ControlAction_Hero2Skill2,
        ControlAction_Hero2Skill3,
        ControlAction_Hero2Skill4,
        ControlAction_Hero2Skill5,
        ControlAction_Hero2Skill6,
        ControlAction_Hero2Skill7,
        ControlAction_Hero2Skill8,
        ControlAction_Hero3Skill1,
        ControlAction_Hero3Skill2,
        ControlAction_Hero3Skill3,
        ControlAction_Hero3Skill4,
        ControlAction_Hero3Skill5,
        ControlAction_Hero3Skill6,
        ControlAction_Hero3Skill7,
        ControlAction_Hero3Skill8,
        ControlAction_Hero4Skill1 = 0x106,
        ControlAction_Hero4Skill2,
        ControlAction_Hero4Skill3,
        ControlAction_Hero4Skill4,
        ControlAction_Hero4Skill5,
        ControlAction_Hero4Skill6,
        ControlAction_Hero4Skill7,
        ControlAction_Hero4Skill8,
        ControlAction_Hero5Skill1,
        ControlAction_Hero5Skill2,
        ControlAction_Hero5Skill3,
        ControlAction_Hero5Skill4,
        ControlAction_Hero5Skill5,
        ControlAction_Hero5Skill6,
        ControlAction_Hero5Skill7,
        ControlAction_Hero5Skill8,
        ControlAction_Hero6Skill1,
        ControlAction_Hero6Skill2,
        ControlAction_Hero6Skill3,
        ControlAction_Hero6Skill4,
        ControlAction_Hero6Skill5,
        ControlAction_Hero6Skill6,
        ControlAction_Hero6Skill7,
        ControlAction_Hero6Skill8,
        ControlAction_Hero7Skill1,
        ControlAction_Hero7Skill2,
        ControlAction_Hero7Skill3,
        ControlAction_Hero7Skill4,
        ControlAction_Hero7Skill5,
        ControlAction_Hero7Skill6,
        ControlAction_Hero7Skill7,
        ControlAction_Hero7Skill8,

        // Skills
        ControlAction_UseSkill1 = 0xA4,
        ControlAction_UseSkill2,
        ControlAction_UseSkill3,
        ControlAction_UseSkill4,
        ControlAction_UseSkill5,
        ControlAction_UseSkill6,
        ControlAction_UseSkill7,
        ControlAction_UseSkill8

    };


struct CompassPoint {
    CompassPoint() : x(0), y(0) {}
    CompassPoint(int _x, int _y) : x(_x), y(_y) {}
    int x;
    int y;
};

typedef void(__cdecl* DecodeStr_Callback)(void* param, const wchar_t* s);

struct ChatTemplate {
    uint32_t        agent_id;
    uint32_t        type; // 0 = build, 1 = equipment
    GW::GWArray<wchar_t>  code;
    wchar_t*        name;
};

using UIChatMessage = Context::UIChatMessage;

struct InteractionMessage {
    uint32_t frame_id;
    UIMessage message_id; // Same as UIMessage from UIMgr, but includes things like mouse move, click etc
    void** wParam;
};

typedef void(__cdecl* UIInteractionCallback)(InteractionMessage* message, void* wParam, void* lParam);
typedef void(__fastcall* UICtlCallback)(void* frame_context, void* wParam, void* lParam);

struct Frame;

struct FrameInteractionCallback {
    UIInteractionCallback callback;
    void* uictl_context;
    uint32_t h0008;
};

struct FrameRelation {
    FrameRelation* parent;
    uint32_t field67_0x124;
    uint32_t field68_0x128;
    uint32_t frame_hash_id;
    GW::GwList<FrameRelation> siblings;

    Frame* GetFrame();
    Frame* GetParent() const;
};
static_assert(sizeof(FrameRelation) == 0x1C, "FrameRelation size mismatch");

struct FramePosition {
    uint32_t flags;
    float left;
    float bottom;
    float right;
    float top;

    float content_left;
    float content_bottom;
    float content_right;
    float content_top;

    float unk;
    float scale_factor; // Depends on UI scale
    float viewport_width; // Width in px of available screen height; this may sometimes be scaled down, too!
    float viewport_height; // Height in px of available screen height; this may sometimes be scaled down, too!

    float screen_left;
    float screen_bottom;
    float screen_right;
    float screen_top;

    [[nodiscard]] GW::Vec2f GetTopLeftOnScreen(const Frame* frame = nullptr) const;
    [[nodiscard]] GW::Vec2f GetBottomRightOnScreen(const Frame* frame = nullptr) const;
    [[nodiscard]] GW::Vec2f GetContentTopLeft(const Frame* frame = nullptr) const;
    [[nodiscard]] GW::Vec2f GetContentBottomRight(const Frame* frame = nullptr) const;
    [[nodiscard]] GW::Vec2f GetSizeOnScreen(const Frame* frame = nullptr) const;
    [[nodiscard]] GW::Vec2f GetViewportScale(const Frame* frame = nullptr) const;
};
static_assert(sizeof(FramePosition) == 0x44, "FramePosition size mismatch");

struct TooltipInfo {
    uint32_t bit_field;
    UIInteractionCallback* render;
    uint32_t* payload;
    uint32_t payload_len;
    uint32_t unk1;
    uint32_t unk2;
    uint32_t unk3;
    uint32_t unk4;
};

struct DecodingString {
    std::wstring encoded;
    std::wstring decoded;
    void* original_callback;
    void* original_param;
    void* ecx;
    void* edx;
};

struct CreateUIComponentPacket {
    uint32_t frame_id;
    uint32_t component_flags;
    uint32_t tab_index;
    UIInteractionCallback event_callback;
    union {
        void* wparam;
        wchar_t* name_enc;
    };
    wchar_t* component_label;
};

struct TypedScrollablePageContext {
    void* field_0;
    void* field_4;
    uint32_t field_8;
};

struct Frame {
    uint32_t field1_0x0;
    uint32_t field2_0x4;
    uint32_t frame_layout;
    uint32_t field3_0xc;
    uint32_t field4_0x10;
    uint32_t field5_0x14;
    uint32_t visibility_flags;
    uint32_t field7_0x1c;
    uint32_t type;
    uint32_t template_type;
    uint32_t field10_0x28;
    uint32_t field11_0x2c;
    uint32_t field12_0x30;
    uint32_t field13_0x34;
    uint32_t field14_0x38;
    uint32_t field15_0x3c;
    uint32_t field16_0x40;
    uint32_t field17_0x44;
    uint32_t field18_0x48;
    uint32_t field19_0x4c;
    uint32_t field20_0x50;
    uint32_t field21_0x54;
    uint32_t field22_0x58;
    uint32_t field23_0x5c;
    uint32_t field24_0x60;
    uint32_t field24a_0x64;
    uint32_t field24b_0x68;
    uint32_t field25_0x6c;
    uint32_t field26_0x70;
    uint32_t field27_0x74;
    uint32_t field28_0x78;
    uint32_t field29_0x7c;
    uint32_t field30_0x80;
    GW::GWArray<void*> field31_0x84;
    uint32_t field32_0x94;
    uint32_t field33_0x98;
    uint32_t field34_0x9c;
    uint32_t field35_0xa0;
    uint32_t field36_0xa4;
    GW::GWArray<UIInteractionCallback> frame_callbacks; // GW::GWArray<FrameInteractionCallback> frame_callbacks;
    uint32_t child_offset_id; // Offset of this child in relation to its parent
    uint32_t frame_id; // Offset in the global frame array
    uint32_t field40_0xc0;
    uint32_t field41_0xc4;
    uint32_t field42_0xc8;
    uint32_t field43_0xcc;
    uint32_t field44_0xd0;
    uint32_t field45_0xd4;
    FramePosition position;
    uint32_t field63_0x11c;
    uint32_t field64_0x120;
    uint32_t field65_0x124;
    FrameRelation relation;
    uint32_t field73_0x144;
    uint32_t field74_0x148;
    uint32_t field75_0x14c;
    uint32_t field76_0x150;
    uint32_t field77_0x154;
    uint32_t field78_0x158;
    uint32_t field79_0x15c;
    uint32_t field80_0x160;
    uint32_t field81_0x164;
    uint32_t field82_0x168;
    uint32_t field83_0x16c;
    uint32_t field84_0x170;
    uint32_t field85_0x174;
    uint32_t field86_0x178;
    uint32_t field87_0x17c;
    uint32_t field88_0x180;
    uint32_t field89_0x184;
    uint32_t field90_0x188;
    uint32_t frame_state;
    uint32_t field92_0x190;
    uint32_t field93_0x194;
    uint32_t field94_0x198;
    uint32_t field95_0x19c;
    uint32_t field96_0x1a0;
    uint32_t field97_0x1a4;
    uint32_t field98_0x1a8;
    TooltipInfo* tooltip_info;
    uint32_t field100_0x1b0;
    uint32_t field101_0x1b4;
    uint32_t field102_0x1b8;
    uint32_t field103_0x1bc;
    uint32_t field104_0x1c0;
    uint32_t field105_0x1c4;

    bool IsCreated() const { return (frame_state & 0x4) != 0; }
    bool IsHidden() const { return (frame_state & 0x200) != 0; }
    bool IsVisible() const { return !IsHidden(); }
    bool IsDisabled() const { return (frame_state & 0x10) != 0; }
};
static_assert(sizeof(Frame) == 0x1C8, "Frame size mismatch");
static_assert(offsetof(Frame, relation) == 0x128, "Frame::relation offset mismatch");

inline GW::Vec2f FramePosition::GetTopLeftOnScreen(const Frame* frame) const
{
    const auto viewport_scale = GetViewportScale(frame);
    const auto height = frame ? frame->position.viewport_height : viewport_height;
    return {
        screen_left * viewport_scale.x,
        (height - screen_top) * viewport_scale.y
    };
}

inline GW::Vec2f FramePosition::GetBottomRightOnScreen(const Frame* frame) const
{
    const auto viewport_scale = GetViewportScale(frame);
    const auto height = frame ? frame->position.viewport_height : viewport_height;
    return {
        screen_right * viewport_scale.x,
        (height - screen_bottom) * viewport_scale.y
    };
}

inline GW::Vec2f FramePosition::GetContentTopLeft(const Frame* frame) const
{
    const auto viewport_scale = GetViewportScale(frame);
    const auto height = frame ? frame->position.viewport_height : viewport_height;
    return {
        content_left * viewport_scale.x,
        (height - content_top) * viewport_scale.y
    };
}

inline GW::Vec2f FramePosition::GetContentBottomRight(const Frame* frame) const
{
    const auto viewport_scale = GetViewportScale(frame);
    const auto height = frame ? frame->position.viewport_height : viewport_height;
    return {
        content_right * viewport_scale.x,
        (height - content_bottom) * viewport_scale.y
    };
}

inline GW::Vec2f FramePosition::GetSizeOnScreen(const Frame* frame) const
{
    const auto viewport_scale = GetViewportScale(frame);
    return {
        (screen_right - screen_left) * viewport_scale.x,
        (screen_top - screen_bottom) * viewport_scale.y,
    };
}

inline GW::Vec2f FramePosition::GetViewportScale(const Frame* frame) const
{
    const auto screen_width = static_cast<float>(GW::render::GetViewportWidth());
    const auto screen_height = static_cast<float>(GW::render::GetViewportHeight());
    return {
        screen_width / (frame ? frame->position.viewport_width : viewport_width),
        screen_height / (frame ? frame->position.viewport_height : viewport_height)
    };
}

} // namespace GW::ui

namespace GW::ui {

namespace packet {
enum ActionState : uint32_t {
    MouseDown = 0x6,
    MouseUp = 0x7,
    MouseClick = 0x8,
    MouseDoubleClick = 0x9,
    DragRelease = 0xB,
    KeyDown = 0xE
};

using kSendCallTarget = Context::SendCallTargetPacket;

using kMouseCoordsClick = Context::MouseCoordsClickPacket;

using kIdentifyItem = Context::IdentifyItemPacket;

using kShowXunlaiChest = Context::ShowXunlaiChestPacket;

using kMoveItem = Context::MoveItemPacket;

using kResize = Context::ResizePacket;

using kTomeSkillSelection = Context::TomeSkillSelectionPacket;

using kMeasureContent = Context::MeasureContentPacket;

using kSetLayout = Context::SetLayoutPacket;

using kSetAgentProfession = Context::SetAgentProfessionPacket;

using kWeaponSwap = Context::WeaponSwapPacket;

using kWeaponSetChanged = Context::WeaponSetChangedPacket;

using kChangeTarget = Context::ChangeTargetPacket;

using kSendLoadSkillTemplate = Context::SendLoadSkillTemplatePacket;

using kSetRendererValue = Context::SetRendererValuePacket;

using kEffectAdd = Context::EffectAddPacket;

using kAgentSpeechBubble = Context::AgentSpeechBubblePacket;

using kAgentStartCasting = Context::AgentStartCastingPacket;

using kPreStartSalvage = Context::PreStartSalvagePacket;

using kServerActiveQuestChanged = Context::ServerActiveQuestChangedPacket;

using kPrintChatMessage = Context::PrintChatMessagePacket;

using kPartyShowConfirmDialog = Context::PartyShowConfirmDialogPacket;

using kUIPositionChanged = Context::UIPositionChangedPacket;

using kPreferenceFlagChanged = Context::PreferenceFlagChangedPacket;

using kPreferenceValueChanged = Context::PreferenceValueChangedPacket;

using kPreferenceEnumChanged = Context::PreferenceEnumChangedPacket;

using kPartySearchInvite = Context::PartySearchInvitePacket;

using kPostProcessingEffect = Context::PostProcessingEffectPacket;

using kLogout = Context::LogoutPacket;

using KeyAction = Context::KeyActionPacket;

using kMouseClick = Context::MouseClickPacket;

using MouseAction = Context::MouseActionPacket;

template <typename TValue>
using ValueChangedPacket = Context::ValueChangedPacket<TValue>;

using ChatLogLine = Context::ChatLogLinePacket;

using kWriteToChatLog = Context::WriteToChatLogPacket;

using kPlayerChatMessage = Context::PlayerChatMessagePacket;

using kInteractAgent = Context::InteractAgentPacket;

using kSendChangeTarget = Context::SendChangeTargetPacket;

using kGetColor = Context::GetColorPacket;

using kWriteToChatLogWithSender = Context::WriteToChatLogWithSenderPacket;

using kSendLoadSkillbar = Context::SendLoadSkillbarPacket;

using kSendPingWeaponSet = Context::SendPingWeaponSetPacket;

using kSendMoveItem = Context::SendMoveItemPacket;

using MerchantTransactionInfo = Context::MerchantTransactionInfo;

using MerchantQuoteInfo = Context::MerchantQuoteInfo;

using kVendorWindow = Context::VendorWindowPacket;

using kVendorQuote = Context::VendorQuotePacket;

using kVendorItems = Context::VendorItemsPacket;

using kSendMerchantRequestQuote = Context::SendMerchantRequestQuotePacket;

using kSendMerchantTransactItem = Context::SendMerchantTransactItemPacket;

using kSendUseItem = Context::SendUseItemPacket;

using kSendChatMessage = Context::SendChatMessagePacket;

using kLogChatMessage = Context::LogChatMessagePacket;

using kRecvWhisper = Context::RecvWhisperPacket;

using kStartWhisper = Context::StartWhisperPacket;

using kCompassDraw = Context::CompassDrawPacket;

using ButtonMouseActionPacket = Context::ButtonMouseActionPacket;

using kObjectiveAdd = Context::ObjectiveAddPacket;

using kObjectiveComplete = Context::ObjectiveCompletePacket;

using kObjectiveUpdated = Context::ObjectiveUpdatedPacket;

using kItemUpdated = Context::ItemUpdatedPacket;

using kInventorySlotUpdated = Context::InventorySlotUpdatedPacket;

using kSendWorldAction = Context::SendWorldActionPacket;

using kAllyOrGuildMessage = Context::AllyOrGuildMessagePacket;
}

using ArrayByte = GW::GWArray<unsigned char>;
using UIMessageCallback = PY4GW::HookCallback<UIMessage, void*, void*>;
using FrameUIMessageCallback = PY4GW::HookCallback<const Frame*, UIMessage, void*, void*>;
using KeyCallback = PY4GW::HookCallback<uint32_t>;
using CreateUIComponentCallback = std::function<void(CreateUIComponentPacket*)>;

bool Initialize();
void Shutdown();

Frame* GetRootFrame();
Frame* GetFrameById(uint32_t frame_id);
Frame* GetParentFrame(Frame* frame);
Frame* GetChildFrame(Frame* parent, uint32_t child_offset);
Frame* GetChildFrame(Frame* parent, std::initializer_list<uint32_t> child_offsets);
Frame* GetFrameByLabel(const wchar_t* frame_label);
uint32_t GetFrameIDByLabel(const wchar_t* frame_label);
uint32_t GetFrameIDByHash(uint32_t hash);
uint32_t GetChildFrameID(uint32_t parent_hash, std::vector<uint32_t> child_offsets);
uint32_t GetHashByLabel(const wchar_t* frame_label);
uint32_t GetHashByLabel(const std::string& label);
Frame* GetRelatedFrame(Frame* frame, Constants::FrameChild relation_kind, Frame* start_after = nullptr);
Frame* GetRelatedFrameById(uint32_t frame_id, Constants::FrameChild relation_kind, uint32_t start_after_id = 0);
Frame* GetChildFromNameHash(Frame* parent, uint32_t name_hash);
std::vector<uint32_t> GetOverlayFrames();
std::vector<uint32_t> GetPopupFrames();
uint32_t GetFrameLayer(Frame* frame);
bool SetFrameLayer(Frame* frame, uint32_t layer);
bool IsAncestorOf(Frame* frame, Frame* other);
uint32_t GetFrameCode(Frame* frame);
bool GetFrameMinSize(Frame* frame, float* width, float* height);
bool GetFrameClientBorder(Frame* frame, float* left, float* top, float* right, float* bottom);
bool GetFrameClipRect(Frame* frame, float* left, float* top, float* right, float* bottom);
bool GetFramePositionEx(Frame* frame, float* x, float* y, float* w, float* h, uint32_t* flags);
bool GetFrameNativeSize(Frame* frame, float* width, float* height);
void* GetFrameContext(Frame* frame);
uint32_t CreateUIComponent(uint32_t parent_frame_id, uint32_t component_flags, uint32_t tab_index, UIInteractionCallback event_callback, void* wparam, const wchar_t* component_label);
uint32_t CreateUIComponent(uint32_t frame_id, uint32_t component_flags, uint32_t tab_index, UIInteractionCallback event_callback, wchar_t* name_enc, wchar_t* component_label);
bool DestroyUIComponent(Frame* frame);
bool AddFrameUIInteractionCallback(Frame* frame, UIInteractionCallback callback, void* wparam);
bool TriggerFrameRedraw(Frame* frame);
bool SetFrameMargins(Frame* frame, uint32_t flags, float size[4], float input_mask[4], uint32_t type);
bool SelectDropdownOption(Frame* frame, uint32_t value);
Frame* CreateButtonFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* name_enc = nullptr, wchar_t* component_label = nullptr);
Frame* CreateButtonFrame(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* name_enc = nullptr, wchar_t* component_label = nullptr);
Frame* CreateCtlButtonFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* name_enc = nullptr, wchar_t* component_label = nullptr);
Frame* CreateCtlButtonFrame(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* name_enc = nullptr, wchar_t* component_label = nullptr);
Frame* CreateFlatButtonWithClick(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* label_text = nullptr, bool enable_click = false);
Frame* CreateFlatButtonWithClick(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* label_text = nullptr, bool enable_click = false);
Frame* CreateTextButtonFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* caption = nullptr, wchar_t* component_label = nullptr);
Frame* CreateTextButtonFrame(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* caption = nullptr, wchar_t* component_label = nullptr);
Frame* CreateCheckboxFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* name_enc = nullptr, wchar_t* component_label = nullptr);
Frame* CreateCheckboxFrame(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* name_enc = nullptr, wchar_t* component_label = nullptr);
Frame* CreateScrollableFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, void* page_context = nullptr, wchar_t* component_label = nullptr);
Frame* CreateScrollableFrame(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, void* page_context = nullptr, wchar_t* component_label = nullptr);
Frame* CreateTextLabelFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* name_enc = nullptr, wchar_t* component_label = nullptr);
Frame* CreateTextLabelFrame(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* name_enc = nullptr, wchar_t* component_label = nullptr);
Frame* CreateDropdownFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* component_label = nullptr);
Frame* CreateDropdownFrame(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* component_label = nullptr);
Frame* CreateSliderFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* component_label = nullptr);
Frame* CreateSliderFrame(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* component_label = nullptr);
Frame* CreateEditableTextFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* component_label = nullptr);
Frame* CreateEditableTextFrame(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* component_label = nullptr);
Frame* CreateProgressBar(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* component_label = nullptr);
Frame* CreateProgressBar(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* component_label = nullptr);
Frame* CreateTabsFrame(uint32_t parent_frame_id, uint32_t component_flags, uint32_t child_index = 0, wchar_t* component_label = nullptr);
Frame* CreateTabsFrame(Frame* parent, uint32_t component_flags, uint32_t child_index = 0, wchar_t* component_label = nullptr);
bool ButtonClick(Frame* btn_frame);
bool TestMouseAction(uint32_t frame_id, uint32_t current_state, uint32_t wparam = 0, uint32_t lparam = 0);
bool TestMouseClickAction(uint32_t frame_id, uint32_t current_state, uint32_t wparam = 0, uint32_t lparam = 0);
bool SendFrameUIMessage(Frame* frame, UIMessage message_id, void* wparam, void* lparam = nullptr);
bool SendUIMessage(UIMessage message_id, void* wparam = nullptr, void* lparam = nullptr, bool skip_hooks = false);
bool Keydown(ControlAction key, Frame* target = nullptr);
bool Keyup(ControlAction key, Frame* target = nullptr);
bool Keypress(ControlAction key, Frame* target = nullptr);
GW::Constants::Language GetTextLanguage();
uint32_t GetPreference(Constants::EnumPreference pref);
uint32_t GetPreferenceOptions(Constants::EnumPreference pref, uint32_t** options_out = nullptr);
uint32_t GetPreference(Constants::NumberPreference pref);
bool GetPreference(Constants::FlagPreference pref);
wchar_t* GetPreference(Constants::StringPreference pref);
bool SetPreference(Constants::EnumPreference pref, uint32_t value);
bool SetPreference(Constants::NumberPreference pref, uint32_t value);
bool SetPreference(Constants::FlagPreference pref, bool value);
bool SetPreference(Constants::StringPreference pref, wchar_t* value);
bool GetCommandLinePref(const wchar_t* label, wchar_t** out);
bool GetCommandLinePref(const wchar_t* label, uint32_t* out);
bool SetCommandLinePref(const wchar_t* label, wchar_t* value);
bool SetCommandLinePref(const wchar_t* label, uint32_t value);
void SetOpenLinks(bool toggle);
Context::WindowPosition* GetWindowPosition(WindowID window_id);
bool SetWindowVisible(WindowID window_id, bool is_visible);
bool SetWindowPosition(WindowID window_id, Context::WindowPosition* info);
bool DrawOnCompass(unsigned session_id, unsigned point_count, CompassPoint* points);
void LoadSettings(size_t size, uint8_t* data);
ArrayByte* GetSettings();
bool GetIsUIDrawn();
bool GetIsShiftScreenShot();
bool GetIsWorldMapShowing();
bool SetFrameVisible(Frame* frame, bool flag);
bool SetFrameDisabled(Frame* frame, bool flag);
bool SetFrameOpacity(Frame* frame, float opacity, float fade_time = 0.0f);
bool ShowFrame(Frame* frame, bool show);
const wchar_t* GetFrameTitle(Frame* frame);
uint32_t GetParentFrameId(Frame* frame);
float GetFrameOpacity(Frame* frame);
uint32_t GetFrameUserParam(Frame* frame);
bool GetFrameStateBit(Frame* frame, uint32_t bit);
uint32_t GetFrameLimit();
bool SetFrameLimit(uint32_t value);
std::vector<std::tuple<uint32_t, uint32_t, uint32_t, uint32_t>> GetFrameHierarchy();
std::vector<std::pair<uint32_t, uint32_t>> GetFrameCoordsByHash(uint32_t frame_hash);
std::vector<uint32_t> GetFrameArray();
void AsyncDecodeStr(const wchar_t* enc_str, char* buffer, size_t size);
void AsyncDecodeStr(const wchar_t* enc_str, wchar_t* buffer, size_t size);
void AsyncDecodeStr(const wchar_t* enc_str, DecodeStr_Callback callback, void* callback_param = nullptr, GW::Constants::Language language_id = GW::Constants::Language::Unknown);
void AsyncDecodeStr(const wchar_t* enc_str, std::wstring* out, GW::Constants::Language language_id = GW::Constants::Language::Unknown);
bool IsValidEncStr(const wchar_t* enc_str);
bool UInt32ToEncStr(uint32_t value, wchar_t* buffer, size_t count);
uint32_t EncStrToUInt32(const wchar_t* enc_str);
TooltipInfo* GetCurrentTooltip();

void RegisterUIMessageCallback(PY4GW::HookEntry* entry, UIMessage message_id, const UIMessageCallback& callback, int altitude = -0x8000);
void RemoveUIMessageCallback(PY4GW::HookEntry* entry, UIMessage message_id = UIMessage::kNone);
void RegisterFrameUIMessageCallback(PY4GW::HookEntry* entry, UIMessage message_id, const FrameUIMessageCallback& callback, int altitude = -0x8000);
void RemoveFrameUIMessageCallback(PY4GW::HookEntry* entry);
void RegisterKeydownCallback(PY4GW::HookEntry* entry, const KeyCallback& callback);
void RemoveKeydownCallback(PY4GW::HookEntry* entry);
void RegisterKeyupCallback(PY4GW::HookEntry* entry, const KeyCallback& callback);
void RemoveKeyupCallback(PY4GW::HookEntry* entry);
void RegisterCreateUIComponentCallback(PY4GW::HookEntry* entry, const CreateUIComponentCallback& callback, int altitude = -0x8000);
void RemoveCreateUIComponentCallback(PY4GW::HookEntry* entry);
bool InitializeTypedComponentCallbacks();

struct ButtonFrame : Frame {
    static ButtonFrame* Create(uint32_t parent_frame_id, uint32_t flags = 0x300, uint32_t child_offset_id = 0xFF, const wchar_t* button_label = nullptr, const wchar_t* frame_label = nullptr);
    bool GetLabel(const wchar_t** enc_string);
    bool SetLabel(const wchar_t* enc_string);
    bool Click();
    bool MouseAction(packet::ActionState action);
    bool DoubleClick();
};

struct FrameWithValue {
    FrameWithValue() = default;
    virtual ~FrameWithValue() = default;
    FrameWithValue(const FrameWithValue&) = default;
    FrameWithValue(FrameWithValue&&) = default;
    FrameWithValue& operator=(const FrameWithValue&) = default;
    FrameWithValue& operator=(FrameWithValue&&) = default;

    virtual uint32_t GetValue();
    virtual bool SetValue(uint32_t value);
};

struct CheckboxFrame final : ButtonFrame, FrameWithValue {
    static CheckboxFrame* Create(uint32_t parent_frame_id, uint32_t flags = 0x8000, uint32_t child_offset_id = 0xFF, const wchar_t* text_label_enc_string = nullptr, const wchar_t* frame_label = nullptr);
    bool IsChecked();
    bool SetChecked(bool checked);

    uint32_t GetValue() override;
    bool SetValue(uint32_t value) override;
};

struct DropdownFrame final : Frame, FrameWithValue {
    static DropdownFrame* Create(uint32_t parent_frame_id, uint32_t flags = 0x300, uint32_t child_offset_id = 0xFF, const wchar_t* frame_label = nullptr);
    std::vector<uint32_t> GetOptions();
    bool SelectOption(uint32_t value);
    bool SelectIndex(uint32_t index);
    bool AddOption(const wchar_t* label_enc_string, uint32_t value);
    bool GetCount(uint32_t* count);
    bool GetOptionValue(uint32_t index, uint32_t* value);
    bool GetOptionIndex(uint32_t value, uint32_t* index);
    bool GetSelectedIndex(uint32_t* index);
    bool HasValueMapping();

    uint32_t GetValue() override;
    bool SetValue(uint32_t value) override;
};

struct SliderFrame final : Frame, FrameWithValue {
    static SliderFrame* Create(uint32_t parent_frame_id, uint32_t flags = 0, uint32_t child_offset_id = 0xFF, const wchar_t* frame_label = nullptr);
    bool GetValue(uint32_t* selected_value);
    bool SetValue(uint32_t value) override;

    uint32_t GetValue() override;
};

struct EditableTextFrame : Frame {
    static EditableTextFrame* Create(uint32_t parent_frame_id, uint32_t flags = 0, uint32_t child_offset_id = 0xFF, const wchar_t* frame_label = nullptr);
    const wchar_t* GetValue();
    bool SetValue(const wchar_t* value);
    bool SetMaxLength(uint32_t max_length);
    bool IsReadOnly();
    bool SetReadOnly(bool readonly);
};

struct ProgressBar final : ButtonFrame, FrameWithValue {
    static ProgressBar* Create(uint32_t parent_frame_id, uint32_t flags = 0x300, uint32_t child_offset_id = 0xFF, const wchar_t* frame_label = nullptr);
    uint32_t GetValue() override;
    bool SetValue(uint32_t value) override;
    bool SetMax(uint32_t value);
    bool SetColorId(uint32_t color_id);

    bool SetStyle(Constants::ProgressBarStyle style);
};

struct TextLabelFrame : Frame {
    static TextLabelFrame* Create(uint32_t parent_frame_id, uint32_t flags = 0x300, uint32_t child_offset_id = 0xFF, const wchar_t* text_label_enc_string = nullptr, const wchar_t* frame_label = nullptr);
    const wchar_t* GetEncodedLabel();
    const wchar_t* GetDecodedLabel();
    bool SetLabel(const wchar_t* enc_string);
    bool SetFont(uint32_t font_id);
};

struct MultiLineTextLabelFrame final : TextLabelFrame {
    const wchar_t* GetEncodedLabel();
    const wchar_t* GetDecodedLabel();
    bool SetLabel(const wchar_t* enc_string);
};

struct TabsFrame : Frame {
    static TabsFrame* Create(uint32_t parent_frame_id, uint32_t flags = 0x40000, uint32_t child_offset_id = 0xFF, const wchar_t* frame_label = nullptr);
    Frame* AddTab(const wchar_t* tab_name_enc, uint32_t flags, uint32_t child_offset_id, UIInteractionCallback callback, void* wparam = nullptr);
    bool DisableTab(uint32_t tab_id);
    bool EnableTab(uint32_t tab_id);
    bool RemoveTab(uint32_t tab_id);
    bool GetCurrentTabIndex(uint32_t* tab_id);
    bool GetTabFrameId(uint32_t tab_id, uint32_t* frame_id);
    bool GetIsTabEnabled(uint32_t tab_id, uint32_t* is_enabled);
    Frame* GetTabByLabel(const wchar_t* label);
    Frame* GetCurrentTab();
    bool ChooseTab(Frame* tab_frame);
    bool ChooseTab(uint32_t tab_index);
    ButtonFrame* GetTabButton(Frame* tab_frame);
};

struct ScrollableFrame : Frame {
    using SortHandler = Context::ScrollableSortHandler;

    struct ScrollablePageContext {
        uint32_t flags;
        UIInteractionCallback page_callback;
        uint32_t wparam;
    };

    static ScrollableFrame* Create(uint32_t parent_frame_id, uint32_t flags = 0x20000, uint32_t child_offset_id = 0xFF, ScrollablePageContext* context = nullptr, const wchar_t* frame_label = nullptr);
    bool SetSortHandler(SortHandler sort_handler);
    SortHandler GetSortHandler();
    bool ClearItems();
    bool RemoveItem(uint32_t child_offset_id);
    bool AddItem(uint32_t flags, uint32_t child_offset_id, UIInteractionCallback callback);
    uint32_t GetItemFrameId(uint32_t child_offset_id);
    bool GetSelectedValue(uint32_t* selected_value);
    uint32_t GetFirstChildFrameId(uint32_t* offset_of_child_out = nullptr);
    uint32_t GetNextChildFrameId(uint32_t frame_id, uint32_t* offset_of_child_out = nullptr);
    uint32_t GetLastChildFrameId(uint32_t* offset_of_child_out = nullptr);
    uint32_t GetPrevChildFrameId(uint32_t frame_id, uint32_t* offset_of_child_out = nullptr);
    bool GetItemRect(uint32_t child_offset_id, float rect[4]);
    bool GetCount(uint32_t* size);
    uint32_t GetItems(uint32_t* child_frame_id_buffer = nullptr, uint32_t buffer_len = 0);
    Frame* GetPage();
    Frame* SetPage(ScrollablePageContext* context);
};

// uint32_t GetPreference(...);
// bool SetPreference(...);
// bool GetCommandLinePref(...);  // Implemented below.
// bool SetCommandLinePref(...);  // Implemented below.
// bool Default_UICallback(...);  // Deferred: header-declared in legacy UIMgr.h, but no body recovered from GWCA UIMgr.cpp.
// bool IsInControllerMode();     // Deferred: header-declared in legacy UIMgr.h, but no body recovered from GWCA UIMgr.cpp.
// bool IsInControllerCursorMode();  // Deferred: header-declared in legacy UIMgr.h, but no body recovered from GWCA UIMgr.cpp.
// bool SetOpenLinks(bool toggle);
// Frame* CreateFlatButtonWithClick(...);
// Deferred in the fresh UIMgr pass. The only remaining known gaps are legacy declarations
// with no recovered GWCA UIMgr.cpp body.

}  // namespace GW::ui
