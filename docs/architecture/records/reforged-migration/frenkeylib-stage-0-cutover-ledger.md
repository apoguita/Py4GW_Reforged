# FrenkeyLib Stage 0 Cutover Ledger

Status: proposed; source-audited on 2026-08-10
Scope: live-source inventory for the FrenkeyLib and Mark modifier-consumer
migration. Deprecated inventory control is an explicit exclusion.
Authority: current Python source, `Item.Mods`, the layered migration plan, and
the current decoder parity report. Legacy source is behavioural reference only.

Related plan: `frenkeylib-layered-migration-plan.md`.

## Recorded migration boundary

The retained FrenkeyLib surface is a consumer of an already supplied item ID.
It may present or compose public Reforged item answers. It must not scan bags,
construct snapshots for control flow, select inventory actions, or execute
identify, salvage, or storage work.

The native System Settings inventory owner now supplies explicit execution
requests without inheriting a Frenkey inventory handler. Its current contract
is deliberately narrow: an identify request accepts item IDs and polls each
native result; salvage and storage operate only on an explicitly hovered item;
materials-salvage confirmation requires a separate explicit request. The
controller uses native `PyInventory` actions and does not create a second raw
modifier, catalogue, snapshot, or action queue owner.

This is an execution owner, not a new inventory rule engine. Reforged remains
the source of item facts and rule verdicts, while the System Settings controller
only receives item IDs. Automatic selection, range interpretation, and legacy
MerchantRules policy remain outside this first cutover.

## Source-reachability inventory

| Current root or dependency | Evidence | Stage 0 disposition |
|---|---|---|
| `Widgets/Guild Wars/Items & Loot/TeamInventoryViewer.py` | Source cutover on 2026-08-10 removed Mark parser imports, `ModDatabase`, `parse_modifiers`, raw modifier reads, and the unused raw-modifier hash cache. | Retained read-only consumer. It derives its display names from `Item.Mods.GetUpgradeInSlot`. |
| `Widgets/Guild Wars/Items & Loot/MerchantRules.py` | Imports `ModDatabase` and `parse_modifiers`; source audit found every parser/catalogue path belongs to its inventory policy. | Explicitly quarantined inventory graph. There is no retained non-inventory parser consumer to migrate; removal waits for the native System Settings replacement or formal retirement. |
| `Widgets/Guild Wars/PartyQuestLog.py` | Direct FrenkeyLib widget root. | Retained non-inventory feature slice; no direct modifier-read evidence in this pass. |
| `Widgets/Guild Wars/MultiBoxing.py` | Direct FrenkeyLib widget root. | Retained non-inventory feature slice; no direct modifier-read evidence in this pass. |
| `Widgets/Automation/Bots/Runners/Sulfurous Runner.py` | Direct FrenkeyLib widget root. | Retained non-inventory feature slice; no direct modifier-read evidence in this pass. |
| `Widgets/Automation/Bots/Miscellaneous/Polymock.py` | Direct FrenkeyLib widget root. | Retained non-inventory feature slice; no direct modifier-read evidence in this pass. |
| `Sources/frenkeyLib/Core/{gui,utility}.py` | Transitive imports from retained Polymock UI. | Active ImGui texture presentation and pure string/path helpers only. They do not read item modifiers, own inventory state, or persist feature data. The texture existence probe concerns bundled static assets, not user persistence. |
| `Sources/frenkeyLib/Core/encoded_names.py` | Imported only by `ItemHandling/Items/item_collecting.py`. | Excluded with the snapshot collector. Its current missing `PyGameThread` static import is not a retained Polymock/Core failure and must not pull inventory collection back into this migration. |
| `Sources/frenkeyLib/Py4GWLibrary/library.py` | No current importer outside its own module; its configuration is read and written through `Settings.find`. | Dormant shared UI helper. No persistence migration is needed unless a supported current launchpad adopts it. |
| `Sources/frenkeyLib/Drafts/` | Historical widget-manager and library scripts create their own old INI directories; no current importer was found. | Not a retained feature. Document as historical code; do not migrate its persistence or UI surface. |
| `Py4GWCoreLib/py4gwcorelib_src/AutoInventoryHandler.py` | Imports `ItemSnapshot` at line 137 and `BTNodes` at lines 338 and 361. | Explicitly excluded and later deprecated. No migration work may repair this coupling or use it as a compatibility path. |
| `Widgets/Guild Wars/Items & Loot/InventoryPlus.py` | Directly constructs `AutoInventoryHandler` for identify and salvage flows. | Explicitly excluded. The native System Settings ID cutover must replace this public execution root before the handler can be retired. |
| `Sources/frenkeyLib/LootEx/inventory_handling.py` | Defines `LootExAutoInventoryHandler`, `InventoryHandler`, and replaces the core handler instance. | Explicitly excluded. It is evidence of the old competing inventory owner, not a base to port. |
| `Sources/frenkeyLib/ItemHandling/{BTNodes,Handlers,Items/item_snapshot.py}` | Snapshot and behavior-tree paths drive inventory decisions and actions. | Explicitly excluded. Do not migrate, test for parity, or retain as a dependency of a migrated consumer. |

The four direct Frenkey widget roots are source-reachability evidence, not proof
that every transitive module is live in a particular injected-client session.
Existing runtime diagnostics are consulted only for a reported feature concern;
they are not a migration prerequisite.

## Item-mod call ledger

| ID | Current source and evidence | Question currently answered | Required owner after cutover | Disposition and removal condition |
|---|---|---|---|---|
| M-01 | `Sources/marks_sources/mods_parser.py`: `ModDatabase`, JSON loading, `Rune`, `WeaponMod`, and `parse_modifiers`. | Decode raw triples into named rune/weapon-mod results, slots, and max status. | `Item.Mods.GetUpgrades`, slot methods, `IsMaxed`, `GetValues`, `GetSubtype`, and `GetDescriptions` as the caller's concrete question requires. | No retained non-inventory caller requires a Mark presentation result after M-02. Its sole production importer is the excluded Merchant inventory path (M-03), so do not redesign it as a second consumer. Retire it with that owner or refit only a newly retained non-inventory caller. |
| M-02 | `TeamInventoryViewer.py`. | Show prefix, suffix, and inherent names for a supplied item ID. | `Item.Mods.GetUpgradeInSlot`. | Source cutover complete. The viewer no longer imports Mark parser/catalog code or reads raw modifiers; it asks the public prefix, suffix, and inherent slots directly. |
| M-03 | `MerchantRules.py:_parse_exact_armor_upgrade_state` at line 4981 and `_get_cached_inventory_modifiers` at line 15764; both use raw triples and the rune catalogue. | Infer upgrade identity and inventory/salvage-oriented state from raw triples and a rune catalogue. | Public `Item.Mods` only for any retained non-inventory display or criterion. | Split. A retained non-inventory question is a Stage 2 consumer cutover. Bag scanning, cached raw triples, exact carrier signatures, salvage, and storage decisions are excluded for the later native owner; no replacement is created here. |
| F-01 | `LootEx/utility.py:104-171,572`. | Interpret requirement, damage, damage type, shield armor, and values from raw modifier argument positions. | `Item.Properties` for generic item facts and typed `Item.Mods.GetSubtype` for modifier facts. | Source cutover complete on 2026-08-10: no runtime `GetModifierValues` use remains in this utility. `Item.Properties.GetShieldArmor` was added as the narrow owner gap for its paired shield value. |
| F-02 | `LootEx/data_collection.py:55`; `LootEx/cache.py`; `LootEx/models.py:1709-1813`. | Build a local modifier-information model from raw modifiers, item type, model ID, and inscribability. | `Item.Mods` plus public item facts; no local modifier-information authority. | Stage 3, but only for retained non-inventory presentation or rule work. Delete or reduce `ItemModifiersInformation` rather than preserving a second decoded model. |
| F-03 | `LootEx/models.py`, `data.py`, `weaponmods.py`, `weapon_rule.py`, and `filter.py`. | Catalogued rune/weapon-mod identities, roll ranges, and local raw-triple matches. | Named upgrades, slots, max status, direction-aware thresholds, and descriptions from `Item.Mods`. | Stage 3. Retire item-mod catalog and matching ownership after the last retained consumer is repointed. Static non-mod feature data needs a separate owner audit. |
| F-04 | `ItemHandling/GlobalConfigs/Rule.py:275-278`. | Compare named upgrades and a rune target type; it reaches `Item.Mods` but first obtains an `ItemSnapshot`. | Public `Item.Mods.GetSubtype` and `GetUpgrades` for a supplied item ID. | Do not port the snapshot/control-flow path. Reuse these calls only if a future non-inventory consumer has the same question. |
| F-05 | `ItemHandling/Items/item_snapshot.py:217-226`. | Cache raw modifiers, upgrades, and subtype as part of inventory control. | None in this migration. | Excluded. The later native owner supplies the item ID and reads public facts directly. |

## Public contract checked during this pass

The current public `Item.Mods` source exposes the required consumer primitives:

| Consumer need | Public surface |
|---|---|
| Named applied upgrades and physical slots | `GetUpgrades`, `GetUpgradeInSlot`, `HasUpgradeInSlot`, `GetSlot` |
| Named upgrade max status | `IsMaxed` |
| Modifier existence, subtype, or direction-aware threshold | `HasMod`, `HasAllMods`, `HasAnyMods`, `GetValues`, `GetSubtype` |
| Reforged-owned readable explanation | `GetDescriptions` |
| Shield armor at and below requirement | `Item.Properties.GetShieldArmor` |

`GetModifiers` and `GetModifierValues` also exist, but this ledger classifies
them as diagnostic/compatibility reads. They are not permitted in a retained
consumer to decode a modifier or make a rule verdict.

`Item.Mods.HasMod` rejects callable predicates. FrenkeyLib and Mark use only
declarative subtype and numeric values, with the existing direction-aware
"that value or better" semantics.

## Retained-boundary static certification

On 2026-08-10, focused production searches over the retained roots
(`TeamInventoryViewer`, `PartyQuestLog`, `MultiBoxing`, `SulfurousRunner`, and
`Polymock`) found no call or import of `GetModifiers`, `GetModifierValues`,
`ModDatabase`, `parse_modifiers`, `AutoInventoryHandler`, `ItemSnapshot`, or
`BTNodes`. The same roots contain no `open(...)`, `json.load`, `json.dump`,
`configparser`, directory-creation, or existence-probe persistence path.

The only remaining production importer of Mark's raw parser is
`MerchantRules.py`. Its parser-driven questions are inventory/salvage-oriented
and remain deferred with the explicitly excluded inventory owner. A broad text
search also found only comments and labels referring to LootEx outside that
excluded graph; it found no retained import.

## Stage 0 completion and remaining evidence

Completed in this source pass:

1. Recorded direct widget roots, Mark consumers, and the core-to-Frenkey
   `AutoInventoryHandler` coupling.
2. Classified raw modifier consumers versus excluded inventory-control paths.
3. Mapped retained item-mod questions to existing public `Item.Mods` calls.

No further Stage 1 input is required unless a consumer or the parity report
identifies a concrete missing public capability. Record that capability as an
`Item.Mods` owner gap; do not add a FrenkeyLib or Mark workaround.

## Stage 1 decoder evidence

### Offline result

The two existing owner validators are injected-client widgets, not fixture-based
tests:

- `Widgets/Coding/Debug/Py4GW/Item Mods Playground.py` latches a hovered item,
  compares game tooltip text against `Item.Mods.GetDescriptions`, displays
  upgrades and slots, and exercises ALL/ANY and threshold helpers.
- `Widgets/Coding/Debug/Py4GW/Mod Parity Scan.py` scans inventory, equipment,
  and storage, then writes game-versus-Reforged results to
  `docs/items/modifiers/generated/mod-parity-scan.txt`.

On 2026-08-10, the user directed the migration to treat the current decoder as
authoritative and add only what is missing. The Playground and parity scan are
diagnostic tools, not migration gates or a request for separate smoke tests.
They are consulted only when their output identifies a concrete owner gap.

`npx.cmd --no-install pyright Py4GWCoreLib\\Item.py` was run on 2026-08-10. It
reported two existing `reportAttributeAccessIssue` diagnostics at lines 241 and
261, where `GetItemIdFromModelID` and `GetItemByAgentID` access `item.item_id`
on a value typed as `dict[str, Any]`. Both are outside `Item.Mods`; no
`Item.Mods` diagnostic was reported. This is a recorded baseline, not a passed
strict-Pyright result.

### Current parity result

The current `mod-parity-scan.txt` was generated on 2026-08-10 at 13:47 and
scanned 271 items. It contains zero `?UNKNOWN` and zero `(UNHANDLED)` raw
decoder statuses. Its structural rows are intentionally non-display carrier
words. The report is a readable GAME-versus-OURS dump rather than an automated
mismatch verdict; sampled weapon and shield facts agree with GAME text despite
display-order differences. It identifies no concrete decoder gap.

### Source-proven owner addition

The historical 2026-07-17 parity export marked generic profession-rune carrier
IDs `0x00AF`, `0x00BB`, `0x00C0`, and `0x013D` as unknown in `GetRawDump`.
Current source inspection showed that `GetUpgrades` already resolves the named
rune and its suffix slot from the accompanying `AttributeRune` word. The
missing information was only the carrier's diagnostic name.

`Py4GWCoreLib/mods_core.py` now derives the names of all 30 generic
profession-rune carriers from the existing `ItemUpgrade.UpgradeRune` and
`ItemUpgradeId` owner data. It changes `GetRawDump` only; it does not alter
the established named-rune/slot result that consumers receive through
`GetUpgrades`.

Focused synthetic verification constructed a Superior Mesmer rune carrier plus
its Fast Casting attribute word and proved both results: `GetUpgrades` still
returns `MesmerRuneOfSuperiorFastCasting` in the suffix slot, while `GetRawDump`
now reports `SuperiorMesmerRune` rather than an unknown carrier. The same table
contains 30 generic profession-rune carrier IDs. `py_compile` and focused
Pyright on `mods_core.py` passed with zero diagnostics.

## Static checks used

- Searched Python sources for direct FrenkeyLib roots, Mark parser imports,
  raw modifier reads, parser/catalog symbols, and `AutoInventoryHandler`
  coupling.
- Inspected the current public `Item.Mods` methods in `Py4GWCoreLib/Item.py`.
- Ran focused Pyright as recorded above; its two non-mod baseline diagnostics
  remain unresolved and no source files were changed to suppress them.

The Stage 1 owner addition changes only raw diagnostics.

## Stage 2 Team Inventory Viewer source cutover

On 2026-08-10, `TeamInventoryViewer.py` was repointed to the public
`Item.Mods.GetUpgradeInSlot` surface for the prefix, suffix, and inherent
labels it composes into a display name. It no longer reads modifier triples,
loads `mods_data`, imports `mods_parser`, or persists a raw-modifier hash.
The hash store had no reader, so it was removed rather than replaced with a
second representation of the same item state.

The Item.Mods inherent-slot query is intentionally retained even though the
current source slot table has no listed inherent mapping. The viewer is a
consumer, not a classifier: if the owning platform reports that slot, the
existing display position receives it; otherwise it presents no inherent
parenthetical. No raw fallback is allowed.

`python -m py_compile` and focused strict Pyright on the widget completed with
zero diagnostics.

## Stage 3 LootEx utility source cutover

On 2026-08-10, `LootEx/utility.py` was repointed from runtime raw modifier
arguments to `Item.Properties.GetRequirement`, `Item.Properties.GetDamage`,
`Item.Mods.GetSubtype`, and `Item.Properties.GetShieldArmor`. The first three
were existing public calls. `GetShieldArmor` is the sole source-proven owner
addition: it returns the shield's above- and below-requirement values as the
former helper contract requires, without exposing raw modifier arguments to
FrenkeyLib.

`python -m py_compile` passed for the edited core and utility modules. Focused
Pyright reported five existing errors outside the edits: two `dict[str, Any]`
attribute reads in `Item.py` (lines 241 and 261), and three analogous item/slot
reads in `LootEx/utility.py` (lines 746-747). The converted methods introduced
no diagnostics. Live feature evidence remains deferred to the retained
non-inventory LootEx slice.

## Remaining raw-owner disposition

The final 2026-08-10 source reachability pass found no retained direct Frenkey
widget root importing `LootEx`. The remaining `ItemModifiersInformation`,
rune/weapon-mod catalog matching, and `get_target_item_type_from_mod` callers
flow through LootEx collection, filtering, storage/salvage, or Merchant Rules
inventory planning. They remain explicitly excluded legacy inventory owners.

Removing or deprecating those modules is a later System Settings rule-policy
cutover decision. This migration does not give them a new raw-parser wrapper,
does not keep them as a compatibility dependency of a retained consumer, and
does not delete them prematurely.

## Native inventory cutover prerequisites

The 2026-08-10 retirement scan established these required replacement points:

1. `InventoryPlus` must stop constructing `AutoInventoryHandler` for identify
   and salvage before that handler is deprecated.
2. LootEx must stop assigning its `LootExAutoInventoryHandler` into the core
   singleton before its inventory module can be detached.
3. The System Settings inventory controller now provides explicit native
   identify, salvage, and storage requests. A later rule-policy integration
   must consume public Reforged verdicts and submit only item IDs; it must not
   restore a Python compatibility inventory handler.
4. Only after those roots are cut over may the `ItemHandling` snapshot,
   behavior-tree, handler, and raw-model graph be removed or deprecated.

## System Settings execution cutover

On 2026-08-11, `system_settings/inventory` gained the first native execution
contract. `InventorySettingsController.request_identify(item_ids)`,
`request_salvage(item_id)`, and `request_store(item_id)` accept an explicit
current inventory item ID and route only through native `PyInventory` calls.
Identify advances after polling the public identified state; a materials-salvage
confirmation requires a separate explicit request. The System Settings UI adds
manual controls, but does not make a rule decision or run on inventory change.

The manual identify helpers in `InventoryPlus.py` now submit their selected
rarity candidates to `request_identify`; the widget no longer calls
`AutoInventoryHandler().IdentifyItems`. Its automatic salvage, storage, and
handler configuration remain legacy work until their replacement policy can
consume public Reforged verdicts without duplicating that authority.

`botting_src/helpers_src/Items.py::auto_identify_items` also now submits the
current candidates to the System Settings controller and yields until that
controller observes completion. It no longer disables, invokes, then restores
the deprecated handler singleton. Salvage, deposit, and combined botting
commands remain deferred because their legacy behavior carries selection and
confirmation policy that has not yet been moved to the Reforged owner.

No `Gw` or `Gw64` process was available during this scan, so the migrated
viewer and feature smoke checks remain deferred.
