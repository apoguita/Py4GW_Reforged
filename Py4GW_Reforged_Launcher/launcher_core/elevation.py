"""Global "run as administrator" toggle (RELAY 035) -- elevates the
LAUNCHER's own process, not each individual GW1 launch. gw1_launch.py's
CreateProcessW(CREATE_SUSPENDED, ...) call passes no explicit token/security
attributes, so a child process it spawns inherits whatever token the
launcher process itself is running under -- if the launcher is elevated,
every profile launched from it is elevated too, with zero changes needed in
gw1_launch.py. Elevating the individual Gw.exe launch instead (via
ShellExecuteEx's own "runas" verb) would run it through a separate elevated
broker process that doesn't expose CreateProcessW's low-level creation-flags
control the suspended-injection technique depends on -- a real,
likely-incompatible fight against the existing pipeline, not a small change.
"""
from __future__ import annotations

import ctypes
import subprocess
import sys

import pywintypes
import win32con
from win32com.shell import shell, shellcon


def is_elevated() -> bool:
    """Whether the CURRENT process token is elevated -- not merely whether
    the logged-in user is an administrator (a non-elevated process run by an
    admin user still correctly reports False here)."""
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def relaunch_elevated() -> None:
    """Starts a second copy of this same launcher with a real UAC consent
    prompt (lpVerb="runas") and blocks until the OS either creates that
    elevated process or the user declines the prompt. Raises OSError on
    failure/decline (wrapping the real pywintypes.error -- e.g. winerror 1223
    ERROR_CANCELLED) rather than returning a bool, so a caller can't
    accidentally treat a declined prompt as success.

    Deliberately does NOT touch the calling process (no sys.exit, no window
    teardown) -- callers decide when it's safe to exit, since a
    bridge-triggered relaunch needs its window closed cleanly by the normal
    close path, not torn down mid-call.
    """
    if getattr(sys, "frozen", False):
        # Packaged (PyInstaller) build -- sys.executable IS the real .exe,
        # same real-hardware-confirmed pattern config_seeding._mod_root()
        # already uses for this exact frozen/dev split.
        exe = sys.executable
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        # Dev run. sys.argv[0] resolves to run_shell.py's own file path when
        # launched via `python -m pywebview_shell.run_shell` (not the literal
        # "-m ..." text) -- relaunching THAT path directly would put
        # pywebview_shell/ on sys.path instead of the project root, breaking
        # `from pywebview_shell...` imports. Reconstructing the documented
        # `-m` invocation (this module's own docstring: "Run directly:
        # .venv\\Scripts\\python.exe -m pywebview_shell.run_shell") avoids
        # that rather than trusting sys.argv[0].
        exe = sys.executable
        params = "-m pywebview_shell.run_shell"

    try:
        shell.ShellExecuteEx(
            fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
            lpVerb="runas",
            lpFile=exe,
            lpParameters=params,
            nShow=win32con.SW_SHOWNORMAL,
        )
    except pywintypes.error as e:
        raise OSError(f"Elevation request failed or was declined: {e}") from e
