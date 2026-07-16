"""Maps raw gw1_launch pipeline log lines to short, user-facing status text.

Shared by both front-ends: the imgui launcher (launcher.py's LaunchSession) and
the pywebview shell (pywebview_shell/bridge.py's per-card launch status). Lives
here in launcher_core so the two stay in sync from one source rather than each
carrying its own copy. Pure string mapping, no dependencies.

The needles are substrings of the exact _log() messages gw1_launch.py emits;
order matters (first match wins), so more specific lines come before the
generic ones they'd otherwise also match.
"""
from __future__ import annotations

_PROGRESS_PATTERNS: list[tuple[str, str]] = [
    ("but reports hung", "Waiting for game update..."),
    ("recovered from hung state", "Update finished, resuming..."),
    ("has been hung for", "Game appears frozen..."),
    ("Hit the absolute ceiling", "Still waiting..."),
    ("is no longer running", "Handling game update (relaunching)..."),
    ("no longer exists", "Handling game update (relaunching)..."),
    ("Scanning for the follow-up process", "Waiting for the game to relaunch..."),
    ("Found follow-up process", "Game relaunched, resuming..."),
    ("Timed out waiting for a follow-up process", "Still waiting for the game to relaunch..."),
    ("Multiclient patch on the follow-up process failed", "Resuming after relaunch..."),
    ("Multiclient patch - patched", "Applying compatibility patch..."),
    ("Launching (suspended)", "Launching..."),
    ("Process resumed", "Starting..."),
    ("Waiting for a window or process exit", "Waiting for the game window..."),
    ("Waiting for GW window", "Waiting for the game window..."),
    (", responsive", "Game window ready..."),
    ("window(s) for PID", "Game window ready..."),
    ("Window found; waiting", "Preparing to inject Py4GW..."),
    ("Timed out waiting for a window", "Still waiting for the game window..."),
    ("starting injection of", "Injecting Py4GW..."),
    ("injection thread exit code", "Verifying injection..."),
    ("injection reported success", "Injected!"),
]


def classify_progress_message(raw_message: str) -> str:
    for needle, friendly in _PROGRESS_PATTERNS:
        if needle in raw_message:
            return friendly
    return "Working..."
