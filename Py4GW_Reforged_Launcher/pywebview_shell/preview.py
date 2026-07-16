"""Live snap-preview overlay.

Reproduces the translucent rectangle Windows shows in the target zone while you
drag toward a screen edge -- the last visibly-missing piece vs native Aero
Snap. A single layered, click-through, topmost Win32 popup that a dedicated
polling thread positions over the current snap zone during a drag.

Rendered with UpdateLayeredWindow (per-pixel alpha), not a flat
SetLayeredWindowAttributes tint: a light fill (~18%) with a crisper, more
opaque border (~66%), so it reads as a "ghost of the destination" rather than a
solid block. The colour is the app's theme ACCENT, pushed in via set_accent()
(the page reports its CSS --accent), so the preview tracks the user's theme
instead of a hardcoded blue.

Why a dedicated thread (not the pywebview UI thread): the overlay window is
created and updated all on ONE thread, so there are no cross-thread
window-handle hazards. pywebview's own message loop runs independently on the
main thread. The only cross-thread state is a plain bool (begin_drag/end_drag)
and the accent tuple (set_accent), which the GIL makes safe enough here.

Click-through (WS_EX_TRANSPARENT) + no-activate (WS_EX_NOACTIVATE) mean the
overlay never interferes with the drag underneath it; tool-window keeps it off
the taskbar.

DPI: the whole process is per-monitor-v2 aware (set at startup), which threads
inherit, so GetCursorPos / the snap geometry / the overlay rect are all in the
same physical-pixel space.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading
import time

import win32api
import win32con
import win32gui

from pywebview_shell import snap

# Look-and-feel. Alphas are 0-255; fill light, border crisp (Chris's call:
# ~15-20% fill, ~60-70% border). BORDER_PX is physical pixels.
_FILL_ALPHA = 46      # ~18%
_BORDER_ALPHA = 168   # ~66%
_BORDER_PX = 6
_DEFAULT_ACCENT = (0, 120, 215)  # fallback only; overridden by set_accent()

_ULW_ALPHA = 0x00000002
_AC_SRC_OVER = 0x00
_AC_SRC_ALPHA = 0x01

_gdi32 = ctypes.windll.gdi32
_user32 = ctypes.windll.user32


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


def _wndproc(hwnd, msg, wparam, lparam):
    # Plain function wndproc: pywin32's convenience dict-form lpfnWndProc raises
    # RegisterClass error 87 inside this pythonnet/WinForms process specifically.
    # UpdateLayeredWindow supplies the surface directly, so no WM_PAINT needed.
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def _premul(color, alpha):
    """One premultiplied BGRA pixel (what UpdateLayeredWindow's AC_SRC_ALPHA
    expects): each channel scaled by alpha/255, byte order B, G, R, A.
    """
    r, g, b = color
    return bytes((b * alpha // 255, g * alpha // 255, r * alpha // 255, alpha))


def _build_pixels(w, h, accent):
    """A w*h top-down BGRA buffer: light accent fill with a crisp accent border,
    built from row templates (fast; only rebuilt when rect or accent changes).
    """
    fill = _premul(accent, _FILL_ALPHA)
    border = _premul(accent, _BORDER_ALPHA)
    bpc = min(_BORDER_PX, w // 2, h // 2)
    row_border = border * w
    if bpc > 0 and w > 2 * bpc:
        row_interior = border * bpc + fill * (w - 2 * bpc) + border * bpc
    else:
        row_interior = fill * w
    mid = max(0, h - 2 * bpc)
    return row_border * bpc + row_interior * mid + row_border * bpc


class SnapPreview:
    def __init__(self) -> None:
        self._accent = _DEFAULT_ACCENT
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

    def set_accent(self, r: int, g: int, b: int) -> None:
        """Theme accent for the overlay fill/border. Called from the page's JS
        (which owns the theme) via the bridge; the poll loop rebuilds on change.
        """
        self._accent = (int(r), int(g), int(b))

    # --- overlay thread ---
    def _run(self) -> None:
        hinst = win32api.GetModuleHandle(None)
        wc = win32gui.WNDCLASS()
        wc.style = 0
        wc.lpfnWndProc = _wndproc
        wc.hInstance = hinst
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
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
        # Mark topmost once (hidden); UpdateLayeredWindow handles position/size.
        win32gui.SetWindowPos(
            self._hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
        )
        self._ready.set()

        shown = False
        last_key = None
        while True:
            win32gui.PumpWaitingMessages()
            accent = self._accent
            if self._active:
                zone, work = snap.zone_at_cursor()
                rect = snap.zone_rect(zone, *work) if zone is not None else None
            else:
                rect = None
            if rect is None:
                if shown:
                    win32gui.ShowWindow(self._hwnd, win32con.SW_HIDE)
                    shown = False
                    last_key = None
            else:
                key = (rect, accent)
                if key != last_key:
                    self._paint(rect, accent)
                    # Show + keep topmost without disturbing the position/size
                    # UpdateLayeredWindow just set. Idempotent; SW_SHOWNA alone
                    # left the window IsWindowVisible=0 on this stack.
                    win32gui.SetWindowPos(
                        self._hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
                        | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
                    )
                    shown = True
                    last_key = key
            time.sleep(0.016)

    def _paint(self, rect, accent) -> None:
        x, y, w, h = rect
        pixels = _build_pixels(w, h, accent)
        screen_dc = _user32.GetDC(0)
        mem_dc = _gdi32.CreateCompatibleDC(screen_dc)
        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # top-down
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0  # BI_RGB
        bits = ctypes.c_void_p()
        hbmp = _gdi32.CreateDIBSection(mem_dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        old = _gdi32.SelectObject(mem_dc, hbmp)
        ctypes.memmove(bits, bytes(pixels), len(pixels))
        blend = _BLENDFUNCTION(_AC_SRC_OVER, 0, 255, _AC_SRC_ALPHA)
        pt_dst = wt.POINT(x, y)
        size = _SIZE(w, h)
        pt_src = wt.POINT(0, 0)
        _user32.UpdateLayeredWindow(
            self._hwnd, screen_dc, ctypes.byref(pt_dst), ctypes.byref(size),
            mem_dc, ctypes.byref(pt_src), 0, ctypes.byref(blend), _ULW_ALPHA,
        )
        _gdi32.SelectObject(mem_dc, old)
        _gdi32.DeleteObject(hbmp)
        _gdi32.DeleteDC(mem_dc)
        _user32.ReleaseDC(0, screen_dc)
