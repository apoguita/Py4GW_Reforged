#include "base/error_handling.h"

#include "GW/item/item.h"

#include "base/CrashHandler.h"
#include "base/hooker.h"
#include "base/hook_types.h"
#include "base/logger.h"
#include "base/patterns.h"
#include "base/scanner.h"

#include "GW/ui/ui.h"

#include <array>
#include <atomic>
#include <unordered_map>

namespace GW::Context {
extern SalvageSessionInfo* g_salvage_context;
}

namespace GW::item {

using ItemClickFn = void(__fastcall*)(uint32_t* bag_id, void* edx, ItemClickParam* param);
using DoActionFn = void(__cdecl*)(uint32_t identifier);
using VoidFn = void(__cdecl*)();
using EquipItemFn = void(__cdecl*)(uint32_t item_id, uint32_t agent_id);
using DropItemFn = void(__cdecl*)(uint32_t item_id, uint32_t quantity);
using MoveItemFn = void(__cdecl*)(uint32_t item_id, uint32_t quantity, uint32_t bag_index, uint32_t slot);
using SalvageStartFn = void(__cdecl*)(uint32_t salvage_kit_id, uint32_t salvage_session_id, uint32_t item_id);
using IdentifyItemFn = void(__cdecl*)(uint32_t identification_kit_id, uint32_t item_id);
using PingWeaponSetFn = void(__cdecl*)(uint32_t agent_id, uint32_t weapon_item_id, uint32_t offhand_item_id);
using ChangeGoldFn = void(__cdecl*)(uint32_t character_gold, uint32_t storage_gold);
using ChangeEquipmentVisibilityFn = void(__cdecl*)(uint32_t equipment_state, uint32_t equip_type);
using GetPvPItemUpgradeInfoNameFn = void(__cdecl*)(uint32_t pvp_item_upgrade_id, uint32_t name_or_description, wchar_t** name_out, wchar_t** description_out);

bool ResolveStorageOpenAddress();
bool ResolveItemClickFunction();
bool ResolveUseItemFunction();
bool ResolveEquipItemFunction();
bool ResolveMoveItemFunction();
bool ResolveDropItemFunction();
bool ResolveSalvagePopupUICallback();
bool ResolveDropGoldAndSalvage();
bool ResolveSalvageStartFunction();
bool ResolveIdentifyItemFunction();
bool ResolveDestroyItemFunction();
bool ResolveChangeEquipmentVisibilityFunction();
bool ResolveChangeGoldFunction();
bool ResolveOpenLockedChestFunction();
bool ResolvePingWeaponSetFunction();
bool ResolvePvPItemUpgradeArray();
bool ResolvePvPItemArray();
bool ResolveCompositeModelInfoArray();
bool ResolvePvPItemUpgradeNameFunction();
bool ResolveItemFormulas();

bool Init();
void EnableHooks();
void DisableHooks();
void Exit();

void __fastcall OnItemClick(uint32_t* bag_index, void* edx, ItemClickParam* param);
void __cdecl OnUseItem(uint32_t item_id);
void __cdecl OnMoveItem(uint32_t item_id, uint32_t quantity, uint32_t bag_index, uint32_t slot);
void __cdecl OnPingWeaponSet(uint32_t agent_id, uint32_t weapon_item_id, uint32_t offhand_item_id);
void __cdecl OnChangeGold(uint32_t character_gold, uint32_t storage_gold);
void OnUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void*);
void OnPingWeaponSet_UIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void*);
void OnSalvagePopup_UICallback(ui::InteractionMessage* message, void* wParam, void* lParam);

DoActionFn g_use_item_func = nullptr;
DoActionFn g_use_item_original = nullptr;
EquipItemFn g_equip_item_func = nullptr;
DropItemFn g_drop_item_func = nullptr;
MoveItemFn g_move_item_func = nullptr;
MoveItemFn g_move_item_original = nullptr;
ItemClickFn g_item_click_func = nullptr;
ItemClickFn g_item_click_original = nullptr;
ui::UIInteractionCallback g_salvage_popup_uicallback_func = nullptr;
ui::UIInteractionCallback g_salvage_popup_uicallback_original = nullptr;
DoActionFn g_drop_gold_func = nullptr;
VoidFn g_salvage_session_cancel_func = nullptr;
VoidFn g_salvage_session_complete_func = nullptr;
VoidFn g_salvage_materials_func = nullptr;
SalvageStartFn g_salvage_start_func = nullptr;
IdentifyItemFn g_identify_item_func = nullptr;
DoActionFn g_destroy_item_func = nullptr;
ChangeEquipmentVisibilityFn g_change_equipment_visibility_func = nullptr;
ChangeGoldFn g_change_gold_func = nullptr;
ChangeGoldFn g_change_gold_original = nullptr;
DoActionFn g_open_locked_chest_func = nullptr;
PingWeaponSetFn g_ping_weapon_set_func = nullptr;
PingWeaponSetFn g_ping_weapon_set_original = nullptr;
GetPvPItemUpgradeInfoNameFn g_pvp_item_upgrade_name_func = nullptr;
PY4GW::HookEntry g_ui_message_entry;
const std::array<ui::UIMessage, 3> g_ui_messages_to_hook = {
    ui::UIMessage::kSendUseItem,
    ui::UIMessage::kSendMoveItem,
    ui::UIMessage::kSendPingWeaponSet
};
PY4GW::HookEntry g_on_use_item_entry;
PY4GW::HookEntry g_on_move_item_entry;
PY4GW::HookEntry g_on_ping_weapon_set_entry;
std::unordered_map<PY4GW::HookEntry*, ItemClickCallback> g_item_click_callbacks;
std::atomic<bool> g_initialized = false;

void __fastcall OnItemClick(uint32_t* bag_index, void* edx, ItemClickParam* param) {
    PY4GW::HookBase::EnterHook();
    if (!(bag_index && param)) {
        g_item_click_original(bag_index, edx, param);
        PY4GW::HookBase::LeaveHook();
        return;
    }

    uint32_t slot = param->slot - 2;
    PY4GW::HookStatus status;
    Bag* bag = GetBagByIndex(*bag_index);
    if (IsStorageBag(bag) && !CanAccessXunlaiChest())
        status.blocked = true;
    if (bag) {
        for (auto& it : g_item_click_callbacks) {
            it.second(&status, static_cast<uint32_t>(static_cast<Constants::ItemClickType>(param->type)), slot, bag);
            ++status.altitude;
        }
    }
    if (!status.blocked)
        g_item_click_original(bag_index, edx, param);
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnUseItem(uint32_t item_id) {
    PY4GW::HookBase::EnterHook();
    ui::SendUIMessage(ui::UIMessage::kSendUseItem, reinterpret_cast<void*>(static_cast<uintptr_t>(item_id)));
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnMoveItem(uint32_t item_id, uint32_t quantity, uint32_t bag_index, uint32_t slot) {
    PY4GW::HookBase::EnterHook();
    ui::packet::kSendMoveItem packet = { item_id, quantity, bag_index, slot };
    ui::SendUIMessage(ui::UIMessage::kSendMoveItem, &packet);
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnPingWeaponSet(uint32_t agent_id, uint32_t weapon_item_id, uint32_t offhand_item_id) {
    PY4GW::HookBase::EnterHook();
    const auto packet = ui::packet::kSendPingWeaponSet{agent_id, weapon_item_id, offhand_item_id};
    ui::SendUIMessage(ui::UIMessage::kSendPingWeaponSet, const_cast<ui::packet::kSendPingWeaponSet*>(&packet));
    PY4GW::HookBase::LeaveHook();
}

void __cdecl OnChangeGold(uint32_t character_gold, uint32_t storage_gold) {
    PY4GW::HookBase::EnterHook();
    if (CanAccessXunlaiChest())
        g_change_gold_original(character_gold, storage_gold);
    PY4GW::HookBase::LeaveHook();
}

void OnUIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void*) {
    switch (message_id) {
    case ui::UIMessage::kSendUseItem: {
        PY4GW_ASSERT(wparam);
        if (!status->blocked) {
            g_use_item_original(static_cast<uint32_t>(reinterpret_cast<uintptr_t>(wparam)));
        }
        break;
    }
    case ui::UIMessage::kSendMoveItem: {
        PY4GW_ASSERT(wparam);
        const auto* packet = static_cast<ui::packet::kSendMoveItem*>(wparam);
        if (!status->blocked && !CanAccessXunlaiChest()) {
            const auto* item = GetItemById(packet->item_id);
            const auto* bag = GetBagByIndex(packet->bag_id);
            if (IsStorageItem(item) || IsStorageBag(bag))
                status->blocked = true;
        }
        if (!status->blocked) {
            g_move_item_original(packet->item_id, packet->quantity, packet->bag_id, packet->slot);
        }
        break;
    }
    case ui::UIMessage::kSendPingWeaponSet: {
        PY4GW_ASSERT(wparam);
        const auto* packet = static_cast<ui::packet::kSendPingWeaponSet*>(wparam);
        if (!status->blocked) {
            g_ping_weapon_set_original(packet->agent_id, packet->weapon_item_id, packet->offhand_item_id);
        }
        break;
    }
    default:
        break;
    }
}

void OnPingWeaponSet_UIMessage(PY4GW::HookStatus* status, ui::UIMessage message_id, void* wparam, void*) {
    PY4GW_ASSERT(message_id == ui::UIMessage::kSendPingWeaponSet && wparam);
    const auto* packet = static_cast<ui::packet::kSendPingWeaponSet*>(wparam);
    if (!status->blocked) {
        g_ping_weapon_set_original(packet->agent_id, packet->weapon_item_id, packet->offhand_item_id);
    }
}

void OnSalvagePopup_UICallback(ui::InteractionMessage* message, void* wParam, void* lParam) {
    PY4GW::HookBase::EnterHook();
    g_salvage_popup_uicallback_original(message, wParam, lParam);
    switch (message->message_id) {
    case ui::UIMessage::kInitFrame:
        Context::g_salvage_context = *reinterpret_cast<SalvageSessionInfo**>(message->wParam);
        break;
    case ui::UIMessage::kDestroyFrame:
        Context::g_salvage_context = nullptr;
        break;
    default:
        break;
    }
    PY4GW::HookBase::LeaveHook();
}

bool Init() {
    CrashContextScope context("startup", "item", "init");
    if (!ResolveStorageOpenAddress() ||
        !ResolveItemClickFunction() ||
        !ResolveUseItemFunction() ||
        !ResolveEquipItemFunction() ||
        !ResolveMoveItemFunction() ||
        !ResolveDropItemFunction() ||
        !ResolveSalvagePopupUICallback() ||
        !ResolveDropGoldAndSalvage() ||
        !ResolveSalvageStartFunction() ||
        !ResolveIdentifyItemFunction() ||
        !ResolveDestroyItemFunction() ||
        !ResolveChangeEquipmentVisibilityFunction() ||
        !ResolveChangeGoldFunction() ||
        !ResolveOpenLockedChestFunction() ||
        !ResolvePingWeaponSetFunction() ||
        !ResolvePvPItemUpgradeArray() ||
        !ResolvePvPItemArray() ||
        !ResolveCompositeModelInfoArray() ||
        !ResolvePvPItemUpgradeNameFunction() ||
        !ResolveItemFormulas()) {
        return false;
    }

    if (g_salvage_popup_uicallback_func) {
        Logger::AssertHook("SalvagePopup_UICallback",
            PY4GW::HookBase::CreateHook(
                reinterpret_cast<void**>(&g_salvage_popup_uicallback_func),
                reinterpret_cast<void*>(&OnSalvagePopup_UICallback),
                reinterpret_cast<void**>(&g_salvage_popup_uicallback_original)),
            "item");
    }
    if (g_item_click_func) {
        Logger::AssertHook("ItemClick_Func",
            PY4GW::HookBase::CreateHook(
                reinterpret_cast<void**>(&g_item_click_func),
                reinterpret_cast<void*>(&OnItemClick),
                reinterpret_cast<void**>(&g_item_click_original)),
            "item");
    }
    if (g_ping_weapon_set_func) {
        Logger::AssertHook("PingWeaponSet_Func",
            PY4GW::HookBase::CreateHook(
                reinterpret_cast<void**>(&g_ping_weapon_set_func),
                reinterpret_cast<void*>(&OnPingWeaponSet),
                reinterpret_cast<void**>(&g_ping_weapon_set_original)),
            "item");
    }
    if (g_move_item_func) {
        Logger::AssertHook("MoveItem_Func",
            PY4GW::HookBase::CreateHook(
                reinterpret_cast<void**>(&g_move_item_func),
                reinterpret_cast<void*>(&OnMoveItem),
                reinterpret_cast<void**>(&g_move_item_original)),
            "item");
    }
    if (g_use_item_func) {
        Logger::AssertHook("UseItem_Func",
            PY4GW::HookBase::CreateHook(
                reinterpret_cast<void**>(&g_use_item_func),
                reinterpret_cast<void*>(&OnUseItem),
                reinterpret_cast<void**>(&g_use_item_original)),
            "item");
    }
    if (g_change_gold_func) {
        Logger::AssertHook("ChangeGold_Func",
            PY4GW::HookBase::CreateHook(
                reinterpret_cast<void**>(&g_change_gold_func),
                reinterpret_cast<void*>(&OnChangeGold),
                reinterpret_cast<void**>(&g_change_gold_original)),
            "item");
    }
    return true;
}

void EnableHooks() {
    CrashContextScope context("runtime", "item", "enable_hooks");
    if (g_salvage_popup_uicallback_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_salvage_popup_uicallback_func));
    }
    if (g_item_click_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_item_click_func));
    }
    if (g_ping_weapon_set_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_ping_weapon_set_func));
    }
    if (g_move_item_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_move_item_func));
    }
    if (g_use_item_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_use_item_func));
    }
    if (g_change_gold_func) {
        PY4GW::HookBase::EnableHooks(reinterpret_cast<void*>(g_change_gold_func));
    }
    for (const auto ui_message : g_ui_messages_to_hook) {
        ui::RegisterUIMessageCallback(&g_ui_message_entry, ui_message, &OnUIMessage, 0x1);
    }
}

void DisableHooks() {
    CrashContextScope context("shutdown", "item", "disable_hooks");
    if (g_salvage_popup_uicallback_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_salvage_popup_uicallback_func));
    }
    if (g_item_click_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_item_click_func));
    }
    if (g_ping_weapon_set_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_ping_weapon_set_func));
    }
    if (g_move_item_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_move_item_func));
    }
    if (g_use_item_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_use_item_func));
    }
    if (g_change_gold_func) {
        PY4GW::HookBase::DisableHooks(reinterpret_cast<void*>(g_change_gold_func));
    }
    ui::RemoveUIMessageCallback(&g_ui_message_entry);
}

void Exit() {
    CrashContextScope context("shutdown", "item", "exit");
    if (g_salvage_popup_uicallback_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_salvage_popup_uicallback_func));
    }
    if (g_item_click_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_item_click_func));
    }
    if (g_ping_weapon_set_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_ping_weapon_set_func));
    }
    if (g_move_item_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_move_item_func));
    }
    if (g_use_item_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_use_item_func));
    }
    if (g_change_gold_func) {
        PY4GW::HookBase::RemoveHook(reinterpret_cast<void*>(g_change_gold_func));
    }

    g_use_item_func = nullptr;
    g_use_item_original = nullptr;
    g_equip_item_func = nullptr;
    g_drop_item_func = nullptr;
    g_move_item_func = nullptr;
    g_move_item_original = nullptr;
    g_item_click_func = nullptr;
    g_item_click_original = nullptr;
    g_salvage_popup_uicallback_func = nullptr;
    g_salvage_popup_uicallback_original = nullptr;
    g_drop_gold_func = nullptr;
    g_salvage_session_cancel_func = nullptr;
    g_salvage_session_complete_func = nullptr;
    g_salvage_materials_func = nullptr;
    g_salvage_start_func = nullptr;
    g_identify_item_func = nullptr;
    g_destroy_item_func = nullptr;
    g_change_equipment_visibility_func = nullptr;
    g_change_gold_func = nullptr;
    g_change_gold_original = nullptr;
    g_open_locked_chest_func = nullptr;
    g_ping_weapon_set_func = nullptr;
    g_ping_weapon_set_original = nullptr;
    g_pvp_item_upgrade_name_func = nullptr;
    Context::g_salvage_context = nullptr;
    g_item_click_callbacks.clear();
}

bool Initialize() {
    CrashContextScope context("startup", "item", "initialize");
    if (g_initialized) {
        return true;
    }

    PY4GW_ASSERT(PY4GW::Scanner::Initialize());
    PY4GW_ASSERT(PY4GW::Patterns::Initialize());

    PY4GW::HookBase::Initialize();
    if (!Init()) {
        Exit();
        PY4GW::HookBase::Deinitialize();
        return false;
    }

    EnableHooks();
    g_initialized = true;
    return true;
}

void Shutdown() {
    CrashContextScope context("shutdown", "item", "shutdown");
    if (!g_initialized) {
        return;
    }

    DisableHooks();
    Exit();
    PY4GW::HookBase::Deinitialize();
    g_initialized = false;
}

}  // namespace GW::item
