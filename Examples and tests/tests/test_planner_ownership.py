"""Real planner/movement trees with native clock, position and commands doubled."""
from __future__ import annotations
import ast, builtins, dataclasses, math, random, unittest
from typing import Any
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[2]
CORE=ROOT/'Py4GWCoreLib'
def definitions(path,namespace,names=None):
    nodes: list[ast.stmt]=[n for n in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and (names is None or n.name in names)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(path),'exec',flags=__import__('__future__').annotations.compiler_flag),namespace)
class NativeWorld:
    bt: Any
    state: Any
    ns: dict[str, Any]
    host: Any
    bb: dict[str, Any]

    def __init__(self):
        self.clock = 10000
        self.map_id = 584
        self.uptime_offset = 0
        self.explorable = True
        self.dead = False
        self.holding = False
        self.model = 24350
        self.item_type = 6
        self.effect = False
        self.xy = (0.0, 0.0)
        self.ground = {}
        self.interactions = []
        self.moves = []
        self.name_requests = []

        class Icons:

            def __getattr__(self, name):
                return ''
        ns: dict[str, Any] = dict(__name__=__name__, ColorPalette=NS(GetColor=lambda name: None), IconsFontAwesome5=Icons(), Console=NS(MessageType=Icons()), ConsoleLog=lambda *a, **k: None, Utils=NS(GetBaseTimestamp=lambda: self.clock))
        exec('from abc import ABC, abstractmethod\nfrom enum import Enum, auto\nfrom typing import *\nimport uuid, inspect', ns)
        definitions(CORE / 'py4gwcorelib_src/BehaviorTree.py', ns, {'BehaviorTree'})
        self.bt = ns['BehaviorTree']
        self.bt._ensure_blackboard_data = lambda tree: None
        self.state = self.bt.NodeState
        ns.update(math=math, dataclass=dataclasses.dataclass, time=NS(monotonic=lambda: self.clock / 1000), Player=NS(GetAgentID=lambda: 1, GetXY=lambda: self.xy, Move=lambda *xy: self.moves.append(xy), ChangeTarget=lambda agent: None, Interact=lambda agent, *a: self.interactions.append(agent)), Map=NS(GetMapID=lambda: self.map_id, IsExplorable=lambda: self.explorable, GetInstanceUptime=lambda: self.clock - self.uptime_offset), Agent=NS(IsHoldingItem=lambda agent: self.holding, IsDead=lambda agent: self.dead, GetWeaponExtraData=lambda agent: (77, 0, 0, 0), IsValid=lambda agent: agent in self.ground, IsItem=lambda agent: agent in self.ground, GetXY=lambda agent: self.ground[agent]['xy'], GetItemAgentOwnerID=lambda agent: self.ground[agent]['owner'], GetItemAgentItemID=lambda agent: agent + 100, GetNameByID=lambda agent: self.ground[agent].get('name', '')), Item=NS(GetModelID=lambda item: self.model if item == 77 else self.ground[item - 100]['model'], GetItemType=lambda item: (self.item_type, 'Bundle'), GetName=lambda item: 'Asura Flame Staff', RequestName=lambda item: self.name_requests.append(item)), Effects=NS(HasEffect=lambda agent, skill: self.effect), AgentArray=NS(GetItemArray=lambda: list(self.ground), Filter=NS(ByDistance=lambda agents, xy, radius: [a for a in agents if math.dist(xy, self.ground[a]['xy']) <= radius]), Sort=NS(ByDistance=lambda agents, xy: sorted(agents, key=lambda a: math.dist(xy, self.ground[a]['xy'])))))
        ns['GLOBAL_CACHE'] = NS(Item=NS(IsNameReady=lambda item: False, RequestName=lambda item: self.name_requests.append(item)))
        self.ns = ns

    def load_movement(self):
        ns = self.ns
        self.keys = []

        def down(key, *args):
            self.keys.append(('down', key))
            if key == 1:
                self.holding = False
                # Drop-key behavior is outside this movement-only fixture.
                pass
        ui = NS(Keydown=down, Keyup=lambda key, *a: self.keys.append(('up', key)))
        control = NS(ControlAction_DropItem=NS(value=1), ControlAction_StrafeLeft=NS(value=2), ControlAction_StrafeRight=NS(value=3))

        class Values:

            def __getattr__(self, name):
                return NS(value=1000)

        def path_to(x, y, **kwargs):
            if False:
                yield None
            return [(x, y)]

        def path_points(pos):
            if hasattr(pos, 'x'):
                return [pos]
            if isinstance(pos, tuple) and len(pos) == 2 and isinstance(pos[0], (float, int)):
                return [NS(x=pos[0], y=pos[1])]
            return [p if hasattr(p, 'x') else NS(x=p[0], y=p[1]) for p in pos]
        ns['Utils'].Distance = math.dist
        ns['Map'].IsMapLoading = lambda: False
        ns['Agent'].GetAgentByID = lambda agent: None
        native = {'Py4GWcorelib': NS(Utils=ns['Utils']), 'Pathing': NS(AutoPathing=lambda: NS(get_path_to=path_to, get_navmesh=lambda: object())), 'Party': NS(Party=NS(IsPartyLeader=lambda: False, IsPartyMember=lambda agent: False)), 'AgentArray': NS(AgentArray=ns['AgentArray']), 'UIManager': NS(UIManager=ui), 'enums_src.UI_enums': NS(ControlAction=control), 'player': NS(BTPlayer=NS()), 'party': NS(_apply_multibox_all_flag=None)}
        self.native = native

        def importing(name, globals=None, locals=None, fromlist=(), level=0):
            if level and name in native:
                return native[name]
            return builtins.__import__(name, globals, locals, fromlist, level)
        ns['__builtins__'] = dict(vars(builtins), __import__=importing)
        ns.update(random=random, Range=Values(), Allegiance=Values(), DEFAULT_MOVE_TOLERANCE=150.0, PointPath=NS(as_path=path_points), Checks=NS(Player=NS(IsDead=lambda: self.dead, IsCasting=lambda: False), Map=NS(MapValid=lambda: self.explorable)), get_local_route_auxiliary_owner=lambda: '', UIManager=ui, ControlAction=control, _log=lambda *a, **k: None, _fail_log=lambda *a, **k: None, PySystem=NS(Console=NS(Log=lambda *a: None, MessageType=Values())))
        definitions(CORE / 'routines_src/behaviourtrees_src/local_avoidance.py', ns)
        definitions(CORE / 'routines_src/behaviourtrees_src/composite.py', ns)
        definitions(CORE / 'routines_src/behaviourtrees_src/movement.py', ns, {'BTMovement'})
def world():
    w=NativeWorld();w.load_movement();n=w.ns
    w.native['Agents']=NS(Agents=NS(GetNearestEnemy=lambda distance:0))
    n['Player'].GetAccountEmail=lambda:'test-account'
    n['GLOBAL_CACHE'].ShMem=NS(PreviewNextMessage=lambda _:(-1,None))
    n['SharedCommandType']=NS(PickUpLoot=1)
    definitions(CORE/'botting_tree_src/enums.py',n)
    definitions(CORE/'botting_tree_src/ticks.py',n,{'BottingTreeTicksMixin'})
    n['Routines']=NS(Checks=NS(Party=NS(IsPartyWiped=lambda:w.dead)))
    n['GLOBAL_CACHE'].Party=NS(IsPartyDefeated=lambda:w.dead)
    Host = type('Host', (n['BottingTreeTicksMixin'],), {})
    h=Host();h.started=True;h.paused=False;h.pause_on_combat=True;h._last_planner_gate_state=None
    h.RestoreAccountIsolation=lambda:None;h.GetNamedPlannerStepNames=lambda:[]
    w.host=h;w.bb={};return w

def tick(w):
    w.host._tick_planner(NS(blackboard=w.bb))

class PlannerOwnershipTests(unittest.TestCase):
    def test_exclusive_owner_withholds_route_commands_and_resumes_same_cursor(self):
        for gate in ('combat','loot','pause','wipe'):
            with self.subTest(gate=gate):
                w=world();h=w.host
                move=w.ns['BTMovement'].MoveDirect([NS(x=1000.,y=0.),NS(x=2000.,y=0.)],timeout_ms=1000,log=False)
                h.planner_tree=move
                tick(w);w.clock+=100;tick(w)
                before=len(w.moves);cursor=w.bb['move_path_index']
                self.assertGreater(before,0)
                if gate=='combat':w.bb['COMBAT_ACTIVE']=True
                elif gate=='loot':w.bb['LOOTING_ACTIVE']=True
                elif gate=='pause':h.paused=True
                else:w.dead=True
                for _ in range(10):w.clock+=1000;tick(w)
                self.assertEqual(len(w.moves),before)
                w.bb['COMBAT_ACTIVE']=False;w.bb['LOOTING_ACTIVE']=False;h.paused=False;w.dead=False
                tick(w)
                self.assertNotEqual(w.bb.get('move_state'),'failed')
                self.assertNotIn('restart_step_name_request',w.bb)
                self.assertEqual(w.bb.get('move_path_index'),cursor)
                self.assertTrue(h.started)
                w.xy=(1000.,0.)
                for _ in range(5):w.clock+=50;tick(w)
                self.assertGreaterEqual(w.bb['move_path_index'],1)
                self.assertEqual(w.moves[-1],(2000.,0.))

    def test_real_ungated_stall_still_times_out(self):
        w=world();h=w.host
        h.planner_tree=w.ns['BTMovement'].MoveDirect([NS(x=1000.,y=0.)],timeout_ms=1000,log=False)
        for _ in range(15):tick(w);w.clock+=300
        self.assertEqual(w.bb.get('move_state'),'failed')

    def test_combat_and_loot_do_not_tick_other_planner_actions(self):
        for flag in ('COMBAT_ACTIVE','LOOTING_ACTIVE'):
            with self.subTest(flag=flag):
                w=world();calls=[]
                w.host.planner_tree=NS(tick=lambda:calls.append(True) or w.state.RUNNING)
                w.bb[flag]=True;tick(w)
                self.assertEqual(calls,[])
                w.bb[flag]=False;tick(w)
                self.assertEqual(calls,[True])

    def test_pause_on_combat_false_retains_route_execution(self):
        w=world();h=w.host;h.pause_on_combat=False;w.bb['COMBAT_ACTIVE']=True
        calls=[];h.planner_tree=NS(tick=lambda:calls.append(True) or w.state.RUNNING)
        tick(w);self.assertEqual(calls,[True])

if __name__=='__main__':unittest.main()
