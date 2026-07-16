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
