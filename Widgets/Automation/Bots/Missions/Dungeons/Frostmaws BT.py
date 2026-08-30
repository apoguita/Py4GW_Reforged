# Frostmaw's Burrows BottingTree conversion.
# Uses native BT wrappers directly and exposes every dungeon waypoint as a planner step.

from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import time

import PySystem
import PyImGui

from Py4GWCoreLib import Agent, AgentArray, GLOBAL_CACHE, Inventory, Map, Party, Player, SharedCommandType, ImGui
from Py4GWCoreLib.ImGui_src.types import Alignment
from Py4GWCoreLib.py4gwcorelib_src.Color import Color
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.Listeners import Listeners
from Py4GWCoreLib.enums import CONSUMABLE_MODELID_TO_EFFECT_NAME
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

TEXTURE = os.path.join(PySystem.Console.get_projects_path(), 'Assets', 'Textures', 'Module_Icons', 'Frostmaws2.png')
MODULE_ICON = 'Assets\\Textures\\Module_Icons\\Frostmaws2.png'
MODULE_NAME = "Frostmaw's Burrows BT"
INI_PATH = 'Widgets/Automation/Bots/Missions/Dungeons/Frostmaws Burrows BT'
INI_FILENAME = 'Frostmaws_Burrows_BT.ini'

START_OUTPOST = 643
SURFACE_MAPS = (546,)
DUNGEON_MAPS = (630, 631, 632, 633, 634)
QUEST_ID = 0x32A
GREAT_TEMPLE_OF_BALTHAZAR = 248

# Frozen Soil / Terre gelee. Verified in Frostmaw runtime:
# effect/skill ID 471, hostile spirit model ID 2933.
FROZEN_SOIL_EFFECT_ID = 471
FROZEN_SOIL_SPIRIT_MODEL_ID = 2933
FROZEN_SOIL_CALL_TARGET_RESEND_MS = 1_000
FROZEN_SOIL_ATTACK_RESEND_MS = 2_500
FROZEN_SOIL_LOCAL_ATTACK_RESEND_MS = 1_000
FROZEN_SOIL_CORPSE_MOVE_TOLERANCE = Range.Nearby.value

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

# Personal consumables are dispatched directly instead of relying on the generic
# ConsumableService recipient resolver.  This keeps PCons reliable with Headless
# HeroAI and across named-planner restarts / dungeon floor transitions.
_PCON_DIRECT_DISPATCH_INTERVAL_MS = 650
PCON_USAGE_LOG = False  # Set True only for PCon consumption diagnostics.
_pcon_direct_index = 0
_pcon_direct_last_dispatch_ms = 0
_pcon_direct_runtime_logged = False
_pcon_direct_unresolved_effects_logged: set[int] = set()
_pcon_direct_last_recipient_signature: tuple[str, ...] = ()
_pcon_direct_morale_remote_index = 0
_PCON_PARTY_MORALE_TARGET_BY_MODEL = {
    int(ModelID.Four_Leaf_Clover.value): 100,
    int(ModelID.Honeycomb.value): 110,
}


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
    """Return generic BottingTree consumable services for the current phase.

    PCons are intentionally NOT returned here.  They are maintained by
    _tick_direct_pcon_upkeep(), which resolves the real multibox party from
    SharedMemory instead of the Headless HeroAI party cache.
    """
    if not _runtime_consumables_enabled:
        return ()

    enabled: list[int] = []
    if _activate_conset:
        enabled.extend(int(model_id) for model_id in CONSET_UPKEEPS)
    return tuple(dict.fromkeys(enabled))


def _pcon_effect_name(model_id: int) -> str:
    """Resolve the effect name sent with SharedCommandType.PCon."""
    model_id = int(model_id)

    # Current ConsumableService presets use these names for rock candy and they
    # are important because UsePcon must receive a non-zero effect id to avoid
    # repeatedly consuming the same candy while its effect is already active.
    overrides = {
        int(ModelID.Blue_Rock_Candy.value): "Blue_Rock_Candy_Rush",
        int(ModelID.Green_Rock_Candy.value): "Green_Rock_Candy_Rush",
        int(ModelID.Red_Rock_Candy.value): "Red_Rock_Candy_Rush",
        int(ModelID.Birthday_Cupcake.value): "Birthday_Cupcake_skill",
        int(ModelID.Bowl_Of_Skalefin_Soup.value): "Skale_Vigor",
        int(ModelID.Candy_Apple.value): "Candy_Apple_skill",
        int(ModelID.Candy_Corn.value): "Candy_Corn_skill",
        int(ModelID.Drake_Kabob.value): "Drake_Skin",
        int(ModelID.Golden_Egg.value): "Golden_Egg_skill",
        int(ModelID.Pahnai_Salad.value): "Pahnai_Salad_item_effect",
        int(ModelID.Slice_Of_Pumpkin_Pie.value): "Pie_Induced_Ecstasy",
        int(ModelID.War_Supplies.value): "Well_Supplied",
    }
    if model_id in overrides:
        return overrides[model_id]
    return str(CONSUMABLE_MODELID_TO_EFFECT_NAME.get(model_id, "") or "")


def _pcon_account_map_tuple(account: object) -> tuple[int, int, int, int]:
    map_obj = getattr(getattr(account, "AgentData", None), "Map", None)
    return (
        int(getattr(account, "MapID", 0) or getattr(map_obj, "MapID", 0) or 0),
        int(getattr(account, "MapRegion", 0) or getattr(map_obj, "Region", 0) or 0),
        int(getattr(account, "MapDistrict", 0) or getattr(map_obj, "District", 0) or 0),
        int(getattr(account, "MapLanguage", 0) or getattr(map_obj, "Language", 0) or 0),
    )


def _pcon_account_party_id(account: object) -> int:
    return int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)


def _direct_pcon_party_emails() -> list[str]:
    """Resolve the real account clients belonging to the leader's current party."""
    local_email = str(Player.GetAccountEmail() or "").strip()
    if not local_email:
        return []

    try:
        local_account = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(local_email)
    except Exception:
        local_account = None

    try:
        accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False) or [])
    except TypeError:
        accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData() or [])
    except Exception:
        accounts = []

    local_party_id = _pcon_account_party_id(local_account) if local_account is not None else 0
    local_map = _pcon_account_map_tuple(local_account) if local_account is not None else None

    # Shared memory can briefly lag during transitions.  PartyID is the primary
    # contract; map identity is only the fallback when PartyID is unavailable.
    result: list[str] = []
    seen: set[str] = set()
    for account in accounts:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        if bool(getattr(account, "IsHero", False)) or bool(getattr(account, "IsNPC", False)):
            continue

        account_party_id = _pcon_account_party_id(account)
        same_party = local_party_id > 0 and account_party_id == local_party_id
        same_map_fallback = (
            local_party_id <= 0
            and local_map is not None
            and _pcon_account_map_tuple(account) == local_map
        )
        if not same_party and not same_map_fallback:
            continue

        seen.add(email)
        result.append(email)

    if local_email not in seen:
        result.append(local_email)
    return result


def _reset_direct_pcon_runtime(*, clear_unresolved: bool = False) -> None:
    global _pcon_direct_index, _pcon_direct_last_dispatch_ms
    global _pcon_direct_runtime_logged, _pcon_direct_last_recipient_signature
    global _pcon_direct_morale_remote_index

    _pcon_direct_index = 0
    _pcon_direct_last_dispatch_ms = 0
    _pcon_direct_runtime_logged = False
    _pcon_direct_last_recipient_signature = ()
    _pcon_direct_morale_remote_index = 0
    if clear_unresolved:
        _pcon_direct_unresolved_effects_logged.clear()


def _bot_is_started() -> bool:
    if botting_tree is None:
        return False
    try:
        fn = getattr(botting_tree, "IsStarted", None)
        if callable(fn):
            return bool(fn())
    except Exception:
        pass
    return bool(getattr(botting_tree, "started", False))


def _shared_party_min_morale_for_direct_pcons() -> int | None:
    """Return the lowest valid shared party morale, or None while unavailable."""
    try:
        entries = GLOBAL_CACHE.ShMem.GetSharedPartyMorale() or []
    except Exception:
        return None

    values: list[int] = []
    for entry in entries:
        try:
            morale = int(entry[1] or 0)
        except (TypeError, ValueError, IndexError):
            continue
        if morale > 0:
            values.append(morale)
    return min(values) if values else None


def _dispatch_party_morale_pcon(model_id: int, recipients: list[str], sender_email: str) -> None:
    """Use one party-wide morale PCon when the shared morale is below its target.

    Only one account is allowed to attempt the party-wide item per service pass;
    this prevents Four-Leaf Clover / Honeycomb from being consumed by several
    multibox clients at the same time before SharedMemory reflects the new morale.
    """
    global _pcon_direct_morale_remote_index

    target_morale = _PCON_PARTY_MORALE_TARGET_BY_MODEL.get(int(model_id))
    if target_morale is None:
        return

    party_min_morale = _shared_party_min_morale_for_direct_pcons()
    if party_min_morale is None or party_min_morale >= int(target_morale):
        return

    local_agent_id = int(Player.GetAgentID() or 0)
    local_is_dead = bool(local_agent_id and Agent.IsDead(local_agent_id))
    if (
        not local_is_dead
        and GLOBAL_CACHE.Inventory.GetModelCount(int(model_id)) > 0
    ):
        item_id = int(GLOBAL_CACHE.Item.GetItemIdFromModelID(int(model_id)) or 0)
        if item_id > 0:
            GLOBAL_CACHE.Inventory.UseItem(item_id)
            if PCON_USAGE_LOG:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f"[PCons] Party morale use: model={int(model_id)}, "
                        f"morale={party_min_morale} -> target={int(target_morale)}."
                    ),
                    PySystem.Console.MessageType.Info,
                )
            return

    remote_recipients = [
        email for email in recipients
        if email and email != sender_email
    ]
    if not remote_recipients:
        return

    # If the leader cannot consume it (dead/missing item), rotate the single
    # remote attempt so another account gets a chance on the next service pass.
    receiver_email = remote_recipients[
        _pcon_direct_morale_remote_index % len(remote_recipients)
    ]
    _pcon_direct_morale_remote_index = (
        _pcon_direct_morale_remote_index + 1
    ) % max(1, len(remote_recipients))

    try:
        GLOBAL_CACHE.ShMem.SendMessage(
            sender_email,
            receiver_email,
            SharedCommandType.PCon,
            (int(model_id), 0, 0, 0),
        )
    except Exception:
        return


def _tick_direct_pcon_upkeep() -> None:
    """Maintain persistent PCons plus party-wide morale consumables directly."""
    global _pcon_direct_index, _pcon_direct_last_dispatch_ms
    global _pcon_direct_runtime_logged, _pcon_direct_last_recipient_signature

    if not _bot_is_started() or not _runtime_consumables_enabled or not _activate_pcons:
        if _pcon_direct_runtime_logged or _pcon_direct_last_dispatch_ms:
            _reset_direct_pcon_runtime()
        return

    try:
        if not Map.IsMapReady() or not Map.IsExplorable():
            return
        if int(Map.GetMapID() or 0) not in DUNGEON_MAPS:
            return
    except Exception:
        return

    if not PCON_UPKEEPS:
        return

    now_ms = int(time.monotonic() * 1000.0)
    if now_ms - int(_pcon_direct_last_dispatch_ms) < _PCON_DIRECT_DISPATCH_INTERVAL_MS:
        return
    _pcon_direct_last_dispatch_ms = now_ms

    recipients = _direct_pcon_party_emails()
    if not recipients:
        return

    recipient_signature = tuple(sorted(recipients))
    if not _pcon_direct_runtime_logged or recipient_signature != _pcon_direct_last_recipient_signature:
        _pcon_direct_runtime_logged = True
        _pcon_direct_last_recipient_signature = recipient_signature
        PySystem.Console.Log(
            MODULE_NAME,
            f"[PCons] Direct multibox upkeep active: models={len(PCON_UPKEEPS)}, accounts={len(recipients)}.",
            PySystem.Console.MessageType.Info,
        )

    model_id = int(PCON_UPKEEPS[_pcon_direct_index % len(PCON_UPKEEPS)])
    _pcon_direct_index = (_pcon_direct_index + 1) % len(PCON_UPKEEPS)

    sender_email = str(Player.GetAccountEmail() or "").strip()
    if not sender_email:
        return

    # Four-Leaf Clover and Honeycomb are morale consumables, not persistent
    # effects.  They are driven by the same party-morale thresholds used by
    # Messaging.UsePcon: Clover <100, Honeycomb <110.
    if model_id in _PCON_PARTY_MORALE_TARGET_BY_MODEL:
        _dispatch_party_morale_pcon(model_id, recipients, sender_email)
        return

    effect_name = _pcon_effect_name(model_id)
    effect_id = int(GLOBAL_CACHE.Skill.GetID(effect_name) or 0) if effect_name else 0
    if effect_id <= 0:
        if model_id not in _pcon_direct_unresolved_effects_logged:
            _pcon_direct_unresolved_effects_logged.add(model_id)
            PySystem.Console.Log(
                MODULE_NAME,
                f"[PCons] Skipping model {model_id}: could not resolve effect '{effect_name or '<none>'}.'",
                PySystem.Console.MessageType.Warning,
            )
        return

    local_agent_id = int(Player.GetAgentID() or 0)
    local_is_dead = bool(local_agent_id and Agent.IsDead(local_agent_id))
    local_has_effect = bool(
        local_agent_id and GLOBAL_CACHE.Effects.HasEffect(local_agent_id, effect_id)
    )
    if (
        not local_is_dead
        and not local_has_effect
        and GLOBAL_CACHE.Inventory.GetModelCount(model_id) > 0
    ):
        item_id = int(GLOBAL_CACHE.Item.GetItemIdFromModelID(model_id) or 0)
        if item_id > 0:
            GLOBAL_CACHE.Inventory.UseItem(item_id)
            if PCON_USAGE_LOG:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[PCons] Local use: model={model_id}, effect={effect_id} ({effect_name}).",
                    PySystem.Console.MessageType.Info,
                )

    # Persistent effects are personal: every remote client receives the same
    # request and Messaging.UsePcon checks its own effect/inventory before use.
    params = (model_id, effect_id, 0, 0)
    for receiver_email in recipients:
        if not receiver_email or receiver_email == sender_email:
            continue
        try:
            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                receiver_email,
                SharedCommandType.PCon,
                params,
            )
        except Exception:
            continue

def _configure_runtime_upkeeps(
    *,
    consumables_enabled: bool | None = None,
    looting_enabled: bool | None = None,
) -> None:
    global _runtime_consumables_enabled, _runtime_looting_enabled
    global _configured_consumable_upkeeps

    previous_runtime_enabled = _runtime_consumables_enabled
    if consumables_enabled is not None:
        _runtime_consumables_enabled = bool(consumables_enabled)
    if looting_enabled is not None:
        _runtime_looting_enabled = bool(looting_enabled)

    if previous_runtime_enabled != _runtime_consumables_enabled:
        _reset_direct_pcon_runtime(clear_unresolved=False)

    if botting_tree is None:
        return

    previous_consumables = _configured_consumable_upkeeps
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

    pcon_count = len(PCON_UPKEEPS) if _runtime_consumables_enabled and _activate_pcons else 0
    if previous_consumables != enabled_consumables or previous_runtime_enabled != _runtime_consumables_enabled:
        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"[Consumables] Runtime {'ON' if _runtime_consumables_enabled else 'OFF'}: "
                f"conset_services={len(enabled_consumables)}, direct_pcons={pcon_count}."
            ),
            PySystem.Console.MessageType.Info,
        )


def _sync_runtime_upkeeps() -> None:
    # Only generic services (currently consets) participate in ConfigureUpkeep.
    # Direct PCons read the live checkbox/runtime flags every frame.
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
    # MerchantRules is intentionally scoped to inventory verification/maintenance.
    # Keeping the widget enabled during normal Frostmaw gameplay has caused client
    # instability, so every path explicitly disables it again before returning.
    disabled = BT.Sequence(
        name="Inventory Maintenance Disabled",
        children=[
            BehaviorTree(
                BehaviorTree.ConditionNode(
                    name="Inventory Maintenance Disabled Check",
                    condition_fn=lambda _node: not _inventory_maintenance_enabled,
                )
            ),
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                False,
                "inventory_disabled_merchant_off",
            ),
        ],
    )

    attempts: list[BehaviorTree] = []
    for attempt in range(1, INVENTORY_MAINTENANCE_RETRY_COUNT + 1):
        key = f"inventory_attempt_{attempt}"

        # The first branch is the normal attempt. If anything in it fails
        # (MerchantRules, refresh query, or threshold validation), the fallback
        # branch restores both widgets and returns FAILURE so the selector can
        # try the next maintenance attempt.
        normal_attempt = BT.Sequence(
            name=f"Inventory Maintenance Attempt {attempt} - Run",
            children=[
                _send_widget_state(
                    INVENTORY_PLUS_WIDGET_NAME,
                    False,
                    f"{key}_inventoryplus_off",
                ),
                _send_widget_state(
                    MERCHANT_RULES_WIDGET_NAME,
                    True,
                    f"{key}_merchant_on",
                ),
                _run_merchant_rules(key),
                _send_widget_state(
                    INVENTORY_PLUS_WIDGET_NAME,
                    True,
                    f"{key}_inventoryplus_on",
                ),
                BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
                _query_all_inventory_states_node(
                    f"Refresh Inventory Attempt {attempt}"
                ),
                _inventory_is_healthy_node(
                    f"Inventory Healthy After Attempt {attempt}"
                ),
                _send_widget_state(
                    MERCHANT_RULES_WIDGET_NAME,
                    False,
                    f"{key}_merchant_off_success",
                ),
            ],
        )

        cleanup_failure = BT.Sequence(
            name=f"Inventory Maintenance Attempt {attempt} - Cleanup Failure",
            children=[
                _send_widget_state(
                    INVENTORY_PLUS_WIDGET_NAME,
                    True,
                    f"{key}_inventoryplus_restore",
                ),
                _send_widget_state(
                    MERCHANT_RULES_WIDGET_NAME,
                    False,
                    f"{key}_merchant_off_failure",
                ),
                BT.Failer(name=f"Inventory Maintenance Attempt {attempt} Failed"),
            ],
        )

        attempts.append(
            BT.Selector(
                name=f"Inventory Maintenance Attempt {attempt}",
                children=[normal_attempt, cleanup_failure],
            )
        )

    # MerchantRules is enabled before the initial inventory verification, then
    # disabled immediately after the threshold decision. If maintenance is
    # required, it stays OFF during resign/travel/party teardown and is only
    # re-enabled inside an actual MerchantRules maintenance attempt.
    healthy_without_maintenance = BT.Sequence(
        name="Inventory Already Healthy",
        children=[
            _inventory_is_healthy_node("Inventory Already Healthy Check"),
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                False,
                "inventory_check_merchant_off_healthy",
            ),
        ],
    )

    maintenance_required = BT.Sequence(
        name="Run MerchantRules Maintenance",
        children=[
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                False,
                "inventory_check_merchant_off_before_maintenance",
            ),
            _return_all_accounts_to_sifhalla("inventory_maintenance_setup"),
            BT.LeaveParty(),
            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
            BT.Selector(name="MerchantRules Attempts", children=attempts),
        ],
    )

    enabled_normal = BT.Sequence(
        name="Inventory Check And Maintenance - Run",
        children=[
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                True,
                "inventory_check_merchant_on",
            ),
            _query_all_inventory_states_node("Query Inventory On All Accounts"),
            BT.Selector(
                name="Inventory Threshold Decision",
                children=[healthy_without_maintenance, maintenance_required],
            ),
        ],
    )

    # Last-resort cleanup: even if a query or maintenance branch fails, do not
    # leave MerchantRules enabled while the bot continues/restarts.
    enabled_cleanup_failure = BT.Sequence(
        name="Inventory Check Failure Cleanup",
        children=[
            _send_widget_state(
                INVENTORY_PLUS_WIDGET_NAME,
                True,
                "inventory_check_inventoryplus_restore",
            ),
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                False,
                "inventory_check_merchant_off_failure",
            ),
            BT.Failer(name="Inventory Check And Maintenance Failed"),
        ],
    )

    enabled = BT.Selector(
        name="Inventory Check And Maintenance",
        children=[enabled_normal, enabled_cleanup_failure],
    )
    return BT.Selector(
        name="Optional Inventory Maintenance",
        children=[disabled, enabled],
    )


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


def _frozen_soil_affected_alive_members(member_ids: Sequence[int]) -> list[int]:
    """Return living party members currently under the Frozen Soil effect."""
    affected: list[int] = []
    for agent_id in member_ids:
        try:
            if not Agent.IsAlive(int(agent_id)):
                continue
            if GLOBAL_CACHE.Effects.HasEffect(int(agent_id), FROZEN_SOIL_EFFECT_ID):
                affected.append(int(agent_id))
        except Exception:
            continue
    return affected


def _find_frozen_soil_spirit(reference_ids: Sequence[int]) -> int:
    """Resolve only the verified Frostmaw Frozen Soil spirit (model 2933).

    Do not fall back to another nearby spirit.  Runtime evidence from Frostmaw
    confirmed model 2933 for Esprit de Terre gelee; the previous generic
    fallback could incorrectly select spirits such as Spirit of Life while the
    Frozen Soil effect was still fading from the party.
    """
    reference_positions: list[tuple[float, float]] = []
    for agent_id in reference_ids:
        try:
            x, y = Agent.GetXY(int(agent_id))
            reference_positions.append((float(x), float(y)))
        except Exception:
            continue

    try:
        spirit_pet_ids = [int(agent_id) for agent_id in (AgentArray.GetSpiritPetArray() or [])]
    except Exception:
        spirit_pet_ids = []
    try:
        enemy_ids = [int(agent_id) for agent_id in (AgentArray.GetEnemyArray() or [])]
    except Exception:
        enemy_ids = []

    ordered_ids: list[int] = []
    seen: set[int] = set()
    for agent_id in (*spirit_pet_ids, *enemy_ids):
        if agent_id <= 0 or agent_id in seen:
            continue
        seen.add(agent_id)
        ordered_ids.append(agent_id)

    candidates: list[tuple[float, int]] = []
    for agent_id in ordered_ids:
        try:
            if not Agent.IsAlive(agent_id):
                continue
            if int(Agent.GetModelID(agent_id) or 0) != FROZEN_SOIL_SPIRIT_MODEL_ID:
                continue
            if reference_positions:
                x, y = Agent.GetXY(agent_id)
                distance_sq = min(
                    (float(x) - rx) ** 2 + (float(y) - ry) ** 2
                    for rx, ry in reference_positions
                )
            else:
                distance_sq = 0.0
            candidates.append((distance_sq, agent_id))
        except Exception:
            continue

    if not candidates:
        return 0
    candidates.sort()
    return int(candidates[0][1])


def _frozen_soil_spirit_scan_summary(reference_ids: Sequence[int]) -> str:
    """Compact one-shot diagnostics when the spirit still cannot be resolved."""
    try:
        ids = [int(agent_id) for agent_id in (AgentArray.GetSpiritPetArray() or [])]
    except Exception:
        ids = []

    reference_positions: list[tuple[float, float]] = []
    for reference_id in reference_ids:
        try:
            x, y = Agent.GetXY(int(reference_id))
            reference_positions.append((float(x), float(y)))
        except Exception:
            continue

    details: list[str] = []
    for agent_id in ids[:8]:
        try:
            name = str(Agent.GetNameByID(agent_id) or "?").strip() or "?"
            model_id = int(Agent.GetModelID(agent_id) or 0)
            is_spirit = bool(Agent.IsSpirit(agent_id))
            alive = bool(Agent.IsAlive(agent_id))
            x, y = Agent.GetXY(agent_id)
            distance = 0.0
            if reference_positions:
                distance = min(
                    ((float(x) - rx) ** 2 + (float(y) - ry) ** 2) ** 0.5
                    for rx, ry in reference_positions
                )
            details.append(
                f"id={agent_id} model={model_id} spirit={int(is_spirit)} alive={int(alive)} d={distance:.0f} name={name}"
            )
        except Exception:
            continue
    return f"SpiritPetArray={len(ids)}" + (" | " + " ; ".join(details) if details else "")


def _send_frozen_soil_call_target(target_id: int) -> tuple[bool, str]:
    """Call the verified Frozen Soil spirit as the party target.

    HeroAI in the current Reforged tree has a dedicated call-target subsystem,
    while the runtime exposed no HeroAICommandAPI.focus method.  Calling the
    target is therefore the next live test: the leader script can still select
    and call an agent while its character is dead, and the other clients can
    react to the party target call.
    """
    target_id = int(target_id)
    if target_id <= 0:
        return False, "invalid target"

    try:
        if int(Player.GetTargetID() or 0) != target_id:
            Player.ChangeTarget(target_id)
    except Exception as exc:
        return False, f"ChangeTarget failed: {exc}"

    try:
        Player.CallTarget(target_id)
        return True, f"CallTarget({target_id})"
    except Exception as exc:
        return False, f"CallTarget failed: {exc}"


def _frozen_soil_account_clients_alive() -> list[tuple[str, int, str]]:
    """Return living real player clients in the leader's current party/map.

    Heroes and NPC slots are intentionally excluded: remote commands are sent to
    actual game clients only.  The local player is included when alive so the
    caller can decide whether to execute locally or through SharedMemory.
    """
    local_email = str(Player.GetAccountEmail() or "").strip()
    if not local_email:
        return []

    try:
        local_account = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(local_email)
    except Exception:
        local_account = None

    try:
        accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False) or [])
    except TypeError:
        accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData() or [])
    except Exception:
        accounts = []

    local_party_id = _pcon_account_party_id(local_account) if local_account is not None else 0
    local_map = _pcon_account_map_tuple(local_account) if local_account is not None else None

    # Fall back to the live map signature if the local shared slot has not
    # published its map yet.
    if not local_map or int(local_map[0] or 0) <= 0:
        try:
            local_map = (
                int(Map.GetMapID() or 0),
                int(Map.GetRegion()[0] or 0),
                int(Map.GetDistrict() or 0),
                int(Map.GetLanguage()[0] or 0),
            )
        except Exception:
            local_map = None

    result: list[tuple[str, int, str]] = []
    seen: set[str] = set()
    for account in accounts:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        if bool(getattr(account, "IsHero", False)) or bool(getattr(account, "IsNPC", False)):
            continue

        account_party_id = _pcon_account_party_id(account)
        account_map = _pcon_account_map_tuple(account)
        same_party = local_party_id > 0 and account_party_id == local_party_id
        same_map_fallback = local_party_id <= 0 and local_map is not None and account_map == local_map
        if not same_party and not same_map_fallback:
            continue

        # A stale same-party slot from a loading/outpost transition must not be
        # ordered to interact with an agent from another instance.
        if local_map is not None and int(account_map[0] or 0) > 0 and account_map != local_map:
            continue

        agent_data = getattr(account, "AgentData", None)
        agent_id = int(getattr(agent_data, "AgentID", 0) or 0)
        if agent_id <= 0:
            continue
        try:
            if not Agent.IsAlive(agent_id):
                continue
        except Exception:
            continue

        label = str(getattr(agent_data, "CharacterName", "") or "").strip() or "player client"
        seen.add(email)
        result.append((email, agent_id, label))

    # Shared memory can briefly omit the local slot even though the local
    # character is usable. Add it explicitly when alive.
    if local_email not in seen:
        local_agent_id = int(Player.GetAgentID() or 0)
        try:
            local_alive = local_agent_id > 0 and Agent.IsAlive(local_agent_id)
        except Exception:
            local_alive = False
        if local_alive:
            try:
                local_label = str(Player.GetName() or "").strip() or "local player"
            except Exception:
                local_label = "local player"
            result.append((local_email, local_agent_id, local_label))

    return result


def _shared_command_ref_is_active(
    sender_email: str,
    receiver_email: str,
    message_index: int,
    command: SharedCommandType,
) -> bool:
    """Return True while one previously dispatched SharedMemory command is active."""
    if int(message_index) < 0:
        return False
    try:
        message = GLOBAL_CACHE.ShMem.GetInbox(int(message_index))
    except Exception:
        return False
    if message is None:
        return False
    try:
        return bool(
            getattr(message, "Active", False)
            and str(getattr(message, "SenderEmail", "") or "") == str(sender_email or "")
            and str(getattr(message, "ReceiverEmail", "") or "") == str(receiver_email or "")
            and int(getattr(message, "Command", -1)) == int(command)
        )
    except Exception:
        return False


def _dispatch_frozen_soil_attack(
    target_id: int,
    *,
    remote_refs: dict[str, tuple[int, int]],
    now_ms: int,
    last_local_attack_ms: int,
) -> tuple[int, int, int]:
    """Force living player clients to start attacking Frozen Soil.

    CallTarget is only a party ping.  The actual attack trigger is Interact on
    the local living client and SharedCommandType.InteractWithTarget on each
    living remote client. Messaging then changes/moves to the supplied agent and
    executes InteractAgent on that client.

    Returns (new_last_local_attack_ms, remote_sent_count, living_client_count).
    """
    target_id = int(target_id)
    if target_id <= 0:
        return int(last_local_attack_ms), 0, 0

    sender_email = str(Player.GetAccountEmail() or "").strip()
    if not sender_email:
        return int(last_local_attack_ms), 0, 0

    clients = _frozen_soil_account_clients_alive()
    remote_sent = 0

    for receiver_email, _agent_id, _label in clients:
        if receiver_email == sender_email:
            if now_ms - int(last_local_attack_ms) < FROZEN_SOIL_LOCAL_ATTACK_RESEND_MS:
                continue
            try:
                if int(Player.GetTargetID() or 0) != target_id:
                    Player.ChangeTarget(target_id)
                Player.Interact(target_id, False)
                last_local_attack_ms = now_ms
            except Exception as exc:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[FrozenSoil] Local attack trigger failed for agent {target_id}: {exc}.",
                    PySystem.Console.MessageType.Warning,
                )
            continue

        previous = remote_refs.get(receiver_email)
        if previous is not None:
            previous_index, previous_sent_ms = previous
            if _shared_command_ref_is_active(
                sender_email,
                receiver_email,
                previous_index,
                SharedCommandType.InteractWithTarget,
            ):
                continue
            if now_ms - int(previous_sent_ms) < FROZEN_SOIL_ATTACK_RESEND_MS:
                continue

        try:
            message_index = int(
                GLOBAL_CACHE.ShMem.SendMessage(
                    sender_email,
                    receiver_email,
                    SharedCommandType.InteractWithTarget,
                    (float(target_id), 0.0, 0.0, 0.0),
                    ("Frozen Soil emergency attack", "", "", ""),
                )
            )
        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[FrozenSoil] Remote attack dispatch failed for {_label}: {exc}.",
                PySystem.Console.MessageType.Warning,
            )
            continue

        if message_index >= 0:
            remote_refs[receiver_email] = (message_index, now_ms)
            remote_sent += 1

    return int(last_local_attack_ms), int(remote_sent), len(clients)


class _PauseWhilePartyNotAliveNode(BehaviorTree.Node):
    """Freeze the current run step while any party member is dead.

    Frostmaw special case: if a living party member is under Frozen Soil while
    somebody is dead, call the verified Frozen Soil spirit and explicitly force
    every living player client to interact/attack it. Once model 2933 is gone,
    regroup heroes/accounts at the closest corpse so HeroAI can resurrect, clear
    the temporary flags, then resume the exact wrapped planner child.
    """

    def __init__(self, child: BehaviorTree | BehaviorTree.Node, *, name: str) -> None:
        super().__init__(name=name, node_type="PartyAliveGate", node_category="decorator")
        self.child = self._coerce_node(child)
        self._blocked = False
        self._last_block_key = ""
        self._last_call_target_id = 0
        self._last_call_target_send_ms = 0
        self._call_target_failure_key = ""
        self._frozen_soil_was_blocking = False
        self._frozen_soil_attack_refs: dict[str, tuple[int, int]] = {}
        self._last_local_frozen_soil_attack_ms = 0
        self._last_attack_dispatch_log_ms = 0
        self._frozen_soil_spirit_gone = False
        self._tracked_frozen_soil_id = 0
        self._corpse_recovery_active = False
        self._corpse_recovery_target_id = 0
        self._corpse_recovery_move_node: BehaviorTree.Node | None = None
        self._corpse_recovery_flag_node: BehaviorTree.Node | None = None
        self._corpse_recovery_unflag_node: BehaviorTree.Node | None = None
        self._corpse_recovery_flagged = False

    def get_children(self) -> list[BehaviorTree.Node]:
        return [self.child]

    def reset(self) -> None:
        super().reset()
        self.child.reset()
        self._blocked = False
        self._last_block_key = ""
        self._last_call_target_id = 0
        self._last_call_target_send_ms = 0
        self._call_target_failure_key = ""
        self._frozen_soil_was_blocking = False
        self._frozen_soil_attack_refs: dict[str, tuple[int, int]] = {}
        self._last_local_frozen_soil_attack_ms = 0
        self._last_attack_dispatch_log_ms = 0
        self._frozen_soil_spirit_gone = False
        self._tracked_frozen_soil_id = 0
        self._corpse_recovery_active = False
        self._corpse_recovery_target_id = 0
        self._corpse_recovery_move_node = None
        self._corpse_recovery_flag_node = None
        self._corpse_recovery_unflag_node = None
        self._corpse_recovery_flagged = False

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

    @staticmethod
    def _select_recovery_corpse(dead_ids: Sequence[int]) -> int:
        """Choose the dead member closest to any living real player client."""
        corpse_ids = [int(agent_id) for agent_id in dead_ids if int(agent_id) > 0]
        if not corpse_ids:
            return 0

        reference_positions: list[tuple[float, float]] = []
        for _email, agent_id, _label in _frozen_soil_account_clients_alive():
            try:
                x, y = Agent.GetXY(int(agent_id))
                reference_positions.append((float(x), float(y)))
            except Exception:
                continue

        if not reference_positions:
            try:
                local_agent_id = int(Player.GetAgentID() or 0)
                if local_agent_id > 0:
                    x, y = Agent.GetXY(local_agent_id)
                    reference_positions.append((float(x), float(y)))
            except Exception:
                pass

        candidates: list[tuple[float, int]] = []
        for corpse_id in corpse_ids:
            try:
                x, y = Agent.GetXY(corpse_id)
                if reference_positions:
                    distance_sq = min(
                        (float(x) - rx) ** 2 + (float(y) - ry) ** 2
                        for rx, ry in reference_positions
                    )
                else:
                    distance_sq = 0.0
                candidates.append((distance_sq, corpse_id))
            except Exception:
                continue

        if not candidates:
            return int(corpse_ids[0])
        candidates.sort()
        return int(candidates[0][1])

    @classmethod
    def _living_party_grouped_at_corpse(cls, corpse_x: float, corpse_y: float) -> bool:
        """Return True once every living party member is close enough to the recovery corpse."""
        member_ids, expected_size = cls._party_member_agent_ids()
        if not member_ids:
            return False
        if expected_size > 0 and len(member_ids) < expected_size:
            return False

        tolerance_sq = float(FROZEN_SOIL_CORPSE_MOVE_TOLERANCE) ** 2
        living_count = 0
        for agent_id in member_ids:
            try:
                if not Agent.IsAlive(int(agent_id)):
                    continue
                living_count += 1
                member_x, member_y = Agent.GetXY(int(agent_id))
                distance_sq = (float(member_x) - corpse_x) ** 2 + (float(member_y) - corpse_y) ** 2
                if distance_sq > tolerance_sq:
                    return False
            except Exception:
                return False

        return living_count > 0

    def _reset_corpse_recovery_nodes(self, *, keep_active: bool = False) -> None:
        for node in (
            self._corpse_recovery_move_node,
            self._corpse_recovery_flag_node,
        ):
            if node is None:
                continue
            try:
                node.reset()
            except Exception:
                pass
        self._corpse_recovery_move_node = None
        self._corpse_recovery_flag_node = None
        self._corpse_recovery_target_id = 0
        if not keep_active:
            self._corpse_recovery_active = False

    def _request_corpse_recovery_unflag(self) -> bool:
        """Clear local + multibox recovery flags before normal planner movement resumes."""
        if not self._corpse_recovery_flagged:
            self._corpse_recovery_unflag_node = None
            return True

        if self._corpse_recovery_unflag_node is None:
            try:
                self._corpse_recovery_unflag_node = self._coerce_node(BT.UnflagAllHeroes())
            except Exception as exc:
                try:
                    Party.Heroes.UnflagAllHeroes()
                except Exception:
                    pass
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[FrozenSoil] Could not build recovery unflag tree: {exc}.",
                    PySystem.Console.MessageType.Warning,
                )
                self._corpse_recovery_flagged = False
                return True

        try:
            if self.blackboard is not None:
                self._corpse_recovery_unflag_node.blackboard = self.blackboard
            state = self._corpse_recovery_unflag_node.tick()
        except Exception as exc:
            try:
                Party.Heroes.UnflagAllHeroes()
            except Exception:
                pass
            PySystem.Console.Log(
                MODULE_NAME,
                f"[FrozenSoil] Recovery unflag failed: {exc}.",
                PySystem.Console.MessageType.Warning,
            )
            self._corpse_recovery_flagged = False
            self._corpse_recovery_unflag_node = None
            return True

        if state == BehaviorTree.NodeState.RUNNING:
            return False

        self._corpse_recovery_flagged = False
        self._corpse_recovery_unflag_node = None
        return True

    def _cancel_corpse_recovery_for_new_spirit(self) -> None:
        """Stop corpse regrouping if a new Frozen Soil spirit appears."""
        self._reset_corpse_recovery_nodes()
        if self._corpse_recovery_flagged:
            # Best effort immediately; attack dispatch must not be delayed by flags
            # that still point to the previous corpse position.
            try:
                Party.Heroes.UnflagAllHeroes()
            except Exception:
                pass
            try:
                unflag_node = self._coerce_node(BT.UnflagAllHeroes())
                if self.blackboard is not None:
                    unflag_node.blackboard = self.blackboard
                unflag_node.tick()
            except Exception:
                pass
            self._corpse_recovery_flagged = False
            self._corpse_recovery_unflag_node = None

    def _tick_corpse_recovery(self, dead_ids: Sequence[int]) -> None:
        """Move/flag the surviving party back to a corpse so HeroAI can resurrect."""
        if not self._corpse_recovery_active:
            return

        corpse_id = self._select_recovery_corpse(dead_ids)
        if corpse_id <= 0:
            return

        try:
            corpse_x, corpse_y = Agent.GetXY(corpse_id)
            corpse_x = float(corpse_x)
            corpse_y = float(corpse_y)
        except Exception:
            return

        if corpse_id != self._corpse_recovery_target_id:
            self._reset_corpse_recovery_nodes(keep_active=True)
            self._corpse_recovery_target_id = int(corpse_id)

            # Flag heroes and HeroAI-controlled accounts directly on the corpse.
            # This also works when the local party leader is the dead member and
            # therefore cannot walk there himself.
            try:
                self._corpse_recovery_flag_node = self._coerce_node(
                    BT.FlagAllHeroes(corpse_x, corpse_y)
                )
                self._corpse_recovery_flagged = True
            except Exception as exc:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[FrozenSoil] Could not flag party to corpse {corpse_id}: {exc}.",
                    PySystem.Console.MessageType.Warning,
                )

            PySystem.Console.Log(
                MODULE_NAME,
                f"[FrozenSoil] Spirit down; regrouping at {self._member_label(corpse_id)} "
                f"(agent={corpse_id}) so HeroAI can resurrect.",
                PySystem.Console.MessageType.Info,
            )

        if self._corpse_recovery_flag_node is not None:
            try:
                if self.blackboard is not None:
                    self._corpse_recovery_flag_node.blackboard = self.blackboard
                flag_state = self._corpse_recovery_flag_node.tick()
                if flag_state != BehaviorTree.NodeState.RUNNING:
                    self._corpse_recovery_flag_node = None
            except Exception:
                self._corpse_recovery_flag_node = None

        # Once all living players/heroes have reached the corpse, release the
        # recovery flag immediately. Keeping the party flagged until the dead
        # member is resurrected can prevent HeroAI-controlled characters from
        # moving freely enough to cast resurrection skills. If several members
        # are dead, the next corpse selection will create a new regroup flag.
        if self._corpse_recovery_flagged and self._living_party_grouped_at_corpse(corpse_x, corpse_y):
            if self._request_corpse_recovery_unflag():
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[FrozenSoil] Regroup complete at {self._member_label(corpse_id)}; recovery flags cleared for HeroAI resurrection.",
                    PySystem.Console.MessageType.Success,
                )
            return

        local_agent_id = int(Player.GetAgentID() or 0)
        try:
            local_alive = local_agent_id > 0 and Agent.IsAlive(local_agent_id)
        except Exception:
            local_alive = False

        if not local_alive:
            return

        try:
            local_x, local_y = Agent.GetXY(local_agent_id)
            distance_sq = (float(local_x) - corpse_x) ** 2 + (float(local_y) - corpse_y) ** 2
            if distance_sq <= float(FROZEN_SOIL_CORPSE_MOVE_TOLERANCE) ** 2:
                return
        except Exception:
            pass

        if self._corpse_recovery_move_node is None:
            try:
                self._corpse_recovery_move_node = self._coerce_node(
                    BT.Move(
                        Vec2f(corpse_x, corpse_y),
                        pause_on_combat=False,
                        tolerance=FROZEN_SOIL_CORPSE_MOVE_TOLERANCE,
                        flag_heroes_to_waypoint=False,
                        log=False,
                        ignore_destination_obstacles=True,
                    )
                )
            except Exception as exc:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[FrozenSoil] Could not build corpse recovery move: {exc}.",
                    PySystem.Console.MessageType.Warning,
                )
                return

        try:
            if self.blackboard is not None:
                self._corpse_recovery_move_node.blackboard = self.blackboard
            move_state = self._corpse_recovery_move_node.tick()
            if move_state == BehaviorTree.NodeState.FAILURE:
                self._corpse_recovery_move_node = None
        except Exception:
            self._corpse_recovery_move_node = None

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
            affected_alive_ids = _frozen_soil_affected_alive_members(member_ids)

            if affected_alive_ids:
                frozen_soil_id = _find_frozen_soil_spirit(affected_alive_ids)
                if frozen_soil_id > 0:
                    # A verified Frozen Soil spirit is present again. If a previous
                    # one had disappeared while effect 471 was lingering, stop any
                    # corpse regroup flags and resume the emergency attack flow.
                    if self._corpse_recovery_active or self._corpse_recovery_flagged:
                        self._cancel_corpse_recovery_for_new_spirit()
                    self._frozen_soil_spirit_gone = False
                    self._tracked_frozen_soil_id = int(frozen_soil_id)
                    spirit_name = self._member_label(frozen_soil_id)
                    try:
                        spirit_model = int(Agent.GetModelID(frozen_soil_id) or 0)
                    except Exception:
                        spirit_model = 0
                    block_key = f"frozen_soil:{frozen_soil_id}:dead:" + "|".join(dead_labels)
                    if self._last_block_key != block_key:
                        PySystem.Console.Log(
                            MODULE_NAME,
                            f"[FrozenSoil] Resurrection blocked. Calling target {spirit_name} "
                            f"(agent={frozen_soil_id}, model={spirit_model}) while dead: {', '.join(dead_labels)}.",
                            PySystem.Console.MessageType.Warning,
                        )
                        self._last_block_key = block_key

                    now_ms = int(time.monotonic() * 1000.0)
                    if (
                        frozen_soil_id != self._last_call_target_id
                        or now_ms - self._last_call_target_send_ms >= FROZEN_SOIL_CALL_TARGET_RESEND_MS
                    ):
                        sent, detail = _send_frozen_soil_call_target(frozen_soil_id)
                        if sent:
                            self._last_call_target_id = frozen_soil_id
                            self._last_call_target_send_ms = now_ms
                            self._call_target_failure_key = ""
                            PySystem.Console.Log(
                                MODULE_NAME,
                                f"[FrozenSoil] Party target call sent for agent {frozen_soil_id}: {detail}.",
                                PySystem.Console.MessageType.Info,
                            )
                        else:
                            failure_key = f"{frozen_soil_id}:{detail}"
                            if failure_key != self._call_target_failure_key:
                                PySystem.Console.Log(
                                    MODULE_NAME,
                                    f"[FrozenSoil] Party target call failed: {detail}.",
                                    PySystem.Console.MessageType.Error,
                                )
                                self._call_target_failure_key = failure_key
                            self._last_call_target_send_ms = now_ms

                    (
                        self._last_local_frozen_soil_attack_ms,
                        remote_attack_sent,
                        living_client_count,
                    ) = _dispatch_frozen_soil_attack(
                        frozen_soil_id,
                        remote_refs=self._frozen_soil_attack_refs,
                        now_ms=now_ms,
                        last_local_attack_ms=self._last_local_frozen_soil_attack_ms,
                    )
                    if (
                        remote_attack_sent > 0
                        or now_ms - self._last_attack_dispatch_log_ms >= 5_000
                    ):
                        PySystem.Console.Log(
                            MODULE_NAME,
                            f"[FrozenSoil] Attack dispatch active for agent {frozen_soil_id}: "
                            f"living_clients={living_client_count}, remote_commands={remote_attack_sent}.",
                            PySystem.Console.MessageType.Info,
                        )
                        self._last_attack_dispatch_log_ms = now_ms

                    self._frozen_soil_was_blocking = True
                    self._blocked = True
                    return BehaviorTree.NodeState.RUNNING

                # Effect 471 can linger very briefly after Frozen Soil dies. Once
                # we had a verified model 2933 and it disappears from SpiritPetArray,
                # stop issuing CallTarget / attack commands immediately instead of
                # waiting for the effect cache to refresh.
                if self._tracked_frozen_soil_id > 0 and not self._frozen_soil_spirit_gone:
                    previous_target_id = int(self._tracked_frozen_soil_id)
                    self._frozen_soil_spirit_gone = True
                    self._last_call_target_id = 0
                    self._last_call_target_send_ms = 0
                    self._call_target_failure_key = ""
                    self._frozen_soil_attack_refs.clear()
                    self._last_local_frozen_soil_attack_ms = 0
                    self._last_attack_dispatch_log_ms = 0
                    self._corpse_recovery_active = True
                    self._last_block_key = "frozen_soil:spirit_gone:dead:" + "|".join(dead_labels)
                    PySystem.Console.Log(
                        MODULE_NAME,
                        f"[FrozenSoil] Spirit model {FROZEN_SOIL_SPIRIT_MODEL_ID} "
                        f"(agent={previous_target_id}) is gone; stopping CallTarget/attack dispatch immediately.",
                        PySystem.Console.MessageType.Success,
                    )
                elif self._tracked_frozen_soil_id <= 0:
                    # We see effect 471 but have not yet resolved a verified model
                    # 2933 in this recovery episode. Keep one diagnostic only.
                    block_key = "frozen_soil:no_hostile_spirit:dead:" + "|".join(dead_labels)
                    if self._last_block_key != block_key:
                        scan_summary = _frozen_soil_spirit_scan_summary(affected_alive_ids)
                        PySystem.Console.Log(
                            MODULE_NAME,
                            "[FrozenSoil] Effect 471 is active, but the spirit was not resolved yet. " + scan_summary,
                            PySystem.Console.MessageType.Warning,
                        )
                        self._last_block_key = block_key

                if self._frozen_soil_spirit_gone and self._corpse_recovery_active:
                    self._tick_corpse_recovery(dead_ids)

                self._frozen_soil_was_blocking = True
                self._blocked = True
                return BehaviorTree.NodeState.RUNNING

            if self._frozen_soil_was_blocking:
                PySystem.Console.Log(
                    MODULE_NAME,
                    "[FrozenSoil] Blocking effect is gone from living party members; regrouping for HeroAI resurrection.",
                    PySystem.Console.MessageType.Success,
                )
                if self._tracked_frozen_soil_id > 0 or self._frozen_soil_spirit_gone:
                    self._corpse_recovery_active = True
                self._frozen_soil_was_blocking = False
                self._frozen_soil_spirit_gone = False
                self._tracked_frozen_soil_id = 0
                self._last_call_target_id = 0
                self._last_call_target_send_ms = 0
                self._call_target_failure_key = ""
                self._frozen_soil_attack_refs.clear()
                self._last_local_frozen_soil_attack_ms = 0
                self._last_attack_dispatch_log_ms = 0

            if self._corpse_recovery_active:
                self._tick_corpse_recovery(dead_ids)

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

        if self._corpse_recovery_flagged:
            if not self._request_corpse_recovery_unflag():
                self._blocked = True
                return BehaviorTree.NodeState.RUNNING

        if self._blocked:
            PySystem.Console.Log(
                MODULE_NAME,
                "[PartyAlive] Every party member is alive. Recovery flags cleared; resuming current run step.",
                PySystem.Console.MessageType.Success,
            )
            self._blocked = False
            self._last_block_key = ""
            self._last_call_target_id = 0
            self._last_call_target_send_ms = 0
            self._call_target_failure_key = ""
            self._frozen_soil_was_blocking = False
            self._frozen_soil_attack_refs.clear()
            self._last_local_frozen_soil_attack_ms = 0
            self._last_attack_dispatch_log_ms = 0
            self._reset_corpse_recovery_nodes()
            self._corpse_recovery_flagged = False
            self._corpse_recovery_unflag_node = None

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
                        move_tolerance=800
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


def _remaining_jaga_route_from_current_position() -> list[Vec2f]:
    """Resume Jaga from the nearest route point instead of replaying passed points."""
    try:
        if int(Map.GetMapID() or 0) != JAGA_MORAINE:
            return list(JAGA_ROUTE)
        current_x, current_y = Player.GetXY()
    except Exception:
        return list(JAGA_ROUTE)

    nearest_index = 0
    nearest_distance_sq = float("inf")
    for index, point in enumerate(JAGA_ROUTE):
        dx = float(point.x) - float(current_x)
        dy = float(point.y) - float(current_y)
        distance_sq = dx * dx + dy * dy
        if distance_sq < nearest_distance_sq:
            nearest_distance_sq = distance_sq
            nearest_index = index

    # Re-run the nearest point itself.  This preserves the MoveAndKill post-combat
    # return/clear guarantee, but never sends the party back through the whole Jaga route.
    return list(JAGA_ROUTE[nearest_index:])


def _build_jaga_vanquish_from_current_position() -> BehaviorTree:
    route = _remaining_jaga_route_from_current_position()
    try:
        current_x, current_y = Player.GetXY()
        start_index = len(JAGA_ROUTE) - len(route) + 1
        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"[JagaResume] Building Jaga route from point {start_index:02d}/"
                f"{len(JAGA_ROUTE)} at current=({current_x:.0f}, {current_y:.0f})."
            ),
            PySystem.Console.MessageType.Info,
        )
    except Exception:
        pass
    return BT.VanquishNode(
        route,
        name="Jaga Moraine Route",
        clear_area_radius=Range.Spirit.value,
        pause_on_combat=True,
        log=False,
    )


def _jaga_route_and_quest_tail() -> BehaviorTree:
    return BT.Sequence(
        name="Jaga Route And Cold Vengeance",
        children=[
            BT.Subtree(
                name="Resume Jaga Route From Current Position",
                subtree_fn=lambda _node: _build_jaga_vanquish_from_current_position(),
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
        ],
    )
L1_ROUTE = [Vec2f(-15326.62, 17240.07), Vec2f(-14654.82, 16460.37), Vec2f(-13949.08, 15526.11), Vec2f(-13290.34, 15118.21), Vec2f(-12589.15, 16123.14), Vec2f(-12942.74, 14284.69), Vec2f(-12534.54, 13983.46), Vec2f(-12130.02, 13416.32), Vec2f(-10692.78, 11887.72), Vec2f(-11035.61, 12018.64), Vec2f(-10552.88, 12086.03), Vec2f(-10692.78, 11887.72), Vec2f(-11035.61, 12018.64)]
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

    # If this planner step is restarted while already in Jaga Moraine, never run
    # the Sifhalla coordinates again and never replay the whole Jaga path.  Resume
    # from the nearest known route point instead.
    resume_in_jaga = BT.Sequence(
        name="Resume Frostmaw Travel In Jaga",
        children=[
            BT.IsCurrentMap(map_id=JAGA_MORAINE, log=False),
            _runtime_consumable_upkeep_node(False),
            _jaga_route_and_quest_tail(),
        ],
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
            BT.MoveAndExitMap(
                Vec2f(16900, 22830),
                target_map_id=JAGA_MORAINE,
                log=True,
                timeout_ms=10_000,
            ),
            BT.MoveAndDialog(
                Vec2f(-9153.42, -22776.35),
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
            ),
            _jaga_route_and_quest_tail(),
        ],
    )

    return BT.Selector(
        name="Travel To Frostmaw",
        children=[already_inside, resume_in_jaga, normal_entry],
    )


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
                BT.ClearEnemiesInArea(Vec2f(-11035.61, 12018.64)),
                BT.MoveAndExitMap(Vec2f(-10900, 10850), target_map_id=FROSTMAW_L2, log=True,timeout_ms=10_000)
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
                BT.ClearEnemiesInArea(Vec2f(13839.18, -18765.72)),
                BT.MoveAndExitMap(Vec2f(13950, -19400), target_map_id=FROSTMAW_L3, log=True,timeout_ms=10_000)
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
                BT.ClearEnemiesInArea(Vec2f(15827.45, 16530.45)),
                BT.MoveAndExitMap(Vec2f(18400, 15800), target_map_id=FROSTMAW_L4, log=True,timeout_ms=10000),
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
                BT.ClearEnemiesInArea(Vec2f(-15666.06, -12007.23)),
                BT.MoveAndExitMap(Vec2f(-16500, -12600), target_map_id=FROSTMAW_L5, log=True,timeout_ms=10_000),
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
                timeout_ms=10_000
            ),

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



def tooltip() -> None:
    PyImGui.set_next_window_size((600, 0))
    PyImGui.begin_tooltip()

    title_color = Color(255, 200, 100, 255)
    ImGui.image(MODULE_ICON, (32, 32))
    PyImGui.same_line(0, 10)
    ImGui.push_font("Regular", 20)
    ImGui.text_aligned(
        MODULE_NAME,
        alignment=Alignment.MidLeft,
        color=title_color.color_tuple,
        height=32,
    )
    ImGui.pop_font()

    PyImGui.spacing()
    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    PyImGui.text_wrapped(
        "A complete multibox BottingTree automation for Frostmaw's Burrows. "
        "The run handles the Jaga Moraine approach and all five dungeon levels, "
        "including quest progression, boss encounters, the final Burrows chest "
        "and preparation for the next run."
    )
    PyImGui.spacing()

    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text(
        "Automates the complete Level 1 through Level 5 Frostmaw route."
    )
    PyImGui.bullet_text(
        "Supports multibox party control, synchronized dialogs and floor progression."
    )
    PyImGui.bullet_text(
        "Handles Frozen Soil recovery: living clients kill the spirit, regroup on "
        "fallen party members and wait for HeroAI resurrection before resuming the paused step."
    )
    PyImGui.bullet_text(
        "Configurable Normal/Hard Mode, consets, direct personal consumables, morale items and summoning stones."
    )
    PyImGui.bullet_text(
        "MerchantRules is enabled only for inventory verification/maintenance and disabled again before gameplay."
    )
    PyImGui.bullet_text(
        "Tracks run/floor times plus Silverwing, Bonecage Scythe and Icicle Staff drops across accounts."
    )
    PyImGui.spacing()

    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Original Frostmaw AutoIt script and route: BubbleTea.")
    PyImGui.bullet_text("BottingTree / multibox conversion and adaptations: Sky.")
    PyImGui.bullet_text("Built on Py4GW and the BottingTree framework by Apo and contributors.")

    PyImGui.end_tooltip()

def main() -> None:
    global initialized
    if not initialized:
        _load_settings()
        ensure_botting_tree()
        initialized = True
    tree = ensure_botting_tree()
    _sync_runtime_upkeeps()
    tree.tick()
    _tick_direct_pcon_upkeep()
    tree.UI.draw_window(icon_path=TEXTURE,
        main_child_dimensions=(430, 390),
        extra_tabs=[("Statistics", _draw_statistics), ("Config", _draw_run_config)],
    )


if __name__ == "__main__":
    main()
