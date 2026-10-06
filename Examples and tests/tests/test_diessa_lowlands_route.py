import ast
from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[2]
ROUTE_FILE = (
    ROOT
    / "Sources"
    / "aC_Scripts"
    / "PyQuishAI_maps"
    / "Proph_Ascalon"
    / "DiessaLowlands.py"
)
RUNNER_FILE = (
    ROOT
    / "Widgets"
    / "Automation"
    / "Bots"
    / "Vanquish"
    / "Simple_Vanquish.py"
)

BRIDGE_START = (-1554.53, -8095.58)
BRIDGE_END = (-3974.73, -10649.39)
FAR_SIDE_SWEEP = [
    (-3743, -12348),
    (-4465, -11283),
    (-5140, -11862),
    (-5518, -12196),
    (-5168, -11824),
    (-4608, -11235),
]
DETOUR_1 = [
    (-8154.76, 5986.55),
    (-8652.32, 5903.67),
    (-9068.21, 5619.17),
    (-9424.5, 5468.6),
]
TREE_DETOUR = [
    (-10895.51, -2635.5),
    (-11111.68, -2177.75),
    (-11613.83, -2156.07),
    (-11884.95, -2696.36),
    (-11971.09, -3038.46),
]
DETOUR_2 = [
    (-16505.6, -11395.24),
    (-16979.5, -11214.91),
    (-16951.06, -11688.12),
]
TREE_SPLIT = [
    (-11900.66, -11450.16),
    (-11480.64, -11684.6),
    (-11355, -13208),
]
RUBBLE_DETOUR = [
    (-18893, -10169),
    (-17033.37, -10827.06),
    (-16892.25, -12053.03),
    (-19030, -9687),
]
REMOVED_BRIDGE_AUTOPATH_POINTS = {
    (-1545, -8141),
    (-3883, -10860),
    (-5564, -10602),
    (-4080, -10665),
    (-1554, -8099),
    (-926, -7547),
}


def _contains_contiguous(sequence, expected):
    return any(
        sequence[index : index + len(expected)] == expected
        for index in range(len(sequence) - len(expected) + 1)
    )


def _load_parser_functions():
    tree = ast.parse(RUNNER_FILE.read_text(encoding="utf-8"))
    wanted = {"_handle_keyword", "_register_aggro_path", "_get_first_path_coord"}
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(RUNNER_FILE), "exec"), namespace)
    return namespace


class _MoveRecorder:
    def __init__(self):
        self.calls = []

    def FollowAutoPath(self, points):
        self.calls.append(("auto", points))

    def FollowAutoPathAggro(
        self,
        points,
        detection_radius,
        clear_radius,
        on_enemy_detected=None,
    ):
        self.calls.append(
            (
                "aggro",
                points,
                detection_radius,
                clear_radius,
                on_enemy_detected,
            )
        )

    def FollowPath(self, points):
        self.calls.append(("literal", points))


class _StatesRecorder:
    def AddHeader(self, _name):
        pass


class _BotRecorder:
    def __init__(self):
        self.Move = _MoveRecorder()
        self.States = _StatesRecorder()


class DiessaLowlandsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.route = runpy.run_path(str(ROUTE_FILE))["DiessaLowlands"]

    def test_segment_types_and_waypoint_counts_match_the_route_design(self):
        signature = [
            (next(iter(segment)), len(next(iter(segment.values()))))
            for segment in self.route
        ]
        self.assertEqual(
            signature,
            [
                ("path", 12),
                ("continuous_path", 4),
                ("path", 86),
                ("literal_path", 2),
                ("path", 6),
                ("literal_path", 2),
                ("path", 7),
                ("continuous_path", 5),
                ("path", 21),
                ("continuous_path", 3),
                ("path", 3),
                ("continuous_path", 3),
                ("path", 25),
            ],
        )
        self.assertEqual(sum(count for _, count in signature), 179)

    def test_captured_segments_match_the_capture_ledgers(self):
        self.assertEqual(self.route[1]["continuous_path"], DETOUR_1)
        self.assertEqual(self.route[7]["continuous_path"], TREE_DETOUR)
        self.assertEqual(self.route[9]["continuous_path"], DETOUR_2)
        self.assertEqual(self.route[11]["continuous_path"], list(reversed(DETOUR_2)))

    def test_bridge_sequence_preserves_the_far_side_sweep(self):
        self.assertEqual(self.route[3]["literal_path"], [BRIDGE_START, BRIDGE_END])
        self.assertEqual(self.route[4]["path"], FAR_SIDE_SWEEP)
        self.assertEqual(self.route[5]["literal_path"], [BRIDGE_END, BRIDGE_START])
        self.assertTrue(
            REMOVED_BRIDGE_AUTOPATH_POINTS.isdisjoint(
                point
                for segment in self.route
                for key, points in segment.items()
                if key in {"path", "continuous_path"}
                for point in points
            )
        )

    def test_supplied_tree_and_rubble_points_keep_their_existing_anchors(self):
        path_segments = [segment["path"] for segment in self.route if "path" in segment]
        self.assertTrue(any(_contains_contiguous(segment, TREE_SPLIT) for segment in path_segments))
        self.assertTrue(any(_contains_contiguous(segment, RUBBLE_DETOUR) for segment in path_segments))

    def test_upstream_parser_registers_every_route_segment_type(self):
        parser = _load_parser_functions()
        bot = _BotRecorder()
        parser["_register_aggro_path"](
            bot,
            [
                {"path": [(1, 1)]},
                {"continuous_path": [(2, 2), (3, 3)]},
                {"literal_path": [(4, 4), (5, 5)]},
            ],
            detection_radius=1200.0,
            clear_radius=1300.0,
        )
        self.assertEqual(
            bot.Move.calls,
            [
                ("aggro", [(1, 1)], 1200.0, 1300.0, None),
                ("aggro", [(2, 2), (3, 3)], 1200.0, 1300.0, None),
                ("literal", [(4, 4), (5, 5)]),
            ],
        )
        self.assertEqual(
            parser["_get_first_path_coord"](
                [{"literal_path": [BRIDGE_START, BRIDGE_END]}]
            ),
            BRIDGE_START,
        )


if __name__ == "__main__":
    unittest.main()
