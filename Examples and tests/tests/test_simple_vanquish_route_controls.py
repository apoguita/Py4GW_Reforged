from __future__ import annotations

import ast
from pathlib import Path
import types
import unittest


ROOT = Path(__file__).resolve().parents[2]
WIDGET = ROOT / "Widgets/Automation/Bots/Vanquish/Simple_Vanquish.py"


class SimpleVanquishRouteControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WIDGET.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def _function(self, name: str) -> ast.FunctionDef:
        return next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef) and node.name == name
        )

    def _boundary_runtime(self, *, saved_pause=False, fail_hold=False):
        events = []

        class FakeProperties:
            @staticmethod
            def Get(_name, _account):
                return saved_pause

            @staticmethod
            def ApplyNow(_name, _account, value):
                events.append(("pause", value))

        class FakeBot:
            Properties = FakeProperties()

            @staticmethod
            def Stop():
                events.append(("bot_stop",))

        class FakePlayer:
            @staticmethod
            def GetAgentID():
                return 1

            @staticmethod
            def GetXY():
                return (10.0, 20.0)

            @staticmethod
            def Move(x, y):
                events.append(("move", x, y))

        class FakeYield:
            @staticmethod
            def wait(milliseconds):
                events.append(("wait", milliseconds))
                yield milliseconds
                if fail_hold:
                    raise RuntimeError("hold failed")

        function = self._function("_face_boundary_and_hold_location")
        module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
        namespace = {
            "Botting": object,
            "Player": FakePlayer,
            "Routines": types.SimpleNamespace(Yield=FakeYield),
            "Utils": types.SimpleNamespace(
                Distance=lambda first, second: 0.0 if first == (10.0, 20.0) else 1.0
            ),
            "time": types.SimpleNamespace(monotonic=lambda: 0.0),
        }
        exec(compile(module, str(WIDGET), "exec"), namespace)
        generator = namespace["_face_boundary_and_hold_location"](
            FakeBot(),
            {
                "name": "test",
                "xy": (10.0, 20.0),
                "facing_move_xy": (0.0, 20.0),
                "hold_ms": 1250,
            },
        )
        return generator, events

    def test_boundary_hold_uses_collision_move_and_restores_hero_pause(self):
        function = self._function("_face_boundary_and_hold_location")
        source = ast.unparse(function)
        self.assertIn("Player.Move(facing_move_xy[0], facing_move_xy[1])", source)
        self.assertIn("yield from Routines.Yield.wait(hold_ms)", source)
        self.assertIn("Player.Move(current_xy[0], current_xy[1])", source)
        self.assertIn(
            "bot.Properties.ApplyNow('hero_ai_paused', 'active', saved_pause)",
            source,
        )
        self.assertNotIn("TurnLeft", source)
        self.assertNotIn("TurnRight", source)

    def test_boundary_hold_normal_completion_releases_move_then_restores_pause(self):
        generator, events = self._boundary_runtime(saved_pause=False)
        self.assertEqual(next(generator), 1250)
        with self.assertRaises(StopIteration) as completed:
            next(generator)
        self.assertTrue(completed.exception.value)
        self.assertEqual(
            events,
            [
                ("pause", True),
                ("move", 0.0, 20.0),
                ("wait", 1250),
                ("move", 10.0, 20.0),
                ("pause", False),
            ],
        )

    def test_boundary_hold_failure_releases_move_restores_pause_and_stops_bot(self):
        generator, events = self._boundary_runtime(saved_pause=True, fail_hold=True)
        self.assertEqual(next(generator), 1250)
        with self.assertRaisesRegex(RuntimeError, "hold failed"):
            next(generator)
        self.assertEqual(
            events[-3:],
            [("move", 10.0, 20.0), ("pause", True), ("bot_stop",)],
        )

    def test_boundary_hold_generator_close_releases_move_and_restores_pause(self):
        generator, events = self._boundary_runtime(saved_pause=False)
        self.assertEqual(next(generator), 1250)
        generator.close()
        self.assertEqual(
            events[-2:],
            [("move", 10.0, 20.0), ("pause", False)],
        )
        self.assertNotIn(("bot_stop",), events)

    def test_route_keywords_dispatch_boundary_hold_and_status_checkpoint(self):
        source = ast.unparse(self._function("_handle_keyword"))
        self.assertIn("key == 'boundary_face_hold'", source)
        self.assertIn("_face_boundary_and_hold_location(bot, data)", source)
        self.assertIn("key == 'vanquish_status'", source)
        self.assertIn("_log_vanquish_status(label)", source)

    def test_status_checkpoint_reads_both_live_vanquish_counters(self):
        source = ast.unparse(self._function("_log_vanquish_status"))
        self.assertIn("Map.GetFoesKilled()", source)
        self.assertIn("Map.GetFoesToKill()", source)
        self.assertIn("VQ_CLEANUP_CHECKPOINT", source)

    def test_reverse_cleanup_count_is_loaded_clamped_and_applied(self):
        queue_class = next(
            node
            for node in self.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "QueuedVanquish"
        )
        queue_source = ast.unparse(queue_class)
        load_source = ast.unparse(self._function("_load_vanquish_data"))
        build_source = ast.unparse(self._function("bot_routine"))

        self.assertIn("reverse_cleanup_passes=2", queue_source)
        self.assertIn("max(0, min(2, int(reverse_cleanup_passes)))", queue_source)
        self.assertIn("ids.get('reverse_cleanup_passes', 2)", load_source)
        self.assertIn("reverse_cleanup_passes=reverse_cleanup_passes", load_source)
        self.assertGreaterEqual(
            build_source.count("vq.reverse_cleanup_passes >= 1"),
            2,
        )
        self.assertGreaterEqual(
            build_source.count("vq.reverse_cleanup_passes >= 2"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
