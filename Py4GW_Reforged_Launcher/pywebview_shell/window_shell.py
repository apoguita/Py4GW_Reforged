"""Window creation helpers: DPI-awareness and native-HWND readiness -- the
parts of the pywebview shell that are pure Win32 mechanics, independent of
any particular window's content or the JS bridge.

No DWM/dark-title-bar code here -- confirmed unnecessary for this app.
Windows are frameless (custom HTML/CSS title bar, no native OS caption), a
deliberate call made after hands-on testing of both bordered and frameless
(dev_notes/RELAY.md 008): the app draws its own title row, so there's no
native caption left to theme. The bordered/DWM path was fully proven working
in spikes/pywebview/ (RELAY 006) and is preserved there and in git history,
not carried into the real shell since it isn't needed.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time
from typing import Optional

import webview

_dpi_awareness_set = False


def ensure_dpi_awareness() -> bool:
    """Call once, before any window is created. Idempotent -- safe to call
    more than once, only makes the real ctypes call the first time. Same
    call (`SetProcessDpiAwarenessContext(-4)`, i.e.
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2) this app already makes
    before creating its hello_imgui/GLFW window today.
    """
    global _dpi_awareness_set
    if _dpi_awareness_set:
        return True
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        _dpi_awareness_set = True
    except Exception:
        _dpi_awareness_set = False
    return _dpi_awareness_set


WM_NCLBUTTONDOWN = 0x00A1
WM_NCPAINT = 0x0085
GWL_STYLE = -16
GWLP_WNDPROC = -4
WS_THICKFRAME = 0x00040000
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004

_WNDPROC_TYPE = ctypes.WINFUNCTYPE(
    ctypes.c_long, wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM
)
_original_wndprocs: dict[int, int] = {}
_wndproc_callbacks: list = []  # keep ctypes callback objects alive -- GC'd otherwise
_border_colors: dict[int, tuple[int, int, int]] = {}  # per-window RGB, see set_border_color

# ctypes.windll defaults every undeclared function to c_int in/out (32-bit).
# GetWindowDC returns a real HDC (pointer-sized -- 64 bits on this process),
# so without an explicit restype it gets truncated/sign-extended into a
# 32-bit int (this is why it printed as a large negative number). Passing
# that corrupted value back into FillRect/ReleaseDC as another undeclared
# (also-c_int) argument re-widens it via sign-extension instead of
# zero-extension, producing a *different* 64-bit pointer than the one
# GetWindowDC actually returned. Declaring real handle-sized types here
# fixes the round-trip.
ctypes.windll.user32.GetWindowDC.restype = wt.HDC
ctypes.windll.user32.GetWindowDC.argtypes = [wt.HWND]
ctypes.windll.user32.ReleaseDC.restype = ctypes.c_int
ctypes.windll.user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
ctypes.windll.gdi32.CreateSolidBrush.restype = wt.HBRUSH
ctypes.windll.gdi32.CreateSolidBrush.argtypes = [wt.COLORREF]
ctypes.windll.gdi32.DeleteObject.restype = ctypes.c_int
ctypes.windll.gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
ctypes.windll.user32.FillRect.restype = ctypes.c_int
ctypes.windll.user32.FillRect.argtypes = [wt.HDC, ctypes.POINTER(wt.RECT), wt.HBRUSH]


def set_border_color(hwnd: int, r: int, g: int, b: int) -> None:
    """Update the color `_paint_nonclient_border` fills the native resize-
    border margin with for this window. The page reports its current theme
    color into this (same shape as bridge.set_accent for the Snap preview)
    so the margin tracks theme changes instead of staying a fixed guess.
    """
    _border_colors[hwnd] = (r, g, b)


def _paint_nonclient_border(hwnd: int) -> None:
    """Fill the native WS_THICKFRAME resize-border margin with a solid color
    instead of leaving it unpainted (RELAY 013 fix).

    Root cause (confirmed live, not guessed): WS_THICKFRAME alone reserves a
    real non-client margin (`GetClientRect`'s screen origin was inset from
    `GetWindowRect`'s by several physical px on every side) that nothing
    paints, since this window has no WS_CAPTION/native chrome telling DWM
    what color that margin should be -- confirmed as a genuine visible gap
    (a solid-color desktop wallpaper bled through it in a real screenshot,
    not just a PrintWindow-capture artifact).

    Deliberately NOT touched via WM_NCCALCSIZE (tried first, reverted): both
    the "blind return 0" and "call original then restore rgrc[0]" variants
    eliminate the margin, but confirmed live that BOTH also degrade a native
    edge resize into a plain window move -- DefWindowProc's SC_SIZE loop
    needs the real non-client geometry from the untouched original proc to
    track a resize correctly. Painting the existing margin instead of
    resizing it away leaves that geometry completely alone, so the sizing
    loop is never at risk.
    """
    color = _border_colors.get(hwnd, (16, 19, 42))  # default: Indigo Aurora's --rail
    window_rect = wt.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
    win_w = window_rect.right - window_rect.left
    win_h = window_rect.bottom - window_rect.top

    client_rect = wt.RECT()
    ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(client_rect))
    client_origin = wt.POINT(0, 0)
    ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(client_origin))
    # Insets, translated into this window's own DC-local coordinate space
    # (GetWindowDC's origin is the window's own top-left corner, not the
    # screen's) -- computed fresh each call rather than assumed constant,
    # since it can vary by DPI/system metrics.
    left_inset = client_origin.x - window_rect.left
    top_inset = client_origin.y - window_rect.top
    right_inset = win_w - (left_inset + client_rect.right)
    bottom_inset = win_h - (top_inset + client_rect.bottom)
    if left_inset <= 0 and top_inset <= 0 and right_inset <= 0 and bottom_inset <= 0:
        return  # nothing to paint -- no margin exists (or window not yet sized)

    hdc = ctypes.windll.user32.GetWindowDC(hwnd)
    try:
        brush = ctypes.windll.gdi32.CreateSolidBrush(color[0] | (color[1] << 8) | (color[2] << 16))
        try:
            for rect in (
                (0, 0, win_w, top_inset),  # top strip
                (0, win_h - bottom_inset, win_w, win_h),  # bottom strip
                (0, 0, left_inset, win_h),  # left strip
                (win_w - right_inset, 0, win_w, win_h),  # right strip
            ):
                r = wt.RECT(*rect)
                ctypes.windll.user32.FillRect(hdc, ctypes.byref(r), brush)
        finally:
            ctypes.windll.gdi32.DeleteObject(brush)
    finally:
        ctypes.windll.user32.ReleaseDC(hwnd, hdc)


def _make_paint_border_wndproc(hwnd: int):
    def wndproc(hwnd_, msg, wparam, lparam):
        result = ctypes.windll.user32.CallWindowProcW(_original_wndprocs[hwnd], hwnd_, msg, wparam, lparam)
        if msg == WM_NCPAINT:
            _paint_nonclient_border(hwnd_)
        return result

    return wndproc


def _fix_native_border_paint(hwnd: int) -> None:
    """Subclass this window's WndProc (in-process only -- this must run from
    inside the same process that owns `hwnd`; a previous attempt to do this
    live from a separate script was invalid and Windows correctly refused
    it) to paint the WS_THICKFRAME margin on every WM_NCPAINT, instead of
    leaving it as a visible gap. See `_paint_nonclient_border` for why this
    approach (paint over it) was chosen over eliminating the margin via
    WM_NCCALCSIZE (tried first -- broke native resize).
    """
    original = ctypes.windll.user32.GetWindowLongW(hwnd, GWLP_WNDPROC)
    _original_wndprocs[hwnd] = original
    new_proc = _WNDPROC_TYPE(_make_paint_border_wndproc(hwnd))
    _wndproc_callbacks.append(new_proc)
    ctypes.windll.user32.SetWindowLongW(hwnd, GWLP_WNDPROC, ctypes.cast(new_proc, ctypes.c_void_p).value)
    ctypes.windll.user32.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0, SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
    )


def ensure_native_resize_style(hwnd: int) -> None:
    """Add WS_THICKFRAME back onto a frameless window's real Win32 style,
    then paint over the native non-client border it introduces (RELAY 013).

    pywebview's `frameless=True` strips WS_THICKFRAME -- confirmed directly
    (RELAY 009): without it, DefWindowProc has no reason to treat a
    WM_NCLBUTTONDOWN/HTRIGHT (etc.) message as a real sizing-border grab, so
    `start_native_resize` was a silent no-op (ReleaseCapture + SendMessage
    both "succeeded," nothing actually moved).

    Deliberately NOT adding WS_CAPTION here. That's the other half of what a
    genuinely native caption-drag (the mechanism Aero Snap hooks into) would
    need, and it was tested (RELAY 009): it works, but Windows then paints a
    real native title bar on top of the custom HTML one -- a real, visible
    regression, and this app doesn't need native caption-drag anymore
    anyway (RELAY 012's hand-rolled Snap covers it).
    """
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_THICKFRAME)
    ctypes.windll.user32.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0, SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
    )
    _fix_native_border_paint(hwnd)


# Confirmed against win32con directly (RELAY 009), not from memory. HTCAPTION
# (2) deliberately isn't included -- dragging stays on pywebview's own
# easy_drag (see ensure_native_resize_style's docstring for why the native
# caption-drag alternative wasn't adopted here).
_RESIZE_EDGE_HITTEST = {
    "left": 10,  # HTLEFT
    "right": 11,  # HTRIGHT
    "top": 12,  # HTTOP
    "topleft": 13,  # HTTOPLEFT
    "topright": 14,  # HTTOPRIGHT
    "bottom": 15,  # HTBOTTOM
    "bottomleft": 16,  # HTBOTTOMLEFT
    "bottomright": 17,  # HTBOTTOMRIGHT
}


def start_native_resize(hwnd: int, edge: str) -> bool:
    """Hand an in-progress mouse-down off to Windows' own native sizing loop,
    as if the user had grabbed a real (native) window edge -- the same
    mechanism a normal bordered/WS_THICKFRAME window gets for free, which is
    also what Aero Snap hooks into. Necessary here because frameless windows
    have no such edge for a human to grab: this app draws its own thin
    hit-zone strips in HTML/CSS, and JS mousedown on one of them calls this
    (via the bridge) instead.

    `ReleaseCapture()` first is required -- WebView2 is a full-bleed child
    window and already holds mouse capture from the JS mousedown that
    triggered this call; without releasing it, the top-level window's
    `SendMessage(WM_NCLBUTTONDOWN, ...)` below wouldn't actually start its
    own sizing loop. Confirmed this parent/child input relationship directly
    in RELAY 008 (a WM_NCHITTEST hook on the parent never even saw clicks
    landing inside the WebView2-covered area for the same reason).

    Returns False for an unrecognized edge name rather than raising --
    a bad edge string is a caller/JS-side bug, not something that should
    crash the resize attempt for every other edge.
    """
    hittest_code = _RESIZE_EDGE_HITTEST.get(edge)
    if hittest_code is None:
        return False
    ctypes.windll.user32.ReleaseCapture()
    ctypes.windll.user32.SendMessageW(hwnd, WM_NCLBUTTONDOWN, hittest_code, 0)
    return True


def get_dpi_scale(hwnd: int) -> float:
    """Return this window's current per-monitor DPI scale (1.0 == 100%,
    2.5 == 250%), via `GetDpiForWindow` (Windows 10 1607+, matches this
    app's baseline -- same API family as `SetProcessDpiAwarenessContext`
    above). Used by the hand-rolled Aero Snap fix (RELAY 012) to convert
    `create_window`'s `min_size` -- which pywebview treats as LOGICAL px --
    into physical px for comparison against monitor work-area rects, which
    are always physical.
    """
    dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
    return dpi / 96.0


def wait_for_native_hwnd(window: webview.Window, retries: int = 10, delay: float = 0.3) -> Optional[int]:
    """Poll this specific window's own `.native` property until it's ready.

    Confirmed in RELAY 006/008: secondary windows aren't necessarily ready
    the instant webview.start()'s callback fires for the first window --
    a single fixed sleep covering every window produces false negatives
    (looked like a real pywebview limitation the first time this was hit,
    wasn't). Returns the real HWND, or None if it never became ready within
    the retry budget. Kept here (rather than dropped along with the DWM
    code) since a real native handle is still generally useful -- taskbar
    grouping, icon-setting, etc. -- independent of title-bar theming.
    """
    for _ in range(retries):
        native = window.native
        if native is not None:
            return int(native.Handle.ToInt64())
        time.sleep(delay)
    return None
