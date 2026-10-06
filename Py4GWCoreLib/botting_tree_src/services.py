import time
from typing import Callable, Sequence

from .. import Py4GW
from ..GlobalCache import GLOBAL_CACHE
from ..Routines import Routines
from ..py4gwcorelib_src.BehaviorTree import BehaviorTree
import PySystem

class BottingTreeServicesMixin:
    @staticmethod
    def SummoningStonePartyServiceTree(
        enabled: bool | Callable[[], bool] = True,
        map_ids: Sequence[int] | None = None,
        initial_grace_ms: float = 3000.0,
        attempt_interval_ms: float = 5000.0,
        retry_cycle_delay_ms: float = 15000.0,
        log: bool = True,
    ) -> BehaviorTree:
        """Keep one summoning-stone ally active for a multibox party.

        The service does not choose an item itself. It asks active accounts in the
        local party, one at a time, through ``SharedCommandType.UseSummoningStone``.
        The receiver-side Messaging handler owns inventory priority, Summoning
        Sickness checks and the final item use. Once an active summon is observed,
        requests stop; if that summon disappears, a new account-by-account cycle
        begins.
        """
        state: dict[str, object] = {
            "map_id": 0,
            "map_entered_ms": 0.0,
            "saw_active_summon": False,
            "recovering": False,
            "targets": [],
            "target_index": 0,
            "next_attempt_ms": 0.0,
        }
        allowed_maps = {int(map_id) for map_id in (map_ids or ()) if int(map_id) > 0}

        def _log(message: str, message_type=PySystem.Console.MessageType.Info) -> None:
            if not log:
                return
            PySystem.Console.Log(
                "SummoningStonePartyService",
                message,
                message_type,
            )

        def _enabled() -> bool:
            try:
                return bool(enabled() if callable(enabled) else enabled)
            except Exception:
                return False

        def _reset_for_map(map_id: int) -> None:
            state["map_id"] = int(map_id)
            state["map_entered_ms"] = time.monotonic() * 1000.0
            state["saw_active_summon"] = False
            state["recovering"] = False
            state["targets"] = []
            state["target_index"] = 0
            state["next_attempt_ms"] = 0.0

        def _reset_disabled() -> None:
            state["map_id"] = 0
            state["map_entered_ms"] = 0.0
            state["saw_active_summon"] = False
            state["recovering"] = False
            state["targets"] = []
            state["target_index"] = 0
            state["next_attempt_ms"] = 0.0

        def _party_id(account: object) -> int:
            try:
                return int(getattr(getattr(account, "AgentPartyData", None), "PartyID", 0) or 0)
            except Exception:
                return 0

        def _map_tuple(account: object) -> tuple[int, int, int, int]:
            map_obj = getattr(getattr(account, "AgentData", None), "Map", None)
            return (
                int(getattr(account, "MapID", 0) or getattr(map_obj, "MapID", 0) or 0),
                int(getattr(account, "MapRegion", 0) or getattr(map_obj, "Region", 0) or 0),
                int(getattr(account, "MapDistrict", 0) or getattr(map_obj, "District", 0) or 0),
                int(getattr(account, "MapLanguage", 0) or getattr(map_obj, "Language", 0) or 0),
            )

        def _label(account: object, email: str) -> str:
            try:
                name = str(getattr(getattr(account, "AgentData", None), "CharacterName", "") or "").strip()
                if name:
                    return name
            except Exception:
                pass
            return email

        def _refresh_targets() -> list[tuple[str, str]]:
            from ..Player import Player

            sender_email = str(Player.GetAccountEmail() or "").strip()
            if not sender_email:
                state["targets"] = []
                return []

            try:
                local_account = GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(sender_email)
            except Exception:
                local_account = None
            local_party_id = _party_id(local_account) if local_account is not None else 0
            local_map = _map_tuple(local_account) if local_account is not None else None

            try:
                accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False) or [])
            except TypeError:
                accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData() or [])
            except Exception:
                accounts = []

            targets: list[tuple[str, str]] = []
            seen: set[str] = set()
            for account in accounts:
                email = str(getattr(account, "AccountEmail", "") or "").strip()
                if not email or email in seen:
                    continue
                if bool(getattr(account, "IsHero", False)) or bool(getattr(account, "IsNPC", False)):
                    continue
                if hasattr(account, "IsSlotActive") and not bool(getattr(account, "IsSlotActive", False)):
                    continue

                account_party_id = _party_id(account)
                same_party = local_party_id > 0 and account_party_id == local_party_id
                same_map_fallback = (
                    local_party_id <= 0
                    and local_map is not None
                    and _map_tuple(account) == local_map
                )
                if not same_party and not same_map_fallback:
                    continue

                seen.add(email)
                targets.append((email, _label(account, email)))

            if sender_email not in seen:
                targets.insert(0, (sender_email, str(Player.GetName() or sender_email)))
            else:
                targets.sort(key=lambda entry: 0 if entry[0] == sender_email else 1)

            state["targets"] = targets
            return targets

        def _tick(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
            from ..Agent import Agent
            from ..Item import has_active_party_summon
            from ..Map import Map
            from ..Player import Player
            from ..enums import SharedCommandType

            if not _enabled():
                if int(state["map_id"] or 0) != 0:
                    _reset_disabled()
                return BehaviorTree.NodeState.RUNNING

            if Map.IsMapLoading() or not Map.IsMapReady() or not Map.IsExplorable():
                return BehaviorTree.NodeState.RUNNING
            if not GLOBAL_CACHE.Party.IsPartyLoaded():
                return BehaviorTree.NodeState.RUNNING

            map_id = int(Map.GetMapID() or 0)
            if allowed_maps and map_id not in allowed_maps:
                return BehaviorTree.NodeState.RUNNING
            if map_id != int(state["map_id"] or 0):
                _reset_for_map(map_id)
                _log(
                    f"Map {map_id}: summon watcher active; first check after {max(0.0, float(initial_grace_ms)) / 1000.0:.1f}s."
                )
                return BehaviorTree.NodeState.RUNNING

            player_id = int(Player.GetAgentID() or 0)
            if player_id <= 0 or not Agent.IsValid(player_id) or Agent.IsDead(player_id):
                return BehaviorTree.NodeState.RUNNING
            if Routines.Checks.Party.IsPartyWiped():
                return BehaviorTree.NodeState.RUNNING

            try:
                summon_alive = bool(has_active_party_summon())
            except Exception:
                summon_alive = False

            if summon_alive:
                if bool(state["recovering"]):
                    _log("Summoned ally detected; request cycle stopped.", PySystem.Console.MessageType.Success)
                elif not bool(state["saw_active_summon"]):
                    _log("Summoned ally observed; replacement monitoring armed.")
                state["saw_active_summon"] = True
                state["recovering"] = False
                state["targets"] = []
                state["target_index"] = 0
                state["next_attempt_ms"] = 0.0
                return BehaviorTree.NodeState.RUNNING

            now_ms = time.monotonic() * 1000.0
            initial_missing = not bool(state["saw_active_summon"])
            if initial_missing and now_ms - float(state["map_entered_ms"] or 0.0) < max(0.0, float(initial_grace_ms)):
                return BehaviorTree.NodeState.RUNNING

            if not bool(state["recovering"]):
                state["recovering"] = True
                state["target_index"] = 0
                state["next_attempt_ms"] = now_ms
                _refresh_targets()
                _log(
                    "No summon observed; trying party accounts one by one."
                    if initial_missing
                    else "Active summon disappeared; trying a replacement account by account.",
                    PySystem.Console.MessageType.Warning,
                )

            if now_ms < float(state["next_attempt_ms"] or 0.0):
                return BehaviorTree.NodeState.RUNNING

            targets: list[tuple[str, str]] = list(state["targets"] or [])
            if not targets:
                targets = _refresh_targets()
                if not targets:
                    state["next_attempt_ms"] = now_ms + max(250.0, float(retry_cycle_delay_ms))
                    return BehaviorTree.NodeState.RUNNING

            target_index = int(state["target_index"] or 0)
            if target_index >= len(targets):
                state["target_index"] = 0
                state["targets"] = _refresh_targets()
                state["next_attempt_ms"] = now_ms + max(250.0, float(retry_cycle_delay_ms))
                _log(
                    f"No summon detected after trying {len(targets)} account(s); retrying in {max(250.0, float(retry_cycle_delay_ms)) / 1000.0:.1f}s.",
                    PySystem.Console.MessageType.Warning,
                )
                return BehaviorTree.NodeState.RUNNING

            sender_email = str(Player.GetAccountEmail() or "").strip()
            if not sender_email:
                state["next_attempt_ms"] = now_ms + max(250.0, float(attempt_interval_ms))
                return BehaviorTree.NodeState.RUNNING

            receiver_email, label = targets[target_index]
            state["target_index"] = target_index + 1
            state["next_attempt_ms"] = now_ms + max(250.0, float(attempt_interval_ms))
            try:
                GLOBAL_CACHE.ShMem.SendMessage(
                    sender_email,
                    receiver_email,
                    SharedCommandType.UseSummoningStone,
                    (0.0, 0.0, 0.0, 0.0),
                )
                _log(
                    f"Asking {label} to try a summoning stone ({target_index + 1}/{len(targets)})."
                )
            except Exception as exc:
                _log(
                    f"Summoning-stone request failed for {label}: {exc}",
                    PySystem.Console.MessageType.Warning,
                )

            return BehaviorTree.NodeState.RUNNING

        return BehaviorTree(
            BehaviorTree.ActionNode(
                name="SummoningStonePartyService",
                action_fn=_tick,
                aftercast_ms=250,
            )
        )

    @staticmethod
    def PartyWipeRecoveryServiceTree(
        default_step_name: str | Callable[[], str | None] | None = None,
        return_interval_ms: float = 1000.0,
    ) -> BehaviorTree:
        """
        Recover the planner after a party wipe.

        Two distinct recovery scenarios are supported:

        1. Recoverable wipe:
           - the party dies in an explorable area;
           - the player is revived at a shrine;
           - the current named planner step is restarted in the same instance.

        2. Party defeated:
           - the party can no longer revive normally;
           - the game returns, or is instructed to return, to the outpost;
           - the current named planner step is restarted from the outpost.
        """
        state = {
            "active": False,
            "mode": "",
            "step_name": "",
            "last_return_ms": 0.0,
            "player_was_dead": False,
            "player_dead_pos": None,
        }

        def _log(
            message: str,
            message_type=PySystem.Console.MessageType.Info,
        ) -> None:
            PySystem.Console.Log(
                "PartyWipeRecoveryService",
                message,
                message_type,
            )

        def _resolve_default_step_name() -> str:
            if callable(default_step_name):
                try:
                    resolved = default_step_name()
                except Exception:
                    resolved = None
            else:
                resolved = default_step_name

            return str(resolved or "")

        def _resolve_recovery_step(
            node: BehaviorTree.Node,
        ) -> str:
            current_step_name = str(
                node.blackboard.get(
                    "current_step_name",
                    "",
                )
                or ""
            )

            last_active_step_name = str(
                node.blackboard.get(
                    "last_active_planner_step_name",
                    "",
                )
                or ""
            )

            named_step_names = {
                str(name)
                for name in (
                    node.blackboard.get(
                        "named_planner_step_names",
                        [],
                    )
                    or []
                )
            }

            if (
                current_step_name
                and (
                    not named_step_names
                    or current_step_name
                    in named_step_names
                )
            ):
                return current_step_name

            if (
                last_active_step_name
                and (
                    not named_step_names
                    or last_active_step_name
                    in named_step_names
                )
            ):
                return last_active_step_name

            return _resolve_default_step_name()

        def _reset_state(
            node: BehaviorTree.Node,
        ) -> None:
            state["active"] = False
            state["mode"] = ""
            state["step_name"] = ""
            state["last_return_ms"] = 0.0
            state["player_was_dead"] = False
            state["player_dead_pos"] = None

            node.blackboard[
                "party_wipe_recovery_active"
            ] = False

            node.blackboard[
                "party_wipe_recovery_mode"
            ] = ""

            node.blackboard[
                "party_wipe_recovery_step_name"
            ] = ""

        def _request_step_restart(
            node: BehaviorTree.Node,
        ) -> bool:
            step_name = str(
                state["step_name"]
                or _resolve_default_step_name()
            )

            if not step_name:
                _log(
                    (
                        "Recovery completed, but no named planner "
                        "step could be resolved."
                    ),
                    PySystem.Console.MessageType.Warning,
                )
                return False

            node.blackboard[
                "restart_step_name_request"
            ] = step_name

            return True

        def _detect_revive_teleport() -> bool:
            """
            Detect a transition from the death location to a distant shrine.

            It handles both:
            - the dead agent being teleported before becoming alive;
            - the player becoming alive at a position far from the death point.
            """
            from ..Agent import Agent
            from ..Player import Player
            from ..enums_src.GameData_enums import Range
            from ..py4gwcorelib_src.Utils import Utils

            player_id = Player.GetAgentID()

            if not Agent.IsValid(player_id):
                return False

            current_pos = Agent.GetXY(
                player_id
            )
            is_dead = bool(
                Agent.IsDead(player_id)
            )

            if is_dead:
                if not state["player_was_dead"]:
                    state["player_was_dead"] = True
                    state["player_dead_pos"] = current_pos
                    return False

                death_pos = state[
                    "player_dead_pos"
                ]

                if (
                    death_pos
                    and Utils.Distance(
                        death_pos,
                        current_pos,
                    )
                    > Range.Spellcast.value
                ):
                    # Some revive flows teleport the dead agent first.
                    state["player_was_dead"] = False
                    state["player_dead_pos"] = None
                    return True

                return False

            if not state["player_was_dead"]:
                return False

            state["player_was_dead"] = False

            death_pos = state[
                "player_dead_pos"
            ]
            state["player_dead_pos"] = None

            if not death_pos:
                return False

            return (
                Utils.Distance(
                    death_pos,
                    current_pos,
                )
                > Range.Spellcast.value
            )

        def _player_is_alive() -> bool:
            from ..Agent import Agent
            from ..Player import Player

            player_id = Player.GetAgentID()

            return bool(
                Agent.IsValid(player_id)
                and not Agent.IsDead(player_id)
            )

        def _can_resume_in_explorable() -> bool:
            from ..Map import Map

            return bool(
                Map.IsMapReady()
                and Map.IsExplorable()
                and GLOBAL_CACHE.Party.IsPartyLoaded()
                and _player_is_alive()
            )

        def _can_resume_from_outpost() -> bool:
            from ..Map import Map

            return bool(
                Map.IsMapReady()
                and Map.IsOutpost()
                and GLOBAL_CACHE.Party.IsPartyLoaded()
            )

        def _begin_recovery(
            node: BehaviorTree.Node,
            mode: str,
        ) -> None:
            from ..py4gwcorelib_src.ActionQueue import (
                ActionQueueManager,
            )

            step_name = _resolve_recovery_step(
                node
            )

            state["active"] = True
            state["mode"] = mode
            state["step_name"] = step_name
            state["last_return_ms"] = 0.0

            node.blackboard[
                "party_wipe_recovery_active"
            ] = True

            node.blackboard[
                "party_wipe_recovery_mode"
            ] = mode

            node.blackboard[
                "party_wipe_recovery_step_name"
            ] = step_name

            ActionQueueManager().ResetAllQueues()

            if mode == "defeated":
                _log(
                    (
                        "Party defeated. Waiting for the outpost "
                        f"before restarting step '{step_name}'."
                    ),
                    PySystem.Console.MessageType.Warning,
                )
            else:
                _log(
                    (
                        "Recoverable party wipe detected. "
                        "Waiting for shrine revival before "
                        f"restarting step '{step_name}'."
                    ),
                    PySystem.Console.MessageType.Warning,
                )

        def _tick_party_wipe_service(
            node: BehaviorTree.Node,
        ) -> BehaviorTree.NodeState:
            from ..Map import Map

            now = time.monotonic() * 1000.0

            if bool(
                node.blackboard.get(
                    "party_wipe_recovery_suppressed",
                    False,
                )
            ):
                _reset_state(node)
                return BehaviorTree.NodeState.RUNNING

            revived_at_shrine = (
                _detect_revive_teleport()
            )

            party_wiped = bool(
                Routines.Checks.Party.IsPartyWiped()
            )

            party_defeated = bool(
                GLOBAL_CACHE.Party.IsPartyDefeated()
            )

            # ---------------------------------------------
            # Start recovery
            # ---------------------------------------------

            if not state["active"]:
                if not (
                    party_wiped
                    or party_defeated
                    or revived_at_shrine
                ):
                    node.blackboard[
                        "party_wipe_recovery_active"
                    ] = False
                    return BehaviorTree.NodeState.RUNNING

                recovery_mode = (
                    "defeated"
                    if party_defeated
                    else "shrine"
                )

                _begin_recovery(
                    node,
                    recovery_mode,
                )

                # The service may first notice the wipe on the same
                # tick as the shrine teleport.
                if (
                    recovery_mode == "shrine"
                    and revived_at_shrine
                    and _can_resume_in_explorable()
                ):
                    restarted = _request_step_restart(
                        node
                    )

                    if restarted:
                        _log(
                            (
                                "Shrine revival detected. "
                                f"Restarting step "
                                f"'{state['step_name']}' "
                                "in the current instance."
                            ),
                            PySystem.Console.MessageType.Success,
                        )

                    _reset_state(node)

                    return (
                        BehaviorTree.NodeState.SUCCESS
                        if restarted
                        else BehaviorTree.NodeState.FAILURE
                    )

                return BehaviorTree.NodeState.RUNNING

            # ---------------------------------------------
            # Recovery already active
            # ---------------------------------------------

            # A recoverable wipe may later become a true defeat.
            if party_defeated:
                if state["mode"] != "defeated":
                    state["mode"] = "defeated"

                    _log(
                        (
                            "The recoverable wipe became a party "
                            "defeat. Switching to outpost recovery."
                        ),
                        PySystem.Console.MessageType.Warning,
                    )

            node.blackboard[
                "party_wipe_recovery_active"
            ] = True

            node.blackboard[
                "party_wipe_recovery_mode"
            ] = state["mode"]

            node.blackboard[
                "party_wipe_recovery_step_name"
            ] = state["step_name"]

            # ---------------------------------------------
            # Shrine recovery: stay in the same instance
            # ---------------------------------------------

            if state["mode"] == "shrine":
                # If the game returned to an outpost anyway, fall back
                # to the outpost recovery behavior.
                if _can_resume_from_outpost():
                    state["mode"] = "defeated"

                    node.blackboard[
                        "party_wipe_recovery_mode"
                    ] = "defeated"

                    _log(
                        (
                            "The party returned to an outpost "
                            "during shrine recovery. Switching "
                            "to outpost recovery."
                        ),
                        PySystem.Console.MessageType.Warning,
                    )

                else:
                    shrine_recovery_complete = bool(
                        revived_at_shrine
                        or (
                            not party_wiped
                            and _can_resume_in_explorable()
                        )
                    )

                    if shrine_recovery_complete:
                        restarted = _request_step_restart(
                            node
                        )

                        if restarted:
                            _log(
                                (
                                    "Shrine revival detected. "
                                    f"Restarting step "
                                    f"'{state['step_name']}' "
                                    "in the current instance."
                                ),
                                PySystem.Console.MessageType.Success,
                            )

                        _reset_state(node)

                        return (
                            BehaviorTree.NodeState.SUCCESS
                            if restarted
                            else BehaviorTree.NodeState.FAILURE
                        )

                    # Never call ReturnToOutpost for a recoverable wipe.
                    return BehaviorTree.NodeState.RUNNING

            # ---------------------------------------------
            # Defeated recovery: resume from the outpost
            # ---------------------------------------------

            if _can_resume_from_outpost():
                restarted = _request_step_restart(
                    node
                )

                if restarted:
                    _log(
                        (
                            "Outpost loaded after party defeat. "
                            f"Restarting step "
                            f"'{state['step_name']}'."
                        ),
                        PySystem.Console.MessageType.Success,
                    )

                _reset_state(node)

                return (
                    BehaviorTree.NodeState.SUCCESS
                    if restarted
                    else BehaviorTree.NodeState.FAILURE
                )

            if (
                now
                - float(
                    state["last_return_ms"]
                )
                >= max(
                    100.0,
                    float(return_interval_ms),
                )
            ):
                GLOBAL_CACHE.Party.ReturnToOutpost()
                state["last_return_ms"] = now

                _log(
                    "Requesting return to outpost after party defeat."
                )

            return BehaviorTree.NodeState.RUNNING

        return BehaviorTree(
            BehaviorTree.ActionNode(
                name="PartyWipeRecoveryService",
                action_fn=_tick_party_wipe_service,
                aftercast_ms=0,
            )
        )
