# FrenkeyLib Layered Migration Plan

Status: proposed
Scope: complete migration of legacy FrenkeyLib and Mark modifier consumption
into Reforged. The deprecated `AutoInventoryHandler` is explicitly excluded.
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

FrenkeyLib may own feature workflow: which already-matched item is displayed,
kept, sold, queued, or announced. It may not own the answer to a question about
the item's modifiers, upgrades, rolls, slots, or modifier-derived identity.

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
- `AutoInventoryHandler`, its salvage behaviour, and dependencies retained only
  for it are not migration targets.
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
| Feature actions and workflow | FrenkeyLib feature module | Act only on public Reforged answers; do not recalculate a match. |
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
| `frenkeyLib/ItemHandling/Rules` and `GlobalConfigs` | Parallel rule hierarchy and upgrade matching over snapshots. | Feature workflow calls public Reforged methods; no parallel modifier evaluator or fallback. |
| `frenkeyLib/ItemHandling/Items/item_snapshot.py` | Cached raw mods and parsed mod-derived fields for the deprecated inventory path. | Do not migrate for `AutoInventoryHandler`; future features read their required public facts directly. |
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
2. Create a call-level ledger for every FrenkeyLib and Mark mod-related call:
   legacy symbol, caller, question asked, public Reforged call, expected result,
   test item, migration stage, and removal condition.
3. Mark all `AutoInventoryHandler`-only paths as excluded. Do not fix or test
   them as part of this migration.
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

**Exit gate:** every live consumer request has a verified public call or a
separately verified `Item.Mods` addition. There is no unreviewed raw-modifier
fallback.

### Stage 2: Remove Mark parser ownership

**Purpose:** eliminate the catalog-backed parser before FrenkeyLib begins using
the same data by accident.

1. Migrate `Widgets/Guild Wars/Items & Loot/TeamInventoryViewer.py`.
   Replace `ModDatabase`, `parse_modifiers`, `MatchedRuneInfo`, and
   `MatchedWeaponModInfo` with direct public item-mod reads. Derive displayed
   prefix, suffix, inherent, slot, and max status from `Item.Mods`.
2. Migrate the Mark-parser branches of
   `Widgets/Guild Wars/Items & Loot/MerchantRules.py`. Replace raw modifier
   tuple extraction and parser-derived upgrade identities with `Item.Mods`
   reads. Preserve its feature-specific execution policy, but make public
   Reforged data the only evidence for that policy.
3. Search all production Python for imports of `mods_parser`, `ModDatabase`,
   `Rune`, `WeaponMod`, `MatchedRuneInfo`, `MatchedWeaponModInfo`, and
   `parse_modifiers`. Repoint every remaining consumer in the same conceptual
   cutover.
4. Delete or archive Mark's parser and its duplicate catalog inputs only when
   no production importer or generated-data dependency remains.

**Exit gate:** no production code imports the Mark parser or its mod catalogue;
Team Inventory Viewer and Merchant Rules render/act correctly in a live client.

### Stage 3: Refit FrenkeyLib's item-mod consumers

**Purpose:** keep FrenkeyLib as a feature library while removing all competing
item-mod ownership.

1. Replace `LootEx` raw modifier reads in `utility.py`, `data_collection.py`,
   cache construction, filtering, salvaging, trading, and UI summaries with
   `Item.Mods`, `Item.Properties`, and public `Item` calls.
2. Replace `LootEx` catalogue-backed rune and weapon-mod selection with named
   upgrades, slots, and max status from `Item.Mods`. The UI consumes names and
   descriptions returned by Reforged; it does not construct a second mod model.
3. Refit `ItemHandling` rule and global-config criteria to public calls. Keep
   action selection as feature workflow, but remove `ModifierInfo`, upgrade
   parsers, snapshot-derived mod properties, and catalog comparison.
4. Do not migrate `BTNodes` or snapshot paths merely because
   `AutoInventoryHandler` uses them. If a non-deprecated Frenkey feature needs
   one, refit that feature to public item calls without reviving the deprecated
   inventory path.
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
5. `LootEx`: restore domain behaviour in smaller slices (profiles, cached item
   display, filtering, merchant/trader features, crafting, salvaging, then UI)
   on the consumed Reforged surfaces. Do not revive its 6,000-line GUI before
   its model and persistence have passed their gates.
6. `Py4GWLibrary` and `Drafts`: inventory feature intent against the current
   launchpad/widget system. Port only real supported functionality into its
   current owner; historical prototypes are documented rather than made live.

**Exit gate per slice:** the widget imports without legacy persistence or mod
ownership, has clean targeted static diagnostics, and passes an injected-client
smoke test for its main workflow and configuration persistence.

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

**Exit gate:** each migrated UI has balanced ImGui stacks, persistent state from
the sanctioned owner, and a live-client smoke test for its normal and empty
states.

### Stage 7: Remove severed ownership and certify the migration

**Purpose:** make the result enforceable rather than merely functional.

1. Run a repository search for forbidden dependencies:

   ```text
   ModDatabase
   raw parse_modifiers
   Rune / WeaponMod matching classes
   item_mods_src
   mods_core / mods_upgrades in production consumer code
   GetModifiers / GetModifierValues used for matching
   runes.json / weapon_mods.json used for item-mod decisions
   raw open/json/configparser persistence in Frenkey feature code
   ```

2. Remove each legacy owner only after its final importer is migrated and its
   relevant behavioural evidence passes. Delete data only after generated-data
   consumers and documentation no longer name it.
3. Update the FrenkeyLib audit, item-mod documentation map, persistence records,
   and widget documentation to show the final owners and removed paths.
4. Re-run focused Pyright for every changed Python slice, formatter/linter
   checks used by that owner, and the applicable standalone tests. There is no
   repository-wide runner, so report each command and result by slice.
5. Run injected-client verification for Item Mods parity, each active widget,
   persistence reload, account/global isolation, and the action workflows that
   consume the migrated item decisions.

**Exit gate:** no duplicate item-mod authority remains, every live consumer is
on public Reforged calls, all Frenkey persistence uses the jails, the active UI
is current-surface only, and verification evidence is recorded per slice.

## Test and evidence matrix

| Layer | Offline evidence | Live injected-client evidence |
|---|---|---|
| Item.Mods owner | Typed API usage and focused tests for every changed helper. | Item Mods Playground and Mod Parity Scan against game tooltip text. |
| Mark cutover | No raw parser/catalog ownership; widget-local tests where available. | Team inventory display and Merchant Rules use correct named upgrades/slots. |
| Frenkey mod consumers | No raw matching/catalog data; targeted Pyright per module. | Representative item actions and summaries use public Reforged answers. |
| Persistence | Schema/default/scope/reload checks through concrete owners. | Fresh and existing account behaviour; global sharing where intended. |
| UI | Targeted static checks and stack-path review. | Draw, interaction, popup/focus, persistence, and empty/error states. |

## Completion criteria

The migration is complete only when all of the following are proven in the
current worktree and applicable live runtime:

1. `Item.Mods` owns every item-mod fact and predicate used by FrenkeyLib, Mark,
   and their widgets.
2. FrenkeyLib and Mark code are consumers only; no raw parser, JSON catalogue,
   duplicate mod class, identifier table, or fallback verdict remains.
3. Deprecated `AutoInventoryHandler` paths were not revived or made a hidden
   dependency of the new work.
4. Every Frenkey persistence path uses `Settings`, `JsonFactory`, or the
   explicitly approved database owner, with correct scope.
5. Each live widget has a current-PyImGui implementation and a recorded smoke
   test.
6. Static checks, focused tests, and live verification are reported for each
   changed slice; no result is inferred from an unrelated green check.

## Immediate next implementation slice

Start Stage 1 and Stage 2 together for the narrowest valuable cutover:
`mods_parser` becomes an item-ID Reforged consumer and
`TeamInventoryViewer` consumes that result or the same public reads. It already
has an item ID and persists through `JsonFactory`, so this proves the consumer
direction without touching deprecated inventory automation, legacy raw
persistence, or Frenkey's large UI.
