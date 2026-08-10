"""Name Obfuscation controller — the process-wide singleton owning the alias identity set.

Responsibilities:
  * hold the global state (master enable, ``{real -> fake}`` alias map, name buckets, surface
    toggles), loaded from the global document;
  * **register it with the native side** — apply the whole set to ``PyNameObfuscator`` at boot
    (``apply_to_native``) and on every change;
  * generate fake names by shuffling the buckets, and enumerate known character names (the live
    character-select list for the current account + the persistent multi-account accounts DB).

``PyNameObfuscator`` / ``Map`` / ``Account`` are imported lazily so this module stays import-safe
offline. One instance per process (``get_controller``), shared by the System Settings widget (boot +
UI) — mirrors ``map_overlay`` / ``system_settings``.
"""

import random
from typing import Optional

from . import model
from . import store


def _pyno():
    """The native ``PyNameObfuscator`` module, or None when unavailable (offline)."""
    try:
        import PyNameObfuscator

        return PyNameObfuscator
    except Exception:
        return None


class NameObfuscationController:
    def __init__(self) -> None:
        self.state: dict = {}
        store.load(self.state)
        self._known_chars: "list[str]" = []

    # ── queries ──────────────────────────────────────────────────────────────────────────
    @property
    def enabled(self) -> bool:
        return bool(self.state.get("enabled", False))

    @property
    def aliases(self) -> "dict[str, str]":
        return self.state.setdefault("aliases", {})

    @property
    def first_names(self) -> "list[str]":
        return self.state.setdefault("first_names", list(model.DEFAULT_FIRST_NAMES))

    @property
    def surnames(self) -> "list[str]":
        return self.state.setdefault("surnames", list(model.DEFAULT_SURNAMES))

    @property
    def known_characters(self) -> "list[str]":
        return self._known_chars

    def alias_for(self, real_name: str) -> str:
        return self.aliases.get(real_name, "")

    # ── native application (register aliases with the obfuscator) ─────────────────────────
    def apply_to_native(self) -> None:
        """Push the entire identity set to ``PyNameObfuscator``. Called at boot and on changes."""
        no = _pyno()
        if no is None:
            return
        try:
            no.clear_aliases()
            for real, fake in self.aliases.items():
                if real and fake:
                    no.set_alias(real, fake)
        except Exception:
            pass
        try:
            no.enable() if self.enabled else no.disable()
        except Exception:
            pass
        for surface, on in self.state.get("surfaces", {}).items():
            try:
                no.set_surface_enabled(surface, bool(on))
            except Exception:
                pass

    # ── mutations (persist + apply live) ─────────────────────────────────────────────────
    def set_enabled(self, value: bool) -> None:
        self.state["enabled"] = bool(value)
        store.save_enabled(bool(value))
        no = _pyno()
        if no is not None:
            try:
                no.enable() if value else no.disable()
            except Exception:
                pass

    def set_alias(self, real_name: str, fake_name: str) -> None:
        real_name = (real_name or "").strip()
        fake_name = (fake_name or "").strip()
        if not real_name:
            return
        self.aliases[real_name] = fake_name
        store.save_aliases(self.aliases)
        no = _pyno()
        if no is not None and fake_name:
            try:
                no.set_alias(real_name, fake_name)
            except Exception:
                pass

    def remove_alias(self, real_name: str) -> None:
        if real_name in self.aliases:
            del self.aliases[real_name]
            store.save_aliases(self.aliases)
            no = _pyno()
            if no is not None:
                try:
                    no.remove_alias(real_name)
                except Exception:
                    pass

    def clear_aliases(self) -> None:
        self.state["aliases"] = {}
        store.save_aliases({})
        no = _pyno()
        if no is not None:
            try:
                no.clear_aliases()
            except Exception:
                pass

    # ── fake-name generation (shuffle the buckets) ───────────────────────────────────────
    def shuffle_name(self) -> str:
        first = random.choice(self.first_names) if self.first_names else "Anon"
        surname = random.choice(self.surnames) if self.surnames else ""
        return ("%s %s" % (first, surname)).strip()

    def assign_random(self, real_name: str) -> None:
        """Assign a freshly-shuffled fake name to ``real_name``."""
        self.set_alias(real_name, self.shuffle_name())

    def assign_random_to_unaliased(self) -> int:
        """Shuffle a fake for every known character that has no alias yet. Returns count assigned."""
        count = 0
        for name in self._known_chars:
            if not self.aliases.get(name):
                self.set_alias(name, self.shuffle_name())
                count += 1
        return count

    # ── buckets ──────────────────────────────────────────────────────────────────────────
    def set_buckets(self, first_names: "list[str]", surnames: "list[str]") -> None:
        self.state["first_names"] = [n.strip() for n in first_names if n.strip()]
        self.state["surnames"] = [n.strip() for n in surnames if n.strip()]
        store.save_buckets(self.first_names, self.surnames)

    def reset_buckets(self) -> None:
        self.set_buckets(list(model.DEFAULT_FIRST_NAMES), list(model.DEFAULT_SURNAMES))

    # ── surfaces (native packet name-rewrite gates) ──────────────────────────────────────
    def list_surfaces(self) -> "list[str]":
        no = _pyno()
        if no is None:
            return []
        try:
            return list(no.list_surfaces() or [])
        except Exception:
            return []

    def is_surface_enabled(self, surface: str) -> bool:
        no = _pyno()
        if no is None:
            return bool(self.state.get("surfaces", {}).get(surface, False))
        try:
            return bool(no.is_surface_enabled(surface))
        except Exception:
            return False

    def set_surface_enabled(self, surface: str, on: bool) -> None:
        surfaces = self.state.setdefault("surfaces", {})
        surfaces[surface] = bool(on)
        store.save_surfaces(surfaces)
        no = _pyno()
        if no is not None:
            try:
                no.set_surface_enabled(surface, bool(on))
            except Exception:
                pass

    # ── live status (read straight from native) ──────────────────────────────────────────
    def native_status(self) -> dict:
        no = _pyno()
        if no is None:
            return {"available": False}
        out: dict = {"available": True}
        for key, fn in (("enabled", "is_enabled"), ("map_ready", "is_map_ready"),
                        ("alias_count", "alias_count"), ("observed_count", "observed_count")):
            try:
                out[key] = getattr(no, fn)()
            except Exception:
                out[key] = None
        return out

    # ── character enumeration (obtain names to alias) ────────────────────────────────────
    def refresh_known_characters(self) -> "list[str]":
        """Rebuild the known-character list: current account's live list + the accounts DB (all)."""
        names: "set[str]" = set()
        # Current account, live at character-select (same source the Switch Character widget uses).
        try:
            from Py4GWCoreLib import Map

            for c in (Map.Pregame.GetAvailableCharacterList() or []):
                name = getattr(c, "player_name", "")
                if name:
                    names.add(str(name))
        except Exception:
            pass
        # Every account on the machine, from the persistent accounts database (multi-account).
        try:
            from Py4GWCoreLib.database_src.Account import Account

            db = Account()
            for account in (db.GetAllAccounts() or []):
                account_id = account.get("ID")
                if account_id is None:
                    continue
                for character in (db.GetCharactersByAccountKey(int(account_id)) or []):
                    name = character.get("Name", "")
                    if name:
                        names.add(str(name))
        except Exception:
            pass
        self._known_chars = sorted(names)
        return self._known_chars


# ── process-wide singleton ───────────────────────────────────────────────────────────────
_controller: Optional[NameObfuscationController] = None


def get_controller() -> NameObfuscationController:
    """Return the process-wide controller, creating (and loading) it on first use."""
    global _controller
    if _controller is None:
        _controller = NameObfuscationController()
    return _controller
