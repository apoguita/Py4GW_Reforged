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
import sys
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
    # config_seeding.py's own _mod_root() already documents for a different
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
MIN_SIZE = (560, 400)


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
            ensure_native_resize_style(hwnd)
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
        preview.start()

    webview.start(on_shown, debug=False)


if __name__ == "__main__":
    main()
