from __future__ import annotations

import os
import time
from collections.abc import Callable

import PySystem

from Py4GWCoreLib import Agent
from Py4GWCoreLib import AgentArray
from Py4GWCoreLib import Effects
from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib import Inventory
from Py4GWCoreLib import Map
from Py4GWCoreLib import Player
from Py4GWCoreLib import Routines
from Py4GWCoreLib import SharedCommandType
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Hero_enums import HeroType
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.py4gwcorelib_src.ActionQueue import ActionQueueManager
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.py4gwcorelib_src.Utils import Utils
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.ApoSource.ApoBottingLib import wrappers as BT


TEXTURE = os.path.join(
    PySystem.Console.get_projects_path(),
    "Assets",
    "Textures",
    "Module_Icons",
    "Ministerial Commendations BT.png",
)
MODULE_ICON = "Assets\\Textures\\Module_Icons\\Ministerial Commendations BT.png"

MODULE_NAME = 'Ministerial Commendations BT'
INI_PATH = 'Widgets/Automation/Bots/Farmers/Trophies/Ministerial Commendations BT'
INI_FILENAME = 'Ministerial_Commendations_BT.ini'

KAINENG_CENTER = 194
A_CHANCE_ENCOUNTER = 861
MISSION_DIALOG = 0x84

# Encounter_ReBuilt.au3 reference builds.
PLAYER_BUILDS_BY_PRIMARY = {
    'Warrior': 'OQojQhV6KT4k9F8E7gUiEY5iwF',
    'Ranger': 'OgEUcDqWV8S4k9F8E7gUi+G5iMH',
    'Monk': 'OwEUAj2S1qS4k9F8E7gUigE5iwF',
    'Necromancer': 'OAFUYCqWVyS4k9F8E7gUizB5iwF',
    'Mesmer': 'OQFUAixS1qS4k9F8E7gUioA5iwF',
    'Elementalist': 'OgFUwi1S1qS4k9F8E7gUitT5iwF',
    'Assassin': 'OwFkQpV63OG0dZfBPxOYDkLTuIcB',
    'Ritualist': 'OAGkQGhLlWpEOZfBPxOIlo0UuIcB',
    'Paragon': 'OQGjgOUcFT4k9F8E7gUiBA5iwF',
    'Dervish': 'OgGlwWrJlWpqFhT2XwTsDSJSglL29B',
}

MINISTERIAL_COMMENDATION = int(ModelID.Ministerial_Commendation.value)
BIRTHDAY_CUPCAKE = int(ModelID.Birthday_Cupcake.value)

# Inventory maintenance mirrors the Shards of Orr thresholds/merchant flow,
# but this script is intentionally single-account only.
ID_KIT_MODEL_IDS = (int(ModelID.Superior_Identification_Kit.value),)
SALVAGE_KIT_MODEL_IDS = (int(ModelID.Superior_Salvage_Kit.value),)
MERCHANT_RULES_WIDGET_NAME = 'MerchantRules'
INVENTORY_PLUS_WIDGET_NAME = 'InventoryPlus'
INVENTORY_MAINTENANCE_RETRY_COUNT = 2
INVENTORY_SNAPSHOT_SETTLE_MS = 2_000
INVENTORY_MERCHANT_TIMEOUT_MS = 240_000

MIKU_LEGACY_AGENT_ID = 58
MIKU_SEARCH_ANCHOR = (-6300.0, -5300.0)

# Exact Encounter_ReBuilt.au3 party positions.
HERO_FIRE_ELE = 1       # Acolyte Sousuke - Starburst
HERO_EARTH_ELE = 2      # Vekk - Stone Sheath
HERO_TRAPPER = 3        # Pyre Fierceshot - Trapper
HERO_PROT_MESMER = 4    # Gwen - Martyr Prot Mesmer
HERO_SOS = 5            # Razah - SoS Resto + Recall
HERO_BIP = 6            # Olias - BiP Resto
HERO_ST = 7             # Xandra - ST Mot

EXPECTED_HERO_IDS = (
    int(HeroType.AcolyteSousuke.value),
    int(HeroType.Vekk.value),
    int(HeroType.PyreFierceshot.value),
    int(HeroType.Gwen.value),
    int(HeroType.Razah.value),
    int(HeroType.Olias.value),
    int(HeroType.Xandra.value),
)

# Numeric behavior values are preserved from the AutoIt:
# 0 Fight, 1 Guard, 2 Avoid.
HERO_BUILDS = (
    (HERO_FIRE_ELE, 'Sousuke', 'OgBDgqyMSlVHR3C8CLg4CKDADA', 0),
    (HERO_EARTH_ELE, 'Vekk', 'OgljkwMopOdVm22oHuK2x14UBA', 0),
    (HERO_TRAPPER, 'Pyre Fierceshot', 'OggjclYsYSNHLHJHKHchYOIHCAA', 0),
    (HERO_PROT_MESMER, 'Gwen', 'OQNDAowvOqkcw0z0NEEcaRBA', 0),
    (HERO_SOS, 'Razah', 'OAejEyiM5QXTYMdOTMSTdiVPciA', 2),
    (HERO_BIP, 'Olias', 'OAhjQoGYIP3BqdVV4JNncDzxJA', 1),
    (HERO_ST, 'Xandra', 'OAmjAyk85QYTWPPOhTOTkTQTfiA', 2),
)

# AutoIt CommandStartingPositions().
STARTING_POSITIONS = (
    (HERO_FIRE_ELE, -6362.0, -4967.0),
    (HERO_EARTH_ELE, -6060.0, -5168.0),
    (HERO_TRAPPER, -6245.0, -5232.0),
    (HERO_PROT_MESMER, -6362.0, -4967.0),
    (HERO_SOS, -5691.0, -5195.0),
    (HERO_BIP, -5606.0, -4747.0),
    (HERO_ST, -5452.0, -4380.0),
)
PLAYER_HERO_SETUP_POSITION = (-6232.0, -5392.0)
PLAYER_TRAP_POSITION = (-6306.0, -5260.0)

# Fixed initial foe IDs used by Encounter_ReBuilt.au3.
INITIAL_FOE_AGENT_IDS = (
    62, 63,
    193, 194, 195, 196, 197, 198, 199, 200,
)

# Journey positions from Encounter_ReBuilt.au3.
AUTOIT_SAFE_SPOT = (-6080.0, -5020.0)
AUTOIT_FIGHT_EXIT = (-4800.0, -3700.0)
AUTOIT_MID_1 = (-4658.0, -757.0)

# Forced stair line between MID_1 and MID_2.
# These points prevent the autopath from cutting beside the staircase.
AUTOIT_STAIR_PATH = (
    (-4761.0, -608.0),
    (-4464.0, -323.0),
    (-3869.0, 240.0),
)

AUTOIT_MID_2 = (-3135.0, 628.0)
AUTOIT_MID_3 = (-2127.0, -1224.0)
AUTOIT_MID_4 = (-878.0, -1854.0)
AUTOIT_STAIRS_APPROACH = (-766.0, -3262.0)
AUTOIT_FARM_POSITION = (-687.0, -3780.0)

_settings = Settings(f'{INI_PATH}/{INI_FILENAME}', 'account')
_settings_loaded = False
_hard_mode = True
_setup_party = True
_load_player_build = True
_use_cupcake = True
_inventory_maintenance_enabled = True
_inventory_min_free_slots = 5
_inventory_min_id_kits = 1
_inventory_min_salvage_kits = 2
_inventory_status_snapshot: dict[str, object] = {}

_STATS_SECTION = 'Statistics'
_statistics_loaded = False
_total_runs = 0
_total_commendations = 0
_total_drop_runs = 0
_session_runs = 0
_session_commendations = 0
_session_drop_runs = 0
_last_run_commendations = 0
_run_start_commendation_count = -1
_statistics_reset_pending = False

initialized = False
botting_tree: BottingTree | None = None
_team_builds_loaded = False

SCRIPT_RESTART_STEP = 'Initialize Bot'
MISSION_RESTART_STEP = 'Enter A Chance Encounter'

def _log(message: str, message_type=PySystem.Console.MessageType.Info) -> None:
    PySystem.Console.Log(MODULE_NAME, message, message_type)


def _load_settings() -> None:
    global _settings_loaded, _hard_mode, _setup_party, _load_player_build, _use_cupcake
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots, _inventory_min_id_kits, _inventory_min_salvage_kits

    if _settings_loaded:
        _load_statistics()
        return

    _hard_mode = _settings.get_bool('Config', 'HardMode', True)
    _setup_party = _settings.get_bool('Config', 'SetupParty', True)
    _load_player_build = _settings.get_bool('Config', 'LoadPlayerBuild', True)
    _use_cupcake = _settings.get_bool('Config', 'UseBirthdayCupcake', True)
    _inventory_maintenance_enabled = _settings.get_bool('Config', 'InventoryMaintenanceEnabled', True)
    _inventory_min_free_slots = max(0, _settings.get_int('Config', 'InventoryMinFreeSlots', 5))
    _inventory_min_id_kits = max(0, _settings.get_int('Config', 'InventoryMinIdKits', 1))
    _inventory_min_salvage_kits = max(0, _settings.get_int('Config', 'InventoryMinSalvageKits', 2))
    _settings_loaded = True
    _load_statistics()


def _save_settings() -> None:
    _settings.set('Config', 'HardMode', _hard_mode)
    _settings.set('Config', 'SetupParty', _setup_party)
    _settings.set('Config', 'LoadPlayerBuild', _load_player_build)
    _settings.set('Config', 'UseBirthdayCupcake', _use_cupcake)
    _settings.set('Config', 'InventoryMaintenanceEnabled', _inventory_maintenance_enabled)
    _settings.set('Config', 'InventoryMinFreeSlots', _inventory_min_free_slots)
    _settings.set('Config', 'InventoryMinIdKits', _inventory_min_id_kits)
    _settings.set('Config', 'InventoryMinSalvageKits', _inventory_min_salvage_kits)


def _draw_config() -> None:
    import PyImGui

    global _hard_mode, _setup_party, _load_player_build, _use_cupcake
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots, _inventory_min_id_kits, _inventory_min_salvage_kits

    _load_settings()
    PyImGui.text('Ministerial Commendations Config')
    PyImGui.separator()
    changed = False

    value = PyImGui.checkbox('Hard Mode (HM)', _hard_mode)
    if value != _hard_mode:
        _hard_mode = value
        changed = True

    value = PyImGui.checkbox('Set up the seven heroes', _setup_party)
    if value != _setup_party:
        _setup_party = value
        changed = True

    value = PyImGui.checkbox('Load the Encounter ReBuilt player build', _load_player_build)
    if value != _load_player_build:
        _load_player_build = value
        changed = True

    value = PyImGui.checkbox('Use Birthday Cupcake', _use_cupcake)
    if value != _use_cupcake:
        _use_cupcake = value
        changed = True

    PyImGui.separator()
    PyImGui.text('Inventory maintenance')

    value = PyImGui.checkbox('Run MerchantRules when inventory is low', _inventory_maintenance_enabled)
    if value != _inventory_maintenance_enabled:
        _inventory_maintenance_enabled = value
        changed = True

    if _inventory_maintenance_enabled:
        value = max(0, int(PyImGui.input_int('Minimum free slots', _inventory_min_free_slots)))
        if value != _inventory_min_free_slots:
            _inventory_min_free_slots = value
            changed = True

        value = max(0, int(PyImGui.input_int('Minimum Superior ID kits (0 = disabled)', _inventory_min_id_kits)))
        if value != _inventory_min_id_kits:
            _inventory_min_id_kits = value
            changed = True

        value = max(0, int(PyImGui.input_int('Minimum Superior salvage kits (0 = disabled)', _inventory_min_salvage_kits)))
        if value != _inventory_min_salvage_kits:
            _inventory_min_salvage_kits = value
            changed = True

        PyImGui.text_wrapped(
            'Single-account inventory maintenance. The Superior ID / Salvage thresholds above '
            'are sent directly to MerchantRules for this execution; the loaded profile still '
            'handles sell, salvage, destroy and storage rules. The temporary kit targets are '
            'not saved in MerchantRules. Equipment Pack is not counted by Inventory.GetInventorySpace().' 
        )

    if changed:
        _save_settings()

    PyImGui.separator()
    PyImGui.text_wrapped(
        'On the first run, the bot prepares the full party in Kaineng Center '
        'and loads every hero build automatically.'
    )
    PyImGui.text('Loaded hero order:')
    for line in (
        '1 Sousuke - Fire Ele / Starburst',
        '2 Vekk - Earth Ele / Stone Sheath',
        '3 Pyre Fierceshot - Trapper',
        '4 Gwen - Martyr Prot Mesmer',
        '5 Razah - SoS Resto + Recall',
        '6 Olias - BiP Resto',
        '7 Xandra - ST',
    ):
        PyImGui.bullet_text(line)



# region Inventory maintenance and statistics


def _load_statistics() -> None:
    global _statistics_loaded
    global _total_runs, _total_commendations, _total_drop_runs

    if _statistics_loaded:
        return

    _total_runs = max(0, _settings.get_int(_STATS_SECTION, 'total_runs', 0))
    _total_commendations = max(0, _settings.get_int(_STATS_SECTION, 'total_commendations', 0))
    _total_drop_runs = max(0, _settings.get_int(_STATS_SECTION, 'total_drop_runs', 0))
    _statistics_loaded = True


def _save_statistics() -> None:
    _settings.set(_STATS_SECTION, 'total_runs', _total_runs)
    _settings.set(_STATS_SECTION, 'total_commendations', _total_commendations)
    _settings.set(_STATS_SECTION, 'total_drop_runs', _total_drop_runs)


def _statistics_action_node(name: str, action: Callable[[], None]) -> BehaviorTree:
    def _run(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            action()
        except Exception as exc:
            _log(
                f'[Statistics] {name} failed: {exc}',
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


def _commendation_inventory_count() -> int:
    return int(GLOBAL_CACHE.Inventory.GetModelCount(MINISTERIAL_COMMENDATION))


def _mark_run_statistics_start_node() -> BehaviorTree:
    def _mark() -> None:
        global _run_start_commendation_count
        _load_statistics()
        _run_start_commendation_count = _commendation_inventory_count()
        _log(
            f'[Statistics] Run snapshot: {_run_start_commendation_count} Ministerial Commendation(s) in inventory.'
        )

    return _statistics_action_node('Snapshot Commendations At Run Start', _mark)


def _record_run_statistics_node() -> BehaviorTree:
    def _record() -> None:
        global _total_runs, _total_commendations, _total_drop_runs
        global _session_runs, _session_commendations, _session_drop_runs
        global _last_run_commendations, _run_start_commendation_count

        _load_statistics()
        after_count = _commendation_inventory_count()
        before_count = int(_run_start_commendation_count)
        gained = max(0, after_count - before_count) if before_count >= 0 else 0

        _last_run_commendations = gained
        _total_runs += 1
        _session_runs += 1
        _total_commendations += gained
        _session_commendations += gained
        if gained > 0:
            _total_drop_runs += 1
            _session_drop_runs += 1

        _run_start_commendation_count = -1
        _save_statistics()

        drop_rate = (_total_drop_runs / _total_runs * 100.0) if _total_runs > 0 else 0.0
        _log(
            f'[Statistics] Run complete - commendations={gained} | '
            f'total={_total_commendations} | drop rate={drop_rate:.1f}%',
            PySystem.Console.MessageType.Success,
        )

    return _statistics_action_node('Record Ministerial Commendation Run', _record)


def _reset_all_time_statistics() -> None:
    global _total_runs, _total_commendations, _total_drop_runs
    _total_runs = 0
    _total_commendations = 0
    _total_drop_runs = 0
    _save_statistics()
    _log('[Statistics] All-time commendation statistics reset.', PySystem.Console.MessageType.Success)


def _draw_statistics() -> None:
    import PyImGui
    from Py4GWCoreLib import Color

    global _statistics_reset_pending

    _load_statistics()

    gold = Color(255, 210, 80, 255).to_tuple_normalized()
    cyan = Color(80, 210, 255, 255).to_tuple_normalized()

    def _drop_rate(runs: int, successful_runs: int) -> str:
        return f'{successful_runs / runs * 100.0:.1f}%' if runs > 0 else '-'

    def _average(runs: int, commendations: int) -> str:
        return f'{commendations / runs:.2f}' if runs > 0 else '-'

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

    PyImGui.text_colored('Ministerial Commendations Statistics', gold)
    PyImGui.separator()
    PyImGui.spacing()

    PyImGui.text_colored('Session Overview', cyan)
    if PyImGui.begin_table('##ministerial_session_stats', 5, table_flags):
        labels = ('Runs', 'Last Run', 'Citations', 'Avg / Run', 'Drop Rate')
        for label in labels:
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
        _header_row(labels)
        values = (
            _session_runs,
            _last_run_commendations,
            _session_commendations,
            _average(_session_runs, _session_commendations),
            _drop_rate(_session_runs, _session_drop_runs),
        )
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_colored('All-Time Overview', cyan)
    if PyImGui.begin_table('##ministerial_total_stats', 5, table_flags):
        labels = ('Runs', 'Citations', 'Drop Runs', 'Avg / Run', 'Drop Rate')
        for label in labels:
            PyImGui.table_setup_column(label, PyImGui.TableColumnFlags.WidthFixed, column_width)
        _header_row(labels)
        values = (
            _total_runs,
            _total_commendations,
            _total_drop_runs,
            _average(_total_runs, _total_commendations),
            _drop_rate(_total_runs, _total_drop_runs),
        )
        PyImGui.table_next_row(0, row_height)
        for index, value in enumerate(values):
            PyImGui.table_set_column_index(index)
            PyImGui.text(str(value))
        PyImGui.end_table()

    PyImGui.spacing()
    PyImGui.text_wrapped('Drop Rate = percentage of completed runs that produced at least one Ministerial Commendation.')
    PyImGui.spacing()

    if not _statistics_reset_pending:
        if PyImGui.button('Reset All-Time Statistics'):
            _statistics_reset_pending = True
    else:
        PyImGui.text_colored('Reset all-time commendation statistics?', gold)
        if PyImGui.button('Confirm Reset'):
            _reset_all_time_statistics()
            _statistics_reset_pending = False
        PyImGui.same_line(0.0, 8.0)
        if PyImGui.button('Cancel'):
            _statistics_reset_pending = False


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


def _refresh_local_inventory_status_node(name: str) -> BehaviorTree:
    def _refresh(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _inventory_status_snapshot
        label = str(Player.GetName() or '').strip() or 'Local account'
        try:
            occupied, capacity, id_kits, salvage_kits = _local_inventory_state()
            available = capacity > 0 and 0 <= occupied <= capacity
        except Exception as exc:
            _log(f'[Inventory] Local inventory query failed: {exc}', PySystem.Console.MessageType.Error)
            occupied = capacity = id_kits = salvage_kits = -1
            available = False

        free_slots = max(0, capacity - occupied) if available else 0
        issues: list[str] = []
        if not available:
            issues.append('inventory query unavailable')
        else:
            if _inventory_min_free_slots > 0 and free_slots < _inventory_min_free_slots:
                issues.append(f'free slots {free_slots}/{_inventory_min_free_slots}')
            if _inventory_min_id_kits > 0 and id_kits < _inventory_min_id_kits:
                issues.append(f'Superior ID kits {id_kits}/{_inventory_min_id_kits}')
            if _inventory_min_salvage_kits > 0 and salvage_kits < _inventory_min_salvage_kits:
                issues.append(f'Superior salvage kits {salvage_kits}/{_inventory_min_salvage_kits}')

        _inventory_status_snapshot = {
            'label': label,
            'available': available,
            'occupied': occupied,
            'capacity': capacity,
            'free_slots': free_slots,
            'id_kits': id_kits,
            'salvage_kits': salvage_kits,
            'issues': issues,
        }

        result = 'MAINTENANCE' if issues else 'OK'
        if available:
            _log(
                f'[Inventory] {label}: free={free_slots}/{capacity}, occupied={occupied}, '
                f'Superior ID kits={id_kits}, Superior salvage kits={salvage_kits} -> {result}',
                PySystem.Console.MessageType.Warning if issues else PySystem.Console.MessageType.Info,
            )
        else:
            _log(
                f'[Inventory] {label}: local inventory query unavailable -> {result}',
                PySystem.Console.MessageType.Warning,
            )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_refresh,
            aftercast_ms=0,
        )
    )


def _inventory_maintenance_issues() -> list[str]:
    return list(_inventory_status_snapshot.get('issues', []))


def _inventory_is_healthy_node(name: str, *, log_success: bool = True) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if not _inventory_status_snapshot:
            _log(
                'Inventory maintenance required - no local inventory snapshot is available.',
                PySystem.Console.MessageType.Warning,
            )
            return BehaviorTree.NodeState.FAILURE

        issues = _inventory_maintenance_issues()
        if issues:
            _log(
                'Inventory maintenance required - ' + ', '.join(issues),
                PySystem.Console.MessageType.Warning,
            )
            return BehaviorTree.NodeState.FAILURE

        if log_success:
            _log('Inventory check passed on the local account.', PySystem.Console.MessageType.Success)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ConditionNode(name=name, condition_fn=_check))


def _inventory_maintenance_trigger_node() -> BehaviorTree:
    def _log_trigger(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        issues = _inventory_maintenance_issues()
        trigger_text = ', '.join(issues) if issues else 'inventory verification'
        _log(
            f'[Inventory] Maintenance triggered by: {trigger_text}. MerchantRules will run on the local account only.',
            PySystem.Console.MessageType.Warning,
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Log Local Inventory Maintenance Trigger',
            action_fn=_log_trigger,
            aftercast_ms=0,
        )
    )


def _local_recipient_emails() -> list[str]:
    email = str(Player.GetAccountEmail() or '').strip()
    return [email] if email else []


def _send_widget_state(widget_name: str, *, enabled: bool, refs_key: str) -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        recipients = _local_recipient_emails()
        if not recipients:
            return BehaviorTree(
                BehaviorTree.FailerNode(name=f'No Local Recipient For {widget_name}')
            )

        return BTShared.SendAndWait(
            command=SharedCommandType.EnableWidget if enabled else SharedCommandType.DisableWidget,
            extra_data=(widget_name, '', '', ''),
            recipients=recipients,
            include_self=True,
            refs_blackboard_key=refs_key,
            timeout_ms=20_000,
            poll_interval_ms=100,
            log=True,
        )

    return BT.Subtree(
        name=('Enable ' if enabled else 'Disable ') + widget_name + ' On Local Account',
        subtree_fn=_build,
    )


def _set_local_auto_inventory_handler(enabled: bool) -> BehaviorTree:
    def _set(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if botting_tree is None:
            return BehaviorTree.NodeState.SUCCESS

        fn = getattr(botting_tree, 'SetAutoInventoryHandlerEnabled', None)
        if not callable(fn):
            return BehaviorTree.NodeState.SUCCESS

        try:
            fn(enabled)
        except Exception:
            pass
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Enable Local Auto Inventory Handler' if enabled else 'Disable Local Auto Inventory Handler',
            action_fn=_set,
            aftercast_ms=0,
        )
    )


def _wait_for_local_inventory_health_after_merchant(
    name: str,
    *,
    timeout_ms: int = INVENTORY_MERCHANT_TIMEOUT_MS,
) -> BehaviorTree:
    """Wait for MerchantRules' asynchronous execution to satisfy the real local thresholds."""

    state = {'last_log': 0.0, 'success_logged': False}

    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _inventory_status_snapshot

        try:
            occupied, capacity, id_kits, salvage_kits = _local_inventory_state()
            available = capacity > 0 and 0 <= occupied <= capacity
        except Exception:
            occupied = capacity = id_kits = salvage_kits = -1
            available = False

        free_slots = max(0, capacity - occupied) if available else 0
        issues: list[str] = []
        if not available:
            issues.append('inventory query unavailable')
        else:
            if _inventory_min_free_slots > 0 and free_slots < _inventory_min_free_slots:
                issues.append(f'free slots {free_slots}/{_inventory_min_free_slots}')
            if _inventory_min_id_kits > 0 and id_kits < _inventory_min_id_kits:
                issues.append(f'Superior ID kits {id_kits}/{_inventory_min_id_kits}')
            if _inventory_min_salvage_kits > 0 and salvage_kits < _inventory_min_salvage_kits:
                issues.append(f'Superior salvage kits {salvage_kits}/{_inventory_min_salvage_kits}')

        _inventory_status_snapshot = {
            'label': str(Player.GetName() or '').strip() or 'Local account',
            'available': available,
            'occupied': occupied,
            'capacity': capacity,
            'free_slots': free_slots,
            'id_kits': id_kits,
            'salvage_kits': salvage_kits,
            'issues': issues,
        }

        if not issues:
            if not bool(state['success_logged']):
                state['success_logged'] = True
                _log(
                    f'[Inventory] MerchantRules thresholds reached: free={free_slots}/{capacity}, '
                    f'Superior ID kits={id_kits}, Superior salvage kits={salvage_kits}.',
                    PySystem.Console.MessageType.Success,
                )
            return BehaviorTree.NodeState.SUCCESS

        now = time.monotonic()
        if now - float(state['last_log']) >= 5.0:
            state['last_log'] = now
            _log(
                '[Inventory] Waiting for MerchantRules to finish: ' + ', '.join(issues),
                PySystem.Console.MessageType.Info,
            )
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name=name,
            condition_fn=_check,
            throttle_interval_ms=500,
            timeout_ms=timeout_ms,
        )
    )


def _restore_inventoryplus_after_merchant(attempt_key: str) -> BehaviorTree:
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
    """Encode this bot's desired carried Merchant Stock targets for MerchantRules."""
    targets: list[str] = []
    if _inventory_min_id_kits > 0 and ID_KIT_MODEL_IDS:
        targets.append(f"{int(ID_KIT_MODEL_IDS[0])}:{int(_inventory_min_id_kits)}")
    if _inventory_min_salvage_kits > 0 and SALVAGE_KIT_MODEL_IDS:
        targets.append(f"{int(SALVAGE_KIT_MODEL_IDS[0])}:{int(_inventory_min_salvage_kits)}")
    return "stock:" + ",".join(targets)


def _run_merchant_rules(attempt_key: str) -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        recipients = _local_recipient_emails()
        if not recipients:
            _log(
                '[Inventory] MerchantRules aborted: local account email is unavailable.',
                PySystem.Console.MessageType.Error,
            )
            return BehaviorTree(BehaviorTree.FailerNode(name='No Local MerchantRules Recipient'))

        request_id = f'ministerial_inventory_{attempt_key}_{int(time.monotonic() * 1000)}'
        _log('[Inventory] Dispatching MerchantRules to the local account.')
        execute = BTShared.SendAndWait(
            command=SharedCommandType.MerchantRules,
            params=(3.0, 0.0, 0.0, 0.0),
            extra_data=(request_id, _merchant_stock_request_spec(), '0', '0'),
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
                        _wait_for_local_inventory_health_after_merchant(
                            name='Wait For MerchantRules Inventory Result',
                        ),
                        _restore_inventoryplus_after_merchant(attempt_key),
                    ],
                ),
                BT.Sequence(
                    name='Restore InventoryPlus After MerchantRules Failure',
                    children=[
                        _restore_inventoryplus_after_merchant(f'{attempt_key}_failure'),
                        BehaviorTree(BehaviorTree.FailerNode(name='Propagate MerchantRules Failure')),
                    ],
                ),
            ],
        )

    return BT.Subtree(name='Run MerchantRules On Local Account', subtree_fn=_build)


def _inventory_maintenance_attempt(attempt_number: int) -> BehaviorTree:
    attempt_key = f'inventory_attempt_{attempt_number}'
    return BT.Sequence(
        name=f'Inventory Maintenance Attempt {attempt_number}',
        children=[
            BT.LogMessage(
                message=(
                    f'Inventory maintenance attempt {attempt_number}/'
                    f'{INVENTORY_MAINTENANCE_RETRY_COUNT} in Kaineng Center.'
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
            _refresh_local_inventory_status_node(
                name=f'Refresh Local Inventory After Attempt {attempt_number}'
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
            issues = _inventory_maintenance_issues()
            issue_text = ', '.join(issues) if issues else 'unknown verification error'
            _log(
                'Inventory maintenance failed twice. The bot was paused safely. '
                f'Remaining issue(s): {issue_text}',
                PySystem.Console.MessageType.Error,
            )

            if botting_tree is not None:
                fn = getattr(botting_tree, 'SetAutoInventoryHandlerEnabled', None)
                if callable(fn):
                    try:
                        fn(True)
                    except Exception:
                        pass

            sender_email = str(Player.GetAccountEmail() or '').strip()
            if sender_email:
                try:
                    GLOBAL_CACHE.ShMem.SendMessage(
                        sender_email,
                        sender_email,
                        SharedCommandType.EnableWidget,
                        (0.0, 0.0, 0.0, 0.0),
                        (INVENTORY_PLUS_WIDGET_NAME, '', '', ''),
                    )
                except Exception:
                    pass

            if botting_tree is not None:
                fn = getattr(botting_tree, 'Pause', None)
                if callable(fn):
                    try:
                        fn(True)
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

    maintenance_attempts = [
        _inventory_maintenance_attempt(attempt_number)
        for attempt_number in range(1, INVENTORY_MAINTENANCE_RETRY_COUNT + 1)
    ]
    maintenance_attempts.append(_stop_for_inventory_failure_node())

    enabled_flow = BT.Sequence(
        name='Enabled Inventory Check And Maintenance',
        children=[
            _refresh_local_inventory_status_node('Query Local Inventory State'),
            BT.Selector(
                name='Check Inventory Thresholds',
                children=[
                    _inventory_is_healthy_node(
                        'Inventory Thresholds Already Satisfied',
                        log_success=True,
                    ),
                    BT.Sequence(
                        name='Run Local Inventory Maintenance',
                        children=[
                            _inventory_maintenance_trigger_node(),
                            BT.IsCurrentMap(map_id=KAINENG_CENTER, log=True),
                            BT.LeaveParty(),
                            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
                            BT.Selector(
                                name='Retry Inventory Maintenance In Kaineng Center',
                                children=maintenance_attempts,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    return BT.Selector(
        name='Inventory Check And Maintenance',
        children=[disabled, enabled_flow],
    )


def StartupInventoryCheck() -> BehaviorTree:
    return BT.Selector(
        name='Startup Inventory Check',
        children=[
            BT.Sequence(
                name='Check Inventory Before Leaving Kaineng Center',
                children=[
                    BT.IsCurrentMap(map_id=KAINENG_CENTER, log=False),
                    InventoryCheckAndMaintenance(),
                ],
            ),
            BT.Succeeder('Skip Startup Inventory Check Outside Kaineng Center'),
        ],
    )


# endregion

def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return float(Utils.Distance(a, b))


def _enemy_ids_near(position: tuple[float, float], radius: float) -> list[int]:
    return [
        agent_id
        for agent_id in AgentArray.GetEnemyArray()
        if Agent.IsLiving(agent_id)
        and not Agent.IsDead(agent_id)
        and _distance(Agent.GetXY(agent_id), position) <= radius
    ]


def _nearest_enemy(position: tuple[float, float], radius: float | None = None) -> int:
    enemies = [
        agent_id
        for agent_id in AgentArray.GetEnemyArray()
        if Agent.IsLiving(agent_id) and not Agent.IsDead(agent_id)
    ]
    if radius is not None:
        enemies = [agent_id for agent_id in enemies if _distance(Agent.GetXY(agent_id), position) <= radius]
    if not enemies:
        return 0
    return min(enemies, key=lambda agent_id: _distance(Agent.GetXY(agent_id), position))


def _initial_foes_alive() -> list[int]:
    """Return the living members of the AutoIt reference initial foe set."""
    result: list[int] = []
    for agent_id in INITIAL_FOE_AGENT_IDS:
        try:
            if (
                Agent.IsValid(agent_id)
                and Agent.IsLiving(agent_id)
                and not Agent.IsDead(agent_id)
            ):
                result.append(int(agent_id))
        except Exception:
            continue
    return result


def _wait_for_enemy_presence_or_timeout(
    name: str,
    *,
    radius: float = 2500.0,
    timeout_ms: int = 7_500,
) -> BehaviorTree:
    """AutoIt journey gate: continue on enemy arrival or after its short timeout."""

    def _condition() -> BehaviorTree.NodeState:
        if _mission_failed():
            return BehaviorTree.NodeState.FAILURE
        if _enemy_ids_near(Player.GetXY(), radius):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    wait = BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name=name,
            condition_fn=_condition,
            throttle_interval_ms=250,
            timeout_ms=timeout_ms,
        )
    )
    return BT.Selector(
        name=name,
        children=[
            wait,
            _continue_after_wait_timeout(
                name,
                f'{name} timed out after {timeout_ms}ms; continuing like the AutoIt route.',
            ),
        ],
    )


def WaitForMikuAtJourneyExit() -> BehaviorTree:
    """Wait until Miku reaches the AutoIt fight-exit area."""

    def _miku_arrived() -> BehaviorTree.NodeState:
        if _mission_failed():
            return BehaviorTree.NodeState.FAILURE

        miku_id = int(_resolve_miku_agent_id() or 0)
        if miku_id <= 0 or Agent.IsDead(miku_id):
            return BehaviorTree.NodeState.RUNNING

        if _distance(Agent.GetXY(miku_id), AUTOIT_FIGHT_EXIT) <= 2500.0:
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name='Wait For Miku At Journey Exit',
            condition_fn=_miku_arrived,
            throttle_interval_ms=250,
            timeout_ms=40_000,
        )
    )


def _party_agent_ids() -> set[int]:
    agent_ids = {int(Player.GetAgentID() or 0)}
    hero_count = int(GLOBAL_CACHE.Party.GetHeroCount() or 0)
    for position in range(1, hero_count + 1):
        agent_ids.add(int(GLOBAL_CACHE.Party.Heroes.GetHeroAgentIDByPartyPosition(position) or 0))
    agent_ids.discard(0)
    return agent_ids


def _resolve_miku_agent_id() -> int:
    if Agent.IsValid(MIKU_LEGACY_AGENT_ID) and Agent.IsLiving(MIKU_LEGACY_AGENT_ID):
        allegiance, _ = Agent.GetAllegiance(MIKU_LEGACY_AGENT_ID)
        if allegiance != 3:
            return MIKU_LEGACY_AGENT_ID

    party_ids = _party_agent_ids()
    candidates = [
        agent_id
        for agent_id in AgentArray.GetAllyArray()
        if agent_id not in party_ids
        and Agent.IsLiving(agent_id)
        and _distance(Agent.GetXY(agent_id), MIKU_SEARCH_ANCHOR) <= Range.SafeCompass.value
    ]
    if not candidates:
        return 0
    return min(candidates, key=lambda agent_id: _distance(Agent.GetXY(agent_id), MIKU_SEARCH_ANCHOR))


def _miku_or_player() -> int:
    return _resolve_miku_agent_id() or int(Player.GetAgentID() or 0)


def _mission_failed() -> bool:
    player_id = int(Player.GetAgentID() or 0)
    if player_id == 0 or Agent.IsDead(player_id):
        return True
    miku_id = _resolve_miku_agent_id()
    return bool(miku_id and Agent.IsDead(miku_id))


def _is_mission_planner_step(step_name: str) -> bool:
    return bool(
        step_name == MISSION_RESTART_STEP
        or step_name in {
            'Place Player And Heroes',
            'Prepare First Fight',
            'Fight Initial Group',
            'Finish Initial Fight',
            'Run To Stairs',
            'Prepare Stairs Defense',
            'Wait For Purity Ball',
            'Spike Ministry Of Purity',
            'Loot And Return',
        }
        or step_name.startswith('Run To Kill Spot - Point ')
    )


def MissionRestartAnchorService() -> BehaviorTree:
    """Leave a failed mission and choose the correct restart anchor in Kaineng."""

    state = {
        'returning_to_outpost': False,
        'last_return_ms': 0.0,
        'mission_ready_since_ms': 0.0,
        'restart_step': MISSION_RESTART_STEP,
    }

    def _select_restart(node: BehaviorTree.Node, step_name: str) -> None:
        node.blackboard['current_step_name'] = step_name
        node.blackboard['last_active_planner_step_name'] = step_name

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        # A Chance Encounter has no shrine revival. The generic BT service
        # otherwise waits forever in the dead mission instance.
        node.blackboard['party_wipe_recovery_suppressed'] = True

        current_step = str(node.blackboard.get('current_step_name', '') or '')
        requested_step = str(node.blackboard.get('restart_step_name_request', '') or '')
        current_map_id = int(Map.GetMapID() or 0)
        in_mission_instance = bool(
            Map.IsMapReady() and current_map_id == A_CHANCE_ENCOUNTER
        )
        in_mission = in_mission_instance or _is_mission_planner_step(current_step)

        # Normal planner failures inside the mission restart from the mission entry.
        # A player death is handled separately below and restarts the whole script.
        if (
            in_mission
            and requested_step
            and requested_step not in (MISSION_RESTART_STEP, SCRIPT_RESTART_STEP)
        ):
            _log(
                f"Mission step '{requested_step}' failed; restarting from '{MISSION_RESTART_STEP}'.",
                PySystem.Console.MessageType.Warning,
            )
            node.blackboard['restart_step_name_request'] = MISSION_RESTART_STEP
            node.blackboard['PLANNER_STATUS'] = f'PLANNER: Restarting {MISSION_RESTART_STEP}'

        # During the map transition into A Chance Encounter, party shared-memory
        # can briefly report wiped/defeated before the mission party is fully
        # populated. Do not evaluate death/restart conditions until map 861 has
        # remained ready for a short stabilization window.
        now_ms = time.monotonic() * 1000.0

        if in_mission_instance:
            if state['mission_ready_since_ms'] <= 0.0:
                state['mission_ready_since_ms'] = now_ms
        else:
            state['mission_ready_since_ms'] = 0.0

        mission_stable = bool(
            in_mission_instance
            and state['mission_ready_since_ms'] > 0.0
            and now_ms - state['mission_ready_since_ms'] >= 3_000.0
        )

        party_wiped = False
        party_defeated = False
        player_dead = False
        mission_failed = False

        if mission_stable:
            party_wiped = bool(Routines.Checks.Party.IsPartyWiped())
            party_defeated = bool(GLOBAL_CACHE.Party.IsPartyDefeated())
            player_dead = bool(Routines.Checks.Player.IsDead())
            mission_failed = bool(_mission_failed())

        if mission_stable and (party_wiped or party_defeated or mission_failed):
            # Player death is special: restart from the very first planner step.
            restart_step = SCRIPT_RESTART_STEP if player_dead else MISSION_RESTART_STEP

            if not state['returning_to_outpost']:
                ActionQueueManager().ResetAllQueues()
                if player_dead:
                    _log(
                        'Player death detected; returning to Kaineng Center and '
                        f"restarting the script from '{SCRIPT_RESTART_STEP}'.",
                        PySystem.Console.MessageType.Warning,
                    )
                else:
                    _log(
                        'Mission failure detected '
                        f'(party_wiped={party_wiped}, '
                        f'party_defeated={party_defeated}, '
                        f'mission_failed={mission_failed}); '
                        'returning to Kaineng Center before '
                        f"restarting '{MISSION_RESTART_STEP}'.",
                        PySystem.Console.MessageType.Warning,
                    )

            state['returning_to_outpost'] = True
            state['restart_step'] = restart_step
            _select_restart(node, restart_step)

        if not state['returning_to_outpost']:
            return BehaviorTree.NodeState.RUNNING

        if Map.IsMapReady() and Map.IsOutpost():
            restart_step = str(state['restart_step'] or MISSION_RESTART_STEP)
            _select_restart(node, restart_step)
            node.blackboard['restart_step_name_request'] = restart_step
            node.blackboard['PLANNER_STATUS'] = f'PLANNER: Restarting {restart_step}'

            state['returning_to_outpost'] = False
            state['last_return_ms'] = 0.0
            state['mission_ready_since_ms'] = 0.0
            state['restart_step'] = MISSION_RESTART_STEP

            _log(
                f"Outpost loaded; restarting '{restart_step}'.",
                PySystem.Console.MessageType.Success,
            )
            return BehaviorTree.NodeState.RUNNING

        if Map.IsMapReady() and current_map_id == A_CHANCE_ENCOUNTER:
            now_ms = time.monotonic() * 1000.0
            if now_ms - state['last_return_ms'] >= 1_000.0:
                GLOBAL_CACHE.Party.ReturnToOutpost()
                state['last_return_ms'] = now_ms

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Mission Restart Anchor',
            action_fn=_tick,
            aftercast_ms=0,
        )
    )


def _skill_ready(slot: int) -> bool:
    try:
        skill_data = GLOBAL_CACHE.SkillBar.GetSkillData(slot)
        return bool(skill_data is not None and int(getattr(skill_data, 'recharge', 0) or 0) == 0)
    except Exception:
        return False


def _skill_adrenaline(slot: int) -> int:
    try:
        skill_data = GLOBAL_CACHE.SkillBar.GetSkillData(slot)
        return int(getattr(skill_data, 'adrenaline_a', 0) or 0) if skill_data is not None else 0
    except Exception:
        return 0


def _has_player_effect_for_slot(slot: int) -> bool:
    try:
        skill_id = int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) or 0)
        return bool(skill_id and GLOBAL_CACHE.Effects.HasEffect(Player.GetAgentID(), skill_id))
    except Exception:
        return False


def _cast_player_skill(slot: int, target_id: int = 0) -> bool:
    if not _skill_ready(slot):
        return False
    GLOBAL_CACHE.SkillBar.UseSkill(slot, int(target_id or 0), aftercast_delay=0)
    return True


def _hero_agent_id(hero_position: int) -> int:
    return int(GLOBAL_CACHE.Party.Heroes.GetHeroAgentIDByPartyPosition(hero_position) or 0)


def _cast_hero_skill(hero_position: int, slot: int, target_id: int = 0) -> bool:
    """
    Manually trigger one hero skill through the dedicated Skillbar API.

    ``HeroUseSkill`` expects the hero's party position (1-7), not the hero
    agent id. This script consistently uses the hero party position (1-7).
    """
    hero_agent_id = _hero_agent_id(hero_position)
    if hero_agent_id == 0 or Agent.IsDead(hero_agent_id):
        return False
    if slot < 1 or slot > 8:
        return False

    GLOBAL_CACHE.SkillBar.HeroUseSkill(
        int(target_id or 0),
        int(slot),
        int(hero_position),
    )
    return True


def _hero_skill_id(hero_position: int, slot: int) -> int:
    """Return the skill id currently loaded in one hero slot."""
    try:
        skillbar = GLOBAL_CACHE.SkillBar.GetHeroSkillbar(hero_position)
        if slot < 1 or slot > len(skillbar):
            return 0
        skill_data = skillbar[slot - 1]
        return int(getattr(getattr(skill_data, 'id', None), 'id', 0) or 0)
    except Exception:
        return 0


def _drop_hero_buff_for_skill_node(
    hero_position: int,
    slot: int,
    *,
    name: str,
) -> BehaviorTree:
    """
    Drop a maintained enchantment/buff owned by a hero.

    This mirrors AutoIt's Effect_DropBond(...).  DropBuff requires the runtime
    buff id, not the skill id, so resolve the buff on the hero first.
    """

    def _drop() -> BehaviorTree.NodeState:
        hero_agent_id = _hero_agent_id(hero_position)
        skill_id = _hero_skill_id(hero_position, slot)

        if hero_agent_id <= 0 or skill_id <= 0:
            _log(
                f'{name}: hero/skill unavailable; nothing to drop.',
                PySystem.Console.MessageType.Warning,
            )
            return BehaviorTree.NodeState.SUCCESS

        try:
            for buff in GLOBAL_CACHE.Effects.GetBuffs(hero_agent_id):
                if int(getattr(buff, 'skill_id', 0) or 0) != skill_id:
                    continue

                buff_id = int(getattr(buff, 'buff_id', 0) or 0)
                if buff_id <= 0:
                    continue

                Effects.get_instance(hero_agent_id).DropBuff(buff_id)
                _log(
                    f'{name}: dropped hero {hero_position} buff '
                    f'(skill_id={skill_id}, buff_id={buff_id}).'
                )
                return BehaviorTree.NodeState.SUCCESS
        except Exception as exc:
            _log(
                f'{name}: failed to drop hero buff: {exc}',
                PySystem.Console.MessageType.Warning,
            )
            return BehaviorTree.NodeState.SUCCESS

        _log(f'{name}: Recall buff was not active; continuing.')
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_drop,
            aftercast_ms=250,
        )
    )


def _wait_for_heroes_out_of_loot_range(timeout_ms: int = 20_000) -> BehaviorTree:
    hero_names = {
        HERO_FIRE_ELE: 'Sousuke',
        HERO_EARTH_ELE: 'Vekk',
        HERO_TRAPPER: 'Pyre',
        HERO_PROT_MESMER: 'Gwen',
        HERO_SOS: 'Razah',
        HERO_BIP: 'Olias',
        HERO_ST: 'Xandra',
    }

    def _visible_heroes() -> list[str]:
        player_xy = Player.GetXY()
        visible: list[str] = []
        for hero_position, hero_name in hero_names.items():
            hero_agent_id = _hero_agent_id(hero_position)
            if hero_agent_id <= 0 or Agent.IsDead(hero_agent_id):
                continue
            if _distance(Agent.GetXY(hero_agent_id), player_xy) <= Range.Compass.value:
                visible.append(hero_name)
        return visible

    def _all_out() -> BehaviorTree.NodeState:
        if _mission_failed():
            return BehaviorTree.NodeState.FAILURE
        return (
            BehaviorTree.NodeState.SUCCESS
            if not _visible_heroes()
            else BehaviorTree.NodeState.RUNNING
        )

    wait = BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name='Wait For Heroes Outside Loot Range',
            condition_fn=_all_out,
            throttle_interval_ms=250,
            timeout_ms=timeout_ms,
        )
    )

    def _timeout_fallback(_node: BehaviorTree.Node) -> BehaviorTree:
        visible = ', '.join(_visible_heroes()) or 'none'
        return BT.Sequence(
            name='Loot Separation Timeout Fallback',
            children=[
                BT.LogMessage(
                    f'Loot separation timed out; heroes still inside Compass: {visible}.',
                    MODULE_NAME,
                ),
                BT.Succeeder('Loot Separation Timeout Accepted'),
            ],
        )

    return BT.Selector(
        name='Wait For Loot Separation',
        children=[
            wait,
            BT.Subtree('Loot Separation Timeout Router', _timeout_fallback),
        ],
    )


def _hero_skill_ready(hero_position: int, slot: int) -> bool:
    try:
        skillbar = GLOBAL_CACHE.SkillBar.GetHeroSkillbar(hero_position)
        if slot < 1 or slot > len(skillbar):
            return False
        skill_data = skillbar[slot - 1]
        skill_id = int(getattr(getattr(skill_data, 'id', None), 'id', 0) or 0)
        recharge = getattr(skill_data, 'get_recharge', 0)
        if callable(recharge):
            recharge = recharge()
        if isinstance(recharge, (int, float, str)):
            try:
                recharge = float(recharge)
            except (TypeError, ValueError):
                recharge = 0.0
        else:
            recharge = 0.0
        return bool(skill_id and recharge <= 0.0)
    except Exception:
        return False


def _hero_skill_node(
    hero_position: int,
    slot: int,
    target: int | Callable[[], int] = 0,
    *,
    condition: Callable[[], bool] | None = None,
    aftercast_ms: int = 100,
    name: str | None = None,
) -> BehaviorTree:
    def _use() -> BehaviorTree.NodeState:
        if condition is not None and not condition():
            return BehaviorTree.NodeState.SUCCESS
        target_id = int(target() if callable(target) else target)
        if not _cast_hero_skill(hero_position, slot, target_id):
            _log(
                f'Hero {hero_position} was not available for skill slot {slot}.',
                PySystem.Console.MessageType.Warning,
            )
            return BehaviorTree.NodeState.FAILURE
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name or f'Hero {hero_position} Cast Slot {slot}',
            action_fn=_use,
            aftercast_ms=aftercast_ms,
        )
    )


def _player_energy() -> float:
    player_id = int(Player.GetAgentID() or 0)
    return float(Agent.GetEnergy(player_id) or 0.0) * float(Agent.GetMaxEnergy(player_id) or 0)


def _continue_after_wait_timeout(name: str, message: str) -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if _mission_failed():
            return BehaviorTree(
                BehaviorTree.ConditionNode(
                    name=f'{name} Mission Still Active',
                    condition_fn=lambda: False,
                )
            )
        return BT.Sequence(
            name=f'{name} Timeout Fallback',
            children=[
                BT.LogMessage(message, MODULE_NAME),
                BT.Succeeder(f'{name} Timeout Accepted'),
            ],
        )

    return BT.Subtree(f'{name} Timeout Router', _build)


def _wait_for_player_resources(
    name: str,
    *,
    min_energy: float,
    min_adrenaline: int,
    timeout_ms: int,
) -> BehaviorTree:
    def _resources_ready() -> BehaviorTree.NodeState:
        if _mission_failed():
            return BehaviorTree.NodeState.FAILURE
        if _player_energy() > min_energy and _skill_adrenaline(4) >= min_adrenaline:
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    wait_node = BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name=name,
            condition_fn=_resources_ready,
            throttle_interval_ms=100,
            timeout_ms=timeout_ms,
        )
    )
    return BT.Selector(
        [
            wait_node,
            _continue_after_wait_timeout(name, f'{name} timed out; continuing the spike.'),
        ],
        name=name,
    )


def _player_skill_node(
    slot: int,
    target: int | Callable[[], int] = 0,
    *,
    condition: Callable[[], bool] | None = None,
    aftercast_ms: int = 100,
    name: str | None = None,
) -> BehaviorTree:
    node_name = name or f'Player Cast Slot {slot}'

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if condition is not None and not condition():
            return BT.Succeeder(f'{node_name} Condition Not Met')
        target_id = int(target() if callable(target) else target)
        return BT.Selector(
            [
                RoutinesBT.Skills.CastSkillSlot(
                    slot=slot,
                    target_agent_id=target_id,
                    aftercast_delay=aftercast_ms,
                    log=False,
                ),
                BT.Succeeder(f'{node_name} Unavailable'),
            ],
            name=node_name,
        )

    return BT.Subtree(node_name, _build)


def _hero_ai_state_node(
    name: str,
    states: dict[int, dict[int, bool]],
    *,
    behaviors: dict[int, int] | None = None,
) -> BehaviorTree:
    """Apply exact per-slot hero AI states using party positions."""

    def _apply() -> BehaviorTree.NodeState:
        for hero_position, slot_states in states.items():
            hero_agent_id = _hero_agent_id(hero_position)
            if hero_agent_id <= 0:
                _log(
                    f'{name}: hero position {hero_position} is unavailable.',
                    PySystem.Console.MessageType.Error,
                )
                return BehaviorTree.NodeState.FAILURE

            for slot, enabled in slot_states.items():
                GLOBAL_CACHE.Party.Heroes.SetSkillAIEnabled(
                    hero_agent_id,
                    int(slot),
                    bool(enabled),
                )

        for hero_position, behavior in (behaviors or {}).items():
            hero_agent_id = _hero_agent_id(hero_position)
            if hero_agent_id > 0:
                GLOBAL_CACHE.Party.Heroes.SetHeroBehavior(
                    hero_agent_id,
                    int(behavior),
                )

        _log(f'{name}: hero AI states applied.')
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=_apply,
            aftercast_ms=250,
        )
    )


def PrepareHeroSkillbarsForQuest() -> BehaviorTree:
    # Start from all skills enabled, matching AddOns_EnableAllHeroSkillbars().
    states: dict[int, dict[int, bool]] = {
        hero_position: {slot: True for slot in range(1, 9)}
        for hero_position in range(1, 8)
    }

    # Encounter_ReBuilt.au3 PrepareHeroSkillbarsForQuest().
    states[HERO_FIRE_ELE].update({6: False, 7: False, 8: False})
    states[HERO_EARTH_ELE].update({6: False, 7: True, 8: False})
    states[HERO_TRAPPER].update({slot: False for slot in range(1, 8)})
    states[HERO_SOS].update({
        1: False, 2: False, 3: False,
        4: True, 5: True, 6: True, 7: True, 8: True,
    })
    states[HERO_BIP].update({1: False, 2: False, 7: False, 8: False})
    states[HERO_ST].update({1: True})
    states[HERO_ST].update({slot: False for slot in range(2, 9)})

    return _hero_ai_state_node(
        'Prepare Hero Skillbars For Quest - AutoIt',
        states,
    )


def PrepareHeroSkillbarsForFight() -> BehaviorTree:
    # Only touch the exact slots changed by the AutoIt.
    states = {
        HERO_EARTH_ELE: {7: True},
        HERO_TRAPPER: {slot: True for slot in range(1, 8)},
        HERO_PROT_MESMER: {1: True, 6: True},
        HERO_BIP: {7: True, 8: True},
        HERO_ST: {slot: True for slot in range(2, 8)},
    }
    return _hero_ai_state_node(
        'Prepare Hero Skillbars For Fight - AutoIt',
        states,
    )


def PrepareHeroSkillbarsForJourney() -> BehaviorTree:
    states = {
        HERO_SOS: {slot: False for slot in range(1, 9)},
        HERO_ST: {slot: False for slot in range(1, 9)},
        HERO_BIP: {7: False},
    }
    return _hero_ai_state_node(
        'Prepare Hero Skillbars For Journey - AutoIt',
        states,
        behaviors={HERO_SOS: 2},
    )


def _set_hero_behavior_node(
    hero_position: int,
    behavior: int,
    name: str,
) -> BehaviorTree:
    return _hero_ai_state_node(
        name,
        {},
        behaviors={int(hero_position): int(behavior)},
    )


def _player_speedboost() -> BehaviorTree:
    """AutoIt Speedboost() expressed through the profession-independent slots."""

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        primary, _secondary = Agent.GetProfessionNames(Player.GetAgentID())
        if primary == 'Assassin':
            return BT.Sequence(
                name='AutoIt Assassin Speedboost',
                children=[
                    _player_skill_node(1, name='Player: Dwarven Stability'),
                    BT.Wait(100),
                    _player_skill_node(5, name='Player: Dark Escape'),
                ],
            )

        return BT.Sequence(
            name='AutoIt Generic Speedboost',
            children=[
                _player_skill_node(3, name='Player: To The Limit'),
                _player_skill_node(5, name='Player: Soldiers Speed'),
            ],
        )

    return BT.Subtree('AutoIt Player Speedboost', _build)


def _current_hero_ids() -> tuple[int, ...]:
    result: list[int] = []
    for position in range(1, 8):
        agent_id = _hero_agent_id(position)
        result.append(int(GLOBAL_CACHE.Party.Heroes.GetHeroIDByAgentID(agent_id) or 0))
    return tuple(result)


def _setup_party_node() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        global _team_builds_loaded

        if not _setup_party:
            return BT.Succeeder('Automatic Party Setup Disabled')
        if _team_builds_loaded and _current_hero_ids() == EXPECTED_HERO_IDS:
            return BT.Succeeder('Exact AutoIt Party And Builds Already Loaded')

        children: list[BehaviorTree | BehaviorTree.Node] = [
            BT.CreateParty(hero_ids=list(EXPECTED_HERO_IDS), log=True),
        ]

        for hero_position, hero_name, template, behavior in HERO_BUILDS:
            children.extend(
                [
                    BT.LoadHeroSkillbar(hero_position, template, log=True),
                    _configure_hero_node(
                        hero_position,
                        hero_name,
                        (),
                        behavior,
                    ),
                    BT.Wait(250),
                ]
            )

        children.extend(
            [
                PrepareHeroSkillbarsForQuest(),
                _mark_team_builds_loaded_node(),
            ]
        )

        return BT.Sequence(
            name='Load Exact Encounter ReBuilt Hero Team',
            children=children,
        )

    return BT.Subtree('Set Up Exact AutoIt Hero Team', _build)


def _configure_hero_node(
    hero_position: int,
    hero_name: str,
    disabled_slots: tuple[int, ...],
    behavior: int,
) -> BehaviorTree:
    def _configure() -> BehaviorTree.NodeState:
        hero_agent_id = _hero_agent_id(hero_position)
        if hero_agent_id == 0:
            _log(
                f'Cannot configure {hero_name}: hero position {hero_position} is empty.',
                PySystem.Console.MessageType.Error,
            )
            return BehaviorTree.NodeState.FAILURE

        for slot in disabled_slots:
            GLOBAL_CACHE.Party.Heroes.SetSkillAIEnabled(hero_agent_id, slot, False)
        GLOBAL_CACHE.Party.Heroes.SetHeroBehavior(hero_agent_id, behavior)

        mode = {0: 'Fight', 1: 'Guard', 2: 'Avoid'}.get(int(behavior), str(behavior))
        locked = ', '.join(str(slot) for slot in disabled_slots) or 'none'
        _log(f'{hero_name} ready: mode={mode}, locked AI slots={locked}.')
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f'Configure {hero_name}',
            action_fn=_configure,
            aftercast_ms=250,
        )
    )


def _mark_team_builds_loaded_node() -> BehaviorTree:
    def _mark() -> BehaviorTree.NodeState:
        global _team_builds_loaded
        _team_builds_loaded = True
        _log('All seven Ministerial hero builds were loaded.', PySystem.Console.MessageType.Success)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Mark Ministerial Hero Builds Loaded',
            action_fn=_mark,
            aftercast_ms=0,
        )
    )


def _load_player_build_node() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not _load_player_build:
            return BT.Succeeder('Automatic Player Build Disabled')

        primary, _secondary = Agent.GetProfessionNames(Player.GetAgentID())
        template = PLAYER_BUILDS_BY_PRIMARY.get(str(primary or ''))
        if not template:
            return BT.Sequence(
                name='Unsupported AutoIt Player Profession',
                children=[
                    BT.LogMessage(
                        f'No Encounter_ReBuilt player template for primary profession {primary or "unknown"}.',
                        MODULE_NAME,
                    ),
                    BT.Succeeder('Keep Current Player Build'),
                ],
            )

        return BT.LoadSkillbar(template, log=True)

    return BT.Subtree('Load Encounter ReBuilt Player Build', _build)


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()
    return BT.Sequence(
        name='Initialize Ministerial Commendations BT',
        children=[
            bot.Config.Pacifist(
                account_isolation=True,
                multi_account=False,
                auto_loot=False,
                resurrection_scroll=False,
                pause_on_danger=False,
            ),
            BT.LogMessage('Ministerial Commendations BT initialized.', MODULE_NAME),
        ],
    )


def PrepareInKaineng() -> BehaviorTree:
    return BT.Sequence(
        name='Prepare In Kaineng Center',
        map_id_or_name=KAINENG_CENTER,
        children=[
            StartupInventoryCheck(),
            _setup_party_node(),
            _load_player_build_node(),
            BT.SetHardMode(_hard_mode, log=True),
        ],
    )


def _move_to_mission_npc_smooth() -> BehaviorTree:
    """
    Kaineng-only movement to the A Chance Encounter NPC.

    The generic Apo wrapper currently fixes stall_threshold_ms at 500ms.
    Here we call the native movement primitive directly so a short period
    without measurable progress does not cause repeated jitter/nudge commands.
    """
    return BT.Sequence(
        name='Smooth Kaineng Mission NPC Approach',
        children=[
            RoutinesBT.Movement.Move(
                x=2240.0,
                y=-1264.0,
                tolerance=150.0,
                timeout_ms=45_000,
                stall_threshold_ms=2_000,
                pause_on_combat=False,
                avoid_obstacles=False,
                ignore_destination_obstacles=True,
                ignore_destination_npcs=True,
                ignore_destination_gadgets=True,
                log=True,
            ),
            BT.Wait(125),
            BT.TargetNearestAndSendDialog(
                pos=(2240.0, -1264.0),
                dialog_id=MISSION_DIALOG,
                target_distance=Range.Nearby.value,
                log=True,
                multi_account=False,
            ),
        ],
    )


def EnterAChanceEncounter() -> BehaviorTree:
    def _approach_if_needed(_node: BehaviorTree.Node) -> BehaviorTree:
        x, y = Player.GetXY()
        if -1400.0 < x < -550.0 and -2000.0 < y < -1100.0:
            return RoutinesBT.Movement.Move(
                x=1474.0,
                y=-1197.0,
                tolerance=150.0,
                timeout_ms=45_000,
                stall_threshold_ms=2_000,
                pause_on_combat=False,
                avoid_obstacles=False,
                ignore_destination_obstacles=True,
                ignore_destination_npcs=True,
                ignore_destination_gadgets=True,
                log=True,
            )
        return BT.Succeeder('Direct Mission NPC Approach')

    return BT.Sequence(
        name='Enter A Chance Encounter',
        map_id_or_name=KAINENG_CENTER,
        children=[
            PrepareHeroSkillbarsForQuest(),
            _mark_run_statistics_start_node(),
            BT.Subtree('Optional Kaineng Approach', _approach_if_needed),
            _move_to_mission_npc_smooth(),
            BT.WaitForMapLoad(A_CHANCE_ENCOUNTER, timeout_ms=45_000),
        ],
    )


def PlaceParty() -> BehaviorTree:
    children: list[BehaviorTree | BehaviorTree.Node] = [
        BT.IsCurrentMap(A_CHANCE_ENCOUNTER, log=True),
    ]
    children.extend(
        BT.FlagHero(position, x, y)
        for position, x, y in STARTING_POSITIONS
    )
    children.extend(
        [
            BT.Move(
                PLAYER_HERO_SETUP_POSITION,
                pause_on_combat=False,
                tolerance=50.0,
                log=True,
                avoid_obstacles=False,
            ),
            _set_hero_behavior_node(
                HERO_SOS,
                1,
                'Razah: AutoIt Pre-Fight Behavior 1',
            ),
        ]
    )
    return BT.Sequence(
        name='Place Player And Heroes - AutoIt',
        children=children,
    )


def PrepareFirstFight() -> BehaviorTree:
    """
    Port of Encounter_ReBuilt.au3 PrepareToFight().

    Hero numbers, skill slots, coordinates and waits intentionally match the
    AutoIt reference so this BT can be compared directly in game.
    """

    miku_target = lambda: int(_resolve_miku_agent_id() or MIKU_LEGACY_AGENT_ID)

    return BT.Sequence(
        name='Prepare First Fight - AutoIt ReBuilt',
        children=[
            # Opening movement support and first trap spot.
            _hero_skill_node(HERO_EARTH_ELE, 6, name='Vekk: Fall Back'),
            _hero_skill_node(HERO_TRAPPER, 7, name='Pyre: Serpents Quickness'),
            BT.Wait(500),
            _hero_skill_node(HERO_TRAPPER, 3, name='Pyre: Dust Trap - Spot 1'),
            _hero_skill_node(HERO_SOS, 1, name='Razah: Signet Of Spirits'),
            _hero_skill_node(
                HERO_BIP, 1,
                target=lambda: _hero_agent_id(HERO_TRAPPER),
                name='Olias: BiP On Pyre',
            ),
            BT.Wait(2_500),
            _hero_skill_node(HERO_TRAPPER, 1, name='Pyre: Spike Trap - Spot 1'),
            _hero_skill_node(HERO_SOS, 6, name='Razah: Agony'),
            _hero_skill_node(
                HERO_BIP, 1,
                target=lambda: _hero_agent_id(HERO_SOS),
                name='Olias: BiP On Razah',
            ),
            BT.Wait(2_500),
            _hero_skill_node(HERO_TRAPPER, 2, name='Pyre: Flame Trap - Spot 1'),
            _hero_skill_node(HERO_BIP, 7, name='Olias: Protective Was Kaolai'),
            BT.Wait(2_500),
            _hero_skill_node(HERO_TRAPPER, 6, name='Pyre: Destruction'),
            _hero_skill_node(HERO_SOS, 8, name='Razah: Rejuvenation'),
            BT.Wait(1_250),

            # Second trap spot.
            BT.FlagHero(HERO_FIRE_ELE, -6517.0, -5129.0),
            BT.FlagHero(HERO_TRAPPER, -6311.0, -5635.0),
            BT.Wait(1_500),
            _hero_skill_node(HERO_TRAPPER, 4, name='Pyre: Barbed Trap - Spot 2'),
            BT.Wait(2_500),
            _hero_skill_node(HERO_TRAPPER, 5, name='Pyre: Piercing Trap - Spot 2'),
            _hero_skill_node(HERO_ST, 5, name='Xandra: Boon Of Creation'),
            BT.Wait(2_500),
            _hero_skill_node(HERO_TRAPPER, 1, name='Pyre: Spike Trap - Spot 2'),
            _hero_skill_node(HERO_ST, 4, name='Xandra: Displacement'),
            BT.Wait(2_500),

            # Third trap spot.
            BT.FlagHero(HERO_FIRE_ELE, -6480.0, -5258.0),
            BT.FlagHero(HERO_TRAPPER, -6503.0, -5937.0),
            _hero_skill_node(HERO_BIP, 2, name='Olias: Recovery'),
            _hero_skill_node(HERO_ST, 1, name='Xandra: Soul Twisting'),
            BT.Wait(1_500),
            _hero_skill_node(HERO_TRAPPER, 2, name='Pyre: Flame Trap - Spot 3'),
            _hero_skill_node(HERO_BIP, 8, name='Olias: Life'),
            _hero_skill_node(HERO_ST, 2, name='Xandra: Shelter'),
            BT.Wait(2_500),
            _hero_skill_node(HERO_TRAPPER, 3, name='Pyre: Dust Trap - Spot 3'),
            _hero_skill_node(HERO_ST, 3, name='Xandra: Union'),
            BT.Wait(1_250),
            _hero_skill_node(
                HERO_SOS, 2,
                target=miku_target,
                name='Razah: Splinter Weapon On Miku',
            ),
            _hero_skill_node(
                HERO_BIP, 1,
                target=lambda: _hero_agent_id(HERO_SOS),
                name='Olias: BiP On Razah - Second',
            ),
            BT.Wait(1_500),
            _hero_skill_node(HERO_FIRE_ELE, 6, name='Sousuke: Fire Attunement'),
            _hero_skill_node(HERO_EARTH_ELE, 8, name='Vekk: Earth Attunement'),
            _hero_skill_node(HERO_ST, 6, name='Xandra: Earthbind'),

            # Return Pyre to second spot and prime the opening burst.
            BT.FlagHero(HERO_TRAPPER, -6311.0, -5635.0),
            BT.FlagHero(HERO_BIP, -5795.0, -4942.0),
            BT.Wait(1_000),
            _player_skill_node(1, name='Player: Dwarven Stability / Feel No Pain'),
            _hero_skill_node(HERO_FIRE_ELE, 7, name='Sousuke: Glyph Of Sacrifice'),
            _hero_skill_node(HERO_TRAPPER, 4, name='Pyre: Barbed Trap - Final'),
            _hero_skill_node(HERO_SOS, 7, name='Razah: Recuperation'),
            _hero_skill_node(
                HERO_BIP, 1,
                target=lambda: _hero_agent_id(HERO_TRAPPER),
                name='Olias: BiP On Pyre - Final',
            ),
            _hero_skill_node(HERO_ST, 7, name='Xandra: Armor Of Unfeeling'),
            BT.Wait(1_500),

            BT.FlagHero(HERO_SOS, -5984.0, -5524.0),
            _player_skill_node(7, name='Player: Ebon Battle Standard Of Honor'),
            BT.Move(
                PLAYER_TRAP_POSITION,
                pause_on_combat=False,
                tolerance=50.0,
                log=True,
                avoid_obstacles=False,
            ),
            _hero_skill_node(
                HERO_FIRE_ELE,
                8,
                target=198,
                name='Sousuke: Meteor Shower On Initial Backline',
            ),
            _hero_skill_node(HERO_TRAPPER, 1, name='Pyre: Spike Trap - Opening'),
            _hero_skill_node(
                HERO_SOS,
                2,
                target=Player.GetAgentID,
                name='Razah: Splinter Weapon On Player',
            ),
            _hero_skill_node(
                HERO_ST,
                8,
                target=Player.GetAgentID,
                name='Xandra: Inspirational Speech On Player',
            ),

            PrepareHeroSkillbarsForFight(),
        ],
    )


def InitialFight() -> BehaviorTree:
    """
    Encounter_ReBuilt.au3 Fight() state machine.

    >5 foes: fight normally.
    <=5 foes: reposition the AutoIt support heroes and renew SoS.
    <=2 foes: player disengages to the safe spot.
    <=1 foe : hand over immediately to the journey.
    """

    state = {
        'started_at': 0.0,
        'last_action_ms': 0.0,
        'seen': set(),
        'medium_repositioned': False,
        'sos_renewed': False,
        'martyr_disabled': False,
        'disengaged': False,
    }

    reposition = {
        HERO_EARTH_ELE: (-6531, -2888),
        HERO_PROT_MESMER: (-6531, -2888),
        HERO_SOS: (-6236.0, -5905.0),
        HERO_BIP: (-6309.0, -5021.0),
        HERO_ST: (-5974.0, -4869.0),
    }

    def _reset() -> None:
        state['started_at'] = 0.0
        state['last_action_ms'] = 0.0
        state['seen'] = set()
        state['medium_repositioned'] = False
        state['sos_renewed'] = False
        state['martyr_disabled'] = False
        state['disengaged'] = False

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now = time.monotonic()
        if state['started_at'] <= 0.0:
            state['started_at'] = now

        if _mission_failed():
            _reset()
            return BehaviorTree.NodeState.FAILURE

        alive = _initial_foes_alive()
        state['seen'].update(alive)
        elapsed = now - float(state['started_at'])

        pack_established = len(state['seen']) >= 8 or elapsed >= 20.0
        remaining = len([
            agent_id for agent_id in state['seen']
            if agent_id in alive
        ])

        if pack_established and remaining <= 1:
            _log(
                f'AutoIt fight transition: {remaining} initial foe(s) remain.',
                PySystem.Console.MessageType.Success,
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        if pack_established and remaining <= 5:
            if not state['medium_repositioned']:
                for hero_position, (x, y) in reposition.items():
                    hero_agent_id = _hero_agent_id(hero_position)
                    if hero_agent_id > 0:
                        GLOBAL_CACHE.Party.Heroes.FlagHero(hero_agent_id, x, y)
                state['medium_repositioned'] = True
                _log(f'AutoIt medium fight phase: repositioned heroes; remaining={remaining}.')

            if not state['sos_renewed']:
                sos_id = _hero_agent_id(HERO_SOS)
                if sos_id > 0 and _distance(Agent.GetXY(sos_id), reposition[HERO_SOS]) <= 150.0:
                    if _hero_skill_ready(HERO_SOS, 1):
                        _cast_hero_skill(HERO_SOS, 1)
                    state['sos_renewed'] = True

            if not state['martyr_disabled']:
                gwen_id = _hero_agent_id(HERO_PROT_MESMER)
                if gwen_id > 0:
                    GLOBAL_CACHE.Party.Heroes.SetSkillAIEnabled(gwen_id, 1, False)
                state['martyr_disabled'] = True

        if pack_established and remaining <= 2:
            if not state['disengaged']:
                state['disengaged'] = True
                # AutoIt MoveToSafeSpot(): speedboost then move to (-6080,-5020).
                _cast_player_skill(3)
                _cast_player_skill(5)
                Player.Move(AUTOIT_SAFE_SPOT[0], AUTOIT_SAFE_SPOT[1])
                _log(
                    f'AutoIt fight state: {remaining} foes remain; player disengaging.'
                )
            return BehaviorTree.NodeState.RUNNING

        # AutoIt PlayerAssistance(True): maintain slot 1, build adrenaline with
        # slot 3, use Hundred Blades slot 2 and Whirlwind slot 4.
        target_id = 0
        if alive:
            target_id = min(
                alive,
                key=lambda agent_id: _distance(
                    Agent.GetXY(agent_id),
                    PLAYER_TRAP_POSITION,
                ),
            )

        now_ms = now * 1000.0
        if target_id and now_ms - float(state['last_action_ms']) >= 750.0:
            Player.ChangeTarget(target_id)
            Player.Interact(target_id, False)

            _cast_player_skill(1)
            if _skill_adrenaline(4) < 130:
                _cast_player_skill(3)
            _cast_player_skill(2)
            _cast_player_skill(4, target_id)

            state['last_action_ms'] = now_ms

        if elapsed >= 120.0:
            _log(
                'AutoIt first fight reached 120s timeout; restarting mission.',
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.FAILURE

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Fight Initial Group - AutoIt ReBuilt',
            action_fn=_tick,
            aftercast_ms=0,
        )
    )


def WaitForMikuAreaClear() -> BehaviorTree:
    def _area_is_clear() -> BehaviorTree.NodeState:
        if _mission_failed():
            return BehaviorTree.NodeState.FAILURE

        center_id = _miku_or_player()
        center = Agent.GetXY(center_id)
        if not _enemy_ids_near(center, Range.Spirit.value):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    wait_node = BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name='Wait For Miku Area Clear',
            condition_fn=_area_is_clear,
            throttle_interval_ms=500,
            timeout_ms=45_000,
        )
    )
    return BT.Selector(
        [
            wait_node,
            _continue_after_wait_timeout(
                'Wait For Miku Area Clear',
                'Miku-area clear timed out; continuing the run.',
            ),
        ],
        name='Wait For Miku Area Clear',
    )


def CastVekkFallBack() -> BehaviorTree:
    """AutoIt Earth Ele movement support: hero 2 slot 6, never blocking."""
    return BT.Selector(
        name='Vekk: Fall Back If Available',
        children=[
            _hero_skill_node(
                HERO_EARTH_ELE,
                6,
                aftercast_ms=100,
                name='Vekk: Fall Back',
            ),
            BT.Succeeder('Vekk Fall Back Unavailable'),
        ],
    )


def FinishInitialFight() -> BehaviorTree:
    return BT.Sequence(
        name='Finish Initial Fight - AutoIt Transition',
        children=[
            CastVekkFallBack(),
            _player_speedboost(),

            # AutoIt issues the player move and these hero commands almost
            # concurrently. BT.Move is blocking, therefore place the hero
            # commands first so they start travelling while the player leaves.
            _set_hero_behavior_node(
                HERO_SOS,
                2,
                'Razah: Set Avoid For Journey',
            ),
            BT.FlagHero(HERO_SOS, -4770.0, -3330.0),
            BT.FlagHero(HERO_ST, -4770.0, -3330.0),
            PrepareHeroSkillbarsForJourney(),

            BT.Move(
                AUTOIT_FIGHT_EXIT,
                pause_on_combat=False,
                tolerance=125.0,
                log=True,
                avoid_obstacles=False,
            ),
        ],
    )


def RunToStairs() -> BehaviorTree:
    return BT.Sequence(
        name='Run To Stairs - Exact AutoIt Roles',
        children=[
            BT.IsCurrentMap(A_CHANCE_ENCOUNTER, log=True),

            BT.FlagAllHeroes(-7047.0, -2651.0),

            _hero_skill_node(
                HERO_BIP,
                1,
                target=lambda: _hero_agent_id(HERO_SOS),
                condition=lambda: Agent.GetHealth(_hero_agent_id(HERO_BIP)) > 0.5,
                name='Olias: BiP On Razah Before Journey',
            ),

            BT.FlagHero(HERO_SOS, -2195.0, 33.0),
            BT.FlagHero(HERO_ST, -2195.0, 33.0),
            _hero_skill_node(
                HERO_SOS,
                3,
                target=lambda: _hero_agent_id(HERO_ST),
                aftercast_ms=2_500,
                name='Razah: Recall On Xandra',
            ),

            _player_speedboost(),
            BT.Move(
                AUTOIT_FIGHT_EXIT,
                pause_on_combat=False,
                tolerance=150.0,
                log=True,
                avoid_obstacles=False,
            ),
            WaitForMikuAtJourneyExit(),

            _hero_skill_node(
                HERO_PROT_MESMER,
                1,
                name='Gwen: Martyr Before Journey',
            ),

            _player_speedboost(),
            BT.Move(
                AUTOIT_MID_1,
                pause_on_combat=False,
                tolerance=125.0,
                log=True,
                avoid_obstacles=False,
            ),

            # Force the actual staircase line. MID_1 is close enough to the
            # staircase edge that a direct autopath to MID_2 can cut around it.
            *[
                BT.Move(
                    point,
                    pause_on_combat=False,
                    tolerance=75.0,
                    log=True,
                    avoid_obstacles=False,
                )
                for point in AUTOIT_STAIR_PATH
            ],

            BT.Move(
                AUTOIT_MID_2,
                pause_on_combat=False,
                tolerance=125.0,
                log=True,
                avoid_obstacles=False,
            ),

            BT.FlagHero(HERO_SOS, AUTOIT_STAIRS_APPROACH[0], AUTOIT_STAIRS_APPROACH[1]),
            BT.FlagHero(HERO_ST, AUTOIT_STAIRS_APPROACH[0], AUTOIT_STAIRS_APPROACH[1]),

            _wait_for_enemy_presence_or_timeout(
                'AutoIt Journey Gate 1',
                radius=2500.0,
                timeout_ms=7_500,
            ),

            # Encounter_ReBuilt.au3 drops Recall here before the second half
            # of the journey.
            _drop_hero_buff_for_skill_node(
                HERO_SOS,
                3,
                name='Razah: Drop Journey Recall',
            ),

            _player_speedboost(),
            BT.Move(
                AUTOIT_MID_3,
                pause_on_combat=False,
                tolerance=125.0,
                log=True,
                avoid_obstacles=False,
            ),
            BT.Move(
                AUTOIT_MID_4,
                pause_on_combat=False,
                tolerance=125.0,
                log=True,
                avoid_obstacles=False,
            ),

            BT.FlagHero(HERO_PROT_MESMER, -5606.0, -2916.0),
            BT.FlagHero(HERO_BIP, -5606.0, -2916.0),
            BT.FlagHero(HERO_SOS, -1119.0, -4683.0),
            BT.FlagHero(HERO_ST, -1665.0, -6015.0),

            _wait_for_enemy_presence_or_timeout(
                'AutoIt Journey Gate 2',
                radius=2500.0,
                timeout_ms=7_500,
            ),

            _player_speedboost(),
            BT.Move(
                AUTOIT_STAIRS_APPROACH,
                pause_on_combat=False,
                tolerance=100.0,
                log=True,
                avoid_obstacles=False,
            ),
            BT.Move(
                AUTOIT_FARM_POSITION,
                pause_on_combat=False,
                tolerance=35.0,
                log=True,
                avoid_obstacles=False,
            ),

            _hero_skill_node(HERO_BIP, 7, name='Olias: Protective Was Kaolai At Farm'),
            _hero_skill_node(
                HERO_ST,
                8,
                target=Player.GetAgentID,
                name='Xandra: Inspirational Speech On Player At Farm',
            ),
        ],
    )


def _defensive_ball_tick(state: dict[str, float], enemy_count: int) -> None:
    """Lightweight AutoIt StayAlive-style player support while waves gather."""
    now_ms = time.monotonic() * 1000.0
    if now_ms - state.get('action_ms', 0.0) < 500.0:
        return

    player_id = int(Player.GetAgentID() or 0)
    health = Agent.GetHealth(player_id)
    casted = False

    # AutoIt always tries To the Limit! while holding the ball.
    if _skill_adrenaline(4) < 130:
        casted = _cast_player_skill(3)

    if not casted and not _has_player_effect_for_slot(1):
        casted = _cast_player_skill(1)

    if not casted and health <= 0.70:
        casted = _cast_player_skill(8)

    if not casted and health <= 0.90:
        casted = _cast_player_skill(6)

    if casted:
        state['action_ms'] = now_ms


def PrepareStairsDefense() -> BehaviorTree:
    """
    Port Encounter_ReBuilt.au3 PlaceSpirits() states 0 -> 3.

    Exact flag coordinates:
      Razah  -> (-997, -4976)
      Xandra -> (-4950, -7955)
    """
    return BT.Sequence(
        name='Prepare Stairs Defense - AutoIt Spirits',
        children=[
            # PlaceSpirits case 0.
            _hero_skill_node(HERO_SOS, 8, name='Razah: Rejuvenation At Farm'),
            _hero_skill_node(HERO_ST, 1, name='Xandra: Soul Twisting At Farm'),
            _hero_skill_node(HERO_ST, 2, name='Xandra: Shelter'),

            # PlaceSpirits case 1.
            BT.FlagHero(HERO_SOS, -997.0, -4976.0),
            _hero_skill_node(
                HERO_SOS,
                3,
                target=lambda: _hero_agent_id(HERO_ST),
                aftercast_ms=2_500,
                name='Razah: Recall On Xandra At Farm',
            ),
            _hero_skill_node(HERO_ST, 3, name='Xandra: Union'),

            # PlaceSpirits case 2.
            _hero_skill_node(HERO_ST, 7, name='Xandra: Armor Of Unfeeling'),

            # PlaceSpirits case 3.
            BT.FlagHero(HERO_ST, -4950.0, -7955.0),
            _hero_skill_node(HERO_SOS, 7, name='Razah: Recuperation At Farm'),
            BT.FlagHero(HERO_PROT_MESMER, -7047, -2651),
            BT.FlagHero(HERO_BIP, -7047, -2651),
            BT.FlagHero(HERO_TRAPPER, -7047, -2651),
            BT.FlagHero(HERO_FIRE_ELE, -7047, -2651),
            BT.FlagHero(HERO_EARTH_ELE, -7047, -2651),
        ],
    )


def WaitForPurityBall() -> BehaviorTree:
    """
    AutoIt-style WaitForFoes wave tracker.

    1) wait until >=4 foes enter 1000 range (max 30s);
    2) remember every unique foe seen in 1000;
    3) mark a foe resolved once it reaches 200, leaves 1000, or dwells
       outside 200 for 12s;
    4) after an 18s no-new-arrival gate (or 60 unique seen), continue when
       >=98% of seen foes are resolved;
    5) hard-stop the wait after 60s, matching the AutoIt fallback.
    """

    state = {
        'phase': 'arrival',
        'phase_started_ms': 0.0,
        'last_new_ms': 0.0,
        'seen': {},
        'action_ms': 0.0,
    }

    def _reset() -> None:
        state['phase'] = 'arrival'
        state['phase_started_ms'] = 0.0
        state['last_new_ms'] = 0.0
        state['seen'] = {}
        state['action_ms'] = 0.0

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _mission_failed():
            _reset()
            return BehaviorTree.NodeState.FAILURE

        now_ms = time.monotonic() * 1000.0
        if state['phase_started_ms'] <= 0.0:
            state['phase_started_ms'] = now_ms
            state['last_new_ms'] = now_ms

        in_1000 = set(_enemy_ids_near(Player.GetXY(), 1000.0))
        in_200 = set(_enemy_ids_near(Player.GetXY(), 200.0))

        # Keep the current Python defensive behavior active while waiting.
        _defensive_ball_tick(state, len(in_200))

        if state['phase'] == 'arrival':
            if len(in_1000) >= 4 or now_ms - state['phase_started_ms'] >= 30_000.0:
                state['phase'] = 'gather'
                state['phase_started_ms'] = now_ms
                state['last_new_ms'] = now_ms
                state['seen'] = {}
                _log(
                    f'AutoIt wave tracker started with {len(in_1000)} foe(s) in 1000 range.'
                )
            else:
                return BehaviorTree.NodeState.RUNNING

        seen: dict[int, dict[str, int | bool]] = state['seen']

        # Add newly seen foes.
        for agent_id in in_1000:
            if agent_id not in seen and len(seen) < 60:
                seen[agent_id] = {
                    'touched_200': False,
                    'dwell_ticks': 0,
                }
                state['last_new_ms'] = now_ms

        # Update resolution state. AutoIt ticks this every 500ms.
        for agent_id, foe_state in seen.items():
            if agent_id in in_200:
                foe_state['touched_200'] = True

            if agent_id in in_1000 and not bool(foe_state['touched_200']):
                foe_state['dwell_ticks'] = int(foe_state['dwell_ticks']) + 1
            else:
                foe_state['dwell_ticks'] = 0

        resolved = 0
        for agent_id, foe_state in seen.items():
            if (
                bool(foe_state['touched_200'])
                or agent_id not in in_1000
                or int(foe_state['dwell_ticks']) >= 24  # 12s / 500ms
            ):
                resolved += 1

        count_seen = len(seen)
        no_arrivals_gate = (
            count_seen >= 60
            or now_ms - float(state['last_new_ms']) >= 18_000.0
        )
        required_resolved = int(count_seen * 0.98)

        if (
            count_seen > 0
            and no_arrivals_gate
            and resolved >= required_resolved
        ):
            _log(
                f'AutoIt wave tracker complete: seen={count_seen}, resolved={resolved}.',
                PySystem.Console.MessageType.Success,
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        if now_ms - float(state['phase_started_ms']) >= 60_000.0:
            _log(
                f'AutoIt wave tracker reached 60s fallback: seen={count_seen}, resolved={resolved}; continuing.',
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Wait For Ministry Of Purity Ball - AutoIt Wave Tracker',
            action_fn=_tick,
            aftercast_ms=500,
        )
    )


def SpikeMinistryOfPurity() -> BehaviorTree:
    """
    Encounter_ReBuilt.au3 Spike() core:
    move Gwen/Olias away, apply weapon support, prime Honor, Hundred Blades,
    then Whirlwind Attack the nearest foe inside 200.
    """
    return BT.Sequence(
        name='Spike Ministry Of Purity - AutoIt',
        children=[
                        _hero_skill_node(HERO_SOS,4,target=Player.GetAgentID,aftercast_ms=1_500,name='Razah: Weapon Support On Player',),
            BT.FlagHero(HERO_SOS, -4950.0, -7955.0),
            _drop_hero_buff_for_skill_node(HERO_SOS,3,name='Razah: Drop Farm Recall',),
            _wait_for_heroes_out_of_loot_range(timeout_ms=15_000),
            _wait_for_player_resources('Wait For AutoIt Spike Resources',min_energy=5.0,min_adrenaline=130,timeout_ms=15_000,),
            _player_skill_node(7, name='Player: Ebon Battle Standard Of Honor'),
            _player_skill_node(2, name='Player: Hundred Blades'),
            BT.Wait(250),
            _player_skill_node(4,target=lambda: _nearest_enemy(Player.GetXY(), 200.0),name='Player: Whirlwind Attack',),
            BT.Wait(3_000),
        ],
    )


def LootAndReturn() -> BehaviorTree:
    return BT.Sequence(
        name='Loot Commendations And Return',
        children=[
            # HeroAI is required for looting, but combat must stay disabled.
            BottingTree.EnableHeroAITree(reset_runtime=True),
            BottingTree.DisableCombatTree(),
            BottingTree.EnableLootingTree(),

            BT.Wait(500),

            BT.LootItems(
                distance=Range.Spirit.value,
                timeout_ms=15_000,
            ),

            BottingTree.DisableLootingTree(),
            BottingTree.DisableHeroAITree(reset_runtime=True),

            BT.Wait(250),

            BT.Travel(
                target_map_id=KAINENG_CENTER,
                log=True,
            ),
            BT.WaitForMapLoad(KAINENG_CENTER, timeout_ms=45_000),
            _record_run_statistics_node(),
        ],
    )


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ('Initialize Bot', InitializeBot),
        ('Prepare In Kaineng', PrepareInKaineng),
        ('Enter A Chance Encounter', EnterAChanceEncounter),
        ('Place Player And Heroes', PlaceParty),
        ('Prepare First Fight', PrepareFirstFight),
        ('Fight Initial Group', InitialFight),
        ('Finish Initial Fight', FinishInitialFight),
        ('Run To Stairs', RunToStairs),
        ('Prepare Stairs Defense', PrepareStairsDefense),
        ('Wait For Purity Ball', WaitForPurityBall),
        ('Spike Ministry Of Purity', SpikeMinistryOfPurity),
        ('Loot And Return', LootAndReturn),
        ('Inventory Check And Maintenance', InventoryCheckAndMaintenance),
    ]


def ensure_botting_tree() -> BottingTree:
    global botting_tree

    _load_settings()
    if botting_tree is None:
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name='MinisterialCommendationsSequence',
            repeat=True,
            multi_account=False,
            isolation_enabled=True,
            pause_on_combat=False,
            configure_fn=_configure_botting_tree,
        )
    return botting_tree


def _configure_botting_tree(tree: BottingTree) -> None:
    tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        resurrection_scroll=False,
        auto_inventory_handler_enabled=True,
        enable_party_wipe_recovery=False,
        heroai_state_logging=False,
    )
    # SetMainRoutine adds the native wipe service after this anchor. This order
    # lets the anchor replace the current step before native recovery captures it.
    tree.AddServiceTree('MissionRestartAnchor', MissionRestartAnchorService)


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
        main_child_dimensions=(440, 390),
        extra_tabs=[('Statistics', _draw_statistics), ('Config', _draw_config)],
    )


if __name__ == '__main__':
    main()