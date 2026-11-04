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
class SwirlingTests(unittest.TestCase):
    def test_real_eight_slot_sort_promotes_only_while_overcast(self) -> None:
        from enum import Enum, IntEnum, auto
        enums = load("Py4GWCoreLib/HeroAI/types.py", ["SkillNature", "SkillType"], {"Enum": Enum, "IntEnum": IntEnum, "auto": auto})
        nature, kind = enums["SkillNature"], enums["SkillType"]
        state = SimpleNamespace(overcast=0)
        rows = [SimpleNamespace(skill_id=808 if i == 7 else i + 1, custom_skill_data=SimpleNamespace(Nature=nature.Offensive.value if i == 7 else nature.Buff.value, SkillType=kind.Spell.value)) for i in range(8)]
        scope = {"SkillNature": nature, "SkillType": kind, "MAX_SKILLS": 8, "Player": SimpleNamespace(GetAgentID=lambda: 1), "Agent": SimpleNamespace(GetOvercast=lambda agent: state.overcast), "GLOBAL_CACHE": SimpleNamespace(Skill=SimpleNamespace(Data=SimpleNamespace(GetCombo=lambda skill: 0))), "should_prioritize_swirling_aura": lambda skill, overcast: skill == 808 and overcast > 0}
        sort = load("Py4GWCoreLib/HeroAI/combat.py", ["PrioritizeSkills"], scope)["PrioritizeSkills"]
        owner = SimpleNamespace(SkillData=lambda slot: rows[slot - 1], skill_order=[0] * 8, skills=[])
        sort(owner)
        self.assertEqual(owner.skill_order, list(range(8)), "without overcast, ordinary buffs stay ahead")
        state.overcast = 1
        sort(owner)
        self.assertEqual(owner.skill_order, [7, 0, 1, 2, 3, 4, 5, 6], "party-wide Swirling Aura moves ahead of ordinary buffs")
    def test_overcast_gate_only_promotes_swirling(self) -> None:
        gate = load("Py4GWCoreLib/HeroAI/constants.py", ["should_prioritize_swirling_aura"], {"SWIRLING_AURA": 808})["should_prioritize_swirling_aura"]
        self.assertFalse(gate(808, 0))
        self.assertTrue(gate(808, 1))
        self.assertFalse(gate(809, 1))
if __name__ == "__main__": unittest.main(verbosity=2)
