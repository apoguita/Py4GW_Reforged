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

from pywebview_shell.bridge import ShellBridge
from pywebview_shell.window_shell import (
    ensure_dpi_awareness,
    ensure_native_resize_style,
    wait_for_native_hwnd,
)

MODE = os.environ.get("AERO_MODE", "native_move")
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

// Native-move drag: mousedown anywhere on the title bar (except the buttons)
// hands the gesture straight to Windows' native move loop via the bridge.
var tb = document.getElementById('titlebar');
tb.addEventListener('mousedown', function(ev) {{
  if (ev.target.tagName === 'BUTTON') return;   // let button clicks through
  if (ev.button !== 0) return;                   // left button only
  window.pywebview.api.start_move();
}});
</script>
</body></html>
"""


class ExpBridge(ShellBridge):
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
    bridge = ExpBridge("exp")
    easy = MODE == "easy_drag"
    window = webview.create_window(
        TITLE,
        html=HTML.format(m=RESIZE_MARGIN, title=TITLE),
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

    webview.start(on_shown, debug=False)


if __name__ == "__main__":
    main()
