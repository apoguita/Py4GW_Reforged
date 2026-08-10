"""What the hand-list surfaces are, defined once.

A **surface** is one toggleable body of entries -- Rarities, Materials, Dyes, Nicholas, or a catalog
category. Settings shows all of them; the quick access shows the ones the user put there. Both draw
them through the shared renderer, so the definition lives here rather than in either.

Each surface supplies its entries as ``(entry_id, display_name, model_id_or_None)`` and the set it
toggles, so the renderer needs to know nothing about what it is drawing.
"""

from . import catalog as catalog_data
from . import dyes as dye_data
from . import materials as material_data
from .nicholas import NicholasSelection
from .nicholas import entry_for_week
from .nicholas import monday_of

RARITIES = "Rarities"
MATERIALS = "Materials"
SALVAGES_TO = "Salvages to"
DYES = "Dyes"
NICHOLAS = "Nicholas"
ITEM_TYPES = "Never these types"

#: Rarity keys in display order. Gold coins is independent and combinable with any of them.
RARITY_KEYS: tuple[tuple[str, str], ...] = (
    ("white", "Whites"), ("blue", "Blues"), ("purple", "Purples"),
    ("gold", "Golds"), ("green", "Greens"), ("gold_coins", "Gold coins"),
)


def names() -> list[str]:
    """Every surface a user may put in their quick access, each exactly once.

    Deduplicated deliberately: "Materials" is both a purpose-built surface and a catalog category, so
    a naive concatenation would list it twice -- two identical headers, and ImGui reporting two
    visible items with a conflicting id.
    """
    seen: dict[str, None] = {}
    for name in ([RARITIES, ITEM_TYPES, MATERIALS, SALVAGES_TO, DYES, NICHOLAS]
                 + list(catalog_data.categories())):
        seen.setdefault(name, None)
    return list(seen)


def default_layout(surface: str) -> str:
    """The layout a surface starts on. The user may change any of them."""
    from .renderer import CHECKBOX_LIST
    from .renderer import TEXTURE_GRID

    return CHECKBOX_LIST if surface in (RARITIES, DYES, NICHOLAS, ITEM_TYPES) else TEXTURE_GRID


def groups_for(surface: str, config) -> list[tuple[str, list[tuple[int, str, int | None]]]]:
    """``[(group_name_or_empty, entries), ...]`` for a surface.

    An empty group name means the surface has no second level and renders flat.
    """
    if surface == MATERIALS:
        out = []
        for kind, label in ((material_data.COMMON, "Common"), (material_data.RARE, "Rare"), ("", "Other")):
            rows = [(m.model_id, m.name, m.model_id) for m in material_data.MATERIALS if m.kind == kind]
            if rows:
                out.append((label, rows))
        return out

    if surface == SALVAGES_TO:
        # Every material is offered. The bundled salvage data is incomplete, so it informs the
        # tooltip and never limits the choice.
        out = []
        for kind, label in ((material_data.COMMON, "Common"), (material_data.RARE, "Rare"), ("", "Other")):
            rows = [(m.model_id, m.name, m.model_id) for m in material_data.MATERIALS if m.kind == kind]
            if rows:
                out.append((label, rows))
        return out

    if surface == DYES:
        # Every dye shares one model id, so a dye has no texture of its own: model is None.
        return [("", [(d.color_id, d.name, None) for d in dye_data.DYES])]

    if surface == RARITIES:
        return [("", [(index, label, None) for index, (_key, label) in enumerate(RARITY_KEYS)])]

    if surface == ITEM_TYPES:
        # The curated taxonomy, IN ITS GROUPS -- "every weapon" has to be one action.
        from ..loot_filter_factory import item_types as item_type_data

        return [(group, [(value, display, None) for display, value in entries])
                for group, entries in item_type_data.grouped()]

    if surface == NICHOLAS:
        return [("", [])]  # Nicholas has its own editor; it is not a toggle list.

    # A catalog category. Trophies has no groups -- its A..W split is banded at render time.
    entries = catalog_data.in_category(surface)
    if not entries:
        return []
    group_names = catalog_data.groups(surface)
    if not group_names:
        return [(band, [(e.model_id, e.name, e.model_id) for e in rows])
                for band, rows in catalog_data.alphabetical_bands(entries)]
    return [(name, [(e.model_id, e.name, e.model_id)
                    for e in catalog_data.in_group(surface, name)]) for name in group_names]


def selected_set(surface: str, config) -> set[int]:
    """The set a surface toggles, on the given config instance."""
    if surface == DYES:
        return config.enabled_dye_colors
    if surface == SALVAGES_TO:
        return config.salvage_target_ids
    if surface == ITEM_TYPES:
        return config.blacklist_item_types
    if surface == RARITIES:
        return {index for index, (key, _label) in enumerate(RARITY_KEYS) if config.rarity_enabled(key)}
    return config.enabled_model_ids


def apply_to(surface: str, config, entry_id: int, on: bool) -> None:
    """Toggle one entry on one config instance."""
    if surface == RARITIES:
        key = RARITY_KEYS[entry_id][0]
        config.set_rarity(key, on)
        return
    target = selected_set(surface, config)
    if on:
        target.add(int(entry_id))
    else:
        target.discard(int(entry_id))


def tooltip_for(surface: str):
    """A tooltip function for a surface, or None. The textured layout depends on these."""
    if surface == SALVAGES_TO:
        def salvage_tooltip(entry_id: int) -> str:
            material = material_data.material(entry_id)
            known = material_data.known_sources(entry_id)
            name = material.name if material else str(entry_id)
            if known:
                return "%s\n%d known item(s) salvage into this." % (name, known)
            return "%s\nNo items recorded - the bundled data is incomplete, not exhaustive." % name
        return salvage_tooltip

    if surface == ITEM_TYPES:
        def type_tooltip(entry_id: int) -> str:
            return ("Ticked = NEVER take this type.\n"
                    "A veto: it beats every reason, exactly like the model blacklist.")
        return type_tooltip

    if surface in (RARITIES, DYES, NICHOLAS):
        return None

    def item_tooltip(entry_id: int) -> str:
        entry = catalog_data.by_model_id(entry_id)
        if entry is None:
            material = material_data.material(entry_id)
            return material.name if material else str(entry_id)
        parts = [entry.name, entry.category if not entry.group else "%s / %s" % (entry.category, entry.group),
                 "model %d" % entry.model_id]
        return "\n".join(parts)
    return item_tooltip


def nicholas_rows(config, today):
    """``[(selection, label, is_current_week), ...]`` for the Nicholas editor."""
    rows = []
    for selection in config.nicholas:
        week = monday_of(today) if selection.week is None else selection.week
        entry = entry_for_week(week)
        item = entry.get("item", "?") if entry else "?"
        label = ("This week: %s" % item) if selection.week is None \
            else ("%s: %s" % (week.isoformat(), item))
        rows.append((selection, label, selection.week is None))
    return rows


def nicholas_preview(day):
    """What a date would resolve to, for the entry control."""
    entry = entry_for_week(monday_of(day))
    if entry is None:
        return ""
    return "%s - %s" % (entry.get("item", "?"), entry.get("location", ""))
