from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
WRAPPERS = ROOT / "Sources/ApoSource/ApoBottingLib/wrappers.py"
CAPTURED = ROOT / "Sources/aC_Scripts/aC_api/Captured_Blessing.py"


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


class TakeBlessingStructureTests(unittest.TestCase):
    def test_public_compatibility_boundary(self) -> None:
        source = WRAPPERS.read_text(encoding="utf-8")
        canonical = _function(WRAPPERS, "TakeBlessing")
        alias = _function(WRAPPERS, "TakeBlessingV2")
        expected = [
            "pos",
            "faction",
            "buttons",
            "blessing_dialog_id",
            "bribe_dialog_id",
            "multi_account",
            "log",
            "pre_dialog_wait_ms",
            "post_dialog_wait_ms",
            "avoid_final_approach_obstacles",
            "captured_blessing",
        ]
        self.assertEqual([arg.arg for arg in canonical.args.args], expected)
        self.assertEqual([arg.arg for arg in alias.args.args], expected)

        self.assertEqual(len(alias.body), 2)
        returned = alias.body[1]
        self.assertIsInstance(returned, ast.Return)
        call = returned.value
        self.assertIsInstance(call, ast.Call)
        self.assertIsInstance(call.func, ast.Name)
        self.assertEqual(call.func.id, "TakeBlessing")
        self.assertEqual([kw.arg for kw in call.keywords], expected)
        self.assertEqual([ast.unparse(kw.value) for kw in call.keywords], expected)

        recursive_calls = [
            node
            for node in ast.walk(canonical)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "TakeBlessing"
        ]
        self.assertFalse(recursive_calls)

        body = ast.get_source_segment(source, canonical) or ""
        for fragment in (
            "StoreFactionData(log=log)",
            "TakeBlessingMultiboxSequence",
            "CapturedBlessingRunnerV2(runtime, spec)",
            "Player.SendAutomaticDialog(requested_button)",
            "fresh_buttonless_response",
            "now - int(state['started_ms']) >= 3000",
            "avoid_obstacles=avoid_final_approach_obstacles",
            "Wait(pre_dialog_wait_ms, log=log)",
            "Wait(post_dialog_wait_ms, log=log)",
        ):
            self.assertIn(fragment, body)

    def test_final_approach_option_is_transaction_local(self) -> None:
        source = WRAPPERS.read_text(encoding="utf-8")
        private = _function(WRAPPERS, "_move_and_interact")
        public = _function(WRAPPERS, "MoveAndInteract")
        private_body = ast.get_source_segment(source, private) or ""
        public_body = ast.get_source_segment(source, public) or ""
        self.assertIn("avoid_obstacles=avoid_obstacles", private_body)
        self.assertIn("return _move_and_interact(", public_body)
        self.assertNotIn("avoid_obstacles=", public_body)


class CapturedNornLifecycleTests(unittest.TestCase):
    def test_reacquires_displaced_norn_and_interacts_once_after_fight(self) -> None:
        spec = importlib.util.spec_from_file_location("captured_blessing_test", CAPTURED)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        class Runtime:
            def __init__(self):
                self.clock = 0.0
                self.player = (0.0, 0.0)
                self.target = (50.0, 0.0)
                self.hostile = False
                self.dialog = False
                self.buttons = 0
                self.interactions = 0
                self.choice_dispatches = 0
                self.combat_enables = 0
                self.events = []
                self.resolution_radii = []

            def now(self): return self.clock
            def pause_automation(self): pass
            def enable_combat_automation(self): self.combat_enables += 1
            def restore_automation(self): pass
            def cancel_movement(self): pass
            def close_stale_dialog(self): self.dialog = False; self.buttons = 0
            def resolve_target(self, _spec, search_radius=None):
                self.resolution_radii.append(search_radius)
                return 77
            def player_xy(self): return self.player
            def target_xy(self, _agent_id): return self.target
            def move(self, x, y): self.player = (float(x), float(y))
            def interact(self, _agent_id):
                self.interactions += 1
                if self.interactions == 1:
                    self.dialog = True
                    self.buttons = 1
                else:
                    self.dialog = False
                    self.buttons = 0
            def dialog_visible(self): return self.dialog
            def dialog_button_count(self): return self.buttons
            def bind_visible_dialog_choice(self, _agent_id, _label): return (1, 77, 1, ())
            def click_dialog_button(self, choice):
                self.choice_dispatches += 1
                self.dialog = False
                self.buttons = 0
                self.hostile = True
                return choice == 1
            def send_dialog(self, _dialog_id): return True
            def effect_signature(self, _effect_ids): return ()
            def target_is_hostile(self, _agent_id): return self.hostile
            def emit(self, event): self.events.append(dict(event))

        captured = {
            "name": "offline displaced Norn",
            "interaction_mode": "norn_challenge",
            "target_xy": (50.0, 0.0),
            "player_approach_xy": (0.0, 0.0),
            "encoded_name": "\\x8102\\x250D\\xBC8F\\x25EF",
            "model_id": 6425,
            "target_name": "Knut Jordansson",
            "visible_button_label": "Fight me.",
            "effect_ids": (2469, 2470, 2471, 2472, 2551, 2591, 2592, 2593, 2594, 2595),
        }
        runtime = Runtime()
        runner = module.CapturedBlessingRunnerV2(
            runtime,
            module.CapturedBlessingSpec.from_mapping(captured),
        )
        runner.start()

        for _ in range(20):
            done, success, reason = runner.update()
            if runtime.combat_enables:
                break
            runtime.clock += 0.1
        self.assertTrue(runtime.hostile)
        self.assertEqual(runtime.interactions, 1)
        self.assertEqual(runtime.choice_dispatches, 1)

        runtime.target = (900.0, 0.0)
        runtime.hostile = False
        for _ in range(40):
            runtime.clock += 0.1
            done, success, reason = runner.update()
            if runtime.interactions >= 2:
                break
        self.assertEqual(runtime.interactions, 2)
        self.assertEqual(runtime.player, runtime.target)
        self.assertIn(1200.0, runtime.resolution_radii)

        for _ in range(30):
            runtime.clock += 0.1
            done, success, reason = runner.update()
            if done:
                break
        self.assertTrue(done)
        self.assertTrue(success)
        self.assertEqual(reason, "post_challenge_final_interaction_dispatched")
        self.assertEqual(runtime.interactions, 2)


if __name__ == "__main__":
    unittest.main()
