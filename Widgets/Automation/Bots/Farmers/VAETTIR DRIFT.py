from __future__ import annotations

import os
import math
import zlib
from collections.abc import Callable, Generator
from typing import Any, cast

import PyImGui
import PySystem

from Py4GWCoreLib import Agent, ConsoleLog, Dialog, GLOBAL_CACHE, Map, Party, Player, Routines, Utils
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.botting_tree_src.account_config import BottingTreeAccountConfig
from Py4GWCoreLib.BuildMgr import BuildMgr
from Py4GWCoreLib.Builds.Assassin.A_Me.SF_Ass_vaettir import SF_Ass_vaettir
from Py4GWCoreLib.Builds.Mesmer.Me_A.SF_Mes_vaettir import SF_Mes_vaettir
from Py4GWCoreLib.Item import Item
from Py4GWCoreLib.enums import Range, TitleID
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.py4gwcorelib_src.AutoInventoryHandler import AutoInventoryHandler
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters import LootFilters
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Sources.ApoSource.ApoBottingLib import wrappers as BT

MODULE_NAME = "VAETTIR DRIFT"
MODULE_CATEGORY = "Automation"
MODULE_TAGS = ["Vaettir", "Farm", "BottingTree", "Hard Mode"]
MODULE_ALIASES = ["YAVB", "YAVB 2.0", "YAVB 2.0 BT", "Vaettir Drift"]
MODULE_DESCRIPTION = """Jaga Moraine Vaettir farm for A/Me and Me/A Shadow Form builds.
Handles the Norn blessing, aggro route, wall positioning, loot and repeat.
Includes session timings, movement watchdog and explicit failure diagnostics.
Prepares the original YAVB Assassin/Mesmer or Mesmer/Assassin skillbar in Longeyes.
Consumables, merchants and inventory restocking remain manual.
BT Planner workflow based on Drift, with YAVB build preparation.
"""
MODULE_ICON = "Assets\\Textures\\Module_Icons\\VAETTIR DRIFT.png"
BOT_TEXTURE = os.path.join(PySystem.Console.get_projects_path(), MODULE_ICON)
INI_PATH = "Widgets/Automation/Bots/YAVB 2.0"
INI_FILENAME = "YAVB_2_0_BT.ini"
# Keep the existing account settings path when renaming the widget.
LONGEYES, BJORA, JAGA = 650, 482, 546
NORN_RANK_TWO_POINTS = 4_000
OUTPOST_DEATH_PENALTY = 60
TOT_BAG_MODEL_ID = int(ModelID.Trick_Or_Treat_Bag.value)
TOT_BATCH_SIZE = 250
JAGA_KILL_TARGET = 50
BALLING_STEP_TIMEOUT_MS = 120_000
HEART_ATTEMPT_TIMEOUT_MS = 8000
HEART_RETRY_COOLDOWN_MS = 12000  # avoid repeated requests while skill is unavailable
KILL_SPOT = (12485.18, -17260.41)
NORN_NPC = (13367, -20771)
JAGA_PORTAL_FLAG = (15495.16, -20762.87)
NORN_BLESSING_IDS = (2469, 2470, 2471, 2472, 2551, 2591, 2592, 2593, 2594)

# Coordinates and route order copied from YAVB 2.0.py.
BJORA_ROUTE: list[tuple[float, float]] = [
    (17810, -17649),
    (17516, -17270),
    (17166, -16813),
    (16862, -16324),
    (16472, -15934),
    (15929, -15731),
    (15387, -15521),
    (14849, -15312),
    (14311, -15101),
    (13776, -14882),
    (13249, -14642),
    (12729, -14386),
    (12235, -14086),
    (11748, -13776),
    (11274, -13450),
    (10839, -13065),
    (10572, -12590),
    (10412, -12036),
    (10238, -11485),
    (10125, -10918),
    (10029, -10348),
    (9909, -9778),
    (9599, -9327),
    (9121, -9009),
    (8674, -8645),
    (8215, -8289),
    (7755, -7945),
    (7339, -7542),
    (6962, -7103),
    (6587, -6666),
    (6210, -6226),
    (5834, -5788),
    (5457, -5349),
    (5081, -4911),
    (4703, -4470),
    (4379, -3990),
    (4063, -3507),
    (3773, -3031),
    (3452, -2540),
    (3117, -2070),
    (2678, -1703),
    (2115, -1593),
    (1541, -1614),
    (960, -1563),
    (388, -1491),
    (-187, -1419),
    (-770, -1426),
    (-1343, -1440),
    (-1922, -1455),
    (-2496, -1472),
    (-3073, -1535),
    (-3650, -1607),
    (-4214, -1712),
    (-4784, -1759),
    (-5278, -1492),
    (-5754, -1164),
    (-6200, -796),
    (-6632, -419),
    (-7192, -300),
    (-7770, -306),
    (-8352, -286),
    (-8932, -258),
    (-9504, -226),
    (-10086, -201),
    (-10665, -215),
    (-11247, -242),
    (-11826, -262),
    (-12400, -247),
    (-12979, -216),
    (-13529, -53),
    (-13944, 341),
    (-14358, 743),
    (-14727, 1181),
    (-15109, 1620),
    (-15539, 2010),
    (-15963, 2380),
    (-18048, 4223),
    (-19196, 4986),
    (-20000, 5595),
    (-20300, 5600),
]
JAGA_ROUTES: list[list[tuple[float, float]]] = [
    [
        (13367, -20771),
        (11375, -22761),
        (10925, -23466),
        (10917, -24311),
        (10280, -24620),
        (10280, -24620),
        (9640, -23175),
        (7815, -23200),
        # Blacklisted (6626.51, -23167.24): reported stuck near (6688, -22575).
        # End this leg here; the next route starts at (7765, -22940).
    ],
    [(7765, -22940), (8213, -22829), (8740, -22475), (8880, -21384), (8684, -20833), (8982, -20576)],
    [(10196, -20124), (10123, -19529), (10049, -18933)],
    [(9976, -18338), (11316, -18056), (10392, -17512), (10114, -16948)],
    [
        (10729, -16273),
        (10505, -14750),
        (10815, -14790),
        (11090, -15345),
        (11670, -15457),
        (12604, -15320),
        (12450, -14800),
        (12725, -14850),
        (12476, -16157),
    ],
    [
        (13070, -16911),
        (12938, -17081),
        (12790, -17201),
        (12747, -17220),
        (12703, -17239),
        (12684, -17184),
        (12485.18, -17260.41),
    ],
]

botting_tree: BottingTree | None = None
_death_recovery_tree: BehaviorTree | None = None
ini_key = ""
runtime: dict[str, Any] = {
    "build": None,
    "prepared": False,
    "farming": False,
    "waiting": False,
    "killing": False,
    "finished": False,
    "stuck_count": 0,
    "returning_from_jaga": False,
    "stop_reason": "",
    "run_started": None,
    "kill_timed_out": False,
    "last_stop": "",
    "balling": False,
    "heart_requested": False,
    "heart_casting": False,
    "heart_next_attempt_at": 0,
    "isolation_verified": False,
    "isolation_group": 0,
    "isolation_ready_once": False,
    "isolation_check_at": 0,
    "isolation_failed_at": None,
    "recovering": False,
    "death_penalty": None,
    "restore_revival_skills": False,
    "kill_anchor": None,
    "route_recovery_reason": "",
    "wall_retries": 0,
    "failed_step": "",
    "step_retry_at": 0,
    "step_failures": {},
    "current_step": "",
    "opening_tot_bags": False,
    "tot_progress": "",
    "jaga_kills": 0,
    "reset_after_clear": False,
    "exiting_jaga": False,
}
stats: dict[str, int | float] = {
    "attempts": 0,
    "completed": 0,
    "incomplete": 0,
    "interrupted": 0,
    "last_ms": 0,
    "best_ms": 0,
    "total_ms": 0,
    "unstuck": 0,
    "heart_requests": 0,
    "deaths": 0,
    "restarts_after_death": 0,
    "route_retries": 0,
    "route_rebuilds": 0,
    "step_retries": 0,
    "tot_bags_opened": 0,
    "tot_batches_opened": 0,
    "threshold_resets": 0,
}


def _log(message: str, kind: int = PySystem.Console.MessageType.Info) -> None:
    ConsoleLog(MODULE_NAME, message, kind, True)


def _action(name: str, callback: Callable[[], bool | None]) -> BehaviorTree:
    def tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        result = callback()
        return BehaviorTree.NodeState.FAILURE if result is False else BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name=name, action_fn=tick))


class _GeneratorAction(BehaviorTree.Node):
    """Close suspended work on the framework's public reset lifecycle."""

    blackboard: dict[str, Any]

    def __init__(self, name: str, factory: Callable[[], Generator[Any, Any, Any]]) -> None:
        self.factory = factory
        self.generator: Generator[Any, Any, Any] | None = None
        super().__init__(name=name, node_type="GeneratorAction", node_category="leaf")

    def _tick_impl(self) -> BehaviorTree.NodeState:
        if self.generator is None:
            self.generator = self.factory()
        try:
            next(self.generator)
            return BehaviorTree.NodeState.RUNNING
        except StopIteration as done:
            self.generator = None
            return BehaviorTree.NodeState.FAILURE if done.value is False else BehaviorTree.NodeState.SUCCESS

    def reset(self) -> None:
        generator, self.generator = self.generator, None
        try:
            if generator is not None:
                generator.close()
        finally:
            super().reset()


def _generator_step(name: str, factory: Callable[[], Generator[Any, Any, Any]]) -> BehaviorTree:
    return BehaviorTree(_GeneratorAction(name, factory))


_missing_build_methods: set[str] = set()


def _build_set(build: Any, method_name: str, value: Any) -> bool:
    """Support older vaettir build classes without crashing on missing setters."""
    method = getattr(build, method_name, None)
    if not callable(method):
        if method_name not in _missing_build_methods:
            _missing_build_methods.add(method_name)
            _log(
                f"Installed {type(build).__name__} has no {method_name}; update the Vaettir build in CoreLib "
                "to restore full behavior. The corresponding control is disabled.",
                PySystem.Console.MessageType.Warning,
            )
        return False
    method(value)
    return True


def _reset_farm_state() -> None:
    global _death_recovery_tree
    if _death_recovery_tree is not None:
        _death_recovery_tree.reset()
        _death_recovery_tree = None
    runtime.update(
        prepared=False,
        farming=False,
        waiting=False,
        killing=False,
        finished=False,
        stuck_count=0,
        returning_from_jaga=False,
        stop_reason="",
        balling=False,
        heart_requested=False,
        heart_casting=False,
        heart_next_attempt_at=0,
        isolation_verified=False,
        isolation_group=0,
        isolation_ready_once=False,
        isolation_check_at=0,
        isolation_failed_at=None,
        recovering=False,
        death_penalty=None,
        restore_revival_skills=False,
        kill_anchor=None,
        route_recovery_reason="",
        wall_retries=0,
        failed_step="",
        step_retry_at=0,
        step_failures={},
        current_step="",
        opening_tot_bags=False,
        tot_progress="",
        jaga_kills=0,
        reset_after_clear=False,
        exiting_jaga=False,
    )
    build = runtime["build"]
    if build is not None:
        # No Heart suppression setter in the installed build.
        _build_set(build, "SetKillingRoutine", False)
        _build_set(build, "SetRoutineFinished", False)
        _build_set(build, "SetStuckSignal", 0)


def _finish_run(*, interrupted: bool = False) -> None:
    started = runtime["run_started"]
    if started is None:
        return
    runtime["run_started"] = None
    if interrupted:
        stats["interrupted"] += 1
        return
    duration = max(0, Utils.GetBaseTimestamp() - started)
    stats["last_ms"] = duration
    if runtime["kill_timed_out"]:
        stats["incomplete"] += 1
        return
    stats["completed"] += 1
    stats["total_ms"] += duration
    if not stats["best_ms"] or duration < stats["best_ms"]:
        stats["best_ms"] = duration


def _queue_step_recovery(name: str, reason: str) -> None:
    if runtime.get("route_recovery_reason"):
        return
    runtime["failed_step"] = name
    runtime["route_recovery_reason"] = reason
    runtime["step_retry_at"] = Utils.GetBaseTimestamp() + 2000
    _log(f"{reason} Automatic retry queued; the bot remains started.", PySystem.Console.MessageType.Warning)


def _restart_planner(tree: BottingTree, step: str) -> None:
    if tree.RestartFromNamedPlannerStep(step, auto_start=False):
        return
    # Recover missing planner metadata after a reset instead of cutting off
    # the post-revival flow. Rebuild through the framework's public API.
    steps = get_execution_steps()
    if step not in {name for name, _factory in steps}:
        step = "Initialize Bot"
    tree.SetNamedPlannerSteps(steps, start_from=step, name="VaettirDriftSequence", repeat=True)
    tree.Reset()


def _checked_step(name: str, factory: Callable[[], BehaviorTree]) -> BehaviorTree:
    def run() -> Generator[Any, Any, bool]:
        runtime["current_step"] = name
        child = factory()
        started = Utils.GetBaseTimestamp()
        balling_move = name.startswith(tuple(f"Clear {index:02d} -" for index in (5, 7, 9, 11, 13, 15)))
        try:
            while True:
                child.blackboard = action.blackboard
                result = child.tick()
                if result != BehaviorTree.NodeState.RUNNING:
                    if result == BehaviorTree.NodeState.FAILURE:
                        _queue_step_recovery(name, f"Step failed: {name}.")
                        # main() handles recovery after this tick. Do
                        # not emit FAILURE: the planner would auto-Start first
                        # and replace the isolation snapshot before our Stop.
                        while True:
                            yield
                    failures = cast(dict[str, int], runtime.get("step_failures", {}))
                    failures.pop(name, None)
                    return True
                if balling_move and Utils.GetBaseTimestamp() - started >= BALLING_STEP_TIMEOUT_MS:
                    _queue_step_recovery(name, f"Balling movement exceeded two minutes: {name}.")
                    while True:
                        yield
                yield
        finally:
            child.reset()

    action = _GeneratorAction(name, run)
    return BehaviorTree(action)


def _jaga_kill_target_met() -> bool:
    if Map.GetMapID() != JAGA:
        return False
    kills = Map.GetFoesKilled()
    runtime["jaga_kills"] = kills
    return kills >= JAGA_KILL_TARGET


def _tick_clear_completion(tree: BottingTree) -> bool:
    if (
        not runtime["prepared"]
        or not runtime["farming"]
        or runtime.get("reset_after_clear", False)
        or runtime["restore_revival_skills"]
        or not _jaga_kill_target_met()
    ):
        return False
    tree.Reset()
    _set_balling(False)
    runtime.update(
        reset_after_clear=True,
        farming=False,
        waiting=False,
        killing=False,
        finished=True,
        kill_timed_out=False,
        route_recovery_reason="",
        failed_step="",
        step_retry_at=0,
    )
    build = runtime["build"]
    if build is not None:
        _build_set(build, "SetKillingRoutine", False)
        _build_set(build, "SetRoutineFinished", True)
    _restart_planner(tree, "Clear 18 - Loot Drops")
    stats["threshold_resets"] += 1
    _log(
        f"Jaga: {runtime['jaga_kills']} enemies killed (target {JAGA_KILL_TARGET}). Looting and resetting via Bjora; no further clear in this instance."
    )
    return True


def _tick_route_recovery(tree: BottingTree) -> None:
    reason = str(runtime["route_recovery_reason"])
    if not reason:
        return
    if _tick_clear_completion(tree):
        return
    if Utils.GetBaseTimestamp() < runtime["step_retry_at"]:
        return
    failed_step = str(runtime["failed_step"])
    runtime["route_recovery_reason"] = ""
    runtime["failed_step"] = ""
    runtime["step_retry_at"] = 0
    failures = cast(dict[str, int], runtime.get("step_failures", {}))
    failures[failed_step] = failures.get(failed_step, 0) + 1
    runtime["step_failures"] = failures
    if failed_step == "Clear 16 - Position Against Wall":
        runtime["wall_retries"] += 1
        rebuild = runtime["wall_retries"] > 2
        step = "Restore Skills After Revival" if rebuild else "Clear 15 - Final Approach"
    else:
        rebuild = (
            failures[failed_step] > 2
            and (
                failed_step.startswith(tuple(f"Clear {index:02d} -" for index in range(5, 18)))
                or failed_step == "Traverse Bjora Marches"
            )
            and Map.GetMapID() in (BJORA, JAGA)
            and runtime["build"] is not None
        )
        step = "Restore Skills After Revival" if rebuild else failed_step
    # Close the failed planner before replacing it. Reset keeps the bot started
    # and preserves the original isolation snapshot; Start would overwrite it.
    tree.Reset()
    if runtime["build"] is not None:
        _set_balling(False)
    runtime.update(waiting=False, killing=False, finished=False, kill_anchor=None)
    build = runtime["build"]
    if build is not None:
        _build_set(build, "SetKillingRoutine", False)
        _build_set(build, "SetRoutineFinished", False)
    if rebuild:
        _finish_run(interrupted=True)
        runtime["restore_revival_skills"] = True
        stats["route_rebuilds"] += 1
    else:
        stats["route_retries"] += 1
    stats["step_retries"] += 1
    _restart_planner(tree, step)
    _log(
        f"{reason} {'Restoring defenses and rebuilding the normal clear in this instance.' if rebuild else f'Retrying {step}.'}",
        PySystem.Console.MessageType.Warning,
    )


def _apply_and_check_isolation() -> bool:
    tree = ensure_botting_tree()
    email = Player.GetAccountEmail()
    if not email or GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(email) is None:
        runtime["isolation_verified"] = False
        return False
    other_groups = {
        int(account.IsolationGroupID)
        for account in GLOBAL_CACHE.ShMem.GetAllAccountData(include_isolated=True)
        if account.IsAccount and account.AccountEmail.casefold() != email.casefold() and account.IsolationGroupID > 0
    }
    group = int(runtime["isolation_group"])
    if group <= 0 or group in other_groups:
        group = 1 + zlib.crc32(email.casefold().encode("utf-8")) % 1_000_000
        while group in other_groups:
            group = group % 1_000_000 + 1
        runtime["isolation_group"] = group
    tree.SetIsolationEnabled(True)
    if GLOBAL_CACHE.ShMem.GetAccountGroupByEmail(email) != group:
        GLOBAL_CACHE.ShMem.SetAccountGroupByEmail(email, group)
    verified = (
        tree.IsSingleAccountMode()
        and tree.IsIsolationEnabled()
        and not tree.account_config.sync_party_isolation
        and GLOBAL_CACHE.ShMem.IsAccountIsolated(email)
        and GLOBAL_CACHE.ShMem.GetAccountGroupByEmail(email) == group
        and group not in other_groups
    )
    runtime["isolation_verified"] = bool(verified)
    return bool(verified)


def _verify_isolation() -> Generator[Any, Any, bool]:
    deadline = Utils.GetBaseTimestamp() + 5000
    while Utils.GetBaseTimestamp() < deadline:
        if _apply_and_check_isolation():
            runtime["isolation_ready_once"] = True
            _log(f"Single-account isolation verified (group {runtime['isolation_group']}).")
            return True
        yield from Routines.Yield.wait(100)
    _log("Account isolation could not be verified in shared memory.", PySystem.Console.MessageType.Error)
    return False


def _isolation_ready_for_tick() -> bool:
    if not runtime["isolation_ready_once"]:
        return True
    now = Utils.GetBaseTimestamp()
    if now >= runtime["isolation_check_at"] or not runtime["isolation_verified"]:
        runtime["isolation_check_at"] = now + 1000
        if _apply_and_check_isolation():
            runtime["isolation_failed_at"] = None
        elif runtime["isolation_failed_at"] is None:
            runtime["isolation_failed_at"] = now
        elif now - runtime["isolation_failed_at"] >= 5000:
            runtime["stop_reason"] = "Account isolation was lost and could not be restored within five seconds."
    return bool(runtime["isolation_verified"])


def _travel_to_start() -> BehaviorTree:
    def build(_node: BehaviorTree.Node) -> BehaviorTree:
        if Map.GetMapID() in (BJORA, JAGA):
            # Never travel back to Longeyes merely because Planner/runtime was reset.
            # Field characters resume from the current explorable instance.
            return BT.Succeeder("Continue in current Bjora/Jaga instance")
        _log(f"Town preparation: travelling to Longeyes (current map={Map.GetMapID()}, prepared={runtime['prepared']}).")
        return RoutinesBT.Map.TravelToOutpost(outpost_id=LONGEYES, log=True, timeout=60_000)

    return BT.Subtree("Travel to Longeyes Ledge on start", build)


def _death_penalty_percent() -> int | None:
    # Py4GW exposes raw morale: 100 is neutral and 40 is -60%.
    # Zero is also the missing-world-context fallback, not a valid penalty.
    morale = Player.GetMorale()
    return max(0, 100 - morale) if 40 <= morale <= 110 else None


def _tick_death_recovery(tree: BottingTree) -> bool:
    global _death_recovery_tree
    dead = Agent.IsDead(Player.GetAgentID())
    defeated = GLOBAL_CACHE.Party.IsPartyDefeated()
    # Do not classify a completed solo clear as a wipe if the player is alive.
    if not dead:
        defeated = False
    if not runtime["recovering"]:
        if not dead and not defeated:
            return False
        _finish_run(interrupted=True)
        # Reset suspended loot/combat work without Stop/Start: keep the original
        # isolation snapshot so a later user Stop still restores the prior state.
        tree.Reset()
        _reset_farm_state()
        runtime["recovering"] = True
        stats["deaths"] += 1
        _death_recovery_tree = tree.PartyWipeRecoveryServiceTree(default_step_name="Initialize Bot")
        _death_recovery_tree.blackboard = {
            "current_step_name": "Initialize Bot",
            "named_planner_step_names": tree.GetNamedPlannerStepNames(),
        }
        _log(
            "Death detected. Waiting for revival; return to outpost requires 60% death penalty.",
            PySystem.Console.MessageType.Warning,
        )

    penalty = _death_penalty_percent()
    runtime["death_penalty"] = penalty
    return_allowed = penalty is not None and penalty >= OUTPOST_DEATH_PENALTY
    if not dead and not defeated:
        # Rebuild the ball in the same instance below the requested threshold.
        # At 60%, reset preparation so normal startup travel clears the penalty.
        map_id = Map.GetMapID()
        resume_here = not return_allowed and map_id in (BJORA, JAGA)
        if runtime["build"] is not None:
            _set_balling(False)
        runtime["prepared"] = resume_here
        runtime["restore_revival_skills"] = resume_here
        runtime["farming"] = bool(resume_here and map_id == JAGA and _jaga_kill_target_met())
        _restart_planner(tree, "Initialize Bot")
        if _death_recovery_tree is not None:
            _death_recovery_tree.reset()
            _death_recovery_tree = None
        runtime["recovering"] = False
        stats["restarts_after_death"] += 1
        _log(
            "Revival confirmed. Restarting in the current instance below 60% death penalty."
            if resume_here
            else "Revival confirmed. Restarting outpost preparation (60% penalty or already outside the farm)."
        )
        return True

    # The shared defeat service can issue ReturnToOutpost. Never tick it below
    # the threshold, including when the morale read is unavailable.
    if return_allowed and _death_recovery_tree is not None:
        _death_recovery_tree.tick()
    return True


def _assign_build() -> bool:
    primary, secondary = Agent.GetProfessionNames(Player.GetAgentID())
    # YAVB chooses the build from the PRIMARY profession only. The skill
    # template loader then applies the required secondary profession in town.
    build_type: type[BuildMgr] | None = {
        "Assassin": SF_Ass_vaettir,
        "Mesmer": SF_Mes_vaettir,
    }.get(primary)
    if build_type is None:
        _log(f"Unsupported primary profession: {primary} (secondary: {secondary}).", PySystem.Console.MessageType.Error)
        return False
    target_secondary = "Mesmer" if primary == "Assassin" else "Assassin"
    if secondary != target_secondary:
        _log(f"Preparing {primary}/{target_secondary} from {primary}/{secondary} via skill template.")
    if not isinstance(runtime["build"], build_type):
        runtime["build"] = build_type()
        # Use original build methods only; no suppression API exists in Apo CoreLib.
    return True


def _inventory_pass() -> Generator[Any, Any, None]:
    from Sources.frenkeyLib.ItemHandling.Items.item_snapshot import ItemSnapshot

    handler = AutoInventoryHandler()
    previous_active = handler.module_active
    handler.module_active = False
    try:
        identify_rarities = {
            rarity
            for enabled, rarity in (
                (handler.id_whites, "White"),
                (handler.id_blues, "Blue"),
                (handler.id_purples, "Purple"),
                (handler.id_golds, "Gold"),
                (handler.id_greens, "Green"),
            )
            if enabled
        }
        live_ids = GLOBAL_CACHE.Inventory.GetAllInventoryItemIds()
        item_ids = []
        for item_id in live_ids:
            if Item.Usage.IsIdentified(item_id):
                continue
            _, rarity = Item.Rarity.GetRarity(item_id)
            if rarity in identify_rarities and Item.GetModelID(item_id) not in handler.id_model_blacklist:
                item_ids.append(item_id)
        if item_ids:
            yield from Routines.Yield.Items.IdentifyItemsAndVerify(item_ids, log=False)
        salvage_ids = [
            item.id
            for item_id in GLOBAL_CACHE.Inventory.GetAllInventoryItemIds()
            if (item := ItemSnapshot.from_item_id(item_id)) is not None
            if handler._get_salvage_skip_reason(item, set()) is None
        ]
        if salvage_ids:
            yield from Routines.Yield.Items.SalvageItemsAndVerify(salvage_ids, log=False)
        # The old AutoInventoryHandler identify/salvage/deposit generators are
        # disabled in this Ap0 revision. Use the live item generators for the
        # configured identify/salvage choices; leave deposit policy untouched.
    finally:
        handler.module_active = previous_active


def _mark_prepared() -> None:
    runtime["prepared"] = True


def _refresh_build_after_skillbar() -> None:
    current: SF_Ass_vaettir | SF_Mes_vaettir = runtime["build"]
    runtime["build"] = type(current)()
    # The loaded build uses its own original skill rotation.


def _revival_defenses_ready(build: SF_Ass_vaettir | SF_Mes_vaettir) -> bool:
    player_id = Player.GetAgentID()
    remaining_ms = cast(float, GLOBAL_CACHE.Effects.GetEffectTimeRemaining(player_id, build.shadow_form))
    return (
        GLOBAL_CACHE.Effects.HasEffect(player_id, build.shadow_form)
        and remaining_ms > 5000
        and GLOBAL_CACHE.Effects.HasEffect(player_id, build.shroud_of_distress)
    )


def _restore_skills_after_revival() -> Generator[Any, Any, bool]:
    if not runtime["restore_revival_skills"]:
        return True
    _refresh_build_after_skillbar()
    build: SF_Ass_vaettir | SF_Mes_vaettir = runtime["build"]
    _build_set(build, "SetKillingRoutine", False)
    _build_set(build, "SetRoutineFinished", False)
    _build_set(build, "SetStuckSignal", 0)
    # No Heart suppression setter in the installed build.
    runtime["prepared"] = True
    deadline = Utils.GetBaseTimestamp() + 90_000
    _log("Revival: rebuilding skill rotation and restoring defenses before the normal clear route.")
    while not _revival_defenses_ready(build):
        if Agent.IsDead(Player.GetAgentID()):
            return False
        if Utils.GetBaseTimestamp() >= deadline:
            _log(
                "Could not restore Shadow Form and Shroud of Distress after revival. Check skillbar, energy and recharge.",
                PySystem.Console.MessageType.Error,
            )
            return False
        yield from Routines.Yield.wait(100)
    runtime["restore_revival_skills"] = False
    if _jaga_kill_target_met():
        runtime["farming"] = True
        _log("Defenses restored; the kill target is already met. Continuing to loot and reset.")
        # Let main switch planners before any clear movement can run this tick.
        yield
        return True
    _log("Defenses restored. Resuming the normal clear route from the beginning.")
    return True


def _norn_rank_two_reached() -> bool:
    title = Player.GetTitle(TitleID.Norn.value)
    return title is not None and title.current_points >= NORN_RANK_TWO_POINTS


def _recruit_norn_henchmen() -> Generator[Any, Any, bool]:
    if _norn_rank_two_reached():
        _log("Norn rank 2 reached; Longeyes henchmen are no longer required.")
        return True
    if Party.GetHenchmanCount() >= 3:
        return True
    if not Party.IsPartyLeader():
        _log(
            "Three henchmen are required: only the party leader can recruit them in Longeyes.",
            PySystem.Console.MessageType.Error,
        )
        return False
    needed = 3 - Party.GetHenchmanCount()
    max_size = Map.GetMaxPartySize()
    if max_size and Party.GetPartySize() + needed > max_size:
        _log(
            f"Three henchmen need {needed} free party slots in Longeyes (party {Party.GetPartySize()}/{max_size}).",
            PySystem.Console.MessageType.Error,
        )
        return False

    # Henchman IDs are outpost-specific. Try the available Longeyes slots,
    # checking the live party count after each request instead of assuming success.
    for henchman_id in range(1, 9):
        if Party.GetHenchmanCount() >= 3:
            break
        previous_count = Party.GetHenchmanCount()
        Party.Henchmen.AddHenchman(henchman_id)
        deadline = Utils.GetBaseTimestamp() + 1500
        while Utils.GetBaseTimestamp() < deadline and Party.GetHenchmanCount() == previous_count:
            yield from Routines.Yield.wait(100)

    if Party.GetHenchmanCount() < 3:
        _log(
            f"Only {Party.GetHenchmanCount()}/3 henchmen joined in Longeyes. Add the missing henchmen manually and restart.",
            PySystem.Console.MessageType.Error,
        )
        return False
    _log("Three Longeyes henchmen are ready for the Norn challenge.")
    return True


def _has_flaggable_companions() -> bool:
    return Party.GetHeroCount() > 0 or (Party.IsPartyLeader() and Party.GetHenchmanCount() > 0)


def _release_companions_for_challenge() -> None:
    if _has_flaggable_companions():
        Party.Heroes.UnflagAllHeroes()


def _flag_companions_at_portal() -> None:
    if _has_flaggable_companions():
        Party.Heroes.FlagAllHeroes(*JAGA_PORTAL_FLAG)
        _log(f"Heroes and henchmen flagged at {JAGA_PORTAL_FLAG} after the Norn blessing.")


def _resume_field_preparation() -> bool:
    """Restore the prepared flag after a planner reset without town travel.

    The build is selected by Initialize Bot. Preparation from an outpost still
    performs the ordinary skillbar loading and HM setup.
    """
    if Map.GetMapID() in (BJORA, JAGA) and runtime["build"] is not None:
        if not runtime["prepared"]:
            _log("Already in explorable zone: resuming existing build; no Longeyes travel.")
        runtime["prepared"] = True
    return True


def _prepare_skillbar() -> BehaviorTree:
    """YAVB preparation: equip the appropriate original Vaettir build.

    Travel is an independent Planner step. Never reload the skillbar when
    recovering in Bjora/Jaga: that would interrupt the active farm.
    """
    def choose(_node: BehaviorTree.Node) -> BehaviorTree:
        if Map.GetMapID() in (BJORA, JAGA):
            return BT.Succeeder("Already prepared in explorable area")
        if Map.GetMapID() != LONGEYES:
            return BT.Failer("Skillbar preparation requires Longeyes")
        selected = runtime["build"]
        if selected is None:
            return BT.Failer("Vaettir build was not assigned")
        return BT.LoadSkillbar(selected.template_code)
    return BT.Subtree("Equip original YAVB skillbar", choose)


def _refresh_prepared_build() -> bool:
    if Map.GetMapID() in (BJORA, JAGA):
        return True
    if Map.GetMapID() != LONGEYES:
        return False
    _refresh_build_after_skillbar()
    return True


def _prepare_henchmen() -> Generator[Any, Any, bool]:
    if Map.GetMapID() in (BJORA, JAGA):
        return True
    if Map.GetMapID() != LONGEYES:
        return False
    return (yield from _recruit_norn_henchmen())


def _validate_preparation() -> bool:
    if Map.GetMapID() in (BJORA, JAGA):
        return True
    if Map.GetMapID() != LONGEYES:
        _log("Preparation must be performed in Longeyes.", PySystem.Console.MessageType.Error)
        return False
    if GLOBAL_CACHE.Inventory.GetFreeSlotCount() == 0:
        _log("Inventory is full. Make room before starting.", PySystem.Console.MessageType.Error)
        return False
    return runtime["build"] is not None


def _mark_prepared_after_setup() -> bool:
    if Map.GetMapID() in (BJORA, JAGA):
        return True
    if Map.GetMapID() != LONGEYES:
        return False
    _mark_prepared()
    return True


def _enable_hard_mode() -> BehaviorTree:
    def choose(_node: BehaviorTree.Node) -> BehaviorTree:
        if Map.GetMapID() in (BJORA, JAGA):
            return BT.Succeeder("Hard mode already configured")
        if Map.GetMapID() != LONGEYES:
            return BT.Failer("Hard mode must be configured in Longeyes")
        return BT.SetHardMode(True)
    return BT.Subtree("Enable Hard Mode in Longeyes", choose)


def _leave_longeyes() -> BehaviorTree:
    def choose(_node: BehaviorTree.Node) -> BehaviorTree:
        if Map.GetMapID() in (BJORA, JAGA):
            return BT.Succeeder("Already outside Longeyes")
        if Map.GetMapID() != LONGEYES or not runtime["prepared"]:
            return BT.Failer("Prepare build before leaving Longeyes")
        return BT.MoveAndExitMap((-26951,16445), target_map_id=BJORA)
    return BT.Subtree("Exit Longeyes to Bjora", choose)


def _traverse_bjora() -> BehaviorTree:
    def build(_node: BehaviorTree.Node) -> BehaviorTree:
        if Map.GetMapID() == JAGA:
            return BT.Succeeder("Already in Jaga Moraine")
        if runtime["returning_from_jaga"] and Map.GetMapID() == BJORA:
            return BT.Sequence(
                "Re-enter Jaga Moraine",
                children=[
                    BT.MoveAndExitMap((-20300, 5600), target_map_id=JAGA),
                    _action("Jaga re-entry complete", lambda: runtime.__setitem__("returning_from_jaga", False)),
                ],
            )
        return BT.Sequence(
            "Cross Bjora Marches",
            children=[
                RoutinesBT.Party.SetTitle(TitleID.Norn.value),
                BT.MoveAndExitMap(BJORA_ROUTE, target_map_id=JAGA),
            ],
        )

    return BT.Subtree("Enter Jaga Moraine", build)


def _start_farm() -> None:
    runtime["reset_after_clear"] = False
    runtime["kill_anchor"] = None
    runtime["wall_retries"] = 0
    _finish_run(interrupted=True)
    runtime["run_started"] = Utils.GetBaseTimestamp()
    runtime["kill_timed_out"] = False
    stats["attempts"] += 1
    runtime["farming"] = True
    runtime["waiting"] = False
    runtime["killing"] = False
    runtime["finished"] = False
    runtime["stuck_count"] = 0
    build: SF_Ass_vaettir | SF_Mes_vaettir = runtime["build"]
    _set_balling(False)
    _build_set(build, "SetKillingRoutine", False)
    _build_set(build, "SetRoutineFinished", False)
    _build_set(build, "SetStuckSignal", 0)


def _set_clear_zone_heart_suppression(suppressed: bool) -> None:
    build: SF_Ass_vaettir | SF_Mes_vaettir = runtime["build"]
    # Apo's supplied Vaettir builds do not implement SetHeartOfShadowSuppressed.
    # Heart casts remain governed by the actual build routine and the explicit
    # serialized request in _build_rotation_service.
    # No nonexistent method is called here.
    if suppressed:
        _build_set(build, "SetStuckSignal", 0)


def _set_balling(active: bool) -> None:
    runtime["balling"] = active
    runtime["heart_requested"] = False
    runtime["stuck_count"] = 0
    _set_clear_zone_heart_suppression(not active)
    _build_set(runtime["build"], "SetStuckSignal", 0)


def _ball_route(index: int) -> BehaviorTree:
    return BT.Sequence(
        f"Balling route {index + 1}",
        children=[
            _action("Enable balling recovery", lambda: _set_balling(True)),
            BT.Move(JAGA_ROUTES[index], tolerance=25 if index == 5 else 200, pause_on_combat=False),
        ],
    )


def _wait_for_ball(label: str, timeout_ms: int) -> BehaviorTree:
    def wait() -> Generator[Any, Any, bool]:
        started = Utils.GetBaseTimestamp()
        runtime["waiting"] = True
        try:
            while True:
                if Agent.IsDead(Player.GetAgentID()) or Map.GetMapID() != JAGA:
                    return False
                xy = Player.GetXY()
                foes = cast(list[int], Routines.Agents.GetFilteredEnemyArray(xy[0], xy[1], Range.Earshot.value))
                balled = all(math.dist(Agent.GetXY(foe), xy) <= Range.Adjacent.value for foe in foes)
                timed_out = Utils.GetBaseTimestamp() - started >= timeout_ms
                if balled or timed_out:
                    if timed_out and not balled:
                        _log(f"{label}: aggro ball timeout.", PySystem.Console.MessageType.Warning)
                    break
                yield from Routines.Yield.wait(150)
            # HoS is reserved for actual body blocks (the watchdog requests it).
            return True
        finally:
            runtime["waiting"] = False

    return _generator_step(f"Wait for {label}", wait)


def _press_against_kill_wall() -> BehaviorTree:
    def press() -> Generator[Any, Any, bool]:
        _set_balling(False)
        started = Utils.GetBaseTimestamp()
        near_at: int | None = None
        near_xy: tuple[float, float] | None = None
        last_move: int | None = None
        runtime["waiting"] = True
        try:
            while True:
                now = Utils.GetBaseTimestamp()
                if Agent.IsDead(Player.GetAgentID()) or Map.GetMapID() != JAGA:
                    return False
                xy = Player.GetXY()
                distance = math.dist(xy, KILL_SPOT)
                if distance <= 150:
                    if near_xy is None or math.dist(xy, near_xy) > 15:
                        near_at = now
                        near_xy = xy
                    exact = distance <= 55
                    settled = near_at is not None and now - near_at >= (1500 if exact else 2000)
                    if settled and (exact or now - started >= 6000):
                        runtime["kill_anchor"] = xy
                        _log(
                            f"Kill position settled {distance:.0f} units from the wall target; combat anchor recorded."
                        )
                        return True
                else:
                    near_at = None
                    near_xy = None
                if distance > 55:
                    if last_move is None or now - last_move >= 750:
                        Player.Move(*KILL_SPOT)
                        last_move = now
                if now - started >= 12_000:
                    _log(
                        f"Could not press against the kill wall (distance {distance:.0f}).",
                        PySystem.Console.MessageType.Error,
                    )
                    return False
                yield from Routines.Yield.wait(100)
        finally:
            runtime["waiting"] = False

    return _generator_step("Press against Vaettir kill wall", press)


def _kill_ball() -> BehaviorTree:
    def kill() -> Generator[Any, Any, bool]:
        if runtime["build"] is None:
            _log("Kill prevented: Vaettir build was not initialized.", PySystem.Console.MessageType.Error)
            return False
        _set_balling(False)
        started = Utils.GetBaseTimestamp()
        clear_at: int | None = None
        last_wall_move: int | None = None
        build: SF_Ass_vaettir | SF_Mes_vaettir = runtime["build"]
        anchor = cast(tuple[float, float], runtime.get("kill_anchor") or KILL_SPOT)
        runtime["killing"] = True
        try:
            while True:
                now = Utils.GetBaseTimestamp()
                if Agent.IsDead(Player.GetAgentID()) or Map.GetMapID() != JAGA:
                    return False
                if _jaga_kill_target_met():
                    break
                if now - started >= 120_000:
                    _log(
                        "Kill timeout; recording an incomplete clear, then looting and exiting.",
                        PySystem.Console.MessageType.Warning,
                    )
                    runtime["kill_timed_out"] = True
                    break
                wall_distance = math.dist(Player.GetXY(), anchor)
                if wall_distance > 100:
                    _build_set(build, "SetKillingRoutine", False)
                    clear_at = None
                    if last_wall_move is None or now - last_wall_move >= 750:
                        Player.Move(*anchor)
                        last_wall_move = now
                else:
                    _build_set(build, "SetKillingRoutine", True)
                    last_wall_move = None
                    foes = Routines.Agents.GetFilteredEnemyArray(*anchor, Range.Spellcast.value)
                    if foes:
                        clear_at = None
                    elif clear_at is None:
                        clear_at = now
                    elif now - clear_at >= 1000:
                        break
                yield from Routines.Yield.wait(100)
            runtime["finished"] = True
            _build_set(build, "SetRoutineFinished", True)
            return True
        finally:
            runtime["killing"] = False
            _build_set(build, "SetKillingRoutine", False)

    return _generator_step("Kill Vaettir ball", kill)


def _has_norn_blessing() -> bool:
    agent_id = Player.GetAgentID()
    return any(GLOBAL_CACHE.Effects.HasEffect(agent_id, skill_id) for skill_id in NORN_BLESSING_IDS)


def _hostile_norn_id(preferred_id: int = 0) -> int:
    if preferred_id and not Agent.IsDead(preferred_id) and Agent.GetAllegiance(preferred_id)[0] == 3:
        return preferred_id
    enemies = Routines.Agents.GetFilteredEnemyArray(*NORN_NPC, 350)
    if not enemies:
        return 0
    return min(enemies, key=lambda agent_id: Utils.Distance(Agent.GetXY(agent_id), NORN_NPC))


def _defeat_norn_challenger(npc_id: int) -> Generator[Any, Any, bool]:
    _log("Norn challenger is hostile; defeating it before taking the blessing.")
    wastrels_demise = GLOBAL_CACHE.Skill.GetID("Wastrels_Demise")
    deadline = Utils.GetBaseTimestamp() + 90_000
    next_attack_at = 0
    while Utils.GetBaseTimestamp() < deadline:
        if Agent.IsDead(Player.GetAgentID()):
            _log("Norn challenge failed: player died.", PySystem.Console.MessageType.Error)
            return False
        if _has_norn_blessing():
            return True
        if not Agent.IsDead(npc_id) and Agent.GetAllegiance(npc_id)[0] != 3:
            return True
        friendly_npc = Routines.Agents.GetNearestNPCXY(*NORN_NPC, 250)
        if friendly_npc and not Agent.IsDead(friendly_npc):
            return True
        if Agent.IsDead(npc_id):
            yield from Routines.Yield.wait(250)
            continue

        Player.ChangeTarget(npc_id)
        now = Utils.GetBaseTimestamp()
        if now >= next_attack_at:
            Player.Interact(npc_id, True)
            next_attack_at = now + 2000
        if wastrels_demise and (yield from Routines.Yield.Skills.IsSkillIDUsable(wastrels_demise)):
            yield from Routines.Yield.Skills.CastSkillID(
                wastrels_demise, target_agent_id=npc_id, aftercast_delay=800, log=False
            )
        else:
            yield from Routines.Yield.wait(250)

    _log("Norn challenge timed out before the NPC became friendly.", PySystem.Console.MessageType.Error)
    return False


def _take_norn_blessing() -> Generator[Any, Any, bool]:
    runtime["waiting"] = True
    try:
        npc_id = 0
        for attempt in range(1, 6):
            if _has_norn_blessing():
                return True

            hostile_id = _hostile_norn_id(npc_id)
            if hostile_id:
                if not (yield from _defeat_norn_challenger(hostile_id)):
                    return False
                yield from Routines.Yield.wait(500)
                continue

            interacted = yield from Routines.Yield.Agents.InteractWithAgentXY(*NORN_NPC)
            if not interacted:
                _log(
                    f"Norn blessing: NPC interaction failed (attempt {attempt}/5).",
                    PySystem.Console.MessageType.Warning,
                )
                yield from Routines.Yield.wait(300)
                continue
            npc_id = Player.GetTargetID()

            # Both the challenge and the post-fight blessing use 0x84 here.
            # Native dialog-button enumeration may be empty even while the
            # choice is visible, so dispatch the known ID and verify the result.
            deadline = Utils.GetBaseTimestamp() + 5500
            next_send_at = 0
            sent_count = 0
            while Utils.GetBaseTimestamp() < deadline:
                if _has_norn_blessing():
                    return True
                hostile_id = _hostile_norn_id(npc_id)
                if hostile_id:
                    if not (yield from _defeat_norn_challenger(hostile_id)):
                        return False
                    break
                now = Utils.GetBaseTimestamp()
                if now >= next_send_at:
                    if sent_count == 0:
                        buttons = [
                            button.dialog_id for button in Dialog.get_active_dialog_buttons() if button.dialog_id
                        ]
                        _log(f"Norn dialog attempt {attempt}/5: sending 0x84; visible button IDs: {buttons}.")
                    if npc_id:
                        Player.ChangeTarget(npc_id)
                    Player.SendDialog(0x84)
                    sent_count += 1
                    next_send_at = now + 900
                yield from Routines.Yield.wait(100)
            else:
                _log(
                    f"Norn dialog 0x84 caused no fight or blessing (attempt {attempt}/5).",
                    PySystem.Console.MessageType.Warning,
                )
                continue
            yield from Routines.Yield.wait(500)

        _log("Norn blessing failed after five attempts.", PySystem.Console.MessageType.Error)
        return False
    finally:
        runtime["waiting"] = False


def _loot_jaga() -> Generator[Any, Any, bool]:
    loot = LootFilters()
    previous_gold_coins = loot.live.loot_gold_coins
    loot.set_rarity("gold_coins", True)
    loot_tree: BehaviorTree | None = None
    try:
        loot_tree = BT.LootItems(distance=Range.Spirit.value, timeout_ms=60000)
        while True:
            state = loot_tree.tick()
            if state != BehaviorTree.NodeState.RUNNING:
                break
            yield from Routines.Yield.wait(100)
        if state == BehaviorTree.NodeState.FAILURE:
            return False
        remaining = loot.GetLootArray(Range.Spirit.value)
        if remaining:
            _log(
                f"Jaga loot pass ended with {len(remaining)} wanted drops in range.",
                PySystem.Console.MessageType.Warning,
            )
        return True
    finally:
        try:
            if loot_tree is not None:
                loot_tree.reset()
        finally:
            loot.set_rarity("gold_coins", previous_gold_coins)


def _prepare_jaga() -> BehaviorTree:
    return BT.Sequence(
        "Prepare Jaga clear",
        children=[BT.WaitForMapLoad(JAGA), _action("Start farm", _start_farm)],
    )


def _leave_jaga() -> BehaviorTree:
    def leave() -> Generator[Any, Any, bool]:
        _set_balling(False)
        runtime["farming"] = False
        move = BT.MoveAndExitMap((17295, -20788), target_map_id=BJORA)
        runtime["exiting_jaga"] = True
        try:
            while True:
                move.blackboard = action.blackboard
                state = move.tick()
                if state != BehaviorTree.NodeState.RUNNING:
                    if state == BehaviorTree.NodeState.FAILURE:
                        return False
                    runtime["returning_from_jaga"] = True
                    return True
                yield
        finally:
            try:
                move.reset()
            finally:
                runtime["exiting_jaga"] = False
                _set_balling(False)

    action = _GeneratorAction("Leave Jaga with body block recovery", leave)
    return BehaviorTree(action)


def _open_tot_bags_in_bjora() -> Generator[Any, Any, bool]:
    if Map.GetMapID() != BJORA or not runtime["returning_from_jaga"]:
        return True
    count = GLOBAL_CACHE.Inventory.GetModelCount(TOT_BAG_MODEL_ID)
    target = count
    if not target:
        _log("Bjora reset: no Trick-or-Treat Bags in inventory.")
        return True
    runtime["opening_tot_bags"] = True
    runtime["tot_progress"] = f"0/{target}"
    opened = 0
    _log(f"Bjora reset: opening {target} Trick-or-Treat Bags from {count} in inventory.")
    try:
        while opened < target:
            if Map.GetMapID() != BJORA or Agent.IsDead(Player.GetAgentID()):
                return True
            if GLOBAL_CACHE.Inventory.GetFreeSlotCount() <= 0:
                _log(
                    "Trick-or-Treat opening paused: inventory is full; remaining bags are kept.",
                    PySystem.Console.MessageType.Warning,
                )
                return True
            item_id = GLOBAL_CACHE.Inventory.GetFirstModelID(TOT_BAG_MODEL_ID)
            before = GLOBAL_CACHE.Inventory.GetModelCount(TOT_BAG_MODEL_ID)
            if not item_id or before <= 0:
                return True
            GLOBAL_CACHE.Inventory.UseItem(item_id)
            deadline = Utils.GetBaseTimestamp() + 3000
            while True:
                yield from Routines.Yield.wait(100)
                if Map.GetMapID() != BJORA or Agent.IsDead(Player.GetAgentID()):
                    return True
                after = GLOBAL_CACHE.Inventory.GetModelCount(TOT_BAG_MODEL_ID)
                if after < before:
                    consumed = before - after
                    prior_batches = opened // TOT_BATCH_SIZE
                    opened += consumed
                    stats["tot_bags_opened"] += consumed
                    stats["tot_batches_opened"] += opened // TOT_BATCH_SIZE - prior_batches
                    runtime["tot_progress"] = f"{opened}/{target}"
                    break
                if Utils.GetBaseTimestamp() >= deadline:
                    _log(
                        "Trick-or-Treat Bag use was not confirmed; ending this opening pass without resending.",
                        PySystem.Console.MessageType.Warning,
                    )
                    return True
            yield from Routines.Yield.wait(150)
        return True
    finally:
        runtime["opening_tot_bags"] = False
        _log(f"Bjora reset: {opened}/{target} Trick-or-Treat Bags opened this pass.")


def _request_heart(reason: str) -> bool:
    """Request a single serialized HoS attempt, respecting a shared cooldown."""
    now = Utils.GetBaseTimestamp()
    if (
        runtime["build"] is None
        or runtime["killing"]
        or not (runtime["balling"] or runtime["exiting_jaga"])
        or runtime["heart_requested"]
        or runtime["heart_casting"]
        or now < runtime["heart_next_attempt_at"]
        or Map.GetMapID() != JAGA
        or Agent.IsDead(Player.GetAgentID())
    ):
        return False
    runtime["heart_requested"] = True
    _log(reason)
    return True


def _build_rotation_service() -> BehaviorTree:
    def rotate() -> Generator[Any, Any, None]:
        while True:
            build: BuildMgr | None = runtime["build"]
            if build is None or not runtime["prepared"] or not Map.IsExplorable() or Agent.IsDead(Player.GetAgentID()):
                yield
                continue
            map_id = Map.GetMapID()
            restoring = bool(runtime["restore_revival_skills"])
            recovery_phase = "balling" if runtime["balling"] else "exiting_jaga"
            recovery = bool(
                runtime.get(recovery_phase, False) and runtime["heart_requested"]
                and not runtime["killing"]
            )
            recovery_started = Utils.GetBaseTimestamp()
            if restoring:
                vaettir_build = cast(SF_Ass_vaettir | SF_Mes_vaettir, build)
                # Original YAVB maintains Shadow Form through ProcessSkillCasting.
                # No DefensiveActions extension is required.
                generator = build.ProcessSkillCasting()
            elif recovery:
                # Exit recovery uses this same serialized caster. Keep automatic
                # Heart casts suppressed outside each explicit exit request.
                _set_clear_zone_heart_suppression(False)
                runtime["heart_requested"] = False
                runtime["heart_casting"] = True
                runtime["heart_next_attempt_at"] = Utils.GetBaseTimestamp() + HEART_RETRY_COOLDOWN_MS
                # The build's automatic HoS path also checks stuck_signal;
                # use only the explicit serialized CastHeartOfShadow path here.
                _build_set(build, "SetStuckSignal", 0)
                stats["heart_requests"] += 1
                _log(f"Heart of Shadow attempt: {recovery_phase}, position {Player.GetXY()}.")
                vaettir_build = cast(SF_Ass_vaettir | SF_Mes_vaettir, build)
                heart_cast = getattr(vaettir_build, "CastHeartOfShadow", None)
                if not callable(heart_cast):
                    runtime["stop_reason"] = "Vaettir build lacks CastHeartOfShadow; update CoreLib build."
                    yield
                    continue
                generator = cast(Generator[Any, Any, Any], heart_cast())
            else:
                generator = build.ProcessSkillCasting()
            try:
                while (
                    runtime["build"] is build
                    and Map.GetMapID() == map_id
                    and Map.IsExplorable()
                    and not Agent.IsDead(Player.GetAgentID())
                ):
                    if restoring and not runtime["restore_revival_skills"]:
                        break
                    if recovery and not runtime.get(recovery_phase, False):
                        break
                    if recovery and Utils.GetBaseTimestamp() - recovery_started >= HEART_ATTEMPT_TIMEOUT_MS:
                        _log(
                            "Heart of Shadow attempt exceeded eight seconds; releasing the caster for another attempt.",
                            PySystem.Console.MessageType.Warning,
                        )
                        break
                    if (
                        not recovery
                        and not restoring
                        and (runtime["balling"] or runtime.get("exiting_jaga", False))
                        and runtime["heart_requested"]
                        and not runtime["killing"]
                    ):
                        break
                    try:
                        next(generator)
                    except StopIteration:
                        break
                    yield
            finally:
                try:
                    generator.close()
                finally:
                    runtime["heart_casting"] = False
                    if recovery and runtime["build"] is build:
                        _set_clear_zone_heart_suppression(not runtime["balling"])
            yield

    return _generator_step("VAETTIR DRIFT build rotation", rotate)


def _norn_henchmen_service() -> BehaviorTree:
    state = {"next_check_at": 0, "previous_count": 0}

    def tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if not Party.IsPartyLoaded() or not Party.IsPartyLeader():
            return BehaviorTree.NodeState.RUNNING
        now = Utils.GetBaseTimestamp()
        if now < state["next_check_at"]:
            return BehaviorTree.NodeState.RUNNING
        state["next_check_at"] = now + 2000
        if not _norn_rank_two_reached():
            return BehaviorTree.NodeState.RUNNING
        henchmen = Party.GetHenchmen()
        if not henchmen:
            if state["previous_count"]:
                _log("Norn rank 2 reached; all Longeyes henchmen have left the party.")
                state["previous_count"] = 0
            return BehaviorTree.NodeState.RUNNING
        state["previous_count"] = len(henchmen)
        Party.Henchmen.KickHenchman(henchmen[0].agent_id)
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name="Remove Norn henchmen at rank 2", action_fn=tick))


def _exit_stuck_service() -> BehaviorTree:
    state: dict[str, Any] = {"last_xy": None, "still_since": 0, "request_at": 0}

    def tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if (
            not runtime.get("exiting_jaga", False)
            or Map.GetMapID() != JAGA
            or not Map.IsExplorable()
            or Agent.IsDead(Player.GetAgentID())
        ):
            state.update(last_xy=None, still_since=0, request_at=0)
            if runtime.get("exiting_jaga", False):
                runtime["heart_requested"] = False
            return BehaviorTree.NodeState.RUNNING
        now = Utils.GetBaseTimestamp()
        xy = Player.GetXY()
        previous_xy = cast(tuple[float, float] | None, state["last_xy"])
        if previous_xy is None or math.dist(xy, previous_xy) >= 35:
            state.update(last_xy=xy, still_since=now)
            runtime["heart_requested"] = False
        elif (
            now - state["still_since"] >= 5000
            and now >= state["request_at"]
            and not runtime["heart_requested"]
            and not runtime["heart_casting"]
            and Routines.Checks.Agents.InDanger(Range.Adjacent)
        ):
            if _request_heart("Exit body block after loot: requesting Heart of Shadow."):
                state["request_at"] = now + HEART_RETRY_COOLDOWN_MS
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name="Post-loot exit body block watchdog", action_fn=tick))


def _stuck_service() -> BehaviorTree:
    state: dict[str, Any] = {"sample_at": 0, "last_xy": None, "stuck_warned": False}

    def tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if Map.GetMapID() != JAGA or not Map.IsExplorable() or runtime["build"] is None:
            runtime["farming"] = False
            state.update(sample_at=0, last_xy=None, stuck_warned=False)
            return BehaviorTree.NodeState.RUNNING
        now = Utils.GetBaseTimestamp()
        if (
            not runtime["farming"]
            or not runtime["balling"]
            or runtime["waiting"]
            or runtime["killing"]
            or runtime["finished"]
            or Agent.IsDead(Player.GetAgentID())
        ):
            runtime["stuck_count"] = 0
            _build_set(runtime["build"], "SetStuckSignal", 0)
            state.update(sample_at=now, last_xy=Player.GetXY(), stuck_warned=False)
            return BehaviorTree.NodeState.RUNNING
        if state["last_xy"] is None:
            state.update(sample_at=now, last_xy=Player.GetXY())
        if now - state["sample_at"] >= 3000:
            xy = Player.GetXY()
            previous_xy: tuple[float, float] | None = state["last_xy"]
            if previous_xy is not None and math.dist(xy, previous_xy) < 35:
                runtime["stuck_count"] += 1
                # Do not signal the build's own HoS logic. Explicit casting is
                # owned by the single rotation service to avoid double casts.
                Player.SendChatCommand("stuck")
                stats["unstuck"] += 1
                if Routines.Checks.Agents.InDanger(Range.Adjacent) and not runtime["heart_casting"]:
                    _request_heart("Balling body block: requesting Heart of Shadow through the build rotation.")
            else:
                runtime["stuck_count"] = 0
                _build_set(runtime["build"], "SetStuckSignal", 0)
                state["stuck_warned"] = False
            state.update(sample_at=now, last_xy=xy)
        if runtime["stuck_count"] >= 10 and not state["stuck_warned"]:
            step = str(runtime.get("current_step") or "Clear 05 - Aggro Inner Packs")
            _queue_step_recovery(step, "No movement for 30 seconds despite /stuck and Heart of Shadow.")
            state["stuck_warned"] = True
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name="Jaga stuck watchdog", action_fn=tick))


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """One named Planner step per farm operation, including YAVB preparation."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        (
            "Initialize Bot",
            lambda: BT.Sequence(
                "Configure VAETTIR DRIFT",
                children=[
                    ensure_botting_tree().Config.PacifistTree(
                        account_isolation=True, multi_account=False,
                        auto_loot=False, pause_on_danger=False,
                    ),
                    _action("Assign original YAVB build", _assign_build),
                ],
            ),
        ),
        ("Verify Account Isolation", lambda: _generator_step("Verify local isolation", _verify_isolation)),
        ("Resume Current Instance", lambda: _action("Resume Bjora/Jaga if already present", _resume_field_preparation)),
        ("Travel to Longeyes Ledge", _travel_to_start),
        ("Prepare 01 - Validate", lambda: _action("Validate build preparation", _validate_preparation)),
        ("Prepare 02 - Equip YAVB Skillbar", _prepare_skillbar),
        ("Prepare 03 - Refresh Build", lambda: _action("Refresh loaded skills", _refresh_prepared_build)),
        ("Prepare 04 - Recruit Norn Henchmen", lambda: _generator_step("Recruit henchmen", _prepare_henchmen)),
        ("Prepare 05 - Set Hard Mode", _enable_hard_mode),
        ("Prepare 06 - Confirm Setup", lambda: _action("Confirm YAVB build setup", _mark_prepared_after_setup)),
        ("Prepare 07 - Exit Longeyes", _leave_longeyes),
        ("Restore Skills After Revival", lambda: _generator_step("Restore revival defenses", _restore_skills_after_revival)),
        ("Traverse Bjora Marches", _traverse_bjora),
        ("Clear 01 - Prepare Jaga", _prepare_jaga),
        (
            "Clear 02 - Approach Norn",
            lambda: BT.Sequence("Approach Norn", children=[
                _action("Release companions", _release_companions_for_challenge),
                BT.Move((13372.44, -20758.50), pause_on_combat=False),
            ]),
        ),
        # The original Drift source deliberately disables these steps.
        # Preserve this setting in the refactor; do not silently re-enable it.
        # ("Clear 03 - Norn Blessing", lambda: _generator_step("Take Norn blessing", _take_norn_blessing)),
        # ("Clear 04 - Flag Companions", lambda: _action("Flag companions", _flag_companions_at_portal)),
    ]
    labels = ("Inner Packs", "Left Packs", "Log Side Packs", "Big Pack", "Right Packs")
    timeouts = (7500, 15000, 7500, 15000, 15000)
    for index, (label, timeout) in enumerate(zip(labels, timeouts)):
        steps.extend([
            (f"Clear {5 + index * 2:02d} - Aggro {label}", lambda index=index: _ball_route(index)),
            (f"Clear {6 + index * 2:02d} - Ball {label}", lambda label=label, timeout=timeout: _wait_for_ball(label, timeout)),
        ])
    steps.extend([
        ("Clear 15 - Final Approach", lambda: _ball_route(5)),
        ("Clear 16 - Position Against Wall", _press_against_kill_wall),
        ("Clear 17 - Kill Vaettirs", _kill_ball),
        ("Clear 18 - Loot Drops", lambda: _generator_step("Loot Jaga drops", _loot_jaga)),
        ("Clear 19 - Identify and Salvage", lambda: _generator_step("Process field loot", _inventory_pass)),
        ("Clear 20 - Record Statistics", lambda: _action("Record Jaga run", _finish_run)),
        ("Exit Jaga Moraine", _leave_jaga),
        ("Open Trick-or-Treat Bags in Bjora", lambda: _generator_step("Open available ToT bags", _open_tot_bags_in_bjora)),
    ])
    return [(name, lambda name=name, factory=factory: _checked_step(name, factory)) for name, factory in steps]


def ensure_botting_tree() -> BottingTree:
    global botting_tree
    if botting_tree is None:
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name="VaettirDriftSequence",
            repeat=True,
            reset=False,
            pause_on_combat=False,
            multi_account=False,
            isolation_enabled=True,
            account_config=BottingTreeAccountConfig(isolation_enabled=True, sync_party_isolation=False),
            auto_loot=False,
            configure_fn=lambda tree: tree.Config.ConfigureUpkeep(
                looting_enabled=False,
                auto_inventory_handler_enabled=False,
                consumable_upkeeps=[],
            ),
        )
        botting_tree.SetHeroAIStateLogging(False)
        botting_tree.AddServiceTree("Vaettir build rotation", _build_rotation_service)
        botting_tree.AddServiceTree("Norn rank 2 henchmen removal", _norn_henchmen_service)
        botting_tree.AddServiceTree("Jaga stuck watchdog", _stuck_service)
        botting_tree.AddServiceTree("Jaga exit body block recovery", _exit_stuck_service)
    return botting_tree


def tooltip() -> None:
    PyImGui.begin_tooltip()
    PyImGui.text("VAETTIR DRIFT - Jaga Moraine Vaettir farm")
    PyImGui.text("Builds: Assassin/Mesmer or Mesmer/Assassin Shadow Form.")
    PyImGui.text("Automatic travel to Longeyes; verified single-account isolation.")
    PyImGui.text("Hard mode; detailed aggro, balling, kill and loot steps.")
    PyImGui.text("Original YAVB build/skillbar preparation in named BT steps.")
    PyImGui.text("No merchant or consumable restocking; supplies are manual.")
    PyImGui.end_tooltip()


def _draw_statistics() -> None:
    def duration(milliseconds: int | float) -> str:
        seconds = int(milliseconds / 1000)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    PyImGui.text("VAETTIR DRIFT - Session statistics")
    PyImGui.separator()
    isolation = "VERIFIED" if runtime["isolation_verified"] else "PENDING / INACTIVE"
    PyImGui.text(f"Account isolation: {isolation} | Group: {runtime['isolation_group']}")
    PyImGui.text(
        f"Balling recovery: {'ON' if runtime['balling'] else 'OFF'} | Heart requests: {stats['heart_requests']}"
    )
    PyImGui.text(f"Post-loot exit recovery: {'ON' if runtime['exiting_jaga'] else 'OFF'} (5 seconds without progress)")
    PyImGui.text(f"Attempts: {stats['attempts']} | Completed: {stats['completed']}")
    PyImGui.text(f"Incomplete clears: {stats['incomplete']} | Interrupted: {stats['interrupted']}")
    PyImGui.text(f"Deaths: {stats['deaths']} | Automatic restarts: {stats['restarts_after_death']}")
    PyImGui.text(f"Wall approach retries: {stats['route_retries']} | Clear rebuilds: {stats['route_rebuilds']}")
    PyImGui.text(f"Automatic step retries: {stats['step_retries']}")
    PyImGui.text(
        f"Jaga enemies killed: {runtime['jaga_kills']}/{JAGA_KILL_TARGET} | Threshold resets: {stats['threshold_resets']}"
    )
    PyImGui.text(
        f"Trick-or-Treat Bags opened: {stats['tot_bags_opened']} | Full batches: {stats['tot_batches_opened']}"
    )
    if runtime["opening_tot_bags"]:
        PyImGui.text(f"Opening bags in Bjora: {runtime['tot_progress']}")
    if runtime["route_recovery_reason"]:
        PyImGui.text_wrapped(f"Recovery pending: {runtime['route_recovery_reason']}")
    if runtime["recovering"]:
        penalty = runtime["death_penalty"]
        PyImGui.text_wrapped(
            f"Recovery: death penalty {penalty if penalty is not None else '?'}%. Outpost return only at 60%."
        )
    elif runtime["restore_revival_skills"]:
        PyImGui.text_wrapped("Revival: restoring Shadow Form and Shroud of Distress before resuming the clear route.")
    PyImGui.text(f"Last run: {duration(stats['last_ms'])} | Best clear: {duration(stats['best_ms'])}")
    average = stats["total_ms"] / stats["completed"] if stats["completed"] else 0
    PyImGui.text(f"Average clear: {duration(average)} | Unstuck requests: {stats['unstuck']}")
    started = runtime["run_started"]
    if started is not None:
        PyImGui.text(f"Current run: {duration(Utils.GetBaseTimestamp() - started)}")
    PyImGui.text_wrapped(
        "Times cover the Norn blessing, aggro, clear and loot. Pauses are included. Counters reset when the widget reloads."
    )
    if runtime["last_stop"]:
        PyImGui.separator()
        PyImGui.text_wrapped(f"Last stop: {runtime['last_stop']}")
    PyImGui.separator()
    PyImGui.text_wrapped(
        "Manual supplies: buy and activate consumables before starting. Empty inventory space is checked before each run."
    )


def on_disable() -> None:
    if botting_tree is not None:
        if botting_tree.IsStarted():
            botting_tree.Stop()
        else:
            botting_tree.Reset()
    _finish_run(interrupted=True)
    _reset_farm_state()


def main() -> None:
    global ini_key
    if not ini_key:
        ini_key = Settings(f"{INI_PATH}/{INI_FILENAME}", "account").name
        if not ini_key:
            return
    tree = ensure_botting_tree()
    if tree.IsStarted() and not tree.IsPaused() and Map.IsMapReady() and Party.IsPartyLoaded():
        try:
            if _tick_death_recovery(tree):
                pass
            elif _tick_clear_completion(tree):
                pass
            elif runtime["prepared"] and Map.GetMapID() not in (LONGEYES, BJORA, JAGA):
                runtime["stop_reason"] = "Unexpected map during the farm. Restart to travel back to Longeyes Ledge."
            else:
                if _isolation_ready_for_tick():
                    tree.tick()
                    _tick_route_recovery(tree)
        except Exception as exc:
            runtime["stop_reason"] = f"Runtime error ({type(exc).__name__}): {exc}"
    if runtime["stop_reason"]:
        reason = str(runtime["stop_reason"])
        runtime["last_stop"] = reason
        _log(reason, PySystem.Console.MessageType.Error)
        tree.Stop()
    if not tree.IsStarted():
        _finish_run(interrupted=True)
        _reset_farm_state()
    tree.UI.draw_window(
        icon_path=BOT_TEXTURE,
        iconwidth=96,
        main_child_dimensions=(550, 380),
        extra_tabs=[("Statistics", _draw_statistics)],
    )


if __name__ == "__main__":
    main()
