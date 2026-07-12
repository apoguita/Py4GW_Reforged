"""Narrow adapter over the function catalog + Font Awesome helpers.

Mirrors :class:`WidgetRuntime`: it enumerates catalog functions and invokes them, so tiles and
the editor depend on a small stable surface instead of the catalog module directly. Functions
are *fire-and-forget* — there is no enabled/toggle state (unlike widgets).

Also exposes the two Font Awesome helpers shared by the host (rendering a tile's glyph) and the
editor (the searchable icon picker), so ``IconsFontAwesome5`` is imported in exactly one place.
Everything is lazy/defensive: safe to import and call offline (returns empty / None).
"""

from typing import Optional

from .functions_catalog import FUNCTIONS
from .functions_catalog import LaunchFunction


def _icons_module():
    """The IconsFontAwesome5 module, or None when unavailable (offline)."""

    try:
        from Py4GWCoreLib.ImGui_Legacy_src.IconsFontAwesome5 import IconsFontAwesome5

        return IconsFontAwesome5
    except Exception:
        return None


def resolve_icon(name: Optional[str]) -> Optional[str]:
    """Font Awesome glyph string for an ``ICON_*`` constant name, or None if unknown/offline."""

    if not name:
        return None
    ic = _icons_module()
    if ic is None:
        return None
    glyph = getattr(ic, name, None)
    return glyph if isinstance(glyph, str) else None


def list_icons() -> list[tuple[str, str]]:
    """``(name, glyph)`` for every ``ICON_*`` constant, sorted by name (empty offline)."""

    ic = _icons_module()
    if ic is None:
        return []
    out: list[tuple[str, str]] = []
    for name in dir(ic):
        if not name.startswith("ICON_"):
            continue
        glyph = getattr(ic, name)
        if isinstance(glyph, str):
            out.append((name, glyph))
    out.sort(key=lambda x: x[0])
    return out


class FunctionRuntime:
    """Enumerate + invoke catalog functions. Fire-and-forget; no per-function state."""

    def list_functions(self) -> list[LaunchFunction]:
        return list(FUNCTIONS)

    def get(self, function_id: Optional[str]) -> Optional[LaunchFunction]:
        if not function_id:
            return None
        return next((f for f in FUNCTIONS if f.id == function_id), None)

    def invoke(self, function_id: Optional[str]) -> None:
        """Run the bound function's callback once; never let a bad callback break the frame."""

        fn = self.get(function_id)
        if fn is None:
            self._log("invoke: unknown function id %r" % function_id)
            return
        try:
            fn.callback()
        except Exception as exc:
            self._log('invoke "%s" raised: %s' % (fn.id, exc))

    def _log(self, msg: str) -> None:
        try:
            import PySystem

            PySystem.Console.Log("LaunchBar", msg, PySystem.Console.MessageType.Warning)
        except Exception:
            pass
