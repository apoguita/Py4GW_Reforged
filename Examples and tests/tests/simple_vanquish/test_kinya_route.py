import ast
import runpy
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
ROUTE = ROOT / 'Sources/aC_Scripts/PyQuishAI_maps/Factions_ShingJeaIsland/KinyaProvince.py'
WIDGET = ROOT / 'Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py'
START = (4579.64, 19114.53)
END = (2782.88, 20021.7)
DETOUR = [(-9514.71, 2088.39), (-9979.81, 2279.86), (-10410.56, 2021.61),
          (-10726.22, 1630.81), (-10984.37, 1199.23), (-11230.49, 761.56)]
DETOUR_3 = [(-6473.07, -7109.15), (-6056.33, -7388.28),
            (-5639.77, -7670.8), (-5548.45, -7736.69)]


class KinyaBridgeTests(unittest.TestCase):
    def test_real_registration_preserves_both_crossings_and_reverse_order(self):
        names = {'_register_aggro_path', '_handle_keyword',
                 '_get_first_path_coord', '_build_reversed_path'}
        tree = ast.parse(WIDGET.read_text(encoding='utf-8'))
        selected = [node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = {'_route_state_counter': 0}
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(WIDGET), 'exec'), namespace)
        route = runpy.run_path(str(ROUTE))['KinyaProvince']
        forward = []
        for candidate in (route, namespace['_build_reversed_path'](route)):
            calls = []
            move = SimpleNamespace(
                FollowPath=lambda points, **kw: calls.append(('direct', points)),
                FollowAutoPathAggro=lambda points, *args, **kw: calls.append(('auto', points)),
            )
            namespace['_register_aggro_path'](SimpleNamespace(Move=move), candidate)
            first = namespace['_get_first_path_coord']([[('literal_path', [START, END])]])
            self.assertEqual(first, START)
            direct = [points for kind, points in calls if kind == 'direct']
            excursion = DETOUR + DETOUR[-2::-1]
            expected_direct = [[START, END], [END, START], excursion, DETOUR_3]
            if forward:
                expected_direct = [points[::-1] for points in expected_direct[::-1]]
            self.assertEqual(direct, expected_direct)
            self.assertEqual(len(calls), 9)
            flat = [point for _, points in calls for point in points]
            self.assertFalse(set(flat) & {(4585.0, 19109.0), (2704.0, 19997.0), (4796.0, 18807.0)})
            self.assertFalse(set(flat) & {(-11071.0, 1455.0), (-10260.0, 1986.0)})
            self.assertFalse(set(flat) & {(-6666.0, -7450.0), (-5110.0, -7830.0)})
            if not forward:
                forward = flat
            else:
                self.assertEqual(flat, forward[::-1])
        self.assertIn([(7494.0, 18765.0), START, END, (1532.0, 13811.0)],
                      [forward[i:i + 4] for i in range(len(forward))])
        expected = [(-8710.0, 2068.0), *DETOUR, *DETOUR[-2::-1], (-8830.0, 1889.0)]
        start = forward.index(expected[0])
        self.assertEqual(forward[start:start + len(expected)], expected)
        expected = [(-4990.0, -3556.0), *DETOUR_3, (-4629.0, -11408.0)]
        start = forward.index(expected[0])
        self.assertEqual(forward[start:start + len(expected)], expected)
        self.assertTrue(all(forward.count(point) == 1 for point in DETOUR_3))
        print('Kinya: bridges, detours, handoffs and reverse PASS')


if __name__ == '__main__':
    unittest.main()
