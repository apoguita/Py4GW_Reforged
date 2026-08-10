from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import time
from Py4GWCoreLib.Listeners import Listeners
import PySystem
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib import Agent, GLOBAL_CACHE, AgentArray,Player, SharedCommandType
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.enums_src.Player_enums import PlayerStatus
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import CONSET_UPKEEPS, CONSUMABLE_UPKEEPS as ALL_CONSUMABLE_UPKEEPS
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Widgets.System.Messaging import get_inventory_count, reset_inventory_count


PathPoint = Vec2f | tuple[float, float] | tuple[int, int]


# endregion


# region Script metadata

MODULE_NAME = "Shards of Orr BT"
INI_PATH = "Widgets/Automation/Bots/Missions/Dungeons/Shards of Orr BT"
INI_FILENAME = "Shards_of_Orr_BT.ini"


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

# Summoning stones already used by the original SoO script.
SUMMON_MODEL_IDS = (30209, 37810, 31155)

# Standard personal consumables provided by ApoBottingLib.
# The conset IDs are excluded because they have their own settings.
PCON_UPKEEPS = tuple(
    int(model_id)
    for model_id in ALL_CONSUMABLE_UPKEEPS
    if int(model_id) not in CONSET_UPKEEPS
)

CONSET_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple(
    (model_id, 10) for model_id in CONSET_UPKEEPS
)
PCON_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple(
    (model_id, 10) for model_id in PCON_UPKEEPS
)

SUMMON_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple(
    (model_id, 10) for model_id in SUMMON_MODEL_IDS
)

# Final chest drops tracked by the statistics tab.
BDS_MODEL_IDS = tuple(range(1987, 2008))
BDS_MODEL_ID_MIN = BDS_MODEL_IDS[0]
BDS_MODEL_ID_MAX = BDS_MODEL_IDS[-1]
GB_MODEL_ID = 2474

# Inventory maintenance. SharedMemory exposes the four regular inventory bags
# (Backpack, Belt Pouch, Bag 1, Bag 2) and does not include the Equipment Pack.
#
# IMPORTANT: the runtime SharedMemory writer currently reports bag.Size as an
# occupied/item count on these clients instead of the real bag capacity. Using
# bag.Size therefore truncates both free-slot checks and item/kit scans. The
# farming accounts use the fully expanded regular inventory: 55 usable slots.
INVENTORY_BAG_IDS = frozenset((1, 2, 3, 4))
INVENTORY_TOTAL_SLOTS = 55
ID_KIT_MODEL_IDS = (
    int(ModelID.Identification_Kit.value),
    int(ModelID.Superior_Identification_Kit.value),
)
# The SharedProfiles.json SoO profile maintains Expert Salvage Kits because
# exact upgrade extraction requires an upgrade-capable salvage kit.
SALVAGE_KIT_MODEL_IDS = (
    int(ModelID.Expert_Salvage_Kit.value),
)
MERCHANT_RULES_WIDGET_NAME = "MerchantRules"
INVENTORY_PLUS_WIDGET_NAME = "InventoryPlus"
# SharedCommandType.TravelToMap forwards these values to TravelToRegion.
# The BT TravelToRegion wrapper expects a 1-based district and subtracts one
# before calling the low-level Map travel API. District 0 would therefore
# become -1 and Guild Wars rejects it as a closed/invalid region.
INVENTORY_TRAVEL_REGION = 2      # Europe
INVENTORY_TRAVEL_DISTRICT = 1    # Europe English District 1
INVENTORY_TRAVEL_LANGUAGE = 0    # English
INVENTORY_MAINTENANCE_RETRY_COUNT = 2
INVENTORY_SNAPSHOT_SETTLE_MS = 2_000
INVENTORY_TRAVEL_TIMEOUT_MS = 60_000
INVENTORY_MERCHANT_TIMEOUT_MS = 240_000

TEXTURE = os.path.join(
    PySystem.Console.get_projects_path(),
    "Textures", 
    "Module_Icons",
    "BDS.png"
)


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
_settings_ini = Settings(
    f"{INI_PATH}/{INI_FILENAME}",
    "global",
)
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

ARBOR_TO_SHANDRA_PATH = [
    Vec2f(13455.43, 10678.00),
    Vec2f(9850.00, 5025.00),
    Vec2f(11207.11, 1872.32),
    Vec2f(10452.02, 178.50),
    Vec2f(10782.86, -3321.00),
    Vec2f(8360.94, -6550.00),
    Vec2f(10382.85, -12342.00),
    Vec2f(10080.30, -13995.00),
    Vec2f(10667.00, -16116.00),
    Vec2f(10747.49, -17546.00),
    Vec2f(11156.00, -17802.00),
]

LEVEL1_EXIT_TO_ARBOR = Vec2f(-15650.0, 8900.0)

SOO_ENTRANCE_PATH = [
    Vec2f(11177.00, -17683.00),
    Vec2f(10218.00, -18864.00),
    Vec2f(9519.00, -19968.00),
    Vec2f(9240.07, -20260.95),
]

L1_PATH = [
    Vec2f(3720.16, 15370.78),
    Vec2f(6740.06, 11039.32),
    Vec2f(15757, 16952),
    Vec2f(16026.25, 16957.26),
    Vec2f(14255.37, 6189.60)
]

L1_PATH_AFTER_DOOR = [
    Vec2f(17442.40, 2577.83),
    Vec2f(20181.6, 1203.7),
    Vec2f(20400.5, 1300.0),
]

# Level 2 routes / torch mechanics
TORCH_MODEL_IDS = (22341, 22342)
TORCH_BUFF_ID = 2545

L2_BLESSING_NPC = Vec2f(-14076.0, -19457.0)


L2_TORCH_CHEST = Vec2f(-14709.0, -16548.0)
L2_FIRST_TORCH_DROP_POINT_PATH = [
    Vec2f(-11002.0, -17001.0),
]
L2_RETURN_TO_FIRST_TORCH_PATH = [
    Vec2f(-9259.0, -17322.0),
    Vec2f(-9550,-17258),
    Vec2f(-10243,-17780)

]
L2_BRAZIER_PART1 = [
    (-11303.00, -14596.00),
    (-11019.00, -11550.00),
    (-9028.00, -9021.00),
    (-6805.00, -11511.00),
    (-8984.00, -13842.00),
]
L2_CLEANING_PATH = [
    Vec2f(-9011.27, -11536.79),
]
L2_TO_ROOM2_DROP = (Vec2f(-10514.69, -9542.61), Vec2f(-11061.1, -7578.5))
L2_RETURN_TO_ROOM2_TORCH_PATH = [
    Vec2f(-10958.2, -4529.5),
    Vec2f(-11690.64, -3802.55),

]
L2_ROOM2_PATH = [
    Vec2f(-8066.1, -4222.4),
    Vec2f(-7058.8, -4191.0),
]

L2_BRAZIER_PART2 = [
    (-3717.00, -4254.00),
    (-8251.00, -3240.00),
    (-8278.0, -1670.0),
]
L2_AFTER_PART2_POSITION = Vec2f(-5009.49, -2542.30)
L2_PATH_TO_LOCK = [Vec2f(-6798.8, -2436.4),Vec2f(-7063, -2017),Vec2f(-16335.1, -9004.5),(-18700.0, -9171.0)
]
L2_DUNGEON_LOCK = Vec2f(-18725.0, -9171.0)
L2_EXIT_PATH = [
    Vec2f(-18610.0, -8636.0),
    Vec2f(-19254, -8256),
]

# Level 3 routes
L3_ENTRY_BLESSING = Vec2f(17544.0, 18810.0)
L3_MAIN_PATH = [
    Vec2f(16325.98, 15981.14),
    Vec2f(14511, 19206),
    Vec2f(8539, 17072),
    Vec2f(3547, 8795),
    Vec2f(4813.8,10340.7),
    Vec2f(2523,8101),
    Vec2f(1923,6151),
    Vec2f(198,8176),
    Vec2f(-4228,6901),
]
    
    
L3_BRIGANT_ROOM = [
    Vec2f(-4528,6301),
    Vec2f(-8203,2775),
    Vec2f(-11428,3600),
    Vec2f(-7903,6601),
]

L3_PATH_TO_TORCH = [
    Vec2f(-4723.0,6703.0), Vec2f(-1280.0,7880.0),
    Vec2f(3089.73,8511.0), Vec2f(4963.0,9974.0),
    Vec2f(9918.64,19108.0), Vec2f(14709.0,19526.0),
    Vec2f(16111.0,17556.0),
]
L3_TORCH_CHEST = Vec2f(16111.0, 17556.0)
L3_BRAZIERS = [
    (15692.0,17111.0), (12969.0,19842.0), (8236.0,16950.0),
    (5549.0,9920.0), (-536.0,6109.0), (-3814.0,5599.0),
    (-4959.0,7558.0), (-7532.0,4536.0), (-10984.0,486.0),
    (-12621.0,2948.0),
]
L3_FENDI_PATH = [
    Vec2f(-8696, 6323),Vec2f(-9988, 7652), Vec2f(-12712.36, 13502.19),Vec2f(-13198.79, 13789.36)
]
FENDI_CHEST_POSITION = (-15800.98, 16901.23)
FENDI_CHEST_GADGET_ID = 8934

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
    _keep_torch_for_caster = _settings_ini.get_bool(
        _SETTINGS_SECTION,
        "KeepTorchForCaster",
        True,
    )
    _inventory_maintenance_enabled = _settings_ini.get_bool(
        _SETTINGS_SECTION,
        "InventoryMaintenanceEnabled",
        True,
    )
    _inventory_min_free_slots = max(
        0,
        _settings_ini.get_int(_SETTINGS_SECTION, "InventoryMinFreeSlots", 5),
    )
    _inventory_min_id_kits = max(
        0,
        _settings_ini.get_int(_SETTINGS_SECTION, "InventoryMinIdKits", 1),
    )
    _inventory_min_salvage_kits = max(
        0,
        _settings_ini.get_int(
            _SETTINGS_SECTION,
            "InventoryMinSalvageKits",
            2,
        ),
    )
    _settings_loaded = True
    _load_statistics()


def _save_settings() -> None:
    _settings_ini.set(_SETTINGS_SECTION, "HardMode", _use_hard_mode)
    _settings_ini.set(_SETTINGS_SECTION, "RestockConset", _restock_conset)
    _settings_ini.set(_SETTINGS_SECTION, "ActivateConset", _activate_conset)
    _settings_ini.set(_SETTINGS_SECTION, "RestockPcons", _restock_pcons)
    _settings_ini.set(_SETTINGS_SECTION, "ActivatePcons", _activate_pcons)
    _settings_ini.set(_SETTINGS_SECTION, "UseSummoningStone", _use_summoning_stone)
    _settings_ini.set(
        _SETTINGS_SECTION,
        "KeepTorchForCaster",
        _keep_torch_for_caster,
    )
    _settings_ini.set(
        _SETTINGS_SECTION,
        "InventoryMaintenanceEnabled",
        _inventory_maintenance_enabled,
    )
    _settings_ini.set(
        _SETTINGS_SECTION,
        "InventoryMinFreeSlots",
        _inventory_min_free_slots,
    )
    _settings_ini.set(
        _SETTINGS_SECTION,
        "InventoryMinIdKits",
        _inventory_min_id_kits,
    )
    _settings_ini.set(
        _SETTINGS_SECTION,
        "InventoryMinSalvageKits",
        _inventory_min_salvage_kits,
    )


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

    for key in _settings_ini.items(_BDS_DROPS_SECTION).keys():
        _bds_drops[key] = _settings_ini.get_int(_BDS_DROPS_SECTION, key, 0)

    for key in _settings_ini.items(_GB_DROPS_SECTION).keys():
        _gb_drops[key] = _settings_ini.get_int(_GB_DROPS_SECTION, key, 0)

    for seed_section in (
        _BDS_SNAPSHOT_SECTION,
        _BDS_RUN_SECTION,
        _GB_SNAPSHOT_SECTION,
        _GB_RUN_SECTION,
    ):
        for key in _settings_ini.items(seed_section).keys():
            _bds_drops.setdefault(key, 0)
            _gb_drops.setdefault(key, 0)

    for key in _settings_ini.items(_CHAR_NAMES_SECTION).keys():
        name = str(
            _settings_ini.get_str(_CHAR_NAMES_SECTION, key, "") or ""
        ).strip()
        if name:
            _char_names[key] = name

    _statistics_loaded = True


def _save_statistics() -> None:
    section = _STATS_SECTION
    _settings_ini.set(section, "total_runs", _total_runs)
    _settings_ini.set(section, "total_run_time", _total_run_time)
    _settings_ini.set(
        section,
        "fastest_run",
        0.0 if _fastest_run == float("inf") else _fastest_run,
    )
    _settings_ini.set(section, "slowest_run", _slowest_run)

    for floor, total, fastest, slowest in (
        ("l1", _l1_total_time, _l1_fastest, _l1_slowest),
        ("l2", _l2_total_time, _l2_fastest, _l2_slowest),
        ("l3", _l3_total_time, _l3_fastest, _l3_slowest),
    ):
        _settings_ini.set(section, f"{floor}_total_time", total)
        _settings_ini.set(
            section,
            f"{floor}_fastest",
            0.0 if fastest == float("inf") else fastest,
        )
        _settings_ini.set(section, f"{floor}_slowest", slowest)

    for key, total in _bds_drops.items():
        _settings_ini.set(_BDS_DROPS_SECTION, key, total)

    for key, total in _gb_drops.items():
        _settings_ini.set(_GB_DROPS_SECTION, key, total)

    for key, name in _char_names.items():
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

    return tuple(
        dict.fromkeys(
            int(model_id)
            for model_id in enabled
        )
    )


def _configure_runtime_upkeeps(
    *,
    consumables_enabled: bool | None = None,
) -> None:
    global _runtime_consumables_enabled

    if consumables_enabled is not None:
        _runtime_consumables_enabled = bool(consumables_enabled)

    if botting_tree is None:
        return

    botting_tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=(
            _enabled_consumable_upkeeps()
            if _runtime_consumables_enabled
            else ()
        ),
        heroai_state_logging=False,
    )


def _runtime_consumable_upkeep_node(
    enabled: bool,
) -> BehaviorTree:
    """Enable or suspend conset and pcon upkeep at runtime."""

    def _apply(
        _node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        if botting_tree is None:
            return BehaviorTree.NodeState.FAILURE

        if _runtime_consumables_enabled != bool(enabled):
            _configure_runtime_upkeeps(
                consumables_enabled=enabled,
            )
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "Consumable upkeep resumed for the dungeon run."
                    if enabled
                    else (
                        "Consumable upkeep suspended during the "
                        "end-of-dungeon return sequence."
                    )
                ),
                PySystem.Console.MessageType.Info,
            )

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=(
                "Resume Consumable Upkeep"
                if enabled
                else "Suspend Consumable Upkeep"
            ),
            action_fn=_apply,
            aftercast_ms=0,
        )
    )



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

    value = PyImGui.checkbox(
        "Hard Mode (HM)",
        _use_hard_mode,
    )
    if value != _use_hard_mode:
        _use_hard_mode = value
        changed = True

    PyImGui.separator()
    PyImGui.text("Conset")

    value = PyImGui.checkbox(
        "Restock conset from storage",
        _restock_conset,
    )
    if value != _restock_conset:
        _restock_conset = value
        changed = True

    value = PyImGui.checkbox(
        "Activate / maintain conset",
        _activate_conset,
    )
    if value != _activate_conset:
        _activate_conset = value
        changed = True
        upkeep_changed = True

    PyImGui.separator()
    PyImGui.text("Personal consumables")

    value = PyImGui.checkbox(
        "Restock pcons from storage",
        _restock_pcons,
    )
    if value != _restock_pcons:
        _restock_pcons = value
        changed = True

    value = PyImGui.checkbox(
        "Activate / maintain pcons",
        _activate_pcons,
    )
    if value != _activate_pcons:
        _activate_pcons = value
        changed = True
        upkeep_changed = True

    PyImGui.separator()
    PyImGui.text("Summoning stones")

    value = PyImGui.checkbox(
        "Use summoning stones",
        _use_summoning_stone,
    )
    if value != _use_summoning_stone:
        _use_summoning_stone = value
        changed = True
        upkeep_changed = True

    PyImGui.separator()
    PyImGui.text("Torch handling")

    value = PyImGui.checkbox(
        "Keep torch for caster builds",
        _keep_torch_for_caster,
    )
    if value != _keep_torch_for_caster:
        _keep_torch_for_caster = value
        _drop_torch_for_combat = None
        changed = True

    PyImGui.separator()
    PyImGui.text("Inventory maintenance")

    value = PyImGui.checkbox(
        "Run MerchantRules when inventory is low",
        _inventory_maintenance_enabled,
    )
    if value != _inventory_maintenance_enabled:
        _inventory_maintenance_enabled = value
        changed = True

    if _inventory_maintenance_enabled:
        value = PyImGui.input_int(
            "Minimum free slots",
            _inventory_min_free_slots,
        )
        value = max(0, int(value))
        if value != _inventory_min_free_slots:
            _inventory_min_free_slots = value
            changed = True

        value = PyImGui.input_int(
            "Minimum ID kits (0 = disabled)",
            _inventory_min_id_kits,
        )
        value = max(0, int(value))
        if value != _inventory_min_id_kits:
            _inventory_min_id_kits = value
            changed = True

        value = PyImGui.input_int(
            "Minimum salvage kits (0 = disabled)",
            _inventory_min_salvage_kits,
        )
        value = max(0, int(value))
        if value != _inventory_min_salvage_kits:
            _inventory_min_salvage_kits = value
            changed = True

        PyImGui.text_wrapped(
            "MerchantRules executes the currently loaded Shards of Orr profile "
            "from SharedProfiles.json. Maintenance is performed directly in Vlox's Falls. "
            "If maintenance is requested from an explorable area, all accounts first return "
            "to Vlox's Falls. The four regular inventory bags are checked using the confirmed "
            "55-slot capacity; Equipment Pack is excluded."
        )

    if changed:
        _save_settings()

    if upkeep_changed:
        _configure_runtime_upkeeps()


def _runtime_difficulty_node() -> BehaviorTree:
    return BT.Subtree(
        name="Apply Selected Difficulty",
        subtree_fn=lambda _node: BT.SetHardMode(_use_hard_mode, log=True),
    )


def _runtime_restock_node() -> BehaviorTree:
    def _build(
        _node: BehaviorTree.Node,
    ) -> BehaviorTree:
        items: list[tuple[int, int]] = []

        if _restock_conset:
            items.extend(CONSET_RESTOCK_ITEMS)

        if _restock_pcons:
            items.extend(PCON_RESTOCK_ITEMS)

        if _use_summoning_stone:
            items.extend(SUMMON_RESTOCK_ITEMS)

        if not items:
            return BT.Succeeder(
                "RestockDisabled"
            )

        return BT.RestockItemsFromList(
            tuple(items),
            allow_missing=True,
        )

    return BT.Subtree(
        name="Restock Selected Consumables",
        subtree_fn=_build,
    )


# endregion


# region Statistics


def _account_key(email: str) -> str:
    return str(email).replace("@", "_at_").replace(".", "_")


def _display_email(key: str) -> str:
    return str(key).replace("_at_", "@").replace("_", ".")


def _known_account_keys() -> list[str]:
    return sorted(
        set(_bds_drops)
        | set(_gb_drops)
        | set(_session_bds)
        | set(_session_gb)
    )


def _account_label(key: str) -> str:
    if not _scramble_accounts:
        return _char_names.get(key) or _display_email(key)

    keys = _known_account_keys()
    index = keys.index(key) + 1 if key in keys else 0
    return f"Player {index}"


def _shared_accounts() -> list[object]:
    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(
            sort_results=False,
            include_isolated=True,
        )
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
    character_name = str(
        getattr(agent_data, "CharacterName", "") or ""
    ).strip()
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
    return (
        int(getattr(map_data, "MapID", 0) or 0),
        int(getattr(map_data, "Region", 0) or 0),
        int(getattr(map_data, "District", 0) or 0),
        int(getattr(map_data, "Language", 0) or 0),
    )


def _iter_shared_inventory_slots(account: object):
    """Yield every shared-memory slot from the four regular inventory bags.

    Do not use bag.Size here. On the current multibox SharedMemory runtime that
    field behaves like an occupied/item count rather than the real bag capacity,
    which can hide valid slots and items located after that index.
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


def _shared_inventory_capacity(account: object) -> int:
    inventory_bags = getattr(account, "InventoryBags", None)
    if inventory_bags is None:
        return 0

    # The four regular inventory bags are mirrored by InventoryBagsStruct; the
    # Equipment Pack is not part of this snapshot. Capacity is fixed to the
    # fully expanded 55-slot setup used by the SoO farming accounts.
    return INVENTORY_TOTAL_SLOTS


def _shared_inventory_occupied_slots(account: object) -> int:
    occupied = 0
    for _bag_id, slot in _iter_shared_inventory_slots(account):
        if (
            int(getattr(slot, "ModelID", 0) or 0) > 0
            and int(getattr(slot, "Quantity", 0) or 0) > 0
        ):
            occupied += 1
    return occupied


def _shared_inventory_free_slots(account: object) -> int:
    capacity = _shared_inventory_capacity(account)
    if capacity <= 0:
        return 0
    occupied = _shared_inventory_occupied_slots(account)
    return max(0, capacity - occupied)


def _shared_inventory_model_count(
    account: object,
    model_ids: Sequence[int],
) -> int:
    wanted = {int(model_id) for model_id in model_ids}
    total = 0
    for _bag_id, slot in _iter_shared_inventory_slots(account):
        model_id = int(getattr(slot, "ModelID", 0) or 0)
        quantity = int(getattr(slot, "Quantity", 0) or 0)
        if model_id in wanted and quantity > 0:
            total += quantity
    return total

def _inventory_maintenance_issues() -> list[str]:
    issues: list[str] = []
    accounts = _inventory_accounts()
    if not accounts:
        return ["No active account inventory snapshot is available."]

    for account in accounts:
        label = _shared_account_label(account)
        capacity = _shared_inventory_capacity(account)
        if capacity <= 0:
            issues.append(f"{label}: inventory snapshot unavailable")
            continue

        free_slots = _shared_inventory_free_slots(account)
        id_kits = _shared_inventory_model_count(account, ID_KIT_MODEL_IDS)
        salvage_kits = _shared_inventory_model_count(
            account,
            SALVAGE_KIT_MODEL_IDS,
        )

        account_issues: list[str] = []
        if (
            _inventory_min_free_slots > 0
            and free_slots < _inventory_min_free_slots
        ):
            account_issues.append(
                f"free slots {free_slots}/{_inventory_min_free_slots}"
            )
        if _inventory_min_id_kits > 0 and id_kits < _inventory_min_id_kits:
            account_issues.append(
                f"ID kits {id_kits}/{_inventory_min_id_kits}"
            )
        if (
            _inventory_min_salvage_kits > 0
            and salvage_kits < _inventory_min_salvage_kits
        ):
            account_issues.append(
                f"salvage kits {salvage_kits}/{_inventory_min_salvage_kits}"
            )

        if account_issues:
            issues.append(f"{label}: {', '.join(account_issues)}")

    return issues


def _inventory_model_label(model_id: int) -> str:
    try:
        return str(ModelID(int(model_id)).name)
    except Exception:
        return f"model_{int(model_id)}"


def _log_unhealthy_inventory_contents() -> None:
    """Log the four regular inventory bags for accounts that still fail maintenance thresholds.

    Shared-memory inventory snapshots expose only bag/slot/model/quantity here,
    so this diagnostic intentionally avoids any live item-name lookup.  That also
    keeps it independent from the currently broken Agent name-resolution path.
    """
    for account in _inventory_accounts():
        capacity = _shared_inventory_capacity(account)
        if capacity <= 0:
            continue

        free_slots = _shared_inventory_free_slots(account)
        id_kits = _shared_inventory_model_count(account, ID_KIT_MODEL_IDS)
        salvage_kits = _shared_inventory_model_count(account, SALVAGE_KIT_MODEL_IDS)
        unhealthy = (
            (_inventory_min_free_slots > 0 and free_slots < _inventory_min_free_slots)
            or (_inventory_min_id_kits > 0 and id_kits < _inventory_min_id_kits)
            or (
                _inventory_min_salvage_kits > 0
                and salvage_kits < _inventory_min_salvage_kits
            )
        )
        if not unhealthy:
            continue

        label = _shared_account_label(account)
        entries: list[str] = []
        for bag_id, slot in _iter_shared_inventory_slots(account):
            model_id = int(getattr(slot, "ModelID", 0) or 0)
            quantity = int(getattr(slot, "Quantity", 0) or 0)
            if model_id <= 0 or quantity <= 0:
                continue
            slot_no = int(getattr(slot, "Slot", 0) or 0)
            entries.append(
                f"B{bag_id}:S{slot_no} "
                f"{_inventory_model_label(model_id)}({model_id}) x{quantity}"
            )

        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"[Inventory diagnostic] {label}: free={free_slots}/{capacity}, "
                f"ID kits={id_kits}, Expert salvage kits={salvage_kits}, "
                f"occupied slots={len(entries)}."
            ),
            PySystem.Console.MessageType.Warning,
        )
        if not entries:
            continue
        chunk_size = 8
        for start in range(0, len(entries), chunk_size):
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Inventory diagnostic] {label}: "
                + " | ".join(entries[start : start + chunk_size]),
                PySystem.Console.MessageType.Info,
            )


def _inventory_is_healthy_node(
    name: str,
    *,
    log_success: bool = True,
) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        issues = _inventory_maintenance_issues()
        if issues:
            PySystem.Console.Log(
                MODULE_NAME,
                "Inventory maintenance required - " + "; ".join(issues),
                PySystem.Console.MessageType.Warning,
            )
            return BehaviorTree.NodeState.FAILURE

        if log_success:
            PySystem.Console.Log(
                MODULE_NAME,
                "Inventory check passed on every active account.",
                PySystem.Console.MessageType.Success,
            )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=name,
            condition_fn=_check,
        )
    )


def _wait_for_inventory_snapshots(
    *,
    name: str,
    timeout_ms: int = 10_000,
) -> BehaviorTree:
    state_key = f"__inventory_snapshot_wait_started_{name}"

    def _wait(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        started_at = float(node.blackboard.get(state_key, 0.0) or 0.0)
        if started_at <= 0.0:
            started_at = time.monotonic()
            node.blackboard[state_key] = started_at

        accounts = _inventory_accounts()
        if accounts and all(
            _shared_inventory_capacity(account) > 0
            for account in accounts
        ):
            node.blackboard.pop(state_key, None)
            return BehaviorTree.NodeState.SUCCESS

        elapsed_ms = int((time.monotonic() - started_at) * 1000.0)
        if elapsed_ms < max(0, int(timeout_ms)):
            return BehaviorTree.NodeState.RUNNING

        PySystem.Console.Log(
            MODULE_NAME,
            (
                "Some inventory snapshots are still unavailable after "
                f"{elapsed_ms} ms. Continuing with the safe maintenance path."
            ),
            PySystem.Console.MessageType.Warning,
        )
        node.blackboard.pop(state_key, None)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_wait,
            aftercast_ms=0,
        )
    )


def _all_accounts_on_map(map_id: int) -> bool:
    accounts = _inventory_accounts()
    return bool(accounts) and all(
        _shared_account_map_id(account) == int(map_id)
        for account in accounts
    )


def _all_accounts_on_map_instance(
    map_id: int,
    region: int,
    district: int,
    language: int,
) -> bool:
    expected = (int(map_id), int(region), int(district), int(language))
    accounts = _inventory_accounts()
    return bool(accounts) and all(
        _shared_account_map_instance(account) == expected
        for account in accounts
    )


def _all_accounts_on_map_node(map_id: int, name: str) -> BehaviorTree:
    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=name,
            condition_fn=lambda _node: _all_accounts_on_map(map_id),
        )
    )


def _wait_for_all_accounts_on_map(
    map_id: int,
    *,
    name: str,
    timeout_ms: int = INVENTORY_TRAVEL_TIMEOUT_MS,
) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _all_accounts_on_map(map_id):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name=name,
            condition_fn=_check,
            throttle_interval_ms=500,
            timeout_ms=timeout_ms,
        )
    )


def _wait_for_all_accounts_on_inventory_instance(
    map_id: int,
    *,
    name: str,
    timeout_ms: int = INVENTORY_TRAVEL_TIMEOUT_MS,
) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _all_accounts_on_map_instance(
            map_id,
            INVENTORY_TRAVEL_REGION,
            INVENTORY_TRAVEL_DISTRICT,
            INVENTORY_TRAVEL_LANGUAGE,
        ):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name=name,
            condition_fn=_check,
            throttle_interval_ms=500,
            timeout_ms=timeout_ms,
        )
    )


def _send_widget_state(
    widget_name: str,
    *,
    enabled: bool,
    refs_key: str,
) -> BehaviorTree:
    return BTShared.SendAndWait(
        command=(
            SharedCommandType.EnableWidget
            if enabled
            else SharedCommandType.DisableWidget
        ),
        extra_data=(widget_name, "", "", ""),
        include_self=True,
        refs_blackboard_key=refs_key,
        timeout_ms=20_000,
        poll_interval_ms=100,
        log=True,
    )


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

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=(
                "Enable Local Auto Inventory Handler"
                if enabled
                else "Disable Local Auto Inventory Handler"
            ),
            action_fn=_set,
            aftercast_ms=0,
        )
    )


def _travel_all_accounts_to_vlox(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(
        name="Travel Every Account To Vlox's Falls",
        children=[
            BTShared.SendAndWait(
                command=SharedCommandType.TravelToMap,
                params=(
                    float(VLOXS_FALL),
                    float(INVENTORY_TRAVEL_REGION),
                    float(INVENTORY_TRAVEL_DISTRICT),
                    float(INVENTORY_TRAVEL_LANGUAGE),
                ),
                include_self=True,
                refs_blackboard_key=f"{attempt_key}_travel_vlox_refs",
                timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
                poll_interval_ms=250,
                log=True,
            ),
            _wait_for_all_accounts_on_inventory_instance(
                VLOXS_FALL,
                name="Wait For Every Account In Vlox's Falls EU-English-1",
            ),
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
            BT.Resign(
                wait_for_map_load=True,
                target_map_id=VLOXS_FALL,
                multi_account=True,
                timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
                log=True,
            ),
            _wait_for_all_accounts_on_map(
                VLOXS_FALL,
                name="Wait For Party Return To Vlox's Falls",
            ),
        ],
    )

    return BT.Selector(
        name="Ensure Every Account Is In Vlox's Falls",
        children=[
            _all_accounts_on_map_node(
                VLOXS_FALL,
                "Every Account Already In Vlox's Falls",
            ),
            resign_from_explorable,
            _travel_all_accounts_to_vlox(attempt_key),
        ],
    )


def _restore_inventoryplus_after_merchant(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(
        name="Restore InventoryPlus After MerchantRules",
        children=[
            _send_widget_state(
                INVENTORY_PLUS_WIDGET_NAME,
                enabled=True,
                refs_key=f"{attempt_key}_enable_inventoryplus_refs",
            ),
            _set_local_auto_inventory_handler(True),
        ],
    )


def _run_merchant_rules(attempt_key: str) -> BehaviorTree:
    request_id = f"soo_inventory_{attempt_key}_{int(time.monotonic() * 1000)}"
    execute = BTShared.SendAndWait(
        command=SharedCommandType.MerchantRules,
        # Opcode 3 = Execute.  The Shards of Orr rules now live entirely in
        # SharedProfiles.json, so no temporary preset or transient protection
        # options are sent with the request.
        params=(3.0, 0.0, 0.0, 0.0),
        extra_data=(request_id, "", "0", "0"),
        include_self=True,
        refs_blackboard_key=f"{attempt_key}_merchant_rules_refs",
        timeout_ms=INVENTORY_MERCHANT_TIMEOUT_MS,
        poll_interval_ms=250,
        log=True,
    )

    # InventoryPlus must always be restored, including after a MerchantRules
    # dispatch timeout.  The fallback restores it and then deliberately fails
    # so the outer retry selector can start a clean second attempt.
    return BT.Selector(
        name="Execute MerchantRules And Restore InventoryPlus",
        children=[
            BT.Sequence(
                name="MerchantRules Completed",
                children=[
                    execute,
                    _restore_inventoryplus_after_merchant(attempt_key),
                ],
            ),
            BT.Sequence(
                name="Restore InventoryPlus After MerchantRules Failure",
                children=[
                    _restore_inventoryplus_after_merchant(
                        f"{attempt_key}_failure"
                    ),
                    BehaviorTree(
                        BehaviorTree.FailerNode(
                            name="Propagate MerchantRules Failure"
                        )
                    ),
                ],
            ),
        ],
    )


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
            BT.LogMessage(
                message=(
                    f"Inventory maintenance attempt {attempt_number}/"
                    f"{INVENTORY_MAINTENANCE_RETRY_COUNT} in Vlox's Falls."
                ),
                module_name=MODULE_NAME,
            ),
            _set_local_auto_inventory_handler(False),
            _send_widget_state(
                INVENTORY_PLUS_WIDGET_NAME,
                enabled=False,
                refs_key=f"{attempt_key}_disable_inventoryplus_refs",
            ),
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                enabled=True,
                refs_key=f"{attempt_key}_enable_merchant_rules_refs",
            ),
            BT.Wait(1_000),
            _run_merchant_rules(attempt_key),
            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
            _inventory_is_healthy_node(
                f"Verify Inventory After Attempt {attempt_number}",
                log_success=True,
            ),
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
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "Inventory maintenance failed twice. The bot was paused "
                    f"safely. Remaining issue(s): {issue_text}"
                ),
                PySystem.Console.MessageType.Error,
            )
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
                receiver_email = str(
                    getattr(account, "AccountEmail", "") or ""
                ).strip()
                if not sender_email or not receiver_email:
                    continue
                GLOBAL_CACHE.ShMem.SendMessage(
                    sender_email,
                    receiver_email,
                    SharedCommandType.EnableWidget,
                    (0.0, 0.0, 0.0, 0.0),
                    (INVENTORY_PLUS_WIDGET_NAME, "", "", ""),
                )

            if botting_tree is not None:
                fn = getattr(botting_tree, "Pause", None)
                if callable(fn):
                    try:
                        fn(True)
                    except Exception:
                        pass

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Pause Bot After Inventory Maintenance Failure",
            action_fn=_stop,
            aftercast_ms=0,
        )
    )


def InventoryCheckAndMaintenance() -> BehaviorTree:
    disabled = BehaviorTree(
        BehaviorTree.ConditionNode(
            name="Inventory Maintenance Disabled",
            condition_fn=lambda _node: not _inventory_maintenance_enabled,
        )
    )

    maintenance_attempts = [
        _inventory_maintenance_attempt(attempt_number)
        for attempt_number in range(1, INVENTORY_MAINTENANCE_RETRY_COUNT + 1)
    ]
    maintenance_attempts.append(_stop_for_inventory_failure_node())

    enabled_flow = BT.Sequence(
        name="Enabled Inventory Check And Maintenance",
        children=[
            _wait_for_inventory_snapshots(
                name="Wait For Multibox Inventory Snapshots",
            ),
            BT.Selector(
                name="Check Inventory Thresholds",
                children=[
                    _inventory_is_healthy_node(
                        "Inventory Thresholds Already Satisfied",
                        log_success=True,
                    ),
                    BT.Sequence(
                        name="Run Inventory Maintenance",
                        children=[
                            BT.LogMessage(
                                message=(
                                    "Inventory thresholds are not satisfied. "
                                    "Starting multibox MerchantRules maintenance "
                                    "with the loaded Shards of Orr profile in Vlox's Falls."
                                ),
                                module_name=MODULE_NAME,
                            ),
                            # Ensure every account is in Vlox once, then keep both
                            # MerchantRules attempts there. No maintenance travel is
                            # needed when the bot already starts in Vlox's Falls.
                            _return_all_accounts_to_vlox("inventory_maintenance_setup"),
                            BT.LeaveParty(),
                            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
                            BT.Selector(
                                name="Retry Inventory Maintenance In Vlox's Falls",
                                children=maintenance_attempts,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    return BT.Selector(
        name="Inventory Check And Maintenance",
        children=[
            disabled,
            enabled_flow,
        ],
    )


def StartupInventoryCheck() -> BehaviorTree:
    return BT.Selector(
        name="Startup Inventory Check",
        children=[
            BT.Sequence(
                name="Check Inventories Before Leaving Vlox's Falls",
                children=[
                    BT.IsCurrentMap(map_id=VLOXS_FALL, log=False),
                    InventoryCheckAndMaintenance(),
                ],
            ),
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


def _statistics_action_node(
    name: str,
    action: Callable[[], None],
) -> BehaviorTree:
    def _run(
        _node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
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

    return _statistics_action_node(
        "Mark Run Start",
        _mark,
    )


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

    return _statistics_action_node(
        "Mark Level 2 Start",
        _mark,
    )


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

    return _statistics_action_node(
        "Mark Level 3 Start",
        _mark,
    )


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

    return _statistics_action_node(
        "Record Successful Run",
        _record,
    )


def _accumulate_drop(
    account_key: str,
    count: int,
    all_time: dict[str, int],
    session: dict[str, int],
) -> None:
    all_time.setdefault(account_key, 0)
    if count <= 0:
        return
    all_time[account_key] += int(count)
    session[account_key] = session.get(account_key, 0) + int(count)


def _inventory_count(
    model_id_min: int,
    model_id_max: int,
) -> int:
    return sum(
        int(GLOBAL_CACHE.Inventory.GetModelCount(model_id))
        for model_id in range(
            int(model_id_min),
            int(model_id_max) + 1,
        )
    )


def _inventory_statistics_node(
    *,
    after_chest: bool,
) -> BehaviorTree:
    node_name = (
        "Record Drops After Final Chest"
        if after_chest
        else "Snapshot Inventories At Dungeon Entry"
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
        bds_section = (
            _BDS_RUN_SECTION
            if after_chest
            else _BDS_SNAPSHOT_SECTION
        )
        gb_section = (
            _GB_RUN_SECTION
            if after_chest
            else _GB_SNAPSHOT_SECTION
        )

        bds_count = _inventory_count(
            BDS_MODEL_ID_MIN,
            BDS_MODEL_ID_MAX,
        )
        gb_count = _inventory_count(
            GB_MODEL_ID,
            GB_MODEL_ID,
        )
        _settings_ini.set(bds_section, local_key, bds_count)
        _settings_ini.set(gb_section, local_key, gb_count)

        account_keys = [local_key]
        requests: list[dict[str, object]] = []
        for account in _shared_accounts():
            email = str(
                getattr(account, "AccountEmail", "") or ""
            ).strip()
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

    def _finish() -> None:
        if not after_chest:
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "[Statistics] Dungeon-entry inventory snapshot "
                    f"completed for {len(state['account_keys'])} account(s)."
                ),
                PySystem.Console.MessageType.Info,
            )
            _save_statistics()
            return

        total_bds = 0
        total_gb = 0
        for key in state["account_keys"]:
            account_key = str(key)
            bds_before = _settings_ini.get_int(
                _BDS_SNAPSHOT_SECTION,
                account_key,
                -1,
            )
            bds_after = _settings_ini.get_int(
                _BDS_RUN_SECTION,
                account_key,
                -1,
            )
            bds_delta = (
                max(0, bds_after - bds_before)
                if bds_before >= 0 and bds_after >= 0
                else 0
            )
            _accumulate_drop(
                account_key,
                bds_delta,
                _bds_drops,
                _session_bds,
            )
            total_bds += bds_delta

            gb_before = _settings_ini.get_int(
                _GB_SNAPSHOT_SECTION,
                account_key,
                -1,
            )
            gb_after = _settings_ini.get_int(
                _GB_RUN_SECTION,
                account_key,
                -1,
            )
            gb_delta = (
                max(0, gb_after - gb_before)
                if gb_before >= 0 and gb_after >= 0
                else 0
            )
            _accumulate_drop(
                account_key,
                gb_delta,
                _gb_drops,
                _session_gb,
            )
            total_gb += gb_delta

        _save_statistics()
        PySystem.Console.Log(
            MODULE_NAME,
            (
                "[Statistics] Final chest recorded - "
                f"BDS {total_bds} | Glacial Blades {total_gb}"
            ),
            PySystem.Console.MessageType.Success,
        )

    def _tick(
        node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
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
                _start()

            requests = state["requests"]
            while int(state["request_index"]) < len(requests):
                request_index = int(state["request_index"])
                request = requests[request_index]
                email = str(request["email"])
                model_min = int(request["model_min"])
                model_max = int(request["model_max"])

                if not bool(state["waiting"]):
                    reset_inventory_count(
                        email,
                        model_min,
                        model_max,
                    )
                    _settings_ini.set(
                        str(request["section"]),
                        str(request["key"]),
                        -1,
                    )
                    GLOBAL_CACHE.ShMem.SendMessage(
                        str(state["local_email"]),
                        email,
                        SharedCommandType.InventoryQuery,
                        (
                            float(model_min),
                            float(model_max),
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
                        model_min,
                        model_max,
                    )
                )
                if count >= 0:
                    _settings_ini.set(
                        str(request["section"]),
                        str(request["key"]),
                        count,
                    )
                    state["request_index"] = request_index + 1
                    state["waiting"] = False
                    continue

                elapsed_ms = (
                    time.monotonic()
                    - float(state["request_started_at"])
                ) * 1000.0
                if elapsed_ms >= _INVENTORY_QUERY_TIMEOUT_MS:
                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            "[Statistics] Inventory query timed out for "
                            f"{request['label']} on "
                            f"{_account_label(str(request['key']))}."
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


def _draw_statistics() -> None:
    import PyImGui
    from Py4GWCoreLib import Color, ImGui

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

    PyImGui.text_colored("Shards of Orr Statistics", gold)
    PyImGui.separator()
    PyImGui.spacing()

    _scramble_accounts = PyImGui.checkbox(
        "Hide Account Names",
        _scramble_accounts,
    )

    session_bds = sum(_session_bds.values())
    session_gb = sum(_session_gb.values())
    total_bds = sum(_bds_drops.values())
    total_gb = sum(_gb_drops.values())

    PyImGui.text_colored("Session Overview", cyan)
    if PyImGui.begin_table("##soo_bt_session", 3, table_flags):
        for label in ("Runs", "BDS", "GB"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                column_width,
            )
        _header_row(("Runs", "BDS", "GB"))
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(
            (_session_runs, session_bds, session_gb)
        ):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Total Overview", cyan)
    if PyImGui.begin_table("##soo_bt_all_time", 5, table_flags):
        for label in ("Runs", "BDS", "BDS Avg", "GB", "GB Avg"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                column_width,
            )
        _header_row(("Runs", "BDS", "BDS Avg", "GB", "GB Avg"))
        values = (
            _total_runs,
            str(total_bds),
            _runs_per_drop(_total_runs, total_bds),
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
    if PyImGui.begin_table("##soo_bt_timings", 5, table_flags):
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
            PyImGui.text(
                _runs_per_drop(_total_runs, all_time_count)
            )

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

_MARTIAL_PRIMARY_PROFESSIONS = {
    "Warrior",
    "Ranger",
    "Assassin",
    "Dervish",
    "Paragon",
}


def _is_holding_bundle() -> bool:
    try:
        return bool(
            Agent.IsHoldingItem(
                Player.GetAgentID(),
            )
        )
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

    PySystem.Console.Log(
        MODULE_NAME,
        (
            "Torch combat policy: "
            f"{'DROP' if _drop_torch_for_combat else 'KEEP'} "
            f"({reason})."
        ),
        PySystem.Console.MessageType.Info,
    )
    return _drop_torch_for_combat


def ResolveTorchCombatPolicy() -> BehaviorTree:
    def _resolve() -> BehaviorTree.NodeState:
        _resolve_torch_combat_policy()
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="ResolveTorchCombatPolicy",
            action_fn=_resolve,
            aftercast_ms=0,
        )
    )


def DropTorchForCombat(log: bool = False) -> BehaviorTree:
    """Drop the torch only when the configured combat policy requires it."""

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not _resolve_torch_combat_policy():
            return BT.Succeeder(
                "KeepTorchForCasterCombat",
            )

        if not _is_holding_bundle():
            return BT.Succeeder(
                "NoTorchBundleToDrop",
            )

        return BT.DropBundle(log=log)

    return BT.Subtree(
        name="Drop Torch For Combat If Required",
        subtree_fn=_build,
    )


def ResetTorchCombatPolicy() -> BehaviorTree:
    def _reset() -> BehaviorTree.NodeState:
        global _drop_torch_for_combat
        _drop_torch_for_combat = None
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="ResetTorchCombatPolicy",
            action_fn=_reset,
            aftercast_ms=0,
        )
    )


def PickupTorch() -> BehaviorTree:
    PICKUP_TIMEOUT_MS = 45_000
    NOT_FOUND_GRACE_MS = 3_000
    RETRY_DELAY_MS = 1_000

    def _create_pickup_tree() -> BehaviorTree:
        return BT.PickupGroundItemByModelID(
            model_ids=TORCH_MODEL_IDS,
            max_distance=200_000.0,
            timeout_ms=PICKUP_TIMEOUT_MS,
            allow_unassigned=True,
            interaction_interval_ms=1000,
            aftercast_ms=100,
            log=False,
        )

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

                owner_id = int(
                    Agent.GetItemAgentOwnerID(agent_id)
                    or 0
                )
                if owner_id not in (0, local_player_id):
                    continue

                item_id = int(
                    Agent.GetItemAgentItemID(agent_id)
                    or 0
                )
                if item_id <= 0:
                    continue

                model_id = int(
                    GLOBAL_CACHE.Item.GetModelID(item_id)
                    or 0
                )
                if model_id in TORCH_MODEL_IDS:
                    return agent_id

            return 0
        except Exception:
            # Preserve the existing pickup behavior if the preliminary scan
            # itself is temporarily unavailable.
            return None

    def _log(
        message: str,
        message_type: PySystem.Console.MessageType,
    ) -> None:
        PySystem.Console.Log(
            "PickupTorch",
            message,
            message_type,
        )

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

    def _pickup_torch_step(
        node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
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
            _log(
                "Looking for a torch...",
                PySystem.Console.MessageType.Info,
            )
            search_logged = True

        elapsed_ms = int(
            (now - started_at) * 1000.0
        )

        if not torch_seen:
            torch_agent_id = _find_available_torch()

            if torch_agent_id is None:
                # The preliminary scan failed. Let the established pickup
                # routine perform its own search rather than skipping.
                torch_seen = True
            elif torch_agent_id > 0:
                torch_seen = True
            elif elapsed_ms >= NOT_FOUND_GRACE_MS:
                _log(
                    (
                        "No torch found on the ground. "
                        "Assuming this pickup was already completed "
                        "before the planner resumed the step; skipping."
                    ),
                    PySystem.Console.MessageType.Warning,
                )
                _reset_state()
                return BehaviorTree.NodeState.SUCCESS
            else:
                return BehaviorTree.NodeState.RUNNING

        if elapsed_ms >= PICKUP_TIMEOUT_MS:
            _log(
                "Failed to pick up a torch after 45s.",
                PySystem.Console.MessageType.Error,
            )
            _reset_state()
            return BehaviorTree.NodeState.FAILURE

        if now < retry_at:
            return BehaviorTree.NodeState.RUNNING

        pickup_tree.blackboard = node.blackboard

        pickup_result = BehaviorTree.Node._normalize_state(
            pickup_tree.tick()
        )

        if pickup_result == BehaviorTree.NodeState.RUNNING:
            return BehaviorTree.NodeState.RUNNING

        # Le node interne annonce SUCCESS, mais la torche
        # n'est réellement pas tenue par le personnage.
        if pickup_result == BehaviorTree.NodeState.SUCCESS:
            _log(
                (
                    "Pickup not completed "
                    "(no torch is held). Retrying..."
                ),
                PySystem.Console.MessageType.Warning,
            )

            pickup_tree = _create_pickup_tree()
            pickup_tree.blackboard = node.blackboard
            retry_at = now + (
                RETRY_DELAY_MS / 1000.0
            )

            return BehaviorTree.NodeState.RUNNING

        pickup_tree = _create_pickup_tree()
        pickup_tree.blackboard = node.blackboard
        retry_at = now + (
            RETRY_DELAY_MS / 1000.0
        )

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="PickupTorch",
            action_fn=_pickup_torch_step,
            aftercast_ms=0,
        )
    )

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


def BrazierSequence(
    name: str,
    points: list[tuple[float, float]],
) -> BehaviorTree:
    """
    Activate a sequence of SoO braziers.

    The first brazier is activated normally because the torch flame effect is
    not available before that interaction. Every following movement continuously
    monitors the flame and returns to the previous brazier if it disappears.
    """
    if not points:
        return BT.Succeeder(
            f"{name}Empty",
        )

    children: list[
        BehaviorTree | BehaviorTree.Node
    ] = []

    first_x, first_y = points[0]

    children.append(
        BT.MoveAndInteractWithGadget(
            pos=Vec2f(
                float(first_x),
                float(first_y),
            ),
            gadget_id=None,
            search_distance=300.0,
            interaction_distance=220.0,
            interaction_count=2,
            interaction_interval_ms=250,
            timeout_ms=15_000,
            pause_on_combat=False,
            multi_account=False,
            include_self=True,
            log=True,
            
        )
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

    return BT.Sequence(
        name=name,
        children=children,
    )

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

    previous_pos = Vec2f(
        float(previous_brazier[0]),
        float(previous_brazier[1]),
    )

    next_pos = Vec2f(
        float(next_brazier[0]),
        float(next_brazier[1]),
    )

    move_to_next = BT.Move(
        next_pos,
        tolerance=float(interaction_distance),
        pause_on_combat=False,
        ignore_destination_obstacles=True,
        log=False,
    )

    move_to_previous = BT.Move(
        previous_pos,
        tolerance=float(interaction_distance),
        pause_on_combat=False,
        ignore_destination_obstacles=True,
        log=False,
    )

    relight_previous = BT.MoveAndInteractWithGadget(
        pos=previous_pos,
        gadget_id=None,
        search_distance=300.0,
        interaction_distance=float(interaction_distance),
        interaction_count=max(
            1,
            int(interaction_count),
        ),
        interaction_interval_ms=max(
            0,
            int(interaction_interval_ms),
        ),
        timeout_ms=15_000,
        pause_on_combat=False,
        multi_account=False,
        include_self=True,
        log=log,
    )

    interact_next = BT.MoveAndInteractWithGadget(
        pos=next_pos,
        gadget_id=None,
        search_distance=300.0,
        interaction_distance=float(interaction_distance),
        interaction_count=max(
            1,
            int(interaction_count),
        ),
        interaction_interval_ms=max(
            0,
            int(interaction_interval_ms),
        ),
        timeout_ms=15_000,
        pause_on_combat=False,
        multi_account=False,
        include_self=True,
        log=log,
    )

    state = {
        "phase": "move_to_next",
        "started_at": 0.0,
        "phase_started_at": 0.0,
        "recovery_count": 0,
    }

    def _trace(
        message: str,
        message_type=PySystem.Console.MessageType.Info,
    ) -> None:
        if not log:
            return

        PySystem.Console.Log(
            MODULE_NAME,
            f"[{name}] {message}",
            message_type,
        )

    def _has_active_flame() -> bool:
        try:
            player_agent_id = Player.GetAgentID()

            if not player_agent_id:
                return False

            return bool(
                GLOBAL_CACHE.Effects.HasEffect(
                    player_agent_id,
                    int(effect_id),
                )
            )
        except Exception:
            return False

    def _cancel_current_movement() -> None:
        try:
            player_x, player_y = Player.GetXY()

            Player.Move(
                float(player_x),
                float(player_y),
            )
        except Exception:
            pass

    def _reset_tree(
        tree: BehaviorTree,
    ) -> None:
        try:
            tree.reset()
        except Exception:
            try:
                tree.root.reset()
            except Exception:
                pass

    def _tick_tree(
        tree: BehaviorTree,
        node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
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

    def _begin_recovery(
        now: float,
        reason: str,
    ) -> BehaviorTree.NodeState:
        state["recovery_count"] += 1

        recovery_limit = max(
            1,
            int(max_recoveries),
        )

        if state["recovery_count"] > recovery_limit:
            _trace(
                (
                    f"{reason} Local recovery failed after "
                    f"{recovery_limit} attempt(s)."
                ),
                PySystem.Console.MessageType.Warning,
            )

            _cancel_current_movement()
            _reset_all()

            return BehaviorTree.NodeState.FAILURE

        _trace(
            (
                f"{reason} Returning to the previous brazier "
                f"(recovery {state['recovery_count']}/"
                f"{recovery_limit})."
            ),
            PySystem.Console.MessageType.Warning,
        )

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

    def _move_with_recovery(
        node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        now = time.monotonic()

        if state["started_at"] <= 0.0:
            state["started_at"] = now
            state["phase_started_at"] = now

            _trace(
                (
                    "Starting monitored BT movement from "
                    f"{previous_brazier} to {next_brazier}."
                )
            )

        elapsed_ms = (
            now
            - float(state["started_at"])
        ) * 1000.0

        if elapsed_ms >= max(
            1,
            int(timeout_ms),
        ):
            _trace(
                "Timed out while moving between braziers.",
                PySystem.Console.MessageType.Warning,
            )

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

        phase = str(
            state["phase"]
        )

        # --------------------------------------------------------------
        # Déplacement vers le prochain brasero
        # --------------------------------------------------------------
        if phase == "move_to_next":
            if not _has_active_flame():
                return _begin_recovery(
                    now,
                    "Torch flame extinguished during movement.",
                )

            result = _tick_tree(
                move_to_next,
                node,
            )

            if result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if result == BehaviorTree.NodeState.FAILURE:
                return _begin_recovery(
                    now,
                    "Movement to the next brazier failed.",
                )

            _reset_tree(move_to_next)

            state["phase"] = "interact_next"
            state["phase_started_at"] = now

            _trace(
                (
                    "Reached the next brazier with the torch "
                    "still active."
                )
            )

            return BehaviorTree.NodeState.RUNNING

        # --------------------------------------------------------------
        # Interaction avec le prochain brasero
        # --------------------------------------------------------------
        if phase == "interact_next":
            if not _has_active_flame():
                return _begin_recovery(
                    now,
                    (
                        "Torch flame extinguished before the next "
                        "brazier interaction."
                    ),
                )

            result = _tick_tree(
                interact_next,
                node,
            )

            if result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if result == BehaviorTree.NodeState.FAILURE:
                # Ne pas laisser FAILURE remonter au planner.
                # On retourne localement au précédent brasero.
                return _begin_recovery(
                    now,
                    (
                        "Interaction with the next brazier "
                        "failed."
                    ),
                )

            _trace(
                "Next brazier interaction completed.",
                PySystem.Console.MessageType.Success,
            )

            _reset_all()

            return BehaviorTree.NodeState.SUCCESS

        # --------------------------------------------------------------
        # Retour au précédent brasero
        # --------------------------------------------------------------
        if phase == "move_to_previous":
            result = _tick_tree(
                move_to_previous,
                node,
            )

            if result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if result == BehaviorTree.NodeState.FAILURE:
                _trace(
                    (
                        "Movement back to the previous brazier "
                        "failed."
                    ),
                    PySystem.Console.MessageType.Warning,
                )

                _cancel_current_movement()
                _reset_all()

                return BehaviorTree.NodeState.FAILURE

            _reset_tree(move_to_previous)

            state["phase"] = "relight_previous"
            state["phase_started_at"] = now

            _trace(
                (
                    "Reached the previous brazier. "
                    "Relighting the torch."
                )
            )

            return BehaviorTree.NodeState.RUNNING

        # --------------------------------------------------------------
        # Interaction avec le précédent brasero
        # --------------------------------------------------------------
        if phase == "relight_previous":
            result = _tick_tree(
                relight_previous,
                node,
            )

            if result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if result == BehaviorTree.NodeState.FAILURE:
                _trace(
                    (
                        "Interaction with the previous brazier "
                        "failed. Retrying local recovery."
                    ),
                    PySystem.Console.MessageType.Warning,
                )

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
                _trace(
                    (
                        "Torch relit successfully. Resuming "
                        "movement to the next brazier."
                    ),
                    PySystem.Console.MessageType.Success,
                )

                _reset_tree(move_to_next)
                _reset_tree(interact_next)

                state["phase"] = "move_to_next"
                state["phase_started_at"] = now

                return BehaviorTree.NodeState.RUNNING

            elapsed_phase_ms = (
                now
                - float(state["phase_started_at"])
            ) * 1000.0

            if elapsed_phase_ms < max(
                1,
                int(effect_apply_timeout_ms),
            ):
                return BehaviorTree.NodeState.RUNNING

            _trace(
                (
                    "The torch effect did not return after the "
                    "previous brazier interaction. Retrying."
                ),
                PySystem.Console.MessageType.Warning,
            )

            _reset_tree(relight_previous)

            state["phase"] = "relight_previous"
            state["phase_started_at"] = now

            return BehaviorTree.NodeState.RUNNING

        _trace(
            (
                f"Unknown brazier recovery phase "
                f"'{phase}'."
            ),
            PySystem.Console.MessageType.Warning,
        )

        _cancel_current_movement()
        _reset_all()

        return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_move_with_recovery,
            aftercast_ms=0,
        )
    )
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
            isolation_enabled=True,
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
            BT.IsCurrentMap(
    map_id=SOO_LEVEL_1,
    log=True,
),
            BT.IsQuestState(
                quest_id=LOST_SOULS_QUEST_ID,
                state="active",
                log=True,
            ),
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
            BT.AbandonQuest(
    quest_id=LOST_SOULS_QUEST_ID,
    multi_account=True,
    include_self=True,
    timeout_ms=10_000,
    log=True,
),
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
    active = BT.Sequence(
        name="Lost Souls Already Active",
        children=[BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state="active", log=True), BT.Succeeder("ContinueWithActiveQuest")],
    )
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


def EnterShardsOfOrr(
    enable_consumables_on_entry: bool = True,
) -> BehaviorTree:
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
            BT.Move(
                SOO_ENTRANCE_PATH,
                pause_on_combat=False,
                ignore_destination_obstacles=True,
                log=False,
            ),
            BT.WaitForMapLoad(map_id=SOO_LEVEL_1, timeout_ms=60_000),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
        ],
    )
    entry = BT.Selector(
        children=[already_inside, normal_entry],
        name="Enter Shards of Orr",
    )

    if not enable_consumables_on_entry:
        return entry

    return BT.Sequence(
        name="Enter Shards of Orr And Resume Consumables",
        children=[
            entry,
            _runtime_consumable_upkeep_node(True),
        ],
    )


# endregion


# region Planner point steps


def _map_guarded_point(
    name: str,
    map_id: int,
    child: BehaviorTree,
    skip_if_in_maps: Sequence[int] = (),
) -> BehaviorTree:
    """Run one point on its map, or accept it when the next level is loaded."""
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
                    BT.IsCurrentMap(map_id=later_map_id, log=False),
                    BT.Succeeder(f"{name}AlreadyPassed"),
                ],
            )
        )

    if len(branches) == 1:
        return branches[0]

    return BT.Selector(
        name=name,
        children=branches,
    )


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
                lambda point=point, name=name: _map_guarded_point(
                    name=name,
                    map_id=map_id,
                    child=BT.Move(
                        point,
                        pause_on_combat=pause_on_combat,
                        tolerance=tolerance,
                        flag_heroes_to_waypoint=flag_heroes_to_waypoint,
                        ignore_destination_obstacles=ignore_destination_obstacles,
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
                lambda point=point, name=name: _map_guarded_point(
                    name=name,
                    map_id=map_id,
                    child=BT.VanquishNode(
                        [point],
                        name=name,
                        clear_area_radius=clear_area_radius,
                        pause_on_combat=pause_on_combat,
                        flag_heroes_to_waypoint=flag_heroes_to_waypoint,
                        move_tolerance=move_tolerance,
                        log=False,
                    ),
                    skip_if_in_maps=skip_if_in_maps,
                ),
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
            BT.MoveAndDialog(
                Vec2f(-11686.0, 10427.0),
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
        ],
    )


def Level1_OpenDoor() -> BehaviorTree:
    return BT.Sequence(
        name="Open Level 1 Door",
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True),
            BT.MoveAndInteractWithGadget(Vec2f(15100.0, 5443.0),
                pause_on_combat=True,
                log=True,
            ),
        ],
    )


def Level1_EnterLevel2() -> BehaviorTree:
    name = f"Level 1 Route To Level 2 - Point {len(L1_PATH_AFTER_DOOR):02d}"
    return BT.Sequence(
        name=name,
        children=[
            _map_guarded_point(
                name=name,
                map_id=SOO_LEVEL_1,
                child=BT.Sequence(
                    name=f"{name} And Load Level 2",
                    children=[
                        BT.VanquishNode(
                            [L1_PATH_AFTER_DOOR[-1]],
                            name=name,
                            flag_heroes_to_waypoint=False,
                            move_tolerance=500,
                            log=False,
                        ),
                        BT.WaitForMapLoad(map_id=SOO_LEVEL_2, timeout_ms=60_000),
                    ],
                ),
                skip_if_in_maps=(SOO_LEVEL_2,),
            ),
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
            BT.MoveAndDialog(
                L2_BLESSING_NPC,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
            BT.ClearEnemiesInArea(
                L2_TORCH_CHEST,
                radius=Range.Compass.value,
                log=True,
            ),
            BT.MoveAndInteractWithGadget(
                L2_TORCH_CHEST,
                pause_on_combat=False,
                log=True,
            ),
            PickupTorch(),
        ],
    )


def Level2_FirstTorchFight() -> BehaviorTree:
    return BT.Sequence(
        name="Level 2 First Torch Fight",
        children=[
            DropTorchForCombat(log=True),
            BT.VanquishNode([L2_RETURN_TO_FIRST_TORCH_PATH], clear_area_radius=Range.SafeCompass.value, log=True),
            PickupTorch(),
        ],
    )


def Level2_BrazierRoute1() -> BehaviorTree:
    return BT.Sequence(
        name="Level 2 Brazier Route 1",
        children=[
            BrazierSequence("Level 2 Brazier Route 1", L2_BRAZIER_PART1),
            DropTorchForCombat(log=True),
        ],
    )


# endregion
# region Level 2 - part 2


def Level2_PrepareRoom2() -> BehaviorTree:
    return BT.Sequence(
        name="Prepare Level 2 Room 2",
        children=[
            ResolveTorchCombatPolicy(),
            BT.Wait(2000),
            BT.MoveAndKill(Vec2f(-9011.27, -11536.79)),
            BT.WaitForClearEnemiesInArea(
               -9011.0,-11536.0,radius=Range.SafeCompass.value,
                log=True,
            ),
            BT.Wait(2000),
            PickupTorch(),
        ],
    )


def Level2_DropTorchBeforeRoom2Return() -> BehaviorTree:
    return BT.Sequence(
        name="Drop Torch Before Returning To Room 2",
        children=[
            DropTorchForCombat(log=True),
        ],
    )


def Level2_PickupRoom2Torch() -> BehaviorTree:
    return BT.Sequence(
        name="Pick Up Level 2 Room 2 Torch",
        children=[
            PickupTorch(),
        ],
    )


def Level2_DropTorchBeforeFinalRoom2Fight() -> BehaviorTree:
    return BT.Sequence(
        name="Drop Torch Before Final Room 2 Fight",
        children=[
            DropTorchForCombat(log=True),
        ],
    )


def Level2_PickupTorchForBrazierRoute2() -> BehaviorTree:
    return BT.Sequence(
        name="Pick Up Torch For Level 2 Brazier Route 2",
        children=[
            PickupTorch(),
        ],
    )


def Level2_BrazierRoute2() -> BehaviorTree:
    return BT.Sequence(
        name="Level 2 Brazier Route 2",
        children=[
            BrazierSequence("Level 2 Brazier Route 2", L2_BRAZIER_PART2),
            BT.DropBundle(log=True),
        ],
    )


# endregion


# region Level 2 - part 3


def Level2_OpenDungeonLock() -> BehaviorTree:
    return BT.Sequence(
        name="Open Level 2 Dungeon Lock",
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_2, log=True),
            BT.MoveAndInteractWithGadget(
                L2_DUNGEON_LOCK,
                pause_on_combat=False,
                log=True,
            ),
        ],
    )


def Level2_EnterLevel3() -> BehaviorTree:
    name = f"Level 2 Exit Route - Point {len(L2_EXIT_PATH):02d}"
    return BT.Sequence(
        name=name,
        children=[
            _map_guarded_point(
                name=name,
                map_id=SOO_LEVEL_2,
                child=BT.Sequence(
                    name=f"{name} And Load Level 3",
                    children=[
                        BT.Move(
                            L2_EXIT_PATH[-1],
                            pause_on_combat=False,
                            tolerance=200.0,
                            log=False,
                        ),
                        BT.WaitForMapLoad(map_id=SOO_LEVEL_3, timeout_ms=60_000),
                    ],
                ),
                skip_if_in_maps=(SOO_LEVEL_3,),
            ),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            _mark_l3_start_node(),
            BT.Wait(2_000),
        ],
    )


# endregion

# region Level 3 - part 1


def Level3_Start() -> BehaviorTree:
    return BT.Sequence(
        name="Start Shards of Orr Level 3",
        children=[
            UseAvailableSummoningStone(),
            BT.MoveAndDialog(
                L3_ENTRY_BLESSING,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
        ],
    )


def Level3_TorchAndBraziers() -> BehaviorTree:
    return BT.Sequence(
        name="Open Level 3 Torch Chest And Light Braziers",
        children=[
            BT.MoveAndInteractWithGadget(
                L3_TORCH_CHEST, pause_on_combat=False, log=True,
            ),
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
            BT.MoveAndKill(
                Vec2f(-11147, 2644) ,
                clear_area_radius=Range.Spirit.value,
                log=False,
            ),
            BT.AddModelToLootWhitelist(25410),
            BT.Wait(2000),
            BT.LootItems(distance=Range.Spirit.value),
            BT.MoveAndInteractWithGadget(
                Vec2f(-9252.32, 6396.40), pause_on_combat=False, log=True,
            ),
        ],
    )
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
    state = {
        "last_target_id": 0,
        "last_interact_ms": 0,
    }

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

        # BossGlow is authoritative when available. The name fallback covers
        # either Fendi form if one of them happens not to expose the glow flag.
        return boss_glow if boss_glow else named_fendi

    def _choose_target(enemies: list[int]) -> tuple[int, str]:
        player_xy = Player.GetXY()
        priority_targets = _priority_boss_targets(enemies)

        if priority_targets:
            target_id = min(
                priority_targets,
                key=lambda aid: _fendi_distance_sq(aid, player_xy),
            )
            try:
                if Agent.HasBossGlow(target_id):
                    return target_id, "BossGlow"
            except Exception:
                pass
            return target_id, "FendiName"

        return (
            min(enemies, key=lambda aid: _fendi_distance_sq(aid, player_xy)),
            "NearestEnemy",
        )

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

        # The Fendi encounter alternates between Fendi and his Soul, with short
        # transition windows and fresh trash spawns on each form change. Do NOT
        # finish the priority phase merely because the enemy array is briefly
        # empty. The final chest is our definitive encounter-complete signal.
        chest_present = _fendi_final_chest_present()

        if not enemies:
            state["last_target_id"] = 0
            state["last_interact_ms"] = 0

            if chest_present:
                PySystem.Console.Log(
                    MODULE_NAME,
                    "Fendi final chest detected. Boss/Soul cycle is complete; "
                    "switching to final stock area-clear verification.",
                    PySystem.Console.MessageType.Success,
                )
                return BehaviorTree.NodeState.SUCCESS

            return BehaviorTree.NodeState.RUNNING

        # Extra guard: if the chest has appeared while only normal adds remain,
        # the boss cycle itself is complete. Hand those remaining enemies to the
        # stock ClearEnemiesInArea + 15s stable-clear sequence below.
        if chest_present and not _priority_boss_targets(enemies):
            PySystem.Console.Log(
                MODULE_NAME,
                "Fendi final chest detected with only normal enemies remaining. "
                "Handing final cleanup to ClearEnemiesInArea.",
                PySystem.Console.MessageType.Info,
            )
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

            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f"Fendi priority target -> {target_name} "
                    f"(id={target_id}, priority={priority_label}, "
                    f"boss_glow={boss_glow}, enemies={len(enemies)})."
                ),
                PySystem.Console.MessageType.Info,
            )
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

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Clear Fendi Arena With Boss Priority",
            action_fn=_fight,
            aftercast_ms=0,
        )
    )


def Level3_FendiFight() -> BehaviorTree:
    return BT.Sequence(
        name="Run Fendi Boss Fight",
        children=[
            # Main fight: always prefer Fendi / his soul when they expose
            # BossGlow, with a name fallback before ordinary enemies.
            ClearFendiArenaWithBossPriority(),

            # Final stock clear is intentionally preserved.  It handles any
            # delayed enemy appearance and requires the arena to stay clear for
            # 15 seconds before the bot is allowed to continue to the chest.
            BT.ClearEnemiesInArea(
                Vec2f(-15606.06, 15287.51),
                radius=Range.Compass.value,
                log=True,
            ),
            BT.WaitForClearEnemiesInArea(
                -15606.06,
                15287.51,
                radius=Range.Compass.value,
                allowed_alive_enemies=0,
                interact_interval_ms=750,
                stable_clear_ms=15_000,
                keep_player_near_center=False,
                center_tolerance=750.0,
                log=True,
            ),
            _record_run_end_node(),
        ],
    )
#endregion

# region Level 3 - Chest
def Level3_Chest() -> BehaviorTree:
    return BT.Sequence(
        name="Open chest",
        children=[
            BT.Move(
                Vec2f(-15198, 16839),
                tolerance=350.0,
                pause_on_combat=False,
                log=True,
            ),
            BT.Wait(3000),
            BT.MoveAndInteractWithGadget(
                gadget_id=FENDI_CHEST_GADGET_ID,
                pos=Vec2f(*FENDI_CHEST_POSITION),
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
            _inventory_statistics_node(after_chest=True),
            
    
        ])
#endregion


# region Reward and restart flow

def CollectInsideReward() -> BehaviorTree:
    """
    Collect the Lost Souls reward from Shandra inside the dungeon.

    Shandra is resolved directly by name using TargetAgentByName.
    The routine interacts with her and sends the known reward dialog
    locally and across the multibox party.
    """
    return BT.Sequence(
        name="Collect Inside Reward",
        children=[
            BT.Wait(5000),
            BT.TargetAgentByName(
                agent_name="Shandra",
                log=True,
            ),
            BT.LogMessage(
                message=(
                    "Shandra was found near the final chest. "
                    "Attempting to collect the Lost Souls reward."
                ),
                module_name=MODULE_NAME,
            ),
            BT.InteractTargetAndSendDialog(
                dialog_id=SHANDRA_REWARD_DIALOG,
                multi_account=True,
                log=True,
            ),
            BT.SendDialog(dialog_id=SHANDRA_REWARD_DIALOG, multi_account=True, log=True),
            BT.WaitForQuestCleared(
                LOST_SOULS_QUEST_ID,
                timeout_ms=15_000,
            ),
        ],
    )




def ResolveShandraQuestAfterRun() -> BehaviorTree:
    """Leave Arbor Bay with Lost Souls active, without starting the next run."""
    direct_retake = BT.Sequence(
        name="Retake Lost Souls Directly",
        children=[
            BT.MoveAndDialog(
                SHANDRA_APPROACH,
                SHANDRA_TAKE_DIALOG,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(
                LOST_SOULS_QUEST_ID,
                timeout_ms=15_000,
            ),
        ],
    )

    retake_after_reset_entry = BT.Sequence(
        name="Reset Shandra By Entering Level 1",
        children=[
            BT.LogMessage(
                message=(
                    "Shandra did not offer Lost Souls directly. "
                    "Entering and leaving Level 1 once before retrying."
                ),
                module_name=MODULE_NAME,
            ),
            EnterShardsOfOrr(enable_consumables_on_entry=False),
            BT.MoveAndExitMap(
                LEVEL1_EXIT_TO_ARBOR,
                target_map_id=ARBOR_BAY,
                log=False,
            ),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.Move(
                [Vec2f(10218.0, -18864.0), SHANDRA_APPROACH],
                pause_on_combat=False,
                log=False,
            ),
            BT.MoveAndDialog(
                SHANDRA_APPROACH,
                SHANDRA_TAKE_DIALOG,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(
                LOST_SOULS_QUEST_ID,
                timeout_ms=15_000,
            ),
        ],
    )

    quest_already_active = BT.Sequence(
        name="Keep Active Lost Souls Quest",
        children=[
            BT.IsQuestState(
                quest_id=LOST_SOULS_QUEST_ID,
                state="active",
                log=True,
            ),
            BT.LogMessage(
                message="Lost Souls is already active for the next run.",
                module_name=MODULE_NAME,
            ),
        ],
    )

    reward_collected_inside = BT.Sequence(
        name="Retake Lost Souls After Inside Reward",
        children=[
            BT.IsQuestState(
                quest_id=LOST_SOULS_QUEST_ID,
                state="missing",
                log=True,
            ),
            BT.Selector(
                name="Retake Lost Souls With Reset Fallback",
                children=[
                    direct_retake,
                    BT.Sequence(
                        name="Retake Completed Despite Wait Failure",
                        children=[
                            BT.IsQuestState(
                                quest_id=LOST_SOULS_QUEST_ID,
                                state="active",
                                log=True,
                            ),
                            BT.Succeeder("LostSoulsRetakeAlreadyCompleted"),
                        ],
                    ),
                    retake_after_reset_entry,
                ],
            ),
        ],
    )

    reward_not_collected_inside = BT.Sequence(
        name="Collect Outside Reward And Retake Lost Souls",
        children=[
            BT.IsQuestState(
                quest_id=LOST_SOULS_QUEST_ID,
                state="complete",
                log=True,
            ),
            BT.LogMessage(
                message=(
                    "The reward is still pending. "
                    "Collecting it from Shandra in Arbor Bay."
                ),
                module_name=MODULE_NAME,
            ),
            BT.MoveAndDialog(
                SHANDRA_APPROACH,
                SHANDRA_REWARD_DIALOG,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForQuestCleared(
                LOST_SOULS_QUEST_ID,
                timeout_ms=15_000,
            ),
            BT.LogMessage(
                message=(
                    "The Lost Souls reward was collected "
                    "successfully in Arbor Bay."
                ),
                module_name=MODULE_NAME,
            ),

            # Guild Wars requires one entry into Level 1 after an outside
            # reward before Shandra offers Lost Souls again.
            EnterShardsOfOrr(enable_consumables_on_entry=False),
            BT.MoveAndExitMap(
                LEVEL1_EXIT_TO_ARBOR,
                target_map_id=ARBOR_BAY,
                log=False,
            ),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.Move(
                [Vec2f(10218.0, -18864.0), SHANDRA_APPROACH],
                pause_on_combat=False,
                log=False,
            ),
            BT.MoveAndDialog(
                SHANDRA_APPROACH,
                SHANDRA_TAKE_DIALOG,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(
                LOST_SOULS_QUEST_ID,
                timeout_ms=15_000,
            ),
        ],
    )

    return BT.Sequence(
        name="Resolve Shandra Quest After Run",
        children=[
            BT.IsCurrentMap(map_id=ARBOR_BAY, log=True),
            BT.Selector(
                name="Resolve Lost Souls State In Arbor Bay",
                children=[
                    quest_already_active,
                    reward_collected_inside,
                    reward_not_collected_inside,
                ],
            ),
            BT.IsQuestState(
                quest_id=LOST_SOULS_QUEST_ID,
                state="active",
                log=True,
            ),
        ],
    )


def PrepareNextDungeonRun() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Next Run Already Entered",
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True),
            BT.IsQuestState(
                quest_id=LOST_SOULS_QUEST_ID,
                state="active",
                log=True,
            ),
        ],
    )

    continue_from_arbor = BT.Sequence(
        name="Enter Next Run From Arbor Bay",
        children=[
            BT.IsCurrentMap(map_id=ARBOR_BAY, log=True),
            BT.IsQuestState(
                quest_id=LOST_SOULS_QUEST_ID,
                state="active",
                log=True,
            ),
            EnterShardsOfOrr(),
        ],
    )

    continue_after_maintenance = BT.Sequence(
        name="Reform Party And Enter Next Run From Vlox",
        children=[
            BT.IsCurrentMap(map_id=VLOXS_FALL, log=True),
            BT.IsQuestState(
                quest_id=LOST_SOULS_QUEST_ID,
                state="active",
                log=True,
            ),
            BT.CreateParty(
                multibox_invite=True,
                timeout_ms=30_000,
                log=True,
            ),
            _runtime_difficulty_node(),
            _runtime_restock_node(),
            TravelToShandra(),
            EnterShardsOfOrr(),
        ],
    )

    return BT.Selector(
        name="Prepare Next Dungeon Run",
        children=[
            already_inside,
            continue_from_arbor,
            continue_after_maintenance,
        ],
    )


def CollectRewardAndReturnToArbor(
    end_countdown_timeout_ms: int = 190_000,
) -> BehaviorTree:
    already_in_arbor = BT.Sequence(
        name="Skip Inside Reward - Already In Arbor Bay",
        children=[
            BT.IsCurrentMap(
                map_id=ARBOR_BAY,
                log=True,
            ),
            BT.LogMessage(
                message=(
                    "The party is already in Arbor Bay. "
                    "Skipping the inside reward search and "
                    "resuming the restart preparation."
                ),
                module_name=MODULE_NAME,
            ),
            BT.Succeeder(
                "InsideRewardAlreadyReturnedToArbor",
            ),
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
            BT.IsCurrentMap(
                map_id=SOO_LEVEL_3,
                log=True,
            ),
            BT.LogMessage(
                message=(
                    "Level 3 confirmed after Fendi. Looking for Shandra "
                    "by name inside the dungeon."
                ),
                module_name=MODULE_NAME,
            ),
            CollectInsideReward(),
            BT.WaitForQuestCleared(
                LOST_SOULS_QUEST_ID,
                timeout_ms=15_000,
            ),
            BT.LogMessage(
                message=(
                    "Shandra was found inside the dungeon "
                    "and the Lost Souls reward was collected."
                ),
                module_name=MODULE_NAME,
            ),
        ],
    )

    reward_not_collected_inside = BT.Sequence(
        name="Shandra Unavailable Inside Dungeon",
        children=[
            BT.LogMessage(
                message=(
                    "Shandra was not found inside the dungeon "
                    "or the inside reward could not be collected. "
                    "The reward will be handled in Arbor Bay."
                ),
                module_name=MODULE_NAME,
            ),
            BT.Succeeder(
                "InsideRewardUnavailable",
            ),
        ],
    )

    return BT.Sequence(
        name="Collect Reward And Return To Arbor",
        children=[
            _runtime_consumable_upkeep_node(False),
            BT.Selector(
                name="Resolve Inside Reward",
                children=[
                    already_in_arbor,
                    reward_collected_inside,
                    reward_not_collected_inside,
                ],
            ),
            BT.LogMessage(
                message=(
                    "Waiting for the end-of-dungeon countdown "
                    "and the return to Arbor Bay."
                ),
                module_name=MODULE_NAME,
            ),
            BT.WaitForMapLoad(
                map_id=ARBOR_BAY,
                timeout_ms=end_countdown_timeout_ms,
            ),
            BT.WaitUntilOnExplorable(
                timeout_ms=30_000,
            ),
            BT.Wait(
                2_000,
            ),
            BT.LogMessage(
                message=(
                    "The party has returned to Arbor Bay. "
                    "Preparing the next dungeon run."
                ),
                module_name=MODULE_NAME,
            ),
            BT.Move(
                SHANDRA_APPROACH,
                pause_on_combat=False,
                log=False,
            ),
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
        *_vanquish_point_steps(
            "Level 1 First Route",
            SOO_LEVEL_1,
            L1_PATH,
            flag_heroes_to_waypoint=False,
            move_tolerance=500.0,
            skip_if_in_maps=(SOO_LEVEL_2, SOO_LEVEL_3),
        ),
        ("Level 1 Open Door", Level1_OpenDoor),
        *_vanquish_point_steps(
            "Level 1 Route To Level 2",
            SOO_LEVEL_1,
            L1_PATH_AFTER_DOOR[:-1],
            flag_heroes_to_waypoint=False,
            move_tolerance=500.0,
            skip_if_in_maps=(SOO_LEVEL_2, SOO_LEVEL_3),
        ),
        (
            f"Level 1 Route To Level 2 - Point {len(L1_PATH_AFTER_DOOR):02d}",
            Level1_EnterLevel2,
        ),

        ("Level 2 Start", Level2_Start),
        *_movement_point_steps(
            "Level 2 First Torch Drop Route",
            SOO_LEVEL_2,
            L2_FIRST_TORCH_DROP_POINT_PATH,
            pause_on_combat=True,
            skip_if_in_maps=(SOO_LEVEL_3,),
        ),
        ("Level 2 First Torch Fight", Level2_FirstTorchFight),
        *_movement_point_steps(
            "Level 2 First Brazier Approach",
            SOO_LEVEL_2,
            [
                Vec2f(-9404.44, -17963.49),
                Vec2f(-11303.00, -14596.00),
            ],
            pause_on_combat=True,
            skip_if_in_maps=(SOO_LEVEL_3,),
        ),
        ("Level 2 Brazier Route 1", Level2_BrazierRoute1),

        ("Level 2 Prepare Room 2", Level2_PrepareRoom2),
        *_vanquish_point_steps(
            "Level 2 Route To Room 2 Drop",
            SOO_LEVEL_2,
            L2_TO_ROOM2_DROP,
            clear_area_radius=Range.Area.value,
            pause_on_combat=True,
            move_tolerance=500.0,
            skip_if_in_maps=(SOO_LEVEL_3,),
        ),
        ("Level 2 Drop Torch Before Room 2 Return", Level2_DropTorchBeforeRoom2Return),
        *_vanquish_point_steps(
            "Level 2 Route Back To Room 2 Torch",
            SOO_LEVEL_2,
            L2_RETURN_TO_ROOM2_TORCH_PATH,
            flag_heroes_to_waypoint=False,
            move_tolerance=500.0,
            skip_if_in_maps=(SOO_LEVEL_3,),
        ),
        ("Level 2 Pick Up Room 2 Torch", Level2_PickupRoom2Torch),
        *_vanquish_point_steps(
            "Level 2 Room 2",
            SOO_LEVEL_2,
            L2_ROOM2_PATH,
            flag_heroes_to_waypoint=False,
            move_tolerance=150.0,
            skip_if_in_maps=(SOO_LEVEL_3,),
        ),
        ("Level 2 Drop Torch Before Final Room 2 Fight", Level2_DropTorchBeforeFinalRoom2Fight),
        *_vanquish_point_steps(
            "Level 2 Room 2 Final Fight",
            SOO_LEVEL_2,
            [Vec2f(-4245.2, -2101.0)],
            flag_heroes_to_waypoint=False,
            move_tolerance=500.0,
            skip_if_in_maps=(SOO_LEVEL_3,),
        ),
        ("Level 2 Pick Up Torch For Brazier Route 2", Level2_PickupTorchForBrazierRoute2),
        ("Level 2 Brazier Route 2", Level2_BrazierRoute2),

        *_vanquish_point_steps(
            "Level 2 Route To Dungeon Lock",
            SOO_LEVEL_2,
            L2_PATH_TO_LOCK,
            pause_on_combat=True,
            flag_heroes_to_waypoint=False,
            move_tolerance=500.0,
            skip_if_in_maps=(SOO_LEVEL_3,),
        ),
        ("Level 2 Open Dungeon Lock", Level2_OpenDungeonLock),
        *_movement_point_steps(
            "Level 2 Exit Route",
            SOO_LEVEL_2,
            L2_EXIT_PATH[:-1],
            pause_on_combat=False,
            skip_if_in_maps=(SOO_LEVEL_3,),
        ),
        (
            f"Level 2 Exit Route - Point {len(L2_EXIT_PATH):02d}",
            Level2_EnterLevel3,
        ),

        ("Level 3 Start", Level3_Start),
        *_vanquish_point_steps(
            "Level 3 Main Route",
            SOO_LEVEL_3,
            L3_MAIN_PATH,
            flag_heroes_to_waypoint=False,
            move_tolerance=500.0,
        ),
        *_vanquish_point_steps(
            "Level 3 Brigant Room Route",
            SOO_LEVEL_3,
            L3_BRIGANT_ROOM,
            flag_heroes_to_waypoint=False,
            move_tolerance=500.0,
        ),
        *_movement_point_steps(
            "Level 3 Torch Route",
            SOO_LEVEL_3,
            L3_PATH_TO_TORCH,
            pause_on_combat=False,
            flag_heroes_to_waypoint=False,
        ),
        ("Level 3 Torch And Braziers", Level3_TorchAndBraziers),
        ("Level 3 Brigant", Level3_Brigant),
        *_vanquish_point_steps(
            "Level 3 Route To Fendi",
            SOO_LEVEL_3,
            L3_FENDI_PATH,
            flag_heroes_to_waypoint=False,
            move_tolerance=500.0,
        ),
        ("Level 3 Fendi Boss Fight", Level3_FendiFight),
        ("Level 3 Chest", Level3_Chest ),
        ("Collect Reward And Return To Arbor", CollectRewardAndReturnToArbor),
        ("Resolve Shandra Quest", ResolveShandraQuestAfterRun),
        ("Inventory Check And Maintenance", InventoryCheckAndMaintenance),
        ("Prepare Next Dungeon Run", PrepareNextDungeonRun),
    ]



def tooltip():
    import PyImGui
    from Py4GWCoreLib import ImGui, Color

    PyImGui.begin_tooltip()

    # Title
    title_color = Color(255, 200, 100, 255)
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored(
        "Shards Of Orr Farm",
        title_color.to_tuple_normalized(),
    )
    ImGui.pop_font()

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    # Description
    PyImGui.text("Fully automated Shards of Orr dungeon farm")
    PyImGui.text("Designed for BDS farming")

    PyImGui.spacing()

    # Features
    PyImGui.text_colored(
        "Features:",
        title_color.to_tuple_normalized(),
    )
    PyImGui.bullet_text("Full 3-level dungeon run")
    PyImGui.bullet_text("Normal / Hard Mode support")
    PyImGui.bullet_text("Multi-account support")
    PyImGui.bullet_text("Automatic inventory maintenance")
    PyImGui.bullet_text("Conset, PCons & Summoning Stones")
    PyImGui.bullet_text("Run time & drop statistics")
    PyImGui.bullet_text("Automatic quest handling")

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    # Credits
    PyImGui.text_colored(
        "Credits:",
        title_color.to_tuple_normalized(),
    )
    PyImGui.bullet_text("Developed by Sky")

    PyImGui.end_tooltip()



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
    tree.UI.draw_window(
        icon_path=TEXTURE,
        iconwidth=96,
        main_child_dimensions=(420, 380),
        extra_tabs=[
            ("Statistics", _draw_statistics),
            ("Config", _draw_run_config),
        ],
    )

if __name__ == "__main__":
    main()