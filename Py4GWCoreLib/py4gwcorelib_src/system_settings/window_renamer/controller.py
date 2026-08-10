"""Window Renamer controller and profiled Main callback."""

from typing import Optional

from . import model
from . import persistence


_CALLBACK_NAME = "WindowRenamer"


def _log(message: str) -> None:
    try:
        import PySystem

        PySystem.Console.Log(_CALLBACK_NAME, message, PySystem.Console.MessageType.Warning)
    except Exception:
        pass


class WindowRenamerController:
    """Rename the client window when the selected display identity changes."""

    def __init__(self) -> None:
        self.config = persistence.load()
        self._last_title = ""
        self._registered = False
        self._known_emails: list[str] = []
        self._account_emails_loaded = False
        self._settings_account_email = ""

    def set_option(self, key: str, value: object) -> None:
        if not hasattr(self.config, key):
            raise AttributeError("Unknown Window Renamer option: %s" % key)
        if key == "display_mode" and value not in model.DISPLAY_MODES:
            raise ValueError("Unknown Window Renamer display mode: %s" % value)
        setattr(self.config, key, value)
        persistence.save(self.config)
        self._last_title = ""

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

    def current_account_email(self) -> str:
        try:
            from Py4GWCoreLib.Player import Player

            return str(Player.GetAccountEmail() or "").strip()
        except Exception:
            return ""

    def refresh_account_emails(self) -> None:
        emails: set[str] = set()
        current_email = self.current_account_email()
        if current_email:
            emails.add(current_email)

        try:
            from Py4GWCoreLib.database_src.Account import Account

            for account in Account().GetAllAccounts(commit=False) or []:
                email = str(account.get("Email", "")).strip()
                if email:
                    emails.add(email)
        except Exception:
            pass

        try:
            from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE

            for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
                email = str(getattr(account, "AccountEmail", "") or "").strip()
                if email:
                    emails.add(email)
        except Exception:
            pass

        self._known_emails = sorted(emails, key=str.casefold)
        self._account_emails_loaded = True

    def known_account_emails(self) -> list[str]:
        if not self._account_emails_loaded:
            self.refresh_account_emails()
        current_email = self.current_account_email()
        if current_email and current_email not in self._known_emails:
            self._known_emails = sorted(
                [*self._known_emails, current_email],
                key=str.casefold,
            )
        return list(self._known_emails)

    @staticmethod
    def alias_for_email(email: str) -> str:
        return persistence.alias_for_email(email)

    @staticmethod
    def set_alias_for_email(email: str, alias: str) -> None:
        persistence.set_alias_for_email(email, alias)

    def _resolve_obfuscated_name(self, real_name: str) -> str:
        try:
            import PyNameObfuscator

            display_name = str(PyNameObfuscator.get_display_name(real_name) or "").strip()
            if display_name:
                return display_name
        except Exception:
            pass
        return real_name

    def _resolve_name(self, real_name: str, account_email: str) -> str:
        mode = self.config.display_mode
        if mode == "obfuscated":
            selected = self._resolve_obfuscated_name(real_name)
        elif mode == "alias":
            selected = self.alias_for_email(account_email)
        else:
            selected = real_name
        if selected or not self.config.fallback_to_character:
            return selected
        return real_name

    def _build_title(self, real_name: str, account_email: str) -> str:
        selected = self._resolve_name(real_name, account_email)
        if not selected:
            return ""
        title = "%s%s%s" % (self.config.prefix, selected, self.config.suffix)
        if self.config.append_game_name:
            title = "%s - Guild Wars" % title
        return title

    def _reload_settings_after_account_bind(self, account_email: str) -> None:
        """Reload once after account-scoped Settings acquires its email anchor."""

        if not account_email or account_email == self._settings_account_email:
            return
        self.config = persistence.load()
        self._settings_account_email = account_email
        self._last_title = ""

    def _apply(self) -> None:
        try:
            from Py4GWCoreLib.Map import Map
            from Py4GWCoreLib.Player import Player

            account_email = self.current_account_email()
            if not account_email or not persistence.is_ready():
                return
            self._reload_settings_after_account_bind(account_email)
            if not self.config.enabled:
                return
            if not Map.IsMapReady():
                return
            real_name = str(Player.GetName() or "").strip()
            if not real_name:
                return
            title = self._build_title(real_name, account_email)
            if not title or title == self._last_title:
                return

            import PySystem

            PySystem.window.set_window_title(title)
            self._last_title = title
        except Exception as exc:
            _log("window title update error: %s" % exc)


_controller: Optional[WindowRenamerController] = None


def get_controller() -> WindowRenamerController:
    """Return the process-wide Window Renamer controller."""

    global _controller
    if _controller is None:
        _controller = WindowRenamerController()
    return _controller
