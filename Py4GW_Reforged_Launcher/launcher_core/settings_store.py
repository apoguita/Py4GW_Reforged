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
    """None means "use the default" (launcher_core.mod_root's own
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


# Today's actual mod-repo URL -- externalized from launcher_core.mod_repo's
# own module constant so it's a quiet one-file-edit escape hatch (edit the
# JSON key by hand) rather than a hardcoded value baked into shipped code,
# without adding a user-facing setting for it.
DEFAULT_MOD_REPO_URL = "https://github.com/apoguita/Py4GW_Reforged.git"


def load_mod_repo_url(path: Path | str | None = None) -> str:
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    return str(data.get("mod_repo_url", DEFAULT_MOD_REPO_URL))


def save_mod_repo_url(mod_repo_url: str, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("mod_repo_url", mod_repo_url, resolved)


# Where the launcher's own releases are checked/published (launcher_core.
# update_check) -- "owner/repo" form, not a full URL, since that's what
# GitHub's REST API path needs directly. Deliberately set to the eventual
# final (upstream) home, not today's actual fork this is being developed
# and released from -- same externalization shape as DEFAULT_MOD_REPO_URL
# above (a quiet one-file JSON edit, no in-app UI control), so testing
# against the real fork right now is just a launcher_release_repo override
# in launcher_settings.json, with no code change needed once/if this
# actually lands upstream.
DEFAULT_LAUNCHER_RELEASE_REPO = "apoguita/Py4GW_Reforged"


def load_launcher_release_repo(path: Path | str | None = None) -> str:
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    return str(data.get("launcher_release_repo", DEFAULT_LAUNCHER_RELEASE_REPO))


def save_launcher_release_repo(launcher_release_repo: str, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("launcher_release_repo", launcher_release_repo, resolved)


def load_dark_theme_enabled(path: Path | str | None = None) -> bool:
    """Default True (dark) -- matches this launcher's existing behavior
    before the light theme existed, so an upgrade with no stored preference
    yet doesn't change anyone's UI out from under them."""
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    return bool(data.get("dark_theme_enabled", True))


def save_dark_theme_enabled(dark_theme_enabled: bool, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("dark_theme_enabled", dark_theme_enabled, resolved)


def load_multiclient_enabled(path: Path | str | None = None) -> bool:
    """Default True -- no behavior change for existing installs until a user
    actually flips this off in App Settings."""
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    return bool(data.get("multiclient_enabled", True))


def save_multiclient_enabled(multiclient_enabled: bool, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("multiclient_enabled", multiclient_enabled, resolved)


def load_py4gw_injection_enabled(path: Path | str | None = None) -> bool:
    """Default True -- no behavior change for existing installs until a user
    actually flips this off in App Settings. Master switch across all
    profiles, independent of each profile's own py4gw_enabled toggle --
    see load_gmod_injection_enabled below for the sibling gMod switch this
    was modeled to make room for."""
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    return bool(data.get("py4gw_injection_enabled", True))


def save_py4gw_injection_enabled(py4gw_injection_enabled: bool, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("py4gw_injection_enabled", py4gw_injection_enabled, resolved)


def load_gmod_injection_enabled(path: Path | str | None = None) -> bool:
    """Default True -- no behavior change for existing installs until a user
    actually flips this off in App Settings. Master switch across all
    profiles, independent of each profile's own gmod_enabled toggle -- same
    shape as load_py4gw_injection_enabled above."""
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    return bool(data.get("gmod_injection_enabled", True))


def save_gmod_injection_enabled(gmod_injection_enabled: bool, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("gmod_injection_enabled", gmod_injection_enabled, resolved)


def load_custom_card_order_enabled(path: Path | str | None = None) -> bool:
    """Default False -- fresh installs and anyone who's never dragged a card
    get plain alphabetical order. Flips to True the moment a drag-and-drop
    reorder actually happens (see show_main_window's card grid loop); no
    separate UI toggle exists for this, only "Reset to alphabetical" in App
    Settings turns it back off."""
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    return bool(data.get("custom_card_order_enabled", False))


def save_custom_card_order_enabled(custom_card_order_enabled: bool, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("custom_card_order_enabled", custom_card_order_enabled, resolved)


def load_minimize_to_tray_enabled(path: Path | str | None = None) -> bool:
    """Default False -- opt-in, matches current behavior (plain taskbar minimize)
    for existing installs and anyone who hasn't turned this on in App Settings."""
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    return bool(data.get("minimize_to_tray_enabled", False))


def save_minimize_to_tray_enabled(minimize_to_tray_enabled: bool, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("minimize_to_tray_enabled", minimize_to_tray_enabled, resolved)


def load_run_as_admin_enabled(path: Path | str | None = None) -> bool:
    """Default False -- opt-in (RELAY 035). Sticky: run_shell.main() checks
    this on every normal start (not just the moment the toggle is flipped)
    and relaunches itself elevated if it's True and the current process
    isn't already elevated."""
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    return bool(data.get("run_as_admin_enabled", False))


def save_run_as_admin_enabled(run_as_admin_enabled: bool, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("run_as_admin_enabled", run_as_admin_enabled, resolved)


def load_custom_palette(path: Path | str | None = None) -> Optional[dict]:
    """None means "nothing saved yet" -- the caller (app.js's loadPalette)
    falls back to THEME_PRESETS[0] itself, same "None means use the
    default, caller resolves it" shape as load_mod_repo_path. Real bug fix
    (RELAY 038): before this, the palette never persisted at all -- app.js
    hardcoded THEME_PRESETS[0] on every load with no save/load call
    anywhere, so any custom color edit silently vanished on the next
    restart."""
    resolved = Path(path) if path is not None else default_settings_path()
    data = _load_all(resolved)
    value = data.get("custom_palette")
    return dict(value) if value else None


def save_custom_palette(custom_palette: dict, path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_settings_path()
    _save_one("custom_palette", dict(custom_palette), resolved)
