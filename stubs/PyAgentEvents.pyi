# PyAgentEvents stub - Reforged Native surface.
# Replaces legacy PyCombatEvents. Per-agent event capture listener.
# Exact counterpart of src/listeners/agent_events_bindings.cpp.
#
# The capture is a named listener ("agent_events"), enabled by default at startup;
# toggle it via PyListeners or the enable()/disable() helpers here, then drain the
# raw event buffer each frame. All interpretation stays in Python.

from typing import List
from typing import Tuple

class PyEventType:
    """Event type constants (`m.def_submodule("PyEventType")`).

    Plain int attributes, not an enum - values come from the
    GW_AGENT_EVENT_TYPES X-macro in include/listeners/agent_events_listener.h.
    """

    SKILL_ACTIVATED: int = 1
    ATTACK_SKILL_ACTIVATED: int = 2
    SKILL_STOPPED: int = 3
    SKILL_FINISHED: int = 4
    ATTACK_SKILL_FINISHED: int = 5
    INTERRUPTED: int = 6
    INSTANT_SKILL_ACTIVATED: int = 7
    ATTACK_SKILL_STOPPED: int = 8
    ATTACK_STARTED: int = 13
    ATTACK_STOPPED: int = 14
    MELEE_ATTACK_FINISHED: int = 15
    DISABLED: int = 16
    KNOCKED_DOWN: int = 17
    CASTTIME: int = 18
    DAMAGE: int = 30
    CRITICAL: int = 31
    ARMOR_IGNORING: int = 32
    HEALING: int = 33
    CURRENT_HEALTH: int = 34
    CURRENT_ENERGY: int = 35
    HEALTH_REGEN_CHANGE: int = 36
    ENERGY_REGEN_CHANGE: int = 37
    REACHED_MAXHP: int = 38
    EFFECT_APPLIED: int = 40
    EFFECT_REMOVED: int = 41
    EFFECT_ON_TARGET: int = 42
    EFFECT_RENEWED: int = 43
    ENERGY_GAINED: int = 50
    ENERGY_SPENT: int = 51
    SKILL_DAMAGE: int = 60
    SKILL_ACTIVATE_PACKET: int = 70
    SKILL_RECHARGE: int = 80
    SKILL_RECHARGED: int = 81

class PyRawAgentEvent:
    """One captured event. All fields are read-only (def_readonly).

    agent_max_hp / agent_max_energy / target_max_hp / target_max_energy exist for
    wire compatibility with the legacy struct and are NOT populated by the capture
    layer (always 0).
    """

    timestamp: int  # System::GetTickCount64() when captured
    event_type: int  # one of the PyEventType constants
    agent_id: int  # primary agent (caster/attacker/target by event)
    value: int  # skill id, effect id, or other uint value
    target_id: int  # secondary agent (target of skill/attack)
    float_value: float  # duration, damage fraction, energy, etc.
    agent_max_hp: int
    agent_max_energy: int
    target_max_hp: int
    target_max_energy: int

    def __init__(self) -> None: ...
    def __repr__(self) -> str: ...
    def as_tuple(self) -> Tuple[int, int, int, int, int, float]:
        """(timestamp, event_type, agent_id, value, target_id, float_value)."""
        ...

def enable() -> None:
    """Install the capture hooks and start recording agent events."""
    ...

def disable() -> None:
    """Remove the capture hooks and clear the buffer."""
    ...

def is_enabled() -> bool: ...
def get_and_clear_events() -> List[PyRawAgentEvent]:
    """Return all captured events and clear the buffer (call each frame)."""
    ...

def peek_events() -> List[PyRawAgentEvent]:
    """Return the captured events without clearing (for debugging)."""
    ...

def get_event_count() -> int: ...
def get_capacity() -> int: ...
