"""Data model for the account-local Window Renamer settings."""

from dataclasses import dataclass


DISPLAY_MODES: tuple[str, ...] = ("character", "obfuscated", "alias")
DISPLAY_MODE_LABELS: tuple[str, ...] = ("Character name", "Obfuscated name", "Configured alias")


@dataclass
class WindowRenamerConfig:
    # Account-scoped settings must fail closed while the account document is
    # still waiting for its email anchor.
    enabled: bool = False
    display_mode: str = "character"
    fallback_to_character: bool = True
    append_game_name: bool = False
    prefix: str = ""
    suffix: str = ""
