from __future__ import annotations

import os
import time
from collections.abc import Callable

import PySystem

from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Model_enums import GadgetModelID
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.enums_src.Title_enums import TitleID
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import CONSET_UPKEEPS
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import CONSUMABLE_UPKEEPS
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems
from Sources.ApoSource.ApoBottingLib import wrappers as BT

TEXTURE = os.path.join(
    PySystem.Console.get_projects_path(),
    "Textures",
    "Module_Icons",
    "Voltaicspear.png",
)
MODULE_ICON = "Textures\\Module_Icons\\Voltaicspear.png"

MODULE_NAME = 'Voltaic Spear BT'
INI_PATH = 'Widgets/Automation/Bots/Farmers/Weapons/Voltaic Spear BT'
INI_FILENAME = 'Voltaic_Spear_BT.ini'

# Maps copied from Voltaic.au3 / Reforged map enums.
UMBRAL_GROTTO = 639
VERDANT_CASCADES = 566
SLAVERS_EXILE = 577
JUSTICIAR_THOMMIS_ROOM = 620

THOMMIS_DIALOG = 0x84
AGGRO_RADIUS = Range.Spellcast.value + 200.0

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

_settings = Settings(f'{INI_PATH}/{INI_FILENAME}', 'account')
_settings_loaded = False

_hard_mode = False
_use_conset = False
_use_pcons = False
_use_summoning_stone = True
_auto_loot = True

_total_runs = 0
_total_seconds = 0.0
_best_seconds = float('inf')
_worst_seconds = 0.0
_total_spears = 0

_session_runs = 0
_session_spears = 0
_run_started_at = 0.0
_last_run_seconds = 0.0
_spear_count_before_run = 0

initialized = False
botting_tree: BottingTree | None = None


def _load_settings() -> None:
    global _settings_loaded
    global _hard_mode, _use_conset, _use_pcons, _use_summoning_stone, _auto_loot
    global _total_runs, _total_seconds, _best_seconds, _worst_seconds, _total_spears

    if _settings_loaded:
        return

    _hard_mode = _settings.get_bool('Config', 'HardMode', False)
    _use_conset = _settings.get_bool('Config', 'UseConset', False)
    _use_pcons = _settings.get_bool('Config', 'UsePcons', False)
    _use_summoning_stone = _settings.get_bool('Config', 'UseSummoningStone', True)
    _auto_loot = _settings.get_bool('Config', 'AutoLoot', True)

    _total_runs = _settings.get_int('Statistics', 'TotalRuns', 0)
    _total_seconds = _settings.get_float('Statistics', 'TotalSeconds', 0.0)
    best = _settings.get_float('Statistics', 'BestSeconds', 0.0)
    _best_seconds = float('inf') if best <= 0.0 else best
    _worst_seconds = _settings.get_float('Statistics', 'WorstSeconds', 0.0)
    _total_spears = _settings.get_int('Statistics', 'TotalVoltaicSpears', 0)
    _settings_loaded = True


def _save_config() -> None:
    _settings.set('Config', 'HardMode', _hard_mode)
    _settings.set('Config', 'UseConset', _use_conset)
    _settings.set('Config', 'UsePcons', _use_pcons)
    _settings.set('Config', 'UseSummoningStone', _use_summoning_stone)
    _settings.set('Config', 'AutoLoot', _auto_loot)


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


def _enabled_pcons() -> tuple[int, ...]:
    return PCON_UPKEEPS if _use_pcons else ()


def _configure_upkeep() -> None:
    if botting_tree is None:
        return
    botting_tree.Config.ConfigureUpkeep(
        looting_enabled=_auto_loot,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=_enabled_pcons(),
        enable_party_wipe_recovery=True,
        heroai_state_logging=False,
    )


def _draw_config() -> None:
    import PyImGui

    global _hard_mode, _use_conset, _use_pcons, _use_summoning_stone, _auto_loot

    changed = False
    upkeep_changed = False

    PyImGui.text('Voltaic Spear Config')
    PyImGui.separator()

    value = PyImGui.checkbox('Hard Mode', _hard_mode)
    if value != _hard_mode:
        _hard_mode = value
        changed = True

    value = PyImGui.checkbox('Use conset in Thommis room', _use_conset)
    if value != _use_conset:
        _use_conset = value
        changed = True

    value = PyImGui.checkbox('Maintain personal consumables', _use_pcons)
    if value != _use_pcons:
        _use_pcons = value
        changed = True
        upkeep_changed = True

    value = PyImGui.checkbox('Use summoning stone', _use_summoning_stone)
    if value != _use_summoning_stone:
        _use_summoning_stone = value
        changed = True

    value = PyImGui.checkbox('Auto loot', _auto_loot)
    if value != _auto_loot:
        _auto_loot = value
        changed = True
        upkeep_changed = True

    if changed:
        _save_config()
    if upkeep_changed:
        _configure_upkeep()


def _format_time(seconds: float) -> str:
    if seconds <= 0.0 or seconds == float('inf'):
        return '--:--'
    minutes, remaining = divmod(int(seconds), 60)
    return f'{minutes:02d}:{remaining:02d}'


def _draw_statistics() -> None:
    import PyImGui

    flags = PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg
    PyImGui.text('Voltaic Spear Statistics')
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

    if PyImGui.begin_table('##voltaic_times', 4, flags):
        for label in ('Last', 'Average', 'Best', 'Worst'):
            PyImGui.table_setup_column(label)
        PyImGui.table_headers_row()
        average = _total_seconds / _total_runs if _total_runs else 0.0
        PyImGui.table_next_row()
        for column, value in enumerate(
            (
                _format_time(_last_run_seconds),
                _format_time(average),
                _format_time(_best_seconds),
                _format_time(_worst_seconds),
            )
        ):
            PyImGui.table_set_column_index(column)
            PyImGui.text(value)
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
        global _run_started_at, _spear_count_before_run
        _run_started_at = time.monotonic()
        _spear_count_before_run = int(
            GLOBAL_CACHE.Inventory.GetModelCount(VOLTAIC_SPEAR_MODEL_ID)
        )

    return _action_node('Start Run Statistics', _start)


def _record_statistics() -> BehaviorTree:
    def _record() -> None:
        global _total_runs, _session_runs, _total_seconds
        global _best_seconds, _worst_seconds, _last_run_seconds
        global _total_spears, _session_spears, _run_started_at

        if _run_started_at <= 0.0:
            return

        _last_run_seconds = time.monotonic() - _run_started_at
        spear_count_after = int(
            GLOBAL_CACHE.Inventory.GetModelCount(VOLTAIC_SPEAR_MODEL_ID)
        )
        spear_delta = max(0, spear_count_after - _spear_count_before_run)

        _total_runs += 1
        _session_runs += 1
        _total_seconds += _last_run_seconds
        _best_seconds = min(_best_seconds, _last_run_seconds)
        _worst_seconds = max(_worst_seconds, _last_run_seconds)
        _total_spears += spear_delta
        _session_spears += spear_delta
        _run_started_at = 0.0
        _save_statistics()

        PySystem.Console.Log(
            MODULE_NAME,
            (
                f'Run completed in {_format_time(_last_run_seconds)}. '
                f'Voltaic Spears: {spear_delta}.'
            ),
            PySystem.Console.MessageType.Success,
        )

    return _action_node('Record Successful Run', _record)


def _summoning_stone() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not _use_summoning_stone:
            return BT.Succeeder('Summoning Stone Disabled')

        choices: list[BehaviorTree | BehaviorTree.Node] = []
        for model_id in SUMMONING_STONES:
            choices.append(
                BT.Sequence(
                    name=f'Use Summoning Stone {model_id}',
                    children=[
                        BT.HasItemQuantity(model_id, 1),
                        BTItems.UseConsumable(model_id, aftercast_ms=500),
                    ],
                )
            )
        choices.append(BT.Succeeder('No Summoning Stone Available'))
        return BT.Selector(choices, name='Select Summoning Stone')

    return BT.Subtree('Use Summoning Stone', _build)


def _conset() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not (_hard_mode and _use_conset):
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
                multi_account=False,
                auto_loot=_auto_loot,
                resurrection_scroll=True,
            ),
            BT.LogMessage('Voltaic Spear BT initialized.', MODULE_NAME),
        ],
    )


def PrepareRun() -> BehaviorTree:
    return BT.Sequence(
        name='Prepare Voltaic Spear Run',
        children=[
            BT.Travel(target_map_id=UMBRAL_GROTTO, log=True),
            BT.SetHardMode(_hard_mode, log=True),
            RoutinesBT.Party.SetTitle(int(TitleID.Asuran.value), log=True),
            _start_statistics(),
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
            _summoning_stone(),
        ],
    )


def _combat_point(
    map_id: int,
    point: tuple[float, float],
    name: str,
) -> BehaviorTree:
    return BT.Sequence(
        name=name,
        children=[
            BT.IsCurrentMap(map_id, log=True),
            BT.MoveAndKill(
                point,
                clear_area_radius=AGGRO_RADIUS,
                pause_on_combat=True,
                move_tolerance=175.0,
                log=True,
            ),
        ],
    )


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
    return BT.MoveAndExitMap(
        THOMMIS_ROOM_PORTAL,
        target_map_id=JUSTICIAR_THOMMIS_ROOM,
        timeout_ms=45_000,
        log=True,
    )


def StartThommisFight() -> BehaviorTree:
    return BT.Sequence(
        name='Start Thommis Fight',
        children=[
            BT.IsCurrentMap(JUSTICIAR_THOMMIS_ROOM, log=True),
            BT.MoveAndDialog(
                THOMMIS_NPC,
                THOMMIS_DIALOG,
                pause_on_combat=False,
                multi_account=False,
                log=True,
            ),
            BT.Wait(1_000),
            _conset(),
            _summoning_stone(),
        ],
    )


def _loot_pass() -> BehaviorTree:
    return BT.Selector(
        [
            BT.LootItems(distance=Range.Earshot.value, timeout_ms=8_000),
            BT.Succeeder('No Loot In This Pass'),
        ],
        name='Loot Chest Pass',
    )


def OpenAndLootChest() -> BehaviorTree:
    return BT.Sequence(
        name='Open And Loot Thommis Chest',
        children=[
            BT.IsCurrentMap(JUSTICIAR_THOMMIS_ROOM, log=True),
            BT.MoveAndInteractWithGadget(
                pos=CHEST_POSITION,
                gadget_id=THOMMIS_CHEST_GADGET_ID,
                search_distance=2_000.0,
                interaction_distance=Range.Nearby.value,
                timeout_ms=45_000,
                pause_on_combat=False,
                log=True,
            ),
            BT.Repeater(
                name='Three Chest Loot Attempts',
                repeat_count=3,
                children=[
                    BT.Wait(5_000),
                    _loot_pass(),
                    BT.Wait(2_500),
                ],
            ),
            _record_statistics(),
        ],
    )


def ReturnToUmbralGrotto() -> BehaviorTree:
    return BT.Travel(target_map_id=UMBRAL_GROTTO, log=True)


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
        *_path_steps('Verdant Cascades', VERDANT_CASCADES, VERDANT_PATH, _combat_point),
        ('Enter Slavers Exile', EnterSlaversExile),
        *_path_steps('Slavers Approach', SLAVERS_EXILE, THOMMIS_ENTRY_PATH, _movement_point),
        ('Enter Thommis Room', EnterThommisRoom),
        ('Start Thommis Fight', StartThommisFight),
        *_path_steps('Thommis Part 1', JUSTICIAR_THOMMIS_ROOM, THOMMIS_PATH_1, _combat_point),
        *_path_steps('Thommis Part 2', JUSTICIAR_THOMMIS_ROOM, THOMMIS_PATH_2, _combat_point),
        ('Open And Loot Chest', OpenAndLootChest),
        ('Return To Umbral Grotto', ReturnToUmbralGrotto),
    ]


def ensure_botting_tree() -> BottingTree:
    global botting_tree

    _load_settings()
    if botting_tree is None:
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name='VoltaicSpearSequence',
            repeat=True,
            multi_account=False,
            isolation_enabled=True,
            pause_on_combat=True,
            configure_fn=lambda tree: tree.Config.ConfigureUpkeep(
                looting_enabled=_auto_loot,
                resurrection_scroll=True,
                auto_inventory_handler_enabled=True,
                consumable_upkeeps=_enabled_pcons(),
                enable_party_wipe_recovery=True,
                heroai_state_logging=False,
            ),
        )
    return botting_tree


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
        main_child_dimensions=(430, 390),
        extra_tabs=[
            ('Statistics', _draw_statistics),
            ('Config', _draw_config),
        ],
    )


if __name__ == '__main__':
    main()