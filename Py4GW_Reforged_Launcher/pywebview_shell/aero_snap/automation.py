"""GUI automation harness for the Aero Snap investigation.

Consolidates the methodology from RELAY.md 009 (item-by-item) into reusable
helpers so each experiment doesn't re-derive it:

- Find a shell window by title substring (avoids the parent/child-PID gotcha
  entirely -- we don't care which PID owns it, only which HWND shows the
  title we launched with).
- Screenshot via PrintWindow(PW_RENDERFULLCONTENT=2) -- the only mode that
  captures WebView2's rendered content.
- Simulate a REAL hardware mouse drag (SetCursorPos + mouse_event, with
  incremental intermediate positions and short sleeps -- a single jump does
  not exercise a live drag/resize).
- GetWindowRect before/after to confirm what actually happened, never inferred
  from return codes.

NEVER calls win32gui.SetForegroundWindow on these windows (RELAY 009 item 1:
reproducibly triggers a pythonnet AccessibilityObject error storm). Hardware
mouse input via SetCursorPos/mouse_event lands on whatever is under the cursor
regardless of focus, so bringing the window forward isn't needed anyway.

32-bit process: GetWindowLongW/SetWindowLongW only (not ...LongPtrW).

Usage (from the shell venv):
  python -m pywebview_shell.aero_snap.automation find "<title substr>"
  python -m pywebview_shell.aero_snap.automation rect "<title substr>"
  python -m pywebview_shell.aero_snap.automation shot "<title substr>" out.png
  python -m pywebview_shell.aero_snap.automation drag <x0> <y0> <x1> <y1> [steps]
  python -m pywebview_shell.aero_snap.automation style "<title substr>"
"""
from __future__ import annotations

import sys
import time

import win32api
import win32con
import win32gui
import win32ui


def find_window(title_substr: str) -> int | None:
    matches: list[tuple[int, str]] = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        text = win32gui.GetWindowText(hwnd)
        if title_substr.lower() in text.lower():
            matches.append((hwnd, text))

    win32gui.EnumWindows(_cb, None)
    if not matches:
        return None
    # Prefer an exact-ish first hit; there should only be one per label.
    return matches[0][0]


def get_rect(hwnd: int) -> tuple[int, int, int, int]:
    return win32gui.GetWindowRect(hwnd)


def screenshot(hwnd: int, out_path: str) -> None:
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    w, h = r - l, b - t
    hdc = win32gui.GetWindowDC(hwnd)
    src = win32ui.CreateDCFromHandle(hdc)
    mem = src.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(src, w, h)
    mem.SelectObject(bmp)
    # PW_RENDERFULLCONTENT = 2 -- required for WebView2 content.
    import ctypes

    ctypes.windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), 2)
    bmp.SaveBitmapFile(mem, out_path + ".bmp")
    try:
        from PIL import Image

        Image.open(out_path + ".bmp").save(out_path)
    except Exception as exc:  # pragma: no cover - diagnostic only
        print(f"(png convert failed, .bmp kept: {exc})")
    win32gui.DeleteObject(bmp.GetHandle())
    mem.DeleteDC()
    src.DeleteDC()
    win32gui.ReleaseDC(hwnd, hdc)


def drag(x0: int, y0: int, x1: int, y1: int, steps: int = 20, settle: float = 0.35) -> None:
    """Real hardware-level mouse drag from (x0,y0) to (x1,y1) with intermediate
    positions -- exercises a live drag/resize, not a single teleport.
    """
    win32api.SetCursorPos((x0, y0))
    time.sleep(0.15)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.15)
    for i in range(1, steps + 1):
        x = int(x0 + (x1 - x0) * i / steps)
        y = int(y0 + (y1 - y0) * i / steps)
        win32api.SetCursorPos((x, y))
        time.sleep(0.02)
    # Let the OS settle on a snap preview before release.
    time.sleep(settle)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.15)


def get_style(hwnd: int) -> int:
    import ctypes

    return ctypes.windll.user32.GetWindowLongW(hwnd, -16) & 0xFFFFFFFF


def describe_style(style: int) -> str:
    bits = {
        "WS_CAPTION": 0x00C00000,
        "WS_THICKFRAME": 0x00040000,
        "WS_SYSMENU": 0x00080000,
        "WS_MINIMIZEBOX": 0x00020000,
        "WS_MAXIMIZEBOX": 0x00010000,
        "WS_BORDER": 0x00800000,
        "WS_DLGFRAME": 0x00400000,
        "WS_MAXIMIZE": 0x01000000,
    }
    present = [name for name, mask in bits.items() if (style & mask) == mask]
    return f"0x{style:08X}: {', '.join(present) if present else '(none of the tracked bits)'}"


def _main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "find":
        hwnd = find_window(argv[1])
        print(f"hwnd={hwnd} rect={get_rect(hwnd) if hwnd else None}")
    elif cmd == "rect":
        hwnd = find_window(argv[1])
        print(get_rect(hwnd) if hwnd else "not found")
    elif cmd == "shot":
        hwnd = find_window(argv[1])
        if hwnd is None:
            print("not found")
            return 1
        screenshot(hwnd, argv[2])
        print(f"saved {argv[2]} rect={get_rect(hwnd)}")
    elif cmd == "drag":
        x0, y0, x1, y1 = (int(a) for a in argv[1:5])
        steps = int(argv[5]) if len(argv) > 5 else 20
        drag(x0, y0, x1, y1, steps)
        print("drag done")
    elif cmd == "style":
        hwnd = find_window(argv[1])
        if hwnd is None:
            print("not found")
            return 1
        print(describe_style(get_style(hwnd)))
    else:
        print(f"unknown command: {cmd}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
