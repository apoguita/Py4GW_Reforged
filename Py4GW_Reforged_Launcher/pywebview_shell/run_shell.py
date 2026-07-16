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

from pathlib import Path

import webview

from pywebview_shell.bridge import ShellBridge
from pywebview_shell.preview import SnapPreview
from pywebview_shell.window_shell import ensure_dpi_awareness, ensure_native_resize_style, wait_for_native_hwnd

WEB_DIR = Path(__file__).parent / "web"
RESIZE_MARGIN = 6
# LOGICAL px (pywebview's own unit for create_window's min_size). Single
# source of truth -- also handed to the bridge (set_min_size) so the
# hand-rolled Snap's quarter targets can clamp against it in physical px at
# whatever the actual DPI scale turns out to be (RELAY 012).
MIN_SIZE = (560, 400)


def main() -> None:
    ensure_dpi_awareness()

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
        width=1000,
        height=720,
        min_size=MIN_SIZE,
        frameless=True,
        easy_drag=False,  # we move the window ourselves (bridge.drag_tick, wired
                          # from the title bar in web/app.js). easy_drag armed on
                          # a mousedown ANYWHERE and jumped the window by the
                          # WS_THICKFRAME border -- see bridge.on_drag_start.
    )
    bridge.bind_window(window)

    def on_shown():
        hwnd = wait_for_native_hwnd(window)
        print(f"[shell] main: hwnd={hwnd!r}")
        if hwnd is not None:
            bridge.bind_hwnd(hwnd)
            ensure_native_resize_style(hwnd)
        preview.start()

    webview.start(on_shown, debug=False)


if __name__ == "__main__":
    main()
