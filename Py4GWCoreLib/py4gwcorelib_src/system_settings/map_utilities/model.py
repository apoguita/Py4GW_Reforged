"""Configuration data for the migrated Map & Missions utilities."""

from dataclasses import dataclass
from dataclasses import field


RGBA = tuple[int, int, int, int]


@dataclass
class OverlayStyle:
    x: int = 100
    y: int = 100
    font_size: int = 20
    color: RGBA = (255, 255, 255, 255)


@dataclass
class MapUtilitiesConfig:
    """Account-local switches plus global overlay appearance settings."""

    vanquish_enabled: bool = True
    instance_timer_enabled: bool = True
    disable_alcohol_effect: bool = False
    true_instance_timer: bool = False
    vanquish: OverlayStyle = field(default_factory=lambda: OverlayStyle(y=200))
    instance_timer: OverlayStyle = field(default_factory=OverlayStyle)
