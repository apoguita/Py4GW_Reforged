from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

import PyImGui
from Py4GWCoreLib import Agent
from Py4GWCoreLib import Botting
from Py4GWCoreLib import ConsoleLog
from Py4GWCoreLib import FSM
from Py4GWCoreLib import Map
from Py4GWCoreLib import Player
from Py4GWCoreLib import PySystem
from Py4GWCoreLib import Routines
from Sources.aC_Scripts.OutpostRunner.map_loader import get_regions
from Sources.aC_Scripts.OutpostRunner.map_loader import get_runs
from Sources.aC_Scripts.OutpostRunner.map_loader import load_map_data
from Sources.aC_Scripts.OutpostRunner import route_mechanics as _route_mechanics

_route_mechanics = importlib.reload(_route_mechanics)
extended_portal_path = _route_mechanics.extended_portal_path
register_outpost_departure = _route_mechanics.register_outpost_departure
register_botting_segment = _route_mechanics.register_botting_segment

BOT_NAME = 'Outpost Fighter'
MODULE_NAME = BOT_NAME

WIDGETS_TO_ENABLE: tuple[str, ...] = (
    'HeroAI',
)

bot = Botting(
    bot_name=BOT_NAME,
    config_halt_on_death=False,
    config_stop_on_party_wipe=True,
    config_pause_on_danger=True,
    config_movement_timeout=-1,
    config_draw_path=True,
    upkeep_hero_ai_active=True,
    upkeep_auto_loot_active=True,
)


@dataclass(frozen=True)
class RouteDefinition:
    region: str
    run_name: str


@dataclass(frozen=True)
class RoutePlan:
    definition: RouteDefinition
    outpost_id: int
    outpost_path: list[tuple[float, float]]
    segments: list[dict[str, Any]]

    @property
    def display(self) -> str:
        return f'[{self.definition.region}] {self.definition.run_name}'


# Discover routes through the same loader used by OutpostRunner, keeping the
# route files as the single source of truth for availability and route data.
def _discover_route_definitions() -> tuple[RouteDefinition, ...]:
    return tuple(
        RouteDefinition(region=region, run_name=run_name)
        for region in get_regions()
        for run_name in get_runs(region)
    )


ROUTE_DEFINITIONS = _discover_route_definitions()
REGIONS: tuple[str, ...] = tuple(sorted({route.region for route in ROUTE_DEFINITIONS}))
QUEUED_ROUTES: list[RoutePlan] = []

_selected_region_index = 0
_selected_route_index = 0
_queue_version = 0
_previous_queue_version = -1
_current_route_index = -1
_current_route_anchor = ''
_route_anchors: list[str] = []
_route_tries: list[int] = []
_ui_error = ''


def _load_route(definition: RouteDefinition) -> RoutePlan:
    data = load_map_data(definition.region, definition.run_name)
    ids = data.get('ids', {})
    outpost_path = data.get('outpost_path', [])
    segments = data.get('segments', [])

    outpost_id = int(ids.get('outpost_id', 0)) if isinstance(ids, dict) else 0
    if outpost_id <= 0:
        raise ValueError('route has no starting outpost ID')
    if not outpost_path:
        raise ValueError('route has no outpost exit path')
    if not segments:
        raise ValueError('route has no explorable segments')

    return RoutePlan(
        definition=definition,
        outpost_id=outpost_id,
        outpost_path=list(outpost_path),
        segments=list(segments),
    )


def _routes_for_region(region: str) -> list[RouteDefinition]:
    return [route for route in ROUTE_DEFINITIONS if route.region == region]


def _route_anchor_name(index: int) -> str:
    return f'OUTPOST_FIGHTER_ROUTE_{index}_START'


def _anchor():
    yield


def _stop_bot():
    bot.Stop()
    yield


def _disable_party_wipe_callback():
    bot.Events.OnPartyWipeCallback(None)
    yield


def _set_current_route(index: int):
    global _current_route_anchor
    global _current_route_index

    _current_route_index = index
    _current_route_anchor = _route_anchors[index]
    _route_tries[index] += 1
    yield


def _build_route_steps(bot_instance: Botting, route: RoutePlan, index: int) -> None:
    bot_instance.States.AddHeader(route.display)

    anchor_name = _route_anchor_name(index)
    _route_anchors.append(anchor_name)
    bot_instance.States.AddCustomState(_anchor, anchor_name)
    bot_instance.States.AddCustomState(lambda route_index=index: _set_current_route(route_index), f'SetRoute_{index}')

    bot_instance.Map.Travel(target_map_id=route.outpost_id)
    bot_instance.Party.SetHardMode(False)
    bot_instance.Multibox.ApplyWidgetPolicy(enable_widgets=WIDGETS_TO_ENABLE)

    first_map_id = int(route.segments[0].get('map_id', 0))
    register_outpost_departure(
        bot_instance,
        route.outpost_path,
        target_map_id=first_map_id,
        step_name=f'{route.definition.run_name}_leave_outpost',
    )

    for segment_index, segment in enumerate(route.segments):
        next_segment = route.segments[segment_index + 1] if segment_index + 1 < len(route.segments) else None
        current_map_id = int(segment.get('map_id', 0))
        next_map_id = int(next_segment.get('map_id', 0)) if next_segment else 0
        transition_map_id = next_map_id if next_map_id and next_map_id != current_map_id else 0
        owns_map_travel = register_botting_segment(
            bot_instance,
            route.definition.run_name,
            segment_index,
            segment,
            target_map_id=transition_map_id,
            resume_key_prefix=f'outpost-fighter:{_queue_version}:{index}',
        )
        if transition_map_id and not owns_map_travel:
            bot_instance.Wait.ForMapToChange(target_map_id=next_map_id)

    bot_instance.Wait.UntilOutOfCombat()


def bot_routine(bot_instance: Botting) -> None:
    global _route_anchors
    global _route_tries

    _route_anchors = []
    _route_tries = [0] * len(QUEUED_ROUTES)

    if not QUEUED_ROUTES:
        ConsoleLog(BOT_NAME, 'No routes queued.', PySystem.Console.MessageType.Error)
        return

    bot_instance.Events.OnPartyWipeCallback(lambda: OnPartyWipe(bot_instance))

    bot_instance.States.AddHeader(BOT_NAME)
    bot_instance.Templates.Aggressive(
        pause_on_danger=True,
        halt_on_death=False,
        movement_timeout=-1,
        account_isolation=True,
        auto_loot=True,
        enable_imp=True,
    )

    for index, route in enumerate(QUEUED_ROUTES):
        _build_route_steps(bot_instance, route, index)

    bot_instance.States.AddHeader('Route Queue Complete')
    bot_instance.States.AddCustomState(_disable_party_wipe_callback, 'DISABLE_PARTY_WIPE_CALLBACK')
    bot_instance.States.AddCustomState(_stop_bot, 'STOP_OUTPOST_FIGHTER')


def _on_party_wipe(bot_instance: Botting):
    yield from Routines.Yield.wait(1500)

    while Agent.IsDead(Player.GetAgentID()):
        yield from Routines.Yield.wait(500)

    while not Routines.Checks.Map.MapValid() or not Player.IsPlayerLoaded():
        yield from Routines.Yield.wait(500)

    if Map.IsOutpost() and _current_route_anchor:
        ConsoleLog(
            BOT_NAME,
            f'Party returned to an outpost. Restarting route {_current_route_index + 1}.',
            PySystem.Console.MessageType.Warning,
        )
        bot_instance.config.FSM.jump_to_state_by_name(_current_route_anchor)
        bot_instance.config.FSM.resume()
        yield
        return

    ConsoleLog(
        BOT_NAME,
        'Party revived at the resurrection shrine. Resuming the current route without resigning.',
        PySystem.Console.MessageType.Warning,
    )
    bot_instance.config.FSM.resume()
    yield


def OnPartyWipe(bot_instance: Botting) -> None:
    fsm = bot_instance.config.FSM
    if fsm.current_state:
        fsm.current_state.reset()
    if not fsm.is_paused():
        fsm.pause()
    fsm.AddManagedCoroutine('OutpostFighterPartyWipe', lambda: _on_party_wipe(bot_instance))


def _reset_bot_runtime() -> None:
    bot.Stop()
    bot.config.FSM = FSM(BOT_NAME)
    bot.config.counters.clear_all()
    bot.config.initialized = False
    bot.UI._FSM_FILTER_START = 0
    bot.UI._FSM_FILTER_END = 0


def _mark_queue_changed() -> None:
    global _queue_version
    _queue_version += 1


def _add_route(definition: RouteDefinition) -> None:
    global _ui_error
    try:
        QUEUED_ROUTES.append(_load_route(definition))
        _ui_error = ''
        _mark_queue_changed()
    except Exception as error:
        _ui_error = f'Could not load {definition.run_name}: {error}'
        ConsoleLog(BOT_NAME, _ui_error, PySystem.Console.MessageType.Error)


def _draw_config() -> None:
    global _previous_queue_version
    global _selected_region_index
    global _selected_route_index

    PyImGui.text('Fight to unlock outposts')
    PyImGui.separator()

    _selected_region_index = PyImGui.combo('Region', _selected_region_index, list(REGIONS))
    if _selected_region_index >= len(REGIONS):
        _selected_region_index = 0

    region_routes = _routes_for_region(REGIONS[_selected_region_index])
    route_names = [route.run_name for route in region_routes]
    if _selected_route_index >= len(route_names):
        _selected_route_index = 0
    _selected_route_index = PyImGui.combo('Route', _selected_route_index, route_names)

    if PyImGui.button('Add Route', 120, 25):
        _add_route(region_routes[_selected_route_index])

    PyImGui.same_line(0, 10)
    if PyImGui.button('Add Region', 120, 25):
        for definition in region_routes:
            _add_route(definition)

    PyImGui.same_line(0, 10)
    if PyImGui.button('Clear Routes', 120, 25):
        QUEUED_ROUTES.clear()
        _mark_queue_changed()

    if _ui_error:
        PyImGui.text_wrapped(_ui_error)

    PyImGui.separator()
    PyImGui.text(f'Queued routes: {len(QUEUED_ROUTES)}')

    route_to_remove = None
    for index, route in enumerate(QUEUED_ROUTES):
        marker = ' <-- CURRENT' if index == _current_route_index and bot.config.initialized else ''
        tries = f' (attempts: {_route_tries[index]})' if index < len(_route_tries) and _route_tries[index] else ''
        PyImGui.text(f'  {index + 1}. {route.display}{tries}{marker}')
        PyImGui.same_line(0, 10)
        if PyImGui.button(f'Remove##route_{index}', 70, 20):
            route_to_remove = index

    if route_to_remove is not None:
        QUEUED_ROUTES.pop(route_to_remove)
        _mark_queue_changed()

    if _queue_version != _previous_queue_version:
        _reset_bot_runtime()
        _previous_queue_version = _queue_version

    PyImGui.separator()
    PyImGui.text_wrapped(
        'OutpostFighter always uses Normal Mode and your currently loaded player and hero builds. '
        'It stays on the OutpostRunner route, pauses for immediate fights and eligible loot, then continues.'
    )


def _draw_help() -> None:
    PyImGui.text('OutpostFighter')
    PyImGui.separator()
    PyImGui.bullet_text('Choose any OutpostRunner route or queue a complete region.')
    PyImGui.bullet_text('Bring your own combat build and hero or henchman party.')
    PyImGui.bullet_text('Fights enemies that engage the party without chasing unrelated groups.')
    PyImGui.bullet_text('Eligible drops are collected according to your Loot Filters settings.')
    PyImGui.bullet_text('The bot always enters explorable areas in Normal Mode.')
    PyImGui.bullet_text('After a full party wipe, the party resurrects at the shrine and continues forward.')


bot.SetMainRoutine(bot_routine)
bot.UI.override_draw_config(_draw_config)
bot.UI.override_draw_help(_draw_help)


def main() -> None:
    if not Routines.Checks.Map.MapValid() or not Player.IsPlayerLoaded():
        return

    bot.UI.draw_window()
    if QUEUED_ROUTES:
        bot.Update()


if __name__ == '__main__':
    main()
