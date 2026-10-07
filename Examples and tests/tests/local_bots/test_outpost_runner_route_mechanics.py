from __future__ import annotations

import ast
import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MECHANICS = ROOT / "Sources" / "aC_Scripts" / "OutpostRunner" / "route_mechanics.py"
RUNNER = ROOT / "Widgets" / "Automation" / "Bots" / "Runners" / "OutpostRunnerV2.py"
FIGHTER = ROOT / "Widgets" / "Automation" / "Bots" / "Runners" / "OutpostFighter.py"
MAPS = ROOT / "Sources" / "aC_Scripts" / "OutpostRunner" / "maps"
JADE_SEA = MAPS / "Cantha - The Jade Sea"
ECHOVALD = MAPS / "Cantha - Echovald Forest"
SHING_JEA = MAPS / "Cantha - Shing Jea Island"
VABBI = MAPS / "NF - Vabbi Tour"
TORMENT = MAPS / "NF - Realm of Torment"
KOURNA = MAPS / "NF - Kourna"
DESOLATION = MAPS / "NF - Desolation"

ETERNAL_GROVE_ROUTE = ECHOVALD / "_9_VasburgArmory_To_TheEternalGrove.py"
TSUMEI_ROUTE = SHING_JEA / "_1_ShingJeaMonastery_To_TsumeiVillage.py"
RANKOR_DWC_ROUTE = MAPS / "Tyria - Beacon's Perch To Droknars Forge" / "_5_CampRankor_To_DeldrimorWarCamp.py"
ELONA_SEEKERS_ROUTE = MAPS / "Tyria - Desert Outposts" / "_4_ElonaReach_to_SeekersPassage.py"
HARVEST_ROUTE = JADE_SEA / "_7_HarvestTemple_To_UnwakingWatersKurzick.py"
BASALT_ROUTE = DESOLATION / "_1_BonePalace_To_BasaltGrotto.py"
LAIR_ROUTE = DESOLATION / "_2_BonePalace_To_LairOfTheForgotten.py"

CANHTA_ROUTE_EXPECTATIONS = {
    JADE_SEA / "_1_Cavalon_To_BreakerHollow.py": "ROUTE-20260905-115546-323",
    JADE_SEA / "_2_BreakerHollow_To_AspenwoodGateLuxon.py": "ROUTE-20260905-120012-484",
    JADE_SEA / "_3_GyalaHatchery_To_EredonTerrace.py": "ROUTE-20260910-172546-445",
    JADE_SEA / "_4_EredonTerrace_To_BaiPaasuReach.py": "ROUTE-20260910-172852-363",
    JADE_SEA / "_5_UnwakingWatersLuxon_To_SeafarersRest.py": "ROUTE-20260910-175318-524",
    JADE_SEA / "_6_SeafarersRest_To_AuriosMines.py": "ROUTE-20260910-175542-883",
    JADE_SEA / "_8_Cavalon_To_JadeFlatsLuxon.py": "ROUTE-20260910-181100-432",
    ECHOVALD / "_1_HouseZuHeltzer_To_SaintAnjekasShrine.py": "ROUTE-20260910-173207-900",
    ECHOVALD / "_2_SaintAnjekasShrine_To_LutgardisConservatory.py": "ROUTE-20260910-173531-803",
    ECHOVALD / "_3_SaintAnjekasShrine_To_BrauerAcademy.py": "ROUTE-20260910-173849-995",
    ECHOVALD / "_4_UnwakingWatersKurzick_To_VasburgArmory.py": "ROUTE-20260910-174117-968",
    ECHOVALD / "_5_UnwakingWatersKurzick_To_DurheimArchives.py": "ROUTE-20260910-174532-032",
    ECHOVALD / "_6_VasburgArmory_To_AmatzBasin.py": "ROUTE-20260910-174813-450",
    ECHOVALD / "_7_HouseZuHeltzer_To_AspenwoodGateKurzick.py": "ROUTE-20260910-213119-662",
    ECHOVALD / "_8_LutgardisConservatory_To_JadeFlatsKurzick.py": "ROUTE-20260910-214257-099",
    ETERNAL_GROVE_ROUTE: "ROUTE-20260914-211649-677",
    TSUMEI_ROUTE: "ROUTE-20260910-181601-806",
}

NIGHTFALL_ROUTE_EXPECTATIONS = {
    VABBI / "_3_honurhill_to_dashavestibulepostcampaign.py": "ROUTE-20260910-192540-375",
    VABBI / "_4_HonurHill_To_YahnurMarket.py": "ROUTE-20260910-202958-660",
    VABBI / "_5_GrandCourtOfSebelkeh_To_DzagonurBastion.py": "ROUTE-20260910-203705-316",
    TORMENT / "_1_gateoftorment_to_gateofthenightfallenlands.py": "ROUTE-20260910-193010-552",
    TORMENT / "_2_gateoftorment_to_theshadownexus.py": "ROUTE-20260910-193856-605",
    KOURNA / "_1_pogahnpassage_to_camphojanu.py": "ROUTE-20260910-195056-356",
    KOURNA / "_2_NunduBay_To_DajkahInlet.py": "ROUTE-20260910-202654-187",
    KOURNA / "_3_KodonurCrossroads_To_RilohnRefuge.py": "ROUTE-20260911-224924-163",
}


def _route_assignments(route: Path) -> dict[str, object]:
    tree = ast.parse(route.read_text(encoding="utf-8"))
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
        if target.id.endswith(("_ids", "_outpost_path", "_segments")):
            result[target.id] = ast.literal_eval(ReplaceMapLookups().visit(node.value))
    return result


def _load_mechanics():
    spec = importlib.util.spec_from_file_location("test_route_mechanics_runtime", MECHANICS)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SharedRouteMechanicsTests(unittest.TestCase):
    @staticmethod
    def _bot():
        calls: list[tuple[str, object, object]] = []

        class Move:
            @staticmethod
            def FollowPath(points, step_name=""):
                calls.append(("direct", list(points), step_name))

            @staticmethod
            def FollowAutoPath(points, step_name="", resume_key=None):
                calls.append(("path", list(points), (step_name, resume_key)))

            @staticmethod
            def FollowPathAndExitMap(
                points,
                target_map_id=0,
                step_name="",
                resume_key=None,
            ):
                calls.append(("portal", list(points), (target_map_id, step_name, resume_key)))

        class Interact:
            @staticmethod
            def WithNpcAtXY(x, y, step_name=""):
                calls.append(("npc", (x, y), step_name))

            @staticmethod
            def WithGadgetAtXY(x, y, step_name=""):
                calls.append(("gadget", (x, y), step_name))

        class Wait:
            @staticmethod
            def UntilCondition(condition, duration=1000):
                calls.append(("condition", condition, duration))

            @staticmethod
            def ForMapLoad(target_map_id=0, target_map_name="", timeout_ms=10000):
                calls.append(("map_load", target_map_id, timeout_ms))

        class Party:
            @staticmethod
            def FlagAllHeroes(x, y):
                calls.append(("flag", (x, y), None))

            @staticmethod
            def UnflagAllHeroes():
                calls.append(("unflag", None, None))

        class States:
            @staticmethod
            def AddCustomState(execute_fn, name):
                calls.append(("custom", execute_fn, name))

        return (
            types.SimpleNamespace(
                Move=Move,
                Interact=Interact,
                Wait=Wait,
                Party=Party,
                States=States,
            ),
            calls,
        )

    def test_portal_extension_uses_450_units_and_captured_heading(self) -> None:
        mechanics = _load_mechanics()
        extended = mechanics.extended_portal_path([(0.0, 0.0), (300.0, 400.0)])
        self.assertEqual(extended[:2], [(0.0, 0.0), (300.0, 400.0)])
        self.assertAlmostEqual(math.dist(extended[-2], extended[-1]), 450.0)
        self.assertEqual(extended[-1], (570.0, 760.0))

    def test_unknown_single_point_heading_is_not_invented(self) -> None:
        mechanics = _load_mechanics()
        self.assertEqual(
            mechanics.extended_portal_path([(300.0, 400.0)]),
            [(300.0, 400.0)],
        )

    def test_outpost_departure_uses_public_movement_owner(self) -> None:
        mechanics = _load_mechanics()
        bot, calls = self._bot()
        mechanics.register_outpost_departure(
            bot,
            [(0.0, 0.0), (100.0, 0.0)],
            target_map_id=2,
            step_name="Leave outpost",
        )
        self.assertEqual(calls, [("portal", [(0.0, 0.0), (100.0, 0.0), (550.0, 0.0)], (2, "Leave outpost", None))])

    def test_transition_segment_uses_public_owner_and_resume_key(self) -> None:
        mechanics = _load_mechanics()
        bot, calls = self._bot()
        owns_map_travel = mechanics.register_botting_segment(
            bot,
            "Route",
            2,
            {"map_id": 1, "path": [(0.0, 0.0), (100.0, 0.0)]},
            target_map_id=2,
            resume_key_prefix="outpost-fighter:4:1",
        )
        self.assertTrue(owns_map_travel)
        self.assertEqual(calls[0][0], "portal")
        self.assertEqual(calls[0][1][-1], (550.0, 0.0))
        self.assertEqual(
            calls[0][2],
            (2, "Route segment 3 step 1", "outpost-fighter:4:1:segment:2:step:1"),
        )

    def test_direct_bridge_path_does_not_use_autopath(self) -> None:
        mechanics = _load_mechanics()
        bot, calls = self._bot()
        owns_map_travel = mechanics.register_botting_segment(
            bot,
            "Bridge route",
            0,
            {
                "map_id": 1,
                "steps": [
                    {
                        "type": "direct_path",
                        "name": "Bridge Start to Bridge End",
                        "path": [(10.0, 20.0), (30.0, 40.0)],
                    }
                ],
            },
        )
        self.assertFalse(owns_map_travel)
        self.assertEqual(
            calls,
            [("direct", [(10.0, 20.0), (30.0, 40.0)], "Bridge Start to Bridge End")],
        )

    def test_unknown_steps_still_fail_closed_at_route_boundary(self) -> None:
        mechanics = _load_mechanics()
        bot, _calls = self._bot()
        with self.assertRaisesRegex(ValueError, "registered public Py4GWCoreLib owners"):
            mechanics.register_botting_segment(
                bot,
                "Unsupported route",
                0,
                {"map_id": 1, "steps": [{"type": "invented_interaction"}]},
            )

    def test_blessing_composes_public_botting_owners(self) -> None:
        mechanics = _load_mechanics()
        bot, calls = self._bot()
        owns_map_travel = mechanics.register_botting_segment(
            bot,
            "Blessing route",
            0,
            {
                "map_id": 1,
                "steps": [
                    {
                        "type": "blessing",
                        "name": "Margonite Battle",
                        "target_xy": (10.0, 20.0),
                        "player_approach_xy": (8.0, 18.0),
                        "visible_button": 1,
                        "effect_ids": (1849, 2036, 2037),
                    }
                ],
            },
        )
        self.assertFalse(owns_map_travel)
        self.assertEqual([call[0] for call in calls], ["path", "npc", "custom", "condition"])
        selected_buttons: list[tuple[int, bool]] = []

        class YieldPlayer:
            @staticmethod
            def SendAutomaticDialog(button_number, log=False):
                selected_buttons.append((button_number, log))
                yield

        fake_core = types.SimpleNamespace(
            Routines=types.SimpleNamespace(
                Yield=types.SimpleNamespace(Player=YieldPlayer),
            )
        )
        previous_core = sys.modules.get("Py4GWCoreLib")
        sys.modules["Py4GWCoreLib"] = fake_core
        try:
            dialog_state = calls[2][1]
            generator = dialog_state()
            next(generator)
            with self.assertRaises(StopIteration):
                next(generator)
        finally:
            if previous_core is None:
                del sys.modules["Py4GWCoreLib"]
            else:
                sys.modules["Py4GWCoreLib"] = previous_core
        self.assertEqual(selected_buttons, [(0, True)])

    def test_junundu_composes_party_gadget_and_postcondition_owners(self) -> None:
        mechanics = _load_mechanics()
        bot, calls = self._bot()
        mechanics.register_botting_segment(
            bot,
            "Junundu route",
            0,
            {
                "map_id": 1,
                "steps": [
                    {
                        "type": "enter_junundu",
                        "name": "Enter Junundu party",
                        "target_xy": (10.0, 20.0),
                        "player_approach_xy": (9.0, 19.0),
                        "party_regroup_xy": (10.0, 20.0),
                    }
                ],
            },
        )
        self.assertEqual(
            [call[0] for call in calls],
            ["path", "flag", "condition", "gadget", "condition", "unflag"],
        )

    def test_dialog_sequence_uses_existing_visible_choice_owner_and_map_wait(self) -> None:
        mechanics = _load_mechanics()
        bot, calls = self._bot()
        owns_map_travel = mechanics.register_botting_segment(
            bot,
            "Dedrick route",
            0,
            {
                "map_id": 1,
                "steps": [
                    {
                        "type": "npc_dialog_sequence",
                        "name": "Gatekeeper Dedrick transfer",
                        "target_xy": (10.0, 20.0),
                        "player_approach_xy": (9.0, 19.0),
                        "visible_button_labels": ("One", "Two", "Three"),
                        "target_map_id": 2,
                    }
                ],
            },
        )
        self.assertTrue(owns_map_travel)
        self.assertEqual(
            [call[0] for call in calls],
            ["path", "npc", "custom", "custom", "custom", "map_load"],
        )

    def test_route_helper_contains_no_private_or_parallel_interaction_owner(self) -> None:
        source = MECHANICS.read_text(encoding="utf-8")
        self.assertNotIn("._coro_", source)
        self.assertNotIn("reliable_interaction", source)
        self.assertNotIn("_RouteInteractionRuntime", source)
        self.assertIn("bot.Move.FollowPathAndExitMap", source)
        self.assertIn("bot.Interact.WithNpcAtXY", source)
        self.assertIn("bot.Interact.WithGadgetAtXY", source)
        self.assertIn("Routines.Yield.Player.SendAutomaticDialog", source)

    def test_both_consumers_bind_shared_public_route_mechanics(self) -> None:
        for path in (RUNNER, FIGHTER):
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn("importlib.reload(_route_mechanics)", source)
                self.assertIn(
                    "register_outpost_departure = _route_mechanics.register_outpost_departure",
                    source,
                )
                self.assertIn("register_botting_segment", source)


class CapturedRouteTests(unittest.TestCase):
    def test_interaction_routes_are_restored_with_captured_provenance(self) -> None:
        expected = {
            HARVEST_ROUTE: "ROUTE-20260910-180114-736",
            BASALT_ROUTE: "ROUTE-20260902-140340-849",
            LAIR_ROUTE: "ROUTE-20260910-151459-766",
        }
        for route, capture_id in expected.items():
            with self.subTest(route=route.name):
                data = _route_assignments(route)
                ids = next(value for key, value in data.items() if key.endswith("_ids"))
                self.assertEqual(ids["source_route_id"], capture_id)
                source = route.read_text(encoding="utf-8")
                self.assertNotIn("agent_id_runtime_only", source)
                self.assertNotIn("captured_at", source)

        harvest_steps = _route_assignments(HARVEST_ROUTE)["_7_harvesttemple_to_unwakingwaterskurzick_segments"][0][
            "steps"
        ]
        self.assertEqual([step["type"] for step in harvest_steps], ["path", "npc_dialog_sequence"])
        for route in (BASALT_ROUTE, LAIR_ROUTE):
            segments = next(value for key, value in _route_assignments(route).items() if key.endswith("_segments"))
            step_types = [step["type"] for segment in segments for step in segment.get("steps", [])]
            self.assertIn("blessing", step_types)
            self.assertIn("enter_junundu", step_types)

    def test_all_retained_captured_routes_preserve_source_and_destination(self) -> None:
        expected = {**CANHTA_ROUTE_EXPECTATIONS, **NIGHTFALL_ROUTE_EXPECTATIONS}
        self.assertEqual(len(expected), 25)
        for route, capture_id in expected.items():
            with self.subTest(route=route.name):
                data = _route_assignments(route)
                ids = next(value for key, value in data.items() if key.endswith("_ids"))
                segments = next(value for key, value in data.items() if key.endswith("_segments"))
                self.assertEqual(ids["source_route_id"], capture_id)
                self.assertTrue(segments)
                final = segments[-1]
                self.assertEqual(final.get("path", final.get("steps")), [])
                source = route.read_text(encoding="utf-8")
                self.assertNotIn("agent_id_runtime_only", source)
                self.assertNotIn("captured_at", source)
                self.assertNotIn("npc_dialog_sequence", source)
                self.assertNotIn("enter_junundu", source)
                self.assertNotIn("blessing", source)

    def test_retained_route_paths_have_no_cross_map_coordinate_jump(self) -> None:
        for route in (*CANHTA_ROUTE_EXPECTATIONS, *NIGHTFALL_ROUTE_EXPECTATIONS):
            segments = next(value for key, value in _route_assignments(route).items() if key.endswith("_segments"))
            for segment_index, segment in enumerate(segments[:-1]):
                paths = [segment.get("path", [])]
                paths.extend(step.get("path", []) for step in segment.get("steps", []))
                for path in paths:
                    for left, right in zip(path, path[1:]):
                        with self.subTest(route=route.name, segment=segment_index):
                            self.assertLessEqual(math.dist(left, right), 2_000.0)

    def test_eternal_grove_stitch_and_direct_bridge_are_preserved(self) -> None:
        data = _route_assignments(ETERNAL_GROVE_ROUTE)
        segments = next(value for key, value in data.items() if key.endswith("_segments"))
        steps = segments[0]["steps"]
        self.assertEqual([step["type"] for step in steps], ["path", "direct_path", "path"])
        self.assertEqual(steps[1]["path"], [(1352.85, 11706.08), (-11.16, 10773.75)])
        retained = [point for step in steps for point in step.get("path", [])]
        for removed in ((18568.48, 2017.34), (14692.08, 1762.97), (14551.83, 1282.04)):
            self.assertNotIn(removed, retained)

    def test_tsumei_uses_captured_angled_portal_exit(self) -> None:
        segments = next(value for key, value in _route_assignments(TSUMEI_ROUTE).items() if key.endswith("_segments"))
        self.assertEqual(segments[0]["portal_exit_xy"], (-4717.07, -13301.82))
        self.assertEqual(segments[-1]["path"], [])

    def test_camp_rankor_replacement_splice_is_preserved(self) -> None:
        data = _route_assignments(RANKOR_DWC_ROUTE)
        ids = next(value for key, value in data.items() if key.endswith("_ids"))
        segments = next(value for key, value in data.items() if key.endswith("_segments"))
        path = segments[0]["path"]
        self.assertEqual(ids["replacement_route_id"], "ROUTE-20260911-202732-875")
        self.assertIn((335.99, -28006.2), path)
        self.assertNotIn((-411.82, -26334.12), path)

    def test_elona_seekers_smoothed_capture_is_preserved(self) -> None:
        data = _route_assignments(ELONA_SEEKERS_ROUTE)
        ids = next(value for key, value in data.items() if key.endswith("_ids"))
        segments = next(value for key, value in data.items() if key.endswith("_segments"))
        self.assertEqual(ids["replacement_route_id"], "ROUTE-20260911-210807-345")
        self.assertEqual(segments[1]["path"][-1], (-16318.77, 7771.75))


if __name__ == "__main__":
    unittest.main()
