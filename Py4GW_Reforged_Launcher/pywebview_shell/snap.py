"""Hand-rolled Aero-Snap geometry + application (Attempt 2).

The premise (proven in Attempt 1 + RELAY 009): a frameless window can't use
Windows' own native move loop without WS_CAPTION (which repaints the native
title bar), and easy_drag moves via SetWindowPos so Windows never runs the
snap-aware modal loop at all. So instead of asking Windows to snap for us, we
detect the drag-release ourselves and reproduce the snapped *result* with our
own SetWindowPos -- no WS_CAPTION, no WM_NCCALCSIZE, nothing that touches the
path RELAY 009 found broken.

This module is deliberately split into:
- classify_zone(): PURE geometry (cursor + monitor rects -> a Zone), unit-
  testable with no live window.
- zone_rect(): PURE geometry (Zone + work area -> target x/y/w/h).
- apply_snap(): the only impure part -- reads the real cursor + monitor via
  Win32 and calls SetWindowPos.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from enum import Enum
from typing import Optional


class Zone(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    MAX = "max"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


# Cursor must be within this many *physical* pixels of a monitor edge for any
# snap to trigger at all (matches how Windows only snaps when the pointer
# actually reaches the screen edge). Tuned live below.
EDGE_TRIGGER = 8

# If, while at an edge, the cursor is also within this many pixels of a
# perpendicular edge, it's a corner (quarter) rather than a half/maximize.
CORNER_BAND = 140


def classify_zone(
    cx: int,
    cy: int,
    mon_left: int,
    mon_top: int,
    mon_right: int,
    mon_bottom: int,
    edge_trigger: int = EDGE_TRIGGER,
    corner_band: int = CORNER_BAND,
) -> Optional[Zone]:
    """Map a cursor position to a snap Zone, using the *monitor* rectangle
    (full screen, incl. under the taskbar) for edge detection -- you drag to
    the physical screen edge. Returns None if not near any snap edge.
    """
    at_left = cx <= mon_left + edge_trigger
    at_right = cx >= mon_right - edge_trigger
    at_top = cy <= mon_top + edge_trigger
    at_bottom = cy >= mon_bottom - edge_trigger

    near_top = cy <= mon_top + corner_band
    near_bottom = cy >= mon_bottom - corner_band
    near_left = cx <= mon_left + corner_band
    near_right = cx >= mon_right - corner_band

    # Corners take priority: at a side/top/bottom edge AND close to a
    # perpendicular edge -> quarter.
    if at_left and near_top:
        return Zone.TOP_LEFT
    if at_left and near_bottom:
        return Zone.BOTTOM_LEFT
    if at_right and near_top:
        return Zone.TOP_RIGHT
    if at_right and near_bottom:
        return Zone.BOTTOM_RIGHT
    if at_top and near_left:
        return Zone.TOP_LEFT
    if at_top and near_right:
        return Zone.TOP_RIGHT
    if at_bottom and near_left:
        return Zone.BOTTOM_LEFT
    if at_bottom and near_right:
        return Zone.BOTTOM_RIGHT

    # Plain edges.
    if at_top:
        return Zone.MAX
    if at_left:
        return Zone.LEFT
    if at_right:
        return Zone.RIGHT
    # Bottom edge (middle) intentionally does nothing -- matches Windows.
    return None


def zone_rect(
    zone: Zone,
    work_left: int,
    work_top: int,
    work_right: int,
    work_bottom: int,
) -> tuple[int, int, int, int]:
    """Target (x, y, w, h) in physical pixels for a Zone, within the *work
    area* (so half/quarter/maximized all respect the taskbar).
    """
    ww = work_right - work_left
    hh = work_bottom - work_top
    half_w = ww // 2
    half_h = hh // 2
    right_w = ww - half_w  # keep total exact despite integer division
    bottom_h = hh - half_h
    left = work_left
    top = work_top
    mid_x = work_left + half_w
    mid_y = work_top + half_h

    if zone is Zone.LEFT:
        return (left, top, half_w, hh)
    if zone is Zone.RIGHT:
        return (mid_x, top, right_w, hh)
    if zone is Zone.MAX:
        return (left, top, ww, hh)
    if zone is Zone.TOP_LEFT:
        return (left, top, half_w, half_h)
    if zone is Zone.TOP_RIGHT:
        return (mid_x, top, right_w, half_h)
    if zone is Zone.BOTTOM_LEFT:
        return (left, mid_y, half_w, bottom_h)
    if zone is Zone.BOTTOM_RIGHT:
        return (mid_x, mid_y, right_w, bottom_h)
    raise ValueError(zone)


# ---------------------------------------------------------------------------
# Impure edge: real cursor + monitor + SetWindowPos.
# ---------------------------------------------------------------------------

_MONITOR_DEFAULTTONEAREST = 2
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("rcMonitor", wt.RECT),
        ("rcWork", wt.RECT),
        ("dwFlags", wt.DWORD),
    ]


def get_cursor_pos() -> tuple[int, int]:
    pt = wt.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _monitor_rects(cx: int, cy: int):
    pt = wt.POINT(cx, cy)
    hmon = ctypes.windll.user32.MonitorFromPoint(pt, _MONITOR_DEFAULTTONEAREST)
    mi = _MONITORINFO()
    mi.cbSize = ctypes.sizeof(_MONITORINFO)
    ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
    m = mi.rcMonitor
    w = mi.rcWork
    return (m.left, m.top, m.right, m.bottom), (w.left, w.top, w.right, w.bottom)


def zone_at_cursor() -> tuple[Optional[Zone], tuple[int, int, int, int]]:
    """Return (zone, work_area) for the current cursor position. work_area is
    the physical work rect of the monitor under the cursor.
    """
    cx, cy = get_cursor_pos()
    mon, work = _monitor_rects(cx, cy)
    return classify_zone(cx, cy, *mon), work


def apply_snap(hwnd: int) -> Optional[tuple[int, int, int, int]]:
    """If the cursor is over a snap zone, move/resize the window to it via
    SetWindowPos and return the applied (x, y, w, h). Otherwise return None.
    """
    zone, work = zone_at_cursor()
    if zone is None:
        return None
    x, y, w, h = zone_rect(zone, *work)
    ctypes.windll.user32.SetWindowPos(
        hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE
    )
    return (x, y, w, h)


def set_window_rect(hwnd: int, x: int, y: int, w: int, h: int) -> None:
    ctypes.windll.user32.SetWindowPos(
        hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE
    )


def get_window_rect(hwnd: int) -> tuple[int, int, int, int]:
    """(x, y, w, h) in physical pixels for a per-monitor-aware process."""
    r = wt.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top
