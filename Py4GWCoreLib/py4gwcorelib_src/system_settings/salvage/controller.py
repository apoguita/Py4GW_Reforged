"""Runtime owner for automatic Salvage.

Classification is delegated to the shared matcher. Execution uses current ``Py4GWCoreLib``
inventory/dialog primitives and a feature-owned timer; no legacy ItemHandling salvage policy is read.
"""

import time
from typing import Any, Optional

from Py4GWCoreLib import ThrottledTimer
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import (
    scan_salvage_kits,
    select_salvage_kit,
)
from Py4GWCoreLib.enums_src.Item_enums import INVENTORY_BAGS

from ..inventory import store as inventory_store
from ..inventory.model import BAGS
from ..inventory.monitor import InventoryMonitor
from ..item_runtime import StableMapGate, get_item_operation_lease
from ..loot_filter_factory.matcher import matching_filters
from ..loot_filter_factory.model import Filter, UpgradeCriterion, canonical_upgrade_name
from . import store
from .model import SalvageSettings


_CALLBACK = "SystemSettingsSalvage"
_DIAGNOSTIC_DRAW_CALLBACK = "SystemSettingsSalvageDiagnosticTargets"
_SALVAGE_INTERVAL_MS = 15_000
_SALVAGE_TIMEOUT_SECONDS = 5.0
_DEBUG_LOGGING = False
_UPGRADE_ACTION_PREFIX = "upgrade_slot:"
_OPERATION_OWNER = "system_settings_salvage"


def _log(message: str, error: bool = False) -> None:
    if not error and not _DEBUG_LOGGING:
        return
    try:
        import PySystem

        level = PySystem.Console.MessageType.Error if error else PySystem.Console.MessageType.Info
        PySystem.Console.Log("System Settings / Salvage", message, level)
    except Exception:
        pass


def _diagnostic_log(message: str, error: bool = False) -> None:
    """Emit an explicit diagnostic dump entry regardless of normal debug logging state."""
    try:
        import PySystem

        level = PySystem.Console.MessageType.Error if error else PySystem.Console.MessageType.Info
        PySystem.Console.Log("System Settings / Salvage", message, level)
    except Exception:
        pass


class SalvageController:
    def __init__(self) -> None:
        self._settings = store.load()
        self._monitor = InventoryMonitor()
        self._timer = ThrottledTimer(_SALVAGE_INTERVAL_MS)
        self._map_gate = StableMapGate()
        self._last_map_id = 0
        self._outpost_pass_pending = False
        self._active_item_id = 0
        self._active_node: Any = None
        self._active_started_at = 0.0
        self._pending_candidates: list[tuple[int, str]] = []
        self._diagnostic_targets: dict[int, tuple[int, int, str]] = {}
        self._registered = False
        self._status = ""
        self._last_execution_phase = ""

    def settings(self) -> SalvageSettings:
        return self._settings

    def save_settings(self) -> None:
        store.save(self._settings)
        if not self._settings.enabled:
            self._stop_automatic_work()

    def reload_account_settings(self) -> bool:
        self._settings = store.load()
        if not self._settings.enabled:
            self._stop_automatic_work()
        return True

    def _automatic_enabled(self) -> bool:
        """Read the persisted master switch as the final authority for automatic work.

        System Settings is reloadable while its named callback can outlive a
        previous controller object.  Reading the account setting here makes a
        disabled checkbox fail closed even for such a stale callback instance.
        Explicit context-menu salvage deliberately does not use this gate.
        """
        try:
            return bool(store.load().enabled)
        except Exception:
            return False

    def _stop_automatic_work(self) -> None:
        """Prevent any further automatic dispatch after its master switch is disabled."""
        self._timer.Stop()
        self._pending_candidates.clear()
        self._clear_active()

    def boot(self) -> None:
        if self._registered:
            return
        migrated_count = store.migrate_legacy_keep_filters()
        if migrated_count:
            self._status = "Moved %d legacy guided Keep List entries into direct checkbox state." % migrated_count
        try:
            import PyCallback

            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            PyCallback.PyCallback.RemoveByName(_CALLBACK)
            PyCallback.PyCallback.RemoveByName(_DIAGNOSTIC_DRAW_CALLBACK)
            PyCallback.PyCallback.Register(
                _CALLBACK, PyCallback.Phase.Update, self._pass, priority=96, context=PyCallback.Context.Update
            )
            PyCallback.PyCallback.Register(
                _DIAGNOSTIC_DRAW_CALLBACK,
                PyCallback.Phase.Update,
                self._diagnostic_draw_pass,
                priority=97,
                context=PyCallback.Context.Draw,
            )
            ProfilingRegistry().register(_CALLBACK)
            ProfilingRegistry().register(_DIAGNOSTIC_DRAW_CALLBACK)
            self._registered = True
            _log("callback registered name=%s phase=Update priority=96" % _CALLBACK)
        except Exception as exc:
            self._registered = False
            _log("callback registration error: %s" % exc, error=True)

    def status(self) -> str:
        return self._status

    def dump_diagnostics(self) -> None:
        """Log the focused, read-only evidence for the configured salvage test."""
        if self._map_context() is None:
            _diagnostic_log("Salvage diagnostics skipped: map is not stably valid.")
            return
        try:
            from Py4GWCoreLib.Item import Bag, Item
            from Py4GWCoreLib.Inventory import Inventory
            from Py4GWCoreLib.enums_src.Item_enums import Bags, INVENTORY_BAGS, SalvageMode
            from Py4GWCoreLib.enums_src.Model_enums import ModelID
            from Py4GWCoreLib.Map import Map
            from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
            from Sources.frenkeyLib.ItemHandling.Items.item_snapshot import ItemSnapshot

            entries = self._monitor.scan(BAGS)
            active_filters = self.active_filters()
            inventory_bag_ids = {int(bag.value) for bag in INVENTORY_BAGS}
            configured_bag_ids = self._settings_bag_ids()
            def usage_fact(item_id: int, getter: str) -> bool:
                try:
                    return bool(getattr(Item.Usage, getter)(item_id))
                except Exception:
                    return False

            def entry_facts(entry: object) -> str:
                item_id = int(getattr(entry, "item_id", 0))
                model_id = int(Item.GetModelID(item_id))
                return (
                    "bag=%s slot=%d item_id=%d model_id=%d rarity=%s uses=%d "
                    "inventory=%s identified=%s salvageable=%s salvage_kit=%s "
                    "native_lesser=%s native_expert=%s native_perfect=%s"
                    % (
                        getattr(getattr(entry, "bag", None), "name", getattr(entry, "bag", "?")),
                        int(getattr(entry, "slot", -1)),
                        item_id,
                        model_id,
                        str(getattr(entry, "rarity", "?")),
                        int(Item.Usage.GetUses(item_id)),
                        bool(getattr(Item.item_instance(item_id), "is_inventory_item", False)),
                        usage_fact(item_id, "IsIdentified"),
                        usage_fact(item_id, "IsSalvageable"),
                        usage_fact(item_id, "IsSalvageKit"),
                        usage_fact(item_id, "IsLesserKit"),
                        usage_fact(item_id, "IsExpertSalvageKit"),
                        usage_fact(item_id, "IsPerfectSalvageKit"),
                    )
                )

            def bag_entry(bag: Bags, slot: int) -> object | None:
                return next(
                    (
                        entry
                        for entry in entries
                        if int(getattr(getattr(entry, "bag", None), "value", -1)) == int(bag.value)
                        and int(getattr(entry, "slot", -1)) == slot
                    ),
                    None,
                )

            bag_policy = inventory_store.load_bags()
            _diagnostic_log("CANDIDATE_SCAN configured-bag entries:")
            for entry in entries:
                bag = getattr(entry, "bag", None)
                bag_id = int(getattr(bag, "value", -1))
                if bag_id not in configured_bag_ids:
                    continue
                item_id = int(getattr(entry, "item_id", 0))
                reasons: list[str] = []
                if bool(getattr(entry, "is_id_kit", False)):
                    reasons.append("id_kit")
                if bool(getattr(entry, "is_salvage_kit", False)):
                    reasons.append("salvage_kit")
                if not bag_policy.allows(bag_id, int(getattr(entry, "slot", -1))):
                    reasons.append("bag_policy")
                rarity = str(getattr(entry, "rarity", "?"))
                if not self._settings.rarity_enabled(rarity):
                    reasons.append("rarity_disabled")
                identified = usage_fact(item_id, "IsIdentified")
                salvageable = usage_fact(item_id, "IsSalvageable")
                customized = bool(Item.Properties.IsCustomized(item_id))
                if customized:
                    reasons.append("customized")
                identification_required = rarity != "White"
                if identification_required and not identified:
                    reasons.append("unidentified")
                elif not identified:
                    reasons.append("white_unidentified_allowed")
                if not salvageable:
                    reasons.append("not_salvageable")
                if not reasons or reasons == ["white_unidentified_allowed"]:
                    reasons.append("eligible")
                _diagnostic_log(
                    "CANDIDATE_SCAN bag=%s slot=%d item_id=%d model_id=%d rarity=%s "
                    "identified=%s customized=%s salvageable=%s decision=%s"
                    % (
                        getattr(bag, "name", bag),
                        int(getattr(entry, "slot", -1)),
                        item_id,
                        int(Item.GetModelID(item_id)),
                        rarity,
                        identified,
                        customized,
                        salvageable,
                        ",".join(reasons),
                    )
                )

            requested_slots = (0, 1, 2)
            automatic_candidate = self._next_candidate()
            node_kits = scan_salvage_kits(configured_bag_ids)

            _diagnostic_log("=== Salvage diagnostics BEGIN ===")
            settings_document = Settings("Widgets/System/Salvage.ini", "account")
            _diagnostic_log(
                "RUNTIME_POLICY settings_path=%s enabled=%s filter_set=%s active_keep_rules=%d "
                "common_materials=%s rare_materials=%s matching_upgrades=%s"
                % (
                    settings_document.resolved_path(),
                    self._settings.enabled,
                    self._settings.filter_set_id or "(none)",
                    len(active_filters),
                    self._settings.salvage_common_materials,
                    self._settings.salvage_rare_materials,
                    self._settings.salvage_matching_upgrades,
                )
            )
            if not active_filters:
                _diagnostic_log("ACTIVE_KEEP_RULES none: no item is protected by a Salvage keep rule.")
            for filter_definition in active_filters:
                _diagnostic_log("ACTIVE_KEEP_RULE %s" % filter_definition.to_dict())
            _diagnostic_log(
                "EXECUTION registered=%s map_ready=%s enabled=%s active_item=%d "
                "timer_expired=%s timer_elapsed_ms=%d dialog_visible=%s"
                % (
                    self._registered,
                    Map.IsMapReady(),
                    self._settings.enabled,
                    self._active_item_id,
                    self._timer.IsExpired(),
                    int(self._timer.GetTimeElapsed()),
                    Inventory.IsSalvageChoiceDialogVisible(),
                )
            )
            _diagnostic_log(
                "TEST config enabled=%s rarities=%s common_materials=%s rare_materials=%s "
                "matching_upgrades=%s configured_bags=%s free_slots=%d"
                % (
                    self._settings.enabled,
                    [rarity for rarity in ("White", "Blue", "Purple", "Gold") if self._settings.rarity_enabled(rarity)],
                    self._settings.salvage_common_materials,
                    self._settings.salvage_rare_materials,
                    self._settings.salvage_matching_upgrades,
                    list(self._settings_bag_ids()),
                    int(Inventory.GetFreeSlotCount()),
                )
            )
            _diagnostic_log(
                "TEST expected_kit_slots=Backpack:[0,1,2] "
                "(your first visible inventory bag; internal enum Bags.Backpack)"
            )
            for bag in (Bags.Backpack,):
                for slot in requested_slots:
                    entry = bag_entry(bag, slot)
                    if entry is None:
                        _diagnostic_log("TEST_SLOT bag=%s slot=%d EMPTY" % (bag.name, slot))
                    else:
                        _diagnostic_log("TEST_SLOT %s bt_scope=%s" % (entry_facts(entry), int(bag.value) in inventory_bag_ids))

            node_snapshot = ItemSnapshot.get_inventory_snapshot(Bag.Backpack, Bag.Bag_2)
            node_snapshot_kits = [
                item
                for bag_entries in node_snapshot.values()
                for item in bag_entries.values()
                if item is not None and item.is_valid and item.is_salvage_kit
            ]
            _diagnostic_log(
                "NODE_SNAPSHOT kit_count=%d kit_ids=%s"
                % (len(node_snapshot_kits), [item.id for item in node_snapshot_kits])
            )
            for bag in (Bag.Backpack,):
                bag_entries = node_snapshot.get(bag, {})
                for slot in requested_slots:
                    item = bag_entries.get(slot)
                    if item is None:
                        _diagnostic_log("NODE_SNAPSHOT bag=%s slot=%d EMPTY" % (bag.name, slot))
                    else:
                        _diagnostic_log(
                            "NODE_SNAPSHOT bag=%s slot=%d item_id=%d model_id=%d valid=%s "
                            "salvage_kit=%s lesser_model=%s expert_model=%s superior_model=%s perfect_model=%s uses=%d"
                            % (
                                bag.name,
                                slot,
                                item.id,
                                item.model_id,
                                item.is_valid,
                                item.is_salvage_kit,
                                item.model_id == int(ModelID.Salvage_Kit),
                                item.model_id == int(ModelID.Expert_Salvage_Kit),
                                item.model_id == int(ModelID.Superior_Salvage_Kit),
                                item.model_id == int(ModelID.Perfect_Salvage_Kit),
                                item.uses,
                            )
                        )

            if automatic_candidate is None:
                _diagnostic_log("CANDIDATE none selected by _next_candidate()")
            else:
                candidate_id, candidate_mode = automatic_candidate
                candidate_model = int(Item.GetModelID(candidate_id))
                _diagnostic_log(
                    "CANDIDATE selected item_id=%d mode=%s model_id=%d rarity=%s identified=%s "
                    "salvageable=%s configured_scope=%s"
                    % (
                        candidate_id,
                        candidate_mode,
                        candidate_model,
                        Item.Rarity.GetRarity(candidate_id)[1],
                        usage_fact(candidate_id, "IsIdentified"),
                        usage_fact(candidate_id, "IsSalvageable"),
                        any(
                            int(getattr(entry, "item_id", 0)) == candidate_id
                            and int(getattr(getattr(entry, "bag", None), "value", -1)) in configured_bag_ids
                            for entry in entries
                        ),
                    )
                )

            _diagnostic_log("BT_INPUT allow_expert_for_common_materials=True scan_bags=%s" % list(configured_bag_ids))
            _diagnostic_log("BT_MODEL_RULES model_ids_are_diagnostic_only; native capability flags select kits")
            _diagnostic_log(
                "BT_SCAN kit_count=%d kit_ids=%s"
                % (len(node_kits), [kit.item_id for kit in node_kits])
            )
            for kit in node_kits:
                _diagnostic_log(
                    "KIT bag=%s slot=%d item_id=%d model_id=%d uses=%d "
                    "native_lesser=%s native_expert=%s native_perfect=%s"
                    % (
                        kit.bag.name,
                        kit.slot,
                        kit.item_id,
                        kit.model_id,
                        kit.uses,
                        kit.is_lesser,
                        kit.is_expert,
                        kit.is_perfect,
                    )
                )
            common_kit = select_salvage_kit(
                SalvageMode.LesserCraftingMaterials,
                configured_bag_ids,
                allow_expert_for_common_materials=True,
            )
            rare_kit = select_salvage_kit(SalvageMode.RareCraftingMaterials, configured_bag_ids)
            upgrade_kit = select_salvage_kit(SalvageMode.Inscription, configured_bag_ids)
            _diagnostic_log(
                "BT_RESOLUTION selected_for_common=%s selected_for_rare=%s selected_for_upgrade=%s"
                % (
                    common_kit.item_id if common_kit is not None else 0,
                    rare_kit.item_id if rare_kit is not None else 0,
                    upgrade_kit.item_id if upgrade_kit is not None else 0,
                )
            )
            _diagnostic_log("=== Salvage diagnostics END ===")
            self._status = "Focused salvage diagnostics dumped to the Py4GW console."
        except Exception as exc:
            self._status = "Salvage diagnostics failed: %s" % exc
            _log(self._status, error=True)

    def _settings_bag_ids(self) -> tuple[int, ...]:
        return tuple(int(value) for value in inventory_store.load_bags().enabled_bags)

    def is_active(self) -> bool:
        return self._active_item_id > 0

    def available_modes(self, item_id: int) -> tuple[str, ...]:
        """Manual salvage modes that are meaningful for one explicitly selected item."""
        if self._map_context() is None:
            return ()
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            return ()
        entry = next(
            (candidate for candidate in self._monitor.scan(BAGS, force=True) if candidate.item_id == item_id),
            None,
        )
        if entry is None or entry.is_id_kit or entry.is_salvage_kit:
            return ()
        if not inventory_store.load_bags().allows(entry.bag, entry.slot):
            return ()
        try:
            from Py4GWCoreLib.Item import Item

            if Item.Properties.IsCustomized(item_id) or not Item.Usage.IsSalvageable(item_id):
                return ()
            if entry.rarity != "White" and not Item.Usage.IsIdentified(item_id):
                return ()
            modes: list[str] = []
            if self._preferred_kit_id("materials") > 0:
                modes.append("materials")
            if entry.rarity in ("Purple", "Gold") and self._preferred_kit_id("rare_materials") > 0:
                modes.append("rare_materials")
            if self._upgrade_salvage_mode(item_id) is not None and self._preferred_kit_id("upgrades") > 0:
                modes.append("upgrades")
            return tuple(modes)
        except Exception:
            return ()

    def _preferred_kit_id(self, mode: str) -> int:
        """Select an allowed kit compatible with the unmodified SalvageItem BT."""
        if self._map_context() is None:
            return 0
        policy = inventory_store.load_bags()
        kits = [
            kit
            for kit in scan_salvage_kits(tuple(int(bag.value) for bag in INVENTORY_BAGS))
            if policy.allows(kit.bag, kit.slot)
        ]
        infinite_kits = [kit for kit in kits if kit.is_infinite]
        kits = [kit for kit in kits if not kit.is_infinite]
        supported_mode = mode in ("materials", "rare_materials") or self._is_upgrade_action(mode)
        if self._settings.prefer_infinite_salvage_kit and infinite_kits and supported_mode:
            return infinite_kits[0].item_id
        if mode == "materials":
            lesser_kits = [kit for kit in kits if kit.is_lesser]
            compatible = lesser_kits or [kit for kit in kits if kit.is_expert]
        elif mode == "rare_materials":
            compatible = [kit for kit in kits if kit.is_expert]
        elif self._is_upgrade_action(mode):
            compatible = [kit for kit in kits if kit.is_perfect or kit.is_expert]
        else:
            compatible = []
        return min(compatible, key=lambda kit: (kit.uses, kit.item_id)).item_id if compatible else 0

    def request_salvage(self, item_id: int, mode: str = "materials") -> bool:
        """Start the existing Salvage BT for one explicitly selected inventory item."""
        self.boot()
        if not self._registered:
            self._status = "Salvage callbacks are unavailable."
            return False
        if self._map_context() is None:
            self._status = "Salvage is unavailable until the map is fully ready."
            return False
        if not get_item_operation_lease().is_available(_OPERATION_OWNER):
            self._status = "Salvage is waiting for Identification or another item operation to finish."
            return False
        if self.is_active():
            self._status = "Salvage is already active for item %d." % self._active_item_id
            return False
        if mode not in ("materials", "rare_materials", "upgrades"):
            self._status = "The requested salvage mode is invalid."
            return False
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            self._status = "The selected item ID is invalid."
            return False
        entry = next(
            (candidate for candidate in self._monitor.scan(BAGS, force=True) if candidate.item_id == item_id),
            None,
        )
        if entry is None:
            self._status = "The selected item is no longer in the inventory."
            return False
        if entry.is_id_kit or entry.is_salvage_kit:
            self._status = "Identification kits and salvage kits cannot be salvaged."
            return False
        if not inventory_store.load_bags().allows(entry.bag, entry.slot):
            self._status = "The selected item is outside the configured Bags slots."
            return False
        try:
            from Py4GWCoreLib.Inventory import Inventory
            from Py4GWCoreLib.Item import Item

            if Inventory.IsSalvageChoiceDialogVisible():
                self._status = "Close the current salvage dialog before starting another salvage action."
                return False
            if Item.Properties.IsCustomized(item_id):
                self._status = "Customized items can never be salvaged."
                return False
            if not Item.Usage.IsSalvageable(item_id):
                self._status = "Item %d is not salvageable." % item_id
                return False
            if entry.rarity != "White" and not Item.Usage.IsIdentified(item_id):
                self._status = "Identify this %s item before salvaging it." % entry.rarity
                return False
            if mode == "upgrades" and self._upgrade_salvage_mode(item_id) is None:
                self._status = "Item %d has no extractable upgrade." % item_id
                return False
        except Exception as exc:
            self._status = "Could not inspect item %d for salvage: %s" % (item_id, exc)
            return False
        self._pending_candidates.clear()
        return self._start_salvage(item_id, mode, require_automatic_candidate=False)

    def active_filters(self) -> list[Filter]:
        return self.curated_keep_filters() + self.custom_filters()

    def custom_filters(self) -> list[Filter]:
        filters = store.load_filters()
        filter_sets = store.load_filter_sets()
        selected_set = store.filter_set_by_id(filter_sets, self._settings.filter_set_id)
        return store.filters_in_set(filters, selected_set)

    def curated_keep_filters(self) -> list[Filter]:
        """Resolve direct Keep List checkbox state into transient matcher inputs."""
        from . import curated

        keep_list = store.load_keep_list()
        weapon_types = dict(curated.weapon_types())
        weapon_names = {item_type: name for name, item_type in weapon_types.items()}
        filters: list[Filter] = []
        for name in sorted(keep_list.upgrades):
            filters.append(Filter(id="keep_upgrade_%s" % name, name="Keep %s" % name,
                                  upgrades=(UpgradeCriterion(name),)))
        for weapon, name in sorted(keep_list.weapon_mods):
            item_type = weapon_types.get(weapon)
            if item_type is None:
                try:
                    item_type = int(weapon)
                except ValueError:
                    continue
            filters.append(Filter(id="keep_weapon_%s_%s" % (item_type, name), name="Keep %s on %s" % (name, weapon_names.get(item_type, weapon)), item_types=(item_type,), upgrades=(UpgradeCriterion(name),)))
        for item_type in sorted(keep_list.item_types):
            requirement = keep_list.item_max_requirement if keep_list.item_requirement_enabled and item_type in weapon_names else None
            filters.append(Filter(id="keep_type_%d" % item_type, name="Keep all %s" % weapon_names.get(item_type, item_type), item_types=(item_type,), max_requirement=requirement))
        for model_id in sorted(keep_list.model_ids):
            filters.append(Filter(id="keep_model_%d" % model_id, name="Keep model %d" % model_id, model_ids=(model_id,)))
        return filters

    def preview(self) -> tuple[bool, str, list[dict[str, Any]]]:
        """Return a map-ready, read-only explanation of the next salvage decisions.

        This deliberately delegates planned actions to :meth:`_candidate_batch`, the same
        classifier automatic Salvage uses.  It never creates a BT node, dispatches an inventory
        action, opens a dialog, or changes timer state.
        """
        self._diagnostic_targets.clear()
        if self._map_context() is None:
            return False, "Preview is unavailable until the map is fully ready.", []
        if self.is_active():
            return False, "Preview is blocked while Salvage is already handling item %d." % self._active_item_id, []
        try:
            from Py4GWCoreLib.Item import Item

            bag_policy = inventory_store.load_bags()
            filters = self.active_filters()
            candidates = dict(self._candidate_batch(force=True))
            rows: list[dict[str, Any]] = []
            for entry in self._monitor.scan(BAGS, force=True):
                item_id = int(entry.item_id)
                rule_names: tuple[str, ...] = ()
                try:
                    model_id = int(Item.GetModelID(item_id))
                    rule_names = tuple(
                        filter_definition.name
                        for filter_definition in matching_filters(filters, item_id, model_id)
                    )
                except Exception:
                    model_id = 0

                decision = "Skip"
                kit = "-"
                mode = candidates.get(item_id)
                if mode is not None:
                    action_kind = self._action_kind(mode)
                    self._diagnostic_targets[item_id] = (int(entry.bag.value), int(entry.slot), action_kind)
                    decision = {
                        "materials": "Salvage for common materials",
                        "rare_materials": "Salvage for rare materials",
                    }.get(action_kind, "Skip")
                    if action_kind == "upgrades":
                        decision = "Extract matching upgrade (%s slot)" % self._upgrade_action_label(mode)
                    kit = self._preferred_kit_label(mode)
                elif entry.is_id_kit or entry.is_salvage_kit:
                    decision = "Skip: kit"
                elif not bag_policy.allows(entry.bag, entry.slot):
                    decision = "Skip: Bags scope excludes this slot"
                elif not self._settings.rarity_enabled(entry.rarity):
                    decision = "Skip: rarity is disabled"
                else:
                    try:
                        if Item.Properties.IsCustomized(item_id):
                            decision = "Skip: customized items are protected"
                        elif entry.rarity != "White" and not Item.Usage.IsIdentified(item_id):
                            decision = "Skip: identify first"
                        elif not Item.Usage.IsSalvageable(item_id):
                            decision = "Skip: not salvageable"
                        elif rule_names:
                            decision = "KEEP: active Keep List rule"
                        else:
                            decision = "Skip: no enabled salvage action applies"
                    except Exception as exc:
                        decision = "Skip: item inspection failed (%s)" % exc
                rows.append(
                    {
                        "bag": entry.bag.name,
                        "slot": int(entry.slot),
                        "item_id": item_id,
                        "model_id": model_id,
                        "rarity": entry.rarity,
                        "rules": rule_names,
                        "decision": decision,
                        "kit": kit,
                        "mode": mode or "",
                    }
                )
            return True, "Read-only preview refreshed. No salvage action was issued.", rows
        except Exception as exc:
            self._diagnostic_targets.clear()
            return False, "Salvage preview failed: %s" % exc, []

    def clear_preview_targets(self) -> None:
        """Remove only the read-only diagnostic target marks."""
        self._diagnostic_targets.clear()

    def _diagnostic_draw_pass(self) -> None:
        """Outline the immutable target snapshot produced by :meth:`preview`."""
        if not self._diagnostic_targets or self._map_context() is None:
            return
        try:
            from Py4GWCoreLib.py4gwcorelib_src.Color import Color

            colors = {
                "materials": (230, 60, 60),
                "rare_materials": (170, 95, 230),
                "upgrades": (250, 190, 45),
            }
            for entry in self._monitor.scan(BAGS):
                target = self._diagnostic_targets.get(int(entry.item_id))
                if target is None:
                    continue
                bag_id, slot, mode = target
                if int(entry.bag.value) != bag_id or int(entry.slot) != slot:
                    continue
                red, green, blue = colors.get(mode, colors["materials"])
                fill = Color(red, green, blue, 36).to_color()
                outline = Color(red, green, blue, 220).to_color()
                for frame in (entry.bag_frame, entry.inventory_frame):
                    if frame is not None:
                        frame.draw(fill)
                        frame.draw_outline(outline, 2.0)
        except Exception:
            # Diagnostic drawing must never affect the action controller or game UI.
            return

    def _preferred_kit_label(self, mode: str) -> str:
        """Describe the exact policy-approved kit without invoking the BT."""
        preferred_kit_id = self._preferred_kit_id(mode)
        if preferred_kit_id <= 0:
            return "No compatible kit in allowed Bags slots"
        policy = inventory_store.load_bags()
        kits = [
            kit
            for kit in scan_salvage_kits(tuple(int(bag.value) for bag in INVENTORY_BAGS))
            if policy.allows(kit.bag, kit.slot)
        ]
        kit = next((candidate for candidate in kits if candidate.item_id == preferred_kit_id), None)
        if kit is None:
            return "Selected kit %d is no longer available" % preferred_kit_id
        capability = "Lesser" if kit.is_lesser else "Expert" if kit.is_expert else "Perfect"
        return "%s kit #%d (%d uses, %s:%d)" % (
            capability,
            kit.item_id,
            kit.uses,
            kit.bag.name,
            kit.slot,
        )

    def update(self) -> None:
        self._pass()

    def _trace_execution(self, phase: str, detail: str = "") -> None:
        if self._last_execution_phase == phase:
            return
        self._last_execution_phase = phase
        suffix = " %s" % detail if detail else ""
        _log("EXECUTION phase=%s%s" % (phase, suffix))

    def _pass(self) -> None:
        map_context = self._map_context()
        if map_context is None:
            self._timer.Stop()
            self._last_map_id = 0
            self._outpost_pass_pending = False
            self._pending_candidates.clear()
            self._diagnostic_targets.clear()
            self._clear_active()
            self._trace_execution("map_blocked", "map_ready=False")
            return
        if self._timer.IsStopped():
            self._timer.Start()
        map_id, is_explorable, is_outpost = map_context
        if map_id != self._last_map_id:
            self._last_map_id = map_id
            self._outpost_pass_pending = is_outpost
            self._pending_candidates.clear()
            self._diagnostic_targets.clear()
            self._timer.Reset()
            self._clear_active()
        if not self._automatic_enabled():
            self._stop_automatic_work()
            self._trace_execution("disabled", "enabled=False")
            return
        if self._active_item_id > 0:
            if not get_item_operation_lease().acquire(_OPERATION_OWNER):
                self._status = "Salvage is paused while another item operation owns the pipeline."
                return
            self._trace_execution("active", "item=%d" % self._active_item_id)
            self._process_active()
            return
        if not is_explorable and not is_outpost:
            self._pending_candidates.clear()
            self._trace_execution("map_blocked", "map_type=unsupported")
            return
        if not get_item_operation_lease().is_available(_OPERATION_OWNER):
            self._trace_execution("operation_blocked", "owner=%s" % get_item_operation_lease().owner())
            self._status = "Salvage is waiting for Identification or another item operation to finish."
            return
        try:
            from Py4GWCoreLib.Inventory import Inventory

            if Inventory.IsSalvageChoiceDialogVisible():
                self._trace_execution("dialog_blocked", "native_salvage_dialog=True")
                self._status = "Salvage is waiting for the open native salvage dialog to close."
                return
        except Exception as exc:
            self._trace_execution("dialog_probe_error", str(exc))
        # A timer pulse owns its complete candidate snapshot.  Drain that snapshot
        # before applying the outpost one-shot rule; otherwise the first item would
        # start and every remaining eligible item would be stranded until a later map.
        if self._pending_candidates:
            item_id, mode = self._pending_candidates.pop(0)
            self._trace_execution(
                "batch_next",
                "item=%d mode=%s remaining=%d" % (item_id, mode, len(self._pending_candidates)),
            )
            _log(
                "Starting Salvage BT item=%d mode=%s (batch remaining=%d)."
                % (item_id, mode, len(self._pending_candidates))
            )
            self._start_salvage(item_id, mode)
            return
        if is_outpost:
            if not self._outpost_pass_pending:
                self._trace_execution("outpost_wait", "already_processed=True")
                return
            self._outpost_pass_pending = False
            self._run_cycle()
            return
        if not self._timer.IsExpired():
            self._trace_execution("timer_wait", "elapsed_ms=%d" % int(self._timer.GetTimeElapsed()))
            return
        self._run_cycle()

    def _map_context(self) -> tuple[int, bool, bool] | None:
        return self._map_gate.context(self._arrival_delay_seconds)

    @staticmethod
    def _arrival_delay_seconds(map_context: tuple[int, bool, bool]) -> float:
        return float(inventory_store.load_bags().arrival_delay_seconds(map_context[2]))

    def _run_cycle(self) -> None:
        if self._map_context() is None or not self._automatic_enabled():
            return
        self._trace_execution("candidate_scan", "cycle_started=True")
        self._timer.Reset()
        self._pending_candidates = self._candidate_batch(force=True)
        if not self._pending_candidates:
            self._trace_execution("no_candidate")
            return
        item_id, mode = self._pending_candidates.pop(0)
        self._trace_execution("starting", "item=%d mode=%s" % (item_id, mode))
        _log("Starting Salvage BT item=%d mode=%s." % (item_id, mode))
        self._start_salvage(item_id, mode)

    def _next_candidate(self) -> tuple[int, str] | None:
        candidates = self._candidate_batch(force=True)
        return candidates[0] if candidates else None

    def _candidate_batch(self, force: bool = False) -> list[tuple[int, str]]:
        if self._map_context() is None:
            return []
        from Py4GWCoreLib.Item import Item

        bag_policy = inventory_store.load_bags()
        filters = self.active_filters()
        candidates: list[tuple[int, str]] = []
        for entry in self._monitor.scan(BAGS, force=force):
            if entry.is_id_kit or entry.is_salvage_kit or not bag_policy.allows(entry.bag, entry.slot):
                continue
            if not self._settings.rarity_enabled(entry.rarity):
                continue
            try:
                identified = bool(Item.Usage.IsIdentified(entry.item_id))
                if Item.Properties.IsCustomized(entry.item_id):
                    continue
                if (entry.rarity != "White" and not identified) or not Item.Usage.IsSalvageable(entry.item_id):
                    continue
                model_id = int(Item.GetModelID(entry.item_id))
                matched_keep_filters = matching_filters(filters, entry.item_id, model_id)
                if matched_keep_filters:
                    # A Salvage filter is a keep rule first.  It may request extraction only
                    # when it explicitly names an upgrade and an Expert-or-better kit can
                    # perform that extraction.  A protected item must never fall through to
                    # either material mode when that route is unavailable.
                    action = self._matching_keep_action(entry.item_id, matched_keep_filters)
                    if action != "keep":
                        candidates.append((int(entry.item_id), action))
                    continue
                if self._settings.salvage_rare_materials and entry.rarity in ("Purple", "Gold"):
                    candidates.append((int(entry.item_id), "rare_materials"))
                    continue
                if self._settings.salvage_common_materials:
                    candidates.append((int(entry.item_id), "materials"))
            except Exception:
                continue
        return candidates

    def _matching_keep_action(self, item_id: int, matched_filters: list[Filter]) -> str:
        """Resolve a keep match without allowing it to become material salvage.

        Generic filters (models, item types, requirements, and modifier rules) mean
        "keep the item".  A matching named-upgrade rule may instead request extraction,
        but only with a valid Expert/Superior/Perfect kit in the configured Bags scope.
        """
        if not self._settings.salvage_matching_upgrades:
            return "keep"
        upgrade_mode = self._matched_upgrade_salvage_mode(item_id, matched_filters)
        if upgrade_mode is None:
            return "keep"
        if self._preferred_kit_id("upgrades") <= 0:
            return "keep"
        return self._upgrade_action(upgrade_mode)

    def _start_salvage(self, item_id: int, mode: str, require_automatic_candidate: bool = True) -> bool:
        lease = get_item_operation_lease()
        keep_lease = False
        try:
            if self._map_context() is None:
                self._status = "Salvage is unavailable until the map is fully ready."
                return False
            if require_automatic_candidate and not self._automatic_enabled():
                self._status = "Automatic Salvage is disabled. No salvage action was issued."
                return False
            if not lease.acquire(_OPERATION_OWNER):
                self._status = "Salvage is waiting for Identification or another item operation to finish."
                return False
            if require_automatic_candidate and (item_id, mode) not in self._candidate_batch(force=True):
                self._status = "Skipped stale salvage candidate %d." % item_id
                return False
            from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree

            salvage_mode = self._salvage_mode(item_id, mode)
            if salvage_mode is None:
                self._status = "Salvage could not resolve a BT mode for item %d." % item_id
                return False
            preferred_kit_id = self._preferred_kit_id(mode)
            if preferred_kit_id <= 0:
                self._status = "No compatible salvage kit is in the configured Bags slots."
                return False

            node = RoutinesBT.Items.SalvageItem(
                item_id,
                salvage_mode=salvage_mode,
                preferred_kit_id=preferred_kit_id,
                allow_expert_for_common_materials=(mode == "materials"),
                state_key="system_settings_salvage_%d" % item_id,
                debug_enabled=self._settings.debug_enabled,
            )
            state = node.tick()
            _log("Salvage BT initial tick item=%d mode=%s state=%s" % (item_id, mode, state))
            if state == BehaviorTree.NodeState.FAILURE:
                self.dump_diagnostics()
                self._status = "Salvage BT node could not start for item %d." % item_id
                return False
            if state == BehaviorTree.NodeState.SUCCESS:
                self._status = "Salvaged item %d." % item_id
                return True
            self._active_item_id = item_id
            self._active_node = node
            self._active_started_at = time.monotonic()
            keep_lease = True
            self._status = "Salvage BT node running for item %d (%s)." % (item_id, mode)
            _log("Salvage BT active item=%d mode=%s." % (item_id, mode))
            return True
        except Exception as exc:
            self._clear_active()
            self._status = "Salvage request failed for item %d: %s" % (item_id, exc)
            _log(self._status, error=True)
            return False
        finally:
            if not keep_lease:
                lease.release(_OPERATION_OWNER)

    def _salvage_mode(self, item_id: int, mode: str) -> Any:
        from Py4GWCoreLib.enums_src.Item_enums import SalvageMode

        if mode == "materials":
            return SalvageMode.LesserCraftingMaterials
        if mode == "rare_materials":
            return SalvageMode.RareCraftingMaterials
        if mode == "upgrades":
            return self._upgrade_salvage_mode(item_id)
        if mode.startswith(_UPGRADE_ACTION_PREFIX):
            try:
                return SalvageMode(int(mode.removeprefix(_UPGRADE_ACTION_PREFIX)))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _is_upgrade_action(mode: str) -> bool:
        return mode == "upgrades" or mode.startswith(_UPGRADE_ACTION_PREFIX)

    @staticmethod
    def _action_kind(mode: str) -> str:
        return "upgrades" if SalvageController._is_upgrade_action(mode) else mode

    @staticmethod
    def _upgrade_action(mode: Any) -> str:
        return "%s%d" % (_UPGRADE_ACTION_PREFIX, int(mode))

    @staticmethod
    def _upgrade_action_label(action: str) -> str:
        from Py4GWCoreLib.enums_src.Item_enums import SalvageMode

        try:
            return SalvageMode(int(action.removeprefix(_UPGRADE_ACTION_PREFIX))).name
        except (TypeError, ValueError):
            return "unknown"

    @staticmethod
    def _matched_upgrade_salvage_mode(item_id: int, matched_filters: list[Filter]) -> Any:
        """Return the actual Item.Mods slot for a named upgrade that matched a Keep rule."""
        from Py4GWCoreLib.Item import Item
        from Py4GWCoreLib.enums_src.Item_enums import SalvageMode

        slot_to_mode = {
            Item.Mods.Slot.Prefix: SalvageMode.Prefix,
            Item.Mods.Slot.Suffix: SalvageMode.Suffix,
            Item.Mods.Slot.Inscription: SalvageMode.Inscription,
        }
        applied_upgrades = tuple(Item.Mods.GetUpgrades(item_id))
        for filter_definition in matched_filters:
            for criterion in filter_definition.upgrades:
                for name, slot in applied_upgrades:
                    if canonical_upgrade_name(name) != canonical_upgrade_name(criterion.name):
                        continue
                    if criterion.slot is not None and int(slot) != int(criterion.slot):
                        continue
                    if criterion.maxed and not Item.Mods.IsMaxed(item_id, name):
                        continue
                    mode = slot_to_mode.get(slot)
                    if mode is not None:
                        return mode
        return None

    @staticmethod
    def _upgrade_salvage_mode(item_id: int) -> Any:
        from Py4GWCoreLib.Item import Item
        from Py4GWCoreLib.enums_src.Item_enums import SalvageMode

        slots = {slot for _name, slot in Item.Mods.GetUpgrades(item_id)}
        if Item.Mods.Slot.Inscription in slots:
            return SalvageMode.Inscription
        if Item.Mods.Slot.Suffix in slots:
            return SalvageMode.Suffix
        if Item.Mods.Slot.Prefix in slots:
            return SalvageMode.Prefix
        return None

    def _process_active(self) -> None:
        node = self._active_node
        item_id = self._active_item_id
        if node is None or item_id <= 0:
            self._clear_active()
            return
        try:
            from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree

            state = node.tick()
            _log("Salvage BT tick item=%d state=%s" % (item_id, state))
            if state == BehaviorTree.NodeState.SUCCESS:
                self._status = "Salvaged item %d." % item_id
                self._clear_active()
                return
            if state == BehaviorTree.NodeState.FAILURE:
                self.dump_diagnostics()
                self._status = (
                    "Salvage BT node failed for item %d; see the System Settings / Salvage "
                    "diagnostic entries for the failed phase."
                ) % item_id
                _log(self._status, error=True)
                self._clear_active()
                return
            if time.monotonic() - self._active_started_at > _SALVAGE_TIMEOUT_SECONDS + 10:
                self._status = "Salvage BT node timed out for item %d." % item_id
                self._clear_active()
        except Exception as exc:
            self._status = "Salvage polling failed for item %d: %s" % (item_id, exc)
            self._clear_active()
            _log(self._status, error=True)

    def _clear_active(self) -> None:
        self._active_item_id = 0
        self._active_node = None
        self._active_started_at = 0.0
        get_item_operation_lease().release(_OPERATION_OWNER)


_controller: Optional[SalvageController] = None


def get_controller() -> SalvageController:
    global _controller
    if _controller is None:
        _controller = SalvageController()
    return _controller
