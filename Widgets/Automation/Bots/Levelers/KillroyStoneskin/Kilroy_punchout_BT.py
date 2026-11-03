# ============================================================================
# Kilroy Stonekin's Punch-Out Extravaganza! - Behavior Tree Conversion
# ============================================================================
# BT conversion of the legacy FSM-based Kilroy bot (same folder). The punch-out
# lap is the single named planner step and the planner repeats it, replacing
# the legacy JumpToStepName("[H]Killroy Stoneskin_1") loop. Party-wipe recovery
# restarts the lap step, replacing the legacy OnDeath coroutine's resign-home
# half. The coroutine's OTHER half -- the slot-8 stand-up spam that pops the
# player back up during a knockdown -- is owned by the StandUpService tree
# (see "Stand-up service" below); without it the dwarves finish the knockdown.
#
# Prerequisite: the character must already have the Punch-Out Extravaganza
# quest unlocked and the punch-out skillbar earned. The unlock chain
# (legacy UnlockKillroy / 0x835A01 -> 0x84 -> map 703 -> brass knuckles) is
# deliberately NOT part of this routine: the planner re-runs every step on each
# successful pass, and the planner restarts the *current* named step on
# failure, so a once-only unlock in the step list wedges the loop. Run the
# legacy script once on a new character to unlock, then use this bot to farm.
#
# Loot: an explicit BT.LootItems pass runs after the arena clear. This uses the
# direct pickup path (target + interact, no PickUpLoot shared-memory relay),
# which sidesteps the auto-loot sender wedge observed in Nightfall_leveler_BT_MA.
#
# Locked chests: the arena walk is split into legs with a chest watchdog after
# each leg (ported from Reputation Farmer BT). Chest spawns are random, so
# boundary sampling keeps a passed chest in detection radius; a per-instance
# ledger stops the lap from revisiting an already-opened chest. The locked-chest
# dialog itself is answered by the native `auto_open_locked_chest` listener
# (System Settings) -- this module only owns detection, travel and interaction.
# ============================================================================
from __future__ import annotations

import os
import time
from collections.abc import Callable

import PySkillbar
import PySystem
from Py4GWCoreLib import ActionQueueManager, Agent, AgentArray, Player, Range, Routines
from Py4GWCoreLib.enums_src.Hero_enums import HeroType
from Py4GWCoreLib.enums_src.Model_enums import GadgetModelID
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Sources.ApoSource.ApoBottingLib import wrappers as BT

BOT_NAME = "Killroy Stoneskin"
MODULE_NAME = "Killroy Stonekin's Punch-Out Extravaganza BT"
MODULE_ICON = "Assets\\Textures\\Module_Icons\\Leveler - Killroy Stoneskin.png"
ICON_PATH = os.path.join(
    PySystem.Console.get_projects_path(),
    "Assets",
    "Textures",
    "Module_Icons",
    "Leveler - Killroy Stoneskin.png",
)
MODULE_CATEGORY = "Bots"
MODULE_TAGS = ["automation", "leveling", "eyenorth", "kilroy", "botting", "bt"]
MODULE_DESCRIPTION = (
    "Behavior Tree conversion of the Kilroy Stonekin punch-out farming bot.\n\n"
    "Repeats the Punch-Out Extravaganza quest in Gunnar's Hold for experience "
    "and Stone Summit Emblems.\n\n"
    "• BT-based automation using the BottingTree planner stack\n"
    "• One planner step per lap; the planner repeats until stopped\n"
    "• Party-wipe recovery restarts the current lap\n"
    "• Explicit direct loot pass after each arena clear\n\n"
    "Credits:\n"
    "• Legacy FSM script by the Py4GW Reforged contributors\n"
    "• BT conversion for the widget system by Kendor"
)
ROUTINE_NAME = "KilroyPunchOutSequence"

GUNNARS_HOLD = 644
# Brass knuckles: required to brawl in the punch-out. Without them equipped the
# arena fight cannot be won, so the lap re-asserts them every pass.
BRASS_KNUCKLES_MODEL_ID = 24897

# Arena entry gadget and the fight route, from the legacy script.
ARENA_GADGET_XY = (13275.00, -16039.00)
ARENA_PATH = [
    (-15115.72, -15375.61),
    (-11299.54, -16402.40),
    (-7284.53, -16235.58),
    (-4397.42, -16123.15),
    (-1385.20, -14400.23),
    (505.33, -14073.99),
    (2959.12, -15991.76),
    (5740.82, -15543.48),
    (7157.02, -15755.44),
    (12249.79, -16291.74),
]

# Gunnar's Hold quest NPC, from the legacy script.
QUEST_NPC_XY = (17341.00, -4796.00)

# Chest-watchdog allowlist for chest gadget models that `GetNearestChest` does
# not cover (it only matches GadgetModelID names starting with "CHEST_").
# 44: "Locked Chest" gadget -- the same model the Reputation Farmer watchdog
# live-verified (2026-09-14, Mount Qinkai) and the model this route expects.
# A match only ever causes a detour to that chest, never a wrong behavior, so
# extra IDs are safe to add from a run's "gadget models seen" diagnostic.
EXTRA_CHEST_MODEL_IDS: tuple[int, ...] = (44,)

# Detection radius for the arena chest watchdog. The punch-out arena is walked
# in one pass, so a generous radius keeps a randomly-spawned chest reachable
# from the nearest waypoint boundary.
CHEST_DETOUR_RADIUS = 4500

botting_tree: BottingTree | None = None
initialized = False

# Chest gadgets already engaged this instance (agent IDs). A chest is one-shot,
# an opened chest's gadget may still be visible, and without the ledger the
# watchdog would walk back to it at every boundary inside detection radius.
# Reset per instance right after entering the arena.
_consumed_chests: set[int] = set()


def ensure_botting_tree() -> BottingTree:
    global botting_tree

    if botting_tree is None:
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name=ROUTINE_NAME,
            repeat=True,
            multi_account=False,
            isolation_enabled=True,
            configure_fn=_configure_upkeep,
        )
        # Service tree: ticks every frame regardless of planner position, so a
        # knockdown mid-arena gets respammed while MoveAndKill is still running.
        botting_tree.AddServiceTree("Stand Up Service", StandUpService)

    return botting_tree


def _configure_upkeep(tree: BottingTree) -> None:
    tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        resurrection_scroll=False,
        auto_inventory_handler_enabled=False,
        enable_outpost_imp_service=False,
        enable_explorable_imp_service=False,
        heroai_state_logging=False,
        enable_party_wipe_recovery=True,
        # A wipe during the arena fight restarts the lap, matching the legacy
        # OnDeath coroutine's jump back to the farm step.
        party_wipe_default_step_name="Punch-Out Lap",
    )



# ============================================================================
# Environment templates (same convention as Nightfall_leveler_BT_MA)
# ============================================================================

def ConfigureAggressiveEnv() -> BehaviorTree:
    return ensure_botting_tree().Config.ConfigureAggressiveEnv(
        multi_account=False,
        account_isolation=True,
        pause_on_danger=True,
        auto_loot=True,
        resurrection_scroll=False,
        reset_hero_ai=False,
    )


def ConfigurePacifistEnv() -> BehaviorTree:
    return ensure_botting_tree().Config.ConfigurePacifistEnv(
        multi_account=False,
        account_isolation=True,
        pause_on_danger=False,
        auto_loot=True,
        resurrection_scroll=False,
        reset_hero_ai=False,
    )


# ============================================================================
# Chest watchdog (ported from Reputation Farmer BT)
# ============================================================================

def _reset_chest_tracking() -> BehaviorTree:
    """Clear the per-instance chest ledger.

    Runs right after entering the arena: a fresh map instance has fresh chests,
    while a lap restart mid-run keeps its ledger so an already-opened chest is
    not re-approached (an opened chest's gadget may linger).
    """

    def _reset(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        _consumed_chests.clear()
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Reset Chest Tracking (New Instance)",
            action_fn=_reset,
        )
    )


def ChestDetour(radius: int = CHEST_DETOUR_RADIUS) -> BehaviorTree:
    """One chest-watchdog step: detour to a locked chest within `radius`, else fall through.

    The watchdog samples at arena leg boundaries; when a chest gadget is in
    range the lap detours, moves to it, and interacts -- the locked-chest dialog
    itself is answered by the native `auto_open_locked_chest` listener
    (System Settings), so this node only owns detection + travel + interaction.
    Detection failure is the healthy common case (a chest is not always in
    range) and simply continues the lap; an already-opened or missing chest
    gadget reads the same way, making the step idempotent across lap retries.
    """

    # Closure-local capture of the chest found by the finder action, consumed
    # by the lazily-built detour subtree on the next tick of the same sequence.
    target: dict[str, float] = {}
    # Agent ID of the chest being engaged this detour; consumed by the record
    # action after the interact completes.
    state: dict[str, int] = {"id": 0}

    def _find_chest(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            # One ledger-aware detector: nearest chest gadget not already
            # engaged this instance. GetNearestChest can not express the
            # exclusion, and re-detecting an opened chest (its gadget may
            # linger) would send the lap back to it at the next boundary.
            known_chests = {
                int(e.value) for e in GadgetModelID if e.name.startswith("CHEST_")
            } | set(EXTRA_CHEST_MODEL_IDS)
            gadgets_in_range = AgentArray.Filter.ByDistance(
                AgentArray.GetGadgetArray(), Player.GetXY(), radius
            )
            gadgets_in_range = AgentArray.Sort.ByDistance(
                gadgets_in_range, Player.GetXY()
            )
            chest_id = 0
            for agent_id in gadgets_in_range:
                gadget_id = int(Agent.GetGadgetID(agent_id))
                if gadget_id not in known_chests:
                    continue
                if int(agent_id) in _consumed_chests:
                    continue
                chest_id = int(agent_id)
                break
            if chest_id == 0:
                # Diagnostic: no UNCONSUMED known chest matched. Report the
                # gadget models seen in range so an unlisted chest type can be
                # added to EXTRA_CHEST_MODEL_IDS from live evidence, not
                # guesswork.
                models = sorted(
                    {int(Agent.GetGadgetID(agent_id)) for agent_id in gadgets_in_range}
                )
                PySystem.Console.Log(
                    MODULE_NAME,
                    "Chest Watchdog: no unconsumed chest in range (%d); gadget models seen: %s"
                    % (radius, models or "none"),
                    PySystem.Console.MessageType.Info,
                )
                return BehaviorTree.NodeState.FAILURE
            chest_x, chest_y = Agent.GetXY(chest_id)
            state["id"] = chest_id
            target["x"] = float(chest_x)
            target["y"] = float(chest_y)
        except Exception:
            return BehaviorTree.NodeState.FAILURE
        return BehaviorTree.NodeState.SUCCESS

    def _build_detour(_node: BehaviorTree.Node) -> BehaviorTree:
        if "x" not in target or "y" not in target:
            return BT.LogMessage(
                "Chest Watchdog: no chest position captured - skipping.",
                module_name=MODULE_NAME,
            )
        return BT.MoveAndInteractWithGadget((target["x"], target["y"]), log=True)

    def _record_chest_consumed(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        # Reached and interacted -- success or not, that chest is done for
        # this instance (one attempt, never spammed). A detour interrupted
        # before reaching the chest fails the subtree above and skips this
        # node, so the chest stays eligible for the next boundary check.
        if state["id"]:
            _consumed_chests.add(state["id"])
            state["id"] = 0
        return BehaviorTree.NodeState.SUCCESS

    return BT.Selector(
        name="Chest Watchdog",
        children=[
            BT.Sequence(
                name="Detour To Locked Chest",
                children=[
                    BehaviorTree(
                        BehaviorTree.ActionNode(
                            name="Locked Chest Nearby?",
                            action_fn=_find_chest,
                        )
                    ),
                    BT.Subtree("Open Locked Chest", _build_detour),
                    BehaviorTree(
                        BehaviorTree.ActionNode(
                            name="Record Chest Consumed",
                            action_fn=_record_chest_consumed,
                        )
                    ),
                ],
            ),
            BT.LogMessage(
                "Chest Watchdog: no chest in range - continuing.",
                module_name=MODULE_NAME,
            ),
        ],
    )


# ============================================================================
# Arena walk with chest watchdog
# ============================================================================

def ArenaWalkWithChestWatch(steps: list[tuple[float, float]] | None = None) -> list[BehaviorTree]:
    """Walk the arena in legs, checking for a locked chest after each leg.

    Chest spawns in the punch-out are random, so sampling at every leg boundary
    keeps a passed chest within detection radius; the per-instance ledger keeps
    repeated checks spam-free. This mirrors the Reputation Farmer's
    `_vanquish_legs` with chest_watch on.
    """
    path = list(steps if steps is not None else ARENA_PATH)
    nodes: list[BehaviorTree] = [_reset_chest_tracking()]
    for leg_index, start in enumerate(range(0, len(path), 2), start=1):
        nodes.append(
            BT.VanquishNode(
                steps=path[start : start + 2],
                name=f"Arena Leg {leg_index}",
                flag_heroes_to_waypoint=False,
                log=False,
            )
        )
        nodes.append(ChestDetour())
    return nodes


# ============================================================================
# Stand-up service (port of the legacy OnDeath coroutine's revival spam)
# ============================================================================

# Slot 8 is the default "revive" / stand-up skill on the punch-out skillbar.
STAND_UP_SLOT = 8
# Re-queue interval, matching the legacy coroutine's 20ms respam cadence.
STAND_UP_INTERVAL_MS = 20
# Sentinel for "agent has no usable energy", which in the punch-out means the
# agent is down. Kept at the legacy value so timing matches the original.
STAND_UP_ENERGY_SENTINEL = 0.9999

_stand_up_skillbar: "PySkillbar.Skillbar | None" = None


def StandUpService() -> BehaviorTree:
    """Spam the stand-up skill while the agent is down, like the legacy OnDeath coroutine.

    The legacy FSM coroutine did two jobs: resign home when ``max_energy >= 80``
    (now owned by BottingTree party-wipe recovery) and respam
    ``UseSkillTargetless(slot 8)`` every 20ms while the agent read as
    "no energy" (now owned here). It is gated on the energy sentinel rather than
    ``Agent.IsKnockedDown()`` on purpose: the energy test also covers the revive
    animation, so a player who is briefly up-but-not-yet-mobile still gets
    respammed, which is what keeps the dwarves from finishing the knockdown.

    Runs as a BottingTree service tree so it ticks every frame regardless of
    where the planner is in the lap.
    """

    last_queue_ms = {"value": 0.0}

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _stand_up_skillbar
        try:
            if not Routines.Checks.Map.MapValid():
                return BehaviorTree.NodeState.SUCCESS

            agent_id = Player.GetAgentID()
            energy = Agent.GetEnergy(agent_id)

            # Energy recovered (or the agent was never down): nothing to do.
            if energy >= STAND_UP_ENERGY_SENTINEL:
                return BehaviorTree.NodeState.SUCCESS

            # In the punch-out a downed agent reports no energy. Do not spam
            # while dead for real -- party-wipe recovery owns that path.
            if Routines.Checks.Player.IsDead():
                return BehaviorTree.NodeState.SUCCESS

            now_ms = time.monotonic() * 1000.0
            if now_ms - last_queue_ms["value"] < STAND_UP_INTERVAL_MS:
                return BehaviorTree.NodeState.SUCCESS
            last_queue_ms["value"] = now_ms

            if _stand_up_skillbar is None:
                _stand_up_skillbar = PySkillbar.Skillbar()
            ActionQueueManager().AddAction(
                "FAST", _stand_up_skillbar.UseSkillTargetless, STAND_UP_SLOT
            )
        except Exception:
            pass
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Stand Up Service",
            action_fn=_tick,
        )
    )


# ============================================================================
# Steps
# ============================================================================

def EquipBrassKnuckles() -> BehaviorTree:
    """Ensure the brass knuckles are equipped before entering the arena.

    ``BT.EquipItemByModelID`` is already a check-then-equip-then-verify
    selector, so the happy path costs one inventory read and no action.

    The failure branch matters more than the happy one: the underlying routine
    returns FAILURE when the knuckles are not in the bags at all, and the
    planner restarts the *current* named step on failure -- which would pin the
    whole loop to this lap forever. A missing knuckle is an inventory problem
    the bot cannot solve, so it is reported loudly and the lap is allowed to
    continue rather than wedging the loop. Without the knuckles the brawl is
    unwinnable and the lap will fail on its own terms anyway; the difference is
    a diagnosable failure instead of a silent restart loop.
    """
    return BT.Selector(
        name="Equip Brass Knuckles",
        children=[
            BT.EquipItemByModelID(BRASS_KNUCKLES_MODEL_ID, log=True),
            BT.LogMessage(
                "Brass knuckles (%d) are not equipped and not in the bags - "
                "the punch-out brawl cannot be won without them. Recover the "
                "knuckles (or rerun the unlock to re-earn the punch-out "
                "skillbar), then restart the bot. Continuing the lap."
                % BRASS_KNUCKLES_MODEL_ID,
                module_name=MODULE_NAME,
                print_to_console=True,
                print_to_blackboard=True,
            ),
        ],
    )


def PunchOutLap() -> BehaviorTree:
    """One punch-out lap, from the legacy KillroyMap()."""
    return BT.Sequence(
        name="Punch-Out Lap",
        children=[
            # Heroes are dismissed before the brawl: the punch-out lap is
            # fought solo, and heroes are invited back before the reward
            # dialog so they share the quest XP (the original's design).
            BT.LeaveParty(),
            BT.Travel(target_map_id=GUNNARS_HOLD),
            ConfigureAggressiveEnv(),
            BT.MoveAndDialog(pos=QUEST_NPC_XY, dialog_id=0x835803),
            BT.MoveAndDialog(pos=QUEST_NPC_XY, dialog_id=0x835801),
            BT.MoveAndDialog(pos=QUEST_NPC_XY, dialog_id=0x85),
            # Brass knuckles are mandatory: the punch-out brawl only responds to
            # the knuckle skillbar, so entering the arena without them equipped
            # leaves the bot standing in a fight it cannot win. Legacy ran this
            # in the once-only unlock step, which is why a lap that re-enters
            # the same map needs it re-asserted here.
            EquipBrassKnuckles(),
            BT.WaitUntilOnExplorable(),
            # VanquishNode walks the arena and clears enemies around each
            # waypoint, pausing behavior like the aggressive env does. Split
            # into legs with a locked-chest watchdog after each leg: chest
            # spawns are random, so boundary sampling keeps a passed chest in
            # detection radius.
            *ArenaWalkWithChestWatch(),
            BT.WaitUntilOutOfCombat(),
            BT.Wait(duration_ms=1000),
            # Direct pickup path: target + interact, no PickUpLoot relay.
            BT.LootItems(distance=Range.Spirit.value),
            # Walk onto the chest before interacting. The gadget interact path
            # (InteractWithGadgetAtXY -> TargetNearestGadgetXY) only TARGETS and
            # interacts; it never moves, and its search radius is far smaller
            # than the ~1050 units between the last arena waypoint and the
            # chest. Without this approach the target lookup fails, the chest
            # never opens, and the mission never completes.
            BT.Move(pos=ARENA_GADGET_XY),
            BT.InteractWithGadgetAtXY(ARENA_GADGET_XY, target_distance=Range.Area.value),
            BT.Wait(duration_ms=2000),
            ConfigurePacifistEnv(),
            BT.Wait(duration_ms=3000),
            BT.Resign(wait_for_map_load=True, target_map_id=GUNNARS_HOLD),
            # Heroes must be in the party BEFORE the reward dialog fires,
            # or they receive nothing from the quest XP.
            InviteHeroesForXP(),
            BT.MoveAndDialog(pos=QUEST_NPC_XY, dialog_id=0x835807),
            BT.Wait(duration_ms=1000),
            BT.TravelGH(),
            BT.LeaveParty(),
            BT.LeaveGH(),
            BT.WaitForMapLoad(map_id=GUNNARS_HOLD),
        ],
    )


# ============================================================================
# Hero invites (from the BT original's InviteHeroesForXP)
# ============================================================================

def InviteHeroesForXP() -> BehaviorTree:
    """Invite the standard leveling heroes so they share the punch-out XP."""
    leveling_heroes = [
        HeroType.Koss,
        HeroType.Dunkoro,
        HeroType.Tahlkora,
        HeroType.Melonni,
        HeroType.Olias,
        HeroType.AcolyteJin,
        HeroType.AcolyteSousuke,
    ]
    hero_ids = [int(hero.value) for hero in leveling_heroes]

    return BT.Sequence(
        name="Invite Heroes For XP",
        children=[
            BT.LeaveParty(),
            BT.CreateParty(hero_ids=hero_ids, log=False),
            BT.Wait(duration_ms=1000),
        ],
    )


# ============================================================================
# Execution steps registration
# ============================================================================

def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Ordered (step_name, builder) list consumed by the BT runtime.

    A single named step is the whole routine: with ``repeat=True`` the planner
    runs a full pass, resets on success, and starts the lap again. An unlock
    step must NOT live in this list -- a successful pass resets to step one and
    re-runs every step, so a quest-unlock chain that can only run once on a
    fresh character would fail on every later pass. Because the planner
    restarts the *current* named step on failure, that failure would pin the
    loop to the unlock forever instead of advancing to the lap.
    """
    return [
        ("Punch-Out Lap", PunchOutLap),
    ]


# ============================================================================
# Widget wiring
# ============================================================================

def main() -> None:
    global initialized

    if not initialized:
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()
    tree.UI.draw_window(
        icon_path=ICON_PATH,
        main_child_dimensions=(500, 350),
    )


def tooltip() -> str:
    return MODULE_NAME + " - Kilroy punch-out farming bot (BT)."


if __name__ == "__main__":
    main()
