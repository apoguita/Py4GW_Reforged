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

import dataclasses
import json
import weakref
from typing import Any, Optional

import webview

from launcher_core import crypto, profile_store
from launcher_core.profile import GameProfile
from launcher_core.team import Team
from pywebview_shell import snap
from pywebview_shell.window_shell import start_native_resize


def _rects_close(a, b, tol: int = 4) -> bool:
    """Whether two (x, y, w, h) rects match within a few px (SetWindowPos can
    land a pixel or two off after DPI rounding)."""
    return all(abs(pa - pb) <= tol for pa, pb in zip(a, b))


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
        self._snap_rect: Optional[tuple[int, int, int, int]] = None
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

    def set_accent(self, r: int, g: int, b: int) -> bool:
        """The page reports its theme ACCENT (from CSS --accent) so the snap
        preview overlay is drawn in the user's accent, not a hardcoded colour.
        """
        if self._preview is not None:
            self._preview.set_accent(r, g, b)
        return True

    def on_drag_start(self) -> bool:
        """A title-bar mousedown. Record the cursor so on_drag_end can tell a
        drag from a click, start the preview, and -- if this window is snapped
        -- restore its pre-snap SIZE so the user drags a normal window again
        (easy_drag then repositions it, so we only fix size here).
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
            profiles.append(target)

        if new_password:
            target.password_protected = crypto.protect_password(new_password)

        profile_store.save_profiles(profiles)
        result = target.to_dict()
        result.pop("password_protected", None)
        return result

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
