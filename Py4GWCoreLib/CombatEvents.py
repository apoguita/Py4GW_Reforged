"""
CombatEventQueue - raw combat event access plus higher-level combat state APIs.

Reforged Native exposes combat packets through ``PyAgentEvents``.  Older
builds used ``PyCombatEvents``.  This module presents one stable queue facade
for both backends and feeds the existing higher-level callback/state layer.
"""

from __future__ import annotations

from typing import Callable, List, Tuple

import PySystem

try:
    import PyAgentEvents  # Reforged Native backend
except ModuleNotFoundError:
    PyAgentEvents = None  # type: ignore[assignment]

try:
    import PyCombatEvents  # Legacy backend, retained only for compatibility
except ModuleNotFoundError:
    PyCombatEvents = None  # type: ignore[assignment]

from .CombatEventQueue_src import helpers
from .enums import EventType


_queue = None
_initialized = False
_backend_name = "unavailable"
_native_event_type_map: dict[int, int] | None = None


class _NormalizedAgentEvent:
    """Small proxy normalizing Reforged event type values to EventType."""

    __slots__ = (
        "timestamp",
        "event_type",
        "agent_id",
        "value",
        "target_id",
        "float_value",
    )

    def __init__(self, event) -> None:
        self.timestamp = int(getattr(event, "timestamp", 0) or 0)
        self.event_type = _normalize_event_type(getattr(event, "event_type", 0))
        self.agent_id = int(getattr(event, "agent_id", 0) or 0)
        self.value = int(getattr(event, "value", 0) or 0)
        self.target_id = int(getattr(event, "target_id", 0) or 0)
        self.float_value = float(getattr(event, "float_value", 0.0) or 0.0)

    def as_tuple(self) -> Tuple[int, int, int, int, int, float]:
        return (
            self.timestamp,
            self.event_type,
            self.agent_id,
            self.value,
            self.target_id,
            self.float_value,
        )


def _build_native_event_type_map() -> dict[int, int]:
    """Map PyAgentEvents.PyEventType constants to the public EventType enum.

    Current Reforged builds use the same integer values, but resolving by name
    keeps the adapter correct if the native enum layout changes later.
    """
    mapping: dict[int, int] = {}
    native_type = getattr(PyAgentEvents, "PyEventType", None) if PyAgentEvents else None
    if native_type is None:
        return mapping
    for member in EventType:
        try:
            native_value = getattr(native_type, member.name)
            mapping[int(native_value)] = int(member)
        except Exception:
            continue
    return mapping


def _normalize_event_type(value) -> int:
    global _native_event_type_map
    try:
        raw = int(value)
    except Exception:
        return 0
    if _native_event_type_map is None:
        _native_event_type_map = _build_native_event_type_map()
    return int(_native_event_type_map.get(raw, raw))


class _AgentEventsQueueAdapter:
    """Legacy queue-shaped wrapper around Reforged's module-level API."""

    def Initialize(self) -> None:
        if PyAgentEvents is None:
            return
        try:
            if not bool(PyAgentEvents.is_enabled()):
                PyAgentEvents.enable()
        except Exception:
            # Some native builds do not expose a reliable pre-enable state.
            PyAgentEvents.enable()

    def Terminate(self) -> None:
        if PyAgentEvents is None:
            return
        try:
            if bool(PyAgentEvents.is_enabled()):
                PyAgentEvents.disable()
        except Exception:
            try:
                PyAgentEvents.disable()
            except Exception:
                pass

    def IsInitialized(self) -> bool:
        if PyAgentEvents is None:
            return False
        try:
            return bool(PyAgentEvents.is_enabled())
        except Exception:
            return False

    def GetAndClearEvents(self):
        if PyAgentEvents is None:
            return []
        try:
            return [_NormalizedAgentEvent(e) for e in (PyAgentEvents.get_and_clear_events() or [])]
        except Exception:
            return []

    def PeekEvents(self):
        if PyAgentEvents is None:
            return []
        try:
            return [_NormalizedAgentEvent(e) for e in (PyAgentEvents.peek_events() or [])]
        except Exception:
            return []

    def SetMaxEvents(self, count: int) -> None:
        # Reforged exposes a fixed native capacity, not a writable max size.
        return None

    def GetMaxEvents(self) -> int:
        if PyAgentEvents is None:
            return 0
        try:
            return int(PyAgentEvents.get_capacity() or 0)
        except Exception:
            return 0

    def GetQueueSize(self) -> int:
        if PyAgentEvents is None:
            return 0
        try:
            return int(PyAgentEvents.get_event_count() or 0)
        except Exception:
            return 0


def _ensure_init():
    """Initialize the available native combat-event backend on first use."""
    global _queue, _initialized, _backend_name
    if _initialized and _queue is not None:
        return

    try:
        if PyAgentEvents is not None:
            candidate = _AgentEventsQueueAdapter()
            candidate.Initialize()
            if candidate.IsInitialized():
                _queue = candidate
                _backend_name = "PyAgentEvents"
                _initialized = True
                return

        if PyCombatEvents is not None:
            candidate = PyCombatEvents.GetCombatEventQueue()
            if not candidate.IsInitialized():
                candidate.Initialize()
            if candidate.IsInitialized():
                _queue = candidate
                _backend_name = "PyCombatEvents"
                _initialized = True
                return

        _queue = None
        _backend_name = "unavailable"
        _initialized = False
    except Exception as exc:
        # Keep retrying on later calls; native hooks can become available after
        # the first module-import frame.
        _queue = None
        _initialized = False
        _backend_name = f"unavailable: {exc!r}"


#region CombatEventQueue
class CombatEventQueue:
    """Raw combat-event queue facade shared by Reforged and legacy builds."""

    @staticmethod
    def IsAvailable() -> bool:
        return PyAgentEvents is not None or PyCombatEvents is not None

    @staticmethod
    def GetBackendName() -> str:
        _ensure_init()
        return str(_backend_name)

    @staticmethod
    def GetQueue():
        _ensure_init()
        return _queue

    @staticmethod
    def Initialize():
        _ensure_init()
        if _queue and not _queue.IsInitialized():
            _queue.Initialize()

    @staticmethod
    def Terminate():
        _ensure_init()
        if _queue and _queue.IsInitialized():
            _queue.Terminate()

    @staticmethod
    def IsInitialized() -> bool:
        _ensure_init()
        return bool(_queue and _queue.IsInitialized())

    @staticmethod
    def GetAndClearEvents():
        _ensure_init()
        if not _queue:
            return []
        return _queue.GetAndClearEvents()

    @staticmethod
    def PeekEvents():
        _ensure_init()
        if not _queue:
            return []
        return _queue.PeekEvents()

    @staticmethod
    def GetAndClearEventTuples() -> List[Tuple[int, int, int, int, int, float]]:
        return [event.as_tuple() for event in CombatEventQueue.GetAndClearEvents()]

    @staticmethod
    def PeekEventTuples() -> List[Tuple[int, int, int, int, int, float]]:
        return [event.as_tuple() for event in CombatEventQueue.PeekEvents()]

    @staticmethod
    def SetMaxEvents(count: int):
        _ensure_init()
        if _queue:
            _queue.SetMaxEvents(count)

    @staticmethod
    def GetMaxEvents() -> int:
        _ensure_init()
        if not _queue:
            return 0
        return int(_queue.GetMaxEvents() or 0)

    @staticmethod
    def GetQueueSize() -> int:
        _ensure_init()
        if not _queue:
            return 0
        return int(_queue.GetQueueSize() or 0)


#region CombatEvents
class CombatEvents:
    """Public combat-event manager and callback API."""

    _callback_name = "CombatEvents.Update"

    @staticmethod
    def GetEvents() -> List[Tuple[int, int, int, int, int, float]]:
        if not helpers._is_callback_active():
            return []
        return list(helpers._events)

    @staticmethod
    def ClearEvents():
        helpers._events.clear()

    @staticmethod
    def GetRecentDamage(count: int = 20) -> List[Tuple[int, int, int, float, int, bool]]:
        if not helpers._is_callback_active():
            return []
        result = []
        for ts, etype, agent, val, target, fval in reversed(list(helpers._events)):
            if etype in (helpers.EventType.DAMAGE, helpers.EventType.CRITICAL, helpers.EventType.ARMOR_IGNORING):
                result.append((ts, agent, target, fval, val, etype == helpers.EventType.CRITICAL))
                if len(result) >= count:
                    break
        return list(reversed(result))

    @staticmethod
    def GetRecentHealing(count: int = 20) -> List[Tuple[int, int, int, float, int]]:
        return helpers._get_recent_healing(count)

    @staticmethod
    def GetRecentEffectRenewals(count: int = 20) -> List[Tuple[int, int, int]]:
        return helpers._get_recent_effect_renewals(count)

    @staticmethod
    def GetRecentSkills(count: int = 20) -> List[Tuple[int, int, int, int, int]]:
        if not helpers._is_callback_active():
            return []
        skill_types = {
            helpers.EventType.SKILL_ACTIVATE_PACKET,
            helpers.EventType.SKILL_ACTIVATED,
            helpers.EventType.ATTACK_SKILL_ACTIVATED,
            helpers.EventType.SKILL_FINISHED,
            helpers.EventType.ATTACK_SKILL_FINISHED,
            helpers.EventType.INTERRUPTED,
            helpers.EventType.INSTANT_SKILL_ACTIVATED,
        }
        result = []
        for ts, etype, agent, val, target, _ in reversed(list(helpers._events)):
            if etype in skill_types:
                result.append((ts, agent, val, target, etype))
                if len(result) >= count:
                    break
        return list(reversed(result))

    @staticmethod
    def OnSkillActivated(cb: Callable[[int, int, int], None]):
        helpers._callbacks.setdefault("skill_activated", []).append(cb)

    @staticmethod
    def OnSkillActivatedTimed(cb: Callable[[int, int, int, int], None]):
        """Register a cast-start callback that also receives native timestamp."""
        helpers._callbacks.setdefault("skill_activated_timed", []).append(cb)

    @staticmethod
    def OnSkillFinished(cb: Callable[[int, int], None]):
        helpers._callbacks.setdefault("skill_finished", []).append(cb)

    @staticmethod
    def OnSkillStopped(cb: Callable[[int, int], None]):
        helpers._callbacks.setdefault("skill_stopped", []).append(cb)

    @staticmethod
    def OnSkillInterrupted(cb: Callable[[int, int], None]):
        helpers._callbacks.setdefault("skill_interrupted", []).append(cb)

    @staticmethod
    def OnCastTime(cb: Callable[[int, int, float], None]):
        helpers._callbacks.setdefault("cast_time", []).append(cb)

    @staticmethod
    def OnAttackStarted(cb: Callable[[int, int], None]):
        helpers._callbacks.setdefault("attack_started", []).append(cb)

    @staticmethod
    def OnKnockdown(cb: Callable[[int, float], None]):
        helpers._callbacks.setdefault("knockdown", []).append(cb)

    @staticmethod
    def OnDamage(cb: Callable[[int, int, float, int], None]):
        helpers._callbacks.setdefault("damage", []).append(cb)

    @staticmethod
    def OnHealing(cb: Callable[[int, int, float, int], None]):
        helpers._callbacks.setdefault("healing", []).append(cb)

    @staticmethod
    def OnEffectRenewed(cb: Callable[[int, int], None]):
        helpers._callbacks.setdefault("effect_renewed", []).append(cb)

    @staticmethod
    def OnAftercastEnded(cb: Callable[[int], None]):
        helpers._callbacks.setdefault("aftercast_ended", []).append(cb)

    @staticmethod
    def OnSkillRechargeStarted(cb: Callable[[int, int, int], None]):
        helpers._callbacks.setdefault("skill_recharge_started", []).append(cb)

    @staticmethod
    def OnSkillRecharged(cb: Callable[[int, int], None]):
        helpers._callbacks.setdefault("skill_recharged", []).append(cb)

    @staticmethod
    def ClearCallbacks():
        helpers._callbacks.clear()

    @staticmethod
    def ClearRechargeData(agent_id: int):
        helpers._recharges.pop(agent_id, None)

    @staticmethod
    def Update():
        helpers._process_pending_events(CombatEventQueue)

    @staticmethod
    def Enable() -> bool:
        if not CombatEventQueue.IsAvailable():
            helpers._set_callback_active(False)
            return False

        CombatEventQueue.Initialize()
        if not CombatEventQueue.IsInitialized():
            helpers._set_callback_active(False)
            return False

        try:
            import PyCallback
            try:
                PyCallback.PyCallback.RemoveByName(CombatEvents._callback_name)
            except Exception:
                pass
            helpers._set_callback_active(True)
            PyCallback.PyCallback.Register(
                CombatEvents._callback_name,
                PyCallback.Phase.Data,
                CombatEvents.Update,
                priority=7,
                context=PyCallback.Context.Draw,
            )
            return True
        except Exception:
            helpers._set_callback_active(False)
            return False

    @staticmethod
    def Disable():
        helpers._set_callback_active(False)
        try:
            import PyCallback
            PyCallback.PyCallback.RemoveByName(CombatEvents._callback_name)
        except Exception:
            pass
        CombatEventQueue.Terminate()


COMBAT_EVENTS = CombatEvents()

try:
    enabled = CombatEvents.Enable()
    if enabled:
        PySystem.Console.Log(
            "CombatEvents",
            f"Native combat events active via {CombatEventQueue.GetBackendName()}",
            PySystem.Console.MessageType.Info,
        )
    else:
        PySystem.Console.Log(
            "CombatEvents",
            "Native event backend unavailable; polling fallback remains active",
            PySystem.Console.MessageType.Warning,
        )
except Exception as exc:
    PySystem.Console.Log(
        "CombatEvents",
        f"Event initialization failed; polling fallback remains active: {exc}",
        PySystem.Console.MessageType.Warning,
    )


EventTypes = EventType
