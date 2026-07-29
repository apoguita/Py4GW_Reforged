"""Evaluating filters against a live item.

**All evaluation lives here.** Rules are values; nothing outside this module supplies logic that
decides whether an item matches. Data in, decisions out.

:func:`evaluate` returns the per-criterion breakdown as well as the verdict, because the Item Mods
Playground already shows exactly that -- *"ITEM MATCHES (all of 4 criteria)"* with a pass/fail line
per condition -- and the filter editor's live preview copies it.

Two levels above that:

* :func:`matches` -- does one filter match one item.
* :func:`any_match` -- does *any* enabled filter match. This is the HAS-ANY both features use.
"""

from .model import MATCH_ANY
from .model import Rule


def evaluate(rule: Rule, item_id: int, model_id: int | None = None) -> tuple[bool, list[tuple[str, bool]]]:
    """``(verdict, [(label, passed), ...])`` for one filter against one item.

    Only criteria the user actually set are evaluated; an unset criterion is not a constraint. A rule
    with no criteria at all matches nothing.
    """
    from Py4GWCoreLib.Item import Item

    results: list[tuple[str, bool]] = []

    if rule.item_types:
        try:
            got = int(Item.GetItemType(item_id)[0])
        except Exception:
            got = -1
        results.append(("item type", got in rule.item_types))

    if rule.model_ids:
        if model_id is None:
            model_id = Item.GetModelID(item_id)
        results.append(("model", int(model_id) in rule.model_ids))

    if rule.rarities:
        # Readable before identifying: rarity comes off the interaction flags.
        checks = (Item.Rarity.IsWhite, Item.Rarity.IsBlue, Item.Rarity.IsPurple,
                  Item.Rarity.IsGold, Item.Rarity.IsGreen)
        got = False
        for index in rule.rarities:
            try:
                if 0 <= int(index) < len(checks) and checks[int(index)](item_id):
                    got = True
                    break
            except Exception:
                continue
        results.append(("rarity", got))

    if rule.name_contains:
        # `contains` is the other half of the closed operator set, and it applies to names only.
        #
        # A ground item's name decodes ASYNCHRONOUSLY -- it is not there on the first frame or two
        # per item kind. So request it, and while it is not ready report the criterion as not
        # passing rather than guessing: a drop is re-evaluated every frame, so it starts matching
        # the moment the name arrives.
        try:
            if Item.IsNameReady(item_id):
                name = (Item.GetName(item_id) or "").lower()
            else:
                Item.RequestName(item_id)
                name = ""
        except Exception:
            name = ""
        results.append(("name contains %s" % " / ".join(rule.name_contains),
                        bool(name) and any(part.lower() in name for part in rule.name_contains)))

    if rule.dye_colors:
        # Dyes are identified by ITEM TYPE plus colour -- every dye shares one model id.
        from ..item_catalog import dyes as dye_data

        results.append(("dye colour",
                        dye_data.is_dye(item_id) and dye_data.color_of(item_id) in rule.dye_colors))

    if rule.salvages_into:
        from ..item_catalog import materials as material_data

        if model_id is None:
            model_id = Item.GetModelID(item_id)
        common, rare = material_data.salvages_into(int(model_id))
        results.append(("salvages into", any(m in rule.salvages_into for m in common + rare)))

    # -- the mod criteria, all three routed through the MOTHER MODULE --
    #
    # `Item.Mods.HasMod(item_id, mod, *values)` already does exactly what is needed:
    #   "an enum arg = a subtype filter; a number = a value threshold ('N or better',
    #    direction from the mod's metadata)"
    # So the direction is never chosen here -- `Requirement` carries better_low=True and the
    # comparison flips itself. Hand-rolling these comparisons is what lost the direction and the
    # range in the first place.

    if rule.max_requirement is not None:
        args: list = [rule.max_requirement]
        if rule.requirement_attribute is not None:
            try:
                from Py4GWCoreLib.enums import Attribute

                args.append(Attribute(rule.requirement_attribute))   # an enum arg = subtype filter
            except Exception:
                pass
        try:
            from Py4GWCoreLib.mods_types import ModifierIdentifier

            ok = bool(Item.Mods.HasMod(item_id, ModifierIdentifier.AttributeRequirement, *args))
        except Exception:
            ok = False
        results.append(("requirement %d or lower" % rule.max_requirement, ok))

    if rule.min_damage is not None:
        # Damage is a RANGE: `value_of` returns [arg2, arg1] = [low, high]. The top end is the
        # number the game shows ("Chaos Dmg: 11-21"), so that is what is compared.
        try:
            from Py4GWCoreLib.mods_types import ModifierIdentifier

            ok = bool(Item.Mods.HasMod(item_id, ModifierIdentifier.Damage,
                                       lambda low: True, lambda high: high >= rule.min_damage))
        except Exception:
            ok = False
        results.append(("damage %d or better" % rule.min_damage, ok))

    if rule.damage_types:
        try:
            from Py4GWCoreLib.enums import DamageType
            from Py4GWCoreLib.mods_types import ModifierIdentifier

            ok = any(Item.Mods.HasMod(item_id, ModifierIdentifier.DamageTypeProperty, DamageType(d))
                     for d in rule.damage_types)
        except Exception:
            ok = False
        results.append(("damage type", ok))

    if rule.min_value is not None:
        try:
            value = int(Item.Properties.GetValue(item_id) or 0)
        except Exception:
            value = 0
        # Match-or-better, because higher is better for value.
        results.append(("worth %d or more" % rule.min_value, value >= rule.min_value))

    if not results:
        return False, results
    passed = [ok for _label, ok in results]
    verdict = any(passed) if rule.mode == MATCH_ANY else all(passed)
    return verdict, results


def matches(rule: Rule, item_id: int, model_id: int | None = None) -> bool:
    if rule.is_empty():
        return False
    return evaluate(rule, item_id, model_id)[0]


def any_match(rules, item_id: int, model_id: int | None = None) -> bool:
    """HAS-ANY: whether any enabled filter matches. Order is irrelevant here."""
    for rule in rules:
        if rule.enabled and matches(rule, item_id, model_id):
            return True
    return False


def matching_rules(rules, item_id: int, model_id: int | None = None) -> list[Rule]:
    """Every enabled filter that matches, in order."""
    return [r for r in rules if r.enabled and matches(r, item_id, model_id)]
