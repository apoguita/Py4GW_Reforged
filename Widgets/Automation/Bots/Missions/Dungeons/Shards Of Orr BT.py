from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import time
import math
from Py4GWCoreLib.Listeners import Listeners
import PySystem
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.ImGui_src.types import Alignment
from Py4GWCoreLib.py4gwcorelib_src.Color import Color
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib import Agent, GLOBAL_CACHE, AgentArray, Map, Party, Player, Routines, SharedCommandType, Inventory, ImGui
from Py4GWCoreLib.enums import CONSUMABLE_MODELID_TO_EFFECT_NAME
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.enums_src.Player_enums import PlayerStatus
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import CONSET_UPKEEPS, CONSUMABLE_UPKEEPS as ALL_CONSUMABLE_UPKEEPS
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Py4GWCoreLib.Pathing import AutoPathing
from Sources.Sky.DungeonParty import DungeonPartyConfig
from Sources.Sky.Support import attach_botting_tree_support
from Sources.Sky.ConsumableRestockUI import draw_restock_group_grid
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Widgets.System.Messaging import get_inventory_count, reset_inventory_count, get_inventory_state, reset_inventory_state
import PyImGui


PathPoint = Vec2f | tuple[float, float] | tuple[int, int]


# region Script metadata

MODULE_NAME = "Shards of Orr BT"
MODULE_CATEGORY = "Automation"
MODULE_TAGS = [
    "Shards of Orr",
    "Dungeon",
    "BDS",
]
MODULE_ALIASES = [
    "SoO",
    "Shards",
    "Shards of Orr",
]
MODULE_DESCRIPTION = """Fully automated multibox BottingTree run for Shards of Orr.

The bot handles the Lost Souls quest, dungeon travel, all three dungeon levels,
torch and brazier mechanics, Fendi, the final chest, reward collection and the
next-run setup. It also includes configurable consumables, inventory
maintenance and multibox statistics.
"""

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

# Shards-only environmental trap handling. These GadgetIDs were confirmed by
# a full three-level probe run. Keep this local to Shards: 0x8000 is an
# activation bit used by other gadgets too, so it must never be treated as a
# global CoreLib trap rule.
SHARDS_TRAP_ACTIVE_BIT = 0x8000
SHARDS_TRAP_GADGET_IDS_BY_MAP: dict[int, frozenset[int]] = {
    SOO_LEVEL_1: frozenset(range(8164, 8174)),
    SOO_LEVEL_2: frozenset(range(8164, 8167)),
    SOO_LEVEL_3: frozenset((8015, 8035, *range(8142, 8149))),
}
# Level 2 corridors do not offer a reliable lateral bypass: when an active
# trap intersects the planned route, wait for its OFF cycle instead of steering
# around it.  GID 8143 has the same restriction on level 3.
SHARDS_TRAP_FORCE_PAUSE_MAPS: frozenset[int] = frozenset((SOO_LEVEL_2,))
SHARDS_TRAP_FORCE_PAUSE_IDS: frozenset[int] = frozenset((8143,))
SHARDS_TRAP_LOOKAHEAD = 1100.0
SHARDS_TRAP_ROUTE_HALF_WIDTH = 430.0
SHARDS_TRAP_HAZARD_RADIUS = 430.0
SHARDS_TRAP_STEERING_DISTANCE = 500.0
SHARDS_TRAP_AVOIDANCE_UPDATE_MS = 150.0
SHARDS_TRAP_NO_DETOUR_RELEASE_MS = 300.0

# Quest / dialogs
LOST_SOULS_QUEST_ID = 0x324
DWARVEN_BLESSING_DIALOG = 0x84
SHANDRA_TAKE_DIALOG = 0x832401
SHANDRA_REWARD_DIALOG = 0x832407
ARBOR_BLESSING_DIALOG = 0x84

# Consumables
SUMMON_MODEL_IDS = (37810,30209,31155)
# Party morale consumables are independent of personal PCons.
MORALE_CON_MODEL_IDS = (int(ModelID.Four_Leaf_Clover.value), int(ModelID.Honeycomb.value))
PCON_UPKEEPS = tuple(int(model_id) for model_id in ALL_CONSUMABLE_UPKEEPS
                     if int(model_id) not in CONSET_UPKEEPS and int(model_id) not in MORALE_CON_MODEL_IDS)

# Per-item restock targets are persisted by this script and sent to every
# account in the current in-game party. 0 disables restock for that item.
RESTOCK_ITEM_DEFINITIONS: tuple[tuple[str, str, int, str, int], ...] = (
    ("Conset", "Essence of Celerity", int(ModelID.Essence_Of_Celerity.value), "RestockQtyEssenceOfCelerity", 10),
    ("Conset", "Grail of Might", int(ModelID.Grail_Of_Might.value), "RestockQtyGrailOfMight", 10),
    ("Conset", "Armor of Salvation", int(ModelID.Armor_Of_Salvation.value), "RestockQtyArmorOfSalvation", 10),
    ("Personal PCons", "Birthday Cupcake", int(ModelID.Birthday_Cupcake.value), "RestockQtyBirthdayCupcake", 10),
    ("Personal PCons", "Golden Egg", int(ModelID.Golden_Egg.value), "RestockQtyGoldenEgg", 10),
    ("Personal PCons", "Candy Corn", int(ModelID.Candy_Corn.value), "RestockQtyCandyCorn", 10),
    ("Personal PCons", "Candy Apple", int(ModelID.Candy_Apple.value), "RestockQtyCandyApple", 10),
    ("Personal PCons", "Pumpkin Pie", int(ModelID.Slice_Of_Pumpkin_Pie.value), "RestockQtyPumpkinPie", 10),
    ("Personal PCons", "Drake Kabob", int(ModelID.Drake_Kabob.value), "RestockQtyDrakeKabob", 10),
    ("Personal PCons", "Bowl of Skalefin Soup", int(ModelID.Bowl_Of_Skalefin_Soup.value), "RestockQtySkalefinSoup", 10),
    ("Personal PCons", "Pahnai Salad", int(ModelID.Pahnai_Salad.value), "RestockQtyPahnaiSalad", 10),
    ("Personal PCons", "War Supplies", int(ModelID.War_Supplies.value), "RestockQtyWarSupplies", 10),
    ("Morale", "Four-Leaf Clover", int(ModelID.Four_Leaf_Clover.value), "RestockQtyFourLeafClover", 10),
    ("Morale", "Honeycomb", int(ModelID.Honeycomb.value), "RestockQtyHoneycomb", 10),
    ("Summoning", "Legionnaire Summoning Crystal", int(ModelID.Legionnaire_Summoning_Crystal.value), "RestockQtyLegionnaireCrystal", 10),
    ("Summoning", "Tengu Summoning Stone", int(ModelID.Tengu_Summon.value), "RestockQtyTenguSummon", 10),
    ("Summoning", "Mysterious Summoning Stone", int(ModelID.Mysterious_Summon.value), "RestockQtyMysteriousSummon", 10),
)
RESTOCK_DEFAULTS = {model_id: default for _group, _label, model_id, _key, default in RESTOCK_ITEM_DEFINITIONS}
RESTOCK_SETTING_KEYS = {model_id: key for _group, _label, model_id, key, _default in RESTOCK_ITEM_DEFINITIONS}

# Final chest drops tracked by the statistics tab.
BDS_MODEL_IDS = tuple(range(1987, 2008))
BDS_MODEL_ID_MIN = BDS_MODEL_IDS[0]
BDS_MODEL_ID_MAX = BDS_MODEL_IDS[-1]
GB_MODEL_ID = 2474

INVENTORY_BAG_IDS = frozenset((1, 2, 3, 4))
ID_KIT_MODEL_IDS = (int(ModelID.Superior_Identification_Kit.value),)
SALVAGE_KIT_MODEL_IDS = (int(ModelID.Superior_Salvage_Kit.value),)
MERCHANT_RULES_WIDGET_NAME = "MerchantRules"
INVENTORY_PLUS_WIDGET_NAME = "InventoryPlus"

INVENTORY_TRAVEL_REGION = 2      # Europe
INVENTORY_TRAVEL_DISTRICT = 1    # Europe English District 1
INVENTORY_TRAVEL_LANGUAGE = 0    # English
INVENTORY_MAINTENANCE_RETRY_COUNT = 2
INVENTORY_SNAPSHOT_SETTLE_MS = 2_000
INVENTORY_TRAVEL_TIMEOUT_MS = 60_000
INVENTORY_MERCHANT_TIMEOUT_MS = 240_000

TEXTURE = os.path.join(PySystem.Console.get_projects_path(), 'Assets', 'Textures', 'Module_Icons', 'BDS.png')
MODULE_ICON = "Assets\\Textures\\Module_Icons\\BDS.png"

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
_dungeon_party = DungeonPartyConfig(_settings_ini)
_settings_loaded = False

_use_hard_mode = True
_restock_conset = True
_activate_conset = True
_restock_pcons = True
_activate_pcons = True
_restock_morale_cons = True
_activate_morale_cons = True
_use_summoning_stone = True
_restock_quantities: dict[int, int] = dict(RESTOCK_DEFAULTS)
_inventory_maintenance_enabled = True
_inventory_min_free_slots = 5
_inventory_min_id_kits = 1
_inventory_min_salvage_kits = 2
_runtime_consumables_enabled = True
_configured_consumable_upkeeps: tuple[int, ...] | None = None

# Personal consumables are maintained directly across the real multibox party.
# Consets keep using the normal ConfigureUpkeep service.
_PCON_DIRECT_DISPATCH_INTERVAL_MS = 650
PCON_USAGE_LOG = False  # Set True only for PCon consumption diagnostics.
_pcon_direct_index = 0
_pcon_direct_last_dispatch_ms = 0
_pcon_direct_runtime_logged = False
_pcon_direct_last_recipient_signature: tuple[str, ...] = ()
_pcon_direct_morale_remote_index = 0
_PCON_PARTY_MORALE_TARGET_BY_MODEL = {
    int(ModelID.Four_Leaf_Clover.value): 100,
    int(ModelID.Honeycomb.value): 110,
}

_runtime_looting_enabled = True
_inventory_status_snapshot: dict[str, dict[str, object]] = {}

# Resolved before a torch is picked up because carrying a bundle can hide the
# equipped weapon type reported by the game.  Martial builds automatically
# drop the torch for combat; caster builds keep it.
_drop_torch_for_combat: bool | None = None
# Last position where a martial leader intentionally dropped the torch for
# combat. PickupTorch can retrace to this point if the fight pulls the player
# farther away than the normal ground-item pickup radius.
_last_torch_drop_position: tuple[float, float] | None = None
# Set from the Core planner restart metadata after a shrine recovery. While
# active, a missing torch may be skipped briefly while the route is retraced
# toward the death location where the dropped torch can still be recovered.
_shrine_recovery_torch_skip_active = False

# Run-local one-shot mechanic state. These flags survive the BottingTree
# Reset()/Start() performed by a shrine restart, but are cleared on a genuinely
# fresh dungeon pass. They make already-completed chest/door/brazier actions
# restart-safe when the Core intentionally resumes from an earlier route anchor.
_restart_safe_completed_mechanics: set[str] = set()
_restart_safe_opened_torch_chests: set[str] = set()
_LEVEL3_BOSS_ROUTE_UNLOCKED_KEY = "level3_boss_route_unlocked"

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

L1_PATH = [Vec2f(-5698.70, 9494.41), Vec2f(3720.16, 15370.78), Vec2f(6740.06, 11039.32), Vec2f(15757, 16952), Vec2f(16026.25, 16957.26), Vec2f(14255.37, 6189.6)]

L1_PATH_AFTER_DOOR = [Vec2f(17442.4, 2577.83), Vec2f(20181.6, 1203.7), Vec2f(20400.5, 1300.0)]

# Level 2 routes / torch mechanics
TORCH_MODEL_IDS = (22341, 22342)
TORCH_BUFF_ID = 2545
# Temporary diagnostic mode for torch pickup. Disable after testing.
TORCH_DIAGNOSTICS = False
TORCH_PROGRESS_LOGS = False
SHARDS_MOVEMENT_LOGS = False
TORCH_DIAGNOSTIC_INTERVAL_MS = 3_000
TORCH_INITIAL_RETRACE_GRACE_MS = 1_000
# Martial leaders keep carrying the torch until enemies are genuinely close.
# This only controls the automatic torch DROP trigger; Vanquish clear radii
# remain unchanged.
TORCH_COMBAT_TRIGGER_RADIUS = Range.Spirit.value

L2_BLESSING_NPC = Vec2f(-14076.0, -19457.0)


L2_TORCH_CHEST = Vec2f(-14709.0, -16548.0)
L2_FIRST_TORCH_DROP_POINT_PATH = [Vec2f(-11002.0, -17001.0)]
L2_RETURN_TO_FIRST_TORCH_PATH = [Vec2f(-9259.0, -17322.0), Vec2f(-9550, -17258), Vec2f(-10243, -17780)]
L2_BRAZIER_PART1 = [(-11303.0, -14596.0), (-11019.0, -11550.0), (-9028.0, -9021.0), (-6805.0, -11511.0), (-8984.0, -13842.0)]
L2_TO_ROOM2_DROP = (Vec2f(-10514.69, -9542.61), Vec2f(-11061.1, -7578.5))
L2_RETURN_TO_ROOM2_TORCH_PATH = [Vec2f(-10958.2, -4529.5), Vec2f(-11690.64, -3802.55)]
L2_ROOM2_PATH = [Vec2f(-8066.1, -4222.4), Vec2f(-7058.8, -4191.0)]

L2_BRAZIER_PART2 = [(-3717.0, -4254.0), (-8251.0, -3240.0), (-8278.0, -1670.0)]
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

# Stable position used to stage the leader before the final chest interaction.
FENDI_CHEST_SAFE_POSITION = Vec2f(-15766.63, 17397.07)

initialized = False
botting_tree: BottingTree | None = None


# Shrine wipe recovery is provided by Py4GWCoreLib.


# endregion

# region Run config

def _load_settings() -> None:
    global _settings_loaded
    global _use_hard_mode, _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons, _restock_morale_cons, _activate_morale_cons, _use_summoning_stone
    global _restock_quantities
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
    # Migrate old configs conservatively: Morale Cons previously followed the PCon switches.
    _restock_morale_cons = _settings_ini.get_bool(_SETTINGS_SECTION, "RestockMoraleCons", _restock_pcons)
    _activate_morale_cons = _settings_ini.get_bool(_SETTINGS_SECTION, "ActivateMoraleCons", _activate_pcons)
    _use_summoning_stone = _settings_ini.get_bool(_SETTINGS_SECTION, "UseSummoningStone", True)
    _restock_quantities = {
        model_id: max(0, _settings_ini.get_int(_SETTINGS_SECTION, setting_key, RESTOCK_DEFAULTS[model_id]))
        for model_id, setting_key in RESTOCK_SETTING_KEYS.items()
    }
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
    _settings_ini.set(_SETTINGS_SECTION, "RestockMoraleCons", _restock_morale_cons)
    _settings_ini.set(_SETTINGS_SECTION, "ActivateMoraleCons", _activate_morale_cons)
    _settings_ini.set(_SETTINGS_SECTION, "UseSummoningStone", _use_summoning_stone)
    for model_id, setting_key in RESTOCK_SETTING_KEYS.items():
        _settings_ini.set(_SETTINGS_SECTION, setting_key, max(0, int(_restock_quantities.get(model_id, 0))))
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

    # Ignore the synthetic "local" key because it is not an account identifier.
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


def _consumables_allowed() -> bool:
    return (
        _runtime_consumables_enabled
        and Map.IsMapReady()
        and not Map.IsMapLoading()
        and Map.GetMapID() in (SOO_LEVEL_1, SOO_LEVEL_2, SOO_LEVEL_3)
    )


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    """Generic Core upkeep services. PCons use the direct dispatcher."""
    if not _runtime_consumables_enabled:
        return ()
    enabled: list[int] = []
    if _activate_conset:
        enabled.extend(int(model_id) for model_id in CONSET_UPKEEPS)
    return tuple(dict.fromkeys(enabled))


def _pcon_effect_name(model_id: int) -> str:
    """Resolve the persistent effect used by SharedCommandType.PCon."""
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

    if not _bot_is_started() or not _runtime_consumables_enabled or not (_activate_pcons or _activate_morale_cons):
        if _pcon_direct_runtime_logged or _pcon_direct_last_dispatch_ms:
            _reset_direct_pcon_runtime()
        return

    try:
        if not Map.IsMapReady() or not Map.IsExplorable():
            return
        if int(Map.GetMapID() or 0) not in (SOO_LEVEL_1, SOO_LEVEL_2, SOO_LEVEL_3):
            return
    except Exception:
        return

    enabled_models = ((PCON_UPKEEPS if _activate_pcons else ()) +
                      (MORALE_CON_MODEL_IDS if _activate_morale_cons else ()))
    if not enabled_models:
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
            f"[Consumables] Direct multibox upkeep: pcons={len(PCON_UPKEEPS) if _activate_pcons else 0}, "
            f"morale_cons={len(MORALE_CON_MODEL_IDS) if _activate_morale_cons else 0}, accounts={len(recipients)}.",
            PySystem.Console.MessageType.Info,
        )

    model_id = int(enabled_models[_pcon_direct_index % len(enabled_models)])
    _pcon_direct_index = (_pcon_direct_index + 1) % len(enabled_models)

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

def _configure_runtime_upkeeps(*, consumables_enabled: bool | None = None, looting_enabled: bool | None = None) -> None:
    global _runtime_consumables_enabled, _runtime_looting_enabled, _configured_consumable_upkeeps

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
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=enabled_consumables,
        enable_party_member_recovery=True,
        party_member_recovery_distance=500.0,
        enable_party_wipe_recovery=True,
        enable_nearest_shrine_recovery=True,
        heroai_state_logging=False,
    )
    # ConfigureUpkeep rebuilds the service list. Reinstall the reusable Core
    # multibox summoning service; the UI flag is read live by the service.
    botting_tree.EnsureSummoningStonePartyService(
        enabled=lambda: _use_summoning_stone and _consumables_allowed(),
        map_ids=(SOO_LEVEL_1, SOO_LEVEL_2, SOO_LEVEL_3),
        initial_grace_ms=2_000,
        attempt_interval_ms=5_000,
        retry_cycle_delay_ms=15_000,
        log=True,
    )
    _configured_consumable_upkeeps = enabled_consumables


def _sync_consumable_upkeeps() -> None:
    # Direct PCons are tick-driven; only Core conset services need resyncing.
    if _enabled_consumable_upkeeps() != _configured_consumable_upkeeps:
        _configure_runtime_upkeeps()


def _runtime_consumable_upkeep_node(enabled: bool) -> BehaviorTree:
    """Enable or suspend conset + direct PCon upkeep at runtime."""
    def _apply(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if botting_tree is None:
            return BehaviorTree.NodeState.FAILURE
        if _runtime_consumables_enabled != bool(enabled):
            _configure_runtime_upkeeps(consumables_enabled=enabled)
            PySystem.Console.Log(
                MODULE_NAME,
                'Consumable upkeep resumed for the dungeon run.' if enabled else 'Consumable upkeep suspended during the end-of-dungeon return sequence.',
                PySystem.Console.MessageType.Info,
            )
        return BehaviorTree.NodeState.SUCCESS
    return BehaviorTree(BehaviorTree.ActionNode(
        name='Resume Consumable Upkeep' if enabled else 'Suspend Consumable Upkeep',
        action_fn=_apply,
        aftercast_ms=0,
    ))


def _draw_run_config() -> None:
    import PyImGui

    global _use_hard_mode
    global _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons
    global _restock_morale_cons, _activate_morale_cons
    global _use_summoning_stone
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
        _reset_direct_pcon_runtime()
        changed = True

    PyImGui.separator()
    PyImGui.text("Morale consumables (party-wide)")
    value = PyImGui.checkbox('Restock morale cons from storage', _restock_morale_cons)
    if value != _restock_morale_cons:
        _restock_morale_cons = value
        changed = True

    value = PyImGui.checkbox('Activate / maintain morale cons', _activate_morale_cons)
    if value != _activate_morale_cons:
        _activate_morale_cons = value
        _reset_direct_pcon_runtime()
        changed = True
    PyImGui.text_wrapped('Four-Leaf Clover below 100 morale; Honeycomb below 110. Independent of personal PCons.')

    PyImGui.separator()
    PyImGui.text("Summoning stones")

    value = PyImGui.checkbox('Use summoning stones', _use_summoning_stone)
    if value != _use_summoning_stone:
        _use_summoning_stone = value
        changed = True
        # The reusable Core SummoningStonePartyService reads this flag live,
        # so no ConfigureUpkeep rebuild is required here.

    PyImGui.separator()
    PyImGui.text("Torch handling")
    PyImGui.text_wrapped(
        "Automatic: martial builds drop the torch only when combat reaches them, "
        "then recover it after the combat step. Caster builds keep carrying it."
    )

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

        value = PyImGui.input_int('Minimum Superior ID kits (0 = disabled)', _inventory_min_id_kits)
        value = max(0, int(value))
        if value != _inventory_min_id_kits:
            _inventory_min_id_kits = value
            changed = True

        value = PyImGui.input_int('Minimum Superior salvage kits (0 = disabled)', _inventory_min_salvage_kits)
        value = max(0, int(value))
        if value != _inventory_min_salvage_kits:
            _inventory_min_salvage_kits = value
            changed = True

        PyImGui.text_wrapped("MerchantRules executes the currently loaded Shards of Orr profile from SharedProfiles.json. The Superior ID / Salvage thresholds above are also sent directly with the execute request and are applied temporarily without changing the profile. If any active account falls below a configured threshold, all active accounts are processed together. Inventory space, Superior ID Kits and Superior Salvage Kits are queried locally on every active client, so each account uses its own real bag capacity. Equipment Pack is excluded.")

    if changed:
        _save_settings()

    if upkeep_changed:
        _configure_runtime_upkeeps()


def _draw_restock_config() -> None:
    global _restock_quantities

    _load_settings()
    changed = False

    PyImGui.text("Restock targets per account")
    PyImGui.text_wrapped(
        "Set the target quantity shown below each icon. The same target is sent to "
        "every account in the current party, and each account only withdraws what "
        "it is missing from its own Xunlai storage. Set a target to 0 to disable "
        "that item."
    )
    PyImGui.text_wrapped(
        "Hover an icon for the item name, ModelID and current restock state."
    )

    group_enabled = {
        "Conset": bool(_restock_conset),
        "Personal PCons": bool(_restock_pcons),
        "Morale": bool(_restock_morale_cons),
        "Summoning": bool(_use_summoning_stone),
    }

    groups: dict[str, list[tuple[str, int, int]]] = {}
    for group, label, model_id, _setting_key, default in RESTOCK_ITEM_DEFINITIONS:
        groups.setdefault(group, []).append((label, int(model_id), int(default)))

    for group in ("Conset", "Personal PCons", "Morale", "Summoning"):
        items = groups.get(group, [])
        if not items:
            continue
        if draw_restock_group_grid(
            group,
            items,
            _restock_quantities,
            group_enabled=group_enabled.get(group, True),
            columns=4,
            icon_size=48.0,
        ):
            changed = True

    PyImGui.separator()
    PyImGui.text_wrapped(
        "The group switches in the Config tab control whether Conset, Personal PCons, "
        "Morale consumables and Summoning Stones are included in the restock step. "
        "Disabling a group never deletes its saved per-item targets."
    )

    if changed:
        _save_settings()


def _runtime_difficulty_node() -> BehaviorTree:
    return BT.Subtree(name='Apply Selected Difficulty', subtree_fn=lambda _node: BT.SetHardMode(_use_hard_mode, log=True))


def _runtime_restock_node() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        enabled_models: set[int] = set()

        if _restock_conset:
            enabled_models.update(int(model_id) for model_id in CONSET_UPKEEPS)
        if _restock_pcons:
            enabled_models.update(int(model_id) for model_id in PCON_UPKEEPS)
        if _restock_morale_cons:
            enabled_models.update(int(model_id) for model_id in MORALE_CON_MODEL_IDS)
        if _use_summoning_stone:
            enabled_models.update(int(model_id) for model_id in SUMMON_MODEL_IDS)

        items = [
            (model_id, max(0, int(_restock_quantities.get(model_id, default))))
            for _group, _label, model_id, _setting_key, default in RESTOCK_ITEM_DEFINITIONS
            if model_id in enabled_models
            and max(0, int(_restock_quantities.get(model_id, default))) > 0
        ]
        if not items:
            return BT.Succeeder('RestockDisabled')

        return BTShared.RestockItems(
            items,
            party_only=True,
            include_self=True,
            allow_missing=True,
            refs_blackboard_prefix='shards_restock_item',
            timeout_ms=30_000,
            poll_interval_ms=100,
            log=True,
        )

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
                f"occupied={status['occupied']}, Superior ID kits={status['id_kits']}, "
                f"Superior salvage kits={status['salvage_kits']} -> {result}"
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
                    f"Superior ID kits={status['id_kits']}, "
                    f"Superior salvage kits={status['salvage_kits']}, "
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
        ],
    )

    return BT.Selector(name="Ensure Every Account Is In Vlox's Falls", children=[_all_accounts_on_map_node(VLOXS_FALL, "Every Account Already In Vlox's Falls"), resign_from_explorable, _travel_all_accounts_to_vlox(attempt_key)])


def _restore_inventoryplus_after_merchant(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(name='Restore InventoryPlus After MerchantRules', children=[_send_widget_state(INVENTORY_PLUS_WIDGET_NAME, enabled=True, refs_key=f'{attempt_key}_enable_inventoryplus_refs'), _set_local_auto_inventory_handler(True)])


def _merchant_stock_request_spec() -> str:
    """Encode this bot's desired carried Merchant Stock targets for MerchantRules."""
    targets: list[str] = []
    if _inventory_min_id_kits > 0 and ID_KIT_MODEL_IDS:
        targets.append(f"{int(ID_KIT_MODEL_IDS[0])}:{int(_inventory_min_id_kits)}")
    if _inventory_min_salvage_kits > 0 and SALVAGE_KIT_MODEL_IDS:
        targets.append(f"{int(SALVAGE_KIT_MODEL_IDS[0])}:{int(_inventory_min_salvage_kits)}")
    return "stock:" + ",".join(targets) if targets else ""


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
            extra_data=(request_id, _merchant_stock_request_spec(), "0", "0"),
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

    MerchantRules stays disabled outside the actual maintenance window. Any
    failure restores InventoryPlus and disables MerchantRules before retrying.
    """
    attempt_key = f"inventory_attempt_{attempt_number}"

    normal_attempt = BT.Sequence(
        name=f"Inventory Maintenance Attempt {attempt_number} - Run",
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
            _query_all_inventory_states_node(
                name=f"Refresh Real Inventories After Attempt {attempt_number}"
            ),
            _inventory_is_healthy_node(
                f"Verify Inventory After Attempt {attempt_number}",
                log_success=True,
            ),
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                enabled=False,
                refs_key=f"{attempt_key}_disable_merchant_rules_success_refs",
            ),
        ],
    )

    cleanup_failure = BT.Sequence(
        name=f"Inventory Maintenance Attempt {attempt_number} - Cleanup Failure",
        children=[
            _restore_inventoryplus_after_merchant(f"{attempt_key}_cleanup"),
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                enabled=False,
                refs_key=f"{attempt_key}_disable_merchant_rules_failure_refs",
            ),
            BehaviorTree(
                BehaviorTree.FailerNode(
                    name=f"Inventory Maintenance Attempt {attempt_number} Failed"
                )
            ),
        ],
    )

    return BT.Selector(
        name=f"Inventory Maintenance Attempt {attempt_number}",
        children=[normal_attempt, cleanup_failure],
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
    # MerchantRules is OFF during normal gameplay and inventory inspection. It is
    # enabled only inside a real maintenance attempt, then disabled again on both
    # success and failure paths.
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
                enabled=False,
                refs_key="inventory_disabled_merchant_off_refs",
            ),
        ],
    )

    maintenance_attempts = [
        _inventory_maintenance_attempt(attempt_number)
        for attempt_number in range(1, INVENTORY_MAINTENANCE_RETRY_COUNT + 1)
    ]
    maintenance_attempts.append(_stop_for_inventory_failure_node())

    enabled_flow = BT.Sequence(
        name="Enabled Inventory Check And Maintenance",
        children=[
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                enabled=False,
                refs_key="inventory_check_merchant_off_refs",
            ),
            _query_all_inventory_states_node(
                name="Query Real Inventory State On Every Active Account"
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
                            _inventory_maintenance_trigger_node(),
                            _send_widget_state(
                                MERCHANT_RULES_WIDGET_NAME,
                                enabled=False,
                                refs_key="inventory_before_travel_merchant_off_refs",
                            ),
                            _return_all_accounts_to_vlox("inventory_maintenance_setup"),
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
        children=[disabled, enabled_flow],
    )

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


def _shared_inventory_count(
    account: object,
    model_id_min: int,
    model_id_max: int,
) -> int | None:
    """Read an item count from the shared-memory inventory mirror.

    InventoryQuery remains the fallback until the mirror becomes available.
    """
    inventory_bags = getattr(account, "InventoryBags", None)
    if inventory_bags is None:
        return None

    try:
        bags = list(inventory_bags.iter_bags())
    except Exception:
        return None

    # No published bag structures means the mirror is not ready. Once bag
    # structures exist, an empty count is a valid zero.
    if not bags:
        return None

    minimum = int(model_id_min)
    maximum = int(model_id_max)
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
                if minimum <= model_id <= maximum:
                    total += max(0, int(getattr(slot, "Quantity", 0) or 0))
    except Exception:
        return None

    return total if saw_slots_container else None


def _inventory_statistics_node(*, after_chest: bool) -> BehaviorTree:
    node_name = 'Record Drops After Final Chest' if after_chest else 'Snapshot Inventories At Dungeon Entry'
    state: dict[str, object] = {
        'started': False,
        'local_email': '',
        'account_keys': [],
        'pending': {},
        'request_started_at': 0.0,
        'local_email_wait_started_at': 0.0,
        'mirror_count': 0,
    }

    def _reset() -> None:
        state['started'] = False
        state['local_email'] = ''
        state['account_keys'] = []
        state['pending'] = {}
        state['request_started_at'] = 0.0
        state['local_email_wait_started_at'] = 0.0
        state['mirror_count'] = 0

    def _start() -> bool:
        _load_statistics()
        _refresh_character_names()

        local_email = str(Player.GetAccountEmail() or '').strip()
        if not local_email:
            return False

        local_key = _account_key(local_email)
        bds_section = _BDS_RUN_SECTION if after_chest else _BDS_SNAPSHOT_SECTION
        gb_section = _GB_RUN_SECTION if after_chest else _GB_SNAPSHOT_SECTION

        _settings_ini.set(
            bds_section,
            local_key,
            _inventory_count(BDS_MODEL_ID_MIN, BDS_MODEL_ID_MAX),
        )
        _settings_ini.set(
            gb_section,
            local_key,
            _inventory_count(GB_MODEL_ID, GB_MODEL_ID),
        )

        account_keys = [local_key]
        pending: dict[str, dict[str, object]] = {}
        mirror_count = 0

        for account in _shared_accounts():
            email = str(getattr(account, 'AccountEmail', '') or '').strip()
            if not email or email == local_email:
                continue

            key = _account_key(email)
            if key not in account_keys:
                account_keys.append(key)

            requests = (
                ('BDS', BDS_MODEL_ID_MIN, BDS_MODEL_ID_MAX, bds_section),
                ('Glacial Blades', GB_MODEL_ID, GB_MODEL_ID, gb_section),
            )

            for label, model_min, model_max, section in requests:
                mirrored_count = _shared_inventory_count(
                    account, int(model_min), int(model_max)
                )

                if mirrored_count is not None:
                    _settings_ini.set(section, key, int(mirrored_count))
                    mirror_count += 1
                    continue

                # Mirror unavailable: dispatch the fallback immediately. Every
                # missing BDS/GB request is sent together and shares one timeout.
                reset_inventory_count(email, int(model_min), int(model_max))
                _settings_ini.set(section, key, -1)
                GLOBAL_CACHE.ShMem.SendMessage(
                    local_email,
                    email,
                    SharedCommandType.InventoryQuery,
                    (float(model_min), float(model_max), 0.0, 0.0),
                    ('report_inventory_count',),
                )

                pending_key = f'{email}|{int(model_min)}|{int(model_max)}'
                pending[pending_key] = {
                    'email': email,
                    'key': key,
                    'model_min': int(model_min),
                    'model_max': int(model_max),
                    'section': section,
                    'label': label,
                }

        for key in account_keys:
            _bds_drops.setdefault(key, 0)
            _gb_drops.setdefault(key, 0)

        state['started'] = True
        state['local_email'] = local_email
        state['account_keys'] = account_keys
        state['pending'] = pending
        state['mirror_count'] = mirror_count
        state['request_started_at'] = time.monotonic() if pending else 0.0
        state['local_email_wait_started_at'] = 0.0

        if pending:
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f'[Statistics] Inventory snapshot: {mirror_count} mirrored value(s) read directly; '
                    f'{len(pending)} InventoryQuery fallback request(s) sent in parallel.'
                ),
                PySystem.Console.MessageType.Info,
            )

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

        total_bds = 0
        total_gb = 0
        for key in state['account_keys']:
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
        PySystem.Console.Log(
            MODULE_NAME,
            f'[Statistics] Final chest recorded - BDS {total_bds} | Glacial Blades {total_gb}',
            PySystem.Console.MessageType.Success,
        )

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if bool(node.blackboard.get('USER_INTERRUPT_ACTIVE', False)):
                _reset()
                return BehaviorTree.NodeState.FAILURE

            if not bool(state['started']):
                if not _start():
                    now = time.monotonic()
                    wait_started = float(state['local_email_wait_started_at'] or 0.0)
                    if wait_started <= 0.0:
                        state['local_email_wait_started_at'] = now
                        return BehaviorTree.NodeState.RUNNING
                    if (now - wait_started) * 1000.0 < _INVENTORY_QUERY_TIMEOUT_MS:
                        return BehaviorTree.NodeState.RUNNING

                    PySystem.Console.Log(
                        MODULE_NAME,
                        "[Statistics] Local account email was unavailable; skipping this statistics snapshot instead of creating a synthetic 'local' account.",
                        PySystem.Console.MessageType.Warning,
                    )
                    _reset()
                    return BehaviorTree.NodeState.SUCCESS

            pending: dict[str, dict[str, object]] = state['pending']

            for pending_key in list(pending):
                request = pending[pending_key]
                email = str(request['email'])
                model_min = int(request['model_min'])
                model_max = int(request['model_max'])
                count = int(get_inventory_count(email, model_min, model_max))

                if count < 0:
                    continue

                _settings_ini.set(
                    str(request['section']),
                    str(request['key']),
                    count,
                )
                pending.pop(pending_key, None)

            if pending:
                elapsed_ms = (
                    time.monotonic() - float(state['request_started_at'] or 0.0)
                ) * 1000.0
                if elapsed_ms < _INVENTORY_QUERY_TIMEOUT_MS:
                    return BehaviorTree.NodeState.RUNNING

                for pending_key, request in list(pending.items()):
                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            f"[Statistics] {request['label']} inventory fallback timed out on "
                            f"{_account_label(str(request['key']))}."
                        ),
                        PySystem.Console.MessageType.Warning,
                    )
                    pending.pop(pending_key, None)

            _finish()
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f'[Statistics] {node_name} failed: {exc}',
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


def _is_core_shrine_resume(node: BehaviorTree.Node) -> bool:
    return str(node.blackboard.get("planner_restart_reason", "") or "") == "shrine"


def _reset_restart_safe_run_state_node() -> BehaviorTree:
    """Clear one-shot mechanic state only for a genuinely fresh dungeon pass."""
    def _reset(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _shrine_recovery_torch_skip_active

        if _is_core_shrine_resume(node):
            return BehaviorTree.NodeState.SUCCESS

        _restart_safe_completed_mechanics.clear()
        _restart_safe_opened_torch_chests.clear()
        _shrine_recovery_torch_skip_active = False
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Reset Restart-Safe Run State",
            action_fn=_reset,
            aftercast_ms=0,
        )
    )


def _mark_restart_safe_mechanic_node(key: str) -> BehaviorTree:
    def _mark(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        _restart_safe_completed_mechanics.add(str(key))
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Mark Restart-Safe Mechanic Complete ({key})",
            action_fn=_mark,
            aftercast_ms=0,
        )
    )


def _skip_if_level3_boss_route_unlocked(
    step_name: str,
    factory: Callable[[], BehaviorTree],
) -> tuple[str, Callable[[], BehaviorTree]]:
    """Skip obsolete pre-boss Level 3 steps after a shrine restart.

    Level 3 passes the same shrine during the torch phase and again on the boss
    route. Once Brigant and its loot are complete, an old nearby shrine anchor
    may still be selected by the generic Core resolver. Those earlier steps are
    no longer valid for this run, so they complete immediately until the planner
    reaches the Brigant door / Fendi route again.
    """

    def _build(node: BehaviorTree.Node) -> BehaviorTree:
        if (
            _is_core_shrine_resume(node)
            and _LEVEL3_BOSS_ROUTE_UNLOCKED_KEY in _restart_safe_completed_mechanics
        ):
            return BT.Succeeder(f"{step_name} Skipped - Level 3 Boss Route Already Unlocked")
        return factory()

    def _factory() -> BehaviorTree:
        return BT.Subtree(
            name=f"Restart Safe Level 3 Phase ({step_name})",
            subtree_fn=_build,
        )

    return step_name, _factory


def _mark_torch_chest_opened_node(key: str) -> BehaviorTree:
    def _mark(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        _restart_safe_opened_torch_chests.add(str(key))
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Mark Torch Chest Opened ({key})",
            action_fn=_mark,
            aftercast_ms=0,
        )
    )


def RestartSafeGadgetInteraction(
    key: str,
    pos: Vec2f,
    *,
    pause_on_combat: bool = False,
    log: bool = True,
) -> BehaviorTree:
    """Replay a one-shot gadget interaction safely after shrine recovery."""
    def _build(node: BehaviorTree.Node) -> BehaviorTree:
        if _is_core_shrine_resume(node) and key in _restart_safe_completed_mechanics:
            return BT.Succeeder(f"{key} Already Completed Before Shrine Wipe")

        return BT.Sequence(
            name=f"Ensure {key}",
            children=[
                BT.MoveAndInteractWithGadget(
                    pos,
                    pause_on_combat=pause_on_combat,
                    log=log,
                ),
                _mark_restart_safe_mechanic_node(key),
            ],
        )

    return BT.Subtree(name=f"Restart Safe Gadget ({key})", subtree_fn=_build)


def RestartSafeBrazierSequence(
    key: str,
    name: str,
    points: list[tuple[float, float]],
) -> BehaviorTree:
    """Skip a brazier route already completed before the shrine wipe."""
    def _build(node: BehaviorTree.Node) -> BehaviorTree:
        if _is_core_shrine_resume(node) and key in _restart_safe_completed_mechanics:
            return BT.Succeeder(f"{name} Already Completed Before Shrine Wipe")

        return BT.Sequence(
            name=f"{name} - Restart Safe",
            children=[
                BrazierSequence(name, points),
                _mark_restart_safe_mechanic_node(key),
            ],
        )

    return BT.Subtree(name=f"Restart Safe {name}", subtree_fn=_build)


def EnsureTorchFromChest(
    key: str,
    chest_pos: Vec2f,
) -> BehaviorTree:
    """Open a torch chest once and make a replay safe after shrine recovery.

    If the chest was already consumed before the wipe and the torch is no longer
    nearby, the resumed route is allowed to continue toward the death location.
    The torch-aware route points keep trying to recover the dropped torch.
    """
    def _build(node: BehaviorTree.Node) -> BehaviorTree:
        global _shrine_recovery_torch_skip_active

        if _is_holding_bundle():
            _restart_safe_opened_torch_chests.add(key)
            return BT.Succeeder(f"{key} Torch Already Held")

        ground_torch = _find_ground_torch()
        if ground_torch and ground_torch > 0:
            _restart_safe_opened_torch_chests.add(key)
            return PickupTorch()

        if (
            _is_core_shrine_resume(node)
            and key in _restart_safe_opened_torch_chests
        ):
            _shrine_recovery_torch_skip_active = True
            return BT.Succeeder(f"{key} Already Opened - Retrace To Dropped Torch")

        return BT.Sequence(
            name=f"Open {key} And Recover Torch",
            children=[
                BT.MoveAndInteractWithGadget(
                    chest_pos,
                    pause_on_combat=False,
                    log=False,
                ),
                _mark_torch_chest_opened_node(key),
                PickupTorch(),
            ],
        )

    return BT.Subtree(name=f"Ensure Torch Source ({key})", subtree_fn=_build)


def _resolve_torch_combat_policy() -> bool:
    """Return True when the leader must drop the torch before combat."""
    global _drop_torch_for_combat

    if _drop_torch_for_combat is not None:
        return _drop_torch_for_combat

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
            reason = f"martial primary profession detected: {primary_profession}"
        elif primary_profession:
            _drop_torch_for_combat = False
            reason = f"caster primary profession detected: {primary_profession}"
        else:
            # Safe fallback: an unknown build must not be forced to fight while
            # the torch occupies its weapon slot.
            _drop_torch_for_combat = True
            reason = "weapon and profession are unknown; safe fallback"

    PySystem.Console.Log(
        MODULE_NAME,
        f"Torch combat policy: {('DROP' if _drop_torch_for_combat else 'KEEP')} ({reason}).",
        PySystem.Console.MessageType.Info,
    )
    return _drop_torch_for_combat


def ResolveTorchCombatPolicy() -> BehaviorTree:
    def _resolve(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        _resolve_torch_combat_policy()
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Resolve Torch Combat Policy',
            action_fn=_resolve,
            aftercast_ms=0,
        )
    )


def ResetTorchCombatPolicy() -> BehaviorTree:
    def _reset(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _drop_torch_for_combat, _shrine_recovery_torch_skip_active
        global _last_torch_drop_position
        _drop_torch_for_combat = None
        _shrine_recovery_torch_skip_active = False
        _last_torch_drop_position = None
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Reset Torch Combat Policy',
            action_fn=_reset,
            aftercast_ms=0,
        )
    )


def _bundle_released_check(name: str) -> BehaviorTree:
    """Succeed only after the player is confirmed to no longer hold a bundle."""

    def _check() -> BehaviorTree.NodeState:
        return (
            BehaviorTree.NodeState.SUCCESS
            if not _is_holding_bundle()
            else BehaviorTree.NodeState.FAILURE
        )

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=name,
            condition_fn=_check,
        )
    )


def _verified_drop_bundle(
    name: str,
    *,
    log: bool,
    attempts: int = 3,
) -> BehaviorTree:
    """Drop a held bundle and verify that the game actually released it.

    BT.DropBundle() only sends the drop action. For torch mechanics we also
    confirm that Agent.IsHoldingItem() becomes false before continuing.
    """
    children: list[BehaviorTree] = [
        _bundle_released_check(f'{name} - Already Released')
    ]

    for attempt in range(1, max(1, int(attempts)) + 1):
        children.append(
            BT.Sequence(
                name=f'{name} - Attempt {attempt}',
                children=[
                    BT.DropBundle(log=log),
                    BT.Wait(250 + ((attempt - 1) * 150)),
                    _bundle_released_check(
                        f'{name} - Verify Attempt {attempt}'
                    ),
                ],
            )
        )

    return BT.Selector(
        name=name,
        children=children,
    )


def DropTorchForCombat(log: bool = False) -> BehaviorTree:
    """Drop the torch for martial combat and verify it was actually released."""

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        global _last_torch_drop_position

        if not _resolve_torch_combat_policy():
            return BT.Succeeder('Keep Torch For Caster Combat')
        if not _is_holding_bundle():
            return BT.Succeeder('No Torch Bundle To Drop')

        try:
            x, y = Player.GetXY()
            _last_torch_drop_position = (float(x), float(y))
            if log:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f'Torch combat drop recorded at ({float(x):.0f}, {float(y):.0f}).',
                    PySystem.Console.MessageType.Info,
                )
        except Exception:
            _last_torch_drop_position = None

        release_tree = _verified_drop_bundle(
            'Drop Torch For Combat - Confirm Release',
            log=log,
        )
        if not TORCH_DIAGNOSTICS or _last_torch_drop_position is None:
            return release_tree

        origin = _last_torch_drop_position
        before_items, before_gadgets = _torch_drop_debug_snapshot('BEFORE', origin)

        def _released_snapshot(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
            _torch_drop_debug_snapshot('RELEASED', origin, before_items, before_gadgets)
            return BehaviorTree.NodeState.SUCCESS

        def _settled_snapshot(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
            _torch_drop_debug_snapshot('SETTLED', origin, before_items, before_gadgets)
            return BehaviorTree.NodeState.SUCCESS

        return BT.Sequence(
            name='Drop Torch For Combat - With Debug Snapshots',
            children=[
                release_tree,
                BehaviorTree(BehaviorTree.ActionNode(name='Torch Drop Snapshot - Released', action_fn=_released_snapshot, aftercast_ms=0)),
                BT.Wait(350),
                BehaviorTree(BehaviorTree.ActionNode(name='Torch Drop Snapshot - Settled', action_fn=_settled_snapshot, aftercast_ms=0)),
            ],
        )

    return BT.Subtree(name='Drop Torch For Combat If Required', subtree_fn=_build)


def DiscardTorch(log: bool = True) -> BehaviorTree:
    """Discard the torch and do not continue until release is confirmed."""

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        global _last_torch_drop_position
        _last_torch_drop_position = None
        if not _is_holding_bundle():
            return BT.Succeeder('No Torch Bundle To Discard')

        return _verified_drop_bundle(
            'Discard Torch After Mechanic - Confirm Release',
            log=log,
        )

    return BT.Subtree(name='Discard Torch After Mechanic', subtree_fn=_build)


def _enemy_in_torch_combat_range(radius: float = TORCH_COMBAT_TRIGGER_RADIUS) -> bool:
    """Return True when a living enemy is close enough to start torch combat handling."""
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


def _shards_trap_destination_xy(destination) -> tuple[float, float] | None:
    """Resolve a single destination from a point or path accepted by BT.Move."""
    try:
        if hasattr(destination, "x") and hasattr(destination, "y"):
            return float(destination.x), float(destination.y)
        if isinstance(destination, Sequence) and not isinstance(destination, (str, bytes)):
            values = list(destination)
            if not values:
                return None
            if len(values) >= 2 and isinstance(values[0], (int, float)) and isinstance(values[1], (int, float)):
                return float(values[0]), float(values[1])
            return _shards_trap_destination_xy(values[-1])
    except Exception:
        return None
    return None



def _shards_known_traps(*, active_only: bool = False) -> list[dict]:
    """Return confirmed Shards traps on the current map."""
    try:
        if not Map.IsMapReady() or Map.IsMapLoading():
            return []
        map_id = int(Map.GetMapID() or 0)
        allowed_ids = SHARDS_TRAP_GADGET_IDS_BY_MAP.get(map_id)
        if not allowed_ids:
            return []

        result: list[dict] = []
        for raw_agent_id in AgentArray.GetGadgetArray() or []:
            agent_id = int(raw_agent_id or 0)
            if agent_id <= 0:
                continue
            try:
                gadget = Agent.GetGadgetAgentByID(agent_id)
                gadget_id = int(getattr(gadget, "gadget_id", 0) or 0) if gadget is not None else 0
                if gadget_id not in allowed_ids:
                    continue
                agent = Agent.GetAgentByID(agent_id)
                if agent is None:
                    continue
                properties = int(getattr(agent, "name_properties", 0) or 0)
                active = bool(properties & SHARDS_TRAP_ACTIVE_BIT)
                if active_only and not active:
                    continue
                tx, ty = Agent.GetXY(agent_id)
                result.append({
                    "map_id": map_id,
                    "agent_id": agent_id,
                    "gadget_id": gadget_id,
                    "active": active,
                    "properties": properties,
                    "x": float(tx),
                    "y": float(ty),
                })
            except Exception:
                continue
        return result
    except Exception:
        return []


def _shards_trap_requires_forced_pause(trap: dict | None) -> bool:
    """Return True when this Shards trap must be waited out instead of bypassed."""
    if not trap:
        return False
    try:
        map_id = int(trap.get("map_id", 0) or 0)
        gadget_id = int(trap.get("gadget_id", 0) or 0)
    except Exception:
        return False
    return (
        map_id in SHARDS_TRAP_FORCE_PAUSE_MAPS
        or gadget_id in SHARDS_TRAP_FORCE_PAUSE_IDS
    )


def _shards_route_blocker(
    destination_xy: tuple[float, float] | None,
    *,
    active_only: bool = True,
) -> dict | None:
    """Return the nearest confirmed Shards trap intersecting the forward route."""
    if destination_xy is None:
        return None
    try:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0 or Agent.IsDead(player_id):
            return None
        px, py = Agent.GetXY(player_id)
        px, py = float(px), float(py)
        dx = float(destination_xy[0]) - px
        dy = float(destination_xy[1]) - py
        segment_len_sq = dx * dx + dy * dy
        if segment_len_sq <= 1.0:
            return None
        segment_len = segment_len_sq ** 0.5

        best: dict | None = None
        for trap in _shards_known_traps(active_only=active_only):
            tx, ty = float(trap["x"]), float(trap["y"])
            rel_x = tx - px
            rel_y = ty - py
            projection = (rel_x * dx + rel_y * dy) / segment_len_sq
            if projection < 0.0 or projection > 1.0:
                continue
            along = projection * segment_len
            if along > SHARDS_TRAP_LOOKAHEAD:
                continue
            closest_x = px + projection * dx
            closest_y = py + projection * dy
            route_offset = ((tx - closest_x) ** 2 + (ty - closest_y) ** 2) ** 0.5
            if route_offset > SHARDS_TRAP_ROUTE_HALF_WIDTH:
                continue
            player_distance = ((tx - px) ** 2 + (ty - py) ** 2) ** 0.5
            candidate = dict(trap)
            candidate.update({
                "distance": player_distance,
                "along": along,
                "route_offset": route_offset,
            })
            if best is None or float(candidate["along"]) < float(best["along"]):
                best = candidate
        return best
    except Exception:
        return None


def _shards_trap_still_blocks(
    trap_xy: tuple[float, float],
    destination_xy: tuple[float, float] | None,
) -> bool:
    """Keep a bypass committed until the trap is no longer inside the forward corridor."""
    if destination_xy is None:
        return False
    try:
        px, py = Player.GetXY()
        px, py = float(px), float(py)
        dx = float(destination_xy[0]) - px
        dy = float(destination_xy[1]) - py
        length_sq = dx * dx + dy * dy
        if length_sq <= 1.0:
            return False
        rel_x = float(trap_xy[0]) - px
        rel_y = float(trap_xy[1]) - py
        projection = (rel_x * dx + rel_y * dy) / length_sq
        if projection <= 0.0:
            return False
        projection = min(1.0, projection)
        cx = px + projection * dx
        cy = py + projection * dy
        offset = ((float(trap_xy[0]) - cx) ** 2 + (float(trap_xy[1]) - cy) ** 2) ** 0.5
        return offset < SHARDS_TRAP_HAZARD_RADIUS
    except Exception:
        return False


def _shards_point_to_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float, tuple[float, float]]:
    """Return (distance, projection 0..1, closest point) from *point* to segment."""
    px, py = float(point[0]), float(point[1])
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-6:
        return math.hypot(px - ax, py - ay), 0.0, (ax, ay)
    projection = ((px - ax) * dx + (py - ay) * dy) / length_sq
    projection = max(0.0, min(1.0, projection))
    cx = ax + projection * dx
    cy = ay + projection * dy
    return math.hypot(px - cx, py - cy), projection, (cx, cy)


def _shards_segment_clears_trap(
    start: tuple[float, float],
    end: tuple[float, float],
    trap_xy: tuple[float, float],
    *,
    radius: float = SHARDS_TRAP_HAZARD_RADIUS,
) -> bool:
    """True when the whole segment stays outside the trap hazard circle."""
    distance, _, _ = _shards_point_to_segment_distance(trap_xy, start, end)
    return distance >= float(radius)


def _shards_trap_centered_bypass_target(
    current_pos: tuple[float, float],
    route_target: tuple[float, float],
    trap: dict,
    *,
    preferred_side: int = 0,
) -> tuple[tuple[float, float], int, float] | None:
    """Choose a navmesh-safe waypoint on a 500u ring around the trap.

    The trap centre, not the player, is the reference.  Candidates are sampled
    on the left/right half of a 500u circle around the trap.  A candidate is
    accepted only if the segment from the player to that point does not cross
    the hazard circle.  Candidates whose onward segment to the real route target
    is already clear are strongly preferred.
    """
    cx, cy = float(current_pos[0]), float(current_pos[1])
    dx = float(route_target[0]) - cx
    dy = float(route_target[1]) - cy
    length = math.hypot(dx, dy)
    if length <= 1.0:
        return None
    ux, uy = dx / length, dy / length
    tx, ty = float(trap["x"]), float(trap["y"])
    ring = float(SHARDS_TRAP_STEERING_DISTANCE)
    hazard = float(SHARDS_TRAP_HAZARD_RADIUS)

    # If already inside the hazard circle, first move directly away from its
    # centre to the 500u safety ring.
    from_trap_x = cx - tx
    from_trap_y = cy - ty
    from_trap_len = math.hypot(from_trap_x, from_trap_y)
    if from_trap_len < hazard:
        if from_trap_len <= 1.0:
            from_trap_x, from_trap_y = -uy, ux
            from_trap_len = 1.0
        candidate = (
            tx + (from_trap_x / from_trap_len) * ring,
            ty + (from_trap_y / from_trap_len) * ring,
        )
        if _shards_trap_segment_walkable(current_pos, candidate):
            side_cross = ux * (candidate[1] - ty) - uy * (candidate[0] - tx)
            side = 1 if side_cross >= 0.0 else -1
            return candidate, side, ring
        return None

    # Sample points on a ring centred on the trap.  90 degrees is the natural
    # lateral bypass.  Larger angles provide a safe tangent-like entry when the
    # player is already fairly close to the trap.
    angle_degrees = (90.0, 110.0, 130.0, 150.0, 70.0, 50.0)
    side_order = [preferred_side] if preferred_side in (-1, 1) else [1, -1]
    if preferred_side in (-1, 1):
        side_order.append(-preferred_side)

    best: tuple[tuple[float, float], int, float, float] | None = None
    for side in side_order:
        for angle_deg in angle_degrees:
            angle = math.radians(angle_deg * side)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            rx = ux * cos_a - uy * sin_a
            ry = ux * sin_a + uy * cos_a
            candidate = (tx + rx * ring, ty + ry * ring)

            if not _shards_trap_segment_walkable(current_pos, candidate):
                continue
            approach_clearance, _, _ = _shards_point_to_segment_distance(
                (tx, ty), current_pos, candidate
            )
            if approach_clearance < hazard:
                continue

            onward_clear = _shards_segment_clears_trap(
                candidate, route_target, (tx, ty), radius=hazard
            )
            # Progress along the original route.  Prefer a one-step bypass that
            # also gives a clear segment back to the original waypoint.
            progress = (candidate[0] - cx) * ux + (candidate[1] - cy) * uy
            travel = math.hypot(candidate[0] - cx, candidate[1] - cy)
            score = (100000.0 if onward_clear else 0.0) + progress * 10.0 - travel
            if preferred_side in (-1, 1) and side == preferred_side:
                score += 250.0
            if best is None or score > best[3]:
                best = (candidate, side, approach_clearance, score)

    if best is None:
        return None
    return best[0], best[1], best[2]


def _shards_trap_segment_walkable(start: tuple[float, float], end: tuple[float, float]) -> bool:
    """Use the existing Core navmesh to reject detours through static geometry."""
    try:
        navmesh = AutoPathing().get_navmesh()
        if navmesh is None:
            return True
        return bool(
            navmesh.contains(float(end[0]), float(end[1]), margin=40.0)
            and navmesh.has_line_of_sight(
                (float(start[0]), float(start[1])),
                (float(end[0]), float(end[1])),
                margin=40.0,
                step_dist=50.0,
            )
        )
    except Exception:
        return False


class _ShardsTrapAvoidNode(BehaviorTree.Node):
    """Locally bypass confirmed active Shards traps without pausing the BottingTree."""

    def __init__(self, child: BehaviorTree | BehaviorTree.Node, destination, *, name: str) -> None:
        super().__init__(name=name, node_type="ShardsTrapAvoid", node_category="decorator")
        self.child = self._coerce_node(child)
        self.destination_xy = _shards_trap_destination_xy(destination)
        self._committed: dict | None = None
        self._side = 0
        self._last_target: tuple[float, float] | None = None
        self._last_eval_ms = 0.0
        self._last_command_ms = 0.0
        self._waiting_without_detour = False
        self._inactive_since_ms = 0.0

    def get_children(self) -> list[BehaviorTree.Node]:
        return [self.child]

    def reset(self) -> None:
        super().reset()
        self.child.reset()
        self._committed = None
        self._side = 0
        self._last_target = None
        self._last_eval_ms = 0.0
        self._last_command_ms = 0.0
        self._waiting_without_detour = False
        self._inactive_since_ms = 0.0

    @staticmethod
    def _stop_local_player() -> None:
        try:
            px, py = Player.GetXY()
            Player.Move(float(px), float(py))
        except Exception:
            pass

    def _route_target(self) -> tuple[float, float] | None:
        """Prefer the wrapped Move's live waypoint when it is available."""
        try:
            blackboard = self.blackboard if isinstance(self.blackboard, dict) else {}
            waypoint = blackboard.get("move_current_waypoint")
            if isinstance(waypoint, Sequence) and len(waypoint) >= 2:
                return float(waypoint[0]), float(waypoint[1])
        except Exception:
            pass
        return self.destination_xy

    def _clear_committed(self) -> None:
        self._committed = None
        self._side = 0
        self._last_target = None
        self._last_eval_ms = 0.0
        self._last_command_ms = 0.0
        self._waiting_without_detour = False
        self._inactive_since_ms = 0.0

    def _tick_impl(self) -> BehaviorTree.NodeState:
        # Combat movement owns itself. Do not inject trap steering while the
        # party is fighting, otherwise this decorator can fight HeroAI/Vanquish.
        try:
            if Routines.Checks.Agents.InDanger():
                if self._committed is not None:
                    self._clear_committed()
                    self.child.reset()
                self.child.blackboard = self.blackboard
                return self.child.tick()
        except Exception:
            pass

        route_target = self._route_target()
        if route_target is None:
            self.child.blackboard = self.blackboard
            return self.child.tick()

        # Start a bypass only when a CONFIRMED Shards trap is currently active.
        if self._committed is None:
            blocker = _shards_route_blocker(route_target, active_only=True)
            if blocker is None:
                self.child.blackboard = self.blackboard
                return self.child.tick()

            self._committed = blocker
            self._side = 0
            self._last_target = None
            self._last_eval_ms = 0.0
            self._last_command_ms = 0.0
            self._waiting_without_detour = False
            self._inactive_since_ms = 0.0

            # Stop the wrapped movement once. From here until the trap is passed,
            # only this decorator issues local movement commands.
            self.child.reset()
            if _shards_trap_requires_forced_pause(blocker):
                action_text = "Forced-pause trap; waiting for OFF."
            else:
                action_text = "Starting trap-centred bypass."
            PySystem.Console.Log(
                MODULE_NAME,
                f"[TrapAvoid] Active trap GID={blocker['gadget_id']} AID={blocker['agent_id']} "
                f"intersects the planned path ({blocker['distance']:.0f}u away, offset={blocker['route_offset']:.0f}u). {action_text}",
                PySystem.Console.MessageType.Warning,
            )

        committed = self._committed
        if committed is None:
            self.child.blackboard = self.blackboard
            return self.child.tick()

        # If the hazardous cycle switches OFF, release immediately.  The whole
        # point of the bypass is to avoid losing time waiting when a safe route
        # is available, not to force completion of a detour that is no longer
        # needed.
        active_now = False
        try:
            agent = Agent.GetAgentByID(int(committed["agent_id"]))
            properties = int(getattr(agent, "name_properties", 0) or 0) if agent is not None else 0
            active_now = bool(properties & SHARDS_TRAP_ACTIVE_BIT)
        except Exception:
            active_now = False

        if not active_now:
            gid = int(committed["gadget_id"])
            PySystem.Console.Log(
                MODULE_NAME,
                f"[TrapAvoid] Trap GID={gid} is OFF; resuming the original route immediately.",
                PySystem.Console.MessageType.Info,
            )
            self._clear_committed()
            self.child.blackboard = self.blackboard
            return self.child.tick()

        if not _shards_trap_still_blocks(
            (float(committed["x"]), float(committed["y"])),
            route_target,
        ):
            gid = int(committed["gadget_id"])
            PySystem.Console.Log(
                MODULE_NAME,
                f"[TrapAvoid] 500u bypass complete for GID={gid}; resuming the original route.",
                PySystem.Console.MessageType.Success,
            )
            self._clear_committed()
            self.child.blackboard = self.blackboard
            return self.child.tick()

        now_ms = time.monotonic() * 1000.0
        if now_ms - self._last_eval_ms < SHARDS_TRAP_AVOIDANCE_UPDATE_MS:
            return BehaviorTree.NodeState.RUNNING
        self._last_eval_ms = now_ms

        try:
            current = Player.GetXY()
            current_pos = (float(current[0]), float(current[1]))
        except Exception:
            return BehaviorTree.NodeState.RUNNING

        gid = int(committed.get("gadget_id", 0) or 0)
        if _shards_trap_requires_forced_pause(committed):
            if not self._waiting_without_detour:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[TrapAvoid] GID={gid} is configured for forced pause on this map; waiting for OFF.",
                    PySystem.Console.MessageType.Warning,
                )
            self._waiting_without_detour = True
            self._inactive_since_ms = 0.0
            self._stop_local_player()
            return BehaviorTree.NodeState.RUNNING

        bypass = _shards_trap_centered_bypass_target(
            current_pos,
            route_target,
            committed,
            preferred_side=self._side,
        )

        if bypass is not None:
            target, side, clearance = bypass
            changed = self._last_target is None or (
                (target[0] - self._last_target[0]) ** 2
                + (target[1] - self._last_target[1]) ** 2
            ) >= 40.0 ** 2
            command_due = now_ms - self._last_command_ms >= SHARDS_TRAP_AVOIDANCE_UPDATE_MS
            if changed or command_due:
                Player.Move(target[0], target[1])
                self._last_target = target
                self._last_command_ms = now_ms

            if self._waiting_without_detour:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[TrapAvoid] Walkable trap-centred detour recovered for GID={committed['gadget_id']}.",
                    PySystem.Console.MessageType.Info,
                )
            if self._side != int(side) or self._waiting_without_detour:
                side_name = "left" if int(side) > 0 else "right"
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[TrapAvoid] Path intersects GID={committed['gadget_id']} "
                    f"(offset={float(committed.get('route_offset', 0.0)):.0f}u); "
                    f"bypassing {side_name} at 500u around trap centre via "
                    f"({target[0]:.0f}, {target[1]:.0f}), approach clearance={clearance:.0f}u.",
                    PySystem.Console.MessageType.Info,
                )
            self._side = int(side)
            self._waiting_without_detour = False
            self._inactive_since_ms = 0.0
            return BehaviorTree.NodeState.RUNNING

        # Narrow corridor / no navmesh-safe lateral point. Only here do we wait.
        if not self._waiting_without_detour:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[TrapAvoid] No safe 500u bypass around GID={committed['gadget_id']}; waiting for OFF.",
                PySystem.Console.MessageType.Warning,
            )
        self._waiting_without_detour = True
        self._inactive_since_ms = 0.0
        self._stop_local_player()
        return BehaviorTree.NodeState.RUNNING


def ShardsTrapGuard(destination, child: BehaviorTree | BehaviorTree.Node, *, name: str = "Shards Trap Guard") -> BehaviorTree:
    return BehaviorTree(_ShardsTrapAvoidNode(child, destination, name=name))


def ShardsTrapMove(pos, **kwargs) -> BehaviorTree:
    """Shards-local BT.Move wrapper with dynamic trap bypass."""
    kwargs.setdefault("log", SHARDS_MOVEMENT_LOGS)
    return ShardsTrapGuard(
        pos,
        BT.Move(pos, **kwargs),
        name="Shards Trap Avoid - Move",
    )


class _ShardsCombatTrapAvoidNode(BehaviorTree.Node):
    """Prefer a 500u local bypass around active traps during Shards combat.

    If no navmesh-safe lateral steering point exists, hold position only while
    the trap is active.  As soon as it switches OFF, hand control back to the
    wrapped combat node immediately.
    """

    def __init__(self, child: BehaviorTree | BehaviorTree.Node, *, name: str) -> None:
        super().__init__(name=name, node_type="ShardsCombatTrapAvoid", node_category="decorator")
        self.child = self._coerce_node(child)
        self._committed: dict | None = None
        self._side = 0
        self._last_target: tuple[float, float] | None = None
        self._last_command_ms = 0.0
        self._waiting_without_detour = False

    def get_children(self) -> list[BehaviorTree.Node]:
        return [self.child]

    def reset(self) -> None:
        super().reset()
        self.child.reset()
        self._clear_committed()

    @staticmethod
    def _stop_local_player() -> None:
        try:
            px, py = Player.GetXY()
            Player.Move(float(px), float(py))
        except Exception:
            pass

    @staticmethod
    def _current_target_xy() -> tuple[float, float] | None:
        try:
            target_id = int(Player.GetTargetID() or 0)
        except Exception:
            target_id = 0
        if target_id <= 0:
            return None
        try:
            if not Agent.IsAlive(target_id):
                return None
        except Exception:
            pass
        try:
            x, y = Agent.GetXY(target_id)
            return float(x), float(y)
        except Exception:
            return None

    @staticmethod
    def _trap_is_active(trap: dict | None) -> bool:
        if trap is None:
            return False
        try:
            agent = Agent.GetAgentByID(int(trap.get("agent_id", 0) or 0))
            if agent is None:
                return False
            properties = int(getattr(agent, "name_properties", 0) or 0)
            return bool(properties & SHARDS_TRAP_ACTIVE_BIT)
        except Exception:
            return False

    def _active_blocker(self, target_xy: tuple[float, float] | None) -> dict | None:
        if target_xy is None:
            return None
        return _shards_route_blocker(target_xy, active_only=True)

    def _clear_committed(self) -> None:
        self._committed = None
        self._side = 0
        self._last_target = None
        self._last_command_ms = 0.0
        self._waiting_without_detour = False

    def _resume_child(self) -> BehaviorTree.NodeState:
        self.child.blackboard = self.blackboard
        return BehaviorTree.Node._normalize_state(self.child.tick())

    def _tick_impl(self) -> BehaviorTree.NodeState:
        target_xy = self._current_target_xy()

        # Let the combat node select/refresh a target when none exists yet.
        if target_xy is None:
            self._clear_committed()
            result = self._resume_child()
            target_xy = self._current_target_xy()
            if target_xy is None:
                return result

        if self._committed is None:
            blocker = self._active_blocker(target_xy)
            if blocker is None:
                # Tick combat normally, then re-check because the child may have
                # selected a new target and issued an approach command this frame.
                result = self._resume_child()
                target_xy = self._current_target_xy()
                blocker = self._active_blocker(target_xy)
                if blocker is None:
                    return result

            self._committed = blocker
            self._side = 0
            self._last_target = None
            self._last_command_ms = 0.0
            self._waiting_without_detour = False
            if _shards_trap_requires_forced_pause(blocker):
                action_text = "forced pause until OFF"
            else:
                action_text = "trying a trap-centred 500u bypass first"
            PySystem.Console.Log(
                MODULE_NAME,
                f"[TrapCombat] Active trap GID={blocker['gadget_id']} AID={blocker['agent_id']} "
                f"intersects the combat path; {action_text}.",
                PySystem.Console.MessageType.Warning,
            )

        committed = self._committed
        if committed is None:
            return self._resume_child()

        # OFF means immediate release.  We do not keep waiting for a completed
        # bypass because the hazardous cycle no longer exists.
        if not self._trap_is_active(committed):
            gid = int(committed.get("gadget_id", 0) or 0)
            if self._waiting_without_detour:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[TrapCombat] Trap GID={gid} is OFF; resuming combat immediately.",
                    PySystem.Console.MessageType.Info,
                )
            self._clear_committed()
            return self._resume_child()

        # If the active trap is no longer in front of the current target route,
        # the local bypass has done its job.
        if not _shards_trap_still_blocks(
            (float(committed["x"]), float(committed["y"])),
            target_xy,
        ):
            gid = int(committed.get("gadget_id", 0) or 0)
            PySystem.Console.Log(
                MODULE_NAME,
                f"[TrapCombat] 500u bypass complete for GID={gid}; resuming combat.",
                PySystem.Console.MessageType.Info,
            )
            self._clear_committed()
            return self._resume_child()

        try:
            px, py = Player.GetXY()
            current_pos = (float(px), float(py))
        except Exception:
            self._stop_local_player()
            return BehaviorTree.NodeState.RUNNING

        gid = int(committed.get("gadget_id", 0) or 0)
        if _shards_trap_requires_forced_pause(committed):
            if not self._waiting_without_detour:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[TrapCombat] GID={gid} is configured for forced pause on this map; waiting for OFF.",
                    PySystem.Console.MessageType.Warning,
                )
            self._waiting_without_detour = True
            self._stop_local_player()
            return BehaviorTree.NodeState.RUNNING

        bypass = _shards_trap_centered_bypass_target(
            current_pos,
            target_xy,
            committed,
            preferred_side=self._side,
        )

        if bypass is not None:
            now_ms = time.monotonic() * 1000.0
            target, side, clearance = bypass
            changed = self._last_target is None or (
                (target[0] - self._last_target[0]) ** 2
                + (target[1] - self._last_target[1]) ** 2
            ) >= 40.0 ** 2
            command_due = now_ms - self._last_command_ms >= SHARDS_TRAP_AVOIDANCE_UPDATE_MS
            if changed or command_due:
                Player.Move(target[0], target[1])
                self._last_target = target
                self._last_command_ms = now_ms

            if side != self._side or self._waiting_without_detour:
                side_name = "left" if side > 0 else "right"
                PySystem.Console.Log(
                    MODULE_NAME,
                    f"[TrapCombat] Combat path intersects GID={committed['gadget_id']} "
                    f"(offset={float(committed.get('route_offset', 0.0)):.0f}u); "
                    f"bypassing {side_name} at 500u around trap centre via "
                    f"({target[0]:.0f}, {target[1]:.0f}), approach clearance={clearance:.0f}u.",
                    PySystem.Console.MessageType.Info,
                )
            self._side = int(side)
            self._waiting_without_detour = False
            return BehaviorTree.NodeState.RUNNING

        # No navmesh-safe bypass exists.  Pause only as the fallback, and only
        # for as long as the trap remains ON.
        if not self._waiting_without_detour:
            PySystem.Console.Log(
                MODULE_NAME,
                f"[TrapCombat] No safe 500u bypass around GID={committed['gadget_id']}; waiting for OFF.",
                PySystem.Console.MessageType.Warning,
            )
        self._waiting_without_detour = True
        self._stop_local_player()
        return BehaviorTree.NodeState.RUNNING


def ShardsCombatTrapAvoid(child: BehaviorTree | BehaviorTree.Node, *, name: str = "Shards Combat Trap Avoid") -> BehaviorTree:
    return BehaviorTree(_ShardsCombatTrapAvoidNode(child, name=name))

def _torch_aware_combat_node(
    name: str,
    combat_factory: Callable[[], BehaviorTree],
    *,
    trigger_radius: float = TORCH_COMBAT_TRIGGER_RADIUS,
) -> BehaviorTree:
    """Tick combat while dropping a martial torch only when enemies enter the dedicated close trigger radius."""
    combat_tree = combat_factory()
    drop_tree: BehaviorTree | None = None

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal combat_tree, drop_tree

        # Keep carrying the torch while travelling. Martial leaders only drop it
        # once a living enemy is genuinely inside the dedicated combat radius.
        # After the verified drop, normal Vanquish / HeroAI combat owns the fight
        # until the combat step completes, then the existing PickupTorch() resumes.
        should_drop_torch = (
            _resolve_torch_combat_policy()
            and _is_holding_bundle()
            and _enemy_in_torch_combat_range(trigger_radius)
        )

        # Finish a started drop subtree even after the bundle disappears from
        # the character's hands. Otherwise the 250ms release confirmation (and
        # the diagnostic after-snapshots) would never get a subsequent tick.
        if drop_tree is not None or should_drop_torch:
            if drop_tree is None:
                drop_tree = DropTorchForCombat(log=TORCH_PROGRESS_LOGS)

            drop_tree.blackboard = node.blackboard
            drop_result = BehaviorTree.Node._normalize_state(drop_tree.tick())
            if drop_result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING
            if drop_result == BehaviorTree.NodeState.FAILURE:
                drop_tree = None
                return BehaviorTree.NodeState.FAILURE
            drop_tree = None

        combat_tree.blackboard = node.blackboard
        result = BehaviorTree.Node._normalize_state(combat_tree.tick())

        if result != BehaviorTree.NodeState.RUNNING:
            # Rebuild the internal combat child.  If the planner/wipe recovery
            # reconstructs or replays this step, it receives a fresh subtree.
            combat_tree = combat_factory()
            drop_tree = None

        return result

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f'{name} - Torch Aware',
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def TorchAwareVanquish(
    points: Sequence[PathPoint],
    name: str,
    *,
    clear_area_radius: float = Range.Spirit.value,
    pause_on_combat: bool | None = None,
    flag_heroes_to_waypoint: bool = False,
    move_tolerance: float = 500.0,
) -> BehaviorTree:
    """Vanquish a path while martial builds automatically drop the torch for combat."""

    def _create() -> BehaviorTree:
        child = BT.VanquishNode(
            list(points),
            name=name,
            clear_area_radius=clear_area_radius,
            pause_on_combat=pause_on_combat,
            flag_heroes_to_waypoint=flag_heroes_to_waypoint,
            move_tolerance=move_tolerance,
            log=False,
        )
        destination = list(points)[-1] if points else None
        return ShardsTrapGuard(destination, child, name=f"Shards Trap Guard - {name}")

    return _torch_aware_combat_node(name, _create)


def TorchAwareMoveAndKill(
    pos: PathPoint,
    name: str,
    *,
    clear_area_radius: float = Range.Spirit.value,
) -> BehaviorTree:
    """Preserve MoveAndKill semantics while applying the automatic torch combat policy."""

    def _create() -> BehaviorTree:
        return ShardsTrapGuard(
            pos,
            BT.MoveAndKill(pos, clear_area_radius=clear_area_radius, log=False),
            name=f"Shards Trap Guard - {name}",
        )

    return _torch_aware_combat_node(name, _create)


def _torch_agent_brief(agent_id: int) -> str:
    """Best-effort details of a positively detected ground item, no character names."""
    try:
        item_id = int(Agent.GetItemAgentItemID(agent_id) or 0)
        owner_id = int(Agent.GetItemAgentOwnerID(agent_id) or 0)
        model_id = int(GLOBAL_CACHE.Item.GetModelID(item_id) or 0) if item_id > 0 else 0
        player_id = int(Player.GetAgentID() or 0)
        px, py = Agent.GetXY(player_id)
        x, y = Agent.GetXY(agent_id)
        distance = ((float(x) - float(px)) ** 2 + (float(y) - float(py)) ** 2) ** 0.5
        return (f'AgentID={agent_id}, ItemID={item_id}, ModelID={model_id}, '
                f'OwnerID={owner_id}, player_dist={distance:.0f}')
    except Exception as exc:
        return f'AgentID={agent_id}, details_error={type(exc).__name__}: {exc}'


def _torch_drop_debug_snapshot(
    stage: str,
    origin: tuple[float, float],
    before_items: set[int] | None = None,
    before_gadgets: set[int] | None = None,
) -> tuple[set[int], set[int]]:
    """Compare ItemAgents and GadgetAgents near a combat drop, diagnostic only.

    The baseline is captured before DropBundle and compared with snapshots after
    release. Unknown agents are logged, NEVER used as pickup candidates.
    """
    nearby_items: list[tuple[float, int, int, int, int]] = []
    nearby_gadgets: list[tuple[float, int, int]] = []
    try:
        item_array = list(AgentArray.GetItemArray() or [])
        gadget_array = list(AgentArray.GetGadgetArray() or [])
        for raw_id in item_array:
            try:
                agent_id = int(raw_id or 0)
                if agent_id <= 0 or not Agent.GetItemAgentByID(agent_id):
                    continue
                x, y = Agent.GetXY(agent_id)
                distance = ((float(x) - origin[0]) ** 2 + (float(y) - origin[1]) ** 2) ** 0.5
                if distance > 950.0:
                    continue
                item_id = int(Agent.GetItemAgentItemID(agent_id) or 0)
                owner_id = int(Agent.GetItemAgentOwnerID(agent_id) or 0)
                model_id = int(GLOBAL_CACHE.Item.GetModelID(item_id) or 0) if item_id > 0 else 0
                nearby_items.append((distance, agent_id, item_id, model_id, owner_id))
            except Exception as exc:
                PySystem.Console.Log(MODULE_NAME, f'[Torch Debug] {stage} item scan error: {type(exc).__name__}: {exc}', PySystem.Console.MessageType.Warning)
        for raw_id in gadget_array:
            try:
                agent_id = int(raw_id or 0)
                if agent_id <= 0:
                    continue
                x, y = Agent.GetXY(agent_id)
                distance = ((float(x) - origin[0]) ** 2 + (float(y) - origin[1]) ** 2) ** 0.5
                if distance > 950.0:
                    continue
                gadget_id = int(Agent.GetGadgetID(agent_id) or 0)
                nearby_gadgets.append((distance, agent_id, gadget_id))
            except Exception as exc:
                PySystem.Console.Log(MODULE_NAME, f'[Torch Debug] {stage} gadget scan error: {type(exc).__name__}: {exc}', PySystem.Console.MessageType.Warning)

        nearby_items.sort()
        nearby_gadgets.sort()
        PySystem.Console.Log(
            MODULE_NAME,
            (f'[Torch Debug] DROP {stage}: held={_is_holding_bundle()}, '
             f'origin=({origin[0]:.0f},{origin[1]:.0f}), '
             f'near_items={len(nearby_items)}/{len(item_array)}, '
             f'near_gadgets={len(nearby_gadgets)}/{len(gadget_array)} (radius=950)'),
            PySystem.Console.MessageType.Info,
        )
        for distance, agent_id, item_id, model_id, owner_id in nearby_items[:12]:
            added = 'NEW' if before_items is not None and agent_id not in before_items else 'existing'
            PySystem.Console.Log(
                MODULE_NAME,
                (f'[Torch Debug] DROP {stage} ItemAgent={agent_id}, ItemID={item_id}, '
                 f'ModelID={model_id}, OwnerID={owner_id}, drop_dist={distance:.0f}, {added}'),
                PySystem.Console.MessageType.Info,
            )
        for distance, agent_id, gadget_id in nearby_gadgets[:12]:
            added = 'NEW' if before_gadgets is not None and agent_id not in before_gadgets else 'existing'
            PySystem.Console.Log(
                MODULE_NAME,
                (f'[Torch Debug] DROP {stage} GadgetAgent={agent_id}, '
                 f'GadgetID={gadget_id}, drop_dist={distance:.0f}, {added}'),
                PySystem.Console.MessageType.Info,
            )
    except Exception as exc:
        PySystem.Console.Log(MODULE_NAME, f'[Torch Debug] DROP {stage} scan failed: {type(exc).__name__}: {exc}', PySystem.Console.MessageType.Warning)
    return ({entry[1] for entry in nearby_items}, {entry[1] for entry in nearby_gadgets})


def _log_torch_ground_diagnostics() -> None:
    """Diagnose a missed torch without changing the actual pickup filters.

    Runs only after a failed _find_ground_torch() and is rate-limited by PickupTorch.
    The model-ID candidates are reported even if an owner/range filter rejects them.
    """
    try:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            PySystem.Console.Log(MODULE_NAME, '[Torch Debug] Invalid local player AgentID.', PySystem.Console.MessageType.Warning)
            return

        px, py = Agent.GetXY(player_id)
        drop_pos = _last_torch_drop_position
        items = list(AgentArray.GetItemArray() or [])
        records: list[dict[str, object]] = []
        torch_model_count = 0
        eligible_count = 0

        for raw_agent_id in items:
            agent_id = int(raw_agent_id or 0)
            item_id = owner_id = model_id = 0
            player_distance: float | None = None
            drop_distance: float | None = None
            valid_agent = False
            reason = 'invalid agent ID'
            try:
                if agent_id > 0:
                    valid_agent = bool(Agent.GetItemAgentByID(agent_id))
                    if valid_agent:
                        owner_id = int(Agent.GetItemAgentOwnerID(agent_id) or 0)
                        item_id = int(Agent.GetItemAgentItemID(agent_id) or 0)
                        if item_id > 0:
                            model_id = int(GLOBAL_CACHE.Item.GetModelID(item_id) or 0)
                        x, y = Agent.GetXY(agent_id)
                        player_distance = ((float(x) - float(px)) ** 2 + (float(y) - float(py)) ** 2) ** 0.5
                        if drop_pos is not None:
                            drop_distance = ((float(x) - drop_pos[0]) ** 2 + (float(y) - drop_pos[1]) ** 2) ** 0.5

                if not valid_agent:
                    reason = 'invalid item-agent'
                elif item_id <= 0:
                    reason = 'invalid ItemID'
                elif model_id not in TORCH_MODEL_IDS:
                    reason = 'different ModelID'
                elif owner_id not in (0, player_id):
                    reason = 'owner filter'
                elif player_distance is None or player_distance > 7500.0:
                    reason = 'outside 7500 range'
                else:
                    reason = 'ELIGIBLE'
                    eligible_count += 1
            except Exception as exc:
                reason = f'candidate error: {type(exc).__name__}: {exc}'

            if model_id in TORCH_MODEL_IDS:
                torch_model_count += 1
            records.append({
                'agent': agent_id, 'item': item_id, 'model': model_id, 'owner': owner_id,
                'distance': player_distance, 'drop_distance': drop_distance, 'reason': reason,
            })

        player_drop_distance = None if drop_pos is None else (
            ((float(px) - drop_pos[0]) ** 2 + (float(py) - drop_pos[1]) ** 2) ** 0.5
        )
        PySystem.Console.Log(
            MODULE_NAME,
            (f'[Torch Debug] Scan: player={player_id}, items={len(items)}, '
             f'torch_ModelIDs={torch_model_count}, eligible={eligible_count}, '
             f'distance_to_recorded_drop={player_drop_distance:.0f}'
             if player_drop_distance is not None else
             f'[Torch Debug] Scan: player={player_id}, items={len(items)}, '
             f'torch_ModelIDs={torch_model_count}, eligible={eligible_count}, recorded_drop=None'),
            PySystem.Console.MessageType.Warning,
        )

        # Show every torch candidate first, then the closest other ground items.
        # This lets us spot a wrong ModelID, owner, range, or missing agent data.
        records.sort(key=lambda entry: (
            0 if entry['model'] in TORCH_MODEL_IDS else 1,
            min(
                entry['distance'] if entry['distance'] is not None else float('inf'),
                entry['drop_distance'] if entry['drop_distance'] is not None else float('inf'),
            ),
        ))
        for entry in records[:12]:
            distance = entry['distance']
            drop_distance = entry['drop_distance']
            distance_label = '?' if distance is None else f'{distance:.0f}'
            drop_distance_label = '?' if drop_distance is None else f'{drop_distance:.0f}'
            PySystem.Console.Log(
                MODULE_NAME,
                (f"[Torch Debug] AgentID={entry['agent']}, ItemID={entry['item']}, "
                 f"ModelID={entry['model']}, OwnerID={entry['owner']}, "
                 f"player_dist={distance_label}, drop_dist={drop_distance_label}, "
                 f"filter={entry['reason']}"),
                PySystem.Console.MessageType.Info,
            )
        if len(records) > 12:
            PySystem.Console.Log(
                MODULE_NAME,
                f'[Torch Debug] {len(records) - 12} additional ground agents omitted from this snapshot.',
                PySystem.Console.MessageType.Info,
            )

        # The current pickup searches ItemArray only. Check GadgetArray as a
        # separate observation; NEVER treat an unknown gadget as a torch.
        gadget_candidates: list[tuple[float, int, int]] = []
        try:
            gadgets = list(AgentArray.GetGadgetArray() or [])
            anchor = drop_pos if drop_pos is not None else (float(px), float(py))
            for raw_id in gadgets:
                try:
                    gadget_agent_id = int(raw_id or 0)
                    if gadget_agent_id <= 0:
                        continue
                    gx, gy = Agent.GetXY(gadget_agent_id)
                    distance = ((float(gx) - anchor[0]) ** 2 + (float(gy) - anchor[1]) ** 2) ** 0.5
                    if distance <= 950.0:
                        gadget_candidates.append((distance, gadget_agent_id, int(Agent.GetGadgetID(gadget_agent_id) or 0)))
                except Exception as exc:
                    PySystem.Console.Log(MODULE_NAME, f'[Torch Debug] Gadget candidate error: {type(exc).__name__}: {exc}', PySystem.Console.MessageType.Warning)
            gadget_candidates.sort()
            PySystem.Console.Log(
                MODULE_NAME,
                f'[Torch Debug] Gadget scan: total={len(gadgets)}, near_anchor={len(gadget_candidates)}, anchor={"drop" if drop_pos is not None else "player"} (radius=950).',
                PySystem.Console.MessageType.Info,
            )
            for distance, agent_id, gadget_id in gadget_candidates[:12]:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f'[Torch Debug] GadgetAgent={agent_id}, GadgetID={gadget_id}, anchor_dist={distance:.0f}.',
                    PySystem.Console.MessageType.Info,
                )
        except Exception as exc:
            PySystem.Console.Log(MODULE_NAME, f'[Torch Debug] Gadget scan error: {type(exc).__name__}: {exc}', PySystem.Console.MessageType.Warning)
    except Exception as exc:
        PySystem.Console.Log(
            MODULE_NAME,
            f'[Torch Debug] Ground scan exception: {type(exc).__name__}: {exc}',
            PySystem.Console.MessageType.Error,
        )


def _find_ground_torch() -> int | None:
    """Return a nearby pickup-compatible torch agent, 0 if absent, None if the scan failed."""
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

            model_id = int(GLOBAL_CACHE.Item.GetModelID(item_id) or 0)
            if model_id not in TORCH_MODEL_IDS:
                continue

            x, y = Agent.GetXY(agent_id)
            dx = float(x) - float(px)
            dy = float(y) - float(py)
            if dx * dx + dy * dy <= search_radius_sq:
                return agent_id

        return 0
    except Exception:
        return None


def PickupTorch(*, allow_shrine_skip: bool = True) -> BehaviorTree:
    """Recover the active torch, retracing to the last combat-drop point when needed."""
    PICKUP_TIMEOUT_MS = 45_000
    COMBAT_TORCH_RECOVERY_TIMEOUT_MS = 30_000
    RETRY_DELAY_MS = 1_000
    PICKUP_CONFIRM_GRACE_MS = 1_500
    PICKUP_SEARCH_RADIUS = 7500.0
    DROP_RETRACE_TOLERANCE = 500.0

    def _create_pickup_tree() -> BehaviorTree:
        return BT.PickupGroundItemByModelID(
            model_ids=TORCH_MODEL_IDS,
            max_distance=PICKUP_SEARCH_RADIUS,
            timeout_ms=PICKUP_TIMEOUT_MS,
            allow_unassigned=True,
            interaction_interval_ms=1_000,
            aftercast_ms=100,
            log=False,
        )

    pickup_tree = _create_pickup_tree()
    return_to_drop_tree: BehaviorTree | None = None
    started_at = 0.0
    retry_at = 0.0
    last_ground_torch_seen_at = 0.0
    last_diagnostic_at = 0.0
    last_detected_torch_agent = 0
    last_detected_brief = 'none'
    pickup_request_logged = False
    search_logged = False
    retrace_logged = False

    def _reset_state() -> None:
        nonlocal pickup_tree, return_to_drop_tree, started_at, retry_at
        nonlocal last_ground_torch_seen_at, last_diagnostic_at, search_logged, retrace_logged
        nonlocal last_detected_torch_agent, last_detected_brief, pickup_request_logged
        pickup_tree = _create_pickup_tree()
        return_to_drop_tree = None
        started_at = 0.0
        retry_at = 0.0
        last_ground_torch_seen_at = 0.0
        last_diagnostic_at = 0.0
        last_detected_torch_agent = 0
        last_detected_brief = 'none'
        pickup_request_logged = False
        search_logged = False
        retrace_logged = False

    def _pickup_torch_step(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal pickup_tree, return_to_drop_tree, started_at, retry_at
        nonlocal last_ground_torch_seen_at, last_diagnostic_at, search_logged, retrace_logged
        nonlocal last_detected_torch_agent, last_detected_brief, pickup_request_logged
        global _shrine_recovery_torch_skip_active, _last_torch_drop_position

        now = time.monotonic()

        if _is_core_shrine_resume(node):
            _shrine_recovery_torch_skip_active = True

        if _is_holding_bundle():
            if TORCH_DIAGNOSTICS:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (f'[Torch Debug] PICKUP HOLD CONFIRMED: held=True, '
                     f'last_detected={last_detected_brief}, '
                     f'elapsed_ms={int((now - started_at) * 1000.0) if started_at > 0.0 else 0}; '
                     'source not inferred when there was no detected candidate.'),
                    PySystem.Console.MessageType.Success,
                )
            _shrine_recovery_torch_skip_active = False
            _last_torch_drop_position = None
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        if started_at <= 0.0:
            started_at = now

        if not search_logged:
            if TORCH_PROGRESS_LOGS:
                PySystem.Console.Log(
                    MODULE_NAME,
                    'Torch is required for the active mechanic. Looking for it on the ground...',
                    PySystem.Console.MessageType.Info,
                )
            search_logged = True

        elapsed_ms = int((now - started_at) * 1000.0)

        if (
            allow_shrine_skip
            and _shrine_recovery_torch_skip_active
            and elapsed_ms >= COMBAT_TORCH_RECOVERY_TIMEOUT_MS
        ):
            PySystem.Console.Log(
                MODULE_NAME,
                'Torch not recovered after 30s ; continuing to the next route point.',
                PySystem.Console.MessageType.Warning,
            )
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        if elapsed_ms >= PICKUP_TIMEOUT_MS:
            PySystem.Console.Log(
                MODULE_NAME,
                'Failed to recover the required torch after 45s.',
                PySystem.Console.MessageType.Error,
            )
            _reset_state()
            return BehaviorTree.NodeState.FAILURE

        ground_torch = _find_ground_torch()

        # Diagnostic snapshots are captured only on misses, at most every 3s.
        if (
            TORCH_DIAGNOSTICS
            and (ground_torch is None or ground_torch == 0)
            and (last_diagnostic_at <= 0.0 or (now - last_diagnostic_at) * 1000.0 >= TORCH_DIAGNOSTIC_INTERVAL_MS)
        ):
            last_diagnostic_at = now
            _log_torch_ground_diagnostics()

        if ground_torch:
            last_ground_torch_seen_at = now
            if TORCH_DIAGNOSTICS and int(ground_torch) != last_detected_torch_agent:
                last_detected_torch_agent = int(ground_torch)
                last_detected_brief = _torch_agent_brief(last_detected_torch_agent)
                PySystem.Console.Log(
                    MODULE_NAME,
                    f'[Torch Debug] FOUND: {last_detected_brief}.',
                    PySystem.Console.MessageType.Success,
                )
        elif (
            ground_torch == 0
            and last_ground_torch_seen_at > 0.0
            and (now - last_ground_torch_seen_at) * 1000.0 < PICKUP_CONFIRM_GRACE_MS
        ):
            # The ground agent can disappear a moment before the carried-bundle
            # state is updated. Give the game time to confirm the pickup before
            # assuming the torch was lost and retracing to the combat-drop point.
            return BehaviorTree.NodeState.RUNNING

        if ground_torch == 0 and _last_torch_drop_position is not None:
            if return_to_drop_tree is None:
                # Avoid retracing immediately after a transient ground-agent miss.
                if elapsed_ms < TORCH_INITIAL_RETRACE_GRACE_MS:
                    return BehaviorTree.NodeState.RUNNING
                drop_x, drop_y = _last_torch_drop_position
                return_to_drop_tree = ShardsTrapMove(
                    Vec2f(float(drop_x), float(drop_y)),
                    tolerance=DROP_RETRACE_TOLERANCE,
                    pause_on_combat=False,
                    log=False,
                )
                if not retrace_logged:
                    PySystem.Console.Log(
                        MODULE_NAME,
                        f'Torch not found nearby; returning to the recorded drop point ({drop_x:.0f}, {drop_y:.0f}).',
                        PySystem.Console.MessageType.Warning,
                    )
                    retrace_logged = True

            return_to_drop_tree.blackboard = node.blackboard
            move_result = BehaviorTree.Node._normalize_state(return_to_drop_tree.tick())
            if move_result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if move_result == BehaviorTree.NodeState.FAILURE:
                PySystem.Console.Log(
                    MODULE_NAME,
                    'Failed to return to the recorded torch drop point; continuing local torch search.',
                    PySystem.Console.MessageType.Warning,
                )
                return_to_drop_tree = None
                _last_torch_drop_position = None
                return BehaviorTree.NodeState.RUNNING

            return_to_drop_tree = None
            pickup_tree = _create_pickup_tree()
            pickup_request_logged = False
            pickup_tree.blackboard = node.blackboard
            retry_at = 0.0
            return BehaviorTree.NodeState.RUNNING

        if ground_torch == 0:
            return BehaviorTree.NodeState.RUNNING

        return_to_drop_tree = None

        if now < retry_at:
            return BehaviorTree.NodeState.RUNNING

        if TORCH_DIAGNOSTICS and not pickup_request_logged:
            pickup_request_logged = True
            target_description = (
                _torch_agent_brief(int(ground_torch)) if ground_torch is not None
                else 'ground scan returned None (exception/unavailable)'
            )
            PySystem.Console.Log(
                MODULE_NAME,
                f'[Torch Debug] PICKUP REQUEST: {target_description}; using existing BT.PickupGroundItemByModelID.',
                PySystem.Console.MessageType.Info,
            )
        pickup_tree.blackboard = node.blackboard
        pickup_result = BehaviorTree.Node._normalize_state(pickup_tree.tick())

        if pickup_result == BehaviorTree.NodeState.RUNNING:
            return BehaviorTree.NodeState.RUNNING

        if pickup_result == BehaviorTree.NodeState.SUCCESS and _is_holding_bundle():
            if TORCH_DIAGNOSTICS:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f'[Torch Debug] PICKUP CONFIRMED: last_detected={last_detected_brief}; held=True.',
                    PySystem.Console.MessageType.Success,
                )
            _shrine_recovery_torch_skip_active = False
            _last_torch_drop_position = None
            _reset_state()
            return BehaviorTree.NodeState.SUCCESS

        if TORCH_DIAGNOSTICS:
            PySystem.Console.Log(
                MODULE_NAME,
                f'[Torch Debug] PICKUP RESULT: state={pickup_result}, held={_is_holding_bundle()}; resetting pickup tree for retry.',
                PySystem.Console.MessageType.Warning,
            )
        pickup_tree = _create_pickup_tree()
        pickup_request_logged = False
        pickup_tree.blackboard = node.blackboard
        retry_at = now + RETRY_DELAY_MS / 1000.0
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Pickup Required Torch',
            action_fn=_pickup_torch_step,
            aftercast_ms=100,
        )
    )

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
        BT.MoveAndInteractWithGadget(pos=Vec2f(float(first_x), float(first_y)), gadget_id=None, search_distance=300.0, interaction_distance=220.0, interaction_count=2, interaction_interval_ms=250, timeout_ms=15000, pause_on_combat=False, multi_account=False, include_self=True, log=False)
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
            log=False,)
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

    move_to_next = ShardsTrapMove(next_pos, tolerance=float(interaction_distance), pause_on_combat=False, ignore_destination_obstacles=True, log=False)

    move_to_previous = ShardsTrapMove(previous_pos, tolerance=float(interaction_distance), pause_on_combat=False, ignore_destination_obstacles=True, log=False)

    relight_previous = BT.MoveAndInteractWithGadget(pos=previous_pos, gadget_id=None, search_distance=300.0, interaction_distance=float(interaction_distance), interaction_count=max(1, int(interaction_count)), interaction_interval_ms=max(0, int(interaction_interval_ms)), timeout_ms=15000, pause_on_combat=False, multi_account=False, include_self=True, log=log)

    interact_next = BT.MoveAndInteractWithGadget(pos=next_pos, gadget_id=None, search_distance=300.0, interaction_distance=float(interaction_distance), interaction_count=max(1, int(interaction_count)), interaction_interval_ms=max(0, int(interaction_interval_ms)), timeout_ms=15000, pause_on_combat=False, multi_account=False, include_self=True, log=log)

    state = {'phase': 'move_to_next', 'started_at': 0.0, 'phase_started_at': 0.0, 'recovery_count': 0}

    def _trace(message: str, message_type=PySystem.Console.MessageType.Info) -> None:
        # Routine brazier progress is intentionally quiet, but real recovery
        # warnings/errors must remain visible.
        if not log and message_type not in (
            PySystem.Console.MessageType.Warning,
            PySystem.Console.MessageType.Error,
        ):
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

        # Reset every phase subtree before starting local recovery.
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
        # --------------------------------------------------------------
        if phase == "interact_next":
            if not _has_active_flame():
                return _begin_recovery(now, 'Torch flame extinguished before the next brazier interaction.')

            result = _tick_tree(interact_next, node)

            if result == BehaviorTree.NodeState.RUNNING:
                return BehaviorTree.NodeState.RUNNING

            if result == BehaviorTree.NodeState.FAILURE:
                # Ne pas laisser FAILURE remonter au planner.
                # Recover locally from the previous brazier.
                return _begin_recovery(now, 'Interaction with the next brazier failed.')

            _trace('Next brazier interaction completed.', PySystem.Console.MessageType.Success)

            _reset_all()

            return BehaviorTree.NodeState.SUCCESS

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


def _configure_botting_tree(tree: BottingTree) -> None:
    tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=_enabled_consumable_upkeeps(),
        enable_party_member_recovery=True,
        party_member_recovery_distance=500.0,
        enable_party_wipe_recovery=True,
        enable_nearest_shrine_recovery=True,
        heroai_state_logging=False,
    )
    tree.EnsureSummoningStonePartyService(
        enabled=lambda: _use_summoning_stone and _consumables_allowed(),
        map_ids=(SOO_LEVEL_1, SOO_LEVEL_2, SOO_LEVEL_3),
        initial_grace_ms=2_000,
        attempt_interval_ms=5_000,
        retry_cycle_delay_ms=15_000,
        log=True,
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


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()
    return BT.Sequence(
        name="Initialize Shards of Orr BT",
        children=[
            ResetTorchCombatPolicy(),
            bot.Config.Aggressive(
                multi_account=True,
                auto_loot=True,
                account_isolation=False,
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
            _dungeon_party.create_party_node(multibox_invite=True, timeout_ms=30_000, log=True),
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
            BT.MoveAndExitMap(VLOXS_EXIT, target_map_id=ARBOR_BAY, log=SHARDS_MOVEMENT_LOGS),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.MoveAndDialog(ARBOR_BLESSING_NPC, dialog_id=ARBOR_BLESSING_DIALOG, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
            ShardsTrapMove(ARBOR_TO_SHANDRA_PATH, pause_on_combat=True, log=False),
            BT.WaitUntilOutOfCombat(timeout_ms=60_000),
            ShardsTrapMove(SHANDRA_APPROACH,avoid_obstacles=False,  pause_on_combat=False, log=False),
        ],
    )
    return BT.Selector(children=[skip_if_already_in_level_1, normal_travel], name="Travel To Shandra")


def TravelToShandraStart() -> BehaviorTree:
    """Planner step: leave Vlox, enter Arbor Bay and take the blessing."""
    skip_if_already_in_level_1 = BT.Sequence(
        name="Skip Travel To Shandra Start - Already In Level 1",
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True),
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state="active", log=True),
            BT.Succeeder("TravelToShandraStartAlreadyDone"),
        ],
    )
    normal_start = BT.Sequence(
        name="Travel To Shandra - Start From Vlox",
        children=[
            BT.MoveAndExitMap(VLOXS_EXIT, target_map_id=ARBOR_BAY, log=SHARDS_MOVEMENT_LOGS),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.MoveAndDialog(ARBOR_BLESSING_NPC, dialog_id=ARBOR_BLESSING_DIALOG, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
        ],
    )
    return BT.Selector(
        children=[skip_if_already_in_level_1, normal_start],
        name="Travel To Shandra - Start",
    )


def TravelToShandraFinalPoint() -> BehaviorTree:
    """Planner step: wait for combat to finish, then make the final Shandra approach."""
    skip_if_already_in_level_1 = BT.Sequence(
        name="Skip Travel To Shandra Final Point - Already In Level 1",
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True),
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state="active", log=True),
            BT.Succeeder("TravelToShandraFinalPointAlreadyDone"),
        ],
    )
    final_approach = BT.Sequence(
        name="Travel To Shandra - Final Point",
        children=[
            BT.IsCurrentMap(map_id=ARBOR_BAY, log=False),
            BT.WaitUntilOutOfCombat(timeout_ms=60_000),
            ShardsTrapMove(SHANDRA_APPROACH, avoid_obstacles=False, pause_on_combat=False, log=False),
        ],
    )
    return BT.Selector(
        children=[skip_if_already_in_level_1, final_approach],
        name="Travel To Shandra - Final Point",
    )


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
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_REWARD_DIALOG, pause_on_combat=False, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
            BT.WaitForQuestCleared(LOST_SOULS_QUEST_ID, timeout_ms=15_000),
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
            BT.WaitForActiveQuest(LOST_SOULS_QUEST_ID, timeout_ms=15_000),
        ],
    )
    missing = BT.Sequence(
        name="Take Lost Souls",
        children=[
            BT.IsQuestState(quest_id=LOST_SOULS_QUEST_ID, state="missing", log=True),
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
            BT.WaitForActiveQuest(LOST_SOULS_QUEST_ID, timeout_ms=15_000),
        ],
    )
    return BT.Selector(children=[already_inside, active, completed, missing], name="Handle Shandra Quest")


def EnterShardsOfOrr(enable_consumables_on_entry: bool=False) -> BehaviorTree:
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
            ShardsTrapMove(SOO_ENTRANCE_PATH, pause_on_combat=False, ignore_destination_obstacles=True, log=False),
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


# Partial party-death pause/regroup/resurrection is provided by the shared
# BottingTree PartyMemberRecoveryService.  Keep Shards focused on dungeon-only
# mechanics such as torches and environmental traps.

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
                lambda point=point, name=name: _map_guarded_point(name=name, map_id=map_id, child=ShardsTrapMove(point, pause_on_combat=pause_on_combat, tolerance=tolerance, flag_heroes_to_waypoint=flag_heroes_to_waypoint, ignore_destination_obstacles=ignore_destination_obstacles, log=False), skip_if_in_maps=skip_if_in_maps),
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
                lambda point=point, name=name: _map_guarded_point(name=name, map_id=map_id, child=ShardsTrapGuard(point, BT.VanquishNode([point], name=name, clear_area_radius=clear_area_radius, pause_on_combat=pause_on_combat, flag_heroes_to_waypoint=flag_heroes_to_waypoint, move_tolerance=move_tolerance, log=False), name=f"Shards Trap Guard - {name}"), skip_if_in_maps=skip_if_in_maps),
            )
        )

    return steps


def _torch_vanquish_point_steps(
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
    """Expose torch-managed Vanquish points as planner steps with recovery inside each step."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"

        def _build(point: PathPoint = point, name: str = name) -> BehaviorTree:
            managed = BT.Sequence(
                name=f'{name} - Torch Managed',
                children=[
                    TorchAwareVanquish(
                        [point],
                        name,
                        clear_area_radius=clear_area_radius,
                        pause_on_combat=pause_on_combat,
                        flag_heroes_to_waypoint=flag_heroes_to_waypoint,
                        move_tolerance=move_tolerance,
                    ),
                    # Recovery is part of the same planner step.  A wipe can
                    # pause/replay the combat without ever skipping this pickup.
                    PickupTorch(),
                ],
            )
            return _map_guarded_point(
                name=name,
                map_id=map_id,
                child=managed,
                skip_if_in_maps=skip_if_in_maps,
            )

        steps.append((name, _build))

    return steps


# endregion
# region Level 1


def Level1_Start() -> BehaviorTree:
    return BT.Sequence(
        name="Start Shards of Orr Level 1",
        children=[
            _runtime_consumable_upkeep_node(True),
            _reset_restart_safe_run_state_node(),
            _mark_run_start_node(),
            _inventory_statistics_node(after_chest=False),
            BT.AddModelToLootWhitelist(25410),
            BT.MoveAndDialog(Vec2f(-11686.0, 10427.0), dialog_id=DWARVEN_BLESSING_DIALOG, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
        ],
    )


def Level1_OpenDoor() -> BehaviorTree:
    return BT.Sequence(
        name='Open Level 1 Door',
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_1, log=True),
            RestartSafeGadgetInteraction(
                'level1_main_door',
                Vec2f(15100.0, 5443.0),
                pause_on_combat=True,
                log=SHARDS_MOVEMENT_LOGS,
            ),
        ],
    )


def Level1_EnterLevel2() -> BehaviorTree:
    name = f"Level 1 Route To Level 2 - Point {len(L1_PATH_AFTER_DOOR):02d}"
    return BT.Sequence(
        name=name,
        children=[
            _map_guarded_point(name=name, map_id=SOO_LEVEL_1, child=BT.Sequence(name=f'{name} And Load Level 2',
            children=[
            BT.MoveAndExitMap(Vec2f(20500.5, 1300.0), target_map_id=SOO_LEVEL_2, log=False),
            BT.WaitForMapLoad(map_id=SOO_LEVEL_2, timeout_ms=60000)]),),
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
            ResetTorchCombatPolicy(),
            ResolveTorchCombatPolicy(),
            BT.AddModelToLootWhitelist(25410),
            BT.MoveAndDialog(L2_BLESSING_NPC, dialog_id=DWARVEN_BLESSING_DIALOG, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
            BT.ClearEnemiesInArea(Vec2f(-15243.0, -17230.0), radius=Range.Compass.value, log=True),
            EnsureTorchFromChest('level2_torch_chest', L2_TORCH_CHEST),
        ],
    )


def Level2_FirstTorchFight() -> BehaviorTree:
    return BT.Sequence(
        name='Level 2 First Torch Fight',
        children=[
            TorchAwareVanquish(
                L2_RETURN_TO_FIRST_TORCH_PATH,
                'Level 2 First Torch Fight',
                clear_area_radius=Range.SafeCompass.value,
                pause_on_combat=True,
            ),
            PickupTorch(),
        ],
    )


def Level2_BrazierRoute1() -> BehaviorTree:
    return BT.Sequence(
        name='Level 2 Brazier Route 1',
        children=[
            RestartSafeBrazierSequence(
                'level2_brazier_route_1',
                'Level 2 Brazier Route 1',
                L2_BRAZIER_PART1,
            )
        ],
    )


# endregion
# region Level 2 - part 2


def Level2_PrepareRoom2() -> BehaviorTree:
    return BT.Sequence(
        name="Prepare Level 2 Room 2",
        children=[
            BT.Wait(2000),
            TorchAwareMoveAndKill(
                Vec2f(-9011.27, -11536.79),
                'Level 2 Prepare Room 2 Combat',
                clear_area_radius=Range.SafeCompass.value,
            ),
            PickupTorch(),
            BT.Wait(2000),
        ],
    )


def Level2_BrazierRoute2() -> BehaviorTree:
    def _build(node: BehaviorTree.Node) -> BehaviorTree:
        if (
            _is_core_shrine_resume(node)
            and 'level2_brazier_route_2' in _restart_safe_completed_mechanics
        ):
            return DiscardTorch(log=False)

        return BT.Sequence(
            name='Level 2 Brazier Route 2 - Restart Safe',
            children=[
                # This mechanic cannot start without the physical torch. Unlike
                # normal shrine-retrace points, do not allow the 5s skip here.
                PickupTorch(allow_shrine_skip=False),
                BrazierSequence('Level 2 Brazier Route 2', L2_BRAZIER_PART2),
                _mark_restart_safe_mechanic_node('level2_brazier_route_2'),
                DiscardTorch(log=TORCH_PROGRESS_LOGS),
            ],
        )

    return BT.Subtree(name='Level 2 Brazier Route 2', subtree_fn=_build)


# endregion


# region Level 2 - part 3


def Level2_OpenDungeonLock() -> BehaviorTree:
    return BT.Sequence(
        name='Open Level 2 Dungeon Lock',
        children=[
            BT.IsCurrentMap(map_id=SOO_LEVEL_2, log=True),
            RestartSafeGadgetInteraction(
                'level2_dungeon_lock',
                L2_DUNGEON_LOCK,
                pause_on_combat=False,
                log=SHARDS_MOVEMENT_LOGS,
            ),
        ],
    )


def Level2_EnterLevel3() -> BehaviorTree:
    name = f"Level 2 Exit Route - Point {len(L2_EXIT_PATH):02d}"
    return BT.Sequence(
        name=name,
        children=[
            _map_guarded_point(name=name, map_id=SOO_LEVEL_2, child=BT.Sequence(name=f'{name} And Load Level 3', children=[ShardsTrapMove(L2_EXIT_PATH[-1], pause_on_combat=False, tolerance=200.0, log=False), BT.WaitForMapLoad(map_id=SOO_LEVEL_3, timeout_ms=60000)]), skip_if_in_maps=(SOO_LEVEL_3,)),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            _mark_l3_start_node(),
            BT.Wait(2_000),
        ],
    )


# endregion

# region Level 3 - entry and torch


def Level3_Start() -> BehaviorTree:
    return BT.Sequence(
        name='Start Shards of Orr Level 3',
        children=[
            BT.MoveAndDialog(L3_ENTRY_BLESSING, dialog_id=DWARVEN_BLESSING_DIALOG, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
        ],
    )


def Level3_TorchAndBraziers() -> BehaviorTree:
    def _build(node: BehaviorTree.Node) -> BehaviorTree:
        if (
            _is_core_shrine_resume(node)
            and 'level3_brazier_route' in _restart_safe_completed_mechanics
        ):
            return DiscardTorch(log=False)

        return BT.Sequence(
            name="Open Level 3 Torch Chest And Light Braziers",
            children=[
                # Resolve the combat policy before pickup because a held bundle can
                # hide the equipped weapon type reported by the game.
                ResetTorchCombatPolicy(),
                ResolveTorchCombatPolicy(),
                EnsureTorchFromChest('level3_torch_chest', L3_TORCH_CHEST),
                BrazierSequence("Level 3 Brazier Route", L3_BRAZIERS),
                _mark_restart_safe_mechanic_node('level3_brazier_route'),
                DiscardTorch(log=TORCH_PROGRESS_LOGS),
            ],
        )

    return BT.Subtree(name='Level 3 Torch And Braziers', subtree_fn=_build)


# endregion


# region Level 3 - Brigant
def Level3_Brigant() -> BehaviorTree:
    return BT.Sequence(
        name="Run Shards of Orr Level 3",
        children=[
            ShardsTrapGuard(Vec2f(-11147, 2644), BT.MoveAndKill(Vec2f(-11147, 2644), clear_area_radius=Range.Spirit.value, log=False), name="Shards Trap Guard - Level 3 Brigant Fight"),
            BT.AddModelToLootWhitelist(25410),
            ShardsTrapMove(Vec2f(-9888.47, 2892.00)),
            BT.LootItems(distance=Range.SafeCompass.value),
            _mark_restart_safe_mechanic_node(_LEVEL3_BOSS_ROUTE_UNLOCKED_KEY),
        ],
    )


def Level3_BrigantDoor() -> BehaviorTree:
    return RestartSafeGadgetInteraction(
        'level3_brigant_door',
        Vec2f(-9252.32, 6396.4),
        pause_on_combat=False,
        log=SHARDS_MOVEMENT_LOGS,
    )


# endregion

# region Level 3 - Fendi


def _set_planner_pause_on_combat(enabled: bool, *, name: str) -> BehaviorTree:
    """Request the shared BottingTree combat gate state on the next HeroAI tick.

    Shards normally keeps the planner paused during combat so route movement cannot
    fight HeroAI.  Fendi is the one deliberate exception: its combat node must keep
    ticking to maintain boss priority and trap avoidance while the fight is active.
    """
    def _apply(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        node.blackboard["pause_on_combat_request"] = bool(enabled)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name=name, action_fn=_apply, aftercast_ms=0))


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

        if target_changed or interaction_due:
            Player.ChangeTarget(target_id)
            try:
                Player.CallTarget(target_id)
            except Exception:
                pass
            try:
                Player.Interact(target_id, False)
            except Exception:
                pass
            state["last_interact_ms"] = now_ms

        if target_changed:
            target_name = _fendi_enemy_name(target_id) or f"agent {target_id}"
            try:
                boss_glow = bool(Agent.HasBossGlow(target_id))
            except Exception:
                boss_glow = False

            PySystem.Console.Log(MODULE_NAME, f'Fendi priority target -> {target_name} (id={target_id}, priority={priority_label}, boss_glow={boss_glow}, enemies={len(enemies)}).', PySystem.Console.MessageType.Info)
            state["last_target_id"] = target_id

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name='Clear Fendi Arena With Boss Priority', action_fn=_fight, aftercast_ms=0))


def Level3_FendiFight() -> BehaviorTree:
    return BT.Sequence(
        name="Run Fendi Boss Fight",
        children=[
            # Defense in depth for restarts: route movement keeps the normal
            # planner combat gate until the dedicated Fendi arena node begins.
            _set_planner_pause_on_combat(True, name="Fendi - Keep Planner Paused During Approach"),
            ShardsTrapMove(Vec2f(-13198.79, 13789.36), log=SHARDS_MOVEMENT_LOGS),
            # Fendi is intentionally different from route movement.  Its combat
            # logic must keep ticking so boss priority and trap avoidance remain
            # active while HeroAI is fighting.
            _set_planner_pause_on_combat(False, name="Fendi - Allow Planner Combat Tick"),
            ShardsCombatTrapAvoid(
                ClearFendiArenaWithBossPriority(),
                name="Fendi Priority Combat - Trap Avoid",
            ),
            ShardsCombatTrapAvoid(
                BT.ClearEnemiesInArea(Vec2f(*FENDI_FIGHT_CENTER), radius=FENDI_FIGHT_RADIUS, log=True),
                name="Fendi Final Clear - Trap Avoid",
            ),
            ShardsCombatTrapAvoid(
                BT.WaitForClearEnemiesInArea(*FENDI_FIGHT_CENTER, radius=FENDI_FIGHT_RADIUS, allowed_alive_enemies=0, interact_interval_ms=750, stable_clear_ms=FENDI_STABLE_CLEAR_MS, keep_player_near_center=False, center_tolerance=750.0, log=True),
                name="Fendi Stable Clear - Trap Avoid",
            ),
            _set_planner_pause_on_combat(True, name="Fendi - Restore Planner Combat Pause"),
        ],
    )
# endregion

# region Level 3 - chest

def Level3_Chest() -> BehaviorTree:
    """Stage the party at the chest, stop the timer, suspend consumables,
    then open the final chest in multibox while normal auto-loot remains active.
    """

    return BT.Sequence(
        name="Open Fendi Chest",
        children=[
            ShardsTrapMove(Vec2f(-15198.0, 16839.0), pause_on_combat=False, log=False),
            ShardsTrapMove(FENDI_CHEST_SAFE_POSITION, pause_on_combat=False, log=False),
            # The timed run ends at the chest, immediately before interaction.
            _record_run_end_node(),
            # From this point until the next Level 1 start, consets, direct PCons
            # and summoning-stone usage/recovery are all suspended. Auto-loot stays on.
            _runtime_consumable_upkeep_node(False),
            BT.MoveAndInteractWithGadget(gadget_id=FENDI_CHEST_GADGET_ID, pos=Vec2f(*FENDI_CHEST_POSITION), search_distance=700.0, interaction_distance=Range.Nearby.value, interaction_count=2, interaction_interval_ms=1000, account_settle_ms=3000, timeout_ms=90000, multi_account=True, include_self=True, log=SHARDS_MOVEMENT_LOGS),
            _inventory_statistics_node(after_chest=True),
        ],
    )

# endregion


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
            ShardsTrapMove(FENDI_CHEST_SAFE_POSITION, pause_on_combat=False, log=False),
        ],
    )


def ResolveShandraQuestAfterRun() -> BehaviorTree:
    """Leave Arbor Bay with Lost Souls active, without starting the next run."""
    direct_retake = BT.Sequence(
        name="Retake Lost Souls Directly",
        children=[
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
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
            ShardsTrapMove([Vec2f(10218.0, -18864.0), SHANDRA_APPROACH], pause_on_combat=False, log=False),
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
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
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_REWARD_DIALOG, pause_on_combat=False, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
            BT.WaitForQuestCleared(LOST_SOULS_QUEST_ID, timeout_ms=15000),
            BT.LogMessage(message='The Lost Souls reward was collected successfully in Arbor Bay.', module_name=MODULE_NAME),

            # Guild Wars requires one entry into Level 1 after an outside
            # reward before Shandra offers Lost Souls again.
            EnterShardsOfOrr(enable_consumables_on_entry=False),
            BT.MoveAndExitMap(LEVEL1_EXIT_TO_ARBOR, target_map_id=ARBOR_BAY, log=False),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            ShardsTrapMove([Vec2f(10218.0, -18864.0), SHANDRA_APPROACH], pause_on_combat=False, log=False),
            BT.MoveAndDialog(SHANDRA_APPROACH, SHANDRA_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=SHARDS_MOVEMENT_LOGS),
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
            _dungeon_party.create_party_node(multibox_invite=True, timeout_ms=30_000, log=True),
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
            ShardsTrapMove(FENDI_CHEST_SAFE_POSITION, pause_on_combat=False, log=False),
        ],
    )

    return BT.Sequence(
        name="Collect Reward And Return To Arbor",
        children=[
            BT.Selector(name='Resolve Inside Reward', children=[already_in_arbor, reward_collected_inside, reward_not_collected_inside]),
            BT.LogMessage(message='Waiting for the end-of-dungeon countdown and the return to Arbor Bay.', module_name=MODULE_NAME),
            BT.WaitForMapLoad(map_id=ARBOR_BAY, timeout_ms=end_countdown_timeout_ms),
            BT.WaitUntilOnExplorable(timeout_ms=30000),
            BT.Wait(2000),
            BT.LogMessage(message='The party has returned to Arbor Bay. Preparing the next dungeon run.', module_name=MODULE_NAME),
            ShardsTrapMove(SHANDRA_APPROACH,pause_on_combat=False,log=False),
        ],
    )


# endregion


# region Execution

def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    run_steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        ("Travel To Shandra - Start", TravelToShandraStart),
        *_movement_point_steps(
            "Travel To Shandra",
            ARBOR_BAY,
            ARBOR_TO_SHANDRA_PATH,
            pause_on_combat=True,
            skip_if_in_maps=(SOO_LEVEL_1,),
        ),
        (f"Travel To Shandra - Point {len(ARBOR_TO_SHANDRA_PATH) + 1:02d}", TravelToShandraFinalPoint),
        ("Handle Shandra Quest", HandleShandraQuest),
        ("Enter Shards Of Orr", EnterShardsOfOrr),

        ("Level 1 Start", Level1_Start),
        *_vanquish_point_steps("Level 1 First Route", SOO_LEVEL_1, L1_PATH, skip_if_in_maps=(SOO_LEVEL_2, SOO_LEVEL_3)),
        ("Level 1 Open Door", Level1_OpenDoor),
        *_vanquish_point_steps("Level 1 Route To Level 2", SOO_LEVEL_1, L1_PATH_AFTER_DOOR[:-1], skip_if_in_maps=(SOO_LEVEL_2, SOO_LEVEL_3)),
        (f"Level 1 Route To Level 2 - Point {len(L1_PATH_AFTER_DOOR):02d}", Level1_EnterLevel2),

        ("Level 2 Start", Level2_Start),
        *_torch_vanquish_point_steps("Level 2 First Torch Drop Route", SOO_LEVEL_2, L2_FIRST_TORCH_DROP_POINT_PATH, pause_on_combat=True, skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 First Torch Fight", Level2_FirstTorchFight),
        *_torch_vanquish_point_steps("Level 2 First Brazier Approach", SOO_LEVEL_2, [Vec2f(-9404.44, -17963.49), Vec2f(-11303.00, -14596.00)], pause_on_combat=True, skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 Brazier Route 1", Level2_BrazierRoute1),
        ("Level 2 Prepare Room 2", Level2_PrepareRoom2),
        *_torch_vanquish_point_steps("Level 2 Route To Room 2 Drop", SOO_LEVEL_2, L2_TO_ROOM2_DROP, clear_area_radius=Range.Area.value, pause_on_combat=True, skip_if_in_maps=(SOO_LEVEL_3,)),
        *_torch_vanquish_point_steps("Level 2 Route Back To Room 2 Torch", SOO_LEVEL_2, L2_RETURN_TO_ROOM2_TORCH_PATH, skip_if_in_maps=(SOO_LEVEL_3,)),
        *_torch_vanquish_point_steps("Level 2 Room 2", SOO_LEVEL_2, L2_ROOM2_PATH, move_tolerance=150.0, skip_if_in_maps=(SOO_LEVEL_3,)),
        *_torch_vanquish_point_steps("Level 2 Room 2 Final Fight", SOO_LEVEL_2, [Vec2f(-4245.2, -2101.0)], skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 Brazier Route 2", Level2_BrazierRoute2),
        *_vanquish_point_steps("Level 2 Route To Dungeon Lock", SOO_LEVEL_2, L2_PATH_TO_LOCK, pause_on_combat=True, skip_if_in_maps=(SOO_LEVEL_3,)),
        ("Level 2 Open Dungeon Lock", Level2_OpenDungeonLock),
        *_movement_point_steps("Level 2 Exit Route", SOO_LEVEL_2, L2_EXIT_PATH[:-1], pause_on_combat=False, skip_if_in_maps=(SOO_LEVEL_3,)),
        (f"Level 2 Exit Route - Point {len(L2_EXIT_PATH):02d}", Level2_EnterLevel3),

        *[
            _skip_if_level3_boss_route_unlocked(step_name, factory)
            for step_name, factory in [
                ("Level 3 Start", Level3_Start),
                *_vanquish_point_steps("Level 3 Main Route", SOO_LEVEL_3, L3_MAIN_PATH),
                *_vanquish_point_steps("Level 3 Brigant Room Route", SOO_LEVEL_3, L3_BRIGANT_ROOM),
                *_movement_point_steps("Level 3 Torch Route", SOO_LEVEL_3, L3_PATH_TO_TORCH, pause_on_combat=False),
                ("Level 3 Torch And Braziers", Level3_TorchAndBraziers),
                ("Level 3 Brigant", Level3_Brigant),
            ]
        ],
        ("Level 3 Brigant Door", Level3_BrigantDoor),
        *_vanquish_point_steps("Level 3 Route To Fendi", SOO_LEVEL_3, L3_FENDI_PATH),
        ("Level 3 Fendi Boss Fight", Level3_FendiFight),
        ("Level 3 Chest", Level3_Chest),
    ]

    return [
        ("Initialize Bot", InitializeBot),
        ("Prepare Party And Supplies", PreparePartyAndSupplies),

        *run_steps,

        ("Collect Reward And Return To Arbor", CollectRewardAndReturnToArbor),
        ("Resolve Shandra Quest", ResolveShandraQuestAfterRun),
        ("Inventory Check And Maintenance", InventoryCheckAndMaintenance),
        ("Prepare Next Dungeon Run", PrepareNextDungeonRun),
    ]

# endregion


def tooltip():
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
        "A complete multibox BottingTree automation for Shards of Orr. "
        "The run starts from Vlox's Falls, handles the Lost Souls quest and "
        "progresses through all three dungeon levels before defeating Fendi, "
        "opening the final chest and preparing the party for the next run."
    )
    PyImGui.spacing()

    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text(
        "Automates the complete Level 1, Level 2 and Level 3 dungeon route."
    )
    PyImGui.bullet_text(
        "Handles dungeon doors, blessings, torches, braziers and the Fendi encounter."
    )
    PyImGui.bullet_text(
        "Supports multibox party control, shared dialogs and synchronized dungeon progression."
    )
    PyImGui.bullet_text(
        "Configurable Normal/Hard Mode, consets, personal consumables and summoning stones."
    )
    PyImGui.bullet_text(
        "Multibox inventory maintenance can trigger MerchantRules when an active account "
        "falls below the configured thresholds."
    )
    PyImGui.bullet_text(
        "Tracks run times, floor times and selected final-chest drops across accounts."
    )
    PyImGui.spacing()

    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Shards of Orr BottingTree implementation: Sky.")
    PyImGui.bullet_text("Built on Py4GW and the BottingTree framework by Apo and contributors.")

    PyImGui.end_tooltip()


def main() -> None:
    global initialized

    if not initialized:
        _load_settings()
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    _sync_consumable_upkeeps()
    tree.tick()
    _tick_direct_pcon_upkeep()
    attach_botting_tree_support(tree)
    tree.UI.draw_window(icon_path=TEXTURE, iconwidth=96, main_child_dimensions=(550, 380), extra_tabs=[('Statistics', _draw_statistics), ('Party', _dungeon_party.draw_tab), ('Config', _draw_run_config), ('Restock', _draw_restock_config)])


# endregion


if __name__ == "__main__":
    main()
