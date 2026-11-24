from typing import Any
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
ROOT = Path(__file__).resolve().parents[2]
def load(path, name, ns: dict[str, Any], owner=None) -> Any:
    tree=ast.parse((ROOT/path).read_text(encoding="utf-8-sig"))
    body=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==owner).body if owner else tree.body
    node=next(n for n in body if isinstance(n,ast.FunctionDef) and n.name==name)
    node.decorator_list=[]
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),"exec"),ns)
    return ns[name]


class PrismPolicyTests(unittest.TestCase):
    def test_water_hex_cluster_selects_target_and_promotes_priority(self):
        points={2:(100,0),3:(110,0),4:(600,0)}
        active=[2,3,4]
        ns={'Range':NS(Spellcast=NS(value=1248),Nearby=NS(value=150)),'SkillNature':NS(OffensiveA=NS(value=10),CustomN=NS(value=99)),'Player':NS(GetXY=lambda:(0,0)),'Utils':NS(Distance=lambda a,b:abs(a[0]-b[0])),'Agent':NS(IsValid=lambda x:True,IsAlive=lambda x:True,GetXY=lambda x:points[x]),'EnemyBlacklist':lambda:NS(is_blacklisted=lambda x:False),'Routines':NS(Agents=NS(GetFilteredEnemyArray=lambda *a:list(active))),'HasWaterMagicHex':lambda x:x in [2,4]}
        path='Py4GWCoreLib/HeroAI/custom_skill_src/icy_prism.py'
        load(path,'TargetWaterHexedClusteredEnemy',ns)
        target=load(path,'select_target',ns);priority=load(path,'select_priority',ns)
        self.assertEqual(target(),2);self.assertEqual(priority(),10)
        active[:]=[4]
        self.assertEqual(target(),4);self.assertEqual(priority(),99)
        active[:]=[3]
        self.assertEqual(target(),0);self.assertEqual(priority(),99)
    def test_water_hex_detection_rejects_other_attributes_and_non_hexes(self):
        effects=[]
        ns: dict[str, Any]={'Agent':NS(IsValid=lambda _:True,IsHexed=lambda _:True),'GLOBAL_CACHE':NS(Effects=NS(GetBuffs=lambda _:[],GetEffects=lambda _:effects),Skill=NS(GetType=lambda sid:(1 if sid!=3 else 2,''),Attribute=NS(GetAttribute=lambda sid:NS(attribute_id=7 if sid!=2 else 8)))),'SkillType':NS(Hex=NS(value=1)),'Attribute':NS(WaterMagic=NS(value=7))}
        fn=load('Py4GWCoreLib/HeroAI/custom_skill_src/icy_prism.py','HasWaterMagicHex',ns)
        self.assertFalse(fn(2))
        effects[:]=[NS(skill_id=2),NS(skill_id=3)]
        self.assertFalse(fn(2))
        effects.append(NS(skill_id=1))
        self.assertTrue(fn(2))

    def test_shared_sort_honors_policy_once_and_preserves_default_skills(self):
        from enum import IntEnum
        types=ast.parse((ROOT/'Py4GWCoreLib/HeroAI/types.py').read_text(encoding='utf-8'))
        enum_node=next(n for n in types.body if isinstance(n,ast.ClassDef) and n.name=='SkillNature')
        enum_ns={'IntEnum':IntEnum,'Enum':__import__('enum').Enum,'auto':__import__('enum').auto}
        exec(compile(ast.Module(body=[enum_node],type_ignores=[]),'types','exec'),enum_ns)
        type_node=next(n for n in types.body if isinstance(n,ast.ClassDef) and n.name=='SkillType')
        exec(compile(ast.Module(body=[type_node],type_ignores=[]),'types','exec'),enum_ns)
        nature=enum_ns['SkillNature'];calls=[]
        def policy(distance):
            calls.append(distance)
            return nature.OffensiveA.value
        skills=[NS(custom_skill_data=NS(Nature=nature.Offensive.value, PrioritySelector=None)) for _ in range(8)]
        skills[-1].custom_skill_data.PrioritySelector=policy
        ns={'Range':NS(Spellcast=NS(value=1248)),'MAX_SKILLS':8,'SkillNature':nature,'SkillType':enum_ns['SkillType'],'copy':__import__('copy')}
        fn=load('Py4GWCoreLib/SkillManager.py','_PrioritizeSkills',ns)
        order=[0]*8
        result=fn(lambda slot:skills[slot-1],order,900)
        self.assertEqual(calls,[900])
        self.assertEqual(order[0],7)
        self.assertEqual(order[1:],list(range(7)))

if __name__=='__main__':unittest.main()
