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

class MaintenanceTests(unittest.TestCase):
    def test_bootstrap_blocks_distribution_and_heartbeat_precedes_distribution(self):
        path="Py4GWCoreLib/Builds/Paragon/P_W/Defensive Refrain.py"
        calls=[]
        def action(label,result):
            def run(*a,**k):
                calls.append(label)
                if False: yield
                return result
            return run
        for ready,heartbeat,expected in [(False,True,['self']),(True,True,['self','heartbeat']),(True,False,['self','heartbeat','fire','party','other'])]:
            calls.clear()
            ns={n:n for n in ['Heroic_Refrain_ID','Cant_Touch_This_ID','Theyre_on_Fire_ID','Aggressive_Refrain_ID','Anthem_of_Flame_ID','Fall_Back_ID']}
            fn=load(path,'_run_upkeep',ns,'Paragon_Refrain')
            leadership=NS(Heroic_Refrain_Self=action('self',False),IsHeroicRefrainSelfReady=lambda:ready,Theyre_on_Fire=action('fire',False),Heroic_Refrain_Party=action('party',False))
            self_=NS(IsSkillEquipped=lambda x:x in ['Heroic_Refrain_ID','Cant_Touch_This_ID','Theyre_on_Fire_ID'],skillbook=NS(Paragon=NS(Leadership=leadership,Command=NS(Cant_Touch_This=action('heartbeat',heartbeat)))),_run_refrain_spreading=action('other',False),IsInAggro=lambda:True)
            list(fn(self_)); self.assertEqual(calls,expected)
if __name__=='__main__':unittest.main()
