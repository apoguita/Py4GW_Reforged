"""Profiled map-load callback for automatic reputation-title selection."""

from typing import Optional

from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.Quest import Quest
from Py4GWCoreLib.routines_src.Checks import Checks

from . import model
from . import persistence


_CALLBACK_NAME = "Title On Map Load"


def _log(message: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log(_CALLBACK_NAME, message, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


class TitleOnMapLoadController:
    """Apply one configured reputation title after each supported map load."""

    def __init__(self) -> None:
        self.config = persistence.load()
        self._registered = False
        self._settings_account_email = ""
        self._last_map_id = 0
        self._title_applied = False

    def set_enabled(self, enabled: bool) -> None:
        self.config.enabled = bool(enabled)
        persistence.save(self.config)
        self._title_applied = False

    def register(self) -> None:
        """Register one profiled Main callback, idempotently across widget reloads."""

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

    def _refresh_local_config_after_bind(self) -> bool:
        try:
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
        self._title_applied = False
        return True

    @staticmethod
    def _title_for_map(map_name: str, map_id: int) -> Optional[model.TitleID]:
        try:
            quest_ids = set(Quest.GetQuestLogIds())
            for quest_id, title_id in model.QUEST_TITLE_OVERRIDES.items():
                if quest_id in quest_ids:
                    return title_id
        except Exception:
            pass

        for rule in model.TITLE_MAP_RULES:
            if map_name in rule.map_names or map_id in rule.map_ids:
                return rule.title_id
        return None

    def _reset_for_unready_map(self) -> None:
        self._last_map_id = 0
        self._title_applied = False

    def _apply(self) -> None:
        if not self._refresh_local_config_after_bind() or not self.config.enabled:
            return

        try:
            if not Checks.Map.MapValid() or not Map.IsExplorable():
                self._reset_for_unready_map()
                return

            map_id = int(Map.GetMapID() or 0)
            if map_id != self._last_map_id:
                self._last_map_id = map_id
                self._title_applied = False
            if self._title_applied:
                return

            title_id = self._title_for_map(str(Map.GetMapName() or ""), map_id)
            if title_id is not None:
                Player.SetActiveTitle(int(title_id))
            self._title_applied = True
        except Exception as exc:
            _log("title update error: %s" % exc)


_controller: Optional[TitleOnMapLoadController] = None


def get_controller() -> TitleOnMapLoadController:
    """Return the process-wide title-on-map-load controller."""

    global _controller
    if _controller is None:
        _controller = TitleOnMapLoadController()
    return _controller
