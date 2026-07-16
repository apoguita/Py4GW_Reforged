"""Standalone smoke-test entry point for the Phase A shell -- creates the
same 3-window shape as the real app (main/settings/app_settings), proving
window_shell.py + bridge.py work together in this app's real module
structure rather than the throwaway spike folder. No real page content --
placeholder HTML only, matching Phase A's scope (shell only, no business
logic, don't load the actual Launcher.dc.html mockup yet).

Frameless windows with a custom HTML/CSS title bar -- decided in RELAY 008
after hands-on testing of both bordered and frameless. Current state
(RELAY 009):
- Dragging works via pywebview's own `easy_drag=True` (NOT CSS
  `-webkit-app-region: drag`, confirmed dead on this backend).
- Resize is real and confirmed via live mouse drags on all 4 edges + both
  tested corners (window_shell.start_native_resize -- hands a mousedown off
  to Windows' own native sizing loop instead of reimplementing it), no
  visual glitches.
- Snap-to-edge: reproduced via a HAND-ROLLED approach (snap.py + preview.py),
  NOT Windows' native snap. Windows' native snap only runs during its own
  modal caption-drag loop, which a frameless window can't enter without
  WS_CAPTION (which repaints the native title bar) -- and easy_drag moves via
  SetWindowPos anyway, never entering that loop. So instead of asking Windows
  to snap, the bridge observes the drag (title-bar mousedown -> on_drag_start,
  window mouseup -> on_drag_end) and, on release over a screen edge/corner,
  reproduces the snapped result with SetWindowPos itself: half/quarter/
  maximize, plus restore-on-drag-away and a live translucent preview overlay.
  All verified with real mouse drags + screenshots (dev_notes/
  AERO_SNAP_INVESTIGATION.md). Not reproduced (accepted trade-off): the Win11
  Snap Layouts hover flyout and keyboard Win+arrow snap. See RELAY.md 008/009
  for why the native path was ruled out.

Run directly: .venv\\Scripts\\python.exe -m pywebview_shell.run_shell
"""
from __future__ import annotations

import webview

from pywebview_shell.bridge import ShellBridge
from pywebview_shell.preview import SnapPreview
from pywebview_shell.window_shell import (
    ensure_dpi_awareness,
    ensure_native_resize_style,
    wait_for_native_hwnd,
)

RESIZE_MARGIN = 6

HTML = """
<html><head><style>
/* --accent is the theme accent, as "r, g, b" components so it works both as
   rgb(var(--accent)) in CSS and parsed by JS to report to Python for the snap
   preview. Placeholder value here; the real buildTheme() will set this from
   user input in a later phase, and the same JS reporting will pick it up. */
:root {{ --accent: 20, 184, 166; }}
</style></head>
<body style="margin:0;background:#1e1e1e;color:#eee;font-family:sans-serif;">
<!-- Edge/corner resize hit-zones (RELAY 009) -- frameless windows have no
     native WS_THICKFRAME border for a human to grab, so these thin strips
     stand in for one. mousedown on any of them hands off to Windows' own
     native sizing loop via the bridge (window_shell.start_native_resize) --
     not a Python-side reimplementation of resize. -->
<div onmousedown="startResize('top')" style="position:fixed;top:0;left:{m}px;right:{m}px;height:{m}px;cursor:n-resize;z-index:1000;"></div>
<div onmousedown="startResize('bottom')" style="position:fixed;bottom:0;left:{m}px;right:{m}px;height:{m}px;cursor:s-resize;z-index:1000;"></div>
<div onmousedown="startResize('left')" style="position:fixed;left:0;top:{m}px;bottom:{m}px;width:{m}px;cursor:w-resize;z-index:1000;"></div>
<div onmousedown="startResize('right')" style="position:fixed;right:0;top:{m}px;bottom:{m}px;width:{m}px;cursor:e-resize;z-index:1000;"></div>
<div onmousedown="startResize('topleft')" style="position:fixed;top:0;left:0;width:{m}px;height:{m}px;cursor:nw-resize;z-index:1001;"></div>
<div onmousedown="startResize('topright')" style="position:fixed;top:0;right:0;width:{m}px;height:{m}px;cursor:ne-resize;z-index:1001;"></div>
<div onmousedown="startResize('bottomleft')" style="position:fixed;bottom:0;left:0;width:{m}px;height:{m}px;cursor:sw-resize;z-index:1001;"></div>
<div onmousedown="startResize('bottomright')" style="position:fixed;bottom:0;right:0;width:{m}px;height:{m}px;cursor:se-resize;z-index:1001;"></div>

<div id="titlebar" style="-webkit-app-region:drag;height:36px;background:#2a2a2a;
border-bottom:2px solid rgb(var(--accent));
display:flex;align-items:center;padding:0 10px;user-select:none;">
  <span style="flex:1;pointer-events:none;">Phase A shell -- {label}</span>
  <button onclick="pywebview.api.minimize_clicked()" style="-webkit-app-region:no-drag;">_</button>
  <button onclick="pywebview.api.toggle_maximize_clicked()" style="-webkit-app-region:no-drag;">[ ]</button>
  <button onclick="pywebview.api.close_clicked()" style="-webkit-app-region:no-drag;">X</button>
</div>
<div style="padding:20px;">
<h2>Phase A shell -- {label}</h2>
<button onclick="doPing()">Ping Python</button>
<button onclick="doPush()">Ask Python to push an event</button>
<p id="result">(no calls yet)</p>
</div>
<script>
window.shellBridge = {{
  on: function(event, data) {{
    document.getElementById('result').innerText =
      'push received: ' + event + ' -> ' + JSON.stringify(data);
  }}
}};
function doPing() {{
  window.pywebview.api.ping('hello from JS').then(function(response) {{
    document.getElementById('result').innerText = 'ping response: ' + JSON.stringify(response);
  }});
}}
function doPush() {{
  window.pywebview.api.trigger_push();
}}
function startResize(edge) {{
  window.pywebview.api.start_resize(edge);
}}
// Hand-rolled Aero Snap: easy_drag does the move; we just tell Python when a
// title-bar drag starts (to show the preview / restore a snapped window) and
// when it ends (to snap into the zone the cursor is over).
var titlebar = document.getElementById('titlebar');
titlebar.addEventListener('mousedown', function(ev) {{
  if (ev.target.tagName === 'BUTTON') return;  // let window-control buttons through
  if (ev.button !== 0) return;                  // left button only
  window.pywebview.api.on_drag_start();
}});
window.addEventListener('mouseup', function() {{
  window.pywebview.api.on_drag_end();
}});
// Report the theme accent (CSS --accent) to Python once the bridge is ready,
// so the snap preview overlay is drawn in the user's accent, not a fixed blue.
function reportAccent() {{
  var raw = getComputedStyle(document.documentElement).getPropertyValue('--accent');
  var p = raw.split(',').map(function(s) {{ return parseInt(s, 10); }});
  if (p.length === 3 && p.every(function(n) {{ return !isNaN(n); }})) {{
    window.pywebview.api.set_accent(p[0], p[1], p[2]);
  }}
}}
if (window.pywebview && window.pywebview.api) {{ reportAccent(); }}
else {{ window.addEventListener('pywebviewready', reportAccent); }}
</script>
</body></html>
"""


class DemoBridge(ShellBridge):
    def trigger_push(self):
        self.push_event("demo_event", {"from": self.label, "note": "python-initiated push"})


def main() -> None:
    ensure_dpi_awareness()

    # One shared snap-preview overlay for the whole app -- only one window is
    # ever dragged at a time, so a single overlay serves all of them.
    preview = SnapPreview()

    labels = ["main", "settings", "app_settings"]
    bridges = {}
    windows = {}

    for i, label in enumerate(labels):
        bridge = DemoBridge(label)
        bridge.set_preview(preview)
        window = webview.create_window(
            f"Phase A shell -- {label}",
            html=HTML.format(label=label, m=RESIZE_MARGIN),
            js_api=bridge,
            width=500,
            height=350,
            x=100 + i * 550,
            y=150,
            frameless=True,
            easy_drag=True,  # dragging stays on pywebview's own mechanism
                              # (proven working, RELAY 006/008) -- RELAY 009
                              # only adds resize, per that entry's own scope.
        )
        bridge.bind_window(window)
        bridges[label] = bridge
        windows[label] = window

    def on_shown():
        for label, window in windows.items():
            hwnd = wait_for_native_hwnd(window)
            print(f"[shell] {label}: hwnd={hwnd!r}")
            if hwnd is not None:
                bridges[label].bind_hwnd(hwnd)
                ensure_native_resize_style(hwnd)
        preview.start()

    webview.start(on_shown, debug=False)


if __name__ == "__main__":
    main()
