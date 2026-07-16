"""Maps raw gw1_launch pipeline log lines to short, user-facing status text
(classify_progress_message) and to a color category for the raw console line
(classify_progress_category, RELAY 030) -- two different consumers of the
same on_log(message) callback, so both live here rather than each front-end
carrying its own copy.

Shared by both front-ends: the imgui launcher (launcher.py's LaunchSession) and
the pywebview shell (pywebview_shell/bridge.py's per-card launch status and
console). Lives here in launcher_core so all consumers stay in sync from one
source. Pure string mapping, no dependencies.

The needles are substrings of the exact _log() messages gw1_launch.py emits
(plus bridge.py's own [Bulk Launch] lines for classify_progress_category);
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


# RELAY 030: category for the RAW console line (a different consumer of the
# same on_log(message) callback than classify_progress_message above -- the
# console shows raw pipeline text verbatim, not the friendly per-card
# status). Categories match the mockup's own real colorMap
# (Launcher.dc.html) exactly: '' (neutral/muted), 'ok' (green), 'warn'
# (amber), 'acc' (blue), 'err' (red) -- reused as literal CSS class suffixes
# by app.js, no separate name mapping needed.
#
# Order matters here too, same reason as above, plus one extra wrinkle:
# several genuinely-failed-sounding messages are deliberately softened to
# 'warn' because gw1_launch.py's own text already frames them as non-fatal
# ("best-effort, continuing", "cosmetic, not a launch failure") or as a
# normal step in the update-relaunch flow ("no longer running"/"no longer
# exists" during the updater-exit-then-relaunch path, not a crash) -- these
# softening needles are checked before the broad "failed" catch-all so they
# don't get swept into 'err'.
_CATEGORY_PATTERNS: list[tuple[str, str]] = [
    # Softened / non-fatal, checked before the generic "failed" bucket below.
    ("best-effort, continuing", "warn"),
    ("cosmetic", "warn"),
    ("no longer running", "warn"),
    ("no longer exists", "warn"),
    ("but reports hung", "warn"),
    ("falling back to manual login", "warn"),
    # App Settings / per-profile "launching without it" heads-ups.
    ("disabled (App Settings)", "warn"),
    ("disabled for this profile", "warn"),
    # bridge.py's own [Bulk Launch] lines (never go through gw1_launch.py's
    # _log(), built directly in _run_bulk_launch -- see that module).
    ("Skipping ", "warn"),
    ("Bulk launch cancelled", "warn"),
    ("Launching next account", "acc"),
    ("Waiting for account to be ready", "acc"),
    # Window title's own "attempting" line must be checked before the plain
    # "set to" success needle below, since "attempting to set to" contains
    # "set to" as a literal substring.
    ("Window title - attempting to set to", "acc"),
    # Real failures.
    ("has been hung for", "err"),
    ("Timed out waiting", "err"),
    ("Hit the absolute ceiling", "err"),
    ("invalid DLL path", "err"),
    ("is not STILL_ACTIVE", "err"),
    ("aborting", "err"),
    ("could not open process", "err"),
    ("Failed to resume thread", "err"),  # capitalized -- doesn't match the lowercase "failed" catch-all below
    ("failed", "err"),
    # Success.
    ("patched at address", "ok"),
    ("window(s) for PID", "ok"),
    ("recovered from hung state", "ok"),
    ("Window title - set to", "ok"),
    ("splash window transitioned", "ok"),
    ("Found follow-up process", "ok"),
    ("GW1 registry fix applied", "ok"),
    ("arguments added", "ok"),
    ("Process resumed", "ok"),
    ("injection reported success", "ok"),
    # Informational / in-progress.
    ("starting injection of", "acc"),
    ("injection thread exit code", "acc"),
    ("Waiting for GW window", "acc"),
    ("Waiting for a window or process exit", "acc"),
    ("Scanning for the follow-up process", "acc"),
    ("folder ready; injecting", "acc"),
    ("Window found; waiting", "acc"),
    ("Launching", "acc"),  # broad catch-all: "Launching (suspended): ..." / "Launching {name}..."
]


def classify_progress_category(raw_message: str) -> str:
    for needle, category in _CATEGORY_PATTERNS:
        if needle in raw_message:
            return category
    return ""
