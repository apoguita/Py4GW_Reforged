from __future__ import annotations

from collections.abc import Callable
import os
import time
import math

import PySystem
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib import GLOBAL_CACHE, Player, SharedCommandType
from Py4GWCoreLib.Listeners import Listeners
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.enums_src.Player_enums import PlayerStatus
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import (
    CONSET_UPKEEPS,
    CONSUMABLE_UPKEEPS as ALL_CONSUMABLE_UPKEEPS,
)
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Widgets.System.Messaging import get_inventory_count, reset_inventory_count


# region Metadata

MODULE_NAME = "Frog Scepter BT"
INI_PATH = "Widgets/Automation/Bots/Missions/Dungeons/Frog Scepter BT"
INI_FILENAME = "Frog_Scepter_BT.ini"

TEXTURE = os.path.join(
    PySystem.Console.get_projects_path(),
    "Textures",
    "Module_Icons",
    "Frog Scepter.png",
)
MODULE_ICON = "Textures\\Module_Icons\\Frog Scepter.png"

# endregion


# region Identifiers

GADDS_ENCAMPMENT = 638
SPARKFLY_SWAMP = 558
BOGROOT_LEVEL_1 = 615
BOGROOT_LEVEL_2 = 616

TEKKS_QUEST_ID = 0x339
DWARVEN_BLESSING_DIALOG = 0x84
TEKKS_TAKE_DIALOG = 0x833901
TEKKS_REWARD_DIALOG = 0x833907

BOSS_KEY_MODEL_ID = 25416
SUMMON_MODEL_IDS = (30209, 37810, 31155)
FROGGY_MODEL_IDS = tuple(range(1953, 1975))
GB_MODEL_ID = 2474

PCON_UPKEEPS = tuple(
    int(model_id)
    for model_id in ALL_CONSUMABLE_UPKEEPS
    if int(model_id) not in CONSET_UPKEEPS
)
CONSET_RESTOCK_ITEMS = tuple((int(model_id), 10) for model_id in CONSET_UPKEEPS)
PCON_RESTOCK_ITEMS = tuple((int(model_id), 10) for model_id in PCON_UPKEEPS)
SUMMON_RESTOCK_ITEMS = tuple((int(model_id), 10) for model_id in SUMMON_MODEL_IDS)

# endregion


# region Routes

GADDS_EXIT = Vec2f(-9451.37, -19766.40)
SPARKFLY_BLESSING = Vec2f(-8950.0, -19843.0)
TEKKS_POSITION = Vec2f(12500.0, 22648.0)

SPARKFLY_TO_TEKKS = [
    Vec2f(-11521,-11694),
    Vec2f(-9117, -8543),
    Vec2f(-6026,-2485),
    Vec2f(1216, 9780),
    Vec2f(10970,23481),

]

BOGROOT_ENTRANCE_PATH = [
    Vec2f(11676.01, 22685.0),
    Vec2f(11562.77, 24059.0),
    Vec2f(13097.0, 26393.0),
]

L1_BLESSING = Vec2f(19045.95, 7877.0)
L1_PATH_1 = [
    Vec2f(18148,7553),
    Vec2f(10030.42, 7026.09),
    Vec2f(8058,7742),
]
L1_PATH_2 = [
    Vec2f(945,521),
    Vec2f(1114, 166)
]

L1_PATH_3 = [
    Vec2f(2112, -11454),
    Vec2f(1210,-14420),
    Vec2f(7317,-18067),
]

L2_ENTRY_BLESSING = Vec2f(-11055.0, -5551.0)
L2_PATH_1 = [

    Vec2f(-11164,-3795),
    Vec2f(-12071,-1409),
    Vec2f(-6727,3297),
    Vec2f(-3769,5280),
    Vec2f(-2963,7834),
    Vec2f(-106,9683),
    Vec2f(-193,10887),

]
L2_BLESSING_2 = Vec2f(-955.0, 10984.0)
L2_PATH_2 = [
    Vec2f(3240,13784),
    Vec2f(5660,13616),
    Vec2f(6837,10120),
    Vec2f(8284,6418),
]
L2_BLESSING_3 = Vec2f(8591.0, 4285.0)
L2_PATH_3 = [
    Vec2f(8366,2377),
    Vec2f(11327,-5481),
    Vec2f(17249,-5822),

    
]
L2_DOOR = Vec2f(17867.55, -6250.63)
L2_PATH_4 = [
    Vec2f(17555.0, -11963.0),
    Vec2f(18761.0, -12747.0),

]
L2_BLESSING_4 = Vec2f(19619.0, -11498.0)
FROGGY_BOSS_PATH = [
    Vec2f(14079.80, -17776.0),
    Vec2f(15116.40, -18733.0),
]
BOGROOT_CHEST_POSITION = Vec2f(14982.66, -19122.0)

# endregion


# region Runtime settings

_SETTINGS_SECTION = "Settings"
_STATS_SECTION = "Statistics"
_FROGGY_DROPS_SECTION = "Froggy Drops"
_FROGGY_SNAPSHOT_SECTION = "Froggy Snapshot"
_FROGGY_RUN_SECTION = "Froggy Run"
_GB_DROPS_SECTION = "GB Drops"
_GB_SNAPSHOT_SECTION = "GB Snapshot"
_GB_RUN_SECTION = "GB Run"
_CHAR_NAMES_SECTION = "Character Names"

_INVENTORY_QUERY_POLL_MS = 200
_INVENTORY_QUERY_TIMEOUT_MS = 10_000

_settings = Settings(f"{INI_PATH}/{INI_FILENAME}", "global")
_settings_loaded = False
_statistics_loaded = False

_use_hard_mode = True
_restock_conset = True
_activate_conset = True
_restock_pcons = True
_activate_pcons = True
_use_summoning_stone = True
_runtime_consumables_enabled = True

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
_froggy_drops: dict[str, int] = {}
_gb_drops: dict[str, int] = {}
_char_names: dict[str, str] = {}

# Session-only statistics.
_session_runs = 0
_session_froggy: dict[str, int] = {}
_session_gb: dict[str, int] = {}
_scramble_accounts = False

# Active and latest completed timing values.
_t_run_start = 0.0
_t_l2_start = 0.0
_current_run_time = 0.0
_current_l1_time = 0.0
_current_l2_time = 0.0


def _load_settings() -> None:
    global _settings_loaded
    global _use_hard_mode, _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons, _use_summoning_stone

    if _settings_loaded:
        _load_statistics()
        return

    _use_hard_mode = _settings.get_bool(_SETTINGS_SECTION, "HardMode", True)
    _restock_conset = _settings.get_bool(_SETTINGS_SECTION, "RestockConset", True)
    _activate_conset = _settings.get_bool(_SETTINGS_SECTION, "ActivateConset", True)
    _restock_pcons = _settings.get_bool(_SETTINGS_SECTION, "RestockPcons", True)
    _activate_pcons = _settings.get_bool(_SETTINGS_SECTION, "ActivatePcons", True)
    _use_summoning_stone = _settings.get_bool(_SETTINGS_SECTION, "UseSummoningStone", True)
    _settings_loaded = True
    _load_statistics()


def _save_settings() -> None:
    _settings.set(_SETTINGS_SECTION, "HardMode", _use_hard_mode)
    _settings.set(_SETTINGS_SECTION, "RestockConset", _restock_conset)
    _settings.set(_SETTINGS_SECTION, "ActivateConset", _activate_conset)
    _settings.set(_SETTINGS_SECTION, "RestockPcons", _restock_pcons)
    _settings.set(_SETTINGS_SECTION, "ActivatePcons", _activate_pcons)
    _settings.set(_SETTINGS_SECTION, "UseSummoningStone", _use_summoning_stone)


def _load_statistics() -> None:
    global _statistics_loaded
    global _total_runs, _total_run_time, _fastest_run, _slowest_run
    global _l1_total_time, _l1_fastest, _l1_slowest
    global _l2_total_time, _l2_fastest, _l2_slowest

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

    for key in _settings.items(_FROGGY_DROPS_SECTION).keys():
        _froggy_drops[key] = _settings.get_int(_FROGGY_DROPS_SECTION, key, 0)
    for key in _settings.items(_GB_DROPS_SECTION).keys():
        _gb_drops[key] = _settings.get_int(_GB_DROPS_SECTION, key, 0)
    for section in (_FROGGY_SNAPSHOT_SECTION, _FROGGY_RUN_SECTION, _GB_SNAPSHOT_SECTION, _GB_RUN_SECTION):
        for key in _settings.items(section).keys():
            _froggy_drops.setdefault(key, 0)
            _gb_drops.setdefault(key, 0)
    for key in _settings.items(_CHAR_NAMES_SECTION).keys():
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
    ):
        _settings.set(_STATS_SECTION, f"{floor}_total_time", total)
        _settings.set(_STATS_SECTION, f"{floor}_fastest", 0.0 if fastest == float("inf") else fastest)
        _settings.set(_STATS_SECTION, f"{floor}_slowest", slowest)
    for key, total in _froggy_drops.items():
        _settings.set(_FROGGY_DROPS_SECTION, key, total)
    for key, total in _gb_drops.items():
        _settings.set(_GB_DROPS_SECTION, key, total)
    for key, name in _char_names.items():
        _settings.set(_CHAR_NAMES_SECTION, key, name)


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    enabled: list[int] = []
    if _activate_conset:
        enabled.extend(int(model_id) for model_id in CONSET_UPKEEPS)
    if _activate_pcons:
        enabled.extend(PCON_UPKEEPS)
    return tuple(dict.fromkeys(enabled))


def _configure_runtime_upkeeps(enabled: bool | None = None) -> None:
    global _runtime_consumables_enabled
    if enabled is not None:
        _runtime_consumables_enabled = bool(enabled)
    if botting_tree is None:
        return
    botting_tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=_enabled_consumable_upkeeps() if _runtime_consumables_enabled else (),
        enable_party_wipe_recovery=True,
        heroai_state_logging=False,
    )


def _runtime_consumable_node(enabled: bool) -> BehaviorTree:
    def _apply(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        _configure_runtime_upkeeps(enabled)
        return BehaviorTree.NodeState.SUCCESS
    return BehaviorTree(BehaviorTree.ActionNode(
        name=("Resume Consumables" if enabled else "Suspend Consumables"),
        action_fn=_apply,
        aftercast_ms=0,
    ))


def _runtime_difficulty_node() -> BehaviorTree:
    return BT.Subtree(name="Apply Selected Difficulty", subtree_fn=lambda _node: BT.SetHardMode(_use_hard_mode, log=True))


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


def UseAvailableSummoningStone() -> BehaviorTree:
    """
    Use the first available summoning stone once.

    Summoning stones are handled as one-shot consumables and are therefore
    kept outside the continuous consumable upkeep service.
    """
    if not _use_summoning_stone:
        return BT.Succeeder(
            "SummoningStoneDisabled",
        )

    return BT.Selector(
        name="Use Available Summoning Stone",
        children=[
            BTItems.UseConsumable(
                int(model_id),
            )
            for model_id in SUMMON_MODEL_IDS
        ]
        + [
            BT.Succeeder(
                "NoSummoningStoneAvailable",
            ),
        ],
    )



def _draw_run_config() -> None:
    import PyImGui
    global _use_hard_mode, _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons, _use_summoning_stone
    _load_settings()
    PyImGui.text("Frog Scepter Run Config")
    PyImGui.separator()
    changed = False
    for label, variable_name in (
        ("Hard Mode (HM)", "_use_hard_mode"),
        ("Restock conset from storage", "_restock_conset"),
        ("Activate / maintain conset", "_activate_conset"),
        ("Restock pcons from storage", "_restock_pcons"),
        ("Activate / maintain pcons", "_activate_pcons"),
        ("Use summoning stones", "_use_summoning_stone"),
    ):
        old_value = bool(globals()[variable_name])
        new_value = PyImGui.checkbox(label, old_value)
        if new_value != old_value:
            globals()[variable_name] = new_value
            changed = True
    if changed:
        _save_settings()
        _configure_runtime_upkeeps()

# endregion


# region Statistics


def _account_key(email: str) -> str:
    return str(email).replace("@", "_at_").replace(".", "_")


def _display_email(key: str) -> str:
    return str(key).replace("_at_", "@").replace("_", ".")


def _known_account_keys() -> list[str]:
    return sorted(set(_froggy_drops) | set(_gb_drops) | set(_session_froggy) | set(_session_gb))


def _account_label(key: str) -> str:
    if not _scramble_accounts:
        return _char_names.get(key) or _display_email(key)
    keys = _known_account_keys()
    index = keys.index(key) + 1 if key in keys else 0
    return f"Player {index}"


def _shared_accounts() -> list[object]:
    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False, include_isolated=True)
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
        character_name = str(getattr(getattr(account, "AgentData", None), "CharacterName", "") or "").strip()
        if email and character_name:
            key = _account_key(email)
            if _char_names.get(key) != character_name:
                _char_names[key] = character_name
                changed = True
    return changed


def _statistics_action_node(name: str, action: Callable[[], None]) -> BehaviorTree:
    def _run(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            action()
        except Exception as exc:
            PySystem.Console.Log(MODULE_NAME, f"[Statistics] {name} failed: {exc}", PySystem.Console.MessageType.Warning)
        return BehaviorTree.NodeState.SUCCESS
    return BehaviorTree(BehaviorTree.ActionNode(name=name, action_fn=_run, aftercast_ms=0))


def _mark_run_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_run_start, _t_l2_start, _current_run_time, _current_l1_time, _current_l2_time
        _t_run_start = time.monotonic()
        _t_l2_start = 0.0
        _current_run_time = _current_l1_time = _current_l2_time = 0.0
    return _statistics_action_node("Mark Run Start", _mark)


def _mark_l2_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_l2_start, _current_l1_time
        now = time.monotonic()
        _t_l2_start = now
        _current_l1_time = now - _t_run_start if _t_run_start > 0.0 else 0.0
    return _statistics_action_node("Mark Level 2 Start", _mark)


def _record_run_end_node() -> BehaviorTree:
    def _record() -> None:
        global _total_runs, _session_runs, _total_run_time, _fastest_run, _slowest_run
        global _l1_total_time, _l1_fastest, _l1_slowest, _l2_total_time, _l2_fastest, _l2_slowest
        global _current_run_time, _current_l1_time, _current_l2_time, _t_run_start, _t_l2_start
        now = time.monotonic()
        valid = _t_run_start > 0.0 and _t_l2_start > _t_run_start
        if valid:
            run_time = now - _t_run_start
            l1_time = _t_l2_start - _t_run_start
            l2_time = now - _t_l2_start
            _current_run_time, _current_l1_time, _current_l2_time = run_time, l1_time, l2_time
            _total_run_time += run_time
            _fastest_run = min(_fastest_run, run_time)
            _slowest_run = max(_slowest_run, run_time)
            _l1_total_time += l1_time
            _l1_fastest = min(_l1_fastest, l1_time)
            _l1_slowest = max(_l1_slowest, l1_time)
            _l2_total_time += l2_time
            _l2_fastest = min(_l2_fastest, l2_time)
            _l2_slowest = max(_l2_slowest, l2_time)
            PySystem.Console.Log(MODULE_NAME, f"[Statistics] Run complete - Total {run_time:.0f}s | L1 {l1_time:.0f}s | L2 {l2_time:.0f}s", PySystem.Console.MessageType.Success)
        _total_runs += 1
        _session_runs += 1
        _t_run_start = _t_l2_start = 0.0
        _save_statistics()
    return _statistics_action_node("Record Successful Run", _record)


def _accumulate_drop(account_key: str, count: int, all_time: dict[str, int], session: dict[str, int]) -> None:
    all_time.setdefault(account_key, 0)
    if count > 0:
        all_time[account_key] += int(count)
        session[account_key] = session.get(account_key, 0) + int(count)


def _inventory_count(model_id_min: int, model_id_max: int) -> int:
    return sum(int(GLOBAL_CACHE.Inventory.GetModelCount(model_id)) for model_id in range(int(model_id_min), int(model_id_max) + 1))


def _inventory_statistics_node(*, after_chest: bool) -> BehaviorTree:
    node_name = "Record Drops After Final Chest" if after_chest else "Snapshot Inventories At Dungeon Entry"
    state: dict[str, object] = {"started": False, "local_email": "", "account_keys": [], "requests": [], "request_index": 0, "waiting": False, "request_started_at": 0.0}
    def _reset() -> None:
        state.update(started=False, local_email="", account_keys=[], requests=[], request_index=0, waiting=False, request_started_at=0.0)
    def _start() -> None:
        _load_statistics(); _refresh_character_names()
        local_email = str(Player.GetAccountEmail() or "").strip()
        local_key = _account_key(local_email or "local")
        froggy_section = _FROGGY_RUN_SECTION if after_chest else _FROGGY_SNAPSHOT_SECTION
        gb_section = _GB_RUN_SECTION if after_chest else _GB_SNAPSHOT_SECTION
        _settings.set(froggy_section, local_key, _inventory_count(FROGGY_MODEL_IDS[0], FROGGY_MODEL_IDS[-1]))
        _settings.set(gb_section, local_key, _inventory_count(GB_MODEL_ID, GB_MODEL_ID))
        account_keys = [local_key]
        requests: list[dict[str, object]] = []
        for account in _shared_accounts():
            email = str(getattr(account, "AccountEmail", "") or "").strip()
            if not email or email == local_email: continue
            key = _account_key(email)
            if key not in account_keys: account_keys.append(key)
            requests.extend([
                {"email": email, "key": key, "model_min": FROGGY_MODEL_IDS[0], "model_max": FROGGY_MODEL_IDS[-1], "section": froggy_section, "label": "Froggy"},
                {"email": email, "key": key, "model_min": GB_MODEL_ID, "model_max": GB_MODEL_ID, "section": gb_section, "label": "Glacial Blades"},
            ])
        for key in account_keys:
            _froggy_drops.setdefault(key, 0); _gb_drops.setdefault(key, 0)
        state.update(started=True, local_email=local_email, account_keys=account_keys, requests=requests)
    def _finish() -> None:
        if not after_chest:
            PySystem.Console.Log(MODULE_NAME, f"[Statistics] Dungeon-entry inventory snapshot completed for {len(state['account_keys'])} account(s).", PySystem.Console.MessageType.Info)
            _save_statistics(); return
        total_froggy = total_gb = 0
        for key in state["account_keys"]:
            k = str(key)
            before = _settings.get_int(_FROGGY_SNAPSHOT_SECTION, k, -1); after = _settings.get_int(_FROGGY_RUN_SECTION, k, -1)
            delta = max(0, after-before) if before >= 0 and after >= 0 else 0
            _accumulate_drop(k, delta, _froggy_drops, _session_froggy); total_froggy += delta
            before = _settings.get_int(_GB_SNAPSHOT_SECTION, k, -1); after = _settings.get_int(_GB_RUN_SECTION, k, -1)
            delta = max(0, after-before) if before >= 0 and after >= 0 else 0
            _accumulate_drop(k, delta, _gb_drops, _session_gb); total_gb += delta
        _save_statistics()
        PySystem.Console.Log(MODULE_NAME, f"[Statistics] Final chest recorded - Froggy {total_froggy} | Glacial Blades {total_gb}", PySystem.Console.MessageType.Success)
    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if bool(node.blackboard.get("USER_INTERRUPT_ACTIVE", False)):
                _reset(); return BehaviorTree.NodeState.FAILURE
            if not bool(state["started"]): _start()
            requests = state["requests"]
            while int(state["request_index"]) < len(requests):
                i = int(state["request_index"]); request = requests[i]
                email = str(request["email"]); model_min = int(request["model_min"]); model_max = int(request["model_max"])
                if not bool(state["waiting"]):
                    reset_inventory_count(email, model_min, model_max)
                    _settings.set(str(request["section"]), str(request["key"]), -1)
                    GLOBAL_CACHE.ShMem.SendMessage(str(state["local_email"]), email, SharedCommandType.InventoryQuery, (float(model_min), float(model_max), 0.0, 0.0), ("report_inventory_count",))
                    state["waiting"] = True; state["request_started_at"] = time.monotonic()
                    return BehaviorTree.NodeState.RUNNING
                count = int(get_inventory_count(email, model_min, model_max))
                if count >= 0:
                    _settings.set(str(request["section"]), str(request["key"]), count)
                    state["request_index"] = i + 1; state["waiting"] = False; continue
                if (time.monotonic() - float(state["request_started_at"])) * 1000.0 >= _INVENTORY_QUERY_TIMEOUT_MS:
                    PySystem.Console.Log(MODULE_NAME, f"[Statistics] Inventory query timed out for {request['label']} on {_account_label(str(request['key']))}.", PySystem.Console.MessageType.Warning)
                    state["request_index"] = i + 1; state["waiting"] = False; continue
                return BehaviorTree.NodeState.RUNNING
            _finish(); _reset(); return BehaviorTree.NodeState.SUCCESS
        except Exception as exc:
            PySystem.Console.Log(MODULE_NAME, f"[Statistics] {node_name} failed: {exc}", PySystem.Console.MessageType.Warning)
            _reset(); return BehaviorTree.NodeState.SUCCESS
    return BehaviorTree(BehaviorTree.ActionNode(name=node_name, action_fn=_tick, aftercast_ms=_INVENTORY_QUERY_POLL_MS))


def _draw_statistics() -> None:
    import PyImGui
    from Py4GWCoreLib import Color
    global _scramble_accounts
    _load_statistics()
    if _refresh_character_names(): _save_statistics()
    gold = Color(255, 210, 80, 255).to_tuple_normalized()
    cyan = Color(80, 210, 255, 255).to_tuple_normalized()
    live = Color(100, 180, 255, 255).to_tuple_normalized()
    def _fmt_time(seconds: float) -> str:
        try: value = float(seconds)
        except (TypeError, ValueError, OverflowError): return "--:--"
        if not math.isfinite(value) or value <= 0.0: return "--:--"
        minutes, remaining = divmod(int(value), 60)
        return f"{minutes:02d}:{remaining:02d}"
    def _avg_time(total: float) -> str:
        return _fmt_time(total / _total_runs) if _total_runs > 0 else "--:--"
    def _runs_per_drop(runs: int, drops: int) -> str:
        return f"{runs / drops:.1f}" if drops > 0 else "-"
    flags = PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg | PyImGui.TableFlags.SizingFixedFit | PyImGui.TableFlags.NoHostExtendX
    header_color = 26 | (38 << 8) | (51 << 16) | (255 << 24)
    width = 72.0; row_height = 22.0
    def _header(labels: tuple[str, ...]) -> None:
        PyImGui.table_next_row(0, row_height); PyImGui.table_set_bg_color(2, header_color, -1)
        for i, label in enumerate(labels): PyImGui.table_set_column_index(i); PyImGui.text(label)
    PyImGui.text_colored("Frog Scepter Statistics", gold); PyImGui.separator(); PyImGui.spacing()
    _scramble_accounts = PyImGui.checkbox("Hide Account Names", _scramble_accounts)
    session_froggy=sum(_session_froggy.values()); session_gb=sum(_session_gb.values()); total_froggy=sum(_froggy_drops.values()); total_gb=sum(_gb_drops.values())
    PyImGui.text_colored("Session Overview", cyan)
    if PyImGui.begin_table("##froggy_bt_session", 3, flags):
        for label in ("Runs", "Froggy", "GB"): PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, width)
        _header(("Runs", "Froggy", "GB")); PyImGui.table_next_row(0,row_height)
        for i,v in enumerate((_session_runs,session_froggy,session_gb)): PyImGui.table_set_column_index(i); PyImGui.text(str(v))
        PyImGui.end_table()
    PyImGui.spacing(); PyImGui.text_colored("Total Overview", cyan)
    if PyImGui.begin_table("##froggy_bt_all_time",5,flags):
        for label in ("Runs","Froggy","Frog Avg","GB","GB Avg"): PyImGui.table_setup_column(label,PyImGui.TableColumnFlags.WidthFixed,width)
        _header(("Runs","Froggy","Frog Avg","GB","GB Avg")); PyImGui.table_next_row(0,row_height)
        for i,v in enumerate((_total_runs,total_froggy,_runs_per_drop(_total_runs,total_froggy),total_gb,_runs_per_drop(_total_runs,total_gb))): PyImGui.table_set_column_index(i); PyImGui.text(str(v))
        PyImGui.end_table()
    PyImGui.spacing(); PyImGui.text_colored("Run Timings", cyan)
    if PyImGui.begin_table("##froggy_bt_timings",5,flags):
        for label in ("Floor","Current","Avg","Best","Worst"): PyImGui.table_setup_column(label,PyImGui.TableColumnFlags.WidthFixed,width)
        _header(("Floor","Current","Avg","Best","Worst"))
        now=time.monotonic(); run_active=_t_run_start>0.0; l1_active=run_active and _t_l2_start<=0.0; l2_active=_t_l2_start>0.0
        rows=(("Overall",now-_t_run_start if run_active else _current_run_time,run_active,_total_run_time,_fastest_run,_slowest_run),("Floor 1",now-_t_run_start if l1_active else _current_l1_time,l1_active,_l1_total_time,_l1_fastest,_l1_slowest),("Floor 2",now-_t_l2_start if l2_active else _current_l2_time,l2_active,_l2_total_time,_l2_fastest,_l2_slowest))
        for label,current,is_live,total,fastest,slowest in rows:
            PyImGui.table_next_row(0,row_height); PyImGui.table_set_column_index(0); PyImGui.text(label); PyImGui.table_set_column_index(1)
            (PyImGui.text_colored(_fmt_time(current),live) if is_live else PyImGui.text(_fmt_time(current)))
            PyImGui.table_set_column_index(2); PyImGui.text(_avg_time(total)); PyImGui.table_set_column_index(3); PyImGui.text(_fmt_time(fastest)); PyImGui.table_set_column_index(4); PyImGui.text(_fmt_time(slowest))
        PyImGui.end_table()
    def _drop_table(table_id: str,title: str,session: dict[str,int],all_time: dict[str,int]) -> None:
        PyImGui.spacing(); PyImGui.text_colored(title,cyan)
        if not PyImGui.begin_table(table_id,4,flags): return
        PyImGui.table_setup_column("Account",PyImGui.TableColumnFlags.WidthStretch)
        for label in ("Session","All Time","Runs/Drop"): PyImGui.table_setup_column(label,PyImGui.TableColumnFlags.WidthFixed,width)
        _header(("Account","Session","All Time","Avg")); keys=sorted(set(session)|set(all_time)); st=at=0
        for key in keys:
            s=session.get(key,0); a=all_time.get(key,0); st+=s; at+=a
            PyImGui.table_next_row(0,row_height)
            for i,v in enumerate((_account_label(key),s,a,_runs_per_drop(_total_runs,a))): PyImGui.table_set_column_index(i); PyImGui.text(str(v))
        PyImGui.table_next_row(0,row_height)
        for i,v in enumerate(("Total",st,at,_runs_per_drop(_total_runs,at))): PyImGui.table_set_column_index(i); PyImGui.text_colored(str(v),gold)
        PyImGui.end_table()
    _drop_table("##froggy_bt_froggy_drops","Frog Scepter Drops",_session_froggy,_froggy_drops)
    _drop_table("##froggy_bt_gb_drops","Glacial Blades Drops",_session_gb,_gb_drops)

# endregion


# region Bot tree

initialized = False
botting_tree: BottingTree | None = None


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
            isolation_enabled=True,
            configure_fn=lambda tree: tree.Config.ConfigureUpkeep(
                looting_enabled=True,
                resurrection_scroll=True,
                auto_inventory_handler_enabled=True,
                activate_widget_list=("LootManager",),
                consumable_upkeeps=_enabled_consumable_upkeeps(),
                enable_party_wipe_recovery=True,
                heroai_state_logging=False,
            ),
        )
    return botting_tree


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()
    return BT.Sequence(
        name="Initialize Frog Scepter BT",
        children=[
            bot.Config.Aggressive(
                multi_account=True,
                auto_loot=True,
                resurrection_scroll=True,
            ),
            BT.SetPlayerStatus(PlayerStatus.Offline, log=True),
            BT.LogMessage(
                message="Frog Scepter BT initialized.",
                module_name=MODULE_NAME,
            ),
        ],
    )


def PreparePartyAndSupplies() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Preparation - Already In Bogroot",
        children=[
            BT.Selector(
                name="Check Bogroot Floor",
                children=[
                    BT.IsCurrentMap(map_id=BOGROOT_LEVEL_1, log=True),
                    BT.IsCurrentMap(map_id=BOGROOT_LEVEL_2, log=True),
                ],
            ),
            BT.Succeeder("Bogroot Preparation Already Done"),
        ],
    )

    normal = BT.Sequence(
        name="Prepare Party And Supplies From Gadd's Encampment",
        map_id_or_name=GADDS_ENCAMPMENT,
        random_travel=True,
        children=[
            BT.CreateParty(multibox_invite=True, timeout_ms=30_000, log=True),
            BT.AbandonQuest(
                quest_id=TEKKS_QUEST_ID,
                multi_account=True,
                include_self=True,
                timeout_ms=10_000,
                log=True,
            ),
            _runtime_difficulty_node(),
            _runtime_restock_node(),
        ],
    )
    return BT.Selector(
        name="Prepare Frog Scepter Party And Supplies",
        children=[already_inside, normal],
    )


def TravelToTekks() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Tekks Travel - Already In Bogroot",
        children=[
            BT.Selector(
                name="Check Bogroot Floor",
                children=[
                    BT.IsCurrentMap(map_id=BOGROOT_LEVEL_1, log=True),
                    BT.IsCurrentMap(map_id=BOGROOT_LEVEL_2, log=True),
                ],
            ),
            BT.Succeeder("Tekks Travel Already Done"),
        ],
    )

    normal = BT.Sequence(
        name="Travel From Gadd's Encampment To Tekks",
        children=[
            BT.MoveAndExitMap(GADDS_EXIT, target_map_id=SPARKFLY_SWAMP, log=True),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.MoveAndDialog(
                SPARKFLY_BLESSING,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
            _runtime_consumable_node(True),
            BT.VanquishNode(
                SPARKFLY_TO_TEKKS,
                name="Sparkfly Route To Tekks",
                flag_heroes_to_waypoint=False,
                log=False,
                move_tolerance=500
            ),
            BT.WaitUntilOutOfCombat(timeout_ms=90_000),
            BT.Move(TEKKS_POSITION, pause_on_combat=False, log=False),
        ],
    )

    return BT.Selector(
        name="Travel To Tekks",
        children=[already_inside, normal],
    )


def HandleTekksQuest() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Tekks Handler - Already In Bogroot",
        children=[
            BT.Selector(
                name="Check Bogroot Floor",
                children=[
                    BT.IsCurrentMap(map_id=BOGROOT_LEVEL_1, log=True),
                    BT.IsCurrentMap(map_id=BOGROOT_LEVEL_2, log=True),
                ],
            ),
            BT.Succeeder("Tekks Handler Already Done"),
        ],
    )

    active = BT.Sequence(
        name="Tekks' War Already Active",
        children=[
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="active", log=True),
            BT.Succeeder("Continue With Active Tekks Quest"),
        ],
    )

    completed = BT.Sequence(
        name="Collect And Retake Tekks' War",
        children=[
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="complete", log=True),
            BT.MoveAndDialog(
                TEKKS_POSITION,
                TEKKS_REWARD_DIALOG,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForQuestCleared(TEKKS_QUEST_ID, timeout_ms=15_000),
            BT.MoveAndDialog(
                TEKKS_POSITION,
                TEKKS_TAKE_DIALOG,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(TEKKS_QUEST_ID, timeout_ms=15_000),
        ],
    )

    missing = BT.Sequence(
        name="Take Tekks' War",
        children=[
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="missing", log=True),
            BT.MoveAndDialog(
                TEKKS_POSITION,
                TEKKS_TAKE_DIALOG,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(TEKKS_QUEST_ID, timeout_ms=15_000),
        ],
    )

    return BT.Selector(
        name="Handle Tekks Quest",
        children=[already_inside, active, completed, missing],
    )


def EnterBogroot() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Bogroot Entry - Already Inside",
        children=[
            BT.Selector(
                name="Check Bogroot Floor",
                children=[
                    BT.IsCurrentMap(map_id=BOGROOT_LEVEL_1, log=True),
                    BT.IsCurrentMap(map_id=BOGROOT_LEVEL_2, log=True),
                ],
            ),
            BT.Succeeder("Bogroot Entry Already Done"),
        ],
    )

    normal = BT.Sequence(
        name="Enter Bogroot Growths",
        children=[
            BT.Move(
                BOGROOT_ENTRANCE_PATH,
                pause_on_combat=False,
                ignore_destination_obstacles=True,
                log=False,
            ),
            BT.WaitForMapLoad(map_id=BOGROOT_LEVEL_1, timeout_ms=60_000),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
        ],
    )

    return BT.Selector(name="Enter Bogroot Growths", children=[already_inside, normal])


def Level1_FirstRoute() -> BehaviorTree:
    return BT.Sequence(
        name="Bogroot Level 1 - First Route",
        children=[
            _mark_run_start_node(),
            _inventory_statistics_node(after_chest=False),
            BT.AddModelToLootWhitelist(BOSS_KEY_MODEL_ID),
            UseAvailableSummoningStone(),
            BT.MoveAndDialog(
                L1_BLESSING,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
            BT.VanquishNode(
                L1_PATH_1,
                name="Level 1 Route 1",
                flag_heroes_to_waypoint=False,
                log=False,
            ),
        ],
    )


def Level1_SecondRoute() -> BehaviorTree:
    return BT.Sequence(
        name="Bogroot Level 1 - Second Route",
        children=[
            BT.VanquishNode(
                L1_PATH_2,
                name="Level 1 Route 2",
                flag_heroes_to_waypoint=False,
                log=False,
            ),
        ],
    )


def Level1_ToLevel2() -> BehaviorTree:
    return BT.Sequence(
        name="Bogroot Level 1 - Route To Level 2",
        children=[
            BT.VanquishNode(
                L1_PATH_3,
                name="Level 1 Route 3",
                flag_heroes_to_waypoint=False,
                log=True,
            ),
            BT.MoveAndExitMap(Vec2f(7731,-19298), target_map_id=BOGROOT_LEVEL_2),
            _mark_l2_start_node(),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
        ],
    )


def Level2_FirstRoute() -> BehaviorTree:
    return BT.Sequence(
        name="Bogroot Level 2 - First Route",
        children=[
            UseAvailableSummoningStone(),
            BT.AddModelToLootWhitelist(BOSS_KEY_MODEL_ID),
            BT.MoveAndDialog(
                L2_ENTRY_BLESSING,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
            BT.VanquishNode(
                L2_PATH_1,
                name="Level 2 Route 1",
                flag_heroes_to_waypoint=False,
                log=False,
            ),
            BT.MoveAndDialog(
                L2_BLESSING_2,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
        ],
    )


def Level2_SecondRoute() -> BehaviorTree:
    return BT.Sequence(
        name="Bogroot Level 2 - Second Route",
        children=[
            BT.VanquishNode(
                L2_PATH_2,
                name="Level 2 Route 2",
                flag_heroes_to_waypoint=False,
                log=False,
            ),
            BT.MoveAndDialog(
                L2_BLESSING_3,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
        ],
    )


def Level2_OpenDoor() -> BehaviorTree:
    return BT.Sequence(
        name="Bogroot Level 2 - Open Boss Door",
        children=[
            BT.VanquishNode(
                L2_PATH_3,
                name="Level 2 Route 3",
                flag_heroes_to_waypoint=False,
                log=False,
            ),
            BT.MoveAndInteractWithGadget(
                pos=L2_DOOR,
                pause_on_combat=True,
                log=True,
            ),
        ],
    )


def Level2_ToBoss() -> BehaviorTree:
    return BT.Sequence(
        name="Bogroot Level 2 - Route To Boss",
        children=[
            BT.VanquishNode(
                L2_PATH_4,
                name="Level 2 Route 4",
                flag_heroes_to_waypoint=False,
                log=False,
            ),
            BT.MoveAndDialog(
                L2_BLESSING_4,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
            BT.VanquishNode(
                FROGGY_BOSS_PATH,
                name="Route To Prismatic Ooze",
                flag_heroes_to_waypoint=False,
                log=False,
            ),
            BT.WaitForClearEnemiesInArea(
                16017.74,
                -19040.79,
                radius=Range.Compass.value,
                allowed_alive_enemies=0,
                interact_interval_ms=750,
                stable_clear_ms=10_000,
                keep_player_near_center=False,
                center_tolerance=750.0,
                log=True,
            ),
        ],
    )


def OpenFinalChest() -> BehaviorTree:
    return BT.Sequence(
        name="Open Bogroot Final Chest",
        children=[
            BT.Move(BOGROOT_CHEST_POSITION, pause_on_combat=False, log=False),
            BT.Wait(2_000),
            BT.MoveAndInteractWithGadget(
                pos=BOGROOT_CHEST_POSITION,
                search_distance=700.0,
                interaction_distance=Range.Nearby.value,
                interaction_count=2,
                interaction_interval_ms=1_000,
                account_settle_ms=3_000,
                timeout_ms=90_000,
                multi_account=True,
                include_self=True,
                log=True,
            ),
            BT.LootItems(distance=Range.Spirit.value),
            _inventory_statistics_node(after_chest=True),
            _record_run_end_node(),
            BT.Wait(5_000),
        ],
    )

def CollectTekksRewardAndRestart() -> BehaviorTree:
    reward_collected_inside = BT.Sequence(
        name="Collect Tekks Reward Inside Dungeon",
        children=[
            BT.IsQuestState(
                quest_id=TEKKS_QUEST_ID,
                state="complete",
                log=True,
            ),

            BT.Move(
                Vec2f(14079.80, -17776.0),
                pause_on_combat=False,
                log=False,
            ),

            BT.LogMessage(
                message=(
                    "Tekks' War is complete. Looking for Tekks "
                    "inside Bogroot Growths."
                ),
                module_name=MODULE_NAME,
            ),

            CollectTekksRewardInsideDungeon(),

            BT.WaitForQuestCleared(
                TEKKS_QUEST_ID,
                timeout_ms=15_000,
            ),

            BT.LogMessage(
                message=(
                    "Tekks was found inside the dungeon and "
                    "the Tekks' War reward was collected."
                ),
                module_name=MODULE_NAME,
            ),
        ],
    )

    reward_not_collected_inside = BT.Sequence(
        name="Tekks Unavailable Inside Dungeon",
        children=[
            BT.LogMessage(
                message=(
                    "Tekks was not found inside the dungeon or "
                    "the reward could not be collected. The quest "
                    "state will be resolved after returning to "
                    "Sparkfly Swamp."
                ),
                module_name=MODULE_NAME,
            ),
            BT.Succeeder(
                "Inside Tekks Reward Unavailable",
            ),
        ],
    )

    return BT.Sequence(
        name="Collect Tekks Reward And Restart",
        children=[
            _runtime_consumable_node(False),

            BT.Selector(
                name="Resolve Inside Tekks Reward",
                children=[
                    reward_collected_inside,
                    reward_not_collected_inside,
                ],
            ),

            BT.LogMessage(
                message=(
                    "Waiting for the end-of-dungeon countdown "
                    "and the return to Sparkfly Swamp."
                ),
                module_name=MODULE_NAME,
            ),

            BT.WaitForMapLoad(
                map_id=SPARKFLY_SWAMP,
                timeout_ms=190_000,
            ),

            BT.WaitUntilOnExplorable(
                timeout_ms=30_000,
            ),

            BT.Wait(2_000),

            BT.LogMessage(
                message=(
                    "The party has returned to Sparkfly Swamp. "
                    "Preparing the next Bogroot run."
                ),
                module_name=MODULE_NAME,
            ),

            BT.Move(
                TEKKS_POSITION,
                pause_on_combat=False,
                log=False,
            ),

            HandleTekksQuest(),

            EnterBogroot(),

            _runtime_consumable_node(True),
        ],
    )

def CollectTekksRewardInsideDungeon() -> BehaviorTree:
    """
    Collect Tekks' War reward from Tekks inside Bogroot Growths.

    Tekks is searched twice if necessary. The routine then interacts with the
    current target and selects the first available dialogue option for every
    account in the multibox party.
    """

    return BT.Sequence(
        name="Collect Tekks Reward Inside Dungeon",
        children=[
            BT.Selector(
                name="Find Tekks Inside Dungeon",
                children=[
                    BT.TargetAgentByName(
                        agent_name="Tekks",
                        log=True,
                    ),
                    BT.Sequence(
                        name="Second Tekks Search",
                        children=[
                            BT.Wait(5_000),
                            BT.TargetAgentByName(
                                agent_name="Tekks",
                                log=True,
                            ),
                        ],
                    ),
                ],
            ),

            BT.LogMessage(
                message=(
                    "Tekks was found inside the dungeon. "
                    "Attempting to collect the Tekks' War reward "
                    "using automatic dialogue."
                ),
                module_name=MODULE_NAME,
            ),

            BT.InteractTargetAndAutoDialog(
                buttons=0,
                multi_account=True,
                aftercast_ms=500,
                log=True,
            ),

            BT.WaitForQuestCleared(
                TEKKS_QUEST_ID,
                timeout_ms=15_000,
            ),

            BT.LogMessage(
                message=(
                    "The Tekks' War reward was successfully "
                    "collected inside the dungeon."
                ),
                module_name=MODULE_NAME,
            ),
        ],
    )

# endregion


# region Execution


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Initialize Bot", InitializeBot),
        ("Prepare Party And Supplies", PreparePartyAndSupplies),
        ("Travel To Tekks", TravelToTekks),
        ("Handle Tekks Quest", HandleTekksQuest),
        ("Enter Bogroot Growths", EnterBogroot),
        ("Level 1 First Route", Level1_FirstRoute),
        ("Level 1 Second Route", Level1_SecondRoute),
        ("Level 1 Route To Level 2", Level1_ToLevel2),
        ("Level 2 First Route", Level2_FirstRoute),
        ("Level 2 Second Route", Level2_SecondRoute),
        ("Level 2 Open Boss Door", Level2_OpenDoor),
        ("Level 2 Route To Boss", Level2_ToBoss),
        ("Open Final Chest", OpenFinalChest),
        ("Collect Reward And Prepare Restart", CollectTekksRewardAndRestart),
    ]


def main() -> None:
    global initialized

    if not initialized:
        _load_settings()
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()
    tree.UI.draw_window(
        icon_path=TEXTURE,
        iconwidth=96,
        main_child_dimensions=(440, 400),
        extra_tabs=[
            ("Statistics", _draw_statistics),
            ("Run Config", _draw_run_config),
        ],
    )


if __name__ == "__main__":
    main()
