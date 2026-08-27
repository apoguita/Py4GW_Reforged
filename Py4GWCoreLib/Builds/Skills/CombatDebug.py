"""Lightweight file logging and native name-tag colors for Simple-Power HeroAI.

This module deliberately has no ImGui panel.  It is controlled by static values
in :mod:`SimplePowerSettings` and is safe to leave loaded during normal play.
Only meaningful combat events are written, one file per account, so eight
multibox clients do not fight over the same log file.

Native colors use Reforged's ``PyAgentTagColor`` hook.  If the hook/module is
unavailable, logging continues and combat behavior is unaffected.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Final

from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill

# ARGB (0xAARRGGBB), as required by PyAgentTagColor.
COLOR_FOCUS: Final[int] = 0xFFFFFF00       # yellow
COLOR_DANGEROUS: Final[int] = 0xFFFF3030   # red
COLOR_CLAIMED: Final[int] = 0xFFFF00FF     # magenta/purple
COLOR_SUCCESS: Final[int] = 0xFF30FF60     # green
COLOR_ESCAPE: Final[int] = 0xFFFF9A20      # orange

PRIORITY_FOCUS: Final[int] = 100
PRIORITY_DANGEROUS: Final[int] = 300
PRIORITY_CLAIMED: Final[int] = 400
PRIORITY_SUCCESS: Final[int] = 500
PRIORITY_ESCAPE: Final[int] = 600

_DEFAULT_LOG_MAX_BYTES: Final[int] = 5 * 1024 * 1024


@dataclass
class _Marker:
    kind: str
    color: int
    priority: int
    expires_tick: int


@dataclass
class _InterruptAttempt:
    target_id: int
    enemy_skill_id: int
    our_skill_id: int
    fired_tick: int
    expected_finish_tick: int
    last_seen_same_cast_tick: int


_markers: dict[int, dict[str, _Marker]] = {}
_applied_color: dict[int, int] = {}
_original_agent_rules: dict[int, int | None] = {}
_interrupt_attempts: dict[tuple[int, int], _InterruptAttempt] = {}
_color_module = None
_color_checked = False
_last_color_check_tick = 0
_color_failure_logged = False
_last_rotation_check_tick = 0
_last_focus_log: tuple[int, int] = (0, 0)
_last_danger_log: dict[tuple[int, int], int] = {}
_pending_log_lines: list[str] = []
_last_log_flush_tick = 0
_LOG_FLUSH_INTERVAL_MS: Final[int] = 250
_LOG_FLUSH_MAX_LINES: Final[int] = 48


def _settings_enabled(name: str, default: bool) -> bool:
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        return bool(SimplePowerSettings.is_feature_enabled(name, default))
    except Exception:
        return bool(default)


def _settings_value(name: str, default):
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        return SimplePowerSettings.get_value(name, default)
    except Exception:
        return default


def _now_ms() -> int:
    try:
        import PySystem
        return int(PySystem.get_tick_count64() or 0)
    except Exception:
        return 0


def _safe_skill_name(skill_id: int) -> str:
    try:
        return str(Skill.GetName(int(skill_id)) or "?").strip() or "?"
    except Exception:
        return "?"


def _safe_agent_name(agent_id: int) -> str:
    try:
        if int(agent_id or 0) <= 0 or not Agent.IsValid(int(agent_id)):
            return "?"
        return str(Agent.GetNameByID(int(agent_id)) or "?").strip() or "?"
    except Exception:
        return "?"


def _account_slug() -> str:
    try:
        raw = str(Player.GetAccountEmail() or Player.GetName() or "unknown")
    except Exception:
        raw = "unknown"
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._")
    return slug[:80] or "unknown"


def get_log_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"HeroAI_Combat_Debug_{_account_slug()}.log"


def _rotate_if_needed(now: int) -> None:
    global _last_rotation_check_tick
    if now <= 0 or now - int(_last_rotation_check_tick) < 5000:
        return
    _last_rotation_check_tick = int(now)
    path = get_log_path()
    try:
        max_bytes = max(256 * 1024, int(_settings_value("combat_debug_log_max_bytes", _DEFAULT_LOG_MAX_BYTES)))
        if path.exists() and path.stat().st_size >= max_bytes:
            old = path.with_suffix(path.suffix + ".old")
            try:
                old.unlink(missing_ok=True)
            except Exception:
                pass
            path.replace(old)
    except Exception:
        pass


def flush_pending(*, force: bool = False) -> None:
    """Write queued combat lines in one batch instead of opening the file per event."""
    global _last_log_flush_tick
    if not _pending_log_lines:
        return
    now = _now_ms()
    if (
        not force
        and len(_pending_log_lines) < int(_LOG_FLUSH_MAX_LINES)
        and int(now) - int(_last_log_flush_tick) < int(_LOG_FLUSH_INTERVAL_MS)
    ):
        return
    lines = list(_pending_log_lines)
    _pending_log_lines.clear()
    _last_log_flush_tick = int(now)
    _rotate_if_needed(now)
    try:
        with get_log_path().open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except Exception:
        # Keep diagnostics best-effort; never put file I/O in the combat path.
        pass


def log_event(event: str, **fields) -> None:
    global _last_log_flush_tick
    if not _settings_enabled("combat_debug_file_log", True):
        return
    now = _now_ms()
    if int(_last_log_flush_tick) <= 0:
        _last_log_flush_tick = int(now)
    pieces = [f"[{int(now):012d}]", str(event)]
    for key, value in fields.items():
        text = str(value).replace("\n", " ").replace("\r", " ")
        pieces.append(f"{key}={text}")
    _pending_log_lines.append(" | ".join(pieces))
    flush_pending(force=len(_pending_log_lines) >= int(_LOG_FLUSH_MAX_LINES))


def _get_color_module():
    global _color_module, _color_checked, _last_color_check_tick, _color_failure_logged
    if not _settings_enabled("combat_debug_colors", True):
        return None
    now = _now_ms()
    if _color_module is not None:
        return _color_module
    # Native modules can become available only after the newest Reforged DLL
    # has been injected. Retry occasionally instead of permanently disabling
    # colors after one early import failure.
    if _color_checked and now > 0 and now - int(_last_color_check_tick) < 3000:
        return None
    _color_checked = True
    _last_color_check_tick = int(now)
    try:
        import PyAgentTagColor
        if not bool(PyAgentTagColor.is_hook_installed()):
            if not _color_failure_logged:
                log_event("DEBUG_COLOR_UNAVAILABLE", reason="hook_not_installed")
                _color_failure_logged = True
            return None
        PyAgentTagColor.enable()
        _color_module = PyAgentTagColor
        _color_failure_logged = False
        try:
            diag = dict(PyAgentTagColor.get_diagnostics() or {})
        except Exception:
            diag = {}
        log_event("DEBUG_COLOR_READY", diagnostics=diag)
    except Exception as exc:
        if not _color_failure_logged:
            log_event("DEBUG_COLOR_UNAVAILABLE", reason=repr(exc))
            _color_failure_logged = True
        _color_module = None
    return _color_module

def _valid_living_agent(agent_id: int) -> bool:
    try:
        return int(agent_id or 0) > 0 and Agent.IsValid(int(agent_id)) and Agent.IsAlive(int(agent_id))
    except Exception:
        return False


def _save_original_rule(agent_id: int, module) -> None:
    if int(agent_id) in _original_agent_rules:
        return
    try:
        rules = dict(module.get_agent_rules() or {})
        _original_agent_rules[int(agent_id)] = int(rules[int(agent_id)]) if int(agent_id) in rules else None
    except Exception:
        _original_agent_rules[int(agent_id)] = None


def _restore_agent(agent_id: int, module) -> None:
    previous = _original_agent_rules.pop(int(agent_id), None)
    try:
        if previous is None:
            module.remove_agent_color(int(agent_id))
        else:
            module.set_agent_color(int(agent_id), int(previous) & 0xFFFFFFFF)
    except Exception:
        pass
    _applied_color.pop(int(agent_id), None)


def _apply_best_marker(agent_id: int, now: int) -> None:
    module = _get_color_module()
    if module is None:
        return
    states = _markers.get(int(agent_id), {})
    for kind, marker in list(states.items()):
        if int(marker.expires_tick) <= int(now):
            states.pop(kind, None)
    if not states or not _valid_living_agent(int(agent_id)):
        _markers.pop(int(agent_id), None)
        if int(agent_id) in _applied_color:
            _restore_agent(int(agent_id), module)
        return
    best = max(states.values(), key=lambda marker: (int(marker.priority), int(marker.expires_tick)))
    if int(_applied_color.get(int(agent_id), -1)) == int(best.color):
        return
    try:
        _save_original_rule(int(agent_id), module)
        module.set_agent_color(int(agent_id), int(best.color) & 0xFFFFFFFF)
        _applied_color[int(agent_id)] = int(best.color)
    except Exception:
        pass


def mark_agent(agent_id: int, kind: str, color: int, priority: int, duration_ms: int) -> None:
    if not _settings_enabled("combat_debug_colors", True):
        return
    now = _now_ms()
    if now <= 0 or not _valid_living_agent(int(agent_id)):
        return
    states = _markers.setdefault(int(agent_id), {})
    states[str(kind)] = _Marker(
        kind=str(kind),
        color=int(color) & 0xFFFFFFFF,
        priority=int(priority),
        expires_tick=int(now) + max(100, int(duration_ms)),
    )
    _apply_best_marker(int(agent_id), now)


def mark_focus(agent_id: int, *, reason: str = "cluster") -> None:
    global _last_focus_log
    now = _now_ms()
    mark_agent(agent_id, "focus", COLOR_FOCUS, PRIORITY_FOCUS, 700)
    # Target selection may legitimately oscillate inside one cluster every frame.
    # Logging each change creates thousands of synchronous file writes and can
    # make movement/input feel delayed. Keep markers live, but rate-limit logs.
    if int(agent_id or 0) > 0 and now - int(_last_focus_log[1]) >= 800:
        _last_focus_log = (int(agent_id), int(now))
        log_event("FOCUS_TARGET", target_id=int(agent_id), target=_safe_agent_name(agent_id), reason=reason)


def mark_dangerous_cast(agent_id: int, skill_id: int, *, score: int | None = None) -> None:
    now = _now_ms()
    mark_agent(agent_id, "dangerous_cast", COLOR_DANGEROUS, PRIORITY_DANGEROUS, 500)
    key = (int(agent_id), int(skill_id))
    if now - int(_last_danger_log.get(key, 0)) >= 1500:
        _last_danger_log[key] = int(now)
        log_event(
            "DANGEROUS_CAST",
            caster_id=int(agent_id),
            caster=_safe_agent_name(agent_id),
            skill_id=int(skill_id),
            skill=_safe_skill_name(skill_id),
            score="?" if score is None else int(score),
        )


def mark_interrupt_claim(agent_id: int, enemy_skill_id: int, our_skill_id: int) -> None:
    mark_agent(agent_id, "interrupt_claim", COLOR_CLAIMED, PRIORITY_CLAIMED, 1400)
    log_event(
        "INTERRUPT_CLAIMED",
        caster_id=int(agent_id),
        caster=_safe_agent_name(agent_id),
        enemy_skill_id=int(enemy_skill_id),
        enemy_skill=_safe_skill_name(enemy_skill_id),
        our_skill_id=int(our_skill_id),
        our_skill=_safe_skill_name(our_skill_id),
    )


def register_interrupt_fired(target_id: int, enemy_skill_id: int, our_skill_id: int) -> None:
    now = _now_ms()
    if now <= 0:
        return
    try:
        from Py4GWCoreLib.Builds.Skills import CombatSense
        activation_ms = int(CombatSense.get_cast_activation_ms(int(enemy_skill_id), fallback_ms=1000))
        seen_ms = int(CombatSense.get_cast_seen_ms(int(target_id), int(enemy_skill_id)) or 0)
    except Exception:
        activation_ms, seen_ms = 1000, 0
    remaining = max(150, int(activation_ms) - max(0, int(seen_ms)))
    _interrupt_attempts[(int(target_id), int(enemy_skill_id))] = _InterruptAttempt(
        target_id=int(target_id),
        enemy_skill_id=int(enemy_skill_id),
        our_skill_id=int(our_skill_id),
        fired_tick=int(now),
        expected_finish_tick=int(now) + int(remaining),
        last_seen_same_cast_tick=int(now),
    )
    mark_agent(target_id, "interrupt_claim", COLOR_CLAIMED, PRIORITY_CLAIMED, min(1800, remaining + 500))
    log_event(
        "INTERRUPT_FIRED",
        caster_id=int(target_id),
        caster=_safe_agent_name(target_id),
        enemy_skill_id=int(enemy_skill_id),
        enemy_skill=_safe_skill_name(enemy_skill_id),
        our_skill_id=int(our_skill_id),
        our_skill=_safe_skill_name(our_skill_id),
        estimated_remaining_ms=int(remaining),
    )


def log_aoe_pending(skill_id: int, caster_id: int, center: tuple[float, float], confidence: str, commit_ms: int) -> None:
    log_event(
        "AOE_PENDING", caster_id=int(caster_id), caster=_safe_agent_name(caster_id),
        skill_id=int(skill_id), skill=_safe_skill_name(skill_id),
        center=f"{float(center[0]):.1f},{float(center[1]):.1f}",
        confidence=str(confidence), commit_ms=int(commit_ms),
    )


def log_aoe_cancelled(skill_id: int, caster_id: int, elapsed_ms: int, reason: str) -> None:
    log_event(
        "AOE_CAST_CANCELLED", caster_id=int(caster_id), caster=_safe_agent_name(caster_id),
        skill_id=int(skill_id), skill=_safe_skill_name(skill_id),
        elapsed_ms=int(elapsed_ms), reason=str(reason),
    )


def log_aoe_escape_skipped(skill_id: int, role: str, confidence: str, reason: str) -> None:
    log_event(
        "AOE_ESCAPE_SKIPPED", account=_account_slug(), role=str(role),
        skill_id=int(skill_id), skill=_safe_skill_name(skill_id),
        confidence=str(confidence), reason=str(reason),
    )


def log_aoe_escape_failed(skill_id: int, role: str, confidence: str, reason: str) -> None:
    log_event(
        "AOE_ESCAPE_FAILED", account=_account_slug(), role=str(role),
        skill_id=int(skill_id), skill=_safe_skill_name(skill_id),
        confidence=str(confidence), reason=str(reason),
    )


def log_aoe_zone(
    skill_id: int,
    caster_id: int,
    center: tuple[float, float],
    radius: float,
    confidence: str,
    critical: bool,
    *,
    provisional: bool = False,
    cast_started_tick: int = 0,
) -> None:
    log_event(
        "AOE_ZONE_ARMED",
        caster_id=int(caster_id),
        caster=_safe_agent_name(caster_id),
        skill_id=int(skill_id),
        skill=_safe_skill_name(skill_id),
        center=f"{float(center[0]):.1f},{float(center[1]):.1f}",
        radius=f"{float(radius):.1f}",
        confidence=str(confidence),
        critical=bool(critical),
        provisional=bool(provisional),
        cast_started_tick=int(cast_started_tick or 0),
    )


def mark_aoe_escape(skill_id: int, destination: tuple[float, float], role: str, confidence: str) -> None:
    try:
        player_id = int(Player.GetAgentID() or 0)
    except Exception:
        player_id = 0
    if player_id > 0:
        mark_agent(player_id, "aoe_escape", COLOR_ESCAPE, PRIORITY_ESCAPE, 1500)
    log_event(
        "AOE_ESCAPE",
        account=_account_slug(),
        role=str(role),
        skill_id=int(skill_id),
        skill=_safe_skill_name(skill_id),
        confidence=str(confidence),
        destination=f"{float(destination[0]):.1f},{float(destination[1]):.1f}",
    )


def log_aoe_return(role: str, destination: tuple[float, float]) -> None:
    log_event(
        "AOE_RETURN",
        account=_account_slug(),
        role=str(role),
        destination=f"{float(destination[0]):.1f},{float(destination[1]):.1f}",
    )


def tick() -> None:
    """Expire colors and infer interrupt outcomes from observed cast state.

    A true native interrupt event is not guaranteed by Reforged yet.  Results
    are therefore labelled ``likely_interrupted`` or ``completed_or_late`` and
    never presented as perfect ground truth.
    """
    now = _now_ms()
    if now <= 0:
        return

    for agent_id in list(_markers):
        _apply_best_marker(int(agent_id), now)

    for key, attempt in list(_interrupt_attempts.items()):
        target_id, enemy_skill_id = key
        native_outcome = None
        try:
            from Py4GWCoreLib.Builds.Skills.ReforgedSupport import get_cast_outcome
            native_outcome = get_cast_outcome(target_id, enemy_skill_id, attempt.fired_tick)
        except Exception:
            native_outcome = None
        if native_outcome is not None:
            result = f"native_{native_outcome}"
            log_event(
                "INTERRUPT_RESULT", result=result, caster_id=target_id,
                caster=_safe_agent_name(target_id), enemy_skill_id=enemy_skill_id,
                enemy_skill=_safe_skill_name(enemy_skill_id),
                our_skill=_safe_skill_name(attempt.our_skill_id),
                elapsed_ms=int(now) - int(attempt.fired_tick),
            )
            if native_outcome == "interrupted":
                mark_agent(target_id, "interrupt_success", COLOR_SUCCESS, PRIORITY_SUCCESS, 900)
            _interrupt_attempts.pop(key, None)
            continue
        if not _valid_living_agent(target_id):
            log_event(
                "INTERRUPT_RESULT",
                result="target_gone",
                caster_id=target_id,
                enemy_skill_id=enemy_skill_id,
                enemy_skill=_safe_skill_name(enemy_skill_id),
                our_skill=_safe_skill_name(attempt.our_skill_id),
            )
            _interrupt_attempts.pop(key, None)
            continue
        try:
            is_same = bool(Agent.IsCasting(target_id)) and int(Agent.GetCastingSkillID(target_id) or 0) == int(enemy_skill_id)
        except Exception:
            is_same = False
        if is_same:
            attempt.last_seen_same_cast_tick = int(now)
            if now <= int(attempt.expected_finish_tick) + 650:
                continue
            log_event(
                "INTERRUPT_RESULT",
                result="missed_or_too_late",
                caster_id=target_id,
                caster=_safe_agent_name(target_id),
                enemy_skill_id=enemy_skill_id,
                enemy_skill=_safe_skill_name(enemy_skill_id),
                our_skill=_safe_skill_name(attempt.our_skill_id),
            )
            _interrupt_attempts.pop(key, None)
            continue

        stopped_early = int(now) < int(attempt.expected_finish_tick) - 80
        result = "likely_interrupted" if stopped_early else "completed_or_late"
        log_event(
            "INTERRUPT_RESULT",
            result=result,
            caster_id=target_id,
            caster=_safe_agent_name(target_id),
            enemy_skill_id=enemy_skill_id,
            enemy_skill=_safe_skill_name(enemy_skill_id),
            our_skill=_safe_skill_name(attempt.our_skill_id),
            elapsed_ms=int(now) - int(attempt.fired_tick),
        )
        if stopped_early:
            mark_agent(target_id, "interrupt_success", COLOR_SUCCESS, PRIORITY_SUCCESS, 900)
        _interrupt_attempts.pop(key, None)


def clear_debug_colors() -> None:
    module = _get_color_module()
    if module is not None:
        for agent_id in list(_applied_color):
            _restore_agent(int(agent_id), module)
    _markers.clear()


# --- Finalization: interrupt outcome confirmation ----------------------------
_interrupt_fired_pending = {}

def register_interrupt_fired(target_id: int, enemy_skill_id: int, source_skill_id: int) -> None:
    """Record a possible interrupt and verify outcome on subsequent ticks.

    This is diagnostic only and never affects combat decisions.
    """
    try:
        now = int(get_game_tick() or 0)
    except Exception:
        now = 0
    _interrupt_fired_pending[(int(target_id), int(enemy_skill_id), int(source_skill_id))] = now

def verify_interrupt_outcomes() -> None:
    """Classify recent fired interrupts as confirmed/stopped/unknown.

    Uses live casting state after the cast; this measures accidental interrupts
    from MAX-SPAM as well as deliberate ones without reserving skills.
    """
    try:
        from Py4GWCoreLib.Agent import Agent
    except Exception:
        return
    try:
        now = int(get_game_tick() or 0)
    except Exception:
        now = 0

    done = []
    for key, fired_tick in list(_interrupt_fired_pending.items()):
        target_id, enemy_skill_id, source_skill_id = key
        age = now - int(fired_tick or 0)
        if age < 100:
            continue
        try:
            casting = bool(Agent.IsCasting(target_id))
            current_skill = int(Agent.GetCastingSkill(target_id) or 0)
        except Exception:
            casting = False
            current_skill = 0

        if age <= 900 and (not casting or current_skill != enemy_skill_id):
            log_event(
                "INTERRUPT_OUTCOME_CONFIRMED",
                target_id=int(target_id),
                enemy_skill_id=int(enemy_skill_id),
                source_skill_id=int(source_skill_id),
                outcome="observed_cast_stop_after_signet",
                latency_ms=int(age),
            )
            done.append(key)
        elif age > 1200:
            log_event(
                "INTERRUPT_OUTCOME_CONFIRMED",
                target_id=int(target_id),
                enemy_skill_id=int(enemy_skill_id),
                source_skill_id=int(source_skill_id),
                outcome="unknown_or_finished",
                latency_ms=int(age),
            )
            done.append(key)
    for key in done:
        _interrupt_fired_pending.pop(key, None)
