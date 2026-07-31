"""Account-scoped persistence for Skillbar+.

The retired widget stored these values in a global document.  New values live in the System area
and are account-scoped.  A one-time read of the old document preserves existing users' settings;
all subsequent writes use the new document.
"""

from . import model


_DOCUMENT = "Widgets/System/Skillbar Plus.ini"
_LEGACY_DOCUMENT = "Widgets/Config/Skillbar +.ini"


def _settings(document: str, scope: str = "account"):
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(document, scope)
    except Exception:
        return None


def _has_new_values(settings) -> bool:
    keys = (
        ("Skillbar", "skill_font_size"),
        ("Skillbar", "draw_background"),
        ("Effects", "font_size"),
        ("Auto Cast", "alt_right_click"),
    )
    return any(settings.has(section, key) for section, key in keys)


def _migrate_legacy(config: model.SkillbarPlusConfig, target) -> bool:
    legacy = _settings(_LEGACY_DOCUMENT, "global")
    if legacy is None:
        return False

    legacy_keys = (
        ("skills", "font"),
        ("skills", "draw_bg"),
        ("effects", "font"),
        ("auto", "enable_click"),
    )
    if not any(legacy.has(section, key) for section, key in legacy_keys):
        return False

    config.skill_font_size = legacy.get_int("skills", "font", config.skill_font_size)
    config.draw_background = legacy.get_bool("skills", "draw_bg", config.draw_background)
    config.background_color = legacy.get_int("skills", "color_default", config.background_color)
    config.near_expiry_color = legacy.get_int("skills", "color_near", config.near_expiry_color)
    config.near_expiry_threshold = legacy.get_int("skills", "threshold", config.near_expiry_threshold)
    config.draw_durations = legacy.get_bool("skills", "draw_duration", config.draw_durations)
    config.duration_font_size = legacy.get_int("skills", "duration_font", config.duration_font_size)
    config.duration_background = legacy.get_int("skills", "duration_bg", config.duration_background)
    config.duration_foreground = legacy.get_int("skills", "duration_bar", config.duration_foreground)
    config.duration_offset = legacy.get_int("skills", "duration_offset", config.duration_offset)
    config.effects_font_size = legacy.get_int("effects", "font", config.effects_font_size)
    config.effects_background = legacy.get_int("effects", "color", config.effects_background)
    config.auto_cast_alt_right_click = legacy.get_bool("auto", "enable_click", config.auto_cast_alt_right_click)
    save(config, target)
    return True


def load() -> model.SkillbarPlusConfig:
    """Load account settings, migrating the retired widget's global document when needed."""

    config = model.default_config()
    settings = _settings(_DOCUMENT)
    if settings is None:
        return config

    if not _has_new_values(settings):
        _migrate_legacy(config, settings)

    config.skill_font_size = settings.get_int("Skillbar", "skill_font_size", config.skill_font_size)
    config.draw_background = settings.get_bool("Skillbar", "draw_background", config.draw_background)
    config.background_color = settings.get_int("Skillbar", "background_color", config.background_color)
    config.near_expiry_color = settings.get_int("Skillbar", "near_expiry_color", config.near_expiry_color)
    config.near_expiry_threshold = settings.get_int("Skillbar", "near_expiry_threshold", config.near_expiry_threshold)
    config.draw_durations = settings.get_bool("Skillbar", "draw_durations", config.draw_durations)
    config.duration_font_size = settings.get_int("Skillbar", "duration_font_size", config.duration_font_size)
    config.duration_background = settings.get_int("Skillbar", "duration_background", config.duration_background)
    config.duration_foreground = settings.get_int("Skillbar", "duration_foreground", config.duration_foreground)
    config.duration_offset = settings.get_int("Skillbar", "duration_offset", config.duration_offset)
    config.effects_font_size = settings.get_int("Effects", "font_size", config.effects_font_size)
    config.effects_background = settings.get_int("Effects", "background", config.effects_background)
    config.auto_cast_alt_right_click = settings.get_bool(
        "Auto Cast", "alt_right_click", config.auto_cast_alt_right_click
    )
    return config


def save(config: model.SkillbarPlusConfig, settings=None) -> None:
    """Persist the complete configuration through the sanctioned Settings wrapper."""

    target = settings or _settings(_DOCUMENT)
    if target is None:
        return

    target.set("Skillbar", "skill_font_size", config.skill_font_size)
    target.set("Skillbar", "draw_background", config.draw_background)
    target.set("Skillbar", "background_color", config.background_color)
    target.set("Skillbar", "near_expiry_color", config.near_expiry_color)
    target.set("Skillbar", "near_expiry_threshold", config.near_expiry_threshold)
    target.set("Skillbar", "draw_durations", config.draw_durations)
    target.set("Skillbar", "duration_font_size", config.duration_font_size)
    target.set("Skillbar", "duration_background", config.duration_background)
    target.set("Skillbar", "duration_foreground", config.duration_foreground)
    target.set("Skillbar", "duration_offset", config.duration_offset)
    target.set("Effects", "font_size", config.effects_font_size)
    target.set("Effects", "background", config.effects_background)
    target.set("Auto Cast", "alt_right_click", config.auto_cast_alt_right_click)
