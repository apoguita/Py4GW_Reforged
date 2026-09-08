
from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import time

import PySystem
import PyImGui

from Py4GWCoreLib import Agent, AgentArray, GLOBAL_CACHE, Inventory, Map, Player, SharedCommandType
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.Listeners import Listeners
from Py4GWCoreLib.enums import CONSUMABLE_MODELID_TO_EFFECT_NAME
from Py4GWCoreLib import Routines
from Py4GWCoreLib.Item import has_active_party_summon
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
    get_inventory_state,
    reset_inventory_count,
    reset_inventory_state,
)

TEXTURE = os.path.join(PySystem.Console.get_projects_path(), 'Assets', 'Textures', 'Module_Icons', 'vloxen.png')
MODULE_NAME = 'Vloxen Excavations BT'
INI_PATH = 'Widgets/Automation/Bots/Missions/Dungeons/Vloxen Excavations BT'
INI_FILENAME = 'Vloxen_Excavations_BT.ini'

START_OUTPOST = 639
DUNGEON_MAPS = (604, 605, 606)
QUEST_ID = 0x33C
DUNGEON_KEY_MODEL_ID = 25410
BOSS_KEY_MODEL_ID = 25416
GLACIAL_BLADE_MODEL_ID = 2474
MASTER_GEAR_MODEL_ID = 5717

SUMMON_MODEL_IDS = (37810, 30209, 31155)
PCON_UPKEEPS = tuple(
    int(model_id)
    for model_id in ALL_CONSUMABLE_UPKEEPS
    if int(model_id) not in CONSET_UPKEEPS
)
CONSET_RESTOCK_ITEMS = tuple((int(model_id), 10) for model_id in CONSET_UPKEEPS)
PCON_RESTOCK_ITEMS = tuple((int(model_id), 10) for model_id in PCON_UPKEEPS)
SUMMON_RESTOCK_ITEMS = tuple((int(model_id), 10) for model_id in SUMMON_MODEL_IDS)

ID_KIT_MODEL_IDS = (int(ModelID.Superior_Identification_Kit.value),)
SALVAGE_KIT_MODEL_IDS = (int(ModelID.Superior_Salvage_Kit.value),)
MERCHANT_RULES_WIDGET_NAME = "MerchantRules"
INVENTORY_PLUS_WIDGET_NAME = "InventoryPlus"

INVENTORY_MAINTENANCE_RETRY_COUNT = 2
INVENTORY_SNAPSHOT_SETTLE_MS = 2_000
INVENTORY_TRAVEL_TIMEOUT_MS = 60_000
INVENTORY_MERCHANT_TIMEOUT_MS = 240_000
_INVENTORY_QUERY_TIMEOUT_MS = 10_000
_INVENTORY_QUERY_POLL_MS = 200

_SETTINGS_SECTION = "Settings"
_STATS_SECTION = "Statistics"
_GB_DROPS_SECTION = "Glacial Blades Drops"
_GB_SNAPSHOT_SECTION = "Glacial Blades Snapshot"
_GB_RUN_SECTION = "Glacial Blades Run"
_CHAR_NAMES_SECTION = "Character Names"
_settings = Settings(f"{INI_PATH}/{INI_FILENAME}", "global")
_settings_loaded = False

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

# Direct multibox PCon runtime state.
_PCON_DIRECT_DISPATCH_INTERVAL_MS = 650
PCON_USAGE_LOG = False
_pcon_direct_index = 0
_pcon_direct_last_dispatch_ms = 0
_pcon_direct_runtime_logged = False
_pcon_direct_last_recipient_signature: tuple[str, ...] = ()
_pcon_direct_morale_remote_index = 0
_PCON_PARTY_MORALE_TARGET_BY_MODEL = {
    int(ModelID.Four_Leaf_Clover.value): 100,
    int(ModelID.Honeycomb.value): 110,
}

# Persistent statistics.
_statistics_loaded = False
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

_gb_drops: dict[str, int] = {}
_char_names: dict[str, str] = {}

# Session-only statistics.
_session_runs = 0
_session_gb: dict[str, int] = {}
_scramble_accounts = False

# Active and most recently completed timings.
_t_run_start = 0.0
_t_l2_start = 0.0
_t_l3_start = 0.0
_current_run_time = 0.0
_current_l1_time = 0.0
_current_l2_time = 0.0
_current_l3_time = 0.0

initialized = False
botting_tree: BottingTree | None = None

# Master Gear bundle state.
_drop_master_gear_for_combat: bool | None = None
_master_gear_dropped_for_combat = False


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
    _inventory_maintenance_enabled = _settings.get_bool(
        _SETTINGS_SECTION,
        "InventoryMaintenanceEnabled",
        True,
    )
    _inventory_min_free_slots = max(
        0,
        _settings.get_int(_SETTINGS_SECTION, "InventoryMinFreeSlots", 5),
    )
    _inventory_min_id_kits = max(
        0,
        _settings.get_int(_SETTINGS_SECTION, "InventoryMinIdKits", 1),
    )
    _inventory_min_salvage_kits = max(
        0,
        _settings.get_int(_SETTINGS_SECTION, "InventoryMinSalvageKits", 2),
    )

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
    _settings.set(
        _SETTINGS_SECTION,
        "InventoryMaintenanceEnabled",
        _inventory_maintenance_enabled,
    )
    _settings.set(
        _SETTINGS_SECTION,
        "InventoryMinFreeSlots",
        _inventory_min_free_slots,
    )
    _settings.set(
        _SETTINGS_SECTION,
        "InventoryMinIdKits",
        _inventory_min_id_kits,
    )
    _settings.set(
        _SETTINGS_SECTION,
        "InventoryMinSalvageKits",
        _inventory_min_salvage_kits,
    )


def _account_key(email: str) -> str:
    return str(email).replace("@", "_at_").replace(".", "_")


def _display_email(key: str) -> str:
    return str(key).replace("_at_", "@").replace("_", ".")


def _account_label(key: str) -> str:
    if not _scramble_accounts:
        return _char_names.get(key) or _display_email(key)

    keys = sorted(set(_gb_drops) | set(_session_gb) | set(_char_names))
    index = keys.index(key) + 1 if key in keys else 0
    return f"Player {index}"


def _refresh_character_names() -> bool:
    changed = False

    local_email = str(Player.GetAccountEmail() or "").strip()
    local_name = str(Player.GetName() or "").strip()
    if local_email and local_name:
        key = _account_key(local_email)
        if _char_names.get(key) != local_name:
            _char_names[key] = local_name
            changed = True

    for account in _inventory_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        agent_data = getattr(account, "AgentData", None)
        character_name = str(
            getattr(agent_data, "CharacterName", "") or ""
        ).strip()
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

    if _statistics_loaded:
        return

    section = _STATS_SECTION
    _total_runs = _settings.get_int(section, "total_runs", 0)
    _total_run_time = _settings.get_float(section, "total_run_time", 0.0)

    fastest = _settings.get_float(section, "fastest_run", 0.0)
    _fastest_run = float("inf") if fastest <= 0.0 else fastest
    _slowest_run = _settings.get_float(section, "slowest_run", 0.0)

    _l1_total_time = _settings.get_float(section, "l1_total_time", 0.0)
    fastest = _settings.get_float(section, "l1_fastest", 0.0)
    _l1_fastest = float("inf") if fastest <= 0.0 else fastest
    _l1_slowest = _settings.get_float(section, "l1_slowest", 0.0)

    _l2_total_time = _settings.get_float(section, "l2_total_time", 0.0)
    fastest = _settings.get_float(section, "l2_fastest", 0.0)
    _l2_fastest = float("inf") if fastest <= 0.0 else fastest
    _l2_slowest = _settings.get_float(section, "l2_slowest", 0.0)

    _l3_total_time = _settings.get_float(section, "l3_total_time", 0.0)
    fastest = _settings.get_float(section, "l3_fastest", 0.0)
    _l3_fastest = float("inf") if fastest <= 0.0 else fastest
    _l3_slowest = _settings.get_float(section, "l3_slowest", 0.0)

    for key in _settings.items(_GB_DROPS_SECTION).keys():
        _gb_drops[key] = _settings.get_int(_GB_DROPS_SECTION, key, 0)

    for seed_section in (_GB_SNAPSHOT_SECTION, _GB_RUN_SECTION):
        for key in _settings.items(seed_section).keys():
            _gb_drops.setdefault(key, 0)

    for key in _settings.items(_CHAR_NAMES_SECTION).keys():
        name = str(_settings.get_str(_CHAR_NAMES_SECTION, key, "") or "").strip()
        if name:
            _char_names[key] = name

    _statistics_loaded = True


def _save_statistics() -> None:
    section = _STATS_SECTION
    _settings.set(section, "total_runs", _total_runs)
    _settings.set(section, "total_run_time", _total_run_time)
    _settings.set(
        section,
        "fastest_run",
        0.0 if _fastest_run == float("inf") else _fastest_run,
    )
    _settings.set(section, "slowest_run", _slowest_run)

    for floor, total, fastest, slowest in (
        ("l1", _l1_total_time, _l1_fastest, _l1_slowest),
        ("l2", _l2_total_time, _l2_fastest, _l2_slowest),
        ("l3", _l3_total_time, _l3_fastest, _l3_slowest),
    ):
        _settings.set(section, f"{floor}_total_time", total)
        _settings.set(
            section,
            f"{floor}_fastest",
            0.0 if fastest == float("inf") else fastest,
        )
        _settings.set(section, f"{floor}_slowest", slowest)

    for key, total in _gb_drops.items():
        _settings.set(_GB_DROPS_SECTION, key, total)

    for key, name in _char_names.items():
        _settings.set(_CHAR_NAMES_SECTION, key, name)


def _statistics_action_node(
    name: str,
    action: Callable[[], None],
) -> BehaviorTree:
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

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_run,
            aftercast_ms=0,
        )
    )


def _mark_run_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_run_start, _t_l2_start, _t_l3_start
        global _current_run_time
        global _current_l1_time, _current_l2_time, _current_l3_time

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
        _current_l1_time = (
            now - _t_run_start
            if _t_run_start > 0.0
            else 0.0
        )

    return _statistics_action_node("Mark Level 2 Start", _mark)


def _mark_l3_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_l3_start, _current_l2_time

        now = time.monotonic()
        _t_l3_start = now
        _current_l2_time = (
            now - _t_l2_start
            if _t_l2_start > 0.0
            else 0.0
        )

    return _statistics_action_node("Mark Level 3 Start", _mark)


def _record_run_end_node() -> BehaviorTree:
    def _record() -> None:
        global _total_runs, _session_runs
        global _total_run_time, _fastest_run, _slowest_run
        global _l1_total_time, _l1_fastest, _l1_slowest
        global _l2_total_time, _l2_fastest, _l2_slowest
        global _l3_total_time, _l3_fastest, _l3_slowest
        global _current_run_time, _current_l1_time
        global _current_l2_time, _current_l3_time
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
                (
                    "[Statistics] Run complete - "
                    f"Total {run_time:.0f}s | "
                    f"L1 {l1_time:.0f}s | "
                    f"L2 {l2_time:.0f}s | "
                    f"L3 {l3_time:.0f}s"
                ),
                PySystem.Console.MessageType.Success,
            )

        _total_runs += 1
        _session_runs += 1
        _t_run_start = 0.0
        _t_l2_start = 0.0
        _t_l3_start = 0.0
        _save_statistics()

    return _statistics_action_node("Record Successful Run", _record)


def _accumulate_gb_drop(account_key: str, count: int) -> None:
    _gb_drops.setdefault(account_key, 0)
    if count <= 0:
        return
    _gb_drops[account_key] += int(count)
    _session_gb[account_key] = _session_gb.get(account_key, 0) + int(count)


def _local_gb_count() -> int:
    return int(GLOBAL_CACHE.Inventory.GetModelCount(GLACIAL_BLADE_MODEL_ID))


def _glacial_blade_statistics_node(*, after_chest: bool) -> BehaviorTree:
    node_name = (
        "Record Glacial Blades After Final Chest"
        if after_chest
        else "Snapshot Glacial Blades At Dungeon Entry"
    )

    state: dict[str, object] = {
        "started": False,
        "local_email": "",
        "account_keys": [],
        "requests": [],
        "request_index": 0,
        "waiting": False,
        "request_started_at": 0.0,
    }

    def _reset() -> None:
        state["started"] = False
        state["local_email"] = ""
        state["account_keys"] = []
        state["requests"] = []
        state["request_index"] = 0
        state["waiting"] = False
        state["request_started_at"] = 0.0

    def _start() -> None:
        _load_statistics()
        _refresh_character_names()

        local_email = str(Player.GetAccountEmail() or "").strip()
        local_key = _account_key(local_email or "local")
        section = _GB_RUN_SECTION if after_chest else _GB_SNAPSHOT_SECTION

        _settings.set(section, local_key, _local_gb_count())

        account_keys = [local_key]
        requests: list[dict[str, object]] = []

        for account in _inventory_accounts():
            email = str(getattr(account, "AccountEmail", "") or "").strip()
            if not email or email == local_email:
                continue

            key = _account_key(email)
            if key not in account_keys:
                account_keys.append(key)

            requests.append(
                {
                    "email": email,
                    "key": key,
                }
            )

        for key in account_keys:
            _gb_drops.setdefault(key, 0)

        state["started"] = True
        state["local_email"] = local_email
        state["account_keys"] = account_keys
        state["requests"] = requests

    def _finish() -> None:
        if not after_chest:
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "[Statistics] Glacial Blades entry snapshot completed for "
                    f"{len(state['account_keys'])} account(s)."
                ),
                PySystem.Console.MessageType.Info,
            )
            _save_statistics()
            return

        total_gb = 0
        for key in state["account_keys"]:
            account_key = str(key)
            before = _settings.get_int(
                _GB_SNAPSHOT_SECTION,
                account_key,
                -1,
            )
            after = _settings.get_int(
                _GB_RUN_SECTION,
                account_key,
                -1,
            )
            delta = (
                max(0, after - before)
                if before >= 0 and after >= 0
                else 0
            )
            _accumulate_gb_drop(account_key, delta)
            total_gb += delta

        _save_statistics()
        PySystem.Console.Log(
            MODULE_NAME,
            f"[Statistics] Final chest recorded - Glacial Blades {total_gb}",
            PySystem.Console.MessageType.Success,
        )

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if bool(node.blackboard.get("USER_INTERRUPT_ACTIVE", False)):
                _reset()
                return BehaviorTree.NodeState.FAILURE

            if not bool(state["started"]):
                _start()

            requests = state["requests"]
            while int(state["request_index"]) < len(requests):
                request_index = int(state["request_index"])
                request = requests[request_index]
                email = str(request["email"])

                if not bool(state["waiting"]):
                    reset_inventory_count(
                        email,
                        GLACIAL_BLADE_MODEL_ID,
                        GLACIAL_BLADE_MODEL_ID,
                    )
                    section = _GB_RUN_SECTION if after_chest else _GB_SNAPSHOT_SECTION
                    _settings.set(section, str(request["key"]), -1)
                    GLOBAL_CACHE.ShMem.SendMessage(
                        str(state["local_email"]),
                        email,
                        SharedCommandType.InventoryQuery,
                        (
                            float(GLACIAL_BLADE_MODEL_ID),
                            float(GLACIAL_BLADE_MODEL_ID),
                            0.0,
                            0.0,
                        ),
                        ("report_inventory_count",),
                    )
                    state["waiting"] = True
                    state["request_started_at"] = time.monotonic()
                    return BehaviorTree.NodeState.RUNNING

                count = int(
                    get_inventory_count(
                        email,
                        GLACIAL_BLADE_MODEL_ID,
                        GLACIAL_BLADE_MODEL_ID,
                    )
                )
                if count >= 0:
                    section = _GB_RUN_SECTION if after_chest else _GB_SNAPSHOT_SECTION
                    _settings.set(section, str(request["key"]), count)
                    state["request_index"] = request_index + 1
                    state["waiting"] = False
                    continue

                elapsed_ms = (
                    time.monotonic() - float(state["request_started_at"])
                ) * 1000.0
                if elapsed_ms >= _INVENTORY_QUERY_TIMEOUT_MS:
                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            "[Statistics] Inventory query timed out for "
                            f"Glacial Blades on {_account_label(str(request['key']))}."
                        ),
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

def _consumables_allowed() -> bool:
    return (
        _runtime_consumables_enabled
        and Map.IsMapReady()
        and not Map.IsMapLoading()
        and Map.GetMapID() in DUNGEON_MAPS
    )


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    """Return Core-managed conset upkeeps; PCons use the direct dispatcher."""
    if not _runtime_consumables_enabled:
        return ()
    enabled: list[int] = []
    if _activate_conset:
        enabled.extend(int(model_id) for model_id in CONSET_UPKEEPS)
    return tuple(dict.fromkeys(enabled))

def _pcon_effect_name(model_id: int) -> str:
    model_id = int(model_id)
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


def _reset_direct_pcon_runtime() -> None:
    global _pcon_direct_index, _pcon_direct_last_dispatch_ms
    global _pcon_direct_runtime_logged, _pcon_direct_last_recipient_signature
    global _pcon_direct_morale_remote_index
    _pcon_direct_index = 0
    _pcon_direct_last_dispatch_ms = 0
    _pcon_direct_runtime_logged = False
    _pcon_direct_last_recipient_signature = ()
    _pcon_direct_morale_remote_index = 0


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
    global _pcon_direct_morale_remote_index
    target_morale = _PCON_PARTY_MORALE_TARGET_BY_MODEL.get(int(model_id))
    if target_morale is None:
        return
    party_min_morale = _shared_party_min_morale_for_direct_pcons()
    if party_min_morale is None or party_min_morale >= int(target_morale):
        return

    local_agent_id = int(Player.GetAgentID() or 0)
    local_is_dead = bool(local_agent_id and Agent.IsDead(local_agent_id))
    if not local_is_dead and GLOBAL_CACHE.Inventory.GetModelCount(int(model_id)) > 0:
        item_id = int(GLOBAL_CACHE.Item.GetItemIdFromModelID(int(model_id)) or 0)
        if item_id > 0:
            GLOBAL_CACHE.Inventory.UseItem(item_id)
            if PCON_USAGE_LOG:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[PCons] Party morale use: model={int(model_id)}, morale={party_min_morale} -> target={int(target_morale)}.",
                    PySystem.Console.MessageType.Info,
                )
            return

    remote_recipients = [email for email in recipients if email and email != sender_email]
    if not remote_recipients:
        return
    receiver_email = remote_recipients[_pcon_direct_morale_remote_index % len(remote_recipients)]
    _pcon_direct_morale_remote_index = (_pcon_direct_morale_remote_index + 1) % max(1, len(remote_recipients))
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
    global _pcon_direct_index, _pcon_direct_last_dispatch_ms
    global _pcon_direct_runtime_logged, _pcon_direct_last_recipient_signature

    if not _bot_is_started() or not _activate_pcons or not _consumables_allowed():
        if _pcon_direct_runtime_logged or _pcon_direct_last_dispatch_ms:
            _reset_direct_pcon_runtime()
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
    if model_id in _PCON_PARTY_MORALE_TARGET_BY_MODEL:
        _dispatch_party_morale_pcon(model_id, recipients, sender_email)
        return

    effect_name = _pcon_effect_name(model_id)
    effect_id = int(GLOBAL_CACHE.Skill.GetID(effect_name) or 0) if effect_name else 0
    if effect_id <= 0:
        return
    local_agent_id = int(Player.GetAgentID() or 0)
    local_is_dead = bool(local_agent_id and Agent.IsDead(local_agent_id))
    local_has_effect = bool(local_agent_id and GLOBAL_CACHE.Effects.HasEffect(local_agent_id, effect_id))
    if not local_is_dead and not local_has_effect and GLOBAL_CACHE.Inventory.GetModelCount(model_id) > 0:
        item_id = int(GLOBAL_CACHE.Item.GetItemIdFromModelID(model_id) or 0)
        if item_id > 0:
            GLOBAL_CACHE.Inventory.UseItem(item_id)
            if PCON_USAGE_LOG:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[PCons] Local use: model={model_id}, effect={effect_id} ({effect_name}).",
                    PySystem.Console.MessageType.Info,
                )

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
        _reset_direct_pcon_runtime()

    if botting_tree is None:
        return
    enabled_consumables = _enabled_consumable_upkeeps()
    botting_tree.Config.ConfigureUpkeep(
        looting_enabled=_runtime_looting_enabled,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=enabled_consumables,
        enable_party_wipe_recovery=True,
        enable_nearest_shrine_recovery=True,
        heroai_state_logging=False,
    )
    botting_tree.AddServiceTree(
        "SummoningStoneRecoveryService",
        SummoningStoneRecoveryService,
    )
    _configured_consumable_upkeeps = enabled_consumables


def _sync_runtime_upkeeps() -> None:
    if _enabled_consumable_upkeeps() != _configured_consumable_upkeeps:
        _configure_runtime_upkeeps()


def _runtime_consumable_upkeep_node(enabled: bool) -> BehaviorTree:
    """Enable or suspend conset and direct PCon upkeep at runtime."""
    def _apply(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if botting_tree is None:
            return BehaviorTree.NodeState.FAILURE
        if _runtime_consumables_enabled != bool(enabled):
            _configure_runtime_upkeeps(consumables_enabled=enabled)
            PySystem.Console.Log(
                MODULE_NAME,
                "Consumable upkeep resumed for the dungeon run." if enabled else "Consumable upkeep suspended during the end-of-dungeon sequence.",
                PySystem.Console.MessageType.Info,
            )
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




def InventoryCheckAndMaintenance() -> BehaviorTree:
    # MerchantRules maintenance lifecycle:
    # OFF outside inventory maintenance, ON only while it is actually required.

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
                BT.Failer(
                    name=f"Inventory Maintenance Attempt {attempt} Failed"
                ),
            ],
        )

        attempts.append(
            BT.Selector(
                name=f"Inventory Maintenance Attempt {attempt}",
                children=[normal_attempt, cleanup_failure],
            )
        )

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
            # MerchantRules stays OFF during party teardown / travel.
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                False,
                "inventory_check_merchant_off_before_maintenance",
            ),
            BT.LeaveParty(),
            BT.Selector(
                name="MerchantRules Attempts",
                children=attempts,
            ),
        ],
    )

    enabled_normal = BT.Sequence(
        name="Inventory Check And Maintenance - Run",
        children=[
            # Enable inventory reporting for the initial verification,
            # then every branch explicitly switches it OFF again.
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                True,
                "inventory_check_merchant_on",
            ),
            _query_all_inventory_states_node(
                "Query Inventory On All Accounts"
            ),
            BT.Selector(
                name="Inventory Threshold Decision",
                children=[
                    healthy_without_maintenance,
                    maintenance_required,
                ],
            ),
        ],
    )

    # Last-resort cleanup: MerchantRules must never leak ON into the dungeon.
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
            BT.Failer(
                name="Inventory Check And Maintenance Failed"
            ),
        ],
    )

    enabled = BT.Selector(
        name="Inventory Check And Maintenance",
        children=[
            enabled_normal,
            enabled_cleanup_failure,
        ],
    )

    return BT.Selector(
        name="Optional Inventory Maintenance",
        children=[
            disabled,
            enabled,
        ],
    )


def UseAvailableSummoningStone(level_key: str) -> BehaviorTree:
    """Broadcast a best-effort summoning-stone request to every active account."""
    def _dispatch(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if not _use_summoning_stone or not _consumables_allowed():
            return BehaviorTree.NodeState.SUCCESS
        sender_email = str(Player.GetAccountEmail() or "").strip()
        recipients = _inventory_recipient_emails()
        if not sender_email or not recipients:
            return BehaviorTree.NodeState.SUCCESS
        for receiver_email in recipients:
            try:
                GLOBAL_CACHE.ShMem.SendMessage(
                    sender_email,
                    receiver_email,
                    SharedCommandType.UseSummoningStone,
                    (0.0, 0.0, 0.0, 0.0),
                    ("", "", "", ""),
                )
            except Exception:
                continue
        return BehaviorTree.NodeState.SUCCESS
    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Use Summoning Stone {level_key} (Multibox Non Blocking)",
            action_fn=_dispatch,
            aftercast_ms=0,
        )
    )

def SummoningStoneRecoveryService() -> BehaviorTree:
    """Replace a summoning-stone ally that dies during the current floor.

    Level-start summon actions remain authoritative. The service arms only after
    a living summon has been observed on the current floor and respects the live
    runtime toggle on every tick.
    """
    ATTEMPT_INTERVAL_MS = 3_000.0
    RETRY_CYCLE_DELAY_MS = 15_000.0
    state: dict[str, object] = {
        "map_id": 0,
        "saw_active_summon": False,
        "recovering": False,
        "targets": [],
        "target_index": 0,
        "next_attempt_ms": 0.0,
    }

    def _reset_for_map(map_id: int) -> None:
        state["map_id"] = int(map_id)
        state["saw_active_summon"] = False
        state["recovering"] = False
        state["targets"] = []
        state["target_index"] = 0
        state["next_attempt_ms"] = 0.0

    def _refresh_targets() -> list[tuple[str, str]]:
        targets: list[tuple[str, str]] = []
        seen: set[str] = set()
        for email, label in _inventory_target_accounts():
            email = str(email or "").strip()
            if not email or email in seen:
                continue
            seen.add(email)
            targets.append((email, str(label or email)))
        state["targets"] = targets
        return targets

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if not _use_summoning_stone or not _consumables_allowed():
            return BehaviorTree.NodeState.RUNNING
        if not Map.IsMapReady() or Map.IsMapLoading() or not Map.IsExplorable():
            return BehaviorTree.NodeState.RUNNING

        map_id = int(Map.GetMapID() or 0)
        if map_id != int(state["map_id"] or 0):
            _reset_for_map(map_id)
            return BehaviorTree.NodeState.RUNNING

        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0 or not Agent.IsValid(player_id) or Agent.IsDead(player_id):
            return BehaviorTree.NodeState.RUNNING
        if Routines.Checks.Party.IsPartyWiped():
            return BehaviorTree.NodeState.RUNNING

        try:
            summon_alive = bool(has_active_party_summon(GLOBAL_CACHE.Party.GetOthers()))
        except Exception:
            summon_alive = False

        if summon_alive:
            if bool(state["recovering"]):
                PySystem.Console.Log(
                    MODULE_NAME,
                    "[Summoning] Replacement summon detected; recovery stopped.",
                    PySystem.Console.MessageType.Success,
                )
            state["saw_active_summon"] = True
            state["recovering"] = False
            state["targets"] = []
            state["target_index"] = 0
            state["next_attempt_ms"] = 0.0
            return BehaviorTree.NodeState.RUNNING

        if not bool(state["saw_active_summon"]):
            return BehaviorTree.NodeState.RUNNING

        now_ms = time.monotonic() * 1000.0
        if not bool(state["recovering"]):
            state["recovering"] = True
            state["target_index"] = 0
            state["next_attempt_ms"] = now_ms
            _refresh_targets()
            PySystem.Console.Log(
                MODULE_NAME,
                "[Summoning] Active party summon was lost; trying replacement stones account by account.",
                PySystem.Console.MessageType.Warning,
            )

        if now_ms < float(state["next_attempt_ms"] or 0.0):
            return BehaviorTree.NodeState.RUNNING

        targets: list[tuple[str, str]] = list(state["targets"] or [])
        if not targets:
            targets = _refresh_targets()
            if not targets:
                state["next_attempt_ms"] = now_ms + RETRY_CYCLE_DELAY_MS
                return BehaviorTree.NodeState.RUNNING

        target_index = int(state["target_index"] or 0)
        if target_index >= len(targets):
            state["target_index"] = 0
            state["targets"] = _refresh_targets()
            state["next_attempt_ms"] = now_ms + RETRY_CYCLE_DELAY_MS
            return BehaviorTree.NodeState.RUNNING

        sender_email = str(Player.GetAccountEmail() or "").strip()
        if not sender_email:
            state["next_attempt_ms"] = now_ms + ATTEMPT_INTERVAL_MS
            return BehaviorTree.NodeState.RUNNING

        receiver_email, label = targets[target_index]
        state["target_index"] = target_index + 1
        state["next_attempt_ms"] = now_ms + ATTEMPT_INTERVAL_MS
        try:
            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                receiver_email,
                SharedCommandType.UseSummoningStone,
                (0.0, 0.0, 0.0, 0.0),
            )
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Summoning] Asking {label} to try a replacement summoning stone.",
                PySystem.Console.MessageType.Info,
            )
        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Summoning] Replacement request failed for {label}: {exc}",
                PySystem.Console.MessageType.Warning,
            )
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Summoning Stone Recovery Service",
            action_fn=_tick,
            aftercast_ms=500,
        )
    )




# ---------------------------------------------------------------------------
# Level 2 Master Gear bundle handling
# Carry the Master Gear while travelling, drop it only when combat starts,
# then recover the bundle before the planner advances.
# ---------------------------------------------------------------------------

_MARTIAL_PRIMARY_PROFESSIONS = {"Warrior", "Ranger", "Assassin", "Dervish", "Paragon"}


def _is_holding_bundle() -> bool:
    try:
        return bool(Agent.IsHoldingItem(Player.GetAgentID()))
    except Exception:
        return False


def _resolve_master_gear_combat_policy() -> bool:
    """Return True when the leader must drop the Master Gear for combat."""
    global _drop_master_gear_for_combat

    if _drop_master_gear_for_combat is not None:
        return _drop_master_gear_for_combat

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
        _drop_master_gear_for_combat = True
        reason = f"martial weapon detected: {weapon_name}"
    elif is_caster:
        _drop_master_gear_for_combat = False
        reason = f"caster weapon detected: {weapon_name}"
    else:
        try:
            primary_profession, _ = Agent.GetProfessionNames(player_id)
        except Exception:
            primary_profession = ""

        if primary_profession in _MARTIAL_PRIMARY_PROFESSIONS:
            _drop_master_gear_for_combat = True
            reason = f"martial primary profession detected: {primary_profession}"
        elif primary_profession:
            _drop_master_gear_for_combat = False
            reason = f"caster primary profession detected: {primary_profession}"
        else:
            # Safe fallback: never risk entering combat with an unknown build
            # while the Master Gear is occupying the weapon slot.
            _drop_master_gear_for_combat = True
            reason = "weapon and profession are unknown; safe fallback"

    PySystem.Console.Log(
        MODULE_NAME,
        f"Master Gear combat policy: {('DROP' if _drop_master_gear_for_combat else 'KEEP')} ({reason}).",
        PySystem.Console.MessageType.Info,
    )
    return _drop_master_gear_for_combat


def ResetMasterGearCombatPolicy() -> BehaviorTree:
    def _reset(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _drop_master_gear_for_combat, _master_gear_dropped_for_combat
        _drop_master_gear_for_combat = None
        _master_gear_dropped_for_combat = False
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Reset Master Gear Combat Policy",
            action_fn=_reset,
            aftercast_ms=0,
        )
    )


def _set_master_gear_dropped_node(value: bool) -> BehaviorTree:
    def _set(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _master_gear_dropped_for_combat
        _master_gear_dropped_for_combat = bool(value)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Mark Master Gear Dropped" if value else "Clear Master Gear Dropped",
            action_fn=_set,
            aftercast_ms=0,
        )
    )


def DropMasterGearForCombat(log: bool=False) -> BehaviorTree:
    """Drop the Master Gear only for martial combat; casters keep carrying it."""

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not _resolve_master_gear_combat_policy():
            return BT.Succeeder("Keep Master Gear For Caster Combat")
        if not _is_holding_bundle():
            return BT.Succeeder("No Master Gear Bundle To Drop")
        return BT.Sequence(
            name="Drop Master Gear For Combat",
            children=[
                BT.DropBundle(log=log),
                _set_master_gear_dropped_node(True),
            ],
        )

    return BT.Subtree(name="Drop Master Gear For Combat If Required", subtree_fn=_build)


def _enemy_in_master_gear_combat_range(radius: float=Range.Earshot.value) -> bool:
    """Return True when a living enemy is within the Master Gear combat-drop radius."""
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


def MasterGearAwareVanquish(point: Vec2f, name: str) -> BehaviorTree:
    """Run one Vanquish point and drop a martial Master Gear only when combat enters Earshot."""

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

        # Keep carrying the Master Gear while travelling. For martial builds,
        # only release it once a live enemy actually enters the same Earshot
        # radius used by this Vanquish point.
        if (
            _resolve_master_gear_combat_policy()
            and _is_holding_bundle()
            and _enemy_in_master_gear_combat_range(Range.Earshot.value)
        ):
            if drop_tree is None:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[MasterGear] Enemy entered Earshot during '{name}' -> dropping bundle for combat.",
                    PySystem.Console.MessageType.Info,
                )
                drop_tree = DropMasterGearForCombat(log=True)

            drop_tree.blackboard = node.blackboard
            drop_result = BehaviorTree.Node._normalize_state(drop_tree.tick())
            if drop_result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING
            if drop_result == BehaviorTree.NodeState.FAILURE:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[MasterGear] Bundle drop FAILED during '{name}'.",
                    PySystem.Console.MessageType.Warning,
                )
                drop_tree = None
                return BehaviorTree.NodeState.FAILURE

            PySystem.Console.Log(
                MODULE_NAME,
                f"[MasterGear] Bundle dropped successfully during '{name}'.",
                PySystem.Console.MessageType.Info,
            )
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
            name=f"{name} - Master Gear Aware",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def _find_ground_master_gear() -> int | None:
    """Return a nearby pickup-compatible Master Gear, 0 if absent, None on scan failure."""
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

            owner_id = int(
                Agent.GetItemAgentOwnerID(agent_id) or 0
            )
            if owner_id not in (0, local_player_id):
                continue

            item_id = int(
                Agent.GetItemAgentItemID(agent_id) or 0
            )
            if item_id <= 0:
                continue

            model_id = int(
                GLOBAL_CACHE.Item.GetModelID(item_id) or 0
            )
            if model_id != MASTER_GEAR_MODEL_ID:
                continue

            x, y = Agent.GetXY(agent_id)
            dx = float(x) - float(px)
            dy = float(y) - float(py)

            if dx * dx + dy * dy <= search_radius_sq:
                return agent_id

        return 0

    except Exception as exc:
        PySystem.Console.Log(
            MODULE_NAME,
            f"[MasterGear] Ground scan failed: {exc}",
            PySystem.Console.MessageType.Warning,
        )
        return None


def PickupMasterGear(*, allow_missing_after_drop: bool = False) -> BehaviorTree:
    """Recover a dropped or newly spawned Master Gear before progression continues."""
    PICKUP_TIMEOUT_MS = 5_000
    RETRY_DELAY_MS = 1_000
    PICKUP_SEARCH_RADIUS = 7500.0

    def _create_pickup_tree() -> BehaviorTree:
        return BT.PickupGroundItemByModelID(
            model_ids=(MASTER_GEAR_MODEL_ID,),
            max_distance=PICKUP_SEARCH_RADIUS,
            timeout_ms=PICKUP_TIMEOUT_MS,
            allow_unassigned=True,
            interaction_interval_ms=1_000,
            aftercast_ms=100,
            log=True,
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
        global _master_gear_dropped_for_combat

        now = time.monotonic()

        if _is_holding_bundle():
            PySystem.Console.Log(
                MODULE_NAME,
                "[MasterGear] Bundle is held -> pickup SUCCESS.",
                PySystem.Console.MessageType.Success,
            )
            _master_gear_dropped_for_combat = False
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        ground_master_gear = _find_ground_master_gear()

        if ground_master_gear == 0 and (
            allow_missing_after_drop
            or not _master_gear_dropped_for_combat
        ):
            if (
                allow_missing_after_drop
                and _master_gear_dropped_for_combat
            ):
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        "[MasterGear] Bundle is no longer on the ground; "
                        "continuing final Gearbox approach."
                    ),
                    PySystem.Console.MessageType.Info,
                )
                _master_gear_dropped_for_combat = False

            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        if started_at <= 0.0:
            started_at = now

        if not search_started:
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "[MasterGear] Looking for Master Gear "
                    f"model_id={MASTER_GEAR_MODEL_ID}..."
                ),
                PySystem.Console.MessageType.Info,
            )
            search_started = True

        if (
            (now - started_at) * 1000.0
            >= PICKUP_TIMEOUT_MS
        ):
            _master_gear_dropped_for_combat = False
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "[MasterGear] Not recovered after 5s; "
                    "continuing to next route point."
                ),
                PySystem.Console.MessageType.Warning,
            )
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        if now < retry_at:
            return BehaviorTree.NodeState.RUNNING

        pickup_tree.blackboard = node.blackboard
        result = BehaviorTree.Node._normalize_state(
            pickup_tree.tick()
        )

        if result == BehaviorTree.NodeState.RUNNING:
            return BehaviorTree.NodeState.RUNNING

        if (
            result == BehaviorTree.NodeState.SUCCESS
            and _is_holding_bundle()
        ):
            PySystem.Console.Log(
                MODULE_NAME,
                "[MasterGear] Pickup CONFIRMED.",
                PySystem.Console.MessageType.Success,
            )
            _master_gear_dropped_for_combat = False
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        PySystem.Console.Log(
            MODULE_NAME,
            (
                "[MasterGear] Pickup subtree finished without held bundle; "
                "retrying."
            ),
            PySystem.Console.MessageType.Warning,
        )
        pickup_tree = _create_pickup_tree()
        pickup_tree.blackboard = node.blackboard
        retry_at = now + RETRY_DELAY_MS / 1000.0
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Pick Up Master Gear",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def _master_gear_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[Vec2f],
    *,
    skip_if_in_maps: Sequence[int]=(),
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Expose Master-Gear route points individually and handle the martial bundle cycle."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    final_gearbox_point_start = max(1, len(points) - 1)

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"
        allow_missing_after_drop = index >= final_gearbox_point_start

        def _build(
            point: Vec2f=point,
            name: str=name,
            allow_missing_after_drop: bool=allow_missing_after_drop,
        ) -> BehaviorTree:
            run = BT.Sequence(
                name=name,
                children=[
                    MasterGearAwareVanquish(point, f"{name} Combat"),
                    PickupMasterGear(allow_missing_after_drop=allow_missing_after_drop),
                    WaitForRecoverablePartyDeaths(name),
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


def _map_guarded_point(
    name: str,
    map_id: int,
    child: BehaviorTree,
    skip_if_in_maps: Sequence[int] = (),
) -> BehaviorTree:
    """Run one planner point on its map, or accept it on a later floor."""
    branches: list[BehaviorTree] = [
        BT.Sequence(
            name=f"{name} - Active Map",
            children=[
                BT.IsCurrentMap(map_id=map_id, log=False),
                child,
            ],
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



# ---------------------------------------------------------------------------
# Party resurrection progression guard
# ---------------------------------------------------------------------------

_RESURRECTION_SKILL_NAMES = (
    "Resurrection_Signet", "Resurrect", "Rebirth", "Restore_Life",
    "Resurrection_Chant", "Flesh_of_My_Flesh", "Death_Pact_Signet",
    "Renew_Life", "Signet_of_Return", "Sunspear_Rebirth_Signet",
    "Vengeance", "Lively_Was_Naomei", "We_Shall_Return",
)
_ONE_SHOT_RESURRECTION_SKILL_NAMES = (
    "Resurrection_Signet", "Signet_of_Return", "Sunspear_Rebirth_Signet",
)
_resurrection_skill_cache: tuple[set[int], set[int]] | None = None


def _resurrection_skill_sets() -> tuple[set[int], set[int]]:
    global _resurrection_skill_cache
    if _resurrection_skill_cache is None:
        def _resolve(names: Sequence[str]) -> set[int]:
            ids: set[int] = set()
            for name in names:
                try:
                    skill_id = int(GLOBAL_CACHE.Skill.GetID(name) or 0)
                except Exception:
                    skill_id = 0
                if skill_id > 0:
                    ids.add(skill_id)
            return ids

        _resurrection_skill_cache = (
            _resolve(_RESURRECTION_SKILL_NAMES),
            _resolve(_ONE_SHOT_RESURRECTION_SKILL_NAMES),
        )
    return _resurrection_skill_cache


def _party_player_agent_ids() -> set[int]:
    result: set[int] = set()
    try:
        for member in GLOBAL_CACHE.Party.GetPlayers() or []:
            login = int(getattr(member, "login_number", 0) or 0)
            agent_id = int(
                GLOBAL_CACHE.Party.Players.GetAgentIDByLoginNumber(login) or 0
            ) if login > 0 else 0
            if agent_id > 0:
                result.add(agent_id)
    except Exception:
        pass
    return result


def _dead_party_member_ids() -> list[int]:
    if not Map.IsExplorable():
        return []
    try:
        if not GLOBAL_CACHE.Party.IsPartyLoaded():
            return []
    except Exception:
        return []

    agent_ids = _party_player_agent_ids()
    for getter in (GLOBAL_CACHE.Party.GetHeroes, GLOBAL_CACHE.Party.GetHenchmen):
        try:
            for member in getter() or []:
                agent_id = int(getattr(member, "agent_id", 0) or 0)
                if agent_id > 0:
                    agent_ids.add(agent_id)
        except Exception:
            pass

    dead: list[int] = []
    for agent_id in sorted(agent_ids):
        try:
            if Agent.IsDead(agent_id):
                dead.append(agent_id)
        except Exception:
            pass
    return dead


def _skill_entries_can_resurrect(
    entries: Sequence[object],
    skill_id_fn: Callable[[object], int],
    recharge_fn: Callable[[object], float],
) -> bool:
    resurrection_ids, one_shot_ids = _resurrection_skill_sets()
    for entry in entries:
        try:
            skill_id = int(skill_id_fn(entry) or 0)
        except Exception:
            continue
        if skill_id not in resurrection_ids:
            continue
        if skill_id not in one_shot_ids:
            return True
        try:
            if float(recharge_fn(entry) or 0.0) <= 0.0:
                return True
        except Exception:
            return True
    return False


def _local_player_can_resurrect() -> bool:
    player_id = int(Player.GetAgentID() or 0)
    try:
        if player_id <= 0 or Agent.IsDead(player_id):
            return False
    except Exception:
        return False

    slots = tuple(range(1, 9))
    return _skill_entries_can_resurrect(
        slots,
        lambda slot: int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(int(slot)) or 0),
        lambda slot: float(
            getattr(GLOBAL_CACHE.SkillBar.GetSkillData(int(slot)), "recharge", 0) or 0
        ),
    )


def _living_hero_can_resurrect() -> bool:
    for hero_position in range(1, 8):
        try:
            agent_id = int(
                GLOBAL_CACHE.Party.Heroes.GetHeroAgentIDByPartyPosition(hero_position) or 0
            )
            if agent_id <= 0 or Agent.IsDead(agent_id):
                continue
            skillbar = GLOBAL_CACHE.SkillBar.GetHeroSkillbar(hero_position) or []
        except Exception:
            continue

        if _skill_entries_can_resurrect(
            tuple(skillbar),
            lambda skill: int(getattr(getattr(skill, "id", None), "id", 0) or 0),
            lambda skill: float(
                (skill.get_recharge() if callable(getattr(skill, "get_recharge", None))
                 else getattr(skill, "get_recharge", 0)) or 0
            ),
        ):
            return True
    return False


def _living_multibox_can_resurrect() -> bool:
    party_ids = _party_player_agent_ids()
    local_id = int(Player.GetAgentID() or 0)
    map_id = int(Map.GetMapID() or 0)

    for account in _inventory_accounts():
        agent_data = getattr(account, "AgentData", None)
        agent_id = int(getattr(agent_data, "AgentID", 0) or 0) if agent_data else 0
        if agent_id <= 0 or agent_id == local_id or agent_id not in party_ids:
            continue

        account_map = int(
            getattr(getattr(agent_data, "Map", None), "MapID", 0) or 0
        )
        if map_id > 0 and account_map > 0 and account_map != map_id:
            continue

        try:
            alive = bool(agent_data.Is_Alive)
        except Exception:
            alive = float(
                getattr(getattr(agent_data, "Health", None), "Current", 0) or 0
            ) > 0.0
        if not alive:
            continue

        skills = tuple(getattr(getattr(agent_data, "Skillbar", None), "Skills", ()) or ())
        if _skill_entries_can_resurrect(
            skills,
            lambda skill: int(getattr(skill, "Id", 0) or 0),
            lambda skill: float(getattr(skill, "Recharge", 0) or 0),
        ):
            return True
    return False


def _party_has_resurrection_provider() -> bool:
    return (
        _local_player_can_resurrect()
        or _living_multibox_can_resurrect()
        or _living_hero_can_resurrect()
    )


def WaitForRecoverablePartyDeaths(name: str) -> BehaviorTree:
    """Wait on a dead ally only while somebody living can still resurrect."""
    waiting = False
    last_dead: tuple[int, ...] = ()

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal waiting, last_dead
        dead = tuple(_dead_party_member_ids())

        if not dead:
            if waiting:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[PartyGuard] {name}: party alive; continuing.",
                    PySystem.Console.MessageType.Success,
                )
            waiting = False
            last_dead = ()
            return BehaviorTree.NodeState.SUCCESS

        if not _party_has_resurrection_provider():
            PySystem.Console.Log(
                MODULE_NAME,
                f"[PartyGuard] {name}: dead={list(dead)}, no resurrection available; continuing.",
                PySystem.Console.MessageType.Warning,
            )
            waiting = False
            last_dead = ()
            return BehaviorTree.NodeState.SUCCESS

        if not waiting or dead != last_dead:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[PartyGuard] {name}: waiting for resurrection; dead={list(dead)}.",
                PySystem.Console.MessageType.Warning,
            )
        waiting = True
        last_dead = dead
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"{name} - Recoverable Party Death Guard",
            action_fn=_tick,
            aftercast_ms=250,
        )
    )

def _guarded_step(
    name: str,
    map_id: int,
    child_builder: Callable[[], BehaviorTree],
    skip_if_in_maps: Sequence[int] = (),
) -> tuple[str, Callable[[], BehaviorTree]]:
    """Build one named planner step guarded by its dungeon floor."""
    def _build() -> BehaviorTree:
        return _map_guarded_point(
            name=name,
            map_id=map_id,
            child=child_builder(),
            skip_if_in_maps=skip_if_in_maps,
        )
    return name, _build


def _movement_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[Vec2f],
    *,
    pause_on_combat: bool = False,
    tolerance: float = 200.0,
    skip_if_in_maps: Sequence[int] = (),
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Expose every non-combat movement coordinate as its own planner step."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"
        steps.append(
            (
                name,
                lambda point=point, name=name: _map_guarded_point(
                    name=name,
                    map_id=map_id,
                    child=BT.Move(
                        point,
                        pause_on_combat=pause_on_combat,
                        tolerance=tolerance,
                        flag_heroes_to_waypoint=False,
                        log=False,
                    ),
                    skip_if_in_maps=skip_if_in_maps,
                ),
            )
        )

    return steps


def _vanquish_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[Vec2f],
    *,
    clear_area_radius: float = Range.Spirit.value,
    pause_on_combat: bool = True,
    move_tolerance: float = 150.0,
    skip_if_in_maps: Sequence[int] = (),
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Expose every Vanquish coordinate as its own planner step."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"
        def _build(
            point: Vec2f=point,
            name: str=name,
        ) -> BehaviorTree:
            run = BT.Sequence(
                name=name,
                children=[
                    BT.VanquishNode(
                        [point],
                        pause_on_combat=pause_on_combat,
                        flag_heroes_to_waypoint=False,
                        name=name,
                        clear_area_radius=Range.Earshot.value,
                        move_tolerance=move_tolerance,
                        log=False,
                    ),
                    WaitForRecoverablePartyDeaths(name),
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


def _reset_statistics() -> None:
    """Reset all Vloxen run/drop statistics while keeping character names."""
    global _total_runs, _session_runs
    global _total_run_time, _fastest_run, _slowest_run
    global _l1_total_time, _l1_fastest, _l1_slowest
    global _l2_total_time, _l2_fastest, _l2_slowest
    global _l3_total_time, _l3_fastest, _l3_slowest
    global _t_run_start, _t_l2_start, _t_l3_start
    global _current_run_time, _current_l1_time
    global _current_l2_time, _current_l3_time

    _total_runs = 0
    _session_runs = 0

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

    _t_run_start = 0.0
    _t_l2_start = 0.0
    _t_l3_start = 0.0

    _current_run_time = 0.0
    _current_l1_time = 0.0
    _current_l2_time = 0.0
    _current_l3_time = 0.0

    # Keep known account keys so _save_statistics() overwrites
    # persisted all-time Glacial Blade counters with zero.
    for key in list(_gb_drops):
        _gb_drops[key] = 0

    _session_gb.clear()

    # Prevent stale before/after chest snapshots from surviving the reset.
    for section in (
        _GB_SNAPSHOT_SECTION,
        _GB_RUN_SECTION,
    ):
        for key in _settings.items(section).keys():
            _settings.set(section, key, 0)

    _save_statistics()

    PySystem.Console.Log(
        MODULE_NAME,
        "Vloxen statistics reset.",
        PySystem.Console.MessageType.Success,
    )



def _draw_statistics() -> None:
    from Py4GWCoreLib import Color

    global _scramble_accounts

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
        return (
            _fmt_time(total / _total_runs)
            if _total_runs > 0
            else "--:--"
        )

    def _runs_per_drop(runs: int, drops: int) -> str:
        return f"{runs / drops:.1f}" if drops > 0 else "-"

    table_flags = (
        PyImGui.TableFlags.Borders
        | PyImGui.TableFlags.RowBg
        | PyImGui.TableFlags.SizingFixedFit
        | PyImGui.TableFlags.NoHostExtendX
    )
    header_color = 26 | (38 << 8) | (51 << 16) | (255 << 24)
    column_width = 72.0
    row_height = 22.0

    def _header_row(labels: tuple[str, ...]) -> None:
        PyImGui.table_next_row(0, row_height)
        PyImGui.table_set_bg_color(2, header_color, -1)
        for index, label in enumerate(labels):
            PyImGui.table_set_column_index(index)
            PyImGui.text(label)

    PyImGui.text_colored("Vloxen Excavations Statistics", gold)
    PyImGui.separator()
    PyImGui.spacing()

    _scramble_accounts = PyImGui.checkbox(
        "Hide Account Names",
        _scramble_accounts,
    )

    PyImGui.same_line()

    if PyImGui.button("Reset Statistics"):
        _reset_statistics()

    session_gb = sum(_session_gb.values())
    total_gb = sum(_gb_drops.values())

    PyImGui.text_colored("Session Overview", cyan)
    if PyImGui.begin_table("##vloxen_bt_session", 2, table_flags):
        for label in ("Runs", "GB"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                column_width,
            )
        _header_row(("Runs", "GB"))
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate((_session_runs, session_gb)):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Total Overview", cyan)
    if PyImGui.begin_table("##vloxen_bt_all_time", 3, table_flags):
        for label in ("Runs", "GB", "GB Avg"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                column_width,
            )
        _header_row(("Runs", "GB", "GB Avg"))
        values = (
            _total_runs,
            str(total_gb),
            _runs_per_drop(_total_runs, total_gb),
        )
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Run Timings", cyan)
    if PyImGui.begin_table("##vloxen_bt_timings", 5, table_flags):
        for label in ("Floor", "Current", "Avg", "Best", "Worst"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                column_width,
            )
        _header_row(("Floor", "Current", "Avg", "Best", "Worst"))

        now = time.monotonic()
        run_active = _t_run_start > 0.0
        l1_active = run_active and _t_l2_start <= 0.0
        l2_active = _t_l2_start > 0.0 and _t_l3_start <= 0.0
        l3_active = _t_l3_start > 0.0

        timing_rows = (
            (
                "Overall",
                now - _t_run_start if run_active else _current_run_time,
                run_active,
                _total_run_time,
                _fastest_run,
                _slowest_run,
            ),
            (
                "Floor 1",
                now - _t_run_start if l1_active else _current_l1_time,
                l1_active,
                _l1_total_time,
                _l1_fastest,
                _l1_slowest,
            ),
            (
                "Floor 2",
                now - _t_l2_start if l2_active else _current_l2_time,
                l2_active,
                _l2_total_time,
                _l2_fastest,
                _l2_slowest,
            ),
            (
                "Floor 3",
                now - _t_l3_start if l3_active else _current_l3_time,
                l3_active,
                _l3_total_time,
                _l3_fastest,
                _l3_slowest,
            ),
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
    PyImGui.text_colored("Glacial Blades Drops", cyan)
    if PyImGui.begin_table("##vloxen_bt_gb_drops", 4, table_flags):
        PyImGui.table_setup_column(
            "Account",
            PyImGui.TableColumnFlags.WidthStretch,
        )
        for label in ("Session", "All Time", "Runs/Drop"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                column_width,
            )
        _header_row(("Account", "Session", "All Time", "Avg"))

        keys = sorted(set(_session_gb) | set(_gb_drops) | set(_char_names))
        session_total = 0
        all_time_total = 0

        for key in keys:
            session_count = _session_gb.get(key, 0)
            all_time_count = _gb_drops.get(key, 0)
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
            PyImGui.text(_runs_per_drop(_total_runs, all_time_count))

        PyImGui.table_next_row(0, row_height)
        PyImGui.table_set_column_index(0)
        PyImGui.text_colored("Total", gold)
        PyImGui.table_set_column_index(1)
        PyImGui.text_colored(str(session_total), gold)
        PyImGui.table_set_column_index(2)
        PyImGui.text_colored(str(all_time_total), gold)
        PyImGui.table_set_column_index(3)
        PyImGui.text_colored(
            _runs_per_drop(_total_runs, all_time_total),
            gold,
        )

        PyImGui.end_table()



UMBRAL_GROTTO = 639
VLOXEN_L1 = 604
VLOXEN_L2 = 605
VLOXEN_L3 = 606
ZOLDARK_CHEST_GADGET_ID = 8930

L1_ROUTE_A = [Vec2f(-14012.69, 17499.42), Vec2f(-13940.80, 14189.62), Vec2f(-15562.73, 12802.01), Vec2f(-15866.67, 12077.89), Vec2f(-16674.63, 11373.40), Vec2f(-17888.89, 8412.45), Vec2f(-15903.08, 7179.44), Vec2f(-16412.41, 5098.74),]
L1_ROUTE_B = [Vec2f(-17947.12, 362.90), Vec2f(-17453.41, -1710.54), Vec2f(-17048.75, -4133.35), Vec2f(-17400.95, -7678.41), Vec2f(-15420.14, -9642.28),]
L1_ROUTE_C = [Vec2f(-11938.26, -10147.11), Vec2f(-9661.54, -8094.25), Vec2f(-8263.11, -8681.05), Vec2f(-7779.47, -9563.11), Vec2f(-7015.26, -10162.46), Vec2f(-6277.48, -10446.44), Vec2f(-5766.41, -11150.74)]
L2_ROUTE_2 = [Vec2f(9272.21, 18650.75), Vec2f(9357.84, 17255.71), Vec2f(10692.47, 17235.91), Vec2f(9373.50, 17102.35), Vec2f(7753.37, 16823.10)]
L2_ROUTE_3 = [Vec2f(7263.72, 14475.96), Vec2f(8239.53, 12474.26), Vec2f(6443.35, 10855.06), Vec2f(5937.82, 9730.58), Vec2f(6718.14, 7955.17), Vec2f(7185.29, 6997.63), Vec2f(6778.87, 6530.81), Vec2f(6272.23, 5274.37), Vec2f(5962.67, 4599.72), Vec2f(4811.26, 3809.84), Vec2f(4363.93, 3114.47),]
L2_ROUTE_4 = [Vec2f(5975.64, 1657.54), Vec2f(7019.73, 1388.40), Vec2f(9097.66, 2302.15), Vec2f(11002.14, 2834.40), Vec2f(11598.77, 1514.75), Vec2f(12591.34, 826.54), Vec2f(13339.67, 736.97), Vec2f(13349.67, 756.97), Vec2f(11986.45, 1082.84), Vec2f(11334.95, 2398.49),]
L2_ROUTE_5 = [Vec2f(12259.09, 4419.84), Vec2f(11408.72, 5959.38), Vec2f(10575.46, 7052.96), Vec2f(10526.70, 9283.91), Vec2f(11008.47, 11289.71), Vec2f(10859.30, 12733.59), Vec2f(11111.02, 14245.50), Vec2f(11876.39, 14981.00), Vec2f(12886.33, 13917.00), Vec2f(13774.89, 13214.02), Vec2f(12447.64, 14130.26), Vec2f(13918.97, 13000.46),]
L2_ROUTE_6 = [Vec2f(14603.51, 11518.10), Vec2f(14848.56, 10721.82), Vec2f(14943.88, 10133.65), Vec2f(16288.51, 10017.23), Vec2f(16610.79, 11236.86), Vec2f(17450.86, 12110.67), Vec2f(17376.05, 13146.70), Vec2f(17731.17, 14903.24), Vec2f(17647.40, 16110.80), Vec2f(17119.44, 13801.64), Vec2f(17108.33, 11535.42), Vec2f(15757.00, 9195.92), Vec2f(15508.02, 7016.37), Vec2f(15127.75, 5611.38), Vec2f(15376.79, 4918.63), Vec2f(15649.25, 3954.62), Vec2f(17677.01, 1252.00)]
L2_ROUTE_7 = [Vec2f(17970.06, 5.71), Vec2f(17501.62, -2752.30), Vec2f(17051.55, -4762.02), Vec2f(17000.95, -6870.13)]
L3_ROUTE_2 = [Vec2f(-10391.98, -18317.89), Vec2f(-8342.72, -16899.33), Vec2f(-6496.76, -17201.72), Vec2f(-6507.50, -15145.49), Vec2f(-5693.61, -14118.42), Vec2f(-3188.40, -13957.91),]
L3_ROUTE_3 = [Vec2f(-738.81, -12194.23), Vec2f(-676.24, -10331.64), Vec2f(421.13, -7568.55), Vec2f(1209.92, -6534.67), Vec2f(1078.16, -4993.53), Vec2f(1290.89, -4647.87), Vec2f(825.54, -7097.56), Vec2f(-446.09, -9633.60), Vec2f(-710.72, -12101.01), Vec2f(-635.45, -13022.32)]
L3_BOSS_ROUTE = [Vec2f(-590.76, -13250.43), Vec2f(414.37, -14659.19), Vec2f(1571.07, -15311.25), Vec2f(1852.93, -15672.27)]


_L1_LATER_MAPS = (VLOXEN_L2, VLOXEN_L3)
_L2_LATER_MAPS = (VLOXEN_L3,)
_L2_GEARBOX_PHASES = (
    (L2_ROUTE_2, Vec2f(7399.38, 16863.55)),
    (L2_ROUTE_3, Vec2f(4103.38, 2812.96)),
    (L2_ROUTE_4, Vec2f(11634.61, 2337.24)),
    (L2_ROUTE_5, Vec2f(14124.39, 12534.04)),
)


def PrepareRun() -> BehaviorTree:
    already_inside = BT.Selector(name="Already Inside Vloxen", children=[BT.IsCurrentMap(map_id=m, log=False) for m in DUNGEON_MAPS])
    prepare = BT.Sequence(
        name="Prepare Vloxen Run",
        map_id_or_name=UMBRAL_GROTTO,
        random_travel=True,
        children=[
            InventoryCheckAndMaintenance(),
            BT.CreateParty(hero_ids=[4, 24, 25, 14], multibox_invite=True, timeout_ms=30_000, log=True),
            BT.AbandonQuest(quest_id=QUEST_ID, multi_account=True, include_self=True, timeout_ms=10_000, log=True),
            BT.MoveAndDialog(
                Vec2f(-24734.23, 11842.46),
                dialog_id=0x833C01,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(QUEST_ID, timeout_ms=15_000),
            _runtime_difficulty_node(),
            _runtime_restock_node(),
            _runtime_consumable_upkeep_node(False),
        ],
    )
    return BT.Selector(name="Prepare Run Or Resume", children=[already_inside, prepare])


def EnterVloxen() -> BehaviorTree:
    later = BT.Selector(name="Vloxen Already Entered", children=[BT.IsCurrentMap(map_id=m, log=False) for m in DUNGEON_MAPS])
    entry = BT.Sequence(
        name="Umbral Grotto To Vloxen",
        children=[
            _runtime_consumable_upkeep_node(False),
            BT.Move(Vec2f(-26428, 10433), pause_on_combat=False, log=False),
            BT.MoveAndExitMap(Vec2f(-25900, 10750), target_map_id=VLOXEN_L1, log=True),
            BT.WaitForMapLoad(map_id=VLOXEN_L1, timeout_ms=60_000),
            _runtime_consumable_upkeep_node(True),
        ],
    )
    return BT.Selector(name="Enter Vloxen", children=[later, entry])


def Level1_Start() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 1 Start",
        map_id=VLOXEN_L1,
        child=BT.Sequence(
            name="Vloxen Level 1 Start",
            children=[
                _runtime_consumable_upkeep_node(True),
                _mark_run_start_node(),
                _glacial_blade_statistics_node(after_chest=False),
                UseAvailableSummoningStone("l1"),
                BT.AddModelToLootWhitelist(BOSS_KEY_MODEL_ID),
                BT.AddModelToLootWhitelist(DUNGEON_KEY_MODEL_ID),
                BT.MoveAndDialog(
                    Vec2f(-13833.55, 19224.39),
                    dialog_id=0x84,
                    multi_account=True,
                    log=True,
                ),
            ],
        ),
        skip_if_in_maps=(VLOXEN_L2, VLOXEN_L3),
    )


def Level2_Start() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 2 Start",
        map_id=VLOXEN_L2,
        child=BT.Sequence(
            name="Vloxen Level 2 Start",
            children=[
                _mark_l2_start_node(),
                ResetMasterGearCombatPolicy(),
                UseAvailableSummoningStone("l2"),
                BT.AddModelToLootWhitelist(BOSS_KEY_MODEL_ID),
                BT.AddModelToLootWhitelist(DUNGEON_KEY_MODEL_ID),
                BT.MoveAndDialog(
                    Vec2f(8825.54, 19266.63),
                    dialog_id=0x84,
                    multi_account=True,
                    log=True,
                ),
            ],
        ),
        skip_if_in_maps=_L2_LATER_MAPS,
    )


def Level3_Start() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 3 Start",
        map_id=VLOXEN_L3,
        child=BT.Sequence(
            name="Vloxen Level 3 Start",
            children=[
                _mark_l3_start_node(),
                UseAvailableSummoningStone("l3"),
                BT.AddModelToLootWhitelist(BOSS_KEY_MODEL_ID),
                BT.AddModelToLootWhitelist(DUNGEON_KEY_MODEL_ID),
                BT.MoveAndDialog(
                    Vec2f(-12500.44, -17889.25),
                    dialog_id=0x84,
                    multi_account=True,
                    log=True,
                ),
            ],
        ),
    )


def Level3_OpenChest() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 3 Open Zoldark Chest",
        map_id=VLOXEN_L3,
        child=BT.Sequence(
            name="Open Zoldark's Chest",
            children=[
                BT.Move([Vec2f(2740, -15282), Vec2f(3600, -15985)]),
                _record_run_end_node(),
                _runtime_consumable_upkeep_node(False),
                BT.MoveAndInteractWithGadget(
                    gadget_id=ZOLDARK_CHEST_GADGET_ID,
                    pos=Vec2f(3594.00, -17518.00),
                    search_distance=700.0,
                    interaction_distance=Range.Nearby.value,
                    interaction_count=2,
                    interaction_interval_ms=1000,
                    account_settle_ms=3_000,
                    timeout_ms=90_000,
                    multi_account=True,
                    include_self=True,
                    log=True,
                    ignore_destination_npcs=False,
                    ignore_destination_gadgets=True,
                ),
                _glacial_blade_statistics_node(after_chest=True),
            ],
        ),
    )


def CollectDredgingReward() -> BehaviorTree:
    already_collected = BT.Sequence(
        name="Dredging Reward Already Collected",
        children=[
            BT.IsQuestState(quest_id=QUEST_ID, state="missing", log=False),
            BT.Succeeder("DredgingRewardAlreadyCollected"),
        ],
    )
    collect = BT.Sequence(
        name="Collect Dredging The Depths Reward",
        children=[
            BT.MoveAndDialog(
                Vec2f(-24725.55, 11821.42),
                dialog_id=0x833C07,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForQuestCleared(QUEST_ID, timeout_ms=15_000),
            
        ],
    )
    return BT.Selector(
        name="Resolve Dredging Reward",
        children=[already_collected, collect],
    )


def ReturnToUmbralAfterRun() -> BehaviorTree:
    """Return the party to Umbral Grotto after the dungeon chest."""
    return BT.Resign(
        wait_for_map_load=True,
        target_map_id=UMBRAL_GROTTO,
        multi_account=True,
        timeout_ms=10_000,
        log=True,
    )


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        ("Initialize", InitializeBot),
        ("Prepare Run", PrepareRun),
        ("Enter Vloxen", EnterVloxen),
        ("Level 1 Start", Level1_Start),
    ]

    # Level 1
    steps.extend(_vanquish_point_steps(
        "Level 1 Shrine 2 Route", VLOXEN_L1, L1_ROUTE_A,
        skip_if_in_maps=_L1_LATER_MAPS,
    ))
    steps.extend(_vanquish_point_steps(
        "Level 1 Shrine 3 Route", VLOXEN_L1, L1_ROUTE_B,
        skip_if_in_maps=_L1_LATER_MAPS,
    ))
    steps.extend(_vanquish_point_steps(
        "Level 1 Boss Key Route", VLOXEN_L1, L1_ROUTE_C,
        skip_if_in_maps=_L1_LATER_MAPS,
    ))
    steps.append(_guarded_step(
        "Level 1 Open Boss Lock", VLOXEN_L1,
        lambda: BT.MoveAndInteractWithGadget(
            pos=Vec2f(-2446.79, -15763.88), search_distance=1_000.0,
            interaction_distance=Range.Nearby.value, interaction_count=1,
            interaction_interval_ms=750, account_settle_ms=1_500,
            timeout_ms=30_000, multi_account=False, include_self=True, log=True,
        ),
        _L1_LATER_MAPS,
    ))
    steps.extend(_movement_point_steps(
        "Level 1 Exit Approach", VLOXEN_L1,
        [Vec2f(-2575.37, -17432.12), Vec2f(-2453.90, -18385.10)],
        pause_on_combat=False, skip_if_in_maps=_L1_LATER_MAPS,
    ))
    steps.append(_guarded_step(
        "Level 1 Enter Level 2", VLOXEN_L1,
        lambda: BT.Sequence(
            name="Enter Vloxen Level 2",
            children=[
                BT.MoveAndExitMap(Vec2f(-2150, -19800), target_map_id=VLOXEN_L2, log=True),
                BT.WaitForMapLoad(map_id=VLOXEN_L2, timeout_ms=60_000),
            ],
        ),
        _L1_LATER_MAPS,
    ))

    # Level 2
    steps.append(("Level 2 Start", Level2_Start))
    for index, (route, gearbox_pos) in enumerate(_L2_GEARBOX_PHASES, start=1):
        steps.extend(_master_gear_point_steps(
            f"Level 2 Gearbox {index} Route", VLOXEN_L2, route,
            skip_if_in_maps=_L2_LATER_MAPS,
        ))
        steps.append(_guarded_step(
            f"Level 2 Open Gearbox {index}", VLOXEN_L2,
            lambda pos=gearbox_pos: BT.MoveAndInteractWithGadget(
                pos=pos, search_distance=1_000.0,
                interaction_distance=Range.Nearby.value, interaction_count=1,
                interaction_interval_ms=750, account_settle_ms=1_500,
                timeout_ms=30_000, multi_account=False, include_self=True, log=True,
            ),
            _L2_LATER_MAPS,
        ))

    steps.extend(_vanquish_point_steps(
        "Level 2 Dungeon Key Route", VLOXEN_L2, L2_ROUTE_6[:5],
        skip_if_in_maps=_L2_LATER_MAPS,
    ))
    steps.append(_guarded_step(
        "Level 2 Open Dungeon Lock", VLOXEN_L2,
        lambda: BT.MoveAndInteractWithGadget(
            pos=Vec2f(16603.56, 11368.58), search_distance=1_000.0,
            interaction_distance=Range.Nearby.value, interaction_count=1,
            interaction_interval_ms=750, account_settle_ms=1_500,
            timeout_ms=30_000, multi_account=False, include_self=True, log=True,
        ),
        _L2_LATER_MAPS,
    ))
    steps.extend(_vanquish_point_steps(
        "Level 2 Keg Station Route", VLOXEN_L2, L2_ROUTE_6[5:10],
        skip_if_in_maps=_L2_LATER_MAPS,
    ))
    steps.append(_guarded_step(
        "Level 2 Take Dwarven Keg", VLOXEN_L2,
        lambda: BT.MoveAndInteractWithGadget(
            pos=Vec2f(17716.05, 16126.33), search_distance=1_000.0,
            interaction_distance=Range.Nearby.value, interaction_count=1,
            interaction_interval_ms=750, account_settle_ms=1_500,
            timeout_ms=30_000, multi_account=False, include_self=True, log=True,
        ),
        _L2_LATER_MAPS,
    ))
    steps.extend(_movement_point_steps(
        "Level 2 Carry Keg To Brittle Wall", VLOXEN_L2,
        [Vec2f(15394.34, 4834.77)], pause_on_combat=False,
        skip_if_in_maps=_L2_LATER_MAPS,
    ))
    steps.append(_guarded_step(
        "Level 2 Drop Keg At Brittle Wall", VLOXEN_L2,
        lambda: BT.DropBundle(log=True), _L2_LATER_MAPS,
    ))
    steps.extend(_vanquish_point_steps(
        "Level 2 Final Shrine Route", VLOXEN_L2, L2_ROUTE_6[10:],
        skip_if_in_maps=_L2_LATER_MAPS,
    ))
    steps.extend(_vanquish_point_steps(
        "Level 2 Exit Route", VLOXEN_L2, L2_ROUTE_7,
        skip_if_in_maps=_L2_LATER_MAPS,
    ))
    steps.append(_guarded_step(
        "Level 2 Enter Level 3", VLOXEN_L2,
        lambda: BT.Sequence(
            name="Enter Vloxen Level 3",
            children=[
                BT.MoveAndExitMap(Vec2f(19200, -6890), target_map_id=VLOXEN_L3, log=True),
                BT.WaitForMapLoad(map_id=VLOXEN_L3, timeout_ms=60_000),
            ],
        ),
        _L2_LATER_MAPS,
    ))

    # Level 3
    steps.append(("Level 3 Start", Level3_Start))
    steps.extend(_vanquish_point_steps("Level 3 Mid Shrine Route", VLOXEN_L3, L3_ROUTE_2))
    steps.extend(_vanquish_point_steps("Level 3 Boss Key And Lock Route", VLOXEN_L3, L3_ROUTE_3))
    steps.append(_guarded_step(
        "Level 3 Open Boss Lock", VLOXEN_L3,
        lambda: BT.MoveAndInteractWithGadget(
            pos=Vec2f(-495.66, -13095.34), search_distance=1_000.0,
            interaction_distance=Range.Nearby.value, interaction_count=1,
            interaction_interval_ms=750, account_settle_ms=1_500,
            timeout_ms=30_000, multi_account=False, include_self=True, log=True,
        ),
    ))
    steps.extend(_vanquish_point_steps("Level 3 Zoldark Arena", VLOXEN_L3, L3_BOSS_ROUTE))
    steps.append(_guarded_step(
        "Level 3 Clear Zoldark",
        VLOXEN_L3,
        lambda: BT.ClearEnemiesInArea(
            pos=Vec2f(1473.77, -16306.52),
            radius=Range.Spirit.value,
            allowed_alive_enemies=0,
            log=False,
        ),
    ))
    steps.extend([
        ("Level 3 Open Zoldark Chest", Level3_OpenChest),
        ("Return To Umbral Grotto", ReturnToUmbralAfterRun),
        ("Collect Dredging Reward", CollectDredgingReward),
    ])
    return steps


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
                enable_nearest_shrine_recovery=True,
                heroai_state_logging=False,
            ),
        )
        botting_tree.AddServiceTree(
            "SummoningStoneRecoveryService",
            SummoningStoneRecoveryService,
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
    _tick_direct_pcon_upkeep()
    tree.UI.draw_window(icon_path=TEXTURE,
        main_child_dimensions=(430, 390),
        extra_tabs=[("Statistics", _draw_statistics), ("Config", _draw_run_config)],
    )


if __name__ == "__main__":
    main()
