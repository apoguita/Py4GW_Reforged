"""Shared inventory/bags item monitor for Colorize.

Both visible sources are peers. There is deliberately no legacy special ``I`` mode and no nested
frame-prefix search here; the current FrameTree exposes direct accessors for both windows.
"""

from dataclasses import dataclass
import time

import PyInventory

from Py4GWCoreLib import Item, UIManager
from Py4GWCoreLib.FrameTree import Frame
from Py4GWCoreLib.enums_src.Item_enums import INVENTORY_BAGS, Bags
from Py4GWCoreLib.enums_src.UI_enums import WindowID


@dataclass
class InventorySlot:
    item_id: int
    rarity: str
    bag: Bags
    slot: int
    is_id_kit: bool = False
    is_salvage_kit: bool = False
    bag_frame: Frame | None = None
    inventory_frame: Frame | None = None


class InventoryMonitor:
    def __init__(self, refresh_interval: float = 0.25) -> None:
        self._refresh_interval = float(refresh_interval)
        self._last_scan = 0.0
        self._last_visibility: tuple[bool, bool] | None = None
        self._cached: list[InventorySlot] = []

    def scan(self) -> list[InventorySlot]:
        bags_visible = bool(UIManager.IsWindowVisible(WindowID.WindowID_InventoryBags))
        inventory_visible = bool(UIManager.IsWindowVisible(WindowID.WindowID_Inventory))
        visibility = (bags_visible, inventory_visible)
        now = time.monotonic()
        if (now - self._last_scan) < self._refresh_interval and visibility == self._last_visibility:
            return self._cached
        self._last_scan = now
        self._last_visibility = visibility
        output: list[InventorySlot] = []
        for bag in INVENTORY_BAGS:
            try:
                bag_instance = PyInventory.Bag(int(bag.value), bag.name)
                for item in bag_instance.GetItems() or []:
                    item_id = int(item.get("item_id", 0) if isinstance(item, dict) else item.item_id)
                    if not item_id:
                        continue
                    item_instance = Item.item_instance(item_id)
                    if item_instance is None:
                        continue
                    _, rarity = Item.Rarity.GetRarity(item_id)
                    slot = int(item.get("slot", -1) if isinstance(item, dict) else item.slot)
                    bag_frame = Frame.bag_slot(bag, slot) if bags_visible else None
                    inventory_frame = Frame.inventory_bag_slot(bag, slot) if inventory_visible else None
                    output.append(InventorySlot(
                        item_id=item_id,
                        rarity=rarity,
                        bag=bag,
                        slot=slot,
                        is_id_kit=bool(item_instance.is_id_kit),
                        is_salvage_kit=bool(item_instance.is_salvage_kit),
                        bag_frame=bag_frame if bag_frame and bag_frame.is_usable else None,
                        inventory_frame=inventory_frame if inventory_frame and inventory_frame.is_usable else None,
                    ))
            except Exception:
                continue
        self._cached = output
        return self._cached

    def hovered_slot(self) -> InventorySlot | None:
        """Return the visible slot beneath the mouse from this monitor's own snapshot."""
        for entry in self.scan():
            for frame in (entry.bag_frame, entry.inventory_frame):
                if frame is not None and frame.is_mouse_over():
                    return entry
        return None
