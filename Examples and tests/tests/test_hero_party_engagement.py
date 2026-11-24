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
class HeroEngagementTests(unittest.TestCase):
    def test_scan_expands_only_for_detected_hero_combat(self) -> None:
        import sys
        from unittest.mock import patch
        settings = SimpleNamespace(Settings=SimpleNamespace(COMBAT_RANGE_MODE_LEGACY=0))
        settings.Settings = lambda: SimpleNamespace(COMBAT_RANGE_MODE_LEGACY=0, get_combat_range_mode=lambda: 0)
        scope: dict[str, Any] = {"__package__": "offline_hero", "Range": SimpleNamespace(Earshot=SimpleNamespace(value=1000), Spellcast=SimpleNamespace(value=1248), Spirit=SimpleNamespace(value=2500)), "STAY_ALERT_TIME": 750}
        owner = SimpleNamespace(data=SimpleNamespace(party_position=0, hero_in_aggro=False), stay_alert_timer=SimpleNamespace(HasElapsed=lambda delay: True))
        # Leader selection short-circuits the settings singleton; the imported
        # module is still doubled only at its runtime boundary.
        with patch.dict(sys.modules, {"offline_hero.settings": settings}):
            scan = load("Py4GWCoreLib/HeroAI/cache_data.py", ["GetActiveScanRange"], scope)["GetActiveScanRange"]
            self.assertEqual(scan(owner), 1000)
            owner.data.hero_in_aggro = True
            self.assertEqual(scan(owner), 2500)
    def test_detect_and_acquire_hero_fight_without_player_target(self) -> None:
        positions = {1: (0, 0), 2: (2000, 0), 3: (2100, 0), 4: (8000, 0)}
        calls: list[int] = []
        class Filter:
            @staticmethod
            def ByDistance(ids: Any, xy: Any, distance: float) -> Any:
                return [i for i in ids if abs(positions[i][0] - xy[0]) <= distance]
        scope: dict[str, Any] = {"Range": SimpleNamespace(Spellcast=SimpleNamespace(value=1248), SafeCompass=SimpleNamespace(value=5000)), "GLOBAL_CACHE": SimpleNamespace(Party=SimpleNamespace(GetHeroes=lambda: [SimpleNamespace(agent_id=2)])), "AgentArray": SimpleNamespace(Filter=Filter, GetEnemyArray=lambda: [3, 4]), "Agent": SimpleNamespace(IsAlive=lambda agent: True, IsValid=lambda agent: True, GetXY=lambda agent: positions[agent], GetAllegiance=lambda agent: (0, "Enemy")), "Player": SimpleNamespace(GetXY=lambda: positions[1], GetTargetID=lambda: 0), "Utils": SimpleNamespace(Distance=lambda a, b: abs(a[0] - b[0])), "EnemyBlacklist": lambda: SimpleNamespace(is_blacklisted=lambda agent: False)}
        detect = load("Py4GWCoreLib/HeroAI/cache_data.py", ["HeroesInAggro"], scope)["HeroesInAggro"]
        cache = SimpleNamespace(data=SimpleNamespace(hero_in_aggro=detect(None, [3, 4], 1248)))
        self.assertTrue(cache.data.hero_in_aggro)
        methods = load("Py4GWCoreLib/HeroAI/combat.py", ["_nearest_enemy_engaging_heroes", "_acquire_hero_engagement_target"], scope)
        owner: Any = SimpleNamespace(cached_data=cache, _is_target_within_guard_anchor_range=lambda agent: True, _is_blacklisted_enemy_target=lambda agent: False, SafeInteract=calls.append, MaybeCallCombatTarget=lambda *args, **kwargs: None)
        owner._nearest_enemy_engaging_heroes = lambda: methods["_nearest_enemy_engaging_heroes"](owner)
        self.assertTrue(methods["_acquire_hero_engagement_target"](owner))
        self.assertEqual(calls, [3], "join the nearby hero enemy, never the out-of-compass enemy")
        owner._is_target_within_guard_anchor_range = lambda agent: False
        self.assertFalse(methods["_acquire_hero_engagement_target"](owner))
        self.assertEqual(calls, [3], "guard-anchor refusal must issue no second interaction")
if __name__ == "__main__": unittest.main(verbosity=2)
