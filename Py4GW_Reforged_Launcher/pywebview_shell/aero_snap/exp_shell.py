"""Configurable single-window experiment shell for the Aero Snap investigation.

Keeps the production shell (window_shell.py / bridge.py / run_shell.py)
untouched while I iterate. One frameless window, resize hit-zones retained
(the proven start_native_resize path), and a drag mechanism selected by the
AERO_MODE env var:

  AERO_MODE=easy_drag    baseline -- pywebview easy_drag (SetWindowPos teleport,
                         no native move loop, so no snap). What ships at 7c2afad8.
  AERO_MODE=native_move  Attempt 1 -- easy_drag OFF; title-bar mousedown calls
                         the bridge, which does ReleaseCapture +
                         SendMessage(WM_NCLBUTTONDOWN, HTCAPTION) against the
                         real HWND -- Windows' own native move loop (which is
                         what Aero Snap hooks into). Styles: WS_THICKFRAME only
                         (added by ensure_native_resize_style), NO WS_CAPTION.

Run:  set AERO_MODE=native_move
      python -m pywebview_shell.aero_snap.exp_shell
"""
from __future__ import annotations

import ctypes
import os

import webview

from pywebview_shell.aero_snap import snap
from pywebview_shell.bridge import ShellBridge
from pywebview_shell.window_shell import (
    ensure_dpi_awareness,
    ensure_native_resize_style,
    wait_for_native_hwnd,
)

MODE = os.environ.get("AERO_MODE", "hand_snap")
RESIZE_MARGIN = 6

WM_NCLBUTTONDOWN = 0x00A1
HTCAPTION = 2

TITLE = f"AERO EXP [{MODE}]"

HTML = """
<html><body style="margin:0;background:#182030;color:#eee;font-family:sans-serif;overflow:hidden;">
<div onmousedown="startResize('top')" style="position:fixed;top:0;left:{m}px;right:{m}px;height:{m}px;cursor:n-resize;z-index:1000;"></div>
<div onmousedown="startResize('bottom')" style="position:fixed;bottom:0;left:{m}px;right:{m}px;height:{m}px;cursor:s-resize;z-index:1000;"></div>
<div onmousedown="startResize('left')" style="position:fixed;left:0;top:{m}px;bottom:{m}px;width:{m}px;cursor:w-resize;z-index:1000;"></div>
<div onmousedown="startResize('right')" style="position:fixed;right:0;top:{m}px;bottom:{m}px;width:{m}px;cursor:e-resize;z-index:1000;"></div>
<div onmousedown="startResize('topleft')" style="position:fixed;top:0;left:0;width:{m}px;height:{m}px;cursor:nw-resize;z-index:1001;"></div>
<div onmousedown="startResize('topright')" style="position:fixed;top:0;right:0;width:{m}px;height:{m}px;cursor:ne-resize;z-index:1001;"></div>
<div onmousedown="startResize('bottomleft')" style="position:fixed;bottom:0;left:0;width:{m}px;height:{m}px;cursor:sw-resize;z-index:1001;"></div>
<div onmousedown="startResize('bottomright')" style="position:fixed;bottom:0;right:0;width:{m}px;height:{m}px;cursor:se-resize;z-index:1001;"></div>

<div id="titlebar" style="height:40px;background:#283550;
display:flex;align-items:center;padding:0 10px;user-select:none;cursor:default;">
  <span style="flex:1;pointer-events:none;">{title}</span>
  <button id="btn-min" onclick="pywebview.api.minimize_clicked()">_</button>
  <button id="btn-max" onclick="pywebview.api.toggle_maximize_clicked()">[ ]</button>
  <button id="btn-close" onclick="pywebview.api.close_clicked()">X</button>
</div>
<div style="padding:20px;">
<h2>{title}</h2>
<p>Drag the dark title bar. Resize from any edge/corner.</p>
<p id="result">(ready)</p>
</div>
<script>
function startResize(edge) {{ window.pywebview.api.start_resize(edge); }}
var MODE = "{mode}";
var tb = document.getElementById('titlebar');

if (MODE === "native_move") {{
  // Native-move drag: mousedown on the title bar (except buttons) hands the
  // gesture straight to Windows' native move loop via the bridge.
  tb.addEventListener('mousedown', function(ev) {{
    if (ev.target.tagName === 'BUTTON') return;
    if (ev.button !== 0) return;
    window.pywebview.api.start_move();
  }});
}} else if (MODE === "hand_snap") {{
  // easy_drag does the actual movement; we only observe the drag to fake a
  // snapped result on release. Title-bar mousedown starts observing; the
  // window-level mouseup ends it (Python reads the real cursor + monitor).
  tb.addEventListener('mousedown', function(ev) {{
    if (ev.target.tagName === 'BUTTON') return;
    if (ev.button !== 0) return;
    window.pywebview.api.on_drag_start();
  }});
  window.addEventListener('mouseup', function(ev) {{
    window.pywebview.api.on_drag_end();
  }});
}}
</script>
</body></html>
"""


class ExpBridge(ShellBridge):
    def __init__(self, label: str) -> None:
        super().__init__(label)
        self._drag_start_pos = None
        self._snapped = False
        self._pre_snap_size = None  # (w, h) physical, to restore on drag-away
        self._preview = None  # SnapPreview, set by main()

    def set_preview(self, preview) -> None:
        self._preview = preview

    # --- Attempt 2: hand-rolled snap (easy_drag does the move) ---
    def on_drag_start(self) -> bool:
        self._drag_start_pos = snap.get_cursor_pos()
        if self._preview is not None:
            self._preview.begin_drag()
        # If we're grabbing a snapped window, restore its pre-snap SIZE so the
        # user drags a normal-sized window again (native behavior). easy_drag
        # then repositions it to follow the cursor, so we only need to fix the
        # size here; leaving position to easy_drag avoids fighting its own
        # cursor-offset math.
        if self._snapped and self._pre_snap_size and self._hwnd is not None:
            w, h = self._pre_snap_size
            cx, cy = self._drag_start_pos
            snap.set_window_rect(self._hwnd, cx - w // 2, cy - 18, w, h)
            self._snapped = False
            self._pre_snap_size = None
        return True

    def on_drag_end(self) -> bool:
        start = self._drag_start_pos
        self._drag_start_pos = None
        if self._preview is not None:
            self._preview.end_drag()
        if start is None or self._hwnd is None:
            return False
        end = snap.get_cursor_pos()
        moved = abs(end[0] - start[0]) + abs(end[1] - start[1])
        if moved < 6:  # a click, not a drag
            return False
        # Remember the floating size before we snap, so a later drag-away can
        # restore it. Only capture when transitioning floating -> snapped.
        pre = snap.get_window_rect(self._hwnd) if not self._snapped else None
        applied = snap.apply_snap(self._hwnd)
        if applied is not None:
            if pre is not None:
                self._pre_snap_size = (pre[2], pre[3])
            self._snapped = True
        print(f"[exp] on_drag_end moved={moved} cursor={end} snapped={applied}", flush=True)
        return applied is not None

    # --- Attempt 1: native caption-drag (kept for reference) ---
    def start_move(self) -> bool:
        """Attempt 1: native caption-drag. ReleaseCapture (WebView2 child holds
        capture from the JS mousedown) then WM_NCLBUTTONDOWN/HTCAPTION on the
        real top-level HWND -- the same shape as start_native_resize, just the
        HTCAPTION hit code (a native MOVE loop) instead of an edge code.
        """
        print(f"[exp] start_move called hwnd={self._hwnd}", flush=True)
        if self._hwnd is None:
            return False
        rc = ctypes.windll.user32.ReleaseCapture()
        res = ctypes.windll.user32.SendMessageW(self._hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)
        print(f"[exp] start_move done ReleaseCapture={rc} SendMessage={res}", flush=True)
        return True


def main() -> None:
    ensure_dpi_awareness()
    preview = None
    if MODE == "hand_snap":
        from pywebview_shell.aero_snap.preview import SnapPreview

        preview = SnapPreview()
    bridge = ExpBridge("exp")
    if preview is not None:
        bridge.set_preview(preview)
    easy = MODE in ("easy_drag", "hand_snap")  # hand_snap keeps easy_drag for the move
    window = webview.create_window(
        TITLE,
        html=HTML.format(m=RESIZE_MARGIN, title=TITLE, mode=MODE),
        js_api=bridge,
        width=560,
        height=380,
        x=200,
        y=180,
        frameless=True,
        easy_drag=easy,
    )
    bridge.bind_window(window)

    def on_shown():
        hwnd = wait_for_native_hwnd(window)
        print(f"[exp] mode={MODE} hwnd={hwnd!r}")
        if hwnd is not None:
            bridge.bind_hwnd(hwnd)
            ensure_native_resize_style(hwnd)
        if preview is not None:
            preview.start()

    webview.start(on_shown, debug=False)


if __name__ == "__main__":
    main()
