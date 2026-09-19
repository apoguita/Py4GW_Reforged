from __future__ import annotations

import ast
import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ROUTE = (
    ROOT
    / 'Sources'
    / 'aC_Scripts'
    / 'OutpostRunner'
    / 'maps'
    / 'NF - Desolation'
    / '_1_BonePalace_To_BasaltGrotto.py'
)
LAIR_ROUTE = ROUTE.with_name('_2_BonePalace_To_LairOfTheForgotten.py')
MECHANICS = ROOT / 'Sources' / 'aC_Scripts' / 'OutpostRunner' / 'route_mechanics.py'
RUNNER = ROOT / 'Widgets' / 'Automation' / 'Bots' / 'Runners' / 'OutpostRunnerV2.py'
FIGHTER = ROOT / 'Widgets' / 'Automation' / 'Bots' / 'Runners' / 'OutpostFighter.py'
MAPS = ROOT / 'Sources' / 'aC_Scripts' / 'OutpostRunner' / 'maps'
JADE_SEA = MAPS / 'Cantha - The Jade Sea'
ECHOVALD = MAPS / 'Cantha - Echovald Forest'
ETERNAL_GROVE_ROUTE = ECHOVALD / '_9_VasburgArmory_To_TheEternalGrove.py'
SHING_JEA = MAPS / 'Cantha - Shing Jea Island'
TSUMEI_ROUTE = SHING_JEA / '_1_ShingJeaMonastery_To_TsumeiVillage.py'
RANKOR_DWC_ROUTE = (
    MAPS
    / "Tyria - Beacon's Perch To Droknars Forge"
    / '_5_CampRankor_To_DeldrimorWarCamp.py'
)
ELONA_SEEKERS_ROUTE = (
    MAPS
    / 'Tyria - Desert Outposts'
    / '_4_ElonaReach_to_SeekersPassage.py'
)
HARVEST_ROUTE = JADE_SEA / '_7_HarvestTemple_To_UnwakingWatersKurzick.py'
VABBI = MAPS / 'NF - Vabbi Tour'
TORMENT = MAPS / 'NF - Realm of Torment'
KOURNA = MAPS / 'NF - Kourna'
NIGHTFALL_ROUTE_EXPECTATIONS = {
    VABBI / '_3_honurhill_to_dashavestibulepostcampaign.py': 'ROUTE-20260910-192540-375',
    VABBI / '_4_HonurHill_To_YahnurMarket.py': 'ROUTE-20260910-202958-660',
    VABBI / '_5_GrandCourtOfSebelkeh_To_DzagonurBastion.py': 'ROUTE-20260910-203705-316',
    TORMENT / '_1_gateoftorment_to_gateofthenightfallenlands.py': 'ROUTE-20260910-193010-552',
    TORMENT / '_2_gateoftorment_to_theshadownexus.py': 'ROUTE-20260910-193856-605',
    KOURNA / '_1_pogahnpassage_to_camphojanu.py': 'ROUTE-20260910-195056-356',
    KOURNA / '_2_NunduBay_To_DajkahInlet.py': 'ROUTE-20260910-202654-187',
    KOURNA / '_3_KodonurCrossroads_To_RilohnRefuge.py': 'ROUTE-20260911-224924-163',
}
CANHTA_ROUTE_EXPECTATIONS = {
    JADE_SEA / '_3_GyalaHatchery_To_EredonTerrace.py': 'ROUTE-20260910-172546-445',
    JADE_SEA / '_4_EredonTerrace_To_BaiPaasuReach.py': 'ROUTE-20260910-172852-363',
    ECHOVALD / '_1_HouseZuHeltzer_To_SaintAnjekasShrine.py': 'ROUTE-20260910-173207-900',
    ECHOVALD / '_2_SaintAnjekasShrine_To_LutgardisConservatory.py': 'ROUTE-20260910-173531-803',
    ECHOVALD / '_3_SaintAnjekasShrine_To_BrauerAcademy.py': 'ROUTE-20260910-173849-995',
    ECHOVALD / '_4_UnwakingWatersKurzick_To_VasburgArmory.py': 'ROUTE-20260910-174117-968',
    ECHOVALD / '_5_UnwakingWatersKurzick_To_DurheimArchives.py': 'ROUTE-20260910-174532-032',
    ECHOVALD / '_6_VasburgArmory_To_AmatzBasin.py': 'ROUTE-20260910-174813-450',
    ECHOVALD / '_7_HouseZuHeltzer_To_AspenwoodGateKurzick.py': 'ROUTE-20260910-213119-662',
    ECHOVALD / '_8_LutgardisConservatory_To_JadeFlatsKurzick.py': 'ROUTE-20260910-214257-099',
    ETERNAL_GROVE_ROUTE: 'ROUTE-20260914-211649-677',
    JADE_SEA / '_5_UnwakingWatersLuxon_To_SeafarersRest.py': 'ROUTE-20260910-175318-524',
    JADE_SEA / '_6_SeafarersRest_To_AuriosMines.py': 'ROUTE-20260910-175542-883',
    HARVEST_ROUTE: 'ROUTE-20260910-180114-736',
    JADE_SEA / '_8_Cavalon_To_JadeFlatsLuxon.py': 'ROUTE-20260910-181100-432',
    TSUMEI_ROUTE: 'ROUTE-20260910-181601-806',
}


def _route_assignments(route: Path = ROUTE) -> dict[str, object]:
    tree = ast.parse(route.read_text(encoding='utf-8'))
    result: dict[str, object] = {}

    class ReplaceMapLookups(ast.NodeTransformer):
        def visit_Subscript(self, node: ast.Subscript) -> ast.Constant:
            return ast.copy_location(ast.Constant(value=0), node)

    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id.endswith(('_ids', '_outpost_path', '_segments')):
            result[target.id] = ast.literal_eval(ReplaceMapLookups().visit(node.value))
    return result


def _load_mechanics_with_fakes():
    fake_core = types.ModuleType('Py4GWCoreLib')

    class Heroes:
        flags: list[tuple[str, tuple[float, ...]]] = []

        @classmethod
        def FlagAllHeroes(cls, *xy):
            cls.flags.append(('flag', xy))

        @classmethod
        def UnflagAllHeroes(cls):
            cls.flags.append(('unflag', ()))

    fake_core.Agent = types.SimpleNamespace()
    fake_core.ConsoleLog = lambda *_args, **_kwargs: None
    fake_core.Effects = types.SimpleNamespace()
    fake_core.GLOBAL_CACHE = types.SimpleNamespace()
    fake_core.Map = types.SimpleNamespace(GetMapID=lambda: 298)
    fake_core.Party = types.SimpleNamespace(Heroes=Heroes, GetHeroes=lambda: [])
    fake_core.Player = types.SimpleNamespace()
    fake_core.PySystem = types.SimpleNamespace(
        Console=types.SimpleNamespace(MessageType=types.SimpleNamespace(Info=1, Error=2))
    )
    fake_core.Routines = types.SimpleNamespace(Yield=types.SimpleNamespace(wait=lambda _ms: iter(())))
    fake_core.SkillBar = types.SimpleNamespace()

    fake_ri = types.ModuleType('Py4GWCoreLib.routines_src.reliable_interaction')

    class Runtime:
        def __init__(self, **_kwargs):
            pass

    class Record:
        def __init__(self, *args, **kwargs):
            self.args = args
            for key, value in kwargs.items():
                setattr(self, key, value)

    for name in (
        'ApproachSpec',
        'DialogSpec',
        'InteractionSpec',
        'PostconditionSpec',
        'RetryPolicy',
        'TargetSpec',
    ):
        setattr(fake_ri, name, Record)
    for name in ('InteractionProfile', 'PostconditionKind', 'TargetKind'):
        setattr(
            fake_ri,
            name,
            types.SimpleNamespace(
                VISIBLE_CHOICE=1,
                GADGET=2,
                EFFECT_PRESENT=3,
                CUSTOM=4,
                NPC=5,
                QUEST_CONVERSATION=6,
                MAP_CHANGED=7,
            ),
        )
    fake_ri.Py4GWInteractionRuntime = Runtime
    controllers = []

    def controller(spec, runtime):
        controllers.append((spec, runtime))
        return object()

    def adapter(*_args, **_kwargs):
        yield
        return True

    fake_ri.ReliableInteractionController = controller
    fake_ri.run_coroutine_adapter = adapter

    saved = {name: sys.modules.get(name) for name in ('Py4GWCoreLib', 'Py4GWCoreLib.routines_src.reliable_interaction')}
    sys.modules['Py4GWCoreLib'] = fake_core
    sys.modules['Py4GWCoreLib.routines_src.reliable_interaction'] = fake_ri
    try:
        spec = importlib.util.spec_from_file_location('test_route_mechanics_runtime', MECHANICS)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        module._test_interaction_controllers = controllers
        return module, Heroes
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _finish(generator):
    while True:
        try:
            next(generator)
        except StopIteration as done:
            return done.value


class BonePalaceBasaltGrottoRouteTests(unittest.TestCase):
    def test_route_preserves_capture_identity_and_destination(self) -> None:
        data = _route_assignments()
        ids = next(value for key, value in data.items() if key.endswith('_ids'))
        segments = next(value for key, value in data.items() if key.endswith('_segments'))
        self.assertEqual(ids['source_route_id'], 'ROUTE-20260902-140340-849')
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[-1]['steps'], [])

    def test_route_keeps_named_mechanics_in_order(self) -> None:
        data = _route_assignments()
        segments = next(value for key, value in data.items() if key.endswith('_segments'))
        steps = segments[0]['steps']
        self.assertEqual(
            [step['type'] for step in steps],
            [
                'path',
                'blessing',
                'path',
                'enter_junundu',
                'path',
                'path',
                'enter_junundu',
                'path',
                'verify_human_form',
                'path',
            ],
        )
        self.assertEqual(steps[1]['capture_id'], 'NPC-20260902-140420-526')
        self.assertEqual(steps[8]['capture_id'], 'LOC-20260902-141142-793')

    def test_first_sulfur_boundary_does_not_manually_leave_junundu(self) -> None:
        segments = next(value for key, value in _route_assignments().items() if key.endswith('_segments'))
        steps = segments[0]['steps']
        first_spoor = next(index for index, step in enumerate(steps) if step['name'] == 'Enter first Junundu party')
        second_spoor = next(index for index, step in enumerate(steps) if step['name'] == 'Enter second Junundu party')
        boundary_steps = steps[first_spoor + 1:second_spoor]

        self.assertEqual([step['type'] for step in boundary_steps], ['path', 'path'])
        self.assertNotIn('leave_junundu', [step['type'] for step in boundary_steps])
        self.assertEqual(boundary_steps[-1]['name'], 'Stay in Junundu across boundary to second Wurm Spoor')

    def test_blessing_uses_captured_accept_choice_and_margonites_effect(self) -> None:
        segments = next(value for key, value in _route_assignments().items() if key.endswith('_segments'))
        blessing = segments[0]['steps'][1]
        self.assertEqual(blessing['visible_button'], 1)
        self.assertEqual(blessing['model_id'], 5666)
        self.assertEqual(blessing['effect_ids'], (1849, 2036, 2037))

    def test_recorded_combat_backtrack_is_removed(self) -> None:
        segments = next(value for key, value in _route_assignments().items() if key.endswith('_segments'))
        boundary_path = segments[0]['steps'][5]['path']
        self.assertNotIn((-2340.29, 10125.91), boundary_path)
        self.assertNotIn((-3031.43, 8806.78), boundary_path)
        self.assertIn((-2247.34, 10625.07), boundary_path)
        self.assertIn((-1800.66, 10359.92), boundary_path)

    def test_final_wurm_spoor_regroups_the_party_at_the_live_target(self) -> None:
        segments = next(value for key, value in _route_assignments().items() if key.endswith('_segments'))
        final_spoor = segments[0]['steps'][6]
        self.assertEqual(final_spoor['target_xy'], (6997.0, 9996.0))
        self.assertEqual(final_spoor['party_regroup_xy'], final_spoor['target_xy'])
        self.assertEqual(final_spoor['party_regroup_radius'], 300.0)
        self.assertEqual(final_spoor['party_regroup_settle_ms'], 1_500)
        self.assertEqual(final_spoor['mount_attempts'], 3)

    def test_transient_empty_hero_snapshot_cannot_verify_full_wurm_party(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        mechanics.Party.GetHeroCount = lambda: 2
        mechanics.Party.GetHeroes = lambda: []
        mechanics.GLOBAL_CACHE.SkillBar = types.SimpleNamespace(
            GetSkillIDBySlot=lambda _slot: mechanics.JUNUNDU_STRIKE_SKILL_ID
        )

        self.assertFalse(mechanics.full_hero_party_in_junundu(2))
        self.assertFalse(
            mechanics._required_heroes_close(
                300.0,
                (0.0, 0.0),
                expected_hero_count=2,
            )
        )

    def test_both_consumers_use_shared_mechanic_registration(self) -> None:
        for path in (RUNNER, FIGHTER):
            source = path.read_text(encoding='utf-8')
            self.assertIn('register_botting_segment', source)

    def test_shared_mechanics_have_bounded_party_verification_and_retry(self) -> None:
        source = MECHANICS.read_text(encoding='utf-8')
        self.assertIn('full_hero_party_in_junundu', source)
        self.assertIn("Party.Heroes.FlagAllHeroes", source)
        self.assertIn("yield from _leave_junundu()", source)
        self.assertIn("yield from _mount_attempt(bot, data, expected_hero_count)", source)
        self.assertIn('finally:', source)
        self.assertIn('Party.Heroes.UnflagAllHeroes()', source)

    def test_partial_wurm_party_leaves_and_retries_once(self) -> None:
        mechanics, heroes = _load_mechanics_with_fakes()
        calls: list[str] = []

        def wait_until(*_args, **_kwargs):
            calls.append('regroup')
            yield
            return True

        def mount(*_args, **_kwargs):
            calls.append('mount')
            yield
            return calls.count('mount') == 2

        def leave(*_args):
            calls.append('leave')
            yield
            return True

        mechanics.full_hero_party_in_junundu = lambda *_args: False
        mechanics._wait_until = wait_until
        mechanics._mount_attempt = mount
        mechanics._leave_junundu = leave
        result = _finish(
            mechanics._enter_junundu(
                object(),
                {
                    'target_xy': (1.0, 2.0),
                    'party_regroup_xy': (3.0, 4.0),
                    'player_approach_xy': (1.0, 2.0),
                },
            )
        )
        self.assertTrue(result)
        self.assertEqual(calls, ['regroup', 'mount', 'leave', 'regroup', 'mount'])
        self.assertEqual(heroes.flags, [('flag', (3.0, 4.0)), ('unflag', ())])

    def test_second_spoor_can_use_configured_third_mount_attempt(self) -> None:
        mechanics, heroes = _load_mechanics_with_fakes()
        calls: list[str] = []

        def wait_until(*_args, **_kwargs):
            calls.append('regroup')
            yield
            return True

        def mount(*_args, **_kwargs):
            calls.append('mount')
            yield
            return calls.count('mount') == 3

        def leave(*_args):
            calls.append('leave')
            yield
            return True

        mechanics.full_hero_party_in_junundu = lambda *_args: False
        mechanics._wait_until = wait_until
        mechanics._mount_attempt = mount
        mechanics._leave_junundu = leave
        result = _finish(
            mechanics._enter_junundu(
                object(),
                {
                    'name': 'Enter second Junundu party',
                    'target_xy': (1.0, 2.0),
                    'party_regroup_xy': (1.0, 2.0),
                    'player_approach_xy': (1.0, 2.0),
                    'mount_attempts': 3,
                },
            )
        )

        self.assertTrue(result)
        self.assertEqual(
            calls,
            ['regroup', 'mount', 'leave', 'regroup', 'mount', 'leave', 'regroup', 'mount'],
        )
        self.assertEqual(heroes.flags, [('flag', (1.0, 2.0)), ('unflag', ())])

    def test_wurm_regroup_defaults_to_the_spoor_target(self) -> None:
        mechanics, heroes = _load_mechanics_with_fakes()

        def wait_until(*_args, **_kwargs):
            yield
            return True

        def mount(*_args, **_kwargs):
            yield
            return True

        mechanics.full_hero_party_in_junundu = lambda *_args: False
        mechanics._wait_until = wait_until
        mechanics._mount_attempt = mount
        result = _finish(
            mechanics._enter_junundu(
                object(),
                {
                    'target_xy': (7.0, 9.0),
                    'player_approach_xy': (1.0, 2.0),
                },
            )
        )
        self.assertTrue(result)
        self.assertEqual(heroes.flags, [('flag', (7.0, 9.0)), ('unflag', ())])

    def test_party_regroup_proximity_is_measured_from_the_flag_point(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        hero = types.SimpleNamespace(agent_id=7)
        mechanics.Party.GetHeroes = lambda: [hero]
        mechanics.Player.GetXY = lambda: (5_000.0, 5_000.0)
        mechanics.Agent.IsValid = lambda agent_id: agent_id == 7
        mechanics.Agent.IsDead = lambda _agent_id: False
        mechanics.Agent.GetXY = lambda _agent_id: (110.0, 100.0)

        self.assertTrue(mechanics._required_heroes_close(20.0, (100.0, 100.0)))
        self.assertFalse(mechanics._required_heroes_close(5.0, (100.0, 100.0)))

    def test_leave_junundu_retries_dropped_player_cast_and_commands_wurm_heroes(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        player_casts: list[int] = []
        hero_casts: list[tuple[int, int, int]] = []
        mechanics.Party.GetHeroes = lambda: [object()]
        mechanics._party_slot_one = lambda *_args: (
            (mechanics.JUNUNDU_STRIKE_SKILL_ID, (mechanics.JUNUNDU_STRIKE_SKILL_ID,))
            if len(player_casts) < 2
            else (1, (2,))
        )
        mechanics._hero_slot_skill = lambda _position, slot: (
            mechanics.LEAVE_JUNUNDU_SKILL_ID if slot == 8 else None
        )
        mechanics.GLOBAL_CACHE.SkillBar = types.SimpleNamespace(
            GetSkillIDBySlot=lambda slot: mechanics.LEAVE_JUNUNDU_SKILL_ID if slot == 8 else 0
        )
        mechanics.SkillBar = types.SimpleNamespace(
            UseSkillTargetless=lambda slot: player_casts.append(slot),
            HeroUseSkill=lambda target, slot, hero: hero_casts.append((target, slot, hero)),
        )

        self.assertTrue(_finish(mechanics._leave_junundu()))
        self.assertEqual(player_casts, [8, 8])
        self.assertEqual(hero_casts, [(0, 8, 1), (0, 8, 1)])

    def test_mount_uses_horde_target_centered_approach_contract(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        hero_ai = types.SimpleNamespace(is_active=lambda: True, set_now=lambda *_args: None)
        fake_bot = types.SimpleNamespace(
            config=types.SimpleNamespace(upkeep=types.SimpleNamespace(hero_ai=hero_ai))
        )
        result = _finish(
            mechanics._mount_attempt(
                fake_bot,
                {
                    'name': 'Wurm Spoor',
                    'target_xy': (-10867.0, 4322.0),
                    'player_approach_xy': (-10867.0, 4322.0),
                    'capture_id': 'wurm-spoor',
                },
            )
        )
        self.assertTrue(result)
        spec, _runtime = mechanics._test_interaction_controllers[0]
        self.assertEqual(spec.approach.player_approach_xy, (-10867.0, 4322.0))
        self.assertEqual(spec.approach.tolerance, 120.0)
        self.assertEqual(spec.approach.target_tolerance, 220.0)
        self.assertEqual(spec.target.search_radius, 1_500.0)

    def test_cancelled_mount_always_clears_hero_flag(self) -> None:
        mechanics, heroes = _load_mechanics_with_fakes()

        def wait_forever(*_args, **_kwargs):
            while True:
                yield

        mechanics.full_hero_party_in_junundu = lambda *_args: False
        mechanics._wait_until = wait_forever
        operation = mechanics._enter_junundu(
            object(),
            {
                'target_xy': (3.0, 4.0),
                'player_approach_xy': (3.0, 4.0),
            },
        )
        next(operation)
        operation.close()
        self.assertEqual(heroes.flags, [('flag', (3.0, 4.0)), ('unflag', ())])

    def test_required_mechanic_failure_stops_route(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()

        class Bot:
            stopped = False

            def Stop(self):
                self.stopped = True

        def fail_leave():
            yield
            return False

        bot = Bot()
        mechanics._leave_junundu = fail_leave
        result = _finish(mechanics._run_required_action(bot, {'type': 'leave_junundu', 'name': 'leave'}))
        self.assertFalse(result)
        self.assertTrue(bot.stopped)


class SharedPortalTransitionTests(unittest.TestCase):
    @staticmethod
    def _bot():
        calls: list[tuple[str, object, object]] = []

        class Move:
            @staticmethod
            def FollowPath(points, step_name=''):
                calls.append(('direct', list(points), step_name))

            @staticmethod
            def FollowAutoPath(points, step_name='', resume_key=None):
                calls.append(('path', list(points), (step_name, resume_key)))

            @staticmethod
            def FollowPathAndExitMap(points, target_map_id=0, step_name='', resume_key=None):
                calls.append(('portal', list(points), (target_map_id, step_name, resume_key)))

            @staticmethod
            def _coro_follow_path_and_exit_map(
                points,
                target_map_id=0,
                step_name='',
                resume_key=None,
            ):
                calls.append(('runtime_portal', list(points), (target_map_id, step_name, resume_key)))
                yield

        class States:
            @staticmethod
            def AddCustomState(action, name):
                calls.append(('state', action, name))

        return types.SimpleNamespace(Move=Move, States=States), calls

    def test_portal_extension_matches_mission_runner_distance_and_heading(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        extended = mechanics.extended_portal_path([(0.0, 0.0), (300.0, 400.0)])
        self.assertEqual(extended[:2], [(0.0, 0.0), (300.0, 400.0)])
        self.assertAlmostEqual(math.dist(extended[-2], extended[-1]), 450.0)
        self.assertAlmostEqual(extended[-1][0], 570.0)
        self.assertAlmostEqual(extended[-1][1], 760.0)

    def test_single_point_portal_uses_live_approach_heading(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        extended = mechanics.extended_portal_path(
            [(300.0, 400.0)],
            approach_origin=(0.0, 0.0),
        )
        self.assertEqual(extended[0], (300.0, 400.0))
        self.assertAlmostEqual(math.dist(extended[-2], extended[-1]), 450.0)
        self.assertAlmostEqual(extended[-1][0], 570.0)
        self.assertAlmostEqual(extended[-1][1], 760.0)

    def test_outpost_departure_resolves_single_point_heading_when_state_runs(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        bot, calls = self._bot()
        mechanics.Player.GetXY = lambda: (0.0, 0.0)

        mechanics.register_outpost_departure(
            bot,
            [(300.0, 400.0)],
            target_map_id=2,
            step_name='Leave outpost',
        )
        self.assertEqual(calls[0][0], 'state')

        _finish(calls[0][1]())
        self.assertEqual(calls[1][0], 'runtime_portal')
        self.assertEqual(calls[1][1][0], (300.0, 400.0))
        self.assertAlmostEqual(calls[1][1][-1][0], 570.0)
        self.assertAlmostEqual(calls[1][1][-1][1], 760.0)
        self.assertEqual(calls[1][2][0], 2)

    def test_physical_transition_uses_extended_path_and_owns_map_load(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        bot, calls = self._bot()
        owns_map_travel = mechanics.register_botting_segment(
            bot,
            'Route',
            0,
            {'map_id': 1, 'path': [(0.0, 0.0), (100.0, 0.0)]},
            target_map_id=2,
        )
        self.assertTrue(owns_map_travel)
        self.assertEqual(calls[0][0], 'portal')
        self.assertEqual(calls[0][1][-1], (550.0, 0.0))
        self.assertEqual(calls[0][2][0], 2)

    def test_captured_portal_exit_replaces_straight_line_extension(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        bot, calls = self._bot()
        owns_map_travel = mechanics.register_botting_segment(
            bot,
            'Angled portal',
            0,
            {
                'map_id': 1,
                'path': [(0.0, 0.0), (100.0, 0.0)],
                'portal_exit_xy': (150.0, 200.0),
            },
            target_map_id=2,
        )
        self.assertTrue(owns_map_travel)
        self.assertEqual(calls[0][0], 'portal')
        self.assertEqual(calls[0][1], [(0.0, 0.0), (100.0, 0.0), (150.0, 200.0)])
        self.assertEqual(calls[0][2][0], 2)

    def test_non_transition_segment_remains_an_ordinary_path(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        bot, calls = self._bot()
        owns_map_travel = mechanics.register_botting_segment(
            bot,
            'Route',
            0,
            {'map_id': 1, 'path': [(0.0, 0.0), (100.0, 0.0)]},
        )
        self.assertFalse(owns_map_travel)
        self.assertEqual(calls[0][0], 'path')
        self.assertIsNone(calls[0][2][1])

    def test_direct_path_uses_captured_points_without_autopath(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        bot, calls = self._bot()
        owns_map_travel = mechanics.register_botting_segment(
            bot,
            'Bridge route',
            0,
            {
                'map_id': 1,
                'steps': [
                    {
                        'type': 'direct_path',
                        'name': 'Bridge Start to Bridge End',
                        'path': [(10.0, 20.0), (30.0, 40.0)],
                    },
                ],
            },
        )
        self.assertFalse(owns_map_travel)
        self.assertEqual(
            calls,
            [('direct', [(10.0, 20.0), (30.0, 40.0)], 'Bridge Start to Bridge End')],
        )

    def test_opt_in_resume_keys_are_stable_per_segment_step(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        bot, calls = self._bot()
        owns_map_travel = mechanics.register_botting_segment(
            bot,
            'Route',
            2,
            {
                'map_id': 1,
                'steps': [
                    {'type': 'path', 'path': [(0.0, 0.0)]},
                    {'type': 'path', 'path': [(100.0, 0.0), (200.0, 0.0)]},
                ],
            },
            target_map_id=2,
            resume_key_prefix='outpost-fighter:4:1',
        )
        self.assertTrue(owns_map_travel)
        self.assertEqual(calls[0][2][1], 'outpost-fighter:4:1:segment:2:step:1')
        self.assertEqual(calls[1][2][2], 'outpost-fighter:4:1:segment:2:step:2')

    def test_dialogue_transfer_does_not_extend_approach_path(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        bot, calls = self._bot()
        owns_map_travel = mechanics.register_botting_segment(
            bot,
            'Dialogue route',
            0,
            {
                'map_id': 1,
                'steps': [
                    {'type': 'path', 'path': [(0.0, 0.0), (100.0, 0.0)]},
                    {'type': 'npc_dialog_sequence', 'name': 'NPC transfer'},
                ],
            },
            target_map_id=2,
        )
        self.assertFalse(owns_map_travel)
        self.assertEqual(calls[0][0], 'path')
        self.assertEqual(calls[0][1], [(0.0, 0.0), (100.0, 0.0)])
        self.assertEqual(calls[1][0], 'state')

    def test_short_or_coincident_geometry_is_not_invented(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        self.assertEqual(mechanics.extended_portal_path([(1.0, 2.0)]), [(1.0, 2.0)])
        self.assertEqual(
            mechanics.extended_portal_path([(1.0, 2.0), (1.0, 2.0)]),
            [(1.0, 2.0), (1.0, 2.0)],
        )

    def test_both_consumers_use_shared_extension_and_transition_ownership(self) -> None:
        for path in (RUNNER, FIGHTER):
            with self.subTest(path=path.name):
                source = path.read_text(encoding='utf-8')
                self.assertIn('extended_portal_path', source)
                self.assertIn('register_outpost_departure', source)
                self.assertIn('target_map_id=transition_map_id', source)
                self.assertIn('not owns_map_travel', source)

    def test_both_consumers_reload_shared_mechanics_before_binding_exports(self) -> None:
        for path in (RUNNER, FIGHTER):
            with self.subTest(path=path.name):
                source = path.read_text(encoding='utf-8')
                self.assertIn('importlib.reload(_route_mechanics)', source)
                self.assertIn('extended_portal_path = _route_mechanics.extended_portal_path', source)
                self.assertIn('register_outpost_departure = _route_mechanics.register_outpost_departure', source)

    def test_camp_rankor_route_drops_stale_snake_dance_portal_threshold(self) -> None:
        data = _route_assignments(RANKOR_DWC_ROUTE)
        outpost_path = next(
            value for key, value in data.items() if key.endswith('_outpost_path')
        )
        segments = next(value for key, value in data.items() if key.endswith('_segments'))
        self.assertEqual(
            outpost_path,
            [
                (7156.76, -42409.7),
                (6825.02, -42034.35),
                (6466.88, -41678.51),
            ],
        )
        self.assertEqual(segments[0]['path'][0], (5680.65, -41273.91))
        self.assertNotIn((6163.73, -41408.86), segments[0]['path'])

    def test_routes_do_not_replay_stale_portal_thresholds(self) -> None:
        stale_starts = {
            ECHOVALD / '_2_SaintAnjekasShrine_To_LutgardisConservatory.py': {
                (-9358.17, -21646.29),
            },
            ECHOVALD / '_6_VasburgArmory_To_AmatzBasin.py': {(18505.81, 1979.94)},
            ECHOVALD / '_8_LutgardisConservatory_To_JadeFlatsKurzick.py': {
                (-7676.80, 1805.39),
            },
            JADE_SEA / '_4_EredonTerrace_To_BaiPaasuReach.py': {(18346.92, 11625.72)},
            JADE_SEA / '_6_SeafarersRest_To_AuriosMines.py': {
                (-11134.94, -18376.52),
            },
            HARVEST_ROUTE: {(3272.80, 2452.22)},
            ROUTE: {(-14622.84, 3444.11)},
            LAIR_ROUTE: {(-14614.51, 3470.76)},
            KOURNA / '_2_NunduBay_To_DajkahInlet.py': {(-15507.39, -4059.98)},
            VABBI / '_4_HonurHill_To_YahnurMarket.py': {(-18720.30, 13522.03)},
            VABBI / '_5_GrandCourtOfSebelkeh_To_DzagonurBastion.py': {(2705.86, 8103.76)},
            MAPS
            / "Tyria - Beacon's Perch To Droknars Forge"
            / '_1_BeaconsPerch_To_DeldrimorWarCamp.py': {(-18593, -9945)},
            MAPS
            / "Tyria - Beacon's Perch To Droknars Forge"
            / '_4_DeldrimorWarCamp_To_CampRankor.py': {
                (-2835.64, -4288.15),
                (7571.86, -2955.53),
            },
            RANKOR_DWC_ROUTE: {(-18593, -9945)},
            MAPS
            / "Tyria - Beacon's Perch To Droknars Forge"
            / '_8_DeldrimorWarCamp_To_TheGraniteCitadel.py': {(-2908.64, -4574.38)},
            MAPS
            / "Tyria - Beacon's Perch To Droknars Forge"
            / '_9_TheGraniteCitadel_To_CopperhammerMines.py': {(-11514.46, 15385.34)},
        }

        for route, forbidden in stale_starts.items():
            segments = next(
                value for key, value in _route_assignments(route).items() if key.endswith('_segments')
            )
            starts = []
            for segment in segments:
                if segment.get('path'):
                    starts.append(segment['path'][0])
                starts.extend(
                    step['path'][0]
                    for step in segment.get('steps', [])
                    if step.get('path')
                )
            with self.subTest(route=route.name):
                self.assertTrue(starts)
                self.assertTrue(forbidden.isdisjoint(starts))

    def test_camp_rankor_route_splices_captured_replacement_over_closed_detour(self) -> None:
        data = _route_assignments(RANKOR_DWC_ROUTE)
        ids = next(value for key, value in data.items() if key.endswith('_ids'))
        segments = next(value for key, value in data.items() if key.endswith('_segments'))
        path = segments[0]['path']
        splice = path.index((785.8, -28165.28))
        replacement = [
            (335.99, -28006.2),
            (-146.68, -27863.74),
            (-657.08, -27810.81),
            (-1170.03, -27827.37),
            (-1667.49, -27925.54),
            (-2167.71, -27998.39),
            (-2667.36, -28038.94),
            (-3167.11, -28071.2),
            (-3669.71, -28108.58),
            (-4170.24, -28139.68),
            (-4673.2, -28118.27),
            (-5147.58, -27937.02),
            (-5453.73, -27534.42),
            (-5644.42, -27063.74),
            (-5775.51, -26579.78),
        ]
        self.assertEqual(ids['replacement_route_id'], 'ROUTE-20260911-202732-875')
        self.assertEqual(path[splice + 1:splice + 16], replacement)
        self.assertEqual(path[splice + 16], (-5757.33, -26449.17))
        for removed in (
            (452.79, -27789.46),
            (-411.82, -26334.12),
            (-631.29, -26066.41),
            (-3932.8, -28138.77),
            (-5278.18, -27810.96),
            (-5724.72, -26952.08),
        ):
            self.assertNotIn(removed, path)

    def test_saint_anjeka_exit_has_stable_heading_and_avoids_ferndale_npcs(self) -> None:
        route = ECHOVALD / '_2_SaintAnjekasShrine_To_LutgardisConservatory.py'
        data = _route_assignments(route)
        ids = next(value for key, value in data.items() if key.endswith('_ids'))
        outpost_path = next(
            value for key, value in data.items() if key.endswith('_outpost_path')
        )
        segments = next(value for key, value in data.items() if key.endswith('_segments'))
        ferndale_path = segments[0]['path']
        replacement = [
            (-8901.0, -21640.4),
            (-8501.25, -21333.81),
            (-8105.0, -21024.71),
            (-7712.53, -20708.52),
            (-7319.51, -20390.7),
        ]

        self.assertEqual(
            ids['start_replacement_route_id'],
            'ROUTE-20260912-163352-904',
        )
        self.assertEqual(
            outpost_path,
            [(-9785.0, -21673.0), (-9358.17, -21646.29)],
        )
        self.assertEqual(ferndale_path[:5], replacement)
        self.assertEqual(ferndale_path[5], (-7037.39, -20465.64))
        for blocked_start in (
            (-8177.0, -21440.0),
            (-7863.2, -21042.6),
            (-7458.76, -20742.54),
        ):
            self.assertNotIn(blocked_start, ferndale_path)

    def test_elona_reach_route_uses_smoothed_seekers_passage_capture(self) -> None:
        data = _route_assignments(ELONA_SEEKERS_ROUTE)
        ids = next(value for key, value in data.items() if key.endswith('_ids'))
        segments = next(value for key, value in data.items() if key.endswith('_segments'))
        path = segments[1]['path']
        splice = path.index((-5938, 15359))
        replacement = [
            (-7794.48, 14427.95),
            (-8212.75, 14139.39),
            (-8635.64, 13863.79),
            (-9017.77, 13534.27),
            (-9352.86, 13162.49),
            (-9667.11, 12768.51),
            (-9961.17, 12363.46),
            (-10255.68, 11957.78),
            (-10551.14, 11550.8),
            (-10884.24, 11089.74),
            (-11190.28, 10687.65),
            (-11500.66, 10293.86),
            (-11734.9, 9851.13),
            (-11909.36, 9376.21),
            (-12087.99, 8908.21),
            (-12260.87, 8433.27),
            (-12430.99, 7958.46),
            (-12544.54, 7809.47),
            (-12797.41, 7375.08),
            (-13063.87, 6945.42),
            (-13415.51, 6585.91),
            (-13875.13, 6388.07),
            (-14371.68, 6318.42),
            (-14851.53, 6472.3),
            (-15295.84, 6706.54),
            (-15739.69, 6943.62),
            (-16040.12, 7350.31),
            (-16318.77, 7771.75),
        ]
        self.assertEqual(ids['replacement_route_id'], 'ROUTE-20260911-210807-345')
        self.assertEqual(path[splice + 1:], replacement)
        for combat_noise in (
            (-12089.34, 8798.29),
            (-12480.36, 8331.35),
            (-12600.93, 8821.92),
            (-12350.28, 8273.44),
        ):
            self.assertNotIn(combat_noise, path)

    def test_fighter_does_not_suppress_unmanaged_transition_failures(self) -> None:
        source = FIGHTER.read_text(encoding='utf-8')
        self.assertNotIn('set_on_unmanaged_fail(lambda: False)', source)


class BonePalaceLairOfTheForgottenRouteTests(unittest.TestCase):
    def test_route_preserves_both_capture_sources_and_destination(self) -> None:
        data = _route_assignments(LAIR_ROUTE)
        ids = next(value for key, value in data.items() if key.endswith('_ids'))
        segments = next(value for key, value in data.items() if key.endswith('_segments'))
        self.assertEqual(ids['source_route_id'], 'ROUTE-20260910-151459-766')
        self.assertEqual(ids['prefix_source_route_id'], 'ROUTE-20260905-170837-570')
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[-1]['steps'], [])

    def test_route_reuses_blessing_and_full_party_wurm_boundaries(self) -> None:
        segments = next(
            value for key, value in _route_assignments(LAIR_ROUTE).items() if key.endswith('_segments')
        )
        self.assertEqual(
            [step['type'] for step in segments[0]['steps']],
            ['path', 'blessing', 'path', 'enter_junundu', 'path'],
        )
        self.assertEqual(
            [step['type'] for step in segments[1]['steps']],
            ['path', 'blessing', 'path', 'enter_junundu', 'path'],
        )
        shattered_wurm = segments[1]['steps'][3]
        self.assertEqual(shattered_wurm['target_xy'], (-3838.0, -8831.0))
        self.assertEqual(shattered_wurm['party_regroup_xy'], (-3838.0, -8831.0))
        self.assertEqual(shattered_wurm['party_regroup_radius'], 300.0)
        self.assertEqual(shattered_wurm['player_approach_xy'], (-3838.0, -8831.0))
        self.assertEqual(
            shattered_wurm['capture_id'],
            'user-screenshot-shattered-ravines-wurm-spoor-20260909',
        )

    def test_all_desolation_wurm_steps_regroup_at_the_spoor(self) -> None:
        for route in (ROUTE, LAIR_ROUTE):
            segments = next(
                value for key, value in _route_assignments(route).items() if key.endswith('_segments')
            )
            steps = [
                step
                for segment in segments
                for step in segment.get('steps', [])
                if step.get('type') == 'enter_junundu'
            ]
            self.assertTrue(steps)
            for step in steps:
                with self.subTest(route=route.name, step=step['name']):
                    self.assertEqual(step['player_approach_xy'], step['target_xy'])
                    self.assertEqual(step['party_regroup_xy'], step['target_xy'])
                    self.assertEqual(step['party_regroup_radius'], 300.0)
                    self.assertNotIn('regroup_xy', step)

    def test_wrong_turn_and_recorded_backtrack_are_removed_at_rejoin(self) -> None:
        segments = next(
            value for key, value in _route_assignments(LAIR_ROUTE).items() if key.endswith('_segments')
        )
        path = segments[1]['steps'][4]['path']
        rejoin_index = path.index((-4087.42, 5629.35))
        self.assertEqual(path[rejoin_index + 1], (-3763.87, 5700.3))
        self.assertEqual(path[rejoin_index + 2], (-3284.36, 5552.99))
        for removed in (
            (-3862.15, 6076.34),
            (-2981.65, 7882.73),
            (-1580.13, 7493.71),
            (-3972.13, 6155.34),
        ):
            self.assertNotIn(removed, path)


class CanthaCapturedRouteTests(unittest.TestCase):
    def test_all_requested_routes_preserve_capture_identity_and_finish_at_an_outpost(self) -> None:
        self.assertEqual(len(CANHTA_ROUTE_EXPECTATIONS), 16)
        for route, capture_id in CANHTA_ROUTE_EXPECTATIONS.items():
            with self.subTest(route=route.name):
                data = _route_assignments(route)
                ids = next(value for key, value in data.items() if key.endswith('_ids'))
                segments = next(value for key, value in data.items() if key.endswith('_segments'))
                self.assertEqual(ids['source_route_id'], capture_id)
                self.assertTrue(segments)
                self.assertEqual(segments[-1].get('path', segments[-1].get('steps')), [])
                source = route.read_text(encoding='utf-8')
                self.assertNotIn('agent_id_runtime_only', source)
                self.assertNotIn('captured_at', source)

    def test_no_stale_cross_map_coordinate_remains_inside_a_route_path(self) -> None:
        for route in CANHTA_ROUTE_EXPECTATIONS:
            segments = next(
                value for key, value in _route_assignments(route).items() if key.endswith('_segments')
            )
            for segment_index, segment in enumerate(segments[:-1]):
                paths = [segment.get('path', [])]
                paths.extend(step.get('path', []) for step in segment.get('steps', []))
                for path in paths:
                    for left, right in zip(path, path[1:]):
                        with self.subTest(route=route.name, segment=segment_index, left=left, right=right):
                            self.assertLessEqual(math.dist(left, right), 2_000.0)

    def test_gyala_resurrection_altar_is_stitched_out(self) -> None:
        route = JADE_SEA / '_3_GyalaHatchery_To_EredonTerrace.py'
        segments = next(value for key, value in _route_assignments(route).items() if key.endswith('_segments'))
        path = segments[0]['path']
        stitch = path.index((19793.28, 9872.88))
        self.assertEqual(path[stitch + 1], (18892.01, 10907.63))
        self.assertNotIn((19189.0, 11311.0), path)

    def test_ferndale_bridge_has_only_named_start_and_end(self) -> None:
        route = ECHOVALD / '_1_HouseZuHeltzer_To_SaintAnjekasShrine.py'
        segments = next(value for key, value in _route_assignments(route).items() if key.endswith('_segments'))
        path = segments[0]['path']
        start = path.index((-9305.57, 8852.48))
        self.assertEqual(path[start + 1], (-7429.13, 8685.64))
        for bridge_middle in ((-8807.14, 8797.72), (-8302.41, 8763.81), (-7800.25, 8719.11)):
            self.assertNotIn(bridge_middle, path)

    def test_eternal_grove_route_stitches_death_and_crosses_bridge_directly(self) -> None:
        data = _route_assignments(ETERNAL_GROVE_ROUTE)
        outpost_path = next(
            value for key, value in data.items() if key.endswith('_outpost_path')
        )
        segments = next(value for key, value in data.items() if key.endswith('_segments'))
        steps = segments[0]['steps']

        self.assertEqual(outpost_path[-2:], [(19173.32, 2631.56), (18817.39, 2273.60)])
        self.assertEqual([step['type'] for step in steps], ['path', 'direct_path', 'path'])
        self.assertEqual(
            steps[1]['path'],
            [(1352.85, 11706.08), (-11.16, 10773.75)],
        )
        self.assertEqual(steps[2]['path'][0], (-14.30, 9929.33))
        self.assertEqual(steps[2]['path'][-1], (-5414.19, 9461.30))
        self.assertEqual(segments[-1]['steps'], [])

        retained = [point for step in steps for point in step.get('path', [])]
        self.assertNotIn((18568.48, 2017.34), retained)
        self.assertNotIn((14692.08, 1762.97), retained)
        self.assertNotIn((14551.83, 1282.04), retained)
        self.assertNotIn((374.68, 10965.19), retained)

    def test_eternal_grove_route_uses_shared_450_unit_destination_portal(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        segments = next(
            value
            for key, value in _route_assignments(ETERNAL_GROVE_ROUTE).items()
            if key.endswith('_segments')
        )
        bot, calls = SharedPortalTransitionTests._bot()

        owns_map_travel = mechanics.register_botting_segment(
            bot,
            'Vasburg Armory to The Eternal Grove',
            0,
            segments[0],
            target_map_id=222,
            resume_key_prefix='outpost-fighter:route:9',
        )

        self.assertTrue(owns_map_travel)
        self.assertEqual([call[0] for call in calls], ['path', 'direct', 'portal'])
        portal_call = calls[-1]
        self.assertEqual(portal_call[2][0], 222)
        self.assertEqual(portal_call[1][-2], (-5414.19, 9461.30))
        self.assertAlmostEqual(math.dist(portal_call[1][-2], portal_call[1][-1]), 450.0)

    def test_aspenwood_route_omits_stale_cross_map_entry_coordinate(self) -> None:
        route = ECHOVALD / '_7_HouseZuHeltzer_To_AspenwoodGateKurzick.py'
        segments = next(value for key, value in _route_assignments(route).items() if key.endswith('_segments'))
        self.assertEqual(segments[0]['path'][0], (-13245.00, 14888.00))
        self.assertNotIn((10338.95, -1119.16), segments[0]['path'])
        self.assertEqual(segments[-1]['path'], [])

    def test_cavalon_route_reuses_the_proven_outpost_exit(self) -> None:
        route = JADE_SEA / '_8_Cavalon_To_JadeFlatsLuxon.py'
        outpost_path = next(
            value for key, value in _route_assignments(route).items() if key.endswith('_outpost_path')
        )
        self.assertEqual(outpost_path[0], (5872.52, 742.1))
        self.assertEqual(outpost_path[-1], (6650.0, -7550.0))

    def test_dedrick_route_uses_shared_label_sequence_and_map_postcondition(self) -> None:
        segments = next(
            value for key, value in _route_assignments(HARVEST_ROUTE).items() if key.endswith('_segments')
        )
        self.assertEqual([step['type'] for step in segments[0]['steps']], ['path', 'npc_dialog_sequence'])
        dialog = segments[0]['steps'][1]
        self.assertEqual(dialog['model_id'], 3435)
        self.assertEqual(dialog['target_xy'], (-10449.0, -55.0))
        self.assertEqual(
            dialog['visible_button_labels'],
            ('We have business in Unwaking Waters.', 'We are ready.', 'Yes.'),
        )
        self.assertEqual(
            dialog['capture_ids'],
            ('NPC-20260910-180722-960', 'NPC-20260910-180800-857', 'ROUTE-20260910-180114-736'),
        )
        path = segments[0]['steps'][0]['path']
        stitch = path.index((-3506.39, 5543.48))
        self.assertEqual(path[stitch + 1], (-3817.59, 5024.07))

    def test_dialog_adapter_delegates_to_shared_controller(self) -> None:
        mechanics, _heroes = _load_mechanics_with_fakes()
        mechanics._RouteInteractionRuntime = lambda *_args, **_kwargs: object()
        result = _finish(
            mechanics._npc_dialog_sequence(
                object(),
                {
                    'name': 'Dedrick',
                    'model_id': 3435,
                    'target_name': 'Gatekeeper Dedrick',
                    'target_xy': (-10449.0, -55.0),
                    'player_approach_xy': (-10429.37, 21.51),
                    'visible_button_labels': ('First', 'Second', 'Third'),
                    'target_map_id': 298,
                    'capture_ids': ('one', 'three', 'route'),
                },
            )
        )
        self.assertTrue(result)
        spec, _runtime = mechanics._test_interaction_controllers[0]
        self.assertEqual(spec.dialog.visible_button_labels, ('First', 'Second', 'Third'))
        self.assertEqual(spec.postcondition.args[1], 298)
        self.assertEqual(spec.source_capture_ids, ('one', 'three', 'route'))

    def test_tsumei_uses_captured_point_across_angled_portal(self) -> None:
        segments = next(
            value for key, value in _route_assignments(TSUMEI_ROUTE).items() if key.endswith('_segments')
        )
        sunqua = segments[0]
        self.assertEqual(sunqua['portal_exit_xy'], (-4717.07, -13301.82))
        self.assertEqual(sunqua['path'][-2:], [(-3908.34, -12788.56), (-4392.07, -12929.78)])
        self.assertEqual(segments[-1]['path'], [])


class NightfallCapturedRouteTests(unittest.TestCase):
    def test_all_requested_routes_preserve_capture_identity_and_destination(self) -> None:
        self.assertEqual(len(NIGHTFALL_ROUTE_EXPECTATIONS), 8)
        for route, capture_id in NIGHTFALL_ROUTE_EXPECTATIONS.items():
            with self.subTest(route=route.name):
                data = _route_assignments(route)
                ids = next(value for key, value in data.items() if key.endswith('_ids'))
                segments = next(value for key, value in data.items() if key.endswith('_segments'))
                self.assertEqual(ids['source_route_id'], capture_id)
                self.assertTrue(segments)
                self.assertEqual(segments[-1]['path'], [])

    def test_routes_use_canonical_py4gw_map_names(self) -> None:
        expected_lookups = {
            VABBI / '_3_honurhill_to_dashavestibulepostcampaign.py': (
                'outpost_name_to_id["Honur Hill"]',
                'explorable_name_to_id["The Mirror of Lyss"]',
                'outpost_name_to_id["Dasha Vestibule outpost"]',
            ),
            VABBI / '_4_HonurHill_To_YahnurMarket.py': (
                'outpost_name_to_id["Honur Hill"]',
                'explorable_name_to_id["Resplendent Makuun"]',
                'outpost_name_to_id["Yahnur Market"]',
            ),
            VABBI / '_5_GrandCourtOfSebelkeh_To_DzagonurBastion.py': (
                'outpost_name_to_id["Grand Court of Sebelkeh outpost"]',
                'explorable_name_to_id["The Mirror of Lyss"]',
                'outpost_name_to_id["Dzagonur Bastion outpost"]',
            ),
            TORMENT / '_1_gateoftorment_to_gateofthenightfallenlands.py': (
                'outpost_name_to_id["Gate of Torment"]',
                'explorable_name_to_id["Nightfallen Jahai"]',
                'outpost_name_to_id["Gate of the Nightfallen Lands"]',
            ),
            TORMENT / '_2_gateoftorment_to_theshadownexus.py': (
                'outpost_name_to_id["Gate of Torment"]',
                'outpost_name_to_id["The Shadow Nexus outpost"]',
            ),
            KOURNA / '_1_pogahnpassage_to_camphojanu.py': (
                'outpost_name_to_id["Pogahn Passage outpost"]',
                'explorable_name_to_id["Dejarin Estate"]',
                'outpost_name_to_id["Camp Hojanu"]',
            ),
            KOURNA / '_2_NunduBay_To_DajkahInlet.py': (
                'outpost_name_to_id["Nundu Bay outpost"]',
                'explorable_name_to_id["Marga Coast"]',
                'outpost_name_to_id["Dajkah Inlet outpost"]',
            ),
            KOURNA / '_3_KodonurCrossroads_To_RilohnRefuge.py': (
                'outpost_name_to_id["Kodonur Crossroads outpost"]',
                'explorable_name_to_id["The Floodplain of Mahnkelon"]',
                'outpost_name_to_id["Rilohn Refuge outpost"]',
            ),
        }
        for route, lookups in expected_lookups.items():
            source = route.read_text(encoding='utf-8')
            for lookup in lookups:
                with self.subTest(route=route.name, lookup=lookup):
                    self.assertIn(lookup, source)

    def test_no_cross_map_coordinate_jump_remains_in_a_route_path(self) -> None:
        for route in NIGHTFALL_ROUTE_EXPECTATIONS:
            data = _route_assignments(route)
            outpost_path = next(value for key, value in data.items() if key.endswith('_outpost_path'))
            segments = next(value for key, value in data.items() if key.endswith('_segments'))
            for path in [outpost_path, *(segment['path'] for segment in segments)]:
                for left, right in zip(path, path[1:]):
                    with self.subTest(route=route.name, left=left, right=right):
                        self.assertLessEqual(math.dist(left, right), 2_000.0)

    def test_post_campaign_dasha_route_is_a_physical_portal_route(self) -> None:
        route = VABBI / '_3_honurhill_to_dashavestibulepostcampaign.py'
        data = _route_assignments(route)
        segments = next(value for key, value in data.items() if key.endswith('_segments'))
        self.assertEqual(len(segments), 2)
        self.assertTrue(segments[0]['path'])
        self.assertNotIn('npc_dialog_sequence', route.read_text(encoding='utf-8'))

    def test_shadow_nexus_capture_contains_no_retained_closed_backtrack(self) -> None:
        route = TORMENT / '_2_gateoftorment_to_theshadownexus.py'
        outpost_path = next(
            value for key, value in _route_assignments(route).items() if key.endswith('_outpost_path')
        )
        for left_index, left in enumerate(outpost_path):
            for right in outpost_path[left_index + 4:]:
                self.assertGreaterEqual(math.dist(left, right), 650.0)

    def test_pogahn_closed_meander_is_spliced_out(self) -> None:
        route = KOURNA / '_1_pogahnpassage_to_camphojanu.py'
        segments = next(value for key, value in _route_assignments(route).items() if key.endswith('_segments'))
        path = segments[0]['path']
        splice = path.index((-3255.90, -390.39))
        self.assertEqual(path[splice + 1], (-3252.19, -302.91))
        for removed in (
            (-3699.21, -150.45),
            (-5389.77, -404.01),
            (-6081.45, -1593.53),
            (-3922.28, 7.07),
        ):
            self.assertNotIn(removed, path)

    def test_kodonur_route_smooths_combat_reversals_and_crosses_rilohn_portal(self) -> None:
        route = KOURNA / '_3_KodonurCrossroads_To_RilohnRefuge.py'
        data = _route_assignments(route)
        segments = next(value for key, value in data.items() if key.endswith('_segments'))
        floodplain = segments[0]
        path = floodplain['path']
        self.assertEqual(floodplain['portal_exit_xy'], (-15393.56, 9062.19))
        self.assertEqual(path[-2:], [(-15288.94, 8208.61), (-15322.8, 8710.21)])
        self.assertNotIn((4639.08, 4416.47), path)
        for combat_reversal in (
            (-18400.81, 3746.5),
            (-17991.56, 3450.08),
            (-18253.1, 3725.18),
        ):
            self.assertNotIn(combat_reversal, path)

    def test_grand_court_reversal_is_spliced_out(self) -> None:
        route = VABBI / '_5_GrandCourtOfSebelkeh_To_DzagonurBastion.py'
        segments = next(value for key, value in _route_assignments(route).items() if key.endswith('_segments'))
        path = segments[0]['path']
        stitch = path.index((12085.30, 1083.32))
        self.assertEqual(path[stitch + 1], (12395.58, 1748.49))
        self.assertNotIn((12490.26, 1384.33), path)
        self.assertNotIn((11991.52, 1450.88), path)


if __name__ == '__main__':
    unittest.main()
