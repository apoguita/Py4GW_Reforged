from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
FIGHTER_PATH = ROOT / 'Widgets' / 'Automation' / 'Bots' / 'Runners' / 'OutpostFighter.py'
MOVE_PATH = ROOT / 'Py4GWCoreLib' / 'botting_src' / 'subclases_src' / 'MOVE_src.py'


class OutpostFighterWipeRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fighter = FIGHTER_PATH.read_text(encoding='utf-8')
        cls.movement = MOVE_PATH.read_text(encoding='utf-8')
        recovery_start = cls.fighter.index('def _on_party_wipe(')
        recovery_end = cls.fighter.index('\ndef OnPartyWipe(', recovery_start)
        cls.recovery = cls.fighter[recovery_start:recovery_end]

    def test_wipe_recovery_never_resigns_or_waits_for_an_outpost(self) -> None:
        self.assertNotIn('_resignParty', self.recovery)
        self.assertNotIn('_coro_until_on_outpost', self.recovery)

    def test_fighter_does_not_enable_the_return_on_defeat_widget(self) -> None:
        widget_start = self.fighter.index('WIDGETS_TO_ENABLE')
        widget_end = self.fighter.index('\n\nbot = Botting(', widget_start)
        self.assertNotIn('Return to outpost on defeat', self.fighter[widget_start:widget_end])

    def test_same_instance_recovery_resumes_the_reset_interrupted_state(self) -> None:
        self.assertIn('fsm.current_state.reset()', self.fighter)
        self.assertIn('Party revived at the resurrection shrine.', self.recovery)
        self.assertIn('bot_instance.config.FSM.resume()', self.recovery)

    def test_game_forced_outpost_return_restarts_without_causing_the_return(self) -> None:
        self.assertIn('if Map.IsOutpost() and _current_route_anchor:', self.recovery)
        self.assertIn('jump_to_state_by_name(_current_route_anchor)', self.recovery)

    def test_route_paths_opt_into_nearest_forward_progress(self) -> None:
        self.assertIn("resume_key_prefix=f'outpost-fighter:{_queue_version}:{index}'", self.fighter)
        auto_start = self.movement.index('    def _coro_follow_auto_path(')
        auto_end = self.movement.index('    def _coro_follow_path_to_aggro(', auto_start)
        auto_path = self.movement[auto_start:auto_end]
        self.assertIn('resume_key: Optional[str] = None', auto_path)
        self.assertIn('range(floor_index, len(path_points))', auto_path)
        self.assertIn('"next_index": index + 1', auto_path)
        self.assertIn('current_uptime + 1_000 >= saved_uptime', auto_path)


if __name__ == '__main__':
    unittest.main()
