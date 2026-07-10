"""Config/.ini seeding for the Py4GW_Reforged game-mod repo: files the mod
needs to run, seeded from default templates bundled with this launcher.
Independent of the prereqs module (this is about config *files*, not
software installs).

For a file that doesn't exist yet at the target location, seed it directly
from this launcher's own bundled default. For a file that already exists,
a hash of whatever content it was last seeded from is tracked; on a later
seed pass, the file is only overwritten if its current content still
matches that tracked hash (meaning the user never touched it since) --
otherwise it's left alone entirely. A ``.new`` sibling file is written next
to it instead (cheap to add, gives the user something to diff/merge
manually) rather than either silently dropping the update or silently
doing nothing.

Where the target location lives is deliberately the simplest honest answer
for today's actual deployment shape, not a general "find the Py4GW_Reforged
install" mechanism -- the project's own docs (Feature & Parity Tracker,
TODO.md) explicitly flag that broader problem (does the mod repo exist
locally at all, where, is it up to date) as a separate, still-unresolved
question (a repo clone/setup wizard), deliberately out of scope here.
Today, this launcher and the mod's files are the same checkout (the
launcher lives in a subfolder one level below the mod's own files), so the
target is simply this launcher's own parent directory. This assumption will
need revisiting once that broader install-location question is resolved.

Explicitly NOT handled here (deferred, matching the task that requested
this): the app's expected file structure changing in a breaking way between
versions. If a future default template adds/removes/restructures sections
in a way an old seeded file can't safely absorb, that's a case-by-case
migration problem for whoever ships that change, not something this module
tries to detect or automate.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Optional

# _LAUNCHER_DIR is deliberately still __file__-based, even though _mod_root()
# below can't be: this is used for _DEFAULTS_DIR, finding this launcher's own
# *bundled* config_defaults/ data, which under a packaged exe is a PyInstaller
# `datas` entry PyInstaller genuinely does extract to disk next to this
# module inside its temp extraction directory -- __file__-relative resolution
# is exactly correct for that. _mod_root() is a different question entirely
# (where's the real, user-facing mod checkout on disk), which is why it needs
# its own, different resolution below rather than reusing this constant.
_LAUNCHER_DIR = Path(__file__).resolve().parent.parent
_DEFAULTS_DIR = _LAUNCHER_DIR / "config_defaults"

APPDATA_SUBDIR = "Py4GW_Reforged_Launcher"
HASH_STORE_FILENAME = "seeded_config_hashes.json"

# Add more filenames here if this ever grows past just Py4GW.ini -- each one
# needs a matching bundled default at config_defaults/{filename}.
SEEDED_CONFIG_FILENAMES = ["Py4GW.ini"]

# How many directories up from the exe (inclusive of the exe's own directory,
# depth 0) _mod_root() will check for a real checkout marker before giving up
# and falling back to the fixed-depth guess -- see _mod_root()'s own
# docstring for why a fixed depth alone isn't enough.
_FROZEN_MOD_ROOT_SEARCH_DEPTH = 4


def _mod_root() -> Path:
    """Today's mod root: this launcher's own parent directory -- see this
    module's docstring for why that's the deliberately simple answer for
    now, not a general install-location discovery mechanism.

    Under a packaged (PyInstaller) exe, __file__-based resolution -- correct
    when running from source -- breaks: this module is bundled pure Python,
    so __file__ resolves relative to PyInstaller's temp extraction directory
    (_MEIxxxxxx), not to wherever the real .exe actually sits on disk.
    Confirmed directly against the real built exe (not assumed): running it
    and inspecting _mod_root()'s result showed a path under
    %TEMP%\\_MEIxxxxxx, not the exe's real folder. sys.executable is the
    correct place to start once frozen -- it always points at the real .exe,
    regardless of where pure-Python modules got unpacked to run it.

    A first fix here just assumed "two parents up from sys.executable" (this
    launcher's own dir, then its parent) -- confirmed wrong on real hardware:
    that only holds if the exe is deployed nested inside a
    Py4GW_Reforged_Launcher subfolder of the mod root, but a real laptop had
    the exe sitting directly inside the mod root itself, one level
    shallower, which made the fixed guess resolve one level too high and
    report "no checkout found" despite a real, valid checkout being right
    there. Instead, walk up from the exe's own directory checking each level
    for the same Py4GWCoreLib/ marker mod_repo.py's own detection already
    uses, and use the first level that actually has it -- covers both real,
    confirmed layouts (exe directly in the mod root, and exe nested one
    level down in its own subfolder) without guessing a single fixed depth.
    Only falls back to the old fixed-depth guess if nothing matches within
    that range -- still a reasonable best-effort default for a genuinely
    fresh machine with no checkout yet to find. Doesn't change the existing
    manual override at all (App Settings' Browse button already lets a user
    correct a wrong guess) -- this only improves the unassisted default.
    """
    if getattr(sys, "frozen", False):
        from launcher_core.mod_repo import MOD_REPO_MARKER_DIR

        exe_dir = Path(sys.executable).resolve().parent
        candidate = exe_dir
        for _ in range(_FROZEN_MOD_ROOT_SEARCH_DEPTH):
            if (candidate / MOD_REPO_MARKER_DIR).is_dir():
                return candidate
            candidate = candidate.parent
        return exe_dir.parent
    return _LAUNCHER_DIR.parent


def default_hash_store_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("%APPDATA% is not set -- expected on Windows")
    return Path(appdata) / APPDATA_SUBDIR / HASH_STORE_FILENAME


def _sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_hash_store(store_path: Path) -> dict:
    if not store_path.exists():
        return {}
    try:
        return json.loads(store_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_hash_store(store_path: Path, data: dict) -> None:
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@dataclasses.dataclass
class SeedResult:
    filename: str
    action: str  # "seeded" | "updated" | "up_to_date" | "skipped_user_modified" | "error"
    detail: str = ""


def seed_default_configs(
    *, hash_store_path: Optional[Path] = None, mod_root: Optional[Path] = None
) -> list[SeedResult]:
    """Runs the seed-if-missing / update-if-untouched / leave-alone-
    otherwise logic described in this module's docstring for every filename
    in SEEDED_CONFIG_FILENAMES. Safe to call on every launch -- each branch
    is a handful of file reads/a hash compare, no different in cost from the
    prereq checks elsewhere in this app.
    """
    store_path = hash_store_path if hash_store_path is not None else default_hash_store_path()
    target_root = mod_root if mod_root is not None else _mod_root()
    hash_store = _load_hash_store(store_path)
    results: list[SeedResult] = []

    for filename in SEEDED_CONFIG_FILENAMES:
        default_path = _DEFAULTS_DIR / filename
        target_path = target_root / filename

        if not default_path.exists():
            results.append(SeedResult(filename, "error", f"No bundled default found at {default_path}"))
            continue

        default_bytes = default_path.read_bytes()
        default_hash = hashlib.sha256(default_bytes).hexdigest()

        if not target_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(default_bytes)
            hash_store[filename] = default_hash
            results.append(SeedResult(filename, "seeded", f"Created {target_path} from the bundled default."))
            continue

        current_hash = _sha256_of_file(target_path)
        last_seeded_hash = hash_store.get(filename)

        if current_hash == default_hash:
            # Already matches the current default's content exactly.
            hash_store[filename] = default_hash
            results.append(SeedResult(filename, "up_to_date", "Already matches the current default."))
        elif last_seeded_hash is not None and current_hash == last_seeded_hash:
            # Untouched since the last time this launcher wrote it, and the
            # bundled default has since moved on -- safe to bring forward.
            target_path.write_bytes(default_bytes)
            hash_store[filename] = default_hash
            results.append(SeedResult(filename, "updated", f"Refreshed {target_path} (untouched since last seed)."))
        else:
            # Either genuinely user-modified, or there's no record of ever
            # seeding this file (a pre-existing file from before this
            # feature existed) -- in both cases, leave the real file alone.
            # Drop a .new sibling with the current default if one doesn't
            # already match, so the user has something to diff/merge
            # manually instead of the update being silently dropped.
            new_path = target_path.with_name(target_path.name + ".new")
            existing_new_hash = _sha256_of_file(new_path) if new_path.exists() else None
            if existing_new_hash != default_hash:
                new_path.write_bytes(default_bytes)
            results.append(
                SeedResult(filename, "skipped_user_modified", f"Left {target_path} as-is; see {new_path.name}.")
            )

    _save_hash_store(store_path, hash_store)
    return results
