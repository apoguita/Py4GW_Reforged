"""Real blessing/BT graph; only native NPC observations and action leaves doubled."""
from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

import test_faction_blessing_effect as effect_fixture

ROOT = effect_fixture.ROOT
definitions = effect_fixture.definitions


class BlessingIdentityTests(unittest.TestCase):
    def setUp(self):
        self.fixture = effect_fixture.FactionEffectTests('test_invalid_player_does_not_pass')
        self.fixture.setUp()
        self.ns = self.fixture.namespace
        self.bt = self.fixture.bt
        self.events = []
        self.target = 0
        self.agents = {
            1: NS(xy=(0, 0), encoded='wrong', model=10),
            2: NS(xy=(30, 40), encoded='priest', model=20),
            3: NS(xy=(400, 0), encoded='priest', model=10),
        }

        def leaf(event):
            def action():
                self.events.append(event)
                if event[0] == 'target':
                    self.target = event[1]
                return self.bt.NodeState.SUCCESS
            return self.bt(self.bt.ActionNode(name=event[0], action_fn=action))

        def sequence(*children, name):
            return self.bt(self.bt.SequenceNode(name=name, children=[self.ns['Node'](c) for c in children]))

        def legacy(**kwargs):
            return leaf(('legacy', kwargs))

        self.ns.update({
            'Range': NS(Area=NS(value=322.0)),
            '_POST_MOVEMENT_SETTLE_MS': 100,
            '_final_point': lambda pos: NS(x=pos[0], y=pos[1]),
            'Move': lambda **kwargs: leaf(('move', kwargs)),
            '_wait_until_player_stops_moving': lambda **_: leaf(('stopped',)),
            'Wait': lambda *_a, **_k: leaf(('wait',)),
            'TargetNearestAndInteract': legacy,
            '_pause_heroai_for_action': lambda tree, **_: tree,
            'RoutinesBT': NS(
                Composite=NS(Sequence=sequence),
                Player=NS(ChangeTarget=lambda agent, **_: leaf(('target', agent)),
                          InteractTarget=lambda **_: leaf(('interact',)),
                          SendAutomaticDialog=lambda **_: leaf(('choice',))),
            ),
        })
        agent = NS(IsValid=lambda i: i in self.agents,
                   IsNPC=lambda i: i in self.agents,
                   GetXY=lambda i: self.agents[i].xy,
                   GetEncNameStrByID=lambda i, **_: self.agents[i].encoded,
                   GetModelID=lambda i: self.agents[i].model)
        native_modules = {
            'Py4GWCoreLib.Agent': NS(Agent=agent),
            'Py4GWCoreLib.AgentArray': NS(AgentArray=NS(GetNPCMinipetArray=lambda: list(self.agents))),
            'Py4GWCoreLib.Py4GWcorelib': NS(Utils=NS(Distance=lambda a, b: math.dist(a, b))),
        }
        previous_import = self.ns['__builtins__']['__import__']

        def importer(name, *args, **kwargs):
            return native_modules[name] if name in native_modules else previous_import(name, *args, **kwargs)

        self.ns['__builtins__']['__import__'] = importer
        definitions(ROOT / 'Sources/ApoSource/ApoBottingLib/wrappers.py',
                    {'_target_identity_and_interact', 'MoveAndInteract'}, self.ns)

    def finish(self, tree):
        for _ in range(100):
            self.fixture.now += 100
            state = tree.tick()
            if state != self.bt.NodeState.RUNNING:
                return state
        self.fail('Graph did not terminate within 100 ticks')

    def test_exact_identity_wins_over_nearer_npc_and_model(self):
        tree = self.ns['_target_identity_and_interact']((0, 0), 322, 'priest', 10, 322, False)
        self.assertEqual(self.finish(tree), self.bt.NodeState.SUCCESS)
        self.assertEqual(self.events, [('target', 2), ('interact',)])

    def test_unresolved_encoded_identity_never_falls_back(self):
        tree = self.ns['_target_identity_and_interact']((0, 0), 322, 'absent', 10, 322, False)
        self.assertEqual(self.finish(tree), self.bt.NodeState.FAILURE)
        self.assertEqual(self.events, [])

    def test_model_only_is_constrained_to_coordinate_envelope(self):
        tree = self.ns['_target_identity_and_interact']((0, 0), 322, None, 20, 322, False)
        self.assertEqual(self.finish(tree), self.bt.NodeState.SUCCESS)
        self.assertEqual(self.target, 2)
        self.events.clear()
        tree = self.ns['_target_identity_and_interact']((500, 0), 322, None, 20, 100, False)
        self.assertEqual(self.finish(tree), self.bt.NodeState.FAILURE)
        self.assertEqual(self.events, [])

    def test_legacy_public_movement_keeps_order_and_parameters(self):
        tree = self.ns['MoveAndInteract']((3, 4), target_distance=111, move_tolerance=75,
                                        pause_on_combat=False, avoid_obstacles=False)
        self.assertEqual(self.finish(tree), self.bt.NodeState.SUCCESS)
        self.assertEqual([event[0] for event in self.events], ['move', 'stopped', 'wait', 'legacy'])
        self.assertEqual(self.events[0][1]['avoid_obstacles'], False)
        self.assertEqual(self.events[0][1]['tolerance'], 75)
        self.assertEqual(self.events[-1][1], dict(pos=(3, 4), target_distance=111, log=False))

    def test_faction_owner_targets_identity_before_effect_gate(self):
        tree = self.ns['TakeBlessing']((0, 0), faction='luxon', encoded_identity='priest', verify_effect=True)
        self.assertEqual(self.fixture.advance(tree), self.bt.NodeState.RUNNING)
        self.assertEqual(self.target, 2)
        self.assertIn('dialog', self.fixture.events)
        self.fixture.effects.add(1947)
        self.assertEqual(self.finish(tree), self.bt.NodeState.SUCCESS)

    def test_multibutton_owner_does_not_dispatch_on_missing_identity(self):
        tree = self.ns['TakeBlessing']((0, 0), buttons=[0, 1], encoded_identity='absent')
        self.assertEqual(self.finish(tree), self.bt.NodeState.FAILURE)
        self.assertNotIn('dialog', self.fixture.events)
        self.assertFalse(any(event[0] == 'interact' for event in self.events))

    def test_invalid_identity_inputs_and_captured_conflict_fail_at_entry(self):
        for kwargs in ({'encoded_identity': ''}, {'model_id': 0}, {'identity_search_radius': 0},
                       {'captured_blessing': {}, 'encoded_identity': 'priest'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.ns['TakeBlessing']((0, 0), **kwargs)

    def test_original_argument_prefix_and_effect_option_are_retained(self):
        source = ROOT / 'Sources/ApoSource/ApoBottingLib/wrappers.py'
        tree = ast.parse(source.read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'TakeBlessing')
        self.assertEqual([arg.arg for arg in fn.args.args[:11]], [
            'pos', 'faction', 'buttons', 'blessing_dialog_id', 'bribe_dialog_id',
            'multi_account', 'log', 'pre_dialog_wait_ms', 'post_dialog_wait_ms',
            'avoid_final_approach_obstacles', 'captured_blessing',
        ])
        self.assertEqual([arg.arg for arg in fn.args.kwonlyargs], ['verify_effect'])


if __name__ == '__main__':
    unittest.main()
