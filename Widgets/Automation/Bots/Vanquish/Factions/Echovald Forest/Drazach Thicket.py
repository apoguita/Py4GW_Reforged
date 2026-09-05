from Py4GWCoreLib import Agent, Botting, ConsoleLog, GLOBAL_CACHE, Map, ModelID, Player, Routines, SharedCommandType
import Py4GW
import PyImGui
import os
import time

BOT_NAME = "VQ Drazach Thicket"
MODULE_NAME = "Drazach Thicket (Vanquish)"
MODULE_ICON = "Assets\\Textures\\Module_Icons\\Vanquish - Drazach Thicket.png"
TEXTURE = os.path.join(PySystem.Console.get_projects_path(), "Sources", "ApoSource", "textures", "VQ_Helmet.png")
OUTPOST_TO_START = 222
EXPLORABLE_TO_VANQUISH = 195
HOUSE_ZU_HELZER = 77
COORDS_TO_EXIT_OUTPOST = (-7544.00, 14343.00)
COORDS_FOR_PRIEST = (-5592.00, -16263.00)
DIALOG_FOR_PRIEST = 0x86

RETURN_TO_OUTPOST_HEADER = "[H]Return to Outpost_4"

restart_after_run = True
donate_after_run = True
watch_vanquish_completion = True

Vanquish_Path: list[tuple[float, float]] = [
    (-9878.31, -14870.55),
    (-7874.59, -12949.60),
    (-7379.29, -12844.72),
    (-6942.61, -12597.86),
    (-6440.81, -12602.38),
    (-5951.63, -12475.38),
    (-5626.20, -12093.91),
    (-5227.94, -11786.53),
    (-4916.42, -11392.90),
    (-4986.59, -10894.21),
    (-4931.71, -10391.40),
    (-4907.02, -10195.30),
    (-4993.83, -9123.04),
    (-5464.51, -8944.35),
    (-5967.93, -8966.51),
    (-6467.51, -9020.68),
    (-6972.30, -9044.26),
    (-7445.42, -9222.97),
    (-7914.38, -9414.95),
    (-7893.66, -9408.40),
    (-5651.87, -6857.37),
    (-6603.41, -5635.55),
    (-11049.86, -6165.82),
    (-11573.19, -8327.89),
    (-10875.07, -5594.80),
    (-10516.25, -2471.60),
    (-9792.65, -536.86),
    (-11308.45, 3273.95),
    (-12730.60, 5712.96),
    (-7237.03, -2142.75),
    (-7105.36, -2426.90),
    (-4554.99, 776.04),
    (-1223.03, 2129.13),
    (-1896.83, 5606.69),
    (-1813.93, -2020.71),
    (-5234.42, -5652.45),
    (211.23, -5091.44),
    (1371.50, -4038.61),
    (3255.87, -4785.59),
    (1558.04, -6938.50),
    (668.36, -9314.83),
    (2366.87, -9547.91),
    (5625.59, -1360.20),
    (4755.49, 821.61),
    (7637.67, 565.40),
    (11031.07, 283.33),
    (10185.84, 2583.37),
    (10202.87, 4548.36),
    (13189.10, 7118.12),
    (10702.87, 5053.48),
    (6305.87, 6799.13),
    (4122.42, 9260.20),
    (3198.79, 10451.46),
    (899.70, 9569.84),
    (2022.75, 10394.34),
    (3396.14, 12257.46),
    (4639.69, 14749.79),
    (6719.38, 15829.74),
    (6489.15, 13063.95),
    (6832.31, 13080.34),
    (8752.42, 11218.01),
    (8246.33, 10203.75),
    (5060.11, 13990.69),
    (3068.08, 14908.65),
    (1663.85, 15372.74),
    (-421.20, 14979.13),
    (-1663.88, 15761.81),
    (-5233.40, 16057.40),
    (-5659.13, 14103.66),
    (-4495.78, 11975.85),
    (-6285.88, 10078.19),
    (-6744.33, 10162.74),
    (-5599.93, 7608.96),
    (-4347.67, 10302.46),
    (-3198.28, 8701.55),
    (-2725.50, 10116.74),
    (-1241.02, 10314.69),
    (-339.24, 8950.46),
    (-2500.23, 7782.04),
    (-4301.04, 5627.14),
    (-6121.91, 4770.20),
    (-5411.09, 6461.05),
    (-5713.13, 8684.84),
    (-7201.17, 9957.66),
    (-7640.64, 12424.33),
    (-10422.90, 10846.65),
    (-12227.19, 7684.96),
    (-12730.60, 5712.96),
    (-10030.67, 4909.71),
]

# A recurring Mantis/Warden patrol can survive its ambient fight and remain
# outside the main route.  Check its three observed positions once, and only
# when the game still reports that the vanquish is incomplete.
MISSING_PATROL_PATH: list[tuple[float, float]] = [
    (-10030.67, 4909.71),
    (-10849.57, 5369.38),
    (-11057.16, 5829.86),
    (-11286.33, 6279.81),
    (-11514.69, 6731.75),
    (-11686.50, 7205.40),
    (-11807.85, 7694.65),
    (-11956.89, 8178.29),
    (-11867.57, 8673.13),
    (-11606.11, 9099.63),
    (-11287.66, 9497.10),
    (-10965.09, 9887.44),
    (-10626.26, 10258.10),
    (-10151.50, 10434.89),
    (-9660.21, 10557.10),
    (-9160.87, 10592.38),
    (-8669.52, 10491.09),
    (-8173.67, 10381.79),
    (-7676.08, 10311.79),
    (-7206.60, 10124.95),
    (-6780.98, 9851.54),
    (-6303.30, 9681.65),
    (-5842.00, 9875.66),
    (-5415.83, 10138.90),
    (-5010.40, 10439.26),
    (-5180.60, 9967.77),
    (-5424.18, 9524.41),
    (-5475.63, 9021.24),
    (-5547.90, 8521.96),
    (-5500.79, 8013.02),
    (-5420.45, 7516.59),
    (-5351.81, 7087.68),
    (-6178.83, 7446.46),
]

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

bot = Botting(
    BOT_NAME,
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


def _are_all_active(property_names: tuple[str, ...]) -> bool:
    return all(bool(bot.Properties.Get(name, "active")) for name in property_names)


def _set_all_active(property_names: tuple[str, ...], active: bool) -> None:
    for property_name in property_names:
        bot.Properties.ApplyNow(property_name, "active", active)


def _get_vanquish_progress() -> tuple[int, int, int, float]:
    if not Routines.Checks.Map.MapValid() or not Routines.Checks.Map.IsExplorable() or not Map.IsVanquishable():
        return 0, 0, 0, 0.0

    foes_killed = Map.GetFoesKilled()
    foes_remaining = Map.GetFoesToKill()
    total_foes = foes_killed + foes_remaining
    progress = (foes_killed / total_foes) if total_foes > 0 else 0.0
    return foes_killed, foes_remaining, total_foes, progress


def _draw_settings():
    global donate_after_run, restart_after_run, watch_vanquish_completion

    PyImGui.text("Drazach Thicket Settings")
    PyImGui.separator()

    restart_after_run = PyImGui.checkbox("Restart after each run", restart_after_run)
    donate_after_run = PyImGui.checkbox("Donate faction after run", donate_after_run)
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
    last_remaining = None
    while True:
        yield from Routines.Yield.wait(1000, break_on_map_transition=True)

        if not watch_vanquish_completion:
            continue

        if not Routines.Checks.Map.MapValid() or not Routines.Checks.Map.IsExplorable() or not Map.IsVanquishable():
            continue

        foes_killed, foes_remaining, total_foes, _ = _get_vanquish_progress()
        if foes_remaining != last_remaining and total_foes > 0:
            bot.UI.PrintMessageToConsole(
                BOT_NAME,
                f"Vanquish progress: {foes_killed}/{total_foes} killed, {foes_remaining} remaining.",
            )
            last_remaining = foes_remaining

        if Map.IsVanquishCompleted():
            bot.UI.PrintMessageToConsole(BOT_NAME, "Vanquish complete. Returning to outpost.")
            bot.config.FSM.pause()
            yield
            bot.config.FSM.jump_to_state_by_name(RETURN_TO_OUTPOST_HEADER)
            yield
            bot.config.FSM.resume()
            yield
            return


def _targeted_missing_patrol_cleanup(bot: "Botting"):
    """Check the recurring skipped patrol once before allowing the run to end."""
    if Map.IsVanquishCompleted():
        return True
    if Map.GetMapID() != EXPLORABLE_TO_VANQUISH or not Map.IsVanquishable():
        raise RuntimeError("Drazach Thicket cleanup requires the active vanquishable instance")

    bot.UI.PrintMessageToConsole(
        BOT_NAME,
        "Main route ended incomplete; checking the recurring missing patrol.",
    )
    yield from bot.Move._coro_set_path_to(MISSING_PATROL_PATH)
    movement_succeeded = yield from bot.Move._coro_follow_path_to(autopath=False)
    if not movement_succeeded:
        raise RuntimeError("Drazach Thicket missing-patrol route could not be completed")

    combat_deadline = time.monotonic() + 120.0
    while Routines.Checks.Agents.InDanger():
        if Map.GetMapID() != EXPLORABLE_TO_VANQUISH:
            raise RuntimeError("Drazach Thicket changed maps during missing-patrol cleanup")
        if time.monotonic() >= combat_deadline:
            raise RuntimeError("Drazach Thicket missing-patrol combat exceeded two minutes")
        yield from Routines.Yield.wait(500, break_on_map_transition=True)

    if not Map.IsVanquishCompleted():
        foes_remaining = int(Map.GetFoesToKill() or 0)
        raise RuntimeError(
            "Drazach Thicket route and missing-patrol check ended without vanquish "
            f"confirmation ({foes_remaining} foes remaining)"
        )

    bot.UI.PrintMessageToConsole(BOT_NAME, "Vanquish confirmed after missing-patrol cleanup.")
    return True


def bot_routine(bot: Botting) -> None:
    bot.Events.OnPartyWipeCallback(lambda: OnPartyWipe(bot))

    bot.States.AddHeader(BOT_NAME)
    bot.Templates.Multibox_Aggressive()
    bot.Templates.Routines.PrepareForFarm(map_id_to_travel=OUTPOST_TO_START)

    bot.Party.SetHardMode(True)
    bot.Move.XYAndExitMap(*COORDS_TO_EXIT_OUTPOST, EXPLORABLE_TO_VANQUISH)
    bot.Wait.ForTime(4000)

    current_luxon = Player.GetLuxonData()[0]
    current_kurzick = Player.GetKurzickData()[0]

    bot.Move.XYAndInteractNPC(*COORDS_FOR_PRIEST)
    if current_luxon >= current_kurzick:
        bot.Multibox.SendDialogToTarget(0x84)
    bot.Multibox.SendDialogToTarget(DIALOG_FOR_PRIEST)

    bot.States.AddHeader("Start Combat")
    bot.UI.PrintMessageToConsole(BOT_NAME, "Starting Drazach Thicket kill route.")
    bot.Items.UseAllConsumables()
    bot.States.AddManagedCoroutine("DrazachFollowerConsumables", lambda: _upkeep_multibox_consumables(bot))
    bot.States.AddManagedCoroutine("DrazachVanquishWatchdog", lambda: _vanquish_watchdog(bot))
    bot.Move.FollowAutoPath(Vanquish_Path, "Kill Route")
    bot.Wait.UntilOutOfCombat()
    bot.States.AddCustomState(
        lambda: _targeted_missing_patrol_cleanup(bot),
        "Confirm Vanquish or Check Missing Patrol",
    )

    bot.States.AddHeader("Return to Outpost")
    bot.Multibox.ResignParty()
    bot.Wait.ForTime(3000)
    bot.Wait.UntilOnOutpost()
    bot.Wait.ForTime(3000)

    if donate_after_run:
        bot.Templates.Routines.PrepareForFarm(map_id_to_travel=HOUSE_ZU_HELZER)
        bot.States.AddHeader("Donate Faction")
        bot.Multibox.DonateFaction()
        bot.Wait.ForTime(20000)

    if restart_after_run:
        bot.States.JumpToStepName("[H]VQ Drazach Thicket_1")


def _on_party_wipe(bot: "Botting"):
    while Agent.IsDead(Player.GetAgentID()):
        yield from bot.Wait._coro_for_time(1000)
        if not Routines.Checks.Map.MapValid():
            bot.config.FSM.resume()
            return

    bot.States.JumpToStepName(RETURN_TO_OUTPOST_HEADER)
    bot.config.FSM.resume()


def OnPartyWipe(bot: "Botting"):
    ConsoleLog(BOT_NAME, "Party wipe detected. Returning to outpost.")
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
    bot.Update()
    bot.UI.draw_window(icon_path=TEXTURE)


if __name__ == "__main__":
    main()
