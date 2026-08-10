# Item Catalogs

Status: research reference

The Guild Wars client exposes eight static item catalogs: colors, attributes,
descriptions, crafting formulas, elements, books, PvP base items, and PvP
unlocks. This record preserves what they are and how to investigate them; it
does not store their dump as a documentation database.

## Known accessors

- Colors: `ConstItemGetColorString` at `0x0019c3c0`, 14 text-id entries.
- Attributes: `ConstItemGetAttributeText` at `0x0019d1b0`, 559 text-id entries.
- Descriptions: `ConstItemGetDescriptionText` at `0x0019da70`, 360 text-id entries.
- Formulas: `ConstItemGetFormulaDef` at `0x0019e010`, 1,498 structs of 20 bytes.
- Elements: `ConstItemGetElementDefClient` at `0x001a5520`, 41 structs of 12 bytes.
- Books: `ConstItemGetBookDefClient` at `0x001a5710`, 33 structs of 28 bytes.
- PvP base items: `ConstItemPvpGetItemDef` at `0x001b2950`, 343 structs of 36 bytes.
- PvP unlocks: `ConstItemPvpGetUnlockDef` at `0x001b5990`, 390 structs of 40 bytes.

The text-id fields are resolved only in a running client because `gw.dat`
supplies the string table. The PvP-unlock names are composed through the
native item binding; see `game-mod-table.md` and `native-name-binding.md`.

## Compact findings from the last extraction

- All 14 color labels, all 360 description labels, and all 41 element names
  resolved successfully. Of the 559 attribute text ids, 259 resolved; the
  remainder require a targeted string-table pass rather than being treated as
  missing attributes.
- The 1,498 crafting formulas cost from 3 to 100,000 and use one ingredient
  in 417 cases, two in 871, three in 111, and four in 99.
- Of 343 PvP base-item entries, 339 have a resolved base name. Of 390 PvP
  unlock entries, 389 have a resolved composed name.
- The 33 book records remain structurally known but semantically incomplete:
  their eight raw fields are not yet named. That is a layout-research task,
  not a documentation-data task.

## Tool ownership

The structural extraction fixtures belong to
`Widgets/Coding/Debug/Py4GW/item_catalog_data/`, beside the `Dump Item
Catalogs` and `Resolve Catalog Text` widgets that read them. Those widgets use
relative paths and may produce local investigation output there. Do not copy
that data into `docs/`.

## Refresh procedure

1. Reconfirm the accessor and layout in Ghidra after a game patch.
2. Refresh the widget-owned extraction fixture only when the layout changed.
3. Run `Dump Item Catalogs` in a loaded client to resolve the runtime text.
4. Record any durable finding, changed count, or layout conclusion in this
   document or the more-specific item-mod research record.

## Current state

The discovery pass, formula layout, element labels, and PvP-unlock decoding
are established. Remaining low-priority work is naming the unfinished book
and PvP-item fields and locating the additional model, material, and item-type
tables that do not have a simple `ConstItemGet*` accessor.
