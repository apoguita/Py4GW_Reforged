import importlib
import math
import os
import time
import traceback
import types
from typing import Any, Generator, Tuple

import PyImGui
from Py4GWCoreLib import *
from Py4GWCoreLib.AgentArray import AgentArray
from Py4GWCoreLib.UIManager import UIManager
from Py4GWCoreLib.routines_src import reliable_interaction as _reliable_interaction
from Widgets.Data.dungeons import darkrime_delves_data as _darkrime_data


# Widget Manager hot-reloads this file without evicting imported modules. Refresh
# both dependencies before binding their classes/constants so shared API changes
# cannot leave this widget holding stale dataclass constructors.
_reliable_interaction = importlib.reload(_reliable_interaction)
ApproachSpec = _reliable_interaction.ApproachSpec
DialogSpec = _reliable_interaction.DialogSpec
InteractionProfile = _reliable_interaction.InteractionProfile
InteractionSpec = _reliable_interaction.InteractionSpec
PostconditionKind = _reliable_interaction.PostconditionKind
PostconditionSpec = _reliable_interaction.PostconditionSpec
Py4GWInteractionRuntime = _reliable_interaction.Py4GWInteractionRuntime
ReliableInteractionController = _reliable_interaction.ReliableInteractionController
RetryPolicy = _reliable_interaction.RetryPolicy
TargetKind = _reliable_interaction.TargetKind
TargetSpec = _reliable_interaction.TargetSpec
run_coroutine_adapter = _reliable_interaction.run_coroutine_adapter

_darkrime_data = importlib.reload(_darkrime_data)
APPROACH_SOURCE_ROUTE_ID = _darkrime_data.APPROACH_SOURCE_ROUTE_ID
BJORA_ENTRY_TO_BLESSING = _darkrime_data.BJORA_ENTRY_TO_BLESSING
LONGEYES_OUTPOST_POINTS = _darkrime_data.LONGEYES_OUTPOST_POINTS
LEVEL_1_LEVER_SAFE_WAIT = _darkrime_data.LEVEL_1_LEVER_SAFE_WAIT
LEVEL_1_LEVER_HERO_SAFE_FLAG = _darkrime_data.LEVEL_1_LEVER_HERO_SAFE_FLAG
LEVEL_1_HERO_REGROUP = _darkrime_data.LEVEL_1_HERO_REGROUP
LEVEL_1_HAVOK_KEY_KILL = _darkrime_data.LEVEL_1_HAVOK_KEY_KILL
LEVEL_1_OTHER_BRIDGE = _darkrime_data.LEVEL_1_OTHER_BRIDGE
LEVEL_1_OTHER_BRIDGE_BLESSING_CAPTURE_ID = _darkrime_data.LEVEL_1_OTHER_BRIDGE_BLESSING_CAPTURE_ID
LEVEL_1_OTHER_BRIDGE_BLESSING_INDEX = _darkrime_data.LEVEL_1_OTHER_BRIDGE_BLESSING_INDEX
LEVEL_1_OTHER_BRIDGE_SOURCE_ROUTE_ID = _darkrime_data.LEVEL_1_OTHER_BRIDGE_SOURCE_ROUTE_ID
LEVEL_1_KEY_FLAG = _darkrime_data.LEVEL_1_KEY_FLAG
LEVEL_1_KEY_LOCATION = _darkrime_data.LEVEL_1_KEY_LOCATION
LEVEL_2_BOSS_LOCK_TO_DOOR = _darkrime_data.LEVEL_2_BOSS_LOCK_TO_DOOR
LEVEL_2_BOSS_LOCK_TO_DOOR_SOURCE_ROUTE_ID = _darkrime_data.LEVEL_2_BOSS_LOCK_TO_DOOR_SOURCE_ROUTE_ID
LEVEL_2_PENDULUM_TRAP_ROOM = _darkrime_data.LEVEL_2_PENDULUM_TRAP_ROOM
LEVEL_2_MAP_ROOM = _darkrime_data.LEVEL_2_MAP_ROOM
LEVEL_2_SAFE_ROUTE = _darkrime_data.LEVEL_2_SAFE_ROUTE
LEVEL_2_SAFE_ROUTE_SOURCE_ROUTE_ID = _darkrime_data.LEVEL_2_SAFE_ROUTE_SOURCE_ROUTE_ID
SNOWBALL_DODGE_2 = _darkrime_data.SNOWBALL_DODGE_2
SNOWBALL_DODGE_SOURCE_ROUTE_ID = _darkrime_data.SNOWBALL_DODGE_SOURCE_ROUTE_ID
MARKERS = _darkrime_data.MARKERS
ROUTE_POINTS = _darkrime_data.ROUTE_POINTS
SOURCE_ROUTE_ID = _darkrime_data.SOURCE_ROUTE_ID
CAPTURE_JOIN_TO_EINARR_POINTS = _darkrime_data.CAPTURE_JOIN_TO_EINARR_POINTS
CAPTURE_JOIN_XY = _darkrime_data.CAPTURE_JOIN_XY
YAVB_BLESSING_TO_CAPTURE_JOIN = _darkrime_data.YAVB_BLESSING_TO_CAPTURE_JOIN


BOT_NAME = "Darkrime Delves"
MODULE_NAME = BOT_NAME
MODULE_ICON = "Textures\\Module_Icons\\Survivor Title - Kath Hammers.png"
MODULE_TAGS = ["Dungeon", "EOTN", "Deldrimor", "Route"]

BJORA_MARCHES = 482
LONGEYES_LEDGE = 650
DARKRIME_LEVEL_1 = 635
DARKRIME_LEVEL_2 = 636
DARKRIME_LEVEL_3 = 637
COLD_VENGEANCE_QUEST_ID = 810
DUNGEON_KEY_MODEL_ID = 25410
BOSS_KEY_MODEL_ID = 25416
ALT_BRIDGE_BLESSING_POINT = 1160
DWARVEN_RAIDER_EFFECT_IDS = (2445, 2446, 2447, 2448, 2549, 2565, 2566, 2567, 2568)
EOTN_BLESSING_EFFECT_IDS = (
    *DWARVEN_RAIDER_EFFECT_IDS,
    2457,
    2458,
    2459,
    2460,
    2550,
    2578,
    2434,
    2435,
    2436,
    2481,
    2548,
    2552,
    2469,
    2470,
    2471,
    2472,
    2551,
    2591,
    2592,
    2593,
    2594,
)

LEVEL_1_EXIT_XY = (-18979.55, 11133.68)
# Deliberately beyond the Level 2 portal. The previous target was within the
# movement arrival tolerance while still on the Level 2 side of the boundary.
LEVEL_2_EXIT_XY = (-20250.0, -953.0)

INTERACTIONS = {
    1007: {
        "profile": InteractionProfile.VISIBLE_CHOICE,
        "target_kind": TargetKind.NPC,
        "xy": (17838.55, -18278.86),
        "model_id": 6425,
        "postcondition": "any_blessing",
        "visible_button": 1,
        "allow_preexisting_postcondition": False,
        "required": True,
        "capture_id": "NPC-20260806-221039-593",
    },
    1: {
        "profile": InteractionProfile.VISIBLE_CHOICE,
        "target_kind": TargetKind.NPC,
        # Einarr is the stationary NPC at this fixed location before the quest.
        # Model 4512 was a party follower near the player, not Einarr.
        "xy": (-15864.09, 13716.09),
        "target_xy": (-15915.0, 13669.0),
        "model_id": 6428,
        "search_radius": 250.0,
        "approach_tolerance": 35.0,
        "target_tolerance": 120.0,
        "max_attempts": 10,
        "retry_delay_ms": 1_500,
        # Poll the quest log after clicking Accept. This is a timeout ceiling,
        # not a fixed delay: the route advances on the first successful poll.
        "verify_timeout_ms": 15_000,
        "postcondition": "quest_active",
        "visible_button": 1,
        # Accept-dialog encoding is 0x800001 | (quest_id << 8).
        # Cold Vengeance is quest 810 (0x32A), so this must be 0x832A01.
        "raw_dialog": 0x832A01,
        "required": True,
        "capture_id": "NPC-20260807-115226-136",
    },
    29: {
        "profile": InteractionProfile.VISIBLE_CHOICE, "target_kind": TargetKind.NPC,
        "xy": (15168.7, 16664.88), "model_id": 5916, "postcondition": "blessing",
        "visible_button": 1,
        "allow_preexisting_postcondition": False,
        "required": True, "capture_id": "NPC-20260806-211806-048",
    },
    81: {
        "profile": InteractionProfile.GADGET, "target_kind": TargetKind.GADGET,
        "xy": (8056.44, 2469.58), "postcondition": "bundle_present", "required": True,
        "capture_id": "NPC-20260806-212134-059",
    },
    92: {
        "profile": InteractionProfile.AUTOMATIC_TRIGGER, "target_kind": TargetKind.NPC,
        "xy": (5977.53, -1512.51), "model_id": 5916, "postcondition": "beacon_response",
        "required": False, "capture_id": "NPC-20260806-212214-809",
    },
    127: {
        "profile": InteractionProfile.GADGET, "target_kind": TargetKind.GADGET,
        "xy": (-369.9, 1412.45), "postcondition": "bundle_present", "required": True,
        "capture_id": "NPC-20260806-212532-703",
    },
    136: {
        "profile": InteractionProfile.GADGET, "target_kind": TargetKind.GADGET,
        "xy": (1515.58, 3768.29), "postcondition": "interaction_sent", "required": True,
        "capture_id": "NPC-20260806-212700-265",
    },
    141: {
        "profile": InteractionProfile.AUTOMATIC_TRIGGER, "target_kind": TargetKind.NPC,
        "xy": (798.87, 5764.11), "model_id": 5916, "postcondition": "beacon_response",
        "required": False, "capture_id": "NPC-20260806-212734-393",
    },
    192: {
        "profile": InteractionProfile.AUTOMATIC_TRIGGER, "target_kind": TargetKind.NPC,
        "xy": (-14953.15, 4260.19), "model_id": 5916, "postcondition": "beacon_response",
        "required": False, "capture_id": "NPC-20260806-213114-043",
    },
    207: {
        "profile": InteractionProfile.GADGET, "target_kind": TargetKind.GADGET,
        "xy": (-12254.41, -1617.48), "postcondition": "lever_activation_settled", "required": True,
        "allow_preexisting_postcondition": False,
        "verify_timeout_ms": 5_000,
        "max_attempts": 3,
        "capture_id": "NPC-20260806-213152-710",
    },
    258: {
        "profile": InteractionProfile.GADGET, "target_kind": TargetKind.GADGET,
        "xy": (-15524.7, 2530.11), "postcondition": "interaction_sent", "required": True,
        "capture_id": "NPC-20260806-213508-669",
    },
    284: {
        "profile": InteractionProfile.VISIBLE_CHOICE, "target_kind": TargetKind.NPC,
        "xy": (19873.92, 14303.41), "model_id": 5916, "postcondition": "blessing",
        "visible_button": 1,
        "allow_preexisting_postcondition": False,
        "required": True, "capture_id": "NPC-20260806-213636-987",
    },
    354: {
        "profile": InteractionProfile.AUTOMATIC_TRIGGER, "target_kind": TargetKind.NPC,
        "xy": (8163.97, 3351.43), "model_id": 5916, "postcondition": "beacon_response",
        "required": False, "capture_id": "NPC-20260806-214155-827",
    },
    419: {
        "profile": InteractionProfile.AUTOMATIC_TRIGGER, "target_kind": TargetKind.NPC,
        "xy": (-15264.56, -4812.22), "model_id": 5916, "postcondition": "beacon_response",
        "required": False, "capture_id": "NPC-20260806-214534-939",
    },
    456: {
        "profile": InteractionProfile.AUTOMATIC_TRIGGER, "target_kind": TargetKind.NPC,
        "xy": (-13037.7, -14565.53), "model_id": 5916, "postcondition": "beacon_response",
        "required": False, "capture_id": "NPC-20260806-214724-274",
    },
    519: {
        "profile": InteractionProfile.GADGET, "target_kind": TargetKind.GADGET,
        "xy": (-19243.37, -960.09), "postcondition": "interaction_sent", "required": True,
        "capture_id": "NPC-20260806-215049-287",
    },
    524: {
        "profile": InteractionProfile.VISIBLE_CHOICE, "target_kind": TargetKind.NPC,
        "xy": (-16402.23, 17848.92), "model_id": 5916, "postcondition": "blessing",
        "approach_tolerance": 35.0,
        "visible_button": 1,
        "allow_preexisting_postcondition": False,
        "required": True, "capture_id": "NPC-20260806-231723-937",
    },
    577: {
        "profile": InteractionProfile.AUTOMATIC_TRIGGER, "target_kind": TargetKind.NPC,
        "xy": (-16192.74, 5469.67), "model_id": 5916, "postcondition": "beacon_response",
        "required": False, "capture_id": "NPC-20260806-215614-535",
    },
    593: {
        "profile": InteractionProfile.GADGET, "target_kind": TargetKind.GADGET,
        "xy": (-16804.47, 11386.86), "postcondition": "chest_opened", "required": True,
        "capture_id": "NPC-20260806-215838-607",
    },
    ALT_BRIDGE_BLESSING_POINT: {
        "profile": InteractionProfile.AUTOMATIC_TRIGGER,
        "target_kind": TargetKind.NPC,
        "xy": (-9178.22, 14943.58),
        "model_id": 5916,
        "postcondition": "beacon_response",
        "required": False,
        "capture_id": LEVEL_1_OTHER_BRIDGE_BLESSING_CAPTURE_ID,
    },
}

# These mechanics do not expose a reliable activation bit through the current
# gadget API. Their following route segment remains the end-to-end gate, but we
# log them explicitly instead of presenting command dispatch as strong proof.
DEFERRED_GATE_VERIFICATION_POINTS = (136, 207, 258, 519)

DROP_BUNDLE_POINTS = {94: "Drop first Powder Keg", 130: "Drop second Powder Keg"}
KEY_PICKUP_POINTS = {
    227: "Pick up the Level 1 dungeon key",
    465: "Defeat Grelk Icelash and pick up the Level 2 dungeon key",
}
KEY_PICKUP_MAPS = {
    227: DARKRIME_LEVEL_1,
    465: DARKRIME_LEVEL_2,
}
KEY_PICKUP_MODEL_IDS = {
    227: DUNGEON_KEY_MODEL_ID,
    465: BOSS_KEY_MODEL_ID,
}
KEY_PICKUP_ITEM_NAMES = {
    227: "Dungeon Key",
    465: "Boss Key",
}

PHASES = [
    ("Full run: Longeyes Ledge to Darkrime", "DD:APPROACH"),
    ("Approach: Bjora entry / get Longeyes blessing", "DD:APPROACH_BJORA"),
    ("Approach: after Longeyes blessing", "DD:APPROACH_YAVB"),
    ("Approach: at Einarr / accept Cold Vengeance", "DD:APPROACH_EINARR"),
    ("Approach: after accepting Cold Vengeance", "DD:APPROACH_POST_QUEST"),
    ("Level 1: entrance / first keg", "DD:L1_ENTRANCE"),
    ("Level 1: after snowball dodge", "DD:L1_AFTER_SNOWBALL"),
    ("Level 1: Havok-kin / second keg", "DD:L1_HAVOK_KIN"),
    ("Level 1: bridges", "DD:L1_BRIDGES"),
    ("Level 1: lever / key / exit", "DD:L1_EXIT"),
    ("Level 1: after lever / go to dungeon key", "DD:L1_AFTER_LEVER"),
    ("Level 1: at dungeon key / pick it up", "DD:L1_KEY"),
    ("Level 1: after key / return to dungeon lock", "DD:L1_AFTER_KEY"),
    ("Level 1: after dungeon lock / go to exit", "DD:L1_AFTER_LOCK"),
    ("Level 2: entrance", "DD:L2_ENTRANCE"),
    ("Level 2: after entrance Beacon / safe route", "DD:L2_AFTER_ENTRANCE_BEACON"),
    ("Level 2: after safe route / upper loop", "DD:L2_AFTER_SAFE_ROUTE"),
    ("Level 2: approach Pendulum Trap Room", "DD:L2_UPPER_HALLS"),
    ("Level 2: Pendulum Trap Room", "DD:L2_PENDULUM_TRAP_ROOM"),
    ("Level 2: descent to second Beacon/Map", "DD:L2_SECOND_BEACON_APPROACH"),
    ("Level 2: Map Room / Second Beacon", "DD:L2_MAP_ROOM"),
    ("Level 2: middle", "DD:L2_MIDDLE"),
    ("Level 2: The Great Rift Hall", "DD:L2_LOWER_CENTRAL"),
    ("Level 2: Chromatic Drake Corner / Third Beacon", "DD:L2_WESTERN_HALLS"),
    ("Level 2: approach Grelk", "DD:L2_GRELK_APPROACH"),
    ("Level 2: midway to Grelk", "DD:L2_GRELK_MIDWAY"),
    ("Level 2: after final Beacon / Grelk corridor", "DD:L2_AFTER_FINAL_BEACON"),
    ("Level 2: at Grelk / collect key", "DD:L2_GRELK_KEY"),
    ("Level 2: after Grelk / return with key", "DD:L2_AFTER_GRELK"),
    ("Level 2: return midpoint", "DD:L2_RETURN_MIDPOINT"),
    ("Level 2: return north corridor", "DD:L2_RETURN_NORTH"),
    ("Level 2: boss lock / exit", "DD:L2_EXIT"),
    ("Level 3: entrance", "DD:L3_ENTRANCE"),
    ("Level 3: Havok Soulwail / chest", "DD:L3_BOSS"),
]

class _RuntimeLog:
    """Send route diagnostics through the project's existing console."""

    def write(self, message: str) -> None:
        ConsoleLog(MODULE_NAME, str(message), Console.MessageType.Info)


SESSION_LOG = _RuntimeLog()
_phase_index = 0
_interaction_events = []
_registered_interaction_points: list[int] = []
_initialization_error = ""

bot = Botting(
    bot_name=BOT_NAME,
    upkeep_hero_ai_active=True,
    upkeep_auto_loot_active=True,
    upkeep_morale_active=True,
)
# Match the working Shards of Orr pattern: make both dungeon key models
# explicit auto-loot priorities. Once collected, these become dungeon UI/
# instance state rather than ordinary bag inventory.
bot.Items.AddModelToLootWhitelist(DUNGEON_KEY_MODEL_ID)
bot.Items.AddModelToLootWhitelist(BOSS_KEY_MODEL_ID)


def _anchor() -> Generator[Any, Any, None]:
    yield


def _idle_forever() -> Generator[Any, Any, None]:
    while bot.config.fsm_running:
        yield from Routines.Yield.wait(250)


def _runtime_snapshot() -> str:
    return f"map={Map.GetMapID()} player_xy={Player.GetXY()} step={bot.config.FSM.get_current_step_name()!r}"


def _hold_failure(message: str) -> Generator[Any, Any, bool]:
    SESSION_LOG.write(f"blocked reason={message!r} {_runtime_snapshot()}")
    bot.config.state_description = message
    while bot.config.fsm_running:
        yield from Routines.Yield.wait(250)
    return False


def _require_map(map_id: int, label: str) -> Generator[Any, Any, bool]:
    if Map.GetMapID() == map_id:
        return True
    yield from _hold_failure(f"{label} requires map {map_id}; current map is {Map.GetMapID()}")
    return False


def _configure_combat(bot: Botting) -> None:
    bot.Properties.Enable("pause_on_danger")
    bot.Properties.Disable("halt_on_death")
    bot.Properties.Set("movement_timeout", value=-1)
    bot.Properties.Enable("hero_ai")
    bot.Templates.Aggressive()


def _gadget_signature(agent_id: int) -> tuple:
    if not agent_id or not Agent.IsValid(agent_id) or not Agent.IsGadget(agent_id):
        return ()
    try:
        return (
            int(Agent.GetGadgetID(agent_id)),
            int(Agent.GetGadgetAgentExtraType(agent_id)),
            int(Agent.GetGadgetAgenth00C4(agent_id)),
            int(Agent.GetGadgetAgenth00C8(agent_id)),
            tuple(Agent.GetGadgetAgenth00D4(agent_id) or ()),
        )
    except Exception:
        return (int(agent_id),)


class _DarkrimeInteractionRuntime(Py4GWInteractionRuntime):
    def __init__(self, point_index: int, verification_key: str, expected_xy: Tuple[float, float]):
        self.point_index = int(point_index)
        self.hero_ai_status = bot.config.upkeep.hero_ai.is_active()
        self.hero_ai_pause_status = bool(
            hasattr(bot.config.upkeep, "hero_ai_paused")
            and bot.config.upkeep.hero_ai_paused.is_active()
        )
        super().__init__(
            pause_automation=self._pause_hero_ai,
            restore_automation=self._restore_hero_ai,
            verify=lambda _postcondition: False,
            diagnostic_sink=self._record_event,
        )
        self.verification_key = verification_key
        self.expected_xy = expected_xy
        self.interacted = False
        self.interaction_sent_at = 0.0
        self.lever_activation_settle_logged = False
        self.dialog_choice_clicked = False
        self.dialog_choice_clicked_at = 0.0
        self.quest_log_snapshot: tuple[int, ...] | None = None
        self.quest_accept_fallback_logged = False
        self.interacted_agent_id = 0
        self.before_gadget_signature: tuple = ()
        self.before_items = set(int(agent_id) for agent_id in (AgentArray.GetItemArray() or []))

    def _record_event(self, event: dict[str, Any]) -> None:
        _record_interaction_event({"point_index": self.point_index, **dict(event)})

    def _pause_hero_ai(self) -> None:
        if hasattr(bot.config.upkeep, "hero_ai_paused"):
            bot.config.upkeep.hero_ai_paused.set_now("active", True)
        else:
            bot.config.upkeep.hero_ai.set_now("active", False)

    def _restore_hero_ai(self) -> None:
        if hasattr(bot.config.upkeep, "hero_ai_paused"):
            bot.config.upkeep.hero_ai_paused.set_now("active", self.hero_ai_pause_status)
        bot.config.upkeep.hero_ai.set_now("active", self.hero_ai_status)

    def interact(self, agent_id: int) -> None:
        self.interacted_agent_id = int(agent_id)
        self.before_gadget_signature = _gadget_signature(agent_id)
        super().interact(agent_id)
        self.interacted = True
        self.interaction_sent_at = time.monotonic()

    def click_dialog_button(self, choice: int) -> bool:
        clicked = bool(super().click_dialog_button(choice))
        if clicked:
            self.dialog_choice_clicked = True
            self.dialog_choice_clicked_at = time.monotonic()
        return clicked

    def verify(self, _postcondition: PostconditionSpec) -> bool:
        if self.verification_key == "quest_accept_clicked":
            return self.dialog_choice_clicked
        if self.verification_key == "quest_active":
            quest_ids = tuple(sorted(int(value) for value in (Quest.GetQuestLogIds() or [])))
            if quest_ids != self.quest_log_snapshot:
                self.quest_log_snapshot = quest_ids
                SESSION_LOG.write(
                    f"einarr_quest_log_check quest_id={COLD_VENGEANCE_QUEST_ID} "
                    f"quest_log_ids={quest_ids}"
                )
            if COLD_VENGEANCE_QUEST_ID in quest_ids:
                return True

            # On this dungeon, the quest-log binding can remain stale even though
            # the visible Accept choice succeeded. A confirmed click followed by
            # the dialog closing is the game's immediate acceptance handoff; use
            # it as a narrow fallback so the controller cannot pull the player
            # back to Einarr for ten false-negative retries.
            accept_handoff_complete = (
                self.dialog_choice_clicked
                and self.dialog_choice_clicked_at > 0.0
                and time.monotonic() - self.dialog_choice_clicked_at >= 0.75
                and not UIManager.IsNPCDialogVisible()
            )
            if accept_handoff_complete and not self.quest_accept_fallback_logged:
                self.quest_accept_fallback_logged = True
                SESSION_LOG.write(
                    "einarr_quest_accept_verified source=visible_accept_click_and_dialog_closed "
                    f"quest_log_ids={quest_ids}"
                )
            return accept_handoff_complete
        if self.verification_key == "blessing":
            player_id = Player.GetAgentID()
            return any(
                Effects.EffectExists(player_id, effect_id) or Effects.BuffExists(player_id, effect_id)
                for effect_id in DWARVEN_RAIDER_EFFECT_IDS
            )
        if self.verification_key == "any_blessing":
            player_id = Player.GetAgentID()
            return any(
                Effects.EffectExists(player_id, effect_id) or Effects.BuffExists(player_id, effect_id)
                for effect_id in EOTN_BLESSING_EFFECT_IDS
            )
        if self.verification_key == "bundle_present":
            return Agent.IsHoldingItem(Player.GetAgentID())
        if self.verification_key == "beacon_response":
            # A blessing that was already active does not prove this Beacon
            # responded. Require an actual dialog response after interaction.
            return self.interacted and UIManager.IsNPCDialogVisible()
        if self.verification_key == "gadget_changed":
            return self.interacted and (
                not Agent.IsValid(self.interacted_agent_id)
                or _gadget_signature(self.interacted_agent_id) != self.before_gadget_signature
            )
        if self.verification_key == "lever_activation_settled":
            gadget_changed = self.interacted and (
                not Agent.IsValid(self.interacted_agent_id)
                or _gadget_signature(self.interacted_agent_id) != self.before_gadget_signature
            )
            # Interacting with this lever is asynchronous. Previously the generic
            # interaction_sent check completed after ~0.1s and the retreat move
            # canceled the lever use. Hold position for two seconds after the
            # command (or proceed sooner if the gadget exposes a state change).
            activation_settled = (
                self.interacted
                and self.interaction_sent_at > 0.0
                and time.monotonic() - self.interaction_sent_at >= 2.0
                and Utils.Distance(Player.GetXY(), self.expected_xy) <= 150.0
            )
            if (gadget_changed or activation_settled) and not self.lever_activation_settle_logged:
                self.lever_activation_settle_logged = True
                SESSION_LOG.write(
                    "level_1_lever_activation_verified "
                    f"source={'gadget_changed' if gadget_changed else 'interaction_settled'} "
                    f"elapsed_ms={int((time.monotonic() - self.interaction_sent_at) * 1000)} "
                    f"{_runtime_snapshot()}"
                )
            return gadget_changed or activation_settled
        if self.verification_key == "interaction_sent":
            return self.interacted
        if self.verification_key == "chest_opened":
            current_items = set(int(agent_id) for agent_id in (AgentArray.GetItemArray() or []))
            return self.interacted and (
                bool(current_items - self.before_items)
                or not Agent.IsValid(self.interacted_agent_id)
                or _gadget_signature(self.interacted_agent_id) != self.before_gadget_signature
            )
        return False


def _record_interaction_event(event: dict[str, Any]) -> None:
    _interaction_events.append(dict(event))
    if len(_interaction_events) > 100:
        del _interaction_events[:-100]
    SESSION_LOG.write(f"reliable_interaction {event}")


def _run_interaction_impl(point_index: int) -> Generator[Any, Any, bool]:
    policy = INTERACTIONS[point_index]
    marker = MARKERS[point_index]
    label = marker["name"]
    xy = tuple(policy["xy"])
    target_xy = tuple(policy.get("target_xy", xy))
    runtime = _DarkrimeInteractionRuntime(point_index, str(policy["postcondition"]), xy)
    raw_dialog = int(policy.get("raw_dialog", 0))
    spec = InteractionSpec(
        name=label,
        profile=policy["profile"],
        target=TargetSpec(
            kind=policy["target_kind"],
            model_id=int(policy.get("model_id", 0)),
            name_contains=str(policy.get("name_contains", "")),
            expected_xy=target_xy,
            search_radius=float(policy.get("search_radius", 500.0)),
        ),
        approach=ApproachSpec(
            player_approach_xy=xy,
            tolerance=float(policy.get("approach_tolerance", 90.0)),
            target_tolerance=(
                float(policy["target_tolerance"])
                if policy.get("target_tolerance") is not None
                else None
            ),
            timeout_ms=15_000,
        ),
        dialog=DialogSpec(
            visible_button=policy.get("visible_button"),
            raw_context_ids=(raw_dialog,) if raw_dialog else (),
            response_timeout_ms=4_000,
            allow_raw_without_visible_dialog=False,
            close_dialog_after_success=bool(policy.get("close_dialog_after_success", False)),
        ),
        postcondition=PostconditionSpec(
            kind=PostconditionKind.CUSTOM,
            value=str(policy["postcondition"]),
            description=f"Darkrime verification: {policy['postcondition']}",
        ),
        retry=RetryPolicy(
            max_attempts=int(policy.get("max_attempts", 3)),
            poll_ms=100,
            verify_timeout_ms=int(policy.get("verify_timeout_ms", 5_000)),
            retry_delay_ms=int(policy.get("retry_delay_ms", 500)),
            pause_settle_ms=350,
        ),
        allow_preexisting_postcondition=bool(
            policy.get("allow_preexisting_postcondition", True)
        ),
        source_capture_ids=(str(policy["capture_id"]),),
    )
    SESSION_LOG.write(
        f"interaction_spec_built point={point_index} label={label!r} "
        f"profile={policy['profile'].value!r} required={bool(policy['required'])} "
        f"capture_id={policy['capture_id']!r}"
    )
    controller = ReliableInteractionController(spec, runtime)
    SESSION_LOG.write(
        f"interaction_controller_start point={point_index} label={label!r} "
        f"{_runtime_snapshot()}"
    )
    success = yield from run_coroutine_adapter(
        controller,
        Routines.Yield.wait,
    )
    if success:
        SESSION_LOG.write(
            f"interaction_state_success point={point_index} label={label!r} "
            f"{_runtime_snapshot()}"
        )
    else:
        SESSION_LOG.write(
            f"interaction_state_failure point={point_index} label={label!r} "
            f"required={bool(policy['required'])} {_runtime_snapshot()}"
        )
    if not success and policy["required"]:
        yield from _hold_failure(f"Reliable interaction failed: {label}")
        return False
    if not success:
        SESSION_LOG.write(f"optional_interaction_skipped point={point_index} label={label!r}")
    return True


def _run_interaction(point_index: int) -> Generator[Any, Any, bool]:
    SESSION_LOG.write(
        f"interaction_state_enter point={point_index} {_runtime_snapshot()}"
    )
    try:
        return bool((yield from _run_interaction_impl(point_index)))
    except Exception as error:
        detail = traceback.format_exc()
        SESSION_LOG.write(
            f"interaction_state_exception point={point_index} "
            f"error_type={type(error).__name__!r} error={str(error)!r} traceback={detail!r} "
            f"{_runtime_snapshot()}"
        )
        ConsoleLog(
            MODULE_NAME,
            f"Interaction point {point_index} crashed: {type(error).__name__}: {error}",
            Console.MessageType.Error,
        )
        required = bool(INTERACTIONS.get(point_index, {}).get("required", True))
        if required:
            yield from _hold_failure(
                f"Interaction point {point_index} crashed: {type(error).__name__}: {error}"
            )
            return False
        return True


def _drop_bundle(point_index: int) -> Generator[Any, Any, bool]:
    label = DROP_BUNDLE_POINTS[point_index]
    if not Agent.IsHoldingItem(Player.GetAgentID()):
        yield from _hold_failure(f"{label}: no Powder Keg is being carried")
        return False
    for attempt in range(3):
        yield from Routines.Yield.Keybinds.DropBundle()
        yield from Routines.Yield.wait(500)
        if not Agent.IsHoldingItem(Player.GetAgentID()):
            SESSION_LOG.write(f"drop_bundle_success point={point_index} attempt={attempt + 1}")
            return True
    yield from _hold_failure(f"{label}: bundle remained in hand")
    return False


def _wait_for_einarr_conversation() -> Generator[Any, Any, bool]:
    if COLD_VENGEANCE_QUEST_ID in set(int(value) for value in (Quest.GetQuestLogIds() or [])):
        return True
    bot.config.state_description = "Waiting 30 seconds for Einarr's conversation"
    SESSION_LOG.write(f"einarr_conversation_wait_start {_runtime_snapshot()}")
    yield from Routines.Yield.wait(30_000)
    bot.config.state_description = "Running"
    SESSION_LOG.write(f"einarr_conversation_wait_finish {_runtime_snapshot()}")
    return True


def _wait_for_party_regroup() -> Generator[Any, Any, bool]:
    radius = float(LEVEL_1_HERO_REGROUP["radius"])
    timeout_ms = int(LEVEL_1_HERO_REGROUP["timeout_ms"])
    started = time.monotonic()
    bot.config.state_description = "Waiting for living heroes to cross the bridge"
    SESSION_LOG.write(
        f"party_regroup_start radius={radius} timeout_ms={timeout_ms} {_runtime_snapshot()}"
    )
    while True:
        player_xy = Player.GetXY()
        followers = [
            *list(GLOBAL_CACHE.Party.GetHeroes() or []),
            *list(GLOBAL_CACHE.Party.GetHenchmen() or []),
        ]
        waiting: list[tuple[int, float]] = []
        for member in followers:
            agent_id = int(getattr(member, "agent_id", 0) or 0)
            if not agent_id or not Agent.IsValid(agent_id) or not Agent.IsAlive(agent_id):
                continue
            distance = math.dist(player_xy, Agent.GetXY(agent_id))
            if distance > radius:
                waiting.append((agent_id, round(distance, 1)))
        if not waiting:
            SESSION_LOG.write(f"party_regroup_success {_runtime_snapshot()}")
            bot.config.state_description = "Running"
            return True
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if elapsed_ms >= timeout_ms:
            SESSION_LOG.write(
                f"party_regroup_timeout elapsed_ms={elapsed_ms} waiting={waiting!r} "
                f"{_runtime_snapshot()}"
            )
            bot.config.state_description = "Running"
            return True
        yield from Routines.Yield.wait(250)


def _flag_all_heroes_at(
    xy: tuple[float, float],
    label: str,
) -> Generator[Any, Any, bool]:
    GLOBAL_CACHE.Party.Heroes.FlagAllHeroes(*xy)
    SESSION_LOG.write(f"heroes_flagged label={label!r} xy={xy} {_runtime_snapshot()}")
    yield from Routines.Yield.wait(500)
    return True


def _unflag_all_heroes(label: str) -> Generator[Any, Any, bool]:
    hero_count = int(GLOBAL_CACHE.Party.GetHeroCount())
    for hero_index in range(1, hero_count + 1):
        GLOBAL_CACHE.Party.Heroes.UnflagHero(hero_index)
    GLOBAL_CACHE.Party.Heroes.UnflagAllHeroes()
    SESSION_LOG.write(f"heroes_unflagged label={label!r} {_runtime_snapshot()}")
    yield from Routines.Yield.wait(500)
    return True


def _follow_recorded_path(
    points: list[Tuple[float, float]], label: str, source_route_id: str = SOURCE_ROUTE_ID
) -> Generator[Any, Any, bool]:
    if not points:
        return True
    SESSION_LOG.write(
        f"path_start label={label!r} source={source_route_id!r} count={len(points)} "
        f"first={points[0]} last={points[-1]} {_runtime_snapshot()}"
    )
    success = yield from bot.Move._coro_follow_path(points)
    SESSION_LOG.write(f"path_finish label={label!r} success={success} {_runtime_snapshot()}")
    if not success:
        yield from _hold_failure(f"Recorded path failed: {label}")
        return False
    return True


def _retreat_from_level_1_lever_and_wait() -> Generator[Any, Any, bool]:
    safe_xy = tuple(LEVEL_1_LEVER_SAFE_WAIT["xy"])
    wait_ms = int(LEVEL_1_LEVER_SAFE_WAIT["wait_ms"])
    capture_id = str(LEVEL_1_LEVER_SAFE_WAIT["capture_id"])
    bot.config.state_description = "Retreating from the Level 1 lever trap"
    SESSION_LOG.write(
        f"level_1_lever_retreat_start safe_xy={safe_xy} wait_ms={wait_ms} "
        f"capture_id={capture_id!r} {_runtime_snapshot()}"
    )
    bot.ResetHeroAICombatState(
        active=True,
        following=True,
        avoidance=True,
        looting=False,
        targeting=False,
        combat=False,
        skills=False,
    )
    try:
        success = yield from Routines.Yield.Movement.FollowPath(
            path_points=[safe_xy],
            custom_pause_fn=lambda: False,
            tolerance=80.0,
            timeout=-1,
            autopath=False,
        )
        if not success:
            yield from _hold_failure("Could not reach the safe wait location after the Level 1 lever")
            return False
        bot.config.state_description = "Waiting 15 seconds for the Level 1 bridge to lower"
        SESSION_LOG.write(f"level_1_bridge_wait_start {_runtime_snapshot()}")
        yield from Routines.Yield.wait(wait_ms)
        SESSION_LOG.write(f"level_1_bridge_wait_finish {_runtime_snapshot()}")
        bot.config.state_description = "Running"
        return True
    finally:
        bot.ResetHeroAICombatState(
            active=True,
            following=True,
            avoidance=True,
            looting=True,
            targeting=True,
            combat=True,
            skills=True,
        )


def _pick_up_key(point_index: int) -> Generator[Any, Any, bool]:
    map_id = KEY_PICKUP_MAPS[point_index]
    key_model_id = KEY_PICKUP_MODEL_IDS[point_index]
    key_name = KEY_PICKUP_ITEM_NAMES[point_index]
    point = next(
        ((x, y) for index, x, y in _capture_segment(map_id) if index == point_index),
        None,
    )
    if point is None:
        yield from _hold_failure(f"Missing captured key location for point {point_index}")
        return False

    bot.config.state_description = KEY_PICKUP_POINTS[point_index]
    spawn_deadline = time.monotonic() + 12.0
    clear_since: float | None = None
    candidates: list[int] = []
    while bot.config.fsm_running and time.monotonic() < spawn_deadline:
        candidates = _ground_keys(key_model_id, near_xy=point, max_distance=700.0)
        if candidates:
            break

        nearby_enemies = [
            int(agent_id)
            for agent_id in (AgentArray.GetEnemyArray() or [])
            if Agent.IsValid(agent_id)
            and Agent.IsAlive(agent_id)
            and Utils.Distance(point, Agent.GetXY(agent_id)) <= 2_000.0
        ]
        if nearby_enemies:
            clear_since = None
        elif clear_since is None:
            clear_since = time.monotonic()
        elif time.monotonic() - clear_since >= 1.0:
            SESSION_LOG.write(
                f"key_pickup_already_retrieved point={point_index} key_name={key_name!r} "
                f"model_id={key_model_id} reason='area clear and no matching key on ground' "
                f"{_runtime_snapshot()}"
            )
            bot.config.state_description = "Running"
            return True
        yield from Routines.Yield.wait(200)

    if not candidates:
        yield from _hold_failure(
            f"No {key_name} appeared near the captured Level "
            f"{1 if map_id == DARKRIME_LEVEL_1 else 2} key location while enemies remain"
        )
        return False

    key_agent_id = candidates[0]
    SESSION_LOG.write(
        f"key_pickup_start point={point_index} key_agent_id={key_agent_id} "
        f"candidate_ids={candidates} key_xy={Agent.GetXY(key_agent_id)} {_runtime_snapshot()}"
    )
    yield from Routines.Yield.Items.LootItems([key_agent_id], pickup_timeout=8_000)
    verify_deadline = time.monotonic() + 3.0
    key_still_present = True
    while bot.config.fsm_running and time.monotonic() < verify_deadline:
        key_still_present = key_agent_id in {
            int(agent_id) for agent_id in (AgentArray.GetItemArray() or [])
        }
        if not key_still_present:
            break
        yield from Routines.Yield.wait(200)
    if key_still_present:
        yield from _hold_failure(
            f"The {key_name} remained on the ground after the pickup attempt"
        )
        return False
    SESSION_LOG.write(
        f"key_pickup_success point={point_index} key_name={key_name!r} "
        f"model_id={key_model_id} verification='ground agent disappeared' {_runtime_snapshot()}"
    )
    bot.config.state_description = "Running"
    return True


def _ground_keys(
    model_id: int,
    near_xy: tuple[float, float] | None = None,
    max_distance: float | None = None,
) -> list[int]:
    keys: list[int] = []
    for agent_id in (AgentArray.GetItemArray() or []):
        agent_id = int(agent_id)
        if not Agent.IsValid(agent_id):
            continue
        try:
            item_id = int(Agent.GetItemAgentItemID(agent_id))
            if not item_id or int(Item.GetModelID(item_id)) != model_id:
                continue
            if (
                near_xy is not None
                and max_distance is not None
                and Utils.Distance(near_xy, Agent.GetXY(agent_id)) > max_distance
            ):
                continue
            keys.append(agent_id)
        except Exception:
            continue
    keys.sort(key=lambda agent_id: Utils.Distance(Player.GetXY(), Agent.GetXY(agent_id)))
    return keys


def _secure_havok_boss_key() -> Generator[Any, Any, bool]:
    """Use the SoO pattern: clear, loot the ground key if present, then use the lock as proof."""
    capture_xy = tuple(LEVEL_1_HAVOK_KEY_KILL["xy"])
    capture_id = str(LEVEL_1_HAVOK_KEY_KILL["capture_id"])
    deadline = time.monotonic() + 90.0
    clear_since: float | None = None
    bot.config.state_description = "Defeat Havok-kin and retrieve the Boss Key"
    SESSION_LOG.write(
        f"havok_key_gate_start capture_xy={capture_xy} capture_id={capture_id!r} "
        "verification='ground key disappearance plus boss-lock progression' "
        f"{_runtime_snapshot()}"
    )

    while bot.config.fsm_running and time.monotonic() < deadline:
        # The later Level 1 Dungeon Key can already be visible through a wall.
        # Havok drops a Boss Key, so only that exact model is valid here.
        ground_keys = _ground_keys(
            BOSS_KEY_MODEL_ID,
            near_xy=capture_xy,
            max_distance=2_000.0,
        )
        if ground_keys:
            key_agent_id = ground_keys[0]
            key_xy = Agent.GetXY(key_agent_id)
            SESSION_LOG.write(
                f"havok_key_ground_found key_agent_id={key_agent_id} key_xy={key_xy} "
                f"all_ground_key_ids={ground_keys!r} {_runtime_snapshot()}"
            )
            # The carrier is dead once the key exists. Move directly to the
            # drop even if another nearby mob still keeps danger active.
            reached = yield from Routines.Yield.Movement.FollowPath(
                path_points=[key_xy],
                custom_pause_fn=lambda: False,
                tolerance=80.0,
                timeout=8_000,
                autopath=False,
            )
            if reached and Agent.IsValid(key_agent_id):
                Player.Interact(key_agent_id, call_target=False)
                yield from Routines.Yield.wait(500)
            if not Agent.IsValid(key_agent_id) or key_agent_id not in {
                int(agent_id) for agent_id in (AgentArray.GetItemArray() or [])
            }:
                SESSION_LOG.write(
                    f"havok_key_ground_disappeared key_agent_id={key_agent_id} "
                    f"{_runtime_snapshot()}"
                )
                bot.config.state_description = "Running"
                return True
            clear_since = None
            continue

        nearby_enemies = [
            int(agent_id)
            for agent_id in (AgentArray.GetEnemyArray() or [])
            if Agent.IsValid(agent_id)
            and Agent.IsAlive(agent_id)
            and Utils.Distance(capture_xy, Agent.GetXY(agent_id)) <= 2_000.0
        ]
        if nearby_enemies:
            clear_since = None
            yield from Routines.Yield.wait(250)
            continue

        # Dungeon keys are instance/UI state after pickup, not bag inventory.
        # If the fight is clear and no Boss Key remains on the ground, HeroAI
        # already collected it (or this phase was resumed after collection).
        if clear_since is None:
            clear_since = time.monotonic()
        elif time.monotonic() - clear_since >= 1.0:
            SESSION_LOG.write(
                "havok_key_gate_success reason='area clear and no Boss Key on ground; "
                f"proceeding to boss lock' {_runtime_snapshot()}"
            )
            bot.config.state_description = "Running"
            return True
        yield from Routines.Yield.wait(250)

    remaining_enemies = [
        int(agent_id)
        for agent_id in (AgentArray.GetEnemyArray() or [])
        if Agent.IsValid(agent_id)
        and Agent.IsAlive(agent_id)
        and Utils.Distance(capture_xy, Agent.GetXY(agent_id)) <= 2_000.0
    ]
    yield from _hold_failure(
        "Havok-kin Boss Key was not acquired; "
        f"nearby enemies={remaining_enemies!r}. The boss lock will not be attempted"
    )
    return False


def _require_level_1_boss_key() -> Generator[Any, Any, bool]:
    SESSION_LOG.write(
        "level_1_boss_key_handoff verification='no bag representation; boss lock is progression gate' "
        f"{_runtime_snapshot()}"
    )
    yield
    return True


def _open_lock_until_passable(
    point_index: int,
    destination: tuple[float, float],
    label: str,
) -> Generator[Any, Any, bool]:
    """Retry a dungeon lock until a known point beyond its door is reachable."""
    for attempt in range(1, 4):
        bot.config.state_description = f"Opening {label} (attempt {attempt}/3)"
        SESSION_LOG.write(
            f"lock_passage_attempt point={point_index} label={label!r} attempt={attempt} "
            f"destination={destination} "
            f"{_runtime_snapshot()}"
        )
        if not (yield from _run_interaction(point_index)):
            return False
        # Lock activation is asynchronous. Give the key-use animation time to
        # complete before the passage probe starts moving the player away.
        yield from Routines.Yield.wait(1_500)
        passed = yield from Routines.Yield.Movement.FollowPath(
            path_points=[destination],
            custom_pause_fn=lambda: False,
            tolerance=60.0,
            timeout=6_000,
            autopath=False,
        )
        SESSION_LOG.write(
            f"lock_passage_result point={point_index} label={label!r} attempt={attempt} "
            f"passed={bool(passed)} destination={destination} {_runtime_snapshot()}"
        )
        if passed:
            bot.config.state_description = "Running"
            return True
        Player.Move(*Player.GetXY())
        yield from Routines.Yield.wait(350)

    yield from _hold_failure(
        f"{label} did not open after 3 interactions; the retrieved key was not consumed"
    )
    return False


def _open_level_1_dungeon_lock() -> Generator[Any, Any, bool]:
    # Point 259 is close enough to be falsely accepted from the locked side of
    # the door. Point 260 is deep enough that reaching it proves passage.
    beyond_door = _captured_path(DARKRIME_LEVEL_1, 260, 260)
    if not beyond_door:
        yield from _hold_failure("Missing Level 1 route point 260 beyond the dungeon lock")
        return False
    return bool(
        (yield from _open_lock_until_passable(258, beyond_door[0], "Level 1 dungeon lock"))
    )


def _schedule_path(
    points: list[Tuple[float, float]], label: str, source_route_id: str = SOURCE_ROUTE_ID
) -> None:
    frozen = list(points)
    bot.States.AddCustomState(
        lambda: _follow_recorded_path(frozen, label, source_route_id),
        label,
    )


def _capture_segment(map_id: int) -> list[Tuple[int, float, float]]:
    return list(ROUTE_POINTS.get(map_id, ()))


def _captured_path(map_id: int, first: int, last: int) -> list[Tuple[float, float]]:
    return [
        (x, y)
        for point_index, x, y in _capture_segment(map_id)
        if first <= point_index <= last
    ]


def _cross_available_level_1_bridge() -> Generator[Any, Any, bool]:
    """Probe the primary bridge, falling back to the captured alternate route."""
    primary_probe = _captured_path(DARKRIME_LEVEL_1, 161, 162)
    primary_tail = _captured_path(DARKRIME_LEVEL_1, 163, 187)
    alternate = list(LEVEL_1_OTHER_BRIDGE)
    blessing_index = int(LEVEL_1_OTHER_BRIDGE_BLESSING_INDEX)

    bot.config.state_description = "Checking whether the first Level 1 bridge is available"
    SESSION_LOG.write(
        f"level_1_bridge_probe_start probe={primary_probe!r} {_runtime_snapshot()}"
    )
    # Combat on the approach has already been cleared by the preceding
    # combat-aware path. Keep this probe direct so autopath cannot silently
    # choose the other bridge for us. Timeout is per waypoint.
    primary_available = yield from Routines.Yield.Movement.FollowPath(
        path_points=primary_probe,
        custom_pause_fn=lambda: False,
        tolerance=100.0,
        timeout=8_000,
        autopath=False,
    )
    SESSION_LOG.write(
        f"level_1_bridge_probe_result primary_available={primary_available} "
        f"{_runtime_snapshot()}"
    )

    if primary_available:
        bot.config.state_description = "Crossing the first Level 1 bridge"
        # The old two-point probe only reached the bridge edge. The missing
        # span is first exercised by point 163, and the standard bot path has
        # an unlimited movement timeout. Try the real crossing three times,
        # ten seconds per unreachable waypoint, before selecting the fallback.
        for attempt in range(1, 4):
            current_xy = Player.GetXY()
            nearest_index = min(
                range(len(primary_tail)),
                key=lambda index: Utils.Distance(current_xy, primary_tail[index]),
            )
            remaining_tail = primary_tail[nearest_index:]
            attempt_start_xy = Player.GetXY()
            SESSION_LOG.write(
                f"level_1_primary_bridge_attempt attempt={attempt} "
                f"resume_index={nearest_index} target={remaining_tail[0]} "
                f"{_runtime_snapshot()}"
            )
            crossed = yield from Routines.Yield.Movement.FollowPath(
                path_points=remaining_tail,
                custom_pause_fn=lambda: False,
                tolerance=100.0,
                timeout=10_000,
                autopath=False,
            )
            attempt_end_xy = Player.GetXY()
            SESSION_LOG.write(
                f"level_1_primary_bridge_attempt_result attempt={attempt} "
                f"success={bool(crossed)} displacement="
                f"{Utils.Distance(attempt_start_xy, attempt_end_xy):.2f} "
                f"start_xy={attempt_start_xy} end_xy={attempt_end_xy} "
                f"{_runtime_snapshot()}"
            )
            if crossed:
                SESSION_LOG.write(
                    f"level_1_primary_bridge_success attempt={attempt} {_runtime_snapshot()}"
                )
                bot.config.state_description = "Running"
                return True
            Player.Move(*Player.GetXY())
            yield from Routines.Yield.wait(250)

        SESSION_LOG.write(
            "level_1_primary_bridge_stalled attempts=3 window_seconds=30 "
            f"action='take alternate bridge' {_runtime_snapshot()}"
        )

    # Stop the failed move at the primary bridge edge before turning around.
    Player.Move(*Player.GetXY())
    bot.config.state_description = "First bridge unavailable; taking the other bridge"
    SESSION_LOG.write(
        f"level_1_bridge_fallback source={LEVEL_1_OTHER_BRIDGE_SOURCE_ROUTE_ID!r} "
        f"count={len(alternate)} {_runtime_snapshot()}"
    )
    reached_blessing = yield from _follow_recorded_path(
        alternate[: blessing_index + 1],
        "Other Level 1 bridge route to Beacon",
        LEVEL_1_OTHER_BRIDGE_SOURCE_ROUTE_ID,
    )
    if not reached_blessing:
        return False
    if not (yield from _run_interaction(ALT_BRIDGE_BLESSING_POINT)):
        return False
    reached_join = yield from _follow_recorded_path(
        alternate[blessing_index + 1 :],
        "Other Level 1 bridge route from Beacon to shared join",
        LEVEL_1_OTHER_BRIDGE_SOURCE_ROUTE_ID,
    )
    bot.config.state_description = "Running"
    return bool(reached_join)


def _add_interaction_state(map_id: int, point_index: int, source: str) -> None:
    if point_index not in INTERACTIONS:
        raise RuntimeError(f"Missing interaction policy for point {point_index}")
    if point_index not in MARKERS:
        raise RuntimeError(f"Missing interaction marker for point {point_index}")
    label = MARKERS[point_index]["name"]
    state_name = f"DD:INTERACTION:{map_id}:{point_index}:{label}"
    SESSION_LOG.write(
        f"interaction_state_added map={map_id} point={point_index} "
        f"state={state_name!r} source={source!r} label={label!r}"
    )
    _registered_interaction_points.append(point_index)
    bot.States.AddCustomState(
        lambda index=point_index: _run_interaction(index),
        state_name,
    )


def _log_phase_interactions(
    phase: str,
    map_id: int,
    first: int,
    last: int,
    expected: list[int],
    registered: list[int],
) -> None:
    SESSION_LOG.write(
        f"phase_interactions phase={phase!r} map={map_id} range={first}-{last} "
        f"ordered_points={registered} expected_points={expected}"
    )
    if registered != expected:
        raise RuntimeError(
            f"Interaction registration mismatch for {phase}: "
            f"expected {expected}, registered {registered}"
        )


def _add_route_points(map_id: int, first: int, last: int) -> None:
    phase = f"map {map_id} capture points {first}-{last}"
    expected_interactions = [
        point_index
        for point_index, _x, _y in _capture_segment(map_id)
        if first <= point_index <= last and point_index in INTERACTIONS
    ]
    registered_interactions: list[int] = []
    buffered: list[Tuple[float, float]] = []
    buffered_first = -1
    buffered_last = -1

    def flush() -> None:
        nonlocal buffered, buffered_first, buffered_last
        if buffered:
            _schedule_path(
                buffered,
                f"Replay map {map_id} capture points {buffered_first}-{buffered_last}",
            )
        buffered = []
        buffered_first = -1
        buffered_last = -1

    for point_index, x, y in _capture_segment(map_id):
        if point_index < first or point_index > last:
            continue
        if point_index in KEY_PICKUP_POINTS:
            # Do not blindly walk to the captured drop coordinate first. The
            # key may already have been auto-looted while approaching. Check
            # the live ground agent before entering the dangerous key pocket;
            # LootItems will move to the real agent only when it still exists.
            flush()
            bot.States.AddCustomState(
                lambda index=point_index: _pick_up_key(index),
                KEY_PICKUP_POINTS[point_index],
            )
            continue
        if buffered_first < 0:
            buffered_first = point_index
        buffered_last = point_index
        buffered.append((x, y))
        if point_index in INTERACTIONS:
            flush()
            _add_interaction_state(map_id, point_index, "generated route boundary")
            registered_interactions.append(point_index)
            if point_index == 207:
                bot.States.AddCustomState(
                    _retreat_from_level_1_lever_and_wait,
                    "Retreat from lever trap and wait for bridge",
                )
        elif point_index in DROP_BUNDLE_POINTS:
            flush()
            bot.States.AddCustomState(
                lambda index=point_index: _drop_bundle(index),
                DROP_BUNDLE_POINTS[point_index],
            )
    flush()
    _log_phase_interactions(
        phase,
        map_id,
        first,
        last,
        expected_interactions,
        registered_interactions,
    )


def darkrime_delves_routine(bot: Botting) -> None:
    _registered_interaction_points.clear()
    SESSION_LOG.write(
        f"interaction_policy_audit total={len(INTERACTIONS)} "
        f"deferred_gate_verification_points={list(DEFERRED_GATE_VERIFICATION_POINTS)}"
    )
    bot.States.AddHeader(BOT_NAME)

    bot.States.AddHeader("MENU")
    bot.States.AddCustomState(_anchor, "MENU_IDLE")
    bot.States.AddCustomState(_idle_forever, "MENU_IDLE_LOOP")

    bot.States.AddHeader("Approach: Longeyes Ledge to Einarr Frostcleft")
    bot.States.AddCustomState(_anchor, "DD:APPROACH")
    _configure_combat(bot)
    bot.Map.Travel(target_map_id=LONGEYES_LEDGE)
    bot.Wait.ForMapLoad(target_map_id=LONGEYES_LEDGE)
    _schedule_path(
        [(x, y) for _point_index, x, y in LONGEYES_OUTPOST_POINTS],
        "Recorded path through Longeyes Ledge",
        APPROACH_SOURCE_ROUTE_ID,
    )
    bot.Move.XYAndExitMap(-26375.0, 16180.0, target_map_id=BJORA_MARCHES)
    bot.Wait.ForMapLoad(target_map_id=BJORA_MARCHES)

    bot.States.AddHeader("Approach: Bjora entry to Longeyes blessing")
    bot.States.AddCustomState(_anchor, "DD:APPROACH_BJORA")
    _configure_combat(bot)
    bot.States.AddCustomState(
        lambda: _require_map(BJORA_MARCHES, "Bjora entry blessing approach"),
        "Require Bjora Marches",
    )
    _schedule_path(
        list(BJORA_ENTRY_TO_BLESSING),
        "Recorded path to the blessing outside Longeyes",
        APPROACH_SOURCE_ROUTE_ID,
    )
    _add_interaction_state(BJORA_MARCHES, 1007, "explicit Bjora blessing control")
    _log_phase_interactions(
        "Bjora entry to Longeyes blessing",
        BJORA_MARCHES,
        1007,
        1007,
        [1007],
        [1007],
    )

    bot.States.AddHeader("Approach: blessing to Einarr Frostcleft")
    bot.States.AddCustomState(_anchor, "DD:APPROACH_YAVB")
    _configure_combat(bot)
    bot.States.AddCustomState(
        lambda: _require_map(BJORA_MARCHES, "YAVB-safe approach"),
        "Require Bjora Marches",
    )
    _schedule_path(
        [*YAVB_BLESSING_TO_CAPTURE_JOIN, CAPTURE_JOIN_XY],
        "YAVB-safe path from the blessing to the captured route",
        "YAVB 2.0 Bjora Marches route",
    )
    _schedule_path(
        [(x, y) for _point_index, x, y in CAPTURE_JOIN_TO_EINARR_POINTS],
        "Captured route continuation to Einarr Frostcleft",
        APPROACH_SOURCE_ROUTE_ID,
    )
    # Only the continuous arrival route needs to wait for Einarr's scripted
    # conversation. Jumping directly to DD:APPROACH_EINARR starts after this
    # state and can interact immediately.
    bot.States.AddCustomState(
        _wait_for_einarr_conversation,
        "Wait 30 seconds for Einarr's conversation",
    )

    bot.States.AddHeader("Approach: At Einarr Frostcleft")
    bot.States.AddCustomState(_anchor, "DD:APPROACH_EINARR")
    _configure_combat(bot)
    bot.States.AddCustomState(
        lambda: _require_map(BJORA_MARCHES, "Einarr quest interaction"),
        "Require Bjora Marches",
    )
    _schedule_path(
        [
            (-15412.21, 13828.47),
            (-15668.46, 13787.23),
            (-15864.09, 13716.09),
        ],
        "Move into Einarr interaction range",
        APPROACH_SOURCE_ROUTE_ID,
    )
    _add_interaction_state(BJORA_MARCHES, 1, "explicit Einarr quest interaction")
    _log_phase_interactions(
        "Einarr quest acceptance",
        BJORA_MARCHES,
        1,
        1,
        [1],
        [1],
    )

    bot.States.AddHeader("Approach: Einarr to Darkrime after accepting Cold Vengeance")
    bot.States.AddCustomState(_anchor, "DD:APPROACH_POST_QUEST")
    _configure_combat(bot)
    bot.States.AddCustomState(
        lambda: _require_map(BJORA_MARCHES, "Post-quest approach"),
        "Require Bjora Marches",
    )
    _add_route_points(BJORA_MARCHES, 2, 25)
    bot.Move.XYAndExitMap(-6343.24, 19591.38, target_map_id=DARKRIME_LEVEL_1)
    bot.Wait.ForMapLoad(target_map_id=DARKRIME_LEVEL_1)

    bot.States.AddHeader("Level 1: Entrance and first Powder Keg")
    bot.States.AddCustomState(_anchor, "DD:L1_ENTRANCE")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_1, "Level 1 entrance"), "Require level 1")
    _add_route_points(DARKRIME_LEVEL_1, 27, 29)
    _schedule_path(
        list(SNOWBALL_DODGE_2),
        "Snowball Dodge 2 from entrance Beacon",
        SNOWBALL_DODGE_SOURCE_ROUTE_ID,
    )

    bot.States.AddHeader("Level 1: After snowball dodge")
    bot.States.AddCustomState(_anchor, "DD:L1_AFTER_SNOWBALL")
    _configure_combat(bot)
    bot.States.AddCustomState(
        lambda: _require_map(DARKRIME_LEVEL_1, "Level 1 after snowball dodge"),
        "Require level 1",
    )
    _add_route_points(DARKRIME_LEVEL_1, 43, 94)

    bot.States.AddHeader("Level 1: Havok-kin and second Powder Keg")
    bot.States.AddCustomState(_anchor, "DD:L1_HAVOK_KIN")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_1, "Level 1 Havok-kin"), "Require level 1")
    _add_route_points(DARKRIME_LEVEL_1, 95, 112)
    _schedule_path(
        [tuple(LEVEL_1_HAVOK_KEY_KILL["xy"])],
        "Move to Havok-kin key carrier before collecting second Powder Keg",
        str(LEVEL_1_HAVOK_KEY_KILL["capture_id"]),
    )
    bot.States.AddCustomState(
        _secure_havok_boss_key,
        "Defeat Havok-kin and retrieve Boss Key",
    )
    _add_route_points(DARKRIME_LEVEL_1, 113, 135)
    bot.States.AddCustomState(
        _require_level_1_boss_key,
        "Proceed to Level 1 boss lock with retrieved Boss Key",
    )
    _schedule_path(
        _captured_path(DARKRIME_LEVEL_1, 136, 136),
        "Approach Level 1 boss lock",
    )
    _registered_interaction_points.append(136)
    SESSION_LOG.write(
        "interaction_state_added map=635 point=136 source='retry-until-passage lock control' "
        "label='Level 1 boss lock'"
    )
    bot.States.AddCustomState(
        lambda: _open_lock_until_passable(
            136,
            # Point 137 can be reached closely enough from the locked side to
            # satisfy movement tolerance. Point 138 proves the boss lock opened.
            _captured_path(DARKRIME_LEVEL_1, 138, 138)[0],
            "Level 1 boss lock",
        ),
        "Open Level 1 boss lock and verify passage",
    )
    # The passage verifier has already carried the continuous run through 138.
    _add_route_points(DARKRIME_LEVEL_1, 139, 141)

    bot.States.AddHeader("Level 1: Bridge route")
    bot.States.AddCustomState(_anchor, "DD:L1_BRIDGES")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_1, "Level 1 bridges"), "Require level 1")
    _add_route_points(DARKRIME_LEVEL_1, 142, 160)
    # This interaction is embedded in the alternate branch rather than added
    # as an unconditional FSM state, but it is still part of the registration
    # audit so hot reload cannot silently omit its policy.
    _registered_interaction_points.append(ALT_BRIDGE_BLESSING_POINT)
    SESSION_LOG.write(
        f"interaction_state_added map={DARKRIME_LEVEL_1} "
        f"point={ALT_BRIDGE_BLESSING_POINT} source='alternate bridge branch' "
        f"label={MARKERS[ALT_BRIDGE_BLESSING_POINT]['name']!r}"
    )
    bot.States.AddCustomState(
        _cross_available_level_1_bridge,
        "Use available Level 1 bridge",
    )
    _add_route_points(DARKRIME_LEVEL_1, 188, 206)

    bot.States.AddHeader("Level 1: Lever, key, and exit")
    bot.States.AddCustomState(_anchor, "DD:L1_EXIT")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_1, "Level 1 exit"), "Require level 1")
    bot.States.AddCustomState(
        lambda: _flag_all_heroes_at(
            tuple(LEVEL_1_LEVER_HERO_SAFE_FLAG["xy"]),
            "Level 1 lever safe spot",
        ),
        "Flag heroes at safe spot before using lever",
    )
    _add_route_points(DARKRIME_LEVEL_1, 207, 207)
    bot.States.AddCustomState(
        lambda: _unflag_all_heroes("Level 1 lever bridge lowered"),
        "Unflag heroes after bridge-lowering wait",
    )

    bot.States.AddHeader("Level 1: After lever to dungeon key")
    bot.States.AddCustomState(_anchor, "DD:L1_AFTER_LEVER")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_1, "Level 1 key route"), "Require level 1")
    _add_route_points(DARKRIME_LEVEL_1, 208, 215)
    _schedule_path(
        [tuple(LEVEL_1_HERO_REGROUP["xy"])],
        "Cross bridge to hero regroup point",
        str(LEVEL_1_HERO_REGROUP["capture_id"]),
    )
    bot.States.AddCustomState(
        _wait_for_party_regroup,
        "Wait for living heroes to cross the bridge",
    )
    _add_route_points(DARKRIME_LEVEL_1, 216, 222)
    bot.States.AddCustomState(
        lambda: _flag_all_heroes_at(
            tuple(LEVEL_1_KEY_FLAG["xy"]),
            "Level 1 dungeon-key rescue position",
        ),
        "Flag heroes before the dungeon-key excursion",
    )
    _add_route_points(DARKRIME_LEVEL_1, 223, 226)

    bot.States.AddHeader("Level 1: Pick up dungeon key")
    bot.States.AddCustomState(_anchor, "DD:L1_KEY")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_1, "Level 1 key pickup"), "Require level 1")
    bot.States.AddCustomState(
        lambda: _flag_all_heroes_at(
            tuple(LEVEL_1_KEY_FLAG["xy"]),
            "Level 1 dungeon-key rescue position (phase start)",
        ),
        "Ensure heroes are flagged before picking up the dungeon key",
    )
    _add_route_points(DARKRIME_LEVEL_1, 227, 227)

    bot.States.AddHeader("Level 1: Return with key to dungeon lock")
    bot.States.AddCustomState(_anchor, "DD:L1_AFTER_KEY")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_1, "Level 1 return route"), "Require level 1")
    _add_route_points(DARKRIME_LEVEL_1, 228, 230)
    bot.States.AddCustomState(
        lambda: _unflag_all_heroes("Level 1 dungeon key retrieved and player returned"),
        "Unflag heroes after returning with the dungeon key",
    )
    _add_route_points(DARKRIME_LEVEL_1, 231, 257)
    _schedule_path(
        _captured_path(DARKRIME_LEVEL_1, 258, 258),
        "Approach Level 1 dungeon lock",
    )
    _registered_interaction_points.append(258)
    SESSION_LOG.write(
        "interaction_state_added map=635 point=258 source='retry-until-passage lock control' "
        "label='Level 1 dungeon lock'"
    )
    bot.States.AddCustomState(
        _open_level_1_dungeon_lock,
        "Open Level 1 dungeon lock and verify passage",
    )

    bot.States.AddHeader("Level 1: Dungeon lock to exit")
    bot.States.AddCustomState(_anchor, "DD:L1_AFTER_LOCK")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_1, "Level 1 exit route"), "Require level 1")
    # The lock verifier has already carried the continuous run through point
    # 260, so continue forward without backtracking toward the lock.
    _add_route_points(DARKRIME_LEVEL_1, 261, 280)
    bot.Move.XYAndExitMap(*LEVEL_1_EXIT_XY, target_map_id=DARKRIME_LEVEL_2)
    bot.Wait.ForMapLoad(target_map_id=DARKRIME_LEVEL_2)

    bot.States.AddHeader("Level 2: Entrance")
    bot.States.AddCustomState(_anchor, "DD:L2_ENTRANCE")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 entrance"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 282, 284)

    bot.States.AddHeader("Level 2: After entrance Beacon and safe route")
    bot.States.AddCustomState(_anchor, "DD:L2_AFTER_ENTRANCE_BEACON")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 safe route"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 285, 288)
    _schedule_path(
        list(LEVEL_2_SAFE_ROUTE),
        "Level 2 aggro-safe route",
        LEVEL_2_SAFE_ROUTE_SOURCE_ROUTE_ID,
    )

    bot.States.AddHeader("Level 2: After safe route and upper loop")
    bot.States.AddCustomState(_anchor, "DD:L2_AFTER_SAFE_ROUTE")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 upper loop"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 296, 312)

    bot.States.AddHeader("Level 2: Approach Pendulum Trap Room")
    bot.States.AddCustomState(_anchor, "DD:L2_UPPER_HALLS")
    _configure_combat(bot)
    bot.States.AddCustomState(
        lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 Pendulum Trap approach"),
        "Require level 2",
    )
    _add_route_points(DARKRIME_LEVEL_2, 318, 327)

    bot.States.AddHeader("Level 2: Pendulum Trap Room")
    bot.States.AddCustomState(_anchor, "DD:L2_PENDULUM_TRAP_ROOM")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 Pendulum Trap Room"), "Require level 2")
    _schedule_path(
        [tuple(LEVEL_2_PENDULUM_TRAP_ROOM["xy"])],
        "Enter Pendulum Trap Room",
        str(LEVEL_2_PENDULUM_TRAP_ROOM["capture_id"]),
    )
    _add_route_points(DARKRIME_LEVEL_2, 328, 334)

    bot.States.AddHeader("Level 2: Descent to second Beacon")
    bot.States.AddCustomState(_anchor, "DD:L2_SECOND_BEACON_APPROACH")
    _configure_combat(bot)
    bot.States.AddCustomState(
        lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 second Beacon approach"),
        "Require level 2",
    )
    _add_route_points(DARKRIME_LEVEL_2, 335, 351)

    bot.States.AddHeader("Level 2: Map Room / Second Beacon")
    bot.States.AddCustomState(_anchor, "DD:L2_MAP_ROOM")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 Map Room"), "Require level 2")
    _schedule_path(
        [tuple(LEVEL_2_MAP_ROOM["xy"])],
        "Enter Map Room",
        str(LEVEL_2_MAP_ROOM["capture_id"]),
    )
    _add_route_points(DARKRIME_LEVEL_2, 352, 354)

    bot.States.AddHeader("Level 2: Middle")
    bot.States.AddCustomState(_anchor, "DD:L2_MIDDLE")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 middle"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 355, 376)

    bot.States.AddHeader("Level 2: The Great Rift Hall")
    bot.States.AddCustomState(_anchor, "DD:L2_LOWER_CENTRAL")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 The Great Rift Hall"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 377, 397)

    bot.States.AddHeader("Level 2: Chromatic Drake Corner / Third Beacon")
    bot.States.AddCustomState(_anchor, "DD:L2_WESTERN_HALLS")
    _configure_combat(bot)
    bot.States.AddCustomState(
        lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 Chromatic Drake Corner / Third Beacon"),
        "Require level 2",
    )
    _add_route_points(DARKRIME_LEVEL_2, 398, 419)

    bot.States.AddHeader("Level 2: Approach Grelk")
    bot.States.AddCustomState(_anchor, "DD:L2_GRELK_APPROACH")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 Grelk approach"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 420, 438)

    bot.States.AddHeader("Level 2: Midway to Grelk")
    bot.States.AddCustomState(_anchor, "DD:L2_GRELK_MIDWAY")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 midway to Grelk"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 439, 456)

    bot.States.AddHeader("Level 2: After final Beacon to Grelk")
    bot.States.AddCustomState(_anchor, "DD:L2_AFTER_FINAL_BEACON")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 final Grelk corridor"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 457, 464)

    bot.States.AddHeader("Level 2: Grelk and dungeon key")
    bot.States.AddCustomState(_anchor, "DD:L2_GRELK_KEY")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 Grelk key"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 465, 465)

    bot.States.AddHeader("Level 2: Return with key")
    bot.States.AddCustomState(_anchor, "DD:L2_AFTER_GRELK")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 return with key"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 466, 482)

    bot.States.AddHeader("Level 2: Return midpoint")
    bot.States.AddCustomState(_anchor, "DD:L2_RETURN_MIDPOINT")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 return midpoint"), "Require level 2")
    _add_route_points(DARKRIME_LEVEL_2, 483, 500)

    bot.States.AddHeader("Level 2: Return north corridor")
    bot.States.AddCustomState(_anchor, "DD:L2_RETURN_NORTH")
    _configure_combat(bot)
    bot.States.AddCustomState(
        lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 return north corridor"),
        "Require level 2",
    )
    _add_route_points(DARKRIME_LEVEL_2, 501, 518)

    bot.States.AddHeader("Level 2: Boss lock and exit")
    bot.States.AddCustomState(_anchor, "DD:L2_EXIT")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_2, "Level 2 exit"), "Require level 2")
    _schedule_path(
        _captured_path(DARKRIME_LEVEL_2, 519, 519),
        "Approach Level 2 boss lock",
    )
    _registered_interaction_points.append(519)
    SESSION_LOG.write(
        "interaction_state_added map=636 point=519 source='retry-until-passage lock control' "
        "label='Level 2 boss lock'"
    )
    bot.States.AddCustomState(
        lambda: _open_lock_until_passable(
            519,
            # The middle point is still reachable from the locked side. The
            # final captured point is beyond the obstruction and is the real
            # passage proof used to decide whether another click is needed.
            tuple(LEVEL_2_BOSS_LOCK_TO_DOOR[-1]),
            "Level 2 boss lock",
        ),
        "Open Level 2 boss lock and verify passage",
    )
    bot.Move.XYAndExitMap(*LEVEL_2_EXIT_XY, target_map_id=DARKRIME_LEVEL_3)
    bot.Wait.ForMapLoad(target_map_id=DARKRIME_LEVEL_3)

    bot.States.AddHeader("Level 3: Entrance")
    bot.States.AddCustomState(_anchor, "DD:L3_ENTRANCE")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_3, "Level 3 entrance"), "Require level 3")
    _schedule_path(
        _captured_path(DARKRIME_LEVEL_3, 522, 524),
        "Replay map 637 capture points 522-524",
    )
    _add_interaction_state(DARKRIME_LEVEL_3, 524, "explicit Level 3 entrance boundary")
    _schedule_path(
        _captured_path(DARKRIME_LEVEL_3, 538, 577),
        "Replay map 637 capture points 538-577",
    )
    _add_interaction_state(DARKRIME_LEVEL_3, 577, "explicit Level 3 interior Beacon boundary")
    _log_phase_interactions(
        "Level 3 entrance",
        DARKRIME_LEVEL_3,
        522,
        577,
        [524, 577],
        [524, 577],
    )

    bot.States.AddHeader("Level 3: Havok Soulwail and chest")
    bot.States.AddCustomState(_anchor, "DD:L3_BOSS")
    _configure_combat(bot)
    bot.States.AddCustomState(lambda: _require_map(DARKRIME_LEVEL_3, "Level 3 boss"), "Require level 3")
    _schedule_path(
        _captured_path(DARKRIME_LEVEL_3, 578, 593),
        "Replay map 637 capture points 578-593",
    )
    _add_interaction_state(DARKRIME_LEVEL_3, 593, "explicit Level 3 chest boundary")
    _log_phase_interactions(
        "Level 3 boss and chest",
        DARKRIME_LEVEL_3,
        578,
        593,
        [593],
        [593],
    )
    missing_interactions = [
        point_index
        for point_index in INTERACTIONS
        if point_index not in _registered_interaction_points
    ]
    duplicate_interactions = sorted(
        {
            point_index
            for point_index in _registered_interaction_points
            if _registered_interaction_points.count(point_index) > 1
        }
    )
    SESSION_LOG.write(
        f"interaction_registration_audit ordered_points={_registered_interaction_points} "
        f"missing_points={missing_interactions} duplicate_points={duplicate_interactions}"
    )
    if missing_interactions or duplicate_interactions:
        raise RuntimeError(
            "Darkrime interaction registration audit failed: "
            f"missing={missing_interactions}, duplicates={duplicate_interactions}"
        )
    bot.States.JumpToStepName("MENU_IDLE")


bot.SetMainRoutine(darkrime_delves_routine)


def _start_at_phase(step_name: str) -> None:
    try:
        bot.Stop()
        GLOBAL_CACHE.Coroutines.clear()
        bot.config.FSM.reset()
        bot.config.fsm_running = True
        bot.config.state_description = "Running"
        bot.config.FSM.jump_to_state_by_name(step_name)
        bot.config.FSM.resume()
        SESSION_LOG.write(f"start_phase step={step_name!r} {_runtime_snapshot()}")
    except Exception as error:
        bot.config.fsm_running = False
        ConsoleLog(MODULE_NAME, f"Could not start {step_name}: {error}", Console.MessageType.Error)


def _draw_main_child_minimal(self, main_child_dimensions=(420, 220), icon_path="", iconwidth=0):
    fsm = self._config.FSM
    running = bool(self._config.fsm_running)
    paused = bool(fsm.is_paused()) if running else False
    PyImGui.text(f"Status: {'Paused' if paused else 'Running' if running else 'Idle'}")
    PyImGui.text_wrapped(f"Step: {fsm.get_current_step_name() or 'Not started'}")
    if running:
        if PyImGui.button(f"{'Resume' if paused else 'Pause'}##DDPause"):
            if paused:
                fsm.resume()
                self._config.state_description = "Running"
            else:
                fsm.pause()
                self._config.state_description = "Paused"
                Player.Move(*Player.GetXY())
        PyImGui.same_line(0.0, 8.0)
        if PyImGui.button("Stop##DDStop"):
            bot.Stop()
            GLOBAL_CACHE.Coroutines.clear()
            self._config.state_description = "Idle"


bot.UI._draw_main_child = types.MethodType(_draw_main_child_minimal, bot.UI)


def _draw_controls() -> None:
    global _phase_index
    PyImGui.separator()
    PyImGui.text("Starting phase")
    labels = [label for label, _ in PHASES]
    _phase_index = PyImGui.combo("##DDPhase", _phase_index, labels)
    if PyImGui.button("Run selected phase##DDRunPhase"):
        _start_at_phase(PHASES[_phase_index][1])
    if _phase_index > 0:
        PyImGui.text_wrapped(
            "Checkpoint starts assume you are on the correct level and earlier keys, locks, "
            "and objectives are complete."
        )
    counts = ", ".join(
        f"{Map.GetMapName(map_id)}: {len(_capture_segment(map_id))}"
        for map_id in (BJORA_MARCHES, DARKRIME_LEVEL_1, DARKRIME_LEVEL_2, DARKRIME_LEVEL_3)
    )
    PyImGui.text_wrapped(f"Normalized capture points: {counts}.")
    if _initialization_error:
        PyImGui.text_wrapped(f"Route initialization error: {_initialization_error}")
    PyImGui.text_wrapped(
        "The full run travels to Longeyes Ledge, takes the outside blessing, follows the YAVB-safe "
        "Bjora route to the captured continuation, waits for Einarr's conversation, accepts Cold Vengeance, "
        "and enters Darkrime."
    )
    if _interaction_events:
        latest = _interaction_events[-1]
        PyImGui.text_wrapped(
            f"Latest interaction: {latest.get('interaction', '')} / {latest.get('event', '')}"
        )
    PyImGui.text_wrapped("Runtime details are written to the Py4GW console.")


def tooltip() -> None:
    PyImGui.begin_tooltip()
    PyImGui.text("Darkrime Delves")
    PyImGui.separator()
    PyImGui.text_wrapped(
        "Replays the normalized three-level route with restartable phases and opt-in Reliable Interaction."
    )
    PyImGui.end_tooltip()


def main() -> None:
    global _initialization_error
    try:
        bot.Update()
    except Exception as error:
        _initialization_error = f"{type(error).__name__}: {error}"
        bot.config.initialized = True
        bot.config.fsm_running = False
        SESSION_LOG.write(f"route_initialization_error error={_initialization_error!r}")
        ConsoleLog(MODULE_NAME, _initialization_error, Console.MessageType.Error)
    bot.UI.draw_window(
        icon_path=os.path.join(PySystem.Console.get_projects_path(), MODULE_ICON),
        main_child_dimensions=(440, 280),
        additional_ui=_draw_controls,
    )


if __name__ == "__main__":
    main()
