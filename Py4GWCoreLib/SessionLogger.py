"""Small file-backed session logger for runtime diagnostics."""

from __future__ import annotations

from datetime import datetime
import os
import threading


class SessionLogger:
    def __init__(self, name: str):
        self.name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(name)) or "session"
        self._path = ""
        self._lock = threading.Lock()

    @property
    def path(self) -> str:
        self._ensure_path()
        return self._path

    def _ensure_path(self) -> None:
        if self._path:
            return
        try:
            import PySystem

            root = str(PySystem.Console.get_projects_path() or ".")
            log_dir = os.path.join(root, "Logs", "Sessions")
            os.makedirs(log_dir, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._path = os.path.join(log_dir, f"{self.name}_{stamp}_{os.getpid()}.log")
        except Exception:
            # Diagnostics must never stop the bot.
            self._path = ""

    def write(self, message: str) -> None:
        self._ensure_path()
        if not self._path:
            return
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] {message}\n"
        try:
            with self._lock:
                with open(self._path, "a", encoding="utf-8") as handle:
                    handle.write(line)
        except Exception:
            pass


_LOGGERS: dict[str, SessionLogger] = {}


def get_session_logger(name: str) -> SessionLogger:
    key = str(name)
    if key not in _LOGGERS:
        _LOGGERS[key] = SessionLogger(key)
    return _LOGGERS[key]
