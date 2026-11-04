"""Bounded, non-BT blessing lifecycle for captured Simple Vanquish routes.

This is deliberately separate from ``Blessing_Core.BlessingRunner``.  The
legacy Blessed widget keeps its existing owner and behaviour; Simple Vanquish
opts into this runner explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Mapping, Protocol

BUILD_ID = "simple-vanquish-captured-blessing-v5-live-final-approach-20261028"
NORN_HUNTING_PARTY_EFFECT_IDS = frozenset((2469, 2470, 2471, 2472, 2551, 2591, 2592, 2593, 2594, 2595))
DEFAULT_APPROACH_TOLERANCE = 50.0
DEFAULT_INTERACTION_RANGE = 200.0


@dataclass(frozen=True)
class CapturedBlessingSpec:
    name: str
    interaction_mode: str
    target_xy: tuple[float, float]
    player_approach_xy: tuple[float, float]
    effect_ids: tuple[int, ...]
    model_id: int = 0
    target_name: str = ""
    search_radius: float = 350.0
    challenge_search_radius: float = 1200.0
    approach_tolerance: float = DEFAULT_APPROACH_TOLERANCE
    interaction_range: float = DEFAULT_INTERACTION_RANGE
    max_attempts: int = 3
    approach_timeout_s: float = 15.0
    dialog_timeout_s: float = 8.0
    result_timeout_s: float = 8.0
    challenge_timeout_s: float = 90.0
    response_settle_s: float = 6.0
    automatic_later_settle_s: float = 0.75
    norn_no_dialog_settle_s: float = 2.0
    friendly_settle_s: float = 0.75
    retry_delay_s: float = 1.0
    encoded_name: str = ""
    initial_choice_settle_s: float = 0.0
    visible_button_label: str = ""
    dialog_id: int = 0
    distance_override_reason: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CapturedBlessingSpec":
        distance_override_keys = ("approach_tolerance", "interaction_range")
        has_distance_override = any(key in value for key in distance_override_keys)
        distance_override_reason = str(value.get("distance_override_reason") or "").strip()
        if has_distance_override and not distance_override_reason:
            raise ValueError(
                "captured blessing distance overrides require distance_override_reason"
            )

        def positive_distance(key: str, default: float) -> float:
            raw_value = value.get(key, default)
            parsed = float(default if raw_value is None else raw_value)
            if not math.isfinite(parsed) or parsed <= 0.0:
                raise ValueError(f"{key} must be a positive finite distance")
            return parsed

        effect_ids = tuple(int(v) for v in value["effect_ids"])
        requested_mode = str(value.get("interaction_mode", "first"))
        # Older captured Norn routes label later hunters as ``refresh`` even
        # though each individual hunter may still require its prerequisite duel.
        # The owner, not every route file, normalizes that family invariant.
        interaction_mode = (
            "norn_challenge"
            if NORN_HUNTING_PARTY_EFFECT_IDS.intersection(effect_ids)
            else requested_mode
        )
        return cls(
            name=str(value["name"]),
            interaction_mode=interaction_mode,
            target_xy=tuple(float(v) for v in value["target_xy"]),
            player_approach_xy=tuple(float(v) for v in value["player_approach_xy"]),
            effect_ids=effect_ids,
            encoded_name=str(value.get("encoded_name") or ""),
            model_id=int(value.get("model_id", 0) or 0),
            target_name=str(value.get("target_name") or value.get("captured_target_name") or ""),
            search_radius=float(value.get("search_radius", 350.0) or 350.0),
            # These are global defaults. Route data may override either value
            # only for a documented geometry exception.
            approach_tolerance=positive_distance(
                "approach_tolerance", DEFAULT_APPROACH_TOLERANCE
            ),
            interaction_range=positive_distance(
                "interaction_range", DEFAULT_INTERACTION_RANGE
            ),
            initial_choice_settle_s=float(value.get("initial_choice_settle_s", 0.0) or 0.0),
            visible_button_label=str(value.get("visible_button_label") or ""),
            dialog_id=int(value.get("dialog_id", 0) or 0),
            distance_override_reason=distance_override_reason,
        )


class CapturedBlessingRuntime(Protocol):
    def now(self) -> float: ...
    def pause_automation(self) -> None: ...
    def enable_combat_automation(self) -> None: ...
    def restore_automation(self) -> None: ...
    def cancel_movement(self) -> None: ...
    def close_stale_dialog(self) -> None: ...
    def resolve_target(self, spec: CapturedBlessingSpec, search_radius: float | None = None) -> int: ...
    def player_xy(self) -> tuple[float, float]: ...
    def target_xy(self, agent_id: int) -> tuple[float, float]: ...
    def move(self, x: float, y: float) -> None: ...
    def interact(self, agent_id: int) -> None: ...
    def dialog_visible(self) -> bool: ...
    def dialog_button_count(self) -> int: ...
    def bind_visible_dialog_choice(self, agent_id: int, label: str) -> tuple[Any, ...] | None: ...
    def click_dialog_button(self, choice: int) -> bool: ...
    def send_dialog(self, dialog_id: int) -> bool: ...
    def effect_signature(self, effect_ids: tuple[int, ...]) -> tuple[tuple[int, int], ...]: ...
    def target_is_hostile(self, agent_id: int) -> bool: ...
    def emit(self, event: dict[str, Any]) -> None: ...


class CapturedBlessingRunner:
    """Poll-driven blessing transaction with an optional Norn challenge."""

    def __init__(self, runtime: CapturedBlessingRuntime, spec: CapturedBlessingSpec):
        self.runtime = runtime
        self.spec = spec
        self.state = "idle"
        self.attempt = 0
        self.deadline = 0.0
        self.settle_since = 0.0
        self.baseline_effects: tuple[tuple[int, int], ...] = ()
        self.challenge_seen = False
        self.done = False
        self.success = False
        self.reason = "not_started"
        self._restored = False
        self._last_move = 0.0
        self._dispatched_at = 0.0
        self._retry_phase = "initial"
        self._interaction_agent_id = 0
        self._visible_choice_binding: tuple[Any, ...] | None = None

    def start(self) -> None:
        if self.state != "idle":
            return
        self.runtime.pause_automation()
        self.runtime.cancel_movement()
        self._prepare_attempt_dialog()
        self.baseline_effects = self.runtime.effect_signature(self.spec.effect_ids)
        self.runtime.emit({
            "event": "start",
            "interaction": self.spec.name,
            "mode": self.spec.interaction_mode,
            "build_id": BUILD_ID,
        })
        self._begin_attempt("initial")

    def cancel(self) -> None:
        if not self.done:
            self._finish(False, "cancelled")
        else:
            self._restore()

    def update(self) -> tuple[bool, bool, str]:
        if self.state == "idle":
            self.start()
        if self.done:
            return True, self.success, self.reason

        now = self.runtime.now()
        try:
            if self.state in {"acquire", "final_acquire"}:
                self._tick_acquire(now, final=self.state == "final_acquire")
            elif self.state in {"approach", "final_approach"}:
                self._tick_approach(now, final=self.state == "final_approach")
            elif self.state in {"dialog", "final_dialog"}:
                self._tick_dialog(now, final=self.state == "final_dialog")
            elif self.state == "automatic_later":
                if now - self._dispatched_at >= self.spec.automatic_later_settle_s:
                    self._finish(True, "automatic_later_interaction_dispatched")
            elif self.state == "choice_result":
                self._tick_choice_result(now)
            elif self.state == "direct_dialog":
                self._tick_direct_dialog(now)
            elif self.state == "direct_dialog_result":
                self._tick_direct_dialog_result(now)
            elif self.state == "challenge":
                self._tick_challenge(now)
            elif self.state == "final_result":
                self._tick_final_result(now)
            elif self.state == "retry_wait" and now >= self.deadline:
                self._begin_attempt(self._retry_phase)
        except Exception as error:
            self.runtime.emit({"event": "exception", "error": f"{type(error).__name__}: {error}"})
            self._finish(False, "runtime_exception")
        return self.done, self.success, self.reason

    def _begin_attempt(self, phase: str) -> None:
        self.attempt += 1
        self.state = "final_acquire" if phase == "final" else "acquire"
        self.deadline = self.runtime.now() + self.spec.approach_timeout_s
        self.settle_since = 0.0
        self._interaction_agent_id = 0
        self._visible_choice_binding = None
        self._prepare_attempt_dialog()
        self.runtime.emit({"event": "attempt", "phase": phase, "attempt": self.attempt})

    def _prepare_attempt_dialog(self) -> None:
        self.runtime.close_stale_dialog()

    def _resolution_radius(self, final: bool) -> float | None:
        return None

    def _use_live_target_approach(self, final: bool) -> bool:
        return False

    def _tick_acquire(self, now: float, final: bool) -> None:
        agent_id = self.runtime.resolve_target(self.spec, self._resolution_radius(final))
        if agent_id > 0:
            self.runtime.emit({"event": "target_resolved", "agent_id": agent_id, "phase": "final" if final else "initial"})
            self.state = "final_approach" if final else "approach"
            self.deadline = now + self.spec.approach_timeout_s
            return
        if now >= self.deadline:
            self._retry_or_fail("target_not_found", final=final)

    def _tick_approach(self, now: float, final: bool) -> None:
        agent_id = self.runtime.resolve_target(self.spec, self._resolution_radius(final))
        if agent_id <= 0:
            if now >= self.deadline:
                self._retry_or_fail("target_lost", final=final)
            return
        player_xy = self.runtime.player_xy()
        approach_distance = math.dist(player_xy, self.spec.player_approach_xy)
        target_xy = self.runtime.target_xy(agent_id)
        target_distance = math.dist(player_xy, target_xy)
        use_live_target_approach = self._use_live_target_approach(final)
        approach_ready = (
            use_live_target_approach
            or approach_distance <= self.spec.approach_tolerance
        )
        if approach_ready and target_distance <= self.spec.interaction_range:
            self.runtime.interact(agent_id)
            self._interaction_agent_id = agent_id
            self.runtime.emit({"event": "interaction_dispatched", "agent_id": agent_id, "phase": "final" if final else "initial"})
            self._dispatched_at = now
            if not final and self.spec.dialog_id > 0:
                self.state = "direct_dialog"
            elif not final and self.spec.interaction_mode == "refresh":
                self.state = "automatic_later"
            else:
                self.state = "final_dialog" if final else "dialog"
            self.deadline = now + self.spec.dialog_timeout_s
            self.settle_since = 0.0
            return
        if now - self._last_move >= 0.5:
            destination = (
                target_xy
                if use_live_target_approach
                or approach_distance <= self.spec.approach_tolerance
                else self.spec.player_approach_xy
            )
            self.runtime.move(*destination)
            self._last_move = now
        if now >= self.deadline:
            self.runtime.emit({
                "event": "approach_timeout_diagnostic",
                "interaction": self.spec.name,
                "player_xy": player_xy,
                "player_approach_xy": self.spec.player_approach_xy,
                "target_xy": target_xy,
                "approach_distance": approach_distance,
                "approach_tolerance": self.spec.approach_tolerance,
                "target_distance": target_distance,
                "interaction_range": self.spec.interaction_range,
                "use_live_target_approach": use_live_target_approach,
                "attempt": self.attempt,
                "phase": "final" if final else "initial",
            })
            self._retry_or_fail("approach_timeout", final=final)

    def _tick_direct_dialog(self, now: float) -> None:
        if now - self._dispatched_at < self.spec.initial_choice_settle_s:
            return
        if not self.runtime.send_dialog(self.spec.dialog_id):
            self._retry_or_fail("direct_dialog_dispatch_failed", final=False)
            return
        self.runtime.emit({
            "event": "direct_dialog_dispatched",
            "dialog_id": self.spec.dialog_id,
            "phase": "initial",
        })
        self._dispatched_at = now
        self.state = "direct_dialog_result"

    def _tick_direct_dialog_result(self, now: float) -> None:
        if now - self._dispatched_at >= self.spec.automatic_later_settle_s:
            self._finish(True, "direct_dialog_dispatched")

    def _tick_dialog(self, now: float, final: bool) -> None:
        if not self.runtime.dialog_visible():
            self.settle_since = 0.0
            self._visible_choice_binding = None
            if (
                not final
                and self.spec.interaction_mode == "norn_challenge"
                and now - self._dispatched_at >= self.spec.norn_no_dialog_settle_s
            ):
                self._finish(True, "automatic_norn_later_interaction_dispatched")
                return
            if now >= self.deadline:
                self._retry_or_fail("dialog_timeout", final=final)
            return
        count = self.runtime.dialog_button_count()
        if count > 0:
            choice = 1
            if (
                not final
                and self.spec.initial_choice_settle_s > 0.0
                and self.spec.visible_button_label
            ):
                binding = self.runtime.bind_visible_dialog_choice(
                    self._interaction_agent_id,
                    self.spec.visible_button_label,
                )
                if binding is None:
                    self.settle_since = 0.0
                    self._visible_choice_binding = None
                    if now >= self.deadline:
                        self._retry_or_fail("visible_choice_not_bound", final=False)
                    return
                if binding != self._visible_choice_binding:
                    self._visible_choice_binding = binding
                    self.settle_since = now
                    self.runtime.emit({
                        "event": "visible_choice_bound",
                        "choice": int(binding[0]),
                        "label": self.spec.visible_button_label,
                        "settle_s": self.spec.initial_choice_settle_s,
                        "phase": "initial",
                    })
                    return
                if now - self.settle_since < self.spec.initial_choice_settle_s:
                    return
                choice = int(binding[0])
            if not self.runtime.click_dialog_button(choice):
                self._retry_or_fail("choice_dispatch_failed", final=final)
                return
            self.runtime.emit({"event": "choice_dispatched", "choice": choice, "phase": "final" if final else "initial"})
            self.settle_since = 0.0
            if final:
                self.state = "final_result"
                self.deadline = now + self.spec.result_timeout_s
            else:
                self.state = "choice_result"
                self.deadline = now + self.spec.result_timeout_s
            return
        if self.settle_since <= 0.0:
            self.settle_since = now
        elif now - self.settle_since >= self.spec.response_settle_s:
            self.runtime.emit({"event": "buttonless_response", "phase": "final" if final else "initial"})
            self._finish(True, "fresh_buttonless_response")

    def _tick_choice_result(self, now: float) -> None:
        signature = self.runtime.effect_signature(self.spec.effect_ids)
        if signature and signature != self.baseline_effects:
            self._finish(True, "blessing_effect_observed")
            return
        agent_id = self.runtime.resolve_target(self.spec)
        if agent_id > 0 and self.runtime.target_is_hostile(agent_id):
            self.challenge_seen = True
            self.runtime.enable_combat_automation()
            self.runtime.emit({"event": "challenge_started", "agent_id": agent_id})
            self.state = "challenge"
            self.deadline = now + self.spec.challenge_timeout_s
            self.settle_since = 0.0
            return
        if now >= self.deadline:
            self._finish(False, "choice_outcome_unobserved")

    def _tick_challenge(self, now: float) -> None:
        agent_id = self.runtime.resolve_target(self.spec, self.spec.challenge_search_radius)
        if agent_id > 0 and not self.runtime.target_is_hostile(agent_id):
            if self.settle_since <= 0.0:
                self.settle_since = now
            elif now - self.settle_since >= self.spec.friendly_settle_s:
                self.runtime.emit({"event": "challenge_finished", "agent_id": agent_id})
                self.runtime.pause_automation()
                self.runtime.cancel_movement()
                self.attempt = 0
                self._begin_attempt("final")
                return
        else:
            self.settle_since = 0.0
        if now >= self.deadline:
            self._finish(False, "challenge_timeout")

    def _tick_final_result(self, now: float) -> None:
        signature = self.runtime.effect_signature(self.spec.effect_ids)
        if signature:
            self._finish(True, "post_challenge_blessing_observed")
        elif self.runtime.dialog_visible() and self.runtime.dialog_button_count() == 0:
            if self.settle_since <= 0.0:
                self.settle_since = now
            elif now - self.settle_since >= self.spec.response_settle_s:
                self._finish(True, "post_challenge_buttonless_response")
        elif now >= self.deadline:
            self._finish(False, "post_challenge_outcome_unobserved")

    def _retry_or_fail(self, reason: str, final: bool) -> None:
        if self.attempt < self.spec.max_attempts:
            self.runtime.emit({"event": "attempt_failed", "reason": reason, "attempt": self.attempt})
            self.runtime.cancel_movement()
            self._prepare_attempt_dialog()
            self.state = "retry_wait"
            self.deadline = self.runtime.now() + self.spec.retry_delay_s
            # Final retries remain post-challenge and never replay the duel.
            self._retry_phase = "final" if final else "initial"
            return
        self._finish(False, reason)

    def _finish(self, success: bool, reason: str) -> None:
        self.done = True
        self.success = bool(success)
        self.reason = reason
        self.state = "done"
        self.runtime.cancel_movement()
        self._restore()
        self.runtime.emit({"event": "result", "success": self.success, "reason": reason})

    def _restore(self) -> None:
        if not self._restored:
            self.runtime.restore_automation()
            self._restored = True


class CanonicalCapturedBlessingRunner(CapturedBlessingRunner):
    """Named pilot owner for dispatch-only post-challenge Norn completion.

    Guild Wars can grant or upgrade a Norn blessing immediately after the
    post-duel interaction without exposing a durable dialogue page or a
    reliable effect/rank transition through the available APIs.  V1 remains
    unchanged; this candidate changes only that final no-dialog boundary and
    records that response/effect proof was unavailable.
    """

    def _prepare_attempt_dialog(self) -> None:
        # Successful blessing responses are dismissed naturally by subsequent
        # route movement.  ControlAction_CloseAllPanels is intentionally not
        # used by the canonical owner because it also closes unrelated player windows.
        return

    def _resolution_radius(self, final: bool) -> float | None:
        # Norn challengers may finish the duel well away from their captured
        # origin.  Reuse the already-bounded challenge radius when reacquiring
        # and approaching the friendly post-fight NPC.
        if final and self.spec.interaction_mode == "norn_challenge":
            return self.spec.challenge_search_radius
        return None

    def _use_live_target_approach(self, final: bool) -> bool:
        # After the duel, approach the reacquired actor's current coordinates.
        # Requiring the original player approach point at the same time can be
        # impossible when combat has displaced the NPC within the admitted
        # challenge search radius.
        return final and self.spec.interaction_mode == "norn_challenge"

    def _tick_dialog(self, now: float, final: bool) -> None:
        if (
            final
            and self.spec.interaction_mode == "norn_challenge"
            and not self.runtime.dialog_visible()
            and now - self._dispatched_at >= self.spec.norn_no_dialog_settle_s
        ):
            self.runtime.emit({
                "event": "post_challenge_no_dialog_dispatch_settled",
                "phase": "final",
                "response_observed": False,
                "effect_observed": False,
            })
            self._finish(True, "post_challenge_final_interaction_dispatched")
            return
        super()._tick_dialog(now, final)


class Py4GWCapturedBlessingRuntime:
    """Injected-game adapter; imports are lazy so the controller is unit-testable."""

    def __init__(self, bot: Any, diagnostic_sink=None):
        self.bot = bot
        self._sink = diagnostic_sink or (lambda _event: None)
        self._last_agent_sources: dict[str, Any] = {}
        self._last_resolution_diagnostic: tuple[Any, ...] | None = None
        self._hero_active = bool(bot.config.upkeep.hero_ai.is_active())
        paused = getattr(bot.config.upkeep, "hero_ai_paused", None)
        self._hero_paused = bool(paused is not None and paused.is_active())

    def now(self) -> float:
        return time.monotonic()

    def pause_automation(self) -> None:
        paused = getattr(self.bot.config.upkeep, "hero_ai_paused", None)
        if paused is not None:
            paused.set_now("active", True)
        else:
            self.bot.config.upkeep.hero_ai.set_now("active", False)

    def enable_combat_automation(self) -> None:
        self.bot.config.upkeep.hero_ai.set_now("active", True)
        paused = getattr(self.bot.config.upkeep, "hero_ai_paused", None)
        if paused is not None:
            paused.set_now("active", False)

    def restore_automation(self) -> None:
        paused = getattr(self.bot.config.upkeep, "hero_ai_paused", None)
        if paused is not None:
            paused.set_now("active", self._hero_paused)
        self.bot.config.upkeep.hero_ai.set_now("active", self._hero_active)

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

        sources: list[tuple[str, Any]] = [
            ("shared_all", AgentArray.GetAgentArray),
            ("shared_npc", AgentArray.GetNPCMinipetArray),
        ]
        source_counts: dict[str, int] = {}
        source_errors: dict[str, str] = {}
        candidates: list[int] = []

        try:
            context = GWContext.AgentArray.GetContext()
        except Exception as error:
            context = None
            source_errors["context"] = f"{type(error).__name__}: {error}"
        if context is not None:
            sources.extend([
                ("context_all", context.GetAgentArray),
                ("context_npc", context.GetNPCMinipetArray),
            ])

        for source_name, getter in sources:
            try:
                values = [int(agent_id) for agent_id in (getter() or []) if int(agent_id) > 0]
                source_counts[source_name] = len(values)
                candidates.extend(values)
            except Exception as error:
                source_counts[source_name] = 0
                source_errors[source_name] = f"{type(error).__name__}: {error}"

        self._last_agent_sources = {
            "counts": source_counts,
            "errors": source_errors,
        }
        return list(dict.fromkeys(candidates))

    def resolve_target(self, spec: CapturedBlessingSpec, search_radius: float | None = None) -> int:
        from Py4GWCoreLib.Agent import Agent
        best_id, best_distance = 0, float("inf")
        expected_encoded_name = spec.encoded_name
        expected_name = spec.target_name.casefold()
        radius = spec.search_radius if search_radius is None else float(search_radius)
        candidates = self._all_agents()
        valid_living = 0
        identity_matches = 0
        in_range = 0
        filter_errors = 0
        for agent_id in candidates:
            try:
                if not Agent.IsValid(agent_id) or not Agent.IsLiving(agent_id):
                    continue
                valid_living += 1
                if expected_encoded_name:
                    if Agent.GetEncNameStrByID(agent_id, literal=True) != expected_encoded_name:
                        continue
                else:
                    if spec.model_id and int(Agent.GetModelID(agent_id) or 0) != spec.model_id:
                        continue
                    if expected_name:
                        actual_name = str(Agent.GetNameByID(agent_id) or "").casefold()
                        if expected_name not in actual_name:
                            continue
                identity_matches += 1
                distance = math.dist(Agent.GetXY(agent_id), spec.target_xy)
                if distance <= radius:
                    in_range += 1
                    if distance < best_distance:
                        best_id, best_distance = int(agent_id), distance
            except Exception:
                filter_errors += 1
                continue
        diagnostic = (
            best_id,
            len(candidates),
            valid_living,
            identity_matches,
            in_range,
            filter_errors,
            tuple(sorted(self._last_agent_sources.get("counts", {}).items())),
            tuple(sorted(self._last_agent_sources.get("errors", {}).items())),
            radius,
        )
        if diagnostic != self._last_resolution_diagnostic:
            self._last_resolution_diagnostic = diagnostic
            self.emit({
                "event": "target_resolution_diagnostic",
                "interaction": spec.name,
                "resolved_agent_id": best_id,
                "candidate_count": len(candidates),
                "valid_living_count": valid_living,
                "identity_match_count": identity_matches,
                "in_range_count": in_range,
                "filter_error_count": filter_errors,
                "source_counts": dict(self._last_agent_sources.get("counts", {})),
                "source_errors": dict(self._last_agent_sources.get("errors", {})),
                "search_radius": radius,
            })
        return best_id

    def player_xy(self) -> tuple[float, float]:
        from Py4GWCoreLib.Player import Player
        return tuple(Player.GetXY())

    def target_xy(self, agent_id: int) -> tuple[float, float]:
        from Py4GWCoreLib.Agent import Agent
        return tuple(Agent.GetXY(agent_id))

    def move(self, x: float, y: float) -> None:
        from Py4GWCoreLib.Player import Player
        Player.Move(x, y)

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

    def bind_visible_dialog_choice(self, agent_id: int, label: str) -> tuple[Any, ...] | None:
        from Py4GWCoreLib.Dialog import get_active_dialog, get_active_dialog_buttons

        active = get_active_dialog()
        if active is None or int(active.agent_id or 0) != int(agent_id or 0):
            return None
        buttons = tuple(get_active_dialog_buttons() or ())
        keys = tuple(
            (
                int(button.dialog_id or 0),
                str(button.message_decoded or button.message or "").strip().casefold(),
                bool(button.message_decode_pending),
            )
            for button in buttons
        )
        wanted = str(label or "").strip().casefold()
        exact = [
            index
            for index, (dialog_id, decoded, pending) in enumerate(keys)
            if dialog_id > 0 and not pending and decoded == wanted
        ]
        if len(exact) != 1:
            return None
        return (
            exact[0] + 1,
            int(active.agent_id or 0),
            int(active.context_dialog_id or 0),
            keys,
        )

    def click_dialog_button(self, choice: int) -> bool:
        from Py4GWCoreLib.UIManager import UIManager
        return bool(UIManager.ClickDialogButton(choice, debug=False))

    def send_dialog(self, dialog_id: int) -> bool:
        from Py4GWCoreLib.Player import Player
        try:
            Player.SendDialog(int(dialog_id))
            return True
        except Exception:
            return False

    def effect_signature(self, effect_ids: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
        from Py4GWCoreLib import Effects
        from Py4GWCoreLib.Player import Player
        player_id = int(Player.GetAgentID() or 0)
        wanted = set(effect_ids)
        observed = set()
        for effect in [*(Effects.GetEffects(player_id) or []), *(Effects.GetBuffs(player_id) or [])]:
            skill_id = int(getattr(effect, "skill_id", 0) or 0)
            if skill_id in wanted:
                observed.add((skill_id, int(getattr(effect, "attribute_level", 0) or 0)))
        return tuple(sorted(observed))

    def target_is_hostile(self, agent_id: int) -> bool:
        from Py4GWCoreLib.Agent import Agent
        allegiance = Agent.GetAllegiance(agent_id)
        if isinstance(allegiance, tuple):
            code = allegiance[0] if allegiance else 0
            name = allegiance[1] if len(allegiance) > 1 else ""
            return int(code or 0) == 3 or str(name).strip().casefold() == "enemy"
        return int(allegiance or 0) == 3 or str(allegiance).strip().casefold() == "enemy"

    def emit(self, event: dict[str, Any]) -> None:
        self._sink(dict(event))
