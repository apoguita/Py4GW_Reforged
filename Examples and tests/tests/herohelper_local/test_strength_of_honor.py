from __future__ import annotations

import ast
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
HERO_HELPER = ROOT / "Widgets" / "Automation" / "Enhancements" / "HeroHelper.py"


def _function_node(name: str, *, class_name: str | None = None) -> ast.FunctionDef:
    tree = ast.parse(HERO_HELPER.read_text(encoding="utf-8"))
    body = tree.body
    if class_name is not None:
        owner = next(
            node
            for node in body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        body = owner.body
    return next(
        node
        for node in body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _load_function(name: str, namespace: dict, *, class_name: str | None = None):
    node = _function_node(name, class_name=class_name)
    node.decorator_list = []
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, HERO_HELPER, "exec"), namespace)
    return namespace[name]


class FakePlayer:
    agent_id = 1

    @classmethod
    def GetAgentID(cls):
        return cls.agent_id


class FakeAgent:
    weapon_item_type = 0
    martial = False

    @classmethod
    def GetWeaponItemType(cls, _agent_id):
        return cls.weapon_item_type

    @classmethod
    def IsMartial(cls, _agent_id):
        return cls.martial


holds_physical_weapon = _load_function(
    "holds_physical_weapon",
    {"Player": FakePlayer, "Agent": FakeAgent},
    class_name="Helper",
)


class FakeParty:
    hero_count = 1

    @classmethod
    def GetHeroCount(cls):
        return cls.hero_count


class FakeSkill:
    @staticmethod
    def GetID(name):
        if name != "Strength_of_Honor":
            raise AssertionError(name)
        return 243


class FakeHelper:
    delay_ready = True
    alive = True
    smartcast_result: tuple[int, int, int, int] | None = (2, 4, 243, 1)
    smartcast_calls = []

    @classmethod
    def reset(cls):
        cls.delay_ready = True
        cls.alive = True
        cls.smartcast_result = (2, 4, 243, 1)
        cls.smartcast_calls = []

    @classmethod
    def can_execute_with_delay(cls, identifier, delay_ms):
        return cls.delay_ready and identifier == "smart_honor" and delay_ms == 1000

    @classmethod
    def is_agent_alive(cls, _agent_id):
        return cls.alive

    @staticmethod
    def holds_physical_weapon():
        return holds_physical_weapon()

    @staticmethod
    def get_physical_party_targets(melee_only=False):
        return [1] if FakeAgent.weapon_item_type in {2,15,27,32,35} else []

    @staticmethod
    def check_for_effects(target, skills):
        return False

    @staticmethod
    def get_spell_cast_range():
        return 1248.0

    @classmethod
    def smartcast_hero_skill(cls, **kwargs):
        cls.smartcast_calls.append(kwargs)
        return cls.smartcast_result


executed_skills = []


def fake_execute_hero_skill(*args):
    executed_skills.append(args)


setattr(FakeHelper, "find_maintenance_cast", staticmethod(_load_function("find_maintenance_cast", {"Helper": FakeHelper}, class_name="Helper")))


smart_honor = _load_function(
    "smart_honor",
    {
        "Party": FakeParty,
        "Player": FakePlayer,
        "Skill": FakeSkill,
        "Helper": FakeHelper,
        "execute_hero_skill": fake_execute_hero_skill,
        "execute_maintenance_skill": lambda selection: fake_execute_hero_skill(*selection[0]) if selection else None,
    },
)


class FakeTreeNodeFlags:
    DefaultOpen = 1


class FakePyImGui:
    TreeNodeFlags = FakeTreeNodeFlags

    @staticmethod
    def text_disabled(_text):
        pass

    @staticmethod
    def separator():
        pass

    @staticmethod
    def collapsing_header(_label, _flags):
        return True

    @staticmethod
    def same_line(*_args):
        pass

    @staticmethod
    def spacing():
        pass

    @staticmethod
    def is_item_hovered():
        return False

    @staticmethod
    def set_tooltip(_text):
        pass


class FakeImGui:
    @staticmethod
    def DrawTexture(*_args):
        pass


class FakeUIHelper:
    @staticmethod
    def get_profession_icon_path(_profession):
        return ""

    @staticmethod
    def get_skill_icon_path(_skill):
        return ""

    @staticmethod
    def visible_checkbox(label, previous):
        if label.startswith("Strength of Honor##"):
            return True
        return previous

    @staticmethod
    def log_event(**_kwargs):
        pass


class FakeConfig:
    smart_honor_enabled: bool
    def __init__(self):
        for attr in (
            "smart_panic_enabled",
            "smart_honor_enabled",
            "smart_life_bond_enabled",
            "smart_vigorous_enabled",
            "smart_bip_enabled",
            "smart_dark_aura_enabled",
            "smart_incoming_fallback_enabled",
            "smart_sos_enabled",
            "smart_st_enabled",
            "smart_splinter_enabled",
            "smart_xinrae_enabled",
        ):
            setattr(self, attr, False)
        self.save_calls = 0

    def save(self):
        self.save_calls += 1


draw_tab_smart_skills = _load_function(
    "draw_tab_smart_skills",
    {
        "Helper": FakeUIHelper,
        "PyImGui": FakePyImGui,
        "ImGui": FakeImGui,
        "os": os,
    },
)


class PhysicalWeaponTests(unittest.TestCase):
    def setUp(self):
        FakePlayer.agent_id = 1
        FakeAgent.weapon_item_type = 0
        FakeAgent.martial = False

    def test_all_supported_physical_item_types_are_accepted(self):
        for item_type in (2, 5, 15, 27, 32, 35, 36):
            with self.subTest(item_type=item_type):
                FakeAgent.weapon_item_type = item_type
                self.assertTrue(holds_physical_weapon())

    def test_bow_does_not_depend_on_high_level_weapon_name_mapping(self):
        FakeAgent.weapon_item_type = 5
        FakeAgent.martial = False
        self.assertTrue(holds_physical_weapon())

    def test_nonphysical_item_is_rejected(self):
        FakeAgent.weapon_item_type = 22  # wand
        self.assertFalse(holds_physical_weapon())

    def test_high_level_martial_classification_remains_a_fallback(self):
        FakeAgent.weapon_item_type = 255
        FakeAgent.martial = True
        self.assertTrue(holds_physical_weapon())

    def test_missing_player_is_rejected(self):
        FakePlayer.agent_id = 0
        FakeAgent.weapon_item_type = 5
        self.assertFalse(holds_physical_weapon())


class StrengthOfHonorBehaviorTests(unittest.TestCase):
    def setUp(self):
        FakePlayer.agent_id = 1
        FakeParty.hero_count = 1
        FakeAgent.weapon_item_type = 0
        FakeAgent.martial = False
        FakeHelper.reset()
        executed_skills.clear()

    def test_melee_reaches_shared_smartcast_and_manual_hero_command(self):
        FakeAgent.weapon_item_type = 2

        smart_honor()

        self.assertEqual(len(FakeHelper.smartcast_calls), 1)
        call = FakeHelper.smartcast_calls[0]
        self.assertEqual(call["skill_id"], 243)
        self.assertTrue(call["allow_out_of_combat"])
        self.assertFalse(call["effect_check"])
        self.assertEqual(call["cast_target_id"], 1)
        self.assertEqual(executed_skills, [FakeHelper.smartcast_result])

    def test_bow_is_excluded_from_strength_of_honor(self):
        FakeAgent.weapon_item_type = 5
        smart_honor()
        self.assertEqual(FakeHelper.smartcast_calls, [])
        self.assertEqual(executed_skills, [])

    def test_wand_stops_before_shared_smartcast(self):
        FakeAgent.weapon_item_type = 22

        smart_honor()

        self.assertEqual(FakeHelper.smartcast_calls, [])
        self.assertEqual(executed_skills, [])

    def test_existing_shared_smartcast_rejection_remains_authoritative(self):
        FakeAgent.weapon_item_type = 2
        FakeHelper.smartcast_result = None

        smart_honor()

        self.assertEqual(len(FakeHelper.smartcast_calls), 1)
        self.assertEqual(executed_skills, [])

    def test_dead_player_stops_before_weapon_and_smartcast(self):
        FakeAgent.weapon_item_type = 5
        FakeHelper.alive = False

        smart_honor()

        self.assertEqual(FakeHelper.smartcast_calls, [])
        self.assertEqual(executed_skills, [])


class SmartSkillPersistenceTests(unittest.TestCase):
    def test_strength_of_honor_toggle_saves_immediately(self):
        config = FakeConfig()

        draw_tab_smart_skills(config)

        self.assertTrue(config.smart_honor_enabled)
        self.assertEqual(config.save_calls, 1)


class PartyMaintenanceTests(unittest.TestCase):
    def test_covered_target_is_skipped_and_caster_exclusion_is_forwarded(self):
        calls=[]
        helper=__import__('types').SimpleNamespace()
        helper.check_for_effects=staticmethod(lambda target,skills:target==1)
        helper.get_spell_cast_range=staticmethod(lambda:1248.0)
        def cast(**kwargs):
            calls.append(kwargs)
            return (2,4,241,kwargs['cast_target_id'])
        helper.smartcast_hero_skill=staticmethod(cast)
        fn=_load_function('find_maintenance_cast',{'Helper':helper},class_name='Helper')
        result=fn(241,[1,2,3],exclude_caster_target=True)
        self.assertEqual(result[1],2)
        self.assertEqual(len(calls),1)
        self.assertTrue(calls[0]['exclude_caster_target'])


if __name__ == "__main__":
    unittest.main()
