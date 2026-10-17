"""EotN Storyline Bot - Multibox variant.

Sibling of ``Eotn storyline bot.py``. Storyline step order, NPC dialogs,
routes and quest ordering are identical to the solo bot; only the party layer
differs:

* No hero and no henchman party setups. Every hero/henchman ``CreateParty``
  call and every ``LoadHeroSkillbar`` call from the solo bot is gone.
* Every party formation is a real multibox formation: summon the other
  accounts, invite them, then travel them to the target outpost.

Account isolation is explicitly disabled. The run depends on cross-account
shared-memory commands (``TravelToMap``, ``InviteToParty``) being delivered,
and isolation gates exactly those commands through
``AllAccounts._can_communicate``; leaving it on would silently starve the
party-formation steps rather than fail loudly.

The step bodies below are carried over from the solo bot verbatim. Only the
``_prepare_standard_party_*`` helpers and the env helpers are replaced.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Sequence

import PySystem
from Py4GWCoreLib import (
    Agent,
    Attribute,
    ConsoleLog,
    GLOBAL_CACHE,
    Map,
    Player,
    Profession,
    Utils,
)
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.Context import GWContext
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Multiboxing_enums import SharedCommandType
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.FrameTree import Frame
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import (
    CONSUMABLE_UPKEEPS,
)
from Sources.ApoSource.ApoBottingLib import wrappers as BT

MODULE_ICON = 'Assets\\Textures\\Module_Icons\\eotn.png'
MODULE_NAME = "EotN Storyline BT - Multibox"
ICON_PATH = os.path.join(
    PySystem.Console.get_projects_path(),
    "Assets",
    "Textures",
    "Module_Icons",
    "eotn.png",
)
KAINENG_CENTER_MAP_ID = 194

# Party formation needs every account to finish a map load, so the summon and
# invite timeouts are deliberately wider than the solo bot's 15s default.
MULTIBOX_PARTY_TIMEOUT_MS = 30_000
MULTIBOX_TRAVEL_TIMEOUT_MS = 60_000

botting_tree: BottingTree | None = None
initialized = False


# ---------------------------------------------------------------------------
# Environment helpers
#
# Account isolation is pinned off. Note this is not cosmetic: the solo bot
# passes account_isolation=True and re-asserts it on every stage, so simply
# unticking the BottingTree UI checkbox does not survive a stage transition.
# Isolation off is what allows TravelToMap/InviteToParty to be delivered.
# ---------------------------------------------------------------------------

def _aggressive(name: str = "Configure Aggressive") -> BehaviorTree:
    return ensure_botting_tree().Config.Aggressive(
        multi_account=True,
        account_isolation=False,
        pause_on_danger=True,
        auto_loot=True,
        resurrection_scroll=True,
        reset_hero_ai=False,
    )


def _pacifist(name: str = "Configure Pacifist") -> BehaviorTree:
    return ensure_botting_tree().Config.Pacifist(
        multi_account=True,
        account_isolation=False,
        pause_on_danger=False,
        auto_loot=True,
        resurrection_scroll=True,
        reset_hero_ai=False,
    )


# ---------------------------------------------------------------------------
# Multibox party layer
#
# Replaces every hero/henchman setup in the solo bot. A "party setup" here
# means: put the local account in the target outpost, pull every other
# account to that same outpost, then invite them into the local party.
# ---------------------------------------------------------------------------


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
    """
    return BT.Sequence(
        name="Prepare Multibox Party",
        children=[
            _pacifist(),
            _travel_all_accounts(f"{refs_key}_travel"),
            _invite_all_accounts(f"{refs_key}_invite"),
        ],
    )


# Compatibility aliases so the storyline step bodies below stay byte-identical
# to the solo bot. Each name that used to build a hero+henchman party now forms
# a multibox party. The refs_key keeps each formation's shared-command refs
# separate in the blackboard.
def _prepare_standard_party() -> BehaviorTree:
    return _prepare_multibox_party("eotn_party_default")


def _prepare_standard_party_eotn() -> BehaviorTree:
    return _prepare_multibox_party("eotn_party_eotn")


def _prepare_standard_party_norn() -> BehaviorTree:
    return _prepare_multibox_party("eotn_party_norn")

def _use_bear_skill_4() -> BehaviorTree:
    return BT.Selector(
        name="Use Bear Skill 4 If Ready",
        children=[
            RoutinesBT.Skills.CastSkillSlot(
                slot=4,
                aftercast_delay=250,
                log=True,
            ),
            BT.Succeeder(name="Skip Bear Skill 4 If Unavailable"),
        ],
    )


def _select_and_equip_reward_skill(slot: int = 8) -> BehaviorTree:
    def _select() -> BehaviorTree.NodeState:
        reward_window = Frame.from_hash(792099697)

        if not reward_window.is_usable:
            ConsoleLog(
                MODULE_NAME,
                "Skill reward window was not found; continuing.",
                log=True,
            )
            return BehaviorTree.NodeState.SUCCESS

        skill_frame = reward_window.find_child(8 + int(slot))

        if skill_frame is None or not skill_frame.is_usable:
            ConsoleLog(
                MODULE_NAME,
                f"Skill reward slot {slot} was not found; continuing.",
                log=True,
            )
            return BehaviorTree.NodeState.SUCCESS


        skill_frame.mouse_action(5)

        return BehaviorTree.NodeState.SUCCESS

    def _equip() -> BehaviorTree.NodeState:
        equip_button = Frame.from_hash(1725534410)

        if not equip_button.is_usable:
            ConsoleLog(
                MODULE_NAME,
                "Reward skill equip button was not found; continuing.",
                log=True,
            )
            return BehaviorTree.NodeState.SUCCESS

        equip_button.click()
        return BehaviorTree.NodeState.SUCCESS

    return BT.Sequence(
        name=f"Select And Equip Reward Skill Slot {slot}",
        children=[
            BehaviorTree(
                BehaviorTree.ActionNode(
                    name=f"Select Reward Skill Slot {slot}",
                    action_fn=_select,
                    aftercast_ms=300,
                )
            ),
            BehaviorTree(
                BehaviorTree.ActionNode(
                    name="Equip Selected Reward Skill",
                    action_fn=_equip,
                    aftercast_ms=300,
                )
            ),
        ],
    )
def _pixel_stack() -> BehaviorTree:
    """Request distant multibox party members to stack on the leader."""

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        sender_email = Player.GetAccountEmail()
        current_map = Map.GetMapID()
        party_id = int(GLOBAL_CACHE.Party.GetPartyID() or 0)
        x, y = Player.GetXY()
        recipients: list[str] = []

        for account in GLOBAL_CACHE.ShMem.GetAllAccountData():
            if not account or account.AccountEmail == sender_email:
                continue
            if int(account.AgentData.Map.MapID or 0) != current_map:
                continue
            if int(account.AgentPartyData.PartyID or 0) != party_id:
                continue

            dx = float(x) - float(account.AgentData.Pos.x)
            dy = float(y) - float(account.AgentData.Pos.y)
            if dx * dx + dy * dy <= float(Range.Earshot.value) ** 2:
                continue

            recipients.append(str(account.AccountEmail))

        return RoutinesBT.Shared.SendCommand(
            command=SharedCommandType.PixelStack,
            params=(float(x), float(y), 0.0, 0.0),
            recipients=recipients,
            include_self=False,
            refs_blackboard_key="eotn_pixel_stack_refs",
            log=True,
        )

    return BT.Subtree(
        name="Pixel Stack Multibox Accounts",
        subtree_fn=_build,
    )


# ---------------------------------------------------------------------------
# Initialization and optional Hall of Monuments unlock
# ---------------------------------------------------------------------------


def InitializeBot() -> BehaviorTree:
    return BT.Sequence(
        name="Initialize EotN Storyline BT",
        children=[
            _aggressive(),
            BT.LogMessage(
                message="EotN Storyline BottingTree initialized.",
                module_name=MODULE_NAME,
            ),
        ],
    )

path_to_eotn = [
    (766,-20764),
    (-4234,-15585),
    (-6020,-13621),
    (-4145,-10496),
    (3266,-14782),
    (6838,-15585),
    (6302,-9960),
    (1391,-3442),
    (3802,-495),
    (1128,882),
]

def UnlockEyeOfTheNorthPool() -> BehaviorTree:
    """Optional one-time Hall of Monuments resurrection-pool unlock."""
    return BT.Sequence(
        name="Unlock Eye of the North Resurrection Pool",
        map_id_or_name=675,
        children=[
            _prepare_standard_party(),
            BT.MoveAndExitMap(Vec2f(4141, -27703), target_map_id=499),
            BT.Move(Vec2f(3598.97, -22331.73)),
            BT.Wait(10000),
            BT.MoveAndDialog(Vec2f(3537.00, -21937.00),0x839104),
            BT.VanquishNode(path_to_eotn),

            BT.MoveAndExitMap(Vec2f(-5198.0, 5595.0), target_map_id=646),
            BT.MoveAndDialog(Vec2f(-6572.70, 6588.83),0x800001),
            BT.Wait(2_000),
            BT.MoveAndDialog(Vec2f(-6662.00, 6584.00),0x63F),
            BT.Wait(6_000),
            BT.MoveAndDialog(Vec2f(-6572.70, 6588.83),0x89),
            BT.Wait(1_000),
            BT.WaitForMapLoad(map_id=646),
            BT.SendDialog(0x89),
            BT.SendDialog(0x831904),
            BT.MoveAndDialog(Vec2f(-6133.41, 5717.30), 0x838904),
            BT.MoveAndDialog(Vec2f(-5626.80, 6259.57), 0x839304),
        ],
    )


def ObtainStoryBook() -> BehaviorTree:
    return BT.Sequence(
        name="Obtain Story Book",
        map_id_or_name="Eye of the North outpost",
        children=[
            BT.MoveAndDialog(Vec2f(-1998.0, 2797.0), 0x1006912),
            BT.SendDialog(0x80)
        ],
    )


# ---------------------------------------------------------------------------
# Norn storyline
# ---------------------------------------------------------------------------


def TravelToGunnarsHold() -> BehaviorTree:
    return BT.Sequence(
        name="Run to Gunnar's Hold",
        map_id_or_name="Eye of the North outpost",
        children=[
            _prepare_standard_party_eotn(),
            _aggressive(),
            BT.MoveAndExitMap
                (Vec2f(1522.0, 464.0),target_map_id=499),
            BT.MoveAndDialog(Vec2f(2825.0, -481.0), 0x832801),
            BT.VanquishNode([
                (2548.84, 7266.08),
                (1233.76, 13803.42),
                (978.88, 21837.26),
                (-4031.0, 27872.0),
            ]),
            BT.WaitForMapLoad(map_id=548),
            BT.Move(Vec2f(14546.0, -6043.0)),
            BT.MoveAndExitMap(Vec2f(15578.0, -6548.0), target_map_id=644, log=True),
        ],
    )






def TravelToSifhalla() -> BehaviorTree:
    return BT.Sequence(
        name="Run to Sifhalla",
        map_id_or_name=644,
        children=[
            _prepare_standard_party_norn(),
            _aggressive(),
            BT.MoveAndExitMap(Vec2f(15193, -6387), target_map_name="Norrhart Domains"),
            BT.VanquishNode([
                (13337.167968, -3869.252929),
                (9826.771484, 416.337768),
                (6321.207031, 2398.933349),
                (2982.609619, 2118.243164),
                (176.124359, 2252.913574),
                (-3766.605468, 3390.211669),
                (-7325.385253, 2669.518066),
                (-9555.996093, 5570.137695),
                (-14153.492187, 5198.475585),
                (-18538.169921, 7079.861816),
                (-22717.630859, 8757.812500),
                (-25531.134765, 10925.241210),
                (-26333.171875, 11242.023437),
            ]),
            BT.WaitForMapLoad(map_name="Drakkar Lake"),
            BT.VanquishNode([
                (14399.201171, -16963.455078),
                (12510.431640, -13414.477539),
                (12011.655273, -9633.283203),
                (11484.183593, -5569.488769),
                (12456.843750, -411.864135),
                (13398.728515, 4328.439453),
                (14000.825195, 8676.782226),
                (14210.789062, 12432.768554),
                (13846.647460, 15850.121093),
                (13595.982421, 18950.578125),
                (13567.612304, 19432.314453),
            ]),
            BT.WaitForMapLoad(map_name="Sifhalla"),
        ],
    )


def CompleteTrackingTheNornbear() -> BehaviorTree:
    return BT.Sequence(
        name="Tracking the Nornbear",
        map_id_or_name="Sifhalla",
        children=[
            _prepare_standard_party_norn(),
            _aggressive(),
            BT.MoveAndDialog(Vec2f(14353.0, 23905.0), 0x84),
            BT.WaitForMapLoad(map_id=678),
            BT.Wait(2_000),
            BT.Move(Vec2f(10388.0, 23888.0)),
            BT.Wait(8_500),
            BT.WaitForMapLoad(map_name="Sifhalla", timeout_ms=50000),
            BT.MoveAndDialog(Vec2f(14353.0, 23905.0), 0x832807),
        ],
    )


def CompleteCurseOfTheNornbear() -> BehaviorTree:
    return BT.Sequence(
        name="Curse of the Nornbear",
        map_id_or_name="Sifhalla",
        children=[
            _prepare_standard_party_norn(),
            _aggressive(),
            BT.MoveAndDialog(Vec2f(14353.0, 23905.0), 0x86),
            BT.WaitForMapLoad(map_id=653),
            BT.Wait(2_000),
            BT.Move(Vec2f(-2638.0, 20433.0)),
            BT.Wait(5_000),
            BT.Move(Vec2f(-5793.0, 15818.0)),
            BT.Wait(2_000),
            BT.Move(Vec2f(8105.0, 14089.0)),
            BT.Wait(2_000),
            BT.Move(Vec2f(4940.0, 6551.0)),
            BT.WaitForMapLoad(map_id=643,timeout_ms=60000),
            BT.Wait(2_000),
            BT.Move(Vec2f(14353.0, 23905.0)),
            _pacifist(),
            BT.MoveAndDialog(Vec2f(14353.0, 23905.0), 0x838904),
            BT.AutoDialog(0x89),
            BT.AutoDialog(0x8A),
        ],
    )


def BloodWashesBlood() -> BehaviorTree:
    return BT.Sequence(
        name="Blood Washes Blood",
        map_id_or_name="Sifhalla",
        children=[
            _aggressive(),
            BT.VanquishNode([(16163.0, 22852.0), (16717.0, 22789.0)]),
            BT.WaitForMapLoad(map_name="Jaga Moraine"),
            BT.VanquishNode([
                (-11949.0, -23710.0),
                (-8929.0, -21112.0),
                (-6111.0, -14675.0),
                (-5757.0, -13735.0),
                (-4855.0, -10881.0),
                (-3702.0, -8096.0),
                (-2962.0, -7412.0),
                (-1397.0, -6161.0),
                (1055.0, -3190.0),
                (2170.0, -397.0),
                (2659.0, 484.0),
                (3151.0, 1355.0),
                (3726.0, 4064.0),
                (4621.0, 5918.0),
            ]),
            _pacifist(),
            BT.MoveAndDialog(Vec2f(4621.0, 5918.0), 0x832001),
            _aggressive(),
            BT.VanquishNode([
                (3014.0, 3308.0),
                (-567.0, -1090.0),
                (5147.0, -5920.0),
                (10490.0, -9516.0),
                (11885.0, -16663.0),
                (9771.0, -21332.0),
            ]),
            BT.Wait(80_000),
            BT.Move(Vec2f(9221.0, -21462.0)),
            _pacifist(),
            BT.MoveAndDialog(Vec2f(9504.0, -21390.0), 0x832007),
            BT.MoveAndDialog(Vec2f(9688.0, -21012.0), 0x84),
            BT.MoveAndExitMap(Vec2f(16045.0, -20642.0),target_map_name="Blood Washes Blood"),
            _aggressive(),
            BT.VanquishNode([
                (419.0, -3059.0),
                (-2083.0, 1061.0),
                (1742.0, 4963.0),
                (228.0, 10003.0),
                (3266.0, 12358.0),
                (3299.0, 13489.0),
                (365.0, 13684.0),
                (2752.0, 13410.0),
                (2258.0, 14533.0),
                (1446.0, 15008.0),
                (127.0, 14203.0),
                (13.0, 13430.0),
                (795.0, 13120.0),
                (1519.0, 13251.0),
                (940.0, 14144.0),
            ]),
            _pacifist(),
            BT.MoveAndInteract(Vec2f(942.0, 14172.0), log=True),
            BT.MoveAndInteract(Vec2f(942.0, 14172.0), log=True),
            _select_and_equip_reward_skill(8),
            _use_bear_skill_4(),
            _aggressive(),
            BT.VanquishNode([
                (2360.0, 13448.0),
                (9167.0, 11874.0),
                (11309.0, 11588.0),
                (11886.0, 10714.0),
                (13453.0, 8619.0),
                (15097.0, 5363.0),
            ]),
            _use_bear_skill_4(),
            BT.VanquishNode([
                (16024.0, 3473.0),
                (16766.0, 5052.0),
                (18332.0, 3893.0),
                (17662.0, 3049.0),
                (17960.0, 2005.0),
                (16668.0, 1509.0),
                (17388.0, -205.0),
                (15749.0, 167.0),
                (15724.0, -2018.0),
            ]),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.WaitForMapLoad(map_name="Gunnar's Hold"),
        ],
    )


def TravelToOlafstead() -> BehaviorTree:
    return BT.Sequence(
        name="Run to Olafstead",
        map_id_or_name="Sifhalla",
        children=[
            _prepare_standard_party_norn(),
            _aggressive(),
            BT.MoveAndExitMap(Vec2f(13663.0, 18683.0), target_map_name="Drakkar Lake"),
            BT.VanquishNode([
                (13856.0, 5241.0),
                (9243.0, -3148.0),
                (10291.0, -14402.0),
                (7425.0, -19995.0),
                (4769.0, -23840.0),
                (6651.0, -26797.0),
            ]),
            BT.WaitForMapLoad(map_name="Varajar Fells"),
            BT.VanquishNode([
                (8582.0, 11620.0),
                (5853.0, 10407.0),
                (1972.0, 12954.0),
                (-696.0, 8467.0),
                (-90.0, 6162.0),
                (-2940.0, 3979.0),
                (-4395.0, 341.0),
                (-4759.0, -3843.0),
                (-3712.0, -4655.0),
                (-2911.0, -3789.0),
                (-2351.0, -3477.0),
                (-3126.0, -2708.0),
                (-3074.0, -55.0),
                (-1777.0, 1319.0),
                (-670.0, 1382.0),
            ]),
            BT.WaitForMapLoad(map_name="Olafstead"),
        ],
    )


def CompleteShrineOfRavenSpirit() -> BehaviorTree:
    return BT.Sequence(
        name="Shrine of the Raven Spirit",
        map_id_or_name="Olafstead",
        children=[
            _prepare_standard_party_norn(),
            BT.MoveAndDialog(Vec2f(132.0, -684.0), 0x832E01),
            _aggressive(),
            BT.MoveAndExitMap(Vec2f(-1392.0, 1205.0), target_map_id=553),
            BT.VanquishNode([
                (-2252.0, 831.0),
                (-2887.0, -2894.0),
                (-3211.0, -3843.0),
                (-3940.0, -3155.0),
                (-4941.0, 728.0),
                (-5310.0, 3693.0),
                (-8984.0, 4861.0),
                (-12866.0, 5695.0),
                (-13612.0, 6369.0),
                (-14355.0, 7040.0),
                (-14909.0, 7880.0),
                (-15520.0, 8680.0),
            ]),
            BT.MoveAndDialog(Vec2f(-15696.0, 8732.0), 0x85),
            BT.WaitForClearEnemiesInArea(-15696.0, 8732.0, radius=Range.Spirit.value, stable_clear_ms=180000),
            BT.Travel(target_map_name="Olafstead"),
            BT.MoveAndDialog(Vec2f(132.0, -684.0), 0x832E07),
            BT.Wait(2000),
            
        ],
    )


def CompleteAGateTooFar() -> BehaviorTree:
    return BT.Sequence(
        name="A Gate Too Far",
        map_id_or_name="Olafstead",
        children=[
            _prepare_standard_party_norn(),
            BT.MoveAndDialog(Vec2f(132.0, -684.0), 0x86),
            BT.WaitForMapToChange(map_id=655, timeout_ms=5_000),
            _aggressive(),
            BT.VanquishNode([
                (-8731,-5078),
                (-8020,-3123),
                (-6013,-3073),
                (-4692,-2598),
                (-4282,-1773),
                (-4536,737),
                (-6193,1490),
            ],move_tolerance=800),
            BT.VanquishNode([
    (-6243,6484),
    (-7508,7340),
    (-8324,4864),
    (-5239,3585),
],log=True),
            BT.WaitForClearEnemiesInArea(
                            -6243,6484,
                            radius=Range.Spirit.value,
                            allowed_alive_enemies=0,
                            interact_interval_ms=750,
                            stable_clear_ms=20_000,
                            keep_player_near_center=False,
                            center_tolerance=750.0,
                            log=True,
                        ),            
            BT.VanquishNode([(-18697.0, 9416.0), (-20211.0, 9897.0)]),
            BT.WaitForMapLoad(map_id=656),
            BT.Wait(2_000),
            BT.Move(Vec2f(17054.0, 6568.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(13357.0, 11594.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(11271.0, 17040.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(5244.0, 17207.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(3249.0, 17858.0)),
            BT.WaitForMapLoad(map_id=657),
            BT.Wait(2_000),
            BT.Move(Vec2f(6360.0, 16486.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(5233.0, 12570.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(6210.0, 10139.0)),
            BT.Move(Vec2f(6716.0, 6344.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(7702.0, 4015.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(7510.0, 2854.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.WaitForMapLoad(map_id=645),
            BT.Wait(2_000),
        ],
    )


# ---------------------------------------------------------------------------
# Ebon Vanguard storyline
# ---------------------------------------------------------------------------


def AdvanceToLongeyeEdge() -> BehaviorTree:
    return BT.Sequence(
        name="Advance to Longeye's Edge",
        map_id_or_name=644,
        children=[
            _aggressive(),
            BT.VanquishNode([
                (15886.204101, -6687.815917),
                (15183.199218, -6381.958984),
            ]),
            BT.WaitForMapLoad(map_id=548),
            BT.VanquishNode([
                (14233.820312, -3638.702636),
                (14944.690429, 1197.740966),
                (14855.548828, 4450.144531),
                (17964.738281, 6782.413574),
                (19127.484375, 9809.458984),
                (21742.705078, 14057.231445),
                (19933.869140, 15609.059570),
                (16294.676757, 16369.736328),
                (16392.476562, 16768.855468),
            ]),
            BT.WaitForMapLoad(map_id=482),
            BT.VanquishNode([
                (-11232.550781, -16722.859375),
                (-7655.780273, -13250.316406),
                (-6672.132324, -13080.853515),
                (-5497.732421, -11904.576171),
                (-3598.337646, -11162.589843),
                (-3013.927490, -9264.664062),
                (-1002.166198, -8064.565429),
                (3533.099609, -9982.698242),
                (7472.125976, -10943.370117),
                (12984.513671, -15341.864257),
                (17305.523437, -17686.404296),
                (19048.208984, -18813.695312),
                (19634.173828, -19118.777343),
            ]),
            BT.WaitForMapLoad(map_id=650),
        ],
    )


def SearchForTheEbonVanguard() -> BehaviorTree:
    return BT.Sequence(
        name="Search for the Ebon Vanguard",
        map_id_or_name=650,
        children=[
            BT.MoveAndDialog(Vec2f(-25160.0, 13505.0), 0x831801),
            _aggressive(),
            BT.MoveAndExitMap(Vec2f(-21502.0,12458.0),target_map_name="Grothmar Wardowns"),
            BT.VanquishNode([(-14000.0, 4297.0), (-9580.0, -2860.0)]),
            _pacifist(),
            BT.MoveAndDialog(Vec2f(-9580.0, -2860.0), 0x831807),
            BT.AutoDialog(0x84),
            BT.AutoDialog(0x84),
            BT.WaitForMapLoad(map_id=665),
            _aggressive(),
            BT.VanquishNode([
                (5221.0, -3019.0),
                (18715.0, -3896.0),
                (20010.0, -66.0),
                (17938.0, 2493.0),
                (19705.0, 3742.0),
            ]),
            BT.WaitForMapLoad(map_id=649),
            _pacifist(),
            BT.MoveAndDialog(Vec2f(19106.0, 413.0), 0x838C01),
            _aggressive(),
            BT.VanquishNode([
                (11484.0, 1898.0),
                (11388.0, 4143.0),
                (23634.0, 15333.0),
            ]),
            BT.MoveAndExitMap(Vec2f(25604.0, 15412.0), target_map_id=647),
            BT.VanquishNode([
                (-13181.0, 3067.0),
                (-14576.0, 10999.0),
                (-15193.0, 13347.0),
            ]),
            BT.MoveAndInteractWithGadget(Vec2f(-15369.0, 13087.0)),
            BT.Move(Vec2f(-17533.0, 14473.0)),
            BT.Move(Vec2f(-16740.0, 17124.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.WaitForMapLoad(map_id=648),
            BT.MoveAndDialog(Vec2f(-19090.86, 18003.03), 0x838C07),
        ],
    )


def WarbandOfBrothers() -> BehaviorTree:
    """Complete all three levels; the legacy level-3 indentation is fixed."""
    return BT.Sequence(
        name="Warband of Brothers",
        map_id_or_name=648,
        children=[
            _aggressive(),
            BT.MoveAndDialog(Vec2f(-19094.0, 17945.0), 0x84),
            BT.WaitForMapLoad(map_id=666),
            BT.AddModelToLootWhitelist(24628),
            BT.VanquishNode([
                (-13404.0, -2958.0),
                (-7696.0, 4576.0),
                (-5939.0, 3668.0),
                (-7823.0, 6395.0),
                (-5790.0, 7957.0),
                (-4799.0, 6891.0),
                (-9905.0, 5280.0),
                (-13153.0, 3346.0),
                (-4600.0, 6494.0),
            ]),
            BT.LootItems(distance=Range.Spirit.value),
            BT.MoveAndInteractWithGadget(Vec2f(-4043.76, 6405.57), log=True),
            BT.Wait(2_000),
            BT.VanquishNode([
                (-1959.15, 7955.19),
                (1490.38, 8409.88),
                (3217.90, 8404.31),
                (-4608.37, 6540.96),
                (-16482.0, 1716.68),
                (-18616.02, 806.14),
                (-19704.0, 318.0),
            ]),
            BT.WaitForMapLoad(map_id=667),
            BT.AddModelToLootWhitelist(24628),
            BT.VanquishNode([
                (-3290.88, 15187.92),
                (-1760.07, 12088.74),
                (-475.83, 11932.78),
                (-2164.81, 11785.08),
                (-2061.81, 12930.91),
                (-2407.16, 14068.22),
                (-2030.78, 12776.65),
            ]),
            BT.LootItems(distance=Range.Spirit.value),
            BT.MoveAndInteractWithGadget(Vec2f(-2254.0, 11176.0), log=True),
            BT.VanquishNode([
                (-2404.72, 9076.48),
                (-1563.08, 11763.31),
                (6634.50, 17973.61),
                (7429.30, 13458.01),
                (13162.54, 9219.06),
                (15923.27, 8823.71),
                (16782.0, 8642.0),
            ]),
            BT.WaitForMapLoad(map_id=668),
            BT.AddModelToLootWhitelist(24628),
            BT.VanquishNode([
                (17337.79, -5963.91),
                (16669.06, -4763.91),
                (16089.83, -3724.50),
                (17007.08, -5518.76),
                (17159.0, -6461.0),
            ]),
            BT.LootItems(distance=Range.Spirit.value),
            BT.MoveAndInteractWithGadget(Vec2f(17159.0, -6461.0), log=True),
            BT.Wait(2_000),
            BT.VanquishNode([
                (17808.17, -9149.82),
                (18827.79, -10402.15),
                (18742.40, -12129.31),
                (18194.92, -14704.77),
                (18334.16, -13903.64),
                (18704.73, -12773.99),
                (18284.53, -14134.07),
            ]),
            BT.LootItems(distance=Range.Spirit.value),
            BT.MoveAndInteractWithGadget(Vec2f(18147.0, -14974.0), log=True),
            BT.Wait(2_000),
            BT.VanquishNode([
                (14379.01, -15352.70),
                (10392.54, -14173.80),
                (9714.57, -12360.55),
                (8907.67, -11354.53),
                (8425.21, -9845.09),
                (8900.77, -10740.29),
                (9908.98, -12902.71),
            ]),
            BT.LootItems(distance=Range.Spirit.value),
            BT.MoveAndInteractWithGadget(Vec2f(10034.0, -14899.0), log=True),
            BT.Wait(2_000),
            BT.VanquishNode([
                (7685.12, -16387.24),
                (3930.38, -13150.31),
                (1072.90, -8136.26),
            ]),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.WaitForMapLoad(map_id=648),
        ],
    )


def WhatMustBeDone() -> BehaviorTree:
    return BT.Sequence(
        name="What Must Be Done",
        map_id_or_name=648,
        children=[
            _aggressive(),
            BT.MoveAndDialog(Vec2f(-14185.0, 17040.0), 0x838D01),
            BT.MoveAndExitMap(Vec2f(-15479.0, 13484.0), target_map_id=647),
            BT.VanquishNode([
                (-12085.0, 8447.0),
                (-9360.0, -298.0),
                (-6856.0, -7620.0),
                (-7908.02, -7825.38),
            ]),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Travel(target_map_id=648),
            BT.MoveAndDialog(Vec2f(-14185.0, 17040.0), 0x84),
            BT.WaitForMapLoad(map_id=674),
            BT.Move(Vec2f(-16946.0, 17319.0)),
            BT.WaitForMapLoad(map_id=648),
            BT.MoveAndDialog(Vec2f(-14185.0, 17040.0), 0x838D07),
        ],
    )


def AssaultOnTheStrongHold() -> BehaviorTree:
    return BT.Sequence(
        name="Assault on the Stronghold",
        map_id_or_name=648,
        children=[
            _aggressive(),
            BT.MoveAndExitMap(Vec2f(-15479.0, 13484.0), target_map_id=647),
            BT.MoveAndDialog(Vec2f(-13849.0, 11217.0), 0x84),
            BT.WaitForMapLoad(map_id=669),
            BT.VanquishNode([(5203.0, 12344.0), (5843.0, 9145.0)]),
            BT.MoveAndDialog(Vec2f(5843.0, 9145.0), 0x84),
            BT.MoveAndDialog(Vec2f(5203.0, 12344.0), 0x84),
            BT.Move(Vec2f(936.0, 10709.0)),
            BT.Wait(30_000),
            BT.VanquishNode([
                (-1671.0, 11103.0),
                (-4202.0, 11045.0),
                (-6271.0, 12087.0),
                (-6896.0, 13899.0),
                (-6393.0, 9770.0),
                (-6895.0, 8102.0),
            ]),
            BT.WaitForMapLoad(map_id=649),
            BT.MoveAndDialog(Vec2f(-21069.0, 12353.0), 0x831907),
        ],
    )


def UnlockBattleHonorStandSkill() -> BehaviorTree:
    """Optional legacy side quest retained as an addable BT step."""
    return BT.Sequence(
        name="Unlock Battle Honor Stand Skill",
        children=[
            BT.MoveAndDialog(Vec2f(-21141.81, 12378.68), 0x836001),
            BT.VanquishNode([
                (-21593.0, 12517.0),
                (-20064.0, 11212.0),
                (-18659.0, 9768.0),
                (-17352.0, 8246.0),
                (-16126.0, 6640.0),
                (-14663.0, 5256.0),
                (-13347.0, 3732.0),
                (-11993.0, 2247.0),
                (-11088.0, 402.0),
                (-9414.0, -699.0),
                (-7532.0, 132.0),
                (-5576.0, -322.0),
                (-3621.0, -814.0),
                (-1677.0, -1304.0),
                (177.0, -2140.0),
                (1759.0, -3373.0),
                (3730.0, -3747.0),
                (5650.0, -4349.0),
                (7421.0, -5292.0),
                (8547.0, -6957.0),
                (10587.0, -6733.0),
                (12591.0, -6583.0),
                (14521.0, -7151.0),
                (16095.0, -8448.0),
                (17681.0, -9721.0),
                (19282.0, -11005.0),
                (20765.0, -12412.0),
                (22538.0, -13411.0),
                (23410.0, -13901.0),
            ]),
            BT.WaitForMapLoad(map_id=651),
            BT.VanquishNode([
                (-17861.0, 16317.0),
                (-16404.0, 14900.0),
                (-16459.0, 12851.0),
                (-17542.0, 11132.0),
                (-17939.0, 9166.0),
                (-16308.0, 7932.0),
                (-15150.0, 6294.0),
                (-14010.0, 4577.0),
                (-13622.0, 2552.0),
                (-13094.0, 598.0),
                (-11367.0, -490.0),
                (-9393.0, -831.0),
                (-7616.0, -1762.0),
                (-5677.0, -2456.0),
                (-4372.0, -4015.0),
                (-3143.0, -5620.0),
                (-2954.0, -7657.0),
                (-2423.0, -9586.0),
                (-593.0, -10426.0),
                (1413.0, -10033.0),
                (3432.0, -9958.0),
                (4945.0, -8637.0),
                (6962.0, -8362.0),
                (8991.0, -8392.0),
                (4471.0, -7294.0),
                (6525.0, -7403.0),
                (8415.0, -8062.0),
                (10082.0, -9228.0),
                (11715.0, -8045.0),
            ]),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Travel(target_map_id=650),
            BT.Move(Vec2f(-21902.0, 12807.0)),
            BT.WaitForMapLoad(map_id=649),
            BT.MoveAndDialog(Vec2f(-21141.81, 12378.68), 0x836007),
        ],
    )


# ---------------------------------------------------------------------------
# Asuran storyline
# ---------------------------------------------------------------------------


def FindingGadd() -> BehaviorTree:
    return BT.Sequence(
        name="Finding Gadd",
        map_id_or_name=624,
        children=[
            BT.MoveAndDialog(Vec2f(16363.0, 15909.0), 0x833301),
            BT.Travel(target_map_id=638),
            _aggressive(),
            BT.Move(Vec2f(-8755.0, -23240.0)),
            BT.MoveAndDialog(Vec2f(-8295.0, -23572.0), 0x833304),
            BT.VanquishNode([
                (-8755.0, -23240.0),
                (-9888.17, -22106.70),
            ]),
            BT.MoveAndExitMap(Vec2f(-9690.0, -19524.0), target_map_id=558),
            BT.VanquishNode([
                (-4466.15, -21025.91),
                (-6967.77, -19810.06),
                (11669.0, -23829.0),
            ]),
            BT.MoveAndDialog(Vec2f(11881.0, -23802.0), 0x833304),
            BT.VanquishNode([(8017.92, -20124.24), (11184.85, -14188.88)]),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Wait(5_000),
            BT.Move(Vec2f(-5740.47, -13723.29)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Wait(5_000),
            BT.Move(Vec2f(2417.11, -25444.55)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Wait(5_000),
            BT.Move(Vec2f(11758.78, -24063.51)),
            BT.Wait(20_000),
            BT.VanquishNode([
                (Vec2f(12236.58, -24474.01)),
                (Vec2f(11675.35, -23909.45)),
            ]),
            BT.AutoDialog(0x833304),
            BT.Wait(10_000),
            BT.Move(Vec2f(11795.0, -24125.0)),
            BT.AutoDialog(0x833307),
        ],
    )


def FindingTheBloodstone() -> BehaviorTree:
    return BT.Sequence(
        name="Finding the Bloodstone",
        map_id_or_name=638,
        children=[
            _aggressive(),
            BT.Move(Vec2f(-9888.17, -22106.70)),
            BT.MoveAndExitMap(Vec2f(-9690.0, -19524.0), target_map_id=558),
            BT.VanquishNode([(-6967.77, -19810.06), (11669.0, -23829.0)]),
            BT.MoveAndDialog(Vec2f(11795.0, -24125.0), 0x833307),
            BT.AutoDialog(0x84),
            BT.WaitForMapLoad(map_id=661),
            BT.VanquishNode([
                (12437.0, 16557.0),
                (12588.0, 14755.0),
                (15387.0, 6941.0),
            ]),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Wait(10_000),
            BT.VanquishNode([
                (16165.77, 10441.95),
                (17149.38, 13434.60),
                (18529.0, 15977.0),
                (18170.14, 15771.52),
            ]),
            BT.Wait(30_000),
            BT.MoveAndExitMap(Vec2f(19212.0, 16155.0), target_map_id=662),
            BT.VanquishNode([
                (-611.51, 5115.83),
                (3574.70, 3567.62),
                (4827.10, 1968.97),
                (11548.76, -2795.90),
                (14596.0, -7708.0),
            ]),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Wait(10_000),
            BT.Move(Vec2f(16743.0, -10170.0)),
            BT.Wait(30_000),
            BT.MoveAndExitMap(Vec2f(18450.0, -10273.0), target_map_id=663),
            BT.VanquishNode([
                (-7249.0, -16397.0),
                (-10466.0, -16166.0),
                (-15377.0, -16565.0),
            ]),
            BT.WaitForMapLoad(map_id=638),
        ],
    )


def LabSpace() -> BehaviorTree:
    return BT.Sequence(
        name="Lab Space",
        map_id_or_name=624,
        children=[
            _aggressive(),
            #BT.MoveAndDialog(Vec2f(16202.0, 16092.0)),
            BT.Travel(target_map_id=640),
           # BT.MoveAndDialog(Vec2f(16024.0, 18468.0)),
            BT.MoveAndExitMap(Vec2f(-6062.0, -2688.0), target_map_name="Magus Stones"),
            #BT.MoveAndDialog(Vec2f(10228.0, 11488.0)),
            BT.VanquishNode([
                (8329.03, 9954.58),
                (7258.69, 10987.36),
                (4812.16, 11197.93),
                (2778.98, 13297.53),
                (499.76, 14253.58),
                (-4305.25, 13044.76),
                (-11493.07, 16584.55),
                (-17671.37, 14695.37),
            ]),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.AddModelToLootWhitelist(24628),
            BT.LootItems(distance=Range.Spirit.value),
            BT.HandleAutoQuest(
                pos=Vec2f(-17597.36, 15027.91),
                buttons=[],
                use_npc_model_or_enc_str=6725,
                require_quest_marker=True,
                log=True,
            ),
            BT.LootItems(distance=Range.Spirit.value),
            BT.Move(Vec2f(-15851.13, 14795.02)),
            BT.AutoDialog(0x832C07),
            BT.AutoDialog(0x84),
            BT.WaitForMapLoad(map_name="Magus Stones"),
            BT.Move(Vec2f(-18608.72, 16541.34)),
            #BT.MoveAndDialog(Vec2f(-18794.0, 16287.0)),
            BT.Move(Vec2f(-20599.0, 14444.0)),
            BT.WaitForMapLoad(map_id=658),
        ],
    )


def TheElusiveGolemancer() -> BehaviorTree:
    return BT.Sequence(
        name="The Elusive Golemancer",
        children=[
            BT.WaitForMapLoad(map_id=658),
            _aggressive(),
            #BT.MoveAndDialog(Vec2f(-14542.0, 12237.0)),
            BT.Move(Vec2f(-17204.16, 8545.91)),
            BT.MoveAndInteractWithGadget(Vec2f(-17601.0, 8150.0), log=True),
            BT.Wait(20_000),
            BT.VanquishNode([
                (-15960.14, 3309.37),
                (-13369.91, -965.44),
            ]),
            BT.MoveAndInteractWithGadget(Vec2f(-11737.0, -3710.0), log=True),
            BT.VanquishNode([
                (-15108.84, -2793.48),
                (-16518.94, -662.78),
            ]),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.VanquishNode([
                (-16898.24, -612.0),
                (-17391.0, -528.0),
                (-17597.36, 15027.91),
                (18755.0, -19827.0),
            ]),
            BT.WaitForMapLoad(map_id=659),
            _aggressive(),
            BT.MoveAndInteractWithGadget(Vec2f(15979.0, -17531.0), log=True),
            _pacifist(),
            BT.VanquishNode([
                (18031.51, -13929.63),
                (17886.86, -13218.39),
            ]),
            BT.MoveAndInteractWithGadget(Vec2f(15551.0, -13705.0), log=True),
            BT.Wait(3_000),
            BT.VanquishNode([
                (15551.0, -13705.0),
                (9928.16, -10998.24),
                (5953.36, -9815.89),
                (4531.82, -9827.91),
                (3035.53, -9450.54),
                (3485.59, -11380.60),
                (-229.0, -12033.0),
            ]),
            _aggressive(),
            BT.AutoDialog(0x84),
            #BT.MoveAndDialog(Vec2f(-2639.0, -15247.0)),
            #BT.MoveAndDialog(Vec2f(3833.0, -16855.0)),
            BT.VanquishNode([(3042.09, -16940.08), (2763.47, -17007.67)]),
            BT.Wait(10_000),
            BT.Move(Vec2f(3348.06, -16214.14)),
            BT.Wait(10_000),
            _pacifist(),
            BT.Move(Vec2f(5107.97, -17710.35)),
            BT.FlagAllHeroes(5413.07, -19400.44),
            BT.PickupGroundItemByModelID(
                22782,
                max_distance=5_000.0,
                timeout_ms=30_000,
                log=True,
            ),
            BT.MoveAndInteractWithGadget(Vec2f(5356.0, -19374.0), log=True),
            _pixel_stack(),
            BT.Wait(10_000),
            BT.DropBundle(log=True),
            BT.PickupGroundItemByModelID(
                22782,
                max_distance=5_000.0,
                timeout_ms=30_000,
                log=True,
            ),
            BT.Wait(1_000),
            BT.MoveAndInteractWithGadget(Vec2f(5356.0, -19374.0), log=True),
            _pixel_stack(),
            BT.Wait(10_000),
            BT.DropBundle(log=True),
            BT.PickupGroundItemByModelID(
                22782,
                max_distance=5_000.0,
                timeout_ms=30_000,
                log=True,
            ),
            BT.Wait(1_000),
            BT.MoveAndInteractWithGadget(Vec2f(5356.0, -19374.0), log=True),
            _pixel_stack(),
            BT.Wait(10_000),
            BT.DropBundle(log=True),
            BT.VanquishNode([(6882.36, -20769.41), (6566.0, -21425.0)]),
            BT.WaitForMapLoad(map_id=660),
            _aggressive(),
            BT.VanquishNode([
                (-12164.0, 10409.53),
                (-12584.28, 13570.28),
                (-15062.15, 16139.62),
                (-18265.0, 13647.0),
            ]),
            BT.WaitForMapLoad(map_id=640),
        ],
    )



# ---------------------------------------------------------------------------
# Planner and entry point
# ---------------------------------------------------------------------------


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Initialize Bot", InitializeBot),
        ("UnlockEyeOfTheNorthPool", UnlockEyeOfTheNorthPool),
        ("Obtain Story Book", ObtainStoryBook),
        ("Travel To Gunnar's Hold", TravelToGunnarsHold),
        ("Travel To Sifhalla", TravelToSifhalla),
        ("Tracking The Nornbear", CompleteTrackingTheNornbear),
        ("Curse Of The Nornbear", CompleteCurseOfTheNornbear),
        ("Blood Washes Blood", BloodWashesBlood),
        ("Travel To Olafstead", TravelToOlafstead),
        ("Shrine Of The Raven Spirit", CompleteShrineOfRavenSpirit),
        ("A Gate Too Far", CompleteAGateTooFar),
        ("Advance To Longeye's Edge", AdvanceToLongeyeEdge),
        ("Search For The Ebon Vanguard", SearchForTheEbonVanguard),
        ("Warband Of Brothers", WarbandOfBrothers),
        ("What Must Be Done", WhatMustBeDone),
        ("Assault On The Stronghold", AssaultOnTheStrongHold),
        ("Finding Gadd", FindingGadd),
        ("Finding The Bloodstone", FindingTheBloodstone)
        #("Lab Space", LabSpace),
        #("The Elusive Golemancer", TheElusiveGolemancer),
    ]


def ensure_botting_tree() -> BottingTree:
    global botting_tree

    if botting_tree is None:
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name="EotNStorylineSequence",
            repeat=False,
            multi_account=True,
            isolation_enabled=False,
            configure_fn=lambda tree: tree.Config.ConfigureUpkeep(
                looting_enabled=True,
                resurrection_scroll=True,
                auto_inventory_handler_enabled=True,
                consumable_upkeeps=tuple(
                    int(model_id)
                    for model_id in CONSUMABLE_UPKEEPS
                ),
                heroai_state_logging=False,
                enable_party_wipe_recovery=True,
            ),
        )

    return botting_tree



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
