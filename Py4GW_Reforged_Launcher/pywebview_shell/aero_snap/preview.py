"""Live snap-preview overlay (Attempt 2c).

Reproduces the translucent rectangle Windows shows in the target zone while you
drag toward a screen edge -- the last visibly-missing piece vs native Aero
Snap. Implemented as a single layered, click-through, topmost Win32 popup that
a dedicated polling thread positions over the current snap zone during a drag.

Why a dedicated thread with its own message loop (not the pywebview UI thread):
the overlay window is created, timed, and updated all on ONE thread, so there
are no cross-thread window-handle hazards. pywebview's own message loop keeps
running independently on the main thread. The only cross-thread state is a
plain bool (begin_drag/end_drag), which the GIL makes safe enough here.

Click-through (WS_EX_TRANSPARENT) + no-activate (WS_EX_NOACTIVATE) mean the
overlay never interferes with the drag underneath it; tool-window keeps it off
the taskbar; layered + SetLayeredWindowAttributes(LWA_ALPHA) makes the class
background brush render as a translucent tint with no WM_PAINT handling.

DPI: the whole process is per-monitor-v2 aware (set at startup), which threads
inherit, so GetCursorPos / SetWindowPos / the snap geometry are all in the same
physical-pixel space.
"""
from __future__ import annotations

import threading
import time

import win32api
import win32con
import win32gui

from pywebview_shell.aero_snap import snap

LWA_ALPHA = 0x00000002

# Module-level fill brush + color for the overlay. Set once by the first
# SnapPreview instance; painted explicitly in _wndproc (relying on the class
# background brush alone left the layered surface transparent in practice).
_FILL_COLOR = (0x3D, 0x7E, 0xFF)
_fill_brush = None


def _get_fill_brush():
    global _fill_brush
    if _fill_brush is None:
        _fill_brush = win32gui.CreateSolidBrush(win32api.RGB(*_FILL_COLOR))
    return _fill_brush


def _wndproc(hwnd, msg, wparam, lparam):
    # A dict-based lpfnWndProc (pywin32's convenience form) raises RegisterClass
    # error 87 inside this pythonnet/WinForms process specifically -- so this is
    # a real function. Paint the fill explicitly on WM_PAINT/WM_ERASEBKGND;
    # the class brush alone did not render on the layered surface.
    if msg == win32con.WM_PAINT:
        hdc, ps = win32gui.BeginPaint(hwnd)
        rc = win32gui.GetClientRect(hwnd)
        win32gui.FillRect(hdc, rc, _get_fill_brush())
        win32gui.EndPaint(hwnd, ps)
        return 0
    if msg == win32con.WM_ERASEBKGND:
        rc = win32gui.GetClientRect(hwnd)
        win32gui.FillRect(wparam, rc, _get_fill_brush())
        return 1
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


class SnapPreview:
    def __init__(self, alpha: int = 90, color: tuple[int, int, int] = (0x3D, 0x7E, 0xFF)) -> None:
        self._alpha = alpha
        self._color = color
        self._hwnd: int | None = None
        self._active = False
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="SnapPreview", daemon=True)

    def start(self) -> None:
        self._thread.start()
        self._ready.wait(3)

    def begin_drag(self) -> None:
        self._active = True

    def end_drag(self) -> None:
        self._active = False

    # --- overlay thread ---
    def _run(self) -> None:
        hinst = win32api.GetModuleHandle(None)
        wc = win32gui.WNDCLASS()
        wc.style = 0
        wc.lpfnWndProc = _wndproc
        wc.hInstance = hinst
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32gui.CreateSolidBrush(win32api.RGB(*self._color))
        wc.lpszClassName = "AeroSnapPreviewOverlay"
        try:
            atom = win32gui.RegisterClass(wc)
        except win32gui.error as exc:
            print(f"[preview] RegisterClass failed: {exc!r}", flush=True)
            self._ready.set()
            return
        exstyle = (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_TOPMOST
            | win32con.WS_EX_NOACTIVATE
            | win32con.WS_EX_TOOLWINDOW
        )
        self._hwnd = win32gui.CreateWindowEx(
            exstyle, atom, None, win32con.WS_POPUP, 0, 0, 10, 10, 0, 0, hinst, None
        )
        win32gui.SetLayeredWindowAttributes(self._hwnd, 0, self._alpha, LWA_ALPHA)
        self._ready.set()

        # Drive updates from a plain poll loop on this thread (no WM_TIMER):
        # PumpWaitingMessages keeps the layered surface painted; the poll reads
        # the cursor and positions/shows/hides the overlay over the snap zone.
        shown = False
        last_rect = None
        while True:
            win32gui.PumpWaitingMessages()
            if self._active:
                zone, work = snap.zone_at_cursor()
                rect = snap.zone_rect(zone, *work) if zone is not None else None
            else:
                rect = None
            if rect is None:
                if shown:
                    win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
                    shown = False
                    last_rect = None
            else:
                if rect != last_rect:
                    x, y, w, h = rect
                    win32gui.SetWindowPos(
                        self._hwnd,
                        win32con.HWND_TOPMOST,
                        x, y, w, h,
                        win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
                    )
                    win32gui.InvalidateRect(self._hwnd, None, True)
                    last_rect = rect
                    shown = True
            time.sleep(0.016)
