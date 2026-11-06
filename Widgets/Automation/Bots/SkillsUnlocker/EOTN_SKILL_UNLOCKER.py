import os
from typing import Any, List, Tuple, Optional, Callable, Generator
import types
import Py4GW
import PyImGui
from Py4GWCoreLib import *
from Py4GWCoreLib import ImGui,GLOBAL_CACHE
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.Routines import Routines
from Py4GWCoreLib.ImGui import ImGui
from Sources.ApoSource.ApoBottingLib import wrappers as BT

BOT_NAME = "Skills Unlocker"
MODULE_NAME = BOT_NAME

TEXTURE = os.path.join(PySystem.Console.get_projects_path(), "Bots", "SkillsUnlocker", "skills_unlocker.png")
ICONS_PATH = os.path.join(PySystem.Console.get_projects_path(), "Bots", "SkillsUnlocker", "icons")

bot = Botting(
    bot_name=BOT_NAME,
    upkeep_hero_ai_active=True,
    upkeep_auto_loot_active=False,
    upkeep_morale_active=True,
)



class BotVars:
    def __init__(self, map_id=0):
        self.bot_started = False
        self.window_module:ImGui.WindowModule
        self.variables = {}

        #HEROES SECTION
        self.koss = 6
        self.goren = 2
        self.jora = 18
        self.acolyte_jin = 5
        self.margrid_the_sly = 12
        self.pyre_fierceshot = 19
        self.tahlkora = 3
        self.dunkoro = 7
        self.ogden_stonehealer = 27
        self.master_of_whispers = 4
        self.olias = 14
        self.livia = 21
        self.norgu = 1
        self.gwen = 24
        self.acolyte_sousuke = 8
        self.zhed_shadowhoof = 10
        self.vekk = 26
        self.zenmai = 13
        self.anton = 20
        self.miku = 36
        self.xandra = 25
        self.zei_ri = 37
        self.razah = 15
        self.general_morgahn = 11
        self.keiran_thackeray = 17
        self.hayda = 22
        self.melonni = 9
        self.mox = 16
        self.kahmu = 23
        self.mercenary_1 = 28
        self.mercenary_2 = 29
        self.mercenary_3 = 30
        self.mercenary_4 = 31
        self.mercenary_5 = 32
        self.mercenary_6 = 33
        self.mercenary_7 = 34
        self.mercenary_8 = 35

bot_vars = BotVars()

def add_heroes_with_builds() -> Generator:
    # Quitter le groupe (optionnel)
    Party.LeaveParty()
    yield from Routines.Yield.wait(1000)

    # Ajout hÃ©ros (runtime)
    GLOBAL_CACHE.Party.Heroes.AddHero(bot_vars.gwen)
    GLOBAL_CACHE.Party.Heroes.AddHero(bot_vars.vekk)
    GLOBAL_CACHE.Party.Heroes.AddHero(bot_vars.ogden_stonehealer)

    # Laisser le temps que les hÃ©ros soient rÃ©ellement "prÃ©sents"
    yield from Routines.Yield.wait(1200)

    # Chargement builds : âœ… positions de party 1..3
    GLOBAL_CACHE.SkillBar.LoadHeroSkillTemplate(1, "OQhkAsC8gFKCNkDT/QY6yQGcxA")  # Gwen
    yield from Routines.Yield.wait(600)

    GLOBAL_CACHE.SkillBar.LoadHeroSkillTemplate(2, "OgljgwMpZO0iwBgWp5N0h14dMA")  # Vekk
    yield from Routines.Yield.wait(600)

    GLOBAL_CACHE.SkillBar.LoadHeroSkillTemplate(3, "OwUTMwHD1ZMWP0iBkZSPIDsSAA")  # Ogden
    yield from Routines.Yield.wait(600)

    yield

def AddHenchies():
    for i in range(1, 8):
        GLOBAL_CACHE.Party.Henchmen.AddHenchman(i)
        yield from Routines.Yield.wait(250)


# Captured from the Sifhalla-side shrine to Outrunner Remlok.  Keep the
# ordinary route short of the NPC; XYAndDialog retains ownership of the final
# approach and conversation.
DRAKKAR_TO_REMLOK_ROUTE_XY = (
    (6949.49, 23542.63), (6465.62, 23406.25), (5986.11, 23255.91),
    (5505.69, 23099.61), (5014.58, 22978.79), (4523.75, 22876.45),
    (4038.84, 22753.05), (3537.72, 22728.83), (3044.56, 22841.23),
    (2575.94, 23020.46), (2108.35, 23202.46), (1649.56, 23404.88),
    (1192.02, 23612.16), (733.86, 23818.65), (277.39, 24026.85),
    (-215.87, 24159.21), (-719.95, 24188.83), (-1227.20, 24194.12),
    (-1730.68, 24152.36), (-2234.14, 24106.43), (-2734.59, 24052.85),
    (-3238.60, 23983.09), (-3735.50, 23879.83), (-4227.79, 23774.18),
    (-4722.49, 23656.45), (-5224.21, 23593.97), (-5724.56, 23526.72),
    (-6221.26, 23455.43), (-6718.96, 23383.18), (-7212.44, 23283.95),
    (-7705.03, 23173.42), (-8205.31, 23134.74), (-8707.81, 23134.40),
    (-9209.32, 23190.40), (-9632.75, 23465.46), (-9971.76, 23837.23),
    (-10334.22, 24189.45), (-10668.65, 24562.33), (-10808.16, 24725.78),
)

# Sepulchre level-one route: walk over the captured Proof of Strength center,
# then continue along the replacement route recorded for Anything You Can Do.
SEPULCHRE_PROOF_OF_STRENGTH_ROUTE_XY = (
    (-7578.23, -16344.19), (-7092.91, -16197.64), (-6599.15, -16087.31),
    (-6110.94, -15971.19), (-5619.90, -15854.39), (-5366.00, -15794.00),
)
SEPULCHRE_LEVEL1_FRAGMENT_ROUTE_XY = (
    (-5686.91, -15401.77), (-5944.79, -14965.62), (-6191.57, -14524.03),
    (-6442.30, -14086.37), (-6575.49, -13594.38), (-6638.05, -13034.15),
    (-6629.68, -12530.43), (-6565.80, -12033.74), (-6467.00, -11541.94),
    (-6311.99, -11066.34), (-6137.25, -10596.09), (-5887.00, -10160.65),
    (-5485.02, -9848.94), (-5563.38, -9354.86), (-5582.04, -8850.15),
    (-5636.44, -8348.81), (-5865.55, -7897.86), (-6518.09, -7650.79),
    (-7015.06, -7567.73), (-7483.88, -7388.38), (-7886.51, -7079.52),
    (-8230.59, -6711.46), (-8512.65, -6287.49), (-8755.94, -5843.83),
    (-9046.10, -5434.51), (-9470.73, -5160.39), (-9865.66, -4847.15),
    (-10253.32, -4530.28), (-10700.16, -4265.96), (-11052.99, -3910.27),
    (-11355.39, -3511.40), (-11634.45, -3093.65), (-11805.14, -2622.12),
    (-11989.17, -2152.87), (-12191.88, -1691.31), (-12364.75, -1219.56),
    (-12474.15, -727.36), (-12580.03, -230.63), (-12690.33, 261.16),
    (-12800.59, 753.82), (-12827.22, 872.84),
)


# Be Very Very Quiet (quest 865), captured from Longeye's Ledge through
# Grothmar Wardowns. Portal routes include the required 450-unit continuation.
EBOSC_VAEL_MODEL_ID = 6081
EBOSC_ENTRY_BLESSING_MODEL_ID = 2036
EBOSC_ENTRY_BLESSING_XY = (-21765.0, 11480.0)
EBOSC_CHARR_INTELLIGENCE_XY = (20543.0, -10141.0)
EBOSC_LONGEYE_FIRST_EXIT_ROUTE_XY = (
    (-23017.95, 14731.92), (-23203.44, 14263.27), (-22966.05, 13819.04),
    (-22613.45, 13459.32), (-22262.66, 13101.46),
)
EBOSC_LONGEYE_FIRST_PORTAL_ROUTE_XY = (
    (-21630.0, 12565.0), (-21286.78, 12273.97),
)
EBOSC_FIRST_APPEARANCE_ROUTE_XY = (
    (-21449.00, 12487.00), (-21567.48, 11999.59), (-21745.34, 11531.71),
    (-21582.76, 11055.59), (-21413.58, 10584.20), (-21249.77, 10107.58),
    (-21121.57, 9624.18), (-21038.44, 9128.31), (-21024.00, 8626.37),
    (-21060.39, 8125.25), (-21122.52, 7625.40), (-21202.64, 7128.38),
    (-21269.40, 6628.64), (-21351.49, 6133.01),
)
EBOSC_LONGEYE_QUEST_EXIT_ROUTE_XY = (
    (-24890.92, 14481.03), (-24417.26, 14641.62), (-23940.32, 14809.94),
    (-23539.40, 14505.05), (-23203.15, 14127.69), (-22869.80, 13753.91),
    (-22527.73, 13383.17), (-22192.62, 13005.56),
)
EBOSC_LONGEYE_QUEST_PORTAL_ROUTE_XY = (
    (-21630.0, 12565.0), (-21275.70, 12287.56),
)
EBOSC_ENTRY_BLESSING_STANDOFF_ROUTE_XY = (
    (-21449.00, 12487.00), (-21601.28, 12006.89),
)
EBOSC_BLESSING_TO_VAEL_ROUTE_XY = (
    (-21169.41, 11282.47), (-20687.98, 11109.20), (-20222.94, 10912.05),
    (-19771.63, 10682.08), (-19330.60, 10446.46), (-18870.52, 10225.99),
    (-18400.47, 10026.70), (-17912.30, 9885.12), (-17422.72, 9765.55),
    (-16920.67, 9744.58), (-16411.16, 9695.54), (-15912.12, 9630.34),
    (-15409.94, 9600.13), (-14902.24, 9575.06), (-14395.68, 9605.74),
    (-13895.63, 9667.85), (-13360.37, 9702.46), (-12865.55, 9599.08),
    (-12382.12, 9739.04), (-11886.62, 9858.22), (-11386.99, 9943.28),
    (-10885.61, 9899.64), (-10384.45, 9814.61), (-9900.13, 9687.23),
    (-9392.87, 9618.34), (-8889.17, 9549.95), (-8384.25, 9475.21),
    (-7885.93, 9390.65), (-7377.44, 9367.50), (-6865.05, 9355.29),
    (-6361.20, 9289.46), (-5897.92, 9092.98), (-5467.94, 8834.80),
    (-5044.42, 8560.27), (-4621.22, 8279.35), (-4220.85, 7972.89),
    (-3831.72, 7654.85), (-3569.09, 7223.25), (-3583.52, 6719.49),
    (-3668.05, 6224.46), (-3789.29, 5737.14), (-3811.17, 5230.99),
    (-3668.80, 4743.11), (-3530.40, 4253.16), (-3305.55, 3754.03),
    (-3096.57, 3298.96), (-2886.53, 2841.60), (-2677.24, 2385.88),
    (-2465.86, 1925.58), (-2312.16, 1444.55), (-2175.64, 959.53),
    (-2001.02, 483.05), (-1801.66, 19.51), (-1555.34, -416.83),
    (-1260.83, -825.15), (-877.28, -1147.80), (-451.01, -1457.27),
    (-47.04, -1762.83), (361.88, -2055.01), (784.92, -2324.99),
    (1217.14, -2593.49), (1662.45, -2834.10), (2109.67, -3075.75),
)
EBOSC_FOLLOW_TORCH_TO_VAEL_ROUTE_XY = (
    (2877.78, -3756.16), (3231.45, -4109.88), (3699.38, -3933.54),
    (4173.58, -3751.91), (4674.46, -3716.25), (5158.84, -3857.56),
    (5600.65, -4124.73), (5940.59, -4501.62), (6357.75, -4793.07),
    (6659.70, -5195.61), (7010.66, -5563.33), (7412.69, -5871.20),
    (7807.93, -6181.51), (8297.80, -6383.14), (8797.85, -6440.01),
    (9296.72, -6487.02), (9795.57, -6521.06), (10293.24, -6569.37),
    (10798.27, -6562.85), (11299.42, -6549.70), (11803.76, -6535.79),
)
EBOSC_FOLLOW_TORCH_TO_MEETING_WAIT_ROUTE_XY = (
    (12811.08, -6565.76), (13316.80, -6514.43), (13818.92, -6471.22),
    (14324.05, -6439.17), (14830.10, -6391.47), (15330.56, -6350.93),
    (15834.92, -6367.30), (16332.66, -6469.86), (16695.08, -6856.71),
    (16956.28, -7285.43), (17241.16, -7702.88), (17551.83, -8095.59),
    (17906.23, -8455.06), (18262.27, -8765.81),
)
EBOSC_MEETING_ATTACK_ROUTE_XY = (
    (18690.49, -9024.01), (19119.33, -9282.58), (19558.03, -9547.10),
    (19957.11, -9851.68), (20247.77, -10260.29), (20564.77, -10648.40),
    (20726.30, -10846.11),
)
EBOSC_LONGEYE_REWARD_EXIT_ROUTE_XY = (
    (-23815.74, 15925.57), (-23876.85, 15424.12), (-23691.63, 14954.76),
    (-23405.51, 14538.81), (-23120.52, 14124.51), (-22783.56, 13753.14),
    (-22425.17, 13398.37), (-22069.23, 13046.04),
)
EBOSC_LONGEYE_REWARD_PORTAL_ROUTE_XY = (
    (-21630.0, 12565.0), (-21326.57, 12232.69),
)


def draw_window_light(
    self,
    main_child_dimensions: Tuple[int, int] = (520, 360),
    icon_path: str = "",
    iconwidth: int = 96,
    additional_ui: Optional[Callable[[], None]] = None
):


    if not self._config.ini_key_initialized:
        self._config.ini_key = Settings(
            f"BottingClass/bot_{self._config.bot_name}/bot_{self._config.bot_name}.ini",
            "account",
        ).name
        self._config.ini_key_initialized = True

    if not self._config.ini_key:
        return

    if ImGui.Begin(
        ini_key=self._config.ini_key,
        name=self._config.bot_name,
        p_open=True,
        flags=PyImGui.WindowFlags.AlwaysAutoResize,
    ):
        self._draw_main_child(main_child_dimensions, icon_path, iconwidth)
        if additional_ui:
            additional_ui()

    ImGui.End(self._config.ini_key)

    # Draw path like original
    if Routines.Checks.Map.MapValid():
        self.parent.UI.DrawPath(
            self._config.config_properties.follow_path_color.get("value"),
            self._config.config_properties.use_occlusion.is_active(),
            self._config.config_properties.snap_to_ground_segments.get("value"),
            self._config.config_properties.floor_offset.get("value"),
        )

# Monkeypatch UI method
try:
    bot.UI.draw_window = types.MethodType(draw_window_light, bot.UI)
except Exception:
    pass

DEBUG = True
def _log(msg: str, mt=PySystem.Console.MessageType.Warning):
    if not DEBUG:
        return
    try:
        PySystem.Console.Log(MODULE_NAME, msg, mt)
    except Exception:
        pass

def _set_bot_started(value: bool):
    cfg = getattr(bot, "config", None)
    if not cfg:
        return
    for attr in ("bot_started", "bot_running", "started", "is_started"):
        if hasattr(cfg, attr):
            try:
                setattr(cfg, attr, bool(value))
                return
            except Exception:
                pass
    try:
        if hasattr(cfg, "variables") and isinstance(cfg.variables, dict):
            cfg.variables["bot_started"] = bool(value)
    except Exception:
        pass


from Py4GWCoreLib import ConsoleLog, Routines, Player

def UseTome21788AndBuyLichAura(bot, inv_cache) -> "Generator":
    """
    Uses tome item_id=21788, then buys skill 114 (Aura de la Liche).
    inv_cache = ton instance de InventoryCache
    """

    TOME_ITEM_ID = 21788
    SKILL_ID = 114

    # VÃ©rif presence (par item_id exact)
    if inv_cache.GetItemCount(TOME_ITEM_ID) <= 0:
        ConsoleLog("Tome", f"Item ID {TOME_ITEM_ID} not found in inventory.")
        return


    ConsoleLog("Tome", f"Using tome item_id={TOME_ITEM_ID} ...")
    inv_cache.UseItem(TOME_ITEM_ID)

    # Laisser la fenÃªtre s'ouvrir
    yield from Routines.Yield.wait(900)

    ConsoleLog("Tome", f"Buying skill {SKILL_ID} ...")
    bot.Player.BuySkill(SKILL_ID)

    yield from Routines.Yield.wait(300)
    ConsoleLog("Tome", "Done.")

def _stop_clear_start_and_jump(step_target: Any, step_name: Optional[str] = None):
    from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE

    cfg = getattr(bot, "config", None)
    fsm = getattr(cfg, "FSM", None) if cfg else None
    if not cfg or not fsm:
        _log("[RUN] No config/FSM found", PySystem.Console.MessageType.Error)
        return

    # ---- STOP + CLEAR ----
    try:
        cfg.fsm_running = False
    except Exception:
        pass
    try:
        fsm.stop()
    except Exception:
        pass
    try:
        GLOBAL_CACHE.Coroutines.clear()
    except Exception:
        pass

    # ---- RESET POINTER ----
    try:
        fsm.reset()
    except Exception:
        pass

    # ---- MARK RUNNING ----
    try:
        cfg.fsm_running = True
        cfg.state_description = "Running"
    except Exception:
        pass

    # ---- JUMP + START (ordering matters) ----
    target_description = step_name or str(step_target)

    def _jump_to_target():
        if isinstance(step_target, int):
            fsm.jump_to_state_by_step_number(step_target)
        else:
            fsm.jump_to_state_by_name(step_target)

    try:
        _jump_to_target()
    except Exception as e:
        _log(f"[RUN] jump failed: {e}", PySystem.Console.MessageType.Error)
        return

    # Prefer resume (doesn't reset again)
    resumed = False
    for name in ("resume", "Resume", "run", "Run", "start", "Start"):
        fn = getattr(fsm, name, None)
        if callable(fn):
            try:
                fn()
                resumed = True
                break
            except Exception:
                pass

    # If no resume-like function exists, fallback to restart then jump again
    if not resumed:
        try:
            fsm.restart()
        except Exception:
            pass
        try:
            _jump_to_target()
        except Exception:
            pass

    _log(f"[RUN] stop/clear -> jump -> start : {target_description}", PySystem.Console.MessageType.Warning)

# Anchor step (jumpable)
_INIT_DONE = False
def _ensure_built():
    global _INIT_DONE
    if _INIT_DONE:
        return
    try:
        _set_bot_started(True)
        bot.Update()
        _INIT_DONE = True
        _log("[INIT] FSM built", PySystem.Console.MessageType.Warning)
    except Exception as e:
        _log(f"[INIT] failed: {e}", PySystem.Console.MessageType.Error)

def _anchor() -> Generator:
    yield

def _idle_forever() -> Generator:
    while True:
        yield from Routines.Yield.wait(250)


def _placeholder_unlock(skill_label: str):
    def _fn(bot: Botting) -> None:
        bot.States.AddHeader(f"[Unlock] {skill_label} (TODO)")
        bot.States.JumpToStepName("MENU_IDLE")
    return _fn


def _run_behavior_tree(tree: BehaviorTree) -> Generator[Any, Any, bool]:
    """Tick an existing BottingTree owner from the legacy FSM state queue."""
    try:
        while bot.config.fsm_running:
            result = tree.tick()
            if result == BehaviorTree.NodeState.SUCCESS:
                return True
            if result == BehaviorTree.NodeState.FAILURE:
                bot.config.state_description = "Blocked: canonical behavior tree failed"
                while bot.config.fsm_running:
                    yield from Routines.Yield.wait(250)
                return False
            yield from Routines.Yield.wait(50)
    finally:
        tree.reset()
    return False


def Unlock_ebon_battle_standard_of_courage(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Ebon Battle Standard of Courage")
    bot.Properties.Enable("halt_on_death")
    bot.Properties.Set("movement_timeout", value=15000)
    bot.Templates.Aggressive()

    # Vael's first appearance must be triggered before the quest instance.
    bot.Map.Travel(target_map_id=650)
    bot.Wait.ForMapLoad(target_map_id=650)
    bot.Properties.Disable("hero_ai")
    bot.Properties.Disable("pause_on_danger")
    bot.Move.FollowAutoPath(list(EBOSC_LONGEYE_FIRST_EXIT_ROUTE_XY))
    bot.Move.FollowPathAndExitMap(
        list(EBOSC_LONGEYE_FIRST_PORTAL_ROUTE_XY), target_map_id=649
    )
    bot.Move.FollowAutoPath(list(EBOSC_FIRST_APPEARANCE_ROUTE_XY))

    # Re-zone, take the Vanguard blessing, and explicitly accept quest 865.
    bot.Map.Travel(target_map_id=650)
    bot.Wait.ForMapLoad(target_map_id=650)
    bot.Move.FollowAutoPath(list(EBOSC_LONGEYE_QUEST_EXIT_ROUTE_XY))
    bot.Move.FollowPathAndExitMap(
        list(EBOSC_LONGEYE_QUEST_PORTAL_ROUTE_XY), target_map_id=649
    )
    bot.Properties.Enable("hero_ai")
    bot.Properties.Enable("pause_on_danger")
    bot.Move.FollowAutoPath(list(EBOSC_ENTRY_BLESSING_STANDOFF_ROUTE_XY))
    bot.States.AddCustomState(
        lambda: _run_behavior_tree(
            BT.TakeBlessing(
                pos=Vec2f(*EBOSC_ENTRY_BLESSING_XY),
                buttons=0,
                multi_account=False,
                log=False,
            )
        ),
        "Take Vanguard blessing outside Longeye",
    )
    bot.Move.FollowAutoPath(list(EBOSC_BLESSING_TO_VAEL_ROUTE_XY))
    bot.Move.XYAndDialog(2558.0, -3318.0, 0x836101)

    # Stay out of combat while following Torch and explicitly release him at Vael.
    bot.Properties.Disable("hero_ai")
    bot.Properties.Disable("pause_on_danger")
    bot.Move.FollowAutoPath(list(EBOSC_FOLLOW_TORCH_TO_VAEL_ROUTE_XY))
    bot.Move.XYAndDialog(11991.96, -6643.81, 0x836104)
    bot.Move.FollowAutoPath(list(EBOSC_FOLLOW_TORCH_TO_MEETING_WAIT_ROUTE_XY))
    bot.Wait.ForTime(30000)

    bot.Properties.Enable("hero_ai")
    bot.Properties.Enable("pause_on_danger")
    bot.Move.FollowAutoPath(list(EBOSC_MEETING_ATTACK_ROUTE_XY))
    bot.Wait.UntilOutOfCombat()
    bot.Move.XY(*EBOSC_CHARR_INTELLIGENCE_XY)
    bot.Wait.ForTime(1500)

    # Captain Langmar awards the skill outside Longeye's Ledge.
    bot.Map.Travel(target_map_id=650)
    bot.Wait.ForMapLoad(target_map_id=650)
    bot.Move.FollowAutoPath(list(EBOSC_LONGEYE_REWARD_EXIT_ROUTE_XY))
    bot.Move.FollowPathAndExitMap(
        list(EBOSC_LONGEYE_REWARD_PORTAL_ROUTE_XY), target_map_id=649
    )
    bot.Move.XYAndDialog(-21069.0, 12353.0, 0x836107)
    bot.UI.CancelSkillRewardWindow()
    bot.States.JumpToStepName("MENU_IDLE")

def Unlock_ebon_battle_standard_of_honor(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Ebon Battle Standard of Honor")
    bot.Properties.Enable("pause_on_danger")
    bot.Properties.Enable("halt_on_death")
    bot.Properties.Enable("hero_ai")
    bot.Templates.Aggressive()

    bot.Map.Travel(target_map_name="Longeyes Ledge")
    bot.Move.XY(-21902, 12807)
    bot.Wait.ForTime(5000)
    bot.Move.XYAndDialog(-21141.81, 12378.68, 0x836003)  # Battle Honor Stand
    bot.Wait.ForTime(1000)
    bot.Move.XYAndDialog(-21141.81, 12378.68, 0x836001)  # Battle Honor Stand
    bot.Wait.ForTime(1000)

    # =========================
# PATH 1
# =========================
    path_1 = [
        (-21593.0, 12517.0),
        (-20064.0, 11212.0),
        (-18659.0,  9768.0),
        (-17352.0,  8246.0),
        (-16126.0,  6640.0),
        (-14663.0,  5256.0),
        (-13347.0,  3732.0),
        (-11993.0,  2247.0),
        (-11088.0,   402.0),
        ( -9414.0,  -699.0),
        ( -7532.0,   132.0),
        ( -5576.0,  -322.0),
        ( -3621.0,  -814.0),
        ( -1677.0, -1304.0),
        (   177.0, -2140.0),
        (  1759.0, -3373.0),
        (  3730.0, -3747.0),
        (  5650.0, -4349.0),
        (  7421.0, -5292.0),
        (  8547.0, -6957.0),
        ( 10587.0, -6733.0),
        ( 12591.0, -6583.0),
        ( 14521.0, -7151.0),
        ( 16095.0, -8448.0),
        ( 17681.0, -9721.0),
        ( 19282.0,-11005.0),
        ( 20765.0,-12412.0),
        ( 22538.0,-13411.0),
        ( 23410.0,-13901.0),
    ]
    bot.Move.FollowAutoPath(path_1)
    bot.Wait.UntilOutOfCombat()
    bot.Wait.ForMapLoad(target_map_id=651)
# =========================
# PATH 2 (aprÃ¨s map 651)
# =========================
    path_2 = [
    (-17861.0, 16317.0),
    (-16404.0, 14900.0),
    (-16459.0, 12851.0),
    (-17542.0, 11132.0),
    (-17939.0,  9166.0),
    (-16308.0,  7932.0),
    (-15150.0,  6294.0),
    (-14010.0,  4577.0),
    (-13622.0,  2552.0),
    (-13094.0,   598.0),
    (-11367.0,  -490.0),
    ( -9393.0,  -831.0),
    ( -7616.0, -1762.0),
    ( -5677.0, -2456.0),
    ( -4372.0, -4015.0),
    ( -3143.0, -5620.0),
    ( -2954.0, -7657.0),
    ( -2423.0, -9586.0),
    (  -593.0,-10426.0),
    (  1413.0,-10033.0),
    (  3432.0, -9958.0),
    (  4945.0, -8637.0),
    (  6962.0, -8362.0),
    (  8991.0, -8392.0),
    (  4471.0, -7294.0),
    (  6525.0, -7403.0),
    (  8415.0, -8062.0),
    ( 10082.0, -9228.0),
    ( 11715.0, -8045.0),
    ]
    bot.Move.FollowAutoPath(path_2)
    bot.Wait.UntilOutOfCombat()


    bot.Map.Travel(target_map_id=650)
    bot.Move.XY(-21902, 12807)
    bot.Wait.ForMapLoad(target_map_id=649)
    bot.Move.XYAndDialog(-21141.81, 12378.68, 0x836007)  # Rewards

    # IMPORTANT: go back to menu, otherwise we'd fall into next section
    bot.States.JumpToStepName("MENU_IDLE")

def Unlock_mental_block(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Mental Block")
    bot.Properties.Enable("pause_on_danger")
    bot.Properties.Disable("halt_on_death")
    bot.Properties.Set("movement_timeout", value=-1)
    bot.Properties.Enable("hero_ai")

    bot.Map.Travel(target_map_id=641)
    bot.Wait.ForMapLoad(target_map_id=641)

    bot.Move.XYAndDialog(25203, -10694, 0x837701)  # Balthazar (take quest)

    bot.Map.Travel(target_map_id=639)
    bot.Wait.ForMapLoad(target_map_id=639)

    bot.Move.XY(-22999, 6530)
    bot.Wait.ForMapLoad(target_map_id=566)

    # 4 hunting spots
    bot.Move.XY(-9761, -8000)   # spot 1
    bot.Move.XY(7833, -8293)    # spot 2
    bot.Move.XY(11690, -6215)   # spot 3
    bot.Move.XY(15918, -2667)   # spot 4

    bot.Wait.ForTime(3000)
    bot.Wait.UntilOutOfCombat()

    bot.Multibox.ResignParty()
    bot.Wait.ForMapLoad(target_map_id=639)

    bot.Map.Travel(target_map_id=641)
    bot.Wait.ForMapLoad(target_map_id=641)

    bot.Move.XYAndDialog(25203, -10694, 0x837707)  # Rewards
    bot.States.JumpToStepName("MENU_IDLE")

def Unlock_smooth_criminal(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Smooth Criminal")
    bot.Map.Travel(target_map_id=641)
    bot.Wait.ForMapLoad(target_map_id=641)

    # This script used ApplyNow; keep it identical
    bot.Properties.ApplyNow("pause_on_danger", "active", True)
    bot.Properties.ApplyNow("halt_on_death", "active", True)
    bot.Properties.ApplyNow("movement_timeout", "value", 15000)
    bot.Properties.ApplyNow("hero_ai", "active", True)

    bot.Move.XYAndDialog(25203, -10694, 0x837C01)  # Melandru (take quest)

    bot.Move.XY(18781, -10477)
    bot.Wait.ForMapLoad(target_map_name="Alcazia Tangle")

    # Spots / shrines route
    bot.Move.XY(17024, -600)
    bot.Move.XY(18237, 6691)     # res shrine 1
    bot.Move.XY(15518, 8375)
    bot.Move.XY(13200, 15000)    # Spot 1 confirmed
    bot.Wait.ForTime(3000)
    bot.Wait.UntilOutOfCombat()

    bot.Move.XY(19516, 4686)     # rez shrine 2 cliff
    bot.Move.XY(12184, 370)      # midway
    bot.Move.XY(4802, -4990)     # Rez Shrine 3
    bot.Move.XY(-8760, -3378)    # Rez Shrine 4
    bot.Move.XY(-5555, -2108)
    bot.Move.XY(-6678, 6477)     # Spot 2 confirmed (per script comment)
    bot.Wait.ForTime(3000)
    bot.Wait.UntilOutOfCombat()

    bot.Move.XY(-8860, -3178)    # Rez Shrine 4 again
    bot.Move.XY(-11202, 758)     # Spot 3 confirmed
    bot.Wait.ForTime(3000)
    bot.Wait.UntilOutOfCombat()

    bot.Multibox.ResignParty()
    bot.Wait.ForTime(3000)
    bot.Wait.ForMapLoad(target_map_id=641)

    bot.Move.XYAndDialog(25203, -10694, 0x837C07)  # Rewards
    bot.States.JumpToStepName("MENU_IDLE")

def Unlock_feel_no_pain(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Feel No Pain")
    bot.Map.Travel(target_map_name="Olafstead")
    bot.Move.XYAndDialog(90.00, -749.00,0x835201)
    bot.Move.XYAndDialog(90.00, -749.00,0x84)
    bot.Wait.ForMapLoad(target_map_name="The Great Norn Alemoot")
    bot.Move.XYAndDialog(12602.00, -6210.00,0x85)
    bot.Move.XYAndInteractGadget(12727.00, -6612.00)
    bot.Move.XYAndInteractGadget(12701.00, -6523.00)
    bot.Move.XYAndInteractGadget(10109.00, -8707.00)
    bot.Move.XY(10750.13, -9616.31)
    bot.Move.XYAndInteractGadget(10109.00, -8707.00)
    bot.Move.XY(10750.13, -9616.31)
    bot.Move.XYAndInteractGadget(10109.00, -8707.00)
    bot.Move.XY(10750.13, -9616.31)
    bot.Move.XY(12727.00, -6612.00)
    bot.Move.XYAndInteractGadget(12727.00, -6612.00)
    bot.Move.XYAndInteractGadget(12701.00, -6523.00)

    path = [
    (10699.6,-7143.7),
    (10860.8,-7346.0),
    (10995.1,-7550.1),
    (10929.0,-7752.8),
    (10732.7,-7956.7),
    (10595.6,-8161.1),
    (10663.2,-8364.8),
    (10866.8,-8382.3),
    (11069.9,-8278.6),
    (11270.6,-8175.8),
    (11474.9,-8166.0),
    (11509.5,-8370.6),
    (11339.8,-8570.8),
    (11165.9,-8776.2),
    (11122.3,-8977.3),
    (11324.1,-9149.3),
    (11524.2,-9087.1),
    (11726.6,-8891.3),
    (11928.8,-8749.9),
    (12128.9,-8825.3),
    (12133.3,-9030.4),
    (11989.0,-9233.9),
    (11841.6,-9434.0),
    (11752.0,-9636.7),
    (11954.8,-9805.3),
    (12156.2,-9668.8),
    (12237.3,-9466.5),
    (12349.3,-9265.1),
    (12905.82, -9617.43)]

    bot.Move.FollowAutoPath(path)
    bot.Move.XY(12727.00, -6612.00)
    bot.Move.XYAndInteractGadget(12727.00, -6612.00)
    bot.Move.XYAndInteractGadget(12701.00, -6523.00)
#need pig sequence
    bot.Move.XYAndDialog(12602.00, -6210.00,0x835207)

def Unlock_dwarven_stability(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Dwarven Stability")
    bot.Map.Travel(target_map_name="Sifhalla")
    bot.Wait.ForMapLoad(target_map_id=643)

    bot.Properties.Enable("pause_on_danger")
    bot.Properties.Disable("halt_on_death")
    bot.Properties.Set("movement_timeout", value=-1)
    bot.Properties.Enable("hero_ai")

    # Big Unfriendly Jotun chain
    bot.Move.XYAndDialog(12009, 24726, 0x837E03)   # open dialog tree
    bot.Dialogs.AtXY(12009, 24726, 0x837E01)       # take quest

    bot.Move.XYAndExitMap(13583, 18781, target_map_id=513)
    bot.Wait.ForMapLoad(target_map_id=513)

    bot.Move.XY(15159, 12506)
    bot.Wait.UntilOutOfCombat()

    bot.Multibox.ResignParty()
    bot.Wait.ForTime(3000)
    bot.Wait.ForMapToChange(target_map_id=643)

    bot.Move.XYAndDialog(12009, 24726, 0x837E07)   # Reward
    bot.States.JumpToStepName("MENU_IDLE")

def Unlock_deft_strike(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Deft Strike")    
    bot.Map.Travel(target_map_name="Eye of the North outpost")

    bot.Move.XYAndDialog(-1856.00, 3073.00, 0x836401)
    bot.Move.XYAndDialog(-1856.00, 3073.00, 0x836404)
    bot.Move.XYAndDialog(-1856.00, 3073.00, 0x84)
    bot.Wait.ForMapLoad(target_map_name="Mano a Norn-o")
    bot.Move.XY(-1470.06,2672)
    bot.Move.XYAndDialog(-1856.00, 3073.00,0x836407)
    bot.UI.CancelSkillRewardWindow()    
    bot.States.JumpToStepName("MENU_IDLE")   

def Unlock_ebon_vanguard_assassin_support(bot: Botting) -> None:
    bot.Templates.Aggressive
    bot.States.AddHeader("[Unlock] Ebon Vanguard Assassin Support")    
    bot.Map.Travel(target_map_name="Eye of the North outpost")
    bot.Move.XYAndDialog(-1856.00, 3073.00, 0x836A01)
    bot.Move.XYAndDialog(-1856.00, 3073.00, 0x836A04)
    bot.Move.XYAndDialog(-1856.00, 3073.00, 0x86)    
    bot.Wait.ForMapLoad(target_map_name="Service: Practice, Dummy")
    bot.Move.XY(-1856.00, 3073.00)
    bot.Wait.ForMapLoad(target_map_name="Eye of the North outpost")
    bot.Move.XYAndDialog(-1856.00, 3073.00,0x836A07) #Reward
    bot.UI.CancelSkillRewardWindow()
    bot.States.JumpToStepName("MENU_IDLE")   

def Unlock_winds(bot: Botting) -> None:
    bot.Templates.Aggressive
    bot.States.AddHeader("[Unlock] Deft Strike")    
    bot.Map.Travel(target_map_name="Eye of the North outpost")

    bot.Move.XYAndDialog(-1856.00, 3073.00, 0x835601)
    bot.Map.Travel(target_map_name="Gunnar's Hold")
    bot.States.AddCustomState(add_heroes_with_builds, "Add heroes + builds")
    bot.Wait.ForTime(2000)
    bot.States.AddCustomState(AddHenchies, "Add Henchies")
    bot.Move.XYAndExitMap(15183.199218, -6381.958984,target_map_name="Norrhart Domains")
    
    path =[
    (14576.0,-6137.7),
    (14568.2,-5136.7),
    (14112.5,-4135.1),
    (13107.6,-3750.6),
    (12600.1,-2745.8),
    (12484.4,-1739.7),
    (12528.0,-732.3),
    (11619.6,313.6),
    (11527.4,1316.2),
    (10823.6,2318.0)]
    bot.Move.FollowAutoPath(path)
    bot.Wait.UntilOutOfCombat

    bot.Map.Travel(target_map_name="Eye of the North outpost")
    bot.Move.XYAndDialog(-1856.00, 3073.00, 0x835607) #reward
    bot.UI.CancelSkillRewardWindow()    
    bot.States.JumpToStepName("MENU_IDLE")   

def Unlock_you_move_like_a_dwarf(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] You Move Like a Dwarf!")

    bot.Map.Travel(target_map_name="Sifhalla")
    bot.Wait.ForMapLoad(target_map_id=643)

    bot.Properties.Enable("pause_on_danger")
    bot.Properties.Disable("halt_on_death")
    bot.Properties.Set("movement_timeout", value=-1)
    bot.Properties.Enable("hero_ai")

    # Worthy Deeds (quest for this skill)
    bot.Move.XYAndDialog(14380, 23968, 0x833A01)  # take quest

    bot.Move.XYAndExitMap(8832, 23870, target_map_id=513)
    bot.Wait.ForMapLoad(target_map_id=513)

    bot.Move.XY(11434, 19708)
    bot.Move.XY(14164, 2682)
    bot.Move.XY(9435, -5806)   # if you got here and no boss restart

    bot.Wait.UntilOutOfCombat()
    bot.Move.XY(1914, -6963)   # Myish, Lady of the Lake
    bot.Wait.UntilOutOfCombat()

    bot.Move.XY(4735, -14202)
    bot.Move.XY(5752, -15236)
    bot.Move.XY(8924, -15922)
    bot.Move.XY(14134, -16744)
    bot.Move.XY(12581, -19343)  # Rabbit hole start
    bot.Move.XY(12702, -23855)  # around the bend
    bot.Move.XY(13952, -23063)  # Nulfastu, Earthbound

    bot.Wait.ForTime(45000)     # time window to kill + return
    bot.Map.Travel(target_map_name="Sifhalla")
    bot.Wait.ForMapLoad(target_map_id=643)

    bot.Move.XYAndDialog(14380, 23968, 0x833A07)  # Rewards
    bot.UI.CancelSkillRewardWindow()    
    bot.States.JumpToStepName("MENU_IDLE")

def Unlock_i_am_unstoppable(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] I Am Unstoppable!")
    bot.States.AddCustomState(_anchor, "IAU:TAKE_ANYTHING_YOU_CAN_DO")

    bot.Map.Travel(target_map_name="Sifhalla")
    bot.Wait.ForMapLoad(target_map_id=643)

    bot.Properties.Enable("pause_on_danger")
    bot.Properties.Disable("halt_on_death")
    bot.Properties.Set("movement_timeout", value=-1)
    bot.Properties.Enable("hero_ai")

    # --- Part 1: Anything you can do ---
    bot.Move.XYAndDialog(14380, 23874, 0x833E01)  # Anything you can do
    bot.States.AddCustomState(_anchor, "IAU:HUNT_AVARR_AND_WHITEOUT")
    bot.Map.Travel(target_map_name="Sifhalla")
    bot.Wait.ForMapLoad(target_map_id=643)
    bot.Move.XY(14682, 22900)
    bot.Move.XYAndExitMap(17000, 22872, target_map_id=546)
    bot.Wait.ForMapLoad(target_map_id=546)

    bot.Move.XY(-9431, -20124)
    bot.Move.XY(-8441, -13685)
    bot.Move.XY(-9743, -6744)
    bot.Move.XY(-10672, 4815)     # wall hugging
    bot.Move.XY(-8464, 17239)     # up to Avarr the Fallen
    bot.Move.XY(-11700, 24101)
    bot.Wait.UntilOutOfCombat()

    bot.Move.XY(-8464, 17239)     # back down the hill
    bot.Move.XY(-638, 17801)      # up to Whiteout (watch boulder)
    bot.Move.XY(-933, 15368)      # run away from boulder
    bot.Wait.ForTime(6000)
    bot.Move.XY(-1339, 22089)     # Kill Whiteout
    bot.Wait.ForTime(5000)        # extra time in case of wipe

    bot.States.AddCustomState(_anchor, "IAU:FRAGMENT_OF_ANTIQUITIES")
    bot.Map.Travel(target_map_name="Sifhalla")
    bot.Wait.ForMapLoad(target_map_id=643)

    # --- Part 2: Fragment of Antiquities ---
    bot.States.AddHeader("[Unlock] Fragment of Antiquities")
    bot.Move.XYAndExitMap(8832, 23870, target_map_id=513)
    bot.Wait.ForMapLoad(target_map_id=513)

    bot.Move.FollowAutoPath(list(DRAKKAR_TO_REMLOK_ROUTE_XY[:-2]))
    bot.Move.XYAndDialog(-10926, 24732, 0x832901)  # Fragment of Antiquities
    bot.Move.XY(-11293.05, 24868.94)
    bot.Move.XY(-11603.00, 24975.00)
    bot.Move.XY(-11763.68, 25412.23)
    bot.Move.XY(-11904.67, 25896.55)
    bot.Move.XY(-12009.97, 26331.78)
    bot.Move.XYAndExitMap(-12138, 26829, target_map_id=628)
    bot.Wait.ForMapLoad(target_map_id=628)

    bot.Move.FollowAutoPath(list(SEPULCHRE_PROOF_OF_STRENGTH_ROUTE_XY))
    bot.Wait.ForTime(1500)  # allow the walk-over Proof of Strength gate to open
    bot.Move.FollowAutoPath(list(SEPULCHRE_LEVEL1_FRAGMENT_ROUTE_XY))
    bot.Wait.UntilOutOfCombat()

    bot.States.AddCustomState(_anchor, "IAU:CLAIM_ANYTHING_YOU_CAN_DO")
    bot.Map.Travel(target_map_name="Sifhalla")
    bot.Wait.ForMapLoad(target_map_id=643)

    bot.Move.XYAndDialog(14380, 23968, 0x833E07)   # Rewards
    
    bot.States.AddCustomState(_anchor, "IAU:COLD_AS_ICE")
    bot.Map.Travel(target_map_name="Sifhalla")
    bot.Wait.ForMapLoad(target_map_id=643)

    bot.Properties.Enable("pause_on_danger")
    bot.Properties.Disable("halt_on_death")
    bot.Properties.Set("movement_timeout", value=-1)
    bot.Properties.Enable("hero_ai")

    bot.Items.SpawnBonusItems()
    bot.Items.Equip(ModelID.Bonus_Nevermore_Flatbow.value)  # swap to prevent error (as script)
    bot.Items.Equip(6515)  # Necro Bonus Staff
    

    #Automatic prepring to load build#

    #bot.Map.Travel(target_map_name="Great Temple of Balthazar")
    #bot.Move.XYAndDialog(-3071.00, -7258.00,0x485)
    #bot.Move.XYAndDialog(-3071.00, -7258.00,0x484)
    #bot.Map.Travel(target_map_name="Eye of the North outpost")
    #bot.Move.XYAndInteractNPC(-3551.00, 2341.00)
    #bot.Wait.ForTime(3000)
    #bot.Player.BuySkill(2139)
    #bot.Map.Travel(target_map_name="Kaineng Center")
    #bot.Move.XY(-914.74, -1621.43)
    #bot.Move.XY(420.00, 1388.00)    
    #bot.Move.XYAndInteractNPC(420.00, 1388.00)
    #bot.Wait.ForTime(3000)
    #bot.Player.BuySkill(101)
    #bot.Wait.ForTime(3000)
    #bot.Player.BuySkill(159)
    #NEED function to use elite necromancer tome and take Aura of the lich
    
    def _equip_skill_bar() -> Generator[Any, Any, None]:
        profession, _ = Agent.GetProfessionNames(Player.GetAgentID())

        if profession == "Dervish":
            yield from Routines.Yield.Skills.LoadSkillbar("OgSCU8pkcQZwnwWIAAAAAAAA")
        elif profession == "Ritualist":
            yield from Routines.Yield.Skills.LoadSkillbar("OASjUwHKIRyBlBfCbhAAAAAAAAA")
        elif profession == "Warrior":
            yield from Routines.Yield.Skills.LoadSkillbar("OQQTU4DHHaLUOoM4TAAAAAAAAAA")
        elif profession == "Ranger":
            yield from Routines.Yield.Skills.LoadSkillbar("OgQTU4DfHaLUOoM4TAAAAAAAAAA")
        elif profession == "Necromancer":
            yield from Routines.Yield.Skills.LoadSkillbar("OApCU8pkcQZwnwWIAAAAAAAA")
        elif profession == "Elementalist":
            yield from Routines.Yield.Skills.LoadSkillbar("OgRDU8x8QbhyBlBfCAAAAAAAAA")
        elif profession == "Mesmer":
            yield from Routines.Yield.Skills.LoadSkillbar("OQRDATxHTbhyBlBfCAAAAAAAAA")
        elif profession == "Monk":
            yield from Routines.Yield.Skills.LoadSkillbar("OwQTU4DDHaLUOoM4TAAAAAAAAAA")
        elif profession == "Assasin":
            yield from Routines.Yield.Skills.LoadSkillbar("OwRjUwH84QbhyBlBfCAAAAAAAAA")
        elif profession == "Paragon":
            yield from Routines.Yield.Skills.LoadSkillbar("OQSCU8pkcQZwnwWIAAAAAAAA")
        yield

    bot.States.AddCustomState(_equip_skill_bar, "Equip Skill Bar")

    bot.Move.XYAndDialog(14380, 23968, 0x834401)  # Cold As Ice (take quest)
    bot.Dialogs.AtXY(14380, 23968, 0x85)          # I am Ready

    bot.Wait.ForMapLoad(target_map_id=690)        # Special Sifhalla Map
    bot.Wait.ForTime(5000)

    bot.Move.XY(14553, 23043)
    bot.Wait.ForTime(2000)
    bot.SkillBar.UseSkill(114)

    bot.Wait.UntilOnCombat()
    bot.Wait.UntilOutOfCombat()

    bot.Multibox.ResignParty()
    bot.Wait.ForTime(20000)
    bot.Wait.ForMapLoad(target_map_id=643)

    bot.States.AddCustomState(_anchor, "IAU:CLAIM_FINAL_REWARD")
    bot.Move.XYAndDialog(14380, 23968, 0x834407)  # Rewards
    bot.States.JumpToStepName("MENU_IDLE")


def Unlock_air_of_superiority(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Previous Skills")
    Unlock_previous_skills(bot)
    bot.States.AddHeader("[Unlock] Air of Superiority")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837D01)
    bot.Map.Travel(target_map_name="Olafstead")
    bot.Move.XYAndExitMap(1440, 1147.00, target_map_name="Varajar Fells")
    # This script used ApplyNow; keep it identical
    bot.Properties.ApplyNow("pause_on_danger", "active", True)
    bot.Properties.ApplyNow("halt_on_death", "active", True)
    bot.Properties.ApplyNow("movement_timeout", "value", 15000)
    bot.Properties.ApplyNow("hero_ai", "active", True)
    path=[(-2584.1,515.4),
    (-3168.0,-985.5),
    (-3228.0,-2487.7),
    (-3424.8,-3989.7),
    (-4391.7,-2487.7),
    (-4291.6,-987.4),
    (-3990.1,512.9),
    (-3273.5,2013.5),
    (-2242.5,3515.2),
    (-975.6,5015.6),
    (527.6,5854.7),
    (2031.6,5378.3),
    (3536.6,5030.3),
    (5041.9,4768.3),
    (6545.9,5184.7),
    (8050.1,5978.9),
    (9552.6,6651.4),
    (11053.5,6855.5),
    (12558.9,7385.4),
    (14059.8,6908.5),
    (15561.8,6764.8),
    (17064.0,5965.7),
    (17953.4,4465.6),
    (19457.1,3896.6),
    (20957.5,3474.3),
    (23571.6,1778.8)]

    bot.Move.FollowAutoPath(path)
    bot.Wait.UntilOutOfCombat()

    bot.Move.XYAndDialog(22648.00,1078.00,0x837D07) # Rewards
    
    bot.UI.CancelSkillRewardWindow()   
    bot.Multibox.ResignParty()
    bot.Wait.ForMapLoad(target_map_name="Olafstead")
     
    bot.States.JumpToStepName("MENU_IDLE")




def Unlock_asuran_scan(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Asuran Scan")

    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837901)  # Grenth (take quest)

    bot.Map.Travel(target_map_name="Gadd's Encampment")
    bot.Move.XYAndExitMap(-9690, -19524, target_map_name="Sparkfly Swamp")
    # This script used ApplyNow; keep it identical
    bot.Properties.ApplyNow("pause_on_danger", "active", True)
    bot.Properties.ApplyNow("halt_on_death", "active", True)
    bot.Properties.ApplyNow("movement_timeout", "value", 15000)
    bot.Properties.ApplyNow("hero_ai", "active", True)

    path=[(-11165.4,-18283.9),    (-11328.1,-17780.3),    (-11384.3,-17280.2),    (-11334.4,-16778.1),    (-11299.2,-16276.2),    (-11329.3,-15772.8),    (-11316.9,-15269.3),    (-11349.1,-14767.7),    (-11348.2,-14267.3),    (-11384.4,-13765.5),    (-11316.9,-13265.2),    (-11233.8,-12765.2),    (-11150.5,-12263.8),    (-11067.2,-11762.9),    (-10896.6,-11260.0),    (-10667.6,-10758.3),    (-10461.4,-10258.3),    (-10254.9,-9757.7),    (-10064.7,-9256.7),    (-9835.3,-8756.4),    (-9718.4,-8251.5),    (-9640.7,-7750.0),    (-9561.5,-7249.7),    (-9512.5,-6749.1),    (-9480.4,-6248.2),    (-9458.3,-5743.9),    (-9469.2,-5241.0),    (-9559.7,-4740.4),    (-9232.6,-4238.3),    (-8888.4,-3737.5),    (-8548.9,-3233.5),    (-8232.0,-2729.6),    (-8124.7,-2227.3),    (-8145.7,-1727.3),    (-8172.7,-1223.1),    (-8213.0,-718.8),    (-8263.4,-217.4),    (-8315.9,285.3),    (-8388.2,789.5),    (-8511.6,1292.5),    (-8647.4,1797.6),    (-8766.6,2301.6),    (-9177.1,2804.6),    (-9641.8,3305.0),    (-9964.5,3809.8),    (-9928.1,4311.3),    (-9428.2,4814.2),    (-8927.0,5191.5),    (-8443.6,5693.6),    (-7941.2,5822.0),    (-7440.0,5904.8),    (-6935.2,5990.9),    (-6431.5,6070.9),    (-5925.0,6133.0),    (-5422.3,6192.9),    (-4917.6,6210.4),    (-4415.9,6234.1),    (-3914.2,6258.1),    (-3413.2,6288.2),    (-2911.0,6320.1),    (-2406.6,6352.2),    (-1902.5,6292.1),    (-1401.4,6104.2),    (-898.4,5923.1),    (-396.5,5874.6),    (107.0,5793.2),    (607.5,5705.9),    (1111.0,5617.4),    (1612.5,5529.3),    (2114.7,5559.1),    (2616.7,5820.9),    (3119.0,6102.4),    (3620.1,6494.9),    (4121.1,6888.0),    (4623.3,7275.8),    (5124.6,7435.8),    (5626.4,7537.5),    (6080.2,7037.3),    (6438.3,6533.6),    (6795.6,6031.0),    (7296.8,5720.0),    (7797.8,5498.1),    (8299.2,5427.9),    (8799.6,5350.6),    (9300.5,5511.6),    (9802.5,5812.5),    (10346.69,8246.0),    (10808.6,6189.0),    (11311.0,6333.2),    (11302.6,5831.4),    (11248.2,5330.4),    (11210.3,4828.7),    (11132.2,4326.2),    (11034.8,3821.7),    (10937.3,3320.5),   (10839.4,2817.3),    (10741.8,2315.8),    (10644.0,1813.2),    (10530.5,1311.6),    (10410.4,807.9),    (10264.4,304.8),    (10117.4,-196.6),    (10220.3,-697.2),    (10295.1,-1198.7),    (9793.1,-1453.9),    (9289.4,-1546.0),    (8787.0,-1543.4),    (8286.1,-1480.6),    (7785.1,-1417.8),    (7285.0,-1355.1),    (6779.9,-1303.0),    (6276.2,-1185.9),    (5774.2,-1006.9),    (5272.1,-1011.6),    (4769.0,-1198.1),    (4264.9,-1441.2),    (3764.1,-1665.9),    (3823.0,-2168.4),    (4325.4,-2468.7),    (4828.8,-2117.9),    (5331.0,-1838.1),    (5833.0,-1559.3),    (6319.6,-1055.8),    (6395.2,-554.3),    (6346.1,-53.7),    (6292.7,447.5),    (6241.4,950.9),    (6140.5,1451.3),    (6090.1,1953.7),    (6039.9,2455.2),    (5728.8,2957.0),    (5271.5,3458.7),    (4767.9,3612.2),    (4350.9,3108.4),    (3865.1,2604.3),    (3657.0,2100.5),    (3460.4,1598.3),(3360.7,1463.1)] #postion 1 
    bot.Move.FollowAutoPath(path)
    bot.Wait.UntilOutOfCombat()
    bot.Wait.ForTime(10000)  # wait for event to trigger
    bot.Multibox.ResignParty()
    bot.Wait.ForMapLoad(target_map_name="Gadd's Encampment")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837907)  # Reward
    bot.UI.CancelSkillRewardWindow()
    bot.States.JumpToStepName("MENU_IDLE")

def Unlock_radiation_field(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Radiation Field")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837801)  # Dwayana (take quest)

    bot.Map.Travel(target_map_name="Rata Sum")
    bot.Move.XYAndExitMap(20340, 16899, target_map_name="Riven Earth")

    # This script used ApplyNow; keep it identical
    bot.Properties.ApplyNow("pause_on_danger", "active", True)
    bot.Properties.ApplyNow("halt_on_death", "active", True)
    bot.Properties.ApplyNow("movement_timeout", "value", 15000)
    bot.Properties.ApplyNow("hero_ai", "active", True)

    path=[(-21603.1,8285.9),
    (-21798.3,9288.2),
    (-21789.4,10290.0),
    (-21909.8,11293.0),
    (-22083.2,12295.0),
    (-21079.4,12098.4),
    (-20077.3,11811.3),
    (-19076.9,11615.3),
    (-18075.5,11247.0),
    (-17073.4,10500.9),
    (-16247.2,9500.6),
    (-15282.3,8499.2),
    (-14280.3,7593.8),
    (-13275.6,7853.4),
    (-12272.0,8145.0),
    (-11268.3,8416.7),
    (-10266.5,7814.2),
    (-9364.5,6812.3),
    (-8361.9,6094.6),
    (-7359.9,6144.0),
    (-6355.5,6385.9),
    (-5405.8,7386.0),
    (-4936.1,8388.2),
    (-4396.1,9390.1),
    (-3394.9,9932.9),
    (-2391.5,9843.4),
    (-1391.0,9588.0),
    (1618.8,8503.5),
    (2311.4,11804.0),
    (3313.1,12027.4),
    (4316.5,11849.2),
    (5316.6,12024.3),
    (6318.5,11885.3),
    (7320.1,11537.4),
    (8321.1,11136.9),
    (9321.7,10593.2),
    (10324.7,10049.8),
    (11326.2,9505.4),
    (14718.8,5965.5),
    (15255.1,4964.5),
    (15921.5,3964.5),
    (16391.0,2962.0),
    (16474.3,1958.2),
    (17130.1,955.1),
    (17756.3,-45.2),
    (18257.8,-1046.1),
    (19065.4,-2046.7),
    (19437.0,-3050.3),
    (19807.5,-4051.0),
    (20178.1,-5052.2),
    (20671.6,-6054.6),
    (20041.9,-5054.5),
    (19039.5,-5913.2),
    (18158.3,-6913.3),
    (17246.3,-7913.5),
    (16287.2,-8914.5),
    (15287.1,-9047.3),
    (14284.6,-9227.9),
    (13283.0,-9408.5),
    (12281.7,-9672.8),
    (11281.3,-9987.0),
    (10280.3,-10117.4),
    (9278.4,-10264.2),
    (8278.3,-10399.0),
    (7275.8,-10447.3),
    (6274.1,-10469.4),
    (5271.4,-10193.3),
    (4270.0,-9822.4),
    (3268.8,-9567.0),
    (2265.5,-9244.4),
    (1263.1,-8930.2),
    (261.3,-8352.1),
    (-740.2,-7670.2),
    (-1556.0,-6669.4),
    (-2414.9,-5668.4),
    (-3224.1,-4665.7),
    (-4227.5,-3773.8),
    ]
    bot.Move.FollowAutoPath(path)
    bot.Wait.UntilOutOfCombat()
    bot.Move.XY(-5226.4,-2772.8)
    bot.Wait.ForTime(10000)
    bot.Multibox.ResignParty()
    bot.Wait.UntilOutOfCombat()
    bot.Wait.ForMapLoad(target_map_name="Rata Sum")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837807)  # Reward
    bot.UI.CancelSkillRewardWindow()
    bot.States.JumpToStepName("MENU_IDLE")

def Unlock_mindbender(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Mindbender")
# a completer
    bot.States.JumpToStepName("MENU_IDLE")


def Unlock_technobabble(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Technobabble")

    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837B01)  # Lyssa (take quest)

    bot.Map.Travel(target_map_name="Rata Sum")
    bot.Move.XYAndExitMap(-6062, -2688, target_map_name="Magus Stones")
    # This script used ApplyNow; keep it identical
    bot.Properties.ApplyNow("pause_on_danger", "active", True)
    bot.Properties.ApplyNow("halt_on_death", "active", True)
    bot.Properties.ApplyNow("movement_timeout", "value", 15000)
    bot.Properties.ApplyNow("hero_ai", "active", True)
    path1=[(16333.0,13134.0),
    (15831.3,12689.2),
    (14826.0,12244.9),
    (13819.6,11800.6),
    (12815.3,11338.3),
    (12323.8,10334.1),
    (11980.6,9332.0),
    (10972.8,8700.9),
    (9966.2,8792.9),
    (8965.1,9574.6),
    (7958.7,10437.8),
    (7435.5,11444.1),
    (6956.4,12448.6),
    (6460.2,13452.2),
    (5804.7,14341.9),
    (4799.9,14136.0),
    (3795.5,13944.2),
    (2793.6,13807.8),
    (1791.5,13711.2),
    (787.7,14183.2),
    (-214.4,13677.2),
    (-737.5,12676.2),
    (-1511.9,11673.6),
    (-2135.2,10670.0),
    (-2655.5,9665.3),
    (-3659.5,9939.1),
    (-4665.0,9846.3),
    (-5668.2,9829.6),
    (-6672.9,10007.4),
    (-7178.3,9004.0),
    (-7180.2,8000.7),
    (-7533.2,9006.4),
    (-8537.4,9423.0),
    (-9538.6,9947.0),
    (-10539.4,10902.5),
    (-10997.0,11906.4),
    (-10826.9,12910.9),
    (-10739.5,13913.7),
    (-10731.4,14918.5),
    (-11405.8,16127.1),
    (-12410.1,15642.0),
    (-13412.0,15177.1),
    (-14418.9,14726.5),
    (-15421.4,14567.4),
    (-16426.4,14590.7),
    (-17430.9,14742.7),
    (-17579.8,13740.1),
    (-18287.3,14623.7),]
    bot.Move.FollowAutoPath(path1)
    bot.Wait.UntilOutOfCombat()
    path2 = list(reversed(path1))
    bot.Move.FollowAutoPath(path2)
    bot.Wait.UntilOutOfCombat()
    # This script used ApplyNow; keep it identical
    path3=[(16029.7,12397.9),
    (15026.6,12140.9),
    (14025.6,11883.9),
    (13371.9,10881.3),
    (12902.8,9874.1),
    (12694.8,8871.6),
    (12506.1,7866.6),
    (11497.3,7588.6),
    (10484.8,7371.9),
    (9480.5,6952.3),
    (9145.1,7044.0),
    (9620.1,6039.9),
    (10161.9,5033.7),
    (10405.3,4027.2),
    (10317.9,3024.2),
    (9724.4,2022.1),
    (8833.3,1015.3),
    (7832.5,507.9),
    (6830.2,23.6),
    (5824.7,-490.1),
    (4822.4,-1027.4),
    (3941.5,-1783.5),
    (2951.3,-2653.6),
    (2170.4,-3524.7),
    (1746.0,-4528.3),
    (1487.5,-5532.6),
    (1182.3,-6537.0),
    (1026.8,-7039.6)]
    bot.Move.FollowAutoPath(path3)
    bot.Wait.UntilOutOfCombat()
    bot.Wait.ForTime(10000)
    bot.Multibox.ResignParty()
    bot.Wait.ForMapLoad(target_map_name="Rata Sum")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837B07)  # Reward
    bot.UI.CancelSkillRewardWindow()
    bot.States.JumpToStepName("MENU_IDLE")


def Unlock_pain_inverter(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Pain Inverter")

    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837A01)  # Kormir (take quest)
    bot.Map.Travel(target_map_name="Vlox's Falls")
    bot.Move.XYAndExitMap(15505.38, 12460.59, target_map_name="Arbor Bay")    
    path=[(14323.3,10846.0),
        (12813.3,10172.5),
        (12706.6,8670.7),
        (12046.3,7170.5),
        (11401.4,5666.6),
        (11104.1,4165.7),
        (12380.1,2655.5),
        (13838.0,5496.0),                   #maybe need separe si point and add wait.fortime(5000) for the fight
        (13645.2,2661.5),
        (12136.8,1741.7),
        (10629.4,1175.4),
        (9118.9,404.5),
        (7617.1,708.9),
        (6114.2,1110.0),
        (4613.7,1104.7),
        (3324.0,2520.8),
        (2059.3,1018.5),
        (554.7,-202.7),                     #maybe need separe si point and add wait.fortime(5000) for the fight
        (-947.4,-1268.4),
        (-2451.0,-1768.3),
        (-3292.4,-3271.8),
        (-4334.0,-4776.2),
        (-5233.3,-6280.5),
        (-5660.5,-7790.6),
        (-4604.2,-9290.9),
        (-4368.7,-10796.7),
        (-5871.9,-11996.5),
        (-7377.8,-11568.5),
        (-8885.3,-10854.7),
        (-9333.4,-12357.6),                 #maybe need separe si point and add wait.fortime(5000) for the fight
        (-452.2,-13283.1),
        (371.6,-11782.2),
        (-149.9,-10277.5),                  #maybe need separe si point and add wait.fortime(5000) for the fight
        ]
    bot.Move.FollowAutoPath(path)
    bot.Wait.UntilOutOfCombat()
    bot.Wait.ForTime(10000)
    bot.Multibox.ResignParty()
    bot.Wait.ForMapLoad(target_map_name="Vlox's Falls")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837A07)  # Reward
    bot.UI.CancelSkillRewardWindow()
    bot.States.JumpToStepName("MENU_IDLE")

def Unlock_i_am_the_strongest(bot: Botting) -> None:
    #en cours !!!
    bot.States.JumpToStepName("MENU_IDLE")

def Unlock_previous_skills(bot: Botting) -> None:
    bot.States.AddHeader("[Unlock] Smooth Criminal")
    bot.Map.Travel(target_map_id=641)
    bot.Wait.ForMapLoad(target_map_id=641)

    # This script used ApplyNow; keep it identical
    bot.Properties.ApplyNow("pause_on_danger", "active", True)
    bot.Properties.ApplyNow("halt_on_death", "active", True)
    bot.Properties.ApplyNow("movement_timeout", "value", 15000)
    bot.Properties.ApplyNow("hero_ai", "active", True)

    bot.Move.XYAndDialog(25203, -10694, 0x837C01)  # Melandru (take quest)

    bot.Move.XY(18781, -10477)
    bot.Wait.ForMapLoad(target_map_name="Alcazia Tangle")

    # Spots / shrines route
    bot.Move.XY(17024, -600)
    bot.Move.XY(18237, 6691)     # res shrine 1
    bot.Move.XY(15518, 8375)
    bot.Move.XY(13200, 15000)    # Spot 1 confirmed
    bot.Wait.ForTime(3000)
    bot.Wait.UntilOutOfCombat()

    bot.Move.XY(19516, 4686)     # rez shrine 2 cliff
    bot.Move.XY(12184, 370)      # midway
    bot.Move.XY(4802, -4990)     # Rez Shrine 3
    bot.Move.XY(-8760, -3378)    # Rez Shrine 4
    bot.Move.XY(-5555, -2108)
    bot.Move.XY(-6678, 6477)     # Spot 2 confirmed (per script comment)
    bot.Wait.ForTime(3000)
    bot.Wait.UntilOutOfCombat()

    bot.Move.XY(-8860, -3178)    # Rez Shrine 4 again
    bot.Move.XY(-11202, 758)     # Spot 3 confirmed
    bot.Wait.ForTime(3000)
    bot.Wait.UntilOutOfCombat()

    bot.Multibox.ResignParty()
    bot.Wait.ForTime(3000)
    bot.Wait.ForMapLoad(target_map_id=641)

    bot.Move.XYAndDialog(25203, -10694, 0x837C07)  # Rewards
    bot.UI.CancelSkillRewardWindow()
    bot.States.AddHeader("[Unlock] Mental Block")
    bot.Properties.Enable("pause_on_danger")
    bot.Properties.Disable("halt_on_death")
    bot.Properties.Set("movement_timeout", value=-1)
    bot.Properties.Enable("hero_ai")

    bot.Move.XYAndDialog(25203, -10694, 0x837701)  # Balthazar (take quest)

    bot.Map.Travel(target_map_id=639)

    bot.Move.XY(-22999, 6530)
    bot.Wait.ForMapLoad(target_map_id=566)

    # 4 hunting spots
    bot.Move.XY(-9761, -8000)   # spot 1
    bot.Move.XY(7622,-9747) # spot 2
    bot.Move.XY(11690, -6215)   # spot 3
    bot.Move.XY(15918, -2667)   # spot 4
    

    bot.Wait.ForTime(3000)
    bot.Wait.UntilOutOfCombat()

    bot.Multibox.ResignParty()
    bot.Wait.ForMapLoad(target_map_id=639)

    bot.Map.Travel(target_map_id=641)

    bot.Move.XYAndDialog(25203, -10694, 0x837707)  # Rewards
    bot.UI.CancelSkillRewardWindow()
    bot.States.AddHeader("[Unlock] Radiation Field")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837801)  # Dwayana (take quest)

    bot.Map.Travel(target_map_name="Rata Sum")
    bot.Move.XYAndExitMap(20340, 16899, target_map_name="Riven Earth")

    # This script used ApplyNow; keep it identical
    bot.Properties.ApplyNow("pause_on_danger", "active", True)
    bot.Properties.ApplyNow("halt_on_death", "active", True)
    bot.Properties.ApplyNow("movement_timeout", "value", 15000)
    bot.Properties.ApplyNow("hero_ai", "active", True)

    path=[(-21603.1,8285.9),
    (-21798.3,9288.2),
    (-21789.4,10290.0),
    (-21909.8,11293.0),
    (-22083.2,12295.0),
    (-21079.4,12098.4),
    (-20077.3,11811.3),
    (-19076.9,11615.3),
    (-18075.5,11247.0),
    (-17073.4,10500.9),
    (-16247.2,9500.6),
    (-15282.3,8499.2),
    (-14280.3,7593.8),
    (-13275.6,7853.4),
    (-12272.0,8145.0),
    (-11268.3,8416.7),
    (-10266.5,7814.2),
    (-9364.5,6812.3),
    (-8361.9,6094.6),
    (-7359.9,6144.0),
    (-6355.5,6385.9),
    (-5405.8,7386.0),
    (-4936.1,8388.2),
    (-4396.1,9390.1),
    (-3394.9,9932.9),
    (-2391.5,9843.4),
    (-1391.0,9588.0),
    (1618.8,8503.5),
    (2311.4,11804.0),
    (3313.1,12027.4),
    (4316.5,11849.2),
    (5316.6,12024.3),
    (6318.5,11885.3),
    (7320.1,11537.4),
    (8321.1,11136.9),
    (9321.7,10593.2),
    (10324.7,10049.8),
    (11326.2,9505.4),
    (14718.8,5965.5),
    (15255.1,4964.5),
    (15921.5,3964.5),
    (16391.0,2962.0),
    (16474.3,1958.2),
    (17130.1,955.1),
    (17756.3,-45.2),
    (18257.8,-1046.1),
    (19065.4,-2046.7),
    (19437.0,-3050.3),
    (19807.5,-4051.0),
    (20178.1,-5052.2),
    (20671.6,-6054.6),
    (20041.9,-5054.5),
    (19039.5,-5913.2),
    (18158.3,-6913.3),
    (17246.3,-7913.5),
    (16287.2,-8914.5),
    (15287.1,-9047.3),
    (14284.6,-9227.9),
    (13283.0,-9408.5),
    (12281.7,-9672.8),
    (11281.3,-9987.0),
    (10280.3,-10117.4),
    (9278.4,-10264.2),
    (8278.3,-10399.0),
    (7275.8,-10447.3),
    (6274.1,-10469.4),
    (5271.4,-10193.3),
    (4270.0,-9822.4),
    (3268.8,-9567.0),
    (2265.5,-9244.4),
    (1263.1,-8930.2),
    (261.3,-8352.1),
    (-740.2,-7670.2),
    (-1556.0,-6669.4),
    (-2414.9,-5668.4),
    (-3224.1,-4665.7),
    (-4227.5,-3773.8),
    ]
    bot.Move.FollowAutoPath(path)
    bot.Wait.UntilOutOfCombat()
    bot.Move.XY(-5226.4,-2772.8)
    bot.Wait.ForTime(10000)
    bot.Multibox.ResignParty()
    bot.Wait.UntilOutOfCombat()
    bot.Wait.ForMapLoad(target_map_name="Rata Sum")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837807)  # Reward
    bot.UI.CancelSkillRewardWindow()

    bot.States.AddHeader("[Unlock] Asuran Scan")

    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837901)  # Grenth (take quest)

    bot.Map.Travel(target_map_name="Gadd's Encampment")
    bot.Move.XYAndExitMap(-9690, -19524, target_map_name="Sparkfly Swamp")
    # This script used ApplyNow; keep it identical
    bot.Properties.ApplyNow("pause_on_danger", "active", True)
    bot.Properties.ApplyNow("halt_on_death", "active", True)
    bot.Properties.ApplyNow("movement_timeout", "value", 15000)
    bot.Properties.ApplyNow("hero_ai", "active", True)

    path=[(-11165.4,-18283.9),    (-11328.1,-17780.3),    (-11384.3,-17280.2),    (-11334.4,-16778.1),    (-11299.2,-16276.2),    (-11329.3,-15772.8),    (-11316.9,-15269.3),    (-11349.1,-14767.7),    (-11348.2,-14267.3),    (-11384.4,-13765.5),    (-11316.9,-13265.2),    (-11233.8,-12765.2),    (-11150.5,-12263.8),    (-11067.2,-11762.9),    (-10896.6,-11260.0),    (-10667.6,-10758.3),    (-10461.4,-10258.3),    (-10254.9,-9757.7),    (-10064.7,-9256.7),    (-9835.3,-8756.4),    (-9718.4,-8251.5),    (-9640.7,-7750.0),    (-9561.5,-7249.7),    (-9512.5,-6749.1),    (-9480.4,-6248.2),    (-9458.3,-5743.9),    (-9469.2,-5241.0),    (-9559.7,-4740.4),    (-9232.6,-4238.3),    (-8888.4,-3737.5),    (-8548.9,-3233.5),    (-8232.0,-2729.6),    (-8124.7,-2227.3),    (-8145.7,-1727.3),    (-8172.7,-1223.1),    (-8213.0,-718.8),    (-8263.4,-217.4),    (-8315.9,285.3),    (-8388.2,789.5),    (-8511.6,1292.5),    (-8647.4,1797.6),    (-8766.6,2301.6),    (-9177.1,2804.6),    (-9641.8,3305.0),    (-9964.5,3809.8),    (-9928.1,4311.3),    (-9428.2,4814.2),    (-8927.0,5191.5),    (-8443.6,5693.6),    (-7941.2,5822.0),    (-7440.0,5904.8),    (-6935.2,5990.9),    (-6431.5,6070.9),    (-5925.0,6133.0),    (-5422.3,6192.9),    (-4917.6,6210.4),    (-4415.9,6234.1),    (-3914.2,6258.1),    (-3413.2,6288.2),    (-2911.0,6320.1),    (-2406.6,6352.2),    (-1902.5,6292.1),    (-1401.4,6104.2),    (-898.4,5923.1),    (-396.5,5874.6),    (107.0,5793.2),    (607.5,5705.9),    (1111.0,5617.4),    (1612.5,5529.3),    (2114.7,5559.1),    (2616.7,5820.9),    (3119.0,6102.4),    (3620.1,6494.9),    (4121.1,6888.0),    (4623.3,7275.8),    (5124.6,7435.8),    (5626.4,7537.5),    (6080.2,7037.3),    (6438.3,6533.6),    (6795.6,6031.0),    (7296.8,5720.0),    (7797.8,5498.1),    (8299.2,5427.9),    (8799.6,5350.6),    (9300.5,5511.6),    (9802.5,5812.5),    (10346.69,8246.0),    (10808.6,6189.0),    (11311.0,6333.2),    (11302.6,5831.4),    (11248.2,5330.4),    (11210.3,4828.7),    (11132.2,4326.2),    (11034.8,3821.7),    (10937.3,3320.5),   (10839.4,2817.3),    (10741.8,2315.8),    (10644.0,1813.2),    (10530.5,1311.6),    (10410.4,807.9),    (10264.4,304.8),    (10117.4,-196.6),    (10220.3,-697.2),    (10295.1,-1198.7),    (9793.1,-1453.9),    (9289.4,-1546.0),    (8787.0,-1543.4),    (8286.1,-1480.6),    (7785.1,-1417.8),    (7285.0,-1355.1),    (6779.9,-1303.0),    (6276.2,-1185.9),    (5774.2,-1006.9),    (5272.1,-1011.6),    (4769.0,-1198.1),    (4264.9,-1441.2),    (3764.1,-1665.9),    (3823.0,-2168.4),    (4325.4,-2468.7),    (4828.8,-2117.9),    (5331.0,-1838.1),    (5833.0,-1559.3),    (6319.6,-1055.8),    (6395.2,-554.3),    (6346.1,-53.7),    (6292.7,447.5),    (6241.4,950.9),    (6140.5,1451.3),    (6090.1,1953.7),    (6039.9,2455.2),    (5728.8,2957.0),    (5271.5,3458.7),    (4767.9,3612.2),    (4350.9,3108.4),    (3865.1,2604.3),    (3657.0,2100.5),    (3460.4,1598.3),(3360.7,1463.1)] #postion 1 
    bot.Move.FollowAutoPath(path)
    bot.Wait.UntilOutOfCombat()
    bot.Wait.ForTime(10000)  # wait for event to trigger
    bot.Multibox.ResignParty()
    bot.Wait.ForMapLoad(target_map_name="Gadd's Encampment")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837907)  # Reward
    bot.UI.CancelSkillRewardWindow()

    bot.States.AddHeader("[Unlock] Technobabble")

    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837B01)  # Lyssa (take quest)

    bot.Map.Travel(target_map_name="Rata Sum")
    bot.Move.XYAndExitMap(-6062, -2688, target_map_name="Magus Stones")
    # This script used ApplyNow; keep it identical
    bot.Properties.ApplyNow("pause_on_danger", "active", True)
    bot.Properties.ApplyNow("halt_on_death", "active", True)
    bot.Properties.ApplyNow("movement_timeout", "value", 15000)
    bot.Properties.ApplyNow("hero_ai", "active", True)
    path1=[(16333.0,13134.0),
    (15831.3,12689.2),
    (14826.0,12244.9),
    (13819.6,11800.6),
    (12815.3,11338.3),
    (12323.8,10334.1),
    (11980.6,9332.0),
    (10972.8,8700.9),
    (9966.2,8792.9),
    (8965.1,9574.6),
    (7958.7,10437.8),
    (7435.5,11444.1),
    (6956.4,12448.6),
    (6460.2,13452.2),
    (5804.7,14341.9),
    (4799.9,14136.0),
    (3795.5,13944.2),
    (2793.6,13807.8),
    (1791.5,13711.2),
    (787.7,14183.2),
    (-214.4,13677.2),
    (-737.5,12676.2),
    (-1511.9,11673.6),
    (-2135.2,10670.0),
    (-2655.5,9665.3),
    (-3659.5,9939.1),
    (-4665.0,9846.3),
    (-5668.2,9829.6),
    (-6672.9,10007.4),
    (-7178.3,9004.0),
    (-7180.2,8000.7),
    (-7533.2,9006.4),
    (-8537.4,9423.0),
    (-9538.6,9947.0),
    (-10539.4,10902.5),
    (-10997.0,11906.4),
    (-10826.9,12910.9),
    (-10739.5,13913.7),
    (-10731.4,14918.5),
    (-11405.8,16127.1),
    (-12410.1,15642.0),
    (-13412.0,15177.1),
    (-14418.9,14726.5),
    (-15421.4,14567.4),
    (-16426.4,14590.7),
    (-17430.9,14742.7),
    (-17579.8,13740.1),
    (-18287.3,14623.7),]
    bot.Move.FollowAutoPath(path1)
    bot.Wait.UntilOutOfCombat()
    path2 = list(reversed(path1))
    bot.Move.FollowAutoPath(path2)
    bot.Wait.UntilOutOfCombat()
    # This script used ApplyNow; keep it identical
    path3=[(16029.7,12397.9),
    (15026.6,12140.9),
    (14025.6,11883.9),
    (13371.9,10881.3),
    (12902.8,9874.1),
    (12694.8,8871.6),
    (12506.1,7866.6),
    (11497.3,7588.6),
    (10484.8,7371.9),
    (9480.5,6952.3),
    (9145.1,7044.0),
    (9620.1,6039.9),
    (10161.9,5033.7),
    (10405.3,4027.2),
    (10317.9,3024.2),
    (9724.4,2022.1),
    (8833.3,1015.3),
    (7832.5,507.9),
    (6830.2,23.6),
    (5824.7,-490.1),
    (4822.4,-1027.4),
    (3941.5,-1783.5),
    (2951.3,-2653.6),
    (2170.4,-3524.7),
    (1746.0,-4528.3),
    (1487.5,-5532.6),
    (1182.3,-6537.0),
    (1026.8,-7039.6)]
    bot.Move.FollowAutoPath(path3)
    bot.Wait.UntilOutOfCombat()
    bot.Wait.ForTime(10000)
    bot.Multibox.ResignParty()
    bot.Wait.ForMapLoad(target_map_name="Rata Sum")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837B07)  # Reward
    bot.UI.CancelSkillRewardWindow()

    bot.States.AddHeader("[Unlock] Pain Inverter")

    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837A01)  # Kormir (take quest)
    bot.Map.Travel(target_map_name="Vlox's Falls")
    bot.Move.XYAndExitMap(15505.38, 12460.59, target_map_name="Arbor Bay")    
    path=[(14323.3,10846.0),
        (12813.3,10172.5),
        (12706.6,8670.7),
        (12046.3,7170.5),
        (11401.4,5666.6),
        (11104.1,4165.7),
        (12380.1,2655.5),
        (13838.0,5496.0),                   #maybe need separe si point and add wait.fortime(5000) for the fight
        (13645.2,2661.5),
        (12136.8,1741.7),
        (10629.4,1175.4),
        (9118.9,404.5),
        (7617.1,708.9),
        (6114.2,1110.0),
        (4613.7,1104.7),
        (3324.0,2520.8),
        (2059.3,1018.5),
        (554.7,-202.7),                     #maybe need separe si point and add wait.fortime(5000) for the fight
        (-947.4,-1268.4),
        (-2451.0,-1768.3),
        (-3292.4,-3271.8),
        (-4334.0,-4776.2),
        (-5233.3,-6280.5),
        (-5660.5,-7790.6),
        (-4604.2,-9290.9),
        (-4368.7,-10796.7),
        (-5871.9,-11996.5),
        (-7377.8,-11568.5),
        (-8885.3,-10854.7),
        (-9333.4,-12357.6),                 #maybe need separe si point and add wait.fortime(5000) for the fight
        (-452.2,-13283.1),
        (371.6,-11782.2),
        (-149.9,-10277.5),                  #maybe need separe si point and add wait.fortime(5000) for the fight
        ]
    bot.Move.FollowAutoPath(path)
    bot.Wait.UntilOutOfCombat()
    bot.Wait.ForTime(10000)
    bot.Multibox.ResignParty()
    bot.Wait.ForMapLoad(target_map_name="Vlox's Falls")
    bot.Map.Travel(target_map_name="Tarnished Haven")
    bot.Move.XYAndDialog(25203, -10694, 0x837A07)  # Reward
    bot.UI.CancelSkillRewardWindow()

# -------------------------
    # Skill registry
# -------------------------
Skill = Tuple[str, str, str, str, Callable[[Botting], None], str]  # key,label,faction,step_name,fn,desc

RAW_SKILLS = [
    ('air_of_superiority', 'Air of Superiority', 'Asura', 'Unlock_air_of_superiority', 'Skill. (20...30 seconds). Gain a random Asura benefit every time you earn experience from killing an enemy.'),
    ('asuran_scan', 'Asuran Scan', 'Asura', 'Unlock_asuran_scan', 'Hex Spell. (9...12 seconds.) You cannot miss target foe. If you kill this foe, you lose 5% Death Penalty.'),
    ('Mental_Block', 'Mental Block', 'Asura', 'Unlock_mental_block', 'Enchantment Spell. (5...11 seconds.) You have a 50% chance to block. Renewal: every time an enemy hits you.'),
    ('mindbender', 'Mindbender', 'Asura', 'Unlock_mindbender', 'Enchantment Spell. (10...16 seconds.) You move 20...33% faster and cast Spells 20% faster.'),
    ('pain_inverter', 'Pain Inverter', 'Asura', 'Unlock_pain_inverter', 'Hex Spell. (6...10 seconds.) Deals 100...140% of the damage (maximum 80) back to target foe every time it does damage.'),
    ('radiation_field', 'Radiation Field', 'Asura', 'Unlock_radiation_field', 'Ward Spell. (5 seconds.) Causes -4...6 Health degeneration to foes in the area. End effect: inflicts Disease condition (12...20 seconds) to foes in the area.'),
    ('smooth_criminal', 'Smooth Criminal', 'Asura', 'Unlock_smooth_criminal', 'Spell. (10...20 seconds.) Disables one Spell. This skill becomes that Spell. You gain 5...10 Energy.'),
    ('summon_ice_imp', 'Summon Ice Imp', 'Asura', 'Unlock_summon_ice_imp', 'Spell. Summon a level 14...20 Ice Imp (40...60 lifespan) that has Ice Spikes. Only 1 Asura Summon can be active a time.'),
    ('summon_mursaat', 'Summon Mursaat', 'Asura', 'Unlock_summon_mursaat', 'Spell. Summon a level 14...20 Mursaat (40...60 lifespan) that has Enervating Charge. Only 1 Asura Summon can be active a time.'),
    ('summon_naga_shaman', 'Summon Naga Shaman', 'Asura', 'Unlock_summon_naga_shaman', 'Spell. Summon a level 14...20 Naga Shaman (40...60 lifespan) that has Stoning. Only 1 Asura Summon can be active a time.'),
    ('summon_ruby_djinn', 'Summon Ruby Djinn', 'Asura', 'Unlock_summon_ruby_djinn', 'Spell. Summon a level 14...20 Ruby Djinn (40...60 lifespan) that has Immolate. Only 1 Asura Summon can be active a time.'),
    ('technobabble', 'Technobabble', 'Asura', 'Unlock_technobabble', 'Spell. Deals 30...40 damage to target and adjacent foes. Inflicts Dazed condition (3...5 seconds) on these foes if target was not a boss.'),

    ('deft_strike', 'Deft Strike', 'Vanguard', 'Unlock_deft_strike', 'Ranged Attack. Deals 18...30 damage. Inflicts Bleeding condition (18...30 seconds) if target foe has Cracked Armor.'),
    ('ebon_battle_standard_of_courage', 'Ebon Battle Standard of Courage', 'Vanguard', 'Unlock_ebon_battle_standard_of_courage', 'Ward Spell. (14...20 seconds.) Allies in this ward have +24 armor and +24 more armor against Charr. Spirits are unaffected.'),
    ('ebon_battle_standard_of_honor', 'Ebon Battle Standard of Honor', 'Vanguard', 'Unlock_ebon_battle_standard_of_honor', 'Ward Spell. (14...20 seconds.) Allies in this ward deal +8...15 damage and +7...10 more damage against Charr. Spirits are unaffected.'),
    ('ebon_battle_standard_of_wisdom', 'Ebon Battle Standard of Wisdom', 'Vanguard', 'Unlock_ebon_battle_standard_of_wisdom', 'Ward Spell. (14...20 seconds.) Spells that allies in this ward cast have a 44...60% chance to recharge 50% faster. Spirits are unaffected.'),
    ('ebon_escape', 'Ebon Escape', 'Vanguard', 'Unlock_ebon_escape', 'Spell. Heals you and target ally for 70...110. Initial effect: Shadow Step to this ally. Cannot self-target.'),
    ('ebon_vanguard_assassin_support', 'Ebon Vanguard Assassin Support', 'Vanguard', 'Unlock_ebon_vanguard_assassin_support', 'Spell. Summon a level 14...20 assassin that has Iron Palm, Fox Fangs, and Nine Tail Strike; it Shadow Steps to this foe. If this foe is a Charr, the assassin lives for 24...30 seconds.'),
    ('ebon_vanguard_sniper_support', 'Ebon Vanguard Sniper Support', 'Vanguard', 'Unlock_ebon_vanguard_sniper_support', 'Spell. Deals 54...90 piercing damage and inflicts Bleeding condition (5...25 seconds). 10% chance of big bonus damage; more if target is a Charr.'),
    ('signet_of_infection', 'Signet of Infection', 'Vanguard', 'Unlock_signet_of_infection', 'Signet. Inflicts Diseased condition 13...20 seconds if target foe is Bleeding.'),
    ('sneak_attack', 'Sneak Attack', 'Vanguard', 'Unlock_sneak_attack', 'Melee Attack. Inflicts Blindness (5...8 seconds). Counts as a lead attack.'),
    ('tryptophan_signet', 'Tryptophan Signet', 'Vanguard', 'Unlock_tryptophan_signet', 'Signet. (14...20 seconds.) Target and adjacent foes move and attack 23...40% slower.'),
    ('weakness_trap', 'Weakness Trap', 'Vanguard', 'Unlock_weakness_trap', 'Trap. (90 seconds.) Affects nearby foes. Deals 24...50 lightning damage. Inflicts Weakness (10...20 seconds). Knocks-down Charr.'),
    ('winds', 'Winds', 'Vanguard', 'Unlock_winds', 'Ebon Vanguard Ritual. Creates a spirit (54...90 seconds). Affects foes within range. 15% chance to miss with ranged attacks.'),

    ('dodge_this', '"Dodge This!"', 'Norn', 'Unlock_dodge_this', 'Shout. (16...20 seconds.) Your next attack is unblockable and deals +14...20 damage.'),
    ('finish_him', '"Finish Him!"', 'Norn', 'Unlock_finish_him', 'Shout. Deals 44...80 damage and inflicts Cracked Armor and Deep Wound (12...20 seconds). No effect unless target < 50% HP.'),
    ('i_am_unstoppable', '"I Am Unstoppable!"', 'Norn', 'Unlock_i_am_unstoppable', 'Shout. (16...20 seconds.) You have +24 armor and cannot be knocked-down or Crippled.'),
    ('i_am_the_strongest', '"I Am the Strongest!"', 'Norn', 'Unlock_i_am_the_strongest', 'Shout. Your next 5...8 attacks deal +14...20 damage.'),
    ('you_are_all_weaklings', '"You Are All Weaklings!"', 'Norn', 'Unlock_you_are_all_weaklings', 'Shout. Inflicts Weakness (8...12 seconds). Also affects adjacent foes.'),
    ('you_move_like_a_dwarf', '"You Move Like a Dwarf!"', 'Norn', 'Unlock_you_move_like_a_dwarf', 'Shout. Deals 44...80 damage, knock-down, and inflicts Crippled (8...15 seconds).'),
    ('a_touch_of_guile', 'A Touch of Guile', 'Norn', 'Unlock_a_touch_of_guile', 'Touch Hex Spell. Deals 44...80 damage. Target cannot attack (5...8 seconds) if it was knocked-down.'),
    ('club_of_a_thousand_bears', 'Club of a Thousand Bears', 'Norn', 'Unlock_club_of_a_thousand_bears', 'Melee Attack. Deals +6...9 damage for each adjacent foe (max 60). Causes knock-down if target is non-human.'),
    ('feel_no_pain', 'Feel No Pain', 'Norn', 'Unlock_feel_no_pain', 'Skill. (30 seconds.) +2...3 regen. +200...300 max HP if drunk when activated.'),
    ('raven_blessing', 'Raven Blessing', 'Norn', 'Unlock_raven_blessing', 'Elite Form. Raven aspect (60 seconds). Attributes set to 0; replaces skills; 80 armor, ~660-700 HP.'),
    ('ursan_blessing', 'Ursan Blessing', 'Norn', 'Unlock_ursan_blessing', 'Elite Form. Bear aspect (60 seconds). Attributes set to 0; replaces skills; 100 armor, ~750-800 HP.'),
    ('volfen_blessing', 'Volfen Blessing', 'Norn', 'Unlock_volfen_blessing', 'Elite Form. Wolf aspect (60 seconds). Attributes set to 0; replaces skills; 80 armor, ~660-700 HP.'),

    ('by_urals_hammer', '"By Ural\'s Hammer!"', 'Deldrimor', 'Unlock_by_ural_s_hammer', 'Shout. (30 seconds.) Rez party in earshot with full HP/E. Party deals +25...33% dmg. They die when it ends (no DP).'),
    ('don_t_trip', '"Don\'t Trip!"', 'Deldrimor', 'Unlock_don_t_trip', 'Shout. (3...5 seconds.) Prevents knock-down; affects party within earshot.'),
    ('alkars_alchemical_acid', "Alkar's Alchemical Acid", 'Deldrimor', 'Unlock_alkar_s_alchemical_acid', 'Spell. Projectile: deals 40...50 damage. Deals extra vs Destroyers and inflicts Cracked Armor (14...20 seconds).'),
    ('black_powder_mine', 'Black Powder Mine', 'Deldrimor', 'Unlock_black_powder_mine', 'Trap. (90 seconds.) Deals 20...30 dmg. Inflicts Blindness and Bleeding (7...10 seconds).'),
    ('brawling_headbutt', 'Brawling Headbutt', 'Deldrimor', 'Unlock_brawling_headbutt', 'Touch Skill. Deals 45...70 damage; causes knock-down.'),
    ('breath_of_the_great_dwarf', 'Breath of the Great Dwarf', 'Deldrimor', 'Unlock_breath_of_the_great_dwarf', 'Spell. Removes burning and heals for 50...60 Health. Affects party members.'),
    ('drunken_master', 'Drunken Master', 'Deldrimor', 'Unlock_drunken_master', 'Stance. (72...90 seconds.) Move/attack faster; more if drunk.'),
    ('dwarven_stability', 'Dwarven Stability', 'Deldrimor', 'Unlock_dwarven_stability', 'Enchantment. (24...30 seconds.) Stances last longer. Cannot be knocked down if activated while drunk.'),
    ('ear_bite', 'Ear Bite', 'Deldrimor', 'Unlock_ear_bite', 'Touch. Deals 50...70 piercing dmg and inflicts Bleeding (15...25 seconds).'),
    ('great_dwarf_armor', 'Great Dwarf Armor', 'Deldrimor', 'Unlock_great_dwarf_armor', 'Enchantment. +24 armor and +60 max HP; extra vs Destroyers.'),
    ('great_dwarf_weapon', 'Great Dwarf Weapon', 'Deldrimor', 'Unlock_great_dwarf_weapon', 'Weapon Spell. +15...20 dmg and chance to KD. Cannot self-target.'),
    ('light_of_deldrimor', 'Light of Deldrimor', 'Deldrimor', 'Unlock_light_of_deldrimor', 'Spell. Holy dmg in area and pings hidden objects on compass.'),
    ('low_blow', 'Low Blow', 'Deldrimor', 'Unlock_low_blow', 'Touch. Deals 45...70 dmg. Extra dmg + Cracked Armor if target was knocked down.'),
    ('snow_storm', 'Snow Storm', 'Deldrimor', 'Unlock_snow_storm', "Spell. Deals cold damage each second (5 seconds). Hits foes adjacent to target's initial location."),
]

def _resolve_unlock_fn(fn_name: str, label: str) -> Callable[[Botting], None]:
    fn = globals().get(fn_name)
    if callable(fn):
        return fn # type: ignore
    return _placeholder_unlock(label)

def _build_skills() -> List[Skill]: # type: ignore
    skills: List[Skill] = [] # type: ignore
    for key, label, faction, fn_name, desc in RAW_SKILLS:
        step_name = f"SKILL:{faction}:{key}"
        fn = _resolve_unlock_fn(fn_name, label)
        skills.append((key, label, faction, step_name, fn, desc))
    return skills

SKILLS: List[Skill] = _build_skills() # type: ignore

FACTIONS = ("Asura", "Vanguard", "Norn", "Deldrimor")

CHECKPOINT_LABEL_OVERRIDES = {
    "IAU:TAKE_ANYTHING_YOU_CAN_DO": "Take Anything You Can Do",
    "IAU:HUNT_AVARR_AND_WHITEOUT": "Hunt Avarr and Whiteout",
    "IAU:FRAGMENT_OF_ANTIQUITIES": "Start Fragment of Antiquities",
    "IAU:CLAIM_ANYTHING_YOU_CAN_DO": "Claim Anything You Can Do",
    "IAU:COLD_AS_ICE": "Cold as Ice solo fight",
    "IAU:CLAIM_FINAL_REWARD": "Claim final reward",
}
_route_skill_index = 0
_route_step_index = 0
_route_previous_skill_index = -1


def _get_route_checkpoints():
    """Expose non-header FSM states grouped by their owning skill route."""
    cfg = getattr(bot, "config", None)
    fsm = getattr(cfg, "FSM", None) if cfg else None
    state_names = fsm.get_state_names() if fsm else []
    if not state_names:
        return []

    anchor_positions = {}
    for _, _, _, step_name, _, _ in SKILLS:
        try:
            anchor_positions[step_name] = state_names.index(step_name)
        except ValueError:
            continue

    routes = []
    ordered_anchors = [
        (skill, anchor_positions[skill[3]])
        for skill in SKILLS
        if skill[3] in anchor_positions
    ]
    for route_number, (skill, start_index) in enumerate(ordered_anchors):
        _, label, faction, step_name, _, _ = skill
        end_index = (
            ordered_anchors[route_number + 1][1]
            if route_number + 1 < len(ordered_anchors)
            else len(state_names)
        )

        checkpoints = []
        visible_step = 0
        for state_index in range(start_index, end_index):
            state_name = state_names[state_index]
            if state_name.startswith("[H]"):
                continue
            visible_step += 1
            display_name = (
                "Start entire route"
                if state_name == step_name
                else CHECKPOINT_LABEL_OVERRIDES.get(state_name, state_name)
            )
            checkpoints.append((f"{visible_step}. {display_name}", state_index, state_name))

        if checkpoints:
            routes.append((f"[{faction}] {label}", checkpoints))
    return routes

# -------------------------
# MAIN ROUTINE: build FSM once (BDS style)
# -------------------------
def skills_unlocker_routine(bot: Botting) -> None:
    bot.States.AddHeader(BOT_NAME)

    # MENU (idle anchor)
    bot.States.AddHeader("MENU")
    bot.States.AddCustomState(_anchor, "MENU_IDLE")
    bot.States.AddCustomState(_idle_forever, "MENU_IDLE_LOOP")  # the FSM will stay here until jump

    # Skills sections (each has a jumpable anchor)
    for key, label, faction, step_name, fn, desc in SKILLS:
        bot.States.AddHeader(f"[{faction}] {label}")
        bot.States.AddCustomState(_anchor, step_name)  # jump target
        fn(bot)  # enqueue actual steps

# set main routine once
bot.SetMainRoutine(skills_unlocker_routine)

try:
    import types
    import PyImGui
    from Py4GWCoreLib import Color
    from Py4GWCoreLib.ImGui import ImGui
    from Py4GWCoreLib.ImGui_src.IconsFontAwesome5 import IconsFontAwesome5
    from Py4GWCoreLib.Py4GWcorelib import ConsoleLog, Console
    from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE

    HIDE_BDS_HEADER = True
    # HIDE_BDS_HEADER = False   # <-- Uncomment this line to restore original BDS header

    if HIDE_BDS_HEADER:

        def _draw_main_child_minimal(self, main_child_dimensions=(350, 275), icon_path="", iconwidth=96):
            icon = IconsFontAwesome5.ICON_STOP_CIRCLE
            if PyImGui.button(icon + "  Stop##BotToggle"):
                    self._config.fsm_running = False
                    ConsoleLog(self._config.bot_name, "Script stopped", Console.MessageType.Info)
                    self._config.state_description = "Idle"
                    self._config.FSM.stop()
                    GLOBAL_CACHE.Coroutines.clear()
            PyImGui.dummy((0, 6))

        bot.UI._draw_main_child = types.MethodType(_draw_main_child_minimal, bot.UI)

except Exception:
    pass


def draw_portal_ui():
    global _route_skill_index, _route_step_index, _route_previous_skill_index

    PyImGui.text("Route Controls:")
    route_checkpoints = _get_route_checkpoints()
    if route_checkpoints:
        route_labels = [route_label for route_label, _ in route_checkpoints]
        _route_skill_index = max(0, min(_route_skill_index, len(route_checkpoints) - 1))
        _route_skill_index = PyImGui.combo("Route##SU_Route", _route_skill_index, route_labels)
        if _route_skill_index != _route_previous_skill_index:
            _route_step_index = 0
            _route_previous_skill_index = _route_skill_index

        checkpoints = route_checkpoints[_route_skill_index][1]
        checkpoint_labels = [label for label, _, _ in checkpoints]
        _route_step_index = max(0, min(_route_step_index, len(checkpoints) - 1))
        _route_step_index = PyImGui.combo(
            "Checkpoint##SU_Checkpoint", _route_step_index, checkpoint_labels
        )
        if PyImGui.button("Jump to checkpoint##SU_JumpCheckpoint"):
            _, checkpoint_index, checkpoint_state = checkpoints[_route_step_index]
            _stop_clear_start_and_jump(checkpoint_index, checkpoint_state)
        if _route_step_index > 0:
            PyImGui.text_wrapped(
                "Jumping ahead assumes all earlier quest objectives are already complete."
            )
    else:
        PyImGui.text_wrapped("Route steps are still being prepared.")
    PyImGui.separator()

    PyImGui.text("Select Skill:")
    PyImGui.separator()

    if PyImGui.begin_tab_bar("SU_Factions"):
        for faction in FACTIONS:
            if PyImGui.begin_tab_item(faction):
                _draw_skill_grid(faction)
                PyImGui.end_tab_item()
        PyImGui.end_tab_bar()

def _draw_skill_grid(faction: str):
    entries = [s for s in SKILLS if s[2] == faction]
    if not entries:
        PyImGui.text("No Skill")
        return

    icon_size = 48
    cols = 4
    c = 0

    for key, label, fac, step_name, fn, desc in entries:
        icon_path = os.path.join(ICONS_PATH, f"{key}.png")
        has_icon = os.path.exists(icon_path)

        if has_icon:
            clicked = ImGui.ImageButton(f"##{key}", icon_path, icon_size, icon_size)
        else:
            clicked = PyImGui.button(label, 260, 40)

        if clicked:
            _stop_clear_start_and_jump(step_name)   # stop/clear then start + jump

        if PyImGui.is_item_hovered():
            PyImGui.begin_tooltip()
            PyImGui.text(label)
            PyImGui.separator()
            PyImGui.text_wrapped(step_name)
            PyImGui.separator()
            PyImGui.text_wrapped(desc)
            PyImGui.end_tooltip()

        if has_icon:
            c += 1
            if c % cols != 0:
                PyImGui.same_line(0.0, -1.0)

# -------------------------
# Runtime entrypoints
# -------------------------
def main():
    _ensure_built()
    bot.Update()
    bot.UI.draw_window(
        icon_path=TEXTURE,
        main_child_dimensions=(280, 370),
        additional_ui=draw_portal_ui
    )

if __name__ == "__main__":
    main()
