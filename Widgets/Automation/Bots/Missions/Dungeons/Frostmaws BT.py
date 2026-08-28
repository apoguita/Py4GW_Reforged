# Frostmaw's Burrows BottingTree conversion.
# Uses native BT wrappers directly and exposes every dungeon waypoint as a planner step.

from __future__ import annotations

from collections.abc import Callable, Sequence
import time

import PySystem
import PyImGui

from Py4GWCoreLib import Agent, AgentArray, GLOBAL_CACHE, Inventory, Map, Party, Player, SharedCommandType
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
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Widgets.System.Messaging import (
    get_inventory_count,
    reset_inventory_count,
    get_inventory_state,
    reset_inventory_state,
)


MODULE_NAME = "Frostmaw's Burrows BT"
INI_PATH = 'Widgets/Automation/Bots/Missions/Dungeons/Frostmaws Burrows BT'
INI_FILENAME = 'Frostmaws_Burrows_BT.ini'

START_OUTPOST = 643
SURFACE_MAPS = (546,)
DUNGEON_MAPS = (630, 631, 632, 633, 634)
QUEST_ID = 0x32A
GREAT_TEMPLE_OF_BALTHAZAR = 248

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

INVENTORY_TRAVEL_REGION = 2
INVENTORY_TRAVEL_DISTRICT = 1
INVENTORY_TRAVEL_LANGUAGE = 0
INVENTORY_MAINTENANCE_RETRY_COUNT = 2
INVENTORY_SNAPSHOT_SETTLE_MS = 2_000
INVENTORY_TRAVEL_TIMEOUT_MS = 60_000
INVENTORY_MERCHANT_TIMEOUT_MS = 240_000
_INVENTORY_QUERY_TIMEOUT_MS = 10_000
_INVENTORY_QUERY_POLL_MS = 200

_SETTINGS_SECTION = "Settings"
_STATS_SECTION = "Statistics"
_CHAR_NAMES_SECTION = "Character Names"

# Verified rare Chest of Burrows model IDs.
# Other Frostmaw-exclusive skins are intentionally not guessed here.
FROSTMAW_DROP_TRACKERS: dict[str, dict[str, object]] = {
    "silverwing": {
        "label": "Silverwing",
        "short": "SW",
        "model_min": 2039,
        "model_max": 2039,
        "drops_section": "Silverwing Drops",
        "snapshot_section": "Silverwing Snapshot",
        "run_section": "Silverwing Run",
    },
    "bonecage": {
        "label": "Bonecage Scythe",
        "short": "Bone",
        "model_min": 2058,
        "model_max": 2058,
        "drops_section": "Bonecage Drops",
        "snapshot_section": "Bonecage Snapshot",
        "run_section": "Bonecage Run",
    },
    "icicle": {
        "label": "Icicle Staff",
        "short": "Icicle",
        "model_min": 2385,
        "model_max": 2389,
        "drops_section": "Icicle Staff Drops",
        "snapshot_section": "Icicle Staff Snapshot",
        "run_section": "Icicle Staff Run",
    },
}

_settings = Settings(f"{INI_PATH}/{INI_FILENAME}", "global")
_settings_loaded = False
_statistics_loaded = False

_use_hard_mode = True
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
_floor_total_time = [0.0] * 5
_floor_fastest = [float("inf")] * 5
_floor_slowest = [0.0] * 5
_drop_totals: dict[str, dict[str, int]] = {key: {} for key in FROSTMAW_DROP_TRACKERS}
_char_names: dict[str, str] = {}

# Session-only statistics.
_session_runs = 0
_session_drops: dict[str, dict[str, int]] = {key: {} for key in FROSTMAW_DROP_TRACKERS}
_scramble_accounts = False
_statistics_reset_pending = False

# Active and most recently completed timings.
_t_run_start = 0.0
_t_floor_starts = [0.0] * 5
_current_run_time = 0.0
_current_floor_times = [0.0] * 5

initialized = False
botting_tree: BottingTree | None = None


def _load_settings() -> None:
    global _settings_loaded
    global _use_hard_mode, _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons, _use_summoning_stone, _auto_loot
    global _inventory_maintenance_enabled, _inventory_min_free_slots
    global _inventory_min_id_kits, _inventory_min_salvage_kits
    global _runtime_looting_enabled

    if _settings_loaded:
        _load_statistics()
        return

    _use_hard_mode = _settings.get_bool(_SETTINGS_SECTION, "HardMode", True)
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
    keys: set[str] = set()
    for tracker_key in FROSTMAW_DROP_TRACKERS:
        keys.update(_drop_totals[tracker_key])
        keys.update(_session_drops[tracker_key])
    return sorted(key for key in keys if key and key != "local")


def _account_label(key: str) -> str:
    if not _scramble_accounts:
        return _char_names.get(key) or _display_email(key)
    keys = _known_account_keys()
    index = keys.index(key) + 1 if key in keys else 0
    return f"Player {index}"


def _shared_accounts() -> list[object]:
    """All active accounts for statistics, including isolated accounts when supported."""
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

    for account in _shared_accounts():
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

    if _statistics_loaded:
        return

    section = _STATS_SECTION
    # Fall back to the previous Frostmaw keys so existing totals are not discarded.
    _total_runs = _settings.get_int(section, "total_runs", _settings.get_int(section, "TotalRuns", 0))
    _total_run_time = _settings.get_float(section, "total_run_time", _settings.get_float(section, "TotalRunTime", 0.0))
    fastest = _settings.get_float(section, "fastest_run", _settings.get_float(section, "FastestRun", 0.0))
    _fastest_run = float("inf") if fastest <= 0.0 else fastest
    _slowest_run = _settings.get_float(section, "slowest_run", 0.0)

    for floor_index in range(5):
        floor = f"l{floor_index + 1}"
        _floor_total_time[floor_index] = _settings.get_float(section, f"{floor}_total_time", 0.0)
        fastest_floor = _settings.get_float(section, f"{floor}_fastest", 0.0)
        _floor_fastest[floor_index] = float("inf") if fastest_floor <= 0.0 else fastest_floor
        _floor_slowest[floor_index] = _settings.get_float(section, f"{floor}_slowest", 0.0)

    for tracker_key, tracker in FROSTMAW_DROP_TRACKERS.items():
        totals = _drop_totals[tracker_key]
        totals.pop("local", None)
        _session_drops[tracker_key].pop("local", None)
        drops_section = str(tracker["drops_section"])
        for key in _settings.items(drops_section).keys():
            if key != "local":
                totals[key] = _settings.get_int(drops_section, key, 0)

        for seed_section in (str(tracker["snapshot_section"]), str(tracker["run_section"])):
            for key in _settings.items(seed_section).keys():
                if key != "local":
                    totals.setdefault(key, 0)

    _char_names.pop("local", None)
    for key in _settings.items(_CHAR_NAMES_SECTION).keys():
        if key == "local":
            continue
        name = str(_settings.get_str(_CHAR_NAMES_SECTION, key, "") or "").strip()
        if name:
            _char_names[key] = name

    _statistics_loaded = True


def _save_statistics() -> None:
    section = _STATS_SECTION
    _settings.set(section, "total_runs", _total_runs)
    _settings.set(section, "total_run_time", _total_run_time)
    _settings.set(section, "fastest_run", 0.0 if _fastest_run == float("inf") else _fastest_run)
    _settings.set(section, "slowest_run", _slowest_run)

    for floor_index in range(5):
        floor = f"l{floor_index + 1}"
        _settings.set(section, f"{floor}_total_time", _floor_total_time[floor_index])
        _settings.set(
            section,
            f"{floor}_fastest",
            0.0 if _floor_fastest[floor_index] == float("inf") else _floor_fastest[floor_index],
        )
        _settings.set(section, f"{floor}_slowest", _floor_slowest[floor_index])

    for tracker_key, tracker in FROSTMAW_DROP_TRACKERS.items():
        drops_section = str(tracker["drops_section"])
        for key, total in _drop_totals[tracker_key].items():
            if key != "local":
                _settings.set(drops_section, key, total)

    for key, name in _char_names.items():
        if key != "local":
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


def _mark_run_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_run_start, _current_run_time
        now = time.monotonic()
        _t_run_start = now
        for index in range(5):
            _t_floor_starts[index] = 0.0
            _current_floor_times[index] = 0.0
        _t_floor_starts[0] = now
        _current_run_time = 0.0

    return _statistics_action_node("Mark Run Start", _mark)


def _mark_floor_start_node(floor_number: int) -> BehaviorTree:
    floor_index = int(floor_number) - 1

    def _mark() -> None:
        if floor_index <= 0 or floor_index >= 5:
            return
        now = time.monotonic()
        previous_start = _t_floor_starts[floor_index - 1]
        if previous_start > 0.0:
            _current_floor_times[floor_index - 1] = max(0.0, now - previous_start)
        _t_floor_starts[floor_index] = now

    return _statistics_action_node(f"Mark Level {floor_number} Start", _mark)


def _record_run_end_node() -> BehaviorTree:
    def _record() -> None:
        global _total_runs, _session_runs
        global _total_run_time, _fastest_run, _slowest_run, _current_run_time, _t_run_start

        now = time.monotonic()
        starts = list(_t_floor_starts)
        timings_valid = (
            _t_run_start > 0.0
            and starts[0] == _t_run_start
            and all(starts[index] > starts[index - 1] for index in range(1, 5))
        )

        if timings_valid:
            run_time = now - _t_run_start
            floor_times = [
                starts[1] - starts[0],
                starts[2] - starts[1],
                starts[3] - starts[2],
                starts[4] - starts[3],
                now - starts[4],
            ]
            _current_run_time = run_time
            _total_run_time += run_time
            _fastest_run = min(_fastest_run, run_time)
            _slowest_run = max(_slowest_run, run_time)

            for index, floor_time in enumerate(floor_times):
                _current_floor_times[index] = floor_time
                _floor_total_time[index] += floor_time
                _floor_fastest[index] = min(_floor_fastest[index], floor_time)
                _floor_slowest[index] = max(_floor_slowest[index], floor_time)

            floor_log = " | ".join(f"L{index + 1} {value:.0f}s" for index, value in enumerate(floor_times))
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] Run complete - Total {run_time:.0f}s | {floor_log}",
                PySystem.Console.MessageType.Success,
            )

        _total_runs += 1
        _session_runs += 1
        _t_run_start = 0.0
        for index in range(5):
            _t_floor_starts[index] = 0.0
        _save_statistics()

    return _statistics_action_node("Record Successful Run", _record)


def _inventory_count(model_id_min: int, model_id_max: int) -> int:
    return sum(
        int(GLOBAL_CACHE.Inventory.GetModelCount(model_id))
        for model_id in range(int(model_id_min), int(model_id_max) + 1)
    )


def _accumulate_drop(tracker_key: str, account_key: str, count: int) -> None:
    all_time = _drop_totals[tracker_key]
    session = _session_drops[tracker_key]
    all_time.setdefault(account_key, 0)
    if count <= 0:
        return
    all_time[account_key] += int(count)
    session[account_key] = session.get(account_key, 0) + int(count)


def _inventory_statistics_node(*, after_chest: bool) -> BehaviorTree:
    node_name = "Record Drops After Burrows Chest" if after_chest else "Snapshot Inventories At Dungeon Entry"
    state: dict[str, object] = {
        "started": False,
        "local_email": "",
        "account_keys": [],
        "requests": [],
        "request_index": 0,
        "waiting": False,
        "request_started_at": 0.0,
        "local_email_wait_started_at": 0.0,
    }

    def _reset() -> None:
        state.update(
            started=False,
            local_email="",
            account_keys=[],
            requests=[],
            request_index=0,
            waiting=False,
            request_started_at=0.0,
            local_email_wait_started_at=0.0,
        )

    def _start() -> bool:
        _load_statistics()
        _refresh_character_names()
        local_email = str(Player.GetAccountEmail() or "").strip()
        if not local_email:
            return False

        local_key = _account_key(local_email)
        account_keys = [local_key]
        requests: list[dict[str, object]] = []

        for tracker_key, tracker in FROSTMAW_DROP_TRACKERS.items():
            section = str(tracker["run_section"] if after_chest else tracker["snapshot_section"])
            model_min = int(tracker["model_min"])
            model_max = int(tracker["model_max"])
            _settings.set(section, local_key, _inventory_count(model_min, model_max))
            _drop_totals[tracker_key].setdefault(local_key, 0)

        for account in _shared_accounts():
            email = str(getattr(account, "AccountEmail", "") or "").strip()
            if not email or email == local_email:
                continue
            key = _account_key(email)
            if key not in account_keys:
                account_keys.append(key)

            for tracker_key, tracker in FROSTMAW_DROP_TRACKERS.items():
                _drop_totals[tracker_key].setdefault(key, 0)
                requests.append(
                    {
                        "email": email,
                        "key": key,
                        "tracker_key": tracker_key,
                        "model_min": int(tracker["model_min"]),
                        "model_max": int(tracker["model_max"]),
                        "section": str(tracker["run_section"] if after_chest else tracker["snapshot_section"]),
                        "label": str(tracker["label"]),
                    }
                )

        state["started"] = True
        state["local_email"] = local_email
        state["account_keys"] = account_keys
        state["requests"] = requests
        return True

    def _finish() -> None:
        if not after_chest:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] Dungeon-entry inventory snapshot completed for {len(state['account_keys'])} account(s).",
                PySystem.Console.MessageType.Info,
            )
            _save_statistics()
            return

        recorded: dict[str, int] = {key: 0 for key in FROSTMAW_DROP_TRACKERS}
        for raw_key in state["account_keys"]:
            account_key = str(raw_key)
            for tracker_key, tracker in FROSTMAW_DROP_TRACKERS.items():
                before = _settings.get_int(str(tracker["snapshot_section"]), account_key, -1)
                after = _settings.get_int(str(tracker["run_section"]), account_key, -1)
                delta = max(0, after - before) if before >= 0 and after >= 0 else 0
                _accumulate_drop(tracker_key, account_key, delta)
                recorded[tracker_key] += delta

        _save_statistics()
        drop_log = " | ".join(
            f"{FROSTMAW_DROP_TRACKERS[key]['label']} {recorded[key]}" for key in FROSTMAW_DROP_TRACKERS
        )
        PySystem.Console.Log(
            MODULE_NAME,
            f"[Statistics] Burrows Chest recorded - {drop_log}",
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
                    started = float(state["local_email_wait_started_at"] or 0.0)
                    if started <= 0.0:
                        state["local_email_wait_started_at"] = now
                        return BehaviorTree.NodeState.RUNNING
                    if (now - started) * 1000.0 < _INVENTORY_QUERY_TIMEOUT_MS:
                        return BehaviorTree.NodeState.RUNNING
                    PySystem.Console.Log(
                        MODULE_NAME,
                        "[Statistics] Local account email unavailable; skipping statistics snapshot.",
                        PySystem.Console.MessageType.Warning,
                    )
                    _reset()
                    return BehaviorTree.NodeState.SUCCESS

            requests = state["requests"]
            while int(state["request_index"]) < len(requests):
                request_index = int(state["request_index"])
                request = requests[request_index]
                email = str(request["email"])
                model_min = int(request["model_min"])
                model_max = int(request["model_max"])

                if not bool(state["waiting"]):
                    reset_inventory_count(email, model_min, model_max)
                    _settings.set(str(request["section"]), str(request["key"]), -1)
                    GLOBAL_CACHE.ShMem.SendMessage(
                        str(state["local_email"]),
                        email,
                        SharedCommandType.InventoryQuery,
                        (float(model_min), float(model_max), 0.0, 0.0),
                        ("report_inventory_count",),
                    )
                    state["waiting"] = True
                    state["request_started_at"] = time.monotonic()
                    return BehaviorTree.NodeState.RUNNING

                count = int(get_inventory_count(email, model_min, model_max))
                if count >= 0:
                    _settings.set(str(request["section"]), str(request["key"]), count)
                    state["request_index"] = request_index + 1
                    state["waiting"] = False
                    continue

                if (time.monotonic() - float(state["request_started_at"])) * 1000.0 >= _INVENTORY_QUERY_TIMEOUT_MS:
                    PySystem.Console.Log(
                        MODULE_NAME,
                        f"[Statistics] Inventory query timed out for {request['label']} on {_account_label(str(request['key']))}.",
                        PySystem.Console.MessageType.Warning,
                    )
                    state["request_index"] = request_index + 1
                    state["waiting"] = False
                    continue

                return BehaviorTree.NodeState.RUNNING

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
    global _current_run_time

    _total_runs = 0
    _total_run_time = 0.0
    _fastest_run = float("inf")
    _slowest_run = 0.0
    _current_run_time = 0.0

    for index in range(5):
        _floor_total_time[index] = 0.0
        _floor_fastest[index] = float("inf")
        _floor_slowest[index] = 0.0
        _current_floor_times[index] = 0.0

    for tracker_key, tracker in FROSTMAW_DROP_TRACKERS.items():
        drops_section = str(tracker["drops_section"])
        keys = set(_drop_totals[tracker_key]) | set(_settings.items(drops_section).keys())
        for key in keys:
            if key == "local":
                continue
            _drop_totals[tracker_key][key] = 0
            _settings.set(drops_section, key, 0)

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
        enable_party_wipe_recovery=True,
        heroai_state_logging=False,
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
    return BTShared.SendAndWait(
        command=SharedCommandType.TravelToMap,
        params=(
            float(map_id),
            float(INVENTORY_TRAVEL_REGION),
            float(INVENTORY_TRAVEL_DISTRICT),
            float(INVENTORY_TRAVEL_LANGUAGE),
        ),
        include_self=True,
        refs_blackboard_key=refs_key,
        timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
        poll_interval_ms=250,
        log=True,
    )


def _return_all_accounts_to_sifhalla(attempt_key: str) -> BehaviorTree:
    """Return the active party to Sifhalla only when inventory maintenance is required.

    Normal dungeon loops stay in Jaga Moraine and keep the existing party intact.
    If maintenance is triggered from an explorable, resign the multibox party back
    to Sifhalla; fall back to direct shared travel if resign is not applicable.
    """
    already_in_sifhalla = BT.Sequence(
        name="Already In Sifhalla For Inventory Maintenance",
        children=[
            BT.IsCurrentMap(map_id=SIFHALLA, log=False),
            BT.Succeeder("Inventory Maintenance Already In Sifhalla"),
        ],
    )

    currently_in_explorable = BT.Selector(
        name="Current Frostmaw Map Can Be Resigned",
        children=[
            BT.IsCurrentMap(map_id=JAGA_MORAINE, log=False),
            *[BT.IsCurrentMap(map_id=map_id, log=False) for map_id in DUNGEON_MAPS],
        ],
    )

    resign_to_sifhalla = BT.Sequence(
        name="Resign Party To Sifhalla",
        children=[
            currently_in_explorable,
            BT.Resign(
                wait_for_map_load=True,
                target_map_id=SIFHALLA,
                multi_account=True,
                timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
                log=True,
            ),
            BT.WaitForMapLoad(map_id=SIFHALLA, timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS),
        ],
    )

    travel_to_sifhalla = _travel_all_accounts(
        SIFHALLA,
        f"{attempt_key}_travel_sifhalla",
    )

    return BT.Selector(
        name="Ensure Party Is In Sifhalla For Inventory Maintenance",
        children=[already_in_sifhalla, resign_to_sifhalla, travel_to_sifhalla],
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
                            _return_all_accounts_to_sifhalla("inventory_maintenance_setup"),
                            BT.LeaveParty(),
                            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
                            BT.Selector(name="MerchantRules Attempts", children=attempts),
                        ],
                    ),
                ],
            ),
        ],
    )
    return BT.Selector(name="Optional Inventory Maintenance", children=[disabled, enabled])


def UseAvailableSummoningStone(level_key: str) -> BehaviorTree:
    """Broadcast a best-effort summon request without blocking the planner."""

    def _send(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if not _use_summoning_stone or not _consumables_allowed():
            return BehaviorTree.NodeState.SUCCESS

        sender_email = str(Player.GetAccountEmail() or "").strip()
        recipients = _inventory_recipient_emails()
        if not sender_email or not recipients:
            return BehaviorTree.NodeState.SUCCESS

        for recipient_email in recipients:
            try:
                GLOBAL_CACHE.ShMem.SendMessage(
                    sender_email,
                    recipient_email,
                    SharedCommandType.UseSummoningStone,
                    (0.0, 0.0, 0.0, 0.0),
                    (f"{MODULE_NAME}:{level_key}", "", "", ""),
                )
            except Exception as exc:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"Summoning stone request skipped for {recipient_email}: {exc}",
                    PySystem.Console.MessageType.Warning,
                )

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Use Summoning Stone {level_key}",
            action_fn=_send,
            aftercast_ms=0,
        )
    )


class _PauseWhilePartyNotAliveNode(BehaviorTree.Node):
    """Freeze the current run step while any party member is dead.

    The child is not reset while blocked. HeroAI and BottingTree background
    services keep running, so resurrection/recovery can happen independently;
    once every party member is alive, the exact current child resumes.
    """

    def __init__(self, child: BehaviorTree | BehaviorTree.Node, *, name: str) -> None:
        super().__init__(name=name, node_type="PartyAliveGate", node_category="decorator")
        self.child = self._coerce_node(child)
        self._blocked = False
        self._last_block_key = ""

    def get_children(self) -> list[BehaviorTree.Node]:
        return [self.child]

    def reset(self) -> None:
        super().reset()
        self.child.reset()
        self._blocked = False
        self._last_block_key = ""

    @staticmethod
    def _party_member_agent_ids() -> tuple[list[int], int]:
        try:
            if not Map.IsMapReady() or not Party.IsPartyLoaded():
                return [], 0

            expected_size = max(0, int(Party.GetPartySize() or 0))
            agent_ids: list[int] = []
            seen: set[int] = set()

            for player in Party.GetPlayers() or []:
                login_number = int(getattr(player, "login_number", 0) or 0)
                if login_number <= 0:
                    continue
                agent_id = int(Party.Players.GetAgentIDByLoginNumber(login_number) or 0)
                if agent_id > 0 and agent_id not in seen:
                    seen.add(agent_id)
                    agent_ids.append(agent_id)

            for member in Party.GetHeroes() or []:
                agent_id = int(getattr(member, "agent_id", 0) or 0)
                if agent_id > 0 and agent_id not in seen:
                    seen.add(agent_id)
                    agent_ids.append(agent_id)

            for member in Party.GetHenchmen() or []:
                agent_id = int(getattr(member, "agent_id", 0) or 0)
                if agent_id > 0 and agent_id not in seen:
                    seen.add(agent_id)
                    agent_ids.append(agent_id)

            return agent_ids, expected_size
        except Exception:
            return [], 0

    @staticmethod
    def _member_label(agent_id: int) -> str:
        try:
            name = str(Agent.GetNameByID(int(agent_id)) or "").strip()
            if name:
                return name
        except Exception:
            pass
        return f"agent {int(agent_id)}"

    def _tick_impl(self) -> BehaviorTree.NodeState:
        # Let the wrapped transition handle map loading normally.
        try:
            map_ready = bool(Map.IsMapReady())
            party_loaded = bool(Party.IsPartyLoaded()) if map_ready else False
        except Exception:
            map_ready = False
            party_loaded = False

        if not map_ready or not party_loaded:
            if self.blackboard is not None:
                self.child.blackboard = self.blackboard
            return self.child.tick()

        member_ids, expected_size = self._party_member_agent_ids()

        # Do not advance if the party mirror is temporarily incomplete.
        if expected_size > 0 and len(member_ids) < expected_size:
            block_key = f"unresolved:{len(member_ids)}/{expected_size}"
            if self._last_block_key != block_key:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[PartyAlive] Pausing run progression: party state incomplete ({len(member_ids)}/{expected_size} members resolved).",
                    PySystem.Console.MessageType.Warning,
                )
                self._last_block_key = block_key
            self._blocked = True
            return BehaviorTree.NodeState.RUNNING

        dead_ids: list[int] = []
        for agent_id in member_ids:
            try:
                if Agent.IsDead(int(agent_id)):
                    dead_ids.append(int(agent_id))
            except Exception:
                continue

        if dead_ids:
            dead_labels = tuple(self._member_label(agent_id) for agent_id in dead_ids)
            block_key = "dead:" + "|".join(dead_labels)
            if self._last_block_key != block_key:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[PartyAlive] Pausing current run step until every party member is alive. Dead: {', '.join(dead_labels)}.",
                    PySystem.Console.MessageType.Warning,
                )
                self._last_block_key = block_key
            self._blocked = True
            return BehaviorTree.NodeState.RUNNING

        if self._blocked:
            PySystem.Console.Log(
                MODULE_NAME,
                "[PartyAlive] Every party member is alive. Resuming current run step.",
                PySystem.Console.MessageType.Success,
            )
            self._blocked = False
            self._last_block_key = ""

        if self.blackboard is not None:
            self.child.blackboard = self.blackboard
        return self.child.tick()


def _guard_run_step(
    step_name: str,
    factory: Callable[[], BehaviorTree],
) -> tuple[str, Callable[[], BehaviorTree]]:
    """Wrap one planner step with the per-tick party-alive gate."""

    def _build() -> BehaviorTree:
        child = factory()
        return BehaviorTree(
            _PauseWhilePartyNotAliveNode(
                child,
                name=f"Party Alive Guard - {step_name}",
            )
        )

    return step_name, _build


def _map_guarded_point(
    name: str,
    map_id: int,
    child: BehaviorTree,
    skip_if_in_maps: Sequence[int] = (),
) -> BehaviorTree:
    """Run one planner step on its expected floor or skip it if a later floor is loaded."""
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
                    BT.Succeeder(f"{name} Already Passed"),
                ],
            )
        )

    return branches[0] if len(branches) == 1 else BT.Selector(name=name, children=branches)


def _vanquish_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[Vec2f],
    *,
    clear_area_radius: float = Range.Spirit.value,
    skip_if_in_maps: Sequence[int] = (),
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Expose every waypoint as a real MultiAccountSequence planner step."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []
    for index, point in enumerate(points, start=1):
        step_name = f"{prefix} - Point {index:02d}"
        steps.append(
            (
                step_name,
                lambda point=point, step_name=step_name: _map_guarded_point(
                    name=step_name,
                    map_id=map_id,
                    child=BT.VanquishNode(
                        [point],
                        name=step_name,
                        clear_area_radius=clear_area_radius,
                        pause_on_combat=True,
                        log=False,
                    ),
                    skip_if_in_maps=skip_if_in_maps,
                ),
            )
        )
    return steps


def _gadget_id_present(gadget_id: int, origin: Vec2f | None = None, radius: float = 5_000.0) -> bool:
    radius_sq = float(radius) * float(radius)
    for agent_id in AgentArray.GetGadgetArray() or []:
        agent_id = int(agent_id)
        try:
            if int(Agent.GetGadgetID(agent_id) or 0) != int(gadget_id):
                continue
            if origin is None:
                return True
            x, y = Agent.GetXY(agent_id)
            dx = float(x) - float(origin[0])
            dy = float(y) - float(origin[1])
            if dx * dx + dy * dy <= radius_sq:
                return True
        except Exception:
            continue
    return False


def _draw_run_config() -> None:
    global _use_hard_mode, _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons, _use_summoning_stone, _auto_loot
    global _inventory_maintenance_enabled, _inventory_min_free_slots
    global _inventory_min_id_kits, _inventory_min_salvage_kits

    _load_settings()
    changed = False
    upkeep_changed = False

    for label, variable_name, affects_upkeep in (
        ("Hard Mode (HM)", "_use_hard_mode", False),
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

    def _avg_time(total: float) -> str:
        return _fmt_time(total / _total_runs) if _total_runs > 0 else "--:--"

    def _drop_rate(runs: int, drops: int) -> str:
        return f"{drops / runs * 100.0:.1f}%" if runs > 0 and drops > 0 else "-"

    table_flags = (
        PyImGui.TableFlags.Borders
        | PyImGui.TableFlags.RowBg
        | PyImGui.TableFlags.SizingFixedFit
        | PyImGui.TableFlags.NoHostExtendX
    )
    header_color = 26 | (38 << 8) | (51 << 16) | (255 << 24)
    column_width = 58.0
    row_height = 22.0

    def _header_row(labels: tuple[str, ...]) -> None:
        PyImGui.table_next_row(0, row_height)
        PyImGui.table_set_bg_color(2, header_color, -1)
        for index, label in enumerate(labels):
            PyImGui.table_set_column_index(index)
            PyImGui.text(label)

    PyImGui.text_colored("Frostmaw's Burrows Statistics", gold)
    PyImGui.separator()
    PyImGui.spacing()

    _scramble_accounts = PyImGui.checkbox("Hide Account Names", _scramble_accounts)

    tracker_keys = list(FROSTMAW_DROP_TRACKERS)
    session_totals = {key: sum(_session_drops[key].values()) for key in tracker_keys}
    all_time_totals = {key: sum(_drop_totals[key].values()) for key in tracker_keys}

    overview_labels: list[str] = ["Runs"]
    for key in tracker_keys:
        short = str(FROSTMAW_DROP_TRACKERS[key]["short"])
        overview_labels.extend((short, f"{short}%"))

    PyImGui.text_colored("Session Overview", cyan)
    if PyImGui.begin_table("##frostmaw_bt_session", len(overview_labels), table_flags):
        for label in overview_labels:
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
        _header_row(tuple(overview_labels))
        values: list[object] = [_session_runs]
        for key in tracker_keys:
            values.extend((session_totals[key], _drop_rate(_session_runs, session_totals[key])))
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Total Overview", cyan)
    if PyImGui.begin_table("##frostmaw_bt_all_time", len(overview_labels), table_flags):
        for label in overview_labels:
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
        _header_row(tuple(overview_labels))
        values = [_total_runs]
        for key in tracker_keys:
            values.extend((all_time_totals[key], _drop_rate(_total_runs, all_time_totals[key])))
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Run Timings", cyan)
    if PyImGui.begin_table("##frostmaw_bt_timings", 5, table_flags):
        for label in ("Floor", "Current", "Avg", "Best", "Worst"):
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, 72.0)
        _header_row(("Floor", "Current", "Avg", "Best", "Worst"))

        now = time.monotonic()
        run_active = _t_run_start > 0.0
        timing_rows: list[tuple[str, float, bool, float, float, float]] = [
            (
                "Overall",
                now - _t_run_start if run_active else _current_run_time,
                run_active,
                _total_run_time,
                _fastest_run,
                _slowest_run,
            )
        ]

        for index in range(5):
            start = _t_floor_starts[index]
            next_start = _t_floor_starts[index + 1] if index < 4 else 0.0
            is_live = start > 0.0 and (index == 4 or next_start <= 0.0)
            current = now - start if is_live else _current_floor_times[index]
            timing_rows.append(
                (
                    f"Floor {index + 1}",
                    current,
                    is_live,
                    _floor_total_time[index],
                    _floor_fastest[index],
                    _floor_slowest[index],
                )
            )

        for label, current, is_live, total, fastest, slowest in timing_rows:
            PyImGui.table_next_row(0, row_height)
            PyImGui.table_set_column_index(0)
            PyImGui.text(label)
            PyImGui.table_set_column_index(1)
            if is_live:
                PyImGui.text_colored(_fmt_time(current), live)
            else:
                PyImGui.text(_fmt_time(current))
            PyImGui.table_set_column_index(2)
            PyImGui.text(_avg_time(total))
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

    def _draw_drop_table(
        table_id: str,
        title: str,
        session_values: dict[str, int],
        all_time_values: dict[str, int],
    ) -> None:
        PyImGui.spacing()
        PyImGui.text_colored(title, cyan)
        if not PyImGui.begin_table(table_id, 4, table_flags):
            return

        PyImGui.table_setup_column("Account", PyImGui.TableColumnFlags.WidthStretch)
        for label in ("Session", "All Time", "Drop Rate"):
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, 72.0)
        _header_row(("Account", "Session", "All Time", "Drop Rate"))

        keys = sorted(set(session_values) | set(all_time_values))
        session_total = 0
        all_time_total = 0
        for key in keys:
            session_count = session_values.get(key, 0)
            all_time_count = all_time_values.get(key, 0)
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

    for tracker_key, tracker in FROSTMAW_DROP_TRACKERS.items():
        _draw_drop_table(
            f"##frostmaw_{tracker_key}_drops",
            f"{tracker['label']} Drops",
            _session_drops[tracker_key],
            _drop_totals[tracker_key],
        )


DWARVEN_BLESSING_DIALOG = 0x84
SIFHALLA = 643
JAGA_MORAINE = 546
FROSTMAW_L1 = 630
FROSTMAW_L2 = 631
FROSTMAW_L3 = 632
FROSTMAW_L4 = 633
FROSTMAW_L5 = 634
BURROWS_CHEST_GADGET_ID = 8926
BURROWS_CHEST_POSITION = Vec2f(15514.00, -16373.00)

JAGA_ROUTE = [Vec2f(-9202.36, -21590.34), Vec2f(-8010.68, -18935.76), Vec2f(-8116.08, -14579.48), Vec2f(-8425.41, -12548.05), Vec2f(-8450.02, -10128.42), Vec2f(-8887.21, -7362.70), Vec2f(-6935.84, -5517.69), Vec2f(-4784.04, -3020.46), Vec2f(-4081.30, 174.96), Vec2f(-1113.24, 2075.98), Vec2f(602.50, 4852.32), Vec2f(605.76, 810.73), Vec2f(15.75, 10129.33), Vec2f(887.83, 13275.95), Vec2f(2001.30, 16280.64), Vec2f(2807.11, 18958.18), Vec2f(1972.66, 21732.93), Vec2f(1278.18, 24506.75)]
L1_ROUTE = [Vec2f(-15326.62, 17240.07), Vec2f(-14654.82, 16460.37), Vec2f(-13949.08, 15526.11), Vec2f(-13290.34, 15118.21), Vec2f(-12589.15, 16123.14), Vec2f(-12942.74, 14284.69), Vec2f(-12534.54, 13983.46), Vec2f(-12130.02, 13416.32), Vec2f(-10692.78, 11887.72), Vec2f(-11035.61, 12018.64), Vec2f(-10552.88, 12086.03), Vec2f(-10692.78, 11887.72), Vec2f(-11035.61, 12018.64), Vec2f(-10552.88, 12086.03)]
L2_ROUTE_A = [Vec2f(18851.07, -3966.53), Vec2f(17812.88, -4577.16), Vec2f(16836.19, -5152.30), Vec2f(16511.35, -6024.33), Vec2f(14824.19, -7040.45), Vec2f(13579.67, -7094.05), Vec2f(12395.61, -6901.50), Vec2f(11993.82, -7825.46), Vec2f(12066.84, -8798.73), Vec2f(12204.84, -9669.14), Vec2f(11179, -10788)]
L2_ROUTE_B = [Vec2f(12148.27, -10747.60), Vec2f(13428.25, -11445.93), Vec2f(13927.18, -12038.94), Vec2f(13997.46, -12528.07), Vec2f(14364.43, -14158.62), Vec2f(14034.07, -14417.76), Vec2f(14057.38, -15872.44), Vec2f(13841.90, -16372.93), Vec2f(13766.07, -17628.01), Vec2f(13953.39, -18542.89), Vec2f(13839.18, -18765.72)]
L3_ROUTE_A = [Vec2f(-17459.51, 10531.91), Vec2f(-16190.60, 11567.74), Vec2f(-15289.93, 11778.42), Vec2f(-14153.34, 12479.54), Vec2f(-12732.61, 13419.55), Vec2f(-10719.29, 14748.05), Vec2f(-10265.08, 15693.50), Vec2f(-8828.57, 15625.13), Vec2f(-8027.84, 14726.56), Vec2f(-7173.30, 14729.47), Vec2f(-6570.46, 14762.64), Vec2f(-5327.02, 14781.65), Vec2f(-4519.06, 14765.36), Vec2f(-3534.68, 15449.94), Vec2f(-1744.74, 17095.78),]
L3_ROUTE_B = [Vec2f(-1445.65, 16684.29), Vec2f(-258.55, 16408.79), Vec2f(22.50, 16289.21), Vec2f(458.91, 14844.25), Vec2f(987.77, 13940.77), Vec2f(2399.96, 13809.41), Vec2f(3997.43, 13437.99), Vec2f(4433.23, 13325.33), Vec2f(4395.41, 14271.70), Vec2f(4773.84, 14988.33), Vec2f(5673.85, 16152.36), Vec2f(7003.23, 16494.92), Vec2f(8159.75, 16750.51), Vec2f(9134.46, 17175.69), Vec2f(11395.14, 16781.35), Vec2f(12839.31, 16404.43), Vec2f(13848.74, 15766.62), Vec2f(14333.85, 15421.58), Vec2f(14112.61, 16961.38), Vec2f(15827.45, 16530.45)]
L4_ROUTE_A = [Vec2f(-13087.91, 16576.76), Vec2f(-11646.38, 15979.65), Vec2f(-12038.07, 15542.13), Vec2f(-13102.65, 15093.05), Vec2f(-12492.21, 14034.73), Vec2f(-13412.09, 13083.65), Vec2f(-14569.28, 11555.54), Vec2f(-14902.39, 9114.88), Vec2f(-16357.17, 9664.09), Vec2f(-17804.09, 8819.00), Vec2f(-18193.83, 8235.71), Vec2f(-19156.21, 7575.98), Vec2f(-19156.33, 5526.35), Vec2f(-18564.30, 4238.94), Vec2f(-17711.28, 2641.45), Vec2f(-16315.27, 2405.68), Vec2f(-15340.94, 2635.77), Vec2f(-14133.86, 1802.69), Vec2f(-13983.26, 601.52), Vec2f(-13329.61, -1080.57),]
L4_ROUTE_B = [Vec2f(-12753.33, -2681.69), Vec2f(-12894.02, -4285.28), Vec2f(-13119.36, -5947.45), Vec2f(-13013.19, -6519.09), Vec2f(-14280.20, -6142.41), Vec2f(-13293.21, -7833.95), Vec2f(-14090.45, -9543.70), Vec2f(-14637.39, -9662.75), Vec2f(-14597.26, -10095.21), Vec2f(-15842.62, -11754.90), Vec2f(-15666.06, -12007.23)]
L5_BOSS_ROUTE = [Vec2f(3469.12, -15729.53), Vec2f(2831.19, -14456.42), Vec2f(4773.45, -13949.30), Vec2f(5919.47, -13205.37), Vec2f(7033.25, -12410.89), Vec2f(8492.01, -13719.10), Vec2f(11087.41, -17307.95), Vec2f(12834.36, -17376.27), Vec2f(14552.52, -17537.88), Vec2f(15227.87, -15399.86), Vec2f(17991.94, -16068.67), Vec2f(16184.52, -16735.55), Vec2f(14465.54, -17302.57), Vec2f(15317.18, -15975.95), Vec2f(14552.52, -17537.88), Vec2f(15227.87, -15399.86), Vec2f(17991.94, -16068.67)]


def PrepareRun() -> BehaviorTree:
    already_inside = BT.Selector(
        name="Already Inside Frostmaw",
        children=[BT.IsCurrentMap(map_id=map_id, log=False) for map_id in DUNGEON_MAPS],
    )

    prepare = BT.Sequence(
        name="Prepare Frostmaw Run",
        children=[
            _travel_all_accounts(SIFHALLA, "frostmaw_start"),
            InventoryCheckAndMaintenance(),
            BT.CreateParty(multibox_invite=True, timeout_ms=30_000, log=True),
            BT.AbandonQuest(quest_id=QUEST_ID, multi_account=True, include_self=True, timeout_ms=10_000, log=True),
            _runtime_difficulty_node(),
            _runtime_restock_node(),
            _runtime_consumable_upkeep_node(False),
        ],
    )
    return BT.Selector(name="Prepare Run Or Resume", children=[already_inside, prepare])


def TravelFrostmaw() -> BehaviorTree:
    already_inside = BT.Selector(
        name="Frostmaw Travel",
        children=[BT.IsCurrentMap(map_id=map_id, log=False) for map_id in DUNGEON_MAPS],
    )

    normal_entry = BT.Sequence(
        name="Sifhalla To Frostmaw",
        children=[
            _runtime_consumable_upkeep_node(False),
            BT.Move(
                [Vec2f(14732.36, 22591.97), Vec2f(16172.98, 22806.55)],
                pause_on_combat=False,
                log=False,
            ),
            BT.MoveAndExitMap(Vec2f(16900, 22830), target_map_id=JAGA_MORAINE, log=True),
            BT.MoveAndDialog(Vec2f(-9153.42, -22776.35),dialog_id=DWARVEN_BLESSING_DIALOG, multi_account=True),
            BT.VanquishNode(
                JAGA_ROUTE,
                name="Jaga Moraine Route",
                clear_area_radius=Range.Spirit.value,
                pause_on_combat=True,
                log=False,
            ),
            BT.Move(Vec2f(646.48, 24899.17), pause_on_combat=False, log=False),
            BT.MoveAndDialog(
                Vec2f(1025.91, 25481.72),
                dialog_id=0x832A01,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(QUEST_ID, timeout_ms=15_000),
            BT.Move(
                [Vec2f(1556.26, 24963.88), Vec2f(1723.61, 25814.54)],
                pause_on_combat=False,
                log=False,
            ),
            
            _runtime_consumable_upkeep_node(True),
        ],
    )
    return BT.Selector(name="Enter Frostmaw", children=[already_inside, normal_entry])


def EnterFrostmaw(enable_consumables_on_entry: bool=True) -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Dungeon Entry - Already In Level 1",
        children=[
            BT.IsCurrentMap(map_id=FROSTMAW_L1, log=True),
            BT.IsQuestState(quest_id=QUEST_ID, state="active", log=True),
            BT.Succeeder("DungeonEntryAlreadyDone"),
        ],
    )
    normal_entry = BT.Sequence(
        name="Enter Frostmaw From Jaga Moraine",
        children=[
            BT.Move(Vec2f(1700, 26400), pause_on_combat=False, ignore_destination_obstacles=True, log=False),
            BT.WaitForMapLoad(map_id=FROSTMAW_L1, timeout_ms=60_000),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
        ],
    )
    entry = BT.Selector(children=[already_inside, normal_entry], name='Enter Frostmaw')

    if not enable_consumables_on_entry:
        return entry

    return BT.Sequence(name='Enter Frostmaw And Resume Consumables', children=[entry, _runtime_consumable_upkeep_node(True)])    

def Level1_Start() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 1 Start",
        map_id=FROSTMAW_L1,
        child=BT.Sequence(
            name="Frostmaw Level 1 Start",
            children=[
                _mark_run_start_node(),
                _inventory_statistics_node(after_chest=False),
                UseAvailableSummoningStone("l1"),
                BT.MoveAndDialog(Vec2f(-16144.88, 17615.97),dialog_id=DWARVEN_BLESSING_DIALOG, multi_account=True),
            ],
        ),
        skip_if_in_maps=(FROSTMAW_L2, FROSTMAW_L3, FROSTMAW_L4, FROSTMAW_L5),
    )


def Level1_EnterLevel2() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 1 Enter Level 2",
        map_id=FROSTMAW_L1,
        child=BT.Sequence(
            name="Enter Frostmaw Level 2",
            children=[
                BT.MoveAndExitMap(Vec2f(-10800, 11050), target_map_id=FROSTMAW_L2, log=True),
                BT.WaitForMapLoad(map_id=FROSTMAW_L2, timeout_ms=60_000),
                BT.WaitUntilOnExplorable(timeout_ms=30_000),
            ],
        ),
        skip_if_in_maps=(FROSTMAW_L2, FROSTMAW_L3, FROSTMAW_L4, FROSTMAW_L5),
    )


def Level2_Start() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 2 Start",
        map_id=FROSTMAW_L2,
        child=BT.Sequence(
            name="Frostmaw Level 2 Start",
            children=[
                _mark_floor_start_node(2),
                UseAvailableSummoningStone("l2"),
                BT.MoveAndDialog(Vec2f(19083.29, -3100.83), dialog_id=DWARVEN_BLESSING_DIALOG,multi_account=True),
            ],
        ),
        skip_if_in_maps=(FROSTMAW_L3, FROSTMAW_L4, FROSTMAW_L5),
    )


def Level2_MidBlessing() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 2 Mid Blessing",
        map_id=FROSTMAW_L2,
        child=BT.MoveAndDialog(Vec2f(10720.54, -10235.50),dialog_id=DWARVEN_BLESSING_DIALOG, multi_account=True),
        skip_if_in_maps=(FROSTMAW_L3, FROSTMAW_L4, FROSTMAW_L5),
    )


def Level2_EnterLevel3() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 2 Enter Level 3",
        map_id=FROSTMAW_L2,
        child=BT.Sequence(
            name="Enter Frostmaw Level 3",
            children=[
                BT.MoveAndExitMap(Vec2f(13950, -19400), target_map_id=FROSTMAW_L3, log=True),
                BT.WaitForMapLoad(map_id=FROSTMAW_L3, timeout_ms=60_000),
                BT.WaitUntilOnExplorable(timeout_ms=30_000),
            ],
        ),
        skip_if_in_maps=(FROSTMAW_L3, FROSTMAW_L4, FROSTMAW_L5),
    )


def Level3_Start() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 3 Start",
        map_id=FROSTMAW_L3,
        child=BT.Sequence(
            name="Frostmaw Level 3 Start",
            children=[
                _mark_floor_start_node(3),
                UseAvailableSummoningStone("l3"),
                BT.MoveAndDialog(Vec2f(-18533.34, 9900.28) ,dialog_id=DWARVEN_BLESSING_DIALOG,multi_account=True),
            ],
        ),
        skip_if_in_maps=(FROSTMAW_L4, FROSTMAW_L5),
    )


def Level3_MidBlessing() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 3 Mid Blessing",
        map_id=FROSTMAW_L3,
        child=BT.MoveAndDialog(Vec2f(-1467.34, 18940.29) ,dialog_id=DWARVEN_BLESSING_DIALOG,multi_account=True),
        skip_if_in_maps=(FROSTMAW_L4, FROSTMAW_L5),
    )


def Level3_EnterLevel4() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 3 Enter Level 4",
        map_id=FROSTMAW_L3,
        child=BT.Sequence(
            name="Enter Frostmaw Level 4",
            children=[
                BT.MoveAndExitMap(Vec2f(18400, 15800), target_map_id=FROSTMAW_L4, log=True),
                BT.WaitForMapLoad(map_id=FROSTMAW_L4, timeout_ms=60_000),
                BT.WaitUntilOnExplorable(timeout_ms=30_000),
            ],
        ),
        skip_if_in_maps=(FROSTMAW_L4, FROSTMAW_L5),
    )


def Level4_Start() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 4 Start",
        map_id=FROSTMAW_L4,
        child=BT.Sequence(
            name="Frostmaw Level 4 Start",
            children=[
                _mark_floor_start_node(4),
                UseAvailableSummoningStone("l4"),
                BT.MoveAndDialog(Vec2f(-13809.59, 16850.71) ,dialog_id=DWARVEN_BLESSING_DIALOG,multi_account=True),
            ],
        ),
        skip_if_in_maps=(FROSTMAW_L5,),
    )


def Level4_MidBlessing() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 4 Mid Blessing",
        map_id=FROSTMAW_L4,
        child=BT.MoveAndDialog(Vec2f(-12082.09, -1269.08) ,dialog_id=DWARVEN_BLESSING_DIALOG,multi_account=True),
        skip_if_in_maps=(FROSTMAW_L5,),
    )


def Level4_EnterLevel5() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 4 Enter Level 5",
        map_id=FROSTMAW_L4,
        child=BT.Sequence(
            name="Enter Frostmaw Level 5",
            children=[
                BT.MoveAndExitMap(Vec2f(-16500, -12600), target_map_id=FROSTMAW_L5, log=True),
                BT.WaitForMapLoad(map_id=FROSTMAW_L5, timeout_ms=60_000),
                BT.WaitUntilOnExplorable(timeout_ms=30_000),
            ],
        ),
        skip_if_in_maps=(FROSTMAW_L5,),
    )


def Level5_Start() -> BehaviorTree:
    return BT.Sequence(
        name="Frostmaw Level 5 Start",
        children=[
            BT.IsCurrentMap(map_id=FROSTMAW_L5, log=True),
            _mark_floor_start_node(5),
            UseAvailableSummoningStone("l5"),
            BT.MoveAndDialog(Vec2f(3928.42, -18217.92) ,dialog_id=DWARVEN_BLESSING_DIALOG,multi_account=True),
        ],
    )


def Level5_OpenChest() -> BehaviorTree:
    chest_pos = BURROWS_CHEST_POSITION
    return BT.Sequence(
        name="Open Burrows Chest And Collect Reward",
        children=[
            BT.IsCurrentMap(map_id=FROSTMAW_L5, log=True),
            _runtime_consumable_upkeep_node(False),
            _record_run_end_node(),
            BT.MoveAndInteractWithGadget(
                gadget_id=BURROWS_CHEST_GADGET_ID,
                pos=chest_pos,
                search_distance=Range.Compass.value,
                interaction_distance=Range.Nearby.value,
                interaction_count=2,
                interaction_interval_ms=750,
                account_settle_ms=1_500,
                timeout_ms=30_000,
                pause_on_combat=False,
                multi_account=True,
                include_self=True,
                log=True,
            ),
            BT.Wait(2_000),
            _inventory_statistics_node(after_chest=True),
        ],
    )

def WaitForLathamInside(timeout_ms: int=30000) -> BehaviorTree:
    """Wait until Latham is resolvable by name inside the dungeon."""

    def _check(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        agent_id = Agent.GetAgentIDByName("Latham")

        if agent_id != 0:
            node.blackboard["latham_agent_id"] = agent_id
            return BehaviorTree.NodeState.SUCCESS

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.WaitUntilNode(name='Wait For Latham Inside Dungeon', condition_fn=_check, throttle_interval_ms=500, timeout_ms=timeout_ms))


def CollectInsideReward() -> BehaviorTree:
    """
    Collect the Cold Vengeance reward from Latham inside the dungeon.

    Wait until Latham is actually resolvable by name before targeting her.
    The lookup is retried every 500 ms for up to 30 seconds, without logging
    each internal attempt.
    """
    return BT.Sequence(
        name="Collect Inside Reward",
        children=[
            WaitForLathamInside(
                timeout_ms=30_000,
            ),
            BT.TargetAgentByName(agent_name='Latham', log=True),
            BT.LogMessage(message='Latham was found near the final chest. Attempting to collect the Cold Vengeance reward.', module_name=MODULE_NAME),
            BT.InteractTargetAndSendDialog(dialog_id=0x832A07, multi_account=True, log=True),
            BT.SendDialog(dialog_id=0x832A07, multi_account=True, log=True),
            BT.WaitForQuestCleared(QUEST_ID, timeout_ms=15000),
        ],
    )

def CollectRewardAndReturnToJaga(end_countdown_timeout_ms: int=190000) -> BehaviorTree:
    already_in_jaga = BT.Sequence(
        name="Skip Inside Reward - Already In Jaga Moraine",
        children=[
            BT.IsCurrentMap(map_id=JAGA_MORAINE, log=True),
            BT.LogMessage(message='The party is already in Jaga Moraine. Skipping the inside reward search and resuming the restart preparation.', module_name=MODULE_NAME),
            BT.Succeeder('InsideRewardAlreadyReturnedToJaga'),
        ],
    )

    reward_collected_inside = BT.Sequence(
        name="Collect Latham Reward Inside Dungeon",
        children=[
            # Do not gate the Latham lookup behind IsQuestState("complete").
            # TargetAgentByName works independently, while the quest-state mirror
            # can still report "active" for a short time after Frostmaw/chest.  If
            # Latham is present, try her directly and let WaitForQuestCleared be
            # the source of truth for whether the reward was actually collected.
            BT.IsCurrentMap(map_id=FROSTMAW_L5, log=True),
            BT.LogMessage(message='Level 5 confirmed after Frostmaw. Looking for Latham by name inside the dungeon.', module_name=MODULE_NAME),
            CollectInsideReward(),
            BT.WaitForQuestCleared(QUEST_ID, timeout_ms=15000),
            BT.LogMessage(message='Latham was found inside the dungeon and the Cold Vengeance reward was collected.', module_name=MODULE_NAME),
        ],
    )

    reward_not_collected_inside = BT.Sequence(
        name="Latham Unavailable Inside Dungeon",
        children=[
            BT.LogMessage(message='Latham was not found inside the dungeon or the inside reward could not be collected. The reward will be handled in Jaga Moraine.', module_name=MODULE_NAME),
            BT.Succeeder('InsideRewardUnavailable'),
        ],
    )

    return BT.Sequence(
        name="Collect Reward And Return To Jaga Moraine",
        children=[
            _runtime_consumable_upkeep_node(False),
            BT.Selector(name='Resolve Inside Reward', children=[already_in_jaga, reward_collected_inside, reward_not_collected_inside]),
            BT.LogMessage(message='Waiting for the end-of-dungeon countdown and the return to Jaga Moraine.', module_name=MODULE_NAME),
            BT.WaitForMapLoad(map_id=JAGA_MORAINE, timeout_ms=end_countdown_timeout_ms),
            BT.WaitUntilOnExplorable(timeout_ms=30000),
            BT.Wait(2000),
            BT.LogMessage(message='The party has returned to Jaga Moraine. Preparing the next dungeon run.', module_name=MODULE_NAME),
            BT.Move(Vec2f(1025.91, 25481.72), pause_on_combat=False, log=False),
        ],
    )


def ResolveLathamQuestAfterRun() -> BehaviorTree:
    """Resolve Cold Vengeance after the automatic return to Jaga Moraine.

    Two distinct flows are required:

    1) Reward collected from Latham inside Level 5:
       wait for the automatic return to Jaga Moraine, then retake Cold Vengeance
       directly from Latham. No Level 1 reset is needed.

    2) Reward could not be collected inside Level 5:
       wait for Jaga Moraine, collect the pending reward from Latham, enter
       Level 1 once, exit back to Jaga Moraine, then retake Cold Vengeance.
    """

    quest_already_active = BT.Sequence(
        name="Keep Active Cold Vengeance Quest",
        children=[
            BT.IsQuestState(quest_id=QUEST_ID, state="active", log=True),
            BT.LogMessage(
                message="Cold Vengeance is already active for the next run.",
                module_name=MODULE_NAME,
            ),
        ],
    )

    # If the reward was successfully collected inside Level 5, the quest is
    # cleared/missing when the party returns to Jaga Moraine. In this case
    # Latham can be used directly to retake Cold Vengeance.
    reward_collected_inside = BT.Sequence(
        name="Retake Cold Vengeance After Inside Reward",
        children=[
            BT.IsQuestState(quest_id=QUEST_ID, state="missing", log=True),
            BT.LogMessage(
                message=(
                    "Cold Vengeance reward was collected inside the dungeon. "
                    "Retaking the quest from Latham in Jaga Moraine."
                ),
                module_name=MODULE_NAME,
            ),
            BT.MoveAndDialog(
                Vec2f(1025.91, 25481.72),
                dialog_id=0x832A01,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(QUEST_ID, timeout_ms=15_000),
        ],
    )

    # If Latham could not be used inside the dungeon, Cold Vengeance remains
    # complete when Jaga Moraine loads. Collect the reward outside, then perform
    # the same Level 1 entry/exit reset used by Shandra before retaking the quest.
    reward_not_collected_inside = BT.Sequence(
        name="Collect Outside Reward Reset Latham And Retake Cold Vengeance",
        children=[
            BT.IsQuestState(quest_id=QUEST_ID, state="complete", log=True),
            BT.LogMessage(
                message=(
                    "Cold Vengeance reward is still pending. Collecting it from "
                    "Latham in Jaga Moraine before resetting the quest offer."
                ),
                module_name=MODULE_NAME,
            ),
            BT.MoveAndDialog(
                Vec2f(1025.91, 25481.72),
                dialog_id=0x832A07,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForQuestCleared(QUEST_ID, timeout_ms=15_000),

            BT.LogMessage(
                message=(
                    "Reward collected in Jaga Moraine. Entering and leaving "
                    "Level 1 once before retaking Cold Vengeance."
                ),
                module_name=MODULE_NAME,
            ),
            EnterFrostmaw(enable_consumables_on_entry=False),
            BT.MoveAndExitMap(
                Vec2f(-17505, 18508),
                target_map_id=JAGA_MORAINE,
                log=False,
            ),
            BT.WaitForMapLoad(map_id=JAGA_MORAINE, timeout_ms=60_000),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),

            BT.MoveAndDialog(
                Vec2f(1025.91, 25481.72),
                dialog_id=0x832A01,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(QUEST_ID, timeout_ms=15_000),
        ],
    )

    return BT.Sequence(
        name="Resolve Latham Quest After Run",
        children=[
            # Never try to resolve the next quest before the automatic dungeon
            # return has completed.
            BT.IsCurrentMap(map_id=JAGA_MORAINE, log=True),
            BT.Selector(
                name="Resolve Cold Vengeance State In Jaga Moraine",
                children=[
                    quest_already_active,
                    reward_collected_inside,
                    reward_not_collected_inside,
                ],
            ),
            BT.IsQuestState(quest_id=QUEST_ID, state="active", log=True),
        ],
    )

def PrepareNextDungeonRun() -> BehaviorTree:
    already_inside = BT.Sequence(name='Next Run Already Entered', children=[BT.IsCurrentMap(map_id=FROSTMAW_L1, log=True), BT.IsQuestState(quest_id=QUEST_ID, state='active', log=True)])

    continue_from_jaga = BT.Sequence(
        name='Enter Next Run From Jaga Moraine',
        children=[
            BT.IsCurrentMap(map_id=JAGA_MORAINE, log=True),
            BT.IsQuestState(quest_id=QUEST_ID, state='active', log=True),
            # Normal loop: keep the party created at startup. No reform, no
            # outpost-only restock; simply re-enter Frostmaw with Cold Vengeance active.
            EnterFrostmaw(),
        ],
    )

    continue_after_maintenance = BT.Sequence(
        name="Reform Party And Enter Next Run From Sifhalla",
        children=[
            BT.IsCurrentMap(map_id=SIFHALLA, log=True),
            BT.IsQuestState(quest_id=QUEST_ID, state='active', log=True),
            BT.CreateParty(multibox_invite=True, timeout_ms=30000, log=True),
            _runtime_difficulty_node(),
            _runtime_restock_node(),
            TravelFrostmaw(),
            EnterFrostmaw(),
        ],
    )

    return BT.Selector(name='Prepare Next Dungeon Run', children=[already_inside, continue_from_jaga, continue_after_maintenance])



def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    guarded_run_steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        ("Travel To Frostmaw", TravelFrostmaw),
        ("Enter Frostmaw", EnterFrostmaw),

        ("Level 1 Start", Level1_Start),
        *_vanquish_point_steps("Level 1 Route",FROSTMAW_L1,L1_ROUTE,skip_if_in_maps=(FROSTMAW_L2,FROSTMAW_L3,FROSTMAW_L4,FROSTMAW_L5,),),
        ("Level 1 Enter Level 2", Level1_EnterLevel2),

        ("Level 2 Start", Level2_Start),
        *_vanquish_point_steps("Level 2 Route A",FROSTMAW_L2,L2_ROUTE_A,skip_if_in_maps=(FROSTMAW_L3,FROSTMAW_L4,FROSTMAW_L5,),),
        ("Level 2 Mid Blessing", Level2_MidBlessing),
        *_vanquish_point_steps("Level 2 Route B",FROSTMAW_L2,L2_ROUTE_B,skip_if_in_maps=(FROSTMAW_L3,FROSTMAW_L4,FROSTMAW_L5,),),
        ("Level 2 Enter Level 3", Level2_EnterLevel3),

        ("Level 3 Start", Level3_Start),
        *_vanquish_point_steps("Level 3 Route A",FROSTMAW_L3,L3_ROUTE_A,skip_if_in_maps=(FROSTMAW_L4,FROSTMAW_L5,),),
        ("Level 3 Mid Blessing", Level3_MidBlessing),
        *_vanquish_point_steps("Level 3 Route B",FROSTMAW_L3,L3_ROUTE_B,skip_if_in_maps=(FROSTMAW_L4,FROSTMAW_L5,),),
        ("Level 3 Enter Level 4", Level3_EnterLevel4),

        ("Level 4 Start", Level4_Start),
        *_vanquish_point_steps(
        "Level 4 Route A",FROSTMAW_L4,L4_ROUTE_A,skip_if_in_maps=(FROSTMAW_L5,),),
        ("Level 4 Mid Blessing", Level4_MidBlessing),
        *_vanquish_point_steps("Level 4 Route B",FROSTMAW_L4,L4_ROUTE_B,skip_if_in_maps=(FROSTMAW_L5,),),
        ("Level 4 Enter Level 5", Level4_EnterLevel5),
        ("Level 5 Start", Level5_Start),*_vanquish_point_steps("Level 5 Boss Route",FROSTMAW_L5,L5_BOSS_ROUTE,),
        ("Open Burrows Chest", Level5_OpenChest),
    ]

    return [
        ("Initialize Bot", InitializeBot),
        ("Prepare Party And Supplies", PrepareRun),

        *(_guard_run_step(step_name, factory)for step_name, factory in guarded_run_steps),

        ("Collect Reward And Return To Jaga", CollectRewardAndReturnToJaga),
        ("Resolve Latham Quest", ResolveLathamQuestAfterRun),
        ("Inventory Check And Maintenance", InventoryCheckAndMaintenance),
        ("Prepare Next Dungeon Run", PrepareNextDungeonRun),
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
            configure_fn=lambda tree: tree.Config.ConfigureUpkeep(
                looting_enabled=_auto_loot,
                resurrection_scroll=True,
                auto_inventory_handler_enabled=True,
                consumable_upkeeps=_enabled_consumable_upkeeps(),
                enable_party_wipe_recovery=True,
                heroai_state_logging=False,
            ),
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
    tree.UI.draw_window(
        main_child_dimensions=(430, 390),
        extra_tabs=[("Statistics", _draw_statistics), ("Config", _draw_run_config)],
    )


if __name__ == "__main__":
    main()
