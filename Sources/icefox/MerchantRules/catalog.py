from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast
from urllib.parse import unquote

from Py4GWCoreLib.enums_src.Item_enums import ItemType
from Py4GWCoreLib.enums_src.Model_enums import ModelID


MODEL_ID_FALLBACK_ITEM_TYPE_SUFFIXES: tuple[tuple[str, str], ...] = (
    ('Daggers', 'Daggers'),
    ('Scythe', 'Scythe'),
    ('Shield', 'Shield'),
    ('Spear', 'Spear'),
    ('Staff', 'Staff'),
    ('Sword', 'Sword'),
    ('Hammer', 'Hammer'),
    ('Focus', 'Offhand'),
    ('Offhand', 'Offhand'),
    ('Icon', 'Offhand'),
    ('Prism', 'Offhand'),
    ('Wand', 'Wand'),
    ('Bow', 'Bow'),
    ('Axe', 'Axe'),
    ('Headpiece', 'Headpiece'),
    ('Chestpiece', 'Chestpiece'),
    ('Gloves', 'Gloves'),
    ('Leggings', 'Leggings'),
    ('Boots', 'Boots'),
    ('SalvageKit', 'Salvage'),
)

WEAPON_MOD_CHOICE_KIND_GENERIC = 'generic'
WEAPON_MOD_CHOICE_KIND_VARIANT = 'variant'
WEAPON_MOD_GENERIC_KEY_PREFIX = 'identifier:'
WEAPON_MOD_VARIANT_KEY_PREFIX = 'variant:'
WEAPON_MOD_CHOICE_SEPARATOR = '|'

MODIFIER_IDENTIFIER_RUNE_ATTRIBUTE = 8680
RUNE_ATTRIBUTE_LABELS: dict[int, str] = {
    0: 'Fast Casting',
    1: 'Illusion Magic',
    2: 'Domination Magic',
    3: 'Inspiration Magic',
    4: 'Blood Magic',
    5: 'Death Magic',
    6: 'Soul Reaping',
    7: 'Curses',
    8: 'Air Magic',
    9: 'Earth Magic',
    10: 'Fire Magic',
    11: 'Water Magic',
    12: 'Energy Storage',
    13: 'Healing Prayers',
    14: 'Smiting Prayers',
    15: 'Protection Prayers',
    16: 'Divine Favor',
    17: 'Strength',
    18: 'Axe Mastery',
    19: 'Hammer Mastery',
    20: 'Swordsmanship',
    21: 'Tactics',
    22: 'Beast Mastery',
    23: 'Expertise',
    24: 'Wilderness Survival',
    25: 'Marksmanship',
    29: 'Dagger Mastery',
    30: 'Deadly Arts',
    31: 'Shadow Arts',
    32: 'Communing',
    33: 'Restoration Magic',
    34: 'Channeling Magic',
    35: 'Critical Strikes',
    36: 'Spawning Power',
    37: 'Spear Mastery',
    38: 'Command',
    39: 'Motivation',
    40: 'Leadership',
    41: 'Scythe Mastery',
    42: 'Wind Prayers',
    43: 'Earth Prayers',
    44: 'Mysticism',
}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        if isinstance(value, str):
            return int(value.strip(), 0)
        return int(cast(Any, value))
    except Exception:
        return default


def _dedupe_model_ids(model_ids: list[int]) -> list[int]:
    unique: list[int] = []
    seen: set[int] = set()
    for value in model_ids:
        model_id = max(0, _safe_int(value, 0))
        if model_id <= 0 or model_id in seen:
            continue
        seen.add(model_id)
        unique.append(model_id)
    return unique


def _resolve_model_id_value(raw_value: object) -> int:
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        if not candidate:
            return 0
        if candidate.startswith('ModelID.'):
            enum_name = candidate.split('.', 1)[1].strip()
            enum_value = getattr(ModelID, enum_name, None)
            if enum_value is not None:
                try:
                    return int(enum_value.value)
                except Exception:
                    return _safe_int(enum_value, 0)
        return _safe_int(candidate, 0)
    return _safe_int(raw_value, 0)


def _normalize_catalog_search_text(raw_value: object) -> str:
    text = str(raw_value or '').strip().lower()
    if not text:
        return ''
    text = unquote(text)
    text = text.replace('_', ' ')
    text = re.sub(r'\.[a-z0-9]+$', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _build_catalog_alias_labels(name: object, skin: object = '', wiki_url: object = '') -> dict[str, str]:
    alias_labels: dict[str, str] = {}

    def _add_alias(raw_alias: object, display_label: object = ''):
        normalized = _normalize_catalog_search_text(raw_alias)
        if not normalized:
            return
        display = str(display_label or raw_alias or '').strip()
        if not display:
            display = normalized.title()
        alias_labels.setdefault(normalized, display)

    safe_name = str(name or '').strip()
    if safe_name:
        _add_alias(safe_name, safe_name)

    safe_skin = str(skin or '').strip()
    if safe_skin:
        skin_label = os.path.splitext(os.path.basename(safe_skin))[0].strip()
        if skin_label:
            _add_alias(skin_label, skin_label)

    safe_wiki_url = str(wiki_url or '').strip()
    if safe_wiki_url:
        wiki_stem = safe_wiki_url.rsplit('/', 1)[-1].split('?', 1)[0].split('#', 1)[0].strip()
        wiki_label = unquote(wiki_stem).replace('_', ' ').strip()
        if wiki_label:
            _add_alias(wiki_label, wiki_label)

    return alias_labels


def _humanize_model_id_enum_name(raw_name: object) -> str:
    text = str(raw_name or '').strip()
    if not text:
        return ''
    text = text.replace('_', ' ')
    text = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', text)
    text = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _get_mirrored_item_priority(item_type: object) -> int:
    normalized_type = str(item_type or '').strip().lower()
    if normalized_type in {
        'axe',
        'bow',
        'daggers',
        'hammer',
        'offhand',
        'scythe',
        'shield',
        'spear',
        'staff',
        'sword',
        'wand',
        'headpiece',
        'chestpiece',
        'gloves',
        'leggings',
        'boots',
    }:
        return 10
    if normalized_type in {'rune_mod', 'salvage'}:
        return 20
    return 30


def _get_catalog_entry_priority(
    model_id: object,
    item_type: object,
    category: object = '',
    sub_category: object = '',
    *,
    scroll_trader_stock_model_ids: frozenset[int] = frozenset(),
) -> int:
    priority = _get_mirrored_item_priority(item_type)
    if max(0, _safe_int(model_id, 0)) not in scroll_trader_stock_model_ids:
        return priority

    normalized_type = _normalize_catalog_search_text(item_type)
    normalized_category = _normalize_catalog_search_text(category)
    normalized_sub_category = _normalize_catalog_search_text(sub_category)
    if (
        normalized_type == 'scroll'
        or normalized_category == 'scroll'
        or normalized_sub_category.endswith('scroll')
    ):
        return min(priority, 15)
    return priority


def _infer_model_id_fallback_item_type(enum_names: list[str], display_name: str) -> str:
    candidates = [display_name, *enum_names]
    for candidate in candidates:
        compact = re.sub(r'[^A-Za-z0-9]+', '', str(candidate or ''))
        normalized = _normalize_catalog_search_text(_humanize_model_id_enum_name(candidate))
        tokens = set(normalized.split())
        for suffix, item_type in MODEL_ID_FALLBACK_ITEM_TYPE_SUFFIXES:
            suffix_lower = suffix.lower()
            if compact.lower().endswith(suffix_lower) or suffix_lower in tokens:
                return item_type
    return ''


def _iter_item_handling_catalog_entries(raw_catalog: object) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []

    def _walk(raw_value: object):
        if isinstance(raw_value, dict):
            if ('model_id' in raw_value or 'ModelID' in raw_value) and ('name' in raw_value or 'Name' in raw_value):
                entries.append(raw_value)
                return
            for child_value in raw_value.values():
                _walk(child_value)
        elif isinstance(raw_value, list):
            for child_value in raw_value:
                _walk(child_value)

    _walk(raw_catalog)
    return entries


def _normalize_weapon_mod_target_item_type(raw_value: object) -> str:
    if raw_value is None:
        return ''
    enum_name = str(getattr(raw_value, 'name', '') or '').strip()
    if enum_name:
        return enum_name
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        if not candidate:
            return ''
        if candidate in getattr(ItemType, '__members__', {}):
            return candidate
        try:
            return ItemType(int(candidate, 0)).name
        except Exception:
            return candidate
    try:
        return ItemType(int(cast(Any, raw_value))).name
    except Exception:
        return str(raw_value or '').strip()


def _normalize_weapon_mod_component_kind(raw_value: object) -> str:
    return str(raw_value or '').strip()


def _normalize_weapon_mod_variant_parts(
    identifier: object,
    target_item_type: object,
    component_kind: object,
) -> tuple[str, str, str]:
    return (
        str(identifier or '').strip(),
        _normalize_weapon_mod_target_item_type(target_item_type),
        _normalize_weapon_mod_component_kind(component_kind),
    )


def _make_weapon_mod_identifier_choice_key(identifier: object) -> str:
    safe_identifier = str(identifier or '').strip()
    return f'{WEAPON_MOD_GENERIC_KEY_PREFIX}{safe_identifier}' if safe_identifier else ''


def _make_weapon_mod_variant_choice_key(
    identifier: object,
    target_item_type: object,
    component_kind: object,
) -> str:
    safe_identifier, safe_target_item_type, safe_component_kind = _normalize_weapon_mod_variant_parts(
        identifier,
        target_item_type,
        component_kind,
    )
    if not safe_identifier or not safe_target_item_type or not safe_component_kind:
        return ''
    return (
        f'{WEAPON_MOD_VARIANT_KEY_PREFIX}{safe_identifier}'
        f'{WEAPON_MOD_CHOICE_SEPARATOR}{safe_target_item_type}'
        f'{WEAPON_MOD_CHOICE_SEPARATOR}{safe_component_kind}'
    )


def _humanize_weapon_mod_component_kind(component_kind: object) -> str:
    safe_component_kind = _normalize_weapon_mod_component_kind(component_kind)
    if not safe_component_kind:
        return ''
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', safe_component_kind).strip()


def _get_weapon_mod_type_name(weapon_mod: object) -> str:
    mod_type = getattr(weapon_mod, 'mod_type', None)
    return str(getattr(mod_type, 'name', mod_type) or '').strip()


def _is_expandable_weapon_mod_type(weapon_mod: object) -> bool:
    return _get_weapon_mod_type_name(weapon_mod) in ('Prefix', 'Suffix')


def _format_weapon_mod_variant_label(weapon_mod: object, component_kind: object) -> str:
    base_name = str(getattr(weapon_mod, 'name', '') or getattr(weapon_mod, 'identifier', '') or '').strip()
    component_label = _humanize_weapon_mod_component_kind(component_kind)
    if not base_name:
        base_name = 'Unknown Weapon Mod'
    if not component_label:
        return base_name
    mod_type_name = _get_weapon_mod_type_name(weapon_mod)
    if mod_type_name == 'Prefix':
        return f'{base_name} {component_label}'
    if mod_type_name == 'Suffix':
        return f'{component_label} {base_name}'
    return base_name


def _normalize_rune_catalog_profession(value: object) -> str:
    safe_value = str(value or '').strip()
    return safe_value or '_None'


def _normalize_catalog_rune_identifier(value: object) -> str:
    return str(value or '').strip()


def _get_rune_profession_label(value: object) -> str:
    profession = _normalize_rune_catalog_profession(value)
    return 'Common' if profession == '_None' else profession


def _get_rune_kind_label(mod_type: object) -> str:
    return 'Insignia' if str(mod_type or '').strip().lower() == 'prefix' else 'Rune'


def _get_rune_kind_sort_key(mod_type: object) -> int:
    return 0 if _get_rune_kind_label(mod_type) == 'Insignia' else 1


def _get_rune_modifier_value(modifier: object, field_name: str) -> object:
    if not isinstance(modifier, dict):
        return ''
    normalized_field = str(field_name or '').strip().lower()
    if normalized_field == 'arg1':
        return modifier.get('Arg1', '')
    if normalized_field == 'arg2':
        return modifier.get('Arg2', '')
    if normalized_field == 'arg':
        return modifier.get('Arg', '')
    return ''


def _resolve_rune_description_template(description: str, modifiers: object) -> str:
    safe_description = str(description or '').strip()
    if not safe_description or '{' not in safe_description:
        return safe_description
    if not isinstance(modifiers, list):
        return safe_description

    modifiers_by_identifier: dict[int, dict[str, object]] = {}
    for modifier in modifiers:
        if not isinstance(modifier, dict):
            continue
        modifier_identifier = _safe_int(modifier.get('Identifier', 0), 0)
        if modifier_identifier:
            modifiers_by_identifier[modifier_identifier] = modifier

    def replace_placeholder(match: re.Match) -> str:
        field_name = str(match.group(1) or '')
        modifier_identifier = _safe_int(match.group(2), 0)
        modifier = modifiers_by_identifier.get(modifier_identifier)
        if modifier is None:
            return str(match.group(0))

        value = _get_rune_modifier_value(modifier, field_name)
        if modifier_identifier == MODIFIER_IDENTIFIER_RUNE_ATTRIBUTE and field_name.lower() == 'arg1':
            attribute_id = _safe_int(value, 0)
            return RUNE_ATTRIBUTE_LABELS.get(attribute_id, f'Attribute {attribute_id}')
        try:
            return str(int(cast(Any, value)))
        except Exception:
            return str(value or match.group(0))

    return re.sub(r'\{(arg1|arg2|arg)\[(\d+)\]\}', replace_placeholder, safe_description)


def _get_rune_rarity_sort_key(rarity: object) -> int:
    rarity_order = {'blue': 0, 'purple': 1, 'gold': 2}
    return rarity_order.get(str(rarity or '').strip().lower(), 99)


@dataclass
class CatalogLoadResult:
    catalog_by_model_id: dict[int, dict[str, object]] = field(default_factory=dict)
    catalog_alias_to_model_ids: dict[str, list[int]] = field(default_factory=dict)
    catalog_alias_display_names: dict[str, str] = field(default_factory=dict)
    catalog_common_material_ids: list[int] = field(default_factory=list)
    catalog_merchant_essentials: list[dict[str, object]] = field(default_factory=list)
    catalog_rare_materials: list[dict[str, object]] = field(default_factory=list)
    catalog_stats: dict[str, int | bool] = field(default_factory=dict)
    catalog_load_error: str = ''
    weapon_mod_entries: list[dict[str, str]] = field(default_factory=list)
    rune_entries: list[dict[str, str]] = field(default_factory=list)
    armor_upgrade_entries: list[dict[str, str]] = field(default_factory=list)
    weapon_mod_names: dict[str, str] = field(default_factory=dict)
    weapon_mod_generic_names: dict[str, str] = field(default_factory=dict)
    weapon_mod_variant_names: dict[str, str] = field(default_factory=dict)
    rune_names: dict[str, str] = field(default_factory=dict)
    rune_buy_entries: list[dict[str, object]] = field(default_factory=list)
    rune_buy_entries_by_identifier: dict[str, dict[str, object]] = field(default_factory=dict)
    rune_buy_identifier_by_exact_label: dict[str, str] = field(default_factory=dict)
    rune_buy_entries_by_profession: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    rune_buy_professions: list[str] = field(default_factory=list)


class CatalogLoader:
    def __init__(
        self,
        *,
        catalog_path: str,
        drop_data_path: str,
        item_handling_path: str,
        runes_catalog_path: str,
        mod_db: object,
        mod_db_load_error: str,
        model_id_members: Callable[[], list[tuple[str, int]]],
        armor_upgrade_identity: Callable[[object], tuple[object | None, str]],
        scroll_trader_stock_model_ids: frozenset[int],
    ) -> None:
        self.catalog_path = str(catalog_path)
        self.drop_data_path = str(drop_data_path)
        self.item_handling_path = str(item_handling_path)
        self.runes_catalog_path = str(runes_catalog_path)
        self.mod_db = mod_db
        self.mod_db_load_error = str(mod_db_load_error or '')
        self.model_id_members = model_id_members
        self.armor_upgrade_identity = armor_upgrade_identity
        self.scroll_trader_stock_model_ids = frozenset(scroll_trader_stock_model_ids)

    def load(self) -> CatalogLoadResult:
        result = CatalogLoadResult()
        load_errors: list[str] = []
        common_entries: list[dict[str, object]] = []
        rare_entries: list[dict[str, object]] = []
        merchant_entries: list[dict[str, object]] = []
        item_handling_items_count = 0
        rune_model_catalog_count = 0
        drop_data_count = 0
        model_id_fallback_count = 0
        item_handling_present = os.path.exists(self.item_handling_path)

        try:
            with open(self.catalog_path, 'r', encoding='utf-8') as file:
                raw_catalog = json.load(file)

            materials = raw_catalog.get('materials', {})
            merchant_items = raw_catalog.get('merchant_items', {})

            common_entries = self._load_catalog_group(
                result,
                entries=list(materials.get('common', [])),
                source='merchant_rules_catalog.common',
                priority=0,
                default_item_type='material',
                default_material_type='common',
            )
            rare_entries = self._load_catalog_group(
                result,
                entries=list(materials.get('rare', [])),
                source='merchant_rules_catalog.rare',
                priority=0,
                default_item_type='material',
                default_material_type='rare',
            )
            merchant_entries = self._load_catalog_group(
                result,
                entries=list(merchant_items.get('essentials', [])),
                source='merchant_rules_catalog.essentials',
                priority=0,
            )

            result.catalog_common_material_ids = _dedupe_model_ids(
                [int(cast(Any, entry['model_id'])) for entry in common_entries]
            )
            result.catalog_rare_materials = rare_entries
            result.catalog_merchant_essentials = merchant_entries
        except Exception as exc:
            load_errors.append(f'Catalog load failed: {exc}')

        try:
            item_handling_items_count = self._load_item_handling_catalog(result)
        except Exception as exc:
            load_errors.append(f'ItemHandling item catalog load failed: {exc}')

        try:
            drop_data_count = self._load_drop_data_catalog(result)
        except Exception as exc:
            load_errors.append(f'Drop-data name load failed: {exc}')

        try:
            self._load_modifier_catalogs(result)
        except Exception as exc:
            load_errors.append(f'Modifier data load failed: {exc}')

        try:
            self._load_rune_buy_catalog(result)
        except Exception as exc:
            load_errors.append(f'Rune buy catalog load failed: {exc}')

        try:
            rune_model_catalog_count = self._load_rune_model_catalog(result)
        except Exception as exc:
            load_errors.append(f'Rune model catalog load failed: {exc}')

        if self.mod_db_load_error:
            load_errors.append(self.mod_db_load_error)

        try:
            model_id_fallback_count = self._load_model_id_fallback_catalog(result)
        except Exception as exc:
            load_errors.append(f'ModelID fallback catalog load failed: {exc}')

        self._rebuild_catalog_alias_index(result)
        result.catalog_stats = {
            'curated_common': len(common_entries),
            'curated_rare': len(rare_entries),
            'curated_essentials': len(merchant_entries),
            'curated_total': len(common_entries) + len(rare_entries) + len(merchant_entries),
            'item_handling_present': item_handling_present,
            'item_handling_items': item_handling_items_count,
            'rune_models': rune_model_catalog_count,
            'drop_data': drop_data_count,
            'modelid_fallback_items': model_id_fallback_count,
            'final_models': len(result.catalog_by_model_id),
            'alias_groups': self._get_catalog_alias_group_count(result),
        }
        if load_errors:
            result.catalog_load_error = ' | '.join(load_errors)
        return result

    def load_catalog_group(
        self,
        catalog_by_model_id: dict[int, dict[str, object]],
        entries: list[dict[str, object]],
        source: str,
        priority: int,
        default_item_type: str = '',
        default_material_type: str = '',
    ) -> list[dict[str, object]]:
        result = CatalogLoadResult(catalog_by_model_id=catalog_by_model_id)
        return self._load_catalog_group(
            result,
            entries,
            source,
            priority,
            default_item_type,
            default_material_type,
        )

    def load_drop_data_catalog(self, catalog_by_model_id: dict[int, dict[str, object]]) -> int:
        return self._load_drop_data_catalog(CatalogLoadResult(catalog_by_model_id=catalog_by_model_id))

    def load_item_handling_catalog(self, catalog_by_model_id: dict[int, dict[str, object]]) -> int:
        return self._load_item_handling_catalog(CatalogLoadResult(catalog_by_model_id=catalog_by_model_id))

    def load_rune_model_catalog(self, catalog_by_model_id: dict[int, dict[str, object]]) -> int:
        return self._load_rune_model_catalog(CatalogLoadResult(catalog_by_model_id=catalog_by_model_id))

    def load_model_id_fallback_catalog(self, catalog_by_model_id: dict[int, dict[str, object]]) -> int:
        return self._load_model_id_fallback_catalog(CatalogLoadResult(catalog_by_model_id=catalog_by_model_id))

    def rebuild_catalog_alias_index(
        self,
        catalog_by_model_id: dict[int, dict[str, object]],
    ) -> tuple[dict[str, list[int]], dict[str, str]]:
        result = CatalogLoadResult(catalog_by_model_id=catalog_by_model_id)
        self._rebuild_catalog_alias_index(result)
        return result.catalog_alias_to_model_ids, result.catalog_alias_display_names

    def load_modifier_catalogs(self) -> CatalogLoadResult:
        result = CatalogLoadResult()
        self._load_modifier_catalogs(result)
        return result

    def load_rune_buy_catalog(self) -> CatalogLoadResult:
        result = CatalogLoadResult()
        self._load_rune_buy_catalog(result)
        return result

    @staticmethod
    def _register_catalog_entry(
        result: CatalogLoadResult,
        model_id: int,
        name: str,
        item_type: str = '',
        material_type: str = '',
        source: str = '',
        priority: int = 100,
        extra: dict[str, object] | None = None,
    ) -> None:
        safe_model_id = max(0, _safe_int(model_id, 0))
        safe_name = str(name or '').strip()
        if safe_model_id <= 0 or not safe_name:
            return

        current = result.catalog_by_model_id.get(safe_model_id)
        if current is not None and int(cast(Any, current.get('priority', 999))) <= priority:
            return

        entry: dict[str, object] = {
            'model_id': safe_model_id,
            'name': safe_name,
            'item_type': str(item_type or '').strip(),
            'material_type': str(material_type or '').strip(),
            'source': source,
            'priority': int(priority),
        }
        if extra:
            for key, value in extra.items():
                if value not in (None, ''):
                    entry[key] = value

        result.catalog_by_model_id[safe_model_id] = entry

    def _load_catalog_group(
        self,
        result: CatalogLoadResult,
        entries: list[dict[str, object]],
        source: str,
        priority: int,
        default_item_type: str = '',
        default_material_type: str = '',
    ) -> list[dict[str, object]]:
        loaded_entries: list[dict[str, object]] = []
        for entry in entries:
            model_id = max(0, _safe_int(entry.get('model_id', 0), 0))
            if model_id <= 0:
                continue

            loaded_entry = {
                'model_id': model_id,
                'name': str(entry.get('name', '') or f'Model {model_id}'),
                'item_type': str(entry.get('item_type', default_item_type) or default_item_type),
                'material_type': str(entry.get('material_type', default_material_type) or default_material_type),
            }
            if 'default_target' in entry:
                loaded_entry['default_target'] = max(0, _safe_int(entry.get('default_target', 0), 0))

            self._register_catalog_entry(
                result,
                model_id=model_id,
                name=str(loaded_entry['name']),
                item_type=str(loaded_entry['item_type']),
                material_type=str(loaded_entry['material_type']),
                source=source,
                priority=priority,
                extra={'default_target': loaded_entry.get('default_target', 0)},
            )
            loaded_entries.append(loaded_entry)
        return loaded_entries

    def _load_drop_data_catalog(self, result: CatalogLoadResult) -> int:
        if not os.path.exists(self.drop_data_path):
            return 0

        with open(self.drop_data_path, 'r', encoding='utf-8') as file:
            rows = json.load(file)

        loaded_count = 0
        for row in rows:
            model_id = _resolve_model_id_value(row.get('model_id', 0))
            name = str(row.get('name', '')).strip()
            if model_id <= 0 or not name:
                continue
            self._register_catalog_entry(
                result,
                model_id=model_id,
                name=name,
                item_type=str(row.get('group', '')).strip(),
                material_type=str(row.get('subgroup', '')).strip(),
                source='modelid_drop_data',
                priority=50,
            )
            loaded_count += 1
        return loaded_count

    def _load_item_handling_catalog(self, result: CatalogLoadResult) -> int:
        if not os.path.exists(self.item_handling_path):
            return 0

        with open(self.item_handling_path, 'r', encoding='utf-8') as file:
            raw_catalog = json.load(file)

        loaded_count = 0
        for entry in _iter_item_handling_catalog_entries(raw_catalog):
            model_id = _resolve_model_id_value(entry.get('model_id', entry.get('ModelID', 0)))
            name = str(entry.get('name') or entry.get('Name') or '').strip()
            if model_id <= 0 or not name:
                continue

            item_type = str(entry.get('item_type') or entry.get('ItemType') or '').strip()
            skin = str(entry.get('skin') or entry.get('Skin') or '').strip()
            wiki_url = str(entry.get('wiki_url') or entry.get('WikiURL') or '').strip()
            category = str(entry.get('category') or '').strip()
            sub_category = str(entry.get('sub_category') or '').strip()
            raw_attributes = entry.get('attributes', [])
            attributes = (
                [str(attribute).strip() for attribute in raw_attributes if str(attribute or '').strip()]
                if isinstance(raw_attributes, list)
                else []
            )
            alias_labels = _build_catalog_alias_labels(name, skin, wiki_url)

            extra: dict[str, object] = {
                'alias_labels': alias_labels,
                'attributes': attributes,
            }
            if skin:
                extra['skin'] = skin
            if wiki_url:
                extra['wiki_url'] = wiki_url
            if category:
                extra['category'] = category
            if sub_category:
                extra['sub_category'] = sub_category

            self._register_catalog_entry(
                result,
                model_id=model_id,
                name=name,
                item_type=item_type,
                source='item_handling_items_catalog',
                priority=_get_catalog_entry_priority(
                    model_id,
                    item_type,
                    category,
                    sub_category,
                    scroll_trader_stock_model_ids=self.scroll_trader_stock_model_ids,
                ),
                extra=extra,
            )
            loaded_count += 1
        return loaded_count

    def _load_rune_model_catalog(self, result: CatalogLoadResult) -> int:
        if not os.path.exists(self.runes_catalog_path):
            return 0

        with open(self.runes_catalog_path, 'r', encoding='utf-8') as file:
            raw_catalog = json.load(file)

        if not isinstance(raw_catalog, dict):
            return 0

        grouped_entries: dict[int, tuple[set[str], set[str]]] = {}
        for raw_identifier, raw_entry in raw_catalog.items():
            if not isinstance(raw_entry, dict):
                continue
            model_id = max(0, _safe_int(raw_entry.get('ModelId', 0), 0))
            if model_id <= 0:
                continue

            names = raw_entry.get('Names', {})
            if isinstance(names, dict):
                display_name = str(names.get('English', '') or '').strip()
            else:
                display_name = ''
            if not display_name:
                display_name = str(raw_entry.get('Identifier', raw_identifier) or '').strip()
            if not display_name:
                continue

            mod_type = str(raw_entry.get('ModType', '') or '').strip()
            normalized_name = _normalize_catalog_search_text(display_name)
            if mod_type == 'Prefix' or 'insignia' in normalized_name:
                kind = 'insignia'
            elif mod_type == 'Suffix' or 'rune' in normalized_name:
                kind = 'rune'
            else:
                kind = ''

            names_for_model, kinds_for_model = grouped_entries.setdefault(model_id, (set(), set()))
            names_for_model.add(display_name)
            if kind:
                kinds_for_model.add(kind)

        loaded_count = 0
        for model_id, (names_for_model, kinds_for_model) in grouped_entries.items():
            names = sorted(str(name) for name in names_for_model if str(name or '').strip())
            kinds = sorted(str(kind) for kind in kinds_for_model if str(kind or '').strip())
            if not names:
                continue

            if len(names) == 1:
                display_name = names[0]
            elif kinds == ['insignia']:
                display_name = 'Insignia'
            elif kinds == ['rune']:
                display_name = 'Rune'
            else:
                display_name = 'Rune / Insignia'

            alias_labels = _build_catalog_alias_labels(display_name)
            for name in names:
                alias_labels.update(_build_catalog_alias_labels(name))

            extra: dict[str, object] = {
                'alias_labels': alias_labels,
                'rune_model_kinds': kinds,
                'rune_model_names': names,
            }
            current = result.catalog_by_model_id.get(model_id)
            if current is None:
                self._register_catalog_entry(
                    result,
                    model_id=model_id,
                    name=display_name,
                    item_type='Rune_Mod',
                    source='runes_catalog',
                    priority=18,
                    extra=extra,
                )
            else:
                if not str(current.get('item_type', '') or '').strip():
                    current['item_type'] = 'Rune_Mod'
                current_kinds = [
                    str(kind)
                    for kind in cast(list[object], current.get('rune_model_kinds', []))
                    if str(kind or '').strip()
                ]
                merged_kinds = sorted(set(current_kinds) | set(kinds))
                if merged_kinds:
                    current['rune_model_kinds'] = merged_kinds

                current_names = [
                    str(name)
                    for name in cast(list[object], current.get('rune_model_names', []))
                    if str(name or '').strip()
                ]
                merged_names = sorted(set(current_names) | set(names))
                if merged_names:
                    current['rune_model_names'] = merged_names

                current_alias_labels = current.get('alias_labels', {})
                if not isinstance(current_alias_labels, dict):
                    current_alias_labels = {}
                current_alias_labels.update(alias_labels)
                current['alias_labels'] = current_alias_labels
            loaded_count += 1

        return loaded_count

    def _load_model_id_fallback_catalog(self, result: CatalogLoadResult) -> int:
        enum_names_by_model_id: dict[int, list[str]] = {}
        for enum_name, model_id in self.model_id_members():
            if model_id <= 0:
                continue
            names = enum_names_by_model_id.setdefault(model_id, [])
            if enum_name not in names:
                names.append(enum_name)

        loaded_count = 0
        for model_id, enum_names in enum_names_by_model_id.items():
            if model_id in result.catalog_by_model_id:
                continue
            if not enum_names:
                continue

            display_name = _humanize_model_id_enum_name(enum_names[0]) or f'Model {model_id}'
            alias_labels = _build_catalog_alias_labels(display_name)
            for enum_name in enum_names:
                raw_name = str(enum_name or '').strip()
                if not raw_name:
                    continue
                alias_labels.setdefault(_normalize_catalog_search_text(raw_name), raw_name)
                humanized_name = _humanize_model_id_enum_name(raw_name)
                if humanized_name:
                    alias_labels.setdefault(_normalize_catalog_search_text(humanized_name), humanized_name)

            self._register_catalog_entry(
                result,
                model_id=model_id,
                name=display_name,
                item_type=_infer_model_id_fallback_item_type(enum_names, display_name),
                source='modelid_enum_fallback',
                priority=90,
                extra={
                    'alias_labels': alias_labels,
                    'enum_names': list(enum_names),
                },
            )
            loaded_count += 1
        return loaded_count

    @staticmethod
    def _rebuild_catalog_alias_index(result: CatalogLoadResult) -> None:
        result.catalog_alias_to_model_ids = {}
        result.catalog_alias_display_names = {}

        for model_id, entry in result.catalog_by_model_id.items():
            alias_labels = entry.get('alias_labels', {})
            normalized_alias_labels: dict[str, str] = {}
            if isinstance(alias_labels, dict):
                for raw_alias, display_name in alias_labels.items():
                    normalized_alias = _normalize_catalog_search_text(raw_alias)
                    if normalized_alias:
                        normalized_alias_labels[normalized_alias] = (
                            str(display_name or '').strip() or normalized_alias.title()
                        )

            name = str(entry.get('name', '')).strip()
            normalized_name = _normalize_catalog_search_text(name)
            if normalized_name and normalized_name not in normalized_alias_labels:
                normalized_alias_labels[normalized_name] = name

            entry['alias_labels'] = normalized_alias_labels
            for normalized_alias, display_name in normalized_alias_labels.items():
                alias_model_ids = result.catalog_alias_to_model_ids.setdefault(normalized_alias, [])
                if model_id not in alias_model_ids:
                    alias_model_ids.append(model_id)
                result.catalog_alias_display_names.setdefault(normalized_alias, display_name)

    @staticmethod
    def _get_catalog_alias_group_count(result: CatalogLoadResult) -> int:
        return sum(1 for model_ids in result.catalog_alias_to_model_ids.values() if len(model_ids) > 1)

    def _load_modifier_catalogs(self, result: CatalogLoadResult) -> None:
        mod_db = cast(Any, self.mod_db)
        for identifier, weapon_mod in sorted(
            mod_db.weapon_mods.items(),
            key=lambda row: row[1].name.lower() or row[0].lower(),
        ):
            display_name = str(weapon_mod.name or identifier).strip()
            safe_identifier = str(identifier)
            generic_label = (
                f'{display_name} (all supported weapons)'
                if _is_expandable_weapon_mod_type(weapon_mod)
                else display_name
            )
            entry = {
                'identifier': _make_weapon_mod_identifier_choice_key(safe_identifier),
                'name': generic_label,
                'base_identifier': safe_identifier,
                'entry_kind': WEAPON_MOD_CHOICE_KIND_GENERIC,
            }
            result.weapon_mod_entries.append(entry)
            result.weapon_mod_names[safe_identifier] = display_name
            result.weapon_mod_generic_names[safe_identifier] = generic_label

            if _is_expandable_weapon_mod_type(weapon_mod):
                for target_item_type, component_kind in getattr(weapon_mod, 'item_mods', {}).items():
                    target_item_type_name = _normalize_weapon_mod_target_item_type(target_item_type)
                    safe_component_kind = _normalize_weapon_mod_component_kind(component_kind)
                    variant_key = _make_weapon_mod_variant_choice_key(
                        safe_identifier,
                        target_item_type_name,
                        safe_component_kind,
                    )
                    if not variant_key:
                        continue
                    variant_label = _format_weapon_mod_variant_label(weapon_mod, safe_component_kind)
                    result.weapon_mod_entries.append(
                        {
                            'identifier': variant_key,
                            'name': variant_label,
                            'base_identifier': safe_identifier,
                            'entry_kind': WEAPON_MOD_CHOICE_KIND_VARIANT,
                            'target_item_type': target_item_type_name,
                            'component_kind': safe_component_kind,
                        }
                    )
                    result.weapon_mod_variant_names[variant_key] = variant_label

        for identifier, rune in sorted(
            mod_db.runes.items(),
            key=lambda row: row[1].name.lower() or row[0].lower(),
        ):
            display_name = str(rune.name or identifier).strip()
            entry = {'identifier': str(identifier), 'name': display_name}
            result.rune_entries.append(entry)
            result.rune_names[str(identifier)] = display_name
            armor_identity, _identity_error = self.armor_upgrade_identity(identifier)
            if armor_identity is not None:
                result.armor_upgrade_entries.append(entry)

    def _load_rune_buy_catalog(self, result: CatalogLoadResult) -> None:
        if not os.path.exists(self.runes_catalog_path):
            raise FileNotFoundError(f'Rune catalog missing: {self.runes_catalog_path}')

        with open(self.runes_catalog_path, 'r', encoding='utf-8') as file:
            raw_catalog = json.load(file)

        if not isinstance(raw_catalog, dict):
            raise ValueError('Rune catalog must be a JSON object.')

        entries: list[dict[str, object]] = []
        for raw_identifier, raw_entry in raw_catalog.items():
            if not isinstance(raw_entry, dict):
                continue
            identifier = _normalize_catalog_rune_identifier(raw_entry.get('Identifier', raw_identifier))
            if not identifier:
                continue
            names = raw_entry.get('Names', {})
            if isinstance(names, dict):
                display_name = str(names.get('English', identifier) or identifier).strip()
            else:
                display_name = identifier
            profession = _normalize_rune_catalog_profession(raw_entry.get('Profession', '_None'))
            rarity = str(raw_entry.get('Rarity', '') or '').strip()
            mod_type = str(raw_entry.get('ModType', '') or '').strip()
            vendor_value = max(0, _safe_int(raw_entry.get('VendorValue', 0), 0))
            descriptions = raw_entry.get('Descriptions', {})
            if isinstance(descriptions, dict):
                english_description = str(descriptions.get('English', '') or '').strip()
            else:
                english_description = ''
            english_description = _resolve_rune_description_template(
                english_description,
                raw_entry.get('Modifiers', []),
            )
            entry = {
                'identifier': identifier,
                'name': display_name,
                'description': english_description,
                'profession': profession,
                'profession_label': _get_rune_profession_label(profession),
                'rarity': rarity,
                'mod_type': mod_type,
                'kind_label': _get_rune_kind_label(mod_type),
                'vendor_value': vendor_value,
            }
            entries.append(entry)

        entries.sort(
            key=lambda entry: (
                str(entry.get('profession_label', '')).lower(),
                _get_rune_kind_sort_key(entry.get('mod_type', '')),
                _get_rune_rarity_sort_key(entry.get('rarity', '')),
                str(entry.get('name', '')).lower(),
                str(entry.get('identifier', '')).lower(),
            )
        )
        grouped_entries: dict[str, list[dict[str, object]]] = {}
        for entry in entries:
            profession = str(entry.get('profession', '_None') or '_None')
            grouped_entries.setdefault(profession, []).append(entry)

        profession_order = sorted(
            grouped_entries.keys(),
            key=lambda profession: (
                0 if profession == '_None' else 1,
                _get_rune_profession_label(profession).lower(),
            ),
        )

        result.rune_buy_entries = entries
        result.rune_buy_entries_by_identifier = {
            str(entry.get('identifier', '')).strip(): entry
            for entry in entries
            if str(entry.get('identifier', '')).strip()
        }
        self._rebuild_rune_exact_display_lookup(result)
        result.rune_buy_entries_by_profession = grouped_entries
        result.rune_buy_professions = profession_order

    @staticmethod
    def _rebuild_rune_exact_display_lookup(result: CatalogLoadResult) -> None:
        identifiers_by_label: dict[str, set[str]] = {}
        for entry in result.rune_buy_entries:
            identifier = str(entry.get('identifier', '') or '').strip()
            if not identifier:
                continue
            for label in (
                str(entry.get('name', '') or '').strip(),
                identifier,
            ):
                normalized_label = _normalize_catalog_search_text(label)
                if normalized_label:
                    identifiers_by_label.setdefault(normalized_label, set()).add(identifier)

        result.rune_buy_identifier_by_exact_label = {
            label: next(iter(identifiers))
            for label, identifiers in identifiers_by_label.items()
            if len(identifiers) == 1
        }
