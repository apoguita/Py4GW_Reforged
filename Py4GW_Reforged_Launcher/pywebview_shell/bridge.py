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

import collections
import dataclasses
import json
import threading
import time
import weakref
import webbrowser
from pathlib import Path
from typing import Any, Optional

import psutil
import webview

from launcher_core import bulk_launch, crypto, elevation, legacy_import, mod_repo, mod_root, prereqs, profile_store, roster_transfer, settings_store, update_check, window_control
from launcher_core import version as launcher_version
from launcher_core.gw1_launch import launch_py4gw_profile
from launcher_core.launch_progress import classify_progress_category, classify_progress_message
from launcher_core.process_control import terminate_process
from launcher_core.profile import GameProfile
from launcher_core.team import Team
from pywebview_shell import snap
from pywebview_shell.window_shell import get_dpi_scale, start_native_resize


def _is_process_alive(pid: int) -> bool:
    """RELAY 040: same real liveness-check pattern gw1_launch.py's own
    `_wait_for_window_or_exit`/`_wait_for_gw_window` already use
    (`psutil.Process(pid).status()`/`psutil.NoSuchProcess`), reused here
    rather than hand-classifying every LaunchResult failure-reason string
    as "definitely alive" or "definitely dead" -- several genuinely are
    ambiguous from the reason text alone (see gw1_launch.py's ~884/894/
    897/900 failure returns, none of which call TerminateProcess)."""
    try:
        return psutil.Process(pid).status() == psutil.STATUS_RUNNING
    except psutil.NoSuchProcess:
        return False


def _rects_close(a, b, tol: int = 4) -> bool:
    """Whether two (x, y, w, h) rects match within a few px (SetWindowPos can
    land a pixel or two off after DPI rounding)."""
    return all(abs(pa - pb) <= tol for pa, pb in zip(a, b))


def _resolve_mod_repo_path():
    """RELAY 033: mirrors the old imgui app's ModRepoState.__init__ exactly
    -- settings_store's saved override if one exists, otherwise
    mod_root's own mod-root assumption (this launcher's own parent
    directory), never duplicated/reimplemented here. Resolved fresh on
    every call (no bridge-instance caching), matching every other
    settings_store-backed read in this app (029/032) -- a path change on
    disk (or via save_mod_repo_path) is visible immediately, nothing to
    invalidate."""
    saved = settings_store.load_mod_repo_path()
    return Path(saved) if saved else mod_root._mod_root()


def _find_dll_under_mod_root(filename: str) -> str:
    """RELAY 060: auto-default a DLL path when a profile is created (new or
    imported) with the matching injection enabled and no path already set.
    Globs for the real filename under the resolved mod root rather than
    assuming a specific subfolder -- confirmed directly against a real
    checkout: Py4GW.dll sits at the mod root itself, gMod.dll under
    Addons/, two different depths, so a fixed relative path would be
    wrong for at least one of them. Returns "" (leave blank, keep the
    existing "must be set manually" warning) unless EXACTLY one match is
    found -- an ambiguous multi-match is a worse guess than no guess."""
    root = _resolve_mod_repo_path()
    if not root.is_dir():
        return ""
    matches = list(root.rglob(filename))
    return str(matches[0]) if len(matches) == 1 else ""


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
        # Title-bar drag + hand-rolled Aero Snap state (snap.py / preview.py).
        # We own the window MOVE ourselves now (drag_tick), not pywebview's
        # easy_drag -- easy_drag arms on a mousedown ANYWHERE in the window (so
        # clicking a button could nudge it) and its move math assumes the
        # content starts at the window's top-left, which is off by the
        # WS_THICKFRAME border we added for native resize (~15px), jumping the
        # window right+down on the first move. Doing it here (title-bar only,
        # offset from the raw window rect) fixes both. A frameless window still
        # can't use Windows' native snap-aware move loop (needs WS_CAPTION), so
        # snap stays hand-rolled: we watch the drag and reproduce the result.
        self._drag_start_pos: Optional[tuple[int, int]] = None
        self._dragging = False
        self._drag_offset: tuple[int, int] = (0, 0)  # cursor - raw window top-left
        self._snapped = False
        self._pre_snap_size: Optional[tuple[int, int]] = None
        self._snap_rect: Optional[tuple[int, int, int, int]] = None
        self._preview = None  # shared SnapPreview overlay, set by the app
        self._min_size_logical: tuple[int, int] = (0, 0)  # set via set_min_size
        # Phase E individual launch. profile_id -> pid of the running client,
        # populated on a successful launch and consumed by stop_profile. Guarded
        # because it's written from the launch background thread and read from
        # the (JS-called) UI thread. profile_id -> True while a launch thread is
        # in flight, to reject a double-launch of the same profile.
        self._launch_lock = threading.Lock()
        self._running_pids: dict[str, int] = {}
        self._in_flight: set[str] = set()
        # Phase F team/bulk launch. Only one sequence at a time -- a second
        # call while one's already running is rejected, not queued behind
        # it (see launch_profiles_bulk). Both guarded by _launch_lock,
        # same as the individual-launch state above.
        self._bulk_cancel_event: Optional[threading.Event] = None
        self._bulk_thread: Optional[threading.Thread] = None
        # Phase G live console (RELAY 021). Same shape as launcher.py's own
        # STATE.console_lines -- a bounded, thread-safe deque fed from both
        # launch paths, own lock (several launch threads can append
        # concurrently during a bulk sequence). In-memory only, same as the
        # imgui app's version -- never persisted to disk, doesn't survive a
        # full app restart.
        self._console_lock = threading.Lock()
        # Each entry is {"line": str, "category": str} -- category added
        # RELAY 030 (classify_progress_category) so a page/history reload
        # (get_console_lines) shows the same coloring as a live-pushed line,
        # not just the live push_event path.
        self._console_lines: collections.deque[dict] = collections.deque(maxlen=500)
        # True right after _update_console_countdown appended/replaced the
        # last line -- so the *next* countdown update knows to replace it in
        # place rather than append another (otherwise a 30-90s pacing delay
        # alone would spam one new line per second). Reset by
        # _append_console_line, so a real per-profile log line breaking the
        # streak always starts a fresh line -- ported from launcher.py's
        # _console_countdown_active exactly.
        self._console_countdown_active = False
        # Phase G part 2 (RELAY 032) -- guards against a second install
        # starting while one's already running, same shape as _in_flight
        # above (a plain lock-guarded value, not the old imgui app's
        # PrereqState polling class -- this app already has push_event for
        # exactly this, no reason to reintroduce a polling design).
        self._prereq_install_lock = threading.Lock()
        self._prereq_install_in_progress: Optional[str] = None
        # Phase G part 3 (RELAY 033) -- same guard shape as prereq installs
        # above, one shared slot since clone and update are mutually
        # exclusive real network/filesystem operations against the same
        # checkout.
        self._mod_repo_op_lock = threading.Lock()
        self._mod_repo_op_in_progress: Optional[str] = None
        # RELAY 035 -- guards against a second elevation relaunch attempt
        # starting while the first (real, potentially slow -- waiting on the
        # user's own UAC response) one is still in flight, same shape as the
        # locks above.
        self._run_as_admin_lock = threading.Lock()
        self._run_as_admin_relaunch_in_progress = False
        # RELAY 041 -- guards against bind_window ever starting a second
        # focus-poll thread (shouldn't happen, but costs nothing to guard).
        self._focus_poll_started = False

    def _window(self) -> Optional[webview.Window]:
        return self._window_ref() if self._window_ref is not None else None

    def bind_window(self, window: webview.Window) -> None:
        self._window_ref = weakref.ref(window)
        if not self._focus_poll_started:
            self._focus_poll_started = True
            threading.Thread(target=self._run_focus_poll, daemon=True).start()

    def bind_hwnd(self, hwnd: int) -> None:
        """Plain int, not a live object -- safe to store directly (no
        get_functions recursion risk; see the class docstring), but kept on
        a private name for consistency with the window back-reference.
        """
        self._hwnd = hwnd

    def set_min_size(self, width: int, height: int) -> None:
        """Called once from Python (run_shell.py), not JS -- the window's own
        `create_window(min_size=...)` value, in LOGICAL px (pywebview's unit
        for that parameter). Plain ints, safe to store directly (same
        reasoning as `bind_hwnd`). Used by `on_drag_end` to keep the
        hand-rolled Snap's quarter targets from overshooting the work area
        at high DPI (RELAY 012) -- see `snap._clamp_into_work_area`.
        """
        self._min_size_logical = (width, height)

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

    def set_accent(self, r: int, g: int, b: int) -> bool:
        """The page reports its theme ACCENT (from CSS --accent) so the snap
        preview overlay is drawn in the user's accent, not a hardcoded colour.
        """
        if self._preview is not None:
            self._preview.set_accent(r, g, b)
        return True

    def on_drag_start(self) -> bool:
        """A title-bar mousedown. Record the cursor so on_drag_end can tell a
        drag from a click, start the preview, restore a snapped window's
        pre-snap size, then latch the cursor->window offset so drag_tick can
        move the window under the cursor with no jump.
        """
        self._drag_start_pos = snap.get_cursor_pos()
        if self._preview is not None:
            self._preview.begin_drag()
        # Restore the pre-snap size only if the window is STILL sitting in the
        # rect we snapped it to. If it's been moved or resized since (incl. via
        # the native WS_THICKFRAME border, which bypasses start_resize), it's no
        # longer "snapped" -- respect the user's change and don't restore.
        if self._snapped and self._hwnd is not None:
            still_snapped = self._snap_rect is not None and _rects_close(
                snap.get_window_rect(self._hwnd), self._snap_rect
            )
            if still_snapped and self._pre_snap_size is not None:
                w, h = self._pre_snap_size
                cx, cy = self._drag_start_pos
                snap.set_window_rect(self._hwnd, cx - w // 2, cy - 18, w, h)
            self._snapped = False
            self._pre_snap_size = None
            self._snap_rect = None
        # Latch the offset from the (possibly just-restored) window's RAW
        # top-left. Using the raw rect for both this and the SetWindowPos in
        # drag_tick is what keeps the window exactly under the cursor -- the
        # WS_THICKFRAME border cancels out instead of jumping the window.
        if self._hwnd is not None:
            wx, wy, _, _ = snap.get_window_rect(self._hwnd)
            cx, cy = self._drag_start_pos
            self._drag_offset = (cx - wx, cy - wy)
            self._dragging = True
        return True

    def drag_tick(self) -> bool:
        """Called from JS on each mousemove during a title-bar drag. Move the
        window so the cursor stays at the same offset from its raw top-left."""
        if not self._dragging or self._hwnd is None:
            return False
        cx, cy = snap.get_cursor_pos()
        ox, oy = self._drag_offset
        snap.move_window(self._hwnd, cx - ox, cy - oy)
        return True

    def on_drag_end(self) -> bool:
        """A mouseup ending a title-bar drag. If the cursor is over a snap zone,
        move/resize this window into it (remembering the floating size first so
        a later drag-away can restore it). Hide the preview either way.
        """
        start = self._drag_start_pos
        self._drag_start_pos = None
        self._dragging = False
        if self._preview is not None:
            self._preview.end_drag()
        if start is None or self._hwnd is None:
            return False
        end = snap.get_cursor_pos()
        if abs(end[0] - start[0]) + abs(end[1] - start[1]) < 6:
            return False  # a click, not a drag
        pre = snap.get_window_rect(self._hwnd) if not self._snapped else None
        scale = get_dpi_scale(self._hwnd)
        min_w = round(self._min_size_logical[0] * scale)
        min_h = round(self._min_size_logical[1] * scale)
        applied = snap.apply_snap(self._hwnd, min_w=min_w, min_h=min_h)
        if applied is not None:
            if pre is not None:
                self._pre_snap_size = (pre[2], pre[3])
            self._snap_rect = applied
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

    def list_profiles(self) -> dict:
        """Real, read-only data path (RELAY 010) -- loads whatever's actually on
        disk via launcher_core.profile_store, same module the imgui app itself
        uses. No caching: called once per page load, cheap enough (small local
        JSON files) that staleness isn't worth the complexity yet.

        `password_protected` is stripped before returning -- it's always a
        DPAPI-encrypted blob, never plaintext (see launcher_core/profile.py),
        but the render layer has no legitimate reason to see even that.
        Saving a changed password goes through save_profile's `new_password`
        field instead of ever round-tripping this blob back from JS.
        """
        profiles = profile_store.load_profiles()
        teams = profile_store.load_teams()
        profile_dicts = []
        for p in profiles:
            d = p.to_dict()
            d.pop("password_protected", None)
            profile_dicts.append(d)
        return {
            "profiles": profile_dicts,
            "teams": [t.to_dict() for t in teams],
        }

    # ---- App Settings (RELAY 029) -- the settings_store-backed controls ----
    # this phase wires UI onto. "Reload profiles/teams from disk" needs no
    # bridge method of its own -- list_profiles() above already reads fresh
    # from disk every call, so the JS side just calls loadData() again.

    def get_app_settings(self) -> dict:
        return {
            "multiclient_enabled": settings_store.load_multiclient_enabled(),
            "py4gw_injection_enabled": settings_store.load_py4gw_injection_enabled(),
            "gmod_injection_enabled": settings_store.load_gmod_injection_enabled(),
            "bulk_launch_pacing_seconds": settings_store.load_bulk_launch_pacing_seconds(),
        }

    def save_multiclient_enabled(self, enabled: bool) -> None:
        settings_store.save_multiclient_enabled(bool(enabled))

    def save_py4gw_injection_enabled(self, enabled: bool) -> None:
        settings_store.save_py4gw_injection_enabled(bool(enabled))

    def save_gmod_injection_enabled(self, enabled: bool) -> None:
        settings_store.save_gmod_injection_enabled(bool(enabled))

    def save_bulk_launch_pacing_seconds(self, seconds: int) -> None:
        # No clamp here -- bulk_launch.clamp_pacing_seconds() already
        # enforces the real [MIN_PACING_SECONDS, MAX_PACING_SECONDS] floor/
        # ceiling at use time (_run_bulk_launch), regardless of whatever
        # raw value this stores. Duplicating the clamp here would just be a
        # second copy of the same rule to keep in sync.
        settings_store.save_bulk_launch_pacing_seconds(int(seconds))

    # ---- Run as administrator (RELAY 035) ----

    def get_run_as_admin_state(self) -> dict:
        """`elevated` is a live fact about THIS running process
        (elevation.is_elevated()), independent of `enabled` -- someone can be
        running elevated right now without the toggle on (e.g. they
        right-clicked the exe themselves), and the header's ADMIN badge (see
        app.js) is keyed off `elevated` alone for exactly that reason."""
        return {
            "enabled": settings_store.load_run_as_admin_enabled(),
            "elevated": elevation.is_elevated(),
        }

    def save_run_as_admin_enabled(self, enabled: bool) -> dict:
        """Turning OFF never touches the current (possibly already-elevated)
        session -- de-elevating a running process isn't possible, so this
        only ever saves the preference and confirms it via a console line;
        "takes effect next restart" is communicated by the Advanced tab's own
        status text (app.js), not by anything this method does.

        Turning ON while already elevated needs no relaunch -- just persists
        the preference. Turning ON while NOT elevated spawns a background
        thread that triggers a real UAC prompt (elevation.relaunch_elevated,
        which blocks on the user's own response) and reports back via
        push_event rather than blocking this call, same shape as every other
        real slow operation in this bridge (032/033) -- waiting on a UAC
        response is, if anything, less bounded than either of those.
        """
        enabled = bool(enabled)
        settings_store.save_run_as_admin_enabled(enabled)

        if not enabled:
            self._push_console_line("Administrator elevation disabled", "acc")
            return {"ok": True, "elevated": elevation.is_elevated()}

        if elevation.is_elevated():
            return {"ok": True, "elevated": True}

        with self._run_as_admin_lock:
            if self._run_as_admin_relaunch_in_progress:
                return {"ok": True, "elevated": False, "relaunching": True}
            self._run_as_admin_relaunch_in_progress = True

        def worker() -> None:
            try:
                elevation.relaunch_elevated()
            except OSError as e:
                with self._run_as_admin_lock:
                    self._run_as_admin_relaunch_in_progress = False
                self.push_event("run_as_admin_relaunch_failed", {"error": str(e)})
                return
            # Real success -- an elevated copy is now starting (or already
            # up). This (non-elevated) instance's job is done; tell the page
            # to close it via the normal close path (window.destroy(), same
            # as the titlebar's own close button) rather than tearing the
            # window down from this background thread directly.
            self.push_event("run_as_admin_relaunching", {})

        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True, "elevated": False, "relaunching": True}

    # ---- Launcher self-update check (RELAY 048) ----
    # Real gap found live: this never made it into the pywebview shell at
    # all (confirmed via this file's own import line before this entry --
    # neither update_check nor version was ever imported). Ported from the
    # old app's real UpdateCheckState/App Settings render block, adapted
    # onto this app's own push_event pattern (032/033) instead of that
    # class's per-frame ImGui polling, which this app has no equivalent of.

    def get_launcher_version(self) -> str:
        return launcher_version.__version__

    def check_launcher_update(self) -> dict:
        """Kicks off a real GitHub releases API check on a background
        thread; result arrives via a "launcher_update_result" push_event.
        Same immediate-ack-then-push shape as check_prereqs -- never
        blocks the caller. Safe to call unconditionally (fetch_latest_
        release_tag never raises, always returns a result -- see its own
        docstring), so this is auto-triggered once at startup exactly like
        the old app's own UpdateCheckState.run_check_async, in addition to
        the explicit "Check for updates" click."""
        threading.Thread(target=self._run_launcher_update_check, daemon=True).start()
        return {"ok": True}

    def _run_launcher_update_check(self) -> None:
        result = update_check.fetch_latest_release_tag()
        current = launcher_version.__version__
        self.push_event(
            "launcher_update_result",
            {
                "ok": result.ok,
                "latest_tag": result.latest_tag,
                "current_version": current,
                "is_newer": result.ok and update_check.is_newer_version_available(result.latest_tag, current),
            },
        )

    def open_releases_page(self) -> None:
        webbrowser.open(update_check.releases_page_url())

    # ---- Theme palette persistence (RELAY 038) ----
    # Real bug fix, not just new UI: before this entry, the palette never
    # persisted at all (app.js hardcoded THEME_PRESETS[0] on every load,
    # confirmed via grep -- no save/load call anywhere), so any custom
    # color edit silently vanished on restart.

    def get_custom_palette(self) -> Optional[dict]:
        return settings_store.load_custom_palette()

    def save_custom_palette(self, palette: dict) -> None:
        settings_store.save_custom_palette(dict(palette))

    # ---- Prerequisites (RELAY 032) -- Python/VC++/DirectX checks, ported
    # onto push_event instead of the old imgui app's PrereqState polling
    # class (this app already has a proven async-push mechanism -- see
    # this class's own docstring on push_event, and RELAY 021/029's own
    # use of the identical pattern).

    def check_prereqs(self) -> dict:
        """Kicks off a background check of all 4 real prereqs.py rows;
        results arrive via a "prereqs_result" push_event once done -- never
        blocks the caller, same immediate-ack-then-push shape as
        launch_profiles_bulk."""
        threading.Thread(target=self._run_prereq_checks, daemon=True).start()
        return {"ok": True}

    def _run_prereq_checks(self) -> None:
        python_result = prereqs.check_python_prereq()
        vcredist_result = prereqs.check_vcredist_prereq()
        directx_result = prereqs.check_directx_runtime_prereq()
        self.push_event(
            "prereqs_result",
            {
                "python": {"is_ok": python_result.is_ok, "diagnostic_text": python_result.diagnostic_text},
                "vcredist_x86": {
                    "is_ok": vcredist_result.x86_status == prereqs.VcRedistStatus.OK,
                    "diagnostic_text": f"version {vcredist_result.x86_version}" if vcredist_result.x86_version else "not found",
                },
                "vcredist_x64": {
                    "is_ok": vcredist_result.x64_status == prereqs.VcRedistStatus.OK,
                    "diagnostic_text": f"version {vcredist_result.x64_version}" if vcredist_result.x64_version else "not found",
                },
                "directx_runtime": {"is_ok": directx_result.is_ok, "diagnostic_text": directx_result.diagnostic_text},
            },
        )

    def install_prereq(self, component: str) -> dict:
        """component is "python"/"vcredist_x86"/"vcredist_x64"/
        "directx_runtime". Rejects a second concurrent install -- the real
        user-facing prevention is the UI disabling the button while one's
        in flight, this is just the server-side guard behind it."""
        with self._prereq_install_lock:
            if self._prereq_install_in_progress is not None:
                return {"ok": False, "error": "An install is already in progress"}
            self._prereq_install_in_progress = component
        threading.Thread(target=self._run_prereq_install, args=(component,), daemon=True).start()
        return {"ok": True}

    def _run_prereq_install(self, component: str) -> None:
        def on_status(text: str) -> None:
            self.push_event("prereq_install_status", {"component": component, "text": text})

        if component == "python":
            success, message = prereqs.download_and_install_python(on_status)
        elif component == "vcredist_x86":
            success, message = prereqs.download_and_install_vcredist("x86", on_status)
        elif component == "vcredist_x64":
            success, message = prereqs.download_and_install_vcredist("x64", on_status)
        elif component == "directx_runtime":
            success, message = prereqs.download_and_install_directx_runtime(on_status)
        else:
            success, message = False, "Unknown component"

        with self._prereq_install_lock:
            self._prereq_install_in_progress = None
        self.push_event("prereq_install_done", {"component": component, "success": success, "message": message})
        # No restart needed to see the result -- prereqs.refresh_env_from_
        # registry's own docstring explains why -- so just re-run every
        # check now that something may have changed, same as the old
        # app's PrereqState._run_install did.
        self._run_prereq_checks()

    # ---- Mod repository (RELAY 033) -- ported from the old imgui app's
    # ModRepoState/_show_mod_repo_section, onto push_event instead of that
    # class's own polling design (same reasoning as Prerequisites above).

    def get_mod_repo_info(self) -> dict:
        """Synchronous, cheap -- the configured path (or its real default)
        plus the configured clone URL, for the drawer's read-only path
        field and the clone-confirm popup's own message."""
        return {"path": str(_resolve_mod_repo_path()), "url": settings_store.load_mod_repo_url()}

    def save_mod_repo_path(self, path: str) -> dict:
        """Persists the new location and re-detects against it -- any
        earlier update-check result was about the OLD location, so the JS
        side clears it itself before calling this (mirrors ModRepoState.
        set_configured_path's own "clear update_check, it's now stale")."""
        settings_store.save_mod_repo_path(path)
        threading.Thread(target=self._run_mod_repo_detect, daemon=True).start()
        return {"ok": True}

    def check_legacy_autodetect(self) -> dict:
        """RELAY 060: first-run offer, ported from the retired imgui app's
        real `_show_legacy_autodetect_popup()` (its own zero-profiles gate
        is the whole guard -- self-resolves the moment any profile exists,
        no persisted "don't ask again" flag needed). Synchronous and cheap
        (one file-exists check + a profile count), called once per session
        from the page's own init flow -- JS decides once-per-session-ness
        by only calling this during initial load, not on every
        loadData() refresh."""
        try:
            accounts_path = _resolve_mod_repo_path() / "accounts.json"
            if profile_store.load_profiles() or not accounts_path.is_file():
                return {"found": False}
            count = legacy_import.count_accounts(accounts_path)
            return {"found": True, "path": str(accounts_path), "count": count}
        except (OSError, ValueError):
            return {"found": False}

    def check_mod_repo(self) -> dict:
        """Cheap, filesystem-only -- safe to call automatically (this app's
        pywebviewready init does, same as check_prereqs) and after every
        path change/clone/update, same as detect_checkout's own docstring."""
        threading.Thread(target=self._run_mod_repo_detect, daemon=True).start()
        return {"ok": True}

    def _run_mod_repo_detect(self) -> None:
        result = mod_repo.detect_checkout(_resolve_mod_repo_path())
        self.push_event("mod_repo_result", {"status": result.status.value, "path": str(result.path)})

    def check_mod_repo_updates(self) -> dict:
        """Unlike detection, this hits the network (a real git fetch) --
        never called automatically, only from the page's explicit "Check
        for updates" click, same reasoning check_prereqs' checks don't
        apply to this one."""
        threading.Thread(target=self._run_mod_repo_check_updates, daemon=True).start()
        return {"ok": True}

    def _run_mod_repo_check_updates(self) -> None:
        result = mod_repo.check_for_updates(_resolve_mod_repo_path())
        self.push_event(
            "mod_repo_update_result",
            {
                "status": result.status.value,
                "message": result.message,
                "behind_count": result.behind_count,
                "ahead_count": result.ahead_count,
            },
        )

    def start_mod_repo_clone(self) -> dict:
        with self._mod_repo_op_lock:
            if self._mod_repo_op_in_progress is not None:
                return {"ok": False, "error": "An operation is already in progress"}
            self._mod_repo_op_in_progress = "clone"
        threading.Thread(target=self._run_mod_repo_clone, daemon=True).start()
        return {"ok": True}

    def _run_mod_repo_clone(self) -> None:
        def on_status(text: str) -> None:
            self.push_event("mod_repo_op_status", {"text": text})

        success, message = mod_repo.clone_mod_repo(_resolve_mod_repo_path(), on_status)
        with self._mod_repo_op_lock:
            self._mod_repo_op_in_progress = None
        self.push_event("mod_repo_op_done", {"success": success, "message": message})
        self._run_mod_repo_detect()

    def start_mod_repo_update(self) -> dict:
        with self._mod_repo_op_lock:
            if self._mod_repo_op_in_progress is not None:
                return {"ok": False, "error": "An operation is already in progress"}
            self._mod_repo_op_in_progress = "update"
        threading.Thread(target=self._run_mod_repo_update, daemon=True).start()
        return {"ok": True}

    def _run_mod_repo_update(self) -> None:
        def on_status(text: str) -> None:
            self.push_event("mod_repo_op_status", {"text": text})

        success, message = mod_repo.update_mod_repo(_resolve_mod_repo_path(), on_status)
        with self._mod_repo_op_lock:
            self._mod_repo_op_in_progress = None
        self.push_event("mod_repo_op_done", {"success": success, "message": message})
        # Same double re-run as the old app's _run_update -- detect (did the
        # checkout itself change) AND re-check-updates (are we caught up
        # now), not just one or the other.
        self._run_mod_repo_detect()
        self._run_mod_repo_check_updates()

    def browse_for_folder(self) -> Optional[str]:
        """Native folder-picker (RELAY 033) -- webview.FileDialog.FOLDER,
        pywebview's own built-in mode, no reason to port the old app's raw
        Win32 SHBrowseForFolder call (that exists there because ImGui has
        no native file-dialog primitive at all, a constraint this app
        doesn't share -- browse_for_file, RELAY 024, already made this
        same call for files). No title parameter -- confirmed via
        create_file_dialog's real signature that pywebview doesn't expose
        one for any dialog type, not an oversight here."""
        window = self._window()
        if window is None:
            return None
        result = window.create_file_dialog(webview.FileDialog.FOLDER, directory=str(_resolve_mod_repo_path()))
        return result[0] if result else None

    # ---- Backup/Restore accounts + Old Launcher Import (RELAY 034) ----
    # All three are fast, synchronous, local file operations (JSON read/
    # write, no network) -- no threading/push_event needed here, unlike
    # 032/033's slow install/clone/fetch operations. The de-dupe logic
    # below is ported directly from the old imgui app's STATE.import_
    # roster/import_legacy_accounts (there's no "STATE" object here, so it
    # lives inline in these two methods instead).

    def browse_for_save_file(self, default_filename: str, type_label: str, pattern: str) -> Optional[str]:
        """Sibling to browse_for_file (RELAY 024) -- same API, SAVE dialog
        type instead of OPEN, for the roster export's Save-As. Same
        file_types format, same reasoning."""
        window = self._window()
        if window is None:
            return None
        file_types = (f"{type_label} ({pattern})", "All files (*.*)")
        result = window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename=default_filename, file_types=file_types
        )
        return result[0] if result else None

    def export_roster(self, path: str, include_passwords: bool) -> dict:
        try:
            roster_transfer.export_roster(
                profile_store.load_profiles(), profile_store.load_teams(), path,
                include_passwords=bool(include_passwords),
            )
            return {"ok": True, "path": path}
        except OSError as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _result_to_dict(
        added_profiles: int, added_teams: int, skipped_profiles: int, skipped_teams: int,
        path_warnings: list, warnings: list,
    ) -> dict:
        return {
            "added_profiles": added_profiles,
            "added_teams": added_teams,
            "skipped_profiles": skipped_profiles,
            "skipped_teams": skipped_teams,
            "path_warnings": path_warnings,
            "warnings": warnings,
        }

    def import_roster(self, path: str) -> dict:
        """De-dupe by id (matches STATE.import_roster exactly) -- safe to
        re-import the same file twice, or import onto a machine that
        already has some of these profiles/teams."""
        try:
            imported_profiles, imported_teams = roster_transfer.import_roster(path)
        except Exception as e:  # a hand-edited or foreign JSON file can fail in many ways
            return {"ok": False, "error": str(e)}

        profiles = profile_store.load_profiles()
        teams = profile_store.load_teams()
        existing_profile_ids = {p.id for p in profiles}
        existing_team_ids = {t.id for t in teams}

        added_profiles = []
        skipped_profiles = 0
        for profile in imported_profiles:
            if profile.id in existing_profile_ids:
                skipped_profiles += 1
            else:
                existing_profile_ids.add(profile.id)  # also guards dup ids within the bundle
                profiles.append(profile)
                added_profiles.append(profile)

        added_teams = 0
        skipped_teams = 0
        for team in imported_teams:
            if team.id in existing_team_ids:
                skipped_teams += 1
            else:
                existing_team_ids.add(team.id)
                teams.append(team)
                added_teams += 1

        if added_profiles:
            profile_store.save_profiles(profiles)
        if added_teams:
            profile_store.save_teams(teams)

        return {
            "ok": True,
            "result": self._result_to_dict(
                len(added_profiles), added_teams, skipped_profiles, skipped_teams,
                roster_transfer.find_missing_paths(added_profiles), [],
            ),
        }

    def import_legacy_accounts(self, path: str) -> dict:
        """De-dupe rules differ from the native roster import (matches
        STATE.import_legacy_accounts exactly) -- legacy files carry no
        ids: teams match by name (reusing the existing team's id),
        profiles match by email when present, else by (executable_path,
        character_name)."""
        try:
            imported_profiles, imported_teams, warnings = legacy_import.parse_legacy_accounts(path)
        except Exception as e:
            return {"ok": False, "error": str(e)}

        profiles = profile_store.load_profiles()
        teams = profile_store.load_teams()

        existing_team_by_name = {t.name: t for t in teams}
        team_id_remap: dict = {}
        added_teams = 0
        skipped_teams = 0
        for team in imported_teams:
            existing = existing_team_by_name.get(team.name)
            if existing is not None:
                team_id_remap[team.id] = existing.id
                skipped_teams += 1
            else:
                teams.append(team)
                existing_team_by_name[team.name] = team
                team_id_remap[team.id] = team.id
                added_teams += 1
        for profile in imported_profiles:
            profile.team_ids = [team_id_remap.get(tid, tid) for tid in profile.team_ids]

        def _profile_keys(p: GameProfile):
            # RELAY 061: exe_char is always computable (executable_path/
            # character_name are always present) so it's listed first and
            # always checked -- email is appended only when present. A
            # single-key version (pick email if present, else exe_char) let
            # the same real account fail to merge if it appeared with email
            # populated in one team listing and blank in another (plausible:
            # credentials filled in once, the character re-entered elsewhere
            # without them) -- confirmed via a mock 30-character file where
            # 5 accounts with inconsistent email presence produced 35
            # profiles instead of 30. Checking/indexing both forms means a
            # match on EITHER key merges the profiles, regardless of which
            # listing was encountered first.
            keys = [("exe_char", p.executable_path, p.character_name)]
            if p.email:
                keys.append(("email", p.email))
            return keys

        # RELAY 060: existing_by_key maps to the actual GameProfile (not just
        # a seen-key set) so a cross-team duplicate can MERGE its team_ids
        # into the profile already kept, instead of the whole duplicate
        # object -- including the team membership it was carrying -- being
        # discarded outright. Root cause of Apo's real "teams came in with
        # zero members" report: his real file has overlapping team
        # categories (a class-based grouping and a misc/campaign grouping
        # both containing the same characters), so the same real account
        # legitimately appears under multiple team keys in one file: the
        # old set-based version correctly recognized the second occurrence
        # as "the same account" but then dropped its team_id along with it,
        # so a team whose members were ALL already-claimed-elsewhere
        # characters came back with zero members. Covers both a duplicate
        # against an already-stored profile and a duplicate within the same
        # import file (both go through this same dict).
        existing_by_key: dict = {}
        for p in profiles:
            for k in _profile_keys(p):
                existing_by_key[k] = p
        added_profiles = []
        skipped_profiles = 0
        merged_team_ids = False  # a duplicate-profile merge alone (no new profiles) still needs saving
        for profile in imported_profiles:
            keys = _profile_keys(profile)
            existing = None
            for k in keys:
                existing = existing_by_key.get(k)
                if existing is not None:
                    break
            if existing is not None:
                for tid in profile.team_ids:
                    if tid not in existing.team_ids:
                        existing.team_ids.append(tid)
                        merged_team_ids = True
                # RELAY 061: backfill whichever key form(s) this listing
                # carried but weren't indexed yet -- so a third listing with
                # yet another email/blank combination still resolves.
                for k in keys:
                    existing_by_key[k] = existing
                skipped_profiles += 1
            else:
                for k in keys:
                    existing_by_key[k] = profile  # also guards duplicates within the same file
                # RELAY 060: same new-profile DLL auto-default save_profile
                # applies -- a merged duplicate is skipped, not appended, so
                # only genuinely-new profiles need this.
                if profile.py4gw_enabled and not profile.py4gw_dll_path:
                    profile.py4gw_dll_path = _find_dll_under_mod_root("Py4GW.dll")
                if profile.gmod_enabled and not profile.gmod_dll_path:
                    profile.gmod_dll_path = _find_dll_under_mod_root("gMod.dll")
                # RELAY 060: the "must be set manually" warning moved here
                # from legacy_import.py, computed AFTER the auto-default
                # attempt above -- only warn if it's still genuinely missing,
                # not a stale warning on a profile that just got auto-filled.
                label = profile.character_name or "(unnamed profile)"
                if profile.py4gw_enabled and not profile.py4gw_dll_path:
                    warnings.append(
                        f"{label}: Py4GW injection was enabled in the old launcher; "
                        "the Py4GW DLL path must be set manually in Settings."
                    )
                if profile.gmod_enabled and not profile.gmod_dll_path:
                    warnings.append(
                        f"{label}: gMod injection was enabled in the old launcher; "
                        "the gMod DLL path must be set manually in Settings."
                    )
                profiles.append(profile)
                added_profiles.append(profile)

        if added_profiles or merged_team_ids:
            profile_store.save_profiles(profiles)
        if added_teams:
            profile_store.save_teams(teams)

        return {
            "ok": True,
            "result": self._result_to_dict(
                len(added_profiles), added_teams, skipped_profiles, skipped_teams,
                roster_transfer.find_missing_paths(added_profiles), warnings,
            ),
        }

    # ---- Live console (RELAY 021) -- shared by both launch paths below ----

    def get_console_lines(self) -> list:
        """Called once on page load (see app.js's loadConsoleHistory) so a
        page reload while this same process keeps running doesn't show an
        empty panel despite real history existing -- see the console
        deque's own docstring in __init__ for why this never survives a
        full app restart."""
        with self._console_lock:
            return list(self._console_lines)

    def clear_console(self) -> dict:
        with self._console_lock:
            self._console_lines.clear()
            self._console_countdown_active = False
        return {"ok": True}

    def _record_console_line(self, line: str, category: str) -> None:
        """Appends without pushing -- for a line seeded before the page has
        loaded (RELAY 035: run_shell.main's startup elevation-confirmation
        line, added right after bind_window but before webview.start()). A
        live push_event that early would race the page's own
        `window.shellBridge` assignment; get_console_lines() picking this up
        on the page's normal load (see loadConsoleHistory in app.js) is the
        only delivery path that matters for a line this early."""
        with self._console_lock:
            self._console_lines.append({"line": line, "category": category})
            self._console_countdown_active = False

    def _push_console_line(self, line: str, category: str) -> None:
        """Appends AND live-pushes -- for a pre-formatted, pre-categorized
        line added once the page is already loaded and interactive (RELAY
        035: the admin toggle flipped off mid-session). Bypasses
        _append_console_line's "[name] message" prefix and
        classify_progress_category's gw1_launch-specific needle list,
        neither of which apply to a launcher-level line with no profile or
        bulk-sequence context."""
        self._record_console_line(line, category)
        self.push_event("console_line", {"line": line, "category": category, "replace_last": False})

    def _append_console_line(self, profile_name: str, message: str) -> None:
        """The normal append path -- one new line, always. Ported from
        launcher.py's append_console_line exactly (same "[name] message"
        format), called from a launch thread's own on_log.

        Category (RELAY 030) is classified off the raw, unprefixed
        `message` -- the same text gw1_launch.py's own _log() calls emit,
        matching classify_progress_category's needle list exactly."""
        line = f"[{profile_name}] {message}"
        category = classify_progress_category(message)
        with self._console_lock:
            self._console_lines.append({"line": line, "category": category})
            self._console_countdown_active = False
        self.push_event("console_line", {"line": line, "category": category, "replace_last": False})

    def _update_console_countdown(self, message: str) -> None:
        """The bulk-sequence status path -- replaces the last line in place
        instead of appending, as long as the previous line was itself one
        of these updates (see _console_countdown_active's docstring).
        Ported from launcher.py's update_bulk_launch_countdown exactly
        (same "[Bulk Launch] message" format and replace-in-place
        semantics)."""
        line = f"[Bulk Launch] {message}"
        category = classify_progress_category(message)
        with self._console_lock:
            replace = bool(self._console_lines) and self._console_countdown_active
            entry = {"line": line, "category": category}
            if replace:
                self._console_lines[-1] = entry
            else:
                self._console_lines.append(entry)
            self._console_countdown_active = True
        self.push_event("console_line", {"line": line, "category": category, "replace_last": replace})

    # ---- Phase E: individual (single-profile) launch ----

    def launch_profile(self, profile_id: str) -> dict:
        """Launch one profile through the real GW1 pipeline
        (launcher_core.gw1_launch.launch_py4gw_profile) on a background thread --
        it blocks for the whole launch (seconds to, rarely, minutes). Progress
        is pushed to that profile's card via push_event('launch_log') and the
        final outcome via push_event('launch_done'); this call returns
        immediately.

        The whole GameProfile is handed to the pipeline, so every per-profile
        toggle (py4gw_enabled/gmod_enabled/auto_login_enabled/windowed_mode_
        enabled/...) already flows through with no extra wiring. The App Settings
        global master switches (multiclient/py4gw/gmod injection) aren't wired in
        the shell yet, so the pipeline's own defaults (all enabled) apply -- same
        as launcher.py before those switches existed.

        Rejects while a team/bulk launch (Phase F) is active -- a manual
        click launching a second, independent EnumWindows-polling pipeline
        concurrently with an active bulk sequence is exactly the GIL-
        contention hang class RELAY.md 004 already fixed once (see
        launch_profiles_bulk's docstring) -- the simplest guard is just
        refusing the second concurrent attempt here. The bulk sequence
        itself calls _start_launch directly, bypassing this check, since
        it IS the active sequence.
        """
        with self._launch_lock:
            if self._bulk_thread is not None and self._bulk_thread.is_alive():
                return {"ok": False, "error": "A team/bulk launch is already in progress"}
        return self._start_launch(profile_id)

    def _start_launch(self, profile_id: str) -> dict:
        """The actual single-launch start logic, factored out of
        launch_profile so _run_bulk_launch can call it directly without
        tripping launch_profile's own "reject during an active bulk
        sequence" guard (see launch_profile's docstring)."""
        profile = self._find_profile(profile_id)
        if profile is None:
            return {"ok": False, "error": "Profile not found"}
        with self._launch_lock:
            if profile_id in self._in_flight or profile_id in self._running_pids:
                return {"ok": False, "error": "Already launching or running"}
            self._in_flight.add(profile_id)
        threading.Thread(target=self._run_launch, args=(profile,), daemon=True).start()
        return {"ok": True}

    def _find_profile(self, profile_id: str) -> Optional[GameProfile]:
        # Load fresh from disk so a launch always uses current data AND can see
        # password_protected (which list_profiles strips) for auto-login.
        for p in profile_store.load_profiles():
            if p.id == profile_id:
                return p
        return None

    def _run_launch(self, profile: GameProfile) -> None:
        def on_log(message: str) -> None:
            self.push_event(
                "launch_log",
                {"profile_id": profile.id, "status": classify_progress_message(message)},
            )
            # Console gets the raw message (launcher.py's own console shows
            # raw pipeline output, not the friendly classified text the
            # per-card status line uses) -- same hook point for both the
            # individual and bulk launch paths, since bulk calls
            # _start_launch -> _run_launch too.
            self._append_console_line(profile.name or "(unnamed profile)", message)

        try:
            # RELAY 029: these three are the App Settings global master
            # switches -- confirmed as the ONLY launch_py4gw_profile call
            # site in pywebview_shell/ (grep), so this is the single place
            # that needs to read them. Before this fix, the launch pipeline
            # silently used the function's own hardcoded True defaults,
            # completely ignoring whatever settings_store had saved -- the
            # App Settings toggles would have looked real but done nothing.
            result = launch_py4gw_profile(
                profile,
                multiclient_enabled=settings_store.load_multiclient_enabled(),
                py4gw_injection_enabled=settings_store.load_py4gw_injection_enabled(),
                gmod_injection_enabled=settings_store.load_gmod_injection_enabled(),
                on_log=on_log,
            )
            success, pid, error = bool(result.success), result.pid, result.error
        except Exception as exc:  # a crashed launch thread must not vanish silently
            success, pid, error = False, None, f"Launch crashed: {exc}"

        # RELAY 040: some failure paths (e.g. "Py4GW DLL injection failed")
        # deliberately leave the real Gw.exe process running -- gw1_launch.py
        # never calls TerminateProcess there, unlike the multiclient-patch
        # failure path, which does. A real liveness check (not a guess off
        # the failure-reason string, several of which are genuinely
        # ambiguous) decides whether this failure needs tracking too, so
        # Stop can actually reach an orphaned client instead of the UI only
        # offering Launch -- which would spawn a second, duplicate process
        # for the same account.
        still_running = not success and pid is not None and _is_process_alive(pid)
        with self._launch_lock:
            self._in_flight.discard(profile.id)
            if (success or still_running) and pid is not None:
                self._running_pids[profile.id] = pid
        self.push_event(
            "launch_done",
            {"profile_id": profile.id, "success": success, "pid": pid, "error": error, "still_running": still_running},
        )

    def stop_profile(self, profile_id: str) -> dict:
        """Terminate the running client tracked for this profile (Phase E Stop).
        This kills an already-running, injected client -- it does NOT cancel an
        in-progress launch (a different, later concern; Stop only appears once
        the card is 'running')."""
        with self._launch_lock:
            pid = self._running_pids.get(profile_id)
        if pid is None:
            return {"ok": False, "error": "No running client tracked for this profile"}
        killed = terminate_process(pid)
        if killed:
            with self._launch_lock:
                self._running_pids.pop(profile_id, None)
        return {"ok": killed, "pid": pid}

    # ---- Two-way card <-> game-window focus sync (RELAY 041) ----

    def focus_profile_window(self, profile_id: str) -> dict:
        """Direction 1: click a card -> bring that profile's real running
        game window to the foreground. Synchronous, cheap (a handful of
        Win32 calls) -- same simple shape as stop_profile above, not
        032/033's threaded pattern; nothing here is slow enough to need it.
        """
        with self._launch_lock:
            pid = self._running_pids.get(profile_id)
        if pid is None:
            return {"ok": False, "error": "Profile is not running"}
        hwnd = window_control.find_visible_window_for_pid(pid)
        if hwnd is None:
            return {"ok": False, "error": "No visible window found for this profile"}
        window_control.foreground_window(hwnd)
        return {"ok": True}

    def _run_focus_poll(self) -> None:
        """Direction 2 of RELAY 041: continuously detect focus changes made
        OUTSIDE this app (Alt-Tab, taskbar, clicking a game window
        directly) and push which tracked profile (if any) now owns the OS
        foreground window. Polling (not SetWinEventHook), same pattern as
        every other real-time feature in this app (032/033's slow-
        operation push_event) -- consistency over a "more proper" but
        second, different live-update mechanism for a first attempt at
        this. ~500ms is responsive enough to feel live without
        meaningfully costing anything (one GetForegroundWindow + one
        GetWindowThreadProcessId per tick, regardless of how many profiles
        exist).

        Pushes "focused_profile_changed" only when the resolved profile_id
        actually changes, not every tick, to avoid redundant DOM churn on
        the JS side. Any foreground window that isn't a tracked pid --
        including this launcher's own window, deliberately not special-
        cased -- resolves to profile_id None, clearing every card's
        focused indicator (Chris's own confirmed answer: clear entirely,
        not persist the last one, when focus moves to something untracked).

        RELAY 042: also validates every tracked `_running_pids` entry each
        tick (`_is_process_alive`, same real check RELAY 040 already added
        for this exact purpose) -- before this, a client closed OUTSIDE the
        app (its own Exit, closing the window directly, not this app's
        Stop) left `_running_pids` stale forever, since the only place that
        ever popped an entry was `stop_profile` itself, a click-driven
        action. This loop already iterates that same dict every tick for
        the focus-match above, so checking liveness in the same pass is
        not new polling overhead, not a second thread -- reusing what 041
        already built, per this entry's own instruction. A pid found dead
        is popped and reported via a new "profile_exited" push per profile,
        BEFORE the focus-match check for that tick, so an exited pid can
        never be misreported as newly focused in the same tick it's
        removed.
        """
        last_reported: Optional[str] = "__unset__"  # sentinel: always push once, even if the real first state is None
        while True:
            time.sleep(0.5)
            try:
                foreground_pid = window_control.get_foreground_window_pid()
                matched_profile_id = None
                exited_profile_ids: list = []
                with self._launch_lock:
                    for candidate_id, pid in list(self._running_pids.items()):
                        if not _is_process_alive(pid):
                            exited_profile_ids.append(candidate_id)
                            del self._running_pids[candidate_id]
                            continue
                        if foreground_pid is not None and pid == foreground_pid:
                            matched_profile_id = candidate_id
                for profile_id in exited_profile_ids:
                    self.push_event("profile_exited", {"profile_id": profile_id})
                if matched_profile_id != last_reported:
                    last_reported = matched_profile_id
                    self.push_event("focused_profile_changed", {"profile_id": matched_profile_id})
            except Exception:
                pass  # best-effort -- one bad tick (a window destroyed mid-check, etc.) must not stop this loop

    # ---- Phase F: team/bulk launch ----

    def launch_profiles_bulk(self, profile_ids: list) -> dict:
        """Launch multiple profiles in order through the same single-launch
        pipeline _start_launch uses, paced between each per bulk_launch.py's
        proven anti-bot throttling (ported from GWxLauncher's
        BulkLaunchThrottlingPolicy.cs). Powers both "Launch Selected"
        (explicit profile_ids from the page's checkbox selection) and
        "Launch Team" (JS passes every profile currently in the active
        team) -- same method either way, the caller decides the list.

        Pacing comes from launcher_settings.json
        (settings_store.load_bulk_launch_pacing_seconds) -- the same shared
        setting the old imgui app's App Settings screen writes to. The
        pywebview shell has no App Settings UI yet (RELAY 019's known gap),
        so this reads whatever's already configured (or the same 30s
        default) rather than inventing a second, disconnected pacing value.

        Only one bulk sequence runs at a time -- a second call while one's
        already in flight is rejected outright, not queued behind it.
        Concurrent manual single-card launches are separately guarded in
        launch_profile (see its docstring) -- this is the same production
        bug class RELAY.md 004 fixed once already (concurrent EnumWindows-
        polling launches causing enough GIL contention to hang the app),
        and bulk sequencing naturally serializes its own launches one at a
        time by construction, but a manual click landing on top of an
        active sequence needed its own explicit guard.
        """
        with self._launch_lock:
            if self._bulk_thread is not None and self._bulk_thread.is_alive():
                return {"ok": False, "error": "A team/bulk launch is already in progress"}
            profiles = [p for p in (self._find_profile(pid) for pid in profile_ids) if p is not None]
            if not profiles:
                return {"ok": False, "error": "No valid profiles to launch"}
            pacing_seconds = settings_store.load_bulk_launch_pacing_seconds()
            self._bulk_cancel_event = threading.Event()
            self._bulk_thread = threading.Thread(
                target=self._run_bulk_launch, args=(profiles, pacing_seconds), daemon=True
            )
            self._bulk_thread.start()
        # RELAY 057: Py4GW.ini's autoexec_script key is root-scoped (one
        # shared file, not per-account) -- a concurrent/paced batch with
        # different scripts per profile can race on that shared key
        # (accepted, Apo's own call: "not a real problem in practice").
        # Cheap set-comparison over just the profiles about to launch, not
        # a pacing/timing fix -- silent whenever every profile shares the
        # same script (or none set at all), which is the common case.
        # Pushed as a real console line (bridge.py's own established
        # pattern for launcher-level heads-ups, e.g. _run_bulk_launch's
        # own "[Bulk Launch]" lines) rather than a new UI element.
        distinct_scripts = {p.script_path for p in profiles if p.script_path}
        if len(distinct_scripts) > 1:
            self._push_console_line(
                "Mixed auto-run scripts — assignment isn't guaranteed during concurrent launches.", "warn"
            )
        return {"ok": True, "count": len(profiles)}

    def cancel_bulk_launch(self) -> dict:
        """Stops queuing further accounts -- never force-closes an already-
        launched client, and never interrupts an in-flight individual
        launch (readiness wait included) partway. Same scope as the old
        imgui app's BulkLaunchSession.cancel.
        """
        with self._launch_lock:
            event = self._bulk_cancel_event
        if event is None:
            return {"ok": False, "error": "No bulk launch in progress"}
        event.set()
        return {"ok": True}

    def _run_bulk_launch(self, profiles: list, pacing_seconds: int) -> None:
        """Runs on its own background thread (started by
        launch_profiles_bulk). Mirrors launcher.py's BulkLaunchSession._run
        shape -- loop in order, skip an already-running profile with a
        status note, launch through _start_launch, wait_for_readiness
        (bounded, not the full launch -- see module docstring on why a
        timeout here isn't an error), pace before the next one (not after
        the last).

        Every profile is marked "queued" up front (not just as the loop
        reaches each one) so the UI reflects the whole sequence immediately
        on click, not one card at a time. Whatever's still queued when the
        loop ends (cancelled, or -- shouldn't happen -- an unhandled
        exception) gets pushed back to idle explicitly via
        'bulk_launch_done' rather than left showing "Queued" forever.
        """
        cancel_event = self._bulk_cancel_event
        total = len(profiles)

        for position, profile in enumerate(profiles, start=1):
            self.push_event(
                "launch_queued", {"profile_id": profile.id, "status": f"Queued... ({position} of {total})"}
            )

        def status_update(pid: str, msg: str) -> None:
            self.push_event("launch_queued", {"profile_id": pid, "status": msg})
            self._update_console_countdown(msg)

        started_ids: set[str] = set()
        try:
            for i, profile in enumerate(profiles):
                if cancel_event.is_set():
                    # RELAY 030: previously silent -- the loop just broke
                    # with no console line, so cancellation was only
                    # inferable from the sequence stopping, never stated.
                    self._update_console_countdown("Bulk launch cancelled")
                    break

                # Fresh check right before each launch, not just once up
                # front -- an earlier account in this same batch could
                # still be settling into "running" while we reach a later
                # one.
                with self._launch_lock:
                    already_running = profile.id in self._running_pids
                if already_running:
                    started_ids.add(profile.id)
                    self.push_event(
                        "launch_queued", {"profile_id": profile.id, "status": "Skipped (already running)"}
                    )
                    self._update_console_countdown(f"Skipping {profile.name or '(unnamed profile)'} (already running)")
                else:
                    self._update_console_countdown(f"Launching {profile.name or '(unnamed profile)'}...")
                    result = self._start_launch(profile.id)
                    started_ids.add(profile.id)
                    if not result.get("ok"):
                        self.push_event(
                            "launch_queued",
                            {"profile_id": profile.id, "status": f"Skipped ({result.get('error', 'could not start')})"},
                        )
                        self._update_console_countdown(f"Skipping {profile.name or '(unnamed profile)'} ({result.get('error', 'could not start')})")
                    else:
                        bulk_launch.wait_for_readiness(
                            lambda pid=profile.id: pid not in self._in_flight,
                            on_status=lambda msg, pid=profile.id: status_update(pid, msg),
                            should_cancel=cancel_event.is_set,
                        )

                is_last = i == total - 1
                if not is_last and not cancel_event.is_set():
                    next_profile = profiles[i + 1]
                    bulk_launch.apply_pacing_delay(
                        pacing_seconds,
                        on_status=lambda msg, pid=next_profile.id: status_update(pid, msg),
                        should_cancel=cancel_event.is_set,
                    )
        finally:
            never_started = [p.id for p in profiles if p.id not in started_ids]
            with self._launch_lock:
                self._bulk_cancel_event = None
                self._bulk_thread = None
            self.push_event("bulk_launch_done", {"reset_profile_ids": never_started})

    def save_profile(self, data: dict) -> dict:
        """Add or update a profile (RELAY 011) -- `data["id"]` matching an
        existing profile means update, otherwise a new one is created.

        Password handling: `list_profiles()` never sends `password_protected`
        to JS, and this method ignores any `password_protected` the caller
        supplies too (never trust a client-side value for an encrypted
        field) -- the only way to actually change a password is a non-empty
        `new_password` (plaintext, freshly typed in the drawer). An empty/
        absent `new_password` leaves an existing profile's real DPAPI blob
        completely untouched, which is what lets the edit drawer show a
        blank/placeholder password field without silently wiping the stored
        password every time someone saves unrelated changes.

        No `run_as_admin`-shaped field here -- deliberately not added this
        round (RELAY 011): `GameProfile` has no such field today, and the
        actual UAC/elevation mechanism is still undesigned, so a stored
        field with nothing behind it would be a control that lies about
        what it does. Left out entirely rather than half-built.
        """
        profiles = profile_store.load_profiles()
        profile_id = data.get("id")
        new_password = data.pop("new_password", "") or ""
        data.pop("password_protected", None)

        writable_fields = {f.name for f in dataclasses.fields(GameProfile)} - {"password_protected"}
        existing = next((p for p in profiles if p.id == profile_id), None) if profile_id else None

        if existing is not None:
            for field_name in writable_fields:
                if field_name in data:
                    setattr(existing, field_name, data[field_name])
            target = existing
        else:
            filtered = {k: v for k, v in data.items() if k in writable_fields}
            target = GameProfile(**filtered)
            # RELAY 060: auto-default DLL paths on a brand-new profile only
            # (an existing profile's own explicit blank is left alone --
            # this is a new-profile convenience, not a standing "fill in
            # whatever's missing" behavior).
            if target.py4gw_enabled and not target.py4gw_dll_path:
                target.py4gw_dll_path = _find_dll_under_mod_root("Py4GW.dll")
            if target.gmod_enabled and not target.gmod_dll_path:
                target.gmod_dll_path = _find_dll_under_mod_root("gMod.dll")
            profiles.append(target)

        if new_password:
            target.password_protected = crypto.protect_password(new_password)

        profile_store.save_profiles(profiles)
        result = target.to_dict()
        result.pop("password_protected", None)
        return result

    def browse_for_file(self, type_label: str, pattern: str) -> Optional[str]:
        """Native file-browse dialog for the edit drawer's Mods tab (RELAY
        024) -- DLL paths and gMod plugin (.tpf) selection. `pattern` is a
        glob like "*.dll", matching pywebview's own file_types format
        (`create_file_dialog`'s docstring: `'Description (*.ext[;*.ext2...])'`
        tuples). Investigated the text-paste fallback the entry allowed for,
        but this API is straightforward to call from a bridge method with no
        extra wiring, so there's no reason to fall back to it.
        """
        window = self._window()
        if window is None:
            return None
        file_types = (f"{type_label} ({pattern})", "All files (*.*)")
        result = window.create_file_dialog(webview.FileDialog.OPEN, file_types=file_types)
        return result[0] if result else None

    def delete_profile(self, profile_id: str) -> bool:
        """Permanently remove a profile from every team it belonged to.
        Only the right call while viewing ALL -- see remove_profile_from_team
        for the team-scoped version (RELAY 011's context-aware distinction).
        """
        profiles = profile_store.load_profiles()
        remaining = [p for p in profiles if p.id != profile_id]
        if len(remaining) == len(profiles):
            return False
        profile_store.save_profiles(remaining)
        return True

    def remove_profile_from_team(self, profile_id: str, team_id: str) -> bool:
        """Strip one team's id from one profile's team_ids -- the profile
        itself is untouched and keeps existing in ALL and any other teams.
        The team-scoped counterpart to delete_profile (RELAY 011).
        """
        profiles = profile_store.load_profiles()
        target = next((p for p in profiles if p.id == profile_id), None)
        if target is None:
            return False
        if team_id in target.team_ids:
            target.team_ids = [t for t in target.team_ids if t != team_id]
            profile_store.save_profiles(profiles)
        return True

    def add_profiles_to_team(self, profile_ids: list, team_id: str) -> bool:
        """Bulk-assign: append `team_id` to every listed profile's team_ids,
        skipping any that already have it.
        """
        profiles = profile_store.load_profiles()
        changed = False
        for p in profiles:
            if p.id in profile_ids and team_id not in p.team_ids:
                p.team_ids.append(team_id)
                changed = True
        if changed:
            profile_store.save_profiles(profiles)
        return True

    def add_team(self, name: str) -> dict:
        teams = profile_store.load_teams()
        new_team = Team(name=name)
        teams.append(new_team)
        profile_store.save_teams(teams)
        return new_team.to_dict()

    def rename_team(self, team_id: str, new_name: str) -> dict:
        """RELAY 057: reuses the same load/mutate/save shape as add_team/
        remove_team, not a new pattern -- rename never existed before this,
        confirmed via source (only add_team/remove_team were ever wired)."""
        teams = profile_store.load_teams()
        for t in teams:
            if t.id == team_id:
                t.name = new_name
                profile_store.save_teams(teams)
                return t.to_dict()
        return {}

    def remove_team(self, team_id: str) -> bool:
        """Deletes the Team itself, but never deletes profiles -- every
        profile that had this team's id gets it stripped from team_ids and
        falls back to whatever other teams it's in (or ALL-only).
        """
        teams = profile_store.load_teams()
        remaining_teams = [t for t in teams if t.id != team_id]
        if len(remaining_teams) == len(teams):
            return False
        profile_store.save_teams(remaining_teams)

        profiles = profile_store.load_profiles()
        changed = False
        for p in profiles:
            if team_id in p.team_ids:
                p.team_ids = [t for t in p.team_ids if t != team_id]
                changed = True
        if changed:
            profile_store.save_profiles(profiles)
        return True

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
