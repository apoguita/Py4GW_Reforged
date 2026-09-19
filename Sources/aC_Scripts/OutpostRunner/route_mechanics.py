from __future__ import annotations

import math
import time
from typing import Any
from typing import Generator

from Py4GWCoreLib import Agent
from Py4GWCoreLib import ConsoleLog
from Py4GWCoreLib import Effects
from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib import Map
from Py4GWCoreLib import Party
from Py4GWCoreLib import Player
from Py4GWCoreLib import PySystem
from Py4GWCoreLib import Routines
from Py4GWCoreLib import SkillBar
from Py4GWCoreLib.routines_src.reliable_interaction import ApproachSpec
from Py4GWCoreLib.routines_src.reliable_interaction import DialogSpec
from Py4GWCoreLib.routines_src.reliable_interaction import InteractionProfile
from Py4GWCoreLib.routines_src.reliable_interaction import InteractionSpec
from Py4GWCoreLib.routines_src.reliable_interaction import PostconditionKind
from Py4GWCoreLib.routines_src.reliable_interaction import PostconditionSpec
from Py4GWCoreLib.routines_src.reliable_interaction import Py4GWInteractionRuntime
from Py4GWCoreLib.routines_src.reliable_interaction import ReliableInteractionController
from Py4GWCoreLib.routines_src.reliable_interaction import RetryPolicy
from Py4GWCoreLib.routines_src.reliable_interaction import TargetKind
from Py4GWCoreLib.routines_src.reliable_interaction import TargetSpec
from Py4GWCoreLib.routines_src.reliable_interaction import run_coroutine_adapter


JUNUNDU_STRIKE_SKILL_ID = 1439
LEAVE_JUNUNDU_SKILL_ID = 1443
PORTAL_EXTENSION_DISTANCE = 450.0


def _xy(data: dict[str, Any], key: str) -> tuple[float, float]:
    value = data[key]
    return float(value[0]), float(value[1])


def segment_steps(segment: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Return ordered mechanic-aware steps, preserving legacy path-only routes."""

    declared = segment.get('steps')
    if isinstance(declared, (list, tuple)):
        return tuple(dict(step) for step in declared)
    path = list(segment.get('path', []))
    return ({'type': 'path', 'path': path},) if path else ()


def extended_portal_path(
    points: list[tuple[float, float]],
    extension_distance: float = PORTAL_EXTENSION_DISTANCE,
    approach_origin: tuple[float, float] | None = None,
) -> list[tuple[float, float]]:
    """Add a forward point beyond a captured portal edge."""

    route = [(float(x), float(y)) for x, y in points]
    if not route:
        return route
    if len(route) >= 2:
        previous, endpoint = route[-2], route[-1]
    elif approach_origin is not None:
        previous = (float(approach_origin[0]), float(approach_origin[1]))
        endpoint = route[-1]
    else:
        return route
    dx = endpoint[0] - previous[0]
    dy = endpoint[1] - previous[1]
    length = math.hypot(dx, dy)
    if length <= 1.0:
        return route
    scale = float(extension_distance) / length
    return [
        *route,
        (endpoint[0] + dx * scale, endpoint[1] + dy * scale),
    ]


def register_outpost_departure(
    bot: Any,
    points: list[tuple[float, float]],
    target_map_id: int,
    step_name: str,
) -> None:
    """Register an outpost exit whose heading is resolved when the state runs."""

    def _leave_outpost() -> Generator[Any, Any, None]:
        portal_path = extended_portal_path(points, approach_origin=Player.GetXY())
        yield from bot.Move._coro_follow_path_and_exit_map(
            portal_path,
            target_map_id=target_map_id,
            step_name=step_name,
        )

    bot.States.AddCustomState(_leave_outpost, step_name)


def register_botting_segment(
    bot: Any,
    route_name: str,
    segment_index: int,
    segment: dict[str, Any],
    target_map_id: int = 0,
    resume_key_prefix: str = '',
) -> bool:
    """Register one shared route segment and report whether it owns map travel."""

    steps = segment_steps(segment)
    owns_map_travel = False
    for step_index, step in enumerate(steps, start=1):
        step_type = str(step.get('type', '')).strip().lower()
        label = str(step.get('name') or f'{route_name} segment {segment_index + 1} step {step_index}')
        resume_key = (
            f'{resume_key_prefix}:segment:{segment_index}:step:{step_index}'
            if resume_key_prefix
            else None
        )
        if step_type == 'path':
            points = list(step.get('path', []))
            if points:
                if target_map_id and step_index == len(steps):
                    portal_path = (
                        [*points, _xy(segment, 'portal_exit_xy')]
                        if 'portal_exit_xy' in segment
                        else extended_portal_path(points)
                    )
                    exit_kwargs = {
                        'target_map_id': target_map_id,
                        'step_name': label,
                    }
                    if resume_key is not None:
                        exit_kwargs['resume_key'] = resume_key
                    bot.Move.FollowPathAndExitMap(portal_path, **exit_kwargs)
                    owns_map_travel = True
                else:
                    path_kwargs = {'step_name': label}
                    if resume_key is not None:
                        path_kwargs['resume_key'] = resume_key
                    bot.Move.FollowAutoPath(points, **path_kwargs)
            continue
        if step_type == 'direct_path':
            points = list(step.get('path', []))
            if points:
                bot.Move.FollowPath(points, step_name=label)
            continue
        if step_type not in {
            'blessing',
            'enter_junundu',
            'leave_junundu',
            'npc_dialog_sequence',
            'verify_human_form',
        }:
            raise ValueError(f'Unsupported OutpostRunner route step type: {step_type!r}')
        bot.States.AddCustomState(
            lambda data=dict(step), owner=bot: _run_required_action(owner, data),
            label,
        )
    return owns_map_travel


def _hero_slot_skill(hero_position: int, slot: int) -> int | None:
    try:
        bar = list(GLOBAL_CACHE.SkillBar.GetHeroSkillbar(hero_position) or [])
        if len(bar) < slot:
            return None
        skill = bar[slot - 1]
        return int(getattr(getattr(skill, 'id', None), 'id', 0) or 0)
    except Exception:
        return None


def _expected_hero_count() -> int:
    heroes = list(Party.GetHeroes() or [])
    try:
        declared_count = int(Party.GetHeroCount() or 0)
    except Exception:
        declared_count = 0
    return max(declared_count, len(heroes))


def _party_slot_one(
    expected_hero_count: int | None = None,
) -> tuple[int | None, tuple[int | None, ...]]:
    try:
        player_skill = int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(1) or 0)
    except Exception:
        player_skill = None
    heroes = list(Party.GetHeroes() or [])
    required_count = (
        _expected_hero_count()
        if expected_hero_count is None
        else max(0, int(expected_hero_count))
    )
    if len(heroes) != required_count:
        return player_skill, tuple(None for _ in range(required_count))
    hero_skills = tuple(
        _hero_slot_skill(position, 1)
        for position, _hero in enumerate(heroes, start=1)
    )
    return player_skill, hero_skills


def full_hero_party_in_junundu(expected_hero_count: int | None = None) -> bool:
    player_skill, hero_skills = _party_slot_one(expected_hero_count)
    return bool(
        player_skill == JUNUNDU_STRIKE_SKILL_ID
        and all(skill == JUNUNDU_STRIKE_SKILL_ID for skill in hero_skills)
    )


def full_hero_party_in_human_form(expected_hero_count: int | None = None) -> bool:
    player_skill, hero_skills = _party_slot_one(expected_hero_count)
    observed = (player_skill,) + hero_skills
    return bool(
        all(skill is not None for skill in observed)
        and all(skill != JUNUNDU_STRIKE_SKILL_ID for skill in observed)
    )


def _required_heroes_close(
    radius: float = 700.0,
    center_xy: tuple[float, float] | None = None,
    expected_hero_count: int | None = None,
) -> bool:
    center = center_xy if center_xy is not None else Player.GetXY()
    heroes = list(Party.GetHeroes() or [])
    if expected_hero_count is not None and len(heroes) != expected_hero_count:
        return False
    for hero in heroes:
        agent_id = int(getattr(hero, 'agent_id', 0) or 0)
        if (
            agent_id <= 0
            or not Agent.IsValid(agent_id)
            or Agent.IsDead(agent_id)
            or math.dist(center, Agent.GetXY(agent_id)) > radius
        ):
            return False
    return True


class _RouteInteractionRuntime(Py4GWInteractionRuntime):
    def __init__(self, bot: Any, verify: Any, action_name: str):
        self.bot = bot
        self.action_name = action_name
        self.hero_ai_status = bot.config.upkeep.hero_ai.is_active()
        self.hero_ai_pause_status = bool(
            hasattr(bot.config.upkeep, 'hero_ai_paused')
            and bot.config.upkeep.hero_ai_paused.is_active()
        )
        super().__init__(
            pause_automation=self._pause,
            restore_automation=self._restore,
            verify=lambda _postcondition: bool(verify()),
            diagnostic_sink=self._record,
        )

    def _pause(self) -> None:
        if hasattr(self.bot.config.upkeep, 'hero_ai_paused'):
            self.bot.config.upkeep.hero_ai_paused.set_now('active', True)
        else:
            self.bot.config.upkeep.hero_ai.set_now('active', False)

    def _restore(self) -> None:
        if hasattr(self.bot.config.upkeep, 'hero_ai_paused'):
            self.bot.config.upkeep.hero_ai_paused.set_now('active', self.hero_ai_pause_status)
        self.bot.config.upkeep.hero_ai.set_now('active', self.hero_ai_status)

    def _record(self, event: dict[str, Any]) -> None:
        event_name = str(event.get('event', 'event'))
        if event_name in {
            'attempt_failed',
            'dialog_buttons_populated',
            'visible_button_clicked',
            'postcondition_verified',
            'result',
        }:
            ConsoleLog(
                'Outpost Route Mechanics',
                f'[{self.action_name}] {event_name}: {event}',
                PySystem.Console.MessageType.Info,
            )


def _blessing_active(effect_ids: tuple[int, ...]) -> bool:
    player_id = int(Player.GetAgentID() or 0)
    return player_id > 0 and any(Effects.HasEffect(player_id, effect_id) for effect_id in effect_ids)


def _take_blessing(bot: Any, data: dict[str, Any]) -> Generator[Any, Any, bool]:
    name = str(data['name'])
    effect_ids = tuple(int(value) for value in data['effect_ids'])
    target_xy = _xy(data, 'target_xy')
    approach_xy = _xy(data, 'player_approach_xy')
    runtime = _RouteInteractionRuntime(bot, lambda: _blessing_active(effect_ids), name)
    spec = InteractionSpec(
        name=name,
        profile=InteractionProfile.VISIBLE_CHOICE,
        target=TargetSpec(
            kind=TargetKind.NPC,
            model_id=int(data.get('model_id', 0)),
            name_contains=str(data.get('target_name', '')),
            expected_xy=target_xy,
            search_radius=float(data.get('search_radius', 350.0)),
        ),
        approach=ApproachSpec(
            player_approach_xy=approach_xy,
            tolerance=100.0,
            target_tolerance=100.0,
            timeout_ms=15_000,
        ),
        dialog=DialogSpec(
            visible_button=int(data.get('visible_button', 1)),
            response_timeout_ms=8_000,
            close_dialog_after_success=True,
            allow_no_choice_success=True,
            no_choice_settle_ms=1_000,
        ),
        postcondition=PostconditionSpec(
            PostconditionKind.EFFECT_PRESENT,
            effect_ids,
            f'{name} bounty effect is active',
        ),
        retry=RetryPolicy(
            max_attempts=3,
            poll_ms=100,
            verify_timeout_ms=5_000,
            retry_delay_ms=750,
            pause_settle_ms=350,
        ),
        allow_preexisting_postcondition=True,
        source_capture_ids=(str(data.get('capture_id', name)),),
    )
    return bool((yield from run_coroutine_adapter(ReliableInteractionController(spec, runtime), Routines.Yield.wait)))


def _mount_attempt(
    bot: Any,
    data: dict[str, Any],
    expected_hero_count: int | None = None,
) -> Generator[Any, Any, bool]:
    name = str(data['name'])
    target_xy = _xy(data, 'target_xy')
    approach_xy = _xy(data, 'player_approach_xy')
    runtime = _RouteInteractionRuntime(
        bot,
        lambda: full_hero_party_in_junundu(expected_hero_count),
        name,
    )
    spec = InteractionSpec(
        name=name,
        profile=InteractionProfile.GADGET,
        target=TargetSpec(
            kind=TargetKind.GADGET,
            name_contains='Wurm Spoor',
            expected_xy=target_xy,
            search_radius=float(data.get('search_radius', 1_500.0)),
        ),
        approach=ApproachSpec(
            player_approach_xy=approach_xy,
            tolerance=float(data.get('approach_tolerance', 120.0)),
            target_tolerance=float(data.get('target_tolerance', 220.0)),
            timeout_ms=15_000,
        ),
        postcondition=PostconditionSpec(
            PostconditionKind.CUSTOM,
            'full_hero_party_in_junundu',
            'Junundu Strike is in player and every hero slot 1',
        ),
        retry=RetryPolicy(
            max_attempts=1,
            poll_ms=100,
            verify_timeout_ms=8_000,
            retry_delay_ms=750,
            pause_settle_ms=350,
        ),
        allow_preexisting_postcondition=True,
        source_capture_ids=(str(data.get('capture_id', name)),),
    )
    return bool((yield from run_coroutine_adapter(ReliableInteractionController(spec, runtime), Routines.Yield.wait)))


def _npc_dialog_sequence(bot: Any, data: dict[str, Any]) -> Generator[Any, Any, bool]:
    name = str(data['name'])
    target_xy = _xy(data, 'target_xy')
    approach_xy = _xy(data, 'player_approach_xy')
    target_map_id = int(data['target_map_id'])
    runtime = _RouteInteractionRuntime(bot, lambda: int(Map.GetMapID()) == target_map_id, name)
    spec = InteractionSpec(
        name=name,
        profile=InteractionProfile.QUEST_CONVERSATION,
        target=TargetSpec(
            kind=TargetKind.NPC,
            model_id=int(data.get('model_id', 0)),
            name_contains=str(data.get('target_name', '')),
            expected_xy=target_xy,
            search_radius=float(data.get('search_radius', 350.0)),
        ),
        approach=ApproachSpec(
            player_approach_xy=approach_xy,
            tolerance=100.0,
            target_tolerance=120.0,
            timeout_ms=15_000,
        ),
        dialog=DialogSpec(
            visible_button_labels=tuple(str(label) for label in data['visible_button_labels']),
            visible_step_delay_ms=500,
            response_timeout_ms=8_000,
            close_dialog_after_success=False,
        ),
        postcondition=PostconditionSpec(
            PostconditionKind.MAP_CHANGED,
            target_map_id,
            f'{name} completed and map {target_map_id} loaded',
        ),
        retry=RetryPolicy(
            max_attempts=4,
            poll_ms=100,
            verify_timeout_ms=90_000,
            retry_delay_ms=750,
            pause_settle_ms=350,
        ),
        allow_preexisting_postcondition=True,
        source_capture_ids=tuple(str(value) for value in data.get('capture_ids', ())),
    )
    return bool((yield from run_coroutine_adapter(ReliableInteractionController(spec, runtime), Routines.Yield.wait)))


def _wait_until(predicate: Any, timeout_s: float, poll_ms: int = 200) -> Generator[Any, Any, bool]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        yield from Routines.Yield.wait(poll_ms)
    return bool(predicate())


def _leave_junundu(
    expected_hero_count: int | None = None,
) -> Generator[Any, Any, bool]:
    if full_hero_party_in_human_form(expected_hero_count):
        return True
    # Follow the same slot-8 Leave Junundu boundary used by Gate of
    # Desolation, but drive every transformed party member and retry the
    # command. A single request can be dropped while the preceding path is
    # still settling or combat is finishing.
    for _attempt in range(15):
        player_skill, hero_skills = _party_slot_one(expected_hero_count)
        if full_hero_party_in_human_form(expected_hero_count):
            return True
        try:
            for hero_position, hero_skill in enumerate(hero_skills, start=1):
                if (
                    hero_skill == JUNUNDU_STRIKE_SKILL_ID
                    and _hero_slot_skill(hero_position, 8) == LEAVE_JUNUNDU_SKILL_ID
                ):
                    SkillBar.HeroUseSkill(0, 8, hero_position)
            if (
                player_skill == JUNUNDU_STRIKE_SKILL_ID
                and int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(8) or 0)
                == LEAVE_JUNUNDU_SKILL_ID
            ):
                SkillBar.UseSkillTargetless(8)
        except Exception as error:
            ConsoleLog(
                'Outpost Route Mechanics',
                f'[Leave Junundu] command error: {type(error).__name__}: {error}',
                PySystem.Console.MessageType.Error,
            )
        yield from Routines.Yield.wait(1_000)

    player_skill, hero_skills = _party_slot_one(expected_hero_count)
    ConsoleLog(
        'Outpost Route Mechanics',
        '[Leave Junundu] party did not return to human form after retries; '
        f'slot-1 snapshot was player={player_skill}, heroes={hero_skills}.',
        PySystem.Console.MessageType.Error,
    )
    return full_hero_party_in_human_form(expected_hero_count)


def _enter_junundu(bot: Any, data: dict[str, Any]) -> Generator[Any, Any, bool]:
    expected_hero_count = _expected_hero_count()
    if full_hero_party_in_junundu(expected_hero_count):
        return True
    regroup_xy = (
        _xy(data, 'party_regroup_xy')
        if 'party_regroup_xy' in data
        else _xy(data, 'target_xy')
    )
    party_radius = float(data.get('party_regroup_radius', 300.0))
    settle_ms = max(0, int(data.get('party_regroup_settle_ms', 0)))
    mount_attempts = max(1, int(data.get('mount_attempts', 2)))

    def _heroes_regrouped() -> bool:
        return _required_heroes_close(
            party_radius,
            regroup_xy,
            expected_hero_count,
        )

    def _regroup() -> Generator[Any, Any, bool]:
        if not (yield from _wait_until(_heroes_regrouped, 45.0)):
            return False
        if settle_ms <= 0:
            return True
        yield from Routines.Yield.wait(settle_ms)
        if _heroes_regrouped():
            return True
        return bool((yield from _wait_until(_heroes_regrouped, 15.0)))

    Party.Heroes.FlagAllHeroes(*regroup_xy)
    try:
        for attempt in range(1, mount_attempts + 1):
            if not (yield from _regroup()):
                return False
            if (yield from _mount_attempt(bot, data, expected_hero_count)):
                return True

            player_skill, hero_skills = _party_slot_one(expected_hero_count)
            ConsoleLog(
                'Outpost Route Mechanics',
                f'[{data.get("name", "Enter Junundu")}] mount attempt '
                f'{attempt}/{mount_attempts} left a partial party; slot-1 snapshot '
                f'was player={player_skill}, heroes={hero_skills}.',
                PySystem.Console.MessageType.Error,
            )
            if attempt >= mount_attempts:
                return False
            if not (yield from _leave_junundu(expected_hero_count)):
                return False
        return False
    finally:
        Party.Heroes.UnflagAllHeroes()


def _run_required_action(bot: Any, data: dict[str, Any]) -> Generator[Any, Any, bool]:
    action_type = str(data.get('type', '')).strip().lower()
    name = str(data.get('name', action_type))
    try:
        if action_type == 'blessing':
            success = yield from _take_blessing(bot, data)
        elif action_type == 'enter_junundu':
            success = yield from _enter_junundu(bot, data)
        elif action_type == 'npc_dialog_sequence':
            success = yield from _npc_dialog_sequence(bot, data)
        elif action_type == 'leave_junundu':
            success = yield from _leave_junundu()
        elif action_type == 'verify_human_form':
            success = yield from _wait_until(full_hero_party_in_human_form, float(data.get('timeout_s', 60.0)))
        else:
            success = False
    except Exception as error:
        ConsoleLog(
            'Outpost Route Mechanics',
            f'[{name}] {type(error).__name__}: {error}',
            PySystem.Console.MessageType.Error,
        )
        success = False
    if not success:
        ConsoleLog(
            'Outpost Route Mechanics',
            f'[{name}] required route mechanic failed; stopping the bot.',
            PySystem.Console.MessageType.Error,
        )
        bot.Stop()
    return bool(success)
