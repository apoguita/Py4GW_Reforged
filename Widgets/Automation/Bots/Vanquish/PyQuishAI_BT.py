from __future__ import annotations

import importlib
import math
import os
import random
import time
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
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
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Sources.ApoSource.ApoBottingLib import wrappers as BT


MODULE_NAME = 'PyQuishAI BT'
MODULE_ICON = 'Assets/Textures/Module_Icons/PyQuishAI.png'
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

MAP_ROOT = os.path.join(
    PySystem.Console.get_projects_path(),
    'Sources',
    'aC_Scripts',
    'PyQuishAI_maps',
)


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
auto_loot = True
take_zquest = True
forward_clear_radius = 3000
reverse_clear_radius_1 = 10000
reverse_clear_radius_2 = 10000

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


def _load_settings() -> None:
    global _settings_loaded
    global _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons
    global _restock_scroll_of_resurrection
    global _restock_multi_account
    global _keep_gold_on_accounts
    global _selected_conset, _selected_pcons

    if _settings_loaded:
        return
    _restock_conset = _settings.get_bool(_SETTINGS_SECTION, _KEY_RESTOCK_CONSET, True)
    _activate_conset = _settings.get_bool(_SETTINGS_SECTION, _KEY_ACTIVATE_CONSET, True)
    _restock_pcons = _settings.get_bool(_SETTINGS_SECTION, _KEY_RESTOCK_PCONS, True)
    _activate_pcons = _settings.get_bool(_SETTINGS_SECTION, _KEY_ACTIVATE_PCONS, True)
    _restock_scroll_of_resurrection = _settings.get_bool(_SETTINGS_SECTION, _KEY_RESTOCK_SCROLL_OF_RESURRECTION, True)
    _restock_multi_account = _settings.get_bool(_SETTINGS_SECTION, _KEY_RESTOCK_MULTI_ACCOUNT, True)
    _keep_gold_on_accounts = _settings.get_bool(_SETTINGS_SECTION, _KEY_KEEP_GOLD_ON_ACCOUNTS, True)

    stored_conset = _settings.get_str(_SETTINGS_SECTION, _KEY_SELECTED_CONSET, '')
    if stored_conset.strip():
        _selected_conset = _parse_model_id_list(stored_conset, CONSET_MODEL_IDS)

    stored_pcons = _settings.get_str(_SETTINGS_SECTION, _KEY_SELECTED_PCONS, '')
    if stored_pcons.strip():
        _selected_pcons = _parse_model_id_list(stored_pcons, PCON_UPKEEPS)

    _settings_loaded = True


def _save_settings() -> None:
    _settings.set(_SETTINGS_SECTION, _KEY_RESTOCK_CONSET, _restock_conset)
    _settings.set(_SETTINGS_SECTION, _KEY_ACTIVATE_CONSET, _activate_conset)
    _settings.set(_SETTINGS_SECTION, _KEY_RESTOCK_PCONS, _restock_pcons)
    _settings.set(_SETTINGS_SECTION, _KEY_ACTIVATE_PCONS, _activate_pcons)
    _settings.set(_SETTINGS_SECTION, _KEY_RESTOCK_SCROLL_OF_RESURRECTION, _restock_scroll_of_resurrection)
    _settings.set(_SETTINGS_SECTION, _KEY_RESTOCK_MULTI_ACCOUNT, _restock_multi_account)
    _settings.set(_SETTINGS_SECTION, _KEY_KEEP_GOLD_ON_ACCOUNTS, _keep_gold_on_accounts)
    _settings.set(_SETTINGS_SECTION, _KEY_SELECTED_CONSET, _serialize_model_id_list(_selected_conset))
    _settings.set(_SETTINGS_SECTION, _KEY_SELECTED_PCONS, _serialize_model_id_list(_selected_pcons))


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
    if not region or not map_name:
        raise ValueError(
            f'No PyQuish map found under {MAP_ROOT}. Select a region and a map in Config.'
        )
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


def _build_transit_leg(definition: VanquishDefinition, index: int) -> BehaviorTree:
    """Walk one intermediate map between the outpost exit and the vanquish map."""
    if index < 0 or index >= len(definition.transit_paths):
        return BT.Succeeder(name=f'NoTransitLeg:{index + 1}')

    transit_path = definition.transit_paths[index]
    next_map_id = definition.explorable_id
    if index + 1 < len(definition.transit_ids) and definition.transit_ids[index + 1] > 0:
        next_map_id = definition.transit_ids[index + 1]

    if _is_plain_path(transit_path) and next_map_id > 0:
        transit_move_path = _coordinate_path(transit_path, f'transit path {index + 1}')
        return BT.MoveAndExitMap(
            transit_move_path,
            target_map_id=next_map_id,
            timeout_ms=TRANSIT_TIMEOUT_MS,
            log=True,
        )

    children: list[BehaviorTree] = [
        _build_path_tree(
            definition,
            transit_path,
            name=f'TransitPath:{index + 1}',
            clear_radius=0.0,
            combat_path=False,
            skip_when_completed=False,
        )
    ]
    if next_map_id > 0:
        children.append(BT.WaitForMapLoad(map_id=next_map_id, timeout_ms=TRANSIT_TIMEOUT_MS))
    return BT.Sequence(name=f'TransitPath:{index + 1}', children=children)


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


def _build_run_preparation(definition: VanquishDefinition) -> BehaviorTree:
    children: list[BehaviorTree] = [
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
        BT.SetHardMode(hard_mode=True),
        ensure_botting_tree().Config.Aggressive(
            multi_account=True,
            auto_loot=auto_loot,
            resurrection_scroll=True,
        ),
    ]

    if _restock_conset or _restock_pcons or _restock_scroll_of_resurrection:
        children.append(_runtime_restock_node())
        if _restock_multi_account:
            children.append(_remote_restock_node())

    children.append(_keep_gold_node())
    children.append(_action('RecordRunStart', _mark_run_started))

    # The outpost exit belongs to the preparation; the intermediate travels are
    # their own named step and only exist when the map really has transit paths.
    if definition.outpost_path:
        children.append(_build_outpost_exit(definition))

    return BT.Sequence(
        name=f'Prepare:{definition.map_name}',
        children=children,
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
    children: list[BehaviorTree] = [_action('RecordRunCompletion', _mark_run_completed)]

    # The trip back is needed by the repeat loop, which starts from an outpost,
    # and by the staging flow, which ends in Embark Beach so the next run starts
    # from a staged position.
    if loop_runs or take_zquest:
        children.append(
            BT.Resign(
                wait_for_map_load=True,
                target_map_id=definition.outpost_id,
                multi_account=True,
                log=True,
            )
        )

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

    Skipped when `Account Isolation` is enabled: the shared-memory gate refuses
    messages between accounts that are not in the same party or isolation group,
    so with no party yet the summon and invite would be dropped (each refusal
    logs a warning and returns -1, so the step would silently do nothing) while
    the local `LeaveParty` still disbanded whatever was left.
    """

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        if _isolation_enabled():
            return BT.Succeeder('Form Party Skipped: Account Isolation')
        return BT.CreateParty(
            multibox_invite=True,
            timeout_ms=REMOTE_PARTY_TIMEOUT_MS,
            poll_interval_ms=100,
            log=True,
        )

    return BT.Subtree(name='Form Party', subtree_fn=_build)


def get_execution_steps(definition: VanquishDefinition) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        # Party first: staging and preparation both assume the group is formed.
        ('Form Party', _build_form_party),
    ]

    # Staging is its own named step so Navigation shows it and it can be
    # restarted on its own.
    if take_zquest:
        steps.append(
            (
                'Take ZQuest',
                lambda: _build_zquest_staging(),
            )
        )

    steps.append(
        (
            f'Prepare {definition.map_name}',
            lambda definition=definition: _build_run_preparation(definition),
        )
    )

    # Only the intermediate travels get their own step, one per transit path; the
    # outpost exit lives in Prepare, so maps with just an outpost path show none.
    for index in range(len(definition.transit_paths)):
        leg_number = index + 1
        steps.append(
            (
                f'Transit path {leg_number}',
                lambda definition=definition, index=index: _build_transit_leg(definition, index),
            )
        )

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


def _configure_upkeep(tree: BottingTree) -> None:
    """Push the run configuration and the consumable upkeep service.

    Called once at creation and again whenever a consumables toggle changes;
    `ConfigureUpkeep` only replaces the upkeep trees, so it does not disturb a
    running planner (the same runtime-reconfigure pattern the Reputation Farmer
    and Shards Of Orr BTs use).
    """
    tree.Config.ConfigureUpkeep(
        looting_enabled=auto_loot,
        resurrection_scroll=True,
        enable_party_wipe_recovery=True,
        heroai_state_logging=True,
        heroai_state_log_interval_ms=5000,
        consumable_upkeeps=_enabled_consumable_upkeeps(),
    )


def ensure_botting_tree() -> BottingTree:
    global botting_tree
    global last_load_error
    global loaded_region_index
    global loaded_map_index

    if botting_tree is None:
        definition = load_selected_definition()
        last_load_error = ''
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(definition),
            routine_name='PyQuishAISequence',
            repeat=loop_runs,
            reset=False,
            multi_account=True,
            auto_loot=auto_loot,
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


class MultiboxDialogSpec(NamedTuple):
    """Everything one multibox autodialog step needs."""

    button: int
    fallback_point: tuple[float, float]
    agent_key: str
    refs_key: str
    resolve: Callable[[], tuple[int, tuple[float, float]]]


_SIGNPOST_DIALOG = MultiboxDialogSpec(
    button=ZQUEST_DIALOG_BUTTON,
    fallback_point=VANQUISH_SIGNPOST,
    agent_key='zquest_signpost_agent_id',
    refs_key='zquest_dialog_refs',
    resolve=_resolve_vanquish_signpost,
)

_REWARD_DIALOG = MultiboxDialogSpec(
    button=ZQUEST_DIALOG_BUTTON,
    fallback_point=ZQUEST_REWARD_NPC,
    agent_key='zquest_reward_agent_id',
    refs_key='zquest_reward_refs',
    resolve=_resolve_reward_npc,
)


def _build_multibox_dialog(spec: MultiboxDialogSpec) -> BehaviorTree:
    """Resolve an agent, fan the dialog out and wait for every account.

    The command goes to every account, this client included, so one handler does
    all the work: it walks to the agent, interacts by id and presses the button.
    Nothing runs locally in parallel, which is why the leader behaves exactly
    like the rest. When the agent cannot be resolved the point-based node takes
    over and fans out the same dialog after walking there. Confirmation is a
    message-dispatch wait, so it only proves each handler finished, not that the
    game accepted the dialog.
    """

    def _resolve(node: BehaviorTree.Node) -> bool:
        agent_id = int(spec.resolve()[0] or 0)
        node.blackboard[spec.agent_key] = agent_id
        return agent_id > 0

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
            BT.Selector(
                name='FindDialogAgent',
                children=[
                    BehaviorTree(
                        BehaviorTree.WaitUntilNode(
                            name='WaitForDialogAgent',
                            condition_fn=_resolve,
                            throttle_interval_ms=250,
                            timeout_ms=ZQUEST_AGENT_WAIT_MS,
                        )
                    ),
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


def _build_zquest_staging() -> BehaviorTree:
    """Travel to Embark Beach and take the vanquish quest from the signpost.

    Runs before Prepare travels to the vanquish outpost. The step is only
    included when `take_zquest` is on, and the UI keeps that toggle off while the
    repeat loop is enabled.
    """
    return BT.Sequence(
        name='TakeZQuest',
        children=[
            _build_travel_to_map(EMBARK_BEACH_MAP_ID, 'EmbarkBeach'),
            _build_multibox_dialog(_SIGNPOST_DIALOG),
        ],
    )


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


def _draw_config() -> None:
    global region_index
    global map_index
    global loop_runs
    global auto_loot
    global take_zquest
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
    new_loop_runs = PyImGui.checkbox('Loop vanquish', loop_runs)
    if new_loop_runs != loop_runs:
        loop_runs = new_loop_runs
        if loop_runs:
            # A repeated full pass starts from the first step again, so staging
            # would run on every cycle. Keeping both on makes no sense, and the
            # pair is resolved here instead of guessing from the map at runtime.
            take_zquest = False
        _request_rebuild()

    new_auto_loot = PyImGui.checkbox('Automatic looting', auto_loot)
    if new_auto_loot != auto_loot:
        auto_loot = new_auto_loot
        _request_rebuild()

    PyImGui.begin_disabled(loop_runs)
    new_take_zquest = PyImGui.checkbox('Take ZQuest', take_zquest)
    if new_take_zquest != take_zquest:
        take_zquest = new_take_zquest
        _request_rebuild()
    PyImGui.end_disabled()
    if loop_runs:
        PyImGui.text_colored(
            'Take ZQuest is off while Loop vanquish is enabled.',
            (160, 160, 160, 255),
        )

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
    PyImGui.text_wrapped('Every route coordinate is a named planner step: Point 1, Point 2, and so on.')
    PyImGui.text_wrapped('A failed movement or party-wipe recovery restarts the current point instead of the full route.')
    PyImGui.text_wrapped('Choose the first step in Navigation to restart from staging; Prepare starts from the outpost.')
    PyImGui.text_wrapped('Form Party disbands, summons the other accounts to the leader map and invites them back before every run; it is skipped while Account Isolation is enabled.')
    PyImGui.text_wrapped('The bot performs the forward route, followed by up to two reverse sweeps if foes remain.')
    PyImGui.text_wrapped('Take ZQuest travels to Embark Beach and takes the vanquish quest from the signpost before each run.')
    PyImGui.text_wrapped('Consumable upkeep is configured in the Consumables tab: consets and pcons are separated.')
    PyImGui.text_wrapped('Enable Restock to pull consumables from storage into bags during each Prepare step.')


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
    _freeze_stopped_run(tree)
    tree.UI.draw_window(
        icon_path=TEXTURE,
        additional_ui=_draw_run_status,
        extra_tabs=[
            ('Config', _draw_config),
            ('Consumables', _draw_consumables),
        ],
    )


if __name__ == '__main__':
    main()
