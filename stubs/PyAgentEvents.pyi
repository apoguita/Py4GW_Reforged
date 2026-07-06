# PyAgentEvents stub — Reforged Native surface (2026-07-06)
# Replaces legacy PyCombatEvents. Per-agent event capture listener.
# Matches agent_events_bindings.cpp.

from typing import List, Tuple

class PyEventType:
    # Event type constants (populated at runtime via GW_AGENT_EVENT_TYPES)
    pass

class PyRawAgentEvent:
    timestamp: int
    event_type: int
    agent_id: int
    value: int
    target_id: int
    float_value: float
    agent_max_hp: int
    agent_max_energy: int
    target_max_hp: int
    target_max_energy: int

    def __init__(self) -> None: ...
    def as_tuple(self) -> Tuple[int, int, int, int, int, float]: ...

def enable() -> None:
    """Install the capture hooks and start recording agent events."""

def disable() -> None:
    """Remove the capture hooks and clear the buffer."""

def is_enabled() -> bool: ...

def get_and_clear_events() -> List[PyRawAgentEvent]:
    """Return all captured events and clear the buffer (call each frame)."""

def peek_events() -> List[PyRawAgentEvent]:
    """Return the captured events without clearing (for debugging)."""

def get_event_count() -> int: ...

def get_capacity() -> int: ...
