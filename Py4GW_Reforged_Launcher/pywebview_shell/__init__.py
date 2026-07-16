"""Production pywebview app shell -- window creation, DPI-awareness, native-HWND
per-window dark title bar, and the Python<->JS bridge plumbing.

Phase A of the pywebview rewrite (dev_notes/RELAY.md 008, extending the
spikes/pywebview/ throwaway spike from RELAY 006). Shell only -- no business
logic, no real page content wired in. Doesn't touch launcher.py or
feature/launcher's existing hello_imgui app at all.

Frameless windows (app draws its own HTML/CSS title row -- logo/label plus
custom minimize/maximize/close), not bordered -- the app's actual visual
direction (matching the Launcher.dc.html mockup family), confirmed as the
real answer going forward after hands-on testing of both. Bordered +
DWMWA_USE_IMMERSIVE_DARK_MODE was fully proven working too (dev_notes/
RELAY.md 006/008, spikes/pywebview/spike_multiwindow.py) but isn't needed --
there's no native caption left to theme once the app draws its own.

Known, real gaps carried forward from that testing, not fixed in this
phase (see spikes/pywebview/test_frameless.py and RELAY.md 008's summary):
- Dragging needs pywebview's own `easy_drag=True` -- CSS
  `-webkit-app-region: drag` alone does nothing on this WebView2 backend.
  `easy_drag` itself stopped registering drags after a single
  minimize/restore cycle in testing (reproduced once, not root-caused).
- Resize is only proven at the "OS accepts a resize command" level
  (WM_SYSCOMMAND/SC_SIZE) -- there's no actual grabbable screen edge yet
  (no WS_THICKFRAME border on a frameless window); real edge-drag resize
  needs custom WM_NCHITTEST hit-testing, not built here.
- Native Aero Snap does not trigger from an easy_drag-driven move -- the
  window travels off-screen instead of snapping to a half/quarter layout.
"""
