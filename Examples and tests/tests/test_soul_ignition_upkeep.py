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
class SoulTests(unittest.TestCase):
    def test_recovery_window_and_safety_boundaries(self) -> None:
        gates = load("Py4GWCoreLib/HeroAI/constants.py", ["soul_ignition_overcast_fraction", "should_activate_soul_ignition", "should_drop_soul_ignition"], {})
        activate, drop = gates["should_activate_soul_ignition"], gates["should_drop_soul_ignition"]
        self.assertTrue(activate(.8, 60, 40))
        self.assertFalse(activate(.8, 61, 39))
        self.assertFalse(activate(.25, 10, 90))
        self.assertFalse(activate(1, 0, 100))
        self.assertTrue(drop(.25, 10, 90))
        self.assertTrue(drop(1, 90, 10))
        self.assertFalse(drop(1, 89, 11))
    def test_drop_uses_buff_id_and_toggle_original_slot(self) -> None:
        drops: list[int] = []
        state = SimpleNamespace(now=1000)
        scope = {"GLOBAL_CACHE": SimpleNamespace(Effects=SimpleNamespace(GetBuffID=lambda skill: 9001, DropBuff=drops.append)), "Player": SimpleNamespace(GetAgentID=lambda: 1), "Agent": SimpleNamespace(GetHealth=lambda agent: .2, GetOvercast=lambda agent: 20, GetMaxEnergy=lambda agent: 80), "Utils": SimpleNamespace(GetBaseTimestamp=lambda: state.now), "should_drop_soul_ignition": lambda *args: True}
        methods = load("Py4GWCoreLib/HeroAI/combat.py", ["_enabled_skill_slot", "_manage_soul_ignition_upkeep"], scope)
        owner: Any = SimpleNamespace(skills=[SimpleNamespace(skill_id=3446), SimpleNamespace(skill_id=1)], soul_ignition=3446, skill_order=[1, 0], is_skill_enabled=[True, False], _next_soul_ignition_drop_ms=0)
        owner._enabled_skill_slot = lambda skill: methods["_enabled_skill_slot"](owner, skill)
        self.assertFalse(methods["_manage_soul_ignition_upkeep"](owner), "disabled original bar slot must not be cancelled")
        owner.is_skill_enabled[1] = True
        self.assertTrue(methods["_manage_soul_ignition_upkeep"](owner))
        self.assertEqual(drops, [9001], "DropBuff needs the runtime buff ID, not skill 3446")
        self.assertFalse(methods["_manage_soul_ignition_upkeep"](owner), "do not flood repeated cancellation")
        state.now += 1000
        self.assertTrue(methods["_manage_soul_ignition_upkeep"](owner))
if __name__ == "__main__": unittest.main(verbosity=2)
