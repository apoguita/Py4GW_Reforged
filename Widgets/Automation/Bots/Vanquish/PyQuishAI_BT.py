from __future__ import annotations

import importlib
import math
import os
import random
import time
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any
from typing import NamedTuple
from typing import TypeAlias

import PyImGui
import PySystem

from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.AgentArray import AgentArray
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.enums import HeroType
from Py4GWCoreLib.enums import Range
from Py4GWCoreLib.enums import SharedCommandType
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.enums_src.Region_enums import District
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import (
    CONSET_UPKEEPS,
    CONSUMABLE_UPKEEPS,
)
from Py4GWCoreLib.routines_src.Agents import Agents as RoutinesAgents
from Py4GWCoreLib.routines_src.Checks import Checks
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Sources.ApoSource.ApoBottingLib import wrappers as BT


MODULE_NAME = 'PyQuishAI BT'
MODULE_ICON = 'Assets/Textures/Module_Icons/PyQuishAI.png'
MODULE_CATEGORY = 'Automation'
MODULE_TAGS = ['Bot', 'Vanquish', 'BehaviorTree']

INI_PATH = 'Widgets/Automation/Bots/Vanquish/PyQuishAI_BT'
INI_FILENAME = 'PyQuishAI_BT.ini'
# Folder this widget lives in, derived from the INI path it already owns, so
# the enemy log written at the end of a run lands next to the widget.
WIDGET_DIR = os.path.dirname(INI_PATH)
MAP_PACKAGE = 'Sources.aC_Scripts.PyQuishAI_maps'
TEXTURE = os.path.join(
    PySystem.Console.get_projects_path(),
    'Sources',
    'ApoSource',
    'textures',
    'VQ_Helmet.png',
)

# Vanquish staging: Embark Beach is where the vanquish signposts live. In an
# outpost the followers do not walk after the leader, so the dialog fan-out is
# what moves them. Travel itself stays local: a formed party travels with its
# leader.
EMBARK_BEACH_MAP_ID = 857
GREAT_TEMPLE_MAP_ID = 248
# Anchor for the vanquish signpost in Embark Beach. It ranks the named signposts
# and doubles as the fallback point when the name cannot be resolved.
VANQUISH_SIGNPOST: tuple[float, float] = (-428.0, -3439.0)
# Embark Beach holds several signposts, so the target is resolved by name and
# then narrowed to the one nearest the player instead of using a fixed spot.
ZQUEST_SIGNPOST_NAME = 'vanquish'
# The quest reward NPC in the Great Temple of Balthazar is "Zehnchu [Zaishen
# Challenge]". Its agent id changes between maps and sessions and it stands among
# other NPCs, so it is resolved by that unique name; the coordinate is kept only
# as the fallback point for the point-based node.
ZQUEST_REWARD_NPC: tuple[float, float] = (-5019.0, -5496.0)
ZQUEST_REWARD_NPC_NAME = 'zehnchu'
# Staging district. Pick one at random per travel so the party is spread over
# the low-traffic channels instead of piling into a single one. Only the district
# channel is used; the instance number stays at 0.
STAGING_DISTRICTS: tuple[int, ...] = (
    District.EuropeItalian.value,
    District.EuropeSpanish.value,
    District.EuropePolish.value,
    District.EuropeRussian.value,
)
# 0-based button pressed on the signpost dialog; the vanquish selector may need
# another entry once the real list is known.
ZQUEST_DIALOG_BUTTON = 0
# Acknowledgement budget for the shared-message commands; a healthy client
# answers in well under a second.
ZQUEST_MESSAGE_TIMEOUT_MS = 10_000
# Time allowed for the signpost to show up in the agent array before falling
# back to the leader-first approach.
ZQUEST_AGENT_WAIT_MS = 5_000
# Every account walks to the signpost on its own; this only bounds a wedged one.
ZQUEST_DIALOG_TIMEOUT_MS = 100_000
# Settle after the dialog before the next step travels: a map change cancels an
# open dialog, and the handler marks its message finished as soon as it presses.
ZQUEST_DIALOG_SETTLE_MS = 500
# Automatic ZQuest handling names the area from the quest the signpost hands
# over, so its text has to be requested and polled for.
ZQUEST_QUEST_RESOLVE_TIMEOUT_MS = 20_000
ZQUEST_QUEST_TEXT_POLL_MS = 500
# `BT.Resign` raises `party_wipe_recovery_suppressed` while it works, and the core
# recovery service that the planner installs unconditionally reads it. This widget
# keeps that flag raised for the whole session (so the core service never acts) and
# uses its own key to mark the resign, which is what its own recovery honours. The
# cap clears the key left behind by a reset in the middle of a resign.
RECOVERY_SUPPRESS_TIMEOUT_MS = 90_000
_RESIGNING_KEY = 'zquest_resigning'

# Consumable upkeep. The core list already separates the conset trio from the
# plain pcons, so the same split the Reputation Farmer uses is reused here
# rather than hard-coding model IDs a second time.
PCON_UPKEEPS: tuple[int, ...] = tuple(
    int(model_id) for model_id in CONSUMABLE_UPKEEPS if int(model_id) not in CONSET_UPKEEPS
)

CONSET_MODEL_IDS: tuple[int, ...] = tuple(int(model_id) for model_id in CONSET_UPKEEPS)

# Built once: `_display_name` runs for every consumable row on every frame, and
# a linear scan over the ~2.4k ModelID members per call is real UI cost.
_MODEL_DISPLAY_NAMES: dict[int, str] = {
    int(member.value): member.name.replace('_', ' ').replace(' Of ', ' of ')
    for member in ModelID
}


def _display_name(model_id: int) -> str:
    """Human label for a consumable model.

    The enum member name is the single owner of a readable identifier here.
    `CONSUMABLE_UPKEEP_PRESETS` is keyed by preset slug rather than model ID, so
    it cannot answer a reverse lookup without rebuilding an index the core
    already declines to expose.
    """
    return _MODEL_DISPLAY_NAMES.get(int(model_id), f'Model {model_id}')


# Selection state, populated by `_load_settings`. Defaults mirror the previous
# all-on behaviour so an existing INI keeps working unchanged.
_selected_conset: set[int] = set(CONSET_MODEL_IDS)
_selected_pcons: set[int] = set(PCON_UPKEEPS)

# Models whose upkeep is a party-morale rule rather than an effect upkeep: the
# service drinks them on a morale threshold, so they are worth flagging in the
# UI instead of presenting every row as interchangeable.
PARTY_MORALE_MODEL_IDS: frozenset[int] = frozenset(
    {
        int(ModelID.Honeycomb.value),
    }
)

# Storage restock targets pulled into bags before each run. `allow_missing` is
# on at the tree level, so an item the player simply does not own is skipped
# instead of failing the run.
CONSUMABLE_RESTOCK_QUANTITY = 10
SCROLL_OF_RESURRECTION_RESTOCK_QUANTITY = 25
RESTOCK_SETTLE_MS = 750
REMOTE_RESTOCK_TIMEOUT_MS = 15000
# Party forming at the start of a run: disband, summon the group to the leader's
# map and invite. Summon and invite share this budget per account batch.
REMOTE_PARTY_TIMEOUT_MS = 15_000
# Character gold kept on every account during the Prepare step. The shared
# command reused here equalizes in both directions: it deposits the excess and
# pulls from storage when the character is short.
KEEP_GOLD_AMOUNT = 10_000
REMOTE_KEEP_GOLD_TIMEOUT_MS = 15_000
# Outpost exit and intermediate travels share the same budget.
TRANSIT_TIMEOUT_MS = 45_000
CONSUMABLE_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple(
    (int(model_id), CONSUMABLE_RESTOCK_QUANTITY)
    for model_id in CONSUMABLE_UPKEEPS
) + (
    (int(ModelID.Scroll_Of_Resurrection.value), SCROLL_OF_RESURRECTION_RESTOCK_QUANTITY),
)

_SETTINGS_SECTION = 'Settings'
_KEY_RESTOCK_CONSET = 'RestockConset'
_KEY_ACTIVATE_CONSET = 'ActivateConset'
_KEY_RESTOCK_PCONS = 'RestockPcons'
_KEY_ACTIVATE_PCONS = 'ActivatePcons'
_KEY_SELECTED_CONSET = 'SelectedConsets'
_KEY_SELECTED_PCONS = 'SelectedPcons'
_KEY_RESTOCK_SCROLL_OF_RESURRECTION = 'RestockScrollOfResurrection'
_KEY_RESTOCK_MULTI_ACCOUNT = 'RestockMultiAccount'
_KEY_KEEP_GOLD_ON_ACCOUNTS = 'KeepGoldOnAccounts'
_KEY_AUTOMATIC_ZQUEST = 'AutomaticZQuestHandling'
_KEY_ENEMY_LOG = 'EnemyLog'
_KEY_QUEUE_ITEMS = 'VanquishQueue'
_KEY_PARTY_PLAN_4 = 'PartyPlan4'
_KEY_PARTY_PLAN_6 = 'PartyPlan6'
_KEY_PARTY_PLAN_8 = 'PartyPlan8'

MAP_ROOT = os.path.join(
    PySystem.Console.get_projects_path(),
    'Sources',
    'aC_Scripts',
    'PyQuishAI_maps',
)

# Enemy log: what the party actually walked past, appended run by run next to the
# widget. Only the leader runs this widget, so there is a single writer. The map
# modules stay the source of truth for the route, so this file is the evidence
# used to move or add points: an enemy logged during the sweeps is one the
# forward pass never cleared, and where it stood says which point to fix.
# It is a history, not a snapshot: every finished run appends its own block, so a
# week of runs can be reviewed together.
ENEMY_LOG_FILENAME = 'PyQuishAI_BT_enemy_log.txt'
ENEMY_LOG_DOCUMENT_HEADER = (
    '# PyQuishAI_BT enemy log\n'
    '# One block per finished run, appended oldest first. Do not edit by hand.\n'
)
ENEMY_LOG_SAMPLE_MS = 250
# Widest radius the game and the sweep configuration allow. The log is not a copy
# of what a step was going to clear: it wants every enemy the client knows about,
# so the map can be routed from where the foes actually stand.
ENEMY_LOG_RADIUS = 10000.0
# Cell used to tell a recycled agent id from the same enemy having moved. Nothing
# stops a wandering foe from crossing a cell, so this has to be wide: at 1 km one
# patrol produced three rows for the same agent.
ENEMY_LOG_ID_CELL = 3000.0
# A map holds a few hundred enemies and a sweep leaves a handful, so this is a
# runaway guard, not a budget.
ENEMY_LOG_MAX_RECORDS = 5000
# Planner step name of the reverse passes; the phase of every other route step is
# read from the map id its name carries.
SWEEP_STEP_NAME = 'Cleanup sweeps'


def _scan_map_catalog() -> dict[str, tuple[str, ...]]:
    """Build the region -> map catalog from the map pack on disk.

    Runs once per widget load, so adding or removing a map file only needs a
    widget reload. Regions are the subfolders, maps are their `.py` files;
    `__init__.py`, private files and `__pycache__` are skipped. An empty region
    folder is dropped so the map combo never resolves to nothing.
    """
    catalog: dict[str, tuple[str, ...]] = {}
    try:
        with os.scandir(MAP_ROOT) as region_entries:
            regions = sorted(region_entries, key=lambda entry: entry.name)
    except OSError:
        return catalog

    for region_entry in regions:
        if not region_entry.is_dir() or region_entry.name == '__pycache__':
            continue
        try:
            with os.scandir(region_entry.path) as file_entries:
                files = sorted(file_entries, key=lambda entry: entry.name)
        except OSError:
            continue
        maps = tuple(
            os.path.splitext(entry.name)[0]
            for entry in files
            if entry.is_file()
            and entry.name.endswith('.py')
            and not entry.name.startswith('_')
        )
        if maps:
            catalog[region_entry.name] = maps
    return catalog


# The map modules stay the source of truth for paths and identifiers; this index
# is only the discovery layer the UI walks.
MAP_CATALOG: dict[str, tuple[str, ...]] = _scan_map_catalog()

Coordinate: TypeAlias = tuple[float, float]


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
loaded_region_index = 0
loaded_map_index = 0
loop_runs = False
# Looting is not a choice in this widget: a vanquish leaves drops along the whole
# route, and turning it off only leaves them on the ground.
AUTO_LOOT = True
# Taking the signpost quest only makes sense together with automatic handling, so
# this is derived from it by `_sync_take_zquest` and has no switch of its own.
take_zquest = True
# Automatic ZQuest handling: the map is the one the signpost quest names, so the
# plan is built from the quest text read after the dialog instead of from the
# combo. `_auto_definition` holds the definition resolved this run and
# `_pending_planner_swap` asks the widget loop to replace the discovery steps.
automatic_zquest = False
_auto_definition: VanquishDefinition | None = None
# The Zaishen Vanquish quest id the signpost handed this run, read back from the
# active quest while resolving. Only the main account runs this widget, and only
# it needs the id: it is what gets abandoned on the accounts the Party Config
# plan leaves out.
_active_vanquish_quest_id: int = 0
_pending_planner_swap = False
forward_clear_radius = 3000
reverse_clear_radius_1 = 10000
reverse_clear_radius_2 = 10000
# Route work needs the enemy log; a normal run does not, so it is off by default
# and switched on from Config. Off means nothing is sampled and nothing is written.
enemy_log_enabled = False
# Vanquish queue: a list of (region, map name) walked one after another. Every
# entry repeats Prepare, route, sweeps and Complete with its resign, so the party
# lands in an outpost and travels to the next map; each Prepare rebuilds the group
# at that map's outpost, and no Form Party step runs.
# There is no separate switch: a queue with maps in it is a queue run, and an
# empty queue runs the map selected in the combos. Because the queue owns the plan
# shape, the signpost flows are disabled whenever it has entries.
vanquish_queue: list[tuple[str, str]] = []

# Party Config: which alts to invite, per party size the vanquish outpost offers.
# Keyed by size, and each list holds one entry per invited slot (the leader fills
# the remaining one). An empty list means "not configured" and keeps the previous
# behaviour of inviting every account already on the map, so an untouched tab
# changes nothing.
PARTY_SIZES: tuple[int, ...] = (4, 6, 8)
_party_plans: dict[int, list[str]] = {size: [] for size in PARTY_SIZES}

# A plan slot holds either an account email or a hero, prefixed so the two id
# spaces cannot be confused: 'hero:24' is Gwen, 'g@example.com' is an account.
_HERO_PREFIX = 'hero:'
# Every hero the client knows, offered whether or not this account unlocked it:
# there is no unlock query to filter on, so the load step reports what the party
# did not receive instead of hiding the choice.
HERO_CHOICES: tuple[int, ...] = tuple(int(hero) for hero in HeroType if int(hero) > 0)

# Consumable upkeep state (persisted per account, same keys as the other BTs).
_settings = Settings(f'{INI_PATH}/{INI_FILENAME}', 'account')
_settings_loaded = False
_restock_conset = True
_activate_conset = True
_restock_pcons = True
_activate_pcons = True
_restock_scroll_of_resurrection = True
_restock_multi_account = True
_keep_gold_on_accounts = True

initialized = False
ini_key = ''
botting_tree: BottingTree | None = None
pending_rebuild = False
_stop_after_sweeps = False
last_load_error = ''
stats = SessionStats()


class EnemyLogRecord(NamedTuple):
    """One enemy the party came close to, as seen during a route step.

    The row is the raw observation: who, where, and how close the party got,
    plus the step it happened in and the party position. Note when reading it
    that `player_x/player_y` describe the chase and not the route: the clear
    loop targets enemies inside its own circle, so the party can be nearly 3 km
    from the waypoint the step names. The route review measures against the map
    points, not against those coordinates.
    """

    phase: str
    step: str
    map_id: int
    agent_id: int
    player_x: float
    player_y: float
    enemy_x: float
    enemy_y: float
    distance: float


# Records are deduplicated per enemy, not per position: enemies wander, so a
# grid key turned one patrolling foe into a row per 100 u cell. The kept sample
# is the closest approach, which is the distance a new or moved route point
# would have to beat. The coarse cell stays in the key only because the game
# recycles agent ids: the same id seen a kilometre away is another agent.
_enemy_log_records: dict[tuple[int, int, int, int, str], EnemyLogRecord] = {}
_enemy_log_active = False
_enemy_log_started_at = ''
_enemy_log_finished_at = ''
_enemy_log_last_sample_ms = 0.0
_enemy_log_map_id = 0
_enemy_log_label = ''
_enemy_log_dropped = 0


def _enemy_log_path() -> str:
    """Path of the enemy log, next to this widget."""
    return os.path.join(PySystem.Console.get_projects_path(), WIDGET_DIR, ENEMY_LOG_FILENAME)


def _enemy_log_begin(definition: VanquishDefinition) -> None:
    """Start collecting for one run, discarding what the previous run left."""
    global _enemy_log_records
    global _enemy_log_active
    global _enemy_log_started_at
    global _enemy_log_finished_at
    global _enemy_log_last_sample_ms
    global _enemy_log_map_id
    global _enemy_log_label
    global _enemy_log_dropped

    _enemy_log_records = {}
    if not enemy_log_enabled:
        # Config has the log switched off: nothing is collected this run, so the
        # flush at the end has nothing to write.
        _enemy_log_active = False
        return
    _enemy_log_active = True
    _enemy_log_started_at = time.strftime('%Y-%m-%d %H:%M:%S')
    _enemy_log_finished_at = ''
    _enemy_log_last_sample_ms = 0.0
    _enemy_log_map_id = _vanquish_route_map_id(definition)
    _enemy_log_label = f'{definition.region}/{definition.map_name}'
    _enemy_log_dropped = 0


def _step_name_map_id(step_name: str) -> int:
    """Map id carried by a `Point N (map M)` / `Action N: label (map M)` name."""
    start = step_name.rfind('(map ')
    if start < 0 or not step_name.endswith(')'):
        return 0
    raw = step_name[start + 5:-1].strip()
    return int(raw) if raw.isdigit() else 0


def _enemy_log_phase(step_name: str) -> str:
    """`forward` or `sweep` for a route step, empty for everything else.

    The current step name is all the planner publishes, and it already carries
    the map the step walks in. Only the two phases that clear the vanquish map
    are logged: a route step in another map is a transit leg, and party forming,
    preparation and completion are not route work at all.
    """
    if step_name == SWEEP_STEP_NAME or step_name.startswith(f'{SWEEP_STEP_NAME} '):
        return 'sweep'
    map_id = _step_name_map_id(step_name)
    if map_id <= 0:
        return ''
    if _enemy_log_map_id and map_id != _enemy_log_map_id:
        return ''
    return 'forward'


def _sample_enemy_log(tree: BottingTree) -> None:
    """Record the living enemies around the leader for the step in progress."""
    global _enemy_log_last_sample_ms
    global _enemy_log_dropped

    if not _enemy_log_active or not enemy_log_enabled:
        return

    now = time.monotonic() * 1000.0
    if _enemy_log_last_sample_ms > 0.0 and now - _enemy_log_last_sample_ms < ENEMY_LOG_SAMPLE_MS:
        return
    _enemy_log_last_sample_ms = now

    # The planner marks the active step in the root blackboard before ticking it,
    # so reading it right after the tick names the step that just ran.
    try:
        step_name = str(tree.GetBlackboardValue('current_step_name', '') or '')
    except Exception:
        return
    phase = _enemy_log_phase(step_name)
    if not phase:
        return

    try:
        map_id = int(Map.GetMapID() or 0)
        player_x, player_y = Player.GetXY()
        enemies = RoutinesAgents.GetFilteredEnemyArray(player_x, player_y, ENEMY_LOG_RADIUS)
    except Exception:
        return

    for raw_agent_id in list(enemies or []):
        agent_id = int(raw_agent_id)
        try:
            enemy_x, enemy_y = Agent.GetXY(agent_id)
        except Exception:
            continue
        distance = math.dist((player_x, player_y), (enemy_x, enemy_y))
        key = (
            map_id,
            agent_id,
            int(round(enemy_x / ENEMY_LOG_ID_CELL)),
            int(round(enemy_y / ENEMY_LOG_ID_CELL)),
            phase,
        )
        existing = _enemy_log_records.get(key)
        if existing is not None:
            if distance < existing.distance:
                _enemy_log_records[key] = EnemyLogRecord(
                    phase, step_name, map_id, agent_id,
                    player_x, player_y, enemy_x, enemy_y, distance,
                )
            continue
        if len(_enemy_log_records) >= ENEMY_LOG_MAX_RECORDS:
            _enemy_log_dropped += 1
            break
        _enemy_log_records[key] = EnemyLogRecord(
            phase, step_name, map_id, agent_id,
            player_x, player_y, enemy_x, enemy_y, distance,
        )


def _flush_enemy_log(outcome: str) -> None:
    """Write the collected records next to the widget and clear the buffer."""
    global _enemy_log_active
    global _enemy_log_finished_at
    global _enemy_log_records
    global _enemy_log_dropped

    if not _enemy_log_active:
        return
    if not enemy_log_enabled:
        # Switched off while the run was in progress: drop what was collected and
        # leave the file that was already there untouched.
        _enemy_log_active = False
        _enemy_log_records = {}
        PySystem.Console.Log(
            MODULE_NAME,
            'Enemy log disabled during the run. Nothing was written.',
            PySystem.Console.MessageType.Info,
        )
        return
    _enemy_log_active = False
    _enemy_log_finished_at = time.strftime('%Y-%m-%d %H:%M:%S')

    records = list(_enemy_log_records.values())
    path = _enemy_log_path()
    lines = [
        f'# --- run {_enemy_log_started_at} -> {_enemy_log_finished_at} outcome={outcome}',
        (
            f'# map={_enemy_log_label} map_id={_enemy_log_map_id}'
            f' radius={int(ENEMY_LOG_RADIUS)} id_cell={int(ENEMY_LOG_ID_CELL)}'
            # The configured clear radii, so a review can tell what the pass was
            # supposed to cover without reading the INI.
            f' clear_forward={int(forward_clear_radius)}'
            f' clear_reverse={int(max(reverse_clear_radius_1, reverse_clear_radius_2))}'
            f' records={len(records)} dropped={_enemy_log_dropped}'
        ),
        '# columns: phase\tstep\tmap_id\tagent_id\tplayer_x\tplayer_y\tenemy_x\tenemy_y\tdistance',
    ]
    for record in records:
        lines.append(
            '\t'.join(
                (
                    record.phase,
                    record.step,
                    str(record.map_id),
                    str(record.agent_id),
                    f'{record.player_x:.1f}',
                    f'{record.player_y:.1f}',
                    f'{record.enemy_x:.1f}',
                    f'{record.enemy_y:.1f}',
                    f'{record.distance:.1f}',
                )
            )
        )

    # Appended, never overwritten: the file is the history of every run, so a week
    # of vanquishes can be read together. The document header is written once, when
    # the file is created, and the block is a single write so a crash cannot leave
    # half a run behind.
    block = '\n'.join(lines) + '\n\n'
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        new_file = not os.path.exists(path) or os.path.getsize(path) == 0
        with open(path, 'a', encoding='utf-8', newline='\n') as handle:
            if new_file:
                handle.write(ENEMY_LOG_DOCUMENT_HEADER)
            handle.write(block)
    except OSError as error:
        _enemy_log_records = {}
        PySystem.Console.Log(
            MODULE_NAME,
            f'Enemy log could not be written to {path}: {error}.',
            PySystem.Console.MessageType.Error,
        )
        return

    _enemy_log_records = {}
    PySystem.Console.Log(
        MODULE_NAME,
        f'Enemy log written to {path} ({len(records)} records, outcome={outcome}).',
        PySystem.Console.MessageType.Info,
    )


def _parse_model_id_list(raw: str, allowed: Sequence[int]) -> set[int]:
    """Parse a comma-separated model ID string, keeping only known models.

    Unknown or malformed entries are dropped rather than raising: the INI is
    user-editable and a stray value should not break widget init.
    """
    allowed_set = {int(model_id) for model_id in allowed}
    parsed: set[int] = set()
    for chunk in str(raw or '').split(','):
        text = chunk.strip()
        if not text:
            continue
        try:
            value = int(text)
        except ValueError:
            continue
        if value in allowed_set:
            parsed.add(value)
    return parsed


def _serialize_model_id_list(model_ids: set[int]) -> str:
    return ','.join(str(model_id) for model_id in sorted(int(value) for value in model_ids))


def _parse_queue(raw: str) -> list[tuple[str, str]]:
    """Queue entries from their stored form, dropping anything the pack cannot load.

    The INI is user-editable and the map pack changes, so an entry that no longer
    resolves is dropped here instead of failing the whole plan at build time.
    """
    entries: list[tuple[str, str]] = []
    for chunk in str(raw or '').split(';'):
        region, _, map_name = chunk.strip().partition('/')
        if not region or not map_name:
            continue
        if map_name not in MAP_CATALOG.get(region, ()):
            continue
        if (region, map_name) in entries:
            continue
        entries.append((region, map_name))
    return entries


def _serialize_queue(entries: Sequence[tuple[str, str]]) -> str:
    return ';'.join(f'{region}/{map_name}' for region, map_name in entries)


def _parse_plan_entries(raw: str) -> list[str]:
    """A stored per-size party plan: one entry per `;`, blanks and repeats dropped.

    An entry is an account email or `hero:<id>`. Repeats are dropped here as well
    as in the UI, so a hand-edited INI cannot ask one party to hold the same alt
    or the same hero twice.
    """
    entries: list[str] = []
    for chunk in str(raw or '').split(';'):
        entry = chunk.strip()
        if entry and entry not in entries:
            entries.append(entry)
    return entries


def _serialize_plan_entries(entries: Sequence[str]) -> str:
    return ';'.join(entry for entry in entries if entry)


def _hero_label(hero_id: int) -> str:
    """Display name for a hero id: MasterOfWhispers -> Master Of Whispers."""
    try:
        name = HeroType(int(hero_id)).name
    except ValueError:
        return f'Hero {hero_id}'
    if name.isupper():
        return name
    parts: list[str] = []
    for character in name:
        if character.isupper() and parts:
            parts.append(' ')
        parts.append(character)
    return ''.join(parts)


def _split_plan(plan: Sequence[str]) -> tuple[list[int], list[str]]:
    """Separate one plan into (hero ids, account emails).

    The halves have different owners: accounts are summoned and invited over
    shared memory, heroes are added locally by the party leader.
    """
    hero_ids: list[int] = []
    emails: list[str] = []
    for entry in plan:
        value = str(entry or '').strip()
        if not value:
            continue
        if value.startswith(_HERO_PREFIX):
            try:
                hero_id = int(value[len(_HERO_PREFIX):])
            except ValueError:
                continue
            if hero_id > 0 and hero_id not in hero_ids:
                hero_ids.append(hero_id)
        elif value not in emails:
            emails.append(value)
    return hero_ids, emails


def _party_plan_for_current_map() -> list[str]:
    """The configured invite list for the outpost the party is standing in.

    The outpost decides the party size, and the run only learns which outpost
    that is after it travels, so this is read when the rebuild node executes
    rather than when the planner is built. A size with no configured plan returns
    nothing, and the caller falls back to inviting every account on the map.
    """
    try:
        limit = int(Map.GetMaxPartySize() or 0)
    except Exception:
        return []
    return [email for email in _party_plans.get(limit, []) if email]


def _append_region_to_queue(region: str) -> int:
    """Append every map of a region to the queue, in catalog order.

    Returns how many entries were added. A region already queued contributes
    nothing, so the button can tell a no-op click from a real change and skip the
    save and the tree rebuild. The catalog order is the combo order, so the plan
    walks the region the way the list reads.
    """
    added = 0
    for map_name in MAP_CATALOG.get(region, ()):
        entry = (region, map_name)
        if entry in vanquish_queue:
            continue
        vanquish_queue.append(entry)
        added += 1
    return added


def _sync_take_zquest() -> None:
    """Taking the signpost quest only makes sense with automatic handling.

    The map comes from the quest the signpost hands over, so taking it without
    reading it would stage the party for a quest the plan is not going to walk.
    A queued run picks its maps from the list, so it never takes one either.
    """
    global take_zquest
    take_zquest = automatic_zquest and not vanquish_queue


def _set_automatic_zquest(value: bool) -> None:
    """Flip Automatic ZQuest handling the way the Config tab does.

    Turning it on clears `loop_runs`, since a repeated pass would have nothing
    left to accept. `take_zquest` is derived from the switch, `_auto_definition`
    is stale afterwards and the plan has to be rebuilt. Every path that flips
    this switch comes through here, so the checkbox and the bridge cannot drift.
    """
    global automatic_zquest, loop_runs, _auto_definition
    automatic_zquest = bool(value)
    if automatic_zquest:
        loop_runs = False
    _sync_take_zquest()
    _auto_definition = None
    _save_settings()
    _request_rebuild()


def _queue_changed() -> None:
    """Bring the derived switch and the plan back in step after the queue moves.

    `take_zquest` is derived from the queue as well as from the automatic switch,
    and the plan shape changes with the queue, so every mutation ends here
    instead of repeating the three calls and forgetting one.
    """
    _sync_take_zquest()
    _save_settings()
    _request_rebuild()


def _clear_vanquish_queue() -> int:
    """Empty the vanquish queue and persist it. Returns how many entries went."""
    removed = len(vanquish_queue)
    if removed:
        vanquish_queue.clear()
        _queue_changed()
    return removed


def _add_map_to_queue(region: str, map_name: str) -> int:
    """Queue one map of a region. Returns 1 when the queue changed, 0 when it was there.

    A pure mutation like `_append_region_to_queue`: the caller decides whether to
    save and rebuild, which is what lets a bridge call validate first and tell a
    no-op from a real change.
    """
    entry = (region, map_name)
    if entry in vanquish_queue:
        return 0
    vanquish_queue.append(entry)
    return 1


def _remove_map_from_queue(region: str, map_name: str) -> int:
    """Drop one queued map. Returns 1 when the queue changed, 0 when it was not there.

    Deliberately not validated against the catalogue: the queue is the authority on
    what it holds, and a map that the catalogue has since renamed is still an entry
    somebody may want out.
    """
    entry = (region, map_name)
    if entry not in vanquish_queue:
        return 0
    vanquish_queue.remove(entry)
    return 1


# ---- Bridge config surface ---------------------------------------------------
# The Py4GW bridge resolves `bridge_config_get` and `bridge_config_set` by name,
# the same way `widgets.start` resolves `ensure_botting_tree`. They exist so the
# bridge never pokes module globals: a write goes through the helpers above,
# which keep the derived flags in sync and persist what the Config tab persists.
_BRIDGE_CONFIG_WRITABLE: tuple[str, ...] = (
    'automatic_zquest',
    'queue_add_map',
    'queue_add_region',
    'queue_add',
    'queue_remove_map',
    'clear_queue',
)


def _invalid(message: str) -> dict[str, Any]:
    return {'error': {'code': 'invalid_value', 'message': message}}


def _split_map_entry(entry: Any) -> tuple[str, str]:
    """Read a {region, map} record, tolerating a missing map name."""
    if not isinstance(entry, dict):
        return '', ''
    return (
        str(entry.get('region') or '').strip(),
        str(entry.get('map') or '').strip(),
    )


def _region_error(region: str) -> dict[str, Any] | None:
    if region not in MAP_CATALOG:
        return _unknown_region(region)
    return None


def _map_error(region: str, map_name: str) -> dict[str, Any] | None:
    maps = MAP_CATALOG.get(region, ())
    if map_name in maps:
        return None
    return {
        'error': {
            'code': 'unknown_map',
            'message': f"{map_name!r} is not in {region}; maps: {', '.join(maps)}",
        }
    }


def _queue_refusal() -> dict[str, Any] | None:
    """The two queue edits and the automatic switch are mutually exclusive.

    The Config tab disables the queue buttons while automatic handling is on, so
    a caller that queues has to switch it off first — in the same call is fine,
    the keys are applied in the order they are listed above.
    """
    if automatic_zquest:
        return {
            'error': {
                'code': 'guard_automatic_zquest',
                'message': 'turn automatic ZQuest handling off before queueing maps',
            }
        }
    return None


def _unknown_region(region: str) -> dict[str, Any]:
    return {
        'error': {
            'code': 'unknown_region',
            'message': f"{region!r} is not a region; regions: {', '.join(REGIONS)}",
        }
    }


def bridge_config_get() -> dict[str, Any]:
    """Report the configuration a bridge caller may read or change.

    `locked` is the condition the Config tab uses to disable its whole panel: a
    tree that is already running has built its plan, so nothing is writable.
    """
    tree = botting_tree
    locked = bool(tree is not None and tree.IsStarted())
    return {
        'automatic_zquest': bool(automatic_zquest),
        'take_zquest': bool(take_zquest),
        'loop_runs': bool(loop_runs),
        'queue': [{'region': region, 'map': map_name} for region, map_name in vanquish_queue],
        'regions': list(REGIONS),
        'locked': locked,
        'writable': not locked,
        'writable_keys': list(_BRIDGE_CONFIG_WRITABLE),
    }


def bridge_config_set(values: dict[str, Any] | None) -> dict[str, Any]:
    """Apply a configuration change, or answer with why it was refused.

    The refusals mirror the Config tab: its panel is disabled while the tree
    runs, and the automatic switch is disabled while the queue has entries,
    because a queued run picks its own maps and `take_zquest` would be forced off
    anyway.
    """
    changes = dict(values or {})
    tree = botting_tree
    if tree is not None and tree.IsStarted():
        return {
            'error': {
                'code': 'guard_widget_running',
                'message': 'stop the bot before changing its configuration',
            }
        }
    unknown = sorted(key for key in changes if key not in _BRIDGE_CONFIG_WRITABLE)
    if unknown:
        return {
            'error': {
                'code': 'unknown_setting',
                'message': f"unknown keys: {', '.join(unknown)}",
            }
        }

    applied: list[str] = []
    added: dict[str, int] = {}
    removed: dict[str, int] = {}
    if 'automatic_zquest' in changes:
        if vanquish_queue:
            return {
                'error': {
                    'code': 'guard_queue_not_empty',
                    'message': 'clear the vanquish queue before switching automatic ZQuest handling',
                }
            }
        _set_automatic_zquest(bool(changes['automatic_zquest']))
        applied.append('automatic_zquest')
    if 'queue_add_map' in changes:
        refusal = _queue_refusal()
        if refusal is not None:
            return refusal
        region, map_name = _split_map_entry(changes['queue_add_map'])
        if not region or not map_name:
            return _invalid('queue_add_map accepts {"region": ..., "map": ...}')
        error = _region_error(region) or _map_error(region, map_name)
        if error is not None:
            return error
        added['queue_add_map'] = _add_map_to_queue(region, map_name)
        if added['queue_add_map']:
            _queue_changed()
        applied.append('queue_add_map')
    if 'queue_add_region' in changes:
        refusal = _queue_refusal()
        if refusal is not None:
            return refusal
        region = str(changes['queue_add_region'] or '').strip()
        error = _region_error(region)
        if error is not None:
            return error
        added['queue_add_region'] = _append_region_to_queue(region)
        if added['queue_add_region']:
            _queue_changed()
        applied.append('queue_add_region')
    if 'queue_add' in changes:
        refusal = _queue_refusal()
        if refusal is not None:
            return refusal
        batch = changes['queue_add']
        if not isinstance(batch, list) or not batch:
            return _invalid(
                'queue_add accepts a non-empty list of {"region", "map"} or {"region"}'
            )
        # Validate the whole batch first: a queue half-applied because entry 7 was
        # a typo is worse than one that refused the lot and said which entry failed.
        planned: list[tuple[str, str]] = []
        for index, raw in enumerate(batch):
            region, map_name = _split_map_entry(raw)
            if not region:
                return _invalid(f"queue_add[{index}] needs a region")
            error = _region_error(region) or (
                _map_error(region, map_name) if map_name else None
            )
            if error is not None:
                # In a batch the same region can appear twice, so say which entry
                # the catalogue rejected instead of leaving the caller to guess.
                error['error']['message'] = f"queue_add[{index}]: {error['error']['message']}"
                return error
            if map_name:
                planned.append((region, map_name))
            else:
                planned.extend((region, each) for each in MAP_CATALOG[region])
        count = 0
        for plan_region, plan_map in planned:
            count += _add_map_to_queue(plan_region, plan_map)
        if count:
            _queue_changed()
        added['queue_add'] = count
        applied.append('queue_add')
    if 'queue_remove_map' in changes:
        refusal = _queue_refusal()
        if refusal is not None:
            return refusal
        region, map_name = _split_map_entry(changes['queue_remove_map'])
        if not region or not map_name:
            return _invalid('queue_remove_map accepts {"region": ..., "map": ...}')
        removed['queue_remove_map'] = _remove_map_from_queue(region, map_name)
        if removed['queue_remove_map']:
            _queue_changed()
        applied.append('queue_remove_map')
    if 'clear_queue' in changes:
        if not bool(changes['clear_queue']):
            return _invalid('clear_queue only accepts true')
        removed['clear_queue'] = _clear_vanquish_queue()
        applied.append('clear_queue')
    result: dict[str, Any] = {'applied': applied}
    if added:
        result['added'] = added
    if removed:
        result['removed'] = removed
    result['config'] = bridge_config_get()
    return result


def _load_settings() -> None:
    global _settings_loaded
    global _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons
    global _restock_scroll_of_resurrection
    global _restock_multi_account
    global _keep_gold_on_accounts
    global _selected_conset, _selected_pcons
    global automatic_zquest
    global take_zquest, loop_runs
    global enemy_log_enabled
    global vanquish_queue

    if _settings_loaded:
        return
    _restock_conset = _settings.get_bool(_SETTINGS_SECTION, _KEY_RESTOCK_CONSET, True)
    _activate_conset = _settings.get_bool(_SETTINGS_SECTION, _KEY_ACTIVATE_CONSET, True)
    _restock_pcons = _settings.get_bool(_SETTINGS_SECTION, _KEY_RESTOCK_PCONS, True)
    _activate_pcons = _settings.get_bool(_SETTINGS_SECTION, _KEY_ACTIVATE_PCONS, True)
    _restock_scroll_of_resurrection = _settings.get_bool(_SETTINGS_SECTION, _KEY_RESTOCK_SCROLL_OF_RESURRECTION, True)
    _restock_multi_account = _settings.get_bool(_SETTINGS_SECTION, _KEY_RESTOCK_MULTI_ACCOUNT, True)
    _keep_gold_on_accounts = _settings.get_bool(_SETTINGS_SECTION, _KEY_KEEP_GOLD_ON_ACCOUNTS, True)
    automatic_zquest = _settings.get_bool(_SETTINGS_SECTION, _KEY_AUTOMATIC_ZQUEST, False)
    enemy_log_enabled = _settings.get_bool(_SETTINGS_SECTION, _KEY_ENEMY_LOG, False)
    vanquish_queue = _parse_queue(_settings.get_str(_SETTINGS_SECTION, _KEY_QUEUE_ITEMS, ''))
    if vanquish_queue:
        # A queued run owns the plan shape, so the signpost flows cannot run with
        # it: every entry has to be a map the party travels to, not the one the
        # signpost happens to hand over. A stored combination from before the
        # queue existed is corrected here instead of being trusted.
        automatic_zquest = False
    if automatic_zquest:
        # A stored combination from an older build has to respect the rule the UI
        # enforces: the signpost feeds the resolution and a loop would have
        # nothing left to accept on its second pass.
        loop_runs = False
    _sync_take_zquest()

    stored_conset = _settings.get_str(_SETTINGS_SECTION, _KEY_SELECTED_CONSET, '')
    if stored_conset.strip():
        _selected_conset = _parse_model_id_list(stored_conset, CONSET_MODEL_IDS)

    stored_pcons = _settings.get_str(_SETTINGS_SECTION, _KEY_SELECTED_PCONS, '')
    if stored_pcons.strip():
        _selected_pcons = _parse_model_id_list(stored_pcons, PCON_UPKEEPS)

    # One entry per invited slot, so a stored list longer than its size (edited by
    # hand in the INI) is trimmed instead of trusted.
    for size, key in ((4, _KEY_PARTY_PLAN_4), (6, _KEY_PARTY_PLAN_6), (8, _KEY_PARTY_PLAN_8)):
        stored_plan = _parse_plan_entries(_settings.get_str(_SETTINGS_SECTION, key, ''))
        _party_plans[size] = stored_plan[: size - 1]

    _settings_loaded = True


def _save_settings() -> None:
    _settings.set(_SETTINGS_SECTION, _KEY_RESTOCK_CONSET, _restock_conset)
    _settings.set(_SETTINGS_SECTION, _KEY_ACTIVATE_CONSET, _activate_conset)
    _settings.set(_SETTINGS_SECTION, _KEY_RESTOCK_PCONS, _restock_pcons)
    _settings.set(_SETTINGS_SECTION, _KEY_ACTIVATE_PCONS, _activate_pcons)
    _settings.set(_SETTINGS_SECTION, _KEY_RESTOCK_SCROLL_OF_RESURRECTION, _restock_scroll_of_resurrection)
    _settings.set(_SETTINGS_SECTION, _KEY_RESTOCK_MULTI_ACCOUNT, _restock_multi_account)
    _settings.set(_SETTINGS_SECTION, _KEY_KEEP_GOLD_ON_ACCOUNTS, _keep_gold_on_accounts)
    _settings.set(_SETTINGS_SECTION, _KEY_AUTOMATIC_ZQUEST, automatic_zquest)
    _settings.set(_SETTINGS_SECTION, _KEY_ENEMY_LOG, enemy_log_enabled)
    _settings.set(_SETTINGS_SECTION, _KEY_QUEUE_ITEMS, _serialize_queue(vanquish_queue))
    _settings.set(_SETTINGS_SECTION, _KEY_SELECTED_CONSET, _serialize_model_id_list(_selected_conset))
    _settings.set(_SETTINGS_SECTION, _KEY_SELECTED_PCONS, _serialize_model_id_list(_selected_pcons))
    _settings.set(_SETTINGS_SECTION, _KEY_PARTY_PLAN_4, _serialize_plan_entries(_party_plans.get(4, [])))
    _settings.set(_SETTINGS_SECTION, _KEY_PARTY_PLAN_6, _serialize_plan_entries(_party_plans.get(6, [])))
    _settings.set(_SETTINGS_SECTION, _KEY_PARTY_PLAN_8, _serialize_plan_entries(_party_plans.get(8, [])))


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    """Upkeep model IDs for the currently enabled and individually selected items.

    Ordering follows the core lists (consets then pcons); duplicates are
    collapsed because `ConfigureUpkeep` would otherwise register two services
    for one model.
    """
    enabled: list[int] = []
    if _activate_conset:
        enabled.extend(model_id for model_id in CONSET_MODEL_IDS if model_id in _selected_conset)
    if _activate_pcons:
        enabled.extend(model_id for model_id in PCON_UPKEEPS if model_id in _selected_pcons)
    return tuple(dict.fromkeys(enabled))


def _consumable_restock_items() -> tuple[tuple[int, int], ...]:
    """Restock targets for the enabled groups only."""
    wanted: set[int] = set()
    if _restock_conset:
        wanted.update(model_id for model_id in CONSET_MODEL_IDS if model_id in _selected_conset)
    if _restock_pcons:
        wanted.update(model_id for model_id in PCON_UPKEEPS if model_id in _selected_pcons)
    if _restock_scroll_of_resurrection:
        wanted.add(int(ModelID.Scroll_Of_Resurrection.value))
    return tuple(
        (model_id, quantity)
        for model_id, quantity in CONSUMABLE_RESTOCK_ITEMS
        if model_id in wanted
    )


def _consumables_short_of_target() -> bool:
    """True when any enabled model is still below its bag target."""
    for model_id, quantity in _consumable_restock_items():
        try:
            if int(GLOBAL_CACHE.Inventory.GetModelCount(model_id) or 0) < int(quantity):
                return True
        except Exception:
            return True
    return False


def _runtime_restock_node() -> BehaviorTree:
    """Resolve the restock list when the step is ticked, not when it is built.

    `get_execution_steps` builds the whole plan once at tree creation, so a
    restock node baked in at build time would freeze the list that was enabled
    at that moment. Building it inside a Subtree keeps the Consumables toggles
    meaningful for the next run without a full plan rebuild.

    `RoutinesBT.Items.RestockItems` samples the storage cache once per item and,
    with `allow_missing=True`, treats a cold zero read as "nothing to do" and
    advances. The first model in the list therefore risks being skipped on the
    run's opening frames (observed live: Essence of Celerity, first in
    CONSET_UPKEEPS, only landed on a second run). The remediation is a settle
    wait plus a second pass -- but the wait is gated on the bags actually being
    short, so a run whose consumables are already stocked pays no delay at all.
    """

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        items = _consumable_restock_items()
        if not items:
            return BT.Succeeder('Restock Disabled')
        return BT.Sequence(
            name='Restock Passes',
            children=[
                BT.RestockItemsFromList(tuple(items), allow_missing=True),
                _restock_retry_guard(),
            ],
        )

    return BT.Subtree(name='Restock Selected Consumables', subtree_fn=_build)


def _restock_retry_guard() -> BehaviorTree:
    """Settle, then re-run the restock only if something is still missing.

    The selector semantics matter here: a first child that returns SUCCESS
    short-circuits the whole guard (nothing missing, no delay), while returning
    FAILURE hands control to the settle-and-retry branch. Returning RUNNING
    would pin the selector to the first child permanently, so it is deliberately
    not used.
    """

    def _nothing_missing(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _consumables_short_of_target():
            return BehaviorTree.NodeState.FAILURE
        return BehaviorTree.NodeState.SUCCESS

    return BT.Subtree(
        name='Restock Retry Guard',
        subtree_fn=lambda _node: BehaviorTree(
            BehaviorTree.SelectorNode(
                name='Retry Restock If Short',
                children=[
                    BehaviorTree(
                        BehaviorTree.ActionNode(
                            name='Consumables Already Stocked',
                            action_fn=_nothing_missing,
                        )
                    ),
                    BehaviorTree(
                        BehaviorTree.SequenceNode(
                            name='Settle And Retry',
                            children=[
                                BT.Wait(duration_ms=RESTOCK_SETTLE_MS),
                                BT.RestockItemsFromList(
                                    _consumable_restock_items(),
                                    allow_missing=True,
                                ),
                            ],
                        )
                    ),
                ],
            )
        ),
    )


def _remote_account_emails() -> list[str]:
    """Emails of the other clients in the shared-memory group, self excluded.

    Each receiver resolves the command through its own Messaging widget. The
    sender is skipped because its bags are already handled by the local nodes.
    """
    try:
        sender_email = str(Player.GetAccountEmail() or '')
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData() or []
    except Exception:
        return []

    recipients: list[str] = []
    for account in accounts:
        email = str(getattr(account, 'AccountEmail', '') or '').strip()
        if not email or email == sender_email or email in recipients:
            continue
        recipients.append(email)
    return recipients


def _summon_map_tuple(account: object) -> tuple[int, int, int, int]:
    """The four fields `SummonAllAccounts` compares between accounts.

    Copied from `routines_src/behaviourtrees_src/shared.py:_account_map_tuple` so
    the census reports exactly what the summon step decides on: map, region,
    district and language. Region and language are part of that comparison even
    though no travel can change them, which is why they are printed here.
    """
    map_obj = getattr(getattr(account, 'AgentData', None), 'Map', None)
    return (
        int(getattr(account, 'MapID', 0) or getattr(map_obj, 'MapID', 0) or 0),
        int(getattr(account, 'MapRegion', 0) or getattr(map_obj, 'Region', 0) or 0),
        int(getattr(account, 'MapDistrict', 0) or getattr(map_obj, 'District', 0) or 0),
        int(getattr(account, 'MapLanguage', 0) or getattr(map_obj, 'Language', 0) or 0),
    )


def _live_map_tuple() -> tuple[int, int, int, int]:
    """This client's map identity straight from the live API."""
    try:
        return (
            int(Map.GetMapID() or 0),
            int(Map.GetRegion()[0] or 0),
            int(Map.GetDistrict() or 0),
            int(Map.GetLanguage()[0] or 0),
        )
    except Exception:
        return (0, 0, 0, 0)


def _shared_memory_census(include_isolated: bool = True) -> list[str]:
    """One line per account the account mirror shows right now.

    The mirror is written by the native multibox module: one slot per client, a
    full push every frame from each client's `DrawLoop`, and this side only reads
    it. So an alt missing from this list is not being hidden by a stale reader —
    it either is not publishing (client not injected, still logging in, or stuck
    on a loading screen) or it lost a slot claim to another client. Neither is
    something this widget can refresh; the census exists to tell the two apart
    from "the alt is there but somewhere else".

    `match` compares each account's map tuple against the leader's the same way
    the summon step does, so a run log shows who that step would target and why.

    `include_isolated` is on because isolation hides accounts from every normal
    query, and a hidden alt looks exactly like a missing one in the logs.
    """
    try:
        accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData(include_isolated=include_isolated) or [])
    except Exception as error:
        return [f'shared memory unavailable: {error}']

    local_email = str(Player.GetAccountEmail() or '').strip()
    local_account = None
    for account in accounts:
        if str(getattr(account, 'AccountEmail', '') or '').strip() == local_email:
            local_account = account
            break
    if local_account is not None:
        local_tuple = _summon_map_tuple(local_account)
        local_source = 'mirror'
    else:
        local_tuple = _live_map_tuple()
        local_source = 'live map'

    now = int(PySystem.get_tick_count64())
    lines = [
        f'{len(accounts)} account slot(s) visible',
        f'  local {local_email or "<no email>"} tuple={local_tuple} from {local_source}',
    ]
    for account in accounts:
        email = str(getattr(account, 'AccountEmail', '') or '').strip() or '<no email>'
        map_id, region, district, language = _summon_map_tuple(account)
        is_account = 'yes' if bool(getattr(account, 'IsAccount', False)) else 'no'
        isolated = ' isolated' if bool(getattr(account, 'IsIsolated', False)) else ''
        matches_leader = 'yes' if (map_id, region, district, language) == local_tuple else 'no'
        # LastUpdated is a 32-bit truncation of the frame clock. A value ahead of
        # ours (publishers run a frame or two later) would otherwise read as a
        # 49-day-old slot, so the top half of the range is treated as "just now".
        age_ms = (now - int(getattr(account, 'LastUpdated', 0) or 0)) % (1 << 32)
        if age_ms > 0x80000000:
            age_ms = 0
        lines.append(
            f'  slot {int(getattr(account, "SlotNumber", 0) or 0)} {email} '
            f'map={map_id} region={region} district={district} language={language} '
            f'account={is_account} match={matches_leader} age={age_ms}ms{isolated}'
        )
    return lines


def _log_shared_memory_census() -> BehaviorTree.NodeState:
    """Write the census to the console before anyone is gathered."""
    for line in _shared_memory_census():
        PySystem.Console.Log(MODULE_NAME, line, PySystem.Console.MessageType.Info)
    return BehaviorTree.NodeState.SUCCESS


def _remote_restock_commands() -> tuple[tuple[SharedCommandType, int], ...]:
    """Shared restock commands for the enabled groups, one quantity each.

    The shared command surface is aggregate: `RestockConset` and
    `RestockAllPcons` restock a fixed model list with a single quantity, so the
    per-item checklist cannot travel over the bus. Quantities, however, mirror
    the local target: `RestockAllPcons` runs at the pcon quantity and the scroll,
    which that handler also moves, is topped up to its own target afterwards.
    """
    items = _consumable_restock_items()
    if not items:
        return ()

    conset_ids = {int(model_id) for model_id in CONSET_MODEL_IDS}
    pcon_ids = {int(model_id) for model_id in PCON_UPKEEPS}
    scroll_id = int(ModelID.Scroll_Of_Resurrection.value)

    def _highest_quantity(model_ids: set[int]) -> int:
        quantities = [int(quantity) for model_id, quantity in items if int(model_id) in model_ids]
        return max(quantities) if quantities else 0

    commands: list[tuple[SharedCommandType, int]] = []

    conset_quantity = _highest_quantity(conset_ids)
    if conset_quantity > 0:
        commands.append((SharedCommandType.RestockConset, conset_quantity))

    pcon_quantity = _highest_quantity(pcon_ids)
    if pcon_quantity > 0:
        commands.append((SharedCommandType.RestockAllPcons, pcon_quantity))

    scroll_quantity = _highest_quantity({scroll_id})
    if scroll_quantity > 0:
        # RestockAllPcons already pulled the scroll up to the pcon quantity; this
        # pass raises it to its own, higher target.
        commands.append((SharedCommandType.RestockResurrectionScroll, scroll_quantity))

    return tuple(commands)


def _remote_restock_node() -> BehaviorTree:
    """Restock the other accounts in the group through the shared command bus.

    Requires the `Messaging` widget on every receiver: without it the message is
    never consumed and the dispatch wait runs into its timeout. Recipients and
    commands are resolved when the step ticks, so toggles and party changes apply
    to the next run without a plan rebuild.
    """

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not _restock_multi_account:
            return BT.Succeeder('Remote Restock Disabled')
        recipients = _remote_account_emails()
        if not recipients:
            return BT.Succeeder('Remote Restock No Recipients')
        commands = _remote_restock_commands()
        if not commands:
            return BT.Succeeder('Remote Restock Disabled')
        return BT.Sequence(
            name='Restock Other Accounts',
            children=[
                RoutinesBT.Shared.SendAndWait(
                    command=command,
                    params=(float(quantity), 0.0, 0.0, 0.0),
                    recipients=recipients,
                    refs_blackboard_key=f'__remote_restock_refs_{int(command)}',
                    timeout_ms=REMOTE_RESTOCK_TIMEOUT_MS,
                    poll_interval_ms=100,
                    log=True,
                    aftercast_ms=100,
                )
                for command, quantity in commands
            ],
        )

    return BT.Subtree(name='Restock Other Accounts', subtree_fn=_build)


def _keep_gold_node() -> BehaviorTree:
    """Leave `KEEP_GOLD_AMOUNT` on every account during the preparation.

    Reuses the existing `WithdrawGold` shared command, which equalizes in both
    directions: it deposits the excess over the target and withdraws from storage
    when the character is short. Recipients resolve it through their own
    `Messaging` widget, so that widget has to be running on every client.
    """

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not _keep_gold_on_accounts:
            return BT.Succeeder('Keep Gold Disabled')

        children: list[BehaviorTree] = [
            BT.EqualizeGold(target_gold=KEEP_GOLD_AMOUNT),
        ]

        recipients = _remote_account_emails()
        if recipients:
            children.append(
                RoutinesBT.Shared.SendAndWait(
                    command=SharedCommandType.WithdrawGold,
                    params=(float(KEEP_GOLD_AMOUNT), 1.0, 0.0, 0.0),
                    recipients=recipients,
                    refs_blackboard_key='__keep_gold_refs',
                    timeout_ms=REMOTE_KEEP_GOLD_TIMEOUT_MS,
                    poll_interval_ms=100,
                    log=True,
                    aftercast_ms=100,
                )
            )

        return BT.Sequence(name='Keep Gold On Accounts', children=children)

    return BT.Subtree(name='Keep Gold On Accounts', subtree_fn=_build)


def _selected_region() -> str:
    if not REGIONS:
        return ''
    return REGIONS[max(0, min(region_index, len(REGIONS) - 1))]


def _selected_maps() -> tuple[str, ...]:
    return MAP_CATALOG.get(_selected_region(), ())


def _selected_map() -> str:
    maps = _selected_maps()
    if not maps:
        return ''
    return maps[max(0, min(map_index, len(maps) - 1))]


def _load_transit_data(
    module: object, map_name: str, ids: Mapping
) -> tuple[tuple[int, ...], tuple[list[object], ...]]:
    """Transit legs in walking order: the map each one exits into, and its path.

    `ids` is the dictionary the caller already resolved. Reading it by name again
    here would lose the transit ids of a legacy map file whose ID dictionary has an
    unrelated variable name, while still finding its `<map>_transit_path`: the legs
    stay but point at the final map, and the outpost exit can never reach the first
    transit map.
    """
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
    if not region or not map_name:
        raise ValueError(
            f'No PyQuish map found under {MAP_ROOT}. Select a region and a map in Config.'
        )
    return load_definition(region, map_name)


def load_definition(region: str, map_name: str) -> VanquishDefinition:
    """Load one map module by region and name, whoever picked it.

    Split out of `load_selected_definition` so the automatic ZQuest handling can
    load the area it read from the quest without touching the combos.
    """
    module_name = f'{MAP_PACKAGE}.{region}.{map_name}'
    # The map pack is data, so drop the cached copy and re-read the file: a live
    # edit is picked up on the next tree build after a widget reload.
    importlib.invalidate_caches()
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        missing_name = str(error.name or '')
        if missing_name and (
            missing_name == module_name
            or module_name.startswith(f'{missing_name}.')
        ):
            raise ValueError(
                f'Missing PyQuish map module: {region}/{map_name}.py. '
                f'Copy the NF_Desolation map pack into {MAP_PACKAGE.replace(".", "/")}.'
            ) from error
        raise
    module = importlib.reload(module)

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
    transit_ids, transit_paths = _load_transit_data(module, map_name, ids)

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


def _active_map_name() -> str:
    """Map the UI reports: the resolved one in automatic mode."""
    if automatic_zquest and _auto_definition is not None:
        return _auto_definition.map_name
    return _selected_map()


def _strip_quest_markup(text: str) -> str:
    """Quest text without the client's markup and control characters.

    Two kinds of noise show up in the strings the client returns: colour tags like
    `<c=@Quest>` and unresolved substitution markers like the `{s}` the vanquish
    objective can carry at the very start. Both are dropped, otherwise the text
    never begins with the verb the parser looks for.
    """
    plain: list[str] = []
    angle = 0
    brace = 0
    for character in text:
        if character == '<':
            angle += 1
            continue
        if character == '>' and angle:
            angle -= 1
            continue
        if character == '{':
            brace += 1
            continue
        if character == '}' and brace:
            brace -= 1
            continue
        if angle or brace:
            continue
        plain.append(character if character.isprintable() else ' ')
    return ' '.join(''.join(plain).split())


def _objective_area(objectives: str) -> tuple[str, str]:
    """(area, location) named by a vanquish objective.

    Objectives read `Clear <area> near <outpost> of all enemies in hard mode.` or
    `Clear <area> in <region> of all enemies in hard mode.`. The area is what is
    left after the verb, once the mode clause and the location clause are cut
    away: `Clear the Floodplain of Mahnkelon in Kourna of all enemies in hard
    mode.` yields (`the Floodplain of Mahnkelon`, `Kourna`). Returns two empty
    strings when the text is not a vanquish objective.
    """
    text = _strip_quest_markup(objectives or '')
    lowered = text.lower()
    for verb in ('clear ', 'vanquish '):
        if lowered.startswith(verb):
            rest = text[len(verb):]
            rest_lowered = lowered[len(verb):]
            break
    else:
        return '', ''

    # The mode clause sits at the end and must go first: `in hard mode` is also a
    # location-looking phrase and would otherwise be taken as the area's location.
    for marker in (' of all enemies', ' in hard mode', ' in normal mode'):
        position = rest_lowered.find(marker)
        if position >= 0:
            rest = rest[:position]
            rest_lowered = rest_lowered[:position]

    area = rest
    location = ''
    for marker in (' near ', ' in '):
        position = rest_lowered.find(marker)
        if position >= 0:
            area = rest[:position]
            location = rest[position + len(marker):]
            break
    return area.strip(), location.strip()


def _area_key(text: str) -> str:
    """Comparison key for an area or region name.

    Map files are named without spaces (`PongmeiValley`, `TheAlkaliPan`) while the
    objective has them and often carries a leading article, so the key drops
    everything but letters and digits and then the article.
    """
    key = ''.join(character for character in text.lower() if character.isalnum())
    if key.startswith('the'):
        key = key[3:]
    return key


def _region_matches_hint(region: str, location: str) -> bool:
    """Whether a catalog region answers the location clause of the objective."""
    hint = _area_key(location)
    if not hint:
        return False
    region_key = _area_key(region.replace('_', ' '))
    return hint in region_key or region_key in hint


# Map files whose name differs from the in-game area name. The wiki and the
# client both spell this one `Tahnnakai Temple`; the file drops an `a`, so the
# day it comes up the area would never match.
_MAP_FILE_ALIASES: dict[str, tuple[str, str]] = {
    'tahnnakaitemple': ('Factions_KainengCity', 'TahnnakiTemple'),
}


def _match_map_key(area_key: str, location: str = '') -> tuple[str, str]:
    """Catalog (region, map) whose name matches the area, most specific first.

    Tiers: equality, map name ending with the area, area ending with the map name,
    containment. A tier that names several maps is narrowed by the location
    clause when the objective has one, which is what separates the two
    `DeldrimorBowl` entries. Anything still ambiguous is reported as no match:
    guessing would run the wrong route.
    """
    if not area_key:
        return '', ''
    alias = _MAP_FILE_ALIASES.get(area_key)
    if alias and alias[1] in MAP_CATALOG.get(alias[0], ()):
        return alias
    pairs = [
        (region, map_name)
        for region, maps in MAP_CATALOG.items()
        for map_name in maps
    ]
    tiers: tuple[Callable[[str], bool], ...] = (
        lambda key: key == area_key,
        lambda key: key.endswith(area_key),
        lambda key: area_key.endswith(key),
        lambda key: area_key in key or key in area_key,
    )
    for matches in tiers:
        found = [pair for pair in pairs if matches(_area_key(pair[1]))]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            hinted = [pair for pair in found if _region_matches_hint(pair[0], location)]
            if len(hinted) == 1:
                return hinted[0]
            # The map pack can hold one area twice under different region folders
            # (`DeldrimorBowl`). Those entries describe the same area, so the first
            # one wins instead of stopping the run over a data duplication.
            if len({pair[1] for pair in found}) == 1:
                return sorted(found)[0]
            return '', ''
    return '', ''


def _resolve_map_from_text(text: str) -> tuple[str, str]:
    """Catalog (region, map) named by a vanquish objective or description."""
    area, location = _objective_area(text)
    if not area:
        return '', ''
    return _match_map_key(_area_key(area), location)


def _resolve_map_from_quest_name(name: str) -> tuple[str, str]:
    """Catalog (region, map) named by a quest title, the last fallback source."""
    text = _strip_quest_markup(name or '')
    if ':' in text:
        text = text.rsplit(':', 1)[-1]
    return _match_map_key(_area_key(_objective_area(text)[0] or text))


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
    if not (Map.IsExplorable() and Map.IsVanquishable()):
        return False

    # The world context briefly reports 0 killed / 0 remaining while some
    # explorable maps are still initializing.  Map.IsVanquishCompleted()
    # only checks ``foes_to_kill == 0`` and therefore returns a false positive
    # during that window, which would skip every named route point instantly.
    foes_killed = int(Map.GetFoesKilled() or 0)
    foes_remaining = int(Map.GetFoesToKill() or 0)
    counter_initialized = (foes_killed + foes_remaining) > 0
    return bool(
        counter_initialized
        and foes_remaining == 0
        and Map.IsVanquishCompleted()
    )


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
        pos = _coordinate(value, 'bless')
        if faction:
            child = BT.TakeBlessing(
                pos=pos,
                faction=faction,
                blessing_dialog_id=dialog_id,
                multi_account=True,
                log=True,
            )
        else:
            # BT.TakeBlessing's no-faction multibox fan-out sends
            # SharedCommandType.GetBlessing, whose ProcessMessages case is a
            # no-op in Widgets/System/Messaging.py. The followers never receive
            # the dialog, and the unconsumed message wedges their inbox, so
            # later commands (restock, travel, resign) are never dispatched.
            # Take the shrine through the fan-out commands whose receivers ARE
            # wired instead, mirroring Reputation Farmer Multibox BT.
            child = BT.Sequence(
                name='BlessShrine',
                children=[
                    BT.Move(pos, tolerance=150.0, log=True),
                    BT.TargetNearestAndAutoDialog(
                        pos,
                        buttons=0,
                        multi_account=True,
                        log=True,
                    ),
                ],
            )
    elif key == 'gadget':
        child = BT.MoveAndInteractWithGadget(
            pos=_coordinate(value, 'gadget'),
            interaction_count=1,
            multi_account=True,
            log=True,
        )
    elif key == 'npc':
        child = BT.MoveAndInteract(
            pos=_coordinate(value, 'npc'),
            target_distance=Range.Nearby.value,
            log=True,
        )
    elif key == 'dialog':
        child = BT.SendDialog(dialog_id=_dialog_id(value), multi_account=True, log=True)
    elif key == 'wait':
        child = BT.Wait(duration_ms=_integer(value, 'wait'), log=False)
    elif key == 'map':
        child = BT.WaitForMapLoad(map_id=_integer(value, 'map'), timeout_ms=TRANSIT_TIMEOUT_MS)
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


def _build_outpost_exit(definition: VanquishDefinition) -> BehaviorTree:
    """Walk out of the outpost into the first map of the vanquish."""
    first_target = definition.explorable_id
    if definition.transit_ids and definition.transit_ids[0] > 0:
        first_target = definition.transit_ids[0]
    if first_target <= 0:
        raise ValueError(f'No target map ID for the outpost exit of {definition.display_name}.')
    return BT.MoveAndExitMap(
        definition.outpost_path,
        target_map_id=first_target,
        timeout_ms=TRANSIT_TIMEOUT_MS,
        log=True,
    )


def _mark_run_started(definition: VanquishDefinition) -> BehaviorTree.NodeState:
    stats.start_run()
    # The enemy log covers one run: a run that starts discards whatever the
    # previous one collected, so the file always describes the run that ended.
    _enemy_log_begin(definition)
    PySystem.Console.Log(
        MODULE_NAME,
        f'Starting vanquish: {definition.region}/{definition.map_name}.',
        PySystem.Console.MessageType.Info,
    )
    return BehaviorTree.NodeState.SUCCESS


def _mark_run_completed() -> BehaviorTree.NodeState:
    duration = stats.complete_run()
    _flush_enemy_log('completed')
    PySystem.Console.Log(
        MODULE_NAME,
        f'Vanquish completed in {_format_time(duration)}.',
        PySystem.Console.MessageType.Success,
    )
    return BehaviorTree.NodeState.SUCCESS


def _build_completion_fallback() -> BehaviorTree:
    """Stop the bot when the vanquish is still incomplete after both sweeps."""
    return BT.Sequence(
        name='VanquishIncomplete',
        children=[
            BT.LogMessage(
                message=(
                    'The vanquish is still incomplete after both cleanup sweeps. '
                    'Stopping the bot.'
                ),
                module_name=MODULE_NAME,
            ),
            _action('RequestBotStop', _request_bot_stop),
        ],
    )


def _build_resign_if_in_explorable(definition: VanquishDefinition) -> BehaviorTree:
    """Return to the outpost when the run starts inside an explorable.

    A queue's last entry no longer resigns, so the party is left standing in the
    map it cleared. Map travel only works from an outpost, so without this the
    first travel of the next run would wait for a map load that never comes.
    """

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if not Map.IsExplorable():
            return BT.Succeeder('AbleToTravel')
        return BT.Resign(
            wait_for_map_load=True,
            target_map_id=definition.outpost_id,
            multi_account=True,
            log=True,
        )

    return BT.Subtree(name='ResignIfInExplorable', subtree_fn=_build)


def _build_run_preparation(definition: VanquishDefinition) -> BehaviorTree:
    """Travel to the vanquish outpost, then rebuild the group there.

    The order matters and is deliberate: `LeaveParty` first, travel second, the
    group rebuild third (`_build_party_rebuild`). The shared travel helper is
    local, and a formed party travels with its leader (see
    `_build_travel_to_map`), so a follower that has to reach the outpost on its
    own would either drag or break the group on the way. Dissolving first lets
    every client travel independently, and building the party afterwards is what
    makes a client that missed its own travel recoverable: the summon runs once
    everyone has had its chance to arrive.

    The rebuild happens in the outpost, never after the exit, because a party
    cannot be assembled once the group is inside the explorable area.
    """

    children: list[BehaviorTree] = [
        # A finished queue leaves the party in the map it cleared, so the next run
        # can start out here: resign first, because travel needs an outpost.
        _build_resign_if_in_explorable(definition),
        # The plan's own Form Party step forms in whatever outpost the run
        # started in; this dissolves that group so every account reaches the
        # vanquish outpost alone and nothing is left to travel together.
        BT.LeaveParty(),
        # Travel first, with the same helper the staging and reward steps use, so
        # the outpost approach also picks a randomised low-traffic district. The
        # hard-mode switch that `BT.Sequence(map_id_or_name=...)` used to apply
        # after its own travel now rides along explicitly.
        _build_travel_to_map(definition.outpost_id, 'Outpost'),
        # The shared travel helper only waits for the map, while the outpost
        # approach also has to wait for the party to finish loading before the
        # restock and the exit start touching the outpost.
        RoutinesBT.Party.WaitForPartyLoaded(
            timeout_ms=REMOTE_PARTY_TIMEOUT_MS,
            log=True,
        ),
        # Rebuild the group at the destination, following the Party Config plan
        # for this outpost's size when one is configured (see
        # _build_party_rebuild for the fallback).
        _build_party_rebuild(),
        BT.SetHardMode(hard_mode=True),
        ensure_botting_tree().Config.Aggressive(
            multi_account=True,
            auto_loot=AUTO_LOOT,
            resurrection_scroll=True,
        ),
    ]

    if _restock_conset or _restock_pcons or _restock_scroll_of_resurrection:
        children.append(_runtime_restock_node())
        if _restock_multi_account:
            children.append(_remote_restock_node())

    children.append(_keep_gold_node())
    # No default parameter here: ActionNode inspects the signature and calls a
    # one-parameter callable as action_fn(node), which is how the definition ended
    # up holding the node instead of the map. A zero-parameter closure keeps the
    # captured definition and gets called with no arguments.
    children.append(_action('RecordRunStart', lambda: _mark_run_started(definition)))

    # The outpost exit belongs to the preparation; the intermediate travels are
    # their own named step and only exist when the map really has transit paths.
    if definition.outpost_path:
        children.append(_build_outpost_exit(definition))

    return BT.Sequence(
        name=f'Prepare:{definition.map_name}',
        children=children,
    )


class RouteItem(NamedTuple):
    """One planner step of a walking leg.

    The map is carried with the point, and in the step name, because transit legs
    and the vanquish route use their own coordinate spaces: reading a point from
    one map against a position from another paths into a wall, and the console
    cannot tell the two apart without the id in the name.

    `combat` selects the flavour: the forward route vanquishes each point with its
    clear radius, while a transit leg only walks it.
    """

    kind: str  # 'point' | 'exit' | 'action' | 'wait_map'
    step_name: str
    map_id: int
    point: Coordinate | None = None
    key: str = ''
    value: object = None
    number: int = 0
    combat: bool = False


def _iter_path_items(path: Sequence[object]) -> list[tuple[str, object]]:
    """Flatten a route path into (keyword, value) items in walking order."""

    if _is_plain_path(path):
        return [('path', path)]

    items: list[tuple[str, object]] = []
    for segment in path:
        items.extend(_iter_segment_items(segment))
    return items


def _transit_leg_map_id(definition: VanquishDefinition, index: int) -> int:
    """Map one transit leg walks in: its own target, not the final map."""
    if 0 <= index < len(definition.transit_ids) and definition.transit_ids[index] > 0:
        return int(definition.transit_ids[index])
    return int(definition.explorable_id or definition.outpost_id)


def _transit_next_map_id(definition: VanquishDefinition, index: int) -> int:
    if index + 1 < len(definition.transit_ids) and definition.transit_ids[index + 1] > 0:
        return int(definition.transit_ids[index + 1])
    return int(definition.explorable_id)


def _vanquish_route_map_id(definition: VanquishDefinition) -> int:
    return int(definition.explorable_id or definition.outpost_id)


def _vanquish_route_items(definition: VanquishDefinition) -> list[RouteItem]:
    """Every walking step in planner order, split by point and by keyword.

    Transit legs are expanded by the same code as the vanquish route, so the
    Navigation list shows one step per waypoint for both and every step name
    carries the map it walks in. The reverse sweeps stay one step: they re-walk
    the whole path, not a single waypoint.
    """

    items: list[RouteItem] = []
    point_number = 0
    action_number = 0

    def _add_point(map_id: int, point: Coordinate, *, combat: bool, exit_target: int = 0) -> None:
        nonlocal point_number
        point_number += 1
        items.append(
            RouteItem(
                kind='exit' if exit_target > 0 else 'point',
                step_name=f'Point {point_number} (map {map_id})',
                map_id=map_id,
                point=point,
                value=exit_target if exit_target > 0 else None,
                number=point_number,
                combat=combat,
            )
        )

    def _add_action(map_id: int, label: str, key: str, value: object, *, combat: bool) -> None:
        nonlocal action_number
        action_number += 1
        items.append(
            RouteItem(
                kind='wait_map' if key == 'map' else 'action',
                step_name=f'Action {action_number}: {label}',
                map_id=map_id,
                key=key,
                value=value,
                number=action_number,
                combat=combat,
            )
        )

    for index, transit_path in enumerate(definition.transit_paths):
        map_id = _transit_leg_map_id(definition, index)
        next_map_id = _transit_next_map_id(definition, index)

        if _is_plain_path(transit_path) and next_map_id > 0:
            # A plain transit leg used to be one MoveAndExitMap: walked in order and
            # exited at the portal. Split by point, the exit stays on the last one.
            points = _coordinate_path(transit_path, f'transit path {index + 1}')
            for position, point in enumerate(points):
                is_last = position == len(points) - 1
                _add_point(map_id, point, combat=False, exit_target=next_map_id if is_last else 0)
            if not points:
                _add_action(map_id, f'map {next_map_id}', 'map', next_map_id, combat=False)
            continue

        for key, value in _iter_path_items(transit_path):
            if key == 'path':
                for point in _coordinate_path(value, f'transit path {index + 1}'):
                    _add_point(map_id, point, combat=False)
                continue
            _add_action(map_id, key, key, value, combat=False)

        # The same explicit wait the leg builder appends, so a structured leg also
        # ends on the map it walks into.
        if next_map_id > 0 and definition.explorable_id > 0:
            _add_action(map_id, f'map {next_map_id}', 'map', next_map_id, combat=False)

    route_map_id = _vanquish_route_map_id(definition)
    for key, value in _iter_path_items(definition.vanquish_path):
        if key == 'path':
            for point in _coordinate_path(value, 'vanquish path'):
                _add_point(route_map_id, point, combat=True)
            continue
        _add_action(route_map_id, key, key, value, combat=True)

    return items


def _build_route_item(definition: VanquishDefinition, item: RouteItem) -> BehaviorTree:
    """Build the tree for one route item, labelled with its step name."""

    if item.kind == 'wait_map':
        return BT.WaitForMapLoad(
            map_id=int(item.value or 0),
            timeout_ms=TRANSIT_TIMEOUT_MS,
        )

    if item.kind == 'action':
        children = _build_keyword_action(
            definition,
            str(item.key),
            item.value,
            float(forward_clear_radius) if item.combat else 0.0,
            item.combat,
            item.combat,
        )
        if not children:
            return BT.Succeeder(name=f'{item.step_name}:Empty')
        return BT.Sequence(name=item.step_name, children=children)

    point = item.point
    if point is None:
        return BT.Succeeder(name=f'{item.step_name}:Empty')

    if item.kind == 'exit':
        return BT.MoveAndExitMap(
            [point],
            target_map_id=int(item.value or 0),
            timeout_ms=TRANSIT_TIMEOUT_MS,
            log=True,
        )

    if item.combat:
        return _build_forward_point(definition, point, item.number)

    # A transit waypoint: the same movement the leg builder used before the split
    # (pause on combat, no clear radius), just walked one point at a time.
    return BT.Move([point], pause_on_combat=True, log=False)


def _recovery_suppression(
    suppressed: bool,
    since_ms: float,
    now_ms: float,
) -> tuple[bool, float, bool]:
    """Decide whether a resign still blocks recovery.

    Returns `(blocked, suppressed_since_ms, timed_out)`.

    The widget marks its own resign around `BT.Resign`, because the core service
    that ships with the planner reads `party_wipe_recovery_suppressed` and this
    widget keeps that flag raised for its whole life. The timeout exists because a
    tree reset during the resign can leave the marker set, and a stuck marker
    would silently disable recovery for the rest of the session.
    """

    if not suppressed:
        return False, 0.0, False
    if since_ms <= 0.0:
        return True, now_ms, False
    if now_ms - since_ms >= RECOVERY_SUPPRESS_TIMEOUT_MS:
        return False, 0.0, True
    return True, since_ms, False


def _route_resume_step(
    definition: VanquishDefinition,
    map_id: int,
    position: Coordinate,
    failed_step_name: str,
    planner_names: Sequence[str],
) -> str:
    """Nearest waypoint to the shrine, ahead or behind, in the map the party is in.

    The rule is geometric: whichever point is closest to the resurrection shrine
    wins, whether the party had already walked it or not, so the resume walk is as
    short as the map allows. Transit legs are included, because their points carry
    the map they walk in.

    One guard remains: the search stops at the next non-point step, so a resume can
    never land past a blessing, a gadget or a map change that has not run yet.
    """

    items = _vanquish_route_items(definition)
    names = list(planner_names)

    points = [
        item
        for item in items
        if item.point is not None and item.map_id == map_id and item.step_name in names
    ]
    if not points:
        return ''

    failed_index = names.index(failed_step_name) if failed_step_name in names else -1

    limit = len(names)
    for item in items:
        if item.point is not None or item.step_name not in names:
            continue
        index = names.index(item.step_name)
        if index > failed_index:
            limit = index
            break

    eligible = [item for item in points if names.index(item.step_name) < limit]
    if not eligible:
        return ''

    def _distance_sq(item: RouteItem) -> float:
        point = item.point
        if point is None:
            return float('inf')
        return (float(point[0]) - position[0]) ** 2 + (float(point[1]) - position[1]) ** 2

    return min(eligible, key=_distance_sq).step_name


def _active_definition(map_id: int) -> VanquishDefinition | None:
    """Definition whose route is the map the party is standing on.

    Automatic mode resolved a map the combos never selected, and a queue walks
    several maps in one plan, so the combo is only right in single-map runs.
    """
    if automatic_zquest and _auto_definition is not None:
        return _auto_definition
    if vanquish_queue:
        for region, map_name in vanquish_queue:
            try:
                candidate = load_definition(region, map_name)
            except Exception:
                continue
            if _vanquish_route_map_id(candidate) == map_id:
                return candidate
        return None
    return load_selected_definition()


def _map_name_from_step(step_name: str) -> str:
    """Queue map name carried by a planner step, empty when it carries none."""
    for prefix in ('Prepare ', f'{SWEEP_STEP_NAME} ', 'Complete and return '):
        if step_name.startswith(prefix):
            return step_name[len(prefix):]
    map_id = _step_name_map_id(step_name)
    if map_id > 0 and vanquish_queue:
        for region, map_name in vanquish_queue:
            try:
                if _vanquish_route_map_id(load_definition(region, map_name)) == map_id:
                    return map_name
            except Exception:
                continue
    return ''


def ZQuestPartyWipeRecoveryService() -> BehaviorTree:
    """Resume a party wipe from the nearest waypoint to the shrine.

    The core service restarts the step that was running, which after the per-point
    split is the waypoint the party died on: correct, but it walks the party back
    to that spot from the shrine. This one goes further: after a shrine revival it
    resolves the waypoint nearest to the shrine, ahead or behind the failed step and
    on the current map, so the party walks the shortest distance back into its
    route. A party defeat restarts from Prepare, the step that knows how to travel
    back, because the route coordinates belong to another map.

    The planner installs the core recovery service unconditionally, so this widget
    holds `party_wipe_recovery_suppressed` raised for its whole life to keep it
    quiet and honours its own resign marker instead.
    """

    state: dict[str, object] = {
        "active": False,
        "mode": "",
        "failed_step_name": "",
        "last_return_ms": 0.0,
        "player_was_dead": False,
        "player_dead_pos": None,
        "suppressed_since_ms": 0.0,
    }

    def _log(message: str, message_type: int = PySystem.Console.MessageType.Info) -> None:
        PySystem.Console.Log("ZQuestWipeRecovery", message, message_type)

    def _current_step(node: BehaviorTree.Node) -> str:
        step_name = str(node.blackboard.get("current_step_name", "") or "")
        if step_name:
            return step_name
        return str(node.blackboard.get("last_active_planner_step_name", "") or "")

    def _planner_step_names() -> list[str]:
        if botting_tree is None:
            return []
        try:
            return list(botting_tree.GetNamedPlannerStepNames() or [])
        except Exception:
            return []

    def _detect_revive_teleport() -> bool:
        """Report a move from the death spot to a distant shrine."""

        try:
            player_id = Player.GetAgentID()
            if not Agent.IsValid(player_id):
                return False
            current_pos = Agent.GetXY(player_id)
            is_dead = bool(Agent.IsDead(player_id))
        except Exception:
            return False

        def _far(death_pos) -> bool:
            return math.hypot(death_pos[0] - current_pos[0], death_pos[1] - current_pos[1]) > 1200.0

        if is_dead:
            if not state["player_was_dead"]:
                state["player_was_dead"] = True
                state["player_dead_pos"] = current_pos
                return False
            death_pos = state["player_dead_pos"]
            if death_pos and _far(death_pos):
                # Some revive flows teleport the dead agent before it becomes alive.
                state["player_was_dead"] = False
                state["player_dead_pos"] = None
                return True
            return False

        if not state["player_was_dead"]:
            return False

        state["player_was_dead"] = False
        death_pos = state["player_dead_pos"]
        state["player_dead_pos"] = None
        return bool(death_pos) and _far(death_pos)

    def _player_is_alive() -> bool:
        try:
            player_id = Player.GetAgentID()
            return bool(Agent.IsValid(player_id) and not Agent.IsDead(player_id))
        except Exception:
            return False

    def _can_resume_in_explorable() -> bool:
        try:
            return bool(Map.IsMapReady() and Map.IsExplorable() and _player_is_alive())
        except Exception:
            return False

    def _can_resume_from_outpost() -> bool:
        try:
            return bool(Map.IsMapReady() and Map.IsOutpost())
        except Exception:
            return False
    def _reset_state(node: BehaviorTree.Node) -> None:
        state["active"] = False
        state["mode"] = ""
        state["failed_step_name"] = ""
        state["last_return_ms"] = 0.0
        state["player_was_dead"] = False
        state["player_dead_pos"] = None
        node.blackboard["party_wipe_recovery_active"] = False
        node.blackboard["party_wipe_recovery_mode"] = ""
        node.blackboard["party_wipe_recovery_step_name"] = ""

    def _begin_recovery(node: BehaviorTree.Node, mode: str) -> None:
        # Whatever was queued when the party died would otherwise run after the
        # revive and fight the step the recovery just resumed at. The core service
        # flushes here for the same reason.
        from Py4GWCoreLib.py4gwcorelib_src.ActionQueue import ActionQueueManager

        state["active"] = True
        state["mode"] = mode
        state["failed_step_name"] = _current_step(node)
        state["last_return_ms"] = 0.0
        node.blackboard["party_wipe_recovery_active"] = True
        node.blackboard["party_wipe_recovery_mode"] = mode
        node.blackboard["party_wipe_recovery_step_name"] = state["failed_step_name"]
        ActionQueueManager().ResetAllQueues()
        detail = (
            "Returning to the outpost to restart from Prepare."
            if mode == "defeated"
            else "Waiting for the shrine revival."
        )
        _log(
            f"Party wipe on '{state['failed_step_name']}'. {detail}",
            PySystem.Console.MessageType.Warning,
        )

    def _resolve_restart_step(mode: str) -> str:
        failed_step_name = str(state["failed_step_name"] or "")
        names = _planner_step_names()

        if mode == "defeated":
            # From an outpost the route coordinates belong to another map, so the
            # only step that can get the party back there is the preparation. A
            # queue has one preparation per entry, so the failed step names the
            # map to return to instead of the first Prepare in the plan.
            if vanquish_queue:
                map_name = _map_name_from_step(failed_step_name)
                if map_name and f'Prepare {map_name}' in names:
                    return f'Prepare {map_name}'
            for step_name in names:
                if step_name.startswith("Prepare "):
                    return step_name
            return failed_step_name

        try:
            # Automatic mode resolved a map the combos never selected, so the plan
            # that is running belongs to `_auto_definition`. A queue walks several
            # maps, so the one that matters is the map the party is standing on.
            player_id = Player.GetAgentID()
            position = Agent.GetXY(player_id)
            map_id = int(Map.GetMapID() or 0)
            definition = _active_definition(map_id)
        except Exception as error:
            _log(f"Could not resolve the shrine resume point: {error}", PySystem.Console.MessageType.Warning)
            return failed_step_name

        if definition is None:
            _log(
                f"No queued map matches map {map_id}; restarting '{failed_step_name}' instead.",
                PySystem.Console.MessageType.Warning,
            )
            return failed_step_name

        step_name = _route_resume_step(definition, map_id, position, failed_step_name, names)
        if step_name:
            _log(
                f"Shrine at ({position[0]:.0f}, {position[1]:.0f}) on map {map_id}: "
                f"resuming at '{step_name}'.",
                PySystem.Console.MessageType.Success,
            )
            return step_name

        _log(
            f"No waypoint on map {map_id}; restarting '{failed_step_name}' instead.",
            PySystem.Console.MessageType.Warning,
        )
        return failed_step_name

    def _request_restart(node: BehaviorTree.Node, mode: str) -> bool:
        step_name = _resolve_restart_step(mode)
        if not step_name:
            _log("Recovery finished but no planner step could be resolved.", PySystem.Console.MessageType.Warning)
            return False

        node.blackboard["party_wipe_recovery_step_name"] = step_name
        node.blackboard["current_step_name"] = step_name
        node.blackboard["last_active_planner_step_name"] = step_name
        node.blackboard["restart_step_name_request"] = step_name
        return True

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        # The planner installs the core recovery service unconditionally, so the
        # only way to keep it quiet is to hold its flag raised. The widget's own
        # resign marker is what this service honours.
        node.blackboard["party_wipe_recovery_suppressed"] = True

        now = _now_ms()
        blocked, state["suppressed_since_ms"], timed_out = _recovery_suppression(
            bool(node.blackboard.get(_RESIGNING_KEY, False)),
            float(state["suppressed_since_ms"]),
            now,
        )
        if timed_out:
            node.blackboard[_RESIGNING_KEY] = False
            _log(
                "The resign marker never cleared; recovery re-armed.",
                PySystem.Console.MessageType.Warning,
            )
        if blocked:
            # The party dying here is a resign we asked for, not a wipe.
            _reset_state(node)
            return BehaviorTree.NodeState.RUNNING

        revived_at_shrine = _detect_revive_teleport()
        try:
            party_wiped = bool(Checks.Party.IsPartyWiped())
            party_defeated = bool(GLOBAL_CACHE.Party.IsPartyDefeated())
        except Exception:
            party_wiped = False
            party_defeated = False

        if not bool(state["active"]):
            if not (party_wiped or party_defeated or revived_at_shrine):
                node.blackboard["party_wipe_recovery_active"] = False
                return BehaviorTree.NodeState.RUNNING

            mode = "defeated" if party_defeated else "shrine"
            _begin_recovery(node, mode)

            if mode == "shrine" and revived_at_shrine and _can_resume_in_explorable():
                restarted = _request_restart(node, mode)
                _reset_state(node)
                return BehaviorTree.NodeState.SUCCESS if restarted else BehaviorTree.NodeState.FAILURE
            return BehaviorTree.NodeState.RUNNING

        if party_defeated and state["mode"] != "defeated":
            state["mode"] = "defeated"
            _log("The shrine recovery became a party defeat; switching to outpost recovery.")

        node.blackboard["party_wipe_recovery_active"] = True
        node.blackboard["party_wipe_recovery_mode"] = state["mode"]

        if state["mode"] == "shrine":
            if _can_resume_from_outpost():
                state["mode"] = "defeated"
                _log("The party returned to an outpost during shrine recovery; switching to outpost recovery.")
            else:
                if revived_at_shrine or (not party_wiped and _can_resume_in_explorable()):
                    restarted = _request_restart(node, "shrine")
                    _reset_state(node)
                    return BehaviorTree.NodeState.SUCCESS if restarted else BehaviorTree.NodeState.FAILURE
                return BehaviorTree.NodeState.RUNNING

        if _can_resume_from_outpost():
            restarted = _request_restart(node, "defeated")
            _reset_state(node)
            return BehaviorTree.NodeState.SUCCESS if restarted else BehaviorTree.NodeState.FAILURE

        if now - float(state["last_return_ms"]) >= 1000.0:
            state["last_return_ms"] = now
            try:
                GLOBAL_CACHE.Party.ReturnToOutpost()
            except Exception as error:
                _log(f"ReturnToOutpost failed: {error}", PySystem.Console.MessageType.Warning)
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='ZQuestPartyWipeRecovery',
            action_fn=_tick,
            aftercast_ms=0,
        )
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


def _mark_recovery_suppression(value: bool) -> BehaviorTree:
    """Set or clear the widget's own resign marker.

    Kept separate from `party_wipe_recovery_suppressed`, which this widget holds
    raised so the core recovery service never acts.
    """

    def _set(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        node.blackboard[_RESIGNING_KEY] = bool(value)
        return BehaviorTree.NodeState.SUCCESS

    return _action(f'MarkResigning:{value}', _set)


def _build_run_completion(
    definition: VanquishDefinition,
    is_last_queue_entry: bool = True,
) -> BehaviorTree:
    """Record the run and resign only when the party still has to be in an outpost.

    The trip back is needed by the repeat loop, which restarts from an outpost;
    by the staging flow, whose reward step is claimed in the Great Temple and can
    only map-travel from an outpost; and by every queue entry whose next Prepare
    still has to travel.

    The last entry of a queue is the exception: with nothing left to walk, the
    party stays in the map it just cleared instead of being dragged back. The loop
    keeps its resign even there, because its next pass starts from an outpost.
    """
    children: list[BehaviorTree] = [_action('RecordRunCompletion', _mark_run_completed)]

    # A queue needs the outpost only while another entry follows; the loop and the
    # signpost flow need it every time.
    needs_outpost = bool(loop_runs or take_zquest or (vanquish_queue and not is_last_queue_entry))
    if needs_outpost:
        children.append(_mark_recovery_suppression(True))
        children.append(
            BT.Resign(
                wait_for_map_load=True,
                target_map_id=definition.outpost_id,
                multi_account=True,
                log=True,
            )
        )
        children.append(_mark_recovery_suppression(False))

    return BT.Sequence(
        name=f'Complete:{definition.map_name}',
        children=children,
    )


def _isolation_enabled() -> bool:
    """Whether the botting tree isolates this account from the wider group.

    Mirrors the `Account Isolation` checkbox of the botting tree UI. While it is
    on, the shared-memory gate only delivers messages between accounts that share
    a party or an isolation group, so a party that does not exist yet cannot be
    formed over the bus.
    """
    tree = botting_tree
    if tree is None:
        return False
    try:
        return bool(tree.IsIsolationEnabled())
    except Exception:
        return False


def _build_form_party() -> BehaviorTree:
    """Disband, gather the group on the leader's map and invite everyone back.

    `BT.CreateParty(multibox_invite=True)` is the owning wrapper for this flow:
    `LeaveParty` first, then `SummonAllAccounts` for the accounts that are on a
    different map (it travels them to the leader's outpost, or to the guild hall
    when the leader is in one), and finally `InviteAllAccounts`. Running it as the
    first step means every run starts from a known party state instead of
    inheriting whatever the previous run left behind.

    The shared-memory census runs first, so the log records who this client could
    see at the moment it asked for a party.

    Skipped when `Account Isolation` is enabled: the shared-memory gate refuses
    messages between accounts that are not in the same party or isolation group,
    so with no party yet the summon and invite would be dropped (each refusal
    logs a warning and returns -1, so the step would silently do nothing) while
    the local `LeaveParty` still disbanded whatever was left.
    """

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        # The census runs even when the step is skipped: it is the record of who
        # this client could see when the run asked for a party, and that is what
        # tells a missing account apart from a hidden or misplaced one.
        census = _action('LogSharedMemoryCensus', _log_shared_memory_census)
        if _isolation_enabled():
            return BT.Sequence(
                name='FormPartyIsolated',
                children=[
                    census,
                    BT.Succeeder('Form Party Skipped: Account Isolation'),
                ],
            )
        return BT.Sequence(
            name='FormParty',
            children=[
                census,
                BT.CreateParty(
                    multibox_invite=True,
                    timeout_ms=REMOTE_PARTY_TIMEOUT_MS,
                    poll_interval_ms=100,
                    log=True,
                ),
            ],
        )

    return BT.Subtree(name='Form Party', subtree_fn=_build)


def _build_hero_load(hero_ids: Sequence[int]) -> BehaviorTree:
    """Fill the plan's hero slots with this account's own heroes.

    `LoadParty` is the owner: leader-only, outpost-only, and it skips heroes the
    party already holds. `clear_existing` is not optional here -- the run's own
    `LeaveParty` kicks players, not heroes, so without it a queue would carry the
    previous map's heroes into the next outpost and eat the free slots.

    There is no unlock query, so the step verifies what the party actually
    received and logs the difference instead of assuming the add worked.
    """
    expected = list(dict.fromkeys(int(hero_id) for hero_id in hero_ids if int(hero_id) > 0))

    def _verify(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        present: set[int] = set()
        for hero in GLOBAL_CACHE.Party.GetHeroes() or []:
            raw_id = getattr(hero, 'hero_id', 0)
            hero_id = int(raw_id.GetID() or 0) if hasattr(raw_id, 'GetID') else int(raw_id or 0)
            if hero_id > 0:
                present.add(hero_id)
        missing = [hero_id for hero_id in expected if hero_id not in present]
        if missing:
            names = ', '.join(f'{_hero_label(hero_id)} ({hero_id})' for hero_id in missing)
            PySystem.Console.Log(
                MODULE_NAME,
                f'Party heroes not added: {names}. Not unlocked on this account, or the '
                'party had no free slot for them.',
                PySystem.Console.MessageType.Warning,
            )
        return BehaviorTree.NodeState.SUCCESS

    return BT.Sequence(
        name='LoadPartyHeroes',
        children=[
            RoutinesBT.Party.LoadParty(hero_ids=expected, clear_existing=True, log=True),
            _action('VerifyPartyHeroes', _verify),
        ],
    )


def _accounts_outside_plan(plan: Sequence[str]) -> list[str]:
    """Visible accounts this run will not invite, this client excluded.

    They took the signpost quest along with everyone else and would never run it.
    The main account is the only client that runs this widget, so it is the one
    that knows both ends of the comparison and can drop those quests on their
    behalf.
    """
    participants = {str(email or '').strip() for email in plan}
    sender = str(Player.GetAccountEmail() or '').strip()
    outsiders: list[str] = []
    for account in GLOBAL_CACHE.ShMem.GetAllAccountData():
        email = str(getattr(account, 'AccountEmail', '') or '').strip()
        if not email or email == sender or email in participants:
            continue
        outsiders.append(email)
    return outsiders


def _build_party_rebuild() -> BehaviorTree:
    """Rebuild the group at the outpost the run just travelled to.

    Honours the Party Config tab: when a plan exists for that outpost's party
    size, only those accounts are summoned and invited. With no plan for that
    size the original behaviour is kept (summon whoever is off-map, invite
    everyone on it), so an untouched tab runs exactly as before.

    Resolved inside a subtree on purpose: the party size belongs to the outpost,
    and the planner is built before the run knows which outpost that is.
    """

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        # Isolation refuses shared-memory traffic between accounts outside the
        # same party, so summon and invite cannot land: skipping is the same rule
        # the Form Party step already follows.
        if _isolation_enabled():
            return BT.Succeeder('Party Rebuild Skipped: Account Isolation')

        plan = _party_plan_for_current_map()
        if not plan:
            return BT.CreateParty(
                multibox_invite=True,
                timeout_ms=REMOTE_PARTY_TIMEOUT_MS,
                poll_interval_ms=100,
                log=True,
            )

        # One plan, two owners: the accounts are summoned and invited over shared
        # memory, the heroes are added locally by this account.
        hero_ids, plan_emails = _split_plan(plan)

        # Everyone took the signpost quest, so the accounts this plan leaves out
        # hold one they will never run. Three of those and the signpost stops
        # handing out new ones -- silently, because at the limit it answers with
        # the generic "quest still active" line. The main account withdraws them
        # through the shared command, best effort: housekeeping must never fail
        # the vanquish.
        children: list[BehaviorTree] = []
        outsiders = _accounts_outside_plan(plan_emails)
        if _active_vanquish_quest_id > 0 and outsiders:
            children.append(
                BT.Selector(
                    name='QuestCleanupBestEffort',
                    children=[
                        RoutinesBT.Shared.SendAndWait(
                            command=SharedCommandType.AbandonQuest,
                            params=(float(_active_vanquish_quest_id), 0.0, 0.0, 0.0),
                            recipients=outsiders,
                            include_self=False,
                            refs_blackboard_key='quest_cleanup_refs',
                            timeout_ms=ZQUEST_MESSAGE_TIMEOUT_MS,
                            log=True,
                        ),
                        BT.Succeeder('QuestCleanupSkipped'),
                    ],
                )
            )

        # Parked wherever the run ends, in every mode: a queue walks map after
        # map, so an account this plan leaves out would otherwise be left in
        # whichever outpost it was last summoned to. Fire-and-forget, same as the
        # reward step's own guild hall travel: a map load outlives any message ack
        # worth waiting for. No leave is sent first -- this run already kicked
        # them out of the party. No quest dependency either: the abandon above is
        # the only part that needs one.
        if outsiders:
            children.append(
                BT.Selector(
                    name='OutsidersToGuildHallBestEffort',
                    children=[
                        RoutinesBT.Shared.SendCommand(
                            command=SharedCommandType.TravelToGuildHall,
                            recipients=outsiders,
                            include_self=False,
                            refs_blackboard_key='outsider_gh_refs',
                            log=True,
                        ),
                        BT.Succeeder('GuildHallTravelSkipped'),
                    ],
                )
            )

        # One batched summon for the whole plan: SendCommand already takes a
        # recipient list, so the send/ack round trip happens once instead of once
        # per account (3-4s each in the live log). Invites stay per-account
        # because the native InvitePlayer call takes a single name.
        children.append(
            RoutinesBT.Multibox.SummonAllAccounts(
                timeout_ms=REMOTE_PARTY_TIMEOUT_MS,
                poll_interval_ms=100,
                log=True,
                only_emails=plan_emails,
            )
        )
        for email in plan_emails:
            children.append(
                BT.InviteAccountByEmail(
                    account_email=email,
                    timeout_ms=REMOTE_PARTY_TIMEOUT_MS,
                    log=True,
                )
            )
        # Heroes last: they fill whatever slots the invited accounts left, and the
        # native add is instant, so the slow half of the rebuild goes first.
        if hero_ids:
            children.append(_build_hero_load(hero_ids))
        return BT.Sequence(name='RebuildParty', children=children)

    return BT.Subtree(name='Party Rebuild', subtree_fn=_build)


def get_execution_steps(definition: VanquishDefinition | None) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Named planner steps for a run.

    `definition=None` is the automatic ZQuest handling before the map is known:
    the plan stops after the signpost, with a resolver step that reads the
    accepted quest and asks the widget for the real plan.
    """
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    # Staging is its own named step so Navigation shows it and it can be
    # restarted on its own. Form Party exists only as its preparation: the
    # signpost dialog is broadcast to the other accounts, so they have to be
    # gathered onto the leader's map first. Every other flow builds its party
    # inside Prepare, at the vanquish outpost, so forming it here would only be
    # disbanded again one step later.
    if take_zquest:
        steps.append(('Form Party', _build_form_party))
        steps.append(
            (
                'Take ZQuest',
                lambda: _build_zquest_staging(),
            )
        )

    if definition is None:
        steps.append(('Resolve ZQuest', _build_auto_zquest_resolver))
        return steps

    steps.append(
        (
            f'Prepare {definition.map_name}',
            lambda definition=definition: _build_run_preparation(definition),
        )
    )

    # Every walking step, one per waypoint and per keyword, transit legs included,
    # each named with the map it walks in. The outpost exit lives in Prepare, so
    # maps with just an outpost path still show none.
    for item in _vanquish_route_items(definition):
        steps.append(
            (
                item.step_name,
                lambda definition=definition, item=item: _build_route_item(definition, item),
            )
        )

    steps.extend(
        [
            (
                SWEEP_STEP_NAME,
                lambda definition=definition: _build_cleanup_sweeps(definition),
            ),
            (
                'Complete and return',
                lambda definition=definition: _build_run_completion(definition),
            ),
        ]
    )

    # Staging flow ends by claiming the reward and dissolving the party, so the
    # run finishes in the guild hall instead of the temple.
    if take_zquest:
        steps.append(
            (
                'Take ZQuest Reward',
                lambda: _build_zquest_reward(),
            )
        )
    return steps


def _queue_definitions() -> list[VanquishDefinition]:
    """Definitions for the queue, in order, one per map id.

    Two pack files can describe the same map (`DeldrimorBowl` lives under two
    region folders), and a repeated map id would produce duplicate planner step
    names, which is exactly what the restart-by-name logic cannot tell apart.
    """
    definitions: list[VanquishDefinition] = []
    seen: set[int] = set()
    for region, map_name in vanquish_queue:
        definition = load_definition(region, map_name)
        route_map_id = _vanquish_route_map_id(definition)
        if route_map_id in seen:
            continue
        seen.add(route_map_id)
        definitions.append(definition)
    if not definitions:
        raise ValueError('The vanquish queue is empty: add at least one map in Config.')
    return definitions


def _queue_entry_steps(
    definition: VanquishDefinition,
    is_last_queue_entry: bool,
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Prepare, walk, sweep and complete one queued map.

    Every entry repeats the same four steps, and the planner restarts steps by
    name, so the sweep and completion names carry the map name. The route steps
    already carry theirs as `(map M)`.

    `is_last_queue_entry` only reaches the completion step: the last entry leaves
    the party in the map it cleared, every other one resigns so the next Prepare
    can travel.
    """
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        (
            f'Prepare {definition.map_name}',
            lambda definition=definition: _build_run_preparation(definition),
        )
    ]
    for item in _vanquish_route_items(definition):
        steps.append(
            (
                item.step_name,
                lambda definition=definition, item=item: _build_route_item(definition, item),
            )
        )
    steps.append(
        (
            f'{SWEEP_STEP_NAME} {definition.map_name}',
            lambda definition=definition: _build_cleanup_sweeps(definition),
        )
    )
    steps.append(
        (
            f'Complete and return {definition.map_name}',
            lambda definition=definition, is_last_queue_entry=is_last_queue_entry: _build_run_completion(
                definition,
                is_last_queue_entry,
            ),
        )
    )
    return steps


def get_queue_execution_steps(
    definitions: Sequence[VanquishDefinition],
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """One plan for the whole queue: one vanquish per entry, no Form Party.

    A filled queue turns automatic ZQuest handling off (`take_zquest` is
    `automatic_zquest and not vanquish_queue`), and Form Party exists only as
    that flow's preparation. Each entry builds its own party inside Prepare, at
    that map's outpost.
    """
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []
    last_index = len(definitions) - 1
    for index, definition in enumerate(definitions):
        steps.extend(
            _queue_entry_steps(
                definition,
                is_last_queue_entry=index == last_index,
            )
        )
    return steps


def _configure_upkeep(tree: BottingTree) -> None:
    """Push the run configuration and the consumable upkeep service.

    Called once at creation and again whenever a consumables toggle changes;
    `ConfigureUpkeep` only replaces the upkeep trees, so it does not disturb a
    running planner (the same runtime-reconfigure pattern the Reputation Farmer
    and Shards Of Orr BTs use).
    """
    tree.Config.ConfigureUpkeep(
        looting_enabled=AUTO_LOOT,
        resurrection_scroll=True,
        # The widget installs its own recovery service below: it resumes at the
        # nearest waypoint to the shrine instead of the failed step, and a party
        # defeat goes back through Prepare, which is the step that can travel.
        enable_party_wipe_recovery=False,
        heroai_state_logging=True,
        heroai_state_log_interval_ms=5000,
        consumable_upkeeps=_enabled_consumable_upkeeps(),
    )
    # ConfigureUpkeep replaces every service tree, so this has to be re-added on
    # each call, not only at creation.
    tree.AddServiceTree('ZQuestPartyWipeRecoveryService', ZQuestPartyWipeRecoveryService)


def ensure_botting_tree() -> BottingTree:
    global botting_tree
    global last_load_error
    global loaded_region_index
    global loaded_map_index

    if botting_tree is None:
        # Automatic mode starts from the discovery plan: the map is unknown until
        # the signpost quest has been accepted and read. The queue replaces both
        # with one plan built from its own list.
        if vanquish_queue:
            routine = get_queue_execution_steps(_queue_definitions())
            definition: VanquishDefinition | None = None
        else:
            definition = None if automatic_zquest else load_selected_definition()
            routine = get_execution_steps(definition)
        last_load_error = ''
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=routine,
            routine_name='PyQuishAISequence',
            repeat=loop_runs,
            reset=False,
            multi_account=True,
            auto_loot=AUTO_LOOT,
            configure_fn=_configure_upkeep,
        )
        botting_tree.UI.override_draw_help(_draw_help)
        loaded_region_index = region_index
        loaded_map_index = map_index

    return botting_tree


def _request_rebuild() -> None:
    global pending_rebuild
    pending_rebuild = True


def _request_bot_stop(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
    """Ask the widget loop to stop the bot and keep the step alive until it does.

    Returning RUNNING instead of failing is deliberate: a failure would make the
    planner restart the current named step, and the stop has to run outside the
    tree tick so `BottingTree.Stop` can reset the tree and restore the account
    state safely.
    """
    global _stop_after_sweeps
    _stop_after_sweeps = True
    return BehaviorTree.NodeState.RUNNING


def _apply_pending_stop() -> None:
    """Stop the bot when the tree requested it, outside of the tree tick."""
    global _stop_after_sweeps
    if not _stop_after_sweeps:
        return
    _stop_after_sweeps = False
    if botting_tree is None:
        return
    _flush_enemy_log('incomplete')
    botting_tree.Stop()
    PySystem.Console.Log(
        MODULE_NAME,
        'Vanquish incomplete after both cleanup sweeps. Bot stopped.',
        PySystem.Console.MessageType.Warning,
    )


def _apply_pending_rebuild() -> None:
    global botting_tree
    global pending_rebuild
    global last_load_error
    global region_index
    global map_index
    global _auto_definition

    if not pending_rebuild:
        return
    if botting_tree is not None and botting_tree.IsStarted():
        return

    previous_tree = botting_tree
    attempted_region = _selected_region()
    attempted_map = _selected_map()
    if previous_tree is not None:
        previous_tree.Stop()
    botting_tree = None
    pending_rebuild = False
    # A fresh tree in automatic mode goes back to the discovery plan, so the map
    # resolved by the previous run must not survive it.
    _auto_definition = None

    try:
        ensure_botting_tree()
    except Exception as error:
        botting_tree = previous_tree
        region_index = loaded_region_index
        map_index = loaded_map_index
        last_load_error = (
            f'{attempted_region}/{attempted_map}: {error}'
        )
        PySystem.Console.Log(
            MODULE_NAME,
            (
                f'Failed to load {attempted_region}/{attempted_map}: {error}. '
                'The previous map selection was restored.'
            ),
            PySystem.Console.MessageType.Error,
        )


def _staging_district() -> int:
    """Random low-traffic district channel for a staging travel."""
    return int(random.choice(STAGING_DISTRICTS))


def _build_travel_to_map(map_id: int, label: str) -> BehaviorTree:
    """Travel to a map unless the party is already there.

    Shared by the staging travel, the reward travel and the approach to the
    vanquish outpost, so all three land in the same randomised low-traffic
    district instead of the default one. Travel is local: a formed party travels
    with its leader, and broadcasting a TravelToMap command per follower would
    fight the party travel.
    """

    if map_id <= 0:
        return BT.Succeeder(name=f'No{label}Travel')

    def _is_current_map() -> bool:
        return int(Map.GetMapID() or 0) == map_id

    def _request_travel() -> BehaviorTree.NodeState:
        Map.TravelToDistrict(map_id, _staging_district())
        return BehaviorTree.NodeState.SUCCESS

    return BT.Selector(
        name=f'Ensure{label}',
        children=[
            _condition(f'AlreadyIn{label}', _is_current_map),
            BT.Sequence(
                name=f'TravelTo{label}',
                children=[
                    _action(f'Request{label}Travel', _request_travel),
                    BT.WaitForMapLoad(map_id=map_id),
                ],
            ),
        ],
    )


def _nearest_living_agent(
    position: tuple[float, float],
    *,
    name_filter: str = '',
    max_distance: float = 0.0,
) -> tuple[int, tuple[float, float]]:
    """Nearest living, non-player agent to a point, as (agent_id, xy).

    Players are excluded so a party member standing on the spot cannot be picked
    instead of the NPC. Names come from `Agent.GetNameByID`, which returns an
    empty string until the client has decoded the name, hence the retry gate the
    callers wrap around this.
    """
    player_id = int(Player.GetAgentID() or 0)
    best_id = 0
    best_position = (0.0, 0.0)
    best_distance = 0.0

    for agent_id in AgentArray.GetAgentArray():
        if agent_id == player_id or not Agent.IsLiving(agent_id):
            continue
        if Agent.IsPlayer(agent_id):
            continue
        if name_filter:
            name = str(Agent.GetNameByID(agent_id) or '')
            if name_filter not in name.lower():
                continue
        x, y = Agent.GetXY(agent_id)
        distance = math.hypot(x - position[0], y - position[1])
        if max_distance > 0.0 and distance > max_distance:
            continue
        if best_id == 0 or distance < best_distance:
            best_id = int(agent_id)
            best_position = (float(x), float(y))
            best_distance = distance
    return best_id, best_position


def _leader_anchor() -> tuple[float, float]:
    """Leader position, falling back to the staging anchor when it cannot be read.

    `Player.GetXY` is the only source that reflects where the party actually is;
    the staging anchor is the last resort for the frames where the map data is not
    ready yet, so the resolver always has a usable reference.
    """
    try:
        position = Player.GetXY()
        if position:
            return float(position[0]), float(position[1])
    except Exception:
        pass
    return VANQUISH_SIGNPOST


def _resolve_vanquish_signpost() -> tuple[int, tuple[float, float]]:
    """Nearest 'Zaishen Vanquish' signpost to the leader.

    Embark Beach holds several signposts, so the name alone does not pick one. The
    closest to the leader is the one the party is actually going to walk to,
    whichever side of the outpost it spawned on; a fixed anchor assumed one side.
    The anchor stays as the reference for the frames where the position cannot be
    read yet.
    """
    return _nearest_living_agent(_leader_anchor(), name_filter=ZQUEST_SIGNPOST_NAME)


def _resolve_reward_npc() -> tuple[int, tuple[float, float]]:
    """Reward NPC in the Great Temple of Balthazar, resolved by its name.

    "Zehnchu [Zaishen Challenge]" is a single NPC standing among others, so the
    name is the identity and no distance filter is needed; `Agent.GetNameByID`
    may return an empty string until the client decodes it, which is what the
    caller's retry gate is for.
    """
    return _nearest_living_agent(ZQUEST_REWARD_NPC, name_filter=ZQUEST_REWARD_NPC_NAME)


def _now_ms() -> float:
    """Monotonic clock in milliseconds for the readiness deadline."""

    return time.monotonic() * 1000.0


def _remote_accounts_on_leader_map() -> tuple[bool, list[str]]:
    """Whether every other account reports the leader's map and district.

    Each account publishes its map in shared memory only after its own client is
    fully loaded, so a leader that finishes loading first sees the others still
    pointed at the previous map. The dialog fan-out resolves its agent on the
    leader and messages the rest: sending it now means the followers receive an
    order for a map they are not in yet, acknowledge it, do nothing, and the party
    ends up with only some accounts holding the quest.
    """

    sender_email = ''
    pending: list[str] = []
    try:
        sender_email = str(Player.GetAccountEmail() or '')
        map_id = int(Map.GetMapID() or 0)
        district = int(Map.GetDistrict() or 0)
    except Exception:
        return False, pending

    if map_id <= 0:
        return False, pending

    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData() or []
    except Exception:
        return False, pending

    for account in accounts:
        if not bool(getattr(account, 'IsAccount', False)):
            continue
        email = str(getattr(account, 'AccountEmail', '') or '')
        if not email or email == sender_email:
            continue
        map_struct = getattr(getattr(account, 'AgentData', None), 'Map', None)
        reported_map = int(getattr(map_struct, 'MapID', 0) or 0)
        reported_district = int(getattr(map_struct, 'District', 0) or 0)
        if reported_map != map_id:
            pending.append(email)
        elif district > 0 and reported_district > 0 and reported_district != district:
            pending.append(email)

    return not pending, pending


def _wait_remote_accounts_ready(label: str) -> BehaviorTree:
    """Hold a multibox dialog until the other accounts are in the same instance.

    Bounded on purpose: an account that is legitimately elsewhere must not stall
    the step forever, so the wait gives up after the remote party timeout and
    leaves a warning naming the accounts that were not ready.
    """

    state = {'started_ms': 0.0, 'reported': False}

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        ready, pending = _remote_accounts_on_leader_map()
        if ready:
            return BehaviorTree.NodeState.SUCCESS

        now = _now_ms()
        if state['started_ms'] <= 0.0:
            state['started_ms'] = now
        if now - state['started_ms'] < REMOTE_PARTY_TIMEOUT_MS:
            return BehaviorTree.NodeState.RUNNING

        if not state['reported']:
            state['reported'] = True
            PySystem.Console.Log(
                MODULE_NAME,
                f'{label}: {len(pending)} account(s) still not on this map after '
                f'{REMOTE_PARTY_TIMEOUT_MS // 1000}s ({", ".join(pending)}); '
                'sending the dialog anyway.',
                PySystem.Console.MessageType.Warning,
            )
            # The census right after the warning is what separates "the alt is
            # in another district" from "the alt is not publishing at all".
            for line in _shared_memory_census():
                PySystem.Console.Log(MODULE_NAME, line, PySystem.Console.MessageType.Warning)
        return BehaviorTree.NodeState.SUCCESS

    return _action(f'Wait{label}AccountsReady', _tick)


class MultiboxDialogSpec(NamedTuple):
    """Everything one multibox autodialog step needs."""

    button: int
    fallback_point: tuple[float, float]
    agent_key: str
    refs_key: str
    resolve: Callable[[], tuple[int, tuple[float, float]]]
    label: str


_SIGNPOST_DIALOG = MultiboxDialogSpec(
    button=ZQUEST_DIALOG_BUTTON,
    fallback_point=VANQUISH_SIGNPOST,
    agent_key='zquest_signpost_agent_id',
    refs_key='zquest_dialog_refs',
    resolve=_resolve_vanquish_signpost,
    label='Signpost',
)

_REWARD_DIALOG = MultiboxDialogSpec(
    button=ZQUEST_DIALOG_BUTTON,
    fallback_point=ZQUEST_REWARD_NPC,
    agent_key='zquest_reward_agent_id',
    refs_key='zquest_reward_refs',
    resolve=_resolve_reward_npc,
    label='Reward',
)


def _wait_dialog_agent(spec: MultiboxDialogSpec) -> BehaviorTree:
    """Resolve the dialog agent, waiting until the client has decoded its name.

    `BehaviorTree.WaitUntilNode` is not usable for this: a `False` from its
    condition is a terminal FAILURE, not "keep waiting", so a predicate that
    answers "not yet" burns the whole retry budget on its first evaluation. After
    a party map load the agent array exists but `Agent.GetNameByID` still returns
    empty while names decode, so the resolver answers "not yet" for a second or
    two — and the step dropped straight into the fallback branch. That branch
    interacts locally and only messages the group once the local dialog is
    accepted, so the leader ends up at the signpost with the followers still
    standing at the portal and the whole step fails on the local dialog timeout.
    """

    state = {'deadline_ms': 0.0}

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        agent_id = int(spec.resolve()[0] or 0)
        if agent_id > 0:
            node.blackboard[spec.agent_key] = agent_id
            return BehaviorTree.NodeState.SUCCESS

        now = _now_ms()
        if state['deadline_ms'] <= 0.0:
            state['deadline_ms'] = now + ZQUEST_AGENT_WAIT_MS
        if now < state['deadline_ms']:
            return BehaviorTree.NodeState.RUNNING

        PySystem.Console.Log(
            MODULE_NAME,
            f'{spec.label}: no dialog agent resolved within {ZQUEST_AGENT_WAIT_MS // 1000}s; '
            'falling back to the point-based dialog.',
            PySystem.Console.MessageType.Warning,
        )
        return BehaviorTree.NodeState.FAILURE

    return _action(f'Resolve{spec.label}DialogAgent', _tick)


def _build_multibox_dialog(spec: MultiboxDialogSpec) -> BehaviorTree:
    """Resolve an agent, fan the dialog out and wait for every account.

    The command goes to every account, this client included, so one handler does
    all the work: it walks to the agent, interacts by id and presses the button.
    Nothing runs locally in parallel, which is why the leader behaves exactly
    like the rest. When the agent cannot be resolved the point-based node takes
    over and fans out the same dialog after walking there. Confirmation is a
    message-dispatch wait, so it only proves each handler finished, not that the
    game accepted the dialog.

    It waits for the other accounts to report this map first: a leader that
    finishes loading before its followers would otherwise dispatch an order for
    an agent the followers cannot see yet, and only some of them would end up
    with the quest.
    """

    def _resolved_branch(node: BehaviorTree.Node) -> BehaviorTree:
        agent_id = int(node.blackboard.get(spec.agent_key, 0) or 0)
        if agent_id <= 0:
            return _condition('DialogAgentMissing', lambda: False)
        return BT.Sequence(
            name='DispatchAndWaitDialog',
            children=[
                BT.Subtree(name='DispatchDialog', subtree_fn=_dispatch),
                BT.Subtree(name='WaitDialogs', subtree_fn=_wait),
            ],
        )

    def _fallback_branch(node: BehaviorTree.Node) -> BehaviorTree:
        agent_id = int(node.blackboard.get(spec.agent_key, 0) or 0)
        if agent_id > 0:
            return _condition('DialogAgentAlreadyResolved', lambda: False)
        return BT.TargetNearestAndAutoDialog(
            spec.fallback_point,
            buttons=spec.button,
            multi_account=True,
            log=True,
        )

    def _dispatch(node: BehaviorTree.Node) -> BehaviorTree:
        agent_id = int(node.blackboard.get(spec.agent_key, 0) or 0)
        if agent_id <= 0:
            return BT.Succeeder('DialogDispatchSkipped')
        return RoutinesBT.Shared.SendCommand(
            command=SharedCommandType.TakeDialogWithTarget,
            params=(float(agent_id), float(spec.button), 0.0, 0.0),
            include_self=True,
            refs_blackboard_key=spec.refs_key,
            log=True,
        )

    def _wait(_node: BehaviorTree.Node) -> BehaviorTree:
        return RoutinesBT.Shared.WaitCommandDispatch(
            command=SharedCommandType.TakeDialogWithTarget,
            refs_blackboard_key=spec.refs_key,
            timeout_ms=ZQUEST_DIALOG_TIMEOUT_MS,
            poll_interval_ms=250,
            log=True,
        )

    return BT.Sequence(
        name='MultiboxDialog',
        children=[
            _wait_remote_accounts_ready(spec.label),
            BT.Selector(
                name='FindDialogAgent',
                children=[
                    _wait_dialog_agent(spec),
                    BT.Succeeder('DialogAgentNotVisibleYet'),
                ],
            ),
            BT.Selector(
                name='DialogPath',
                children=[
                    BT.Subtree(name='ResolvedDialog', subtree_fn=_resolved_branch),
                    BT.Subtree(name='FallbackDialog', subtree_fn=_fallback_branch),
                ],
            ),
            BT.Wait(duration_ms=ZQUEST_DIALOG_SETTLE_MS),
        ],
    )


def _active_quest_id() -> int:
    """The active quest id, or 0.

    Only the active quest is read, never the log. `RequestQuestInfo` is what the
    client uses to select a quest, so asking for the text of every logged quest
    walks the quest tracker through unrelated entries: the run ends up resolving a
    map, and switching the client, for a quest the party is not doing.
    """
    try:
        return int(GLOBAL_CACHE.Quest.GetActiveQuest() or 0)
    except Exception:
        return 0


def _quest_text_value(raw: object) -> str:
    """Client quest string, minus the decoder's failure sentinel.

    The async decoders answer `Timeout` when the text has not arrived yet; the
    rest of the repo treats it as a retry signal (`quest_data_src.py`), never as
    text. Returning '' keeps the poll going instead of trying to match an area
    called "Timeout".
    """
    text = str(raw or '')
    return '' if text.strip().lower() == 'timeout' else text


def _read_quest_texts(quest_id: int, request: bool, request_info: bool = False) -> tuple[str, str, str]:
    """(objectives, description, name) for a quest, empty while not ready.

    The vanquish objective is the string that names the area (`Clear Pongmei
    Valley near Kaineng City of all enemies in hard mode.`), so it is the primary
    source; the description is only a fallback and the title the last resort.

    `request_info` asks the client for the quest record itself, once per quest:
    the per-field decoders answer with the `Timeout` sentinel when the record was
    never requested, which is what the account quest cache does before it reads
    a field.
    """
    if request_info:
        GLOBAL_CACHE.Quest.RequestQuestInfo(quest_id)
    if request:
        GLOBAL_CACHE.Quest.RequestQuestObjectives(quest_id)
        GLOBAL_CACHE.Quest.RequestQuestDescription(quest_id)
        GLOBAL_CACHE.Quest.RequestQuestName(quest_id)
    objectives = ''
    if GLOBAL_CACHE.Quest.IsQuestObjectivesReady(quest_id):
        objectives = _quest_text_value(GLOBAL_CACHE.Quest.GetQuestObjectives(quest_id))
    description = ''
    if GLOBAL_CACHE.Quest.IsQuestDescriptionReady(quest_id):
        description = _quest_text_value(GLOBAL_CACHE.Quest.GetQuestDescription(quest_id))
    name = ''
    if GLOBAL_CACHE.Quest.IsQuestNameReady(quest_id):
        name = _quest_text_value(GLOBAL_CACHE.Quest.GetQuestName(quest_id))
    return objectives, description, name


def _select_map(region: str, map_name: str) -> None:
    """Point the combos at the resolved map so the UI and the plan agree."""
    global region_index
    global map_index
    if region in REGIONS:
        region_index = REGIONS.index(region)
    maps = MAP_CATALOG.get(region, ())
    if map_name in maps:
        map_index = maps.index(map_name)


def _build_auto_zquest_resolver() -> BehaviorTree:
    """Name the area from the vanquish quest the signpost just gave the party.

    The plan cannot be built before this runs: the route belongs to the map and
    the signpost picks the map. The step reads the objectives of the **active**
    quest — never the quest log, because `RequestQuestInfo` selects the quest it
    describes and walking the log would leave the client tracking an unrelated
    one — resolves the area against the map catalog and stores the definition,
    then asks the widget to swap the remaining steps for the resolved run.

    It never reports success while it is waiting: a completed pass stops the tree,
    and the swap has to happen with the tree still running, so the step stays
    RUNNING until the new plan replaces it. The clock is capped, and when it runs
    out the step logs the text it saw and reports success so the run ends instead
    of retrying a quest that will not resolve.
    """
    state: dict[str, float | str | bool] = {
        'deadline_ms': 0.0,
        'last_request_ms': 0.0,
        'last_text': '',
        'info_requested': False,
    }

    def _stop(message: str) -> BehaviorTree.NodeState:
        PySystem.Console.Log(MODULE_NAME, message, PySystem.Console.MessageType.Error)
        return BehaviorTree.NodeState.SUCCESS

    def _resolve(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _auto_definition
        global _pending_planner_swap
        global _active_vanquish_quest_id

        if _auto_definition is not None and not _pending_planner_swap:
            # The swap clears the request; seeing the definition without it means
            # the planner was not replaced and this step would run forever.
            return _stop(
                'Automatic ZQuest: the map was resolved but the planner swap did '
                'not apply. Stopping instead of walking the wrong plan.'
            )

        now = _now_ms()
        if not state['deadline_ms']:
            state['deadline_ms'] = now + ZQUEST_QUEST_RESOLVE_TIMEOUT_MS

        request = now - float(state['last_request_ms']) >= ZQUEST_QUEST_TEXT_POLL_MS
        if request:
            state['last_request_ms'] = now

        quest_id = _active_quest_id()
        if quest_id > 0:
            # The quest record is asked for once; the per-field decoders answer
            # with the `Timeout` sentinel until it has been requested.
            request_info = not bool(state['info_requested'])
            if request_info:
                state['info_requested'] = True
            objectives, description, name = _read_quest_texts(quest_id, request, request_info)
            if objectives or description or name:
                state['last_text'] = objectives or description or name
            region, map_name = (
                _resolve_map_from_text(objectives)
                or _resolve_map_from_text(description)
                or _resolve_map_from_quest_name(name)
            )
            if region and map_name:
                definition = load_definition(region, map_name)
                _select_map(region, map_name)
                _auto_definition = definition
                # Kept for the Party Config cleanup: the accounts the plan leaves
                # out hold this same quest and would never run it.
                _active_vanquish_quest_id = quest_id
                _pending_planner_swap = True
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f'Automatic ZQuest: quest {quest_id} names {region}/{map_name} '
                        f'("{state["last_text"]}"). Continuing at Prepare.'
                    ),
                    PySystem.Console.MessageType.Success,
                )
                return BehaviorTree.NodeState.RUNNING

        if now >= float(state['deadline_ms']):
            return _stop(
                'Automatic ZQuest: no map matched the active quest after '
                f'{ZQUEST_QUEST_RESOLVE_TIMEOUT_MS // 1000}s (active quest {quest_id}, '
                f'last read: "{state["last_text"] or "nothing"}"). '
                'Stop the bot, check the quest is in the log and that its area '
                'exists under Sources/aC_Scripts/PyQuishAI_maps.'
            )

        return BehaviorTree.NodeState.RUNNING

    return _action('ResolveZQuest', _resolve)


def _build_zquest_staging() -> BehaviorTree:
    """Travel to Embark Beach and take the vanquish quest from the signpost.

    Runs before Prepare travels to the vanquish outpost. The step is only
    included when automatic ZQuest handling is on, because that is the flow that
    reads the map out of the quest this step accepts; a queued run never takes it.
    """
    return BT.Sequence(
        name='TakeZQuest',
        children=[
            _build_travel_to_map(EMBARK_BEACH_MAP_ID, 'EmbarkBeach'),
            _build_multibox_dialog(_SIGNPOST_DIALOG),
        ],
    )


def _apply_pending_planner_swap() -> None:
    """Replace the discovery steps with the plan for the resolved map.

    Runs from the widget loop, after the tick that resolved the map: the running
    planner must not be mutated from inside one of its own nodes. The new steps
    are installed with `start_from` at the preparation step, so the run continues
    where the quest was accepted instead of travelling back to Embark Beach.
    """
    global _pending_planner_swap
    global _auto_definition

    if not _pending_planner_swap:
        return

    tree = botting_tree
    definition = _auto_definition
    if tree is None or definition is None or not tree.IsStarted():
        _pending_planner_swap = False
        return

    try:
        tree.SetNamedPlannerSteps(
            get_execution_steps(definition),
            start_from=f'Prepare {definition.map_name}',
            name='PyQuishAISequence',
            repeat=loop_runs,
        )
    except Exception as error:
        _pending_planner_swap = False
        _auto_definition = None
        PySystem.Console.Log(
            MODULE_NAME,
            f'Automatic ZQuest: could not build the plan for {definition.map_name}: {error}',
            PySystem.Console.MessageType.Error,
        )
        tree.Stop()
        return

    _pending_planner_swap = False
    PySystem.Console.Log(
        MODULE_NAME,
        (
            f'Automatic ZQuest: plan for {definition.region}/{definition.map_name} '
            f'installed, continuing at Prepare {definition.map_name}.'
        ),
        PySystem.Console.MessageType.Info,
    )


def _reset_auto_resolution_on_stop(tree: BottingTree) -> None:
    """Put the discovery plan back once an automatic run is over.

    The completed run replaced the planner steps with the resolved route, so a
    new start would skip the signpost and walk a map the party may no longer
    hold. Rebuilding the tree restores the discovery steps and clears the
    resolved map.
    """
    if not automatic_zquest or _auto_definition is None or tree.IsStarted():
        return
    global _active_vanquish_quest_id
    # The next run resolves its own quest; keeping the old id would let a later
    # cleanup abandon a quest this run already finished with.
    _active_vanquish_quest_id = 0
    _request_rebuild()


def _build_leave_party_and_travel_gh() -> BehaviorTree:
    """Dissolve the party on every account and send them to the guild hall.

    Mirrors HeroAI's "Leave & Travel to GH" command: every account, this client
    included, receives LeaveParty and then TravelToGuildHall through its own
    Messaging widget. That means the leader needs the widget enabled as well; if
    it is off the leave is never acknowledged and the step fails after
    `ZQUEST_MESSAGE_TIMEOUT_MS`.

    The leave is awaited so every client is out of the party before the guild
    hall travel is dispatched. The travel itself is fire-and-forget: a map load
    takes longer than a message ack, and this is the last step of the plan.
    """

    def _remote_leave(_node: BehaviorTree.Node) -> BehaviorTree:
        return RoutinesBT.Shared.SendAndWait(
            command=SharedCommandType.LeaveParty,
            include_self=True,
            refs_blackboard_key='zquest_leave_refs',
            timeout_ms=ZQUEST_MESSAGE_TIMEOUT_MS,
            poll_interval_ms=250,
            log=True,
        )

    def _remote_travel(_node: BehaviorTree.Node) -> BehaviorTree:
        return RoutinesBT.Shared.SendCommand(
            command=SharedCommandType.TravelToGuildHall,
            include_self=True,
            refs_blackboard_key='zquest_gh_refs',
            log=True,
        )

    return BT.Sequence(
        name='LeavePartyAndTravelGH',
        children=[
            BT.Subtree(name='RemoteLeaveParty', subtree_fn=_remote_leave),
            BT.Subtree(name='RemoteTravelGH', subtree_fn=_remote_travel),
        ],
    )


def _build_zquest_reward() -> BehaviorTree:
    """Claim the quest reward in the Great Temple of Balthazar.

    Runs after the run completed and resigned, so the party travels from the
    vanquish outpost to the temple and claims the reward there. The dialog is
    fanned out like the signpost one: every account walks to the reward NPC, and
    the step only ends once all of them finished.
    """
    return BT.Sequence(
        name='ZQuestReward',
        children=[
            _build_travel_to_map(GREAT_TEMPLE_MAP_ID, 'GreatTempleOfBalthazar'),
            _build_multibox_dialog(_REWARD_DIALOG),
            _build_leave_party_and_travel_gh(),
        ],
    )


def _party_plan_candidates() -> list[tuple[str, str]]:
    """(email, label) for every other account this client can reach.

    Same shared-memory source the summon and invite nodes use, so the tab can
    only offer accounts the run is actually able to invite.
    """
    sender = str(Player.GetAccountEmail() or '')
    candidates: list[tuple[str, str]] = []
    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception:
        return candidates
    for account in accounts:
        email = str(getattr(account, 'AccountEmail', '') or '')
        if not email or email == sender:
            continue
        name = str(
            getattr(account, 'CharacterName', '')
            or getattr(getattr(account, 'AgentData', None), 'CharacterName', '')
            or ''
        )
        candidates.append((email, f'{name} ({email})' if name else email))
    candidates.sort(key=lambda entry: entry[1].lower())
    return candidates


def _draw_party_plan_column(size: int, options: Sequence[tuple[str, str]]) -> bool:
    """One party-size column: a dropdown per slot. Returns True when it changed.

    An entry already held by another slot of this column is not offered again:
    one party cannot hold the same alt or the same hero twice, and filtering the
    list is where that rule belongs -- the stored side drops repeats too, so a
    hand-edited INI cannot smuggle one in.
    """
    slots = max(0, size - 1)
    plan = _party_plans.setdefault(size, [])
    while len(plan) < slots:
        plan.append('')
    del plan[slots:]

    changed = False
    # A duplicate that got past the stored side could not be shown at all (the
    # combo refuses to offer it), so it is dropped instead of left invisible.
    seen: set[str] = set()
    for index in range(slots):
        entry = plan[index]
        if not entry:
            continue
        if entry in seen:
            plan[index] = ''
            changed = True
        else:
            seen.add(entry)

    for slot in range(slots):
        selected = plan[slot]
        taken = {entry for index, entry in enumerate(plan) if index != slot and entry}
        values: list[str] = ['']
        labels: list[str] = ['(none)']
        for value, label in options:
            if value in taken:
                continue
            values.append(value)
            labels.append(label)
        index = values.index(selected) if selected in values else 0
        new_index = PyImGui.combo(f'Slot {slot + 1}##partyplan{size}_{slot}', index, labels)
        if new_index != index:
            plan[slot] = values[new_index]
            changed = True
    return changed


def _draw_party_config() -> None:
    """Party Config: which alts and heroes each party size brings.

    Three columns, one per size the vanquish outposts offer. The run reads the
    column matching the outpost it travelled to, at run time, so the same config
    works for 4, 6 and 8 player maps without switching anything. Heroes come from
    this account's own roster; an alt's heroes are never used.
    """
    candidates = _party_plan_candidates()
    options: list[tuple[str, str]] = list(candidates)
    for hero_id in HERO_CHOICES:
        options.append((f'{_HERO_PREFIX}{hero_id}', f'{_hero_label(hero_id)} (hero)'))

    # A stored account that is not visible right now (offline, or not sharing
    # memory yet) still belongs in the list: dropping it would leave the slot
    # showing "(none)" while the config keeps the value the run would use. Heroes
    # are always listed, so this only ever adds stale emails.
    known = {value for value, _label in options}
    for plan in _party_plans.values():
        for entry in plan:
            if entry and entry not in known:
                known.add(entry)
                options.append((entry, f'{entry} (not visible)'))

    PyImGui.text_wrapped('Pick which alts and heroes each party size brings. The size comes from the vanquish outpost the run travels to: 4, 6 or 8. Heroes are added by this account, not by the alts. A size with every slot on "(none)" keeps the previous behaviour and invites every account already on the map.')
    if not candidates:
        PyImGui.text_colored('No other accounts visible in shared memory: only heroes are offered.', (255, 190, 80, 255))
    PyImGui.separator()

    changed = False
    if PyImGui.begin_table(
        'pyquishai_party_plan',
        len(PARTY_SIZES),
        PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg | PyImGui.TableFlags.SizingStretchSame,
    ):
        for size in PARTY_SIZES:
            PyImGui.table_setup_column(f'{size} Man')
        PyImGui.table_next_row()
        for column, size in enumerate(PARTY_SIZES):
            PyImGui.table_set_column_index(column)
            PyImGui.text(f'{size} Man')
            changed = _draw_party_plan_column(size, options) or changed
        PyImGui.end_table()

    if changed:
        _save_settings()


def _draw_config() -> None:
    global region_index
    global map_index
    global loop_runs
    global automatic_zquest
    global forward_clear_radius
    global reverse_clear_radius_1
    global reverse_clear_radius_2
    global enemy_log_enabled
    global vanquish_queue

    tree = botting_tree
    locked = bool(tree is not None and tree.IsStarted())
    queued = bool(vanquish_queue)
    PyImGui.text('Region and map')
    PyImGui.separator()
    if locked:
        PyImGui.text_colored('Stop the bot before changing the map.', (255, 190, 80, 255))

    PyImGui.begin_disabled(locked)
    PyImGui.begin_disabled(queued)
    new_automatic = PyImGui.checkbox('Automatic ZQuest handling', automatic_zquest)
    if new_automatic != automatic_zquest:
        _set_automatic_zquest(new_automatic)
    PyImGui.end_disabled()

    PyImGui.begin_disabled(automatic_zquest)
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
    PyImGui.end_disabled()
    if automatic_zquest:
        PyImGui.text_colored(
            'The map is read from the quest the signpost gives the party.',
            (160, 160, 160, 255),
        )

    PyImGui.begin_disabled(automatic_zquest)
    if PyImGui.button('Add Map to queue'):
        if _add_map_to_queue(_selected_region(), _selected_map()):
            _queue_changed()
    PyImGui.same_line(0, 16)
    if PyImGui.button('Add Region to queue'):
        if _append_region_to_queue(_selected_region()):
            _queue_changed()
    PyImGui.same_line(0, 16)
    if PyImGui.button('Clear queue'):
        _clear_vanquish_queue()

    if vanquish_queue:
        PyImGui.text(f'Queued vanquishes: {len(vanquish_queue)}')
    for position in range(len(vanquish_queue)):
        region, map_name = vanquish_queue[position]
        PyImGui.text(f'{position + 1:>2}. {region} / {map_name}')
        PyImGui.same_line(0, 24)
        if PyImGui.button(f'Remove##queue{position}'):
            if _remove_map_from_queue(region, map_name):
                _queue_changed()
            break
    PyImGui.end_disabled()

    PyImGui.separator()
    PyImGui.begin_disabled(automatic_zquest)
    new_loop_runs = PyImGui.checkbox('Loop vanquish', loop_runs)
    if new_loop_runs != loop_runs:
        loop_runs = new_loop_runs
        _request_rebuild()
    PyImGui.end_disabled()

    new_enemy_log = PyImGui.checkbox('Write enemy log to a txt file', enemy_log_enabled)
    if new_enemy_log != enemy_log_enabled:
        enemy_log_enabled = new_enemy_log
        # Nothing in the plan depends on it: the log is sampled from the widget
        # loop, so there is no tree to rebuild.
        _save_settings()

    PyImGui.separator()
    PyImGui.text('Enemy sweep radius')
    new_forward = max(1200, min(10000, PyImGui.input_int('Forward pass', forward_clear_radius)))
    new_reverse_1 = max(1200, min(10000, PyImGui.input_int('Reverse pass 1', reverse_clear_radius_1)))
    new_reverse_2 = max(1200, min(10000, PyImGui.input_int('Reverse pass 2', reverse_clear_radius_2)))
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


def _apply_consumable_upkeep_change() -> None:
    """Re-push the upkeep service so toggles apply without a tree rebuild.

    `ConfigureUpkeep` replaces only the upkeep trees, so this is safe while the
    bot is running; the restock toggles take effect on the next run preparation.
    """
    if botting_tree is None:
        return
    _configure_upkeep(botting_tree)


def _draw_consumable_group(
    label: str,
    model_ids: tuple[int, ...],
    selected: set[int],
    activate: bool,
    restock: bool,
    on_change,
) -> tuple[bool, bool, set[int]]:
    """Draw one conset/pcon group: master toggles plus a per-item checklist.

    Returns the (possibly updated) activate flag, restock flag and selection so
    the caller can persist them and re-push the upkeep service.
    """
    new_selection = set(selected)

    # The collapsing header's identity is its label, so the volatile "n/m
    # selected" count must not live in the portion ImGui hashes. Everything
    # before "###" is display-only; the part after it is the stable identity.
    # Without this split the label changes on every toggle, which ImGui reads as
    # a brand-new item defaulting to closed -- collapsing the list on each click.
    if PyImGui.collapsing_header(
        f'{label} ({len(new_selection)}/{len(model_ids)} selected)###{label}_group_header'
    ):
        PyImGui.text_colored(
            'Only ticked items are used and restocked.' if activate else 'Group is off; selection is remembered.',
            (200, 200, 200, 255) if activate else (255, 190, 80, 255),
        )

        if PyImGui.button(f'Select all##{label}'):
            new_selection = set(model_ids)
            on_change()
        PyImGui.same_line(0.0, 6.0)
        if PyImGui.button(f'Select none##{label}'):
            new_selection = set()
            on_change()

        for model_id in model_ids:
            checked = model_id in new_selection
            new_checked = PyImGui.checkbox(f'{_display_name(model_id)}##{label}_{model_id}', checked)
            if new_checked != checked:
                if new_checked:
                    new_selection.add(model_id)
                else:
                    new_selection.discard(model_id)
                on_change()
            if model_id in PARTY_MORALE_MODEL_IDS:
                PyImGui.same_line(0.0, 6.0)
                PyImGui.text_colored(
                    '(party morale rule)',
                    (150, 190, 255, 255),
                )

    return activate, restock, new_selection


def _draw_consumables() -> None:
    global _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons
    global _restock_scroll_of_resurrection
    global _restock_multi_account
    global _keep_gold_on_accounts
    global _selected_conset, _selected_pcons

    def _persist() -> None:
        _save_settings()

    def _persist_and_apply() -> None:
        _save_settings()
        _apply_consumable_upkeep_change()

    PyImGui.text('Consumable Upkeep')
    PyImGui.separator()
    PyImGui.text_wrapped(
        'Upkeep consumes from bags. Restock pulls the item from storage into '
        'bags during the Prepare step, so run preparation needs enough free slots '
        'and a storage window the bot can reach.'
    )
    PyImGui.text_wrapped(
        'Each group has a master switch for whether the bot uses/restocks it at '
        'all, and a per-item checklist for which consumables are included.'
    )
    PyImGui.separator()

    PyImGui.text('ConSets')
    new_activate_conset = PyImGui.checkbox('Use Consets##group', _activate_conset)
    if new_activate_conset != _activate_conset:
        _activate_conset = new_activate_conset
        _persist_and_apply()
    PyImGui.same_line(0.0, 12.0)
    new_restock_conset = PyImGui.checkbox('Restock Consets from storage##group', _restock_conset)
    if new_restock_conset != _restock_conset:
        _restock_conset = new_restock_conset
        _persist()

    _, _, updated_conset = _draw_consumable_group(
        'Conset items',
        CONSET_MODEL_IDS,
        _selected_conset,
        _activate_conset,
        _restock_conset,
        _persist_and_apply,
    )
    if updated_conset != _selected_conset:
        _selected_conset = updated_conset

    PyImGui.separator()

    PyImGui.text('PCons')
    new_activate_pcons = PyImGui.checkbox('Use Pcons##group', _activate_pcons)
    if new_activate_pcons != _activate_pcons:
        _activate_pcons = new_activate_pcons
        _persist_and_apply()
    PyImGui.same_line(0.0, 12.0)
    new_restock_pcons = PyImGui.checkbox('Restock Pcons from storage##group', _restock_pcons)
    if new_restock_pcons != _restock_pcons:
        _restock_pcons = new_restock_pcons
        _persist()

    _, _, updated_pcons = _draw_consumable_group(
        'Pcon items',
        PCON_UPKEEPS,
        _selected_pcons,
        _activate_pcons,
        _restock_pcons,
        _persist_and_apply,
    )
    if updated_pcons != _selected_pcons:
        _selected_pcons = updated_pcons

    PyImGui.separator()

    PyImGui.text('Scroll Of Resurrection')
    new_restock_scroll_of_resurrection = PyImGui.checkbox('Restock Scroll Of Resurrection from storage##group', _restock_scroll_of_resurrection)
    if new_restock_scroll_of_resurrection != _restock_scroll_of_resurrection:
        _restock_scroll_of_resurrection = new_restock_scroll_of_resurrection
        _persist()

    PyImGui.separator()

    PyImGui.text('Multibox restock')
    new_restock_multi_account = PyImGui.checkbox('Also restock the other accounts##group', _restock_multi_account)
    if new_restock_multi_account != _restock_multi_account:
        _restock_multi_account = new_restock_multi_account
        _persist()
    PyImGui.text_wrapped(
        'The other accounts are restocked through the shared command bus, so the '
        'Messaging widget must be enabled on every client. Each group uses the '
        'same quantity as this account, but the bus cannot carry the per-item '
        'checklist: remote clients restock their whole conset or pcon group.'
    )

    PyImGui.separator()

    PyImGui.text('Gold')
    new_keep_gold_on_accounts = PyImGui.checkbox(
        f'Keep {KEEP_GOLD_AMOUNT} gold on every account##group',
        _keep_gold_on_accounts,
    )
    if new_keep_gold_on_accounts != _keep_gold_on_accounts:
        _keep_gold_on_accounts = new_keep_gold_on_accounts
        _persist()
    PyImGui.text_wrapped(
        'Runs during the Prepare step, right after the restock: character gold '
        'above the keep amount goes into storage, on this account and on the other '
        'accounts of the group through the shared command bus. Accounts below the '
        'keep amount are topped up from storage, so every client ends the step '
        'with the same amount.'
    )

    PyImGui.separator()
    active = _enabled_consumable_upkeeps()
    if active:
        PyImGui.text(f'Upkeep active for {len(active)} consumable model(s).')
    else:
        PyImGui.text_colored('Consumable upkeep is disabled.', (255, 190, 80, 255))

    scheduled = _consumable_restock_items()
    if scheduled:
        PyImGui.text(f'Restock list: {len(scheduled)} model(s) per run.')
    else:
        PyImGui.text('Restock list: empty.')


def _draw_help() -> None:
    PyImGui.text_wrapped('PyQuishAI rebuilt on BottingTree and BehaviorTree nodes only. No legacy FSM is used.')
    PyImGui.separator()
    PyImGui.text_wrapped('Select a map in Config, then start it from the Main tab.')
    PyImGui.text_wrapped('With Automatic ZQuest handling on, the region and map combos are disabled: the plan is built from the quest the signpost gives the party, resolved from its "Clear <area> ..." objective.')
    PyImGui.text_wrapped('Every route coordinate is a named planner step carrying the map it walks in: Point 1 (map 99), Point 2 (map 103), and so on, transit legs included.')
    PyImGui.text_wrapped('A failed movement or party-wipe recovery restarts the current point instead of the full route.')
    PyImGui.text_wrapped('Choose the first step in Navigation to restart from staging. Prepare leaves the party, travels to the vanquish outpost, rebuilds the group there, then restocks and exits.')
    PyImGui.text_wrapped('Form Party only runs with Automatic ZQuest handling on, as the preparation for taking the signpost quest: it disbands, gathers the other accounts onto the leader map and invites them back, and logs the shared-memory census first. It is skipped while Account Isolation is enabled.')
    PyImGui.text_wrapped('The quest dialogs wait for the other accounts to report the leader map and district before the order is sent, so no follower misses the quest because it was still loading.')
    PyImGui.text_wrapped('The bot performs the forward route, followed by up to two reverse sweeps if foes remain.')
    PyImGui.text_wrapped('Automatic ZQuest handling travels to Embark Beach, takes the vanquish quest from the signpost, reads the map out of it and claims the reward at the end. It is the only flow that takes the quest: a manual run and a queued run never do.')
    PyImGui.text_wrapped('The vanquish queue chains several maps in one plan: every entry repeats Prepare, route, sweeps and Complete with its resign. It and Automatic ZQuest handling exclude each other: turn the switch off to add maps.')
    PyImGui.text_wrapped('Looting is always on: a vanquish leaves drops along the whole route.')
    PyImGui.text_wrapped('Consumable upkeep is configured in the Consumables tab: consets and pcons are separated.')
    PyImGui.text_wrapped('Enable Restock to pull consumables from storage into bags during each Prepare step.')


def _format_time(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


def _draw_run_status() -> None:
    if vanquish_queue:
        # The combos do not drive a queued run, so listing a "selected" map here
        # would name a map the plan is not going to walk. The loop re-runs Form
        # Party, so the party clause has to follow the loop rather than the queue.
        party_clause = 'party re-formed each pass' if loop_runs else 'party formed once'
        PyImGui.text(f'Queue: {len(vanquish_queue)} vanquishes, {party_clause}')
    elif automatic_zquest and _auto_definition is None:
        PyImGui.text('Selected: (pending quest)')
    elif automatic_zquest:
        PyImGui.text(f'Selected: {_active_map_name()} (from quest)')
    else:
        PyImGui.text(f'Selected: {_selected_region()} / {_active_map_name()}')
    if last_load_error:
        PyImGui.text_colored(f'Load error: {last_load_error}', (255, 80, 80, 255))

    if Map.IsExplorable() and Map.IsVanquishable():
        killed = int(Map.GetFoesKilled() or 0)
        remaining = int(Map.GetFoesToKill() or 0)
        total = killed + remaining
        if total > 0:
            progress = 100.0 * killed / total
            PyImGui.text(f'Vanquish: {killed} / {total} ({progress:.1f}%)')
        else:
            PyImGui.text('Vanquish: initializing foe counter...')

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
    # Manual stop or a tree reset: the run ended without reaching completion, so
    # what it collected is still worth writing.
    _flush_enemy_log('stopped')


def main() -> None:
    global initialized
    global ini_key
    global last_load_error

    if not initialized:
        if not ini_key:
            ini_key = Settings(f'{INI_PATH}/{INI_FILENAME}', 'account').name
            if not ini_key:
                return
        _load_settings()
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

    _apply_pending_stop()
    _apply_pending_rebuild()
    tree = ensure_botting_tree()
    tree.tick()
    _sample_enemy_log(tree)
    _apply_pending_planner_swap()
    _reset_auto_resolution_on_stop(tree)
    _freeze_stopped_run(tree)
    tree.UI.draw_window(
        icon_path=TEXTURE,
        additional_ui=_draw_run_status,
        extra_tabs=[
            ('Config', _draw_config),
            ('Party Config', _draw_party_config),
            ('Consumables', _draw_consumables),
        ],
    )


if __name__ == '__main__':
    main()
