from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Py4GWCoreLib import UIManager
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib import Agent, Botting, ConsoleLog, Effects, GLOBAL_CACHE, Map, ModelID, Player, Range, Routines
from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters import LootFilters
from Py4GWCoreLib.py4gwcorelib_src.AutoInventoryHandler import AutoInventoryHandler
from Sources.aC_Scripts.aC_api.Verify_Blessing import Blessings
import Py4GW
import PyImGui
import PySystem
import os
import time

MODULE_NAME = "Ferndale (Vanquish)"
MODULE_ICON = "Textures\\Module_Icons\\Vanquish - Ferndale.png"

BOT_NAME = "VQ Ferndale"
TEXTURE = os.path.join(PySystem.Console.get_projects_path(), "Sources", "ApoSource", "textures", "VQ_Helmet.png")
HOUSE_ZU_HELZER = 77
FERNDALE = 210
COORDS_TO_EXIT_OUTPOST = (10446.0, -1147.0)
COORDS_FOR_PRIEST = (-12909.0, 15616.0)

STAGE_TOWN_SETUP = "Stage 1 Init - Town Setup"
STAGE_ENTER_AREA = "Stage 2 Init - Enter Ferndale"
STAGE_START_ROUTE = "Stage 3 Init - Start Vanquish Route"
STAGE_POST_ROUTE = "Stage 4 Init - Post Route"
STAGE_MANUAL_DONATION = "Stage 5 Init - Manual Donation Test"

_KURZICK_PRIEST_MODEL_ID = 3477
_KURZICK_PRIEST_CAPTURE_IDS = (
    "NPC-20260815-171112-253",
    "NPC-20260815-171146-695",
)
_KURZICK_PRIEST_APPROACH_XY = (-12878.49, 15596.32)
_HOUSE_DONATION_NPC_MODEL_ID = 3465
_HOUSE_DONATION_NPC_TARGET_XY = (5336.0, 1468.0)
_HOUSE_DONATION_APPROACH_XY = (5306.78, 1543.68)
_HOUSE_DONATION_CAPTURE_ID = "NPC-20260813-091734-598"

RETURN_TO_OUTPOST_HEADER = STAGE_POST_ROUTE

restart_after_run = True
donate_after_run = True
watch_vanquish_completion = True
DONATION_HEADROOM = 30_000
DONATION_CHUNK = 5_000
VQ_TIMEOUT_MS = 45 * 60 * 1000
DEAD_MEMBER_RECOVERY_TIMEOUT_MS = 60 * 1000
_CARRIED_GOLD_TARGET = 1_000
_BLESSING_GOLD_REQUIRED = 100
_ALCOHOL_RESTOCK_TARGET = 50
_ALCOHOL_MODEL_IDS = (
    int(ModelID.Dwarven_Ale.value), int(ModelID.Hunters_Ale.value),
    int(ModelID.Bottle_Of_Rice_Wine.value), int(ModelID.Bottle_Of_Vabbian_Wine.value),
    int(ModelID.Bottle_Of_Juniberry_Gin.value), int(ModelID.Shamrock_Ale.value),
    int(ModelID.Hard_Apple_Cider.value), int(ModelID.Eggnog.value),
    int(ModelID.Aged_Dwarven_Ale.value), int(ModelID.Aged_Hunters_Ale.value),
    int(ModelID.Keg_Of_Aged_Hunters_Ale.value), int(ModelID.Bottle_Of_Grog.value),
    int(ModelID.Spiked_Eggnog.value), int(ModelID.Vial_Of_Absinthe.value),
    int(ModelID.Witchs_Brew.value),
)

experiment_label = "Ferndale baseline"
_vq_terminal_requested = False

Vanquish_Path: list[tuple[float, float]] = [
    (-9358.26, 12733.01),
    (-11763.50, 6875.62),
    (-8343.50, 10348.14),
    (-9358.26, 12733.01),
    (-11057.97, 20483.20),
    (-5486.26, 18571.37),
    (-5214.33, 15808.12),
    (-3129.34, 15116.34),
    (-1997.73, 19808.71),
    (937.34, 14460.03),
    (-1552.20, 12181.78),
    (-418.83, 9722.58),
    (1623.41, 11681.61),
    (2353.03, 8665.77),
    (3497.35, 7112.98),
    (4920.25, 14639.28),
    (4777.39, 8038.80),
    (6225.68, 14860.03),
    (7747.10, 12009.60),
    (9991.06, 11601.30),
    (9188.73, 16076.83),
    (12075.11, 18961.69),
    (11635.97, 9944.48),
    (3388.01, 5963.63),
    (-2324.46, 224.24),
    (4964.69, 4695.06),
    # ROUTE-20260815-221247-741: exact center-of-bridge capture replacing
    # the side-biased bridge path that could wedge the player against terrain.
    (5032.51, 4820.28),
    (5238.35, 4587.86),
    (5450.09, 4452.25),
    (5670.98, 4332.43),
    (5890.77, 4202.19),
    (6131.49, 4119.66),
    (6385.12, 4102.94),
    (6637.95, 4107.18),
    (6891.35, 4115.85),
    (7148.72, 4108.70),
    (7395.43, 4065.94),
    (7541.51, 4000.25),
    (9769.06, 3201.43),
    (11953.75, 9212.22),
    (14419.30, 1311.15),
    (8990.68, 518.77),
    (9532.74, -2186.87),
    (5588.56, -1831.51),
    (4358.47, -3596.96),
    (2391.71, -3199.59),
    (-811.80, -2427.94),
    (4681.77, -12246.70),
    (8444.18, -11786.52),
    (8241.50, -13956.31),
    (10657.37, -17255.84),
    (14073.04, -19839.37),
    (3291.92, -13745.13),
    (3629.04, -14834.70),
    (-7260.26, -18284.58),
    (1653.33, -10685.74),
    (-531.23, -10904.48),
    (-114.91, -9269.86),
    (-2798.66, -7118.50),
    (-7398.05, -6884.35),
    (-9947.11, -8920.49),
    (-8121.48, -5619.89),
    (-2614.03, -5811.48),
    (-2540.95, -3791.90),
    (-5708.50, -3462.03),
    (-7744.69, -4578.63),
    # ROUTE-20260815-223100-292: exact stair traversal captured after the
    # original single waypoint could wedge the player against the stairs.
    (-8614.02, -3314.33),
    (-8487.01, -3092.58),
    (-8337.43, -2889.49),
    (-8168.50, -2701.54),
    (-7991.30, -2515.37),
    (-7816.38, -2332.85),
    (-7641.11, -2152.10),
    (-7460.12, -1976.07),
    (-7276.71, -1803.74),
    (-7090.80, -1629.06),
    (-6903.61, -1455.82),
    (-6720.03, -1286.00),
    (-6534.74, -1114.59),
    (-6348.03, -941.87),
    (-6144.84, -792.52),
    (-5925.72, -668.20),
    (-5847.54, -626.60),
    (-4026.24, 152.70),
    (-10708.04, 1472.96),
    (-12390.78, 6997.02),
    (-10708.04, 1472.96),
    (-4870.12, 3132.08),
    (-4187.85, 6256.14),
    (-828.52, 8779.88),
    (-6834.56, 8525.84),
    (-1292.07, 14085.61),
]

CONSET_PROPERTIES = ("essence_of_celerity", "grail_of_might", "armor_of_salvation")
PCON_PROPERTIES = (
    "birthday_cupcake",
    "golden_egg",
    "candy_corn",
    "candy_apple",
    "slice_of_pumpkin_pie",
    "drake_kabob",
    "bowl_of_skalefin_soup",
    "pahnai_salad",
)

bot = Botting(
    BOT_NAME,
    upkeep_hero_ai_active=True,
    upkeep_auto_inventory_management_active=True,
    upkeep_auto_loot_active=True,
    upkeep_armor_of_salvation_active=True,
    upkeep_birthday_cupcake_active=True,
    upkeep_bowl_of_skalefin_soup_active=True,
    upkeep_candy_apple_active=True,
    upkeep_candy_corn_active=True,
    upkeep_drake_kabob_active=True,
    upkeep_essence_of_celerity_active=True,
    upkeep_golden_egg_active=True,
    upkeep_grail_of_might_active=True,
    upkeep_honeycomb_active=True,
    upkeep_pahnai_salad_active=True,
    upkeep_slice_of_pumpkin_pie_active=True,
    upkeep_war_supplies_active=True,
)

_operator_pause_recorded = False


def _are_all_active(property_names: tuple[str, ...]) -> bool:
    return all(bool(bot.Properties.Get(name, "active")) for name in property_names)


def _set_all_active(property_names: tuple[str, ...], active: bool) -> None:
    for property_name in property_names:
        bot.Properties.ApplyNow(property_name, "active", active)


def _kurzick_blessing_active() -> bool:
    player_id = int(Player.GetAgentID() or 0)
    return player_id > 0 and any(
        Effects.EffectExists(player_id, effect_id)
        for effect_id in Blessings.Blessing_of_the_Kurzicks.ids
    )


def _initialize_town_stage():
    bot.ResetHeroAICombatState(
        active=True,
        following=True,
        avoidance=True,
        looting=False,
        targeting=False,
        combat=False,
        skills=False,
    )
    yield


def _initialize_post_route():
    bot.ResetHeroAICombatState(
        active=True,
        following=True,
        avoidance=True,
        looting=True,
        targeting=True,
        combat=True,
        skills=True,
    )
    yield


def _ensure_hard_mode_before_departure():
    if not bool(GLOBAL_CACHE.Party.IsHardMode()):
        ConsoleLog(BOT_NAME, "Switching party to Hard Mode.")
        yield from Routines.Yield.Map.SetHardMode(True)
    stable_reads = 0
    for _ in range(20):
        if bool(GLOBAL_CACHE.Party.IsHardMode()):
            stable_reads += 1
            if stable_reads >= 3:
                ConsoleLog(BOT_NAME, "Hard Mode confirmed before departure.")
                return True
        else:
            stable_reads = 0
        yield from Routines.Yield.wait(250)
    raise RuntimeError("Hard Mode could not be confirmed in House zu Heltzer")


def _normalize_carried_gold():
    while True:
        yield from Routines.Yield.Items.WithdrawGold(
            target_gold=_CARRIED_GOLD_TARGET,
            deposit_all=True,
            log=True,
        )
        for _ in range(20):
            carried = int(GLOBAL_CACHE.Inventory.GetGoldOnCharacter() or 0)
            if carried == _CARRIED_GOLD_TARGET:
                return True
            yield from Routines.Yield.wait(250)
        carried = int(GLOBAL_CACHE.Inventory.GetGoldOnCharacter() or 0)
        if carried >= _BLESSING_GOLD_REQUIRED:
            ConsoleLog(
                BOT_NAME,
                f"[Trip Reset] Gold settled at {carried:,}; the priest blessing is funded, continuing.",
            )
            return True
        ConsoleLog(BOT_NAME, "[Trip Reset] Blessing gold unavailable; retrying in 10 seconds.")
        yield from Routines.Yield.wait(10_000)


def _player_has_drunken_master() -> bool:
    skill_id = int(GLOBAL_CACHE.Skill.GetID("Drunken_Master") or 0)
    return skill_id > 0 and any(
        int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) or 0) == skill_id
        for slot in range(1, 9)
    )


def _carried_alcohol_count() -> int:
    return sum(
        int(GLOBAL_CACHE.Inventory.GetModelCount(model_id) or 0)
        for model_id in _ALCOHOL_MODEL_IDS
    )


def _ensure_trip_alcohol():
    if not _player_has_drunken_master():
        return True
    handler = AutoInventoryHandler()
    protected = set(int(model_id) for model_id in handler.deposit_model_blacklist)
    protected.update(_ALCOHOL_MODEL_IDS)
    handler.deposit_model_blacklist = sorted(protected)
    if _carried_alcohol_count() > 0:
        return True
    yield from Routines.Yield.Items.WithdrawFirstAvailable(
        list(_ALCOHOL_MODEL_IDS),
        _ALCOHOL_RESTOCK_TARGET,
    )
    if _carried_alcohol_count() <= 0:
        raise RuntimeError("Drunken Master is equipped, but no supported alcohol was found in storage")
    ConsoleLog(BOT_NAME, f"[Trip Reset] Withdrew {_carried_alcohol_count()} alcohol uses.")
    return True


def _prepare_trip_resources():
    yield from _normalize_carried_gold()
    yield from _ensure_trip_alcohol()
    return True


def _verify_explorable_hard_mode():
    for _ in range(20):
        if Map.GetMapID() == FERNDALE and Map.IsVanquishable():
            ConsoleLog(BOT_NAME, "Ferndale Hard Mode instance confirmed.")
            return True
        yield from Routines.Yield.wait(250)
    raise RuntimeError("Ferndale is not vanquishable; return to House zu Heltzer and retry")


def _run_owner_tree(bot: Botting, tree: BehaviorTree):
    """Schedule an existing owner tree while this FSM holds HeroAI upkeep."""
    saved_pause = bool(bot.Properties.Get("hero_ai_paused", "active"))
    bot.Properties.ApplyNow("hero_ai_paused", "active", True)
    try:
        yield from Routines.Yield.wait(100)
        while True:
            state = tree.tick()
            if state == BehaviorTree.NodeState.SUCCESS:
                return True
            if state == BehaviorTree.NodeState.FAILURE:
                return False
            yield from Routines.Yield.wait(100)
    finally:
        try:
            tree.reset()
        finally:
            if bool(bot.Properties.Get("hero_ai_paused", "active")):
                bot.Properties.ApplyNow("hero_ai_paused", "active", saved_pause)



def _take_kurzick_blessing(bot: Botting):
    tree = BT.TakeBlessing(pos=COORDS_FOR_PRIEST, faction="kurzick", multi_account=False, log=True)
    if not (yield from _run_owner_tree(bot, tree)):
        raise RuntimeError("Kurzick blessing owner failed")
    for _ in range(20):
        if _kurzick_blessing_active():
            return True
        yield from Routines.Yield.wait(250)
    raise RuntimeError("Kurzick blessing owner completed without an observed blessing effect")



def _open_kurzick_donation_npc(bot: Botting):
    tree = BT.MoveAndInteract(pos=_HOUSE_DONATION_NPC_TARGET_XY, log=True)
    if not (yield from _run_owner_tree(bot, tree)):
        return False
    for _ in range(20):
        if UIManager.IsNPCDialogVisible():
            return True
        yield from Routines.Yield.wait(250)
    return False



def _donate_all_available_kurzick(bot: "Botting"):
    if not (yield from _open_kurzick_donation_npc(bot)):
        return False, "Kurzick Bureaucrat interaction failed"
    previous = int(Player.GetKurzickData()[0])
    donated = 0
    while previous >= DONATION_CHUNK:
        Player.DepositFaction(0)
        yield from Routines.Yield.wait(750)
        current = int(Player.GetKurzickData()[0])
        if current >= previous:
            return False, f"Kurzick faction did not decrease after donation request ({previous:,})"
        donated += previous - current
        previous = current
    if donated <= 0:
        return False, "No Kurzick faction was available in a complete 5,000-point chunk"
    ConsoleLog(BOT_NAME, f"[Donation] Donated {donated:,} Kurzick faction to the alliance.")
    return True, ""


def _donate_kurzick_if_near_cap(bot: "Botting"):
    current, _, maximum = Player.GetKurzickData()
    if int(maximum) > 0 and int(maximum) - int(current) > DONATION_HEADROOM:
        return True
    if Map.GetMapID() != HOUSE_ZU_HELZER:
        yield from bot.Map._coro_travel(HOUSE_ZU_HELZER, "")
    success, reason = yield from _donate_all_available_kurzick(bot)
    if not success:
        raise RuntimeError(reason)
    return True


def _drain_post_vq_loot():
    yield from Routines.Yield.wait(1_000)
    loot_filters = LootFilters()
    if not loot_filters.GetLootArray(Range.Earshot.value):
        return True
    ConsoleLog(BOT_NAME, "[Post-VQ Loot] Waiting for eligible nearby drops before travel.")
    elapsed_ms = 0
    while elapsed_ms < 8_000:
        if not loot_filters.GetLootArray(Range.Earshot.value):
            ConsoleLog(BOT_NAME, "[Post-VQ Loot] Eligible nearby drops collected.")
            return True
        yield from Routines.Yield.wait(250)
        elapsed_ms += 250
    ConsoleLog(BOT_NAME, "[Post-VQ Loot] Timed out after 8 seconds; continuing restart.")
    return False


def _post_vq_transition(bot: "Botting"):
    fully_vanquished = bool(Map.IsVanquishCompleted())
    if fully_vanquished:
        yield from _drain_post_vq_loot()
    current, _, maximum = Player.GetKurzickData()
    headroom = max(0, int(maximum) - int(current))
    if fully_vanquished and donate_after_run and headroom <= DONATION_HEADROOM:
        yield from bot.Map._coro_travel(HOUSE_ZU_HELZER, "")
        success, reason = yield from _donate_all_available_kurzick(bot)
        if not success:
            ConsoleLog(BOT_NAME, f"[Donation] Post-VQ donation failed: {reason}; continuing restart.")
    else:
        reason = "vanquish was not confirmed" if not fully_vanquished else f"faction headroom is {headroom:,}"
        ConsoleLog(BOT_NAME, f"[Donation] No post-VQ donation needed: {reason}.")
    if Map.GetMapID() != HOUSE_ZU_HELZER:
        yield from bot.Map._coro_travel(HOUSE_ZU_HELZER, "")
    yield from _prepare_trip_resources()
    return True


def _initialize_vanquish_attempt():
    global _vq_terminal_requested
    _vq_terminal_requested = False
    yield


def _cancel_active_route_and_enter_post_vq(bot: "Botting") -> None:
    bot.config.FSM.jump_to_state_by_name(RETURN_TO_OUTPOST_HEADER, cancel_current_state=True)
    bot.config.FSM.resume()


def _ensure_route_watchdogs(bot: "Botting") -> None:
    """Restore route safeguards after an operator jumps to a waypoint step."""
    bot.config.FSM.AddManagedCoroutine(
        "FerndaleVanquishWatchdog",
        lambda: _vanquish_watchdog(bot),
    )
    bot.config.FSM.AddManagedCoroutine(
        "FerndaleDeadMemberRecoveryWatchdog",
        lambda: _dead_member_recovery_watchdog(bot),
    )


def _follow_logged_waypoint(bot: "Botting", waypoint: int, x: float, y: float):
    if _vq_terminal_requested:
        return True
    _ensure_route_watchdogs(bot)
    yield from bot.Move._coro_get_path_to(x, y)
    if _vq_terminal_requested:
        return True
    yield from bot.Move._coro_follow_path_to()
    if _vq_terminal_requested:
        return True
    ConsoleLog(BOT_NAME, f"[Route] Reached waypoint {waypoint}/{len(Vanquish_Path)} at ({x:.0f}, {y:.0f}).")
    return True


def _get_vanquish_progress() -> tuple[int, int, int, float]:
    if not Routines.Checks.Map.MapValid() or not Routines.Checks.Map.IsExplorable() or not Map.IsVanquishable():
        return 0, 0, 0, 0.0

    foes_killed = Map.GetFoesKilled()
    foes_remaining = Map.GetFoesToKill()
    total_foes = foes_killed + foes_remaining
    progress = (foes_killed / total_foes) if total_foes > 0 else 0.0
    return foes_killed, foes_remaining, total_foes, progress


def _draw_settings():
    global experiment_label, watch_vanquish_completion

    PyImGui.text("Ferndale Settings")
    PyImGui.separator()

    PyImGui.text("Party Mode: Single Account with Heroes")
    PyImGui.text_colored("Preserves the hero party you assembled before starting.", (0.4, 1.0, 0.4, 1.0))
    PyImGui.text("Continuous mode: direct outpost travel and automatic restart")
    PyImGui.text(f"Post-VQ alliance donation: headroom <= {DONATION_HEADROOM:,}")
    PyImGui.text_colored("Loot: Uses the current Loot Filters configuration", (0.4, 1.0, 0.4, 1.0))
    experiment_label = PyImGui.input_text("Experiment label", experiment_label, 80)
    watch_vanquish_completion = PyImGui.checkbox("Stop when vanquish completes", watch_vanquish_completion)

    PyImGui.separator()
    PyImGui.text("Automation")

    auto_loot = bool(bot.Properties.Get("auto_loot", "active"))
    auto_loot = PyImGui.checkbox("Auto loot", auto_loot)
    bot.Properties.ApplyNow("auto_loot", "active", auto_loot)

    auto_inventory = bool(bot.Properties.Get("auto_inventory_management", "active"))
    auto_inventory = PyImGui.checkbox("Auto inventory management", auto_inventory)
    bot.Properties.ApplyNow("auto_inventory_management", "active", auto_inventory)

    draw_path = bool(bot.Properties.Get("draw_path", "active"))
    draw_path = PyImGui.checkbox("Draw route overlay", draw_path)
    bot.Properties.ApplyNow("draw_path", "active", draw_path)

    PyImGui.separator()
    PyImGui.text("Leader Consumables")

    use_conset = _are_all_active(CONSET_PROPERTIES)
    new_use_conset = PyImGui.checkbox("Use native Conset upkeep", use_conset)
    if new_use_conset != use_conset:
        _set_all_active(CONSET_PROPERTIES, new_use_conset)

    use_pcons = _are_all_active(PCON_PROPERTIES)
    new_use_pcons = PyImGui.checkbox("Use native PCons upkeep", use_pcons)
    if new_use_pcons != use_pcons:
        _set_all_active(PCON_PROPERTIES, new_use_pcons)

    use_war_supplies = bool(bot.Properties.Get("war_supplies", "active"))
    use_war_supplies = PyImGui.checkbox("Use War Supplies upkeep", use_war_supplies)
    bot.Properties.ApplyNow("war_supplies", "active", use_war_supplies)

    use_honeycomb = bool(bot.Properties.Get("honeycomb", "active"))
    use_honeycomb = PyImGui.checkbox("Use Honeycomb upkeep", use_honeycomb)
    bot.Properties.ApplyNow("honeycomb", "active", use_honeycomb)

    PyImGui.separator()
    PyImGui.text_wrapped("Consumable upkeep applies to this single-account hero party.")


def _format_duration(duration_ms: int) -> str:
    total_seconds = max(0, int(duration_ms) // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"




def _draw_help():
    foes_killed, foes_remaining, total_foes, progress = _get_vanquish_progress()

    PyImGui.text("Ferndale Notes")
    PyImGui.separator()
    if total_foes > 0:
        PyImGui.text(f"Vanquish progress: {foes_killed}/{total_foes} killed")
        PyImGui.progress_bar(progress, 260, 0, f"{progress * 100:.1f}%")
        PyImGui.text(f"Remaining foes: {foes_remaining}")
    else:
        PyImGui.text("Vanquish progress is available once the run is inside the explorable area.")

    PyImGui.separator()
    PyImGui.bullet_text("PrepareForFarm already wires regroup and party-danger callbacks.")
    PyImGui.bullet_text("Party wipe recovery now jumps to a stable return-to-outpost header.")
    PyImGui.bullet_text("The route still contains a known sticky segment around the fork section.")


def _vanquish_watchdog(bot: "Botting"):
    global _vq_terminal_requested
    last_remaining = None
    watchdog_started_ms = int(time.monotonic() * 1000)
    pause_started_ms = None
    while True:
        yield from Routines.Yield.wait(1000, break_on_map_transition=True)

        now_ms = int(time.monotonic() * 1000)
        if bot.config.FSM.is_operator_paused():
            if pause_started_ms is None:
                pause_started_ms = now_ms
            continue
        if pause_started_ms is not None:
            watchdog_started_ms += now_ms - pause_started_ms
            pause_started_ms = None

        if not watch_vanquish_completion:
            continue

        if (
            not Routines.Checks.Map.MapValid()
            or Map.GetMapID() != FERNDALE
            or not Routines.Checks.Map.IsExplorable()
            or not Map.IsVanquishable()
        ):
            return

        foes_killed, foes_remaining, total_foes, _ = _get_vanquish_progress()
        if foes_remaining != last_remaining and total_foes > 0:
            bot.UI.PrintMessageToConsole(
                BOT_NAME,
                f"Vanquish progress: {foes_killed}/{total_foes} killed, {foes_remaining} remaining.",
            )
            last_remaining = foes_remaining

        if Map.IsVanquishCompleted():
            bot.UI.PrintMessageToConsole(BOT_NAME, "Vanquish complete. Returning to outpost.")
            _vq_terminal_requested = True
            yield from Routines.Yield.Movement.StopMovement()
            _cancel_active_route_and_enter_post_vq(bot)
            return

        if now_ms - watchdog_started_ms >= VQ_TIMEOUT_MS:
            failure_reason = "Ferndale VQ exceeded the 45-minute route timeout"
            ConsoleLog(BOT_NAME, f"[Timeout] {failure_reason}; restarting.")
            _vq_terminal_requested = True
            yield from Routines.Yield.Movement.StopMovement()
            _cancel_active_route_and_enter_post_vq(bot)
            return


def _dead_member_recovery_watchdog(bot: "Botting"):
    global _vq_terminal_requested
    recovery_started_ms = None
    pause_started_ms = None
    while True:
        yield from Routines.Yield.wait(500, break_on_map_transition=True)
        now_ms = int(time.monotonic() * 1000)
        if bot.config.FSM.is_operator_paused():
            if pause_started_ms is None:
                pause_started_ms = now_ms
            continue
        if pause_started_ms is not None:
            if recovery_started_ms is not None:
                recovery_started_ms += now_ms - pause_started_ms
            pause_started_ms = None
        if _vq_terminal_requested:
            return
        if Map.GetMapID() != FERNDALE or not Map.IsExplorable():
            return
        dead_member_id = int(Routines.Party.GetDeadPartyMemberID() or 0)
        if dead_member_id == 0 or Routines.Checks.Agents.InDanger():
            recovery_started_ms = None
            continue
        if recovery_started_ms is None:
            recovery_started_ms = now_ms
            continue
        if now_ms - recovery_started_ms < DEAD_MEMBER_RECOVERY_TIMEOUT_MS:
            continue
        failure_reason = "party member remained dead for 60 seconds after combat"
        ConsoleLog(BOT_NAME, f"[Recovery Timeout] {failure_reason}; restarting.")
        _vq_terminal_requested = True
        yield from Routines.Yield.Movement.StopMovement()
        _cancel_active_route_and_enter_post_vq(bot)
        return


def bot_routine(bot: Botting) -> None:
    bot.Events.OnPartyWipeCallback(lambda: OnPartyWipe(bot))

    bot.States.AddHeader(BOT_NAME)
    bot.States.AddCustomState(_initialize_vanquish_attempt, "Initialize Vanquish Attempt")
    bot.States.AddCustomState(_initialize_town_stage, STAGE_TOWN_SETUP)
    bot.Templates.Aggressive()
    bot.Templates.Routines.PrepareForFarm(map_id_to_travel=HOUSE_ZU_HELZER, single_account=True)
    bot.States.AddCustomState(_prepare_trip_resources, "Prepare Gold and Conditional Alcohol")

    bot.States.AddHeader(STAGE_ENTER_AREA)
    bot.States.AddCustomState(_ensure_hard_mode_before_departure, "Require Hard Mode")
    bot.Move.XYAndExitMap(*COORDS_TO_EXIT_OUTPOST, FERNDALE)
    bot.Wait.ForTime(4000)
    bot.States.AddCustomState(_verify_explorable_hard_mode, "Verify Ferndale Hard Mode")

    bot.Move.XY(*_KURZICK_PRIEST_APPROACH_XY)
    bot.States.AddCustomState(lambda: _take_kurzick_blessing(bot), "Take Verified Kurzick Blessing")

    bot.States.AddHeader(STAGE_START_ROUTE)
    bot.UI.PrintMessageToConsole(BOT_NAME, "Starting Ferndale kill route.")
    bot.Items.UseAllConsumables()
    bot.States.AddManagedCoroutine("FerndaleVanquishWatchdog", lambda: _vanquish_watchdog(bot))
    bot.States.AddManagedCoroutine("FerndaleDeadMemberRecoveryWatchdog", lambda: _dead_member_recovery_watchdog(bot))
    for waypoint, (x, y) in enumerate(Vanquish_Path, start=1):
        bot.States.AddCustomState(
            lambda waypoint=waypoint, x=x, y=y: _follow_logged_waypoint(bot, waypoint, x, y),
            f"Ferndale route waypoint {waypoint:02d}/{len(Vanquish_Path):02d}",
        )
    bot.Wait.UntilOutOfCombat()
    bot.States.AddCustomState(_initialize_post_route, STAGE_POST_ROUTE)

    bot.States.AddHeader("Post-VQ Transaction and Restart")
    bot.States.AddCustomState(lambda: _post_vq_transition(bot), "Donate If Needed and Return to House zu Heltzer")
    if restart_after_run:
        bot.States.JumpToStepName("[H]VQ Ferndale_1")

    bot.States.AddHeader(STAGE_MANUAL_DONATION)
    bot.States.AddCustomState(lambda: _donate_kurzick_if_near_cap(bot), "Test Kurzick Alliance Donation")


def _on_party_wipe(bot: "Botting"):
    while Agent.IsDead(Player.GetAgentID()):
        yield from bot.Wait._coro_for_time(1000)
        if not Routines.Checks.Map.MapValid():
            return

    bot.config.FSM.resume()
    ConsoleLog(
        BOT_NAME,
        "Party resurrected. Route remains paused for inspection; choose a waypoint if needed, then Continue.",
    )
    return True


def OnPartyWipe(bot: "Botting"):
    ConsoleLog(BOT_NAME, "Party wipe detected. Pausing at the interrupted route step for inspection.")
    fsm = bot.config.FSM
    fsm.pause()
    fsm.pause_by_operator()
    fsm.AddManagedCoroutine("FerndaleOnWipe", lambda: _on_party_wipe(bot))


bot.SetMainRoutine(bot_routine)
bot.UI.override_draw_config(_draw_settings)
bot.UI.override_draw_help(_draw_help)


def configure():
    bot.UI.draw_configure_window()


def main():
    global _operator_pause_recorded
    if not Routines.Checks.Map.MapValid():
        return
    try:
        operator_paused = bot.config.FSM.is_operator_paused()
        if operator_paused and not _operator_pause_recorded:
            pass
        _operator_pause_recorded = operator_paused
        bot.Update()
    except Exception as error:
        raise
    bot.UI.draw_window(icon_path=TEXTURE, extra_tabs=[])


if __name__ == "__main__":
    main()
