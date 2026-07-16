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
GWL_STYLE = -16
WS_THICKFRAME = 0x00040000
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004


def ensure_native_resize_style(hwnd: int) -> None:
    """Add WS_THICKFRAME back onto a frameless window's real Win32 style.

    pywebview's `frameless=True` strips this -- confirmed directly (RELAY
    009): without it, DefWindowProc has no reason to treat a
    WM_NCLBUTTONDOWN/HTRIGHT (etc.) message as a real sizing-border grab, so
    `start_native_resize` was a silent no-op (ReleaseCapture + SendMessage
    both "succeeded," nothing actually moved). WS_THICKFRAME alone adds no
    visible chrome -- confirmed via screenshot, no doubled/native border
    appears.

    Deliberately NOT also adding WS_CAPTION here. That's the other half of
    what a genuinely native caption-drag (the mechanism Aero Snap hooks
    into) needs, and it was tested: it works, but Windows then paints a
    real native title bar on top of the custom HTML one (confirmed via
    screenshot -- a real, visible regression, not a clean fix). Suppressing
    that would need a WM_NCCALCSIZE override on top of this, which is
    exactly the "push further into deeper Win32 workarounds" this entry
    says to stop at and report on rather than route around silently.
    """
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_THICKFRAME)
    ctypes.windll.user32.SetWindowPos(
        hwnd, 0, 0, 0, 0, 0, SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
    )


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
