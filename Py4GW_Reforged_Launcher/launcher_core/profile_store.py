"""JSON load/save for a list of GameProfile.

New schema, not a migration target -- GWxLauncher's own profiles.json (and its
accounts.json legacy import) are a separate, later task. This deliberately writes to
its own AppData subfolder rather than GWxLauncher's, so the two launchers' profile
stores can never collide or be misread as each other's format.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from launcher_core.profile import GameProfile

APPDATA_SUBDIR = "Py4GW_Reforged_Launcher"
# GWxLauncherPy was this project's own leftover placeholder AppData folder name from
# before it settled on Py4GW_Reforged_Launcher -- not to be confused with the
# separate C# GWxLauncher project. Kept only so _migrate_legacy_profiles_if_needed()
# can find and copy forward anyone's existing profiles.json one time; never written
# to.
_LEGACY_APPDATA_SUBDIR = "GWxLauncherPy"
PROFILES_FILENAME = "profiles.json"


def default_profiles_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("%APPDATA% is not set -- expected on Windows")
    return Path(appdata) / APPDATA_SUBDIR / PROFILES_FILENAME


def _legacy_profiles_path() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / _LEGACY_APPDATA_SUBDIR / PROFILES_FILENAME


def _migrate_legacy_profiles_if_needed() -> None:
    """If the new AppData folder has no profiles.json yet but the old GWxLauncherPy
    one does, copy it over once rather than silently orphaning profiles saved under
    the old placeholder name. Only applies to the default AppData location --
    callers passing an explicit path are opting out of default-location behavior
    entirely, migration included.
    """
    new_path = default_profiles_path()
    if new_path.exists():
        return

    legacy_path = _legacy_profiles_path()
    if legacy_path is None or not legacy_path.exists():
        return

    new_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy_path, new_path)


def load_profiles(path: Path | str | None = None) -> list[GameProfile]:
    """Load profiles from `path` (or the default AppData location).

    Missing file -> empty list, same as a fresh install. Does not attempt recovery
    on malformed JSON; that's a corrupt-file problem, not something to silently paper
    over for data this sensitive.
    """
    if path is None:
        _migrate_legacy_profiles_if_needed()

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
