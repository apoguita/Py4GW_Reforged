"""Loot Filters persistence -- split by shape, and only the PERSISTED instance is ever written.

``Settings`` holds flat values, ``JsonFactory`` holds structured collections. Both are the mandated
persistence classes; nothing here opens a file directly.

* **account, `Settings`** -- the master switch, the rarity toggles, the active profile, and the
  quick-access surface choices. Flat booleans and strings.
* **account, `JsonFactory`** -- this account's id lists and Nicholas dates. Simple, but long.

**The live instance is never written.** There is no code path from it to a writer, which is what makes
the user's configuration intact by construction rather than by discipline.

Deliberately absent: the catalogs (package data, versioned with the code), the filters and profiles
(the Loot Filter Factory's, global), and every agent/item-id entry (meaningless after a map change).
"""

from datetime import date

from ..item_catalog.nicholas import NicholasSelection
from .model import LootConfig

_INI = "Widgets/System/LootFilters.ini"
_SELECTIONS = "Widgets/System/LootFiltersSelections.json"

_QA_SEPARATOR = "|"
#: What the quick access shows on a fresh install.
DEFAULT_QUICK_ACCESS: tuple[str, ...] = ("Rarities", "Materials", "Dyes", "Nicholas")


def _settings():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_INI, "account")
    except Exception:
        return None


def _json():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory

        return JsonFactory(_SELECTIONS, "account")
    except Exception:
        return None


def load() -> LootConfig:
    """The persisted configuration. Live is seeded from a copy of this."""
    config = LootConfig()

    settings = _settings()
    if settings is not None:
        config.enabled = settings.get_bool("general", "enabled", True)
        config.respect_loot_lock = settings.get_bool("general", "respect_loot_lock", True)
        config.profile = settings.get_str("general", "profile", "")
        for key in ("white", "blue", "purple", "gold", "green", "gold_coins"):
            config.set_rarity(key, settings.get_bool("rarity", key, False))

    doc = _json()
    if doc is not None:
        config.enabled_model_ids = {int(v) for v in doc.get_json("enabled_model_ids", []) or []}
        config.enabled_dye_colors = {int(v) for v in doc.get_json("enabled_dye_colors", []) or []}
        config.salvage_target_ids = {int(v) for v in doc.get_json("salvage_target_ids", []) or []}
        config.added_model_ids = {int(v) for v in doc.get_json("added_model_ids", []) or []}
        config.blacklist_model_ids = {int(v) for v in doc.get_json("blacklist_model_ids", []) or []}
        config.blacklist_item_types = {int(v) for v in doc.get_json("blacklist_item_types", []) or []}
        # Nicholas is OPT IN. No stored value means none selected -- it is a thing the user turns
        # on, not a thing they have to discover and turn off.
        selections: list[NicholasSelection] = []
        for entry in doc.get_json("nicholas", []) or []:
            if entry in (None, ""):
                selections.append(NicholasSelection(None))   # the rolling "current week"
                continue
            try:
                selections.append(NicholasSelection(date.fromisoformat(str(entry))))
            except ValueError:
                continue
        config.nicholas = tuple(selections)

    return config


def save(config: LootConfig) -> None:
    """Persist. Only ever called with the PERSISTED instance -- never with live."""
    settings = _settings()
    if settings is not None:
        settings.set("general", "enabled", bool(config.enabled))
        settings.set("general", "respect_loot_lock", bool(config.respect_loot_lock))
        settings.set("general", "profile", str(config.profile))
        for key in ("white", "blue", "purple", "gold", "green", "gold_coins"):
            settings.set("rarity", key, bool(config.rarity_enabled(key)))

    doc = _json()
    if doc is not None:
        doc.set_json("enabled_model_ids", sorted(config.enabled_model_ids))
        doc.set_json("enabled_dye_colors", sorted(config.enabled_dye_colors))
        doc.set_json("salvage_target_ids", sorted(config.salvage_target_ids))
        doc.set_json("added_model_ids", sorted(config.added_model_ids))
        doc.set_json("blacklist_model_ids", sorted(config.blacklist_model_ids))
        doc.set_json("blacklist_item_types", sorted(config.blacklist_item_types))
        doc.set_json("nicholas", ["" if s.week is None else s.week.isoformat() for s in config.nicholas])


# ---------------------------------------------------------------- quick access (flat, account)


def load_quick_access() -> tuple[list[str], str, bool]:
    """``(surfaces, layout, window_open)``.

    Whether the window is open is a setting like any other: a user who wants it up should find it up
    next session rather than re-opening it from settings every time.
    """
    settings = _settings()
    if settings is None:
        return list(DEFAULT_QUICK_ACCESS), "checkbox_list", False
    raw = settings.get_str("quick access", "surfaces", "")
    surfaces = [part for part in raw.split(_QA_SEPARATOR) if part] or list(DEFAULT_QUICK_ACCESS)
    return (surfaces,
            settings.get_str("quick access", "layout", "checkbox_list"),
            settings.get_bool("quick access", "window_open", False))


def save_quick_access(surfaces, layout: str, window_open: bool) -> None:
    settings = _settings()
    if settings is not None:
        settings.set("quick access", "surfaces", _QA_SEPARATOR.join(str(s) for s in surfaces))
        settings.set("quick access", "layout", str(layout))
        settings.set("quick access", "window_open", bool(window_open))


def load_layout_for(surface: str, default: str) -> str:
    """The rendering chosen for one surface. The choice is PER SURFACE."""
    settings = _settings()
    if settings is None:
        return default
    return settings.get_str("layouts", surface, default)


def save_layout_for(surface: str, layout: str) -> None:
    settings = _settings()
    if settings is not None:
        settings.set("layouts", surface, str(layout))
