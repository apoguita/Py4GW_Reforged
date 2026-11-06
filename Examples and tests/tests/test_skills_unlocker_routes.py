from pathlib import Path
from enum import Enum, auto
import re
from types import SimpleNamespace
from typing import Any, Generator
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = (
    ROOT
    / "Widgets"
    / "Automation"
    / "Bots"
    / "SkillsUnlocker"
    / "EOTN_SKILL_UNLOCKER.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


def function_source(name: str) -> str:
    match = re.search(
        rf"(?ms)^def {re.escape(name)}\([^\n]*\).*?(?=^def |\Z)",
        SOURCE,
    )
    if not match:
        raise AssertionError(f"Function {name!r} was not found")
    return match.group(0)


class SkillsUnlockerRouteTests(unittest.TestCase):
    def test_sneak_attack_orders_plan_a_dialogs_wait_bundle_and_reward(self):
        route = function_source("Unlock_sneak_attack")
        accept = route.index("0x836201")
        vael = route.index("0x836204")
        wait = route.index("bot.Wait.ForTime(70000)")
        pickup = route.index("bot.Interact.WithItemAtXY(*PLAN_A_BATTLE_PLANS_XY)")
        reward = route.index("0x836207")
        self.assertLess(accept, vael)
        self.assertLess(vael, wait)
        self.assertLess(wait, pickup)
        self.assertLess(pickup, reward)

    def test_sneak_attack_reuses_existing_bundle_and_blessing_owners(self):
        route = function_source("Unlock_sneak_attack")
        self.assertIn("BT.TakeBlessing", route)
        self.assertIn("buttons=0", route)
        self.assertIn("buttons=[]", route)
        self.assertIn("bot.Interact.WithItemAtXY", route)
        self.assertNotIn("ReliableInteractionController", route)
        self.assertNotIn("Player.Interact", route)

    def test_sneak_attack_preserves_captured_carry_route_endpoints(self):
        route = function_source("Unlock_sneak_attack")
        self.assertIn("PLAN_A_CARRY_TO_RETURN_BLESSING_ROUTE_XY", route)
        self.assertIn("PLAN_A_CARRY_FROM_RETURN_BLESSING_ROUTE_XY", route)
        self.assertIn("(-3235.89, -1021.53)", SOURCE)
        self.assertIn("(-20912.11, 12164.77)", SOURCE)

    def test_behavior_tree_adapter_advances_only_on_success(self):
        class FakeNodeState(Enum):
            RUNNING = auto()
            SUCCESS = auto()
            FAILURE = auto()

        class FakeBehaviorTree:
            NodeState = FakeNodeState

        class FakeTree:
            def __init__(self, result):
                self.result = result
                self.reset_count = 0

            def tick(self):
                return self.result

            def reset(self):
                self.reset_count += 1

        class FakeYield:
            @staticmethod
            def wait(milliseconds):
                yield ("wait", milliseconds)

        config = SimpleNamespace(fsm_running=True, state_description="")
        namespace = {
            "Any": Any,
            "BehaviorTree": FakeBehaviorTree,
            "Generator": Generator,
            "Routines": SimpleNamespace(Yield=FakeYield),
            "bot": SimpleNamespace(config=config),
        }
        exec(function_source("_run_behavior_tree"), namespace)
        run_tree = namespace["_run_behavior_tree"]

        success_tree = FakeTree(FakeNodeState.SUCCESS)
        with self.assertRaises(StopIteration) as success:
            next(run_tree(success_tree))
        self.assertIs(success.exception.value, True)
        self.assertEqual(success_tree.reset_count, 1)

        failure_tree = FakeTree(FakeNodeState.FAILURE)
        failure_state = run_tree(failure_tree)
        self.assertEqual(next(failure_state), ("wait", 250))
        self.assertIn("Blocked", config.state_description)
        config.fsm_running = False
        with self.assertRaises(StopIteration):
            next(failure_state)
        self.assertEqual(failure_tree.reset_count, 1)

    def test_courage_rezones_before_accepting_quest_and_uses_explicit_dialogs(self):
        route = function_source("Unlock_ebon_battle_standard_of_courage")
        first_appearance = route.index("EBOSC_FIRST_APPEARANCE_ROUTE_XY")
        second_travel = route.index("bot.Map.Travel(target_map_id=650)", first_appearance)
        quest_accept = route.index("0x836101")
        midquest_dialog = route.index("0x836104")
        reward_dialog = route.index("0x836107")
        self.assertLess(first_appearance, second_travel)
        self.assertLess(second_travel, quest_accept)
        self.assertLess(quest_accept, midquest_dialog)
        self.assertLess(midquest_dialog, reward_dialog)

    def test_courage_preserves_stealth_wait_pickup_and_extended_portals(self):
        route = function_source("Unlock_ebon_battle_standard_of_courage")
        self.assertIn('bot.Properties.Disable("hero_ai")', route)
        self.assertIn("bot.Wait.ForTime(30000)", route)
        self.assertIn("bot.Move.XY(*EBOSC_CHARR_INTELLIGENCE_XY)", route)
        self.assertNotIn("PickupMissionStateGroundItemByModelID", SOURCE)
        self.assertIn("(-21286.78, 12273.97)", SOURCE)
        self.assertIn("(-21275.70, 12287.56)", SOURCE)
        self.assertIn("(-21326.57, 12232.69)", SOURCE)

    def test_courage_delegates_blessing_to_upstream_owner(self):
        route = function_source("Unlock_ebon_battle_standard_of_courage")
        self.assertIn("BT.TakeBlessing", route)
        self.assertIn("buttons=0", route)
        self.assertNotIn("click_dialog_button", SOURCE)
        self.assertNotIn("Player.Interact", route)

    def test_ymlad_starts_from_sifhalla_and_returns_by_map_travel(self):
        route = function_source("Unlock_you_move_like_a_dwarf")
        first_travel = route.index('bot.Map.Travel(target_map_name="Sifhalla")')
        quest_dialog = route.index("0x833A01")
        self.assertLess(first_travel, quest_dialog)
        self.assertGreaterEqual(route.count('bot.Map.Travel(target_map_name="Sifhalla")'), 2)
        self.assertNotIn("ResignParty", route)

    def test_iau_has_restartable_phase_anchors(self):
        route = function_source("Unlock_i_am_unstoppable")
        for anchor in (
            "IAU:TAKE_ANYTHING_YOU_CAN_DO",
            "IAU:HUNT_AVARR_AND_WHITEOUT",
            "IAU:FRAGMENT_OF_ANTIQUITIES",
            "IAU:CLAIM_ANYTHING_YOU_CAN_DO",
            "IAU:COLD_AS_ICE",
            "IAU:CLAIM_FINAL_REWARD",
        ):
            self.assertIn(anchor, route)

    def test_iau_uses_captured_remlok_and_sepulchre_routes(self):
        route = function_source("Unlock_i_am_unstoppable")
        remlok_route = route.index("DRAKKAR_TO_REMLOK_ROUTE_XY")
        remlok_dialog = route.index("0x832901")
        proof_route = route.index("SEPULCHRE_PROOF_OF_STRENGTH_ROUTE_XY")
        fragment_route = route.index("SEPULCHRE_LEVEL1_FRAGMENT_ROUTE_XY")
        self.assertLess(remlok_route, remlok_dialog)
        self.assertLess(proof_route, fragment_route)
        self.assertIn("(-5366.00, -15794.00)", SOURCE)
        self.assertIn("(-12827.22, 872.84)", SOURCE)

    def test_checkpoint_picker_covers_every_skill_route(self):
        picker = function_source("_get_route_checkpoints")
        self.assertIn("for skill in SKILLS", picker)
        self.assertIn("CHECKPOINT_LABEL_OVERRIDES", picker)
        self.assertIn("jump_to_state_by_step_number", function_source("_stop_clear_start_and_jump"))

    def test_route_pr_does_not_add_a_private_interaction_framework(self):
        forbidden = (
            "InteractionSpec",
            "InteractionBoundarySpec",
            "SessionLogger",
            "_interact_sif_shadowhunter",
            "_interact_outrunner_remlok_reliable",
        )
        for name in forbidden:
            self.assertNotIn(name, SOURCE)


if __name__ == "__main__":
    unittest.main()
