# PyItem stub — Reforged Native surface (2026-07-06)
# Matches item_bindings.cpp. PyItem class + ItemModifier + ItemTypeClass + DyeInfo.

from typing import List, Any
from enum import IntEnum

class Rarity(IntEnum):
    White: int = 0
    Blue: int = 1
    Purple: int = 2
    Gold: int = 3
    Green: int = 4

class ItemModifier:
    def __init__(self, identifier: int) -> None: ...
    def GetIdentifier(self) -> int: ...
    def GetArg1(self) -> int: ...
    def GetArg2(self) -> int: ...
    def GetArg(self) -> int: ...
    def IsValid(self) -> bool: ...
    def GetModBits(self) -> int: ...
    def ToString(self) -> str: ...

class ItemTypeClass:
    def __init__(self, item_type: int) -> None: ...
    def ToInt(self) -> int: ...
    def GetName(self) -> str: ...

class DyeColorClass:
    def __init__(self, dye_color: int) -> None: ...
    def ToInt(self) -> int: ...
    def ToString(self) -> str: ...

class DyeInfo:
    dye_tint: int
    dye1: DyeColorClass
    dye2: DyeColorClass
    dye3: DyeColorClass
    dye4: DyeColorClass
    def __init__(self) -> None: ...
    def ToString(self) -> str: ...

class PyItem:
    item_id: int
    agent_id: int
    agent_item_id: int
    name: str
    modifiers: List[ItemModifier]
    is_customized: bool
    item_type: ItemTypeClass
    dye_info: DyeInfo
    value: int
    interaction: int
    model_id: int
    model_file_id: int
    item_formula: int
    is_material_salvageable: int
    quantity: int
    equipped: int
    profession: int
    slot: int
    is_stackable: bool
    is_inscribable: bool
    is_material: bool
    is_zcoin: bool
    rarity: Rarity
    uses: int
    is_id_kit: bool
    is_salvage_kit: bool
    is_tome: bool
    is_lesser_kit: bool
    is_expert_salvage_kit: bool
    is_perfect_salvage_kit: bool
    is_weapon: bool
    is_armor: bool
    is_salvageable: bool
    is_inventory_item: bool
    is_storage_item: bool
    is_rare_material: bool
    is_offered_in_trade: bool
    is_sparkly: bool
    is_identified: bool
    is_prefix_upgradable: bool
    is_suffix_upgradable: bool
    is_usable: bool
    is_tradable: bool
    is_inscription: bool
    is_rarity_blue: bool
    is_rarity_purple: bool
    is_rarity_green: bool
    is_rarity_gold: bool

    def __init__(self, item_id: int) -> None: ...
    def GetContext(self) -> None: ...
    def RequestName(self) -> None: ...
    def IsItemNameReady(self) -> bool: ...
    def GetName(self) -> str: ...
    def GetInfoString(self) -> List[int]: ...
    def GetNameEnc(self) -> List[int]: ...
    def GetCompleteNameEnc(self) -> List[int]: ...
    def GetSingleItemName(self) -> List[int]: ...
    def IsItemValid(self, item_id: int) -> bool: ...

    @staticmethod
    def GetCompositeModelIDs(item_id: int) -> List[int]: ...

# ── Module-level free functions ──
def use_item_by_id(item_id: int) -> bool: ...
def equip_item_by_id(item_id: int, agent_id: int = 0) -> bool: ...
def drop_item_by_id(item_id: int, quantity: int = 1) -> bool: ...
