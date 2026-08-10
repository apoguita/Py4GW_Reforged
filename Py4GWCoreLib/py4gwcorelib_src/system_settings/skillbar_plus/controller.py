"""Skillbar+ controller and native callback registration."""

from typing import Optional

from . import model
from . import persistence
from .runtime import SkillbarPlusRuntime


_CALLBACK_NAME = "SkillbarPlus"


def _log(message: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log(_CALLBACK_NAME, message, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


class SkillbarPlusController:
    """Own persisted settings, transient autocast slots, and the callback-driven runtime."""

    def __init__(self) -> None:
        self.config = persistence.load()
        self.autocast_slots: list[bool] = [False] * 8
        self.runtime = SkillbarPlusRuntime(self.config, self.autocast_slots)
        self._registered = False

    def set_option(self, key: str, value: object) -> None:
        if not hasattr(self.config, key):
            raise AttributeError("Unknown Skillbar+ option: %s" % key)
        setattr(self.config, key, value)
        persistence.save(self.config)

    def reset_autocast_slots(self) -> None:
        self.autocast_slots[:] = [False] * 8

    def register(self) -> None:
        """Register the complete runtime as one profiled native Draw callback."""

        try:
            import PyCallback

            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            PyCallback.PyCallback.RemoveByName(_CALLBACK_NAME)
            PyCallback.PyCallback.Register(
                _CALLBACK_NAME,
                PyCallback.Phase.Update,
                self._callback,
                priority=99,
                context=PyCallback.Context.Draw,
            )
            ProfilingRegistry().register(_CALLBACK_NAME)
            self._registered = True
        except Exception as exc:
            _log("callback registration error: %s" % exc)

    def unregister(self) -> None:
        try:
            import PyCallback

            PyCallback.PyCallback.RemoveByName(_CALLBACK_NAME)
        except Exception:
            pass
        self._registered = False

    def _callback(self) -> None:
        try:
            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            registry = ProfilingRegistry()
            if registry.enabled:
                registry.runcall_scope("widgets", "%s:draw" % _CALLBACK_NAME, self.runtime.draw)
                return
        except Exception:
            pass
        self.runtime.draw()


_controller: Optional[SkillbarPlusController] = None


def get_controller() -> SkillbarPlusController:
    """Return the process-wide Skillbar+ controller."""

    global _controller
    if _controller is None:
        _controller = SkillbarPlusController()
    return _controller
