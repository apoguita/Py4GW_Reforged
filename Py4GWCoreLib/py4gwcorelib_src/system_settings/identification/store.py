"""Per-account persistence for Identification and its private filter definitions.

Identification owns its filter and filter-set records. They intentionally do not read or write the
Loot Filter Factory pool. Legacy AutoInventory/InventoryPlus identification values are not read here.
"""

from ..loot_filter_factory.model import Filter, FilterSet
from .model import IdentificationSettings


_INI = "Widgets/System/Identification.ini"
FILTERS_DOCUMENT = "Widgets/System/IdentificationFilters.json"


def _json():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory

        return JsonFactory(FILTERS_DOCUMENT, "account")
    except Exception:
        return None


def _settings():
    try:
        from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

        return Settings(_INI, "account")
    except Exception:
        return None


def load() -> IdentificationSettings:
    settings = _settings()
    if settings is None:
        return IdentificationSettings()
    return IdentificationSettings(
        enabled=settings.get_bool("general", "enabled", False),
        id_whites=settings.get_bool("rarity", "white", False),
        id_blues=settings.get_bool("rarity", "blue", True),
        id_purples=settings.get_bool("rarity", "purple", True),
        id_golds=settings.get_bool("rarity", "gold", True),
        prefer_infinite_id_kit=settings.get_bool("general", "prefer_infinite_kit", False),
        filter_set_id=settings.get_str("general", "filter_set", ""),
    )


def save(config: IdentificationSettings) -> None:
    settings = _settings()
    if settings is None:
        return
    settings.set("general", "enabled", bool(config.enabled))
    settings.set("general", "filter_set", str(config.filter_set_id))
    settings.set("general", "prefer_infinite_kit", bool(config.prefer_infinite_id_kit))
    settings.set("rarity", "white", bool(config.id_whites))
    settings.set("rarity", "blue", bool(config.id_blues))
    settings.set("rarity", "purple", bool(config.id_purples))
    settings.set("rarity", "gold", bool(config.id_golds))


def load_filters() -> list[Filter]:
    document = _json()
    raw = document.get_json("filters", []) if document is not None else []
    if not isinstance(raw, list):
        return []
    output: list[Filter] = []
    for entry in raw:
        if isinstance(entry, dict):
            try:
                output.append(Filter.from_dict(entry))
            except Exception:
                continue
    return output


def save_filters(filters: list[Filter]) -> None:
    document = _json()
    if document is not None:
        document.set_json("filters", [filter_definition.to_dict() for filter_definition in filters])


def load_filter_sets() -> list[FilterSet]:
    document = _json()
    raw = document.get_json("filter_sets", []) if document is not None else []
    if not isinstance(raw, list):
        return []
    output: list[FilterSet] = []
    for entry in raw:
        if isinstance(entry, dict):
            try:
                output.append(FilterSet.from_dict(entry))
            except Exception:
                continue
    return output


def save_filter_sets(filter_sets: list[FilterSet]) -> None:
    document = _json()
    if document is not None:
        document.set_json("filter_sets", [filter_set.to_dict() for filter_set in filter_sets])


def next_filter_id(filters: list[Filter]) -> str:
    taken = {filter_definition.id for filter_definition in filters}
    index = 1
    while "id_filter_%d" % index in taken:
        index += 1
    return "id_filter_%d" % index


def next_filter_set_id(filter_sets: list[FilterSet]) -> str:
    taken = {filter_set.id for filter_set in filter_sets}
    index = 1
    while "id_set_%d" % index in taken:
        index += 1
    return "id_set_%d" % index


def filter_set_by_name(filter_sets: list[FilterSet], name: str) -> FilterSet | None:
    return next((filter_set for filter_set in filter_sets if filter_set.name == name), None)


def filter_set_by_id(filter_sets: list[FilterSet], filter_set_id: str) -> FilterSet | None:
    return next((filter_set for filter_set in filter_sets if filter_set.id == filter_set_id), None)


def filters_in_set(filters: list[Filter], filter_set: FilterSet | None) -> list[Filter]:
    if filter_set is None:
        return []
    index = {filter_definition.id: filter_definition for filter_definition in filters}
    return [index[filter_id] for filter_id in filter_set.filter_ids if filter_id in index]
