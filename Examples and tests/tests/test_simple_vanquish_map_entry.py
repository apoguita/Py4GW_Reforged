from __future__ import annotations

import importlib.util
import ast
from collections.abc import Mapping, Sequence
from pathlib import Path
import re
import runpy
import types
import unittest
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "Sources" / "aC_Scripts" / "PyQuishAI_map_entry.py"
BLESSING_MODULE_PATH = REPO_ROOT / "Sources" / "aC_Scripts" / "PyQuishAI_blessing.py"
WIDGET_PATH = REPO_ROOT / "Widgets" / "Automation" / "Bots" / "Vanquish" / "Simple_Vanquish.py"
PYQUISH_PATH = REPO_ROOT / "Widgets" / "Automation" / "Bots" / "Vanquish" / "PyQuishAI_BT.py"
ROUTES_DIR = REPO_ROOT / "Sources" / "aC_Scripts" / "PyQuishAI_maps"
ROUTE_BLESSING_KEYS = frozenset({
    "bless", "vanguard_blessing", "norn_blessing", "asuran_blessing",
    "faction_blessing",
})


def _load_module():
    spec = importlib.util.spec_from_file_location("simple_vanquish_map_entry_tested", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_blessing_module():
    spec = importlib.util.spec_from_file_location(
        "simple_vanquish_blessing_tested", BLESSING_MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pyquish_keyword_builder():
    tree = ast.parse(PYQUISH_PATH.read_text(encoding="utf-8"), filename=str(PYQUISH_PATH))
    wanted = {"_blessing_parameters", "_coordinate", "_integer", "_build_keyword_action"}
    selected: list[ast.stmt] = [
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
        "Any": object,
        "cast": lambda _type, value: value,
        "ROUTE_BLESSING_KEYS": frozenset({
            "bless", "vanguard_blessing", "norn_blessing", "asuran_blessing",
            "faction_blessing",
        }),
    }
    exec(compile(module, str(PYQUISH_PATH), "exec"), namespace)
    return namespace["_build_keyword_action"], FakeBT


def _load_widget_keyword_handler(captured_runner):
    tree = ast.parse(WIDGET_PATH.read_text(encoding="utf-8"), filename=str(WIDGET_PATH))
    selected: list[ast.stmt] = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_keyword"
    ]
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "Mapping": Mapping,
        "BotSettings": types.SimpleNamespace(BOT_NAME="Simple Vanquish"),
        "ROUTE_BLESSING_KEYS": frozenset({
            "bless", "vanguard_blessing", "norn_blessing", "asuran_blessing",
            "faction_blessing",
        }),
        "run_route_blessing": captured_runner,
        "run_fixed_map_entry": mock.Mock(),
        "_take_blessing": mock.Mock(),
    }
    exec(compile(module, str(WIDGET_PATH), "exec"), namespace)
    return namespace["_handle_keyword"]


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

    def TakeBlessing(self, **kwargs):
        self.calls.append(("blessing", kwargs))
        return ("blessing-tree", kwargs)


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


class _FakeStates:
    def __init__(self):
        self.registered = []

    def AddCustomState(self, callback, name):
        self.registered.append((callback, name))


class _FakeUI:
    @staticmethod
    def PrintMessageToConsole(*_args):
        return None


class _FakeWidgetBot:
    def __init__(self):
        self.States = _FakeStates()
        self.UI = _FakeUI()


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


def _iter_route_blessing_records(value, seen=None):
    if seen is None:
        seen = set()
    value_id = id(value)
    if value_id in seen:
        return
    if isinstance(value, Mapping):
        seen.add(value_id)
        for key, child in value.items():
            if key in ROUTE_BLESSING_KEYS and isinstance(child, Mapping):
                yield key, child
            else:
                yield from _iter_route_blessing_records(child, seen)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        seen.add(value_id)
        if (
            len(value) == 2
            and isinstance(value[0], str)
            and value[0] in ROUTE_BLESSING_KEYS
            and isinstance(value[1], Mapping)
        ):
            yield value[0], value[1]
        else:
            for child in value:
                yield from _iter_route_blessing_records(child, seen)


def validate_route_blessings(route_path: Path):
    namespace = runpy.run_path(str(route_path))
    found = []
    seen_records = set()
    for name, value in namespace.items():
        if name.startswith("_"):
            continue
        for key, record in _iter_route_blessing_records(value):
            marker = id(record)
            if marker in seen_records:
                continue
            seen_records.add(marker)
            found.append((key, record))
            faction = str(record.get("faction", "")).strip().lower()
            if faction:
                if faction not in {"luxon", "kurzick"}:
                    raise AssertionError(f"{route_path}: unsupported faction {faction!r}")
                if not any(
                    position in record
                    for position in ("route_standoff_xy", "player_approach_xy", "target_xy")
                ):
                    raise AssertionError(f"{route_path}: faction blessing lacks geometry")
            else:
                required = {"name", "target_xy", "player_approach_xy", "effect_ids"}
                missing = sorted(required.difference(record))
                if missing:
                    raise AssertionError(
                        f"{route_path}: captured blessing lacks {', '.join(missing)}"
                    )
                if not tuple(record["effect_ids"]):
                    raise AssertionError(f"{route_path}: captured blessing has no effect IDs")
                if not str(record.get("encoded_name", "")).strip() and not (
                    int(record.get("model_id", 0) or 0) > 0
                    and str(record.get("target_name", "")).strip()
                ):
                    raise AssertionError(
                        f"{route_path}: captured blessing lacks executable identity"
                    )
    return found


class SimpleVanquishMapEntryTests(unittest.TestCase):
    def test_existing_baked_route_blessings_satisfy_canonical_owner_contract(self):
        validated = []
        for route_path in ROUTES_DIR.rglob("*.py"):
            source = route_path.read_text(encoding="utf-8-sig")
            has_specialized_key = any(
                key in source for key in ROUTE_BLESSING_KEYS if key != "bless"
            )
            has_mapping_bless = bool(
                re.search(r'''["']bless["']\s*[:,]\s*\{''', source)
            )
            if not has_specialized_key and not has_mapping_bless:
                continue
            validated.extend(validate_route_blessings(route_path))
        self.assertIsInstance(validated, list)

    def test_legacy_widget_bridge_forwards_baked_record_to_canonical_owner(self):
        module = _load_blessing_module()
        wrappers = _FakeWrappers()
        captured = {
            "name": "Cliffs of Dohjok Insect Hunt",
            "interaction_mode": "first",
            "route_standoff_xy": (-26016.72, -9302.96),
            "player_approach_xy": (-26016.72, -9302.96),
            "target_xy": (-26053.0, -9242.0),
            "encoded_name": r"\x8101\x47F0\xEE05\x0D2F",
            "model_id": 4829,
            "effect_ids": (1793, 1829, 1830, 1967, 1968),
            "buttons": 0,
        }

        tree = module.build_route_blessing_tree(captured, wrappers=wrappers)

        self.assertEqual(tree[0], "blessing-tree")
        self.assertEqual(wrappers.calls[0][0], "blessing")
        self.assertEqual(wrappers.calls[0][1]["pos"], captured["route_standoff_xy"])
        self.assertEqual(wrappers.calls[0][1]["buttons"], 0)
        self.assertEqual(wrappers.calls[0][1]["captured_blessing"], captured)
        self.assertIsNot(wrappers.calls[0][1]["captured_blessing"], captured)

    def test_faction_route_uses_canonical_faction_owner_without_captured_lifecycle(self):
        module = _load_blessing_module()
        wrappers = _FakeWrappers()
        faction = {
            "name": "Take the Luxon blessing",
            "faction": "luxon",
            "target_xy": (14126.0, -10653.0),
        }

        module.build_route_blessing_tree(faction, wrappers=wrappers)

        kwargs = wrappers.calls[0][1]
        self.assertEqual(kwargs["pos"], faction["target_xy"])
        self.assertEqual(kwargs["faction"], "luxon")
        self.assertNotIn("captured_blessing", kwargs)

    def test_actual_widget_handler_registers_mapping_as_one_canonical_owner_state(self):
        received = []

        def captured_runner(bot, data):
            received.append((bot, data))
            return "canonical-runner"

        handle = _load_widget_keyword_handler(captured_runner)
        bot = _FakeWidgetBot()
        captured = {
            "name": "Cliffs of Dohjok Insect Hunt",
            "route_standoff_xy": (-26016.72, -9302.96),
            "encoded_name": r"\x8101\x47F0\xEE05\x0D2F",
        }

        handle(bot, "asuran_blessing", captured)

        self.assertEqual(len(bot.States.registered), 1)
        callback, state_name = bot.States.registered[0]
        self.assertEqual(callback(), "canonical-runner")
        self.assertEqual(received, [(bot, captured)])
        self.assertIn("Cliffs of Dohjok Insect Hunt", state_name)

    def test_captured_blessing_runner_restores_host_pause_after_success(self):
        module = _load_blessing_module()
        wrappers = _FakeWrappers()
        planner = _FakePlanner()
        _FakeBottingTree.planner = planner
        bot = _FakeBot(paused=False)
        captured = {"route_standoff_xy": (1.0, 2.0), "encoded_name": "captured"}

        with mock.patch.object(
            module,
            "_load_runtime_dependencies",
            return_value=(_FakeBottingTree, _FakeRoutines, wrappers),
        ):
            self.assertIs(_finish(module.run_route_blessing(bot, captured)), True)

        self.assertIs(bot.stopped, False)
        self.assertEqual(bot.Properties.writes, [True, False])
        self.assertIs(planner.headless, False)
        self.assertEqual(planner.stop_calls, 1)

    def test_captured_blessing_runner_stops_route_when_owner_fails(self):
        module = _load_blessing_module()
        wrappers = _FakeWrappers()
        planner = _FakePlanner(status="PLANNER: Failed")
        _FakeBottingTree.planner = planner
        bot = _FakeBot(paused=True)
        captured = {"route_standoff_xy": (1.0, 2.0), "encoded_name": "captured"}

        with (
            mock.patch.object(
                module,
                "_load_runtime_dependencies",
                return_value=(_FakeBottingTree, _FakeRoutines, wrappers),
            ),
            self.assertRaisesRegex(RuntimeError, "canonical captured-blessing owner failed"),
        ):
            _finish(module.run_route_blessing(bot, captured))

        self.assertIs(bot.stopped, True)
        self.assertEqual(bot.Properties.writes, [True, True])
        self.assertEqual(planner.stop_calls, 1)

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

    def test_specialized_captured_keyword_reaches_same_canonical_owner(self):
        build, fake_bt = _load_pyquish_keyword_builder()
        fake_bt.calls.clear()
        definition = types.SimpleNamespace(region="EOTN_Tarnished_Coast")
        captured = {
            "name": "Arbor Bay Asuran blessing",
            "route_standoff_xy": (15806.97, 11963.51),
            "target_xy": (16362.0, 11627.0),
            "encoded_name": r"\x8102\x240D\xFEF0\xC41A\x1619",
            "effect_ids": (2445, 2446),
        }

        build(definition, "asuran_blessing", captured, 2500.0, False, False)

        self.assertEqual(fake_bt.calls[0]["captured_blessing"], captured)
        self.assertEqual(fake_bt.calls[0]["pos"], captured["route_standoff_xy"])

    def test_faction_keyword_uses_canonical_faction_owner(self):
        build, fake_bt = _load_pyquish_keyword_builder()
        fake_bt.calls.clear()
        definition = types.SimpleNamespace(region="Factions_TheJadeSea")
        faction = {
            "name": "Take the Luxon blessing",
            "faction": "luxon",
            "target_xy": (14126.0, -10653.0),
        }

        build(definition, "faction_blessing", faction, 2500.0, False, False)

        self.assertEqual(fake_bt.calls[0]["faction"], "luxon")
        self.assertEqual(fake_bt.calls[0]["pos"], faction["target_xy"])
        self.assertNotIn("captured_blessing", fake_bt.calls[0])

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

    def test_widget_routes_mapping_blessings_through_canonical_bridge(self):
        source = WIDGET_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "from Sources.aC_Scripts.PyQuishAI_blessing import ROUTE_BLESSING_KEYS, run_route_blessing",
            source,
        )
        self.assertIn("if isinstance(value, Mapping):", source)
        self.assertIn("lambda data=value: run_route_blessing(bot, data)", source)
        self.assertIn("lambda x=value[0], y=value[1]: _take_blessing(bot, x, y)", source)


if __name__ == "__main__":
    unittest.main()
