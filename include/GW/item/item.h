#pragma once

#include "base/hook_types.h"
#include "GW/common/constants/constants.h"
#include "GW/context/item.h"

#include <cstdint>
#include <string>

namespace GW::item {

using Item = Context::Item;
using ItemArray = Context::ItemArray;
using Bag = Context::Bag;
using Inventory = Context::Inventory;
using SalvageSessionInfo = Context::SalvageSessionInfo;
using PvPItemUpgradeInfo = Context::PvPItemUpgradeInfo;
using PvPItemInfo = Context::PvPItemInfo;
using CompositeModelInfo = Context::CompositeModelInfo;
using ItemFormula = Context::ItemFormula;
using ItemModifier = Context::ItemModifier;

using PvPItemUpgradeArray = GW::GWArray<Context::PvPItemUpgradeInfo>;
using PvPItemInfoArray = GW::GWArray<Context::PvPItemInfo>;
using CompositeModelInfoArray = GW::GWArray<Context::CompositeModelInfo>;
using ItemClickParam = Context::ItemClickParam;
using ItemClickCallback = PY4GW::HookCallback<uint32_t, uint32_t, Bag*>;

bool Initialize();
void Shutdown();

Bag* GetBag(Constants::Bag bag_id);
Bag* GetBagByIndex(uint32_t bag_index);
Item* GetItemBySlot(const Bag* bag, uint32_t slot);
Item* GetHoveredItem();
Item* GetItemById(uint32_t item_id);
bool UseItem(const Item* item);
bool EquipItem(const Item* item, uint32_t agent_id = 0);
bool DropItem(const Item* item, uint32_t quantity);
bool PingWeaponSet(uint32_t agent_id, uint32_t weapon_item_id, uint32_t offhand_item_id);
bool MoveItem(const Item* from, Constants::Bag bag_id, uint32_t slot, uint32_t quantity = 0);
bool MoveItem(const Item* from, const Bag* bag, uint32_t slot, uint32_t quantity = 0);
bool MoveItem(const Item* from, const Item* to, uint32_t quantity = 0);
bool UseItemByModelId(uint32_t model_id, int bag_start = 1, int bag_end = 4);
uint32_t CountItemByModelId(uint32_t model_id, int bag_start = 1, int bag_end = 4);
Item* GetItemByModelId(uint32_t model_id, int bag_start = 1, int bag_end = 4);
Item* GetItemByModelIdAndModifiers(uint32_t model_id, const ItemModifier* modifiers, uint32_t modifiers_len, int bag_start = 1, int bag_end = 4);
uint32_t GetGoldAmountOnCharacter();
uint32_t GetGoldAmountInStorage();
bool DropGold(uint32_t amount = 1);
uint32_t DepositGold(uint32_t amount = 0);
uint32_t WithdrawGold(uint32_t amount = 0);
bool ChangeGold(uint32_t character_gold, uint32_t storage_gold);
bool SalvageStart(uint32_t salvage_kit_id, uint32_t item_id);
bool IdentifyItem(uint32_t identification_kit_id, uint32_t item_id);
bool SalvageSessionCancel();
bool SalvageSessionDone();
bool DestroyItem(uint32_t item_id);
bool SalvageMaterials();
void OpenXunlaiWindow(bool anniversary_pane_unlocked = true);
Constants::StoragePane GetStoragePage();
bool GetIsStorageOpen();
void AsyncGetItemName(const Item* item, std::wstring& name);
void RegisterItemClickCallback(PY4GW::HookEntry* entry, const ItemClickCallback& callback);
void RemoveItemClickCallback(PY4GW::HookEntry* entry);
Constants::MaterialSlot GetMaterialSlot(const Item* item);
uint32_t GetEquipmentVisibilityState();
Constants::EquipmentStatus GetEquipmentVisibility(Constants::EquipmentType type);
bool SetEquipmentVisibility(Constants::EquipmentType type, Constants::EquipmentStatus state);
uint32_t GetMaterialStorageStackSize();
const PvPItemUpgradeInfo* GetPvPItemUpgrade(uint32_t pvp_item_upgrade_idx);
const PvPItemUpgradeArray& GetPvPItemUpgradesArray();
const PvPItemInfo* GetPvPItemInfo(uint32_t pvp_item_idx);
const PvPItemInfoArray& GetPvPItemInfoArray();
const CompositeModelInfo* GetCompositeModelInfo(uint32_t model_file_id);
const CompositeModelInfoArray& GetCompositeModelInfoArray();
bool GetPvPItemUpgradeEncodedName(uint32_t pvp_item_upgrade_idx, wchar_t** out);
bool GetPvPItemUpgradeEncodedDescription(uint32_t pvp_item_upgrade_idx, wchar_t** out);
const ItemFormula* GetItemFormula(const Item* item);
bool PickUpItem(const Item* item, uint32_t call_target = 0);
bool CanAccessXunlaiChest();
bool IsStorageBag(const Bag* bag);
bool IsStorageItem(const Item* item);
bool CanInteractWithItem(const Item* item);

}  // namespace GW::item

namespace GW {
namespace Items = item;
}
