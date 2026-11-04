"""System Settings UI for automatic Identification and its private filters."""

from dataclasses import replace

import PyImGui

from ....ImGui import ImGui
from ..loot_filter_factory import config_ui as criteria_ui
from ..loot_filter_factory.model import Filter, FilterSet
from . import store
from .controller import IdentificationController, get_controller


MUTED = (0.66, 0.67, 0.70, 1.0)
WARN = (0.86, 0.65, 0.28, 1.0)
GOOD = (0.55, 0.80, 0.58, 1.0)

_state: dict[str, str] = {"new_filter_set": ""}


def _draw_general(controller: IdentificationController) -> None:
    settings = controller.settings()
    changed = False
    enabled = PyImGui.checkbox("Enable automatic identification##id_enabled", settings.enabled)
    if enabled != settings.enabled:
        settings.enabled = enabled
        changed = True

    PyImGui.text_wrapped(
        "Unidentified items are checked by rarity, then excluded by the selected Identification "
        "filter set. In explorable maps, the ID timer repeats periodically. In outposts, it runs "
        "one pass when entering and then stays idle until the next map change."
    )
    PyImGui.text_colored("Green items cannot be identified by the game and are not offered here.", WARN)
    PyImGui.text_colored(
        "Outpost warning: automatic identification can compete with manual inventory handling. "
        "It runs only once on outpost entry; disable it when you need uninterrupted manual control.",
        WARN,
    )
    PyImGui.separator()
    PyImGui.text("Identify these rarities")
    for label, attribute in (
        ("White", "id_whites"),
        ("Blue", "id_blues"),
        ("Purple", "id_purples"),
        ("Gold", "id_golds"),
    ):
        value = bool(getattr(settings, attribute))
        picked = PyImGui.checkbox("%s##id_rarity_%s" % (label, label), value)
        if picked != value:
            setattr(settings, attribute, picked)
            changed = True

    PyImGui.separator()
    prefer_infinite = PyImGui.checkbox(
        "Prefer Infinite Identification Kit##id_prefer_infinite_kit", settings.prefer_infinite_id_kit
    )
    if prefer_infinite != settings.prefer_infinite_id_kit:
        settings.prefer_infinite_id_kit = prefer_infinite
        changed = True

    PyImGui.separator()
    PyImGui.text("Identification exclusion filter set")
    PyImGui.text_colored(
        "These filters belong only to Identification and are managed in the Filters and Filter "
        "Sets tabs below. Every filter uses ALL criteria; any complete filter match excludes the item.",
        MUTED,
    )
    filter_sets = store.load_filter_sets()
    names = ["(none)"] + [filter_set.name for filter_set in filter_sets]
    current = next(
        (index + 1 for index, filter_set in enumerate(filter_sets) if filter_set.id == settings.filter_set_id), 0
    )
    picked = PyImGui.combo("##id_filter_set", current, names)
    if picked != current:
        settings.filter_set_id = "" if picked == 0 else filter_sets[picked - 1].id
        changed = True
    active = controller.active_filters()
    PyImGui.text_colored("%d exclusion filter(s) active" % len(active), MUTED)
    for filter_definition in active:
        PyImGui.text_colored("  - %s (ALL criteria)" % filter_definition.name, MUTED)
    if not active:
        PyImGui.text_colored("  (no filters: only the rarity gates apply)", MUTED)

    if changed:
        controller.save_settings()
    status = controller.status()
    if status:
        PyImGui.separator()
        PyImGui.text_colored(
            status, GOOD if "failed" not in status.lower() and "timed out" not in status.lower() else WARN
        )
    if controller.is_active():
        ImGui.show_tooltip("One item is being polled until the game reports it identified.")


def _criteria_filter(filter_definition: Filter) -> Filter:
    """Give the shared criteria editor an Identification-specific ImGui namespace."""
    return replace(filter_definition, id="identification_%s" % filter_definition.id, mode="all")


def _draw_filters() -> None:
    current = store.load_filters()
    if PyImGui.button("New filter##id_new_filter"):
        current.append(Filter(id=store.next_filter_id(current), name="Filter %d" % (len(current) + 1)))
        store.save_filters(current)
        return
    PyImGui.same_line(0, 8)
    PyImGui.text_colored("%d Identification filter(s)" % len(current), MUTED)
    PyImGui.text_wrapped(
        "Identification filters are private to this feature. Their criteria use the same model and "
        "modifier primitives as Loot Filter Factory, but their records are stored separately."
    )
    PyImGui.separator()
    if not current:
        PyImGui.text_colored("None yet. Create one above.", MUTED)
        return

    for index, filter_definition in enumerate(list(current)):
        enabled = PyImGui.checkbox("##id_filter_enabled_%s" % filter_definition.id, filter_definition.enabled)
        if enabled != filter_definition.enabled:
            current[index] = filter_definition.with_enabled(enabled)
            store.save_filters(current)
            return
        PyImGui.same_line(0, 6)
        if not PyImGui.collapsing_header(
            "%d. %s###id_filter_header_%s" % (index + 1, filter_definition.name, filter_definition.id)
        ):
            continue

        typed = PyImGui.input_text("Name##id_filter_name_%s" % filter_definition.id, filter_definition.name)
        if typed != filter_definition.name and typed.strip():
            current[index] = filter_definition.renamed(typed.strip())
            store.save_filters(current)
            return

        edited = criteria_ui._draw_criteria(_criteria_filter(filter_definition), index)
        if edited is not None:
            current[index] = replace(edited, id=filter_definition.id, mode="all")
            store.save_filters(current)
            return
        if filter_definition.is_empty():
            PyImGui.text_colored("No conditions set - this filter matches nothing.", WARN)

        PyImGui.separator()
        criteria_ui._draw_preview(_criteria_filter(filter_definition))
        PyImGui.separator()
        if PyImGui.small_button("Duplicate##id_filter_duplicate_%s" % filter_definition.id):
            current.insert(
                index + 1,
                Filter.from_dict({
                    **filter_definition.to_dict(),
                    "id": store.next_filter_id(current),
                    "name": filter_definition.name + " (copy)",
                    "mode": "all",
                }),
            )
            store.save_filters(current)
            return
        PyImGui.same_line(0, 6)
        if PyImGui.small_button("Delete##id_filter_delete_%s" % filter_definition.id):
            current.pop(index)
            filter_sets = store.load_filter_sets()
            store.save_filters(current)
            store.save_filter_sets([
                FilterSet(
                    id=filter_set.id,
                    name=filter_set.name,
                    filter_ids=tuple(
                        filter_id for filter_id in filter_set.filter_ids if filter_id != filter_definition.id
                    ),
                )
                for filter_set in filter_sets
            ])
            return


def _draw_filter_sets(controller: IdentificationController) -> None:
    current = store.load_filter_sets()
    all_filters = store.load_filters()
    PyImGui.text_wrapped(
        "Identification filter sets are private to Identification. Create a set here, then select "
        "which one the automatic handler uses on the General tab."
    )
    PyImGui.separator()
    PyImGui.push_item_width(180)
    _state["new_filter_set"] = PyImGui.input_text("##id_new_filter_set", _state["new_filter_set"])
    PyImGui.pop_item_width()
    PyImGui.same_line(0, 6)
    if PyImGui.button("New filter set##id_add_filter_set"):
        name = _state["new_filter_set"].strip()
        if name and not store.filter_set_by_name(current, name):
            current.append(FilterSet(id=store.next_filter_set_id(current), name=name))
            _state["new_filter_set"] = ""
            store.save_filter_sets(current)
            return
    PyImGui.separator()
    if not current:
        PyImGui.text_colored("No Identification filter sets yet.", MUTED)
        return

    for index, filter_set in enumerate(list(current)):
        if not PyImGui.collapsing_header(
            "%s  (%d)###id_filter_set_header_%s" % (filter_set.name, len(filter_set.filter_ids), filter_set.id)
        ):
            continue
        typed = PyImGui.input_text("Name##id_filter_set_name_%s" % filter_set.id, filter_set.name)
        if typed != filter_set.name and typed.strip():
            current[index] = FilterSet(id=filter_set.id, name=typed.strip(), filter_ids=filter_set.filter_ids)
            store.save_filter_sets(current)
            return

        PyImGui.text_colored("Filters in this filter set", MUTED)
        chosen = filter_set.filter_ids
        for filter_definition in all_filters:
            on = filter_definition.id in chosen
            picked = PyImGui.checkbox(
                "%s##id_filter_set_member_%s_%s" % (filter_definition.name, filter_set.id, filter_definition.id), on
            )
            if picked != on:
                chosen = (
                    tuple(filter_id for filter_id in chosen if filter_id != filter_definition.id)
                    if on
                    else chosen + (filter_definition.id,)
                )
                current[index] = FilterSet(id=filter_set.id, name=filter_set.name, filter_ids=chosen)
                store.save_filter_sets(current)
                return
        if not all_filters:
            PyImGui.text_colored("Create a filter first.", MUTED)

        if PyImGui.small_button("Duplicate##id_filter_set_duplicate_%s" % filter_set.id):
            name = filter_set.name + " (copy)"
            if not store.filter_set_by_name(current, name):
                current.insert(
                    index + 1,
                    FilterSet(id=store.next_filter_set_id(current), name=name, filter_ids=filter_set.filter_ids),
                )
                store.save_filter_sets(current)
                return
        PyImGui.same_line(0, 6)
        if PyImGui.small_button("Delete##id_filter_set_delete_%s" % filter_set.id):
            current.pop(index)
            if controller.settings().filter_set_id == filter_set.id:
                controller.settings().filter_set_id = ""
                controller.save_settings()
            store.save_filter_sets(current)
            return


def add_sections(win, group) -> None:
    controller = get_controller()
    win.add_account_section(group, "items.identification", "Identification")
    win.add_tab("Identification", "General", lambda c=controller: _draw_general(c))
    win.add_tab("Identification", "Filters", _draw_filters)
    win.add_tab("Identification", "Filter Sets", lambda c=controller: _draw_filter_sets(c))
