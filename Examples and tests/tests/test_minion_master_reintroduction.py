import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
ROOT = Path(__file__).resolve().parents[2]
def load(path, name, ns, owner=None):
    tree=ast.parse((ROOT/path).read_text(encoding="utf-8-sig"))
    body=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==owner).body if owner else tree.body
    node=next(n for n in body if isinstance(n,ast.FunctionDef) and n.name==name)
    node.decorator_list=[]
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),"exec"),ns)
    return ns[name]

class SummoningTests(unittest.TestCase):
    def test_world_count_is_not_added_for_repeated_owner_records(self):
        ns={};fn=load("Py4GWCoreLib/Builds/Necromancer/N_Any/Minion Master.py",'controlled_minion_count',ns)
        self.assertEqual(fn([(7,8),(7,8),(9,10)],7),8)
    def test_summoning_requires_capacity_and_a_corpse_or_ready_lich(self):
        ns={'AURA_OF_THE_LICH_ID':1,'Routines':NS(Checks=NS(Skills=NS(IsSkillIDReady=lambda _:True)))}
        fn=load("Py4GWCoreLib/Builds/Necromancer/N_Any/Minion Master.py",'_needs_guaranteed_summon',ns,'Minion_Master')
        actor=NS(_equipped_corpse_animation_ids=lambda:[2],IsSkillEquipped=lambda _:False)
        self.assertFalse(fn(actor,has_corpse=True,minion_count=10,desired_cap=10))
        self.assertTrue(fn(actor,has_corpse=True,minion_count=9,desired_cap=10))
        self.assertFalse(fn(actor,has_corpse=False,minion_count=9,desired_cap=10))
        actor.IsSkillEquipped=lambda _:True
        self.assertTrue(fn(actor,has_corpse=False,minion_count=9,desired_cap=10))
if __name__=='__main__':unittest.main()
