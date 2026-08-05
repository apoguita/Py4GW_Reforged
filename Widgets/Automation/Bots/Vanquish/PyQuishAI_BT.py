from __future__ import annotations

import importlib
import os
import time
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from typing import TypeAlias

import PyImGui
import PySystem

from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.enums import Range
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Sources.ApoSource.ApoBottingLib import wrappers as BT


MODULE_NAME = 'PyQuishAI BT'
MODULE_ICON = 'Textures\\Module_Icons\\PyQuishAI.png'
MODULE_CATEGORY = 'Automation'
MODULE_TAGS = ['Bot', 'Vanquish', 'BehaviorTree']

INI_PATH = 'Widgets/Automation/Bots/Vanquish/PyQuishAI_BT'
INI_FILENAME = 'PyQuishAI_BT.ini'
MAP_PACKAGE = 'Sources.aC_Scripts.PyQuishAI_maps'
TEXTURE = os.path.join(
    PySystem.Console.get_projects_path(),
    'Sources',
    'ApoSource',
    'textures',
    'VQ_Helmet.png',
)

Coordinate: TypeAlias = tuple[float, float]


# Static discovery avoids scanning the source tree every frame. The map modules remain
# the source of truth for paths and map identifiers.
MAP_CATALOG: dict[str, tuple[str, ...]] = {
    'EOTN_Charr_Homelands': (
        'Dalada_Uplands',
    ),
    'EOTN_Far_Silverpeaks': (
        'Drakkar_Lake',
        'Ice_Cliff_Chasms',
        'Norrhart_Domains',
        'Varajar_Fells',
    ),
    'EOTN_Tarnished_Coast': (
        'AlcaziaTangle',
        'ArborBay',
        'MagusStones',
        'RivenEarth',
        'VerdantCascades',
    ),
    'Factions_EchovaldForest': (
        'Arborstone',
        'DrazachThicket',
        'Ferndale',
        'MelandrusHope',
        'MorostavTrail',
        'MourningVeilFalls',
        'TheEternalGrove',
    ),
    'Factions_KainengCity': (
        'BukdekByway',
        'NahpuiQuarter',
        'PongmeiValley',
        'RaisuPalace',
        'ShadowsPassage',
        'ShenzunTunnels',
        'SunjiangDistrict',
        'TahnnakiTemple',
        'WajjunBazaar',
        'XaquangSkyway',
    ),
    'Factions_ShingJeaIsland': (
        'HaijuLagoon',
        'JayaBluffs',
        'KinyaProvince',
        'MinisterChosEstate',
        'PanjiangPeninsula',
        'SaoshangTrail',
        'SunquaVale',
        'ZenDaijun',
    ),
    'Factions_TheJadeSea': (
        'Archipelagos',
        'BoreasSeabed',
        'GyalaHatchery',
        'MaishangHills',
        'MountQinkai',
        'RheasCrater',
        'SilentSurf',
        'UnwakingWaters',
    ),
    'NF_Desolation': (
        'CrystalOverlook',
        'JokosDomain',
        'PoisonedOutcrops',
        'TheAlkaliPan',
        'TheRupturedHeart',
        'TheShatteredRavines',
        'TheSulfurousWastes',
    ),
    'NF_Istan': (
        'CliffsOfDohjok',
        'FahranurTheFirstCity',
        'IssnurIsles',
        'LahtendaBog',
        'MehtaniKeys',
        'PlainsofJarin',
        'ZehlonReach',
    ),
    'NF_Kourna': (
        'ArkjokWard',
        'BahdokCaverns',
        'BarbarousShore',
        'DejarinEstate',
        'GandaraTheMoonFortress',
        'JahaiBluffs',
        'MargaCoast',
        'SunwardMarches',
        'TheFloodplainOfMahnkelon',
        'TuraisProcession',
    ),
    'NF_Vabbi': (
        'ForumHighlands',
        'GardenOfSeborhin',
        'HoldingsOfChokhin',
        'ResplendentMakuun',
        'TheHiddenCityOfAhdashim',
        'TheMirrorOfLyss',
        'VehjinMines',
        'VehtendiValley',
        'WildernessOfBahdza',
        'YatendiCanyons',
    ),
    'Proph_Ascalon': (
        'AscalonFoothills',
        'DiessaLowlands',
        'DragonsGullet',
        'EasternFrontier',
        'FlameTempleCorridor',
        'OldAscalon',
        'PockmarkFlats',
        'RegentValley',
        'TheBreach',
    ),
    'Proph_CrystalDesert': (
        'DivinersAscent',
        'ProphetsPath',
        'SaltFlats',
        'SkywardReach',
        'TheAridSea',
        'TheScar',
        'VultureDrifts',
    ),
    'Proph_Kryta': (
        'CursedLands',
        'KessexPeak',
        'NeboTerrace',
        'NorthKrytaProvince',
        'ScoundrelsRise',
        'StingrayStrand',
        'TalmarkWilderness',
        'TearsOfTheFallen',
        'TheBlackCurtain',
        'TwinSerpentLakes',
        'WatchtowerCoast',
    ),
    'Proph_Maguuma': (
        'DryTop',
        'EttinsBack',
        'MajestysRest',
        'MamnoonLagoon',
        'ReedBog',
        'SageLands',
        'Silverwood',
        'TangleRoot',
        'TheFalls',
    ),
    'Proph_NorthernShiverpeaks': (
        'AnvilRock',
        'DeldrimorBowl',
        'GriffonsMouth',
        'IronHorseMine',
        'TravelersVale',
    ),
    'Proph_RingOfFireIsland': (
        'PerditionRock',
    ),
    'Proph_SouthernShiverpeaks': (
        'DeldrimorBowl',
        'DreadnoughtsDrift',
        'FrozenForest',
        'GrenthsFootprint',
        'IceDome',
        'IceFloe',
        'LornarsPass',
        'MineralSprings',
        'SnakeDance',
        'SpearheadPeak',
        'TalusChute',
        'TascasDemise',
        'WitmansFolly',
    ),
}


class VanquishDefinition:
    """Immutable-by-convention data loaded from one PyQuish map module.

    Py4GW loads widgets through a dynamic module loader which does not always
    register the module in ``sys.modules`` before executing it.  Python 3.13's
    ``@dataclass`` implementation expects that registration while resolving
    postponed annotations, and otherwise crashes during widget import with
    ``AttributeError: 'NoneType' object has no attribute '__dict__'``.

    A small explicit container avoids that loader dependency entirely.
    """

    __slots__ = (
        'region',
        'map_name',
        'outpost_id',
        'explorable_id',
        'outpost_path',
        'vanquish_path',
        'transit_ids',
        'transit_paths',
    )

    def __init__(
        self,
        region: str,
        map_name: str,
        outpost_id: int,
        explorable_id: int,
        outpost_path: Sequence[Coordinate],
        vanquish_path: Sequence[object],
        transit_ids: Sequence[int],
        transit_paths: Sequence[Sequence[object]],
    ) -> None:
        self.region = region
        self.map_name = map_name
        self.outpost_id = outpost_id
        self.explorable_id = explorable_id
        self.outpost_path: list[Coordinate] = list(outpost_path)
        self.vanquish_path: list[object] = list(vanquish_path)
        self.transit_ids: tuple[int, ...] = tuple(transit_ids)
        self.transit_paths: tuple[list[object], ...] = tuple(list(path) for path in transit_paths)

    @property
    def display_name(self) -> str:
        return f'{self.region.replace("_", " ")} / {self.map_name}'


class SessionStats:
    def __init__(self) -> None:
        self.started_at = 0.0
        self.current_run_started_at = 0.0
        self.runs_attempted = 0
        self.runs_completed = 0
        self.runs_failed = 0
        self.run_times: list[float] = []

    def start_run(self) -> None:
        if self.current_run_started_at > 0.0:
            return
        now = time.monotonic()
        if self.started_at <= 0.0:
            self.started_at = now
        self.current_run_started_at = now
        self.runs_attempted += 1

    def complete_run(self) -> float:
        duration = self.current_run_time()
        if self.current_run_started_at > 0.0:
            self.runs_completed += 1
            self.run_times.append(duration)
        self.current_run_started_at = 0.0
        return duration

    def fail_run(self) -> float:
        duration = self.current_run_time()
        if self.current_run_started_at > 0.0:
            self.runs_failed += 1
        self.current_run_started_at = 0.0
        return duration

    def current_run_time(self) -> float:
        if self.current_run_started_at <= 0.0:
            return 0.0
        return time.monotonic() - self.current_run_started_at

    def total_time(self) -> float:
        if self.started_at <= 0.0:
            return 0.0
        return time.monotonic() - self.started_at


REGIONS = tuple(MAP_CATALOG)
region_index = 0
map_index = 0
loop_runs = False
auto_loot = True
forward_clear_radius = 2500
reverse_clear_radius_1 = 3500
reverse_clear_radius_2 = 5000

initialized = False
ini_key = ''
botting_tree: BottingTree | None = None
pending_rebuild = False
last_load_error = ''
stats = SessionStats()


def _selected_region() -> str:
    return REGIONS[max(0, min(region_index, len(REGIONS) - 1))]


def _selected_maps() -> tuple[str, ...]:
    return MAP_CATALOG[_selected_region()]


def _selected_map() -> str:
    maps = _selected_maps()
    return maps[max(0, min(map_index, len(maps) - 1))]


def _load_transit_data(module: object, map_name: str) -> tuple[tuple[int, ...], tuple[list[object], ...]]:
    ids = getattr(module, f'{map_name}_ids', {})
    transit_ids: list[int] = []
    transit_paths: list[list[object]] = []

    index = 1
    while True:
        id_key = 'transit_id' if index == 1 else f'transit_id{index}'
        path_name = f'{map_name}_transit_path' if index == 1 else f'{map_name}_transit_path{index}'
        transit_id = int(ids.get(id_key, 0) or 0)
        transit_path = getattr(module, path_name, None)

        if transit_id <= 0 and transit_path is None:
            break

        transit_ids.append(transit_id)
        transit_paths.append(list(transit_path or ()))
        index += 1

    return tuple(transit_ids), tuple(transit_paths)


def load_selected_definition() -> VanquishDefinition:
    region = _selected_region()
    map_name = _selected_map()
    module_name = f'{MAP_PACKAGE}.{region}.{map_name}'
    module = importlib.import_module(module_name)

    ids = getattr(module, f'{map_name}_ids', None)
    if not isinstance(ids, Mapping):
        # Compatibility with two legacy map files whose ID dictionary had an
        # unrelated variable name. The supplied hotfixes correct them, while
        # this fallback makes the BT script tolerant of an older map folder.
        candidates = [
            value
            for key, value in vars(module).items()
            if key.endswith('_ids') and isinstance(value, Mapping)
        ]
        if len(candidates) != 1:
            raise ValueError(f'No unambiguous ID dictionary found for {region}/{map_name}.')
        ids = candidates[0]

    outpost_id = int(ids.get('outpost_id', 0) or 0)
    explorable_id = int(ids.get('map_id', 0) or 0)
    outpost_path = list(getattr(module, f'{map_name}_outpost_path', ()) or ())
    vanquish_path = list(getattr(module, map_name, ()) or ())
    transit_ids, transit_paths = _load_transit_data(module, map_name)

    if outpost_id <= 0:
        raise ValueError(f'Invalid outpost ID for {region}/{map_name}.')
    if not vanquish_path:
        raise ValueError(f'No vanquish path found for {region}/{map_name}.')

    return VanquishDefinition(
        region=region,
        map_name=map_name,
        outpost_id=outpost_id,
        explorable_id=explorable_id,
        outpost_path=outpost_path,
        vanquish_path=vanquish_path,
        transit_ids=transit_ids,
        transit_paths=transit_paths,
    )


def _condition(name: str, condition_fn: Callable[[], bool]) -> BehaviorTree:
    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=name,
            condition_fn=condition_fn,
        )
    )


def _action(name: str, action_fn: Callable[[], BehaviorTree.NodeState]) -> BehaviorTree:
    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=name,
            action_fn=action_fn,
        )
    )


def _vanquish_completed() -> bool:
    return bool(Map.IsExplorable() and Map.IsVanquishable() and Map.IsVanquishCompleted())


def _completed_condition(name: str = 'VanquishCompleted') -> BehaviorTree:
    return _condition(name, _vanquish_completed)


def _skip_if_completed(child: BehaviorTree, name: str) -> BehaviorTree:
    return BT.Selector(
        name=f'SkipIfCompleted:{name}',
        children=[
            _completed_condition(name=f'AlreadyCompleted:{name}'),
            child,
        ],
    )


def _blessing_parameters(region: str) -> tuple[str | None, int]:
    if region == 'Factions_EchovaldForest':
        return 'kurzick', 0x86
    if region == 'Factions_TheJadeSea':
        return 'luxon', 0x86
    if region.startswith('Factions_'):
        return None, 0x86
    if region.startswith('NF_'):
        return None, 0x85
    if region.startswith('EOTN_'):
        return None, 0x84
    return None, 0x86


def _coordinate(value: object, field_name: str) -> Coordinate:
    if not isinstance(value, (tuple, list)) or len(value) < 2:
        raise ValueError(f'{field_name} must be a coordinate, got {value!r}.')

    x = value[0]
    y = value[1]
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        raise ValueError(f'{field_name} must contain numeric coordinates, got {value!r}.')
    return float(x), float(y)


def _coordinate_path(value: object, field_name: str) -> list[Coordinate]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f'{field_name} must be a coordinate path, got {value!r}.')
    return [_coordinate(point, f'{field_name}[{index}]') for index, point in enumerate(value)]


def _integer(value: object, field_name: str) -> int:
    if not isinstance(value, (int, float, str)):
        raise ValueError(f'{field_name} must be an integer-compatible value, got {value!r}.')
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{field_name} must be an integer-compatible value, got {value!r}.') from error


def _dialog_id(value: object) -> int | str:
    if isinstance(value, (int, str)):
        return value
    raise ValueError(f'dialog must be an int or string, got {value!r}.')


def _follow_model_parameters(value: object) -> tuple[int | str, float, int]:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError(f'followmodel must contain model, range and timeout, got {value!r}.')

    model_id = value[0]
    follow_range = value[1]
    timeout_ms = value[2]
    if not isinstance(model_id, (int, str)):
        raise ValueError(f'followmodel model must be an int or string, got {model_id!r}.')
    if not isinstance(follow_range, (int, float)):
        raise ValueError(f'followmodel range must be numeric, got {follow_range!r}.')
    return model_id, float(follow_range), _integer(timeout_ms, 'followmodel timeout')


def _build_keyword_action(
    definition: VanquishDefinition,
    key: str,
    value: object,
    clear_radius: float,
    combat_path: bool,
    skip_when_completed: bool,
) -> list[BehaviorTree]:
    children: list[BehaviorTree] = []

    if key == 'path':
        path = _coordinate_path(value, 'path')
        if combat_path:
            for point_index, point in enumerate(path):
                child = BT.VanquishNode(
                    [point],
                    clear_area_radius=clear_radius,
                    flag_heroes_to_waypoint=False,
                    name=f'VanquishPoint:{point_index}',
                    log=False,
                )
                if skip_when_completed:
                    child = _skip_if_completed(child, f'PathPoint:{point_index}')
                children.append(child)
        elif path:
            children.append(BT.Move(path, pause_on_combat=True, log=False))
        return children

    if key == 'bless':
        faction, dialog_id = _blessing_parameters(definition.region)
        child = BT.TakeBlessing(
            pos=_coordinate(value, 'bless'),
            faction=faction,
            blessing_dialog_id=dialog_id,
            multi_account=False,
            log=True,
        )
    elif key == 'gadget':
        child = BT.MoveAndInteractWithGadget(
            pos=_coordinate(value, 'gadget'),
            interaction_count=1,
            multi_account=False,
            log=True,
        )
    elif key == 'npc':
        child = BT.MoveAndInteract(
            pos=_coordinate(value, 'npc'),
            target_distance=Range.Nearby.value,
            log=True,
        )
    elif key == 'dialog':
        child = BT.SendDialog(dialog_id=_dialog_id(value), multi_account=False, log=True)
    elif key == 'wait':
        child = BT.Wait(duration_ms=_integer(value, 'wait'), log=False)
    elif key == 'map':
        child = BT.WaitForMapLoad(map_id=_integer(value, 'map'), timeout_ms=45_000)
    elif key == 'dropbundle':
        child = BT.DropBundle(log=True)
    elif key == 'followmodel':
        model_id, follow_range, timeout_ms = _follow_model_parameters(value)
        child = BT.FollowModel(
            modelID_or_encStr=model_id,
            follow_range=follow_range,
            timeout_ms=timeout_ms,
            log=True,
        )
    else:
        raise ValueError(f'Unsupported PyQuish map keyword: {key!r}.')

    if skip_when_completed:
        child = _skip_if_completed(child, key)
    children.append(child)
    return children


def _iter_segment_items(segment: object) -> list[tuple[str, object]]:
    if isinstance(segment, Mapping):
        return [(str(key), value) for key, value in segment.items()]
    if isinstance(segment, list):
        items: list[tuple[str, object]] = []
        for entry in segment:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError(f'Invalid tuple-list map segment: {entry!r}.')
            items.append((str(entry[0]), entry[1]))
        return items
    raise ValueError(f'Invalid structured map segment: {segment!r}.')


def _is_coordinate(value: object) -> bool:
    return (
        isinstance(value, (tuple, list))
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    )


def _is_plain_path(path: Sequence[object]) -> bool:
    return bool(path) and all(_is_coordinate(point) for point in path)


def _build_path_tree(
    definition: VanquishDefinition,
    path: Sequence[object],
    *,
    name: str,
    clear_radius: float,
    combat_path: bool,
    skip_when_completed: bool,
) -> BehaviorTree:
    children: list[BehaviorTree] = []

    if _is_plain_path(path):
        children.extend(
            _build_keyword_action(
                definition,
                'path',
                path,
                clear_radius,
                combat_path,
                skip_when_completed,
            )
        )
    else:
        for segment in path:
            for key, value in _iter_segment_items(segment):
                children.extend(
                    _build_keyword_action(
                        definition,
                        key,
                        value,
                        clear_radius,
                        combat_path,
                        skip_when_completed,
                    )
                )

    if not children:
        return BT.Succeeder(name=f'{name}:Empty')
    return BT.Sequence(name=name, children=children)


def _reverse_path(path: Sequence[object]) -> list[object]:
    if _is_plain_path(path):
        return list(reversed(path))

    reversed_segments: list[object] = []
    for segment in reversed(path):
        items = list(reversed(_iter_segment_items(segment)))
        reversed_items = [
            (key, list(reversed(value)) if key == 'path' and isinstance(value, Sequence) else value)
            for key, value in items
        ]
        reversed_segments.append(reversed_items)
    return reversed_segments


def _build_transit_tree(definition: VanquishDefinition) -> BehaviorTree:
    children: list[BehaviorTree] = []

    if definition.outpost_path:
        first_target = definition.explorable_id
        if definition.transit_ids and definition.transit_ids[0] > 0:
            first_target = definition.transit_ids[0]
        if first_target <= 0:
            raise ValueError(f'No target map ID for the outpost exit of {definition.display_name}.')
        children.append(
            BT.MoveAndExitMap(
                definition.outpost_path,
                target_map_id=first_target,
                timeout_ms=45_000,
                log=True,
            )
        )

    for index, transit_path in enumerate(definition.transit_paths):
        next_map_id = definition.explorable_id
        if index + 1 < len(definition.transit_ids) and definition.transit_ids[index + 1] > 0:
            next_map_id = definition.transit_ids[index + 1]

        if _is_plain_path(transit_path) and next_map_id > 0:
            transit_move_path = _coordinate_path(transit_path, f'transit path {index + 1}')
            children.append(
                BT.MoveAndExitMap(
                    transit_move_path,
                    target_map_id=next_map_id,
                    timeout_ms=45_000,
                    log=True,
                )
            )
            continue

        children.append(
            _build_path_tree(
                definition,
                transit_path,
                name=f'TransitPath:{index + 1}',
                clear_radius=0.0,
                combat_path=False,
                skip_when_completed=False,
            )
        )
        if next_map_id > 0:
            children.append(BT.WaitForMapLoad(map_id=next_map_id, timeout_ms=45_000))

    if not children:
        return BT.Succeeder(name='NoTransitRequired')
    return BT.Sequence(name='TravelToVanquishMap', children=children)


def _mark_run_started() -> BehaviorTree.NodeState:
    stats.start_run()
    PySystem.Console.Log(
        MODULE_NAME,
        f'Starting vanquish: {_selected_region()}/{_selected_map()}.',
        PySystem.Console.MessageType.Info,
    )
    return BehaviorTree.NodeState.SUCCESS


def _mark_run_completed() -> BehaviorTree.NodeState:
    duration = stats.complete_run()
    PySystem.Console.Log(
        MODULE_NAME,
        f'Vanquish completed in {_format_time(duration)}.',
        PySystem.Console.MessageType.Success,
    )
    return BehaviorTree.NodeState.SUCCESS


def _build_completion_fallback() -> BehaviorTree:
    return BT.Sequence(
        name='VanquishIncomplete',
        children=[
            BT.LogMessage(
                message=(
                    'The vanquish is still incomplete after both cleanup sweeps. '
                    'Restarting the cleanup step from the current map.'
                ),
                module_name=MODULE_NAME,
            ),
            BT.Failer(name='RetryCleanupSweeps'),
        ],
    )


def _build_run_preparation(definition: VanquishDefinition) -> BehaviorTree:
    return BT.Sequence(
        name=f'Prepare:{definition.map_name}',
        map_id_or_name=definition.outpost_id,
        hard_mode=True,
        children=[
            ensure_botting_tree().Config.Aggressive(
                multi_account=False,
                auto_loot=auto_loot,
                resurrection_scroll=False,
            ),
            _action('RecordRunStart', _mark_run_started),
            _build_transit_tree(definition),
        ],
    )


def _build_forward_point(
    definition: VanquishDefinition,
    point: Coordinate,
    point_number: int,
) -> BehaviorTree:
    child = BT.VanquishNode(
        [point],
        clear_area_radius=float(forward_clear_radius),
        flag_heroes_to_waypoint=False,
        name=f'ForwardPoint:{point_number}',
        log=False,
    )
    return _skip_if_completed(child, f'ForwardPoint:{point_number}')


def _build_forward_action(
    definition: VanquishDefinition,
    key: str,
    value: object,
    action_number: int,
) -> BehaviorTree:
    children = _build_keyword_action(
        definition,
        key,
        value,
        clear_radius=float(forward_clear_radius),
        combat_path=True,
        skip_when_completed=True,
    )
    if not children:
        return BT.Succeeder(name=f'ForwardAction:{action_number}:Empty')
    return BT.Sequence(
        name=f'ForwardAction:{action_number}:{key}',
        children=children,
    )


def _build_cleanup_sweeps(definition: VanquishDefinition) -> BehaviorTree:
    reverse_path = _reverse_path(definition.vanquish_path)
    reverse_1 = _build_path_tree(
        definition,
        reverse_path,
        name='ReverseVanquishPass1',
        clear_radius=float(reverse_clear_radius_1),
        combat_path=True,
        skip_when_completed=True,
    )
    reverse_2 = _build_path_tree(
        definition,
        reverse_path,
        name='ReverseVanquishPass2',
        clear_radius=float(reverse_clear_radius_2),
        combat_path=True,
        skip_when_completed=True,
    )

    completion = BT.Selector(
        name='CompleteOrSweepAgain',
        children=[
            _completed_condition('CompletedAfterForwardPass'),
            BT.Sequence(
                name='FirstReverseSweep',
                children=[
                    reverse_1,
                    _completed_condition('CompletedAfterReversePass1'),
                ],
            ),
            BT.Sequence(
                name='SecondReverseSweep',
                children=[
                    reverse_2,
                    BT.Selector(
                        name='ValidateFinalSweep',
                        children=[
                            _completed_condition('CompletedAfterReversePass2'),
                            _build_completion_fallback(),
                        ],
                    ),
                ],
            ),
        ],
    )
    return completion


def _build_run_completion(definition: VanquishDefinition) -> BehaviorTree:
    return BT.Sequence(
        name=f'Complete:{definition.map_name}',
        children=[
            _action('RecordRunCompletion', _mark_run_completed),
            BT.Resign(
                wait_for_map_load=True,
                target_map_id=definition.outpost_id,
                multi_account=False,
                log=True,
            ),
        ],
    )


def get_execution_steps(definition: VanquishDefinition) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        (
            f'Prepare {definition.map_name}',
            lambda definition=definition: _build_run_preparation(definition),
        ),
    ]

    point_number = 0
    action_number = 0
    path_items: list[tuple[str, object]] = []
    if _is_plain_path(definition.vanquish_path):
        path_items.append(('path', definition.vanquish_path))
    else:
        for segment in definition.vanquish_path:
            path_items.extend(_iter_segment_items(segment))

    for key, value in path_items:
        if key == 'path':
            points = _coordinate_path(value, 'vanquish path')
            for point in points:
                point_number += 1
                current_point_number = point_number
                steps.append(
                    (
                        f'Point {current_point_number}',
                        lambda definition=definition, point=point, point_number=current_point_number: _build_forward_point(
                            definition,
                            point,
                            point_number,
                        ),
                    )
                )
            continue

        action_number += 1
        current_action_number = action_number
        steps.append(
            (
                f'Action {current_action_number}: {key}',
                lambda definition=definition, key=key, value=value, action_number=current_action_number: _build_forward_action(
                    definition,
                    key,
                    value,
                    action_number,
                ),
            )
        )

    steps.extend(
        [
            (
                'Cleanup sweeps',
                lambda definition=definition: _build_cleanup_sweeps(definition),
            ),
            (
                'Complete and return',
                lambda definition=definition: _build_run_completion(definition),
            ),
        ]
    )
    return steps


def ensure_botting_tree() -> BottingTree:
    global botting_tree
    global last_load_error

    if botting_tree is None:
        definition = load_selected_definition()
        last_load_error = ''
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(definition),
            routine_name='PyQuishAISequence',
            repeat=loop_runs,
            reset=False,
            multi_account=False,
            auto_loot=auto_loot,
            configure_fn=lambda tree: tree.Config.ConfigureUpkeep(
                looting_enabled=auto_loot,
                resurrection_scroll=False,
                enable_party_wipe_recovery=True,
                heroai_state_logging=True,
                heroai_state_log_interval_ms=5000,
            ),
        )
        botting_tree.UI.override_draw_help(_draw_help)

    return botting_tree


def _request_rebuild() -> None:
    global pending_rebuild
    pending_rebuild = True


def _apply_pending_rebuild() -> None:
    global botting_tree
    global pending_rebuild
    global last_load_error

    if not pending_rebuild:
        return
    if botting_tree is not None and botting_tree.IsStarted():
        return

    if botting_tree is not None:
        botting_tree.Stop()
    botting_tree = None
    pending_rebuild = False

    try:
        ensure_botting_tree()
    except Exception as error:
        last_load_error = str(error)
        PySystem.Console.Log(
            MODULE_NAME,
            f'Failed to rebuild the selected map: {error}',
            PySystem.Console.MessageType.Error,
        )


def _draw_config() -> None:
    global region_index
    global map_index
    global loop_runs
    global auto_loot
    global forward_clear_radius
    global reverse_clear_radius_1
    global reverse_clear_radius_2

    tree = botting_tree
    locked = bool(tree is not None and tree.IsStarted())
    PyImGui.text('Region and map')
    PyImGui.separator()
    if locked:
        PyImGui.text_colored('Stop the bot before changing the map.', (255, 190, 80, 255))

    PyImGui.begin_disabled(locked)
    new_region_index = PyImGui.combo('Region', region_index, list(REGIONS))
    if new_region_index != region_index:
        region_index = new_region_index
        map_index = 0
        _request_rebuild()

    maps = _selected_maps()
    map_index = max(0, min(map_index, len(maps) - 1))
    new_map_index = PyImGui.combo('Map', map_index, list(maps))
    if new_map_index != map_index:
        map_index = new_map_index
        _request_rebuild()

    PyImGui.separator()
    new_loop_runs = PyImGui.checkbox('Repeat completed vanquish', loop_runs)
    if new_loop_runs != loop_runs:
        loop_runs = new_loop_runs
        _request_rebuild()

    new_auto_loot = PyImGui.checkbox('Automatic looting', auto_loot)
    if new_auto_loot != auto_loot:
        auto_loot = new_auto_loot
        _request_rebuild()

    PyImGui.separator()
    PyImGui.text('Enemy sweep radii')
    new_forward = max(1200, min(5000, PyImGui.input_int('Forward pass', forward_clear_radius)))
    new_reverse_1 = max(1200, min(5000, PyImGui.input_int('Reverse pass 1', reverse_clear_radius_1)))
    new_reverse_2 = max(1200, min(5000, PyImGui.input_int('Reverse pass 2', reverse_clear_radius_2)))
    if (new_forward, new_reverse_1, new_reverse_2) != (
        forward_clear_radius,
        reverse_clear_radius_1,
        reverse_clear_radius_2,
    ):
        forward_clear_radius = new_forward
        reverse_clear_radius_1 = new_reverse_1
        reverse_clear_radius_2 = new_reverse_2
        _request_rebuild()
    PyImGui.end_disabled()

def _draw_help() -> None:
    PyImGui.text_wrapped('PyQuishAI rebuilt on BottingTree and BehaviorTree nodes only. No legacy FSM is used.')
    PyImGui.separator()
    PyImGui.text_wrapped('Select a map in Config, then start it from the Main tab.')
    PyImGui.text_wrapped('Every route coordinate is a named planner step: Point 1, Point 2, and so on.')
    PyImGui.text_wrapped('A failed movement or party-wipe recovery restarts the current point instead of the full route.')
    PyImGui.text_wrapped('Choose the Prepare step in Navigation to force a complete restart from the outpost.')
    PyImGui.text_wrapped('The bot performs the forward route, followed by up to two reverse sweeps if foes remain.')


def _format_time(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


def _draw_run_status() -> None:
    PyImGui.text(f'Selected: {_selected_region()} / {_selected_map()}')
    if last_load_error:
        PyImGui.text_colored(f'Load error: {last_load_error}', (255, 80, 80, 255))

    if Map.IsExplorable() and Map.IsVanquishable():
        killed = int(Map.GetFoesKilled() or 0)
        remaining = int(Map.GetFoesToKill() or 0)
        total = killed + remaining
        progress = (100.0 * killed / total) if total > 0 else 100.0
        PyImGui.text(f'Vanquish: {killed} / {total} ({progress:.1f}%)')

    PyImGui.text(f'Current run: {_format_time(stats.current_run_time())}')
    PyImGui.text(f'Session: {_format_time(stats.total_time())}')
    PyImGui.text(f'Runs: {stats.runs_completed} completed / {stats.runs_attempted} attempted')
    if stats.runs_failed:
        PyImGui.text(f'Incomplete paths: {stats.runs_failed}')
    if stats.run_times:
        average = sum(stats.run_times) / len(stats.run_times)
        PyImGui.text(f'Best: {_format_time(min(stats.run_times))}')
        PyImGui.text(f'Average: {_format_time(average)}')
        PyImGui.text(f'Worst: {_format_time(max(stats.run_times))}')


def _freeze_stopped_run(tree: BottingTree) -> None:
    if stats.current_run_started_at <= 0.0 or tree.IsStarted():
        return
    stats.fail_run()


def main() -> None:
    global initialized
    global ini_key
    global last_load_error

    if not initialized:
        if not ini_key:
            ini_key = Settings(f'{INI_PATH}/{INI_FILENAME}', 'account').name
            if not ini_key:
                return
        try:
            ensure_botting_tree()
        except Exception as error:
            last_load_error = str(error)
            PySystem.Console.Log(
                MODULE_NAME,
                f'Initialization failed: {error}',
                PySystem.Console.MessageType.Error,
            )
            return
        initialized = True

    _apply_pending_rebuild()
    tree = ensure_botting_tree()
    tree.tick()
    _freeze_stopped_run(tree)
    tree.UI.draw_window(
        icon_path=TEXTURE,
        additional_ui=_draw_run_status,
        extra_tabs=[
            ('Config', _draw_config),
        ],
    )


if __name__ == '__main__':
    main()