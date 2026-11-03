from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence

import PySkillbar
import PySystem
from Py4GWCoreLib import (
    Agent,
    ConsoleLog,
    GLOBAL_CACHE,
    HeroType,
    Map,
    Player,
    Utils,
)
from Py4GWCoreLib.AgentArray import AgentArray
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.Context import GWContext
from Py4GWCoreLib.enums_src.GameData_enums import Attribute, Profession, Range
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Py4GWCoreLib.enums_src.Multiboxing_enums import SharedCommandType
from Py4GWCoreLib.FrameTree import Frame
from Py4GWCoreLib.native_src.internals.types import Vec2f
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as RoutinesBT
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import (
    CONSUMABLE_UPKEEPS,
)
from Sources.Sky.Support import attach_botting_tree_support
from Sources.ApoSource.ApoBottingLib import wrappers as BT



MODULE_ICON = 'Assets\\Textures\\Module_Icons\\eotn.png'
MODULE_NAME = "EotN Storyline BT"
ICON_PATH = os.path.join(
    PySystem.Console.get_projects_path(),
    "Assets",
    "Textures", 
    "Module_Icons",
    "eotn.png"
)
MAP_TIMEOUT_MS = 190_000
KAINENG_CENTER_MAP_ID = 194
OLAF_OLAFSON_MODEL_ID = 6403

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
        resurrection_scroll=True,
        reset_hero_ai=False,
    )


def _pacifist(name: str = "Configure Pacifist") -> BehaviorTree:
    return ensure_botting_tree().Config.Pacifist(
        multi_account=True,
        account_isolation=True,
        pause_on_danger=False,
        resurrection_scroll=True,
        reset_hero_ai=False,
    )


def _prepare_standard_party_olias() -> BehaviorTree:
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
        "OAhjUwGZYOyhqAVANUVncSzLGA",
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

def _prepare_standard_party_xandra() -> BehaviorTree:
    heroes = [
            HeroType.Vekk.value,
            HeroType.Ogden.value,
            HeroType.Gwen.value,
            HeroType.MOX.value,
            HeroType.Olias.value,
            HeroType.Xandra.value
        ]
    templates = [
            "OgljgwMpZO0iwB5Qp5N0h14dMA",
            "OwUTMwmCZaj4upB8ioLKDoHghAA",
            "OQhkAsC8gFKCNM95gpLDDRGcxA",
            "OgejkqrMLOfb2Luj7Ku72jbzLA",
            "OAhjUwGZYOyhqAVANUVncSzLGA",
            "OAOjAyhDJPYTnp17xFOhmtkLGA"
        ]
    return BT.Sequence(
            name="Prepare Standard EotN Party",
            children=[
                BT.CreateParty(
                    hero_ids=heroes,
                    henchman_ids=[3],
                    multibox_invite=False,
                    log=True,
                ),
                *[
                    BT.LoadHeroSkillbar(index, template, log=True)
                    for index, template in enumerate(templates, start=1)
                ],
            ],
        )

def _prepare_standard_party_full() -> BehaviorTree:
    heroes = [
            HeroType.Vekk.value,
            HeroType.Ogden.value,
            HeroType.Gwen.value,
            HeroType.MOX.value,
            HeroType.Olias.value,
            HeroType.Xandra.value,
            HeroType.Livia.value
        ]
    templates = [
            "OgljgwMpZO0iwB5Qp5N0h14dMA",
            "OwUTMwmCZaj4upB8ioLKDoHghAA",
            "OQhkAsC8gFKCNM95gpLDDRGcxA",
            "OgejkqrMLOfb2Luj7Ku72jbzLA",
            "OAhjUwGZYOyhqAVANUVncSzLGA",
            "OAOjAyhDJPYTnp17xFOhmtkLGA",
            "OAhjYkHcYOP1qqdwScxGmSzJHA"

        ]
    return BT.Sequence(
            name="Prepare Standard EotN Party",
            children=[
                BT.CreateParty(
                    hero_ids=heroes,
                    multibox_invite=False,
                    log=True,
                ),
                *[
                    BT.LoadHeroSkillbar(index, template, log=True)
                    for index, template in enumerate(templates, start=1)
                ],
            ],
        )

def _prepare_touch_team() -> BehaviorTree:
    heroes = [
            HeroType.Vekk.value,
            HeroType.Ogden.value,
            HeroType.Gwen.value,
            HeroType.Olias.value,
            HeroType.Xandra.value,
            HeroType.Livia.value,
            HeroType.PyreFierceshot.value
        ]
    templates = [
            "OgNDwcnfO1CahWseAG/IkEdC",
            "OwUTMwmCZaj4upB8ioLKDoHghAA",
            "OQhkAsC8gFKTIc6lDMdyghQG4iB",
            "OABCQsx0MTNUmQjohDN0ggAA",
            "OAOjAyhDJPYTnp17xFOhmtkLGA",
            "OAhjQwGc4QzM1QZCNiGO0QDCXMA",
            "OgQUQ4DdXcN1QOhmA1IJGECHfDA"

        ]
    return BT.Sequence(
            name="Prepare Standard EotN Party",
            children=[
                BT.CreateParty(
                    hero_ids=heroes,
                    multibox_invite=False,
                    log=True,
                ),
                *[
                    BT.LoadHeroSkillbar(index, template, log=True)
                    for index, template in enumerate(templates, start=1)
                ],
            ],
        )

def _prepare_standard_party() -> BehaviorTree:
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
                henchman_ids=[1,3,6,9],
                multibox_invite=False,
                log=True,
            ),
            *[
                BT.LoadHeroSkillbar(index, template, log=True)
                for index, template in enumerate(templates, start=1)
            ],
        ],
    )

def _prepare_standard_party2() -> BehaviorTree:
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

# Blood Washes Blood - stable IDs confirmed by probes.
EGIL_MODEL_ID = 6397
BEAR_SPIRIT_MODEL_ID = 6461
BLOOD_WASHES_BLOOD_BEAR_FORM_EFFECT_ID = 228
BLOOD_WASHES_BLOOD_URSAN_FORCE_SKILL_ID = 2396


def _maintain_blood_washes_blood_bear_form() -> BehaviorTree:
    """Use the temporary bear transformation when available without blocking combat.

    Normal skillbar:
      - If Ursan Aura is present and ready, cast it.
      - Otherwise do nothing and let HeroAI use the normal build.

    Bear skillbar:
      - Detect the Blood Washes Blood bear bar from mission Ursan Force (2396)
        being present specifically in slot 4.
      - Use mission Ursan Force whenever it is ready and its own effect is not
        already active.
      - Never cast an arbitrary normal-build slot 4.
    """

    def _has_bear_form() -> BehaviorTree.NodeState:
        # The mission bear form replaces the normal bar and puts the
        # Blood Washes Blood version of Ursan Force (2396) in slot 4.
        # Detect the temporary bar directly instead of passing the probed
        # effect id 228 to Effects.HasEffect(), which expects a skill id.
        ursan_force_slot = int(
            GLOBAL_CACHE.SkillBar.GetSlotBySkillID(
                BLOOD_WASHES_BLOOD_URSAN_FORCE_SKILL_ID
            ) or 0
        )
        return (
            BehaviorTree.NodeState.SUCCESS
            if ursan_force_slot == 4
            else BehaviorTree.NodeState.FAILURE
        )

    def _does_not_have_bear_form() -> BehaviorTree.NodeState:
        return (
            BehaviorTree.NodeState.FAILURE
            if _has_bear_form() == BehaviorTree.NodeState.SUCCESS
            else BehaviorTree.NodeState.SUCCESS
        )

    def _ursan_aura_is_in_skillbar() -> BehaviorTree.NodeState:
        ursan_aura_id = int(GLOBAL_CACHE.Skill.GetID("Ursan_Aura") or 0)
        if ursan_aura_id <= 0:
            return BehaviorTree.NodeState.FAILURE

        slot = int(GLOBAL_CACHE.SkillBar.GetSlotBySkillID(ursan_aura_id) or 0)
        return (
            BehaviorTree.NodeState.SUCCESS
            if 1 <= slot <= 8
            else BehaviorTree.NodeState.FAILURE
        )

    def _ursan_force_is_in_bear_bar_and_needed() -> BehaviorTree.NodeState:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            return BehaviorTree.NodeState.FAILURE

        slot = int(
            GLOBAL_CACHE.SkillBar.GetSlotBySkillID(
                BLOOD_WASHES_BLOOD_URSAN_FORCE_SKILL_ID
            ) or 0
        )
        if slot != 4:
            return BehaviorTree.NodeState.FAILURE

        return (
            BehaviorTree.NodeState.FAILURE
            if GLOBAL_CACHE.Effects.HasEffect(
                player_id,
                BLOOD_WASHES_BLOOD_URSAN_FORCE_SKILL_ID,
            )
            else BehaviorTree.NodeState.SUCCESS
        )

    def _cast_ursan_aura() -> BehaviorTree:
        ursan_aura_id = int(GLOBAL_CACHE.Skill.GetID("Ursan_Aura") or 0)
        if ursan_aura_id <= 0:
            return BT.Failer(name="Ursan Aura Is Not Available")

        return RoutinesBT.Skills.CastSkillID(
            skill_id=ursan_aura_id,
            aftercast_delay=250,
            log=True,
        )

    return BT.Selector(
        name="Maintain Blood Washes Blood Bear Form",
        children=[
            BT.Sequence(
                name="Use Ursan Force While In Bear Form",
                children=[
                    BehaviorTree(
                        BehaviorTree.ConditionNode(
                            name="Check Bear Form Active",
                            condition_fn=_has_bear_form,
                        )
                    ),
                    BehaviorTree(
                        BehaviorTree.ConditionNode(
                            name="Check Mission Ursan Force Is Available",
                            condition_fn=_ursan_force_is_in_bear_bar_and_needed,
                        )
                    ),
                    RoutinesBT.Skills.CastSkillID(
                        skill_id=BLOOD_WASHES_BLOOD_URSAN_FORCE_SKILL_ID,
                        aftercast_delay=250,
                        log=True,
                    ),
                ],
            ),
            BT.Sequence(
                name="Enter Bear Form When Ursan Aura Is Ready",
                children=[
                    BehaviorTree(
                        BehaviorTree.ConditionNode(
                            name="Check Bear Form Inactive",
                            condition_fn=_does_not_have_bear_form,
                        )
                    ),
                    BehaviorTree(
                        BehaviorTree.ConditionNode(
                            name="Check Ursan Aura Is In Skillbar",
                            condition_fn=_ursan_aura_is_in_skillbar,
                        )
                    ),
                    BT.Subtree(
                        name="Cast Ursan Aura Transformation",
                        subtree_fn=lambda _node: _cast_ursan_aura(),
                    ),
                ],
            ),
            BT.Succeeder(
                name="Bear Transformation Unavailable - Continue Normal HeroAI Combat"
            ),
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
# Granular planner helpers
# ---------------------------------------------------------------------------

PathPoint = Vec2f | tuple[float, float] | tuple[int, int]
PlannerStep = tuple[str, Callable[[], BehaviorTree]]


# ---------------------------------------------------------------------------
# Temporary loot diagnostics
# ---------------------------------------------------------------------------

EOTN_LOOT_DIAGNOSTIC_MODEL_IDS = (25413,)
_eotn_loot_diag_last_signature: dict[int, tuple[object, ...]] = {}
_eotn_loot_diag_next_tick_at = 0.0


def _collect_eotn_loot_diag(model_id: int) -> tuple[tuple[object, ...], str]:
    """Collect the LIVE loot state without changing it."""
    model_id = int(model_id)
    map_id = int(Map.GetMapID() or 0)
    account_email = str(Player.GetAccountEmail() or "")

    public_loot = None
    controller_loot = None
    import_error = ""

    try:
        from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters import (
            LootFilters as PublicLootFilters,
        )
        public_loot = PublicLootFilters()
    except Exception as exc:
        import_error = f"public_import={exc!r}"

    try:
        from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters.controller import (
            LootFilters as ControllerLootFilters,
        )
        controller_loot = ControllerLootFilters()
    except Exception as exc:
        import_error = (
            f"{import_error}; controller_import={exc!r}"
            if import_error
            else f"controller_import={exc!r}"
        )

    loot = controller_loot or public_loot
    if loot is None:
        signature = (map_id, model_id, "lootfilters-unavailable", import_error)
        return signature, (
            f"[LootDiag] map={map_id} model={model_id} "
            f"LootFilters unavailable: {import_error}"
        )

    live = getattr(loot, "live", None)
    enabled = getattr(live, "enabled", None)

    added_models = set(getattr(live, "added_model_ids", ()) or ())
    blacklisted_models = set(getattr(live, "blacklist_model_ids", ()) or ())
    blacklisted_types = set(getattr(live, "blacklist_item_types", ()) or ())

    added = model_id in added_models
    model_blacklisted = model_id in blacklisted_models

    item_type = None
    type_vetoed = None
    try:
        from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters.expected_types import (
            expected_type,
        )
        item_type = expected_type(model_id)
        type_vetoed = (
            item_type is not None
            and int(item_type) in blacklisted_types
        )
    except Exception:
        pass

    public_controller_same = (
        public_loot is not None
        and controller_loot is not None
        and public_loot is controller_loot
    )

    # Crucial hot-reload probe:
    # inspect the LootFilters class actually captured by the BT wrapper chain.
    bt_loot_class = None
    bt_loot = None
    bt_class_same = None
    bt_instance_same = None
    bt_added = None
    bt_probe_error = ""

    try:
        wrapper_routines = BT.AddModelToLootWhitelist.__globals__.get("RoutinesBT")
        wrapper_items = getattr(wrapper_routines, "Items", None)
        wrapper_add_fn = getattr(wrapper_items, "AddModelToLootWhitelist", None)
        wrapper_globals = getattr(wrapper_add_fn, "__globals__", {})
        bt_loot_class = wrapper_globals.get("LootFilters")

        if bt_loot_class is not None:
            bt_loot = bt_loot_class()
            bt_class_same = (
                controller_loot is not None
                and bt_loot_class is controller_loot.__class__
            )
            bt_instance_same = (
                controller_loot is not None
                and bt_loot is controller_loot
            )
            bt_live = getattr(bt_loot, "live", None)
            bt_added = model_id in set(
                getattr(bt_live, "added_model_ids", ()) or ()
            )
    except Exception as exc:
        bt_probe_error = repr(exc)

    try:
        wanted_loot = {
            int(agent_id)
            for agent_id in (loot.GetLootArray(Range.Earshot.value) or [])
            if int(agent_id or 0) > 0
        }
    except Exception:
        wanted_loot = set()

    player_x, player_y = Player.GetXY()
    ground_details: list[str] = []
    ground_signature: list[tuple[int, int, bool]] = []

    try:
        ground_item_agents = AgentArray.GetItemArray() or []
    except Exception:
        ground_item_agents = []

    for raw_agent_id in ground_item_agents:
        agent_id = int(raw_agent_id or 0)
        if agent_id <= 0:
            continue

        try:
            item_id = int(Agent.GetItemAgentItemID(agent_id) or 0)
            if item_id <= 0:
                continue

            ground_model_id = int(GLOBAL_CACHE.Item.GetModelID(item_id) or 0)
            if ground_model_id != model_id:
                continue

            owner_id = int(Agent.GetItemAgentOwnerID(agent_id) or 0)
            item_x, item_y = Agent.GetXY(agent_id)
            dx = float(item_x) - float(player_x)
            dy = float(item_y) - float(player_y)
            distance = (dx * dx + dy * dy) ** 0.5
            in_wanted_loot = agent_id in wanted_loot

            ground_signature.append((agent_id, owner_id, in_wanted_loot))
            ground_details.append(
                (
                    f"agent={agent_id},item={item_id},owner={owner_id},"
                    f"dist={distance:.0f},in_GetLootArray={in_wanted_loot}"
                )
            )
        except Exception as exc:
            ground_details.append(f"agent={agent_id},probe_error={exc!r}")

    pickup_message_indices: list[int] = []
    try:
        pickup_command = int(SharedCommandType.PickUpLoot)
        for message_index, message in GLOBAL_CACHE.ShMem.GetAllMessages():
            if message is None:
                continue
            if not bool(getattr(message, "Active", False)):
                continue
            if str(getattr(message, "ReceiverEmail", "") or "") != account_email:
                continue
            if int(getattr(message, "Command", -1)) != pickup_command:
                continue
            pickup_message_indices.append(int(message_index))
    except Exception:
        pickup_message_indices = []

    looting_enabled = None
    looting_active = None
    if botting_tree is not None:
        try:
            looting_enabled = bool(botting_tree.IsLootingEnabled())
        except Exception:
            pass
        try:
            looting_active = bool(botting_tree.IsLootingActive())
        except Exception:
            pass

    signature = (
        map_id,
        model_id,
        enabled,
        added,
        model_blacklisted,
        item_type,
        type_vetoed,
        public_controller_same,
        bt_class_same,
        bt_instance_same,
        bt_added,
        tuple(sorted(ground_signature)),
        tuple(sorted(pickup_message_indices)),
        looting_enabled,
        looting_active,
    )

    ground_text = "none" if not ground_details else " | ".join(ground_details)
    message = (
        f"[LootDiag] map={map_id} model={model_id} "
        f"master={enabled} added={added} "
        f"model_blacklisted={model_blacklisted} "
        f"item_type={item_type} type_vetoed={type_vetoed} "
        f"same_public_controller={public_controller_same} "
        f"bt_class_same={bt_class_same} "
        f"bt_instance_same={bt_instance_same} "
        f"bt_added={bt_added} "
        f"looting_enabled={looting_enabled} looting_active={looting_active} "
        f"pickup_messages={pickup_message_indices} "
        f"ground=[{ground_text}]"
    )
    if import_error:
        message += f" import_note={import_error}"
    if bt_probe_error:
        message += f" bt_probe_error={bt_probe_error}"

    return signature, message


def _emit_eotn_loot_diag(
    model_id: int,
    context: str,
    *,
    force: bool = False,
) -> None:
    model_id = int(model_id)
    signature, message = _collect_eotn_loot_diag(model_id)

    if (
        not force
        and _eotn_loot_diag_last_signature.get(model_id) == signature
    ):
        return

    _eotn_loot_diag_last_signature[model_id] = signature
    ConsoleLog(
        MODULE_NAME,
        f"{context}: {message}",
        log=True,
    )


def _tick_eotn_loot_diagnostics() -> None:
    """Watch the loot state at 250 ms and log only meaningful changes."""
    global _eotn_loot_diag_next_tick_at

    now = time.monotonic()
    if now < _eotn_loot_diag_next_tick_at:
        return

    _eotn_loot_diag_next_tick_at = now + 0.25

    for model_id in EOTN_LOOT_DIAGNOSTIC_MODEL_IDS:
        try:
            _emit_eotn_loot_diag(
                model_id,
                "Runtime",
                force=False,
            )
        except Exception as exc:
            ConsoleLog(
                MODULE_NAME,
                f"[LootDiag] runtime probe failed for model {model_id}: {exc!r}",
                log=True,
            )


def _loot_diag_once(model_id: int, context: str) -> BehaviorTree:
    def _probe() -> BehaviorTree.NodeState:
        try:
            _emit_eotn_loot_diag(
                int(model_id),
                str(context),
                force=True,
            )
        except Exception as exc:
            ConsoleLog(
                MODULE_NAME,
                f"[LootDiag] one-shot probe failed in {context}: {exc!r}",
                log=True,
            )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Loot Diagnostic - {context}",
            action_fn=_probe,
            aftercast_ms=0,
        )
    )


def _add_model_to_loot_whitelist_with_diag(
    model_id: int,
    context: str,
) -> BehaviorTree:
    """Use the stock helper, with a before/after proof of the LIVE state."""
    return BT.Sequence(
        name=f"{context} - Add Loot Whitelist With Diagnostic",
        children=[
            _loot_diag_once(model_id, f"{context} BEFORE add"),
            BT.AddModelToLootWhitelist(int(model_id)),
            _loot_diag_once(model_id, f"{context} AFTER add"),
        ],
    )



def _planner_map_prep_step(
    name: str,
    map_id_or_name: int | str,
) -> PlannerStep:
    """Expose BT.Sequence(map_id_or_name=...) as its own named planner step."""
    if isinstance(map_id_or_name, int):
        return (
            name,
            lambda map_id=int(map_id_or_name): BT.Travel(
                target_map_id=map_id,
            ),
        )

    return (
        name,
        lambda map_name=str(map_id_or_name): BT.Travel(
            target_map_name=map_name,
        ),
    )


class _TickSidecarWhileMainRunningNode(BehaviorTree.Node):
    """Tick a side behavior while the main behavior is RUNNING.

    The main child owns SUCCESS/FAILURE.  This is intentionally different from
    ParallelNode: when Vanquish finishes, the side behavior cannot keep the
    wrapper RUNNING and accidentally cause the completed Vanquish to restart.
    """

    def __init__(
        self,
        main: BehaviorTree | BehaviorTree.Node,
        sidecar: BehaviorTree | BehaviorTree.Node,
        *,
        name: str,
    ) -> None:
        super().__init__(
            name=name,
            node_type="TickSidecarWhileMainRunning",
            node_category="decorator",
        )
        self.main = self._coerce_node(main)
        self.sidecar = self._coerce_node(sidecar)

    def get_children(self) -> list[BehaviorTree.Node]:
        return [self.main, self.sidecar]

    def reset(self) -> None:
        super().reset()
        self.main.reset()
        self.sidecar.reset()

    def _tick_impl(self) -> BehaviorTree.NodeState:
        if self.blackboard is not None:
            self.main.blackboard = self.blackboard
            self.sidecar.blackboard = self.blackboard

        main_state = self.main.tick()

        if main_state != BehaviorTree.NodeState.RUNNING:
            self.sidecar.reset()
            return main_state

        sidecar_state = self.sidecar.tick()
        if sidecar_state != BehaviorTree.NodeState.RUNNING:
            # The bear-form maintenance selector is one-shot. Reset it after
            # each completed attempt so it can run again on the next main tick.
            self.sidecar.reset()

        return BehaviorTree.NodeState.RUNNING


def _planner_vanquish_point_steps(
    name: str,
    points: Sequence[PathPoint],
    *,
    during_step_factory: Callable[[], BehaviorTree] | None = None,
    **kwargs,
) -> list[PlannerStep]:
    """Expose every VanquishNode waypoint as an independent named planner step.

    This intentionally keeps the behavior of VanquishNode itself for each point,
    while giving the planner explicit sequential progress. A wipe can therefore
    restart the current point instead of replaying an entire multi-point route.
    """
    point_list = list(points)
    total = len(point_list)
    result: list[PlannerStep] = []

    for index, point in enumerate(point_list, start=1):
        step_name = f"{name} - Point {index:02d}/{total:02d}"
        bound_kwargs = dict(kwargs)
        bound_kwargs.setdefault("clear_area_radius", Range.Earshot.value)

        def _factory(
            bound_point=point,
            bound_kwargs=bound_kwargs,
            bound_step_name=step_name,
            bound_during_step_factory=during_step_factory,
        ) -> BehaviorTree:
            vanquish = BT.VanquishNode(
                [bound_point],
                **bound_kwargs,
            )

            if bound_during_step_factory is None:
                return vanquish

            return BehaviorTree(
                _TickSidecarWhileMainRunningNode(
                    main=vanquish,
                    sidecar=bound_during_step_factory(),
                    name=f"{bound_step_name} - Maintain Side Behavior",
                )
            )

        result.append((step_name, _factory))

    return result


class _RetryMoveDirectUntilReachedNode(BehaviorTree.Node):
    """Probe a passage directly until the player is physically on the far side.

    Blood Washes Blood barricades must not use normal pathfinding for the
    far-side verification point: while the barricade is still present, the
    pathfinder can choose an alternate route. MoveDirect keeps the supplied
    verification point as the direct movement target instead.
    """

    def __init__(
        self,
        destination: Vec2f,
        *,
        name: str,
        tolerance: float = 180.0,
        retry_interval_ms: int = 6_000,
    ) -> None:
        super().__init__(
            name=name,
            node_type="RetryMoveDirectUntilReached",
            node_category="movement",
        )
        self.destination = destination
        self.tolerance = max(1.0, float(tolerance))
        self.retry_interval_ms = max(500, int(retry_interval_ms))
        self.move = self._coerce_node(
            BT.MoveDirect(
                destination,
                pause_on_combat=False,
                log=True,
            )
        )
        self.attempt_started_at = 0.0

    def get_children(self) -> list[BehaviorTree.Node]:
        return [self.move]

    def reset(self) -> None:
        super().reset()
        self.move.reset()
        self.attempt_started_at = 0.0

    def _destination_reached(self) -> bool:
        x, y = Player.GetXY()
        dx = float(x) - float(self.destination.x)
        dy = float(y) - float(self.destination.y)
        return dx * dx + dy * dy <= self.tolerance * self.tolerance

    def _restart_move(self, now: float) -> None:
        self.move.reset()
        self.attempt_started_at = now

    def _tick_impl(self) -> BehaviorTree.NodeState:
        if self._destination_reached():
            return BehaviorTree.NodeState.SUCCESS

        if self.blackboard is not None:
            self.move.blackboard = self.blackboard

        now = time.monotonic()
        if self.attempt_started_at <= 0.0:
            self.attempt_started_at = now
        elif (now - self.attempt_started_at) * 1000.0 >= self.retry_interval_ms:
            ConsoleLog(
                MODULE_NAME,
                f"{self.name}: passage not confirmed; retrying direct verification.",
                log=True,
            )
            self._restart_move(now)

        move_state = self.move.tick()

        if self._destination_reached():
            return BehaviorTree.NodeState.SUCCESS

        if move_state != BehaviorTree.NodeState.RUNNING:
            self._restart_move(now)

        return BehaviorTree.NodeState.RUNNING


def _verify_blood_washes_blood_barricade_passage(
    name: str,
    verify_point: Vec2f,
) -> BehaviorTree:
    """Use the far-side coordinate only to prove that the barricade is open."""
    return BehaviorTree(
        _TickSidecarWhileMainRunningNode(
            main=_RetryMoveDirectUntilReachedNode(
                verify_point,
                name=f"{name} - Verify Player Crossed Barricade",
            ),
            sidecar=_maintain_blood_washes_blood_bear_form(),
            name=f"{name} - Verify Passage With Bear Form",
        )
    )


# ---------------------------------------------------------------------------
# Initialization and optional Hall of Monuments unlock
# ---------------------------------------------------------------------------


def _steps_InitializeBot() -> list[PlannerStep]:
    return [
        ('Initialize Bot - 01 Aggressive', lambda: _aggressive()),
        ('Initialize Bot - 02 Log Message', lambda: BT.LogMessage(message='EotN Storyline BottingTree initialized.', module_name=MODULE_NAME)),
    ]

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

def _steps_UnlockEyeOfTheNorthPool() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('UnlockEyeOfTheNorthPool' + ' - 00 Map Preparation', 675),
        ('UnlockEyeOfTheNorthPool - 01 Prepare Standard Party', lambda: _prepare_standard_party()),
        ('UnlockEyeOfTheNorthPool - 02 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(4141, -27703), target_map_id=499)),
        ('UnlockEyeOfTheNorthPool - 03 Move', lambda: BT.Move(Vec2f(3598.97, -22331.73))),
        ('UnlockEyeOfTheNorthPool - 04 Wait', lambda: BT.Wait(10000)),
        ('UnlockEyeOfTheNorthPool - 05 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(3537.0, -21937.0), 8622340)),
        *_planner_vanquish_point_steps('UnlockEyeOfTheNorthPool - 06 Vanquish Route 01', path_to_eotn),
        ('UnlockEyeOfTheNorthPool - 07 Wait EOTN Outpost' , lambda : BT.WaitForMapLoad(642)),
        ('UnlockEyeOfTheNorthPool - 08 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-5198.0, 5595.0), target_map_id=646)),
        ('UnlockEyeOfTheNorthPool - 09 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-6572.7, 6588.83), 8388609)),
        ('UnlockEyeOfTheNorthPool - 10 Wait', lambda: BT.Wait(2000)),
        ('UnlockEyeOfTheNorthPool - 11 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-6662.0, 6584.0), 1599)),
        ('UnlockEyeOfTheNorthPool - 12 Wait', lambda: BT.Wait(6000)),
        ('UnlockEyeOfTheNorthPool - 13 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-6572.7, 6588.83), 137)),
        ('UnlockEyeOfTheNorthPool - 14 Wait', lambda: BT.Wait(1000)),
        ('UnlockEyeOfTheNorthPool - 15 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=646)),
        ('UnlockEyeOfTheNorthPool - 16 Send Dialog', lambda: BT.SendDialog(137)),
        ('UnlockEyeOfTheNorthPool - 17 Send Dialog', lambda: BT.SendDialog(8591620)),
        ('UnlockEyeOfTheNorthPool - 18 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-6133.41, 5717.3), 8620292)),
        ('UnlockEyeOfTheNorthPool - 19 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-5626.8, 6259.57), 8622852)),
    ]


def _steps_ObtainStoryBook() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Obtain Story Book' + ' - 00 Map Preparation', 'Eye of the North outpost'),
        ('Obtain Story Book - 01 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-1998.0, 2797.0), 16804114)),
        ('Obtain Story Book - 02 Send Dialog', lambda: BT.SendDialog(128)),
    ]


# ---------------------------------------------------------------------------
# Norn storyline
# ---------------------------------------------------------------------------


def _steps_TravelToGunnarsHold() -> list[PlannerStep]:
    return [
        _planner_map_prep_step("Travel To Gunnar's Hold" + ' - 00 Map Preparation', 'Eye of the North outpost'),
        ("Travel To Gunnar's Hold - 01 Prepare Standard Party Olias", lambda: _prepare_standard_party_olias()),
        ("Travel To Gunnar's Hold - 02 Aggressive", lambda: _aggressive()),
        ("Travel To Gunnar's Hold - 03 Move And Exit Map", lambda: BT.MoveAndExitMap(Vec2f(1522.0, 464.0), target_map_id=499)),
        ("Travel To Gunnar's Hold - 04 Move And Dialog", lambda: BT.MoveAndDialog(Vec2f(2825.0, -481.0), 8595457)),
        *_planner_vanquish_point_steps("Travel To Gunnar's Hold - 05 Vanquish Route 01", [(2548.84, 7266.08), (1233.76, 13803.42), (978.88, 21837.26), (-4031.0, 27872.0)]),
        ("Travel To Gunnar's Hold - 06 Wait For Map Load", lambda: BT.WaitForMapLoad(map_id=548)),
        ("Travel To Gunnar's Hold - 07 Move", lambda: BT.Move(Vec2f(14546.0, -6043.0))),
        ("Travel To Gunnar's Hold - 08 Move And Exit Map", lambda: BT.MoveAndExitMap(Vec2f(15578.0, -6548.0), target_map_id=644, log=True)),
    ]




def _steps_Unlock_Xandra() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Talk To Gunnar' + ' - 00 Map Preparation', "Gunnar's Hold"),
        ('Talk To Gunnar - 01 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(24078.0, -7512.0), 8595460)),
    ]

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

# Optional elite used for the Norn Tournament setup.
# The account must already have the elite unlocked; the character learns it
# from an Elite Ritualist Tome through RoutinesBT.Player.LearnSkillFromTome.
NORN_TOURNAMENT_OPTIONAL_ELITE_SKILL = "Signet_of_Spirits"
RITUALIST_ELITE_TOME_MODEL_ID = int(ModelID.Ritualist_Elite_Tome.value)
GOLD_ZAISHEN_COIN_MODEL_ID = int(ModelID.Gold_Zaishen_Coin.value)

from Py4GWCoreLib.Skill import Skill
Painful_Bond_ID = Skill.GetID("Painful_Bond")

PRE_XANDRA_BUILD_BLACKBOARD_KEY = "eotn_pre_xandra_player_build"

# Conservé hors du blackboard pour survivre à un restart du Planner.
_pre_xandra_player_build_snapshot: dict[str, object] | None = None


def SavePreXandraPlayerBuild(log: bool = True) -> BehaviorTree:
    """Capture the player's current profession, attributes and 8-slot skillbar."""

    def _save(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _pre_xandra_player_build_snapshot

        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            return BehaviorTree.NodeState.FAILURE

        primary_id, secondary_id = Agent.GetProfessionIDs(player_id)
        primary_id = int(primary_id or 0)
        secondary_id = int(secondary_id or 0)

        if primary_id <= 0:
            return BehaviorTree.NodeState.FAILURE

        raw_attributes = Agent.GetAttributesDict(player_id) or {}
        attributes = {
            int(attribute_id): max(0, min(12, int(value or 0)))
            for attribute_id, value in raw_attributes.items()
            if int(value or 0) > 0
        }

        skills = tuple(
            int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) or 0)
            for slot in range(1, 9)
        )

        template = Utils.GenerateSkillbarTemplateFrom(
            prof_primary=primary_id,
            prof_secondary=secondary_id,
            attributes=attributes,
            skills=list(skills),
        )

        if not template:
            ConsoleLog(
                MODULE_NAME,
                "Unable to generate the pre-Xandra player build template.",
                log=True,
            )
            return BehaviorTree.NodeState.FAILURE

        snapshot = {
            "template": str(template),
            "primary_id": primary_id,
            "secondary_id": secondary_id,
            "attributes": dict(attributes),
            "skills": skills,
        }

        # Blackboard pour le fonctionnement normal.
        node.blackboard[PRE_XANDRA_BUILD_BLACKBOARD_KEY] = snapshot

        # Copie persistante pour survivre à un restart de l'étape.
        _pre_xandra_player_build_snapshot = snapshot

        if log:
            ConsoleLog(
                MODULE_NAME,
                (
                    "Saved pre-Xandra player build: "
                    f"primary={primary_id}, secondary={secondary_id}, "
                    f"skills={list(skills)}."
                ),
                log=True,
            )

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Save Pre-Xandra Player Build",
            action_fn=_save,
            aftercast_ms=0,
        )
    )


def RestorePreXandraPlayerBuild(log: bool = True) -> BehaviorTree:
    """Restore profession and skillbar captured before the Xandra setup."""

    def _build(node: BehaviorTree.Node) -> BehaviorTree:
        snapshot = node.blackboard.get(PRE_XANDRA_BUILD_BLACKBOARD_KEY)

        # Le blackboard est vidé lors d'un Planner restart.
        # On retombe donc sur la copie persistante.
        if not isinstance(snapshot, dict):
            snapshot = _pre_xandra_player_build_snapshot

        if not isinstance(snapshot, dict):
            ConsoleLog(
                MODULE_NAME,
                "Pre-Xandra build snapshot is missing.",
                log=True,
            )
            return BT.Failer(name="Pre-Xandra Build Snapshot Missing")

        template = str(snapshot.get("template", "") or "")
        primary_id = int(snapshot.get("primary_id", 0) or 0)
        secondary_id = int(snapshot.get("secondary_id", 0) or 0)
        saved_skills = tuple(
            int(value or 0)
            for value in snapshot.get("skills", ())
        )

        if not template or primary_id <= 0 or len(saved_skills) != 8:
            ConsoleLog(
                MODULE_NAME,
                "Pre-Xandra build snapshot is invalid.",
                log=True,
            )
            return BT.Failer(name="Pre-Xandra Build Snapshot Invalid")

        def _restore_secondary() -> BehaviorTree.NodeState:
            player_id = int(Player.GetAgentID() or 0)
            if player_id <= 0:
                return BehaviorTree.NodeState.FAILURE

            current_primary_id, current_secondary_id = Agent.GetProfessionIDs(
                player_id
            )
            current_primary_id = int(current_primary_id or 0)
            current_secondary_id = int(current_secondary_id or 0)

            if current_primary_id != primary_id:
                ConsoleLog(
                    MODULE_NAME,
                    (
                        "Cannot restore pre-Xandra build: "
                        f"primary profession changed "
                        f"({current_primary_id}/{primary_id})."
                    ),
                    log=True,
                )
                return BehaviorTree.NodeState.FAILURE

            if current_secondary_id == secondary_id:
                return BehaviorTree.NodeState.SUCCESS

            changed = bool(
                PySkillbar.change_second_profession(
                    secondary_id,
                    0,  # player
                )
            )

            if log:
                ConsoleLog(
                    MODULE_NAME,
                    (
                        "Requested pre-Xandra secondary profession: "
                        f"{current_secondary_id} -> {secondary_id}."
                    ),
                    log=True,
                )

            return (
                BehaviorTree.NodeState.SUCCESS
                if changed
                else BehaviorTree.NodeState.FAILURE
            )

        def _profession_restored() -> BehaviorTree.NodeState:
            player_id = int(Player.GetAgentID() or 0)
            if player_id <= 0:
                return BehaviorTree.NodeState.FAILURE

            current_primary_id, current_secondary_id = Agent.GetProfessionIDs(
                player_id
            )

            return (
                BehaviorTree.NodeState.SUCCESS
                if (
                    int(current_primary_id or 0) == primary_id
                    and int(current_secondary_id or 0) == secondary_id
                )
                else BehaviorTree.NodeState.FAILURE
            )

        def _build_restored() -> BehaviorTree.NodeState:
            player_id = int(Player.GetAgentID() or 0)
            if player_id <= 0:
                return BehaviorTree.NodeState.FAILURE

            loaded_primary_id, loaded_secondary_id = Agent.GetProfessionIDs(
                player_id
            )

            loaded_skills = tuple(
                int(GLOBAL_CACHE.SkillBar.GetSkillIDBySlot(slot) or 0)
                for slot in range(1, 9)
            )

            return (
                BehaviorTree.NodeState.SUCCESS
                if (
                    int(loaded_primary_id or 0) == primary_id
                    and int(loaded_secondary_id or 0) == secondary_id
                    and loaded_skills == saved_skills
                )
                else BehaviorTree.NodeState.FAILURE
            )

        def _log_success() -> BehaviorTree.NodeState:
            if log:
                ConsoleLog(
                    MODULE_NAME,
                    (
                        "Pre-Xandra player build restored successfully: "
                        f"primary={primary_id}, secondary={secondary_id}, "
                        f"skills={list(saved_skills)}."
                    ),
                    log=True,
                )

            return BehaviorTree.NodeState.SUCCESS

        return BT.Sequence(
            name="Restore Pre-Xandra Player Build",
            children=[
                BehaviorTree(
                    BehaviorTree.ActionNode(
                        name="Restore Pre-Xandra Secondary Profession",
                        action_fn=_restore_secondary,
                        aftercast_ms=500,
                    )
                ),

                BehaviorTree(
                    BehaviorTree.WaitUntilSuccessNode(
                        name="Wait For Pre-Xandra Profession",
                        condition_fn=_profession_restored,
                        throttle_interval_ms=100,
                        timeout_ms=5_000,
                    )
                ),

                BT.LoadSkillbar(
                    template=template,
                    log=log,
                ),

                BehaviorTree(
                    BehaviorTree.WaitUntilSuccessNode(
                        name="Wait For Pre-Xandra Skillbar",
                        condition_fn=_build_restored,
                        throttle_interval_ms=100,
                        timeout_ms=5_000,
                    )
                ),

                BehaviorTree(
                    BehaviorTree.ActionNode(
                        name="Confirm Pre-Xandra Build Restored",
                        action_fn=_log_success,
                        aftercast_ms=0,
                    )
                ),
            ],
        )

    return BT.Subtree(
        name="Restore Saved Pre-Xandra Player Build",
        subtree_fn=_build,
    )

NORN_TOURNAMENT_SPIRIT_CASTS = (
    ("Bloodsong", 3_500),
    ("Shadowsong", 3_500),
    ("Pain", 3_500),
    ("Destruction", 3_500),
    ("Disenchantment", 5_500),
)


def _skill_state_condition(
    skill_name: str,
    *,
    learned: bool,
    name: str,
) -> BehaviorTree:
    """Check either the character-learned or account-unlocked skill state."""
    skill_id = int(GLOBAL_CACHE.Skill.GetID(skill_name) or 0)

    def _check() -> BehaviorTree.NodeState:
        if skill_id <= 0:
            return BehaviorTree.NodeState.FAILURE

        available = bool(
            GLOBAL_CACHE.SkillBar.IsSkillLearnt(skill_id)
            if learned
            else GLOBAL_CACHE.SkillBar.IsSkillUnlocked(skill_id)
        )
        return (
            BehaviorTree.NodeState.SUCCESS
            if available
            else BehaviorTree.NodeState.FAILURE
        )

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=name,
            condition_fn=_check,
        )
    )


def _storage_has_model(
    model_id: int,
    quantity: int,
    name: str,
) -> BehaviorTree:
    """Succeed when storage contains at least the requested model quantity."""

    def _check() -> BehaviorTree.NodeState:
        stored_quantity = int(
            GLOBAL_CACHE.Inventory.GetModelCountInStorage(model_id) or 0
        )
        return (
            BehaviorTree.NodeState.SUCCESS
            if stored_quantity >= int(quantity)
            else BehaviorTree.NodeState.FAILURE
        )

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=name,
            condition_fn=_check,
        )
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

    optional_signet_cast = BT.Selector(
        name="Cast Signet Of Spirits If Learned",
        children=[
            BT.Sequence(
                name="Signet Of Spirits Is Available",
                children=[
                    _skill_state_condition(
                        NORN_TOURNAMENT_OPTIONAL_ELITE_SKILL,
                        learned=True,
                        name="Check Signet Of Spirits Before Cast",
                    ),
                    _cast_norn_tournament_skill(
                        NORN_TOURNAMENT_OPTIONAL_ELITE_SKILL,
                        aftercast_delay_ms=1_500,
                        log=log,
                    ),
                ],
            ),
            BT.Succeeder(name="Continue Round Without Signet Of Spirits"),
        ],
    )

    return BT.Sequence(
        name="Manual Norn Tournament Round",
        children=[
            BT.Move(
                Tournament_Path[0],
                pause_on_combat=True,
                log=log,
                tolerance=50
            ),
            optional_signet_cast,
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
                            clear_area_radius=Range.Earshot.value,
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
    """Activate Ritualist as secondary profession when already unlocked."""

    ritualist_id = int(Profession.Ritualist.value)

    def _change_secondary() -> BehaviorTree.NodeState:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            return BehaviorTree.NodeState.FAILURE

        primary_id, secondary_id = Agent.GetProfessionIDs(player_id)
        primary_id = int(primary_id or 0)
        secondary_id = int(secondary_id or 0)

        # Ritualist primary: nothing to change.
        if primary_id == ritualist_id:
            return BehaviorTree.NodeState.SUCCESS

        # Ritualist already active as secondary.
        if secondary_id == ritualist_id:
            return BehaviorTree.NodeState.SUCCESS

        changed = bool(
            PySkillbar.change_second_profession(
                ritualist_id,
                0,  # 0 = player
            )
        )

        if log:
            ConsoleLog(
                MODULE_NAME,
                (
                    "Requested Ritualist as secondary profession."
                    if changed
                    else "Failed to request Ritualist as secondary profession."
                ),
                log=True,
            )

        return (
            BehaviorTree.NodeState.SUCCESS
            if changed
            else BehaviorTree.NodeState.FAILURE
        )

    def _verify_active() -> BehaviorTree.NodeState:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            return BehaviorTree.NodeState.FAILURE

        primary_id, secondary_id = Agent.GetProfessionIDs(player_id)

        active = bool(
            int(primary_id or 0) == ritualist_id
            or int(secondary_id or 0) == ritualist_id
        )

        if log:
            ConsoleLog(
                MODULE_NAME,
                (
                    "Ritualist profession is active."
                    if active
                    else "Ritualist profession activation verification failed."
                ),
                log=True,
            )

        return (
            BehaviorTree.NodeState.SUCCESS
            if active
            else BehaviorTree.NodeState.FAILURE
        )

    return BT.Sequence(
        name="Activate Ritualist Secondary",
        children=[
            BehaviorTree(
                BehaviorTree.ActionNode(
                    name="Change Secondary Profession To Ritualist",
                    action_fn=_change_secondary,
                    aftercast_ms=500,
                )
            ),
            BehaviorTree(
                BehaviorTree.ConditionNode(
                    name="Verify Ritualist Secondary Is Active",
                    condition_fn=_verify_active,
                )
            ),
        ],
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


def _learn_signet_of_spirits_from_elite_tome(
    log: bool = True,
) -> BehaviorTree:
    """Learn Signet of Spirits with the validated native SkillTome routine."""

    skill_id = int(
        GLOBAL_CACHE.Skill.GetID(NORN_TOURNAMENT_OPTIONAL_ELITE_SKILL) or 0
    )
    if skill_id <= 0:
        return BT.Failer(name="Resolve Signet Of Spirits Failed")

    # LearnSkillFromTome performs the complete native GW flow:
    # UseItem -> select the SkillTome row with real PyMouse input ->
    # click Learn -> verify IsSkillLearnt. No SendDialog is used.
    return RoutinesBT.Player.LearnSkillFromTome(
        skill_id=skill_id,
        log=log,
    )


def EnsureSignetOfSpirits(log: bool = True) -> BehaviorTree:
    """Learn Signet of Spirits when unlocked and a tome can be obtained."""

    skill_name = NORN_TOURNAMENT_OPTIONAL_ELITE_SKILL

    acquire_tome = BT.Selector(
        name="Acquire Elite Ritualist Tome If Available",
        children=[
            BT.HasItemQuantity(RITUALIST_ELITE_TOME_MODEL_ID, 1),
            BT.Sequence(
                name="Withdraw Stored Elite Ritualist Tome",
                children=[
                    _storage_has_model(
                        RITUALIST_ELITE_TOME_MODEL_ID,
                        1,
                        "Check Stored Elite Ritualist Tome",
                    ),
                    BT.RestockItems(
                        model_id=RITUALIST_ELITE_TOME_MODEL_ID,
                        desired_quantity=1,
                        allow_missing=False,
                    ),
                    BT.HasItemQuantity(RITUALIST_ELITE_TOME_MODEL_ID, 1),
                ],
            ),
            BT.Sequence(
                name="Buy Elite Ritualist Tome With Zaishen Coin",
                children=[
                    BT.Selector(
                        name="Check Gold Zaishen Coin Availability",
                        children=[
                            BT.HasItemQuantity(GOLD_ZAISHEN_COIN_MODEL_ID, 1),
                            _storage_has_model(
                                GOLD_ZAISHEN_COIN_MODEL_ID,
                                1,
                                "Check Stored Gold Zaishen Coin",
                            ),
                        ],
                    ),
                    BT.Travel(target_map_id=248, log=log),
                    BT.RestockItems(
                        model_id=GOLD_ZAISHEN_COIN_MODEL_ID,
                        desired_quantity=1,
                        allow_missing=False,
                    ),
                    BT.EqualizeGold(
                        target_gold=100,
                        deposit_all=False,
                        log=log,
                    ),
                    BT.TargetAgentByName(
                        agent_name="Jessie Llam",
                        log=log,
                    ),
                    BT.InteractTarget(log=log),
                    BT.Wait(1_000),
                    BT.CraftItem(
                        output_model_id=RITUALIST_ELITE_TOME_MODEL_ID,
                        trade_model_ids=[GOLD_ZAISHEN_COIN_MODEL_ID],
                        quantity_list=[1],
                        cost=100,
                        aftercast_ms=500,
                    ),
                    BT.Wait(1_000),
                    BT.HasItemQuantity(RITUALIST_ELITE_TOME_MODEL_ID, 1),
                ],
            ),
        ],
    )

    return BT.Selector(
        name="Ensure Optional Signet Of Spirits",
        children=[
            _skill_state_condition(
                skill_name,
                learned=True,
                name="Check Signet Of Spirits Learned",
            ),
            BT.Sequence(
                name="Learn Signet Of Spirits If Resources Are Available",
                children=[
                    _skill_state_condition(
                        skill_name,
                        learned=False,
                        name="Check Signet Of Spirits Account Unlock",
                    ),
                    acquire_tome,
                    _learn_signet_of_spirits_from_elite_tome(log=log),
                    _skill_state_condition(
                        skill_name,
                        learned=True,
                        name="Verify Signet Of Spirits Learned",
                    ),
                    BT.LogMessage(
                        message=(
                            "Signet of Spirits was learned from an "
                            "Elite Ritualist Tome."
                        ),
                        module_name=MODULE_NAME,
                    ),
                ],
            ),
            BT.Sequence(
                name="Skip Optional Signet Of Spirits",
                children=[
                    BT.LogMessage(
                        message=(
                            "Signet of Spirits is unavailable or no usable Elite "
                            "Ritualist Tome / Gold Zaishen Coin could be obtained; "
                            "the tournament setup continues without it."
                        ),
                        module_name=MODULE_NAME,
                    ),
                    BT.Succeeder(name="Continue Without Signet Of Spirits"),
                ],
            ),
        ],
    )


def _equip_norn_tournament_build(log: bool = True) -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        player_id = int(Player.GetAgentID() or 0)
        primary_id, current_secondary_id = Agent.GetProfessionIDs(player_id)
        primary_id = int(primary_id or 0)
        skill_names = list(NORN_TOURNAMENT_SKILLS)

        optional_elite_id = int(
            GLOBAL_CACHE.Skill.GetID(NORN_TOURNAMENT_OPTIONAL_ELITE_SKILL)
            or 0
        )
        if (
            optional_elite_id > 0
            and GLOBAL_CACHE.SkillBar.IsSkillLearnt(optional_elite_id)
        ):
            # Keep Signet of Spirits in slot 1 when available. Existing
            # explicit casts use skill IDs, so the current round logic remains
            # valid even though the other skills shift one slot to the right.
            skill_names.insert(0, NORN_TOURNAMENT_OPTIONAL_ELITE_SKILL)

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
            EnsureSignetOfSpirits(log=log),
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


def _steps_PrepareXandraTournament() -> list[PlannerStep]:
    return [
        ('PrepareXandraTournament - 01 Prepare Norn Tournament Skills', lambda: UnlockNornTournamentSkills(log=True)),
        ('PrepareXandraTournament - 02 Travel', lambda: BT.Travel(target_map_name="Gunnar's Hold", log=True)),
        ('PrepareXandraTournament - 03 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(17763.0, -11467.0), 8604161)),
    ]




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


def _steps_TravelToSifhalla() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Travel To Sifhalla' + ' - 00 Map Preparation', 644),
        ('Travel To Sifhalla - 01 Prepare Standard Party Xandra', lambda: _prepare_standard_party_xandra()),
        ('Travel To Sifhalla - 02 Aggressive', lambda: _aggressive()),
        ('Travel To Sifhalla - 03 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(15193, -6387), target_map_name='Norrhart Domains')),
        *_planner_vanquish_point_steps('Travel To Sifhalla - 04 Vanquish Route 01', [(13337.167968, -3869.252929), (9826.771484, 416.337768), (6321.207031, 2398.933349), (2982.609619, 2118.243164), (176.124359, 2252.913574), (-3766.605468, 3390.211669), (-7325.385253, 2669.518066), (-9555.996093, 5570.137695), (-14153.492187, 5198.475585), (-18538.169921, 7079.861816), (-22717.630859, 8757.8125), (-25531.134765, 10925.24121), (-26333.171875, 11242.023437)]),
        ('Travel To Sifhalla - 05 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Drakkar Lake')),
        *_planner_vanquish_point_steps('Travel To Sifhalla - 06 Vanquish Route 02', [(14399.201171, -16963.455078), (12510.43164, -13414.477539), (12011.655273, -9633.283203), (11484.183593, -5569.488769), (12456.84375, -411.864135), (13398.728515, 4328.439453), (14000.825195, 8676.782226), (14210.789062, 12432.768554), (13846.64746, 15850.121093), (13595.982421, 18950.578125), (13567.612304, 19432.314453)]),
        ('Travel To Sifhalla - 07 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Sifhalla')),
    ]


def _steps_CompleteTrackingTheNornbear() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Tracking The Nornbear' + ' - 00 Map Preparation', 'Sifhalla'),
        ('Tracking The Nornbear - 01 Prepare Standard Party Xandra', lambda: _prepare_standard_party_xandra()),
        ('Tracking The Nornbear - 02 Aggressive', lambda: _aggressive()),
        ('Tracking The Nornbear - 03 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14353.0, 23905.0), 132)),
        ('Tracking The Nornbear - 04 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=678)),
        ('Tracking The Nornbear - 05 Wait', lambda: BT.Wait(2000)),
        ('Tracking The Nornbear - 06 Move', lambda: BT.Move(Vec2f(10388.0, 23888.0))),
        ('Tracking The Nornbear - 07 Wait', lambda: BT.Wait(8500)),
        ('Tracking The Nornbear - 08 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Sifhalla', timeout_ms=50000)),
        ('Tracking The Nornbear - 09 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14353.0, 23905.0), 8595463)),
    ]


def _steps_CompleteCurseOfTheNornbear() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Curse Of The Nornbear' + ' - 00 Map Preparation', 'Sifhalla'),
        ('Curse Of The Nornbear - 01 Prepare Standard Party Xandra', lambda: _prepare_standard_party_xandra()),
        ('Curse Of The Nornbear - 02 Aggressive', lambda: _aggressive()),
        ('Curse Of The Nornbear - 03 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14353.0, 23905.0), 134)),
        ('Curse Of The Nornbear - 04 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=653)),
        ('Curse Of The Nornbear - 05 Wait', lambda: BT.Wait(2000)),
        ('Curse Of The Nornbear - 06 Move', lambda: BT.Move(Vec2f(-2638.0, 20433.0))),
        ('Curse Of The Nornbear - 07 Wait', lambda: BT.Wait(5000)),
        ('Curse Of The Nornbear - 08 Move', lambda: BT.Move(Vec2f(-5793.0, 15818.0))),
        ('Curse Of The Nornbear - 09 Wait', lambda: BT.Wait(2000)),
        ('Curse Of The Nornbear - 10 Move', lambda: BT.Move(Vec2f(8105.0, 14089.0))),
        ('Curse Of The Nornbear - 11 Wait', lambda: BT.Wait(2000)),
        ('Curse Of The Nornbear - 12 Move', lambda: BT.Move(Vec2f(4940.0, 6551.0))),
        ('Curse Of The Nornbear - 13 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=643, timeout_ms=60000)),
        ('Curse Of The Nornbear - 14 Wait', lambda: BT.Wait(2000)),
        ('Curse Of The Nornbear - 15 Move', lambda: BT.Move(Vec2f(14353.0, 23905.0))),
        ('Curse Of The Nornbear - 16 Pacifist', lambda: _pacifist()),
        ('Curse Of The Nornbear - 17 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(14353.0, 23905.0), 8620292)),
        ('Curse Of The Nornbear - 18 Auto Dialog', lambda: BT.SendDialog(137)),
        ('Curse Of The Nornbear - 19 Auto Dialog', lambda: BT.SendDialog(138)),
    ]


def _steps_BloodWashesBlood() -> list[PlannerStep]:
    return [
        _planner_map_prep_step("Blood Washes Blood - 00 Map Preparation", "Sifhalla"),
        ("Blood Washes Blood - 01 Aggressive", lambda: _aggressive()),
        *_planner_vanquish_point_steps("Blood Washes Blood - 02 Vanquish Route 01", [(16163.0, 22852.0), (16717.0, 22789.0)]),
        ("Blood Washes Blood - 03 Wait For Map Load", lambda: BT.WaitForMapLoad(map_name="Jaga Moraine")),
        *_planner_vanquish_point_steps("Blood Washes Blood - 04 Vanquish Route 02", [(-11949.0, -23710.0), (-8929.0, -21112.0), (-6111.0, -14675.0), (-5757.0, -13735.0), (-4855.0, -10881.0), (-3702.0, -8096.0), (-2962.0, -7412.0), (-1397.0, -6161.0), (1055.0, -3190.0), (2170.0, -397.0), (2659.0, 484.0), (3151.0, 1355.0), (3726.0, 4064.0), (4621.0, 5918.0)]),
        ("Blood Washes Blood - 05 Pacifist", lambda: _pacifist()),
        ("Blood Washes Blood - 06 Move And Dialog", lambda: BT.MoveAndDialog(Vec2f(4621.0, 5918.0), 8593409)),
        ("Blood Washes Blood - 07 Aggressive", lambda: _aggressive()),
        *_planner_vanquish_point_steps("Blood Washes Blood - 08 Vanquish Route 03", [(3014.0, 3308.0), (-567.0, -1090.0), (5147.0, -5920.0), (10490.0, -9516.0), (11885.0, -16663.0), (9771.0, -21332.0)]),
        ("Blood Washes Blood - 09 Wait", lambda: BT.Wait(80000)),
        ("Blood Washes Blood - 10 Move and talk To Egil If Present", lambda: _move_to_egil_if_present()),
        ("Blood Washes Blood - 11 Pacifist", lambda: _pacifist()),
        ("Blood Washes Blood - 12 Move", lambda: BT.Move(Vec2f(9285, -20889))),
        ("Blood Washes Blood - 13 Bear Spirit Dialog", lambda: BT.MoveAndDialogByModelID(BEAR_SPIRIT_MODEL_ID, 0x84, log=True)),
        ("Blood Washes Blood - 14 Move And Exit Map", lambda: BT.MoveAndExitMap(Vec2f(16045.0, -20642.0), target_map_name="Blood Washes Blood")),
        ("Blood Washes Blood - 15 Aggressive", lambda: _aggressive()),
        *_planner_vanquish_point_steps("Blood Washes Blood - 16 Vanquish Route 04", [(419.0, -3059.0), (-2083.0, 1061.0), (1742.0, 4963.0), (228.0, 10003.0), (3266.0, 12358.0), (3299.0, 13489.0), (365.0, 13684.0)]),
        ("Blood Washes Blood - 17 Pacifist", lambda: _pacifist()),
        ("Blood Washes Blood - 18 Move And Interact", lambda: BT.MoveAndInteract(Vec2f(942.0, 14172.0), log=True)),
        ("Blood Washes Blood - 19 Move And Interact", lambda: BT.MoveAndInteract(Vec2f(942.0, 14172.0), log=True)),
        ("Blood Washes Blood - 20 Select And Equip Reward Skill", lambda: _select_and_equip_reward_skill(8)),
        ("Blood Washes Blood - 21 Aggressive", lambda: _aggressive()),

        # Original route. Barricade approach points are inserted without
        # replacing any original waypoint. Bear-form maintenance stays active
        # through the far-side verification of barricade 04 only.
        *_planner_vanquish_point_steps("Blood Washes Blood - 22 Route To Barricade 01", [(7375, 12256), (8137.44, 12125.30)], during_step_factory=_maintain_blood_washes_blood_bear_form),
        ("Blood Washes Blood - 23 Verify Barricade 01 Passage", lambda: _verify_blood_washes_blood_barricade_passage("Blood Washes Blood - Barricade 01", Vec2f(8514.08, 12101.35))),
        *_planner_vanquish_point_steps("Blood Washes Blood - 24 Route To Barricade 02", [(10984, 11918), (11337.05, 11403.98)], during_step_factory=_maintain_blood_washes_blood_bear_form),
        ("Blood Washes Blood - 25 Verify Barricade 02 Passage", lambda: _verify_blood_washes_blood_barricade_passage("Blood Washes Blood - Barricade 02", Vec2f(11709.23, 10948.48))),
        *_planner_vanquish_point_steps("Blood Washes Blood - 26 Route To Barricade 03", [(13038.97, 9352.95)], during_step_factory=_maintain_blood_washes_blood_bear_form),
        ("Blood Washes Blood - 27 Verify Barricade 03 Passage", lambda: _verify_blood_washes_blood_barricade_passage("Blood Washes Blood - Barricade 03", Vec2f(13175.19, 8990.44))),
        *_planner_vanquish_point_steps("Blood Washes Blood - 28 Route To Barricade 04", [(13502, 8591), (16885, 7971), (15198, 6897), (14874, 3441), (15379.00, 3398.32)], during_step_factory=_maintain_blood_washes_blood_bear_form),
        ("Blood Washes Blood - 29 Verify Barricade 04 Passage", lambda: _verify_blood_washes_blood_barricade_passage("Blood Washes Blood - Barricade 04", Vec2f(15729.87, 3342.82))),

        # Barricade 04 crossed: no more manual bear-form / skill-4 maintenance.
        *_planner_vanquish_point_steps("Blood Washes Blood - 30 Vanquish After Last Barricade", [(16960, 3216), (16734, 5066), (18257, 3930), (17938, 2201), (15908, -280), (11438, 7209)]),
        ("Blood Washes Blood - 31 Wait For Map Load", lambda: BT.WaitForMapLoad(map_name="Gunnar's Hold")),
    ]


def _move_to_egil_if_present() -> BehaviorTree:
    return BT.Selector(
        name="Blood Washes Blood - Move To Egil If Present",
        children=[
            BT.MoveAndDialogByModelID(EGIL_MODEL_ID,0x832007,log=True,),
            BT.Succeeder(name="Egil Absent - Previous Phase Already Completed"),],)


def _steps_TravelToOlafstead() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Travel To Olafstead' + ' - 00 Map Preparation', 'Sifhalla'),
        ('Travel To Olafstead - 01 Prepare Standard Party Xandra', lambda: _prepare_standard_party_xandra()),
        ('Travel To Olafstead - 02 Aggressive', lambda: _aggressive()),
        ('Travel To Olafstead - 03 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(13663.0, 18683.0), target_map_name='Drakkar Lake')),
        *_planner_vanquish_point_steps('Travel To Olafstead - 04 Vanquish Route 01', [(13856.0, 5241.0), (9243.0, -3148.0), (10291.0, -14402.0), (7425.0, -19995.0), (4769.0, -23840.0), (6651.0, -26797.0)]),
        ('Travel To Olafstead - 05 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Varajar Fells')),
        *_planner_vanquish_point_steps('Travel To Olafstead - 06 Vanquish Route 02', [(8582.0, 11620.0), (5853.0, 10407.0), (1972.0, 12954.0), (-696.0, 8467.0), (-90.0, 6162.0), (-2940.0, 3979.0), (-4395.0, 341.0), (-4759.0, -3843.0), (-3712.0, -4655.0), (-2911.0, -3789.0), (-2351.0, -3477.0), (-3126.0, -2708.0), (-3074.0, -55.0), (-1777.0, 1319.0), (-670.0, 1382.0)]),
        ('Travel To Olafstead - 07 Wait For Map Load', lambda: BT.WaitForMapLoad(map_name='Olafstead')),
    ]


def _steps_CompleteShrineOfRavenSpirit() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Shrine Of The Raven Spirit' + ' - 00 Map Preparation', 'Olafstead'),
        ('Shrine Of The Raven Spirit - 01 Prepare Standard Party Xandra', lambda: _prepare_standard_party_xandra()),
        ('Shrine Of The Raven Spirit - 02 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(132.0, -684.0), 8596993)),
        ('Shrine Of The Raven Spirit - 03 Aggressive', lambda: _aggressive()),
        ('Shrine Of The Raven Spirit - 04 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-1392.0, 1205.0), target_map_id=553)),
        *_planner_vanquish_point_steps('Shrine Of The Raven Spirit - 05 Vanquish Route 01', [(-2252.0, 831.0), (-2887.0, -2894.0), (-3211.0, -3843.0), (-3940.0, -3155.0), (-4941.0, 728.0), (-5310.0, 3693.0), (-8984.0, 4861.0), (-12866.0, 5695.0), (-13612.0, 6369.0), (-14355.0, 7040.0), (-14909.0, 7880.0), (-15520.0, 8680.0)]),
        ('Shrine Of The Raven Spirit - 06 Target Olaf And Dialog', lambda: BT.TargetAgentByModelIDAndInteract(OLAF_OLAFSON_MODEL_ID,log=True)),
        ('Shrine Of The Raven Spirit - 07 Target Olaf And Dialog', lambda: BT.SendDialog(0x85, log=True)),
        ('Shrine Of The Raven Spirit - 08 Wait For Clear Area', lambda: BT.WaitForClearEnemiesInArea(-15696.0, 8732.0, radius=Range.Longbow.value, stable_clear_ms=30000, log=True)),
        ('Shrine Of The Raven Spirit - 09 Travel', lambda: BT.Travel(target_map_name='Olafstead')),
        ('Shrine Of The Raven Spirit - 10 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(132.0, -684.0), 0x832E07)),
        ('Shrine Of The Raven Spirit - 11 Wait', lambda: BT.Wait(2000)),
    ]


def _steps_CompleteAGateTooFar() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('A Gate Too Far' + ' - 00 Map Preparation', 'Olafstead'),
        ('A Gate Too Far - 01 Prepare Standard Party Xandra', lambda: _prepare_standard_party_xandra()),
        ('A Gate Too Far - 02 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(132.0, -684.0), 134)),
        ('A Gate Too Far - 03 Wait For Map Change', lambda: BT.WaitForMapToChange(map_id=655, timeout_ms=5000)),
        ('A Gate Too Far - 04 Aggressive', lambda: _aggressive()),
        *_planner_vanquish_point_steps('A Gate Too Far - 05 Vanquish Route 01', [(-8731, -5078), (-8020, -3123), (-6013, -3073), (-4692, -2598), (-4282, -1773), (-4536, 737), (-6193, 1490)], move_tolerance=800),
        *_planner_vanquish_point_steps('A Gate Too Far - 06 Vanquish Route 02', [(-6243, 6484), (-7508, 7340), (-8324, 4864), (-5239, 3585)], log=True),
        ('A Gate Too Far - 07 Wait For Clear Area', lambda: BT.WaitForClearEnemiesInArea(-6243, 6484, radius=Range.Spirit.value, allowed_alive_enemies=0, interact_interval_ms=750, stable_clear_ms=20000, keep_player_near_center=False, center_tolerance=750.0, log=True)),
        *_planner_vanquish_point_steps('A Gate Too Far - 08 Vanquish Route 03', [(-18697.0, 9416.0), (-20211.0, 9897.0)]),
        ('A Gate Too Far - 09 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=656)),
        ('A Gate Too Far - 10 Wait', lambda: BT.Wait(2000)),
        ('A Gate Too Far - 11 Move', lambda: BT.Move(Vec2f(17054.0, 6568.0))),
        ('A Gate Too Far - 12 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('A Gate Too Far - 13 Move', lambda: BT.Move(Vec2f(13357.0, 11594.0))),
        ('A Gate Too Far - 14 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('A Gate Too Far - 15 Move', lambda: BT.Move(Vec2f(11271.0, 17040.0))),
        ('A Gate Too Far - 16 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('A Gate Too Far - 17 Move', lambda: BT.Move(Vec2f(5244.0, 17207.0))),
        ('A Gate Too Far - 18 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('A Gate Too Far - 19 Move', lambda: BT.Move(Vec2f(3249.0, 17858.0))),
        ('A Gate Too Far - 20 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=657)),
        ('A Gate Too Far - 21 Wait', lambda: BT.Wait(2000)),
        ('A Gate Too Far - 22 Move', lambda: BT.Move(Vec2f(6360.0, 16486.0))),
        ('A Gate Too Far - 23 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('A Gate Too Far - 24 Move', lambda: BT.Move(Vec2f(5233.0, 12570.0))),
        ('A Gate Too Far - 25 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('A Gate Too Far - 26 Move', lambda: BT.Move(Vec2f(6210.0, 10139.0))),
        ('A Gate Too Far - 27 Move', lambda: BT.Move(Vec2f(6716.0, 6344.0))),
        ('A Gate Too Far - 28 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('A Gate Too Far - 29 Move', lambda: BT.Move(Vec2f(7702.0, 4015.0))),
        ('A Gate Too Far - 30 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('A Gate Too Far - 31 Move', lambda: BT.Move(Vec2f(7510.0, 2854.0))),
        ('A Gate Too Far - 32 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('A Gate Too Far - 33 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=645)),
        ('A Gate Too Far - 34 Wait', lambda: BT.Wait(2000)),
    ]


# ---------------------------------------------------------------------------
# Ebon Vanguard storyline
# ---------------------------------------------------------------------------


def _steps_AdvanceToLongeyeEdge() -> list[PlannerStep]:
    return [
        _planner_map_prep_step("Advance To Longeye's Edge" + ' - 00 Map Preparation', 644),
        ("Advance To Longeye's Edge - 01 Prepare Standard Party Xandra", lambda: _prepare_standard_party_xandra()),
        ("Advance To Longeye's Edge - 02 Aggressive", lambda: _aggressive()),
        *_planner_vanquish_point_steps("Advance To Longeye's Edge - 03 Vanquish Route 01", [(15886.204101, -6687.815917), (15183.199218, -6381.958984)]),
        ("Advance To Longeye's Edge - 04 Wait For Map Load", lambda: BT.WaitForMapLoad(map_id=548)),
        *_planner_vanquish_point_steps("Advance To Longeye's Edge - 05 Vanquish Route 02", [(14233.820312, -3638.702636), (14944.690429, 1197.740966), (14855.548828, 4450.144531), (17964.738281, 6782.413574), (19127.484375, 9809.458984), (21742.705078, 14057.231445), (19933.86914, 15609.05957), (16294.676757, 16369.736328), (16392.476562, 16768.855468)]),
        ("Advance To Longeye's Edge - 06 Wait For Map Load", lambda: BT.WaitForMapLoad(map_id=482)),
        *_planner_vanquish_point_steps("Advance To Longeye's Edge - 07 Vanquish Route 03", [(-11232.550781, -16722.859375), (-7655.780273, -13250.316406), (-6672.132324, -13080.853515), (-5497.732421, -11904.576171), (-3598.337646, -11162.589843), (-3013.92749, -9264.664062), (-1002.166198, -8064.565429), (3533.099609, -9982.698242), (7472.125976, -10943.370117), (12984.513671, -15341.864257), (17305.523437, -17686.404296), (19048.208984, -18813.695312), (19634.173828, -19118.777343)]),
        ("Advance To Longeye's Edge - 08 Wait For Map Load", lambda: BT.WaitForMapLoad(map_id=650)),
    ]


def _steps_SearchForTheEbonVanguard() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Search For The Ebon Vanguard' + ' - 00 Map Preparation', 650),
        ('Search For The Ebon Vanguard - 01 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-25160.0, 13505.0), 8591361)),
        ('Search For The Ebon Vanguard - 02 Aggressive', lambda: _aggressive()),
        ('Search For The Ebon Vanguard - 03 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-21502.0, 12458.0), target_map_name='Grothmar Wardowns')),
        *_planner_vanquish_point_steps('Search For The Ebon Vanguard - 04 Vanquish Route 01', [(-14000.0, 4297.0), (-9580.0, -2860.0)]),
        ('Search For The Ebon Vanguard - 05 Pacifist', lambda: _pacifist()),
        ('Search For The Ebon Vanguard - 06 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-9580.0, -2860.0), 8591367)),
        ('Search For The Ebon Vanguard - 07 Send Dialog', lambda: BT.MoveAndDialog(Vec2f(-9580.0, -2860.0),0x84)),
        ('Search For The Ebon Vanguard - 08 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=665)),
        ('Search For The Ebon Vanguard - 09 Aggressive', lambda: _aggressive()),
        *_planner_vanquish_point_steps('Search For The Ebon Vanguard - 10 Vanquish Route 02', [(5221.0, -3019.0), (18715.0, -3896.0), (20010.0, -66.0), (17938.0, 2493.0), (19705.0, 3742.0)]),
        ('Search For The Ebon Vanguard - 11 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=649)),
        ('Search For The Ebon Vanguard - 12 Pacifist', lambda: _pacifist()),
        ('Search For The Ebon Vanguard - 13 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(19106.0, 413.0), 8621057)),
        ('Search For The Ebon Vanguard - 14 Aggressive', lambda: _aggressive()),
        *_planner_vanquish_point_steps('Search For The Ebon Vanguard - 15 Vanquish Route 03', [(11484.0, 1898.0), (11388.0, 4143.0), (23634.0, 15333.0)]),
        ('Search For The Ebon Vanguard - 16 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(25604.0, 15412.0), target_map_id=647)),
        *_planner_vanquish_point_steps('Search For The Ebon Vanguard - 17 Vanquish Route 04', [(-13181.0, 3067.0), (-14576.0, 10999.0), (-15193.0, 13347.0)]),
        ('Search For The Ebon Vanguard - 18 Move And Interact With Gadget', lambda: BT.MoveAndInteractWithGadget(Vec2f(-15369.0, 13087.0))),
        ('Search For The Ebon Vanguard - 19 Move', lambda: BT.Move(Vec2f(-17533.0, 14473.0))),
        ('Search For The Ebon Vanguard - 20 Move', lambda: BT.Move(Vec2f(-16740.0, 17124.0))),
        ('Search For The Ebon Vanguard - 21 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('Search For The Ebon Vanguard - 22 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=648)),
        ('Search For The Ebon Vanguard - 23 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-19090.86, 18003.03), 8621063)),
    ]


def _steps_WarbandOfBrothers() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Warband Of Brothers' + ' - 00 Map Preparation', 648),
        ('Warband Of Brothers - 01 Aggressive', lambda: _aggressive()),
        ('Warband Of Brothers - 02 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-19094.0, 17945.0), 132)),
        ('Warband Of Brothers - 03 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=666)),
        ('Warband Of Brothers - 04 Add Loot Whitelist', lambda: _add_model_to_loot_whitelist_with_diag(25413, "Warband 04")),
        *_planner_vanquish_point_steps('Warband Of Brothers - 05 Vanquish Route 01', [(-13404.0, -2958.0), (-7696.0, 4576.0), (-5939.0, 3668.0), (-7823.0, 6395.0), (-5790.0, 7957.0),(-4569.23, 6526.14), (-12068.0, 3611.0),(-4043.76, 6405.57) ]),
        ('Warband Of Brothers - 06 Move And Interact With Gadget', lambda: BT.MoveAndInteractWithGadget(Vec2f(-4043.76, 6405.57), log=True)),
        ('Warband Of Brothers - 07 Wait', lambda: BT.Wait(2000)),
        *_planner_vanquish_point_steps('Warband Of Brothers - 08 Vanquish Route 02', [(3038,8357),(-629,9052),(-4345,6631),(-14125,2723),(-18800,853),(-19452,498)]),
        ('Warband Of Brothers - 09 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=667)),
        ('Warband Of Brothers - 10 Add Loot Whitelist', lambda: _add_model_to_loot_whitelist_with_diag(25413, "Warband 10")),
        *_planner_vanquish_point_steps('Warband Of Brothers - 11 Vanquish Route 03', [(-3290.88, 15187.92), (-1760.07, 12088.74), (-475.83, 11932.78), (-2164.81, 11785.08), (-2061.81, 12930.91), (-2407.16, 14068.22), (-2030.78, 12776.65)]),
        ('Warband Of Brothers - 12 Move And Interact With Gadget', lambda: BT.MoveAndInteractWithGadget(Vec2f(-2254.0, 11176.0), log=True)),
        *_planner_vanquish_point_steps('Warband Of Brothers - 13 Vanquish Route 04', [(-2404.72, 9076.48), (-1563.08, 11763.31), (6634.5, 17973.61), (7429.3, 13458.01), (13162.54, 9219.06), (15923.27, 8823.71), (16782.0, 8642.0)]),
        ('Warband Of Brothers - 14 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=668)),
        ('Warband Of Brothers - 15 Add Loot Whitelist', lambda: _add_model_to_loot_whitelist_with_diag(25413, "Warband 15")),
        *_planner_vanquish_point_steps('Warband Of Brothers - 16 Vanquish Route 05', [(17337.79, -5963.91), (16669.06, -4763.91), (16089.83, -3724.5), (17007.08, -5518.76), (17159.0, -6461.0)]),
        ('Warband Of Brothers - 17 Move And Interact With Gadget', lambda: BT.MoveAndInteractWithGadget(Vec2f(17159.0, -6461.0), log=True)),
        ('Warband Of Brothers - 18 Wait', lambda: BT.Wait(2000)),
        *_planner_vanquish_point_steps('Warband Of Brothers - 19 Vanquish Route 06', [(17808.17, -9149.82), (18827.79, -10402.15), (18742.4, -12129.31), (18194.92, -14704.77), (18334.16, -13903.64), (18704.73, -12773.99), (18284.53, -14134.07)]),
        ('Warband Of Brothers - 20 Move And Interact With Gadget', lambda: BT.MoveAndInteractWithGadget(Vec2f(18147.0, -14974.0), log=True)),
        ('Warband Of Brothers - 21 Wait', lambda: BT.Wait(2000)),
        *_planner_vanquish_point_steps('Warband Of Brothers - 22 Vanquish Route 07', [(14379.01, -15352.7), (10392.54, -14173.8), (9714.57, -12360.55), (8907.67, -11354.53), (8425.21, -9845.09), (8900.77, -10740.29), (9908.98, -12902.71)]),
        ('Warband Of Brothers - 23 Move And Interact With Gadget', lambda: BT.MoveAndInteractWithGadget(Vec2f(10034.0, -14899.0), log=True)),
        ('Warband Of Brothers - 24 Wait', lambda: BT.Wait(2000)),
        *_planner_vanquish_point_steps('Warband Of Brothers - 25 Vanquish Route 08', [(7685.12, -16387.24), (3930.38, -13150.31), (1072.9, -8136.26)]),
        ('Warband Of Brothers - 26 Wait Until Out Of Combat', lambda: BT.ClearEnemiesInArea(Vec2f(-7908.02, -7825.38))),
        ('Warband Of Brothers - 27 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=648)),
    ]


def _steps_WhatMustBeDone() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('What Must Be Done' + ' - 00 Map Preparation', 648),
        ('What Must Be Done - 01 Aggressive', lambda: _aggressive()),
        ('What Must Be Done - 02 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-14185.0, 17040.0), 8621313)),
        ('What Must Be Done - 03 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-15479.0, 13484.0), target_map_id=647)),
        *_planner_vanquish_point_steps('What Must Be Done - 04 Vanquish Route 01', [(-12085.0, 8447.0), (-9360.0, -298.0), (-6856.0, -7620.0), (-7908.02, -7825.38)]),
        ('What Must Be Done - 05 Wait Until Out Of Combat', lambda: BT.ClearEnemiesInArea(Vec2f(-7908.02, -7825.38))),
        ('What Must Be Done - 06 Secure step', lambda: BT.WaitForClearEnemiesInArea(-7908.02,-7825.38, radius=Range.Spirit.value, stable_clear_ms=20000,)),
        ('What Must Be Done - 06 Travel', lambda: BT.Travel(target_map_id=648)),
        ('What Must Be Done - 07 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-14185.0, 17040.0), 132)),
        ('What Must Be Done - 08 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=674)),
        ('What Must Be Done - 09 Move', lambda: BT.Move(Vec2f(-16946.0, 17319.0))),
        ('What Must Be Done - 10 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=648)),
        ('What Must Be Done - 11 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-14185.0, 17040.0), 8621319)),
    ]


def _steps_AssaultOnTheStrongHold() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Assault On The Stronghold' + ' - 00 Map Preparation', 648),
        ('Assault On The Stronghold - 01 Aggressive', lambda: _aggressive()),
        ('Assault On The Stronghold - 02 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-15479.0, 13484.0), target_map_id=647)),
        ('Assault On The Stronghold - 03 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-13849.0, 11217.0), 132)),
        ('Assault On The Stronghold - 04 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=669)),
        *_planner_vanquish_point_steps('Assault On The Stronghold - 05 Vanquish Route 01', [(5203.0, 12344.0), (5843.0, 9145.0)]),
        ('Assault On The Stronghold - 06 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(5843.0, 9145.0), 132)),
        ('Assault On The Stronghold - 07 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(5203.0, 12344.0), 132)),
        ('Assault On The Stronghold - 08 Move', lambda: BT.Move(Vec2f(936.0, 10709.0))),
        ('Assault On The Stronghold - 09 Wait', lambda: BT.Wait(30000)),
        *_planner_vanquish_point_steps('Assault On The Stronghold - 10 Vanquish Route 02', [(-1671.0, 11103.0), (-4202.0, 11045.0), (-6271.0, 12087.0), (-6896.0, 13899.0), (-6393.0, 9770.0), (-6895.0, 8102.0)]),
        ('Assault On The Stronghold - 11 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=649)),
        ('Assault On The Stronghold - 12 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-21069.0, 12353.0), 8591623)),
    ]


# ---------------------------------------------------------------------------
# Asuran storyline
# ---------------------------------------------------------------------------


def _steps_FindingGadd() -> list[PlannerStep]:
    return [
        _planner_map_prep_step('Finding Gadd' + ' - 00 Map Preparation', 645),
        *_planner_vanquish_point_steps('Finding Gadd - Unlock Gadds Camp 1',[(-3638,-4352),(-8976,-2448),(-11746,-6048),(-17007,-6187),(-20768,-9927),(-26166,-13391),],),
        ('Finding Gadd - Unlock Gadds Camp 1', lambda: BT.WaitForMapLoad(map_id=566)),
        *_planner_vanquish_point_steps('Finding Gadd - Unlock Gadds Camp 2', [(18151, 10252), (12551, 4510), (3069, -5735), (-10915, 3126), (-19310, 6501), (-23267, 7881)]),
        ('Finding Gadd - Unlock Gadds Camp 3', lambda: BT.WaitForMapLoad(map_id=639)),
        ('Finding Gadd - Unlock Gadds Camp 4', lambda: BT.MoveAndExitMap(Vec2f(-26186,10582), target_map_id=604)),
        *_planner_vanquish_point_steps('Finding Gadd - Unlock Gadds Camp 5',[(-14003,14202),(-16378,11031),(-17869,7983),(-16067,5680),(-16727,2566),(-17584,-472),(-18026,-11361)]),
        ('Finding Gadd - Unlock Gadds Camp 6', lambda: BT.MoveAndExitMap(Vec2f(-20209,-11995), target_map_id=624)),
        ('Finding Gadd - Unlock Gadds Camp 7', lambda: BT.MoveAndDialog(Vec2f(16363, 15909), 0x833301,)),
        *_planner_vanquish_point_steps('Finding Gadd - Unlock Gadds Camp 8', [(13455.43, 10678.0), (9850.0, 5025.0), (11207.11, 1872.32), (10452.02, 178.5), (10782.86, -3321.0), (8360.94, -6550.0), (10382.85, -12342.0), (10080.3, -13995.0),(10667.0, -16116.0), (10747.49, -17546.0), (11156.0, -17802.0)]),
        ('Finding Gadd - Unlock Gadds Camp 8', lambda: BT.MoveAndExitMap(Vec2f(9240.07, -20260.95), target_map_id=581)),

        *_planner_vanquish_point_steps('Finding Gadd - Unlock Gadds Camp 9', [(-10109,9330),(-1896,13284),(3117,15816),(5902,13035),(11314,13724),(16086,17089),(16926,13169),(15907,11619)]),
        ('Finding Gadd - Unlock Gadds Camp 10', lambda: BT.MoveAndExitMap(Vec2f(14224,11771), target_map_id=638)),

        ('Finding Gadd - 01 Move And Dialog', lambda: BT.MoveAndDialog(Vec2f(-8295.0, -23572.0), 8598276)),
        ('Finding Gadd - 02 Move And Exit', lambda: BT.MoveAndExitMap(Vec2f(-9604,-20187), target_map_id=558)),
        *_planner_vanquish_point_steps('Finding Gadd - 03 Move To Livia', [(-8113,-17955),(-2808,-22064),(6115,-22309),(11604,-23291),]),
        ('Finding Gadd - 04 Move And Dialog', lambda: BT.MoveAndDialogByModelID(5999, 8598276)),
        *_planner_vanquish_point_steps('Finding Gadd - 05 Vanquish Route', [(8017.92, -20124.24), (11184.85, -14188.88),(-5740.47, -13723.29),(2417.11, -25444.55),(12056.22, -24132.56)]),
        ('Finding Gadd - 6 Wait', lambda: BT.Wait(10000)),
        ('Finding Gadd - 7 Dialog', lambda: BT.MoveAndDialogByModelID(6772, 8598276, log=True)),
        ('Finding Gadd - 8 Wait', lambda: BT.Wait(10000)),
        ('Finding Gadd - 9 Dialog ', lambda: BT.MoveAndDialog(Vec2f(11795.0, -24125.0), 8598279))
    ]



def _steps_FindingTheBloodstone() -> list[PlannerStep]:
    return [
        ('Finding The Bloodstone - 01 Dialog', lambda: BT.SendDialog(0x84)),
        ('Finding The Bloodstone - 02 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=661)),
        *_planner_vanquish_point_steps('Finding The Bloodstone - 03 Vanquish Route 02', [(12437.0, 16557.0), (12588.0, 14755.0), (15387.0, 6941.0)]),
        ('Finding The Bloodstone - 04 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('Finding The Bloodstone - 05 Wait', lambda: BT.Wait(10000)),
        *_planner_vanquish_point_steps('Finding The Bloodstone - 06 Vanquish Route 03', [(16165.77, 10441.95), (17149.38, 13434.6), (18529.0, 15977.0), (18170.14, 15771.52)]),
        ('Finding The Bloodstone - 11 Wait', lambda: BT.Wait(30000)),
        ('Finding The Bloodstone - 12 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(19212.0, 16155.0), target_map_id=662)),
        *_planner_vanquish_point_steps('Finding The Bloodstone - 13 Vanquish Route 04', [(-611.51, 5115.83), (3574.7, 3567.62), (4827.1, 1968.97), (11548.76, -2795.9), (14596.0, -7708.0)]),
        ('Finding The Bloodstone - 14 Wait Until Out Of Combat', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120000)),
        ('Finding The Bloodstone - 15 Wait', lambda: BT.Wait(10000)),
        ('Finding The Bloodstone - 16 Move', lambda: BT.Move(Vec2f(16743.0, -10170.0))),
        ('Finding The Bloodstone - 17 Wait', lambda: BT.Wait(30000)),
        ('Finding The Bloodstone - 18 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(18450.0, -10273.0), target_map_id=663)),
        *_planner_vanquish_point_steps('Finding The Bloodstone - 19 Vanquish Route 05', [(-7249.0, -16397.0), (-10466.0, -16166.0), (-15377.0, -16565.0)]),
        ('Finding The Bloodstone - 20 Wait For Map Load', lambda: BT.WaitForMapLoad(map_id=638)),
    ]

def _steps_LabSpace() -> list[PlannerStep]:
    return [
        ('LabSpace - Unlock Rata Sum 0', lambda: BT.Travel(target_map_id=624)),
        ('LabSpace - Take next story quests 1', lambda: BT.MoveAndDialog(Vec2f(16517.00, 16089.00),0x833401)),
        ('LabSpace - Take next story quests 2', lambda: BT.MoveAndDialog(Vec2f(16202.00, 16092.00),0x832C01)),
        ("LabSpace - Prepare Standard Party Full", lambda: _prepare_standard_party_full()),
        ('LabSpace - Unlock Rata Sum 1', lambda: BT.MoveAndExitMap(Vec2f(15360,12015), target_map_id=485)),
        *_planner_vanquish_point_steps('LabSpace - Unlock Rata Sum 2',[(13856,11004),(6067,-95),(-4525,-4292),(-5923,-7830),(-2872,-11614),(-6080,-13317),(-12623,-14600),(-17826,-14505),]),
        ('LabSpace - Unlock Rata Sum 3', lambda: BT.MoveAndExitMap(Vec2f(-20751,-20094), target_map_id=572)),
        *_planner_vanquish_point_steps('LabSpace - Unlock Rata Sum 4',[(16143,13302),(11572,13967),(4551,15089),(-1219,14737),(-6124,15859),(-11606,14416),(-17312,12108),(-20647,9415),(-23916,9351),(-25863,10650),]),
        ('LabSpace - Unlock Rata Sum 5', lambda: BT.MoveAndExitMap(Vec2f(-26394,10028), target_map_id=569)),
        *_planner_vanquish_point_steps('LabSpace - Unlock Rata Sum 6',[ (17610,-6862),(17279,-1470),(17874,7038), (16322,13060)]),
        ('LabSpace - Unlock Rata Sum 7', lambda: BT.MoveAndExitMap(Vec2f(16411,14405), target_map_id=640)),
        ('LabSpace - 1', lambda: BT.MoveAndDialog(Vec2f(16024.0, 18468.0), 8596484)),

            
        ('LabSpace - 2', lambda: BT.MoveAndExitMap(Vec2f(16376,13436), target_map_name="Magus Stones")),
        ('LabSpace - 3', lambda: BT.MoveAndDialog(Vec2f(10228.0, 11488.0), 8596484)),
        *_planner_vanquish_point_steps('LabSpace - 4', [(8329.03, 9954.58), (7258.69, 10987.36), (4812.16, 11197.93), (2778.98, 13297.53), (499.76, 14253.58), (-4305.25, 13044.76), (-11493.07, 16584.55), (-17671.37, 14695.37)]),
        ('LabSpace - 5', lambda: _add_model_to_loot_whitelist_with_diag(24628, "LabSpace 6")),
        ('LabSpace - 6', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)),
        ('LabSpace - 7', lambda:BT.TargetAgentByName(agent_name='Blimm', log=True)),
        ('LabSpace - 8', lambda:BT.InteractTargetAndSendDialog(0x832C07, log=True)),
        ('LabSpace - 9', lambda:BT.InteractTargetAndSendDialog(0x84, log=True)),
        ('LabSpace - 10', lambda:BT.MoveDirect(Vec2f(-18513,16437))),
    ]

FLUCTUATION_MATRIX_MODEL_IDS = {
    22782,
    25413,
}

ELUSIVE_PROTECTION_GOLEM_MODEL_ID = 6880
ELUSIVE_INDESTRUCTIBLE_GOLEM_MODEL_ID = 6878


def _repeat_fluctuation_matrix_until_golem_dead() -> BehaviorTree:
    """Repeat the fluctuation-matrix cycle until the target golem dies.

    Model 6878 is tracked once seen. If it subsequently disappears from the
    live agent array, that is treated as completion as well, but a golem that
    has never been observed is never mistaken for a dead one.
    """
    tracked_golem_agent_id = {"value": 0}

    def _find_golem_agent_id() -> int:
        for raw_agent_id in AgentArray.GetAgentArray() or []:
            agent_id = int(raw_agent_id or 0)
            if agent_id <= 0:
                continue

            try:
                if (
                    int(Agent.GetModelID(agent_id) or 0)
                    == ELUSIVE_INDESTRUCTIBLE_GOLEM_MODEL_ID
                ):
                    tracked_golem_agent_id["value"] = agent_id
                    return agent_id
            except Exception:
                continue

        return 0

    def _is_golem_dead() -> BehaviorTree.NodeState:
        agent_id = _find_golem_agent_id()

        if agent_id > 0:
            return (
                BehaviorTree.NodeState.SUCCESS
                if Agent.IsDead(agent_id)
                else BehaviorTree.NodeState.FAILURE
            )

        # Only consider disappearance as death after this exact golem has
        # previously been observed. This avoids a false success before spawn.
        agent_id = int(tracked_golem_agent_id["value"] or 0)
        if agent_id > 0:
            if Agent.IsDead(agent_id) or not Agent.IsValid(agent_id):
                return BehaviorTree.NodeState.SUCCESS

        return BehaviorTree.NodeState.FAILURE

    def _dead_condition(name: str) -> BehaviorTree:
        return BehaviorTree(
            BehaviorTree.ConditionNode(
                name=name,
                condition_fn=_is_golem_dead,
            )
        )

    attempt = BT.Selector(
        name="Fluctuation Matrix Attempt Or Golem Already Dead",
        children=[
            _dead_condition("Check Indestructible Golem Before Matrix Cycle"),
            BT.Sequence(
                name="Fluctuation Matrix Cycle",
                children=[
                    BT.PickupGroundItemByModelID(
                        tuple(FLUCTUATION_MATRIX_MODEL_IDS),
                        max_distance=10_000.0,
                        timeout_ms=10_000,
                        allow_unassigned=True,
                        interaction_interval_ms=500,
                        log=True,
                    ),
                    BT.Wait(1_000),
                    BT.MoveAndInteractWithGadget(
                        Vec2f(5356.0, -19374.0),
                        log=True,
                    ),
                    _pixel_stack(),
                    BT.Wait(5_000),
                    BT.DropBundle(log=True),
                    _dead_condition("Check Indestructible Golem After Matrix Cycle"),
                ],
            ),
        ],
    )

    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            name="Repeat Fluctuation Matrix Until Golem Dies",
            child=BT.Node(attempt),
            timeout_ms=0,
        )
    )


def _steps_TheElusiveGolemancer() -> list[PlannerStep]:
    return [
        ('TheElusiveGolemancer 0', lambda: BT.MoveAndExitMap(Vec2f(-20318,14531), target_map_id=658)),
        ('TheElusiveGolemancer 1', lambda: BT.MoveAndDialog(Vec2f(-14542.0, 12237.0),129)),
        ('TheElusiveGolemancer 2', lambda: BT.Move(Vec2f(-17204.16, 8545.91))),
        ('TheElusiveGolemancer 3', lambda: BT.MoveAndInteractWithGadget(Vec2f(-17601.0, 8150.0), log=True)),
        ('TheElusiveGolemancer 4', lambda: BT.Wait(20_000)),
        ('TheElusiveGolemancer 5', lambda: BT.Move([Vec2f(-15960.14, 3309.37), Vec2f(-13369.91, -965.44)], avoid_obstacles=False, tolerance=800)),
        ('TheElusiveGolemancer 6', lambda: BT.MoveAndInteractWithGadget(Vec2f(-11737.0, -3710.0), log=True)),
            *_planner_vanquish_point_steps('TheElusiveGolemancer 7', [(-15108.84, -2793.48),(-16518.94, -662.78),]),
            ('TheElusiveGolemancer 8', lambda: BT.WaitUntilOutOfCombat(timeout_ms=120_000)),
            *_planner_vanquish_point_steps('TheElusiveGolemancer 9', [(-16898.24, -612.0), (-17391.0, -528.0), (-17597.36, 15027.91), (18755.0, -19827.0)]),
            ('TheElusiveGolemancer 10', lambda: BT.WaitForMapLoad(map_id=659)),
            ('TheElusiveGolemancer 11', lambda: BT.MoveAndInteractWithGadget(Vec2f(15979.0, -17531.0), log=True)),
            ('TheElusiveGolemancer 12', lambda: _pacifist()),
            ('TheElusiveGolemancer 13', lambda : BT.Move([(17914,-15612),(18112,-13333),(17163,-12397),], flag_heroes_to_waypoint=True)),
            ('TheElusiveGolemancer 14', lambda: BT.MoveAndInteractWithGadget(Vec2f(15551.0, -13705.0), log=True)),
            ('TheElusiveGolemancer 15', lambda: BT.Wait(3_000)),
            ('TheElusiveGolemancer 16', lambda: _aggressive()),
        *_planner_vanquish_point_steps(
            'The Elusive Golemancer - 17 Approach Protection Golem',
            [(15551.0, -13705.0)],
        ),
        (
            'The Elusive Golemancer - 18 Interact With Protection Golem',
            lambda: BT.MoveAndInteractByModelID(
                ELUSIVE_PROTECTION_GOLEM_MODEL_ID,
                log=True,
            ),
        ),
        ('The Elusive Golemancer - 19 Wait For Protection Golem', lambda: BT.Wait(1_000)),
        (
            'The Elusive Golemancer - 20 Follow Protection Golem',
            lambda: BT.FollowModel(
                ELUSIVE_PROTECTION_GOLEM_MODEL_ID,
                follow_range=Range.Nearby.value,
                timeout_ms=120_000,
                repath_interval_ms=500,
                repath_distance=150.0,
                exit_by_area=((5953.36, -9815.89), 800.0),
                log=True,
            ),
        ),
        *_planner_vanquish_point_steps(
            'The Elusive Golemancer - 21 Vanquish Route 04 After Protection Golem',
            [
                (4531.82, -9827.91),
                (3054.24, -9730.68),
                (3485.59, -11380.60),
            ],
        ),            ('TheElusiveGolemancer 22', lambda: BT.MoveAndDialog((-229.0, -12033.0), 0x84)),
            ('TheElusiveGolemancer 23', lambda: BT.Move(Vec2f(3176.96, -17026.31))),
            ('TheElusiveGolemancer 24', lambda: BT.Wait(10_000)),
            ('TheElusiveGolemancer 25', lambda: BT.MoveAndDialog((-2639.00, -15247.00), 0x84)),
            ('TheElusiveGolemancer 26', lambda: BT.Move(Vec2f(3468.83, -16308.18))),
            ('TheElusiveGolemancer 27', lambda: BT.Wait(10_000)),
            ('TheElusiveGolemancer 28', lambda: _pacifist()),
            ('TheElusiveGolemancer 29', lambda: BT.Move(Vec2f(5107.97, -17710.35))),
            ('TheElusiveGolemancer 30', lambda: BT.FlagAllHeroes(5413.07, -19400.44)),
            ('TheElusiveGolemancer 31 Matrix Cycle Until Golem Dead', lambda: _repeat_fluctuation_matrix_until_golem_dead()),
            ('TheElusiveGolemancer 32', lambda: BT.VanquishNode([(6882.36, -20769.41), (6566.0, -21425.0)], clear_area_radius=Range.Earshot.value)),
            ('TheElusiveGolemancer 33', lambda: BT.WaitForMapLoad(map_id=660)),
            ('TheElusiveGolemancer 34', lambda: _aggressive()),
            *_planner_vanquish_point_steps('TheElusiveGolemancer 35', [(-12164.0, 10409.53),(-12584.28, 13570.28),(-15062.15, 16139.62),(-18265.0, 13647.0),]),
            ('TheElusiveGolemancer 36', lambda: BT.WaitForMapLoad(map_id=640)),
        ]

def _unflag_alittlehelp_heroes_local() -> BehaviorTree:
    def _unflag(hero_position: int) -> BehaviorTree:
        def _action() -> BehaviorTree.NodeState:
            try:
                GLOBAL_CACHE.Party.Heroes.UnflagHero(hero_position)

                ConsoleLog(
                    MODULE_NAME,
                    f"A Little Help: hero {hero_position} unflagged.",
                    log=True,
                )

                return BehaviorTree.NodeState.SUCCESS

            except Exception as exc:
                ConsoleLog(
                    MODULE_NAME,
                    f"A Little Help: failed to unflag hero {hero_position}: {exc}",
                    log=True,
                )

                return BehaviorTree.NodeState.FAILURE

        return BehaviorTree(
            BehaviorTree.ActionNode(
                name=f"Unflag A Little Help Hero {hero_position}",
                action_fn=_action,
                aftercast_ms=125,
            )
        )

    return BT.Sequence(
        name="Unflag A Little Help Heroes",
        children=[
            _unflag(1),
            _unflag(2),
            _unflag(3),
            BT.Wait(500),
        ],
    )

ALITTLEHELP_WIPE_RESTART_STEP = 'A Little Help - 09 Dialog'
ALITTLEHELP_WIPE_STEP_PREFIXES = tuple(f'A Little Help - {index:02d} ' for index in range(9, 27))


def _alittlehelp_wipe_restart_service() -> BehaviorTree:
    state = {"armed": False, "last_return_ms": 0.0}

    def _is_alittlehelp_mission_step(step_name: str) -> bool:
        return any(step_name.startswith(prefix) for prefix in ALITTLEHELP_WIPE_STEP_PREFIXES)

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        recovery_active = bool(node.blackboard.get("party_wipe_recovery_active", False))
        recovery_step = str(node.blackboard.get("party_wipe_recovery_step_name", "") or "")
        current_step = str(node.blackboard.get("current_step_name", "") or "")

        if not state["armed"] and recovery_active and (_is_alittlehelp_mission_step(recovery_step) or _is_alittlehelp_mission_step(current_step)):
            state["armed"] = True
            state["last_return_ms"] = 0.0
            ConsoleLog(MODULE_NAME, f"A Little Help wipe detected; restarting from '{ALITTLEHELP_WIPE_RESTART_STEP}'.", log=True)

        if not state["armed"]:
            return BehaviorTree.NodeState.RUNNING

        # Désactive temporairement le recovery standard pour empêcher
        # une reprise de l'étape courante.
        node.blackboard["party_wipe_recovery_suppressed"] = True
        node.blackboard["restart_step_name_request"] = ""

        # Une fois revenu à Rata Sum, reprendre au dialogue qui relance la mission.
        if Map.IsMapReady() and Map.IsOutpost() and int(Map.GetMapID() or 0) == 640 and GLOBAL_CACHE.Party.IsPartyLoaded():
            node.blackboard["party_wipe_recovery_suppressed"] = False
            node.blackboard["restart_step_name_request"] = ALITTLEHELP_WIPE_RESTART_STEP
            state["armed"] = False
            state["last_return_ms"] = 0.0
            ConsoleLog(MODULE_NAME, f"A Little Help recovery ready; restarting from '{ALITTLEHELP_WIPE_RESTART_STEP}'.", log=True)
            return BehaviorTree.NodeState.RUNNING

        # Même si GW prévoit une résurrection au sanctuaire, on force ici
        # le retour à l'avant-poste afin de relancer correctement la mission.
        now = time.monotonic() * 1000.0
        if Map.IsMapReady() and now - state["last_return_ms"] >= 1000.0:
            GLOBAL_CACHE.Party.ReturnToOutpost()
            state["last_return_ms"] = now

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="A Little Help Wipe Restart Service",
            action_fn=_tick,
            aftercast_ms=0,
        )
    )

def _steps_ALittleHelp() -> list[PlannerStep]:
    return [
        ('A Little Help - 00 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(20320, 16861), target_map_id=501)),
        *_planner_vanquish_point_steps('A Little Help - 01 Vanquish Route 01', [(-22469, -5887), (-12978, -8490), (2552, -9452), (9029, -9692), (14574, -9613)]),
        ('A Little Help - 02 Dialog', lambda: BT.MoveAndDialog(Vec2f(17611.00, -9341.00), 8598532)),
        *_planner_vanquish_point_steps('A Little Help - 03 Vanquish Route 02', [(8016, -10470), (1025, -8638), (-4327, -10132), (-8425, -12543)]),
        ('A Little Help - 04 Move And Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-8618, -14375), target_map_id=572)),
        *_planner_vanquish_point_steps('A Little Help - 05 Vanquish Route 03', [(-5413, 15875), (-15672, 11827), (-10182, -115), (-16273, -5484), (-20039, -10133), (-21923, -9612), (-24115, -10567)]),
        ('A Little Help - 06 Wait Out Of Combat', lambda: BT.WaitUntilOutOfCombat()),
        ('A Little Help - 07 Dialog Model ID 6789', lambda: BT.MoveAndDialogByModelID(6789, 8598532)),
        ('A Little Help - 08 Travel To Rata Sum', lambda: BT.Travel(target_map_name="Rata Sum")),
        ('A Little Help - 09 Dialog', lambda: BT.MoveAndDialog(Vec2f(16051.00, 15183.00), 8598535)),
        ('A Little Help - 10 Send Dialog 132', lambda: BT.SendDialog(132)),
        ('A Little Help - 11 Wait For Map 664', lambda: BT.WaitForMapLoad(map_id=664)),
        ('A Little Help - 12 Move To Fight Position', lambda: BT.Move(Vec2f(-16715.00, 8931.00))),
        ('A Little Help - 13 Flag Hero 1', lambda: BT.FlagHero(1, -17880.37, 10046.01)),
        ('A Little Help - 14 Flag Hero 2', lambda: BT.FlagHero(2, -17880.37, 10046.01)),
        ('A Little Help - 15 Flag Hero 3', lambda: BT.FlagHero(3, -17880.37, 10046.01)),
        ('A Little Help - 16 Move To Combat Area', lambda: BT.Move(Vec2f(-15365,8605),)),
        ('A Little Help - 17 Wait 5 Seconds', lambda: BT.Wait(5000)),
        ('A Little Help - 18 Wait For Area Clear', lambda: BT.WaitForClearEnemiesInArea(-15365,8605, stable_clear_ms=80_000, radius=Range.Longbow.value, log=True, keep_player_near_center=True)),
        ('A Little Help - 19 Unflag Heroes', lambda: _unflag_alittlehelp_heroes_local()),
        ('A Little Help - 19 Move to secure position', lambda:BT.Move((-16246,9117))),
        ('A Little Help - 20 Target Sokka', lambda: BT.TargetAgentByName(agent_name='Sokka', log=True)),
        ('A Little Help - 21 Interact With Sokka And Send Dialog', lambda: BT.InteractTargetAndSendDialog(0x84)),
        ('A Little Help - 21 Interact With Sokka And Send Dialog', lambda: BT.InteractTargetAndSendDialog(0x84)),
        ('A Little Help - 22 Drop Bundle', lambda: BT.DropBundle(log=True)),
        ('A Little Help - 23 Wait 10 Seconds', lambda: BT.Wait(10000)),
        ('A Little Help - 24 Interact With Sokka And Send Dialog', lambda: BT.InteractTargetAndSendDialog(0x84)),
        ('A Little Help - 24 Interact With Sokka And Send Dialog', lambda: BT.InteractTargetAndSendDialog(0x84)),
        ('A Little Help - 25 Drop Bundle', lambda: BT.DropBundle(log=True)),
        *_planner_vanquish_point_steps('A Little Help - 26 Vanquish Route 04', [(-16464,9550),(-17826,11011),(-17046,14895),(-12464,13766),(-4723,13262),(-6188, 15259)]),
        ('A Little Help - 27 Wait For Map 640', lambda: BT.WaitForMapToChange(map_id=640)),
        ('A Little Help - 28 Final Dialog', lambda: BT.MoveAndDialog(Vec2f(16051.00, 15183.00), 8622855)),
    ]

def _steps_Jalis() -> list[PlannerStep]:
        return [
('Jalis 0 - Travel Eyes of The North', lambda: BT.Travel(642)),
('Jalis 1 - Enter Hall of Monuments ', lambda: BT.MoveAndExitMap(Vec2f(1522.0, 464.0), target_map_id=499)),
('Jalis 2 - Navigate to Target Location', lambda: BT.Move([(-1797,-3176),(-8148,-3770),])),
('Jalis 3 - Exit Current Map', lambda: BT.MoveAndExitMap(Vec2f(-10224,-3758), target_map_id=625)),
*_planner_vanquish_point_steps('Jalis 4 - Vanquish Points',[(19160,18738),(1408,19625),(-2193,16151),(-4747,17842),]),
('Jalis 5 - Interact for vision', lambda: BT.MoveAndDialog(Vec2f(-4874.00, 17584.00), 0x838907)),
('Jalis 6 - Travel to Eyes of The North', lambda: BT.Travel(642)),
('Jalis 7 - Exit Map', lambda: BT.MoveAndExitMap(Vec2f(-4575,5752), target_map_id=646)),
('Jalis 8 - Interact with Jalis', lambda: BT.MoveAndDialog(Vec2f(-6662.00, 6584.00), 0x63F)),
('Jalis 9 - Travel Eyes of The North', lambda: BT.Travel(642)),
('Jalis 10 - Prepare Touch Team', lambda: _prepare_touch_team()),
('Jalis 10 - Exit Map', lambda: BT.MoveAndExitMap(Vec2f(1522.0, 464.0), target_map_id=499)),
('Jalis 11 - Navigate to Target Location', lambda: BT.Move([(-1797,-3176),(-8148,-3770),])),
('Jalis 12 - Enter to Battledepths', lambda: BT.MoveAndExitMap(Vec2f(-10224,-3758), target_map_id=625)),
*_planner_vanquish_point_steps('Jalis 13 - Vanquish Points',[(19160,18738),(1408,19625),(-2193,16151),(-4747,17842),]),
('Jalis 14 - Interact with Jalis', lambda: BT.MoveAndDialog(Vec2f(-4874.00, 17584.00), 0x833101)),
*_planner_vanquish_point_steps('Jalis 15 - Vanquish Points', [(1115,11797),(6542,12098),(7916,10192),(6055,7277),]),
('Jalis 16 - Enter to HeartofTheShiverspeak', lambda: BT.MoveAndExitMap(Vec2f(5873,8216), target_map_id=607)),
        ]

HEART_BUDGER_MODEL_ID = 6230
HEART_CYNDR_MODEL_ID = 6965
HEART_CYNDR_XANDRA_HERO_POSITION = 5
HEART_CYNDR_BLACKBOARD_KEY = "heart_cyndr_agent_id"
HEART_CYNDR_XANDRA_FLAG = Vec2f(-6814.0, -14431.0)


def _heart_player_near(
    pos: Vec2f,
    *,
    tolerance: float = 250.0,
    name: str = "Check Heart Position",
) -> BehaviorTree:
    def _check() -> BehaviorTree.NodeState:
        try:
            x, y = Player.GetXY()
        except Exception:
            return BehaviorTree.NodeState.FAILURE

        dx = float(x) - float(pos.x)
        dy = float(y) - float(pos.y)
        return (
            BehaviorTree.NodeState.SUCCESS
            if dx * dx + dy * dy <= float(tolerance) ** 2
            else BehaviorTree.NodeState.FAILURE
        )

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name=name,
            condition_fn=_check,
        )
    )


def _heart_wait_bundle_state(
    *,
    holding: bool,
    timeout_ms: int = 5_000,
    name: str,
) -> BehaviorTree:
    def _check() -> BehaviorTree.NodeState:
        player_id = int(Player.GetAgentID() or 0)
        if player_id <= 0:
            return BehaviorTree.NodeState.FAILURE

        has_bundle = bool(Agent.IsHoldingItem(player_id))
        return (
            BehaviorTree.NodeState.SUCCESS
            if has_bundle == bool(holding)
            else BehaviorTree.NodeState.FAILURE
        )

    return BehaviorTree(
        BehaviorTree.WaitUntilSuccessNode(
            name=name,
            condition_fn=_check,
            throttle_interval_ms=150,
            timeout_ms=max(0, int(timeout_ms)),
        )
    )


def _heart_destroy_wall(
    *,
    name: str,
    wall_pos: Vec2f,
    verify_pos: Vec2f,
) -> BehaviorTree:
    """Destroy a cracked wall and prove the player can physically cross it."""

    def _cross_check(label: str) -> BehaviorTree:
        return BT.Sequence(
            name=label,
            children=[
                BT.Move(
                    verify_pos,
                    pause_on_combat=False,
                    tolerance=175.0,
                    ignore_destination_obstacles=True,
                    log=True,
                ),
                _heart_player_near(
                    verify_pos,
                    tolerance=275.0,
                    name=f"{label} - Verify Player Crossed Wall",
                ),
            ],
        )

    def _breach_attempt(attempt: int) -> BehaviorTree:
        return BT.Sequence(
            name=f"{name} - Breach Attempt {attempt}",
            children=[
                _pacifist(),
                BT.MoveAndInteractByModelID(
                    HEART_BUDGER_MODEL_ID,
                    log=True,
                ),
                _heart_wait_bundle_state(
                    holding=True,
                    timeout_ms=5_000,
                    name=f"{name} - Attempt {attempt} Wait For Powder Keg",
                ),
                BT.Move(
                    wall_pos,
                    pause_on_combat=False,
                    tolerance=50.0,
                    log=True,
                ),
                _heart_wait_bundle_state(
                    holding=True,
                    timeout_ms=750,
                    name=f"{name} - Attempt {attempt} Verify Keg Still Carried",
                ),
                BT.DropBundle(log=True),
                _heart_wait_bundle_state(
                    holding=False,
                    timeout_ms=2_000,
                    name=f"{name} - Attempt {attempt} Verify Keg Dropped",
                ),
                BT.Wait(3_500),
                _cross_check(f"{name} - Attempt {attempt} Cross Wall"),
                _aggressive(),
            ],
        )

    return BT.Selector(
        name=name,
        children=[
            BT.Sequence(
                name=f"{name} - Wall Already Open",
                children=[
                    _cross_check(f"{name} - Probe Existing Passage"),
                    _aggressive(),
                ],
            ),
            _breach_attempt(1),
            _breach_attempt(2),
            _breach_attempt(3),
            BT.Sequence(
                name=f"{name} - Breach Failed",
                children=[
                    _aggressive(),
                    BT.LogMessage(
                        message=f"{name}: wall could not be crossed after 3 powder-keg attempts.",
                        module_name=MODULE_NAME,
                    ),
                    BT.Failer(name=f"{name} - Stop After Failed Wall Breach"),
                ],
            ),
        ],
    )


def _heart_find_agent_by_model_id(model_id: int) -> int:
    try:
        for agent_id in AgentArray.GetAgentArray():
            agent_id = int(agent_id or 0)
            if agent_id > 0 and int(Agent.GetModelID(agent_id) or 0) == int(model_id):
                return agent_id
    except Exception:
        pass
    return 0


def _heart_wait_for_cyndr(timeout_ms: int = 15_000) -> BehaviorTree:
    def _find(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        agent_id = _heart_find_agent_by_model_id(HEART_CYNDR_MODEL_ID)
        if agent_id <= 0:
            return BehaviorTree.NodeState.FAILURE

        node.blackboard[HEART_CYNDR_BLACKBOARD_KEY] = agent_id
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.WaitUntilSuccessNode(
            name="Heart - Wait For Cyndr",
            condition_fn=_find,
            throttle_interval_ms=250,
            timeout_ms=max(0, int(timeout_ms)),
        )
    )


def _heart_cyndr_is_dead() -> BehaviorTree:
    def _check(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        agent_id = int(node.blackboard.get(HEART_CYNDR_BLACKBOARD_KEY, 0) or 0)
        if agent_id <= 0:
            agent_id = _heart_find_agent_by_model_id(HEART_CYNDR_MODEL_ID)
            if agent_id > 0:
                node.blackboard[HEART_CYNDR_BLACKBOARD_KEY] = agent_id

        if agent_id <= 0:
            return BehaviorTree.NodeState.FAILURE

        living = Agent.GetLivingAgentByID(agent_id)
        dead = bool(
            Agent.IsDead(agent_id)
            or (living is not None and float(Agent.GetHealth(agent_id) or 0.0) <= 0.001)
        )
        return (
            BehaviorTree.NodeState.SUCCESS
            if dead
            else BehaviorTree.NodeState.FAILURE
        )

    return BehaviorTree(
        BehaviorTree.ConditionNode(
            name="Heart - Check Cyndr Dead",
            condition_fn=_check,
        )
    )


HEART_CYNDR_XANDRA_SKILL_SEQUENCE = (2, 1, 3, 4, 5, 6)


def _heart_set_xandra_manual_skill_ai(enabled: bool) -> BehaviorTree:
    """Enable/disable HeroAI for Xandra slots 1-6 while we force the setup order."""

    def _apply() -> BehaviorTree.NodeState:
        hero_position = HEART_CYNDR_XANDRA_HERO_POSITION
        hero_agent_id = int(
            GLOBAL_CACHE.Party.Heroes.GetHeroAgentIDByPartyPosition(hero_position) or 0
        )
        if hero_agent_id <= 0:
            ConsoleLog(
                MODULE_NAME,
                "Heart: Xandra is unavailable while configuring her Cyndr skill AI.",
                log=True,
            )
            return BehaviorTree.NodeState.SUCCESS

        try:
            for slot in range(1, 7):
                GLOBAL_CACHE.Party.Heroes.SetSkillAIEnabled(
                    hero_agent_id,
                    slot,
                    bool(enabled),
                )
        except Exception as exc:
            ConsoleLog(
                MODULE_NAME,
                f"Heart: failed to configure Xandra skill AI: {exc}",
                log=True,
            )
            return BehaviorTree.NodeState.FAILURE

        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=(
                "Heart - Enable Xandra Cyndr Skill AI"
                if enabled
                else "Heart - Disable Xandra Cyndr Skill AI"
            ),
            action_fn=_apply,
            aftercast_ms=100,
        )
    )


def _heart_xandra_skill_ready(slot: int) -> bool:
    try:
        skillbar = GLOBAL_CACHE.SkillBar.GetHeroSkillbar(
            HEART_CYNDR_XANDRA_HERO_POSITION
        )
        if slot < 1 or slot > len(skillbar):
            return False

        skill_data = skillbar[slot - 1]
        skill_id = int(getattr(getattr(skill_data, "id", None), "id", 0) or 0)
        recharge = getattr(skill_data, "get_recharge", 0)
        if callable(recharge):
            recharge = recharge()
        try:
            recharge = float(recharge or 0.0)
        except (TypeError, ValueError):
            recharge = 0.0

        return bool(skill_id > 0 and recharge <= 0.0)
    except Exception:
        return False


def _heart_force_xandra_skill(slot: int) -> BehaviorTree:
    """Cast one ready Xandra slot manually; unavailable/recharging slots are skipped."""

    def _cast() -> BehaviorTree.NodeState:
        hero_position = HEART_CYNDR_XANDRA_HERO_POSITION
        hero_agent_id = int(
            GLOBAL_CACHE.Party.Heroes.GetHeroAgentIDByPartyPosition(hero_position) or 0
        )
        if hero_agent_id <= 0 or Agent.IsDead(hero_agent_id):
            ConsoleLog(
                MODULE_NAME,
                f"Heart: Xandra unavailable for forced slot {slot}; continuing.",
                log=True,
            )
            return BehaviorTree.NodeState.SUCCESS

        if not _heart_xandra_skill_ready(slot):
            ConsoleLog(
                MODULE_NAME,
                f"Heart: Xandra slot {slot} is not ready; keeping ordered setup moving.",
                log=True,
            )
            return BehaviorTree.NodeState.SUCCESS

        try:
            GLOBAL_CACHE.SkillBar.HeroUseSkill(
                0,
                int(slot),
                int(hero_position),
            )
            ConsoleLog(
                MODULE_NAME,
                f"Heart: forced Xandra slot {slot} for Cyndr setup.",
                log=True,
            )
        except Exception as exc:
            ConsoleLog(
                MODULE_NAME,
                f"Heart: failed to force Xandra slot {slot}: {exc}",
                log=True,
            )
            # Do not leave Xandra's manual setup half-configured because one
            # dispatch failed; continue so the sequence can re-enable HeroAI.
            return BehaviorTree.NodeState.SUCCESS

        return BehaviorTree.NodeState.SUCCESS

    def _finished_casting() -> BehaviorTree.NodeState:
        hero_agent_id = int(
            GLOBAL_CACHE.Party.Heroes.GetHeroAgentIDByPartyPosition(
                HEART_CYNDR_XANDRA_HERO_POSITION
            ) or 0
        )
        if hero_agent_id <= 0 or Agent.IsDead(hero_agent_id):
            return BehaviorTree.NodeState.SUCCESS
        try:
            return (
                BehaviorTree.NodeState.RUNNING
                if Agent.IsCasting(hero_agent_id)
                else BehaviorTree.NodeState.SUCCESS
            )
        except Exception:
            return BehaviorTree.NodeState.SUCCESS

    return BT.Sequence(
        name=f"Heart - Xandra Forced Slot {slot}",
        children=[
            BehaviorTree(
                BehaviorTree.ActionNode(
                    name=f"Heart - Cast Xandra Slot {slot}",
                    action_fn=_cast,
                    aftercast_ms=0,
                )
            ),
            # Give the client a moment to publish the hero casting state before
            # checking it, otherwise two HeroUseSkill commands can be queued too fast.
            BT.Wait(150),
            BT.Selector(
                name=f"Heart - Wait Xandra Slot {slot} Or Continue",
                children=[
                    BehaviorTree(
                        BehaviorTree.WaitUntilNode(
                            name=f"Heart - Wait Xandra Slot {slot} Cast End",
                            condition_fn=_finished_casting,
                            throttle_interval_ms=100,
                            timeout_ms=4_500,
                        )
                    ),
                    BT.Succeeder(
                        name=f"Heart - Xandra Slot {slot} Cast Wait Timeout Continue"
                    ),
                ],
            ),
            BT.Wait(100),
        ],
    )


def _heart_xandra_cyndr_skill_sequence() -> BehaviorTree:
    """Force Xandra's requested Cyndr setup order: 2 -> 1 -> 3 -> 4 -> 5 -> 6."""
    return BT.Sequence(
        name="Heart - Xandra Cyndr Skill Sequence 2-1-3-4-5-6",
        children=[
            _heart_set_xandra_manual_skill_ai(False),
            *[
                _heart_force_xandra_skill(slot)
                for slot in HEART_CYNDR_XANDRA_SKILL_SEQUENCE
            ],
            _heart_set_xandra_manual_skill_ai(True),
        ],
    )

def _heart_unflag_cyndr_dps_heroes() -> BehaviorTree:
    """Unflag every Touch-team hero except Xandra."""

    def _apply() -> BehaviorTree.NodeState:
        hero_count = int(GLOBAL_CACHE.Party.GetHeroCount() or 0)
        failed = False

        for hero_position in range(1, hero_count + 1):
            if hero_position == HEART_CYNDR_XANDRA_HERO_POSITION:
                continue
            try:
                GLOBAL_CACHE.Party.Heroes.UnflagHero(hero_position)
            except Exception as exc:
                failed = True
                ConsoleLog(
                    MODULE_NAME,
                    f"Heart: failed to unflag hero {hero_position}: {exc}",
                    log=True,
                )

        return (
            BehaviorTree.NodeState.FAILURE
            if failed
            else BehaviorTree.NodeState.SUCCESS
        )

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Heart - Unflag All Touch Heroes Except Xandra",
            action_fn=_apply,
            aftercast_ms=250,
        )
    )


def _heart_wait_until_cyndr_dead(timeout_ms: int = 10 * 60_000) -> BehaviorTree:
    """Wait for the Touch team to kill Cyndr without using powder kegs."""
    return BehaviorTree(
        BehaviorTree.RepeaterUntilSuccessNode(
            name="Heart - Wait Until Cyndr Is Dead",
            child=BT.Node(_heart_cyndr_is_dead()),
            timeout_ms=max(0, int(timeout_ms)),
        )
    )


def _heart_cyndr_encounter() -> BehaviorTree:
    """Defeat Cyndr with the validated Touch team.

    Boss powder-keg mechanics are intentionally not used here. Xandra stays
    fixed in the room and performs the requested 2 -> 1 -> 3 -> 4 -> 5 -> 6
    sequence once. Every other hero is explicitly unflagged so HeroAI can
    freely engage Cyndr and can also reach the player for resurrection.
    """
    return BT.Sequence(
        name="Heart - Defeat Cyndr With Touch Team",
        children=[
            _aggressive(),
            _heart_unflag_cyndr_dps_heroes(),
            BT.FlagHero(
                HEART_CYNDR_XANDRA_HERO_POSITION,
                HEART_CYNDR_XANDRA_FLAG.x,
                HEART_CYNDR_XANDRA_FLAG.y,
            ),
            BT.Wait(400),
            BT.TargetAgentByModelIDAndInteract(HEART_CYNDR_MODEL_ID, log=True),
            _heart_xandra_cyndr_skill_sequence(),
            _heart_wait_until_cyndr_dead(),
            BT.Wait(10000)
        ],
    )


def _steps_HeartofTheShiverspeak() -> list[PlannerStep]:
    return [
        *_planner_vanquish_point_steps('HeartofTheShiverspeak - 01', [(16656,10285),(14959,6248),(11603,7924),(10251.43, 7158.36),(11184,6397),(11129,2735),(7633,832),], clear_area_radius=Range.Nearby.value),
        ('HeartofTheShiverspeak - 02 Move And Dialog', lambda: BT.MoveAndDialogByModelID(HEART_BUDGER_MODEL_ID, 0x833104)),
        *_planner_vanquish_point_steps('HeartofTheShiverspeak - 03 Kill', [(10241,-1296),(11520,-2522),]),
        (
            'HeartofTheShiverspeak - 04 Destroy Wall 1',
            lambda: _heart_destroy_wall(
                name='Heart Wall 1',
                wall_pos=Vec2f(12216, -3053),
                verify_pos=Vec2f(12777, -3380),
            ),
        ),
        *_planner_vanquish_point_steps('HeartofTheShiverspeak - 05 Vanquish Route 01', [(12216,-3053),(18707,-6839),]),
        ('HeartofTheShiverspeak - 06 Exit Level 1', lambda: BT.MoveAndExitMap(Vec2f(19368,-6902), target_map_id=608)),
        *_planner_vanquish_point_steps('HeartofTheShiverspeak - 07 Vanquish Route 02', [(-16570,-10792),(-17411,-7548),(-17428,-4996),]),
        (
            'HeartofTheShiverspeak - 08 Destroy Wall 2',
            lambda: _heart_destroy_wall(
                name='Heart Wall 2',
                wall_pos=Vec2f(-17080,-3726),
                verify_pos=Vec2f(-17107,-3076),
            ),
        ),
        *_planner_vanquish_point_steps('HeartofTheShiverspeak - 09 Vanquish Route 03', [(-17329,2321),(-18794,3595),]),
        ('HeartofTheShiverspeak - 10 Wait For Level 3', lambda: BT.WaitForMapToChange(map_id=609)),
        (
            'HeartofTheShiverspeak - 11 Destroy Wall 3',
            lambda: _heart_destroy_wall(
                name='Heart Wall 3',
                wall_pos=Vec2f(1264.75, -17241.79),
                verify_pos=Vec2f(686,-16616),
            ),
        ),
        *_planner_vanquish_point_steps('HeartofTheShiverspeak - 12 Vanquish Route 04', [(828,-16794),(-722,-14645),(-1331,-13489),(-4122,-10775),]),
        (
            'HeartofTheShiverspeak - 13 Destroy Wall 4',
            lambda: _heart_destroy_wall(
                name='Heart Wall 4',
                wall_pos=Vec2f(-5170,-11489),
                verify_pos=Vec2f(-5499,-11675),
            ),
        ),
        ('HeartofTheShiverspeak - 14 Move to Cyndr Room', lambda: BT.Move([(-5499,-11675),(-7515.01, -17050.18)], pause_on_combat=False)),
        ('HeartofTheShiverspeak - 15 Wait For Cyndr', lambda: _heart_wait_for_cyndr()),
        ('HeartofTheShiverspeak - 16 Defeat Cyndr', lambda: _heart_cyndr_encounter()),
        ('HeartofTheShiverspeak - 17 Exit Level 3', lambda: BT.MoveAndInteractWithGadget(Vec2f(-5739.00, -17127.00))),
        ('HeartofTheShiverspeak - 18 Move To Exit', lambda: BT.MoveAndInteractWithGadget(Vec2f(-6592.00, -16928.00),)),
        ('HeartofTheShiverspeak - 19 Wait For Map Change', lambda: BT.WaitForMapToChange(map_id=625, timeout_ms=190_000)),
        ('HeartofTheShiverspeak - 20 Talk to Jalis', lambda: BT.MoveAndDialog(Vec2f(-4874.00, 17584.00),0x833107)),
        ('HeartofTheShiverspeak - 21 Talk to Jalis for next step', lambda: BT.SendDialog(0x84)),
    ]

def _steps_DestructionsDepth() -> list[PlannerStep]:
    return [
        ('DestructionsDepth - 01 Wait for map change', lambda: BT.WaitForMapToChange(map_id=670)),
        ('DestructionsDepth - 02 Move and interact with golem 1', lambda: BT.MoveAndDialog(Vec2f(14875.00, -577.00),0x88)),
        ('DestructionsDepth - 10 Change Golem Type', lambda: BT.MoveAndDialog(Vec2f(14875.00, -577.00),0x85)),
        ('DestructionsDepth - 03 Wait mana', lambda: BT.Wait(5000)),
        ('DestructionsDepth - 03 Move and interact with golem 2', lambda: BT.MoveAndDialog(Vec2f(14615.07, -518.46),0x88)),
        ('DestructionsDepth - 03 Wait mana', lambda: BT.Wait(5000)),
        ('DestructionsDepth - 04 Move and interact with golem 3', lambda: BT.MoveAndDialog(Vec2f(14206.00, -373.00),0x88)),
        *_planner_vanquish_point_steps('DestructionsDepth - 05 Vanquish Route', [(13838,-1004),(9735,-795),(6821,-1560),(7233,-4327),(4614,-3797),]),
        ('DestructionsDepth - 06 Wait open door', lambda: BT.Wait(15000)),
        *_planner_vanquish_point_steps('DestructionsDepth - 07 Vanquish Route', [(1602,-4001),(531,-5912),(-2602,-7593),(-3055,-9348),(-2090,-14031),(-5409,-16717),(-8116,-16917),]),
        ('DestructionsDepth - 08 Move and exit', lambda: BT.MoveAndExitMap(Vec2f(-7550,-18381),target_map_id=671)),
        ('DestructionsDepth - 09 Move and interact with golem 1', lambda: BT.MoveAndDialog(Vec2f(1863.00, 2429.00),0x88)),
        ('DestructionsDepth - 10 Change Golem Type', lambda: BT.MoveAndDialog(Vec2f(1863.00, 2429.00),0x85)),
        ('DestructionsDepth - 10 Wait mana', lambda: BT.Wait(5000)),
        ('DestructionsDepth - 11 Move and interact with golem 2', lambda: BT.MoveAndDialog(Vec2f(2115.00, 2518.00),0x88)),
        ('DestructionsDepth - 12 Wait mana', lambda: BT.Wait(5000)),
        ('DestructionsDepth - 13 Move and interact with golem 3', lambda: BT.MoveAndDialog(Vec2f(2333.00, 2556.00),0x88)),
        *_planner_vanquish_point_steps('DestructionsDepth - 14 Vanquish Route', [(5039,2032),(5939,152),(7203,-3396),(5053,-7207),]),
        ('DestructionsDepth - 15 Clear Area', lambda: BT.ClearEnemiesInArea(Vec2f(5053,-7207),radius=Range.Compass.value,)),
        ('DestructionsDepth - 16 Wait for Clear Enemies', lambda: BT.WaitForClearEnemiesInArea(5053,-7207, radius=Range.Compass.value, stable_clear_ms=60_000,)),
        *_planner_vanquish_point_steps('DestructionsDepth - 17 Vanquish Route', [(7318,-3547),(12260,-3868),(14750,-5535),(15423,-17214),]),
        ('DestructionsDepth - 18 Move and exit', lambda: BT.MoveAndExitMap(Vec2f(15474,-18742),target_map_id=672)),
        ('DestructionsDepth - 19 Move and interact with golem 1', lambda: BT.MoveAndDialog(Vec2f(-40.00, 3742.00),0x88)),
        ('DestructionsDepth - 20 Change Golem Type', lambda: BT.MoveAndDialog(Vec2f(-40.00, 3742.00),0x85)),
        ('DestructionsDepth - 20 Wait mana', lambda: BT.Wait(5000)),
        ('DestructionsDepth - 21 Move and interact with golem 2', lambda: BT.MoveAndDialog(Vec2f(331.00, 3745.00),0x88)),
        ('DestructionsDepth - 22 Change Golem Type', lambda: BT.MoveAndDialog(Vec2f(331.00, 3745.00),0x85)),
        ('DestructionsDepth - 22 Wait mana', lambda: BT.Wait(5000)),
        ('DestructionsDepth - 23 Move and interact with golem 3', lambda: BT.MoveAndDialog(Vec2f(-369.00, 3750.00),0x88)),
        *_planner_vanquish_point_steps('DestructionsDepth - 24 Vanquish Route', [(-1781,3491),(-1056,4167),(1150,4138),(2034,3173),(934,1862),(1386,656),(-664,370),]),
        ('DestructionsDepth - 25 Wait for Map Change', lambda: BT.WaitForMapToChange(map_id=652)),
        


    ]

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
            ], log=log, clear_area_radius=Range.Earshot.value),
            BT.MoveAndDialog(Vec2f(-1131.99, 818.35), 0x82D401, log=log),
            BT.MoveAndExitMap(Vec2f(-2439.0, 1732.0), target_map_id=290, log=log),
            BT.VanquishNode([
                (-2995.68, 2077.20),
                (-6938.10, 4286.61),
                (-6064.40, 5300.26),
                (-2396.20, 5260.67),
                (-5031.77, 6001.52),
                (-5899.57, 7240.19),
            ], log=log, clear_area_radius=Range.Earshot.value),
            BT.TargetAgentByModelIDAndSendDialog(4914, 0x87, log=log),
            BT.WaitForMapLoad(map_id=400),
            _aggressive(),
            BT.VanquishNode([
                (-1712.16, -700.23),
                (-907.97, -2862.29),
                (742.42, -4167.73),
                (1352.94, -3694.75)], clear_area_radius=Range.Earshot.value),
            BT.Wait(5000),
            BT.VanquishNode([    
                (1786, -1448)], clear_area_radius=Range.Earshot.value),
            BT.Wait(5000),
            BT.VanquishNode([
                (2651.48, -3750.63),
                (3355.63, -2151.82),
                (4347, -1682),], clear_area_radius=Range.Earshot.value),
            BT.Wait(5000),
            BT.VanquishNode([    
                (279, 811)
            ], pause_on_combat=True, log=log, clear_area_radius=Range.Earshot.value),
            BT.WaitForMapLoad(map_id=290, timeout_ms=60000),
            BT.TargetAgentByModelIDAndSendDialog(4914, 0x84, log=log),
            BT.SendDialog(0x84),
            BT.WaitForMapLoad(map_id=543),
            BT.Wait(2_000),
            BT.TargetAgentByModelIDAndSendDialog(4829, 0x82D407, log=log),
        ],
    )


def ToConsulateDocksForOlias(log: bool = True) -> BehaviorTree:
    return BT.Sequence(
        name="Unlock Consulate Docks",
        children=[
            BT.Travel(target_map_id=449, log=log),
            BT.Move(Vec2f(-8075.89, 14592.47), log=log),
            BT.Move(Vec2f(-6743.29, 16663.21), log=log),
            BT.Move(Vec2f(-5271.00, 16740.00), log=log),
            BT.WaitForMapLoad(map_id=429),
            BT.MoveAndDialog(Vec2f(-4631.86, 16711.79), 0x85, log=log),
            BT.WaitForMapLoad(map_id=493),
            BT.MoveAndDialog((-2367.00, 16796.00),0x830E01)
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
                ], clear_area_radius=Range.Earshot.value),

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
                            clear_area_radius=Range.Earshot.value,
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
            _prepare_standard_party2(),
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
            ], pause_on_combat=True, log=log, clear_area_radius=Range.Earshot.value),
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
        *_steps_InitializeBot(),
        *_steps_UnlockEyeOfTheNorthPool(),
        *_steps_ObtainStoryBook(),
        ('Ensure MOX Unlocked', EnsureMOXUnlocked),
        ('Ensure Olias Unlocked', EnsureOliasUnlocked),
        *_steps_TravelToGunnarsHold(),
        ('Save Pre-Xandra Player Build', SavePreXandraPlayerBuild),
        *_steps_Unlock_Xandra(),
        ('Optional Xandra Tournament', CompleteOptionalXandraTournament),
        *_steps_PrepareXandraTournament(),
        ('Fight Sequence', Fight_Sequence),
        ('Restore Pre-Xandra Player Build', RestorePreXandraPlayerBuild),
        *_steps_TravelToSifhalla(),
        *_steps_CompleteTrackingTheNornbear(),
        *_steps_CompleteCurseOfTheNornbear(),
        *_steps_BloodWashesBlood(),
        *_steps_TravelToOlafstead(),
        *_steps_CompleteShrineOfRavenSpirit(),
        *_steps_CompleteAGateTooFar(),
        *_steps_AdvanceToLongeyeEdge(),
        *_steps_SearchForTheEbonVanguard(),
        *_steps_WarbandOfBrothers(),
        *_steps_WhatMustBeDone(),
        *_steps_AssaultOnTheStrongHold(),
        *_steps_FindingGadd(),
        *_steps_FindingTheBloodstone(),
        *_steps_LabSpace(),
        *_steps_TheElusiveGolemancer(),
        *_steps_ALittleHelp(),
        *_steps_Jalis(),
        *_steps_HeartofTheShiverspeak(),
        *_steps_DestructionsDepth()
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
                heroai_state_logging=False,
                enable_party_wipe_recovery=True,
            ),
        )

        botting_tree.AddServiceTree("A Little Help Wipe Restart", _alittlehelp_wipe_restart_service)

    return botting_tree



def main() -> None:
    global initialized

    if not initialized:
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()
    _tick_eotn_loot_diagnostics()
    attach_botting_tree_support(tree)
    tree.UI.draw_window(
        icon_path=ICON_PATH,
        main_child_dimensions=(550, 350),
    )


if __name__ == "__main__":
    main()
