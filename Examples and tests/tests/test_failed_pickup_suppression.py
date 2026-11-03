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


import sys
from types import ModuleType
from unittest.mock import patch
class SuppressionTests(unittest.TestCase):
    def test_failed_item_is_scoped_to_account_map_group_and_expiry(self):
        path='Py4GWCoreLib/GlobalCache/WhiteboardLocks.py'
        intent=NS(OwnerEmail='owner',KindID=1,SkillID=1000026,TargetAgentID=7,IsolationGroupID=2,ExpiresAtTick=200)
        entries=[(0,intent)];cleared=[]
        core=ModuleType('Py4GWCoreLib');core.GLOBAL_CACHE=NS(ShMem=NS(GetAllAccounts=lambda:NS(GetAllIntents=lambda:entries,ClearIntent=cleared.append)))
        ns={'LOOT_SUPPRESSION_KEY_BASE':1000000,'WhiteboardLockKind':NS(LOOT_ITEM=1),'_owner_context':lambda:('owner',2),'_loot_suppression_key':lambda:1000026}
        check=load(path,'is_loot_suppressed',ns)
        clear=load(path,'clear_loot_suppressions',ns)
        with patch.dict(sys.modules,{'Py4GWCoreLib':core}):
            self.assertTrue(check(7,100));self.assertFalse(check(8,100));self.assertFalse(check(7,200))
            intent.OwnerEmail='other';self.assertFalse(check(7,100));intent.OwnerEmail='owner'
            intent.SkillID=1000027;self.assertFalse(check(7,100));intent.SkillID=1000026
            intent.IsolationGroupID=3;self.assertFalse(check(7,100));intent.IsolationGroupID=2
            self.assertEqual(clear(),1);self.assertEqual(cleared,[0])
if __name__=='__main__':unittest.main()
