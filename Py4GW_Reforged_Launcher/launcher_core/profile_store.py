"""JSON load/save for a list of GameProfile.

New schema, not a migration target -- GWxLauncher's own profiles.json (and its
accounts.json legacy import) are a separate, later task. This deliberately writes to
its own AppData subfolder rather than GWxLauncher's, so the two launchers' profile
stores can never collide or be misread as each other's format.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from launcher_core.profile import GameProfile

APPDATA_SUBDIR = "GWxLauncherPy"
PROFILES_FILENAME = "profiles.json"


def default_profiles_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("%APPDATA% is not set -- expected on Windows")
    return Path(appdata) / APPDATA_SUBDIR / PROFILES_FILENAME


def load_profiles(path: Path | str | None = None) -> list[GameProfile]:
    """Load profiles from `path` (or the default AppData location).

    Missing file -> empty list, same as a fresh install. Does not attempt recovery
    on malformed JSON; that's a corrupt-file problem, not something to silently paper
    over for data this sensitive.
    """
    resolved = Path(path) if path is not None else default_profiles_path()

    if not resolved.exists():
        return []

    raw = json.loads(resolved.read_text(encoding="utf-8"))
    return [GameProfile.from_dict(entry) for entry in raw]


def save_profiles(profiles: list[GameProfile], path: Path | str | None = None) -> None:
    """Save `profiles` to `path` (or the default AppData location), pretty-printed."""
    resolved = Path(path) if path is not None else default_profiles_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)

    payload = [p.to_dict() for p in profiles]
    resolved.write_text(json.dumps(payload, indent=2), encoding="utf-8")
