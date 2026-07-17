"""Where's the real, user-facing Py4GW_Reforged mod checkout on disk -- the
shared assumption several other launcher_core modules (mod_repo, settings_store)
and pywebview_shell.bridge build their own defaults on top of.

Deliberately the simplest honest answer for today's actual deployment shape,
not a general "find the Py4GW_Reforged install" mechanism -- the project's own
docs (Feature & Parity Tracker, TODO.md) explicitly flag that broader problem
(does the mod repo exist locally at all, where, is it up to date) as a
separate, still-unresolved question (a repo clone/setup wizard), deliberately
out of scope here. Today, this launcher and the mod's files are the same
checkout (the launcher lives in a subfolder one level below the mod's own
files), so the target is simply this launcher's own parent directory. This
assumption will need revisiting once that broader install-location question
is resolved.

Formerly part of config_seeding.py (RELAY 053: that module also seeded a
bundled Py4GW.ini default into a fresh checkout -- removed, since it turned
out to serve only the old standalone Py4GW_Launcher.py, which this project
replaces, not this launcher or the current mod runtime; see RELAY.md 053 for
the full investigation). _mod_root() itself is still real, load-bearing logic
other modules depend on, so it survives that removal under its own name.
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAUNCHER_DIR = Path(__file__).resolve().parent.parent

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
