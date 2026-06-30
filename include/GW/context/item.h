#pragma once

#include "base/error_handling.h"

#include "GW/common/constants/constants.h"
#include "GW/common/constants/item_ids.h"
#include "GW/common/gw_array.h"

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace GW::Context {

    struct Item;
    using ItemArray = GW::GWArray<Item*>;

    struct DyeInfo {
        uint8_t dye_tint;
        Constants::DyeColor dye1 : 4;
        Constants::DyeColor dye2 : 4;
        Constants::DyeColor dye3 : 4;
        Constants::DyeColor dye4 : 4;
    };
    static_assert(sizeof(DyeInfo) == 0x3, "DyeInfo size mismatch");

    struct ItemData {
        uint32_t model_file_id = 0;
        GW::Constants::ItemType type = (GW::Constants::ItemType)0xff;
        GW::Context::DyeInfo dye = {};
        uint32_t value = 0;
        uint32_t interaction = 0;
    };
    static_assert(sizeof(ItemData) == 0x10, "ItemData size mismatch");

    struct MaterialCost {
        GW::Constants::MaterialSlot material;
        uint32_t amount;
        uint32_t h0008;
        uint32_t h000c;
    };
    static_assert(sizeof(MaterialCost) == 0x10, "MaterialCost size mismatch");

    struct ItemFormula {
        uint32_t h0000;
        uint32_t gold_cost;
        uint32_t skill_point_cost;
        uint32_t material_cost_count;
        MaterialCost* material_cost_buffer; // NB: The game stores a cached array of material amounts that the player has in inventory; we don't care about it though!
    };
    static_assert(sizeof(ItemFormula) == 0x14, "ItemFormula size mismatch");

    struct Bag { // total: 0x28/40
        /* +h0000 */ GW::Constants::BagType bag_type;
        /* +h0004 */ uint32_t index;
        /* +h0008 */ uint32_t _unknown0;
        /* +h000C */ uint32_t container_item;
        /* +h0010 */ uint32_t items_count;
        /* +h0014 */ Bag* bag_array;
        /* +h0018 */ ItemArray items;

        bool IsInventoryBag()       const { return bag_type == GW::Constants::BagType::Inventory; }
        bool IsStorageBag()         const { return bag_type == GW::Constants::BagType::Storage; }
        bool IsMaterialStorage()    const { return bag_type == GW::Constants::BagType::MaterialStorage; }

        static const size_t npos = (size_t)-1;

        size_t find_dye(uint32_t model_id, DyeInfo extra_id, size_t pos) const;
        size_t find1(uint32_t model_id, size_t pos) const;
        size_t find2(const Item* item, size_t pos) const;

        [[nodiscard]] Constants::Bag bag_id() const
        {
            return static_cast<Constants::Bag>(index + 1);
        }
    };
    static_assert(sizeof(Bag) == 0x28, "Bag size mismatch");

    struct ItemModifier {
        uint32_t mod = 0;

        uint32_t identifier() const { return mod >> 16; }
        uint32_t arg1() const { return (mod & 0x0000FF00) >> 8; }
        uint32_t arg2() const { return (mod & 0x000000FF); }
        uint32_t arg() const { return (mod & 0x0000FFFF); }
        operator bool() const { return mod != 0; }
    };
    static_assert(sizeof(ItemModifier) == 0x4, "ItemModifier size mismatch");

    struct Item { // total: 0x54/84
        /* +h0000 */ uint32_t       item_id;
        /* +h0004 */ uint32_t       agent_id;
        /* +h0008 */ Bag* bag_equipped; // Only valid if Item is a equipped Bag
        /* +h000C */ Bag* bag;
        /* +h0010 */ ItemModifier* mod_struct; // Pointer to an array of mods.
        /* +h0014 */ uint32_t       mod_struct_size; // Size of this array.
        /* +h0018 */ wchar_t* customized;
        /* +h001C */ uint32_t       model_file_id;
        /* +h0020 */ GW::Constants::ItemType        type;
        /* +h0021 */ DyeInfo        dye;
        /* +h0024 */ uint16_t       value;
        /* +h0026 */ uint16_t       h0026;
        /* +h0028 */ uint32_t       interaction;
        /* +h002C */ uint32_t       model_id;
        /* +h0030 */ wchar_t* info_string;
        /* +h0034 */ wchar_t* name_enc;
        /* +h0038 */ wchar_t* complete_name_enc; // with color, quantity, etc.
        /* +h003C */ wchar_t* single_item_name; // with color, w/o quantity, named as single item
        /* +h0040 */ uint32_t       h0040[2];
        /* +h0048 */ uint16_t       item_formula;
        /* +h004A */ uint8_t        is_material_salvageable; // Only valid for type 11 (Materials)
        /* +h004B */ uint8_t        h004B; // probably used for quantity extension for new material storage
        /* +h004C */ uint16_t       quantity;
        /* +h004E */ uint8_t        equipped;
        /* +h004F */ uint8_t        profession;
        /* +h0050 */ uint8_t        slot;

        bool GetIsStackable() const { return (interaction & 0x80000) != 0; }
        bool GetIsInscribable() const { return (interaction & 0x08000000) != 0; }
        bool GetIsMaterial() const;
        bool GetIsZcoin() const;
        ItemModifier* GetModifier(uint32_t identifier) const;
    };
    static_assert(sizeof(Item) == 0x54, "Item size mismatch");

    struct WeaponSet { // total: 0x8/8
        /* +h0000 */ Item* weapon;
        /* +h0004 */ Item* offhand;
    };
    static_assert(sizeof(WeaponSet) == 0x8, "WeaponSet size mismatch");

    struct Inventory { // total: 0x98/152
        union {
            /* +h0000 */ Bag* bags[23];
            struct {
                /* +h0000 */ Bag* unused_bag;
                /* +h0004 */ Bag* backpack;
                /* +h0008 */ Bag* belt_pouch;
                /* +h000C */ Bag* bag1;
                /* +h0010 */ Bag* bag2;
                /* +h0014 */ Bag* equipment_pack;
                /* +h0018 */ Bag* material_storage;
                /* +h001C */ Bag* unclaimed_items;
                /* +h0020 */ Bag* storage1;
                /* +h0024 */ Bag* storage2;
                /* +h0028 */ Bag* storage3;
                /* +h002C */ Bag* storage4;
                /* +h0030 */ Bag* storage5;
                /* +h0034 */ Bag* storage6;
                /* +h0038 */ Bag* storage7;
                /* +h003C */ Bag* storage8;
                /* +h0040 */ Bag* storage9;
                /* +h0044 */ Bag* storage10;
                /* +h0048 */ Bag* storage11;
                /* +h004C */ Bag* storage12;
                /* +h0050 */ Bag* storage13;
                /* +h0054 */ Bag* storage14;
                /* +h0058 */ Bag* equipped_items;
            };
        };
        /* +h005C */ Item* bundle;
        /* +h0060 */ uint32_t storage_panes_unlocked;
        union {
            /* +h0064 */ WeaponSet weapon_sets[4];
            struct {
                /* +h0064 */ Item* weapon_set0;
                /* +h0068 */ Item* offhand_set0;
                /* +h006C */ Item* weapon_set1;
                /* +h0070 */ Item* offhand_set1;
                /* +h0074 */ Item* weapon_set2;
                /* +h0078 */ Item* offhand_set2;
                /* +h007C */ Item* weapon_set3;
                /* +h0080 */ Item* offhand_set3;
            };
        };
        /* +h0084 */ uint32_t active_weapon_set;
        /* +h0088 */ uint32_t h0088[2];
        /* +h0090 */ uint32_t gold_character;
        /* +h0094 */ uint32_t gold_storage;
    };
    static_assert(sizeof(Inventory) == 0x98, "Inventory size mismatch");

    struct PvPItemUpgradeInfo {
        uint32_t file_id;
        uint32_t name_id;
        uint32_t upgrade_type; // Axe, Bow, Inscription
        uint32_t campaign_id;
        uint32_t interaction;
        uint32_t is_dev; // boolean; if 1, then don't use in-game
        uint32_t profession; // if 0xb then is for all professions
        uint32_t h0018;
        uint32_t mod_struct_size;
        uint32_t* mod_struct;
    };
    static_assert(sizeof(PvPItemUpgradeInfo) == 0x28, "PvPItemUpgradeInfo size mismatch");

    struct PvPItemInfo {
        uint32_t unk[9];
    };
    static_assert(sizeof(PvPItemInfo) == 0x24, "PvPItemInfo size mismatch");

    struct CompositeModelInfo {
        uint32_t class_flags;
        uint32_t file_ids[11];
    };
    static_assert(sizeof(CompositeModelInfo) == 0x30, "CompositeModelInfo size mismatch");

    struct SalvageSessionInfo {
        void* vtable;
        uint32_t frame_id;
        uint32_t item_id;
        uint32_t salvagable_1; // Prefix
        uint32_t salvagable_2; // Suffix
        uint32_t salvagable_3; // Inscription
        uint32_t chosen_salvagable; // 3 for materials
        uint32_t h001c;
        uint32_t kit_id;
    };
    static_assert(sizeof(SalvageSessionInfo) == 0x24, "SalvageSessionInfo size mismatch");

    struct ItemClickParam {
        uint32_t unk0;
        uint32_t slot;
        uint32_t type;
    };
    static_assert(sizeof(ItemClickParam) == 0xC, "ItemClickParam size mismatch");

    using MerchItemArray = GW::GWArray<uint32_t>;

    struct InventoryTableEntry {
        uint32_t stride;
        uint32_t end;
        GW::Context::Inventory* start;
    };
    static_assert(sizeof(InventoryTableEntry) == 0xC, "InventoryTableEntry size mismatch");

    struct ItemContext { // total: 0x10C/268 BYTEs
        /* +h0000 */ GW::GWArray<void*> h0000;
        /* +h0010 */ GW::GWArray<void*> h0010;
        /* +h0020 */ uint32_t h0020;
        /* +h0024 */ GW::GWArray<Bag*> bags_array;
        /* +h0034 */ uint32_t h0034;
        /* +h0038 */ uint32_t h0038;
        /* +h003C */ uint32_t h003C;
        /* +h0040 */ GW::GWArray<void*> h0040;
        /* +h0050 */ GW::GWArray<void*> h0050;
        /* +h0060 */ uint32_t h0060;
        /* +h0064 */ uint32_t h0064;
        /* +h0068 */ uint32_t h0068;
        /* +h006C */ uint32_t h006C;
        /* +h0070 */ uint32_t h0070;
        /* +h0074 */ uint32_t h0074;
        /* +h0078 */ uint32_t h0078;
        /* +h007C */ uint32_t h007C;
        /* +h0080 */ uint32_t h0080;
        /* +h0084 */ uint32_t h0084;
        /* +h0088 */ uint32_t h0088;
        /* +h008C */ uint32_t h008C;
        /* +h0090 */ uint32_t h0090;
        /* +h0094 */ uint32_t h0094;
        /* +h0098 */ uint32_t h0098;
        /* +h009C */ uint32_t h009C;
        /* +h00A0 */ uint32_t h00A0;
        /* +h00A4 */ uint32_t h00A4;
        /* +h00A8 */ uint32_t h00A8;
        /* +h00AC */ uint32_t h00AC;
        /* +h00B0 */ uint32_t h00B0;
        /* +h00B4 */ uint32_t h00B4;
        /* +h00B8 */ GW::GWArray<Item*> item_array;
        /* +h00C8 */ uint32_t h00C8;
        /* +h00CC */ uint32_t h00CC;
        /* +h00D0 */ uint32_t h00D0;
        /* +h00D4 */ uint32_t h00D4;
        /* +h00D8 */ uint32_t h00D8;
        /* +h00DC */ uint32_t h00DC;
        /* +h00E0 */ uint32_t h00E0;
        /* +h00E4 */ GW::GWArray<InventoryTableEntry> inventory_table;
        /* +h00F4 */ uint32_t h00F4;
        /* +h00F8 */ Inventory* inventory;
        /* +h00FC */ GW::GWArray<void*> h00FC;
    };

    static_assert(offsetof(ItemContext, bags_array) == 0x24, "ItemContext::bags_array offset mismatch");
    static_assert(offsetof(ItemContext, item_array) == 0xB8, "ItemContext::item_array offset mismatch");
    static_assert(offsetof(ItemContext, inventory_table) == 0xE4, "ItemContext::inventory_table offset mismatch");
    static_assert(offsetof(ItemContext, inventory) == 0xF8, "ItemContext::inventory offset mismatch");
    static_assert(sizeof(ItemContext) == 0x10C, "ItemContext size mismatch");

    ItemArray* GetItemArray();
    Inventory* GetInventory();
    Bag** GetBagArray();
    uint32_t* GetStorageOpenAddress();
    GW::GWArray<PvPItemUpgradeInfo>* GetPvPItemUpgradeArray();
    GW::GWArray<PvPItemInfo>* GetPvPItemInfoArray();
    GW::GWArray<CompositeModelInfo>* GetCompositeModelInfoArrayPtr();
    ItemFormula* GetItemFormulas();
    uint32_t GetItemFormulaCount();

}  // namespace GW::Context
