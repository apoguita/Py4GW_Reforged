"""Py4GW_Reforged_Launcher -- real, minimal working launcher window.

Wires the validated UI spike (spikes/spike_ui_multiviewport.py: card-grid main window
+ multi-viewport settings window) to the real profile data layer (launcher_core) and
the real GW1 launch pipeline (launcher_core.gw1_launch). Not a mockup: cards show real
profiles loaded from profile_store, clicking them drives the actual injection
pipeline, and status text reflects the pipeline's real, live progress.

Add/edit profiles through the Settings window (opened via the "+" card for a new
profile, or "Settings" with a card selected to edit it). Reuses the one settings
window/tab shell rather than a second, separate form. Password field never displays
the real stored value -- it's write-only: blank means "don't change," typing a new
value replaces the DPAPI blob on save.

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


_make_process_dpi_aware()


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
    import dataclasses
    import os
    import threading
    import time
    from pathlib import Path
    from typing import Callable, Optional

    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from imgui_bundle import hello_imgui, imgui
    import psutil

    from launcher_core.crypto import protect_password
    from launcher_core.gw1_launch import LaunchResult, launch_py4gw_profile
    from launcher_core.profile import GameProfile
    from launcher_core.profile_store import load_profiles, save_profiles
    from launcher_core.window_control import (
        find_running_pid_for_exe_path,
        find_visible_window_for_pid,
        foreground_window,
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
        self.sessions: dict[str, LaunchSession] = {}
        self.running_pids: dict[str, int] = {}
        self.selected_id: Optional[str] = None
        self.settings_window_open = False
        self.edit_buffer: Optional[ProfileEditBuffer] = None
        self._last_liveness_check = 0.0
        self.reload_profiles()
        self._rehydrate_running_instances()

    def reload_profiles(self) -> None:
        self.profiles = load_profiles()

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

def draw_profile_card(draw_list, origin, profile: GameProfile, *, card_w: float, card_h: float, hovered: bool, selected: bool, running: bool, launching: bool, status_text: str, is_error: bool) -> None:
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

    icon_center = (x + em * 1.733, y + em * 1.6)
    draw_list.add_circle_filled(icon_center, em * 0.8, _u32(45, 47, 52))

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


def show_main_window() -> None:
    STATE.update()

    imgui.text(f"{len(STATE.profiles)} profile(s) loaded from profile_store.")
    imgui.same_line()
    if imgui.button("Settings"):
        if STATE.selected_id is not None:
            STATE.begin_edit_selected()
        else:
            STATE.settings_window_open = True
    imgui.same_line()
    if imgui.button("Reload profiles"):
        STATE.reload_profiles()

    imgui.separator()
    imgui.spacing()

    card_w, card_h, card_gap = _card_dimensions()
    avail_w = imgui.get_content_region_avail().x
    cols = max(1, int(avail_w // (card_w + card_gap)))

    imgui.begin_child("card_grid", size=(0, 0), child_flags=int(imgui.ChildFlags_.borders.value))
    draw_list = imgui.get_window_draw_list()
    origin = imgui.get_cursor_screen_pos()
    grid_is_hoverable = imgui.is_window_hovered()

    for i, profile in enumerate(STATE.profiles):
        col = i % cols
        row = i // cols
        card_origin = (
            origin.x + col * (card_w + card_gap),
            origin.y + row * (card_h + card_gap),
        )
        p_min = card_origin
        p_max = (card_origin[0] + card_w, card_origin[1] + card_h)

        hovered = grid_is_hoverable and imgui.is_mouse_hovering_rect(p_min, p_max)
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

        draw_profile_card(
            draw_list, card_origin, profile, card_w=card_w, card_h=card_h,
            hovered=hovered, selected=(STATE.selected_id == profile.id),
            running=running, launching=launching or is_error,
            status_text=status_text, is_error=is_error,
        )

    add_index = len(STATE.profiles)
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
        _, buffer.gmod_enabled = imgui.checkbox("Inject gMod", buffer.gmod_enabled)
        _, buffer.gmod_dll_path = imgui.input_text("gMod DLL path", buffer.gmod_dll_path)
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
# Entry point
# -----------------------------------------------------------------------------

def gui() -> None:
    show_main_window()
    show_settings_window()


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

    hello_imgui.run(runner_params)


if __name__ == "__main__":
    main()
