"""
mods_core -- the new item-modifier engine (replaces the item_mods_src parser).
==============================================================================

This is the whole "match id -> return value" job, as a small data table + one reader, in
place of the 596 convoluted classes in `item_mods_src`. Nothing here parses JSON; the mod
value/subtype rules are the *facts* mined from the old `upgrade_parser` factory, encoded as
plain data. The clean data enums (`ModifierIdentifier`, `ItemUpgrade`, `ItemUpgradeId`) are
kept as-is and imported.

A raw modifier word is `identifier(16) | arg1(8) | arg2(8)`. Per the game's own convention the
engine strips the identifier to 10 bits `(id >> 4) & 0x3FF` to key `ModifierIdentifier` (the same
mapping the old decoder used, so behaviour is identical). The Upgrade word (`ModifierIdentifier.
Upgrade`) additionally carries an `upgrade_id` in the low 16 bits of its raw bits -- the "barcode"
that names a prefix/suffix/inscription/rune/insignia.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

import PyItem

from Py4GWCoreLib.enums_src.GameData_enums import Ailment
from Py4GWCoreLib.enums_src.GameData_enums import Attribute
from Py4GWCoreLib.enums_src.GameData_enums import DamageType
from Py4GWCoreLib.enums_src.GameData_enums import Reduced_Ailment
from Py4GWCoreLib.enums_src.Item_enums import BowType
from Py4GWCoreLib.enums_src.Item_enums import ItemType
from Py4GWCoreLib import mods_upgrades
from Py4GWCoreLib.mods_types import ItemBaneSpecies
from Py4GWCoreLib.mods_types import ItemUpgrade
from Py4GWCoreLib.mods_types import ItemUpgradeId
from Py4GWCoreLib.mods_types import ModifierIdentifier


class Slot(IntEnum):
    """Where an applied upgrade sits (salvage extracts by slot)."""
    Inherent = 0
    Prefix = 1
    Suffix = 2
    Inscription = 3
    Rune = 4
    Insignia = 5


# ── how to read one effect word ────────────────────────────────────────────────
# Value source (which arg is the magnitude) and, if an arg is an enum index, the catalog.
V_NONE, V_A1, V_A2, V_RANGE = 0, 1, 2, 3   # value = none | arg1 | arg2 | range(arg2,arg1)


@dataclass(frozen=True)
class _Def:
    name: str
    value: int = V_NONE              # V_A1 / V_A2 / V_RANGE / V_NONE
    subtype_arg: int = 0             # 1 -> arg1 is an enum index, 2 -> arg2, 0 -> none
    subtype_cat: Optional[type] = None
    better_low: bool = False         # requirement etc. -> lower is better
    negate: bool = False             # value stored as a negative (degens)
    offset: int = 0                  # add to the raw value (e.g. DamageCustomized = arg1 - 100)


# The effect table -- the FACTS mined from item_mods_src/upgrade_parser.get_property_factory().
# Keyed by the (stripped) ModifierIdentifier. Replaces properties.py + the 90-lambda factory.
_EFFECT: dict[int, _Def] = {
    int(ModifierIdentifier.Empty): _Def("Empty"),
    int(ModifierIdentifier.Armor1): _Def("Armor", V_A1),
    int(ModifierIdentifier.Armor2): _Def("Armor", V_A1),
    int(ModifierIdentifier.ArmorMinusAttacking): _Def("Armor (while attacking)", V_A2),
    int(ModifierIdentifier.ArmorPenetration): _Def("Armor Penetration", V_A2),
    int(ModifierIdentifier.ArmorPlus): _Def("Armor", V_A2),
    int(ModifierIdentifier.ArmorPlusAttacking): _Def("Armor (while attacking)", V_A2),
    int(ModifierIdentifier.ArmorPlusCasting): _Def("Armor (while casting)", V_A2),
    int(ModifierIdentifier.ArmorPlusEnchanted): _Def("Armor (while enchanted)", V_A2),
    int(ModifierIdentifier.ArmorPlusHexed): _Def("Armor (while hexed)", V_A2),
    int(ModifierIdentifier.ArmorPlusAbove): _Def("Armor (health above)", V_A2),
    int(ModifierIdentifier.ArmorPlusVsDamage): _Def("Armor vs. Damage", V_A2, 1, DamageType),
    int(ModifierIdentifier.ArmorPlusVsElemental): _Def("Armor vs. Elemental", V_A2),
    int(ModifierIdentifier.ArmorPlusVsPhysical): _Def("Armor vs. Physical", V_A2),
    int(ModifierIdentifier.ArmorPlusVsPhysical2): _Def("Armor vs. Physical", V_A2),
    int(ModifierIdentifier.ArmorPlusVsSpecies): _Def("Armor vs. Species", V_A2, 1, ItemBaneSpecies),
    int(ModifierIdentifier.ArmorPlusWhileBelow): _Def("Armor (health below)", V_A2),
    int(ModifierIdentifier.AttributePlusOne): _Def("Attribute +1", V_A2, 1, Attribute),
    int(ModifierIdentifier.AttributePlusOneItem): _Def("Attribute +1", V_A1),
    int(ModifierIdentifier.AttributeRequirement): _Def("Requirement", V_A2, 1, Attribute, better_low=True),
    int(ModifierIdentifier.BaneSpecies): _Def("Bane Species", V_NONE, 1, ItemBaneSpecies),
    int(ModifierIdentifier.Damage): _Def("Damage", V_RANGE),
    int(ModifierIdentifier.Damage2): _Def("Damage", V_RANGE),
    int(ModifierIdentifier.DamageCustomized): _Def("Damage %", V_A1, offset=-100),
    int(ModifierIdentifier.DamagePlusEnchanted): _Def("Damage (while enchanted)", V_A2),
    int(ModifierIdentifier.DamagePlusHexed): _Def("Damage (while hexed)", V_A2),
    int(ModifierIdentifier.DamagePlusPercent): _Def("Damage %", V_A2),
    int(ModifierIdentifier.DamagePlusStance): _Def("Damage (in a stance)", V_A2),
    int(ModifierIdentifier.DamagePlusVsHexed): _Def("Damage (vs. hexed)", V_A2),
    int(ModifierIdentifier.DamagePlusVsSpecies): _Def("Damage vs. Species", V_A1),
    int(ModifierIdentifier.DamagePlusWhileBelow): _Def("Damage (health below)", V_A2),
    int(ModifierIdentifier.DamagePlusWhileAbove): _Def("Damage (health above)", V_A2),
    int(ModifierIdentifier.DamageTypeProperty): _Def("Damage Type", V_NONE, 1, DamageType),
    int(ModifierIdentifier.Energy): _Def("Energy", V_A1),
    int(ModifierIdentifier.Energy2): _Def("Energy", V_A1),
    int(ModifierIdentifier.EnergyRecovery): _Def("Energy Recovery", V_A1),
    int(ModifierIdentifier.EnergyRegeneration): _Def("Energy Regeneration", V_A2, negate=True),
    int(ModifierIdentifier.EnergyGainOnHit): _Def("Energy Gain on Hit", V_A2),
    int(ModifierIdentifier.EnergyMinus): _Def("Energy -", V_A2),
    int(ModifierIdentifier.EnergyPlus): _Def("Energy", V_A2),
    int(ModifierIdentifier.EnergyPlusEnchanted): _Def("Energy (while enchanted)", V_A2),
    int(ModifierIdentifier.EnergyPlusHexed): _Def("Energy (while hexed)", V_A2),
    int(ModifierIdentifier.EnergyPlusWhileBelow): _Def("Energy (health below)", V_A2),
    int(ModifierIdentifier.EnergyPlusWhileAbove): _Def("Energy (health above)", V_A2),
    int(ModifierIdentifier.Furious): _Def("Furious", V_A2),
    int(ModifierIdentifier.HalvesCastingTimeAttribute): _Def("Halves Casting (attribute)", V_A1, 2, Attribute),
    int(ModifierIdentifier.HalvesCastingTimeGeneral): _Def("Halves Casting", V_A1),
    int(ModifierIdentifier.HalvesCastingTimeItemAttribute): _Def("Halves Casting (item attribute)", V_A1),
    int(ModifierIdentifier.HalvesSkillRechargeAttribute): _Def("Halves Recharge (attribute)", V_A1, 2, Attribute),
    int(ModifierIdentifier.HalvesSkillRechargeGeneral): _Def("Halves Recharge", V_A1),
    int(ModifierIdentifier.HalvesSkillRechargeItemAttribute): _Def("Halves Recharge (item attribute)", V_A1),
    int(ModifierIdentifier.HeadpieceAttribute): _Def("Headpiece Attribute", V_A2, 1, Attribute),
    int(ModifierIdentifier.HeadpieceGenericAttribute): _Def("Headpiece Attribute"),
    int(ModifierIdentifier.HealthRegeneneration): _Def("Health Regeneration", V_A2, negate=True),
    int(ModifierIdentifier.HealthMinus): _Def("Health -", V_A2),
    int(ModifierIdentifier.HealthPlus): _Def("Health", V_A1),
    int(ModifierIdentifier.HealthPlus2): _Def("Health", V_A2),
    int(ModifierIdentifier.HealthPlusEnchanted): _Def("Health (while enchanted)", V_A1),
    int(ModifierIdentifier.HealthPlusHexed): _Def("Health (while hexed)", V_A1),
    int(ModifierIdentifier.HealthPlusStance): _Def("Health (in a stance)", V_A1),
    int(ModifierIdentifier.HealthStealOnHit): _Def("Life Stealing", V_A1),
    int(ModifierIdentifier.HighlySalvageable): _Def("Highly Salvageable"),
    int(ModifierIdentifier.IncreaseConditionDuration): _Def("Lengthens Condition", V_NONE, 2, Ailment),
    int(ModifierIdentifier.IncreaseEnchantmentDuration): _Def("Enchantment Duration", V_A2),
    int(ModifierIdentifier.IncreasedSaleValue): _Def("Increased Sale Value"),
    int(ModifierIdentifier.Infused): _Def("Infused"),
    int(ModifierIdentifier.OfTheProfession): _Def("Of the Profession", V_A2, 1, Attribute),
    int(ModifierIdentifier.ReceiveLessPhysDamageEnchanted): _Def("Reduce Phys Damage (enchanted)", V_A2),
    int(ModifierIdentifier.ReceiveLessPhysDamageHexed): _Def("Reduce Phys Damage (hexed)", V_A2),
    int(ModifierIdentifier.ReceiveLessPhysDamageStance): _Def("Reduce Phys Damage (stance)", V_A2),
    int(ModifierIdentifier.ReduceConditionDuration): _Def("Reduces Condition", V_NONE, 1, Reduced_Ailment),
    int(ModifierIdentifier.ReduceConditionTupleDuration): _Def("Reduces Condition", V_NONE, 2, Reduced_Ailment),
    int(ModifierIdentifier.ReducesDiseaseDuration): _Def("Reduces Disease"),
    int(ModifierIdentifier.ReceiveLessDamage): _Def("Receive Less Damage", V_A2),
    int(ModifierIdentifier.BowType): _Def("Bow Type", V_NONE, 1, BowType),
    int(ModifierIdentifier.TargetItemType): _Def("Target Item Type", V_NONE, 1, ItemType),
    int(ModifierIdentifier.TooltipDescription): _Def("Tooltip"),
    int(ModifierIdentifier.AttributeRune): _Def("Attribute", V_A2, 1, Attribute),  # rune: {attr} +{tier}
}

_UPGRADE_ID = int(ModifierIdentifier.Upgrade)
_ATTR_RUNE_ID = int(ModifierIdentifier.AttributeRune)
_VALID_IDS: frozenset[int] = frozenset(int(e) for e in ModifierIdentifier)


# upgrade_id (barcode) -> the named-mod name, folded across weapon types (Icy_Axe/Icy_Bow -> "Icy").
def _build_upgrade_names() -> dict[int, str]:
    out: dict[int, str] = {}
    for member in ItemUpgrade:
        val = member.value
        if isinstance(val, dict):
            for uid in val.values():
                out[int(uid)] = member.name
        elif isinstance(val, ItemUpgradeId):
            out[int(val)] = member.name
        elif isinstance(val, int):
            out[int(val)] = member.name
    return out


_UPGRADE_NAME: dict[int, str] = _build_upgrade_names()


@dataclass
class DecodedMod:
    """One decoded modifier word off an item."""
    identifier: int          # stripped ModifierIdentifier value
    arg1: int
    arg2: int
    upgrade_id: int          # low-16 barcode (only meaningful on the Upgrade word), else 0
    raw_arg: int             # arg1<<8 | arg2


def decode_item(item_id: int) -> list[DecodedMod]:
    """Every valid modifier on the item, decoded to (identifier, args, upgrade_id)."""
    out: list[DecodedMod] = []
    try:
        py = PyItem.PyItem(item_id)
        mods = py.modifiers or []
    except Exception:
        return out
    for m in mods:
        try:
            if not m.IsValid():
                continue
            runtime_id = m.GetIdentifier()
            stripped = (runtime_id >> 4) & 0x3FF
            if stripped not in _VALID_IDS:
                continue
            a1, a2 = m.GetArg1(), m.GetArg2()
            uid = 0
            if stripped in (_UPGRADE_ID, _ATTR_RUNE_ID):
                # upgrade_id = low 16 bits of the word = GetArg() (GetModBits returns a binary STRING).
                uid = m.GetArg() & 0xFFFF
            out.append(DecodedMod(stripped, a1, a2, uid, (a1 << 8) | a2))
        except Exception:
            continue
    return out


def find(item_id: int, *identifiers: int) -> Optional[DecodedMod]:
    """First decoded mod on the item whose identifier is one of `identifiers`, else None."""
    wanted = {int(i) for i in identifiers}
    for dm in decode_item(item_id):
        if dm.identifier in wanted:
            return dm
    return None


def value_of(mod: DecodedMod) -> list[int]:
    """The mod's value(s), always a list. [] when the mod carries no numeric value."""
    d = _EFFECT.get(mod.identifier)
    if d is None:
        return []
    if d.value == V_RANGE:
        return [mod.arg2, mod.arg1]
    if d.value == V_A1:
        v = mod.arg1
    elif d.value == V_A2:
        v = mod.arg2
    else:
        return []
    v += d.offset
    return [-v if d.negate else v]


def subtype_of(mod: DecodedMod):
    """The mod's catalog subtype (an enum member), or None."""
    d = _EFFECT.get(mod.identifier)
    if d is None or d.subtype_arg == 0 or d.subtype_cat is None:
        return None
    idx = mod.arg1 if d.subtype_arg == 1 else mod.arg2
    try:
        return d.subtype_cat(idx)
    except ValueError:
        return None


def name_of(mod: DecodedMod) -> str:
    """Human name: the upgrade's folded name if it's a barcode, else the effect name."""
    if mod.upgrade_id and mod.upgrade_id in _UPGRADE_NAME:
        return _UPGRADE_NAME[mod.upgrade_id]
    d = _EFFECT.get(mod.identifier)
    return d.name if d is not None else "0x%X" % mod.identifier


def is_better(mod: DecodedMod) -> bool:
    """True if this mod's value axis is 'lower is better' (e.g. requirement)."""
    d = _EFFECT.get(mod.identifier)
    return bool(d and d.better_low)


def upgrades_on(item_id: int) -> list[tuple[str, int]]:
    """The applied upgrades on the item as (name, slot) — one per barcode word."""
    out: list[tuple[str, int]] = []
    for dm in decode_item(item_id):
        if dm.upgrade_id and dm.upgrade_id in _UPGRADE_NAME:
            name = _UPGRADE_NAME[dm.upgrade_id]
            slot = mods_upgrades.UPGRADE_SLOT.get(name)
            if slot is not None:
                out.append((name, slot))
    return out


def slot_of_upgrade(name: str) -> Optional[int]:
    """The slot (Slot value) for an upgrade name, or None."""
    return mods_upgrades.UPGRADE_SLOT.get(name)


def upgrade_is_maxed(item_id: int, upgrade_name: str) -> bool:
    """True if the upgrade's variable value is at the top of its roll range."""
    var_id = mods_upgrades.UPGRADE_VAR.get(upgrade_name)
    rng = mods_upgrades.UPGRADE_RANGE.get(upgrade_name)
    if var_id is None or rng is None:
        return False
    dm = find(item_id, var_id)
    if dm is None:
        return False
    vals = value_of(dm)
    return bool(vals) and vals[0] >= rng[1]


def effect_name(identifier: int) -> str:
    """The effect/base name for a modifier identifier."""
    d = _EFFECT.get(int(identifier))
    if d is not None:
        return d.name
    try:
        return ModifierIdentifier(int(identifier)).name
    except ValueError:
        return "0x%X" % int(identifier)


# ── description rendering (the game-style text / oracle layer) ───────────────────
def _pretty(name: str) -> str:
    """'IllusionMagic' -> 'Illusion Magic'; '_' -> ' '."""
    if not name:
        return name
    out = name[0]
    for c in name[1:]:
        if c.isupper() and out[-1].islower():
            out += " "
        out += c
    return out.replace("_", " ")


# Game-style templates per identifier. {value} {sub}. Damage is rendered with its type sibling.
_TEXT: dict[int, str] = {
    int(ModifierIdentifier.AttributeRequirement): "Requires {value} {sub}",
    int(ModifierIdentifier.Armor1): "Armor: {value}",
    int(ModifierIdentifier.Armor2): "Armor: {value}",
    int(ModifierIdentifier.ArmorPlus): "Armor +{value}",
    int(ModifierIdentifier.ArmorPlusVsDamage): "Armor +{value} (vs. {sub} damage)",
    int(ModifierIdentifier.ArmorPlusVsElemental): "Armor +{value} (vs. elemental damage)",
    int(ModifierIdentifier.ArmorPlusVsPhysical): "Armor +{value} (vs. physical damage)",
    int(ModifierIdentifier.ArmorPlusVsPhysical2): "Armor +{value} (vs. physical damage)",
    int(ModifierIdentifier.ArmorPlusVsSpecies): "Armor +{value} (vs. {sub})",
    int(ModifierIdentifier.ArmorPlusAttacking): "Armor +{value} (while attacking)",
    int(ModifierIdentifier.ArmorPlusCasting): "Armor +{value} (while casting)",
    int(ModifierIdentifier.ArmorPlusEnchanted): "Armor +{value} (while Enchanted)",
    int(ModifierIdentifier.ArmorPlusHexed): "Armor +{value} (while Hexed)",
    int(ModifierIdentifier.ArmorMinusAttacking): "Armor -{value} (while attacking)",
    int(ModifierIdentifier.HealthPlus): "Health +{value}",
    int(ModifierIdentifier.HealthMinus): "Health -{value}",
    int(ModifierIdentifier.HealthPlusEnchanted): "Health +{value} (while Enchanted)",
    int(ModifierIdentifier.HealthPlusHexed): "Health +{value} (while Hexed)",
    int(ModifierIdentifier.HealthPlusStance): "Health +{value} (while in a Stance)",
    int(ModifierIdentifier.HealthRegeneneration): "Health regeneration {value}",
    int(ModifierIdentifier.Energy): "Energy +{value}",
    int(ModifierIdentifier.Energy2): "Energy +{value}",
    int(ModifierIdentifier.EnergyPlus): "Energy +{value}",
    int(ModifierIdentifier.EnergyPlusEnchanted): "Energy +{value} (while Enchanted)",
    int(ModifierIdentifier.EnergyPlusHexed): "Energy +{value} (while Hexed)",
    int(ModifierIdentifier.EnergyRegeneration): "Energy regeneration {value}",
    int(ModifierIdentifier.EnergyGainOnHit): "Energy gain on hit: {value}",
    int(ModifierIdentifier.DamagePlusPercent): "Damage +{value}%",
    int(ModifierIdentifier.DamageCustomized): "Damage +{value}%",
    int(ModifierIdentifier.DamagePlusStance): "Damage +{value}% (while in a Stance)",
    int(ModifierIdentifier.DamagePlusEnchanted): "Damage +{value}% (while Enchanted)",
    int(ModifierIdentifier.DamagePlusHexed): "Damage +{value}% (while Hexed)",
    int(ModifierIdentifier.DamagePlusWhileAbove): "Damage +{value}% (while Health is above {thresh}%)",
    int(ModifierIdentifier.DamagePlusWhileBelow): "Damage +{value}% (while Health is below {thresh}%)",
    int(ModifierIdentifier.ArmorPlusAbove): "Armor +{value} (while Health is above {thresh}%)",
    int(ModifierIdentifier.ArmorPlusWhileBelow): "Armor +{value} (while Health is below {thresh}%)",
    int(ModifierIdentifier.EnergyPlusWhileAbove): "Energy +{value} (while Health is above {thresh}%)",
    int(ModifierIdentifier.EnergyPlusWhileBelow): "Energy +{value} (while Health is below {thresh}%)",
    int(ModifierIdentifier.HealthStealOnHit): "Life Draining: {value}",
    int(ModifierIdentifier.IncreaseEnchantmentDuration): "Enchantments last {value}% longer",
    int(ModifierIdentifier.IncreaseConditionDuration): "Lengthens {sub} duration on foes by 33% (Stacking)",
    int(ModifierIdentifier.ReduceConditionDuration): "Reduces {sub} duration on you by 20% (Stacking)",
    int(ModifierIdentifier.OfTheProfession): "{sub}: {value}",
    int(ModifierIdentifier.Furious): "Double adrenaline gain (Chance: {value}%)",
    int(ModifierIdentifier.ArmorPenetration): "Armor penetration +{value}% (Chance: {thresh}%)",
    int(ModifierIdentifier.HeadpieceAttribute): "{sub} +{value} (Stacking)",
    int(ModifierIdentifier.AttributeRune): "{sub} +{value} (Non-stacking)",
    int(ModifierIdentifier.HealthPlus2): "Health +{value} (Non-stacking)",
    int(ModifierIdentifier.ReceiveLessDamage): "Received physical damage -{value} (Chance: {thresh}%)",
    int(ModifierIdentifier.ReceiveLessPhysDamageStance): "Received physical damage -{value} (while in a Stance)",
    int(ModifierIdentifier.ReceiveLessPhysDamageEnchanted): "Received physical damage -{value} (while Enchanted)",
    int(ModifierIdentifier.ReceiveLessPhysDamageHexed): "Received physical damage -{value} (while Hexed)",
    int(ModifierIdentifier.HalvesCastingTimeGeneral): "Halves casting time of spells (Chance: {value}%)",
    int(ModifierIdentifier.HalvesCastingTimeAttribute): "Halves casting time of {sub} spells (Chance: {value}%)",
    int(ModifierIdentifier.HalvesSkillRechargeGeneral): "Halves skill recharge of spells (Chance: {value}%)",
    int(ModifierIdentifier.HalvesSkillRechargeAttribute): "Halves skill recharge of {sub} spells (Chance: {value}%)",
    int(ModifierIdentifier.Infused): "Infused",
    int(ModifierIdentifier.AttributePlusOne): "{sub} +1 ({value}% chance while using skills)",
}

# identifiers with no visible line (structural / absorbed into another line).
_SILENT: frozenset[int] = frozenset({
    int(ModifierIdentifier.Empty),
    int(ModifierIdentifier.DamageTypeProperty),   # merged into the Damage line
    int(ModifierIdentifier.TooltipDescription),
    int(ModifierIdentifier.BowType),
    int(ModifierIdentifier.TargetItemType),
    int(ModifierIdentifier.Upgrade),              # barcode carrier -> handled via upgrade_id
})


def render_mod(item_id: int, mod: DecodedMod) -> str:
    """A game-style human-readable line for the mod, or '' if it renders no visible line."""
    ident = mod.identifier
    if ident in _SILENT:
        return ""
    d = _EFFECT.get(ident)
    if d is None:
        return ""
    if d.value == V_RANGE:   # Damage: combine with the damage-type sibling -> "Fire Dmg: 6-28"
        dt = find(item_id, int(ModifierIdentifier.DamageTypeProperty))
        dsub = subtype_of(dt) if dt is not None else None
        dname = _pretty(dsub.name) if dsub is not None else "Damage"
        return "%s Dmg: %d-%d" % (dname, mod.arg2, mod.arg1)
    if ident in (int(ModifierIdentifier.HalvesCastingTimeItemAttribute),
                 int(ModifierIdentifier.HalvesSkillRechargeItemAttribute)):
        # "of item's attribute" -> the item's requirement attribute (a sibling mod)
        req = find(item_id, int(ModifierIdentifier.AttributeRequirement))
        rattr = subtype_of(req) if req is not None else None
        attr_s = _pretty(rattr.name) if rattr is not None else "item's attribute"
        verb = "casting time" if ident == int(ModifierIdentifier.HalvesCastingTimeItemAttribute) else "skill recharge"
        return "Halves %s of %s spells (Chance: %d%%)" % (verb, attr_s, mod.arg1)
    vals = value_of(mod)
    sub = subtype_of(mod)
    sub_s = _pretty(sub.name) if sub is not None else ""
    tmpl = _TEXT.get(ident)
    if tmpl:
        return (tmpl.replace("{value}", str(vals[0]) if vals else "")
                    .replace("{sub}", sub_s)
                    .replace("{thresh}", str(mod.arg1)))
    v = (" %+d" % vals[0]) if vals else ""
    s = (" (%s)" % sub_s) if sub_s else ""
    return (d.name + s + v).strip()


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def describe_item(item_id: int) -> list[str]:
    """Game-style description lines the engine produces for the item.
    Combines: (1) effect modifier WORDS (base stats, weapon-upgrade effects, attribute runes),
    (2) rune/insignia INTRINSIC effects (armor upgrades store no effect word -> from the game's
    390-component descriptions), and (3) inscription name labels. Text-deduped so a line that is
    both a word and part of an upgrade's description (e.g. a rune's 'Health -75') appears once."""
    out: list[str] = []
    seen: set[str] = set()

    def add(line: str) -> None:
        n = _norm(line)
        if n and n not in seen:
            seen.add(n)
            out.append(line)

    for dm in decode_item(item_id):        # (1) effect words
        line = render_mod(item_id, dm)
        if line:
            add(line)

    for dm in decode_item(item_id):        # (2)+(3) upgrades
        uid = dm.upgrade_id
        if not uid:
            continue
        name = _UPGRADE_NAME.get(uid)
        if not name:
            continue
        if mods_upgrades.UPGRADE_SLOT.get(name) == int(Slot.Inscription):
            add('Inscription: "%s"' % _pretty(name))
        # armor rune/insignia intrinsic effects (their effect is not stored as a modifier word)
        if ("Rune" in name or "Insignia" in name) and uid in mods_upgrades.UPGRADE_DESC:
            # 'backslash-n' is a literal line-break placeholder. Join it to a following '(clause)'
            # (the game keeps "Health +50 (Non-stacking)" on one line) but split it before a
            # new effect (e.g. "... backslash-n Health -75" -> its own line).
            d = mods_upgrades.UPGRADE_DESC[uid]
            d = d.replace(" \\n (", " (").replace("\\n (", " (").replace("\\n(", " (")
            for part in d.split("\\n"):
                part = " ".join(part.split()).strip()
                if part:
                    add(part)
    return out


def raw_dump(item_id: int) -> list[str]:
    """Every decoded modifier word (for diagnosing gaps): id / args / upgrade_id + render status."""
    out: list[str] = []
    for dm in decode_item(item_id):
        if dm.upgrade_id:   # a barcode carrier word
            nm = _UPGRADE_NAME.get(dm.upgrade_id)
            tag = ("upgrade: %s" % nm) if nm else ("upgrade: ?UNKNOWN (uid=0x%X)" % dm.upgrade_id)
        else:
            rendered = render_mod(item_id, dm)
            if rendered:
                tag = "-> %s" % rendered
            elif dm.identifier in _SILENT:
                tag = "(structural)"
            else:
                tag = "(UNHANDLED)"
        out.append("0x%03X %-24s a1=%-3d a2=%-3d  %s" % (
            dm.identifier, effect_name(dm.identifier)[:24], dm.arg1, dm.arg2, tag))
    return out
