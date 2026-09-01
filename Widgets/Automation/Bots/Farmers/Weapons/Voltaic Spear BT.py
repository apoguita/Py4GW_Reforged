from __future__ import annotations

import os
import time
import unicodedata
from collections.abc import Callable, Sequence
from typing import Protocol, cast
from Py4GWCoreLib.native_src.internals.types import Vec2f
import PySystem
import PyImGui
PathPoint = Vec2f | tuple[float, float] | tuple[int, int]
from Py4GWCoreLib import Agent, AgentArray, GLOBAL_CACHE, Inventory, Map, Player, SharedCommandType, ImGui
from Py4GWCoreLib.enums import CONSUMABLE_MODELID_TO_EFFECT_NAME
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.ImGui_src.types import Alignment
from Py4GWCoreLib.py4gwcorelib_src.Color import Color
from Py4GWCoreLib.Listeners import Listeners
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Model_enums import GadgetModelID
from Py4GWCoreLib.enums_src.Model_enums import ModelID, SpiritModelID
from Py4GWCoreLib.enums_src.Title_enums import TitleID
from Py4GWCoreLib.enums_src.Player_enums import PlayerStatus
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import CONSET_UPKEEPS
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import CONSUMABLE_UPKEEPS
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Widgets.System.Messaging import (
    get_inventory_count,
    get_inventory_state,
    reset_inventory_count,
    reset_inventory_state,
)

TEXTURE = os.path.join(
    PySystem.Console.get_projects_path(),
    "Assets",
    "Textures",
    "Module_Icons",
    "Voltaicspear.png",
)
MODULE_ICON = "Assets\\Textures\\Module_Icons\\Voltaicspear.png"

MODULE_NAME = 'Voltaic Spear BT'
INI_PATH = 'Widgets/Automation/Bots/Farmers/Weapons/Voltaic Spear BT'
INI_FILENAME = 'Voltaic_Spear_BT.ini'
_SPEAR_DROPS_SECTION = 'Voltaic Spear Drops'
_SPEAR_SNAPSHOT_SECTION = 'Voltaic Spear Snapshot'
_SPEAR_RUN_SECTION = 'Voltaic Spear Run'
_CHAR_NAMES_SECTION = 'Character Names'

# Maps copied from Voltaic.au3 / Reforged map enums.
UMBRAL_GROTTO = 639
VERDANT_CASCADES = 566
SLAVERS_EXILE = 577
JUSTICIAR_THOMMIS_ROOM = 620

THOMMIS_DIALOG = 0x84
AGGRO_RADIUS = Range.Spellcast.value + 200.0
_DUNGEON_PRIORITY_ROLE_TERMS = (
    ('Priest', ('priest', 'pretre')),
    ('Defender', ('defender', 'defenseur')),
)
_DUNGEON_SPIRIT_MODEL_IDS = frozenset(int(model.value) for model in SpiritModelID)


# Typed views of the existing Core interfaces; no runtime replacement.
class _DungeonClearNode(Protocol):
    blackboard: dict[str, object]


class _DungeonTargeting(Protocol):
    def ChangeTarget(self, agent_id: int) -> None: ...

    def CallTarget(self, agent_id: int) -> None: ...

    def Interact(self, agent_id: int, call_target: bool) -> None: ...


VOLTAIC_SPEAR_MODEL_ID = int(ModelID.Voltaic_Spear.value)
THOMMIS_CHEST_GADGET_ID = int(
    GadgetModelID.CHEST_DUNGEON_SLAVERS_EXILE_JUSTICIAR_THOMMIS_ROOM.value
)
SUMMONING_STONES = (30209, 37810, 31155)
PCON_UPKEEPS = tuple(
    int(model_id)
    for model_id in CONSUMABLE_UPKEEPS
    if int(model_id) not in CONSET_UPKEEPS
)
CONSET_RESTOCK_ITEMS = tuple(
    (int(model_id), 10) for model_id in CONSET_UPKEEPS
)
PCON_RESTOCK_ITEMS = tuple(
    (int(model_id), 10) for model_id in PCON_UPKEEPS
)
SUMMON_RESTOCK_ITEMS = tuple(
    (int(model_id), 10) for model_id in SUMMONING_STONES
)

INVENTORY_BAG_IDS = frozenset((1, 2, 3, 4))
ID_KIT_MODEL_IDS = (int(ModelID.Superior_Identification_Kit.value),)
SALVAGE_KIT_MODEL_IDS = (int(ModelID.Superior_Salvage_Kit.value),)
MERCHANT_RULES_WIDGET_NAME = 'MerchantRules'
INVENTORY_PLUS_WIDGET_NAME = 'InventoryPlus'

INVENTORY_TRAVEL_REGION = 2
INVENTORY_TRAVEL_DISTRICT = 1
INVENTORY_TRAVEL_LANGUAGE = 0
INVENTORY_MAINTENANCE_RETRY_COUNT = 2
INVENTORY_SNAPSHOT_SETTLE_MS = 2_000
INVENTORY_TRAVEL_TIMEOUT_MS = 60_000
INVENTORY_MERCHANT_TIMEOUT_MS = 240_000
_INVENTORY_QUERY_POLL_MS = 200
_INVENTORY_QUERY_TIMEOUT_MS = 10_000

# Exact route from Voltaic.au3.
UMBRAL_EXIT_PATH = [(-23200.0, 7100.0), (-22735.0, 6339.0)]

VERDANT_PATH = [
    (-19887.0, 6074.0),
    (-10273.0, 3251.0),
    (-6878.0, -329.0),
    (-3041.0, -3446.0),
    (3571.0, -9501.0),
    (10764.0, -6448.0),
    (13063.0, -4396.0),
    (18054.0, -3275.0),
    (20966.0, -6476.0),
    (25298.0, -9456.0),
]

SLAVERS_PORTAL = (25729.0, -9360.0)
THOMMIS_ENTRY_PATH = [(-16797.0, 9251.0), (-17835.0, 12524.0)]
THOMMIS_ROOM_PORTAL = (-18300.0, 12527.0)
THOMMIS_NPC = (-12135.0, -18210.0)

THOMMIS_PATH_1 = [
    (-13500.0, -15750.0),
    (-12500.0, -15000.0),
    (-10400.0, -14800.0),
    (-11500.0, -13300.0),
    (-13400.0, -11500.0),
    (-13700.0, -9550.0),
    (-14100.0, -8600.0),
    (-15000.0, -7500.0),
    (-16500.0, -8000.0),
    (-18800.0, -7850.0),
]

THOMMIS_PATH_2 = [
    (-18500.0, -11500.0),
    (-17700.0, -12500.0),
    (-17500.0, -14250.0),
]

CHEST_POSITION = (-17461.0, -14258.0)

_settings = Settings(f'{INI_PATH}/{INI_FILENAME}', 'global')
_settings_loaded = False

_hard_mode = True
_restock_conset = True
_use_conset = True
_restock_pcons = True
_use_pcons = True
_use_summoning_stone = True
_auto_loot = True
_inventory_maintenance_enabled = True
_inventory_min_free_slots = 5
_inventory_min_id_kits = 1
_inventory_min_salvage_kits = 2
_inventory_status_snapshot: dict[str, dict[str, object]] = {}
_runtime_consumables_enabled = False
_configured_consumable_upkeeps: tuple[int, ...] | None = None

# PCons are maintained by a direct multibox dispatcher. Consets stay on the
# generic BottingTree upkeep service. This avoids the generic PCon recipient
# resolver while preserving the existing Voltaic surface/Thommis lifecycle.
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

_total_runs = 0
_total_seconds = 0.0
_best_seconds = float('inf')
_worst_seconds = 0.0
_total_spears = 0
_split_runs = 0
_verdant_total_seconds = 0.0
_verdant_best_seconds = float('inf')
_verdant_worst_seconds = 0.0
_thommis_total_seconds = 0.0
_thommis_best_seconds = float('inf')
_thommis_worst_seconds = 0.0

_session_runs = 0
_session_spears = 0
_run_started_at = 0.0
_thommis_started_at = 0.0
_last_run_seconds = 0.0
_last_verdant_seconds = 0.0
_last_thommis_seconds = 0.0
_last_run_spears = 0
_statistics_reset_pending = False
_spear_drops: dict[str, int] = {}
_session_spear_drops: dict[str, int] = {}
_char_names: dict[str, str] = {}

initialized = False
botting_tree: BottingTree | None = None


def _load_settings() -> None:
    global _settings_loaded
    global _hard_mode, _restock_conset, _use_conset
    global _restock_pcons, _use_pcons, _use_summoning_stone, _auto_loot
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots, _inventory_min_id_kits
    global _inventory_min_salvage_kits
    global _total_runs, _total_seconds, _best_seconds, _worst_seconds, _total_spears
    global _split_runs, _verdant_total_seconds, _verdant_best_seconds, _verdant_worst_seconds
    global _thommis_total_seconds, _thommis_best_seconds, _thommis_worst_seconds

    if _settings_loaded:
        return

    _hard_mode = _settings.get_bool('Config', 'HardMode', True)
    _restock_conset = _settings.get_bool('Config', 'RestockConset', True)
    _use_conset = _settings.get_bool('Config', 'UseConset', True)
    _restock_pcons = _settings.get_bool('Config', 'RestockPcons', True)
    _use_pcons = _settings.get_bool('Config', 'UsePcons', True)
    _use_summoning_stone = _settings.get_bool('Config', 'UseSummoningStone', True)
    _auto_loot = _settings.get_bool('Config', 'AutoLoot', True)
    _inventory_maintenance_enabled = _settings.get_bool(
        'Config',
        'InventoryMaintenanceEnabled',
        True,
    )
    _inventory_min_free_slots = max(
        0,
        _settings.get_int('Config', 'InventoryMinFreeSlots', 5),
    )
    _inventory_min_id_kits = max(
        0,
        _settings.get_int('Config', 'InventoryMinIdKits', 1),
    )
    _inventory_min_salvage_kits = max(
        0,
        _settings.get_int('Config', 'InventoryMinSalvageKits', 2),
    )

    _total_runs = _settings.get_int('Statistics', 'TotalRuns', 0)
    _total_seconds = _settings.get_float('Statistics', 'TotalSeconds', 0.0)
    best = _settings.get_float('Statistics', 'BestSeconds', 0.0)
    _best_seconds = float('inf') if best <= 0.0 else best
    _worst_seconds = _settings.get_float('Statistics', 'WorstSeconds', 0.0)
    _total_spears = _settings.get_int('Statistics', 'TotalVoltaicSpears', 0)
    # Older runs have no split measurements; keep their totals without inventing splits.
    _split_runs = _settings.get_int('Statistics', 'SplitRuns', 0)
    _verdant_total_seconds = _settings.get_float('Statistics', 'VerdantTotalSeconds', 0.0)
    best = _settings.get_float('Statistics', 'VerdantBestSeconds', 0.0)
    _verdant_best_seconds = float('inf') if best <= 0.0 else best
    _verdant_worst_seconds = _settings.get_float('Statistics', 'VerdantWorstSeconds', 0.0)
    _thommis_total_seconds = _settings.get_float('Statistics', 'ThommisTotalSeconds', 0.0)
    best = _settings.get_float('Statistics', 'ThommisBestSeconds', 0.0)
    _thommis_best_seconds = float('inf') if best <= 0.0 else best
    _thommis_worst_seconds = _settings.get_float('Statistics', 'ThommisWorstSeconds', 0.0)

    for key in _settings.items(_SPEAR_DROPS_SECTION).keys():
        if key == 'local':
            continue
        _spear_drops[key] = _settings.get_int(
            _SPEAR_DROPS_SECTION,
            key,
            0,
        )

    for key in _settings.items(_CHAR_NAMES_SECTION).keys():
        if key == 'local':
            continue
        name = str(_settings.get_str(_CHAR_NAMES_SECTION, key, '') or '').strip()
        if name:
            _char_names[key] = name

    # Preserve an existing total created by the old local-only tracker.
    _total_spears = max(_total_spears, sum(_spear_drops.values()))
    _settings_loaded = True


def _save_config() -> None:
    _settings.set('Config', 'HardMode', _hard_mode)
    _settings.set('Config', 'RestockConset', _restock_conset)
    _settings.set('Config', 'UseConset', _use_conset)
    _settings.set('Config', 'RestockPcons', _restock_pcons)
    _settings.set('Config', 'UsePcons', _use_pcons)
    _settings.set('Config', 'UseSummoningStone', _use_summoning_stone)
    _settings.set('Config', 'AutoLoot', _auto_loot)
    _settings.set(
        'Config',
        'InventoryMaintenanceEnabled',
        _inventory_maintenance_enabled,
    )
    _settings.set(
        'Config',
        'InventoryMinFreeSlots',
        _inventory_min_free_slots,
    )
    _settings.set(
        'Config',
        'InventoryMinIdKits',
        _inventory_min_id_kits,
    )
    _settings.set(
        'Config',
        'InventoryMinSalvageKits',
        _inventory_min_salvage_kits,
    )


def _save_statistics() -> None:
    _settings.set('Statistics', 'TotalRuns', _total_runs)
    _settings.set('Statistics', 'TotalSeconds', _total_seconds)
    _settings.set(
        'Statistics',
        'BestSeconds',
        0.0 if _best_seconds == float('inf') else _best_seconds,
    )
    _settings.set('Statistics', 'WorstSeconds', _worst_seconds)
    _settings.set('Statistics', 'TotalVoltaicSpears', _total_spears)
    _settings.set('Statistics', 'SplitRuns', _split_runs)
    _settings.set('Statistics', 'VerdantTotalSeconds', _verdant_total_seconds)
    _settings.set(
        'Statistics', 'VerdantBestSeconds', 0.0 if _verdant_best_seconds == float('inf') else _verdant_best_seconds
    )
    _settings.set('Statistics', 'VerdantWorstSeconds', _verdant_worst_seconds)
    _settings.set('Statistics', 'ThommisTotalSeconds', _thommis_total_seconds)
    _settings.set(
        'Statistics', 'ThommisBestSeconds', 0.0 if _thommis_best_seconds == float('inf') else _thommis_best_seconds
    )
    _settings.set('Statistics', 'ThommisWorstSeconds', _thommis_worst_seconds)
    for key, total in _spear_drops.items():
        if key != 'local':
            _settings.set(_SPEAR_DROPS_SECTION, key, total)
    for key, name in _char_names.items():
        if key != 'local':
            _settings.set(_CHAR_NAMES_SECTION, key, name)


def _reset_statistics() -> None:
    """Clear recorded statistics while preserving an active run and its inventory baseline."""
    global _total_runs, _total_seconds, _best_seconds, _worst_seconds, _total_spears
    global _session_runs, _session_spears, _split_runs
    global _verdant_total_seconds, _verdant_best_seconds, _verdant_worst_seconds
    global _thommis_total_seconds, _thommis_best_seconds, _thommis_worst_seconds
    global _last_run_seconds, _last_verdant_seconds, _last_thommis_seconds, _last_run_spears
    global _statistics_reset_pending

    _total_runs = _session_runs = _split_runs = 0
    _total_spears = _session_spears = _last_run_spears = 0
    _total_seconds = _verdant_total_seconds = _thommis_total_seconds = 0.0
    _best_seconds = _verdant_best_seconds = _thommis_best_seconds = float('inf')
    _worst_seconds = _verdant_worst_seconds = _thommis_worst_seconds = 0.0
    _last_run_seconds = _last_verdant_seconds = _last_thommis_seconds = 0.0
    _spear_drops.clear()
    _session_spear_drops.clear()

    # Remove offline characters' saved counters too, so reload cannot restore them.
    # Keep configuration, character names and the in-flight inventory snapshots.
    _settings.delete_section('Statistics')
    _settings.delete_section(_SPEAR_DROPS_SECTION)
    _save_statistics()
    _statistics_reset_pending = False
    PySystem.Console.Log(
        MODULE_NAME,
        'Session and saved statistics reset. Any active run keeps its timing.',
        PySystem.Console.MessageType.Success,
    )


def _consumables_allowed() -> bool:
    return (
        _runtime_consumables_enabled
        and Map.IsMapReady()
        and not Map.IsMapLoading()
        and Map.GetMapID() == JUSTICIAR_THOMMIS_ROOM
    )


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    """Return generic BottingTree consumable services for the current phase.

    PCons are intentionally excluded here. They are maintained by
    _tick_direct_pcon_upkeep() using the real multibox accounts from SharedMemory.
    """
    if not _runtime_consumables_enabled:
        return ()

    enabled: list[int] = []
    if _use_conset:
        enabled.extend(int(model_id) for model_id in CONSET_UPKEEPS)
    return tuple(dict.fromkeys(enabled))


def _pcon_effect_name(model_id: int) -> str:
    """Resolve the persistent effect name associated with a PCon model."""
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
    """Resolve real player accounts in the Thommis-room multibox party."""
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

        # Voltaic has a hard contract: PCons may only be used in Thommis room.
        # A briefly lagging remote SharedMemory snapshot is skipped and will be
        # picked up on the next 650-ms pass rather than consuming during Verdant.
        if _pcon_account_map_tuple(account)[0] != JUSTICIAR_THOMMIS_ROOM:
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

    # The local account can be omitted from GetAllAccountData(). It is safe to
    # add it because _tick_direct_pcon_upkeep() already verifies Thommis room.
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
    """Use one party-wide morale PCon only while the party is below target."""
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

    # Only one remote is asked per pass so a party-wide morale item cannot be
    # consumed simultaneously by several clients before SharedMemory updates.
    receiver_email = remote_recipients[_pcon_direct_morale_remote_index % len(remote_recipients)]
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

    if not _bot_is_started() or not _runtime_consumables_enabled or not _use_pcons:
        if _pcon_direct_runtime_logged or _pcon_direct_last_dispatch_ms:
            _reset_direct_pcon_runtime()
        return

    try:
        if not Map.IsMapReady() or not Map.IsExplorable():
            return
        if int(Map.GetMapID() or 0) != JUSTICIAR_THOMMIS_ROOM:
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

    # Four-Leaf Clover and Honeycomb are driven by morale, not a buff effect.
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


def _configure_runtime_upkeeps(*, consumables_enabled: bool | None = None) -> None:
    global _runtime_consumables_enabled, _configured_consumable_upkeeps

    previous_runtime_enabled = _runtime_consumables_enabled
    if consumables_enabled is not None:
        _runtime_consumables_enabled = bool(consumables_enabled)

    if previous_runtime_enabled != _runtime_consumables_enabled:
        _reset_direct_pcon_runtime(clear_unresolved=False)

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
    if _enabled_consumable_upkeeps() != _configured_consumable_upkeeps:
        _configure_runtime_upkeeps()


def _runtime_consumable_upkeep_node(enabled: bool) -> BehaviorTree:
    def _apply(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        _configure_runtime_upkeeps(consumables_enabled=enabled)
        return BehaviorTree.NodeState.SUCCESS
    return BehaviorTree(BehaviorTree.ActionNode(
        name='Resume Consumable Upkeep' if enabled else 'Suspend Consumable Upkeep',
        action_fn=_apply,
        aftercast_ms=0,
    ))

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
            return BT.Succeeder('Restock Disabled')

        return BT.RestockItemsFromList(tuple(items), allow_missing=True)

    return BT.Subtree('Restock Selected Consumables', _build)


def _draw_config() -> None:
    import PyImGui

    global _hard_mode, _restock_conset, _use_conset
    global _restock_pcons, _use_pcons, _use_summoning_stone, _auto_loot
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots, _inventory_min_id_kits
    global _inventory_min_salvage_kits

    changed = False
    upkeep_changed = False

    PyImGui.text('Voltaic Spear Config')
    PyImGui.separator()

    value = PyImGui.checkbox('Hard Mode (HM)', _hard_mode)
    if value != _hard_mode:
        _hard_mode = value
        changed = True

    PyImGui.separator()
    PyImGui.text('Conset')

    value = PyImGui.checkbox('Restock conset from storage', _restock_conset)
    if value != _restock_conset:
        _restock_conset = value
        changed = True

    value = PyImGui.checkbox('Activate / maintain conset', _use_conset)
    if value != _use_conset:
        _use_conset = value
        changed = True

    PyImGui.separator()
    PyImGui.text('Personal consumables')
    PyImGui.text_wrapped('Pcons, consets and summoning stones are only used in the Thommis room, never during travel.')

    value = PyImGui.checkbox('Restock pcons from storage', _restock_pcons)
    if value != _restock_pcons:
        _restock_pcons = value
        changed = True

    value = PyImGui.checkbox('Activate / maintain pcons', _use_pcons)
    if value != _use_pcons:
        _use_pcons = value
        changed = True
        upkeep_changed = True

    value = PyImGui.checkbox('Use summoning stones', _use_summoning_stone)
    if value != _use_summoning_stone:
        _use_summoning_stone = value
        changed = True

    value = PyImGui.checkbox('Auto loot', _auto_loot)
    if value != _auto_loot:
        _auto_loot = value
        changed = True
        upkeep_changed = True

    PyImGui.separator()
    PyImGui.text('Inventory maintenance')

    value = PyImGui.checkbox(
        'Run MerchantRules when inventory is low',
        _inventory_maintenance_enabled,
    )
    if value != _inventory_maintenance_enabled:
        _inventory_maintenance_enabled = value
        changed = True

    if _inventory_maintenance_enabled:
        value = max(
            0,
            int(
                PyImGui.input_int(
                    'Minimum free slots',
                    _inventory_min_free_slots,
                )
            ),
        )
        if value != _inventory_min_free_slots:
            _inventory_min_free_slots = value
            changed = True

        value = max(
            0,
            int(
                PyImGui.input_int(
                    'Minimum Superior ID kits (0 = disabled)',
                    _inventory_min_id_kits,
                )
            ),
        )
        if value != _inventory_min_id_kits:
            _inventory_min_id_kits = value
            changed = True

        value = max(
            0,
            int(
                PyImGui.input_int(
                    'Minimum Superior salvage kits (0 = disabled)',
                    _inventory_min_salvage_kits,
                )
            ),
        )
        if value != _inventory_min_salvage_kits:
            _inventory_min_salvage_kits = value
            changed = True

        PyImGui.text_wrapped(
            'If one active account falls below a threshold, MerchantRules runs '
            'on every active account before the party is created.'
        )

    if changed:
        _save_config()
    if upkeep_changed:
        _configure_runtime_upkeeps()


def _format_time(seconds: float) -> str:
    if seconds <= 0.0 or seconds == float('inf'):
        return '--:--'
    minutes, remaining = divmod(int(seconds), 60)
    return f'{minutes:02d}:{remaining:02d}'


def _account_key(email: str) -> str:
    return str(email).replace('@', '_at_').replace('.', '_')


def _account_label(key: str) -> str:
    if key in _char_names:
        return _char_names[key]
    return str(key).replace('_at_', '@').replace('_', '.')


def _refresh_character_names() -> bool:
    changed = False

    local_email = str(Player.GetAccountEmail() or '').strip()
    local_name = str(Player.GetName() or '').strip()
    if local_email and local_name:
        key = _account_key(local_email)
        if _char_names.get(key) != local_name:
            _char_names[key] = local_name
            changed = True

    for account in _inventory_accounts():
        email = str(getattr(account, 'AccountEmail', '') or '').strip()
        name = _shared_account_label(account).strip()
        if not email or not name:
            continue
        key = _account_key(email)
        if _char_names.get(key) != name:
            _char_names[key] = name
            changed = True

    return changed


def _draw_statistics() -> None:
    import PyImGui

    global _statistics_reset_pending

    if _refresh_character_names():
        _save_statistics()

    flags = PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg
    PyImGui.text('Voltaic Spear Statistics')
    PyImGui.same_line()
    if PyImGui.button('Reset statistics'):
        _statistics_reset_pending = True
    if _statistics_reset_pending:
        PyImGui.text_wrapped('Reset all session and saved runs, drops and timings? This cannot be undone.')
        if _run_started_at > 0.0:
            PyImGui.text_wrapped('The current run keeps its timers and will count as the first run after reset.')
        if PyImGui.button('Confirm reset##voltaic_statistics'):
            _reset_statistics()
        PyImGui.same_line()
        if PyImGui.button('Cancel##voltaic_statistics'):
            _statistics_reset_pending = False
    PyImGui.separator()

    if PyImGui.begin_table('##voltaic_counts', 4, flags):
        for label in ('Period', 'Runs', 'Spears', 'Runs/Spear'):
            PyImGui.table_setup_column(label)
        PyImGui.table_headers_row()
        for period, runs, spears in (
            ('Session', _session_runs, _session_spears),
            ('All time', _total_runs, _total_spears),
        ):
            PyImGui.table_next_row()
            values = (period, runs, spears, f'{runs / spears:.1f}' if spears else '-')
            for column, value in enumerate(values):
                PyImGui.table_set_column_index(column)
                PyImGui.text(str(value))
        PyImGui.end_table()

    if PyImGui.begin_table('##voltaic_times', 6, flags):
        for label in ('Phase', 'Current', 'Last', 'Average', 'Best', 'Worst'):
            PyImGui.table_setup_column(label)
        PyImGui.table_headers_row()
        now = time.monotonic()
        if _run_started_at > 0.0:
            current = now - _run_started_at
            current_verdant = (_thommis_started_at or now) - _run_started_at
            current_thommis = now - _thommis_started_at if _thommis_started_at > 0.0 else 0.0
        else:
            current = _last_run_seconds
            current_verdant = _last_verdant_seconds
            current_thommis = _last_thommis_seconds
        for phase, live, last, total, count, best, worst in (
            (
                'Verdant',
                current_verdant,
                _last_verdant_seconds,
                _verdant_total_seconds,
                _split_runs,
                _verdant_best_seconds,
                _verdant_worst_seconds,
            ),
            (
                'Thommis',
                current_thommis,
                _last_thommis_seconds,
                _thommis_total_seconds,
                _split_runs,
                _thommis_best_seconds,
                _thommis_worst_seconds,
            ),
            ('Total', current, _last_run_seconds, _total_seconds, _total_runs, _best_seconds, _worst_seconds),
        ):
            PyImGui.table_next_row()
            values = (
                phase,
                *(_format_time(value) for value in (live, last, total / count if count else 0.0, best, worst)),
            )
            for column, value in enumerate(values):
                PyImGui.table_set_column_index(column)
                PyImGui.text(value)
        PyImGui.end_table()
    PyImGui.text(f'Split times recorded: {_split_runs} completed run(s).')

    PyImGui.spacing()
    PyImGui.text('Voltaic Spear Drops By Character')
    if PyImGui.begin_table('##voltaic_by_character', 4, flags):
        for label in ('Character', 'Session', 'All Time', 'Drop Rate'):
            PyImGui.table_setup_column(label)
        PyImGui.table_headers_row()

        keys = sorted(set(_session_spear_drops) | set(_spear_drops))
        for key in keys:
            session_count = _session_spear_drops.get(key, 0)
            all_time_count = _spear_drops.get(key, 0)
            rate = f'{all_time_count / _total_runs * 100.0:.1f}%' if _total_runs > 0 and all_time_count > 0 else '-'
            values = (
                _account_label(key),
                session_count,
                all_time_count,
                rate,
            )
            PyImGui.table_next_row()
            for column, value in enumerate(values):
                PyImGui.table_set_column_index(column)
                PyImGui.text(str(value))

        PyImGui.end_table()


def _action_node(name: str, callback: Callable[[], None]) -> BehaviorTree:
    def _run() -> BehaviorTree.NodeState:
        callback()
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_run,
            aftercast_ms=0,
        )
    )


def _start_statistics() -> BehaviorTree:
    def _start() -> None:
        global _run_started_at, _thommis_started_at, _last_run_spears
        _run_started_at = time.monotonic()
        _thommis_started_at = 0.0
        _last_run_spears = 0

    return _action_node('Start Run Timer', _start)


def _start_thommis_statistics() -> BehaviorTree:
    def _split() -> None:
        global _thommis_started_at
        # A retried fight step must not restart the split or lose elapsed time.
        if _run_started_at > 0.0 and _thommis_started_at <= 0.0:
            _thommis_started_at = time.monotonic()

    return _action_node('Finish Verdant Timer And Start Thommis Timer', _split)


def _record_statistics() -> BehaviorTree:
    def _record() -> None:
        global _total_runs, _session_runs, _total_seconds
        global _best_seconds, _worst_seconds, _last_run_seconds
        global _run_started_at, _thommis_started_at, _last_verdant_seconds, _last_thommis_seconds
        global _split_runs, _verdant_total_seconds, _verdant_best_seconds, _verdant_worst_seconds
        global _thommis_total_seconds, _thommis_best_seconds, _thommis_worst_seconds

        if _run_started_at <= 0.0:
            return

        finished_at = time.monotonic()
        _last_run_seconds = finished_at - _run_started_at
        if _thommis_started_at > 0.0:
            _last_verdant_seconds = _thommis_started_at - _run_started_at
            _last_thommis_seconds = finished_at - _thommis_started_at
            _split_runs += 1
            _verdant_total_seconds += _last_verdant_seconds
            _verdant_best_seconds = min(_verdant_best_seconds, _last_verdant_seconds)
            _verdant_worst_seconds = max(_verdant_worst_seconds, _last_verdant_seconds)
            _thommis_total_seconds += _last_thommis_seconds
            _thommis_best_seconds = min(_thommis_best_seconds, _last_thommis_seconds)
            _thommis_worst_seconds = max(_thommis_worst_seconds, _last_thommis_seconds)
        else:
            # A run resumed beyond the split has no reliable phase durations.
            _last_verdant_seconds = 0.0
            _last_thommis_seconds = 0.0

        _total_runs += 1
        _session_runs += 1
        _total_seconds += _last_run_seconds
        _best_seconds = min(_best_seconds, _last_run_seconds)
        _worst_seconds = max(_worst_seconds, _last_run_seconds)
        _run_started_at = 0.0
        _thommis_started_at = 0.0
        _save_statistics()

        PySystem.Console.Log(
            MODULE_NAME,
            f'Run completed in {_format_time(_last_run_seconds)} '
            f'(Verdant: {_format_time(_last_verdant_seconds)}, Thommis: {_format_time(_last_thommis_seconds)}).',
            PySystem.Console.MessageType.Success,
        )

    return _action_node('Record Successful Run', _record)


# region Inventory maintenance


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
        email = str(getattr(account, 'AccountEmail', '') or '').strip()
        if not email or email in seen:
            continue
        seen.add(email)
        unique.append(account)
    return unique


def _shared_account_label(account: object) -> str:
    agent_data = getattr(account, 'AgentData', None)
    character_name = str(
        getattr(agent_data, 'CharacterName', '') or ''
    ).strip()
    if character_name:
        return character_name
    return str(getattr(account, 'AccountEmail', '') or 'Unknown account')


def _inventory_spear_statistics_node(
    *,
    after_chest: bool,
) -> BehaviorTree:
    node_name = (
        'Record Voltaic Spears After Chest'
        if after_chest
        else 'Snapshot Voltaic Spears Before Run'
    )
    state: dict[str, object] = {
        'started': False,
        'local_email': '',
        'account_keys': [],
        'requests': [],
        'request_index': 0,
        'waiting': False,
        'request_started_at': 0.0,
        'local_email_wait_started_at': 0.0,
    }

    def _reset() -> None:
        state['started'] = False
        state['local_email'] = ''
        state['account_keys'] = []
        state['requests'] = []
        state['request_index'] = 0
        state['waiting'] = False
        state['request_started_at'] = 0.0
        state['local_email_wait_started_at'] = 0.0

    def _start() -> bool:
        if _refresh_character_names():
            _save_statistics()

        local_email = str(Player.GetAccountEmail() or '').strip()
        if not local_email:
            return False

        section = (
            _SPEAR_RUN_SECTION
            if after_chest
            else _SPEAR_SNAPSHOT_SECTION
        )
        local_key = _account_key(local_email)
        local_count = int(
            GLOBAL_CACHE.Inventory.GetModelCount(VOLTAIC_SPEAR_MODEL_ID)
        )
        _settings.set(section, local_key, local_count)

        account_keys = [local_key]
        requests: list[dict[str, str]] = []
        for account in _inventory_accounts():
            email = str(
                getattr(account, 'AccountEmail', '') or ''
            ).strip()
            if not email or email == local_email:
                continue

            key = _account_key(email)
            if key not in account_keys:
                account_keys.append(key)
            requests.append(
                {
                    'email': email,
                    'key': key,
                    'section': section,
                }
            )

        for key in account_keys:
            _spear_drops.setdefault(key, 0)

        state['started'] = True
        state['local_email'] = local_email
        state['account_keys'] = account_keys
        state['requests'] = requests
        state['request_index'] = 0
        state['waiting'] = False
        return True

    def _finish() -> None:
        global _total_spears, _session_spears, _last_run_spears

        if not after_chest:
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    '[Statistics] Voltaic Spear snapshot completed for '
                    f"{len(state['account_keys'])} account(s)."
                ),
                PySystem.Console.MessageType.Info,
            )
            _save_statistics()
            return

        total_delta = 0
        drop_messages: list[str] = []
        for raw_key in state['account_keys']:
            key = str(raw_key)
            before = _settings.get_int(
                _SPEAR_SNAPSHOT_SECTION,
                key,
                -1,
            )
            after = _settings.get_int(
                _SPEAR_RUN_SECTION,
                key,
                -1,
            )
            delta = (
                max(0, after - before)
                if before >= 0 and after >= 0
                else 0
            )
            if delta <= 0:
                continue

            _spear_drops[key] = _spear_drops.get(key, 0) + delta
            _session_spear_drops[key] = (
                _session_spear_drops.get(key, 0) + delta
            )
            total_delta += delta
            drop_messages.append(f'{_account_label(key)} +{delta}')

        _last_run_spears = total_delta
        _total_spears += total_delta
        _session_spears += total_delta
        _save_statistics()

        details = ', '.join(drop_messages) if drop_messages else 'no drop'
        PySystem.Console.Log(
            MODULE_NAME,
            (
                '[Statistics] Chest recorded - Voltaic Spears '
                f'{total_delta} ({details}).'
            ),
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
                    wait_started = float(
                        state['local_email_wait_started_at'] or 0.0
                    )
                    if wait_started <= 0.0:
                        state['local_email_wait_started_at'] = now
                        return BehaviorTree.NodeState.RUNNING
                    if (
                        (now - wait_started) * 1000.0
                        < _INVENTORY_QUERY_TIMEOUT_MS
                    ):
                        return BehaviorTree.NodeState.RUNNING

                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            '[Statistics] Local account email unavailable; '
                            'skipping the Voltaic Spear snapshot.'
                        ),
                        PySystem.Console.MessageType.Warning,
                    )
                    _reset()
                    return BehaviorTree.NodeState.SUCCESS

            requests: list[dict[str, str]] = state['requests']
            while int(state['request_index']) < len(requests):
                request_index = int(state['request_index'])
                request = requests[request_index]
                email = str(request['email'])

                if not bool(state['waiting']):
                    reset_inventory_count(
                        email,
                        VOLTAIC_SPEAR_MODEL_ID,
                        VOLTAIC_SPEAR_MODEL_ID,
                    )
                    _settings.set(
                        request['section'],
                        request['key'],
                        -1,
                    )
                    GLOBAL_CACHE.ShMem.SendMessage(
                        str(state['local_email']),
                        email,
                        SharedCommandType.InventoryQuery,
                        (
                            float(VOLTAIC_SPEAR_MODEL_ID),
                            float(VOLTAIC_SPEAR_MODEL_ID),
                            0.0,
                            0.0,
                        ),
                        ('report_inventory_count',),
                    )
                    state['waiting'] = True
                    state['request_started_at'] = time.monotonic()
                    return BehaviorTree.NodeState.RUNNING

                count = int(
                    get_inventory_count(
                        email,
                        VOLTAIC_SPEAR_MODEL_ID,
                        VOLTAIC_SPEAR_MODEL_ID,
                    )
                )
                if count >= 0:
                    _settings.set(
                        request['section'],
                        request['key'],
                        count,
                    )
                    state['request_index'] = request_index + 1
                    state['waiting'] = False
                    continue

                elapsed_ms = (
                    time.monotonic() - float(state['request_started_at'])
                ) * 1000.0
                if elapsed_ms >= _INVENTORY_QUERY_TIMEOUT_MS:
                    PySystem.Console.Log(
                        MODULE_NAME,
                        (
                            '[Statistics] Voltaic Spear inventory query '
                            f"timed out for {_account_label(request['key'])}."
                        ),
                        PySystem.Console.MessageType.Warning,
                    )
                    state['request_index'] = request_index + 1
                    state['waiting'] = False
                    continue

                return BehaviorTree.NodeState.RUNNING

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


def _shared_account_map_id(account: object) -> int:
    agent_data = getattr(account, 'AgentData', None)
    map_data = getattr(agent_data, 'Map', None)
    return int(getattr(map_data, 'MapID', 0) or 0)


def _shared_account_map_instance(
    account: object,
) -> tuple[int, int, int, int]:
    agent_data = getattr(account, 'AgentData', None)
    map_data = getattr(agent_data, 'Map', None)
    return (
        int(getattr(map_data, 'MapID', 0) or 0),
        int(getattr(map_data, 'Region', 0) or 0),
        int(getattr(map_data, 'District', 0) or 0),
        int(getattr(map_data, 'Language', 0) or 0),
    )


def _iter_shared_inventory_slots(account: object):
    inventory_bags = getattr(account, 'InventoryBags', None)
    if inventory_bags is None:
        return

    for bag in inventory_bags.iter_bags():
        bag_id = int(getattr(bag, 'BagID', 0) or 0)
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
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()

    for account in _inventory_accounts():
        email = str(getattr(account, 'AccountEmail', '') or '').strip()
        if not email or email in seen:
            continue
        seen.add(email)
        targets.append((email, _shared_account_label(account)))

    local_email = str(Player.GetAccountEmail() or '').strip()
    if local_email and local_email not in seen:
        local_name = str(Player.GetName() or '').strip()
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
        occupied, capacity, id_kits, salvage_kits = (
            int(value) for value in state
        )

    available = capacity > 0 and 0 <= occupied <= capacity
    free_slots = max(0, capacity - occupied) if available else 0
    return {
        'email': str(email),
        'label': str(label),
        'available': available,
        'capacity': capacity,
        'occupied': occupied,
        'free_slots': free_slots,
        'id_kits': id_kits,
        'salvage_kits': salvage_kits,
    }


def _inventory_account_statuses() -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []
    for raw_status in _inventory_status_snapshot.values():
        status = dict(raw_status)
        issues: list[str] = []

        if not bool(status.get('available', False)):
            issues.append('inventory query unavailable')
        else:
            free_slots = int(status.get('free_slots', 0) or 0)
            id_kits = int(status.get('id_kits', 0) or 0)
            salvage_kits = int(status.get('salvage_kits', 0) or 0)

            if (
                _inventory_min_free_slots > 0
                and free_slots < _inventory_min_free_slots
            ):
                issues.append(
                    f'free slots {free_slots}/{_inventory_min_free_slots}'
                )
            if (
                _inventory_min_id_kits > 0
                and id_kits < _inventory_min_id_kits
            ):
                issues.append(
                    f'ID kits {id_kits}/{_inventory_min_id_kits}'
                )
            if (
                _inventory_min_salvage_kits > 0
                and salvage_kits < _inventory_min_salvage_kits
            ):
                issues.append(
                    'salvage kits '
                    f'{salvage_kits}/{_inventory_min_salvage_kits}'
                )

        status['issues'] = issues
        statuses.append(status)
    return statuses


def _inventory_maintenance_issues() -> list[str]:
    statuses = _inventory_account_statuses()
    if not statuses:
        return ['No active account inventory query result is available.']
    return [
        f"{status['label']}: {', '.join(status['issues'])}"
        for status in statuses
        if status['issues']
    ]


def _log_inventory_statuses(
    statuses: list[dict[str, object]],
) -> None:
    if not statuses:
        PySystem.Console.Log(
            MODULE_NAME,
            '[Inventory] No active account inventory query result is available.',
            PySystem.Console.MessageType.Warning,
        )
        return

    for status in statuses:
        issues = list(status['issues'])
        result = 'MAINTENANCE' if issues else 'OK'
        if bool(status.get('available', False)):
            message = (
                f"[Inventory] {status['label']}: "
                f"free={status['free_slots']}/{status['capacity']}, "
                f"occupied={status['occupied']}, "
                f"Superior ID kits={status['id_kits']}, "
                f"Superior salvage kits={status['salvage_kits']} -> {result}"
            )
        else:
            message = (
                f"[Inventory] {status['label']}: "
                f'local inventory query unavailable -> {result}'
            )

        PySystem.Console.Log(
            MODULE_NAME,
            message,
            (
                PySystem.Console.MessageType.Warning
                if issues
                else PySystem.Console.MessageType.Info
            ),
        )


def _query_all_inventory_states_node(
    name: str,
    *,
    timeout_ms: int = _INVENTORY_QUERY_TIMEOUT_MS,
) -> BehaviorTree:
    state: dict[str, object] = {
        'started': False,
        'request_id': '',
        'pending': {},
        'results': {},
        'started_at': 0.0,
    }

    def _reset() -> None:
        state['started'] = False
        state['request_id'] = ''
        state['pending'] = {}
        state['results'] = {}
        state['started_at'] = 0.0

    def _finish() -> BehaviorTree.NodeState:
        global _inventory_status_snapshot
        _inventory_status_snapshot = dict(state['results'])
        _reset()
        return BehaviorTree.NodeState.SUCCESS

    def _start() -> None:
        request_id = (
            f'volta_inventory_state_{int(time.monotonic() * 1000)}'
        )
        sender_email = str(Player.GetAccountEmail() or '').strip()
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
                        f'[Inventory] Local inventory query failed on {label}: {exc}',
                        PySystem.Console.MessageType.Error,
                    )
                    local_state = None
                results[email] = _build_inventory_status(
                    email,
                    label,
                    local_state,
                )
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
                    float(
                        SALVAGE_KIT_MODEL_IDS[0]
                        if SALVAGE_KIT_MODEL_IDS
                        else 0
                    ),
                    0.0,
                ),
                ('report_inventory_state', request_id, '', ''),
            )
            pending[email] = label

        state['started'] = True
        state['request_id'] = request_id
        state['pending'] = pending
        state['results'] = results
        state['started_at'] = time.monotonic()
        PySystem.Console.Log(
            MODULE_NAME,
            (
                '[Inventory] Requested real inventory state from '
                f'{len(targets)} active account(s).'
            ),
            PySystem.Console.MessageType.Info,
        )

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if bool(node.blackboard.get('USER_INTERRUPT_ACTIVE', False)):
                _reset()
                return BehaviorTree.NodeState.FAILURE

            if not bool(state['started']):
                _start()

            pending: dict[str, str] = state['pending']
            request_id = str(state['request_id'])
            for email in list(pending):
                reply = get_inventory_state(email, request_id)
                if reply is None:
                    continue
                label = pending.pop(email)
                state['results'][email] = _build_inventory_status(
                    email,
                    label,
                    reply,
                )

            if not pending:
                return _finish()

            elapsed_ms = int(
                (time.monotonic() - float(state['started_at'])) * 1000.0
            )
            if elapsed_ms < max(0, int(timeout_ms)):
                return BehaviorTree.NodeState.RUNNING

            for email, label in list(pending.items()):
                state['results'][email] = _build_inventory_status(
                    email,
                    label,
                    None,
                )
                PySystem.Console.Log(
                    MODULE_NAME,
                    f'[Inventory] Real inventory query timed out for {label}.',
                    PySystem.Console.MessageType.Warning,
                )
            pending.clear()
            return _finish()

        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f'[Inventory] Multibox inventory-state query failed: {exc}',
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
    return [email for email, _label in _inventory_target_accounts()]


def _inventory_maintenance_trigger_node() -> BehaviorTree:
    def _log(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        statuses = _inventory_account_statuses()
        trigger_labels = [
            str(status['label'])
            for status in statuses
            if status['issues']
        ]
        recipients = _inventory_recipient_emails()
        trigger_text = (
            ', '.join(trigger_labels)
            if trigger_labels
            else 'inventory verification'
        )
        PySystem.Console.Log(
            MODULE_NAME,
            (
                f'[Inventory] Maintenance triggered by: {trigger_text}. '
                'MerchantRules will run on ALL '
                f'{len(recipients)} active account(s).'
            ),
            PySystem.Console.MessageType.Warning,
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Log Collective Inventory Maintenance Trigger',
            action_fn=_log,
            aftercast_ms=0,
        )
    )


def _inventory_model_label(model_id: int) -> str:
    try:
        return str(ModelID(int(model_id)).name)
    except Exception:
        return f'model_{int(model_id)}'


def _log_unhealthy_inventory_contents() -> None:
    status_by_email = {
        str(status['email']): status
        for status in _inventory_account_statuses()
        if status['issues']
    }

    for account in _inventory_accounts():
        email = str(getattr(account, 'AccountEmail', '') or '').strip()
        status = status_by_email.get(email)
        if status is None:
            continue

        label = str(status['label'])
        entries: list[str] = []
        for bag_id, slot in _iter_shared_inventory_slots(account):
            model_id = int(getattr(slot, 'ModelID', 0) or 0)
            quantity = int(getattr(slot, 'Quantity', 0) or 0)
            if model_id <= 0 or quantity <= 0:
                continue
            slot_no = int(getattr(slot, 'Slot', 0) or 0)
            entries.append(
                f'B{bag_id}:S{slot_no} '
                f'{_inventory_model_label(model_id)}({model_id}) x{quantity}'
            )

        PySystem.Console.Log(
            MODULE_NAME,
            (
                f'[Inventory diagnostic] {label}: '
                f'mirrored occupied items={len(entries)}.'
            ),
            PySystem.Console.MessageType.Warning,
        )
        for start_index in range(0, len(entries), 8):
            PySystem.Console.Log(
                MODULE_NAME,
                f'[Inventory diagnostic] {label}: '
                + ' | '.join(entries[start_index:start_index + 8]),
                PySystem.Console.MessageType.Info,
            )


def _inventory_is_healthy_node(
    name: str,
    *,
    log_success: bool = True,
) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        statuses = _inventory_account_statuses()
        _log_inventory_statuses(statuses)

        if not statuses:
            return BehaviorTree.NodeState.FAILURE
        if any(status['issues'] for status in statuses):
            return BehaviorTree.NodeState.FAILURE

        if log_success:
            PySystem.Console.Log(
                MODULE_NAME,
                'Inventory check passed on every active account.',
                PySystem.Console.MessageType.Success,
            )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ConditionNode(name=name, condition_fn=_check)
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
    expected = (
        int(map_id),
        int(region),
        int(district),
        int(language),
    )
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
    return BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name=name,
            condition_fn=lambda _node: (
                BehaviorTree.NodeState.SUCCESS
                if _all_accounts_on_map(map_id)
                else BehaviorTree.NodeState.RUNNING
            ),
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
    return BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name=name,
            condition_fn=lambda _node: (
                BehaviorTree.NodeState.SUCCESS
                if _all_accounts_on_map_instance(
                    map_id,
                    INVENTORY_TRAVEL_REGION,
                    INVENTORY_TRAVEL_DISTRICT,
                    INVENTORY_TRAVEL_LANGUAGE,
                )
                else BehaviorTree.NodeState.RUNNING
            ),
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
        extra_data=(widget_name, '', '', ''),
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
        function = getattr(
            botting_tree,
            'SetAutoInventoryHandlerEnabled',
            None,
        )
        if callable(function):
            try:
                function(enabled)
            except Exception:
                pass
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=(
                'Enable Local Auto Inventory Handler'
                if enabled
                else 'Disable Local Auto Inventory Handler'
            ),
            action_fn=_set,
            aftercast_ms=0,
        )
    )


def _travel_all_accounts_to_umbral(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(
        name='Travel Every Account To Umbral Grotto',
        children=[
            BTShared.SendAndWait(
                command=SharedCommandType.TravelToMap,
                params=(
                    float(UMBRAL_GROTTO),
                    float(INVENTORY_TRAVEL_REGION),
                    float(INVENTORY_TRAVEL_DISTRICT),
                    float(INVENTORY_TRAVEL_LANGUAGE),
                ),
                include_self=True,
                refs_blackboard_key=f'{attempt_key}_travel_umbral_refs',
                timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
                poll_interval_ms=250,
                log=True,
            ),
            _wait_for_all_accounts_on_inventory_instance(
                UMBRAL_GROTTO,
                name='Wait For Every Account In Umbral Grotto EU-English-1',
            ),
        ],
    )


def _return_all_accounts_to_umbral(attempt_key: str) -> BehaviorTree:
    explorable = BT.Selector(
        name='Current Map Can Be Resigned',
        children=[
            BT.IsCurrentMap(VERDANT_CASCADES, log=False),
            BT.IsCurrentMap(SLAVERS_EXILE, log=False),
            BT.IsCurrentMap(JUSTICIAR_THOMMIS_ROOM, log=False),
        ],
    )
    resign = BT.Sequence(
        name='Resign Party To Umbral Grotto',
        children=[
            explorable,
            BT.Resign(
                wait_for_map_load=True,
                target_map_id=UMBRAL_GROTTO,
                multi_account=True,
                timeout_ms=INVENTORY_TRAVEL_TIMEOUT_MS,
                log=True,
            ),
            _wait_for_all_accounts_on_map(
                UMBRAL_GROTTO,
                name='Wait For Party Return To Umbral Grotto',
            ),
        ],
    )
    return BT.Selector(
        name='Ensure Every Account Is In Umbral Grotto',
        children=[
            _all_accounts_on_map_node(
                UMBRAL_GROTTO,
                'Every Account Already In Umbral Grotto',
            ),
            resign,
            _travel_all_accounts_to_umbral(attempt_key),
        ],
    )


def _restore_inventoryplus_after_merchant(
    attempt_key: str,
) -> BehaviorTree:
    return BT.Sequence(
        name='Restore InventoryPlus After MerchantRules',
        children=[
            _send_widget_state(
                INVENTORY_PLUS_WIDGET_NAME,
                enabled=True,
                refs_key=f'{attempt_key}_enable_inventoryplus_refs',
            ),
            _set_local_auto_inventory_handler(True),
        ],
    )


def _merchant_stock_request_spec() -> str:
    targets: list[str] = []
    if _inventory_min_id_kits > 0 and ID_KIT_MODEL_IDS:
        targets.append(
            f'{ID_KIT_MODEL_IDS[0]}:{_inventory_min_id_kits}'
        )
    if _inventory_min_salvage_kits > 0 and SALVAGE_KIT_MODEL_IDS:
        targets.append(
            f'{SALVAGE_KIT_MODEL_IDS[0]}:{_inventory_min_salvage_kits}'
        )
    return 'stock:' + ','.join(targets) if targets else ''


def _run_merchant_rules(attempt_key: str) -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        recipients = _inventory_recipient_emails()
        if not recipients:
            PySystem.Console.Log(
                MODULE_NAME,
                '[Inventory] MerchantRules aborted: no active recipients.',
                PySystem.Console.MessageType.Error,
            )
            return BehaviorTree(
                BehaviorTree.FailerNode(
                    name='No Active MerchantRules Recipients'
                )
            )

        request_id = (
            f'volta_inventory_{attempt_key}_{int(time.monotonic() * 1000)}'
        )
        execute = BTShared.SendAndWait(
            command=SharedCommandType.MerchantRules,
            params=(3.0, 0.0, 0.0, 0.0),
            extra_data=(
                request_id,
                _merchant_stock_request_spec(),
                '0',
                '0',
            ),
            recipients=recipients,
            include_self=True,
            refs_blackboard_key=f'{attempt_key}_merchant_rules_refs',
            timeout_ms=INVENTORY_MERCHANT_TIMEOUT_MS,
            poll_interval_ms=250,
            log=True,
        )
        return BT.Selector(
            name='Execute MerchantRules And Restore InventoryPlus',
            children=[
                BT.Sequence(
                    name='MerchantRules Completed',
                    children=[
                        execute,
                        _restore_inventoryplus_after_merchant(attempt_key),
                    ],
                ),
                BT.Sequence(
                    name='Restore InventoryPlus After MerchantRules Failure',
                    children=[
                        _restore_inventoryplus_after_merchant(
                            f'{attempt_key}_failure'
                        ),
                        BehaviorTree(
                            BehaviorTree.FailerNode(
                                name='Propagate MerchantRules Failure'
                            )
                        ),
                    ],
                ),
            ],
        )

    return BT.Subtree('Run MerchantRules On All Active Accounts', _build)


def _inventory_maintenance_attempt(attempt_number: int) -> BehaviorTree:
    attempt_key = f'inventory_attempt_{attempt_number}'
    return BT.Sequence(
        name=f'Inventory Maintenance Attempt {attempt_number}',
        children=[
            BT.LogMessage(
                message=(
                    f'Inventory maintenance attempt {attempt_number}/'
                    f'{INVENTORY_MAINTENANCE_RETRY_COUNT} in Umbral Grotto.'
                ),
                module_name=MODULE_NAME,
            ),
            _set_local_auto_inventory_handler(False),
            _send_widget_state(
                INVENTORY_PLUS_WIDGET_NAME,
                enabled=False,
                refs_key=f'{attempt_key}_disable_inventoryplus_refs',
            ),
            _send_widget_state(
                MERCHANT_RULES_WIDGET_NAME,
                enabled=True,
                refs_key=f'{attempt_key}_enable_merchant_rules_refs',
            ),
            BT.Wait(1_000),
            _run_merchant_rules(attempt_key),
            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
            _query_all_inventory_states_node(
                name=(
                    'Refresh Real Inventories After Attempt '
                    f'{attempt_number}'
                )
            ),
            _inventory_is_healthy_node(
                f'Verify Inventory After Attempt {attempt_number}',
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
            issue_text = '; '.join(_inventory_maintenance_issues())
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    'Inventory maintenance failed twice. The bot was paused '
                    f'safely. Remaining issue(s): {issue_text}'
                ),
                PySystem.Console.MessageType.Error,
            )
            _log_unhealthy_inventory_contents()

            if botting_tree is not None:
                function = getattr(
                    botting_tree,
                    'SetAutoInventoryHandlerEnabled',
                    None,
                )
                if callable(function):
                    try:
                        function(True)
                    except Exception:
                        pass

            sender_email = str(Player.GetAccountEmail() or '').strip()
            for account in _inventory_accounts():
                receiver_email = str(
                    getattr(account, 'AccountEmail', '') or ''
                ).strip()
                if not sender_email or not receiver_email:
                    continue
                GLOBAL_CACHE.ShMem.SendMessage(
                    sender_email,
                    receiver_email,
                    SharedCommandType.EnableWidget,
                    (0.0, 0.0, 0.0, 0.0),
                    (INVENTORY_PLUS_WIDGET_NAME, '', '', ''),
                )

            if botting_tree is not None:
                pause = getattr(botting_tree, 'Pause', None)
                if callable(pause):
                    try:
                        pause(True)
                    except Exception:
                        pass

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Pause Bot After Inventory Maintenance Failure',
            action_fn=_stop,
            aftercast_ms=0,
        )
    )


def InventoryCheckAndMaintenance() -> BehaviorTree:
    disabled = BehaviorTree(
        BehaviorTree.ConditionNode(
            name='Inventory Maintenance Disabled',
            condition_fn=lambda _node: not _inventory_maintenance_enabled,
        )
    )
    attempts = [
        _inventory_maintenance_attempt(attempt_number)
        for attempt_number in range(
            1,
            INVENTORY_MAINTENANCE_RETRY_COUNT + 1,
        )
    ]
    attempts.append(_stop_for_inventory_failure_node())

    enabled = BT.Sequence(
        name='Enabled Inventory Check And Maintenance',
        children=[
            _query_all_inventory_states_node(
                name='Query Real Inventory State On Every Active Account'
            ),
            BT.Selector(
                name='Check Inventory Thresholds',
                children=[
                    _inventory_is_healthy_node(
                        'Inventory Thresholds Already Satisfied',
                        log_success=True,
                    ),
                    BT.Sequence(
                        name='Run Inventory Maintenance',
                        children=[
                            _inventory_maintenance_trigger_node(),
                            _return_all_accounts_to_umbral(
                                'inventory_maintenance_setup'
                            ),
                            BT.LeaveParty(),
                            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
                            BT.Selector(
                                attempts,
                                name=(
                                    'Retry Inventory Maintenance '
                                    'In Umbral Grotto'
                                ),
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
    return BT.Selector(
        [disabled, enabled],
        name='Inventory Check And Maintenance',
    )


def StartupInventoryCheck() -> BehaviorTree:
    return BT.Selector(
        [
            BT.Sequence(
                name='Check Inventories Before Leaving Umbral Grotto',
                children=[
                    BT.IsCurrentMap(UMBRAL_GROTTO, log=False),
                    InventoryCheckAndMaintenance(),
                ],
            ),
            BT.Succeeder(
                'Skip Startup Inventory Check Outside Umbral Grotto'
            ),
        ],
        name='Startup Inventory Check',
    )


# endregion


def _summoning_stone() -> BehaviorTree:
    """Broadcast a best-effort summoning-stone request without blocking the run.

    Each account handles its own active summon / sickness / inventory state.
    The BT never waits for an acknowledgement: an already-active summon must not
    stall the next dungeon step.
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
                # Summoning stones are optional/best-effort. Never block the run.
                continue

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Use Summoning Stone (Non Blocking)",
            action_fn=_dispatch,
            aftercast_ms=0,
        )
    )


def _conset() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not (_hard_mode and _use_conset and _consumables_allowed()):
            return BT.Succeeder('Conset Disabled')
        return BTItems.UseConsumables(
            [(int(model_id), '') for model_id in CONSET_UPKEEPS],
            aftercast_ms=150,
        )

    return BT.Subtree('Use Conset In Thommis Room', _build)


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()
    return BT.Sequence(
        name='Initialize Voltaic Spear BT',
        children=[
            bot.Config.Aggressive(
                multi_account=True,
                auto_loot=_auto_loot,
                resurrection_scroll=True,
                account_isolation=False,
            ),
            BT.SetPlayerStatus(PlayerStatus.Offline, log=True),
            BT.LogMessage('Voltaic Spear BT initialized.', MODULE_NAME),
        ],
    )


def PrepareRun() -> BehaviorTree:
    return BT.Sequence(
        name='Prepare Voltaic Spear Run',
        map_id_or_name=UMBRAL_GROTTO,
        random_travel=True,
        hard_mode=None,
        children=[
            StartupInventoryCheck(),
            BT.CreateParty(hero_ids=[1,14,25,4], multibox_invite=True, timeout_ms=30_000, log=True),
            BT.SetHardMode(_hard_mode, log=True),
            _runtime_restock_node(),
            _runtime_consumable_upkeep_node(False),
            RoutinesBT.Party.SetTitle(int(TitleID.Asuran.value), log=True),
            BT.LogMessage(
                'Party formed and selected supplies prepared.',
                MODULE_NAME,
            ),
        ],
    )


def ExitUmbralGrotto() -> BehaviorTree:
    return BT.MoveAndExitMap(
        UMBRAL_EXIT_PATH,
        target_map_id=VERDANT_CASCADES,
        timeout_ms=45_000,
        log=True,
    )


def StartVerdantCascades() -> BehaviorTree:
    return BT.Sequence(
        name='Start Verdant Cascades',
        children=[
            BT.IsCurrentMap(VERDANT_CASCADES, log=True),
            _start_statistics(),
        ],
    )


def _normalized_agent_name(agent_id: int) -> str:
    name = Agent.GetNameByID(agent_id) or ''
    return ''.join(
        character
        for character in unicodedata.normalize('NFKD', name.casefold())
        if not unicodedata.combining(character)
    )


def _dungeon_enemy_priority(agent_id: int) -> tuple[int, str]:
    # Recheck decoded names, including the plural markers seen in the runtime log.
    name = _normalized_agent_name(agent_id).replace('[s]', '')
    # Hostile summons can have Enemy allegiance, so type checks alone are insufficient.
    if (
        Agent.IsSpirit(agent_id)
        or Agent.GetModelID(agent_id) in _DUNGEON_SPIRIT_MODEL_IDS
        or name.startswith(('esprit ', 'spirit of '))
        or name.endswith(' spirit')
    ):
        return len(_DUNGEON_PRIORITY_ROLE_TERMS) + 1, 'Spirit'
    if Agent.IsMinion(agent_id) or name in ('serviteur squelette', 'bone minion'):
        return len(_DUNGEON_PRIORITY_ROLE_TERMS) + 1, 'Minion'
    for rank, (role, terms) in enumerate(_DUNGEON_PRIORITY_ROLE_TERMS):
        if any(term in name for term in terms):
            return rank, role
    return len(_DUNGEON_PRIORITY_ROLE_TERMS), 'Nearest'


def _dungeon_enemies_in_area(
    point: tuple[float, float],
    radius: float,
) -> list[int]:
    radius_sq = float(radius) ** 2
    enemies: list[int] = []
    for agent_id in AgentArray.GetEnemyArray():
        if not Agent.IsAlive(agent_id):
            continue
        enemy_x, enemy_y = Agent.GetXY(agent_id)
        if (enemy_x - point[0]) ** 2 + (enemy_y - point[1]) ** 2 <= radius_sq:
            enemies.append(agent_id)
    return enemies


def _select_dungeon_clear_target(
    enemies: list[int],
    preferred_agent_id: int = 0,
) -> tuple[int, str] | None:
    if not enemies:
        return None
    player_x, player_y = Player.GetXY()
    candidates: list[tuple[int, int, float, int, str]] = []
    for agent_id in enemies:
        rank, role = _dungeon_enemy_priority(agent_id)
        enemy_x, enemy_y = Agent.GetXY(agent_id)
        distance_sq = (enemy_x - player_x) ** 2 + (enemy_y - player_y) ** 2
        # Preserve focus among equal-priority enemies, even if another is nearer.
        candidates.append((rank, int(agent_id != preferred_agent_id), distance_sq, agent_id, role))
    _, _, _, target_id, role = min(candidates)
    return target_id, role


def _dungeon_priority_clear_enemies(
    point: tuple[float, float],
    radius: float = AGGRO_RADIUS,
    interact_interval_ms: int = 750,
) -> BehaviorTree:
    """Own targeting only while this waypoint's movement has finished."""
    last_target_id = 0
    last_interact_ms = 0
    last_pause_reason = ''

    def _pause_reason(node: _DungeonClearNode) -> str:
        blackboard = node.blackboard
        player_id = Player.GetAgentID()
        if not player_id or not Agent.IsAlive(player_id):
            return 'player_dead'
        if bool(blackboard.get('PAUSE_MOVEMENT', False)):
            return 'external_pause'
        if Agent.IsCasting(player_id):
            return 'casting'
        index, message = GLOBAL_CACHE.ShMem.PreviewNextMessage(Player.GetAccountEmail())
        if (
            index != -1
            and message
            and message.Command == SharedCommandType.PickUpLoot
            and bool(getattr(message, 'Running', False))
        ):
            return 'loot_message_active'
        return ''

    def _clear(node: _DungeonClearNode) -> BehaviorTree.NodeState:
        nonlocal last_target_id, last_interact_ms, last_pause_reason
        blackboard = node.blackboard
        if bool(blackboard.get('USER_INTERRUPT_ACTIVE', False)):
            last_target_id = 0
            last_interact_ms = 0
            last_pause_reason = ''
            return BehaviorTree.NodeState.FAILURE

        pause_reason = _pause_reason(node)
        if pause_reason:
            if pause_reason != last_pause_reason:
                PySystem.Console.Log(
                    MODULE_NAME,
                    f'Dungeon priority clear paused due to {pause_reason}.',
                    PySystem.Console.MessageType.Info,
                )
            last_pause_reason = pause_reason
            return BehaviorTree.NodeState.RUNNING
        last_pause_reason = ''

        enemies = _dungeon_enemies_in_area(point, radius)
        blackboard['clear_area_enemy_count'] = len(enemies)
        blackboard['clear_area_center'] = point
        blackboard['clear_area_radius'] = radius
        blackboard['clear_area_allowed_alive_enemies'] = 0
        selected = _select_dungeon_clear_target(enemies, last_target_id)
        if selected is None:
            last_target_id = 0
            last_interact_ms = 0
            blackboard.pop('clear_area_target_id', None)
            PySystem.Console.Log(
                MODULE_NAME,
                f'Dungeon priority area clear at {point}.',
                PySystem.Console.MessageType.Success,
            )
            return BehaviorTree.NodeState.SUCCESS

        target_id, role = selected
        blackboard['clear_area_target_id'] = target_id
        now_ms = int(time.monotonic() * 1000.0)
        target_changed = target_id != last_target_id
        if not target_changed and now_ms - last_interact_ms < interact_interval_ms:
            return BehaviorTree.NodeState.RUNNING

        targeting = cast(_DungeonTargeting, Player)
        if Player.GetTargetID() != target_id:
            targeting.ChangeTarget(target_id)
        if target_changed:
            targeting.CallTarget(target_id)
            target_name = _normalized_agent_name(target_id) or f'agent {target_id}'
            target_x, target_y = Agent.GetXY(target_id)
            target_distance = ((target_x - point[0]) ** 2 + (target_y - point[1]) ** 2) ** 0.5
            reason = 'initial_target'
            previous_detail = ''
            if last_target_id:
                previous_alive = Agent.IsAlive(last_target_id)
                previous_distance_text = 'n/a'
                if not previous_alive:
                    reason = 'previous_not_alive'
                else:
                    previous_x, previous_y = Agent.GetXY(last_target_id)
                    previous_distance = ((previous_x - point[0]) ** 2 + (previous_y - point[1]) ** 2) ** 0.5
                    previous_distance_text = f'{previous_distance:.0f}'
                    if previous_distance > radius:
                        reason = 'previous_outside_radius'
                    elif last_target_id not in enemies:
                        reason = 'previous_missing_from_enemies'
                    else:
                        reason = 'priority_changed'
                previous_detail = (
                    f', previous_id={last_target_id}, previous_alive={previous_alive}'
                    f', previous_distance={previous_distance_text}'
                )
            PySystem.Console.Log(
                MODULE_NAME,
                f'Dungeon clear target -> {target_name} '
                f'(id={target_id}, model={Agent.GetModelID(target_id)}, role={role}, enemies={len(enemies)}, '
                f'waypoint={point}, distance={target_distance:.0f}/{radius:.0f}, '
                f'reason={reason}{previous_detail}).',
                PySystem.Console.MessageType.Info,
            )
        targeting.Interact(target_id, False)
        last_target_id = target_id
        last_interact_ms = now_ms
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name='Clear Dungeon Enemies With Priority',
            condition_fn=_clear,
        )
    )


def _dungeon_priority_move_and_kill(
    point: PathPoint,
    *,
    clear_area_radius: float = AGGRO_RADIUS,
    pause_on_combat: bool | None = True,
    flag_heroes_to_waypoint: bool = False,
    move_tolerance: float = 175.0,
) -> BehaviorTree:
    """Like Shards' Fendi fight, give the clear phase exclusive target control."""
    center = (float(point.x), float(point.y)) if isinstance(point, Vec2f) else (float(point[0]), float(point[1]))
    return BT.Sequence(
        name='Move And Kill With Dungeon Target Priority',
        children=[
            BT.Move(
                point,
                pause_on_combat=pause_on_combat,
                tolerance=move_tolerance,
                flag_heroes_to_waypoint=flag_heroes_to_waypoint,
                log=False,
            ),
            _dungeon_priority_clear_enemies(center, radius=clear_area_radius),
            BT.Move(
                point,
                pause_on_combat=True,
                tolerance=400.0,
                flag_heroes_to_waypoint=flag_heroes_to_waypoint,
                log=False,
            ),
        ],
    )

def _map_guarded_point(name: str, map_id: int, child: BehaviorTree, skip_if_in_maps: Sequence[int]=()) -> BehaviorTree:
    """Run one point on its map, or accept it when the next level is loaded."""
    branches: list[BehaviorTree] = [BT.Sequence(name=f'{name} - Active Map', children=[BT.IsCurrentMap(map_id=map_id, log=False), child])]

    for later_map_id in skip_if_in_maps:
        branches.append(BT.Sequence(name=f'{name} - Later Map {later_map_id}', children=[BT.IsCurrentMap(map_id=later_map_id, log=False), BT.Succeeder(f'{name}AlreadyPassed')]))

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
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"

        def _build_point(point: PathPoint = point, name: str = name) -> BehaviorTree:
            if map_id == JUSTICIAR_THOMMIS_ROOM:
                # Do not also run the stock clear: it would overwrite our target.
                child = _dungeon_priority_move_and_kill(
                    point,
                    clear_area_radius=Range.Spellcast.value,
                    pause_on_combat=pause_on_combat,
                    flag_heroes_to_waypoint=flag_heroes_to_waypoint,
                    move_tolerance=move_tolerance,
                )
            else:
                child = BT.VanquishNode(
                    [point],
                    name=name,
                    clear_area_radius=Range.Spellcast.value,
                    pause_on_combat=pause_on_combat,
                    flag_heroes_to_waypoint=flag_heroes_to_waypoint,
                    move_tolerance=move_tolerance,
                    log=False,
                )
            return _map_guarded_point(
                name=name,
                map_id=map_id,
                child=child,
                skip_if_in_maps=skip_if_in_maps,
            )

        steps.append((name, _build_point))

    return steps


def EnterSlaversExile() -> BehaviorTree:
    return BT.MoveAndExitMap(
        SLAVERS_PORTAL,
        target_map_id=SLAVERS_EXILE,
        timeout_ms=45_000,
        log=True,
    )


def _movement_point(
    map_id: int,
    point: tuple[float, float],
    name: str,
) -> BehaviorTree:
    return BT.Sequence(
        name=name,
        children=[
            BT.IsCurrentMap(map_id, log=True),
            BT.Move(point, pause_on_combat=False, tolerance=175.0, log=True),
        ],
    )


def EnterThommisRoom() -> BehaviorTree:
    entry = BT.MoveAndExitMap(
        THOMMIS_ROOM_PORTAL,
        target_map_id=JUSTICIAR_THOMMIS_ROOM,
        timeout_ms=45_000,
        log=True,
    )
    return BT.Sequence(
        name='Enter Thommis Room And Resume Consumables',
        children=[
            entry,
            BT.WaitUntilOnExplorable(timeout_ms=30_000),
            _runtime_consumable_upkeep_node(True),
        ],
    )


def StartThommisFight() -> BehaviorTree:
    return BT.Sequence(
        name='Start Thommis Fight',
        children=[
            BT.IsCurrentMap(JUSTICIAR_THOMMIS_ROOM, log=True),
            _start_thommis_statistics(),
            BT.MoveAndDialog(
                THOMMIS_NPC,
                THOMMIS_DIALOG,
                pause_on_combat=False,
                multi_account=False,
                log=True,
            ),
            BT.Wait(1_000),
            _summoning_stone(),
        ],
    )


def OpenAndLootChest() -> BehaviorTree:
    return BT.Sequence(
        name='Open And Loot Thommis Chest',
        children=[
            BT.Move(
                CHEST_POSITION,
                pause_on_combat=True,
                tolerance=150.0,
                ignore_destination_obstacles=True,
                ignore_destination_npcs=False,
                ignore_destination_gadgets=True,
                log=True,
            ),
            BehaviorTree(
                BehaviorTree.WaitUntilNode(
                    name='Wait Until Stopped At Chest',
                    condition_fn=lambda: (
                        BehaviorTree.NodeState.RUNNING
                        if Agent.IsMoving(Player.GetAgentID())
                        else BehaviorTree.NodeState.SUCCESS
                    ),
                    timeout_ms=2_000,
                    throttle_interval_ms=100,
                )
            ),
            BT.Wait(125),
            # Include the final approach; exclude the chest interaction and loot.
            _record_statistics(),
            RoutinesBT.Agents.MoveAndInteractWithGadget(
                gadget_id=THOMMIS_CHEST_GADGET_ID,
                pos=CHEST_POSITION,
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
            BT.Wait(8_000),
            _inventory_spear_statistics_node(after_chest=True),
        ],
    )

def ReturnToUmbralGrotto() -> BehaviorTree:
    return BT.Sequence(
        name="Return To Umbral Grotto",
        children=[
            _runtime_consumable_upkeep_node(False),
            BT.Resign(
                wait_for_map_load=True,
                target_map_name="Umbral Grotto",
                multi_account=True,
            ),
            BT.Wait(2_000),

        ],
    )


def _path_steps(
    prefix: str,
    map_id: int,
    points: list[tuple[float, float]],
    factory: Callable[[int, tuple[float, float], str], BehaviorTree],
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    result: list[tuple[str, Callable[[], BehaviorTree]]] = []
    for index, point in enumerate(points, start=1):
        name = f'{prefix} - Point {index:02d}'
        result.append(
            (
                name,
                lambda map_id=map_id, point=point, name=name: factory(
                    map_id,
                    point,
                    name,
                ),
            )
        )
    return result


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ('Initialize Bot', InitializeBot),
        ('Prepare Run', PrepareRun),
        ('Exit Umbral Grotto', ExitUmbralGrotto),
        ('Start Verdant Cascades', StartVerdantCascades),
        *_vanquish_point_steps("Verdant Cascades", VERDANT_CASCADES, VERDANT_PATH),
        ('Enter Slavers Exile', EnterSlaversExile),
        *_path_steps('Slavers Approach', SLAVERS_EXILE, THOMMIS_ENTRY_PATH, _movement_point),
        ('Enter Thommis Room', EnterThommisRoom),
        ('Start Thommis Fight', StartThommisFight),
        *_vanquish_point_steps('Thommis Part 1', JUSTICIAR_THOMMIS_ROOM, THOMMIS_PATH_1,),
        *_vanquish_point_steps('Thommis Part 2', JUSTICIAR_THOMMIS_ROOM, THOMMIS_PATH_2,),
        ('Open And Loot Chest', OpenAndLootChest),
        ('Return To Umbral Grotto', ReturnToUmbralGrotto),
    ]


def ensure_botting_tree() -> BottingTree:
    global botting_tree

    _load_settings()
    if botting_tree is None:
        Listeners.AutoReturnOnDefeat.Enable()
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name='VoltaicSpearSequence',
            repeat=True,
            multi_account=True,
            isolation_enabled=False,
            pause_on_combat=True,
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
        "A complete multibox BottingTree farm for the Voltaic Spear. The run starts from "
        "Umbral Grotto, crosses Verdant Cascades to Slaver's Exile and clears Justiciar "
        "Thommis' room before opening the final chest and returning for the next run."
    )
    PyImGui.spacing()

    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Automates the complete Umbral Grotto, Verdant Cascades and Thommis route.")
    PyImGui.bullet_text("Uses point-based dungeon clearing with priority handling for key enemy roles.")
    PyImGui.bullet_text(
        "Consets, personal consumables and summoning stones remain disabled during travel and "
        "are enabled only inside the Thommis room."
    )
    PyImGui.bullet_text("Supports multibox party control, synchronized chest handling and configurable Hard Mode.")
    PyImGui.bullet_text(
        "Multibox inventory maintenance can trigger MerchantRules when an active account falls "
        "below the configured thresholds."
    )
    PyImGui.bullet_text(
        "Tracks total, Verdant and Thommis split times plus Voltaic Spear drops for each account."
    )
    PyImGui.spacing()

    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Original Voltaic Spear AutoIt script and route: BubbleTea.")
    PyImGui.bullet_text("BottingTree conversion, multibox integration and adaptations: Sky.")
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
        main_child_dimensions=(430, 390),
        extra_tabs=[
            ('Statistics', _draw_statistics),
            ('Config', _draw_config),
        ],
    )


if __name__ == '__main__':
    main()
