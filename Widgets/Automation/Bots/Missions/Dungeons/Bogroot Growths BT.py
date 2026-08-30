from __future__ import annotations

from collections.abc import Callable, Sequence
import os
import time
import math

import PySystem
import PyImGui
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.ImGui_src.types import Alignment
from Py4GWCoreLib.py4gwcorelib_src.Color import Color
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib import GLOBAL_CACHE, Agent, Map, Player, SharedCommandType, Inventory, ImGui
from Py4GWCoreLib.Listeners import Listeners
from Py4GWCoreLib.enums import CONSUMABLE_MODELID_TO_EFFECT_NAME
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
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Widgets.System.Messaging import get_inventory_count, reset_inventory_count, get_inventory_state, reset_inventory_state


PathPoint = Vec2f | tuple[float, float] | tuple[int, int]


# region Metadata

MODULE_NAME = "Frog Scepter BT"
INI_PATH = "Widgets/Automation/Bots/Missions/Dungeons/Frog Scepter BT"
INI_FILENAME = "Frog_Scepter_BT.ini"

TEXTURE = os.path.join(
    PySystem.Console.get_projects_path(),
    "Assets",
    "Textures",
    "Module_Icons",
    "Frog Scepter.png",
)
MODULE_ICON = "Assets\\Textures\\Module_Icons\\Frog Scepter.png"

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
_auto_loot = True
_inventory_maintenance_enabled = True
_inventory_min_free_slots = 5
_inventory_min_id_kits = 1
_inventory_min_salvage_kits = 2
_inventory_status_snapshot: dict[str, dict[str, object]] = {}
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
    global _auto_loot, _inventory_maintenance_enabled
    global _inventory_min_free_slots, _inventory_min_id_kits, _inventory_min_salvage_kits

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


def _consumables_allowed() -> bool:
    return (
        _runtime_consumables_enabled
        and Map.IsMapReady()
        and not Map.IsMapLoading()
        and Map.GetMapID() in (BOGROOT_LEVEL_1, BOGROOT_LEVEL_2)
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

    if not _bot_is_started() or not _runtime_consumables_enabled or not _activate_pcons:
        if _pcon_direct_runtime_logged or _pcon_direct_last_dispatch_ms:
            _reset_direct_pcon_runtime()
        return

    try:
        if not Map.IsMapReady() or not Map.IsExplorable():
            return
        if int(Map.GetMapID() or 0) not in (BOGROOT_LEVEL_1, BOGROOT_LEVEL_2):
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

def _configure_runtime_upkeeps(enabled: bool | None = None) -> None:
    global _runtime_consumables_enabled, _configured_consumable_upkeeps
    previous_runtime_enabled = _runtime_consumables_enabled
    if enabled is not None:
        _runtime_consumables_enabled = bool(enabled)
    if previous_runtime_enabled != _runtime_consumables_enabled:
        _reset_direct_pcon_runtime()
    if botting_tree is None:
        return
    enabled_consumables = _enabled_consumable_upkeeps()
    botting_tree.Config.ConfigureUpkeep(
        looting_enabled=_auto_loot,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=enabled_consumables,
        enable_party_wipe_recovery=True,
        heroai_state_logging=False,
    )
    _configured_consumable_upkeeps = enabled_consumables


def _sync_consumable_upkeeps() -> None:
    # Floor loading no longer tears down PCons; only conset services are synced.
    if _enabled_consumable_upkeeps() != _configured_consumable_upkeeps:
        _configure_runtime_upkeeps()


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


def UseAvailableSummoningStone(level_key: str) -> BehaviorTree:
    """Broadcast a best-effort summon request to every active account.

    This is deliberately fire-and-forget. A receiver may already have an active
    summon, have summoning sickness, or have no usable stone; none of those cases
    is allowed to block the dungeon planner.
    """

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
                # Optional consumable: failure on one account must not stall all.
                continue

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Use Summoning Stone {level_key} (Non Blocking)",
            action_fn=_dispatch,
            aftercast_ms=0,
        )
    )


def _draw_run_config() -> None:
    import PyImGui
    global _use_hard_mode, _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons, _use_summoning_stone, _auto_loot
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots, _inventory_min_id_kits, _inventory_min_salvage_kits

    _load_settings()
    changed = False
    upkeep_changed = False

    PyImGui.text("Frog Scepter Run Config")
    PyImGui.separator()

    toggles = (
        ("Hard Mode (HM)", "_use_hard_mode", False),
        ("Restock conset from storage", "_restock_conset", False),
        ("Activate / maintain conset", "_activate_conset", True),
        ("Restock pcons from storage", "_restock_pcons", False),
        ("Activate / maintain pcons", "_activate_pcons", True),
        ("Use summoning stones", "_use_summoning_stone", False),
    )
    for label, variable_name, affects_upkeep in toggles:
        old_value = bool(globals()[variable_name])
        new_value = PyImGui.checkbox(label, old_value)
        if new_value != old_value:
            globals()[variable_name] = new_value
            changed = True
            upkeep_changed = upkeep_changed or affects_upkeep

    PyImGui.separator()
    PyImGui.text("Loot")
    value = PyImGui.checkbox("Auto loot", _auto_loot)
    if value != _auto_loot:
        _auto_loot = value
        changed = True
        upkeep_changed = True

    PyImGui.separator()
    PyImGui.text("Inventory maintenance")
    value = PyImGui.checkbox("Run MerchantRules when inventory is low", _inventory_maintenance_enabled)
    if value != _inventory_maintenance_enabled:
        _inventory_maintenance_enabled = value
        changed = True
    if _inventory_maintenance_enabled:
        for label, variable_name in (
            ("Minimum free slots", "_inventory_min_free_slots"),
            ("Minimum Superior ID kits (0 = disabled)", "_inventory_min_id_kits"),
            ("Minimum Superior salvage kits (0 = disabled)", "_inventory_min_salvage_kits"),
        ):
            old_value = int(globals()[variable_name])
            new_value = max(0, int(PyImGui.input_int(label, old_value)))
            if new_value != old_value:
                globals()[variable_name] = new_value
                changed = True

    if changed:
        _save_settings()
    if upkeep_changed:
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
        request_id = f"bogroot_inventory_state_{int(time.monotonic() * 1000)}"
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


def _travel_all_accounts_to_gadds(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(
        name="Travel Every Account To Gadd's Encampment",
        children=[
            BTShared.SendAndWait(command=SharedCommandType.TravelToMap, params=(float(GADDS_ENCAMPMENT), float(INVENTORY_TRAVEL_REGION), float(INVENTORY_TRAVEL_DISTRICT), float(INVENTORY_TRAVEL_LANGUAGE)), include_self=True, refs_blackboard_key=f'{attempt_key}_travel_vlox_refs', timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS, poll_interval_ms=250, log=True),
            _wait_for_all_accounts_on_inventory_instance(GADDS_ENCAMPMENT, name="Wait For Every Account In Gadd's Encampment EU-English-1"),
        ],
    )


def _return_all_accounts_to_gadds(attempt_key: str) -> BehaviorTree:
    currently_in_an_explorable = BT.Selector(
        name="Current Map Can Be Resigned",
        children=[
            BT.IsCurrentMap(map_id=SPARKFLY_SWAMP, log=False),
            BT.IsCurrentMap(map_id=BOGROOT_LEVEL_1, log=False),
            BT.IsCurrentMap(map_id=BOGROOT_LEVEL_2, log=False),
        ],
    )

    resign_from_explorable = BT.Sequence(
        name="Resign Party To Gadd's Encampment",
        children=[
            currently_in_an_explorable,
            BT.Resign(wait_for_map_load=True, target_map_id=GADDS_ENCAMPMENT, multi_account=True, timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS, log=True),
            _wait_for_all_accounts_on_map(GADDS_ENCAMPMENT, name="Wait For Party Return To Gadd's Encampment"),
        ],
    )

    return BT.Selector(name="Ensure Every Account Is In Gadd's Encampment", children=[_all_accounts_on_map_node(GADDS_ENCAMPMENT, "Every Account Already In Gadd's Encampment"), resign_from_explorable, _travel_all_accounts_to_gadds(attempt_key)])


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

        request_id = f"bogroot_inventory_{attempt_key}_{int(time.monotonic() * 1000)}"
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
    """Run one MerchantRules attempt while staying in Gadd's Encampment.

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
                    f"{INVENTORY_MAINTENANCE_RETRY_COUNT} in Gadd's Encampment."
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
                            _return_all_accounts_to_gadds("inventory_maintenance_setup"),
                            BT.LeaveParty(),
                            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
                            BT.Selector(
                                name="Retry Inventory Maintenance In Gadd's Encampment",
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
            BT.Sequence(name="Check Inventories Before Leaving Gadd's Encampment", children=[BT.IsCurrentMap(map_id=GADDS_ENCAMPMENT, log=False), InventoryCheckAndMaintenance()]),
            BT.Succeeder("Skip Startup Inventory Check Outside Gadd's Encampment"),
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


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()
    return BT.Sequence(
        name="Initialize Frog Scepter BT",
        children=[
            bot.Config.Aggressive(
                multi_account=True,
                auto_loot=_auto_loot,
                resurrection_scroll=True,
                account_isolation=False,
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
            StartupInventoryCheck(),
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


def TravelToTekksStart() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Tekks Travel Start - Already In Bogroot",
        children=[
            BT.Selector(
                name="Check Bogroot Floor",
                children=[
                    BT.IsCurrentMap(map_id=BOGROOT_LEVEL_1, log=True),
                    BT.IsCurrentMap(map_id=BOGROOT_LEVEL_2, log=True),
                ],
            ),
            BT.Succeeder("Tekks Travel Start Already Done"),
        ],
    )

    normal = BT.Sequence(
        name="Start Travel From Gadd's Encampment To Tekks",
        children=[
            _runtime_consumable_node(False),
            BT.MoveAndExitMap(GADDS_EXIT, target_map_id=SPARKFLY_SWAMP, log=True),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.MoveAndDialog(
                SPARKFLY_BLESSING,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
        ],
    )

    return BT.Selector(
        name="Start Travel To Tekks",
        children=[already_inside, normal],
    )


def TravelToTekksFinish() -> BehaviorTree:
    name = "Finish Sparkfly Route To Tekks"
    return _map_guarded_point(
        name=name,
        map_id=SPARKFLY_SWAMP,
        child=BT.Sequence(
            name=name,
            children=[
                BT.WaitUntilOutOfCombat(timeout_ms=90_000),
                BT.Move(TEKKS_POSITION, pause_on_combat=False, log=False),
            ],
        ),
        skip_if_in_maps=(BOGROOT_LEVEL_1, BOGROOT_LEVEL_2),
    )

def HandleTekksQuest() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Skip Tekks Handler - Already In Level 1",
        children=[
            BT.IsCurrentMap(map_id=BOGROOT_LEVEL_1, log=True),
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="active", log=True),
            BT.Succeeder("TekksHandlerAlreadyDone"),
        ],
    )
    active = BT.Sequence(name="Tekks' War Already Active", children=[BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state='active', log=True), BT.Succeeder('ContinueWithActiveQuest')])
    completed = BT.Sequence(
        name="Collect And Retake Tekks' War",
        children=[
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="complete", log=True),
            BT.MoveAndDialog(TEKKS_POSITION, TEKKS_REWARD_DIALOG, pause_on_combat=False, multi_account=True, log=True),
            BT.WaitForQuestCleared(TEKKS_QUEST_ID, timeout_ms=15_000),
            BT.MoveAndDialog(TEKKS_POSITION, TEKKS_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=True),
            BT.WaitForActiveQuest(TEKKS_QUEST_ID, timeout_ms=15_000),
        ],
    )
    missing = BT.Sequence(
        name="Take Tekks' War",
        children=[
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="missing", log=True),
            BT.MoveAndDialog(TEKKS_POSITION, TEKKS_TAKE_DIALOG, pause_on_combat=False, multi_account=True, log=True),
            BT.WaitForActiveQuest(TEKKS_QUEST_ID, timeout_ms=15_000),
        ],
    )
    return BT.Selector(children=[already_inside, active, completed, missing], name="Handle Tekks Quest")


def EnterBogroot(enable_consumables_on_entry: bool = True) -> BehaviorTree:
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

    entry = BT.Selector(name="Enter Bogroot Growths", children=[already_inside, normal])

    if not enable_consumables_on_entry:
        return entry

    return BT.Sequence(
        name="Enter Bogroot Growths And Resume Consumables",
        children=[entry, _runtime_consumable_node(True)],
    )


# region Planner point steps


def _map_guarded_point(
    name: str,
    map_id: int,
    child: BehaviorTree,
    skip_if_in_maps: Sequence[int] = (),
) -> BehaviorTree:
    """Run one planner point on its expected map, or accept it if a later map is already loaded."""
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

    return BT.Selector(name=name, children=branches)


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
    """Expose every Vanquish path point as its own MultiAccountSequence planner step."""
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


# region Dungeon route actions


def Level1_Start() -> BehaviorTree:
    return BT.Sequence(
        name="Bogroot Level 1 - Start",
        children=[
            _mark_run_start_node(),
            _inventory_statistics_node(after_chest=False),
            BT.AddModelToLootWhitelist(BOSS_KEY_MODEL_ID),
            UseAvailableSummoningStone("l1"),
            BT.MoveAndDialog(
                L1_BLESSING,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
        ],
    )


def Level1_EnterLevel2() -> BehaviorTree:
    name = "Bogroot Level 1 - Enter Level 2"
    return BT.Sequence(
        name=name,
        children=[
            _map_guarded_point(
                name=name,
                map_id=BOGROOT_LEVEL_1,
                child=BT.MoveAndExitMap(
                    Vec2f(7731, -19298),
                    target_map_id=BOGROOT_LEVEL_2,
                ),
                skip_if_in_maps=(BOGROOT_LEVEL_2,),
            ),
            _mark_l2_start_node(),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
        ],
    )


def Level2_Start() -> BehaviorTree:
    return BT.Sequence(
        name="Bogroot Level 2 - Start",
        children=[
            BT.AddModelToLootWhitelist(BOSS_KEY_MODEL_ID),
            UseAvailableSummoningStone("l2"),
            BT.MoveAndDialog(
                L2_ENTRY_BLESSING,
                dialog_id=DWARVEN_BLESSING_DIALOG,
                multi_account=True,
                log=True,
            ),
        ],
    )


def Level2_Blessing2() -> BehaviorTree:
    return BT.MoveAndDialog(
        L2_BLESSING_2,
        dialog_id=DWARVEN_BLESSING_DIALOG,
        multi_account=True,
        log=True,
    )


def Level2_Blessing3() -> BehaviorTree:
    return BT.MoveAndDialog(
        L2_BLESSING_3,
        dialog_id=DWARVEN_BLESSING_DIALOG,
        multi_account=True,
        log=True,
    )


def Level2_OpenDoor() -> BehaviorTree:
    return BT.Sequence(
        name="Bogroot Level 2 - Open Boss Door",
        children=[
            BT.IsCurrentMap(map_id=BOGROOT_LEVEL_2, log=False),
            BT.MoveAndInteractWithGadget(
                pos=L2_DOOR,
                pause_on_combat=True,
                log=True,
            ),
        ],
    )


def Level2_Blessing4() -> BehaviorTree:
    return BT.MoveAndDialog(
        L2_BLESSING_4,
        dialog_id=DWARVEN_BLESSING_DIALOG,
        multi_account=True,
        log=True,
    )


def Level2_ZhimFight() -> BehaviorTree:
    return BT.WaitForClearEnemiesInArea(
        16017.74,
        -19040.79,
        radius=Range.Compass.value,
        allowed_alive_enemies=0,
        interact_interval_ms=750,
        stable_clear_ms=10_000,
        keep_player_near_center=False,
        center_tolerance=750.0,
        log=True,
    )


# endregion

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

def ExitBogrootLevel1ToSparkfly() -> BehaviorTree:
    """Leave Level 1 through the same entry-side portal used from Sparkfly.

    The reset entry starts at the Sparkfly-side spawn.  Rather than hard-code a
    portal coordinate, build an exit point dynamically by extending the vector
    from the first Deldrimor blessing back through the current spawn position.
    This keeps the reset tied to the actual entry spawn if the coordinate shifts.
    """

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        player_x, player_y = Player.GetXY()
        dx = float(player_x) - float(L1_BLESSING.x)
        dy = float(player_y) - float(L1_BLESSING.y)
        length = math.hypot(dx, dy)

        if length <= 1.0:
            return BT.Failer("Cannot Resolve Bogroot Entry Exit Direction")

        # Walk well beyond the spawn in the opposite direction from the first
        # blessing; MoveAndExitMap completes as soon as Sparkfly loads.
        extension = 2_500.0
        exit_point = Vec2f(
            float(player_x) + (dx / length) * extension,
            float(player_y) + (dy / length) * extension,
        )
        return BT.MoveAndExitMap(
            exit_point,
            target_map_id=SPARKFLY_SWAMP,
            log=False,
        )

    return BT.Subtree(
        name="Exit Bogroot Level 1 To Sparkfly",
        subtree_fn=_build,
    )


def CollectRewardAndReturnToSparkfly(end_countdown_timeout_ms: int = 190_000) -> BehaviorTree:
    """Try the inside Tekks reward, then wait for the automatic return to Sparkfly."""
    already_in_sparkfly = BT.Sequence(
        name="Skip Inside Tekks Reward - Already In Sparkfly Swamp",
        children=[
            BT.IsCurrentMap(map_id=SPARKFLY_SWAMP, log=True),
            BT.LogMessage(
                message=(
                    "The party is already in Sparkfly Swamp. Skipping the inside "
                    "Tekks search and resuming the restart preparation."
                ),
                module_name=MODULE_NAME,
            ),
            BT.Succeeder("InsideTekksRewardAlreadyReturnedToSparkfly"),
        ],
    )

    reward_collected_inside = BT.Sequence(
        name="Collect Tekks Reward Inside Dungeon",
        children=[
            # Do not gate the lookup behind IsQuestState('complete').  As in
            # Shards of Orr, the mirrored quest state can lag immediately after
            # the boss/chest.  Tekks presence + WaitForQuestCleared is the source
            # of truth for a successful inside reward.
            BT.IsCurrentMap(map_id=BOGROOT_LEVEL_2, log=True),
            BT.Move(Vec2f(14079.80, -17776.0), pause_on_combat=False, log=False),
            BT.LogMessage(
                message="Level 2 confirmed after Z'him. Looking for Tekks by name inside the dungeon.",
                module_name=MODULE_NAME,
            ),
            CollectTekksRewardInsideDungeon(),
            BT.WaitForQuestCleared(TEKKS_QUEST_ID, timeout_ms=15_000),
            BT.LogMessage(
                message="Tekks was found inside the dungeon and the Tekks' War reward was collected.",
                module_name=MODULE_NAME,
            ),
        ],
    )

    reward_not_collected_inside = BT.Sequence(
        name="Tekks Unavailable Inside Dungeon",
        children=[
            BT.LogMessage(
                message=(
                    "Tekks was not found inside the dungeon or the inside reward could not be "
                    "collected. The reward will be handled in Sparkfly Swamp."
                ),
                module_name=MODULE_NAME,
            ),
            BT.Succeeder("InsideTekksRewardUnavailable"),
        ],
    )

    return BT.Sequence(
        name="Collect Reward And Return To Sparkfly",
        children=[
            _runtime_consumable_node(False),
            BT.Selector(
                name="Resolve Inside Tekks Reward",
                children=[already_in_sparkfly, reward_collected_inside, reward_not_collected_inside],
            ),
            BT.LogMessage(
                message="Waiting for the end-of-dungeon countdown and the return to Sparkfly Swamp.",
                module_name=MODULE_NAME,
            ),
            BT.WaitForMapLoad(map_id=SPARKFLY_SWAMP, timeout_ms=end_countdown_timeout_ms),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.LogMessage(
                message="The party has returned to Sparkfly Swamp. Resolving Tekks' War for the next run.",
                module_name=MODULE_NAME,
            ),
            BT.Move(TEKKS_POSITION, pause_on_combat=False, log=False),
        ],
    )


def WaitForTekksInside(timeout_ms: int = 30_000) -> BehaviorTree:
    """Wait until Tekks is resolvable by name inside Bogroot Growths."""

    def _check(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        agent_id = Agent.GetAgentIDByName("Tekks")

        if agent_id != 0:
            node.blackboard["tekks_agent_id"] = agent_id
            return BehaviorTree.NodeState.SUCCESS

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name="Wait For Tekks Inside Dungeon",
            condition_fn=_check,
            throttle_interval_ms=500,
            timeout_ms=timeout_ms,
        )
    )


def CollectTekksRewardInsideDungeon() -> BehaviorTree:
    """Collect Tekks' War from Tekks at the final chest when he is present."""
    return BT.Sequence(
        name="Collect Tekks Reward Inside Dungeon",
        children=[
            WaitForTekksInside(timeout_ms=30_000),
            BT.TargetAgentByName(agent_name="Tekks", log=True),
            BT.LogMessage(
                message="Tekks was found near the final chest. Attempting to collect the Tekks' War reward.",
                module_name=MODULE_NAME,
            ),
            BT.InteractTargetAndSendDialog(
                dialog_id=TEKKS_REWARD_DIALOG,
                multi_account=True,
                log=True,
            ),
            BT.SendDialog(
                dialog_id=TEKKS_REWARD_DIALOG,
                multi_account=True,
                log=True,
            ),
            BT.WaitForQuestCleared(TEKKS_QUEST_ID, timeout_ms=15_000),
        ],
    )


def ResolveTekksQuestAfterRun() -> BehaviorTree:
    """Leave Sparkfly with Tekks' War active, mirroring the Shards restart flow."""

    direct_retake = BT.Sequence(
        name="Retake Tekks' War Directly",
        children=[
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

    retake_after_reset_entry = BT.Sequence(
        name="Reset Tekks By Entering Bogroot Level 1",
        children=[
            BT.LogMessage(
                message=(
                    "Tekks did not offer Tekks' War directly. Entering and leaving "
                    "Bogroot Level 1 once before retrying."
                ),
                module_name=MODULE_NAME,
            ),
            EnterBogroot(enable_consumables_on_entry=False),
            ExitBogrootLevel1ToSparkfly(),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.Move(TEKKS_POSITION, pause_on_combat=False, log=False),
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

    quest_already_active = BT.Sequence(
        name="Keep Active Tekks' War Quest",
        children=[
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="active", log=True),
            BT.LogMessage(
                message="Tekks' War is already active for the next run.",
                module_name=MODULE_NAME,
            ),
        ],
    )

    reward_collected_inside = BT.Sequence(
        name="Retake Tekks' War After Inside Reward",
        children=[
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="missing", log=True),
            BT.Selector(
                name="Retake Tekks' War With Reset Fallback",
                children=[
                    direct_retake,
                    BT.Sequence(
                        name="Retake Completed Despite Wait Failure",
                        children=[
                            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="active", log=True),
                            BT.Succeeder("TekksWarRetakeAlreadyCompleted"),
                        ],
                    ),
                    retake_after_reset_entry,
                ],
            ),
        ],
    )

    reward_not_collected_inside = BT.Sequence(
        name="Collect Outside Reward And Retake Tekks' War",
        children=[
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="complete", log=True),
            BT.LogMessage(
                message="The Tekks' War reward is still pending. Collecting it from Tekks in Sparkfly Swamp.",
                module_name=MODULE_NAME,
            ),
            BT.MoveAndDialog(
                TEKKS_POSITION,
                TEKKS_REWARD_DIALOG,
                pause_on_combat=False,
                multi_account=True,
                log=True,
            ),
            BT.WaitForQuestCleared(TEKKS_QUEST_ID, timeout_ms=15_000),
            BT.LogMessage(
                message="The Tekks' War reward was collected successfully in Sparkfly Swamp.",
                module_name=MODULE_NAME,
            ),

            # If the reward is collected only after the automatic return, Tekks
            # needs one zone reset before offering the repeatable quest again.
            EnterBogroot(enable_consumables_on_entry=False),
            ExitBogrootLevel1ToSparkfly(),
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            BT.Wait(2_000),
            BT.Move(TEKKS_POSITION, pause_on_combat=False, log=False),
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

    return BT.Sequence(
        name="Resolve Tekks Quest After Run",
        children=[
            BT.IsCurrentMap(map_id=SPARKFLY_SWAMP, log=True),
            BT.Selector(
                name="Resolve Tekks' War State In Sparkfly Swamp",
                children=[quest_already_active, reward_collected_inside, reward_not_collected_inside],
            ),
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="active", log=True),
        ],
    )


def PrepareNextBogrootRun() -> BehaviorTree:
    already_inside = BT.Sequence(
        name="Next Bogroot Run Already Entered",
        children=[
            BT.IsCurrentMap(map_id=BOGROOT_LEVEL_1, log=True),
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="active", log=True),
        ],
    )

    continue_from_sparkfly = BT.Sequence(
        name="Enter Next Bogroot Run From Sparkfly Swamp",
        children=[
            BT.IsCurrentMap(map_id=SPARKFLY_SWAMP, log=True),
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="active", log=True),
            EnterBogroot(),
        ],
    )

    continue_after_maintenance = BT.Sequence(
        name="Reform Party And Enter Next Bogroot Run From Gadd's Encampment",
        children=[
            BT.IsCurrentMap(map_id=GADDS_ENCAMPMENT, log=True),
            BT.IsQuestState(quest_id=TEKKS_QUEST_ID, state="active", log=True),
            BT.CreateParty(multibox_invite=True, timeout_ms=30_000, log=True),
            _runtime_difficulty_node(),
            _runtime_restock_node(),
            TravelToTekksStart(),
            BT.Move(SPARKFLY_TO_TEKKS, pause_on_combat=True, log=False),
            TravelToTekksFinish(),
            EnterBogroot(),
        ],
    )

    return BT.Selector(
        name="Prepare Next Bogroot Run",
        children=[already_inside, continue_from_sparkfly, continue_after_maintenance],
    )


# Backward-compatible wrapper for any external reference to the old step name.
def CollectTekksRewardAndRestart() -> BehaviorTree:
    return BT.Sequence(
        name="Collect Tekks Reward And Restart",
        children=[
            CollectRewardAndReturnToSparkfly(),
            ResolveTekksQuestAfterRun(),
            PrepareNextBogrootRun(),
        ],
    )

# endregion


# region Execution


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Initialize Bot", InitializeBot),
        ("Prepare Party And Supplies", PreparePartyAndSupplies),

        ("Travel To Tekks - Start", TravelToTekksStart),
        *_vanquish_point_steps(
            "Sparkfly Route To Tekks",
            SPARKFLY_SWAMP,
            SPARKFLY_TO_TEKKS,
            skip_if_in_maps=(BOGROOT_LEVEL_1, BOGROOT_LEVEL_2),
        ),
        ("Travel To Tekks - Finish", TravelToTekksFinish),
        ("Handle Tekks Quest", HandleTekksQuest),
        ("Enter Bogroot Growths", EnterBogroot),

        ("Level 1 Start", Level1_Start),
        *_vanquish_point_steps(
            "Level 1 Route 1",
            BOGROOT_LEVEL_1,
            L1_PATH_1,
            skip_if_in_maps=(BOGROOT_LEVEL_2,),
        ),
        *_vanquish_point_steps(
            "Level 1 Route 2",
            BOGROOT_LEVEL_1,
            L1_PATH_2,
            skip_if_in_maps=(BOGROOT_LEVEL_2,),
        ),
        *_vanquish_point_steps(
            "Level 1 Route 3",
            BOGROOT_LEVEL_1,
            L1_PATH_3,
            skip_if_in_maps=(BOGROOT_LEVEL_2,),
        ),
        ("Level 1 Enter Level 2", Level1_EnterLevel2),

        ("Level 2 Start", Level2_Start),
        *_vanquish_point_steps("Level 2 Route 1", BOGROOT_LEVEL_2, L2_PATH_1),
        ("Level 2 Blessing 2", Level2_Blessing2),
        *_vanquish_point_steps("Level 2 Route 2", BOGROOT_LEVEL_2, L2_PATH_2),
        ("Level 2 Blessing 3", Level2_Blessing3),
        *_vanquish_point_steps("Level 2 Route 3", BOGROOT_LEVEL_2, L2_PATH_3),
        ("Level 2 Open Boss Door", Level2_OpenDoor),
        *_vanquish_point_steps("Level 2 Route 4", BOGROOT_LEVEL_2, L2_PATH_4),
        ("Level 2 Blessing 4", Level2_Blessing4),
        *_vanquish_point_steps(
            "Route To Z'him",
            BOGROOT_LEVEL_2,
            FROGGY_BOSS_PATH,
        ),
        ("Z'him Fight", Level2_ZhimFight),

        ("Open Final Chest", OpenFinalChest),
        ("Collect Reward And Return To Sparkfly", CollectRewardAndReturnToSparkfly),
        ("Resolve Tekks Quest", ResolveTekksQuestAfterRun),
        ("Inventory Check And Maintenance", InventoryCheckAndMaintenance),
        ("Prepare Next Bogroot Run", PrepareNextBogrootRun),
    ]


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
        "A complete multibox BottingTree automation for Bogroot Growths / Frog Scepter farming. "
        "The run starts from Gadd's Encampment, handles Tekks' War and progresses through both "
        "dungeon levels before opening the final chest and preparing the next run."
    )
    PyImGui.spacing()

    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Automates Sparkfly Swamp and the complete Level 1 and Level 2 Bogroot route.")
    PyImGui.bullet_text("Handles Tekks' War, dungeon blessings, boss keys, doors, bosses and the final chest.")
    PyImGui.bullet_text("Uses point-by-point dungeon clearing while preserving the current step during party recovery.")
    PyImGui.bullet_text(
        "Supports multibox party control, configurable Hard Mode, consets, personal consumables "
        "and summoning stones with dungeon-only upkeep."
    )
    PyImGui.bullet_text(
        "Multibox inventory maintenance can trigger MerchantRules when an active account falls "
        "below the configured thresholds."
    )
    PyImGui.bullet_text("Tracks Level 1/Level 2 times plus Frog Scepter and Glacial Blades drops across accounts.")
    PyImGui.spacing()

    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Bogroot Growths / Frog Scepter BottingTree implementation: Sky.")
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
