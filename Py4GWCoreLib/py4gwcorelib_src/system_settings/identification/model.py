"""Per-account settings for automatic identification."""

from dataclasses import dataclass


@dataclass
class IdentificationSettings:
    """Identification policy; filter definitions remain owned by the Factory."""

    enabled: bool = False
    id_whites: bool = False
    id_blues: bool = True
    id_purples: bool = True
    id_golds: bool = True
    prefer_infinite_id_kit: bool = False
    filter_set_id: str = ""

    def rarity_enabled(self, rarity: str) -> bool:
        return {
            "White": self.id_whites,
            "Blue": self.id_blues,
            "Purple": self.id_purples,
            "Gold": self.id_golds,
        }.get(str(rarity), False)

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "id_whites": self.id_whites,
            "id_blues": self.id_blues,
            "id_purples": self.id_purples,
            "id_golds": self.id_golds,
            "prefer_infinite_id_kit": self.prefer_infinite_id_kit,
            "filter_set_id": self.filter_set_id,
        }
