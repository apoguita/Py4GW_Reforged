"""Opt-in, profile-aware interaction reliability for BottingTree and coroutine bots.

Legacy interaction wrappers intentionally do not import or call this module.  Callers provide a
policy plus a runtime adapter and must opt in at each interaction site.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable, Generator, Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol


class InteractionProfile(str, Enum):
    QUEST_CONVERSATION = "quest_conversation"
    VISIBLE_CHOICE = "visible_choice"
    REWARD_ACCEPT = "reward_accept"
    AUTOMATIC_TRIGGER = "automatic_npc_or_beacon_trigger"
    GADGET = "gadget_door_or_chest"
    WALK_OVER = "walk_over_trigger"
    CHALLENGE_THEN_REINTERACT = "challenge_then_reinteract"


class TargetKind(str, Enum):
    LIVING = "living"
    NPC = "npc"
    GADGET = "gadget"
    ITEM = "item"
    LOCATION = "location"


class PostconditionKind(str, Enum):
    CUSTOM = "custom"
    QUEST_ACTIVE = "quest_active"
    QUEST_COMPLETED = "quest_completed"
    QUEST_CLEARED = "quest_cleared"
    EFFECT_PRESENT = "effect_present"
    MAP_CHANGED = "map_changed"
    ITEM_DROP_PRESENT = "item_drop_present"
    BUNDLE_CHANGED = "bundle_changed"
    HOSTILITY_CHANGED = "hostility_changed"
    GADGET_STATE_CHANGED = "gadget_state_changed"


class InteractionStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True)
class TargetSpec:
    kind: TargetKind
    model_id: int = 0
    name_contains: str = ""
    expected_xy: tuple[float, float] | None = None
    search_radius: float = 1200.0


@dataclass(frozen=True)
class ApproachSpec:
    player_approach_xy: tuple[float, float] | None = None
    tolerance: float = 90.0
    target_tolerance: float | None = None
    timeout_ms: int = 12_000
    move_reissue_ms: int = 600


@dataclass(frozen=True)
class DialogSpec:
    visible_button: int | None = None
    raw_context_ids: tuple[int, ...] = ()
    response_timeout_ms: int = 4_000
    raw_step_delay_ms: int = 350
    allow_raw_without_visible_dialog: bool = False
    close_dialog_after_success: bool = False
    post_success_dialog_timeout_ms: int = 1_500


@dataclass(frozen=True)
class PostconditionSpec:
    kind: PostconditionKind
    value: int | str | tuple[int, ...] | None = None
    description: str = ""


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    poll_ms: int = 100
    verify_timeout_ms: int = 4_000
    retry_delay_ms: int = 400
    pause_settle_ms: int = 350
    challenge_timeout_ms: int = 90_000


@dataclass(frozen=True)
class InteractionSpec:
    name: str
    profile: InteractionProfile
    target: TargetSpec
    approach: ApproachSpec
    postcondition: PostconditionSpec
    dialog: DialogSpec = field(default_factory=DialogSpec)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    close_stale_dialog: bool = True
    allow_preexisting_postcondition: bool = True
    source_capture_ids: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        data = asdict(self)
        data["profile"] = self.profile.value
        data["target"]["kind"] = self.target.kind.value
        data["postcondition"]["kind"] = self.postcondition.kind.value
        return data


@dataclass(frozen=True)
class CaptureInteractionMetadata:
    """Normalized capture metadata; runtime IDs are deliberately excluded."""

    schema_version: int
    interaction_kind: InteractionProfile
    target_kind: TargetKind
    target_xy: tuple[float, float] | None
    player_approach_xy: tuple[float, float] | None
    model_id: int
    target_name: str
    postcondition: PostconditionSpec
    source_capture_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["interaction_kind"] = self.interaction_kind.value
        result["target_kind"] = self.target_kind.value
        result["postcondition"]["kind"] = self.postcondition.kind.value
        return result


def normalize_capture_metadata(
    capture: Mapping[str, Any],
    *,
    interaction_kind: InteractionProfile,
    postcondition: PostconditionSpec,
    target_kind: TargetKind = TargetKind.LIVING,
) -> CaptureInteractionMetadata:
    """Normalize either capture widget's record without requiring a second capture."""

    target = capture.get("target") if isinstance(capture.get("target"), Mapping) else {}
    player = capture.get("player") if isinstance(capture.get("player"), Mapping) else {}
    point = capture.get("point") if isinstance(capture.get("point"), Mapping) else capture
    target_xy = target.get("xy") or point.get("target_xy") or point.get("npc_xy")
    approach_xy = (
        point.get("player_approach_xy")
        or player.get("xy")
        or point.get("xy")
    )

    def _xy(value: Any) -> tuple[float, float] | None:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return None
        return float(value[0]), float(value[1])

    capture_id = str(capture.get("capture_id") or "")
    return CaptureInteractionMetadata(
        schema_version=2,
        interaction_kind=interaction_kind,
        target_kind=target_kind,
        target_xy=_xy(target_xy),
        player_approach_xy=_xy(approach_xy),
        model_id=int(target.get("model_id") or point.get("preferred_npc_model_id") or 0),
        target_name=str(target.get("name") or point.get("npc_name") or ""),
        postcondition=postcondition,
        source_capture_ids=(capture_id,) if capture_id else (),
    )


class InteractionRuntime(Protocol):
    def now(self) -> float: ...
    def pause_automation(self) -> None: ...
    def restore_automation(self) -> None: ...
    def cancel_movement(self) -> None: ...
    def close_stale_dialog(self) -> None: ...
    def resolve_target(self, target: TargetSpec) -> int | None: ...
    def agent_xy(self, agent_id: int) -> tuple[float, float]: ...
    def agent_model_id(self, agent_id: int) -> int: ...
    def player_xy(self) -> tuple[float, float]: ...
    def move_to(self, xy: tuple[float, float]) -> None: ...
    def interact(self, agent_id: int) -> None: ...
    def dialog_visible(self) -> bool: ...
    def dialog_button_count(self) -> int: ...
    def click_dialog_button(self, choice: int) -> bool: ...
    def send_dialog(self, dialog_id: int) -> None: ...
    def verify(self, postcondition: PostconditionSpec) -> bool: ...
    def is_hostile(self, agent_id: int) -> bool: ...
    def emit(self, event: dict[str, Any]) -> None: ...


class ReliableInteractionController:
    """Tick-driven controller shared by both adapters."""

    def __init__(self, spec: InteractionSpec, runtime: InteractionRuntime):
        self.spec = spec
        self.runtime = runtime
        self.stage = "new"
        self.attempt = 0
        self.agent_id = 0
        self.deadline = 0.0
        self.last_move_at = 0.0
        self.raw_index = 0
        self.dialog_visible_logged = False
        self.dialog_button_count_logged = 0
        self.paused = False
        self.finished = False
        self.result = InteractionStatus.RUNNING

    def _event(self, event: str, **values: Any) -> None:
        self.runtime.emit(
            {
                "component": "reliable_interaction",
                "event": event,
                "interaction": self.spec.name,
                "profile": self.spec.profile.value,
                "stage": self.stage,
                "attempt": self.attempt,
                "agent_id_runtime_only": self.agent_id,
                **values,
            }
        )

    def _finish(self, success: bool, reason: str) -> InteractionStatus:
        if not self.finished:
            try:
                self.runtime.cancel_movement()
            finally:
                if self.paused:
                    self.runtime.restore_automation()
                    self.paused = False
            self.finished = True
            self.result = InteractionStatus.SUCCESS if success else InteractionStatus.FAILURE
            self.stage = "complete" if success else "failed"
            self._event("result", success=success, reason=reason)
        return self.result

    def _postcondition_succeeded(self, now: float, reason: str) -> InteractionStatus:
        self._event(
            "postcondition_verified",
            postcondition=self.spec.postcondition.kind.value,
            description=self.spec.postcondition.description,
        )
        if self.spec.dialog.close_dialog_after_success:
            self.stage = "wait_post_success_dialog"
            self.deadline = now + self.spec.dialog.post_success_dialog_timeout_ms / 1000.0
            self._event(
                "post_success_dialog_wait_started",
                timeout_ms=self.spec.dialog.post_success_dialog_timeout_ms,
            )
            return InteractionStatus.RUNNING
        return self._finish(True, reason)

    def cancel(self, reason: str = "cancelled") -> None:
        if not self.finished:
            self._finish(False, reason)

    def _retry(self, reason: str) -> InteractionStatus:
        self._event("attempt_failed", reason=reason)
        if self.attempt >= max(1, self.spec.retry.max_attempts):
            return self._finish(False, reason)
        self.runtime.cancel_movement()
        if self.spec.close_stale_dialog:
            self.runtime.close_stale_dialog()
        self.agent_id = 0
        self.raw_index = 0
        self.dialog_visible_logged = False
        self.dialog_button_count_logged = 0
        self.stage = "retry_delay"
        self.deadline = self.runtime.now() + self.spec.retry.retry_delay_ms / 1000.0
        return InteractionStatus.RUNNING

    def _destination(self) -> tuple[float, float] | None:
        if self.spec.approach.player_approach_xy is not None:
            return self.spec.approach.player_approach_xy
        target_xy = self.runtime.agent_xy(self.agent_id) if self.agent_id else self.spec.target.expected_xy
        if target_xy is None:
            return None
        if self.spec.target.kind == TargetKind.LOCATION:
            return target_xy
        player_xy = self.runtime.player_xy()
        distance = math.dist(player_xy, target_xy)
        stand_off = max(80.0, self.spec.approach.tolerance)
        if distance <= stand_off:
            return player_xy
        scale = stand_off / distance
        return (
            target_xy[0] + (player_xy[0] - target_xy[0]) * scale,
            target_xy[1] + (player_xy[1] - target_xy[1]) * scale,
        )

    def _agent_model_id(self, agent_id: int) -> int | None:
        getter = getattr(self.runtime, "agent_model_id", None)
        return int(getter(agent_id)) if callable(getter) else None

    def _effective_target_tolerance(self) -> float | None:
        if self.spec.target.kind == TargetKind.LOCATION:
            return None
        if self.spec.approach.target_tolerance is not None:
            return self.spec.approach.target_tolerance
        if self.spec.approach.player_approach_xy is not None:
            return self.spec.approach.tolerance
        return max(80.0, self.spec.approach.tolerance)

    def _position_snapshot(self, destination: tuple[float, float] | None) -> dict[str, Any]:
        player_xy = self.runtime.player_xy()
        agent_xy = self.runtime.agent_xy(self.agent_id) if self.agent_id else None
        expected_xy = self.spec.target.expected_xy
        return {
            "player_xy": player_xy,
            "agent_xy": agent_xy,
            "expected_target_xy": expected_xy,
            "player_approach_xy": destination,
            "player_to_approach_distance": (
                round(math.dist(player_xy, destination), 2) if destination is not None else None
            ),
            "player_to_agent_distance": (
                round(math.dist(player_xy, agent_xy), 2) if agent_xy is not None else None
            ),
            "agent_to_expected_target_distance": (
                round(math.dist(agent_xy, expected_xy), 2)
                if agent_xy is not None and expected_xy is not None
                else None
            ),
            "resolved_model_id": self._agent_model_id(self.agent_id) if self.agent_id else None,
            "expected_model_id": self.spec.target.model_id or None,
        }

    def _resolved_target_failure(self, snapshot: dict[str, Any]) -> str | None:
        expected_model_id = self.spec.target.model_id
        resolved_model_id = snapshot["resolved_model_id"]
        if expected_model_id and resolved_model_id != expected_model_id:
            return f"resolved model {resolved_model_id!r} did not match expected model {expected_model_id}"
        expected_distance = snapshot["agent_to_expected_target_distance"]
        if expected_distance is not None and expected_distance > self.spec.target.search_radius:
            return (
                f"resolved target was {expected_distance:.2f} from expected location, "
                f"outside search radius {self.spec.target.search_radius:.2f}"
            )
        return None

    def tick(self) -> InteractionStatus:
        if self.finished:
            return self.result
        try:
            return self._tick()
        except Exception as error:
            self._event("exception", error=f"{type(error).__name__}: {error}")
            return self._finish(False, "runtime exception")

    def _tick(self) -> InteractionStatus:
        now = self.runtime.now()
        if self.stage == "new":
            if self.runtime.verify(self.spec.postcondition):
                if self.spec.allow_preexisting_postcondition:
                    return self._finish(True, "postcondition already satisfied")
                self._event("preexisting_postcondition_ignored")
            self.runtime.pause_automation()
            self.paused = True
            self.runtime.cancel_movement()
            if self.spec.close_stale_dialog:
                self.runtime.close_stale_dialog()
            self.stage = "pause_settle"
            self.deadline = now + self.spec.retry.pause_settle_ms / 1000.0
            self._event("start", policy=self.spec.to_metadata())
            return InteractionStatus.RUNNING

        if self.stage == "pause_settle":
            if now < self.deadline:
                return InteractionStatus.RUNNING
            self.attempt += 1
            self.stage = "resolve"

        if self.stage == "retry_delay":
            if now < self.deadline:
                return InteractionStatus.RUNNING
            self.attempt += 1
            self.stage = "resolve"

        if self.stage == "resolve":
            if self.spec.target.kind != TargetKind.LOCATION:
                resolved = self.runtime.resolve_target(self.spec.target)
                if not resolved:
                    return self._retry("target not found")
                self.agent_id = int(resolved)
                destination = self._destination()
                snapshot = self._position_snapshot(destination)
                failure = self._resolved_target_failure(snapshot)
                if failure:
                    return self._retry(failure)
                self._event("target_resolved", **snapshot)
            self.stage = "approach"
            self.deadline = now + self.spec.approach.timeout_ms / 1000.0
            self.last_move_at = 0.0
            destination = self._destination()
            self._event(
                "approach_started",
                tolerance=self.spec.approach.tolerance,
                target_tolerance=self._effective_target_tolerance(),
                configured_target_tolerance=self.spec.approach.target_tolerance,
                **self._position_snapshot(destination),
            )

        if self.stage == "approach":
            destination = self._destination()
            if destination is None:
                return self._retry("no safe approach coordinate")
            snapshot = self._position_snapshot(destination)
            approach_distance = float(snapshot["player_to_approach_distance"])
            agent_distance = snapshot["player_to_agent_distance"]
            target_tolerance = self._effective_target_tolerance()
            target_close_enough = (
                target_tolerance is None
                or (agent_distance is not None and float(agent_distance) <= target_tolerance)
            )
            if approach_distance <= self.spec.approach.tolerance and target_close_enough:
                self.runtime.cancel_movement()
                self._event(
                    "approach_reached",
                    tolerance=self.spec.approach.tolerance,
                    target_tolerance=target_tolerance,
                    configured_target_tolerance=self.spec.approach.target_tolerance,
                    **snapshot,
                )
                self.stage = "verify" if self.spec.profile == InteractionProfile.WALK_OVER else "reacquire"
                self.deadline = now + self.spec.retry.verify_timeout_ms / 1000.0
            elif now >= self.deadline:
                return self._retry("safe approach timed out")
            elif now - self.last_move_at >= self.spec.approach.move_reissue_ms / 1000.0:
                self.runtime.move_to(destination)
                self.last_move_at = now
                self._event(
                    "approach_progress",
                    tolerance=self.spec.approach.tolerance,
                    target_tolerance=target_tolerance,
                    configured_target_tolerance=self.spec.approach.target_tolerance,
                    movement_command_sent=True,
                    **snapshot,
                )
            return InteractionStatus.RUNNING

        if self.stage == "reacquire":
            resolved = self.runtime.resolve_target(self.spec.target)
            if not resolved:
                return self._retry("target disappeared before interaction")
            old_id = self.agent_id
            self.agent_id = int(resolved)
            destination = self._destination()
            snapshot = self._position_snapshot(destination)
            failure = self._resolved_target_failure(snapshot)
            if failure:
                return self._retry(f"reacquired target validation failed: {failure}")
            self._event(
                "target_reacquired",
                previous_agent_id_runtime_only=old_id,
                **snapshot,
            )
            self.stage = "interact"

        if self.stage == "interact":
            self.runtime.interact(self.agent_id)
            self._event("interaction_sent", target_xy=self.runtime.agent_xy(self.agent_id))
            if self.spec.profile in (
                InteractionProfile.AUTOMATIC_TRIGGER,
                InteractionProfile.GADGET,
            ):
                self.stage = "verify"
                self.deadline = now + self.spec.retry.verify_timeout_ms / 1000.0
            else:
                self.stage = "wait_response"
                self.deadline = now + self.spec.dialog.response_timeout_ms / 1000.0
            return InteractionStatus.RUNNING

        if self.stage == "wait_response":
            visible = self.runtime.dialog_visible()
            button_count = self.runtime.dialog_button_count() if visible else 0
            if visible and not self.dialog_visible_logged:
                self.dialog_visible_logged = True
                self._event("dialog_visible")
            if visible and button_count > 0 and button_count != self.dialog_button_count_logged:
                self.dialog_button_count_logged = button_count
                self._event("dialog_buttons_populated", button_count=button_count)

            visible_button = self.spec.dialog.visible_button
            if visible_button is not None:
                if visible and button_count > 0:
                    choice = int(visible_button)
                    if choice <= button_count and self.runtime.click_dialog_button(choice):
                        self._event("visible_button_clicked", button=choice, button_count=button_count)
                        if self.spec.dialog.raw_context_ids:
                            # Some quest NPCs expose a visible quest-list choice
                            # followed by a quest-detail context whose *01
                            # dialog performs acceptance. Preserve both steps.
                            self.stage = "wait_raw_response"
                            self.deadline = now + self.spec.dialog.response_timeout_ms / 1000.0
                        else:
                            self.stage = "verify"
                            self.deadline = now + self.spec.retry.verify_timeout_ms / 1000.0
                        return InteractionStatus.RUNNING
                if now >= self.deadline:
                    return self._retry("expected visible dialog choice did not become clickable")
                return InteractionStatus.RUNNING

            if visible and self.raw_index < len(self.spec.dialog.raw_context_ids):
                dialog_id = self.spec.dialog.raw_context_ids[self.raw_index]
                self.runtime.send_dialog(dialog_id)
                self.raw_index += 1
                self._event("raw_dialog_sent", dialog_id=dialog_id, dialog_id_hex=f"0x{dialog_id:X}")
                if self.raw_index >= len(self.spec.dialog.raw_context_ids):
                    self.stage = "verify"
                    self.deadline = now + self.spec.retry.verify_timeout_ms / 1000.0
                else:
                    self.deadline = now + self.spec.dialog.raw_step_delay_ms / 1000.0
                return InteractionStatus.RUNNING
            if now >= self.deadline:
                if (
                    self.raw_index < len(self.spec.dialog.raw_context_ids)
                    and self.spec.dialog.allow_raw_without_visible_dialog
                ):
                    dialog_id = self.spec.dialog.raw_context_ids[self.raw_index]
                    self.runtime.send_dialog(dialog_id)
                    self.raw_index += 1
                    self._event(
                        "raw_dialog_sent_without_visible_frame",
                        dialog_id=dialog_id,
                        dialog_id_hex=f"0x{dialog_id:X}",
                    )
                    self.stage = "verify"
                    self.deadline = now + self.spec.retry.verify_timeout_ms / 1000.0
                    return InteractionStatus.RUNNING
                return self._retry("expected dialogue response did not appear")
                return InteractionStatus.RUNNING

        if self.stage == "wait_raw_response":
            # A visible choice can itself complete the requested action. Check
            # the real postcondition before requiring a follow-up raw context;
            # otherwise an already-accepted quest is retried while automation
            # remains paused simply because its detail frame disappeared.
            if self.runtime.verify(self.spec.postcondition):
                return self._postcondition_succeeded(
                    now,
                    "postcondition verified after visible choice",
                )
            visible = self.runtime.dialog_visible()
            if visible and self.raw_index < len(self.spec.dialog.raw_context_ids):
                dialog_id = self.spec.dialog.raw_context_ids[self.raw_index]
                self.runtime.send_dialog(dialog_id)
                self.raw_index += 1
                self._event(
                    "raw_dialog_sent_after_visible_choice",
                    dialog_id=dialog_id,
                    dialog_id_hex=f"0x{dialog_id:X}",
                )
                if self.raw_index >= len(self.spec.dialog.raw_context_ids):
                    self.stage = "verify"
                    self.deadline = now + self.spec.retry.verify_timeout_ms / 1000.0
                else:
                    self.deadline = now + self.spec.dialog.raw_step_delay_ms / 1000.0
                return InteractionStatus.RUNNING
            if now >= self.deadline:
                return self._retry("quest detail response did not become available")
            return InteractionStatus.RUNNING

        if self.stage == "verify":
            if self.runtime.verify(self.spec.postcondition):
                return self._postcondition_succeeded(now, "postcondition verified")
            if self.spec.profile == InteractionProfile.CHALLENGE_THEN_REINTERACT and self.agent_id:
                if self.runtime.is_hostile(self.agent_id):
                    self._event("challenge_hostile")
                    self.runtime.restore_automation()
                    self.paused = False
                    self.stage = "wait_challenge"
                    self.deadline = now + self.spec.retry.challenge_timeout_ms / 1000.0
                    return InteractionStatus.RUNNING
            if now >= self.deadline:
                return self._retry("postcondition was not verified")
            return InteractionStatus.RUNNING

        if self.stage == "wait_challenge":
            if self.runtime.verify(self.spec.postcondition):
                return self._postcondition_succeeded(now, "challenge postcondition verified")
            resolved = self.runtime.resolve_target(self.spec.target)
            if resolved and not self.runtime.is_hostile(int(resolved)):
                self.runtime.pause_automation()
                self.paused = True
                self.agent_id = int(resolved)
                self.stage = "pause_settle"
                self.deadline = now + self.spec.retry.pause_settle_ms / 1000.0
                self._event("challenge_finished_reinteract")
                return InteractionStatus.RUNNING
            if now >= self.deadline:
                return self._finish(False, "challenge did not finish before timeout")
            return InteractionStatus.RUNNING

        if self.stage == "wait_post_success_dialog":
            if self.runtime.dialog_visible():
                self._event("post_success_dialog_visible")
                self.runtime.close_stale_dialog()
                self._event("post_success_dialog_closed")
                return self._finish(True, "postcondition verified and follow-up dialog closed")
            if now >= self.deadline:
                self._event("post_success_dialog_not_seen")
                return self._finish(True, "postcondition verified; no follow-up dialog appeared")
            return InteractionStatus.RUNNING

        return self._finish(False, f"unknown stage {self.stage!r}")


def run_coroutine_adapter(
    controller: ReliableInteractionController,
    wait: Callable[[int], Generator[Any, Any, Any]],
) -> Generator[Any, Any, bool]:
    """Run the shared controller inside a coroutine/FSM custom state."""

    try:
        while True:
            status = controller.tick()
            if status != InteractionStatus.RUNNING:
                return status == InteractionStatus.SUCCESS
            yield from wait(max(10, controller.spec.retry.poll_ms))
    finally:
        if not controller.finished:
            controller.cancel("coroutine closed")


class Py4GWInteractionRuntime:
    """Active-runtime adapter. Persistence is delegated to the diagnostic sink."""

    def __init__(
        self,
        *,
        pause_automation: Callable[[], None],
        restore_automation: Callable[[], None],
        verify: Callable[[PostconditionSpec], bool],
        diagnostic_sink: Callable[[dict[str, Any]], None] | None = None,
    ):
        self._pause = pause_automation
        self._restore = restore_automation
        self._verify = verify
        self._sink = diagnostic_sink or (lambda _event: None)

    def now(self) -> float:
        return time.monotonic()

    def pause_automation(self) -> None:
        from Py4GWCoreLib.Py4GWcorelib import ActionQueueManager

        self._pause()
        ActionQueueManager().ResetAllQueues()

    def restore_automation(self) -> None:
        self._restore()

    def cancel_movement(self) -> None:
        from Py4GWCoreLib.Py4GWcorelib import ActionQueueManager

        ActionQueueManager().ResetAllQueues()

    def close_stale_dialog(self) -> None:
        from Py4GWCoreLib.UIManager import UIManager
        from Py4GWCoreLib.enums_src.UI_enums import ControlAction

        if UIManager.IsNPCDialogVisible():
            keybind = ControlAction.ControlAction_CloseAllPanels.value
            UIManager.Keydown(keybind, 0)
            UIManager.Keyup(keybind, 0)

    def _all_agents(self) -> list[int]:
        from Py4GWCoreLib.AgentArray import AgentArray
        from Py4GWCoreLib.Context import GWContext

        shared = list(AgentArray.GetAgentArray() or [])
        context = GWContext.AgentArray.GetContext()
        context_agents = list(context.GetAgentArray() or []) if context is not None else []
        return list(dict.fromkeys([*shared, *context_agents]))

    def resolve_target(self, target: TargetSpec) -> int | None:
        from Py4GWCoreLib.Agent import Agent
        from Py4GWCoreLib.Player import Player

        origin = target.expected_xy or Player.GetXY()
        wanted_name = target.name_contains.strip().lower()
        candidates: list[int] = []
        for agent_id in self._all_agents():
            if not Agent.IsValid(agent_id):
                continue
            if target.kind == TargetKind.LIVING and not Agent.IsLiving(agent_id):
                continue
            if target.kind == TargetKind.NPC and not (Agent.IsLiving(agent_id) and Agent.IsNPC(agent_id)):
                continue
            if target.kind == TargetKind.GADGET and not Agent.IsGadget(agent_id):
                continue
            if target.kind == TargetKind.ITEM and not Agent.IsItem(agent_id):
                continue
            if target.model_id and int(Agent.GetModelID(agent_id)) != target.model_id:
                continue
            if wanted_name and wanted_name not in str(Agent.GetNameByID(agent_id) or "").strip().lower():
                continue
            if math.dist(origin, Agent.GetXY(agent_id)) > target.search_radius:
                continue
            candidates.append(int(agent_id))
        if not candidates:
            return None
        return min(candidates, key=lambda agent_id: math.dist(origin, Agent.GetXY(agent_id)))

    def agent_xy(self, agent_id: int) -> tuple[float, float]:
        from Py4GWCoreLib.Agent import Agent

        xy = Agent.GetXY(agent_id)
        return float(xy[0]), float(xy[1])

    def agent_model_id(self, agent_id: int) -> int:
        from Py4GWCoreLib.Agent import Agent

        return int(Agent.GetModelID(agent_id))

    def player_xy(self) -> tuple[float, float]:
        from Py4GWCoreLib.Player import Player

        xy = Player.GetXY()
        return float(xy[0]), float(xy[1])

    def move_to(self, xy: tuple[float, float]) -> None:
        from Py4GWCoreLib.Player import Player

        Player.Move(*xy)

    def interact(self, agent_id: int) -> None:
        from Py4GWCoreLib.Player import Player

        Player.ChangeTarget(agent_id)
        Player.Interact(agent_id, call_target=False)

    def dialog_visible(self) -> bool:
        from Py4GWCoreLib.UIManager import UIManager

        return bool(UIManager.IsNPCDialogVisible())

    def dialog_button_count(self) -> int:
        from Py4GWCoreLib.UIManager import UIManager

        return int(UIManager.GetDialogButtonCount())

    def click_dialog_button(self, choice: int) -> bool:
        from Py4GWCoreLib.UIManager import UIManager

        return bool(UIManager.ClickDialogButton(choice, debug=False))

    def send_dialog(self, dialog_id: int) -> None:
        from Py4GWCoreLib.Player import Player

        Player.SendDialog(dialog_id)

    def verify(self, postcondition: PostconditionSpec) -> bool:
        return bool(self._verify(postcondition))

    def is_hostile(self, agent_id: int) -> bool:
        from Py4GWCoreLib.Agent import Agent

        allegiance = Agent.GetAllegiance(agent_id)
        name = str(allegiance[1] if isinstance(allegiance, tuple) and len(allegiance) > 1 else allegiance)
        return name.strip().lower() == "enemy"

    def emit(self, event: dict[str, Any]) -> None:
        self._sink(dict(event))


def build_botting_tree_action(spec: InteractionSpec, runtime: InteractionRuntime):
    """Build a reset-safe BottingTree leaf without changing any legacy wrapper."""

    from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree

    controller_box = [ReliableInteractionController(spec, runtime)]

    class _ReliableInteractionActionNode(BehaviorTree.ActionNode):
        def reset(self) -> None:
            controller = controller_box[0]
            if not controller.finished:
                controller.cancel("BottingTree node reset")
            controller_box[0] = ReliableInteractionController(spec, runtime)
            super().reset()

    def _tick() -> BehaviorTree.NodeState:
        controller = controller_box[0]
        status = controller.tick()
        if status == InteractionStatus.RUNNING:
            return BehaviorTree.NodeState.RUNNING
        if status == InteractionStatus.SUCCESS:
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(_ReliableInteractionActionNode(name=spec.name, action_fn=_tick, aftercast_ms=0))
