from __future__ import annotations

from collections.abc import Callable
import time

import PySystem

from Py4GWCoreLib import Agent, AgentArray, GLOBAL_CACHE, Map, Player, SharedCommandType
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Widgets.System.Messaging import (
    get_inventory_count,
    reset_inventory_count,
)

from .NicholasFarms import (
    FLOW_CHALLENGE,
    FLOW_DIALOG,
    FLOW_DIRECT,
    FLOW_FOW,
    FLOW_PORTAL_LOOP,
    FLOW_ROUTE_LOOP,
    FLOW_TWO_MAP,
    FarmDefinition,
)


MODULE_NAME = "Nicholas Farm Base"

_PREPARED_ATTR = "_nicholas_manager_prepared_farm_key"
_PORTAL_READY_KEY = "__nicholas_manager_portal_ready"
_TARGET_REACHED_FARM_KEY = ""

_INVENTORY_QUERY_TIMEOUT_MS = 10_000
_INVENTORY_QUERY_POLL_MS = 100

# Nicholas loot is orchestrated directly from NicoBase while a farm waypoint
# is running. The leader interacts with wanted loot directly; followers receive
# SharedCommandType.PickUpLoot.
_NICHOLAS_LOOT_ORCHESTRATOR_STATE: dict[str, dict[str, object]] = {}


def _selected_nicholas_drop_agents(farm: FarmDefinition) -> list[int]:
    """Return raw ground agents matching the selected Nicholas model."""
    try:
        from Py4GWCoreLib.Item import Item
    except Exception:
        return []

    wanted_model_id = int(farm.model_id)
    matches: list[int] = []

    try:
        item_agents = AgentArray.GetItemArray()
    except Exception:
        return matches

    for raw_agent_id in item_agents:
        try:
            agent_id = int(raw_agent_id)
            item_agent = Agent.GetItemAgentByID(agent_id)
            if item_agent is None:
                continue
            item_id = int(item_agent.item_id)
            if item_id <= 0:
                continue
            if int(Item.GetModelID(item_id)) == wanted_model_id:
                matches.append(agent_id)
        except Exception:
            continue

    return matches


def _dispatch_nicholas_pickup_to_followers(
    farm: FarmDefinition,
    drop_agent_id: int,
    *,
    retry_after_ms: int = 5000,
) -> bool:
    """
    Dispatch follower pickup once per ground drop.

    The same ``drop_agent_id`` is not re-dispatched on every tree tick. If the
    item is still present after ``retry_after_ms``, one retry is allowed.
    """
    key = str(farm.key)
    state = _NICHOLAS_LOOT_ORCHESTRATOR_STATE.setdefault(
        key,
        {
            "local_agent_id": 0,
            "remote_drops": {},
        },
    )

    remote_drops = state.setdefault("remote_drops", {})
    if not isinstance(remote_drops, dict):
        remote_drops = {}
        state["remote_drops"] = remote_drops

    agent_id = int(drop_agent_id)
    now_ms = int(time.monotonic() * 1000.0)

    drop_state = remote_drops.setdefault(
        agent_id,
        {
            "last_dispatch_ms": 0,
            "dispatch_count": 0,
        },
    )

    last_dispatch_ms = int(drop_state.get("last_dispatch_ms", 0) or 0)
    dispatch_count = int(drop_state.get("dispatch_count", 0) or 0)

    should_dispatch = (
        dispatch_count == 0
        or (
            dispatch_count == 1
            and now_ms - last_dispatch_ms >= int(retry_after_ms)
        )
    )
    if not should_dispatch:
        return False

    sender_email = str(Player.GetAccountEmail() or "").strip()
    if not sender_email:
        return False

    recipients: list[str] = []

    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData() or []
    except Exception:
        accounts = []

    for account in accounts:
        try:
            receiver_email = str(getattr(account, "AccountEmail", "") or "").strip()
            if not receiver_email or receiver_email == sender_email:
                continue
            if not bool(getattr(account, "IsAccount", False)):
                continue

            account_map = int(
                getattr(
                    getattr(getattr(account, "AgentData", None), "Map", None),
                    "MapID",
                    0,
                )
                or 0
            )
            if account_map != int(farm.farm_map_id):
                continue

            message_index = int(
                GLOBAL_CACHE.ShMem.SendMessage(
                    sender_email,
                    receiver_email,
                    SharedCommandType.PickUpLoot,
                    (0, 0, 0, 0),
                )
            )
            if message_index >= 0:
                recipients.append(receiver_email)
        except Exception:
            continue

    if not recipients:
        return False

    drop_state["last_dispatch_ms"] = now_ms
    drop_state["dispatch_count"] = dispatch_count + 1

    if dispatch_count == 0:
        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"Nicholas loot: {farm.name} pickup dispatched to "
                f"{len(recipients)} follower(s)."
            ),
            PySystem.Console.MessageType.Info,
        )
    else:
        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"Nicholas loot: {farm.name} pickup retry dispatched to "
                f"{len(recipients)} follower(s) after {int(retry_after_ms / 1000)}s."
            ),
            PySystem.Console.MessageType.Info,
        )

    return True


def _cleanup_nicholas_remote_drop_state(
    farm: FarmDefinition,
    visible_agent_ids: set[int],
) -> None:
    """Forget follower-dispatch state for drops no longer visible."""
    state = _NICHOLAS_LOOT_ORCHESTRATOR_STATE.setdefault(
        str(farm.key),
        {
            "local_agent_id": 0,
            "remote_drops": {},
        },
    )

    remote_drops = state.setdefault("remote_drops", {})
    if not isinstance(remote_drops, dict):
        state["remote_drops"] = {}
        return

    for agent_id in list(remote_drops):
        if int(agent_id) not in visible_agent_ids:
            remote_drops.pop(agent_id, None)



def _priority_local_nicholas_loot_tick(
    farm: FarmDefinition,
    _node: BehaviorTree.Node,
) -> BehaviorTree.NodeState:
    """
    Directly pick the selected Nicholas trophy on the BottingTree leader.

    This uses the same local LootFilters authority proven by the diagnostics,
    but does NOT go through HeroAI or a self-addressed PickUpLoot message.
    Returning RUNNING gives the local pickup priority over the farm waypoint.
    """
    try:
        if int(Map.GetMapID()) != int(farm.farm_map_id):
            return BehaviorTree.NodeState.FAILURE

        from Py4GWCoreLib.Item import Item
        from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters.controller import LootFilters

        wanted_model_id = int(farm.model_id)
        loot_array = LootFilters().GetLootArray(Range.Earshot.value)

        selected_agent_id = 0
        for raw_agent_id in loot_array:
            try:
                agent_id = int(raw_agent_id)
                item_agent = Agent.GetItemAgentByID(agent_id)
                if item_agent is None:
                    continue
                item_id = int(item_agent.item_id)
                if item_id <= 0:
                    continue
                if int(Item.GetModelID(item_id)) != wanted_model_id:
                    continue
                selected_agent_id = agent_id
                break
            except Exception:
                continue

        if selected_agent_id <= 0:
            state = _NICHOLAS_LOOT_ORCHESTRATOR_STATE.setdefault(
                str(farm.key),
                {"local_agent_id": 0, "remote_drops": {}},
            )
            state["local_agent_id"] = 0
            return BehaviorTree.NodeState.FAILURE

        state = _NICHOLAS_LOOT_ORCHESTRATOR_STATE.setdefault(
            str(farm.key),
            {"local_agent_id": 0, "remote_drops": {}},
        )

        if int(state.get("local_agent_id", 0) or 0) != selected_agent_id:
            state["local_agent_id"] = selected_agent_id
            PySystem.Console.Log(
                MODULE_NAME,
                f"Nicholas loot: {farm.name} pickup started on leader.",
                PySystem.Console.MessageType.Info,
            )

        # This is the same native interaction used by RoutinesBT.Items.LootItems.
        # Guild Wars handles the approach to an interactable item.
        Player.ChangeTarget(selected_agent_id)
        Player.Interact(selected_agent_id, False)

        return BehaviorTree.NodeState.RUNNING

    except Exception as exc:
        PySystem.Console.Log(
            MODULE_NAME,
            f"Nicholas direct local loot failed for {farm.name}: {exc}",
            PySystem.Console.MessageType.Warning,
        )
        return BehaviorTree.NodeState.FAILURE


def _nicholas_remote_loot_monitor_tick(
    farm: FarmDefinition,
    _node: BehaviorTree.Node,
) -> BehaviorTree.NodeState:
    """
    Dispatch follower pickup once per visible selected trophy.

    A still-visible drop gets at most one retry after five seconds. Removed
    drops are forgotten so a future drop dispatches immediately.
    """
    try:
        if int(Map.GetMapID()) != int(farm.farm_map_id):
            _cleanup_nicholas_remote_drop_state(farm, set())
            return BehaviorTree.NodeState.SUCCESS

        visible_agent_ids = {
            int(agent_id)
            for agent_id in _selected_nicholas_drop_agents(farm)
        }

        _cleanup_nicholas_remote_drop_state(farm, visible_agent_ids)

        for agent_id in visible_agent_ids:
            _dispatch_nicholas_pickup_to_followers(
                farm,
                agent_id,
                retry_after_ms=5000,
            )

    except Exception as exc:
        PySystem.Console.Log(
            MODULE_NAME,
            f"Nicholas follower loot dispatch failed for {farm.name}: {exc}",
            PySystem.Console.MessageType.Warning,
        )

    return BehaviorTree.NodeState.SUCCESS



def _with_nicholas_loot_orchestrator(
    farm: FarmDefinition,
    child: BehaviorTree,
    *,
    name: str,
) -> BehaviorTree:
    """
    Give the selected Nicholas trophy priority while a farm waypoint is active.

    Leader:
      LootFilters candidate -> direct Player.Interact -> resume farm.

    Followers:
      selected-model ground detection -> SharedCommandType.PickUpLoot.
    """
    local_priority = BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"{name} - Direct Nicholas Loot",
            action_fn=lambda node: _priority_local_nicholas_loot_tick(farm, node),
            aftercast_ms=0,
        )
    )

    priority_child = BT.Selector(
        name=f"{name} - Nicholas Loot Priority",
        children=[
            local_priority,
            child,
        ],
    )

    remote_monitor = BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"{name} - Follower Nicholas Loot Dispatch",
            action_fn=lambda node: _nicholas_remote_loot_monitor_tick(farm, node),
            aftercast_ms=0,
        )
    )

    return BehaviorTree(
        BehaviorTree.ParallelNode(
            name=f"{name} - With Nicholas Loot",
            children=[
                priority_child,
                remote_monitor,
            ],
        )
    )


def configure_tree(tree: BottingTree) -> BottingTree:
    """
    Common Nicholas runtime policy.

    Inventory maintenance is intentionally disabled during the farm because
    MerchantRules is also disabled on every multibox client while the native
    item/map-transition crash is being investigated.
    """
    return tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        resurrection_scroll=False,
        auto_inventory_handler_enabled=False,
        restore_auto_inventory_handler_on_stop=True,
        enable_party_wipe_recovery=False,
        heroai_state_logging=False,
    )


def disable_merchant_rules_all_accounts() -> BehaviorTree:
    """
    Disable MerchantRules once on leader + all active shared-memory accounts.

    There is deliberately no BottingTree widget policy here: the command is
    dispatched once and acknowledged, so WidgetHandler is not touched on every
    tick.
    """
    return BTShared.SendAndWait(
        command=SharedCommandType.DisableWidget,
        extra_data=("MerchantRules", "", "", ""),
        include_self=True,
        refs_blackboard_key="__nicholas_disable_merchant_rules_refs",
        timeout_ms=10_000,
        poll_interval_ms=100,
        log=True,
        aftercast_ms=100,
    )



def _add_farm_item_loot_local(farm: FarmDefinition) -> BehaviorTree:
    """
    Add the selected Nicholas model DIRECTLY to the new LIVE LootFilters system.

    Do not use BT.AddModelToLootWhitelist here. Some Py4GW installations still
    expose an older implementation backed by legacy LootConfig, while the
    current HeroAI loot filter reads LootFilters(). This direct mutation makes
    Nicholas use the exact same authority that _verify_farm_item_loot_live()
    inspects immediately afterwards.
    """
    def _add(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters.controller import LootFilters

            model_id = int(farm.model_id)
            loot = LootFilters()
            loot.add_model(model_id)

            added = model_id in loot.live.added_model_ids

            return (
                BehaviorTree.NodeState.SUCCESS
                if added
                else BehaviorTree.NodeState.FAILURE
            )

        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"Direct LIVE loot add failed for {farm.name}: {exc}",
                PySystem.Console.MessageType.Error,
            )
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Direct Live Loot Add - {farm.name}",
            action_fn=_add,
            aftercast_ms=50,
        )
    )


def _verify_farm_item_loot_live(farm: FarmDefinition) -> BehaviorTree:
    """
    Verify the leader's LIVE LootFilters state for the selected Nicholas item.

    Stable model additions normally survive map changes.  This check exists so
    Nicholas does not silently continue farming when another LIVE loot rule
    prevents the requested trophy from ever being offered to HeroAI.

    We deliberately DO NOT override the user's blacklist/veto policy here.
    Instead we fail with an explicit console message.
    """
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters.controller import LootFilters
            from Py4GWCoreLib.py4gwcorelib_src.system_settings.loot_filters.expected_types import expected_type

            loot = LootFilters()
            model_id = int(farm.model_id)
            item_type = expected_type(model_id)

            enabled = bool(loot.live.enabled)
            added = model_id in loot.live.added_model_ids
            model_blacklisted = model_id in loot.live.blacklist_model_ids
            type_vetoed = (
                item_type is not None
                and int(item_type) in loot.live.blacklist_item_types
            )

            if not enabled:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        "Loot Filters master switch is OFF. "
                        f"{farm.name} cannot be auto-looted."
                    ),
                    PySystem.Console.MessageType.Error,
                )
                return BehaviorTree.NodeState.FAILURE

            if model_blacklisted:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f"{farm.name} [{model_id}] is model-blacklisted. "
                        "The blacklist vetoes the Nicholas script whitelist."
                    ),
                    PySystem.Console.MessageType.Error,
                )
                return BehaviorTree.NodeState.FAILURE

            if type_vetoed:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f"The item type for {farm.name} is vetoed in Loot Filters. "
                        "Item-type vetoes beat script-added models."
                    ),
                    PySystem.Console.MessageType.Error,
                )
                return BehaviorTree.NodeState.FAILURE

            if not added:
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f"{farm.name} [{model_id}] is missing from the LIVE "
                        "script-added model whitelist."
                    ),
                    PySystem.Console.MessageType.Error,
                )
                return BehaviorTree.NodeState.FAILURE

            PySystem.Console.Log(
                MODULE_NAME,
                f"Nicholas loot enabled: {farm.name} [{model_id}].",
                PySystem.Console.MessageType.Info,
            )
            return BehaviorTree.NodeState.SUCCESS

        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"Could not verify live loot state for {farm.name}: {exc}",
                PySystem.Console.MessageType.Error,
            )
            return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Verify Live Loot - {farm.name}",
            action_fn=_check,
            aftercast_ms=0,
        )
    )


def whitelist_farm_item_all_accounts(farm: FarmDefinition) -> BehaviorTree:
    """
    Add the selected Nicholas trophy model to the LIVE loot whitelist.

    Leader:
      - mutate LootFilters().live directly and verify it locally.

    Followers:
      - use the stock SharedCommandType.AddModelToLootWhitelist command (71).

    This version deliberately does NOT depend on custom InventoryQuery extensions
    in Messaging.py, so it is compatible with the original Messaging widget.
    """
    model_id = int(farm.model_id)

    return BT.Sequence(
        name=f"Whitelist Farm Item - {farm.name}",
        children=[
            _add_farm_item_loot_local(farm),

            BTShared.SendAndWait(
                command=SharedCommandType.AddModelToLootWhitelist,
                params=(float(model_id), 0.0, 0.0, 0.0),
                extra_data=(farm.name, "", "", ""),
                include_self=False,
                refs_blackboard_key="__nicholas_add_farm_model_whitelist_refs",
                timeout_ms=10_000,
                poll_interval_ms=100,
                log=False,
                aftercast_ms=100,
            ),

            _verify_farm_item_loot_live(farm),
        ],
    )


def _wait_for_farm_party_on_map(
    farm: FarmDefinition,
    *,
    stable_ms: int = 1250,
    timeout_ms: int = 20_000,
) -> BehaviorTree:
    """
    Wait until every account in the current Nicholas farming party is reported
    on the actual farm map, then keep that state stable briefly.

    This is intentionally done BEFORE broadcasting the loot whitelist refresh.
    Live testing showed followers could receive/acknowledge the whitelist command
    while still zoning. Their subsequent map load then rebuilt/reset their local
    LootFilters state, leaving the Nicholas model absent on that follower.
    """
    state = {
        "started_at": 0.0,
        "ready_since": 0.0,
        "last_waiting": None,
    }

    def _wait(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        now = time.monotonic()

        if float(state["started_at"] or 0.0) <= 0.0:
            state["started_at"] = now

        target_map_id = int(farm.farm_map_id)
        party_accounts = farm_party_accounts()

        if not party_accounts:
            state["ready_since"] = 0.0
            return BehaviorTree.NodeState.RUNNING

        waiting: list[str] = []

        for email, label in party_accounts:
            try:
                account = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(email)
            except Exception:
                account = None

            if account is None:
                waiting.append(f"{label}:no-shmem")
                continue

            account_map_id = int(_account_map_tuple(account)[0])

            if account_map_id != target_map_id:
                waiting.append(f"{label}:map={account_map_id}")

        if waiting:
            state["ready_since"] = 0.0

            waiting_text = ", ".join(waiting)
            if waiting_text != state["last_waiting"]:
                state["last_waiting"] = waiting_text
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f"Waiting before loot refresh for all accounts to load "
                        f"{farm.name} farm map {target_map_id}: {waiting_text}"
                    ),
                    PySystem.Console.MessageType.Info,
                )

            elapsed_ms = int((now - float(state["started_at"])) * 1000.0)
            if elapsed_ms >= int(timeout_ms):
                PySystem.Console.Log(
                    MODULE_NAME,
                    (
                        f"Timed out after {elapsed_ms} ms waiting for all Nicholas "
                        f"accounts on farm map {target_map_id}. Loot refresh aborted "
                        "instead of broadcasting during an account map transition."
                    ),
                    PySystem.Console.MessageType.Error,
                )
                return BehaviorTree.NodeState.FAILURE

            return BehaviorTree.NodeState.RUNNING

        # Everyone is now reported on the requested map. Require that state to
        # remain true briefly so a follower that is still finalizing its zoning
        # cannot immediately lose the refreshed LootFilters state afterwards.
        if float(state["ready_since"] or 0.0) <= 0.0:
            state["ready_since"] = now
            state["last_waiting"] = None

            labels = ", ".join(label for _email, label in party_accounts)
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f"All Nicholas accounts reported on farm map {target_map_id}: "
                    f"{labels}. Waiting {int(stable_ms)} ms for map state to settle "
                    "before refreshing loot."
                ),
                PySystem.Console.MessageType.Info,
            )
            return BehaviorTree.NodeState.RUNNING

        stable_elapsed_ms = int(
            (now - float(state["ready_since"])) * 1000.0
        )
        if stable_elapsed_ms < int(stable_ms):
            return BehaviorTree.NodeState.RUNNING

        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"All Nicholas accounts stable on farm map {target_map_id} for "
                f"{stable_elapsed_ms} ms. Refreshing {farm.name} loot whitelist now."
            ),
            PySystem.Console.MessageType.Info,
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Wait All Accounts On Farm Map - {farm.name}",
            action_fn=_wait,
            aftercast_ms=0,
        )
    )

def _refresh_farm_runtime_after_entry(
    farm: FarmDefinition,
) -> BehaviorTree:
    """
    Prepare Nicholas loot after entering the farm map.

    Wait until every farming account has finished zoning, then push the selected
    trophy model once. Pickup is handled by the Nicholas loot orchestrator.
    """
    return _map_guarded_node(
        name=f"Prepare Farm Loot - {farm.name}",
        map_id=int(farm.farm_map_id),
        child=BT.Sequence(
            name=f"Prepare Farm Loot - {farm.name} - All Accounts",
            children=[
                _wait_for_farm_party_on_map(farm),
                whitelist_farm_item_all_accounts(farm),
            ],
        ),
    )


def _challenge_instance_already_loaded(
    farm: FarmDefinition,
) -> BehaviorTree:
    """
    Immediate check for challenge/mission instances whose outpost and mission
    may share the same MapID.

    MapID alone is NOT sufficient:
      Minotaur Horn: outpost 118, mission 118
      Spiked Crest : outpost 19,  mission 19

    The farm is considered loaded only when the expected MapID is active AND
    the current instance is actually explorable.
    """
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            current_map_id = int(Map.GetMapID() or 0)
            is_explorable = bool(Map.IsExplorable())
        except Exception:
            return BehaviorTree.NodeState.FAILURE

        if current_map_id == int(farm.farm_map_id) and is_explorable:
            return BehaviorTree.NodeState.SUCCESS

        return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Challenge Instance Loaded - {farm.name}",
            action_fn=_check,
            aftercast_ms=0,
        )
    )


def _enter_challenge_and_wait_for_explorable(
    farm: FarmDefinition,
) -> BehaviorTree:
    """
    Enter a mission/challenge and wait for the INSTANCE TYPE to become
    explorable.

    Do not use BT.EnterChallenge(target_map_id=farm.farm_map_id) here when the
    outpost and mission share one MapID: its final WaitForMapLoad(map_id) can
    succeed while we are still standing in the outpost because the MapID
    already matches.

    Waiting for Map.IsExplorable() removes that ambiguity.
    """
    def _click_enter(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if not Map.IsOutpost():
                # If recovery reaches this action after the zone has already
                # changed, do not click Enter Challenge a second time.
                if Map.IsExplorable():
                    return BehaviorTree.NodeState.SUCCESS

            PySystem.Console.Log(
                MODULE_NAME,
                f"Entering challenge for {farm.name}.",
                PySystem.Console.MessageType.Info,
            )
            Map.EnterChallenge()
            return BehaviorTree.NodeState.SUCCESS
        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"Enter challenge failed for {farm.name}: {exc}",
                PySystem.Console.MessageType.Error,
            )
            return BehaviorTree.NodeState.FAILURE

    return BT.Sequence(
        name=f"Enter Challenge - {farm.name}",
        children=[
            BehaviorTree(
                BehaviorTree.ActionNode(
                    name=f"Click Enter Challenge - {farm.name}",
                    action_fn=_click_enter,
                    aftercast_ms=100,
                )
            ),
            BT.Wait(max(0, int(farm.challenge_delay_ms))),
            BT.WaitUntilOnExplorable(timeout_ms=60_000),
        ],
    )


def _range_for_farm(farm: FarmDefinition) -> float:
    if farm.clear_radius == "Spirit":
        return Range.Spirit.value
    return Range.Earshot.value


def reset_prepare_session(tree: BottingTree) -> None:
    """
    Forget the one-time farm preparation state.

    This is deliberately stored on the BottingTree instance instead of its
    blackboard. BottingTree.Start() -> Reset() clears the blackboard when a
    named planner step is restarted, which previously caused the next planner
    pass to kick/rebuild the multibox party again.

    The tree instance itself survives planner restarts, so this attribute
    remains valid until the user actually stops the bot.
    """
    global _TARGET_REACHED_FARM_KEY

    setattr(tree, _PREPARED_ATTR, "")
    _TARGET_REACHED_FARM_KEY = ""


def _is_prepare_session_ready(
    tree: BottingTree,
    farm: FarmDefinition,
) -> bool:
    return str(getattr(tree, _PREPARED_ATTR, "") or "") == str(farm.key)


def _prepared_session_check(
    tree: BottingTree,
    farm: FarmDefinition,
) -> BehaviorTree:
    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _is_prepare_session_ready(tree, farm):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Farm Party Already Prepared",
            action_fn=_check,
            aftercast_ms=0,
        )
    )


def _mark_prepare_session_ready(
    tree: BottingTree,
    farm: FarmDefinition,
) -> BehaviorTree:
    def _mark(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        setattr(tree, _PREPARED_ATTR, str(farm.key))
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Remember Farm Party Preparation",
            action_fn=_mark,
            aftercast_ms=0,
        )
    )


def prepare_farm(
    tree_getter: Callable[[], BottingTree],
    farm: FarmDefinition,
) -> BehaviorTree:
    """
    One-time setup per MANUAL Start:

      MerchantRules OFF on all accounts
      -> aggressive multibox HeroAI
      -> leave current party
      -> RANDOM travel to farm outpost
      -> create multibox party
      -> Normal Mode
      -> selected trophy model whitelisted + verified on all accounts

    IMPORTANT:
    The prepared state is stored on the BottingTree instance, not in the
    blackboard. Named-step recovery may call BottingTree.Start(), whose Reset()
    clears the blackboard. The tree attribute survives that internal restart,
    so a normal farm run returns to the outpost and continues with its outpost
    path / MoveAndExitMap without kicking and rebuilding the party.

    The Manager clears this session attribute only while the farm tree is
    genuinely stopped, so the next manual Start performs a fresh setup.
    """
    tree = tree_getter()

    return BT.Selector(
        name="Prepare Farm",
        children=[
            _prepared_session_check(tree, farm),
            BT.Sequence(
                name="Initial Farm Setup",
                children=[
                    disable_merchant_rules_all_accounts(),
                    tree.Config.Aggressive(
                        multi_account=True,
                        account_isolation=False,
                        auto_loot=True,
                        resurrection_scroll=False,
                        reset_hero_ai=True,
                    ),
                    BT.LeaveParty(),
                    BT.Travel(
                        target_map_id=farm.outpost_map_id,
                        random_travel=True,
                        log=True,
                    ),
                    BT.CreateParty(
                        multibox_invite=True,
                        timeout_ms=20_000,
                        log=True,
                    ),
                    BT.SetHardMode(
                        hard_mode=False,
                        log=False,
                    ),

                    # Party first: farm_party_accounts() can now identify every
                    # farming client before we push/verify the LIVE loot model.
                    whitelist_farm_item_all_accounts(farm),

                    _mark_prepare_session_ready(tree, farm),
                ],
            ),
        ],
    )


def _account_map_tuple(account: object) -> tuple[int, int, int, int]:
    map_obj = getattr(getattr(account, "AgentData", None), "Map", None)
    return (
        int(getattr(account, "MapID", 0) or getattr(map_obj, "MapID", 0) or 0),
        int(getattr(account, "MapRegion", 0) or getattr(map_obj, "Region", 0) or 0),
        int(getattr(account, "MapDistrict", 0) or getattr(map_obj, "District", 0) or 0),
        int(getattr(account, "MapLanguage", 0) or getattr(map_obj, "Language", 0) or 0),
    )


def _account_party_id(account: object) -> int:
    return int(
        getattr(
            getattr(account, "AgentPartyData", None),
            "PartyID",
            0,
        )
        or 0
    )


def _account_label(account: object) -> str:
    agent_data = getattr(account, "AgentData", None)
    character_name = str(getattr(agent_data, "CharacterName", "") or "").strip()
    if character_name:
        return character_name
    return str(getattr(account, "AccountEmail", "") or "Unknown account")


def farm_party_accounts() -> list[tuple[str, str]]:
    """
    Resolve the accounts belonging to the current farming party.

    PartyID is preferred. During the short periods where PartyID is not
    populated, the current map instance is used as a fallback.
    """
    local_email = str(Player.GetAccountEmail() or "").strip()
    if not local_email:
        return []

    try:
        local_account = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(local_email)
    except Exception:
        local_account = None

    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False)
    except TypeError:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception:
        accounts = []

    local_party_id = _account_party_id(local_account) if local_account is not None else 0
    local_map = _account_map_tuple(local_account) if local_account is not None else None

    result: list[tuple[str, str]] = []
    seen: set[str] = set()

    for account in accounts or []:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue

        same_party = (
            local_party_id > 0
            and _account_party_id(account) == local_party_id
        )
        same_map_fallback = (
            local_party_id <= 0
            and local_map is not None
            and _account_map_tuple(account) == local_map
        )

        if not same_party and not same_map_fallback:
            continue

        seen.add(email)
        result.append((email, _account_label(account)))

    if local_email not in seen:
        local_name = str(Player.GetName() or "").strip()
        result.append((local_email, local_name or local_email))

    return result


def check_target_item_count(
    *,
    farm: FarmDefinition,
    target_getter: Callable[[], int],
    result_callback: Callable[[int, dict[str, int], dict[str, str]], None],
    stop_callback: Callable[[], None],
) -> BehaviorTree:
    """
    Count the selected Nicholas item across the whole farming party.

    The local inventory is read directly. Followers are queried through
    SharedCommandType.InventoryQuery. The target is collective, not per-account.
    """
    state: dict[str, object] = {
        "initialized": False,
        "local_email": "",
        "targets": [],
        "index": 0,
        "waiting": False,
        "request_started_at": 0.0,
        "counts": {},
        "labels": {},
    }

    def _reset_state() -> None:
        state["initialized"] = False
        state["local_email"] = ""
        state["targets"] = []
        state["index"] = 0
        state["waiting"] = False
        state["request_started_at"] = 0.0
        state["counts"] = {}
        state["labels"] = {}

    def _finish() -> BehaviorTree.NodeState:
        counts = {
            str(email): int(count)
            for email, count in dict(state["counts"]).items()
        }
        labels = {
            str(email): str(label)
            for email, label in dict(state["labels"]).items()
        }

        total = sum(counts.values())
        target = max(1, int(target_getter()))
        result_callback(total, counts, labels)

        details = " | ".join(
            f"{labels.get(email, email)}={count}"
            for email, count in counts.items()
        )
        PySystem.Console.Log(
            MODULE_NAME,
            (
                f"{farm.name}: {total}/{target}"
                + (f" | {details}" if details else "")
            ),
            PySystem.Console.MessageType.Info,
        )

        if total >= target:
            global _TARGET_REACHED_FARM_KEY

            _TARGET_REACHED_FARM_KEY = str(farm.key)
            PySystem.Console.Log(
                MODULE_NAME,
                (
                    f"Target reached for {farm.name}: {total}/{target}. "
                    "Returning the multibox party to the starting outpost before stopping."
                ),
                PySystem.Console.MessageType.Success,
            )

        _reset_state()
        return BehaviorTree.NodeState.SUCCESS

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        local_email = str(Player.GetAccountEmail() or "").strip()
        if not local_email:
            return BehaviorTree.NodeState.RUNNING

        if not bool(state["initialized"]):
            targets = farm_party_accounts()
            if not targets:
                return BehaviorTree.NodeState.RUNNING

            state["initialized"] = True
            state["local_email"] = local_email
            state["targets"] = targets
            state["index"] = 0
            state["waiting"] = False
            state["counts"] = {}
            state["labels"] = {
                email: label
                for email, label in targets
            }

        targets = list(state["targets"])
        index = int(state["index"])

        if index >= len(targets):
            return _finish()

        email, _label = targets[index]
        email = str(email)
        model_id = int(farm.model_id)

        if email == local_email:
            try:
                count = int(GLOBAL_CACHE.Inventory.GetModelCount(model_id))
            except Exception:
                count = 0

            counts = dict(state["counts"])
            counts[email] = count
            state["counts"] = counts
            state["index"] = index + 1
            state["waiting"] = False
            return BehaviorTree.NodeState.RUNNING

        if not bool(state["waiting"]):
            reset_inventory_count(email, model_id, model_id)

            GLOBAL_CACHE.ShMem.SendMessage(
                local_email,
                email,
                SharedCommandType.InventoryQuery,
                (float(model_id), float(model_id), 0.0, 0.0),
                ("report_inventory_count",),
            )

            state["waiting"] = True
            state["request_started_at"] = time.monotonic()
            return BehaviorTree.NodeState.RUNNING

        count = int(get_inventory_count(email, model_id, model_id))

        if count >= 0:
            counts = dict(state["counts"])
            counts[email] = count
            state["counts"] = counts
            state["index"] = index + 1
            state["waiting"] = False
            state["request_started_at"] = 0.0
            return BehaviorTree.NodeState.RUNNING

        elapsed_ms = (
            time.monotonic()
            - float(state["request_started_at"])
        ) * 1000.0

        if elapsed_ms >= _INVENTORY_QUERY_TIMEOUT_MS:
            PySystem.Console.Log(
                MODULE_NAME,
                f"Inventory query timed out for {email}; retrying.",
                PySystem.Console.MessageType.Warning,
            )
            reset_inventory_count(email, model_id, model_id)
            state["waiting"] = False
            state["request_started_at"] = 0.0

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Check {farm.name} Total",
            action_fn=_tick,
            aftercast_ms=_INVENTORY_QUERY_POLL_MS,
        )
    )


def handle_target_reached(
    *,
    tree_getter: Callable[[], BottingTree],
    farm: FarmDefinition,
) -> BehaviorTree:
    """
    Finish the Nicholas session cleanly after the collective item target is met.

    The count step only marks the target as reached. This step then:
      - does nothing when the target is not pending;
      - if already in the configured outpost, stops directly;
      - otherwise waits for combat to settle, resigns the multibox party,
        waits for the starting outpost to load, then stops the BottingTree.

    Stopping only after the resign/map-load sequence prevents BottingTree.Stop()
    from cancelling the cleanup before /resign can be dispatched.
    """

    def _target_is_pending(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if str(_TARGET_REACHED_FARM_KEY or "") == str(farm.key):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.FAILURE

    def _stop_tree(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        global _TARGET_REACHED_FARM_KEY

        _TARGET_REACHED_FARM_KEY = ""
        try:
            tree = tree_getter()
        except Exception as exc:
            PySystem.Console.Log(
                MODULE_NAME,
                f"Could not resolve BottingTree after target cleanup: {exc}",
                PySystem.Console.MessageType.Error,
            )
            return BehaviorTree.NodeState.FAILURE

        PySystem.Console.Log(
            MODULE_NAME,
            f"{farm.name} target cleanup complete. Stopping Nicholas Manager.",
            PySystem.Console.MessageType.Success,
        )
        tree.Stop()
        return BehaviorTree.NodeState.SUCCESS

    return BT.Selector(
        name=f"Handle Target Reached - {farm.name}",
        children=[
            BT.Sequence(
                name=f"Target Reached Cleanup - {farm.name}",
                children=[
                    BehaviorTree(
                        BehaviorTree.ActionNode(
                            name=f"Target Reached Check - {farm.name}",
                            action_fn=_target_is_pending,
                            aftercast_ms=0,
                        )
                    ),
                    return_to_outpost_if_needed(farm),
                    BehaviorTree(
                        BehaviorTree.ActionNode(
                            name=f"Stop After Target Cleanup - {farm.name}",
                            action_fn=_stop_tree,
                            aftercast_ms=0,
                        )
                    ),
                ],
            ),
            BT.Succeeder(f"Target Not Reached - {farm.name}"),
        ],
    )


def farm_path(farm: FarmDefinition) -> BehaviorTree:
    return BT.VanquishNode(
        farm.farm_path,
        name=f"Farm {farm.name}",
        clear_area_radius=_range_for_farm(farm),
        pause_on_combat=True,
        flag_heroes_to_waypoint=False,
        move_tolerance=175.0,
        log=False,
    )


def return_to_outpost_if_needed(farm: FarmDefinition) -> BehaviorTree:
    """
    Finish a farm run safely.

    Some Nicholas farms naturally return to their starting outpost while
    others remain in an explorable instance. Avoid sending /resign blindly:

      - already at the configured starting outpost -> succeed immediately;
      - otherwise wait for combat to settle, resign the multibox party and
        wait for the starting outpost to load.

    This keeps natural-return farms clean while still resetting every farm
    that remains in an explorable area.
    """
    return BT.Selector(
        name="Return To Outpost",
        children=[
            BT.Sequence(
                name="Return To Outpost - Already There",
                children=[
                    BT.IsCurrentMap(
                        map_id=farm.outpost_map_id,
                        log=False,
                    ),
                    BT.Succeeder("StartingOutpostAlreadyLoaded"),
                ],
            ),
            BT.Sequence(
                name="Return To Outpost - Resign",
                children=[
                    BT.WaitUntilOutOfCombat(
                        range=Range.Earshot.value,
                        timeout_ms=60_000,
                    ),
                    BT.Wait(3_000),
                    BT.Resign(
                        wait_for_map_load=True,
                        target_map_id=farm.outpost_map_id,
                        multi_account=True,
                        timeout_ms=60_000,
                        log=True,
                    ),
                    BT.Wait(3_000),
                ],
            ),
        ],
    )


def reset_portal_loop_with_fallback(farm: FarmDefinition) -> BehaviorTree:
    """
    Reset a portal-loop farm.

    The portal remains the normal reset method so the expensive initial transit
    path is not replayed every run. If the portal transition fails, fall back to
    a multibox resign to the starting outpost and clear the portal-ready flag so
    the next planner loop rebuilds the initial portal route correctly.
    """
    portal_reset = _map_transition_node(
        name="Reset Via Portal",
        from_map_id=farm.farm_map_id,
        target_map_id=farm.reset_map_id,
        point=farm.portal_back,
        timeout_ms=60_000,
        before_children=(
            BT.WaitUntilOutOfCombat(
                range=Range.Earshot.value,
                timeout_ms=60_000,
            ),
            BT.Wait(3_000),
        ),
        after_children=(BT.Wait(3_000),),
    )

    return BT.Selector(
        name="Reset Via Portal",
        children=[
            portal_reset,
            BT.Sequence(
                name="Reset Via Portal - Resign Fallback",
                children=[
                    return_to_outpost_if_needed(farm),
                    BT.ClearBlackboardValue(
                        _PORTAL_READY_KEY,
                        log=True,
                    ),
                ],
            ),
        ],
    )


def prepare_portal_once(farm: FarmDefinition) -> BehaviorTree:
    return BT.Selector(
        name="Prepare Farm Portal",
        children=[
            BT.HasBlackboardValue(_PORTAL_READY_KEY, log=False),
            BT.Sequence(
                name="Initial Trip To Farm Portal",
                children=[
                    BT.MoveAndExitMap(
                        farm.exit_point,
                        target_map_id=farm.reset_map_id,
                        timeout_ms=45_000,
                        log=True,
                    ),
                    BT.VanquishNode(
                        farm.transit_path,
                        name="Initial Transit To Farm Portal",
                        clear_area_radius=Range.Earshot.value,
                        pause_on_combat=True,
                        flag_heroes_to_waypoint=False,
                        move_tolerance=175.0,
                        log=True,
                    ),
                    BT.SaveBlackboardValue(
                        _PORTAL_READY_KEY,
                        True,
                        log=False,
                    ),
                ],
            ),
        ],
    )


def reset_via_portal(farm: FarmDefinition) -> BehaviorTree:
    return BT.Sequence(
        name="Reset Farm Via Portal",
        children=[
            BT.WaitUntilOutOfCombat(
                range=Range.Earshot.value,
                timeout_ms=60_000,
            ),
            BT.Wait(3_000),
            BT.MoveAndExitMap(
                farm.portal_back,
                target_map_id=farm.reset_map_id,
                timeout_ms=60_000,
                log=True,
            ),
            BT.Wait(3_000),
        ],
    )


def wait_for_agent_model(model_id: int, timeout_ms: int = 20_000) -> BehaviorTree:
    state = {"started": 0.0}

    def _check(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if state["started"] <= 0.0:
            state["started"] = time.monotonic()

        try:
            for agent_id in AgentArray.GetNPCMinipetArray():
                if (
                    Agent.IsValid(agent_id)
                    and int(Agent.GetModelID(agent_id) or 0) == int(model_id)
                ):
                    return BehaviorTree.NodeState.SUCCESS
        except Exception:
            pass

        if (time.monotonic() - state["started"]) * 1000.0 >= timeout_ms:
            state["started"] = 0.0
            return BehaviorTree.NodeState.FAILURE

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name=f"Wait For Agent Model {model_id}",
            action_fn=_check,
            aftercast_ms=250,
        )
    )


def enter_fow(farm: FarmDefinition) -> BehaviorTree:
    return BT.Sequence(
        name="Enter Fissure Of Woe",
        children=[
            BT.Move(
                farm.balthazar_approach,
                pause_on_combat=False,
                flag_heroes_to_waypoint=False,
                log=False,
            ),
            BT.SendChatCommand("kneel", log=True),
            wait_for_agent_model(farm.balthazar_champion_model_id),
            BT.TargetAgentByModelIDAndSendDialog(
                farm.balthazar_champion_model_id,
                dialog_id=0x85,
                log=True,
                multi_account=False,
            ),
            BT.Wait(500),
            BT.SendDialog(
                dialog_id=0x86,
                log=True,
                multi_account=False,
            ),
            BT.WaitForMapLoad(
                map_id=farm.farm_map_id,
                timeout_ms=45_000,
            ),
        ],
    )




def _message_ref_is_active(
    sender_email: str,
    receiver_email: str,
    message_index: int,
    command: SharedCommandType,
) -> bool:
    if int(message_index) < 0:
        return False

    try:
        message = GLOBAL_CACHE.ShMem.GetInbox(int(message_index))
    except Exception:
        return False

    return bool(
        getattr(message, "Active", False)
        and str(getattr(message, "ReceiverEmail", "") or "") == str(receiver_email or "")
        and str(getattr(message, "SenderEmail", "") or "") == str(sender_email or "")
        and int(getattr(message, "Command", -1)) == int(command.value)
    )


def interact_current_target_all_accounts(
    *,
    timeout_ms: int = 10_000,
) -> BehaviorTree:
    """
    Interact with the leader's current target on every active multibox client.

    Agent IDs are shared by clients in the same map instance. The interaction
    itself is executed by Messaging on each client so HeroAI is suspended and
    restored locally around the NPC interaction.
    """
    state: dict[str, object] = {
        "sent": False,
        "sender": "",
        "refs": [],
        "started_at": 0.0,
    }

    def _reset() -> None:
        state["sent"] = False
        state["sender"] = ""
        state["refs"] = []
        state["started_at"] = 0.0

    def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if not bool(state["sent"]):
            sender_email = str(Player.GetAccountEmail() or "").strip()
            target_id = int(Player.GetTargetID() or 0)

            if not sender_email or target_id <= 0:
                _reset()
                return BehaviorTree.NodeState.FAILURE

            try:
                accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False)
            except TypeError:
                accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
            except Exception:
                accounts = []

            refs: list[tuple[str, int]] = []
            seen: set[str] = set()

            for account in accounts or []:
                receiver_email = str(
                    getattr(account, "AccountEmail", "") or ""
                ).strip()

                if not receiver_email or receiver_email in seen:
                    continue

                seen.add(receiver_email)

                message_index = int(
                    GLOBAL_CACHE.ShMem.SendMessage(
                        sender_email,
                        receiver_email,
                        SharedCommandType.InteractWithTarget,
                        (float(target_id), 0.0, 0.0, 0.0),
                        ("Nicholas collector", "", "", ""),
                    )
                )
                refs.append((receiver_email, message_index))

            if sender_email not in seen:
                message_index = int(
                    GLOBAL_CACHE.ShMem.SendMessage(
                        sender_email,
                        sender_email,
                        SharedCommandType.InteractWithTarget,
                        (float(target_id), 0.0, 0.0, 0.0),
                        ("Nicholas collector", "", "", ""),
                    )
                )
                refs.append((sender_email, message_index))

            state["sent"] = True
            state["sender"] = sender_email
            state["refs"] = refs
            state["started_at"] = time.monotonic()
            return BehaviorTree.NodeState.RUNNING

        sender_email = str(state["sender"])
        refs = list(state["refs"])

        active = any(
            _message_ref_is_active(
                sender_email,
                receiver_email,
                message_index,
                SharedCommandType.InteractWithTarget,
            )
            for receiver_email, message_index in refs
        )

        if not active:
            _reset()
            return BehaviorTree.NodeState.SUCCESS

        elapsed_ms = (
            time.monotonic() - float(state["started_at"])
        ) * 1000.0

        if elapsed_ms >= max(0, int(timeout_ms)):
            PySystem.Console.Log(
                MODULE_NAME,
                "Timed out while opening the collector on all accounts.",
                PySystem.Console.MessageType.Warning,
            )
            _reset()
            return BehaviorTree.NodeState.FAILURE

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name="Interact Collector All Accounts",
            action_fn=_tick,
            aftercast_ms=100,
        )
    )


def exchange_collector_all_accounts(
    farm: FarmDefinition,
) -> BehaviorTree:
    """
    Ask Messaging on every client to perform its own local collector trades.

    The collector window must already be open on each account.
    Each client stops once it owns collector_target_count output items or can
    no longer pay the exchange rate.
    """
    return BTShared.SendAndWait(
        command=SharedCommandType.CollectorExchange,
        params=(
            float(farm.collector_item_model_id),
            float(farm.model_id),
            float(farm.collector_exchange_rate),
            float(farm.collector_target_count),
        ),
        extra_data=(
            farm.name,
            farm.collector_item_name,
            "",
            "",
        ),
        include_self=True,
        refs_blackboard_key="__nicholas_collector_exchange_refs",
        timeout_ms=30_000,
        poll_interval_ms=100,
        log=True,
        aftercast_ms=100,
    )


def build_collector_conversion(
    farm: FarmDefinition,
    *,
    include_town_travel: bool,
) -> BehaviorTree:
    """
    Build the shared conversion step for one collector-backed Nicholas farm.
    """
    if not farm.requires_collector_conversion:
        return BT.Succeeder(name="NoCollectorConversion")

    if farm.collector_mode == "manual":
        return BT.LogMessage(
            message=(
                f"{farm.name} requires {farm.collector_item_name}, but the "
                "BubbleTea AutoIt source does not provide a reliable automated "
                "route to this collector. Convert the items manually first."
            ),
            module_name=MODULE_NAME,
        )

    if farm.collector_mode not in ("town", "inline"):
        return BT.LogMessage(
            message=f"Unsupported collector mode for {farm.name}: {farm.collector_mode}",
            module_name=MODULE_NAME,
        )

    if farm.collector_position is None:
        return BT.LogMessage(
            message=f"Collector position is missing for {farm.name}.",
            module_name=MODULE_NAME,
        )

    children: list[BehaviorTree | BehaviorTree.Node] = []

    if include_town_travel and farm.collector_mode == "town":
        children.extend(
            [
                BT.Travel(
                    target_map_id=farm.collector_town_map_id,
                    random_travel=False,
                    log=True,
                ),
                BT.SetHardMode(
                    hard_mode=False,
                    log=False,
                ),
            ]
        )

        if farm.collector_route:
            children.append(
                BT.Move(
                    farm.collector_route,
                    pause_on_combat=False,
                    flag_heroes_to_waypoint=False,
                    log=False,
                )
            )

    children.extend(
        [
            BT.TargetNearest(
                farm.collector_position[0],
                farm.collector_position[1],
                target_distance=1320.0,
                log=True,
            ),
            interact_current_target_all_accounts(),
            BT.Wait(1_000),
            exchange_collector_all_accounts(farm),
            BT.Wait(750),
        ]
    )

    return BT.Sequence(
        name=f"Convert {farm.name} To {farm.collector_item_name}",
        children=children,
    )




def _map_guarded_node(
    *,
    name: str,
    map_id: int,
    child: BehaviorTree,
    skip_if_in_maps: tuple[int, ...] = (),
) -> BehaviorTree:
    """
    Shards-of-Orr style map guard.

    Run the child only on its expected map. If a later map is already loaded,
    treat the step as already passed. This is important around portals: a
    movement point close to a portal can zone before the planner advances.
    """
    branches: list[BehaviorTree] = [
        BT.Sequence(
            name=f"{name} - Active Map",
            children=[
                BT.IsCurrentMap(map_id=int(map_id), log=False),
                child,
            ],
        )
    ]

    seen: set[int] = {int(map_id)}
    for later_map_id in skip_if_in_maps:
        later_map_id = int(later_map_id)
        if later_map_id <= 0 or later_map_id in seen:
            continue
        seen.add(later_map_id)

        branches.append(
            BT.Sequence(
                name=f"{name} - Later Map {later_map_id}",
                children=[
                    BT.IsCurrentMap(map_id=later_map_id, log=False),
                    BT.Succeeder(f"{name}AlreadyPassed"),
                ],
            )
        )

    if len(branches) == 1:
        return branches[0]

    return BT.Selector(
        name=name,
        children=branches,
    )


def _blackboard_guarded_node(
    *,
    name: str,
    blackboard_key: str,
    child: BehaviorTree,
) -> BehaviorTree:
    """Skip a one-time planner step once its blackboard flag is set."""
    return BT.Selector(
        name=name,
        children=[
            BT.HasBlackboardValue(blackboard_key, log=False),
            child,
        ],
    )


def _movement_point_steps(
    prefix: str,
    map_id: int,
    points: tuple[tuple[float, float], ...] | list[tuple[float, float]],
    *,
    pause_on_combat: bool,
    tolerance: float = 175.0,
    flag_heroes_to_waypoint: bool = False,
    skip_if_in_maps: tuple[int, ...] = (),
    blackboard_skip_key: str = "",
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Create one planner step per movement waypoint."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"

        def _build(
            point=point,
            name=name,
        ) -> BehaviorTree:
            node = _map_guarded_node(
                name=name,
                map_id=int(map_id),
                child=BT.Move(
                    point,
                    pause_on_combat=pause_on_combat,
                    tolerance=tolerance,
                    flag_heroes_to_waypoint=flag_heroes_to_waypoint,
                    log=False,
                ),
                skip_if_in_maps=tuple(skip_if_in_maps),
            )

            if blackboard_skip_key:
                node = _blackboard_guarded_node(
                    name=name,
                    blackboard_key=blackboard_skip_key,
                    child=node,
                )

            return node

        steps.append((name, _build))

    return steps


def _vanquish_point_steps(
    prefix: str,
    map_id: int,
    points: tuple[tuple[float, float], ...] | list[tuple[float, float]],
    *,
    clear_area_radius: float,
    pause_on_combat: bool = True,
    flag_heroes_to_waypoint: bool = False,
    move_tolerance: float = 175.0,
    skip_if_in_maps: tuple[int, ...] = (),
    blackboard_skip_key: str = "",
    loot_farm: FarmDefinition | None = None,
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Create one planner step per combat/farm waypoint."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"

        def _build(
            point=point,
            name=name,
        ) -> BehaviorTree:
            farm_node = BT.VanquishNode(
                [point],
                name=name,
                clear_area_radius=clear_area_radius,
                pause_on_combat=pause_on_combat,
                flag_heroes_to_waypoint=flag_heroes_to_waypoint,
                move_tolerance=move_tolerance,
                log=False,
            )

            if loot_farm is not None:
                farm_node = _with_nicholas_loot_orchestrator(
                    loot_farm,
                    farm_node,
                    name=name,
                )

            node = _map_guarded_node(
                name=name,
                map_id=int(map_id),
                child=farm_node,
                skip_if_in_maps=tuple(skip_if_in_maps),
            )

            if blackboard_skip_key:
                node = _blackboard_guarded_node(
                    name=name,
                    blackboard_key=blackboard_skip_key,
                    child=node,
                )

            return node

        steps.append((name, _build))

    return steps


def _map_transition_node(
    *,
    name: str,
    from_map_id: int,
    target_map_id: int,
    point: tuple[float, float],
    timeout_ms: int,
    skip_if_in_maps: tuple[int, ...] = (),
    blackboard_skip_key: str = "",
    before_children: tuple[BehaviorTree, ...] = (),
    after_children: tuple[BehaviorTree, ...] = (),
) -> BehaviorTree:
    """
    Map-aware transition step.

    If the destination (or a later map) is already loaded when this planner
    step is retried, the transition is accepted as already completed.
    """
    branches: list[BehaviorTree] = []

    accepted_maps: list[int] = [int(target_map_id)]
    accepted_maps.extend(int(map_id) for map_id in skip_if_in_maps)

    seen: set[int] = set()
    for accepted_map_id in accepted_maps:
        if accepted_map_id <= 0 or accepted_map_id in seen:
            continue
        seen.add(accepted_map_id)

        branches.append(
            BT.Sequence(
                name=f"{name} - Already In {accepted_map_id}",
                children=[
                    BT.IsCurrentMap(map_id=accepted_map_id, log=False),
                    BT.Succeeder(f"{name}AlreadyPassed"),
                ],
            )
        )

    transition_children: list[BehaviorTree] = [
        BT.IsCurrentMap(map_id=int(from_map_id), log=False),
    ]
    transition_children.extend(before_children)
    transition_children.append(
        BT.MoveAndExitMap(
            point,
            target_map_id=int(target_map_id),
            timeout_ms=int(timeout_ms),
            log=True,
        )
    )
    transition_children.extend(after_children)

    branches.append(
        BT.Sequence(
            name=f"{name} - Transition",
            children=transition_children,
        )
    )

    node: BehaviorTree = BT.Selector(
        name=name,
        children=branches,
    )

    if blackboard_skip_key:
        node = _blackboard_guarded_node(
            name=name,
            blackboard_key=blackboard_skip_key,
            child=node,
        )

    return node


def _travel_to_map_node(
    *,
    name: str,
    map_id: int,
) -> BehaviorTree:
    """Travel only when the requested outpost is not already loaded."""
    return BT.Selector(
        name=name,
        children=[
            BT.Sequence(
                name=f"{name} - Already There",
                children=[
                    BT.IsCurrentMap(map_id=int(map_id), log=False),
                    BT.Succeeder(f"{name}AlreadyThere"),
                ],
            ),
            BT.Travel(
                target_map_id=int(map_id),
                random_travel=False,
                log=True,
            ),
        ],
    )


def _collector_exchange_step(farm: FarmDefinition) -> BehaviorTree:
    """Collector interaction only; collector travel waypoints are planner steps."""
    if farm.collector_position is None:
        return BT.LogMessage(
            message=f"Collector position is missing for {farm.name}.",
            module_name=MODULE_NAME,
        )

    return BT.Sequence(
        name=f"Convert {farm.name} To {farm.collector_item_name}",
        children=[
            BT.TargetNearest(
                farm.collector_position[0],
                farm.collector_position[1],
                target_distance=1320.0,
                log=True,
            ),
            interact_current_target_all_accounts(),
            BT.Wait(1_000),
            exchange_collector_all_accounts(farm),
            BT.Wait(750),
        ],
    )


def _future_exchange_maps(
    actions: tuple[tuple[str, tuple[float, float], int], ...],
    action_index: int,
    current_map_id: int,
) -> tuple[int, ...]:
    """
    Return later map IDs reachable after one exchange action.

    Used by point guards so a retry does not attempt an old-map waypoint after
    the character has already crossed one or more portals.
    """
    result: list[int] = []
    seen: set[int] = {int(current_map_id)}

    for kind, _point, target_map_id in actions[action_index + 1:]:
        if kind != "exit":
            continue
        target_map_id = int(target_map_id)
        if target_map_id <= 0 or target_map_id in seen:
            continue
        seen.add(target_map_id)
        result.append(target_map_id)

    return tuple(result)




def _future_farm_route_maps(
    actions: tuple[tuple[str, int, tuple[float, float], int, int], ...],
    action_index: int,
    current_map_id: int,
) -> tuple[int, ...]:
    """Return later unique map IDs after a granular farm-route action."""
    result: list[int] = []
    seen: set[int] = {int(current_map_id)}

    for kind, expected_map_id, _point, target_map_id, _dialog_id in actions[action_index + 1:]:
        for map_id in (
            int(expected_map_id),
            int(target_map_id) if kind == "exit" else 0,
        ):
            if map_id <= 0 or map_id in seen:
                continue
            seen.add(map_id)
            result.append(map_id)

    return tuple(result)


def _route_loop_action_steps(
    farm: FarmDefinition,
    *,
    prefix: str,
    actions: tuple[tuple[str, int, tuple[float, float], int, int], ...],
    blackboard_skip_key: str = "",
    reset_fallback: bool = False,
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """
    Expand a complex source route into one planner step per action.

    Supports old AutoIt farms that cross several maps, revisit maps through
    portals, or require an NPC dialog during setup.
    """
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, action in enumerate(actions, start=1):
        kind, expected_map_id, point, target_map_id, dialog_id = action
        expected_map_id = int(expected_map_id)
        target_map_id = int(target_map_id)
        dialog_id = int(dialog_id)

        later_maps = _future_farm_route_maps(
            actions,
            index - 1,
            expected_map_id,
        )

        accepted_later_maps = tuple(
            dict.fromkeys(
                (*later_maps, farm.outpost_map_id)
                if reset_fallback
                else later_maps
            )
        )

        name = f"{prefix} - {index:02d} {kind.title()}"

        def _build(
            kind=kind,
            expected_map_id=expected_map_id,
            point=point,
            target_map_id=target_map_id,
            dialog_id=dialog_id,
            accepted_later_maps=accepted_later_maps,
            name=name,
        ) -> BehaviorTree:
            if kind == "move":
                node = _map_guarded_node(
                    name=name,
                    map_id=expected_map_id,
                    child=BT.Move(
                        point,
                        pause_on_combat=False,
                        tolerance=175.0,
                        flag_heroes_to_waypoint=False,
                        log=False,
                    ),
                    skip_if_in_maps=accepted_later_maps,
                )

            elif kind == "aggro":
                aggro_node: BehaviorTree = BT.VanquishNode(
                    [point],
                    name=name,
                    clear_area_radius=Range.Earshot.value,
                    pause_on_combat=True,
                    flag_heroes_to_waypoint=False,
                    move_tolerance=175.0,
                    log=False,
                )

                if expected_map_id == int(farm.farm_map_id):
                    aggro_node = _with_nicholas_loot_orchestrator(
                        farm,
                        aggro_node,
                        name=name,
                    )

                node = _map_guarded_node(
                    name=name,
                    map_id=expected_map_id,
                    child=aggro_node,
                    skip_if_in_maps=accepted_later_maps,
                )

            elif kind == "dialog":
                node = _map_guarded_node(
                    name=name,
                    map_id=expected_map_id,
                    child=BT.MoveAndDialog(
                        point,
                        dialog_id=dialog_id,
                        pause_on_combat=False,
                        log=True,
                        multi_account=False,
                    ),
                    skip_if_in_maps=accepted_later_maps,
                )

            elif kind == "exit":
                transition = _map_transition_node(
                    name=name,
                    from_map_id=expected_map_id,
                    target_map_id=target_map_id,
                    point=point,
                    timeout_ms=60_000,
                    skip_if_in_maps=accepted_later_maps,
                    after_children=(BT.Wait(2_000),),
                )

                if reset_fallback:
                    node = BT.Selector(
                        name=name,
                        children=[
                            transition,
                            BT.Sequence(
                                name=f"{name} - Resign Fallback",
                                children=[
                                    return_to_outpost_if_needed(farm),
                                    BT.ClearBlackboardValue(
                                        _PORTAL_READY_KEY,
                                        log=True,
                                    ),
                                ],
                            ),
                        ],
                    )
                else:
                    node = transition

            else:
                raise ValueError(
                    f"Unsupported farm route action '{kind}' for {farm.name}."
                )

            if blackboard_skip_key:
                node = _blackboard_guarded_node(
                    name=name,
                    blackboard_key=blackboard_skip_key,
                    child=node,
                )

            return node

        steps.append((name, _build))

        # Route-loop farms can leave and re-enter the farm map multiple times.
        # Every EXIT landing on the farm map gets the same lifecycle as every
        # other flow:
        #
        #   stable map -> add model -> reload follower HeroAI -> add model again
        if kind == "exit" and target_map_id == int(farm.farm_map_id):
            refresh_name = f"{prefix} - {index:02d} Refresh Runtime"
            steps.append(
                (
                    refresh_name,
                    lambda: _refresh_farm_runtime_after_entry(farm),
                )
            )

    return steps


def build_nicholas_exchange(farm: FarmDefinition) -> BehaviorTree:
    """
    Travel to Nicholas and exchange the selected weekly item on all accounts.

    The route is migrated from the legacy AutoIt Exchange script. Movement is
    kept data-driven in NicholasFarms.py; this function is shared by every farm.

    Collector conversions are not silently invented here. For farms whose
    requested Nicholas item is obtained from a collector, the UI tells the user
    that the collector conversion must be completed before this exchange route.
    """
    if not farm.exchange_available:
        return BT.LogMessage(
            message=f"No legacy Nicholas exchange route is available for {farm.name}.",
            module_name=MODULE_NAME,
        )

    children: list[BehaviorTree | BehaviorTree.Node] = [
        disable_merchant_rules_all_accounts(),
    ]

    if farm.collector_mode == "town":
        children.append(
            build_collector_conversion(
                farm,
                include_town_travel=True,
            )
        )

    if farm.collector_mode == "manual":
        children.append(
            BT.LogMessage(
                message=(
                    f"Manual collector conversion required for {farm.name} -> "
                    f"{farm.collector_item_name}. The Nicholas route will continue; "
                    "make sure each account already has the converted items."
                ),
                module_name=MODULE_NAME,
            )
        )

    children.extend(
        [
            BT.Travel(
                target_map_id=farm.exchange_town_map_id,
                random_travel=False,
                log=True,
            ),
            BT.SetHardMode(
                hard_mode=False,
                log=False,
            ),
        ]
    )

    pending_kind = ""
    pending_points: list[tuple[float, float]] = []

    def flush_pending() -> None:
        nonlocal pending_kind, pending_points

        if not pending_points:
            pending_kind = ""
            return

        points = list(pending_points)

        if pending_kind == "aggro":
            children.append(
                BT.VanquishNode(
                    points,
                    name="Route To Nicholas",
                    clear_area_radius=Range.Earshot.value,
                    pause_on_combat=True,
                    flag_heroes_to_waypoint=False,
                    move_tolerance=175.0,
                    log=False,
                )
            )
        else:
            children.append(
                BT.Move(
                    points,
                    pause_on_combat=False,
                    flag_heroes_to_waypoint=False,
                    log=False,
                )
            )

        pending_kind = ""
        pending_points = []

    for action_index, (kind, point, target_map_id) in enumerate(farm.exchange_actions):
        if kind in ("move", "aggro"):
            if pending_kind and pending_kind != kind:
                flush_pending()
            pending_kind = kind
            pending_points.append(point)

            if (
                farm.collector_mode == "inline"
                and action_index == farm.collector_insert_after
            ):
                flush_pending()
                children.append(
                    build_collector_conversion(
                        farm,
                        include_town_travel=False,
                    )
                )

            continue

        flush_pending()

        if kind == "exit":
            children.append(
                BT.MoveAndExitMap(
                    point,
                    target_map_id=int(target_map_id),
                    timeout_ms=60_000,
                    log=True,
                )
            )
            children.append(BT.Wait(3_000))
            continue

        raise ValueError(
            f"Unsupported Nicholas exchange action '{kind}' for {farm.name}."
        )

    flush_pending()

    children.extend(
        [
            BT.WaitUntilOutOfCombat(
                range=Range.Earshot.value,
                timeout_ms=60_000,
            ),
            BT.Wait(1_500),
            BT.TargetNearestAndSendDialog(
                farm.nicholas_position,
                dialog_id=0x85,
                target_distance=Range.Nearby.value,
                log=True,
                multi_account=True,
            ),
            BT.Wait(1_000),
            BT.SendDialog(
                dialog_id=0x86,
                log=True,
                multi_account=True,
            ),
            BT.Wait(1_500),
        ]
    )

    return BT.Sequence(
        name=f"Exchange {farm.nicholas_item_name} With Nicholas",
        children=children,
    )


def build_exchange_steps(
    farm: FarmDefinition,
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """
    Build the Nicholas exchange as granular planner steps.

    Every route waypoint is a separate step. Zone changes remain explicit
    MoveAndExitMap steps and every route point is guarded by the map on which it
    belongs.
    """
    if not farm.exchange_available:
        return [
            (
                "Nicholas Exchange Unavailable",
                lambda: BT.LogMessage(
                    message=f"No legacy Nicholas exchange route is available for {farm.name}.",
                    module_name=MODULE_NAME,
                ),
            ),
        ]

    steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        (
            "Disable MerchantRules",
            disable_merchant_rules_all_accounts,
        ),
    ]

    # Collector conversion before the Nicholas route.
    if farm.collector_mode == "town":
        steps.append(
            (
                "Travel To Collector",
                lambda: _travel_to_map_node(
                    name="Travel To Collector",
                    map_id=farm.collector_town_map_id,
                ),
            )
        )

        steps.extend(
            _movement_point_steps(
                "Collector Route",
                farm.collector_town_map_id,
                farm.collector_route,
                pause_on_combat=False,
                tolerance=175.0,
                flag_heroes_to_waypoint=False,
            )
        )

        steps.append(
            (
                f"Collector Exchange - {farm.collector_item_name}",
                lambda: _map_guarded_node(
                    name=f"Collector Exchange - {farm.collector_item_name}",
                    map_id=farm.collector_town_map_id,
                    child=_collector_exchange_step(farm),
                ),
            )
        )

    elif farm.collector_mode == "manual":
        steps.append(
            (
                "Manual Collector Conversion Required",
                lambda: BT.LogMessage(
                    message=(
                        f"Manual collector conversion required for {farm.name} -> "
                        f"{farm.collector_item_name}. Make sure every account already "
                        "has the converted items before continuing."
                    ),
                    module_name=MODULE_NAME,
                ),
            )
        )

    steps.append(
        (
            "Travel To Nicholas Route",
            lambda: _travel_to_map_node(
                name="Travel To Nicholas Route",
                map_id=farm.exchange_town_map_id,
            ),
        )
    )

    current_map_id = int(farm.exchange_town_map_id)
    route_point_number = 0
    zone_number = 0

    for action_index, (kind, point, target_map_id) in enumerate(farm.exchange_actions):
        later_maps = _future_exchange_maps(
            farm.exchange_actions,
            action_index,
            current_map_id,
        )

        if kind in ("move", "aggro"):
            route_point_number += 1
            name = f"Nicholas Route - Point {route_point_number:02d}"

            if kind == "aggro":
                steps.extend(
                    _vanquish_point_steps(
                        "Nicholas Route",
                        current_map_id,
                        (point,),
                        clear_area_radius=Range.Earshot.value,
                        pause_on_combat=True,
                        flag_heroes_to_waypoint=False,
                        move_tolerance=175.0,
                        skip_if_in_maps=later_maps,
                    )
                )
                # Rename the generated single-point step with global route number.
                generated_name, generated_factory = steps.pop()
                steps.append((name, generated_factory))
            else:
                steps.extend(
                    _movement_point_steps(
                        "Nicholas Route",
                        current_map_id,
                        (point,),
                        pause_on_combat=False,
                        tolerance=175.0,
                        flag_heroes_to_waypoint=False,
                        skip_if_in_maps=later_maps,
                    )
                )
                generated_name, generated_factory = steps.pop()
                steps.append((name, generated_factory))

            if (
                farm.collector_mode == "inline"
                and action_index == farm.collector_insert_after
            ):
                collector_name = f"Collector Exchange - {farm.collector_item_name}"
                collector_map_id = int(current_map_id)
                steps.append(
                    (
                        collector_name,
                        lambda collector_name=collector_name, collector_map_id=collector_map_id: _map_guarded_node(
                            name=collector_name,
                            map_id=collector_map_id,
                            child=_collector_exchange_step(farm),
                        ),
                    )
                )

            continue

        if kind == "exit":
            zone_number += 1
            from_map_id = int(current_map_id)
            next_map_id = int(target_map_id)
            name = f"Nicholas Route - Zone {zone_number:02d} ({from_map_id} -> {next_map_id})"

            steps.append(
                (
                    name,
                    lambda name=name, from_map_id=from_map_id, next_map_id=next_map_id, point=point, later_maps=later_maps: _map_transition_node(
                        name=name,
                        from_map_id=from_map_id,
                        target_map_id=next_map_id,
                        point=point,
                        timeout_ms=60_000,
                        skip_if_in_maps=later_maps,
                        after_children=(BT.Wait(3_000),),
                    ),
                )
            )

            current_map_id = next_map_id
            continue

        raise ValueError(
            f"Unsupported Nicholas exchange action '{kind}' for {farm.name}."
        )

    final_map_id = int(current_map_id)
    steps.append(
        (
            "Exchange With Nicholas",
            lambda final_map_id=final_map_id: _map_guarded_node(
                name="Exchange With Nicholas",
                map_id=final_map_id,
                child=BT.Sequence(
                    name=f"Exchange {farm.nicholas_item_name} With Nicholas",
                    children=[
                        BT.WaitUntilOutOfCombat(
                            range=Range.Earshot.value,
                            timeout_ms=60_000,
                        ),
                        BT.Wait(1_500),
                        BT.TargetNearestAndSendDialog(
                            farm.nicholas_position,
                            dialog_id=0x85,
                            target_distance=Range.Nearby.value,
                            log=True,
                            multi_account=True,
                        ),
                        BT.Wait(1_000),
                        BT.SendDialog(
                            dialog_id=0x86,
                            log=True,
                            multi_account=True,
                        ),
                        BT.Wait(1_500),
                    ],
                ),
            ),
        )
    )

    return steps


def build_execution_steps(
    *,
    tree_getter: Callable[[], BottingTree],
    farm: FarmDefinition,
    count_node_factory: Callable[[], BehaviorTree],
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """
    Build a Shards-of-Orr style granular planner.

    Every path waypoint is its own planner step. If movement fails, BottingTree
    recovery therefore retries only that waypoint instead of replaying the whole
    route.

    Zone transitions are NEVER flattened into path points. They remain explicit
    map-aware steps between the waypoint groups belonging to each map.
    """
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = [
        ("Prepare Farm", lambda: prepare_farm(tree_getter, farm)),
        ("Check Target Count", count_node_factory),
        (
            "Handle Target Reached",
            lambda: handle_target_reached(
                tree_getter=tree_getter,
                farm=farm,
            ),
        ),
    ]

    clear_radius = _range_for_farm(farm)

    if farm.flow == FLOW_DIRECT:
        steps.extend(
            _movement_point_steps(
                "Outpost Path",
                farm.outpost_map_id,
                farm.outpost_path,
                pause_on_combat=False,
                tolerance=175.0,
                flag_heroes_to_waypoint=False,
                skip_if_in_maps=(farm.farm_map_id,),
            )
        )

        steps.append(
            (
                "Go Out",
                lambda: _map_transition_node(
                    name="Go Out",
                    from_map_id=farm.outpost_map_id,
                    target_map_id=farm.farm_map_id,
                    point=farm.exit_point,
                    timeout_ms=45_000,
                ),
            )
        )
        steps.append(
            (
                "Prepare Farm Loot",
                lambda: _refresh_farm_runtime_after_entry(farm),
            )
        )

        steps.extend(
            _vanquish_point_steps(
                "Farm Path",
                farm.farm_map_id,
                farm.farm_path,
                clear_area_radius=clear_radius,
                pause_on_combat=True,
                flag_heroes_to_waypoint=False,
                move_tolerance=175.0,
                loot_farm=farm,
            )
        )

        steps.append(
            ("Return To Outpost", lambda: return_to_outpost_if_needed(farm))
        )

    elif farm.flow == FLOW_TWO_MAP:
        steps.extend(
            _movement_point_steps(
                "Outpost Path",
                farm.outpost_map_id,
                farm.outpost_path,
                pause_on_combat=False,
                tolerance=175.0,
                flag_heroes_to_waypoint=False,
                skip_if_in_maps=(farm.transit_map_id, farm.farm_map_id),
            )
        )

        steps.append(
            (
                "Go Out",
                lambda: _map_transition_node(
                    name="Go Out",
                    from_map_id=farm.outpost_map_id,
                    target_map_id=farm.transit_map_id,
                    point=farm.exit_point,
                    timeout_ms=45_000,
                    skip_if_in_maps=(farm.farm_map_id,),
                ),
            )
        )

        steps.extend(
            _vanquish_point_steps(
                "Transit Path",
                farm.transit_map_id,
                farm.transit_path,
                clear_area_radius=Range.Earshot.value,
                pause_on_combat=True,
                flag_heroes_to_waypoint=False,
                move_tolerance=175.0,
                skip_if_in_maps=(farm.farm_map_id,),
            )
        )

        steps.append(
            (
                "Enter Farm Map",
                lambda: _map_transition_node(
                    name="Enter Farm Map",
                    from_map_id=farm.transit_map_id,
                    target_map_id=farm.farm_map_id,
                    point=farm.portal_to_farm,
                    timeout_ms=60_000,
                ),
            )
        )
        steps.append(
            (
                "Prepare Farm Loot",
                lambda: _refresh_farm_runtime_after_entry(farm),
            )
        )

        steps.extend(
            _vanquish_point_steps(
                "Farm Path",
                farm.farm_map_id,
                farm.farm_path,
                clear_area_radius=clear_radius,
                pause_on_combat=True,
                flag_heroes_to_waypoint=False,
                move_tolerance=175.0,
                loot_farm=farm,
            )
        )

        steps.append(
            ("Return To Outpost", lambda: return_to_outpost_if_needed(farm))
        )

    elif farm.flow == FLOW_PORTAL_LOOP:
        # First trip only: outpost -> reset map -> long transit path.
        steps.extend(
            _movement_point_steps(
                "Prepare Farm Portal - Outpost",
                farm.outpost_map_id,
                farm.outpost_path,
                pause_on_combat=False,
                tolerance=175.0,
                flag_heroes_to_waypoint=False,
                skip_if_in_maps=(farm.reset_map_id, farm.farm_map_id),
                blackboard_skip_key=_PORTAL_READY_KEY,
            )
        )

        steps.append(
            (
                "Prepare Farm Portal - Go Out",
                lambda: _map_transition_node(
                    name="Prepare Farm Portal - Go Out",
                    from_map_id=farm.outpost_map_id,
                    target_map_id=farm.reset_map_id,
                    point=farm.exit_point,
                    timeout_ms=45_000,
                    skip_if_in_maps=(farm.farm_map_id,),
                    blackboard_skip_key=_PORTAL_READY_KEY,
                ),
            )
        )

        steps.extend(
            _vanquish_point_steps(
                "Prepare Farm Portal - Transit",
                farm.reset_map_id,
                farm.transit_path,
                clear_area_radius=Range.Earshot.value,
                pause_on_combat=True,
                flag_heroes_to_waypoint=False,
                move_tolerance=175.0,
                skip_if_in_maps=(farm.farm_map_id,),
                blackboard_skip_key=_PORTAL_READY_KEY,
            )
        )

        steps.append(
            (
                "Prepare Farm Portal - Ready",
                lambda: _blackboard_guarded_node(
                    name="Prepare Farm Portal - Ready",
                    blackboard_key=_PORTAL_READY_KEY,
                    child=BT.SaveBlackboardValue(
                        _PORTAL_READY_KEY,
                        True,
                        log=False,
                    ),
                ),
            )
        )

        # This transition is repeated on every farm loop.
        steps.append(
            (
                "Enter Farm Map",
                lambda: _map_transition_node(
                    name="Enter Farm Map",
                    from_map_id=farm.reset_map_id,
                    target_map_id=farm.farm_map_id,
                    point=farm.portal_to_farm,
                    timeout_ms=60_000,
                ),
            )
        )
        steps.append(
            (
                "Prepare Farm Loot",
                lambda: _refresh_farm_runtime_after_entry(farm),
            )
        )

        # If the final farm waypoint itself zones back through the reset portal,
        # accept those waypoint steps as already passed.
        steps.extend(
            _vanquish_point_steps(
                "Farm Path",
                farm.farm_map_id,
                farm.farm_path,
                clear_area_radius=clear_radius,
                pause_on_combat=True,
                flag_heroes_to_waypoint=False,
                move_tolerance=175.0,
                loot_farm=farm,
                skip_if_in_maps=(farm.reset_map_id,),
            )
        )

        steps.append(
            (
                "Reset Via Portal",
                lambda: reset_portal_loop_with_fallback(farm),
            )
        )

    elif farm.flow == FLOW_ROUTE_LOOP:
        steps.extend(
            _route_loop_action_steps(
                farm,
                prefix="Prepare Farm Route",
                actions=farm.setup_actions,
                blackboard_skip_key=_PORTAL_READY_KEY,
                reset_fallback=False,
            )
        )

        steps.append(
            (
                "Prepare Farm Route - Ready",
                lambda: _blackboard_guarded_node(
                    name="Prepare Farm Route - Ready",
                    blackboard_key=_PORTAL_READY_KEY,
                    child=BT.SaveBlackboardValue(
                        _PORTAL_READY_KEY,
                        True,
                        log=False,
                    ),
                ),
            )
        )

        steps.extend(
            _vanquish_point_steps(
                "Farm Path",
                farm.farm_map_id,
                farm.farm_path,
                clear_area_radius=clear_radius,
                pause_on_combat=True,
                flag_heroes_to_waypoint=False,
                move_tolerance=175.0,
                loot_farm=farm,
            )
        )


        # Sandblasted Lodestone is a portal-reset loop:
        #
        #   439 -> 443 -> 439 -> farm again
        #
        # A failed reset transition must NOT /resign the party back to Mouth of
        # Torment (440). Let the planner fail/retry the current transition step
        # instead. Other route-loop farms keep the generic resign fallback until
        # their reset semantics are reviewed individually.
        use_reset_resign_fallback = str(farm.key) != "sandblasted_lodestone"

        steps.extend(
            _route_loop_action_steps(
                farm,
                prefix="Reset Farm Route",
                actions=farm.reset_actions,
                reset_fallback=use_reset_resign_fallback,
            )
        )

    elif farm.flow == FLOW_CHALLENGE:
        steps.append(
            (
                "Enter Challenge",
                lambda: BT.Selector(
                    name="Enter Challenge",
                    children=[
                        _challenge_instance_already_loaded(farm),
                        _enter_challenge_and_wait_for_explorable(farm),
                    ],
                ),
            )
        )

        steps.append(
            (
                "Prepare Farm Loot",
                lambda: _refresh_farm_runtime_after_entry(farm),
            )
        )

        steps.extend(
            _vanquish_point_steps(
                "Farm Path",
                farm.farm_map_id,
                farm.farm_path,
                clear_area_radius=clear_radius,
                pause_on_combat=True,
                flag_heroes_to_waypoint=False,
                move_tolerance=175.0,
                loot_farm=farm,
            )
        )

        steps.append(
            ("Return To Outpost", lambda: return_to_outpost_if_needed(farm))
        )

    elif farm.flow == FLOW_DIALOG:
        steps.append(
            (
                "Enter Farm By Dialog",
                lambda: BT.Selector(
                    name="Enter Farm By Dialog",
                    children=[
                        BT.Sequence(
                            name="Enter Farm By Dialog - Already Loaded",
                            children=[
                                BT.IsCurrentMap(
                                    map_id=farm.farm_map_id,
                                    log=False,
                                ),
                                BT.Succeeder("DialogFarmAlreadyLoaded"),
                            ],
                        ),
                        BT.Sequence(
                            name="Enter Farm By Dialog - Active",
                            children=[
                                BT.IsCurrentMap(
                                    map_id=farm.outpost_map_id,
                                    log=False,
                                ),
                                BT.MoveAndDialog(
                                    farm.entry_position,
                                    dialog_id=farm.entry_dialog,
                                    pause_on_combat=False,
                                    log=True,
                                    multi_account=False,
                                ),
                                BT.WaitForMapLoad(
                                    map_id=farm.farm_map_id,
                                    timeout_ms=45_000,
                                ),
                            ],
                        ),
                    ],
                ),
            )
        )

        steps.append(
            (
                "Prepare Farm Loot",
                lambda: _refresh_farm_runtime_after_entry(farm),
            )
        )

        steps.extend(
            _vanquish_point_steps(
                "Farm Path",
                farm.farm_map_id,
                farm.farm_path,
                clear_area_radius=clear_radius,
                pause_on_combat=True,
                flag_heroes_to_waypoint=False,
                move_tolerance=175.0,
                loot_farm=farm,
            )
        )

        steps.append(
            ("Return To Outpost", lambda: return_to_outpost_if_needed(farm))
        )

    elif farm.flow == FLOW_FOW:
        # Split the approach path before the actual /kneel + dialogs + zoning.
        steps.extend(
            _movement_point_steps(
                "Fissure Of Woe Approach",
                farm.outpost_map_id,
                farm.balthazar_approach,
                pause_on_combat=False,
                tolerance=175.0,
                flag_heroes_to_waypoint=False,
                skip_if_in_maps=(farm.farm_map_id,),
            )
        )

        steps.append(
            (
                "Enter Fissure Of Woe",
                lambda: BT.Selector(
                    name="Enter Fissure Of Woe",
                    children=[
                        BT.Sequence(
                            name="Enter Fissure Of Woe - Already Loaded",
                            children=[
                                BT.IsCurrentMap(
                                    map_id=farm.farm_map_id,
                                    log=False,
                                ),
                                BT.Succeeder("FoWAlreadyLoaded"),
                            ],
                        ),
                        BT.Sequence(
                            name="Enter Fissure Of Woe - Active",
                            children=[
                                BT.IsCurrentMap(
                                    map_id=farm.outpost_map_id,
                                    log=False,
                                ),
                                BT.SendChatCommand("kneel", log=True),
                                wait_for_agent_model(
                                    farm.balthazar_champion_model_id
                                ),
                                BT.TargetAgentByModelIDAndSendDialog(
                                    farm.balthazar_champion_model_id,
                                    dialog_id=0x85,
                                    log=True,
                                    multi_account=False,
                                ),
                                BT.Wait(500),
                                BT.SendDialog(
                                    dialog_id=0x86,
                                    log=True,
                                    multi_account=False,
                                ),
                                BT.WaitForMapLoad(
                                    map_id=farm.farm_map_id,
                                    timeout_ms=45_000,
                                ),
                            ],
                        ),
                    ],
                ),
            )
        )

        steps.append(
            (
                "Prepare Farm Loot",
                lambda: _refresh_farm_runtime_after_entry(farm),
            )
        )

        steps.extend(
            _vanquish_point_steps(
                "Farm Path",
                farm.farm_map_id,
                farm.farm_path,
                clear_area_radius=clear_radius,
                pause_on_combat=True,
                flag_heroes_to_waypoint=False,
                move_tolerance=175.0,
                loot_farm=farm,
            )
        )

        steps.append(
            ("Return To Outpost", lambda: return_to_outpost_if_needed(farm))
        )

    else:
        raise ValueError(f"Unsupported Nicholas farm flow: {farm.flow}")

    return steps

