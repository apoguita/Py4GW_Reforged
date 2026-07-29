"""Filter rules and profiles -- pure data.

**Terminology.** A **filter** is the *composite resolver*: criteria composed together, yielding one
verdict per item. A single condition inside it is a **criterion**, never "a filter". A **profile** is
a named set of filters.

**A filter is criteria, plus the marking outcome it carries.** The criteria say *what matches*. For
Loot Filters that is the whole story -- the outcome is *wanted*, and there is nothing to configure. For
Recolor & Beacons the outcome is a **recolour and/or a beacon**, which has values, and those values sit
**on the filter**: *"each filter **is** a recolour or a beacon"*.

There is deliberately **no separate object binding an outcome onto a filter afterwards**. That binding
step was the reverted build's invention and is what produced the "two competing orderings" defect. One
filter, carrying its own outcome, has one order -- the profile's.

The ``mark_*`` fields are read and written **only** by Recolor & Beacons; Loot Filters ignores them
entirely. So one filter serves both features without either inheriting the other's behaviour.

**Nothing here decides.** No callables, no predicates: a filter is values, and the matcher owns all
evaluation. That is what stops a script handing the class its own ruling to run.

**Shape follows the Item Mods Playground** (`Widgets/Coding/Debug/Py4GW/Item Mods Playground.py`),
which is the existing, working example of filtering items by mods: upgrades are chosen by **slot and
name** (never modifier ids), the requirement is *at most*, and there is **one ALL/ANY mode for the
whole rule** rather than separate all-of and any-of lists.

**Numbers are match-or-better, never exact** -- item mods are defined that way, so filters follow the
data.
"""

from dataclasses import dataclass
from dataclasses import field
from dataclasses import replace

MATCH_ALL = "all"
MATCH_ANY = "any"


@dataclass(frozen=True)
class Rule:
    """One composite resolver: a named, toggleable set of criteria.

    Identity is :attr:`id` -- a short sequential number. :attr:`name` is a **label**, never a key, so
    titles may repeat and be renamed freely and duplicating a filter costs nothing.
    """

    id: str = ""
    name: str = "New filter"
    enabled: bool = True

    #: How this rule's criteria combine. ALL = every set criterion must hold; ANY = at least one.
    mode: str = MATCH_ALL

    # -- criteria. An unset criterion is NOT a constraint; a rule with none matches nothing. --
    item_types: tuple[int, ...] = ()          # any-of
    model_ids: tuple[int, ...] = ()           # any-of
    dye_colors: tuple[int, ...] = ()          # any-of; dyes are item-type + colour, never model id
    salvages_into: tuple[int, ...] = ()       # any-of material model ids

    #: Rarities, any-of. 0=White 1=Blue 2=Purple 3=Gold 4=Green.
    #:
    #: Rarity is readable on an unidentified drop -- it comes off the interaction flags
    #: (GREEN 0x10, GOLD 0x20000, PURPLE 0x400000), which is why the dump decodes exactly those.
    #:
    #: This is NOT the same thing as the rarity toggles in Loot Filters. Those are a global
    #: "take golds" switch on the hand-crafted side. This is a *criterion*, so it composes: it is
    #: what makes "gold weapons at requirement 9" or "beacon every green" expressible at all.
    rarities: tuple[int, ...] = ()

    #: Substrings of the item's name. Any-of, case-insensitive.
    #:
    #: **contains** is one of the two operators in the closed set, and it applies to **names only** --
    #: a substring test does not mean anything on a type, a model or a number. This is what lets the
    #: settled example be written: *item type AND name contains ... AND value ... AND requirement*.
    name_contains: tuple[str, ...] = ()

    #: Worth **at least** -- match-or-better, since higher is better for value.
    #: Not a mod: gold value is a field on the item, not an effect word.
    min_value: int | None = None

    # -- the MOD criteria. --
    #
    # Deliberately only three, because only three are *there*. A drop is unidentified, and the
    # dump of one (`docs/item_mods/catalogs/single_item_dump.txt`) shows exactly what that means:
    #
    #     Chaos Dmg: 11-21 (Requires 11 Illusion Magic)
    #       0x2798  arg1=1  arg2=11   Requirement 11 (IllusionMagic)
    #       0x24B8  arg1=6  arg2=0    Damage Type (Blunt)
    #       0xA7A8  arg1=21 arg2=11   Damage 11        <- a RANGE, arg2..arg1
    #
    # Those are the INHERENT mods (`mods_core.Slot.Inherent`). Prefixes, suffixes, runes,
    # insignias and inscriptions are NOT visible before identifying, so filtering on them could
    # never fire -- they were dead controls and are gone.

    #: Requirement **at most** -- match-or-better, and the direction is not ours to choose:
    #: `Requirement` is the one mod in the table declaring `better_low=True`.
    max_requirement: int | None = None
    #: Which attribute that requirement is in (the mod's subtype). None = any attribute.
    requirement_attribute: int | None = None

    #: Damage **at least** -- compared against the range's TOP end (`arg1`), since that is the
    #: number the game shows as the weapon's damage and higher is better.
    #: This is what replaces the old "require max damage" checkbox: a real ranged comparison
    #: instead of a boolean that collapsed the range and nullified match-or-better.
    min_damage: int | None = None

    #: Damage types, any-of -- Blunt, Slashing, Chaos, Fire ... (the mod's subtype enum).
    damage_types: tuple[int, ...] = ()

    # -- the marking outcome. Recolor & Beacons' territory; Loot Filters never reads these. --
    #: Recolour the item's label. Independent of :attr:`mark_beacon` -- a filter may do either,
    #: both, or neither.
    mark_recolor: bool = False
    #: The label colour, RGBA 0..1.
    mark_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
    #: **BLANK** -- a named feature, not a trick. A fully transparent colour removes the item from
    #: the on-screen labels entirely. Used to hide unwanted drops and loot assigned to someone else.
    #: Visual only: blanking a label never changes whether the item is wanted.
    mark_blank: bool = False
    #: Put a beacon over it.
    mark_beacon: bool = False
    #: Which beacon preset, by name. Empty = the base beacon.
    mark_preset: str = ""

    def marks(self) -> bool:
        """Whether this filter does anything at all for the marking feature."""
        return bool(self.mark_recolor or self.mark_blank or self.mark_beacon)

    def is_empty(self) -> bool:
        """A rule with no criteria at all. It matches nothing, rather than everything."""
        return not (
            self.item_types or self.model_ids or self.dye_colors or self.salvages_into
            or self.name_contains or self.rarities
            or self.max_requirement is not None or self.min_value is not None
            or self.min_damage is not None or self.damage_types
        )

    def renamed(self, name: str) -> "Rule":
        return replace(self, name=name)

    def with_enabled(self, enabled: bool) -> "Rule":
        return replace(self, enabled=bool(enabled))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "enabled": self.enabled, "mode": self.mode,
            "item_types": list(self.item_types), "model_ids": list(self.model_ids),
            "dye_colors": list(self.dye_colors), "salvages_into": list(self.salvages_into),
            "name_contains": list(self.name_contains), "rarities": list(self.rarities),
            "max_requirement": self.max_requirement,
            "requirement_attribute": self.requirement_attribute,
            "min_value": self.min_value, "min_damage": self.min_damage,
            "damage_types": list(self.damage_types),
            "mark_recolor": self.mark_recolor, "mark_color": list(self.mark_color),
            "mark_blank": self.mark_blank, "mark_beacon": self.mark_beacon,
            "mark_preset": self.mark_preset,
        }

    @staticmethod
    def from_dict(raw: dict) -> "Rule":
        def ints(key: str) -> tuple[int, ...]:
            return tuple(int(v) for v in raw.get(key, ()) or ())

        def strs(key: str) -> tuple[str, ...]:
            return tuple(str(v) for v in raw.get(key, ()) or ())

        mode = str(raw.get("mode", MATCH_ALL))
        max_req = raw.get("max_requirement")
        min_val = raw.get("min_value")
        stored_color = raw.get("mark_color") or (1.0, 1.0, 1.0, 1.0)
        try:
            channels = tuple(float(c) for c in stored_color)[:4]
        except (TypeError, ValueError):
            channels = (1.0, 1.0, 1.0, 1.0)
        if len(channels) != 4:
            channels = (1.0, 1.0, 1.0, 1.0)
        return Rule(
            id=str(raw.get("id", "")),
            name=str(raw.get("name", "New filter")),
            enabled=bool(raw.get("enabled", True)),
            mode=mode if mode in (MATCH_ALL, MATCH_ANY) else MATCH_ALL,
            item_types=ints("item_types"), model_ids=ints("model_ids"),
            dye_colors=ints("dye_colors"), salvages_into=ints("salvages_into"),
            name_contains=tuple(s for s in strs("name_contains") if s),
            rarities=ints("rarities"),
            max_requirement=None if max_req is None else int(max_req),
            min_value=None if min_val is None else int(min_val),
            requirement_attribute=(None if raw.get("requirement_attribute") is None
                                   else int(raw["requirement_attribute"])),
            min_damage=(None if raw.get("min_damage") is None else int(raw["min_damage"])),
            damage_types=ints("damage_types"),
            mark_recolor=bool(raw.get("mark_recolor", False)),
            mark_color=(channels[0], channels[1], channels[2], channels[3]),
            mark_blank=bool(raw.get("mark_blank", False)),
            mark_beacon=bool(raw.get("mark_beacon", False)),
            mark_preset=str(raw.get("mark_preset", "")),
        )


@dataclass(frozen=True)
class Profile:
    """A named set of filters -- "Caster", "Ranger", "Melee".

    Global, so a profile composed once is usable from every account. Holds **filters only**: toggles
    and hand lists are per-account settings, and putting them in a shared object would stop two
    accounts running one profile with different toggles.
    """

    name: str = ""
    filter_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"name": self.name, "filter_ids": list(self.filter_ids)}

    @staticmethod
    def from_dict(raw: dict) -> "Profile":
        return Profile(
            name=str(raw.get("name", "")),
            filter_ids=tuple(str(v) for v in raw.get("filter_ids", ()) or ()),
        )
