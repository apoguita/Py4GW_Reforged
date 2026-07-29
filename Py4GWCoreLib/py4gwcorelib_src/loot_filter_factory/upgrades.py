"""The five upgrade lists, derived from the mods module.

Copied from the Item Mods Playground (`_build_lists`, `:59-74`): upgrades are split by **slot**, and
insignias and runes are separated from plain prefixes and suffixes by name. This is why a user picks
*"Sundering"* rather than modifier id 42 -- the identity of an upgrade is its name, and the whole
filter surface is built on that.

Names are prettified through ``mods_core._pretty`` and sorted, exactly as the reference does.
"""

_CACHE: dict[str, list[tuple[str, str]]] | None = None


def _pretty(internal: str) -> str:
    """Display name for an internal upgrade name, matching the playground's presentation."""
    try:
        from Py4GWCoreLib import mods_core

        s = mods_core._pretty(internal)
    except Exception:
        s = internal
    s = s.replace(" Of ", " of ").replace(" The ", " the ").replace(" And ", " and ")
    if s.startswith("Of "):
        s = "of " + s[3:]
    return s


def _build() -> dict[str, list[tuple[str, str]]]:
    """``{slot_key: [(display, internal), ...]}`` -- empty offline, where mods_core is unavailable."""
    lists: dict[str, list[tuple[str, str]]] = {
        "prefixes": [], "suffixes": [], "runes": [], "insignias": [], "inscriptions": [],
    }
    try:
        from Py4GWCoreLib import mods_core
        from Py4GWCoreLib import mods_upgrades
    except Exception:
        return lists

    for name, slot in mods_upgrades.UPGRADE_SLOT.items():
        entry = (_pretty(name), name)
        if slot == int(mods_core.Slot.Prefix):
            (lists["insignias"] if "Insignia" in name else lists["prefixes"]).append(entry)
        elif slot == int(mods_core.Slot.Suffix):
            (lists["runes"] if "Rune" in name else lists["suffixes"]).append(entry)
        elif slot == int(mods_core.Slot.Inscription):
            lists["inscriptions"].append(entry)
    for values in lists.values():
        values.sort(key=lambda e: e[0].lower())
    return lists


def lists() -> dict[str, list[tuple[str, str]]]:
    """The five lists, built once."""
    global _CACHE
    if _CACHE is None:
        _CACHE = _build()
    return _CACHE


def display_name(internal: str) -> str:
    for values in lists().values():
        for display, name in values:
            if name == internal:
                return display
    return _pretty(internal)


def applied_upgrades(item_id: int) -> set[str]:
    """Internal names of the upgrades on an item. The set a filter's upgrade criteria match against."""
    try:
        from Py4GWCoreLib.Item import Item

        return {name for name, _slot in Item.Mods.GetUpgrades(item_id)}
    except Exception:
        return set()
