"""System Settings UI for automatic Salvage and its private filter CRUD."""

from dataclasses import replace
from typing import Any

import PyImGui

from ...Color import ColorPalette
from ..loot_filter_factory import config_ui as criteria_ui
from ..loot_filter_factory.model import Filter, FilterSet
from .model import CuratedKeepList
from . import curated, store
from .controller import SalvageController, get_controller


MUTED = (0.66, 0.67, 0.70, 1.0)
WARN = (0.86, 0.65, 0.28, 1.0)
GOOD = (0.55, 0.80, 0.58, 1.0)
_state: dict[str, Any] = {
    "selected_upgrades": set(),
    "selected_weapon_mods": set(),
    "selected_item_types": set(),
    "selected_model_ids": set(),
    "item_requirement_enabled": False,
    "item_max_requirement": 9,
    "model_ids": "",
    "new_filter_set": "",
    "salvage_preview": None,
}


def _draw_general(controller: SalvageController) -> None:
    settings = controller.settings()
    changed = False
    enabled = PyImGui.checkbox("Enable automatic Salvage##salvage_enabled", settings.enabled)
    if enabled != settings.enabled:
        settings.enabled = enabled
        changed = True
    PyImGui.text_wrapped(
        "Salvage runs on its own timer, scans only the shared Bags scope, and considers salvageable "
        "items. Unidentified White items are allowed; every other selected rarity must be identified. "
        "A matching Keep List rule is protected: named upgrades are extracted only with an "
        "Expert-or-better kit; every other keep match stays untouched. Only items that match no "
        "Keep List rule can go to material salvage. In explorable maps, the timer repeats "
        "periodically; in outposts, one batch runs on entry and then remains idle until the next "
        "map change."
    )
    PyImGui.text_colored(
        "The feature starts disabled and material confirmations stay manual unless you explicitly enable them.",
        WARN,
    )
    PyImGui.text_colored(
        "Outpost warning: automatic salvage can compete with manual inventory handling. "
        "It runs only once on outpost entry; disable it when you need uninterrupted manual control.",
        WARN,
    )
    PyImGui.separator()
    PyImGui.text("Eligible rarities")
    for label, attribute in (
        ("White", "salvage_whites"),
        ("Blue", "salvage_blues"),
        ("Purple", "salvage_purples"),
        ("Gold", "salvage_golds"),
    ):
        value = bool(getattr(settings, attribute))
        picked = PyImGui.checkbox("%s##salvage_rarity_%s" % (label, label), value)
        if picked != value:
            setattr(settings, attribute, picked)
            changed = True

    PyImGui.separator()
    PyImGui.text("Allowed operation")
    for label, attribute in (
        ("Salvage nonmatching items for common materials", "salvage_common_materials"),
        ("Salvage nonmatching items for rare materials", "salvage_rare_materials"),
        ("Extract a matching upgrade", "salvage_matching_upgrades"),
        ("Auto-confirm materials warning", "auto_confirm_materials_warning"),
        ("Prefer Infinite Superior Salvage Kit", "prefer_infinite_salvage_kit"),
    ):
        value = bool(getattr(settings, attribute))
        picked = PyImGui.checkbox("%s##salvage_action_%s" % (label, attribute), value)
        if picked != value:
            setattr(settings, attribute, picked)
            changed = True

    PyImGui.separator()
    PyImGui.text("Advanced filter set")
    filter_sets = store.load_filter_sets()
    names = ["(none)"] + [entry.name for entry in filter_sets]
    current = next((index + 1 for index, entry in enumerate(filter_sets) if entry.id == settings.filter_set_id), 0)
    picked = PyImGui.combo("##salvage_filter_set", current, names)
    if picked != current:
        settings.filter_set_id = "" if picked == 0 else filter_sets[picked - 1].id
        changed = True
    PyImGui.text_colored(
        "%d active keep rule(s): matched items cannot fall through to material salvage."
        % len(controller.active_filters()),
        MUTED,
    )
    if changed:
        controller.save_settings()
    status = controller.status()
    if status:
        PyImGui.separator()
        PyImGui.text_colored(
            status, GOOD if "failed" not in status.lower() and "timed out" not in status.lower() else WARN
        )


def _draw_upgrade_tree(category: str, color_groups: bool = False, entry_color=None) -> None:
    selected = set(str(value) for value in _state.get("selected_upgrades", set()))
    for group, entries in curated.grouped_upgrades(category):
        group_id = group.replace(" ", "_").replace("/", "_")
        count = sum(1 for _display, internal in entries if internal in selected)
        group_label = "%s (%d/%d)" % (group, count, len(entries))
        group_open = (
            _colored_tree_node(group_label, _profession_color(group), "salvage_keep_%s_%s" % (category, group_id))
            if color_groups
            else PyImGui.tree_node("%s###salvage_keep_%s_%s" % (group_label, category, group_id))
        )
        if not group_open:
            continue
        if PyImGui.small_button("Select all##salvage_keep_all_%s_%s" % (category, group_id)):
            selected.update(internal for _display, internal in entries)
        PyImGui.same_line(0, 6)
        if PyImGui.small_button("Clear##salvage_keep_clear_%s_%s" % (category, group_id)):
            selected.difference_update(internal for _display, internal in entries)
        for subgroup, subgroup_entries in curated.entry_groups(entries):
            if subgroup:
                subgroup_id = "%s_%s" % (group_id, subgroup)
                subgroup_count = sum(1 for _display, internal in subgroup_entries if internal in selected)
                if not PyImGui.tree_node(
                    "%s (%d/%d)###salvage_keep_%s_%s"
                    % (
                        subgroup,
                        subgroup_count,
                        len(subgroup_entries),
                        category,
                        subgroup_id,
                    )
                ):
                    continue
            for display, internal in subgroup_entries:
                on = internal in selected
                picked = (
                    _colored_checkbox(display, on, entry_color, "salvage_keep_%s" % internal)
                    if entry_color is not None
                    else PyImGui.checkbox("%s##salvage_keep_%s" % (display, internal), on)
                )
                if picked != on:
                    if picked:
                        selected.add(internal)
                    else:
                        selected.discard(internal)
            if subgroup:
                PyImGui.tree_pop()
        PyImGui.tree_pop()
    _state["selected_upgrades"] = selected


def _draw_item_type_tree() -> None:
    PyImGui.text_wrapped(
        "Keep every item of a selected concrete type, such as every Shield or every Axe. "
        "These are generic item filters and do not require a named upgrade."
    )
    selected = set(int(value) for value in _state.get("selected_item_types", set()))
    weapon_values = {item_type for _display, item_type in curated.weapon_types()}
    for group, entries in curated.item_type_groups():
        group_id = group.replace(" ", "_").replace("&", "and")
        ids = {item_type for _display, item_type in entries}
        count = sum(1 for item_type in ids if item_type in selected)
        if not PyImGui.tree_node(
            "%s (%d/%d)###salvage_item_types_%s" % (group, count, len(ids), group_id)
        ):
            continue
        if PyImGui.small_button("Select all##salvage_item_types_all_%s" % group_id):
            selected.update(ids)
        PyImGui.same_line(0, 6)
        if PyImGui.small_button("Clear##salvage_item_types_clear_%s" % group_id):
            selected.difference_update(ids)
        for display, item_type in entries:
            on = item_type in selected
            picked = PyImGui.checkbox(
                "%s##salvage_item_type_%s_%d" % (display, group_id, item_type),
                on,
            )
            if picked != on:
                if picked:
                    selected.add(item_type)
                else:
                    selected.discard(item_type)
        PyImGui.tree_pop()

    selected_weapon_types = selected.intersection(weapon_values)
    if selected_weapon_types:
        PyImGui.separator()
        requirement_enabled = bool(_state.get("item_requirement_enabled", False))
        picked_requirement_enabled = PyImGui.checkbox(
            "Limit selected weapon types by requirement##salvage_item_requirement_enabled",
            requirement_enabled,
        )
        if picked_requirement_enabled != requirement_enabled:
            _state["item_requirement_enabled"] = picked_requirement_enabled
            requirement_enabled = picked_requirement_enabled
        if requirement_enabled:
            max_requirement = int(_state.get("item_max_requirement", 9))
            PyImGui.same_line(0, 6)
            PyImGui.push_item_width(120)
            max_requirement = PyImGui.slider_int(
                "Requirement at most##salvage_item_max_requirement",
                max_requirement,
                0,
                13,
            )
            PyImGui.pop_item_width()
            _state["item_max_requirement"] = max(0, min(13, int(max_requirement)))
            PyImGui.text_wrapped(
                "Lower requirements are better. For example, 8 keeps selected weapon types at "
                "requirement 8 and lower."
            )
        else:
            PyImGui.text_wrapped(
                "Requirement filtering is off. Selected weapon types are kept at every requirement."
            )
    else:
        PyImGui.text_wrapped(
            "Requirement filtering is available when at least one weapon type is selected."
        )
    _state["selected_item_types"] = selected


def _draw_weapon_mod_tree() -> None:
    PyImGui.text_wrapped(
        "Choose upgrades under the weapon and component where they spawn. "
        "Prefixes, suffixes, and inscriptions are grouped here. Each selected entry becomes "
        "a filter for that specific weapon type."
    )
    selected = set(tuple(value) for value in _state.get("selected_weapon_mods", set()))
    for weapon, components in curated.grouped_weapon_mods():
        weapon_id = weapon.replace(" ", "_")
        all_entries = [entry for _component, entries in components for entry in entries]
        keys = {(weapon, internal) for _display, internal in all_entries}
        count = sum(1 for key in keys if key in selected)
        if not PyImGui.tree_node(
            "%s (%d/%d)###salvage_weapon_mods_%s" % (weapon, count, len(keys), weapon_id)
        ):
            continue
        if PyImGui.small_button("Select all##salvage_weapon_mods_all_%s" % weapon_id):
            selected.update(keys)
        PyImGui.same_line(0, 6)
        if PyImGui.small_button("Clear##salvage_weapon_mods_clear_%s" % weapon_id):
            selected.difference_update(keys)
        for component, entries in components:
            component_id = "%s_%s" % (weapon_id, component.replace(" ", "_"))
            if not PyImGui.tree_node(
                "%s (%d/%d)###salvage_weapon_component_%s" % (
                    component,
                    sum(1 for _display, internal in entries if (weapon, internal) in selected),
                    len(entries),
                    component_id,
                )
            ):
                continue
            for subgroup, subgroup_entries in curated.entry_groups(entries):
                if subgroup:
                    subgroup_id = "%s_%s" % (component_id, subgroup)
                    if not PyImGui.tree_node(
                        "%s###salvage_weapon_mods_subgroup_%s" % (subgroup, subgroup_id)
                    ):
                        continue
                for display, internal in subgroup_entries:
                    key = (weapon, internal)
                    on = key in selected
                    picked = PyImGui.checkbox("%s##salvage_weapon_mod_%s_%s" % (display, weapon_id, internal), on)
                    if picked != on:
                        if picked:
                            selected.add(key)
                        else:
                            selected.discard(key)
                if subgroup:
                    PyImGui.tree_pop()
            PyImGui.tree_pop()
        PyImGui.tree_pop()
    _state["selected_weapon_mods"] = selected


def _rune_color(rarity: str):
    return ColorPalette.GetColor(
        {
            "Superior": "Markdown_Gold",
            "Major": "Markdown_Purple",
            "Minor": "Markdown_Blue",
            "General": "Markdown_White",
        }.get(rarity, "Markdown_White")
    ).to_tuple_normalized()


def _profession_color(profession: str):
    palette_name = "GW_%s" % profession if profession not in ("General", "Common") else "GW_White"
    return ColorPalette.GetColor(palette_name).to_tuple_normalized()


def _colored_tree_node(label: str, color, node_id: str) -> bool:
    PyImGui.push_style_color(PyImGui.ImGuiCol.Text, color)
    try:
        return PyImGui.tree_node("%s###%s" % (label, node_id))
    finally:
        PyImGui.pop_style_color(1)


def _colored_checkbox(label: str, value: bool, color, checkbox_id: str) -> bool:
    PyImGui.push_style_color(PyImGui.ImGuiCol.Text, color)
    try:
        return PyImGui.checkbox("%s##%s" % (label, checkbox_id), value)
    finally:
        PyImGui.pop_style_color(1)


def _draw_rune_tree() -> None:
    selected = set(str(value) for value in _state.get("selected_upgrades", set()))

    def draw_entries(entries, rarity: str) -> None:
        color = _rune_color(rarity)
        for display, internal in entries:
            on = internal in selected
            picked = _colored_checkbox(display, on, color, "salvage_rune_%s" % internal)
            if picked != on:
                if picked:
                    selected.add(internal)
                else:
                    selected.discard(internal)

    for profession, rune_types in curated.grouped_runes():
        profession_id = profession.replace(" ", "_")
        profession_count = sum(
            1
            for _rune_type_name, rarities in rune_types
            for _rarity, entries in rarities
            for _display, internal in entries
            if internal in selected
        )
        profession_total = sum(len(entries) for _rune_type_name, rarities in rune_types for _rarity, entries in rarities)
        if not _colored_tree_node(
            "%s (%d/%d)" % (profession, profession_count, profession_total),
            _profession_color(profession),
            "salvage_runes_profession_%s" % profession_id,
        ):
            continue
        for rune_type, rarities in rune_types:
            rune_type_id = "%s_%s" % (profession_id, rune_type.replace(" ", "_"))
            rune_type_entries = [entry for _rarity, entries in rarities for entry in entries]
            rune_type_count = sum(1 for _display, internal in rune_type_entries if internal in selected)
            if not PyImGui.tree_node(
                "%s (%d/%d)###salvage_runes_type_%s" % (rune_type, rune_type_count, len(rune_type_entries), rune_type_id)
            ):
                continue
            if PyImGui.small_button("Select all##salvage_runes_all_%s" % rune_type_id):
                selected.update(internal for _display, internal in rune_type_entries)
            PyImGui.same_line(0, 6)
            if PyImGui.small_button("Clear##salvage_runes_clear_%s" % rune_type_id):
                selected.difference_update(internal for _display, internal in rune_type_entries)
            if len(rarities) == 1:
                rarity, entries = rarities[0]
                draw_entries(entries, rarity)
            else:
                for rarity, entries in rarities:
                    rarity_id = "%s_%s" % (rune_type_id, rarity)
                    rarity_count = sum(1 for _display, internal in entries if internal in selected)
                    if not _colored_tree_node(
                        "%s (%d/%d)" % (rarity, rarity_count, len(entries)),
                        _rune_color(rarity),
                        "salvage_runes_rarity_%s" % rarity_id,
                    ):
                        continue
                    draw_entries(entries, rarity)
                    PyImGui.tree_pop()
            PyImGui.tree_pop()
        PyImGui.tree_pop()
    _state["selected_upgrades"] = selected


def _draw_model_keep_tab() -> None:
    PyImGui.text_wrapped(
        "Use this for a specific weapon skin or model. The current repository has no verified "
        "price catalogue, so model IDs are intentionally explicit rather than pretending every "
        "rare-looking name is valuable."
    )
    typed = PyImGui.input_text("Model ID(s), comma separated##salvage_model_ids", str(_state.get("model_ids", "")))
    _state["model_ids"] = typed
    model_ids: list[int] = []
    for value in typed.split(","):
        try:
            model_id = int(value.strip())
        except ValueError:
            continue
        if model_id > 0:
            model_ids.append(model_id)
    if PyImGui.button("Keep these model IDs##salvage_model_add") and model_ids:
        selected = set(int(value) for value in _state.get("selected_model_ids", set()))
        selected.update(model_ids)
        _state["selected_model_ids"] = selected
        _state["model_ids"] = ""
    selected_model_ids = sorted(int(value) for value in _state.get("selected_model_ids", set()))
    if selected_model_ids:
        PyImGui.text("Kept model IDs: %s" % ", ".join(str(value) for value in selected_model_ids))


def _draw_curated(controller: SalvageController) -> None:
    """Direct, account-owned checkbox state for the guided Keep Lists."""
    keep_list = store.load_keep_list()
    _state["selected_upgrades"] = set(keep_list.upgrades)
    _state["selected_weapon_mods"] = set(keep_list.weapon_mods)
    _state["selected_item_types"] = set(keep_list.item_types)
    _state["selected_model_ids"] = set(keep_list.model_ids)
    _state["item_requirement_enabled"] = keep_list.item_requirement_enabled
    _state["item_max_requirement"] = keep_list.item_max_requirement
    active_rules = controller.curated_keep_filters()
    PyImGui.text("Keep List (%d active checkbox rule(s))" % len(active_rules))
    if active_rules:
        PyImGui.text_colored(
            "Each checked entry is saved immediately and protects matching items immediately. "
            "Use Diagnostics to review the complete resolved rule list.",
            GOOD,
        )
    else:
        PyImGui.text_colored(
            "No active Keep List rules. Automatic material salvage has nothing to exclude.",
            WARN,
        )
    PyImGui.separator()
    PyImGui.text("Keep List checkboxes")
    PyImGui.text_wrapped(
        "Tick or untick an entry and it is saved immediately. Named upgrades are extracted only with an "
        "Expert-or-better kit; every other matching Keep List entry preserves the complete item."
    )
    if PyImGui.begin_tab_bar("salvage_keep_category_tabs"):
        for category, label in (
            ("Runes", "Runes"),
            ("Insignias", "Insignias"),
            ("Item Types", "Item Types"),
            ("Weapon Mods", "Weapon Mods"),
            ("Models", "Models / Skins"),
        ):
            if not PyImGui.begin_tab_item(label + "##salvage_keep_tab"):
                continue
            if category == "Models":
                _draw_model_keep_tab()
            elif category == "Runes":
                _draw_rune_tree()
            elif category == "Insignias":
                _draw_upgrade_tree("Insignias", color_groups=True, entry_color=_rune_color("Minor"))
            elif category == "Item Types":
                _draw_item_type_tree()
            elif category == "Weapon Mods":
                _draw_weapon_mod_tree()
            else:
                _draw_upgrade_tree(category)
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()

    updated_keep_list = CuratedKeepList(
        upgrades=set(str(value) for value in _state.get("selected_upgrades", set())),
        weapon_mods=set((str(weapon), str(name)) for weapon, name in _state.get("selected_weapon_mods", set())),
        item_types=set(int(value) for value in _state.get("selected_item_types", set())),
        item_requirement_enabled=bool(_state.get("item_requirement_enabled", False)),
        item_max_requirement=int(_state.get("item_max_requirement", 9)),
        model_ids=set(int(value) for value in _state.get("selected_model_ids", set())),
    )
    if updated_keep_list != keep_list:
        store.save_keep_list(updated_keep_list)


def _criteria_filter(filter_definition: Filter) -> Filter:
    return replace(filter_definition, id="salvage_%s" % filter_definition.id)


def _draw_filters() -> None:
    current = store.load_filters()
    if PyImGui.button("New filter##salvage_new_filter"):
        current.append(Filter(id=store.next_filter_id(current), name="Filter %d" % (len(current) + 1)))
        store.save_filters(current)
        return
    PyImGui.same_line(0, 8)
    PyImGui.text_colored("%d private Salvage filter(s)" % len(current), MUTED)
    PyImGui.text_wrapped(
        "These filters belong only to Salvage. They use the complete current Item.Mods criteria: "
        "item fields, inherent effects, named upgrades, slot checks, and maxed checks."
    )
    PyImGui.separator()
    if not current:
        PyImGui.text_colored("None yet. Create one above or use Keep Lists.", MUTED)
        return
    for index, filter_definition in enumerate(list(current)):
        enabled = PyImGui.checkbox("##salvage_filter_enabled_%s" % filter_definition.id, filter_definition.enabled)
        if enabled != filter_definition.enabled:
            current[index] = filter_definition.with_enabled(enabled)
            store.save_filters(current)
            return
        PyImGui.same_line(0, 6)
        if not PyImGui.collapsing_header(
            "%d. %s###salvage_filter_header_%s" % (index + 1, filter_definition.name, filter_definition.id)
        ):
            continue
        typed = PyImGui.input_text("Name##salvage_filter_name_%s" % filter_definition.id, filter_definition.name)
        if typed != filter_definition.name and typed.strip():
            current[index] = filter_definition.renamed(typed.strip())
            store.save_filters(current)
            return
        edited = criteria_ui._draw_criteria(_criteria_filter(filter_definition), index)
        if edited is not None:
            current[index] = replace(edited, id=filter_definition.id)
            store.save_filters(current)
            return
        if filter_definition.is_empty():
            PyImGui.text_colored("No conditions set - this filter matches nothing.", WARN)
        PyImGui.separator()
        criteria_ui._draw_preview(_criteria_filter(filter_definition))
        PyImGui.separator()
        if PyImGui.small_button("Duplicate##salvage_filter_duplicate_%s" % filter_definition.id):
            current.insert(
                index + 1,
                Filter.from_dict(
                    {
                        **filter_definition.to_dict(),
                        "id": store.next_filter_id(current),
                        "name": filter_definition.name + " (copy)",
                    }
                ),
            )
            store.save_filters(current)
            return
        PyImGui.same_line(0, 6)
        if PyImGui.small_button("Delete##salvage_filter_delete_%s" % filter_definition.id):
            current.pop(index)
            sets = store.load_filter_sets()
            store.save_filters(current)
            store.save_filter_sets(
                [
                    FilterSet(
                        entry.id,
                        entry.name,
                        tuple(filter_id for filter_id in entry.filter_ids if filter_id != filter_definition.id),
                    )
                    for entry in sets
                ]
            )
            return


def _draw_filter_sets(controller: SalvageController) -> None:
    current = store.load_filter_sets()
    all_filters = store.load_filters()
    PyImGui.text_wrapped(
        "Advanced Salvage filter sets are separate from the checkbox Keep Lists. A matching advanced filter protects "
        "its item from material salvage; named upgrade filters may use Expert-or-better extraction."
    )
    PyImGui.separator()
    typed = PyImGui.input_text("##salvage_new_filter_set", str(_state.get("new_filter_set", "")))
    _state["new_filter_set"] = typed
    PyImGui.same_line(0, 6)
    if PyImGui.button("New filter set##salvage_add_filter_set"):
        name = typed.strip()
        if name and not store.filter_set_by_name(current, name):
            current.append(FilterSet(id=store.next_filter_set_id(current), name=name))
            _state["new_filter_set"] = ""
            store.save_filter_sets(current)
            return
    PyImGui.separator()
    for index, filter_set in enumerate(list(current)):
        if not PyImGui.collapsing_header(
            "%s (%d)###salvage_set_%s" % (filter_set.name, len(filter_set.filter_ids), filter_set.id)
        ):
            continue
        name = PyImGui.input_text("Name##salvage_set_name_%s" % filter_set.id, filter_set.name)
        if name != filter_set.name and name.strip():
            current[index] = FilterSet(filter_set.id, name.strip(), filter_set.filter_ids)
            store.save_filter_sets(current)
            return
        chosen = filter_set.filter_ids
        for filter_definition in all_filters:
            on = filter_definition.id in chosen
            picked = PyImGui.checkbox(
                "%s##salvage_set_member_%s_%s" % (filter_definition.name, filter_set.id, filter_definition.id), on
            )
            if picked != on:
                chosen = (
                    tuple(value for value in chosen if value != filter_definition.id)
                    if on
                    else chosen + (filter_definition.id,)
                )
                current[index] = FilterSet(filter_set.id, filter_set.name, chosen)
                store.save_filter_sets(current)
                return
        if PyImGui.small_button("Delete##salvage_set_delete_%s" % filter_set.id):
            current.pop(index)
            if controller.settings().filter_set_id == filter_set.id:
                controller.settings().filter_set_id = ""
                controller.save_settings()
            store.save_filter_sets(current)
            return


def _draw_diagnostics(controller: SalvageController) -> None:
    settings = controller.settings()
    active_rules = controller.active_filters()
    PyImGui.text("Salvage Diagnostics")
    PyImGui.text_wrapped(
        "This is a read-only assessment of future automatic Salvage decisions. Refresh it before enabling "
        "automatic Salvage to verify the action and kit selected for every item in the configured Bags scope. "
        "It never starts a BT node, sends an inventory action, or changes timer state."
    )
    PyImGui.separator()
    PyImGui.text("Live policy")
    PyImGui.text(
        "Automatic: %s | Common materials: %s | Rare materials: %s | Extract matching upgrades: %s"
        % (
            "on" if settings.enabled else "off",
            "on" if settings.salvage_common_materials else "off",
            "on" if settings.salvage_rare_materials else "off",
            "on" if settings.salvage_matching_upgrades else "off",
        )
    )
    PyImGui.text("Active advanced filter set: %s" % (settings.filter_set_id or "(none)"))
    if active_rules:
        PyImGui.text_colored("Active rules enforced by automatic Salvage:", GOOD)
        for filter_definition in active_rules:
            PyImGui.text("- %s" % filter_definition.name)
    else:
        PyImGui.text_colored("No active Keep List rules; nothing is excluded by a keep rule.", WARN)
    PyImGui.separator()
    PyImGui.text("Future-action assessment")
    PyImGui.text_wrapped(
        "The table reports the actual future decision: keep, extract a matching upgrade, salvage for materials, "
        "or skip. The chosen kit is shown beside the action. It is unavailable while a map is loading or not stable."
    )
    assessment_label = (
        "Pause automatic Salvage and resolve targets##salvage_preview_refresh"
        if settings.enabled
        else "Resolve and mark salvage targets##salvage_preview_refresh"
    )
    if settings.enabled:
        PyImGui.text_colored(
            "Resolving targets pauses automatic Salvage first; you must explicitly enable it again afterwards.",
            WARN,
        )
    if PyImGui.button(assessment_label):
        if settings.enabled:
            settings.enabled = False
            controller.save_settings()
        _state["salvage_preview"] = controller.preview()
    preview = _state.get("salvage_preview")
    if preview is not None:
        ready, message, rows = preview
        PyImGui.text_colored(message, GOOD if ready else WARN)
        targets = [row for row in rows if row["mode"]]
        if ready:
            if targets:
                PyImGui.text_colored(
                    "Resolved salvage targets: %d. Open inventory or bags to see their marks." % len(targets),
                    WARN,
                )
                PyImGui.text_colored(
                    "Red = common materials | Purple = rare materials | Gold = matching upgrade extraction",
                    MUTED,
                )
            else:
                PyImGui.text_colored("Resolved salvage targets: 0. Nothing will be salvaged by this snapshot.", GOOD)
        if PyImGui.button("Clear visual target marks##salvage_preview_clear"):
            controller.clear_preview_targets()
            _state["salvage_preview"] = None
            return
        if ready and rows:
            if PyImGui.begin_table("##salvage_preview", 6, PyImGui.TableFlags.RowBg | PyImGui.TableFlags.Borders):
                for heading in ("Location", "Item", "Rarity", "Keep rule(s)", "Proposed action", "Kit"):
                    PyImGui.table_setup_column(heading)
                PyImGui.table_headers_row()
                for row in rows:
                    PyImGui.table_next_row()
                    PyImGui.table_next_column()
                    PyImGui.text("%s:%d" % (row["bag"], row["slot"]))
                    PyImGui.table_next_column()
                    PyImGui.text("%d / model %d" % (row["item_id"], row["model_id"]))
                    PyImGui.table_next_column()
                    PyImGui.text(str(row["rarity"]))
                    PyImGui.table_next_column()
                    PyImGui.text(", ".join(row["rules"]) if row["rules"] else "-")
                    PyImGui.table_next_column()
                    action = str(row["decision"])
                    PyImGui.text_colored(action, GOOD if action.startswith("KEEP") else WARN if action.startswith("Skip") else MUTED)
                    PyImGui.table_next_column()
                    PyImGui.text(str(row["kit"]))
                PyImGui.end_table()
        elif ready:
            PyImGui.text_colored("No items are currently visible in the configured Bags scope.", MUTED)
    PyImGui.separator()
    PyImGui.text("Optional BT console trace")
    debug_enabled = PyImGui.checkbox(
        "Enable Salvage debug logging##salvage_debug_enabled",
        settings.debug_enabled,
    )
    if debug_enabled != settings.debug_enabled:
        settings.debug_enabled = debug_enabled
        controller.save_settings()
    PyImGui.text_wrapped(
        "This only adds BT execution messages to the Py4GW console. It does not affect selection, timing, "
        "dialogs, or salvage behavior."
    )
    if PyImGui.button("Dump current Salvage diagnostics##salvage_dump_diagnostics"):
        controller.dump_diagnostics()
    PyImGui.same_line(0, 8)
    PyImGui.text_colored("Inspect entries tagged TEST_SLOT, KIT, and BT_RESOLUTION in the console.", MUTED)
    status = controller.status()
    if status:
        PyImGui.separator()
        PyImGui.text_colored(
            status, GOOD if "failed" not in status.lower() and "timed out" not in status.lower() else WARN
        )


def add_sections(win, group) -> None:
    controller = get_controller()
    win.add_account_section(group, "items.salvage", "Salvage")
    win.add_tab("Salvage", "General", lambda c=controller: _draw_general(c))
    win.add_tab("Salvage", "Keep Lists", lambda c=controller: _draw_curated(c))
    win.add_tab("Salvage", "Filters", _draw_filters)
    win.add_tab("Salvage", "Filter Sets", lambda c=controller: _draw_filter_sets(c))
    win.add_tab("Salvage", "Diagnostics", lambda c=controller: _draw_diagnostics(c))
