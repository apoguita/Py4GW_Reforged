from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = (
    ROOT
    / "Py4GWCoreLib"
    / "Builds"
    / "Paragon"
    / "P_W"
    / "Defensive Refrain.py"
)

SKILL_IDS = {
    name: index + 1
    for index, name in enumerate(
        (
            "Heroic_Refrain",
            "Mending_Refrain",
            "Bladeturn_Refrain",
            "Energizing_Finale",
            "Burning_Refrain",
            "Blazing_Finale",
            "Hasty_Refrain",
            "Aggressive_Refrain",
            "Anthem_of_Flame",
            "Theyre_on_Fire",
            "Fall_Back",
        )
    )
}


class _ChecksSkills:
    can_cast = True

    @classmethod
    def CanCast(cls):
        return cls.can_cast


class _Routines:
    class Checks:
        Skills = _ChecksSkills


class _BuildMgr:
    pass


def _load_contract_class():
    source = CONTRACT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Paragon_Refrain"
    )
    isolated = ast.Module(body=[class_node], type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = {
        "BuildMgr": _BuildMgr,
        "Routines": _Routines,
        "SkillsTemplate": object,
        **{f"{name}_ID": skill_id for name, skill_id in SKILL_IDS.items()},
    }
    exec(compile(isolated, CONTRACT_PATH, "exec"), namespace)
    return namespace["Paragon_Refrain"]


ParagonRefrain = _load_contract_class()


def _run(generator):
    try:
        while True:
            next(generator)
    except StopIteration as stop:
        return stop.value


class ParagonRefrainAtomicHandlerTests(unittest.TestCase):
    def setUp(self):
        _ChecksSkills.can_cast = True
        self.events = []
        self.build = object.__new__(ParagonRefrain)
        self.build.IsInAggro = lambda: True
        self.upkeep_result = True
        self.combat_result = True

        def upkeep():
            if False:
                yield
            self.events.append("upkeep")
            return self.upkeep_result

        def combat():
            if False:
                yield
            self.events.append("combat")
            return self.combat_result

        self.build._run_upkeep = upkeep
        self.build._run_combat = combat

    def test_ooc_starts_with_upkeep_on_each_fresh_tick(self):
        self.assertTrue(_run(self.build._run_ooc()))
        self.assertTrue(_run(self.build._run_ooc()))
        self.assertEqual(self.events, ["upkeep", "upkeep"])

    def test_ooc_to_combat_transition_does_not_lose_upkeep(self):
        self.assertTrue(_run(self.build._run_ooc()))
        self.assertTrue(_run(self.build._run_combat_phase()))
        self.assertEqual(self.events, ["upkeep", "upkeep"])

    def test_combat_work_runs_only_after_upkeep_has_nothing_to_do(self):
        self.upkeep_result = False
        self.assertTrue(_run(self.build._run_combat_phase()))
        self.assertEqual(self.events, ["upkeep", "combat"])

    def test_cannot_cast_returns_without_creating_a_waiting_continuation(self):
        _ChecksSkills.can_cast = False
        self.assertFalse(_run(self.build._run_ooc()))
        self.assertFalse(_run(self.build._run_combat_phase()))
        self.assertEqual(self.events, [])

    def test_contract_registers_explicit_phase_handlers(self):
        source = CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertIn("self.SetOOCFn(self._run_ooc)", source)
        self.assertIn("self.SetCombatFn(self._run_combat_phase)", source)
        self.assertNotIn("self.SetSkillCastingFn(self._run_local_skill_logic)", source)


class _SkillMethod:
    def __init__(self, name, calls, outcomes):
        self.name = name
        self.calls = calls
        self.outcomes = outcomes

    def __call__(self, *args, **kwargs):
        if False:
            yield
        self.calls.append(self.name)
        values = self.outcomes.get(self.name, [False])
        if len(values) > 1:
            return values.pop(0)
        return values[0]


def _skill_group(names, calls, outcomes):
    group = type("SkillGroup", (), {})()
    for name in names:
        setattr(group, name, _SkillMethod(name, calls, outcomes))
    return group


def _skillbook(calls, outcomes):
    root = type("Skillbook", (), {})()
    root.Paragon = type("Paragon", (), {})()
    root.Paragon.Leadership = _skill_group(
        ("Heroic_Refrain", "Aggressive_Refrain", "Anthem_of_Flame", "Theyre_on_Fire"),
        calls,
        outcomes,
    )
    root.Paragon.Motivation = _skill_group(
        (
            "Mending_Refrain",
            "Energizing_Finale",
            "Burning_Refrain",
            "Blazing_Finale",
            "Hasty_Refrain",
        ),
        calls,
        outcomes,
    )
    root.Paragon.Command = _skill_group(("Bladeturn_Refrain", "Fall_Back"), calls, outcomes)
    return root


class ParagonRefrainReportedBarTests(unittest.TestCase):
    def setUp(self):
        _ChecksSkills.can_cast = True
        self.calls = []
        self.outcomes = {
            "Heroic_Refrain": [True, True, True, False],
            "Hasty_Refrain": [True, False],
            "Aggressive_Refrain": [True, False],
            "Theyre_on_Fire": [True, False],
        }
        self.build = object.__new__(ParagonRefrain)
        self.build.skillbook = _skillbook(self.calls, self.outcomes)
        self.build.IsInAggro = lambda: True
        self.equipped = {
            SKILL_IDS["Heroic_Refrain"],
            SKILL_IDS["Hasty_Refrain"],
            SKILL_IDS["Aggressive_Refrain"],
            SKILL_IDS["Theyre_on_Fire"],
        }
        self.build.IsSkillEquipped = lambda skill_id: skill_id in self.equipped

        def combat():
            if False:
                yield
            self.calls.append("combat")
            return True

        self.build._run_combat = combat

    def test_fresh_ticks_preserve_bootstrap_distribution_and_maintenance_order(self):
        final_calls = []
        for handler in (
            self.build._run_ooc,
            self.build._run_ooc,
            self.build._run_combat_phase,
            self.build._run_combat_phase,
            self.build._run_combat_phase,
            self.build._run_combat_phase,
        ):
            self.assertTrue(_run(handler()))
            final_calls.append(self.calls[-1])

        self.assertEqual(
            final_calls,
            [
                "Heroic_Refrain",
                "Heroic_Refrain",
                "Heroic_Refrain",
                "Hasty_Refrain",
                "Aggressive_Refrain",
                "Theyre_on_Fire",
            ],
        )
        self.assertNotIn("combat", final_calls)


if __name__ == "__main__":
    unittest.main()
