"""JSON load/save for simple launcher-wide settings that don't belong to any
single profile or team: the bulk launch pacing delay, and the configured
location of the Py4GW_Reforged mod-repo checkout (launcher_core.mod_repo).

All settings live in one shared JSON file, so every save here reads the
current file, merges in just the one key being changed, and writes the whole
dict back -- overwriting the file with a single-key dict (an earlier version
of this module did exactly that for the one setting that existed then) would
silently discard whichever other setting was already stored, the moment a
second setting was added.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

APPDATA_SUBDIR = "Py4GW_Reforged_Launcher"
SETTINGS_FILENAME = "launcher_settings.json"

# Reasonable default within bulk_launch.py's [MIN_PACING_SECONDS, MAX_PACING_SECONDS]
# clamp range -- this is just a starting value for a fresh install, not itself a
# safety control. The real floor/ceiling enforcement lives in bulk_launch.py's
# clamp_pacing_seconds(), which runs regardless of what's stored here.
DEFAULT_BULK_LAUNCH_PACING_SECONDS = 30


def default_settings_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("%APPDATA% is not set -- expected on Windows")
    return Path(appdata) / APPDATA_SUBDIR / SETTINGS_FILENAME


def _load_all(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_one(key: str, value: object, path: Path) -> None:
    data = _load_all(path)
    data[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_bulk_launch_pacing_seconds(path: Path | str | None = None) -> int:
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    return int(data.get("bulk_launch_pacing_seconds", DEFAULT_BULK_LAUNCH_PACING_SECONDS))


def save_bulk_launch_pacing_seconds(seconds: int, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("bulk_launch_pacing_seconds", seconds, resolved)


def load_mod_repo_path(path: Path | str | None = None) -> Optional[str]:
    """None means "use the default" (launcher_core.config_seeding's own
    _mod_root() assumption -- this launcher's own parent directory) --
    callers resolve that default themselves rather than this module
    duplicating that path logic, per the task that added this."""
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    value = data.get("mod_repo_path")
    return str(value) if value else None


def save_mod_repo_path(mod_repo_path: str, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("mod_repo_path", mod_repo_path, resolved)
