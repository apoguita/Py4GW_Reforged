from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
COMBAT_PATH = ROOT / "Py4GWCoreLib" / "HeroAI" / "combat.py"


class FakePets:
    pet_id = 0

    @classmethod
    def GetPetID(cls, _player_id: int) -> int:
        return cls.pet_id


class FakeParty:
    Pets = FakePets


class FakeGlobalCache:
    Party = FakeParty


class FakePlayer:
    @staticmethod
    def GetAgentID() -> int:
        return 100

    @staticmethod
    def GetXY() -> tuple[float, float]:
        return 0.0, 0.0


class FakeAgent:
    valid = True
    alive = True

    @classmethod
    def IsValid(cls, _agent_id: int) -> bool:
        return cls.valid

    @classmethod
    def IsAlive(cls, _agent_id: int) -> bool:
        return cls.alive


class FakeAgentArrayFilter:
    in_range = True

    @classmethod
    def ByDistance(cls, agent_ids, _origin, _distance):
        return list(agent_ids) if cls.in_range else []


class FakeAgentArray:
    Filter = FakeAgentArrayFilter


class FakeSpellcastRange:
    value = 1248


class FakeRange:
    Spellcast = FakeSpellcastRange


class FakeSkill:
    def __init__(self, skill_id: int) -> None:
        self.skill_id = skill_id


def _load_target_resolver():
    module = ast.parse(COMBAT_PATH.read_text(encoding="utf-8"))
    class_node = next(
        node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "CombatClass"
    )
    method = next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "_resolve_double_dragon_pet_target"
    )
    isolated_class = ast.ClassDef(
        name="CombatClass",
        bases=[],
        keywords=[],
        body=[method],
        decorator_list=[],
    )
    isolated_module = ast.Module(body=[isolated_class], type_ignores=[])
    ast.fix_missing_locations(isolated_module)
    namespace = {
        "Agent": FakeAgent,
        "AgentArray": FakeAgentArray,
        "GLOBAL_CACHE": FakeGlobalCache,
        "Player": FakePlayer,
        "Range": FakeRange,
    }
    exec(compile(isolated_module, COMBAT_PATH, "exec"), namespace)
    return namespace["CombatClass"]


CombatClass = _load_target_resolver()


class DoubleDragonPetTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        FakePets.pet_id = 0
        FakeAgent.valid = True
        FakeAgent.alive = True
        FakeAgentArrayFilter.in_range = True
        self.combat = CombatClass()
        self.combat.double_dragon = 1234
        self.combat.charm_animal = 411
        self.combat.comfort_animal = 436
        self.combat.heal_as_one = 6502
        self.combat.pet_attack_list = [5001, 5002]
        self.combat.skills = []

    def test_unrelated_skill_keeps_normal_targeting(self) -> None:
        FakePets.pet_id = 200
        self.assertIsNone(self.combat._resolve_double_dragon_pet_target(9999))

    def test_no_owned_pet_keeps_other_ally_fallback_for_non_pet_build(self) -> None:
        self.assertIsNone(self.combat._resolve_double_dragon_pet_target(1234))

    def test_pet_build_without_resolved_pet_blocks_backline_fallback(self) -> None:
        self.combat.skills = [FakeSkill(self.combat.comfort_animal)]
        self.assertEqual(self.combat._resolve_double_dragon_pet_target(1234), 0)

    def test_living_in_range_pet_is_selected(self) -> None:
        FakePets.pet_id = 200
        self.assertEqual(self.combat._resolve_double_dragon_pet_target(1234), 200)

    def test_dead_pet_blocks_backline_fallback(self) -> None:
        FakePets.pet_id = 200
        FakeAgent.alive = False
        self.assertEqual(self.combat._resolve_double_dragon_pet_target(1234), 0)

    def test_out_of_range_pet_blocks_backline_fallback(self) -> None:
        FakePets.pet_id = 200
        FakeAgentArrayFilter.in_range = False
        self.assertEqual(self.combat._resolve_double_dragon_pet_target(1234), 0)


if __name__ == "__main__":
    unittest.main()
