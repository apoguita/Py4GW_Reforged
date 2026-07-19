"""Real (non-placeholder) launcher window entry point (RELAY 010) -- replaces
Phase A's 3-window inline-HTML demo (dev_notes/RELAY.md 008/009) with the
approved design (Guild Wars Launcher Redesign Round 4, see
dev_notes/mockups/KEEP_DISCARD_ALTER_ADD.md) hand-rebuilt as real files under
pywebview_shell/web/, plus one real data path (ShellBridge.list_profiles()).

One window, not three -- the approved design's Settings drawer slides in
*inside* the main window rather than opening as a separate OS window (a
genuine upgrade over the current shipped app's separate App Settings window,
per KEEP_DISCARD_ALTER_ADD.md), so Phase A's main/settings/app_settings
3-window shape no longer applies. All of Phase A's proven window mechanics
(DPI-awareness, native-HWND resize via edge/corner hit-zones, frameless
custom title bar, easy_drag dragging) carry over unchanged into this single
window's markup.

Frameless (dev_notes/RELAY.md 008): the app draws its own title row. Native
Aero Snap can't work here (RELAY 009 -- Windows only snaps during its own
modal caption-drag loop, which a frameless window can't enter without
WS_CAPTION, which repaints the native title bar; and easy_drag moves via
SetWindowPos, never entering that loop). Snap is instead reproduced
hand-rolled (snap.py + preview.py, dev_notes/AERO_SNAP_INVESTIGATION.md): the
bridge observes the title-bar drag (on_drag_start/on_drag_end from web/app.js)
and on release over a screen edge/corner applies the snapped rect itself --
half/quarter/maximize, restore-on-drag-away, and a live preview overlay drawn
in the theme's --accent. Not reproduced (accepted trade-off): the Win11 Snap
Layouts hover flyout and keyboard Win+arrow snap.

Run directly: .venv\\Scripts\\python.exe -m pywebview_shell.run_shell
"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import webview

from launcher_core import elevation, settings_store, window_control
from pywebview_shell.bridge import ShellBridge
from pywebview_shell.preview import SnapPreview
from pywebview_shell.window_shell import ensure_dpi_awareness, ensure_native_resize_style, wait_for_native_hwnd

if getattr(sys, "frozen", False):
    # RELAY 043: PyInstaller flattens the ENTRY-POINT script's own extraction
    # location to directly under sys._MEIPASS -- confirmed live against a
    # real built exe: __file__ resolved to "<_MEIPASS>/run_shell.py", not
    # "<_MEIPASS>/pywebview_shell/run_shell.py" the way every other module
    # in this package does, so plain __file__-relative resolution silently
    # pointed WEB_DIR at a nonexistent "<_MEIPASS>/web" and pywebview's own
    # local server 404'd on index.html. Same class of frozen-vs-dev gotcha
    # mod_root.py's own _mod_root() already documents for a different
    # path -- sys._MEIPASS is the correct root once frozen; the .spec's own
    # datas entry (`('pywebview_shell/web', 'pywebview_shell/web')`)
    # preserves that destination structure there, so this really does exist.
    WEB_DIR = Path(sys._MEIPASS) / "pywebview_shell" / "web"
else:
    WEB_DIR = Path(__file__).parent / "web"
RESIZE_MARGIN = 6
# LOGICAL px (pywebview's own unit for create_window's min_size). Single
# source of truth -- also handed to the bridge (set_min_size) so the
# hand-rolled Snap's quarter targets can clamp against it in physical px at
# whatever the actual DPI scale turns out to be (RELAY 012).
# RELAY 086: lowered from (560, 400) -- live-tested, not guessed, since the
# CSS's own headroom estimate can't account for cross-axis interaction (see
# below). At the OLD 560x400 floor, ~180px of vertical chrome (titlebar +
# header + action row + filter row) left comfortable room for the card grid
# + console bar; shrinking width alone wasn't the whole story, though --
# below ~340px wide, #action-row's buttons wrap to a 2nd line, which eats
# ~38px of EXTRA vertical space that a width-only or height-only test would
# never surface. Confirmed live by shrinking the actual running window,
# watching for real breakage (not just "cramped," which Chris explicitly
# wants) at each combination:
#   - Width alone (600 tall): clean at 320px; 290px wraps the header title
#     onto 2 lines AND clips card content behind a horizontal scrollbar.
#   - Height alone (600 wide, no wrap): clean at 250px; 240px clips/overlaps
#     the console bar's own text.
#   - BOTH at their independently-found floor (320x250) simultaneously:
#     broken -- the 2-line-wrapped action row (only present at narrow width)
#     ate enough extra height to push the card grid AND console bar
#     completely out of the visible window, invisible not just cramped.
#   - Re-tested height at the ACTUAL chosen width (320) to find the real
#     combined floor: clean at 300px, with a safety margin above the
#     270-290px zone where the console bar starts running right up against
#     the window edge. 320x300 landed on cleanly, matching every check in
#     the entry: nothing overlapping, nothing missing, nothing unreachable.
MIN_SIZE = (320, 300)


def _webview2_storage_path() -> str:
    """Return a stable, reused WebView2 user-data-dir, creating it if needed.

    RELAY 054: without this, pywebview's default (private_mode=True and no
    storage_path) makes its winforms backend set WebView2's UserDataFolder to
    `tempfile.TemporaryDirectory().name` (webview/platforms/winforms.py,
    init_storage). That idiom is a leak: the TemporaryDirectory object is
    discarded the instant `.name` is read, so its finalizer deletes the
    still-empty dir immediately -- then WebView2 re-creates and populates that
    exact path and nothing ever cleans it up. Net effect: one orphaned
    `%TEMP%\\tmpXXXX\\EBWebView` profile (~15-30MB) leaks on EVERY launch (68
    dirs / ~894MB seen in the wild, RELAY 022), and cold-start time measurably
    climbs as the count grows (confirmed: +~0.3-0.5s across a 40-launch run).

    Passing an explicit storage_path makes pywebview take its persistent
    branch and reuse ONE stable profile dir instead: no per-launch leak, no
    unbounded accumulation, and no delete-then-recreate window during cold
    start. Sharing a single user-data-dir across (rare) concurrent instances
    is WebView2's normal, supported mode -- it's exactly what pywebview itself
    does by default for every non-private app (a shared %APPDATA%/pywebview).
    """
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or tempfile.gettempdir()
    path = Path(base) / "Py4GW_Reforged_Launcher" / "webview2"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


# RELAY 054 root fix. on_shown fires as the top-level window is shown -- the
# exact moment WebView2 is running its cold-start composite. Calling
# ensure_native_resize_style right then adds WS_THICKFRAME and issues
# SetWindowPos(SWP_FRAMECHANGED) INTO that composite; under CPU/disk contention
# the reframe races the initial present and the content comes up blank-white
# (the window never even flips to visible), or presents at the pre-reframe
# client size and renders cut off on the right/bottom edges. Proven by a
# single-variable A/B under a 6-CPU-burner load: reframe applied in on_shown =
# 83% stuck (10/12); reframe deferred to after first present = 0% (0/12).
# 8s past 'shown' is well beyond any legitimate present (measured <5s even
# under heavy load), so the fallback only fires in the genuinely-stuck case --
# and applying the style even then is strictly better than permanently losing
# native edge-resize; the render watchdog handles that stuck case separately.
_REFRAME_AFTER_SHOW_TIMEOUT = 8.0


def _apply_resize_style_after_first_paint(hwnd: int) -> None:
    """Defer ensure_native_resize_style until WebView2 has presented its first
    frame, instead of reframing the window mid-composite (RELAY 054 root cause).

    Waiting for IsWindowVisible means the present that mattered has already
    happened, so adding the resize border afterward is just an ordinary
    steady-state style change (the window lives its entire life with
    WS_THICKFRAME anyway -- WebView2 handles frame-size changes routinely during
    normal use) rather than one racing the cold-start present. In the healthy
    fast case the window is visible almost immediately and this applies right
    away; it only actually defers when there IS a present gap -- which is
    exactly the loaded, race-prone case the reframe must stay out of. A timeout
    fallback still applies the style if 'visible' never arrives, so native
    edge-resize is never permanently lost. Daemon thread, same off-GUI-thread
    context ensure_native_resize_style already ran on when called from on_shown.
    """
    def apply() -> None:
        deadline = time.time() + _REFRAME_AFTER_SHOW_TIMEOUT
        while time.time() < deadline:
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                break
            time.sleep(0.05)
        ensure_native_resize_style(hwnd)

    threading.Thread(target=apply, name="deferred-reframe", daemon=True).start()


# RELAY 054 render watchdog. A healthy window becomes visible within ~1s
# (no load) and reliably under ~5s even under heavy CPU/disk contention
# (measured live), so 8s is comfortably past any legitimate slow start and
# only trips on the genuine stuck state. SW_MINIMIZE/SW_RESTORE is the exact
# repaint-forcing recovery confirmed to un-stick a blank window in place
# (RELAY 022's 2026-07-17 occurrence, and reproduced+re-confirmed here).
_RENDER_READY_TIMEOUT = 8.0
_RECOVER_ATTEMPTS = 2
_SW_MINIMIZE = 6
_SW_RESTORE = 9


def _start_render_watchdog(hwnd: int, bridge: ShellBridge) -> None:
    """Belt-and-suspenders net under the RELAY 054 root fix
    (`_apply_resize_style_after_first_paint`): the confirmed cause of the
    intermittent stuck/blank-white window was this app's own post-show reframe
    racing WebView2's cold-start present, and deferring that reframe drives the
    stuck rate to 0% under the same load that used to blank ~83% of launches.
    This watchdog stays as a cheap safety net for any residual cold-start
    stall from deeper in WebView2/pywebview that the app can't reach: under
    resource contention the content area can come up fully blank-white with the
    top-level window never even flipping to visible (`IsWindowVisible` stays 0)
    and not self-recovering by waiting.

    Root cause is NOT temp-dir accumulation (ruled out: crossing the old
    ~68-dir threshold with zero blanks when unloaded, and an explicit
    storage_path that stops the accumulation entirely does NOT lower the
    stuck rate under load) -- accumulation is a real but separate leak, fixed
    independently by `_webview2_storage_path`.

    Detects the stuck state via `IsWindowVisible` (the observed signature) and
    forces a repaint with the proven minimize/restore recovery, retrying a
    couple of times, instead of leaving the user staring at a blank window.
    Daemon thread -- never blocks shutdown, and a no-op on every healthy launch
    (returns the instant the window shows, which is almost always <2s).
    """
    def watch() -> None:
        deadline = time.time() + _RENDER_READY_TIMEOUT
        while time.time() < deadline:
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                return  # healthy -- shown well within budget, do nothing
            time.sleep(0.25)
        # Still not visible past the budget: treat as the stuck cold-start
        # race and force a repaint. Re-check after each attempt.
        for _ in range(_RECOVER_ATTEMPTS):
            bridge._record_console_line(
                "Window failed to render on start -- forcing a repaint (RELAY 054)", "err"
            )
            ctypes.windll.user32.ShowWindow(hwnd, _SW_MINIMIZE)
            time.sleep(1.0)
            ctypes.windll.user32.ShowWindow(hwnd, _SW_RESTORE)
            recheck = time.time() + 4.0
            while time.time() < recheck:
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    return
                time.sleep(0.25)

    threading.Thread(target=watch, name="render-watchdog", daemon=True).start()


def main() -> None:
    ensure_dpi_awareness()

    # RELAY 046: in dev-mode, Windows' taskbar groups this window's presence
    # under python.exe's own shared identity by default (no distinct
    # AppUserModelID set) -- confirmed live: window_control.set_window_icon
    # correctly changed the window's own WM_GETICON handles (both SMALL and
    # BIG extracted and pixel-verified as the real icon), but the taskbar
    # button itself kept showing python.exe's generic icon regardless, and
    # survived minimize/restore AND pin/unpin (both real, standard icon-
    # cache-refresh tricks that would have fixed a simple stale-cache case).
    # That specific symptom -- correct per-window icon, wrong taskbar icon,
    # immune to cache-refresh tricks -- is the known signature of taskbar
    # identity grouping, not a caching bug: explicitly giving this process
    # its own AppUserModelID (must be set before any window is created)
    # tells the shell to treat it as its own distinct app rather than
    # inheriting python.exe's. Harmless no-op once frozen (a real .exe
    # already has its own distinct identity from its own file path).
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Py4GW.ReforgedLauncher")
    except OSError:
        pass

    # RELAY 035 -- "run as administrator" is sticky: honored on every normal
    # start (double-click, Launch.bat), not just the moment the App Settings
    # toggle is flipped. A declined UAC prompt here falls through to a
    # normal non-elevated start rather than refusing to launch at all --
    # the setting stays True (elevation.relaunch_elevated raises without
    # touching settings_store), so the next start prompts again.
    if settings_store.load_run_as_admin_enabled() and not elevation.is_elevated():
        try:
            elevation.relaunch_elevated()
        except OSError:
            pass
        else:
            return

    # Snap-preview overlay for the hand-rolled Aero Snap (see this module's
    # docstring). Owns its own thread + layered window; the page reports the
    # theme accent into it via bridge.set_accent().
    preview = SnapPreview()
    preview.set_min_size(*MIN_SIZE)

    bridge = ShellBridge("main")
    bridge.set_preview(preview)
    bridge.set_min_size(*MIN_SIZE)
    window = webview.create_window(
        "Py4GW Reforged Launcher",
        url=str(WEB_DIR / "index.html"),
        js_api=bridge,
        # Default first-run size, tuned so the ALL/team card grid renders
        # exactly 2 columns x 4 rows (8 cards) with no scrollbar and no
        # leftover slack below the last row -- confirmed by measuring a
        # live, user-resized window pixel-by-pixel at 100% DPI (target
        # OUTER rect 585x778; see dev_notes/RELAY.md's footnote after
        # entry 027 for the exact measurements this came from).
        #
        # The values below are NOT 585/778 directly -- create_window's own
        # width/height consistently produce a smaller real GetWindowRect
        # than requested (confirmed reproducibly: the old 1000x720 default
        # measured 984x681 in every screenshot this app has ever had taken
        # of it, a constant (16, 39) shortfall). Compensated for here so
        # the ACTUAL window really is 585x778, not 569x739.
        width=601,
        height=817,
        min_size=MIN_SIZE,
        frameless=True,
        easy_drag=False,  # we move the window ourselves (bridge.drag_tick, wired
                          # from the title bar in web/app.js). easy_drag armed on
                          # a mousedown ANYWHERE and jumped the window by the
                          # WS_THICKFRAME border -- see bridge.on_drag_start.
    )
    bridge.bind_window(window)

    # Seeded (not push_event'd -- see _record_console_line's own docstring)
    # before the page loads, so get_console_lines() picks it up on the
    # normal load path. Fires whenever this session is genuinely elevated
    # AND the toggle is on -- covers both "just relaunched via the gate
    # above" and "already elevated some other way with the toggle already
    # saved on," both real and both worth confirming, not just the former.
    if settings_store.load_run_as_admin_enabled() and elevation.is_elevated():
        bridge._record_console_line("Launcher will run elevated (admin)", "acc")

    def on_shown():
        hwnd = wait_for_native_hwnd(window)
        print(f"[shell] main: hwnd={hwnd!r}")
        if hwnd is not None:
            bridge.bind_hwnd(hwnd)
            _apply_resize_style_after_first_paint(hwnd)
            # RELAY 046: dev-mode only. Confirmed empirically (real
            # WM_GETICON handle extracted and pixel-compared against
            # assets/python_icon.ico, both a built .exe and a live
            # screenshot) that a BUILT .exe's live window ALREADY shows the
            # real icon in taskbar/Alt-Tab for free -- Windows falls back
            # to the process's own embedded icon resource (this .spec's
            # own icon= EXE option, RELAY 043) with zero runtime call
            # needed, so calling this there too would be redundant, not
            # just harmless -- skipped rather than also bundling the icon
            # as a runtime datas asset it would never actually use.
            # Dev-mode has no such resource (confirmed the same way: the
            # extracted icon was python.exe's own generic icon, not ours,
            # and Chris independently confirmed this live) -- this is the
            # only case that actually needs the explicit WM_SETICON call.
            # Frameless (no WS_CAPTION): there is no native title-bar icon
            # slot to fill either way -- this affects the taskbar/Alt-Tab
            # icon only, confirmed via the same real screenshot check.
            if not getattr(sys, "frozen", False):
                icon_path = Path(__file__).parent.parent / "assets" / "python_icon.ico"
                window_control.set_window_icon(hwnd, str(icon_path))
            _start_render_watchdog(hwnd, bridge)
        preview.start()

    webview.start(on_shown, debug=False, storage_path=_webview2_storage_path())


if __name__ == "__main__":
    main()
