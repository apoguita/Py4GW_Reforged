# FrenkeyLib Layered Migration Plan

Status: proposed
Scope: complete migration of legacy FrenkeyLib and Mark modifier consumption
into Reforged. Deprecated inventory control, including
`AutoInventoryHandler`, is explicitly excluded.
Authority: current Reforged item source, `Item.Mods`, the Item Mods Playground,
the persistence jail owners, current widget entry points, and legacy FrenkeyLib
as behavioural reference only.

## Outcome

FrenkeyLib becomes a Reforged consumer. It never parses an item modifier,
loads a mod catalogue, applies its own modifier formula, or replaces a Reforged
match result. Mark's parser stops being a raw parser and becomes a Reforged
consumer; it remains only if its callers still need its presentation result.

```text
widget or script
    -> FrenkeyLib feature workflow and UI state
        -> Item.Mods / Item.Properties / Item public methods
            -> Reforged item implementation
                -> native item data

Settings and JsonFactory are direct persistence owners.
PyImGui and the active ImGui helper are direct rendering owners.
```

FrenkeyLib may own non-inventory feature workflow and presentation over an
already supplied item ID. It may not own the answer to a question about the
item's modifiers, upgrades, rolls, slots, or modifier-derived identity, nor
may it become the inventory scanner, item executor, or inventory lifecycle
manager.

## What materially changed from legacy

| Concern | Legacy FrenkeyLib / Mark shape | Reforged migration shape |
|---|---|---|
| Mod evidence | Raw modifier triples decoded in feature code. | `Item.Mods` answers from item ID through its public contract. |
| Names and identities | Local `runes.json` / `weapon_mods.json` catalogues and local model classes. | Reforged exposes named upgrades, slots, values, subtype, and descriptions. |
| Rule result | Parallel feature-side evaluators can override or bypass item-mod rules. | A consumer calls the existing Reforged operation for the question, then applies only feature workflow. |
| Numeric input | Legacy lower/upper or exact-shaped records can imply an independent range evaluator. | One direction-aware threshold: that value or better. Requirements are lower-is-better; other supported values are higher-is-better. |
| Persistence | Custom INI/JSON paths, loaders, save loops, and wrappers. | Direct `Settings` or `JsonFactory` documents with their existing scope and autosave behaviour. |
| UI | Historical facade/texture assumptions and retained legacy state. | Current PyImGui immediate-mode code with state in the sanctioned persistence owner. |
| Inventory authority | FrenkeyLib was shaped to scan inventory and drive identify, salvage, and storage actions. | Explicitly excluded. System Settings owns explicit native identify, salvage, and storage requests; FrenkeyLib is only a prepared consumer base for later rule-policy work. |

This is an ownership migration, not a request to invent a new rule language.
Where the platform already has the needed `Item.Mods` operation, consumers call
it. A real uncovered question is an `Item.Mods` owner gap to prove and add;
consumer-side decoding is never the answer.

## Post-migration inventory boundary

This plan deliberately prepares FrenkeyLib for the next architecture without
making it that architecture. The System Settings inventory project now owns
explicit native execution; its rule-policy layer remains separate:

```text
native System Settings inventory execution
    -> owns explicit identify, salvage, and storage requests
        -> supplies an item ID to rule/presentation consumers
            -> Item.Mods provides item-mod facts and verdicts
                -> FrenkeyLib provides reusable consumer workflow or UI only
```

The initial System Settings contract accepts item IDs, invokes native
`PyInventory` actions, and polls identify completion. It does not select rules,
auto-confirm salvage options, or run on inventory change. Rule-policy settings,
automatic selection, and the final retirement protocol remain follow-on work.
The readiness criterion remains firm: a future rule owner can use FrenkeyLib
without inheriting an inventory loop, snapshot cache, behavior-tree executor,
or a competing item-mod evaluator.

## Fixed decisions

- The legacy tree at `C:\Users\Apo\Py4GW_python_files\Sources\frenkeyLib`
  is behavioural evidence, not code to copy wholesale.
- `Py4GWCoreLib/Item.py::Item.Mods` is the sole public owner of item-mod
  decoding, identifiers, names, values, directions, slots, upgrades, max-roll
  status, and mod predicates.
- The Item Mods Playground is the reference for how a consumer composes the
  existing public item surfaces. Nearby feature modules do not become owners
  merely because they also filter items.
- Numeric modifier input means Reforged's direction-aware threshold: that value
  or better. No ranges, exact-value modes, lambdas, predicates, raw triples, or
  user-supplied executable rule input are migrated.
- `Settings` is the only INI owner and `JsonFactory` is the only structured
  JSON owner. No Frenkey persistence wrapper, raw config handler,
  `configparser`, `open`, or `json.load`/`json.dump` remains in injected feature
  code. Static non-persistence assets retain their actual current owner.
- Inventory handling is being deprecated. `AutoInventoryHandler`, Frenkey
  inventory scanning, item snapshots used for control flow, inventory behavior
  trees, identify/salvage/storage execution, and dependencies retained only for
  those paths are not migration targets.
- System Settings owns the initial explicit native identify, salvage, and
  storage requests. It is not a Frenkey compatibility layer: it accepts item
  IDs and leaves all item-rule decisions with Reforged.
- No bulk overwrite from legacy. Each cutover is additive, reviewed, and
  verified before its legacy implementation is removed.

## Authoritative ownership map

| Concern | Sole owner after migration | Consumer rule |
|---|---|---|
| Raw modifier words and identifier interpretation | `Item.Mods` over its Reforged implementation | FrenkeyLib and Mark never read or compare raw triples. |
| Modifier values, subtype, and better direction | `Item.Mods` | Consumers call `HasMod`, `HasAnyMods`, `HasAllMods`, `GetValues`, or `GetSubtype` as appropriate. |
| Named upgrades, physical slots, and max roll | `Item.Mods` | Consumers call `GetUpgrades`, slot methods, and `IsMaxed`; no rune/weapon-mod catalogue. |
| Game-style explanation | `Item.Mods.GetDescriptions` | UI may render the returned explanation but does not rebuild it from modifier data. |
| Generic item facts | Existing public `Item` and `Item.Properties` methods | Use item type, model, name, rarity, requirement, damage, value, and other facts from their current owners. |
| Non-inventory feature workflow and presentation | FrenkeyLib feature module | Act only on public Reforged answers; do not recalculate a match or own an inventory lifecycle. |
| INI preferences | `Settings` | Construct the required document directly; setters autosave. |
| Structured profiles, layouts, and snapshots | `JsonFactory` | Construct the required document directly; no persistence wrapper or raw path. |
| Ephemeral cross-account commands | established shared-memory owner | Do not use account files as IPC. |
| UI rendering and interaction | `PyImGui` plus the active helper where applicable | Rebuild each frame; do not revive `ImGui_Legacy` or abandoned facades. |

## Known legacy bypasses and their replacement

| Legacy code | What it wrongly owns | Reforged consumer replacement |
|---|---|---|
| `Sources/marks_sources/mods_parser.py` | Raw triple parser; `Rune`, `WeaponMod`, `ModDatabase`; JSON catalogue loading; roll and slot verdicts. | Refit as an item-ID Reforged consumer if callers still need its result. No raw parser or replacement catalogue. |
| `frenkeyLib/LootEx/models.py` and `data.py` | Modifier models, identifier tables, roll ranges, names, and `runes.json`/`weapon_mods.json` ownership. | Item-mod facts come from `Item.Mods`. Preserve only non-mod feature data after its own ownership audit. |
| `frenkeyLib/LootEx/utility.py` | Reads `GetModifierValues` and assigns meaning to `arg1`/`arg2`. | `Item.Properties` for item facts and `Item.Mods` for typed mod facts. |
| `frenkeyLib/ItemHandling/Rules` and `GlobalConfigs` | Parallel rule hierarchy and upgrade matching over snapshots. | Refit reusable mod questions to public Reforged calls only if a non-inventory consumer needs them; no parallel evaluator or fallback. |
| `frenkeyLib/ItemHandling/Items/item_snapshot.py` | Cached raw mods and parsed mod-derived fields for inventory control. | Do not migrate. Future native inventory ownership supplies item IDs and reads required public facts directly. |
| `frenkeyLib/Core/encoded_names.py` | Parallel encoded-string decode implementation. | Use the current owner only when a feature has a real display requirement; it must not decide mod behaviour. |

## Item.Mods consumer contract

Every legacy item-mod request maps to an existing public call before any
consumer code moves.

| Legacy request | Public Reforged call pattern |
|---|---|
| Does this item have one modifier? | `Item.Mods.HasMod`. |
| Does it satisfy all or any selected modifiers? | `Item.Mods.HasAllMods` or `Item.Mods.HasAnyMods`. |
| Is a requirement or damage value good enough? | `Item.Mods.HasMod` with the numeric threshold; direction comes from Reforged metadata. |
| What are the item's readable values or subtype? | `Item.Mods.GetValues` and `Item.Mods.GetSubtype`. |
| Which named upgrades are applied? | `Item.Mods.GetUpgrades`. |
| What occupies a physical upgrade slot? | `Item.Mods.GetUpgradeInSlot` or `HasUpgradeInSlot`. |
| Is a named applied upgrade maxed? | `Item.Mods.IsMaxed`. |
| How should the item be described in UI? | `Item.Mods.GetDescriptions`. |
| What is the item type, model, name, rarity, requirement, or damage? | The current public `Item` or `Item.Properties` owner used by the Playground. |

If a concrete legacy request cannot be expressed by one of these public calls,
the migration stops at that call and records the exact missing `Item.Mods`
contract. The change then belongs in `Item.Mods`, is proved in the Playground
and parity scan, and only then becomes available to consumers. FrenkeyLib and
Mark never receive a workaround API.

## Staged execution plan

### Stage 0: Freeze evidence and establish the cutover ledger

**Purpose:** prevent the partially migrated tree from becoming a second source
of truth.

1. Record the legacy and current relative file inventory, content differences,
   active importers, and entry points.
2. Create and maintain `frenkeylib-stage-0-cutover-ledger.md`, a call-level
   ledger for every FrenkeyLib and Mark mod-related call:
   legacy symbol, caller, question asked, public Reforged call, expected result,
   test item, migration stage, and removal condition.
3. Mark all inventory-control paths as excluded: `AutoInventoryHandler`,
   inventory scanning, snapshots, behavior-tree execution, and identify,
   salvage, or storage actions. Do not fix or test them as part of this
   migration.
4. Baseline current static diagnostics per migration slice. Existing errors are
   recorded separately from new errors.

**Exit gate:** every active consumer has a ledger owner; no implementation code
is copied from legacy merely to make an import resolve.

### Stage 1: Validate the Item.Mods owner before consumer changes

**Purpose:** prove that the authority being consumed is ready for real Frenkey
work rather than assuming the Playground covered every old path.

1. Use the Playground and Mod Parity Scan with representative items for each
   physical upgrade slot: prefix, suffix, inscription, rune, insignia, and
   inherent. Include a matching and a non-matching item for each relevant
   consumer rule.
2. For each ledger row, compare the public answer with the game's composed
   information and the legacy observed result. Record only behavioural parity,
   not legacy implementation detail.
3. Confirm threshold behaviour: requirements use lower-is-better and all other
   supported numeric facts use their Reforged direction. Normalize legacy
   lower/upper range data to this single threshold form.
4. Confirm consumers can obtain every needed answer from item ID and current
   public item surfaces. Do not add an arbitrary-raw-modifier parse path.
5. Where source reveals a genuine gap, change `Item.Mods` first, with type
   annotations, focused checks, Playground evidence, and parity evidence. No
   consumer change is allowed to compensate for a missing owner capability.
6. Execution decision recorded on 2026-08-10: treat the current decoder as the
   authority for consumer migration and add only source-proven owner gaps.
   The Playground and parity scan are diagnostic tools, not per-slice migration
   gates. Consult their output only when it reports a concrete owner gap.

**Exit gate:** every consumer request has a source-verified public call or a
focused-checked `Item.Mods` addition. There is no unreviewed raw-modifier
fallback.

### Stage 2: Remove Mark raw-parser ownership from retained consumers

**Purpose:** ensure no retained FrenkeyLib feature can adopt Mark's duplicate
decoder. This stage does not preserve the parser solely for the excluded
inventory owner.

1. Migrate retained callers to direct public `Item.Mods` reads where that is
   clearer than a compatibility result. `TeamInventoryViewer.py` completed
   this cutover on 2026-08-10 for prefix, suffix, and inherent presentation.
2. Inspect each `MerchantRules.py` parser use by responsibility. Do not create
   a compatibility parser if it belongs to bag scanning, raw-cache construction,
   rule execution, salvage, storage, or other excluded inventory policy.
3. Current source audit result: all remaining `MerchantRules.py` parser and
   catalogue uses are in its inventory policy, including its rule editor,
   inventory cache, exact-signature checks, and salvage planning. No retained
   non-inventory Mark consumer exists to migrate.
4. Retire `ModDatabase`, raw `parse_modifiers`, `Rune`, `WeaponMod`, and their
   JSON catalogues when the native System Settings inventory owner replaces or
   formally retires the MerchantRules execution graph. Do not substitute a
   FrenkeyLib parser in the meantime.

**Exit gate:** no retained consumer owns a Mark raw parser or mod catalogue;
Team Inventory Viewer renders through public Item.Mods calls. The sole raw
importer is explicitly confined to the excluded MerchantRules inventory graph
until its native System Settings replacement is available.

### Stage 3: Refit FrenkeyLib's item-mod consumers

**Purpose:** keep FrenkeyLib as a feature library while removing all competing
item-mod ownership.

1. Replace `LootEx` raw modifier reads in `utility.py`, `data_collection.py`,
   cache construction, filtering, salvaging, trading, and UI summaries with
   `Item.Mods`, `Item.Properties`, and public `Item` calls.
2. Replace `LootEx` catalogue-backed rune and weapon-mod selection with named
   upgrades, slots, and max status from `Item.Mods`. The UI consumes names and
   descriptions returned by Reforged; it does not construct a second mod model.
3. Refit an `ItemHandling` rule or global-config criterion only where a
   non-inventory Frenkey consumer genuinely needs it. It may compose public
   answers, but cannot carry inventory execution, `ModifierInfo`, upgrade
   parsers, snapshot-derived mod properties, or catalogue comparison.
4. Do not migrate `BTNodes`, inventory handler, or snapshot paths. A future
   native System Settings ID owner supplies the item ID and owns identify,
   salvage, and storage; no Frenkey compatibility path may stand in for it.
5. Repoint any remaining `Core` helper that makes a modifier-derived decision.
   Display-only encoded-name work is separate and may use its current owner
   after the item-mod cutover is complete.
6. Remove legacy mod classes, hand-authored identifier tables, parser functions,
   and duplicate `runes.json`/`weapon_mods.json` data only after the import
   scan is clean.

**Exit gate:** FrenkeyLib contains no modifier decoder, matcher, range table,
slot table, or JSON-backed mod catalogue. Every mod-derived feature result is
traceable to one public Reforged call.

### Stage 4: Migrate persistence without a third storage system

**Purpose:** move Frenkey feature state into the required jails while retaining
account/global semantics.

1. Inventory every legacy read/write, filename, scope, schema, and caller.
   Classify it before code moves:

   | Data kind | Destination |
   |---|---|
   | Small scalar preference, window toggle, hotkey, geometry | Direct `Settings` document. |
   | Structured profile, rule selection, layout, cached user choice | Direct `JsonFactory` document. |
   | Static game/mod fact | Reforged source owner, never user persistence. |
   | Live multibox message | shared-memory owner, never disk. |
   | Large relational/history data | existing database owner, only when the data genuinely requires it. |

2. Assign each document an account or global scope from its actual meaning.
   Account preferences follow the logged-in account; machine-wide shared layouts
   and profiles use global scope. Do not infer scope from the old path.
3. Replace custom `load`, `save`, throttle, directory creation, `open`,
   `json.load`, `json.dump`, and INI handlers with direct concrete owner calls.
   Use the owners' autosave; do not add a feature save loop.
4. Treat legacy user-data import as a separate, owner-approved conversion path.
   Injected Frenkey code never opens an old arbitrary file to import it. The
   converter must write only through the sanctioned owner.
5. Verify fresh defaults, existing-state migration, account isolation, global
   sharing, document reload, and shutdown persistence for each moved document.

**Exit gate:** no Frenkey feature owns a raw persistent file path or file I/O;
all persisted feature data is reachable only through `Settings`, `JsonFactory`,
or the approved database owner.

### Stage 4 execution record: PartyQuestLog settings

On 2026-08-10, `Sources/frenkeyLib/PartyQuestLog/settings.py` was reduced to
an in-memory feature state object over the existing global
`Settings("Widgets/Config/PartyQuestLog.ini", "global")` document. The legacy
filesystem existence probe, save-request state, feature throttle, and
per-frame/disable flush calls were removed. Changed UI state now writes with
the typed `Settings` setters, whose persistence lifecycle is the owner.

Existing section/key names and global scope were preserved. `python -m
py_compile` and focused strict Pyright passed for the settings module and its
widget entry point. No generic injected-client toggle or restart check is a
migration gate; investigate only a concrete reported feature issue.

### Stage 5: Migrate live feature slices before dormant UI

**Purpose:** restore reachable functionality in independent, reviewable units.

Use this order, keeping each slice logic -> persistence -> UI -> live test:

1. `MultiBoxing`: current widget imports it directly; move configuration to
   the jails, retain current inter-client transport ownership, then port UI.
2. `PartyQuestLog`: migrate its custom INI state to `Settings`, then its UI and
   quest cache behaviour.
3. `SulfurousRunner`: migrate settings, direct item/UI dependencies, and colour
   tuples, then validate path and flag rendering.
4. `Polymock`: migrate its state/data/UI dependencies after the reusable item
   and persistence work is stable.
5. `LootEx`: restore only reusable, non-inventory domain behaviour in smaller
   slices (profiles, item presentation, filtering, and rule presentation).
   Merchant/trader views may show Reforged answers but may not execute
   inventory work. Do not migrate inventory scans, identification, salvage,
   storage, crafting execution, or its 6,000-line GUI before its consumer
   model and persistence have passed their gates.
6. `Py4GWLibrary` and `Drafts`: inventory feature intent against the current
   launchpad/widget system. Port only real supported functionality into its
   current owner; historical prototypes are documented rather than made live.

**Exit gate per slice:** the widget imports without legacy persistence or mod
ownership and has clean targeted static diagnostics. Existing runtime tools are
diagnostic only when a concrete feature issue is reported.

### Stage 5 source audit: direct feature roots

The 2026-08-10 source audit found the following direct widget roots after the
item-mod cutovers:

- `MultiBoxing` already uses global `Settings` for scalar preferences, global
  `JsonFactory` for layouts, and shared memory for inter-client commands.
- `PartyQuestLog` was migrated in the Stage 4 execution record above.
- `SulfurousRunner` already uses the global `Settings` document directly; its
  path and waypoint data are static feature data, not user persistence.
- `Polymock` has no user-persistence path or item-mod consumer. Its static
  combat data is feature data and its current UI uses PyImGui plus the active
  `Py4GWCoreLib.ImGui` texture helper through `frenkeyLib.Core.gui`. That
  helper carries no item-mod, inventory, or persistence ownership.
- `Py4GWLibrary` is not imported by a current root. Its `Settings.find` calls
  already consume the sanctioned owner, so it is dormant rather than a
  persistence migration target.
- `Drafts` contains historical scripts that still create old INI directories.
  They have no current importer and remain explicitly out of scope rather than
  becoming a second UI or storage system.

No direct root imports the retained LootEx raw modifier model. Remaining
LootEx and Merchant raw-modifier ownership stays confined to the explicitly
excluded inventory domain until its native System Settings ID replacement is
authorized and available.

The focused retained-root certification also found no raw modifier/parser,
inventory-handler/snapshot, or raw persistence dependency. `MerchantRules` is
the sole production importer of Mark's raw parser and remains wholly deferred
at the inventory boundary; it is not a reason to recreate a Frenkey-owned
consumer path.

### Stage 6: Rebuild UI on the active immediate-mode surface

**Purpose:** preserve supported interaction without attempting to resurrect
retired textured/facade architecture.

1. Keep `update()` for non-UI work and `draw()`/`main()` for per-frame UI.
   Neither is a one-time initialization hook.
2. Recreate windows with direct `PyImGui` and the active `Py4GWCoreLib.ImGui`
   helper only where its current source supports the required operation.
3. Keep window state in the appropriate `Settings` or `JsonFactory` document;
   do not create UI-local persistence or assume abandoned facade methods exist.
4. Convert colours and geometry to current typed tuples. Pair every pushed
   style, font, ID, child, table, popup, and window scope with its matching pop
   or end in the same frame path.
5. Make each UI render Reforged descriptions, names, slots, and rule outcomes;
   UI code never decodes modifier content itself.

**Exit gate:** each migrated UI has balanced ImGui stacks and persistent state
from the sanctioned owner. A live diagnostic is used only for a concrete
reported UI issue.

### Stage 7: Remove severed ownership and certify the migration

**Purpose:** make the result enforceable rather than merely functional.

1. Run a retained-consumer search for forbidden dependencies:

   ```text
   ModDatabase
   raw parse_modifiers
   Rune / WeaponMod matching classes
   item_mods_src
   mods_core / mods_upgrades in production consumer code
   GetModifiers / GetModifierValues used for matching
   runes.json / weapon_mods.json used for item-mod decisions
   raw open/json/configparser persistence in Frenkey feature code
   Frenkey inventory scan, snapshot, or action-executor dependencies in a
   migrated consumer
   ```

2. Remove each legacy owner only after its final importer is migrated or its
   excluded execution graph is replaced by the native System Settings owner.
   Delete data only after generated-data consumers and documentation no longer
   name it.
3. Update the FrenkeyLib audit, item-mod documentation map, persistence records,
   and widget documentation to show the final owners and removed paths.
4. Re-run focused Pyright for every changed Python slice, formatter/linter
   checks used by that owner, and the applicable standalone tests. There is no
   repository-wide runner, so report each command and result by slice.
5. Use existing injected-client diagnostics only to investigate a concrete
   reported Item.Mods, widget, persistence, or non-inventory workflow issue.

**Exit gate:** no duplicate item-mod authority remains, every live consumer is
on public Reforged calls, all Frenkey persistence uses the jails, the active UI
is current-surface only, and verification evidence is recorded per slice.

## Test and evidence matrix

| Layer | Offline evidence | Existing live diagnostic, when a concrete issue is reported |
|---|---|---|
| Item.Mods owner | Typed API usage and focused checks for every changed helper. | Item Mods Playground and Mod Parity Scan. |
| Mark cutover | No raw parser/catalog ownership; widget-local checks where available. | Team inventory display and Merchant Rules. |
| Frenkey mod consumers | No raw matching/catalog data; targeted Pyright per module. | Relevant consumer UI and rule outcome. |
| Persistence | Schema/default/scope/reload checks through concrete owners. | Fresh/existing account behaviour and global sharing. |
| UI | Targeted static checks and stack-path review. | Draw, interaction, popup/focus, persistence, and empty/error states. |

## Completion criteria

The migration is complete only when all of the following are proven in the
current worktree and applicable live runtime:

1. `Item.Mods` owns every item-mod fact and predicate used by FrenkeyLib, Mark,
   and their widgets.
2. Retained FrenkeyLib and Mark consumers are consumers only; no raw parser,
   JSON catalogue, duplicate mod class, identifier table, or fallback verdict
   remains outside the explicitly quarantined inventory graph.
3. No deprecated inventory path (`AutoInventoryHandler`, inventory scans,
   snapshots, BT nodes, identify, salvage, or storage execution) was revived
   or made a hidden dependency of the new work.
4. Every Frenkey persistence path uses `Settings`, `JsonFactory`, or the
   explicitly approved database owner, with correct scope.
5. Each retained widget has a current-PyImGui implementation; live diagnostics
   are consulted only when a concrete issue is reported.
6. Static checks and focused checks are reported for each changed slice; no
   result is inferred from an unrelated green check.
7. FrenkeyLib is ready for System Settings rule-policy work because its
   retained consumers accept public Reforged item facts without owning any
   inventory lifecycle or action executor.

## Immediate next implementation slice

The retained consumer cutover is complete: Team Inventory Viewer uses direct
public reads, and the remaining Mark parser importer is wholly inside the
explicitly excluded MerchantRules inventory graph. System Settings now owns
explicit native execution; the next follow-on slice is a public-Reforged
rule-policy integration that replaces or retires that graph rather than
receiving a Frenkey compatibility parser.
