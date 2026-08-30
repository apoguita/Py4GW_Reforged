from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import time

import PySystem
import PyImGui

from Py4GWCoreLib import Agent, AgentArray, GLOBAL_CACHE, Inventory, Map, Player, Routines, SharedCommandType
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.Listeners import Listeners
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.enums_src.Player_enums import PlayerStatus
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import (
    CONSET_UPKEEPS,
    CONSUMABLE_UPKEEPS as ALL_CONSUMABLE_UPKEEPS,
)
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Widgets.System.Messaging import get_inventory_count, reset_inventory_count, get_inventory_state, reset_inventory_state

TEXTURE = os.path.join(PySystem.Console.get_projects_path(), 'Assets', 'Textures', 'Module_Icons', 'forsaken.png')
MODULE_ICON = "Assets\\Textures\\Module_Icons\\forsaken.png"
MODULE_NAME = 'Tunnels of the Forsaken BT'
INI_PATH = 'Widgets/Automation/Bots/Missions/Dungeons/Tunnels Of The Forsaken BT'
INI_FILENAME = 'Tunnels_Of_The_Forsaken_BT.ini'

START_OUTPOST = 40  # Default/legacy start; 6-men mode selects Yak's Bend at runtime.
SURFACE_MAPS = (99, 103, 13, 102)
DUNGEON_MAPS = (880, 881, 882)
QUEST_ID = 0x5B5
GREAT_TEMPLE_OF_BALTHAZAR = 248
ETERNAL_BLADE_MODEL_ID = 1045

SUMMON_MODEL_IDS = (37810, 30209, 31155)
PCON_UPKEEPS = tuple(
    int(model_id)
    for model_id in ALL_CONSUMABLE_UPKEEPS
    if int(model_id) not in CONSET_UPKEEPS
)
CONSET_RESTOCK_ITEMS = tuple((int(model_id), 10) for model_id in CONSET_UPKEEPS)
PCON_RESTOCK_ITEMS = tuple((int(model_id), 10) for model_id in PCON_UPKEEPS)
SUMMON_RESTOCK_ITEMS = tuple((int(model_id), 10) for model_id in SUMMON_MODEL_IDS)

INVENTORY_BAG_IDS = frozenset((1, 2, 3, 4))
ID_KIT_MODEL_IDS = (int(ModelID.Superior_Identification_Kit.value),)
SALVAGE_KIT_MODEL_IDS = (int(ModelID.Superior_Salvage_Kit.value),)
MERCHANT_RULES_WIDGET_NAME = "MerchantRules"
INVENTORY_PLUS_WIDGET_NAME = "InventoryPlus"

# Preferred non-Europe districts for multibox start travel, in fallback order.
# China/Japan intentionally use English (0), matching Map.TravelToDistrict().
START_TRAVEL_PREFERENCES: tuple[tuple[str, int, int, int], ...] = (
    ("International", -2, 1, 0),
    ("Chinese", 3, 1, 0),
    ("Japanese", 4, 1, 0),
)
INVENTORY_MAINTENANCE_RETRY_COUNT = 2
INVENTORY_SNAPSHOT_SETTLE_MS = 2_000
INVENTORY_TRAVEL_TIMEOUT_MS = 60_000
INVENTORY_MERCHANT_TIMEOUT_MS = 240_000
_INVENTORY_QUERY_TIMEOUT_MS = 10_000
_INVENTORY_QUERY_POLL_MS = 200

_SETTINGS_SECTION = "Settings"
_STATS_SECTION = "Statistics"
_ETERNAL_BLADE_DROPS_SECTION = "Eternal Blade Drops"
_ETERNAL_BLADE_SNAPSHOT_SECTION = "Eternal Blade Snapshot"
_ETERNAL_BLADE_RUN_SECTION = "Eternal Blade Run"
_CHAR_NAMES_SECTION = "Character Names"
_settings = Settings(f"{INI_PATH}/{INI_FILENAME}", "global")
_settings_loaded = False
_statistics_loaded = False

_use_hard_mode = True
_six_men = False
_restock_conset = True
_activate_conset = True
_restock_pcons = True
_activate_pcons = True
_use_summoning_stone = True
_auto_loot = True
_inventory_maintenance_enabled = True
_inventory_min_free_slots = 5
_inventory_min_id_kits = 1
_inventory_min_salvage_kits = 2

_runtime_consumables_enabled = True
_runtime_looting_enabled = True
_configured_consumable_upkeeps: tuple[int, ...] | None = None
_inventory_status_snapshot: dict[str, dict[str, object]] = {}

# Persistent statistics.
_total_runs = 0
_total_run_time = 0.0
_fastest_run = float("inf")
_slowest_run = 0.0
_l1_total_time = 0.0
_l1_fastest = float("inf")
_l1_slowest = 0.0
_l2_total_time = 0.0
_l2_fastest = float("inf")
_l2_slowest = 0.0
_l3_total_time = 0.0
_l3_fastest = float("inf")
_l3_slowest = 0.0
_surface_runs = 0
_surface_total_time = 0.0
_surface_fastest = float("inf")
_surface_slowest = 0.0
_eternal_blade_drops: dict[str, int] = {}
_char_names: dict[str, str] = {}

# Session-only statistics.
_session_runs = 0
_session_eternal_blades: dict[str, int] = {}
_scramble_accounts = False
_statistics_reset_pending = False

# Active and most recently completed timings.
_t_run_start = 0.0
_t_l2_start = 0.0
_t_l3_start = 0.0
_t_surface_start = 0.0
_current_run_time = 0.0
_current_l1_time = 0.0
_current_l2_time = 0.0
_current_l3_time = 0.0
_current_surface_time = 0.0

# Elemental Keystone bundle handling.  The policy is resolved before the
# Keystone is picked up because carrying a bundle can hide the equipped
# weapon type reported by the game.
_drop_keystone_for_combat: bool | None = None
_keystone_dropped_for_combat = False

initialized = False
botting_tree: BottingTree | None = None


def _load_settings() -> None:
    global _settings_loaded
    global _use_hard_mode, _six_men, _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons, _use_summoning_stone, _auto_loot
    global _inventory_maintenance_enabled, _inventory_min_free_slots
    global _inventory_min_id_kits, _inventory_min_salvage_kits
    global _runtime_looting_enabled

    if _settings_loaded:
        _load_statistics()
        return

    _use_hard_mode = _settings.get_bool(_SETTINGS_SECTION, "HardMode", True)
    _six_men = _settings.get_bool(_SETTINGS_SECTION, "SixMen", False)
    _restock_conset = _settings.get_bool(_SETTINGS_SECTION, "RestockConset", True)
    _activate_conset = _settings.get_bool(_SETTINGS_SECTION, "ActivateConset", True)
    _restock_pcons = _settings.get_bool(_SETTINGS_SECTION, "RestockPcons", True)
    _activate_pcons = _settings.get_bool(_SETTINGS_SECTION, "ActivatePcons", True)
    _use_summoning_stone = _settings.get_bool(_SETTINGS_SECTION, "UseSummoningStone", True)
    _auto_loot = _settings.get_bool(_SETTINGS_SECTION, "AutoLoot", True)
    _runtime_looting_enabled = _auto_loot
    _inventory_maintenance_enabled = _settings.get_bool(_SETTINGS_SECTION, "InventoryMaintenanceEnabled", True)
    _inventory_min_free_slots = max(0, _settings.get_int(_SETTINGS_SECTION, "InventoryMinFreeSlots", 5))
    _inventory_min_id_kits = max(0, _settings.get_int(_SETTINGS_SECTION, "InventoryMinIdKits", 1))
    _inventory_min_salvage_kits = max(0, _settings.get_int(_SETTINGS_SECTION, "InventoryMinSalvageKits", 2))

    _settings_loaded = True
    _load_statistics()


def _save_settings() -> None:
    _settings.set(_SETTINGS_SECTION, "HardMode", _use_hard_mode)
    _settings.set(_SETTINGS_SECTION, "SixMen", _six_men)
    _settings.set(_SETTINGS_SECTION, "RestockConset", _restock_conset)
    _settings.set(_SETTINGS_SECTION, "ActivateConset", _activate_conset)
    _settings.set(_SETTINGS_SECTION, "RestockPcons", _restock_pcons)
    _settings.set(_SETTINGS_SECTION, "ActivatePcons", _activate_pcons)
    _settings.set(_SETTINGS_SECTION, "UseSummoningStone", _use_summoning_stone)
    _settings.set(_SETTINGS_SECTION, "AutoLoot", _auto_loot)
    _settings.set(_SETTINGS_SECTION, "InventoryMaintenanceEnabled", _inventory_maintenance_enabled)
    _settings.set(_SETTINGS_SECTION, "InventoryMinFreeSlots", _inventory_min_free_slots)
    _settings.set(_SETTINGS_SECTION, "InventoryMinIdKits", _inventory_min_id_kits)
    _settings.set(_SETTINGS_SECTION, "InventoryMinSalvageKits", _inventory_min_salvage_kits)


def _account_key(email: str) -> str:
    return str(email).replace("@", "_at_").replace(".", "_")


def _display_email(key: str) -> str:
    return str(key).replace("_at_", "@").replace("_", ".")


def _known_account_keys() -> list[str]:
    return sorted(
        key
        for key in (set(_eternal_blade_drops) | set(_session_eternal_blades))
        if key and key != "local"
    )


def _account_label(key: str) -> str:
    if not _scramble_accounts:
        return _char_names.get(key) or _display_email(key)

    keys = _known_account_keys()
    index = keys.index(key) + 1 if key in keys else 0
    return f"Player {index}"


def _statistics_accounts() -> list[object]:
    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False, include_isolated=True)
    except TypeError:
        try:
            accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False)
        except TypeError:
            accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception:
        accounts = []

    unique: list[object] = []
    seen: set[str] = set()
    for account in accounts or []:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        unique.append(account)
    return unique


def _refresh_character_names() -> bool:
    changed = False

    local_email = str(Player.GetAccountEmail() or "").strip()
    local_name = str(Player.GetName() or "").strip()
    if local_email and local_name:
        key = _account_key(local_email)
        if _char_names.get(key) != local_name:
            _char_names[key] = local_name
            changed = True

    for account in _statistics_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        agent_data = getattr(account, "AgentData", None)
        character_name = str(getattr(agent_data, "CharacterName", "") or "").strip()
        if not email or not character_name:
            continue

        key = _account_key(email)
        if _char_names.get(key) != character_name:
            _char_names[key] = character_name
            changed = True

    return changed


def _load_statistics() -> None:
    global _statistics_loaded
    global _total_runs, _total_run_time, _fastest_run, _slowest_run
    global _l1_total_time, _l1_fastest, _l1_slowest
    global _l2_total_time, _l2_fastest, _l2_slowest
    global _l3_total_time, _l3_fastest, _l3_slowest
    global _surface_runs, _surface_total_time, _surface_fastest, _surface_slowest

    if _statistics_loaded:
        return

    _total_runs = _settings.get_int(_STATS_SECTION, "total_runs", 0)
    _total_run_time = _settings.get_float(_STATS_SECTION, "total_run_time", 0.0)
    fastest = _settings.get_float(_STATS_SECTION, "fastest_run", 0.0)
    _fastest_run = float("inf") if fastest <= 0.0 else fastest
    _slowest_run = _settings.get_float(_STATS_SECTION, "slowest_run", 0.0)

    _l1_total_time = _settings.get_float(_STATS_SECTION, "l1_total_time", 0.0)
    fastest = _settings.get_float(_STATS_SECTION, "l1_fastest", 0.0)
    _l1_fastest = float("inf") if fastest <= 0.0 else fastest
    _l1_slowest = _settings.get_float(_STATS_SECTION, "l1_slowest", 0.0)

    _l2_total_time = _settings.get_float(_STATS_SECTION, "l2_total_time", 0.0)
    fastest = _settings.get_float(_STATS_SECTION, "l2_fastest", 0.0)
    _l2_fastest = float("inf") if fastest <= 0.0 else fastest
    _l2_slowest = _settings.get_float(_STATS_SECTION, "l2_slowest", 0.0)

    _l3_total_time = _settings.get_float(_STATS_SECTION, "l3_total_time", 0.0)
    fastest = _settings.get_float(_STATS_SECTION, "l3_fastest", 0.0)
    _l3_fastest = float("inf") if fastest <= 0.0 else fastest
    _l3_slowest = _settings.get_float(_STATS_SECTION, "l3_slowest", 0.0)

    _surface_runs = _settings.get_int(_STATS_SECTION, "surface_runs", 0)
    _surface_total_time = _settings.get_float(_STATS_SECTION, "surface_total_time", 0.0)
    fastest = _settings.get_float(_STATS_SECTION, "surface_fastest", 0.0)
    _surface_fastest = float("inf") if fastest <= 0.0 else fastest
    _surface_slowest = _settings.get_float(_STATS_SECTION, "surface_slowest", 0.0)

    for key in _settings.items(_ETERNAL_BLADE_DROPS_SECTION).keys():
        if key and key != "local":
            _eternal_blade_drops[key] = _settings.get_int(_ETERNAL_BLADE_DROPS_SECTION, key, 0)

    for seed_section in (_ETERNAL_BLADE_SNAPSHOT_SECTION, _ETERNAL_BLADE_RUN_SECTION):
        for key in _settings.items(seed_section).keys():
            if key and key != "local":
                _eternal_blade_drops.setdefault(key, 0)

    for key in _settings.items(_CHAR_NAMES_SECTION).keys():
        if key and key != "local":
            name = str(_settings.get_str(_CHAR_NAMES_SECTION, key, "") or "").strip()
            if name:
                _char_names[key] = name

    _statistics_loaded = True


def _save_statistics() -> None:
    _settings.set(_STATS_SECTION, "total_runs", _total_runs)
    _settings.set(_STATS_SECTION, "total_run_time", _total_run_time)
    _settings.set(_STATS_SECTION, "fastest_run", 0.0 if _fastest_run == float("inf") else _fastest_run)
    _settings.set(_STATS_SECTION, "slowest_run", _slowest_run)

    for floor, total, fastest, slowest in (
        ("l1", _l1_total_time, _l1_fastest, _l1_slowest),
        ("l2", _l2_total_time, _l2_fastest, _l2_slowest),
        ("l3", _l3_total_time, _l3_fastest, _l3_slowest),
    ):
        _settings.set(_STATS_SECTION, f"{floor}_total_time", total)
        _settings.set(_STATS_SECTION, f"{floor}_fastest", 0.0 if fastest == float("inf") else fastest)
        _settings.set(_STATS_SECTION, f"{floor}_slowest", slowest)

    _settings.set(_STATS_SECTION, "surface_runs", _surface_runs)
    _settings.set(_STATS_SECTION, "surface_total_time", _surface_total_time)
    _settings.set(_STATS_SECTION, "surface_fastest", 0.0 if _surface_fastest == float("inf") else _surface_fastest)
    _settings.set(_STATS_SECTION, "surface_slowest", _surface_slowest)

    for key, total in _eternal_blade_drops.items():
        if key and key != "local":
            _settings.set(_ETERNAL_BLADE_DROPS_SECTION, key, total)

    for key, name in _char_names.items():
        if key and key != "local":
            _settings.set(_CHAR_NAMES_SECTION, key, name)


def _statistics_action_node(name: str, action: Callable[[], None]) -> BehaviorTree:
    def _run(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            action()
        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] {name} failed: {exc}",
                PySystem.Console.MessageType.Warning,
            )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name=name, action_fn=_run, aftercast_ms=0))


def _mark_surface_start_node() -> BehaviorTree:
    """Start the 6-man surface timer after Yak's Bend has been exited."""
    def _mark() -> None:
        global _t_surface_start, _current_surface_time
        _t_surface_start = time.monotonic()
        _current_surface_time = 0.0
        PySystem.Console.Log(
            MODULE_NAME,
            "[Statistics] Yak's Bend -> Tunnels timer started.",
            PySystem.Console.MessageType.Info,
        )

    return _statistics_action_node("Mark Yak To Tunnels Start", _mark)


def _record_surface_end_node() -> BehaviorTree:
    """Stop and store the 6-man surface timer once Tunnels level 1 is loaded."""
    def _record() -> None:
        global _t_surface_start, _current_surface_time
        global _surface_runs, _surface_total_time, _surface_fastest, _surface_slowest

        if _t_surface_start <= 0.0:
            return

        elapsed = max(0.0, time.monotonic() - _t_surface_start)
        _current_surface_time = elapsed
        _t_surface_start = 0.0
        _surface_runs += 1
        _surface_total_time += elapsed
        _surface_fastest = min(_surface_fastest, elapsed)
        _surface_slowest = max(_surface_slowest, elapsed)
        _save_statistics()
        PySystem.Console.Log(
            MODULE_NAME,
            f"[Statistics] Yak's Bend -> Tunnels: {elapsed:.0f}s",
            PySystem.Console.MessageType.Success,
        )

    return _statistics_action_node("Record Yak To Tunnels Time", _record)


def _mark_run_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_run_start, _t_l2_start, _t_l3_start
        global _current_run_time, _current_l1_time, _current_l2_time, _current_l3_time

        _t_run_start = time.monotonic()
        _t_l2_start = 0.0
        _t_l3_start = 0.0
        _current_run_time = 0.0
        _current_l1_time = 0.0
        _current_l2_time = 0.0
        _current_l3_time = 0.0

    return _statistics_action_node("Mark Run Start", _mark)


def _mark_l2_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_l2_start, _current_l1_time
        now = time.monotonic()
        _t_l2_start = now
        _current_l1_time = now - _t_run_start if _t_run_start > 0.0 else 0.0

    return _statistics_action_node("Mark Level 2 Start", _mark)


def _mark_l3_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_l3_start, _current_l2_time
        now = time.monotonic()
        _t_l3_start = now
        _current_l2_time = now - _t_l2_start if _t_l2_start > 0.0 else 0.0

    return _statistics_action_node("Mark Level 3 Start", _mark)


def _record_run_end_node() -> BehaviorTree:
    def _record() -> None:
        global _total_runs, _session_runs
        global _total_run_time, _fastest_run, _slowest_run
        global _l1_total_time, _l1_fastest, _l1_slowest
        global _l2_total_time, _l2_fastest, _l2_slowest
        global _l3_total_time, _l3_fastest, _l3_slowest
        global _current_run_time, _current_l1_time, _current_l2_time, _current_l3_time
        global _t_run_start, _t_l2_start, _t_l3_start

        now = time.monotonic()
        timings_valid = (
            _t_run_start > 0.0
            and _t_l2_start > _t_run_start
            and _t_l3_start > _t_l2_start
        )

        if timings_valid:
            run_time = now - _t_run_start
            l1_time = _t_l2_start - _t_run_start
            l2_time = _t_l3_start - _t_l2_start
            l3_time = now - _t_l3_start

            _current_run_time = run_time
            _current_l1_time = l1_time
            _current_l2_time = l2_time
            _current_l3_time = l3_time

            _total_run_time += run_time
            _fastest_run = min(_fastest_run, run_time)
            _slowest_run = max(_slowest_run, run_time)

            _l1_total_time += l1_time
            _l1_fastest = min(_l1_fastest, l1_time)
            _l1_slowest = max(_l1_slowest, l1_time)

            _l2_total_time += l2_time
            _l2_fastest = min(_l2_fastest, l2_time)
            _l2_slowest = max(_l2_slowest, l2_time)

            _l3_total_time += l3_time
            _l3_fastest = min(_l3_fastest, l3_time)
            _l3_slowest = max(_l3_slowest, l3_time)

            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] Run complete - Total {run_time:.0f}s | L1 {l1_time:.0f}s | L2 {l2_time:.0f}s | L3 {l3_time:.0f}s",
                PySystem.Console.MessageType.Success,
            )

        _total_runs += 1
        _session_runs += 1
        _t_run_start = 0.0
        _t_l2_start = 0.0
        _t_l3_start = 0.0
        _save_statistics()

    return _statistics_action_node("Record Successful Run", _record)


def _accumulate_eternal_blade_drop(account_key: str, count: int) -> None:
    _eternal_blade_drops.setdefault(account_key, 0)
    if count <= 0:
        return
    _eternal_blade_drops[account_key] += int(count)
    _session_eternal_blades[account_key] = _session_eternal_blades.get(account_key, 0) + int(count)


def _local_eternal_blade_count() -> int:
    return int(GLOBAL_CACHE.Inventory.GetModelCount(ETERNAL_BLADE_MODEL_ID))


def _shared_eternal_blade_count(account: object) -> int | None:
    """Read the mirrored Eternal Blade count for one shared-memory account.

    InventoryQuery remains available as a fallback, but the normal statistics
    path should not depend on every remote client processing a request in time.
    """
    inventory_bags = getattr(account, "InventoryBags", None)
    if inventory_bags is None:
        return None

    try:
        bags = list(inventory_bags.iter_bags())
    except Exception:
        return None

    # An account whose inventory mirror has not been published yet normally has
    # no bags at all.  Once the bag structures exist, an empty inventory is a
    # valid count of zero.
    if not bags:
        return None

    total = 0
    saw_slots_container = False
    try:
        for bag in bags:
            slots = getattr(bag, "Slots", None)
            if slots is None:
                continue
            saw_slots_container = True
            for slot in slots:
                model_id = int(getattr(slot, "ModelID", 0) or 0)
                if model_id != int(ETERNAL_BLADE_MODEL_ID):
                    continue
                total += max(0, int(getattr(slot, "Quantity", 0) or 0))
    except Exception:
        return None

    return total if saw_slots_container else None


def _inventory_statistics_node(*, after_chest: bool) -> BehaviorTree:
    node_name = "Record Eternal Blade After Final Chest" if after_chest else "Snapshot Eternal Blades At Dungeon Entry"
    state: dict[str, object] = {
        "started": False,
        "local_email": "",
        "account_keys": [],
        "pending": {},
        "request_started_at": 0.0,
        "local_email_wait_started_at": 0.0,
        "mirror_count": 0,
    }

    def _reset() -> None:
        state.update(
            started=False,
            local_email="",
            account_keys=[],
            pending={},
            request_started_at=0.0,
            local_email_wait_started_at=0.0,
            mirror_count=0,
        )

    def _start() -> bool:
        _load_statistics()
        _refresh_character_names()

        local_email = str(Player.GetAccountEmail() or "").strip()
        if not local_email:
            return False

        local_key = _account_key(local_email)
        section = _ETERNAL_BLADE_RUN_SECTION if after_chest else _ETERNAL_BLADE_SNAPSHOT_SECTION
        _settings.set(section, local_key, _local_eternal_blade_count())

        account_keys = [local_key]
        pending: dict[str, dict[str, str]] = {}
        mirror_count = 0

        for account in _statistics_accounts():
            email = str(getattr(account, "AccountEmail", "") or "").strip()
            if not email or email == local_email:
                continue

            key = _account_key(email)
            if key not in account_keys:
                account_keys.append(key)

            mirrored_count = _shared_eternal_blade_count(account)
            if mirrored_count is not None:
                _settings.set(section, key, int(mirrored_count))
                mirror_count += 1
                continue

            # Mirror unavailable: keep the existing InventoryQuery protocol as a
            # fallback, but launch every remote request together so the timeout is
            # global rather than 10 seconds per account.
            reset_inventory_count(email, ETERNAL_BLADE_MODEL_ID, ETERNAL_BLADE_MODEL_ID)
            _settings.set(section, key, -1)
            GLOBAL_CACHE.ShMem.SendMessage(
                local_email,
                email,
                SharedCommandType.InventoryQuery,
                (float(ETERNAL_BLADE_MODEL_ID), float(ETERNAL_BLADE_MODEL_ID), 0.0, 0.0),
                ("report_inventory_count",),
            )
            pending[email] = {"email": email, "key": key, "section": section}

        for key in account_keys:
            _eternal_blade_drops.setdefault(key, 0)

        state["started"] = True
        state["local_email"] = local_email
        state["account_keys"] = account_keys
        state["pending"] = pending
        state["mirror_count"] = mirror_count
        state["request_started_at"] = time.monotonic() if pending else 0.0
        state["local_email_wait_started_at"] = 0.0

        if pending:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] Eternal Blade snapshot: {mirror_count} remote account(s) read from shared inventory; {len(pending)} IPC fallback request(s) sent in parallel.",
                PySystem.Console.MessageType.Info,
            )
        return True

    def _finish() -> None:
        if not after_chest:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] Dungeon-entry Eternal Blade snapshot completed for {len(state['account_keys'])} account(s).",
                PySystem.Console.MessageType.Info,
            )
            _save_statistics()
            return

        total_drops = 0
        for key in state["account_keys"]:
            account_key = str(key)
            before = _settings.get_int(_ETERNAL_BLADE_SNAPSHOT_SECTION, account_key, -1)
            after = _settings.get_int(_ETERNAL_BLADE_RUN_SECTION, account_key, -1)
            delta = max(0, after - before) if before >= 0 and after >= 0 else 0
            _accumulate_eternal_blade_drop(account_key, delta)
            total_drops += delta

        _save_statistics()
        PySystem.Console.Log(
            MODULE_NAME,
            f"[Statistics] Final chest recorded - Eternal Blade {total_drops}",
            PySystem.Console.MessageType.Success,
        )

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if bool(node.blackboard.get("USER_INTERRUPT_ACTIVE", False)):
                _reset()
                return BehaviorTree.NodeState.FAILURE

            if not bool(state["started"]):
                if not _start():
                    now = time.monotonic()
                    wait_started = float(state["local_email_wait_started_at"] or 0.0)
                    if wait_started <= 0.0:
                        state["local_email_wait_started_at"] = now
                        return BehaviorTree.NodeState.RUNNING
                    if (now - wait_started) * 1000.0 < _INVENTORY_QUERY_TIMEOUT_MS:
                        return BehaviorTree.NodeState.RUNNING

                    PySystem.Console.Log(
                        MODULE_NAME,
                        "[Statistics] Local account email unavailable; skipping this statistics snapshot.",
                        PySystem.Console.MessageType.Warning,
                    )
                    _reset()
                    return BehaviorTree.NodeState.SUCCESS

            pending: dict[str, dict[str, str]] = state["pending"]
            for email in list(pending):
                request = pending[email]
                count = int(get_inventory_count(email, ETERNAL_BLADE_MODEL_ID, ETERNAL_BLADE_MODEL_ID))
                if count < 0:
                    continue
                _settings.set(str(request["section"]), str(request["key"]), count)
                pending.pop(email, None)

            if pending:
                elapsed_ms = (time.monotonic() - float(state["request_started_at"] or 0.0)) * 1000.0
                if elapsed_ms < _INVENTORY_QUERY_TIMEOUT_MS:
                    return BehaviorTree.NodeState.RUNNING

                for email, request in list(pending.items()):
                    PySystem.Console.Log(
                        MODULE_NAME,
                        f"[Statistics] Eternal Blade inventory fallback timed out on {_account_label(str(request['key']))}.",
                        PySystem.Console.MessageType.Warning,
                    )
                    pending.pop(email, None)

            _finish()
            _reset()
            return BehaviorTree.NodeState.SUCCESS
        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] {node_name} failed: {exc}",
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=node_name,
            action_fn=_tick,
            aftercast_ms=_INVENTORY_QUERY_POLL_MS,
        )
    )

def _reset_total_overview_and_timings() -> None:
    global _total_runs, _total_run_time, _fastest_run, _slowest_run
    global _l1_total_time, _l1_fastest, _l1_slowest
    global _l2_total_time, _l2_fastest, _l2_slowest
    global _l3_total_time, _l3_fastest, _l3_slowest
    global _surface_runs, _surface_total_time, _surface_fastest, _surface_slowest
    global _current_run_time, _current_l1_time, _current_l2_time, _current_l3_time
    global _current_surface_time, _t_surface_start

    _total_runs = 0
    _total_run_time = 0.0
    _fastest_run = float("inf")
    _slowest_run = 0.0
    _l1_total_time = 0.0
    _l1_fastest = float("inf")
    _l1_slowest = 0.0
    _l2_total_time = 0.0
    _l2_fastest = float("inf")
    _l2_slowest = 0.0
    _l3_total_time = 0.0
    _l3_fastest = float("inf")
    _l3_slowest = 0.0
    _surface_runs = 0
    _surface_total_time = 0.0
    _surface_fastest = float("inf")
    _surface_slowest = 0.0

    _current_run_time = 0.0
    _current_l1_time = 0.0
    _current_l2_time = 0.0
    _current_l3_time = 0.0
    _current_surface_time = 0.0
    _t_surface_start = 0.0

    keys = set(_eternal_blade_drops) | set(_settings.items(_ETERNAL_BLADE_DROPS_SECTION).keys())
    for key in keys:
        if not key or key == "local":
            continue
        _eternal_blade_drops[key] = 0
        _settings.set(_ETERNAL_BLADE_DROPS_SECTION, key, 0)

    _save_statistics()
    PySystem.Console.Log(
        MODULE_NAME,
        "[Statistics] Total Overview and Run Timings reset to zero.",
        PySystem.Console.MessageType.Success,
    )


def _consumables_allowed() -> bool:
    return (
        _runtime_consumables_enabled
        and Map.IsMapReady()
        and not Map.IsMapLoading()
        and Map.GetMapID() in DUNGEON_MAPS
    )


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    if not _consumables_allowed():
        return ()
    enabled: list[int] = []
    if _activate_conset:
        enabled.extend(int(model_id) for model_id in CONSET_UPKEEPS)
    if _activate_pcons:
        enabled.extend(int(model_id) for model_id in PCON_UPKEEPS)
    return tuple(dict.fromkeys(enabled))


def _configure_runtime_upkeeps(
    *,
    consumables_enabled: bool | None = None,
    looting_enabled: bool | None = None,
) -> None:
    global _runtime_consumables_enabled, _runtime_looting_enabled
    global _configured_consumable_upkeeps

    if consumables_enabled is not None:
        _runtime_consumables_enabled = bool(consumables_enabled)
    if looting_enabled is not None:
        _runtime_looting_enabled = bool(looting_enabled)

    if botting_tree is None:
        return

    enabled_consumables = _enabled_consumable_upkeeps()
    botting_tree.Config.ConfigureUpkeep(
        looting_enabled=_runtime_looting_enabled,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=enabled_consumables,
        enable_party_wipe_recovery=False,
        heroai_state_logging=False,
    )
    # ConfigureUpkeep rebuilds the service list, so reinstall the Forsaken-specific
    # wipe recovery service every time runtime upkeep configuration changes.
    botting_tree.AddServiceTree(
        "ForsakenPartyWipeRecoveryService",
        ForsakenPartyWipeRecoveryService,
    )
    _configured_consumable_upkeeps = enabled_consumables


def _sync_runtime_upkeeps() -> None:
    if _enabled_consumable_upkeeps() != _configured_consumable_upkeeps:
        _configure_runtime_upkeeps()


def _runtime_consumable_upkeep_node(enabled: bool) -> BehaviorTree:
    def _apply(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        _configure_runtime_upkeeps(consumables_enabled=enabled)
        return BehaviorTree.NodeState.SUCCESS
    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Resume Consumable Upkeep" if enabled else "Suspend Consumable Upkeep",
            action_fn=_apply,
            aftercast_ms=0,
        )
    )


def _runtime_difficulty_node() -> BehaviorTree:
    return BT.Subtree(
        name="Apply Selected Difficulty",
        subtree_fn=lambda _node: BT.SetHardMode(_use_hard_mode, log=True),
    )


def _runtime_restock_node() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        items: list[tuple[int, int]] = []
        if _restock_conset:
            items.extend(CONSET_RESTOCK_ITEMS)
        if _restock_pcons:
            items.extend(PCON_RESTOCK_ITEMS)
        if _use_summoning_stone:
            items.extend(SUMMON_RESTOCK_ITEMS)
        if not items:
            return BT.Succeeder("Restock Disabled")
        return BT.RestockItemsFromList(tuple(items), allow_missing=True)
    return BT.Subtree(name="Restock Selected Supplies", subtree_fn=_build)


def _inventory_accounts() -> list[object]:
    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False)
    except TypeError:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception:
        accounts = []
    unique: list[object] = []
    seen: set[str] = set()
    for account in accounts or []:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        unique.append(account)
    return unique


def _shared_account_label(account: object) -> str:
    agent_data = getattr(account, "AgentData", None)
    character_name = str(getattr(agent_data, "CharacterName", "") or "").strip()
    return character_name or str(getattr(account, "AccountEmail", "") or "Unknown account")


def _inventory_target_accounts() -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for account in _inventory_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if email and email not in seen:
            seen.add(email)
            targets.append((email, _shared_account_label(account)))
    local_email = str(Player.GetAccountEmail() or "").strip()
    if local_email and local_email not in seen:
        targets.append((local_email, str(Player.GetName() or local_email)))
    return targets


def _inventory_recipient_emails() -> list[str]:
    return [email for email, _label in _inventory_target_accounts()]


def _local_inventory_state() -> tuple[int, int, int, int]:
    occupied, capacity = Inventory.GetInventorySpace()
    id_kits = sum(int(GLOBAL_CACHE.Inventory.GetModelCount(mid)) for mid in ID_KIT_MODEL_IDS)
    salvage_kits = sum(int(GLOBAL_CACHE.Inventory.GetModelCount(mid)) for mid in SALVAGE_KIT_MODEL_IDS)
    return int(occupied), int(capacity), int(id_kits), int(salvage_kits)


def _build_inventory_status(
    email: str,
    label: str,
    state: tuple[int, int, int, int] | None,
) -> dict[str, object]:
    if state is None:
        occupied = capacity = id_kits = salvage_kits = -1
    else:
        occupied, capacity, id_kits, salvage_kits = (int(v) for v in state)
    available = capacity > 0 and 0 <= occupied <= capacity
    free_slots = max(0, capacity - occupied) if available else 0
    issues: list[str] = []
    if not available:
        issues.append("inventory query unavailable")
    else:
        if _inventory_min_free_slots > 0 and free_slots < _inventory_min_free_slots:
            issues.append(f"free slots {free_slots}/{_inventory_min_free_slots}")
        if _inventory_min_id_kits > 0 and id_kits < _inventory_min_id_kits:
            issues.append(f"ID kits {id_kits}/{_inventory_min_id_kits}")
        if _inventory_min_salvage_kits > 0 and salvage_kits < _inventory_min_salvage_kits:
            issues.append(f"salvage kits {salvage_kits}/{_inventory_min_salvage_kits}")
    return {
        "email": email,
        "label": label,
        "available": available,
        "occupied": occupied,
        "capacity": capacity,
        "free_slots": free_slots,
        "id_kits": id_kits,
        "salvage_kits": salvage_kits,
        "issues": issues,
    }


def _query_all_inventory_states_node(name: str) -> BehaviorTree:
    state: dict[str, object] = {
        "started": False,
        "request_id": "",
        "pending": {},
        "results": {},
        "started_at": 0.0,
    }

    def _reset() -> None:
        state.update(started=False, request_id="", pending={}, results={}, started_at=0.0)

    def _finish() -> BehaviorTree.NodeState:
        global _inventory_status_snapshot
        _inventory_status_snapshot = dict(state["results"])
        _reset()
        return BehaviorTree.NodeState.SUCCESS

    def _start() -> None:
        request_id = f"{MODULE_NAME}_inventory_{int(time.monotonic() * 1000)}"
        sender_email = str(Player.GetAccountEmail() or "").strip()
        pending: dict[str, str] = {}
        results: dict[str, dict[str, object]] = {}
        for email, label in _inventory_target_accounts():
            if email == sender_email:
                try:
                    local_state = _local_inventory_state()
                except Exception:
                    local_state = None
                results[email] = _build_inventory_status(email, label, local_state)
                continue
            if not sender_email:
                results[email] = _build_inventory_status(email, label, None)
                continue
            reset_inventory_state(email, request_id)
            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                email,
                SharedCommandType.InventoryQuery,
                (
                    float(ID_KIT_MODEL_IDS[0] if ID_KIT_MODEL_IDS else 0),
                    0.0,
                    float(SALVAGE_KIT_MODEL_IDS[0] if SALVAGE_KIT_MODEL_IDS else 0),
                    0.0,
                ),
                ("report_inventory_state", request_id, "", ""),
            )
            pending[email] = label
        state["started"] = True
        state["request_id"] = request_id
        state["pending"] = pending
        state["results"] = results
        state["started_at"] = time.monotonic()

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if bool(node.blackboard.get("USER_INTERRUPT_ACTIVE", False)):
            _reset()
            return BehaviorTree.NodeState.FAILURE
        if not bool(state["started"]):
            _start()
        pending: dict[str, str] = state["pending"]
        request_id = str(state["request_id"])
        for email in list(pending):
            reply = get_inventory_state(email, request_id)
            if reply is None:
                continue
            label = pending.pop(email)
            state["results"][email] = _build_inventory_status(email, label, reply)
        if not pending:
            return _finish()
        if (time.monotonic() - float(state["started_at"])) * 1000.0 < _INVENTORY_QUERY_TIMEOUT_MS:
            return BehaviorTree.NodeState.RUNNING
        for email, label in list(pending.items()):
            state["results"][email] = _build_inventory_status(email, label, None)
        pending.clear()
        return _finish()

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_tick,
            aftercast_ms=_INVENTORY_QUERY_POLL_MS,
        )
    )


def _inventory_is_healthy_node(name: str) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        statuses = list(_inventory_status_snapshot.values())
        if not statuses:
            return BehaviorTree.NodeState.FAILURE
        issues: list[str] = []
        for status in statuses:
            if status["issues"]:
                issues.append(f"{status['label']}: {', '.join(status['issues'])}")
        if issues:
            PySystem.Console.Log(
                MODULE_NAME,
                "[Inventory] Maintenance required - " + "; ".join(issues),
                PySystem.Console.MessageType.Warning,
            )
            return BehaviorTree.NodeState.FAILURE
        return BehaviorTree.NodeState.SUCCESS
    return BehaviorTree(BehaviorTree.ConditionNode(name=name, condition_fn=_check))


def _send_widget_state(widget_name: str, enabled: bool, refs_key: str) -> BehaviorTree:
    return BTShared.SendAndWait(
        command=SharedCommandType.EnableWidget if enabled else SharedCommandType.DisableWidget,
        extra_data=(widget_name, "", "", ""),
        include_self=True,
        refs_blackboard_key=refs_key,
        timeout_ms=20_000,
        poll_interval_ms=100,
        log=True,
    )


def _merchant_stock_request_spec() -> str:
    targets: list[str] = []
    if _inventory_min_id_kits > 0 and ID_KIT_MODEL_IDS:
        targets.append(f"{ID_KIT_MODEL_IDS[0]}:{_inventory_min_id_kits}")
    if _inventory_min_salvage_kits > 0 and SALVAGE_KIT_MODEL_IDS:
        targets.append(f"{SALVAGE_KIT_MODEL_IDS[0]}:{_inventory_min_salvage_kits}")
    return "stock:" + ",".join(targets) if targets else ""


def _run_merchant_rules(attempt_key: str) -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        recipients = _inventory_recipient_emails()
        if not recipients:
            return BehaviorTree(BehaviorTree.FailerNode(name="No MerchantRules Recipients"))
        request_id = f"{MODULE_NAME}_merchant_{attempt_key}_{int(time.monotonic() * 1000)}"
        return BTShared.SendAndWait(
            command=SharedCommandType.MerchantRules,
            params=(3.0, 0.0, 0.0, 0.0),
            extra_data=(request_id, _merchant_stock_request_spec(), "0", "0"),
            recipients=recipients,
            include_self=True,
            refs_blackboard_key=f"{attempt_key}_merchant_refs",
            timeout_ms=INVENTORY_MERCHANT_TIMEOUT_MS,
            poll_interval_ms=250,
            log=True,
        )
    return BT.Subtree(name="Run MerchantRules On All Accounts", subtree_fn=_build)


def _travel_all_accounts(map_id: int, refs_key: str) -> BehaviorTree:
    attempts: list[BehaviorTree] = []
    for label, region, district, language in START_TRAVEL_PREFERENCES:
        attempts.append(
            BT.Sequence(
                name=f"Travel To {label} District",
                children=[
                    BTShared.SendAndWait(
                        command=SharedCommandType.TravelToMap,
                        params=(
                            float(map_id),
                            float(region),
                            float(district),
                            float(language),
                        ),
                        include_self=True,
                        refs_blackboard_key=f"{refs_key}_{label.lower()}",
                        timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
                        poll_interval_ms=250,
                        log=True,
                    )
                ],
            )
        )

    return BT.Selector(
        name="Travel To Preferred Non-Europe District",
        children=attempts,
    )


def InventoryCheckAndMaintenance() -> BehaviorTree:
    disabled = BehaviorTree(
        BehaviorTree.ConditionNode(
            name="Inventory Maintenance Disabled",
            condition_fn=lambda _node: not _inventory_maintenance_enabled,
        )
    )
    attempts: list[BehaviorTree] = []
    for attempt in range(1, INVENTORY_MAINTENANCE_RETRY_COUNT + 1):
        key = f"inventory_attempt_{attempt}"
        attempts.append(
            BT.Sequence(
                name=f"Inventory Maintenance Attempt {attempt}",
                children=[
                    _send_widget_state(INVENTORY_PLUS_WIDGET_NAME, False, f"{key}_inventoryplus_off"),
                    _send_widget_state(MERCHANT_RULES_WIDGET_NAME, True, f"{key}_merchant_on"),
                    _run_merchant_rules(key),
                    _send_widget_state(INVENTORY_PLUS_WIDGET_NAME, True, f"{key}_inventoryplus_on"),
                    BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
                    _query_all_inventory_states_node(f"Refresh Inventory Attempt {attempt}"),
                    _inventory_is_healthy_node(f"Inventory Healthy After Attempt {attempt}"),
                ],
            )
        )

    enabled = BT.Sequence(
        name="Inventory Check And Maintenance",
        children=[
            _query_all_inventory_states_node("Query Inventory On All Accounts"),
            BT.Selector(
                name="Inventory Threshold Decision",
                children=[
                    _inventory_is_healthy_node("Inventory Already Healthy"),
                    BT.Sequence(
                        name="Run MerchantRules Maintenance",
                        children=[
                            BT.LeaveParty(),
                            BT.Selector(name="MerchantRules Attempts", children=attempts),
                        ],
                    ),
                ],
            ),
        ],
    )
    return BT.Selector(name="Optional Inventory Maintenance", children=[disabled, enabled])


def UseAvailableSummoningStone(level_key: str) -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not _use_summoning_stone or not _consumables_allowed():
            return BT.Succeeder("Summoning Stone Disabled")
        recipients = _inventory_recipient_emails()
        if not recipients:
            return BT.Succeeder("No Summoning Stone Recipients")
        return BTShared.SendAndWait(
            command=SharedCommandType.UseSummoningStone,
            recipients=recipients,
            include_self=True,
            refs_blackboard_key=f"{MODULE_NAME}_summon_{level_key}_refs",
            timeout_ms=10_000,
            poll_interval_ms=100,
            log=True,
        )
    return BT.Subtree(name=f"Use Summoning Stone {level_key}", subtree_fn=_build)



def _on_map_or_skip(
    name: str,
    map_id: int,
    child: BehaviorTree,
    skip_if_maps: Sequence[int]=(),
) -> BehaviorTree:
    run_here = BT.Sequence(
        name=f"{name} - Current Map",
        children=[BT.IsCurrentMap(map_id=map_id, log=False), child],
    )
    if not skip_if_maps:
        return run_here
    skip = BT.Sequence(
        name=f"{name} - Already Past",
        children=[
            BT.Selector(
                name=f"{name} - Later Map",
                children=[BT.IsCurrentMap(map_id=int(mid), log=False) for mid in skip_if_maps],
            ),
            BT.Succeeder(f"Skip {name}"),
        ],
    )
    return BT.Selector(name=name, children=[run_here, skip])


def _draw_run_config() -> None:
    global _use_hard_mode, _six_men, _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons, _use_summoning_stone, _auto_loot
    global _inventory_maintenance_enabled, _inventory_min_free_slots
    global _inventory_min_id_kits, _inventory_min_salvage_kits

    _load_settings()
    changed = False
    upkeep_changed = False

    for label, variable_name, affects_upkeep in (
        ("Hard Mode (HM)", "_use_hard_mode", False),
        ("6 men (Start from Yak's Bend)", "_six_men", False),
        ("Restock conset from storage", "_restock_conset", False),
        ("Activate / maintain conset", "_activate_conset", True),
        ("Restock pcons from storage", "_restock_pcons", False),
        ("Activate / maintain pcons", "_activate_pcons", True),
        ("Use summoning stones", "_use_summoning_stone", False),
        ("Auto Loot", "_auto_loot", True),
    ):
        old = bool(globals()[variable_name])
        new = PyImGui.checkbox(label, old)
        if new != old:
            globals()[variable_name] = new
            changed = True
            upkeep_changed = upkeep_changed or affects_upkeep

    PyImGui.separator()
    new = PyImGui.checkbox("Run MerchantRules when inventory is low", _inventory_maintenance_enabled)
    if new != _inventory_maintenance_enabled:
        _inventory_maintenance_enabled = new
        changed = True

    if _inventory_maintenance_enabled:
        value = max(0, int(PyImGui.input_int("Minimum free slots", _inventory_min_free_slots)))
        if value != _inventory_min_free_slots:
            _inventory_min_free_slots = value
            changed = True
        value = max(0, int(PyImGui.input_int("Minimum Superior ID kits", _inventory_min_id_kits)))
        if value != _inventory_min_id_kits:
            _inventory_min_id_kits = value
            changed = True
        value = max(0, int(PyImGui.input_int("Minimum Superior salvage kits", _inventory_min_salvage_kits)))
        if value != _inventory_min_salvage_kits:
            _inventory_min_salvage_kits = value
            changed = True

    if changed:
        _save_settings()
    if upkeep_changed:
        _configure_runtime_upkeeps(looting_enabled=_auto_loot)


def _draw_statistics() -> None:
    from Py4GWCoreLib import Color

    global _scramble_accounts, _statistics_reset_pending

    _load_statistics()
    if _refresh_character_names():
        _save_statistics()

    gold = Color(255, 210, 80, 255).to_tuple_normalized()
    cyan = Color(80, 210, 255, 255).to_tuple_normalized()
    live = Color(100, 180, 255, 255).to_tuple_normalized()

    def _fmt_time(seconds: float) -> str:
        if seconds <= 0.0 or seconds == float("inf"):
            return "--:--"
        minutes, remaining = divmod(int(seconds), 60)
        return f"{minutes:02d}:{remaining:02d}"

    def _avg_time(total: float, count: int | None = None) -> str:
        sample_count = _total_runs if count is None else int(count)
        return _fmt_time(total / sample_count) if sample_count > 0 else "--:--"

    def _drop_rate(runs: int, drops: int) -> str:
        return f"{drops / runs * 100.0:.1f}%" if runs > 0 and drops > 0 else "-"

    table_flags = (
        PyImGui.TableFlags.Borders
        | PyImGui.TableFlags.RowBg
        | PyImGui.TableFlags.SizingFixedFit
        | PyImGui.TableFlags.NoHostExtendX
    )
    header_color = 26 | (38 << 8) | (51 << 16) | (255 << 24)
    column_width = 92.0
    row_height = 22.0

    def _header_row(labels: tuple[str, ...]) -> None:
        PyImGui.table_next_row(0, row_height)
        PyImGui.table_set_bg_color(2, header_color, -1)
        for index, label in enumerate(labels):
            PyImGui.table_set_column_index(index)
            PyImGui.text(label)

    PyImGui.text_colored("Tunnels of the Forsaken Statistics", gold)
    PyImGui.separator()
    PyImGui.spacing()

    _scramble_accounts = PyImGui.checkbox("Hide Account Names", _scramble_accounts)

    session_eternal = sum(_session_eternal_blades.values())
    total_eternal = sum(_eternal_blade_drops.values())

    PyImGui.text_colored("Session Overview", cyan)
    if PyImGui.begin_table("##forsaken_bt_session", 3, table_flags):
        for label in ("Runs", "Eternal Blade", "Drop Rate"):
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
        _header_row(("Runs", "Eternal Blade", "Drop Rate"))
        values = (
            _session_runs,
            session_eternal,
            _drop_rate(_session_runs, session_eternal),
        )
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Total Overview", cyan)
    if PyImGui.begin_table("##forsaken_bt_all_time", 3, table_flags):
        for label in ("Runs", "Eternal Blade", "Drop Rate"):
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
        _header_row(("Runs", "Eternal Blade", "Drop Rate"))
        values = (
            _total_runs,
            total_eternal,
            _drop_rate(_total_runs, total_eternal),
        )
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Run Timings", cyan)
    if PyImGui.begin_table("##forsaken_bt_timings", 5, table_flags):
        for label in ("Floor", "Current", "Avg", "Best", "Worst"):
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, 72.0)
        _header_row(("Floor", "Current", "Avg", "Best", "Worst"))

        now = time.monotonic()
        run_active = _t_run_start > 0.0
        l1_active = run_active and _t_l2_start <= 0.0
        l2_active = _t_l2_start > 0.0 and _t_l3_start <= 0.0
        l3_active = _t_l3_start > 0.0
        surface_active = _t_surface_start > 0.0

        timing_rows = (
            ("Yak -> Dungeon", now - _t_surface_start if surface_active else _current_surface_time, surface_active, _surface_total_time, _surface_fastest, _surface_slowest, _surface_runs),
            ("Overall", now - _t_run_start if run_active else _current_run_time, run_active, _total_run_time, _fastest_run, _slowest_run, _total_runs),
            ("Floor 1", now - _t_run_start if l1_active else _current_l1_time, l1_active, _l1_total_time, _l1_fastest, _l1_slowest, _total_runs),
            ("Floor 2", now - _t_l2_start if l2_active else _current_l2_time, l2_active, _l2_total_time, _l2_fastest, _l2_slowest, _total_runs),
            ("Floor 3", now - _t_l3_start if l3_active else _current_l3_time, l3_active, _l3_total_time, _l3_fastest, _l3_slowest, _total_runs),
        )

        for label, current, is_live, total, fastest, slowest, sample_count in timing_rows:
            PyImGui.table_next_row(0, row_height)
            PyImGui.table_set_column_index(0)
            PyImGui.text(label)
            PyImGui.table_set_column_index(1)
            if is_live:
                PyImGui.text_colored(_fmt_time(current), live)
            else:
                PyImGui.text(_fmt_time(current))
            PyImGui.table_set_column_index(2)
            PyImGui.text(_avg_time(total, sample_count))
            PyImGui.table_set_column_index(3)
            PyImGui.text(_fmt_time(fastest))
            PyImGui.table_set_column_index(4)
            PyImGui.text(_fmt_time(slowest))

        PyImGui.end_table()

    PyImGui.spacing()
    if not _statistics_reset_pending:
        if PyImGui.button("Reset Total Overview & Run Timings"):
            _statistics_reset_pending = True
    else:
        PyImGui.text_colored("Reset all-time totals and timing history?", gold)
        if PyImGui.button("Confirm Reset"):
            _reset_total_overview_and_timings()
            _statistics_reset_pending = False
        PyImGui.same_line(0.0, 8.0)
        if PyImGui.button("Cancel"):
            _statistics_reset_pending = False

    PyImGui.spacing()
    PyImGui.text_colored("Eternal Blade Drops", cyan)
    if PyImGui.begin_table("##forsaken_bt_eternal_blade_drops", 4, table_flags):
        PyImGui.table_setup_column("Account", PyImGui.TableColumnFlags.WidthStretch)
        for label in ("Session", "All Time", "Drop Rate"):
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
        _header_row(("Account", "Session", "All Time", "Drop Rate"))

        keys = sorted(set(_session_eternal_blades) | set(_eternal_blade_drops))
        session_total = 0
        all_time_total = 0
        for key in keys:
            session_count = _session_eternal_blades.get(key, 0)
            all_time_count = _eternal_blade_drops.get(key, 0)
            session_total += session_count
            all_time_total += all_time_count

            PyImGui.table_next_row(0, row_height)
            PyImGui.table_set_column_index(0)
            PyImGui.text(_account_label(key))
            PyImGui.table_set_column_index(1)
            PyImGui.text(str(session_count))
            PyImGui.table_set_column_index(2)
            PyImGui.text(str(all_time_count))
            PyImGui.table_set_column_index(3)
            PyImGui.text(_drop_rate(_total_runs, all_time_count))

        PyImGui.table_next_row(0, row_height)
        PyImGui.table_set_column_index(0)
        PyImGui.text_colored("Total", gold)
        PyImGui.table_set_column_index(1)
        PyImGui.text_colored(str(session_total), gold)
        PyImGui.table_set_column_index(2)
        PyImGui.text_colored(str(all_time_total), gold)
        PyImGui.table_set_column_index(3)
        PyImGui.text_colored(_drop_rate(_total_runs, all_time_total), gold)
        PyImGui.end_table()


# region Elemental Keystone bundle handling

_MARTIAL_PRIMARY_PROFESSIONS = {"Warrior", "Ranger", "Assassin", "Dervish", "Paragon"}


def _is_holding_bundle() -> bool:
    try:
        return bool(Agent.IsHoldingItem(Player.GetAgentID()))
    except Exception:
        return False


def _resolve_keystone_combat_policy() -> bool:
    """Return True when the leader must drop the Elemental Keystone for combat."""
    global _drop_keystone_for_combat

    if _drop_keystone_for_combat is not None:
        return _drop_keystone_for_combat

    player_id = int(Player.GetAgentID() or 0)
    weapon_name = "Unknown"

    try:
        _, weapon_name = Agent.GetWeaponType(player_id)
    except Exception:
        weapon_name = "Unknown"

    try:
        is_martial = bool(Agent.IsMartial(player_id))
    except Exception:
        is_martial = False

    try:
        is_caster = bool(Agent.IsCaster(player_id))
    except Exception:
        is_caster = False

    if is_martial:
        _drop_keystone_for_combat = True
        reason = f"martial weapon detected: {weapon_name}"
    elif is_caster:
        _drop_keystone_for_combat = False
        reason = f"caster weapon detected: {weapon_name}"
    else:
        try:
            primary_profession, _ = Agent.GetProfessionNames(player_id)
        except Exception:
            primary_profession = ""

        if primary_profession in _MARTIAL_PRIMARY_PROFESSIONS:
            _drop_keystone_for_combat = True
            reason = f"martial primary profession detected: {primary_profession}"
        elif primary_profession:
            _drop_keystone_for_combat = False
            reason = f"caster primary profession detected: {primary_profession}"
        else:
            # Safe fallback: never risk entering combat with an unknown build
            # while the Keystone is occupying the weapon slot.
            _drop_keystone_for_combat = True
            reason = "weapon and profession are unknown; safe fallback"

    PySystem.Console.Log(
        MODULE_NAME,
        f"Elemental Keystone combat policy: {('DROP' if _drop_keystone_for_combat else 'KEEP')} ({reason}).",
        PySystem.Console.MessageType.Info,
    )
    return _drop_keystone_for_combat


def ResetKeystoneCombatPolicy() -> BehaviorTree:
    def _reset(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _drop_keystone_for_combat, _keystone_dropped_for_combat
        _drop_keystone_for_combat = None
        _keystone_dropped_for_combat = False
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Reset Elemental Keystone Combat Policy",
            action_fn=_reset,
            aftercast_ms=0,
        )
    )


def ResolveKeystoneCombatPolicy() -> BehaviorTree:
    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        _resolve_keystone_combat_policy()
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Resolve Elemental Keystone Combat Policy",
            action_fn=_resolve,
            aftercast_ms=0,
        )
    )


def _set_keystone_dropped_node(value: bool) -> BehaviorTree:
    def _set(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _keystone_dropped_for_combat
        _keystone_dropped_for_combat = bool(value)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Mark Elemental Keystone Dropped" if value else "Clear Elemental Keystone Dropped",
            action_fn=_set,
            aftercast_ms=0,
        )
    )


def DropKeystoneForCombat(log: bool=False) -> BehaviorTree:
    """Drop the Keystone only for martial combat; casters keep carrying it."""

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not _resolve_keystone_combat_policy():
            return BT.Succeeder("Keep Keystone For Caster Combat")
        if not _is_holding_bundle():
            return BT.Succeeder("No Keystone Bundle To Drop")
        return BT.Sequence(
            name="Drop Elemental Keystone For Combat",
            children=[
                BT.DropBundle(log=log),
                _set_keystone_dropped_node(True),
            ],
        )

    return BT.Subtree(name="Drop Keystone For Combat If Required", subtree_fn=_build)


def _enemy_in_keystone_combat_range(radius: float=Range.Earshot.value) -> bool:
    """Return True when a living enemy is within the Keystone combat-drop radius."""
    try:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            return False

        px, py = Agent.GetXY(player_id)
        radius_sq = float(radius) * float(radius)

        for candidate in AgentArray.GetEnemyArray() or []:
            agent_id = int(candidate or 0)
            if agent_id <= 0:
                continue
            try:
                if Agent.IsDead(agent_id):
                    continue
                x, y = Agent.GetXY(agent_id)
            except Exception:
                continue

            dx = float(x) - float(px)
            dy = float(y) - float(py)
            if dx * dx + dy * dy <= radius_sq:
                return True

        return False
    except Exception:
        return False


def KeystoneAwareVanquish(point: Vec2f, name: str) -> BehaviorTree:
    """Run one Vanquish point and drop a martial Keystone only when combat enters Earshot."""

    def _create_vanquish_tree() -> BehaviorTree:
        return BT.VanquishNode(
            [point],
            name=name,
            clear_area_radius=Range.Earshot.value,
            pause_on_combat=True,
            log=False,
        )

    vanquish_tree = _create_vanquish_tree()
    drop_tree: BehaviorTree | None = None

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal vanquish_tree, drop_tree

        # Keep carrying the Keystone while travelling.  For martial builds, only
        # release it once a live enemy actually enters the same Earshot radius
        # used by this Vanquish point.
        if (
            _resolve_keystone_combat_policy()
            and _is_holding_bundle()
            and _enemy_in_keystone_combat_range(Range.Earshot.value)
        ):
            if drop_tree is None:
                drop_tree = DropKeystoneForCombat(log=True)

            drop_tree.blackboard = node.blackboard
            drop_result = BehaviorTree.Node._normalize_state(drop_tree.tick())
            if drop_result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING
            if drop_result == BehaviorTree.NodeState.FAILURE:
                drop_tree = None
                return BehaviorTree.NodeState.FAILURE
            drop_tree = None

        vanquish_tree.blackboard = node.blackboard
        result = BehaviorTree.Node._normalize_state(vanquish_tree.tick())
        if result != BehaviorTree.NodeState.RUNNING:
            # Rebuild the internal node so a planner/wipe restart can execute the
            # point again instead of inheriting a completed child state.
            vanquish_tree = _create_vanquish_tree()
            drop_tree = None
        return result

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"{name} - Keystone Aware",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def _find_ground_keystone() -> int | None:
    """Return a nearby pickup-compatible Elemental Keystone, 0 if absent, None on scan failure."""
    try:
        local_player_id = int(Player.GetAgentID() or 0)
        if local_player_id <= 0:
            return 0
        px, py = Agent.GetXY(local_player_id)
        search_radius = 7500.0
        search_radius_sq = search_radius * search_radius

        for candidate in AgentArray.GetItemArray() or []:
            agent_id = int(candidate or 0)
            if agent_id <= 0 or not Agent.GetItemAgentByID(agent_id):
                continue
            owner_id = int(Agent.GetItemAgentOwnerID(agent_id) or 0)
            if owner_id not in (0, local_player_id):
                continue
            item_id = int(Agent.GetItemAgentItemID(agent_id) or 0)
            if item_id <= 0:
                continue
            if int(GLOBAL_CACHE.Item.GetModelID(item_id) or 0) != int(ELEMENTAL_KEYSTONE_MODEL_ID):
                continue

            x, y = Agent.GetXY(agent_id)
            dx = float(x) - float(px)
            dy = float(y) - float(py)
            if dx * dx + dy * dy <= search_radius_sq:
                return agent_id

        return 0
    except Exception:
        return None


def PickupKeystone(*, allow_missing_after_drop: bool = False) -> BehaviorTree:
    """Recover a dropped/new Keystone, optionally accepting a door-consumed bundle."""
    PICKUP_TIMEOUT_MS = 5_000
    RETRY_DELAY_MS = 1_000
    PICKUP_SEARCH_RADIUS = 7500.0

    def _create_pickup_tree() -> BehaviorTree:
        return BT.PickupGroundItemByModelID(
            model_ids=(ELEMENTAL_KEYSTONE_MODEL_ID,),
            max_distance=PICKUP_SEARCH_RADIUS,
            timeout_ms=PICKUP_TIMEOUT_MS,
            allow_unassigned=True,
            interaction_interval_ms=1_000,
            aftercast_ms=100,
            log=False,
        )

    pickup_tree = _create_pickup_tree()
    started_at = 0.0
    retry_at = 0.0
    search_started = False

    def _reset_state() -> None:
        nonlocal pickup_tree, started_at, retry_at, search_started
        pickup_tree = _create_pickup_tree()
        started_at = 0.0
        retry_at = 0.0
        search_started = False

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal pickup_tree, started_at, retry_at, search_started
        global _keystone_dropped_for_combat

        now = time.monotonic()

        if _is_holding_bundle():
            _keystone_dropped_for_combat = False
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        ground_keystone = _find_ground_keystone()
        if ground_keystone == 0 and (allow_missing_after_drop or not _keystone_dropped_for_combat):
            # Before the quest drop exists, absence is expected.  On the final
            # Level 1 door points, the Keystone can also be consumed by the door
            # after it was dropped; that disappearance must not block the route.
            if allow_missing_after_drop and _keystone_dropped_for_combat:
                PySystem.Console.Log(
                    MODULE_NAME,
                    "Elemental Keystone is no longer on the ground; assuming the door consumed it and continuing.",
                    PySystem.Console.MessageType.Info,
                )
                _keystone_dropped_for_combat = False
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        # If a preliminary scan itself failed, or we know we dropped the bundle,
        # let the established pickup routine search/retry until it is recovered.
        if started_at <= 0.0:
            started_at = now

        if not search_started:
            PySystem.Console.Log(
                MODULE_NAME,
                "Looking for the Elemental Keystone...",
                PySystem.Console.MessageType.Info,
            )
            search_started = True

        if (now - started_at) * 1000.0 >= PICKUP_TIMEOUT_MS:
            # After a shrine wipe the bundle can disappear entirely.  Do not fail
            # the planner and restart this Keystone point forever: clear the stale
            # dropped-state and accept the point so the route can continue.
            _keystone_dropped_for_combat = False
            PySystem.Console.Log(
                MODULE_NAME,
                "Elemental Keystone not recovered after 5s; continuing to the next route point.",
                PySystem.Console.MessageType.Warning,
            )
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        if now < retry_at:
            return BehaviorTree.NodeState.RUNNING

        pickup_tree.blackboard = node.blackboard
        result = BehaviorTree.Node._normalize_state(pickup_tree.tick())

        if result == BehaviorTree.NodeState.RUNNING:
            return BehaviorTree.NodeState.RUNNING

        if result == BehaviorTree.NodeState.SUCCESS and _is_holding_bundle():
            _keystone_dropped_for_combat = False
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        pickup_tree = _create_pickup_tree()
        pickup_tree.blackboard = node.blackboard
        retry_at = now + RETRY_DELAY_MS / 1000.0
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Pick Up Elemental Keystone",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def _keystone_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[Vec2f],
    *,
    skip_if_in_maps: Sequence[int]=(),
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Expose Keystone-route points individually and handle the martial bundle cycle."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    final_door_point_start = max(1, len(points) - 1)

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"
        allow_missing_after_drop = index >= final_door_point_start

        def _build(
            point: Vec2f=point,
            name: str=name,
            allow_missing_after_drop: bool=allow_missing_after_drop,
        ) -> BehaviorTree:
            run = BT.Sequence(
                name=name,
                children=[
                    KeystoneAwareVanquish(point, f"{name} Combat"),
                    PickupKeystone(allow_missing_after_drop=allow_missing_after_drop),
                ],
            )
            return _map_guarded_point(
                name=name,
                map_id=map_id,
                child=run,
                skip_if_in_maps=skip_if_in_maps,
            )

        steps.append((name, _build))

    return steps


# endregion


PIKEN_SQUARE = 40
YAKS_BEND = 134
TRAVELERS_VALE = 99
ASCALON_FOOTHILLS = 103
DIESSA_LOWLANDS = 13
THE_BREACH = 102
TUNNELS_L1 = 880
TUNNELS_L2 = 881
TUNNELS_L3 = 882
ELEMENTAL_KEYSTONE_MODEL_ID = 38301
BOSS_KEY_MODEL_ID = 25416

# Standard Piken route.
BREACH_ROUTE = [Vec2f(21250.00, 3550.00), Vec2f(18850.00, -900.00), Vec2f(19200.00, -4200.00), Vec2f(18000.00, -1700.00)]

# Alternate 6-man route: Yak's Bend -> Traveler's Vale -> Ascalon Foothills
# -> Diessa Lowlands -> The Breach -> Tunnels of the Forsaken.
YAKS_BEND_EXIT = Vec2f(-50.0, 50.0)
TRAVELERS_VALE_ROUTE = [
    Vec2f(8314, -665),
    Vec2f(10992, -1368),
    Vec2f(10422, -4573),
    Vec2f(10861, -8173),
    Vec2f(10378, -12168),
    Vec2f(9148, -15153),
    Vec2f(9772, -17054),
    Vec2f(11364, -17119),
]
ASCALON_FOOTHILLS_ROUTE = [
    Vec2f(-6007, 6342),
    Vec2f(-7967, 4382),
    Vec2f(-5576, 1599),
    Vec2f(-2048, 2226),
    Vec2f(-844, 3446),
    Vec2f(-972, 5100),
    Vec2f(730, 5662),
    Vec2f(2528, 7284),
    Vec2f(4134, 6272),
    Vec2f(6247, 2887),
    Vec2f(3337, -3168),
    Vec2f(7257, -5301),
    Vec2f(7443, -7201),
]
DIESSA_LOWLANDS_ROUTE = [
    Vec2f(-20468, 13104),
    Vec2f(-17761, 10229),
    Vec2f(-17154, 7964),
    Vec2f(-14188, 4980),
    Vec2f(-12684, 6347),
    Vec2f(-9787, 5387),
    Vec2f(-5969, 5601),
    Vec2f(-1754, 4700),
    Vec2f(-439, 1678),
    Vec2f(6697, 1119),
    Vec2f(9574, -7291),
    Vec2f(11012, -10887),
    Vec2f(16213, -10721),
    Vec2f(20583, -13167),
    Vec2f(21988, -15070),
    Vec2f(24345, -15138),
]
SIX_MEN_BREACH_ROUTE = [
    Vec2f(-16044, 3993),
    Vec2f(-13150, 6208),
    Vec2f(-11685, 10031),
    Vec2f(-4167, 8636),
    Vec2f(-747, 3961),
    Vec2f(7971, 5118),
    Vec2f(9434, 3312),
    Vec2f(14556, 1437),
    Vec2f(17414, 2100),
    Vec2f(17711, -186),
    Vec2f(19609, -4005),
    Vec2f(18695, -2976),
    Vec2f(17688, -1284),
]
L1_OPENING = [Vec2f(-13102.00, -6841.00), Vec2f(-11660.00, -7585.00), Vec2f(-7836.00, -9115.00)]
L1_KEY_ROUTE = [Vec2f(-9672.00, -3286.00), Vec2f(-11186.00, -1788.00), Vec2f(-10727.00, -304.00), Vec2f(-8618.00, 3132.00),]
L2_ROUTE = [Vec2f(-2196.00, 12191.00), Vec2f(1228.00, 16292.00), Vec2f(-764.00, 17454.00), Vec2f(-643.00, 20296.00), Vec2f(-2584.00, 21152.00), Vec2f(-3558.00, 21554.00), Vec2f(-3788.00, 21873.00), Vec2f(-6974.00, 20808.00), Vec2f(-9017.00, 21345.00), Vec2f(-9967,21872),Vec2f(-11685,21978),  Vec2f(-16238.00, 17982.00), Vec2f(-16724.00, 15846.00), Vec2f(-13865.00, 17135.00), Vec2f(-12848.00, 18506.00), Vec2f(-10956.00, 19044.00), Vec2f(-9889.00, 18907.00), Vec2f(-8953.00, 18720.00), Vec2f(-7921.00, 18913.00), Vec2f(-7456.00, 18718.00), Vec2f(-6272.00, 17188.00), Vec2f(-5910.00, 14892.00), Vec2f(-7177.00, 13320.00), Vec2f(-10482.00, 14259.00), Vec2f(-10816.00, 15686.00), Vec2f(-12402.00, 15310.00), Vec2f(-14553.00, 12670.00), Vec2f(-16047.00, 10162.00), Vec2f(-16759.00, 7708.00), Vec2f(-16748.00, 5350.00)]
L3_ROUTE_A = [Vec2f(-11162.00, 3309.00), Vec2f(-10127.00, 2505.00), Vec2f(-17353.00, -952.00), Vec2f(-16397.00, -3496.00), Vec2f(-15176.00, -3768.00), Vec2f(-13875.00, -4543.00), Vec2f(-14111.00, -6232.00), Vec2f(-13875.00, -4543.00), Vec2f(-10724.00, -3552.00)]
L3_ROUTE_B = [Vec2f(-9820.00, -2108.00), Vec2f(-8166.00, 1081.00), Vec2f(-5090.00, -78.00), Vec2f(-6212.00, -2777.00)]
L3_BOSS_ROUTE = [Vec2f(-7771.00, -6279.00), Vec2f(-11025.00, -7480.00), Vec2f(-12939.00, -8238.00), Vec2f(-13836.00, -8918.00),]


def _shrine_resume_candidates(map_id: int) -> list[tuple[str, Vec2f]]:
    """Return route planner steps that are safe anchors after a shrine revival."""
    if map_id == TUNNELS_L1:
        return [
            *[(f"Level 1 Opening - Point {index:02d}", point) for index, point in enumerate(L1_OPENING, start=1)],
            *[(
                f"Level 1 Elemental Keystone Route - Point {index:02d}",
                point,
            ) for index, point in enumerate(L1_KEY_ROUTE, start=1)],
        ]

    if map_id == TUNNELS_L2:
        return [
            (f"Level 2 Route - Point {index:02d}", point)
            for index, point in enumerate(L2_ROUTE, start=1)
        ]

    if map_id == TUNNELS_L3:
        return [
            *[(f"Level 3 Route A - Point {index:02d}", point) for index, point in enumerate(L3_ROUTE_A, start=1)],
            *[(f"Level 3 Door Approach - Point {index:02d}", point) for index, point in enumerate(L3_ROUTE_B, start=1)],
            *[(f"Level 3 Boss Route - Point {index:02d}", point) for index, point in enumerate(L3_BOSS_ROUTE, start=1)],
        ]

    return []


def _nearest_shrine_resume_step(
    map_id: int,
    position: tuple[float, float],
    failed_step_name: str,
) -> tuple[str, float]:
    """Pick the closest already-reached planner waypoint to the current shrine."""
    candidates = _shrine_resume_candidates(map_id)
    if not candidates:
        return "", float("inf")

    # Never jump forward past the planner step where the wipe happened.
    # This keeps quest/door progression safe even when another route section is
    # geometrically close on the other side of a wall.
    planner_names: list[str] = []
    if botting_tree is not None:
        try:
            planner_names = list(botting_tree.GetNamedPlannerStepNames() or [])
        except Exception:
            planner_names = []

    if planner_names and failed_step_name in planner_names:
        failed_index = planner_names.index(failed_step_name)
        eligible: list[tuple[str, Vec2f]] = []
        for step_name, point in candidates:
            try:
                if planner_names.index(step_name) <= failed_index:
                    eligible.append((step_name, point))
            except ValueError:
                continue
        if eligible:
            candidates = eligible

    px, py = float(position[0]), float(position[1])

    def _distance_sq(candidate: tuple[str, Vec2f]) -> float:
        point = candidate[1]
        dx = float(point.x) - px
        dy = float(point.y) - py
        return dx * dx + dy * dy

    step_name, point = min(candidates, key=_distance_sq)
    distance = _distance_sq((step_name, point)) ** 0.5
    return step_name, distance


def ForsakenPartyWipeRecoveryService() -> BehaviorTree:
    """Resume a shrine wipe from the route step nearest to the resurrection shrine."""
    state: dict[str, object] = {
        "active": False,
        "mode": "",
        "failed_step_name": "",
        "restart_step_name": "",
        "last_return_ms": 0.0,
        "player_was_dead": False,
        "player_dead_pos": None,
    }

    def _log(message: str, message_type=PySystem.Console.MessageType.Info) -> None:
        PySystem.Console.Log("ForsakenWipeRecovery", message, message_type)

    def _resolve_current_step(node: BehaviorTree.Node) -> str:
        step_name = str(node.blackboard.get("current_step_name", "") or "")
        if step_name:
            return step_name
        return str(node.blackboard.get("last_active_planner_step_name", "") or "")

    def _reset_state(node: BehaviorTree.Node) -> None:
        state["active"] = False
        state["mode"] = ""
        state["failed_step_name"] = ""
        state["restart_step_name"] = ""
        state["last_return_ms"] = 0.0
        state["player_was_dead"] = False
        state["player_dead_pos"] = None
        node.blackboard["party_wipe_recovery_active"] = False
        node.blackboard["party_wipe_recovery_mode"] = ""
        node.blackboard["party_wipe_recovery_step_name"] = ""

    def _player_is_alive() -> bool:
        player_id = int(Player.GetAgentID() or 0)
        return bool(player_id > 0 and Agent.IsValid(player_id) and not Agent.IsDead(player_id))

    def _can_resume_in_explorable() -> bool:
        return bool(
            Map.IsMapReady()
            and Map.IsExplorable()
            and GLOBAL_CACHE.Party.IsPartyLoaded()
            and _player_is_alive()
        )

    def _can_resume_from_outpost() -> bool:
        return bool(
            Map.IsMapReady()
            and Map.IsOutpost()
            and GLOBAL_CACHE.Party.IsPartyLoaded()
        )

    def _detect_revive_teleport() -> bool:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0 or not Agent.IsValid(player_id):
            return False

        current_pos = Agent.GetXY(player_id)
        is_dead = bool(Agent.IsDead(player_id))

        if is_dead:
            if not bool(state["player_was_dead"]):
                state["player_was_dead"] = True
                state["player_dead_pos"] = current_pos
                return False

            death_pos = state["player_dead_pos"]
            if death_pos:
                dx = float(current_pos[0]) - float(death_pos[0])
                dy = float(current_pos[1]) - float(death_pos[1])
                if dx * dx + dy * dy > float(Range.Spellcast.value) ** 2:
                    # Some GW revive flows move the dead agent to the shrine one
                    # frame before it becomes alive. Keep the new shrine position.
                    state["player_dead_pos"] = current_pos
                    return True
            return False

        if not bool(state["player_was_dead"]):
            return False

        state["player_was_dead"] = False
        death_pos = state["player_dead_pos"]
        state["player_dead_pos"] = None
        if not death_pos:
            return False

        dx = float(current_pos[0]) - float(death_pos[0])
        dy = float(current_pos[1]) - float(death_pos[1])
        return dx * dx + dy * dy > float(Range.Spellcast.value) ** 2

    def _begin_recovery(node: BehaviorTree.Node, mode: str) -> None:
        from Py4GWCoreLib.py4gwcorelib_src.ActionQueue import ActionQueueManager

        failed_step_name = _resolve_current_step(node)
        state["active"] = True
        state["mode"] = mode
        state["failed_step_name"] = failed_step_name
        state["restart_step_name"] = failed_step_name
        state["last_return_ms"] = 0.0

        node.blackboard["party_wipe_recovery_active"] = True
        node.blackboard["party_wipe_recovery_mode"] = mode
        node.blackboard["party_wipe_recovery_step_name"] = failed_step_name

        ActionQueueManager().ResetAllQueues()

        if mode == "defeated":
            _log(
                f"Party defeated. Waiting for outpost before restarting '{failed_step_name}'.",
                PySystem.Console.MessageType.Warning,
            )
        else:
            _log(
                f"Recoverable wipe on '{failed_step_name}'. Waiting for shrine revival.",
                PySystem.Console.MessageType.Warning,
            )

    def _resolve_shrine_restart(node: BehaviorTree.Node) -> str:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0 or not Agent.IsValid(player_id):
            return str(state["failed_step_name"] or "")

        map_id = int(Map.GetMapID() or 0)
        shrine_pos = Agent.GetXY(player_id)
        failed_step_name = str(state["failed_step_name"] or "")
        step_name, distance = _nearest_shrine_resume_step(
            map_id,
            shrine_pos,
            failed_step_name,
        )

        if step_name:
            _log(
                f"Shrine at ({shrine_pos[0]:.0f}, {shrine_pos[1]:.0f}) -> "
                f"nearest safe resume '{step_name}' ({distance:.0f} units).",
                PySystem.Console.MessageType.Success,
            )
            return step_name

        _log(
            f"No shrine resume waypoint resolved on map {map_id}; falling back to '{failed_step_name}'.",
            PySystem.Console.MessageType.Warning,
        )
        return failed_step_name

    def _request_restart(node: BehaviorTree.Node, *, shrine: bool) -> bool:
        if shrine:
            step_name = _resolve_shrine_restart(node)
        else:
            step_name = str(state["restart_step_name"] or state["failed_step_name"] or "")

        if not step_name:
            _log("Recovery completed but no planner step could be resolved.", PySystem.Console.MessageType.Warning)
            return False

        state["restart_step_name"] = step_name
        node.blackboard["party_wipe_recovery_step_name"] = step_name
        node.blackboard["current_step_name"] = step_name
        node.blackboard["last_active_planner_step_name"] = step_name
        node.blackboard["restart_step_name_request"] = step_name

        # A wipe can happen while the special L2 wall passage has CombatTree
        # disabled. Always restore combat before the resumed planner step starts.
        node.blackboard["combat_enabled_request"] = True
        return True

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        # SetNamedPlannerSteps always installs the Core recovery service. Keep it
        # suppressed so it cannot restart the stale pre-wipe planner step; this
        # Forsaken-specific service owns both shrine and outpost recovery.
        node.blackboard["party_wipe_recovery_suppressed"] = True

        now = time.monotonic() * 1000.0
        revived_at_shrine = _detect_revive_teleport()
        party_wiped = bool(Routines.Checks.Party.IsPartyWiped())
        party_defeated = bool(GLOBAL_CACHE.Party.IsPartyDefeated())

        if not bool(state["active"]):
            if not (party_wiped or party_defeated or revived_at_shrine):
                node.blackboard["party_wipe_recovery_active"] = False
                return BehaviorTree.NodeState.RUNNING

            recovery_mode = "defeated" if party_defeated else "shrine"
            _begin_recovery(node, recovery_mode)

            # The service can first notice the wipe on the same frame as the
            # shrine teleport. Resolve from the actual shrine position directly.
            if recovery_mode == "shrine" and revived_at_shrine and _can_resume_in_explorable():
                restarted = _request_restart(node, shrine=True)
                _reset_state(node)
                return BehaviorTree.NodeState.SUCCESS if restarted else BehaviorTree.NodeState.FAILURE

            return BehaviorTree.NodeState.RUNNING

        if party_defeated and state["mode"] != "defeated":
            state["mode"] = "defeated"
            _log(
                "Recoverable wipe became a party defeat; switching to outpost recovery.",
                PySystem.Console.MessageType.Warning,
            )

        node.blackboard["party_wipe_recovery_active"] = True
        node.blackboard["party_wipe_recovery_mode"] = str(state["mode"] or "")
        node.blackboard["party_wipe_recovery_step_name"] = str(
            state["restart_step_name"] or state["failed_step_name"] or ""
        )

        if state["mode"] == "shrine":
            if _can_resume_from_outpost():
                state["mode"] = "defeated"
                node.blackboard["party_wipe_recovery_mode"] = "defeated"
                _log(
                    "Party returned to an outpost during shrine recovery; switching to outpost recovery.",
                    PySystem.Console.MessageType.Warning,
                )
            else:
                shrine_recovery_complete = bool(
                    revived_at_shrine
                    or (not party_wiped and _can_resume_in_explorable())
                )
                if shrine_recovery_complete:
                    restarted = _request_restart(node, shrine=True)
                    _reset_state(node)
                    return BehaviorTree.NodeState.SUCCESS if restarted else BehaviorTree.NodeState.FAILURE

                return BehaviorTree.NodeState.RUNNING

        if _can_resume_from_outpost():
            restarted = _request_restart(node, shrine=False)
            _reset_state(node)
            return BehaviorTree.NodeState.SUCCESS if restarted else BehaviorTree.NodeState.FAILURE

        if now - float(state["last_return_ms"] or 0.0) >= 1000.0:
            GLOBAL_CACHE.Party.ReturnToOutpost()
            state["last_return_ms"] = now
            _log("Requesting return to outpost after party defeat.")

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Forsaken Party Wipe Recovery",
            action_fn=_tick,
            aftercast_ms=0,
        )
    )


def _map_guarded_point(
    name: str,
    map_id: int,
    child: BehaviorTree,
    skip_if_in_maps: Sequence[int]=(),
) -> BehaviorTree:
    """Run one planner point on its map, or accept it once a later floor is loaded."""
    branches: list[BehaviorTree] = [
        BT.Sequence(
            name=f"{name} - Active Map",
            children=[BT.IsCurrentMap(map_id=map_id, log=False), child],
        )
    ]

    for later_map_id in skip_if_in_maps:
        branches.append(
            BT.Sequence(
                name=f"{name} - Later Map {later_map_id}",
                children=[
                    BT.IsCurrentMap(map_id=int(later_map_id), log=False),
                    BT.Succeeder(f"{name}AlreadyPassed"),
                ],
            )
        )

    if len(branches) == 1:
        return branches[0]
    return BT.Selector(name=name, children=branches)


def _vanquish_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[Vec2f],
    *,
    clear_area_radius: float=Range.Earshot.value,
    pause_on_combat: bool=True,
    skip_if_in_maps: Sequence[int]=(),
    loot_after: bool=False,
    point_number_offset: int=0,
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Expose every Vanquish waypoint as its own MultiAccountSequence planner step."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for local_index, point in enumerate(points, start=1):
        point_number = int(point_number_offset) + local_index
        name = f"{prefix} - Point {point_number:02d}"

        def _build(
            point: Vec2f=point,
            name: str=name,
        ) -> BehaviorTree:
            child = BT.VanquishNode(
                [point],
                name=name,
                clear_area_radius=clear_area_radius,
                pause_on_combat=pause_on_combat,
                log=False,
            )
            return _map_guarded_point(
                name=name,
                map_id=map_id,
                child=child,
                skip_if_in_maps=skip_if_in_maps,
            )

        steps.append((name, _build))

    return steps


def _combat_disabled_move_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[Vec2f],
    *,
    skip_if_in_maps: Sequence[int]=(),
    point_number_offset: int=0,
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Move through wall-sensitive waypoints with HeroAI combat fully disabled."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []
    point_count = len(points)

    for local_index, point in enumerate(points, start=1):
        point_number = int(point_number_offset) + local_index
        name = f"{prefix} - Point {point_number:02d}"
        restore_combat = local_index == point_count

        def _build(
            point: Vec2f=point,
            name: str=name,
            restore_combat: bool=restore_combat,
        ) -> BehaviorTree:
            children: list[BehaviorTree] = [
                BottingTree.DisableCombatTree(),
                BT.Move(
                    point,
                    pause_on_combat=False,
                    tolerance=250.0,
                    log=False,
                ),
            ]
            if restore_combat:
                children.append(BottingTree.EnableCombatTree())

            child = BT.Sequence(
                name=f"{name} - Combat Disabled",
                children=children,
            )
            return _map_guarded_point(
                name=name,
                map_id=map_id,
                child=child,
                skip_if_in_maps=skip_if_in_maps,
            )

        steps.append((name, _build))

    return steps


def _selected_start_outpost() -> int:
    return YAKS_BEND if _six_men else PIKEN_SQUARE


def _surface_route_to_map(
    name: str,
    points: Sequence[Vec2f],
    target_map_id: int,
) -> BehaviorTree:
    if not points:
        return BT.Succeeder(f"{name} Empty")

    children: list[BehaviorTree] = [
        BT.VanquishNode(
            [point],
            clear_area_radius=Range.Earshot.value,
            pause_on_combat=True,
            log=True,
        )
        for point in points[:-1]
    ]
    children.append(
        BT.MoveAndExitMap(
            points[-1],
            target_map_id=target_map_id,
            log=True,
        )
    )
    return BT.Sequence(name=name, children=children)


def _six_men_surface_entry() -> BehaviorTree:
    return BT.Sequence(
        name="6 Men Surface Entry",
        children=[
            _on_map_or_skip(
                "6 Men - Exit Yak's Bend",
                YAKS_BEND,
                BT.Sequence(
                    name="6 Men - Exit Yak's Bend And Start Timer",
                    children=[
                        BT.MoveAndExitMap(
                            YAKS_BEND_EXIT,
                            target_map_id=TRAVELERS_VALE,
                            log=True,
                        ),
                        _mark_surface_start_node(),
                    ],
                ),
                (TRAVELERS_VALE, ASCALON_FOOTHILLS, DIESSA_LOWLANDS, THE_BREACH, TUNNELS_L1, TUNNELS_L2, TUNNELS_L3),
            ),
            _on_map_or_skip(
                "6 Men - Traveler's Vale Route",
                TRAVELERS_VALE,
                _surface_route_to_map(
                    "6 Men - Traveler's Vale Route",
                    TRAVELERS_VALE_ROUTE,
                    ASCALON_FOOTHILLS,
                ),
                (ASCALON_FOOTHILLS, DIESSA_LOWLANDS, THE_BREACH, TUNNELS_L1, TUNNELS_L2, TUNNELS_L3),
            ),
            _on_map_or_skip(
                "6 Men - Ascalon Foothills Route",
                ASCALON_FOOTHILLS,
                _surface_route_to_map(
                    "6 Men - Ascalon Foothills Route",
                    ASCALON_FOOTHILLS_ROUTE,
                    DIESSA_LOWLANDS,
                ),
                (DIESSA_LOWLANDS, THE_BREACH, TUNNELS_L1, TUNNELS_L2, TUNNELS_L3),
            ),
            _on_map_or_skip(
                "6 Men - Diessa Lowlands Route",
                DIESSA_LOWLANDS,
                _surface_route_to_map(
                    "6 Men - Diessa Lowlands Route",
                    DIESSA_LOWLANDS_ROUTE,
                    THE_BREACH,
                ),
                (THE_BREACH, TUNNELS_L1, TUNNELS_L2, TUNNELS_L3),
            ),
            _on_map_or_skip(
                "6 Men - The Breach To Tunnels",
                THE_BREACH,
                _surface_route_to_map(
                    "6 Men - The Breach To Tunnels",
                    SIX_MEN_BREACH_ROUTE,
                    TUNNELS_L1,
                ),
                (TUNNELS_L1, TUNNELS_L2, TUNNELS_L3),
            ),
        ],
    )


def PrepareRun() -> BehaviorTree:
    already_inside = BT.Selector(
        name="Already Inside Tunnels",
        children=[BT.IsCurrentMap(map_id=m, log=False) for m in DUNGEON_MAPS],
    )
    prepare = BT.Sequence(
        name="Prepare Tunnels Run",
        children=[
            BT.Subtree(
                name="Travel To Selected Start Outpost",
                subtree_fn=lambda _node: _travel_all_accounts(
                    _selected_start_outpost(),
                    "tunnels_start_yaks" if _six_men else "tunnels_start_piken",
                ),
            ),
            InventoryCheckAndMaintenance(),
            BT.CreateParty(hero_ids=[24,25],multibox_invite=True, timeout_ms=30_000, log=True),
            BT.AbandonQuest(quest_id=QUEST_ID, multi_account=True, include_self=True, timeout_ms=10_000, log=True),
            _runtime_difficulty_node(),
            _runtime_restock_node(),
            _runtime_consumable_upkeep_node(False),
        ],
    )
    return BT.Selector(name="Prepare Run Or Resume", children=[already_inside, prepare])


def EnterTunnels() -> BehaviorTree:
    later = BT.Selector(
        name="Tunnels Already Entered",
        children=[BT.IsCurrentMap(map_id=m, log=False) for m in DUNGEON_MAPS],
    )

    def _build_entry(_node: BehaviorTree.Node) -> BehaviorTree:
        if _six_men:
            return BT.Sequence(
                name="Yak's Bend To Tunnels Level 1 - 6 Men",
                children=[
                    _runtime_consumable_upkeep_node(False),
                    _six_men_surface_entry(),
                    BT.WaitForMapLoad(map_id=TUNNELS_L1, timeout_ms=60_000),
                    _record_surface_end_node(),
                    _runtime_consumable_upkeep_node(True),
                ],
            )

        return BT.Sequence(
            name="Piken To Tunnels Level 1",
            children=[
                _runtime_consumable_upkeep_node(False),
                BT.MoveAndExitMap(Vec2f(20180, 7500), target_map_id=THE_BREACH, log=True),
                BT.Sequence(
                    name="The Breach Route",
                    children=[
                        BT.VanquishNode(
                            [point],
                            clear_area_radius=Range.Earshot.value,
                            pause_on_combat=True,
                            log=True,
                        )
                        for point in BREACH_ROUTE
                    ],
                ),
                BT.MoveAndExitMap(Vec2f(17600, -1300), target_map_id=TUNNELS_L1, log=True),
                BT.WaitForMapLoad(map_id=TUNNELS_L1, timeout_ms=60_000),
                _runtime_consumable_upkeep_node(True),
            ],
        )

    entry = BT.Subtree(name="Selected Surface Entry", subtree_fn=_build_entry)
    return BT.Selector(name="Enter Tunnels", children=[later, entry])


def Level1_Start() -> BehaviorTree:
    run = BT.Sequence(
        name="Tunnels Level 1 Start",
        children=[
            _mark_run_start_node(),
            _inventory_statistics_node(after_chest=False),
            ResetKeystoneCombatPolicy(),
            ResolveKeystoneCombatPolicy(),
            UseAvailableSummoningStone("l1"),
            BT.AddModelToLootWhitelist(ELEMENTAL_KEYSTONE_MODEL_ID),
            BT.Move(Vec2f(-15247, -5785), pause_on_combat=False, log=False),
        ],
    )
    return _on_map_or_skip(
        "Level 1 Start",
        TUNNELS_L1,
        run,
        (TUNNELS_L2, TUNNELS_L3),
    )


def Level1_TakeQuest() -> BehaviorTree:
    run = BT.Sequence(
        name="Take The Dreamer and the Zealot",
        children=[
            BT.MoveAndDialog(
                Vec2f(-7400, -9462),
                dialog_id=0x85B501,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(QUEST_ID, timeout_ms=15_000),
        ],
    )
    return _on_map_or_skip(
        "Level 1 Take Quest",
        TUNNELS_L1,
        run,
        (TUNNELS_L2, TUNNELS_L3),
    )


def Level1_EnterLevel2() -> BehaviorTree:
    run = BT.Sequence(
        name="Enter Tunnels Level 2",
        children=[
            BT.MoveAndExitMap(Vec2f(-8576,5749), target_map_id=TUNNELS_L2, log=True, destination_obstacle_ignore_distance=Range.Spirit.value),
            BT.WaitForMapLoad(map_id=TUNNELS_L2, timeout_ms=60_000),
            _mark_l2_start_node(),
        ],
    )
    return _on_map_or_skip(
        "Level 1 Enter Level 2",
        TUNNELS_L1,
        run,
        (TUNNELS_L2, TUNNELS_L3),
    )


def Level2_Start() -> BehaviorTree:
    run = BT.Sequence(
        name="Tunnels Level 2 Start",
        children=[
            # Safety restore in case a previous interrupted wall passage left combat disabled.
            BottingTree.EnableCombatTree(),
            UseAvailableSummoningStone("l2"),
        ],
    )
    return _on_map_or_skip(
        "Level 2 Start",
        TUNNELS_L2,
        run,
        (TUNNELS_L3,),
    )


def Level2_EnterLevel3() -> BehaviorTree:
    run = BT.Sequence(
        name="Enter Tunnels Level 3",
        children=[
            BT.MoveAndExitMap(Vec2f(-16780, 4324), target_map_id=TUNNELS_L3, log=True),
            BT.WaitForMapLoad(map_id=TUNNELS_L3, timeout_ms=60_000),
            _mark_l3_start_node(),
        ],
    )
    return _on_map_or_skip(
        "Level 2 Enter Level 3",
        TUNNELS_L2,
        run,
        (TUNNELS_L3,),
    )


def Level3_Start() -> BehaviorTree:
    return BT.Sequence(
        name="Tunnels Level 3 Start",
        children=[
            BT.IsCurrentMap(map_id=TUNNELS_L3, log=True),
            BT.AddModelToLootWhitelist(BOSS_KEY_MODEL_ID),
            UseAvailableSummoningStone("l3"),
        ],
    )


def Level3_OpenDoor() -> BehaviorTree:
    return BT.Sequence(
        name="Open Level 3 Dungeon Door",
        children=[
            BT.IsCurrentMap(map_id=TUNNELS_L3, log=True),
            BT.MoveAndInteractWithGadget(
                pos=Vec2f(-6442, -4281),
                search_distance=900.0,
                interaction_distance=Range.Nearby.value,
                interaction_count=2,
                interaction_interval_ms=750,
                account_settle_ms=1_500,
                timeout_ms=30_000,
                multi_account=False,
                include_self=True,
                log=True,
            ),
        ],
    )


def Level3_FinishRun() -> BehaviorTree:
    """Finish the dungeon through reward/chest handling only."""
    return BT.Sequence(
        name="Level 3 Reward And Chest",
        children=[
            BT.WaitForClearEnemiesInArea(-13836.00, -8918.00, stable_clear_ms=2000, log=True),
            _record_run_end_node(),
            BT.IsCurrentMap(map_id=TUNNELS_L3, log=True),
            _runtime_consumable_upkeep_node(False),
            BT.MoveAndDialog(
                Vec2f(-16098, -8626),
                dialog_id=0x85B507,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.InteractTargetAndSendDialog(0x85B507, multi_account=True, log=True),
            BT.SendDialog(0x85B507, multi_account=True, log=True),
            BT.WaitForQuestCleared(QUEST_ID, timeout_ms=15_000),
            BT.MoveAndInteractWithGadget(
                pos=Vec2f(-16066, -8370),
                search_distance=2_500.0,
                interaction_distance=Range.Nearby.value,
                interaction_count=2,
                interaction_interval_ms=750,
                account_settle_ms=1_500,
                timeout_ms=30_000,
                multi_account=True,
                include_self=True,
                log=True,
            ),
            BT.Wait(5_000),
            _inventory_statistics_node(after_chest=True),
        ],
    )


def Level3_ReturnToOutpost() -> BehaviorTree:
    """Return every account to the start outpost selected by the 6-men option."""
    return BT.Subtree(
        name="Return To Selected Start Outpost",
        subtree_fn=lambda _node: BT.Resign(
            wait_for_map_load=True,
            target_map_id=_selected_start_outpost(),
            multi_account=True,
            timeout_ms=10_000,
            log=True,
        ),
    )


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Initialize", InitializeBot),
        ("Prepare Run", PrepareRun),
        ("Enter Tunnels", EnterTunnels),

        ("Level 1 Start", Level1_Start),
        *_vanquish_point_steps(
            "Level 1 Opening",
            TUNNELS_L1,
            L1_OPENING,
            skip_if_in_maps=(TUNNELS_L2, TUNNELS_L3),
        ),
        ("Level 1 Take Quest", Level1_TakeQuest),
        *_keystone_point_steps(
            "Level 1 Elemental Keystone Route",
            TUNNELS_L1,
            L1_KEY_ROUTE,
            skip_if_in_maps=(TUNNELS_L2, TUNNELS_L3),
        ),
        ("Level 1 Enter Level 2", Level1_EnterLevel2),

        ("Level 2 Start", Level2_Start),
        *_vanquish_point_steps(
            "Level 2 Route",
            TUNNELS_L2,
            L2_ROUTE[:16],
            skip_if_in_maps=(TUNNELS_L3,),
        ),
        *_combat_disabled_move_point_steps(
            "Level 2 Route",
            TUNNELS_L2,
            L2_ROUTE[16:19],
            skip_if_in_maps=(TUNNELS_L3,),
            point_number_offset=16,
        ),
        *_vanquish_point_steps(
            "Level 2 Route",
            TUNNELS_L2,
            L2_ROUTE[19:],
            skip_if_in_maps=(TUNNELS_L3,),
            point_number_offset=19,
        ),
        ("Level 2 Enter Level 3", Level2_EnterLevel3),

        ("Level 3 Start", Level3_Start),
        *_vanquish_point_steps("Level 3 Route A", TUNNELS_L3, L3_ROUTE_A),
        *_vanquish_point_steps("Level 3 Door Approach", TUNNELS_L3, L3_ROUTE_B),
        ("Level 3 Open Dungeon Door", Level3_OpenDoor),
        *_vanquish_point_steps("Level 3 Boss Route", TUNNELS_L3, L3_BOSS_ROUTE),
        ("Level 3 Reward And Chest", Level3_FinishRun),
        ("Return To Selected Start Outpost", Level3_ReturnToOutpost),
    ]


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()
    return BT.Sequence(
        name="Initialize Bot",
        children=[
            bot.Config.Aggressive(
                multi_account=True,
                auto_loot=_auto_loot,
                resurrection_scroll=True,
                account_isolation=False,
            ),
            BT.SetPlayerStatus(PlayerStatus.Offline, log=True),
            BT.LogMessage(message=f"{MODULE_NAME} initialized.", module_name=MODULE_NAME),
        ],
    )


def _configure_botting_tree(tree: BottingTree) -> None:
    tree.Config.ConfigureUpkeep(
        looting_enabled=_auto_loot,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=_enabled_consumable_upkeeps(),
        enable_party_wipe_recovery=False,
        heroai_state_logging=False,
    )
    tree.AddServiceTree(
        "ForsakenPartyWipeRecoveryService",
        ForsakenPartyWipeRecoveryService,
    )


def ensure_botting_tree() -> BottingTree:
    global botting_tree
    _load_settings()
    if botting_tree is None:
        Listeners.AutoReturnOnDefeat.Enable()
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name="MultiAccountSequence",
            repeat=True,
            multi_account=True,
            isolation_enabled=False,
            configure_fn=_configure_botting_tree,
        )
    return botting_tree


def main() -> None:
    global initialized
    if not initialized:
        _load_settings()
        ensure_botting_tree()
        initialized = True
    tree = ensure_botting_tree()
    _sync_runtime_upkeeps()
    tree.tick()
    tree.UI.draw_window(icon_path=TEXTURE,
        main_child_dimensions=(430, 390),
        extra_tabs=[("Statistics", _draw_statistics), ("Config", _draw_run_config)],
    )


if __name__ == "__main__":
    main()
