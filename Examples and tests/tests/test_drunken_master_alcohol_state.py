from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
COMBAT_PATH = ROOT / "Py4GWCoreLib" / "HeroAI" / "combat.py"


class _Utils:
    now_ms = 1000

    @classmethod
    def GetBaseTimestamp(cls):
        return cls.now_ms


class _Effects:
    level = 0

    @classmethod
    def GetAlcoholLevel(cls):
        return cls.level


class _Inventory:
    counts = {}
    uses = []

    @classmethod
    def GetModelCount(cls, model_id):
        return cls.counts.get(model_id, 0)

    @classmethod
    def UseItem(cls, item_id):
        cls.uses.append(item_id)


class _Item:
    @staticmethod
    def GetItemIdFromModelID(model_id):
        return model_id + 10000


class _GlobalCache:
    Inventory = _Inventory
    Item = _Item


class _Console:
    class MessageType:
        Debug = 0
        Info = 1
        Warning = 2

    @staticmethod
    def Log(*_args, **_kwargs):
        return None


class _PySystem:
    Console = _Console


def _load_combat_class():
    tree = ast.parse(COMBAT_PATH.read_text(encoding="utf-8"))
    source_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "CombatClass"
    )
    wanted = {
        "GetDrunkLevel",
        "UseAlcoholIfAvailable",
        "_reset_alcohol_drink_state",
        "IsAlcoholTopoffPending",
    }
    methods = [
        node
        for node in source_class.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    isolated_class = ast.ClassDef(
        name="CombatClass",
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    isolated = ast.Module(body=[isolated_class], type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = {
        "ALCOHOL_L1_MODEL_IDS": [101, 102],
        "ALCOHOL_L3_MODEL_IDS": [301],
        "ALCOHOL_MAX_USE_ATTEMPTS": 3,
        "ALCOHOL_USE_CONFIRM_TIMEOUT_MS": 2000,
        "Effects": _Effects,
        "GLOBAL_CACHE": _GlobalCache,
        "PySystem": _PySystem,
        "Utils": _Utils,
    }
    exec(compile(isolated, COMBAT_PATH, "exec"), namespace)
    return namespace["CombatClass"]


CombatClass = _load_combat_class()


class DrunkenMasterAlcoholStateTests(unittest.TestCase):
    def setUp(self):
        _Utils.now_ms = 1000
        _Effects.level = 0
        _Inventory.counts = {101: 10, 102: 10, 301: 10}
        _Inventory.uses = []
        self.combat = CombatClass()
        self.combat._next_alcohol_recheck_ms = 0
        self.combat._alcohol_drink_pending = False
        self.combat._alcohol_drink_attempts = 0
        self.combat._alcohol_pending_model_id = 0
        self.combat._alcohol_pending_model_count = 0

    def test_sober_call_submits_exactly_one_drink(self):
        self.assertTrue(self.combat.UseAlcoholIfAvailable())
        self.assertEqual(_Inventory.uses, [101 + 10000])
        self.assertTrue(self.combat._alcohol_drink_pending)
        self.assertEqual(self.combat._alcohol_drink_attempts, 1)

    def test_pending_request_does_not_submit_a_second_drink(self):
        self.assertTrue(self.combat.UseAlcoholIfAvailable())
        self.assertFalse(self.combat.UseAlcoholIfAvailable())
        self.assertEqual(len(_Inventory.uses), 1)

    def test_unconfirmed_request_retries_only_after_timeout(self):
        self.assertTrue(self.combat.UseAlcoholIfAvailable())
        _Utils.now_ms = 2999
        self.assertFalse(self.combat.UseAlcoholIfAvailable())
        _Utils.now_ms = 3000
        self.assertTrue(self.combat.UseAlcoholIfAvailable())
        self.assertEqual(len(_Inventory.uses), 2)

    def test_inventory_decrease_confirms_use_without_retry(self):
        self.assertTrue(self.combat.UseAlcoholIfAvailable())
        _Inventory.counts[101] = 9
        _Utils.now_ms = 3000
        self.assertFalse(self.combat.UseAlcoholIfAvailable())
        self.assertEqual(len(_Inventory.uses), 1)
        self.assertFalse(self.combat._alcohol_drink_pending)

    def test_positive_drunk_level_never_consumes_alcohol(self):
        _Effects.level = 1
        self.assertFalse(self.combat.UseAlcoholIfAvailable())
        self.assertEqual(_Inventory.uses, [])

    def test_three_unconfirmed_attempts_are_the_hard_ceiling(self):
        for expected_attempts in (1, 2, 3):
            self.assertTrue(self.combat.UseAlcoholIfAvailable())
            self.assertEqual(self.combat._alcohol_drink_attempts, expected_attempts)
            _Utils.now_ms += 2000

        self.assertFalse(self.combat.UseAlcoholIfAvailable())
        self.assertEqual(len(_Inventory.uses), 3)


if __name__ == "__main__":
    unittest.main()
