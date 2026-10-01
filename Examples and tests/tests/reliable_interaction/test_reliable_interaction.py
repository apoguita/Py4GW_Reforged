from __future__ import annotations

import importlib.util
import math
import pathlib
import sys
import types
import unittest
from unittest.mock import patch


MODULE_PATH = (
    pathlib.Path(__file__).parents[3]
    / "Py4GWCoreLib"
    / "routines_src"
    / "reliable_interaction.py"
)
SPEC = importlib.util.spec_from_file_location("reliable_interaction_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ri = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ri
SPEC.loader.exec_module(ri)


class FakeRuntime:
    def __init__(self, behavior: str):
        self.behavior = behavior
        self.clock = 0.0
        self.player = (0.0, 0.0)
        self.agent = 10
        self.agent_position = (100.0, 0.0)
        self.visible = False
        self.buttons = 0
        self.button_labels = ()
        self.satisfied = False
        self.hostile = False
        self.pause_count = 0
        self.restore_count = 0
        self.resolve_count = 0
        self.interact_count = 0
        self.click_count = 0
        self.sent_dialog_ids = []
        self.close_count = 0
        self.events = []
        self.popup_at = None
        self.clicked_choices = []
        self.scroll_count = 0
        self.scroll_deltas = []

    def now(self):
        return self.clock

    def advance(self, seconds=0.11):
        self.clock += seconds

    def pause_automation(self):
        self.pause_count += 1

    def restore_automation(self):
        self.restore_count += 1

    def cancel_movement(self):
        return

    def close_stale_dialog(self):
        self.visible = False
        self.buttons = 0
        self.button_labels = ()
        self.close_count += 1

    def resolve_target(self, _target):
        self.resolve_count += 1
        return self.agent

    def agent_xy(self, _agent_id):
        return self.agent_position

    def agent_model_id(self, _agent_id):
        return 42

    def player_xy(self):
        return self.player

    def move_to(self, xy):
        self.player = xy
        if self.behavior == "walk_over":
            self.satisfied = True

    def interact(self, _agent_id):
        self.interact_count += 1
        if self.behavior in (
            "raw",
            "visible",
            "reward",
            "challenge",
            "delayed_visible",
            "delayed_popup",
            "two_page_visible",
            "two_page_label_visible",
            "two_page_scroll_visible",
            "visible_then_raw",
        ):
            self.visible = True
            self.buttons = 0 if self.behavior in ("raw", "delayed_visible") else 2
            if self.behavior == "two_page_label_visible":
                self.button_labels = ("Captured", "Naga Oil", "Battle in the Sewers")
                self.buttons = len(self.button_labels)
            elif self.behavior == "two_page_scroll_visible":
                self.button_labels = ("Stolen Eggs", "Fort Aspenwood", "The Jade Quarry")
                self.buttons = len(self.button_labels)
        if self.behavior in ("automatic", "gadget"):
            self.satisfied = True

    def dialog_visible(self):
        if self.popup_at is not None and self.clock >= self.popup_at:
            self.visible = True
            self.popup_at = None
        return self.visible

    def dialog_button_count(self):
        return self.buttons

    def dialog_button_labels(self):
        return self.button_labels

    def scroll_dialog(self, delta):
        self.scroll_count += 1
        self.scroll_deltas.append(delta)
        if self.behavior == "two_page_scroll_visible":
            self.buttons = 2
        return True

    def click_dialog_button(self, _choice):
        self.click_count += 1
        self.clicked_choices.append(_choice)
        if self.behavior == "two_page_label_visible" and self.click_count == 1:
            self.button_labels = (
                "Just doing my duty to the emperor.",
                "On second thought, it does sound foolhardy.",
            )
            self.buttons = len(self.button_labels)
        elif self.behavior == "two_page_label_visible" and self.click_count == 2:
            self.satisfied = True
        elif self.behavior == "two_page_scroll_visible" and self.click_count == 1:
            self.button_labels = (
                "Hang on, little ones! I'll save you!",
                "Have you ever tried pickled turtle eggs?",
            )
            # The logical response exists, but the native button frame is
            # below the viewport until the dialogue page is scrolled.
            self.buttons = 0
        elif self.behavior == "two_page_scroll_visible" and self.click_count == 2:
            self.satisfied = True
        elif self.behavior == "two_page_visible" and self.click_count == 1:
            # Page one is replaced by another populated page under the same
            # visible dialog frame. The postcondition is not yet satisfied.
            self.buttons = 2
        elif self.behavior == "two_page_visible" and self.click_count == 2:
            self.satisfied = True
        elif self.behavior == "visible_then_raw":
            # The visible choice opens a buttonless conclusion page whose
            # Continue response is exposed only by its raw context id.
            self.visible = True
            self.buttons = 0
        elif self.behavior == "challenge" and self.click_count == 1:
            self.hostile = True
        elif self.behavior == "delayed_popup":
            self.satisfied = True
            self.visible = False
            self.buttons = 0
            self.popup_at = self.clock + 0.3
        else:
            self.satisfied = True
        return True

    def send_dialog(self, _dialog_id):
        self.sent_dialog_ids.append(int(_dialog_id))
        self.satisfied = True

    def verify(self, _postcondition):
        return self.satisfied

    def is_hostile(self, _agent_id):
        return self.hostile

    def emit(self, event):
        self.events.append(event)


def make_spec(profile, *, dialog=None, attempts=2):
    return ri.InteractionSpec(
        name=f"test {profile.value}",
        profile=profile,
        target=ri.TargetSpec(
            kind=ri.TargetKind.LOCATION if profile == ri.InteractionProfile.WALK_OVER else ri.TargetKind.LIVING,
            model_id=42,
            expected_xy=(100.0, 0.0),
        ),
        approach=ri.ApproachSpec(player_approach_xy=(95.0, 0.0), tolerance=5.0),
        dialog=dialog or ri.DialogSpec(),
        postcondition=ri.PostconditionSpec(ri.PostconditionKind.CUSTOM, description="fake"),
        retry=ri.RetryPolicy(max_attempts=attempts, pause_settle_ms=0, retry_delay_ms=0),
    )


def run(controller, runtime, limit=100):
    for _ in range(limit):
        status = controller.tick()
        if status != ri.InteractionStatus.RUNNING:
            return status
        runtime.advance()
    raise AssertionError(f"controller did not finish; stage={controller.stage}")


class FakeRouteExecutor:
    def __init__(self, runtime, *, terminal=ri.InteractionStatus.SUCCESS, custom_exit_false=False):
        self.runtime = runtime
        self.terminal = terminal
        self.custom_exit_false = custom_exit_false
        self.points = ()
        self.tolerance = 0.0
        self.handoff_ready = None
        self.start_count = 0
        self.tick_count = 0
        self.cancel_count = 0

    def start(self, route_points, tolerance, handoff_ready):
        self.points = route_points
        self.tolerance = tolerance
        self.handoff_ready = handoff_ready
        self.start_count += 1

    def tick(self):
        self.tick_count += 1
        if self.terminal == ri.InteractionStatus.FAILURE:
            return self.terminal
        self.runtime.player = self.points[-1]
        if self.custom_exit_false and self.handoff_ready and self.handoff_ready():
            return ri.InteractionStatus.FAILURE
        return self.terminal

    def cancel(self):
        self.cancel_count += 1


def make_boundary(*, route_endpoint=(-100.0, 0.0), interaction=None):
    return ri.InteractionBoundarySpec(
        name="safe route boundary",
        route_points=((-300.0, 0.0), route_endpoint),
        route_standoff_xy=route_endpoint,
        route_tolerance=30.0,
        handoff_radius=75.0,
        interaction=interaction or make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER),
    )


class ReliableInteractionTests(unittest.TestCase):
    def test_controller_publishes_and_clears_interaction_ownership(self):
        refreshed = []
        cleared = []
        coordination = types.SimpleNamespace(
            refresh_local_reliable_interaction=lambda token, **fields: refreshed.append(
                (token, fields)
            ),
            clear_local_reliable_interaction=lambda token: cleared.append(token),
        )
        runtime = FakeRuntime("automatic")
        controller = ri.ReliableInteractionController(
            make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER),
            runtime,
        )

        with patch.dict(
            sys.modules,
            {"Py4GWCoreLib.routines_src.shared_command_coordination": coordination},
        ):
            self.assertEqual(run(controller, runtime), ri.InteractionStatus.SUCCESS)

        self.assertGreater(len(refreshed), 1)
        tokens = {id(token) for token, _fields in refreshed}
        self.assertEqual(len(tokens), 1)
        self.assertEqual(refreshed[0][1]["name"], "test automatic_npc_or_beacon_trigger")
        self.assertEqual(cleared, [refreshed[0][0]])

    def test_controller_cancel_and_runtime_exception_clear_ownership(self):
        active = set()
        coordination = types.SimpleNamespace(
            refresh_local_reliable_interaction=lambda token, **_fields: active.add(token),
            clear_local_reliable_interaction=lambda token: active.discard(token),
        )

        with patch.dict(
            sys.modules,
            {"Py4GWCoreLib.routines_src.shared_command_coordination": coordination},
        ):
            runtime = FakeRuntime("automatic")
            cancelled = ri.ReliableInteractionController(
                make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER),
                runtime,
            )
            cancelled.tick()
            self.assertTrue(active)
            cancelled.cancel("user stop")
            self.assertFalse(active)

            broken_runtime = FakeRuntime("automatic")
            broken_runtime.verify = lambda _postcondition: (_ for _ in ()).throw(
                RuntimeError("boom")
            )
            broken = ri.ReliableInteractionController(
                make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER),
                broken_runtime,
            )
            self.assertEqual(broken.tick(), ri.InteractionStatus.FAILURE)
            self.assertFalse(active)

    def test_coroutine_adapter_defers_initial_interaction_during_auxiliary_owner(self):
        runtime = FakeRuntime("automatic")
        controller = ri.ReliableInteractionController(
            make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER),
            runtime,
        )
        waits = []

        def wait(milliseconds):
            waits.append(milliseconds)
            yield None

        adapter = ri.run_coroutine_adapter(controller, wait)
        with patch.object(ri, "_local_route_auxiliary_active", side_effect=[True, False]):
            next(adapter)
            self.assertEqual(controller.stage, "new")
            self.assertEqual(runtime.pause_count, 0)
            next(adapter)

        self.assertEqual(controller.stage, "pause_settle")
        self.assertEqual(runtime.pause_count, 1)
        self.assertEqual(len(waits), 2)
        adapter.close()

    def test_boundary_adapter_cannot_handoff_during_auxiliary_owner(self):
        runtime = FakeRuntime("automatic")
        runtime.player = (-500.0, 0.0)
        route = FakeRouteExecutor(runtime)
        controller = ri.InteractionBoundaryController(make_boundary(), runtime, route)
        waits = []

        def wait(milliseconds):
            waits.append(milliseconds)
            yield None

        adapter = ri.run_boundary_coroutine_adapter(controller, wait)
        with patch.object(ri, "_local_route_auxiliary_active", side_effect=[True, False]):
            next(adapter)
            self.assertEqual(controller.stage, "new")
            self.assertEqual(route.start_count, 0)
            self.assertEqual(runtime.pause_count, 0)
            next(adapter)

        self.assertEqual(route.start_count, 1)
        self.assertEqual(controller.stage, "interaction")
        self.assertEqual(len(waits), 2)
        adapter.close()

    def test_botting_tree_adapter_defers_initial_interaction_during_auxiliary_owner(self):
        class NodeState:
            RUNNING = "running"
            SUCCESS = "success"
            FAILURE = "failure"

        class ActionNode:
            def __init__(self, name, action_fn, aftercast_ms=0):
                self.name = name
                self.action_fn = action_fn

            def reset(self):
                return None

        class FakeBehaviorTree:
            def __init__(self, root):
                self.root = root

            def tick(self):
                return self.root.action_fn()

            def reset(self):
                self.root.reset()

        FakeBehaviorTree.NodeState = NodeState
        FakeBehaviorTree.ActionNode = ActionNode

        runtime = FakeRuntime("automatic")
        behavior_module = types.SimpleNamespace(BehaviorTree=FakeBehaviorTree)
        with patch.dict(
            sys.modules,
            {"Py4GWCoreLib.py4gwcorelib_src.BehaviorTree": behavior_module},
        ):
            tree = ri.build_botting_tree_action(
                make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER),
                runtime,
            )
            with patch.object(ri, "_local_route_auxiliary_active", side_effect=[True, False]):
                self.assertEqual(tree.tick(), NodeState.RUNNING)
                self.assertEqual(runtime.pause_count, 0)
                self.assertEqual(tree.tick(), NodeState.RUNNING)

        self.assertEqual(runtime.pause_count, 1)
        tree.reset()

    def test_mamp_geometry_rejects_the_old_route_to_final_approach(self):
        mamp = ri.InteractionSpec(
            name="Start G.O.L.E.M. at Mamp",
            profile=ri.InteractionProfile.VISIBLE_CHOICE,
            target=ri.TargetSpec(
                kind=ri.TargetKind.NPC,
                model_id=6766,
                expected_xy=(16051.0, 15183.0),
                search_radius=1200.0,
            ),
            approach=ri.ApproachSpec(player_approach_xy=(16082.28, 15253.92)),
            dialog=ri.DialogSpec(visible_buttons=(1, 1)),
            postcondition=ri.PostconditionSpec(ri.PostconditionKind.MAP_CHANGED),
        )
        boundary = ri.InteractionBoundarySpec(
            name="G.O.L.E.M. route-to-Mamp",
            route_points=((15000.0, 15000.0), (16082.28, 15253.92)),
            route_standoff_xy=(16082.28, 15253.92),
            interaction=mamp,
        )
        with self.assertRaisesRegex(
            ri.InteractionBoundaryValidationError,
            "reuses the final player approach coordinate",
        ):
            boundary.validate()

    def test_mamp_geometry_accepts_a_distinct_resolvable_standoff(self):
        mamp = ri.InteractionSpec(
            name="Start G.O.L.E.M. at Mamp",
            profile=ri.InteractionProfile.VISIBLE_CHOICE,
            target=ri.TargetSpec(
                kind=ri.TargetKind.NPC,
                model_id=6766,
                expected_xy=(16051.0, 15183.0),
                search_radius=1200.0,
            ),
            approach=ri.ApproachSpec(player_approach_xy=(16082.28, 15253.92)),
            dialog=ri.DialogSpec(visible_buttons=(1, 1)),
            postcondition=ri.PostconditionSpec(ri.PostconditionKind.MAP_CHANGED),
        )
        # This endpoint remains well clear of both Mamp and the model-51 NPC
        # observed at (16043.93, 15260.60), while Mamp remains resolvable.
        boundary = ri.InteractionBoundarySpec(
            name="G.O.L.E.M. route-to-Mamp",
            route_points=((15000.0, 15000.0), (15750.0, 15250.0)),
            route_standoff_xy=(15750.0, 15250.0),
            interaction=mamp,
        )
        boundary.validate()

    def test_route_endpoint_equal_to_target_is_rejected_and_logged(self):
        runtime = FakeRuntime("automatic")
        spec = make_boundary(route_endpoint=(100.0, 0.0))
        route = FakeRouteExecutor(runtime)
        with self.assertRaisesRegex(
            ri.InteractionBoundaryValidationError,
            "reuses the live target coordinate",
        ):
            ri.InteractionBoundaryController(spec, runtime, route)
        failures = [
            event for event in runtime.events
            if event["event"] == "boundary_construction_validation_failed"
        ]
        self.assertEqual(len(failures), 1)

    def test_valid_standoff_hands_off_and_interacts_successfully(self):
        runtime = FakeRuntime("automatic")
        runtime.player = (-500.0, 0.0)
        route = FakeRouteExecutor(runtime)
        controller = ri.InteractionBoundaryController(make_boundary(), runtime, route)
        self.assertEqual(run(controller, runtime, limit=200), ri.InteractionStatus.SUCCESS)
        self.assertEqual(runtime.interact_count, 1)
        event_names = [event["event"] for event in runtime.events]
        for event_name in (
            "route_boundary_entered",
            "target_resolvable_from_standoff",
            "handoff_to_interaction_controller",
            "postcondition_verified",
        ):
            self.assertIn(event_name, event_names)
        self.assertLess(
            event_names.index("handoff_to_interaction_controller"),
            event_names.index("interaction_sent"),
        )

    def test_custom_exit_false_at_safe_boundary_is_not_treated_as_route_failure(self):
        runtime = FakeRuntime("automatic")
        runtime.player = (-500.0, 0.0)
        route = FakeRouteExecutor(runtime, custom_exit_false=True)
        controller = ri.InteractionBoundaryController(make_boundary(), runtime, route)
        self.assertEqual(run(controller, runtime, limit=200), ri.InteractionStatus.SUCCESS)
        self.assertEqual(route.tick_count, 1)
        self.assertEqual(runtime.interact_count, 1)

    def test_mamp_collision_proximity_cannot_trap_the_safe_route(self):
        runtime = FakeRuntime("automatic")
        runtime.player = (15000.0, 15000.0)
        runtime.agent_position = (16051.0, 15183.0)
        interaction = ri.InteractionSpec(
            name="generic collision-sensitive NPC interaction",
            profile=ri.InteractionProfile.AUTOMATIC_TRIGGER,
            target=ri.TargetSpec(
                kind=ri.TargetKind.NPC,
                model_id=42,
                expected_xy=(16051.0, 15183.0),
                search_radius=1200.0,
            ),
            approach=ri.ApproachSpec(
                player_approach_xy=(16082.28, 15253.92),
                tolerance=90.0,
                target_tolerance=100.0,
            ),
            postcondition=ri.PostconditionSpec(ri.PostconditionKind.CUSTOM),
            retry=ri.RetryPolicy(max_attempts=1, pause_settle_ms=0),
        )

        class CollisionAwareRoute(FakeRouteExecutor):
            def tick(self):
                self.tick_count += 1
                blocker_xy = (16043.93, 15260.60)
                if math.dist(self.points[-1], blocker_xy) <= 50.0:
                    return ri.InteractionStatus.RUNNING
                self.runtime.player = self.points[-1]
                return ri.InteractionStatus.SUCCESS

        boundary = ri.InteractionBoundarySpec(
            name="generic safe NPC boundary",
            route_points=((15000.0, 15000.0), (15750.0, 15250.0)),
            route_standoff_xy=(15750.0, 15250.0),
            route_tolerance=150.0,
            handoff_radius=250.0,
            interaction=interaction,
        )
        route = CollisionAwareRoute(runtime)
        controller = ri.InteractionBoundaryController(boundary, runtime, route)
        self.assertEqual(run(controller, runtime, limit=200), ri.InteractionStatus.SUCCESS)
        self.assertEqual(route.tick_count, 1)
        self.assertEqual(runtime.interact_count, 1)

    def test_route_failure_blocks_before_required_interaction(self):
        runtime = FakeRuntime("automatic")
        runtime.player = (-500.0, 0.0)
        route = FakeRouteExecutor(runtime, terminal=ri.InteractionStatus.FAILURE)
        controller = ri.InteractionBoundaryController(make_boundary(), runtime, route)
        self.assertEqual(run(controller, runtime), ri.InteractionStatus.FAILURE)
        self.assertEqual(runtime.interact_count, 0)
        self.assertTrue(
            any(
                event["event"] == "boundary_runtime_validation_failed"
                for event in runtime.events
            )
        )

    def test_required_interaction_failure_blocks_after_successful_handoff(self):
        runtime = FakeRuntime("never")
        runtime.player = (-500.0, 0.0)
        failed_interaction = make_spec(
            ri.InteractionProfile.AUTOMATIC_TRIGGER,
            attempts=1,
        )
        failed_interaction = ri.InteractionSpec(
            **{
                **failed_interaction.__dict__,
                "retry": ri.RetryPolicy(
                    max_attempts=1,
                    pause_settle_ms=0,
                    verify_timeout_ms=100,
                    retry_delay_ms=0,
                ),
            }
        )
        boundary = make_boundary(interaction=failed_interaction)
        controller = ri.InteractionBoundaryController(
            boundary,
            runtime,
            FakeRouteExecutor(runtime),
        )
        self.assertEqual(run(controller, runtime, limit=100), ri.InteractionStatus.FAILURE)
        self.assertEqual(runtime.interact_count, 1)
        self.assertTrue(
            any(
                event["event"] == "boundary_result"
                and event["success"] is False
                and event["reason"] == "required interaction failed"
                for event in runtime.events
            )
        )

    def test_boundary_cancel_during_interaction_restores_automation_and_movement(self):
        runtime = FakeRuntime("never")
        runtime.player = (-500.0, 0.0)
        route = FakeRouteExecutor(runtime)
        controller = ri.InteractionBoundaryController(make_boundary(), runtime, route)
        for _ in range(20):
            controller.tick()
            if runtime.pause_count:
                break
            runtime.advance()
        self.assertEqual(runtime.pause_count, 1)
        controller.cancel("test restart")
        self.assertEqual(controller.result, ri.InteractionStatus.FAILURE)
        self.assertEqual(runtime.restore_count, 1)
        self.assertGreaterEqual(route.cancel_count, 1)

    def test_boundary_coroutine_close_cancels_route_before_handoff(self):
        runtime = FakeRuntime("never")
        runtime.player = (-500.0, 0.0)

        class RunningRoute(FakeRouteExecutor):
            def tick(self):
                self.tick_count += 1
                return ri.InteractionStatus.RUNNING

        route = RunningRoute(runtime)
        controller = ri.InteractionBoundaryController(make_boundary(), runtime, route)

        def wait(_milliseconds):
            yield None

        adapter = ri.run_boundary_coroutine_adapter(controller, wait)
        next(adapter)
        adapter.close()
        self.assertEqual(controller.result, ri.InteractionStatus.FAILURE)
        self.assertGreaterEqual(route.cancel_count, 1)

    def test_runtime_only_resolution_is_an_explicit_escape_hatch(self):
        interaction = make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER)
        interaction = ri.InteractionSpec(
            **{
                **interaction.__dict__,
                "target": ri.TargetSpec(
                    kind=ri.TargetKind.LIVING,
                    model_id=42,
                    expected_xy=None,
                ),
            }
        )
        boundary = ri.InteractionBoundarySpec(
            name="runtime-only boundary",
            route_points=((-300.0, 0.0), (-100.0, 0.0)),
            route_standoff_xy=(-100.0, 0.0),
            route_tolerance=30.0,
            handoff_radius=75.0,
            interaction=interaction,
            resolution_strategy=ri.StandoffResolutionStrategy.RUNTIME_ONLY,
        )
        boundary.validate()

    def test_py4gw_runtime_resolves_ground_item_model_through_item_data(self):
        agent_module = types.ModuleType("Py4GWCoreLib.Agent")
        agent_array_module = types.ModuleType("Py4GWCoreLib.AgentArray")
        context_module = types.ModuleType("Py4GWCoreLib.Context")
        item_module = types.ModuleType("Py4GWCoreLib.Item")
        player_module = types.ModuleType("Py4GWCoreLib.Player")

        class Agent:
            IsValid = staticmethod(lambda agent_id: agent_id == 77)
            IsLiving = staticmethod(lambda _agent_id: False)
            IsNPC = staticmethod(lambda _agent_id: False)
            IsGadget = staticmethod(lambda _agent_id: False)
            IsItem = staticmethod(lambda agent_id: agent_id == 77)
            GetItemAgentItemID = staticmethod(lambda agent_id: 9001 if agent_id == 77 else 0)
            GetModelID = staticmethod(
                lambda _agent_id: (_ for _ in ()).throw(
                    AssertionError("living-agent model lookup must not be used for an item")
                )
            )
            GetNameByID = staticmethod(lambda _agent_id: "")
            GetXY = staticmethod(lambda _agent_id: (10.0, 20.0))

        class AgentArray:
            GetAgentArray = staticmethod(lambda: [77])

        class ContextAgentArray:
            GetContext = staticmethod(lambda: None)

        class GWContext:
            AgentArray = ContextAgentArray

        class Item:
            GetModelID = staticmethod(lambda item_id: 2569 if item_id == 9001 else 0)

        class Player:
            GetXY = staticmethod(lambda: (0.0, 0.0))

        agent_module.Agent = Agent
        agent_array_module.AgentArray = AgentArray
        context_module.GWContext = GWContext
        item_module.Item = Item
        player_module.Player = Player
        fake_modules = {
            "Py4GWCoreLib.Agent": agent_module,
            "Py4GWCoreLib.AgentArray": agent_array_module,
            "Py4GWCoreLib.Context": context_module,
            "Py4GWCoreLib.Item": item_module,
            "Py4GWCoreLib.Player": player_module,
        }
        runtime = ri.Py4GWInteractionRuntime(
            pause_automation=lambda: None,
            restore_automation=lambda: None,
            verify=lambda _postcondition: False,
        )
        target = ri.TargetSpec(
            kind=ri.TargetKind.ITEM,
            model_id=2569,
            expected_xy=(10.0, 20.0),
            search_radius=100.0,
        )
        with patch.dict(sys.modules, fake_modules):
            self.assertEqual(runtime.resolve_target(target), 77)
            self.assertEqual(runtime.agent_model_id(77), 2569)

    def test_py4gw_runtime_resolves_mount_qinkai_priest_by_captured_location(self):
        agent_module = types.ModuleType("Py4GWCoreLib.Agent")
        agent_array_module = types.ModuleType("Py4GWCoreLib.AgentArray")
        context_module = types.ModuleType("Py4GWCoreLib.Context")
        player_module = types.ModuleType("Py4GWCoreLib.Player")

        captured_xy = {
            38: (-8345.0, -9758.0),
            24: (-8456.52, -9733.1),
            25: (-8448.95, -9873.77),
            30: (-8308.28, -9866.2),
        }

        class Agent:
            IsValid = staticmethod(lambda agent_id: agent_id in captured_xy)
            IsLiving = staticmethod(lambda agent_id: agent_id in captured_xy)
            IsNPC = staticmethod(lambda agent_id: agent_id in captured_xy)
            IsGadget = staticmethod(lambda _agent_id: False)
            IsItem = staticmethod(lambda _agent_id: False)
            GetModelID = staticmethod(lambda agent_id: {38: 3692, 24: 1311, 25: 6025, 30: 4512}[agent_id])
            GetNameByID = staticmethod(lambda _agent_id: "")
            GetXY = staticmethod(lambda agent_id: captured_xy[agent_id])

        class AgentArray:
            GetAgentArray = staticmethod(lambda: list(captured_xy))

        class ContextAgentArray:
            GetContext = staticmethod(lambda: None)

        class GWContext:
            AgentArray = ContextAgentArray

        class Player:
            GetXY = staticmethod(lambda: (-8354.51, -9776.93))

        agent_module.Agent = Agent
        agent_array_module.AgentArray = AgentArray
        context_module.GWContext = GWContext
        player_module.Player = Player
        fake_modules = {
            "Py4GWCoreLib.Agent": agent_module,
            "Py4GWCoreLib.AgentArray": agent_array_module,
            "Py4GWCoreLib.Context": context_module,
            "Py4GWCoreLib.Player": player_module,
        }
        runtime = ri.Py4GWInteractionRuntime(
            pause_automation=lambda: None,
            restore_automation=lambda: None,
            verify=lambda _postcondition: False,
        )
        target = ri.TargetSpec(
            kind=ri.TargetKind.NPC,
            model_id=3692,
            expected_xy=(-8345.0, -9758.0),
            search_radius=700.0,
        )
        with patch.dict(sys.modules, fake_modules):
            self.assertEqual(runtime.resolve_target(target), 38)

    def test_normalizes_target_and_safe_approach_separately(self):
        metadata = ri.normalize_capture_metadata(
            {
                "capture_id": "NPC-1",
                "player": {"xy": [10, 20]},
                "target": {"xy": [30, 40], "model_id": 55, "name": "Target"},
            },
            interaction_kind=ri.InteractionProfile.VISIBLE_CHOICE,
            postcondition=ri.PostconditionSpec(ri.PostconditionKind.EFFECT_PRESENT, 99),
        )
        self.assertEqual(metadata.player_approach_xy, (10.0, 20.0))
        self.assertEqual(metadata.target_xy, (30.0, 40.0))
        self.assertEqual(metadata.source_capture_ids, ("NPC-1",))

    def test_quest_conversation_uses_raw_context_and_verifies(self):
        runtime = FakeRuntime("raw")
        runtime.visible = True
        spec = make_spec(
            ri.InteractionProfile.QUEST_CONVERSATION,
            dialog=ri.DialogSpec(raw_context_ids=(0x831801,)),
        )
        controller = ri.ReliableInteractionController(spec, runtime)
        self.assertEqual(run(controller, runtime), ri.InteractionStatus.SUCCESS)
        self.assertGreaterEqual(runtime.resolve_count, 2)
        self.assertEqual(runtime.restore_count, 1)

    def test_visible_choice_can_be_followed_by_raw_context_response(self):
        runtime = FakeRuntime("visible_then_raw")
        spec = make_spec(
            ri.InteractionProfile.QUEST_CONVERSATION,
            dialog=ri.DialogSpec(
                visible_buttons=(1,),
                raw_context_ids=(0x833404,),
                chain_raw_after_visible=True,
                visible_step_delay_ms=100,
            ),
        )
        controller = ri.ReliableInteractionController(spec, runtime)
        self.assertEqual(run(controller, runtime), ri.InteractionStatus.SUCCESS)
        self.assertEqual(runtime.click_count, 1)
        self.assertEqual(runtime.sent_dialog_ids, [0x833404])
        events = [event["event"] for event in runtime.events]
        self.assertIn("raw_dialog_after_visible_wait_started", events)
        self.assertIn("raw_dialog_sent", events)
        self.assertLess(
            events.index("visible_button_clicked"),
            events.index("raw_dialog_sent"),
        )

    def test_quest_conversation_accepts_immediate_trigger_without_dialog(self):
        runtime = FakeRuntime("automatic")
        spec = make_spec(
            ri.InteractionProfile.QUEST_CONVERSATION,
            dialog=ri.DialogSpec(
                raw_context_ids=(0x84,),
                allow_raw_without_visible_dialog=True,
            ),
        )
        spec = ri.InteractionSpec(
            **{
                **spec.__dict__,
                "allow_preexisting_postcondition": False,
            }
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        self.assertEqual(runtime.sent_dialog_ids, [])

    def test_visible_choice_and_reward_accept_click_one_based_button(self):
        for profile, behavior in (
            (ri.InteractionProfile.VISIBLE_CHOICE, "visible"),
            (ri.InteractionProfile.REWARD_ACCEPT, "reward"),
        ):
            with self.subTest(profile=profile):
                runtime = FakeRuntime(behavior)
                spec = make_spec(profile, dialog=ri.DialogSpec(visible_button=1))
                self.assertEqual(
                    run(ri.ReliableInteractionController(spec, runtime), runtime),
                    ri.InteractionStatus.SUCCESS,
                )
                self.assertEqual(runtime.click_count, 1)

    def test_visible_choice_waits_for_populated_buttons_and_never_sends_raw_context(self):
        runtime = FakeRuntime("delayed_visible")
        spec = make_spec(
            ri.InteractionProfile.VISIBLE_CHOICE,
            dialog=ri.DialogSpec(
                visible_button=1,
                raw_context_ids=(0x84,),
                response_timeout_ms=1_000,
            ),
        )
        controller = ri.ReliableInteractionController(spec, runtime)
        for _ in range(20):
            controller.tick()
            runtime.advance(0.05)
            if controller.stage == "wait_response":
                break
        self.assertEqual(controller.stage, "wait_response")

        for _ in range(5):
            self.assertEqual(controller.tick(), ri.InteractionStatus.RUNNING)
            runtime.advance(0.05)
        self.assertEqual(runtime.sent_dialog_ids, [])
        self.assertEqual(runtime.click_count, 0)

        runtime.buttons = 2
        self.assertEqual(controller.tick(), ri.InteractionStatus.RUNNING)
        runtime.advance(0.05)
        self.assertEqual(controller.tick(), ri.InteractionStatus.SUCCESS)
        self.assertEqual(runtime.click_count, 1)
        self.assertEqual(runtime.sent_dialog_ids, [])
        events = [event["event"] for event in runtime.events]
        self.assertIn("dialog_visible", events)
        self.assertIn("dialog_buttons_populated", events)
        self.assertIn("visible_button_clicked", events)
        self.assertIn("postcondition_verified", events)
        self.assertFalse(any(event.startswith("raw_dialog_sent") for event in events))

    def test_visible_choice_accepts_stable_no_choice_alternate_without_retrying(self):
        class NoChoiceRuntime(FakeRuntime):
            def __init__(self):
                super().__init__("raw")

            def verify(self, _postcondition):
                return self.visible and self.buttons == 0

        runtime = NoChoiceRuntime()
        spec = make_spec(
            ri.InteractionProfile.VISIBLE_CHOICE,
            dialog=ri.DialogSpec(
                visible_button=1,
                response_timeout_ms=2_000,
                allow_no_choice_success=True,
                no_choice_settle_ms=500,
                close_dialog_after_success=True,
            ),
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        self.assertEqual(runtime.click_count, 0)
        self.assertTrue(
            any(event["event"] == "no_choice_dialog_settle_started" for event in runtime.events)
        )

    def test_visible_choice_supports_two_page_button_sequence(self):
        runtime = FakeRuntime("two_page_visible")
        spec = make_spec(
            ri.InteractionProfile.VISIBLE_CHOICE,
            dialog=ri.DialogSpec(
                visible_buttons=(1, 1),
                visible_step_delay_ms=500,
                response_timeout_ms=1_000,
            ),
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        self.assertEqual(runtime.click_count, 2)
        self.assertEqual(runtime.sent_dialog_ids, [])
        clicked = [
            event
            for event in runtime.events
            if event["event"] == "visible_button_clicked"
        ]
        self.assertEqual([event["button"] for event in clicked], [1, 1])
        self.assertEqual([event["sequence_index"] for event in clicked], [1, 2])
        self.assertIn(
            "next_visible_dialog_wait_started",
            [event["event"] for event in runtime.events],
        )

    def test_visible_choice_resolves_variable_menu_positions_by_label(self):
        runtime = FakeRuntime("two_page_label_visible")
        spec = make_spec(
            ri.InteractionProfile.QUEST_CONVERSATION,
            dialog=ri.DialogSpec(
                visible_buttons=(1, 1),
                visible_button_labels=(
                    "Battle in the Sewers",
                    "Just doing my duty to the emperor.",
                ),
                visible_step_delay_ms=500,
                response_timeout_ms=1_000,
            ),
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.clicked_choices, [3, 1])
        clicked = [
            event
            for event in runtime.events
            if event["event"] == "visible_button_label_clicked"
        ]
        self.assertEqual([event["label"] for event in clicked], [
            "Battle in the Sewers",
            "Just doing my duty to the emperor.",
        ])

    def test_long_dialog_page_scrolls_before_clicking_captured_response(self):
        runtime = FakeRuntime("two_page_scroll_visible")
        response = "Hang on, little ones! I'll save you!"
        spec = make_spec(
            ri.InteractionProfile.QUEST_CONVERSATION,
            dialog=ri.DialogSpec(
                visible_button_labels=("Stolen Eggs", response),
                scroll_down_before_visible_button_labels=(response,),
                visible_step_delay_ms=500,
                scroll_step_delay_ms=350,
                response_timeout_ms=1_000,
            ),
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.clicked_choices, [1, 1])
        self.assertEqual(runtime.scroll_count, 1)
        self.assertEqual(runtime.scroll_deltas, [-120])
        self.assertIn(
            "dialog_scrolled_for_visible_button_label",
            [event["event"] for event in runtime.events],
        )

    def test_visible_choice_label_moves_to_first_position_when_other_quests_are_absent(self):
        runtime = FakeRuntime("two_page_label_visible")
        runtime.interact = lambda _agent_id: (
            setattr(runtime, "visible", True),
            setattr(runtime, "button_labels", ("Battle in the Sewers",)),
            setattr(runtime, "buttons", 1),
            setattr(runtime, "interact_count", runtime.interact_count + 1),
        )
        spec = make_spec(
            ri.InteractionProfile.QUEST_CONVERSATION,
            dialog=ri.DialogSpec(
                visible_button_labels=(
                    "Battle in the Sewers",
                    "Just doing my duty to the emperor.",
                ),
                visible_step_delay_ms=500,
                response_timeout_ms=1_000,
            ),
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.clicked_choices, [1, 1])

    def test_optional_leading_label_clicks_menu_then_required_detail(self):
        class ConditionalQuestRuntime(FakeRuntime):
            def __init__(self, *, direct_detail: bool):
                super().__init__("visible")
                self.direct_detail = direct_detail

            def interact(self, _agent_id):
                self.interact_count += 1
                self.visible = True
                self.button_labels = (
                    ("I'll seek out Elder Rhea.", "I haven't decided yet.")
                    if self.direct_detail
                    else ("Journey to House zu Heltzer", "Journey to Cavalon")
                )
                self.buttons = len(self.button_labels)

            def click_dialog_button(self, choice):
                self.click_count += 1
                self.clicked_choices.append(choice)
                if self.button_labels[choice - 1] == "Journey to Cavalon":
                    self.button_labels = (
                        "I'll seek out Elder Rhea.",
                        "I haven't decided yet.",
                    )
                    self.buttons = len(self.button_labels)
                else:
                    self.satisfied = True
                return True

        runtime = ConditionalQuestRuntime(direct_detail=False)
        spec = make_spec(
            ri.InteractionProfile.QUEST_CONVERSATION,
            dialog=ri.DialogSpec(
                optional_leading_visible_button_labels=("Journey to Cavalon",),
                visible_button_labels=("I'll seek out Elder Rhea.",),
                visible_step_delay_ms=500,
                response_timeout_ms=1_000,
            ),
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.clicked_choices, [2, 1])
        self.assertIn(
            "optional_visible_button_label_clicked",
            [event["event"] for event in runtime.events],
        )

    def test_optional_leading_label_skips_direct_detail_without_reinteraction(self):
        class DirectQuestRuntime(FakeRuntime):
            def __init__(self):
                super().__init__("visible")

            def interact(self, _agent_id):
                self.interact_count += 1
                self.visible = True
                self.button_labels = (
                    "I'll seek out Elder Rhea.",
                    "I haven't decided yet.",
                )
                self.buttons = len(self.button_labels)

        runtime = DirectQuestRuntime()
        spec = make_spec(
            ri.InteractionProfile.QUEST_CONVERSATION,
            dialog=ri.DialogSpec(
                optional_leading_visible_button_labels=("Journey to Cavalon",),
                visible_button_labels=("I'll seek out Elder Rhea.",),
                visible_step_delay_ms=500,
                response_timeout_ms=1_000,
            ),
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        self.assertEqual(runtime.clicked_choices, [1])
        self.assertIn(
            "optional_visible_button_label_absent",
            [event["event"] for event in runtime.events],
        )

    def test_stateful_visible_choice_accepts_remaining_opposite_label_without_reclick(self):
        class AlreadyFollowingRuntime(FakeRuntime):
            def __init__(self):
                super().__init__("visible")

            def interact(self, _agent_id):
                self.interact_count += 1
                self.visible = True
                self.button_labels = ("Siege Mode",)
                self.buttons = 1

            def verify(self, _postcondition):
                labels = tuple(label.casefold() for label in self.button_labels)
                return self.visible and "siege mode" in labels and "follow me" not in labels

        runtime = AlreadyFollowingRuntime()
        base = make_spec(
            ri.InteractionProfile.VISIBLE_CHOICE,
            dialog=ri.DialogSpec(
                visible_button_labels=("Follow Me",),
                response_timeout_ms=1_000,
            ),
        )
        spec = ri.InteractionSpec(
            **{
                **base.__dict__,
                "allow_preexisting_postcondition": True,
            }
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        self.assertEqual(runtime.click_count, 0)
        self.assertTrue(
            any(
                event["event"] == "postcondition_verified"
                for event in runtime.events
            )
        )

    def test_visible_choice_supports_three_page_entry_sequence(self):
        runtime = FakeRuntime("two_page_visible")
        spec = make_spec(
            ri.InteractionProfile.VISIBLE_CHOICE,
            dialog=ri.DialogSpec(
                visible_buttons=(1, 1, 1),
                visible_step_delay_ms=500,
                response_timeout_ms=1_000,
            ),
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        self.assertEqual(runtime.click_count, 3)
        clicked = [
            event
            for event in runtime.events
            if event["event"] == "visible_button_clicked"
        ]
        self.assertEqual([event["button"] for event in clicked], [1, 1, 1])
        self.assertEqual([event["sequence_index"] for event in clicked], [1, 2, 3])

    def test_visible_choice_waits_for_and_closes_post_success_popup(self):
        runtime = FakeRuntime("delayed_popup")
        spec = make_spec(
            ri.InteractionProfile.VISIBLE_CHOICE,
            dialog=ri.DialogSpec(
                visible_button=1,
                close_dialog_after_success=True,
                post_success_dialog_timeout_ms=1_000,
            ),
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        self.assertEqual(runtime.click_count, 1)
        self.assertEqual(runtime.close_count, 2)
        self.assertEqual(runtime.restore_count, 1)
        events = [event["event"] for event in runtime.events]
        self.assertIn("postcondition_verified", events)
        self.assertIn("post_success_dialog_visible", events)
        self.assertIn("post_success_dialog_closed", events)

    def test_later_dungeon_beacon_leaves_success_response_open(self):
        class LaterBeaconRuntime(FakeRuntime):
            def interact(self, _agent_id):
                self.interact_count += 1
                self.visible = True
                self.buttons = 0
                self.satisfied = True

        runtime = LaterBeaconRuntime("later_beacon_response")
        spec = make_spec(
            ri.InteractionProfile.AUTOMATIC_TRIGGER,
            dialog=ri.DialogSpec(close_dialog_after_success=False),
        )

        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        # One cleanup before the attempt is still required. The successful
        # response remains visible for the following route movement to dismiss.
        self.assertEqual(runtime.close_count, 1)
        self.assertTrue(runtime.visible)
        events = [event["event"] for event in runtime.events]
        self.assertIn("postcondition_verified", events)
        self.assertNotIn("post_success_dialog_wait_started", events)
        self.assertNotIn("post_success_dialog_closed", events)

    def test_approach_logs_live_agent_distance_and_revalidates_target(self):
        runtime = FakeRuntime("visible")
        spec = make_spec(
            ri.InteractionProfile.VISIBLE_CHOICE,
            dialog=ri.DialogSpec(visible_button=1),
        )
        spec = ri.InteractionSpec(
            **{
                **spec.__dict__,
                "approach": ri.ApproachSpec(
                    player_approach_xy=(80.0, 0.0),
                    tolerance=5.0,
                    target_tolerance=25.0,
                ),
            }
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        events = {event["event"]: event for event in runtime.events}
        self.assertEqual(events["target_resolved"]["resolved_model_id"], 42)
        self.assertIn("approach_started", events)
        self.assertIn("approach_progress", events)
        self.assertEqual(events["approach_reached"]["player_to_agent_distance"], 20.0)
        self.assertEqual(events["target_reacquired"]["resolved_model_id"], 42)
        self.assertEqual(events["target_reacquired"]["player_to_agent_distance"], 20.0)
        event_order = [event["event"] for event in runtime.events]
        expected_order = [
            "target_resolved",
            "approach_started",
            "approach_progress",
            "approach_reached",
            "target_reacquired",
            "interaction_sent",
            "dialog_visible",
            "dialog_buttons_populated",
            "visible_button_clicked",
            "postcondition_verified",
        ]
        self.assertEqual(
            [event_order.index(event) for event in expected_order],
            sorted(event_order.index(event) for event in expected_order),
        )

    def test_explicit_approach_enforces_agent_distance_by_default(self):
        runtime = FakeRuntime("visible")
        runtime.agent_position = (120.0, 0.0)
        spec = make_spec(
            ri.InteractionProfile.VISIBLE_CHOICE,
            dialog=ri.DialogSpec(visible_button=1),
            attempts=1,
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime, limit=200),
            ri.InteractionStatus.FAILURE,
        )
        self.assertEqual(runtime.interact_count, 0)
        progress = [event for event in runtime.events if event["event"] == "approach_progress"]
        self.assertTrue(progress)
        self.assertEqual(progress[-1]["target_tolerance"], 5.0)
        self.assertGreater(progress[-1]["player_to_agent_distance"], 5.0)

    def test_required_interaction_does_not_short_circuit_on_preexisting_postcondition(self):
        runtime = FakeRuntime("visible")
        runtime.satisfied = True
        spec = make_spec(
            ri.InteractionProfile.VISIBLE_CHOICE,
            dialog=ri.DialogSpec(visible_button=1),
        )
        spec = ri.InteractionSpec(
            **{
                **spec.__dict__,
                "allow_preexisting_postcondition": False,
            }
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        self.assertEqual(runtime.click_count, 1)
        self.assertTrue(
            any(event["event"] == "preexisting_postcondition_ignored" for event in runtime.events)
        )

    def test_idempotent_interaction_keeps_preexisting_postcondition_shortcut(self):
        runtime = FakeRuntime("visible")
        runtime.satisfied = True
        spec = make_spec(
            ri.InteractionProfile.VISIBLE_CHOICE,
            dialog=ri.DialogSpec(visible_button=1),
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.resolve_count, 0)
        self.assertEqual(runtime.interact_count, 0)

    def test_automatic_trigger_and_gadget_require_postcondition(self):
        for profile, behavior in (
            (ri.InteractionProfile.AUTOMATIC_TRIGGER, "automatic"),
            (ri.InteractionProfile.GADGET, "gadget"),
        ):
            with self.subTest(profile=profile):
                runtime = FakeRuntime(behavior)
                spec = make_spec(profile)
                self.assertEqual(
                    run(ri.ReliableInteractionController(spec, runtime), runtime),
                    ri.InteractionStatus.SUCCESS,
                )
                self.assertEqual(runtime.interact_count, 1)

    def test_toggle_follow_uses_one_interaction_then_moves_to_verify(self):
        class ToggleFollowRuntime(FakeRuntime):
            def __init__(self):
                super().__init__("never")
                self.following = False

            def interact(self, _agent_id):
                self.interact_count += 1
                self.following = not self.following

            def move_to(self, xy):
                self.player = xy
                if self.following:
                    self.satisfied = True

        runtime = ToggleFollowRuntime()
        base = make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER, attempts=1)
        spec = ri.InteractionSpec(
            **{
                **base.__dict__,
                "verification_move_xy": (250.0, 0.0),
                "verification_move_reissue_ms": 0,
            }
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 1)
        self.assertTrue(runtime.following)
        self.assertEqual(runtime.player, (250.0, 0.0))
        self.assertTrue(
            any(event["event"] == "verification_movement_sent" for event in runtime.events)
        )

    def test_walk_over_moves_without_interacting(self):
        runtime = FakeRuntime("walk_over")
        spec = make_spec(ri.InteractionProfile.WALK_OVER)
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertEqual(runtime.interact_count, 0)

    def test_missing_safe_capture_uses_standoff_not_occupied_target(self):
        runtime = FakeRuntime("automatic")
        spec = make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER)
        spec = ri.InteractionSpec(
            **{
                **spec.__dict__,
                "approach": ri.ApproachSpec(player_approach_xy=None, tolerance=5.0),
            }
        )
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.SUCCESS,
        )
        self.assertNotEqual(runtime.player, runtime.agent_position)
        self.assertAlmostEqual(runtime.player[0], 20.0)

    def test_challenge_restores_for_combat_then_reacquires_and_reinteracts(self):
        runtime = FakeRuntime("challenge")
        spec = make_spec(
            ri.InteractionProfile.CHALLENGE_THEN_REINTERACT,
            dialog=ri.DialogSpec(visible_button=1),
        )
        controller = ri.ReliableInteractionController(spec, runtime)
        for _ in range(100):
            status = controller.tick()
            if controller.stage == "wait_challenge":
                runtime.hostile = False
            if status != ri.InteractionStatus.RUNNING:
                break
            runtime.advance()
        self.assertEqual(status, ri.InteractionStatus.SUCCESS)
        self.assertEqual(runtime.click_count, 2)
        self.assertGreaterEqual(runtime.resolve_count, 4)
        self.assertEqual(runtime.pause_count, 2)
        self.assertEqual(runtime.restore_count, 2)

    def test_failure_retries_and_always_restores(self):
        runtime = FakeRuntime("never")
        spec = make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER, attempts=2)
        self.assertEqual(
            run(ri.ReliableInteractionController(spec, runtime), runtime),
            ri.InteractionStatus.FAILURE,
        )
        self.assertEqual(runtime.interact_count, 2)
        self.assertEqual(runtime.restore_count, 1)
        self.assertTrue(any(event["event"] == "attempt_failed" for event in runtime.events))

    def test_cancel_restores_automation(self):
        runtime = FakeRuntime("never")
        controller = ri.ReliableInteractionController(
            make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER), runtime
        )
        controller.tick()
        controller.cancel("test cancel")
        self.assertEqual(controller.result, ri.InteractionStatus.FAILURE)
        self.assertEqual(runtime.restore_count, 1)

    def test_coroutine_adapter_restores_when_fsm_closes_state(self):
        runtime = FakeRuntime("never")
        controller = ri.ReliableInteractionController(
            make_spec(ri.InteractionProfile.AUTOMATIC_TRIGGER), runtime
        )

        def wait(_milliseconds):
            yield None

        adapter = ri.run_coroutine_adapter(controller, wait)
        next(adapter)
        adapter.close()
        self.assertTrue(controller.finished)
        self.assertEqual(runtime.restore_count, 1)


if __name__ == "__main__":
    unittest.main()
