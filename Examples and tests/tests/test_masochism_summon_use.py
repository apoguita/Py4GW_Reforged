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


class MasochismTests(unittest.TestCase):
    def test_default_requires_aggro_but_explicit_summon_use_does_not(self):
        calls=[]
        def cast(**kwargs):
            calls.append(kwargs)
            if False:yield
            return True
        ns={'BuildCoroutine':object,'Skill':NS(GetID=lambda _:1),'Player':NS(GetAgentID=lambda:7),'Utils':NS(GetBaseTimestamp=lambda:100),'Routines':NS(Checks=NS(Agents=NS(HasEffect=lambda *a:False))),'GLOBAL_CACHE':NS(Effects=NS(GetEffectTimeRemaining=lambda *a:0))}
        fn=load('Py4GWCoreLib/Builds/Skills/necromancer/SoulReaping.py','Masochism',ns,'SoulReaping')
        build=NS(IsSkillEquipped=lambda _:True,IsInAggro=lambda:False,IsCloseToAggro=lambda:False,CastSkillID=cast)
        actor=NS(build=build)
        list(fn(actor));self.assertEqual(calls,[])
        list(fn(actor,require_aggro=False));self.assertEqual(len(calls),1)
        list(fn(actor,require_aggro=False));self.assertEqual(len(calls),1)
if __name__=='__main__':unittest.main()
