from __future__ import annotations
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import unittest
ROOT = Path(__file__).resolve().parents[2]
def load(relative: str, names: list[str], scope: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8-sig"))
    nodes: list[ast.stmt] = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    namespace: dict[str, Any] = {"__name__": "offline_owner", **scope}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), relative, "exec"), namespace)
    return namespace
class LootOwnershipTests(unittest.TestCase):
    def test_expired_throttle_does_not_release_active_pickup(self) -> None:
        state = SimpleNamespace(active=True, combat=False, slots=5, valid=True)
        cached = SimpleNamespace(in_looting_routine=False, IsHeadlessCombatPauseActive=lambda: state.combat)
        owner: Any = SimpleNamespace(_headless_looting_enabled=True, cached_data=cached, _has_active_pick_up_loot_message=lambda: state.active, _loot_throttle_check=SimpleNamespace(IsExpired=lambda: True), _follow_state={})
        scope = {"BehaviorTree": SimpleNamespace(NodeState=SimpleNamespace(RUNNING="running", FAILURE="failure")), "is_follow_recovery_active": lambda *args: False, "Routines": SimpleNamespace(Checks=SimpleNamespace(Map=SimpleNamespace(MapValid=lambda: state.valid))), "Map": SimpleNamespace(IsExplorable=lambda: True), "GLOBAL_CACHE": SimpleNamespace(Inventory=SimpleNamespace(GetFreeSlotCount=lambda: state.slots)), "LootFilters": lambda: SimpleNamespace(GetLootArray=lambda distance: []), "Range": SimpleNamespace(Earshot=SimpleNamespace(value=1000))}
        methods = load("Py4GWCoreLib/HeroAI/headless_tree.py", ["_is_looting_routine_active", "_handle_looting"], scope)
        self.assertTrue(methods["_is_looting_routine_active"](owner), "active worker must retain ownership after throttle expiry")
        self.assertEqual(methods["_handle_looting"](owner), "running")
        self.assertTrue(cached.in_looting_routine)
        state.active = False
        self.assertFalse(methods["_is_looting_routine_active"](owner))
        self.assertEqual(methods["_handle_looting"](owner), "failure")
        self.assertFalse(cached.in_looting_routine)
        state.active, state.combat = True, True
        self.assertFalse(methods["_is_looting_routine_active"](owner))
        self.assertEqual(methods["_handle_looting"](owner), "failure")
        state.combat, state.slots = False, 1
        self.assertEqual(methods["_handle_looting"](owner), "failure")
        state.slots, state.valid = 5, False
        self.assertEqual(methods["_handle_looting"](owner), "failure")
        self.assertFalse(cached.in_looting_routine)
if __name__ == "__main__": unittest.main(verbosity=2)
