"""Runtime feature switches and tunable values for the Simple-Power HeroAI package.

Defaults keep the tested behavior enabled.  The optional control panel can
change these values at runtime for testing.  If the panel is not loaded, normal
behavior is unchanged.
"""
from __future__ import annotations

_DEFAULT_FEATURES: dict[str, bool] = {
    "global_danger_interrupt_claim": True,
    "execution_focus": True,
    "combat_sense_cache": True,
    "threat_aware_cluster_targeting": True,
    "aoe_prediction": True,
    "aoe_avoidance": True,
    "aoe_avoidance_st": True,
    "aoe_avoidance_non_st": True,
    "aoe_safe_escape_pathing": True,
    "st_aoe_safe_hold_spirit_setup": True,
    "aoe_safe_hold_combat_actions": True,
    "st_aoe_preescape_knockdown_immunity": True,
    "lethal_aoe_interrupt_approach": True,
    "telemetry": False,
    "adaptive_threat_memory": True,
    "combat_debug_file_log": True,
    "combat_debug_colors": False,
}
_FEATURES: dict[str, bool] = dict(_DEFAULT_FEATURES)
_FEATURE_LABELS: dict[str, str] = {
    "global_danger_interrupt_claim": "Global dangerous-cast interrupt claim",
    "execution_focus": "Low-HP execution focus",
    "combat_sense_cache": "Central combat-sense cache",
    "threat_aware_cluster_targeting": "Threat-aware cluster targeting",
    "aoe_prediction": "AoE danger prediction",
    "aoe_avoidance": "AoE movement avoidance master switch",
    "aoe_avoidance_st": "AoE avoidance for ST Ritualist",
    "aoe_avoidance_non_st": "AoE avoidance for other roles",
    "aoe_safe_escape_pathing": "Safer AoE escape pathing",
    "st_aoe_safe_hold_spirit_setup": "ST rebuilds spirits at AoE safe hold",
    "aoe_safe_hold_combat_actions": "All builds keep casting from a safe AoE hold point",
    "st_aoe_preescape_knockdown_immunity": "ST uses knockdown immunity before AoE escape",
    "lethal_aoe_interrupt_approach": "Mesmer may make a short approach to interrupt lethal AoE",
    "telemetry": "Telemetry / debug counters",
    "adaptive_threat_memory": "Adaptive enemy threat memory",
    "combat_debug_file_log": "Combat debug file logging",
    "combat_debug_colors": "Native combat debug name-tag colors",
}

_DEFAULT_VALUES: dict[str, object] = {
    # Global execution override: any reachable enemy below 15% HP is
    # finished before the team returns to the densest cluster.
    "execution_hp_threshold": 0.15,
    # Event-aware interrupt build: 55ms keeps the shared cache responsive
    # without making every build perform its own enemy scan.
    "combat_sense_throttle_ms": 100,
    # Native cast events are available; poll the ranked candidate view at 35ms.
    "danger_interrupt_scan_throttle_ms": 75,
    # Minimum contextual danger score for a dedicated claimed interrupt.
    "danger_interrupt_min_score": 80,
    # Stable destination refresh; avoids movement spam while preserving fast escape.
    "aoe_avoid_cooldown_ms": 700,
    # V9 two-stage AoE escape: prepare at 90%, move only in the final frame.
    # The legacy key remains as a compatibility alias for older control panels.
    "aoe_escape_prepare_fraction": 0.90,
    "aoe_escape_commit_fraction": 0.90,
    # Unclaimed casts may arm movement only this shortly before completion.
    "aoe_escape_final_move_lead_ms": 70,
    "aoe_escape_meteor_move_lead_ms": 120,
    "aoe_escape_short_cast_move_lead_ms": 55,
    # Tiny claim handoff plus native-event grace prevents movement when an
    # interrupt was fired but its interrupted/stopped outcome arrives a frame later.
    "aoe_escape_final_interrupt_grace_ms": 45,
    "aoe_escape_interrupt_outcome_grace_ms": 340,
    "aoe_escape_general_outcome_grace_ms": 125,
    "aoe_safe_hold_action_distance": 180.0,
    "aoe_escape_cast_overrun_failsafe_ms": 260,
    # Bounded Mesmer approach: enough to enter casting range, never a long chase.
    "interrupt_approach_max_extra_distance": 420.0,
    "interrupt_approach_leader_tether": 1200.0,
    "interrupt_approach_move_cooldown_ms": 140,
    # normal = corpse-boosted Sorrow first, Corruption opening if no corpse.
    # aggressive = use Sorrow earlier as general damage filler before Corruption.
    "keystone_sorrow_priority": "normal",
    # Per-account combat logs rotate at this size.
    "combat_debug_log_max_bytes": 5 * 1024 * 1024,
}
_VALUES: dict[str, object] = dict(_DEFAULT_VALUES)

def is_feature_enabled(name: str, default: bool = True) -> bool:
    try:
        return bool(_FEATURES.get(str(name), bool(default)))
    except Exception:
        return bool(default)

def set_feature_enabled(name: str, enabled: bool) -> bool:
    key = str(name)
    if key not in _DEFAULT_FEATURES:
        _DEFAULT_FEATURES[key] = bool(enabled)
    _FEATURES[key] = bool(enabled)
    return bool(_FEATURES[key])

def toggle_feature(name: str) -> bool:
    key = str(name)
    return set_feature_enabled(key, not is_feature_enabled(key, True))

def reset_defaults() -> None:
    _FEATURES.clear()
    _FEATURES.update(_DEFAULT_FEATURES)
    _VALUES.clear()
    _VALUES.update(_DEFAULT_VALUES)

def get_feature_map() -> dict[str, bool]:
    return dict(_FEATURES)

def get_feature_labels() -> dict[str, str]:
    return dict(_FEATURE_LABELS)

def get_value(name: str, default=None):
    try:
        return _VALUES.get(str(name), default)
    except Exception:
        return default

def set_value(name: str, value) -> object:
    key = str(name)
    if key not in _DEFAULT_VALUES:
        _DEFAULT_VALUES[key] = value
    _VALUES[key] = value
    return _VALUES[key]

def get_values() -> dict[str, object]:
    return dict(_VALUES)

def set_execution_threshold(value: float) -> float:
    value = max(0.05, min(0.50, float(value)))
    set_value("execution_hp_threshold", value)
    return value

def get_execution_threshold(default: float = 0.15) -> float:
    try:
        return float(get_value("execution_hp_threshold", default))
    except Exception:
        return float(default)

def set_combat_sense_mode(mode: str) -> int:
    mode = str(mode or "balanced").lower()
    if mode == "fast":
        throttle = 60
    elif mode == "safe":
        throttle = 140
    else:
        throttle = 90
    set_value("combat_sense_throttle_ms", int(throttle))
    return int(throttle)

def get_combat_sense_throttle(default: int = 90) -> int:
    try:
        return int(get_value("combat_sense_throttle_ms", default))
    except Exception:
        return int(default)

def set_aoe_movement_mode(mode: str) -> str:
    mode = str(mode or "all").lower()
    if mode == "off":
        set_feature_enabled("aoe_avoidance", False)
        set_feature_enabled("aoe_avoidance_st", False)
        set_feature_enabled("aoe_avoidance_non_st", False)
        return "off"
    set_feature_enabled("aoe_avoidance", True)
    if mode == "st_only":
        set_feature_enabled("aoe_avoidance_st", True)
        set_feature_enabled("aoe_avoidance_non_st", False)
        return "st_only"
    set_feature_enabled("aoe_avoidance_st", True)
    set_feature_enabled("aoe_avoidance_non_st", True)
    return "all"

def get_aoe_movement_mode() -> str:
    if not is_feature_enabled("aoe_avoidance", True):
        return "off"
    st = is_feature_enabled("aoe_avoidance_st", True)
    non_st = is_feature_enabled("aoe_avoidance_non_st", True)
    if st and not non_st:
        return "st_only"
    if st and non_st:
        return "all"
    return "off"
