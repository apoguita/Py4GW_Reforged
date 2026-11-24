"""Canonical captured-blessing bridge for the legacy Simple Vanquish widget."""

from collections.abc import Mapping
from typing import Any, cast

CAPTURED_BLESSING_KEYS = frozenset({
    "bless",
    "vanguard_blessing",
    "norn_blessing",
    "asuran_blessing",
})
ROUTE_BLESSING_KEYS = CAPTURED_BLESSING_KEYS | {"faction_blessing"}


def build_route_blessing_tree(blessing_data: Mapping[str, Any], wrappers=None):
    """Delegate an immutable route record to the canonical blessing owner."""
    if wrappers is None:
        from Sources.ApoSource.ApoBottingLib import wrappers

    captured_blessing = dict(blessing_data)
    route_standoff = captured_blessing.get(
        "route_standoff_xy",
        captured_blessing.get("player_approach_xy"),
    )
    if route_standoff is None:
        route_standoff = captured_blessing.get("target_xy")
    if route_standoff is None:
        raise ValueError(
            "route blessing requires route_standoff_xy, player_approach_xy, or target_xy"
        )

    faction = str(captured_blessing.get("faction", "")).strip().lower()
    if faction:
        return wrappers.TakeBlessing(
            pos=route_standoff,
            faction=faction,
            multi_account=False,
            log=True,
        )

    return cast(Any, wrappers.TakeBlessing)(
        pos=route_standoff,
        buttons=int(captured_blessing.get("buttons", 0)),
        multi_account=False,
        log=True,
        captured_blessing=captured_blessing,
    )


build_captured_blessing_tree = build_route_blessing_tree


def _load_runtime_dependencies():
    from Py4GWCoreLib import Routines
    from Py4GWCoreLib.BottingTree import BottingTree
    from Sources.ApoSource.ApoBottingLib import wrappers
    from Sources.ApoSource.ApoBottingLib.helpers import CanonicalDialogueStateScope

    return BottingTree, Routines, wrappers, CanonicalDialogueStateScope


def run_route_blessing(bot, blessing_data: Mapping[str, Any]):
    """Run canonical TakeBlessing while the host route waits at one state."""
    planner = None
    scope = None
    saved_pause = False
    pause_restore_required = False
    try:
        try:
            BottingTree, Routines, wrappers, CanonicalDialogueStateScope = (
                _load_runtime_dependencies()
            )
            scope = CanonicalDialogueStateScope()
            canonical_blessing = build_route_blessing_tree(
                blessing_data,
                wrappers=wrappers,
            )
            planner = BottingTree.Create(
                bot_name="Simple Vanquish captured blessing",
                main_routine=canonical_blessing,
                pause_on_combat=False,
                multi_account=False,
                auto_loot=False,
                isolation_enabled=False,
                manage_account_isolation=False,
                headless_heroai_enabled=False,
            )
            saved_pause = bool(bot.Properties.Get("hero_ai_paused", "active"))
            pause_restore_required = True
            bot.Properties.ApplyNow("hero_ai_paused", "active", True)
            planner.Start()

            while planner.IsStarted():
                scope.run(planner.tick)
                yield from Routines.Yield.wait(50)

            status = str(planner.GetBlackboardValue("PLANNER_STATUS", ""))
            if status != "PLANNER: Completed":
                raise RuntimeError(
                    "canonical captured-blessing owner failed "
                    f"({status or 'no status'})"
                )
            return True
        finally:
            try:
                if scope is not None:
                    scope.close()
            finally:
                try:
                    if planner is not None:
                        planner.Stop()
                finally:
                    if pause_restore_required:
                        bot.Properties.ApplyNow("hero_ai_paused", "active", saved_pause)
    except Exception:
        bot.Stop()
        raise


run_captured_blessing = run_route_blessing
