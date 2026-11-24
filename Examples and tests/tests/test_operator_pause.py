from typing import Any
import ast, unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[2]
def load(path,name,ns: dict[str, Any],owner=None) -> Any:
 tree=ast.parse((ROOT/path).read_text(encoding="utf-8-sig"));body=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==owner).body if owner else tree.body
 node=next(n for n in body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name);node.decorator_list=[]
 exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),path,"exec",flags=__import__('__future__').annotations.compiler_flag),ns);return ns[name]

class OperatorPauseTests(unittest.TestCase):
 def setUp(self):
  ns={'ConsoleLog':lambda *a,**k:None,'PySystem':NS(Console=NS(MessageType=NS(Info=0,Warning=1,Error=2))),'ThrottledTimer':lambda *a:NS(Reset=lambda:None),'Optional':__import__('typing').Optional}
  self.FSM=load('Py4GWCoreLib/py4gwcorelib_src/FSM.py','FSM',ns)
 def test_internal_resume_cannot_release_operator_pause(self):
  f=self.FSM('test');calls=[]
  f.current_state=NS(execute=lambda:calls.append('route'),can_exit=lambda:False,poll_next_state=lambda:None)
  f.pause_by_operator();f.pause();f.resume();f.update()
  self.assertTrue(f.is_paused());self.assertEqual(calls,[])
  f.resume_by_operator();f.update();self.assertEqual(calls,['route'])
 def test_managed_stop_command_still_runs_while_operator_paused(self):
  f=self.FSM('test');calls=[]
  def stop():
   calls.append('stop movement')
   yield
  f.current_state=NS(name='route');f.managed_coroutines.append(stop());f.pause_by_operator();f.update()
  self.assertEqual(calls,['stop movement']);self.assertTrue(f.is_paused())
 def test_internal_pause_remains_after_user_continue(self):
  f=self.FSM('test');f.pause();f.pause_by_operator();f.resume_by_operator()
  self.assertTrue(f.is_paused());f.resume();self.assertFalse(f.is_paused())
 def test_real_bot_pause_restores_exact_heroai_options_and_is_idempotent(self):
  options=NS(Following=False,Targeting=True,Combat=True);writes=[];commands=[]
  ns: dict[str, Any]={'Player':NS(GetAccountEmail=lambda:'account'), 'GLOBAL_CACHE':NS(ShMem=NS(GetHeroAIOptionsFromEmail=lambda _:options,SetHeroAIOptionsByEmail=lambda *a:writes.append((options.Following,options.Targeting,options.Combat))))}
  helper=NS(_hero_ai_pause_applied=False,_hero_ai_pause_snapshot=None,cancel_movement_triggered=False)
  for name in ('apply_hero_ai_pause','release_hero_ai_pause'):
   fn=load('Py4GWCoreLib/botting_src/helpers_src/Upkeepers.py',name,ns,'_Upkeepers');setattr(helper,name,lambda fn=fn:fn(helper))
  class Toggle:
   def __init__(self,value):self.value=value
   def is_active(self):return self.value
   def set_now(self,key,value):self.value=value
  f=self.FSM('test');f.AddManagedCoroutine=lambda name,routine:commands.append(name)
  actor=NS(config=NS(fsm_running=True,FSM=f,upkeep=NS(hero_ai=Toggle(True),hero_ai_paused=Toggle(False))),helpers=NS(Upkeepers=helper),_operator_pause_owns_hero_ai_pause=False)
  player=NS(GetXY=lambda:(1,2),Move=lambda *a:commands.append('cancel destination'))
  import builtins
  def importing(name,globals=None,locals=None,fromlist=(),level=0):
   if level and name=='Player':return NS(Player=player)
   if level and name=='Routines':return NS(Routines=NS(Yield=NS(Movement=NS(StopMovement=lambda:iter(())))))
   return builtins.__import__(name,globals,locals,fromlist,level)
  ns['__builtins__']=dict(vars(builtins),__import__=importing)
  for name in ('_release_operator_pause','Pause','Resume'):
   fn=load('Py4GWCoreLib/Botting.py',name,ns,'BottingClass');setattr(actor,name,lambda fn=fn:fn(actor))
  actor.Pause();actor.Pause();self.assertTrue(f.is_operator_paused());self.assertEqual(writes,[(False,False,False)])
  f.resume();self.assertTrue(f.is_paused())
  actor.Resume();self.assertFalse(f.is_operator_paused());self.assertEqual(writes[-1],(False,True,True));self.assertFalse(actor.config.upkeep.hero_ai_paused.is_active())
  actor.Pause();options.Following=True;actor.Resume()
  self.assertTrue(options.Following, 'Continue must preserve the newer manual Following choice')
  reads=[]
  ns['GLOBAL_CACHE'].ShMem.GetHeroAIOptionsFromEmail=lambda email:reads.append(email) or options
  actor.Pause();ns['Player'].GetAccountEmail=lambda:'other-account';actor.Resume()
  self.assertEqual(reads[-1],'account', 'Restore belongs to the captured account, not the new login')

if __name__=='__main__':unittest.main()
