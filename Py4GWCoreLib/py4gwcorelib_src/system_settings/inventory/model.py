"""Plain System Settings data for Xunlai access and Colorize."""

from dataclasses import dataclass, field
from typing import Any


RARITIES: tuple[str, ...] = ("White", "Blue", "Green", "Purple", "Gold")
_FALLBACK_COLORS: dict[str, tuple[int, int, int, int]] = {
    "White": (255, 255, 255, 255),
    "Blue": (0, 0, 255, 255),
    "Green": (0, 255, 0, 255),
    "Purple": (128, 0, 128, 255),
    "Gold": (255, 215, 0, 255),
}


def _palette_colors() -> dict[str, tuple[int, int, int, int]]:
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Color import ColorPalette

        return {rarity: tuple(ColorPalette.GetColor("GW_%s" % rarity).to_tuple()) for rarity in RARITIES}
    except Exception:
        return dict(_FALLBACK_COLORS)


DEFAULT_COLORS: dict[str, tuple[int, int, int, int]] = _palette_colors()


def _color(value: Any, fallback: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    try:
        channels = tuple(max(0, min(255, int(channel))) for channel in value)[:4]
    except (TypeError, ValueError):
        return fallback
    return channels if len(channels) == 4 else fallback


@dataclass
class ColorizeSettings:
    enabled: bool = False
    imgui_frame: bool = True
    imgui_outline: bool = True
    native_frame: bool = False
    native_outline: bool = False
    context_menu_toggle: bool = True
    rarities: dict[str, bool] = field(default_factory=lambda: {
        "White": False, "Blue": True, "Green": True, "Purple": True, "Gold": True,
    })
    colors: dict[str, tuple[int, int, int, int]] = field(default_factory=lambda: dict(DEFAULT_COLORS))

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "imgui_frame": self.imgui_frame,
            "imgui_outline": self.imgui_outline,
            "native_frame": self.native_frame,
            "native_outline": self.native_outline,
            "context_menu_toggle": self.context_menu_toggle,
            "rarities": {name: bool(self.rarities.get(name, False)) for name in RARITIES},
            "colors": {name: list(_color(self.colors.get(name), DEFAULT_COLORS[name])) for name in RARITIES},
        }

    @staticmethod
    def from_dict(raw: Any) -> "ColorizeSettings":
        raw = raw if isinstance(raw, dict) else {}
        stored_rarities = raw.get("rarities", {})
        stored_colors = raw.get("colors", {})
        return ColorizeSettings(
            enabled=bool(raw.get("enabled", False)),
            imgui_frame=bool(raw.get("imgui_frame", True)),
            imgui_outline=bool(raw.get("imgui_outline", True)),
            native_frame=bool(raw.get("native_frame", False)),
            native_outline=bool(raw.get("native_outline", False)),
            context_menu_toggle=bool(raw.get("context_menu_toggle", True)),
            rarities={name: bool(stored_rarities.get(name, False)) for name in RARITIES}
            if isinstance(stored_rarities, dict) else {},
            colors={name: _color(stored_colors.get(name), DEFAULT_COLORS[name]) for name in RARITIES}
            if isinstance(stored_colors, dict) else dict(DEFAULT_COLORS),
        )


@dataclass
class InventoryFeatureSettings:
    colorize: ColorizeSettings = field(default_factory=ColorizeSettings)
    context_menu_xunlai: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"colorize": self.colorize.to_dict(), "context_menu_xunlai": self.context_menu_xunlai}

    @staticmethod
    def from_dict(raw: Any) -> "InventoryFeatureSettings":
        raw = raw if isinstance(raw, dict) else {}
        return InventoryFeatureSettings(
            colorize=ColorizeSettings.from_dict(raw.get("colorize")),
            context_menu_xunlai=bool(raw.get("context_menu_xunlai", True)),
        )
