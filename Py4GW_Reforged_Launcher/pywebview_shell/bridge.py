"""Python<->JS bridge scaffold. Phase A proves the mechanism works cleanly
in this app's real structure -- no real business logic wired to it yet.

Bidirectional shape:
- JS -> Python: any public method on a ShellBridge instance, called from JS
  as `window.pywebview.api.<method_name>(...)` -- pywebview's normal js_api
  contract, unchanged.
- Python -> JS: `push_event`, calling back into the page via
  `window.evaluate_js(...)` to invoke a JS-side handler. This is the shape
  later phases wire up for real push updates (live console lines, per-card
  launch status) without the page needing to poll Python for state.
"""
from __future__ import annotations

import json
import weakref
from typing import Any, Optional

import webview

from pywebview_shell import snap
from pywebview_shell.window_shell import start_native_resize


class ShellBridge:
    """One instance per window, matching pywebview's one-js_api-per-window
    model. The window back-reference is bound after webview.create_window()
    returns -- the bridge needs it to push events back into the page, but
    js_api has to be handed to create_window before that object exists.

    ROOT CAUSE, found during Phase A smoke testing: this back-reference must
    stay on a name starting with `_`. pywebview rebuilds its callable-method
    map on every JS->Python call by walking `dir(bridge)` (see
    `webview.util.get_functions`), skipping only underscore-prefixed names,
    and recursing into any *public*, non-callable attribute it finds. An
    earlier version exposed this as a public `window` property -- `dir()`
    doesn't skip properties, so `get_functions` dereferenced it, got the live
    `webview.Window`, and recursed into its `.native` (a real pythonnet/COM
    WinForms object), which is fully self-referential when introspected this
    way (`.native.AccessibilityObject.Bounds.Empty.Empty.Empty...`),
    producing a runaway recursion that hung the process -- reproduced on a
    genuine mouse click, not just the automation used to test this. A
    weakref alone didn't fix it (this isn't a GC/cycle issue -- `getattr()`
    still resolves to the live object either way); keeping the name private
    is what makes `get_functions` skip it entirely. The original RELAY 006
    spike's `Api` class never hit this because it never exposed anything
    window-shaped as a public attribute.

    Also owns the custom title bar's window-control calls (minimize/
    maximize/close) -- frameless windows have no native chrome to provide
    these, so the HTML title bar's buttons call back into Python for them,
    same round trip shape as everything else JS->Python.
    """

    def __init__(self, label: str) -> None:
        self.label = label
        self._window_ref: Optional[weakref.ReferenceType] = None
        self._hwnd: Optional[int] = None
        self._maximized = False
        # Hand-rolled Aero Snap state (see snap.py / preview.py; RELAY 009
        # follow-up). easy_drag does the actual movement; we observe the drag
        # to reproduce the snapped *result*, since a frameless window can't use
        # Windows' native snap-aware move loop without WS_CAPTION.
        self._drag_start_pos: Optional[tuple[int, int]] = None
        self._snapped = False
        self._pre_snap_size: Optional[tuple[int, int]] = None
        self._preview = None  # shared SnapPreview overlay, set by the app

    def _window(self) -> Optional[webview.Window]:
        return self._window_ref() if self._window_ref is not None else None

    def bind_window(self, window: webview.Window) -> None:
        self._window_ref = weakref.ref(window)

    def bind_hwnd(self, hwnd: int) -> None:
        """Plain int, not a live object -- safe to store directly (no
        get_functions recursion risk; see the class docstring), but kept on
        a private name for consistency with the window back-reference.
        """
        self._hwnd = hwnd

    def start_resize(self, edge: str) -> bool:
        """JS mousedown on one of the frameless window's edge/corner
        hit-zones calls this (RELAY 009) -- hands off to Windows' own native
        sizing loop instead of reimplementing resize in Python. See
        window_shell.start_native_resize for why this works at all.
        """
        if self._hwnd is None:
            return False
        return start_native_resize(self._hwnd, edge)

    def set_preview(self, preview) -> None:
        """Bind the shared snap-preview overlay (one per app, not per window)."""
        self._preview = preview

    def on_drag_start(self) -> bool:
        """A title-bar mousedown. Record the cursor so on_drag_end can tell a
        drag from a click, start the preview, and -- if this window is snapped
        -- restore its pre-snap SIZE so the user drags a normal window again
        (easy_drag then repositions it, so we only fix size here).
        """
        self._drag_start_pos = snap.get_cursor_pos()
        if self._preview is not None:
            self._preview.begin_drag()
        if self._snapped and self._pre_snap_size and self._hwnd is not None:
            w, h = self._pre_snap_size
            cx, cy = self._drag_start_pos
            snap.set_window_rect(self._hwnd, cx - w // 2, cy - 18, w, h)
            self._snapped = False
            self._pre_snap_size = None
        return True

    def on_drag_end(self) -> bool:
        """A mouseup ending a title-bar drag. If the cursor is over a snap zone,
        move/resize this window into it (remembering the floating size first so
        a later drag-away can restore it). Hide the preview either way.
        """
        start = self._drag_start_pos
        self._drag_start_pos = None
        if self._preview is not None:
            self._preview.end_drag()
        if start is None or self._hwnd is None:
            return False
        end = snap.get_cursor_pos()
        if abs(end[0] - start[0]) + abs(end[1] - start[1]) < 6:
            return False  # a click, not a drag
        pre = snap.get_window_rect(self._hwnd) if not self._snapped else None
        applied = snap.apply_snap(self._hwnd)
        if applied is not None:
            if pre is not None:
                self._pre_snap_size = (pre[2], pre[3])
            self._snapped = True
        return applied is not None

    def minimize_clicked(self) -> None:
        window = self._window()
        if window is not None:
            window.minimize()

    def toggle_maximize_clicked(self) -> None:
        window = self._window()
        if window is None:
            return
        if self._maximized:
            window.restore()
        else:
            window.maximize()
        self._maximized = not self._maximized

    def close_clicked(self) -> None:
        window = self._window()
        if window is not None:
            window.destroy()

    def ping(self, payload: Any = None) -> dict:
        """Minimal JS->Python round trip: JS calls this, Python returns a
        real value synchronously. Stand-in for later real calls (e.g. a
        launch button invoking a profile launch).
        """
        return {"ok": True, "label": self.label, "echo": payload}

    def push_event(self, event_name: str, data: Any = None) -> bool:
        """Python->JS push: invokes a JS-side `window.shellBridge.on(event,
        data)` handler the page is expected to define. Stand-in for later
        real pushes (live console lines, per-card status updates).
        Returns False if there's no bound window yet rather than raising --
        a push before the window exists is a caller ordering bug, not
        something that should crash the app.
        """
        window = self._window()
        if window is None:
            return False
        payload = json.dumps(data)
        script = f"window.shellBridge && window.shellBridge.on({event_name!r}, {payload})"
        window.evaluate_js(script)
        return True
