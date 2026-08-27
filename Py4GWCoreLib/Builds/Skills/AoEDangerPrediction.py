from __future__ import annotations

import math
from dataclasses import dataclass

from Py4GWCoreLib import AgentArray, Range
from Py4GWCoreLib.Agent import Agent
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Skill import Skill

# Lightweight cast-prediction based AoE avoidance.
# Py4GW currently does not expose full active ground-effect data, so this helper
# predicts temporary danger zones from enemy casts that are likely to create
# dangerous persistent AoE fields.  It does NOT react immediately on cast start:
# a pending cast must reach the commit window first, which avoids pointless
# movement when the team's interrupt logic stops the cast.
AOE_SCAN_THROTTLE_MS = 75
AOE_PENDING_TIMEOUT_MS = 6500
AOE_AVOID_COOLDOWN_MS = 700
AOE_ESCAPE_RETARGET_COOLDOWN_MS = 1600
AOE_ESCAPE_STALL_REISSUE_MS = 1100
AOE_ESCAPE_PROGRESS_EPSILON = 24.0
AOE_ESCAPE_ARRIVAL_DISTANCE = 90.0
AOE_SAFE_HOLD_ACTION_DISTANCE = 180.0
AOE_ESCAPE_RELEASE_PADDING = 70.0
AOE_ESCAPE_PATH_PADDING = 95.0
AOE_MIN_MOVE_DISTANCE = 300.0
AOE_DEFAULT_MOVE_DISTANCE = 520.0
AOE_MAX_MOVE_DISTANCE = 720.0
AOE_SAFE_ESCAPE_SCAN_RANGE = Range.Spirit.value
AOE_SAFE_ESCAPE_ENEMY_HARD_RADIUS = Range.Area.value + 80.0
AOE_SAFE_ESCAPE_ENEMY_SOFT_RADIUS = Range.Earshot.value
AOE_SAFE_ESCAPE_AOE_PADDING = 110.0
AOE_FINAL_INTERRUPT_GRACE_MS = 45
# V9 two-stage commit: prepare the escape decision early, but do not move until
# the cast is essentially complete.  If a coordinated interrupt is claimed,
# wait for the native outcome instead of issuing a speculative movement command.
AOE_PREPARE_FRACTION_DEFAULT = 0.90
AOE_FINAL_MOVE_LEAD_MS_DEFAULT = 70
AOE_METEOR_MOVE_LEAD_MS_DEFAULT = 120
AOE_SHORT_CAST_MOVE_LEAD_MS_DEFAULT = 55
AOE_INTERRUPT_OUTCOME_GRACE_MS_DEFAULT = 340
AOE_GENERAL_OUTCOME_GRACE_MS_DEFAULT = 125
AOE_CAST_OVERRUN_FAILSAFE_MS_DEFAULT = 260


@dataclass(frozen=True, slots=True)
class AoESpec:
    skill_names: tuple[str, ...]
    radius: float
    duration_ms: int
    fallback_cast_ms: int
    commit_fraction: float = 0.78
    critical: bool = True
    placement: str = "targeted"  # targeted | caster | ground


@dataclass(slots=True)
class PendingAoECast:
    caster_id: int
    skill_id: int
    started_tick: int
    last_seen_tick: int
    center: tuple[float, float]
    confidence: str = "medium"
    committed: bool = False
    # ``prearmed`` now means "escape prepared", not "movement already active".
    # This keeps the 90% planning point without recreating the unnecessary
    # movement seen in the V5-V8 logs.
    prearmed: bool = False
    interrupt_deferred_logged: bool = False
    commit_ready_tick: int = 0
    last_interrupt_claim_tick: int = 0
    disappeared_tick: int = 0
    outcome_grace_logged: bool = False


@dataclass(slots=True)
class ActiveAoEZone:
    skill_id: int
    caster_id: int
    center: tuple[float, float]
    radius: float
    expires_tick: int
    critical: bool = True
    confidence: str = "medium"  # high | medium | low
    cast_started_tick: int = 0
    provisional: bool = False


@dataclass(slots=True)
class AoEReturnState:
    active: bool = False
    origin: tuple[float, float] | None = None
    follow_anchor: tuple[float, float] | None = None
    escape_destination: tuple[float, float] | None = None
    zone_key: tuple[int, int, int] | None = None
    escaped_tick: int = 0
    last_escape_command_tick: int = 0
    last_retarget_tick: int = 0
    role: str = "generic"
    safe_hold_actions_logged: bool = False
    best_escape_distance: float = 0.0
    last_progress_tick: int = 0


_AOE_SPECS: tuple[AoESpec, ...] = (
    AoESpec(("Meteor_Shower",), Range.Area.value, 9200, 5000, 0.78, True, "targeted"),
    AoESpec(("Savannah_Heat",), Range.Area.value, 5200, 2000, 0.78, True, "targeted"),
    AoESpec(("Searing_Heat",), Range.Area.value, 5200, 2000, 0.78, True, "targeted"),
    AoESpec(("Teinais_Heat", "Teinai's_Heat"), Range.Area.value, 5200, 2000, 0.78, True, "targeted"),
    AoESpec(("Bed_of_Coals",), Range.Adjacent.value, 5600, 1000, 0.78, True, "targeted"),
    AoESpec(("Ray_of_Judgment",), Range.Area.value, 5200, 2000, 0.78, True, "targeted"),
    # Reforged currently may expose the cast without the ground coordinates for
    # these fields.  Their fallback center is therefore low-confidence.
    AoESpec(("Fire_Storm",), Range.Area.value, 9800, 2000, 0.78, True, "ground"),
    AoESpec(("Maelstrom",), Range.Area.value, 10500, 2000, 0.78, True, "ground"),
    AoESpec(("Churning_Earth",), Range.Area.value, 6000, 2000, 0.78, True, "targeted"),
    AoESpec(("Sandstorm",), Range.Area.value, 10000, 2000, 0.78, True, "targeted"),
    AoESpec(("Eruption",), Range.Area.value, 6200, 2000, 0.78, True, "targeted"),
    AoESpec(("Deep_Freeze",), Range.Area.value, 4200, 3000, 0.78, False, "targeted"),
    AoESpec(("Unsteady_Ground",), Range.Area.value, 6200, 2000, 0.78, True, "targeted"),
    AoESpec(("Ward_Against_Foes", "Ward_Against_Melee", "Ward_Against_Harm", "Ward_Against_Elements"), Range.Area.value, 8500, 1000, 0.80, False, "caster"),
)


def _build_spec_map() -> dict[int, AoESpec]:
    specs: dict[int, AoESpec] = {}
    for spec in _AOE_SPECS:
        for name in spec.skill_names:
            try:
                skill_id = int(Skill.GetID(name) or 0)
            except Exception:
                skill_id = 0
            if skill_id > 0:
                specs[skill_id] = spec
    return specs


_AOE_SPEC_BY_SKILL_ID: dict[int, AoESpec] = _build_spec_map()
_PENDING_CASTS: dict[tuple[int, int], PendingAoECast] = {}
_ACTIVE_ZONES: list[ActiveAoEZone] = []
_LAST_SCAN_TICK: int = 0
_LAST_AVOID_TICK: int = 0
_RETURN_STATE = AoEReturnState()


# ST-specific danger classification.  The Ritualist should never plant long
# binding rituals inside a confirmed persistent field.  Knockdown/control
# fields are distinguished so the ST can use I Am Unstoppable before escaping,
# then rebuild or rescue spirits from the stable safe hold point.
_ST_REPEATED_KNOCKDOWN_NAMES = {"Meteor_Shower"}
_ST_KNOCKDOWN_NAMES = {"Bed_of_Coals", "Churning_Earth", "Unsteady_Ground"}
_ST_INTERRUPT_FIELD_NAMES = {"Maelstrom"}


def _skill_id_matches_names(skill_id: int, names: set[str]) -> bool:
    sid = int(skill_id or 0)
    if sid <= 0:
        return False
    for name in names:
        try:
            if int(Skill.GetID(name) or 0) == sid:
                return True
        except Exception:
            continue
    return False


def get_player_active_aoe_context(
    *,
    padding: float = 60.0,
    critical_only: bool = True,
) -> dict[str, object] | None:
    """Return the active danger field currently covering the local player.

    The result is intentionally a plain dict so build modules can consume it
    without depending on the private ActiveAoEZone dataclass.
    """
    player_xy = _player_xy()
    if not player_xy:
        return None
    zone = _active_zone_at_position(
        player_xy,
        padding=float(padding),
        critical_only=bool(critical_only),
    )
    if zone is None:
        return None

    control = "damage"
    if _skill_id_matches_names(zone.skill_id, _ST_REPEATED_KNOCKDOWN_NAMES):
        control = "repeated_knockdown"
    elif _skill_id_matches_names(zone.skill_id, _ST_KNOCKDOWN_NAMES):
        control = "knockdown"
    elif _skill_id_matches_names(zone.skill_id, _ST_INTERRUPT_FIELD_NAMES):
        control = "interrupt_field"

    now = get_game_tick()
    remaining_ms = max(0, int(zone.expires_tick) - int(now or 0)) if now > 0 else 0
    return {
        "skill_id": int(zone.skill_id),
        "caster_id": int(zone.caster_id),
        "control": control,
        "remaining_ms": int(remaining_ms),
        "critical": bool(zone.critical),
        "confidence": str(zone.confidence),
        "provisional": bool(zone.provisional),
    }


def is_aoe_escape_safe_hold_active(*, role: str | None = None) -> bool:
    """True when the account is safely outside the AoE near its hold point.

    Normal follow remains blocked until the route back to formation is safe,
    but build rotations may cast from this hold point.  A wider action radius
    than the exact movement-arrival radius avoids idle accounts when collision
    or pathing stops them slightly short of the calculated coordinate.
    """
    if not _RETURN_STATE.active or _RETURN_STATE.escape_destination is None:
        return False
    # Escape state is local to one account.  The optional role argument is kept
    # for call-site clarity but must not reject a state that was first created
    # by the generic follower before the build-specific ST tick ran.
    del role
    player_xy = _player_xy()
    if not player_xy:
        return False
    if _active_zone_at_position(
        player_xy,
        padding=AOE_ESCAPE_RELEASE_PADDING,
        critical_only=False,
    ) is not None:
        return False
    action_distance = float(AOE_SAFE_HOLD_ACTION_DISTANCE)
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        action_distance = float(SimplePowerSettings.get_value(
            "aoe_safe_hold_action_distance", action_distance
        ))
    except Exception:
        pass
    return _distance(player_xy, _RETURN_STATE.escape_destination) <= max(
        AOE_ESCAPE_ARRIVAL_DISTANCE + 35.0, action_distance
    )


def get_game_tick() -> int:
    """Return the Reforged monotonic game/runtime tick in milliseconds.

    Reforged exposes ``get_tick_count64`` through ``PySystem``.  Older builds
    also exposed it through ``Py4GW.Game``.  The previous AoE helper only tried
    the legacy path and silently returned 0 on Reforged, which disabled every
    pending-zone, active-zone and escape check without producing a traceback.
    """
    try:
        import PySystem
        tick = int(PySystem.get_tick_count64() or 0)
        if tick > 0:
            return tick
    except Exception:
        pass
    try:
        import Py4GW
        return int(Py4GW.Game.get_tick_count64() or 0)
    except Exception:
        return 0


def _dist_sq(a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay = a
    bx, by = b
    dx = float(ax) - float(bx)
    dy = float(ay) - float(by)
    return dx * dx + dy * dy


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.sqrt(_dist_sq(a, b))


def _safe_xy_for_agent(agent_id: int) -> tuple[float, float] | None:
    try:
        if int(agent_id or 0) <= 0 or not Agent.IsValid(int(agent_id)):
            return None
        xy = Agent.GetXY(int(agent_id))
        if not xy:
            return None
        return (float(xy[0]), float(xy[1]))
    except Exception:
        return None


def _player_xy() -> tuple[float, float] | None:
    try:
        xy = Player.GetXY()
        if not xy:
            return None
        return (float(xy[0]), float(xy[1]))
    except Exception:
        return None


def _nearest_living_ally_to_caster(caster_id: int) -> tuple[float, float] | None:
    """Best available fallback for target/ground casts without exposed coordinates.

    Using each local account position as the center made every client create a
    different danger zone.  Reforged often exposes no ground X/Y, so use the
    living ally nearest to the caster as one shared, deterministic estimate.
    """
    caster_xy = _safe_xy_for_agent(int(caster_id))
    if not caster_xy:
        return None
    try:
        allies = AgentArray.GetAllyArray()
    except Exception:
        allies = []
    best_xy = None
    best_dist = float("inf")
    for ally_id in allies or []:
        try:
            ally_id = int(ally_id or 0)
            if ally_id <= 0 or not Agent.IsValid(ally_id) or not Agent.IsAlive(ally_id):
                continue
            ally_xy = _safe_xy_for_agent(ally_id)
            if not ally_xy:
                continue
            dist = _dist_sq(caster_xy, ally_xy)
            if dist < best_dist:
                best_dist = dist
                best_xy = ally_xy
        except Exception:
            continue
    return best_xy


def _estimate_aoe_center(caster_id: int, spec: AoESpec) -> tuple[tuple[float, float], str] | None:
    """Return (center, confidence) for a predicted AoE.

    Confidence rules:
    - high: explicit target coordinates or a known caster-centered skill
    - medium: target-centered spell with no target exposed; local position used
    - low: true ground-target spell with no ground coordinates exposed
    """
    if str(spec.placement) == "caster":
        caster_xy = _safe_xy_for_agent(int(caster_id))
        return (caster_xy, "high") if caster_xy else None

    try:
        from Py4GWCoreLib.Builds.Skills.ReforgedSupport import get_cast_target_id
        current_skill_id = int(Agent.GetCastingSkillID(int(caster_id)) or 0)
        target_id = int(get_cast_target_id(int(caster_id), current_skill_id) or 0)
    except Exception:
        target_id = 0
    if target_id <= 0:
        try:
            target_id = int(Agent.GetTarget(int(caster_id)) or 0)
        except Exception:
            target_id = 0
    if target_id > 0:
        target_xy = _safe_xy_for_agent(target_id)
        if target_xy:
            return (target_xy, "high")

    try:
        from Py4GWCoreLib.Builds.Skills import CombatSense
        _ = CombatSense.get_enemy_sense(int(caster_id), range_value=Range.Spellcast.value)
    except Exception:
        pass

    # Reforged currently does not reliably expose ground X/Y.  Use one
    # deterministic team estimate instead of centering the zone on each local
    # account.  This is substantially better for Fire Storm / Maelstrom and
    # targeted AoEs whose target_id is missing.
    fallback = _nearest_living_ally_to_caster(int(caster_id))
    if fallback:
        return (fallback, "medium")
    fallback = _player_xy()
    if not fallback:
        return None
    return (fallback, "low")


def _cast_activation_ms(skill_id: int, spec: AoESpec, caster_id: int = 0) -> int:
    # Native CASTTIME contains the real duration after Fast Casting and other
    # activation modifiers.  Use it whenever the event bridge captured it so
    # the 90% commit point is based on this exact cast, not only base skill data.
    if int(caster_id or 0) > 0:
        try:
            from Py4GWCoreLib.Builds.Skills import ReforgedSupport
            native_ms = int(ReforgedSupport.get_cast_duration_ms(
                int(caster_id), int(skill_id)
            ) or 0)
            if native_ms > 0:
                return max(1, int(native_ms))
        except Exception:
            pass
    try:
        activation_s = float(Skill.Data.GetActivation(int(skill_id)) or 0.0)
        if activation_s > 0:
            return max(250, int(activation_s * 1000))
    except Exception:
        pass
    return int(spec.fallback_cast_ms)



def _native_cast_info(caster_id: int, skill_id: int) -> tuple[int, int] | None:
    """Return (start_tick, target_id) from Reforged raw events when available."""
    try:
        from Py4GWCoreLib.Builds.Skills.ReforgedSupport import get_recent_cast
        cast = get_recent_cast(int(caster_id), max_age_ms=8000)
        if not cast or int(cast[0]) != int(skill_id):
            return None
        return int(cast[2] or 0), int(cast[1] or 0)
    except Exception:
        return None


def _confidence_rank(value: str) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(str(value or "low").lower(), 0)


def _confidence_allowed_for_role(confidence: str, role: str, *, critical: bool) -> bool:
    del role  # Role-specific movement was deliberately removed with global spread.
    confidence = str(confidence or "low").lower()
    if confidence == "high":
        return True
    if confidence == "medium":
        return bool(critical)
    # Never move an account from a purely local/guessed center.  A wrong escape
    # command costs more than a weak field and can pull the account into a pack.
    return False


def _normalize_cast_outcome(outcome: str | None) -> str:
    value = str(outcome or "").strip().lower()
    if value.startswith("native_"):
        value = value[7:]
    return value


def _has_live_interrupt_claim(caster_id: int, skill_id: int, now_tick: int) -> bool:
    """Best-effort check for a shared interrupt already committed to this cast.

    A live claim postpones *pre-arming* the danger zone.  If the cast still
    finishes, the zone is confirmed immediately from the native finish event.
    This prevents unnecessary movement when Power Drain/Keystone is already on
    the way without ever trusting the claim as proof that the cast was stopped.
    """
    try:
        from Py4GWCoreLib import GLOBAL_CACHE
        from Py4GWCoreLib.enums_src.Whiteboard_enums import WhiteboardLockKind

        all_accounts = GLOBAL_CACHE.ShMem.GetAllAccounts()
        if hasattr(GLOBAL_CACHE.ShMem, "SweepExpiredIntents"):
            GLOBAL_CACHE.ShMem.SweepExpiredIntents(int(now_tick))
        for _, intent in all_accounts.GetActiveIntents() or []:
            if int(getattr(intent, "ExpiresAtTick", 0) or 0) <= int(now_tick):
                continue
            if int(getattr(intent, "KindID", 0) or 0) != int(WhiteboardLockKind.INTERRUPT_TARGET):
                continue
            if int(getattr(intent, "TargetAgentID", 0) or 0) != int(caster_id):
                continue
            if int(getattr(intent, "SkillID", 0) or 0) != int(skill_id):
                continue
            return True
    except Exception:
        pass
    return False


def _prepare_lead_ms(skill_id: int, spec: AoESpec, cast_ms: int) -> int:
    """Return the planning window; this stage never owns movement.

    V9 computes/logs the escape at roughly 90% cast progress but delays the
    actual zone arming until the final command window.  The split is essential:
    the old implementation treated the planning threshold as permission to move.
    """
    del skill_id
    if not bool(spec.critical):
        return 0
    prepare_fraction = float(AOE_PREPARE_FRACTION_DEFAULT)
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        prepare_fraction = float(SimplePowerSettings.get_value(
            "aoe_escape_prepare_fraction",
            SimplePowerSettings.get_value("aoe_escape_commit_fraction", prepare_fraction),
        ))
    except Exception:
        pass
    prepare_fraction = max(0.82, min(0.96, float(prepare_fraction)))
    return max(1, int(int(cast_ms) * (1.0 - prepare_fraction)))


def _final_move_lead_ms(skill_id: int, spec: AoESpec, cast_ms: int) -> int:
    """Return how shortly before an unclaimed cast may trigger movement.

    These windows are deliberately tiny.  With the 75 ms scan throttle they
    normally produce a command at the last frame before completion or directly
    after completion.  A live coordinated interrupt claim suppresses this stage
    completely and is resolved through the native cast outcome instead.
    """
    if not bool(spec.critical):
        return 0
    normal_lead = int(AOE_FINAL_MOVE_LEAD_MS_DEFAULT)
    meteor_lead = int(AOE_METEOR_MOVE_LEAD_MS_DEFAULT)
    short_lead = int(AOE_SHORT_CAST_MOVE_LEAD_MS_DEFAULT)
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        normal_lead = int(SimplePowerSettings.get_value("aoe_escape_final_move_lead_ms", normal_lead))
        meteor_lead = int(SimplePowerSettings.get_value("aoe_escape_meteor_move_lead_ms", meteor_lead))
        short_lead = int(SimplePowerSettings.get_value("aoe_escape_short_cast_move_lead_ms", short_lead))
    except Exception:
        pass
    normal_lead = max(0, min(180, normal_lead))
    meteor_lead = max(0, min(260, meteor_lead))
    short_lead = max(0, min(120, short_lead))
    try:
        meteor_shower_id = int(Skill.GetID("Meteor_Shower") or 0)
    except Exception:
        meteor_shower_id = 0
    if meteor_shower_id > 0 and int(skill_id) == meteor_shower_id:
        return int(meteor_lead)
    if int(cast_ms) <= 1200:
        return int(short_lead)
    return int(normal_lead)


def _outcome_grace_ms(pending: PendingAoECast, now_tick: int) -> int:
    recent_claim = (
        int(pending.last_interrupt_claim_tick or 0) > 0
        and int(now_tick) - int(pending.last_interrupt_claim_tick) <= 900
    )
    default = (
        int(AOE_INTERRUPT_OUTCOME_GRACE_MS_DEFAULT)
        if recent_claim
        else int(AOE_GENERAL_OUTCOME_GRACE_MS_DEFAULT)
    )
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        key = (
            "aoe_escape_interrupt_outcome_grace_ms"
            if recent_claim
            else "aoe_escape_general_outcome_grace_ms"
        )
        default = int(SimplePowerSettings.get_value(key, default))
    except Exception:
        pass
    return max(0, min(650, int(default)))


def _zone_key(zone: ActiveAoEZone) -> tuple[int, int, int]:
    return (
        int(zone.caster_id),
        int(zone.skill_id),
        int(zone.cast_started_tick or 0),
    )


def _remove_provisional_zone(caster_id: int, skill_id: int, cast_started_tick: int, reason: str) -> None:
    removed = False
    for zone in list(_ACTIVE_ZONES):
        try:
            if not bool(zone.provisional):
                continue
            if int(zone.caster_id) != int(caster_id) or int(zone.skill_id) != int(skill_id):
                continue
            if int(cast_started_tick or 0) > 0 and int(zone.cast_started_tick or 0) not in (0, int(cast_started_tick)):
                continue
            _ACTIVE_ZONES.remove(zone)
            removed = True
        except Exception:
            continue
    if removed:
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_event(
                "AOE_PROVISIONAL_ZONE_REMOVED",
                caster_id=int(caster_id),
                skill_id=int(skill_id),
                reason=str(reason or "cast_stopped"),
            )
        except Exception:
            pass


def _add_active_zone(
    caster_id: int,
    skill_id: int,
    center: tuple[float, float],
    now_tick: int,
    confidence: str,
    *,
    cast_started_tick: int = 0,
    provisional: bool = False,
) -> None:
    spec = _AOE_SPEC_BY_SKILL_ID.get(int(skill_id))
    if spec is None or not center:
        return

    # Refresh the exact same cast even if the estimated target position moved
    # by more than 220 units between pre-arm and cast completion.  The previous
    # distance gate could create two zones for one cast and make the local
    # account alternate between two escape destinations.
    for zone in _ACTIVE_ZONES:
        if int(zone.skill_id) != int(skill_id) or int(zone.caster_id) != int(caster_id):
            continue
        existing_start = int(zone.cast_started_tick or 0)
        incoming_start = int(cast_started_tick or 0)
        same_native_cast = existing_start > 0 and incoming_start > 0 and existing_start == incoming_start
        compatible_legacy_cast = (
            (existing_start <= 0 or incoming_start <= 0)
            and _dist_sq(zone.center, center) <= 220.0 * 220.0
        )
        if not same_native_cast and not compatible_legacy_cast:
            continue

        was_provisional = bool(zone.provisional)
        zone.center = (float(center[0]), float(center[1]))
        zone.expires_tick = max(zone.expires_tick, int(now_tick) + int(spec.duration_ms))
        zone.cast_started_tick = int(incoming_start or existing_start or 0)
        if not bool(provisional):
            zone.provisional = False
        if _confidence_rank(confidence) > _confidence_rank(zone.confidence):
            zone.confidence = str(confidence)
        if was_provisional and not bool(zone.provisional):
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "AOE_ZONE_CONFIRMED",
                    caster_id=int(caster_id),
                    skill_id=int(skill_id),
                    cast_started_tick=int(cast_started_tick or 0),
                )
            except Exception:
                pass
        return

    _ACTIVE_ZONES.append(ActiveAoEZone(
        skill_id=int(skill_id),
        caster_id=int(caster_id),
        center=(float(center[0]), float(center[1])),
        radius=float(spec.radius),
        expires_tick=int(now_tick) + int(spec.duration_ms),
        critical=bool(spec.critical),
        confidence=str(confidence),
        cast_started_tick=int(cast_started_tick or 0),
        provisional=bool(provisional),
    ))
    try:
        from Py4GWCoreLib.Builds.Skills import Telemetry
        Telemetry.count("aoe.zone_armed")
        Telemetry.count(f"aoe.zone_{str(confidence).lower()}")
        Telemetry.event("aoe_zone", str(int(skill_id)))
    except Exception:
        pass
    try:
        from Py4GWCoreLib.Builds.Skills import CombatDebug
        CombatDebug.tick()
        CombatDebug.log_aoe_zone(
            int(skill_id),
            int(caster_id),
            center,
            float(spec.radius),
            str(confidence),
            bool(spec.critical),
            provisional=bool(provisional),
            cast_started_tick=int(cast_started_tick or 0),
        )
    except Exception:
        pass


def refresh_aoe_danger_zones(range_value: float = Range.Spellcast.value) -> None:
    global _LAST_SCAN_TICK

    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        if not SimplePowerSettings.is_feature_enabled("aoe_prediction", True):
            return
    except Exception:
        pass

    now = get_game_tick()
    if now <= 0:
        return

    # Always expire old zones/pending casts cheaply, even when throttled.
    _ACTIVE_ZONES[:] = [zone for zone in _ACTIVE_ZONES if int(zone.expires_tick) > now]
    for key, pending in list(_PENDING_CASTS.items()):
        if now - int(pending.last_seen_tick or pending.started_tick) > AOE_PENDING_TIMEOUT_MS:
            _PENDING_CASTS.pop(key, None)

    if _LAST_SCAN_TICK > 0 and now - _LAST_SCAN_TICK < AOE_SCAN_THROTTLE_MS:
        return
    _LAST_SCAN_TICK = now

    player_xy = _player_xy()
    if not player_xy:
        return

    try:
        enemies = AgentArray.GetEnemyArray()
        enemies = AgentArray.Filter.ByDistance(enemies, player_xy, float(range_value))
    except Exception:
        enemies = []

    seen_keys: set[tuple[int, int]] = set()
    for enemy_id in enemies or []:
        try:
            enemy_id = int(enemy_id or 0)
            if enemy_id <= 0 or not Agent.IsValid(enemy_id) or not Agent.IsAlive(enemy_id):
                continue
            if not Agent.IsCasting(enemy_id):
                continue
            skill_id = int(Agent.GetCastingSkillID(enemy_id) or 0)
            spec = _AOE_SPEC_BY_SKILL_ID.get(skill_id)
            if spec is None:
                continue
            center_info = _estimate_aoe_center(enemy_id, spec)
            if not center_info:
                continue
            center, confidence = center_info

            key = (enemy_id, skill_id)
            seen_keys.add(key)
            pending = _PENDING_CASTS.get(key)
            if pending is None:
                native_info = _native_cast_info(enemy_id, skill_id)
                native_start = int(native_info[0]) if native_info and int(native_info[0]) > 0 else int(now)
                # Guard against incompatible timestamp domains or stale queue data.
                if native_start > now or now - native_start > AOE_PENDING_TIMEOUT_MS:
                    native_start = int(now)
                pending = PendingAoECast(
                    caster_id=enemy_id,
                    skill_id=skill_id,
                    started_tick=native_start,
                    last_seen_tick=now,
                    center=center,
                    confidence=str(confidence),
                    committed=False,
                )
                _PENDING_CASTS[key] = pending
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    cast_ms_for_log = _cast_activation_ms(skill_id, spec, enemy_id)
                    prepare_lead_for_log = _prepare_lead_ms(skill_id, spec, cast_ms_for_log)
                    CombatDebug.log_aoe_pending(
                        int(skill_id),
                        int(enemy_id),
                        center,
                        str(confidence),
                        max(0, int(cast_ms_for_log) - int(prepare_lead_for_log)),
                    )
                except Exception:
                    pass
            else:
                pending.last_seen_tick = now
                pending.center = center
                if _confidence_rank(confidence) > _confidence_rank(pending.confidence):
                    pending.confidence = str(confidence)

            cast_ms = _cast_activation_ms(skill_id, spec, enemy_id)
            elapsed = max(0, now - int(pending.started_tick))
            remaining_ms = max(0, int(cast_ms) - int(elapsed))
            prepare_lead_ms = _prepare_lead_ms(skill_id, spec, cast_ms)
            final_move_lead_ms = _final_move_lead_ms(skill_id, spec, cast_ms)
            pending.disappeared_tick = 0

            live_interrupt_claim = _has_live_interrupt_claim(enemy_id, skill_id, now)
            if live_interrupt_claim:
                pending.last_interrupt_claim_tick = int(now)

            # Stage 1: prepare at roughly 90%, but do not create an active zone
            # and therefore do not move any account yet.
            if (
                not pending.prearmed
                and prepare_lead_ms > 0
                and remaining_ms <= prepare_lead_ms
                and _confidence_rank(pending.confidence) >= _confidence_rank("medium")
            ):
                pending.prearmed = True
                pending.commit_ready_tick = int(now)
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "AOE_ESCAPE_PREPARED",
                        caster_id=int(enemy_id),
                        skill_id=int(skill_id),
                        elapsed_ms=int(elapsed),
                        remaining_ms=int(remaining_ms),
                    )
                except Exception:
                    pass

            # Stage 2: movement is armed only in the final tiny window and only
            # when no coordinated interrupt is currently committed.  If a claim
            # exists, native interrupted/stopped/finished is authoritative.
            if (
                pending.prearmed
                and not pending.committed
                and final_move_lead_ms >= 0
                and remaining_ms <= final_move_lead_ms
                and _confidence_rank(pending.confidence) >= _confidence_rank("medium")
            ):
                if live_interrupt_claim:
                    if not pending.interrupt_deferred_logged:
                        pending.interrupt_deferred_logged = True
                        try:
                            from Py4GWCoreLib.Builds.Skills import CombatDebug
                            CombatDebug.log_event(
                                "AOE_ESCAPE_COMMIT_DEFERRED",
                                caster_id=int(enemy_id),
                                skill_id=int(skill_id),
                                remaining_ms=int(remaining_ms),
                                reason="live_interrupt_claim_waiting_for_native_outcome",
                            )
                        except Exception:
                            pass
                else:
                    # A claim that disappeared very recently may have just fired
                    # and be waiting for the outcome queue.  Give it a very small
                    # handoff window before issuing a speculative move.
                    grace_ms = int(AOE_FINAL_INTERRUPT_GRACE_MS)
                    try:
                        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
                        grace_ms = int(SimplePowerSettings.get_value(
                            "aoe_escape_final_interrupt_grace_ms", grace_ms
                        ))
                    except Exception:
                        pass
                    grace_ms = max(0, min(120, int(grace_ms)))
                    recent_claim = (
                        int(pending.last_interrupt_claim_tick or 0) > 0
                        and int(now) - int(pending.last_interrupt_claim_tick) <= int(grace_ms)
                    )
                    if not recent_claim:
                        if not _cast_is_still_live(enemy_id, skill_id):
                            try:
                                from Py4GWCoreLib.Builds.Skills import CombatDebug
                                CombatDebug.log_event(
                                    "AOE_ESCAPE_COMMIT_ABORTED",
                                    caster_id=int(enemy_id),
                                    skill_id=int(skill_id),
                                    remaining_ms=int(remaining_ms),
                                    reason="cast_no_longer_live",
                                )
                            except Exception:
                                pass
                            continue
                        pending.committed = True
                        _add_active_zone(
                            enemy_id,
                            skill_id,
                            center,
                            now,
                            pending.confidence,
                            cast_started_tick=int(pending.started_tick),
                            provisional=True,
                        )
                        try:
                            from Py4GWCoreLib.Builds.Skills import CombatDebug
                            CombatDebug.log_event(
                                "AOE_ESCAPE_COMMIT_FINAL",
                                caster_id=int(enemy_id),
                                skill_id=int(skill_id),
                                remaining_ms=int(remaining_ms),
                                move_lead_ms=int(final_move_lead_ms),
                                reason="no_interrupt_claim",
                            )
                        except Exception:
                            pass

            # Failsafe for rare timestamp/cast-duration mismatches: if the enemy
            # is still reported casting well past the expected finish and no live
            # claim remains, arm the zone.  This never fires during the normal
            # final-window path.
            overrun_ms = int(AOE_CAST_OVERRUN_FAILSAFE_MS_DEFAULT)
            try:
                from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
                overrun_ms = int(SimplePowerSettings.get_value(
                    "aoe_escape_cast_overrun_failsafe_ms", overrun_ms
                ))
            except Exception:
                pass
            overrun_ms = max(120, min(700, int(overrun_ms)))
            if (
                pending.prearmed
                and not pending.committed
                and elapsed >= int(cast_ms) + int(overrun_ms)
                and not live_interrupt_claim
                and _confidence_rank(pending.confidence) >= _confidence_rank("medium")
            ):
                pending.committed = True
                _add_active_zone(
                    enemy_id,
                    skill_id,
                    center,
                    now,
                    pending.confidence,
                    cast_started_tick=int(pending.started_tick),
                    provisional=True,
                )
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "AOE_ESCAPE_COMMIT_FAILSAFE",
                        caster_id=int(enemy_id),
                        skill_id=int(skill_id),
                        elapsed_ms=int(elapsed),
                        expected_cast_ms=int(cast_ms),
                    )
                except Exception:
                    pass
        except Exception:
            continue

    # Resolve casts that disappeared from live Agent state using the native
    # outcome queue.  A finished cast confirms the zone; interrupted/stopped
    # removes any provisional pre-arm.  With no native outcome, only a cast that
    # reached its expected end is conservatively treated as finished.
    for key, pending in list(_PENDING_CASTS.items()):
        if key in seen_keys:
            continue
        if int(pending.disappeared_tick or 0) <= 0:
            pending.disappeared_tick = int(now)
        native_outcome = None
        try:
            from Py4GWCoreLib.Builds.Skills.ReforgedSupport import get_cast_outcome
            native_outcome = get_cast_outcome(
                int(pending.caster_id), int(pending.skill_id), int(pending.started_tick)
            )
        except Exception:
            native_outcome = None

        outcome = _normalize_cast_outcome(native_outcome)
        spec = _AOE_SPEC_BY_SKILL_ID.get(int(pending.skill_id))
        cast_ms = _cast_activation_ms(int(pending.skill_id), spec, int(pending.caster_id)) if spec is not None else 1000
        elapsed_ms = max(0, int(now) - int(pending.started_tick))

        if outcome == "finished":
            _PENDING_CASTS.pop(key, None)
            _add_active_zone(
                int(pending.caster_id),
                int(pending.skill_id),
                pending.center,
                now,
                pending.confidence,
                cast_started_tick=int(pending.started_tick),
                provisional=False,
            )
            continue

        if outcome in ("interrupted", "stopped", "cancelled"):
            _PENDING_CASTS.pop(key, None)
            _remove_provisional_zone(
                int(pending.caster_id),
                int(pending.skill_id),
                int(pending.started_tick),
                outcome,
            )
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_aoe_cancelled(
                    int(pending.skill_id),
                    int(pending.caster_id),
                    int(elapsed_ms),
                    str(outcome),
                )
            except Exception:
                pass
            continue

        # Reforged can expose the Agent state transition one frame before the
        # native outcome queue.  Never infer a finished AoE immediately in that
        # gap, especially after an interrupt claim.
        grace_ms = _outcome_grace_ms(pending, now)
        disappeared_for_ms = max(0, int(now) - int(pending.disappeared_tick or now))
        if disappeared_for_ms < int(grace_ms):
            if not pending.outcome_grace_logged:
                pending.outcome_grace_logged = True
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "AOE_OUTCOME_GRACE",
                        caster_id=int(pending.caster_id),
                        skill_id=int(pending.skill_id),
                        grace_ms=int(grace_ms),
                        recent_interrupt_claim=bool(
                            int(pending.last_interrupt_claim_tick or 0) > 0
                            and int(now) - int(pending.last_interrupt_claim_tick) <= 900
                        ),
                    )
                except Exception:
                    pass
            continue

        _PENDING_CASTS.pop(key, None)

        # Polling fallback after the outcome grace.  Only assume completion near
        # the expected end; an earlier disappearance is treated as a stop.
        if spec is not None and elapsed_ms >= max(250, int(cast_ms) - 120):
            _add_active_zone(
                int(pending.caster_id),
                int(pending.skill_id),
                pending.center,
                now,
                pending.confidence,
                cast_started_tick=int(pending.started_tick),
                provisional=False,
            )
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.log_event(
                    "AOE_ZONE_CONFIRMED_BY_POLLING",
                    caster_id=int(pending.caster_id),
                    skill_id=int(pending.skill_id),
                    elapsed_ms=int(elapsed_ms),
                    expected_cast_ms=int(cast_ms),
                    outcome_grace_ms=int(grace_ms),
                )
            except Exception:
                pass
            continue

        _remove_provisional_zone(
            int(pending.caster_id),
            int(pending.skill_id),
            int(pending.started_tick),
            "unknown_early_stop",
        )
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_aoe_cancelled(
                int(pending.skill_id),
                int(pending.caster_id),
                int(elapsed_ms),
                str(native_outcome or "unknown_early_stop"),
            )
        except Exception:
            pass


def _active_zone_at_position(
    position: tuple[float, float] | None,
    *,
    padding: float = 55.0,
    critical_only: bool = False,
) -> ActiveAoEZone | None:
    if not position:
        return None
    refresh_aoe_danger_zones()
    now = get_game_tick()
    best: tuple[float, ActiveAoEZone] | None = None
    for zone in _ACTIVE_ZONES:
        try:
            if int(zone.expires_tick) <= now:
                continue
            if critical_only and not bool(zone.critical):
                continue
            radius = float(zone.radius) + float(padding)
            dist = _distance(position, zone.center)
            if dist <= radius:
                score = radius - dist
                if best is None or score > best[0]:
                    best = (score, zone)
        except Exception:
            continue
    return best[1] if best else None


def is_position_in_active_aoe(
    position: tuple[float, float] | None,
    *,
    padding: float = 55.0,
    critical_only: bool = False,
) -> bool:
    return _active_zone_at_position(position, padding=padding, critical_only=critical_only) is not None


def is_player_in_active_aoe(*, padding: float = 55.0, critical_only: bool = False) -> bool:
    return is_position_in_active_aoe(_player_xy(), padding=padding, critical_only=critical_only)




def _nearby_enemy_positions(
    player_xy: tuple[float, float],
    *,
    scan_range: float = AOE_SAFE_ESCAPE_SCAN_RANGE,
) -> list[tuple[int, tuple[float, float]]]:
    """Return nearby alive enemy positions used only for safe-escape scoring.

    This is intentionally lightweight and local to the escape decision. It does
    not try to identify aggro state because Py4GW does not expose a reliable
    "will aggro if moved there" signal.  Instead, candidates that move toward
    enemies or end near enemies are penalized or rejected.
    """
    try:
        enemies = AgentArray.GetEnemyArray()
        enemies = AgentArray.Filter.ByDistance(enemies, player_xy, float(scan_range))
    except Exception:
        enemies = []

    result: list[tuple[int, tuple[float, float]]] = []
    for enemy_id in enemies or []:
        try:
            enemy_id = int(enemy_id or 0)
            if enemy_id <= 0 or not Agent.IsValid(enemy_id) or not Agent.IsAlive(enemy_id):
                continue
            xy = _safe_xy_for_agent(enemy_id)
            if not xy:
                continue
            result.append((enemy_id, xy))
        except Exception:
            continue
    return result


def _position_hits_any_active_zone(
    position: tuple[float, float],
    *,
    padding: float = AOE_SAFE_ESCAPE_AOE_PADDING,
) -> bool:
    now = get_game_tick()
    for zone in list(_ACTIVE_ZONES):
        try:
            if int(zone.expires_tick) <= now:
                continue
            if _distance(position, zone.center) <= float(zone.radius) + float(padding):
                return True
        except Exception:
            continue
    return False


def _rotate_unit(ux: float, uy: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(float(degrees))
    c = math.cos(radians)
    s = math.sin(radians)
    return (ux * c - uy * s, ux * s + uy * c)


def _account_escape_angle_bias() -> float:
    """Small stable per-account bias to avoid identical multibox escape rays."""
    try:
        email = str(Player.GetAccountEmail() or "").strip().lower()
        seed = sum((index + 1) * ord(char) for index, char in enumerate(email))
        return (-35.0, -17.5, 0.0, 17.5, 35.0)[seed % 5]
    except Exception:
        return 0.0


def _cast_is_still_live(caster_id: int, skill_id: int) -> bool:
    """Final cheap validation immediately before arming movement."""
    try:
        if not Agent.IsValid(int(caster_id)) or Agent.IsDead(int(caster_id)):
            return False
        if not Agent.IsCasting(int(caster_id)):
            return False
        return int(Agent.GetCastingSkillID(int(caster_id)) or 0) == int(skill_id)
    except Exception:
        return False


def _escape_candidate_score(
    *,
    candidate: tuple[float, float],
    player_xy: tuple[float, float],
    ideal_destination: tuple[float, float],
    zone: ActiveAoEZone,
    enemy_positions: list[tuple[int, tuple[float, float]]],
    move_distance: float,
    angle_penalty: float,
) -> float:
    """Higher score is safer.

    Hard priorities:
    - do not end inside another active predicted AoE
    - do not end very near enemies if avoidable
    Soft priorities:
    - move away from enemies, not toward them
    - do not move farther than needed
    - stay close to the ideal outward vector when safety is equal
    """
    if _position_hits_any_active_zone(candidate):
        return -1_000_000.0

    # Must actually improve distance from the current AoE zone.
    current_zone_dist = _distance(player_xy, zone.center)
    candidate_zone_dist = _distance(candidate, zone.center)
    if candidate_zone_dist <= current_zone_dist + 60.0:
        return -900_000.0

    score = 0.0
    score += (candidate_zone_dist - current_zone_dist) * 1.4

    nearest_enemy = 999999.0
    hard_enemy_count = 0
    soft_enemy_count = 0
    moving_closer_count = 0
    very_close_penalty = 0.0

    for _, enemy_xy in enemy_positions:
        try:
            cur_dist = _distance(player_xy, enemy_xy)
            cand_dist = _distance(candidate, enemy_xy)
            nearest_enemy = min(nearest_enemy, cand_dist)
            if cand_dist <= AOE_SAFE_ESCAPE_ENEMY_HARD_RADIUS:
                hard_enemy_count += 1
                very_close_penalty += (AOE_SAFE_ESCAPE_ENEMY_HARD_RADIUS - cand_dist)
            if cand_dist <= AOE_SAFE_ESCAPE_ENEMY_SOFT_RADIUS:
                soft_enemy_count += 1
            if cand_dist + 55.0 < cur_dist and cand_dist <= AOE_SAFE_ESCAPE_ENEMY_SOFT_RADIUS:
                moving_closer_count += 1
        except Exception:
            continue

    # Prefer a candidate that does not pull/move into extra enemies.
    score -= hard_enemy_count * 900.0
    score -= soft_enemy_count * 75.0
    score -= moving_closer_count * 180.0
    score -= very_close_penalty * 1.5
    score += min(nearest_enemy, 1400.0) * 0.15

    # Prefer smaller movement when safety is close; this preserves formation.
    score -= float(move_distance) * 0.18
    score -= abs(float(angle_penalty)) * 2.0

    # Prefer candidates close to the default radial escape destination.
    score -= _distance(candidate, ideal_destination) * 0.08
    return score

def _escape_destination(zone: ActiveAoEZone, player_xy: tuple[float, float]) -> tuple[float, float]:
    px, py = player_xy
    cx, cy = zone.center
    dx = float(px) - float(cx)
    dy = float(py) - float(cy)
    length = math.sqrt(dx * dx + dy * dy)

    if length < 1.0:
        caster_xy = _safe_xy_for_agent(zone.caster_id)
        if caster_xy:
            # If the AoE center is estimated on the player, move away from the
            # caster instead of choosing a random direction.
            dx = float(px) - float(caster_xy[0])
            dy = float(py) - float(caster_xy[1])
            length = math.sqrt(dx * dx + dy * dy)

    if length < 1.0:
        # Deterministic fallback: move east.  This avoids random jitter.
        dx, dy, length = 1.0, 0.0, 1.0

    ux = dx / length
    uy = dy / length
    needed = (float(zone.radius) + 160.0) - length
    base_move_distance = max(
        AOE_MIN_MOVE_DISTANCE,
        min(AOE_MAX_MOVE_DISTANCE, needed + AOE_DEFAULT_MOVE_DISTANCE * 0.25),
    )
    ideal_destination = (float(px) + ux * base_move_distance, float(py) + uy * base_move_distance)

    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        if not SimplePowerSettings.is_feature_enabled("aoe_safe_escape_pathing", True):
            return ideal_destination
    except Exception:
        pass

    enemy_positions = _nearby_enemy_positions(player_xy)
    if not enemy_positions and not _ACTIVE_ZONES:
        return ideal_destination

    # Try a small fan of candidates around the ideal outward vector.  This keeps
    # the command cheap but avoids three common failures: moving toward enemies,
    # stepping into a second predicted AoE, or running deeper into another pack.
    preferred_angle = _account_escape_angle_bias()
    angle_options = (0.0, -22.5, 22.5, -45.0, 45.0, -70.0, 70.0, -100.0, 100.0, -135.0, 135.0)
    distance_options = (
        base_move_distance,
        min(AOE_MAX_MOVE_DISTANCE, base_move_distance + 140.0),
        max(AOE_MIN_MOVE_DISTANCE, base_move_distance - 120.0),
    )

    scored_candidates: list[tuple[float, tuple[float, float]]] = []
    for move_distance in distance_options:
        for angle in angle_options:
            try:
                rux, ruy = _rotate_unit(ux, uy, angle)
                candidate = (float(px) + rux * float(move_distance), float(py) + ruy * float(move_distance))
                score = _escape_candidate_score(
                    candidate=candidate,
                    player_xy=player_xy,
                    ideal_destination=ideal_destination,
                    zone=zone,
                    enemy_positions=enemy_positions,
                    move_distance=float(move_distance),
                    angle_penalty=float(angle) - float(preferred_angle),
                )
                scored_candidates.append((score, candidate))
            except Exception:
                continue

    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    if not scored_candidates:
        return ideal_destination

    # Reforged-only refinement: validate only the best few geometric candidates
    # with the native immediate path planner. This is called only while actually
    # escaping an AoE, so it adds no normal combat-frame cost.
    try:
        from Py4GWCoreLib.Builds.Skills.ReforgedSupport import path_quality
        best_reachable: tuple[float, tuple[float, float]] | None = None
        for geometric_score, candidate in scored_candidates[:5]:
            reachable, path_length = path_quality(player_xy, candidate)
            if not reachable:
                continue
            combined = float(geometric_score) - min(float(path_length), 3000.0) * 0.06
            if best_reachable is None or combined > best_reachable[0]:
                best_reachable = (combined, candidate)
        if best_reachable is not None:
            return best_reachable[1]
    except Exception:
        pass

    # If Reforged pathing is unavailable or every path check fails, retain the
    # proven geometric SafeAoEEscape fallback.
    return scored_candidates[0][1]


def _current_follow_anchor() -> tuple[float, float] | None:
    """Read the current HeroAI follow/flag destination without owning follow logic.

    This intentionally mirrors the public follower runtime rules.  If the
    destination cannot be read, the caller falls back to the pre-escape origin
    and ultimately leaves recovery to the normal Follow module.
    """
    try:
        from Py4GWCoreLib import GLOBAL_CACHE

        email = str(Player.GetAccountEmail() or "").strip()
        if not email:
            return None
        options = GLOBAL_CACHE.ShMem.GetHeroAIOptionsFromEmail(email)
        if not options or not bool(getattr(options, "Following", False)):
            return None

        follow = (float(options.FollowPos.x), float(options.FollowPos.y))
        if abs(follow[0]) > 0.001 or abs(follow[1]) > 0.001:
            return follow

        if bool(getattr(options, "IsFlagged", False)):
            flag = (float(options.FlagPos.x), float(options.FlagPos.y))
            if abs(flag[0]) > 0.001 or abs(flag[1]) > 0.001:
                return flag
    except Exception:
        pass
    return None


def _nearest_enemy_distance(position: tuple[float, float], enemy_positions: list[tuple[int, tuple[float, float]]]) -> float:
    nearest = 999999.0
    for _, enemy_xy in enemy_positions:
        try:
            nearest = min(nearest, _distance(position, enemy_xy))
        except Exception:
            continue
    return nearest



def _segment_hits_any_active_zone(
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    padding: float = AOE_ESCAPE_PATH_PADDING,
) -> bool:
    """Return True when the straight return path crosses an active danger zone."""
    refresh_aoe_danger_zones()
    now = get_game_tick()
    sx, sy = float(start[0]), float(start[1])
    ex, ey = float(end[0]), float(end[1])
    vx, vy = ex - sx, ey - sy
    length_sq = vx * vx + vy * vy
    for zone in _ACTIVE_ZONES:
        try:
            if int(zone.expires_tick) <= int(now):
                continue
            cx, cy = float(zone.center[0]), float(zone.center[1])
            if length_sq <= 1.0:
                nearest_x, nearest_y = sx, sy
            else:
                t = ((cx - sx) * vx + (cy - sy) * vy) / length_sq
                t = max(0.0, min(1.0, t))
                nearest_x = sx + t * vx
                nearest_y = sy + t * vy
            radius = float(zone.radius) + float(padding)
            if (nearest_x - cx) ** 2 + (nearest_y - cy) ** 2 <= radius * radius:
                return True
        except Exception:
            continue
    return False


def _remember_escape_origin(
    player_xy: tuple[float, float],
    now: int,
    role: str,
    destination: tuple[float, float],
    zone: ActiveAoEZone,
    *,
    retarget: bool = False,
) -> bool:
    """Store one stable escape episode.

    A new overlapping zone no longer starts a new episode by itself.  The
    destination changes only when it has become unsafe and the retarget
    cooldown has elapsed.
    """
    is_new = not _RETURN_STATE.active
    if is_new:
        _RETURN_STATE.origin = (float(player_xy[0]), float(player_xy[1]))
        _RETURN_STATE.follow_anchor = _current_follow_anchor()
        _RETURN_STATE.escaped_tick = int(now)
        _RETURN_STATE.last_escape_command_tick = 0
        _RETURN_STATE.last_retarget_tick = int(now)
        _RETURN_STATE.role = str(role or "generic")
    _RETURN_STATE.active = True
    if is_new or retarget or _RETURN_STATE.escape_destination is None:
        _RETURN_STATE.escape_destination = (float(destination[0]), float(destination[1]))
        _RETURN_STATE.zone_key = _zone_key(zone)
        _RETURN_STATE.last_retarget_tick = int(now)
        _RETURN_STATE.best_escape_distance = float(_distance(player_xy, destination))
        _RETURN_STATE.last_progress_tick = int(now)
    return bool(is_new or retarget)


def _clear_return_state(*, completed: bool = False) -> None:
    if completed:
        try:
            from Py4GWCoreLib.Builds.Skills import Telemetry
            Telemetry.count("aoe.return_completed")
        except Exception:
            pass
    _RETURN_STATE.active = False
    _RETURN_STATE.origin = None
    _RETURN_STATE.follow_anchor = None
    _RETURN_STATE.escape_destination = None
    _RETURN_STATE.zone_key = None
    _RETURN_STATE.escaped_tick = 0
    _RETURN_STATE.last_escape_command_tick = 0
    _RETURN_STATE.last_retarget_tick = 0
    _RETURN_STATE.role = "generic"
    _RETURN_STATE.safe_hold_actions_logged = False
    _RETURN_STATE.best_escape_distance = 0.0
    _RETURN_STATE.last_progress_tick = 0


def _should_refresh_escape_move(
    player_xy: tuple[float, float],
    destination: tuple[float, float],
    now: int,
    cooldown_ms: int,
) -> bool:
    """Issue a new escape move only when the character stopped making progress.

    Re-sending Player.Move on a fixed timer can compete with keyboard/mouse input
    and makes steering feel sticky.  A healthy move is now left alone; the escape
    command is refreshed only after the distance has not improved for a while.
    """
    distance = float(_distance(player_xy, destination))
    if distance <= float(AOE_ESCAPE_ARRIVAL_DISTANCE):
        _RETURN_STATE.best_escape_distance = min(
            float(_RETURN_STATE.best_escape_distance or distance), distance
        )
        _RETURN_STATE.last_progress_tick = int(now)
        return False

    if int(_RETURN_STATE.last_escape_command_tick or 0) <= 0:
        _RETURN_STATE.best_escape_distance = distance
        _RETURN_STATE.last_progress_tick = int(now)
        return True

    best = float(_RETURN_STATE.best_escape_distance or distance)
    if distance + float(AOE_ESCAPE_PROGRESS_EPSILON) < best:
        _RETURN_STATE.best_escape_distance = distance
        _RETURN_STATE.last_progress_tick = int(now)
        return False

    if int(now) - int(_RETURN_STATE.last_progress_tick or now) < int(AOE_ESCAPE_STALL_REISSUE_MS):
        return False
    if int(now) - int(_RETURN_STATE.last_escape_command_tick or 0) < int(cooldown_ms):
        return False

    _RETURN_STATE.best_escape_distance = distance
    _RETURN_STATE.last_progress_tick = int(now)
    return True


def _maybe_return_after_aoe(player_xy: tuple[float, float], now: int) -> bool:
    """Release movement back to normal Follow without issuing competing moves.

    V5 sent its own AOE_RETURN command every 500 ms while normal Follow also
    updated its destination.  It also cleared the escape state after 4.5 s,
    shorter than Fire Storm and Meteor Shower.  That combination caused the
    team to run back into a live field and escape again.

    V6 holds the safe point while the formation anchor or the straight return
    path is still dangerous.  As soon as the route is safe, this state is
    cleared and the normal Follow module resumes as the single movement owner.
    """
    if not _RETURN_STATE.active:
        return False

    # If a new/overlapping field has reached the player, the normal escape path
    # handles it on the next call.
    if _active_zone_at_position(
        player_xy,
        padding=AOE_ESCAPE_RELEASE_PADDING,
        critical_only=False,
    ) is not None:
        return True

    anchor = _current_follow_anchor() or _RETURN_STATE.follow_anchor or _RETURN_STATE.origin
    if not anchor:
        _clear_return_state()
        return False
    anchor = (float(anchor[0]), float(anchor[1]))

    anchor_unsafe = _position_hits_any_active_zone(
        anchor,
        padding=AOE_ESCAPE_RELEASE_PADDING,
    )
    path_unsafe = _segment_hits_any_active_zone(
        player_xy,
        anchor,
        padding=AOE_ESCAPE_PATH_PADDING,
    )
    if anchor_unsafe or path_unsafe:
        # Hold the already selected safe destination.  Refresh only when still
        # materially away from it; never generate a second return destination.
        destination = _RETURN_STATE.escape_destination
        if destination:
            try:
                distance_to_destination = _distance(player_xy, destination)
                hold_distance = float(AOE_SAFE_HOLD_ACTION_DISTANCE)
                try:
                    from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
                    hold_distance = float(SimplePowerSettings.get_value(
                        "aoe_safe_hold_action_distance", hold_distance
                    ))
                except Exception:
                    pass
                if (
                    distance_to_destination > max(AOE_ESCAPE_ARRIVAL_DISTANCE, hold_distance)
                    and _should_refresh_escape_move(
                        player_xy, destination, now, AOE_AVOID_COOLDOWN_MS
                    )
                ):
                    Player.Move(float(destination[0]), float(destination[1]))
                    _RETURN_STATE.last_escape_command_tick = int(now)
            except Exception:
                pass
        return True

    # The normal follower now owns the return.  Do not issue an AOE_RETURN move.
    _clear_return_state(completed=True)
    return False



def avoid_active_aoe_if_needed(
    *,
    role: str = "generic",
    allow_noncritical: bool = False,
    padding: float = 60.0,
    allow_actions_at_safe_hold: bool = False,
) -> bool:
    """Move the local account out of a predicted active AoE zone.

    Returns True while this account's movement is owned by the escape/return
    override.  Callers must then skip normal follow/cast movement for this tick.
    Non-critical zones are ignored unless allow_noncritical=True.

    With ``allow_actions_at_safe_hold=True`` the build rotation resumes once
    the account is safely outside the field and close to its stable escape
    point.  The follower calls this helper without that flag, so normal follow
    remains blocked and cannot drag the account back through the active AoE.
    """
    global _LAST_AVOID_TICK

    # HR KeySoJway safety policy: only the Soul Twisting Ritualist is allowed
    # to move because of predicted AoE. Other accounts may still observe combat
    # events for interrupt logic, but AoE prediction must never own their
    # movement or spread the team.
    role_key_hard = str(role or "generic").strip().lower()
    if role_key_hard not in ("st", "soul_twisting", "ritualist"):
        return False

    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        if not SimplePowerSettings.is_feature_enabled("aoe_avoidance", True):
            return False
        role_key_for_settings = str(role or "generic").strip().lower()
        if role_key_for_settings in ("st", "soul_twisting", "ritualist"):
            if not SimplePowerSettings.is_feature_enabled("aoe_avoidance_st", True):
                return False
        else:
            if not SimplePowerSettings.is_feature_enabled("aoe_avoidance_non_st", True):
                return False
    except Exception:
        pass

    now = get_game_tick()
    if now <= 0:
        return False
    avoid_cooldown_ms = int(AOE_AVOID_COOLDOWN_MS)
    try:
        from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
        avoid_cooldown_ms = int(SimplePowerSettings.get_value("aoe_avoid_cooldown_ms", avoid_cooldown_ms))
    except Exception:
        pass
    player_xy = _player_xy()
    if not player_xy:
        return False

    # Only true damaging danger fields trigger movement by default.  The old
    # ST exception also moved from harmless wards and recreated spread-like
    # behavior, so non-critical zones now require an explicit opt-in.
    role_key = str(role or "generic").strip().lower()
    critical_only = not bool(allow_noncritical)
    zone = _active_zone_at_position(player_xy, padding=padding, critical_only=critical_only)
    if zone is None:
        movement_owned = _maybe_return_after_aoe(player_xy, now)
        safe_hold_actions_enabled = bool(allow_actions_at_safe_hold)
        try:
            from Py4GWCoreLib.Builds.Skills import SimplePowerSettings
            safe_hold_actions_enabled = safe_hold_actions_enabled and SimplePowerSettings.is_feature_enabled(
                "aoe_safe_hold_combat_actions", True
            )
        except Exception:
            pass
        if (
            movement_owned
            and safe_hold_actions_enabled
            and is_aoe_escape_safe_hold_active(role=role_key)
        ):
            if not _RETURN_STATE.safe_hold_actions_logged:
                _RETURN_STATE.safe_hold_actions_logged = True
                try:
                    from Py4GWCoreLib.Builds.Skills import CombatDebug
                    CombatDebug.log_event(
                        "AOE_SAFE_HOLD_COMBAT_ENABLED",
                        account=str(Player.GetAccountEmail() or ""),
                        role=role_key,
                        destination=(
                            f"{float(_RETURN_STATE.escape_destination[0]):.1f},"
                            f"{float(_RETURN_STATE.escape_destination[1]):.1f}"
                            if _RETURN_STATE.escape_destination else ""
                        ),
                    )
                except Exception:
                    pass
            return False
        return movement_owned
    if not _confidence_allowed_for_role(zone.confidence, role_key, critical=bool(zone.critical)):
        try:
            from Py4GWCoreLib.Builds.Skills import Telemetry
            Telemetry.count(f"aoe.ignored_{str(zone.confidence).lower()}")
        except Exception:
            pass
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_aoe_escape_skipped(
                int(zone.skill_id), role_key, str(zone.confidence), "confidence_policy"
            )
        except Exception:
            pass
        return False

    try:
        destination = _RETURN_STATE.escape_destination
        is_new_episode = not _RETURN_STATE.active or destination is None
        destination_unsafe = bool(
            destination
            and _position_hits_any_active_zone(
                destination,
                padding=AOE_ESCAPE_RELEASE_PADDING,
            )
        )
        may_retarget = (
            destination_unsafe
            and now - int(_RETURN_STATE.last_retarget_tick or 0) >= AOE_ESCAPE_RETARGET_COOLDOWN_MS
        )

        if is_new_episode or may_retarget:
            destination = _escape_destination(zone, player_xy)

        changed_escape = _remember_escape_origin(
            player_xy,
            now,
            role_key,
            destination,
            zone,
            retarget=bool(may_retarget and not is_new_episode),
        )

        distance_to_destination = _distance(player_xy, destination)
        should_issue_move = (
            distance_to_destination > AOE_ESCAPE_ARRIVAL_DISTANCE
            and _should_refresh_escape_move(
                player_xy, destination, now, int(avoid_cooldown_ms)
            )
        )
        if should_issue_move:
            Player.Move(float(destination[0]), float(destination[1]))
            _RETURN_STATE.last_escape_command_tick = int(now)
            _LAST_AVOID_TICK = int(now)
            try:
                from Py4GWCoreLib.Builds.Skills import Telemetry
                Telemetry.count("aoe.avoid_move")
                Telemetry.event("aoe_avoid", str(role))
            except Exception:
                pass

        if changed_escape:
            try:
                from Py4GWCoreLib.Builds.Skills import CombatDebug
                CombatDebug.tick()
                CombatDebug.mark_aoe_escape(int(zone.skill_id), destination, role_key, str(zone.confidence))
                if not is_new_episode:
                    CombatDebug.log_event(
                        "AOE_ESCAPE_RETARGET",
                        account=str(Player.GetAccountEmail() or ""),
                        skill_id=int(zone.skill_id),
                        destination=f"{float(destination[0]):.1f},{float(destination[1]):.1f}",
                        reason="previous_destination_became_unsafe",
                    )
            except Exception:
                pass

        # Return True for the entire time the account is inside the field, not
        # only on frames that issue Player.Move.  This prevents normal follow or
        # cast logic from immediately overwriting the escape destination.
        return True
    except Exception as exc:
        try:
            from Py4GWCoreLib.Builds.Skills import CombatDebug
            CombatDebug.log_aoe_escape_failed(
                int(zone.skill_id), role_key, str(zone.confidence), repr(exc)
            )
        except Exception:
            pass
        return False
