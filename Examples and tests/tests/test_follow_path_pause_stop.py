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
class PauseStopTests(unittest.TestCase):
    def test_real_generator_stops_once_then_resumes(self) -> None:
        import sys
        from unittest.mock import patch
        moves: list[tuple[float, float]] = []
        state = SimpleNamespace(paused=False, xy=(0., 0.), map_id=1)
        def wait(delay: int) -> Any:
            yield delay
        checks = SimpleNamespace(Map=SimpleNamespace(MapValid=lambda: True), Party=SimpleNamespace(IsPartyWiped=lambda: False))
        scope: dict[str, Any] = {"__package__": "offline.routines_src.yield_src", "Player": SimpleNamespace(GetXY=lambda: state.xy, GetAgentID=lambda: 1, Move=lambda x, y: moves.append((x, y))), "Agent": SimpleNamespace(IsValid=lambda agent: True, IsCasting=lambda agent: False), "Utils": SimpleNamespace(Distance=lambda a, b: abs(a[0] - b[0]), GetBaseTimestamp=lambda: 0), "GLOBAL_CACHE": SimpleNamespace(Party=SimpleNamespace(IsPartyDefeated=lambda: False)), "ConsoleLog": lambda *args, **kwargs: None, "Console": SimpleNamespace(MessageType=SimpleNamespace(Info=0, Debug=0, Warning=0)), "wait": wait}
        modules: dict[str, Any] = {"offline.routines_src.Checks": SimpleNamespace(Checks=checks), "offline.Pathing": SimpleNamespace(AutoPathing=object), "offline.Map": SimpleNamespace(Map=SimpleNamespace(GetMapID=lambda: state.map_id, IsInCinematic=lambda: False))}
        with patch.dict(sys.modules, modules):
            follow = load("Py4GWCoreLib/routines_src/yield_src/movement.py", ["FollowPath"], scope)["FollowPath"]
            route = follow([(400., 0.)], custom_pause_fn=lambda: state.paused, stop_on_party_wipe=False, autopath=False)
            next(route)
            self.assertEqual(moves, [(400., 0.)])
            state.paused = True
            next(route)
            self.assertEqual(moves, [(400., 0.), (0., 0.)], "pause must cancel the outstanding destination")
            next(route)
            self.assertEqual(len(moves), 2, "same pause must not issue repeated stop commands")
            state.paused = False
            next(route)
            self.assertEqual(moves[-1], (400., 0.), "existing resume path must dispatch its waypoint again")
            route.close()
if __name__ == "__main__": unittest.main(verbosity=2)
