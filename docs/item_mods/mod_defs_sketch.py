"""
PROPOSAL SKETCH -- the shape of the mod-definition table (NOT the final system).
================================================================================

This is 4 real mods written in the agreed design, so you can read one end to end and
we lock the shape before scaling to all 62. Nothing here is wired into Py4GWCoreLib yet.

The design, in one screen:
  - CATALOGS are the existing enums (Attribute, DamageType, ...) -- the lookup tables.
  - A `ModDef` per identifier is PURE FACTS: which arg is a value, which arg is a catalog
    index, plus one English `text` template. No per-mod code (except a rare escape hatch).
  - ONE shared reader (`resolve`) turns any raw word into structured data (value + subtype).
  - ONE shared renderer (`render_text`) turns that into English, reusing the Fields so the
    template never repeats catalog knowledge.
  - Filters run on the structured data. Display in production still uses the game's
    encoded strings; `render_text` exists mainly to validate against them (the oracle check).
"""

import re
from dataclasses import dataclass
from enum import Enum
from enum import IntEnum
from typing import Callable
from typing import Optional
from typing import Type

# Catalogs already exist as game-native enums; in the real module this is the only import.
from Py4GWCoreLib.enums import Attribute
from Py4GWCoreLib.enums import DamageType


# ── how to read ONE arg ────────────────────────────────────────────────────────
class Role(Enum):
    VALUE = "value"          # the raw number (armor 8, req level 9, chance 20)
    CATALOG = "catalog"      # an index into a catalog enum (Attribute[21] -> Tactics)
    RANGE_MIN = "range_min"  # low end of a min-max pair (damage 11-21)
    RANGE_MAX = "range_max"  # high end
    UNUSED = "unused"        # this arg carries nothing


@dataclass(frozen=True)
class Field:
    role: Role
    catalog: Optional[Type[IntEnum]] = None   # the foreign-key enum, ONLY when role == CATALOG


_UNUSED = Field(Role.UNUSED)


# ── one mod's definition = pure facts + an English template ─────────────────────
@dataclass(frozen=True)
class ModDef:
    name: str                              # short pick-list label
    arg1: Field
    arg2: Field = _UNUSED
    text: str = ""                         # English template; {arg1}/{arg2} resolved via the Fields
    render: Optional[Callable] = None      # escape hatch: only for the ~3% no template can express


# ── THE TABLE (4 examples; the real one has ~62 rows in exactly this form) ───────
MOD_DEFS = {
    # id       name               arg1                            arg2               text template
    0x2798: ModDef("Requirement",      Field(Role.CATALOG, Attribute),  Field(Role.VALUE),     "Requires {arg2} {arg1}"),
    0x2118: ModDef("Armor vs. Damage", Field(Role.CATALOG, DamageType), Field(Role.VALUE),     "Armor +{arg2} (vs. {arg1} damage)"),
    0xA7A8: ModDef("Damage",           Field(Role.RANGE_MAX),           Field(Role.RANGE_MIN), "{arg2}-{arg1}"),
    0xA7B8: ModDef("Shield Armor",     Field(Role.VALUE),               _UNUSED,               "Armor: {arg1}"),
    0x24B8: ModDef("Damage Type",      Field(Role.CATALOG, DamageType), _UNUSED,               "{arg1} Dmg"),
    # escape-hatch example (how the rare 3% would look -- a lambda instead of a template):
    # 0x2532: ModDef("Weird One", _UNUSED, _UNUSED, render=lambda a1, a2: f"custom {a1}/{a2}"),
}


# ── the runtime atom + ONE shared reader (handles every mod) ────────────────────
@dataclass
class ResolvedMod:
    id: int
    definition: ModDef
    arg1: int
    arg2: int
    value: object                 # an int, or (min, max) for ranges, or None
    subtype: Optional[IntEnum]    # a catalog enum member (Attribute.Tactics), or None


def _read_catalog(fld: Field, arg: int) -> Optional[IntEnum]:
    if fld.catalog is None:
        return None
    try:
        return fld.catalog(arg)
    except ValueError:
        return None


def resolve(word: int) -> Optional[ResolvedMod]:
    ident = word >> 16
    d = MOD_DEFS.get(ident)
    if d is None:
        return None                      # unknown/structural word (e.g. 0xC000) -> skipped
    a1, a2 = (word >> 8) & 0xFF, word & 0xFF
    value = subtype = None
    lo = hi = None
    for fld, raw in ((d.arg1, a1), (d.arg2, a2)):
        if fld.role == Role.CATALOG:
            subtype = _read_catalog(fld, raw)
        elif fld.role == Role.VALUE:
            value = raw
        elif fld.role == Role.RANGE_MIN:
            lo = raw
        elif fld.role == Role.RANGE_MAX:
            hi = raw
    if lo is not None or hi is not None:
        value = (lo, hi)
    return ResolvedMod(ident, d, a1, a2, value, subtype)


# ── one shared renderer: {arg1}/{arg2} resolved through the SAME Fields ──────────
def render_text(r: ResolvedMod) -> str:
    d = r.definition
    if d.render:                          # the escape hatch, used only where a template can't
        return d.render(r.arg1, r.arg2)

    def sub(m):
        which = m.group(1)
        fld = d.arg1 if which == "arg1" else d.arg2
        raw = r.arg1 if which == "arg1" else r.arg2
        if fld.role == Role.CATALOG:
            member = _read_catalog(fld, raw)
            return member.name if member is not None else str(raw)
        return str(raw)

    return re.sub(r"\{(arg1|arg2)\}", sub, d.text)


# ── filtering runs on the STRUCTURE (this is the actual goal) ────────────────────
def has(mods, ident, subtype=None, value=None) -> bool:
    """mods = list[int]. value: None=any, int=exact, callable=predicate(value)->bool."""
    for word in mods:
        r = resolve(word)
        if r is None or r.id != ident:
            continue
        if subtype is not None and r.subtype != subtype:
            continue
        if value is not None:
            ok = value(r.value) if callable(value) else (r.value == value)
            if not ok:
                continue
        return True
    return False


# Example filters this enables (the "shield, req <= 9 Tactics" kind):
#   has(mods, 0x2798, Attribute.Tactics, lambda lvl: lvl <= 9)
#   has(mods, 0xA7B8, value=16)


# ── runnable demo: resolve + render + filter on two real items ──────────────────
def _word(ident: int, arg1: int, arg2: int) -> int:
    return (ident << 16) | (arg1 << 8) | arg2


def main() -> None:
    samples = [
        ("Embossed Aegis", [(0x2798, 21, 10), (0x2118, 1, 8), (0xA7B8, 16, 8)]),
        ("Jade Wand", [(0x2798, 1, 11), (0x24B8, 6, 0), (0xA7A8, 21, 11)]),
    ]
    for item_name, mods in samples:
        print("== %s ==" % item_name)
        for ident, a1, a2 in mods:
            r = resolve(_word(ident, a1, a2))
            if r is None:
                continue
            sub = r.subtype.name if r.subtype is not None else None
            print("  %-16s value=%-10s subtype=%-14s %r" % (r.definition.name, r.value, sub, render_text(r)))

    print("== filter demo ==")
    shield = [_word(0x2798, 21, 9), _word(0xA7B8, 16, 8)]   # req 9 Tactics shield, armor 16
    print("  req <= 9 Tactics   :", has(shield, 0x2798, Attribute.Tactics, lambda lvl: lvl <= 9))
    print("  shield armor == 16 :", has(shield, 0xA7B8, value=16))
    print("  req Swordsmanship  :", has(shield, 0x2798, Attribute.Swordsmanship))


if __name__ == "__main__":
    main()
