"""Settings-backed persistence for title-on-map-load."""

from .model import TitleOnMapLoadConfig


_DOCUMENT = "Widgets/System/Title On Map Load.ini"


def _settings():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_DOCUMENT, "account")
    except Exception:
        return None


def local_is_ready() -> bool:
    settings = _settings()
    if settings is None:
        return False
    try:
        return settings.is_ready()
    except Exception:
        return False


def load() -> TitleOnMapLoadConfig:
    config = TitleOnMapLoadConfig()
    settings = _settings()
    if settings is not None:
        config.enabled = settings.get_bool("Title On Map Load", "enabled", config.enabled)
    return config


def save(config: TitleOnMapLoadConfig) -> None:
    settings = _settings()
    if settings is not None:
        settings.set("Title On Map Load", "enabled", config.enabled)
