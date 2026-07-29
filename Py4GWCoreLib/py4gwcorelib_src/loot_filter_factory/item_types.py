"""Item types a filter can match on, grouped.

**Every type that can drop is filterable. Anything that cannot drop gets no filter at all.**

**Umbrella members are never filterable entries.** `Weapon`, `MartialWeapon`, `SpellcastingWeapon`,
`OffhandOrShield`, `EquippableItem` and `Unknown` are *definitions* (`ITEM_TYPE_META_TYPES`), not
things a user picks -- offering them beside the concrete types would let one filter be written two
ways (`MartialWeapon` versus Axe+Sword+...), and **no group may duplicate another group's flags**.

**Weapons is one flat group of 11.** The enum contradicts itself here -- `ItemType.Weapon` is 9 while
`WEAPON_TYPES` is 11 -- and we take the broader reading, including Offhand and Shield. The
contradiction itself is *not* fixed as part of this work; see `docs/pending_fixes.md` PF-1.

The martial / spellcasting / offhand subdivision the enum describes is deliberately **not** surfaced:
the user sees the weapon list, not its internal taxonomy.
"""

#: group -> the concrete ItemType member names in it, in the settled grouping.
GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Weapons", ("Axe", "Bow", "Daggers", "Hammer", "Offhand", "Scythe", "Shield",
                 "Spear", "Staff", "Sword", "Wand")),
    ("Armor", ("Chestpiece", "Headpiece", "Leggings", "Boots", "Gloves")),
    ("Upgrades", ("Rune_Mod",)),
    ("Miniatures", ("Minipet",)),
    ("Consumables", ("Usable", "Kit", "Scroll")),
    ("Currency & tokens", ("Gold_Coin", "CC_Shards", "Materials_Zcoins")),
    ("Materials & salvage", ("Salvage", "Trophy")),
    ("Keys & quest", ("Key", "Quest_Item", "Storybook")),
    ("Cosmetic", ("Dye", "Costume", "Costume_Headpiece")),
    ("Containers", ("Bag", "Bundle")),
    ("Event", ("Present",)),
)

#: Definitions, not drops. Never offered.
EXCLUDED: frozenset[str] = frozenset({
    "Weapon", "MartialWeapon", "SpellcastingWeapon", "OffhandOrShield", "EquippableItem", "Unknown",
})

_CACHE: list[tuple[str, list[tuple[str, int]]]] | None = None


def _pretty(name: str) -> str:
    return name.replace("_", " ")


def grouped() -> list[tuple[str, list[tuple[str, int]]]]:
    """``[(group, [(display, value), ...]), ...]``. Empty offline, where the enum is unavailable."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        from Py4GWCoreLib.enums import ItemType
    except Exception:
        return []
    members = {m.name: int(m.value) for m in ItemType}
    out: list[tuple[str, list[tuple[str, int]]]] = []
    for group, names in GROUPS:
        entries = [(_pretty(n), members[n]) for n in names if n in members]
        if entries:
            out.append((group, entries))
    _CACHE = out
    return out


def display_name(value: int) -> str:
    for _group, entries in grouped():
        for display, item_type in entries:
            if item_type == value:
                return display
    return str(value)
