from __future__ import annotations
import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest
from enum import Enum, auto
from typing import Any
ROOT = Path(__file__).resolve().parents[3]
class NodeState(Enum):
    RUNNING = auto()
    SUCCESS = auto()
    FAILURE = auto()

class Node:

    def __init__(self, name='', node_type='', node_category='', **_kwargs):
        self.name = name
        self.node_type = node_type
        self.node_category = node_category
        self.blackboard = {}
        self.last_state = None

    @staticmethod
    def _normalize_state(value):
        return value if isinstance(value, NodeState) else None

    def _tick_impl(self):
        raise NotImplementedError

    def tick(self):
        self.last_state = self._tick_impl()
        return self.last_state

    def reset(self):
        self.last_state = None

class ActionNode(Node):

    def __init__(self, action_fn, aftercast_ms=0, name='ActionNode'):
        super().__init__(name=name, node_type='ActionNode', node_category='action')
        self.action_fn = action_fn
        self.aftercast_ms = aftercast_ms

    def _tick_impl(self):
        try:
            return self.action_fn(self)
        except TypeError:
            return self.action_fn()

class BehaviorTree:
    NodeState = NodeState
    Node = Node
    ActionNode = ActionNode

    def __init__(self, root):
        self.root = root
        self.blackboard = root.blackboard

    def tick(self):
        return self.root.tick()

    def reset(self):
        self.root.reset()

class Runtime:

    def __init__(self):
        self.player_xy = (15000.0, 15000.0)
        self.agent_xy = {10: (16051.0, 15183.0), 20: (16051.0, 15183.0)}
        self.valid = {10, 20}
        self.move_calls = []
        self.move_option_snapshots = []
        self.interactions = []
        self.resolutions = [10]
        self.completed = False
        self.hero_options = types.SimpleNamespace(Following=True, Avoidance=True, Looting=True, Targeting=True, Combat=True, Skills=[True, False, True])
        self.hero_writes = 0
        self.hero_options_available = True
        self.hero_set_raises = False
        self.remote_message = types.SimpleNamespace(Active=True, SenderEmail='test@example.invalid', ReceiverEmail='remote@example.invalid', Command=1)
        self.inbox_mode = 'message'

    def resolve(self):
        if len(self.resolutions) > 1:
            return self.resolutions.pop(0)
        return self.resolutions[0]

class FakeAgent:

    @staticmethod
    def GetXY(agent_id):
        return runtime.agent_xy[agent_id]

    @staticmethod
    def IsValid(agent_id):
        return agent_id in runtime.valid

    @staticmethod
    def GetGadgetID(agent_id):
        return 123 if agent_id in runtime.valid else 0

class FakePlayer:

    @staticmethod
    def GetXY():
        return runtime.player_xy

    @staticmethod
    def Move(x, y):
        runtime.move_option_snapshots.append({'Following': runtime.hero_options.Following, 'Avoidance': runtime.hero_options.Avoidance, 'Looting': runtime.hero_options.Looting, 'Targeting': runtime.hero_options.Targeting, 'Combat': runtime.hero_options.Combat, 'Skills': list(runtime.hero_options.Skills)})
        runtime.move_calls.append((float(x), float(y)))
        runtime.player_xy = (float(x), float(y))

    @staticmethod
    def GetAccountEmail():
        return 'test@example.invalid'

    @staticmethod
    def ChangeTarget(_agent_id):
        return None

    @staticmethod
    def Interact(agent_id, _call_target=False):
        runtime.interactions.append(agent_id)

class FakeSharedMemory:

    def GetHeroAIOptionsFromEmail(self, _email):
        if not runtime.hero_options_available:
            return None
        return runtime.hero_options

    def SetHeroAIOptionsByEmail(self, _email, _options):
        if runtime.hero_set_raises:
            raise RuntimeError('HeroAI options write failed')
        runtime.hero_writes += 1

    def GetInbox(self, _index):
        if runtime.inbox_mode == 'raise':
            raise RuntimeError('inbox unavailable')
        if runtime.inbox_mode == 'none':
            return None
        if runtime.inbox_mode == 'mismatch':
            return types.SimpleNamespace(Active=True, SenderEmail='unexpected@example.invalid', ReceiverEmail='remote@example.invalid', Command=1)
        return runtime.remote_message

    def SendMessage(self, _sender, _receiver, _command, _params):
        runtime.remote_message.Active = True
        return 7

    def GetAccountDataFromEmail(self, email):
        return self._account(email)

    def GetAllAccountData(self):
        return [self._account('test@example.invalid'), self._account('remote@example.invalid')]

    @staticmethod
    def _account(email):
        map_data = types.SimpleNamespace(MapID=1, Region=2, Language=0, District=1)
        return types.SimpleNamespace(AccountEmail=email, IsSlotActive=True, PartyID=5, AgentData=types.SimpleNamespace(Map=map_data))

class FakeUtils:

    @staticmethod
    def Distance(left, right):
        return math.dist(left, right)

def _stub_module(name: str, **attributes: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    return module

def _install_module_stubs():
    package_names = ('Py4GWCoreLib', 'Py4GWCoreLib.routines_src', 'Py4GWCoreLib.routines_src.behaviourtrees_src', 'Py4GWCoreLib.py4gwcorelib_src')
    for name in package_names:
        module = types.ModuleType(name)
        module.__path__ = []
        sys.modules[name] = module
    sys.modules['Py4GWCoreLib.Agent'] = _stub_module('Py4GWCoreLib.Agent', Agent=FakeAgent)
    sys.modules['Py4GWCoreLib.Player'] = _stub_module('Py4GWCoreLib.Player', Player=FakePlayer)
    sys.modules['Py4GWCoreLib.GlobalCache'] = _stub_module('Py4GWCoreLib.GlobalCache', GLOBAL_CACHE=types.SimpleNamespace(ShMem=FakeSharedMemory()))
    sys.modules['Py4GWCoreLib.Py4GWcorelib'] = _stub_module('Py4GWCoreLib.Py4GWcorelib', Console=types.SimpleNamespace(MessageType=types.SimpleNamespace(Warning=1, Info=2, Success=3)), ConsoleLog=lambda *_args, **_kwargs: None, Utils=FakeUtils)
    sys.modules['Py4GWCoreLib.py4gwcorelib_src.BehaviorTree'] = _stub_module('Py4GWCoreLib.py4gwcorelib_src.BehaviorTree', BehaviorTree=BehaviorTree)
    sys.modules['Py4GWCoreLib.enums_src'] = types.ModuleType('Py4GWCoreLib.enums_src')
    sys.modules['Py4GWCoreLib.enums_src.GameData_enums'] = _stub_module('Py4GWCoreLib.enums_src.GameData_enums', Range=types.SimpleNamespace(Adjacent=types.SimpleNamespace(value=166.0), Nearby=types.SimpleNamespace(value=252.0), Earshot=types.SimpleNamespace(value=1000.0), Area=types.SimpleNamespace(value=322.0), Spirit=types.SimpleNamespace(value=2500.0), Spellcast=types.SimpleNamespace(value=1248.0)), Allegiance=object)
    sys.modules['Py4GWCoreLib.enums_src.Multiboxing_enums'] = _stub_module('Py4GWCoreLib.enums_src.Multiboxing_enums', SharedCommandType=types.SimpleNamespace(InteractWithTarget=1))
    sys.modules['Py4GWCoreLib.AgentArray'] = _stub_module('Py4GWCoreLib.AgentArray', AgentArray=types.SimpleNamespace(GetGadgetArray=lambda: [10]))
    sys.modules['Py4GWCoreLib.routines_src.Agents'] = _stub_module('Py4GWCoreLib.routines_src.Agents', Agents=types.SimpleNamespace(GetNearestGadgetByID=lambda **_kwargs: 10))
    sys.modules['Py4GWCoreLib.routines_src.Checks'] = _stub_module('Py4GWCoreLib.routines_src.Checks', Checks=object)
    sys.modules['Py4GWCoreLib.routines_src.shared_command_coordination'] = _stub_module('Py4GWCoreLib.routines_src.shared_command_coordination', get_local_route_auxiliary_owner=lambda: None)
    sys.modules['Py4GWCoreLib.routines_src.behaviourtrees_src.composite'] = _stub_module('Py4GWCoreLib.routines_src.behaviourtrees_src.composite', BTCompositeHelpers=object, BTComposite=object)
    sys.modules['Py4GWCoreLib.routines_src.behaviourtrees_src.movement'] = _stub_module('Py4GWCoreLib.routines_src.behaviourtrees_src.movement', BTMovement=object)
    sys.modules['Py4GWCoreLib.routines_src.behaviourtrees_src.player'] = _stub_module('Py4GWCoreLib.routines_src.behaviourtrees_src.player', BTPlayer=object)
    sys.modules['Py4GWCoreLib.native_src'] = types.ModuleType('Py4GWCoreLib.native_src')
    sys.modules['Py4GWCoreLib.native_src.internals'] = types.ModuleType('Py4GWCoreLib.native_src.internals')
    sys.modules['Py4GWCoreLib.native_src.internals.types'] = _stub_module('Py4GWCoreLib.native_src.internals.types', Point2D=tuple, PointOrPath=object, PointPath=types.SimpleNamespace(as_path=lambda value: value), Vec2f=object)
    sys.modules['Py4GWCoreLib.Map'] = _stub_module('Py4GWCoreLib.Map', Map=object)
    sys.modules['Py4GWCoreLib.enums'] = _stub_module('Py4GWCoreLib.enums', SharedCommandType=object)
    sys.modules['Py4GWCoreLib.UIManager'] = _stub_module('Py4GWCoreLib.UIManager', UIManager=object)
    sys.modules['Py4GWCoreLib.enums_src.UI_enums'] = _stub_module('Py4GWCoreLib.enums_src.UI_enums', ControlAction=object)
    sys.modules['Py4GWCoreLib.py4gwcorelib_src.Console'] = _stub_module('Py4GWCoreLib.py4gwcorelib_src.Console', ConsoleLog=lambda *_args, **_kwargs: None, Console=types.SimpleNamespace(MessageType=types.SimpleNamespace(Info=1, Warning=2)))
    sys.modules['Py4GWCoreLib.routines_src.behaviourtrees_src.local_avoidance'] = _stub_module('Py4GWCoreLib.routines_src.behaviourtrees_src.local_avoidance', CircularObstacle=object, choose_avoidance_target=lambda *_args, **_kwargs: None, find_first_blocker=lambda *_args, **_kwargs: None)

_install_module_stubs()
spec = importlib.util.spec_from_file_location("Py4GWCoreLib.routines_src.behaviourtrees_src.agents", ROOT / "Py4GWCoreLib/routines_src/behaviourtrees_src/agents.py")
assert spec is not None and spec.loader is not None
agents_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = agents_module
spec.loader.exec_module(agents_module)
class GadgetInteractionTests(unittest.TestCase):

    def setUp(self):
        global runtime
        runtime = Runtime()
        agents_module._DETACHED_GADGET_COMMANDS.clear()

    def assert_hero_options_restored(self):
        self.assertTrue(runtime.hero_options.Following)
        self.assertTrue(runtime.hero_options.Avoidance)
        self.assertTrue(runtime.hero_options.Looting)
        self.assertTrue(runtime.hero_options.Targeting)
        self.assertTrue(runtime.hero_options.Combat)
        self.assertEqual(runtime.hero_options.Skills, [True, False, True])

    def assert_move_happened_under_exclusive_lease(self, index=0):
        snapshot = runtime.move_option_snapshots[index]
        self.assertFalse(snapshot['Following'])
        self.assertFalse(snapshot['Avoidance'])
        self.assertFalse(snapshot['Looting'])
        self.assertFalse(snapshot['Targeting'])
        self.assertFalse(snapshot['Combat'])
        self.assertEqual(snapshot['Skills'], [False, False, False])

    def build_gadget_remote_wait(self, **overrides):
        values = dict(gadget_id=123, interaction_distance=252.0, interaction_interval_ms=0, account_settle_ms=0, multi_account=True, suspend_hero_ai=False)
        values.update(overrides)
        runtime.player_xy = runtime.agent_xy[10]
        tree = agents_module.BTAgents.MoveAndInteractWithGadget(**values)
        for _ in range(7):
            self.assertEqual(tree.tick(), NodeState.RUNNING)
        return tree

    @staticmethod
    def gadget_state(tree):
        for cell in tree.root.action_fn.__closure__ or ():
            value = cell.cell_contents
            if isinstance(value, dict) and 'phase' in value and ('current_message_index' in value):
                return value
        raise AssertionError('gadget state closure not found')

    def test_public_gadget_owner_reset_restores_heroai_and_stops(self):
        runtime.player_xy = runtime.agent_xy[10]
        tree = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, interaction_distance=100.0, suspend_hero_ai=True)
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertFalse(runtime.hero_options.Following)
        tree.reset()
        self.assertTrue(runtime.hero_options.Following)
        self.assertTrue(runtime.hero_options.Combat)
        self.assertEqual(runtime.hero_options.Skills, [True, False, True])
        self.assertEqual(runtime.move_calls[-1], runtime.player_xy)

    def test_gadget_retains_live_blackboard_ownership_tracking(self):
        tree = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, interaction_distance=100.0, suspend_hero_ai=False)
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertTrue(tree.blackboard['INTERACTION_ACTIVE'])
        tree.reset()
        self.assertFalse(tree.blackboard['INTERACTION_ACTIVE'])

    def test_gadget_reset_preserves_outer_interaction_scope_ownership(self):
        tree = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, interaction_distance=100.0, suspend_hero_ai=False)
        tree.blackboard['INTERACTION_SCOPE_ACTIVE'] = True
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertTrue(tree.blackboard['INTERACTION_ACTIVE'])
        tree.reset()
        self.assertTrue(tree.blackboard['INTERACTION_ACTIVE'])

    def test_gadget_out_of_range_acquires_lease_before_first_approach_move(self):
        runtime.player_xy = (15000.0, 15000.0)
        tree = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, interaction_distance=100.0, suspend_hero_ai=True)
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertEqual(runtime.move_calls, [runtime.agent_xy[10]])
        self.assert_move_happened_under_exclusive_lease()
        self.assertTrue(tree.blackboard['gadget_ownership_acquired'])
        self.assertEqual(tree.blackboard['gadget_target_agent_id'], 10)
        self.assertEqual(tree.blackboard['gadget_target_xy'], runtime.agent_xy[10])
        self.assertGreater(tree.blackboard['gadget_target_distance'], 100.0)
        tree.reset()
        self.assert_hero_options_restored()

    def test_gadget_ownership_acquisition_failure_never_moves_or_interacts(self):
        runtime.player_xy = (15000.0, 15000.0)
        runtime.hero_options_available = False
        tree = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, interaction_distance=100.0, suspend_hero_ai=True)
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertEqual(tree.tick(), NodeState.FAILURE)
        self.assertEqual(runtime.move_calls, [])
        self.assertEqual(runtime.interactions, [])
        self.assertFalse(tree.blackboard['gadget_ownership_acquired'])

    def test_gadget_ownership_write_exception_restores_without_movement(self):
        runtime.player_xy = (15000.0, 15000.0)
        runtime.hero_set_raises = True
        tree = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, interaction_distance=100.0, suspend_hero_ai=True)
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertEqual(tree.tick(), NodeState.FAILURE)
        self.assertEqual(runtime.move_calls, [])
        self.assertEqual(runtime.interactions, [])
        self.assert_hero_options_restored()

    def test_gadget_combat_releases_then_reacquires_before_resuming_move(self):
        runtime.player_xy = (15000.0, 15000.0)
        tree = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, interaction_distance=100.0, suspend_hero_ai=True, pause_on_combat=True)
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assert_move_happened_under_exclusive_lease(0)
        tree.blackboard['COMBAT_ACTIVE'] = True
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertTrue(tree.blackboard['gadget_combat_paused'])
        self.assert_hero_options_restored()
        tree.blackboard['COMBAT_ACTIVE'] = False
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertFalse(tree.blackboard['gadget_combat_paused'])
        self.assert_move_happened_under_exclusive_lease(-1)
        tree.reset()
        self.assert_hero_options_restored()

    def test_gadget_local_exception_restores_exact_heroai_snapshot(self):
        runtime.player_xy = (15000.0, 15000.0)
        tree = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, interaction_distance=100.0, suspend_hero_ai=True)
        self.assertEqual(tree.tick(), NodeState.RUNNING)
        self.assertEqual(tree.tick(), NodeState.RUNNING)

        class ExplodingBlackboard(dict):

            def get(self, *_args, **_kwargs):
                raise RuntimeError('blackboard read failed')
        tree.root.blackboard = ExplodingBlackboard()
        self.assertEqual(tree.tick(), NodeState.FAILURE)
        self.assert_hero_options_restored()

    def test_gadget_reset_quarantines_active_remote_command(self):
        agents_module._DETACHED_GADGET_COMMANDS.clear()
        tree = self.build_gadget_remote_wait()
        tree.reset()
        self.assertEqual(len(agents_module._DETACHED_GADGET_COMMANDS), 1)
        successor = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, multi_account=True, suspend_hero_ai=False)
        self.assertEqual(successor.tick(), NodeState.RUNNING)
        self.assertEqual(successor.blackboard['gadget_detached_remote_commands'], 1)
        runtime.remote_message.Active = False
        self.assertEqual(successor.tick(), NodeState.RUNNING)
        self.assertEqual(successor.blackboard['gadget_detached_remote_commands'], 0)

    def test_gadget_unknown_remote_status_is_fail_closed_and_bounded(self):
        agents_module._DETACHED_GADGET_COMMANDS.clear()
        tree = self.build_gadget_remote_wait()
        runtime.inbox_mode = 'raise'
        tree.reset()
        self.assertEqual(len(agents_module._DETACHED_GADGET_COMMANDS), 1)
        successor = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, multi_account=True, suspend_hero_ai=False, detached_command_unknown_timeout_ms=1000)
        self.assertEqual(successor.tick(), NodeState.RUNNING)
        self.assertEqual(successor.blackboard['gadget_detached_remote_commands'], 1)
        self.assertEqual(successor.blackboard['gadget_detached_remote_unknown_expired'], 0)
        for key in tuple(agents_module._DETACHED_GADGET_COMMANDS):
            agents_module._DETACHED_GADGET_COMMANDS[key] -= 2.0
        self.assertEqual(successor.tick(), NodeState.FAILURE)
        self.assertEqual(successor.blackboard['gadget_detached_remote_unknown_expired'], 1)
        self.assertEqual(len(agents_module._DETACHED_GADGET_COMMANDS), 1)

    def test_gadget_none_and_mismatched_remote_status_remain_quarantined(self):
        for inbox_mode in ('none', 'mismatch'):
            with self.subTest(inbox_mode=inbox_mode):
                agents_module._DETACHED_GADGET_COMMANDS.clear()
                runtime.inbox_mode = 'message'
                runtime.remote_message.Active = True
                tree = self.build_gadget_remote_wait()
                runtime.inbox_mode = inbox_mode
                tree.reset()
                self.assertEqual(len(agents_module._DETACHED_GADGET_COMMANDS), 1)

    def test_gadget_user_interrupt_precedes_detached_quarantine_wait(self):
        agents_module._DETACHED_GADGET_COMMANDS.clear()
        agents_module._DETACHED_GADGET_COMMANDS['test@example.invalid', 'remote@example.invalid', 7] = agents_module.time.monotonic()
        tree = agents_module.BTAgents.MoveAndInteractWithGadget(gadget_id=123, multi_account=True, suspend_hero_ai=False)
        tree.blackboard['USER_INTERRUPT_ACTIVE'] = True
        self.assertEqual(tree.tick(), NodeState.FAILURE)
        self.assertEqual(len(agents_module._DETACHED_GADGET_COMMANDS), 1)

    def test_gadget_timeout_retains_active_remote_command(self):
        agents_module._DETACHED_GADGET_COMMANDS.clear()
        tree = self.build_gadget_remote_wait(timeout_ms=50)
        state = self.gadget_state(tree)
        state['started_at'] -= 1.0
        self.assertEqual(tree.tick(), NodeState.FAILURE)
        self.assertEqual(len(agents_module._DETACHED_GADGET_COMMANDS), 1)

    def test_gadget_exception_retains_active_remote_command(self):
        agents_module._DETACHED_GADGET_COMMANDS.clear()
        tree = self.build_gadget_remote_wait()

        class ExplodingBlackboard(dict):

            def get(self, *_args, **_kwargs):
                raise RuntimeError('blackboard read failed')
        tree.root.blackboard = ExplodingBlackboard()
        self.assertEqual(tree.tick(), NodeState.FAILURE)
        self.assertEqual(len(agents_module._DETACHED_GADGET_COMMANDS), 1)

if __name__ == "__main__":
    unittest.main(verbosity=2)
