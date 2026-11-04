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


class HonorTargetTests(unittest.TestCase):
    def test_party_precedes_summons_and_maintained_summon_is_skipped(self):
        maintained=[NS(skill_id=243,target_agent_id=3)]
        covered=set()
        xy={1:(0,0),2:(100,0),3:(10,0),4:(20,0)}
        ns={'Range':NS(Spellcast=NS(value=1248)), 'Player':NS(GetAgentID=lambda:1,GetXY=lambda:xy[1]),'Utils':NS(Distance=lambda a,b:abs(a[0]-b[0])), 'Agent':NS(IsValid=lambda x:x in xy,IsTargettable=lambda x:True,IsAlive=lambda x:True,GetXY=lambda x:xy[x],IsPet=lambda x:x==3,IsMinion=lambda x:x==4,GetOwnerID=lambda x:1,CanBeViewedInPartyWindow=lambda x:True),'AgentArray':NS(GetAllyArray=lambda:[1,2,3,4],GetSpiritPetArray=lambda:[],GetMinionArray=lambda:[4],GetNPCMinipetArray=lambda:[]),'Routines':NS(Checks=NS(Agents=NS(IsMelee=lambda x:x!=1)),Party=NS(IsPartyMember=lambda x:x in [1,2])),'GLOBAL_CACHE':NS(Skill=NS(GetID=lambda _:243),Effects=NS(GetBuffs=lambda _:maintained),ShMem=NS(GetAllActiveSlotsData=lambda:[])),'GetAllAlliesArray':lambda *a,**k:[1,2],'CheckForEffect':lambda x,s:x in covered}
        import builtins
        def importing(name, globals=None, locals=None, fromlist=(), level=0):
            if level and name == 'utils':
                return NS(CheckForEffect=lambda agent, skill: agent in covered)
            return builtins.__import__(name, globals, locals, fromlist, level)
        ns['__builtins__'] = dict(vars(builtins), __import__=importing)
        fn=load('Py4GWCoreLib/HeroAI/targeting.py','TargetStrengthOfHonor',ns)
        self.assertEqual(fn(),2)
        covered.add(2)
        self.assertEqual(fn(),4)
        maintained.append(NS(skill_id=243,target_agent_id=4))
        self.assertEqual(fn(),0)
    def test_core_targetability_projects_existing_native_predicate(self):
        calls=[]
        fn=load('Py4GWCoreLib/Agent.py','IsTargettable',{'PyAgent':NS(get_agent_is_targettable=lambda agent:calls.append(agent) or agent==2)},'Agent')
        self.assertTrue(fn(2));self.assertFalse(fn(3));self.assertEqual(calls,[2,3])
if __name__=='__main__':unittest.main()
