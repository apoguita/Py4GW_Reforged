"""Py4GW_Reforged_Launcher -- real, minimal working launcher window.

Wires the validated UI spike (spikes/spike_ui_multiviewport.py: card-grid main window
+ multi-viewport settings window) to the real profile data layer (launcher_core) and
the real GW1 launch pipeline (launcher_core.gw1_launch). Not a mockup: cards show real
profiles loaded from profile_store, clicking them drives the actual injection
pipeline, and status text reflects the pipeline's real, live progress.

Each card is the entire interaction surface -- no separate buttons per action:
left-click selects a stopped profile or brings a running one to the foreground,
double-click launches a stopped profile, and right-click opens a small context menu
("Edit" for now, room left for more card-level actions later) rather than Settings
directly -- an accidental right-click dismisses a harmless small menu instead of a
whole window that has to be found and dismissed. The "+" card opens Settings for a
new profile. Hovering
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
  unresolved with Apo). This file only checks whether *this launcher's own*
  runtime environment is sane enough to start; it doesn't install anything or
  manage the wider Py4GW dependency chain.

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
    import ctypes.wintypes
    import dataclasses
    import logging
    import logging.handlers
    import math
    import os
    import threading
    import time
    import traceback
    import zlib
    from pathlib import Path
    from typing import Callable, Optional

    sys.path.insert(0, str(Path(__file__).resolve().parent))

    from imgui_bundle import hello_imgui, imgui
    import psutil
    import pywintypes
    import win32api
    import win32con
    import win32gui
    from win32com.shell import shell as win32_shell

    from launcher_core import bulk_launch, config_seeding, legacy_import, mod_repo, prereqs, roster_transfer
    from launcher_core.crypto import protect_password
    from launcher_core.gw1_launch import LaunchResult, launch_py4gw_profile
    from launcher_core.profile import GameProfile
    from launcher_core.profile_store import load_profiles, load_teams, save_profiles, save_teams
    from launcher_core.settings_store import (
        load_bulk_launch_pacing_seconds,
        load_dark_theme_enabled,
        load_mod_repo_path,
        load_mod_repo_url,
        load_multiclient_enabled,
        load_py4gw_injection_enabled,
        save_bulk_launch_pacing_seconds,
        save_dark_theme_enabled,
        save_mod_repo_path,
        save_multiclient_enabled,
        save_py4gw_injection_enabled,
    )
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


_window_icon_applied = False


def _apply_window_icon_if_needed() -> None:
    """hello_imgui.RunnerParams exposes no window-icon option (checked directly --
    app_window_params has no icon field), so this is the fallback: WM_SETICON via
    ctypes once the native window actually exists and is visible.

    Originally wired to callbacks.post_init (one-shot, called "after everything
    is inited: ImGui, Platform and Renderer Backend" per hello_imgui's own docs)
    -- that never actually worked, confirmed via temporary diagnostic logging
    that showed find_visible_window_for_pid() returning None every single time
    at post_init: the native window exists by then but hello_imgui hasn't shown
    it yet (IsWindowVisible() is still False), so a one-shot attempt there can
    never succeed. It failed completely silently, which is exactly why it went
    unnoticed until checked on real hardware.

    Wired to callbacks.pre_new_frame instead, which fires every frame: keeps
    retrying (cheap -- an EnumWindows scan, stopped for good once it succeeds)
    until whichever frame the window actually becomes visible on, with no
    dependency on hello_imgui's exact internal show-window timing.
    """
    global _window_icon_applied
    if _window_icon_applied:
        return
    hwnd = find_visible_window_for_pid(os.getpid())
    if hwnd is not None:
        set_window_icon(hwnd, str(ICON_PATH))
        _window_icon_applied = True


# GWL_WNDPROC (same value as the 64-bit-only GWLP_WNDPROC alias, but this project's
# hard 32-bit requirement -- see the sys.maxsize check above -- means the *_PTR
# Win32 entry points below aren't actually exported: SetWindowLongPtrW/
# GetWindowLongPtrW are #define'd to the plain 32-bit calls in a 32-bit build,
# confirmed directly (hasattr against ctypes.windll.user32 was False for both
# *_PTR names, True for the plain W names), so this uses the 32-bit-native
# SetWindowLongW/GetWindowLongW rather than assuming the wider API exists.
_GWL_WNDPROC = -4
_WM_GETMINMAXINFO = 0x0024


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MINMAXINFO(ctypes.Structure):
    _fields_ = [
        ("pt_reserved", _POINT),
        ("pt_max_size", _POINT),
        ("pt_max_position", _POINT),
        ("pt_min_track_size", _POINT),
        ("pt_max_track_size", _POINT),
    ]


_WNDPROC_TYPE = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.wintypes.HWND, ctypes.c_uint, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
)

_min_window_width_applied = False
_min_window_width_original_wndproc = None
_min_window_width_wndproc_instance: Optional[Callable] = None  # kept alive -- ctypes holds no reference itself
_min_window_width_value = 0.0


def _min_window_width_wndproc(hwnd, msg, wparam, lparam):
    """Replacement window procedure: run the real (GLFW-installed) one first so
    Windows' own default min/max-track-size values get computed as normal, then
    raise ptMinTrackSize.x to our floor if the default was smaller. Only ever
    raises it (never lowers), and only touches .x -- height is deliberately left
    alone, per the "only width needs a floor" requirement.
    """
    result = ctypes.windll.user32.CallWindowProcW(_min_window_width_original_wndproc, hwnd, msg, wparam, lparam)
    if msg == _WM_GETMINMAXINFO:
        info = ctypes.cast(lparam, ctypes.POINTER(_MINMAXINFO)).contents
        if info.pt_min_track_size.x < int(_min_window_width_value):
            info.pt_min_track_size.x = int(_min_window_width_value)
    return result


def _enforce_minimum_window_width_if_needed() -> None:
    """hello_imgui.RunnerParams has no minimum-window-size option either (checked
    directly, same as the window-icon case above: app_window_params and
    window_geometry's full attribute lists have no such field, and a module-wide
    search of hello_imgui for min/constraint/limit-named symbols found nothing),
    so this falls back to native Win32: subclass the window to intercept
    WM_GETMINMAXINFO and enforce a floor on ptMinTrackSize.x.

    The floor is derived from _card_dimensions()'s min_card_w -- the same minimum
    already established for the responsive card grid -- rather than a separate
    hardcoded number, so a future change to the grid's own minimum can't silently
    drift out of sync with this. The margin (card_gap on each side, plus 2em for
    the grid's outer padding) is what a single column actually needs around it to
    render without clipping; see show_main_window()'s own layout math for the same
    padding assumptions.

    Wired to callbacks.pre_new_frame (see _apply_window_icon_if_needed's docstring
    for why post_init doesn't work here): keeps retrying every frame, cheap once
    installed (an EnumWindows scan plus an early-out flag), until the real native
    window exists.
    """
    global _min_window_width_applied, _min_window_width_original_wndproc
    global _min_window_width_wndproc_instance, _min_window_width_value
    if _min_window_width_applied:
        return
    hwnd = find_visible_window_for_pid(os.getpid())
    if hwnd is None:
        return

    min_card_w, _card_h, card_gap = _card_dimensions()
    em = hello_imgui.em_size()
    _min_window_width_value = min_card_w + card_gap * 2.0 + em * 2.0

    _min_window_width_wndproc_instance = _WNDPROC_TYPE(_min_window_width_wndproc)
    _min_window_width_original_wndproc = ctypes.windll.user32.SetWindowLongW(
        hwnd, _GWL_WNDPROC, ctypes.cast(_min_window_width_wndproc_instance, ctypes.c_void_p).value
    )
    _min_window_width_applied = True


# ImGui's default MouseDoubleClickMaxDist is a fixed 6px, calibrated for a
# 96-DPI mouse. The two clicks of a genuine double-click routinely land more
# than 6px apart on a higher-DPI display or a high-precision trackpad, so ImGui
# rejects the pair and the card's double-click-to-launch never fires -- while
# single-click select (which has no distance gate) keeps working, which is the
# tell that clicks register fine and only the double-click *distance* threshold
# is the problem. Widen it, and scale it by em_size() -- the same DPI-aware unit
# every other size in this UI is expressed in -- so it tracks the display's DPI
# instead of being a fixed pixel count that's only right at one scale. 0.8 em is
# ~2x the default 6px at 96 DPI and grows proportionally from there.
_DOUBLE_CLICK_MAX_DIST_EM = 0.8


def _apply_double_click_distance() -> None:
    imgui.get_io().mouse_double_click_max_dist = hello_imgui.em_size() * _DOUBLE_CLICK_MAX_DIST_EM


def _pre_new_frame_hooks() -> None:
    """Combines the one-shot, per-frame-retried setup hooks that need the real
    native window to already exist -- pre_new_frame only accepts a single
    callback, so both live here rather than one silently replacing the other.
    """
    _apply_window_icon_if_needed()
    _enforce_minimum_window_width_if_needed()
    _apply_imgui_style_theme_if_needed()
    # Re-applied every frame on purpose: em_size() changes when the window moves
    # between monitors of different DPI (this process is Per-Monitor-v2 aware),
    # so the threshold must be recomputed rather than set once at startup.
    _apply_double_click_distance()


# -----------------------------------------------------------------------------
# Palette -- ported from the C# reference implementation's Light/Dark palette
# classes, with hover/selected contrast pushed further per an approved design
# direction (hover = full neutral elevation step, selected = accent-tinted bg +
# accent border + solid bar).
# STATUS_* colors (amber/red) aren't part of that 4-state card spec -- they're new,
# needed to satisfy the "honest status text, not a spinner" requirement below.
# Kept identical across both themes (see set_theme()'s docstring for why), so
# they're plain constants, not part of either palette dict below.
#
# CARD_BACK/CARD_SELECTED_BACK/etc. below are reassigned at runtime by
# set_theme() (module-level `global` writes) rather than computed once here --
# every drawing call site references these names directly, so swapping the
# theme is just a matter of pointing them at different values, with no call
# site needing to change. DARK_PALETTE's values are this project's original,
# already-approved dark theme, unchanged from before the light theme existed.
# LIGHT_PALETTE's are ported from the C# reference's own LightPalette.cs
# (GWxLauncher/UI/LightPalette.cs), mapped onto this project's existing
# constant names (e.g. CardBack -> CARD_BACK, HoverBack -> HOVER_BACK).
# -----------------------------------------------------------------------------

def _u32(r: int, g: int, b: int, a: int = 255) -> int:
    return imgui.color_convert_float4_to_u32((r / 255.0, g / 255.0, b / 255.0, a / 255.0))


DARK_PALETTE = {
    "CARD_BACK": (32, 32, 38),
    "CARD_SELECTED_BACK": (28, 40, 58),
    "HOVER_BACK": (48, 48, 56),
    "CARD_BORDER": (55, 55, 65),
    "HOVER_BORDER": (90, 90, 105),
    "MUTED_FORE": (110, 110, 122),
    "ACCENT": (0, 120, 215),
    "CARD_NAME_FORE": (255, 255, 255),
    "CARD_SUB_FORE": (170, 170, 185),
    "BADGE_BACK": (50, 50, 65),
    "BADGE_BORDER": (75, 75, 95),
    "BADGE_FORE": (210, 210, 220),
}

# Ported from GWxLauncher/UI/LightPalette.cs. Not every DARK_PALETTE key has an
# obvious LightPalette equivalent -- none needed one here, every key below maps
# directly onto a real LightPalette.cs property.
LIGHT_PALETTE = {
    "CARD_BACK": (255, 255, 255),  # LightPalette.CardBack (White)
    "CARD_SELECTED_BACK": (235, 242, 255),  # CardSelectedBack
    "HOVER_BACK": (248, 250, 255),  # HoverBack
    "CARD_BORDER": (185, 185, 205),  # CardBorder
    "HOVER_BORDER": (160, 175, 210),  # HoverBorder
    "MUTED_FORE": (90, 95, 115),  # SubtleFore -- closest conceptual match to MUTED_FORE
    "ACCENT": (0, 105, 210),  # Accent
    "CARD_NAME_FORE": (0, 0, 0),  # CardNameFore (Black)
    "CARD_SUB_FORE": (85, 85, 105),  # CardSubFore
    "BADGE_BACK": (230, 235, 245),  # BadgeBack
    "BADGE_BORDER": (200, 205, 220),  # BadgeBorder
    "BADGE_FORE": (60, 65, 85),  # BadgeFore
}

# Declared here so the names exist at module scope before set_theme() (called
# once below, and again later whenever the user toggles the theme) assigns
# their real values via `global`.
CARD_BACK = 0
CARD_SELECTED_BACK = 0
HOVER_BACK = 0
CARD_BORDER = 0
HOVER_BORDER = 0
MUTED_FORE = 0
ACCENT = 0
CARD_NAME_FORE = 0
CARD_SUB_FORE = 0
BADGE_BACK = 0
BADGE_BORDER = 0
BADGE_FORE = 0

STATUS_PROGRESS = _u32(230, 180, 80)
STATUS_ERROR = _u32(220, 90, 90)


# hello_imgui ships a set of built-in, purpose-designed ImGuiCol_* theme
# presets (hello_imgui.ImGuiTheme_) -- confirmed directly (dir() on the
# module, then hello_imgui.imgui_theme_name() against every member) rather
# than hand-authoring a full style table from scratch. "DarculaDarker" is
# the exact preset already in effect today (confirmed against this
# project's own persisted Py4GW_Reforged_Launcher.ini, [Theme] Name=
# DarculaDarker) even though no code here ever explicitly requested it --
# it's hello_imgui's own default -- so using it explicitly for the dark
# case reproduces today's actual look exactly, not just "a" dark theme.
# "GrayVariations" is a neutral-grey light preset. "LightRounded" and the near-
# identical "ImGuiColorsLight" (Dear ImGui's stock light palette) were tried first
# but make every interactive widget -- buttons, checkbox fills, checkmarks -- a
# saturated blue at rest, so the whole of Settings/App Settings read as permanently
# "selected". GrayVariations keeps those neutral grey, matching how the dark preset
# (DarculaDarker) reads, and its grey chrome still gives buttons/checkmarks enough
# contrast against the light window background (verified visually).
_DARK_IMGUI_THEME = "DarculaDarker"
_LIGHT_IMGUI_THEME = "GrayVariations"

# apply_theme() needs a live ImGui context -- confirmed directly (raises
# IM_ASSERT "No current context" when called before one exists) -- but
# set_theme() is first called at plain module-import time, well before
# hello_imgui.run() ever creates one. Same problem _apply_window_icon_if_needed
# solves for a different resource (the native window handle) that also isn't
# ready yet at that point: retry once per frame via _pre_new_frame_hooks until
# it succeeds, then stop. _current_theme_is_dark records what set_theme() was
# last actually asked for, so the retry (which doesn't get a `dark` argument
# of its own) knows which preset to (re)try applying.
_current_theme_is_dark = True
_theme_imgui_style_applied = False


def _apply_imgui_style_theme() -> None:
    """Actually applies whichever theme set_theme() was last asked for --
    this is the part that needs a live ImGui context and a running
    hello_imgui app (see module comment above); the CARD_*-style custom
    palette reassignment in set_theme() itself has no such requirement and
    always runs immediately.

    hello_imgui.imgui_theme_from_name() expects its own display-name spelling
    ("DarculaDarker", "LightRounded" -- see _DARK_IMGUI_THEME/_LIGHT_IMGUI_THEME
    above), not the ImGuiTheme_ enum member's Python spelling
    ("darcula_darker"); passing the wrong spelling doesn't raise, it silently
    resolves to ImGuiColorsClassic, which was the actual cause of an earlier
    version of this function visually doing nothing. Also update
    RunnerParams.imgui_window_params.tweaked_theme (replacing the whole
    ImGuiTweakedTheme, not mutating its .theme field in place -- confirmed
    in-place mutation alone doesn't stick) so hello_imgui's own internal
    per-frame processing, which re-applies this stored theme choice every
    frame, doesn't overwrite the apply_theme() call below on the very next
    frame.
    """
    global _theme_imgui_style_applied
    theme_name = _DARK_IMGUI_THEME if _current_theme_is_dark else _LIGHT_IMGUI_THEME
    try:
        theme = hello_imgui.imgui_theme_from_name(theme_name)
        runner_params = hello_imgui.get_runner_params()
        imgui_window_params = runner_params.imgui_window_params
        imgui_window_params.tweaked_theme = hello_imgui.ImGuiTweakedTheme(theme=theme)
        runner_params.imgui_window_params = imgui_window_params
        hello_imgui.apply_theme(theme)
        _theme_imgui_style_applied = True
    except RuntimeError:
        _theme_imgui_style_applied = False


def _apply_imgui_style_theme_if_needed() -> None:
    """Wired into _pre_new_frame_hooks -- retries _apply_imgui_style_theme
    every frame until it succeeds (the first real frame, once hello_imgui's
    ImGui context actually exists), then becomes a no-op for the rest of
    the run. Any later set_theme() call (the user toggling App Settings'
    checkbox, well after startup) applies immediately on its own and sets
    _theme_imgui_style_applied True itself, so this never re-fires then.
    """
    if _theme_imgui_style_applied:
        return
    _apply_imgui_style_theme()


def set_theme(dark: bool) -> None:
    """Reassigns every palette constant above from DARK_PALETTE or
    LIGHT_PALETTE, and applies the corresponding built-in hello_imgui
    ImGuiCol_* theme preset (see _DARK_IMGUI_THEME/_LIGHT_IMGUI_THEME above)
    -- called once at startup with the persisted preference, and again
    immediately whenever the user toggles the App Settings theme switch, so
    every existing drawing call site (which reference e.g. CARD_BACK
    directly, not through a lookup) *and* every real ImGui widget/window
    (buttons, checkboxes, text inputs, window/titlebar backgrounds --
    previously untouched by this toggle, since this codebase never once set
    imgui.get_style().colors anywhere) pick up the new colors together, with
    no call site needing to change.

    STATUS_PROGRESS/STATUS_ERROR and the avatar hue palette
    (_AVATAR_HUES_DEG etc.) are deliberately NOT reassigned here -- neither
    has an obvious LightPalette.cs equivalent, and both still read fine
    against a light background (amber/red status text and a fixed set of
    saturated avatar hues don't get confusing or illegible just because the
    surrounding chrome flipped light), so forcing a mapping that doesn't
    exist isn't worth it.
    """
    global CARD_BACK, CARD_SELECTED_BACK, HOVER_BACK, CARD_BORDER, HOVER_BORDER
    global MUTED_FORE, ACCENT, CARD_NAME_FORE, CARD_SUB_FORE, BADGE_BACK, BADGE_BORDER, BADGE_FORE
    global _current_theme_is_dark

    palette = DARK_PALETTE if dark else LIGHT_PALETTE
    CARD_BACK = _u32(*palette["CARD_BACK"])
    CARD_SELECTED_BACK = _u32(*palette["CARD_SELECTED_BACK"])
    HOVER_BACK = _u32(*palette["HOVER_BACK"])
    CARD_BORDER = _u32(*palette["CARD_BORDER"])
    HOVER_BORDER = _u32(*palette["HOVER_BORDER"])
    MUTED_FORE = _u32(*palette["MUTED_FORE"])
    ACCENT = _u32(*palette["ACCENT"])
    CARD_NAME_FORE = _u32(*palette["CARD_NAME_FORE"])
    CARD_SUB_FORE = _u32(*palette["CARD_SUB_FORE"])
    BADGE_BACK = _u32(*palette["BADGE_BACK"])
    BADGE_BORDER = _u32(*palette["BADGE_BORDER"])
    BADGE_FORE = _u32(*palette["BADGE_FORE"])

    _current_theme_is_dark = dark
    _apply_imgui_style_theme()


_dark_theme_enabled = load_dark_theme_enabled()
set_theme(dark=_dark_theme_enabled)


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


def _max_card_w_for_columns(cols: int, min_card_w: float, avail_w: float) -> float:
    """The soft ceiling on how wide a card can stretch, scaled by how many
    columns are actually in play rather than a flat multiplier regardless of
    layout. A single column has no neighbor to look oversized next to --
    there's no real cost to it filling essentially the whole row -- so it
    gets no ceiling at all. More columns means an overly-wide card reads
    worse sitting next to others, so the ceiling tightens as column count
    grows: 1.6x at 2 columns (the original, already-approved multiplier),
    1.3x at 3 or more.

    Confirmed the problem directly before writing this rather than guessing
    a bigger multiplier: at a real 532x430 window (single column, 2 real
    profiles), the flat 1.6x ceiling capped card_w well short of the
    available width, leaving a visibly large, pointless gap between the
    lone card and the scrollbar.
    """
    if cols <= 1:
        return avail_w
    if cols == 2:
        return min_card_w * 1.6
    return min_card_w * 1.3


def _grid_columns_and_card_width(avail_w: float, min_card_w: float, card_gap: float) -> tuple[int, float]:
    """How many columns fit at the floor width, and the actual (stretched,
    capped -- see _max_card_w_for_columns) card width for that column count.
    Pulled out of show_main_window so it can be called twice in one frame:
    once against the full available width, and again against a
    scrollbar-reduced width if one turns out to be needed (see
    show_main_window's scrollbar pre-check).
    """
    cols = max(1, int(avail_w // (min_card_w + card_gap)))
    max_card_w = _max_card_w_for_columns(cols, min_card_w, avail_w)
    card_w = max(min_card_w, min(max_card_w, (avail_w - (cols - 1) * card_gap) / cols))
    return cols, card_w


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
# launcher.log / launcher_errors.log -- shared by _log_launch_attempt below and
# _log_prereq_ui_error further down. Previously both wrote everything (launch
# attempts *and* UI errors, success or failure alike) to one file named
# "launcher_errors.log" -- a misleading name (it captured every launch, not
# just errors) with no easy way to see just what went wrong. Now one logger
# feeds two RotatingFileHandlers: launcher.log gets everything (INFO+, the
# full picture -- what this file used to be called, before the rename), and
# launcher_errors.log is filtered to WARNING+ only, so it's genuinely
# errors-only. Each call site's logging *level* is what actually routes a
# given message to the errors file or not -- see _log_launch_attempt and
# _log_prereq_ui_error for which level each uses and why. maxBytes=5MB/
# backupCount=3 per file (so up to ~20MB each) is a reasonable starting
# point, not a tuned figure from real observed log volume. A bare
# "%(message)s" formatter (no logging-added timestamp/level prefix) keeps the
# on-disk text the same shape as before -- both call sites still build their
# own timestamped, multi-line message text and hand the whole thing to the
# logger as a single record.
# -----------------------------------------------------------------------------

_error_logger = logging.getLogger("py4gw_launcher_errors")
_error_logger.setLevel(logging.INFO)
_error_logger.propagate = False
try:
    _log_dir = Path(os.environ.get("APPDATA", ".")) / config_seeding.APPDATA_SUBDIR
    _log_dir.mkdir(parents=True, exist_ok=True)

    _main_log_handler = logging.handlers.RotatingFileHandler(
        _log_dir / "launcher.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _main_log_handler.setFormatter(logging.Formatter("%(message)s"))
    _error_logger.addHandler(_main_log_handler)

    _errors_only_log_handler = logging.handlers.RotatingFileHandler(
        _log_dir / "launcher_errors.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    _errors_only_log_handler.setLevel(logging.WARNING)
    _errors_only_log_handler.setFormatter(logging.Formatter("%(message)s"))
    _error_logger.addHandler(_errors_only_log_handler)
except OSError:
    pass


def _log_launch_attempt(profile: GameProfile, result: LaunchResult) -> None:
    """Persists the full per-launch log (every step -- process creation, the
    multiclient patch's success/address or specific failure reason,
    injection, window-wait -- not just the single top-line status string
    LaunchSession otherwise shows) to launcher.log. LaunchResult.log was
    previously discarded the moment _run() finished, leaving nothing to
    diagnose a failed launch after the fact. Written for every launch
    attempt, success or failure, so e.g. a working launch and a failing one
    from the same session can be diffed side by side rather than only ever
    having a log for the failure.

    Logged at WARNING when the launch failed (so it also lands in the
    WARNING+-filtered launcher_errors.log) and INFO when it succeeded (so a
    normal, working launch only ever shows up in the full launcher.log, not
    the errors-only one).
    """
    lines = [
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} [launch] "
        f"profile={profile.name or '(unnamed profile)'!r} "
        f"success={result.success} error={result.error!r}"
    ]
    lines.extend(f"    {line}" for line in result.log)
    level = logging.INFO if result.success else logging.WARNING
    try:
        _error_logger.log(level, "\n".join(lines))
    except OSError:
        pass


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
        result = launch_py4gw_profile(
            self.profile,
            multiclient_enabled=STATE.multiclient_enabled,
            py4gw_injection_enabled=STATE.py4gw_injection_enabled,
            on_log=self._on_log,
        )
        _log_launch_attempt(self.profile, result)
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
# PrereqState: runs launcher_core.prereqs' Python/VC++/DirectX-runtime checks
# (and any install a user requests) on a background thread, same thread-safe
# status pattern as LaunchSession/BulkLaunchSession above -- never call ImGui
# from the background thread, only plain state mutation the UI thread polls.
# Checks are re-run fresh every time (on app start, after any install
# finishes, and whenever the user clicks "Check now") rather than cached --
# see launcher_core.prereqs' module docstring for why that's fine (a cheap
# subprocess/registry/filesystem check, not worth staleness-tracking
# complexity).
#
# A DirectX *SDK* check was considered and deliberately left out -- see
# launcher_core.prereqs' module docstring for why (verified directly against
# Py4GW_Reforged_Native's own CMakeLists.txt: no D3DX linkage anywhere, only
# standard Windows-SDK d3d9/d3dcompiler, so the legacy DXSDK isn't needed).
# The DirectX End-User *Runtime* below is a different, real requirement --
# confirmed necessary by Apo directly.
# -----------------------------------------------------------------------------

class PrereqState:
    def __init__(self):
        self._lock = threading.Lock()
        self.python_result: Optional[prereqs.PythonPrereqResult] = None
        self.vcredist_result: Optional[prereqs.VcRedistResult] = None
        self.directx_runtime_result: Optional[prereqs.DirectXRuntimeResult] = None
        self._checking = False
        self._install_in_progress: Optional[str] = None
        self._install_status_text = ""
        self._install_done_message: Optional[str] = None

    def run_check_async(self) -> None:
        if self._checking:
            return
        self._checking = True
        threading.Thread(target=self._check_all, daemon=True).start()

    def _check_all(self) -> None:
        python_result = prereqs.check_python_prereq()
        vcredist_result = prereqs.check_vcredist_prereq()
        directx_runtime_result = prereqs.check_directx_runtime_prereq()
        with self._lock:
            self.python_result = python_result
            self.vcredist_result = vcredist_result
            self.directx_runtime_result = directx_runtime_result
            self._checking = False

    def start_install(self, component: str) -> None:
        """component is "python", "vcredist_x86", "vcredist_x64", or
        "directx_runtime"."""
        if self._install_in_progress is not None:
            return
        self._install_in_progress = component
        self._install_done_message = None
        threading.Thread(target=self._run_install, args=(component,), daemon=True).start()

    def _set_install_status(self, text: str) -> None:
        with self._lock:
            self._install_status_text = text

    def _run_install(self, component: str) -> None:
        if component == "python":
            success, message = prereqs.download_and_install_python(self._set_install_status)
        elif component == "vcredist_x86":
            success, message = prereqs.download_and_install_vcredist("x86", self._set_install_status)
        elif component == "vcredist_x64":
            success, message = prereqs.download_and_install_vcredist("x64", self._set_install_status)
        elif component == "directx_runtime":
            success, message = prereqs.download_and_install_directx_runtime(self._set_install_status)
        else:
            success, message = False, "Unknown component"

        with self._lock:
            self._install_done_message = message
            self._install_in_progress = None
        # No restart (of the OS or this app) needed to see the result -- see
        # prereqs.refresh_env_from_registry's docstring for why -- so just
        # re-run every check now that something may have changed.
        self.run_check_async()

    @property
    def checking(self) -> bool:
        with self._lock:
            return self._checking

    @property
    def install_in_progress(self) -> Optional[str]:
        with self._lock:
            return self._install_in_progress

    @property
    def install_status_text(self) -> str:
        with self._lock:
            return self._install_status_text

    @property
    def install_done_message(self) -> Optional[str]:
        with self._lock:
            return self._install_done_message

    def all_ok(self) -> Optional[bool]:
        """None while any result is still unavailable (still checking on
        this frame -- don't show anything yet, badge or popup). True only if
        every prerequisite reports OK; False otherwise. Read by the gear-icon
        badge (show_settings_gear_button) and the launch-confirm gate
        (_try_launch_with_prereq_gate) -- both need the exact same tri-state
        logic, so it lives here once rather than being reimplemented twice.
        """
        if self.python_result is None or self.vcredist_result is None or self.directx_runtime_result is None:
            return None
        return self.python_result.is_ok and self.vcredist_result.is_ok and self.directx_runtime_result.is_ok

    def missing_names(self) -> list[str]:
        """Human-readable names of whichever prerequisites currently aren't
        OK -- same labels shown in the App Settings rows -- for the
        launch-confirm gate's message. Empty if still checking or everything
        checks out.
        """
        names: list[str] = []
        if self.python_result is not None and not self.python_result.is_ok:
            names.append("Python 3.13.0 (32-bit)")
        if self.vcredist_result is not None:
            if self.vcredist_result.x86_status != prereqs.VcRedistStatus.OK:
                names.append("VC++ Redistributable (x86)")
            if self.vcredist_result.x64_status != prereqs.VcRedistStatus.OK:
                names.append("VC++ Redistributable (x64)")
        if self.directx_runtime_result is not None and not self.directx_runtime_result.is_ok:
            names.append("DirectX End-User Runtime")
        return names


# -----------------------------------------------------------------------------
# ModRepoState: detection/clone/update-check for the actual Py4GW_Reforged mod
# checkout (launcher_core.mod_repo) -- a different concern from PrereqState above
# ("is the right software installed") and from config_seeding ("do the right
# config files exist"): this is "does the mod's actual code exist, and is it
# current." Same thread-safe status pattern as PrereqState/LaunchSession: real
# work (clone, fetch) runs on a background thread via dulwich, the UI thread only
# ever polls plain attributes/properties, never calls into dulwich directly.
# -----------------------------------------------------------------------------

class ModRepoState:
    def __init__(self):
        self._lock = threading.Lock()
        saved_path = load_mod_repo_path()
        # No saved override yet -- default to config_seeding's own mod-root
        # assumption (this launcher's own parent directory) rather than
        # duplicating that path logic here, per the task that added this.
        self.configured_path: Path = Path(saved_path) if saved_path else config_seeding._mod_root()
        self.detection: Optional[mod_repo.CheckoutDetectionResult] = None
        self.update_check: Optional[mod_repo.UpdateCheckResult] = None
        self._detecting = False
        self._checking_updates = False
        self._clone_in_progress = False
        self._update_in_progress = False
        self._operation_status_text = ""
        self._operation_done_message: Optional[str] = None

    def set_configured_path(self, path: str) -> None:
        """Persists the new location and re-detects against it -- any
        earlier update-check result was about the *old* location, so it's
        cleared rather than left showing a stale answer for a path that's no
        longer the one in effect.
        """
        self.configured_path = Path(path)
        save_mod_repo_path(path)
        self.update_check = None
        self.run_detect_async()

    def run_detect_async(self) -> None:
        """Cheap, filesystem-only -- safe to fire on every relevant state
        change (startup, path change, after a clone/update finishes), same
        as PrereqState's own local checks."""
        if self._detecting:
            return
        self._detecting = True
        threading.Thread(target=self._detect, daemon=True).start()

    def _detect(self) -> None:
        result = mod_repo.detect_checkout(self.configured_path)
        with self._lock:
            self.detection = result
            self._detecting = False

    def run_check_updates_async(self) -> None:
        """Unlike detection, this hits the network (a real git fetch) --
        never run automatically, only from an explicit "Check for updates"
        click, same reasoning PrereqState does NOT apply to its own local
        checks (those are cheap enough to always re-run; this isn't)."""
        if self._checking_updates:
            return
        self._checking_updates = True
        threading.Thread(target=self._check_updates, daemon=True).start()

    def _check_updates(self) -> None:
        result = mod_repo.check_for_updates(self.configured_path)
        with self._lock:
            self.update_check = result
            self._checking_updates = False

    def start_clone(self) -> None:
        if self._clone_in_progress:
            return
        self._clone_in_progress = True
        self._operation_done_message = None
        threading.Thread(target=self._run_clone, daemon=True).start()

    def _run_clone(self) -> None:
        _success, message = mod_repo.clone_mod_repo(self.configured_path, self._set_operation_status)
        with self._lock:
            self._operation_done_message = message
            self._clone_in_progress = False
        self.run_detect_async()

    def start_update(self) -> None:
        if self._update_in_progress:
            return
        self._update_in_progress = True
        self._operation_done_message = None
        threading.Thread(target=self._run_update, daemon=True).start()

    def _run_update(self) -> None:
        _success, message = mod_repo.update_mod_repo(self.configured_path, self._set_operation_status)
        with self._lock:
            self._operation_done_message = message
            self._update_in_progress = False
        self.run_detect_async()
        self.run_check_updates_async()

    def _set_operation_status(self, text: str) -> None:
        with self._lock:
            self._operation_status_text = text

    @property
    def detecting(self) -> bool:
        with self._lock:
            return self._detecting

    @property
    def checking_updates(self) -> bool:
        with self._lock:
            return self._checking_updates

    @property
    def clone_in_progress(self) -> bool:
        with self._lock:
            return self._clone_in_progress

    @property
    def update_in_progress(self) -> bool:
        with self._lock:
            return self._update_in_progress

    @property
    def operation_status_text(self) -> str:
        with self._lock:
            return self._operation_status_text

    @property
    def operation_done_message(self) -> Optional[str]:
        with self._lock:
            return self._operation_done_message


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
    auto_select_character_enabled: bool = False
    character_name: str = ""
    py4gw_enabled: bool = False
    py4gw_dll_path: str = ""
    gmod_enabled: bool = False
    gmod_dll_path: str = ""
    windowed_mode_enabled: bool = True
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
            auto_select_character_enabled=profile.auto_select_character_enabled,
            character_name=profile.character_name,
            py4gw_enabled=profile.py4gw_enabled,
            py4gw_dll_path=profile.py4gw_dll_path,
            gmod_enabled=profile.gmod_enabled,
            gmod_dll_path=profile.gmod_dll_path,
            windowed_mode_enabled=profile.windowed_mode_enabled,
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
        self.multiclient_enabled: bool = load_multiclient_enabled()
        self.py4gw_injection_enabled: bool = load_py4gw_injection_enabled()
        self.name_filter: str = ""
        # Ephemeral (never persisted): which ALL-view cards are batch-checked for
        # "Add N to Team". Cleared on leaving ALL -- see jump_to_view.
        self.batch_selected_ids: set[str] = set()
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

    def jump_to_view(self, team_id: Optional[str]) -> None:
        # Batch checkboxes only exist on ALL, so a selection made there shouldn't
        # linger invisibly once the view actually leaves ALL for a team.
        if self.current_team_id is None and team_id is not None:
            self.batch_selected_ids.clear()
        self.current_team_id = team_id

    def create_team(self, name: str) -> Team:
        """Create a team on the fly (typed into the switcher's popup, no separate
        "manage teams" screen) and switch straight to viewing it."""
        team = Team(name=name)
        self.teams.append(team)
        save_teams(self.teams)
        self.current_team_id = team.id
        return team

    def duplicate_team(self, team_id: str) -> Optional[Team]:
        """Copy a team: a new "<name> copy" team whose membership matches the
        source's, then switch to viewing it (same as create_team) so the copy is
        immediately visible and renameable. Independent of the source -- profiles
        gain the new team's id alongside the original's, so renaming or deleting
        either team later never touches the other. Mirrors delete_team's
        loop-and-single-save shape.
        """
        source = next((t for t in self.teams if t.id == team_id), None)
        if source is None:
            return None
        new_team = Team(name=f"{source.name} copy")
        self.teams.append(new_team)
        save_teams(self.teams)

        changed = False
        for profile in self.profiles:
            if team_id in profile.team_ids:
                profile.team_ids.append(new_team.id)
                changed = True
        if changed:
            save_profiles(self.profiles)

        self.current_team_id = new_team.id
        return new_team

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

    def delete_profile(self, profile_id: str) -> None:
        """Remove a profile and save once. No team cleanup needed -- team_ids lives
        on the profile itself, so deleting the profile removes its memberships with
        it (unlike delete_team, which has to scrub the other side of that relation
        off every profile)."""
        self.profiles = [p for p in self.profiles if p.id != profile_id]
        if self.selected_id == profile_id:
            self.selected_id = None
        save_profiles(self.profiles)

    def add_profiles_to_team(self, profile_ids: set[str], team_id: str) -> None:
        """Append team_id to each listed profile's team_ids (skipping any already
        in it), saving once at the end if anything changed -- the same single-save
        shape delete_team uses, not a save per profile."""
        changed = False
        for profile in self.profiles:
            if profile.id in profile_ids and team_id not in profile.team_ids:
                profile.team_ids.append(team_id)
                changed = True
        if changed:
            save_profiles(self.profiles)

    def toggle_team_membership(self, profile: GameProfile, team_id: str) -> None:
        """Toggle `profile`'s membership in `team_id` and save immediately -- the
        card's right-click "Teams" submenu has no separate "Save" step, unlike
        the Settings form."""
        if team_id in profile.team_ids:
            profile.team_ids.remove(team_id)
        else:
            profile.team_ids.append(team_id)
        save_profiles(self.profiles)

    def export_roster(self, path, *, include_passwords: bool = True) -> None:
        roster_transfer.export_roster(self.profiles, self.teams, path, include_passwords=include_passwords)

    def import_roster(self, path) -> "roster_transfer.RosterImportResult":
        """Load a roster bundle, appending only profiles/teams whose id isn't
        already present locally (de-dupe by id, not a data merge -- re-importing the
        same file, or importing onto a machine that already has some of these,
        mustn't create id collisions or duplicates). Saves once each if anything was
        added, and reports which newly-added profiles reference paths missing here.
        """
        imported_profiles, imported_teams = roster_transfer.import_roster(path)

        existing_profile_ids = {p.id for p in self.profiles}
        existing_team_ids = {t.id for t in self.teams}

        added_profiles = []
        skipped_profiles = 0
        for profile in imported_profiles:
            if profile.id in existing_profile_ids:
                skipped_profiles += 1
            else:
                existing_profile_ids.add(profile.id)  # also guards dup ids within the bundle
                self.profiles.append(profile)
                added_profiles.append(profile)

        added_teams = 0
        skipped_teams = 0
        for team in imported_teams:
            if team.id in existing_team_ids:
                skipped_teams += 1
            else:
                existing_team_ids.add(team.id)
                self.teams.append(team)
                added_teams += 1

        if added_profiles:
            save_profiles(self.profiles)
        if added_teams:
            save_teams(self.teams)

        return roster_transfer.RosterImportResult(
            added_profiles=len(added_profiles),
            added_teams=added_teams,
            skipped_profiles=skipped_profiles,
            skipped_teams=skipped_teams,
            path_warnings=roster_transfer.find_missing_paths(added_profiles),
        )

    def import_legacy_accounts(self, path) -> "roster_transfer.RosterImportResult":
        """Import the old Py4GW_Launcher.py accounts.json format (see legacy_import).

        De-dupes differently from the native roster import (which matches by id --
        legacy files carry no ids): teams match by name (reusing the existing team's
        id for imported profiles rather than creating a duplicate), and profiles match
        by email when non-empty, else by (executable_path, character_name). Matches are
        skipped, not merged. Saves once each if anything was added, and reuses
        roster_transfer.find_missing_paths for the same post-import path warnings the
        native import surfaces.
        """
        imported_profiles, imported_teams, warnings = legacy_import.parse_legacy_accounts(path)

        # Teams: match by name; reuse the existing id, remap imported profiles onto it.
        existing_team_by_name = {t.name: t for t in self.teams}
        team_id_remap: dict[str, str] = {}
        added_teams = 0
        skipped_teams = 0
        for team in imported_teams:
            existing = existing_team_by_name.get(team.name)
            if existing is not None:
                team_id_remap[team.id] = existing.id
                skipped_teams += 1
            else:
                self.teams.append(team)
                existing_team_by_name[team.name] = team
                team_id_remap[team.id] = team.id
                added_teams += 1
        for profile in imported_profiles:
            profile.team_ids = [team_id_remap.get(tid, tid) for tid in profile.team_ids]

        # Profiles: dedup by email when present, else by (executable_path, character_name).
        def _profile_key(p: GameProfile):
            if p.email:
                return ("email", p.email)
            return ("exe_char", p.executable_path, p.character_name)

        existing_keys = {_profile_key(p) for p in self.profiles}
        added_profiles = []
        skipped_profiles = 0
        for profile in imported_profiles:
            key = _profile_key(profile)
            if key in existing_keys:
                skipped_profiles += 1
            else:
                existing_keys.add(key)  # also guards duplicates within the same file
                self.profiles.append(profile)
                added_profiles.append(profile)

        if added_profiles:
            save_profiles(self.profiles)
        if added_teams:
            save_teams(self.teams)

        return roster_transfer.RosterImportResult(
            added_profiles=len(added_profiles),
            added_teams=added_teams,
            skipped_profiles=skipped_profiles,
            skipped_teams=skipped_teams,
            path_warnings=roster_transfer.find_missing_paths(added_profiles),
            warnings=warnings,
        )

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
            or buffer.auto_select_character_enabled != baseline.auto_select_character_enabled
            or buffer.character_name != baseline.character_name
            or buffer.py4gw_enabled != baseline.py4gw_enabled
            or buffer.py4gw_dll_path != baseline.py4gw_dll_path
            or buffer.gmod_enabled != baseline.gmod_enabled
            or buffer.gmod_dll_path != baseline.gmod_dll_path
            or buffer.windowed_mode_enabled != baseline.windowed_mode_enabled
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
        profile.auto_select_character_enabled = buffer.auto_select_character_enabled
        profile.character_name = buffer.character_name
        profile.py4gw_enabled = buffer.py4gw_enabled
        profile.py4gw_dll_path = buffer.py4gw_dll_path
        profile.gmod_enabled = buffer.gmod_enabled
        profile.gmod_dll_path = buffer.gmod_dll_path
        profile.windowed_mode_enabled = buffer.windowed_mode_enabled
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

    def set_multiclient_enabled(self, enabled: bool) -> None:
        self.multiclient_enabled = enabled
        save_multiclient_enabled(enabled)

    def set_py4gw_injection_enabled(self, enabled: bool) -> None:
        self.py4gw_injection_enabled = enabled
        save_py4gw_injection_enabled(enabled)

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
PREREQS = PrereqState()
PREREQS.run_check_async()
MOD_REPO_STATE = ModRepoState()
MOD_REPO_STATE.run_detect_async()

try:
    # Independent of the prereqs above (config files, not software installs)
    # -- see config_seeding's own module docstring for exactly what this
    # does and doesn't handle. Best-effort: a seeding hiccup shouldn't be
    # fatal to starting the app.
    CONFIG_SEED_RESULTS = config_seeding.seed_default_configs()
except OSError:
    CONFIG_SEED_RESULTS = []


# -----------------------------------------------------------------------------
# Card grid (main window content)
# -----------------------------------------------------------------------------

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


def batch_checkbox_rect(card_origin, card_h: float, em: float) -> tuple[tuple[float, float], tuple[float, float]]:
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


_CHECKMARK_COLOR = _u32(255, 255, 255)


def _draw_batch_checkbox(draw_list, min_pt, max_pt, *, checked: bool, hovered: bool) -> None:
    """The card's batch-select box (ALL view only) -- its own small click target,
    kept separate from the rest of the card; show_main_window excludes this rect
    from the card's own hover/click handling so the two interactions can't collide.
    Checked reads as a solid ACCENT box with a white checkmark, clearly visible at
    a glance; unchecked stays a thin outline.
    """
    if checked:
        draw_list.add_rect_filled(min_pt, max_pt, ACCENT, rounding=3.0)
        w = max_pt[0] - min_pt[0]
        h = max_pt[1] - min_pt[1]
        thickness = max(1.5, w * 0.12)
        p1 = (min_pt[0] + w * 0.22, min_pt[1] + h * 0.52)
        p2 = (min_pt[0] + w * 0.42, min_pt[1] + h * 0.72)
        p3 = (min_pt[0] + w * 0.78, min_pt[1] + h * 0.30)
        draw_list.add_line(p1, p2, _CHECKMARK_COLOR, thickness=thickness)
        draw_list.add_line(p2, p3, _CHECKMARK_COLOR, thickness=thickness)
    else:
        border = ACCENT if hovered else CARD_BORDER
        draw_list.add_rect(min_pt, max_pt, border, rounding=3.0, thickness=1.5)


def draw_profile_card(draw_list, origin, profile: GameProfile, *, card_w: float, card_h: float, hovered: bool, selected: bool, running: bool, launching: bool, status_text: str, is_error: bool, show_batch_checkbox: bool = False, batch_checked: bool = False, checkbox_hovered: bool = False) -> None:
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
        # Same condition gw1_launch._build_auto_login_args uses to decide
        # whether -character is actually passed -- don't show a name here
        # that won't actually be auto-selected.
        if profile.auto_select_character_enabled and profile.character_name:
            sub_text = profile.character_name
        else:
            sub_text = "Ready to launch"
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

    if show_batch_checkbox:
        checkbox_min, checkbox_max = batch_checkbox_rect((x, y), card_h, em)
        _draw_batch_checkbox(draw_list, checkbox_min, checkbox_max, checked=batch_checked, hovered=checkbox_hovered)


def draw_add_card(draw_list, origin, *, card_w: float, card_h: float, hovered: bool) -> None:
    """The "+" card: same size/shape as a profile card, consistent visual language,
    but a dashed-feeling outline (achieved with the hover border color at rest) and
    a plain "+" instead of icon/name/badges, so it doesn't read as a real profile.
    Deliberately quiet at rest (muted color, smaller glyph) -- it's the
    least-used action in the app and shouldn't compete with real accounts for
    attention; hover still brightens to full ACCENT, unchanged.
    """
    em = hello_imgui.em_size()
    x, y = origin
    p_min = (x, y)
    p_max = (x + card_w, y + card_h)

    bg = HOVER_BACK if hovered else CARD_BACK
    border = ACCENT if hovered else CARD_BORDER
    draw_list.add_rect_filled(p_min, p_max, bg, rounding=6.0)
    draw_list.add_rect(p_min, p_max, border, rounding=6.0, thickness=1.0)

    plus_col = ACCENT if hovered else MUTED_FORE
    cx, cy = x + card_w / 2, y + card_h / 2
    arm = em * 0.5
    draw_list.add_line((cx - arm, cy), (cx + arm, cy), plus_col, thickness=1.5)
    draw_list.add_line((cx, cy - arm), (cx, cy + arm), plus_col, thickness=1.5)
    text = "Add profile"
    text_w = imgui.calc_text_size(text).x
    draw_list.add_text((cx - text_w / 2, y + card_h - em * 1.467), plus_col, text)


_TEAM_OVERFLOW_POPUP_ID = "Jump to view##team_switcher_popup"
_NEW_TEAM_POPUP_ID = "New team##tab_strip_new_team_popup"
_new_team_name_buffer = ""
# Which team's context menu (opened by right-click, same pattern as profile
# cards) is mid-rename -- None means no context menu is in rename mode.
_renaming_team_id: Optional[str] = None
_rename_buffer = ""


def _team_member_count(team_id: str) -> int:
    return sum(1 for p in STATE.profiles if team_id in p.team_ids)


def _tab_width(label: str) -> float:
    """A tab's required width, measured the same way the Browse buttons are
    (calc_text_size + frame_padding on both sides) rather than guessed --
    every tab's width, including the overflow chip's, depends on its actual
    label text (which includes a live member count), so this can't be a
    fixed constant.
    """
    return imgui.calc_text_size(label).x + imgui.get_style().frame_padding.x * 2.0


def _draw_tab(draw_list, pos, w: float, h: float, label: str, *, key: str, active: bool) -> tuple[bool, bool]:
    """One tab: an invisible_button for real hit-testing/cursor behavior
    (right-click-popup support included), fully custom-drawn on top via
    draw_list -- same approach show_settings_gear_button already uses for its
    own custom-drawn icon button. Active-tab styling (accent-tinted
    background, accent border, accent bar) intentionally reuses the exact
    colors/treatment draw_profile_card uses for a selected card, just with
    the bar along the bottom edge instead of the left (cards are vertical,
    tabs are horizontal) -- so the header and grid read as one visual
    language rather than two different affordances.

    Returns (left_clicked, right_clicked); right-click is only meaningful
    for real team tabs -- callers ignore it for ALL/+/the overflow chip.
    """
    em = hello_imgui.em_size()
    imgui.set_cursor_screen_pos(pos)
    # invisible_button only tracks the left mouse button unless told
    # otherwise -- without this flag, is_item_clicked(1) below never fires,
    # confirmed directly (a real-app right-click test produced no popup at
    # all until this was added).
    both_buttons = int(imgui.ButtonFlags_.mouse_button_left.value | imgui.ButtonFlags_.mouse_button_right.value)
    imgui.invisible_button(f"##tab_{key}", size=(w, h), flags=both_buttons)
    hovered = imgui.is_item_hovered()
    clicked = imgui.is_item_clicked(0)
    right_clicked = imgui.is_item_clicked(1)
    p_min, p_max = imgui.get_item_rect_min(), imgui.get_item_rect_max()

    if active:
        bg, border = CARD_SELECTED_BACK, ACCENT
    elif hovered:
        bg, border = HOVER_BACK, HOVER_BORDER
    else:
        bg, border = CARD_BACK, CARD_BORDER
    draw_list.add_rect_filled(p_min, p_max, bg, rounding=6.0)
    draw_list.add_rect(p_min, p_max, border, rounding=6.0, thickness=1.0)
    if active:
        bar_h = em * 0.267
        draw_list.add_rect_filled((p_min[0], p_max[1] - bar_h), (p_max[0], p_max[1]), ACCENT, rounding=3.0)

    text_size = imgui.calc_text_size(label)
    text_pos = (p_min[0] + (w - text_size.x) / 2.0, p_min[1] + (h - text_size.y) / 2.0)
    draw_list.add_text(text_pos, CARD_NAME_FORE if active else CARD_SUB_FORE, label)
    return clicked, right_clicked


def _draw_inline_team_create_row() -> None:
    """The name-input + Create button for on-the-fly team creation -- shared
    between the "+" tab's own small popup and the overflow dropdown's tail
    (which had this same control before this pass; kept identical rather
    than duplicated).
    """
    global _new_team_name_buffer
    em = hello_imgui.em_size()
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


def _draw_team_context_menu(team: Team) -> None:
    """Rename/Delete popup body for `team`. Doesn't decide *how* it gets
    opened -- a team tab detects its own right-click directly (is_item_clicked
    (1)) and calls open_popup itself, while the overflow dropdown's list rows
    use open_popup_on_item_click instead -- so this only handles begin_popup
    plus content, shared so Rename/Delete behaves identically regardless of
    which surface triggered it.
    """
    global _renaming_team_id, _rename_buffer
    context_popup_id = f"team_context##{team.id}"
    if imgui.begin_popup(context_popup_id):
        em = hello_imgui.em_size()
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
            if imgui.selectable("Duplicate", False)[0]:
                STATE.duplicate_team(team.id)
                imgui.close_current_popup()
            if imgui.selectable("Delete", False)[0]:
                STATE.delete_team(team.id)
                imgui.close_current_popup()
        imgui.end_popup()


def show_team_tab_strip(avail_w: float) -> None:
    """Tab strip: "ALL" is a permanent first tab, then one tab per team
    (name plus a live member count, e.g. "Farm Squad · 2"), then a trailing
    "+" tab for inline team creation. Replaces the old </> arrows + center
    dropdown-label switcher entirely -- the arrows are gone outright (tabs
    make direct jumps to any view a single click, so cycling one at a time
    no longer earns its own buttons), but the dropdown-list popup itself
    wasn't thrown away: it's now the overflow path (see below).

    The Launch Team control (show_team_actions) is drawn right-aligned at
    the end of this same row instead of a separate row below -- its width is
    reserved (see _team_actions_width) before deciding how many team tabs
    fit, since it's competing with tabs for the same row now.

    Takes avail_w explicitly rather than querying get_content_region_avail()
    itself -- show_main_window wraps the whole header block in its own
    padded region narrower than the full window, and this right-aligns
    against that padded width, not the raw window width.

    Doesn't filter the card grid itself -- switching tabs here just changes
    STATE.current_team_id, which _visible_profiles reads to decide which
    cards actually show (a team tab narrows to that team's members only;
    membership itself is set via each card's right-click "Teams" submenu,
    not anything drawn here).

    If every team's tab doesn't fit in the available width, the ones that
    don't collapse into a trailing "N more" chip that opens the pre-existing
    dropdown-list popup for whatever didn't fit as a tab. Which teams fit is
    resolved by trying every possible split (all fit, all but one, ... none)
    rather than guessed, since the chip's own width depends on how many
    teams ended up in it.
    """
    global _new_team_name_buffer

    em = hello_imgui.em_size()
    style = imgui.get_style()
    spacing = style.item_spacing.x
    tab_h = imgui.get_frame_height() + em * 0.5

    draw_list = imgui.get_window_draw_list()
    row_origin = imgui.get_cursor_screen_pos()

    all_w = _tab_width("ALL")
    plus_w = _tab_width("+")
    actions_w = _team_actions_width()

    team_specs = []  # (team, label, width)
    for team in STATE.teams:
        label = f"{team.name or '(unnamed team)'} · {_team_member_count(team.id)}"
        team_specs.append((team, label, _tab_width(label)))

    # The Launch Team control shares this row (right-aligned, drawn after
    # the tabs below) rather than sitting on a row of its own -- reserve its
    # width here so tabs don't get laid out underneath it.
    tabs_avail_w = max(0.0, avail_w - actions_w - spacing)

    visible_teams: list[tuple[Team, str, float]] = team_specs
    overflow_teams: list[tuple[Team, str, float]] = []
    for visible_count in range(len(team_specs), -1, -1):
        candidate_visible = team_specs[:visible_count]
        candidate_overflow = team_specs[visible_count:]
        items_w = sum(w for _, _, w in candidate_visible)
        num_gaps = len(candidate_visible) + 1  # +1 for the gap before the "+" tab
        if candidate_overflow:
            items_w += _tab_width(f"{len(candidate_overflow)} more")
            num_gaps += 1
        total = all_w + items_w + plus_w + spacing * num_gaps
        if total <= tabs_avail_w or visible_count == 0:
            visible_teams, overflow_teams = candidate_visible, candidate_overflow
            break

    x, y = row_origin.x, row_origin.y

    if _draw_tab(draw_list, (x, y), all_w, tab_h, "ALL", key="all", active=STATE.current_team_id is None)[0]:
        STATE.jump_to_view(None)
    x += all_w + spacing

    for team, label, w in visible_teams:
        clicked, right_clicked = _draw_tab(
            draw_list, (x, y), w, tab_h, label, key=team.id, active=STATE.current_team_id == team.id
        )
        if clicked:
            STATE.jump_to_view(team.id)
        if right_clicked:
            imgui.open_popup(f"team_context##{team.id}")
        _draw_team_context_menu(team)
        x += w + spacing

    if overflow_teams:
        chip_label = f"{len(overflow_teams)} more"
        chip_w = _tab_width(chip_label)
        # Styled active (same accent treatment a selected tab gets) when the
        # currently-viewed team is hidden inside this chip -- otherwise the
        # active view would look like it belongs to no tab at all, and you'd
        # have to open the dropdown just to confirm where you actually are.
        active_team_is_overflowed = any(team.id == STATE.current_team_id for team, _, _ in overflow_teams)
        if _draw_tab(draw_list, (x, y), chip_w, tab_h, chip_label, key="overflow", active=active_team_is_overflowed)[0]:
            imgui.open_popup(_TEAM_OVERFLOW_POPUP_ID)
        x += chip_w + spacing

    if _draw_tab(draw_list, (x, y), plus_w, tab_h, "+", key="new_team", active=False)[0]:
        imgui.open_popup(_NEW_TEAM_POPUP_ID)
        _new_team_name_buffer = ""

    show_team_actions((row_origin.x + avail_w - actions_w, y))

    if imgui.begin_popup(_NEW_TEAM_POPUP_ID):
        _draw_inline_team_create_row()
        imgui.end_popup()

    if imgui.begin_popup(_TEAM_OVERFLOW_POPUP_ID):
        if imgui.selectable("ALL", STATE.current_team_id is None)[0]:
            STATE.jump_to_view(None)
            imgui.close_current_popup()
        for team in STATE.teams:
            label = f"{team.name or '(unnamed team)'} · {_team_member_count(team.id)}"
            if imgui.selectable(label, STATE.current_team_id == team.id)[0]:
                STATE.jump_to_view(team.id)
                imgui.close_current_popup()

            # Right-click a team for Rename/Delete -- same pattern as the
            # existing right-click-to-edit on profile cards.
            imgui.open_popup_on_item_click(f"team_context##{team.id}")
            _draw_team_context_menu(team)

        imgui.separator()
        _draw_inline_team_create_row()
        imgui.end_popup()

    imgui.set_cursor_screen_pos(row_origin)
    imgui.dummy((avail_w, tab_h))


def _visible_profiles() -> list[GameProfile]:
    """Profiles matching the current team view (if any) and the current name
    filter (case-insensitive substring) -- the single source of truth for
    "visible" used by the card grid. Team narrowing happens first, then the
    name filter narrows within that -- so both compose correctly regardless
    of which view is active. ALL (current_team_id is None) skips the team
    narrowing entirely and behaves exactly as before.
    """
    team_id = STATE.current_team_id
    pool = STATE.profiles if team_id is None else [p for p in STATE.profiles if team_id in p.team_ids]

    query = STATE.name_filter.strip().lower()
    if not query:
        return list(pool)
    return [p for p in pool if query in p.name.lower()]


def _team_actions_width() -> float:
    """Measured width of whatever occupies the top-right action slot -- the tab
    strip needs this before it lays out tabs, to reserve room for that control
    sharing the same row rather than tabs running underneath it. On ALL that slot
    is the "Add N to Team" batch control; on a team it's the Launch Team button
    (plus any live bulk-launch status text trailing it). Mirrors show_team_actions'
    own logic exactly so the two can't drift apart.
    """
    team_id = STATE.current_team_id
    if team_id is None:
        return _batch_add_to_team_width()
    label = f"Launch Team ({_team_member_count(team_id)})"
    style = imgui.get_style()
    width = imgui.calc_text_size(label).x + style.frame_padding.x * 2.0
    if STATE.is_bulk_launching():
        width += style.item_spacing.x + imgui.calc_text_size(STATE.bulk_launch_session.status_text).x
    return width


def show_team_actions(pos: tuple[float, float]) -> None:
    """Launch Team -- drawn at an explicit screen position (right-aligned
    after the tab strip's last tab, same row) rather than its own separate
    row below it, and always drawn regardless of view: this row previously
    drew nothing and consumed zero height when STATE.current_team_id was
    None, which meant switching between a team view and ALL shifted the
    card grid's origin -- visibly clipping/unclipping cards on every view
    switch. Disabled (not hidden) instead, matching the existing
    begin_disabled()/end_disabled() pattern already used below for the
    no-members-checked case. See _team_actions_width for the matching width
    measurement the tab strip uses to reserve room for this on that row
    before laying out tabs.

    Disabled/unarmed when there's no active team (ALL), no account is a member
    of the currently-viewed team, or a bulk launch is already running (never
    overlap two at once). The (N) in the label mirrors the member count
    directly -- team membership is set via each card's right-click "Teams"
    submenu, not anything drawn here -- so the armed/disabled state reads at
    a glance instead of being just a greyed-out button with no context.

    "Select all visible" / "Select none" were cut per design review -- they
    didn't earn their toolbar space -- rather than relabeled or relocated. The
    pacing control moved to the app settings window (gear icon) -- this is
    just the action and its live status, which stays here since that's what
    the user is actually watching during a launch.

    On the ALL view this same reserved slot holds the "Add N to Team" batch
    control instead of a permanently-disabled Launch Team button -- one live
    control per view rather than one visibly dead here and the other cramped onto
    the filter row.
    """
    em = hello_imgui.em_size()
    tab_h = imgui.get_frame_height() + em * 0.5
    imgui.set_cursor_screen_pos(pos)

    if STATE.current_team_id is None:
        _draw_batch_add_to_team_control(tab_h)
        return

    team_id = STATE.current_team_id
    members = [p for p in STATE.profiles if team_id in p.team_ids]
    bulk_launching = STATE.is_bulk_launching()
    can_launch = bool(members) and not bulk_launching and STATE.multiclient_enabled

    label = f"Launch Team ({len(members)})"
    if not can_launch:
        imgui.begin_disabled()
    launch_clicked = imgui.button(label, size=(0, tab_h))
    if not can_launch:
        imgui.end_disabled()
    if launch_clicked and can_launch:
        _try_launch_with_prereq_gate(
            lambda: STATE.start_bulk_launch(members),
            needs_py4gw=any(member.py4gw_enabled for member in members),
        )

    if bulk_launching:
        imgui.same_line()
        imgui.text_colored((0.9, 0.75, 0.3, 1.0), STATE.bulk_launch_session.status_text)


_BATCH_ADD_POPUP_ID = "Add to team##batch_add_popup"


def _batch_add_to_team_label() -> str:
    return f"Add {len(STATE.batch_selected_ids)} to Team"


def _batch_add_to_team_width() -> float:
    """Measured width of the batch-add button, so the tab strip can reserve room
    for it in the top-right action slot -- mirrors the Launch Team measurement in
    _team_actions_width for the other view."""
    style = imgui.get_style()
    return imgui.calc_text_size(_batch_add_to_team_label()).x + style.frame_padding.x * 2.0


def _draw_batch_add_to_team_control(button_height: float) -> None:
    """The ALL-view control that adds the batch-checked cards to a chosen team,
    drawn in show_team_actions' reserved top-right slot. Disabled (not hidden) when
    nothing is checked, so the slot doesn't reshuffle as the count crosses zero,
    only the label's count changes. Opens a small team picker with the same
    "No teams yet" disabled-row fallback the card's Teams submenu uses; picking a
    team adds the current selection and clears it.
    """
    has_selection = bool(STATE.batch_selected_ids)
    if not has_selection:
        imgui.begin_disabled()
    clicked = imgui.button(_batch_add_to_team_label(), size=(0, button_height))
    if not has_selection:
        imgui.end_disabled()
    if clicked and has_selection:
        imgui.open_popup(_BATCH_ADD_POPUP_ID)

    if imgui.begin_popup(_BATCH_ADD_POPUP_ID):
        if not STATE.teams:
            imgui.begin_disabled()
            imgui.selectable("No teams yet", False)
            imgui.end_disabled()
        else:
            for team in STATE.teams:
                if imgui.selectable(team.name or "(unnamed team)", False)[0]:
                    STATE.add_profiles_to_team(STATE.batch_selected_ids, team.id)
                    STATE.batch_selected_ids.clear()
                    imgui.close_current_popup()
        imgui.end_popup()


def show_settings_gear_button() -> None:
    """Small gear icon -- both reference launchers use this same icon for
    this same purpose, so it's a recognized affordance rather than a new one
    to learn. Drawn at the current cursor position (same_line right after
    the filter box, which show_main_window sizes to leave exactly enough
    room for this) rather than right-aligning itself -- it shares the filter
    box's row now instead of sitting alone on its own near-empty row above.

    Gets a small warning-colored badge at its corner when
    PREREQS.all_ok() is False -- a first-run user with a missing
    prerequisite shouldn't have to stumble into a silent injection failure
    to discover it. Deliberately a badge on this existing affordance rather
    than a new status row: this app has already trimmed near-empty status
    rows before (the old "N profiles loaded" line, an unconditional reload
    button), so a new row for this would cut against that precedent, while a
    badge on the icon that already opens the place to fix it doesn't. No
    badge while all_ok() is None (still checking) or True.
    """
    em = hello_imgui.em_size()
    icon_size = em * 1.8
    clicked = imgui.button("##app_settings_gear", size=(icon_size, icon_size))
    hovered = imgui.is_item_hovered()
    item_min, item_max = imgui.get_item_rect_min(), imgui.get_item_rect_max()
    center = ((item_min[0] + item_max[0]) / 2, (item_min[1] + item_max[1]) / 2)
    draw_list = imgui.get_window_draw_list()
    _draw_gear_icon(draw_list, center, icon_size * 0.7, CARD_SUB_FORE)

    try:
        if PREREQS.all_ok() is False:
            badge_radius = icon_size * 0.15
            badge_center = (item_max[0] - badge_radius, item_min[1] + badge_radius)
            # draw_list calls want a packed u32 color, not the float4 tuple
            # _PREREQ_MISSING_COLOR is (that's for imgui.text_colored) -- same
            # conversion _u32() does internally.
            badge_color = imgui.color_convert_float4_to_u32(_PREREQ_MISSING_COLOR)
            draw_list.add_circle_filled(badge_center, badge_radius, badge_color)
            draw_list.add_circle(badge_center, badge_radius, CARD_BACK, thickness=1.5)
            if hovered:
                imgui.set_tooltip("Setup incomplete -- click for details")
    except Exception:
        # No Begin/End pairing at stake here (just draw_list calls plus a
        # tooltip), so a plain catch-and-log is enough -- unlike the launch-
        # gate popup, there's no window stack to leave unbalanced.
        _log_prereq_ui_error("gear icon prereq badge")

    if clicked:
        STATE.app_settings_window_open = True


def show_main_window() -> None:
    STATE.update()

    # The whole header block (tab strip + Launch Team, then filter box +
    # gear icon) gets real outer margin instead of sitting flush against the
    # window edges: a one-time top inset (dummy) plus a persistent left
    # inset (indent, held until unindent below) for the block's full height,
    # and an explicit reduced width passed to whichever elements right-align
    # or stretch (tab strip, filter box) so they stop header_pad short of
    # the true right edge too -- indent alone only handles the left side.
    # Two visually related rows (tabs+launch, then filter+gear) instead of
    # three disconnected ones (gear alone on its own near-empty row, tabs,
    # filter) sitting right against the window frame.
    em = hello_imgui.em_size()
    header_pad = em * 0.6
    avail_w_full = imgui.get_content_region_avail().x
    header_w = avail_w_full - header_pad * 2.0

    imgui.dummy((0.0, header_pad))
    imgui.indent(header_pad)

    show_team_tab_strip(header_w)

    imgui.spacing()
    style = imgui.get_style()
    gear_icon_size = em * 1.8
    filter_w = header_w - gear_icon_size - style.item_spacing.x
    imgui.set_next_item_width(filter_w)
    _, STATE.name_filter = imgui.input_text_with_hint("##name_filter", "Filter by name...", STATE.name_filter)
    imgui.same_line()
    show_settings_gear_button()

    imgui.unindent(header_pad)
    imgui.dummy((0.0, header_pad))

    imgui.separator()
    imgui.spacing()

    em = hello_imgui.em_size()
    min_card_w, card_h, card_gap = _card_dimensions()
    # Cards stretch to fill the row instead of leaving a trailing gap on the
    # right: min_card_w is a floor (today's size, used to decide how many
    # columns fit), and a soft ceiling (see _max_card_w_for_columns, scaled by
    # column count) keeps cards from getting absurdly wide on a large window
    # without needlessly capping a single column short of the available
    # width. Only the card's own width changes -- everything drawn inside a
    # card (avatar, text, badges) is still positioned/sized relative
    # to em and to the card's own edges, so it doesn't scale with it.
    visible_profiles = _visible_profiles()
    # Team tabs are pure roster views -- no "Add profile" card there, only in ALL.
    show_add_card = STATE.current_team_id is None
    item_count = len(visible_profiles) + (1 if show_add_card else 0)

    imgui.begin_child("card_grid", size=(0, 0), child_flags=int(imgui.ChildFlags_.borders.value))
    draw_list = imgui.get_window_draw_list()
    origin = imgui.get_cursor_screen_pos()
    grid_is_hoverable = imgui.is_window_hovered()

    # Measured from *inside* the child (after begin_child), not the parent's
    # avail beforehand -- the child applies its own window padding on both
    # sides, and origin (above) already starts past the left padding, so
    # sizing against the parent's wider, padding-unaware avail_w would let
    # cards extend past the child's actual right-padding edge, reading as
    # uneven left/right margins. Confirmed directly (not assumed): a one-off
    # diagnostic print showed the parent's avail_w exceeding this child-side
    # figure by exactly 2x window_padding.x.
    avail = imgui.get_content_region_avail()
    avail_w = avail.x
    cols, card_w = _grid_columns_and_card_width(avail_w, min_card_w, card_gap)

    # Pre-check whether a vertical scrollbar will actually be needed, using the
    # same ceiling-rows formula the end-of-grid dummy sizing already uses. Only
    # matters for the one transition frame where the scrollbar isn't showing
    # yet (get_scroll_max_y() from the end of the previous frame is still 0)
    # but this frame's content is about to overflow -- avail_w measured above
    # doesn't know about that yet, so redo the column/card-width math against
    # a scrollbar-reduced width now, rather than assuming full width and
    # getting the rightmost column clipped by the scrollbar next frame.
    #
    # Once the scrollbar is actually showing (get_scroll_max_y() > 0), avail_w
    # already reflects it -- it was measured via get_content_region_avail()
    # *inside* the child, which ImGui itself already shrinks by scrollbar_size
    # once a scrollbar is active. Subtracting scrollbar_w again here on top of
    # that double-counted it, narrowing every card by a full scrollbar-width's
    # worth of pixels for as long as the scrollbar stayed visible -- confirmed
    # directly via a one-off diagnostic (avail_w=570.0 with get_scroll_max_y()
    # already >0, i.e. steady-state, yet still getting shrunk by another 14px).
    rows = (item_count + cols - 1) // cols
    content_h = rows * card_h + max(0, rows - 1) * card_gap
    if content_h > avail.y and imgui.get_scroll_max_y() == 0.0:
        scrollbar_w = imgui.get_style().scrollbar_size
        cols, card_w = _grid_columns_and_card_width(
            max(min_card_w, avail_w - scrollbar_w), min_card_w, card_gap
        )

    for i, profile in enumerate(visible_profiles):
        col = i % cols
        row = i // cols
        card_origin = (
            origin.x + col * (card_w + card_gap),
            origin.y + row * (card_h + card_gap),
        )
        p_min = card_origin
        p_max = (card_origin[0] + card_w, card_origin[1] + card_h)

        in_all_view = STATE.current_team_id is None
        checkbox_hovered = False
        if in_all_view:
            checkbox_min, checkbox_max = batch_checkbox_rect(card_origin, card_h, em)
            checkbox_hovered = grid_is_hoverable and imgui.is_mouse_hovering_rect(checkbox_min, checkbox_max)
            if checkbox_hovered and imgui.is_mouse_clicked(0):
                if profile.id in STATE.batch_selected_ids:
                    STATE.batch_selected_ids.discard(profile.id)
                else:
                    STATE.batch_selected_ids.add(profile.id)

        # Excludes the checkbox's own rect so the two click targets can't collide:
        # a click on the checkbox toggles batch selection only, never also selects
        # or foregrounds the card underneath it.
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
                # Default-arg trick (p=profile) to bind *this* iteration's
                # profile into the lambda now -- without it, a deferred
                # launch_action (if the prereq gate below interposes with
                # its confirm popup) would close over the loop variable
                # itself and, by the time "Launch anyway" is actually
                # clicked frames later, launch whatever profile this loop
                # last iterated to instead of the one actually double-clicked.
                _try_launch_with_prereq_gate(
                    lambda p=profile: STATE.start_launch(p), needs_py4gw=profile.py4gw_enabled
                )

        if hovered and imgui.is_mouse_clicked(1):
            STATE.selected_id = profile.id
            imgui.open_popup(f"card_context##{profile.id}")

        if imgui.begin_popup(f"card_context##{profile.id}"):
            if imgui.selectable("Edit", False)[0]:
                STATE.begin_edit_selected()
                imgui.close_current_popup()

            # Checkable rows via imgui.checkbox (not menu_item) specifically
            # because checkboxes never auto-close the popup -- lets a user set
            # membership across several teams in one right-click session
            # instead of having to reopen the menu after every toggle.
            # toggle_team_membership already saves immediately, same as the
            # card checkbox this submenu replaced.
            if imgui.begin_menu("Teams"):
                if not STATE.teams:
                    imgui.begin_disabled()
                    imgui.selectable("No teams yet", False)
                    imgui.end_disabled()
                else:
                    for team in STATE.teams:
                        changed, _ = imgui.checkbox(
                            team.name or "(unnamed team)", team.id in profile.team_ids
                        )
                        if changed:
                            STATE.toggle_team_membership(profile, team.id)
                imgui.end_menu()

            # Disabled (not hidden) while a session is live -- don't let a
            # running or launching profile be deleted out from under itself.
            delete_disabled = STATE.is_running(profile.id) or STATE.is_launching(profile.id)
            if delete_disabled:
                imgui.begin_disabled()
            if imgui.selectable("Delete", False)[0]:
                _request_delete_profile(profile)
            if delete_disabled:
                imgui.end_disabled()

            imgui.end_popup()

        draw_profile_card(
            draw_list, card_origin, profile, card_w=card_w, card_h=card_h,
            hovered=hovered, selected=(STATE.selected_id == profile.id),
            running=running, launching=launching or is_error,
            status_text=status_text, is_error=is_error,
            show_batch_checkbox=in_all_view,
            batch_checked=(profile.id in STATE.batch_selected_ids),
            checkbox_hovered=checkbox_hovered,
        )

    if show_add_card:
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

    rows = (item_count + cols - 1) // cols
    imgui.dummy((avail_w, rows * (card_h + card_gap)))
    imgui.end_child()

    _show_prereq_launch_confirm_popup()
    _show_delete_profile_confirm_popup()
    _show_legacy_autodetect_popup()


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


def _browse_for_save_file(*, title: str, filter_str: str, default_filename: str = "") -> Optional[str]:
    """Blocking native Win32 Save-As dialog, the save-side mirror of
    _browse_for_file: same pywin32-already-a-dependency reasoning, same
    NUL-separated filter format, but GetSaveFileNameW with OFN_OVERWRITEPROMPT
    (confirm before clobbering an existing file) instead of GetOpenFileNameW's
    must-exist flags. `default_filename` pre-fills the name field.
    """
    try:
        filename, _customfilter, _flags = win32gui.GetSaveFileNameW(
            File=default_filename,
            Filter=filter_str,
            Title=title,
            Flags=win32con.OFN_OVERWRITEPROMPT,
        )
    except pywintypes.error:
        return None  # user cancelled

    return filename or None


# BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE -- this pywin32 build's shellcon module
# doesn't expose either name (confirmed directly: AttributeError on both), so these
# are the documented Win32 SHBrowseForFolder flag values themselves rather than
# symbolic constants: only return real filesystem directories, and use the modern
# resizable/tree-view dialog instead of the old fixed-size one.
_BIF_RETURNONLYFSDIRS = 0x0001
_BIF_NEWDIALOGSTYLE = 0x0040


def _browse_for_folder(*, title: str, initial_path: str = "") -> Optional[str]:
    """Native Win32 folder-picker (SHBrowseForFolder, via the win32com.shell
    extension already bundled with this project's existing pywin32 dependency
    -- no new dependency) for the mod-repo location field, which needs a
    directory rather than a specific file the way _browse_for_file's fields
    do. Confirmed directly (screenshot + programmatic cancel) that this shows
    the real modern folder-browser dialog and correctly reports a cancel as
    (None, None, None) from SHBrowseForFolder rather than raising.
    """
    result = win32_shell.SHBrowseForFolder(
        0, None, title, _BIF_RETURNONLYFSDIRS | _BIF_NEWDIALOGSTYLE, None, None
    )
    pidl = result[0] if result else None
    if pidl is None:
        return None  # user cancelled
    path = win32_shell.SHGetPathFromIDList(pidl)
    if path is None:
        return None
    # Confirmed via a real crash report (not assumed): SHGetPathFromIDList
    # returned bytes instead of str on one real machine -- unlike
    # _browse_for_file's GetOpenFileNameW (an explicit wide/Unicode API,
    # always str), this shell API gives no such guarantee across
    # environments. Coerce defensively rather than passing a possibly-bytes
    # value straight into Path(), which rejects bytes outright.
    if isinstance(path, bytes):
        path = os.fsdecode(path)
    return path or None


def _path_field_with_browse(*, label: str, value: str, id_suffix: str, dialog_title: str, filter_str: str) -> str:
    """Label above an input + measured-width "..." browse button, rather than
    picking a window size that happens not to clip the button (the previous
    fix): calc_text_size gives the button's real required width, that width is
    reserved exactly, and the input takes whatever's left -- the input is what
    flexes on a narrow window, the button never does, so this can't clip at
    any reasonable window size.
    """
    imgui.text(label)
    style = imgui.get_style()
    button_w = imgui.calc_text_size("...").x + style.frame_padding.x * 2
    avail_w = imgui.get_content_region_avail().x
    input_w = max(1.0, avail_w - button_w - style.item_spacing.x)
    imgui.set_next_item_width(input_w)
    _, value = imgui.input_text(f"##{id_suffix}", value)
    imgui.same_line()
    if imgui.button(f"...##{id_suffix}_browse", size=(button_w, 0)):
        chosen = _browse_for_file(title=dialog_title, filter_str=filter_str, initial_path=value)
        if chosen:
            value = chosen
    return value


SETTINGS_TABS = ["General", "Mods", "Window"]
_active_tab = SETTINGS_TABS[0]

# How many frames to keep AlwaysAutoResize active after the Settings window
# (re)appears -- see show_settings_window() for why this needs to be more than 1.
_SETTINGS_AUTOSIZE_FRAMES = 4
_settings_autosize_frames_remaining = 0
# Separate counter from the profile Settings window's -- both can be open at once,
# so they can't share one autosize-frames state.
_app_settings_autosize_frames_remaining = 0


def _is_protected_install_path(exe_path: str) -> bool:
    """True if exe_path lives under a protected Windows install root (Program Files
    or Program Files (x86)) -- ported from GWxLauncher's own check. Detect-and-warn
    only: this app never requests elevation, matching its existing philosophy. Uses
    the %ProgramFiles% / %ProgramFiles(x86)% env vars (case-insensitive path
    compare), falling back to the literal defaults only if those are somehow unset.
    """
    if not exe_path:
        return False
    normalized = os.path.normcase(os.path.abspath(exe_path))
    roots = (
        os.environ.get("ProgramFiles") or r"C:\Program Files",
        os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)",
        # This launcher is a 32-bit process, so under WOW64 %ProgramFiles% resolves
        # to the (x86) folder, not the real 64-bit "C:\Program Files". %ProgramW6432%
        # is how a 32-bit process sees that 64-bit folder -- without it a Gw.exe
        # installed there wouldn't be flagged. Falls back to the literal if unset
        # (e.g. a genuine 32-bit OS, where there's no separate 64-bit folder anyway).
        os.environ.get("ProgramW6432") or r"C:\Program Files",
    )
    for root in roots:
        root_norm = os.path.normcase(os.path.abspath(root))
        if normalized == root_norm or normalized.startswith(root_norm + os.sep):
            return True
    return False


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
        imgui.spacing()
        imgui.text("Launch")
        _, buffer.name = imgui.input_text("Profile name", buffer.name)
        buffer.executable_path = _path_field_with_browse(
            label="Executable path", value=buffer.executable_path, id_suffix="executable_path",
            dialog_title="Select Guild Wars executable",
            filter_str="Guild Wars executable (Gw.exe)\0Gw.exe\0Executable files (*.exe)\0*.exe\0All files (*.*)\0*.*\0",
        )
        if buffer.executable_path:
            # Same case-insensitive comparison gw1_launch.py's own
            # _find_replacement_process already uses for matching executable
            # paths -- informational only (doesn't block Save): running two
            # profiles pointed at the same real Gw.exe install is a
            # legitimate but easy-to-miss mistake, worth flagging before it
            # causes confusing launch behavior rather than blocking it
            # outright (there may be real reasons to do this intentionally).
            normalized = os.path.normcase(os.path.abspath(buffer.executable_path))
            duplicate = next(
                (
                    p for p in STATE.profiles
                    if p.id != buffer.original_id and p.executable_path
                    and os.path.normcase(os.path.abspath(p.executable_path)) == normalized
                ),
                None,
            )
            if duplicate is not None:
                imgui.text_colored(
                    (0.9, 0.75, 0.3, 1.0),
                    f"Another profile ('{duplicate.name or '(unnamed profile)'}') already uses this executable path.",
                )
        # Independent of the duplicate-path check above -- a path can trigger
        # neither, either, or both.
        if _is_protected_install_path(buffer.executable_path):
            imgui.text_colored(
                (0.9, 0.75, 0.3, 1.0),
                "This looks like a protected Windows folder. Py4GW injection may fail\n"
                "or behave unpredictably here -- consider moving your Guild Wars install\n"
                "to a regular folder instead (e.g. C:\\Games\\Guild Wars\\).",
            )
        imgui.separator()
        imgui.spacing()
        imgui.text("Auto-Login")
        _, buffer.email = imgui.input_text("Account email", buffer.email)
        _, buffer.password_input = imgui.input_text(
            "Password", buffer.password_input, flags=int(imgui.InputTextFlags_.password.value)
        )
        if buffer.has_stored_password and not buffer.password_input:
            imgui.text_colored((0.6, 0.6, 0.65, 1.0), "A password is already saved -- leave blank to keep it.")
        _, buffer.auto_login_enabled = imgui.checkbox("Enable auto-login", buffer.auto_login_enabled)
        _, buffer.auto_select_character_enabled = imgui.checkbox(
            "Auto-select character", buffer.auto_select_character_enabled
        )
        _, buffer.character_name = imgui.input_text("Character name", buffer.character_name)
    elif _active_tab == "Mods":
        _, buffer.py4gw_enabled = imgui.checkbox("Inject Py4GW", buffer.py4gw_enabled)
        buffer.py4gw_dll_path = _path_field_with_browse(
            label="Py4GW DLL path", value=buffer.py4gw_dll_path, id_suffix="py4gw_dll_path",
            dialog_title="Select Py4GW DLL", filter_str="DLL files (*.dll)\0*.dll\0All files (*.*)\0*.*\0",
        )
        _, buffer.gmod_enabled = imgui.checkbox("Inject gMod", buffer.gmod_enabled)
        buffer.gmod_dll_path = _path_field_with_browse(
            label="gMod DLL path", value=buffer.gmod_dll_path, id_suffix="gmod_dll_path",
            dialog_title="Select gMod DLL", filter_str="DLL files (*.dll)\0*.dll\0All files (*.*)\0*.*\0",
        )
        imgui.text_colored((0.6, 0.6, 0.65, 1.0), "(gMod injection timing not implemented yet)")
    elif _active_tab == "Window":
        _, buffer.windowed_mode_enabled = imgui.checkbox("Windowed mode", buffer.windowed_mode_enabled)
        imgui.text_colored(
            (0.6, 0.6, 0.65, 1.0),
            "Recommended: fullscreen can cause problems when running multiple accounts.",
        )

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


def _main_window_rect_and_work_area() -> Optional[tuple[tuple[int, int, int, int], tuple[int, int, int, int]]]:
    """The main app window's current (left, top, right, bottom) screen rect,
    plus the work area (screen bounds minus taskbar) of whichever monitor it
    currently sits on -- or None if the main window can't be found (e.g. not
    shown yet). Used to position the Settings window relative to wherever
    the main window actually is right now -- see _settings_window_default_pos.
    """
    hwnd = find_visible_window_for_pid(os.getpid())
    if hwnd is None:
        return None
    main_rect = win32gui.GetWindowRect(hwnd)
    monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
    work_area = win32api.GetMonitorInfo(monitor)["Work"]
    return main_rect, work_area


def _settings_window_default_pos(settings_w: float, settings_h: float) -> tuple[float, float]:
    """Where to place the Settings window relative to the main window's
    current position and size, rather than a fixed or remembered spot that
    goes stale the moment the main window moves (including to a different
    monitor): picks whichever side -- left, right, above, or below the main
    window -- has the most free space on its current monitor's work area,
    offsets a small margin into that space off the main window's edge, and
    centers/clamps along the other axis so it can't run off-screen there
    either. Falls back to a fixed small offset if the main window can't be
    found at all (not expected in practice, but cheaper than crashing).
    """
    em = hello_imgui.em_size()
    result = _main_window_rect_and_work_area()
    if result is None:
        return em * 4.0, em * 4.0

    (m_left, m_top, m_right, m_bottom), (w_left, w_top, w_right, w_bottom) = result
    space_left = m_left - w_left
    space_right = w_right - m_right
    space_above = m_top - w_top
    space_below = w_bottom - m_bottom
    margin = em * 1.0

    # The placement axis (x for left/right, y for above/below) is clamped to the
    # work area too, not just offset off the main window's edge: when the window
    # is wider/taller than the chosen side's free space it would otherwise spill
    # off that edge of the screen (the partial-off-screen bug). Clamping keeps it
    # fully on-screen -- overlapping the main window if it has to, which beats
    # hanging off the edge. The cross axis was already clamped this way.
    best = max(space_left, space_right, space_above, space_below)
    if best == space_right:
        x = float(min(w_right - settings_w, m_right + margin))
        y = float(max(w_top, min(m_top, w_bottom - settings_h)))
    elif best == space_left:
        x = float(max(w_left, m_left - margin - settings_w))
        y = float(max(w_top, min(m_top, w_bottom - settings_h)))
    elif best == space_below:
        x = float(max(w_left, min(m_left, w_right - settings_w)))
        y = float(min(w_bottom - settings_h, m_bottom + margin))
    else:
        x = float(max(w_left, min(m_left, w_right - settings_w)))
        y = float(max(w_top, m_top - margin - settings_h))
    return x, y


def show_settings_window() -> None:
    if not STATE.settings_window_open:
        return

    global _settings_autosize_frames_remaining

    em = hello_imgui.em_size()
    # Rough baseline for the single frame before real measurement below takes
    # over -- not the final word, just avoids a jarring flash at some ImGui
    # internal default size before AlwaysAutoResize kicks in. Also used as
    # the size estimate for _settings_window_default_pos below, since the
    # real auto-fitted size isn't known until after this window's first
    # render.
    baseline_w, baseline_h = em * 32.0, em * 21.3
    imgui.set_next_window_size((baseline_w, baseline_h), cond=imgui.Cond_.appearing.value)
    imgui.set_next_window_size_constraints((em * 20.0, em * 12.0), (1.0e9, 1.0e9))
    # cond=appearing (not first_use_ever): recomputed fresh from the main
    # window's *current* position/monitor every single time this window
    # opens, rather than remembering a fixed spot from whenever it was last
    # opened -- a remembered position goes stale the moment the main window
    # moves (dragged to a different spot, or a different monitor entirely).
    # This fully replaces the previous pass's persisted-position approach,
    # not supplements it -- see _settings_window_default_pos.
    imgui.set_next_window_pos(_settings_window_default_pos(baseline_w, baseline_h), cond=imgui.Cond_.appearing.value)

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

_PREREQ_OK_COLOR = (0.45, 0.75, 0.45, 1.0)
_PREREQ_MISSING_COLOR = (0.86, 0.35, 0.35, 1.0)
_PREREQ_MUTED_COLOR = (0.6, 0.6, 0.65, 1.0)
_PREREQ_BUSY_COLOR = (0.9, 0.75, 0.3, 1.0)

_PREREQ_INSTALL_CONFIRM_POPUP_ID = "Install prerequisite?##prereq_confirm"
# (component key for PrereqState.start_install, download URL shown to the
# user, display name) -- set when "Install now" is clicked, read by the
# confirm popup, cleared once resolved either way.
_prereq_install_pending: Optional[tuple[str, str, str]] = None

_PREREQ_LAUNCH_CONFIRM_POPUP_ID = "Prerequisites missing##prereq_launch_confirm"
# (missing prereq names, the actual launch call to run if the user clicks
# "Launch anyway") -- set by _try_launch_with_prereq_gate when it intercepts
# a launch, read/cleared by the confirm popup once resolved either way.
_prereq_launch_pending: Optional[tuple[list[str], Callable[[], None]]] = None
# Set by _try_launch_with_prereq_gate, consumed by _show_prereq_launch_confirm_popup:
# the actual imgui.open_popup() call is deferred to that function rather than
# fired from the gate itself, because the gate can be called from inside the
# card grid's own child window (a real ID-stack scope in ImGui) while the popup
# is rendered from the top level, after that child has already ended. OpenPopup
# and BeginPopupModal must run at the *same* ID-stack depth to refer to the same
# popup -- calling OpenPopup from inside the child computed a different ID than
# BeginPopupModal checked for at the top level, so the popup silently never
# matched and never opened. Confirmed directly: a real double-click on a card
# (not a distance/timing issue -- this reproduced with the mouse landing dead on
# target) triggered the gate but never showed anything, with no exception either
# -- exactly what a silent ID mismatch looks like, as opposed to Launch Team's
# button (already top-level, same scope as the popup call) which always worked.
_prereq_launch_popup_should_open = False
# Once the user clicks "Launch anyway" once, this stops interrupting for the
# rest of this run -- guidance, not a recurring nag on every single launch
# once the user has already made an informed choice to proceed anyway.
_prereq_launch_acknowledged_this_session = False

# Last logged prereq-UI exception text (badge draw or launch-gate popup) -- de-dupes
# so a failure that recurs every single frame doesn't spam the log at 60fps; a new,
# distinct failure still gets its own line.
_prereq_ui_last_logged_error: Optional[str] = None


def _log_prereq_ui_error(context: str) -> None:
    """Both the gear-icon badge draw and the launch-gate popup run on every
    single frame whenever a prereq is missing -- the one state the pre-ship
    sanity check only forced briefly, never exercised via a real, repeated
    run. An uncaught exception raised from ImGui-calling code can abort just
    that frame's drawing without crashing the process -- immediate-mode GUIs
    have no separate "model" to fall back on, so a mid-frame exception can
    leave that frame (or, if a Begin/End pair was left unbalanced, every
    frame after it) rendering nothing: an intermittent or permanently blank
    window with no crash and no visible error. Callers must catch here
    (never let this feature's own failure block an actual launch or corrupt
    the frame) and this logs once per distinct message rather than every
    frame, to both stderr (visible under console python.exe) and a file
    under %APPDATA% (visible even under the packaged, console-less exe).

    Always logged at ERROR -- this function only ever runs because
    something genuinely broke, so it always belongs in the WARNING+-filtered
    launcher_errors.log, not just the full launcher.log.
    """
    global _prereq_ui_last_logged_error
    text = traceback.format_exc()
    if text == _prereq_ui_last_logged_error:
        return
    _prereq_ui_last_logged_error = text
    print(f"[prereq-ui] {context} failed:\n{text}", file=sys.stderr)
    try:
        _error_logger.error(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{context}]\n{text}")
    except OSError:
        pass


def _try_launch_with_prereq_gate(launch_action: Callable[[], None], *, needs_py4gw: bool) -> None:
    """Runs `launch_action` (a zero-arg callable that actually starts the
    launch -- e.g. a lambda wrapping STATE.start_launch(profile) or
    STATE.start_bulk_launch(members)) immediately, with zero added friction,
    unless all three of these hold: this launch actually uses Py4GW
    injection (needs_py4gw -- a plain GW1-only profile/team has nothing to
    check here), PREREQS has definitively finished checking and found
    something missing (PREREQS.all_ok() is False -- None means still
    checking, which also launches immediately rather than blocking on a
    check that hasn't finished yet), and the user hasn't already clicked
    "Launch anyway" earlier this session.

    Never a hard block -- "Launch anyway" is always one click away in the
    popup this opens instead of launching directly, since the check itself
    could have an edge case (unusual Python install layout, etc.) that
    shouldn't be able to actually prevent a launch, only prompt about it.
    Same guarantee holds if this gate's own logic breaks: any exception here
    is logged and treated as "nothing to gate on," falling through to the
    real launch rather than silently eating the user's double-click/button
    press with no launch and no popup either.
    """
    global _prereq_launch_pending, _prereq_launch_popup_should_open
    try:
        should_gate = (
            needs_py4gw
            and not _prereq_launch_acknowledged_this_session
            and PREREQS.all_ok() is False
        )
        if should_gate:
            _prereq_launch_pending = (PREREQS.missing_names(), launch_action)
            _prereq_launch_popup_should_open = True
            return
    except Exception:
        _log_prereq_ui_error("prereq launch gate")
    launch_action()


def _show_prereq_launch_confirm_popup() -> None:
    """Rendered unconditionally every frame from show_main_window (not
    nested inside any particular window's own open/closed state, unlike the
    install-confirm popup which only matters while App Settings is open --
    a launch attempt can happen with App Settings closed), always at this
    same top-level scope -- open_popup is called from right here too (see
    _prereq_launch_popup_should_open) rather than from the gate itself, so
    both calls always agree on the popup's ID regardless of which nested
    window/child the gate happened to be triggered from.

    begin_popup_modal's block is wrapped in try/finally: Begin*/End* calls
    must stay balanced no matter what happens in between, or ImGui's window
    stack is left corrupted for every frame afterward -- a real candidate
    for a permanently blank window that never recovers on its own. An
    exception in here is logged and the popup is dismissed rather than left
    dangling.
    """
    global _prereq_launch_pending, _prereq_launch_acknowledged_this_session, _prereq_launch_popup_should_open
    if _prereq_launch_popup_should_open:
        imgui.open_popup(_PREREQ_LAUNCH_CONFIRM_POPUP_ID)
        _prereq_launch_popup_should_open = False

    opened = imgui.begin_popup_modal(
        _PREREQ_LAUNCH_CONFIRM_POPUP_ID, flags=int(imgui.WindowFlags_.always_auto_resize.value)
    )[0]
    if not opened:
        return
    try:
        if _prereq_launch_pending is not None:
            missing_names, launch_action = _prereq_launch_pending
            count = len(missing_names)
            imgui.text(
                f"Py4GW injection needs {count} prerequisite{'s' if count != 1 else ''} "
                f"that aren't installed yet:\n{', '.join(missing_names)}"
            )
            imgui.spacing()
            if imgui.button("Open App Settings"):
                STATE.app_settings_window_open = True
                _prereq_launch_pending = None
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("Launch anyway"):
                _prereq_launch_acknowledged_this_session = True
                pending_launch_action = launch_action
                _prereq_launch_pending = None
                imgui.close_current_popup()
                pending_launch_action()
    except Exception:
        _log_prereq_ui_error("prereq launch confirm popup")
        _prereq_launch_pending = None
    finally:
        imgui.end_popup()


_DELETE_PROFILE_CONFIRM_POPUP_ID = "Delete profile?##delete_profile_confirm"
# The profile awaiting delete-confirmation, and a deferred-open flag. The actual
# open_popup is fired from _show_delete_profile_confirm_popup (top-level scope),
# not from the card context menu that requests it: that menu renders inside the
# card grid's own child window, and OpenPopup must share BeginPopupModal's
# ID-stack depth or the modal silently never opens -- the same scope trap the
# prereq launch gate above documents.
_profile_pending_delete: "Optional[GameProfile]" = None
_delete_profile_popup_should_open = False


def _request_delete_profile(profile: GameProfile) -> None:
    """Arm the delete-confirm modal for `profile` (called from the card's
    right-click menu). Deferred-open, see _profile_pending_delete's note."""
    global _profile_pending_delete, _delete_profile_popup_should_open
    _profile_pending_delete = profile
    _delete_profile_popup_should_open = True


def _show_delete_profile_confirm_popup() -> None:
    global _profile_pending_delete, _delete_profile_popup_should_open
    if _delete_profile_popup_should_open:
        imgui.open_popup(_DELETE_PROFILE_CONFIRM_POPUP_ID)
        _delete_profile_popup_should_open = False

    if not imgui.begin_popup_modal(
        _DELETE_PROFILE_CONFIRM_POPUP_ID, flags=int(imgui.WindowFlags_.always_auto_resize.value)
    )[0]:
        return
    try:
        profile = _profile_pending_delete
        if profile is not None:
            imgui.text(f"Delete {profile.name or '(unnamed profile)'}?")
            imgui.text_colored(
                _PREREQ_MUTED_COLOR,
                "This removes its saved login, mod configuration, and team membership.\n"
                "This can't be undone.",
            )
            imgui.spacing()
            if imgui.button("Delete"):
                STATE.delete_profile(profile.id)
                _profile_pending_delete = None
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("Cancel"):
                _profile_pending_delete = None
                imgui.close_current_popup()
    finally:
        imgui.end_popup()


class _VcRedistArchView:
    """Adapts one arch's slice of a combined VcRedistResult (which reports
    both x86 and x64 together) to the same is_ok/diagnostic_text shape
    _draw_prereq_row expects from every other prereq result type, so it
    doesn't need special-casing for VC++'s two-architectures-in-one-result
    shape.
    """

    def __init__(self, result: prereqs.VcRedistResult, arch: str):
        self._arch = arch
        self._status = result.x86_status if arch == "x86" else result.x64_status
        self._version = result.x86_version if arch == "x86" else result.x64_version

    @property
    def is_ok(self) -> bool:
        return self._status == prereqs.VcRedistStatus.OK

    @property
    def diagnostic_text(self) -> str:
        if self.is_ok:
            return f"version {self._version}"
        return "not found"


def _draw_prereq_row(label: str, result, component_key: str, download_url: str) -> None:
    """One prereq status row: a clear OK/NOT FOUND status (never buried --
    this is drawn first thing in the window, not tucked under other
    settings) plus a single low-friction "Install now" action when missing.
    Downloading and running a real installer from the internet isn't a
    zero-consequence click, so it's gated behind one confirm/Cancel popup
    rather than starting immediately.
    """
    global _prereq_install_pending

    if result is None:
        imgui.text_colored(_PREREQ_MUTED_COLOR, f"{label}: checking...")
        return

    if result.is_ok:
        imgui.text_colored(_PREREQ_OK_COLOR, f"{label}: OK -- {result.diagnostic_text}")
        return

    imgui.text_colored(_PREREQ_MISSING_COLOR, f"{label}: NOT FOUND")
    if PREREQS.install_in_progress == component_key:
        imgui.same_line()
        imgui.text_colored(_PREREQ_BUSY_COLOR, PREREQS.install_status_text)
    else:
        imgui.same_line()
        if imgui.button(f"Install now##{component_key}"):
            _prereq_install_pending = (component_key, download_url, label)
            imgui.open_popup(_PREREQ_INSTALL_CONFIRM_POPUP_ID)


def _show_prereq_install_confirm_popup() -> None:
    global _prereq_install_pending
    if imgui.begin_popup_modal(_PREREQ_INSTALL_CONFIRM_POPUP_ID, flags=int(imgui.WindowFlags_.always_auto_resize.value))[0]:
        if _prereq_install_pending is not None:
            component_key, download_url, label = _prereq_install_pending
            imgui.text(f"This will download and run the installer for:\n{label}")
            imgui.text_colored(_PREREQ_MUTED_COLOR, download_url)
            if component_key == "directx_runtime":
                # Quoted directly from Microsoft's own download page -- the
                # user should know this *before* agreeing, not after, same
                # transparency-first pattern as the pacing-clamp wording
                # elsewhere in this window.
                imgui.spacing()
                imgui.text_colored(_PREREQ_MISSING_COLOR, prereqs.DIRECTX_RUNTIME_CANNOT_UNINSTALL_NOTICE)
            imgui.spacing()
            if imgui.button("Install"):
                PREREQS.start_install(component_key)
                _prereq_install_pending = None
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("Cancel"):
                _prereq_install_pending = None
                imgui.close_current_popup()
        imgui.end_popup()


# -----------------------------------------------------------------------------
# Mod Repository section (App Settings window) -- a separate section from
# Prerequisites above: that's "is the right software installed," this is "does
# the actual Py4GW_Reforged mod code exist at the configured location, and is
# it current." Same confirm-before-acting pattern as the prereq installs above
# (clone/update are real, non-instant actions -- a confirm popup first, not an
# immediate action on click), but neither popup here can be triggered from
# outside this window (unlike the launch-confirm gate elsewhere in this file),
# so there's no cross-window ID-scope concern to design around here.
# -----------------------------------------------------------------------------

_MOD_REPO_CLONE_CONFIRM_POPUP_ID = "Clone Py4GW_Reforged?##mod_repo_clone_confirm"
_mod_repo_clone_pending = False

_MOD_REPO_UPDATE_CONFIRM_POPUP_ID = "Update Py4GW_Reforged?##mod_repo_update_confirm"
_mod_repo_update_pending = False


def _show_mod_repo_clone_confirm_popup() -> None:
    global _mod_repo_clone_pending
    if imgui.begin_popup_modal(
        _MOD_REPO_CLONE_CONFIRM_POPUP_ID, flags=int(imgui.WindowFlags_.always_auto_resize.value)
    )[0]:
        try:
            if _mod_repo_clone_pending:
                imgui.text("This will clone the full Py4GW_Reforged repository from:")
                imgui.text_colored(_PREREQ_MUTED_COLOR, load_mod_repo_url())
                imgui.text("into:")
                imgui.text_colored(_PREREQ_MUTED_COLOR, str(MOD_REPO_STATE.configured_path))
                imgui.spacing()
                # Real, tested number (see mod_repo.clone_mod_repo's own docstring),
                # not a guess -- the user should know this isn't instant before
                # clicking, not discover it by watching a UI that looks frozen.
                imgui.text_colored(
                    _PREREQ_MUTED_COLOR,
                    "This is the full mod repository (roughly 600MB) and can take a "
                    "minute or two depending on your connection.",
                )
                imgui.spacing()
                if imgui.button("Clone"):
                    MOD_REPO_STATE.start_clone()
                    _mod_repo_clone_pending = False
                    imgui.close_current_popup()
                imgui.same_line()
                if imgui.button("Cancel"):
                    _mod_repo_clone_pending = False
                    imgui.close_current_popup()
        finally:
            imgui.end_popup()


def _show_mod_repo_update_confirm_popup() -> None:
    global _mod_repo_update_pending
    if imgui.begin_popup_modal(
        _MOD_REPO_UPDATE_CONFIRM_POPUP_ID, flags=int(imgui.WindowFlags_.always_auto_resize.value)
    )[0]:
        try:
            if _mod_repo_update_pending:
                check = MOD_REPO_STATE.update_check
                behind_text = f" ({check.message})" if check is not None else ""
                imgui.text("This will fast-forward the checkout at:")
                imgui.text_colored(_PREREQ_MUTED_COLOR, str(MOD_REPO_STATE.configured_path))
                imgui.text(f"to the latest Py4GW_Reforged{behind_text}.")
                imgui.spacing()
                imgui.text_colored(
                    _PREREQ_MUTED_COLOR,
                    "Only ever fast-forwards -- refused automatically if the checkout "
                    "has any uncommitted changes, so nothing local is discarded.",
                )
                imgui.spacing()
                if imgui.button("Update"):
                    MOD_REPO_STATE.start_update()
                    _mod_repo_update_pending = False
                    imgui.close_current_popup()
                imgui.same_line()
                if imgui.button("Cancel"):
                    _mod_repo_update_pending = False
                    imgui.close_current_popup()
        finally:
            imgui.end_popup()


def _show_mod_repo_section() -> None:
    global _mod_repo_clone_pending, _mod_repo_update_pending

    imgui.text("Mod Repository (Py4GW_Reforged):")

    em = hello_imgui.em_size()
    imgui.text("Location:")
    imgui.same_line()
    style = imgui.get_style()
    button_w = imgui.calc_text_size("Browse...").x + style.frame_padding.x * 2
    avail_w = imgui.get_content_region_avail().x
    path_w = max(1.0, avail_w - button_w - style.item_spacing.x)
    imgui.set_next_item_width(path_w)
    imgui.input_text("##mod_repo_path", str(MOD_REPO_STATE.configured_path), flags=int(imgui.InputTextFlags_.read_only.value))
    imgui.same_line()
    if imgui.button("Browse...##mod_repo_path_browse", size=(button_w, 0)):
        chosen = _browse_for_folder(
            title="Select the Py4GW_Reforged location",
            initial_path=str(MOD_REPO_STATE.configured_path),
        )
        if chosen:
            MOD_REPO_STATE.set_configured_path(chosen)

    detection = MOD_REPO_STATE.detection
    if detection is None:
        imgui.text_colored(_PREREQ_MUTED_COLOR, "Checking...")
        return

    if detection.status == mod_repo.CheckoutStatus.NOT_FOUND:
        imgui.text_colored(_PREREQ_MISSING_COLOR, "No Py4GW_Reforged checkout found at this location.")
        if MOD_REPO_STATE.clone_in_progress:
            imgui.same_line()
            imgui.text_colored(_PREREQ_BUSY_COLOR, MOD_REPO_STATE.operation_status_text)
        else:
            imgui.same_line()
            if imgui.button("Clone Py4GW_Reforged"):
                _mod_repo_clone_pending = True
                imgui.open_popup(_MOD_REPO_CLONE_CONFIRM_POPUP_ID)
    elif detection.status == mod_repo.CheckoutStatus.NOT_A_GIT_REPO:
        imgui.text_colored(
            _PREREQ_MISSING_COLOR,
            "Found a folder here, but it isn't a git checkout -- can't check for updates.",
        )
    else:
        imgui.text_colored(_PREREQ_OK_COLOR, "Checkout found.")
        imgui.same_line()
        if MOD_REPO_STATE.checking_updates:
            imgui.text_colored(_PREREQ_BUSY_COLOR, "Checking for updates...")
        elif imgui.button("Check for updates"):
            MOD_REPO_STATE.run_check_updates_async()

        check = MOD_REPO_STATE.update_check
        if check is not None:
            if check.status == mod_repo.UpdateStatus.UP_TO_DATE:
                imgui.text_colored(_PREREQ_OK_COLOR, check.message)
            elif check.status == mod_repo.UpdateStatus.BEHIND:
                imgui.text_colored(_PREREQ_MISSING_COLOR, check.message)
                if MOD_REPO_STATE.update_in_progress:
                    imgui.same_line()
                    imgui.text_colored(_PREREQ_BUSY_COLOR, MOD_REPO_STATE.operation_status_text)
                else:
                    imgui.same_line()
                    if imgui.button("Update now"):
                        _mod_repo_update_pending = True
                        imgui.open_popup(_MOD_REPO_UPDATE_CONFIRM_POPUP_ID)
            else:
                # AHEAD or ERROR -- informational only, no fast-forward is
                # possible/needed either way, so no "Update now" button.
                imgui.text_colored(_PREREQ_MUTED_COLOR, check.message)

    if MOD_REPO_STATE.operation_done_message and not MOD_REPO_STATE.clone_in_progress and not MOD_REPO_STATE.update_in_progress:
        imgui.text_colored(_PREREQ_MUTED_COLOR, MOD_REPO_STATE.operation_done_message)

    _show_mod_repo_clone_confirm_popup()
    _show_mod_repo_update_confirm_popup()


# -----------------------------------------------------------------------------
# Export / Import Accounts section (App Settings window) -- app-native roster
# interchange (profiles + teams), passwords in plaintext so they survive the move
# to another machine/Windows user where the DPAPI blob couldn't be decrypted. The
# plaintext is gated behind an explicit warning-before-export confirm.
# -----------------------------------------------------------------------------

_EXPORT_CONFIRM_POPUP_ID = "Back up accounts?##roster_export_confirm"
_IMPORT_RESULT_POPUP_ID = "Import complete##roster_import_result"
_ROSTER_DEFAULT_FILENAME = "py4gw_reforged_roster.json"
_ROSTER_JSON_FILTER = "JSON files (*.json)\0*.json\0All files (*.*)\0*.*\0"
_ROSTER_WARNING_COLOR = (0.86, 0.35, 0.35, 1.0)

# Deferred so the blocking Save-As dialog runs *after* the confirm popup's
# begin/end block has fully closed, never mid-popup.
_export_browse_pending = False
_export_include_passwords = True
_roster_status_message = ""
_last_import_result: "Optional[roster_transfer.RosterImportResult]" = None


def _show_export_confirm_popup() -> None:
    global _export_browse_pending
    if imgui.begin_popup_modal(
        _EXPORT_CONFIRM_POPUP_ID, flags=int(imgui.WindowFlags_.always_auto_resize.value)
    )[0]:
        try:
            if _export_include_passwords:
                imgui.text("This file will contain your saved account passwords in plain text.")
                imgui.text_colored(
                    _PREREQ_MUTED_COLOR,
                    "Store it securely and delete it once you're done restoring it elsewhere.",
                )
            else:
                imgui.text("Back up your profiles and teams to a file.")
                imgui.text_colored(
                    _PREREQ_MUTED_COLOR,
                    "Passwords are not included -- restored profiles will need their passwords re-entered.",
                )
            imgui.spacing()
            if imgui.button("Choose file and back up..."):
                _export_browse_pending = True
                imgui.close_current_popup()
            imgui.same_line()
            if imgui.button("Cancel"):
                imgui.close_current_popup()
        finally:
            imgui.end_popup()


def _render_import_result_body(result: "roster_transfer.RosterImportResult") -> None:
    """Shared body for any import's result popup (native roster import, legacy
    old-launcher import, first-run auto-detect) -- counts, then any non-path import
    notes, then any missing-path warnings. Just the content; the caller owns the
    surrounding popup and its Close button."""
    imgui.text(f"Profiles: {result.added_profiles} added, {result.skipped_profiles} already present.")
    imgui.text(f"Teams: {result.added_teams} added, {result.skipped_teams} already present.")
    if result.warnings:
        imgui.spacing()
        imgui.text_colored(_ROSTER_WARNING_COLOR, "Some old-launcher settings weren't carried over:")
        for warning in result.warnings:
            imgui.text_colored(_PREREQ_MUTED_COLOR, warning)
    if result.path_warnings:
        imgui.spacing()
        imgui.text_colored(_ROSTER_WARNING_COLOR, "Some imported paths don't exist on this machine:")
        for warning in result.path_warnings:
            imgui.text_colored(_PREREQ_MUTED_COLOR, warning)
        imgui.spacing()
        imgui.text_colored(_PREREQ_MUTED_COLOR, "Fix these in each profile's Settings on this machine.")


def _show_import_result_popup() -> None:
    if imgui.begin_popup_modal(
        _IMPORT_RESULT_POPUP_ID, flags=int(imgui.WindowFlags_.always_auto_resize.value)
    )[0]:
        try:
            if _last_import_result is not None:
                _render_import_result_body(_last_import_result)
            imgui.spacing()
            if imgui.button("Close"):
                imgui.close_current_popup()
        finally:
            imgui.end_popup()


def _show_export_import_section() -> None:
    global _export_browse_pending, _roster_status_message, _last_import_result, _export_include_passwords
    imgui.text("Backup / Restore Accounts:")
    imgui.text_colored(_PREREQ_MUTED_COLOR, "Move your accounts to another computer, or just keep a backup.")
    _, _export_include_passwords = imgui.checkbox("Include passwords", _export_include_passwords)
    if imgui.button("Backup accounts..."):
        imgui.open_popup(_EXPORT_CONFIRM_POPUP_ID)
    imgui.same_line()
    if imgui.button("Restore accounts..."):
        chosen = _browse_for_file(title="Import accounts", filter_str=_ROSTER_JSON_FILTER)
        if chosen:
            _last_import_result = STATE.import_roster(chosen)
            _roster_status_message = ""
            imgui.open_popup(_IMPORT_RESULT_POPUP_ID)

    imgui.separator()
    imgui.spacing()

    imgui.text("Old Launcher Import:")
    imgui.text_colored(
        _PREREQ_MUTED_COLOR, "Have an accounts.json from the previous Python launcher? Import it below."
    )
    if imgui.button("Import"):
        chosen = _browse_for_file(
            title="Import from old launcher (accounts.json)", filter_str=_ROSTER_JSON_FILTER
        )
        if chosen:
            _last_import_result = STATE.import_legacy_accounts(chosen)
            _roster_status_message = ""
            imgui.open_popup(_IMPORT_RESULT_POPUP_ID)

    if _roster_status_message:
        imgui.text_colored(_PREREQ_MUTED_COLOR, _roster_status_message)

    _show_export_confirm_popup()
    # Run the blocking Save-As dialog outside the confirm popup's begin/end block.
    if _export_browse_pending:
        _export_browse_pending = False
        chosen = _browse_for_save_file(
            title="Back up accounts", filter_str=_ROSTER_JSON_FILTER,
            default_filename=_ROSTER_DEFAULT_FILENAME,
        )
        if chosen:
            STATE.export_roster(chosen, include_passwords=_export_include_passwords)
            _roster_status_message = f"Backed up to {chosen}"

    _show_import_result_popup()


_LEGACY_AUTODETECT_POPUP_ID = "Import old launcher accounts?##legacy_autodetect"
_legacy_autodetect_evaluated = False
_legacy_autodetect_pending: "Optional[tuple]" = None   # (Path, count) while confirming
_legacy_autodetect_result: "Optional[roster_transfer.RosterImportResult]" = None


def _show_legacy_autodetect_popup() -> None:
    """First-run offer: if there are zero local profiles and an old-launcher
    accounts.json sits next to the configured mod repo, offer to import it once.
    The zero-profiles gate is the whole guard -- it self-resolves the moment any
    profile exists (imported here or added any other way), so no persisted
    "don't ask again" flag is needed; the condition is only evaluated once per run.
    """
    global _legacy_autodetect_evaluated, _legacy_autodetect_pending, _legacy_autodetect_result

    if not _legacy_autodetect_evaluated:
        _legacy_autodetect_evaluated = True
        try:
            accounts_path = MOD_REPO_STATE.configured_path / "accounts.json"
            if not STATE.profiles and accounts_path.is_file():
                count = legacy_import.count_accounts(accounts_path)
                _legacy_autodetect_pending = (accounts_path, count)
                imgui.open_popup(_LEGACY_AUTODETECT_POPUP_ID)
        except (OSError, ValueError):
            _legacy_autodetect_pending = None

    if not imgui.begin_popup_modal(
        _LEGACY_AUTODETECT_POPUP_ID, flags=int(imgui.WindowFlags_.always_auto_resize.value)
    )[0]:
        return
    try:
        if _legacy_autodetect_result is not None:
            _render_import_result_body(_legacy_autodetect_result)
            imgui.spacing()
            if imgui.button("Close"):
                _legacy_autodetect_result = None
                imgui.close_current_popup()
        elif _legacy_autodetect_pending is not None:
            accounts_path, count = _legacy_autodetect_pending
            imgui.text("Found accounts.json from the old launcher at:")
            imgui.text_colored(_PREREQ_MUTED_COLOR, str(accounts_path))
            imgui.text(f"Import {count} account{'s' if count != 1 else ''} now?")
            imgui.spacing()
            if imgui.button("Import"):
                _legacy_autodetect_result = STATE.import_legacy_accounts(accounts_path)
                _legacy_autodetect_pending = None
                # Stay open, switching to the result state to show counts + warnings.
            imgui.same_line()
            if imgui.button("Skip"):
                _legacy_autodetect_pending = None
                imgui.close_current_popup()
    finally:
        imgui.end_popup()


def show_app_settings_window() -> None:
    global _dark_theme_enabled, _app_settings_autosize_frames_remaining

    if not STATE.app_settings_window_open:
        return

    em = hello_imgui.em_size()
    autosizing = _app_settings_autosize_frames_remaining > 0
    # Same real-measured auto-sizing the profile Settings window uses (see
    # show_settings_window): baseline is only the single pre-measurement frame's
    # size and the estimate fed to _settings_window_default_pos; AlwaysAutoResize
    # for the next few frames then fits the window to its real rendered content,
    # after which the flag drops and it becomes normally resizable. baseline_h is a
    # close estimate of the real fitted height so positioning doesn't clip at the
    # screen bottom before measurement takes over.
    baseline_w, baseline_h = em * 34.0, em * 36.0
    imgui.set_next_window_size((baseline_w, baseline_h), cond=imgui.Cond_.appearing.value)
    # Cap the width *only while auto-resizing* (Settings leaves its max unbounded):
    # App Settings has unbounded-width content -- the prereq diagnostic lines are
    # single unwrapped file paths (e.g. the full python.exe path) -- so an uncapped
    # AlwaysAutoResize balloons the window across the screen to fit the longest
    # path. Capping only during the autosize frames lets it fit the *height* (every
    # section visible without scrolling, the actual goal) with those paths clipping
    # at the edge as they already did, then lifts the cap so the window stays freely
    # resizable afterward.
    max_w = baseline_w if autosizing else 1.0e9
    imgui.set_next_window_size_constraints((em * 20.0, em * 12.0), (max_w, 1.0e9))
    imgui.set_next_window_pos(
        _settings_window_default_pos(baseline_w, baseline_h), cond=imgui.Cond_.appearing.value
    )

    flags = imgui.WindowFlags_.always_auto_resize.value if autosizing else 0

    expanded, STATE.app_settings_window_open = imgui.begin(
        "App Settings##launcher", STATE.app_settings_window_open, flags
    )

    if imgui.is_window_appearing():
        _app_settings_autosize_frames_remaining = _SETTINGS_AUTOSIZE_FRAMES
    elif _app_settings_autosize_frames_remaining > 0:
        _app_settings_autosize_frames_remaining -= 1
    if expanded:
        # Prerequisites are shown first, not buried under other settings --
        # GW1/Py4GW injection genuinely doesn't work without them. Checked
        # fresh (no caching) on every app start and again after any install
        # finishes; "Check now" lets the user force a re-check any other time.
        imgui.text("Prerequisites for Py4GW injection:")
        if PREREQS.checking and PREREQS.python_result is None:
            imgui.text_colored(_PREREQ_MUTED_COLOR, "Checking...")
        else:
            _draw_prereq_row(
                "Python 3.13.0 (32-bit)", PREREQS.python_result, "python", prereqs.PYTHON_DOWNLOAD_URL
            )
            vc = PREREQS.vcredist_result
            _draw_prereq_row(
                "VC++ Redistributable (x86)",
                None if vc is None else _VcRedistArchView(vc, "x86"),
                "vcredist_x86", prereqs.VCREDIST_2013_X86_URL,
            )
            _draw_prereq_row(
                "VC++ Redistributable (x64)",
                None if vc is None else _VcRedistArchView(vc, "x64"),
                "vcredist_x64", prereqs.VCREDIST_2013_X64_URL,
            )
            _draw_prereq_row(
                "DirectX End-User Runtime", PREREQS.directx_runtime_result,
                "directx_runtime", prereqs.DIRECTX_RUNTIME_DOWNLOAD_URL,
            )
        if PREREQS.install_done_message and PREREQS.install_in_progress is None:
            imgui.text_colored(_PREREQ_MUTED_COLOR, PREREQS.install_done_message)
        if imgui.button("Check now"):
            PREREQS.run_check_async()
        _show_prereq_install_confirm_popup()

        imgui.separator()
        imgui.spacing()

        _show_mod_repo_section()

        imgui.separator()
        imgui.spacing()

        _show_export_import_section()

        imgui.separator()
        imgui.spacing()

        imgui.text("Injection:")
        changed_multiclient, new_multiclient_enabled = imgui.checkbox(
            "Multiclient patch", STATE.multiclient_enabled
        )
        if changed_multiclient:
            STATE.set_multiclient_enabled(new_multiclient_enabled)
        imgui.text_colored(
            _PREREQ_MUTED_COLOR,
            "Required to run more than one Guild Wars 1 instance at once. Off disables\n"
            "Bulk Launch; single-profile launches aren't affected.",
        )

        changed_py4gw_injection, new_py4gw_injection_enabled = imgui.checkbox(
            "Py4GW injection", STATE.py4gw_injection_enabled
        )
        if changed_py4gw_injection:
            STATE.set_py4gw_injection_enabled(new_py4gw_injection_enabled)
        imgui.text_colored(
            _PREREQ_MUTED_COLOR,
            "Master switch across all profiles, independent of each profile's own toggle.",
        )

        imgui.separator()
        imgui.spacing()

        imgui.text("Delay between launches (seconds):")
        imgui.same_line()
        imgui.set_next_item_width(em * 6.0)
        # No UI-side min/max here on purpose -- the UI may show/accept any
        # value; the real safety floor/ceiling is enforced in
        # bulk_launch.clamp_pacing_seconds, in the code that actually executes
        # the wait, not here.
        changed, new_value = imgui.input_int("##bulk_pacing_seconds", STATE.bulk_launch_pacing_seconds)
        if changed:
            STATE.set_bulk_launch_pacing_seconds(new_value)

        imgui.separator()
        imgui.spacing()

        # Global setting (not per-profile), applied immediately on change --
        # not just on restart -- via set_theme(), same function used to
        # apply the persisted choice once at startup.
        changed_theme, new_dark_enabled = imgui.checkbox("Dark theme", _dark_theme_enabled)
        if changed_theme:
            _dark_theme_enabled = new_dark_enabled
            set_theme(dark=_dark_theme_enabled)
            save_dark_theme_enabled(_dark_theme_enabled)

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
    # (below) takes over after that, so this never affects an existing user, only the
    # first impression. Per hello_imgui's own docs this size is "handled as if
    # specified for a 96 PPI screen", i.e. it's already scaled for the actual display's
    # DPI internally. 600x430 re-tuned from the previous pass's 520x350 after the card
    # grid's padding bug and the ALL-view-vs-team-view toolbar height mismatch were both
    # fixed -- 520 width sat right at the boundary of fitting 2 columns once the padding
    # math was corrected (only 2 columns without a scrollbar present, dropping to 1 once
    # one appeared), and 350 height was tuned against the shorter ALL-view-only toolbar.
    # 600x430 gives a clean, stable 2-column x 3-row grid for a handful of profiles (with
    # margin to spare even once a scrollbar appears) and reads consistently across both
    # ALL and team views now that both share the same toolbar height -- checked visually
    # in both. Re-verified again after the tab strip replaced the </label/> switcher (a
    # taller header than the old one): still holds up with no clipping in ALL view, a
    # real team view, the sparse 2-profile state, and with enough teams to trigger the
    # tab strip's own overflow chip -- no change needed this time. resizable defaults to
    # True already, so this is a starting point, not a hard limit.
    runner_params.app_window_params.window_geometry.size = (600, 430)
    # Persist the main window's size/position across restarts (written to
    # imgui_app_window.ini alongside this launcher's own .ini). Off by default in
    # hello_imgui; nothing was persisting the OS-level window's geometry before this.
    runner_params.app_window_params.restore_previous_geometry = True

    runner_params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.provide_full_screen_window
    )
    runner_params.imgui_window_params.enable_viewports = True

    runner_params.callbacks.show_gui = gui
    runner_params.callbacks.pre_new_frame = _pre_new_frame_hooks

    hello_imgui.run(runner_params)


if __name__ == "__main__":
    main()
