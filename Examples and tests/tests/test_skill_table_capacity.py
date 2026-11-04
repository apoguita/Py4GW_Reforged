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

class CapacityTests(unittest.TestCase):
    def test_highest_skill_roundtrip_and_invalid_boundary(self) -> None:
        def skill() -> Any:
            return SimpleNamespace(SkillID=0)
        def register(table: list[Any]) -> None:
            table[3446] = SimpleNamespace(SkillID=3446)
        names = ("Warrior", "Ranger", "Monk", "Necromancer", "Mesmer", "Elementalist", "Assassin", "Ritualist", "Paragon", "Dervish", "PVE")
        owner = load_class("Py4GWCoreLib/HeroAI/custom_skill.py", "CustomSkillClass", {"CustomSkill": skill, **{name + "Skills": register for name in names}})
        table = owner()
        self.assertEqual(table.get_skill(3446).SkillID, 3446, "Soul Ignition must survive real constructor registration")
        replacement = SimpleNamespace(SkillID=3446)
        table.set_skill(3446, replacement)
        self.assertIs(table.get_skill(3446), replacement)
        for invalid in (-1, 3447):
            with self.assertRaises(ValueError, msg=f"invalid skill ID {invalid}"):
                table.get_skill(invalid)
            with self.assertRaises(ValueError, msg=f"invalid skill ID {invalid}"):
                table.set_skill(invalid, replacement)

if __name__ == "__main__":
    unittest.main(verbosity=2)
