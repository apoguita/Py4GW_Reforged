"""AgentRecolor — thin Python wrapper over the embedded ``PyAgentRecolor`` module.

This is the source-of-truth surface the rest of the library uses to drive overhead
name-tag recoloring, the counterpart of how :mod:`Agent` wraps ``PyAgent``. It owns
NO rules and NO scheduling — it only translates clean Python calls into the native
primitives and normalises colors. The rule engine (filtering the agent array each
data-phase pass and handing the matched set here) lives in
``py4gwcorelib_src.system_settings.agent_recolor``.

Native recap (see ``stubs/PyAgentRecolor.pyi``): three detours recolor living agents,
gadgets and ground items; Python owns a master hook switch, per-category enable gates,
and the rule stores. Colors are ARGB ``0xAARRGGBB`` and the alpha byte is a
fade/hide channel: ``0xFF`` solid, ``0x01..0xFE`` fade, ``0x00`` hide.

``PyAgentRecolor`` is imported lazily so this module stays import-safe offline; every
call no-ops (or returns a benign default) when the native module is unavailable.
"""

from typing import List
from typing import Optional
from typing import Tuple


def _ar():
    """The native ``PyAgentRecolor`` module, or None when unavailable (offline)."""
    try:
        import PyAgentRecolor

        return PyAgentRecolor
    except Exception:
        return None


class RecolorMode:
    """How a rule's color is applied, encoded into the ARGB alpha byte."""

    SOLID = "solid"   # alpha 0xFF — opaque recolor
    FADE = "fade"     # alpha 0x01..0xFE — semi-transparent (dimmer)
    HIDE = "hide"     # alpha 0x00 — name tag blanked


class AgentRecolor:
    """Static facade over ``PyAgentRecolor``. All methods are safe to call offline."""

    # ── color helpers ────────────────────────────────────────────────────────────────────
    @staticmethod
    def RGBToARGB(rgb: int, alpha: int = 0xFF) -> int:
        """Combine a ``0xRRGGBB`` color and an 8-bit alpha into ``0xAARRGGBB``."""
        return ((int(alpha) & 0xFF) << 24) | (int(rgb) & 0xFFFFFF)

    @staticmethod
    def ARGB(mode: str, rgb: int, alpha: int = 0xFF) -> int:
        """Resolve a (mode, rgb, alpha) triple to the ARGB the native store expects.

        ``HIDE`` -> ``0x00000000`` (alpha 0), ``FADE`` -> clamped 1..254 alpha,
        ``SOLID`` -> 0xFF alpha. ``rgb`` is ``0xRRGGBB``.
        """
        rgb &= 0xFFFFFF
        if mode == RecolorMode.HIDE:
            return 0x00000000
        if mode == RecolorMode.FADE:
            a = max(1, min(254, int(alpha))) & 0xFF
            return (a << 24) | rgb
        return 0xFF000000 | rgb

    @staticmethod
    def FloatRGBToInt(rgb: "Tuple[float, float, float]") -> int:
        """Convert an ImGui ``(r, g, b)`` float triple (0..1) to ``0xRRGGBB``."""
        r, g, b = rgb
        return ((int(r * 255) & 0xFF) << 16) | ((int(g * 255) & 0xFF) << 8) | (int(b * 255) & 0xFF)

    @staticmethod
    def IntRGBToFloat(rgb: int) -> "Tuple[float, float, float]":
        """Convert ``0xRRGGBB`` to an ImGui ``(r, g, b)`` float triple (0..1)."""
        return ((rgb >> 16) & 0xFF) / 255.0, ((rgb >> 8) & 0xFF) / 255.0, (rgb & 0xFF) / 255.0

    # ── master hook switch (per-account System Settings toggle) ───────────────────────────
    @staticmethod
    def MasterEnable() -> None:
        ar = _ar()
        if ar is not None:
            try:
                ar.master_enable()
            except Exception:
                pass

    @staticmethod
    def MasterDisable() -> None:
        ar = _ar()
        if ar is not None:
            try:
                ar.master_disable()
            except Exception:
                pass

    @staticmethod
    def IsMasterEnabled() -> bool:
        ar = _ar()
        if ar is None:
            return False
        try:
            return bool(ar.is_master_enabled())
        except Exception:
            return False

    @staticmethod
    def IsHookInstalled() -> bool:
        ar = _ar()
        if ar is None:
            return False
        try:
            return bool(ar.is_hook_installed())
        except Exception:
            return False

    # ── per-category enable gates ─────────────────────────────────────────────────────────
    @staticmethod
    def EnableAgents(on: bool = True) -> None:
        ar = _ar()
        if ar is None:
            return
        try:
            ar.enable() if on else ar.disable()
        except Exception:
            pass

    @staticmethod
    def EnableGadgets(on: bool = True) -> None:
        ar = _ar()
        if ar is None:
            return
        try:
            ar.gadget_enable() if on else ar.gadget_disable()
        except Exception:
            pass

    # ── bulk rule application (the data-phase engine's push path) ──────────────────────────
    @staticmethod
    def SetAgentColors(rules: "List[Tuple[int, int]]") -> None:
        """Replace the WHOLE per-agent store with ``rules`` (list of ``(agent_id, argb)``)."""
        ar = _ar()
        if ar is None:
            return
        try:
            ar.set_agent_colors(rules)
        except Exception:
            pass

    @staticmethod
    def SetGadgetColors(rules: "List[Tuple[int, int]]") -> None:
        """Replace the WHOLE per-gadget store with ``rules`` (list of ``(agent_id, argb)``)."""
        ar = _ar()
        if ar is None:
            return
        try:
            ar.set_gadget_colors(rules)
        except Exception:
            pass

    # ── ground items ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def EnableItems(on: bool = True) -> None:
        ar = _ar()
        if ar is None:
            return
        try:
            ar.item_enable() if on else ar.item_disable()
        except Exception:
            pass

    @staticmethod
    def AreItemsEnabled() -> bool:
        ar = _ar()
        if ar is None:
            return False
        try:
            return bool(ar.item_is_enabled())
        except Exception:
            return False

    @staticmethod
    def SetItemColors(rules: "List[Tuple[int, int]]") -> None:
        """Replace the WHOLE per-item-agent store with ``rules`` (``(agent_id, argb)``).

        Ids not present are dropped; the item_id / model / name / type / rarity stores are
        separate and untouched. This is the marking feature's whole delivery surface: the
        caller resolves every match itself and hands over one already-decided colour per agent.

        The per-kind item setters (model / name / type / rarity) stay deliberately unexposed --
        under this design the caller resolves matching, so a second matching path in the backend
        would be a competing authority.
        """
        ar = _ar()
        if ar is None:
            return
        try:
            ar.set_item_agent_colors(rules)
            return
        except AttributeError:
            pass
        except Exception:
            return
        # The bulk binding is missing (a DLL built before it existed). Reproduce it exactly with
        # the per-id calls -- set what is wanted, drop what is no longer there -- so behaviour is
        # identical and only the call count differs.
        try:
            wanted = {int(agent_id): int(argb) for agent_id, argb in rules}
            for agent_id in [i for i in ar.get_item_agent_rules() if i not in wanted]:
                ar.remove_item_agent_color(agent_id)
            for agent_id, argb in wanted.items():
                ar.set_item_agent_color(agent_id, argb)
        except Exception:
            pass

    @staticmethod
    def ClearItemRules() -> None:
        ar = _ar()
        if ar is None:
            return
        try:
            ar.item_clear_rules()
        except Exception:
            pass

    @staticmethod
    def RefreshNameTags() -> None:
        """Force every overhead name tag to re-render so a rule change applies without a hover."""
        ar = _ar()
        if ar is None:
            return
        try:
            ar.refresh_name_tags()
        except Exception:
            pass

    @staticmethod
    def ClearAllRules() -> None:
        ar = _ar()
        if ar is None:
            return
        try:
            ar.clear_all_rules()
        except Exception:
            pass

    # ── diagnostics passthrough ───────────────────────────────────────────────────────────
    @staticmethod
    def GetDiagnostics() -> dict:
        ar = _ar()
        if ar is None:
            return {}
        try:
            return dict(ar.get_diagnostics() or {})
        except Exception:
            return {}

    @staticmethod
    def IsAvailable() -> bool:
        return _ar() is not None
