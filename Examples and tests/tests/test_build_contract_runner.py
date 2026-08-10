from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPOSITORY_ROOT / 'Py4GWCoreLib' / 'HeroAI' / 'build_contract_runner.py'
RUNNER_SPEC = importlib.util.spec_from_file_location('headless_build_contract_runner', RUNNER_PATH)
if RUNNER_SPEC is None or RUNNER_SPEC.loader is None:
    raise RuntimeError(f'Unable to load build contract runner from {RUNNER_PATH}')
RUNNER_MODULE = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER_MODULE)
BuildContractRunner = RUNNER_MODULE.BuildContractRunner


class FakeContract:
    def __init__(self, name: str = 'contract') -> None:
        self.name = name
        self.tick_state = None
        self.events: list[str] = []

    def DidTickSucceed(self) -> bool:
        return self.tick_state == 'success'

    def ProcessOOC(self):
        self.events.append('ooc:start')
        try:
            yield
            self.events.append('ooc:resume')
            self.tick_state = 'success'
        finally:
            self.events.append('ooc:close')

    def ProcessCombat(self):
        self.events.append('combat:start')
        try:
            yield
            self.events.append('combat:resume')
            self.tick_state = 'success'
        finally:
            self.events.append('combat:close')


class BuildContractRunnerTests(unittest.TestCase):
    def test_same_contract_coroutine_resumes_on_the_next_tick(self) -> None:
        contract = FakeContract()
        runner = BuildContractRunner()

        self.assertFalse(runner.tick(contract, is_in_combat=True))
        self.assertEqual(contract.events, ['combat:start'])
        self.assertTrue(runner.is_running)

        self.assertTrue(runner.tick(contract, is_in_combat=True))
        self.assertEqual(
            contract.events,
            ['combat:start', 'combat:resume', 'combat:close'],
        )
        self.assertFalse(runner.is_running)

    def test_phase_change_closes_old_coroutine_before_starting_new_phase(self) -> None:
        contract = FakeContract()
        runner = BuildContractRunner()

        runner.tick(contract, is_in_combat=False)
        runner.tick(contract, is_in_combat=True)

        self.assertEqual(
            contract.events,
            ['ooc:start', 'ooc:close', 'combat:start'],
        )

    def test_contract_change_closes_previous_contract(self) -> None:
        first = FakeContract('first')
        second = FakeContract('second')
        runner = BuildContractRunner()

        runner.tick(first, is_in_combat=True)
        runner.tick(second, is_in_combat=True)

        self.assertEqual(first.events, ['combat:start', 'combat:close'])
        self.assertEqual(second.events, ['combat:start'])
        self.assertIs(runner.contract, second)

    def test_reset_and_missing_contract_close_pending_work(self) -> None:
        contract = FakeContract()
        runner = BuildContractRunner()

        runner.tick(contract, is_in_combat=True)
        runner.reset()
        self.assertEqual(contract.events, ['combat:start', 'combat:close'])
        self.assertIsNone(runner.contract)
        self.assertFalse(runner.is_running)

        self.assertFalse(runner.tick(None, is_in_combat=True))

    def test_completed_cycle_starts_a_fresh_cycle_on_later_tick(self) -> None:
        contract = FakeContract()
        runner = BuildContractRunner()

        runner.tick(contract, is_in_combat=True)
        runner.tick(contract, is_in_combat=True)
        runner.tick(contract, is_in_combat=True)

        self.assertEqual(contract.events.count('combat:start'), 2)


if __name__ == '__main__':
    unittest.main()
