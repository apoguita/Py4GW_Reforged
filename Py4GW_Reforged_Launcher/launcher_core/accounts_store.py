"""RELAY 066: owns `Settings/Py4GW_Reforged_Launcher/accounts.json` -- the
single, permanent data store for this app's profiles and teams, replacing
profile_store.py's `%APPDATA%\\...\\profiles.json`/`teams.json` entirely.

Real context (agreed live with Apo on Discord, see dev_notes/RELAY.md 066):
this launcher is becoming the only launcher, so there's no import/migration
step -- accounts.json itself is the permanent store, forever, with this
app's own fields added into it rather than copied elsewhere. Separately,
accounts.json was committed once in this repo's actual initial commit and
is still reachable from `remotes/upstream/main` with 8 real accounts'
plaintext credentials -- the reason this file now lives under `Settings/`
(covered by the existing `Settings/*/` gitignore rule, verified directly
via `git check-ignore`, zero new lines needed) rather than the mod repo
root, and the reason plaintext passwords are converted to a DPAPI blob
the moment this app ever sees them.

On-disk shape is UNCHANGED from the old standalone launcher's own format
(team name -> list of account dicts) -- "don't reinterpret" was Apo's own
explicit requirement, since other tools (Layout Manager.py) hard-read this
exact shape. A profile belonging to N teams gets N full copies of its
account dict, one per team-name key, kept identical since this app is now
the only writer (unlike the old launcher's uncoordinated hand-edits, which
is exactly what let copies drift and produced RELAY 060/061's "teams came
in empty" bug). Unknown/legacy fields this app doesn't model (gw_client_
name, enable_client_rename, run_as_admin, the old runtime-stat fields,
etc.) are preserved verbatim across a save, not stripped -- see
_EXTRA_FIELDS_CACHE below. The one deliberate exception is the plaintext
`password` key, which never survives a save once this app has touched the
account (see _account_from_dict).

A profile with zero team memberships (a very normal state -- e.g. right
after "+Add Profile" before assigning a team) has nowhere to live in a
format where team NAME is literally the only bucket a JSON object can sit
under. Real gap the entry text didn't address; resolved by writing such
profiles under one reserved key (_UNASSIGNED_TEAM_KEY) that's excluded
from the real team list load_teams() returns, so it never appears as a
selectable team in the UI -- just a storage bucket, matching the same
"ALL isn't a real team" pattern this app already uses elsewhere.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dulwich.errors import NotGitRepository
from dulwich.repo import Repo

from launcher_core import crypto, mod_root
from launcher_core.profile import GameProfile
from launcher_core.team import Team

# Reserved storage bucket for profiles with no team membership -- never
# returned by load_teams() as a real, selectable team. Deliberately not a
# name any real user would plausibly type for an actual team.
_UNASSIGNED_TEAM_KEY = "__py4gw_reforged_launcher_unassigned__"

# Unknown/legacy fields this app doesn't model, keyed by profile.id, so a
# save can write them back unchanged instead of silently dropping them.
# Module-level and never persisted separately -- this app is a single,
# long-running process and the only writer of the real file (Apo's own
# design requirement), so an in-memory cache populated on every load and
# consulted on every save is sufficient; nothing here needs to survive a
# process restart on its own (a fresh load repopulates it from disk).
_EXTRA_FIELDS_CACHE: dict[str, dict] = {}

SETTINGS_SUBDIR = "Settings"
LAUNCHER_SETTINGS_DIR = "Py4GW_Reforged_Launcher"
ACCOUNTS_FILENAME = "accounts.json"


def default_accounts_path() -> Path:
    """`<resolved mod repo root>/Settings/Py4GW_Reforged_Launcher/accounts.json`
    -- override-aware (mod_root.resolve_mod_repo_path(), not the bare
    _mod_root() default) so this file follows wherever the user's actual,
    currently-configured checkout is, matching Apo's "stays in the repo"
    requirement for whichever repo that actually is.
    """
    return mod_root.resolve_mod_repo_path() / SETTINGS_SUBDIR / LAUNCHER_SETTINGS_DIR / ACCOUNTS_FILENAME


def _account_from_dict(raw: dict) -> tuple[GameProfile, dict]:
    """One account dict -> (GameProfile, preserved-extras dict). `extras`
    starts as a full copy of `raw` and has every field this app owns
    popped out of it, so whatever's left is exactly the unknown/legacy
    content to preserve verbatim on the next save.
    """
    extras = dict(raw)

    character_name = extras.pop("character_name", "") or ""
    email = extras.pop("email", "") or ""
    gw_path = extras.pop("gw_path", "") or ""
    extra_args = extras.pop("extra_args", "") or ""
    inject_py4gw = extras.pop("inject_py4gw", False)
    inject_gmod = extras.pop("inject_gmod", False)
    gmod_mods = extras.pop("gmod_mods", []) or []
    script_path = extras.pop("script_path", "") or ""

    # New-format fields this app owns -- already present if a prior save by
    # this app wrote them, absent on a first-ever load of the old format.
    profile_id = extras.pop("id", None)
    name = extras.pop("name", None)
    py4gw_dll_path = extras.pop("py4gw_dll_path", "") or ""
    gmod_dll_path = extras.pop("gmod_dll_path", "") or ""
    auto_login_enabled = extras.pop("auto_login_enabled", None)
    auto_select_character_enabled = extras.pop("auto_select_character_enabled", None)
    windowed_mode_enabled = extras.pop("windowed_mode_enabled", True)
    window_x = extras.pop("window_x", 0)
    window_y = extras.pop("window_y", 0)
    window_width = extras.pop("window_width", 800)
    window_height = extras.pop("window_height", 600)
    window_maximized = extras.pop("window_maximized", False)
    window_remember_changes = extras.pop("window_remember_changes", False)
    window_lock_changes = extras.pop("window_lock_changes", False)
    window_block_inputs = extras.pop("window_block_inputs", False)
    bulk_launch_enabled = extras.pop("bulk_launch_enabled", False)

    # RELAY 066 item 6: encrypt on first touch. A real plaintext `password`
    # value always wins over whatever password_protected already exists --
    # its presence means either the original, never-before-touched old
    # file, or a hand-pasted new value -- and is NEVER carried into extras
    # (popped above), so it can't round-trip back out as plaintext.
    plaintext_password = extras.pop("password", None)
    password_protected = extras.pop("password_protected", "") or ""
    if plaintext_password:
        password_protected = crypto.protect_password(plaintext_password)

    if auto_login_enabled is None:
        # Old format has no such toggle -- the old launcher always
        # attempted auto-login whenever real credentials existed. Same
        # inference RELAY 060's legacy_import.py already established.
        auto_login_enabled = bool(email) and bool(password_protected)
    if auto_select_character_enabled is None:
        auto_select_character_enabled = bool(character_name)

    kwargs: dict[str, Any] = dict(
        name=name if name is not None else character_name,
        character_name=character_name,
        email=email,
        executable_path=gw_path,
        launch_arguments=extra_args,
        py4gw_enabled=bool(inject_py4gw),
        py4gw_dll_path=py4gw_dll_path,
        gmod_enabled=bool(inject_gmod),
        gmod_dll_path=gmod_dll_path,
        gmod_plugin_paths=list(gmod_mods),
        script_path=script_path,
        auto_login_enabled=bool(auto_login_enabled),
        password_protected=password_protected,
        auto_select_character_enabled=bool(auto_select_character_enabled),
        windowed_mode_enabled=bool(windowed_mode_enabled),
        window_x=int(window_x),
        window_y=int(window_y),
        window_width=int(window_width),
        window_height=int(window_height),
        window_maximized=bool(window_maximized),
        window_remember_changes=bool(window_remember_changes),
        window_lock_changes=bool(window_lock_changes),
        window_block_inputs=bool(window_block_inputs),
        bulk_launch_enabled=bool(bulk_launch_enabled),
    )
    if profile_id:
        kwargs["id"] = profile_id

    profile = GameProfile(**kwargs)
    return profile, extras


def _dedup_keys(p: GameProfile) -> list[tuple]:
    """RELAY 061's own multi-key matching, reused here for the same reason:
    on a first-ever load of the old format (no `id` field written by this
    app yet), the same real account can appear under several team keys as
    separate dict copies with no shared identifier except its own content.
    The `id` key is always present too (every GameProfile has one, freshly
    generated if the file didn't provide it) -- once this app has saved the
    file at least once, ids are the primary, most reliable match; the
    content-based keys keep working for the very first load and for a
    hand-edited entry a user pastes in without an id.
    """
    keys: list[tuple] = [("id", p.id), ("exe_char", p.executable_path, p.character_name)]
    if p.email:
        keys.append(("email", p.email))
    return keys


def _parse_raw(raw: dict) -> tuple[list[GameProfile], list[Team]]:
    existing_by_key: dict[tuple, GameProfile] = {}
    ordered_profiles: list[GameProfile] = []
    teams: list[Team] = []

    if not isinstance(raw, dict):
        return [], []

    for team_name, accounts in raw.items():
        if not isinstance(accounts, list):
            continue
        is_real_team = team_name != _UNASSIGNED_TEAM_KEY
        if is_real_team:
            teams.append(Team(id=team_name, name=team_name))

        for account in accounts:
            if not isinstance(account, dict):
                continue
            profile, extras = _account_from_dict(account)
            keys = _dedup_keys(profile)

            existing = None
            for key in keys:
                existing = existing_by_key.get(key)
                if existing is not None:
                    break

            if existing is not None:
                if is_real_team and team_name not in existing.team_ids:
                    existing.team_ids.append(team_name)
                for key in keys:
                    existing_by_key[key] = existing
            else:
                profile.team_ids = [team_name] if is_real_team else []
                for key in keys:
                    existing_by_key[key] = profile
                ordered_profiles.append(profile)
                _EXTRA_FIELDS_CACHE[profile.id] = extras

    return ordered_profiles, teams


def _load_and_parse(path: Path) -> tuple[list[GameProfile], list[Team]]:
    if not path.exists():
        return [], []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _parse_raw(raw)


def _profile_to_dict(profile: GameProfile) -> dict:
    """The inverse of _account_from_dict: preserved extras as the base,
    every field this app owns refreshed on top from the live GameProfile.
    The plaintext `password` key is popped from the base extras too, in
    case a stale cache entry (from before this app first saved) somehow
    still carried one -- never written, ever, regardless of source.
    """
    extras = dict(_EXTRA_FIELDS_CACHE.get(profile.id, {}))
    extras.pop("password", None)

    extras.update(
        {
            "character_name": profile.character_name,
            "email": profile.email,
            "gw_path": profile.executable_path,
            "extra_args": profile.launch_arguments,
            "inject_py4gw": profile.py4gw_enabled,
            "inject_gmod": profile.gmod_enabled,
            "gmod_mods": list(profile.gmod_plugin_paths),
            "script_path": profile.script_path,
            "id": profile.id,
            "name": profile.name,
            "py4gw_dll_path": profile.py4gw_dll_path,
            "gmod_dll_path": profile.gmod_dll_path,
            "password_protected": profile.password_protected,
            "auto_login_enabled": profile.auto_login_enabled,
            "auto_select_character_enabled": profile.auto_select_character_enabled,
            "windowed_mode_enabled": profile.windowed_mode_enabled,
            "window_x": profile.window_x,
            "window_y": profile.window_y,
            "window_width": profile.window_width,
            "window_height": profile.window_height,
            "window_maximized": profile.window_maximized,
            "window_remember_changes": profile.window_remember_changes,
            "window_lock_changes": profile.window_lock_changes,
            "window_block_inputs": profile.window_block_inputs,
            "bulk_launch_enabled": profile.bulk_launch_enabled,
        }
    )
    return extras


def _write(profiles: list[GameProfile], teams: list[Team], path: Path) -> None:
    structure: dict[str, list[dict]] = {t.name: [] for t in teams}
    unassigned: list[dict] = []

    for profile in profiles:
        account_dict = _profile_to_dict(profile)
        member_teams = [tid for tid in profile.team_ids if tid in structure]
        if member_teams:
            for team_name in member_teams:
                structure[team_name].append(dict(account_dict))
        else:
            unassigned.append(account_dict)

    if unassigned:
        structure[_UNASSIGNED_TEAM_KEY] = unassigned

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(structure, indent=2), encoding="utf-8")


def _ensure_migrated(path: Path) -> None:
    """RELAY 066 item 2: one-time migration, idempotent. If `path` (the new
    canonical location) doesn't exist yet, but a root-level accounts.json
    does (the file's original, pre-066 location -- also where the old
    standalone launcher itself puts it), read it once and write it to
    `path`. The root file is NEVER written to or deleted -- untouched, it
    automatically stays the de facto backup, with zero extra code. Re-runs
    (does real work again) if `path` is later deleted, by design -- not a
    one-shot flag stored anywhere.
    """
    if path.exists():
        return
    root_file = mod_root.resolve_mod_repo_path() / ACCOUNTS_FILENAME
    if not root_file.is_file():
        return
    profiles, teams = _load_and_parse(root_file)
    _write(profiles, teams, path)


def load_profiles(path: Path | str | None = None) -> list[GameProfile]:
    resolved = Path(path) if path is not None else default_accounts_path()
    if path is None:
        _ensure_migrated(resolved)
    profiles, _teams = _load_and_parse(resolved)
    return profiles


def save_profiles(profiles: list[GameProfile], path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_accounts_path()
    teams = load_teams(resolved)  # preserve empty teams -- see module docstring
    _write(profiles, teams, resolved)


def load_teams(path: Path | str | None = None) -> list[Team]:
    resolved = Path(path) if path is not None else default_accounts_path()
    if path is None:
        _ensure_migrated(resolved)
    _profiles, teams = _load_and_parse(resolved)
    return teams


def save_teams(teams: list[Team], path: Path | str | None = None) -> None:
    resolved = Path(path) if path is not None else default_accounts_path()
    profiles = load_profiles(resolved)  # preserve account data
    _write(profiles, teams, resolved)


def save_accounts(profiles: list[GameProfile], teams: list[Team], path: Path | str | None = None) -> None:
    """Save BOTH profiles and teams together in one real write. Required
    (not just a convenience) whenever a caller has modified both in the
    same logical operation -- calling save_profiles() then save_teams()
    separately is NOT equivalent: each one independently re-reads the
    OTHER half fresh from disk to preserve it (see their own docstrings),
    so the second call's re-read can't see the first call's still-
    in-memory-only changes yet. Real bug self-caught during RELAY 066's
    own live verification: import_legacy_accounts adding a brand-new team
    AND a profile that belongs to it, saved via the old separate-calls
    pattern, silently dropped that profile into the unassigned bucket --
    save_profiles() ran first, its own internal load_teams() re-read
    hadn't seen the new team yet (that only got written by the SECOND
    call), so the new team wasn't a recognized key when profiles were
    written. This function writes both in the single call that already
    has both correct in memory, no re-read needed at all.
    """
    resolved = Path(path) if path is not None else default_accounts_path()
    _write(profiles, teams, resolved)


def is_accounts_file_tracked(path: Path | str | None = None) -> bool:
    """RELAY 066 item 7: real tripwire against a repeat of this repo's own
    past incident -- accounts.json was committed once in the initial
    commit and is still reachable from remotes/upstream/main with 8 real
    accounts' plaintext credentials. Checks whether the resolved
    accounts.json is tracked by git RIGHT NOW in whatever repository
    contains it, via dulwich (already a real dependency -- mod_repo.py's
    own precedent for not shelling out to a system `git` binary that
    isn't guaranteed to be on a real end user's PATH).

    Returns False -- not an error -- if there's no git repository here at
    all: a real end user might have downloaded a ZIP instead of cloning,
    which is a completely normal, safe case, not a warning-worthy one.
    Real end users are never expected to see this come back True, ever --
    it's a tripwire for the mistake happening again, not a normal-path
    check.
    """
    resolved = Path(path) if path is not None else default_accounts_path()
    try:
        repo = Repo.discover(str(resolved.parent))
    except NotGitRepository:
        return False
    try:
        repo_root = Path(repo.path).resolve()
        rel = resolved.resolve().relative_to(repo_root)
        key = str(rel).replace("\\", "/").encode("utf-8")
        return key in repo.open_index()
    except (ValueError, OSError):
        # relative_to raises ValueError if resolved somehow isn't under
        # repo_root at all (shouldn't happen -- discover() finds the repo
        # FROM resolved's own parent -- but fail closed, not with a crash).
        return False
    finally:
        repo.close()
