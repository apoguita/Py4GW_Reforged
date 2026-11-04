# Sadi's Benediction BT - Forum Highlands green staff farm (multibox).
#
# Kills Commander Sadi-Belai's group for a shot at Sadi's Benediction, the
# unique green staff. This is the SAME monk boss the elite-capture bot uses
# to cap Zealous Benediction, so the route below IS that proven capture path
# (EliteSkillsCapture.ZealousBenediction), walked in reverse intent:
#   Tihark Orchard (428) -> exit north -> Forum Highlands (399) ->
#   fight down to the boss group at the south choke -> loot -> resign -> loop.
# The wiki's own strategy note calls the south group near Commander
# Sadi-Belai a "Do Not Touch" pull - for everyone else. It is the farm.
#
# Normal Mode on purpose: green weapon farms run NM (see the sibling
# Green_Unique files, which are overwhelmingly SetHardMode(False)). Hard Mode
# is the Elite Tome farm family, not this one.
from __future__ import annotations

from collections.abc import Callable
import os
import time

import PyImGui
import PySystem

from Py4GWCoreLib import Color, ConsoleLog, ImGui, Listeners
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Sources.ApoSource.ApoBottingLib import wrappers as BT

MODULE_NAME = "Sadi's Benediction BT"
MODULE_ICON = "Assets\\Textures\\Module_Icons\\Sadi's_Benediction.png"
ROUTINE_NAME = "SadisBenedictionSequence"

BOT_NAME = "Sadi's Benediction Farm"
BOT_TEXTURE = os.path.join(PySystem.Console.get_projects_path(), MODULE_ICON)

# Map id, not name: the catalog stores this as "Tihark Orchard outpost", so
# GetMapIDByName("Tihark Orchard") silently resolved to 0 - which made
# Resign's WaitForMapLoad wait for map 0 forever, fail, and re-fire resign
# in town. The id is stable; use it.
OUTPOST_TO_TRAVEL = 428  # Tihark Orchard outpost
FORUM_HIGHLANDS_MAP_ID = 399

# Inventory item model id for Sadi's Benediction (the green staff drop), as
# provided by the operator. Keys the same party-wide counter the Asterius
# Scythe BT uses for its scythe.
SADI_STAFF_ITEM_MODEL_ID = 19419
STAFF_COUNT_BLACKBOARD_KEY = "sadi_staff_count"
STAFF_PER_ACCOUNT_BLACKBOARD_KEY = "sadi_staff_per_account"

# Set to False to disable headless Hero AI and use the Hero AI widget directly.
# This makes manual operations like resigning easier since accounts won't fight
# for control. Set to True for full BottingTree automation.
USE_HEADLESS_HERO_AI = False

# When running with the HeroAI widget (USE_HEADLESS_HERO_AI = False), the widget's
# frame loop re-runs settings init on a 50 ms retry and logs "Loading HeroAI
# settings..." ~20x/sec. The real fix is that init latch in the shared HeroAI
# code, which is out of scope for this bot file, so we mute just that one line
# through this bot's own view of the module's ConsoleLog. Everything else passes
# through untouched. Set to False to see the spam again.
SUPPRESS_HEROAI_SETTINGS_SPAM = True

# Tihark Orchard -> Forum Highlands exit, same coords the capture bot uses.
EXIT_TO_FARM: tuple[float, float] = (-3.0, 12656.0)

# Forum Highlands killing route, lifted verbatim from the capture bot's walk.
# The last point IS Commander Sadi-Belai's group - VanquishNode's final clear
# happens right on top of the boss.
TRAVEL_PATH: list[tuple[float, float]] = [
    (-6079, 4930),
    (-7671, -3974),
    (-8311, -8169),
    (3971, -12376),
]

LOOT_SETTLE_MS = 10_000
POST_OUTPOST_SETTLE_MS = 10_000
MULTIBOX_PARTY_TIMEOUT_MS = 30_000
MULTIBOX_TRAVEL_TIMEOUT_MS = 60_000

botting_tree: BottingTree | None = None


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Prepare For Farm", _step_prepare_for_farm),
        ("Prepare Multibox Party", _step_prepare_multibox_party),
        ("Exit To Farm", _step_exit_to_farm),
        ("Wait For Farm Map", _step_wait_for_farm_map),
        ("Kill Route", _step_kill_route),
        ("Resign", _step_resign),
        ("Back On Outpost", _step_back_on_outpost),
    ]


def _suppress_heroai_settings_spam() -> None:
    """
    Mute only the "Loading HeroAI settings..." log line emitted by HeroAI's
    settings module, without touching that shared file.

    The HeroAI widget's frame loop (_handle_settings) retries settings init on a
    50 ms throttle whenever ensure_initialized() fails to latch, and each retry
    logs "Loading HeroAI settings...". This wraps the ConsoleLog reference that
    the settings module resolved at import time and drops that one exact line;
    every other HeroAI log passes through unchanged. Idempotent: re-running
    detects the wrapper and does nothing.
    """
    try:
        from Py4GWCoreLib.HeroAI import settings as heroai_settings
    except Exception:
        return

    original_console_log = getattr(heroai_settings, "ConsoleLog", None)
    if original_console_log is None or getattr(original_console_log, "_sadi_spam_filter", False):
        return

    _SPAM_TEXT = "Loading HeroAI settings..."

    def _filtered_console_log(module_name: str, message: str, *args, **kwargs):
        if str(module_name) == "HeroAI" and str(message).strip() == _SPAM_TEXT:
            return
        return original_console_log(module_name, message, *args, **kwargs)

    _filtered_console_log._sadi_spam_filter = True  # type: ignore[attr-defined]
    heroai_settings.ConsoleLog = _filtered_console_log


def ensure_botting_tree() -> BottingTree:
    global botting_tree

    if SUPPRESS_HEROAI_SETTINGS_SPAM:
        _suppress_heroai_settings_spam()

    if botting_tree is None:
        Listeners.AutoReturnOnDefeat.Enable()
        botting_tree = BottingTree.Create(
            f"{BOT_NAME} BT",
            main_routine=get_execution_steps(),
            routine_name=ROUTINE_NAME,
            repeat=True,
            pause_on_combat=True,
            multi_account=True,
            auto_loot=True,
            isolation_enabled=False,
            activate_widget_list=["HeroAI"] if not USE_HEADLESS_HERO_AI else None,
            configure_fn=lambda tree: (
                tree.Config.ConfigureUpkeep(
                    looting_enabled=True,
                    resurrection_scroll=True,
                    auto_inventory_handler_enabled=True,
                    consumable_upkeeps=(),
                    heroai_state_logging=False,
                    enable_party_wipe_recovery=True,
                ),
                tree.AddServiceTree("Staff Counter", BehaviorTree(BehaviorTree.ActionNode(name="StaffCounter", action_fn=_staff_counter_tick))),
            ),
        )
        # Set headless Hero AI state after creation to avoid type stub issues
        # type: ignore[attr-defined] - Core library type stub mismatch: protocol uses literal types that don't match implementation
        botting_tree.SetHeadlessHeroAIEnabled(USE_HEADLESS_HERO_AI, reset_runtime=True)  # type: ignore[attr-defined]

    return botting_tree


def _count_local_staffs() -> int:
    """Count Sadi's Benediction in this client's own inventory bags (bags 1-4)."""
    from Py4GWCoreLib import GLOBAL_CACHE, Item

    bags_to_check = GLOBAL_CACHE.ItemArray.CreateBagList(1, 2, 3, 4)
    item_array = GLOBAL_CACHE.ItemArray.GetItemArray(bags_to_check)
    staff_count = 0
    for item_id in item_array:
        try:
            if int(Item.GetModelID(item_id) or 0) == SADI_STAFF_ITEM_MODEL_ID:
                staff_count += 1
        except Exception:
            continue
    return staff_count


def _count_party_staffs() -> tuple[int, dict[str, int]]:
    """
    Count Sadi's Benediction across every party member's inventory.

    Every running client mirrors its own bags (Backpack/BeltPouch/Bag1/Bag2,
    per-slot model ids) into the multibox shared-memory region. As the leader,
    read that region so the total reflects the whole party, not just the
    account running this script. Returns (party_total, per_account_breakdown).

    Each account is read in an isolated try/except so one unreadable account can
    never abort the whole tally. For our own account the mirror can lag ~1.5s
    behind a fresh loot, so we take max(mirror, live local read) for self: the
    live read can only raise self's count, never lower it, and a failure there
    simply falls back to the mirror.

    Falls back to counting only this client's local bags when shared memory is
    unavailable (e.g. a single client, or the C++ writer is not up yet).
    """
    from Py4GWCoreLib import GLOBAL_CACHE, Player

    try:
        self_email = str(Player.GetAccountEmail() or "")
    except Exception:
        self_email = ""

    breakdown: dict[str, int] = {}
    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception:
        accounts = []

    if not accounts:
        # Shared memory unavailable: count only this client's local bags.
        local_count = _count_local_staffs()
        if local_count:
            breakdown["Leader (local)"] = local_count
        return local_count, breakdown

    for account in accounts:
        try:
            if not getattr(account, "IsSlotActive", False):
                continue

            account_email = str(getattr(account, "AccountEmail", "") or "")
            name = (
                str(getattr(account, "AccountName", "") or "")
                or account_email
                or f"Slot {int(getattr(account, 'SlotNumber', 0) or 0)}"
            )

            # Base count from the shared-memory mirror (works for every account).
            account_count = 0
            for bag in account.InventoryBags.iter_bags():
                for slot in bag.Slots:
                    if int(getattr(slot, "ModelID", 0) or 0) == SADI_STAFF_ITEM_MODEL_ID:
                        account_count += 1

            # Our own mirror can lag behind a fresh loot; the live local read is
            # always current. Raise self's count to it (never lower), tolerating
            # a failed read without ever lowering the count or aborting
            # the aggregation if the local read fails.
            if self_email and account_email == self_email:
                try:
                    account_count = max(account_count, _count_local_staffs())
                except Exception:
                    pass

            if account_count:
                breakdown[name] = account_count
        except Exception:
            # A single unreadable account must not zero out the rest.
            continue

    return sum(breakdown.values()), breakdown


# The counter is a service tree, so _staff_counter_tick fires every frame. A
# full-party bag scan (every account's InventoryBags plus a live local read) is
# far too expensive to run 60x/sec for a number that only changes when a staff
# drops. Cap the aggregation to once per interval so it stops hammering
# shared memory / the account snapshot every frame.
STAFF_COUNTER_INTERVAL_MS = 1000
_staff_counter_last_run_ms = 0.0


def _staff_counter_tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
    """Service tick that counts Sadi's Benediction across the whole party.

    Throttled to once per STAFF_COUNTER_INTERVAL_MS: the heavy aggregation is
    skipped on all other frames to avoid per-frame shared-memory/account work.
    """
    global _staff_counter_last_run_ms
    now_ms = time.monotonic() * 1000.0
    if now_ms - _staff_counter_last_run_ms < STAFF_COUNTER_INTERVAL_MS:
        return BehaviorTree.NodeState.RUNNING
    _staff_counter_last_run_ms = now_ms

    try:
        staff_count, breakdown = _count_party_staffs()
        previous_count = int(node.blackboard.get(STAFF_COUNT_BLACKBOARD_KEY, 0) or 0)
        if staff_count > previous_count:
            ConsoleLog(MODULE_NAME, f"Sadi's Benediction collected! Party total: {staff_count}", 1)
        node.blackboard[STAFF_COUNT_BLACKBOARD_KEY] = staff_count
        node.blackboard[STAFF_PER_ACCOUNT_BLACKBOARD_KEY] = breakdown
    except Exception:
        pass
    return BehaviorTree.NodeState.RUNNING


def _travel_all_accounts(refs_key: str) -> BehaviorTree:
    """Pull every other account to the local map, district and language.

    Delegates to ``BTShared.SummonAllAccounts``, the same routine
    ``CreateParty(multibox_invite=True)`` uses, so district handling stays in
    one owner. The local account is already here, so ``include_self`` is not a
    concern for this call.
    """
    return RoutinesBT.Shared.SummonAllAccounts(
        refs_blackboard_key=refs_key,
        timeout_ms=MULTIBOX_TRAVEL_TIMEOUT_MS,
        poll_interval_ms=250,
        log=True,
    )


def _aggressive(name: str = "Configure Aggressive") -> BehaviorTree:
    return ensure_botting_tree().Config.Aggressive(
        multi_account=True,
        account_isolation=False,
        pause_on_danger=True,
        auto_loot=True,
        resurrection_scroll=True,
        reset_hero_ai=USE_HEADLESS_HERO_AI,
    )


def _invite_all_accounts(refs_key: str) -> BehaviorTree:
    """Invite every eligible account on this map into the local party.

    Uses ``BTShared.InviteAllAccounts`` rather than ``LoadParty``: ``LoadParty``
    fills the party with heroes and henchmen, which this variant must not do.
    """
    return RoutinesBT.Shared.InviteAllAccounts(
        refs_blackboard_key=refs_key,
        timeout_ms=MULTIBOX_PARTY_TIMEOUT_MS,
        poll_interval_ms=250,
        log=True,
    )


def _prepare_multibox_party(refs_key: str) -> BehaviorTree:
    """Form a player-only multibox party.

    No heroes. No henchmen. No hero skillbars.
    Uses aggressive mode to keep Hero AI enabled on all accounts for following.
    """
    return BT.Sequence(
        name="Prepare Multibox Party",
        children=[
            _aggressive(),
            _travel_all_accounts(f"{refs_key}_travel"),
            _invite_all_accounts(f"{refs_key}_invite"),
        ],
    )


# Compatibility alias for the farm sequence below. It used to build a
# hero+henchman party in sibling conversions; this farm stays players-only,
# so the name now forms the multibox party.
def _prepare_standard_party() -> BehaviorTree:
    return _prepare_multibox_party("sadi_party")


# Each step below builds lazily at planner time so ``_aggressive``
# can reach the already-created tree. Building them eagerly inside the
# step list would recurse through ``ensure_botting_tree``.
def _step_prepare_for_farm() -> BehaviorTree:
    return BT.Sequence(
        "Prepare For Farm",
        map_id_or_name=OUTPOST_TO_TRAVEL,
        hard_mode=False,
        children=[
            BT.SetHardMode(False),
        ],
    )


def _step_prepare_multibox_party() -> BehaviorTree:
    return _prepare_standard_party()


def _step_exit_to_farm() -> BehaviorTree:
    return BT.MoveAndExitMap(EXIT_TO_FARM, target_map_id=FORUM_HIGHLANDS_MAP_ID)


def _step_wait_for_farm_map() -> BehaviorTree:
    return BT.Sequence(
        "Wait For Farm Map",
        children=[
            BT.WaitForMapLoad(FORUM_HIGHLANDS_MAP_ID, timeout_ms=30_000),
            BT.Wait(4000),
        ],
    )


def _step_kill_route() -> BehaviorTree:
    # Sadi is a stationary boss at a fixed position, unlike Asterius who walks
    # a patrol path. VanquishNode's final waypoint IS her group, so the route
    # clear kills her outright - no separate spot-and-wait confirmation needed
    # (that wait would poll for a live boss already dead and stall the run).
    return BT.Sequence(
        "Kill Route",
        children=[
            BT.VanquishNode(TRAVEL_PATH),
            BT.Wait(LOOT_SETTLE_MS),
        ],
    )


def _step_resign() -> BehaviorTree:
    return BT.Resign(wait_for_map_load=True, target_map_id=OUTPOST_TO_TRAVEL, multi_account=True)


def _step_back_on_outpost() -> BehaviorTree:
    return BT.Sequence(
        "Back On Outpost",
        children=[
            BT.WaitUntilOnOutpost(timeout_ms=30_000),
            BT.Wait(POST_OUTPOST_SETTLE_MS),
        ],
    )


def _get_tree() -> BottingTree:
    """Compatibility alias for the lazily built shared controller."""
    return ensure_botting_tree()


def configure() -> None:
    return None


def _draw_staff_stats_tab() -> None:
    """Draw staff collection statistics in a dedicated tab."""
    PyImGui.text_colored("Sadi's Benediction Farm Statistics", Color(255, 200, 100, 255).to_tuple_normalized())
    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    staff_count = 0
    per_account: dict[str, int] = {}
    if botting_tree is not None:
        staff_count = int(botting_tree.blackboard.get(STAFF_COUNT_BLACKBOARD_KEY, 0) or 0)
        per_account = botting_tree.blackboard.get(STAFF_PER_ACCOUNT_BLACKBOARD_KEY, {}) or {}

    PyImGui.text(f"Total Staves Collected (Party): {staff_count}")
    PyImGui.spacing()

    PyImGui.text_colored("Per Account Breakdown:", Color(200, 200, 200, 255).to_tuple_normalized())
    if per_account:
        for account_name, account_count in sorted(per_account.items(), key=lambda kv: (-kv[1], kv[0])):
            PyImGui.bullet_text(f"{account_name}: {account_count}")
    else:
        PyImGui.bullet_text("No staves recorded yet.")
    PyImGui.spacing()

    PyImGui.text_colored("Configuration:", Color(200, 200, 200, 255).to_tuple_normalized())
    headless_status = "ENABLED" if USE_HEADLESS_HERO_AI else "DISABLED"
    PyImGui.bullet_text(f"Headless Hero AI: {headless_status}")
    if not USE_HEADLESS_HERO_AI:
        PyImGui.bullet_text("  - Uses Hero AI widget directly (easier manual control)")
        PyImGui.bullet_text("  - Edit USE_HEADLESS_HERO_AI at the top of the file to enable")

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.text_colored("Requirements:", Color(200, 200, 200, 255).to_tuple_normalized())
    PyImGui.bullet_text("- 6-8 well-geared player accounts")
    PyImGui.bullet_text("- Launch the script on the party leader only")
    PyImGui.bullet_text("- No heroes or henchmen (lowers green drop rates)")
    PyImGui.bullet_text("- Normal Mode (better green drop rates)")

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.text_colored("Credits:", Color(200, 200, 200, 255).to_tuple_normalized())
    PyImGui.bullet_text("Route from the Zealous Benediction capture bot")
    PyImGui.bullet_text("BT conversion and staff counter by Kendor")


def tooltip() -> None:
    PyImGui.begin_tooltip()

    title_color = Color(255, 200, 100, 255)
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored("Sadi's Benediction Farmer BT", title_color.to_tuple_normalized())
    ImGui.pop_font()
    PyImGui.spacing()
    PyImGui.separator()

    PyImGui.text("multi-account bot to farm Sadi's Benediction (green staff)")
    PyImGui.spacing()
    PyImGui.bullet_text("See the 'Staff Stats' tab for collection statistics")
    PyImGui.bullet_text("Boss: Commander Sadi-Belai, Forum Highlands")
    PyImGui.bullet_text("Route shared with the Zealous Benediction capture bot")
    PyImGui.spacing()
    PyImGui.bullet_text("Requirements:")
    PyImGui.bullet_text("- 6-8 well-geared player accounts")
    PyImGui.bullet_text("- Launch the script on the party leader only")
    PyImGui.bullet_text("- No heroes or henchmen (lowers green drop rates)")
    PyImGui.bullet_text("- Normal Mode (better green drop rates)")

    PyImGui.end_tooltip()


def main() -> None:
    tree = _get_tree()
    tree.tick()
    tree.UI.draw_window(
        icon_path=BOT_TEXTURE,
        extra_tabs=[("Staff Stats", _draw_staff_stats_tab)],
    )


__all__ = ["main", "configure", "tooltip"]

