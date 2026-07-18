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


def _looks_like_legacy_accounts(data: object) -> bool:
    """RELAY 060: cheap structural check -- Apo's own screenshot surfaced a
    real gap, picking the wrong import button (native roster restore
    instead of this one) on a file that doesn't match this format
    silently returned a 0/0 result with no explanation. Doesn't validate
    every field, just enough to distinguish "this is plausibly a legacy
    accounts.json" from "this is some other JSON file" -- a foreign or
    hand-edited file that happens to satisfy this shape still goes
    through the real per-field parsing above, which is the actual
    source of truth."""
    if not isinstance(data, dict) or not data:
        return False
    # This app's own native roster bundle (roster_transfer.export_roster)
    # uses exactly these two reserved top-level keys -- an empty bundle
    # ({"profiles": [], "teams": []}) would otherwise trivially pass the
    # per-account loop below (nothing inside an empty list to fail on),
    # a real false negative confirmed via a live test with Apo's own
    # cross-wired-file scenario in reverse.
    if set(data.keys()) >= {"profiles", "teams"}:
        return False
    for accounts in data.values():
        if not isinstance(accounts, list):
            return False
        for account in accounts:
            if not isinstance(account, dict):
                return False
            if "character_name" not in account and "gw_path" not in account:
                return False
    return True


def parse_legacy_accounts(path: Path | str) -> tuple[list[GameProfile], list[Team], list[str]]:
    """Parse an old-launcher accounts.json into (profiles, teams, warnings).

    One Team per unique top-level key; every account under a key gets that team's id
    in its team_ids. Warnings are human-readable lines (including the profile name)
    for old-launcher settings that have no equivalent here and are intentionally not
    imported -- returned, not raised, so the caller can surface them.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not _looks_like_legacy_accounts(data):
        raise ValueError(
            "This doesn't look like a legacy accounts.json from the old launcher "
            "(expected team names mapping to lists of accounts)."
        )

    profiles: list[GameProfile] = []
    teams: list[Team] = []
    warnings: list[str] = []

    for team_name, accounts in data.items():
        if not isinstance(accounts, list):
            continue
        team = Team(name=team_name)
        teams.append(team)

        for account in accounts:
            # RELAY 060: character_name is the real, always-populated identity
            # field (the old launcher's own account-list display label,
            # Py4GW_Launcher.py lines 1218/1271/1595) -- gw_client_name is a
            # separate, optional, cosmetic field ("Rename GW Client") that's
            # confirmed dead code in the real source (only ever written, never
            # read for any actual behavior -- grepped every use) and on a real
            # multi-account roster is essentially guaranteed blank. Using it
            # for profile.name produced the "(unnamed)" wall Apo hit on his
            # real 60-account import.
            character_name = account.get("character_name", "")
            email = account.get("email", "")
            password = account.get("password", "")

            profile = GameProfile()
            profile.name = character_name
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
            profile.script_path = account.get("script_path", "")
            profile.team_ids = [team.id]
            profiles.append(profile)

            label = character_name or "(unnamed profile)"
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
            # above from fields that don't exist in this format). RELAY 060:
            # a missing-DLL-path warning is NOT generated here anymore --
            # bridge.py's import_legacy_accounts now tries a real auto-default
            # (glob for the DLL under the resolved mod root) before deciding
            # whether a warning is actually still warranted, and this module
            # has no access to that resolution (mod-repo path is a bridge.py/
            # settings_store concern). Generating the warning here, before
            # that auto-default even runs, would produce a stale "must be set
            # manually" message on a profile that ends up auto-filled anyway.
            # Silently dropped (no warning): runtime stats (last_launch_time,
            # *_runtime, current_session_time), window geometry (top_left, width,
            # height), preview_area, resize_client, launch_selected,
            # launcher_account_uid, gwtoolbox_path. Also gw_client_name/
            # enable_client_rename/use_character_name/custom_client_name
            # (RELAY 060) -- confirmed dead code in the real old-launcher
            # source (the only consumer is wrapped in a triple-quoted,
            # never-executed block), so there's no real behavior lost and no
            # warning is warranted, unlike the genuinely-dropped features
            # above.

    return profiles, teams, warnings
