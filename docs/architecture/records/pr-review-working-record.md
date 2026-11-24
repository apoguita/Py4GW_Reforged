### [#220 - Add enable toggles for the Skillbar+ overlay and effect durations](https://github.com/apoguita/Py4GW_Reforged/pull/220)

- Review verdict: REQUEST CHANGES. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `cbf2bf524a14301e38748664e5687602659075a5`; changes: 5 files, +29/-4.
- Files: `Py4GWCoreLib/py4gwcorelib_src/system_settings/copy_catalog.py`, `Py4GWCoreLib/py4gwcorelib_src/system_settings/skillbar_plus/config_ui.py`, `Py4GWCoreLib/py4gwcorelib_src/system_settings/skillbar_plus/model.py`, `Py4GWCoreLib/py4gwcorelib_src/system_settings/skillbar_plus/persistence.py`, `Py4GWCoreLib/py4gwcorelib_src/system_settings/skillbar_plus/runtime.py`.
- Classification (derived from the recorded decision; the prior session did not record one): Skillbar+ settings and UI change; the recorded verdict requests changes on an unguarded immediate-mode disabled stack.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Decision and required direction: _draw_skillbar and _draw_effects call begin_disabled and then perform UI and settings work before end_disabled without guaranteed cleanup. An exception in that work can skip end_disabled and leave the immediate-mode disabled stack unbalanced. Wrap the disabled scopes using the established scoped API or guaranteed try/finally cleanup so the stack is restored on every path. Defaults, save/load and copy wiring otherwise retain prior enabled behavior.
- Independent checks: text diff and relevant current owner inspected; previous patch applicability checks are recorded above. No candidate-specific type check, binary inspection, live-client test or GitHub review was performed.

- Release placement (derived from the recorded verdict; the prior session did not state one): after the requested changes in the decision above are addressed..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: request-changes confirmed. The diff pairs `begin_disabled` with a trailing `end_disabled` and no `try/finally`, so an exception in the settings widgets still leaves the immediate-mode disabled stack open; Pyright 0 versus a 0 base.

### [#219 - Restore HeroAI state when a botting tree goes idle or finishes](https://github.com/apoguita/Py4GW_Reforged/pull/219)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `e299c8776cb93aa80297931eb7ee0bd497255883`; changes: 3 files, +28/-5.
- Files: `Py4GWCoreLib/BottingTree.py`, `Py4GWCoreLib/botting_tree_src/heroai.py`, `Py4GWCoreLib/botting_tree_src/ticks.py`.
- Classification: lifecycle fix in the BottingTree owner plus a deliberate multibox behavior change.
- Verified: `_release_runtime_state` centralizes `RestoreWidgetStates`, `RestoreAutoInventoryHandlerState`, `_restore_heroai_widget_after_headless` and `_sync_multibox_heroai_widget(False)`; `Stop` now delegates to it, and the planner SUCCESS and FAILURE completion paths in `ticks.py` call it so a run that ends on its own restores the account exactly as a manual stop does (previously those paths could leave the headless HeroAI widget disabled, and a later `Stop` could not fix it because it is guarded by `self.started`). The ticks protocol gains the method declaration. In the HeroAI mixin, a disable request now forgets the last broadcast state and returns without sending `DisableWidget`, so followers keep fighting with their own widget instead of being shut off at every stop, and the next start re-announces the enabled state.
- Notes: this changes multibox follower behavior on purpose — the tree no longer disables followers' HeroAI when idle. Completion paths deliberately do not `Reset()` or clear pending messages, keeping the fix narrow.
- Independent checks: exact head fetched and diffed; both completion call sites, the extracted helper and the mixin branch read; Pyright at head: `BottingTree` 18 equal to base, `heroai`/`ticks` 0. No test file; no live-client test or GitHub review.
- Unresolved: whether forgetting the broadcast state can leave a follower whose widget was toggled by another command in a stale state until the next start.

### [#218 - Add Zaishen Bounty rebuilt on BottingTree](https://github.com/apoguita/Py4GW_Reforged/pull/218)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `09cc0217044eb50583c2ac9fddd7293e2ea821d6`; changes: 2 files, +3078/-1.
- Files: `Sources/ZaishenBounty/ChungtheAttuned.py`, `Widgets/Automation/Bots/Missions/ZaishenBounty_BT.py`.
- Classification: new single-purpose widget on the BottingTree framework, with a small companion data change.
- Verified: the widget is built on `BottingTree` (`from Py4GWCoreLib.BottingTree import BottingTree`), keeps its persisted options on the concrete `Settings(f'{INI_PATH}/{INI_FILENAME}', 'account')` document inside the settings jail, and expresses restock and gold behavior through `SharedCommandType` messages (`RestockConset`, `RestockAllPcons`, `RestockResurrectionScroll`, `WithdrawGold`) rather than direct shared-state writes or private file handling. No raw file I/O, window-geometry overrides or parallel stores appear in the new file.
- Notes: the new file reports 14 Pyright diagnostics, all type-cleanliness looseness in new code — `object`-typed values passed to `int`/`float` converters, `object | tuple[()]` iterables, an `int` passed where `MessageType` is expected, and an `ActionNode` callback signature that the node itself documents as supported (`action_fn()` or `action_fn(node)`). None of them evidences a runtime defect, but the changed-file check is not clean, so they should be addressed or explicitly justified.
- Independent checks: exact head fetched and scanned for persistence, IO, window and messaging patterns; imports and the settings document read; Pyright at head: widget 14, companion file 0. No test file; no live-client test or GitHub review.
- Unresolved: whether the Zaishen Bounty flow is correct in live play; the widget carries no test and the snapshot has no live evidence for it.

### [#216 - PyQuishAI_BT: multibox staging, restock, gold and party flow](https://github.com/apoguita/Py4GW_Reforged/pull/216)

- Review verdict: REQUEST CHANGES. Release placement: after the file-backed diagnostics are replaced and the change is split. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `c7acc92ff5f97d0841f7cda383c34d3071a90eaf`; changes: 3 files, +2474/-358.
- Files: `.gitignore`, `Sources/aC_Scripts/PyQuishAI_maps/Proph_Maguuma/SageLands.py`, `Widgets/Automation/Bots/Vanquish/PyQuishAI_BT.py`.
- Classification: large extension of the BottingTree vanquish consumer with multibox staging, remote restock, gold handling and party flow, plus one route-data repair.
- Verified: the `SageLands.py` change repairs a genuine defect — the snapshot file lacks the comma after `(21818.0, -1878.0)`, which Python parses with `SyntaxWarning: 'tuple' object is not callable` and which raises `TypeError` when the module executes, so that route could not load before this PR. `PyQuishAI_BT.py` grows by roughly 2,460 net lines: `_scan_map_catalog`, shared-memory census helpers, `_remote_restock_commands`/`_remote_restock_node` driving `SharedCommandType.Restock*`, `_keep_gold_node` with `WithdrawGold`, and party staging through the top-level flow.
- Findings and required direction: the new enemy-log pipeline (`_enemy_log_path`, `_enemy_log_begin`, `_sample_enemy_log`, `_flush_enemy_log`) and the `PyQuishAI_route_review_*.md` reports write files next to the widget, and the PR's own `.gitignore` addition admits those artifacts. That is the forbidden custom file-backed diagnostic mechanism; replace it with approved console/runtime diagnostics, or present it as a separate, explicitly authorized infrastructure change — an ignore rule is not authorization. Split the delivery: multibox staging, remote consumable restock, gold handling and encounter logging are independent outcomes inside a 2,800-line single-file extension, and each needs its own review and revert path. Address or justify the 12 new Pyright diagnostics in the widget (the changed-file check must be clean per the project rule).
- Independent checks: exact head fetched and diffed; the route repair verified by compiling the base file and observing the tuple-call warning; the added helper families and command paths enumerated; Pyright at head: widget 12 versus a 0 base, route 0. No test file; no live-client test or GitHub review.
- Unresolved: whether remote restock/gold commands sequence correctly across accounts in live play, and whether the enemy log is required by any consuming workflow.

### [#213 - Add two Prophecies reward trophies to the loot filter catalog](https://github.com/apoguita/Py4GW_Reforged/pull/213)

- Review verdict: REQUEST CHANGES. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `277c06eeed5a8bcdc3c81623653941365f9712b2`; changes: 2 files, +5/-1.
- Files: `Py4GWCoreLib/py4gwcorelib_src/system_settings/loot_filters/catalog.py`, `Py4GWCoreLib/py4gwcorelib_src/system_settings/loot_filters/expected_types.py`.
- Classification (derived from the recorded decision; the prior session did not record one): Loot-filter catalog data change bundled with an independent existing-item expected-type correction.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Decision and required direction: catalog.py adds two reward trophies, while expected_types.py also independently changes existing Trick_Or_Treat_Bag model 28434 from type 33 to 9. The existing-item correction is not necessary to add the two new trophies, and the author offers sibling item types rather than direct evidence of this item type. Move the independent existing-item correction to a separate change so each behavior can be evaluated and reverted independently.
- Independent checks: text diff and relevant current owner inspected; previous patch applicability checks are recorded above. No candidate-specific type check, binary inspection, live-client test or GitHub review was performed.

- Release placement (derived from the recorded verdict; the prior session did not state one): after the requested changes in the decision above are addressed..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: request-changes confirmed. 38613/38614 are free at the snapshot base and the `28434` 33->9 correction is still bundled with the two additions; Pyright 0 versus a 0 base.

### [#214 - Fix item model texture file names for tonics and add two reward trophies](https://github.com/apoguita/Py4GW_Reforged/pull/214)

- Review verdict: BLOCK. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `1db4c377b1a9219ee9ebe795891ebbc8d79f7dd1`; changes: 5 files, +2/-0.
- Files: `Assets/Textures/Item Models/29241-Yuletide_Tonic.png`, `Assets/Textures/Item Models/31021-Mischievous_Tonic.png`, `Assets/Textures/Item Models/38613-Stalkers_Ration.png`, `Assets/Textures/Item Models/38614-Birds_Eye_Compass.png`, `Py4GWCoreLib/enums_src/Model_enums.py`.
- Classification (derived from the recorded decision; the prior session did not record one): Binary texture assets plus duplicate ModelID members shared with #150.
- Patch check: binary data not available for this check.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Decision and required direction: The text diff shows two texture renames, two new binary textures and two ModelID additions that duplicate PR #150. The retrieved diff does not include the new image bytes, so their actual contents and applicability were not inspected. Obtain the exact two head-version image files for review; coordinate the duplicate ModelID members with #150 before combining these PRs.
- Independent checks: text diff and relevant current owner inspected; previous patch applicability checks are recorded above. No candidate-specific type check, binary inspection, live-client test or GitHub review was performed.

- Release placement (derived from the recorded verdict; the prior session did not state one): after the ModelID duplication with #150 is coordinated and the binary texture contents are reviewed..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: block confirmed. The two new textures remain uninspected binaries and `Birds_Eye_Compass`/`Stalkers_Ration` are the same members #150 adds; Pyright 0 versus a 0 base.

### [#212 - Fix Kessex Peak transit route](https://github.com/apoguita/Py4GW_Reforged/pull/212)

- Review verdict: APPROVE for the submitted source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `28377fa0b552f002542f4a1be28f5a40602f7b73`; changes: 2 files, +178/-13.
- Files: `Examples and tests/tests/test_kessex_peak_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/Proph_Kryta/KessexPeak.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): - Dungeon Playbook v3 independent review ? PASS on commit `28377fa0b552f002542f4a1be28f5a40602f7b73`.
- Classification: semantic route-data change; first-batch candidate. No changes requested.
- Verified: Corrects KessexPeak_ids and extends KessexPeak_transit_path, plus a focused route test. Both Simple_Vanquish.py and PyQuishAI_BT.py look up map-specific _ids names, confirming the old CursedLands_ids declaration was not found under KessexPeak. No shared runtime code is changed. Actual route clearance and portal crossing remain unverified.
- Independent checks: reviewed full patch and current route loader; patch applied with the other four in an isolated copy; changed route compiled and Pyright reported 0 errors, 0 warnings, 0 information. The author-reported tests were not independently rerun.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session (commit-safe standalone): head `28377fa0` matches; the transit path gains captured detour points and the ids declaration is corrected, with the added route test reporting 0 diagnostics; Pyright 0 versus a 0 base.

### [#211 - Add captured Mourning Veil Falls blessing](https://github.com/apoguita/Py4GW_Reforged/pull/211)

- Review verdict: APPROVE for the submitted source change. Release placement: after #192. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `96329fa8ffa7f5cdd01ef2e66c02f3e7f7d21c3d`; changes: 2 files, +72/-0.
- Files: `Examples and tests/tests/test_mourning_veil_falls_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/Factions_EchovaldForest/MourningVeilFalls.py`.
- Classification: semantic route-data addition plus a route test; contained to one map module; no shared code changes.
- Verified: same record shape as #207 (faction `kurzick`, `target_xy` (-16475.0, -6496.0), model 3477) wrapped around the existing coordinate route by rebinding. `Simple_Vanquish.py:727-754` resolves the attribute by map name, so the wrapper is what both consumers receive. At base the unknown key is ignored silently by `Simple_Vanquish` and raises `ValueError` in `PyQuishAI_BT`, which lists the map at `PyQuishAI_BT.py:127`. Under #192 it executes as a faction blessing.
- Dependency resolution: the description states the route is route-only and must merge after its dependencies; the executable dependency is #192. #148 is needed only if effect verification is requested, which the record does not do.
- Independent checks: exact head fetched and diffed; consumers and owner contracts inspected; Pyright at head 0 errors, 0 warnings on both changed files. The author test was read for shape but not rerun; no live-client test or GitHub review.
- Unresolved: capture validity, priest reachability, and portal clearance; the PR is a draft and was not treated as reviewable-complete by its author.

### [#210 - Add captured Sparkfly Swamp vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/210)

- Review verdict: APPROVE for the submitted source change. Release placement: after #124, #148 and #192. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `34a1e7ea2aef26cb28f1701992478760ae448845`; changes: 3 files, +487/-0.
- Files: `Examples and tests/tests/test_sparkfly_swamp_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/EOTN_Tarnished_Coast/SparkflySwamp.py`, `Sources/aC_Scripts/PyQuishAI_maps/THIRD_PARTY_NOTICES.md`.
- Classification: additive new route data plus attribution file and a route test; no shared code, API, or lifecycle change.
- Verified: the route uses `literal_path`, `path` and an `asuran_blessing` mapping (model 6806, `buttons: 0`, Asuran effect ids, encoded identity). `literal_path` executes only after #124 adds it to `Simple_Vanquish._handle_keyword`; `asuran_blessing` is one of #192's `ROUTE_BLESSING_KEYS` and its captured fields are consumed by #148's `TakeBlessing(captured_blessing=...)`. SparkflySwamp is absent from `PyQuishAI_BT`'s map table, so Simple Vanquish is the only consumer and no BottingTree parity gap applies. `THIRD_PARTY_NOTICES.md` is new and records the MIT donor (`mrdomrocks/Guild-Wars-Vanquish-Bot`, commit `330b8f50`); the route file cites it in its header.
- Dependency resolution: the description names #124, #148 and #192, matching the keys the record actually uses.
- Independent checks: exact head fetched and diffed against the snapshot base; base consumers and owner contracts inspected; Pyright at head 0 errors, 0 warnings on both Python files. No author test rerun, live-client test, or GitHub review.
- Unresolved: the file states supervised collision and blessing validation is pending; capture identity, terrain clearance and effect verification cannot be proven statically. The `ASURAN_BODYGUARD_EFFECT_IDS` tuple repeats nine effect ids that also appear in #194's Norn set (`2469-2472`, `2551`, `2591-2594`), which is unexpected for a faction-specific effect group and should be justified by the author before merge.

### [#209 - fix(woc): adding loot filtering, timeout and cupcake fixes](https://github.com/apoguita/Py4GW_Reforged/pull/209)

- Review verdict: REQUEST CHANGES. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `6685ee024d41adb6efc74686fae7065c032353c2`; changes: 1 files, +107/-50.
- Files: `Widgets/Automation/Bots/Farmers/Trophies/WOC/MinisterialCommendations_BT.py`.
- Classification (derived from the recorded decision; the prior session did not record one): Farm-bot loot-filter and logging change bundled into one widget.
- Patch check: not run.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Decision and required direction: _want_commendations_node adds the model to singleton LootFilters.live.added_model_ids. The existing shared filter uses that set for all consumers, and map change only clears session item IDs; the new addition therefore remains wanted beyond the bot until live state is reset. Provide ownership-scoped cleanup through the loot filter owner without clearing other scripts settings. The diff also combines independent logging, cupcake, timeout, recovery and loot outcomes; separate them so a fix can be reverted without removing the others.
- Independent checks: text diff and relevant current owner inspected; previous patch applicability checks are recorded above. No candidate-specific type check, binary inspection, live-client test or GitHub review was performed.

- Release placement (derived from the recorded verdict; the prior session did not state one): after the requested changes in the decision above are addressed..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: request-changes confirmed. The diff adds a logging toggle and gates `BT.LogMessage`/timeouts on it while the shared `added_model_ids` ownership finding stands; Pyright improved from 1 to 0 errors.

### [#208 - Add Plains of Jarin eight-member departure](https://github.com/apoguita/Py4GW_Reforged/pull/208)

- Review verdict: REQUEST CHANGES. Release placement: after #148 and #192, and only after the shared-consumer findings below are repaired. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `51142030b436eeb78d986326d9d72ac3bec9cc77`; changes: 2 files, +150/-3.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/NF_Istan/PlainsofJarin.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`.
- Classification: semantic route-data change plus feature orchestration added to the shared widget; not a contained route-only change.
- Verified: the route converts three coordinate `bless` records to mappings (`interaction_mode: first`, `initial_choice_settle_s`, effect ids, encoded identities), which at base raise `KeyError` in `Simple_Vanquish._handle_keyword` and `ValueError` in `PyQuishAI_BT._coordinate`; they execute only through #192 and, for the captured path, #148. The widget gains a `departure_setup` slot on `QueuedVanquish`, loaded via `getattr(mod, f"{map_name}_departure_setup", None)`, and a Plains-of-Jarin branch that travels to map 554, hires four henchmen by encoded identity, verifies the party, walks the recorded path and sails to Kamadan 449 through `run_fixed_map_entry`. Identities are resolved fresh per run rather than reusing recorded agent ids, and `Agent.GetEncNameStrByID(..., literal=True)`, `PyParty.add_henchman`, `bot.Map.Travel(target_map_id=...)` and `bot.Wait.ForMapLoad(target_map_id=...)` all exist.
- Findings and required direction: the branch keys on the literal map name (`if vq.map_name == "PlainsofJarin" and vq.departure_setup`) with dedicated `_poj_*` helpers and a hardcoded map id inside the shared consumer. Another departure route cannot reuse this without copying it, and `PyQuishAI_BT` has no departure consumption, so the same `PlainsofJarin` data executes with and without the eight-member preparation depending on the widget. Move the orchestration to the route owner (for example, make `departure_setup` a callable or generator supplied by the route module and call it generically), or extend a shared party/departure owner and have both consumers call it. Either mirror the hook in `PyQuishAI_BT` or state explicitly that this map is Simple-Vanquish-only and keep it out of the BT path. Register the dependency honestly: the diff fails at baseline with `ImportError` for `PyQuishAI_map_entry` and with the mapping `bless` above.
- Independent checks: exact head fetched and diffed; both consumers and owner contracts inspected. Pyright: route 0 errors; `Simple_Vanquish.py` 107 errors against the 101-error base baseline, a six-diagnostic delta (five `Botting` attribute diagnostics of the existing baseline class and one `Import "Sources.aC_Scripts.PyQuishAI_map_entry" could not be resolved` that disappears once #192 lands). No author test rerun, live-client test, or GitHub review.
- Unresolved: whether three heroes plus four henchmen is the only valid Dajkah Inlet composition; captured identities and the departure path are unverified statically.

### [#207 - Add Morostav Trail Kurzick blessing to Simple Vanquish](https://github.com/apoguita/Py4GW_Reforged/pull/207)

- Review verdict: APPROVE for the submitted source change. Release placement: after #192. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `e61579441134351c610dce8c7685f19f3193339f`; changes: 1 files, +16/-0.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/Factions_EchovaldForest/MorostavTrail.py`.
- Classification: semantic route-data addition; contained to one map module; no shared code, public API, or lifecycle change.
- Verified: appends a `faction_blessing` record (faction `kurzick`, `target_xy` (22109.0, 12076.0), Kurzick Priest model 3477, encoded name) and rebinds the module attribute to `[{"faction_blessing": ...}, {"path": MorostavTrail}]`. `Simple_Vanquish.py:727-754` loads a fresh module per call and reads `getattr(mod, map_name, [])`, so the rebinding is transparent and cannot nest. Base `_handle_keyword` (`Simple_Vanquish.py:139-186`) has no `faction_blessing` branch, so at base the blessing does not execute; base `PyQuishAI_BT._build_keyword_action` raises `ValueError('Unsupported PyQuish map keyword')`, and that consumer lists the map at `PyQuishAI_BT.py:126`, so merging before #192 breaks Morostav Trail there. Under #192 the faction branch calls `TakeBlessing(pos, faction='kurzick')`, which the current owner already supports.
- Dependency resolution: the description names #148 and #192. The diff proves execution needs #192; #148 matters only for opt-in `verify_effect`, which this record does not request. The record's `encoded_name` and `model_id` are unused by the faction branch, which reads geometry and faction only.
- Independent checks: exact head fetched and diffed against the snapshot base; both consumers and the #192/#148 contracts inspected; Pyright at head 0 errors, 0 warnings. No test rerun, live-client test, binary inspection, or GitHub review.
- Unresolved: capture identity validity, terrain clearance, and portal crossing cannot be established statically.

### [#206 - Add captured Zen Daijun map entry](https://github.com/apoguita/Py4GW_Reforged/pull/206)

- Review verdict: REQUEST CHANGES. Release placement: after #192, and only after the record-contract and duplicate-adapter findings are repaired. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `a57a9276e2c303e1bf8b63dc2875de625a5570ba`; changes: 4 files, +429/-7.
- Files: `Examples and tests/tests/test_simple_vanquish_map_entry.py`, `Sources/aC_Scripts/PyQuishAI_map_entry.py`, `Sources/aC_Scripts/PyQuishAI_maps/Factions_ShingJeaIsland/ZenDaijun.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`.
- Classification: route-data replacement plus a second implementation of a shared adapter and a matching widget hunk; mixed scope against the dependency's ownership.
- Verified: Zen Daijun replaces the transit `npc` plus `dialog 0x7F`/`0x800009`/`0x80000B` sequence with one `map_entry` record (Guard Lae Fao, maps 250 to 246, encoded identity, model 3282) and a `map: 246` step. The route supplies the dialog pages as `visible_buttons: (1, 1, 1)`, documented in the record as one-based, while `_normalize_map_entry` in this PR reads `entry_data.get("button_positions", ())`, so the record normalizes to no dialog pages and raises `ValueError: at least one dialog page is required` when the transit registers. The added test asserts `"button_positions": (0, 0, 0)` and never loads the route record, so the mismatch is untested. Separately, this PR ships its own `Sources/aC_Scripts/PyQuishAI_map_entry.py` (blob `25963ac6`) that differs from #192's file (blob `861e5cce`): the copy drops `CanonicalDialogueStateScope`, omits #192's `manage_account_isolation`/`headless_heroai_enabled` arguments, and wires the planner through `SetPlannerTree` and `SetHeadlessHeroAIEnabled` instead of `main_routine`. Both the `map_entry` key and the duplicate module are absent from `PyQuishAI_BT`, which lists Zen Daijun (line 150), so the BottingTree consumer raises `ValueError('Unsupported PyQuish map keyword: map_entry')` even after #192.
- Required direction: rebase on #192 and delete the duplicated `PyQuishAI_map_entry.py` and the duplicated `Simple_Vanquish` hunk, calling the owner's `run_fixed_map_entry` instead, because two adapters against one contract drift and one of them owns dialogue state differently. Convert the route record to the owner's `button_positions` (zero-based) contract and have the test exercise the actual route record rather than only the normalizer, because the submitted record cannot execute. Add `map_entry` to the BottingTree consumer or state that this map is Simple-Vanquish-only and keep it out of the BT path, because the map is already in BT's table.
- Independent checks: exact head fetched and diffed; #192's adapter and `BottingTree.Create` inspected (the `manage_account_isolation`/`headless_heroai_enabled` parameters are a legitimate #192 owner extension); `SetPlannerTree`/`SetHeadlessHeroAIEnabled` confirmed to exist. Pyright at head: 0 errors on the adapter, test and route; `Simple_Vanquish.py` 101 errors equal to the base baseline. No author test rerun, live-client test, or GitHub review.
- Unresolved: the captured three-page dialog sequence, and whether the `map: 246` step is required once the adapter waits for the destination map.

### [#205 - Add captured Sacnoth Valley vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/205)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148, #192 and #195 (the owner of `face_hold`); the dependency statement needs correcting. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `3964b34c544f0f0ae15ba3a463519ac090e7323b`; changes: 1 files, +377/-0.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/EOTN_Charr_Homelands/SacnothValley.py`.
- Classification: additive new route data with captured blessing records and one cartography hold.
- Verified: eleven captured `bless` mappings name the Ascalonian Refugee (model 2036, encoded identity, zero buttons, Vanguard effect ids) with no `faction` key, so they run through #192's captured branch and #148's `TakeBlessing`; one `face_hold` record settles at `(15553.0, 9297.0)` facing `-0.7853981633974483` for 3000 ms. The map is absent from the BT table, so Simple Vanquish is the only consumer.
- Finding and required direction: the description lists a dependency on #186 for "dictionary blessing dispatch, canonical blessing execution, face_hold, and literal_path". The route uses one `face_hold` and zero `literal_path`; `face_hold` is introduced by #195's Simple Vanquish controls, not by #186. Correct the dependency statement and sequence this PR after #195, because otherwise the hold is silently dropped by the widget and the cartography point never resolves.
- Notes: no test file; capture validity is a live claim.
- Independent checks: exact head fetched and diffed; key census run with both quote styles; the blessing record and hold record read; BT table checked; Pyright at head 0 errors. No author test rerun; no live-client test or GitHub review.
- Unresolved: whether the 3-second southeast hold reveals the intended map corner, and whether all eleven blessings are reachable.

### [#204 - Add captured Grothmar Wardowns vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/204)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148 and #192. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `7421b344546590bc0001115665ecabcf8d36f9a5`; changes: 1 files, +349/-0.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/EOTN_Charr_Homelands/GrothmarWardowns.py`.
- Classification: additive new route data; captured Vanguard blessing records interleaved with path segments.
- Verified: eight `bless` mappings name the Ascalonian Refugee with encoded identity, model 2036, standoff/approach/target geometry, zero buttons and the shared Vanguard effect set, and none carries a `faction` key, so execution takes #192's captured branch into #148's `TakeBlessing(captured_blessing=...)`. The file stays inside the map-data contract, adds no keywords beyond `bless`/`path`, and Grothmar Wardowns is absent from the BT map table, so Simple Vanquish is the only consumer and no BottingTree parity gap applies.
- Notes: the PR adds no test file; capture validity and terrain clearance are live claims.
- Independent checks: exact head fetched and diffed; record shape and key census read; BT table checked; Pyright at head 0 errors. No author test rerun; no live-client test or GitHub review.
- Unresolved: capture validity and whether all eight blessings are reachable on the route line.

### [#203 - Add captured Flame Temple Corridor detours](https://github.com/apoguita/Py4GW_Reforged/pull/203)

- Review verdict: REQUEST CHANGES. Release placement: after #124, and only once the BottingTree consumer can execute the keys this route uses. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `234ce9d59c092f8fb5cda6401c1e7baa151ba35d`; changes: 4 files, +438/-54.
- Files: `Examples and tests/tests/test_diessa_lowlands_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/Proph_Ascalon/DiessaLowlands.py`, `Sources/aC_Scripts/PyQuishAI_maps/Proph_Ascalon/FlameTempleCorridor.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`.
- Classification: stacked route-data restructure; the `Simple_Vanquish`, `DiessaLowlands` and test changes are #124's commits carried byte-identically (blobs `23614622`, `93ab8f9d`, `1b581b75`), so this PR's own contribution is the Flame Temple Corridor route.
- Verified: the flat route becomes dict segments, and four `continuous_path` detours replace obstructed corners; `Simple_Vanquish` gained `continuous_path`/`literal_path` only through #124. Coordinate integrity: 45 removed waypoints, 68 added, and one removed waypoint is not re-added — `(-13857, -9107)`. The `FTC: Detour 1 replaces the obstructed corner` comment suggests replacement, but the diff does not state the removal. Flame Temple Corridor (BT table line 209) and the carried Diessa Lowlands change (BT table line 206) are BottingTree maps, and `PyQuishAI_BT` has no `continuous_path` or `literal_path` branch, so the route build raises `ValueError('Unsupported PyQuish map keyword: continuous_path')` under that consumer.
- Required direction: extend the BottingTree consumer to execute `continuous_path`/`literal_path`, or keep these maps out of the BT path, because both affected maps are in its table and the record is currently simple-executable only. Document the dropped `(-13857, -9107)` waypoint: name whether the detour intentionally replaces it, because a silent removal changes the traversed line. Rebase onto #124 after it lands so this PR's comparison contains only the Flame Temple Corridor change.
- Independent checks: exact head fetched and diffed; blob-level comparison against #124; BT map table and keyword handler inspected. Pyright at head: route files 0 errors; the shared `test_diessa_lowlands_route.py` reports one pre-existing `reportArgumentType` ast-body invariance error inherited from #124; `Simple_Vanquish.py` 101 errors equal to the base baseline. No author test rerun, live-client test, or GitHub review.
- Unresolved: detour collision and bridge clearance, and whether the dropped waypoint is intentional.

### [#202 - Add captured Haiju Lagoon route addendum](https://github.com/apoguita/Py4GW_Reforged/pull/202)

- Review verdict: REQUEST CHANGES. Release placement: after #124, and only once the BottingTree consumer can execute `continuous_path`. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `711d428212d94e536292ef43a6801c29009e5dcc`; changes: 4 files, +435/-64.
- Files: `Examples and tests/tests/test_diessa_lowlands_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/Factions_ShingJeaIsland/HaijuLagoon.py`, `Sources/aC_Scripts/PyQuishAI_maps/Proph_Ascalon/DiessaLowlands.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`.
- Classification: stacked route-data restructure; as with #203, the widget, Diessa Lowlands and test files are #124 carried unchanged, so this PR's own contribution is the Haiju Lagoon addendum.
- Verified: the route is restructured around `continuous_path` addendum segments; 55 removed waypoints were compared by value against the added set and all 55 are present at head, so the restructure preserves the existing line and adds the addendum. `continuous_path` exists only in `Simple_Vanquish` through #124. Haiju Lagoon (BT table line 143) and the carried Diessa Lowlands change (BT table line 206) are BottingTree maps with no `continuous_path` branch, so the route build raises `ValueError('Unsupported PyQuish map keyword: continuous_path')` under that consumer.
- Required direction: extend the BottingTree consumer for `continuous_path`, or keep these maps out of the BT path, because the record is simple-executable only while the map is already registered there. Rebase onto #124 once it lands so the comparison contains only the Haiju Lagoon change. No coordinate loss was found, so no route-data repair is requested.
- Independent checks: exact head fetched and diffed; removed-versus-added coordinate comparison by value; blob-level comparison against #124; BT map table and keyword handler inspected. Pyright at head: route 0 errors; shared `test_diessa_lowlands_route.py` one pre-existing inherited error; `Simple_Vanquish.py` 101 errors equal to the base baseline. No author test rerun, live-client test, or GitHub review.
- Unresolved: addendum clearance and the capture provenance of the new segment.

### [#201 - Add Tears of the Fallen cartographer waypoint](https://github.com/apoguita/Py4GW_Reforged/pull/201)

- Review verdict: APPROVE for the submitted source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `937807026813838b20021b3b9345e19769229ffc`; changes: 1 files, +1/-0.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/Proph_Kryta/TearsOfTheFallen.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): - Independent immutable-candidate review: PASS.
- Classification: semantic route-data change; first-batch candidate. No changes requested.
- Verified: Adds (-9312, -2880) to the existing TearsOfTheFallen route list. Scope is a single map data file; existing route owner and order otherwise remain intact. The claimed map reveal and terrain clearance cannot be established from static code.
- Independent checks: reviewed full patch and current route loader; patch applied with the other four in an isolated copy; changed route compiled and Pyright reported 0 errors, 0 warnings, 0 information. The author-reported tests were not independently rerun.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session (commit-safe standalone): head `93780702` matches; one coordinate is inserted with an inline comment; Pyright 0 versus a 0 base.

### [#200 - Correct Skyward Reach captured waypoint](https://github.com/apoguita/Py4GW_Reforged/pull/200)

- Review verdict: APPROVE for the submitted source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `77fbc82cce1d9c1902088e12181537262061e8d0`; changes: 1 files, +1/-1.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/Proph_CrystalDesert/SkywardReach.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): - Independent immutable-candidate review: PASS.
- Classification: semantic route-data change; first-batch candidate. No changes requested.
- Verified: Replaces one SkywardReach route coordinate, retaining the same list and surrounding sequence. Scope is a single map data file; the captured coordinate and traversal cannot be independently established from static code.
- Independent checks: reviewed full patch and current route loader; patch applied with the other four in an isolated copy; changed route compiled and Pyright reported 0 errors, 0 warnings, 0 information. The author-reported tests were not independently rerun.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session (commit-safe standalone): head `77fbc82c` matches; one coordinate is replaced and the list shape is unchanged; Pyright 0 versus a 0 base.

### [#199 - Add captured Dragon's Gullet spur](https://github.com/apoguita/Py4GW_Reforged/pull/199)

- Review verdict: APPROVE for the submitted source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `72bc4a22f86998f59af55cea6ac0ac5637bd972f`; changes: 1 files, +11/-0.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/Proph_Ascalon/DragonsGullet.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): - Independent immutable-candidate review: PASS.
- Classification: semantic route-data change; first-batch candidate. No changes requested.
- Verified: Inserts an eleven-point out-and-back spur into DragonsGullet without altering the remaining route values. The return ends at (-3201.21, 9948.78), near but not exactly at the preceding (-3421, 9865), so the description claiming the exact original handoff is imprecise. No concrete path failure follows from that difference alone; terrain clearance remains unverified.
- Independent checks: reviewed full patch and current route loader; patch applied with the other four in an isolated copy; changed route compiled and Pyright reported 0 errors, 0 warnings, 0 information. The author-reported tests were not independently rerun.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session (commit-safe standalone): head `72bc4a22` matches; the diff is an eleven-point out-and-back spur appended to a plain list; Pyright 0 versus a 0 base.

### [#198 - Add captured Bjora Marches vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/198)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148, #192 and the `literal_path` owner (#124 or #195). GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `330e509a0538c9426d54b811257b7107bfeeaa07`; changes: 1 files, +365/-0.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/EOTN_Far_Silverpeaks/Bjora_Marches.py`.
- Classification: additive new route data only; no shared code, API or lifecycle change.
- Verified: eight `bless` mappings with `interaction_mode: norn_challenge`, standoff/approach/target geometry, encoded identity, model 6425 and the shared Norn effect set, interleaved with eight `path` segments and one `literal_path`. Because the records are mappings without a `faction` key, execution needs #192's adapter plus #148's captured-blessing path; `literal_path` needs the path-key owner. Bjora Marches is not in the BottingTree map table, so Simple Vanquish is the only consumer and the control-key parity gap does not apply. The file contains no `face_hold`, `boundary_face_hold` or `vanquish_status`, so the description's #195 dependency for `face_hold` is broader than the diff proves.
- Dependency resolution: the author states #148, #192 and #195. Only #148, #192 and `literal_path` are exercised; the face-hold claim is unsupported by the file.
- Independent checks: exact head fetched and diffed; record keys counted; owner contracts and BT table inspected; Pyright at head 0 errors, 0 warnings. No author test rerun, live-client test or GitHub review.
- Unresolved: captured identities and Norn challenge dialogues; terrain clearance and the missing-mob sweep cannot be proven statically.

### [#197 - Add captured Frozen Forest patrol cleanup](https://github.com/apoguita/Py4GW_Reforged/pull/197)

- Review verdict: REQUEST CHANGES. Release placement: after #195 and after the BottingTree consumer statement. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `db4a164188f9f16568264ef37c9fc8d37c9c0caa`; changes: 3 files, +832/-110.
- Files: `Examples and tests/tests/test_simple_vanquish_route_controls.py`, `Sources/aC_Scripts/PyQuishAI_maps/Proph_SouthernShiverpeaks/FrozenForest.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`.
- Classification: route restructure plus a private copy of the shared route controls; mixed scope against #195's ownership.
- Verified: the widget file is blob `e5add29c` and the test file `15b30ad8`, both byte-identical to #196 and both a subset of #195's owner files. The route adds `vanquish_status` checkpoints before the central patrol sweep and the counterclockwise cleanup, restructures the route (430 added coordinates, 78 removed), and sets `"reverse_cleanup_passes": 0` in `FrozenForest_ids`. Three removed waypoints are not re-added: `223,-1164`, `474,-3477`, `-2476,-2002`. Frozen Forest is a BottingTree map (`PyQuishAI_BT.py:261`) and BT has no `vanquish_status` branch, so the route build raises `ValueError('Unsupported PyQuish map keyword: vanquish_status')` there. Pyright: route and test 0 errors; `Simple_Vanquish.py` 107 against the 101 baseline, the six diagnostics all in the pre-existing `bot.Properties`/`bot.Stop`/module-as-type class.
- Required direction: drop the `Simple_Vanquish.py` and `test_simple_vanquish_route_controls.py` hunks and depend on #195, because this copy matches #196's byte-for-byte and diverges from the owner's version. State the three removed waypoints' disposition, because the patrol restructure replaces sweeping geometry and a silent removal changes the traversed line. Add `vanquish_status` to the BottingTree consumer or keep Frozen Forest out of its path, because the map is registered there.
- Independent checks: exact head fetched and diffed; widget/test blobs compared to #195/#196; coordinate preservation by value; BT table inspected; Pyright at head in a detached worktree. No author test rerun, live-client test or GitHub review.
- Unresolved: patrol-loop coverage against live spawn counts, and whether `reverse_cleanup_passes: 0` is required or merely preferred.

### [#196 - Add Ettin Back boundary cartography hold](https://github.com/apoguita/Py4GW_Reforged/pull/196)

- Review verdict: REQUEST CHANGES. Release placement: after #195 and after the BottingTree consumer statement. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `b0f2b2c90f4c24a40bcf1701bc34906640513d71`; changes: 3 files, +296/-34.
- Files: `Examples and tests/tests/test_simple_vanquish_route_controls.py`, `Sources/aC_Scripts/PyQuishAI_maps/Proph_Maguuma/EttinsBack.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`.
- Classification: route restructure plus a private copy of the shared route controls; mixed scope against #195's ownership.
- Verified: EttinsBack becomes the tuple-list complex format with a `path` segment, a `boundary_face_hold` record at `(-27744,-1152)` pressing toward `(-28494,-1152)` for 1250 ms (capture `LOC-20261014-154705-076`), and the remaining path. The widget is blob `e5add29c` and the test `15b30ad8`, identical to #197 and a subset of #195. At base, `Simple_Vanquish` silently ignores `boundary_face_hold` and runs only the paths; Ettin Back is a BottingTree map (`PyQuishAI_BT.py:239`) where the unknown key raises `ValueError`. Pyright: route and test 0 errors; `Simple_Vanquish.py` 107 against 101 baseline, six diagnostics in the pre-existing class.
- Required direction: drop the `Simple_Vanquish.py` and test hunks and depend on #195, because the copies duplicate the owner and collide with #197's identical blobs. Add `boundary_face_hold` to the BottingTree consumer or keep Ettin Back out of its path, because the map is registered there. Confirm the cartography hold's facing direction and hold duration against the capture, because those values drive a boundary-dependent map-reveal effect that static review cannot verify.
- Independent checks: exact head fetched and diffed; widget/test blobs compared to #195/#197; BT table inspected; Pyright at head in a detached worktree. No author test rerun, live-client test or GitHub review.
- Unresolved: whether the west-facing press and 1250 ms hold actually reveal the map corner, and the `location_capture_id` provenance.

### [#195 - Add route-specific Simple Vanquish controls](https://github.com/apoguita/Py4GW_Reforged/pull/195)

- Review verdict: REQUEST CHANGES. Release placement: after the path-key ownership decision, and after the BottingTree consumer statement below. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `1c209c8716edaa4512fe4071cf527eae7f8653e4`; changes: 2 files, +516/-33.
- Files: `Examples and tests/tests/test_simple_vanquish_route_controls.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`.
- Classification: shared-consumer capability addition; this is the intended owner for the new route-control keywords.
- Verified: adds `vanquish_status` (console checkpoint through `ConsoleLog`, the approved mechanism), `boundary_face_hold` (reach `xy`, press toward `facing_move_xy`, hold), `face_hold` (settle at `xy`, converge on `facing_angle` with `Routines.Yield.Movement` turns, hold stably), `literal_path`, and `QueuedVanquish.reverse_cleanup_passes` clamped to 0..2 and read from `<map>_ids["reverse_cleanup_passes"]`. The ReverseAggro1/2 headers and their registration are gated by the same counter and both drop together, so `_section_headers` indexing stays aligned; default 2 preserves current behavior. Both hold helpers save and restore `hero_ai_paused` in nested `finally` blocks. Pyright: test 0 errors; `Simple_Vanquish.py` 115 against the 101 baseline, all fourteen diagnostics in the pre-existing `bot.Properties`/`bot.Stop`/module-as-type class.
- Dependency resolution: #196 and #197 ship the identical `Simple_Vanquish.py` blob `e5add29c`, a subset of this file (`5e7ab457`), plus an identical test blob `15b30ad8`. Those route PRs must depend on this owner rather than re-ship it.
- Required direction: remove the duplicate `literal_path` addition, or take sole ownership and have #124 rebase onto it, because #124 adds the same lines to the same handlers and merging both conflicts. State and enforce the consumer contract for `boundary_face_hold`, `face_hold` and `vanquish_status`: EttinsBack and Frozen Forest are in the BottingTree map table and will raise for these keys, so either extend the BT consumer or keep those maps out of its path. Decide the `reverse_cleanup_passes` data contract (route `_ids` key) explicitly, because it is a new route-data surface.
- Independent checks: exact head fetched and diffed; base consumer, BT table and the dependent route PRs compared by blob; Pyright at head in a detached worktree. The 325-line author test was not rerun; no live-client test or GitHub review.
- Unresolved: whether the 10-second position and 6-second facing deadlines match capture conditions, and whether the hold resets are sufficient at map boundaries.

### [#194 - Add captured Jaga Moraine vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/194)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148 and #192. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `2322e2689a92d8bb545c2d87de053c4997e97983`; changes: 1 files, +287/-0.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/EOTN_Far_Silverpeaks/Jaga_Moraine.py` (create mode).
- Classification: additive new route data; contained to one new map module; no shared code changes.
- Verified: adds six `bless` mappings with `interaction_mode: norn_challenge`, `route_standoff_xy`/`target_xy`, encoded identity, model 6425, and Norn effect ids, each followed by its sweep. No `faction` key is present, so execution requires the captured path of #148 through the #192 adapter; `verify_effect` is not requested. Base `Simple_Vanquish.py:774-783` discovers maps by directory listing, so the new file appears in the selector and its mapping `bless` raises `KeyError` when the route is registered; `PyQuishAI_BT` does not list this map in its map table, so the legacy widget is the consumer affected by a standalone merge.
- Dependency resolution (resolved from diffs, not descriptions): #174 changes only `Dalada_Uplands.py` and its test and provides no adapter. The adapter owner is #192 (`Sources/aC_Scripts/PyQuishAI_blessing.py`, `Sources/aC_Scripts/PyQuishAI_map_entry.py`, and the Simple_Vanquish/PyQuishAI_BT dispatch). The description's "PR #174 adapter" claim is stale and would produce the wrong merge order. Requested correction: name #148 as the captured-blessing owner and #192 as the adapter, and drop #174 as a dependency.
- Independent checks: exact head fetched and diffed; commit adds a new file only; both consumers and owner contracts inspected; Pyright at head 0 errors, 0 warnings. No live-client test or GitHub review.
- Unresolved: captured identity validity, the Norn challenge dialogues, and terrain clearance; whether the six captures correspond to the map's actual blessings cannot be proven statically.

### [#193 - Add captured Tangle Root safe crossings](https://github.com/apoguita/Py4GW_Reforged/pull/193)

- Review verdict: APPROVE for the submitted source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `91a143d71e75f6226086931fb33d6f997d4532f2`; changes: 1 files, +69/-5.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/Proph_Maguuma/TangleRoot.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): - Independent Dungeon Playbook v3 review: PASS on 91a143d71e75f6226086931fb33d6f997d4532f2..
- Classification: semantic route-data change; first-batch candidate. No changes requested.
- Verified: Replaces and extends five sections of the TangleRoot route list and removes a duplicate point. The change stays in the existing route owner and preserves its data interface. Captured passability and whether the executor follows each point precisely are not established by this static review.
- Independent checks: reviewed full patch and current route loader; patch applied with the other four in an isolated copy; changed route compiled and Pyright reported 0 errors, 0 warnings, 0 information. The author-reported tests were not independently rerun.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session (commit-safe standalone): head `91a143d7` matches the record; the diff is additive captured crossings plus removal of one duplicate point; TangleRoot contains no dictionary keys; Pyright 0 versus a 0 base.

### [#192 - Add canonical map entry and blessing adapters to Simple Vanquish](https://github.com/apoguita/Py4GW_Reforged/pull/192)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148, and before every route PR that uses blessing or map-entry records; one parity limitation is recorded (the BT consumer is not taught `map_entry`). GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `57ef198d6b8dcdd3897ec5d5edacd2e36fce79b7`; changes: 8 files, +1170/-14.
- Files: `Examples and tests/tests/test_simple_vanquish_map_entry.py`, `Py4GWCoreLib/BottingTree.py`, `Py4GWCoreLib/botting_tree_src/isolation.py`, `Sources/ApoSource/ApoBottingLib/helpers.py`, `Sources/aC_Scripts/PyQuishAI_blessing.py`, `Sources/aC_Scripts/PyQuishAI_map_entry.py`, `Widgets/Automation/Bots/Vanquish/PyQuishAI_BT.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`.
- Classification: adapter layer in front of the canonical owners plus one owner extension; no parallel implementation of target resolution or dialogue handling.
- Verified: `PyQuishAI_map_entry.py` validates the immutable record (required name/encoded identity/source and destination maps, zero-based dialog pages, timeout floor), builds the owner sequence from `MoveAndAutoDialogByModelID` plus `WaitForMapLoad`, and runs it in a nested `BottingTree` with the host HeroAI pause saved and restored. `PyQuishAI_blessing.py` exposes the canonical key set, dispatches a `faction` record to `TakeBlessing(pos, faction=...)` and a captured record to `TakeBlessing(..., captured_blessing=...)` (which requires #148), refuses non-mapping records for the new keys, and runs the nested planner through a `CanonicalDialogueStateScope`. `BottingTree.Create` gains `manage_account_isolation` and `headless_heroai_enabled` with defaults that preserve prior behavior, and the isolation mixin honors the flag. `Simple_Vanquish` gains the keyword dispatch and keeps the reverse-path builder from reversing blessing mappings. The 780-line test exercises the baked-route contract and the legacy bridge with fakes.
- Recorded limitation: `map_entry` is taught only to Simple Vanquish; `PyQuishAI_BT` receives the blessing keys but no map-entry branch, so a route that uses `map_entry` on a map in the BT table (for example #206's Zen Daijun) still raises there. Captured blessings also reject `multi_account=True` by design.
- Independent checks: exact head fetched and diffed; both adapter modules, the owner extension, the isolation guards and both dispatch sites read in full across batches five, nine and this batch; the test structure inspected; Pyright at head: adapters 0, `BottingTree` 18 equal to base, `Simple_Vanquish` 101 equal to base, `PyQuishAI_BT` 0, test 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: the nested-planner lifecycle under live cancellation (the dialogue scope restores HeroAI state, but only live play proves the pause accounting), and BottingTree map-entry parity.

### [#191 - Fix Quest Auto-Runner consumable controls and remove misleading HeroAI option](https://github.com/apoguita/Py4GW_Reforged/pull/191)

- Review verdict: REQUEST CHANGES. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `93b40c88a9d03b0e3f3fec84d833b6d52ab5aa93`; changes: 1 files, +30/-45.
- Files: `Widgets/Automation/Bots/Runners/Quest Auto-Runner (Simple).py`.
- Classification (derived from the recorded decision; the prior session did not record one): Quest Auto-Runner consumable-control change that also removes an existing HeroAI preference, reviewed as a bundle.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Decision and required direction: The same Quest Auto-Runner diff both adds consumable controls and removes the independently stored manual HeroAI control and preference. These are independently reversible user-facing outcomes. Separate the HeroAI removal from the consumable-control change so either behavior can be reviewed and reverted on its own.
- Independent checks: text diff and relevant current owner inspected; previous patch applicability checks are recorded above. No candidate-specific type check, binary inspection, live-client test or GitHub review was performed.

- Release placement (derived from the recorded verdict; the prior session did not state one): after the requested changes in the decision above are addressed..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: request-changes confirmed. The diff removes `_apply_hero_ai_live` and the persisted `hero_ai_enabled` preference while adding consumable controls; Pyright improved from 3 to 2 errors and adds no new diagnostic.

### [#190 - Add captured Forum Highlands route](https://github.com/apoguita/Py4GW_Reforged/pull/190)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148 and #192. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `c972d0bccfc8017b97bd9416bdc50571c6c20d7e`; changes: 1 files, +78/-3.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/NF_Vabbi/ForumHighlands.py`.
- Classification: semantic route-data change; three blessing conversions plus two documented detours and one out-and-back addition; no shared code.
- Verified: the three blessings become captured mappings naming Vabbian Scout and Whispers Informant (models 5683 and 5734). The same hunk adds two detours labelled `FH: Detour 1/2` that replace a long direct leg and refine a final approach, and one `FH: Addition 1` out-and-back clear anchored at the existing `-16177,632`; each inserted block carries its route id and stated purpose. No path waypoint is lost (value-level comparison). ForumHighlands is a BottingTree map (`PyQuishAI_BT.py:193`); mapping blessings need #192, the captured path needs #148. No test file is added.
- Dependency resolution: no dependency statement in the description; the diff requires #148 and #192.
- Independent checks: exact head fetched and diffed; consumers and BT table inspected; coordinate preservation by value; Pyright at head 0 errors, 0 warnings. No author test rerun, live-client test or GitHub review.
- Unresolved: detour collision clearance and capture validity.

### [#189 - Add captured Holdings of Chokhin route](https://github.com/apoguita/Py4GW_Reforged/pull/189)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148 and #192. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `896c623303d23711ff3a8ba777a8b71d1eee148b`; changes: 1 files, +69/-6.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/NF_Vabbi/HoldingsOfChokhin.py`.
- Classification: semantic route-data change; four blessing conversions plus a documented out-and-back corridor replacement; no shared code.
- Verified: the four blessings become captured mappings naming the Vabbian Scout (models 5683). A Minotaur-segment out-and-back to `-10036,5369` is removed and re-expressed later as a corridor anchored near `-7323.59,2212.04`, introduced by the in-file comment `HoC: Route to Replace Part of 124`; the removed anchor `-15641,-14058` remains in the route, so no path waypoint is lost. HoldingsOfChokhin is a BottingTree map (`PyQuishAI_BT.py:195`); mapping blessings need #192, and the captured path needs #148. No test file is added.
- Dependency resolution: no dependency statement in the description; the diff requires #148 and #192. The in-file comment references #124 only as the route part being replaced, not as a code dependency.
- Independent checks: exact head fetched and diffed; consumers and BT table inspected; coordinate preservation by value; Pyright at head 0 errors, 0 warnings. No author test rerun, live-client test or GitHub review.
- Unresolved: whether the moved corridor preserves the northern spur's coverage, and capture validity.

### [#188 - Add captured Garden of Seborhin blessings](https://github.com/apoguita/Py4GW_Reforged/pull/188)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148 and #192, and after `map_entry` is either supported by `PyQuishAI_BT` or this map is excluded from it; one description clarification is requested. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `a481efc180886fffa2fb4938767da9b4be3f29a7`; changes: 1 files, +60/-8.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/NF_Vabbi/GardenOfSeborhin.py`.
- Classification: semantic route-data change; three blessing conversions plus a transit rewrite to `map_entry`; no shared code.
- Verified: the first blessing keeps its coordinate as `target_xy` `4032,-14621`; the second and third anchors move materially (from `3960,-14652` and `8315,-949` to standoffs `8281.87,-860.74` and `8352.16,4400.11`), so one hunt location is replaced and another added while the blessing count stays three. The transit replaces the `npc` plus `dialog 0x80`/`0x84` pair with one `map_entry` record (Seborhin Protector Zuor, maps 399 to 394) using the owner's zero-based `button_positions: (0, 0)` contract, and the old interaction coordinate survives as its `target_xy`. No path waypoint is lost (the apparent loss was a formatting false positive). GardenOfSeborhin is a BottingTree map (`PyQuishAI_BT.py:194`), and `PyQuishAI_BT` has no `map_entry` branch even in #192, so its transit raises `ValueError('Unsupported PyQuish map keyword: map_entry')` there. Blessing mappings themselves are BT-safe after #192.
- Required direction: state in the description which blessing the removed `3960,-14652` anchor represented and why the captured hunt replaces it, because the route's blessing coverage changes and the diff does not say so. Add `map_entry` to the BottingTree consumer or keep Garden of Seborhin out of its path, because the map is already registered there. No code change is requested for the conversion itself.
- Independent checks: exact head fetched and diffed; consumers, #192's map-entry contract and BT table inspected; coordinate preservation by value; Pyright at head 0 errors, 0 warnings. No author test rerun, live-client test or GitHub review.
- Unresolved: capture validity, standoff reachability and the three-page dialog sequence.

### [#187 - Add captured Jahai Bluffs blessings](https://github.com/apoguita/Py4GW_Reforged/pull/187)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148 and #192. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `a9144919042756999f8981254ebf76b5163aec1a`; changes: 1 files, +56/-4.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/NF_Kourna/JahaiBluffs.py`.
- Classification: semantic route-data change; four blessing records converted and one blessing segment inserted; no shared code.
- Verified: the four legacy `bless` coordinates become captured mappings naming the Wandering Priest; the segment that previously carried the coordinate `8593,11728` is replaced by a new `Jahai Bluffs blessing 3` segment whose standoff `8597.16,11732.61` sits within a few units of it, and a later segment loses its blessing line. No path waypoint is lost (value-level comparison). JahaiBluffs is a BottingTree map (`PyQuishAI_BT.py:186`); mapping blessings need #192 and the captured path needs #148. No test file is added.
- Dependency resolution: no dependency statement in the description; the diff requires #148 and #192. The blessing position moves earlier in the route, which is a semantic ordering change that the segment comments do not explain.
- Independent checks: exact head fetched and diffed; consumers and BT table inspected; coordinate preservation by value; Pyright at head 0 errors, 0 warnings. No author test rerun, live-client test or GitHub review.
- Unresolved: whether the reordered third blessing preserves the intent of the removed segment, and capture validity.

### [#186 - Add captured Gandara vanquish blessings](https://github.com/apoguita/Py4GW_Reforged/pull/186)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148 and #192. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `ede7f70d725d3e4740d0d878eeda9814279ea592`; changes: 1 files, +24/-2.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/NF_Kourna/GandaraTheMoonFortress.py`.
- Classification: semantic route-data change; two blessing records converted from coordinates to captured mappings; no shared code.
- Verified: both `bless` records become mappings naming the Wandering Priest with encoded identity, model 5434, standoff/approach/target geometry, effect ids and capture ids; the legacy coordinates `6818,15641` and `-7412,14230` are replaced by captures rather than retyped, and no path waypoint is lost. GandaraTheMoonFortress is a BottingTree map (`PyQuishAI_BT.py:185`); `Simple_Vanquish` currently raises `KeyError` on a mapping `bless` and `PyQuishAI_BT` raises `ValueError`, so the records cannot execute before #192 and their captured path needs #148. No test file is added.
- Dependency resolution: no dependency statement in the description; the diff requires #148 and #192. The second mapping reuses the encoded identity string also used by #187's fourth blessing, which is plausible for the same Wandering Priest display name but should be confirmed against the captures.
- Independent checks: exact head fetched and diffed; base consumers and BT table inspected; coordinate preservation checked by value; Pyright at head 0 errors, 0 warnings. No author test rerun, live-client test or GitHub review.
- Unresolved: capture validity, standoff reachability and effect verification cannot be proven statically.

### [#185 - Add captured Maishang Hills vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/185)

- Review verdict: APPROVE for the submitted source change. Release placement: after #192. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `943d98ad5dc154b34a8873366c72b0750bca93be`; changes: 1 files, +240/-1.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/Factions_TheJadeSea/MaishangHills.py`.
- Classification: semantic route-data change; the flat route is expanded and spliced with a capture, then wrapped in a faction blessing by rebinding the module attribute; no shared code.
- Verified: the single-line 83-point route becomes a readable multi-line list with the captured `ROUTE-20261030-181216-220` run spliced in, and the header documents the splice plan (preserve 1-23, retain 26-33 after captured point 16, resume capture 17-160, then original 50-80). Eighteen original waypoints (#24-25 and #34-49) are not present verbatim, consistent with that documented replacement; #24-25's disposition is not stated explicitly. The module attribute is then rebound to `[{"faction_blessing": {"name": "Take the Luxon blessing", "faction": "luxon", "target_xy": (14126.0, -10653.0)}}, {"path": MaishangHills}]`, the same wrapper pattern as #207/#211. `Simple_Vanquish.py:727-754` loads a fresh module and reads the attribute by map name, so the rebinding is transparent. Maishang Hills is a BT map (line 156) and `faction_blessing` is in `ROUTE_BLESSING_KEYS`, so this is BT-safe after #192; the owner already supports faction blessings, so #148 matters only if effect verification is later enabled.
- Required direction: state what happened to original waypoints #24-25 (the splice comment names 1-23 and 26-33 but skips 24-25), because a silent omission of two waypoints changes the traversed line. No other change requested.
- Independent checks: exact head fetched and diffed; normalization-aware comparison against every base point; consumers and BT table inspected; Pyright at head 0 errors, 0 warnings. No test file is added and no author test rerun; no live-client test or GitHub review.
- Unresolved: the splice's collision clearance and whether the blessing start position is reachable from the entry point.

### [#184 - Add captured Riven Earth vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/184)

- Review verdict: REQUEST CHANGES. Release placement: after #192 and the `literal_path` owner (#124 or #195), and only after the BottingTree consumer can execute `literal_path` or Riven Earth is excluded from it. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `d326d7b6bfc28b40659a5862a8b0173b61df980c`; changes: 2 files, +372/-102.
- Files: `Examples and tests/tests/test_riven_earth_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/EOTN_Tarnished_Coast/RivenEarth.py`.
- Classification: route restructure; the flat list becomes interleaved `literal_path` segments (fifteen) and eight `asuran_blessing` records; no shared code shipped.
- Verified: each Asuran blessing names the Sky Krewe member with encoded identity, model id and effect ids, and several blessings are bracketed by paired out-and-back `literal_path` lists. A normalized comparison keeps most prior geometry, with eight base coordinates absent (two of them ambiguous because the tuple spans lines), so the author should confirm whether those were intentionally replaced. `asuran_blessing` is BT-safe after #192, but `literal_path` exists only in `Simple_Vanquish` (added by #124, duplicated by #195) and Riven Earth is a BottingTree map (`PyQuishAI_BT.py:118`) whose handler raises `ValueError('Unsupported PyQuish map keyword: literal_path')`. The `literal_path` ownership collision recorded for batch seven applies directly here.
- Required direction: settle the single `literal_path` owner and add it to the BottingTree consumer or keep Riven Earth out of its path, because the map is registered there and the route is simple-executable only. State the eight absent coordinates' disposition. Sequence after #192.
- Independent checks: exact head fetched and diffed; key census, normalized coordinate comparison and BT table checked; Pyright at head 0 errors, 0 warnings on both files. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether the out-and-back literal segments cover the intended hunt locations, and capture validity.

### [#183 - Add captured Arbor Bay vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/183)

- Review verdict: REQUEST CHANGES. Release placement: after #192 and #195, and only after the BottingTree consumer can execute `face_hold` or Arbor Bay is excluded from it. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `9582b24513b7afe84d09e21cc2bb8b88e996bf01`; changes: 2 files, +249/-8.
- Files: `Examples and tests/tests/test_arbor_bay_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/EOTN_Tarnished_Coast/ArborBay.py`.
- Classification: route restructure to the tuple-list format with eight `asuran_blessing` records and one cartography `face_hold`; no shared code shipped by this PR.
- Verified: eight Asuran blessings carry encoded identity, model id, shared effect ids and capture ids, and one `face_hold` record (`AB: Carto Face South`, facing `-0.7853981633974483`, `hold_ms: 1250`, `angle_tolerance: 0.15`, capture `LOC-20260924-125832-192`) performs a boundary cartography hold. A normalized comparison retains almost all previous geometry; two base coordinates are absent (one is ambiguous because the tuple spans lines). `asuran_blessing` is BT-safe after #192, but `face_hold` exists only in #195's `Simple_Vanquish`, and Arbor Bay is a BottingTree map (`PyQuishAI_BT.py:116`) whose handler raises `ValueError('Unsupported PyQuish map keyword: face_hold')`.
- Required direction: add `face_hold` to the BottingTree consumer or keep Arbor Bay out of its path, because the map is already registered there and the route's cartography hold cannot run under the BT widget. Sequence this PR after #195 and confirm against #195's `face_hold` contract (position, facing angle, hold duration) since the record's angle value must match the owner's radian convention. State the two absent coordinates' disposition.
- Independent checks: exact head fetched and diffed; key census, normalized coordinate comparison and BT table checked; #195's `face_hold` contract inspected; Pyright at head 0 errors, 0 warnings on both files. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether the south-facing hold reveals the intended map corner, and the capture provenance of the facing angle.

### [#182 - Add captured Ice Cliff Chasms vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/182)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148 and #192, and after #210 if both add the notices file. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `4fb68a8f7191bc6c13064164152cf5a94bff098a`; changes: 3 files, +371/-25.
- Files: `Examples and tests/tests/test_ice_cliff_chasms_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/EOTN_Far_Silverpeaks/Ice_Cliff_Chasms.py`, `Sources/aC_Scripts/PyQuishAI_maps/THIRD_PARTY_NOTICES.md`.
- Classification: route rewrite with attribution; flat coordinate list replaced by segmented captured geometry plus eight `norn_blessing` mappings.
- Verified: the flat 49-coordinate route is replaced by segmented `path` lists and eight Norn blessings (Tjorvi Throstson, Nidbjorg, Skjaldulf Lightfingers and others) with encoded identity, model id and Norn effect ids. A normalized comparison shows 47 of the 49 base coordinates absent from the head, which matches the file header's statement that Crystal interior points were replaced by user recordings while donor geometry is retained. `THIRD_PARTY_NOTICES.md` is the identical blob `0c9018bc` that #210 also adds. The constant `NORN_HUNTING_PARTY_EFFECT_IDS` is defined but never referenced because each record inlines the same tuple. `norn_blessing` is BT-safe after #192 (Ice Cliff Chasms is a BT map at line 110); the captured path needs #148.
- Required clarification: describe the PR as a route rewrite, not an addition, because nearly the whole previous route is replaced; drop `THIRD_PARTY_NOTICES.md` from this diff if #210 lands first; use the shared effect-id constant or remove it.
- Independent checks: exact head fetched and diffed; key census, normalized coordinate comparison, notices blob comparison and BT table checked; Pyright at head 0 errors, 0 warnings on both code files. Author test not rerun; no live-client test or GitHub review.
- Unresolved: donor geometry clearance, and whether the retained final sweep still matches the current donor snapshot.

### [#181 - Add captured Drakkar Lake Norn route](https://github.com/apoguita/Py4GW_Reforged/pull/181)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148 and #192. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `069964f661bf4d638bc345b94e9c1b3d56deacb7`; changes: 2 files, +270/-2.
- Files: `Examples and tests/tests/test_drakkar_lake_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/EOTN_Far_Silverpeaks/Drakkar_Lake.py`.
- Classification: semantic route-data change; blessing conversion plus captured segments; no shared code.
- Verified: the first `bless` coordinate becomes a `norn_blessing` mapping and eight further mappings are added (Durdan Cliffjumper, Sonya the Crimson, Beojorn and others), each with encoded identity, model id, Norn effect ids and capture id. A captured `SONYA_OUTBOUND_ROUTE` is inserted, followed by a return segment built with `list(reversed(SONYA_OUTBOUND_ROUTE))` at import time, which is deterministic route data rather than a runtime dependency. `norn_blessing` is in #192's `ROUTE_BLESSING_KEYS` and Drakkar Lake is a BottingTree map (`PyQuishAI_BT.py:109`), so the mappings are BT-safe once #192 lands; the captured path needs #148 because no record carries `faction`. A focused route test is added.
- Dependency resolution: no dependency statement in the description; the diff requires #148 and #192.
- Independent checks: exact head fetched and diffed; keys counted and owner contracts inspected; BT table checked; Pyright at head 0 errors, 0 warnings on both files. Author test not rerun; no live-client test or GitHub review.
- Unresolved: capture validity, the reverse-derived return leg triggering no cleanup duplication, and terrain clearance.

### [#180 - Add Black Powder Mine route](https://github.com/apoguita/Py4GW_Reforged/pull/180)

- Review verdict: APPROVE for the submitted source change. Release placement: last in the #176-#180 series, after #179. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `bda80bc78be821b109871532173dd61d8e8114b3`; changes: 2 files, +922/-4 (cumulative; own contribution `1a675b21..bda80bc7` is +124 in the widget and +43 in the test file).
- Files: `Examples and tests/tests/test_skills_unlocker_routes.py`, `Widgets/Automation/Bots/SkillsUnlocker/EOTN_SKILL_UNLOCKER.py`.
- Classification: leaf route addition with a shared quest flow; two catalog entries served by one flow.
- Verified: adds `_build_in_the_service_of_revenge_flow(bot)` plus `Unlock_black_powder_mine` and `Unlock_great_dwarf_armor`, both of which call the flow and therefore claim both rewards from the same quest: Orozar's accept dialog `0x834501`, Dundan's Norn blessing `0x84`, the camp-clear route, then Orozar's reward dialog `0x834507`, reward-window cancel and `MENU_IDLE`. `Templates.Aggressive(halt_on_death=True, movement_timeout=15000, auto_loot=False)` matches the framework signature. Bundling the two skills is justified by the shared quest and shared reward dialog, but the title names only Black Powder Mine, so the description should name both skills this PR unlocks.
- Dependency resolution: stacked on #179; own contribution is the flow, `ITSOR_*` route constants and the two routes plus tests. Both skills are already catalogued at base with their function names.
- Independent checks: pairwise diff against #179 inspected; constants verified; `Templates.Aggressive` and `Properties.Set` signatures inspected; Pyright at head: widget 667 against 510 (same class), test 0. Author tests not rerun; no live-client test or GitHub review.
- Unresolved: the CTC portal boundary (`target_map_id=625`) and the full camp-clear path are live-dependent; whether the reward dialog grants both skills in one interaction is unproven statically.

### [#179 - Add I Am the Strongest route](https://github.com/apoguita/Py4GW_Reforged/pull/179)

- Review verdict: APPROVE for the submitted source change. Release placement: fourth in the series, after #178. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `1a675b21550b112769c59485b19b6dd8f0f47818`; changes: 2 files, +755/-4 (cumulative; own contribution `1da6e6f2..1a675b21` is +91/-4 in the widget and +30 in the test file).
- Files: `Examples and tests/tests/test_skills_unlocker_routes.py`, `Widgets/Automation/Bots/SkillsUnlocker/EOTN_SKILL_UNLOCKER.py`.
- Classification: leaf route implementation replacing a placeholder; no shared code.
- Verified: this PR replaces a pre-existing `#en cours !!!` placeholder body of `Unlock_i_am_the_strongest` with a working route that travels to Gunnar's Hold, accepts through `IATS_GUNNAR_XY` (`0x834601`), travels to Olafstead, takes Olgana's blessing (`0x84`), claims the reward from Hogni (`0x834607`), cancels the reward window and returns to `MENU_IDLE`. Replacing the placeholder is a genuine improvement rather than a new competing path; the function name already exists in the catalog.
- Dependency resolution: stacked on #178; own contribution is the replacement route, its `IATS_*` constants and tests.
- Independent checks: pairwise diff against #178 inspected, including the deleted placeholder lines; constants verified; Pyright at head: widget 640 against 510 (same class), test 0. Author tests not rerun; no live-client test or GitHub review.
- Unresolved: the map-name-based travel to Gunnar's Hold and Olafstead is string-keyed and unverified against the local map table; dialog ids are capture-dependent.

### [#178 - Add Weakness Trap route](https://github.com/apoguita/Py4GW_Reforged/pull/178)

- Review verdict: APPROVE for the submitted source change. Release placement: third in the series, after #177. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `1da6e6f2c67bfd0939beb201603f25bfdacf1122`; changes: 2 files, +638/-0 (cumulative; own contribution `f16bc496..1da6e6f2` is +80/-4 in the widget and +47 in the test file).
- Files: `Examples and tests/tests/test_skills_unlocker_routes.py`, `Widgets/Automation/Bots/SkillsUnlocker/EOTN_SKILL_UNLOCKER.py`.
- Classification: leaf route addition plus a file-local flow extraction; the four deleted lines replace #177's inline route with a shared helper.
- Verified: `_build_forbidden_fruit_flow(bot, return_to_menu)` now carries the route shared by Tryptophan Signet (`return_to_menu=True`) and the new Weakness Trap (`return_to_menu=False`). The extraction is a private helper in the owning widget file, not a library abstraction, which is acceptable; the two skills plausibly come from the same quest line. The skill is already catalogued at base with this function name.
- Dependency resolution: stacked on #177 and supersedes its inline implementation; own contribution is the helper, the re-pointed Tryptophan route, Weakness Trap and tests.
- Independent checks: pairwise diff against #177 inspected; constants verified; Pyright at head: widget 624 against 510 (same class), test 0. Author tests not rerun; no live-client test or GitHub review.
- Unresolved: what the FSM does after the shared flow when `return_to_menu=False` — the flow does not jump to `MENU_IDLE` in that case, and static review cannot show the next state.

### [#177 - Add Tryptophan Signet route](https://github.com/apoguita/Py4GW_Reforged/pull/177)

- Review verdict: APPROVE for the submitted source change. Release placement: second in the series, after #176. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `f16bc49610f8a92274d3d2f43df3305328570b41`; changes: 2 files, +519/-0 (cumulative; own contribution `37e32225..f16bc496` is +145 in the widget and +37 in the test file).
- Files: `Examples and tests/tests/test_skills_unlocker_routes.py`, `Widgets/Automation/Bots/SkillsUnlocker/EOTN_SKILL_UNLOCKER.py`.
- Classification: leaf Skills Unlocker route addition; stacked on #176; no shared code.
- Verified: adds `Unlock_tryptophan_signet` plus `FF_*` route constants, travelling to Longeye's Ledge, accepting through `0x837F01`, taking the entry blessing and a Sacnoth blessing (`0x84`), talking to Vael (`0x837F04`), waiting 12 seconds, claiming the reward (`0x837F07`), cancelling the reward window and returning to `MENU_IDLE`. The skill is already catalogued at base with this function name.
- Dependency resolution: stacked on #176 (which carries #173); own contribution is the route plus tests. #178 later refactors this route into `_build_forbidden_fruit_flow`, so this PR's implementation is superseded if the full stack lands.
- Independent checks: pairwise diff against #176 inspected; constants verified; Pyright at head: widget 607 against 510 (same class), test 0. Author tests not rerun; no live-client test or GitHub review.
- Unresolved: quest dialog ids and the 12-second wait are capture-dependent; the route's `0x84` Sacnoth blessing assumes the EOTN dialog id.

### [#176 - Add Sneak Attack route](https://github.com/apoguita/Py4GW_Reforged/pull/176)

- Review verdict: APPROVE for the submitted source change. Release placement: first in the #176-#180 series, after the #173 stack root. GitHub state: draft; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `37e322253d2cb778b4346c6219c6c06506f73d46`; changes: 2 files, +337/-0 (cumulative stack diff; own contribution `45000419..37e32225` is +136 in the widget and +28 in the test file).
- Files: `Examples and tests/tests/test_skills_unlocker_routes.py`, `Widgets/Automation/Bots/SkillsUnlocker/EOTN_SKILL_UNLOCKER.py`.
- Classification: leaf Skills Unlocker route addition; no library, shared-consumer or lifecycle change; stacked on #173.
- Verified: adds `Unlock_sneak_attack`, which travels to Longeye's Ledge (`target_map_id=650`), accepts the quest through `Move.XYAndDialog(-21069.0, 12353.0, 0x836201)`, takes the Vanguard blessing through the existing FSM `0x84` dialog, talks to Vael (`0x836204`), waits 70 seconds, claims the reward (`0x836207`), cancels the reward window and returns to `MENU_IDLE`. It reuses #173's `EBOSC_ENTRY_BLESSING_XY` and `PLAN_A_VAEL_XY` constants, so it is not independent of the root. The skill is already listed in the base catalog with this function name, so it is reachable. No shared code is modified.
- Dependency resolution: the PR is a draft stacked on #173; the base-to-head diff includes #173's route. Own contribution is the function and its tests only.
- Independent checks: pairwise diff against #173 inspected; referenced constants verified defined; framework APIs verified; Pyright at head: widget 574 diagnostics against the 510 baseline (all in the pre-existing `bot.*` attribute class), test file 0 errors. Author structural tests not rerun; no live-client test or GitHub review.
- Unresolved: the 70-second Torch wait and the quest dialog ids are capture-dependent and unverifiable statically.

### [#175 - Support Infinite Superior Salvage Kit in SalvageItem BT](https://github.com/apoguita/Py4GW_Reforged/pull/175)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `e5ed8b7d67d9552e62d1fff34bcd8e21c631ef84`; changes: 3 files, +46/-25.
- Files: `Py4GWCoreLib/enums_src/Model_enums.py`, `Py4GWCoreLib/routines_src/behaviourtrees_src/items.py`, `Sources/frenkeyLib/ItemHandling/BTNodes.py`.
- Classification: tier-matching rule change in the salvage-kit owner plus a mirrored change in the legacy shim.
- Verified: `Infinite_Identification_Kit = 38620` and `Infinite_Superior_Salvage_Kit = 38621` are new and do not duplicate any existing member or #150's block. `_kit_matches_tier` accepts a kit when its model id is a known tier member **or** when the kit reports the relevant native capability fact (`IsExpertSalvageKit` for the expert tier, `IsPerfectSalvageKit`/`IsExpertSalvageKit` for the upgrade tier); both facts exist in `ItemCache.py` and are already used the same way by the loot controller. The preferred-kit path, the expert-kit scan and the upgrade-kit scan all route through the helper, so an infinite kit is treated as an expert tool without a per-model whitelist entry.
- Notes: the same predicate is implemented twice — once at module level in `Py4GWCoreLib`'s items module and once nested in the `frenkeyLib` shim. That shim is a legacy area, but the duplication means the rule must be changed in two places next time.
- Independent checks: exact head fetched and diffed; enum additions and the three call sites read; native usage facts and their existing consumers verified; Pyright at head: `items.py` and `Model_enums` 0, `BTNodes` 18 equal to base. No test file; no live-client test or GitHub review.
- Unresolved: whether the infinite kits actually report the capability flags at runtime; that is the assumption the new fallback rests on.

### [#174 - Add captured Dalada Uplands blessing route](https://github.com/apoguita/Py4GW_Reforged/pull/174)

- Review verdict: APPROVE for the submitted source change. Release placement: after #148 and #192. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `92daa3f0a6fb1ecc9b241691ab5f07dd74db3ad6`; changes: 2 files, +192/-41.
- Files: `Examples and tests/tests/test_dalada_uplands_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/EOTN_Charr_Homelands/Dalada_Uplands.py`.
- Classification: semantic route-data replacement plus a route test; contained to one map module; no shared code changes.
- Verified: replaces four working `bless` coordinate records with `vanguard_blessing` mappings built by `_vanguard_blessing` (`buttons: 0`, Vanguard effect ids, standoff/approach/target geometry, encoded identity; no `faction` key) and splits the route into path slices. Because `vanguard_blessing` is unknown at base, `Simple_Vanquish` ignores it silently and the four currently executing Vanguard blessings stop happening; `PyQuishAI_BT` raises `ValueError` for the unknown keyword and lists the map at `PyQuishAI_BT.py:106`. This is a behavior regression if merged standalone, not a neutral no-op. Under #192 the record has no `faction`, so it takes the captured path and calls `TakeBlessing(..., captured_blessing=record)`, a parameter introduced by #148; #148 must therefore land before #192, and this route last.
- Dependency resolution: this PR's own description names #192 as the adapter, consistent with the diff. #194's statement that it depends on an adapter supplied by #174 does not match this diff, which contains route data and its test only.
- Independent checks: exact head fetched and diffed; both consumers and owner contracts inspected; Pyright at head 0 errors, 0 warnings on both changed files. No author test rerun, live-client test, or GitHub review.
- Unresolved: captured identity validity and terrain clearance; whether the removed coordinate blessings and the new records are behaviorally equivalent cannot be proven statically.

### [#173 - Add Ebon Battle Standard of Courage route](https://github.com/apoguita/Py4GW_Reforged/pull/173)

- Review verdict: APPROVE for the submitted source change. Release placement: first in the Skills Unlocker route series (#173 -> #176 -> ... -> #180). GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `45000419cf1de4a4928304c09772ef3a8a3529d2`; changes: 2 files, +173/-0.
- Files: `Examples and tests/tests/test_skills_unlocker_routes.py`, `Widgets/Automation/Bots/SkillsUnlocker/EOTN_SKILL_UNLOCKER.py`.
- Classification: leaf Skills Unlocker route addition with a structural test; no shared code.
- Verified: `Unlock_ebon_battle_standard_of_courage` claims the quest through explicit dialogue ids, re-zones for Vael's first appearance, takes the Vanguard blessing through the existing FSM dialog, waits out the scripted delay, claims the reward and returns to `MENU_IDLE`. Every constant it references is defined in the same file, the framework calls used (`FollowPathAndExitMap`, `XYAndDialog`, `CancelSkillRewardWindow`, `Wait.ForMapLoad`) exist in their owners, and the skill is already listed in the base catalog with this function name, so the route is reachable. The test asserts the dialog and travel ordering structurally and `#176`-`#180` build on this file.
- Notes: the widget reports 41 new Pyright diagnostics over its base (551 versus 510), all of them the file's existing `bot.Move`/`bot.Wait`/`bot.States` attribute-access class on the new route lines; the test file is clean.
- Independent checks: exact head fetched and diffed; route constants and framework calls verified in batch nine; Pyright at head: widget 551 against the 510 base, test 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: capture geometry and dialog ids remain live claims.

### [#171 - Defer widget-manager core imports until ImGui is ready](https://github.com/apoguita/Py4GW_Reforged/pull/171)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `38a9a412821e80a4348889ece93572e203988e42`; changes: 2 files, +194/-8.
- Files: `Examples and tests/tests/test_widget_manager_startup.py`, `Py4GW_widget_manager.py`.
- Classification: startup-lifecycle change in the widget host script; no library contract change.
- Verified: the module no longer binds `Settings`, `WidgetHandler`, `register_launchpad_once` or the shared handler at import time; `_ensure_runtime()` probes `PyImGui.StyleConfig()` and only proceeds when the native side is ready, binding the modules lazily and caching `widget_manager`. `main()` returns early until the context exists, then registers the launchpad and bootstraps; `_bootstrap_once` also guards the unbound state. `draw()` is a documented no-op and the host calls `main()` every frame, so nothing dereferences the unbound handler first. The legacy `get_widget_handler()` import name is preserved as a wrapper.
- Notes: the readiness probe depends on the native error text ("no imgui context") and re-raises any other RuntimeError, so a wording change in the binding would turn a deferral into a startup failure; `assert register_launchpad_once is not None` encodes a runtime guarantee as an assert, which is stripped under `python -O`. Neither is a functional defect today.
- Independent checks: exact head fetched and diffed; host lifecycle docstring, `draw()`/`main()` and `_bootstrap_once` read; Pyright at head 0 errors on both files. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether every supported native build raises the same RuntimeError wording that the probe matches.

### [#170 - Strengthen gadget interaction ownership and document shared usage](https://github.com/apoguita/Py4GW_Reforged/pull/170)

- Review verdict: REQUEST CHANGES. Release placement: any time for the ownership improvements, but the detached-command gating must be repaired first because it can block gadget interaction process-wide. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `0baf81bea2b9dfc12879fddcf89e5621d6e48eca`; changes: 4 files, +704/-54.
- Files: `Examples and tests/tests/native_interaction/test_gadget_interaction.py`, `Py4GWCoreLib/routines_src/behaviourtrees_src/agents.py`, `docs/automation/README.md`, `docs/automation/gadget-interactions.md`.
- Classification: ownership and lifecycle strengthening of the existing gadget owner, with focused tests and new documentation; no parallel controller.
- Verified: exclusive HeroAI ownership is now acquired before the final approach and failure to acquire aborts with a diagnostic instead of proceeding; a partially applied HeroAI snapshot is rolled back field by field on exception; `pause_on_combat` yields while combat is active and shifts the transaction deadlines by the paused duration; transient counts are exported to the blackboard. Documentation is correctly labelled `Status: proposed` with scope, authority and a call-shape example, and the automation README links it.
- Findings and required direction: the detached-command registry is a module-global keyed by `(sender_email, receiver_email, message_index)`. `_detached_remote_command_state` removes only `inactive` entries, so an entry that stays `unknown` past `detached_command_unknown_timeout_ms` reports `failed` on every later tick without ever being removed — and since the gate runs before dispatch, every subsequent gadget transaction for that key fails until the process restarts or the message turns inactive. Worse, the key is an inbox slot index that recycles: a recycled index carrying an `InteractWithTarget` command with the same sender and receiver reads `active`, so the gate returns `pending` and the tree waits in RUNNING with no deadline. Remove or terminally mark an entry when declaring `failed`, bound `pending` by dispatch age as well, and key the registry by a unique command identity rather than a reusable slot index.
- Independent checks: exact head fetched and diffed; detached-command lifecycle, snapshot/rollback and combat pause read in the full file; documentation reviewed against the style guide; Pyright at head 0 errors on the changed module and test. Author test not rerun; no live-client test or GitHub review.
- Unresolved: how quickly the inbox slot is reused in live multibox play, and whether the remote `InteractWithTarget` command can remain active without ever completing.

### [#169 - Retain headless loot ownership while the pickup worker is active](https://github.com/apoguita/Py4GW_Reforged/pull/169)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency; one cleanup is required before merge (the dead `_loot_throttle_check`). GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `5fb65074a1c1cbc5e81351be7366dd56255723e9`; changes: 2 files, +36/-6.
- Files: `Examples and tests/tests/test_headless_loot_ownership.py`, `Py4GWCoreLib/HeroAI/headless_tree.py`.
- Classification: behavioral change in the headless HeroAI loot gate plus a focused test.
- Verified: both `_loot_throttle_check.IsExpired()` reads are removed — the `_is_looting_routine_active` entry gate and the `_handle_looting` RUNNING branch — so an active pickup message keeps the routine RUNNING instead of being dropped on throttle expiry, which is the stated intent. A natural exit still exists: when `_has_active_pick_up_loot_message()` goes false the code falls through to the fresh-pickup branch, and map-invalid, free-slot, combat-pause and follow-recovery exits are unchanged. The timer object remains constructed and is still `Reset()` in the fresh-pickup branch, so it is now dead state.
- Required direction: delete `_loot_throttle_check` and its `Reset()` call, or restore a read, because a timer that is reset and never consulted is misleading; and state whether an active message that never clears should keep the routine RUNNING, because the removed check was also the only stall breaker on that path.
- Independent checks: exact head fetched and diffed; entry-gate and looting routine read end to end; Pyright at head 0 errors on both files. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether the pickup worker's message reliably clears in live play.

### [#168 - Preserve optional MovePath progress through named planner retries](https://github.com/apoguita/Py4GW_Reforged/pull/168)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `b5d6389e58bc5e8aa6013b215621298670dac80a`; changes: 3 files, +199/-2.
- Files: `Examples and tests/tests/test_restart_safe_path_progress.py`, `Py4GWCoreLib/botting_tree_src/planner.py`, `Py4GWCoreLib/routines_src/behaviourtrees_src/movement.py`.
- Classification: additive capability behind an opt-in parameter on the shared movement owner, plus retry-state preservation in the planner mixin.
- Verified: `BTMovement.MovePath` gains `resume_key`; when supplied it wraps the path in a `SubtreeNode` that records `bt_move_path_progress:<key>` (map id, instance uptime, next forward index) after each waypoint and resumes from the nearest remaining forward point, rejecting a record whose map differs or whose uptime appears rewound (`current + 1000 >= saved`). `RestartFromNamedPlannerStep` now captures only `bt_move_path_progress:*` blackboard dicts, resets and rebuilds the planner tree, then restores them; transient movement/interaction keys are explicitly not preserved. `resume_key=None` keeps the previous code path intact. The `Utils` import resolves through `Py4GWcorelib`'s re-export, and `SubtreeNode` builds its subtree once per reset.
- Independent checks: exact head fetched and diffed; planner `_set_planner_tree`/`SetNamedPlannerSteps` and `SubtreeNode` semantics read; Pyright at head: planner.py 1 error equal to the base diagnostic, both other files 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: the nearest-forward-point choice ignores terrain and could pick a point behind an obstacle; the uptime gate assumes millisecond monotonic instance uptime; the newly added `planner_tree.reset()` is a behavior change for retries whose old tree still had pending node state.

### [#167 - Cancel the active waypoint movement when FollowPath pauses](https://github.com/apoguita/Py4GW_Reforged/pull/167)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `cb756acc6ca1f65b8e1947da7a8cad9b79f61dc2`; changes: 2 files, +45/-0.
- Files: `Examples and tests/tests/test_follow_path_pause_stop.py`, `Py4GWCoreLib/routines_src/yield_src/movement.py`.
- Classification: behavioral fix in a shared movement owner with a focused test; no contract change.
- Verified: the pause block now issues `Player.Move(*Player.GetXY())` once per pause episode, because withholding the next waypoint does not cancel the click-to-move destination already in flight. `pause_stop_issued` is declared inside the per-iteration pause block, so a later pause episode issues its own cancellation; on resume the existing code re-issues `Player.Move(target_x, target_y)`, so the stop is not sticky. Map-validity, party-wipe, cast and exit guards are untouched.
- Independent checks: exact head fetched and diffed; surrounding loop and resume path read; Pyright at head 0 errors on both files. Author test not rerun; no live-client test or GitHub review.
- Unresolved: that the native client treats a move-to-current-position as cancelling the pending destination is inferred from the client's movement model, not verified live.

### [#166 - Prioritize Seven Weapons Stance in generic HeroAI](https://github.com/apoguita/Py4GW_Reforged/pull/166)

- Review verdict: APPROVE for the reviewed source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `1b61783abebac15a1f5108f124bbc0729fb94cb7`; changes: 1 files, +1/-1.
- Files: `Py4GWCoreLib/HeroAI/custom_skill_src/pve.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Classification: semantic shared-code change; later batch: changes skill priority relative to healing. No code change requested.
- Verified: Changes only Seven Weapon Stance from Buff to CustomC. Existing HeroAI combat.py priority order places CustomC before Healing and Resurrection; an eligible use can therefore precede those actions. This is the stated policy, not a demonstrated defect, but it crosses the first-batch containment criterion.
- Independent checks: complete production patch and current owning conditions/priority table inspected; five patches applied together to isolated copies and Python compilation passed. Pyright was not independently run for this batch; author reports are not independent results.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: approval confirmed. One line moves Seven Weapon Stance to `CustomC`; the head matches and Pyright is 0 versus a 0 base; the CustomC-ordering caveat still applies.

### [#165 - Prioritize Over the Limit before ordinary support actions](https://github.com/apoguita/Py4GW_Reforged/pull/165)

- Review verdict: APPROVE for the reviewed source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `b9f8a11450ca124eae0668441b0bd833a7687469`; changes: 1 files, +1/-1.
- Files: `Py4GWCoreLib/HeroAI/custom_skill_src/pve.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Classification: semantic shared-code change; later batch: changes skill priority relative to healing. No code change requested.
- Verified: Changes only Over the Limit from Buff to CustomC. Existing HeroAI combat.py priority order places CustomC before Healing and Resurrection; an eligible use can therefore precede those actions. This is the stated policy, not a demonstrated defect, but it crosses the first-batch containment criterion.
- Independent checks: complete production patch and current owning conditions/priority table inspected; five patches applied together to isolated copies and Python compilation passed. Pyright was not independently run for this batch; author reports are not independent results.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: approval confirmed. One line moves Over the Limit to `CustomC`; the head matches and Pyright is 0 versus a 0 base. The recorded CustomC-ordering caveat still applies.

### [#164 - Resume melee engagement after targeted non-attack skills](https://github.com/apoguita/Py4GW_Reforged/pull/164)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `84150e38ebff2bdc25be7076370e17eba7bfabfc`; changes: 2 files, +92/-0.
- Files: `Examples and tests/tests/test_resume_melee_after_spell.py`, `Py4GWCoreLib/HeroAI/combat.py`.
- Classification: combat-engagement state added to the existing owner; focused test.
- Verified: after `UseSkill`, `_queue_melee_engagement_after_skill` records the target only when the player is melee (`Agent.IsMelee`), the skill is not an attack skill, and the target is a valid living non-blacklisted enemy within the guard anchor and combat distance. `_resume_pending_melee_engagement` fires at the top of non-OOC combat only when nothing is casting, clears the record before acting, re-validates it, and then `SafeInteract`s the target. Self-targeted skills cannot queue a resume because the recorded id fails the enemy-allegiance check.
- Independent checks: exact head fetched and diffed; both new helpers and their call sites read; the referenced owner helpers (`IsMelee`, `SafeInteract`, `_is_blacklisted_enemy_target`, `_is_target_within_guard_anchor_range`, `get_combat_distance`) confirmed present; Pyright at head: `combat.py` 17 equal to base, test 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether the one-tick re-engage delay is acceptable for attack-speed-sensitive builds, and what happens if the skill is interrupted before the queue is consumed.

### [#163 - Join combat already detected around party heroes](https://github.com/apoguita/Py4GW_Reforged/pull/163)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency; one shared-contract note (hero engagement is now published as party in-aggro to followers). GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `a5c19144026138d1616c8df55042bf8ff4611f47`; changes: 3 files, +160/-3.
- Files: `Examples and tests/tests/test_hero_party_engagement.py`, `Py4GWCoreLib/HeroAI/cache_data.py`, `Py4GWCoreLib/HeroAI/combat.py`.
- Classification: aggro-detection extension in the cache plus a target-acquisition path in the combat owner; focused test.
- Verified: `CacheData.HeroesInAggro` reports living, non-blacklisted enemies within a radius of any living hero, and the leader (`party_position == 0`) records `hero_in_aggro`, widens the active scan range to `Range.Spirit` while it holds, sets `party_in_aggro`, and publishes `local_in_aggro or hero_in_aggro` to shared memory. `CombatClass._nearest_enemy_engaging_heroes` collects living, valid, non-blacklisted enemies near heroes within the guard-anchor range and `Range.SafeCompass` of the player, and `_acquire_hero_engagement_target` leaves an already valid enemy target alone, otherwise safely interacts with and calls the nearest candidate. Both new paths use existing helpers (`Filter.ByDistance`, `EnemyBlacklist`, `_is_target_within_guard_anchor_range`, `SafeInteract`, `MaybeCallCombatTarget`).
- Shared-contract note: the published in-aggro value now includes hero engagement, so followers and multibox consumers of that signal will treat the leader's hero fights as party aggro. That may be intended, but it alters a signal outside the PR's own player.
- Independent checks: exact head fetched and diffed; cache update order and both new functions read; Pyright at head: `cache_data.py` 0, `combat.py` 17 equal to base, test 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: `GetActiveScanRange` is sampled before `hero_in_aggro` is refreshed, so the first detection frame uses the previous frame's range; whether that lag matters is unverified.

### [#162 - Register the Agent of the Mad King disguise skills](https://github.com/apoguita/Py4GW_Reforged/pull/162)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency; one robustness note (the four event skill ids are keyed without a `GetID` zero guard). GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `e884c014581a1b7e9802269953ffb166e454f83c`; changes: 1 files, +34/-0.
- Files: `Py4GWCoreLib/HeroAI/custom_skill_src/pve.py`.
- Classification: additive skill-data registration in the existing PvE custom-skill module; no scheduling logic.
- Verified: four disguise-bar skills are registered through `PVESkills.__init__` into the shared `skill_data` table: Sugar Rush as a self buff stance enabled out of combat while moving, Sticky Ground as an offensive shout on moving enemies without strict targeting, Sugar Shock as an offensive enemy shout, and The Mad King's Influence as a self-targeted shout with `EnemyCount = 1` inside Earshot. The module already imports `GLOBAL_CACHE`, `Range` and the `SkillNature`/`Skilltarget`/`SkillType` enums, and every enum member used exists (`EnemyMoving`, `Stance`, `Shout`, `SelfTargeted`, `Buff`, `Offensive`). No shared owner is modified.
- Robustness note: the four entries are keyed by `GLOBAL_CACHE.Skill.GetID(...)` with no zero guard, while the same file already uses `GetID("Junundu_Siege") or 1441`. If an event skill id fails to resolve, all four would be written under key 0 and overwrite each other; add a guard or state that these ids always resolve.
- Independent checks: exact head fetched and diffed; module imports and enum members verified; registration pattern compared with the file's existing entries; no test file exists for this PR; Pyright at head 0 errors on the changed module. No live-client test or GitHub review.
- Unresolved: whether the disguise bar's skills resolve through `GetID` outside the Halloween event, and whether the act/skill conditions match how the disguise bar is consumed.

### [#161 - Add bounded Soul Ignition upkeep to HeroAI](https://github.com/apoguita/Py4GW_Reforged/pull/161)

- Review verdict: APPROVE for the submitted source change. Release placement: coordinate with #156, which carries the same capacity bump; two cleanups are requested (drop the duplicate capacity edit if #156 lands first, and import the `SOUL_IGNITION` constant instead of the duplicate 3446 literal). GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `1fd1257280570913bf7111242f0e677638f746e1`; changes: 5 files, +144/-3.
- Files: `Examples and tests/tests/test_soul_ignition_upkeep.py`, `Py4GWCoreLib/HeroAI/combat.py`, `Py4GWCoreLib/HeroAI/constants.py`, `Py4GWCoreLib/HeroAI/custom_skill.py`, `Py4GWCoreLib/HeroAI/custom_skill_src/elementalist.py`.
- Classification: skill-data capacity and registration plus a bounded upkeep policy in the combat owner; focused test.
- Verified: `MaxSkillData` grows 3433 -> 3447 so index 3446 exists; Elementalist registers Soul Ignition as a self-targeted `CustomA` enchantment out of combat; `constants.py` owns `SOUL_IGNITION` and the two threshold predicates (activate above 25% health with overcast present and an overcast share <= 60%; drop at <= 25% health or overcast share >= 90%, where the share reconstructs the full bar as current max energy plus overcast); `HandleCombat` drops the buff through `Effects.GetBuffID`/`DropBuff` with a one-second throttle, and `FindCastableSkill` refuses activation outside its window. `_enabled_skill_slot` is correct: `self.skills` is the ordered array, so `skill_order[slot]` maps back to the original index that `is_skill_enabled` is keyed by, matching `IsSkillReady`.
- Required direction: #156 already changes `MaxSkillData` with an identical `custom_skill.py` blob, so sequence the two and drop the duplicate capacity edit from whichever lands second; and import the `SOUL_IGNITION` constant in `elementalist.py` instead of duplicating the `3446` fallback literal, because the constants module is the owner of that value.
- Independent checks: exact head fetched and diffed; capacity, upkeep and indexing paths read against the base owner; blob identity with #156 checked; Pyright at head: `combat.py` 17 equal to base, the other modules and the test 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: the helper assumes `Agent.GetMaxEnergy` reports the overcast-reduced maximum (documented in the file, not proven here); the health and overcast thresholds are policy choices that only live play can validate.

### [#160 - Prioritize party-wide Swirling Aura while overcast](https://github.com/apoguita/Py4GW_Reforged/pull/160)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `0a8f3520020320ca7db443177eb2a9e72ff99a36`; changes: 3 files, +49/-2.
- Files: `Examples and tests/tests/test_swirling_aura_priority.py`, `Py4GWCoreLib/HeroAI/combat.py`, `Py4GWCoreLib/HeroAI/constants.py`.
- Classification: skill-gated priority override in the HeroAI combat owner; constants helper plus a focused test.
- Verified: `constants.py` adds `SWIRLING_AURA` resolved at import through the existing `GLOBAL_CACHE.Skill.GetID` pattern used by `BLOOD_IS_POWER`, plus a pure `should_prioritize_swirling_aura(skill_id, player_overcast)` predicate. `FindCastableSkill` samples `Agent.GetOvercast(Player.GetAgentID())` once per priority pass and rewrites `effective_nature` to `SelfTargeted` only for that skill id while overcast is above zero. No other skill's nature changes; the override only moves Swirling Aura's ordering.
- Independent checks: exact head fetched and diffed; the priority loop and constants module read; Pyright at head: `combat.py` 17 errors equal to the base diagnostic, `constants.py` 0, test 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: `overcast > 0` is a very broad trigger for reordering a skill ahead of other self-targeted skills; live timing at partial overcast is unverified.

### [#159 - Reserve in-combat Junundu Wail for multiple dead party members](https://github.com/apoguita/Py4GW_Reforged/pull/159)

- Review verdict: APPROVE for the reviewed source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `1fec02efe7fa90b4029dc51f2d2e1bca50c177e5`; changes: 3 files, +41/-12.
- Files: `Examples and tests/tests/test_junundu_wail_policy.py`, `Py4GWCoreLib/HeroAI/combat.py`, `Py4GWCoreLib/HeroAI/constants.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Classification: semantic shared-code change; first-batch candidate. No code change requested.
- Verified: The Junundu Wail branch now calls should_use_junundu_wail with the nearby enemy and dead-party counts. During combat it waits for two dead allies; otherwise it permits one or low-health healing. This changes that skill decision and can affect party recovery while the skill is used.
- Independent checks: complete production patch and current owning conditions/priority table inspected; five patches applied together to isolated copies and Python compilation passed. Pyright was not independently run for this batch; author reports are not independent results.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: approval confirmed. `should_use_junundu_wail` encodes heal/resurrect out of combat versus mass-resurrect when two or more are down in combat, `GetDeadAllyArray` exists, and both `combat.py` (17, equal to base) and the policy test are clean.

### [#158 - Avoid spending Fall Back while standing still](https://github.com/apoguita/Py4GW_Reforged/pull/158)

- Review verdict: APPROVE for the reviewed source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `e2aead9a6efb7c26a7b34569af8beb8db5b134bb`; changes: 3 files, +36/-1.
- Files: `Examples and tests/tests/test_fall_back_movement.py`, `Py4GWCoreLib/Builds/Skills/paragon/Command.py`, `Py4GWCoreLib/HeroAI/custom_skill_src/paragon.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Classification: semantic shared-code change; first-batch candidate. No code change requested.
- Verified: Adds the movement condition to both the BuildMgr Fall_Back helper and the generic HeroAI skill definition. Existing out-of-combat and shared-effect checks remain. The effects are confined to Fall Back callers.
- Independent checks: complete production patch and current owning conditions/priority table inspected; five patches applied together to isolated copies and Python compilation passed. Pyright was not independently run for this batch; author reports are not independent results.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: approval confirmed. `Fall_Back` gains an `Agent.IsMoving` gate (the API exists) and the new test exercises the standing-still case; Pyright 0 versus a 0 base.

### [#157 - Use the existing echo-spreading owner for Mending Refrain](https://github.com/apoguita/Py4GW_Reforged/pull/157)

- Review verdict: APPROVE for the reviewed source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `5c0d186d3d70b3339e163402b000b6026b13e768`; changes: 2 files, +35/-19.
- Files: `Examples and tests/tests/test_mending_refrain_spread.py`, `Py4GWCoreLib/Builds/Skills/paragon/Motivation.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Classification: semantic skill-specific change; first-batch candidate. No code changes requested.
- Verified: Replaces the Mending_Refrain helper with delegation to BuildMgr.SpreadEchoToAlly. Current BuildMgr implements castability, range-limited target resolution, cast and target restoration. This changes that skill-specific BuildMgr path and does not modify generic HeroAI. No cross-PR dependency was established.
- Independent checks: full patch and relevant current owner inspected; five patches applied together in isolated copies and compilation passed. Pyright reported 0 diagnostics for the three route files and Model_enums.py; Pyright was not run for Motivation.py in the isolated copy.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: approval confirmed. `Mending_Refrain` now delegates to the existing `SpreadEchoToAlly` (`BuildMgr.py:585`) instead of resolving its own target; Pyright 0 versus a 0 base.

### [#156 - Include Soul Ignition in HeroAI skill-data capacity](https://github.com/apoguita/Py4GW_Reforged/pull/156)

- Review verdict: APPROVE for the reviewed source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `af839ca01041fb4385b370443bde4b194e4b41a0`; changes: 2 files, +39/-2.
- Files: `Examples and tests/tests/test_skill_table_capacity.py`, `Py4GWCoreLib/HeroAI/custom_skill.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): Increase the existing skill table from 3433 to 3447 entries, including ID 3446. The current fixed allocation and get/set guards cannot register or retrieve Soul Ignition. There is no dynamic replacement upstream. This is the shared prerequisite for the Soul Ig / Dependent submission: #161 includes this identical allocation prerequisite. Merge #156 first to remove that duplicate supporting hunk from #161. #121 merely reads the ID and does not require this table expansion..
- Classification: semantic shared-code change; later batch: shared skill table allocation. No code change requested.
- Verified: Increases CustomSkillClass.MaxSkillData from 3433 to 3447; existing get/set bounds use this constant. This changes allocation for every CustomSkillClass instance. PR #161 repeats the allocation change, so the later integrated diff must be reconciled.
- Independent checks: complete production patch and current owning conditions/priority table inspected; five patches applied together to isolated copies and Python compilation passed. Pyright was not independently run for this batch; author reports are not independent results.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: approval confirmed. The diff is `MaxSkillData` 3433->3447 plus a capacity test, and the `custom_skill.py` blob is still identical to #161's; Pyright 0 versus a 0 base.

### [#155 - Take the Luxon blessing from Gyala Hatchery route data](https://github.com/apoguita/Py4GW_Reforged/pull/155)

- Review verdict: APPROVE for the submitted source change. Release placement: after #192. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `a9c3cbf50e932eef88b7a4387ebd887a8fa1eaf5`; changes: 2 files, +51/-0.
- Files: `Examples and tests/tests/test_gyala_route_blessing.py`, `Sources/aC_Scripts/PyQuishAI_maps/Factions_TheJadeSea/GyalaHatchery.py`.
- Classification: semantic route-data addition plus a route test; contained to one map module; no shared code changes.
- Verified: appends `{"bless": {"name", "faction": "luxon", "target_xy": (7631.0, -19239.0)}}` ahead of the existing path. Base `Simple_Vanquish._handle_keyword` indexes `value[0]`/`value[1]` for `bless`, so a mapping raises `KeyError` during FSM registration; base `PyQuishAI_BT` coerces `bless` through `_coordinate`, which rejects a mapping with `ValueError`. Unlike #207/#211 this is a hard failure in both consumers, not a silent skip, because the key already existed with a coordinate contract. Under #192 the mapping takes the `run_route_blessing` path and, because `faction` is present, calls `TakeBlessing(pos=target_xy, faction='luxon')`.
- Dependency resolution: the description names #148 for opt-in faction-effect verification. The record sets no verify flag and #192 passes none, so the diff does not exercise #148; the executable dependency is #192, and #148 is required only for the claimed verification path. Requested clarification: name #192 as the required merge dependency so the ordering is not misread as "#148 alone".
- Independent checks: exact head fetched and diffed; both consumers and owner contracts inspected; Pyright at head 0 errors, 0 warnings on both changed files. The author's composed caller checks were not rerun; no live-client test or GitHub review.
- Unresolved: whether the author intends `verify_effect` for this route (it is not requested in the record), and capture validity.

### [#154 - Use Ferndale route, canonical blessing and local party preparation](https://github.com/apoguita/Py4GW_Reforged/pull/154)

- Review verdict: REQUEST CHANGES. Release placement: after #148, and only after the shared-owner findings are repaired. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `acfa6707346cf4d6c3e2db40bda11be8e7e9d3f0`; changes: 2 files, +194/-11.
- Files: `Examples and tests/tests/test_vanquish_route_blessing.py`, `Widgets/Automation/Bots/Vanquish/Factions/Echovald Forest/Ferndale.py`.
- Classification: route script change with the same two owner-bound helpers as #153; route data adds a priest coordinate and two detours.
- Verified: the same canonical replacement applies — `_take_kurzick_blessing` calls `BT.TakeBlessing(..., faction="kurzick", multi_account=True, verify_effect=True)` and runs it in a custom state with the HeroAI pause restored; the legacy faction-comparison dialog is removed; the kill route switches to `FollowPath`; two detour segments and `COORDS_FOR_PRIEST` are added.
- Findings and required direction: identical to #153 — extend `Templates.Routines.PrepareForFarm` for the single-account mode rather than copying its callback wiring (the copy omits kick/leave/summon/invite), resolve why `Multibox_Aggressive()` is used with "single-account" preparation, and move the run-in-a-custom-state blessing plumbing to a shared helper instead of duplicating it here and in #153. The two PRs carry the same helper block, so at most one copy should survive.
- Independent checks: exact head fetched and diffed; the canonical signature and guard clauses in #148 read; `PrepareForFarm` read; Pyright at head: route file 1 new diagnostic (`No parameter named "verify_effect"` — the #148 dependency), test 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: detour clearance and effect verification are live claims.

### [#153 - Use Drazach Thicket route, canonical blessing and local party preparation](https://github.com/apoguita/Py4GW_Reforged/pull/153)

- Review verdict: REQUEST CHANGES. Release placement: after #148 (hard dependency on `verify_effect`), and only after the shared-owner findings are repaired. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `2c7bab99c2bd312bce01f2ae63267bc789d2c7f6`; changes: 2 files, +164/-10.
- Files: `Examples and tests/tests/test_vanquish_route_blessing.py`, `Widgets/Automation/Bots/Vanquish/Factions/Echovald Forest/Drazach Thicket.py`.
- Classification: route script change that replaces local blessing dialogue with the canonical owner, but also adds two helpers that belong to shared owners.
- Verified: the inline `XYAndInteractNPC` plus faction-comparison dialog is replaced by `_take_kurzick_blessing`, which builds `BT.TakeBlessing(pos=COORDS_FOR_PRIEST, faction="kurzick", multi_account=True, verify_effect=True)` and ticks it in a custom state with HeroAI paused and restored in `finally`. That pairing is correct: #148 permits `verify_effect` for an ordinary Luxon/Kurzick blessing and only rejects it for captured mappings. The kill route switches from `FollowAutoPath` to literal `FollowPath`.
- Findings and required direction: `_prepare_for_farm` copies the shared routine's three callback registrations and random-district travel while omitting the kick/leave, summon, wait and invite that `Templates.Routines.PrepareForFarm` performs. Extend that owner with a single-account mode instead of copying it, because the next route will copy the same block and the mode then lives in N places. Resolve the mode inconsistency: the widget still calls `Templates.Multibox_Aggressive()` while preparation claims "single-account", so one of the two is wrong. Move the run-tree-in-a-custom-state plumbing into a shared helper, because both this PR and #154 duplicate it and #192's `PyQuishAI_blessing.run_route_blessing` already implements the same lifecycle for Simple Vanquish.
- Independent checks: exact head fetched and diffed; the canonical signature and guard clauses in #148 read; `Templates.Routines.PrepareForFarm` read; Pyright at head: route file 1 new diagnostic (`No parameter named "verify_effect"` — the #148 dependency), test 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: effect verification behavior and literal-path clearance are live claims.

### [#152 - Add ground-item and held-slot diagnostic widget](https://github.com/apoguita/Py4GW_Reforged/pull/152)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `2c0685c5cd447db4ae10bf242aa87b0106775a5d`; changes: 2 files, +299/-14.
- Files: `Examples and tests/tests/test_ground_item_dump.py`, `Widgets/Coding/Debug/Py4GW/Ground Item Dump.py`.
- Classification: extension of an existing diagnostic widget plus a focused test; no shared code.
- Verified: the widget gains a held-slot evidence section and `_try_value`/`_evidence_line` helpers so a failing accessor is recorded as evidence instead of aborting the dump, matching the file's stated defensive policy. The log target moves from `docs/automation/loot_redesign/ground_item_dump.log` to `diagnostics/ground_item_dump.log`, which is an improvement: operational logs do not belong under `docs/`. The settings document continues to use the `Settings(f"{INI_PATH}/{INI_FILENAME}", "account")` jail form.
- Baseline note: the widget's custom file logging (`open(path, "a")` / `open(path, "w")`) is pre-existing, not introduced here, so the persistence-diagnostic rule is not newly violated; the PR relocates the artifact rather than adding a mechanism.
- Independent checks: exact head fetched and diffed; the evidence helpers, log-path change and settings use read; Pyright at head 0 errors on both files. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether the held-slot evidence matches the engine's possession surface; that is exactly what the widget is designed to discover.

### [#151 - Add Party Trade Collector widget](https://github.com/apoguita/Py4GW_Reforged/pull/151)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `e8e45e5dc3ceb2e5b9e131b35415599de92018be`; changes: 1 files, +3148/-0.
- Files: `Widgets/Automation/Multiboxing/Party Trade Collector.py`.
- Classification: additive leaf widget; no library or shared-consumer change.
- Verified: persistence stays inside the documented jail — every document is created through the concrete `Settings("Widgets/PartyTradeCollector/<name>.ini", "global")` form, the same `(name, scope)` convention used by other widgets, so files remain under `settings/Global/<name>`. Window handling follows the ImGui owner: a single module-level `draw()` opens with `ImGui.BeginWithClose` and `PyImGui.set_next_window_size(..., FirstUseEver)`, so ImGui owns size and position after first use; the other `draw()` callables are closures returned by cell factories, not duplicate module entry points. No sockets, threads or raw file writes appear. The native trade binding is loaded defensively through `importlib.import_module("PyTrade")` and the module degrades to `None` when absent. `update()` and `draw()` are the exported callbacks, and `WIDGET_NAME` matches the file stem for the remote enable command.
- Notes: it is a 3,148-line single-file widget with no author test; that is a maintainability cost rather than a correctness defect, and the widget is self-contained.
- Independent checks: exact head fetched and reviewed in structure and by targeted scans (persistence, window, IO, threads, dynamic imports); the `Settings` constructor and jail documented in `Settings.py` read; Pyright at head 0 errors. No live-client test or GitHub review.
- Unresolved: trade behavior against the live `PyTrade` binding cannot be established statically.

### [#150 - Add new consumable model IDs](https://github.com/apoguita/Py4GW_Reforged/pull/150)

- Review verdict: APPROVE for the reviewed source change. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `6c9fea6e82a817ca5e619536ec779b34274469f5`; changes: 1 files, +10/-0.
- Files: `Py4GWCoreLib/enums_src/Model_enums.py`.
- Patch check: passed against local checkout.
- Dependency statements (author-provided, not independently resolved): none detected by text search; absence is not proof of independence.
- Classification: additive enum data; first-batch candidate. No code changes requested.
- Verified: Adds ten ModelID enum members. AST inspection found no existing entries with the ten new numeric IDs. PRs #214 and #175 repeat some names, so after integrating this PR their diffs must be rechecked; merging duplicate Python enum names without reconciliation can break import. Item-name/ID source claims are author-provided.
- Independent checks: full patch and relevant current owner inspected; five patches applied together in isolated copies and compilation passed. Pyright reported 0 errors, 0 warnings, 0 information for the three route files and Model_enums.py.
- Runtime: no live-client test was run or required by the user. No GitHub review was submitted.

- Release placement (derived from the recorded verdict; the prior session did not state one): any time; no dependency is recorded and the recorded verdict requests no changes..
- Unresolved (not recorded by the prior session): the prior session did not record a separate unresolved-facts line; the evidence above stands unchanged, no live-client behavior was verified, and no GitHub review was submitted..
- Re-verified this session: approval confirmed. All nine added model ids are free at the snapshot base; `Birds_Eye_Compass`/`Stalkers_Ration` still overlap #214, `Infinite_Identification_Kit`/`Infinite_Superior_Salvage_Kit` still overlap #175, and #125 adds the same two values under different names. Pyright 0 versus a 0 base.

### [#148 - Extend TakeBlessing with captured blessings and identity targeting](https://github.com/apoguita/Py4GW_Reforged/pull/148)

- Review verdict: APPROVE for the submitted source change. Release placement: first in the blessing-owner chain; every route PR that passes `verify_effect` or `captured_blessing` must follow it. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `f97bca9b3412ce98414d009b139934c1391b1c24`; changes: 5 files, +1813/-33.
- Files: `Examples and tests/tests/test_faction_blessing_effect.py`, `Examples and tests/tests/test_take_blessing.py`, `Examples and tests/tests/test_take_blessing_identity.py`, `Sources/ApoSource/ApoBottingLib/wrappers.py`, `Sources/aC_Scripts/aC_api/Captured_Blessing.py`.
- Classification: owner extension at the canonical blessing owner plus a new captured-blessing execution module; no parallel blessing controller.
- Verified: `TakeBlessing` gains `captured_blessing`, `encoded_identity`, `model_id`, `identity_search_radius` and a keyword-only `verify_effect`. `verify_effect` raises unless the faction is an ordinary Luxon or Kurzick blessing; `captured_blessing` raises when `multi_account=True` ("local execution only"); a captured mapping is normalized through `CapturedBlessingSpec.from_mapping`, which derives `interaction_mode` (defaulting to `first`) and switches to the Norn mode when the effect set intersects `NORN_HUNTING_PARTY_EFFECT_IDS`. The captured path runs `CanonicalCapturedBlessingRunner`, deliberately separate from the `Blessing_Core.BlessingRunner` (stated in the module docstring), and the legacy single/multi-button conversation path is preserved (`resolved_buttons`, `outcome_key`, fresh buttonless response). Three focused tests cover the effect, identity and general paths, and the optional verification uses the existing `Verify_Blessing` module.
- Dependency resolution: #192's adapter passes `captured_blessing=` with `multi_account=False` and no `verify_effect`, which the contract accepts; #153/#154 pass `faction="kurzick"` with `verify_effect=True` and `multi_account=True`, which the contract also accepts. The captured path intentionally does not support multi-account dispatch yet.
- Independent checks: exact head fetched and diffed; the full signature, both guard clauses, the captured runner handoff and the preserved legacy sequence read; `Verify_Blessing.py` existence confirmed; Pyright at head: `wrappers.py` 1 error identical to the base diagnostic, the new module and all three tests 0. Author tests not rerun; no live-client test or GitHub review.
- Unresolved: the five-second effect-verification window and the Norn post-fight reacquisition are live-behavior claims; the multi-account captured path is explicitly unsupported rather than deferred.

### [#147 - Keep shared command failures from skipping later queued work](https://github.com/apoguita/Py4GW_Reforged/pull/147)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `e872186e7af2be2e6f487f6f6a2a250c7633aae1`; changes: 2 files, +52/-1.
- Files: `Examples and tests/tests/test_shared_command_errors.py`, `Widgets/System/Environment Upkeeper.py`.
- Classification: widget-level coroutine lifecycle fix in the existing shared command loop; focused test.
- Verified: the loop iterates `GLOBAL_CACHE.Coroutines[:]`, a copy, so retiring one routine cannot make the iteration skip the next queued entry. `StopIteration` removal is now guarded by membership, and a new `except Exception` branch logs the module name, the exception text and `traceback.format_exc()` through `ConsoleLog` (the approved diagnostic mechanism) at Error level before retiring the failed routine — failures are no longer silent and the remaining routines still run. No file persistence or new diagnostic file is introduced.
- Independent checks: exact head fetched and diffed; the loop head, both retirement paths and the coroutine container type (`List[Generator]` in `GlobalCache.py`) read; Pyright at head 0 errors on both files. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether retiring a failed routine leaves partial queue state that the widget should also reset, and whether the logged traceback is the right volume for a routinely failing command.

### [#145 - Add an operator Pause that internal movement resumes cannot release](https://github.com/apoguita/Py4GW_Reforged/pull/145)

- Review verdict: APPROVE for the submitted source change. Release placement: any time, but coordinate the movement-cancellation approach with #167. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `bddda499df3dcad365176b5f0187e0b0f413a080`; changes: 5 files, +204/-27.
- Files: `Examples and tests/tests/test_operator_pause.py`, `Py4GWCoreLib/Botting.py`, `Py4GWCoreLib/botting_src/helpers_src/Upkeepers.py`, `Py4GWCoreLib/botting_src/subclases_src/UI_src.py`, `Py4GWCoreLib/py4gwcorelib_src/FSM.py`.
- Classification: FSM and bot lifecycle extension with UI wiring; the HeroAI pause is extracted into owned apply/release functions.
- Verified: `FSM` gains `operator_paused`, separate from the internal `paused`, and `is_paused()` covers both, so internal resumes cannot clear an operator pause. `Botting.Pause` pauses by operator, applies `hero_ai_paused` immediately through the new `apply_hero_ai_pause`, and queues `StopMovement` under a de-duplicated coroutine name (`AddManagedCoroutine` no-ops on an attached name). `release_hero_ai_pause` restores only the HeroAI fields that are still False, so a newer manual choice is not overwritten — the ownership rule the guide requires. Start, Stop and StartAtStep clear the operator pause; the UI gains a Pause/Continue button and the state description reflects the operator pause. The pre-existing pause snapshot/restore was refactored into the same functions rather than duplicated.
- Notes: the Pause comment explicitly states that moving to the current position is not a reliable cancellation of an active click-to-move command, which contradicts #167's approach to the same problem. That is a cross-PR coordination item, not a defect in this implementation.
- Independent checks: exact head fetched and diffed; FSM pause lifecycle, bot Pause/Resume/release and the upkeeper apply/release read; `FSM.resume`/`resume_by_operator` and `AddManagedCoroutine` de-duplication verified in source; Pyright at head 0 errors on every changed file and the test. Author test not rerun; no live-client test or GitHub review.
- Unresolved: interaction between the operator pause, the combat/looting gates and other pause owners; and whether the queued `StopMovement` coroutine interacts with the FSM's managed-coroutine lifecycle as intended.

### [#144 - Keep planner control exclusive during combat and looting](https://github.com/apoguita/Py4GW_Reforged/pull/144)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `1365fb6573c53ae3743928a6f6ae7c6bdad190e2`; changes: 3 files, +188/-0.
- Files: `Examples and tests/tests/test_planner_ownership.py`, `Py4GWCoreLib/botting_tree_src/ticks.py`, `Py4GWCoreLib/routines_src/behaviourtrees_src/movement.py`.
- Classification: planner gating behavior in the shared tick owner plus a movement rebase hook; focused test.
- Verified: `_tick_planner` now derives a pause reason (inactive, manual pause, party wipe, combat, looting), publishes `movement_scheduler_pause_serial` and `movement_scheduler_pause_reason` when one holds, and returns `RUNNING` for the combat and looting gates so the planner tree is not ticked while HeroAI owns control. The movement node compares the serial against its own stored value, and on a change stops strafing, clears avoidance, resets its timeout, marks itself paused with the published reason and clears its stall-retry count.
- Notes: the serial increments on every gated tick rather than on the pause edge. That is harmless only because the gated branches return before the movement subtree is ticked; a consumer that ticks the same movement nodes through another path while the planner is gated would reset its timeout every tick. The gating is also a behavior change for every planner consumer: the planner no longer advances during combat or looting.
- Independent checks: exact head fetched and diffed; the gate ladder and the movement rebase read in full; Pyright at head 0 errors on both modules and the test. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether withholding planner ticks through long fights starves planner-side state that only advances on tick.

### [#143 - Keep Icy Prism targeting and priority in its skill definition](https://github.com/apoguita/Py4GW_Reforged/pull/143)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `b175a49421ff2b7ec9b76a2918515a2b8ed9dccf`; changes: 6 files, +166/-5.
- Files: `Examples and tests/tests/test_icy_prism_policy.py`, `Py4GWCoreLib/HeroAI/combat.py`, `Py4GWCoreLib/HeroAI/custom_skill_src/elementalist.py`, `Py4GWCoreLib/HeroAI/custom_skill_src/icy_prism.py`, `Py4GWCoreLib/HeroAI/custom_skill_src/skill_types.py`, `Py4GWCoreLib/SkillManager.py`.
- Classification: skill-local policy under the Elementalist definition, enabled through two optional hooks on the shared skill data.
- Verified: `icy_prism.py` owns both policies. `HasWaterMagicHex` walks buffs plus effects and requires a Water Magic hex by attribute id; `TargetWaterHexedClusteredEnemy` ranks water-hexed targets by nearby companions first and player distance second; `select_priority` promotes Icy Prism to `OffensiveA` only when at least one nearby companion exists, otherwise demotes it to `CustomN`. `CustomSkill` gains `TargetSelector`/`PrioritySelector` defaulting to `None`, and both `HeroAI/combat.py` (precomputed effective natures) and `SkillManager.py` (`_PrioritizeSkills`, `_GetAppropiateTarget`) consult them before their normal logic, so absent policies preserve current behavior exactly.
- Notes: the new hooks must be consulted by both engines for any future policy skill, which is now an explicit contract; selector calls add enemy scans to priority construction and target resolution.
- Independent checks: exact head fetched and diffed; new module, both selector call sites and the enum/import surface read; Pyright at head: `combat.py` 17 equal to base, every other file and the test 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: the live value of the priority promotion, and the default cluster radius choice, are policy claims that only play can validate.

### [#142 - Prefer unbuffed melee party members, then melee summons for Strength of Honor](https://github.com/apoguita/Py4GW_Reforged/pull/142)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `d67649d9b801fcad7866cf20f278f1236394232d`; changes: 8 files, +139/-3.
- Files: `Examples and tests/tests/test_honor_target_priority.py`, `Py4GWCoreLib/Agent.py`, `Py4GWCoreLib/BuildMgr.py`, `Py4GWCoreLib/HeroAI/combat.py`, `Py4GWCoreLib/HeroAI/custom_skill_src/monk.py`, `Py4GWCoreLib/HeroAI/targeting.py`, `Py4GWCoreLib/HeroAI/types.py`, `Py4GWCoreLib/SkillManager.py`.
- Classification: skill targeting policy at the owning target helpers, with the Monk skill definition re-pointed and both consumer engines updated.
- Verified: `TargetStrengthOfHonor` collects maintained targets from the caster's buff list and from every active slot's buff data, then returns the first unbuffed melee party member within range, falling back to the nearest eligible summon (pet, minion, owned agent or party-window viewer) that is not a party member. Eligibility requires validity, targetability, life, range and melee classification; `Agent.IsTargettable` wraps an existing native binding (`PyAgent.pyi:103`), and `Checks.Agents.IsMelee` already returns True for pets. `monk.py` switches Strength of Honor from `AllyMartialMelee` to the new `StrengthOfHonor` allegiance, and `BuildMgr`, `_GetAppropiateTarget` and `HeroAI/combat.py` all dispatch to the new helper, so both engines agree.
- Notes: the policy performs an all-active-slot buff scan on every targeting call, which is heavier than the previous single-allegiance lookup; the maintained-target detection assumes buff records expose `target_agent_id`. The change affects every build that uses Strength of Honor because the Monk definition is shared.
- Independent checks: exact head fetched and diffed; every helper and native binding it calls verified; all four dispatch sites read; Pyright at head: `BuildMgr.py` and `combat.py` equal their base diagnostics, `targeting.py` 0 (it carried one at base), all other files and the test 0. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether live buff records expose maintained targets as assumed, and whether the added per-call buff scan is acceptable at HeroAI tick rate.

### [#141 - Restore Minion Master summoning with shared Masochism handling](https://github.com/apoguita/Py4GW_Reforged/pull/141)

- Review verdict: REQUEST CHANGES. Release placement: after the golem-identification fix; the reinstatement also needs its rollback rationale recorded. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `268878be0f9fed6b18d6d368aa65631baa61fb2b`; changes: 5 files, +357/-3.
- Files: `Examples and tests/tests/test_masochism_summon_use.py`, `Examples and tests/tests/test_minion_master_reintroduction.py`, `Py4GWCoreLib/Builds/Necromancer/N_Any/Minion Master.py`, `Py4GWCoreLib/Builds/Skills/necromancer/SoulReaping.py`, `Py4GWCoreLib/enums_src/Model_enums.py`.
- Classification: reinstatement of a reverted build controller, with a small owner extension and a canonical enum addition.
- Verified: commit `53a04740` (PR #132) had reverted exactly this controller file; the reinstated version is not a blind copy — versus the reverted file it imports `AgentModelID`, drops the local golem constant, and replaces a raw `CastSkillID(MASOCHISM_ID, ...)` with `skillbook.Necromancer.SoulReaping.Masochism(require_aggro=False)`. `SoulReaping.Masochism` gains a keyword-only `require_aggro` defaulting to True, so existing callers keep the aggro gate while the Minion Master may cast after a fight. `AgentModelID.FLESH_GOLEM = 2795` collides with nothing in the enum, and both new tests pass Pyright.
- Finding and required direction: `_has_owned_flesh_golem` compares `Agent.GetPlayerNumber(minion_agent_id)` with `AgentModelID.FLESH_GOLEM` (2795). Player numbers are small integers, so the comparison can never match and the "no golem yet" gate is permanently true — the controller will keep summoning a golem whenever a corpse and the skill are available. Compare `Agent.GetModelID(minion_agent_id)` instead (the API exists) and add a test for that gate, because the current tests cover the count and capacity helpers but not golem identification. Also record in the description why the controller was reverted and how this version answers that reason, since a reinstatement after a rollback needs its own justification.
- Independent checks: exact head fetched and diffed against both the base and the reverted version (`53a04740^`); the golem gate, summon capacity logic, `SoulReaping.Masochism` and both tests read; `Agent.GetPlayerNumber` and `Agent.GetModelID` signatures inspected; Pyright at head 0 errors on every changed file and both tests. Author tests not rerun; no live-client test or GitHub review.
- Unresolved: whether the reverted controller's original rollback reason was code-related or policy-related, and whether golem re-summon behavior has other live consequences beyond corpse use.

### [#140 - Share failed pickup suppression across account widgets](https://github.com/apoguita/Py4GW_Reforged/pull/140)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `ee14c16049168995e6283f0b25c231c9665e4526`; changes: 3 files, +184/-3.
- Files: `Examples and tests/tests/test_failed_pickup_suppression.py`, `Py4GWCoreLib/GlobalCache/WhiteboardLocks.py`, `Py4GWCoreLib/py4gwcorelib_src/system_settings/loot_filters/controller.py`.
- Classification: extension of the existing shared whiteboard-lock owner plus a narrow controller integration.
- Verified: `WhiteboardLocks.py` already exists at the snapshot; this PR adds only the suppression section (`LOOT_SUPPRESSION_KEY_BASE`, `_loot_suppression_key`, `is_loot_suppressed`, `post_loot_suppression`, `clear_loot_suppressions`) on the existing `ShMem.PostLock`/`GetAllIntents`/`ClearIntent` API, so no parallel store is introduced. Suppression is keyed by map (`1_000_000 + map_id`) and owner-scoped by email and isolation group, deliberately includes the same account's own locks so a terminal failure reaches independently loaded HeroAI and Botting selectors, and refreshes an existing slot instead of posting a duplicate. The controller posts on `report_failed`, consults it in `wants`, clears it on a real map change, and the `_check_map` change correctly avoids treating first discovery as a transition so another widget's published failure is not wiped on startup.
- Notes: `wants` runs per candidate item inside `GetLootArray`, and the suppression lookup performs a full intent scan each call; consider a per-frame cached suppressed set if loot arrays are large.
- Independent checks: exact head fetched and diffed; the new suppression functions, controller integration and the existing lock API signatures read; Pyright at head 0 errors on both files and the test. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether a six-hour TTL without a map change is the intended fallback when an account leaves the explorable area through a non-map-change path.

### [#139 - Maintain Honor and Life Bond on melee party members](https://github.com/apoguita/Py4GW_Reforged/pull/139)

- Review verdict: REQUEST CHANGES. Release placement: any time, but the shared-predicate effect must be resolved first. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `8f5daa6909362fa242397554bd38c7e0bceebdd7`; changes: 2 files, +146/-38.
- Files: `Examples and tests/tests/herohelper_local/test_strength_of_honor.py`, `Widgets/Automation/Enhancements/HeroHelper.py`.
- Classification: widget-level maintenance behavior built on new target helpers; the change also redefines a shared classification helper.
- Verified: Strength of Honor and Life Bond now maintain through `find_maintenance_cast` over `get_physical_party_targets(melee_only=True)`, so the target's own weapon decides eligibility rather than the player's; Life Bond excludes the caster; the smart-skill UI text now states that bows and spears are excluded. `holds_melee_weapon`/`holds_physical_weapon` accept an agent id, and hero skill caching is keyed with the hero agent id so cached lookups resolve the right agent. The focused test was extended and reports no diagnostics.
- Finding and required direction: the same `holds_melee_weapon` is consumed by the hex-removal classification pair (`hexes_melee`/`hexes_caster`, lines 941-942) and by three melee-enchantment paths (lines 1011, 1036, 1112). Dropping Spear therefore reclassifies spear-wielding Paragons in those paths, which the new UI text does not cover and the PR description does not state. Give the buff maintenance its own predicate (for example a weapon-set argument or a dedicated helper) so the hex and enchantment classifications keep their previous meaning, or state explicitly that Paragon spear users should now be treated as non-melee everywhere and show that the affected paths still behave.
- Independent checks: exact head fetched and diffed; every caller of the two predicates enumerated at base; `Agent.GetWeaponItemType` and the `ItemType` members verified; Pyright at head 0 errors on both files. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether bow/spear exclusion matches how the owning heroes should prioritize melee targets in mixed parties.

### [#138 - Prioritize Heroic Refrain maintenance before party refill](https://github.com/apoguita/Py4GW_Reforged/pull/138)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `bf76aaf476b29973fac4dac8364490cfcad907cb`; changes: 5 files, +120/-52.
- Files: `Examples and tests/tests/test_hr_maintenance_priority.py`, `Examples and tests/tests/test_paragon_refrain_atomic_handlers.py`, `Py4GWCoreLib/Builds/Paragon/P_W/Defensive Refrain.py`, `Py4GWCoreLib/Builds/Skills/paragon/Command.py`, `Py4GWCoreLib/Builds/Skills/paragon/Leadership.py`.
- Classification: build-rotation reorder at the owning Paragon build plus a split of the skill helper it calls; no new mechanism.
- Verified: `Leadership.Heroic_Refrain` is split into `Heroic_Refrain_Self` (self bootstrap only, returning False when the bootstrap is complete) and `Heroic_Refrain_Party` (requires `IsHeroicRefrainSelfReady()` and resolves its target with `ResolveAllyTargetInRange`), with the original name kept as a wrapper so other callers keep working; `IsHeroicRefrainSelfReady` documents the rank-20 observable postcondition. The build now orders self bootstrap, Cant Touch This maintenance, "They're on Fire!", party Heroic Refrain repair, refrain spreading, Aggressive Refrain and Anthem of Flame, with comments explaining that maintenance deadlines outrank distribution. `Command.py` changes are comment/whitespace only. Both tests report zero diagnostics.
- Notes: this deliberately changes when CTT and "They're on Fire!" fire relative to party refrains — the PR's stated purpose, but a rotation behavior change for every user of this build.
- Independent checks: exact head fetched and diffed; the split methods, wrapper, postcondition and reordered rotation read; `Heroic_Refrain_Self`/`_Party` confirmed present at head; Pyright at head 0 errors on all three modules and both tests. Author tests not rerun; no live-client test or GitHub review.
- Unresolved: whether the reordered maintenance truly outranks refill in live fights, and whether range-restricted party targeting degrades refill coverage.

### [#137 - Add combined Halloween Skeleton Farmer widget](https://github.com/apoguita/Py4GW_Reforged/pull/137)

- Review verdict: REQUEST CHANGES. Release placement: blocked on the shared-dependency gap (#168 among them) and on the persistence finding. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `ea50658d5b22f82287abc7b58719ed51bdd09cf8`; changes: 6 files, +2577/-0.
- Files: `Sources/HalloweenSkeletonFarmer/README.md`, `Sources/HalloweenSkeletonFarmer/__init__.py`, `Sources/HalloweenSkeletonFarmer/capture.py`, `Sources/HalloweenSkeletonFarmer/mobstoppers.py`, `Sources/HalloweenSkeletonFarmer/turn_ins.py`, `Widgets/Automation/Helpers/Halloween Skeleton Farmer.py`.
- Classification: new feature package with a host widget; not a migration.
- Verified: three independently started jobs are described and implemented, all start stopped, and the capture job requires Dash plus Death's Charge or Dark Prison. `mobstoppers.py` and `turn_ins.py` use `Settings("Widgets/<name>.ini", "account")`, which stays inside the settings jail, and the widget file itself introduces no window or persistence code.
- Blockers and required direction: `capture.py` writes JSONL through `Path.open('a')` plus `json.dumps` into `Logs/HalloweenSkeleton`, a custom file-backed diagnostic mechanism the repository forbids without explicit infrastructure authorization — use the approved diagnostics/storage owner or seek that authorization as a separate change. The same file calls `BTMovement.MovePath(..., resume_key=...)`, a parameter that only #168 introduces, so the package cannot type-check or run against the snapshot without it — declare and sequence that dependency or drop the parameter. The new files report 25 Pyright diagnostics, including a `protect` attribute on `ApproachAndSkills` that does not exist upstream, which matches the README's statement that upstream lacks the shared dependencies; resolve those against current owners instead of shipping a local-variant draft. Finally, the README itself states "It is not ready to merge", so a PR carrying a self-declared-unmergeable draft should be split rather than presented for merge.
- Independent checks: exact head fetched and reviewed in structure and by targeted scans (persistence, window, IO, settings); README and all four code files inspected; Pyright at head: `capture.py` 21, `mobstoppers.py` 2, `turn_ins.py` 2, widget 0. No test file exists for this package; no live-client test or GitHub review.
- Unresolved: capture geometry, the ten-second resign deadline interaction, and whether the three jobs share instance state correctly are live claims.

### [#136 - Update Issnur Isles bridge and boat route with cartography hold](https://github.com/apoguita/Py4GW_Reforged/pull/136)

- Review verdict: REQUEST CHANGES. Release placement: after #192 for its blessing records, and only after the shared-widget findings are repaired. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `a0b29f22653870f3008de18598843d22dbbcc492`; changes: 4 files, +266/-12.
- Files: `Py4GWCoreLib/routines_src/behaviourtrees_src/cartography.py`, `Sources/aC_Scripts/PyQuishAI_maps/NF_Istan/IssnurIsles.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`, `tests/test_issnur_isles_route.py`.
- Classification: mixed — a new library behavior-tree capability, a shared-widget integration, a route-data update and a test.
- Verified: the new library module is the right layer for a reusable hold and is API-correct (`BehaviorTree(root)` at `BehaviorTree.py:2020`, resolving `Map`/`Player`/`BehaviorTree` imports). The route converts four blessing coordinates to captured values, replaces the bridge point with two captured bridge points, and moves the boat exit into `literal_path` + `cartography_hold` + `literal_path` + `path`. The widget adds `cartography_hold` (ticks the tree in a custom state and resets it in `finally`), re-adds `literal_path`, and branches the outpost transit on `vq.explorable_id == 486`, which is Issnur Isles' explorable id from `IssnurIsles_ids["map_id"]`.
- Required direction: replace the `explorable_id == 486` branch with a route-owned or generic transit mode, because a literal map id in the shared `bot_routine` creates a second owner for transit behavior and every subsequent special map would add another branch. Drop the duplicated `literal_path` block, because three other PRs add the identical lines. Move `tests/test_issnur_isles_route.py` under `Examples and tests/tests/`, because the repository has a single test root. Fix or justify the new test's six Pyright diagnostics, because the changed-file check is mandatory and currently not clean.
- Independent checks: exact head fetched and diffed; library module imports/constructor/validation inspected; route and widget consumers inspected; `ForMapLoad(target_map_id, timeout_ms)` signature confirmed (`WAIT_src.py:154`); Pyright at head: module 0 errors, route 0 errors, widget 105 against the 101 baseline (four diagnostics, all pre-existing class), test 6 errors (scaffolding artifacts). Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether the cartography hold reveals the intended corner, and whether the boat transit needs a per-map mode by design.

### [#135 - Fix Kinya Province bridge crossings and add detours](https://github.com/apoguita/Py4GW_Reforged/pull/135)

- Review verdict: REQUEST CHANGES. Release placement: after the `literal_path` ownership decision, and only after the BottingTree consumer can execute it or Kinya Province is excluded. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `3456752dc1e3b974423943502b1e0c0e954f9614`; changes: 3 files, +178/-74.
- Files: `Examples and tests/tests/simple_vanquish/test_kinya_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/Factions_ShingJeaIsland/KinyaProvince.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`.
- Classification: route restructure plus a copy of the shared `literal_path` keyword; the widget hunk is not specific to this route.
- Verified: the flat route becomes tuple-list segments with four `literal_path` crossings (two bridges and a detour pair), each carrying a capture id. Seven original waypoints are absent from the head; each is replaced by a captured bridge or detour run, and the file header names the two bridge captures, so the replacement is documented. The widget adds the same `literal_path` handling and `_get_first_path_coord` change as #124/#136/#195. Kinya Province is a BottingTree map (`PyQuishAI_BT.py:145`) with no `literal_path` support, so the route still cannot run under BT after the keyword owner lands.
- Required direction: drop the `Simple_Vanquish.py` hunks and take `literal_path` from its single owner, because four PRs add the identical block and the second merge conflicts. Add `literal_path` to the BottingTree consumer or keep Kinya Province out of its path. Fix or justify the test's four Pyright diagnostics, because the changed-file check is mandatory.
- Independent checks: exact head fetched and diffed; normalized comparison against every base coordinate; consumers and BT table inspected; Pyright at head: route 0 errors, widget 101 equal to baseline, test 4 errors (scaffolding artifacts). Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether the capture-derived crossings clear both bridge planes in practice.

### [#134 - Use native live overcast reader](https://github.com/apoguita/Py4GW_Reforged/pull/134)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `96a150ed6240a2fc3bb7b22a55ad1e287c7f8833`; changes: 2 files, +7/-4.
- Files: `Py4GWCoreLib/Agent.py`, `stubs/PyAgent.pyi`.
- Classification: small owner fix replacing a raw struct-field read with the native binding, plus its stub.
- Verified: `Agent.GetOvercast` now returns `max(0.0, float(PyAgent.get_overcast(agent_id)))` inside a narrow `except (AttributeError, TypeError, ValueError)` that degrades to `0.0`, replacing the previous `living.h0128` offset read. The stub declares `get_overcast(agent_id: float)` alongside the existing `PyAgent` declarations. Callers that gate on overcast (including the Swirling Aura priority in #160) therefore read the same live value without a struct-offset dependency.
- Notes: when the shipped native module lacks the binding, the helper silently returns zero overcast rather than raising, which is a deliberate degradation but means overcast-gated features quietly do nothing on an older DLL.
- Independent checks: exact head fetched and diffed; the binding declaration and both diagnostics inspected; Pyright at head 0 errors on both files. No test file; no live-client test or GitHub review.
- Unresolved: whether the deployed native build exposes `get_overcast`, and whether its units match the previous field read.

### [#133 - Handle Pious Renewal teardown ordering in HeroAI](https://github.com/apoguita/Py4GW_Reforged/pull/133)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `2a0fd6e7cab504783662e03718adaf0fa0155905`; changes: 2 files, +276/-1.
- Files: `Examples and tests/tests/test_pious_renewal_order.py`, `Py4GWCoreLib/HeroAI/combat.py`.
- Classification: skill-ordering gate inside the HeroAI combat owner plus a focused test.
- Verified: the class records the Pious Renewal id and the Dervish teardown skills (filtered for resolvable ids). `_newest_dervish_enchantment` walks the player's effects, skips expired ones by duration versus elapsed, ignores invalid timestamps and returns `None` when the newest timestamp is ambiguous. A refresh of Pious Renewal is then blocked while it is itself the newest Dervish enchantment or while order is unknown, and teardown attacks are blocked unless Pious Renewal is the newest — applied consistently in the readiness check, the out-of-combat scan and the cast path, so a teardown cannot fire at the wrong moment. The new test was read and reports the same single AST-scaffolding diagnostic as the other structural tests.
- Notes: behavior is deliberately conservative on ambiguity (no refresh, no teardown) which is the right failure direction for an enchantment chain. The logic depends on live effect `timestamp`, `duration` and `time_elapsed` fields and on `Skill.GetType`/`GetProfession` returning the string members used here.
- Independent checks: exact head fetched and diffed; all four gate sites and the helpers read; Pyright at head: `combat.py` 17 equal to base, test 1 scaffolding diagnostic. Author test not rerun; no live-client test or GitHub review.
- Unresolved: whether the client always populates effect timestamps for Dervish enchantments, and whether the newest-enchantment heuristic matches the skill's actual teardown rule in live combat.

### [#129 - Update Lornar's Pass vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/129)

- Review verdict: APPROVE for the submitted source change (re-review; the prior session's `APPROVE for the reviewed source change` evidence block was overwritten by the batch-11 script and is not recoverable here). Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `9e116fb98f85c69a2394f8c55427348568604251`; changes: 1 files, +64/-1.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/Proph_SouthernShiverpeaks/LornarsPass.py`.
- Classification: additive route-data change; a new out-and-back spur inserted into the flat coordinate list; no shared code, no new keywords.
- Verified: the added block walks a 25-point spur and returns along the same points to the previous waypoint, so the loop is self-contained and the route continues on its original line. Because the route stays a flat list, both consumers already execute it and the bot's reverse cleanup passes traverse it without new keyword support; Lornar's Pass is in the BT table (line 265) and needs nothing new.
- Independent checks: exact head fetched and diffed; BT table inspected; Pyright at head 0 errors, 0 warnings. No author test exists and none was rerun; no live-client test or GitHub review.
- Unresolved: whether the spur's far end actually clears the missed foe group.

### [#128 - Add conditional cleanup loop to Dreadnought's Drift route](https://github.com/apoguita/Py4GW_Reforged/pull/128)

- Review verdict: APPROVE for the submitted source change (re-review; the prior session's `APPROVE for the reviewed source change` evidence block was overwritten by the batch-11 script and is not recoverable here). Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `33598997f9938d623e0447d4a6ca6a7a9c43ce8e`; changes: 1 files, +38/-0.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/Proph_SouthernShiverpeaks/DreadnoughtsDrift.py`.
- Classification: additive route-data change; a 38-point loop appended to the flat coordinate list.
- Verified: the append is pure coordinates — no dictionary keys, no widget changes — so the "conditional" behavior comes from the existing reverse cleanup passes re-traversing it rather than from new route grammar. Both consumers execute flat lists unchanged and Dreadnought's Drift is in the BT table (line 260) without needing new keywords. The loop rejoins the route through a repeated near-identical endpoint, which is the same pattern other appended cleanup blocks use.
- Independent checks: exact head fetched and diffed; BT table inspected; Pyright at head 0 errors, 0 warnings. No author test exists and none was rerun; no live-client test or GitHub review.
- Unresolved: whether the loop covers the intended patrol group and whether it duplicates the built-in reverse sweep.

### [#127 - Update Snake Dance vanquish route](https://github.com/apoguita/Py4GW_Reforged/pull/127)

- Review verdict: APPROVE for the submitted source change (re-review; the prior session's `APPROVE for the reviewed source change` evidence block was overwritten by the batch-11 script and is not recoverable here). Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `febcac78e18131b237623757328cb3e0f1e23501`; changes: 1 files, +105/-1.
- Files: `Sources/aC_Scripts/PyQuishAI_maps/Proph_SouthernShiverpeaks/SnakeDance.py`.
- Classification: additive route-data change; two out-and-back spur blocks inserted into the flat coordinate list.
- Verified: a ten-point spur is inserted early in the route and a longer ~34-point spur later, both returning along their own points to the surrounding waypoints. The file stays a flat list with no dictionary keys or widget changes, so both consumers execute it unchanged and the BT consumer needs nothing new; Snake Dance is in the BT table (line 267).
- Independent checks: exact head fetched and diffed; BT table inspected; Pyright at head 0 errors, 0 warnings. No author test exists and none was rerun; no live-client test or GitHub review.
- Unresolved: whether both spurs clear the intended groups and whether the early spur is reachable without a bridge detour.

### [#126 - Fix HeroAI follow after client reconnect](https://github.com/apoguita/Py4GW_Reforged/pull/126)

- Review verdict: APPROVE for the submitted source change. Release placement: any time; no dependency. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `86f0e0ae910e1af6cc8aaf25f2732e240ad6b890`; changes: 1 files, +162/-27.
- Files: `Py4GWCoreLib/HeroAI/follow/leader_publish.py`.
- Classification: identity and bootstrap fix inside the follow publisher; no new mechanism.
- Verified: the map signature loses its `PartyID` component and is now read from the live client (`Map.GetMapID`, `Map.GetRegion()[0]`, `Map.GetDistrict`, `Map.GetLanguage()[0]`) rather than the leader's shared-memory record, with the docstring recording that GW can rebuild the party identity during a reconnect while every surviving client stays in one instance. Publishable accounts are then filtered by slot activity, isolation from the viewer, the map signature, and membership in the live party roster resolved by AgentID or LoginNumber; party position is resolved by LoginNumber first, AgentID second, and only then falls back to the stamped `PartyPosition`. All helpers exist (`Map.GetRegion`/`GetDistrict`/`GetLanguage`, `AgentData.LoginNumber`, `AllAccounts._is_slot_active`, `_is_slot_isolated_from_viewer`).
- Notes: the fix intentionally couples Follow's identity to the local client's map rather than the leader's published record, which is correct for the reconnect case but means a lagging shared-memory publish no longer affects formation validity. The code uses two private `AllAccounts` helpers rather than the public slot property; acceptable but worth aligning when that module is next touched.
- Independent checks: exact head fetched and diffed; signature construction, roster lookups, position fallbacks and the combat gate read; every API and struct field verified; Pyright at head 0 errors. No test file; no live-client test or GitHub review.
- Unresolved: whether the reconnect scenario that motivated the fix reproduces only with a republished party identity, and whether Follow should also tolerate a leader whose local map lags.

### [#125 - 55 and 330](https://github.com/apoguita/Py4GW_Reforged/pull/125)

- Review verdict: REQUEST CHANGES. Release placement: split before review. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `97710a32656365b15b2b4c8ffd5fb963452fc045`; changes: 7 files, +2170/-53.
- Files: `Assets/Textures/Module_Icons/Sadi's_Benediction.png`, `Py4GWCoreLib/Builds/Monk/Mo_D/Monk55Farmer.py`, `Py4GWCoreLib/Builds/Ritualist/Rt_Mo/330RIT.py`, `Py4GWCoreLib/enums_src/Model_enums.py`, `Widgets/Automation/Bots/Farmers/Weapons/Green_Unique/Scythe/Asterius Scythe BT.py`, `Widgets/Automation/Bots/Farmers/Weapons/Green_Unique/Staff/Sadi's Benediction BT.py`, `Widgets/Automation/Bots/Levelers/KillroyStoneskin/Kilroy_punchout_BT.py`.
- Classification: several independent feature deliveries bundled in one PR: a new Ritualist/Monk farmer build, a revision of the Monk 55 farmer, two new green-weapon farm bots, a leveler service change, model-enum additions and an icon.
- Verified: `330RIT.py` is a documented build whose header explains the Protective Spirit / Vengeful Was Khanhei pairing, the 330-to-360 HP decision and the shrinking margin; that reasoning is good documentation. `Monk55Farmer.py` receives many targeted revisions. Both new weapon bots carry `_suppress_heroai_settings_spam()`, which mutes HeroAI's settings log and stashes its wrapper on a function attribute (`_asterius_spam_filter`), and their own comments state that the real fix belongs to the shared HeroAI init latch. `Kilroy_punchout_BT.py` changes every `StandUpService` path from `SUCCESS` to `RUNNING`, so the node never completes. `ModelID` gains `Stalker_s_Ration`/`Bird_s_Eye_Compass`, the same two values #150 and #214 add as `Stalkers_Ration`/`Birds_Eye_Compass`.
- Required direction: split this into the Ritualist build, the Monk farmer revision and the weapon-farm bots, because they deliver unrelated outcomes and cannot be reviewed, reverted or released independently. Remove the per-widget log patching and fix the HeroAI settings init latch at its owner, because a widget that wraps another owner's function is exactly the hole-based attachment the guide forbids and its own comment admits the workaround. Agree one spelling for the two model members with #150/#214 before any of them merges, because two names for one value hide the duplication. Confirm the `StandUpService` change is intended to make the node permanently running, because if it is a sequence child the tree can never leave it. The Asterius bot also reports one new Pyright diagnostic for the attribute assignment used by the patch.
- Independent checks: exact head fetched and diffed; both builds, both new bots, the leveler change and the enum additions inspected; Pyright at head: `Monk55Farmer`, `330RIT`, `Model_enums` and Sadi's bot 0, Asterius bot 1. No test file exists; no live-client test or GitHub review.
- Unresolved: whether 360 HP remains the right target on a live bar, and whether the weapon bots' capture routes are correct; asset contents not inspected.

### [#124 - Fix Diessa Lowlands bridge and obstacle routing](https://github.com/apoguita/Py4GW_Reforged/pull/124)

- Review verdict: REQUEST CHANGES. Release placement: after the path-key ownership decision below, and not exposed to BottingTree until it supports the keys. GitHub state: open; mergeability: reported conflicting.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `86b3b937763db23c5863693e1c4e7f2361b103dd`; changes: 3 files, +334/-9.
- Files: `Examples and tests/tests/test_diessa_lowlands_route.py`, `Sources/aC_Scripts/PyQuishAI_maps/Proph_Ascalon/DiessaLowlands.py`, `Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py`.
- Classification: semantic route-data restructure plus two new path-execution keywords in the shared widget; this commit is the root of the #202/#203 stacks.
- Verified: `_handle_keyword` gains `continuous_path` (FollowAutoPath) and `literal_path` (FollowPath), the aggro variant gains both, and `_get_first_path_coord` accepts both; the Diessa route uses them. Four removed waypoints are not re-added: `-1545,-8141`, `-3883,-1086`, `-1554,-8099`, `-11822,-11488`. Diessa Lowlands is a BottingTree map (`PyQuishAI_BT.py:206`) and BT has no branch for either key, so the route build raises `ValueError('Unsupported PyQuish map keyword: continuous_path')` there; `Simple_Vanquish` executes the keys. Pyright: route 0 errors, `Simple_Vanquish.py` 101 errors equal to the base baseline, and the new test file reports one `reportArgumentType` diagnostic (`ast.AST` body invariance) that this PR introduces.
- Dependency resolution: #202 and #203 carry this diff byte-identically (Diessa blob `93ab8f9d`, widget blob `23614622`, test `1b581b75`), so those PRs are stacks on this one and inherit its parity gap. #195 independently adds `literal_path` to the same function, so the key has two owners.
- Required direction: choose one owner for `continuous_path`/`literal_path` and remove the duplicate addition from whichever PR is not the owner, because both PRs edit the same `_handle_keyword` lines and the second merge will conflict on an identical feature. Add the keys to the BottingTree consumer or keep Diessa Lowlands out of the BT path, because the map is already registered there. State which of the four removed waypoints the new detours replace, because silent removals change the traversed line. Fix or justify the new test diagnostic.
- Independent checks: exact head fetched and diffed; base consumers, BT table and coordinate preservation by value inspected; Pyright per changed file at head in a detached worktree. The author's focused test was not rerun; no live-client test or GitHub review.
- Unresolved: bridge clearance and detour collision behavior at runtime.

### [#123 - feat: improve BottingTree automation, multibox services and EOTN tooling](https://github.com/apoguita/Py4GW_Reforged/pull/123)

- Review verdict: REQUEST CHANGES. Release placement: split into coherent PRs; no single verdict can accept 85 files. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `b851539d47d7796ac2cad32764e05541228d8b67`; changes: 85 files, +41414/-8302.
- Files: 85 changed paths across `Widgets/Automation` (21), `Py4GWCoreLib/Builds` (14), `Py4GWCoreLib/botting_tree_src` (7), `Py4GWCoreLib/botting_src` (6), `Py4GWCoreLib/HeroAI` (5), `Py4GWCoreLib/py4gwcorelib_src` (5), `Py4GWCoreLib/routines_src` (4), `Py4GWCoreLib/FrameTree` (4), `Assets/Textures` (4), `Sources/Sky` (3), `Sources/icefox` (2), plus `Py4GWCoreLib/Item.py`, `Player.py`, `BottingTree.py`, `enums_src/Multiboxing_enums.py`, `README.txt`, `MIGRATION_MESSAGING_MERCHANTRULES.md` and `AUDIT_MIGRATION_WORK_APO.md`.
- Classification: mixed scope spanning several independent outcomes.
- Verified: the diff contains at least five separable deliveries — (a) party-recovery centralization in `botting_tree_src` plus `Shards Of Orr BT`, which is the only outcome the new `README.txt` documents; (b) a MerchantRules/Messaging migration (`MerchantRules.py` +7289, `Messaging.py` +171, `Sources/icefox/MerchantRules/catalog.py`, migration and audit documents); (c) new core modules `proactive_move.py` and `shards_flame_hold.py` plus `FrameTree`, `Item.py`, `Player.py` and `BottingTree.py` changes; (d) a Sky dungeon-party package (`DungeonParty.py`, `Support.py`, `ConsumableRestockUI.py`) with four new builds; (e) new farm and dungeon bots (`VAETTIR DRIFT.py` +1766, gemstone farmer, Underworld, Arachnis Haunt, Tunnels of the Forsaken, Vloxen) and four textures. Pyright at head does not worsen: `MerchantRules` 511 versus a 550 base, `Messaging` 16 equal to base, and the new modules 0 — although 511 diagnostics in a changed 7,289-line file is itself a maintainability fact. The comparison also cannot be applied as one patch: `git apply` rejects it with a malformed diff header, matching the earlier record that this PR was retrieved as 85 separate file patches.
- Required direction: split the PR into at least the five deliveries above, each with its own diff, verification and review, because a single comparison of 41k lines cannot show which changes implement which requested behavior, and it cannot be reverted or released piecewise. Record the MerchantRules/Messaging migration as its own migration with the report the description already references. Keep the recovery patch first, since it is the one the README documents and it touches shared BottingTree code.
- Independent checks: exact head fetched; changed-file categories, top files, new files and core-module changes enumerated; migration and README documents read; patch application attempted (failed structurally); Pyright sampled across the largest changed modules and new files with base comparisons. No live-client test or GitHub review.
- Unresolved: whether any single delivery is individually acceptable cannot be answered until it is separated and reviewed on its own; texture contents were not inspected.

### [#122 - feat(heroai): expand consumable auto-upkeep, summoning, and party controls](https://github.com/apoguita/Py4GW_Reforged/pull/122)

- Review verdict: BLOCK. Release placement: not mergeable in its current form. GitHub state: open; mergeability: reported clean.
- Base: `8aac6065c4d54888845c2c884f3c3e2da26901d9`; head: `7291ff636aea667af61d4b2db2cdffd499a6a48a`; changes: 8 files, +2482/-136.
- Files: `Assets/Textures/Item Models/26501-Scroll_Of_Resurrection.png`, `Assets/Textures/Item Models/29424-Lunar_Fortune.png`, `Assets/Textures/Item Models/30847-Igneous_Summoning_Stone.png`, `Assets/Textures/Item Models/321795-Heroes_Trifecta.png`, `Assets/Textures/Item Models/321796-Empowering_Feast.png`, `Assets/Textures/Item Models/Ascalonian_War_Horn.png`, `Assets/Textures/Item Models/Ascalonian_War_Horn_Unique.png`, `Py4GWCoreLib/HeroAI/ui.py`.
- Classification: large UI and behavior expansion of the HeroAI options surface, with binary assets.
- Verified blockers: the changed module does not compile — `python -m py_compile` fails at line 3969 with `SyntaxError: expected 'except' or 'finally' block`, so HeroAI's UI cannot be imported with this change. Worse is queued behind it: `NativeSettings("HeroAI/ConsumableAuto.ini", ...)` and `NativeSettings(..., "global")` are called at module scope (lines 1842, 1850) without any import of that name, and `time` is used in six places without an import, so fixing the syntax yields NameError at module import and in the lock helpers respectively. Pyright reports 25 diagnostics against a four-diagnostic base, including those undefined names, eight `cannot access "value" for class "int"`, two tuple-return mismatches and two possibly-unbound variables.
- Second finding: the new cross-process locks (`_try_acquire_special_lock`, `_try_acquire_conset_lock`, `_try_acquire_party_morale_lock`) write `.lock` files with `os.open(O_CREAT|O_EXCL|O_WRONLY)` plus `os.makedirs` under `<projects>/Settings/Global/HeroAI`. They bypass the concrete `Settings` owner even though the folder is inside the jail, and they duplicate the shared-memory whiteboard-lock API (`GlobalCache/WhiteboardLocks.py`) that already owns cross-account coordination. Use that owner or present the file-lock mechanism as a separately approved infrastructure change.
- Third finding: six new and one modified binary texture assets are included; their contents were not inspected, as with #214.
- Required direction: repair the syntax error and the missing `NativeSettings`/`time` imports, then re-run compile and changed-file Pyright, because the file is currently unimportable. Route cross-account coordination through the whiteboard-lock owner, because a second lock mechanism divides ownership of who may cast what. Provide the exact texture files for review or state their provenance. Finally, split the delivery — consumable auto-upkeep, summoning presets, party-morale and Conset coordination plus a 2,400-line UI rewrite are several independent outcomes in one PR.
- Independent checks: exact head fetched and diffed; `py_compile` executed against the head file; imports and module-scope usage inspected; Pyright head-versus-base delta extracted; lock paths and helpers read; asset list inspected by name only. No live-client test or GitHub review.
- Unresolved: whether the consumable/summoning behavior works at all beyond the compile failure, and what the texture contents are.

### [#121 - Add Invoke Lightning air build behavior](https://github.com/apoguita/Py4GW_Reforged/pull/121)

- Review verdict: APPROVE for the submitted source change. Release placement: after #134 (its overcast reader). GitHub state: open; mergeability: reported clean.
- Base: `a5fd2e54d504605200a752b1bc991d618ed33c41`; head: `c5339f982e55d89cf3701dd55d0201213b1da66e`; changes: 6 files, +286/-0.
- Files: `Py4GWCoreLib/BuildMgr.py`, `Py4GWCoreLib/Builds/Elementalist/E_Any/Invoke Lightning.py`, `Py4GWCoreLib/HeroAI/combat.py`, `Py4GWCoreLib/HeroAI/custom_skill_src/elementalist.py`, `Py4GWCoreLib/HeroAI/custom_skill_src/skill_types.py`, `Py4GWCoreLib/routines_src/Checks.py`.
- Classification: new build controller plus a shared cast-condition capability used by both engines.
- Verified: `Invoke_Lightning_Air` maintains Air Attunement and either Elemental Lord, pairs Intensity with a ready Invoke Lightning or Lightning Strike when it can afford both, and never acquires an AoE target on its own — it reads `Party.GetPartyTarget` (frame-cached in `Py4GWCoreLib/Party.py`) and the player target and only uses an established enemy. `CastConditions` gains `MaxOvercastFraction`/`MaxOvercastBypassSkillID`, enforced in `BuildMgr` and in `HeroAI/combat.py` through the new `Routines.Checks.Skills.IsProjectedOvercastAllowed`, which reads the native overcast via `Agent.GetOvercast` (#134). Air skills get engagement-scoped target rules: Arc Lightning requires overcast above zero, Shell Shock requires the target to lack Cracked Armor, Lightning Javelin uses the preferred target. The affordability helper multiplies the fractional `Agent.GetEnergy` by `GetMaxEnergy`, the same convention used by existing scripts.
- Dependency resolution: the description names #10 and #134. PR #10 returns 404 and cannot be resolved, so the statement is stale; #134 is the operative dependency and is approved in batch seventeen. The single `Checks.py` diagnostic at head also exists in this branch's own base (`a5fd2e54`, line 1368) and is not introduced here.
- Independent checks: exact head fetched and diffed; the build, both gate sites and the new check read; `Party.GetPartyTarget`, `cracked_armor` and the energy convention verified against existing sources; Pyright at head: `BuildMgr` 1 and `combat` 17 equal to base, new build/elementalist/skill_types 0, `Checks.py` 1 attributed to the branch base. No test file; no live-client test or GitHub review.
- Unresolved: whether the projected-overcast 50% gate is the right threshold in live play, and whether established-target-only AoE matches intended air-bar behavior.

### [#115 - Expand OutpostRunner routes and improve OutpostFighter recovery](https://github.com/apoguita/Py4GW_Reforged/pull/115)

- Review verdict: REQUEST CHANGES. Release placement: after the resume-progress ownership decision and cleanup. GitHub state: open; mergeability: reported clean.
- Base: `fd8da45570ec79f1fdaa413063dabbdbe7ab5c76`; head: `c28143b3ca99c929fcf22383917a7f3d3b24f278`; changes: 42 files, +4589/-99.
- Files: `Examples and tests/tests/local_bots/test_outpost_fighter_wipe_recovery.py`, `Examples and tests/tests/local_bots/test_outpost_runner_route_mechanics.py`, `Py4GWCoreLib/botting_src/subclases_src/DIALOGS_src.py`, `Py4GWCoreLib/botting_src/subclases_src/MOVE_src.py`, `Sources/aC_Scripts/OutpostRunner/maps/**` (route data), `Sources/aC_Scripts/OutpostRunner/route_mechanics.py`, `Widgets/Automation/Bots/Runners/OutpostFighter.py`, `Widgets/Automation/Bots/Runners/OutpostRunnerV2.py`.
- Classification: route-mechanics owner addition plus route data and widget integration; the diff applies cleanly to the snapshot checkout.
- Verified: `route_mechanics.py` owns the new `steps` grammar (`segment_steps`), `extended_portal_path` with its 450-unit continuation, `register_outpost_departure`, `register_botting_segment` and `requires_physical_outpost_departure`, and both runners delegate to it; 40 route files add steps-based segments with blessing and Junundu steps; `MOVE_src` gains `resume_key` and a `progress_callback` passthrough; focused mechanics and recovery tests are included.
- Findings and required direction: `MOVE_src` implements its own restart-safe store (`self._config._restart_safe_path_progress`) for `resume_key`, while #168 already implements the same concept as `bt_move_path_progress:*` blackboard records for the behavior-tree layer. Choose one owner per layer and state the split, because two progress stores make resume behavior depend on which layer ran the path. Both runners call `importlib.reload(_route_mechanics)` at import time, which re-executes a shared module and rebinds its functions; explain and remove it unless a load-order requirement is proven, because a reload can double-run module initialization. `OutpostFighter` also drops `'Return to outpost on defeat'` from its enabled-widget policy and gains one new Pyright diagnostic (`OnPartyWipeCallback(None)` in the known callback-None class); state the intended recovery ownership and clean the diagnostic.
- Independent checks: exact head fetched and diffed; patch application verified against the snapshot checkout; route mechanics, both runner integrations, the move-layer store and the removal of the enabled widget read; tests and routes inspected at structure level; Pyright at head: `OutpostRunnerV2` 7 equal to base, `route_mechanics`/`MOVE_src` 0, `OutpostFighter` 1 new. No live-client test or GitHub review.
- Unresolved: whether the physical-departure rule and portal extension reproduce the captured portals reliably, and whether the FSM-level resume store and the BT-level records agree after a combined pause.

### [#91 - Target Ancestors' Rage by adjacent enemy density](https://github.com/apoguita/Py4GW_Reforged/pull/91)

- Review verdict: REQUEST CHANGES. Release placement: after a rebase onto the snapshot base; it cannot be merged or re-reviewed as submitted. GitHub state: open; mergeability: reported conflicting.
- Base: `ea053d1abd01906ce31e1a2829ed84e5571db65b`; head: `38e209589719df64767d1cee0c0e3c8da7853ba3`; changes: 8 files, +123/-20.
- Files: `Py4GWCoreLib/Agent.py`, `Py4GWCoreLib/BuildMgr.py`, `Py4GWCoreLib/HeroAI/combat.py`, `Py4GWCoreLib/HeroAI/custom_skill_src/ritualist.py`, `Py4GWCoreLib/HeroAI/targeting.py`, `Py4GWCoreLib/HeroAI/types.py`, `Py4GWCoreLib/SkillManager.py`, `Py4GWCoreLib/routines_src/Targeting.py`.
- Classification: skill targeting policy for Ancestors' Rage plus the shared density helper both engines call.
- Verified: the branch base is an ancestor of the snapshot base, and applying its own diff to the current checkout fails at `BuildMgr.py:419`, `HeroAI/combat.py:10` and `HeroAI/targeting.py:109`, so the recorded conflict is confirmed. The submitted content itself is clean where it stands: `routines_src/Targeting.py` gains a density-scored helper and `HeroAI/targeting.py` wraps it for the modern engine, with a new `Skilltarget` member and a Ritualist skill definition re-pointed at it.
- Required direction: rebase onto `8aac6065c4d54888845c2c884f3c3e2da26901d9`, re-apply, and re-review the resulting comparison, because the current patch neither applies nor represents the code that would merge. State the density threshold and tie-break policy in the description, because that is the behavior this PR introduces.
- Independent checks: base ancestry checked, patch application attempted with `git apply --check` against the snapshot checkout, and per-file Pyright run at the branch head (`BuildMgr` 1 equal to base, `combat` 15 versus a 17 base, `targeting` 0 versus a 1 base). No test file; no live-client test or GitHub review.
- Unresolved: the intended density threshold and whether it matches Ancestors' Rage's adjacent-only rule in live combat.

### [#60 - Improve combat-event compatibility and interrupt timing](https://github.com/apoguita/Py4GW_Reforged/pull/60)

- Review verdict: REQUEST CHANGES. Release placement: after a rebase onto the current layout and removal of the unused support module. GitHub state: open; mergeability: reported conflicting.
- Base: `11a80d289e0574de0f48277f92ab112da9334922`; head: `4f3c3873e485fb7d4d585e558935e3b6e2e39136`; changes: 4 files, +650/-50.
- Files: `HeroAI/interrupt.py`, `Py4GWCoreLib/Builds/Skills/ReforgedSupport.py`, `Py4GWCoreLib/CombatEventQueue_src/helpers.py`, `Py4GWCoreLib/CombatEvents.py`.
- Classification: event-backend normalization plus interrupt timing changes, bundled with a new support module.
- Verified: `CombatEvents` gains `_NormalizedAgentEvent`, a native event-type map and `_AgentEventsQueueAdapter` with the standard queue surface, plus `OnSkillActivatedTimed`, `OnSkillStopped` and `OnCastTime`; `helpers.py` dispatches `SKILL_ACTIVATE_PACKET`, `CASTTIME` and `SKILL_STOPPED` while keeping a pending-cast fallback for older bindings, and damage/healing now prefer the packet's skill id. Those changes are coherent and guarded.
- Findings and required direction: the PR modifies `HeroAI/interrupt.py` at the repository root, a path that existed at its base but no longer exists — the interrupt owner is `Py4GWCoreLib/HeroAI/interrupt.py` — so the patch cannot apply and the interrupt-side changes must be ported onto the current owner. It also adds `Py4GWCoreLib/Builds/Skills/ReforgedSupport.py`, a cast-tracking bridge with its own `_CASTS`/`_OUTCOMES`/`_DAMAGE` state and polling fallbacks, which has zero references anywhere in the PR's tree; an unreferenced parallel event layer is dead code and, if it is meant to be the interrupt fix, it must extend `CombatEvents` rather than shadow it. Rebase, delete or merge the support module, and keep the event-queue work.
- Independent checks: exact head fetched and diffed; branch base and current layout compared; patch application attempted against the snapshot checkout; the new adapter, callbacks and dispatcher branches read; `ReforgedSupport` reference search run across the PR tree. No test file; no live-client test or GitHub review.
- Unresolved: whether the packet-first activation events reduce interrupt latency in live play or only duplicate the existing ones.

## Batch log

- Batch 5 (resumed in a new session after the desktop-executor blocker): #207, #211, #194, #155 and #174 reviewed and recorded. Heads re-verified against GitHub and matched the recorded values: #207 `e6157944`, #211 `96329fa8`, #194 `2322e268`, #155 `a9c3cbf5`, #174 `92daa3f0`. Dependencies #148 (`f97bca9b`) and #192 (`57ef198d`) inspected in source. Pyright reported 0 errors and 0 warnings on every changed file at head. Verdicts are source-review approvals with explicit merge placement; they are not GitHub approvals and prove nothing about live behavior.
- Merge order established by this batch: #148 (canonical `TakeBlessing` owner) -> #192 (Simple Vanquish/BT adapter) -> routes #207, #211, #155 (faction records) and #174, #194 (captured records). No live-client test, GitHub review, merge, or commit was performed.
- Batch 6: #210, #208, #206, #203 and #202 reviewed and recorded from the same snapshot base. Heads re-verified and matched the ledger exactly: #210 `34a1e7ea`, #208 `51142030`, #206 `a57a9276`, #203 `234ce9d5`, #202 `711d4282`. Dependencies #124 (`86b3b937`) and #195 (`1c209c87`) inspected in source; #192 (`57ef198d`) and its `BottingTree.Create` extension inspected for the adapter contracts.
- Outcome: one approval (#210, no BottingTree exposure) and four request-changes driven by consumer parity, a duplicate adapter (#206) and single-map policy inside the shared widget (#208). Pyright run per changed file at each head in detached worktrees, reported as a delta against the 101-diagnostic `Simple_Vanquish.py` baseline. No live-client test, GitHub review, merge or commit was performed.

- Batch 7: #124, #195, #198, #197 and #196 reviewed and recorded. Heads re-verified against GitHub and matched the ledger: #124 `86b3b937`, #195 `1c209c87`, #198 `330e509a`, #197 `db4a1641`, #196 `b0f2b2c9`. Blob comparison proved that #196 and #197 ship identical copies of the shared widget and test (`e5add29c`, `15b30ad8`) that diverge from #195's owner files (`5e7ab457`, `f36b8cec`), and that #124 partially duplicates #195's `literal_path` work.
- Outcome: one approval (#198, no BottingTree exposure) and four request-changes driven by duplicate shared-control copies, path-key double ownership and BottingTree parity. Pyright run per changed file at each head in detached worktrees, reported as a delta against the 101-diagnostic baseline. No live-client test, GitHub review, merge or commit was performed.

- Batch 8: #190, #189, #188, #187 and #186 reviewed and recorded. Heads re-verified against GitHub and matched the ledger: #190 `c972d0bc`, #189 `896c6233`, #188 `a481efc1`, #187 `a9144919`, #186 `ede7f70d`. All five are single-file Elona route-data conversions from legacy bless coordinates to captured mappings, plus detours in #190, a corridor replacement in #189 and a `map_entry` transit in #188.
- Outcome: five approvals for the submitted route data, all placed after #148 and #192; #188 additionally requires BottingTree `map_entry` parity or exclusion and one description clarification about a replaced blessing anchor. Value-level coordinate comparison found no lost path waypoint in any PR. Pyright 0 errors and 0 warnings on every changed file. No live-client test, GitHub review, merge or commit was performed.

- Batch 9: #176, #177, #178, #179 and #180 reviewed and recorded as one ordered stack. Heads re-verified and matched the ledger: #176 `37e32225`, #177 `f16bc496`, #178 `1da6e6f2`, #179 `1a675b21`, #180 `bda80bc7`; root #173 (`45000419`) inspected as the stack base and left pending its own verdict. The cumulative base-to-head diffs are not the review surface; each PR's own contribution was isolated with pairwise diffs (`45000419..37e32225`, `37e32225..f16bc496`, `f16bc496..1da6e6f2`, `1da6e6f2..1a675b21`, `1a675b21..bda80bc7`).
- Outcome: five approvals for the submitted leaf route data, released in series order after #173. #178 extracts #177's route into a file-local flow helper; #179 replaces a `#en cours` placeholder. All route constants verified defined; all framework calls verified against their owning source. Pyright reported as cumulative deltas against the 510-diagnostic widget baseline, all in the existing `bot.*` attribute class. No live-client test, GitHub review, merge or commit was performed.

- Batch 10: #185, #184, #183, #182 and #181 reviewed and recorded. Heads re-verified and matched the ledger: #185 `943d98ad`, #184 `d326d7b6`, #183 `9582b245`, #182 `4fb68a8f`, #181 `069964f6`. #181/#182 convert to `norn_blessing`, #183/#184 to `asuran_blessing`; #185 wraps the existing route in a `faction_blessing`. #182 and #210 add the identical `THIRD_PARTY_NOTICES.md` blob `0c9018bc`; #182 also defines an unused effect-id constant.
- Outcome: three approvals (#181, #182, #185) placed after #148/#192, and two request-changes (#183, #184) blocked on `face_hold`/`literal_path` consumer parity for maps that are in the BottingTree table. Normalized coordinate comparisons used for the three restructures. Pyright 0 errors and 0 warnings on every changed file. No live-client test, GitHub review, merge or commit was performed.

- Batch 11: #136, #135, #129, #128 and #127 reviewed and recorded. Heads re-verified and matched the ledger: #136 `a0b29f22`, #135 `3456752d`, #129 `9e116fb9`, #128 `33598997`, #127 `febcac78`. #136 is mixed scope: a new library `cartography.py` behavior-tree node, a shared-widget integration, a route update and a test; its widget adds the fourth copy of `literal_path` and a hardcoded `explorable_id == 486` transit branch. #135 adds a fifth copy of the same block. #129/#128/#127 are pure flat-list coordinate additions with no keywords.
- Outcome: three approvals (#129, #128, #127 — all BT-safe, dependency-free) and two request-changes (#136, #135) driven by the `literal_path` ownership collision, the map-id branch in the shared widget and non-clean test Pyright. No live-client test, GitHub review, merge or commit was performed.
- Record incident (self-inflicted, corrected): the batch-11 replacement script rewrote whole ledger sections regardless of their current verdict. #129, #128 and #127 already held `APPROVE for the reviewed source change` verdicts from the prior session; their evidence blocks were replaced by this session's independent verdicts. The dispositions agree (approve either way), and the three entries are now marked as re-reviews, but the prior session's evidence text for those three is not recoverable in this session and should be merged back if that record is available. Corrected counts are fifty-two verdicts and forty-three pending. Future batches must read the current verdict and only replace `PENDING` entries, appending rather than overwriting any recorded verdict.

- Batch 12: #167, #168, #169, #170 and #171 reviewed and recorded. Heads re-verified and matched the ledger: #167 `cb756acc`, #168 `b5d6389e`, #169 `5fb65074`, #170 `0baf81be`, #171 `38a9a412`. All five are library or host-script changes with focused tests, not route data, so owner, lifecycle and cleanup paths were read end to end.
- Outcome: four approvals (#167, #168, #169, #171) and one request-changes (#170) whose detached-command registry can fail or hang process-wide because expired entries are never removed and inbox slot indexes recycle. #169's approval carries a required cleanup for the dead `_loot_throttle_check`. Changed-file Pyright was clean for the whole batch except the pre-existing single `planner.py` diagnostic. No live-client test, GitHub review, merge or commit was performed.

- Batch 13: #164, #163, #162, #161 and #160 reviewed and recorded. Heads re-verified and matched the ledger: #164 `84150e38`, #163 `a5c19144`, #162 `e884c014`, #161 `1fd12572`, #160 `0a8f3520`. All are HeroAI skill-gating changes with focused tests (except #162, which only registers skill data). #156 was inspected as an overlap: its `custom_skill.py` blob is identical to #161's, so the Soul Ignition capacity bump exists in both.
- Outcome: five approvals; #161 carries two cleanups (sequence with #156, remove the duplicated 3446 literal) and #163 a shared-contract note about publishing hero engagement as party aggro. Pyright: `combat.py` reports the same 17 diagnostics at base and at every head, every other changed file and all four new tests report zero. No live-client test, GitHub review, merge or commit was performed.

- Batch 14: #148, #151, #152, #153 and #154 reviewed and recorded. Heads re-verified and matched the ledger: #148 `f97bca9b`, #151 `e8e45e5d`, #152 `2c0685c5`, #153 `2c7bab99`, #154 `acfa6707`. #148 is the canonical blessing owner; its new signature and guard clauses were pinned against the call shapes of #192 and of #153/#154.
- Outcome: three approvals (#148, #151, #152) and two request-changes (#153, #154) for copying `PrepareForFarm` callback wiring into route widgets, an inconsistent multibox-versus-single-account mode, and a duplicated run-in-a-custom-state blessing helper that #192 already owns. Pyright was reported as a delta against each file's base: #148's single `wrappers.py` diagnostic is pre-existing, and #153/#154's new `verify_effect` diagnostic is the #148 dependency surfacing. No live-client test, GitHub review, merge or commit was performed.

- Batch 15: #142, #143, #144, #145 and #147 reviewed and recorded. Heads re-verified and matched the ledger: #142 `d67649d9`, #143 `b175a494`, #144 `1365fb65`, #145 `bddda499`, #147 `e872186e`. All are shared-owner or widget changes with focused tests, so the gate ladders, pause lifecycles and policy hooks were read in full rather than by diff shape.
- Outcome: five approvals. #145 carries a cross-PR coordination note (its StopMovement approach contradicts #167's move-to-current cancellation), #144 a coupling note on the per-tick pause serial, and #142 a behavior note that the shared Monk definition changes Strength of Honor targeting for every build. Pyright was clean for the whole batch: no changed file exceeded its base diagnostic count and several improved. No live-client test, GitHub review, merge or commit was performed.

- Batch 16: #137, #138, #139, #140 and #141 reviewed and recorded. Heads re-verified and matched the ledger: #137 `ea50658d`, #138 `bf76aaf4`, #139 `8f5daa69`, #140 `ee14c160`, #141 `268878be`. #141 was reviewed against the reverted version (`53a04740^`), #137 against the #168 dependency its code calls, and #139 against every caller of the predicate it redefines.
- Outcome: two approvals (#138, #140) and three request-changes — #137 (custom file-backed capture persistence, an undeclared #168 dependency, 25 new diagnostics and a self-declared unmergeable draft), #139 (a shared classification predicate changed for hex and enchantment callers) and #141 (a permanently-false golem identification check plus a missing rollback rationale). Pyright reported per changed file against each file's base; both approvals and all tests were clean. No live-client test, GitHub review, merge or commit was performed.

- Batch 17: #122, #125, #126, #133 and #134 reviewed and recorded. Heads re-verified and matched the ledger: #122 `7291ff63`, #125 `97710a32`, #126 `86f0e0ae`, #133 `2a0fd6e7`, #134 `96a150ed`. #122 was additionally compiled with `python -m py_compile`, which failed.
- Outcome: three approvals (#126, #133, #134), one request-changes (#125) and the review's first hard block (#122) because its changed module cannot compile and carries two more undefined-name defects behind that. Pyright was reported as a head-versus-base delta per file; #122's 25-vs-4 delta and #125's single new diagnostic are recorded in the entries. No live-client test, GitHub review, merge or commit was performed.

- Batch 18: #121, #91, #60, #115 and #123 reviewed and recorded. Heads re-verified and matched the ledger: #121 `c5339f98`, #91 `38e20958`, #60 `4f3c3873`, #115 `c28143b3`, #123 `b851539d`. Patch application was re-tested for #91, #60 and #123 against the snapshot checkout; #121's `#10` dependency was resolved against GitHub and does not exist.
- Outcome: one approval (#121, after #134), and four request-changes — #91 and #60 are stale against the current layout and cannot apply, #115 adds a second resume-progress store next to #168's and reloads a shared module at import, and #123 is a five-delivery mega-PR that cannot be applied as one patch or reviewed as one purpose. Pyright was reported as a head-versus-base delta per file. No live-client test, GitHub review, merge or commit was performed.

- Batch 19: #173, #175, #192, #204 and #205 reviewed and recorded. Heads re-verified and matched the ledger: #173 `45000419`, #175 `e5ed8b7d`, #192 `57ef198d`, #204 `7421b344`, #205 `3964b34c`. #192's adapters and owner extension were re-read in full against the consumers recorded in earlier batches; #205's key census was rerun with both quote styles after a single-style census gave a false zero.
- Outcome: five approvals. #192 carries its recorded map-entry parity limitation, #205 a dependency misattribution (face_hold belongs to #195, not #186), #175 a duplicated tier predicate in the legacy shim, and #173 the pre-existing widget diagnostic class on its new lines. Pyright was reported per changed file against each file's base; #192's adapters, #204 and #205 were clean. No live-client test, GitHub review, merge or commit was performed.

- Batch 20: #216, #218 and #219 reviewed and recorded, completing the ledger. Heads verified: #216 `c7acc92f`, #218 `09cc0217`, #219 `e299c877`. The `SageLands.py` repair in #216 was verified by compiling the snapshot version and observing the tuple-call warning.
- Outcome: two approvals (#218, #219) and one request-changes (#216) for forbidden file-backed diagnostics admitted through `.gitignore`, an unsplit 2,800-line extension, and 12 new widget diagnostics. With this batch every one of the ninety-five open PRs in the snapshot has a recorded source-review verdict, a classification, its evidence, release placement, the checks performed or omitted, and its unresolved facts. No merge, commit or GitHub review was performed, and no live-client test was imposed at any point.

- Re-verification pass (prior-session verdicts): #220, #213, #214, #212, #209, #201, #200, #199, #193, #191, #166, #165, #159, #158, #157, #156 and #150 were re-checked against their recorded heads. All heads matched GitHub; every diff claim was re-read; per-file Pyright was re-run against the snapshot base with no new diagnostics. Feasibility outcomes are recorded per entry.

## Continuation

Review in groups by owner: route data and Simple Vanquish; Skills Unlocker; item/loot; HeroAI and build skills; BottingTree/movement; widgets and diagnostics; native/bridge; large mixed PRs. For every PR, inspect the base-to-head diff, relevant owner and prior discussion; preserve exact head SHA, decision, evidence, and unresolved facts. Recheck PR heads before final recommendations. Do not publish reviews, merge, or commit.
