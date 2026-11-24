"""Offline route registration and cartography lifecycle checks; no game imports."""
import ast
import math
import time
import types
import unittest
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / 'Sources/aC_Scripts/PyQuishAI_maps/NF_Istan/IssnurIsles.py'
WIDGET = ROOT / 'Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py'
OWNER = ROOT / 'Py4GWCoreLib/routines_src/behaviourtrees_src/cartography.py'


def definitions(path, names, scope):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), scope)
    return scope


class Tree:
    class NodeState(Enum):
        RUNNING = 1
        SUCCESS = 2
        FAILURE = 3

    class Node:
        def __init__(self, name):
            self.name = name

        def reset(self):
            pass

    def __init__(self, root):
        self.root = root


class IssnurRouteTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(ROUTE.read_text(encoding='utf-8'))
        self.route = ast.literal_eval(tree.body[0].value)

    def test_registered_forward_and_reverse_preserve_bridge_and_boat(self):
        calls = []
        scope = {'Botting': object, 'Player': object}
        names = {'_handle_keyword', '_register_aggro_path', '_build_reversed_path', '_get_first_path_coord'}
        definitions(WIDGET, names, scope)
        move = types.SimpleNamespace(
            FollowAutoPathAggro=lambda points, *a, **kw: calls.append(('aggro', list(points))),
            FollowPath=lambda points: calls.append(('literal', list(points))))
        bot = types.SimpleNamespace(Move=move,
            Wait=types.SimpleNamespace(UntilOutOfCombat=lambda: None),
            UI=types.SimpleNamespace(PrintMessageToConsole=lambda *a: None),
            States=types.SimpleNamespace(AddCustomState=lambda *a: None))
        scope['BotSettings'] = types.SimpleNamespace(BOT_NAME='test')
        scope['_register_aggro_path'](bot, self.route)
        literal = [p for kind, points in calls if kind == 'literal' for p in points]
        self.assertEqual(len(literal), 10)
        self.assertEqual(literal[0], (27258.85, -4187.8))
        self.assertEqual(literal[5], (27844.59, -6115.37))
        self.assertEqual(literal[-1], (27258.31, -4270.65))
        forward = [p for kind, points in calls for p in points]
        i = forward.index((2155.3, -12252.13))
        self.assertEqual(forward[i + 1], (2570.56, -10996.04))
        calls.clear()
        scope['_register_aggro_path'](bot, scope['_build_reversed_path'](self.route))
        self.assertEqual([p for kind, points in calls for p in points], forward[::-1])

    def test_upstream_blessing_shape_and_no_local_aggro_features(self):
        blessings = [e['bless'] for e in self.route if 'bless' in e]
        self.assertEqual(blessings, [(-15434.66, 10790.87), (-10559.35, -4338.26),
                                     (7864.06, -4554.69), (-818.55, 7885.4)])
        hold = next(e['cartography_hold'] for e in self.route if 'cartography_hold' in e)
        self.assertEqual(hold['direction'], 'south')
        self.assertEqual(hold['xy'], (27844.59, -6115.37))
        for source in [ROUTE, WIDGET, OWNER]:
            text = source.read_text(encoding='utf-8')
            for forbidden in ['tight_path', 'no_contact_timeout_ms', 'Issnur Movement Checkpoint', 'CapturedBlessingRunner']:
                self.assertNotIn(forbidden, text)

    def owner(self):
        now = [0.0]
        map_id = [486]
        moves = []
        scope = {'math': math, 'time': types.SimpleNamespace(monotonic=lambda: now[0]),
                 'BehaviorTree': Tree,
                 'Map': types.SimpleNamespace(IsExplorable=lambda: True, GetMapID=lambda: map_id[0]),
                 'Player': types.SimpleNamespace(GetXY=lambda: (27844.59, -6115.37),
                                                Move=lambda *xy: moves.append(xy))}
        definitions(OWNER, {'_CartographyHoldNode', 'HoldCartographyPoint'}, scope)
        tree = scope['HoldCartographyPoint']((27844.59, -6115.37), direction='south', hold_seconds=3.0)
        return tree.root, now, map_id, moves

    def test_exact_south_push_three_seconds_and_stop(self):
        node, now, map_id, moves = self.owner()
        self.assertEqual(node._tick_impl(), Tree.NodeState.RUNNING)
        self.assertEqual(moves, [(27844.59, -6865.37)])
        now[0] = 2.99
        self.assertEqual(node._tick_impl(), Tree.NodeState.RUNNING)
        now[0] = 3.0
        self.assertEqual(node._tick_impl(), Tree.NodeState.SUCCESS)
        self.assertEqual(moves[-1], (27844.59, -6115.37))

    def test_cancel_restart_and_map_change(self):
        node, now, map_id, moves = self.owner()
        node._tick_impl()
        node.reset()
        self.assertEqual(moves[-1], (27844.59, -6115.37))
        now[0] = 10.0
        self.assertEqual(node._tick_impl(), Tree.NodeState.RUNNING)
        count = len(moves)
        map_id[0] = 487
        self.assertEqual(node._tick_impl(), Tree.NodeState.FAILURE)
        node.reset()
        self.assertEqual(len(moves), count)


if __name__ == '__main__':
    unittest.main()
