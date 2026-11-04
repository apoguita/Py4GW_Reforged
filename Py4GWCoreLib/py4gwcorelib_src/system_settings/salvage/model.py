"""Persistent Salvage policy values.

The policy is deliberately small. Item classification belongs to the private Salvage filter set;
these values only choose which operation is permitted and which rarities are candidates.
"""

from dataclasses import dataclass, field


@dataclass
class SalvageSettings:
    enabled: bool = False
    salvage_whites: bool = False
    salvage_blues: bool = False
    salvage_purples: bool = False
    salvage_golds: bool = False
    salvage_common_materials: bool = True
    salvage_rare_materials: bool = False
    salvage_matching_upgrades: bool = True
    auto_confirm_materials_warning: bool = False
    prefer_infinite_salvage_kit: bool = False
    debug_enabled: bool = False
    filter_set_id: str = ""

    def rarity_enabled(self, rarity: str) -> bool:
        return {
            "White": self.salvage_whites,
            "Blue": self.salvage_blues,
            "Purple": self.salvage_purples,
            "Gold": self.salvage_golds,
        }.get(str(rarity), False)

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "salvage_whites": self.salvage_whites,
            "salvage_blues": self.salvage_blues,
            "salvage_purples": self.salvage_purples,
            "salvage_golds": self.salvage_golds,
            "salvage_common_materials": self.salvage_common_materials,
            "salvage_rare_materials": self.salvage_rare_materials,
            "salvage_matching_upgrades": self.salvage_matching_upgrades,
            "auto_confirm_materials_warning": self.auto_confirm_materials_warning,
            "prefer_infinite_salvage_kit": self.prefer_infinite_salvage_kit,
            "debug_enabled": self.debug_enabled,
            "filter_set_id": self.filter_set_id,
        }


@dataclass
class CuratedKeepList:
    """Feature-owned checkbox state for the guided Salvage Keep Lists."""

    upgrades: set[str] = field(default_factory=set)
    weapon_mods: set[tuple[str, str]] = field(default_factory=set)
    item_types: set[int] = field(default_factory=set)
    item_requirement_enabled: bool = False
    item_max_requirement: int = 9
    model_ids: set[int] = field(default_factory=set)

    def to_dict(self) -> dict[str, object]:
        return {
            "upgrades": sorted(self.upgrades),
            "weapon_mods": [list(value) for value in sorted(self.weapon_mods)],
            "item_types": sorted(self.item_types),
            "item_requirement_enabled": self.item_requirement_enabled,
            "item_max_requirement": self.item_max_requirement,
            "model_ids": sorted(self.model_ids),
        }

    @staticmethod
    def from_dict(raw: object) -> "CuratedKeepList":
        value = raw if isinstance(raw, dict) else {}

        def strings(key: str) -> set[str]:
            values = value.get(key, [])
            if not isinstance(values, (list, tuple, set)):
                return set()
            return {str(entry) for entry in values if str(entry)}

        def positive_ints(key: str) -> set[int]:
            result: set[int] = set()
            values = value.get(key, [])
            if not isinstance(values, (list, tuple, set)):
                return result
            for entry in values:
                try:
                    parsed = int(entry)
                except (TypeError, ValueError):
                    continue
                if parsed > 0:
                    result.add(parsed)
            return result

        def bounded_int(key: str, default: int) -> int:
            try:
                parsed = int(value.get(key, default))
            except (TypeError, ValueError):
                parsed = default
            return max(0, min(13, parsed))

        raw_weapon_mods = value.get("weapon_mods", [])
        weapon_mods: set[tuple[str, str]] = set()
        if isinstance(raw_weapon_mods, (list, tuple, set)):
            for entry in raw_weapon_mods:
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    weapon_mods.add((str(entry[0]), str(entry[1])))
        return CuratedKeepList(
            upgrades=strings("upgrades"),
            weapon_mods=weapon_mods,
            item_types=positive_ints("item_types"),
            item_requirement_enabled=bool(value.get("item_requirement_enabled", False)),
            item_max_requirement=bounded_int("item_max_requirement", 9),
            model_ids=positive_ints("model_ids"),
        )
