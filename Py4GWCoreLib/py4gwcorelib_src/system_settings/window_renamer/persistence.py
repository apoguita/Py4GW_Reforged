"""Persistence for Window Renamer.

Window title behavior belongs to the local account profile.  The alias directory is
the exception: it is one global email-keyed JSON document so every client can edit
and consume the same account aliases.
"""

from .model import DISPLAY_MODES
from .model import WindowRenamerConfig


_DOC = "Widgets/System/Window Renamer.ini"
_ALIASES_DOC = "Widgets/System/Window Renamer.json"


def _settings():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_DOC, "account")
    except Exception:
        return None


def is_ready() -> bool:
    settings = _settings()
    if settings is None:
        return False
    try:
        return settings.is_ready()
    except Exception:
        return False


def load() -> WindowRenamerConfig:
    settings = _settings()
    if settings is None:
        return WindowRenamerConfig()

    display_mode = settings.get_str("window_renamer", "display_mode", "character")
    if display_mode not in DISPLAY_MODES:
        display_mode = "character"
    return WindowRenamerConfig(
        enabled=settings.get_bool("window_renamer", "enabled", False),
        display_mode=display_mode,
        fallback_to_character=settings.get_bool("window_renamer", "fallback_to_character", True),
        append_game_name=settings.get_bool("window_renamer", "append_game_name", False),
        prefix=settings.get_str("window_renamer", "prefix", ""),
        suffix=settings.get_str("window_renamer", "suffix", ""),
    )


def save(config: WindowRenamerConfig) -> None:
    settings = _settings()
    if settings is None:
        return
    settings.set("window_renamer", "enabled", config.enabled)
    settings.set("window_renamer", "display_mode", config.display_mode)
    settings.set("window_renamer", "fallback_to_character", config.fallback_to_character)
    settings.set("window_renamer", "append_game_name", config.append_game_name)
    settings.set("window_renamer", "prefix", config.prefix)
    settings.set("window_renamer", "suffix", config.suffix)


def _aliases_json():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory

        return JsonFactory(_ALIASES_DOC, "global")
    except Exception:
        return None


def load_aliases() -> dict[str, str]:
    document = _aliases_json()
    if document is None:
        return {}

    try:
        raw_aliases = document.get_json("aliases", {})
    except Exception:
        return {}
    if not isinstance(raw_aliases, dict):
        return {}

    return {
        str(email).strip(): str(alias).strip()
        for email, alias in raw_aliases.items()
        if str(email).strip() and str(alias).strip()
    }


def save_aliases(aliases: dict[str, str]) -> None:
    document = _aliases_json()
    if document is None:
        return
    document.set_json(
        "aliases",
        {
            str(email).strip(): str(alias).strip()
            for email, alias in aliases.items()
            if str(email).strip() and str(alias).strip()
        },
    )


def alias_for_email(email: str) -> str:
    normalized_email = str(email).strip()
    if not normalized_email:
        return ""
    return load_aliases().get(normalized_email, "")


def set_alias_for_email(email: str, alias: str) -> None:
    normalized_email = str(email).strip()
    if not normalized_email:
        return

    aliases = load_aliases()
    normalized_alias = str(alias).strip()
    if normalized_alias:
        aliases[normalized_email] = normalized_alias
    else:
        aliases.pop(normalized_email, None)
    save_aliases(aliases)
