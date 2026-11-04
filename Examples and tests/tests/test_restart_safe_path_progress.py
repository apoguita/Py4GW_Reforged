from __future__ import annotations
import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import unittest
ROOT = Path(__file__).resolve().parents[2]
def load(relative: str, names: list[str], scope: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8-sig"))
    nodes: list[ast.stmt] = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    namespace: dict[str, Any] = {"__name__": "offline_owner", **scope}
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), relative, "exec"), namespace)
    return namespace
class ProgressTests(unittest.TestCase):
    def test_real_nodes_record_progress_and_rebuild_forward(self) -> None:
        import sys, uuid, inspect
        from abc import ABC, abstractmethod
        from enum import Enum, auto
        from unittest.mock import patch
        class Icons:
            def __getattr__(self, name: str) -> str: return name
        scope: dict[str, Any] = {"ABC": ABC, "abstractmethod": abstractmethod, "Enum": Enum, "auto": auto, "uuid": uuid, "inspect": inspect, "ColorPalette": SimpleNamespace(GetColor=lambda name: 0), "IconsFontAwesome5": Icons(), "Utils": SimpleNamespace(GetBaseTimestamp=lambda: 0), "ConsoleLog": lambda *args, **kwargs: None}
        BT = load("Py4GWCoreLib/py4gwcorelib_src/BehaviorTree.py", ["BehaviorTree"], scope)["BehaviorTree"]
        scope["BehaviorTree"] = BT
        helpers = SimpleNamespace(as_tree=lambda item: item)
        scope["BTCompositeHelpers"] = helpers
        sequence = load("Py4GWCoreLib/routines_src/behaviourtrees_src/composite.py", ["Sequence"], scope)["Sequence"]
        state = SimpleNamespace(uptime=10000, map_id=1, xy=(0., 0.), allow_second=False)
        moved: list[float] = []
        def move(**kwargs: Any) -> Any:
            def action(node: Any) -> Any:
                if kwargs["x"] == 20 and not state.allow_second:
                    return BT.NodeState.RUNNING
                moved.append(kwargs["x"])
                state.xy = (kwargs["x"], kwargs["y"])
                return BT.NodeState.SUCCESS
            return BT(BT.ActionNode(action_fn=action))
        owner: Any = SimpleNamespace(_as_path=lambda points: [SimpleNamespace(x=x, y=y) for x, y in points], Move=move)
        scope.update({"__package__": "offline.routines_src.behaviourtrees_src", "BTMovement": owner, "BTComposite": SimpleNamespace(Sequence=sequence), "DEFAULT_MOVE_TOLERANCE": 1., "Map": SimpleNamespace(GetMapID=lambda: state.map_id, GetInstanceUptime=lambda: state.uptime), "Player": SimpleNamespace(GetXY=lambda: state.xy), "Utils": SimpleNamespace(GetBaseTimestamp=lambda: 0)})
        modules: dict[str, Any] = {"offline.routines_src.behaviourtrees_src.player": SimpleNamespace(BTPlayer=object), "offline.Py4GWcorelib": SimpleNamespace(Utils=SimpleNamespace(Distance=lambda a, b: abs(a[0] - b[0])))}
        with patch.dict(sys.modules, modules):
            build = load("Py4GWCoreLib/routines_src/behaviourtrees_src/movement.py", ["MovePath"], scope)["MovePath"]
            board: dict[str, Any] = {}
            first = build([(10., 0.), (20., 0.), (30., 0.)], resume_key="corridor", tolerance=1.)
            first.blackboard = board
            for _ in range(24):
                first.tick()
                if board["bt_move_path_progress:corridor"]["next_index"] == 1: break
            self.assertEqual(board["bt_move_path_progress:corridor"]["next_index"], 1)
            saved = board["bt_move_path_progress:corridor"]["next_index"]
            moved.clear()
            state.allow_second = True
            retry = build([(10., 0.), (20., 0.), (30., 0.)], resume_key="corridor", tolerance=1.)
            retry.blackboard = board
            for _ in range(32):
                if retry.tick() == BT.NodeState.SUCCESS: break
            self.assertEqual(moved, [20., 30.], f"completed corridor replayed: saved={saved}, moved={moved}")
            self.assertEqual(board["bt_move_path_progress:corridor"]["next_index"], 3)
            # Reusing a key on a different map or with a rewound map age must
            # not restore the old forward floor.
            for changed_map, uptime in [(2, 20000), (1, 0)]:
                state.map_id, state.uptime, state.xy = changed_map, uptime, (0., 0.)
                moved.clear()
                board["bt_move_path_progress:corridor"] = {"map_id": 1, "instance_uptime": 10000, "next_index": 2}
                fresh = build([(10., 0.), (20., 0.), (30., 0.)], resume_key="corridor", tolerance=1.)
                fresh.blackboard = board
                for _ in range(12):
                    fresh.tick()
                    if moved: break
                self.assertEqual(moved, [10.], f"stale floor survived map={changed_map}, uptime={uptime}")
            # Named restart runs the real planner method and real prior-tree
            # reset; a full Start boundary clears transient blackboard state.
            events: list[str] = []
            class ResetNode(BT.ActionNode):
                def reset(self) -> None:
                    events.append("cancel-old-tree")
                    super().reset()
            old = BT(ResetNode(action_fn=lambda node: BT.NodeState.RUNNING))
            old.blackboard.update({"bt_move_path_progress:corridor": {"map_id": 1, "next_index": 1}, "MOVING": True})
            parent: Any = SimpleNamespace(_planner_steps=[("corridor", None)], tree=old, planner_tree=old, _planner_sequence_name="route", planner_repeat=False)
            def replace(tree: Any) -> None:
                parent.tree = tree
                parent.planner_tree = tree
            parent._set_planner_tree = replace
            parent._build_named_planner_tree = lambda *args, **kwargs: BT(BT.SucceederNode())
            parent.Start = lambda: parent.tree.blackboard.clear()
            parent.Reset = parent.Start
            restart = load("Py4GWCoreLib/botting_tree_src/planner.py", ["RestartFromNamedPlannerStep"], scope)["RestartFromNamedPlannerStep"]
            self.assertTrue(restart(parent, "corridor"))
            self.assertEqual(events, ["cancel-old-tree"])
            self.assertNotIn("MOVING", parent.tree.blackboard)
            self.assertEqual(parent.tree.blackboard["bt_move_path_progress:corridor"]["next_index"], 1)
if __name__ == "__main__": unittest.main(verbosity=2)
