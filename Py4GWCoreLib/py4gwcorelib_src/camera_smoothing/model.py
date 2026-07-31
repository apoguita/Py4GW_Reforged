"""Pure configuration data for the camera-smoothing feature."""

from dataclasses import dataclass


@dataclass
class CameraSmoothingConfig:
    """Persisted camera options."""

    disable_smoothing: bool = False


def default_config() -> CameraSmoothingConfig:
    """Return a fresh default configuration."""

    return CameraSmoothingConfig()
