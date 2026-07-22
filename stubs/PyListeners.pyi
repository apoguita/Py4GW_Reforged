# PyListeners stub - Reforged Native surface.
# Exact counterpart of src/listeners/listeners_bindings.cpp.
#
# Runtime toggles for the native game-event listeners. A listener is a named unit
# over a set of native callbacks (StoC packets, a UI hook, or a poll tick) whose
# only job is to be switched on or off: enable installs the callbacks, disable
# removes them (both idempotent), so a disabled listener has zero overhead.
#
# Registered names (see include/listeners/listeners.h):
#   "merchant"                   - quoted price / transaction / window item capture (on by default)
#   "agent_events"               - per-agent event ring buffer (on by default)
#   "skill_list_filter"          - hide known / non-elite skills in skill windows (opt-in)
#   "signet_of_capture_limit"    - clamp Signet of Capture count to 10 (opt-in)
#   "faction_warning"            - warn when earned faction reaches a % of the cap (opt-in)
#   "cinematic_skip"             - auto-skip in-game cinematics (opt-in)
#   "auto_return_on_defeat"      - leader returns party to outpost on wipe (opt-in)
#   "disable_gold_confirmation"  - remove gold/green item sell confirmation (opt-in)
#   "remove_cast_bar_minimum"    - show cast bar for very short casts (opt-in)
#   "auto_cancel_ua"             - drop Unyielding Aura before recasting it (opt-in)
#   "auto_open_locked_chest"     - auto-send use-key / use-lockpick at a locked chest (opt-in)
#   "faction_donate_skip_name"   - prefill character name when donating faction (opt-in)
#   "keep_current_quest"         - keep manually-chosen quest when a new one is added (opt-in)
#
# Every toggle is addressed by name and returns False when the name is unknown.
# The set_*/get_* config functions below target a specific listener directly; a
# listener must still be enabled by name for its config to take effect.

from typing import List

def list() -> List[str]:
    """List the names of all toggleable listeners."""
    ...

def enable(name: str) -> bool:
    """Enable a listener by name. False if the name is unknown."""
    ...

def disable(name: str) -> bool:
    """Disable a listener by name. False if the name is unknown."""
    ...

def toggle(name: str) -> bool:
    """Toggle a listener by name. False if the name is unknown."""
    ...

def set_enabled(name: str, enabled: bool) -> bool:
    """Set a listener's enabled state. False if the name is unknown."""
    ...

def is_enabled(name: str) -> bool:
    """Check whether a listener is enabled. False if the name is unknown."""
    ...

# --- skill_list_filter config ---
# Tune which skills the "skill_list_filter" listener hides once it is enabled.

def set_hide_known_skills(value: bool) -> None:
    """Hide skills the character already owns from tome / trainer / capture windows."""
    ...

def get_hide_known_skills() -> bool:
    """Whether known skills are hidden from the skill-selection windows."""
    ...

def set_hide_nonelites_on_capture(value: bool) -> None:
    """In the skill-capture window, hide all non-elite skills."""
    ...

def get_hide_nonelites_on_capture() -> bool:
    """Whether non-elite skills are hidden in the skill-capture window."""
    ...

# --- faction_warning config ---
# Set the threshold for the "faction_warning" listener once it is enabled.

def set_faction_warn_percent(percent: int) -> None:
    """Percentage (0-100) of the faction cap at which to warn."""
    ...

def get_faction_warn_percent() -> int:
    """The configured faction-warning percentage."""
    ...

# --- auto_open_locked_chest config ---
# Pick which auto-open response the "auto_open_locked_chest" listener sends.

def set_auto_open_use_key(value: bool) -> None:
    """Auto-send the 'use key' response at a locked chest."""
    ...

def get_auto_open_use_key() -> bool:
    """Whether the 'use key' response is auto-sent."""
    ...

def set_auto_open_use_lockpick(value: bool) -> None:
    """Auto-send the 'use lockpick' response at a locked chest."""
    ...

def get_auto_open_use_lockpick() -> bool:
    """Whether the 'use lockpick' response is auto-sent."""
    ...
