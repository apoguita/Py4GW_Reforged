"""Account-owned Salvage settings and private filter definitions."""

from ..loot_filter_factory.model import Filter, FilterSet
from .model import CuratedKeepList, SalvageSettings


_INI = "Widgets/System/Salvage.ini"
FILTERS_DOCUMENT = "Widgets/System/SalvageFilters.json"
KEEP_LIST_DOCUMENT = "Widgets/System/SalvageKeepList.json"


def _json():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory

        return JsonFactory(FILTERS_DOCUMENT, "account")
    except Exception:
        return None


def _keep_list_json():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory

        return JsonFactory(KEEP_LIST_DOCUMENT, "account")
    except Exception:
        return None


def _settings():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_INI, "account")
    except Exception:
        return None


def load() -> SalvageSettings:
    settings = _settings()
    if settings is None:
        return SalvageSettings()
    return SalvageSettings(
        enabled=settings.get_bool("general", "enabled", False),
        filter_set_id=settings.get_str("general", "filter_set", ""),
        salvage_whites=settings.get_bool("rarity", "white", False),
        salvage_blues=settings.get_bool("rarity", "blue", False),
        salvage_purples=settings.get_bool("rarity", "purple", False),
        salvage_golds=settings.get_bool("rarity", "gold", False),
        salvage_common_materials=settings.get_bool("actions", "common_materials", True),
        salvage_rare_materials=settings.get_bool("actions", "rare_materials", False),
        salvage_matching_upgrades=settings.get_bool("actions", "matching_upgrades", True),
        auto_confirm_materials_warning=settings.get_bool("actions", "auto_confirm_warning", False),
        prefer_infinite_salvage_kit=settings.get_bool("actions", "prefer_infinite_kit", False),
        debug_enabled=settings.get_bool("debug", "enabled", False),
    )


def save(config: SalvageSettings) -> None:
    settings = _settings()
    if settings is None:
        return
    settings.set("general", "enabled", bool(config.enabled))
    settings.set("general", "filter_set", str(config.filter_set_id))
    settings.set("rarity", "white", bool(config.salvage_whites))
    settings.set("rarity", "blue", bool(config.salvage_blues))
    settings.set("rarity", "purple", bool(config.salvage_purples))
    settings.set("rarity", "gold", bool(config.salvage_golds))
    settings.set("actions", "common_materials", bool(config.salvage_common_materials))
    settings.set("actions", "rare_materials", bool(config.salvage_rare_materials))
    settings.set("actions", "matching_upgrades", bool(config.salvage_matching_upgrades))
    settings.set("actions", "auto_confirm_warning", bool(config.auto_confirm_materials_warning))
    settings.set("actions", "prefer_infinite_kit", bool(config.prefer_infinite_salvage_kit))
    settings.set("debug", "enabled", bool(config.debug_enabled))


def _load_list(key: str) -> list[dict]:
    document = _json()
    raw = document.get_json(key, []) if document is not None else []
    return [entry for entry in raw if isinstance(entry, dict)] if isinstance(raw, list) else []


def load_filters() -> list[Filter]:
    output: list[Filter] = []
    for entry in _load_list("filters"):
        try:
            output.append(Filter.from_dict(entry))
        except Exception:
            continue
    return output


def save_filters(filters: list[Filter]) -> None:
    document = _json()
    if document is not None:
        document.set_json("filters", [entry.to_dict() for entry in filters])


def load_filter_sets() -> list[FilterSet]:
    output: list[FilterSet] = []
    for entry in _load_list("filter_sets"):
        try:
            output.append(FilterSet.from_dict(entry))
        except Exception:
            continue
    return output


def save_filter_sets(filter_sets: list[FilterSet]) -> None:
    document = _json()
    if document is not None:
        document.set_json("filter_sets", [entry.to_dict() for entry in filter_sets])


def load_keep_list() -> CuratedKeepList:
    document = _keep_list_json()
    return CuratedKeepList.from_dict(document.get_json("keep_list", {}) if document is not None else {})


def save_keep_list(keep_list: CuratedKeepList) -> None:
    document = _keep_list_json()
    if document is not None:
        document.set_json("keep_list", keep_list.to_dict())


def migrate_legacy_keep_filters() -> int:
    """Import only the former Keep List UI's generated filters into direct checkbox state."""
    from . import curated

    keep_list = load_keep_list()
    filters = load_filters()
    active_filter_ids = {filter_id for entry in load_filter_sets() for filter_id in entry.filter_ids}
    upgrade_display_names = {
        internal: display
        for _category, entries in curated.upgrade_groups()
        for display, internal in entries
    }
    weapon_types = dict(curated.weapon_types())
    weapon_type_names = {item_type: name for name, item_type in weapon_types.items()}
    item_type_names = {
        item_type: name
        for _group, entries in curated.item_type_groups()
        for name, item_type in entries
    }
    migrated_ids: set[str] = set()
    for filter_definition in filters:
        if (
            filter_definition.id not in active_filter_ids
            or filter_definition.mode != "all"
            or not filter_definition.name.startswith("Keep ")
        ):
            continue
        if (
            len(filter_definition.upgrades) == 1
            and not filter_definition.item_types
            and not filter_definition.model_ids
            and filter_definition.upgrades[0].name in upgrade_display_names
            and filter_definition.name == "Keep %s" % upgrade_display_names[filter_definition.upgrades[0].name]
        ):
            keep_list.upgrades.add(filter_definition.upgrades[0].name)
            migrated_ids.add(filter_definition.id)
        elif (
            len(filter_definition.upgrades) == 1
            and len(filter_definition.item_types) == 1
            and not filter_definition.model_ids
            and filter_definition.item_types[0] in weapon_type_names
            and filter_definition.upgrades[0].name in upgrade_display_names
            and filter_definition.name == "Keep %s on %s" % (
                upgrade_display_names[filter_definition.upgrades[0].name],
                weapon_type_names[filter_definition.item_types[0]],
            )
        ):
            # Weapon names are reconstructed at runtime from the item type; persist only the stable type and upgrade.
            keep_list.weapon_mods.add((str(filter_definition.item_types[0]), filter_definition.upgrades[0].name))
            migrated_ids.add(filter_definition.id)
        elif (
            len(filter_definition.item_types) == 1
            and not filter_definition.upgrades
            and not filter_definition.model_ids
            and filter_definition.item_types[0] in item_type_names
            and filter_definition.name == "Keep all %s" % item_type_names[filter_definition.item_types[0]]
        ):
            keep_list.item_types.add(filter_definition.item_types[0])
            if filter_definition.max_requirement is not None and filter_definition.item_types[0] in weapon_type_names:
                keep_list.item_requirement_enabled = True
                keep_list.item_max_requirement = filter_definition.max_requirement
            migrated_ids.add(filter_definition.id)
        elif (
            filter_definition.model_ids
            and not filter_definition.upgrades
            and not filter_definition.item_types
            and filter_definition.name.startswith("Keep model")
        ):
            keep_list.model_ids.update(filter_definition.model_ids)
            migrated_ids.add(filter_definition.id)
    if not migrated_ids:
        return 0
    save_keep_list(keep_list)
    save_filters([entry for entry in filters if entry.id not in migrated_ids])
    save_filter_sets([
        FilterSet(entry.id, entry.name, tuple(filter_id for filter_id in entry.filter_ids if filter_id not in migrated_ids))
        for entry in load_filter_sets()
    ])
    return len(migrated_ids)


def next_filter_id(filters: list[Filter]) -> str:
    taken = {entry.id for entry in filters}
    index = 1
    while "salvage_filter_%d" % index in taken:
        index += 1
    return "salvage_filter_%d" % index


def next_filter_set_id(filter_sets: list[FilterSet]) -> str:
    taken = {entry.id for entry in filter_sets}
    index = 1
    while "salvage_set_%d" % index in taken:
        index += 1
    return "salvage_set_%d" % index


def filter_set_by_name(filter_sets: list[FilterSet], name: str) -> FilterSet | None:
    return next((entry for entry in filter_sets if entry.name == name), None)


def filter_set_by_id(filter_sets: list[FilterSet], filter_set_id: str) -> FilterSet | None:
    return next((entry for entry in filter_sets if entry.id == filter_set_id), None)


def filters_in_set(filters: list[Filter], filter_set: FilterSet | None) -> list[Filter]:
    if filter_set is None:
        return []
    index = {entry.id: entry for entry in filters}
    return [index[filter_id] for filter_id in filter_set.filter_ids if filter_id in index]
