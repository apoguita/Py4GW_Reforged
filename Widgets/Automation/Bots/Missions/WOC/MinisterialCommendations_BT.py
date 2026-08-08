from __future__ import annotations

import time
from collections.abc import Callable

import PySystem

from Py4GWCoreLib import Agent
from Py4GWCoreLib import AgentArray
from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib import Map
from Py4GWCoreLib import Player
from Py4GWCoreLib import Routines
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
from Sources.ApoSource.ApoBottingLib import wrappers as BT


MODULE_NAME = 'Ministerial Commendations BT'
INI_PATH = 'Widgets/Automation/Bots/Farmers/Trophies/Ministerial Commendations BT'
INI_FILENAME = 'Ministerial_Commendations_BT.ini'

KAINENG_CENTER = 194
A_CHANCE_ENCOUNTER = 861
MISSION_DIALOG = 0x84

PLAYER_SKILLBAR = 'OgGlQlVp6smsJRg19RTKexTkL2XsDC'
MINISTERIAL_COMMENDATION = int(ModelID.Ministerial_Commendation.value)
BIRTHDAY_CUPCAKE = int(ModelID.Birthday_Cupcake.value)

MIKU_LEGACY_AGENT_ID = 58
MIKU_SEARCH_ANCHOR = (-6300.0, -5300.0)

HERO_VEKK = 1
HERO_NORGU = 2
HERO_RAZAH = 3
HERO_OGDEN = 4
HERO_XANDRA = 5
HERO_MASTER_OF_WHISPERS = 6
HERO_LIVIA = 7

HERO_SPEED_SUPPORT = HERO_OGDEN
HERO_PROT = HERO_XANDRA
HERO_BIP = HERO_MASTER_OF_WHISPERS
HERO_SOS = HERO_LIVIA

EXPECTED_HERO_IDS = (
    int(HeroType.Vekk.value),
    int(HeroType.Norgu.value),
    int(HeroType.Razah.value),
    int(HeroType.Ogden.value),
    int(HeroType.Xandra.value),
    int(HeroType.MasterOfWhispers.value),
    int(HeroType.Livia.value),
)

HERO_BUILDS = (
    (HERO_VEKK, 'Vekk', 'OgJTgYWizhWQO+GeDkjyZ5oDBA', (6, 7), 0),
    (HERO_NORGU, 'Norgu', 'OQpkAsBjwqizJY6lDMdDBZQe++C', (8,), 0),
    (HERO_RAZAH, 'Razah', 'OQpkAoB8gpa0LAC4KQeGJQGgAw9F', (8,), 0),
    (HERO_OGDEN, 'Ogden', 'Owkk0wPGkaaEDRNm/wNWGxKxdVDI', (4,), 1),
    (HERO_XANDRA, 'Xandra', 'OAqjAykqKOYzHX406BNJnCg7LA', (8,), 1),
    (HERO_MASTER_OF_WHISPERS, 'Master of Whispers', 'OAhjQoGYIP3hqqAYYK8kmTuxJA', (), 1),
    (HERO_LIVIA, 'Livia', 'OAhkYQgV4Kyz18bix8mVvJ3wUaC', (5,), 1),
)

STARTING_POSITIONS = (
    (HERO_VEKK, -6221.0, -5717.0),
    (HERO_NORGU, -6143.0, -4724.0),
    (HERO_RAZAH, -6262.0, -5479.0),
    (HERO_OGDEN, -5840.0, -4734.0),
    (HERO_XANDRA, -5748.0, -4284.0),
    (HERO_MASTER_OF_WHISPERS, -5757.0, -5007.0),
    (HERO_LIVIA, -6060.0, -5050.0),
)
PLAYER_HERO_SETUP_POSITION = (-6105.82, -5182.48)
PLAYER_TRAP_POSITION = (-6332.0, -5251.0)

RUN_TO_KILL_SPOT = [
    (-4199.0, -1475.0),
    (-4709.0, -609.0),
    (-3116.0, 650.0),
    (-2518.0, 631.0),
    (-2096.0, -1067.0),
    (-815.0, -1898.0),
    (-690.0, -3769.0),
    (-771.12, -3879.82),
]

_settings = Settings(f'{INI_PATH}/{INI_FILENAME}', 'account')
_settings_loaded = False
_hard_mode = True
_setup_party = True
_load_player_build = True
_use_cupcake = True

initialized = False
botting_tree: BottingTree | None = None
_team_builds_loaded = False

MISSION_RESTART_STEP = 'Enter A Chance Encounter'
MYSTIC_HEALING_STEPS = {
    'Prepare Stairs Defense',
    'Wait For Purity Ball',
    'Spike Ministry Of Purity',
    'Loot And Return',
}
MYSTIC_HEALING_HEROES = (
    (HERO_NORGU, 'Norgu'),
    (HERO_RAZAH, 'Razah'),
    (HERO_XANDRA, 'Xandra'),
)


def _log(message: str, message_type=PySystem.Console.MessageType.Info) -> None:
    PySystem.Console.Log(MODULE_NAME, message, message_type)


def _load_settings() -> None:
    global _settings_loaded, _hard_mode, _setup_party, _load_player_build, _use_cupcake
    if _settings_loaded:
        return
    _hard_mode = _settings.get_bool('Config', 'HardMode', True)
    _setup_party = _settings.get_bool('Config', 'SetupParty', True)
    _load_player_build = _settings.get_bool('Config', 'LoadPlayerBuild', True)
    _use_cupcake = _settings.get_bool('Config', 'UseBirthdayCupcake', True)
    _settings_loaded = True


def _save_settings() -> None:
    _settings.set('Config', 'HardMode', _hard_mode)
    _settings.set('Config', 'SetupParty', _setup_party)
    _settings.set('Config', 'LoadPlayerBuild', _load_player_build)
    _settings.set('Config', 'UseBirthdayCupcake', _use_cupcake)


def _draw_config() -> None:
    import PyImGui

    global _hard_mode, _setup_party, _load_player_build, _use_cupcake

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

    value = PyImGui.checkbox('Load the recommended Dervish build', _load_player_build)
    if value != _load_player_build:
        _load_player_build = value
        changed = True

    value = PyImGui.checkbox('Use Birthday Cupcake', _use_cupcake)
    if value != _use_cupcake:
        _use_cupcake = value
        changed = True

    if changed:
        _save_settings()

    PyImGui.separator()
    PyImGui.text_wrapped(
        'On the first run, the bot prepares the full party in Kaineng Center '
        'and loads every hero build automatically.'
    )
    PyImGui.text('Loaded hero order:')
    for line in (
        '1 Vekk - Air / traps (slots 6 and 7 locked)',
        '2 Norgu - Energy Surge (Mystic Healing manually controlled)',
        '3 Razah - Ineptitude (Mystic Healing manually controlled)',
        '4 Ogden - support (slot 4 locked)',
        '5 Xandra - Soul Twisting protection (Mystic Healing manually controlled)',
        '6 Master of Whispers - BiP support',
        '7 Livia - Signet of Spirits (slot 5 locked)',
    ):
        PyImGui.bullet_text(line)


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
            'Prepare Stairs Defense',
            'Wait For Purity Ball',
            'Spike Ministry Of Purity',
            'Loot And Return',
        }
        or step_name.startswith('Run To Kill Spot - Point ')
    )


def MissionRestartAnchorService() -> BehaviorTree:
    """Leave a failed mission and restart it from Kaineng Center."""

    state = {
        'returning_to_outpost': False,
        'last_return_ms': 0.0,
    }

    def _select_mission_restart(node: BehaviorTree.Node) -> None:
        node.blackboard['current_step_name'] = MISSION_RESTART_STEP
        node.blackboard['last_active_planner_step_name'] = MISSION_RESTART_STEP

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

        if in_mission and requested_step and requested_step != MISSION_RESTART_STEP:
            _log(
                f"Mission step '{requested_step}' failed; restarting from '{MISSION_RESTART_STEP}'.",
                PySystem.Console.MessageType.Warning,
            )
            node.blackboard['restart_step_name_request'] = MISSION_RESTART_STEP
            node.blackboard['PLANNER_STATUS'] = f'PLANNER: Restarting {MISSION_RESTART_STEP}'

        party_wiped = bool(Routines.Checks.Party.IsPartyWiped())
        party_defeated = bool(GLOBAL_CACHE.Party.IsPartyDefeated())
        player_dead = bool(Routines.Checks.Player.IsDead())
        mission_failed = bool(in_mission_instance and (player_dead or _mission_failed()))
        if in_mission_instance and (party_wiped or party_defeated or mission_failed):
            if not state['returning_to_outpost']:
                ActionQueueManager().ResetAllQueues()
                _log(
                    f'Mission failure detected (player_dead={player_dead}); '
                    'returning to Kaineng Center before '
                    f"restarting '{MISSION_RESTART_STEP}'.",
                    PySystem.Console.MessageType.Warning,
                )
            state['returning_to_outpost'] = True
            _select_mission_restart(node)

        if not state['returning_to_outpost']:
            return BehaviorTree.NodeState.RUNNING

        if Map.IsMapReady() and Map.IsOutpost():
            _select_mission_restart(node)
            node.blackboard['restart_step_name_request'] = MISSION_RESTART_STEP
            node.blackboard['PLANNER_STATUS'] = f'PLANNER: Restarting {MISSION_RESTART_STEP}'
            state['returning_to_outpost'] = False
            state['last_return_ms'] = 0.0
            _log(
                f"Outpost loaded; restarting '{MISSION_RESTART_STEP}'.",
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
    hero_agent_id = _hero_agent_id(hero_position)
    if hero_agent_id == 0:
        return False
    GLOBAL_CACHE.Party.Heroes.UseSkill(hero_agent_id, slot, int(target_id or 0))
    return True


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


def MysticHealingService() -> BehaviorTree:
    """Manually rotate the three locked Mystic Healing skills at the stairs."""

    state = {'last_cast_ms': 0.0, 'next_hero': 0}

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        current_step = str(node.blackboard.get('current_step_name', '') or '')
        if current_step not in MYSTIC_HEALING_STEPS:
            state['last_cast_ms'] = 0.0
            return BehaviorTree.NodeState.RUNNING

        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0 or Agent.IsDead(player_id) or Agent.GetHealth(player_id) >= 0.98:
            return BehaviorTree.NodeState.RUNNING

        now_ms = time.monotonic() * 1000.0
        if now_ms - state['last_cast_ms'] < 350.0:
            return BehaviorTree.NodeState.RUNNING

        hero_count = len(MYSTIC_HEALING_HEROES)
        start_index = int(state['next_hero']) % hero_count
        for offset in range(hero_count):
            index = (start_index + offset) % hero_count
            hero_position, hero_name = MYSTIC_HEALING_HEROES[index]
            hero_agent_id = _hero_agent_id(hero_position)
            if hero_agent_id <= 0 or Agent.IsDead(hero_agent_id):
                continue
            if not _hero_skill_ready(hero_position, 8):
                continue
            if _cast_hero_skill(hero_position, 8):
                state['last_cast_ms'] = now_ms
                state['next_hero'] = (index + 1) % hero_count
                _log(
                    f'{hero_name}: Mystic Healing manually triggered '
                    f'at {Agent.GetHealth(player_id):.0%} player health.'
                )
                break

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='Mystic Healing Service',
            action_fn=_tick,
            aftercast_ms=0,
        )
    )


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
        if _player_energy() > min_energy and _skill_adrenaline(8) >= min_adrenaline:
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


def _optional_commendation_loot(timeout_ms: int = 5_000) -> BehaviorTree:
    return BT.Selector(
        [
            BT.PickupGroundItemByModelID(
                MINISTERIAL_COMMENDATION,
                max_distance=Range.Compass.value,
                timeout_ms=timeout_ms,
                allow_unassigned=True,
                log=True,
            ),
            BT.Succeeder('No Ministerial Commendation Nearby'),
        ],
        name='Optional Ministerial Commendation Loot',
    )


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
            return BT.Succeeder('Expected Party And Builds Already Loaded')

        children: list[BehaviorTree | BehaviorTree.Node] = [
            BT.CreateParty(hero_ids=list(EXPECTED_HERO_IDS), log=True),
        ]
        for hero_position, hero_name, template, disabled_slots, behavior in HERO_BUILDS:
            children.extend(
                [
                    BT.LoadHeroSkillbar(hero_position, template, log=True),
                    _configure_hero_node(hero_position, hero_name, disabled_slots, behavior),
                    BT.Wait(500),
                ]
            )
        children.append(_mark_team_builds_loaded_node())
        return BT.Sequence(name='Load Ministerial Hero Team And Builds', children=children)

    return BT.Subtree('Set Up Ministerial Hero Team', _build)


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

        mode = 'Fight' if behavior == 0 else 'Guard'
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
        if primary != 'Dervish':
            return BT.Sequence(
                name='Keep Manually Configured Player Build',
                children=[
                    BT.LogMessage(
                        f'Primary profession is {primary or "unknown"}; keeping the current player build.',
                        MODULE_NAME,
                    )
                ],
            )
        return BT.LoadSkillbar(PLAYER_SKILLBAR, log=True)

    return BT.Subtree('Load Recommended Player Build', _build)


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
            _setup_party_node(),
            _load_player_build_node(),
            BT.SetHardMode(_hard_mode, log=True),
        ],
    )


def EnterAChanceEncounter() -> BehaviorTree:
    def _approach_if_needed(_node: BehaviorTree.Node) -> BehaviorTree:
        x, y = Player.GetXY()
        if -1400.0 < x < -550.0 and -2000.0 < y < -1100.0:
            return BT.Move((1474.0, -1197.0), pause_on_combat=False, log=True)
        return BT.Succeeder('Direct Mission NPC Approach')

    return BT.Sequence(
        name='Enter A Chance Encounter',
        map_id_or_name=KAINENG_CENTER,
        children=[
            BT.Subtree('Optional Kaineng Approach', _approach_if_needed),
            BT.MoveAndDialog(
                (2240.0, -1264.0),
                MISSION_DIALOG,
                pause_on_combat=False,
                multi_account=False,
                log=True,
            ),
            BT.WaitForMapLoad(A_CHANCE_ENCOUNTER, timeout_ms=45_000),
        ],
    )


def PlaceParty() -> BehaviorTree:
    children: list[BehaviorTree | BehaviorTree.Node] = [
        BT.IsCurrentMap(A_CHANCE_ENCOUNTER, log=True),
        BT.Move(PLAYER_HERO_SETUP_POSITION, pause_on_combat=False, tolerance=50.0, log=True),
    ]
    children.extend(BT.FlagHero(position, x, y) for position, x, y in STARTING_POSITIONS)
    children.append(BT.Wait(4_000))
    return BT.Sequence(name='Place Player And Heroes', children=children)


def PrepareFirstFight() -> BehaviorTree:
    children: list[BehaviorTree | BehaviorTree.Node] = [
        _hero_skill_node(HERO_VEKK, 5, name='Vekk: Serpents Quickness'),
        BT.Wait(500),
        _hero_skill_node(HERO_VEKK, 6, name='Vekk: Barbed Trap - First Setup'),
        BT.Wait(200),
        _hero_skill_node(HERO_VEKK, 7, name='Vekk: Flame Trap - First Setup'),
        BT.Move(PLAYER_TRAP_POSITION, pause_on_combat=False, tolerance=40.0, log=True),
        BT.Wait(1_500),
        _hero_skill_node(HERO_SOS, 1, name='SoS: Signet Of Spirits'),
        _hero_skill_node(HERO_PROT, 2, name='Prot: Union'),
        BT.FlagHero(HERO_VEKK, -6310.44, -5238.35),
        BT.FlagHero(HERO_PROT, -5530.0, -5250.0),
        BT.FlagHero(HERO_SOS, -5152.0, -4556.0),
        BT.Wait(3_000),
        BT.FlagHero(HERO_BIP, -5757.0, -5007.0),
        _hero_skill_node(HERO_SOS, 2, name='SoS: Pain'),
        _hero_skill_node(HERO_PROT, 3, name='Prot: Displacement'),
        BT.Wait(2_000),
        BT.FlagHero(HERO_PROT, -5622.0, -5072.0),
        BT.FlagHero(HERO_SOS, -5152.0, -4556.0),
        BT.Wait(2_000),
        _hero_skill_node(HERO_SOS, 5, name='SoS: Recuperation'),
        BT.Wait(2_000),
        _hero_skill_node(HERO_PROT, 4, name='Prot: Shelter'),
        BT.Wait(2_000),
        BT.FlagHero(HERO_SOS, -6060.0, -5050.0),
        _hero_skill_node(
            HERO_BIP,
            1,
            target=lambda: _hero_agent_id(HERO_SOS),
            name='BiP: Blood Is Power On Livia',
        ),
        BT.Wait(4_000),
        _hero_skill_node(HERO_PROT, 6, name='Prot: Earthbind'),
        _hero_skill_node(HERO_SOS, 3, target=_miku_or_player, name='SoS: Splinter Weapon On Miku'),
        BT.Wait(4_000),
        _hero_skill_node(HERO_PROT, 5, name='Prot: Armor Of Unfeeling'),
        _hero_skill_node(HERO_VEKK, 7, name='Vekk: Flame Trap - Second Setup'),
        BT.Wait(200),
        _hero_skill_node(HERO_VEKK, 6, name='Vekk: Barbed Trap - Second Setup'),
        BT.Wait(1_000),
    ]
    if _use_cupcake:
        children.append(BTItems.UseConsumable(BIRTHDAY_CUPCAKE, aftercast_ms=100))
    children.extend(
        [
            _player_skill_node(6, name='Player: Ebon Battle Standard Of Honor'),
            BT.Wait(100),
            BT.FlagHero(HERO_VEKK, -6342.0, -4941.0),
            _player_skill_node(7, name='Player: Hundred Blades'),
            _hero_skill_node(HERO_SOS, 3, target=Player.GetAgentID, name='SoS: Splinter Weapon On Player'),
            BT.WaitUntilOnCombat(range=500.0, timeout_ms=45_000),
            _hero_skill_node(HERO_SOS, 4, target=Player.GetAgentID, name='SoS: Ancestors Rage'),
            BT.Wait(200),
            _hero_skill_node(HERO_SOS, 3, target=Player.GetAgentID, name='SoS: Refresh Splinter Weapon'),
        ]
    )
    return BT.Sequence(name='Prepare The First Fight', children=children)


def InitialFight() -> BehaviorTree:
    clear_area = BT.WaitForClearEnemiesInArea(
        x=PLAYER_TRAP_POSITION[0],
        y=PLAYER_TRAP_POSITION[1],
        radius=8_000.0,
        allowed_alive_enemies=0,
        stable_clear_ms=2_000,
        log=True,
    )
    state = {'started_at': 0.0, 'last_action_ms': 0.0}

    def _reset() -> None:
        state.update(started_at=0.0, last_action_ms=0.0)
        clear_area.reset()

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now = time.monotonic()
        if state['started_at'] <= 0.0:
            state['started_at'] = now

        if _mission_failed():
            _reset()
            return BehaviorTree.NodeState.FAILURE

        elapsed = now - state['started_at']
        clear_area.blackboard = node.blackboard
        clear_state = clear_area.tick()
        if clear_state is BehaviorTree.NodeState.SUCCESS:
            _reset()
            return BehaviorTree.NodeState.SUCCESS
        if clear_state is BehaviorTree.NodeState.FAILURE:
            _reset()
            return BehaviorTree.NodeState.FAILURE
        if elapsed >= 80.0:
            _log(
                'Initial fight timed out while enemies were still alive; restarting the mission.',
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.FAILURE

        now_ms = now * 1000.0
        target_id = int(node.blackboard.get('wait_clear_area_target_id', 0) or 0)
        if target_id and now_ms - state['last_action_ms'] >= 1_300.0:
            for slot in (3, 7, 5):
                if _cast_player_skill(slot, target_id):
                    break
            state['last_action_ms'] = now_ms

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name='Fight Initial Group', action_fn=_tick, aftercast_ms=0))


def WaitForMikuAreaClear() -> BehaviorTree:
    def _area_is_clear() -> BehaviorTree.NodeState:
        if _mission_failed():
            return BehaviorTree.NodeState.FAILURE

        center_id = _miku_or_player()
        center = Agent.GetXY(center_id)
        if not _enemy_ids_near(center, Range.Spellcast.value):
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


def CastOgdenMakeHaste() -> BehaviorTree:
    """Bring Ogden into cast range, wait for slot 4, then hold for the cast."""

    node_name = 'Ogden: Make Haste'

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        player_x, player_y = Player.GetXY()

        def _ogden_ready() -> BehaviorTree.NodeState:
            if _mission_failed():
                return BehaviorTree.NodeState.FAILURE

            hero_agent_id = _hero_agent_id(HERO_SPEED_SUPPORT)
            if hero_agent_id <= 0 or Agent.IsDead(hero_agent_id):
                return BehaviorTree.NodeState.FAILURE

            in_range = _distance(Agent.GetXY(hero_agent_id), Player.GetXY()) < 1_350.0
            if in_range and _hero_skill_ready(HERO_SPEED_SUPPORT, 4):
                return BehaviorTree.NodeState.SUCCESS
            return BehaviorTree.NodeState.RUNNING

        wait_ready = BehaviorTree(
            BehaviorTree.WaitUntilNode(
                name='Wait For Ogden Make Haste',
                condition_fn=_ogden_ready,
                throttle_interval_ms=250,
                timeout_ms=10_000,
            )
        )
        cast = BT.Sequence(
            name='Position Ogden And Cast Make Haste',
            children=[
                BT.FlagHero(HERO_SPEED_SUPPORT, player_x, player_y),
                wait_ready,
                BT.LogMessage('Ogden is in range; casting Make Haste.', MODULE_NAME),
                _hero_skill_node(
                    HERO_SPEED_SUPPORT,
                    4,
                    target=Player.GetAgentID,
                    aftercast_ms=2_000,
                    name=node_name,
                ),
            ],
        )
        return BT.Selector(
            [
                cast,
                _continue_after_wait_timeout(
                    node_name,
                    'Ogden could not cast Make Haste within 10 seconds; continuing the run.',
                ),
            ],
            name=node_name,
        )

    return BT.Subtree(node_name, _build)


def FinishInitialFight() -> BehaviorTree:
    return BT.Sequence(
        name='Finish Initial Fight And Start Pull',
        children=[
            _optional_commendation_loot(),
            BT.UnflagAllHeroes(log=True),
            CastOgdenMakeHaste(),
            BT.FlagAllHeroes(-6699.0, -5645.0),
            _hero_skill_node(
                HERO_SPEED_SUPPORT,
                1,
                target=Player.GetAgentID,
                condition=lambda: Agent.IsCrippled(Player.GetAgentID()),
                name='Ogden: Crippled Player Support',
            ),
            _player_skill_node(
                3,
                condition=lambda: Agent.IsCrippled(Player.GetAgentID()),
                name='Player: I Am Unstoppable If Crippled',
            ),
            BT.Move((-4693.0, -3137.0), pause_on_combat=False, tolerance=150.0, log=True),
            WaitForMikuAreaClear(),
            _hero_skill_node(
                HERO_SOS,
                7,
                target=_miku_or_player,
                condition=lambda: Agent.IsCrippled(_miku_or_player()),
                name='Livia: Protective Was Kaolai For Crippled Miku',
            ),
            _hero_skill_node(
                HERO_BIP,
                6,
                target=_miku_or_player,
                condition=lambda: Agent.IsCrippled(_miku_or_player()),
                name='BiP: Mend Body And Soul On Crippled Miku',
            ),
            BT.FlagAllHeroes(-7075.0, -5685.0),
        ],
    )


def _run_point(
    point: tuple[float, float],
    label: str,
    *,
    tolerance: float = 125.0,
) -> BehaviorTree:
    return BT.Sequence(
        name=label,
        children=[
            BT.IsCurrentMap(A_CHANCE_ENCOUNTER, log=True),
            BT.Move(point, pause_on_combat=False, tolerance=tolerance, log=True, avoid_obstacles=False),
        ],
    )


def _defensive_ball_tick(state: dict[str, float], enemy_count: int) -> None:
    now_ms = time.monotonic() * 1000.0
    if now_ms - state.get('action_ms', 0.0) < 250.0:
        return

    player_id = int(Player.GetAgentID() or 0)
    health = Agent.GetHealth(player_id)
    adrenaline = _skill_adrenaline(8)
    casted = False

    if enemy_count > 3 and adrenaline < 130:
        casted = _cast_player_skill(5)
    if not casted and health < 0.90:
        casted = _cast_player_skill(3)
    if not casted and not _has_player_effect_for_slot(1):
        casted = _cast_player_skill(1)
    if not casted and health < 0.60 and not _has_player_effect_for_slot(4):
        casted = _cast_player_skill(4)
    if not casted and health < 0.45:
        casted = _cast_player_skill(2)

    if casted:
        state['action_ms'] = now_ms


def PrepareStairsDefense() -> BehaviorTree:
    return BT.Sequence(
        name='Prepare Stairs Defense',
        children=[
            BT.Wait(7_500),
            BT.FlagHeroesFromList(
                [HERO_VEKK, HERO_NORGU, HERO_RAZAH, HERO_OGDEN, HERO_MASTER_OF_WHISPERS],
                -6707.0,
                -5242.0,
            ),
            _hero_skill_node(HERO_SOS, 5, name='Livia: Recuperation At Stairs'),
            BT.Wait(2_000),
            BT.FlagHero(HERO_SOS, -4818.0, -7841.0),
            _hero_skill_node(HERO_PROT, 3, name='Xandra: Displacement At Stairs'),
            BT.Wait(2_000),
            BT.FlagHero(HERO_PROT, -4818.0, -7841.0),
        ],
    )


def WaitForPurityBall() -> BehaviorTree:
    state = {'action_ms': 0.0}

    def _ball_is_ready() -> BehaviorTree.NodeState:
        if _mission_failed():
            return BehaviorTree.NodeState.FAILURE

        enemies = _enemy_ids_near(Player.GetXY(), 200.0)
        if len(enemies) > 50 and _skill_adrenaline(8) >= 120:
            _log('Purity ball is ready.', PySystem.Console.MessageType.Success)
            return BehaviorTree.NodeState.SUCCESS

        _defensive_ball_tick(state, len(enemies))
        return BehaviorTree.NodeState.RUNNING

    wait_node = BehaviorTree(
        BehaviorTree.WaitUntilNode(
            name='Wait For Ministry Of Purity Ball',
            condition_fn=_ball_is_ready,
            throttle_interval_ms=100,
            timeout_ms=45_000,
        )
    )
    return BT.Selector(
        [
            wait_node,
            _continue_after_wait_timeout(
                'Wait For Ministry Of Purity Ball',
                'Purity ball wait timed out; starting the spike.',
            ),
        ],
        name='Wait For Ministry Of Purity Ball',
    )


def SpikeMinistryOfPurity() -> BehaviorTree:
    return BT.Sequence(
        name='Spike Ministry Of Purity',
        children=[
            _wait_for_player_resources(
                'Wait For Banner Resources',
                min_energy=13.0,
                min_adrenaline=120,
                timeout_ms=10_000,
            ),
            _player_skill_node(6, name='Ebon Battle Standard Of Honor'),
            _wait_for_player_resources(
                'Wait For Hundred Blades Resources',
                min_energy=5.0,
                min_adrenaline=120,
                timeout_ms=5_000,
            ),
            _player_skill_node(7, name='Hundred Blades'),
            _wait_for_player_resources(
                'Wait For Whirlwind Adrenaline',
                min_energy=-1.0,
                min_adrenaline=120,
                timeout_ms=5_000,
            ),
            _player_skill_node(
                8,
                target=lambda: _nearest_enemy(Player.GetXY(), 200.0),
                name='Whirlwind Attack',
            ),
            BT.Wait(3_000),
        ],
    )


def LootAndReturn() -> BehaviorTree:
    return BT.Sequence(
        name='Loot Commendations And Return',
        children=[
            _optional_commendation_loot(timeout_ms=10_000),
            BT.LootItems(distance=Range.Compass.value, timeout_ms=15_000),
            BT.Travel(target_map_id=KAINENG_CENTER, log=True),
        ],
    )


def _run_point_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []
    for index, point in enumerate(RUN_TO_KILL_SPOT, start=1):
        name = f'Run To Kill Spot - Point {index:02d}'
        tolerance = 15.0 if index == len(RUN_TO_KILL_SPOT) else 125.0
        steps.append(
            (
                name,
                lambda point=point, name=name, tolerance=tolerance: _run_point(
                    point,
                    name,
                    tolerance=tolerance,
                ),
            )
        )
    return steps


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ('Initialize Bot', InitializeBot),
        ('Prepare In Kaineng', PrepareInKaineng),
        ('Enter A Chance Encounter', EnterAChanceEncounter),
        ('Place Player And Heroes', PlaceParty),
        ('Prepare First Fight', PrepareFirstFight),
        ('Fight Initial Group', InitialFight),
        ('Finish Initial Fight', FinishInitialFight),
        *_run_point_steps(),
        ('Prepare Stairs Defense', PrepareStairsDefense),
        ('Wait For Purity Ball', WaitForPurityBall),
        ('Spike Ministry Of Purity', SpikeMinistryOfPurity),
        ('Loot And Return', LootAndReturn),
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
        looting_enabled=False,
        resurrection_scroll=False,
        auto_inventory_handler_enabled=True,
        enable_party_wipe_recovery=False,
        heroai_state_logging=False,
    )
    # SetMainRoutine adds the native wipe service after this anchor. This order
    # lets the anchor replace the current step before native recovery captures it.
    tree.AddServiceTree('MissionRestartAnchor', MissionRestartAnchorService)
    tree.AddServiceTree('MysticHealing', MysticHealingService)


def main() -> None:
    global initialized

    if not initialized:
        _load_settings()
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()
    tree.UI.draw_window(
        main_child_dimensions=(440, 390),
        extra_tabs=[('Config', _draw_config)],
    )


if __name__ == '__main__':
    main()