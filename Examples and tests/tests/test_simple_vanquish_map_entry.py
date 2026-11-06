from __future__ import annotations

import importlib.util
import ast
from collections.abc import Mapping, Sequence
from pathlib import Path
import types
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "Sources" / "aC_Scripts" / "PyQuishAI_map_entry.py"
WIDGET_PATH = REPO_ROOT / "Widgets" / "Automation" / "Bots" / "Vanquish" / "Simple_Vanquish.py"
PYQUISH_PATH = REPO_ROOT / "Widgets" / "Automation" / "Bots" / "Vanquish" / "PyQuishAI_BT.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("simple_vanquish_map_entry_tested", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pyquish_keyword_builder():
    tree = ast.parse(PYQUISH_PATH.read_text(encoding="utf-8"), filename=str(PYQUISH_PATH))
    wanted = {"_blessing_parameters", "_coordinate", "_integer", "_build_keyword_action"}
    selected = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted
    ]
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *selected],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)

    class FakeBT:
        calls = []

        @classmethod
        def TakeBlessing(cls, **kwargs):
            cls.calls.append(dict(kwargs))
            return ("take-blessing", kwargs)

    namespace = {
        "Mapping": Mapping,
        "Sequence": Sequence,
        "BT": FakeBT,
        "BehaviorTree": object,
        "VanquishDefinition": object,
        "Coordinate": tuple[float, float],
    }
    exec(compile(module, str(PYQUISH_PATH), "exec"), namespace)
    return namespace["_build_keyword_action"], FakeBT


ZEN_ENTRY = {
    "name": "Guard Lae Fao",
    "source_map_id": 250,
    "expected_map_id": 246,
    "encoded_name": "\\x5CF5\\x978F\\xF211\\x057A",
    "button_positions": (0, 0, 0),
}


class _FakeWrappers:
    def __init__(self):
        self.calls = []

    def MoveAndAutoDialogByModelID(self, **kwargs):
        self.calls.append(("dialog", kwargs))
        return "dialog-owner"

    def WaitForMapLoad(self, **kwargs):
        self.calls.append(("map", kwargs))
        return "map-owner"

    def Sequence(self, **kwargs):
        self.calls.append(("sequence", kwargs))
        return ("tree", kwargs)


class _FakeProperties:
    def __init__(self, active=False):
        self.active = active
        self.writes = []

    def Get(self, name, field):
        assert (name, field) == ("hero_ai_paused", "active")
        return self.active

    def ApplyNow(self, name, field, value):
        assert (name, field) == ("hero_ai_paused", "active")
        self.active = bool(value)
        self.writes.append(bool(value))


class _FakeBot:
    def __init__(self, paused=False):
        self.Properties = _FakeProperties(paused)
        self.stopped = False

    def Stop(self):
        self.stopped = True


class _FakePlanner:
    def __init__(self, status="PLANNER: Completed", tick_error=None):
        self.status = status
        self.tick_error = tick_error
        self.started = False
        self.headless = None
        self.tree = None
        self.stop_calls = 0

    def SetHeadlessHeroAIEnabled(self, value):
        self.headless = value

    def SetPlannerTree(self, tree):
        self.tree = tree

    def Start(self):
        self.started = True

    def IsStarted(self):
        return self.started

    def tick(self):
        if self.tick_error is not None:
            raise self.tick_error
        self.started = False

    def GetBlackboardValue(self, key, default=""):
        assert key == "PLANNER_STATUS"
        return self.status

    def Stop(self):
        self.stop_calls += 1
        self.started = False


class _FakeBottingTree:
    planner: _FakePlanner | None = None

    @classmethod
    def Create(cls, **kwargs):
        assert kwargs["pause_on_combat"] is False
        assert kwargs["auto_loot"] is False
        assert kwargs["isolation_enabled"] is False
        assert cls.planner is not None
        return cls.planner


class _FakeMap:
    map_id = 250

    @classmethod
    def GetMapID(cls):
        return cls.map_id


class _FakeRoutines:
    class Yield:
        @staticmethod
        def wait(_milliseconds):
            if False:
                yield None


def _finish(generator):
    while True:
        try:
            next(generator)
        except StopIteration as done:
            return done.value


class SimpleVanquishMapEntryTests(unittest.TestCase):
    def test_captured_blessing_mapping_reaches_canonical_owner_unchanged(self):
        build, fake_bt = _load_pyquish_keyword_builder()
        fake_bt.calls.clear()
        definition = types.SimpleNamespace(region="NF_Istan")
        captured = {
            "name": "Cliffs of Dohjok Insect Hunt",
            "interaction_mode": "first",
            "route_standoff_xy": (-26016.72, -9302.96),
            "player_approach_xy": (-26016.72, -9302.96),
            "target_xy": (-26053.0, -9242.0),
            "encoded_name": r"\x8101\x47F0\xEE05\x0D2F",
            "model_id": 4829,
            "target_name": "Sunspear Scout",
            "effect_ids": (1793, 1829, 1830, 1967, 1968),
            "buttons": 0,
        }

        children = build(definition, "bless", captured, 2500.0, False, False)

        self.assertEqual(len(children), 1)
        self.assertEqual(len(fake_bt.calls), 1)
        self.assertEqual(fake_bt.calls[0]["pos"], captured["route_standoff_xy"])
        self.assertEqual(fake_bt.calls[0]["buttons"], 0)
        self.assertEqual(fake_bt.calls[0]["blessing_dialog_id"], 0x85)
        self.assertEqual(fake_bt.calls[0]["captured_blessing"], captured)

    def test_coordinate_blessing_keeps_legacy_call_shape(self):
        build, fake_bt = _load_pyquish_keyword_builder()
        fake_bt.calls.clear()
        definition = types.SimpleNamespace(region="NF_Istan")

        build(definition, "bless", (-25984.0, -9240.0), 2500.0, False, False)

        self.assertEqual(fake_bt.calls[0]["pos"], (-25984.0, -9240.0))
        self.assertNotIn("captured_blessing", fake_bt.calls[0])
        self.assertNotIn("buttons", fake_bt.calls[0])

    def test_builder_delegates_exact_identity_and_zero_based_pages_to_canonical_owner(self):
        module = _load_module()
        wrappers = _FakeWrappers()

        tree = module.build_fixed_map_entry_tree(ZEN_ENTRY, wrappers=wrappers)

        self.assertEqual(tree[0], "tree")
        self.assertEqual(
            wrappers.calls[0],
            (
                "dialog",
                {
                    "modelID_or_encStr": "\\x5CF5\\x978F\\xF211\\x057A",
                    "button_number": [0, 0, 0],
                    "log": True,
                    "multi_account": False,
                },
            ),
        )
        self.assertEqual(
            wrappers.calls[1],
            ("map", {"map_id": 246, "timeout_ms": 60_000}),
        )
        self.assertEqual(wrappers.calls[2][0], "sequence")
        self.assertEqual(
            wrappers.calls[2][1]["children"],
            ["dialog-owner", "map-owner"],
        )

    def test_runner_restores_host_pause_after_success(self):
        module = _load_module()
        wrappers = _FakeWrappers()
        planner = _FakePlanner()
        _FakeBottingTree.planner = planner
        bot = _FakeBot(paused=False)

        with mock.patch.object(
            module,
            "_load_runtime_dependencies",
            return_value=(_FakeBottingTree, _FakeMap, _FakeRoutines, wrappers),
        ):
            self.assertIs(_finish(module.run_fixed_map_entry(bot, ZEN_ENTRY)), True)

        self.assertIs(bot.stopped, False)
        self.assertEqual(bot.Properties.writes, [True, False])
        self.assertIs(planner.headless, False)
        self.assertEqual(planner.stop_calls, 1)

    def test_runner_fails_closed_on_wrong_source_map(self):
        module = _load_module()
        bot = _FakeBot()

        with (
            mock.patch.object(_FakeMap, "map_id", 999),
            mock.patch.object(
                module,
                "_load_runtime_dependencies",
                return_value=(_FakeBottingTree, _FakeMap, _FakeRoutines, _FakeWrappers()),
            ),
            self.assertRaisesRegex(RuntimeError, "expected source map 250, found 999"),
        ):
            _finish(module.run_fixed_map_entry(bot, ZEN_ENTRY))

        self.assertIs(bot.stopped, True)
        self.assertEqual(bot.Properties.writes, [])

    def test_runner_stops_route_and_restores_pause_when_owner_fails(self):
        module = _load_module()
        wrappers = _FakeWrappers()
        planner = _FakePlanner(status="PLANNER: Failed")
        _FakeBottingTree.planner = planner
        bot = _FakeBot(paused=True)

        with (
            mock.patch.object(_FakeMap, "map_id", 250),
            mock.patch.object(
                module,
                "_load_runtime_dependencies",
                return_value=(_FakeBottingTree, _FakeMap, _FakeRoutines, wrappers),
            ),
            self.assertRaisesRegex(RuntimeError, "canonical map-entry owner failed"),
        ):
            _finish(module.run_fixed_map_entry(bot, ZEN_ENTRY))

        self.assertIs(bot.stopped, True)
        self.assertEqual(bot.Properties.writes, [True, True])
        self.assertEqual(planner.stop_calls, 1)

    def test_runner_stops_route_and_restores_pause_when_owner_raises(self):
        module = _load_module()
        wrappers = _FakeWrappers()
        planner = _FakePlanner(tick_error=ValueError("owner tick exploded"))
        _FakeBottingTree.planner = planner
        bot = _FakeBot(paused=False)

        with (
            mock.patch.object(_FakeMap, "map_id", 250),
            mock.patch.object(
                module,
                "_load_runtime_dependencies",
                return_value=(_FakeBottingTree, _FakeMap, _FakeRoutines, wrappers),
            ),
            self.assertRaisesRegex(ValueError, "owner tick exploded"),
        ):
            _finish(module.run_fixed_map_entry(bot, ZEN_ENTRY))

        self.assertIs(bot.stopped, True)
        self.assertEqual(bot.Properties.writes, [True, False])
        self.assertEqual(planner.stop_calls, 1)

    def test_widget_registers_map_entry_as_one_custom_state(self):
        source = WIDGET_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "from Sources.aC_Scripts.PyQuishAI_map_entry import run_fixed_map_entry",
            source,
        )
        self.assertIn('if key == "map_entry":', source)
        self.assertIn("lambda data=value: run_fixed_map_entry(bot, data)", source)


if __name__ == "__main__":
    unittest.main()
