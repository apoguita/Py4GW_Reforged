"""Account-scoped persistence for camera settings."""

from . import model


_DOCUMENT = "Widgets/System/Camera Smoothing.ini"


def _settings():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_DOCUMENT, "account")
    except Exception:
        return None


def load() -> model.CameraSmoothingConfig:
    """Load the camera settings, defaulting to disabled."""

    config = model.default_config()
    settings = _settings()
    if settings is not None:
        config.disable_smoothing = settings.get_bool("Camera", "disable_smoothing", config.disable_smoothing)
    return config


def save(config: model.CameraSmoothingConfig) -> None:
    """Persist camera settings through the sanctioned Settings wrapper."""

    settings = _settings()
    if settings is not None:
        settings.set("Camera", "disable_smoothing", config.disable_smoothing)
