"""Runtime owner for System Settings inventory features and explicit item operations."""

from dataclasses import dataclass
import time
from collections.abc import Iterable
from typing import Optional

from Py4GWCoreLib.py4gwcorelib_src.Color import Color

from ..item_runtime import StableMapGate, get_item_operation_lease
from . import store
from .model import BagSettings, ColorizeSettings, InventoryFeatureSettings, BAGS
from Py4GWCoreLib.enums_src.Item_enums import INVENTORY_BAGS, MAX_BAG_SIZES, STORAGE_BAGS, Bags
from .monitor import InventoryMonitor

_CONTEXT_POPUP_ID = "SystemItemsContextMenu"
_CONTEXT_CALLBACK = "SystemItemsContextMenuCallback"
_COLORIZE_CALLBACK = "SystemItemsColorize"
_ACTION_CALLBACK = "SystemItemsActions"
_IDENTIFY_TIMEOUT_SECONDS = 2.0
_ITEM_MAP_GATE = StableMapGate()
_IDENTIFY_OPERATION_OWNER = "system_settings_inventory_identification"
_SALVAGE_OPERATION_OWNER = "system_settings_inventory_salvage"


@dataclass
class _IdentifyRun:
    pending_item_ids: list[int]
    active_item_id: int = 0
    active_started_at: float = 0.0
    identified_count: int = 0
    skipped_count: int = 0


@dataclass
class _SalvageRun:
    pending_item_ids: list[int]
    salvage_kit_id: int | None = None
    active_item_id: int = 0
    active_quantity: int = 0
    salvaged_count: int = 0
    skipped_count: int = 0


@dataclass(frozen=True)
class _ContextItemActions:
    item_id: int
    kit_label: str = ""
    can_identify: bool = False
    salvage_modes: tuple[str, ...] = ()

    def has_items(self) -> bool:
        return bool(self.kit_label or self.can_identify or self.salvage_modes)


def _log(message: str, error: bool = False) -> None:
    try:
        import PySystem

        level = PySystem.Console.MessageType.Error if error else PySystem.Console.MessageType.Info
        PySystem.Console.Log("System Settings / Items", message, level)
    except Exception:
        pass


def _color(color: tuple[int, int, int, int], alpha: int | None = None) -> Color:
    value = Color(*color)
    if alpha is not None:
        value.set_a(alpha)
    return value


def _map_is_ready() -> bool:
    return _ITEM_MAP_GATE.context() is not None


class InventorySettingsController:
    def __init__(self) -> None:
        self._settings = store.load()
        self._bags = store.load_bags()
        self._monitor = InventoryMonitor()
        self._context_monitor = InventoryMonitor()
        self._booted = False
        self._native_tints: dict[int, int] = {}
        self._xunlai_status = ""
        self._native_outline_warned = False
        self._callbacks_registered = False
        self._identify_run: _IdentifyRun | None = None
        self._salvage_run: _SalvageRun | None = None
        self._action_status = ""
        self._context_item_id = 0
        self._context_actions: _ContextItemActions | None = None

    def boot(self) -> None:
        if not self._booted:
            self._booted = True
            self._register_callbacks()

    def settings(self) -> InventoryFeatureSettings:
        return self._settings

    def bag_settings(self) -> BagSettings:
        """The shared bag/slot scope used by identification and later item operations."""
        return self._bags

    def save_settings(self) -> None:
        store.save(self._settings)
        store.save_bags(self._bags)

    def reload_account_settings(self) -> bool:
        """Reload the account-owned inventory documents after an account-copy transaction."""
        self._settings = store.load()
        self._bags = store.load_bags()
        self._native_tints.clear()
        return True

    def _register_callbacks(self) -> None:
        try:
            import PyCallback

            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            PyCallback.PyCallback.RemoveByName(_CONTEXT_CALLBACK)
            PyCallback.PyCallback.RemoveByName(_COLORIZE_CALLBACK)
            PyCallback.PyCallback.RemoveByName(_ACTION_CALLBACK)
            PyCallback.PyCallback.Register(_CONTEXT_CALLBACK, PyCallback.Phase.Update, self._context_pass,
                                            priority=99, context=PyCallback.Context.Draw)
            PyCallback.PyCallback.Register(_COLORIZE_CALLBACK, PyCallback.Phase.Update, self._colorize_pass,
                                            priority=99, context=PyCallback.Context.Draw)
            PyCallback.PyCallback.Register(_ACTION_CALLBACK, PyCallback.Phase.Update, self._action_pass,
                                            priority=98, context=PyCallback.Context.Draw)
            registry = ProfilingRegistry()
            registry.register(_CONTEXT_CALLBACK)
            registry.register(_COLORIZE_CALLBACK)
            registry.register(_ACTION_CALLBACK)
            self._callbacks_registered = True
        except Exception as exc:
            self._callbacks_registered = False
            _log("item callback registration error: %s" % exc, error=True)

    def open_xunlai(self) -> None:
        if not _map_is_ready():
            self._xunlai_status = "Map is not ready."
            return
        try:
            from Py4GWCoreLib import GLOBAL_CACHE

            if GLOBAL_CACHE.Inventory.IsStorageOpen():
                self._xunlai_status = "Xunlai Vault is already open."
                return
            opened = bool(GLOBAL_CACHE.Inventory.OpenXunlaiWindow())
            self._xunlai_status = "Xunlai Vault is already open." if opened else "Xunlai Vault open requested."
        except Exception as exc:
            self._xunlai_status = "Open Xunlai failed: %s" % exc
            _log(self._xunlai_status, error=True)

    def xunlai_status(self) -> str:
        return self._xunlai_status

    def action_status(self) -> str:
        """The latest explicit native item-operation result or progress message."""
        return self._action_status

    def is_action_active(self) -> bool:
        return self._identify_run is not None or self._salvage_run is not None

    def is_identify_active(self) -> bool:
        return self._identify_run is not None

    def is_salvage_active(self) -> bool:
        return self._salvage_run is not None

    def cancel_identify(self) -> bool:
        """Cancel the remaining explicit identify requests without touching native queues."""
        if self._identify_run is None:
            self._action_status = "No identify batch is active."
            return False
        run = self._identify_run
        self._identify_run = None
        get_item_operation_lease().release(_IDENTIFY_OPERATION_OWNER)
        self._action_status = "Identify batch cancelled after %d identified and %d skipped." % (
            run.identified_count,
            run.skipped_count,
        )
        return True

    def cancel_salvage(self) -> bool:
        """Stop beginning further requested salvage items; an open game dialog remains the user's decision."""
        if self._salvage_run is None:
            self._action_status = "No salvage batch is active."
            return False
        run = self._salvage_run
        self._salvage_run = None
        get_item_operation_lease().release(_SALVAGE_OPERATION_OWNER)
        self._action_status = "Salvage batch stopped after %d completed and %d skipped item(s)." % (
            run.salvaged_count,
            run.skipped_count,
        )
        return True

    def unidentified_item_ids(self, rarities: Iterable[str] | None = None) -> list[int]:
        """Current configured-Bags candidates, optionally constrained by explicit rarity choices."""
        if not _map_is_ready():
            return []
        selected_rarities = {str(rarity).strip() for rarity in rarities or () if str(rarity).strip()}
        candidates: list[int] = []
        for entry in self._monitor.scan(BAGS):
            if entry.is_id_kit or entry.is_salvage_kit:
                continue
            if selected_rarities and entry.rarity not in selected_rarities:
                continue
            if not self._bags.allows(entry.bag, entry.slot):
                continue
            try:
                from Py4GWCoreLib.Item import Item

                if not Item.Usage.IsIdentified(entry.item_id):
                    candidates.append(entry.item_id)
            except Exception:
                continue
        return candidates

    def hovered_item_id(self) -> int:
        if not _map_is_ready():
            return 0
        slot = self._context_monitor.hovered_slot(BAGS)
        return int(slot.item_id) if slot is not None else 0

    def request_identify(self, item_ids: Iterable[int]) -> bool:
        """Queue one explicit identify batch; each native result is polled before advancing."""
        self.boot()
        if not _map_is_ready():
            self._action_status = "Identification is unavailable until the map is stably valid."
            return False
        if not self._callbacks_registered:
            self._action_status = "System Settings item callbacks are unavailable."
            return False
        if self.is_action_active():
            self._action_status = "Another System Settings item operation is already active."
            return False
        targets: list[int] = []
        seen: set[int] = set()
        allowed_item_ids = {
            entry.item_id for entry in self._monitor.scan(BAGS)
            if not entry.is_id_kit and not entry.is_salvage_kit and self._bags.allows(entry.bag, entry.slot)
        }
        for raw_item_id in item_ids:
            try:
                item_id = int(raw_item_id)
            except (TypeError, ValueError):
                continue
            if item_id > 0 and item_id in allowed_item_ids and item_id not in seen:
                seen.add(item_id)
                targets.append(item_id)
        if not targets:
            self._action_status = "No unidentified items are available in the configured Bags."
            return False
        self._identify_run = _IdentifyRun(targets)
        self._action_status = "Identify batch queued for %d item(s)." % len(targets)
        return True

    def request_salvage_hovered(self) -> bool:
        """Start native salvage for the currently hovered item; confirmation stays explicit."""
        item_id = self.hovered_item_id()
        if item_id <= 0:
            self._action_status = "Hover an inventory item before starting salvage."
            return False
        return self.request_salvage(item_id)

    def request_salvage(self, item_id: int, salvage_kit_id: int | None = None) -> bool:
        """Start native salvage for one explicit inventory item; confirmation stays explicit."""
        return self.request_salvage_batch([item_id], salvage_kit_id=salvage_kit_id)

    def request_salvage_batch(self, item_ids: Iterable[int], salvage_kit_id: int | None = None) -> bool:
        """Queue explicit salvage requests; every game dialog remains user-confirmed."""
        self.boot()
        if not _map_is_ready():
            self._action_status = "Salvage is unavailable until the map is stably valid."
            return False
        if not self._callbacks_registered:
            self._action_status = "System Settings item callbacks are unavailable."
            return False
        if self.is_action_active():
            self._action_status = "Another System Settings item operation is already active."
            return False
        allowed_item_ids = {
            entry.item_id for entry in self._monitor.scan(BAGS)
            if not entry.is_id_kit and not entry.is_salvage_kit and self._bags.allows(entry.bag, entry.slot)
        }
        try:
            targets = [int(item_id) for item_id in item_ids if int(item_id) in allowed_item_ids]
        except (TypeError, ValueError):
            self._action_status = "Salvage request contains an invalid item ID."
            return False
        if not targets:
            self._action_status = "No salvage items were supplied from the configured Bags slots."
            return False
        if salvage_kit_id is not None:
            try:
                salvage_kit_id = int(salvage_kit_id)
            except (TypeError, ValueError):
                self._action_status = "The selected salvage kit ID is invalid."
                return False
            allowed_kit_ids = {
                entry.item_id for entry in self._monitor.scan(INVENTORY_BAGS)
                if entry.is_salvage_kit and self._bags.allows(entry.bag, entry.slot)
            }
            if salvage_kit_id not in allowed_kit_ids:
                self._action_status = "The selected salvage kit is outside the configured Bags slots."
                return False
        self._salvage_run = _SalvageRun(targets, salvage_kit_id=salvage_kit_id)
        self._action_status = "Salvage batch queued for %d item(s); choose each native dialog explicitly." % len(targets)
        return True

    def request_confirm_salvage(self) -> bool:
        """Confirm the currently visible native materials dialog only after an explicit UI request."""
        if not _map_is_ready():
            self._action_status = "Salvage confirmation is unavailable until the map is stably valid."
            return False
        if self._salvage_run is None:
            self._action_status = "No System Settings salvage request is active."
            return False
        try:
            from Py4GWCoreLib.Inventory import Inventory

            if not Inventory.IsSalvageChoiceMaterialConfirmVisible():
                self._action_status = "No active materials-salvage confirmation is visible."
                return False
            import PyInventory

            PyInventory.PyInventory().AcceptSalvageWindow()
            self._action_status = "Native materials-salvage confirmation requested."
            return True
        except Exception as exc:
            self._action_status = "Salvage confirmation failed: %s" % exc
            _log(self._action_status, error=True)
            return False

    def request_store_hovered(self) -> bool:
        """Move the hovered inventory item once to a deterministic storage destination."""
        item_id = self.hovered_item_id()
        if item_id <= 0:
            self._action_status = "Hover an inventory item before storing it."
            return False
        return self.request_store(item_id)

    def request_store(self, item_id: int) -> bool:
        """Move one explicit inventory item once to a deterministic storage destination."""
        if not _map_is_ready():
            self._action_status = "Storage is unavailable until the map is stably valid."
            return False
        if self.is_action_active():
            self._action_status = "Another System Settings item operation is already active."
            return False
        try:
            item_id = int(item_id)
            if item_id <= 0 or not self._inventory_contains(item_id):
                self._action_status = "The requested item is not in the current inventory."
                return False
            from Py4GWCoreLib import GLOBAL_CACHE

            if not GLOBAL_CACHE.Inventory.IsStorageOpen():
                self._action_status = "Open Xunlai Vault before storing an item."
                return False
            destination = self._storage_destination(item_id)
            if destination is None:
                self._action_status = "No compatible free storage slot is available."
                return False
            bag_id, slot, quantity = destination
            import PyInventory

            PyInventory.PyInventory().MoveItem(item_id, bag_id, slot, quantity)
            self._action_status = "Native storage move requested for item %d." % item_id
            return True
        except Exception as exc:
            self._action_status = "Storage request failed: %s" % exc
            _log(self._action_status, error=True)
            return False

    def toggle_colorize(self) -> None:
        self._settings.colorize.enabled = not self._settings.colorize.enabled
        self.save_settings()
        _log("Colorize %s from the shared item context menu." %
             ("enabled" if self._settings.colorize.enabled else "disabled"))

    def _request_context_identify(self, item_id: int) -> bool:
        from ..identification.controller import get_controller as get_identification_controller

        controller = get_identification_controller()
        started = controller.request_identify(item_id)
        self._action_status = controller.status()
        return started

    def _request_context_salvage(self, item_id: int, mode: str) -> bool:
        from ..salvage.controller import get_controller as get_salvage_controller

        controller = get_salvage_controller()
        started = controller.request_salvage(item_id, mode)
        self._action_status = controller.status()
        return started

    def _context_item_actions(self, item_id: int) -> _ContextItemActions:
        if not _map_is_ready():
            return _ContextItemActions(0)
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            return _ContextItemActions(0)
        entry = next(
            (candidate for candidate in self._context_monitor.scan(BAGS, force=True) if candidate.item_id == item_id),
            None,
        )
        if entry is None:
            return _ContextItemActions(item_id)
        try:
            from Py4GWCoreLib.Item import Item

            uses = max(0, int(Item.Usage.GetUses(item_id)))
            if entry.is_id_kit:
                return _ContextItemActions(
                    item_id=item_id,
                    kit_label="Identification kit (%d uses remaining)" % uses,
                )
            if entry.is_salvage_kit:
                kit_name = "Salvage kit"
                if Item.Usage.IsLesserKit(item_id):
                    kit_name = "Lesser salvage kit"
                elif Item.Usage.IsPerfectSalvageKit(item_id):
                    kit_name = "Perfect salvage kit"
                elif Item.Usage.IsExpertSalvageKit(item_id):
                    kit_name = "Expert salvage kit"
                return _ContextItemActions(
                    item_id=item_id,
                    kit_label="%s (%d uses remaining)" % (kit_name, uses),
                )
        except Exception:
            return _ContextItemActions(item_id)
        from ..identification.controller import get_controller as get_identification_controller
        from ..salvage.controller import get_controller as get_salvage_controller

        return _ContextItemActions(
            item_id=item_id,
            can_identify=get_identification_controller().can_identify(item_id),
            salvage_modes=get_salvage_controller().available_modes(item_id),
        )

    def draw_context_menu_items(self, prepend_separator: bool = True, item_id: int | None = None) -> bool:
        if not _map_is_ready():
            return False
        import PyImGui

        from Py4GWCoreLib import GLOBAL_CACHE

        settings = self._settings
        target_item_id = self.hovered_item_id() if item_id is None else int(item_id)
        item_actions = (
            self._context_actions
            if self._context_actions is not None and self._context_actions.item_id == target_item_id
            else self._context_item_actions(target_item_id)
        )
        has_item_actions = item_actions.has_items()
        has_utility_actions = settings.context_menu_xunlai or settings.colorize.context_menu_toggle
        if not (has_item_actions or has_utility_actions):
            return False
        if prepend_separator:
            PyImGui.separator()
        if has_item_actions:
            if item_actions.kit_label:
                PyImGui.menu_item(
                    item_actions.kit_label + "##system_items_kit_info", shortcut="", selected=False, enabled=False
                )
            if item_actions.can_identify and PyImGui.begin_menu("Identification##system_items_identification"):
                if PyImGui.menu_item("Identify this item##system_items_identify_item"):
                    self._request_context_identify(target_item_id)
                    PyImGui.close_current_popup()
                PyImGui.end_menu()
            if item_actions.salvage_modes and PyImGui.begin_menu("Salvage##system_items_salvage"):
                if "materials" in item_actions.salvage_modes and PyImGui.menu_item(
                    "For common materials##system_items_salvage_materials"
                ):
                    self._request_context_salvage(target_item_id, "materials")
                    PyImGui.close_current_popup()
                if "rare_materials" in item_actions.salvage_modes and PyImGui.menu_item(
                    "For rare materials##system_items_salvage_rare_materials"
                ):
                    self._request_context_salvage(target_item_id, "rare_materials")
                    PyImGui.close_current_popup()
                if "upgrades" in item_actions.salvage_modes and PyImGui.menu_item(
                    "Extract an upgrade##system_items_salvage_upgrade"
                ):
                    self._request_context_salvage(target_item_id, "upgrades")
                    PyImGui.close_current_popup()
                PyImGui.end_menu()
        if has_item_actions and has_utility_actions:
            PyImGui.separator()
        if settings.context_menu_xunlai and not GLOBAL_CACHE.Inventory.IsStorageOpen():
            if PyImGui.menu_item("Open Xunlai Vault##system_items_xunlai"):
                self.open_xunlai()
                PyImGui.close_current_popup()
        if settings.colorize.context_menu_toggle:
            label = "Disable Colorize" if settings.colorize.enabled else "Enable Colorize"
            if PyImGui.menu_item(label + "##system_items_colorize"):
                self.toggle_colorize()
                PyImGui.close_current_popup()
        return True

    def update(self) -> None:
        self._context_pass()
        self._colorize_pass()
        self._action_pass()

    def _context_pass(self) -> None:
        if not _map_is_ready():
            return
        self._draw_context_menu()

    def _colorize_pass(self) -> None:
        if not _map_is_ready():
            return
        colorize = self._settings.colorize
        slots = self._monitor.scan(BAGS) if colorize.enabled else []
        self._draw_imgui(colorize, slots)
        self._reconcile_native(colorize, slots)
        self._draw_bags_overlay(self._bags)

    def _action_pass(self) -> None:
        if not _map_is_ready():
            self._cancel_actions_for_unstable_map()
            return
        self._process_identify_run()
        self._process_salvage_run()

    def _process_identify_run(self) -> None:
        run = self._identify_run
        if run is None:
            return
        now = time.monotonic()
        lease = get_item_operation_lease()
        if run.active_item_id > 0:
            if not lease.acquire(_IDENTIFY_OPERATION_OWNER):
                self._action_status = "Identify batch is waiting for another item operation to finish."
                return
            try:
                from Py4GWCoreLib.Item import Item

                if Item.Usage.IsIdentified(run.active_item_id):
                    run.identified_count += 1
                    run.active_item_id = 0
                    run.active_started_at = 0.0
                    lease.release(_IDENTIFY_OPERATION_OWNER)
                elif now - run.active_started_at >= _IDENTIFY_TIMEOUT_SECONDS:
                    run.skipped_count += 1
                    run.active_item_id = 0
                    run.active_started_at = 0.0
                    lease.release(_IDENTIFY_OPERATION_OWNER)
            except Exception:
                run.skipped_count += 1
                run.active_item_id = 0
                run.active_started_at = 0.0
                lease.release(_IDENTIFY_OPERATION_OWNER)
            return

        if not run.pending_item_ids:
            lease.release(_IDENTIFY_OPERATION_OWNER)
            self._action_status = "Identify batch completed: %d identified, %d skipped." % (
                run.identified_count,
                run.skipped_count,
            )
            self._identify_run = None
            return

        if not lease.acquire(_IDENTIFY_OPERATION_OWNER):
            self._action_status = "Identify batch is waiting for another item operation to finish."
            return
        item_id = run.pending_item_ids.pop(0)
        keep_lease = False
        try:
            from Py4GWCoreLib.Item import Item

            if not self._is_item_allowed(item_id):
                run.skipped_count += 1
                return
            if Item.Usage.IsIdentified(item_id):
                run.skipped_count += 1
                return
            kit_id = self._first_kit("identify")
            if kit_id <= 0:
                self._action_status = "Identify batch stopped after %d item(s): no usable ID kit." % run.identified_count
                self._identify_run = None
                return
            import PyInventory

            PyInventory.PyInventory().IdentifyItem(kit_id, item_id)
            run.active_item_id = item_id
            run.active_started_at = now
            keep_lease = True
            self._action_status = "Identifying item %d (%d remaining)." % (item_id, len(run.pending_item_ids))
        except Exception as exc:
            run.skipped_count += 1
            self._action_status = "Identify request failed for item %d: %s" % (item_id, exc)
            _log(self._action_status, error=True)
        finally:
            if not keep_lease:
                lease.release(_IDENTIFY_OPERATION_OWNER)

    def _process_salvage_run(self) -> None:
        run = self._salvage_run
        if run is None:
            return
        lease = get_item_operation_lease()
        if run.active_item_id > 0:
            if not lease.acquire(_SALVAGE_OPERATION_OWNER):
                self._action_status = "Salvage batch is waiting for another item operation to finish."
                return
            try:
                from Py4GWCoreLib.Item import Item
                from Py4GWCoreLib.Inventory import Inventory

                current_quantity = int(Item.Properties.GetQuantity(run.active_item_id))
                if not self._inventory_contains(run.active_item_id) or current_quantity < run.active_quantity:
                    run.salvaged_count += 1
                    run.active_item_id = 0
                    run.active_quantity = 0
                    lease.release(_SALVAGE_OPERATION_OWNER)
                elif Inventory.IsSalvageChoiceMaterialConfirmVisible():
                    self._action_status = "Materials-salvage confirmation is waiting for explicit approval."
            except Exception:
                run.salvaged_count += 1
                run.active_item_id = 0
                run.active_quantity = 0
                lease.release(_SALVAGE_OPERATION_OWNER)
            return

        if not run.pending_item_ids:
            lease.release(_SALVAGE_OPERATION_OWNER)
            self._action_status = "Salvage batch completed: %d completed, %d skipped." % (
                run.salvaged_count,
                run.skipped_count,
            )
            self._salvage_run = None
            return

        if not lease.acquire(_SALVAGE_OPERATION_OWNER):
            self._action_status = "Salvage batch is waiting for another item operation to finish."
            return
        item_id = run.pending_item_ids.pop(0)
        keep_lease = False
        try:
            from Py4GWCoreLib.Item import Item

            if not self._is_item_allowed(item_id) or not Item.Usage.IsSalvageable(item_id):
                run.skipped_count += 1
                return
            kit_id = run.salvage_kit_id or self._first_kit("salvage")
            if kit_id <= 0 or not self._inventory_contains(kit_id) or not Item.Usage.IsSalvageKit(kit_id):
                self._action_status = "Salvage batch stopped after %d item(s): no usable salvage kit." % run.salvaged_count
                self._salvage_run = None
                return
            run.active_quantity = int(Item.Properties.GetQuantity(item_id))
            from Py4GWCoreLib.routines_src.behaviourtrees_src.items import enqueue_salvage_request

            if not enqueue_salvage_request(kit_id, item_id):
                raise RuntimeError("the salvage request could not be queued on the GW game thread")
            run.active_item_id = item_id
            keep_lease = True
            self._action_status = "Native salvage requested for item %d (%d remaining)." % (
                item_id,
                len(run.pending_item_ids),
            )
        except Exception as exc:
            run.skipped_count += 1
            self._action_status = "Salvage request failed for item %d: %s" % (item_id, exc)
            _log(self._action_status, error=True)
        finally:
            if not keep_lease:
                lease.release(_SALVAGE_OPERATION_OWNER)

    def _first_kit(self, kind: str) -> int:
        if not _map_is_ready():
            return 0
        if kind == "identify":
            from ..identification.controller import get_controller as get_identification_controller

            preferred_kit_id = get_identification_controller().preferred_kit_id()
            if preferred_kit_id > 0:
                return preferred_kit_id
        candidates: list[tuple[int, int]] = []
        for entry in self._monitor.scan(INVENTORY_BAGS):
            if not self._bags.allows(entry.bag, entry.slot):
                continue
            if (kind == "identify" and not entry.is_id_kit) or (kind == "salvage" and not entry.is_salvage_kit):
                continue
            try:
                from Py4GWCoreLib.Item import Item

                uses = int(Item.Usage.GetUses(entry.item_id))
            except Exception:
                continue
            if uses > 0:
                candidates.append((uses, entry.item_id))
        return min(candidates)[1] if candidates else 0

    def _inventory_contains(self, item_id: int) -> bool:
        if not _map_is_ready():
            return False
        return any(entry.item_id == item_id for entry in self._monitor.scan(BAGS))

    def _is_item_allowed(self, item_id: int) -> bool:
        """Whether an explicit legacy-batch target still belongs to the shared Bags scope."""
        if not _map_is_ready():
            return False
        return any(
            entry.item_id == item_id
            and not entry.is_id_kit
            and not entry.is_salvage_kit
            and self._bags.allows(entry.bag, entry.slot)
            for entry in self._monitor.scan(BAGS)
        )

    @staticmethod
    def _entry_value(entry: object, name: str, fallback: int = 0) -> int:
        try:
            value = entry.get(name, fallback) if isinstance(entry, dict) else getattr(entry, name, fallback)
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _storage_destination(self, item_id: int) -> tuple[int, int, int] | None:
        """Find one current storage target; multi-step storage policy belongs to later rules."""
        if not _map_is_ready():
            return None
        import PyInventory

        from Py4GWCoreLib.Item import Item
        from Py4GWCoreLib.enums_src.Item_enums import MAX_STACK_SIZE, STORAGE_BAGS

        model_id = int(Item.GetModelID(item_id))
        quantity = int(Item.Properties.GetQuantity(item_id))
        if quantity <= 0:
            return None
        is_stackable = bool(Item.Properties.IsStackable(item_id))
        bags: list[tuple[int, list[object], int]] = []
        for bag in STORAGE_BAGS:
            bag_instance = PyInventory.Bag(int(bag.value), bag.name)
            bags.append((int(bag.value), list(bag_instance.GetItems() or []), int(bag_instance.GetSize())))
        if is_stackable:
            for bag_id, entries, _size in bags:
                for entry in entries:
                    candidate_id = self._entry_value(entry, "item_id")
                    if candidate_id <= 0 or int(Item.GetModelID(candidate_id)) != model_id:
                        continue
                    candidate_quantity = int(Item.Properties.GetQuantity(candidate_id))
                    if candidate_quantity < MAX_STACK_SIZE:
                        return bag_id, self._entry_value(entry, "slot"), min(quantity, MAX_STACK_SIZE - candidate_quantity)
        for bag_id, entries, size in bags:
            occupied = {self._entry_value(entry, "slot", -1) for entry in entries}
            for slot in range(size):
                if slot not in occupied:
                    return bag_id, slot, min(quantity, MAX_STACK_SIZE) if is_stackable else quantity
        return None

    def _cancel_actions_for_unstable_map(self) -> None:
        """Never resume an item operation whose IDs were captured before a map transition."""
        if self._identify_run is None and self._salvage_run is None:
            return
        self._identify_run = None
        self._salvage_run = None
        lease = get_item_operation_lease()
        lease.release(_IDENTIFY_OPERATION_OWNER)
        lease.release(_SALVAGE_OPERATION_OWNER)
        self._action_status = "Item operation cancelled because the map is no longer stably valid."

    def _draw_context_menu(self) -> None:
        import PyImGui

        from Py4GWCoreLib.FrameTree import Frame, FrameId
        from Py4GWCoreLib.enums_src.IO_enums import MouseButton

        if PyImGui.is_mouse_clicked(MouseButton.Right.value):
            hit = (Frame(FrameId.InventoryBagsWindow).is_mouse_over()
                   or Frame(FrameId.InventoryWindow).is_mouse_over())
            if hit:
                self._context_item_id = self.hovered_item_id()
                self._context_actions = self._context_item_actions(self._context_item_id)
                settings = self._settings
                if (
                    self._context_actions.has_items()
                    or settings.context_menu_xunlai
                    or settings.colorize.context_menu_toggle
                ):
                    PyImGui.open_popup(_CONTEXT_POPUP_ID)
        if PyImGui.begin_popup(_CONTEXT_POPUP_ID):
            self.draw_context_menu_items(prepend_separator=False, item_id=self._context_item_id)
            PyImGui.end_popup()
        else:
            self._context_item_id = 0
            self._context_actions = None

    @staticmethod
    def _color_for(settings: ColorizeSettings, rarity: str) -> tuple[int, int, int, int] | None:
        return settings.colors.get(rarity) if settings.rarities.get(rarity, False) else None

    def _draw_imgui(self, settings: ColorizeSettings, slots) -> None:
        if not settings.enabled or not (settings.imgui_frame or settings.imgui_outline):
            return
        for entry in slots:
            color = self._color_for(settings, entry.rarity)
            if color is None:
                continue
            if settings.imgui_frame:
                for frame in (entry.bag_frame, entry.inventory_frame):
                    if frame is not None:
                        frame.draw(_color(color, 25).to_color())
            if settings.imgui_outline:
                for frame in (entry.bag_frame, entry.inventory_frame):
                    if frame is not None:
                        frame.draw_outline(_color(color, 125).to_color())

    def _draw_bags_overlay(self, settings: BagSettings) -> None:
        """Show the shared bag/slot policy on every visible inventory frame."""
        if not settings.show_slot_overlay:
            return
        try:
            from Py4GWCoreLib.FrameTree import Frame
            from Py4GWCoreLib.UIManager import XunlaiStorageWindow

            allowed_color = _color((75, 190, 100, 255), 150).to_color()
            blocked_color = _color((210, 75, 75, 255), 150).to_color()
            active_storage_bag = XunlaiStorageWindow.GetActiveTabBag() \
                if XunlaiStorageWindow.IsOpen() else None
            for bag in BAGS:
                if bag in STORAGE_BAGS or bag == Bags.MaterialStorage:
                    if bag != active_storage_bag:
                        continue
                size = self._bag_size(bag)
                for slot in range(size):
                    color = allowed_color if settings.allows(bag, slot) else blocked_color
                    frames = []
                    if bag in {Bags.Backpack, Bags.BeltPouch, Bags.Bag1, Bags.Bag2, Bags.EquipmentPack}:
                        frames.append(Frame.bag_slot(bag, slot))
                    if bag in {Bags.Backpack, Bags.BeltPouch, Bags.Bag1, Bags.Bag2, Bags.EquipmentPack}:
                        frames.append(Frame.inventory_bag_slot(bag, slot))
                    elif bag == Bags.MaterialStorage:
                        frames.append(Frame.material_slot(
                            slot, max_tabs=14, raw_slot=True))
                    elif bag.value >= Bags.Storage1.value and bag.value <= Bags.Storage14.value:
                        frames.append(Frame.storage_slot(bag, slot))
                    for frame in frames:
                        if frame is not None and frame.is_usable:
                            frame.draw_outline(color)
        except Exception:
            # The overlay is diagnostic UI. It must never interrupt colorize or item actions when
            # the game has not created one of the optional storage/inventory frame trees yet.
            return

    @staticmethod
    def _bag_size(bag: Bags) -> int:
        size = int(MAX_BAG_SIZES.get(bag, 0))
        if size:
            return size
        try:
            import PyInventory

            return max(0, int(PyInventory.Bag(int(bag.value), bag.name).GetSize()))
        except Exception:
            return 0

    def _reconcile_native(self, settings: ColorizeSettings, slots) -> None:
        desired: dict[int, int] = {}
        if settings.enabled and settings.native_frame:
            for entry in slots:
                color = self._color_for(settings, entry.rarity)
                if color is None:
                    continue
                for frame in (entry.bag_frame, entry.inventory_frame):
                    if frame is not None:
                        desired[int(frame.frame_id)] = _color(color).to_dx_color()
        try:
            import PyUIManager

            for frame_id in set(self._native_tints) - set(desired):
                PyUIManager.UIManager.clear_item_frame_tint_by_frame_id(frame_id)
            for frame_id, color in desired.items():
                if self._native_tints.get(frame_id) != color:
                    PyUIManager.UIManager.set_item_frame_tint_by_frame_id(frame_id, color)
            self._native_tints = desired
        except Exception as exc:
            if desired:
                _log("Native Colorize unavailable: %s" % exc, error=True)
        if settings.native_outline and not self._native_outline_warned:
            self._native_outline_warned = True
            _log("Native outline Colorize is not exposed by the current native UI owner; no native outline was applied.")


_controller: Optional[InventorySettingsController] = None


def get_controller() -> InventorySettingsController:
    global _controller
    if _controller is None:
        _controller = InventorySettingsController()
    return _controller
