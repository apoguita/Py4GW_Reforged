"""Run the actual environment frame with command/native boundaries doubled."""
import ast,traceback,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[2]
class SharedCommandTests(unittest.TestCase):
 def frame(self,routines,logs):
  path=ROOT/'Widgets/System/Environment Upkeeper.py'
  fn=next(n for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n,ast.FunctionDef) and n.name=='main')
  cache=NS(Coroutines=routines,_update_cache=lambda:None)
  ns={'GLOBAL_CACHE':cache,'HOTKEY_MANAGER':NS(update=lambda:None),'Routines':NS(Checks=NS(Map=NS(MapValid=lambda:True))), 'Map':NS(IsMapLoading=lambda:True,IsInCinematic=lambda:False),'widget_config':NS(action_queue_manager=NS(ResetNonTransitionQueues=lambda:None),throttle_transition_queue=NS(IsExpired=lambda:False)), 'ConsoleLog':lambda *a:logs.append(a),'MODULE_NAME':'Environment Upkeeper','PySystem':NS(Console=NS(MessageType=NS(Error=1))),'traceback':traceback}
  exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),ns);ns['main']()
 def test_failed_command_is_logged_retired_and_next_command_runs_same_frame(self):
  calls=[];logs=[]
  def failed():
   calls.append('travel');raise ValueError('travel command failed')
   yield
  def healthy():
   calls.append('invite');yield
  bad=failed();good=healthy();routines=[bad,good]
  self.frame(routines,logs)
  self.assertEqual(calls,['travel','invite']);self.assertEqual(routines,[good])
  self.assertEqual(len(logs),1);self.assertIn('ValueError: travel command failed',logs[0][1]);self.assertIn('Traceback',logs[0][1])
 def test_self_removing_completed_command_does_not_interrupt_next_command(self):
  calls=[];logs=[];routines=[]
  def finished():
   routines.remove(done)
   if False:yield
  def healthy():
   calls.append('next command');yield
  done=finished();good=healthy();routines[:]=[done,good]
  self.frame(routines,logs)
  self.assertEqual(calls,['next command']);self.assertEqual(routines,[good]);self.assertEqual(logs,[])
 def test_normal_completion_removes_only_completed_command(self):
  calls=[];logs=[]
  def healthy():calls.append('running');yield
  done=iter(());good=healthy();routines=[done,good]
  self.frame(routines,logs)
  self.assertEqual(routines,[good]);self.assertEqual(calls,['running']);self.assertEqual(logs,[])
if __name__=='__main__':unittest.main()
