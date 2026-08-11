# FrenkeyLib and Mark Mod Consumer Contract Audit

Status: proposed; source-audited on 2026-08-10
Scope: item-mod and item-rule consumption by `Sources/frenkeyLib/` and
`Sources/marks_sources/mods_parser.py`; excludes deprecated
inventory control, `AutoInventoryHandler`, and action execution.
Authority: current `Item.Mods`, current public item source, and current
consumer source. The current decoder is authoritative; parity output is
consulted only when it reports a concrete owner gap.

## Decision

Reforged owns modifier decoding, named upgrades, roll direction, and item-mod
matching. FrenkeyLib and Mark's former parser are consumers. They must not
decode raw triples, read modifier catalogs, or supply a competing match result.
They also do not acquire inventory scanning, item snapshots for control flow,
or identify/salvage/storage execution while becoming consumers.

The production dependency direction is:

```text
feature/widget -> FrenkeyLib consumer -> public Item.Mods and item surfaces
               -> Reforged item implementation -> native item data
```

`Py4GWCoreLib.mods_core`, `mods_upgrades`, raw `ItemModifier` triples, and the
encoded-string decoder are implementation or diagnostic layers. The Item Mods
Playground may inspect them to prove Reforged behaviour; feature code must not.

## Current Reforged contract

`Py4GWCoreLib/Item.py::Item.Mods` is the public item-mod authority:

- effect presence and direction-aware value/subtype matching: `HasMod`,
  `HasAllMods`, and `HasAnyMods`;
- named applied upgrades and slots: `GetUpgrades`, `GetSlot`,
  `GetUpgradeInSlot`, `HasUpgradeInSlot`, and `IsMaxed`;
- explanatory/diagnostic output: `GetDescriptions` and `GetRawDump`.

The Item Mods Playground is the migration reference for the public surface:
it composes item type, requirement, damage, named upgrades, slots, ALL/ANY,
and `Item.Mods` helpers against a real item. `Item.Mods` remains the item-mod
authority for every item state, including identified upgrades. A consumer
chooses the existing public surface that expresses its rule.

Other Reforged modules may be consulted only when a specific migrated caller
already owns or uses them. They are not a baseline, replacement rule system, or
implicit constraint on this migration.

## Legacy bypass inventory

| Legacy owner | Existing behaviour | Required disposition |
|---|---|---|
| `Sources/marks_sources/mods_parser.py` | Loads `runes.json` and `weapon_mods.json`, then turns raw triples into its own rune/weapon-mod model and verdict. | Refit as an item-ID Reforged consumer if callers still need its presentation result. Remove raw parsing and catalog ownership; do not replace it with another raw-triple parser. |
| `frenkeyLib/LootEx/models.py` and `data.py` | Own `Rune`, `WeaponMod`, `ModifierInfo`, roll ranges, names, and matching catalogues. | Do not migrate these as domain authority. Preserve only non-mod feature data after a separate ownership decision. |
| `frenkeyLib/LootEx/utility.py` | Reads `GetModifierValues` and reinterprets identifier/argument positions. | Repoint each question to `Item.Properties` or a typed `Item.Mods` helper. |
| `frenkeyLib/ItemHandling/{Rules,GlobalConfigs}` | Defines parallel rule classes and compares snapshots, old item data, and upgrade names. | Refit a criterion only for a genuine non-inventory consumer, using public `Item.Mods` and item calls; retain no fallback evaluator. |
| `frenkeyLib/ItemHandling/Items/item_snapshot.py` | Captures raw modifiers, parsed properties, and upgrades for legacy inventory rules. | Not a migration target. A future native System Settings ID owner supplies item IDs and reads Reforged surfaces directly. |

`mods_parser.py` has two current non-legacy consumers: `TeamInventoryViewer.py`
and `MerchantRules.py`. Both already have an item ID at the call sites. The
module can therefore consume `Item.Mods` directly; a public "parse arbitrary
triples" API would reintroduce the bypass and is rejected.

## Criteria migration matrix

| Legacy question | Reforged owner | Audit result |
|---|---|---|
| Is this a selected item type or model ID? | `Item.GetItemType` and `Item.GetModelID` | Direct public-item mapping. |
| Is this a selected rarity, dye colour, or minimum value? | Existing Reforged item/data owner for the specific question | Outside the `Item.Mods` contract; migrate only to the current owner already used by the caller. |
| Should an item be identified, salvaged, or stored? | Future native System Settings ID owner | Explicitly outside this FrenkeyLib migration; do not create a Python inventory executor. |
| Does the name contain a selected string? | `Item.GetName` after the existing name-readiness flow | Direct public-item mapping. |
| Is the requirement at most N, optionally for one attribute? | `Item.Properties.GetRequirement` or `Item.Mods.HasMod` | Direct mapping; Reforged owns the lower-is-better direction. |
| Is maximum damage at least N or a selected damage type? | `Item.Properties.GetDamage` or `Item.Mods.HasMod` | Direct mapping; range top-end selection is Reforged-owned. |
| What are a shield's armor values at and below its requirement? | `Item.Properties.GetShieldArmor` | Direct typed mapping; it replaces the legacy raw `ShieldArmor` argument read. |
| What are the named applied upgrades and their slots? | `Item.Mods.GetUpgrades` | Direct read mapping. This replaces JSON rune/weapon-mod identification. |
| Is the named upgrade maxed? | `Item.Mods.IsMaxed` | Direct read mapping. |
| Does an item have a selected named upgrade, slot, or max roll? | `Item.Mods.GetUpgrades`, `GetUpgradeInSlot`, `HasUpgradeInSlot`, and `IsMaxed` | Direct consumption mapping. Use the existing method that expresses the legacy question; do not add a convenience duplicate. |
| Does a consumer need selected named upgrades or slots as part of its rule? | Existing `Item.Mods` public upgrade and matching methods | Direct consumption mapping. Identification is item state, not a migration boundary. |
| Does a legacy weapon rule carry lower/upper range fields? | Numeric `Item.Mods` match-or-better semantics and Item Mods Playground behaviour | Normalize the legacy shape to one direction-aware threshold. Do not migrate ranges, exact-value modes, predicates, or lambda input. |
| Is an item a named skin from `items.json`? | Existing model-ID and name surfaces | Migrate consumers to the existing criteria. Do not create or copy a Frenkey-owned skin catalogue as a migration step. |
| Is a stack full, or which feature action should follow a match? | Not item-mod matching | Feature policy, outside this contract. FrenkeyLib may consume a Reforged verdict but must not alter how the verdict is computed. |

## Migration sequencing

1. Repoint every legacy item/mod question to the existing public `Item.Mods`
   or item method demonstrated by the Playground. Do not introduce a new public
   helper as part of this migration.
2. When a concrete owner concern is reported, inspect the existing Item Mods
   Playground or Mod Parity Scan output for the affected item and public read.
   Do not create a generic sample-item or smoke-test requirement for a source
   cutover.
3. Refit Mark's parser first, then migrate Team Inventory Viewer and retained
   non-inventory Merchant Rules consumers to its item-ID Reforged-consumer
   result or to the same direct public calls. Remove `ModDatabase` and raw
   triple parsing, not merely the import path.
4. Repoint FrenkeyLib consumer code. Remove the legacy modifier catalog and
   match classes only after no production importer remains. The basic utility
   questions use existing public item calls; a paired shield-armor fact is
   exposed by `Item.Properties.GetShieldArmor` because no prior public method
   represented both values.
5. If, and only if, a concrete migrated call cannot be expressed by the
   existing platform, stop there and record the exact missing public contract.
   Do not work around it in FrenkeyLib or Mark's code.

## Non-negotiable migration rules

- No feature code imports `mods_core`, `mods_upgrades`, the encoded-string
  decoder, or `item_mods_src` to decide a rule.
- No feature code calls `GetModifiers` or `GetModifierValues` to implement
  matching. Those are diagnostic compatibility reads, not a policy surface.
- No raw `runes.json`, `weapon_mods.json`, `items.json`, `ModDatabase`, or
  `matches_modifiers` fallback participates in a production verdict.
- Rule input is declarative data only. Numeric modifier values always mean the
  Reforged direction-aware threshold (that value or better); no predicates or
  lambdas are accepted from configuration or consumer code.
- A missing Reforged capability blocks the consumer migration at that
   capability. The fix belongs to the owning Reforged public item surface,
   with parity evidence, before any consumer work continues.

## Verification plan

The source cutover is verified by the public call mapping and targeted static
checks. The Item Mods Playground and Mod Parity Scan remain diagnostic tools:
use their existing output only if a reported item exposes a concrete mismatch
or missing public capability.

Static verification for the cutover must show no production ownership of
`ModDatabase`, legacy `Rune`/`WeaponMod` matching classes, raw
`parse_modifiers`, or raw modifier matching. Run strict Pyright on each changed
Python owner and its changed consumer.
