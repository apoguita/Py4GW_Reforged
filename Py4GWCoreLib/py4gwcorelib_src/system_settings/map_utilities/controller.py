"""Profiled runtime callback for the migrated Map & Missions utilities."""

from typing import Optional

import PyImGui

from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib import ImGui
from Py4GWCoreLib import Map
from Py4GWCoreLib import FormatTime
from Py4GWCoreLib.Effect import Effects
from Py4GWCoreLib.ImGui_src.types import Alignment
from Py4GWCoreLib.py4gwcorelib_src.Timer import ThrottledTimer

from . import model
from . import persistence


_CALLBACK_NAME = "Map Utilities"
_POLL_INTERVAL_MS = 50
_ALCOHOL_INTERVAL_MS = 1000


def _log(message: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log(_CALLBACK_NAME, message, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


def _normalise_color(color: model.RGBA) -> tuple[float, float, float, float]:
    return tuple(channel / 255.0 for channel in color)  # type: ignore[return-value]


class MapUtilitiesController:
    """Own the two overlays and the alcohol-effect suppression pass."""

    def __init__(self) -> None:
        self.config = persistence.load()
        self._poll_timer = ThrottledTimer(_POLL_INTERVAL_MS)
        self._alcohol_timer = ThrottledTimer(_ALCOHOL_INTERVAL_MS)
        self._registered = False
        self._settings_account_email = ""
        self._map_id = -1
        self._instance_entry_time = 0
        self._instance_uptime = 0
        self._instance_initialized = False
        self._map_ready = False
        self._party_loaded = False
        self._vanquish_valid = False
        self._killed = 0
        self._total = 0

    def save(self) -> None:
        persistence.save(self.config)

    def register(self) -> None:
        """Register one profiled Draw callback, idempotently across widget reloads."""

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
                registry.runcall_scope("widgets", "%s:main" % _CALLBACK_NAME, self._run_frame)
                return
        except Exception:
            pass
        self._run_frame()

    def _poll_map_state(self) -> None:
        if not self._poll_timer.IsExpired():
            return
        self._poll_timer.Reset()

        self._map_ready = bool(Map.IsMapReady())
        self._party_loaded = bool(GLOBAL_CACHE.Party.IsPartyLoaded()) if self._map_ready else False
        if not self._map_ready:
            self._map_id = -1
            self._instance_initialized = False
            self._vanquish_valid = False
            return

        current_map_id = int(Map.GetMapID() or 0)
        if not self._instance_initialized or current_map_id != self._map_id:
            self._map_id = current_map_id
            self._instance_entry_time = int(Map.GetInstanceUptime() or 0)
            self._instance_initialized = True

        if self._party_loaded:
            self._instance_uptime = int(Map.GetInstanceUptime() or 0) - (
                0 if self.config.true_instance_timer else self._instance_entry_time
            )
            is_explorable = bool(Map.IsExplorable())
            is_vanquishable = bool(Map.IsVanquishable())
            is_hard_mode = bool(GLOBAL_CACHE.Party.IsHardMode())
            self._vanquish_valid = is_explorable and is_vanquishable and is_hard_mode
            if self._vanquish_valid:
                self._killed = int(Map.GetFoesKilled() or 0)
                self._total = self._killed + int(Map.GetFoesToKill() or 0)
            return

        self._vanquish_valid = False

    def _refresh_local_config_after_bind(self) -> bool:
        """Wait for the account document before applying local enable switches."""

        try:
            from Py4GWCoreLib.Player import Player

            account_email = str(Player.GetAccountEmail() or "").strip()
        except Exception:
            return False
        if not account_email:
            return False
        if account_email == self._settings_account_email:
            return True
        if not persistence.local_is_ready():
            return False
        self.config = persistence.load()
        self._settings_account_email = account_email
        return True

    def _clear_alcohol_effect(self) -> None:
        if not self.config.disable_alcohol_effect or not self._alcohol_timer.IsExpired():
            return
        self._alcohol_timer.Reset()
        if not Map.IsMapReady():
            return
        if Effects.GetAlcoholLevel() > 0:
            Effects.ApplyDrunkEffect(0, 0)

    @staticmethod
    def _overlay_flags(include_mouse_inputs: bool = True):
        flags = PyImGui.WindowFlags.NoBackground | PyImGui.WindowFlags.NoTitleBar
        flags |= PyImGui.WindowFlags.NoCollapse
        if include_mouse_inputs:
            flags |= PyImGui.WindowFlags.NoMouseInputs
        return flags

    def _draw_vanquish(self) -> None:
        style = self.config.vanquish
        text = "%d/%d" % (self._killed, self._total)
        PyImGui.set_next_window_pos(style.x, style.y)
        ImGui.push_font("Regular", style.font_size)
        text_size = ImGui.calc_text_size("999/999")
        PyImGui.set_next_window_size(text_size[0] + 20, text_size[1] + 20)
        if PyImGui.begin("Vanquish Monitor##MapUtilitiesVanquish", self._overlay_flags()):
            PyImGui.push_style_color(PyImGui.ImGuiCol.Text, _normalise_color(style.color))
            ImGui.text_aligned(text, text_size[0], text_size[1], alignment=Alignment.MidRight)
            PyImGui.pop_style_color(1)
        PyImGui.end()
        ImGui.pop_font()

    def _draw_instance_timer(self) -> None:
        style = self.config.instance_timer
        mask = "hh:mm:ss:ms" if self._instance_uptime > 3600000 else "mm:ss:ms"
        text = FormatTime(self._instance_uptime, mask)
        PyImGui.set_next_window_pos(style.x, style.y)
        if PyImGui.begin("Instance Timer##MapUtilitiesInstance", self._overlay_flags(False)):
            ImGui.push_font("Regular", style.font_size)
            PyImGui.push_style_color(PyImGui.ImGuiCol.Text, _normalise_color(style.color))
            PyImGui.text(text)
            PyImGui.pop_style_color(1)
            ImGui.pop_font()
        PyImGui.end()

    def _run_frame(self) -> None:
        if not self._refresh_local_config_after_bind():
            return
        if not (
            self.config.vanquish_enabled
            or self.config.instance_timer_enabled
            or self.config.disable_alcohol_effect
        ):
            return

        if self.config.vanquish_enabled or self.config.instance_timer_enabled:
            self._poll_map_state()
        self._clear_alcohol_effect()

        if self._map_ready and self._party_loaded:
            if self.config.vanquish_enabled and self._vanquish_valid:
                self._draw_vanquish()
            if self.config.instance_timer_enabled:
                self._draw_instance_timer()


_controller: Optional[MapUtilitiesController] = None


def get_controller() -> MapUtilitiesController:
    """Return the process-wide Map Utilities controller."""

    global _controller
    if _controller is None:
        _controller = MapUtilitiesController()
    return _controller
