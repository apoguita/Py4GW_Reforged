# Item User Manual

`GW::item` is the inventory, item action, and storage subsystem.

Main capabilities from `include/GW/item/item.h`:

- use, equip, move, drop, salvage, identify, and destroy items
- inspect character and storage gold
- operate on Xunlai/storage state
- register item-click callbacks
- decode item names asynchronously
- manage equipment visibility

Representative API:

- `UseItem(...)`
- `EquipItem(...)`
- `MoveItem(...)`
- `DropItem(...)`
- `SalvageStart(...)`
- `IdentifyItem(...)`
- `OpenXunlaiWindow(...)`
- `AsyncGetItemName(...)`

Use this manager instead of stitching inventory actions together manually.
