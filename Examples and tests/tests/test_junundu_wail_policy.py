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
class WailTests(unittest.TestCase):
    def test_combat_and_recovery_boundaries(self) -> None:
        gate = load("Py4GWCoreLib/HeroAI/constants.py", ["should_use_junundu_wail"], {})["should_use_junundu_wail"]
        for health, dead, enemies, expected in [(1., 0, True, False), (.1, 1, True, False), (1., 2, True, True), (1., 1, False, True), (.4, 0, False, True), (.5, 0, False, False)]:
            with self.subTest(health=health, dead=dead, enemies=enemies):
                self.assertEqual(gate(health, .5, dead, enemies), expected)
if __name__ == "__main__": unittest.main(verbosity=2)
