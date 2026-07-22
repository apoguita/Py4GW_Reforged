"""System Settings controller — the process-wide singleton that owns the options state.

Responsibilities:
  * hold the current values (each listener's enabled flag + sub-option values), loaded from disk;
  * **register them with the native side** — apply the persisted state to ``PyListeners`` at boot
    (``apply_all_to_native``), and on every change (``set_listener_enabled`` / ``set_option``);
  * own the options-window visibility (hidden by default; toggled by the System launchpad cog);
  * build + draw the options window (a ``SidebarWindow``) on demand.

One instance per process (``get_overlay``-style singleton), shared by the always-on System widget
that renders it and the launch-bar action that toggles it — see :func:`get_controller`. ``PyListeners``
is imported lazily so this module stays import-safe offline.
"""

from typing import Optional

from . import model
from . import persistence


def _pylisteners():
    """The native ``PyListeners`` module, or None when unavailable (offline)."""
    try:
        import PyListeners

        return PyListeners
    except Exception:
        return None


class LibrarySettingsController:
    def __init__(self) -> None:
        self.enabled: "dict[str, bool]" = {}
        self.options: "dict[str, object]" = {}
        persistence.load(self.enabled, self.options)
        self._window_open: bool = False          # hidden until the launchpad cog toggles it
        self._sidebar = None                     # lazily built SidebarWindow

    # ── queries used by the UI ───────────────────────────────────────────────────────────
    def is_enabled(self, lsn: "model.Listener") -> bool:
        return bool(self.enabled.get(lsn.name, lsn.default_enabled))

    def option_value(self, lsn: "model.Listener", opt) -> object:
        return self.options.get("%s.%s" % (lsn.name, opt.key), opt.default)

    # ── native application (register options with cpp) ───────────────────────────────────
    def apply_all_to_native(self) -> None:
        """Push every persisted value to ``PyListeners``. Called once at boot by the widget."""
        pl = _pylisteners()
        if pl is None:
            return
        for cat in model.CATALOG:
            for lsn in cat.listeners:
                self._apply_listener(pl, lsn)

    def _apply_listener(self, pl, lsn: "model.Listener") -> None:
        try:
            pl.set_enabled(lsn.name, self.is_enabled(lsn))
        except Exception:
            pass
        for opt in lsn.options:
            self._apply_option(pl, lsn, opt)

    def _apply_option(self, pl, lsn: "model.Listener", opt) -> None:
        setter = getattr(pl, opt.setter, None)
        if callable(setter):
            try:
                setter(self.option_value(lsn, opt))
            except Exception:
                pass

    # ── mutations (persist + apply live) ─────────────────────────────────────────────────
    def set_listener_enabled(self, cat_key: str, lsn: "model.Listener", value: bool) -> None:
        value = bool(value)
        self.enabled[lsn.name] = value
        persistence.save_enabled(cat_key, lsn.name, value)
        pl = _pylisteners()
        if pl is None:
            return
        try:
            pl.set_enabled(lsn.name, value)
        except Exception:
            pass
        if value:  # re-assert this listener's options when it turns on
            for opt in lsn.options:
                self._apply_option(pl, lsn, opt)

    def set_option(self, cat_key: str, lsn: "model.Listener", opt, value) -> None:
        self.options["%s.%s" % (lsn.name, opt.key)] = value
        persistence.save_option(cat_key, lsn.name, opt.key, value)
        pl = _pylisteners()
        if pl is not None:
            self._apply_option(pl, lsn, opt)

    # ── window visibility (driven by the launchpad cog) ──────────────────────────────────
    def is_window_open(self) -> bool:
        return self._window_open

    def open(self) -> None:
        self._window_open = True

    def close(self) -> None:
        self._window_open = False

    def toggle_window(self) -> None:
        self._window_open = not self._window_open

    # ── render (only while toggled open) ─────────────────────────────────────────────────
    def draw(self) -> None:
        if not self._window_open:
            return
        if self._sidebar is None:
            from . import config_ui

            self._sidebar = config_ui.build_window(self)
        self._sidebar.draw()


# ── process-wide singleton + module-level convenience API ────────────────────────────────
_controller: Optional[LibrarySettingsController] = None


def get_controller() -> LibrarySettingsController:
    """Return the process-wide controller, creating (and loading) it on first use."""
    global _controller
    if _controller is None:
        _controller = LibrarySettingsController()
    return _controller


def toggle_window() -> None:
    get_controller().toggle_window()


def is_window_open() -> bool:
    return get_controller().is_window_open()


def open_window() -> None:
    get_controller().open()


def close_window() -> None:
    get_controller().close()
