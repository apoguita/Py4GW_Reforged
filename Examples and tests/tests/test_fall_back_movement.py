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
class FallBackTests(unittest.TestCase):
    def test_build_helper_casts_only_while_moving(self) -> None:
        calls: list[int] = []
        state = SimpleNamespace(moving=False)
        def cast(**kwargs: Any) -> Any:
            calls.append(kwargs["skill_id"])
            yield "cast"
            return True
        scope = {"Agent": SimpleNamespace(IsMoving=lambda agent: state.moving), "Player": SimpleNamespace(GetAgentID=lambda: 1), "Skill": SimpleNamespace(GetID=lambda name: 1 if name == "Fall_Back" else 2), "Routines": SimpleNamespace(Checks=SimpleNamespace(Agents=SimpleNamespace(HasEffect=lambda *args: False)))}
        owner = load("Py4GWCoreLib/Builds/Skills/paragon/Command.py", ["Command"], scope)["Command"]
        helper = owner(SimpleNamespace(IsSkillEquipped=lambda skill: True, IsInAggro=lambda: False, IsCloseToAggro=lambda: False, CastSkillID=cast))
        with self.assertRaises(StopIteration) as stopped:
            next(helper.Fall_Back())
        self.assertIs(stopped.exception.value, False)
        self.assertEqual(calls, [], "standing still must not spend the shout")
        state.moving = True
        self.assertEqual(next(helper.Fall_Back()), "cast")
        self.assertEqual(calls, [1])
if __name__ == "__main__": unittest.main(verbosity=2)
