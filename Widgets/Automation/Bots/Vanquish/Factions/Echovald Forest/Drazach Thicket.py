import PySystem
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Py4GWCoreLib import UIManager
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib import Agent, AgentArray, Botting, ConsoleLog, Effects, GLOBAL_CACHE, Map, ModelID, Player, Range, Routines, SharedCommandType, Utils
from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters import LootFilters
from Py4GWCoreLib.py4gwcorelib_src.AutoInventoryHandler import AutoInventoryHandler
from Py4GWCoreLib.enums_src.Title_enums import TitleID
from Sources.aC_Scripts.aC_api.Verify_Blessing import Blessings
from Sources.dt_route_archive import DT_BETTER_4_ROUTE_89, DT_ENDPOINT_TO_MISSING_GUY_ROUTE
import Py4GW
import PyImGui
import math
import os
import time

BOT_NAME = "VQ Drazach Thicket"
MODULE_NAME = "Drazach Thicket (Vanquish)"
MODULE_ICON = "Textures\\Module_Icons\\Vanquish - Drazach Thicket.png"
TEXTURE = os.path.join(PySystem.Console.get_projects_path(), "Sources", "ApoSource", "textures", "VQ_Helmet.png")
OUTPOST_TO_START = 222
EXPLORABLE_TO_VANQUISH = 195
HOUSE_ZU_HELZER = 77
COORDS_TO_EXIT_OUTPOST = (-7544.00, 14343.00)
COORDS_FOR_PRIEST = (-5592.00, -16263.00)
DIALOG_FOR_PRIEST = 0x86

STAGE_TOWN_SETUP = "Stage 1 Init - Town Setup"
STAGE_ENTER_DRAZACH = "Stage 2 Init - Enter Drazach Thicket"
STAGE_MANUAL_BLESSING = "Stage 3 Init - Manual Bribe or Blessing"
STAGE_START_ROUTE = "Stage 4 Init - Start Vanquish Route"
STAGE_POST_ROUTE = "Stage 5 Init - Post Route"
STAGE_MANUAL_DONATION = "Stage 6 Init - Manual Donation Capture"

_KURZICK_PRIEST_MODEL_ID = 3477
_KURZICK_PRIEST_CAPTURE_IDS = (
    "NPC-20260813-091437-434",
    "NPC-20260813-084431-508",
)
_KURZICK_PRIEST_APPROACH_XY = (-5633.44, -16283.08)
_HOUSE_DONATION_NPC_MODEL_ID = 3465
_HOUSE_DONATION_NPC_TARGET_XY = (5336.0, 1468.0)
_HOUSE_DONATION_APPROACH_XY = (5306.78, 1543.68)
_HOUSE_DONATION_CAPTURE_ID = "NPC-20260813-091734-598"
_AMBER_REDEMPTION_CAPTURE_IDS = (
    "NPC-20260816-185832-874",
    "NPC-20260816-190317-376",
)
_AMBER_REDEMPTION_MAX_VISIBLE_BUTTONS = (1, 2)

RETURN_TO_OUTPOST_HEADER = STAGE_POST_ROUTE

restart_after_run = True
donate_after_run = True
watch_vanquish_completion = True
DONATION_HEADROOM = 24_000
DONATION_CHUNK = 5_000
KURZICK_TITLE_CAP = 10_000_000
DT_VQ_TIMEOUT_MS = 32 * 60 * 1000
DEAD_MEMBER_RECOVERY_TIMEOUT_MS = 60 * 1000
_CARRIED_GOLD_TARGET = 1_000
_BLESSING_GOLD_REQUIRED = 100
_ALCOHOL_RESTOCK_TARGET = 50
_ALCOHOL_MODEL_IDS = (
    int(ModelID.Dwarven_Ale.value),
    int(ModelID.Hunters_Ale.value),
    int(ModelID.Bottle_Of_Rice_Wine.value),
    int(ModelID.Bottle_Of_Vabbian_Wine.value),
    int(ModelID.Bottle_Of_Juniberry_Gin.value),
    int(ModelID.Shamrock_Ale.value),
    int(ModelID.Hard_Apple_Cider.value),
    int(ModelID.Eggnog.value),
    int(ModelID.Aged_Dwarven_Ale.value),
    int(ModelID.Aged_Hunters_Ale.value),
    int(ModelID.Keg_Of_Aged_Hunters_Ale.value),
    int(ModelID.Bottle_Of_Grog.value),
    int(ModelID.Spiked_Eggnog.value),
    int(ModelID.Vial_Of_Absinthe.value),
    int(ModelID.Witchs_Brew.value),
)

_commissioning_stage = "Normal start"
_manual_blessing_waiting = False
experiment_label = "DT baseline"
_vq_terminal_requested = False
_vq_terminal_reason = ""
_BETTER_4_DIRECT_WAYPOINTS = frozenset(range(2, 21))

Vanquish_Path: list[tuple[float, float]] = list(DT_BETTER_4_ROUTE_89)

FOLLOWER_CONSUMABLES: tuple[tuple[str, int, str], ...] = (
    ("essence_of_celerity", ModelID.Essence_Of_Celerity.value, "Essence_of_Celerity_item_effect"),
    ("grail_of_might", ModelID.Grail_Of_Might.value, "Grail_of_Might_item_effect"),
    ("armor_of_salvation", ModelID.Armor_Of_Salvation.value, "Armor_of_Salvation_item_effect"),
    ("birthday_cupcake", ModelID.Birthday_Cupcake.value, "Birthday_Cupcake_skill"),
    ("golden_egg", ModelID.Golden_Egg.value, "Golden_Egg_skill"),
    ("candy_corn", ModelID.Candy_Corn.value, "Candy_Corn_skill"),
    ("candy_apple", ModelID.Candy_Apple.value, "Candy_Apple_skill"),
    ("slice_of_pumpkin_pie", ModelID.Slice_Of_Pumpkin_Pie.value, "Pie_Induced_Ecstasy"),
    ("drake_kabob", ModelID.Drake_Kabob.value, "Drake_Skin"),
    ("bowl_of_skalefin_soup", ModelID.Bowl_Of_Skalefin_Soup.value, "Skale_Vigor"),
    ("pahnai_salad", ModelID.Pahnai_Salad.value, "Pahnai_Salad_item_effect"),
    ("war_supplies", ModelID.War_Supplies.value, "Well_Supplied"),
)

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

bot = Botting(BOT_NAME, upkeep_hero_ai_active=True, upkeep_auto_loot_active=True)







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


def _stage_requires_drazach(stage_name: str) -> bool:
    return stage_name in {
        STAGE_MANUAL_BLESSING,
        STAGE_START_ROUTE,
        STAGE_POST_ROUTE,
    }


def _request_stage(stage_name: str) -> None:
    global _commissioning_stage

    if _stage_requires_drazach(stage_name) and Map.GetMapID() != EXPLORABLE_TO_VANQUISH:
        ConsoleLog(BOT_NAME, "That stage requires the character to already be inside Drazach Thicket.")
        return
    if stage_name == STAGE_ENTER_DRAZACH and Map.GetMapID() != OUTPOST_TO_START:
        ConsoleLog(BOT_NAME, "Enter-DT stage requires The Eternal Grove. Use Town Setup first.")
        return
    if stage_name == STAGE_START_ROUTE:
        if not Map.IsVanquishable():
            ConsoleLog(BOT_NAME, "The loaded Drazach Thicket instance is not vanquishable; route start refused.")
            return
        if not _kurzick_blessing_active():
            ConsoleLog(BOT_NAME, "Kurzick blessing is not active; route start refused.")
            return


    if stage_name != STAGE_MANUAL_DONATION:
        pass

    _commissioning_stage = stage_name
    bot.StartAtStep(stage_name)


def _initialize_stage(stage_name: str):
    global _commissioning_stage

    _commissioning_stage = stage_name
    combat_ready = stage_name in {STAGE_START_ROUTE, STAGE_POST_ROUTE}
    bot.ResetHeroAICombatState(
        active=True,
        following=True,
        avoidance=True,
        looting=combat_ready,
        targeting=combat_ready,
        combat=combat_ready,
        skills=combat_ready,
    )


    if _stage_requires_drazach(stage_name):
        if Map.GetMapID() != EXPLORABLE_TO_VANQUISH:
            raise RuntimeError(f"{stage_name} requires Drazach Thicket")
        if not Map.IsVanquishable():
            raise RuntimeError("Drazach Thicket is not a Hard Mode vanquishable instance")

    if stage_name == STAGE_START_ROUTE and not _kurzick_blessing_active():
        raise RuntimeError("Kurzick blessing is required before starting the route")

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
    raise RuntimeError("Hard Mode could not be confirmed in The Eternal Grove")


def _normalize_carried_gold():
    """Keep exactly enough carried gold for the Kurzick priest blessing."""
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
                f"[Trip Reset] Could not confirm exactly {_CARRIED_GOLD_TARGET:,} gold after 5 seconds "
                f"(current reading {carried:,}), but the blessing is funded; continuing.",
            )
            return True

        ConsoleLog(
            BOT_NAME,
            f"[Trip Reset] Only {carried:,} carried gold; at least {_BLESSING_GOLD_REQUIRED:,} is required. "
            "Remaining in town and retrying in 10 seconds.",
        )
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
    alcohol_count = _carried_alcohol_count()
    if alcohol_count <= 0:
        raise RuntimeError("Drunken Master is equipped, but no supported alcohol was found in storage")
    ConsoleLog(BOT_NAME, f"[Trip Reset] Withdrew {alcohol_count} alcohol uses for Drunken Master.")
    return True


def _prepare_trip_resources():
    if not (yield from _normalize_carried_gold()):
        return False
    yield from _ensure_trip_alcohol()
    return True


def _verify_drazach_hard_mode():
    for _ in range(20):
        if Map.GetMapID() == EXPLORABLE_TO_VANQUISH and Map.IsVanquishable():
            ConsoleLog(BOT_NAME, "Drazach Thicket Hard Mode instance confirmed.")
            return True
        yield from Routines.Yield.wait(250)
    raise RuntimeError("Drazach Thicket is not vanquishable; return to The Eternal Grove and retry")


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
    opened = yield from _open_kurzick_donation_npc(bot)
    if not opened:
        return False, "Kurzick Bureaucrat interaction failed"

    current, _, _ = Player.GetKurzickData()
    previous = int(current)
    donated = 0
    while previous >= DONATION_CHUNK:
        Player.DepositFaction(0)  # Kurzick, alliance donation only.
        yield from Routines.Yield.wait(750)
        current, _, _ = Player.GetKurzickData()
        current = int(current)
        if current >= previous:
            return False, f"Kurzick faction did not decrease after donation request ({previous:,})"
        donated += previous - current
        previous = current

    if donated <= 0:
        return False, "No Kurzick faction was available in a complete 5,000-point chunk"
    ConsoleLog(BOT_NAME, f"[Donation] Donated {donated:,} Kurzick faction to the alliance.")
    return True, ""


def _redeem_kurzick_faction_for_amber(bot: "Botting"):
    faction_before, _, _ = Player.GetKurzickData()
    faction_before = int(faction_before)
    amber_before = int(GLOBAL_CACHE.Inventory.GetModelCount(ModelID.Amber_Chunk) or 0)
    if faction_before < DONATION_CHUNK:
        return False, f"Only {faction_before:,} Kurzick faction is available"

    chunks_expected = faction_before // DONATION_CHUNK
    faction_expected = chunks_expected * DONATION_CHUNK

    def redemption_verified(_postcondition) -> bool:
        faction_after, _, _ = Player.GetKurzickData()
        amber_after = int(GLOBAL_CACHE.Inventory.GetModelCount(ModelID.Amber_Chunk) or 0)
        return bool(
            int(faction_after) == faction_before - faction_expected
            and amber_after == amber_before + chunks_expected
        )

    # Captured UIManager choices are 1-based; the canonical owner uses 0-based positions.
    tree = BT.MoveAndAutoDialog(
        pos=_HOUSE_DONATION_NPC_TARGET_XY,
        buttons=[choice - 1 for choice in _AMBER_REDEMPTION_MAX_VISIBLE_BUTTONS],
        multi_account=False,
        log=True,
    )
    success = yield from _run_owner_tree(bot, tree)
    if success:
        for _ in range(20):
            if redemption_verified(None):
                break
            yield from Routines.Yield.wait(250)
        else:
            success = False
    if not success:
        return False, "House zu Heltzer Amber exchange was not verified"

    faction_after, _, _ = Player.GetKurzickData()
    faction_after = int(faction_after)
    amber_after = int(GLOBAL_CACHE.Inventory.GetModelCount(ModelID.Amber_Chunk) or 0)
    ConsoleLog(
        BOT_NAME,
        (
            f"[Amber Redemption] Exchanged {faction_before - faction_after:,} Kurzick faction "
            f"for {amber_after - amber_before:,} Amber Chunk(s)."
        ),
    )
    return True, ""


def _stage_donation_validation(bot: "Botting"):
    bot.ResetHeroAICombatState(
        active=False,
        following=False,
        avoidance=False,
        looting=False,
        targeting=False,
        combat=False,
        skills=False,
    )
    if Map.GetMapID() != HOUSE_ZU_HELZER:
        yield from bot.Map._coro_travel(HOUSE_ZU_HELZER, "")
    success, reason = yield from _donate_all_available_kurzick(bot)
    if success:
        ConsoleLog(BOT_NAME, "Kurzick alliance-donation validation succeeded. Widget stopped.")
    else:
        ConsoleLog(BOT_NAME, f"Kurzick alliance-donation validation failed: {reason}")
    bot.Stop()
    yield


def _stop_after_commissioning_run():
    ConsoleLog(
        BOT_NAME,
        "Commissioning run saved. Widget stopped before donation; use stage 6 when ready to capture it.",
    )
    bot.Stop()
    yield


def _donate_kurzick_if_near_cap(bot: "Botting"):
    current, _, maximum = Player.GetKurzickData()
    current = int(current)
    maximum = int(maximum)
    if maximum > 0 and maximum - current > DONATION_HEADROOM:
        return True
    success, reason = yield from _donate_all_available_kurzick(bot)
    if not success:
        raise RuntimeError(reason)
    return True


def _post_vq_transition(bot: "Botting"):
    """Finish the VQ transaction, then return directly to the starting outpost."""
    fully_vanquished = bool(Map.IsVanquishCompleted())
    if fully_vanquished:
        yield from _drain_post_vq_loot()
    current, _, maximum = Player.GetKurzickData()
    current = int(current)
    maximum = int(maximum)
    headroom = max(0, maximum - current)
    title = Player.GetTitle(TitleID.Kurzick)
    title_points = int(title.current_points if title else 0)
    title_is_maxed = title_points >= KURZICK_TITLE_CAP

    should_spend = bool(
        fully_vanquished
        and donate_after_run
        and current >= DONATION_CHUNK
        and headroom <= DONATION_HEADROOM
    )
    if should_spend:
        redeem_amber = bool(title_is_maxed)
        transaction_target = "other" if redeem_amber else "alliance"
        transaction_label = "Amber redemption" if redeem_amber else "alliance donation"
        yield from bot.Map._coro_travel(HOUSE_ZU_HELZER, "")
        if redeem_amber:
            success, reason = yield from _redeem_kurzick_faction_for_amber(bot)
        else:
            success, reason = yield from _donate_all_available_kurzick(bot)
        if not success:
            # Donation is a post-VQ transaction. Its failure must be retained in
            # the benchmark donation fields, but it must neither rewrite a
            # successful vanquish as a failed run nor stop the AFK loop.
            ConsoleLog(
                BOT_NAME,
                f"[Faction] Post-VQ {transaction_label} failed: {reason}; returning to Eternal Grove and retrying after the next VQ.",
            )
    else:
        reason = (
            "vanquish was not confirmed"
            if not fully_vanquished
            else f"faction headroom is {headroom:,}"
        )
        ConsoleLog(BOT_NAME, f"[Donation] No post-VQ donation needed: {reason}.")

    if Map.GetMapID() != OUTPOST_TO_START:
        yield from bot.Map._coro_travel(OUTPOST_TO_START, "")
    yield from _prepare_trip_resources()
    return True


def _drain_post_vq_loot():
    """Wait only when wanted earshot loot remains, with a hard bounded timeout."""
    # The vanquish flag can arrive one or more frames before the final foe's
    # ground drop is visible to the item array. Give that drop a short chance
    # to materialize, then wait only for loot selected by the active profile.
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

    PyImGui.text("Drazach Thicket Settings")
    PyImGui.separator()

    PyImGui.text("Party Mode: Single Account with Heroes")
    PyImGui.text_colored("Preserves the hero party you assembled before starting.", (0.4, 1.0, 0.4, 1.0))
    PyImGui.text("Continuous mode: direct outpost travel and automatic restart")
    PyImGui.text(f"Post-VQ alliance donation: headroom <= {DONATION_HEADROOM:,}")
    PyImGui.text("At max Kurzick title: redeem maximum faction for Amber Chunks")
    PyImGui.text_colored("Loot: Uses the current Loot Filters configuration", (0.4, 1.0, 0.4, 1.0))
    experiment_label = PyImGui.input_text("Experiment label", experiment_label, 80)
    watch_vanquish_completion = PyImGui.checkbox("Stop when vanquish completes", watch_vanquish_completion)

    PyImGui.separator()
    PyImGui.text("Commissioning Stages")
    PyImGui.text_wrapped(
        "Stage jumps reset HeroAI safely. Any jumped run is marked manual/test so it cannot affect autonomous averages."
    )
    if PyImGui.button("1. Town setup"):
        _request_stage(STAGE_TOWN_SETUP)
    if PyImGui.button("2. Enter DT (from Eternal Grove)"):
        _request_stage(STAGE_ENTER_DRAZACH)
    if PyImGui.button("3. Wait for manual bribe/blessing"):
        _request_stage(STAGE_MANUAL_BLESSING)
    if PyImGui.button("4. Start route (blessing required)"):
        _request_stage(STAGE_START_ROUTE)
    if PyImGui.button("5. Post-route finalize"):
        _request_stage(STAGE_POST_ROUTE)
    if PyImGui.button("6. Test Kurzick alliance donation now"):
        _request_stage(STAGE_MANUAL_DONATION)
    if PyImGui.button("7. Restart after manual donation"):
        _request_stage(STAGE_TOWN_SETUP)
    PyImGui.text_wrapped(f"Current stage: {_commissioning_stage}")
    if _manual_blessing_waiting:
        PyImGui.text_colored("Taking and verifying the Kurzick blessing...", (1.0, 0.8, 0.2, 1.0))

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
    PyImGui.text_wrapped(
        "Leader upkeep now uses native Botting properties. Followers stay synced through shared-memory consumable messages."
    )


def _draw_help():
    foes_killed, foes_remaining, total_foes, progress = _get_vanquish_progress()

    PyImGui.text("Drazach Thicket Notes")
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
    PyImGui.bullet_text("The indoor path has several ambush rooms and pop-up groups.")


def _format_duration(duration_ms: int) -> str:
    total_seconds = max(0, int(duration_ms) // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"




def _send_consumable_to_followers(model_id: int, skill_name: str):
    skill_id = GLOBAL_CACHE.Skill.GetID(skill_name)
    if skill_id == 0:
        ConsoleLog(BOT_NAME, f"Unable to resolve consumable effect for {skill_name}")
        yield
        return

    sender_email = Player.GetAccountEmail()
    accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    for account in accounts:
        if account.AccountEmail == sender_email:
            continue

        GLOBAL_CACHE.ShMem.SendMessage(
            sender_email,
            account.AccountEmail,
            SharedCommandType.PCon,
            (model_id, skill_id, 0, 0),
        )
    yield from Routines.Yield.wait(250)


def _upkeep_multibox_consumables(bot: "Botting"):
    while True:
        if Routines.Checks.Map.MapValid() and Routines.Checks.Map.IsExplorable():
            for property_name, model_id, skill_name in FOLLOWER_CONSUMABLES:
                if bot.Properties.IsActive(property_name):
                    yield from _send_consumable_to_followers(model_id, skill_name)

        yield from bot.Wait._coro_for_time(15000)


def _vanquish_watchdog(bot: "Botting"):
    global _vq_terminal_requested, _vq_terminal_reason
    last_remaining = None
    watchdog_started_ms = int(time.monotonic() * 1000)
    while True:
        yield from Routines.Yield.wait(1000, break_on_map_transition=True)

        if not watch_vanquish_completion:
            continue

        # This watchdog belongs only to the DT instance in which it was
        # started.  Keeping it alive through the return to town lets its old
        # monotonic start time resume in the next run, causing that attempt to
        # inherit the previous attempt's elapsed time.
        if (
            not Routines.Checks.Map.MapValid()
            or Map.GetMapID() != EXPLORABLE_TO_VANQUISH
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
            # Do not jump the FSM from this managed coroutine. A direct jump
            # leaves the active route state's generator alive; it can resume in
            # House zu Heltzer and execute stale waypoints. Signal the route to
            # unwind cooperatively instead.
            _vq_terminal_requested = True
            _vq_terminal_reason = "vanquish_complete"
            yield from Routines.Yield.Movement.StopMovement()
            _cancel_active_route_and_enter_post_vq(bot)
            return

        if int(time.monotonic() * 1000) - watchdog_started_ms >= DT_VQ_TIMEOUT_MS:
            failure_reason = "Drazach Thicket VQ exceeded the 32-minute route timeout"
            ConsoleLog(BOT_NAME, f"[Timeout] {failure_reason}; restarting.")
            _vq_terminal_requested = True
            _vq_terminal_reason = "timeout"
            yield from Routines.Yield.Movement.StopMovement()
            _cancel_active_route_and_enter_post_vq(bot)
            return


def _dead_member_recovery_watchdog(bot: "Botting"):
    """Restart DT after one combat-free minute with a party member still dead."""
    global _vq_terminal_requested, _vq_terminal_reason
    recovery_started_ms = None
    while True:
        yield from Routines.Yield.wait(500, break_on_map_transition=True)
        if _vq_terminal_requested:
            return
        if Map.GetMapID() != EXPLORABLE_TO_VANQUISH or not Map.IsExplorable():
            return

        dead_member_id = int(Routines.Party.GetDeadPartyMemberID() or 0)
        if dead_member_id == 0 or Routines.Checks.Agents.InDanger():
            recovery_started_ms = None
            continue

        now_ms = int(time.monotonic() * 1000)
        if recovery_started_ms is None:
            recovery_started_ms = now_ms
            continue
        if now_ms - recovery_started_ms < DEAD_MEMBER_RECOVERY_TIMEOUT_MS:
            continue

        failure_reason = "party member remained dead for 60 seconds after combat"
        ConsoleLog(BOT_NAME, f"[Recovery Timeout] {failure_reason}; restarting.")
        _vq_terminal_requested = True
        _vq_terminal_reason = "dead_member_recovery_timeout"
        yield from Routines.Yield.Movement.StopMovement()
        _cancel_active_route_and_enter_post_vq(bot)
        return


def _cancel_active_route_and_enter_post_vq(bot: "Botting") -> None:
    """Cancel the active yield-state generator before entering post-VQ work.

    Yield-based custom states are registered in GLOBAL_CACHE.Coroutines. Merely
    changing ``FSM.current_state`` does not detach that generator, which is why
    stale route waypoints previously continued after travel. Resetting the
    active state first invokes YieldRoutineState.reset(), removing its generator
    from the scheduler before the post-VQ state is entered.
    """
    bot.config.FSM.jump_to_state_by_name(RETURN_TO_OUTPOST_HEADER, cancel_current_state=True)
    bot.config.FSM.resume()




def _nearest_route_waypoint(xy: tuple[float, float]) -> int:
    return min(
        range(len(Vanquish_Path)),
        key=lambda index: math.dist(xy, Vanquish_Path[index]),
    ) + 1








def _follow_logged_route_segment(
    bot: "Botting",
    segment: list[tuple[float, float]],
    first_waypoint: int,
    fixed_checkpoint_after_segment: bool,
):
    """Use the same autopath primitives while logging every completed target."""
    if _vq_terminal_requested:
        return True
    for offset, (x, y) in enumerate(segment):
        if _vq_terminal_requested:
            return True
        waypoint = first_waypoint + offset
        if waypoint in _BETTER_4_DIRECT_WAYPOINTS:
            ConsoleLog(
                BOT_NAME,
                f"[Route] Following Better 4 direct waypoint {waypoint}/{len(Vanquish_Path)} "
                f"at ({x:.0f}, {y:.0f}).",
            )
            yield from bot.Move._coro_follow_path([(x, y)])
        else:
            yield from bot.Move._coro_get_path_to(x, y)
            if _vq_terminal_requested:
                return True
            yield from bot.Move._coro_follow_path_to()
        if _vq_terminal_requested:
            return True
        ConsoleLog(
            BOT_NAME,
            f"[Route] Reached waypoint {waypoint}/{len(Vanquish_Path)} at ({x:.0f}, {y:.0f}).",
        )
        # A fixed checkpoint immediately following this segment already forces
        # setup. Avoid issuing a duplicate conditional setup at the same stop.
        is_segment_end = offset == len(segment) - 1
    return True


def _targeted_missing_patrol_cleanup(bot: "Botting"):
    """Check the three supervised patrol locations once, then fail fast."""
    if (
        _vq_terminal_requested
        or Map.IsVanquishCompleted()
        or Map.GetMapID() != EXPLORABLE_TO_VANQUISH
        or not Map.IsExplorable()
    ):
        return True

    ConsoleLog(
        BOT_NAME,
        "[Cleanup] Main route ended incomplete; checking Check here 1, "
        "Check here 2, and Missing Guy once.",
    )
    cleanup_result = "exhausted"
    try:
        # This is a dense, manually walked route. Follow its recorded geometry
        # directly rather than letting autopath collapse it into another path.
        yield from bot.Move._coro_set_path_to(list(DT_ENDPOINT_TO_MISSING_GUY_ROUTE))
        movement_succeeded = yield from bot.Move._coro_follow_path_to(
            autopath=False,
            fail_on_unmanaged=False,
        )
        if _vq_terminal_requested or Map.IsVanquishCompleted():
            cleanup_result = "vanquish_confirmed"
            return True
        if not movement_succeeded:
            cleanup_result = "movement_failed"
            ConsoleLog(
                BOT_NAME,
                "[Cleanup] Could not finish the targeted patrol route; "
                "recording failure and restarting.",
            )
            return True
        ConsoleLog(
            BOT_NAME,
            "[Cleanup] Targeted missing-patrol route exhausted without vanquish; "
            "recording failure and restarting.",
        )
        return True
    finally:
        pass


def _initialize_vanquish_attempt():
    """Reset per-attempt terminal coordination."""
    global _vq_terminal_requested, _vq_terminal_reason
    _vq_terminal_requested = False
    _vq_terminal_reason = ""
    yield


def bot_routine(bot: Botting) -> None:
    bot.Events.OnPartyWipeCallback(lambda: OnPartyWipe(bot))

    bot.States.AddHeader(BOT_NAME)
    bot.States.AddCustomState(_initialize_vanquish_attempt, "Initialize Vanquish Attempt")
    bot.States.AddCustomState(lambda: _initialize_stage(STAGE_TOWN_SETUP), STAGE_TOWN_SETUP)
    bot.Templates.Aggressive()
    bot.Templates.Routines.PrepareForFarm(map_id_to_travel=OUTPOST_TO_START, single_account=True)
    bot.States.AddCustomState(_prepare_trip_resources, "Prepare Gold and Conditional Alcohol")

    bot.States.AddCustomState(lambda: _initialize_stage(STAGE_ENTER_DRAZACH), STAGE_ENTER_DRAZACH)
    bot.States.AddCustomState(_ensure_hard_mode_before_departure, "Require Hard Mode")
    bot.Move.XYAndExitMap(*COORDS_TO_EXIT_OUTPOST, EXPLORABLE_TO_VANQUISH)
    bot.Wait.ForTime(4000)
    bot.States.AddCustomState(_verify_drazach_hard_mode, "Verify Drazach Thicket Hard Mode")

    bot.States.AddCustomState(lambda: _initialize_stage(STAGE_MANUAL_BLESSING), STAGE_MANUAL_BLESSING)
    bot.Move.XY(*_KURZICK_PRIEST_APPROACH_XY)
    bot.States.AddCustomState(lambda: _take_kurzick_blessing(bot), "Take Verified Kurzick Blessing")

    bot.States.AddCustomState(lambda: _initialize_stage(STAGE_START_ROUTE), STAGE_START_ROUTE)
    bot.UI.PrintMessageToConsole(BOT_NAME, "Starting Drazach Thicket kill route.")
    bot.Items.UseAllConsumables()
    bot.States.AddManagedCoroutine("DrazachVanquishWatchdog", lambda: _vanquish_watchdog(bot))
    bot.States.AddManagedCoroutine(
        "DrazachDeadMemberRecoveryWatchdog",
        lambda: _dead_member_recovery_watchdog(bot),
    )
    bot.States.AddCustomState(
        lambda: _follow_logged_route_segment(bot, Vanquish_Path, 1, False),
        "Follow the captured kill route",
    )
    bot.States.AddCustomState(
        lambda: _targeted_missing_patrol_cleanup(bot),
        "Targeted Missing Patrol Cleanup",
    )
    bot.States.AddCustomState(lambda: _initialize_stage(STAGE_POST_ROUTE), STAGE_POST_ROUTE)

    bot.States.AddHeader("Post-VQ Transaction and Restart")
    bot.States.AddCustomState(lambda: _post_vq_transition(bot), "Donate If Needed and Return to Eternal Grove")

    if restart_after_run:
        bot.States.JumpToStepName("[H]VQ Drazach Thicket_1")

    bot.States.AddCustomState(_stop_after_commissioning_run, "Stop After Commissioning Run")
    bot.States.AddCustomState(lambda: _initialize_stage(STAGE_MANUAL_DONATION), STAGE_MANUAL_DONATION)
    bot.States.AddCustomState(lambda: _stage_donation_validation(bot), "Validate Kurzick Alliance Donation")


def _on_party_wipe(bot: "Botting"):
    while Agent.IsDead(Player.GetAgentID()):
        yield from bot.Wait._coro_for_time(1000)
        if not Routines.Checks.Map.MapValid():
            bot.config.FSM.resume()
            return

    yield from Routines.Yield.Movement.StopMovement()
    _cancel_active_route_and_enter_post_vq(bot)


def OnPartyWipe(bot: "Botting"):
    global _vq_terminal_requested, _vq_terminal_reason
    ConsoleLog(BOT_NAME, "Party wipe detected. Returning to outpost.")
    _vq_terminal_requested = True
    _vq_terminal_reason = "party_wipe"
    fsm = bot.config.FSM
    fsm.pause()
    fsm.AddManagedCoroutine("DrazachOnWipe", lambda: _on_party_wipe(bot))


bot.SetMainRoutine(bot_routine)
bot.UI.override_draw_config(_draw_settings)
bot.UI.override_draw_help(_draw_help)


def configure():
    bot.UI.draw_configure_window()


def main():
    if not Routines.Checks.Map.MapValid():
        return
    try:
        bot.Update()
    except Exception as error:
        raise
    bot.UI.draw_window(icon_path=TEXTURE, extra_tabs=[])


if __name__ == "__main__":
    main()
