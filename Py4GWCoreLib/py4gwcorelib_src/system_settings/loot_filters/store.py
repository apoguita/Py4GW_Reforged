"""Loot persistence split by lifetime: global policy, local selection, and session-only live state.

The global Loot Policy is shared by every account.  An account persists only which global Factory
profile it currently uses.  ``LootFilters.live`` remains in memory and is never written here.
"""

from datetime import date

from .nicholas import NicholasSelection
from .model import LootConfig


_POLICY_INI = "Widgets/System/LootFilters.ini"
_POLICY_SELECTIONS = "Widgets/System/LootFiltersSelections.json"
_PROFILE_SELECTION_INI = "Widgets/System/LootFilterProfileSelection.ini"

_QA_SEPARATOR = "|"
DEFAULT_QUICK_ACCESS: tuple[str, ...] = ("Rarities", "Materials", "Dyes", "Nicholas")


def _settings(scope: str):
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_POLICY_INI, scope)
    except Exception:
        return None


def _selection_settings():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_PROFILE_SELECTION_INI, "account")
    except Exception:
        return None


def _json(scope: str):
    try:
        from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory

        return JsonFactory(_POLICY_SELECTIONS, scope)
    except Exception:
        return None


def _load_policy(settings, doc) -> LootConfig:
    config = LootConfig()
    if settings is not None:
        config.enabled = settings.get_bool("general", "enabled", True)
        config.respect_loot_lock = settings.get_bool("general", "respect_loot_lock", True)
        for key in ("white", "blue", "purple", "gold", "green", "gold_coins"):
            config.set_rarity(key, settings.get_bool("rarity", key, False))
    if doc is not None:
        config.enabled_model_ids = {int(v) for v in doc.get_json("enabled_model_ids", []) or []}
        config.enabled_dye_colors = {int(v) for v in doc.get_json("enabled_dye_colors", []) or []}
        config.salvage_target_ids = {int(v) for v in doc.get_json("salvage_target_ids", []) or []}
        config.added_model_ids = {int(v) for v in doc.get_json("added_model_ids", []) or []}
        config.blacklist_model_ids = {int(v) for v in doc.get_json("blacklist_model_ids", []) or []}
        config.blacklist_item_types = {int(v) for v in doc.get_json("blacklist_item_types", []) or []}
        selections: list[NicholasSelection] = []
        for entry in doc.get_json("nicholas", []) or []:
            if entry in (None, ""):
                selections.append(NicholasSelection(None))
                continue
            try:
                selections.append(NicholasSelection(date.fromisoformat(str(entry))))
            except ValueError:
                continue
        config.nicholas = tuple(selections)
    return config


def _save_policy(config: LootConfig, settings, doc) -> None:
    if settings is not None:
        settings.set("general", "enabled", bool(config.enabled))
        settings.set("general", "respect_loot_lock", bool(config.respect_loot_lock))
        for key in ("white", "blue", "purple", "gold", "green", "gold_coins"):
            settings.set("rarity", key, bool(config.rarity_enabled(key)))
    if doc is not None:
        doc.set_json("enabled_model_ids", sorted(config.enabled_model_ids))
        doc.set_json("enabled_dye_colors", sorted(config.enabled_dye_colors))
        doc.set_json("salvage_target_ids", sorted(config.salvage_target_ids))
        doc.set_json("added_model_ids", sorted(config.added_model_ids))
        doc.set_json("blacklist_model_ids", sorted(config.blacklist_model_ids))
        doc.set_json("blacklist_item_types", sorted(config.blacklist_item_types))
        doc.set_json("nicholas", ["" if s.week is None else s.week.isoformat() for s in config.nicholas])


def _migrate_account_policy(policy_settings, policy_doc) -> None:
    """The first account to use the new global policy imports the prior account policy once."""
    if policy_settings is None or policy_settings.get_bool("migration", "from_account", False):
        return
    _save_policy(_load_policy(_settings("account"), _json("account")), policy_settings, policy_doc)
    policy_settings.set("migration", "from_account", True)


def _load_account_profile() -> str:
    selection = _selection_settings()
    if selection is None:
        return ""
    if not selection.get_bool("migration", "from_loot_filters", False):
        legacy = _settings("account")
        selection.set("general", "profile", legacy.get_str("general", "profile", "") if legacy else "")
        selection.set("migration", "from_loot_filters", True)
    return selection.get_str("general", "profile", "")


def _save_account_profile(profile: str) -> None:
    selection = _selection_settings()
    if selection is not None:
        selection.set("general", "profile", str(profile))
        selection.set("migration", "from_loot_filters", True)


def load() -> LootConfig:
    """Load global policy plus this account's selected global Loot Filter Profile."""
    policy_settings, policy_doc = _settings("global"), _json("global")
    _migrate_account_policy(policy_settings, policy_doc)
    config = _load_policy(policy_settings, policy_doc)
    config.profile = _load_account_profile()
    return config


def save(config: LootConfig) -> None:
    """Persist global policy and only the profile selection locally; never persist live state."""
    _save_policy(config, _settings("global"), _json("global"))
    _save_account_profile(config.profile)


# ---------------------------------------------------------------- quick access and layouts (global presentation policy)


def load_quick_access() -> tuple[list[str], str, bool]:
    settings = _settings("global")
    if settings is None:
        return list(DEFAULT_QUICK_ACCESS), "checkbox_list", False
    raw = settings.get_str("quick access", "surfaces", "")
    surfaces = [part for part in raw.split(_QA_SEPARATOR) if part] or list(DEFAULT_QUICK_ACCESS)
    return (surfaces,
            settings.get_str("quick access", "layout", "checkbox_list"),
            settings.get_bool("quick access", "window_open", False))


def save_quick_access(surfaces, layout: str, window_open: bool) -> None:
    settings = _settings("global")
    if settings is not None:
        settings.set("quick access", "surfaces", _QA_SEPARATOR.join(str(surface) for surface in surfaces))
        settings.set("quick access", "layout", str(layout))
        settings.set("quick access", "window_open", bool(window_open))


def load_layout_for(surface: str, default: str) -> str:
    settings = _settings("global")
    return settings.get_str("layouts", surface, default) if settings is not None else default


def save_layout_for(surface: str, layout: str) -> None:
    settings = _settings("global")
    if settings is not None:
        settings.set("layouts", surface, str(layout))
