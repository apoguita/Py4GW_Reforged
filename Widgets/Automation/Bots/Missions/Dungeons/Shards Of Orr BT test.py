from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import time
from Py4GWCoreLib.Listeners import Listeners
import PySystem
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters import LootFilters
from Py4GWCoreLib import Agent, GLOBAL_CACHE, AgentArray, Player, SharedCommandType, Inventory
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.enums_src.Player_enums import PlayerStatus
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import CONSET_UPKEEPS, CONSUMABLE_UPKEEPS as ALL_CONSUMABLE_UPKEEPS
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Widgets.System.Messaging import get_inventory_count, reset_inventory_count, get_inventory_state, reset_inventory_state


PathPoint = Vec2f | tuple[float, float] | tuple[int, int]


# endregion


# region Script metadata

MODULE_NAME = "Shards of Orr BT Test Geyser"
INI_PATH = "Widgets/Automation/Bots/Missions/Dungeons/Shards of Orr BT test"
INI_FILENAME = "Shards_of_Orr_BT_Test_Geyser.ini"


# endregion


# region Game identifiers

# Maps
VLOXS_FALL = 624
ARBOR_BAY = 485
SOO_LEVEL_1 = 581
SOO_LEVEL_2 = 582
SOO_LEVEL_3 = 583

# Quest / dialogs
LOST_SOULS_QUEST_ID = 0x324
DWARVEN_BLESSING_DIALOG = 0x84
SHANDRA_TAKE_DIALOG = 0x832401
SHANDRA_REWARD_DIALOG = 0x832407
ARBOR_BLESSING_DIALOG = 0x84

# Consumables
# Conset model IDs.
ESSENCE_OF_CELERITY = 24859
GRAIL_OF_MIGHT = 24860
ARMOR_OF_SALVATION = 24861


SUMMON_MODEL_IDS = (30209, 37810, 31155)
PCON_UPKEEPS = tuple((int(model_id) for model_id in ALL_CONSUMABLE_UPKEEPS if int(model_id) not in CONSET_UPKEEPS))

CONSET_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple(((model_id, 10) for model_id in CONSET_UPKEEPS))
PCON_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple(((model_id, 10) for model_id in PCON_UPKEEPS))

SUMMON_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple(((model_id, 10) for model_id in SUMMON_MODEL_IDS))

# Final chest drops tracked by the statistics tab.
BDS_MODEL_IDS = tuple(range(1987, 2008))
BDS_MODEL_ID_MIN = BDS_MODEL_IDS[0]
BDS_MODEL_ID_MAX = BDS_MODEL_IDS[-1]
GB_MODEL_ID = 2474

INVENTORY_BAG_IDS = frozenset((1, 2, 3, 4))
ID_KIT_MODEL_IDS = (int(ModelID.Identification_Kit.value), int(ModelID.Superior_Identification_Kit.value))
SALVAGE_KIT_MODEL_IDS = (int(ModelID.Expert_Salvage_Kit.value),)
MERCHANT_RULES_WIDGET_NAME = "MerchantRules"
INVENTORY_PLUS_WIDGET_NAME = "InventoryPlus"

INVENTORY_TRAVEL_REGION = 2      # Europe
INVENTORY_TRAVEL_DISTRICT = 1    # Europe English District 1
INVENTORY_TRAVEL_LANGUAGE = 0    # English
INVENTORY_MAINTENANCE_RETRY_COUNT = 2
INVENTORY_SNAPSHOT_SETTLE_MS = 2_000
INVENTORY_TRAVEL_TIMEOUT_MS = 60_000
INVENTORY_MERCHANT_TIMEOUT_MS = 240_000

TEXTURE = os.path.join(PySystem.Console.get_projects_path(), 'Textures', 'Module_Icons', 'BDS.png')


MODULE_ICON = "Textures\\Module_Icons\\BDS.png"

# endregion


# region Settings state

_SETTINGS_SECTION = "Settings"
_STATS_SECTION = "Statistics"
_BDS_DROPS_SECTION = "BDS Drops"
_BDS_SNAPSHOT_SECTION = "BDS Snapshot"
_BDS_RUN_SECTION = "BDS Run"
_GB_DROPS_SECTION = "GB Drops"
_GB_SNAPSHOT_SECTION = "GB Snapshot"
_GB_RUN_SECTION = "GB Run"
_CHAR_NAMES_SECTION = "Character Names"

_INVENTORY_QUERY_POLL_MS = 200
_INVENTORY_QUERY_TIMEOUT_MS = 10_000

# Global scope is intentional: run configuration and multibox statistics are
# shared by every account using this bot.
_settings_ini = Settings(f'{INI_PATH}/{INI_FILENAME}', 'global')
_settings_loaded = False

_use_hard_mode = True
_restock_conset = True
_activate_conset = True
_restock_pcons = True
_activate_pcons = True
_use_summoning_stone = True
_keep_torch_for_caster = True
_inventory_maintenance_enabled = True
_inventory_min_free_slots = 5
_inventory_min_id_kits = 1
_inventory_min_salvage_kits = 2
_runtime_consumables_enabled = True
_runtime_looting_enabled = True
_inventory_status_snapshot: dict[str, dict[str, object]] = {}

# Resolved once per run before the first tactical torch drop.  The value is
# cached because carrying a bundle can temporarily hide the equipped weapon
# type reported by the game.
_drop_torch_for_combat: bool | None = None

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
_bds_drops: dict[str, int] = {}
_gb_drops: dict[str, int] = {}
_char_names: dict[str, str] = {}

# Session-only statistics.
_session_runs = 0
_session_bds: dict[str, int] = {}
_session_gb: dict[str, int] = {}
_scramble_accounts = False
_statistics_reset_pending = False

# Active and most recently completed timings.
_t_run_start = 0.0
_t_l2_start = 0.0
_t_l3_start = 0.0
_current_run_time = 0.0
_current_l1_time = 0.0
_current_l2_time = 0.0
_current_l3_time = 0.0


# endregion


# region Routes and coordinates

# Coordinates
VLOXS_EXIT = Vec2f(15505.38, 12460.59)
ARBOR_BLESSING_NPC = Vec2f(16327.00, 11607.00)
SHANDRA_APPROACH = Vec2f(12056.00, -17882.00)

ARBOR_TO_SHANDRA_PATH = [Vec2f(13455.43, 10678.0), Vec2f(9850.0, 5025.0), Vec2f(11207.11, 1872.32), Vec2f(10452.02, 178.5), Vec2f(10782.86, -3321.0), Vec2f(8360.94, -6550.0), Vec2f(10382.85, -12342.0), Vec2f(10080.3, -13995.0),
    Vec2f(10667.0, -16116.0), Vec2f(10747.49, -17546.0), Vec2f(11156.0, -17802.0)]

LEVEL1_EXIT_TO_ARBOR = Vec2f(-15650.0, 8900.0)

SOO_ENTRANCE_PATH = [Vec2f(11177.0, -17683.0), Vec2f(10218.0, -18864.0), Vec2f(9519.0, -19968.0), Vec2f(9240.07, -20260.95)]

L1_PATH = [Vec2f(3720.16, 15370.78), Vec2f(6740.06, 11039.32), Vec2f(15757, 16952), Vec2f(16026.25, 16957.26), Vec2f(14255.37, 6189.6)]

L1_PATH_AFTER_DOOR = [Vec2f(17442.4, 2577.83), Vec2f(20181.6, 1203.7), Vec2f(20400.5, 1300.0)]

# Level 2 routes / torch mechanics
TORCH_MODEL_IDS = (22341, 22342)
TORCH_BUFF_ID = 2545

L2_BLESSING_NPC = Vec2f(-14076.0, -19457.0)


L2_TORCH_CHEST = Vec2f(-14709.0, -16548.0)
L2_FIRST_TORCH_DROP_POINT_PATH = [Vec2f(-11002.0, -17001.0)]
L2_RETURN_TO_FIRST_TORCH_PATH = [Vec2f(-9259.0, -17322.0), Vec2f(-9550, -17258), Vec2f(-10243, -17780)]
L2_BRAZIER_PART1 = [(-11303.0, -14596.0), (-11019.0, -11550.0), (-9028.0, -9021.0), (-6805.0, -11511.0), (-8984.0, -13842.0)]
L2_CLEANING_PATH = [Vec2f(-9011.27, -11536.79)]
L2_TO_ROOM2_DROP = (Vec2f(-10514.69, -9542.61), Vec2f(-11061.1, -7578.5))
L2_RETURN_TO_ROOM2_TORCH_PATH = [Vec2f(-10958.2, -4529.5), Vec2f(-11690.64, -3802.55)]
L2_ROOM2_PATH = [Vec2f(-8066.1, -4222.4), Vec2f(-7058.8, -4191.0)]

L2_BRAZIER_PART2 = [(-3717.0, -4254.0), (-8251.0, -3240.0), (-8278.0, -1670.0)]
L2_AFTER_PART2_POSITION = Vec2f(-5009.49, -2542.30)
L2_PATH_TO_LOCK = [Vec2f(-6798.8, -2436.4), Vec2f(-7063, -2017), Vec2f(-16335.1, -9004.5), (-18700.0, -9171.0)]
L2_DUNGEON_LOCK = Vec2f(-18725.0, -9171.0)
L2_EXIT_PATH = [Vec2f(-18610.0, -8636.0), Vec2f(-19254, -8256)]

# Level 3 routes
L3_ENTRY_BLESSING = Vec2f(17544.0, 18810.0)
L3_MAIN_PATH = [Vec2f(16325.98, 15981.14), Vec2f(14511, 19206), Vec2f(8539, 17072), Vec2f(3547, 8795), Vec2f(4813.8, 10340.7), Vec2f(2523, 8101), Vec2f(1923, 6151), Vec2f(198, 8176), Vec2f(-4228, 6901)]
    
    
L3_BRIGANT_ROOM = [Vec2f(-4528, 6301), Vec2f(-8203, 2775), Vec2f(-11428, 3600), Vec2f(-7903, 6601)]

L3_PATH_TO_TORCH = [Vec2f(-4723.0, 6703.0), Vec2f(-1280.0, 7880.0), Vec2f(3089.73, 8511.0), Vec2f(4963.0, 9974.0), Vec2f(9918.64, 19108.0), Vec2f(14709.0, 19526.0), Vec2f(16111.0, 17556.0)]
L3_TORCH_CHEST = Vec2f(16111.0, 17556.0)
L3_BRAZIERS = [(15692.0, 17111.0), (12969.0, 19842.0), (8236.0, 16950.0), (5549.0, 9920.0), (-536.0, 6109.0), (-3814.0, 5599.0), (-4959.0, 7558.0), (-7532.0, 4536.0), (-10984.0, 486.0), (-12621.0, 2948.0)]
L3_FENDI_PATH = [Vec2f(-8696, 6323), Vec2f(-9988, 7652), Vec2f(-12712.36, 13502.19)]
FENDI_CHEST_POSITION = (-15800.98, 16901.23)
FENDI_CHEST_GADGET_ID = 8934

# Fendi chest fire geysers.
# Probe-confirmed runtime gadget id and positions (map 583).
FENDI_GEYSER_GADGET_ID = 8015
# Probe-confirmed on 2026-08-14:
# Agent.GetNameProperties(gadget_id) carries bit 0x8000 while a Fendi geyser
# is actively venting. The same geyser was captured at 0x8022 (ON) and
# 0x0022 (OFF).
FENDI_GEYSER_ACTIVE_NAME_PROPERTY_BIT = 0x8000
FENDI_GEYSER_SAFETY_RADIUS = 250.0
FENDI_CHEST_LOOT_SCAN_RADIUS = 1_400.0
FENDI_SAFE_LOOT_TIMEOUT_MS = 75_000
FENDI_SAFE_LOOT_MAX_ATTEMPTS_PER_ITEM = 2
FENDI_GEYSER_FALLBACK_POSITIONS = (
    (-15866.0, 16574.0),
    (-14640.0, 17723.0),
    (-14641.0, 15252.0),
    (-16911.0, 15168.0),
    (-18053.0, 18215.0),
)

# Safe regroup point used immediately after the final chest multibox interaction.
FENDI_CHEST_SAFE_POSITION = Vec2f(-15885.85, 17100.0)

initialized = False
botting_tree: BottingTree | None = None

# endregion

# region Run config

def _load_settings() -> None:
    global _settings_loaded
    global _use_hard_mode, _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons, _use_summoning_stone
    global _keep_torch_for_caster
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots
    global _inventory_min_id_kits
    global _inventory_min_salvage_kits

    if _settings_loaded:
        _load_statistics()
        return

    _use_hard_mode = _settings_ini.get_bool(_SETTINGS_SECTION, "HardMode", True)
    _restock_conset = _settings_ini.get_bool(_SETTINGS_SECTION, "RestockConset", True)
    _activate_conset = _settings_ini.get_bool(_SETTINGS_SECTION, "ActivateConset", True)
    _restock_pcons = _settings_ini.get_bool(_SETTINGS_SECTION, "RestockPcons", True)
    _activate_pcons = _settings_ini.get_bool(_SETTINGS_SECTION, "ActivatePcons", True)
    _use_summoning_stone = _settings_ini.get_bool(_SETTINGS_SECTION, "UseSummoningStone", True)
    _keep_torch_for_caster = _settings_ini.get_bool(_SETTINGS_SECTION, 'KeepTorchForCaster', True)
    _inventory_maintenance_enabled = _settings_ini.get_bool(_SETTINGS_SECTION, 'InventoryMaintenanceEnabled', True)
    _inventory_min_free_slots = max(0, _settings_ini.get_int(_SETTINGS_SECTION, 'InventoryMinFreeSlots', 5))
    _inventory_min_id_kits = max(0, _settings_ini.get_int(_SETTINGS_SECTION, 'InventoryMinIdKits', 1))
    _inventory_min_salvage_kits = max(0, _settings_ini.get_int(_SETTINGS_SECTION, 'InventoryMinSalvageKits', 2))
    _settings_loaded = True
    _load_statistics()


def _save_settings() -> None:
    _settings_ini.set(_SETTINGS_SECTION, "HardMode", _use_hard_mode)
    _settings_ini.set(_SETTINGS_SECTION, "RestockConset", _restock_conset)
    _settings_ini.set(_SETTINGS_SECTION, "ActivateConset", _activate_conset)
    _settings_ini.set(_SETTINGS_SECTION, "RestockPcons", _restock_pcons)
    _settings_ini.set(_SETTINGS_SECTION, "ActivatePcons", _activate_pcons)
    _settings_ini.set(_SETTINGS_SECTION, "UseSummoningStone", _use_summoning_stone)
    _settings_ini.set(_SETTINGS_SECTION, 'KeepTorchForCaster', _keep_torch_for_caster)
    _settings_ini.set(_SETTINGS_SECTION, 'InventoryMaintenanceEnabled', _inventory_maintenance_enabled)
    _settings_ini.set(_SETTINGS_SECTION, 'InventoryMinFreeSlots', _inventory_min_free_slots)
    _settings_ini.set(_SETTINGS_SECTION, 'InventoryMinIdKits', _inventory_min_id_kits)
    _settings_ini.set(_SETTINGS_SECTION, 'InventoryMinSalvageKits', _inventory_min_salvage_kits)


def _load_statistics() -> None:
    global _statistics_loaded
    global _total_runs, _total_run_time, _fastest_run, _slowest_run
    global _l1_total_time, _l1_fastest, _l1_slowest
    global _l2_total_time, _l2_fastest, _l2_slowest
    global _l3_total_time, _l3_fastest, _l3_slowest

    if _statistics_loaded:
        return

    section = _STATS_SECTION
    _total_runs = _settings_ini.get_int(section, "total_runs", 0)
    _total_run_time = _settings_ini.get_float(section, "total_run_time", 0.0)

    fastest = _settings_ini.get_float(section, "fastest_run", 0.0)
    _fastest_run = float("inf") if fastest <= 0.0 else fastest
    _slowest_run = _settings_ini.get_float(section, "slowest_run", 0.0)

    _l1_total_time = _settings_ini.get_float(section, "l1_total_time", 0.0)
    fastest = _settings_ini.get_float(section, "l1_fastest", 0.0)
    _l1_fastest = float("inf") if fastest <= 0.0 else fastest
    _l1_slowest = _settings_ini.get_float(section, "l1_slowest", 0.0)

    _l2_total_time = _settings_ini.get_float(section, "l2_total_time", 0.0)
    fastest = _settings_ini.get_float(section, "l2_fastest", 0.0)
    _l2_fastest = float("inf") if fastest <= 0.0 else fastest
    _l2_slowest = _settings_ini.get_float(section, "l2_slowest", 0.0)

    _l3_total_time = _settings_ini.get_float(section, "l3_total_time", 0.0)
    fastest = _settings_ini.get_float(section, "l3_fastest", 0.0)
    _l3_fastest = float("inf") if fastest <= 0.0 else fastest
    _l3_slowest = _settings_ini.get_float(section, "l3_slowest", 0.0)

    # "local" was an old fallback key created when Player.GetAccountEmail()
    # temporarily returned an empty string. It is not a real account.
    _bds_drops.pop("local", None)
    _gb_drops.pop("local", None)
    _session_bds.pop("local", None)
    _session_gb.pop("local", None)
    _char_names.pop("local", None)

    for key in _settings_ini.items(_BDS_DROPS_SECTION).keys():
        if key == "local":
            continue
        _bds_drops[key] = _settings_ini.get_int(_BDS_DROPS_SECTION, key, 0)

    for key in _settings_ini.items(_GB_DROPS_SECTION).keys():
        if key == "local":
            continue
        _gb_drops[key] = _settings_ini.get_int(_GB_DROPS_SECTION, key, 0)

    for seed_section in (
        _BDS_SNAPSHOT_SECTION,
        _BDS_RUN_SECTION,
        _GB_SNAPSHOT_SECTION,
        _GB_RUN_SECTION,
    ):
        for key in _settings_ini.items(seed_section).keys():
            if key == "local":
                continue
            _bds_drops.setdefault(key, 0)
            _gb_drops.setdefault(key, 0)

    for key in _settings_ini.items(_CHAR_NAMES_SECTION).keys():
        if key == "local":
            continue
        name = str(_settings_ini.get_str(_CHAR_NAMES_SECTION, key, '') or '').strip()
        if name:
            _char_names[key] = name

    _statistics_loaded = True


def _save_statistics() -> None:
    section = _STATS_SECTION
    _settings_ini.set(section, "total_runs", _total_runs)
    _settings_ini.set(section, "total_run_time", _total_run_time)
    _settings_ini.set(section, 'fastest_run', 0.0 if _fastest_run == float('inf') else _fastest_run)
    _settings_ini.set(section, "slowest_run", _slowest_run)

    for floor, total, fastest, slowest in (
        ("l1", _l1_total_time, _l1_fastest, _l1_slowest),
        ("l2", _l2_total_time, _l2_fastest, _l2_slowest),
        ("l3", _l3_total_time, _l3_fastest, _l3_slowest),
    ):
        _settings_ini.set(section, f"{floor}_total_time", total)
        _settings_ini.set(section, f'{floor}_fastest', 0.0 if fastest == float('inf') else fastest)
        _settings_ini.set(section, f"{floor}_slowest", slowest)

    for key, total in _bds_drops.items():
        if key != "local":
            _settings_ini.set(_BDS_DROPS_SECTION, key, total)

    for key, total in _gb_drops.items():
        if key != "local":
            _settings_ini.set(_GB_DROPS_SECTION, key, total)

    for key, name in _char_names.items():
        if key != "local":
            _settings_ini.set(_CHAR_NAMES_SECTION, key, name)


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    """
    Return the consumables that must be continuously maintained.

    Summoning stones are excluded because they are one-shot items and must not
    be handled by ConsumableService.
    """
    enabled: list[int] = []

    if _activate_conset:
        enabled.extend(CONSET_UPKEEPS)

    if _activate_pcons:
        enabled.extend(PCON_UPKEEPS)

    return tuple(dict.fromkeys((int(model_id) for model_id in enabled)))


def _configure_runtime_upkeeps(*, consumables_enabled: bool | None=None, looting_enabled: bool | None=None) -> None:
    global _runtime_consumables_enabled, _runtime_looting_enabled

    if consumables_enabled is not None:
        _runtime_consumables_enabled = bool(consumables_enabled)
    if looting_enabled is not None:
        _runtime_looting_enabled = bool(looting_enabled)

    if botting_tree is None:
        return

    botting_tree.Config.ConfigureUpkeep(
        looting_enabled=_runtime_looting_enabled,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=(
            _enabled_consumable_upkeeps()
            if _runtime_consumables_enabled
            else ()
        ),
        heroai_state_logging=False,
    )


def _runtime_consumable_upkeep_node(enabled: bool) -> BehaviorTree:
    """Enable or suspend conset and pcon upkeep at runtime."""

    def _apply(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if botting_tree is None:
            return BehaviorTree.NodeState.FAILURE

        if _runtime_consumables_enabled != bool(enabled):
            _configure_runtime_upkeeps(consumables_enabled=enabled)
            PySystem.Console.Log(MODULE_NAME, 'Consumable upkeep resumed for the dungeon run.' if enabled else 'Consumable upkeep suspended during the end-of-dungeon return sequence.', PySystem.Console.MessageType.Info)

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name='Resume Consumable Upkeep' if enabled else 'Suspend Consumable Upkeep', action_fn=_apply, aftercast_ms=0))



def _draw_run_config() -> None:
    import PyImGui

    global _use_hard_mode
    global _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons
    global _use_summoning_stone
    global _keep_torch_for_caster, _drop_torch_for_combat
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots
    global _inventory_min_id_kits
    global _inventory_min_salvage_kits

    _load_settings()

    PyImGui.text("Shards of Orr Run Config")
    PyImGui.separator()

    changed = False
    upkeep_changed = False

    value = PyImGui.checkbox('Hard Mode (HM)', _use_hard_mode)
    if value != _use_hard_mode:
        _use_hard_mode = value
        changed = True

    PyImGui.separator()
    PyImGui.text("Conset")

    value = PyImGui.checkbox('Restock conset from storage', _restock_conset)
    if value != _restock_conset:
        _restock_conset = value
        changed = True

    value = PyImGui.checkbox('Activate / maintain conset', _activate_conset)
    if value != _activate_conset:
        _activate_conset = value
        changed = True
        upkeep_changed = True

    PyImGui.separator()
    PyImGui.text("Personal consumables")

    value = PyImGui.checkbox('Restock pcons from storage', _restock_pcons)
    if value != _restock_pcons:
        _restock_pcons = value
        changed = True

    value = PyImGui.checkbox('Activate / maintain pcons', _activate_pcons)
    if value != _activate_pcons:
        _activate_pcons = value
        changed = True
        upkeep_changed = True

    PyImGui.separator()
    PyImGui.text("Summoning stones")

    value = PyImGui.checkbox('Use summoning stones', _use_summoning_stone)
    if value != _use_summoning_stone:
        _use_summoning_stone = value
        changed = True
        upkeep_changed = True

    PyImGui.separator()
    PyImGui.text("Torch handling")

    value = PyImGui.checkbox('Keep torch for caster builds', _keep_torch_for_caster)
    if value != _keep_torch_for_caster:
        _keep_torch_for_caster = value
        _drop_torch_for_combat = None
        changed = True

    PyImGui.separator()
    PyImGui.text("Inventory maintenance")

    value = PyImGui.checkbox('Run MerchantRules when inventory is low', _inventory_maintenance_enabled)
    if value != _inventory_maintenance_enabled:
        _inventory_maintenance_enabled = value
        changed = True

    if _inventory_maintenance_enabled:
        value = PyImGui.input_int('Minimum free slots', _inventory_min_free_slots)
        value = max(0, int(value))
        if value != _inventory_min_free_slots:
            _inventory_min_free_slots = value
            changed = True

        value = PyImGui.input_int('Minimum ID kits (0 = disabled)', _inventory_min_id_kits)
        value = max(0, int(value))
        if value != _inventory_min_id_kits:
            _inventory_min_id_kits = value
            changed = True

        value = PyImGui.input_int('Minimum salvage kits (0 = disabled)', _inventory_min_salvage_kits)
        value = max(0, int(value))
        if value != _inventory_min_salvage_kits:
            _inventory_min_salvage_kits = value
            changed = True

        PyImGui.text_wrapped("MerchantRules executes the currently loaded Shards of Orr profile from SharedProfiles.json. If any active account falls below a configured threshold, all active accounts are processed together. Inventory space, ID kits and Expert Salvage Kits are queried locally on every active client, so each account uses its own real bag capacity. Equipment Pack is excluded.")

    if changed:
        _save_settings()

    if upkeep_changed:
        _configure_runtime_upkeeps()


def _runtime_difficulty_node() -> BehaviorTree:
    return BT.Subtree(name='Apply Selected Difficulty', subtree_fn=lambda _node: BT.SetHardMode(_use_hard_mode, log=True))


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
            return BT.Succeeder('RestockDisabled')

        return BT.RestockItemsFromList(tuple(items), allow_missing=True)

    return BT.Subtree(name='Restock Selected Consumables', subtree_fn=_build)


# endregion


# region Statistics


def _account_key(email: str) -> str:
    return str(email).replace("@", "_at_").replace(".", "_")


def _display_email(key: str) -> str:
    return str(key).replace("_at_", "@").replace("_", ".")


def _known_account_keys() -> list[str]:
    return sorted(
        key
        for key in (set(_bds_drops) | set(_gb_drops) | set(_session_bds) | set(_session_gb))
        if key and key != "local"
    )


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


def _inventory_accounts() -> list[object]:
    """Return the active accounts targeted by shared BT commands.

    Unlike the statistics view, inventory maintenance respects BottingTree
    account isolation so unrelated active clients are never moved or checked.
    """
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
    character_name = str(getattr(agent_data, 'CharacterName', '') or '').strip()
    if character_name:
        return character_name
    return str(getattr(account, "AccountEmail", "") or "Unknown account")


def _shared_account_map_id(account: object) -> int:
    agent_data = getattr(account, "AgentData", None)
    map_data = getattr(agent_data, "Map", None)
    return int(getattr(map_data, "MapID", 0) or 0)


def _shared_account_map_instance(account: object) -> tuple[int, int, int, int]:
    agent_data = getattr(account, "AgentData", None)
    map_data = getattr(agent_data, "Map", None)
    return (int(getattr(map_data, 'MapID', 0) or 0), int(getattr(map_data, 'Region', 0) or 0), int(getattr(map_data, 'District', 0) or 0), int(getattr(map_data, 'Language', 0) or 0))


def _iter_shared_inventory_slots(account: object):
    """Yield mirrored slots only for diagnostic item listing.

    Threshold decisions do NOT use this SharedMemory snapshot. Capacity and
    free-slot counts are queried locally on each client through InventoryQuery.
    """
    inventory_bags = getattr(account, "InventoryBags", None)
    if inventory_bags is None:
        return

    for bag in inventory_bags.iter_bags():
        bag_id = int(getattr(bag, "BagID", 0) or 0)
        if bag_id not in INVENTORY_BAG_IDS:
            continue
        for slot in bag.Slots:
            yield bag_id, slot


def _local_inventory_state() -> tuple[int, int, int, int]:
    occupied, capacity = Inventory.GetInventorySpace()
    id_kits = sum(
        int(GLOBAL_CACHE.Inventory.GetModelCount(model_id))
        for model_id in ID_KIT_MODEL_IDS
    )
    salvage_kits = sum(
        int(GLOBAL_CACHE.Inventory.GetModelCount(model_id))
        for model_id in SALVAGE_KIT_MODEL_IDS
    )
    return int(occupied), int(capacity), int(id_kits), int(salvage_kits)


def _inventory_target_accounts() -> list[tuple[str, str]]:
    """Return every active account as (email, display label), including self."""
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()

    for account in _inventory_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        targets.append((email, _shared_account_label(account)))

    local_email = str(Player.GetAccountEmail() or "").strip()
    if local_email and local_email not in seen:
        local_name = str(Player.GetName() or "").strip()
        targets.append((local_email, local_name or local_email))

    return targets


def _build_inventory_status(
    email: str,
    label: str,
    state: tuple[int, int, int, int] | None,
) -> dict[str, object]:
    if state is None:
        occupied = capacity = id_kits = salvage_kits = -1
    else:
        occupied, capacity, id_kits, salvage_kits = (int(value) for value in state)

    available = capacity > 0 and occupied >= 0 and occupied <= capacity
    free_slots = max(0, capacity - occupied) if available else 0

    return {
        "email": str(email),
        "label": str(label),
        "available": available,
        "capacity": capacity,
        "occupied": occupied,
        "free_slots": free_slots,
        "id_kits": id_kits,
        "salvage_kits": salvage_kits,
    }


def _inventory_account_statuses() -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []

    for raw_status in _inventory_status_snapshot.values():
        status = dict(raw_status)
        account_issues: list[str] = []

        if not bool(status.get("available", False)):
            account_issues.append("inventory query unavailable")
        else:
            free_slots = int(status.get("free_slots", 0) or 0)
            id_kits = int(status.get("id_kits", 0) or 0)
            salvage_kits = int(status.get("salvage_kits", 0) or 0)

            if _inventory_min_free_slots > 0 and free_slots < _inventory_min_free_slots:
                account_issues.append(f"free slots {free_slots}/{_inventory_min_free_slots}")
            if _inventory_min_id_kits > 0 and id_kits < _inventory_min_id_kits:
                account_issues.append(f"ID kits {id_kits}/{_inventory_min_id_kits}")
            if _inventory_min_salvage_kits > 0 and salvage_kits < _inventory_min_salvage_kits:
                account_issues.append(f"salvage kits {salvage_kits}/{_inventory_min_salvage_kits}")

        status["issues"] = account_issues
        statuses.append(status)

    return statuses


def _inventory_maintenance_issues() -> list[str]:
    statuses = _inventory_account_statuses()
    if not statuses:
        return ["No active account inventory query result is available."]

    return [
        f"{status['label']}: {', '.join(status['issues'])}"
        for status in statuses
        if status["issues"]
    ]


def _log_inventory_statuses(statuses: list[dict[str, object]]) -> None:
    if not statuses:
        PySystem.Console.Log(
            MODULE_NAME,
            "[Inventory] No active account inventory query result is available.",
            PySystem.Console.MessageType.Warning,
        )
        return

    for status in statuses:
        issues = list(status["issues"])
        result = "MAINTENANCE" if issues else "OK"
        if bool(status.get("available", False)):
            message = (
                f"[Inventory] {status['label']}: free={status['free_slots']}/{status['capacity']}, "
                f"occupied={status['occupied']}, ID kits={status['id_kits']}, "
                f"Expert salvage kits={status['salvage_kits']} -> {result}"
            )
        else:
            message = f"[Inventory] {status['label']}: local inventory query unavailable -> {result}"

        PySystem.Console.Log(
            MODULE_NAME,
            message,
            PySystem.Console.MessageType.Warning if issues else PySystem.Console.MessageType.Info,
        )


def _query_all_inventory_states_node(
    name: str,
    *,
    timeout_ms: int=_INVENTORY_QUERY_TIMEOUT_MS,
) -> BehaviorTree:
    """Query real inventory state locally on every active Guild Wars client."""
    state: dict[str, object] = {
        "started": False,
        "request_id": "",
        "sender_email": "",
        "pending": {},
        "results": {},
        "started_at": 0.0,
    }

    def _reset() -> None:
        state["started"] = False
        state["request_id"] = ""
        state["sender_email"] = ""
        state["pending"] = {}
        state["results"] = {}
        state["started_at"] = 0.0

    def _finish() -> BehaviorTree.NodeState:
        global _inventory_status_snapshot
        _inventory_status_snapshot = dict(state["results"])
        _reset()
        return BehaviorTree.NodeState.SUCCESS

    def _start() -> None:
        request_id = f"soo_inventory_state_{int(time.monotonic() * 1000)}"
        sender_email = str(Player.GetAccountEmail() or "").strip()
        targets = _inventory_target_accounts()

        results: dict[str, dict[str, object]] = {}
        pending: dict[str, str] = {}

        for email, label in targets:
            if email == sender_email:
                try:
                    local_state = _local_inventory_state()
                except Exception as exc:
                    PySystem.Console.Log(
                        MODULE_NAME,
                        f"[Inventory] Local inventory query failed on {label}: {exc}",
                        PySystem.Console.MessageType.Error,
                    )
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
                    float(ID_KIT_MODEL_IDS[0] if len(ID_KIT_MODEL_IDS) > 0 else 0),
                    float(ID_KIT_MODEL_IDS[1] if len(ID_KIT_MODEL_IDS) > 1 else 0),
                    float(SALVAGE_KIT_MODEL_IDS[0] if SALVAGE_KIT_MODEL_IDS else 0),
                    0.0,
                ),
                ("report_inventory_state", request_id, "", ""),
            )
            pending[email] = label

        state["started"] = True
        state["request_id"] = request_id
        state["sender_email"] = sender_email
        state["pending"] = pending
        state["results"] = results
        state["started_at"] = time.monotonic()

        PySystem.Console.Log(
            MODULE_NAME,
            f"[Inventory] Requested real inventory state from {len(targets)} active account(s).",
            PySystem.Console.MessageType.Info,
        )

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
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

            elapsed_ms = int(
                (time.monotonic() - float(state["started_at"])) * 1000.0
            )
            if elapsed_ms < max(0, int(timeout_ms)):
                return BehaviorTree.NodeState.RUNNING

            for email, label in list(pending.items()):
                state["results"][email] = _build_inventory_status(email, label, None)
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[Inventory] Real inventory query timed out for {label}.",
                    PySystem.Console.MessageType.Warning,
                )
            pending.clear()
            return _finish()

        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Inventory] Multibox inventory-state query failed: {exc}",
                PySystem.Console.MessageType.Error,
            )
            return _finish()

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_tick,
            aftercast_ms=_INVENTORY_QUERY_POLL_MS,
        )
    )


def _inventory_recipient_emails() -> list[str]:
    """Return every currently active account that must receive maintenance."""
    return [email for email, _label in _inventory_target_accounts()]


def _inventory_maintenance_trigger_node() -> BehaviorTree:
    def _log(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        statuses = _inventory_account_statuses()
        trigger_labels = [str(status["label"]) for status in statuses if status["issues"]]
        recipients = _inventory_recipient_emails()
        trigger_text = ", ".join(trigger_labels) if trigger_labels else "inventory verification"
        recipient_text = ", ".join(
            str(status["label"])
            for status in statuses
            if str(status["email"]) in recipients
        )
        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"[Inventory] Maintenance triggered by: {trigger_text}. "
                f"MerchantRules will run on ALL {len(recipients)} active account(s)"
                + (f": {recipient_text}." if recipient_text else ".")
            ),
            PySystem.Console.MessageType.Warning,
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Log Collective Inventory Maintenance Trigger",
            action_fn=_log,
            aftercast_ms=0,
        )
    )



def _inventory_model_label(model_id: int) -> str:
    try:
        return str(ModelID(int(model_id)).name)
    except Exception:
        return f"model_{int(model_id)}"


def _log_unhealthy_inventory_contents() -> None:
    """Log mirrored item contents for accounts that still fail local-query thresholds."""
    status_by_email = {
        str(status["email"]): status
        for status in _inventory_account_statuses()
        if status["issues"]
    }

    for account in _inventory_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        status = status_by_email.get(email)
        if status is None:
            continue

        label = str(status["label"])
        entries: list[str] = []
        for bag_id, slot in _iter_shared_inventory_slots(account):
            model_id = int(getattr(slot, "ModelID", 0) or 0)
            quantity = int(getattr(slot, "Quantity", 0) or 0)
            if model_id <= 0 or quantity <= 0:
                continue
            slot_no = int(getattr(slot, "Slot", 0) or 0)
            entries.append(
                f"B{bag_id}:S{slot_no} {_inventory_model_label(model_id)}({model_id}) x{quantity}"
            )

        if bool(status.get("available", False)):
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f"[Inventory diagnostic] {label}: "
                    f"free={status['free_slots']}/{status['capacity']}, "
                    f"ID kits={status['id_kits']}, "
                    f"Expert salvage kits={status['salvage_kits']}, "
                    f"mirrored occupied items={len(entries)}."
                ),
                PySystem.Console.MessageType.Warning,
            )
        else:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Inventory diagnostic] {label}: local inventory query unavailable; mirrored occupied items={len(entries)}.",
                PySystem.Console.MessageType.Warning,
            )

        chunk_size = 8
        for start_index in range(0, len(entries), chunk_size):
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Inventory diagnostic] {label}: "
                + " | ".join(entries[start_index:start_index + chunk_size]),
                PySystem.Console.MessageType.Info,
            )



def _inventory_is_healthy_node(name: str, *, log_success: bool=True) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        statuses = _inventory_account_statuses()
        _log_inventory_statuses(statuses)

        if not statuses:
            PySystem.Console.Log(MODULE_NAME, "Inventory maintenance required - no active account inventory snapshot is available.", PySystem.Console.MessageType.Warning)
            return BehaviorTree.NodeState.FAILURE

        issues = [
            f"{status['label']}: {', '.join(status['issues'])}"
            for status in statuses
            if status["issues"]
        ]
        if issues:
            PySystem.Console.Log(MODULE_NAME, "Inventory maintenance required - " + "; ".join(issues), PySystem.Console.MessageType.Warning)
            return BehaviorTree.NodeState.FAILURE

        if log_success:
            PySystem.Console.Log(MODULE_NAME, "Inventory check passed on every active account.", PySystem.Console.MessageType.Success)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ConditionNode(name=name, condition_fn=_check))



def _all_accounts_on_map(map_id: int) -> bool:
    accounts = _inventory_accounts()
    return bool(accounts) and all((_shared_account_map_id(account) == int(map_id) for account in accounts))


def _all_accounts_on_map_instance(map_id: int, region: int, district: int, language: int) -> bool:
    expected = (int(map_id), int(region), int(district), int(language))
    accounts = _inventory_accounts()
    return bool(accounts) and all((_shared_account_map_instance(account) == expected for account in accounts))


def _all_accounts_on_map_node(map_id: int, name: str) -> BehaviorTree:
    return BehaviorTree(BehaviorTree.ConditionNode(name=name, condition_fn=lambda _node: _all_accounts_on_map(map_id)))


def _wait_for_all_accounts_on_map(map_id: int, *, name: str, timeout_ms: int=INVENTORY_TRAVEL_TIMEOUT_MS) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _all_accounts_on_map(map_id):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.WaitUntilNode(name=name, condition_fn=_check, throttle_interval_ms=500, timeout_ms=timeout_ms))


def _wait_for_all_accounts_on_inventory_instance(map_id: int, *, name: str, timeout_ms: int=INVENTORY_TRAVEL_TIMEOUT_MS) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _all_accounts_on_map_instance(map_id, INVENTORY_TRAVEL_REGION, INVENTORY_TRAVEL_DISTRICT, INVENTORY_TRAVEL_LANGUAGE):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.WaitUntilNode(name=name, condition_fn=_check, throttle_interval_ms=500, timeout_ms=timeout_ms))


def _send_widget_state(widget_name: str, *, enabled: bool, refs_key: str) -> BehaviorTree:
    return BTShared.SendAndWait(command=SharedCommandType.EnableWidget if enabled else SharedCommandType.DisableWidget, extra_data=(widget_name, '', '', ''), include_self=True, refs_blackboard_key=refs_key, timeout_ms=20000, poll_interval_ms=100, log=True)


def _set_local_auto_inventory_handler(enabled: bool) -> BehaviorTree:
    def _set(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if botting_tree is None:
            return BehaviorTree.NodeState.SUCCESS

        fn = getattr(botting_tree, "SetAutoInventoryHandlerEnabled", None)
        if fn is None:
            return BehaviorTree.NodeState.SUCCESS

        try:
            fn(enabled)
        except Exception:
            return BehaviorTree.NodeState.SUCCESS

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name='Enable Local Auto Inventory Handler' if enabled else 'Disable Local Auto Inventory Handler', action_fn=_set, aftercast_ms=0))


def _travel_all_accounts_to_vlox(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(
        name="Travel Every Account To Vlox's Falls",
        children=[
            BTShared.SendAndWait(command=SharedCommandType.TravelToMap, params=(float(VLOXS_FALL), float(INVENTORY_TRAVEL_REGION), float(INVENTORY_TRAVEL_DISTRICT), float(INVENTORY_TRAVEL_LANGUAGE)), include_self=True, refs_blackboard_key=f'{attempt_key}_travel_vlox_refs', timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS, poll_interval_ms=250, log=True),
            _wait_for_all_accounts_on_inventory_instance(VLOXS_FALL, name="Wait For Every Account In Vlox's Falls EU-English-1"),
        ],
    )


def _return_all_accounts_to_vlox(attempt_key: str) -> BehaviorTree:
    currently_in_an_explorable = BT.Selector(
        name="Current Map Can Be Resigned",
        children=[
            BT.IsCurrentMap(map_id=ARBOR_BAY, log=False),
            BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=False),
            BT.IsCurrentMap(map_id=SOO_LEVEL_2, log=False),
            BT.IsCurrentMap(map_id=SOO_LEVEL_3, log=False),
        ],
    )

    resign_from_explorable = BT.Sequence(
        name="Resign Party To Vlox's Falls",
        children=[
            currently_in_an_explorable,
            BT.Resign(wait_for_map_load=True, target_map_id=VLOXS_FALL, multi_account=True, timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS, log=True),
            _wait_for_all_accounts_on_map(VLOXS_FALL, name="Wait For Party Return To Vlox's Falls"),
        ],
    )

    return BT.Selector(name="Ensure Every Account Is In Vlox's Falls", children=[_all_accounts_on_map_node(VLOXS_FALL, "Every Account Already In Vlox's Falls"), resign_from_explorable, _travel_all_accounts_to_vlox(attempt_key)])


def _restore_inventoryplus_after_merchant(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(name='Restore InventoryPlus After MerchantRules', children=[_send_widget_state(INVENTORY_PLUS_WIDGET_NAME, enabled=True, refs_key=f'{attempt_key}_enable_inventoryplus_refs'), _set_local_auto_inventory_handler(True)])


def _run_merchant_rules(attempt_key: str) -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        recipients = _inventory_recipient_emails()
        if not recipients:
            PySystem.Console.Log(MODULE_NAME, "[Inventory] MerchantRules aborted: no active account recipients.", PySystem.Console.MessageType.Error)
            return BehaviorTree(BehaviorTree.FailerNode(name="No Active MerchantRules Recipients"))

        request_id = f"soo_inventory_{attempt_key}_{int(time.monotonic() * 1000)}"
        PySystem.Console.Log(
            MODULE_NAME,
            f"[Inventory] Dispatching MerchantRules to all {len(recipients)} active account(s).",
            PySystem.Console.MessageType.Info,
        )
        execute = BTShared.SendAndWait(
            command=SharedCommandType.MerchantRules,
            params=(3.0, 0.0, 0.0, 0.0),
            extra_data=(request_id, "", "0", "0"),
            recipients=recipients,
            include_self=True,
            refs_blackboard_key=f"{attempt_key}_merchant_rules_refs",
            timeout_ms=INVENTORY_MERCHANT_TIMEOUT_MS,
            poll_interval_ms=250,
            log=True,
        )

        return BT.Selector(
            name="Execute MerchantRules And Restore InventoryPlus",
            children=[
                BT.Sequence(name="MerchantRules Completed", children=[execute, _restore_inventoryplus_after_merchant(attempt_key)]),
                BT.Sequence(name="Restore InventoryPlus After MerchantRules Failure", children=[_restore_inventoryplus_after_merchant(f"{attempt_key}_failure"), BehaviorTree(BehaviorTree.FailerNode(name="Propagate MerchantRules Failure"))]),
            ],
        )

    return BT.Subtree(name="Run MerchantRules On All Active Accounts", subtree_fn=_build)



def _inventory_maintenance_attempt(attempt_number: int) -> BehaviorTree:
    """Run one MerchantRules attempt while staying in Vlox's Falls.

    InventoryCheckAndMaintenance() ensures every active account is in Vlox's
    Falls before the first attempt. If the first attempt leaves the inventory
    below threshold, the retry runs immediately in the same outpost.
    """
    attempt_key = f"inventory_attempt_{attempt_number}"
    return BT.Sequence(
        name=f"Inventory Maintenance Attempt {attempt_number}",
        children=[
            BT.LogMessage(message=f"Inventory maintenance attempt {attempt_number}/{INVENTORY_MAINTENANCE_RETRY_COUNT} in Vlox's Falls.", module_name=MODULE_NAME),
            _set_local_auto_inventory_handler(False),
            _send_widget_state(INVENTORY_PLUS_WIDGET_NAME, enabled=False, refs_key=f'{attempt_key}_disable_inventoryplus_refs'),
            _send_widget_state(MERCHANT_RULES_WIDGET_NAME, enabled=True, refs_key=f'{attempt_key}_enable_merchant_rules_refs'),
            BT.Wait(1_000),
            _run_merchant_rules(attempt_key),
            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
            _query_all_inventory_states_node(name=f"Refresh Real Inventories After Attempt {attempt_number}"),
            _inventory_is_healthy_node(f'Verify Inventory After Attempt {attempt_number}', log_success=True),
        ],
    )


def _stop_for_inventory_failure_node() -> BehaviorTree:
    stopped = False

    def _stop(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal stopped
        if not stopped:
            stopped = True
            issues = _inventory_maintenance_issues()
            issue_text = "; ".join(issues) if issues else "unknown verification error"
            PySystem.Console.Log(MODULE_NAME, f'Inventory maintenance failed twice. The bot was paused safely. Remaining issue(s): {issue_text}', PySystem.Console.MessageType.Error)
            _log_unhealthy_inventory_contents()

            if botting_tree is not None:
                fn = getattr(botting_tree, "SetAutoInventoryHandlerEnabled", None)
                if callable(fn):
                    try:
                        fn(True)
                    except Exception:
                        pass

            sender_email = str(Player.GetAccountEmail() or "").strip()
            for account in _inventory_accounts():
                receiver_email = str(getattr(account, 'AccountEmail', '') or '').strip()
                if not sender_email or not receiver_email:
                    continue
                GLOBAL_CACHE.ShMem.SendMessage(sender_email, receiver_email, SharedCommandType.EnableWidget, (0.0, 0.0, 0.0, 0.0), (INVENTORY_PLUS_WIDGET_NAME, '', '', ''))

            if botting_tree is not None:
                fn = getattr(botting_tree, "Pause", None)
                if callable(fn):
                    try:
                        fn(True)
                    except Exception:
                        pass

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name='Pause Bot After Inventory Maintenance Failure', action_fn=_stop, aftercast_ms=0))


def InventoryCheckAndMaintenance() -> BehaviorTree:
    disabled = BehaviorTree(BehaviorTree.ConditionNode(name='Inventory Maintenance Disabled', condition_fn=lambda _node: not _inventory_maintenance_enabled))

    maintenance_attempts = [_inventory_maintenance_attempt(attempt_number) for attempt_number in range(1, INVENTORY_MAINTENANCE_RETRY_COUNT + 1)]
    maintenance_attempts.append(_stop_for_inventory_failure_node())

    enabled_flow = BT.Sequence(
        name="Enabled Inventory Check And Maintenance",
        children=[
            _query_all_inventory_states_node(name='Query Real Inventory State On Every Active Account'),
            BT.Selector(
                name="Check Inventory Thresholds",
                children=[
                    _inventory_is_healthy_node('Inventory Thresholds Already Satisfied', log_success=True),
                    BT.Sequence(
                        name="Run Inventory Maintenance",
                        children=[
                            _inventory_maintenance_trigger_node(),
                            _return_all_accounts_to_vlox("inventory_maintenance_setup"),
                            BT.LeaveParty(),
                            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
                            BT.Selector(name="Retry Inventory Maintenance In Vlox's Falls", children=maintenance_attempts),
                        ],
                    ),
                ],
            ),
        ],
    )

    return BT.Selector(name='Inventory Check And Maintenance', children=[disabled, enabled_flow])


def StartupInventoryCheck() -> BehaviorTree:
    return BT.Selector(
        name="Startup Inventory Check",
        children=[
            BT.Sequence(name="Check Inventories Before Leaving Vlox's Falls", children=[BT.IsCurrentMap(map_id=VLOXS_FALL, log=False), InventoryCheckAndMaintenance()]),
            BT.Succeeder("Skip Startup Inventory Check Outside Vlox's Falls"),
        ],
    )


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
        character_name = str(getattr(agent_data, 'CharacterName', '') or '').strip()
        if not email or not character_name:
            continue

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
            PySystem.Console.Log(MODULE_NAME, f'[Statistics] {name} failed: {exc}', PySystem.Console.MessageType.Warning)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name=name, action_fn=_run, aftercast_ms=0))


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

    return _statistics_action_node('Mark Run Start', _mark)


def _mark_l2_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_l2_start, _current_l1_time

        now = time.monotonic()
        _t_l2_start = now
        _current_l1_time = now - _t_run_start if _t_run_start > 0.0 else 0.0

    return _statistics_action_node('Mark Level 2 Start', _mark)


def _mark_l3_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _t_l3_start, _current_l2_time

        now = time.monotonic()
        _t_l3_start = now
        _current_l2_time = now - _t_l2_start if _t_l2_start > 0.0 else 0.0

    return _statistics_action_node('Mark Level 3 Start', _mark)


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
        timings_valid = _t_run_start > 0.0 and _t_l2_start > _t_run_start and (_t_l3_start > _t_l2_start)

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

            PySystem.Console.Log(MODULE_NAME, f'[Statistics] Run complete - Total {run_time:.0f}s | L1 {l1_time:.0f}s | L2 {l2_time:.0f}s | L3 {l3_time:.0f}s', PySystem.Console.MessageType.Success)

        _total_runs += 1
        _session_runs += 1
        _t_run_start = 0.0
        _t_l2_start = 0.0
        _t_l3_start = 0.0
        _save_statistics()

    return _statistics_action_node('Record Successful Run', _record)


def _accumulate_drop(account_key: str, count: int, all_time: dict[str, int], session: dict[str, int]) -> None:
    all_time.setdefault(account_key, 0)
    if count <= 0:
        return
    all_time[account_key] += int(count)
    session[account_key] = session.get(account_key, 0) + int(count)


def _inventory_count(model_id_min: int, model_id_max: int) -> int:
    return sum((int(GLOBAL_CACHE.Inventory.GetModelCount(model_id)) for model_id in range(int(model_id_min), int(model_id_max) + 1)))


def _inventory_statistics_node(*, after_chest: bool) -> BehaviorTree:
    node_name = 'Record Drops After Final Chest' if after_chest else 'Snapshot Inventories At Dungeon Entry'
    state: dict[str, object] = {'started': False, 'local_email': '', 'account_keys': [], 'requests': [], 'request_index': 0, 'waiting': False, 'request_started_at': 0.0, 'local_email_wait_started_at': 0.0}

    def _reset() -> None:
        state["started"] = False
        state["local_email"] = ""
        state["account_keys"] = []
        state["requests"] = []
        state["request_index"] = 0
        state["waiting"] = False
        state["request_started_at"] = 0.0
        state["local_email_wait_started_at"] = 0.0

    def _start() -> bool:
        _load_statistics()
        _refresh_character_names()

        local_email = str(Player.GetAccountEmail() or "").strip()
        if not local_email:
            return False

        local_key = _account_key(local_email)
        bds_section = _BDS_RUN_SECTION if after_chest else _BDS_SNAPSHOT_SECTION
        gb_section = _GB_RUN_SECTION if after_chest else _GB_SNAPSHOT_SECTION

        bds_count = _inventory_count(BDS_MODEL_ID_MIN, BDS_MODEL_ID_MAX)
        gb_count = _inventory_count(GB_MODEL_ID, GB_MODEL_ID)
        _settings_ini.set(bds_section, local_key, bds_count)
        _settings_ini.set(gb_section, local_key, gb_count)

        account_keys = [local_key]
        requests: list[dict[str, object]] = []
        for account in _shared_accounts():
            email = str(getattr(account, 'AccountEmail', '') or '').strip()
            if not email or email == local_email:
                continue

            key = _account_key(email)
            if key not in account_keys:
                account_keys.append(key)

            requests.extend(
                [
                    {
                        "email": email,
                        "key": key,
                        "model_min": BDS_MODEL_ID_MIN,
                        "model_max": BDS_MODEL_ID_MAX,
                        "section": bds_section,
                        "label": "BDS",
                    },
                    {
                        "email": email,
                        "key": key,
                        "model_min": GB_MODEL_ID,
                        "model_max": GB_MODEL_ID,
                        "section": gb_section,
                        "label": "Glacial Blades",
                    },
                ]
            )

        for key in account_keys:
            _bds_drops.setdefault(key, 0)
            _gb_drops.setdefault(key, 0)

        state["started"] = True
        state["local_email"] = local_email
        state["account_keys"] = account_keys
        state["requests"] = requests
        state["local_email_wait_started_at"] = 0.0
        return True

    def _finish() -> None:
        if not after_chest:
            PySystem.Console.Log(MODULE_NAME, f"[Statistics] Dungeon-entry inventory snapshot completed for {len(state['account_keys'])} account(s).", PySystem.Console.MessageType.Info)
            _save_statistics()
            return

        total_bds = 0
        total_gb = 0
        for key in state["account_keys"]:
            account_key = str(key)
            bds_before = _settings_ini.get_int(_BDS_SNAPSHOT_SECTION, account_key, -1)
            bds_after = _settings_ini.get_int(_BDS_RUN_SECTION, account_key, -1)
            bds_delta = max(0, bds_after - bds_before) if bds_before >= 0 and bds_after >= 0 else 0
            _accumulate_drop(account_key, bds_delta, _bds_drops, _session_bds)
            total_bds += bds_delta

            gb_before = _settings_ini.get_int(_GB_SNAPSHOT_SECTION, account_key, -1)
            gb_after = _settings_ini.get_int(_GB_RUN_SECTION, account_key, -1)
            gb_delta = max(0, gb_after - gb_before) if gb_before >= 0 and gb_after >= 0 else 0
            _accumulate_drop(account_key, gb_delta, _gb_drops, _session_gb)
            total_gb += gb_delta

        _save_statistics()
        PySystem.Console.Log(MODULE_NAME, f'[Statistics] Final chest recorded - BDS {total_bds} | Glacial Blades {total_gb}', PySystem.Console.MessageType.Success)

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if bool(
                node.blackboard.get(
                    "USER_INTERRUPT_ACTIVE",
                    False,
                )
            ):
                _reset()
                return BehaviorTree.NodeState.FAILURE

            if not bool(state["started"]):
                if not _start():
                    now = time.monotonic()
                    wait_started = float(state["local_email_wait_started_at"] or 0.0)
                    if wait_started <= 0.0:
                        state["local_email_wait_started_at"] = now
                        return BehaviorTree.NodeState.RUNNING

                    elapsed_ms = (now - wait_started) * 1000.0
                    if elapsed_ms < _INVENTORY_QUERY_TIMEOUT_MS:
                        return BehaviorTree.NodeState.RUNNING

                    PySystem.Console.Log(
                        MODULE_NAME,
                        "[Statistics] Local account email was unavailable; skipping this statistics snapshot instead of creating a synthetic 'local' account.",
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
                    _settings_ini.set(str(request['section']), str(request['key']), -1)
                    GLOBAL_CACHE.ShMem.SendMessage(str(state['local_email']), email, SharedCommandType.InventoryQuery, (float(model_min), float(model_max), 0.0, 0.0), ('report_inventory_count',))
                    state["waiting"] = True
                    state["request_started_at"] = time.monotonic()
                    return BehaviorTree.NodeState.RUNNING

                count = int(get_inventory_count(email, model_min, model_max))
                if count >= 0:
                    _settings_ini.set(str(request['section']), str(request['key']), count)
                    state["request_index"] = request_index + 1
                    state["waiting"] = False
                    continue

                elapsed_ms = (time.monotonic() - float(state['request_started_at'])) * 1000.0
                if elapsed_ms >= _INVENTORY_QUERY_TIMEOUT_MS:
                    PySystem.Console.Log(MODULE_NAME, f"[Statistics] Inventory query timed out for {request['label']} on {_account_label(str(request['key']))}.", PySystem.Console.MessageType.Warning)
                    state["request_index"] = request_index + 1
                    state["waiting"] = False
                    continue

                return BehaviorTree.NodeState.RUNNING

            _finish()
            _reset()
            return BehaviorTree.NodeState.SUCCESS
        except Exception as exc:
            PySystem.Console.Log(MODULE_NAME, f'[Statistics] {node_name} failed: {exc}', PySystem.Console.MessageType.Warning)
            _reset()
            return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name=node_name, action_fn=_tick, aftercast_ms=_INVENTORY_QUERY_POLL_MS))



def _reset_total_overview_and_timings() -> None:
    """Reset persistent all-time overview/drop counters and timing statistics."""
    global _total_runs, _total_run_time, _fastest_run, _slowest_run
    global _l1_total_time, _l1_fastest, _l1_slowest
    global _l2_total_time, _l2_fastest, _l2_slowest
    global _l3_total_time, _l3_fastest, _l3_slowest
    global _current_run_time, _current_l1_time, _current_l2_time, _current_l3_time

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

    # Clear the last completed timing display as well. If a run is currently
    # active, its live timer still comes from the active monotonic timestamps.
    _current_run_time = 0.0
    _current_l1_time = 0.0
    _current_l2_time = 0.0
    _current_l3_time = 0.0

    # Total Overview uses the persistent BDS / Glacial Blades counters.
    # Write zeroes for every stored INI key so a script reload cannot restore
    # the previous values.
    bds_keys = set(_bds_drops) | set(_settings_ini.items(_BDS_DROPS_SECTION).keys())
    gb_keys = set(_gb_drops) | set(_settings_ini.items(_GB_DROPS_SECTION).keys())

    for key in bds_keys:
        _bds_drops[key] = 0
        _settings_ini.set(_BDS_DROPS_SECTION, key, 0)

    for key in gb_keys:
        _gb_drops[key] = 0
        _settings_ini.set(_GB_DROPS_SECTION, key, 0)

    _save_statistics()
    PySystem.Console.Log(
        MODULE_NAME,
        "[Statistics] Total Overview and Run Timings reset to zero.",
        PySystem.Console.MessageType.Success,
    )

def _draw_statistics() -> None:
    import PyImGui
    from Py4GWCoreLib import Color, ImGui

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
        return _fmt_time(total / _total_runs) if _total_runs > 0 else '--:--'

    def _drop_rate(runs: int, drops: int) -> str:
        return f"{drops / runs * 100.0:.1f}%" if runs > 0 and drops > 0 else "-"

    table_flags = PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg | PyImGui.TableFlags.SizingFixedFit | PyImGui.TableFlags.NoHostExtendX
    header_color = 26 | (38 << 8) | (51 << 16) | (255 << 24)
    column_width = 72.0
    row_height = 22.0

    def _header_row(labels: tuple[str, ...]) -> None:
        PyImGui.table_next_row(0, row_height)
        PyImGui.table_set_bg_color(2, header_color, -1)
        for index, label in enumerate(labels):
            PyImGui.table_set_column_index(index)
            PyImGui.text(label)

    PyImGui.text_colored("Shards of Orr Statistics", gold)
    PyImGui.separator()
    PyImGui.spacing()

    _scramble_accounts = PyImGui.checkbox('Hide Account Names', _scramble_accounts)

    session_bds = sum(_session_bds.values())
    session_gb = sum(_session_gb.values())
    total_bds = sum(_bds_drops.values())
    total_gb = sum(_gb_drops.values())

    PyImGui.text_colored("Session Overview", cyan)
    if PyImGui.begin_table("##soo_bt_session", 5, table_flags):
        for label in ("Runs", "BDS", "BDS Rate", "GB", "GB Rate"):
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
        _header_row(("Runs", "BDS", "BDS Rate", "GB", "GB Rate"))
        values = (_session_runs, session_bds, _drop_rate(_session_runs, session_bds), session_gb, _drop_rate(_session_runs, session_gb))
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Total Overview", cyan)
    if PyImGui.begin_table("##soo_bt_all_time", 5, table_flags):
        for label in ("Runs", "BDS", "BDS Rate", "GB", "GB Rate"):
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
        _header_row(("Runs", "BDS", "BDS Rate", "GB", "GB Rate"))
        values = (_total_runs, str(total_bds), _drop_rate(_total_runs, total_bds), str(total_gb), _drop_rate(_total_runs, total_gb))
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Run Timings", cyan)
    if PyImGui.begin_table("##soo_bt_timings", 5, table_flags):
        for label in ("Floor", "Current", "Avg", "Best", "Worst"):
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
        _header_row(("Floor", "Current", "Avg", "Best", "Worst"))

        now = time.monotonic()
        run_active = _t_run_start > 0.0
        l1_active = run_active and _t_l2_start <= 0.0
        l2_active = _t_l2_start > 0.0 and _t_l3_start <= 0.0
        l3_active = _t_l3_start > 0.0

        timing_rows = (('Overall', now - _t_run_start if run_active else _current_run_time, run_active, _total_run_time, _fastest_run, _slowest_run),
            ('Floor 1', now - _t_run_start if l1_active else _current_l1_time, l1_active, _l1_total_time, _l1_fastest, _l1_slowest),
            ('Floor 2', now - _t_l2_start if l2_active else _current_l2_time, l2_active, _l2_total_time, _l2_fastest, _l2_slowest),
            ('Floor 3', now - _t_l3_start if l3_active else _current_l3_time, l3_active, _l3_total_time, _l3_fastest, _l3_slowest), )

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

    def _draw_drop_table(table_id: str, title: str, session_values: dict[str, int], all_time_values: dict[str, int]) -> None:
        PyImGui.spacing()
        PyImGui.text_colored(title, cyan)
        if not PyImGui.begin_table(table_id, 4, table_flags):
            return

        PyImGui.table_setup_column('Account', PyImGui.TableColumnFlags.WidthStretch)
        for label in ("Session", "All Time", "Drop Rate"):
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
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

    _draw_drop_table(
        "##soo_bt_bds_drops",
        "BDS Drops",
        _session_bds,
        _bds_drops,
    )
    _draw_drop_table(
        "##soo_bt_gb_drops",
        "Glacial Blades Drops",
        _session_gb,
        _gb_drops,
    )


# endregion


# region Helpers

_MARTIAL_PRIMARY_PROFESSIONS = {'Warrior', 'Ranger', 'Assassin', 'Dervish', 'Paragon'}


def _is_holding_bundle() -> bool:
    try:
        return bool(Agent.IsHoldingItem(Player.GetAgentID()))
    except Exception:
        return False


def _resolve_torch_combat_policy() -> bool:
    """Return True when the leader must drop the torch before combat."""
    global _drop_torch_for_combat

    if _drop_torch_for_combat is not None:
        return _drop_torch_for_combat

    if not _keep_torch_for_caster:
        _drop_torch_for_combat = True
        reason = "caster torch retention is disabled in Config"
    else:
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
            _drop_torch_for_combat = True
            reason = f"martial weapon detected: {weapon_name}"
        elif is_caster:
            _drop_torch_for_combat = False
            reason = f"caster weapon detected: {weapon_name}"
        else:
            try:
                primary_profession, _ = Agent.GetProfessionNames(player_id)
            except Exception:
                primary_profession = ""

            if primary_profession in _MARTIAL_PRIMARY_PROFESSIONS:
                _drop_torch_for_combat = True
                reason = (
                    "weapon type unavailable; martial primary profession "
                    f"detected: {primary_profession}"
                )
            elif primary_profession:
                _drop_torch_for_combat = False
                reason = (
                    "weapon type unavailable; caster primary profession "
                    f"detected: {primary_profession}"
                )
            else:
                # Preserve the previous behavior when no reliable player data
                # is available instead of risking combat with a martial build
                # still carrying the bundle.
                _drop_torch_for_combat = True
                reason = "weapon and profession are unknown; safe fallback"

    PySystem.Console.Log(MODULE_NAME, f"Torch combat policy: {('DROP' if _drop_torch_for_combat else 'KEEP')} ({reason}).", PySystem.Console.MessageType.Info)
    return _drop_torch_for_combat


def ResolveTorchCombatPolicy() -> BehaviorTree:
    def _resolve() -> BehaviorTree.NodeState:
        _resolve_torch_combat_policy()
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name='ResolveTorchCombatPolicy', action_fn=_resolve, aftercast_ms=0))


def DropTorchForCombat(log: bool = False) -> BehaviorTree:
    """Drop the torch only when the configured combat policy requires it."""

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not _resolve_torch_combat_policy():
            return BT.Succeeder('KeepTorchForCasterCombat')

        if not _is_holding_bundle():
            return BT.Succeeder('NoTorchBundleToDrop')

        return BT.DropBundle(log=log)

    return BT.Subtree(name='Drop Torch For Combat If Required', subtree_fn=_build)


def ResetTorchCombatPolicy() -> BehaviorTree:
    def _reset() -> BehaviorTree.NodeState:
        global _drop_torch_for_combat
        _drop_torch_for_combat = None
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name='ResetTorchCombatPolicy', action_fn=_reset, aftercast_ms=0))


def PickupTorch() -> BehaviorTree:
    PICKUP_TIMEOUT_MS = 45_000
    NOT_FOUND_GRACE_MS = 3_000
    RETRY_DELAY_MS = 1_000

    def _create_pickup_tree() -> BehaviorTree:
        return BT.PickupGroundItemByModelID(model_ids=TORCH_MODEL_IDS, max_distance=200000.0, timeout_ms=PICKUP_TIMEOUT_MS, allow_unassigned=True, interaction_interval_ms=1000, aftercast_ms=100, log=False)

    pickup_tree = _create_pickup_tree()

    started_at = 0.0
    retry_at = 0.0
    search_logged = False
    torch_seen = False

    def _find_available_torch() -> int | None:
        """Return a pickup-compatible torch, or None if the scan failed."""
        try:
            local_player_id = int(Player.GetAgentID() or 0)

            for candidate in AgentArray.GetItemArray():
                agent_id = int(candidate or 0)
                if agent_id <= 0:
                    continue

                if not Agent.GetItemAgentByID(agent_id):
                    continue

                owner_id = int(Agent.GetItemAgentOwnerID(agent_id) or 0)
                if owner_id not in (0, local_player_id):
                    continue

                item_id = int(Agent.GetItemAgentItemID(agent_id) or 0)
                if item_id <= 0:
                    continue

                model_id = int(GLOBAL_CACHE.Item.GetModelID(item_id) or 0)
                if model_id in TORCH_MODEL_IDS:
                    return agent_id

            return 0
        except Exception:
            # Preserve the existing pickup behavior if the preliminary scan
            # itself is temporarily unavailable.
            return None

    def _log(message: str, message_type: PySystem.Console.MessageType) -> None:
        PySystem.Console.Log('PickupTorch', message, message_type)

    def _reset_state() -> None:
        nonlocal pickup_tree
        nonlocal started_at
        nonlocal retry_at
        nonlocal search_logged
        nonlocal torch_seen

        pickup_tree = _create_pickup_tree()
        started_at = 0.0
        retry_at = 0.0
        search_logged = False
        torch_seen = False

    def _pickup_torch_step(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal pickup_tree
        nonlocal started_at
        nonlocal retry_at
        nonlocal search_logged
        nonlocal torch_seen

        now = time.monotonic()

        # Intermediate pickup nodes remain in the route for recovery.  A
        # caster that kept the torch completes them immediately without
        # starting a search or producing a misleading lookup log.
        if _is_holding_bundle():
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        if started_at <= 0.0:
            started_at = now

        if not search_logged:
            _log('Looking for a torch...', PySystem.Console.MessageType.Info)
            search_logged = True

        elapsed_ms = int((now - started_at) * 1000.0)

        if not torch_seen:
            torch_agent_id = _find_available_torch()

            if torch_agent_id is None:
                # The preliminary scan failed. Let the established pickup
                # routine perform its own search rather than skipping.
                torch_seen = True
            elif torch_agent_id > 0:
                torch_seen = True
            elif elapsed_ms >= NOT_FOUND_GRACE_MS:
                _log('No torch found on the ground. Assuming this pickup was already completed before the planner resumed the step; skipping.', PySystem.Console.MessageType.Warning)
                _reset_state()
                return BehaviorTree.NodeState.SUCCESS
            else:
                return BehaviorTree.NodeState.RUNNING

        if elapsed_ms >= PICKUP_TIMEOUT_MS:
            _log('Failed to pick up a torch after 45s.', PySystem.Console.MessageType.Error)
            _reset_state()
            return BehaviorTree.NodeState.FAILURE

        if now < retry_at:
            return BehaviorTree.NodeState.RUNNING

        pickup_tree.blackboard = node.blackboard

        pickup_result = BehaviorTree.Node._normalize_state(pickup_tree.tick())

        if pickup_result == BehaviorTree.NodeState.RUNNING:
            return BehaviorTree.NodeState.RUNNING

        # Le node interne annonce SUCCESS, mais la torche
        # n'est réellement pas tenue par le personnage.
        if pickup_result == BehaviorTree.NodeState.SUCCESS:
            _log('Pickup not completed (no torch is held). Retrying...', PySystem.Console.MessageType.Warning)

            pickup_tree = _create_pickup_tree()
            pickup_tree.blackboard = node.blackboard
            retry_at = now + RETRY_DELAY_MS / 1000.0

            return BehaviorTree.NodeState.RUNNING

        pickup_tree = _create_pickup_tree()
        pickup_tree.blackboard = node.blackboard
        retry_at = now + RETRY_DELAY_MS / 1000.0

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name='PickupTorch', action_fn=_pickup_torch_step, aftercast_ms=0))

def UseAvailableSummoningStone() -> BehaviorTree:
    """
    Use the first available summoning stone once.

    Summoning stones are handled as one-shot consumables and are therefore
    kept outside the continuous consumable upkeep service.
    """
    if not _use_summoning_stone:
        return BT.Succeeder('SummoningStoneDisabled')

    return BT.Selector(name='Use Available Summoning Stone', children=[BTItems.UseConsumable(int(model_id)) for model_id in SUMMON_MODEL_IDS] + [BT.Succeeder('NoSummoningStoneAvailable')])


def BrazierSequence(name: str, points: list[tuple[float, float]]) -> BehaviorTree:
    """
    Activate a sequence of SoO braziers.

    The first brazier is activated normally because the torch flame effect is
    not available before that interaction. Every following movement continuously
    monitors the flame and returns to the previous brazier if it disappears.
    """
    if not points:
        return BT.Succeeder(f'{name}Empty')

    children: list[BehaviorTree | BehaviorTree.Node] = []

    first_x, first_y = points[0]

    children.append(
        BT.MoveAndInteractWithGadget(pos=Vec2f(float(first_x), float(first_y)), gadget_id=None, search_distance=300.0, interaction_distance=220.0, interaction_count=2, interaction_interval_ms=250, timeout_ms=15000, pause_on_combat=False, multi_account=False, include_self=True, log=True)
    )

    for index in range(
        1,
        len(points),
    ):
        previous_brazier = points[
            index - 1
        ]
        next_brazier = points[
            index
        ]

        children.append(
            MoveBetweenBraziersWithFlameRecovery(
            name=f"{name} {index}/{len(points) - 1}",
            previous_brazier=previous_brazier,
            next_brazier=next_brazier,
            effect_id=TORCH_BUFF_ID,
            interaction_distance=220.0,
            interaction_count=2,
            interaction_interval_ms=250,
            effect_apply_timeout_ms=3000,
            timeout_ms=90000,
            max_recoveries=5,
            log=True,)
        )

    return BT.Sequence(name=name, children=children)

def MoveBetweenBraziersWithFlameRecovery(
    name: str,
    previous_brazier: tuple[float, float],
    next_brazier: tuple[float, float],
    effect_id: int = TORCH_BUFF_ID,
    interaction_distance: float = 220.0,
    interaction_count: int = 2,
    interaction_interval_ms: int = 250,
    effect_apply_timeout_ms: int = 3_000,
    timeout_ms: int = 90_000,
    max_recoveries: int = 5,
    log: bool = True,
) -> BehaviorTree:
    """
    Move between two braziers while continuously monitoring the torch flame.

    If the flame disappears, movement fails, or interaction with the next
    brazier fails, the node returns to the previous brazier, relights the
    torch, and retries the movement to the next brazier.

    FAILURE is returned only when local recovery is exhausted, the return
    movement fails, the global timeout is reached, or a user interruption
    occurs.
    """
    import time

    from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE
    from Py4GWCoreLib.Player import Player

    previous_pos = Vec2f(float(previous_brazier[0]), float(previous_brazier[1]))

    next_pos = Vec2f(float(next_brazier[0]), float(next_brazier[1]))

    move_to_next = BT.Move(next_pos, tolerance=float(interaction_distance), pause_on_combat=False, ignore_destination_obstacles=True, log=False)

    move_to_previous = BT.Move(previous_pos, tolerance=float(interaction_distance), pause_on_combat=False, ignore_destination_obstacles=True, log=False)

    relight_previous = BT.MoveAndInteractWithGadget(pos=previous_pos, gadget_id=None, search_distance=300.0, interaction_distance=float(interaction_distance), interaction_count=max(1, int(interaction_count)), interaction_interval_ms=max(0, int(interaction_interval_ms)), timeout_ms=15000, pause_on_combat=False, multi_account=False, include_self=True, log=log)

    interact_next = BT.MoveAndInteractWithGadget(pos=next_pos, gadget_id=None, search_distance=300.0, interaction_distance=float(interaction_distance), interaction_count=max(1, int(interaction_count)), interaction_interval_ms=max(0, int(interaction_interval_ms)), timeout_ms=15000, pause_on_combat=False, multi_account=False, include_self=True, log=log)

    state = {'phase': 'move_to_next', 'started_at': 0.0, 'phase_started_at': 0.0, 'recovery_count': 0}

    def _trace(message: str, message_type=PySystem.Console.MessageType.Info) -> None:
        if not log:
            return

        PySystem.Console.Log(MODULE_NAME, f'[{name}] {message}', message_type)

    def _has_active_flame() -> bool:
        try:
            player_agent_id = Player.GetAgentID()

            if not player_agent_id:
                return False

            return bool(GLOBAL_CACHE.Effects.HasEffect(player_agent_id, int(effect_id)))
        except Exception:
            return False

    def _cancel_current_movement() -> None:
        try:
            player_x, player_y = Player.GetXY()

            Player.Move(float(player_x), float(player_y))
        except Exception:
            pass

    def _reset_tree(tree: BehaviorTree) -> None:
        try:
            tree.reset()
        except Exception:
            try:
                tree.root.reset()
            except Exception:
                pass

    def _tick_tree(tree: BehaviorTree, node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        tree.root.blackboard = node.blackboard

        result = tree.root.tick()

        if isinstance(
            result,
            BehaviorTree.NodeState,
        ):
            return result

        if result is True:
            return BehaviorTree.NodeState.SUCCESS

        if result is False:
            return BehaviorTree.NodeState.FAILURE

        return BehaviorTree.NodeState.RUNNING

    def _reset_all() -> None:
        _reset_tree(move_to_next)
        _reset_tree(move_to_previous)
        _reset_tree(relight_previous)
        _reset_tree(interact_next)

        state["phase"] = "move_to_next"
        state["started_at"] = 0.0
        state["phase_started_at"] = 0.0
        state["recovery_count"] = 0

    def _begin_recovery(now: float, reason: str) -> BehaviorTree.NodeState:
        state["recovery_count"] += 1

        recovery_limit = max(1, int(max_recoveries))

        if state["recovery_count"] > recovery_limit:
            _trace(f'{reason} Local recovery failed after {recovery_limit} attempt(s).', PySystem.Console.MessageType.Warning)

            _cancel_current_movement()
            _reset_all()

            return BehaviorTree.NodeState.FAILURE

        _trace(f"{reason} Returning to the previous brazier (recovery {state['recovery_count']}/{recovery_limit}).", PySystem.Console.MessageType.Warning)

        # Tous les sous-arbres concernés sont remis à zéro avant
        # d'entamer la récupération locale.
        _reset_tree(move_to_next)
        _reset_tree(move_to_previous)
        _reset_tree(relight_previous)
        _reset_tree(interact_next)

        _cancel_current_movement()

        state["phase"] = "move_to_previous"
        state["phase_started_at"] = now

        return BehaviorTree.NodeState.RUNNING

    def _move_with_recovery(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now = time.monotonic()

        if state["started_at"] <= 0.0:
            state["started_at"] = now
            state["phase_started_at"] = now

            _trace(f'Starting monitored BT movement from {previous_brazier} to {next_brazier}.')

        elapsed_ms = (now - float(state['started_at'])) * 1000.0

        if elapsed_ms >= max(
            1,
            int(timeout_ms),
        ):
            _trace('Timed out while moving between braziers.', PySystem.Console.MessageType.Warning)

            _cancel_current_movement()
            _reset_all()

            return BehaviorTree.NodeState.FAILURE

        if bool(
            node.blackboard.get(
                "USER_INTERRUPT_ACTIVE",
                False,
            )
        ):
            _cancel_current_movement()
            _reset_all()

            return BehaviorTree.NodeState.FAILURE

        phase = str(state['phase'])

        # --------------------------------------------------------------
        # Déplacement vers le prochain brasero
        # --------------------------------------------------------------
        if phase == "move_to_next":
            if not _has_active_flame():
                return _begin_recovery(now, 'Torch flame extinguished during movement.')

            result = _tick_tree(move_to_next, node)

            if result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if result == BehaviorTree.NodeState.FAILURE:
                return _begin_recovery(now, 'Movement to the next brazier failed.')

            _reset_tree(move_to_next)

            state["phase"] = "interact_next"
            state["phase_started_at"] = now

            _trace('Reached the next brazier with the torch still active.')

            return BehaviorTree.NodeState.RUNNING

        # --------------------------------------------------------------
        # Interaction avec le prochain brasero
        # --------------------------------------------------------------
        if phase == "interact_next":
            if not _has_active_flame():
                return _begin_recovery(now, 'Torch flame extinguished before the next brazier interaction.')

            result = _tick_tree(interact_next, node)

            if result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if result == BehaviorTree.NodeState.FAILURE:
                # Ne pas laisser FAILURE remonter au planner.
                # On retourne localement au précédent brasero.
                return _begin_recovery(now, 'Interaction with the next brazier failed.')

            _trace('Next brazier interaction completed.', PySystem.Console.MessageType.Success)

            _reset_all()

            return BehaviorTree.NodeState.SUCCESS

        # --------------------------------------------------------------
        # Retour au précédent brasero
        # --------------------------------------------------------------
        if phase == "move_to_previous":
            result = _tick_tree(move_to_previous, node)

            if result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if result == BehaviorTree.NodeState.FAILURE:
                _trace('Movement back to the previous brazier failed.', PySystem.Console.MessageType.Warning)

                _cancel_current_movement()
                _reset_all()

                return BehaviorTree.NodeState.FAILURE

            _reset_tree(move_to_previous)

            state["phase"] = "relight_previous"
            state["phase_started_at"] = now

            _trace('Reached the previous brazier. Relighting the torch.')

            return BehaviorTree.NodeState.RUNNING

        # --------------------------------------------------------------
        # Interaction avec le précédent brasero
        # --------------------------------------------------------------
        if phase == "relight_previous":
            result = _tick_tree(relight_previous, node)

            if result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if result == BehaviorTree.NodeState.FAILURE:
                _trace('Interaction with the previous brazier failed. Retrying local recovery.', PySystem.Console.MessageType.Warning)

                _reset_tree(relight_previous)

                state["phase"] = "move_to_previous"
                state["phase_started_at"] = now

                return BehaviorTree.NodeState.RUNNING

            _reset_tree(relight_previous)

            state["phase"] = "wait_for_relight"
            state["phase_started_at"] = now

            return BehaviorTree.NodeState.RUNNING

        # --------------------------------------------------------------
        # Attente de la réapparition de l'effet de flamme
        # --------------------------------------------------------------
        if phase == "wait_for_relight":
            if _has_active_flame():
                _trace('Torch relit successfully. Resuming movement to the next brazier.', PySystem.Console.MessageType.Success)

                _reset_tree(move_to_next)
                _reset_tree(interact_next)

                state["phase"] = "move_to_next"
                state["phase_started_at"] = now

                return BehaviorTree.NodeState.RUNNING

            elapsed_phase_ms = (now - float(state['phase_started_at'])) * 1000.0

            if elapsed_phase_ms < max(
                1,
                int(effect_apply_timeout_ms),
            ):
                return BehaviorTree.NodeState.RUNNING

            _trace('The torch effect did not return after the previous brazier interaction. Retrying.', PySystem.Console.MessageType.Warning)

            _reset_tree(relight_previous)

            state["phase"] = "relight_previous"
            state["phase_started_at"] = now

            return BehaviorTree.NodeState.RUNNING

        _trace(f"Unknown brazier recovery phase '{phase}'.", PySystem.Console.MessageType.Warning)

        _cancel_current_movement()
        _reset_all()

        return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(BehaviorTree.ActionNode(name=name, action_fn=_move_with_recovery, aftercast_ms=0))
# endregion


# region Bot initialization


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
                looting_enabled=True,
                resurrection_scroll=True,
                auto_inventory_handler_enabled=True,
                consumable_upkeeps=_enabled_consumable_upkeeps(),
                enable_party_wipe_recovery=True,
                heroai_state_logging=False,
            ),
        )

    return botting_tree


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()
    return BT.Sequence(
        name="Initialize Shards of Orr BT",
        children=[
            ResetTorchCombatPolicy(),
            bot.Config.Aggressive(
                multi_account=True,
                auto_loot=True,
                resurrection_scroll=True,
                account_isolation=False,
            ),
            BT.SetPlayerStatus(PlayerStatus.Offline, log=True),
            BT.LogMessage(message="Shards of Orr BT initialized", module_name=MODULE_NAME),
        ],
    )


# endregion


# region Preparation and dungeon entry


def PreparePartyAndSupplies() -> BehaviorTree:
    already_ready_in_level_1 = BT.Sequence(
        name="Skip Outpost Preparation - Already In Level 1",
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True),
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state='active', log=True),
            BT.Succeeder("OutpostPreparationAlreadyDone"),
        ],
    )
    normal_preparation = BT.Sequence(
        name="Prepare Party And Supplies From Vlox",
        map_id_or_name=VLOXS_FALL,
        random_travel=True,
        hard_mode=None,
        children=[
            # Keep inventory maintenance and party formation in the same ordered
            # subtree so the planner cannot form the party before maintenance.
            StartupInventoryCheck(),
            BT.CreateParty(multibox_invite=True, timeout_ms=30_000, log=True),
            BT.AbandonQuest(quest_id=LOST_SOULS_QUEST_ID, multi_account=True, include_self=True, timeout_ms=10000, log=True),
            _runtime_difficulty_node(),
            _runtime_restock_node(),
            BT.LogMessage(message="Party formed and selected settings applied", module_name=MODULE_NAME),
        ],
    )
    return BT.Selector(children=[already_ready_in_level_1, normal_preparation], name="Prepare Party And Supplies")


def TravelToShandra() -> BehaviorTree:
    skip_if_already_in_level_1 = BT.Sequence(
        name="Skip Travel To Shandra - Already In Level 1",
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True),
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state="active", log=True),
            BT.Succeeder("TravelToShandraAlreadyDone"),
        ],
    )
    normal_travel = BT.Sequence(
        name="Travel To Shandra From Vlox",
        children=[
            BT.MoveAndExitMap(VLOXS_EXIT, target_map_id=ARBOR_BAY, log=True),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.MoveAndDialog(ARBOR_BLESSING_NPC, dialog_id=ARBOR_BLESSING_DIALOG, multi_account=True, log=True),
            BT.Move(ARBOR_TO_SHANDRA_PATH, pause_on_combat=True, log=False),
            BT.WaitUntilOutOfCombat(timeout_ms=60_000),
            BT.Move(SHANDRA_APPROACH,avoid_obstacles=False,  pause_on_combat=False, log=False),
        ],
    )
    return BT.Selector(children=[skip_if_already_in_level_1, normal_travel], name="Travel To Shandra")


def HandleShandraQuest() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Shandra Handler - Already In Level 1",
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True),
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state="active", log=True),
            BT.Succeeder("ShandraHandlerAlreadyDone"),
        ],
    )
    active = BT.Sequence(name='Lost Souls Already Active', children=[BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state='active', log=True), BT.Succeeder('ContinueWithActiveQuest')])
    completed = BT.Sequence(
        name="Collect And Retake Lost Souls",
        children=[
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state="complete", log=True),
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_REWARD_DIALOG, pause_on_combat=False, multi_account=True, log=True),
            BT.WaitForQuestCleared(LOST_SOULS_QUEST_ID, timeout_ms=15_000),
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=True),
            BT.WaitForActiveQuest(LOST_SOULS_QUEST_ID, timeout_ms=15_000),
        ],
    )
    missing = BT.Sequence(
        name="Take Lost Souls",
        children=[
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state="missing", log=True),
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=True),
            BT.WaitForActiveQuest(LOST_SOULS_QUEST_ID, timeout_ms=15_000),
        ],
    )
    return BT.Selector(children=[already_inside, active, completed, missing], name="Handle Shandra Quest")


def EnterShardsOfOrr(enable_consumables_on_entry: bool=True) -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Dungeon Entry - Already In Level 1",
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True),
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state="active", log=True),
            BT.Succeeder("DungeonEntryAlreadyDone"),
        ],
    )
    normal_entry = BT.Sequence(
        name="Enter Shards of Orr From Arbor Bay",
        children=[
            BT.Move(SOO_ENTRANCE_PATH, pause_on_combat=False, ignore_destination_obstacles=True, log=False),
            BT.WaitForMapLoad(map_id=SOO_LEVEL_1, timeout_ms=60_000),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
        ],
    )
    entry = BT.Selector(children=[already_inside, normal_entry], name='Enter Shards of Orr')

    if not enable_consumables_on_entry:
        return entry

    return BT.Sequence(name='Enter Shards of Orr And Resume Consumables', children=[entry, _runtime_consumable_upkeep_node(True)])


# endregion


# region Planner point steps


def _map_guarded_point(name: str, map_id: int, child: BehaviorTree, skip_if_in_maps: Sequence[int]=()) -> BehaviorTree:
    """Run one point on its map, or accept it when the next level is loaded."""
    branches: list[BehaviorTree] = [BT.Sequence(name=f'{name} - Active Map', children=[BT.IsCurrentMap(map_id=map_id, log=False), child])]

    for later_map_id in skip_if_in_maps:
        branches.append(BT.Sequence(name=f'{name} - Later Map {later_map_id}', children=[BT.IsCurrentMap(map_id=later_map_id, log=False), BT.Succeeder(f'{name}AlreadyPassed')]))

    if len(branches) == 1:
        return branches[0]

    return BT.Selector(name=name, children=branches)


def _movement_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[PathPoint],
    *,
    pause_on_combat: bool,
    tolerance: float = 200.0,
    flag_heroes_to_waypoint: bool = False,
    ignore_destination_obstacles: bool = False,
    skip_if_in_maps: Sequence[int] = (),
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"
        steps.append(
            (
                name,
                lambda point=point, name=name: _map_guarded_point(name=name, map_id=map_id, child=BT.Move(point, pause_on_combat=pause_on_combat, tolerance=tolerance, flag_heroes_to_waypoint=flag_heroes_to_waypoint, ignore_destination_obstacles=ignore_destination_obstacles, log=False), skip_if_in_maps=skip_if_in_maps),
            )
        )

    return steps


def _vanquish_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[PathPoint],
    *,
    clear_area_radius: float = Range.Spirit.value,
    pause_on_combat: bool | None = None,
    flag_heroes_to_waypoint: bool = False,
    move_tolerance: float = 500.0,
    skip_if_in_maps: Sequence[int] = (),
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"
        steps.append(
            (
                name,
                lambda point=point, name=name: _map_guarded_point(name=name, map_id=map_id, child=BT.VanquishNode([point], name=name, clear_area_radius=clear_area_radius, pause_on_combat=pause_on_combat, flag_heroes_to_waypoint=flag_heroes_to_waypoint, move_tolerance=move_tolerance, log=False), skip_if_in_maps=skip_if_in_maps),
            )
        )

    return steps


# endregion
# region Level 1


def Level1_Start() -> BehaviorTree:
    return BT.Sequence(
        name="Start Shards of Orr Level 1",
        children=[
            _mark_run_start_node(),
            _inventory_statistics_node(after_chest=False),
            UseAvailableSummoningStone(),
            BT.AddModelToLootWhitelist(25410),
            BT.MoveAndDialog(Vec2f(-11686.0, 10427.0), dialog_id=DWARVEN_BLESSING_DIALOG, multi_account=True, log=True),
        ],
    )


def Level1_OpenDoor() -> BehaviorTree:
    return BT.Sequence(name='Open Level 1 Door', children=[BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True), BT.MoveAndInteractWithGadget(Vec2f(15100.0, 5443.0), pause_on_combat=True, log=True)])


def Level1_EnterLevel2() -> BehaviorTree:
    name = f"Level 1 Route To Level 2 - Point {len(L1_PATH_AFTER_DOOR):02d}"
    return BT.Sequence(
        name=name,
        children=[
            _map_guarded_point(name=name, map_id=SOO_LEVEL_1, child=BT.Sequence(name=f'{name} And Load Level 2', children=[BT.VanquishNode([L1_PATH_AFTER_DOOR[-1]], name=name, flag_heroes_to_waypoint=False, move_tolerance=500, log=False), BT.WaitForMapLoad(map_id=SOO_LEVEL_2, timeout_ms=60000)]), skip_if_in_maps=(SOO_LEVEL_2,)),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            _mark_l2_start_node(),
            BT.Wait(2_000),
        ],
    )


# endregion


# region Level 2 - part 1


def Level2_Start() -> BehaviorTree:
    return BT.Sequence(
        name="Start Shards of Orr Level 2",
        children=[
            ResolveTorchCombatPolicy(),
            UseAvailableSummoningStone(),
            BT.AddModelToLootWhitelist(25410),
            BT.MoveAndDialog(L2_BLESSING_NPC, dialog_id=DWARVEN_BLESSING_DIALOG, multi_account=True, log=True),
            BT.Move(Vec2f(-15243.0, -17230.0)),
            BT.ClearEnemiesInArea(Vec2f(-15243.0, -17230.0), radius=Range.Compass.value, log=True),
            BT.MoveAndInteractWithGadget(L2_TORCH_CHEST, pause_on_combat=False, log=True),
            PickupTorch(),
        ],
    )


def Level2_FirstTorchFight() -> BehaviorTree:
    return BT.Sequence(name='Level 2 First Torch Fight', children=[DropTorchForCombat(log=True), BT.VanquishNode([L2_RETURN_TO_FIRST_TORCH_PATH], clear_area_radius=Range.SafeCompass.value, log=True), PickupTorch()])


def Level2_BrazierRoute1() -> BehaviorTree:
    return BT.Sequence(name='Level 2 Brazier Route 1', children=[BrazierSequence('Level 2 Brazier Route 1', L2_BRAZIER_PART1), DropTorchForCombat(log=True)])


# endregion
# region Level 2 - part 2


def Level2_PrepareRoom2() -> BehaviorTree:
    return BT.Sequence(
        name="Prepare Level 2 Room 2",
        children=[
            ResolveTorchCombatPolicy(),
            BT.Wait(2000),
            BT.MoveAndKill(Vec2f(-9011.27, -11536.79)),
            BT.WaitForClearEnemiesInArea(-9011.0, -11536.0, radius=Range.SafeCompass.value, log=True),
            BT.Wait(2000),
            PickupTorch(),
        ],
    )


def Level2_DropTorchBeforeRoom2Return() -> BehaviorTree:
    return BT.Sequence(name='Drop Torch Before Returning To Room 2', children=[DropTorchForCombat(log=True)])


def Level2_PickupRoom2Torch() -> BehaviorTree:
    return BT.Sequence(name='Pick Up Level 2 Room 2 Torch', children=[PickupTorch()])


def Level2_DropTorchBeforeFinalRoom2Fight() -> BehaviorTree:
    return BT.Sequence(name='Drop Torch Before Final Room 2 Fight', children=[DropTorchForCombat(log=True)])


def Level2_PickupTorchForBrazierRoute2() -> BehaviorTree:
    return BT.Sequence(name='Pick Up Torch For Level 2 Brazier Route 2', children=[PickupTorch()])


def Level2_BrazierRoute2() -> BehaviorTree:
    return BT.Sequence(name='Level 2 Brazier Route 2', children=[BrazierSequence('Level 2 Brazier Route 2', L2_BRAZIER_PART2), BT.DropBundle(log=True)])


# endregion


# region Level 2 - part 3


def Level2_OpenDungeonLock() -> BehaviorTree:
    return BT.Sequence(name='Open Level 2 Dungeon Lock', children=[BT.IsCurrentMap(map_id=SOO_LEVEL_2, log=True), BT.MoveAndInteractWithGadget(L2_DUNGEON_LOCK, pause_on_combat=False, log=True)])


def Level2_EnterLevel3() -> BehaviorTree:
    name = f"Level 2 Exit Route - Point {len(L2_EXIT_PATH):02d}"
    return BT.Sequence(
        name=name,
        children=[
            _map_guarded_point(name=name, map_id=SOO_LEVEL_2, child=BT.Sequence(name=f'{name} And Load Level 3', children=[BT.Move(L2_EXIT_PATH[-1], pause_on_combat=False, tolerance=200.0, log=False), BT.WaitForMapLoad(map_id=SOO_LEVEL_3, timeout_ms=60000)]), skip_if_in_maps=(SOO_LEVEL_3,)),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            _mark_l3_start_node(),
            BT.Wait(2_000),
        ],
    )


# endregion

# region Level 3 - part 1


def Level3_Start() -> BehaviorTree:
    return BT.Sequence(name='Start Shards of Orr Level 3', children=[UseAvailableSummoningStone(), BT.MoveAndDialog(L3_ENTRY_BLESSING, dialog_id=DWARVEN_BLESSING_DIALOG, multi_account=True, log=True)])


def Level3_TorchAndBraziers() -> BehaviorTree:
    return BT.Sequence(
        name="Open Level 3 Torch Chest And Light Braziers",
        children=[
            BT.MoveAndInteractWithGadget(L3_TORCH_CHEST, pause_on_combat=False, log=True),
            PickupTorch(),
            BrazierSequence("Level 3 Brazier Route", L3_BRAZIERS),
            BT.DropBundle(log=True),
        ],
    )


# endregion


# region Level 3 - part 3
def Level3_Brigant() -> BehaviorTree:
    return BT.Sequence(
        name="Run Shards of Orr Level 3",
        children=[             
            BT.MoveAndKill(Vec2f(-11147, 2644), clear_area_radius=Range.Spirit.value, log=False),
            BT.AddModelToLootWhitelist(25410),
            BT.Move(Vec2f(-9888.47, 2892.00)),
            BT.LootItems(distance=Range.SafeCompass.value),
            
        ],
    )

def Level3_BrigantDoor() -> BehaviorTree:
    return BT.Sequence(name='Open Level 3 Brigant Door', children=[BT.MoveAndInteractWithGadget(Vec2f(-9252.32, 6396.4), pause_on_combat=False, log=True)])


# endregion

# region Level 3 - boss


FENDI_FIGHT_CENTER = (-15606.06, 15287.51)
FENDI_FIGHT_RADIUS = float(Range.Compass.value)
FENDI_TARGET_INTERVAL_MS = 750
FENDI_STABLE_CLEAR_MS = 15_000


def _fendi_distance_sq(agent_id: int, origin: tuple[float, float]) -> float:
    try:
        x, y = Agent.GetXY(agent_id)
    except Exception:
        return float("inf")
    dx = float(x) - float(origin[0])
    dy = float(y) - float(origin[1])
    return (dx * dx) + (dy * dy)


def _fendi_enemy_name(agent_id: int) -> str:
    try:
        return str(Agent.GetNameByID(agent_id) or "").strip()
    except Exception:
        return ""


def _fendi_final_chest_present() -> bool:
    """Return True once Fendi's final chest gadget has spawned."""
    origin = FENDI_CHEST_POSITION
    max_distance_sq = 1_200.0 * 1_200.0

    for agent_id in AgentArray.GetGadgetArray() or []:
        agent_id = int(agent_id)
        try:
            if int(Agent.GetGadgetID(agent_id) or 0) != int(FENDI_CHEST_GADGET_ID):
                continue
        except Exception:
            continue

        if _fendi_distance_sq(agent_id, origin) <= max_distance_sq:
            return True

    return False


def ClearFendiArenaWithBossPriority() -> BehaviorTree:
    """Clear Fendi's arena while forcing boss targets ahead of normal enemies.

    Priority:
      1. Any alive enemy with Agent.HasBossGlow().
      2. Any alive enemy whose decoded name contains "Fendi" (safety fallback).
      3. Nearest remaining enemy.

    The selected enemy is also called as the party target so HeroAI can follow
    the same focus. The node deliberately survives every Fendi <-> Soul
    transition and only hands off once Fendi's final chest appears. The stock
    final-clear sequence then performs the 15-second respawn verification.
    """
    state = {'last_target_id': 0, 'last_interact_ms': 0}

    center = FENDI_FIGHT_CENTER
    radius_sq = FENDI_FIGHT_RADIUS * FENDI_FIGHT_RADIUS

    def _alive_enemies_in_arena() -> list[int]:
        result: list[int] = []
        for agent_id in AgentArray.GetEnemyArray() or []:
            agent_id = int(agent_id)
            try:
                if not Agent.IsAlive(agent_id):
                    continue
            except Exception:
                continue
            if _fendi_distance_sq(agent_id, center) <= radius_sq:
                result.append(agent_id)
        return result

    def _priority_boss_targets(enemies: list[int]) -> list[int]:
        """Return Fendi / Soul candidates before ordinary enemies."""
        boss_glow: list[int] = []
        named_fendi: list[int] = []

        for agent_id in enemies:
            try:
                if Agent.HasBossGlow(agent_id):
                    boss_glow.append(agent_id)
                    continue
            except Exception:
                pass

            if "fendi" in _fendi_enemy_name(agent_id).casefold():
                named_fendi.append(agent_id)

        return boss_glow if boss_glow else named_fendi

    def _choose_target(enemies: list[int]) -> tuple[int, str]:
        player_xy = Player.GetXY()
        priority_targets = _priority_boss_targets(enemies)

        if priority_targets:
            target_id = min(priority_targets, key=lambda aid: _fendi_distance_sq(aid, player_xy))
            try:
                if Agent.HasBossGlow(target_id):
                    return target_id, "BossGlow"
            except Exception:
                pass
            return target_id, "FendiName"

        return (min(enemies, key=lambda aid: _fendi_distance_sq(aid, player_xy)), 'NearestEnemy')

    def _fight(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now_ms = int(time.monotonic() * 1000.0)

        # Do not steal the target while the shared loot service is busy.
        try:
            account_email = Player.GetAccountEmail()
            index, message = GLOBAL_CACHE.ShMem.PreviewNextMessage(account_email)
            if (
                index != -1
                and message
                and message.Command == SharedCommandType.PickUpLoot
                and bool(getattr(message, "Running", False))
            ):
                return BehaviorTree.NodeState.RUNNING
        except Exception:
            pass

        if bool(node.blackboard.get("PAUSE_MOVEMENT", False)):
            return BehaviorTree.NodeState.RUNNING

        try:
            if Agent.IsDead(Player.GetAgentID()):
                return BehaviorTree.NodeState.RUNNING
        except Exception:
            pass

        enemies = _alive_enemies_in_arena()
        node.blackboard["fendi_arena_enemy_count"] = len(enemies)


        chest_present = _fendi_final_chest_present()

        if not enemies:
            state["last_target_id"] = 0
            state["last_interact_ms"] = 0

            if chest_present:
                PySystem.Console.Log(MODULE_NAME, 'Fendi final chest detected. Boss/Soul cycle is complete; switching to final stock area-clear verification.', PySystem.Console.MessageType.Success)
                return BehaviorTree.NodeState.SUCCESS

            return BehaviorTree.NodeState.RUNNING
        
        if chest_present and not _priority_boss_targets(enemies):
            PySystem.Console.Log(MODULE_NAME, 'Fendi final chest detected with only normal enemies remaining. Handing final cleanup to ClearEnemiesInArea.', PySystem.Console.MessageType.Info)
            state["last_target_id"] = 0
            state["last_interact_ms"] = 0
            return BehaviorTree.NodeState.SUCCESS

        target_id, priority_label = _choose_target(enemies)
        target_changed = int(state["last_target_id"]) != int(target_id)
        interaction_due = now_ms - int(state["last_interact_ms"]) >= FENDI_TARGET_INTERVAL_MS

        if target_changed:
            Player.ChangeTarget(target_id)
            try:
                Player.CallTarget(target_id)
            except Exception:
                pass
            try:
                Player.Interact(target_id, False)
            except Exception:
                pass

            target_name = _fendi_enemy_name(target_id) or f"agent {target_id}"
            try:
                boss_glow = bool(Agent.HasBossGlow(target_id))
            except Exception:
                boss_glow = False

            PySystem.Console.Log(MODULE_NAME, f'Fendi priority target -> {target_name} (id={target_id}, priority={priority_label}, boss_glow={boss_glow}, enemies={len(enemies)}).', PySystem.Console.MessageType.Info)
            state["last_target_id"] = target_id
            state["last_interact_ms"] = now_ms
            return BehaviorTree.NodeState.RUNNING

        if interaction_due:
            Player.ChangeTarget(target_id)
            try:
                Player.Interact(target_id, False)
            except Exception:
                pass
            state["last_interact_ms"] = now_ms

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name='Clear Fendi Arena With Boss Priority', action_fn=_fight, aftercast_ms=0))


def Level3_FendiFight() -> BehaviorTree:
    return BT.Sequence(
        name="Run Fendi Boss Fight",
        children=[
            BT.Move(Vec2f(-13198.79, 13789.36),log=True),
            ClearFendiArenaWithBossPriority(),
            BT.ClearEnemiesInArea(Vec2f(-15606.06, 15287.51), radius=Range.Compass.value, log=True),
            BT.WaitForClearEnemiesInArea(-15606.06, 15287.51, radius=Range.Compass.value, allowed_alive_enemies=0, interact_interval_ms=750, stable_clear_ms=15000, keep_player_near_center=False, center_tolerance=750.0, log=True),
            _record_run_end_node(),
        ],
    )
#endregion

# region Level 3 - Chest

def _set_party_looting_node(enabled: bool) -> BehaviorTree:
    """Enable/disable headless auto-loot locally and on the multibox party."""

    local_state = BehaviorTree(
        BehaviorTree.ActionNode(
            name=("Enable Local Looting" if enabled else "Disable Local Looting"),
            action_fn=lambda _node: (
                _configure_runtime_upkeeps(looting_enabled=enabled)
                or BehaviorTree.NodeState.SUCCESS
            ),
            aftercast_ms=0,
        )
    )

    remote_state = BTShared.SendAndWait(
        command=SharedCommandType.SetHeadlessLooting,
        params=(1.0 if enabled else 0.0, 0.0, 0.0, 0.0),
        include_self=False,
        refs_blackboard_key=(
            "fendi_enable_remote_looting_refs"
            if enabled
            else "fendi_disable_remote_looting_refs"
        ),
        timeout_ms=10_000,
        poll_interval_ms=100,
        log=True,
    )

    return BT.Sequence(
        name=("Enable Party Looting" if enabled else "Disable Party Looting"),
        children=[
            local_state,
            remote_state,
            BT.Wait(300),
        ],
    )

def _fendi_stack_party_safe() -> BehaviorTree:
    """Approach the chest from the north side and stack remote accounts there."""

    return BT.Sequence(
        name="Stack Party At Safe Fendi Chest Position",
        children=[
            BT.Move(
                FENDI_CHEST_SAFE_POSITION,
                tolerance=80.0,
                pause_on_combat=False,
                flag_heroes_to_waypoint=False,
                ignore_destination_obstacles=False,
                ignore_destination_npcs=False,
                ignore_destination_gadgets=False,
                log=True,
            ),
            BTShared.SendAndWait(
                command=SharedCommandType.PixelStack,
                params=(
                    float(FENDI_CHEST_SAFE_POSITION.x),
                    float(FENDI_CHEST_SAFE_POSITION.y),
                    0.0,
                    0.0,
                ),
                include_self=False,
                refs_blackboard_key="fendi_safe_stack_refs",
                timeout_ms=20_000,
                poll_interval_ms=100,
                log=True,
            ),
            BT.Wait(750),
        ],
    )

def _fendi_geyser_is_active(agent_id: int) -> bool:
    """Return True while a Fendi 8015 geyser is actively venting.

    The ON/OFF probe captured the same geyser with NameProperties 0x8022
    while ON and 0x0022 while OFF. Bit 0x8000 is therefore the runtime
    activity flag used by the safe-loot routine.
    """

    try:
        properties = int(Agent.GetNameProperties(int(agent_id)) or 0)
    except Exception:
        # Unknown state must be treated as dangerous.
        return True

    # A zero value is commonly seen for a gadget before its state snapshot has
    # settled. Do not interpret that transient/unknown state as a safe window.
    if properties == 0:
        return True

    return bool(properties & FENDI_GEYSER_ACTIVE_NAME_PROPERTY_BIT)

def _fendi_active_geyser_positions() -> list[tuple[float, float]]:
    """Return only currently-active Fendi geysers near the final chest.

    If no live 8015 gadget can be resolved at all, fall back to the known
    positions and treat them as dangerous. An empty list is valid when the
    gadgets are present but every geyser is currently OFF.
    """

    active_geysers: list[tuple[float, float]] = []
    found_runtime_geyser = False

    for agent_id in AgentArray.GetGadgetArray() or []:
        agent_id = int(agent_id)
        try:
            if int(Agent.GetGadgetID(agent_id) or 0) != FENDI_GEYSER_GADGET_ID:
                continue

            x, y = Agent.GetXY(agent_id)
        except Exception:
            continue

        dx = float(x) - float(FENDI_CHEST_POSITION[0])
        dy = float(y) - float(FENDI_CHEST_POSITION[1])
        if (dx * dx) + (dy * dy) > (3_500.0 * 3_500.0):
            continue

        found_runtime_geyser = True
        if _fendi_geyser_is_active(agent_id):
            active_geysers.append((float(x), float(y)))

    if found_runtime_geyser:
        return active_geysers

    # No runtime state is available: preserve the previous conservative safety
    # behaviour instead of assuming that the area is clear.
    return list(FENDI_GEYSER_FALLBACK_POSITIONS)

def _distance_sq_to_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    """Squared distance from a point to a line segment."""

    px, py = float(point[0]), float(point[1])
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])

    abx = bx - ax
    aby = by - ay
    ab_len_sq = (abx * abx) + (aby * aby)

    if ab_len_sq <= 0.0001:
        dx = px - ax
        dy = py - ay
        return (dx * dx) + (dy * dy)

    t = ((px - ax) * abx + (py - ay) * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))

    cx = ax + (abx * t)
    cy = ay + (aby * t)
    dx = px - cx
    dy = py - cy
    return (dx * dx) + (dy * dy)

def _fendi_account_agent_id(account: object) -> int:
    return int(
        getattr(account, "PlayerID", 0)
        or getattr(getattr(account, "AgentData", None), "AgentID", 0)
        or 0
    )

def _fendi_account_position(account: object) -> tuple[float, float]:
    agent_data = getattr(account, "AgentData", None)
    pos = getattr(agent_data, "Pos", None)
    return (
        float(getattr(pos, "x", 0.0) or 0.0),
        float(getattr(pos, "y", 0.0) or 0.0),
    )

def _fendi_same_level3_accounts() -> list[object]:
    accounts: list[object] = []
    for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
        map_data = getattr(getattr(account, "AgentData", None), "Map", None)
        if int(getattr(map_data, "MapID", 0) or 0) != SOO_LEVEL_3:
            continue
        accounts.append(account)
    return accounts

def _fendi_loot_recipient(item_agent_id: int) -> tuple[str, tuple[float, float]] | None:
    """Resolve the owning multibox account for a visible chest drop."""

    try:
        owner_id = int(Agent.GetItemAgentOwnerID(item_agent_id) or 0)
    except Exception:
        owner_id = 0

    local_email = str(Player.GetAccountEmail() or "").strip()

    if owner_id <= 0:
        # Unassigned drop: keep it on the leader rather than sending two accounts
        # to the same object.
        if not local_email:
            return None
        player_x, player_y = Player.GetXY()
        return local_email, (float(player_x), float(player_y))

    for account in _fendi_same_level3_accounts():
        if _fendi_account_agent_id(account) != owner_id:
            continue
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if email:
            return email, _fendi_account_position(account)

    if owner_id == int(Player.GetAgentID() or 0) and local_email:
        player_x, player_y = Player.GetXY()
        return local_email, (float(player_x), float(player_y))

    return None

def _fendi_loot_path_is_safe(
    start: tuple[float, float],
    end: tuple[float, float],
    geysers: Sequence[tuple[float, float]],
) -> bool:
    safety_sq = float(FENDI_GEYSER_SAFETY_RADIUS) ** 2

    # The endpoint itself must be outside every geyser.
    for geyser in geysers:
        dx = float(end[0]) - float(geyser[0])
        dy = float(end[1]) - float(geyser[1])
        if (dx * dx) + (dy * dy) <= safety_sq:
            return False

    # Also reject a direct approach that cuts through a geyser circle.
    for geyser in geysers:
        if _distance_sq_to_segment(geyser, start, end) <= safety_sq:
            return False

    return True

def SafeLootFendiChest() -> BehaviorTree:
    """Loot chest drops only during a safe Fendi geyser window.

    A drop is never skipped merely because its path is currently blocked by an
    active geyser. The routine first waits for a safe OFF window. If the safe
    wait reaches FENDI_SAFE_LOOT_TIMEOUT_MS, it switches to forced pickup mode:
    geyser state is ignored and the remaining valid chest loot is still picked
    up. Auto-loot remains disabled until the party leaves Level 3 so HeroAI
    cannot override this controlled pass.
    """

    state = {
        "started_at": 0.0,
        "pending_index": -1,
        "pending_receiver": "",
        "pending_item": 0,
        "attempts": {},
        "skipped": set(),
        # Used only to avoid log spam while the same item remains blocked by a
        # currently-active geyser.
        "waiting_for_geyser": set(),
        # Safety first, loot always: once the safe-wait timeout expires the
        # routine ignores geyser state and keeps trying to collect valid drops.
        "force_pickup_mode": False,
    }

    def _message_is_active(index: int, receiver_email: str) -> bool:
        if index < 0 or not receiver_email:
            return False
        try:
            message = GLOBAL_CACHE.ShMem.GetInbox(index)
        except Exception:
            return False
        return bool(
            message
            and getattr(message, "Active", False)
            and str(getattr(message, "ReceiverEmail", "") or "") == receiver_email
            and int(getattr(message, "Command", -1))
            == int(SharedCommandType.InteractWithTarget)
        )

    def _safe_loot(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now = time.monotonic()
        if state["started_at"] <= 0.0:
            state["started_at"] = now

        if (
            not bool(state["force_pickup_mode"])
            and (now - state["started_at"]) * 1000.0 >= FENDI_SAFE_LOOT_TIMEOUT_MS
        ):
            waiting = set(state["waiting_for_geyser"])
            state["force_pickup_mode"] = True
            state["waiting_for_geyser"] = set()

            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "Safe Fendi chest loot wait expired. Switching to FORCED PICKUP: "
                    "geyser ON/OFF state is now ignored so the final chest loot "
                    f"is not left behind. Waiting drops={len(waiting)}."
                ),
                PySystem.Console.MessageType.Warning,
            )

        pending_index = int(state["pending_index"])
        pending_receiver = str(state["pending_receiver"])
        pending_item = int(state["pending_item"])

        if pending_index >= 0:
            if _message_is_active(pending_index, pending_receiver):
                return BehaviorTree.NodeState.RUNNING

            # The remote/local interaction finished. If the item is still there,
            # count another attempt before eventually skipping it.
            state["pending_index"] = -1
            state["pending_receiver"] = ""
            state["pending_item"] = 0
            if pending_item > 0 and Agent.IsValid(pending_item):
                attempts = dict(state["attempts"])
                attempts[pending_item] = int(attempts.get(pending_item, 0)) + 1
                state["attempts"] = attempts
                if attempts[pending_item] >= FENDI_SAFE_LOOT_MAX_ATTEMPTS_PER_ITEM:
                    skipped = set(state["skipped"])
                    skipped.add(pending_item)
                    state["skipped"] = skipped
                    waiting = set(state["waiting_for_geyser"])
                    waiting.discard(pending_item)
                    state["waiting_for_geyser"] = waiting
                    PySystem.Console.Log(
                        MODULE_NAME,
                        f"Skipping chest drop agent {pending_item} after repeated pickup failure.",
                        PySystem.Console.MessageType.Warning,
                    )

        force_pickup_mode = bool(state["force_pickup_mode"])
        active_geysers = (
            []
            if force_pickup_mode
            else _fendi_active_geyser_positions()
        )
        skipped = set(state["skipped"])
        waiting_for_geyser = set(state["waiting_for_geyser"])

        try:
            loot_array = LootFilters().GetLootArray(FENDI_CHEST_LOOT_SCAN_RADIUS)
        except Exception:
            loot_array = []

        candidates: list[int] = []
        blocked_items: set[int] = set()

        for item_agent_id in loot_array:
            item_agent_id = int(item_agent_id or 0)
            if item_agent_id <= 0 or item_agent_id in skipped:
                continue
            if not Agent.IsValid(item_agent_id):
                waiting_for_geyser.discard(item_agent_id)
                continue

            try:
                item_xy = tuple(map(float, Agent.GetXY(item_agent_id)))
            except Exception:
                continue

            dx = item_xy[0] - float(FENDI_CHEST_POSITION[0])
            dy = item_xy[1] - float(FENDI_CHEST_POSITION[1])
            if (dx * dx) + (dy * dy) > FENDI_CHEST_LOOT_SCAN_RADIUS ** 2:
                continue

            recipient = _fendi_loot_recipient(item_agent_id)
            if recipient is None:
                continue

            _receiver_email, start_xy = recipient
            end_xy = (float(item_xy[0]), float(item_xy[1]))

            if not _fendi_loot_path_is_safe(start_xy, end_xy, active_geysers):
                blocked_items.add(item_agent_id)
                if item_agent_id not in waiting_for_geyser:
                    waiting_for_geyser.add(item_agent_id)
                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            f"Chest drop agent {item_agent_id} is blocked by an active "
                            "Fendi geyser. Waiting for the geyser to switch OFF."
                        ),
                        PySystem.Console.MessageType.Info,
                    )
                continue

            if item_agent_id in waiting_for_geyser:
                waiting_for_geyser.discard(item_agent_id)
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f"Safe geyser window detected for chest drop agent "
                        f"{item_agent_id}; attempting pickup now."
                    ),
                    PySystem.Console.MessageType.Success,
                )

            candidates.append(item_agent_id)

        state["waiting_for_geyser"] = waiting_for_geyser

        if not candidates:
            if blocked_items:
                # This is the important behaviour change: a dangerous drop is
                # retained and retried on every tick instead of being marked
                # skipped. As soon as the blocking 0x8000 state clears, it
                # becomes a normal pickup candidate.
                return BehaviorTree.NodeState.RUNNING

            if skipped:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f"Safe Fendi chest loot complete. {len(skipped)} drop(s) "
                        "were left behind only after repeated pickup failure."
                    ),
                    PySystem.Console.MessageType.Info,
                )
            return BehaviorTree.NodeState.SUCCESS

        item_agent_id = candidates[0]
        recipient = _fendi_loot_recipient(item_agent_id)
        if recipient is None:
            skipped.add(item_agent_id)
            state["skipped"] = skipped
            return BehaviorTree.NodeState.RUNNING

        receiver_email, _start_xy = recipient
        sender_email = str(Player.GetAccountEmail() or "").strip()
        if not sender_email or not receiver_email:
            skipped.add(item_agent_id)
            state["skipped"] = skipped
            return BehaviorTree.NodeState.RUNNING

        message_index = GLOBAL_CACHE.ShMem.SendMessage(
            sender_email,
            receiver_email,
            SharedCommandType.InteractWithTarget,
            (float(item_agent_id), 0.0, 0.0, 0.0),
        )

        if int(message_index) < 0:
            skipped.add(item_agent_id)
            state["skipped"] = skipped
            return BehaviorTree.NodeState.RUNNING

        state["pending_index"] = int(message_index)
        state["pending_receiver"] = receiver_email
        state["pending_item"] = item_agent_id
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Safe Loot Fendi Chest",
            action_fn=_safe_loot,
            aftercast_ms=100,
        )
    )

def Level3_Chest() -> BehaviorTree:
    """Open and loot the final Fendi chest with geyser-aware multibox safety.

    This keeps the current functional chest approach/interaction timings, but
    temporarily disables normal party auto-loot so chest drops can be collected
    only when the probe-confirmed Fendi geyser state/path is safe. If no safe
    window appears within the configured timeout, the routine falls back to
    forced pickup so valid final-chest loot is not abandoned.
    """

    return BT.Sequence(
        name="Open Fendi Chest Safely",
        children=[
            # Prevent normal HeroAI/headless auto-loot from moving accounts into
            # a live geyser while the controlled final-chest pass is running.
            _set_party_looting_node(False),

            # Preserve the current functional north-side approach waypoint.
            BT.Move(
                Vec2f(-15198.0, 16839.0),
                pause_on_combat=False,
                log=False,
            ),

            # Stack the whole multibox party at the known safe north-side point.
            _fendi_stack_party_safe(),

            # Preserve the interaction parameters from the current functional bot.
            BT.MoveAndInteractWithGadget(
                gadget_id=FENDI_CHEST_GADGET_ID,
                pos=Vec2f(*FENDI_CHEST_POSITION),
                search_distance=700.0,
                interaction_distance=Range.Nearby.value,
                interaction_count=2,
                interaction_interval_ms=1000,
                account_settle_ms=3000,
                timeout_ms=90000,
                multi_account=True,
                include_self=True,
                log=True,
            ),

            # Pull everyone back away from the chest/geyser line before looting.
            _fendi_stack_party_safe(),
            BT.Wait(750),

            # Controlled loot pass based on the 8015 geyser runtime state.
            SafeLootFendiChest(),

            _inventory_statistics_node(after_chest=True),
        ],
    )


#endregion


# region Reward and restart flow

def WaitForShandraInside(timeout_ms: int=30000) -> BehaviorTree:
    """Wait until Shandra is resolvable by name inside the dungeon."""

    def _check(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        agent_id = Agent.GetAgentIDByName("Shandra")

        if agent_id != 0:
            node.blackboard["shandra_agent_id"] = agent_id
            return BehaviorTree.NodeState.SUCCESS

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.WaitUntilNode(name='Wait For Shandra Inside Dungeon', condition_fn=_check, throttle_interval_ms=500, timeout_ms=timeout_ms))


def CollectInsideReward() -> BehaviorTree:
    """
    Collect the Lost Souls reward from Shandra inside the dungeon.

    Wait until Shandra is actually resolvable by name before targeting her.
    The lookup is retried every 500 ms for up to 30 seconds, without logging
    each internal attempt.
    """
    return BT.Sequence(
        name="Collect Inside Reward",
        children=[
            WaitForShandraInside(
                timeout_ms=30_000,
            ),
            BT.TargetAgentByName(agent_name='Shandra', log=True),
            BT.LogMessage(message='Shandra was found near the final chest. Attempting to collect the Lost Souls reward.', module_name=MODULE_NAME),
            BT.InteractTargetAndSendDialog(dialog_id=SHANDRA_REWARD_DIALOG, multi_account=True, log=True),
            BT.SendDialog(dialog_id=SHANDRA_REWARD_DIALOG, multi_account=True, log=True),
            BT.WaitForQuestCleared(LOST_SOULS_QUEST_ID, timeout_ms=15000),
            BT.Move(FENDI_CHEST_SAFE_POSITION, pause_on_combat=False, log=False),
        ],
    )




def ResolveShandraQuestAfterRun() -> BehaviorTree:
    """Leave Arbor Bay with Lost Souls active, without starting the next run."""
    direct_retake = BT.Sequence(
        name="Retake Lost Souls Directly",
        children=[
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=True),
            BT.WaitForActiveQuest(LOST_SOULS_QUEST_ID, timeout_ms=15000),
        ],
    )

    retake_after_reset_entry = BT.Sequence(
        name="Reset Shandra By Entering Level 1",
        children=[
            BT.LogMessage(message='Shandra did not offer Lost Souls directly. Entering and leaving Level 1 once before retrying.', module_name=MODULE_NAME),
            EnterShardsOfOrr(enable_consumables_on_entry=False),
            BT.MoveAndExitMap(LEVEL1_EXIT_TO_ARBOR, target_map_id=ARBOR_BAY, log=False),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.Move([Vec2f(10218.0, -18864.0), SHANDRA_APPROACH], pause_on_combat=False, log=False),
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=True),
            BT.WaitForActiveQuest(LOST_SOULS_QUEST_ID, timeout_ms=15000),
        ],
    )

    quest_already_active = BT.Sequence(
        name="Keep Active Lost Souls Quest",
        children=[
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state='active', log=True),
            BT.LogMessage(message='Lost Souls is already active for the next run.', module_name=MODULE_NAME),
        ],
    )

    reward_collected_inside = BT.Sequence(
        name="Retake Lost Souls After Inside Reward",
        children=[
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state='missing', log=True),
            BT.Selector(
                name="Retake Lost Souls With Reset Fallback",
                children=[
                    direct_retake,
                    BT.Sequence(name='Retake Completed Despite Wait Failure', children=[BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state='active', log=True), BT.Succeeder('LostSoulsRetakeAlreadyCompleted')]),
                    retake_after_reset_entry,
                ],
            ),
        ],
    )

    reward_not_collected_inside = BT.Sequence(
        name="Collect Outside Reward And Retake Lost Souls",
        children=[
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state='complete', log=True),
            BT.LogMessage(message='The reward is still pending. Collecting it from Shandra in Arbor Bay.', module_name=MODULE_NAME),
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_REWARD_DIALOG, pause_on_combat=False, multi_account=True, log=True),
            BT.WaitForQuestCleared(LOST_SOULS_QUEST_ID, timeout_ms=15000),
            BT.LogMessage(message='The Lost Souls reward was collected successfully in Arbor Bay.', module_name=MODULE_NAME),

            # Guild Wars requires one entry into Level 1 after an outside
            # reward before Shandra offers Lost Souls again.
            EnterShardsOfOrr(enable_consumables_on_entry=False),
            BT.MoveAndExitMap(LEVEL1_EXIT_TO_ARBOR, target_map_id=ARBOR_BAY, log=False),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.Move([Vec2f(10218.0, -18864.0), SHANDRA_APPROACH], pause_on_combat=False, log=False),
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=True),
            BT.WaitForActiveQuest(LOST_SOULS_QUEST_ID, timeout_ms=15000),
        ],
    )

    return BT.Sequence(
        name="Resolve Shandra Quest After Run",
        children=[
            BT.IsCurrentMap(map_id=ARBOR_BAY, log=True),
            BT.Selector(name='Resolve Lost Souls State In Arbor Bay', children=[quest_already_active, reward_collected_inside, reward_not_collected_inside]),
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state='active', log=True),
        ],
    )


def PrepareNextDungeonRun() -> BehaviorTree:
    already_inside = BT.Sequence(name='Next Run Already Entered', children=[BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True), BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state='active', log=True)])

    continue_from_arbor = BT.Sequence(name='Enter Next Run From Arbor Bay', children=[BT.IsCurrentMap(map_id=ARBOR_BAY, log=True), BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state='active', log=True), EnterShardsOfOrr()])

    continue_after_maintenance = BT.Sequence(
        name="Reform Party And Enter Next Run From Vlox",
        children=[
            BT.IsCurrentMap(map_id=VLOXS_FALL, log=True),
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state='active', log=True),
            BT.CreateParty(multibox_invite=True, timeout_ms=30000, log=True),
            _runtime_difficulty_node(),
            _runtime_restock_node(),
            TravelToShandra(),
            EnterShardsOfOrr(),
        ],
    )

    return BT.Selector(name='Prepare Next Dungeon Run', children=[already_inside, continue_from_arbor, continue_after_maintenance])


def CollectRewardAndReturnToArbor(end_countdown_timeout_ms: int=190000) -> BehaviorTree:
    already_in_arbor = BT.Sequence(
        name="Skip Inside Reward - Already In Arbor Bay",
        children=[
            BT.IsCurrentMap(map_id=ARBOR_BAY, log=True),
            BT.LogMessage(message='The party is already in Arbor Bay. Skipping the inside reward search and resuming the restart preparation.', module_name=MODULE_NAME),
            BT.Succeeder('InsideRewardAlreadyReturnedToArbor'),
        ],
    )

    reward_collected_inside = BT.Sequence(
        name="Collect Shandra Reward Inside Dungeon",
        children=[
            # Do not gate the Shandra lookup behind IsQuestState("complete").
            # TargetAgentByName works independently, while the quest-state mirror
            # can still report "active" for a short time after Fendi/chest.  If
            # Shandra is present, try her directly and let WaitForQuestCleared be
            # the source of truth for whether the reward was actually collected.
            BT.IsCurrentMap(map_id=SOO_LEVEL_3, log=True),
            BT.LogMessage(message='Level 3 confirmed after Fendi. Looking for Shandra by name inside the dungeon.', module_name=MODULE_NAME),
            CollectInsideReward(),
            BT.WaitForQuestCleared(LOST_SOULS_QUEST_ID, timeout_ms=15000),
            BT.LogMessage(message='Shandra was found inside the dungeon and the Lost Souls reward was collected.', module_name=MODULE_NAME),
        ],
    )

    reward_not_collected_inside = BT.Sequence(
        name="Shandra Unavailable Inside Dungeon",
        children=[
            BT.LogMessage(message='Shandra was not found inside the dungeon or the inside reward could not be collected. The reward will be handled in Arbor Bay.', module_name=MODULE_NAME),
            BT.Succeeder('InsideRewardUnavailable'),
            BT.Move(FENDI_CHEST_SAFE_POSITION, pause_on_combat=False, log=False),
        ],
    )

    return BT.Sequence(
        name="Collect Reward And Return To Arbor",
        children=[
            _runtime_consumable_upkeep_node(False),
            BT.Selector(name='Resolve Inside Reward', children=[already_in_arbor, reward_collected_inside, reward_not_collected_inside]),
            BT.LogMessage(message='Waiting for the end-of-dungeon countdown and the return to Arbor Bay.', module_name=MODULE_NAME),
            BT.WaitForMapLoad(map_id=ARBOR_BAY, timeout_ms=end_countdown_timeout_ms),
            BT.WaitUntilOnExplorable(timeout_ms=30000),
            BT.Wait(2000),
            # The final-chest geysers no longer exist after leaving Level 3.
            # Resume normal local + multibox auto-loot for the next run.
            _set_party_looting_node(True),
            BT.LogMessage(message='The party has returned to Arbor Bay. Preparing the next dungeon run.', module_name=MODULE_NAME),
            BT.Move(SHANDRA_APPROACH,pause_on_combat=False,log=False),
        ],
    )


# endregion


# region Execution

def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Initialize Bot", InitializeBot),
        ("Prepare Party And Supplies", PreparePartyAndSupplies),
        ("Travel To Shandra", TravelToShandra),
        ("Handle Shandra Quest", HandleShandraQuest),
        ("Enter Shards Of Orr", EnterShardsOfOrr),

        ("Level 1 Start", Level1_Start),
        *_vanquish_point_steps("Level 1 First Route", SOO_LEVEL_1, L1_PATH, skip_if_in_maps=(SOO_LEVEL_2, SOO_LEVEL_3)),
        ("Level 1 Open Door", Level1_OpenDoor),
        *_vanquish_point_steps("Level 1 Route To Level 2", SOO_LEVEL_1, L1_PATH_AFTER_DOOR[:-1], skip_if_in_maps=(SOO_LEVEL_2, SOO_LEVEL_3)),
        (f"Level 1 Route To Level 2 - Point {len(L1_PATH_AFTER_DOOR):02d}", Level1_EnterLevel2),

        ("Level 2 Start", Level2_Start),
        *_movement_point_steps("Level 2 First Torch Drop Route", SOO_LEVEL_2, L2_FIRST_TORCH_DROP_POINT_PATH, pause_on_combat=True, skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 First Torch Fight", Level2_FirstTorchFight),
        *_movement_point_steps("Level 2 First Brazier Approach", SOO_LEVEL_2, [Vec2f(-9404.44, -17963.49), Vec2f(-11303.00, -14596.00)], pause_on_combat=True, skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 Brazier Route 1", Level2_BrazierRoute1),
        ("Level 2 Prepare Room 2", Level2_PrepareRoom2),
        *_vanquish_point_steps("Level 2 Route To Room 2 Drop", SOO_LEVEL_2, L2_TO_ROOM2_DROP, clear_area_radius=Range.Area.value, pause_on_combat=True, skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 Drop Torch Before Room 2 Return", Level2_DropTorchBeforeRoom2Return),
        *_vanquish_point_steps("Level 2 Route Back To Room 2 Torch", SOO_LEVEL_2, L2_RETURN_TO_ROOM2_TORCH_PATH, skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 Pick Up Room 2 Torch", Level2_PickupRoom2Torch),
        *_vanquish_point_steps("Level 2 Room 2", SOO_LEVEL_2, L2_ROOM2_PATH, move_tolerance=150.0, skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 Drop Torch Before Final Room 2 Fight", Level2_DropTorchBeforeFinalRoom2Fight),
        *_vanquish_point_steps("Level 2 Room 2 Final Fight", SOO_LEVEL_2, [Vec2f(-4245.2, -2101.0)], skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 Pick Up Torch For Brazier Route 2", Level2_PickupTorchForBrazierRoute2),
        ("Level 2 Brazier Route 2", Level2_BrazierRoute2),
        *_vanquish_point_steps("Level 2 Route To Dungeon Lock", SOO_LEVEL_2, L2_PATH_TO_LOCK, pause_on_combat=True, skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 Open Dungeon Lock", Level2_OpenDungeonLock),
        *_movement_point_steps("Level 2 Exit Route", SOO_LEVEL_2, L2_EXIT_PATH[:-1], pause_on_combat=False, skip_if_in_maps=(SOO_LEVEL_3,)),
        (f"Level 2 Exit Route - Point {len(L2_EXIT_PATH):02d}", Level2_EnterLevel3),

        ("Level 3 Start", Level3_Start),
        *_vanquish_point_steps("Level 3 Main Route", SOO_LEVEL_3, L3_MAIN_PATH),
        *_vanquish_point_steps("Level 3 Brigant Room Route", SOO_LEVEL_3, L3_BRIGANT_ROOM),
        *_movement_point_steps("Level 3 Torch Route", SOO_LEVEL_3, L3_PATH_TO_TORCH, pause_on_combat=False),
        ("Level 3 Torch And Braziers", Level3_TorchAndBraziers),
        ("Level 3 Brigant", Level3_Brigant),
        ("Level 3 Brigant Door", Level3_BrigantDoor),
        *_vanquish_point_steps("Level 3 Route To Fendi", SOO_LEVEL_3, L3_FENDI_PATH),
        ("Level 3 Fendi Boss Fight", Level3_FendiFight),
        ("Level 3 Chest", Level3_Chest),
        ("Collect Reward And Return To Arbor", CollectRewardAndReturnToArbor),
        ("Resolve Shandra Quest", ResolveShandraQuestAfterRun),
        ("Inventory Check And Maintenance", InventoryCheckAndMaintenance),
        ("Prepare Next Dungeon Run", PrepareNextDungeonRun),
    ]

# endregion


def main() -> None:
    global initialized

    if not initialized:
        # Settings binds and loads automatically; no ensure/load lifecycle is
        # required with the new persistence system.
        _load_settings()
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()
    tree.UI.draw_window(icon_path=TEXTURE, iconwidth=96, main_child_dimensions=(420, 380), extra_tabs=[('Statistics', _draw_statistics), ('Config', _draw_run_config)])


# endregion


if __name__ == "__main__":
    main()