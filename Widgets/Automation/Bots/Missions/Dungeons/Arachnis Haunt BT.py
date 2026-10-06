from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import time

import PyImGui
import PySystem

from Py4GWCoreLib import (
    Agent,
    AgentArray,
    GLOBAL_CACHE,
    Inventory,
    Map,
    Player,
    Routines,
    SharedCommandType,
)
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.Item import has_active_party_summon
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
from Sources.Sky.DungeonParty import DungeonPartyConfig
from Sources.Sky.Support import attach_botting_tree_support
from Widgets.System.Messaging import get_inventory_count, reset_inventory_count, get_inventory_state, reset_inventory_state


PathPoint = Vec2f | tuple[float, float] | tuple[int, int] | tuple[float, float, int] | tuple[int, int, int]

TEXTURE = os.path.join(PySystem.Console.get_projects_path(), 'Assets', 'Textures', 'Module_Icons', 'arachni2.png')
MODULE_ICON = "Assets\\Textures\\Module_Icons\\arachni2.png"

# =============================================================================
# Metadata
# =============================================================================

MODULE_NAME = "Arachni's Haunt BT"
MODULE_CATEGORY = "Automation"
MODULE_TAGS = ["Arachni's Haunt", "Dungeon", "Asura Flame Staff"]
MODULE_ALIASES = ["Arachni", "Arachnis", "Arachni's Haunt"]

MODULE_DESCRIPTION = """Multibox BottingTree automation for Arachni's Haunt.

Current draft follows the supplied two-floor route, Scrambled Reinforcements,
Asura Flame Staff / web / Spider Egg mechanics, Hixx reward flow and repeat.
"""

INI_PATH = "Widgets/Automation/Bots/Missions/Dungeons/Arachnis Haunt BT"
INI_FILENAME = "Arachnis_Haunt_BT.ini"


# =============================================================================
# Game identifiers
# =============================================================================

RATA_SUM = 640
MAGUS_STONES = 569
ARACHNI_LEVEL_1 = 584
ARACHNI_LEVEL_2 = 585

# Scrambled Reinforcements.
# Dialog family 0x831A corresponds to quest 0x31A, following the same encoding
# used by the other EotN dungeon quest dialogs.
SCRAMBLED_REINFORCEMENTS_QUEST_ID = 0x31A
HIXX_TAKE_DIALOG = 0x831A01
HIXX_REWARD_DIALOG = 0x831A07

ASURA_FLAME_STAFF_MODEL_ID = 24350
ASURA_FLAME_STAFF_MODEL_IDS = (ASURA_FLAME_STAFF_MODEL_ID,)
DUNGEON_KEY_MODEL_ID = 25410

# Final chest drop tracked by the Statistics tab.
# IMPORTANT: no reliable public source currently exposes the Guild Wars item
# ModelID for Insectoid Scythe. Keep this disabled instead of guessing.
# The chest discovery probe below logs new ModelIDs after Arachni's Spoils,
# making the exact ID directly observable on the first relevant drop.
INSECTOID_SCYTHE_MODEL_ID = 2062

SUMMON_MODEL_IDS = (37810, 30209, 31155)

PCON_UPKEEPS = tuple(
    int(model_id)
    for model_id in ALL_CONSUMABLE_UPKEEPS
    if int(model_id) not in CONSET_UPKEEPS
)
CONSET_RESTOCK_ITEMS = tuple(
    (int(model_id), 10)
    for model_id in CONSET_UPKEEPS
)
PCON_RESTOCK_ITEMS = tuple(
    (int(model_id), 10)
    for model_id in PCON_UPKEEPS
)
SUMMON_RESTOCK_ITEMS = tuple(
    (int(model_id), 10)
    for model_id in SUMMON_MODEL_IDS
)

# Inventory maintenance - same multibox MerchantRules flow as Shards of Orr.
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


# =============================================================================
# Coordinates / routes
# =============================================================================

RATA_EXIT = Vec2f(16408, 13467)

HIXX_QUEST_POSITION = Vec2f(-10121.00, -17087.00)
ARACHNI_ENTRANCE = Vec2f(-11487,-19073)

MAGUS_ROUTE_TO_HIXX = (
    (17569, 7596),
    (17065, -2078),
    (8300, -1399),
    (7310, -8574),
    (1496, -6595),
    (-3885, -10862),
    (-11430, -11481),
    (-8833, -16800),
    (-9386, -17217),
)

L1_ROUTE_TO_FIRST_STAFF = (
    (15920, 18220),
    (12390, 19660),
)

L1_WEB_1_BEFORE = Vec2f(12390, 19660)
L1_WEB_1_AFTER = Vec2f(11654, 19468)

L1_ROUTE_AFTER_WEB_1 = (
    (10042, 19039),
    (8697, 16821),
    (4829, 10355),
    (2372, 7958),
    (784, 9636),
    (-3441, 7418),
    (-5797, 7819),
    (-12839, 3761),
)

L1_WEB_2_BEFORE = Vec2f(-14526, 2459)
L1_WEB_2_AFTER = Vec2f(-15089, 2107)

L1_ROUTE_TO_EGG_GROUP_1 = (
    (-16729, 2640),
    (-18352, 3386),
    (-17643, 4460),
    (-15897, 4575),
    (-14919, 6378),
    (-15437, 7893),
    (-17662, 8641),
)

L1_EGG_GROUP_1 = (
    (-18845.00, 9089.00),
    (-18781.00, 9082.00),
    (-18648.00, 8265.00),
    (-18593.00, 8218.00),
    (-18677.00, 8200.00),
)

L1_ROUTE_TO_EGG_GROUP_2 = (
    (-16850, 11655),
    (-11222, 13743),
    (-3636, 16275),
)

L1_EGG_GROUP_2 = (
    (-3079.00, 16649.00),
    (-3010.00, 16674.00),
    (-2787.00, 16940.00),
    (-2739.00, 17000.00),
    (-2670.00, 17034.00),
)

L1_ROUTE_TO_WEB_3 = (
    (-1692, 17767),
    (-446, 17209),
)

L1_WEB_3_BEFORE = Vec2f(271, 16851)
L1_WEB_3_AFTER = Vec2f(916, 16565)

L1_ROUTE_TO_LOCK = (
    (2930, 16963),
    (2630, 19256),
)

L1_DUNGEON_LOCK = Vec2f(2072.00, 19791.00)
L1_EXIT_TO_LEVEL_2 = Vec2f(1358, 20065)

L2_STAFF_POSITION = Vec2f(12562, 16504)

L2_ROUTE_1 = (
    (12442, 14756),
    (10261, 9543),
)

L2_WEB_1_BEFORE = Vec2f(8534, 10960)
L2_WEB_1_AFTER = Vec2f(8298, 11257)

L2_ROUTE_2 = (
    (5862, 10498),
    (3249, 9839),
    (653, 11351),
)

L2_WEB_2_BEFORE = Vec2f(-111, 11909)
L2_WEB_2_AFTER = Vec2f(-440, 12183)

L2_ROUTE_3 = (
    (-3039, 12463),
    (-6061, 11791),
    (-7837, 12370),
    (-10186, 18128),
    (-15464, 18426),
)

L2_WEB_3_BEFORE = Vec2f(-15342, 16258)
L2_WEB_3_AFTER = Vec2f(-15316, 15860)

L2_ROUTE_TO_EGGS = (
    (-18060, 14298),
    (-18273, 12255),
    (-16826, 9488),
    (-16017, 10637),
    (-14017, 12170),
    (-13378, 14042),
    (-15336, 13872),
)

L2_EGG_GROUP_1 = (
    (-14091.00, 11739.00, 8819),
    (-14147.00, 11683.00, 8820),
    (-13520.00, 11955.00, 8823),
    (-13487.00, 11888.00, 8821),
    (-13507.00, 11803.00, 8822),
)

L2_EGG_GROUP_2 = (
    (-17178.00, 11320.00, 8827),
    (-17264.00, 11332.00, 8565),
    (-17331.00, 11597.00, 8826),
    (-17386.00, 11770.00, 8825),
    (-17394.00, 11675.00, 8824),
)

L2_BOSS_STAGING = Vec2f(-14351.38, 11640.90)
L2_FINAL_CHEST_POSITION = Vec2f(-17206.00, 11618.00)


# =============================================================================
# Settings / UI state
# =============================================================================

_SETTINGS_SECTION = "Settings"
_STATS_SECTION = "Statistics"
_SCYTHE_DROPS_SECTION = "Insectoid Scythe Drops"
_SCYTHE_SNAPSHOT_SECTION = "Insectoid Scythe Snapshot"
_SCYTHE_RUN_SECTION = "Insectoid Scythe Run"
_CHAR_NAMES_SECTION = "Character Names"

_settings = Settings(f"{INI_PATH}/{INI_FILENAME}", "global")
_dungeon_party = DungeonPartyConfig(_settings)

_INVENTORY_QUERY_POLL_MS = 200
_INVENTORY_QUERY_TIMEOUT_MS = 10_000

_settings_loaded = False

_use_hard_mode = True
_restock_conset = True
_activate_conset = True
_restock_pcons = True
_activate_pcons = True
_use_summoning_stone = True

_inventory_maintenance_enabled = True
_inventory_min_free_slots = 5
_inventory_min_id_kits = 1
_inventory_min_salvage_kits = 2
_inventory_status_snapshot: dict[str, dict[str, object]] = {}

_runtime_consumables_enabled = True
_configured_consumable_upkeeps: tuple[int, ...] | None = None

_PCON_DIRECT_DISPATCH_INTERVAL_MS = 650
_pcon_direct_index = 0
_pcon_direct_last_dispatch_ms = 0

# Staff state, adapted from Shards torch handling.
_MARTIAL_PRIMARY_PROFESSIONS = {
    "Warrior",
    "Ranger",
    "Assassin",
    "Dervish",
    "Paragon",
}
_drop_staff_for_combat: bool | None = None
_last_staff_drop_position: tuple[float, float] | None = None
_shrine_recovery_staff_skip_active = False

# Statistics.
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

# Persistent and session-only Insectoid Scythe drop counters.
_scythe_drops: dict[str, int] = {}
_char_names: dict[str, str] = {}
_session_runs = 0
_session_scythe: dict[str, int] = {}
_scramble_accounts = False

# Chest-model discovery is session-only and intentionally generic while the
# exact Insectoid Scythe ModelID remains unresolved.
_chest_model_snapshot: dict[str, dict[int, int]] = {}
_last_chest_model_deltas: dict[str, dict[int, int]] = {}
_scythe_tracking_warning_logged = False

_t_run_start = 0.0
_t_l2_start = 0.0

_current_run_time = 0.0
_current_l1_time = 0.0
_current_l2_time = 0.0

_statistics_reset_pending = False

initialized = False
botting_tree: BottingTree | None = None


# =============================================================================
# Settings
# =============================================================================

def _load_settings() -> None:
    global _settings_loaded
    global _use_hard_mode
    global _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons
    global _use_summoning_stone
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots
    global _inventory_min_id_kits
    global _inventory_min_salvage_kits

    if _settings_loaded:
        _load_statistics()
        return

    _use_hard_mode = _settings.get_bool(
        _SETTINGS_SECTION,
        "HardMode",
        True,
    )
    _restock_conset = _settings.get_bool(
        _SETTINGS_SECTION,
        "RestockConset",
        True,
    )
    _activate_conset = _settings.get_bool(
        _SETTINGS_SECTION,
        "ActivateConset",
        True,
    )
    _restock_pcons = _settings.get_bool(
        _SETTINGS_SECTION,
        "RestockPcons",
        True,
    )
    _activate_pcons = _settings.get_bool(
        _SETTINGS_SECTION,
        "ActivatePcons",
        True,
    )
    _use_summoning_stone = _settings.get_bool(
        _SETTINGS_SECTION,
        "UseSummoningStone",
        True,
    )
    _inventory_maintenance_enabled = _settings.get_bool(
        _SETTINGS_SECTION,
        "InventoryMaintenanceEnabled",
        True,
    )
    _inventory_min_free_slots = max(
        0,
        _settings.get_int(
            _SETTINGS_SECTION,
            "InventoryMinFreeSlots",
            5,
        ),
    )
    _inventory_min_id_kits = max(
        0,
        _settings.get_int(
            _SETTINGS_SECTION,
            "InventoryMinIdKits",
            1,
        ),
    )
    _inventory_min_salvage_kits = max(
        0,
        _settings.get_int(
            _SETTINGS_SECTION,
            "InventoryMinSalvageKits",
            2,
        ),
    )

    _settings_loaded = True
    _load_statistics()


def _save_settings() -> None:
    _settings.set(_SETTINGS_SECTION, "HardMode", _use_hard_mode)
    _settings.set(_SETTINGS_SECTION, "RestockConset", _restock_conset)
    _settings.set(_SETTINGS_SECTION, "ActivateConset", _activate_conset)
    _settings.set(_SETTINGS_SECTION, "RestockPcons", _restock_pcons)
    _settings.set(_SETTINGS_SECTION, "ActivatePcons", _activate_pcons)
    _settings.set(
        _SETTINGS_SECTION,
        "UseSummoningStone",
        _use_summoning_stone,
    )
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


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    if not _runtime_consumables_enabled:
        return ()
    if not _activate_conset:
        return ()
    return tuple(int(model_id) for model_id in CONSET_UPKEEPS)


def _runtime_difficulty_node() -> BehaviorTree:
    return BT.Subtree(
        name="Apply Selected Difficulty",
        subtree_fn=lambda _node: BT.SetHardMode(
            _use_hard_mode,
            log=True,
        ),
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
            return BT.Succeeder("RestockDisabled")

        return BT.RestockItemsFromList(
            tuple(items),
            allow_missing=True,
        )

    return BT.Subtree(
        name="Restock Selected Consumables",
        subtree_fn=_build,
    )


def _configure_runtime_upkeeps() -> None:
    global _configured_consumable_upkeeps

    if botting_tree is None:
        return

    enabled_consumables = _enabled_consumable_upkeeps()

    botting_tree.Config.ConfigureUpkeep(
        looting_enabled=True,
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


def _sync_consumable_upkeeps() -> None:
    if _enabled_consumable_upkeeps() != _configured_consumable_upkeeps:
        _configure_runtime_upkeeps()


def _draw_run_config() -> None:
    global _use_hard_mode
    global _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons
    global _use_summoning_stone
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots
    global _inventory_min_id_kits
    global _inventory_min_salvage_kits

    _load_settings()

    PyImGui.text("Arachni's Haunt Run Config")
    PyImGui.separator()

    changed = False
    upkeep_changed = False

    value = PyImGui.checkbox("Hard Mode (HM)", _use_hard_mode)
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

    PyImGui.separator()
    PyImGui.text("Summoning stones")

    value = PyImGui.checkbox(
        "Use summoning stones",
        _use_summoning_stone,
    )
    if value != _use_summoning_stone:
        _use_summoning_stone = value
        changed = True

    PyImGui.separator()
    PyImGui.text("Asura Flame Staff")
    PyImGui.text_wrapped(
        "Automatic Shards-style handling: martial builds keep the staff while "
        "travelling, drop it only when combat reaches them, then recover it "
        "after the Vanquish step. Caster builds keep carrying it. Explicit "
        "forced-drop mechanics in the route override this policy."
    )

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
            "Minimum Superior ID kits (0 = disabled)",
            _inventory_min_id_kits,
        )
        value = max(0, int(value))
        if value != _inventory_min_id_kits:
            _inventory_min_id_kits = value
            changed = True

        value = PyImGui.input_int(
            "Minimum Superior salvage kits (0 = disabled)",
            _inventory_min_salvage_kits,
        )
        value = max(0, int(value))
        if value != _inventory_min_salvage_kits:
            _inventory_min_salvage_kits = value
            changed = True

        PyImGui.text_wrapped(
            "Same multibox maintenance flow as Shards of Orr. Every active "
            "account is queried locally. If one account falls below a configured "
            "threshold, MerchantRules runs on all active accounts in Rata Sum. "
            "InventoryPlus is temporarily disabled during maintenance and restored "
            "afterward. Equipment Pack is excluded from the slot thresholds."
        )

    if changed:
        _save_settings()

    if upkeep_changed:
        _configure_runtime_upkeeps()


# =============================================================================
# Statistics
# =============================================================================

def _account_key(email: str) -> str:
    return str(email).replace("@", "_at_").replace(".", "_")


def _display_email(key: str) -> str:
    return str(key).replace("_at_", "@").replace("_", ".")


def _known_account_keys() -> list[str]:
    return sorted(
        key
        for key in (set(_scythe_drops) | set(_session_scythe))
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


def _load_statistics() -> None:
    global _statistics_loaded
    global _total_runs, _total_run_time
    global _fastest_run, _slowest_run
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

    _scythe_drops.pop("local", None)
    _session_scythe.pop("local", None)
    _char_names.pop("local", None)

    for key in _settings.items(_SCYTHE_DROPS_SECTION).keys():
        if key == "local":
            continue
        _scythe_drops[key] = _settings.get_int(_SCYTHE_DROPS_SECTION, key, 0)

    for seed_section in (_SCYTHE_SNAPSHOT_SECTION, _SCYTHE_RUN_SECTION):
        for key in _settings.items(seed_section).keys():
            if key == "local":
                continue
            _scythe_drops.setdefault(key, 0)

    for key in _settings.items(_CHAR_NAMES_SECTION).keys():
        if key == "local":
            continue
        name = str(_settings.get_str(_CHAR_NAMES_SECTION, key, "") or "").strip()
        if name:
            _char_names[key] = name

    _statistics_loaded = True


def _save_statistics() -> None:
    _settings.set(_STATS_SECTION, "total_runs", _total_runs)
    _settings.set(_STATS_SECTION, "total_run_time", _total_run_time)
    _settings.set(
        _STATS_SECTION,
        "fastest_run",
        0.0 if _fastest_run == float("inf") else _fastest_run,
    )
    _settings.set(_STATS_SECTION, "slowest_run", _slowest_run)

    for floor, total, fastest, slowest in (
        ("l1", _l1_total_time, _l1_fastest, _l1_slowest),
        ("l2", _l2_total_time, _l2_fastest, _l2_slowest),
    ):
        _settings.set(_STATS_SECTION, f"{floor}_total_time", total)
        _settings.set(
            _STATS_SECTION,
            f"{floor}_fastest",
            0.0 if fastest == float("inf") else fastest,
        )
        _settings.set(_STATS_SECTION, f"{floor}_slowest", slowest)

    for key, total in _scythe_drops.items():
        if key != "local":
            _settings.set(_SCYTHE_DROPS_SECTION, key, total)

    for key, name in _char_names.items():
        if key != "local":
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


def MarkRunStart() -> BehaviorTree:
    def _mark() -> None:
        global _t_run_start, _t_l2_start
        global _current_run_time
        global _current_l1_time, _current_l2_time

        _t_run_start = time.monotonic()
        _t_l2_start = 0.0

        _current_run_time = 0.0
        _current_l1_time = 0.0
        _current_l2_time = 0.0

    return _statistics_action_node("Mark Arachni Run Start", _mark)


def MarkLevel2Start() -> BehaviorTree:
    def _mark() -> None:
        global _t_l2_start, _current_l1_time

        now = time.monotonic()
        _t_l2_start = now

        if _t_run_start > 0.0:
            _current_l1_time = now - _t_run_start

    return _statistics_action_node("Mark Arachni Level 2 Start", _mark)


def RecordSuccessfulRun() -> BehaviorTree:
    def _record() -> None:
        global _total_runs, _session_runs
        global _total_run_time
        global _fastest_run, _slowest_run
        global _l1_total_time, _l1_fastest, _l1_slowest
        global _l2_total_time, _l2_fastest, _l2_slowest
        global _current_run_time
        global _current_l1_time, _current_l2_time
        global _t_run_start, _t_l2_start

        now = time.monotonic()

        if _t_run_start > 0.0 and _t_l2_start > _t_run_start:
            run_time = now - _t_run_start
            l1_time = _t_l2_start - _t_run_start
            l2_time = now - _t_l2_start

            _current_run_time = run_time
            _current_l1_time = l1_time
            _current_l2_time = l2_time

            _total_run_time += run_time
            _fastest_run = min(_fastest_run, run_time)
            _slowest_run = max(_slowest_run, run_time)

            _l1_total_time += l1_time
            _l1_fastest = min(_l1_fastest, l1_time)
            _l1_slowest = max(_l1_slowest, l1_time)

            _l2_total_time += l2_time
            _l2_fastest = min(_l2_fastest, l2_time)
            _l2_slowest = max(_l2_slowest, l2_time)

            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f"[Statistics] Run complete - Total {run_time:.0f}s | "
                    f"L1 {l1_time:.0f}s | L2 {l2_time:.0f}s"
                ),
                PySystem.Console.MessageType.Success,
            )

        _total_runs += 1
        _session_runs += 1
        _t_run_start = 0.0
        _t_l2_start = 0.0
        _save_statistics()

    return _statistics_action_node("Record Successful Arachni Run", _record)


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


def _inventory_count(model_id: int) -> int:
    return int(GLOBAL_CACHE.Inventory.GetModelCount(int(model_id)))


def _shared_inventory_count(account: object, model_id: int) -> int | None:
    inventory_bags = getattr(account, "InventoryBags", None)
    if inventory_bags is None:
        return None

    try:
        bags = list(inventory_bags.iter_bags())
    except Exception:
        return None

    if not bags:
        return None

    wanted = int(model_id)
    total = 0
    saw_slots_container = False

    try:
        for bag in bags:
            slots = getattr(bag, "Slots", None)
            if slots is None:
                continue
            saw_slots_container = True
            for slot in slots:
                if int(getattr(slot, "ModelID", 0) or 0) == wanted:
                    total += max(0, int(getattr(slot, "Quantity", 0) or 0))
    except Exception:
        return None

    return total if saw_slots_container else None


def _inventory_statistics_node(*, after_chest: bool) -> BehaviorTree:
    node_name = (
        "Record Insectoid Scythe After Final Chest"
        if after_chest
        else "Snapshot Insectoid Scythe Before Final Chest"
    )
    state: dict[str, object] = {
        "started": False,
        "local_email": "",
        "account_keys": [],
        "pending": {},
        "request_started_at": 0.0,
        "local_email_wait_started_at": 0.0,
    }

    def _reset() -> None:
        state["started"] = False
        state["local_email"] = ""
        state["account_keys"] = []
        state["pending"] = {}
        state["request_started_at"] = 0.0
        state["local_email_wait_started_at"] = 0.0

    def _tracking_disabled() -> bool:
        global _scythe_tracking_warning_logged

        if int(INSECTOID_SCYTHE_MODEL_ID) > 0:
            return False

        if not _scythe_tracking_warning_logged:
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "[Statistics] Insectoid Scythe tracking is disabled because "
                    "its exact ModelID is still unverified. Chest ModelID discovery "
                    "remains active."
                ),
                PySystem.Console.MessageType.Warning,
            )
            _scythe_tracking_warning_logged = True
        return True

    def _start() -> bool:
        if _tracking_disabled():
            return True

        _load_statistics()
        _refresh_character_names()

        local_email = str(Player.GetAccountEmail() or "").strip()
        if not local_email:
            return False

        local_key = _account_key(local_email)
        section = _SCYTHE_RUN_SECTION if after_chest else _SCYTHE_SNAPSHOT_SECTION
        model_id = int(INSECTOID_SCYTHE_MODEL_ID)

        _settings.set(section, local_key, _inventory_count(model_id))

        account_keys = [local_key]
        pending: dict[str, dict[str, object]] = {}

        for account in _shared_accounts():
            email = str(getattr(account, "AccountEmail", "") or "").strip()
            if not email or email == local_email:
                continue

            key = _account_key(email)
            if key not in account_keys:
                account_keys.append(key)

            mirrored_count = _shared_inventory_count(account, model_id)
            if mirrored_count is not None:
                _settings.set(section, key, int(mirrored_count))
                continue

            reset_inventory_count(email, model_id, model_id)
            _settings.set(section, key, -1)
            GLOBAL_CACHE.ShMem.SendMessage(
                local_email,
                email,
                SharedCommandType.InventoryQuery,
                (float(model_id), float(model_id), 0.0, 0.0),
                ("report_inventory_count",),
            )
            pending[email] = {
                "email": email,
                "key": key,
                "section": section,
            }

        for key in account_keys:
            _scythe_drops.setdefault(key, 0)

        state["started"] = True
        state["local_email"] = local_email
        state["account_keys"] = account_keys
        state["pending"] = pending
        state["request_started_at"] = time.monotonic() if pending else 0.0
        state["local_email_wait_started_at"] = 0.0
        return True

    def _finish() -> None:
        if _tracking_disabled():
            return

        if not after_chest:
            _save_statistics()
            return

        total_scythes = 0
        for key in state["account_keys"]:
            account_key = str(key)
            before = _settings.get_int(
                _SCYTHE_SNAPSHOT_SECTION,
                account_key,
                -1,
            )
            after = _settings.get_int(
                _SCYTHE_RUN_SECTION,
                account_key,
                -1,
            )
            delta = (
                max(0, after - before)
                if before >= 0 and after >= 0
                else 0
            )
            _accumulate_drop(
                account_key,
                delta,
                _scythe_drops,
                _session_scythe,
            )
            total_scythes += delta

        _save_statistics()
        PySystem.Console.Log(
            MODULE_NAME,
            f"[Statistics] Final chest recorded - Insectoid Scythes {total_scythes}",
            PySystem.Console.MessageType.Success,
        )

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if bool(node.blackboard.get("USER_INTERRUPT_ACTIVE", False)):
                _reset()
                return BehaviorTree.NodeState.FAILURE

            if _tracking_disabled():
                _reset()
                return BehaviorTree.NodeState.SUCCESS

            if not bool(state["started"]):
                if not _start():
                    now = time.monotonic()
                    wait_started = float(
                        state["local_email_wait_started_at"] or 0.0
                    )
                    if wait_started <= 0.0:
                        state["local_email_wait_started_at"] = now
                        return BehaviorTree.NodeState.RUNNING
                    if (
                        (now - wait_started) * 1000.0
                        < _INVENTORY_QUERY_TIMEOUT_MS
                    ):
                        return BehaviorTree.NodeState.RUNNING

                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            "[Statistics] Local account email was unavailable; "
                            "skipping this statistics snapshot."
                        ),
                        PySystem.Console.MessageType.Warning,
                    )
                    _reset()
                    return BehaviorTree.NodeState.SUCCESS

            pending: dict[str, dict[str, object]] = state["pending"]
            model_id = int(INSECTOID_SCYTHE_MODEL_ID)

            for email in list(pending):
                request = pending[email]
                count = int(get_inventory_count(email, model_id, model_id))
                if count < 0:
                    continue

                _settings.set(
                    str(request["section"]),
                    str(request["key"]),
                    count,
                )
                pending.pop(email, None)

            if pending:
                elapsed_ms = (
                    time.monotonic() - float(state["request_started_at"] or 0.0)
                ) * 1000.0
                if elapsed_ms < _INVENTORY_QUERY_TIMEOUT_MS:
                    return BehaviorTree.NodeState.RUNNING

                for email, request in list(pending.items()):
                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            "[Statistics] Insectoid Scythe inventory query timed "
                            f"out on {_account_label(str(request['key']))}."
                        ),
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


def _shared_inventory_model_counts(account: object) -> dict[int, int] | None:
    """Return per-ModelID counts from the shared-memory inventory mirror."""
    inventory_bags = getattr(account, "InventoryBags", None)
    if inventory_bags is None:
        return None

    try:
        bags = list(inventory_bags.iter_bags())
    except Exception:
        return None

    if not bags:
        return None

    counts: dict[int, int] = {}
    saw_slots_container = False
    try:
        for bag in bags:
            bag_id = int(getattr(bag, "BagID", 0) or 0)
            if bag_id not in INVENTORY_BAG_IDS:
                continue

            slots = getattr(bag, "Slots", None)
            if slots is None:
                continue

            saw_slots_container = True
            for slot in slots:
                model_id = int(getattr(slot, "ModelID", 0) or 0)
                quantity = max(0, int(getattr(slot, "Quantity", 0) or 0))
                if model_id > 0 and quantity > 0:
                    counts[model_id] = counts.get(model_id, 0) + quantity
    except Exception:
        return None

    return counts if saw_slots_container else None


def _chest_model_discovery_node(*, after_chest: bool) -> BehaviorTree:
    """Log ModelIDs newly added by Arachni's Spoils.

    This is a temporary safe discovery path while INSECTOID_SCYTHE_MODEL_ID is
    unresolved. It never guesses or changes the tracked ModelID automatically.
    """
    def _capture() -> None:
        global _chest_model_snapshot, _last_chest_model_deltas

        current: dict[str, dict[int, int]] = {}
        for account in _shared_accounts():
            email = str(getattr(account, "AccountEmail", "") or "").strip()
            if not email:
                continue
            counts = _shared_inventory_model_counts(account)
            if counts is not None:
                current[_account_key(email)] = counts

        if not after_chest:
            _chest_model_snapshot = current
            _last_chest_model_deltas = {}
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "[Statistics] Chest ModelID discovery snapshot captured for "
                    f"{len(current)} account(s)."
                ),
                PySystem.Console.MessageType.Info,
            )
            return

        deltas: dict[str, dict[int, int]] = {}
        for key, after_counts in current.items():
            before_counts = _chest_model_snapshot.get(key, {})
            positive: dict[int, int] = {}
            for model_id, after_qty in after_counts.items():
                delta = int(after_qty) - int(before_counts.get(model_id, 0))
                if delta > 0:
                    positive[int(model_id)] = delta
            if positive:
                deltas[key] = positive

        _last_chest_model_deltas = deltas

        if not deltas:
            PySystem.Console.Log(
                MODULE_NAME,
                "[Statistics] Chest discovery found no positive inventory ModelID delta.",
                PySystem.Console.MessageType.Info,
            )
            return

        for key, model_deltas in sorted(deltas.items()):
            details = ", ".join(
                f"{model_id} x{quantity}"
                for model_id, quantity in sorted(model_deltas.items())
            )
            PySystem.Console.Log(
                MODULE_NAME,
                f"[Statistics] Chest ModelIDs - {_account_label(key)}: {details}",
                PySystem.Console.MessageType.Success,
            )

    return _statistics_action_node(
        (
            "Discover Arachni Chest ModelIDs After Open"
            if after_chest
            else "Snapshot Arachni Chest ModelIDs Before Open"
        ),
        _capture,
    )


def _reset_total_overview_and_timings() -> None:
    global _total_runs, _total_run_time, _fastest_run, _slowest_run
    global _l1_total_time, _l1_fastest, _l1_slowest
    global _l2_total_time, _l2_fastest, _l2_slowest
    global _current_run_time, _current_l1_time, _current_l2_time

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

    _current_run_time = 0.0
    _current_l1_time = 0.0
    _current_l2_time = 0.0

    keys = set(_scythe_drops) | set(_settings.items(_SCYTHE_DROPS_SECTION).keys())
    for key in keys:
        if key == "local":
            continue
        _scythe_drops[key] = 0
        _settings.set(_SCYTHE_DROPS_SECTION, key, 0)

    _save_statistics()
    PySystem.Console.Log(
        MODULE_NAME,
        "[Statistics] Total Overview and Run Timings reset to zero.",
        PySystem.Console.MessageType.Success,
    )


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
        return (
            f"{drops / runs * 100.0:.1f}%"
            if runs > 0 and drops > 0
            else "-"
        )

    table_flags = (
        PyImGui.TableFlags.Borders
        | PyImGui.TableFlags.RowBg
        | PyImGui.TableFlags.SizingFixedFit
        | PyImGui.TableFlags.NoHostExtendX
    )
    header_color = 26 | (38 << 8) | (51 << 16) | (255 << 24)
    column_width = 82.0
    row_height = 22.0

    def _header_row(labels: tuple[str, ...]) -> None:
        PyImGui.table_next_row(0, row_height)
        PyImGui.table_set_bg_color(2, header_color, -1)
        for index, label in enumerate(labels):
            PyImGui.table_set_column_index(index)
            PyImGui.text(label)

    PyImGui.text_colored("Arachni's Haunt Statistics", gold)
    PyImGui.separator()
    PyImGui.spacing()

    _scramble_accounts = PyImGui.checkbox(
        "Hide Account Names",
        _scramble_accounts,
    )

    if int(INSECTOID_SCYTHE_MODEL_ID) <= 0:
        PyImGui.text_colored(
            "Insectoid Scythe tracking: waiting for verified ModelID",
            gold,
        )
        PyImGui.text_wrapped(
            "The bot will not guess the ID. Chest ModelID discovery is active "
            "and logs every positive inventory ModelID delta after Arachni's Spoils."
        )
        if _last_chest_model_deltas:
            PyImGui.spacing()
            PyImGui.text_colored("Last chest ModelID deltas", cyan)
            for key, model_deltas in sorted(_last_chest_model_deltas.items()):
                details = ", ".join(
                    f"{model_id} x{quantity}"
                    for model_id, quantity in sorted(model_deltas.items())
                )
                PyImGui.text_wrapped(f"{_account_label(key)}: {details}")
        PyImGui.spacing()

    session_scythes = sum(_session_scythe.values())
    total_scythes = sum(_scythe_drops.values())

    PyImGui.text_colored("Session Overview", cyan)
    if PyImGui.begin_table("##arachni_bt_session", 3, table_flags):
        for label in ("Runs", "Scythes", "Drop Rate"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                column_width,
            )
        _header_row(("Runs", "Scythes", "Drop Rate"))
        values = (
            _session_runs,
            session_scythes,
            _drop_rate(_session_runs, session_scythes),
        )
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Total Overview", cyan)
    if PyImGui.begin_table("##arachni_bt_all_time", 3, table_flags):
        for label in ("Runs", "Scythes", "Drop Rate"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                column_width,
            )
        _header_row(("Runs", "Scythes", "Drop Rate"))
        values = (
            _total_runs,
            total_scythes,
            _drop_rate(_total_runs, total_scythes),
        )
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored("Run Timings", cyan)
    if PyImGui.begin_table("##arachni_bt_timings", 5, table_flags):
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
        l2_active = _t_l2_start > 0.0

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
        PyImGui.text_colored(
            "Reset all-time totals and timing history?",
            gold,
        )
        if PyImGui.button("Confirm Reset##arachni_stats"):
            _reset_total_overview_and_timings()
            _statistics_reset_pending = False
        PyImGui.same_line(0.0, 8.0)
        if PyImGui.button("Cancel##arachni_stats"):
            _statistics_reset_pending = False

    PyImGui.spacing()
    PyImGui.text_colored("Insectoid Scythe Drops", cyan)
    if PyImGui.begin_table("##arachni_bt_scythe_drops", 4, table_flags):
        PyImGui.table_setup_column(
            "Account",
            PyImGui.TableColumnFlags.WidthStretch,
        )
        for label in ("Session", "All Time", "Drop Rate"):
            PyImGui.table_setup_column(
                label,
                PyImGui.TableColumnFlags.WidthFixed,
                column_width,
            )
        _header_row(("Account", "Session", "All Time", "Drop Rate"))

        keys = sorted(set(_session_scythe) | set(_scythe_drops))
        session_total = 0
        all_time_total = 0

        for key in keys:
            session_count = _session_scythe.get(key, 0)
            all_time_count = _scythe_drops.get(key, 0)
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
        PyImGui.text_colored(
            _drop_rate(_total_runs, all_time_total),
            gold,
        )
        PyImGui.end_table()


# =============================================================================
# Inventory maintenance - Shards flow adapted to Rata Sum
# =============================================================================

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
        request_id = f"arachni_inventory_state_{int(time.monotonic() * 1000)}"
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

        request_id = f"arachni_inventory_{attempt_key}_{int(time.monotonic() * 1000)}"
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
    """Run one MerchantRules attempt while staying in Rata Sum.

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
                    f"{INVENTORY_MAINTENANCE_RETRY_COUNT} in Rata Sum."
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
                            _ensure_all_accounts_in_rata_sum("inventory_maintenance_setup"),
                            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
                            BT.Selector(
                                name="Retry Inventory Maintenance In Rata Sum",
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


def _travel_all_accounts_to_rata_sum(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(
        name="Travel Every Account To Rata Sum",
        children=[
            BTShared.SendAndWait(
                command=SharedCommandType.TravelToMap,
                params=(
                    float(RATA_SUM),
                    float(INVENTORY_TRAVEL_REGION),
                    float(INVENTORY_TRAVEL_DISTRICT),
                    float(INVENTORY_TRAVEL_LANGUAGE),
                ),
                include_self=True,
                refs_blackboard_key=f"{attempt_key}_travel_rata_refs",
                timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
                poll_interval_ms=250,
                log=True,
            ),
            _wait_for_all_accounts_on_inventory_instance(
                RATA_SUM,
                name="Wait For Every Account In Rata Sum EU-English-1",
            ),
        ],
    )


def _ensure_all_accounts_in_rata_sum(attempt_key: str) -> BehaviorTree:
    return BT.Selector(
        name="Ensure Every Account Is In Rata Sum",
        children=[
            _all_accounts_on_map_node(
                RATA_SUM,
                "Every Account Already In Rata Sum",
            ),
            _travel_all_accounts_to_rata_sum(attempt_key),
        ],
    )


def StartupInventoryCheck() -> BehaviorTree:
    return BT.Selector(
        name="Startup Inventory Check",
        children=[
            BT.Sequence(
                name="Check Inventories Before Leaving Rata Sum",
                children=[
                    BT.IsCurrentMap(
                        map_id=RATA_SUM,
                        log=False,
                    ),
                    InventoryCheckAndMaintenance(),
                ],
            ),
            BT.Succeeder(
                "Skip Startup Inventory Check Outside Rata Sum"
            ),
        ],
    )



# =============================================================================
# Active multibox accounts / PCons
# =============================================================================

def _pcon_account_map_tuple(
    account: object,
) -> tuple[int, int, int, int]:
    map_obj = getattr(
        getattr(account, "AgentData", None),
        "Map",
        None,
    )
    return (
        int(
            getattr(account, "MapID", 0)
            or getattr(map_obj, "MapID", 0)
            or 0
        ),
        int(
            getattr(account, "MapRegion", 0)
            or getattr(map_obj, "Region", 0)
            or 0
        ),
        int(
            getattr(account, "MapDistrict", 0)
            or getattr(map_obj, "District", 0)
            or 0
        ),
        int(
            getattr(account, "MapLanguage", 0)
            or getattr(map_obj, "Language", 0)
            or 0
        ),
    )


def _pcon_account_party_id(account: object) -> int:
    return int(
        getattr(
            getattr(account, "AgentPartyData", None),
            "PartyID",
            0,
        )
        or 0
    )


def _active_party_emails() -> list[str]:
    local_email = str(
        Player.GetAccountEmail() or ""
    ).strip()

    if not local_email:
        return []

    try:
        local_account = (
            GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(
                local_email
            )
        )
    except Exception:
        local_account = None

    try:
        accounts = list(
            GLOBAL_CACHE.ShMem.GetAllAccountData(
                sort_results=False
            )
            or []
        )
    except TypeError:
        accounts = list(
            GLOBAL_CACHE.ShMem.GetAllAccountData()
            or []
        )
    except Exception:
        accounts = []

    local_party_id = (
        _pcon_account_party_id(local_account)
        if local_account is not None
        else 0
    )
    local_map = (
        _pcon_account_map_tuple(local_account)
        if local_account is not None
        else None
    )

    result: list[str] = []
    seen: set[str] = set()

    for account in accounts:
        email = str(
            getattr(account, "AccountEmail", "")
            or ""
        ).strip()

        if not email or email in seen:
            continue

        if bool(getattr(account, "IsHero", False)):
            continue
        if bool(getattr(account, "IsNPC", False)):
            continue

        account_party_id = _pcon_account_party_id(
            account
        )
        account_map = _pcon_account_map_tuple(account)

        same_party = (
            local_party_id > 0
            and account_party_id == local_party_id
        )
        same_map_fallback = (
            local_party_id <= 0
            and local_map is not None
            and account_map == local_map
        )

        if not same_party and not same_map_fallback:
            continue

        seen.add(email)
        result.append(email)

    if local_email not in seen:
        result.append(local_email)

    return result


def _pcon_effect_name(model_id: int) -> str:
    model_id = int(model_id)

    overrides = {
        int(ModelID.Blue_Rock_Candy.value):
            "Blue_Rock_Candy_Rush",
        int(ModelID.Green_Rock_Candy.value):
            "Green_Rock_Candy_Rush",
        int(ModelID.Red_Rock_Candy.value):
            "Red_Rock_Candy_Rush",
        int(ModelID.Birthday_Cupcake.value):
            "Birthday_Cupcake_skill",
        int(ModelID.Bowl_Of_Skalefin_Soup.value):
            "Skale_Vigor",
        int(ModelID.Candy_Apple.value):
            "Candy_Apple_skill",
        int(ModelID.Candy_Corn.value):
            "Candy_Corn_skill",
        int(ModelID.Drake_Kabob.value):
            "Drake_Skin",
        int(ModelID.Golden_Egg.value):
            "Golden_Egg_skill",
        int(ModelID.Pahnai_Salad.value):
            "Pahnai_Salad_item_effect",
        int(ModelID.Slice_Of_Pumpkin_Pie.value):
            "Pie_Induced_Ecstasy",
        int(ModelID.War_Supplies.value):
            "Well_Supplied",
    }

    if model_id in overrides:
        return overrides[model_id]

    return str(
        CONSUMABLE_MODELID_TO_EFFECT_NAME.get(
            model_id,
            "",
        )
        or ""
    )


def _tick_direct_pcon_upkeep() -> None:
    global _pcon_direct_index
    global _pcon_direct_last_dispatch_ms

    if (
        botting_tree is None
        or not botting_tree.IsStarted()
        or not _runtime_consumables_enabled
        or not _activate_pcons
    ):
        return

    try:
        if (
            not Map.IsMapReady()
            or not Map.IsExplorable()
            or int(Map.GetMapID() or 0)
            not in (
                ARACHNI_LEVEL_1,
                ARACHNI_LEVEL_2,
            )
        ):
            return
    except Exception:
        return

    if not PCON_UPKEEPS:
        return

    now_ms = int(time.monotonic() * 1000.0)

    if (
        now_ms - int(_pcon_direct_last_dispatch_ms)
        < _PCON_DIRECT_DISPATCH_INTERVAL_MS
    ):
        return

    _pcon_direct_last_dispatch_ms = now_ms

    recipients = _active_party_emails()
    if not recipients:
        return

    model_id = int(
        PCON_UPKEEPS[
            _pcon_direct_index % len(PCON_UPKEEPS)
        ]
    )
    _pcon_direct_index = (
        _pcon_direct_index + 1
    ) % len(PCON_UPKEEPS)

    sender_email = str(
        Player.GetAccountEmail() or ""
    ).strip()
    if not sender_email:
        return

    effect_name = _pcon_effect_name(model_id)
    effect_id = (
        int(GLOBAL_CACHE.Skill.GetID(effect_name) or 0)
        if effect_name
        else 0
    )

    # Persistent PCons. Morale items are still accepted by Messaging.PCon;
    # effect_id 0 lets the remote handler apply its item-specific logic.
    params = (
        int(model_id),
        int(effect_id),
        0,
        0,
    )

    for receiver_email in recipients:
        if not receiver_email:
            continue

        if receiver_email == sender_email:
            try:
                local_agent_id = int(
                    Player.GetAgentID() or 0
                )
                has_effect = bool(
                    effect_id > 0
                    and local_agent_id > 0
                    and GLOBAL_CACHE.Effects.HasEffect(
                        local_agent_id,
                        effect_id,
                    )
                )
                if (
                    not has_effect
                    and GLOBAL_CACHE.Inventory.GetModelCount(
                        model_id
                    )
                    > 0
                ):
                    item_id = int(
                        GLOBAL_CACHE.Item.GetItemIdFromModelID(
                            model_id
                        )
                        or 0
                    )
                    if item_id > 0:
                        GLOBAL_CACHE.Inventory.UseItem(item_id)
            except Exception:
                pass
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


# =============================================================================
# Summoning stones
# =============================================================================

def _consumables_allowed() -> bool:
    return (
        _runtime_consumables_enabled
        and Map.IsMapReady()
        and not Map.IsMapLoading()
        and int(Map.GetMapID() or 0)
        in (
            ARACHNI_LEVEL_1,
            ARACHNI_LEVEL_2,
        )
    )


def UseAvailableSummoningStone() -> BehaviorTree:
    def _dispatch(
        _node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        if (
            not _use_summoning_stone
            or not _consumables_allowed()
        ):
            return BehaviorTree.NodeState.SUCCESS

        sender_email = str(
            Player.GetAccountEmail() or ""
        ).strip()
        recipients = _active_party_emails()

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
            name="Use Summoning Stone In Arachni",
            action_fn=_dispatch,
            aftercast_ms=0,
        )
    )


def SummoningStoneRecoveryService() -> BehaviorTree:
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
        state["map_id"] = map_id
        state["saw_active_summon"] = False
        state["recovering"] = False
        state["targets"] = []
        state["target_index"] = 0
        state["next_attempt_ms"] = 0.0

    def _tick(
        _node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        if (
            not _use_summoning_stone
            or not _consumables_allowed()
        ):
            return BehaviorTree.NodeState.RUNNING

        map_id = int(Map.GetMapID() or 0)

        if map_id != int(state["map_id"]):
            _reset_for_map(map_id)

        try:
            if Routines.Checks.Party.IsPartyWiped():
                return BehaviorTree.NodeState.RUNNING
        except Exception:
            pass

        try:
            active_summon = bool(
                has_active_party_summon(
                    GLOBAL_CACHE.Party.GetOthers()
                )
            )
        except Exception:
            active_summon = False

        if active_summon:
            state["saw_active_summon"] = True
            state["recovering"] = False
            state["targets"] = []
            state["target_index"] = 0
            return BehaviorTree.NodeState.RUNNING

        if not bool(state["saw_active_summon"]):
            return BehaviorTree.NodeState.RUNNING

        now_ms = time.monotonic() * 1000.0

        if now_ms < float(state["next_attempt_ms"]):
            return BehaviorTree.NodeState.RUNNING

        sender_email = str(
            Player.GetAccountEmail() or ""
        ).strip()
        if not sender_email:
            return BehaviorTree.NodeState.RUNNING

        if not bool(state["recovering"]):
            state["targets"] = _active_party_emails()
            state["target_index"] = 0
            state["recovering"] = True

        targets = list(state["targets"])
        index = int(state["target_index"])

        if index >= len(targets):
            state["recovering"] = False
            state["targets"] = []
            state["target_index"] = 0
            state["next_attempt_ms"] = (
                now_ms + RETRY_CYCLE_DELAY_MS
            )
            return BehaviorTree.NodeState.RUNNING

        receiver_email = str(targets[index])
        state["target_index"] = index + 1
        state["next_attempt_ms"] = (
            now_ms + ATTEMPT_INTERVAL_MS
        )

        try:
            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email,
                receiver_email,
                SharedCommandType.UseSummoningStone,
                (0.0, 0.0, 0.0, 0.0),
                ("", "", "", ""),
            )
        except Exception:
            pass

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Arachni Summoning Stone Recovery",
            action_fn=_tick,
            aftercast_ms=500,
        )
    )


# =============================================================================
# Asura Flame Staff handling
# =============================================================================

def _is_holding_bundle() -> bool:
    try:
        return bool(
            Agent.IsHoldingItem(
                Player.GetAgentID()
            )
        )
    except Exception:
        return False


def _is_core_shrine_resume(
    node: BehaviorTree.Node,
) -> bool:
    return (
        str(
            node.blackboard.get(
                "planner_restart_reason",
                "",
            )
            or ""
        )
        == "shrine"
    )


def _resolve_staff_combat_policy() -> bool:
    global _drop_staff_for_combat

    if _drop_staff_for_combat is not None:
        return _drop_staff_for_combat

    player_id = int(Player.GetAgentID() or 0)
    weapon_name = "Unknown"

    try:
        _, weapon_name = Agent.GetWeaponType(
            player_id
        )
    except Exception:
        weapon_name = "Unknown"

    try:
        is_martial = bool(
            Agent.IsMartial(player_id)
        )
    except Exception:
        is_martial = False

    try:
        is_caster = bool(
            Agent.IsCaster(player_id)
        )
    except Exception:
        is_caster = False

    if is_martial:
        _drop_staff_for_combat = True
        reason = (
            f"martial weapon detected: {weapon_name}"
        )
    elif is_caster:
        _drop_staff_for_combat = False
        reason = (
            f"caster weapon detected: {weapon_name}"
        )
    else:
        try:
            primary_profession, _ = (
                Agent.GetProfessionNames(player_id)
            )
        except Exception:
            primary_profession = ""

        if (
            primary_profession
            in _MARTIAL_PRIMARY_PROFESSIONS
        ):
            _drop_staff_for_combat = True
            reason = (
                "martial primary profession detected: "
                f"{primary_profession}"
            )
        elif primary_profession:
            _drop_staff_for_combat = False
            reason = (
                "caster primary profession detected: "
                f"{primary_profession}"
            )
        else:
            _drop_staff_for_combat = True
            reason = (
                "unknown weapon/profession; safe drop"
            )

    PySystem.Console.Log(
        MODULE_NAME,
        (
            "Asura Flame Staff combat policy: "
            f"{'DROP' if _drop_staff_for_combat else 'KEEP'} "
            f"({reason})."
        ),
        PySystem.Console.MessageType.Info,
    )

    return _drop_staff_for_combat


def ResolveStaffCombatPolicy() -> BehaviorTree:
    def _resolve(
        _node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        _resolve_staff_combat_policy()
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Resolve Flame Staff Combat Policy",
            action_fn=_resolve,
            aftercast_ms=0,
        )
    )


def ResetStaffCombatPolicy() -> BehaviorTree:
    def _reset(
        _node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        global _drop_staff_for_combat
        global _last_staff_drop_position
        global _shrine_recovery_staff_skip_active

        _drop_staff_for_combat = None
        _last_staff_drop_position = None
        _shrine_recovery_staff_skip_active = False

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Reset Flame Staff Combat Policy",
            action_fn=_reset,
            aftercast_ms=0,
        )
    )


def _bundle_released_check(
    name: str,
) -> BehaviorTree:
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
    children: list[BehaviorTree] = [
        _bundle_released_check(
            f"{name} - Already Released"
        )
    ]

    for attempt in range(
        1,
        max(1, int(attempts)) + 1,
    ):
        children.append(
            BT.Sequence(
                name=f"{name} - Attempt {attempt}",
                children=[
                    BT.DropBundle(log=log),
                    BT.Wait(
                        250
                        + ((attempt - 1) * 150)
                    ),
                    _bundle_released_check(
                        f"{name} - Verify {attempt}"
                    ),
                ],
            )
        )

    return BT.Selector(
        name=name,
        children=children,
    )


def DropStaffForCombat(
    log: bool = False,
) -> BehaviorTree:
    def _build(
        _node: BehaviorTree.Node,
    ) -> BehaviorTree:
        global _last_staff_drop_position

        if not _resolve_staff_combat_policy():
            return BT.Succeeder(
                "Keep Flame Staff For Caster Combat"
            )

        if not _is_holding_bundle():
            return BT.Succeeder(
                "No Flame Staff Bundle To Drop"
            )

        try:
            x, y = Player.GetXY()
            _last_staff_drop_position = (
                float(x),
                float(y),
            )

            if log:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        "Flame Staff combat drop recorded "
                        f"at ({float(x):.0f}, {float(y):.0f})."
                    ),
                    PySystem.Console.MessageType.Info,
                )
        except Exception:
            _last_staff_drop_position = None

        return _verified_drop_bundle(
            "Drop Flame Staff For Combat",
            log=log,
        )

    return BT.Subtree(
        name="Drop Flame Staff For Combat If Required",
        subtree_fn=_build,
    )


def ForceDropStaff(
    log: bool = True,
) -> BehaviorTree:
    def _build(
        _node: BehaviorTree.Node,
    ) -> BehaviorTree:
        global _last_staff_drop_position

        _last_staff_drop_position = None

        if not _is_holding_bundle():
            return BT.Succeeder(
                "No Flame Staff Bundle To Force Drop"
            )

        return _verified_drop_bundle(
            "Force Drop Flame Staff",
            log=log,
        )

    return BT.Subtree(
        name="Force Drop Flame Staff",
        subtree_fn=_build,
    )


def _enemy_in_staff_combat_range(
    radius: float = Range.Spirit.value,
) -> bool:
    try:
        player_id = int(Player.GetAgentID() or 0)

        if player_id <= 0:
            return False

        px, py = Agent.GetXY(player_id)
        radius_sq = float(radius) ** 2

        for candidate in (
            AgentArray.GetEnemyArray()
            or []
        ):
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

            if (
                dx * dx + dy * dy
                <= radius_sq
            ):
                return True

        return False
    except Exception:
        return False


def _staff_aware_combat_node(
    name: str,
    combat_factory: Callable[
        [],
        BehaviorTree,
    ],
    *,
    trigger_radius: float = Range.Spirit.value,
) -> BehaviorTree:
    combat_tree = combat_factory()
    drop_tree: BehaviorTree | None = None

    def _tick(
        node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        nonlocal combat_tree, drop_tree

        should_drop = (
            _resolve_staff_combat_policy()
            and _is_holding_bundle()
            and _enemy_in_staff_combat_range(
                trigger_radius
            )
        )

        if should_drop:
            if drop_tree is None:
                drop_tree = DropStaffForCombat(
                    log=True
                )

            drop_tree.blackboard = node.blackboard

            result = BehaviorTree.Node._normalize_state(
                drop_tree.tick()
            )

            if (
                result
                == BehaviorTree.NodeState.RUNNING
            ):
                return result

            if (
                result
                == BehaviorTree.NodeState.FAILURE
            ):
                drop_tree = None
                return result

            drop_tree = None

        combat_tree.blackboard = node.blackboard

        result = BehaviorTree.Node._normalize_state(
            combat_tree.tick()
        )

        if (
            result
            != BehaviorTree.NodeState.RUNNING
        ):
            combat_tree = combat_factory()
            drop_tree = None

        return result

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"{name} - Staff Aware",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def StaffAwareVanquish(
    points: Sequence[PathPoint],
    name: str,
    *,
    clear_area_radius: float = Range.Spirit.value,
    pause_on_combat: bool | None = None,
    move_tolerance: float = 500.0,
) -> BehaviorTree:
    def _create() -> BehaviorTree:
        return BT.VanquishNode(
            list(points),
            name=name,
            clear_area_radius=clear_area_radius,
            pause_on_combat=pause_on_combat,
            flag_heroes_to_waypoint=False,
            move_tolerance=move_tolerance,
            log=False,
        )

    return _staff_aware_combat_node(
        name,
        _create,
    )


def StaffAwareMoveAndKill(
    pos: PathPoint,
    name: str,
    *,
    clear_area_radius: float = Range.Spirit.value,
) -> BehaviorTree:
    def _create() -> BehaviorTree:
        return BT.MoveAndKill(
            pos,
            clear_area_radius=clear_area_radius,
            log=False,
        )

    return _staff_aware_combat_node(
        name,
        _create,
    )


def _find_ground_staff() -> int | None:
    try:
        local_player_id = int(
            Player.GetAgentID() or 0
        )

        if local_player_id <= 0:
            return 0

        px, py = Agent.GetXY(local_player_id)

        search_radius = 7500.0
        search_radius_sq = (
            search_radius * search_radius
        )

        for candidate in (
            AgentArray.GetItemArray()
            or []
        ):
            agent_id = int(candidate or 0)

            if (
                agent_id <= 0
                or not Agent.GetItemAgentByID(
                    agent_id
                )
            ):
                continue

            owner_id = int(
                Agent.GetItemAgentOwnerID(
                    agent_id
                )
                or 0
            )

            if owner_id not in (
                0,
                local_player_id,
            ):
                continue

            item_id = int(
                Agent.GetItemAgentItemID(
                    agent_id
                )
                or 0
            )

            if item_id <= 0:
                continue

            model_id = int(
                GLOBAL_CACHE.Item.GetModelID(
                    item_id
                )
                or 0
            )

            if (
                model_id
                not in ASURA_FLAME_STAFF_MODEL_IDS
            ):
                continue

            x, y = Agent.GetXY(agent_id)
            dx = float(x) - float(px)
            dy = float(y) - float(py)

            if (
                dx * dx + dy * dy
                <= search_radius_sq
            ):
                return agent_id

        return 0
    except Exception:
        return None


def PickupFlameStaff(
    *,
    allow_shrine_skip: bool = True,
) -> BehaviorTree:
    PICKUP_TIMEOUT_MS = 45_000
    SHRINE_PICKUP_TIMEOUT_MS = 5_000
    PICKUP_SEARCH_RADIUS = 7500.0
    DROP_RETRACE_TOLERANCE = 500.0

    def _create_pickup_tree() -> BehaviorTree:
        return BT.PickupGroundItemByModelID(
            model_ids=ASURA_FLAME_STAFF_MODEL_IDS,
            max_distance=PICKUP_SEARCH_RADIUS,
            timeout_ms=PICKUP_TIMEOUT_MS,
            allow_unassigned=True,
            interaction_interval_ms=1_000,
            aftercast_ms=100,
            log=False,
        )

    pickup_tree = _create_pickup_tree()
    return_to_drop_tree: BehaviorTree | None = None

    state = {
        "started_at": 0.0,
        "search_logged": False,
        "retrace_logged": False,
    }

    def _reset() -> None:
        nonlocal pickup_tree
        nonlocal return_to_drop_tree

        pickup_tree = _create_pickup_tree()
        return_to_drop_tree = None

        state["started_at"] = 0.0
        state["search_logged"] = False
        state["retrace_logged"] = False

    def _tick(
        node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        nonlocal pickup_tree
        nonlocal return_to_drop_tree
        global _last_staff_drop_position
        global _shrine_recovery_staff_skip_active

        now = time.monotonic()

        if _is_core_shrine_resume(node):
            _shrine_recovery_staff_skip_active = True

        if _is_holding_bundle():
            _shrine_recovery_staff_skip_active = False
            _last_staff_drop_position = None
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        if float(state["started_at"]) <= 0.0:
            state["started_at"] = now

        if not bool(state["search_logged"]):
            PySystem.Console.Log(
                MODULE_NAME,
                "Looking for the required Asura Flame Staff...",
                PySystem.Console.MessageType.Info,
            )
            state["search_logged"] = True

        elapsed_ms = int(
            (
                now
                - float(state["started_at"])
            )
            * 1000.0
        )

        if (
            allow_shrine_skip
            and _shrine_recovery_staff_skip_active
            and elapsed_ms
            >= SHRINE_PICKUP_TIMEOUT_MS
        ):
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    "Flame Staff was not recovered after shrine recovery; "
                    "continuing route retrace."
                ),
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        if elapsed_ms >= PICKUP_TIMEOUT_MS:
            PySystem.Console.Log(
                MODULE_NAME,
                "Failed to recover the required Asura Flame Staff.",
                PySystem.Console.MessageType.Error,
            )
            _reset()
            return BehaviorTree.NodeState.FAILURE

        ground_staff = _find_ground_staff()

        if (
            ground_staff == 0
            and _last_staff_drop_position
            is not None
        ):
            if return_to_drop_tree is None:
                drop_x, drop_y = (
                    _last_staff_drop_position
                )

                return_to_drop_tree = BT.Move(
                    Vec2f(
                        float(drop_x),
                        float(drop_y),
                    ),
                    tolerance=DROP_RETRACE_TOLERANCE,
                    pause_on_combat=False,
                    log=False,
                )

                if not bool(
                    state["retrace_logged"]
                ):
                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            "Staff not found nearby; returning to "
                            f"drop point ({drop_x:.0f}, {drop_y:.0f})."
                        ),
                        PySystem.Console.MessageType.Warning,
                    )
                    state["retrace_logged"] = True

            return_to_drop_tree.blackboard = (
                node.blackboard
            )

            move_result = (
                BehaviorTree.Node._normalize_state(
                    return_to_drop_tree.tick()
                )
            )

            if (
                move_result
                == BehaviorTree.NodeState.RUNNING
            ):
                return move_result

            if (
                move_result
                == BehaviorTree.NodeState.FAILURE
            ):
                return_to_drop_tree = None
                _last_staff_drop_position = None
                return BehaviorTree.NodeState.RUNNING

            return_to_drop_tree = None
            pickup_tree = _create_pickup_tree()
            pickup_tree.blackboard = node.blackboard
            return BehaviorTree.NodeState.RUNNING

        if ground_staff == 0:
            return BehaviorTree.NodeState.RUNNING

        return_to_drop_tree = None
        pickup_tree.blackboard = node.blackboard

        pickup_result = (
            BehaviorTree.Node._normalize_state(
                pickup_tree.tick()
            )
        )

        if (
            pickup_result
            == BehaviorTree.NodeState.RUNNING
        ):
            return pickup_result

        if (
            pickup_result
            == BehaviorTree.NodeState.SUCCESS
            and _is_holding_bundle()
        ):
            _last_staff_drop_position = None
            _shrine_recovery_staff_skip_active = False
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        pickup_tree = _create_pickup_tree()
        pickup_tree.blackboard = node.blackboard

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Pickup Required Asura Flame Staff",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


# =============================================================================
# Spider Egg mechanics / named NPC waits
# =============================================================================

def WaitUntilNoNearbyEnemies(
    *,
    radius: float = Range.Compass.value,
    clear_for_ms: int = 2_000,
    timeout_ms: int = 120_000,
) -> BehaviorTree:
    """Wait until no living enemy remains nearby for a stable period.

    The stable-clear window prevents a delayed egg-room spawn from being
    mistaken for the end of combat immediately after re-enabling CombatTree.
    """
    state = {
        "started_at": 0.0,
        "clear_since": 0.0,
    }

    def _reset() -> None:
        state["started_at"] = 0.0
        state["clear_since"] = 0.0

    def _tick(
        node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        now = time.monotonic()

        if bool(
            node.blackboard.get(
                "USER_INTERRUPT_ACTIVE",
                False,
            )
        ):
            _reset()
            return BehaviorTree.NodeState.FAILURE

        if float(state["started_at"]) <= 0.0:
            state["started_at"] = now

        elapsed_ms = int(
            (now - float(state["started_at"]))
            * 1000.0
        )

        if elapsed_ms >= max(0, int(timeout_ms)):
            PySystem.Console.Log(
                MODULE_NAME,
                "Timed out waiting for egg-room combat to finish.",
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.FAILURE

        if _enemy_in_staff_combat_range(
            float(radius)
        ):
            state["clear_since"] = 0.0
            return BehaviorTree.NodeState.RUNNING

        if float(state["clear_since"]) <= 0.0:
            state["clear_since"] = now
            return BehaviorTree.NodeState.RUNNING

        clear_elapsed_ms = int(
            (now - float(state["clear_since"]))
            * 1000.0
        )

        if clear_elapsed_ms < max(0, int(clear_for_ms)):
            return BehaviorTree.NodeState.RUNNING

        _reset()
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Wait Until Egg Combat Is Clear",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def BurnSpiderEggs(
    name: str,
    points: Sequence[PathPoint],
    *,
    force_drop_after: bool = False,
    pickup_after: bool = False,
) -> BehaviorTree:
    children: list[BehaviorTree] = [
        PickupFlameStaff(
            allow_shrine_skip=False
        ),
        BottingTree.DisableCombatTree(),
    ]

    for index, point in enumerate(
        points,
        start=1,
    ):
        x = float(point[0])
        y = float(point[1])

        # Level 2 Spider Eggs have been probed and use exact gadget IDs.
        # Level 1 can still use coordinate-only entries until those IDs are
        # captured; in that case the nearest gadget at the supplied position
        # is used as before.
        gadget_id = (
            int(point[2])
            if len(point) >= 3
            else None
        )

        children.append(
            BT.MoveAndInteractWithGadget(
                pos=Vec2f(x, y),
                gadget_id=gadget_id,
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

    if force_drop_after:
        children.append(
            ForceDropStaff(log=True)
        )

    children.append(
        BottingTree.EnableCombatTree()
    )

    # When the egg mechanic explicitly drops the staff, do not recover it
    # until the spawned combat has genuinely finished.  Requiring a stable
    # enemy-free window also protects against slightly delayed spawns.
    if force_drop_after:
        children.append(
            WaitUntilNoNearbyEnemies(
                radius=Range.Compass.value,
                clear_for_ms=2_000,
                timeout_ms=120_000,
            )
        )

    if pickup_after:
        children.append(
            PickupFlameStaff(
                allow_shrine_skip=False
            )
        )

    return BT.Sequence(
        name=name,
        children=children,
    )


def WaitForNamedAgent(
    name: str,
    *,
    timeout_ms: int = 60_000,
) -> BehaviorTree:
    def _check(
        node: BehaviorTree.Node,
    ) -> BehaviorTree.NodeState:
        agent_id = int(
            Agent.GetAgentIDByName(name)
            or 0
        )

        if agent_id > 0:
            node.blackboard[
                f"arachni_named_agent_{name}"
            ] = agent_id
            return BehaviorTree.NodeState.SUCCESS

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name=f"Wait For {name}",
            condition_fn=_check,
            throttle_interval_ms=500,
            timeout_ms=timeout_ms,
        )
    )


# =============================================================================
# Planner helpers
# =============================================================================

def _map_guarded_point(
    name: str,
    map_id: int,
    child: BehaviorTree,
    skip_if_in_maps: Sequence[int] = (),
) -> BehaviorTree:
    branches: list[BehaviorTree] = [
        BT.Sequence(
            name=f"{name} - Active Map",
            children=[
                BT.IsCurrentMap(
                    map_id=map_id,
                    log=False,
                ),
                child,
            ],
        )
    ]

    for later_map_id in skip_if_in_maps:
        branches.append(
            BT.Sequence(
                name=(
                    f"{name} - Later Map "
                    f"{later_map_id}"
                ),
                children=[
                    BT.IsCurrentMap(
                        map_id=later_map_id,
                        log=False,
                    ),
                    BT.Succeeder(
                        f"{name}AlreadyPassed"
                    ),
                ],
            )
        )

    if len(branches) == 1:
        return branches[0]

    return BT.Selector(
        name=name,
        children=branches,
    )


def _vanquish_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[PathPoint],
    *,
    skip_if_in_maps: Sequence[int] = (),
) -> list[
    tuple[
        str,
        Callable[[], BehaviorTree],
    ]
]:
    steps = []

    for index, point in enumerate(
        points,
        start=1,
    ):
        name = (
            f"{prefix} - Point {index:02d}"
        )

        steps.append(
            (
                name,
                lambda point=point, name=name:
                    _map_guarded_point(
                        name=name,
                        map_id=map_id,
                        child=BT.VanquishNode(
                            [point],
                            name=name,
                            clear_area_radius=(
                                Range.Spirit.value
                            ),
                            pause_on_combat=None,
                            flag_heroes_to_waypoint=False,
                            move_tolerance=500.0,
                            log=False,
                        ),
                        skip_if_in_maps=(
                            skip_if_in_maps
                        ),
                    ),
            )
        )

    return steps


def _staff_vanquish_point_steps(
    prefix: str,
    map_id: int,
    points: Sequence[PathPoint],
    *,
    skip_if_in_maps: Sequence[int] = (),
) -> list[
    tuple[
        str,
        Callable[[], BehaviorTree],
    ]
]:
    steps = []

    for index, point in enumerate(
        points,
        start=1,
    ):
        name = (
            f"{prefix} - Point {index:02d}"
        )

        def _build(
            point: PathPoint = point,
            name: str = name,
        ) -> BehaviorTree:
            return _map_guarded_point(
                name=name,
                map_id=map_id,
                skip_if_in_maps=skip_if_in_maps,
                child=BT.Sequence(
                    name=f"{name} - Staff Managed",
                    children=[
                        StaffAwareVanquish(
                            [point],
                            name,
                        ),
                        PickupFlameStaff(),
                    ],
                ),
            )

        steps.append((name, _build))

    return steps


# =============================================================================
# Preparation / travel / quest
# =============================================================================

def PreparePartyAndSupplies() -> BehaviorTree:
    already_past_outpost = BT.Sequence(
        name="Skip Rata Preparation - Already Past Rata",
        children=[
            BT.Selector(
                name="Already In Magus Or Arachni",
                children=[
                    BT.IsCurrentMap(
                        MAGUS_STONES,
                        log=False,
                    ),
                    BT.IsCurrentMap(
                        ARACHNI_LEVEL_1,
                        log=False,
                    ),
                    BT.IsCurrentMap(
                        ARACHNI_LEVEL_2,
                        log=False,
                    ),
                ],
            ),
            BT.Succeeder(
                "ArachniPreparationAlreadyDone"
            ),
        ],
    )

    normal = BT.Sequence(
        name="Prepare Arachni Party From Rata Sum",
        map_id_or_name=RATA_SUM,
        random_travel=True,
        children=[
            # Inventory maintenance must complete before party formation.
            StartupInventoryCheck(),
            _dungeon_party.create_party_node(
                multibox_invite=True,
                timeout_ms=30_000,
                log=True,
            ),
            _runtime_difficulty_node(),
            _runtime_restock_node(),
            BT.LogMessage(
                message=(
                    "Arachni party formed and selected "
                    "settings applied."
                ),
                module_name=MODULE_NAME,
            ),
        ],
    )

    return BT.Selector(
        name="Prepare Party And Supplies",
        children=[
            already_past_outpost,
            normal,
        ],
    )


def TravelToMagusStones() -> BehaviorTree:
    skip = BT.Sequence(
        name="Skip Rata Exit",
        children=[
            BT.Selector(
                name="Already In Magus Or Arachni",
                children=[
                    BT.IsCurrentMap(
                        MAGUS_STONES,
                        log=False,
                    ),
                    BT.IsCurrentMap(
                        ARACHNI_LEVEL_1,
                        log=False,
                    ),
                    BT.IsCurrentMap(
                        ARACHNI_LEVEL_2,
                        log=False,
                    ),
                ],
            ),
            BT.Succeeder(
                "RataExitAlreadyDone"
            ),
        ],
    )

    normal = BT.Sequence(
        name="Rata Sum To Magus Stones",
        children=[
            BT.IsCurrentMap(
                RATA_SUM,
                log=True,
            ),
            BT.MoveAndExitMap(
                RATA_EXIT,
                target_map_id=MAGUS_STONES,
                timeout_ms=60_000,
                log=True,
            ),
            BT.WaitUntilOnExplorable(
                timeout_ms=30_000
            ),
            BT.Wait(2_000),
        ],
    )

    return BT.Selector(
        name="Travel To Magus Stones",
        children=[
            skip,
            normal,
        ],
    )


def TakeScrambledReinforcements() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Hixx Quest - Already In Dungeon",
        children=[
            BT.Selector(
                name="Already In Arachni",
                children=[
                    BT.IsCurrentMap(
                        ARACHNI_LEVEL_1,
                        log=False,
                    ),
                    BT.IsCurrentMap(
                        ARACHNI_LEVEL_2,
                        log=False,
                    ),
                ],
            ),
            BT.Succeeder(
                "ArachniQuestAlreadyHandled"
            ),
        ],
    )

    already_active = BT.Sequence(
        name="Scrambled Reinforcements Already Active",
        children=[
            BT.IsCurrentMap(
                MAGUS_STONES,
                log=False,
            ),
            BT.IsQuestState(
                quest_id=SCRAMBLED_REINFORCEMENTS_QUEST_ID,
                state="active",
                log=True,
            ),
            BT.Succeeder(
                "ContinueWithActiveArachniQuest"
            ),
        ],
    )

    take = BT.Sequence(
        name="Take Scrambled Reinforcements",
        children=[
            BT.IsCurrentMap(
                MAGUS_STONES,
                log=True,
            ),
            BT.MoveAndDialog(
                HIXX_QUEST_POSITION,
                HIXX_TAKE_DIALOG,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(
                SCRAMBLED_REINFORCEMENTS_QUEST_ID,
                timeout_ms=15_000,
            ),
        ],
    )

    return BT.Selector(
        name="Handle Scrambled Reinforcements",
        children=[
            already_inside,
            already_active,
            take,
        ],
    )


def EnterArachnisHaunt() -> BehaviorTree:
    skip = BT.Sequence(
        name="Skip Arachni Entry - Already Inside",
        children=[
            BT.Selector(
                name="Already In Arachni",
                children=[
                    BT.IsCurrentMap(
                        ARACHNI_LEVEL_1,
                        log=False,
                    ),
                    BT.IsCurrentMap(
                        ARACHNI_LEVEL_2,
                        log=False,
                    ),
                ],
            ),
            BT.Succeeder(
                "ArachniEntryAlreadyDone"
            ),
        ],
    )

    normal = BT.Sequence(
        name="Enter Arachni's Haunt",
        children=[
            BT.IsCurrentMap(
                MAGUS_STONES,
                log=True,
            ),
            BT.MoveAndExitMap(
                ARACHNI_ENTRANCE,
                target_map_id=ARACHNI_LEVEL_1,
                timeout_ms=60_000,
                log=True,
            ),
            BT.WaitUntilOnExplorable(
                timeout_ms=30_000
            ),
            BT.Wait(2_000),
        ],
    )

    return BT.Selector(
        name="Enter Arachni's Haunt Or Resume",
        children=[
            skip,
            normal,
        ],
    )

class _RetryWebPassageUntilReachedNode(BehaviorTree.Node):
    """Keep probing the far side until the player physically crosses the web.

    Normal pathfinding can try to route around a still-closed web.  As in the
    EotN barricade cross-check, the far-side coordinate is therefore used as a
    direct movement target and success is based only on the player's real XY.
    """

    def __init__(
        self,
        destination: Vec2f,
        *,
        name: str,
        tolerance: float = 180.0,
        retry_interval_ms: int = 6_000,
    ) -> None:
        super().__init__(
            name=name,
            node_type="RetryWebPassageUntilReached",
            node_category="movement",
        )
        self.destination = destination
        self.tolerance = max(1.0, float(tolerance))
        self.retry_interval_ms = max(500, int(retry_interval_ms))
        self.move = self._coerce_node(
            BT.MoveDirect(
                destination,
                pause_on_combat=False,
                log=True,
            )
        )
        self.attempt_started_at = 0.0

    def get_children(self) -> list[BehaviorTree.Node]:
        return [self.move]

    def reset(self) -> None:
        super().reset()
        self.move.reset()
        self.attempt_started_at = 0.0

    def _destination_reached(self) -> bool:
        x, y = Player.GetXY()
        dx = float(x) - float(self.destination.x)
        dy = float(y) - float(self.destination.y)
        return (
            dx * dx + dy * dy
            <= self.tolerance * self.tolerance
        )

    def _restart_move(self, now: float) -> None:
        self.move.reset()
        self.attempt_started_at = now

    def _tick_impl(self) -> BehaviorTree.NodeState:
        if self._destination_reached():
            return BehaviorTree.NodeState.SUCCESS

        if self.blackboard is not None:
            self.move.blackboard = self.blackboard

        now = time.monotonic()

        if self.attempt_started_at <= 0.0:
            self.attempt_started_at = now
        elif (
            (now - self.attempt_started_at) * 1000.0
            >= self.retry_interval_ms
        ):
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f"{self.name}: web passage not confirmed; "
                    "retrying direct crossing."
                ),
                PySystem.Console.MessageType.Warning,
            )
            self._restart_move(now)

        move_state = BehaviorTree.Node._normalize_state(
            self.move.tick()
        )

        if self._destination_reached():
            return BehaviorTree.NodeState.SUCCESS

        if move_state != BehaviorTree.NodeState.RUNNING:
            self._restart_move(now)

        return BehaviorTree.NodeState.RUNNING


def CrossWebWithFlameStaff(
    name: str,
    before_point: Vec2f,
    after_point: Vec2f,
    *,
    force_drop_after: bool = False,
) -> BehaviorTree:
    """Carry the staff to a web and verify the player really reaches its far side."""

    children: list[BehaviorTree] = [
        PickupFlameStaff(
            allow_shrine_skip=False
        ),
        BT.Move(
            before_point,
            pause_on_combat=False,
            tolerance=180.0,
            log=False,
        ),
        BehaviorTree(
            _RetryWebPassageUntilReachedNode(
                after_point,
                name=f"{name} - Cross And Verify",
                tolerance=180.0,
                retry_interval_ms=6_000,
            )
        ),
    ]

    if force_drop_after:
        children.append(
            ForceDropStaff(log=True)
        )

    return BT.Sequence(
        name=name,
        children=children,
    )



# =============================================================================
# Level 1 mechanics
# =============================================================================

def Level1Start() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 1 Start",
        map_id=ARACHNI_LEVEL_1,
        skip_if_in_maps=(ARACHNI_LEVEL_2,),
        child=BT.Sequence(
            name="Start Arachni Level 1",
            children=[
                ResetStaffCombatPolicy(),
                ResolveStaffCombatPolicy(),
                MarkRunStart(),
                UseAvailableSummoningStone(),
                BT.MoveAndDialog(Vec2f(17507.00, 18900.00), dialog_id=0x84, multi_account=True, log=True)
            ],
        ),
    )


def AcquireLevel1Staff() -> BehaviorTree:
    return _map_guarded_point(
        name="Acquire Level 1 Flame Staff",
        map_id=ARACHNI_LEVEL_1,
        skip_if_in_maps=(ARACHNI_LEVEL_2,),
        child=PickupFlameStaff(
            allow_shrine_skip=False
        ),
    )


def CrossLevel1Web1() -> BehaviorTree:
    return _map_guarded_point(
        name="Cross Level 1 Web 1",
        map_id=ARACHNI_LEVEL_1,
        skip_if_in_maps=(ARACHNI_LEVEL_2,),
        child=CrossWebWithFlameStaff(
            "Cross First Web With Flame Staff",
            L1_WEB_1_BEFORE,
            L1_WEB_1_AFTER,
        ),
    )


def CrossLevel1Web2() -> BehaviorTree:
    return _map_guarded_point(
        name="Cross Level 1 Web 2",
        map_id=ARACHNI_LEVEL_1,
        skip_if_in_maps=(ARACHNI_LEVEL_2,),
        child=CrossWebWithFlameStaff(
            "Cross Second Web With Flame Staff",
            L1_WEB_2_BEFORE,
            L1_WEB_2_AFTER,
        ),
    )


def BurnLevel1EggGroup1() -> BehaviorTree:
    return _map_guarded_point(
        name="Burn Level 1 Egg Group 1",
        map_id=ARACHNI_LEVEL_1,
        skip_if_in_maps=(ARACHNI_LEVEL_2,),
        child=BurnSpiderEggs(
            "Burn Level 1 Egg Group 1",
            L1_EGG_GROUP_1,
            force_drop_after=True,
            pickup_after=True,
        ),
    )


def BurnLevel1EggGroup2() -> BehaviorTree:
    return _map_guarded_point(
        name="Burn Level 1 Egg Group 2",
        map_id=ARACHNI_LEVEL_1,
        skip_if_in_maps=(ARACHNI_LEVEL_2,),
        child=BT.Sequence(
            name="Burn Level 1 Egg Group 2 And Recover Key",
            children=[
                BurnSpiderEggs(
                    "Burn Level 1 Egg Group 2",
                    L1_EGG_GROUP_2,
                    force_drop_after=True,
                    pickup_after=False,
                ),
                BT.AddModelToLootWhitelist(
                    DUNGEON_KEY_MODEL_ID
                ),
                BT.Wait(2_000),
                BT.LootItems(
                    distance=Range.SafeCompass.value,
                    timeout_ms=10_000,
                ),
                PickupFlameStaff(
                    allow_shrine_skip=False
                ),
            ],
        ),
    )


def CrossLevel1Web3AndDiscardStaff() -> BehaviorTree:
    return _map_guarded_point(
        name="Cross Level 1 Web 3 And Drop Staff",
        map_id=ARACHNI_LEVEL_1,
        skip_if_in_maps=(ARACHNI_LEVEL_2,),
        child=CrossWebWithFlameStaff(
            "Cross Third Web And Explicitly Drop Staff",
            L1_WEB_3_BEFORE,
            L1_WEB_3_AFTER,
            force_drop_after=True,
        ),
    )


def OpenLevel1DungeonLock() -> BehaviorTree:
    return _map_guarded_point(
        name="Open Level 1 Dungeon Lock",
        map_id=ARACHNI_LEVEL_1,
        skip_if_in_maps=(ARACHNI_LEVEL_2,),
        child=BT.MoveAndInteractWithGadget(
            pos=L1_DUNGEON_LOCK,
            gadget_id=None,
            search_distance=800.0,
            interaction_distance=Range.Nearby.value,
            interaction_count=2,
            interaction_interval_ms=750,
            timeout_ms=30_000,
            pause_on_combat=False,
            multi_account=False,
            include_self=True,
            log=True,
        ),
    )


def EnterLevel2() -> BehaviorTree:
    return BT.Sequence(
        name="Enter Arachni Level 2",
        children=[
            _map_guarded_point(
                name="Arachni Level 1 Exit",
                map_id=ARACHNI_LEVEL_1,
                skip_if_in_maps=(ARACHNI_LEVEL_2,),
                child=BT.MoveAndExitMap(
                    L1_EXIT_TO_LEVEL_2,
                    target_map_id=ARACHNI_LEVEL_2,
                    timeout_ms=60_000,
                    log=True,
                ),
            ),
            BT.WaitForMapLoad(
                map_id=ARACHNI_LEVEL_2,
                timeout_ms=60_000,
            ),
            MarkLevel2Start(),
            BT.Wait(2_000),
        ],
    )


# =============================================================================
# Level 2 mechanics
# =============================================================================

def Level2StartAndAcquireStaff() -> BehaviorTree:
    return _map_guarded_point(
        name="Level 2 Start And Staff",
        map_id=ARACHNI_LEVEL_2,
        child=BT.Sequence(
            name="Start Arachni Level 2",
            children=[
                UseAvailableSummoningStone(),
                BT.Move(
                    L2_STAFF_POSITION,
                    pause_on_combat=False,
                    tolerance=300.0,
                    log=False,
                ),
                PickupFlameStaff(
                    allow_shrine_skip=False
                ),
            ],
        ),
    )


def CrossLevel2Web1() -> BehaviorTree:
    return _map_guarded_point(
        name="Cross Level 2 Web 1",
        map_id=ARACHNI_LEVEL_2,
        child=CrossWebWithFlameStaff(
            "Cross Level 2 Web 1",
            L2_WEB_1_BEFORE,
            L2_WEB_1_AFTER,
        ),
    )


def CrossLevel2Web2() -> BehaviorTree:
    return _map_guarded_point(
        name="Cross Level 2 Web 2",
        map_id=ARACHNI_LEVEL_2,
        child=CrossWebWithFlameStaff(
            "Cross Level 2 Web 2",
            L2_WEB_2_BEFORE,
            L2_WEB_2_AFTER,
        ),
    )


def CrossLevel2Web3() -> BehaviorTree:
    return _map_guarded_point(
        name="Cross Level 2 Web 3",
        map_id=ARACHNI_LEVEL_2,
        child=CrossWebWithFlameStaff(
            "Cross Level 2 Web 3",
            L2_WEB_3_BEFORE,
            L2_WEB_3_AFTER,
        ),
    )


def BurnLevel2EggGroup1() -> BehaviorTree:
    return _map_guarded_point(
        name="Burn Level 2 Egg Group 1",
        map_id=ARACHNI_LEVEL_2,
        child=BurnSpiderEggs(
            "Burn Level 2 Egg Group 1",
            L2_EGG_GROUP_1,
            force_drop_after=True,
            pickup_after=True,
        ),
    )


def BurnLevel2EggGroup2() -> BehaviorTree:
    return _map_guarded_point(
        name="Burn Level 2 Egg Group 2",
        map_id=ARACHNI_LEVEL_2,
        child=BurnSpiderEggs(
            "Burn Level 2 Egg Group 2",
            L2_EGG_GROUP_2,
            force_drop_after=False,
            pickup_after=False,
        ),
    )


def ResolveArachniBossFight() -> BehaviorTree:
    return _map_guarded_point(
        name="Resolve Arachni Boss Fight",
        map_id=ARACHNI_LEVEL_2,
        child=BT.Sequence(
            name="Resolve Arachni And Final Matriarch",
            children=[
                BT.Wait(8_000),
                StaffAwareMoveAndKill(
                    L2_BOSS_STAGING,
                    "Arachni Final Boss Fight",
                    clear_area_radius=Range.Compass.value,
                ),
                PickupFlameStaff(),
                BT.WaitUntilOutOfCombat(
                    timeout_ms=120_000
                ),
                BT.Wait(3_000),
            ],
        ),
    )


def CollectHixxReward() -> BehaviorTree:
    return _map_guarded_point(
        name="Collect Hixx Reward",
        map_id=ARACHNI_LEVEL_2,
        child=BT.Sequence(
            name="Find Hixx And Collect Reward",
            children=[
                WaitForNamedAgent(
                    "Hixx",
                    timeout_ms=60_000,
                ),
                BT.TargetAgentByName(
                    agent_name="Hixx",
                    log=True,
                ),
                BT.InteractTargetAndSendDialog(
                    dialog_id=HIXX_REWARD_DIALOG,
                    multi_account=True,
                    log=True,
                ),
                BT.SendDialog(
                    dialog_id=HIXX_REWARD_DIALOG,
                    multi_account=True,
                    log=True,
                ),
                BT.WaitForQuestCleared(
                    SCRAMBLED_REINFORCEMENTS_QUEST_ID,
                    timeout_ms=15_000,
                ),
            ],
        ),
    )


def OpenFinalChest() -> BehaviorTree:
    return _map_guarded_point(
        name="Open Arachni Final Chest",
        map_id=ARACHNI_LEVEL_2,
        child=BT.Sequence(
            name="Open Arachni Spoils Multibox",
            children=[
                _inventory_statistics_node(after_chest=False),
                _chest_model_discovery_node(after_chest=False),
                BT.MoveAndInteractWithGadget(
                    pos=L2_FINAL_CHEST_POSITION,
                    gadget_id=None,
                    search_distance=800.0,
                    interaction_distance=Range.Nearby.value,
                    interaction_count=2,
                    interaction_interval_ms=1_000,
                    account_settle_ms=3_000,
                    timeout_ms=90_000,
                    pause_on_combat=False,
                    multi_account=True,
                    include_self=True,
                    log=True,
                    ignore_destination_npcs=False,
                    ignore_destination_gadgets=True,
                ),
                BT.Wait(5_000),
                RecordSuccessfulRun(),
                _inventory_statistics_node(after_chest=True),
                _chest_model_discovery_node(after_chest=True),
            ],
        ),
    )


def ReturnRetakeAndReenter() -> BehaviorTree:
    return BT.Sequence(
        name="Return To Magus And Prepare Next Arachni Run",
        children=[
            BT.LogMessage(
                message=(
                    "Waiting for the dungeon end countdown "
                    "and return to Magus Stones."
                ),
                module_name=MODULE_NAME,
            ),
            BT.WaitForMapLoad(
                map_id=MAGUS_STONES,
                timeout_ms=190_000,
            ),
            BT.WaitUntilOnExplorable(
                timeout_ms=30_000
            ),
            BT.Wait(2_000),
            BT.MoveAndDialog(
                HIXX_QUEST_POSITION,
                HIXX_TAKE_DIALOG,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForActiveQuest(
                SCRAMBLED_REINFORCEMENTS_QUEST_ID,
                timeout_ms=15_000,
            ),
            EnterArachnisHaunt(),
        ],
    )


# =============================================================================
# Bot initialization / execution
# =============================================================================

def _configure_botting_tree(
    tree: BottingTree,
) -> None:
    tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=_enabled_consumable_upkeeps(),
        enable_party_wipe_recovery=True,
        enable_nearest_shrine_recovery=True,
        heroai_state_logging=False,
    )
    tree.AddServiceTree(
        "SummoningStoneRecoveryService",
        SummoningStoneRecoveryService,
    )


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()

    return BT.Sequence(
        name="Initialize Arachni's Haunt BT",
        children=[
            ResetStaffCombatPolicy(),
            bot.Config.Aggressive(
                multi_account=True,
                auto_loot=True,
                resurrection_scroll=True,
                account_isolation=False,
            ),
            BT.SetPlayerStatus(
                PlayerStatus.Offline,
                log=True,
            ),
            BT.LogMessage(
                message=(
                    "Arachni's Haunt BT initialized."
                ),
                module_name=MODULE_NAME,
            ),
        ],
    )


def get_execution_steps() -> list[
    tuple[
        str,
        Callable[[], BehaviorTree],
    ]
]:
    return [
        ("Initialize Bot", InitializeBot),
        (
            "Prepare Party And Supplies",
            PreparePartyAndSupplies,
        ),
        (
            "Travel Rata Sum To Magus Stones",
            TravelToMagusStones,
        ),

        *_vanquish_point_steps(
            "Magus Route To Hixx",
            MAGUS_STONES,
            MAGUS_ROUTE_TO_HIXX,
            skip_if_in_maps=(
                ARACHNI_LEVEL_1,
                ARACHNI_LEVEL_2,
            ),
        ),

        (
            "Take Scrambled Reinforcements",
            TakeScrambledReinforcements,
        ),
        (
            "Enter Arachni's Haunt",
            EnterArachnisHaunt,
        ),

        ("Level 1 Start", Level1Start),

        *_vanquish_point_steps(
            "Level 1 Route To First Staff",
            ARACHNI_LEVEL_1,
            L1_ROUTE_TO_FIRST_STAFF,
            skip_if_in_maps=(ARACHNI_LEVEL_2,),
        ),

        (
            "Level 1 Acquire Flame Staff",
            AcquireLevel1Staff,
        ),
        (
            "Level 1 Cross Web 1",
            CrossLevel1Web1,
        ),

        *_staff_vanquish_point_steps(
            "Level 1 Route After Web 1",
            ARACHNI_LEVEL_1,
            L1_ROUTE_AFTER_WEB_1,
            skip_if_in_maps=(ARACHNI_LEVEL_2,),
        ),

        (
            "Level 1 Cross Web 2",
            CrossLevel1Web2,
        ),

        *_staff_vanquish_point_steps(
            "Level 1 Route To Egg Group 1",
            ARACHNI_LEVEL_1,
            L1_ROUTE_TO_EGG_GROUP_1,
            skip_if_in_maps=(ARACHNI_LEVEL_2,),
        ),

        (
            "Level 1 Burn Egg Group 1",
            BurnLevel1EggGroup1,
        ),

        *_staff_vanquish_point_steps(
            "Level 1 Route To Egg Group 2",
            ARACHNI_LEVEL_1,
            L1_ROUTE_TO_EGG_GROUP_2,
            skip_if_in_maps=(ARACHNI_LEVEL_2,),
        ),

        (
            "Level 1 Burn Egg Group 2",
            BurnLevel1EggGroup2,
        ),

        *_staff_vanquish_point_steps(
            "Level 1 Route To Web 3",
            ARACHNI_LEVEL_1,
            L1_ROUTE_TO_WEB_3,
            skip_if_in_maps=(ARACHNI_LEVEL_2,),
        ),

        (
            "Level 1 Cross Web 3 And Drop Staff",
            CrossLevel1Web3AndDiscardStaff,
        ),

        *_vanquish_point_steps(
            "Level 1 Route To Dungeon Lock",
            ARACHNI_LEVEL_1,
            L1_ROUTE_TO_LOCK,
            skip_if_in_maps=(ARACHNI_LEVEL_2,),
        ),

        (
            "Level 1 Open Dungeon Lock",
            OpenLevel1DungeonLock,
        ),
        (
            "Level 1 Enter Level 2",
            EnterLevel2,
        ),

        (
            "Level 2 Start And Acquire Staff",
            Level2StartAndAcquireStaff,
        ),

        *_staff_vanquish_point_steps(
            "Level 2 Route 1",
            ARACHNI_LEVEL_2,
            L2_ROUTE_1,
        ),

        (
            "Level 2 Cross Web 1",
            CrossLevel2Web1,
        ),

        *_staff_vanquish_point_steps(
            "Level 2 Route 2",
            ARACHNI_LEVEL_2,
            L2_ROUTE_2,
        ),

        (
            "Level 2 Cross Web 2",
            CrossLevel2Web2,
        ),

        *_staff_vanquish_point_steps(
            "Level 2 Route 3",
            ARACHNI_LEVEL_2,
            L2_ROUTE_3,
        ),

        (
            "Level 2 Cross Web 3",
            CrossLevel2Web3,
        ),

        *_staff_vanquish_point_steps(
            "Level 2 Route To Egg Room",
            ARACHNI_LEVEL_2,
            L2_ROUTE_TO_EGGS,
        ),

        (
            "Level 2 Burn Egg Group 1",
            BurnLevel2EggGroup1,
        ),
        (
            "Level 2 Burn Egg Group 2",
            BurnLevel2EggGroup2,
        ),
        (
            "Level 2 Resolve Arachni Boss",
            ResolveArachniBossFight,
        ),
        (
            "Level 2 Collect Hixx Reward",
            CollectHixxReward,
        ),
        (
            "Level 2 Open Final Chest",
            OpenFinalChest,
        ),
        (
            "Return / Retake / Re-enter",
            ReturnRetakeAndReenter,
        ),
    ]


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

    _sync_consumable_upkeeps()

    tree.tick()
    _tick_direct_pcon_upkeep()

    attach_botting_tree_support(tree)

    tree.UI.draw_window(icon_path=TEXTURE,
        main_child_dimensions=(550, 390),
        extra_tabs=[
            ("Statistics", _draw_statistics),
            ("Party", _dungeon_party.draw_tab),
            ("Config", _draw_run_config),
        ],
    )


if __name__ == "__main__":
    main()
