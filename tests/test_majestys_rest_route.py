"""Offline contract checks for the Majesty's Rest route."""
import ast
import types
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "Sources/aC_Scripts/PyQuishAI_maps/Proph_Maguuma/MajestysRest.py"
WIDGET = ROOT / "Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py"

BRIDGE_START = (14500.48, -1683.47)
BRIDGE_MIDDLE = (14130.67, -773.96)
BRIDGE_END = (13935.59, -144.96)
UNSAFE_BRIDGE_POINTS = {(16252, -1572), (17470, -1816), (14470, -1522), (13929, -179)}


def assignments(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }


def definitions(path: Path, names: set[str], scope: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected: list[ast.stmt] = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), scope)
    return scope


class MajestysRestRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = assignments(ROUTE)
        cls.route = cls.values["MajestysRest"]

    def test_registration_metadata_and_transit_endpoints(self):
        self.assertNotIn("CursedLands_ids", self.values)
        self.assertEqual(
            self.values["MajestysRest_ids"],
            {"outpost_id": 138, "map_id": 60, "transit_id": 18, "transit_id2": 17},
        )
        self.assertEqual(self.values["MajestysRest_outpost_path"][0], (-5199, 16327))
        self.assertEqual(self.values["MajestysRest_transit_path"][0], (-6302, 14890))
        self.assertEqual(self.values["MajestysRest_transit_path"][-1], (-20274, 1812))
        self.assertEqual(self.values["MajestysRest_transit_path2"][0], (16716, 2887))
        self.assertEqual(self.values["MajestysRest_transit_path2"][-1], (-20190, 3714))

    def test_bridge_uses_only_supplied_three_point_literal_crossings(self):
        literal_paths = [value for segment in self.route for key, value in segment if key == "literal_path"]
        self.assertEqual(
            literal_paths,
            [
                [BRIDGE_START, BRIDGE_MIDDLE, BRIDGE_END],
                [BRIDGE_END, BRIDGE_MIDDLE, BRIDGE_START],
            ],
        )
        all_points = {
            point
            for segment in self.route
            for _key, value in segment
            if isinstance(value, list)
            for point in value
        }
        self.assertTrue(UNSAFE_BRIDGE_POINTS.isdisjoint(all_points))

    def test_literal_bridge_dispatch_bypasses_aggro_autopath(self):
        calls = []
        scope: dict[str, Any] = {"Botting": object, "Player": object}
        definitions(WIDGET, {"_handle_keyword", "_register_aggro_path"}, scope)
        bot = types.SimpleNamespace(
            Move=types.SimpleNamespace(
                FollowAutoPathAggro=lambda points, *args, **kwargs: calls.append(("aggro", list(points))),
                FollowPath=lambda points: calls.append(("literal", list(points))),
            ),
            States=types.SimpleNamespace(AddHeader=lambda *_args: None),
        )

        scope["_register_aggro_path"](bot, self.route)

        self.assertEqual(
            [points for kind, points in calls if kind == "literal"],
            [
                [BRIDGE_START, BRIDGE_MIDDLE, BRIDGE_END],
                [BRIDGE_END, BRIDGE_MIDDLE, BRIDGE_START],
            ],
        )
        aggro_points = [point for kind, points in calls if kind == "aggro" for point in points]
        self.assertNotIn(BRIDGE_MIDDLE, aggro_points)

    def test_reverse_builder_preserves_exact_bridge_geometry(self):
        scope = {}
        definitions(WIDGET, {"_build_reversed_path"}, scope)
        reversed_route = scope["_build_reversed_path"](self.route)
        literal_paths = [
            value for segment in reversed_route for key, value in segment if key == "literal_path"
        ]
        self.assertEqual(
            literal_paths,
            [
                [BRIDGE_START, BRIDGE_MIDDLE, BRIDGE_END],
                [BRIDGE_END, BRIDGE_MIDDLE, BRIDGE_START],
            ],
        )

    def test_recorded_replacements_are_present(self):
        transit_one = self.values["MajestysRest_transit_path"]
        transit_two = self.values["MajestysRest_transit_path2"]
        self.assertIn((-13241.43, 15025.76), transit_one)
        self.assertIn((-17748.03, 8043.34), transit_one)
        self.assertNotIn((-16718, 13517), transit_one)
        self.assertIn((-2863.03, 9229.10), transit_two)
        self.assertIn((-19175.29, 3660.37), transit_two)
        self.assertNotIn((-7004, 10342), transit_two)


if __name__ == "__main__":
    unittest.main()
