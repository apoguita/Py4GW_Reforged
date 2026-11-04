from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[2]
COMBAT_PATH = ROOT / "Py4GWCoreLib" / "HeroAI" / "combat.py"


class _Effects:
    active = []

    @classmethod
    def GetEffects(cls, _agent_id):
        return cls.active


class _Skill:
    dervish_enchantments = {1499, 1500}

    @classmethod
    def GetType(cls, skill_id):
        skill_type = "Enchantment" if skill_id in cls.dervish_enchantments else "Stance"
        return 0, skill_type

    @classmethod
    def GetProfession(cls, skill_id):
        profession = "Dervish" if skill_id in cls.dervish_enchantments else "Monk"
        return 0, profession


class _GlobalCache:
    Effects = _Effects
    Skill = _Skill


class _Player:
    @staticmethod
    def GetAgentID():
        return 99


class _Agent:
    @staticmethod
    def IsLiving(agent_id):
        return agent_id > 0


def _effect(skill_id: int, timestamp: int, duration: float = 8.0, time_elapsed: int = 0):
    return SimpleNamespace(
        skill_id=skill_id,
        timestamp=timestamp,
        duration=duration,
        time_elapsed=time_elapsed,
    )


def _load_combat_class():
    tree = ast.parse(COMBAT_PATH.read_text(encoding="utf-8"))
    source_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "CombatClass"
    )
    wanted = {
        "_has_pious_renewal_bar",
        "_newest_dervish_enchantment",
        "_can_refresh_pious_renewal",
        "_can_teardown_pious_renewal",
        "FindCastableSkill",
        "HandleCombat",
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
    isolated = ast.fix_missing_locations(ast.Module(body=[isolated_class], type_ignores=[]))
    namespace = {
        "Agent": _Agent,
        "GLOBAL_CACHE": _GlobalCache,
        "MAX_SKILLS": 2,
        "Player": _Player,
    }
    exec(compile(isolated, COMBAT_PATH, "exec"), namespace)
    return namespace["CombatClass"]


CombatClass = _load_combat_class()


class PiousRenewalOrderTests(unittest.TestCase):
    def setUp(self):
        _Effects.active = []
        self.combat = CombatClass()
        self.combat.pious_renewal = 1499
        self.combat.pious_teardown_skill_ids = {1490}
        self.combat.skills = [
            SimpleNamespace(skill_id=1499),
            SimpleNamespace(skill_id=1490),
        ]

    def test_newest_dervish_enchantment_uses_timestamp_not_list_order(self):
        _Effects.active = [_effect(1499, 200), _effect(1500, 100)]
        self.assertEqual(self.combat._newest_dervish_enchantment(), 1499)

    def test_unknown_or_ambiguous_order_fails_closed(self):
        _Effects.active = [_effect(1499, 100), _effect(1500, 100)]
        self.assertIsNone(self.combat._newest_dervish_enchantment())

        _Effects.active = [_effect(1499, 0)]
        self.assertIsNone(self.combat._newest_dervish_enchantment())

    def test_expired_effect_is_not_considered_newest(self):
        _Effects.active = [
            _effect(1499, 200, duration=8.0, time_elapsed=8000),
            _effect(1500, 100),
        ]
        self.assertEqual(self.combat._newest_dervish_enchantment(), 1500)

    def test_refresh_is_allowed_only_when_another_dervish_enchantment_is_newer(self):
        _Effects.active = [_effect(1499, 100), _effect(1500, 200)]
        self.assertTrue(self.combat._can_refresh_pious_renewal(1499))

        _Effects.active = [_effect(1500, 100), _effect(1499, 200)]
        self.assertFalse(self.combat._can_refresh_pious_renewal(1499))

    def test_teardown_is_allowed_only_when_pious_renewal_is_newest(self):
        _Effects.active = [_effect(1500, 100), _effect(1499, 200)]
        self.assertTrue(self.combat._can_teardown_pious_renewal(1490))

        _Effects.active = [_effect(1499, 100), _effect(1500, 200)]
        self.assertFalse(self.combat._can_teardown_pious_renewal(1490))

    def test_ooc_scan_evaluates_safe_teardown(self):
        _Effects.active = [_effect(1499, 200)]
        self.combat.drunken_master = -1
        self.combat.IsSkillReady = lambda slot: slot == 1
        self.combat.IsOOCSkill = lambda _slot: False
        self.combat.IsReadyToCast = lambda _slot: (True, 42)

        self.assertEqual(self.combat.FindCastableSkill(ooc=True), (1, 42))

    def test_ooc_scan_keeps_unsafe_teardown_blocked(self):
        _Effects.active = [_effect(1499, 100), _effect(1500, 200)]
        self.combat.drunken_master = -1
        self.combat.IsSkillReady = lambda slot: slot == 1
        self.combat.IsOOCSkill = lambda _slot: False
        self.combat.IsReadyToCast = lambda _slot: (True, 42)

        self.assertEqual(self.combat.FindCastableSkill(ooc=True), (-1, 0))

    def test_dispatch_rechecks_order_after_selection(self):
        _Effects.active = [_effect(1499, 100), _effect(1500, 200)]
        self.combat.FindCastableSkill = lambda ooc=False: (1, 42)
        self.combat.SetSkillPointer = lambda slot: setattr(self.combat, "pointer", slot)
        self.combat.ResetSkillPointer = lambda: setattr(self.combat, "pointer", -1)

        self.assertFalse(self.combat.HandleCombat(ooc=True))
        self.assertEqual(self.combat.pointer, -1)


if __name__ == "__main__":
    unittest.main()
