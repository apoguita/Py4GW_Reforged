"""JSON load/save for simple launcher-wide settings that don't belong to any
single profile or team. Currently just the bulk launch pacing delay -- a single
persisted number, so a dedicated settings screen isn't warranted yet.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

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


def load_bulk_launch_pacing_seconds(path: Path | str | None = None) -> int:
    resolved = Path(path) if path is not None else default_settings_path()
    if not resolved.exists():
        return DEFAULT_BULK_LAUNCH_PACING_SECONDS

    data = json.loads(resolved.read_text(encoding="utf-8"))
    return int(data.get("bulk_launch_pacing_seconds", DEFAULT_BULK_LAUNCH_PACING_SECONDS))


def save_bulk_launch_pacing_seconds(seconds: int, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps({"bulk_launch_pacing_seconds": seconds}, indent=2), encoding="utf-8")
