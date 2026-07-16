"""Standalone smoke-test entry point for the Phase A shell -- creates the
same 3-window shape as the real app (main/settings/app_settings), proving
window_shell.py + bridge.py work together in this app's real module
structure rather than the throwaway spike folder. No real page content --
placeholder HTML only, matching Phase A's scope (shell only, no business
logic, don't load the actual Launcher.dc.html mockup yet).

Frameless windows with a custom HTML/CSS title bar -- decided during this
phase (dev_notes/RELAY.md 008) after hands-on testing of both bordered and
frameless. Real, known gaps carried forward rather than silently fixed here,
since fixing them is follow-up work, not Phase A's scope:
- Dragging works via pywebview's own `easy_drag=True` (NOT CSS
  `-webkit-app-region: drag`, confirmed dead on this backend) -- but it
  stopped registering drags after one minimize/restore cycle in testing,
  reproduced once, not fully root-caused.
- Resize is only proven at the "OS accepts a resize command" level
  (WM_SYSCOMMAND/SC_SIZE, no visual glitches) -- there's no actual
  grabbable screen edge yet, since frameless windows have no WS_THICKFRAME
  border; a human resizing by dragging an edge needs custom WM_NCHITTEST
  edge hit-testing that doesn't exist yet.
- Native Aero Snap does not trigger from an easy_drag-driven move -- the
  window travels off-screen instead of snapping. Not reimplemented here.

Run directly: .venv\\Scripts\\python.exe -m pywebview_shell.run_shell
"""
from __future__ import annotations

import webview

from pywebview_shell.bridge import ShellBridge
from pywebview_shell.window_shell import ensure_dpi_awareness, wait_for_native_hwnd

HTML = """
<html><body style="margin:0;background:#1e1e1e;color:#eee;font-family:sans-serif;">
<div style="-webkit-app-region:drag;height:36px;background:#2a2a2a;
display:flex;align-items:center;padding:0 10px;user-select:none;">
  <span style="flex:1;">Phase A shell -- {label}</span>
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
</script>
</body></html>
"""


class DemoBridge(ShellBridge):
    def trigger_push(self):
        self.push_event("demo_event", {"from": self.label, "note": "python-initiated push"})


def main() -> None:
    ensure_dpi_awareness()

    labels = ["main", "settings", "app_settings"]
    bridges = {}
    windows = {}

    for i, label in enumerate(labels):
        bridge = DemoBridge(label)
        window = webview.create_window(
            f"Phase A shell -- {label}",
            html=HTML.format(label=label),
            js_api=bridge,
            width=500,
            height=350,
            x=100 + i * 550,
            y=150,
            frameless=True,
            easy_drag=True,  # required -- CSS app-region alone doesn't move
                              # the window on this backend, confirmed in
                              # spikes/pywebview/test_frameless.py
        )
        bridge.bind_window(window)
        bridges[label] = bridge
        windows[label] = window

    def on_shown():
        for label, window in windows.items():
            hwnd = wait_for_native_hwnd(window)
            print(f"[shell] {label}: hwnd={hwnd!r}")

    webview.start(on_shown, debug=False)


if __name__ == "__main__":
    main()
