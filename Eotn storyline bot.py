from __future__ import annotations

from collections.abc import Callable, Sequence

import Py4GW

from Py4GWCoreLib import (
    ConsoleLog,
    GLOBAL_CACHE,
    HeroType,
    Map,
    Player,
    UIManager,
)
import os
import PySystem
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Multiboxing_enums import SharedCommandType
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import (
    CONSUMABLE_UPKEEPS,
)
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Py4GWCoreLib import Agent, ConsoleLog, GLOBAL_CACHE, Player, Utils
from Py4GWCoreLib.Context import GWContext
from Py4GWCoreLib.enums_src.GameData_enums import Attribute, Profession
from Py4GWCoreLib.enums_src.Model_enums import ModelID






MODULE_NAME = "EotN Storyline BT"
ICON_PATH = os.path.join(
    PySystem.Console.get_projects_path(),
    "Textures", 
    "Module_Icons",
    "eotn.png"
)
MAP_TIMEOUT_MS = 190_000
KAINENG_CENTER_MAP_ID = 194

botting_tree: BottingTree | None = None
initialized = False


# ---------------------------------------------------------------------------
# Generic BT helpers
# ---------------------------------------------------------------------------

def _aggressive(name: str = "Configure Aggressive") -> BehaviorTree:
    return ensure_botting_tree().Config.Aggressive(
        multi_account=True,
        account_isolation=True,
        pause_on_danger=True,
        auto_loot=True,
        resurrection_scroll=True,
        reset_hero_ai=False,
    )


def _pacifist(name: str = "Configure Pacifist") -> BehaviorTree:
    return ensure_botting_tree().Config.Pacifist(
        multi_account=True,
        account_isolation=True,
        pause_on_danger=False,
        auto_loot=True,
        resurrection_scroll=True,
        reset_hero_ai=False,
    )


def _prepare_standard_party() -> BehaviorTree:
    heroes = [
        HeroType.Vekk.value,
        HeroType.Ogden.value,
        HeroType.Gwen.value,
        HeroType.MOX.value,
        HeroType.Olias.value,
    ]
    templates = [
        "OgljgwMpZO0iwB5Qp5N0h14dMA",
        "OwUTMwmCZaj4upB8ioLKDoHghAA",
        "OQhkAsC8gFKCNM95gpLDDRGcxA",
        "OgejkqrMLOfb2Luj7Ku72jbzLA",
        "OAhjUwGpYOyhqAVANUVxYezLGA",
    ]
    return BT.Sequence(
        name="Prepare Standard EotN Party",
        children=[
            BT.CreateParty(
                hero_ids=heroes,
                henchman_ids=[3, 6,1,4,2],
                multibox_invite=False,
                log=True,
            ),
            *[
                BT.LoadHeroSkillbar(index, template, log=True)
                for index, template in enumerate(templates, start=1)
            ],
        ],
    )

def _prepare_standard_party_olias() -> BehaviorTree:
    heroes = [
        HeroType.Vekk.value,
        HeroType.Ogden.value,
        HeroType.Gwen.value,
        HeroType.MOX.value,
    ]
    templates = [
        "OgljgwMpZO0iwB5Qp5N0h14dMA",
        "OwUTMwmCZaj4upB8ioLKDoHghAA",
        "OQhkAsC8gFKCNM95gpLDDRGcxA",
        "OgejkqrMLOfb2Luj7Ku72jbzLA",
    ]
    return BT.Sequence(
        name="Prepare Standard EotN Party",
        children=[
            BT.CreateParty(
                hero_ids=heroes,
                henchman_ids=[4,6,12],
                multibox_invite=False,
                log=True,
            ),
            *[
                BT.LoadHeroSkillbar(index, template, log=True)
                for index, template in enumerate(templates, start=1)
            ],
        ],
    )

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
        import PyUIManager

        reward_window = UIManager.GetFrameIDByHash(792099697)
        if not reward_window:
            ConsoleLog(
                MODULE_NAME,
                "Skill reward window was not found; continuing.",
                log=True,
            )
            return BehaviorTree.NodeState.SUCCESS

        skill_frame = UIManager.GetChildFrameByFrameId(
            reward_window,
            8 + int(slot),
        )
        if not skill_frame:
            ConsoleLog(
                MODULE_NAME,
                f"Skill reward slot {slot} was not found; continuing.",
                log=True,
            )
            return BehaviorTree.NodeState.SUCCESS

        PyUIManager.UIManager.button_mouse_action_by_frame_id(skill_frame, 5)
        return BehaviorTree.NodeState.SUCCESS

    def _equip() -> BehaviorTree.NodeState:
        frame_id = UIManager.GetFrameIDByHash(1725534410)
        if not frame_id:
            ConsoleLog(
                MODULE_NAME,
                "Reward skill equip button was not found; continuing.",
                log=True,
            )
            return BehaviorTree.NodeState.SUCCESS
        UIManager.FrameClick(frame_id)
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
            _prepare_standard_party(),
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




def Unlock_Xandra() -> BehaviorTree:
    return BT.Sequence(
        name="Talk to Gunnar",
        map_id_or_name="Gunnar's Hold",
        children=[
            BT.MoveAndDialog(Vec2f(24078.0, -7512.0), 0x832804),
        ],
    )

Tournament_Path = [
    Vec2f(18597.83, -10787.19),
    Vec2f(18715.88, -10922.83),
    Vec2f(18790.54, -11002.89),
]

NORN_TOURNAMENT_SKILLS = (
    "Bloodsong",
    "Shadowsong",
    "Pain",
    "Painful_Bond",
    "Destruction",
    "Disenchantment",
)
from Py4GWCoreLib.Skill import Skill
Painful_Bond_ID = Skill.GetID("Painful_Bond")

NORN_TOURNAMENT_SPIRIT_CASTS = (
    ("Bloodsong", 3_500),
    ("Shadowsong", 3_500),
    ("Pain", 3_500),
    ("Destruction", 3_500),
    ("Disenchantment", 5_500),
)






def _cast_norn_tournament_skill(
    skill_name: str,
    *,
    aftercast_delay_ms: int,
    log: bool,
) -> BehaviorTree:
    """Retry a tournament skill until its energy and recharge checks pass."""

    skill_id = int(GLOBAL_CACHE.Skill.GetID(skill_name) or 0)
    if skill_id <= 0:
        return BT.Failer(name=f"Resolve Tournament Skill Failed - {skill_name}")

    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            name=f"Cast Tournament Skill When Ready - {skill_name}",
            child=BT.Node(
                BT.CastSkillID(
                    skill_id=skill_id,
                    aftercast_delay_ms=aftercast_delay_ms,
                    log=log,
                )
            ),
            timeout_ms=90_000,
        )
    )


def _run_norn_tournament_round(log: bool = False) -> BehaviorTree:
    """Run one tournament round with explicit Ritualist skill control."""

    return BT.Sequence(
        name="Manual Norn Tournament Round",
        children=[
            BT.Move(
                Tournament_Path[0],
                pause_on_combat=True,
                log=log,
                tolerance=50
            ),
            *[
                _cast_norn_tournament_skill(
                    skill_name,
                    aftercast_delay_ms=aftercast_delay_ms,
                    log=log,
                )
                for skill_name, aftercast_delay_ms
                in NORN_TOURNAMENT_SPIRIT_CASTS
            ],
            BT.Move(Vec2f(18816.43, -11083.93)),
            BT.Wait(2000),
            BT.Move(
                Tournament_Path[0],
                pause_on_combat=True,
                log=log,
                tolerance=50
            ),
            BT.Wait(2000),
            BT.CastSkillID(skill_id = Painful_Bond_ID),
            _aggressive(),
            BT.VanquishNode(
                Tournament_Path,
                pause_on_combat=True,
                log=True,
            ),
            _pacifist()
        ],
    )


def _wait_for_xandra(
    timeout_ms: int = 20_000,
) -> BehaviorTree:
    """Wait until Xandra exists in the complete agent array."""

    def _is_xandra_present() -> BehaviorTree.NodeState:
        xandra_agent_id = int(Agent.GetAgentIDByName("Xandra") or 0)
        return (
            BehaviorTree.NodeState.SUCCESS
            if xandra_agent_id > 0
            else BehaviorTree.NodeState.FAILURE
        )

    probe = BT.Selector(
        name="Probe Xandra Presence",
        children=[
            BehaviorTree(
                BehaviorTree.ConditionNode(
                    name="Find Xandra In Agent Array",
                    condition_fn=_is_xandra_present,
                )
            ),
            BT.Sequence(
                name="Delay Before Next Xandra Probe",
                children=[
                    BT.Wait(250),
                    BT.Failer(name="Xandra Probe Failed"),
                ],
            ),
        ],
    )

    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            name="Wait For Xandra To Spawn",
            child=BT.Node(probe),
            timeout_ms=max(0, int(timeout_ms)),
        )
    )


def _ritualist_secondary_unlocked(log: bool = True) -> BehaviorTree:
    def _check() -> BehaviorTree.NodeState:
        player_id = int(Player.GetAgentID() or 0)
        primary_id, secondary_id = Agent.GetProfessionIDs(player_id)

        if int(primary_id) == int(Profession.Ritualist.value):
            return BehaviorTree.NodeState.SUCCESS

        world_context = GWContext.World.GetContext()
        profession_states = (
            list(world_context.party_profession_states or [])
            if world_context is not None
            else []
        )

        for profession_state in profession_states:
            if int(profession_state.agent_id or 0) != player_id:
                continue

            unlocked = bool(
                int(secondary_id) == int(Profession.Ritualist.value)
                or profession_state.IsProfessionUnlocked(
                    int(Profession.Ritualist.value)
                )
            )
            if log:
                ConsoleLog(
                    MODULE_NAME,
                    (
                        "Ritualist secondary is unlocked."
                        if unlocked
                        else "Ritualist secondary must be unlocked at GToB."
                    ),
                    log=True,
                )
            return (
                BehaviorTree.NodeState.SUCCESS
                if unlocked
                else BehaviorTree.NodeState.FAILURE
            )

        ConsoleLog(
            MODULE_NAME,
            "Unable to resolve the local profession unlock state.",
            log=True,
        )
        return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name="Check Ritualist Secondary Unlock",
            condition_fn=_check,
        )
    )


def _activate_ritualist_secondary(log: bool = True) -> BehaviorTree:
    """Activate Ritualist without visiting GToB when it is already unlocked."""

    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        player_id = int(Player.GetAgentID() or 0)
        primary_id, secondary_id = Agent.GetProfessionIDs(player_id)
        primary_id = int(primary_id or 0)
        secondary_id = int(secondary_id or 0)
        ritualist_id = int(Profession.Ritualist.value)

        if primary_id == ritualist_id or secondary_id == ritualist_id:
            return BT.Succeeder(name="Ritualist Profession Already Active")

        template = Utils.GenerateSkillbarTemplateFrom(
            prof_primary=primary_id,
            prof_secondary=ritualist_id,
            attributes={},
            skills=[0, 0, 0, 0, 0, 0, 0, 0],
        )
        if not template:
            return BT.Failer(name="Generate Ritualist Activation Template Failed")

        def _verify_active() -> BehaviorTree.NodeState:
            _, loaded_secondary_id = Agent.GetProfessionIDs(player_id)
            return (
                BehaviorTree.NodeState.SUCCESS
                if int(loaded_secondary_id) == ritualist_id
                else BehaviorTree.NodeState.FAILURE
            )

        return BT.Sequence(
            name="Activate Ritualist Secondary",
            children=[
                BT.LoadSkillbar(template=template, log=log),
                BT.Wait(1_000),
                BehaviorTree(
                    BehaviorTree.ConditionNode(
                        name="Verify Ritualist Secondary Is Active",
                        condition_fn=_verify_active,
                    )
                ),
            ],
        )

    return BT.Subtree(
        name="Activate Ritualist Secondary Subtree",
        subtree_fn=_build,
    )


def EnsureRitualistSecondaryUnlocked(
    *,
    skill_budget_gold: int = 5_000,
    log: bool = True,
) -> BehaviorTree:
    unlock_if_needed = BT.Selector(
        name="Unlock Ritualist Secondary If Needed",
        children=[
            _ritualist_secondary_unlocked(log=log),
            BT.Sequence(
                name="Unlock Ritualist Secondary At GToB",
                children=[
                    BT.Travel(target_map_id=248, log=log),
                    BT.EqualizeGold(
                        target_gold=max(0, int(skill_budget_gold)) + 500,
                        deposit_all=False,
                        log=log,
                    ),
                    BT.MoveAndDialog(Vec2f(-3071.00, -7258.00),0x884),
                    BT.Wait(2_000),
                    _ritualist_secondary_unlocked(log=log),
                    BT.LogMessage(
                        message="Ritualist secondary was unlocked at GToB.",
                        module_name=MODULE_NAME,
                    ),
                ],
            ),
        ],
    )

    return BT.Sequence(
        name="Ensure Ritualist Secondary Is Unlocked And Active",
        children=[
            unlock_if_needed,
            _activate_ritualist_secondary(log=log),
        ],
    )


def _ensure_skill_learned(skill_name: str, log: bool) -> BehaviorTree:
    skill_id = int(GLOBAL_CACHE.Skill.GetID(skill_name) or 0)

    if skill_id <= 0:
        return BT.Failer(name=f"Resolve Skill ID Failed - {skill_name}")

    def _already_learned() -> BehaviorTree.NodeState:
        return (
            BehaviorTree.NodeState.SUCCESS
            if GLOBAL_CACHE.SkillBar.IsSkillLearnt(skill_id)
            else BehaviorTree.NodeState.FAILURE
        )

    return BT.Selector(
        name=f"Ensure Skill Learned - {skill_name}",
        children=[
            BehaviorTree(
                BehaviorTree.ConditionNode(
                    name=f"Check Skill Learned - {skill_name}",
                    condition_fn=_already_learned,
                )
            ),
            RoutinesBT.Player.BuySkill(
                skill_id=skill_id,
                log=log,
            ),
        ],
    )






def _equip_norn_tournament_build(log: bool = True) -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        player_id = int(Player.GetAgentID() or 0)
        primary_id, current_secondary_id = Agent.GetProfessionIDs(player_id)
        primary_id = int(primary_id or 0)
        skill_names = list(NORN_TOURNAMENT_SKILLS)
        skill_ids = [
            int(GLOBAL_CACHE.Skill.GetID(skill_name) or 0)
            for skill_name in skill_names
        ]

        if (
            primary_id <= 0
            or len(skill_ids) > 8
            or any(skill_id <= 0 for skill_id in skill_ids)
        ):
            return BT.Failer(name="Resolve Norn Tournament Build Failed")

        secondary_id = (
            int(current_secondary_id or 0)
            if primary_id == int(Profession.Ritualist.value)
            else int(Profession.Ritualist.value)
        )
        template = Utils.GenerateSkillbarTemplateFrom(
            prof_primary=primary_id,
            prof_secondary=secondary_id,
            attributes={
                int(Attribute.Communing.value): 12,
                int(Attribute.ChannelingMagic.value): 12,
            },
            skills=[*skill_ids, *([0] * (8 - len(skill_ids)))],
        )

        if not template:
            return BT.Failer(name="Generate Norn Tournament Build Failed")

        def _verify() -> BehaviorTree.NodeState:
            _, loaded_secondary_id = Agent.GetProfessionIDs(player_id)
            attributes = Agent.GetAttributesDict(player_id)
            loaded_skills = [
                int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) or 0)
                for slot in range(1, len(skill_ids) + 1)
            ]
            communing_value = int(
                attributes.get(int(Attribute.Communing.value), 0) or 0
            )
            channeling_value = int(
                attributes.get(int(Attribute.ChannelingMagic.value), 0) or 0
            )

            # Attribute values requested by the template are automatically
            # reduced by Guild Wars when the character does not yet have
            # enough attribute points (for example, before level 20).
            # The build is therefore considered correctly loaded when the
            # Ritualist secondary and the expected skills are present.
            valid = bool(
                int(loaded_secondary_id) == secondary_id
                and loaded_skills == skill_ids
            )

            if not valid:
                ConsoleLog(
                    MODULE_NAME,
                    (
                        "Norn Tournament build verification failed: "
                        f"secondary={loaded_secondary_id}/{secondary_id}, "
                        f"Communing={communing_value}, "
                        f"Channeling={channeling_value}, "
                        f"skills={loaded_skills}/{skill_ids}."
                    ),
                    log=True,
                )
            elif log:
                ConsoleLog(
                    MODULE_NAME,
                    (
                        "Norn Tournament build loaded successfully: "
                        f"secondary={loaded_secondary_id}, "
                        f"Communing={communing_value}, "
                        f"Channeling={channeling_value}, "
                        f"skills={loaded_skills}."
                    ),
                    log=True,
                )
            return (
                BehaviorTree.NodeState.SUCCESS
                if valid
                else BehaviorTree.NodeState.FAILURE
            )

        return BT.Sequence(
            name="Equip Norn Tournament Build",
            children=[
                BT.LoadSkillbar(template=template, log=log),
                BT.Wait(1_000),
                BehaviorTree(
                    BehaviorTree.ConditionNode(
                        name="Verify Norn Tournament Build",
                        condition_fn=_verify,
                    )
                ),
            ],
        )

    return BT.Subtree(
        name="Generate And Equip Norn Tournament Build",
        subtree_fn=_build,
    )


def UnlockNornTournamentSkills(
    *,
    skill_budget_gold: int = 5_000,
    log: bool = True,
) -> BehaviorTree:
    return BT.Sequence(
        name="Prepare Norn Tournament Build",
        children=[
            EnsureRitualistSecondaryUnlocked(
                skill_budget_gold=skill_budget_gold,
                log=log,
            ),
            BT.Travel(target_map_name="Kaineng Center", log=log),
            BT.EqualizeGold(
                target_gold=max(0, int(skill_budget_gold)),
                deposit_all=False,
                log=log,
            ),
            BT.Move(
                Vec2f(420.00, 1388.00),
                ignore_destination_obstacles=True,
                log=log,
            ),
            BT.TargetAgentByName(agent_name="Michiko", log=log),
            BT.InteractTarget(log=log),
            BT.Wait(1_000),
            *[
                _ensure_skill_learned(skill_name, log)
                for skill_name in NORN_TOURNAMENT_SKILLS
            ],
            BT.Wait(1_000),
            _equip_norn_tournament_build(log=log),
        ],
    )


def Fight_Sequence(
    return_outpost_name: str = "Gunnar's Hold",
    log: bool = True,
) -> BehaviorTree:
    tournament_attempt = BT.Sequence(
        name="Norn Tournament Attempt",
        children=[
            BT.Travel(target_map_name=return_outpost_name, log=log),
            _pacifist(),
            BT.MoveAndDialog(Vec2f(17944.00, -11846.00), 0x84),
            BT.Wait(12_000),
            _run_norn_tournament_round(log=log),
            BT.Selector(
                name="Check Second Round For Xandra",
                children=[
                    BT.Sequence(
                        name="Xandra Found",
                        children=[
                            _wait_for_xandra(timeout_ms=20_000),
                            BT.LogMessage(
                                message=(
                                    "Xandra was detected for the second round; "
                                    "finishing the tournament attempt."
                                ),
                                module_name=MODULE_NAME,
                            ),
                            BT.Wait(7000),
                            _run_norn_tournament_round(log=log),
                            BT.Travel(
                                target_map_name=return_outpost_name,
                                log=log,
                            ),
                            BT.LogMessage(
                                message=(
                                    "Xandra fight completed; the Norn Tournament "
                                    "retry loop is stopping."
                                ),
                                module_name=MODULE_NAME,
                            ),
                        ],
                    ),
                    BT.Sequence(
                        name="Xandra Absent",
                        children=[
                            BT.LogMessage(
                                message=(
                                    "Xandra was not detected; returning to "
                                    "Gunnar's Hold before retrying."
                                ),
                                module_name=MODULE_NAME,
                            ),
                            BT.Travel(
                                target_map_name=return_outpost_name,
                                log=log,
                            ),
                            BT.Failer(name="Retry Tournament Without Xandra"),
                        ],
                    ),
                ],
            ),
        ],
    )

    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            name="Repeat Norn Tournament Until Xandra",
            child=BT.Node(tournament_attempt),
            timeout_ms=0,
        )
    )



def _is_kaineng_center_unlocked(log: bool = True) -> BehaviorTree:
    """Succeed only when Kaineng Center is unlocked for this character."""

    def _check() -> BehaviorTree.NodeState:
        unlocked = bool(Map.IsMapUnlocked(KAINENG_CENTER_MAP_ID))

        if log:
            ConsoleLog(
                MODULE_NAME,
                (
                    "Kaineng Center is unlocked; preparing the Xandra tournament."
                    if unlocked
                    else "Kaineng Center is not unlocked; skipping the Xandra tournament setup."
                ),
                log=True,
            )

        return (
            BehaviorTree.NodeState.SUCCESS
            if unlocked
            else BehaviorTree.NodeState.FAILURE
        )

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name="Check Kaineng Center Unlock",
            condition_fn=_check,
        )
    )


def PrepareXandraTournament(
    return_outpost_name: str = "Gunnar's Hold",
    log: bool = True,
) -> BehaviorTree:
    """Prepare the build and unlock tournament access once before retries."""

    return BT.Sequence(
        name="Prepare Xandra Tournament",
        children=[
            UnlockNornTournamentSkills(log=log),
            BT.Travel(target_map_name=return_outpost_name, log=log),
            BT.MoveAndDialog(Vec2f(17763.00, -11467.00), 0x834A01),
        ],
    )




def CompleteOptionalXandraTournament(
    return_outpost_name: str = "Gunnar's Hold",
    log: bool = True,
) -> BehaviorTree:
    """Run every Xandra-tournament preparation step only with Kaineng unlocked."""

    return BT.Selector(
        name="Optional Xandra Tournament",
        children=[
            BT.Sequence(
                name="Run Xandra Tournament With Kaineng",
                children=[
                    _is_kaineng_center_unlocked(log=log),
                    
                ],
            ),
            BT.Sequence(
                name="Skip Xandra Tournament Without Kaineng",
                children=[
                    BT.LogMessage(
                        message=(
                            "Kaineng Center is unavailable for this character. "
                            "Ritualist profession setup, skill purchases and the "
                            "Norn Tournament are skipped."
                        ),
                        module_name=MODULE_NAME,
                    ),
                    BT.Travel(
                        target_map_name=return_outpost_name,
                        log=log,
                    ),
                    BT.Succeeder(name="Continue Norn Story Without Xandra"),
                ],
            ),
        ],
    )


def TravelToSifhalla() -> BehaviorTree:
    return BT.Sequence(
        name="Run to Sifhalla",
        map_id_or_name=644,
        children=[
            _aggressive(),
            BT.VanquishNode([
                (16003.853515, -6544.087402),
                (15193.037109, -6387.140625),
            ]),
            BT.WaitForMapLoad(map_name="Norrhart Domains"),
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
            _aggressive(),
            BT.MoveAndDialog(Vec2f(14353.0, 23905.0), 0x84),
            BT.WaitForMapLoad(map_id=678),
            BT.Wait(2_000),
            BT.Move(Vec2f(10388.0, 23888.0)),
            BT.Wait(8_500),
            BT.WaitUntilOnCombat(timeout_ms=60_000),
            BT.Wait(40_000),
            BT.WaitForMapLoad(map_name="Sifhalla"),
            BT.MoveAndDialog(Vec2f(14353.0, 23905.0), 0x832807),
        ],
    )


def CompleteCurseOfTheNornbear() -> BehaviorTree:
    return BT.Sequence(
        name="Curse of the Nornbear",
        map_id_or_name="Sifhalla",
        children=[
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
            BT.WaitUntilOnCombat(timeout_ms=60_000),
            BT.Wait(5_000),
            BT.WaitForMapLoad(map_id=643),
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
            _pacifist(),
            BT.MoveAndDialog(Vec2f(-15696.0, 8732.0), 0x85),
            _aggressive(),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Wait(50_000),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Wait(15_000),
            BT.Travel(target_map_name="Olafstead"),
            BT.MoveAndDialog(Vec2f(132.0, -684.0), 0x832E07),
            BT.MoveAndDialog(Vec2f(132.0, -684.0), 0x86),
        ],
    )


def CompleteAGateTooFar() -> BehaviorTree:
    return BT.Sequence(
        name="A Gate Too Far",
        children=[
            BT.Wait(2_000),
            _aggressive(),
            BT.VanquishNode([
                (-6814.0, -2984.0),
                (-3947.0, -226.0),
                (-6545.0, 6730.0),
            ]),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(-7653.0, 5072.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(-6282.0, 6545.0)),
            BT.Wait(120_000),
            BT.Move(Vec2f(-8244.0, 576.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(-10132.0, 807.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(-13368.0, 1995.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(-14761.0, 3282.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(-15036.0, 5711.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
            BT.Move(Vec2f(-15976.0, 7767.0)),
            BT.WaitUntilOutOfCombat(timeout_ms=120_000),
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
            BT.MoveAndDialog(Vec2f(-2639.0, -15247.0)),
            BT.MoveAndDialog(Vec2f(3833.0, -16855.0)),
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
# Optional Olias unlock
# ---------------------------------------------------------------------------

OLIAS_HERO_ID = int(HeroType.Olias.value)


MOX_HERO_ID = int(HeroType.MOX.value)


def _mox_is_unlocked(log: bool = True) -> BehaviorTree:
    """Check MOX ownership by temporarily asking the outpost party API to add him."""

    def _request_add() -> BehaviorTree.NodeState:
        GLOBAL_CACHE.Party.Heroes.AddHero(MOX_HERO_ID)
        return BehaviorTree.NodeState.SUCCESS

    def _check_added() -> BehaviorTree.NodeState:
        heroes = GLOBAL_CACHE.Party.GetHeroes() or []
        player_login = int(Player.GetLoginNumber() or 0)
        unlocked = any(
            int(getattr(hero, "hero_id", 0) or 0) == MOX_HERO_ID
            and int(getattr(hero, "owner_player_id", 0) or 0) == player_login
            for hero in heroes
        )

        if log:
            ConsoleLog(
                MODULE_NAME,
                "MOX is already unlocked." if unlocked else "MOX is not unlocked.",
                log=True,
            )

        return (
            BehaviorTree.NodeState.SUCCESS
            if unlocked
            else BehaviorTree.NodeState.FAILURE
        )

    def _remove_test_hero() -> BehaviorTree.NodeState:
        GLOBAL_CACHE.Party.Heroes.KickHero(MOX_HERO_ID)
        return BehaviorTree.NodeState.SUCCESS

    return BT.Sequence(
        name="Check MOX Unlock",
        children=[
            BT.LeaveParty(),
            BehaviorTree(
                BehaviorTree.ActionNode(
                    name="Attempt To Add MOX",
                    action_fn=_request_add,
                    aftercast_ms=750,
                )
            ),
            BT.Wait(1_000),
            BehaviorTree(
                BehaviorTree.ConditionNode(
                    name="Verify MOX Joined Party",
                    condition_fn=_check_added,
                )
            ),
            BehaviorTree(
                BehaviorTree.ActionNode(
                    name="Remove MOX After Unlock Check",
                    action_fn=_remove_test_hero,
                    aftercast_ms=500,
                )
            ),
        ],
    )


def UnlockMOX(log: bool = True) -> BehaviorTree:
    return BT.Sequence(
        name="Unlock MOX",
        children=[
            BT.Travel(target_map_id=KAINENG_CENTER_MAP_ID, log=log),
            BT.MoveAndExitMap(
                Vec2f(3243.0, -4911.0),
                target_map_name="Bukdek Byway",
                log=log,
            ),
            BT.MoveAndDialog(
                Vec2f(-5803.48, 18951.70),
                0x85,
                log=log,
            ),
            BT.Wait(1_000),
        ],
    )


def EnsureMOXUnlocked(log: bool = True) -> BehaviorTree:
    """Skip the Bukdek Byway unlock route when MOX is already owned."""
    return BT.Selector(
        name="Ensure MOX Is Unlocked",
        children=[
            BT.Sequence(
                name="MOX Already Unlocked",
                children=[
                    _mox_is_unlocked(log=log),
                    BT.LogMessage(
                        message="MOX is already unlocked; skipping his unlock route.",
                        module_name=MODULE_NAME,
                    ),
                ],
            ),
            BT.Sequence(
                name="Unlock MOX If Missing",
                children=[
                    BT.LogMessage(
                        message="MOX is missing; starting his unlock route.",
                        module_name=MODULE_NAME,
                    ),
                    UnlockMOX(log=log),
                    BT.LogMessage(
                        message="MOX unlock route completed.",
                        module_name=MODULE_NAME,
                    ),
                ],
            ),
        ],
    )


def _olias_is_unlocked(log: bool = True) -> BehaviorTree:
    """Check ownership by temporarily asking the outpost party API to add Olias."""

    def _request_add() -> BehaviorTree.NodeState:
        GLOBAL_CACHE.Party.Heroes.AddHero(OLIAS_HERO_ID)
        return BehaviorTree.NodeState.SUCCESS

    def _check_added() -> BehaviorTree.NodeState:
        heroes = GLOBAL_CACHE.Party.GetHeroes() or []
        player_login = int(Player.GetLoginNumber() or 0)
        unlocked = any(
            int(getattr(hero, "hero_id", 0) or 0) == OLIAS_HERO_ID
            and int(getattr(hero, "owner_player_id", 0) or 0) == player_login
            for hero in heroes
        )

        if log:
            ConsoleLog(
                MODULE_NAME,
                "Olias is already unlocked." if unlocked else "Olias is not unlocked.",
                log=True,
            )

        return (
            BehaviorTree.NodeState.SUCCESS
            if unlocked
            else BehaviorTree.NodeState.FAILURE
        )

    def _remove_test_hero() -> BehaviorTree.NodeState:
        GLOBAL_CACHE.Party.Heroes.KickHero(OLIAS_HERO_ID)
        return BehaviorTree.NodeState.SUCCESS

    return BT.Sequence(
        name="Check Olias Unlock",
        children=[
            BT.LeaveParty(),
            BehaviorTree(
                BehaviorTree.ActionNode(
                    name="Attempt To Add Olias",
                    action_fn=_request_add,
                    aftercast_ms=750,
                )
            ),
            BT.Wait(1_000),
            BehaviorTree(
                BehaviorTree.ConditionNode(
                    name="Verify Olias Joined Party",
                    condition_fn=_check_added,
                )
            ),
            BehaviorTree(
                BehaviorTree.ActionNode(
                    name="Remove Olias After Unlock Check",
                    action_fn=_remove_test_hero,
                    aftercast_ms=500,
                )
            ),
        ],
    )


def ToKamadanForOlias(log: bool = True) -> BehaviorTree:
    return BT.Sequence(
        name="Sunspears In Cantha - Reach Kamadan",
        children=[
            BT.Travel(target_map_id=KAINENG_CENTER_MAP_ID, log=log),
            _prepare_standard_party_olias(),
            BT.VanquishNode([
                (3049.35, -2020.75),
                (2739.30, -3710.67),
                (-648.30, -3493.72),
                (-1661.91, -636.09),
            ], log=log),
            BT.MoveAndDialog(Vec2f(-1131.99, 818.35), 0x82D401, log=log),
            BT.MoveAndExitMap(Vec2f(-2439.0, 1732.0), target_map_id=290, log=log),
            BT.VanquishNode([
                (-2995.68, 2077.20),
                (-6938.10, 4286.61),
                (-6064.40, 5300.26),
                (-2396.20, 5260.67),
                (-5031.77, 6001.52),
                (-5899.57, 7240.19),
            ], log=log),
            BT.TargetAgentByModelIDAndSendDialog(4914, 0x82D404, log=log),
            BT.Wait(500),
            BT.SendDialog(0x87, log=log),
            BT.WaitForMapLoad(map_id=400),
            _aggressive(),
            BT.VanquishNode([
                (-1712.16, -700.23),
                (-907.97, -2862.29),
                (742.42, -4167.73),
                (1352.94, -3694.75)]),
            BT.Wait(5000),
            BT.VanquishNode([    
                (1786, -1448)]),
            BT.Wait(5000),
            BT.VanquishNode([
                (2651.48, -3750.63),
                (3355.63, -2151.82),
                (4347, -1682),]),
            BT.Wait(5000),
            BT.VanquishNode([    
                (279, 811)
            ], pause_on_combat=True, log=log),
            BT.WaitForMapLoad(map_id=290, timeout_ms=60000),
            BT.TargetAgentByModelIDAndSendDialog(4914, 0x84, log=log),
            BT.SendDialog(0x85),
            BT.WaitForMapLoad(map_id=543),
            BT.Wait(2_000),
            BT.TargetAgentByModelIDAndSendDialog(4829, 0x82D407, log=log),
        ],
    )


def ToConsulateDocksForOlias(log: bool = True) -> BehaviorTree:
    return BT.Sequence(
        name="Unlock Consulate Docks",
        children=[
            BT.Travel(target_map_id=KAINENG_CENTER_MAP_ID, log=log),
            BT.LeaveParty(),
            BT.Travel(target_map_id=449, log=log),
            BT.Move(Vec2f(-8075.89, 14592.47), log=log),
            BT.Move(Vec2f(-6743.29, 16663.21), log=log),
            BT.Move(Vec2f(-5271.00, 16740.00), log=log),
            BT.WaitForMapLoad(map_id=429),
            BT.MoveAndDialog(Vec2f(-4631.86, 16711.79), 0x85, log=log),
            BT.WaitForMapLoad(map_id=493),
        ],
    )

def ToLionsArch() -> BehaviorTree:
    return BT.Sequence(
        "To Lion's Arch",
        children=[
            BT.Travel(KAINENG_CENTER_MAP_ID),

            BT.VanquishNode([
                    (3049.35, -2020.75),
                    (2739.30, -3710.67),
                    (-648.30, -3493.72),
                    (-1661.91, -636.09),
                ]),

            BT.MoveAndDialog(Vec2f(-1006.97,-817.63),0x81DF01),
            BT.MoveAndExitMap((-2439,1732),target_map_id=290),
            BT.VanquishNode(
                [
                    (-2995.68, 2077.20),
                    (-6938.10, 4286.61),
                    (-6064.40, 5300.26),
                    (-2396.20, 5260.67),
                    (-5031.77, 6001.52),
                ],
            ),
            BT.MoveAndDialog(Vec2f(-5626.17, 7017.33),0x81DF04),
            BT.MoveAndDialog(Vec2f(-4661.13, 7479.86),0x84),
            BT.WaitForMapLoad(map_name="Lion's Gate"),
            BT.MoveAndDialog(Vec2f(-1181, 1038),0x85),
            BT.Travel(55),
            BT.MoveAndDialog(Vec2f(328.00,9594.00),0x81DF07),

        ],
    )

def CompleteOliasUnlock(log: bool = True) -> BehaviorTree:
    return BT.Sequence(
        name="All For One And One For Justice",
        children=[
            ToLionsArch(),
            BT.LeaveParty(),
            _prepare_standard_party(),
            BT.MoveAndDialog(Vec2f(-1137.00, 2501.00), 0x84, log=log),
            BT.WaitForMapLoad(map_id=471),
            BT.Wait(3_000),
            BT.MoveAndDialog(Vec2f(5117.00, 10515.00), 0x830E04, log=log),
            _aggressive(),
            BT.VanquishNode([
                (8518.10, 9309.66),
                (8067.40, 5703.23),
                (5657.20, 4485.55),
                (4461.65, -710.88),
                (10750.0, 2100.0),
            ], pause_on_combat=True, log=log),
            BT.WaitForMapLoad(map_id=55, timeout_ms=120000),
            BT.LeaveParty(),
            BT.Travel(target_map_id=449, log=log),
            BT.Move(Vec2f(-8149.02, 14900.65), log=log),
            BT.MoveAndDialog(Vec2f(-6480.00, 16331.00), 0x830E07, log=log),
        ],
    )


def EnsureOliasUnlocked(log: bool = True) -> BehaviorTree:
    """Skip the complete Cantha/Nightfall route when Olias is already owned."""
    return BT.Selector(
        name="Ensure Olias Is Unlocked",
        children=[
            BT.Sequence(
                name="Olias Already Unlocked",
                children=[
                    _olias_is_unlocked(log=log),
                    BT.LogMessage(
                        message="Olias is already unlocked; skipping his unlock route.",
                        module_name=MODULE_NAME,
                    ),
                ],
            ),
            BT.Sequence(
                name="Unlock Olias If Missing",
                children=[
                    BT.LogMessage(
                        message="Olias is missing; starting the complete unlock route.",
                        module_name=MODULE_NAME,
                    ),
                    ToKamadanForOlias(log=log),
                    ToConsulateDocksForOlias(log=log),
                    CompleteOliasUnlock(log=log),
                    BT.LogMessage(
                        message="Olias unlock route completed.",
                        module_name=MODULE_NAME,
                    ),
                ],
            ),
        ],
    )

# ---------------------------------------------------------------------------
# Planner and entry point
# ---------------------------------------------------------------------------


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Initialize Bot", InitializeBot),
        ("UnlockEyeOfTheNorthPool",UnlockEyeOfTheNorthPool),
        ("Obtain Story Book", ObtainStoryBook),
        ("Ensure MOX Unlocked", EnsureMOXUnlocked),
        ("Ensure Olias Unlocked", EnsureOliasUnlocked),
        ("Travel To Gunnar's Hold", TravelToGunnarsHold),
        ("Talk To Gunnar", Unlock_Xandra),
        ("Optional Xandra Tournament", CompleteOptionalXandraTournament),
        ("PrepareXandraTournament",PrepareXandraTournament),
        ("Fight Sequence",Fight_Sequence),
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
            isolation_enabled=True,
            configure_fn=lambda tree: tree.Config.ConfigureUpkeep(
                looting_enabled=True,
                resurrection_scroll=True,
                auto_inventory_handler_enabled=True,
                activate_widget_list=(
                    "LootManager",
                ),
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


if __name__ == "__main__":
    main()