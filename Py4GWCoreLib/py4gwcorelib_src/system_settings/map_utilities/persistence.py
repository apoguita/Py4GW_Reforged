"""Settings-backed persistence for the migrated Map & Missions utilities."""

from .model import MapUtilitiesConfig
from .model import OverlayStyle


_LOCAL_DOCUMENT = "Widgets/System/Map Utilities.ini"
_VANQUISH_DOCUMENT = "Widgets/Config/Vanquish.ini"
_INSTANCE_DOCUMENT = "Widgets/Config/InstanceTimer.ini"


def _settings(name: str, scope: str):
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(name, scope)
    except Exception:
        return None


def local_is_ready() -> bool:
    settings = _settings(_LOCAL_DOCUMENT, "account")
    if settings is None:
        return False
    try:
        return settings.is_ready()
    except Exception:
        return False


def _read_style(settings, section: str, default: OverlayStyle) -> OverlayStyle:
    if settings is None:
        return OverlayStyle(default.x, default.y, default.font_size, default.color)
    return OverlayStyle(
        x=settings.get_int(section, "x", default.x),
        y=settings.get_int(section, "y", default.y),
        font_size=settings.get_int(section, "font_size", default.font_size),
        color=(
            settings.get_int(section, "color_r", default.color[0]),
            settings.get_int(section, "color_g", default.color[1]),
            settings.get_int(section, "color_b", default.color[2]),
            settings.get_int(section, "color_a", default.color[3]),
        ),
    )


def _save_style(settings, section: str, style: OverlayStyle) -> None:
    if settings is None:
        return
    settings.set(section, "x", style.x)
    settings.set(section, "y", style.y)
    settings.set(section, "font_size", style.font_size)
    settings.set(section, "color_r", style.color[0])
    settings.set(section, "color_g", style.color[1])
    settings.set(section, "color_b", style.color[2])
    settings.set(section, "color_a", style.color[3])


def load() -> MapUtilitiesConfig:
    config = MapUtilitiesConfig()
    local = _settings(_LOCAL_DOCUMENT, "account")
    vanquish = _settings(_VANQUISH_DOCUMENT, "global")
    instance = _settings(_INSTANCE_DOCUMENT, "global")

    if local is not None:
        config.vanquish_enabled = local.get_bool("Map Utilities", "vanquish_enabled", config.vanquish_enabled)
        config.instance_timer_enabled = local.get_bool(
            "Map Utilities", "instance_timer_enabled", config.instance_timer_enabled
        )
        config.disable_alcohol_effect = local.get_bool(
            "Map Utilities", "disable_alcohol_effect", config.disable_alcohol_effect
        )

    config.vanquish = _read_style(vanquish, "Vanquish Monitor", config.vanquish)
    config.instance_timer = _read_style(instance, "Instance Timer", config.instance_timer)

    legacy_true_timer = (
        instance.get_bool("Instance Timer", "true_instance_timer", config.true_instance_timer)
        if instance is not None
        else config.true_instance_timer
    )
    if local is not None:
        config.true_instance_timer = local.get_bool("Map Utilities", "true_instance_timer", legacy_true_timer)
    else:
        config.true_instance_timer = legacy_true_timer
    return config


def save(config: MapUtilitiesConfig) -> None:
    local = _settings(_LOCAL_DOCUMENT, "account")
    vanquish = _settings(_VANQUISH_DOCUMENT, "global")
    instance = _settings(_INSTANCE_DOCUMENT, "global")

    if local is not None:
        local.set("Map Utilities", "vanquish_enabled", config.vanquish_enabled)
        local.set("Map Utilities", "instance_timer_enabled", config.instance_timer_enabled)
        local.set("Map Utilities", "disable_alcohol_effect", config.disable_alcohol_effect)
        local.set("Map Utilities", "true_instance_timer", config.true_instance_timer)
    _save_style(vanquish, "Vanquish Monitor", config.vanquish)
    _save_style(instance, "Instance Timer", config.instance_timer)
