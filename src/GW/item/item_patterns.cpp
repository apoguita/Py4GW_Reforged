#include "base/error_handling.h"

#include "base/CrashHandler.h"
#include "base/memory_patcher.h"
#include "base/patterns.h"

#include "GW/item/item.h"
#include "GW/ui/ui.h"

namespace GW::Context {
extern uint32_t* g_storage_open_addr;
extern GW::GWArray<PvPItemUpgradeInfo> g_unlocked_pvp_item_upgrade_array;
extern GW::GWArray<PvPItemInfo> g_pvp_item_array;
extern GW::GWArray<CompositeModelInfo>* g_composite_model_info_array;
extern ItemFormula* g_item_formulas;
extern uint32_t g_item_formula_count;
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

extern DoActionFn g_use_item_func;
extern EquipItemFn g_equip_item_func;
extern DropItemFn g_drop_item_func;
extern MoveItemFn g_move_item_func;
extern ItemClickFn g_item_click_func;
extern ui::UIInteractionCallback g_salvage_popup_uicallback_func;
extern DoActionFn g_drop_gold_func;
extern VoidFn g_salvage_session_cancel_func;
extern VoidFn g_salvage_session_complete_func;
extern VoidFn g_salvage_materials_func;
extern SalvageStartFn g_salvage_start_func;
extern IdentifyItemFn g_identify_item_func;
extern DoActionFn g_destroy_item_func;
extern ChangeEquipmentVisibilityFn g_change_equipment_visibility_func;
extern ChangeGoldFn g_change_gold_func;
extern DoActionFn g_open_locked_chest_func;
extern PingWeaponSetFn g_ping_weapon_set_func;
extern GetPvPItemUpgradeInfoNameFn g_pvp_item_upgrade_name_func;

bool ResolveStorageOpenAddress() {
    CrashContextScope context("startup", "item", "resolve_storage_open");
    return PY4GW::Patterns::Resolve("item.storage_open_addr", &Context::g_storage_open_addr);
}

bool ResolveItemClickFunction() {
    CrashContextScope context("startup", "item", "resolve_item_click");
    return PY4GW::Patterns::Resolve("item.item_click_func", &g_item_click_func);
}

bool ResolveUseItemFunction() {
    CrashContextScope context("startup", "item", "resolve_use_item");
    return PY4GW::Patterns::Resolve("item.use_item_func", &g_use_item_func);
}

bool ResolveEquipItemFunction() {
    CrashContextScope context("startup", "item", "resolve_equip_item");
    return PY4GW::Patterns::Resolve("item.equip_item_func", &g_equip_item_func);
}

bool ResolveMoveItemFunction() {
    CrashContextScope context("startup", "item", "resolve_move_item");
    return PY4GW::Patterns::Resolve("item.move_item_func", &g_move_item_func);
}

bool ResolveDropItemFunction() {
    CrashContextScope context("startup", "item", "resolve_drop_item");
    return PY4GW::Patterns::Resolve("item.drop_item_func", &g_drop_item_func);
}

bool ResolveSalvagePopupUICallback() {
    CrashContextScope context("startup", "item", "resolve_salvage_popup");
    return PY4GW::Patterns::Resolve("item.salvage_popup_uicallback_func", &g_salvage_popup_uicallback_func);
}

bool ResolveDropGoldAndSalvage() {
    CrashContextScope context("startup", "item", "resolve_drop_gold_and_salvage");
    return PY4GW::Patterns::Resolve("item.drop_gold_func", &g_drop_gold_func) &&
        PY4GW::Patterns::Resolve("item.salvage_session_cancel_func", &g_salvage_session_cancel_func) &&
        PY4GW::Patterns::Resolve("item.salvage_session_complete_func", &g_salvage_session_complete_func) &&
        PY4GW::Patterns::Resolve("item.salvage_materials_func", &g_salvage_materials_func);
}

bool ResolveSalvageStartFunction() {
    CrashContextScope context("startup", "item", "resolve_salvage_start");
    return PY4GW::Patterns::Resolve("item.salvage_start_func", &g_salvage_start_func);
}

bool ResolveIdentifyItemFunction() {
    CrashContextScope context("startup", "item", "resolve_identify_item");
    return PY4GW::Patterns::Resolve("item.identify_item_func", &g_identify_item_func);
}

bool ResolveDestroyItemFunction() {
    CrashContextScope context("startup", "item", "resolve_destroy_item");
    return PY4GW::Patterns::Resolve("item.destroy_item_func", &g_destroy_item_func);
}

bool ResolveChangeEquipmentVisibilityFunction() {
    CrashContextScope context("startup", "item", "resolve_change_equipment_visibility");
    return PY4GW::Patterns::Resolve("item.change_equipment_visibility_func", &g_change_equipment_visibility_func);
}

bool ResolveChangeGoldFunction() {
    CrashContextScope context("startup", "item", "resolve_change_gold");
    return PY4GW::Patterns::Resolve("item.change_gold_func", &g_change_gold_func);
}

bool ResolveOpenLockedChestFunction() {
    CrashContextScope context("startup", "item", "resolve_open_locked_chest");
    return PY4GW::Patterns::Resolve("item.open_locked_chest_func", &g_open_locked_chest_func);
}

bool ResolvePingWeaponSetFunction() {
    CrashContextScope context("startup", "item", "resolve_ping_weapon_set");
    return PY4GW::Patterns::Resolve("item.ping_weapon_set_func", &g_ping_weapon_set_func);
}

bool ResolvePvPItemUpgradeArray() {
    CrashContextScope context("startup", "item", "resolve_pvp_item_upgrade_array");
    return PY4GW::Patterns::Resolve("item.pvp_item_upgrade_array_buffer", &Context::g_unlocked_pvp_item_upgrade_array.m_buffer) &&
        PY4GW::Patterns::Resolve("item.pvp_item_upgrade_array_size", &Context::g_unlocked_pvp_item_upgrade_array.m_size);
}

bool ResolvePvPItemArray() {
    CrashContextScope context("startup", "item", "resolve_pvp_item_array");
    return PY4GW::Patterns::Resolve("item.pvp_item_array_buffer", &Context::g_pvp_item_array.m_buffer) &&
        PY4GW::Patterns::Resolve("item.pvp_item_array_size", &Context::g_pvp_item_array.m_size);
}

bool ResolveCompositeModelInfoArray() {
    CrashContextScope context("startup", "item", "resolve_composite_model_info_array");
    return PY4GW::Patterns::Resolve("item.composite_model_info_array", &Context::g_composite_model_info_array);
}

bool ResolvePvPItemUpgradeNameFunction() {
    CrashContextScope context("startup", "item", "resolve_pvp_item_upgrade_name");
    return PY4GW::Patterns::Resolve("item.pvp_item_upgrade_name_func", &g_pvp_item_upgrade_name_func);
}

bool ResolveItemFormulas() {
    CrashContextScope context("startup", "item", "resolve_item_formulas");
    return PY4GW::Patterns::Resolve("item.item_formulas_addr", &Context::g_item_formulas) &&
        PY4GW::Patterns::Resolve("item.item_formulas_count", &Context::g_item_formula_count);
}

}  // namespace GW::item
