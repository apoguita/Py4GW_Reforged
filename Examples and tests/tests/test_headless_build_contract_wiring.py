from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HEADLESS_TREE_PATH = REPOSITORY_ROOT / 'Py4GWCoreLib' / 'HeroAI' / 'headless_tree.py'


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def _method_source(class_name: str, method_name: str) -> str:
    source = _read(HEADLESS_TREE_PATH)
    module = ast.parse(source)
    class_node = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method_node = next(
        node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name
    )
    return ast.get_source_segment(source, method_node) or ''


class HeadlessBuildContractWiringTests(unittest.TestCase):
    def test_headless_resolves_and_runs_the_selected_contract_directly(self) -> None:
        source = _read(HEADLESS_TREE_PATH)
        runner_source = _method_source('HeroAIHeadlessTree', '_run_build_contract')

        self.assertIn('from .build_contract_runner import BuildContractRunner', source)
        self.assertIn('EnsureBuildContract(self.cached_data)', runner_source)
        self.assertIn('self._build_contract_runner.tick(', runner_source)
        self.assertNotIn('self.heroai_build.ProcessCombat()', runner_source)
        self.assertNotIn('self.heroai_build.ProcessOOC()', runner_source)

    def test_ooc_and_combat_use_the_same_contract_runner_with_distinct_phases(self) -> None:
        ooc_source = _method_source('HeroAIHeadlessTree', '_handle_out_of_combat')
        combat_source = _method_source('HeroAIHeadlessTree', '_handle_combat')

        self.assertIn('self._run_build_contract(is_in_combat=False)', ooc_source)
        self.assertIn('self._run_build_contract(is_in_combat=True)', combat_source)

    def test_headless_reset_cancels_pending_contract_coroutine(self) -> None:
        reset_source = _method_source('HeroAIHeadlessTree', 'reset')

        self.assertIn('self._build_contract_runner.reset()', reset_source)
        self.assertLess(
            reset_source.index('self._build_contract_runner.reset()'),
            reset_source.index('self.heroai_build.ClearBuildContract()'),
        )

    def test_initialize_cancels_pending_work_at_runtime_boundaries(self) -> None:
        initialize_source = _method_source('HeroAIHeadlessTree', 'initialize')

        self.assertGreaterEqual(
            initialize_source.count('self._build_contract_runner.reset()'),
            5,
        )
        self.assertIn(
            'if self._build_contract_map_signature != map_signature:',
            initialize_source,
        )


if __name__ == '__main__':
    unittest.main()
