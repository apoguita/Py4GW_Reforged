from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
import types
from typing import Any
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
    def test_public_boundary(self) -> None:
        source = WRAPPERS.read_text(encoding="utf-8")
        canonical = _function(WRAPPERS, "TakeBlessing")
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
            "encoded_identity",
            "model_id",
            "identity_search_radius",
        ]
        self.assertEqual([arg.arg for arg in canonical.args.args], expected)

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
            "CanonicalCapturedBlessingRunner(runtime, spec)",
            "Player.SendAutomaticDialog(requested_button)",
            "fresh_buttonless_response",
            "now - int(state['started_ms']) >= 3000",
            "avoid_obstacles=avoid_final_approach_obstacles",
            "Wait(pre_dialog_wait_ms, log=log)",
            "Wait(post_dialog_wait_ms, log=log)",
        ):
            self.assertIn(fragment, body)

    def test_captured_blessing_does_not_silently_ignore_multibox(self) -> None:
        node = _function(WRAPPERS, "TakeBlessing")
        namespace: dict[str, Any] = {"Range": types.SimpleNamespace(Area=types.SimpleNamespace(value=322.0))}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(WRAPPERS), "exec",
                     flags=__import__("__future__").annotations.compiler_flag), namespace)
        with self.assertRaisesRegex(ValueError, "local execution only"):
            namespace["TakeBlessing"]((0, 0), captured_blessing={}, multi_account=True)

    def test_final_approach_option_is_transaction_local(self) -> None:
        source = WRAPPERS.read_text(encoding="utf-8")
        public = _function(WRAPPERS, "MoveAndInteract")
        public_body = ast.get_source_segment(source, public) or ""
        self.assertIn("avoid_obstacles=avoid_obstacles", public_body)
        self.assertEqual([arg.arg for arg in public.args.kwonlyargs], [
            "avoid_obstacles", "encoded_identity", "model_id", "identity_search_radius",
        ])
        default = public.args.kw_defaults[0]
        assert isinstance(default, ast.Constant)
        self.assertTrue(default.value)
        self.assertNotIn("def _move_and_interact", source)


class CapturedNornLifecycleTests(unittest.TestCase):
    def test_reacquires_displaced_norn_and_interacts_once_after_fight(self) -> None:
        spec = importlib.util.spec_from_file_location("captured_blessing_test", CAPTURED)
        if spec is None or spec.loader is None:
            self.fail("captured blessing module could not be loaded")
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
        runner = module.CanonicalCapturedBlessingRunner(
            runtime,
            module.CapturedBlessingSpec.from_mapping(captured),
        )
        runner.start()

        done, success, reason = False, False, "not_started"
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


class CapturedOrdinaryLifecycleTests(unittest.TestCase):
    @staticmethod
    def _load_captured():
        spec = importlib.util.spec_from_file_location("captured_blessing_ordinary_test", CAPTURED)
        if spec is None or spec.loader is None:
            raise RuntimeError("captured blessing module could not be loaded")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_exact_encoded_identity_and_occurrence_geometry_select_target(self) -> None:
        module = self._load_captured()

        agents = {
            11: {"encoded": r"\x8101\xWRONG", "model": 4829, "name": "Sunspear Scout", "xy": (-26053.0, -9242.0)},
            12: {"encoded": r"\x8101\x47F0\xEE05\x0D2F", "model": 9999, "name": "Other", "xy": (-26050.0, -9240.0)},
            13: {"encoded": r"\x8101\x47F0\xEE05\x0D2F", "model": 4829, "name": "Sunspear Scout", "xy": (-24000.0, -7000.0)},
        }

        class FakeAgent:
            @staticmethod
            def IsValid(agent_id): return agent_id in agents
            @staticmethod
            def IsLiving(agent_id): return agent_id in agents
            @staticmethod
            def GetEncNameStrByID(agent_id, literal=True): return agents[agent_id]["encoded"]
            @staticmethod
            def GetModelID(agent_id): return agents[agent_id]["model"]
            @staticmethod
            def GetNameByID(agent_id): return agents[agent_id]["name"]
            @staticmethod
            def GetXY(agent_id): return agents[agent_id]["xy"]

        fake_agent_module = types.ModuleType("Py4GWCoreLib.Agent")
        setattr(fake_agent_module, "Agent", FakeAgent)
        old_agent_module = sys.modules.get("Py4GWCoreLib.Agent")
        sys.modules["Py4GWCoreLib.Agent"] = fake_agent_module
        try:
            runtime = object.__new__(module.Py4GWCapturedBlessingRuntime)
            runtime._all_agents = lambda: [11, 13, 12]
            runtime._last_agent_sources = {"counts": {"test": 3}, "errors": {}}
            runtime._last_resolution_diagnostic = None
            runtime._sink = lambda _event: None
            captured = module.CapturedBlessingSpec.from_mapping({
                "name": "Cliffs Insect Hunt",
                "interaction_mode": "first",
                "target_xy": (-26053.0, -9242.0),
                "player_approach_xy": (-26016.72, -9302.96),
                "encoded_name": r"\x8101\x47F0\xEE05\x0D2F",
                "model_id": 4829,
                "target_name": "Sunspear Scout",
                "effect_ids": (1793, 1829, 1830, 1967, 1968),
            })
            self.assertEqual(runtime.resolve_target(captured), 12)
        finally:
            if old_agent_module is None:
                sys.modules.pop("Py4GWCoreLib.Agent", None)
            else:
                sys.modules["Py4GWCoreLib.Agent"] = old_agent_module

    def test_option_one_dispatch_requires_observed_blessing_effect(self) -> None:
        module = self._load_captured()

        class Runtime:
            def __init__(self):
                self.clock = 0.0
                self.dialog = False
                self.effect = ()
                self.clicked = []
                self.interacted = []
                self.events = []
            def now(self): return self.clock
            def pause_automation(self): pass
            def enable_combat_automation(self): pass
            def restore_automation(self): pass
            def cancel_movement(self): pass
            def close_stale_dialog(self): pass
            def resolve_target(self, spec, search_radius=None):
                self.events.append({"event": "resolved", "encoded": spec.encoded_name})
                return 50
            def player_xy(self): return (-26016.72, -9302.96)
            def target_xy(self, agent_id): return (-26053.0, -9242.0)
            def move(self, x, y): raise AssertionError("captured approach is already satisfied")
            def interact(self, agent_id): self.interacted.append(agent_id); self.dialog = True
            def dialog_visible(self): return self.dialog
            def dialog_button_count(self): return 1 if self.dialog else 0
            def bind_visible_dialog_choice(self, agent_id, label): return None
            def click_dialog_button(self, choice):
                self.clicked.append(choice)
                self.dialog = False
                self.effect = ((1793, 0),)
                return True
            def send_dialog(self, dialog_id): return True
            def effect_signature(self, effect_ids): return self.effect
            def target_is_hostile(self, agent_id): return False
            def emit(self, event): self.events.append(dict(event))

        captured = {
            "name": "Cliffs Insect Hunt",
            "interaction_mode": "first",
            "target_xy": (-26053.0, -9242.0),
            "player_approach_xy": (-26016.72, -9302.96),
            "encoded_name": r"\x8101\x47F0\xEE05\x0D2F",
            "model_id": 4829,
            "target_name": "Sunspear Scout",
            "effect_ids": (1793, 1829, 1830, 1967, 1968),
        }
        runtime = Runtime()
        runner = module.CanonicalCapturedBlessingRunner(
            runtime,
            module.CapturedBlessingSpec.from_mapping(captured),
        )
        runner.start()
        done, success, reason = False, False, "not_started"
        for _ in range(10):
            done, success, reason = runner.update()
            runtime.clock += 0.1
            if done:
                break
        self.assertTrue(done)
        self.assertTrue(success)
        self.assertEqual(reason, "blessing_effect_observed")
        self.assertEqual(runtime.interacted, [50])
        self.assertEqual(runtime.clicked, [1])
        self.assertTrue(any(event.get("encoded") == captured["encoded_name"] for event in runtime.events))


if __name__ == "__main__":
    unittest.main()
