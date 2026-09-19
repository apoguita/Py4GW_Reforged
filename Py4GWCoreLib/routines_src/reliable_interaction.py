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
    NONLIVING_NPC = "nonliving_npc"
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


class StandoffResolutionStrategy(str, Enum):
    """How a boundary proves that its target can be found from the standoff."""

    EXPECTED_TARGET_RADIUS = "expected_target_radius"
    RUNTIME_ONLY = "runtime_only"


@dataclass(frozen=True)
class TargetSpec:
    kind: TargetKind
    model_id: int = 0
    gadget_id: int = 0
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
    # One-based visible-button sequence for multi-page conversations. When
    # populated, this takes precedence over visible_button. Example: (1, 1)
    # clicks the first choice, waits for the next populated page, then clicks
    # the first choice again.
    visible_buttons: tuple[int, ...] = ()
    # Case-insensitive visible-label sequence for menus whose button position
    # changes as other quests become available. When populated, labels take
    # precedence over positional visible_buttons.
    visible_button_labels: tuple[str, ...] = ()
    # Optional leading pages that may disappear when a sibling quest or other
    # one-time choice is already complete. Each label is clicked when present;
    # once a populated page proves it is absent, the controller continues with
    # visible_button_labels on that same page. This keeps both the menu-first
    # and direct-detail variants inside one restart-safe interaction attempt.
    optional_leading_visible_button_labels: tuple[str, ...] = ()
    # Long dialogue pages can place their response buttons below the viewport.
    # Labels listed here receive bounded downward mouse-wheel scrolls once the
    # target's dialog is visible and before label discovery/click. Long pages
    # may need several distinct wheel ticks before the response is exposed.
    # This is opt-in because most NPC pages must not move the user's UI.
    scroll_down_before_visible_button_labels: tuple[str, ...] = ()
    scroll_step_delay_ms: int = 350
    # PyMouse forwards this value directly as the signed high word of
    # WM_MOUSEWHEEL. Use one native Windows wheel notch, not a legacy logical
    # step count; sub-notch values such as -5 may be ignored by Guild Wars.
    scroll_wheel_delta: int = -120
    raw_context_ids: tuple[int, ...] = ()
    # Opt in when a conversation intentionally changes from normal visible
    # buttons to raw context responses on a later page. Without this flag,
    # visible choices retain precedence and raw ids remain fallback metadata.
    chain_raw_after_visible: bool = False
    response_timeout_ms: int = 4_000
    visible_step_delay_ms: int = 500
    raw_step_delay_ms: int = 350
    allow_raw_without_visible_dialog: bool = False
    close_dialog_after_success: bool = False
    post_success_dialog_timeout_ms: int = 1_500
    # Some optional interactions answer with a stable, buttonless page when
    # their eligibility requirement is not met. Callers must provide a
    # postcondition that recognizes that alternate outcome. The settle delay
    # prevents an asynchronously populating choice page from being mistaken
    # for a final no-choice response.
    allow_no_choice_success: bool = False
    no_choice_settle_ms: int = 1_000


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
    # Some interactions toggle an NPC into a following state without opening
    # a dialog. Moving away after the single click provides the stimulus needed
    # to verify that state without clicking again and toggling it back off.
    verification_move_xy: tuple[float, float] | None = None
    verification_move_reissue_ms: int = 600
    source_capture_ids: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        data = asdict(self)
        data["profile"] = self.profile.value
        data["target"]["kind"] = self.target.kind.value
        data["postcondition"]["kind"] = self.postcondition.kind.value
        return data


class InteractionBoundaryValidationError(ValueError):
    """Raised when a route can enter an interaction's collision-sensitive area."""


@dataclass(frozen=True)
class InteractionBoundarySpec:
    """Own the ordinary route and its handoff to one reliable interaction.

    ``route_points`` ends at ``route_standoff_xy``.  It must never end at the
    captured live-target coordinate or at the final player approach.  The
    boundary stops that route early once the player is within ``handoff_radius``
    and the intended target is resolvable; the interaction controller then
    exclusively owns the final approach and all later stages.
    """

    name: str
    route_points: tuple[tuple[float, float], ...]
    route_standoff_xy: tuple[float, float]
    interaction: InteractionSpec
    route_tolerance: float = 150.0
    handoff_radius: float = 250.0
    coordinate_epsilon: float = 1.0
    resolution_strategy: StandoffResolutionStrategy = (
        StandoffResolutionStrategy.EXPECTED_TARGET_RADIUS
    )

    def validate(self) -> None:
        errors: list[str] = []
        if not self.route_points:
            errors.append("ordinary route must contain at least one point")
        if self.route_tolerance <= 0:
            errors.append("route_tolerance must be positive")
        if self.handoff_radius <= 0:
            errors.append("handoff_radius must be positive")
        elif self.handoff_radius < self.route_tolerance:
            errors.append("handoff_radius must be at least route_tolerance")
        if self.coordinate_epsilon < 0:
            errors.append("coordinate_epsilon cannot be negative")

        route_endpoint = self.route_points[-1] if self.route_points else None
        approach_xy = self.interaction.approach.player_approach_xy
        target_xy = self.interaction.target.expected_xy

        def same(left: tuple[float, float] | None, right: tuple[float, float] | None) -> bool:
            return left is not None and right is not None and math.dist(left, right) <= self.coordinate_epsilon

        if route_endpoint is not None and not same(route_endpoint, self.route_standoff_xy):
            errors.append("ordinary route endpoint must be the declared route standoff")
        if same(route_endpoint, approach_xy):
            errors.append("ordinary route endpoint reuses the final player approach coordinate")
        if same(route_endpoint, target_xy):
            errors.append("ordinary route endpoint reuses the live target coordinate")
        if same(self.route_standoff_xy, approach_xy):
            errors.append("route standoff and final player approach must be distinct")
        if same(self.route_standoff_xy, target_xy):
            errors.append("route standoff and live target coordinate must be distinct")
        if same(approach_xy, target_xy):
            errors.append("final player approach and live target coordinate must be distinct")

        if self.resolution_strategy == StandoffResolutionStrategy.EXPECTED_TARGET_RADIUS:
            if target_xy is None and self.interaction.target.kind != TargetKind.LOCATION:
                errors.append(
                    "expected-target-radius resolution requires a captured live target coordinate"
                )
            elif target_xy is not None:
                standoff_to_target = math.dist(self.route_standoff_xy, target_xy)
                if standoff_to_target > self.interaction.target.search_radius:
                    errors.append(
                        "route standoff is outside the target search radius "
                        f"({standoff_to_target:.2f} > {self.interaction.target.search_radius:.2f})"
                    )

        if errors:
            raise InteractionBoundaryValidationError("; ".join(errors))

    def to_metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "route_points": self.route_points,
            "route_standoff_xy": self.route_standoff_xy,
            "route_tolerance": self.route_tolerance,
            "handoff_radius": self.handoff_radius,
            "resolution_strategy": self.resolution_strategy.value,
            "interaction": self.interaction.to_metadata(),
        }


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
    def agent_gadget_id(self, agent_id: int) -> int: ...
    def player_xy(self) -> tuple[float, float]: ...
    def move_to(self, xy: tuple[float, float]) -> None: ...
    def interact(self, agent_id: int) -> None: ...
    def dialog_visible(self) -> bool: ...
    def dialog_button_count(self) -> int: ...
    def dialog_button_labels(self) -> tuple[str, ...]: ...
    def scroll_dialog(self, delta: int) -> bool: ...
    def click_dialog_button(self, choice: int) -> bool: ...
    def send_dialog(self, dialog_id: int) -> None: ...
    def verify(self, postcondition: PostconditionSpec) -> bool: ...
    def is_hostile(self, agent_id: int) -> bool: ...
    def emit(self, event: dict[str, Any]) -> None: ...


class BoundaryRouteExecutor(Protocol):
    """Tick-driven adapter for the bot's normal pathing implementation."""

    def start(
        self,
        route_points: tuple[tuple[float, float], ...],
        tolerance: float,
        handoff_ready: Callable[[], bool],
    ) -> None: ...
    def tick(self) -> InteractionStatus: ...
    def cancel(self) -> None: ...


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
        self.last_verification_move_at = 0.0
        self.raw_index = 0
        self.visible_index = 0
        self.optional_visible_index = 0
        self.scrolled_visible_indices: set[int] = set()
        self.scroll_steps_by_visible_index: dict[int, int] = {}
        self.visible_step_not_before = 0.0
        self.dialog_visible_logged = False
        self.dialog_button_count_logged = 0
        self.no_choice_visible_since = 0.0
        self.paused = False
        self.finished = False
        self.result = InteractionStatus.RUNNING
        self._ownership_token = object()
        self._ownership_published = False

    def _refresh_ownership(self) -> None:
        was_published = self._ownership_published
        try:
            from Py4GWCoreLib.routines_src.shared_command_coordination import (
                refresh_local_reliable_interaction,
            )

            refresh_local_reliable_interaction(
                self._ownership_token,
                name=self.spec.name,
            )
            self._ownership_published = True
            if not was_published:
                self._event("movement_ownership_acquired")
        except Exception:
            # The standalone policy tests intentionally load this module
            # without the full injected Py4GW package.  Coordination is an
            # active-runtime enhancement; interaction behavior stays usable
            # if that optional process-local module is unavailable.
            return

    def _clear_ownership(self) -> None:
        if not self._ownership_published:
            return
        try:
            try:
                from Py4GWCoreLib.routines_src.shared_command_coordination import (
                    clear_local_reliable_interaction,
                )

                clear_local_reliable_interaction(self._ownership_token)
            except Exception:
                pass
        finally:
            self._ownership_published = False
            try:
                self._event("movement_ownership_released")
            except Exception:
                pass

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
                try:
                    self.runtime.cancel_movement()
                finally:
                    if self.paused:
                        self.runtime.restore_automation()
                        self.paused = False
            finally:
                self._clear_ownership()
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
        self.visible_index = 0
        self.optional_visible_index = 0
        self.scrolled_visible_indices.clear()
        self.scroll_steps_by_visible_index.clear()
        self.visible_step_not_before = 0.0
        self.dialog_visible_logged = False
        self.dialog_button_count_logged = 0
        self.no_choice_visible_since = 0.0
        self.last_verification_move_at = 0.0
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

    def _agent_gadget_id(self, agent_id: int) -> int | None:
        getter = getattr(self.runtime, "agent_gadget_id", None)
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
            "resolved_gadget_id": self._agent_gadget_id(self.agent_id) if self.agent_id else None,
            "expected_gadget_id": self.spec.target.gadget_id or None,
        }

    def _resolved_target_failure(self, snapshot: dict[str, Any]) -> str | None:
        expected_model_id = self.spec.target.model_id
        resolved_model_id = snapshot["resolved_model_id"]
        if expected_model_id and resolved_model_id != expected_model_id:
            return f"resolved model {resolved_model_id!r} did not match expected model {expected_model_id}"
        expected_gadget_id = self.spec.target.gadget_id
        resolved_gadget_id = snapshot["resolved_gadget_id"]
        if expected_gadget_id and resolved_gadget_id != expected_gadget_id:
            return (
                f"resolved gadget {resolved_gadget_id!r} did not match "
                f"expected gadget {expected_gadget_id}"
            )
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
            self._refresh_ownership()
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
            # Some quest conversations (for example Scout Ryder) complete as a
            # direct consequence of Interact and never populate a dialog frame.
            if (
                self.spec.profile == InteractionProfile.QUEST_CONVERSATION
                and self.runtime.verify(self.spec.postcondition)
            ):
                return self._postcondition_succeeded(
                    now,
                    "postcondition verified immediately after interaction",
                )
            visible = self.runtime.dialog_visible()
            button_count = self.runtime.dialog_button_count() if visible else 0
            if visible and not self.dialog_visible_logged:
                self.dialog_visible_logged = True
                self._event("dialog_visible")
            if visible and button_count > 0 and button_count != self.dialog_button_count_logged:
                self.dialog_button_count_logged = button_count
                self._event("dialog_buttons_populated", button_count=button_count)
            if self.spec.dialog.allow_no_choice_success and visible and button_count == 0:
                if self.no_choice_visible_since <= 0.0:
                    self.no_choice_visible_since = now
                    self._event(
                        "no_choice_dialog_settle_started",
                        settle_ms=self.spec.dialog.no_choice_settle_ms,
                    )
                elif (
                    now - self.no_choice_visible_since
                    >= self.spec.dialog.no_choice_settle_ms / 1000.0
                    and self.runtime.verify(self.spec.postcondition)
                ):
                    return self._postcondition_succeeded(
                        now,
                        "stable no-choice dialog matched alternate postcondition",
                    )
            else:
                self.no_choice_visible_since = 0.0

            visible_buttons = (
                tuple(int(choice) for choice in self.spec.dialog.visible_buttons)
                if self.spec.dialog.visible_buttons
                else (
                    (int(self.spec.dialog.visible_button),)
                    if self.spec.dialog.visible_button is not None
                    else ()
                )
            )
            visible_button_labels = tuple(
                str(label).strip()
                for label in self.spec.dialog.visible_button_labels
                if str(label).strip()
            )
            optional_leading_labels = tuple(
                str(label).strip()
                for label in self.spec.dialog.optional_leading_visible_button_labels
                if str(label).strip()
            )
            scroll_down_labels = {
                str(label).strip().casefold()
                for label in self.spec.dialog.scroll_down_before_visible_button_labels
                if str(label).strip()
            }
            if self.optional_visible_index < len(optional_leading_labels):
                if now < self.visible_step_not_before:
                    return InteractionStatus.RUNNING
                if visible and button_count > 0:
                    labels = tuple(self.runtime.dialog_button_labels())
                    labels_ready = (
                        len(labels) >= button_count
                        and any(str(label).strip() for label in labels)
                    )
                    if labels_ready:
                        desired = optional_leading_labels[self.optional_visible_index]
                        desired_folded = desired.casefold()
                        exact = [
                            index + 1
                            for index, label in enumerate(labels)
                            if str(label).strip().casefold() == desired_folded
                        ]
                        contains = [
                            index + 1
                            for index, label in enumerate(labels)
                            if desired_folded in str(label).strip().casefold()
                        ]
                        matches = exact or contains
                        if len(matches) == 1:
                            choice = matches[0]
                            if choice <= button_count and self.runtime.click_dialog_button(choice):
                                self.optional_visible_index += 1
                                self._event(
                                    "optional_visible_button_label_clicked",
                                    button=choice,
                                    label=desired,
                                    observed_labels=labels,
                                    button_count=button_count,
                                    sequence_index=self.optional_visible_index,
                                    sequence_length=len(optional_leading_labels),
                                )
                                self.visible_step_not_before = (
                                    now + self.spec.dialog.visible_step_delay_ms / 1000.0
                                )
                                self.deadline = (
                                    self.visible_step_not_before
                                    + self.spec.dialog.response_timeout_ms / 1000.0
                                )
                                self.dialog_visible_logged = False
                                self.dialog_button_count_logged = 0
                                self._event(
                                    "next_visible_dialog_wait_started",
                                    next_sequence_index=self.visible_index + 1,
                                    settle_ms=self.spec.dialog.visible_step_delay_ms,
                                )
                                return InteractionStatus.RUNNING
                        elif len(matches) > 1:
                            self._event(
                                "optional_visible_button_label_ambiguous",
                                label=desired,
                                observed_labels=labels,
                                matching_buttons=matches,
                            )
                            if now >= self.deadline:
                                return self._retry(
                                    "optional visible dialog label was ambiguous"
                                )
                            return InteractionStatus.RUNNING
                        else:
                            self.optional_visible_index += 1
                            self._event(
                                "optional_visible_button_label_absent",
                                label=desired,
                                observed_labels=labels,
                            )
                            # Evaluate the required label against this same
                            # populated page without another interaction.
            if visible_button_labels and self.visible_index < len(visible_button_labels):
                if now < self.visible_step_not_before:
                    return InteractionStatus.RUNNING
                desired = visible_button_labels[self.visible_index]
                desired_folded = desired.casefold()
                if visible and desired_folded in scroll_down_labels:
                    labels = tuple(self.runtime.dialog_button_labels())
                    exact_before_scroll = [
                        index + 1
                        for index, label in enumerate(labels)
                        if str(label).strip().casefold() == desired_folded
                    ]
                    contains_before_scroll = [
                        index + 1
                        for index, label in enumerate(labels)
                        if desired_folded in str(label).strip().casefold()
                    ]
                    matches_before_scroll = exact_before_scroll or contains_before_scroll
                    scroll_steps = self.scroll_steps_by_visible_index.get(
                        self.visible_index, 0
                    )
                    must_scroll = scroll_steps == 0
                    matching_choice = (
                        matches_before_scroll[0]
                        if len(matches_before_scroll) == 1
                        else 0
                    )
                    # Native dialog metadata can expose every logical choice
                    # before any corresponding button frame has entered the
                    # scrolled viewport. Keep scrolling until the matched
                    # one-based choice is also represented by a visible frame;
                    # label uniqueness alone is not clickability proof.
                    matching_choice_dispatchable = (
                        matching_choice > 0 and matching_choice <= button_count
                    )
                    needs_more_scroll = not matching_choice_dispatchable
                    if (must_scroll or needs_more_scroll) and now < self.deadline:
                        if not self.runtime.scroll_dialog(
                            int(self.spec.dialog.scroll_wheel_delta)
                        ):
                            if now >= self.deadline:
                                return self._retry(
                                    "dialog page could not be scrolled to its response buttons"
                                )
                            return InteractionStatus.RUNNING
                        scroll_steps += 1
                        self.scroll_steps_by_visible_index[self.visible_index] = scroll_steps
                        self.scrolled_visible_indices.add(self.visible_index)
                        self.visible_step_not_before = (
                            now + self.spec.dialog.scroll_step_delay_ms / 1000.0
                        )
                        self.dialog_button_count_logged = 0
                        self._event(
                            "dialog_scrolled_for_visible_button_label",
                            label=desired,
                            wheel_delta=self.spec.dialog.scroll_wheel_delta,
                            scroll_step=scroll_steps,
                            observed_labels=labels,
                        )
                        return InteractionStatus.RUNNING
                if visible and button_count > 0:
                    labels = tuple(self.runtime.dialog_button_labels())
                    exact = [
                        index + 1
                        for index, label in enumerate(labels)
                        if str(label).strip().casefold() == desired_folded
                    ]
                    contains = [
                        index + 1
                        for index, label in enumerate(labels)
                        if desired_folded in str(label).strip().casefold()
                    ]
                    matches = exact or contains
                    # Stateful choice dialogs may remove the selected mode
                    # and leave only its opposite option. That remaining page
                    # is a concrete, restart-safe postcondition: do not click
                    # the toggle again merely because its label disappeared.
                    if (
                        not matches
                        and self.spec.allow_preexisting_postcondition
                        and self.runtime.verify(self.spec.postcondition)
                    ):
                        return self._postcondition_succeeded(
                            now,
                            "visible dialog matched preexisting postcondition",
                        )
                    if len(matches) == 1:
                        choice = matches[0]
                        if choice <= button_count and self.runtime.click_dialog_button(choice):
                            self.visible_index += 1
                            self._event(
                                "visible_button_label_clicked",
                                button=choice,
                                label=desired,
                                observed_labels=labels,
                                button_count=button_count,
                                sequence_index=self.visible_index,
                                sequence_length=len(visible_button_labels),
                            )
                            if self.visible_index < len(visible_button_labels):
                                self.visible_step_not_before = (
                                    now + self.spec.dialog.visible_step_delay_ms / 1000.0
                                )
                                self.deadline = (
                                    self.visible_step_not_before
                                    + self.spec.dialog.response_timeout_ms / 1000.0
                                )
                                self.dialog_visible_logged = False
                                self.dialog_button_count_logged = 0
                                self._event(
                                    "next_visible_dialog_wait_started",
                                    next_sequence_index=self.visible_index + 1,
                                    settle_ms=self.spec.dialog.visible_step_delay_ms,
                                )
                            elif (
                                self.spec.dialog.chain_raw_after_visible
                                and self.raw_index < len(self.spec.dialog.raw_context_ids)
                            ):
                                # Some conversations change API mechanisms
                                # between pages: a normal visible choice opens
                                # a conclusion page acknowledged by raw context
                                # id. Settle that replacement page, then hand it
                                # to the shared raw-response branch below.
                                self.visible_step_not_before = (
                                    now + self.spec.dialog.visible_step_delay_ms / 1000.0
                                )
                                self.deadline = (
                                    self.visible_step_not_before
                                    + self.spec.dialog.response_timeout_ms / 1000.0
                                )
                                self.dialog_visible_logged = False
                                self.dialog_button_count_logged = 0
                                self._event(
                                    "raw_dialog_after_visible_wait_started",
                                    next_raw_index=self.raw_index + 1,
                                    settle_ms=self.spec.dialog.visible_step_delay_ms,
                                )
                            else:
                                self.stage = "verify"
                                self.deadline = (
                                    now + self.spec.retry.verify_timeout_ms / 1000.0
                                )
                            return InteractionStatus.RUNNING
                    elif len(matches) > 1:
                        self._event(
                            "visible_button_label_ambiguous",
                            label=desired,
                            observed_labels=labels,
                            matching_buttons=matches,
                        )
                if now >= self.deadline:
                    return self._retry(
                        "expected visible dialog label did not become uniquely clickable"
                    )
                return InteractionStatus.RUNNING

            if visible_buttons and self.visible_index < len(visible_buttons):
                if now < self.visible_step_not_before:
                    return InteractionStatus.RUNNING
                if visible and button_count > 0:
                    choice = visible_buttons[self.visible_index]
                    if choice <= button_count and self.runtime.click_dialog_button(choice):
                        self.visible_index += 1
                        self._event(
                            "visible_button_clicked",
                            button=choice,
                            button_count=button_count,
                            sequence_index=self.visible_index,
                            sequence_length=len(visible_buttons),
                        )
                        if self.visible_index < len(visible_buttons):
                            # The game may replace a dialogue page without an
                            # observable invisible frame. Match the proven
                            # dungeon pattern: settle, then wait again for a
                            # populated visible page before the next click.
                            self.visible_step_not_before = (
                                now + self.spec.dialog.visible_step_delay_ms / 1000.0
                            )
                            self.deadline = (
                                self.visible_step_not_before
                                + self.spec.dialog.response_timeout_ms / 1000.0
                            )
                            self.dialog_visible_logged = False
                            self.dialog_button_count_logged = 0
                            self._event(
                                "next_visible_dialog_wait_started",
                                next_sequence_index=self.visible_index + 1,
                                settle_ms=self.spec.dialog.visible_step_delay_ms,
                            )
                        elif (
                            self.spec.dialog.chain_raw_after_visible
                            and self.raw_index < len(self.spec.dialog.raw_context_ids)
                        ):
                            self.visible_step_not_before = (
                                now + self.spec.dialog.visible_step_delay_ms / 1000.0
                            )
                            self.deadline = (
                                self.visible_step_not_before
                                + self.spec.dialog.response_timeout_ms / 1000.0
                            )
                            self.dialog_visible_logged = False
                            self.dialog_button_count_logged = 0
                            self._event(
                                "raw_dialog_after_visible_wait_started",
                                next_raw_index=self.raw_index + 1,
                                settle_ms=self.spec.dialog.visible_step_delay_ms,
                            )
                        else:
                            self.stage = "verify"
                            self.deadline = now + self.spec.retry.verify_timeout_ms / 1000.0
                        return InteractionStatus.RUNNING
                if now >= self.deadline:
                    return self._retry("expected visible dialog choice did not become clickable")
                return InteractionStatus.RUNNING

            if now < self.visible_step_not_before:
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

        if self.stage == "verify":
            if self.runtime.verify(self.spec.postcondition):
                return self._postcondition_succeeded(now, "postcondition verified")
            if self.spec.verification_move_xy is not None:
                if (
                    now - self.last_verification_move_at
                    >= self.spec.verification_move_reissue_ms / 1000.0
                ):
                    self.runtime.move_to(self.spec.verification_move_xy)
                    self.last_verification_move_at = now
                    self._event(
                        "verification_movement_sent",
                        verification_move_xy=self.spec.verification_move_xy,
                    )
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
                # A challenge deliberately starts the same interaction again
                # after combat, so its dialogue sequence must begin at page 1.
                self.raw_index = 0
                self.visible_index = 0
                self.optional_visible_index = 0
                self.visible_step_not_before = 0.0
                self.dialog_visible_logged = False
                self.dialog_button_count_logged = 0
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


class InteractionBoundaryController:
    """Execute a safe ordinary-route handoff before a reliable interaction."""

    def __init__(
        self,
        spec: InteractionBoundarySpec,
        runtime: InteractionRuntime,
        route_executor: BoundaryRouteExecutor,
    ):
        self.spec = spec
        self.runtime = runtime
        self.route_executor = route_executor
        self.stage = "new"
        self.finished = False
        self.result = InteractionStatus.RUNNING
        self.route_started = False
        self.interaction_controller: ReliableInteractionController | None = None
        self.handoff_agent_id = 0
        try:
            self.spec.validate()
        except InteractionBoundaryValidationError as error:
            self._event("boundary_construction_validation_failed", reason=str(error))
            raise

    def _event(self, event: str, **values: Any) -> None:
        self.runtime.emit(
            {
                "component": "reliable_interaction_boundary",
                "event": event,
                "boundary": self.spec.name,
                "interaction": self.spec.interaction.name,
                "stage": self.stage,
                **values,
            }
        )

    def _finish(self, success: bool, reason: str) -> InteractionStatus:
        if not self.finished:
            try:
                self.route_executor.cancel()
            finally:
                self.runtime.cancel_movement()
            self.finished = True
            self.result = InteractionStatus.SUCCESS if success else InteractionStatus.FAILURE
            self.stage = "complete" if success else "failed"
            self._event("boundary_result", success=success, reason=reason)
        return self.result

    def cancel(self, reason: str = "cancelled") -> None:
        if self.finished:
            return
        if self.interaction_controller is not None and not self.interaction_controller.finished:
            self.interaction_controller.cancel(f"interaction boundary cancelled: {reason}")
        self._finish(False, reason)

    def _handoff_snapshot(self) -> tuple[bool, dict[str, Any]]:
        player_xy = self.runtime.player_xy()
        standoff_distance = math.dist(player_xy, self.spec.route_standoff_xy)
        target = self.spec.interaction.target
        agent_id = 0
        agent_xy = None
        resolved_model_id = None
        resolved_gadget_id = None
        failure = None

        if target.kind != TargetKind.LOCATION:
            resolved = self.runtime.resolve_target(target)
            if resolved:
                agent_id = int(resolved)
                agent_xy = self.runtime.agent_xy(agent_id)
                model_getter = getattr(self.runtime, "agent_model_id", None)
                resolved_model_id = int(model_getter(agent_id)) if callable(model_getter) else None
                gadget_getter = getattr(self.runtime, "agent_gadget_id", None)
                resolved_gadget_id = int(gadget_getter(agent_id)) if callable(gadget_getter) else None
                if target.model_id and resolved_model_id != target.model_id:
                    failure = (
                        f"resolved model {resolved_model_id!r} did not match "
                        f"expected model {target.model_id}"
                    )
                elif target.gadget_id and resolved_gadget_id != target.gadget_id:
                    failure = (
                        f"resolved gadget {resolved_gadget_id!r} did not match "
                        f"expected gadget {target.gadget_id}"
                    )
                elif target.expected_xy is not None:
                    target_offset = math.dist(agent_xy, target.expected_xy)
                    if target_offset > target.search_radius:
                        failure = (
                            f"resolved target was {target_offset:.2f} from expected location, "
                            f"outside search radius {target.search_radius:.2f}"
                        )
            else:
                failure = "intended live target was not resolvable"

        snapshot = {
            "player_xy": player_xy,
            "route_standoff_xy": self.spec.route_standoff_xy,
            "player_to_standoff_distance": round(standoff_distance, 2),
            "handoff_radius": self.spec.handoff_radius,
            "agent_id_runtime_only": agent_id,
            "agent_xy": agent_xy,
            "player_to_agent_distance": (
                round(math.dist(player_xy, agent_xy), 2) if agent_xy is not None else None
            ),
            "resolved_model_id": resolved_model_id,
            "expected_model_id": target.model_id or None,
            "resolved_gadget_id": resolved_gadget_id,
            "expected_gadget_id": target.gadget_id or None,
            "failure": failure,
        }
        ready = standoff_distance <= self.spec.handoff_radius and failure is None
        if ready:
            self.handoff_agent_id = agent_id
        return ready, snapshot

    def _handoff_ready(self) -> bool:
        ready, _snapshot = self._handoff_snapshot()
        return ready

    def _begin_handoff(self, snapshot: dict[str, Any]) -> InteractionStatus:
        self.route_executor.cancel()
        self.runtime.cancel_movement()
        self._event("target_resolvable_from_standoff", **snapshot)
        self.interaction_controller = ReliableInteractionController(
            self.spec.interaction,
            self.runtime,
        )
        self.stage = "interaction"
        self._event(
            "handoff_to_interaction_controller",
            final_approach_xy=self.spec.interaction.approach.player_approach_xy,
            **snapshot,
        )
        return InteractionStatus.RUNNING

    def tick(self) -> InteractionStatus:
        if self.finished:
            return self.result
        try:
            return self._tick()
        except Exception as error:
            self._event(
                "boundary_runtime_validation_failed",
                reason=f"{type(error).__name__}: {error}",
            )
            if self.interaction_controller is not None and not self.interaction_controller.finished:
                self.interaction_controller.cancel("boundary runtime exception")
            return self._finish(False, "boundary runtime exception")

    def _tick(self) -> InteractionStatus:
        if self.stage == "new":
            self._event("route_boundary_entered", policy=self.spec.to_metadata())
            self.route_executor.start(
                self.spec.route_points,
                self.spec.route_tolerance,
                self._handoff_ready,
            )
            self.route_started = True
            self.stage = "route"

        if self.stage == "route":
            ready, snapshot = self._handoff_snapshot()
            if ready:
                return self._begin_handoff(snapshot)

            route_status = self.route_executor.tick()
            if route_status != InteractionStatus.RUNNING:
                # A coroutine route may report failure when its custom-exit
                # predicate deliberately ended the route. Recheck readiness
                # before interpreting the route's terminal status.
                ready, snapshot = self._handoff_snapshot()
                if ready:
                    return self._begin_handoff(snapshot)
                reason = (
                    "ordinary route completed without a resolvable handoff"
                    if route_status == InteractionStatus.SUCCESS
                    else "ordinary route failed before a resolvable handoff"
                )
                self._event("boundary_runtime_validation_failed", reason=reason, **snapshot)
                return self._finish(False, reason)
            return InteractionStatus.RUNNING

        if self.stage == "interaction":
            if self.interaction_controller is None:
                self._event(
                    "boundary_runtime_validation_failed",
                    reason="interaction controller was not created",
                )
                return self._finish(False, "interaction controller missing")
            status = self.interaction_controller.tick()
            if status == InteractionStatus.SUCCESS:
                return self._finish(True, "route handoff and interaction succeeded")
            if status == InteractionStatus.FAILURE:
                return self._finish(False, "required interaction failed")
            return InteractionStatus.RUNNING

        return self._finish(False, f"unknown boundary stage {self.stage!r}")


class GeneratorBoundaryRouteExecutor:
    """Adapt a coroutine/FSM route generator to the boundary controller."""

    def __init__(
        self,
        route_factory: Callable[
            [
                tuple[tuple[float, float], ...],
                float,
                Callable[[], bool],
            ],
            Generator[Any, Any, Any],
        ],
    ):
        self.route_factory = route_factory
        self.generator: Generator[Any, Any, Any] | None = None
        self.finished = False

    def start(
        self,
        route_points: tuple[tuple[float, float], ...],
        tolerance: float,
        handoff_ready: Callable[[], bool],
    ) -> None:
        if self.generator is not None:
            raise RuntimeError("boundary route executor was started more than once")
        self.generator = self.route_factory(route_points, tolerance, handoff_ready)

    def tick(self) -> InteractionStatus:
        if self.finished:
            return InteractionStatus.SUCCESS
        if self.generator is None:
            raise RuntimeError("boundary route executor was ticked before start")
        try:
            next(self.generator)
            return InteractionStatus.RUNNING
        except StopIteration as stopped:
            self.finished = True
            return (
                InteractionStatus.SUCCESS
                if stopped.value is not False
                else InteractionStatus.FAILURE
            )

    def cancel(self) -> None:
        generator = self.generator
        self.generator = None
        self.finished = True
        if generator is not None:
            generator.close()


def make_follow_path_boundary_executor(
    follow_path: Callable[..., Generator[Any, Any, Any]],
    **follow_path_kwargs: Any,
) -> GeneratorBoundaryRouteExecutor:
    """Build a boundary executor around ``Routines.Yield.Movement.FollowPath``."""

    def _route_factory(
        route_points: tuple[tuple[float, float], ...],
        tolerance: float,
        handoff_ready: Callable[[], bool],
    ) -> Generator[Any, Any, Any]:
        return follow_path(
            list(route_points),
            custom_exit_condition=handoff_ready,
            tolerance=tolerance,
            **follow_path_kwargs,
        )

    return GeneratorBoundaryRouteExecutor(_route_factory)


def _local_route_auxiliary_active() -> bool:
    """Observe Loot/Chest ownership only at adapter entry.

    The shared chest worker drives a controller directly, so keeping this gate
    in route/mission adapters avoids making that worker observe its own inbox
    transaction.
    """

    try:
        from Py4GWCoreLib.routines_src.shared_command_coordination import (
            is_local_route_auxiliary_active,
        )

        return bool(is_local_route_auxiliary_active())
    except Exception:
        return False


def _boundary_should_defer_for_auxiliary(
    controller: InteractionBoundaryController,
) -> bool:
    """Keep a boundary from handing off into a new interaction mid-command."""

    if not _local_route_auxiliary_active():
        return False
    interaction = controller.interaction_controller
    return interaction is None or interaction.stage == "new"


def run_coroutine_adapter(
    controller: ReliableInteractionController,
    wait: Callable[[int], Generator[Any, Any, Any]],
) -> Generator[Any, Any, bool]:
    """Run the shared controller inside a coroutine/FSM custom state."""

    try:
        while True:
            if controller.stage == "new" and _local_route_auxiliary_active():
                yield from wait(max(10, controller.spec.retry.poll_ms))
                continue
            status = controller.tick()
            if status != InteractionStatus.RUNNING:
                return status == InteractionStatus.SUCCESS
            yield from wait(max(10, controller.spec.retry.poll_ms))
    finally:
        if not controller.finished:
            controller.cancel("coroutine closed")


def run_boundary_coroutine_adapter(
    controller: InteractionBoundaryController,
    wait: Callable[[int], Generator[Any, Any, Any]],
) -> Generator[Any, Any, bool]:
    """Run the complete route boundary and interaction in a coroutine/FSM state."""

    try:
        while True:
            if _boundary_should_defer_for_auxiliary(controller):
                yield from wait(max(10, controller.spec.interaction.retry.poll_ms))
                continue
            status = controller.tick()
            if status != InteractionStatus.RUNNING:
                return status == InteractionStatus.SUCCESS
            yield from wait(max(10, controller.spec.interaction.retry.poll_ms))
    finally:
        if not controller.finished:
            controller.cancel("boundary coroutine closed")


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
            if target.kind == TargetKind.NONLIVING_NPC and not (
                Agent.IsNPC(agent_id) and not Agent.IsLiving(agent_id)
            ):
                continue
            if target.kind == TargetKind.GADGET and not Agent.IsGadget(agent_id):
                continue
            if target.kind == TargetKind.ITEM and not Agent.IsItem(agent_id):
                continue
            # Agent.GetModelID only resolves living agents. Ground-item agents
            # require item-agent id -> item model id translation.
            if target.model_id and self.agent_model_id(agent_id) != target.model_id:
                continue
            if target.gadget_id and int(Agent.GetGadgetID(agent_id) or 0) != target.gadget_id:
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

        if Agent.IsItem(agent_id):
            from Py4GWCoreLib.Item import Item

            item_id = int(Agent.GetItemAgentItemID(agent_id) or 0)
            if item_id <= 0:
                return 0
            return int(Item.GetModelID(item_id) or 0)
        return int(Agent.GetModelID(agent_id))

    def agent_gadget_id(self, agent_id: int) -> int:
        from Py4GWCoreLib.Agent import Agent

        if not Agent.IsGadget(agent_id):
            return 0
        return int(Agent.GetGadgetID(agent_id) or 0)

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

    def dialog_button_labels(self) -> tuple[str, ...]:
        from Py4GWCoreLib.Dialog import get_active_dialog_buttons

        labels: list[str] = []
        for button in get_active_dialog_buttons():
            decoded = str(getattr(button, "message_decoded", "") or "").strip()
            raw = str(getattr(button, "message", "") or "").strip()
            labels.append(decoded or raw)
        return tuple(labels)

    def scroll_dialog(self, delta: int) -> bool:
        import PyMouse

        from Py4GWCoreLib.FrameTree import Frame, FrameId

        dialog = Frame(FrameId.NpcDialog)
        if not dialog.exists or not dialog.is_visible:
            return False
        left, top, right, bottom = dialog.rect
        if right <= left or bottom <= top:
            return False
        x = int((left + right) / 2)
        y = int((top + bottom) / 2)
        PyMouse.PyMouse().Scroll(int(delta), x, y)
        return True

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


class BehaviorTreeBoundaryRouteExecutor:
    """Adapt an existing BottingTree route to the boundary controller."""

    def __init__(self, route_tree_factory: Callable[[tuple[tuple[float, float], ...], float], Any]):
        self.route_tree_factory = route_tree_factory
        self.route_tree: Any = None

    def start(
        self,
        route_points: tuple[tuple[float, float], ...],
        tolerance: float,
        _handoff_ready: Callable[[], bool],
    ) -> None:
        if self.route_tree is not None:
            raise RuntimeError("BottingTree boundary route was started more than once")
        self.route_tree = self.route_tree_factory(route_points, tolerance)

    def tick(self) -> InteractionStatus:
        if self.route_tree is None:
            raise RuntimeError("BottingTree boundary route was ticked before start")
        state = self.route_tree.tick()
        state_name = getattr(state, "name", "")
        if state_name == "RUNNING":
            return InteractionStatus.RUNNING
        if state_name == "SUCCESS":
            return InteractionStatus.SUCCESS
        return InteractionStatus.FAILURE

    def cancel(self) -> None:
        if self.route_tree is not None:
            self.route_tree.reset()
            self.route_tree = None


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
        if controller.stage == "new" and _local_route_auxiliary_active():
            return BehaviorTree.NodeState.RUNNING
        status = controller.tick()
        if status == InteractionStatus.RUNNING:
            return BehaviorTree.NodeState.RUNNING
        if status == InteractionStatus.SUCCESS:
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(_ReliableInteractionActionNode(name=spec.name, action_fn=_tick, aftercast_ms=0))


def build_botting_tree_boundary_action(
    spec: InteractionBoundarySpec,
    runtime: InteractionRuntime,
    route_tree_factory: Callable[[tuple[tuple[float, float], ...], float], Any] | None = None,
):
    """Build a reset-safe BottingTree route-to-interaction composite."""

    from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree

    if route_tree_factory is None:
        from Py4GWCoreLib.routines_src.behaviourtrees_src.movement import BTMovement

        def route_tree_factory(
            route_points: tuple[tuple[float, float], ...],
            tolerance: float,
        ):
            return BTMovement.MovePath(list(route_points), tolerance=tolerance)

    def _new_controller() -> InteractionBoundaryController:
        return InteractionBoundaryController(
            spec,
            runtime,
            BehaviorTreeBoundaryRouteExecutor(route_tree_factory),
        )

    controller_box = [_new_controller()]

    class _InteractionBoundaryActionNode(BehaviorTree.ActionNode):
        def reset(self) -> None:
            controller = controller_box[0]
            if not controller.finished:
                controller.cancel("BottingTree boundary node reset")
            controller_box[0] = _new_controller()
            super().reset()

    def _tick() -> BehaviorTree.NodeState:
        if _boundary_should_defer_for_auxiliary(controller_box[0]):
            return BehaviorTree.NodeState.RUNNING
        status = controller_box[0].tick()
        if status == InteractionStatus.RUNNING:
            return BehaviorTree.NodeState.RUNNING
        if status == InteractionStatus.SUCCESS:
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.FAILURE

    return BehaviorTree(
        _InteractionBoundaryActionNode(
            name=spec.name,
            action_fn=_tick,
            aftercast_ms=0,
        )
    )
