"""Camera-smoothing controller and profiled native callback."""

from typing import Optional

from Py4GWCoreLib.Camera import Camera

from . import model
from . import persistence


_CALLBACK_NAME = "DisableCameraSmoothing"


def _log(message: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log(_CALLBACK_NAME, message, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


class CameraSmoothingController:
    """Own the persisted toggle and execute the original camera update from a native callback."""

    def __init__(self) -> None:
        self.config = persistence.load()
        self._registered = False

    def set_disabled(self, disabled: bool) -> None:
        self.config.disable_smoothing = bool(disabled)
        persistence.save(self.config)

    def register(self) -> None:
        """Register the original per-frame operation as a profiled Main callback."""

        try:
            import PyCallback

            from Py4GWCoreLib.py4gwcorelib_src.Profiling import ProfilingRegistry

            PyCallback.PyCallback.RemoveByName(_CALLBACK_NAME)
            PyCallback.PyCallback.Register(
                _CALLBACK_NAME,
                PyCallback.Phase.Update,
                self._callback,
                priority=99,
                context=PyCallback.Context.Main,
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
                registry.runcall_scope("widgets", "%s:main" % _CALLBACK_NAME, self._apply)
                return
        except Exception:
            pass
        self._apply()

    def _apply(self) -> None:
        if not self.config.disable_smoothing:
            return
        try:
            position = Camera.GetCameraPositionToGo()
            Camera.SetCameraPosition(position[0], position[1], position[2])
        except Exception as exc:
            _log("camera update error: %s" % exc)


_controller: Optional[CameraSmoothingController] = None


def get_controller() -> CameraSmoothingController:
    """Return the process-wide camera-smoothing controller."""

    global _controller
    if _controller is None:
        _controller = CameraSmoothingController()
    return _controller
