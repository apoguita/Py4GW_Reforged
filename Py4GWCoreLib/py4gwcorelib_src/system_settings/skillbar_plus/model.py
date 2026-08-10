"""Pure configuration data for the Skillbar+ runtime."""

from dataclasses import dataclass


@dataclass
class SkillbarPlusConfig:
    """Persisted Skillbar+ options using the shared ABGR integer colour format."""

    skill_font_size: int = 40
    draw_background: bool = True
    background_color: int = 0x3200FF00
    near_expiry_color: int = 0x960000FF
    near_expiry_threshold: int = 5
    draw_durations: bool = False
    duration_font_size: int = 16
    duration_background: int = 0xFF000000
    duration_foreground: int = 0xFF646464
    duration_offset: int = 0
    effects_font_size: int = 20
    effects_background: int = 0x96000000
    auto_cast_alt_right_click: bool = False


def default_config() -> SkillbarPlusConfig:
    """Return a fresh default configuration."""

    return SkillbarPlusConfig()
