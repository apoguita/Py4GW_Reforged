from __future__ import annotations
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parents[2]

def load_class(relative: str, name: str, namespace: dict[str, Any]) -> Any:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8-sig"))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    scope: dict[str, Any] = {"__name__": "offline_owner", **namespace}
    exec(compile(ast.Module(body=[node], type_ignores=[]), relative, "exec"), scope)
    return scope[name]

class MendingTests(unittest.TestCase):
    def test_delegates_to_existing_spread_owner_and_preserves_result(self) -> None:
        calls: list[int] = []
        def spread(skill_id: int) -> Any:
            calls.append(skill_id)
            yield "cast-in-progress"
            return True
        owner = load_class("Py4GWCoreLib/Builds/Skills/paragon/Motivation.py", "Motivation", {"Skill": SimpleNamespace(GetID=lambda name: 1578)})
        helper = owner(SimpleNamespace(SpreadEchoToAlly=spread))
        cast = helper.Mending_Refrain()
        self.assertEqual(next(cast), "cast-in-progress")
        with self.assertRaises(StopIteration) as done:
            next(cast)
        self.assertIs(done.exception.value, True)
        self.assertEqual(calls, [1578])

if __name__ == "__main__":
    unittest.main(verbosity=2)
