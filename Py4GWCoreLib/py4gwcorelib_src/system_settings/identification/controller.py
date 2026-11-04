"""Runtime owner for automatic Identification."""

from dataclasses import replace
import time
from typing import Any, Optional

from Py4GWCoreLib import ThrottledTimer
from Py4GWCoreLib.enums_src.Item_enums import INVENTORY_BAGS
from Py4GWCoreLib.enums_src.Model_enums import ModelID

from ..inventory.monitor import InventoryMonitor
from ..inventory import store as inventory_store
from ..inventory.model import BAGS
from ..item_runtime import StableMapGate, get_item_operation_lease
from ..loot_filter_factory.matcher import matches
from ..loot_filter_factory.model import MATCH_ALL, Filter
from . import store
from .model import IdentificationSettings


_CALLBACK = "SystemSettingsIdentification"
_IDENTIFY_INTERVAL_MS = 15_000
_IDENTIFY_TIMEOUT_SECONDS = 2.0
_OPERATION_OWNER = "system_settings_identification"


def _log(message: str, error: bool = False) -> None:
    try:
        import PySystem

        level = PySystem.Console.MessageType.Error if error else PySystem.Console.MessageType.Info
        PySystem.Console.Log("System Settings / Identification", message, level)
    except Exception:
        pass


class IdentificationController:
    def __init__(self) -> None:
        self._settings = store.load()
        self._monitor = InventoryMonitor()
        self._id_timer = ThrottledTimer(_IDENTIFY_INTERVAL_MS)
        self._map_gate = StableMapGate()
        self._last_map_id = 0
        self._outpost_pass_pending = False
        self._active_node: Any = None
        self._active_node_finished = False
        self._active_item_id = 0
        self._active_started_at = 0.0
        self._registered = False
        self._status = ""

    def settings(self) -> IdentificationSettings:
        return self._settings

    def save_settings(self) -> None:
        store.save(self._settings)

    def reload_account_settings(self) -> bool:
        """Reload the account-owned Identification INI after an account-copy transaction."""
        self._settings = store.load()
        return True

    def boot(self) -> None:
        if self._registered:
            return
        try:
            import PyCallback

            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            PyCallback.PyCallback.RemoveByName(_CALLBACK)
            PyCallback.PyCallback.Register(
                _CALLBACK, PyCallback.Phase.Update, self._pass, priority=97, context=PyCallback.Context.Update
            )
            ProfilingRegistry().register(_CALLBACK)
            self._registered = True
        except Exception as exc:
            self._registered = False
            _log("callback registration error: %s" % exc, error=True)

    def status(self) -> str:
        return self._status

    def active_filters(self) -> list[Filter]:
        filters = store.load_filters()
        filter_sets = store.load_filter_sets()
        selected_set = store.filter_set_by_id(filter_sets, self._settings.filter_set_id)
        return store.filters_in_set(filters, selected_set)

    def is_active(self) -> bool:
        return self._active_item_id > 0

    def can_identify(self, item_id: int) -> bool:
        """Whether one explicitly selected inventory item can be identified."""
        if self._map_context() is None:
            return False
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            return False
        entry = next(
            (candidate for candidate in self._monitor.scan(BAGS, force=True) if candidate.item_id == item_id),
            None,
        )
        if entry is None or entry.is_id_kit or entry.is_salvage_kit:
            return False
        if not inventory_store.load_bags().allows(entry.bag, entry.slot):
            return False
        try:
            from Py4GWCoreLib.Item import Item

            return not bool(Item.Usage.IsIdentified(item_id)) and self._has_usable_id_kit()
        except Exception:
            return False

    def preferred_kit_id(self) -> int:
        """Return the allowed infinite kit when the option selects it, otherwise 0.

        The kit's native flags and use count are unverified, so its model decides.
        """
        if not self._settings.prefer_infinite_id_kit or self._map_context() is None:
            return 0
        try:
            from Py4GWCoreLib.Item import Item

            policy = inventory_store.load_bags()
            for entry in self._monitor.scan(INVENTORY_BAGS, force=True):
                if (
                    int(Item.GetModelID(entry.item_id)) == int(ModelID.Infinite_Identification_Kit)
                    and policy.allows(entry.bag, entry.slot)
                ):
                    return entry.item_id
        except Exception:
            return 0
        return 0

    def _has_usable_id_kit(self) -> bool:
        """Require the preferred or legacy-selected kit to live in an allowed Bags slot."""
        if self._map_context() is None:
            return False
        if self.preferred_kit_id() > 0:
            return True
        try:
            from Py4GWCoreLib.Inventory import Inventory

            kit_id = int(Inventory.GetFirstIDKit())
        except Exception:
            return False
        if kit_id <= 0:
            return False
        entry = next(
            (candidate for candidate in self._monitor.scan(BAGS, force=True) if candidate.item_id == kit_id),
            None,
        )
        return bool(
            entry is not None
            and entry.is_id_kit
            and inventory_store.load_bags().allows(entry.bag, entry.slot)
        )

    def request_identify(self, item_id: int) -> bool:
        """Start the existing Identification BT for one explicitly selected inventory item."""
        self.boot()
        if not self._registered:
            self._status = "Identification callbacks are unavailable."
            return False
        if self._map_context() is None:
            self._status = "Identification is unavailable until the map is fully ready."
            return False
        if not get_item_operation_lease().is_available(_OPERATION_OWNER):
            self._status = "Identification is waiting for Salvage or another item operation to finish."
            return False
        if self.is_active():
            self._status = "Identification is already active for item %d." % self._active_item_id
            return False
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            self._status = "The selected item ID is invalid."
            return False
        if not self.can_identify(item_id):
            self._status = "The selected item cannot be identified."
            return False
        self._start_identify(item_id)
        return self._active_item_id == item_id

    def update(self) -> None:
        self._pass()

    def _pass(self) -> None:
        map_context = self._map_context()
        if map_context is None:
            self._id_timer.Stop()
            self._last_map_id = 0
            self._outpost_pass_pending = False
            self._clear_active()
            return
        if self._id_timer.IsStopped():
            self._id_timer.Start()
        map_id, is_explorable, is_outpost = map_context
        if map_id != self._last_map_id:
            self._last_map_id = map_id
            self._outpost_pass_pending = is_outpost
            self._id_timer.Reset()
            self._clear_active()
        if self._active_item_id > 0:
            if not get_item_operation_lease().acquire(_OPERATION_OWNER):
                self._status = "Identification is paused while another item operation owns the pipeline."
                return
            self._process_active()
            return
        if not self._settings.enabled:
            return
        if not get_item_operation_lease().is_available(_OPERATION_OWNER):
            self._status = "Identification is waiting for Salvage or another item operation to finish."
            return
        if is_outpost:
            if not self._outpost_pass_pending:
                return
            self._outpost_pass_pending = False
            self._run_cycle()
            return
        if not is_explorable:
            return
        if not self._id_timer.IsExpired():
            return
        self._run_cycle()

    def _map_context(self) -> tuple[int, bool, bool] | None:
        return self._map_gate.context(self._arrival_delay_seconds)

    @staticmethod
    def _arrival_delay_seconds(map_context: tuple[int, bool, bool]) -> float:
        return float(inventory_store.load_bags().arrival_delay_seconds(map_context[2]))

    def _run_cycle(self) -> None:
        if self._map_context() is None:
            return
        self._id_timer.Reset()
        item_id = self._next_candidate()
        if item_id <= 0:
            return
        self._start_identify(item_id)

    def _next_candidate(self) -> int:
        if self._map_context() is None:
            return 0
        from Py4GWCoreLib.Item import Item

        policy = inventory_store.load_bags()
        for entry in self._monitor.scan(BAGS):
            if entry.is_id_kit or entry.is_salvage_kit or not policy.allows(entry.bag, entry.slot):
                continue
            if not self._settings.rarity_enabled(entry.rarity):
                continue
            try:
                if Item.Usage.IsIdentified(entry.item_id):
                    continue
                model_id = int(Item.GetModelID(entry.item_id))
                if self._excluded_by_filter_set(entry.item_id, model_id):
                    continue
                return int(entry.item_id)
            except Exception:
                continue
        return 0

    def _excluded_by_filter_set(self, item_id: int, model_id: int) -> bool:
        """ID exclusions are HAS-ALL per filter; any complete exclusion filter vetoes the item."""
        for source_filter in self.active_filters():
            # Identification owns this filter definition. Its exclusion semantics are always ALL;
            # the temporary replacement keeps the shared criterion model immutable at runtime.
            id_filter = replace(source_filter, mode=MATCH_ALL)
            if id_filter.enabled and matches(id_filter, item_id, model_id):
                return True
        return False

    def _start_identify(self, item_id: int) -> None:
        lease = get_item_operation_lease()
        keep_lease = False
        try:
            if self._map_context() is None:
                return
            if not lease.acquire(_OPERATION_OWNER):
                self._status = "Identification is waiting for Salvage or another item operation to finish."
                return
            if not self._has_usable_id_kit():
                self._status = "No usable identification kit is in the configured Bags slots."
                return
            from ...BehaviorTree import BehaviorTree
            from Sources.frenkeyLib.ItemHandling.BTNodes import BTNodes

            node = BTNodes.Items.IdentifyItems(
                [item_id],
                fail_if_no_kit=True,
                succeed_if_already_identified=True,
                aftercast_ms=150,
                preferred_kit_id=self.preferred_kit_id(),
            )
            state = node.tick()
            if state == BehaviorTree.NodeState.FAILURE:
                self._status = (
                    "Identification could not start for item %d (no usable ID kit or invalid item)." % item_id
                )
                return
            self._active_node = node
            self._active_node_finished = state != BehaviorTree.NodeState.RUNNING
            self._active_item_id = item_id
            self._active_started_at = time.monotonic()
            keep_lease = True
            self._status = "Identification requested for item %d." % item_id
        except Exception as exc:
            self._status = "Identification request failed for item %d: %s" % (item_id, exc)
            _log(self._status, error=True)
        finally:
            if not keep_lease:
                lease.release(_OPERATION_OWNER)

    def _process_active(self) -> None:
        item_id = self._active_item_id
        try:
            from Py4GWCoreLib.Item import Item
            from ...BehaviorTree import BehaviorTree

            if Item.Usage.IsIdentified(item_id):
                self._status = "Identified item %d." % item_id
                self._clear_active()
                return
            if self._active_node is not None and not self._active_node_finished:
                state = self._active_node.tick()
                if state == BehaviorTree.NodeState.FAILURE:
                    self._status = "Identification failed for item %d." % item_id
                    self._clear_active()
                    return
                self._active_node_finished = state != BehaviorTree.NodeState.RUNNING
            if time.monotonic() - self._active_started_at >= _IDENTIFY_TIMEOUT_SECONDS:
                self._status = "Identification timed out for item %d." % item_id
                self._clear_active()
        except Exception as exc:
            self._status = "Identification polling failed for item %d: %s" % (item_id, exc)
            self._clear_active()

    def _clear_active(self) -> None:
        self._active_node = None
        self._active_node_finished = False
        self._active_item_id = 0
        self._active_started_at = 0.0
        get_item_operation_lease().release(_OPERATION_OWNER)


_controller: Optional[IdentificationController] = None


def get_controller() -> IdentificationController:
    global _controller
    if _controller is None:
        _controller = IdentificationController()
    return _controller
