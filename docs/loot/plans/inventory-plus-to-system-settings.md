# Inventory+ to System Settings Migration

Status: active, reduced scope
Scope: System Settings item-frame interaction, Xunlai access, and Colorize
Last reviewed: 2026-08-09

## Current owner and scope

`system_settings/inventory/` owns only two independent item features:

- opening the Xunlai Vault from the shared item context menu;
- coloring bag and regular-inventory slots.

The shared context monitor uses `InventoryBagsWindow` and `InventoryWindow` as
equal frame sources. When both are open, both are monitored. The old special
`I` path is not used.

Colorize has its own draw callback. Xunlai access has its own context action.
Both settings are stored together as plain global feature settings in
`Widgets/System/InventoryFeatures.json`; neither belongs to a user-selected
configuration object.

Loot Filters are outside this migration and remain unchanged.

## Verification record

Static verification is required after Python changes: focused `compileall`,
strict Pyright, and `git diff --check`. Live injected-client testing remains
necessary to verify the right-click trigger, popup focus, both frame sources,
and native tint behavior.

## Journal

### 2026-08-09 - Scope reset

Removed the disconnected item-management work and reduced the active migration
to the two features above. The System Settings Items category exposes only
Xunlai access and Colorize from this migration. Loot Filters were not changed.
