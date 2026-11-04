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
class MeleeTests(unittest.TestCase):
    def test_only_resumes_valid_melee_target_after_casting(self) -> None:
        state = SimpleNamespace(casting=True, melee=True)
        calls: list[int] = []
        scope = {"Agent": SimpleNamespace(IsMelee=lambda agent: state.melee, IsCasting=lambda agent: state.casting), "Player": SimpleNamespace(GetAgentID=lambda: 1), "SkillType": SimpleNamespace(Attack=SimpleNamespace(value=1))}
        methods = load("Py4GWCoreLib/HeroAI/combat.py", ["_queue_melee_engagement_after_skill", "_resume_pending_melee_engagement"], scope)
        owner: Any = SimpleNamespace(pending_melee_engagement_target_id=0, _is_valid_current_enemy_target=lambda target: target == 99, InCastingRoutine=lambda: False, SafeInteract=calls.append)
        skill = SimpleNamespace(custom_skill_data=SimpleNamespace(SkillType=2))
        methods["_queue_melee_engagement_after_skill"](owner, skill, 99)
        self.assertFalse(methods["_resume_pending_melee_engagement"](owner))
        self.assertEqual(owner.pending_melee_engagement_target_id, 99)
        state.casting = False
        self.assertTrue(methods["_resume_pending_melee_engagement"](owner))
        self.assertEqual(calls, [99])
        self.assertFalse(methods["_resume_pending_melee_engagement"](owner), "one interaction per pending handoff")
        state.melee = False
        methods["_queue_melee_engagement_after_skill"](owner, skill, 99)
        self.assertEqual(owner.pending_melee_engagement_target_id, 0)
if __name__ == "__main__": unittest.main(verbosity=2)
