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
Aero Snap does not work (RELAY 009 -- a real, structural gap; see that
entry's summary for the full investigation and hand-off).

Run directly: .venv\\Scripts\\python.exe -m pywebview_shell.run_shell
"""
from __future__ import annotations

from pathlib import Path

import webview

from pywebview_shell.bridge import ShellBridge
from pywebview_shell.window_shell import ensure_dpi_awareness, ensure_native_resize_style, wait_for_native_hwnd

WEB_DIR = Path(__file__).parent / "web"
RESIZE_MARGIN = 6


def main() -> None:
    ensure_dpi_awareness()

    bridge = ShellBridge("main")
    window = webview.create_window(
        "Py4GW Reforged Launcher",
        url=str(WEB_DIR / "index.html"),
        js_api=bridge,
        width=1000,
        height=720,
        min_size=(560, 400),
        frameless=True,
        easy_drag=True,  # dragging stays on pywebview's own mechanism
                         # (proven working, RELAY 006/008/009)
    )
    bridge.bind_window(window)

    def on_shown():
        hwnd = wait_for_native_hwnd(window)
        print(f"[shell] main: hwnd={hwnd!r}")
        if hwnd is not None:
            bridge.bind_hwnd(hwnd)
            ensure_native_resize_style(hwnd)

    webview.start(on_shown, debug=False)


if __name__ == "__main__":
    main()
