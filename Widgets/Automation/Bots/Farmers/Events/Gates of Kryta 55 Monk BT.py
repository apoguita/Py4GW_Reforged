from __future__ import annotations

import os
import time
from typing import Callable, Sequence

import PySystem

from Py4GWCoreLib import (
    Agent,
    ConsoleLog,
    Map,
    Player,
    Routines,
    Utils,
)
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.enums import Range
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Sources.ApoSource.ApoBottingLib import wrappers as BT

MODULE_NAME = "Gates of Kryta 55 Monk BT"
# Shield of Judgment (skill 262) - the build's identity skill, and the one cast
# that defines the fight. Drawn from the shared Skill_Icons library by ID, so it
# tracks the skill rather than being a hand-picked lookalike.
# NOTE: this is NOT a Vanquish bot. It walks a route with VanquishNode, but that
# is a movement mechanism; the theme is the Monk, not the vanquish.
MODULE_ICON = "Assets\\Textures\\Skill_Icons\\[262] - Shield of Judgment.jpg"
INI_PATH = "Widgets/Automation/Bots/Gates of Kryta 55 Monk"
INI_FILENAME = "Gates_of_Kryta_55_Monk.ini"

BOT_TEXTURE = os.path.join(PySystem.Console.get_projects_path(), MODULE_ICON)

initialized = False
ini_key = ""
botting_tree: BottingTree | None = None


# The route is walked in two parts, and the split is deliberate.
#
# PART 1 - plain Moves. These are transit waypoints: positions to pass through
# on the way to the ball spot, not places to fight. The first also sits by a
# group the route deliberately bypasses, and a VanquishNode step would stop to
# clear it (every step gets a clear_area_radius).
#
# PART 2 - VanquishNode, one step: the ball spot, the proximity trigger.
#
# Why the split rather than just a tighter tolerance: VanquishNode builds a
# MoveAndKill per step and applies move_tolerance to ALL of them. The ball spot
# needs a wide hold radius (2500) to stand in a choke, and that same value was
# being applied to the transit points too - so the monk declared itself arrived
# up to 2500 units short and turned early, never actually reaching the
# coordinates. A per-step tolerance cannot express "wide here, exact there", so
# the two needs are separated into two different mechanisms instead.
#
# If a waypoint is added: transit or fight? Transit goes in PART 1 as a Move,
# fight goes in PART 2 as a VanquishNode step.
PART_1_MOVES: list[tuple[float, float]] = [
    (3360.00, 16512.00),
    (4983.42, 16128.00),
    (5840.02, 18675.45),
]

# The ball spot: the proximity trigger that spawns the large extra group once the
# monk is close. Reached, cleared, and held - see PROXIMITY_SPAWN_DWELL_MS.
PART_2_VANQUISH: list[tuple[float, float]] = [
    (8273.50, 14369.13),
]

# Arrival radius for the transit moves. Tight on purpose: these are points to
# pass through, so the monk must actually reach them rather than turning short.
TRANSIT_TOLERANCE = 200.0

# Ball spot arrival radius, and how far the monk may stray once there. 150 (the
# library default) is "stand on this exact pixel", which fights the pack in a choke.
BALL_SPOT_TOLERANCE = Range.Spirit.value  # 2500
BALL_SPOT_HOLD_RADIUS = Range.Spirit.value  # 2500


# The final waypoint is a proximity trigger: walking close spawns a large extra
# group. The bot must stand there long enough for that to happen, otherwise the
# clear check sees an empty area and resigns before the group ever appears.
#
# These two are the only tunables for that behaviour. DWELL is the window in
# which the group may appear; DEBOUNCE is how long the area must then stay empty
# before the run is considered done.
#
# Keep DWELL SHORT. The monk is a lone 55 in NORMAL mode, and the prox group is
# the biggest fight in the run - standing at the choke is exposure, and every
# second of dwell is a second of it. The value only has to cover the trigger
# FIRING, because once the group is actually visible the dwell is satisfied and
# the clear check takes over immediately (see _wait_for_proximity_spawn). A fast
# spawn therefore costs the debounce, not the full window.
#
# Cut from 20s -> 8s -> 3s. If groups are still being missed, raise it in small
# steps - an early resign costs the group, but a dead monk costs the run.
PROXIMITY_SPAWN_DWELL_MS = 3_000
PROXIMITY_SPAWN_CLEAR_DEBOUNCE_MS = 4_000

GATES_OF_KRYTA_MAP_ID = 14
AREA_CLEAR_RADIUS = Range.Earshot.value
# How long a clear may stall before we complain. This is NOT a give-up timer:
# timing out re-bases the clock and keeps waiting, because resigning with a
# live pack throws the whole run away. A wipe is the planner's job.
RUN_COMPLETE_TIMEOUT_MS = 90_000
TRAVEL_TIMEOUT_MS = 30_000
RESIGN_TIMEOUT_MS = 30_000
# How long to wait for combat to lapse before resigning.
#
# /resign is silently dropped in combat, so this has to outlast the last hit.
# The guard in _resign_run is what makes the value low-risk: it refuses to hand
# off to the resign while any foe is alive, so this only bounds the tail after a
# fight is genuinely over - it is not the thing keeping the monk safe. That is
# why it can be short: the guard re-checks every tick regardless.
#
# Halved from 15s. The long version was dead time on every run, paid after the
# loot was already done. Raise it if /resign ever gets dropped while the map
# reads as out of combat.
OUT_OF_COMBAT_TIMEOUT_MS = 7_500
POST_OUTPOST_SETTLE_MS = 5000
# Matches the mission record (gates_of_kryta.json: enter_challenge delay_ms).
ENTER_CHALLENGE_DELAY_MS = 5000
# Settle time after the map reports ready, before the first autopath request.
#
# The log showed the walk failing with autopath_failed and current_pos still on
# the outpost coords ~5s after EnterChallenge. WaitUntilOnExplorable had already
# returned, so the instance was nominally loaded - but IsExplorable() goes true
# during the load window, and issuing a path there hits a map with no pathing
# data yet. The planner then restarts the same step and spins.
#
# This is a settle, not a retry: the map must be ready AND stay ready for this
# long before the first move is issued. Keep it small - it only has to cover the
# tail of the load, not a slow map.
MAP_SETTLE_MS = 2000

_warned_inputs: set[str] = set()


# --- Enchant upkeep engine ----------------------------------------------------
def _warn_once(key: str, message: str) -> None:
    if key in _warned_inputs:
        return
    _warned_inputs.add(key)
    ConsoleLog(MODULE_NAME, message, PySystem.Console.MessageType.Warning)




def _foe_count(radius: float) -> int:
    try:
        px, py = Player.GetXY()
        return len(Routines.Agents.GetFilteredEnemyArray(px, py, radius))
    except Exception:
        return 0






def _enter_farm_map() -> BehaviorTree:
    state: dict[str, BehaviorTree | None] = {"tree": None}

    def _t(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if Map.IsExplorable():
            # Already on a run: the outpost and the explorable instance share
            # map id 14, so IsExplorable() is the only reliable discriminator.
            return BehaviorTree.NodeState.SUCCESS
        if state["tree"] is None:
            children: list[BehaviorTree | BehaviorTree.Node] = []
            if not Map.IsMapIDMatch(Map.GetMapID(), GATES_OF_KRYTA_MAP_ID):
                children.append(BT.Travel(target_map_id=GATES_OF_KRYTA_MAP_ID, log=True))
                children.append(
                    BT.WaitForMapLoad(GATES_OF_KRYTA_MAP_ID, timeout_ms=TRAVEL_TIMEOUT_MS)
                )
            # Difficulty is deliberately NOT set here.
            #
            # This used to call BT.SetHardMode(True), which put the monk into
            # HARD MODE on every run while the rest of this bot is tuned for
            # NORMAL mode - the prox-spawn dwell, the shield rotation and the
            # sustain budget are all NM assumptions. That mismatch is why the
            # monk kept dying at the ball spot: an HM pack on an NM rotation.
            #
            # If hard mode is ever wanted back, the survivability work has to be
            # re-tuned for it first. Do not just flip this back on.
            children.append(
                BT.EnterChallenge(
                    target_map_id=GATES_OF_KRYTA_MAP_ID,
                    delay_ms=ENTER_CHALLENGE_DELAY_MS,
                )
            )
            # EnterChallenge's own load-wait passes on the outpost instance too
            # (same map id); insist on a real explorable instance instead.
            children.append(BT.WaitUntilOnExplorable(timeout_ms=TRAVEL_TIMEOUT_MS))
            state["tree"] = BT.Sequence("Enter Gates Of Kryta", children=children)
            state["tree"].root.blackboard = node.blackboard
        st = state["tree"].tick()
        if st != BehaviorTree.NodeState.RUNNING:
            state["tree"] = None
        return st

    return BehaviorTree(BehaviorTree.ActionNode(name="Enter Gates Of Kryta", action_fn=_t))




def _restart_if_wiped() -> BehaviorTree:
    """Bounce back to Initialize Bot if a wipe dropped us at the outpost.

    Dying in the mission boots us to the outpost, which shares map id 14 with
    the explorable instance - so the planner cannot tell "still in the mission"
    from "back at the outpost" by map id, and just retries the failed step
    forever. Map.IsOutpost() and Map.IsExplorable() both read GetInstanceType(),
    so they are mutually exclusive and IsOutpost() is the reliable discriminator.

    Returns SUCCESS either way so the sequence continues to the VanquishNode; the
    restart request is what actually moves the planner, and this step is
    abandoned on the next tick.
    """
    def _t(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if not Routines.Checks.Map.MapValid() or not Map.IsOutpost():
            return BehaviorTree.NodeState.SUCCESS
        _warn_once("wipe", "Wiped - booted to the outpost, starting a fresh run.")
        node.blackboard["restart_step_name_request"] = "Initialize Bot"
        node.blackboard["PLANNER_STATUS"] = "PLANNER: Wiped, restarting run"
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name="Restart If Wiped", action_fn=_t))


def _walk_to_mobs() -> BehaviorTree:
    """Walk the route, clearing as we go.

    Must be a returned tree, not a hand-ticked ActionNode: the planner drives
    step trees on the root blackboard, and DrawMovePath reads move_path_points
    from there, so a manually ticked subtree draws nothing and errors nowhere.
    Asterius Scythe BT is the reference.

    The settle covers autopath_failed right after EnterChallenge - IsExplorable
    goes true before the map can actually path.
    """
    return BT.Sequence(
        "Walk To Mobs",
        children=[
            # A wipe mid-clear drops us at the outpost, which shares the mission
            # map id - so without this the planner retries this step forever
            # instead of going back through Enter.
            _restart_if_wiped(),
            # No BT.WaitUntilMapReady wrapper; Enter already uses WaitForMapLoad.
            BT.WaitForMapLoad(GATES_OF_KRYTA_MAP_ID, timeout_ms=TRAVEL_TIMEOUT_MS),
            BT.Wait(MAP_SETTLE_MS),
            # PART 1: transit only - no clear radius, no kill, and a tight
            # tolerance so the monk actually reaches each point. Passing through
            # the bypassed group must not pull a fight.
            BT.Move(
                pos=[point for point in PART_1_MOVES],
                tolerance=TRANSIT_TOLERANCE,
                pause_on_combat=False,
            ),
            # PART 2: the ball spot. Wide hold tolerance on purpose - the monk
            # stands here in a choke and must trigger the proximity spawn.
            BT.VanquishNode(
                steps=[tuple(point) for point in PART_2_VANQUISH],
                clear_area_radius=Range.Spirit.value,
                pause_on_combat=False,
                move_tolerance=BALL_SPOT_TOLERANCE,
            ),
        ],
    )


def _wait_for_proximity_spawn() -> BehaviorTree:
    """Dwell at the final waypoint until the proximity spawn is cleared.

    The last path point is a proximity trigger: stepping close spawns a large
    extra group. That is the whole point of standing there, and it inverts the
    usual logic - the spawn is *caused* by arriving, so a clear-check that
    accepts "zero foes" the instant VanquishNode returns will resign before the
    group ever appears and throw the whole event group away.

    So this waits out a MINIMUM dwell first, regardless of what is on screen,
    giving the trigger time to fire, and only then hands off once the area is
    genuinely empty. The dwell is not a guess about the spawn delay: it is the
    window in which a new group can appear, and bailing early costs the run.

    Only AFTER the dwell elapses does an empty area count as done. Hostiles seen
    during the dwell reset the clock, so a group that lands late still has to be
    cleared before the resign is allowed.
    """
    state: dict[str, float] = {"t0": 0.0, "cleared_at": 0.0, "spawn_seen": 0.0}

    def _t(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        del node
        pid = Player.GetAgentID()
        if not pid or Agent.IsDead(pid):
            state["t0"] = 0.0
            state["cleared_at"] = 0.0
            state["spawn_seen"] = 0.0
            return BehaviorTree.NodeState.FAILURE
        now_ms = time.monotonic() * 1000.0
        if state["t0"] == 0.0:
            state["t0"] = now_ms
        elapsed_ms = now_ms - state["t0"]
        foes = _foe_count(AREA_CLEAR_RADIUS)

        # The trigger has fired. VanquishNode has already cleared the ball spot
        # before this step runs, so anything alive now is the proximity group
        # arriving - which means there is no reason to keep standing through the
        # rest of the dwell. Record it once and fall straight through to the
        # clear check, so a fast spawn does not pay the full dwell.
        if foes > 0:
            if state["spawn_seen"] == 0.0:
                state["spawn_seen"] = now_ms
        elif state["spawn_seen"] != 0.0:
            # Group gone. Re-anchor so the clear must hold before the resign.
            state["t0"] = now_ms
            state["cleared_at"] = 0.0
            state["spawn_seen"] = 0.0
            return BehaviorTree.NodeState.RUNNING

        # Dwell only has to cover the trigger actually firing. Once the group has
        # been seen the dwell is satisfied, so fall through immediately.
        dwell_done = state["spawn_seen"] != 0.0 or elapsed_ms >= PROXIMITY_SPAWN_DWELL_MS
        if not dwell_done:
            return BehaviorTree.NodeState.RUNNING

        if foes > 0:
            return BehaviorTree.NodeState.RUNNING

        # Empty, post-dwell. Debounce so a single empty frame mid-spawn is not
        # read as "done".
        if state["cleared_at"] == 0.0:
            state["cleared_at"] = now_ms
            return BehaviorTree.NodeState.RUNNING
        if now_ms - state["cleared_at"] >= PROXIMITY_SPAWN_CLEAR_DEBOUNCE_MS:
            state["t0"] = 0.0
            state["cleared_at"] = 0.0
            state["spawn_seen"] = 0.0
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name="Wait For Proximity Spawn", action_fn=_t))

def _resign_guard() -> BehaviorTree:
    """Hold here while anything is still attacking us.

    A mid-fight resign throws away the run. This refuses to hand off to the
    /resign while the area still has foes, and keeps the protective kit up in
    the meantime, so a late pull cannot be quit out of. It is a guard, not a
    wait: it has no timeout, because the correct answer to "still fighting" is
    to keep fighting.
    """

    def _t(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _foe_count(AREA_CLEAR_RADIUS) > 0:
            return BehaviorTree.NodeState.RUNNING
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name="Resign Guard", action_fn=_t))


def _resign_run() -> BehaviorTree:
    # Direct chat-command resign (RoutinesBT.Party.Resign) rather than the
    # shared-memory BT.Resign path: this is a solo bot and must not depend on
    # the Messaging widget being active to process the resign command.
    return BT.Sequence(
        "Resign Run",
        children=[
            _resign_guard(),
            # /resign is silently dropped in combat, so wait it out first. The
            # guard above is what makes a timeout here harmless: it cannot hand
            # off to the resign while anything is still attacking us.
            BT.WaitUntilOutOfCombat(timeout_ms=OUT_OF_COMBAT_TIMEOUT_MS),
            RoutinesBT.Party.Resign(log=True),
            BT.WaitUntilOnOutpost(timeout_ms=RESIGN_TIMEOUT_MS),
            BT.Wait(POST_OUTPOST_SETTLE_MS),
        ],
    )


# --- Bot wiring (single-account template shape) --------------------------------
def ensure_botting_tree() -> BottingTree:
    global botting_tree

    if botting_tree is None:
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name="GatesOfKryta55Sequence",
            repeat=True,
            reset=False,
            multi_account=False,
            configure_fn=lambda tree: tree.Config.ConfigureUpkeep(),
        )

    return botting_tree


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()
    return BehaviorTree(
        BehaviorTree.SequenceNode(
            name="Initialize Bot",
            children=[
                bot.Config.Aggressive(multi_account=False, auto_loot=True),
                # HeroAI owns all skill usage. Explicit, since Config.Aggressive
                # already requests hero_ai=True and the old disable came after it.
                BottingTree.EnableHeroAITree(reset_runtime=True),
            ],
        )
    )


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Initialize Bot", InitializeBot),
        ("Enter Gates Of Kryta", _enter_farm_map),
        ("Walk To Mobs", _walk_to_mobs),
        # Dwell at the last waypoint: it is a proximity trigger, so the extra
        # group only spawns once the monk is standing there.
        ("Wait For Proximity Spawn", _wait_for_proximity_spawn),
        ("Resign Run", _resign_run),
    ]


def tooltip() -> None:
    import PyImGui
    from Py4GWCoreLib import Color, ImGui

    title_color = Color(255, 200, 100, 255)
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored(MODULE_NAME, title_color.to_tuple_normalized())
    ImGui.pop_font()
    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()
    PyImGui.text("Solo event-item tank farmer (Gates of Kryta).")
    PyImGui.spacing()
    PyImGui.text_colored("Skills", title_color.to_tuple_normalized())
    PyImGui.bullet_text("HeroAI manages every cast - bring your own bar.")
    PyImGui.bullet_text("This bot does not load a skillbar, so whatever")
    PyImGui.bullet_text("you have equipped is what gets used in the run.")
    PyImGui.spacing()
    PyImGui.text_colored("What this bot handles", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Travels to the Gates of Kryta and farms the route.")
    PyImGui.bullet_text("Waits for aggro, then holds until the area is clear.")
    PyImGui.bullet_text("Loots between fights and resigns when the run ends.")



def main() -> None:
    global initialized, ini_key

    if not initialized:
        if not ini_key:
            ini_key = Settings(f"{INI_PATH}/{INI_FILENAME}", "account").name
            if not ini_key:
                return

        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()
    # Plain draw_window(), matching every other BT bot (see
    # Sources/ApoSource/single_account_botting_tree_template.py). No
    # additional_ui and no SetMovePathDrawingEnabled call.
    #
    # This widget used to add its own DrawMovePathDebugOptions to the main tab
    # via additional_ui, which duplicated the built-in options and fought them:
    # both wrote the same draw_move_path_enabled flag, and the module-level
    # DRAW_MOVE_PATH constant was re-applied every frame from main(), so
    # toggling it in one place was silently reverted by the other. Path drawing
    # is on by default (BottingTree.draw_move_path_enabled = True) and is meant
    # to be driven from the built-in settings, so this bot now neither hardcodes
    # it nor re-asserts it.
    tree.UI.draw_window(icon_path=BOT_TEXTURE)


if __name__ == "__main__":
    main()
