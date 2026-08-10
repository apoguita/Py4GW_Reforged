"""The shared hand-list renderer -- ONE implementation, used by settings and the quick access.

Both surfaces show the same lists with the same layouts, the same collapsible headers and the same
bulk actions, so they call the same function. A fix or a new layout lands in both at once and they
cannot drift apart.

**One structure, many renderings.** Collapsible headers are the container everywhere -- that is what
makes the system feel like one thing. What sits *inside* a header is chosen to fit the data, and the
**user** picks it per surface:

1. ``checkbox_list``   -- few options, or the cheapest to draw
2. ``checkbox_grid``   -- a large set, cheap cells
3. ``toggle_grid``     -- a large set, buttons carrying the item's text
4. ``texture_grid``    -- the most compact, and the heaviest: one texture per entry

Where a texture is missing, ``get_texture_for_model`` already returns
``Assets/Textures/Item Models/0-File_Not_found.png``, so the textured layout is offered everywhere and simply
shows the placeholder. Layout 3 is a *choice*; the placeholder is a *safety net*.
"""

import PyImGui

from ....ImGui import ImGui

#: `text_disabled` renders too dim to read; a mid gray keeps secondary text legible.
GRAY = (0.66, 0.67, 0.70, 1.0)

CHECKBOX_LIST = "checkbox_list"
CHECKBOX_GRID = "checkbox_grid"
TOGGLE_GRID = "toggle_grid"
TEXTURE_GRID = "texture_grid"

LAYOUTS: tuple[tuple[str, str], ...] = (
    (CHECKBOX_LIST, "Checkbox list"),
    (CHECKBOX_GRID, "Checkbox grid"),
    (TOGGLE_GRID, "Toggle grid"),
    (TEXTURE_GRID, "Textured grid"),
)

_TILE = 48.0


def _texture(model_id: int) -> str:
    try:
        from Py4GWCoreLib.enums_src.Texture_enums import get_texture_for_model

        return get_texture_for_model(int(model_id))
    except Exception:
        return ""


def bulk_buttons(key: str, ids, selected: set[int], apply) -> None:
    """`all` / `clear` for one level. Offered at EVERY level where it applies.

    ``apply(entry_id, on)`` performs the change, so this stays ignorant of which list it edits.
    """
    ids = list(ids)
    if not ids:
        return
    if PyImGui.small_button("all##bulk_on_%s" % key):
        for entry_id in ids:
            if entry_id not in selected:
                apply(entry_id, True)
    PyImGui.same_line(0, 4)
    if PyImGui.small_button("clear##bulk_off_%s" % key):
        for entry_id in ids:
            if entry_id in selected:
                apply(entry_id, False)
    PyImGui.same_line(0, 8)


def draw_entries(key: str, entries, selected: set[int], apply, layout: str,
                 tooltip=None) -> None:
    """Draw one flat run of entries in the chosen layout.

    ``entries`` is ``[(entry_id, display_name, model_id_or_None), ...]``. ``model_id`` is what a
    texture is resolved from; ``None`` means this entry has no texture (a dye colour, for instance),
    and the textured layout falls back to the toggle for it.
    """
    entries = list(entries)
    if not entries:
        PyImGui.text_colored("Nothing here.", GRAY)
        return

    if layout == CHECKBOX_LIST:
        for entry_id, name, _model in entries:
            on = entry_id in selected
            if PyImGui.checkbox("%s##%s_%s" % (name, key, entry_id), on) != on:
                apply(entry_id, not on)
            if tooltip:
                ImGui.show_tooltip(tooltip(entry_id))
        return

    if layout == CHECKBOX_GRID:
        columns = max(1, int(PyImGui.get_content_region_avail()[0] // 160))
        for index, (entry_id, name, _model) in enumerate(entries):
            if index % columns:
                PyImGui.same_line(0, 12)
            on = entry_id in selected
            if PyImGui.checkbox("%s##%s_%s" % (name, key, entry_id), on) != on:
                apply(entry_id, not on)
            if tooltip:
                ImGui.show_tooltip(tooltip(entry_id))
        PyImGui.new_line()
        return

    if layout == TOGGLE_GRID:
        columns = max(1, int(PyImGui.get_content_region_avail()[0] // 120))
        for index, (entry_id, name, _model) in enumerate(entries):
            if index % columns:
                PyImGui.same_line(0, 4)
            on = entry_id in selected
            if ImGui.toggle_button("%s##%s_%s" % (name, key, entry_id), on, 112, 22) != on:
                apply(entry_id, not on)
            if tooltip:
                ImGui.show_tooltip(tooltip(entry_id))
        PyImGui.new_line()
        return

    # TEXTURE_GRID -- the most compact and the heaviest.
    columns = max(1, int(PyImGui.get_content_region_avail()[0] // (_TILE + 6)))
    for index, (entry_id, name, model) in enumerate(entries):
        if index % columns:
            PyImGui.same_line(0, 4)
        on = entry_id in selected
        PyImGui.begin_group()
        if model is None:
            # No texture exists for this kind of entry; the toggle carries the text instead.
            if ImGui.toggle_button("%s##%s_%s" % (name, key, entry_id), on, _TILE, _TILE) != on:
                apply(entry_id, not on)
        else:
            new_state = ImGui.image_toggle_button("##%s_%s" % (key, entry_id), _texture(model), on,
                                                  width=_TILE, height=_TILE)
            if new_state != on:
                apply(entry_id, not on)
        PyImGui.end_group()
        # An icon does not identify itself -- the tooltip is what makes this layout usable.
        ImGui.show_tooltip(tooltip(entry_id) if tooltip else name)
    PyImGui.new_line()


def draw_section(key: str, title: str, groups, selected: set[int], apply, layout: str,
                 tooltip=None, default_open: bool = False) -> None:
    """One surface: a collapsible header per group, with bulk actions at every level.

    ``groups`` is ``[(group_name_or_empty, entries), ...]``. A single unnamed group renders flat --
    a category with no groups (Trophies) needs no inner header.
    """
    groups = [(name, list(entries)) for name, entries in groups]
    every = [e[0] for _name, entries in groups for e in entries]
    on_count = sum(1 for e in every if e in selected)

    # ###id: the label carries a count, and a ## label would lose its open state whenever it changed.
    if not PyImGui.collapsing_header("%s  (%d/%d)###sec_%s" % (title, on_count, len(every), key)):
        return

    bulk_buttons("sec_%s" % key, every, selected, apply)
    PyImGui.new_line()

    if len(groups) == 1 and not groups[0][0]:
        draw_entries(key, groups[0][1], selected, apply, layout, tooltip)
        return

    for name, entries in groups:
        ids = [e[0] for e in entries]
        sub_on = sum(1 for i in ids if i in selected)
        if not PyImGui.collapsing_header("%s  (%d/%d)###grp_%s_%s" % (name, sub_on, len(ids), key, name)):
            continue
        bulk_buttons("grp_%s_%s" % (key, name), ids, selected, apply)
        PyImGui.new_line()
        draw_entries("%s_%s" % (key, name), entries, selected, apply, layout, tooltip)


def layout_selector(key: str, current: str, on_change) -> None:
    """The per-surface rendering choice, with its cost warning."""
    names = [label for _value, label in LAYOUTS]
    values = [value for value, _label in LAYOUTS]
    index = values.index(current) if current in values else 0
    picked = PyImGui.combo("Layout##lay_%s" % key, index, names)
    if picked != index:
        on_change(values[picked])
    if values[picked] == TEXTURE_GRID:
        PyImGui.text_colored("Textured grid renders one texture per entry - the heaviest option.", GRAY)
