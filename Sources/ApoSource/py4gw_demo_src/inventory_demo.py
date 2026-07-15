"""
Inventory section — bag/slot ENUMERATION plus gold, kits, and every mutate action.

Shape (see SPEC_reengineer.md §1.2, mirrors player_demo.py):
  * ``build_inventory()`` calls the inventory getters + iterates the bags via ``PyInventory.Bag``
    (the piece the old 9-field summary hid), CASTS each value via ``casts``, and returns a list of
    display Blocks. Item ids are widened to (bag, slot, model, name) rows — never a bare id, never a
    raw handle (R3 §6/§7).
  * ``draw_inventory_view()`` renders those blocks, exposes every action binding as an explicit
    trigger button (never auto-fired), and offers the per-section Dump-to-file button.

Data path: ``GLOBAL_CACHE.Inventory.*`` (the throttled/cached ``InventoryCache``), aligned with the
legacy demo (``Widgets\\Coding\\Py4GW_DEMO.py``) exactly. The cache mirrors the base ``Inventory``
wrapper API, so this is a pure access-layer swap. One member used here is NOT on ``InventoryCache`` and
stays on the base ``Inventory`` wrapper (marked inline with ``# base wrapper: not on GLOBAL_CACHE``):
``GetModelCountInMaterialStorage``. Per-bag enumeration keeps ``PyInventory.Bag(...).GetItems()`` (a
direct binding, not the Inventory wrapper) so each item exposes bag+slot; per-item naming routes
through ``GLOBAL_CACHE.Item.GetName`` like legacy.

R2 coverage — PyInventory reached through the cache:
  Getters wired: GetGoldAmount (GetGoldOnCharacter), GetGoldAmountInStorage (GetGoldInStorage),
  GetIsStorageOpen (IsStorageOpen), GetHoveredItemID; wrapper derived getters:
  GetInventorySpace, GetStorageSpace, GetFreeSlotCount, GetFirstIDKit, GetFirstSalvageKit,
  GetFirstUnidentifiedItem, GetFirstSalvageableItem, GetItemCount, GetModelCount,
  GetModelCountInStorage, GetModelCountInMaterialStorage, GetModelCountInEquipped,
  FindItemBagAndSlot. Bag class wired: Bag(bag_id, name) + GetItems (per-slot enumeration; item
  fields item_id/slot/model_id/quantity).
  Actions wired: OpenXunlaiWindow, IdentifyFirst, IdentifyItem, SalvageFirst, SalvageItem,
  PickUpItem (item_id), UseItem, DestroyItem, DropItem, EquipItem (item_id, agent_id), MoveItem,
  DepositGold, WithdrawGold, DropGold, DepositItemToStorage, WithdrawItemFromStorage,
  RequestName (Item, name prefetch for the bag tables).
  Skipped (require the live ActionQueue/Routines generator loop, out of scope for a demo panel):
  AcceptSalvageMaterialsWindow, AcceptSalvageWindow, and the salvage-choice dialog handlers
  HandleSalvageChoiceDialog / HandleSalvageChoiceMaterialConfirmDialog /
  IsSalvageChoiceDialogVisible / IsSalvageChoiceMaterialConfirmVisible (+ their private helpers);
  GetZeroFilledStorageArray (bulk flat dump, redundant with the enumeration tables).
"""

import PyImGui
import PyInventory

from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib.Inventory import Inventory

from . import casts
from . import diagnostics
from . import ui

_SECTION = "Inventory"

# (bag_id, display name) — explicit, no reflection. Ids match the Bags/Bag enums.
_INVENTORY_BAGS = [
    (1, "Backpack"),
    (2, "Belt Pouch"),
    (3, "Bag 1"),
    (4, "Bag 2"),
    (5, "Equipment Pack"),
]
_STORAGE_BAGS = [
    (6, "Material Storage"),
    (8, "Storage 1"),
    (9, "Storage 2"),
    (10, "Storage 3"),
    (11, "Storage 4"),
    (12, "Storage 5"),
    (13, "Storage 6"),
    (14, "Storage 7"),
    (15, "Storage 8"),
    (16, "Storage 9"),
    (17, "Storage 10"),
    (18, "Storage 11"),
    (19, "Storage 12"),
    (20, "Storage 13"),
    (21, "Storage 14"),
]
_EQUIPPED_BAGS = [
    (22, "Equipped Items"),
]

_BAG_HEADERS = ["Bag", "Slot", "Item ID", "Model ID", "Qty", "Name"]


class _State:
    item_id: int = 0
    kit_id: int = 0
    agent_id: int = 0
    model_id: int = 0
    bag_id: int = 1
    slot: int = 0
    quantity: int = 1
    gold_amount: int = 100


state = _State()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt_gold(amount) -> str:
    """R1 §7 currency cast: plat = amount // 1000; gold = amount % 1000."""
    try:
        i = int(amount)
        return f"{i // 1000} plat {i % 1000} gold ({i})"
    except (TypeError, ValueError):
        return str(amount)


def _bag_rows(bag_list):
    """Enumerate real bag contents into (bag, slot, item_id, model_id, qty, name) rows.

    Iterates ``PyInventory.Bag(bag_id, name).GetItems()`` directly (R3 §6) so each item exposes
    bag+slot — data lost by ItemArray's flat item_id list. Every field is guarded so one bad bag
    never blanks the table; the item_id is widened to a readable name via ``GLOBAL_CACHE.Item.GetName``.
    """
    rows = []
    for bag_id, bag_name in bag_list:
        bag = casts.safe(PyInventory.Bag, bag_id, bag_name)
        if bag is None:
            continue
        items = casts.safe(bag.GetItems, default=[]) or []
        for it in items:
            item_id = casts.safe(getattr, it, "item_id", default=0)
            slot = casts.safe(getattr, it, "slot", default=-1)
            model_id = casts.safe(getattr, it, "model_id", default=0)
            qty = casts.safe(getattr, it, "quantity", default=0)
            name = casts.safe(GLOBAL_CACHE.Item.GetName, item_id, default="")
            rows.append((bag_name, slot, item_id, model_id, qty, str(name)))
    return rows


# ---------------------------------------------------------------------------
# build_* — call getters, cast, return blocks (shared by render AND dump)
# ---------------------------------------------------------------------------
def _gold_block():
    inv_items, inv_cap = casts.safe(GLOBAL_CACHE.Inventory.GetInventorySpace, default=(0, 0)) or (0, 0)
    sto_items, sto_cap = casts.safe(GLOBAL_CACHE.Inventory.GetStorageSpace, default=(0, 0)) or (0, 0)
    rows = [
        ("Gold On Character", _fmt_gold(casts.safe(GLOBAL_CACHE.Inventory.GetGoldOnCharacter, default=0))),
        ("Gold In Storage", _fmt_gold(casts.safe(GLOBAL_CACHE.Inventory.GetGoldInStorage, default=0))),
        ("Is Storage Open", casts.yesno(casts.safe(GLOBAL_CACHE.Inventory.IsStorageOpen))),
        ("Hovered Item ID", casts.safe(GLOBAL_CACHE.Inventory.GetHoveredItemID)),
        ("Free Slot Count", casts.safe(GLOBAL_CACHE.Inventory.GetFreeSlotCount)),
        ("Inventory Space (used / cap)", f"{inv_items} / {inv_cap}"),
        ("Storage Space (used / cap)", f"{sto_items} / {sto_cap}"),
    ]
    return ui.kv_block("Gold & Space", rows)


def _kits_block():
    rows = [
        ("First ID Kit", casts.safe(GLOBAL_CACHE.Inventory.GetFirstIDKit)),
        ("First Salvage Kit", casts.safe(GLOBAL_CACHE.Inventory.GetFirstSalvageKit)),
        ("First Unidentified Item", casts.safe(GLOBAL_CACHE.Inventory.GetFirstUnidentifiedItem)),
        ("First Salvageable Item", casts.safe(GLOBAL_CACHE.Inventory.GetFirstSalvageableItem)),
    ]
    return ui.kv_block("Kits & First Items", rows)


def _lookup_block():
    """Id-driven getters (item_id / model_id) exposed as a live cast row set."""
    bag, slot = casts.safe(GLOBAL_CACHE.Inventory.FindItemBagAndSlot, state.item_id, default=(None, None)) or (None, None)
    rows = [
        ("Lookup Item ID", state.item_id),
        ("FindItemBagAndSlot(item_id)", f"bag={bag}  slot={slot}"),
        ("GetItemCount(item_id)", casts.safe(GLOBAL_CACHE.Inventory.GetItemCount, state.item_id)),
        ("Lookup Model ID", state.model_id),
        ("GetModelCount(model_id)", casts.safe(GLOBAL_CACHE.Inventory.GetModelCount, state.model_id)),
        ("GetModelCountInStorage(model_id)", casts.safe(GLOBAL_CACHE.Inventory.GetModelCountInStorage, state.model_id)),
        ("GetModelCountInMaterialStorage(model_id)", casts.safe(Inventory.GetModelCountInMaterialStorage, state.model_id)),  # base wrapper: not on GLOBAL_CACHE
        ("GetModelCountInEquipped(model_id)", casts.safe(GLOBAL_CACHE.Inventory.GetModelCountInEquipped, state.model_id)),
    ]
    return ui.kv_block("Lookup (driven by Actions inputs)", rows)


def build_inventory():
    blocks = [_gold_block(), _kits_block(), _lookup_block()]
    blocks.append(ui.multi_block("Inventory Bags", _BAG_HEADERS, _bag_rows(_INVENTORY_BAGS)))
    blocks.append(ui.multi_block("Storage Bags", _BAG_HEADERS, _bag_rows(_STORAGE_BAGS)))
    blocks.append(ui.multi_block("Equipped Items", _BAG_HEADERS, _bag_rows(_EQUIPPED_BAGS)))
    return blocks


# ---------------------------------------------------------------------------
# Actions — explicit trigger buttons, fired only on click
# ---------------------------------------------------------------------------
def _request_all_names():
    """Prefetch item names for the visible bag tables (async; names fill on later frames)."""
    count = 0
    for bag_id, bag_name in _INVENTORY_BAGS + _STORAGE_BAGS + _EQUIPPED_BAGS:
        bag = casts.safe(PyInventory.Bag, bag_id, bag_name)
        if bag is None:
            continue
        for it in casts.safe(bag.GetItems, default=[]) or []:
            item_id = casts.safe(getattr, it, "item_id", default=0)
            if item_id:
                casts.safe(GLOBAL_CACHE.Item.RequestName, item_id)
                count += 1
    return f"requested {count}"


def _draw_actions():
    ui.section_header("Item Subject (item_id / kit_id / agent_id)")
    state.item_id = PyImGui.input_int("Item ID", state.item_id)
    state.kit_id = PyImGui.input_int("Kit ID (id / salvage)", state.kit_id)
    state.agent_id = PyImGui.input_int("Agent ID (equip target)", state.agent_id)
    ui.action_button("Request All Names", _request_all_names, key="req_names")

    PyImGui.spacing()
    ui.section_header("Identify / Salvage")
    ui.action_button("Identify First", GLOBAL_CACHE.Inventory.IdentifyFirst, key="id_first")
    PyImGui.same_line(0, 8)
    ui.action_button("Identify Item", GLOBAL_CACHE.Inventory.IdentifyItem, state.item_id, state.kit_id, key="id_item")
    ui.action_button("Salvage First", GLOBAL_CACHE.Inventory.SalvageFirst, key="salv_first")
    PyImGui.same_line(0, 8)
    ui.action_button("Salvage Item", GLOBAL_CACHE.Inventory.SalvageItem, state.item_id, state.kit_id, key="salv_item")

    PyImGui.spacing()
    ui.section_header("Item Operations")
    ui.action_button("Pick Up Item (item_id)", GLOBAL_CACHE.Inventory.PickUpItem, state.item_id, key="pickup")
    PyImGui.same_line(0, 8)
    ui.action_button("Use Item", GLOBAL_CACHE.Inventory.UseItem, state.item_id, key="use")
    PyImGui.same_line(0, 8)
    ui.action_button("Destroy Item", GLOBAL_CACHE.Inventory.DestroyItem, state.item_id, key="destroy")
    ui.action_button("Equip Item (item_id, agent_id)", GLOBAL_CACHE.Inventory.EquipItem, state.item_id, state.agent_id, key="equip")

    PyImGui.spacing()
    ui.section_header("Move / Deposit / Withdraw Items")
    state.bag_id = PyImGui.input_int("Bag ID", state.bag_id)
    state.slot = PyImGui.input_int("Slot", state.slot)
    state.quantity = PyImGui.input_int("Quantity", state.quantity)
    ui.action_button("Move Item", GLOBAL_CACHE.Inventory.MoveItem, state.item_id, state.bag_id, state.slot, state.quantity, key="move")
    ui.action_button("Drop Item", GLOBAL_CACHE.Inventory.DropItem, state.item_id, state.quantity, key="drop")
    ui.action_button("Deposit Item To Storage", GLOBAL_CACHE.Inventory.DepositItemToStorage, state.item_id, key="dep_item")
    PyImGui.same_line(0, 8)
    ui.action_button("Withdraw Item From Storage", GLOBAL_CACHE.Inventory.WithdrawItemFromStorage, state.item_id, state.quantity, key="wd_item")

    PyImGui.spacing()
    ui.section_header("Storage / Gold")
    ui.action_button("Open Xunlai Window", GLOBAL_CACHE.Inventory.OpenXunlaiWindow, key="xunlai")
    state.gold_amount = PyImGui.input_int("Gold Amount", state.gold_amount)
    ui.action_button("Deposit Gold", GLOBAL_CACHE.Inventory.DepositGold, state.gold_amount, key="dep_gold")
    PyImGui.same_line(0, 8)
    ui.action_button("Withdraw Gold", GLOBAL_CACHE.Inventory.WithdrawGold, state.gold_amount, key="wd_gold")
    PyImGui.same_line(0, 8)
    ui.action_button("Drop Gold", GLOBAL_CACHE.Inventory.DropGold, state.gold_amount, key="drop_gold")

    PyImGui.spacing()
    ui.section_header("Model Lookup")
    state.model_id = PyImGui.input_int("Model ID (Lookup block on Data tab)", state.model_id)


# ---------------------------------------------------------------------------
# draw_*_view — uniform section entry point
# ---------------------------------------------------------------------------
def draw_inventory_view() -> None:
    blocks = build_inventory()
    diagnostics.dump_button(_SECTION, blocks)
    PyImGui.separator()
    if PyImGui.begin_tab_bar("InventoryTabs"):
        if PyImGui.begin_tab_item("Data"):
            ui.draw_blocks(_SECTION, blocks)
            PyImGui.end_tab_item()
        if PyImGui.begin_tab_item("Actions"):
            _draw_actions()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()
