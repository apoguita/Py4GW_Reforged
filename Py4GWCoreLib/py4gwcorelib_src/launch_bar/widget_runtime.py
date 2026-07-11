"""Narrow adapter over the widget runtime (``WidgetHandler``).

This is the ONLY launch-bar code that knows the handler's method names, so tiles/browser
depend on a small stable surface instead of handler internals. It consumes the neutral runtime
+ catalog metadata; it does NOT depend on the widget-manager UI we replace, and it does NOT do
discovery/bootstrap (a future "main toolbar" owns that). ``WidgetHandler`` is imported lazily so
importing this module never pulls in the heavy facade.

All enable/disable/configure calls are keyed by the full widget id (``folder_script_name``);
the handler's enable/disable take ``plain_name``, so we bridge via the resolved ``Widget``.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class WidgetMeta:
    """Read-only view of one widget for the launch bar."""

    id: str            # full folder_script_name (stable key)
    name: str          # display name
    icon: str          # image path (may be a missing-texture path or empty)
    category: str      # top folder / MODULE_CATEGORY
    enabled: bool
    configurable: bool
    folder: str = ""       # normalized "/"-separated folder path (from widget_path) for the tree
    configuring: bool = False   # is its configure panel currently open


def _handler():
    """The WidgetHandler singleton, or None if the runtime is unavailable."""

    try:
        from Py4GWCoreLib.py4gwcorelib_src.WidgetManager import get_widget_handler

        return get_widget_handler()
    except Exception:
        return None


class WidgetRuntime:
    """Enumerate + toggle + configure widgets through the handler. Safe when it's unavailable."""

    def _meta(self, widget_id: str, w) -> WidgetMeta:
        folder = str(getattr(w, "widget_path", "") or "")
        if not folder:  # derive from the id: "a/b/c/Widget.py" -> "a/b/c"
            rel = widget_id.replace("\\", "/").rsplit(".", 1)[0]
            folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
        folder = folder.replace("\\", "/").strip("/")
        category = str(getattr(w, "category", "") or "") or (folder.split("/")[0] if folder else "")
        return WidgetMeta(
            id=widget_id,
            name=str(getattr(w, "name", "") or widget_id),
            icon=str(getattr(w, "image", "") or ""),
            category=category,
            enabled=bool(getattr(w, "enabled", False)),
            configurable=bool(getattr(w, "has_configure_property", False)),
            folder=folder,
            configuring=bool(getattr(w, "configuring", False)),
        )

    def list_widgets(self) -> list[WidgetMeta]:
        h = _handler()
        if h is None:
            return []
        out = []
        for widget_id, w in getattr(h, "widgets", {}).items():
            try:
                out.append(self._meta(widget_id, w))
            except Exception:
                continue
        return out

    def _widget(self, widget_id: str):
        h = _handler()
        if h is None or not widget_id:
            return None
        try:
            return h.get_widget_info(widget_id)
        except Exception:
            return None

    def get(self, widget_id: str) -> Optional[WidgetMeta]:
        w = self._widget(widget_id)
        return self._meta(widget_id, w) if w is not None else None

    def tooltip_text(self, widget_id: str) -> str:
        m = self.get(widget_id)
        if m is None:
            return widget_id or ""
        return "Enable / disable %s" % m.name

    def draw_tooltip(self, widget_id: str) -> bool:
        """Render the widget's OWN tooltip if it defines one, exactly as the Widget Manager does.

        A widget may expose ``has_tooltip_property`` + a ``tooltip`` callable that draws its own
        tooltip window (begin_tooltip/…/end_tooltip). Call this only while the row is hovered.
        Returns True if a custom tooltip was drawn, False otherwise (caller shows a fallback).
        """
        w = self._widget(widget_id)
        if w is None or not bool(getattr(w, "has_tooltip_property", False)):
            return False
        fn = getattr(w, "tooltip", None)
        if not callable(fn):
            return False
        try:
            fn()
            return True
        except Exception:
            return False

    def is_enabled(self, widget_id: str) -> bool:
        w = self._widget(widget_id)
        return bool(getattr(w, "enabled", False)) if w is not None else False

    def toggle(self, widget_id: str) -> None:
        h = _handler()
        w = self._widget(widget_id)
        if h is None or w is None:
            return
        if bool(getattr(w, "enabled", False)):
            # System-safe disable path (defers System widgets to their confirmation modal)
            try:
                h._request_disable_widget(w)
            except Exception:
                try:
                    h.disable_widget(w.plain_name)
                except Exception:
                    pass
        else:
            try:
                h.enable_widget(w.plain_name)
            except Exception:
                pass

    def set_configuring(self, widget_id: str, value: bool = True) -> None:
        h = _handler()
        w = self._widget(widget_id)
        if h is None or w is None:
            return
        try:
            h.set_widget_configuring(w.plain_name, value)
        except Exception:
            pass

    # ---- favorites (shared with the Widget Manager) ---------------------------------
    # The WM persists favorites in its account settings under [Favorites] favorites as a
    # comma-separated list of widget ids. The handler exposes that settings key as
    # MANAGER_INI_KEY, so we read/write the SAME store instead of keeping a private set.
    def _fav_cfg(self):
        h = _handler()
        if h is None:
            return None
        key = str(getattr(h, "MANAGER_INI_KEY", "") or "")
        if not key:
            return None
        try:
            from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

            return Settings.find(key)
        except Exception:
            return None

    def list_favorites(self) -> set:
        cfg = self._fav_cfg()
        if cfg is None:
            return set()
        try:
            raw = cfg.get_str("Favorites", "favorites", "") or ""
        except Exception:
            return set()
        return {p.strip() for p in raw.split(",") if p.strip()}

    def is_favorite(self, widget_id: str) -> bool:
        return bool(widget_id) and widget_id in self.list_favorites()

    def set_favorite(self, widget_id: str, value: bool) -> None:
        cfg = self._fav_cfg()
        if cfg is None or not widget_id:
            return
        favs = self.list_favorites()
        if value:
            favs.add(widget_id)
        else:
            favs.discard(widget_id)
        try:
            cfg.set("Favorites", "favorites", ",".join(sorted(favs)))
        except Exception:
            pass

    def toggle_favorite(self, widget_id: str) -> None:
        self.set_favorite(widget_id, not self.is_favorite(widget_id))
