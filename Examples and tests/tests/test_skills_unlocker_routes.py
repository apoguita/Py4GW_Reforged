from pathlib import Path
import re
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

    def test_courage_uses_existing_fsm_blessing_interaction(self):
        route = function_source("Unlock_ebon_battle_standard_of_courage")
        self.assertIn("bot.Move.XYAndDialog(*EBOSC_ENTRY_BLESSING_XY, 0x84)", route)
        self.assertNotIn("BT.TakeBlessing", route)
        self.assertNotIn("_run_behavior_tree", SOURCE)
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
