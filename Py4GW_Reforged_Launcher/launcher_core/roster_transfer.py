"""App-native roster export/import: profiles + teams as one JSON bundle.

Deliberately writes passwords in PLAINTEXT, under a differently-named field
(``password_plaintext``) than the stored DPAPI blob (``password_protected``).
Two reasons for plaintext rather than copying the encrypted blob: a DPAPI blob is
scoped to one Windows user account on one machine, so it's undecryptable after the
move this feature exists to enable; and the distinct field name keeps an export
bundle visually unmistakable from profiles.json at a glance. The plaintext is a
real secret at rest -- the UI warns before writing one (see launcher.py's export
confirm popup), and this module never writes an export except when asked to.

This is separate from profiles.json/teams.json (profile_store) on purpose: those
are the app's own storage, this is an interchange format that travels between
machines/users.
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

from launcher_core import crypto
from launcher_core.profile import GameProfile
from launcher_core.team import Team


@dataclasses.dataclass
class RosterImportResult:
    added_profiles: int = 0
    added_teams: int = 0
    skipped_profiles: int = 0
    skipped_teams: int = 0
    path_warnings: list[str] = dataclasses.field(default_factory=list)
    # Non-path import notes (e.g. old-launcher settings that couldn't be carried
    # over). Empty for the native roster import; populated by the legacy import.
    warnings: list[str] = dataclasses.field(default_factory=list)


def export_roster(
    profiles: list[GameProfile], teams: list[Team], path: Path | str, *, include_passwords: bool = True
) -> None:
    """Write ``{"profiles": [...], "teams": [...]}`` as pretty JSON. The stored DPAPI
    ``password_protected`` blob is always dropped (it wouldn't decrypt after the
    move). When ``include_passwords`` is True each profile instead carries a decrypted
    ``password_plaintext``; when False that field is omitted entirely -- not written as
    "" -- so the bundle has no password data at all. ``include_passwords`` is a
    parameter, not UI state, so the function stays testable on its own.
    """
    profile_dicts = []
    for profile in profiles:
        data = profile.to_dict()
        protected = data.pop("password_protected", "")
        if include_passwords:
            # Mirror crypto.unprotect_password's own empty-string short-circuit --
            # don't hand DPAPI an empty blob, just carry an empty plaintext through.
            data["password_plaintext"] = crypto.unprotect_password(protected) if protected.strip() else ""
        profile_dicts.append(data)

    bundle = {"profiles": profile_dicts, "teams": [team.to_dict() for team in teams]}
    Path(path).write_text(json.dumps(bundle, indent=2), encoding="utf-8")


def import_roster(path: Path | str) -> tuple[list[GameProfile], list[Team]]:
    """Reverse of export_roster: re-encrypt each ``password_plaintext`` back into a
    ``password_protected`` DPAPI blob for this Windows user, then rebuild models."""
    bundle = json.loads(Path(path).read_text(encoding="utf-8"))

    profiles = []
    for entry in bundle.get("profiles", []):
        data = dict(entry)  # don't mutate the parsed structure
        plaintext = data.pop("password_plaintext", "")
        if plaintext:
            data["password_protected"] = crypto.protect_password(plaintext)
        profiles.append(GameProfile.from_dict(data))

    teams = [Team.from_dict(entry) for entry in bundle.get("teams", [])]
    return profiles, teams


def find_missing_paths(profiles: list[GameProfile]) -> list[str]:
    """Human-readable warning lines for any referenced file path that doesn't exist
    on this machine -- executable_path always, py4gw_dll_path only when Py4GW is
    enabled, and each gmod_plugin_paths entry only when gMod is enabled. Empty/unset
    fields aren't a problem and are skipped."""
    warnings = []
    for profile in profiles:
        label = profile.name or "(unnamed profile)"
        if profile.executable_path and not os.path.exists(profile.executable_path):
            warnings.append(f"{label}: executable_path not found: {profile.executable_path}")
        if profile.py4gw_enabled and profile.py4gw_dll_path and not os.path.exists(profile.py4gw_dll_path):
            warnings.append(f"{label}: py4gw_dll_path not found: {profile.py4gw_dll_path}")
        if profile.gmod_enabled:
            for plugin_path in profile.gmod_plugin_paths:
                if plugin_path and not os.path.exists(plugin_path):
                    warnings.append(f"{label}: gmod_plugin_paths not found: {plugin_path}")
    return warnings
