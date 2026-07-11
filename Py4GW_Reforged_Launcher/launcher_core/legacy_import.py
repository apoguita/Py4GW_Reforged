"""Import the OLD Py4GW_Launcher.py accounts.json format.

A third, separate interchange format -- distinct from GWxLauncher's own profiles
and from this app's native roster_transfer export/import. The field mapping below is
derived from the old launcher's actual source (Py4GW_Launcher.py's Account class and
its launch code), NOT from the JSON shape alone -- see the per-field notes for where
the source disagrees with what the JSON looks like it means.

Top-level JSON keys are team names; each holds a list of account dicts.
"""

from __future__ import annotations

import json
from pathlib import Path

from launcher_core import crypto
from launcher_core.profile import GameProfile
from launcher_core.team import Team


def count_accounts(path: Path | str) -> int:
    """Total account count across all teams in an old-launcher accounts.json --
    for the first-run "Import N accounts?" prompt, without a full parse."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return sum(len(accounts) for accounts in data.values() if isinstance(accounts, list))


def parse_legacy_accounts(path: Path | str) -> tuple[list[GameProfile], list[Team], list[str]]:
    """Parse an old-launcher accounts.json into (profiles, teams, warnings).

    One Team per unique top-level key; every account under a key gets that team's id
    in its team_ids. Warnings are human-readable lines (including the profile name)
    for old-launcher settings that have no equivalent here and are intentionally not
    imported -- returned, not raised, so the caller can surface them.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    profiles: list[GameProfile] = []
    teams: list[Team] = []
    warnings: list[str] = []

    for team_name, accounts in data.items():
        if not isinstance(accounts, list):
            continue
        team = Team(name=team_name)
        teams.append(team)

        for account in accounts:
            name = account.get("gw_client_name", "")
            character_name = account.get("character_name", "")
            email = account.get("email", "")
            password = account.get("password", "")

            profile = GameProfile()
            profile.name = name
            profile.character_name = character_name
            profile.email = email
            # The old launcher has no auto-login toggle -- it always sends both when
            # they exist -- so infer the intent from real credentials being present.
            profile.auto_login_enabled = bool(email) and bool(password)
            # Mirrors the old launch code's own `if character:` gate (launch_and_patch),
            # NOT use_character_name (which only drives window-title text, unrelated
            # to login).
            profile.auto_select_character_enabled = bool(character_name)
            if password:
                profile.password_protected = crypto.protect_password(password)
            profile.executable_path = account.get("gw_path", "")
            profile.launch_arguments = account.get("extra_args", "")
            profile.py4gw_enabled = bool(account.get("inject_py4gw", False))
            profile.gmod_enabled = bool(account.get("inject_gmod", False))
            profile.gmod_plugin_paths = list(account.get("gmod_mods", []) or [])
            profile.team_ids = [team.id]
            profiles.append(profile)

            label = name or "(unnamed profile)"
            # GWToolbox++ is unsupported (see profile.py's docstring). Check BOTH keys:
            # older files (like this one) use inject_gwtoolbox, current upstream renamed
            # it to inject_blackbox -- reading only one would miss it or KeyError.
            if account.get("inject_blackbox") or account.get("inject_gwtoolbox"):
                warnings.append(
                    f"{label}: GWToolbox++ injection was enabled in the old launcher; "
                    "not supported, not imported."
                )
            if account.get("run_as_admin"):
                warnings.append(
                    f"{label}: 'Run as Admin' was enabled in the old launcher; not supported, not imported."
                )
            # The old accounts.json format never had a per-account DLL path field
            # for either injection type -- inject_py4gw/inject_gmod can come in
            # True with py4gw_dll_path/gmod_dll_path both staying empty (set
            # above from fields that don't exist in this format), which would
            # otherwise fail to inject with no explanation until someone
            # noticed in Settings.
            if profile.py4gw_enabled and not profile.py4gw_dll_path:
                warnings.append(
                    f"{label}: Py4GW injection was enabled in the old launcher; "
                    "the Py4GW DLL path must be set manually in Settings."
                )
            if profile.gmod_enabled and not profile.gmod_dll_path:
                warnings.append(
                    f"{label}: gMod injection was enabled in the old launcher; "
                    "the gMod DLL path must be set manually in Settings."
                )
            if account.get("script_path"):
                warnings.append(
                    f"{label}: an auto-run script ({account['script_path']}) was set in the old launcher; "
                    "not supported, not imported."
                )
            if (
                account.get("enable_client_rename")
                and not account.get("use_character_name")
                and account.get("custom_client_name")
            ):
                warnings.append(
                    f"{label}: a custom window title ('{account['custom_client_name']}') was set in the "
                    "old launcher; not carried over."
                )
            # Silently dropped (no warning): runtime stats (last_launch_time,
            # *_runtime, current_session_time), window geometry (top_left, width,
            # height), preview_area, resize_client, launch_selected,
            # launcher_account_uid, gwtoolbox_path.

    return profiles, teams, warnings
