"""Execute the real owner and BT nodes; native effects and interaction leaves are doubled."""
from __future__ import annotations

import ast
import builtins
import inspect
import unittest
import uuid
from abc import ABC, abstractmethod
from enum import Enum, auto
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def definitions(path: Path, names: set[str], namespace: dict[str, Any]) -> None:
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    nodes: list[ast.stmt] = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec',
                 flags=__import__('__future__').annotations.compiler_flag), namespace)


class Symbols:
    def __getattr__(self, _name: str) -> str:
        return ''


class FactionEffectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 1000
        self.effects: set[int] = set()
        self.events: list[str] = []
        self.player_id = 7
        self.dispatch_ok = True
        ns: dict[str, Any] = dict(
            ABC=ABC, abstractmethod=abstractmethod, Enum=Enum, auto=auto, uuid=uuid, inspect=inspect,
            ColorPalette=NS(GetColor=lambda *_: None), IconsFontAwesome5=Symbols(),
            Utils=NS(GetBaseTimestamp=lambda: self.now), ConsoleLog=lambda *_a, **_k: None,
            Console=NS(MessageType=Symbols()),
        )
        definitions(ROOT / 'Py4GWCoreLib/py4gwcorelib_src/BehaviorTree.py', {'BehaviorTree'}, ns)
        self.bt = ns['BehaviorTree']
        state = self.bt.NodeState

        def leaf(name: str):
            def action():
                self.events.append(name)
                return state.FAILURE if name == 'dialog' and not self.dispatch_ok else state.SUCCESS
            return self.bt(self.bt.ActionNode(action_fn=action, name=name))

        # Execute the real enum catalog, excluding its injected module-level player read.
        catalog: dict[str, Any] = {'Enum': Enum}
        definitions(ROOT / 'Sources/aC_Scripts/aC_api/Verify_Blessing.py', {'Blessings'}, catalog)
        effect_module = NS(Effects=NS(HasEffect=lambda player, skill: player == 7 and skill in self.effects))
        player_module = NS(Player=NS(GetAgentID=lambda: self.player_id))
        original_import = builtins.__import__

        def importer(name, *args, **kwargs):
            if name == 'Py4GWCoreLib.Effect':
                return effect_module
            if name == 'Py4GWCoreLib.Player':
                return player_module
            if name == 'Sources.aC_Scripts.aC_api.Verify_Blessing':
                return NS(Blessings=catalog['Blessings'])
            return original_import(name, *args, **kwargs)

        ns.update({
            '__builtins__': dict(vars(builtins), __import__=importer),
            'StoreFactionData': lambda **_: leaf('faction'),
            'MoveAndInteract': lambda **_: leaf('approach'),
            'LogMessage': lambda **_: leaf('log'),
            'Wait': lambda *_a, **_k: leaf('settle'),
            'InteractTargetAndSendDialog': lambda **_: leaf('dialog'),
            'Subtree': lambda name, subtree_fn: self.bt(self.bt.SubtreeNode(name=name, subtree_fn=subtree_fn)),
            'Succeeder': lambda **_: self.bt(self.bt.SucceederNode()),
        })
        definitions(ROOT / 'Sources/ApoSource/ApoBottingLib/wrappers.py', {'Node', 'Sequence', 'TakeBlessing'}, ns)
        self.owner = ns['TakeBlessing']

    def advance(self, tree):
        def waiting(node):
            return (isinstance(node, self.bt.WaitUntilNode) and node.last_state == self.bt.NodeState.RUNNING
                    or any(waiting(child) for child in node.get_children()))
        for _ in range(50):
            self.now += 100
            result = tree.tick()
            if result != self.bt.NodeState.RUNNING or waiting(tree.root):
                return result
        self.fail('Owner did not reach terminal state or effect wait in 50 ticks')

    def test_dispatch_does_not_succeed_until_requested_effect_arrives(self):
        for faction, wanted, wrong in [('luxon', 1947, 593), ('kurzick', 593, 1947)]:
            with self.subTest(faction=faction):
                self.effects = {wrong}
                tree = self.owner((1, 2), faction=faction, verify_effect=True)
                self.assertEqual(self.advance(tree), self.bt.NodeState.RUNNING)
                self.assertIn('dialog', self.events)
                self.effects.add(wanted)
                self.now += 100
                self.assertEqual(self.advance(tree), self.bt.NodeState.SUCCESS)

    def test_missing_effect_times_out_and_does_not_redispatch(self):
        tree = self.owner((1, 2), faction='luxon', verify_effect=True)
        self.assertEqual(self.advance(tree), self.bt.NodeState.RUNNING)
        before = self.events.count('dialog')
        self.now += 5001
        self.assertEqual(self.advance(tree), self.bt.NodeState.FAILURE)
        self.assertEqual(self.events.count('dialog'), before)

    def test_reset_restarts_timeout_and_original_sequence(self):
        tree = self.owner((1, 2), faction='luxon', verify_effect=True)
        self.advance(tree)
        tree.reset()
        self.now += 8000
        self.assertEqual(self.advance(tree), self.bt.NodeState.RUNNING)
        self.effects.add(1946)
        self.now += 100
        self.assertEqual(self.advance(tree), self.bt.NodeState.SUCCESS)
        self.assertEqual(self.events.count('approach'), 2)

    def test_default_preserves_dispatch_only_completion(self):
        tree = self.owner((1, 2), faction='luxon')
        self.assertEqual(self.advance(tree), self.bt.NodeState.SUCCESS)

    def test_existing_requested_effect_still_runs_interaction_first(self):
        self.effects.add(1947)
        tree = self.owner((1, 2), faction='luxon', verify_effect=True)
        self.assertEqual(self.advance(tree), self.bt.NodeState.SUCCESS)
        self.assertIn('approach', self.events)
        self.assertIn('dialog', self.events)

    def test_dispatch_failure_is_not_hidden_by_an_existing_effect(self):
        self.dispatch_ok = False
        self.effects.add(1947)
        tree = self.owner((1, 2), faction='luxon', verify_effect=True)
        self.assertEqual(self.advance(tree), self.bt.NodeState.FAILURE)

    def test_invalid_player_does_not_pass(self):
        self.player_id = 0
        self.effects.add(1947)
        tree = self.owner((1, 2), faction='luxon', verify_effect=True)
        self.assertEqual(self.advance(tree), self.bt.NodeState.RUNNING)

    def test_opt_in_rejects_non_faction_and_captured_profiles(self):
        for kwargs in [{}, {'faction': 'norn'}, {'faction': 'luxon', 'captured_blessing': {}}]:
            with self.assertRaisesRegex(ValueError, 'ordinary Luxon or Kurzick'):
                self.owner((1, 2), verify_effect=True, **kwargs)


if __name__ == '__main__':
    unittest.main()
