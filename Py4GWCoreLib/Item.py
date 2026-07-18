from typing import Iterable, Optional, Type

import PyItem
import PyInventory

from enum import Enum, IntEnum

from Py4GWCoreLib.enums_src.GameData_enums import Attribute, DyeColor, Gender
from Py4GWCoreLib.enums_src.Item_enums import DAMAGE_RANGES, ItemType, Rarity
from Py4GWCoreLib import mods_core
from Py4GWCoreLib.mods_types import ModifierIdentifier as ModId

class Bag(Enum):
    NoBag = 0
    Backpack = 1
    Belt_Pouch = 2
    Bag_1 = 3
    Bag_2 = 4
    Equipment_Pack = 5
    Material_Storage = 6
    Unclaimed_Items = 7
    Storage_1 = 8
    Storage_2 = 9
    Storage_3 = 10
    Storage_4 = 11
    Storage_5 = 12
    Storage_6 = 13
    Storage_7 = 14
    Storage_8 = 15
    Storage_9 = 16
    Storage_10 = 17
    Storage_11 = 18
    Storage_12 = 19
    Storage_13 = 20
    Storage_14 = 21
    Equipped_Items = 22
    Max = 23


class Item:
        # ── Item.Mods ────────────────────────────────────────────────────────────
        # Read/filter an item's modifiers. `mod` = a ModId (ModifierIdentifier) member or its
        # int. Backed by mods_core (one reader + a small effect table); replaces the
        # item_mods_src parser and the deprecated Item.Customization.Modifiers.
        class Mods:
            Slot = mods_core.Slot   # Prefix / Suffix / Inscription / Rune / Insignia / Inherent

            @staticmethod
            def GetMods(item_id) -> list:
                """The distinct mod ids present on the item, as ModId members."""
                seen: list[int] = []
                for dm in mods_core.decode_item(item_id):
                    if dm.identifier not in seen:
                        seen.append(dm.identifier)
                return [ModId(i) for i in seen]

            @staticmethod
            def GetName(mod) -> str:
                """The mod's effect/base name, from its id."""
                return mods_core.effect_name(int(mod))

            @staticmethod
            def GetDescriptions(item_id) -> list:
                """Game-style human-readable lines for the item (upgrades + effect mods).
                The render/oracle layer — compare against the game's decoded info-string."""
                return mods_core.describe_item(item_id)

            @staticmethod
            def GetRawDump(item_id) -> list:
                """Every decoded mod word with id/args/upgrade_id + render status (diagnostics)."""
                return mods_core.raw_dump(item_id)

            @staticmethod
            def GetValues(item_id, mod) -> list:
                """Value(s) of the first matching mod — ALWAYS a list ([] if absent/valueless)."""
                for dm in mods_core.decode_item(item_id):
                    if dm.identifier == int(mod):
                        return mods_core.value_of(dm)
                return []

            @staticmethod
            def GetSubtype(item_id, mod):
                """Catalog subtype (enum member) of the first matching mod, or None."""
                for dm in mods_core.decode_item(item_id):
                    if dm.identifier == int(mod):
                        return mods_core.subtype_of(dm)
                return None

            @staticmethod
            def GetRaw(item_id, mod):
                """(arg1, arg2) of the first matching mod, or None."""
                for dm in mods_core.decode_item(item_id):
                    if dm.identifier == int(mod):
                        return (dm.arg1, dm.arg2)
                return None

            @staticmethod
            def GetUpgrades(item_id) -> list:
                """Applied upgrades as (name, Slot) — prefixes/suffixes/inscriptions/runes/insignias."""
                return [(name, mods_core.Slot(slot)) for name, slot in mods_core.upgrades_on(item_id)]

            @staticmethod
            def GetSlot(item_id, upgrade_name):
                """The slot of an applied upgrade (by name), or None."""
                slot = mods_core.slot_of_upgrade(str(upgrade_name))
                return mods_core.Slot(slot) if slot is not None else None

            @staticmethod
            def GetUpgradeInSlot(item_id, slot):
                """The name of the applied upgrade in the given slot, or None."""
                for name, s in Item.Mods.GetUpgrades(item_id):
                    if s == slot:
                        return name
                return None

            @staticmethod
            def HasUpgradeInSlot(item_id, slot) -> bool:
                """True if an upgrade occupies the given slot."""
                return any(s == slot for _, s in Item.Mods.GetUpgrades(item_id))

            @staticmethod
            def IsMaxed(item_id, upgrade_name) -> bool:
                """True if the named upgrade's value is at the top of its roll range."""
                return mods_core.upgrade_is_maxed(item_id, str(upgrade_name))

            @staticmethod
            def HasMod(item_id, mod, *values) -> bool:
                """True if the item has `mod`, optionally filtered by values.
                An enum arg = a subtype filter; a number = a value threshold ('N or better',
                direction from the mod's metadata); a callable = predicate(value)."""
                modid = int(mod)
                subtype_filter = None
                value_filters: list = []
                for v in values:
                    if isinstance(v, IntEnum):
                        subtype_filter = v
                    else:
                        value_filters.append(v)
                for dm in mods_core.decode_item(item_id):
                    if dm.identifier != modid:
                        continue
                    if subtype_filter is not None and mods_core.subtype_of(dm) != subtype_filter:
                        continue
                    if value_filters and not Item.Mods._values_match(dm, value_filters):
                        continue
                    return True
                return False

            @staticmethod
            def _values_match(dm, value_filters) -> bool:
                vals = mods_core.value_of(dm)
                better_low = mods_core.is_better(dm)
                for i, f in enumerate(value_filters):
                    if i >= len(vals):
                        return False
                    got = vals[i]
                    if callable(f):
                        if not f(got):
                            return False
                    elif better_low:
                        if got > f:
                            return False
                    elif got < f:
                        return False
                return True

            @staticmethod
            def HasAllMods(item_id, modlist) -> bool:
                """True if the item satisfies EVERY entry. Entry = mod | (mod, *values)."""
                for entry in modlist:
                    if isinstance(entry, (tuple, list)):
                        if not Item.Mods.HasMod(item_id, entry[0], *entry[1:]):
                            return False
                    elif not Item.Mods.HasMod(item_id, entry):
                        return False
                return True

            @staticmethod
            def HasAnyMods(item_id, modlist) -> bool:
                """True if the item satisfies ANY entry. Entry = mod | (mod, *values)."""
                for entry in modlist:
                    if isinstance(entry, (tuple, list)):
                        if Item.Mods.HasMod(item_id, entry[0], *entry[1:]):
                            return True
                    elif Item.Mods.HasMod(item_id, entry):
                        return True
                return False

            # -- raw modifier access (replaces Customization.Modifiers.*) --
            @staticmethod
            def GetModifiers(item_id):
                """The raw ItemModifier list off the item."""
                return Item.item_instance(item_id).modifiers

            @staticmethod
            def GetModifierCount(item_id) -> int:
                return len(Item.item_instance(item_id).modifiers)

            @staticmethod
            def ModifierExists(item_id, identifier_lookup) -> bool:
                for m in Item.item_instance(item_id).modifiers:
                    if m.GetIdentifier() == identifier_lookup:
                        return True
                return False

            @staticmethod
            def GetModifierValues(item_id, identifier_lookup):
                for m in Item.item_instance(item_id).modifiers:
                    if m.GetIdentifier() == identifier_lookup:
                        return m.GetArg(), m.GetArg1(), m.GetArg2()
                return None, None, None

        @staticmethod
        def item_instance(item_id):
            """
            Purpose: Create an instance of an item.
            Args:
                item_id (int): The ID of the item to create an instance of.
            Returns: PyItem.Item: The item instance.
            """
            return PyItem.PyItem(item_id)

        @staticmethod
        def GetAgentID(item_id):
            """Purpose: Retrieve the agent ID of an item by its ID."""
            return Item.item_instance(item_id).agent_id

        @staticmethod
        def GetAgentItemID(item_id):
            """Purpose: Retrieve the agent item ID of an item by its ID."""
            return Item.item_instance(item_id).agent_item_id

        @staticmethod
        def GetItemIdFromModelID(model_id):
            """Purpose: Retrieve the item ID from the model ID."""
            bags_to_check = [Bag.Backpack, Bag.Belt_Pouch, Bag.Bag_1, Bag.Bag_2]

            for bag_enum in bags_to_check:
                bag_instance = PyInventory.Bag(bag_enum.value, bag_enum.name)
                for item in bag_instance.GetItems():
                    pyitem_instance = PyItem.PyItem(item.item_id)
            
                    # Check if the item's model ID matches the given model ID
                    if pyitem_instance.model_id == model_id:
                        return pyitem_instance.item_id  # Return the item ID if a match is found

            return 0  # Return 0 if no matching item is found

        @staticmethod
        def GetItemByAgentID(agent_id):
            """Purpose: Retrieve the item associated with a given agent ID."""
            # Bags to check (Backpack, Belt Pouch, Bag 1, Bag 2, etc.)
            bags_to_check = [Bag.Backpack, Bag.Belt_Pouch, Bag.Bag_1, Bag.Bag_2]

            # Iterate over the bags
            for bag_enum in bags_to_check:
                bag_instance = PyInventory.Bag(bag_enum.value, bag_enum.name)

                # Iterate over the items in the bag
                for item in bag_instance.GetItems():
                    pyitem_instance = PyItem.PyItem(item.item_id)

                    # Check if the item's agent ID matches the given agent ID
                    if pyitem_instance.agent_id == agent_id:
                        return pyitem_instance  # Return the item if a match is found

            return None  # Return None if no matching item is found

        @staticmethod
        def RequestName(item_id):
            """Purpose: Request the name of an item by its ID."""
            return Item.item_instance(item_id).RequestName()
        
        @staticmethod
        def IsNameReady(item_id):
            """Purpose: Check if the name of an item is ready by its ID."""
            return Item.item_instance(item_id).IsItemNameReady()
        
        @staticmethod
        def GetName(item_id):
            """Purpose: Retrieve the name of an item by its ID."""
            return Item.item_instance(item_id).GetName()
        
        @staticmethod
        def GetItemType(item_id):
            """Purpose: Retrieve the item type of an item by its ID."""
            return Item.item_instance(item_id).item_type.ToInt(), Item.item_instance(item_id).item_type.GetName()

        @staticmethod
        def IsArmorType(item_id):
            """Purpose: Check if an item is an armor type by its ID."""
            item_type_value, _ = Item.GetItemType(item_id)
            return ItemType(item_type_value).is_armor_type()
        
        @staticmethod
        def IsWeapon(item_id):
            """Purpose: Check if an item is a weapon type by its ID."""
            item_type_value, _ = Item.GetItemType(item_id)
            return ItemType(item_type_value).is_weapon_type()

        @staticmethod
        def GetModelID(item_id):
            """Purpose: Retrieve the model ID of an item by its ID."""
            return Item.item_instance(item_id).model_id
        
        @staticmethod
        def GetModelFileID(item_id):
            """Purpose: Retrieve the model file ID of an item by its ID."""
            return Item.item_instance(item_id).model_file_id

        @staticmethod
        def GetCompositeModelIDs(model_file_id) -> list[int]:
            """Purpose: Retrieve the composite model file IDs of an item by its ID."""
            return PyItem.PyItem.GetCompositeModelIDs(model_file_id) if model_file_id > 0 else []

        @staticmethod
        def GetTrueModelFileID(model_file_id, gender : Gender = Gender.Unknown) -> int:
            """Purpose: Retrieve the "true" model file ID of an item by its ID."""
            from .Agent import Agent
            from .Player import Player

            true_id = model_file_id
            female = Agent.IsFemale(Player.GetAgentID()) if gender == Gender.Unknown else gender == Gender.Female
            file_ids = Item.GetCompositeModelIDs(model_file_id)
                        
            if file_ids:
                true_id = file_ids[10] if len(file_ids) > 10 else 0
                
                if not true_id:
                    true_id = file_ids[5] if female and len(file_ids) > 5 else file_ids[0]
                
                if not true_id:
                    true_id = model_file_id
                    
            return true_id if true_id >= 0 else 0
        
        @staticmethod
        def GetSlot(item_id):
            """Purpose: Retrieve the slot of an item is in a bag by its ID."""
            return Item.item_instance(item_id).slot

        @staticmethod
        def GetDyeColor(item_id: int) -> int:
            """
            Purpose: Retrieve the Vial of Dye color by its ID.
            Args:
                item_id (int): The vial of dye item id.
            Returns: int: The Py4GWCoreLib.DyeColor equivalent value or zero (None).
            """            
            mods = Item.item_instance(item_id).modifiers

            # Check if the item has any modifiers
            for mod in mods:
                modColor = mod.GetArg1()
                
                if modColor != 0:
                    return modColor
                
            # Zero is default dye color, i.e. no dye applied
            return 0
        
        class Rarity:
            @staticmethod
            def GetRarity(item_id) -> tuple[int, str]:
                """Purpose: Retrieve the rarity of an item by its ID."""
                return Item.item_instance(item_id).rarity.value, Item.item_instance(item_id).rarity.name

            @staticmethod
            def IsWhite(item_id):
                """Purpose: Check if an item is white rarity by its ID."""
                rarity_value, rarity_name  = Item.Rarity.GetRarity(item_id)
                return rarity_name == "White"

            @staticmethod
            def IsBlue(item_id):
                """Purpose: Check if an item is blue rarity by its ID."""
                rarity_value, rarity_name  = Item.Rarity.GetRarity(item_id)
                return rarity_name == "Blue"

            @staticmethod
            def IsPurple(item_id):
                """Purpose: Check if an item is purple rarity by its ID."""
                rarity_value, rarity_name  = Item.Rarity.GetRarity(item_id)
                return rarity_name == "Purple"

            @staticmethod
            def IsGold(item_id):
                """Purpose: Check if an item is gold rarity by its ID."""
                rarity_value, rarity_name  = Item.Rarity.GetRarity(item_id)
                return rarity_name == "Gold"

            @staticmethod
            def IsGreen(item_id):
                """Purpose: Check if an item is green rarity by its ID."""
                rarity_value, rarity_name  = Item.Rarity.GetRarity(item_id)
                return rarity_name == "Green"

        class Properties:
            @staticmethod
            def IsCustomized(item_id):
                """Purpose: Check if an item is customized by its ID."""
                return Item.item_instance(item_id).is_customized

            @staticmethod
            def GetValue(item_id):
                """Purpose: Retrieve the value of an item by its ID."""
                return Item.item_instance(item_id).value

            @staticmethod
            def GetQuantity(item_id):
                """Purpose: Retrieve the quantity of an item by its ID."""
                return Item.item_instance(item_id).quantity

            @staticmethod
            def IsEquipped(item_id):
                """Purpose: Check if an item is equipped by its ID."""
                return Item.item_instance(item_id).equipped

            @staticmethod
            def GetProfession(item_id):
                """
                Purpose: Retrieve the profession of an item by its ID.
                Args:
                    item_id (int): The ID of the item to retrieve.
                Returns: int: The profession of the item.
                """
                return Item.item_instance(item_id).profession

            @staticmethod
            def GetInteraction(item_id):
                """Purpose: Retrieve the interaction of an item by its ID."""
                return Item.item_instance(item_id).interaction

            @staticmethod
            def GetRequirement(item_id) -> tuple[Attribute, int]:
                """Purpose: Retrieve the requirement of a weapon item by its ID."""
                
                item_type = ItemType(Item.GetItemType(item_id)[0])
                if not item_type.is_weapon_type():
                    return Attribute.None_, 0
                                
                dm = mods_core.find(item_id, ModId.AttributeRequirement)
                if dm is None:
                    return Attribute.None_, 0
                attr = mods_core.subtype_of(dm)
                vals = mods_core.value_of(dm)
                return (attr if isinstance(attr, Attribute) else Attribute.None_, vals[0] if vals else 0)
            
            @staticmethod
            def GetDamage(item_id) -> tuple[int, int]:
                """Purpose: Retrieve the damage of a weapon item by its ID."""
                
                item_type = ItemType(Item.GetItemType(item_id)[0])
                if not item_type.is_weapon_type() and not item_type in [ItemType.Offhand, ItemType.Shield]:
                    return 0, 0
                                
                dm = mods_core.find(item_id, ModId.Damage, ModId.Damage2)
                if dm is None:
                    return 0, 0
                vals = mods_core.value_of(dm)   # [min, max]
                return (vals[0] if len(vals) > 0 else 0, vals[1] if len(vals) > 1 else 0)
            
            @staticmethod
            def GetArmor(item_id) -> int:                
                item_type = ItemType(Item.GetItemType(item_id)[0])
                if not item_type.is_armor_type() and not item_type == ItemType.Shield:
                    return 0
                                
                dm = mods_core.find(item_id, ModId.Armor1, ModId.Armor2)
                if dm is None:
                    return 0
                vals = mods_core.value_of(dm)
                return vals[0] if vals else 0
            
            @staticmethod
            def GetEnergy(item_id) -> int:                
                item_type = ItemType(Item.GetItemType(item_id)[0])
                if not item_type.is_armor_type() and not item_type in [ItemType.Offhand, ItemType.Staff]:
                    return 0
                                
                dm = mods_core.find(item_id, ModId.Energy, ModId.Energy2)
                if dm is None:
                    return 0
                vals = mods_core.value_of(dm)
                return vals[0] if vals else 0

            @staticmethod
            def GetItemFormula(item_id):
                """Purpose: Retrieve the item (crafting) formula of an item by its ID."""
                return Item.item_instance(item_id).item_formula

            @staticmethod
            def IsStackable(item_id):
                """Purpose: Check if an item is stackable by its ID."""
                interaction = Item.Properties.GetInteraction(item_id)
                return (interaction & 0x80000) != 0

            @staticmethod
            def IsSparkly(item_id):
                """Purpose: Check if an item is sparkly by its ID."""
                return Item.item_instance(item_id).is_sparkly

            @staticmethod
            def IsInscription(item_id):
                """True if the item is an inscription."""
                return Item.item_instance(item_id).is_inscription

            @staticmethod
            def IsInscribable(item_id):
                """True if the item can take an inscription."""
                return Item.item_instance(item_id).is_inscribable

            @staticmethod
            def IsPrefixUpgradable(item_id):
                """True if the item can take a prefix upgrade."""
                return Item.item_instance(item_id).is_prefix_upgradable

            @staticmethod
            def IsSuffixUpgradable(item_id):
                """True if the item can take a suffix upgrade."""
                return Item.item_instance(item_id).is_suffix_upgradable

            @staticmethod
            def IsOfferedInTrade(item_id):
                """Purpose: Check if an item is offered in trade by its ID."""
                return Item.item_instance(item_id).is_offered_in_trade

            @staticmethod
            def IsTradable(item_id):
                """Purpose: Check if an item is tradable by its ID."""
                return Item.item_instance(item_id).is_tradable

            @staticmethod
            def IsMaxDamage(item_id: int) -> bool:
                """True if a weapon's damage is the max for its type at its requirement."""
                item_type = ItemType(Item.GetItemType(item_id)[0])
                _, requirement = Item.Properties.GetRequirement(item_id)
                damage_for_requirement = DAMAGE_RANGES.get(item_type, {}).get(requirement, (0, 0))
                _, weapon_max = Item.Properties.GetDamage(item_id)
                return weapon_max > 0 and weapon_max == damage_for_requirement[1]

        class Type:
            @staticmethod
            def IsWeapon(item_id):
                """Purpose: Check if an item is a weapon by its ID."""
                return Item.item_instance(item_id).is_weapon

            @staticmethod
            def IsArmor(item_id):
                """Purpose: Check if an item is armor by its ID."""
                return Item.item_instance(item_id).is_armor

            @staticmethod
            def IsInventoryItem(item_id):
                """Purpose: Check if an item is an inventory item by its ID."""
                return Item.item_instance(item_id).is_inventory_item

            @staticmethod
            def IsStorageItem(item_id):
                """Purpose: Check if an item is a storage item by its ID."""
                return Item.item_instance(item_id).is_storage_item

            @staticmethod
            def IsMaterial(item_id):
                """Purpose: Check if an item is a material by its ID."""
                return Item.item_instance(item_id).is_material

            @staticmethod
            def IsRareMaterial(item_id):
                """Purpose: Check if an item is a rare material by its ID."""
                return Item.item_instance(item_id).is_rare_material

            @staticmethod
            def IsZCoin(item_id):
                """Purpose: Check if an item is a ZCoin by its ID."""
                return Item.item_instance(item_id).is_zcoin

            @staticmethod
            def IsTome(item_id):
                """Purpose: Check if an item is a tome by its ID."""
                return Item.item_instance(item_id).is_tome

        class Usage:
            @staticmethod
            def IsUsable(item_id):
                """Purpose: Check if an item is usable by its ID."""
                return Item.item_instance(item_id).is_usable

            @staticmethod
            def GetUses(item_id):
                """Purpose: Retrieve the uses of an item by its ID."""
                return Item.item_instance(item_id).uses

            @staticmethod
            def IsSalvageable(item_id):
                """Purpose: Check if an item is salvageable by its ID."""
                return Item.item_instance(item_id).is_salvageable

            @staticmethod
            def IsMaterialSalvageable(item_id):
                """Purpose: Check if an item is material salvageable by its ID."""
                return Item.item_instance(item_id).is_material_salvageable

            @staticmethod
            def IsSalvageKit(item_id):
                """Purpose: Check if an item is a salvage kit by its ID."""
                return Item.item_instance(item_id).is_salvage_kit

            @staticmethod
            def IsLesserKit(item_id):
                """Purpose: Check if an item is a lesser kit by its ID."""
                return Item.item_instance(item_id).is_lesser_kit

            @staticmethod
            def IsExpertSalvageKit(item_id):
                """Purpose: Check if an item is an expert salvage kit by its ID."""
                return Item.item_instance(item_id).is_expert_salvage_kit

            @staticmethod
            def IsPerfectSalvageKit(item_id):
                """Purpose: Check if an item is a perfect salvage kit by its ID."""
                return Item.item_instance(item_id).is_perfect_salvage_kit

            @staticmethod
            def IsIDKit(item_id):
                """Purpose: Check if an item is an ID Kit by its ID."""
                return Item.item_instance(item_id).is_id_kit

            @staticmethod
            def IsIdentified(item_id):
                """Purpose: Check if an item is identified by its ID."""
                return Item.item_instance(item_id).is_identified

        class Dye:
            """Dye reads (own subsystem, not Mods): an item's dye channels + tint, and dye-vial
            colour. All read-only; keyed by the DyeColor enum. Replaces Customization.GetDyeInfo
            (dye-colour matching = IsColor)."""
            @staticmethod
            def GetInfo(item_id):
                """Raw DyeInfo struct (tint + 4 colour channels)."""
                return Item.item_instance(item_id).dye_info

            @staticmethod
            def GetColor(item_id: int) -> DyeColor:
                """Primary dye colour: a dyed item's dye1, else a dye vial's colour."""
                try:
                    primary = DyeColor.from_dye_info(Item.item_instance(item_id).dye_info)
                    if primary != DyeColor.NoColor:
                        return primary
                except Exception:
                    pass
                try:
                    return DyeColor(Item.GetDyeColor(item_id))
                except Exception:
                    return DyeColor.NoColor

            @staticmethod
            def GetChannels(item_id):
                """(tint, [dye1, dye2, dye3, dye4]) with channels as DyeColor members."""
                info = Item.item_instance(item_id).dye_info

                def _dc(ch) -> DyeColor:
                    try:
                        return DyeColor(ch.ToInt())
                    except Exception:
                        return DyeColor.NoColor
                return (info.dye_tint, [_dc(info.dye1), _dc(info.dye2), _dc(info.dye3), _dc(info.dye4)])

            @staticmethod
            def IsColor(item_id: int, color: DyeColor) -> bool:
                """True if this item is a dye (vial) of the given colour."""
                item_type, _ = Item.GetItemType(item_id)
                return item_type == ItemType.Dye and Item.Dye.GetColor(item_id) == color


SUMMONING_SICKNESS_EFFECT_ID = 2886

KNOWN_SUMMONING_STONE_CREATURE_MODEL_IDS = frozenset({
    513,         # Fire Imp
    1726,        # Fire Imp variant
    8028,        # Legionnaire
    9055, 9076,  # Tengu Support Flare - Warrior
    9056, 9077,  # Tengu Support Flare - Ranger
    9058, 9079,  # Tengu Support Flare - Monk
    9060, 9081,  # Tengu Support Flare - Mesmer
    9062, 9083,  # Tengu Support Flare - Ritualist
    9065, 9086,  # Tengu Support Flare - Assassin
    9067, 9088,  # Tengu Support Flare - Elementalist
    9069, 9090,  # Tengu Support Flare - Necromancer
    9264,        # Imperial Guard Reinforcement Order / Canthan Guard
})

KNOWN_SUMMONING_STONE_CREATURE_ENC_NAMES = frozenset({
    "\\x8103\\x06FE",  # Imperial Guard Reinforcement Order / Canthan Guard
})


def party_player_agent_ids() -> set[int]:
    from .Party import Party
    from .Player import Player

    out: set[int] = set()
    try:
        me = int(Player.GetAgentID() or 0)
        if me > 0:
            out.add(me)
    except Exception:
        pass

    try:
        for player in Party.GetPlayers() or []:
            try:
                login_number = int(getattr(player, "login_number", 0) or 0)
                if login_number <= 0:
                    continue
                agent_id = int(Party.Players.GetAgentIDByLoginNumber(login_number) or 0)
                if agent_id > 0:
                    out.add(agent_id)
            except Exception:
                continue
    except Exception:
        pass
    return out


def has_summoning_sickness(agent_id: int | None = None) -> bool:
    from .Effect import Effects
    from .Player import Player

    try:
        target_agent_id = int(agent_id or Player.GetAgentID() or 0)
        if target_agent_id <= 0:
            return False
        return bool(Effects.HasEffect(target_agent_id, SUMMONING_SICKNESS_EFFECT_ID))
    except Exception:
        return False


def is_active_summoning_stone_ally(agent_id: int, owner_ids: set[int] | None = None) -> bool:
    from .Agent import Agent

    try:
        agent_id = int(agent_id or 0)
    except Exception:
        return False
    if agent_id <= 0:
        return False

    try:
        if not Agent.IsAlive(agent_id):
            return False
    except Exception:
        return False

    try:
        model_id = int(Agent.GetModelID(agent_id) or 0)
        if model_id in KNOWN_SUMMONING_STONE_CREATURE_MODEL_IDS:
            return True
    except Exception:
        pass

    try:
        encoded_name = Agent.GetEncNameStrByID(agent_id, literal=True)
        if encoded_name in KNOWN_SUMMONING_STONE_CREATURE_ENC_NAMES:
            return True
    except Exception:
        pass

    try:
        if Agent.IsSpirit(agent_id) or Agent.IsMinion(agent_id):
            return False
    except Exception:
        pass

    if owner_ids is None:
        owner_ids = party_player_agent_ids()

    try:
        owner_id = int(Agent.GetOwnerID(agent_id) or 0)
    except Exception:
        owner_id = 0

    if owner_id > 0 and owner_id in owner_ids:
        try:
            if Agent.IsNPC(agent_id):
                return True
        except Exception:
            return True

    return False


def has_active_party_summon(others: Iterable[int] | None = None) -> bool:
    from .Party import Party

    owner_ids = party_player_agent_ids()
    if others is None:
        try:
            others = Party.GetOthers() or []
        except Exception:
            others = []

    for other in others:
        try:
            agent_id = int(other or 0)
        except Exception:
            continue
        if is_active_summoning_stone_ally(agent_id, owner_ids=owner_ids):
            return True
    return False
                    
