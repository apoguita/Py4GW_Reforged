"""Py4GW_Reforged_Launcher -- real, minimal working launcher window.

Wires the validated UI spike (spikes/spike_ui_multiviewport.py: card-grid main window
+ multi-viewport settings window) to the real profile data layer (launcher_core) and
the real GW1 launch pipeline (launcher_core.gw1_launch). Not a mockup: cards show real
profiles loaded from profile_store, clicking them drives the actual injection
pipeline, and status text reflects the pipeline's real, live progress.

Each card is the entire interaction surface -- no separate buttons per action:
left-click selects a stopped profile or brings a running one to the foreground,
double-click launches a stopped profile, and right-click opens Settings directly
for that profile (replacing an earlier "Settings" button whose behavior depended on
hidden selection state). The "+" card opens Settings for a new profile. Hovering
reveals a small action icon (play triangle / bring-to-front arrow) as a visual cue
only -- the whole card is already the click target, not just the icon. Settings
reuses one window/tab shell for both add and edit rather than a second, separate
form. Password field never displays the real stored value -- it's write-only: blank
means "don't change," typing a new value replaces the DPAPI blob on save.

Deliberately deferred (not built here):
- gMod's early-injection timing/strategy. GameProfile.gmod_enabled already exists on
  the data model and is editable, but nothing wires it to an actual injection call yet.
- Editing window-placement fields (window/x/y/width/height/etc.) -- shown read-only.
- Any config editing, or the broader Py4GW install/distribution mechanism (still
  unresolved with Apo -- see the handover doc). This file only checks whether *this
  launcher's own* runtime environment is sane enough to start; it doesn't install
  anything or manage the wider Py4GW dependency chain.

Run with the project's 32-bit venv, from this file's directory or with it importable:
    C:\\Users\\Chris\\Projects\\Py4GW\\myenv\\Scripts\\python.exe Py4GW_Reforged_Launcher\\launcher.py

Startup failure handling
-------------------------
Launch.bat runs this under pythonw.exe specifically to avoid a console flash --
which means an unhandled exception during startup (missing dependency, wrong
Python) would otherwise fail completely silently: no window, no console, no error,
nothing. That's the exact "confused user goes to Discord" failure mode this project
exists to prevent, so every import and prereq check that can plausibly fail on a
misconfigured machine is wrapped below and reported via a native MessageBoxW instead
-- ctypes is stdlib, so this works even if every third-party dependency is missing.
"""

from __future__ import annotations

import ctypes
import sys


def _fatal_startup_error(message: str) -> None:
    """Show a native Windows message box and exit. No ImGui, no third-party
    dependency -- ctypes.windll is stdlib, so this works even when the failure is
    that literally nothing else could be imported."""
    ctypes.windll.user32.MessageBoxW(0, message, "Py4GW_Reforged_Launcher — Startup Error", 0x10)
    sys.exit(1)


def _make_process_dpi_aware() -> None:
    """Declare Per-Monitor-v2 DPI awareness before imgui_bundle/SDL ever creates a
    window. This process had no DPI awareness declared anywhere (confirmed via
    ctypes.windll.shcore.GetProcessDpiAwareness() returning 0/Unaware by default) --
    without it, Windows doesn't just misreport the display scale to real DPI
    queries, it also bitmap-stretches the *entire already-rendered* window to match
    the real scale afterward. That produces clipped *and* oversized content at the
    same time regardless of any saved ini value, since the stretching happens after
    our own layout math runs, not inside it -- which is exactly the symptom seen on
    real hardware, and exactly what mocking hello_imgui.em_size() in earlier testing
    could never exercise (that only ever touched the ImGui-side font/content scale,
    never this OS-level awareness declaration). Must run before imgui_bundle is
    imported below, so it's called at module scope here, first thing.
    """
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4 (Windows 10 1703+)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2 (Windows 8.1+, no per-monitor-v2 support)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except (AttributeError, OSError):
        pass
    try:
        # Windows Vista/7 fallback: system-DPI-aware only.
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass


def _set_app_user_model_id() -> None:
    """Give this app its own taskbar identity instead of inheriting python.exe's.
    Without an explicit AppUserModelID, Windows groups/identifies a python.exe-
    launched app under the interpreter's own taskbar icon and grouping (a real,
    previously-identified bug here, not a hypothetical) -- setting this early,
    before the window is created, makes Explorer treat this as its own distinct
    app for taskbar icon/grouping purposes.
    """
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Py4GW.ReforgedLauncher")
    except (AttributeError, OSError):
        pass


_make_process_dpi_aware()
_set_app_user_model_id()


# 32-bit is a hard requirement, not a preference: imgui_bundle has no 64-bit wheel
# available for this project's venv (source-build only, see gw1_launch.py's docs),
# and the GW1 injection pipeline needs same-bitness with GW1's own 32-bit process
# for CreateRemoteThread to work at all. Checked directly rather than assumed --
# confirmed via `sys.maxsize` against the actual running interpreter, not a
# hardcoded expected Python version (which could go stale independent of this).
if sys.maxsize > 2**32:
    _fatal_startup_error(
        "This launcher requires 32-bit Python, but a 64-bit Python interpreter is "
        "running instead.\n\n"
        f"Detected: {sys.executable}\n"
        f"Python {sys.version.split()[0]} (64-bit)\n\n"
        "Use Launch.bat to start the launcher -- it points at the project's "
        "dedicated 32-bit virtual environment. If you're running this manually, "
        "use that same venv's python.exe/pythonw.exe instead of a system Python."
    )

try:
    import colorsys
    import dataclasses
    import math
    import os
    import threading
    import time
    import zlib
    from pathlib import Path
    from typing import Callable, Optional

    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from imgui_bundle import hello_imgui, imgui
    import psutil
    import pywintypes
    import win32con
    import win32gui

    from launcher_core import bulk_launch
    from launcher_core.crypto import protect_password
    from launcher_core.gw1_launch import LaunchResult, launch_py4gw_profile
    from launcher_core.profile import GameProfile
    from launcher_core.profile_store import load_profiles, load_teams, save_profiles, save_teams
    from launcher_core.settings_store import load_bulk_launch_pacing_seconds, save_bulk_launch_pacing_seconds
    from launcher_core.team import Team
    from launcher_core.window_control import (
        find_running_pid_for_exe_path,
        find_visible_window_for_pid,
        foreground_window,
        set_window_icon,
        set_window_title,
    )
except ImportError as e:
    _fatal_startup_error(
        "Py4GW_Reforged_Launcher failed to start: a required package is missing or "
        f"failed to load.\n\n{type(e).__name__}: {e}\n\n"
        f"Detected: {sys.executable}\n"
        f"Python {sys.version.split()[0]} (32-bit)\n\n"
        "This usually means the launcher isn't running under the project's "
        "dedicated Python virtual environment. Use Launch.bat to start it "
        "correctly, or if running manually, use:\n"
        "C:\\Users\\Chris\\Projects\\Py4GW\\myenv\\Scripts\\pythonw.exe"
    )
except Exception as e:
    _fatal_startup_error(
        "Py4GW_Reforged_Launcher failed to start unexpectedly.\n\n"
        f"{type(e).__name__}: {e}"
    )

# Window title format for a running client -- proposed, confirm it reads sensibly in
# the taskbar/Alt-Tab before treating this as final. Purely cosmetic: our own
# tracking is PID-based (see window_control.find_visible_window_for_pid) and never
# depends on this string.
WINDOW_TITLE_FORMAT = "Guild Wars Reforged — {profile_name}"

ICON_PATH = Path(__file__).resolve().parent / "assets" / "python_icon.ico"


def _apply_window_icon() -> None:
    """hello_imgui.RunnerParams exposes no window-icon option (checked directly --
    app_window_params has no icon field), so this is the fallback: find our own
    window by PID once the native window actually exists (callbacks.post_init
    fires "after everything is inited: ImGui, Platform and Renderer Backend") and
    apply the .ico via WM_SETICON. Best-effort -- a missing icon file or failed
    lookup isn't worth failing startup over.
    """
    hwnd = find_visible_window_for_pid(os.getpid())
    if hwnd is not None:
        set_window_icon(hwnd, str(ICON_PATH))


# -----------------------------------------------------------------------------
# Palette -- dark theme, real tokens from PY4GW_LAUNCHER_HANDOVER.md's "Real color
# values" table (Dark column), with hover/selected contrast pushed further per the
# handover's "UI/UX design authority" section (approved direction: hover = full
# neutral elevation step, selected = accent-tinted bg + accent border + solid bar).
# STATUS_* colors (amber/red) aren't part of that 4-state card spec -- they're new,
# needed to satisfy the "honest status text, not a spinner" requirement below.
# -----------------------------------------------------------------------------

def _u32(r: int, g: int, b: int, a: int = 255) -> int:
    return imgui.color_convert_float4_to_u32((r / 255.0, g / 255.0, b / 255.0, a / 255.0))


CARD_BACK = _u32(32, 32, 38)
CARD_SELECTED_BACK = _u32(28, 40, 58)
HOVER_BACK = _u32(48, 48, 56)
CARD_BORDER = _u32(55, 55, 65)
HOVER_BORDER = _u32(90, 90, 105)
ACCENT = _u32(0, 120, 215)
CARD_NAME_FORE = _u32(255, 255, 255)
CARD_SUB_FORE = _u32(170, 170, 185)
BADGE_BACK = _u32(50, 50, 65)
BADGE_BORDER = _u32(75, 75, 95)
BADGE_FORE = _u32(210, 210, 220)
STATUS_PROGRESS = _u32(230, 180, 80)
STATUS_ERROR = _u32(220, 90, 90)

# Avatar palette -- hues picked to avoid colliding with colors that already
# mean something specific: ACCENT's blue (~210 deg) means selection,
# STATUS_PROGRESS's amber (~35 deg) and STATUS_ERROR's red (~5 deg) mean
# status. Evenly spaced across the remaining hue range at a fixed saturation/
# lightness tuned to read well against the dark card background while still
# keeping a plain white letter legible on top of any of them.
_AVATAR_HUES_DEG = [60, 95, 130, 165, 245, 275, 300, 325]
_AVATAR_SATURATION = 0.55
_AVATAR_LIGHTNESS = 0.42


def _avatar_color_for_id(profile_id: str) -> int:
    """Deterministic color from the profile's id, not its name -- so renaming
    a profile doesn't shuffle its color and break the "that color is this
    account" muscle memory. Uses zlib.crc32 rather than the builtin hash():
    Python randomizes str hashing per-process by default, which would give a
    different color every time the app restarts.
    """
    index = zlib.crc32(profile_id.encode("utf-8")) % len(_AVATAR_HUES_DEG)
    hue = _AVATAR_HUES_DEG[index] / 360.0
    r, g, b = colorsys.hls_to_rgb(hue, _AVATAR_LIGHTNESS, _AVATAR_SATURATION)
    return _u32(round(r * 255), round(g * 255), round(b * 255))


def _card_dimensions() -> tuple[float, float, float]:
    """Card width/height/gap in real screen pixels, derived from the current font's
    em size (hello_imgui.em_size()) rather than hardcoded -- em_size already reflects
    whatever the actual DPI/font scale is at render time, so the grid scales instead
    of clipping or looking tiny on a different display. Ratios (16 / 5.6 / 0.8 em)
    are calibrated to reproduce the original approved 240/84/12px look exactly at
    the 15px default em size measured on the dev machine at 100% display scaling --
    not arbitrary, just expressed relative to font size instead of fixed pixels.
    Must be called during a frame (inside the ImGui callback), not at import time --
    em_size() needs a live ImGui context.
    """
    em = hello_imgui.em_size()
    return em * 16.0, em * 5.6, em * 0.8


# -----------------------------------------------------------------------------
# Live status classification: maps gw1_launch's raw log lines to short, honest
# progress text. This is the actual point of the earlier stall-detection work --
# specifically surfacing the "window found but hung" signal as "waiting for game
# update" instead of collapsing every wait state into one generic spinner. Ordered
# most-specific-substring-first since matching is just "is this substring present".
# -----------------------------------------------------------------------------

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


# -----------------------------------------------------------------------------
# LaunchSession: runs launch_py4gw_profile on a background thread (it blocks for
# the whole launch, seconds to tens of minutes during a large update) and exposes
# thread-safe, lock-protected status for the UI thread to poll every frame. Never
# call any ImGui function from the background thread -- only plain state updates.
# -----------------------------------------------------------------------------

class LaunchSession:
    def __init__(self, profile: GameProfile):
        self.profile = profile
        self._lock = threading.Lock()
        self._status_text = "Launching..."
        self._result: Optional[LaunchResult] = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _on_log(self, message: str) -> None:
        with self._lock:
            self._status_text = classify_progress_message(message)

    def _run(self) -> None:
        result = launch_py4gw_profile(self.profile, on_log=self._on_log)
        with self._lock:
            self._result = result

    @property
    def status_text(self) -> str:
        with self._lock:
            if self._result is not None:
                return "Injected" if self._result.success else f"Failed: {self._result.error}"
            return self._status_text

    @property
    def is_done(self) -> bool:
        with self._lock:
            return self._result is not None

    @property
    def result(self) -> Optional[LaunchResult]:
        with self._lock:
            return self._result


# -----------------------------------------------------------------------------
# BulkLaunchSession: launches a team's checked profiles one at a time on a
# background thread, applying launcher_core.bulk_launch's anti-bot pacing
# between each. Mirrors LaunchSession's thread-safe status/is_done pattern for
# the UI to poll every frame -- same rule applies: never call ImGui from here.
# -----------------------------------------------------------------------------

class BulkLaunchSession:
    def __init__(self, profiles: list[GameProfile], pacing_seconds: int):
        self.profiles = profiles
        self.pacing_seconds = pacing_seconds
        self._lock = threading.Lock()
        self._status_text = "Starting bulk launch..."
        self._done = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _set_status(self, text: str) -> None:
        with self._lock:
            self._status_text = text

    def _run(self) -> None:
        for i, profile in enumerate(self.profiles):
            # Check STATE.is_running() right before each launch, not just once
            # up front -- an earlier account in this same batch could still be
            # settling into "running" while we reach a later one.
            if STATE.is_running(profile.id):
                self._set_status(f"Skipping {profile.name or '(unnamed profile)'} (already running)")
            else:
                self._set_status(f"Launching {profile.name or '(unnamed profile)'}...")
                STATE.start_launch(profile)
                session = STATE.sessions.get(profile.id)
                if session is not None:
                    bulk_launch.wait_for_readiness(lambda: session.is_done, on_status=self._set_status)

            is_last = i == len(self.profiles) - 1
            if not is_last:
                bulk_launch.apply_pacing_delay(self.pacing_seconds, on_status=self._set_status)

        with self._lock:
            self._done = True

    @property
    def status_text(self) -> str:
        with self._lock:
            return self._status_text

    @property
    def is_done(self) -> bool:
        with self._lock:
            return self._done


# -----------------------------------------------------------------------------
# ProfileEditBuffer: a staging copy of the fields the Settings window edits, kept
# separate from the real GameProfile until Save. `password_input` is write-only --
# it starts empty even when editing a profile that already has a stored password
# (never decrypt-and-display), and is only DPAPI-encrypted over the real
# `password_protected` field on save if the user actually typed something.
# -----------------------------------------------------------------------------

@dataclasses.dataclass
class ProfileEditBuffer:
    is_new: bool
    original_id: Optional[str]
    name: str = ""
    executable_path: str = ""
    email: str = ""
    password_input: str = ""
    has_stored_password: bool = False
    auto_login_enabled: bool = False
    py4gw_enabled: bool = False
    py4gw_dll_path: str = ""
    gmod_enabled: bool = False
    gmod_dll_path: str = ""
    error_message: str = ""

    @staticmethod
    def blank() -> "ProfileEditBuffer":
        return ProfileEditBuffer(is_new=True, original_id=None)

    @staticmethod
    def from_profile(profile: GameProfile) -> "ProfileEditBuffer":
        return ProfileEditBuffer(
            is_new=False,
            original_id=profile.id,
            name=profile.name,
            executable_path=profile.executable_path,
            email=profile.email,
            password_input="",
            has_stored_password=bool(profile.password_protected),
            auto_login_enabled=profile.auto_login_enabled,
            py4gw_enabled=profile.py4gw_enabled,
            py4gw_dll_path=profile.py4gw_dll_path,
            gmod_enabled=profile.gmod_enabled,
            gmod_dll_path=profile.gmod_dll_path,
        )


# -----------------------------------------------------------------------------
# App state
# -----------------------------------------------------------------------------

class AppState:
    def __init__(self):
        self.profiles: list[GameProfile] = []
        self.teams: list[Team] = []
        # None means the built-in "ALL" view -- never a real team, never stored.
        self.current_team_id: Optional[str] = None
        self.sessions: dict[str, LaunchSession] = {}
        self.running_pids: dict[str, int] = {}
        self.selected_id: Optional[str] = None
        self.settings_window_open = False
        self.app_settings_window_open = False
        self.edit_buffer: Optional[ProfileEditBuffer] = None
        self.bulk_launch_session: Optional[BulkLaunchSession] = None
        self.bulk_launch_pacing_seconds: int = load_bulk_launch_pacing_seconds()
        self.name_filter: str = ""
        self._last_liveness_check = 0.0
        self.reload_profiles()
        self.reload_teams()
        self._rehydrate_running_instances()

    def reload_profiles(self) -> None:
        self.profiles = load_profiles()

    def reload_teams(self) -> None:
        self.teams = load_teams()

    def current_team(self) -> Optional[Team]:
        if self.current_team_id is None:
            return None
        return next((t for t in self.teams if t.id == self.current_team_id), None)

    def _view_order(self) -> list[Optional[str]]:
        """[None, team0.id, team1.id, ...] -- None is the ALL view, first always."""
        return [None] + [t.id for t in self.teams]

    def cycle_view(self, direction: int) -> None:
        order = self._view_order()
        try:
            idx = order.index(self.current_team_id)
        except ValueError:
            idx = 0  # current_team_id pointed at a team that no longer exists
        self.current_team_id = order[(idx + direction) % len(order)]

    def jump_to_view(self, team_id: Optional[str]) -> None:
        self.current_team_id = team_id

    def create_team(self, name: str) -> Team:
        """Create a team on the fly (typed into the switcher's popup, no separate
        "manage teams" screen) and switch straight to viewing it."""
        team = Team(name=name)
        self.teams.append(team)
        save_teams(self.teams)
        self.current_team_id = team.id
        return team

    def rename_team(self, team_id: str, new_name: str) -> None:
        team = next((t for t in self.teams if t.id == team_id), None)
        if team is None:
            return
        team.name = new_name
        save_teams(self.teams)

    def delete_team(self, team_id: str) -> None:
        """Removes the team and its membership from every profile -- never
        deletes the profiles themselves, just their membership in this team.
        Falls back to the ALL view if the deleted team was the one currently
        being viewed, rather than leaving current_team_id pointing at nothing.
        """
        self.teams = [t for t in self.teams if t.id != team_id]
        save_teams(self.teams)

        changed = False
        for profile in self.profiles:
            if team_id in profile.team_ids:
                profile.team_ids.remove(team_id)
                changed = True
        if changed:
            save_profiles(self.profiles)

        if self.current_team_id == team_id:
            self.current_team_id = None

    def toggle_team_membership(self, profile: GameProfile, team_id: str) -> None:
        """Toggle `profile`'s membership in `team_id` and save immediately -- the
        card checkbox has no separate "Save" step, unlike the Settings form."""
        if team_id in profile.team_ids:
            profile.team_ids.remove(team_id)
        else:
            profile.team_ids.append(team_id)
        save_profiles(self.profiles)

    def _rehydrate_running_instances(self) -> None:
        """Scan for already-running game processes matching each profile's exe path,
        once at startup before the first render. Covers processes this launcher
        instance didn't itself start: a manual launch, Launch.bat, the old C#
        launcher, or a previous session of this same app that's since closed --
        the point is reflecting real process state, not just what we launched.

        If two profiles share an exe path, claimed PIDs are excluded from later
        matches in the same pass so the same running process can't get assigned to
        more than one card.
        """
        claimed_pids: set = set()
        for profile in self.profiles:
            pid = find_running_pid_for_exe_path(profile.executable_path, exclude_pids=claimed_pids)
            if pid is None:
                continue

            claimed_pids.add(pid)
            self.running_pids[profile.id] = pid

            # Nice-to-have: apply the same window title override a fresh launch
            # gets, for consistency. Best-effort -- a missing/failed window lookup
            # here doesn't affect tracking correctness (that's PID-based).
            hwnd = find_visible_window_for_pid(pid)
            if hwnd is not None:
                title = WINDOW_TITLE_FORMAT.format(profile_name=profile.name or "(unnamed profile)")
                set_window_title(hwnd, title)

    def begin_new_profile(self) -> None:
        self.edit_buffer = ProfileEditBuffer.blank()
        self.settings_window_open = True

    def begin_edit_selected(self) -> None:
        profile = next((p for p in self.profiles if p.id == self.selected_id), None)
        self.edit_buffer = ProfileEditBuffer.from_profile(profile) if profile else None
        self.settings_window_open = True

    def cancel_edit(self) -> None:
        self.edit_buffer = None

    def edit_buffer_is_dirty(self) -> bool:
        """True if edit_buffer holds changes not yet written via save_edit_buffer().
        Guards the Settings window's titlebar close (X) button so a checked-but-
        unsaved toggle can't be silently discarded -- real testing hit exactly this:
        "Inject Py4GW" looked checked in Settings, but the window had been closed
        (or focus moved away) without clicking Save, so the launch read the real
        profile's still-False value and failed.
        """
        buffer = self.edit_buffer
        if buffer is None:
            return False

        baseline = ProfileEditBuffer.blank()
        if not buffer.is_new:
            profile = next((p for p in self.profiles if p.id == buffer.original_id), None)
            if profile is not None:
                baseline = ProfileEditBuffer.from_profile(profile)

        return (
            buffer.name != baseline.name
            or buffer.executable_path != baseline.executable_path
            or buffer.email != baseline.email
            or buffer.password_input != baseline.password_input
            or buffer.auto_login_enabled != baseline.auto_login_enabled
            or buffer.py4gw_enabled != baseline.py4gw_enabled
            or buffer.py4gw_dll_path != baseline.py4gw_dll_path
            or buffer.gmod_enabled != baseline.gmod_enabled
            or buffer.gmod_dll_path != baseline.gmod_dll_path
        )

    def save_edit_buffer(self) -> None:
        buffer = self.edit_buffer
        if buffer is None:
            return

        if not buffer.executable_path or not os.path.exists(buffer.executable_path):
            buffer.error_message = f"Executable path does not exist: {buffer.executable_path!r}"
            return

        if buffer.is_new:
            profile = GameProfile()
            self.profiles.append(profile)
        else:
            profile = next((p for p in self.profiles if p.id == buffer.original_id), None)
            if profile is None:
                buffer.error_message = "Profile no longer exists (removed elsewhere?)."
                return

        profile.name = buffer.name
        profile.executable_path = buffer.executable_path
        profile.email = buffer.email
        profile.auto_login_enabled = buffer.auto_login_enabled
        profile.py4gw_enabled = buffer.py4gw_enabled
        profile.py4gw_dll_path = buffer.py4gw_dll_path
        profile.gmod_enabled = buffer.gmod_enabled
        profile.gmod_dll_path = buffer.gmod_dll_path
        if buffer.password_input:
            profile.password_protected = protect_password(buffer.password_input)

        save_profiles(self.profiles)

        self.selected_id = profile.id
        self.edit_buffer = None
        self.settings_window_open = False

    def is_launching(self, profile_id: str) -> bool:
        session = self.sessions.get(profile_id)
        return session is not None and not session.is_done

    def is_running(self, profile_id: str) -> bool:
        return profile_id in self.running_pids

    def start_launch(self, profile: GameProfile) -> None:
        if self.is_launching(profile.id) or self.is_running(profile.id):
            return
        session = LaunchSession(profile)
        self.sessions[profile.id] = session
        session.start()

    def is_bulk_launching(self) -> bool:
        return self.bulk_launch_session is not None and not self.bulk_launch_session.is_done

    def start_bulk_launch(self, profiles: list[GameProfile]) -> None:
        if self.is_bulk_launching() or not profiles:
            return
        session = BulkLaunchSession(profiles, self.bulk_launch_pacing_seconds)
        self.bulk_launch_session = session
        session.start()

    def set_bulk_launch_pacing_seconds(self, seconds: int) -> None:
        self.bulk_launch_pacing_seconds = seconds
        save_bulk_launch_pacing_seconds(seconds)

    def foreground_profile(self, profile_id: str) -> None:
        pid = self.running_pids.get(profile_id)
        if pid is None:
            return
        hwnd = find_visible_window_for_pid(pid)
        if hwnd is not None:
            foreground_window(hwnd)

    def update(self) -> None:
        """Called once per frame: promote finished successful sessions into
        running_pids, and periodically prune pids that are no longer alive."""
        for profile_id, session in list(self.sessions.items()):
            if session.is_done:
                result = session.result
                if result is not None and result.success and result.pid is not None:
                    if profile_id not in self.running_pids:
                        self.running_pids[profile_id] = result.pid
                        hwnd = find_visible_window_for_pid(result.pid)
                        if hwnd is not None:
                            title = WINDOW_TITLE_FORMAT.format(profile_name=session.profile.name or "(unnamed profile)")
                            set_window_title(hwnd, title)
                    del self.sessions[profile_id]
                elif result is not None and not result.success:
                    # keep the session around so its "Failed: ..." status_text stays
                    # visible on the card; only cleared by a fresh launch attempt.
                    pass

        now = time.time()
        if now - self._last_liveness_check >= 1.0:
            self._last_liveness_check = now
            for profile_id, pid in list(self.running_pids.items()):
                if not psutil.pid_exists(pid):
                    self.running_pids.pop(profile_id, None)


STATE = AppState()


# -----------------------------------------------------------------------------
# Card grid (main window content)
# -----------------------------------------------------------------------------

def membership_checkbox_rect(card_origin, card_h: float, em: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """Bottom-left corner -- the only card corner not already used by the avatar
    (top-left), hover action icon (top-right), or mod badges (bottom-right).
    Shared by show_main_window's manual hit-test and draw_profile_card's visual so
    the clickable area and the drawn box are always the exact same rectangle.
    """
    x, y = card_origin
    size = em * 1.0
    min_pt = (x + em * 0.667, y + card_h - em * 1.667)
    max_pt = (min_pt[0] + size, min_pt[1] + size)
    return min_pt, max_pt


def _draw_membership_checkbox(draw_list, min_pt, max_pt, *, is_member: bool, hovered: bool) -> None:
    """Its own small click target, separate from the rest of the card -- see
    show_main_window, which excludes this rect from the card's own hover/click
    handling so the two interactions can't collide."""
    border = ACCENT if hovered else CARD_BORDER
    draw_list.add_rect(min_pt, max_pt, border, rounding=3.0, thickness=1.5)
    if is_member:
        pad = (max_pt[0] - min_pt[0]) * 0.25
        inner_min = (min_pt[0] + pad, min_pt[1] + pad)
        inner_max = (max_pt[0] - pad, max_pt[1] - pad)
        draw_list.add_rect_filled(inner_min, inner_max, ACCENT, rounding=2.0)


def _draw_play_icon(draw_list, center, size: float, color: int) -> None:
    """Small filled play triangle -- hover cue on a stopped card. Purely visual,
    not a separate click target: the whole card already handles double-click."""
    r = size / 2
    p1 = (center[0] - r * 0.6, center[1] - r * 0.8)
    p2 = (center[0] - r * 0.6, center[1] + r * 0.8)
    p3 = (center[0] + r * 0.9, center[1])
    draw_list.add_triangle_filled(p1, p2, p3, color)


def _draw_bring_to_front_icon(draw_list, center, size: float, color: int) -> None:
    """Two overlapping squares (back outline, front filled) -- the common
    "bring to front" glyph, used as a hover cue on an already-running card."""
    r = size / 2
    back_min = (center[0] - r, center[1] - r)
    back_max = (center[0] + r * 0.35, center[1] + r * 0.35)
    front_min = (center[0] - r * 0.35, center[1] - r * 0.35)
    front_max = (center[0] + r, center[1] + r)
    draw_list.add_rect(back_min, back_max, color, thickness=1.5)
    draw_list.add_rect_filled(front_min, front_max, color, rounding=1.0)


def _draw_gear_icon(draw_list, center, size: float, color: int) -> None:
    """Hub + radiating teeth -- both reference launchers (GWxLauncher and the
    newer Python launcher PR) use a gear icon for app settings, a recognized
    affordance worth matching rather than inventing a new one."""
    cx, cy = center
    hub_r = size * 0.26
    tooth_len = size * 0.16
    tooth_w = size * 0.2
    num_teeth = 6
    draw_list.add_circle_filled(center, hub_r, color, num_segments=20)
    for i in range(num_teeth):
        angle = (2 * math.pi / num_teeth) * i
        dx, dy = math.cos(angle), math.sin(angle)
        px, py = -dy, dx
        r_mid = hub_r + tooth_len / 2
        mx, my = cx + dx * r_mid, cy + dy * r_mid
        half_len, half_w = tooth_len / 2, tooth_w / 2
        p1 = (mx + dx * half_len + px * half_w, my + dy * half_len + py * half_w)
        p2 = (mx + dx * half_len - px * half_w, my + dy * half_len - py * half_w)
        p3 = (mx - dx * half_len - px * half_w, my - dy * half_len - py * half_w)
        p4 = (mx - dx * half_len + px * half_w, my - dy * half_len + py * half_w)
        draw_list.add_quad_filled(p1, p2, p3, p4, color)


def draw_profile_card(draw_list, origin, profile: GameProfile, *, card_w: float, card_h: float, hovered: bool, selected: bool, running: bool, launching: bool, status_text: str, is_error: bool, in_team_view: bool = False, is_member: bool = False, checkbox_hovered: bool = False) -> None:
    em = hello_imgui.em_size()
    x, y = origin
    p_min = (x, y)
    p_max = (x + card_w, y + card_h)

    if selected:
        bg, border = CARD_SELECTED_BACK, ACCENT
    elif hovered:
        bg, border = HOVER_BACK, HOVER_BORDER
    else:
        bg, border = CARD_BACK, CARD_BORDER

    draw_list.add_rect_filled(p_min, p_max, bg, rounding=6.0)
    draw_list.add_rect(p_min, p_max, border, rounding=6.0, thickness=1.0)

    if selected:
        draw_list.add_rect_filled((x, y), (x + em * 0.267, y + card_h), ACCENT, rounding=6.0)

    if in_team_view:
        checkbox_min, checkbox_max = membership_checkbox_rect((x, y), card_h, em)
        _draw_membership_checkbox(draw_list, checkbox_min, checkbox_max, is_member=is_member, hovered=checkbox_hovered)

    icon_center = (x + em * 1.733, y + em * 1.6)
    draw_list.add_circle_filled(icon_center, em * 0.8, _avatar_color_for_id(profile.id))

    initial = (profile.name[:1] or "?").upper()
    initial_size = imgui.calc_text_size(initial)
    draw_list.add_text(
        (icon_center[0] - initial_size.x / 2, icon_center[1] - initial_size.y / 2),
        CARD_NAME_FORE, initial,
    )

    if hovered:
        action_center = (x + card_w - em * 1.267, y + em * 1.267)
        if running:
            _draw_bring_to_front_icon(draw_list, action_center, em * 1.0, ACCENT)
        else:
            _draw_play_icon(draw_list, action_center, em * 1.0, ACCENT)

    text_x = x + em * 3.067
    draw_list.add_text((text_x, y + em * 0.933), CARD_NAME_FORE, profile.name or "(unnamed profile)")

    if launching:
        sub_col = STATUS_ERROR if is_error else STATUS_PROGRESS
        sub_text = status_text
    elif running:
        sub_col = ACCENT
        sub_text = "Running"
    else:
        sub_col = CARD_SUB_FORE
        sub_text = "Guild Wars 1"
    draw_list.add_text((text_x, y + em * 2.133), sub_col, sub_text)

    badges = []
    if profile.py4gw_enabled:
        badges.append("Py4GW")
    if profile.gmod_enabled:
        badges.append("gMod")

    badge_pad = em * 0.4
    badge_x = x + card_w - em * 0.667
    badge_y = y + card_h - em * 1.467
    badge_h = em * 1.067
    for badge in badges:
        # Real measured text width (imgui.calc_text_size), not a guessed
        # chars-times-average-width estimate -- stays correct at any font/DPI.
        text_w = imgui.calc_text_size(badge).x
        w = text_w + badge_pad * 2
        badge_x -= w + em * 0.267
        b_min = (badge_x, badge_y)
        b_max = (badge_x + w, badge_y + badge_h)
        draw_list.add_rect_filled(b_min, b_max, BADGE_BACK, rounding=8.0)
        draw_list.add_text((badge_x + badge_pad, badge_y + em * 0.067), BADGE_FORE, badge)


def draw_add_card(draw_list, origin, *, card_w: float, card_h: float, hovered: bool) -> None:
    """The "+" card: same size/shape as a profile card, consistent visual language,
    but a dashed-feeling outline (achieved with the hover border color at rest) and
    a plain "+" instead of icon/name/badges, so it doesn't read as a real profile."""
    em = hello_imgui.em_size()
    x, y = origin
    p_min = (x, y)
    p_max = (x + card_w, y + card_h)

    bg = HOVER_BACK if hovered else CARD_BACK
    border = ACCENT if hovered else CARD_BORDER
    draw_list.add_rect_filled(p_min, p_max, bg, rounding=6.0)
    draw_list.add_rect(p_min, p_max, border, rounding=6.0, thickness=1.0)

    plus_col = ACCENT if hovered else CARD_SUB_FORE
    cx, cy = x + card_w / 2, y + card_h / 2
    arm = em * 0.667
    draw_list.add_line((cx - arm, cy), (cx + arm, cy), plus_col, thickness=2.0)
    draw_list.add_line((cx, cy - arm), (cx, cy + arm), plus_col, thickness=2.0)
    text = "Add profile"
    text_w = imgui.calc_text_size(text).x
    draw_list.add_text((cx - text_w / 2, y + card_h - em * 1.467), plus_col, text)


_TEAM_SWITCHER_POPUP_ID = "Jump to view##team_switcher_popup"
_new_team_name_buffer = ""
# Which team's context menu (opened by right-click, same pattern as profile
# cards) is mid-rename -- None means no context menu is in rename mode.
_renaming_team_id: Optional[str] = None
_rename_buffer = ""


def _draw_dropdown_caret(draw_list, rect_min, rect_max, color: int) -> None:
    """Small downward chevron near a button's right edge -- the only visible
    signal that the label itself opens a dropdown, distinct from the plain </>
    nudge arrows beside it. Sized relative to the button's own height so it
    scales correctly at any font/DPI, same convention as the rest of this file.
    """
    height = rect_max[1] - rect_min[1]
    cx = rect_max[0] - height * 0.45
    cy = (rect_min[1] + rect_max[1]) / 2
    r = height * 0.18
    p1 = (cx - r, cy - r * 0.5)
    p2 = (cx + r, cy - r * 0.5)
    p3 = (cx, cy + r * 0.6)
    draw_list.add_triangle_filled(p1, p2, p3, color)


def show_team_switcher() -> None:
    """Center label + </> arrows to cycle views (ALL first, then each team in
    stored order). Clicking the label opens a popup listing every view for a
    direct jump -- cycling one at a time through a long team list would be
    tedious -- plus a text box to create a new team on the fly, no separate
    "manage teams" screen. A small caret next to the label is the only thing
    that visibly distinguishes it as its own, separate clickable action from
    the </> arrows -- without it, the label reads as inert text sitting between
    two buttons rather than a second, distinct way to change the view. Does not
    filter the card grid itself: which cards are visible never changes with the
    view (see draw_profile_card's membership checkbox, which is what the view
    actually controls).
    """
    global _new_team_name_buffer, _renaming_team_id, _rename_buffer

    em = hello_imgui.em_size()
    current_team = STATE.current_team()
    label = current_team.name if current_team else "ALL"

    arrow_w = em * 2.0
    label_w = em * 12.0
    total_w = arrow_w * 2 + label_w
    avail_w = imgui.get_content_region_avail().x
    indent = (avail_w - total_w) / 2
    if indent > 0:
        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + indent)

    if imgui.button("<##team_prev", size=(arrow_w, 0)):
        STATE.cycle_view(-1)
    imgui.same_line()
    label_clicked = imgui.button(f"{label}##team_label", size=(label_w, 0))
    _draw_dropdown_caret(imgui.get_window_draw_list(), imgui.get_item_rect_min(), imgui.get_item_rect_max(), CARD_SUB_FORE)
    if label_clicked:
        imgui.open_popup(_TEAM_SWITCHER_POPUP_ID)
        _new_team_name_buffer = ""
    imgui.same_line()
    if imgui.button(">##team_next", size=(arrow_w, 0)):
        STATE.cycle_view(1)

    if imgui.begin_popup(_TEAM_SWITCHER_POPUP_ID):
        if imgui.selectable("ALL", STATE.current_team_id is None)[0]:
            STATE.jump_to_view(None)
            imgui.close_current_popup()
        for team in STATE.teams:
            if imgui.selectable(team.name or "(unnamed team)", STATE.current_team_id == team.id)[0]:
                STATE.jump_to_view(team.id)
                imgui.close_current_popup()

            # Right-click a team for Rename/Delete -- same pattern as the
            # existing right-click-to-edit on profile cards.
            context_popup_id = f"team_context##{team.id}"
            imgui.open_popup_on_item_click(context_popup_id)
            if imgui.begin_popup(context_popup_id):
                if _renaming_team_id == team.id:
                    imgui.set_next_item_width(em * 10.0)
                    enter_pressed, _rename_buffer = imgui.input_text(
                        f"##rename_team_{team.id}", _rename_buffer,
                        flags=int(imgui.InputTextFlags_.enter_returns_true.value),
                    )
                    imgui.same_line()
                    save_clicked = imgui.button("Save")
                    renamed = _rename_buffer.strip()
                    if (enter_pressed or save_clicked) and renamed:
                        STATE.rename_team(team.id, renamed)
                        _renaming_team_id = None
                        imgui.close_current_popup()
                    imgui.same_line()
                    if imgui.button("Cancel"):
                        _renaming_team_id = None
                        imgui.close_current_popup()
                else:
                    if imgui.selectable("Rename", False)[0]:
                        _renaming_team_id = team.id
                        _rename_buffer = team.name
                    if imgui.selectable("Delete", False)[0]:
                        STATE.delete_team(team.id)
                        imgui.close_current_popup()
                imgui.end_popup()

        imgui.separator()
        imgui.set_next_item_width(em * 10.0)
        enter_pressed, _new_team_name_buffer = imgui.input_text(
            "##new_team_name", _new_team_name_buffer,
            flags=int(imgui.InputTextFlags_.enter_returns_true.value),
        )
        imgui.same_line()
        create_clicked = imgui.button("Create")
        new_name = _new_team_name_buffer.strip()
        if (enter_pressed or create_clicked) and new_name:
            STATE.create_team(new_name)
            _new_team_name_buffer = ""
            imgui.close_current_popup()
        imgui.end_popup()


def _visible_profiles() -> list[GameProfile]:
    """Profiles matching the current name filter (case-insensitive substring) --
    the single source of truth for "visible" used by the card grid. Composes
    with the team view: the filter narrows within whichever view is active,
    not just ALL.
    """
    query = STATE.name_filter.strip().lower()
    if not query:
        return list(STATE.profiles)
    return [p for p in STATE.profiles if query in p.name.lower()]


def show_team_actions() -> None:
    """Launch Team -- only meaningful in a real team view (ALL has no
    membership, so there's nothing to bulk-launch). Disabled/unarmed unless at
    least one account is checked into the currently-viewed team, and while a
    bulk launch is already running (never overlap two at once).

    "Select all visible" / "Select none" were cut per design review -- they
    didn't earn their toolbar space -- rather than relabeled or relocated. The
    pacing control moved to the app settings window (gear icon) -- this is
    just the action and its live status, which stays here since that's what
    the user is actually watching during a launch.
    """
    team_id = STATE.current_team_id
    if team_id is None:
        return

    members = [p for p in STATE.profiles if team_id in p.team_ids]
    bulk_launching = STATE.is_bulk_launching()
    can_launch = bool(members) and not bulk_launching

    if not can_launch:
        imgui.begin_disabled()
    launch_clicked = imgui.button("Launch Team")
    if not can_launch:
        imgui.end_disabled()
    if launch_clicked and can_launch:
        STATE.start_bulk_launch(members)

    if bulk_launching:
        imgui.same_line()
        imgui.text_colored((0.9, 0.75, 0.3, 1.0), STATE.bulk_launch_session.status_text)


def show_settings_gear_button() -> None:
    """Small gear icon, right-aligned in the toolbar -- both reference
    launchers use this same icon for this same purpose, so it's a recognized
    affordance rather than a new one to learn."""
    em = hello_imgui.em_size()
    icon_size = em * 1.8
    avail_w = imgui.get_content_region_avail().x
    imgui.same_line(avail_w - icon_size)
    clicked = imgui.button("##app_settings_gear", size=(icon_size, icon_size))
    item_min, item_max = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    center = ((item_min[0] + item_max[0]) / 2, (item_min[1] + item_max[1]) / 2)
    _draw_gear_icon(imgui.get_window_draw_list(), center, icon_size * 0.7, CARD_SUB_FORE)
    if clicked:
        STATE.app_settings_window_open = True


def show_main_window() -> None:
    STATE.update()

    imgui.text(f"{len(STATE.profiles)} profile(s) loaded from profile_store.")
    show_settings_gear_button()

    imgui.spacing()
    show_team_switcher()
    show_team_actions()

    imgui.spacing()
    imgui.set_next_item_width(hello_imgui.em_size() * 16.0)
    _, STATE.name_filter = imgui.input_text_with_hint("##name_filter", "Filter by name...", STATE.name_filter)

    imgui.separator()
    imgui.spacing()

    em = hello_imgui.em_size()
    card_w, card_h, card_gap = _card_dimensions()
    avail_w = imgui.get_content_region_avail().x
    cols = max(1, int(avail_w // (card_w + card_gap)))
    visible_profiles = _visible_profiles()

    imgui.begin_child("card_grid", size=(0, 0), child_flags=int(imgui.ChildFlags_.borders.value))
    draw_list = imgui.get_window_draw_list()
    origin = imgui.get_cursor_screen_pos()
    grid_is_hoverable = imgui.is_window_hovered()

    for i, profile in enumerate(visible_profiles):
        col = i % cols
        row = i // cols
        card_origin = (
            origin.x + col * (card_w + card_gap),
            origin.y + row * (card_h + card_gap),
        )
        p_min = card_origin
        p_max = (card_origin[0] + card_w, card_origin[1] + card_h)

        in_team_view = STATE.current_team_id is not None
        checkbox_hovered = False
        if in_team_view:
            checkbox_min, checkbox_max = membership_checkbox_rect(card_origin, card_h, em)
            checkbox_hovered = grid_is_hoverable and imgui.is_mouse_hovering_rect(checkbox_min, checkbox_max)
            if checkbox_hovered and imgui.is_mouse_clicked(0):
                STATE.toggle_team_membership(profile, STATE.current_team_id)

        # Excludes the checkbox's own rect so the two click targets can't collide:
        # clicking the checkbox toggles membership only, never also selects/
        # forgrounds the card underneath it.
        hovered = grid_is_hoverable and imgui.is_mouse_hovering_rect(p_min, p_max) and not checkbox_hovered
        running = STATE.is_running(profile.id)
        launching = STATE.is_launching(profile.id)
        session = STATE.sessions.get(profile.id)
        status_text = session.status_text if session else ""
        is_error = bool(session and session.is_done and session.result and not session.result.success)

        if hovered and imgui.is_mouse_clicked(0):
            if running:
                STATE.foreground_profile(profile.id)
            else:
                STATE.selected_id = profile.id

        if hovered and imgui.is_mouse_double_clicked(0):
            if not running and not launching:
                STATE.start_launch(profile)

        if hovered and imgui.is_mouse_clicked(1):
            STATE.selected_id = profile.id
            STATE.begin_edit_selected()

        draw_profile_card(
            draw_list, card_origin, profile, card_w=card_w, card_h=card_h,
            hovered=hovered, selected=(STATE.selected_id == profile.id),
            running=running, launching=launching or is_error,
            status_text=status_text, is_error=is_error,
            in_team_view=in_team_view,
            is_member=bool(in_team_view and STATE.current_team_id in profile.team_ids),
            checkbox_hovered=checkbox_hovered,
        )

    add_index = len(visible_profiles)
    add_col = add_index % cols
    add_row = add_index // cols
    add_origin = (
        origin.x + add_col * (card_w + card_gap),
        origin.y + add_row * (card_h + card_gap),
    )
    add_p_min = add_origin
    add_p_max = (add_origin[0] + card_w, add_origin[1] + card_h)
    add_hovered = grid_is_hoverable and imgui.is_mouse_hovering_rect(add_p_min, add_p_max)
    if add_hovered and imgui.is_mouse_clicked(0):
        STATE.begin_new_profile()
    draw_add_card(draw_list, add_origin, card_w=card_w, card_h=card_h, hovered=add_hovered)

    rows = (add_index + cols) // cols
    imgui.dummy((avail_w, rows * (card_h + card_gap)))
    imgui.end_child()


# -----------------------------------------------------------------------------
# Settings window -- add/edit form for the selected or new profile. One shared
# window/tab shell for both add and edit (not a second, separate form).
# -----------------------------------------------------------------------------

def _browse_for_file(*, title: str, filter_str: str, initial_path: str = "") -> Optional[str]:
    """Blocking native Win32 file-open dialog via the pywin32 dependency this
    project already uses elsewhere (crypto.py, gw1_launch.py, window_control.py) --
    no new dependency, per this project's deliberately careful 32-bit dependency
    footprint. tkinter.filedialog was tried first, but this venv's Python install
    is missing its Tcl library files -- `import tkinter` succeeds and even
    `tkinter.TkVersion` reads fine, but `tkinter.Tk()` itself raises TclError
    ("Can't find a usable init.tcl"), so it's not actually usable here.

    `filter_str` follows Win32's raw OPENFILENAME filter format: NUL-separated
    "description\\0pattern" pairs, e.g. "DLL files\\0*.dll\\0All files\\0*.*\\0".

    Confirmed against the actual injection/launch code (gw1_launch.py) before
    adding this: executable_path is wrapped straight into a launch command line,
    and py4gw_dll_path is written byte-for-byte into the target process for
    LoadLibraryA-style injection -- both need a specific file, not a folder, so
    this is always a file-open dialog, never a folder picker.
    """
    initial_dir = os.path.dirname(initial_path) if initial_path else ""
    if not os.path.isdir(initial_dir):
        initial_dir = ""

    try:
        filename, _customfilter, _flags = win32gui.GetOpenFileNameW(
            InitialDir=initial_dir,
            Filter=filter_str,
            Title=title,
            Flags=win32con.OFN_FILEMUSTEXIST | win32con.OFN_PATHMUSTEXIST,
        )
    except pywintypes.error:
        return None  # user cancelled

    return filename or None


SETTINGS_TABS = ["General", "Mods", "Window"]
_active_tab = SETTINGS_TABS[0]

# How many frames to keep AlwaysAutoResize active after the Settings window
# (re)appears -- see show_settings_window() for why this needs to be more than 1.
_SETTINGS_AUTOSIZE_FRAMES = 4
_settings_autosize_frames_remaining = 0


def show_settings_content() -> None:
    global _active_tab

    buffer = STATE.edit_buffer
    em = hello_imgui.em_size()

    imgui.begin_child("settings_sidebar", size=(em * 8.0, 0), child_flags=int(imgui.ChildFlags_.borders.value))
    for tab in SETTINGS_TABS:
        clicked, _ = imgui.selectable(tab, tab == _active_tab)
        if clicked:
            _active_tab = tab
    imgui.end_child()

    imgui.same_line()

    imgui.begin_child("settings_content", size=(0, 0))
    if buffer is None:
        imgui.text("No profile selected -- click a card, or click \"Add profile\" to create one.")
        imgui.end_child()
        return

    imgui.text("New profile" if buffer.is_new else f"Editing: {buffer.name or '(unnamed profile)'}")
    imgui.separator()

    if _active_tab == "General":
        _, buffer.name = imgui.input_text("Profile name", buffer.name)
        _, buffer.executable_path = imgui.input_text("Executable path", buffer.executable_path)
        imgui.same_line()
        if imgui.button("Browse##executable_path"):
            chosen = _browse_for_file(
                title="Select Guild Wars executable",
                filter_str="Guild Wars executable (Gw.exe)\0Gw.exe\0Executable files (*.exe)\0*.exe\0All files (*.*)\0*.*\0",
                initial_path=buffer.executable_path,
            )
            if chosen:
                buffer.executable_path = chosen
        _, buffer.email = imgui.input_text("Account email", buffer.email)
        _, buffer.password_input = imgui.input_text(
            "Password", buffer.password_input, flags=int(imgui.InputTextFlags_.password.value)
        )
        if buffer.has_stored_password and not buffer.password_input:
            imgui.text_colored((0.6, 0.6, 0.65, 1.0), "A password is already saved -- leave blank to keep it.")
        _, buffer.auto_login_enabled = imgui.checkbox("Enable auto-login", buffer.auto_login_enabled)
    elif _active_tab == "Mods":
        _, buffer.py4gw_enabled = imgui.checkbox("Inject Py4GW", buffer.py4gw_enabled)
        _, buffer.py4gw_dll_path = imgui.input_text("Py4GW DLL path", buffer.py4gw_dll_path)
        imgui.same_line()
        if imgui.button("Browse##py4gw_dll_path"):
            chosen = _browse_for_file(
                title="Select Py4GW DLL",
                filter_str="DLL files (*.dll)\0*.dll\0All files (*.*)\0*.*\0",
                initial_path=buffer.py4gw_dll_path,
            )
            if chosen:
                buffer.py4gw_dll_path = chosen
        _, buffer.gmod_enabled = imgui.checkbox("Inject gMod", buffer.gmod_enabled)
        _, buffer.gmod_dll_path = imgui.input_text("gMod DLL path", buffer.gmod_dll_path)
        imgui.same_line()
        if imgui.button("Browse##gmod_dll_path"):
            chosen = _browse_for_file(
                title="Select gMod DLL",
                filter_str="DLL files (*.dll)\0*.dll\0All files (*.*)\0*.*\0",
                initial_path=buffer.gmod_dll_path,
            )
            if chosen:
                buffer.gmod_dll_path = chosen
        imgui.text_colored((0.6, 0.6, 0.65, 1.0), "(gMod injection timing not implemented yet)")
    elif _active_tab == "Window":
        existing = next((p for p in STATE.profiles if p.id == buffer.original_id), None) if not buffer.is_new else None
        if existing is None:
            imgui.text("Window placement is recorded after the profile has been launched once.")
        else:
            imgui.text(f"Windowed mode enabled: {existing.windowed_mode_enabled}")
            imgui.text(f"Size: {existing.window_width}x{existing.window_height} @ ({existing.window_x}, {existing.window_y})")
        imgui.text_colored((0.6, 0.6, 0.65, 1.0), "(editing window placement not implemented yet)")

    imgui.separator()
    if buffer.error_message:
        imgui.text_colored((0.86, 0.35, 0.35, 1.0), buffer.error_message)
    if imgui.button("Save"):
        STATE.save_edit_buffer()
    imgui.same_line()
    if imgui.button("Cancel"):
        STATE.cancel_edit()
    imgui.end_child()


_UNSAVED_CHANGES_POPUP_ID = "Unsaved changes?##settings_close_confirm"


def _show_unsaved_changes_popup() -> None:
    """Rendered unconditionally every frame the Settings window is open -- only
    actually appears once open_popup(_UNSAVED_CHANGES_POPUP_ID) has been called
    (see show_settings_window's close-request handling below), per ImGui's own
    open/begin popup pattern."""
    if imgui.begin_popup_modal(_UNSAVED_CHANGES_POPUP_ID, flags=int(imgui.WindowFlags_.always_auto_resize.value))[0]:
        imgui.text("This profile has unsaved changes.")
        imgui.spacing()
        if imgui.button("Save"):
            STATE.save_edit_buffer()
            imgui.close_current_popup()
        imgui.same_line()
        if imgui.button("Discard"):
            STATE.cancel_edit()
            STATE.settings_window_open = False
            imgui.close_current_popup()
        imgui.same_line()
        if imgui.button("Keep editing"):
            imgui.close_current_popup()
        imgui.end_popup()


def show_settings_window() -> None:
    if not STATE.settings_window_open:
        return

    global _settings_autosize_frames_remaining

    em = hello_imgui.em_size()
    imgui.set_next_window_pos((em * 4.0, em * 4.0), cond=imgui.Cond_.appearing.value)
    # Rough baseline for the single frame before real measurement below takes
    # over -- not the final word, just avoids a jarring flash at some ImGui
    # internal default size before AlwaysAutoResize kicks in.
    imgui.set_next_window_size((em * 32.0, em * 21.3), cond=imgui.Cond_.appearing.value)
    imgui.set_next_window_size_constraints((em * 20.0, em * 12.0), (1.0e9, 1.0e9))

    autosizing = _settings_autosize_frames_remaining > 0
    flags = imgui.WindowFlags_.always_auto_resize.value if autosizing else 0

    # Always pass True as the window's own p_open: we handle a close request
    # (requested_open == False below) ourselves rather than letting ImGui close
    # the window immediately, so an unsaved edit isn't silently dropped just
    # because the titlebar X was clicked instead of Save.
    expanded, requested_open = imgui.begin("Settings##launcher", True, flags)

    if imgui.is_window_appearing():
        # Real, measured sizing, not a guessed formula: force AlwaysAutoResize for
        # the next few frames so the window genuinely fits whatever is actually
        # rendered inside it -- correct at any DPI/font scale, since it's driven
        # by real ImGui layout, not a size we precomputed. After that, drop the
        # flag so the window becomes normally resizable, and Dear ImGui's own
        # ini-based window-state persistence remembers whatever size it settled
        # at (or whatever the user resizes it to later) across restarts.
        _settings_autosize_frames_remaining = _SETTINGS_AUTOSIZE_FRAMES
    elif _settings_autosize_frames_remaining > 0:
        _settings_autosize_frames_remaining -= 1

    if not requested_open:
        if STATE.edit_buffer_is_dirty():
            imgui.open_popup(_UNSAVED_CHANGES_POPUP_ID)
        else:
            STATE.settings_window_open = False
            STATE.edit_buffer = None

    if expanded:
        show_settings_content()

    _show_unsaved_changes_popup()

    imgui.end()


# -----------------------------------------------------------------------------
# App settings window (gear icon) -- lightweight, global settings that aren't
# per-profile or per-team. Kept minimal on purpose: just the pieces relocated
# in this pass, not placeholder sections for anything not designed yet.
# -----------------------------------------------------------------------------

def show_app_settings_window() -> None:
    if not STATE.app_settings_window_open:
        return

    em = hello_imgui.em_size()
    imgui.set_next_window_size((em * 30.0, em * 11.0), cond=imgui.Cond_.appearing.value)
    expanded, STATE.app_settings_window_open = imgui.begin("App Settings##launcher", STATE.app_settings_window_open)
    if expanded:
        imgui.text("Delay between team launches (seconds):")
        imgui.same_line()
        imgui.set_next_item_width(em * 6.0)
        # No UI-side min/max here on purpose -- the UI may show/accept any
        # value; the real safety floor/ceiling is enforced in
        # bulk_launch.clamp_pacing_seconds, in the code that actually executes
        # the wait, not here.
        changed, new_value = imgui.input_int("##bulk_pacing_seconds", STATE.bulk_launch_pacing_seconds)
        if changed:
            STATE.set_bulk_launch_pacing_seconds(new_value)
        imgui.text_colored((0.6, 0.6, 0.65, 1.0), "(actual delay is always kept between 5 and 90 seconds)")

        imgui.separator()
        imgui.spacing()
        if imgui.button("Reload profiles and teams from disk"):
            STATE.reload_profiles()
            STATE.reload_teams()
    imgui.end()


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def gui() -> None:
    show_main_window()
    show_settings_window()
    show_app_settings_window()


def main() -> None:
    runner_params = hello_imgui.RunnerParams()
    runner_params.app_window_params.window_title = "Py4GW_Reforged_Launcher"
    # Initial size only matters for the true first-ever run -- restore_previous_geometry
    # (below) takes over after that. Per hello_imgui's own docs this size is "handled
    # as if specified for a 96 PPI screen", i.e. it's already scaled for the actual
    # display's DPI internally; 900x600 is a reasonable default for a card grid that
    # scrolls/wraps regardless of window size, not a hard content-fit requirement the
    # way the Settings form is. resizable defaults to True already.
    runner_params.app_window_params.window_geometry.size = (900, 600)
    # Persist the main window's size/position across restarts (written to
    # imgui_app_window.ini alongside this launcher's own .ini). Off by default in
    # hello_imgui; nothing was persisting the OS-level window's geometry before this.
    runner_params.app_window_params.restore_previous_geometry = True

    runner_params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_window
    )
    runner_params.imgui_window_params.enable_viewports = True

    runner_params.callbacks.show_gui = gui
    runner_params.callbacks.post_init = _apply_window_icon

    hello_imgui.run(runner_params)


if __name__ == "__main__":
    main()
