import json
import os
import time
from dataclasses import dataclass
from typing import Callable

import PySystem
import PyImGui

from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.Player import Player
from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE
from Py4GWCoreLib.Inventory import Inventory
from Py4GWCoreLib.py4gwcorelib_src.Console import ConsoleLog
from Py4GWCoreLib.enums_src.Py4GW_enums import Console
from Py4GWCoreLib.enums_src.Multiboxing_enums import SharedCommandType
from Py4GWCoreLib.enums_src.Hero_enums import HeroType
from Py4GWCoreLib.ImGui_src.ImGuisrc import ImGui

from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import *
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants import *
from Py4GWCoreLib.routines_src.behaviourtrees_src.composite import BTComposite
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems
from Sources.ApoSource.ApoBottingLib import wrappers as BT
from Py4GWCoreLib.enums import Range
from Py4GWCoreLib.enums_src.Model_enums import ModelID
from Widgets.System.Messaging import get_inventory_state, reset_inventory_state

MODULE_NAME = 'Tunnels of the Forsaken Farm'
INI_PATH = 'Widgets/Automation/Bots/Missions/Dungeons/Tunnels of the Forsaken Farm'
INI_FILENAME = 'Tunnels_of_the_Forsaken_Farm.ini'
MODULE_ICON = 'Assets\\Textures\\Module_Icons\\Tunnels of the Forsaken.png'
TEXTURE = os.path.join(PySystem.Console.get_projects_path(), 'Assets', 'Textures', 'Module_Icons', 'Tunnels of the Forsaken.png')

# ── Map IDs ──────────────────────────────────────────────────────────────────
PIKEN_SQUARE = 40
THE_BREACH   = 102
TUNNELS_LVL_1 = 880
TUNNELS_LVL_2 = 881
TUNNELS_LVL_3 = 882

# ── Quest / Dialog IDs ────────────────────────────────────────────────────────
DREAMER_AND_ZEALOT_QUEST_ID = 1461
QUEST_ACCEPT_DIALOG         = 0x85B501
QUEST_REWARD_DIALOG         = 0x85B507

# ── Important interaction positions ─────────────────────────────────────────
QUEST_NPC_POS               = (-7400., -9462.)
QUEST_REWARD_NPC_POS        = (-16098., -8626.)
DUNGEON_CHEST_POS           = (-16066., -8370.)

# ── Aggro range ($RANGE_SPELLCAST + 100 from AutoIt) ─────────────────────────
TUNNELS_AGGRO_RANGE = Range.Spellcast.value + 100.0

# ── Consumables ──────────────────────────────────────────────────────────────
# Same generic, non-content-locked stones Shards Of Orr's own
# UseAvailableSummoningStone() offers -- carry over only if these are actually
# in the loadout; harmless (no-op) if not carried.
SUMMON_MODEL_IDS = (30209, 37810, 31155)  # Tengu Summon, Legionnaire Summoning Crystal, Mysterious Summon
PCON_UPKEEPS = tuple((int(model_id) for model_id in CONSUMABLE_UPKEEPS if int(model_id) not in CONSET_UPKEEPS))
CONSET_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple(((int(model_id), 10) for model_id in CONSET_UPKEEPS))
PCON_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple(((int(model_id), 10) for model_id in PCON_UPKEEPS))
SUMMON_RESTOCK_ITEMS: tuple[tuple[int, int], ...] = tuple(((model_id, 10) for model_id in SUMMON_MODEL_IDS))

# ── Inventory maintenance ────────────────────────────────────────────────────
ID_KIT_MODEL_IDS = (int(ModelID.Identification_Kit.value), int(ModelID.Superior_Identification_Kit.value))
SALVAGE_KIT_MODEL_IDS = (int(ModelID.Expert_Salvage_Kit.value),)
MERCHANT_RULES_WIDGET_NAME = "MerchantRules"
INVENTORY_PLUS_WIDGET_NAME = "InventoryPlus"
INVENTORY_MAINTENANCE_RETRY_COUNT = 2
INVENTORY_SNAPSHOT_SETTLE_MS = 2_000
INVENTORY_MERCHANT_TIMEOUT_MS = 240_000
_INVENTORY_QUERY_POLL_MS = 200
_INVENTORY_QUERY_TIMEOUT_MS = 10_000

initialized = False
botting_tree: BottingTree | None = None

# ── Bot settings (persisted to INI) ──────────────────────────────────────────
_settings_ini = Settings(f'{INI_PATH}/{INI_FILENAME}', 'account')
_SETTINGS_SECTION = 'Settings'
_HARD_MODE_KEY = 'use_hard_mode'
_RESTOCK_CONSET_KEY = 'restock_conset'
_ACTIVATE_CONSET_KEY = 'activate_conset'
_RESTOCK_PCONS_KEY = 'restock_pcons'
_ACTIVATE_PCONS_KEY = 'activate_pcons'
_USE_SUMMONING_STONE_KEY = 'use_summoning_stone'
_INVENTORY_ENABLED_KEY = 'inventory_maintenance_enabled'
_INVENTORY_MIN_FREE_SLOTS_KEY = 'inventory_min_free_slots'
_INVENTORY_MIN_ID_KITS_KEY = 'inventory_min_id_kits'
_INVENTORY_MIN_SALVAGE_KITS_KEY = 'inventory_min_salvage_kits'

_use_hard_mode: bool = True
_restock_conset: bool = True
_activate_conset: bool = True
_restock_pcons: bool = True
_activate_pcons: bool = True
_use_summoning_stone: bool = True
_inventory_maintenance_enabled: bool = True
_inventory_min_free_slots: int = 5
_inventory_min_id_kits: int = 1
_inventory_min_salvage_kits: int = 2

_inventory_status_snapshot: dict[str, dict[str, object]] = {}

# ── Party mode (Single Account with Heroes / Multiboxing) ───────────────────
_USE_MULTIBOX_KEY = 'use_multibox_alts'
_party_mode: int = 0      # 0 = Single Account with Heroes, 1 = Multiboxing
_tree_party_mode: int | None = None  # party mode the current botting_tree was built for
_heroes_setup_done: bool = False


def _is_multibox() -> bool:
    return _party_mode == 1


# ── Hero config ──────────────────────────────────────────────────────────────
@dataclass
class _PartyHeroSlot:
    hero_id: int = 0
    template: str = ""


def _humanize_hero_name(enum_name: str) -> str:
    if enum_name == "None_":
        return "<Empty>"
    words: list[str] = []
    current = enum_name[0]
    for char in enum_name[1:]:
        if (char.isupper() and not current[-1].isupper()) or (char.isdigit() and not current[-1].isdigit()):
            words.append(current)
            current = char
        else:
            current += char
    words.append(current)
    return " ".join(words)


_HERO_OPTIONS: list[HeroType] = [HeroType.None_] + sorted(
    [h for h in HeroType if h != HeroType.None_],
    key=lambda h: _humanize_hero_name(h.name),
)
_HERO_OPTION_LABELS: list[str] = [_humanize_hero_name(h.name) for h in _HERO_OPTIONS]
_HERO_ID_TO_OPTION_INDEX: dict[int, int] = {int(h): i for i, h in enumerate(_HERO_OPTIONS)}

_HERO_ICON_FILENAMES: dict[HeroType, str] = {
    HeroType.Norgu: "Norgu-icon.jpg",           HeroType.Goren: "Goren-icon.jpg",
    HeroType.Tahlkora: "Tahlkora-icon.jpg",      HeroType.MasterOfWhispers: "MasterOfWhispers-icon.jpg",
    HeroType.AcolyteJin: "AcolyteSousuke-icon.jpg", HeroType.Koss: "Koss-icon.jpg",
    HeroType.Dunkoro: "Dunkoro-icon.jpg",        HeroType.AcolyteSousuke: "AcolyteSousuke-icon.jpg",
    HeroType.Melonni: "Melonni-icon.jpg",        HeroType.ZhedShadowhoof: "ZhedShadowhoof-icon.jpg",
    HeroType.GeneralMorgahn: "GeneralMorgahn-icon.jpg", HeroType.MagridTheSly: "MargridTheSly-icon.jpg",
    HeroType.Zenmai: "Zenmai-icon.jpg",          HeroType.Olias: "Olias-icon.jpg",
    HeroType.Razah: "Razah-icon.jpg",            HeroType.MOX: "M.O.X.-icon.jpg",
    HeroType.KeiranThackeray: "KeiranThackeray-icon.jpg", HeroType.Jora: "Jora-icon.jpg",
    HeroType.PyreFierceshot: "Pyre_Fierceshot-icon.jpg", HeroType.Anton: "Anton-icon.jpg",
    HeroType.Livia: "Livia-icon.jpg",            HeroType.Hayda: "Hayda-icon.jpg",
    HeroType.Kahmu: "Kahmu-icon.jpg",            HeroType.Gwen: "Gwen-icon.jpg",
    HeroType.Xandra: "Xandra-icon.jpg",          HeroType.Vekk: "Vekk-icon.jpg",
    HeroType.Ogden: "Ogden_Stonehealer-icon.jpg", HeroType.Miku: "Miku-icon.jpg",
    HeroType.ZeiRi: "Zei_Ri-icon.jpg",
}

_DEFAULT_HERO_TEMPLATES: dict[HeroType, str] = {}  # fill with preferred templates, if any

_HERO_SLOTS_COUNT = 7
_hero_slots: list[_PartyHeroSlot] = [_PartyHeroSlot() for _ in range(_HERO_SLOTS_COUNT)]
_hero_config_dirty: bool = False
_hero_config_status: str = ""
_hero_import_source_index: int = 0

_BOT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
_HERO_CONFIG_PATH = os.path.join(_BOT_SCRIPT_DIR, f"{MODULE_NAME} Heroes.json")
_HERO_ICONS_BASE = os.path.normpath(os.path.join(
    PySystem.Console.get_projects_path(), "..", "Property-of-Wick-Divinus-and-Kendor",
    "PVE Skills Unlocker", "Textures", "Skill_Icons",
))


def _load_settings() -> None:
    global _use_hard_mode, _restock_conset, _activate_conset, _restock_pcons, _activate_pcons
    global _use_summoning_stone, _inventory_maintenance_enabled
    global _inventory_min_free_slots, _inventory_min_id_kits, _inventory_min_salvage_kits
    global _party_mode

    _party_mode = 1 if _settings_ini.get_bool(_SETTINGS_SECTION, _USE_MULTIBOX_KEY, False) else 0
    _use_hard_mode = _settings_ini.get_bool(_SETTINGS_SECTION, _HARD_MODE_KEY, True)
    _restock_conset = _settings_ini.get_bool(_SETTINGS_SECTION, _RESTOCK_CONSET_KEY, True)
    _activate_conset = _settings_ini.get_bool(_SETTINGS_SECTION, _ACTIVATE_CONSET_KEY, True)
    _restock_pcons = _settings_ini.get_bool(_SETTINGS_SECTION, _RESTOCK_PCONS_KEY, True)
    _activate_pcons = _settings_ini.get_bool(_SETTINGS_SECTION, _ACTIVATE_PCONS_KEY, True)
    _use_summoning_stone = _settings_ini.get_bool(_SETTINGS_SECTION, _USE_SUMMONING_STONE_KEY, True)
    _inventory_maintenance_enabled = _settings_ini.get_bool(_SETTINGS_SECTION, _INVENTORY_ENABLED_KEY, True)
    _inventory_min_free_slots = max(0, _settings_ini.get_int(_SETTINGS_SECTION, _INVENTORY_MIN_FREE_SLOTS_KEY, 5))
    _inventory_min_id_kits = max(0, _settings_ini.get_int(_SETTINGS_SECTION, _INVENTORY_MIN_ID_KITS_KEY, 1))
    _inventory_min_salvage_kits = max(0, _settings_ini.get_int(_SETTINGS_SECTION, _INVENTORY_MIN_SALVAGE_KITS_KEY, 2))


def _save_settings() -> None:
    _settings_ini.set(_SETTINGS_SECTION, _USE_MULTIBOX_KEY, _is_multibox())
    _settings_ini.set(_SETTINGS_SECTION, _HARD_MODE_KEY, _use_hard_mode)
    _settings_ini.set(_SETTINGS_SECTION, _RESTOCK_CONSET_KEY, _restock_conset)
    _settings_ini.set(_SETTINGS_SECTION, _ACTIVATE_CONSET_KEY, _activate_conset)
    _settings_ini.set(_SETTINGS_SECTION, _RESTOCK_PCONS_KEY, _restock_pcons)
    _settings_ini.set(_SETTINGS_SECTION, _ACTIVATE_PCONS_KEY, _activate_pcons)
    _settings_ini.set(_SETTINGS_SECTION, _USE_SUMMONING_STONE_KEY, _use_summoning_stone)
    _settings_ini.set(_SETTINGS_SECTION, _INVENTORY_ENABLED_KEY, _inventory_maintenance_enabled)
    _settings_ini.set(_SETTINGS_SECTION, _INVENTORY_MIN_FREE_SLOTS_KEY, _inventory_min_free_slots)
    _settings_ini.set(_SETTINGS_SECTION, _INVENTORY_MIN_ID_KITS_KEY, _inventory_min_id_kits)
    _settings_ini.set(_SETTINGS_SECTION, _INVENTORY_MIN_SALVAGE_KITS_KEY, _inventory_min_salvage_kits)


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    """Consumables that must be continuously maintained. Summoning stones are
    excluded -- they're one-shot items, handled separately by
    UseAvailableSummoningStone(), not the continuous upkeep service."""
    enabled: list[int] = []
    if _activate_conset:
        enabled.extend(CONSET_UPKEEPS)
    if _activate_pcons:
        enabled.extend(PCON_UPKEEPS)
    return tuple(dict.fromkeys((int(model_id) for model_id in enabled)))


def _runtime_restock_node() -> BehaviorTree:
    def _build(_node: BehaviorTree.Node) -> BehaviorTree:
        items: list[tuple[int, int]] = []
        if _restock_conset:
            items.extend(CONSET_RESTOCK_ITEMS)
        if _restock_pcons:
            items.extend(PCON_RESTOCK_ITEMS)
        if _use_summoning_stone:
            items.extend(SUMMON_RESTOCK_ITEMS)
        if not items:
            return BT.Succeeder('RestockDisabled')
        return BT.RestockItemsFromList(tuple(items), allow_missing=True)

    return BT.Subtree(name='Restock Selected Consumables', subtree_fn=_build)


def UseAvailableSummoningStone() -> BehaviorTree:
    """Use the first available summoning stone once. Kept outside the continuous
    consumable upkeep service since these are one-shot items, not something to
    keep re-buffing."""
    if not _use_summoning_stone:
        return BT.Succeeder('SummoningStoneDisabled')

    stone_attempts = [
        BT.Sequence(
            name=f'Use Summoning Stone {model_id}',
            children=[BTItems.HasItemQuantity(int(model_id), 1), BTItems.UseConsumable(int(model_id))],
        )
        for model_id in SUMMON_MODEL_IDS
    ]
    return BT.Selector(name='Use Available Summoning Stone', children=stone_attempts + [BT.Succeeder('NoSummoningStoneAvailable')])


def _draw_bot_config() -> None:
    global _party_mode
    global _use_hard_mode
    global _restock_conset, _activate_conset
    global _restock_pcons, _activate_pcons
    global _use_summoning_stone
    global _inventory_maintenance_enabled
    global _inventory_min_free_slots, _inventory_min_id_kits, _inventory_min_salvage_kits

    changed = False
    upkeep_changed = False

    PyImGui.text('Party Mode')
    new_mode = PyImGui.radio_button('Single Account with Heroes', _party_mode, 0)
    PyImGui.same_line(0, 16)
    new_mode = PyImGui.radio_button('Multiboxing', new_mode, 1)
    if new_mode != _party_mode:
        _party_mode = int(new_mode)
        _save_settings()
        _rebuild_tree_for_party_mode()

    if _is_multibox():
        PyImGui.text_colored('Multibox: alt accounts are summoned and invited automatically.', (0.6, 0.9, 1.0, 1.0))
    else:
        PyImGui.text_colored('Single account: heroes configured on the Heroes tab are loaded automatically.', (0.7, 1.0, 0.7, 1.0))

    PyImGui.separator()

    value = PyImGui.checkbox('Hard Mode', _use_hard_mode)
    if value != _use_hard_mode:
        _use_hard_mode = value
        changed = True

    PyImGui.separator()
    PyImGui.text('Conset')

    value = PyImGui.checkbox('Restock conset from storage', _restock_conset)
    if value != _restock_conset:
        _restock_conset = value
        changed = True

    value = PyImGui.checkbox('Activate / maintain conset', _activate_conset)
    if value != _activate_conset:
        _activate_conset = value
        changed = True
        upkeep_changed = True

    PyImGui.separator()
    PyImGui.text('Personal consumables')

    value = PyImGui.checkbox('Restock pcons from storage', _restock_pcons)
    if value != _restock_pcons:
        _restock_pcons = value
        changed = True

    value = PyImGui.checkbox('Activate / maintain pcons', _activate_pcons)
    if value != _activate_pcons:
        _activate_pcons = value
        changed = True
        upkeep_changed = True

    PyImGui.separator()
    PyImGui.text('Summoning stones')

    value = PyImGui.checkbox('Use summoning stones', _use_summoning_stone)
    if value != _use_summoning_stone:
        _use_summoning_stone = value
        changed = True

    PyImGui.separator()
    PyImGui.text('Inventory maintenance')

    value = PyImGui.checkbox('Run MerchantRules when inventory is low', _inventory_maintenance_enabled)
    if value != _inventory_maintenance_enabled:
        _inventory_maintenance_enabled = value
        changed = True

    if _inventory_maintenance_enabled:
        value = max(0, int(PyImGui.input_int('Minimum free slots', _inventory_min_free_slots)))
        if value != _inventory_min_free_slots:
            _inventory_min_free_slots = value
            changed = True

        value = max(0, int(PyImGui.input_int('Minimum ID kits (0 = disabled)', _inventory_min_id_kits)))
        if value != _inventory_min_id_kits:
            _inventory_min_id_kits = value
            changed = True

        value = max(0, int(PyImGui.input_int('Minimum salvage kits (0 = disabled)', _inventory_min_salvage_kits)))
        if value != _inventory_min_salvage_kits:
            _inventory_min_salvage_kits = value
            changed = True

        PyImGui.text_wrapped(
            'Checked when every account returns to Piken Square. If any active account '
            'falls below a threshold, MerchantRules runs on ALL active accounts together.'
        )

    if changed:
        _save_settings()

    if upkeep_changed and botting_tree is not None:
        _apply_upkeep_config(botting_tree)


def _draw_help_page() -> None:
    PyImGui.text('Tunnels of the Forsaken Farm')
    PyImGui.separator()
    PyImGui.text('Requirements')
    PyImGui.separator()
    PyImGui.text('- Single Account with Heroes, or Multiboxing with real alt accounts;')
    PyImGui.text('  set in the Bot Config tab (Multiboxing needs at least one follower account,')
    PyImGui.text('  Single Account needs heroes configured on the Heroes tab).')
    PyImGui.text('- Althea the Healer must have been unlocked in a previous run.')
    PyImGui.text('- No consumables required.')
    PyImGui.text('- Hard Mode toggle available in the Bot Config tab.')
    PyImGui.separator()
    PyImGui.text('Tested Setup')
    PyImGui.separator()
    PyImGui.text('- Tested in Normal Mode only.')
    PyImGui.text('- Tested with: TaO Ranger, Panic Mesmer, Inept Mesmer, SoS Healer.')
    PyImGui.separator()
    PyImGui.text('Route')
    PyImGui.separator()
    PyImGui.text('- Travels to Piken Square, enters The Breach, then clears all 3 floors.')
    PyImGui.text('- Accepts and rewards The Dreamer and the Zealot quest automatically.')
    PyImGui.text('- Abandons and re-takes the quest at the start of each run.')
    PyImGui.separator()
    PyImGui.text('Credits')
    PyImGui.separator()
    PyImGui.text('- Original Author: GWAU2 BotsHub (Kronos, TDawg)')
    PyImGui.text('- Py4GW port by Northbound')


# ── Hero config I/O ───────────────────────────────────────────────────────────

def _load_hero_config() -> None:
    global _hero_slots, _hero_config_dirty, _hero_config_status
    if not os.path.exists(_HERO_CONFIG_PATH):
        _hero_config_status = ""
        return
    try:
        with open(_HERO_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _hero_slots = _parse_hero_config_entries(raw)
        _hero_config_dirty = False
        _hero_config_status = "Loaded."
    except Exception as exc:
        _hero_config_status = f"Load error: {exc}"


def _save_hero_config() -> None:
    global _hero_config_dirty, _hero_config_status
    payload = [{"hero_id": int(s.hero_id), "template": s.template} for s in _hero_slots]
    try:
        os.makedirs(os.path.dirname(_HERO_CONFIG_PATH), exist_ok=True)
        with open(_HERO_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        _hero_config_dirty = False
        _hero_config_status = "Saved."
    except Exception as exc:
        _hero_config_status = f"Save error: {exc}"


def _reset_hero_config() -> None:
    global _hero_slots, _hero_config_dirty, _hero_config_status
    _hero_slots = [_PartyHeroSlot() for _ in range(_HERO_SLOTS_COUNT)]
    _hero_config_dirty = True
    _hero_config_status = "Reset to empty."


def _parse_hero_config_entries(raw: object) -> list[_PartyHeroSlot]:
    slots: list[_PartyHeroSlot] = []
    for i in range(_HERO_SLOTS_COUNT):
        entry = raw[i] if isinstance(raw, list) and i < len(raw) else {}
        hero_id = int(entry.get("hero_id", 0) or 0)
        if hero_id not in _HERO_ID_TO_OPTION_INDEX:
            hero_id = 0
        slots.append(_PartyHeroSlot(hero_id=hero_id, template=str(entry.get("template", "") or "")))
    return slots


def _list_importable_hero_configs() -> list[str]:
    try:
        files = [
            os.path.join(_BOT_SCRIPT_DIR, e)
            for e in os.listdir(_BOT_SCRIPT_DIR)
            if e.endswith(" Heroes.json") and os.path.isfile(os.path.join(_BOT_SCRIPT_DIR, e))
        ]
        files.sort(key=lambda p: os.path.basename(p).lower())
        return files
    except OSError:
        return []


def _hero_import_label(path: str) -> str:
    name = os.path.splitext(os.path.basename(path))[0]
    return name[:-7] if name.endswith(" Heroes") else name


def _import_hero_config(path: str) -> None:
    global _hero_slots, _hero_config_dirty, _hero_config_status
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _hero_slots = _parse_hero_config_entries(raw)
        _hero_config_dirty = True
        _save_hero_config()
        _hero_config_status = f"Imported from {_hero_import_label(path)} and saved."
    except Exception as exc:
        _hero_config_status = f"Import error: {exc}"


def _get_hero_icon_path(hero_id: int) -> str | None:
    try:
        hero_type = HeroType(hero_id)
    except ValueError:
        return None
    filename = _HERO_ICON_FILENAMES.get(hero_type)
    if not filename:
        return None
    path = os.path.join(_HERO_ICONS_BASE, filename)
    return path if os.path.exists(path) else None


def _draw_hero_icon(hero_id: int, size: int = 24) -> None:
    path = _get_hero_icon_path(hero_id)
    if path:
        try:
            cx, cy = PyImGui.get_cursor_screen_pos()
            ImGui.DrawTextureInDrawList(pos=(float(cx), float(cy)), size=(float(size), float(size)), texture_path=path)
        except Exception:
            try:
                ImGui.DrawTexture(texture_path=path, width=size, height=size)
            except Exception:
                pass
    PyImGui.dummy((int(size), int(size)))


def _draw_hero_combo(label: str, hero_id: int) -> int:
    current_index = _HERO_ID_TO_OPTION_INDEX.get(hero_id, 0)
    preview = _HERO_OPTION_LABELS[current_index]
    if PyImGui.begin_combo(label, preview, PyImGui.ImGuiComboFlags.NoFlag):
        for index, hero in enumerate(_HERO_OPTIONS):
            if hero != HeroType.None_:
                _draw_hero_icon(int(hero), size=20)
            else:
                PyImGui.dummy((20, 20))
            PyImGui.same_line(0.0, 8.0)
            if PyImGui.selectable(f"{_HERO_OPTION_LABELS[index]}##{label}_{index}", index == current_index, 0, [0.0, 0.0]):
                current_index = index
        PyImGui.end_combo()
    return int(_HERO_OPTIONS[current_index])


def _draw_hero_slot_editor(slot_index: int) -> None:
    global _hero_config_dirty
    slot = _hero_slots[slot_index]
    combo_label_width = 70.0

    PyImGui.text(f"Hero {slot_index + 1}")
    PyImGui.same_line(combo_label_width, 8.0)
    _draw_hero_icon(slot.hero_id, size=24)
    PyImGui.same_line(0.0, 8.0)
    PyImGui.set_next_item_width(PyImGui.get_content_region_avail()[0])
    new_hero_id = _draw_hero_combo(f"##hero_{slot_index}", slot.hero_id)
    if new_hero_id != slot.hero_id:
        slot.hero_id = new_hero_id
        if slot.hero_id == HeroType.None_.value:
            slot.template = ""
        elif not slot.template.strip():
            try:
                hero_type = HeroType(slot.hero_id)
            except ValueError:
                hero_type = HeroType.None_
            slot.template = _DEFAULT_HERO_TEMPLATES.get(hero_type, "")
        _hero_config_dirty = True

    PyImGui.text("Template")
    PyImGui.same_line(0.0, 8.0)
    if PyImGui.small_button(f"Clear##slot_{slot_index}"):
        if slot.hero_id != HeroType.None_.value or slot.template:
            slot.hero_id = HeroType.None_.value
            slot.template = ""
            _hero_config_dirty = True
    PyImGui.set_next_item_width(PyImGui.get_content_region_avail()[0])
    new_template = PyImGui.input_text(f"##template_{slot_index}", slot.template)
    if new_template != slot.template:
        slot.template = new_template
        _hero_config_dirty = True


def _draw_hero_settings_tab() -> None:
    global _hero_import_source_index
    PyImGui.text("Configure up to 7 heroes for Single Account mode.")
    PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (0.7, 0.7, 0.7, 1.0))
    PyImGui.text("Heroes are added in order; duplicates and empty slots are skipped.")
    PyImGui.pop_style_color(1)
    PyImGui.spacing()

    if _hero_config_dirty:
        PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (1.0, 0.8, 0.2, 1.0))
        PyImGui.text("Unsaved changes")
        PyImGui.pop_style_color(1)
    elif _hero_config_status:
        PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (0.6, 0.9, 0.6, 1.0))
        PyImGui.text(_hero_config_status)
        PyImGui.pop_style_color(1)

    if PyImGui.button("Save", 100, 26):
        _save_hero_config()
    PyImGui.same_line(0, 8)
    if PyImGui.button("Reload", 100, 26):
        _load_hero_config()
    PyImGui.same_line(0, 8)
    if PyImGui.button("Reset", 100, 26):
        _reset_hero_config()

    import_paths = _list_importable_hero_configs()
    if import_paths:
        if _hero_import_source_index >= len(import_paths):
            _hero_import_source_index = 0
        import_labels = [_hero_import_label(p) for p in import_paths]
        _hero_import_source_index = PyImGui.combo("Import Team From", _hero_import_source_index, import_labels)
        if PyImGui.button("Import Team", 120, 26):
            _import_hero_config(import_paths[_hero_import_source_index])
    else:
        PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (0.7, 0.7, 0.7, 1.0))
        PyImGui.text("Import Team: save another title bot hero lineup first.")
        PyImGui.pop_style_color(1)

    PyImGui.separator()
    # Fixed height, not -1 ("fill remaining space in the current window"): the outer
    # bot window is WindowFlags.AlwaysAutoResize, so a child sized relative to the
    # window it's helping to size creates a feedback loop -- each frame's measured
    # content height feeds the next frame's window height, compounding into a
    # continuous shrink. A fixed height breaks the loop.
    if PyImGui.begin_child("HeroSlotsChild", (0, 380), True):
        for i in range(_HERO_SLOTS_COUNT):
            _draw_hero_slot_editor(i)
            if i < _HERO_SLOTS_COUNT - 1:
                PyImGui.separator()
    PyImGui.end_child()


def _party_wipe_revive_in_place_node() -> BehaviorTree:
    """Restart the in-progress planner step after a party wipe.

    Tunnels of the Forsaken auto-revives the party at an in-instance shrine at
    the start of the current floor instead of returning them to an outpost, so
    the BottingTree's stock party-wipe recovery service (which waits on
    Map.IsOutpost()) never fires and the planner just keeps ticking the step
    from wherever it left off. This watches the death/defeat flags directly:
    once they clear after a wipe, it requests a restart of whichever named
    step (e.g. 'Floor 2') was active when the wipe happened, via the same
    'restart_step_name_request' blackboard key the stock service uses.

    GW's "defeated" flag also flips momentarily when the party legitimately
    Resigns (e.g. after clearing Floor 3), which would otherwise be
    misdetected as a wipe and force-restart a dungeon step from Piken Square.
    A genuine shrine revive never changes map, while a Resign always leaves
    the dungeon, so the map id at defeat-cleared time gates the restart.
    """
    state: dict = {'active': False, 'step_name': '', 'map_id': 0}

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE
        from Py4GWCoreLib.Routines import Routines
        from Py4GWCoreLib.Map import Map

        if not Map.IsMapReady():
            # Mid map-transition; state isn't reliable, don't act on it.
            return BehaviorTree.NodeState.RUNNING

        is_defeated = bool(
            Routines.Checks.Party.IsPartyWiped()
            or GLOBAL_CACHE.Party.IsPartyDefeated()
        )

        if not state['active']:
            if not is_defeated:
                return BehaviorTree.NodeState.RUNNING
            state['active'] = True
            state['step_name'] = str(node.blackboard.get('current_step_name', '') or '')
            state['map_id'] = Map.GetMapID()
            return BehaviorTree.NodeState.RUNNING

        if is_defeated:
            return BehaviorTree.NodeState.RUNNING

        if state['step_name'] and Map.GetMapID() == state['map_id']:
            node.blackboard['restart_step_name_request'] = state['step_name']
        state['active'] = False
        state['step_name'] = ''
        state['map_id'] = 0
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='PartyWipeReviveInPlace',
            action_fn=_tick,
            aftercast_ms=0,
        )
    )


def _apply_upkeep_config(tree: BottingTree) -> None:
    tree.Config.ConfigureUpkeep(
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=_enabled_consumable_upkeeps(),
        # The stock party-wipe recovery service waits for a return to an
        # outpost before restarting a step, but this dungeon auto-revives
        # the party at an in-instance shrine instead. Use our own
        # _party_wipe_revive_in_place_node service below instead.
        enable_party_wipe_recovery=False,
        heroai_state_logging=False,
    )


def _rebuild_tree_for_party_mode() -> None:
    """Drop the cached BottingTree so ensure_botting_tree() rebuilds it for the new
    party mode."""
    global botting_tree, _tree_party_mode, _heroes_setup_done
    if botting_tree is not None:
        try:
            if botting_tree.IsStarted():
                botting_tree.Stop()
        except Exception:
            pass
    botting_tree = None
    _tree_party_mode = None
    _heroes_setup_done = False


def ensure_botting_tree() -> BottingTree:
    global botting_tree, _tree_party_mode

    if botting_tree is not None and _tree_party_mode != _party_mode:
        _rebuild_tree_for_party_mode()

    if botting_tree is None:
        multi_account = _is_multibox()
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name='MultiAccountSequence',
            repeat=True,
            multi_account=multi_account,
            isolation_enabled=not multi_account,
            configure_fn=_apply_upkeep_config,
        )
        botting_tree.AddServiceTree('PartyWipeReviveInPlace', _party_wipe_revive_in_place_node)
        botting_tree.UI.override_draw_help(_draw_help_page)
        _tree_party_mode = _party_mode

    return botting_tree


def _abandon_quest_node() -> BehaviorTree:
    """Abandon the Dreamer and the Zealot quest so it can be re-taken next loop.
    Skips silently if DREAMER_AND_ZEALOT_QUEST_ID has not been filled in yet."""
    def _action() -> BehaviorTree.NodeState:
        if DREAMER_AND_ZEALOT_QUEST_ID > 0:
            from Py4GWCoreLib.Quest import Quest
            Quest.AbandonQuest(DREAMER_AND_ZEALOT_QUEST_ID)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(
        BehaviorTree.ActionNode(
            name='AbandonDreamerAndZealot',
            action_fn=_action,
            aftercast_ms=250,
        )
    )


def _local_inventory_state() -> tuple[int, int, int, int]:
    occupied, capacity = Inventory.GetInventorySpace()
    id_kits = sum(int(GLOBAL_CACHE.Inventory.GetModelCount(model_id)) for model_id in ID_KIT_MODEL_IDS)
    salvage_kits = sum(int(GLOBAL_CACHE.Inventory.GetModelCount(model_id)) for model_id in SALVAGE_KIT_MODEL_IDS)
    return int(occupied), int(capacity), int(id_kits), int(salvage_kits)


def _inventory_target_accounts() -> list[tuple[str, str]]:
    """Return every active account as (email, display label), including self."""
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()

    for account in _all_active_accounts():
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        agent_data = getattr(account, "AgentData", None)
        character_name = str(getattr(agent_data, "CharacterName", "") or "").strip()
        targets.append((email, character_name or email))

    local_email = str(Player.GetAccountEmail() or "").strip()
    if local_email and local_email not in seen:
        local_name = str(Player.GetName() or "").strip()
        targets.append((local_email, local_name or local_email))

    return targets


def _inventory_recipient_emails() -> list[str]:
    return [email for email, _label in _inventory_target_accounts()]


def _build_inventory_status(email: str, label: str, state: tuple[int, int, int, int] | None) -> dict[str, object]:
    if state is None:
        occupied = capacity = id_kits = salvage_kits = -1
    else:
        occupied, capacity, id_kits, salvage_kits = (int(value) for value in state)

    available = capacity > 0 and occupied >= 0 and occupied <= capacity
    free_slots = max(0, capacity - occupied) if available else 0

    return {
        "email": str(email),
        "label": str(label),
        "available": available,
        "capacity": capacity,
        "occupied": occupied,
        "free_slots": free_slots,
        "id_kits": id_kits,
        "salvage_kits": salvage_kits,
    }


def _inventory_account_statuses() -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []
    for raw_status in _inventory_status_snapshot.values():
        status = dict(raw_status)
        account_issues: list[str] = []

        if not bool(status.get("available", False)):
            account_issues.append("inventory query unavailable")
        else:
            free_slots = int(status.get("free_slots", 0) or 0)
            id_kits = int(status.get("id_kits", 0) or 0)
            salvage_kits = int(status.get("salvage_kits", 0) or 0)

            if _inventory_min_free_slots > 0 and free_slots < _inventory_min_free_slots:
                account_issues.append(f"free slots {free_slots}/{_inventory_min_free_slots}")
            if _inventory_min_id_kits > 0 and id_kits < _inventory_min_id_kits:
                account_issues.append(f"ID kits {id_kits}/{_inventory_min_id_kits}")
            if _inventory_min_salvage_kits > 0 and salvage_kits < _inventory_min_salvage_kits:
                account_issues.append(f"salvage kits {salvage_kits}/{_inventory_min_salvage_kits}")

        status["issues"] = account_issues
        statuses.append(status)

    return statuses


def _inventory_maintenance_issues() -> list[str]:
    statuses = _inventory_account_statuses()
    if not statuses:
        return ["No active account inventory query result is available."]
    return [f"{status['label']}: {', '.join(status['issues'])}" for status in statuses if status["issues"]]


def _log_inventory_statuses(statuses: list[dict[str, object]]) -> None:
    if not statuses:
        ConsoleLog(MODULE_NAME, "[Inventory] No active account inventory query result is available.", Console.MessageType.Warning, True)
        return

    for status in statuses:
        issues = list(status["issues"])
        result = "MAINTENANCE" if issues else "OK"
        if bool(status.get("available", False)):
            message = (
                f"[Inventory] {status['label']}: free={status['free_slots']}/{status['capacity']}, "
                f"occupied={status['occupied']}, ID kits={status['id_kits']}, "
                f"Expert salvage kits={status['salvage_kits']} -> {result}"
            )
        else:
            message = f"[Inventory] {status['label']}: local inventory query unavailable -> {result}"
        ConsoleLog(MODULE_NAME, message, Console.MessageType.Warning if issues else Console.MessageType.Info, True)


def _query_all_inventory_states_node(name: str, *, timeout_ms: int = _INVENTORY_QUERY_TIMEOUT_MS) -> BehaviorTree:
    """Query real inventory state locally on every active Guild Wars client."""
    state: dict[str, object] = {"started": False, "request_id": "", "sender_email": "", "pending": {}, "results": {}, "started_at": 0.0}

    def _reset() -> None:
        state["started"] = False
        state["request_id"] = ""
        state["sender_email"] = ""
        state["pending"] = {}
        state["results"] = {}
        state["started_at"] = 0.0

    def _finish() -> BehaviorTree.NodeState:
        global _inventory_status_snapshot
        _inventory_status_snapshot = dict(state["results"])
        _reset()
        return BehaviorTree.NodeState.SUCCESS

    def _start() -> None:
        request_id = f"totf_inventory_state_{int(time.monotonic() * 1000)}"
        sender_email = str(Player.GetAccountEmail() or "").strip()
        targets = _inventory_target_accounts()

        results: dict[str, dict[str, object]] = {}
        pending: dict[str, str] = {}

        for email, label in targets:
            if email == sender_email:
                try:
                    local_state = _local_inventory_state()
                except Exception as exc:
                    ConsoleLog(MODULE_NAME, f"[Inventory] Local inventory query failed on {label}: {exc}", Console.MessageType.Error, True)
                    local_state = None
                results[email] = _build_inventory_status(email, label, local_state)
                continue

            if not sender_email:
                results[email] = _build_inventory_status(email, label, None)
                continue

            reset_inventory_state(email, request_id)
            GLOBAL_CACHE.ShMem.SendMessage(
                sender_email, email, SharedCommandType.InventoryQuery,
                (
                    float(ID_KIT_MODEL_IDS[0] if len(ID_KIT_MODEL_IDS) > 0 else 0),
                    float(ID_KIT_MODEL_IDS[1] if len(ID_KIT_MODEL_IDS) > 1 else 0),
                    float(SALVAGE_KIT_MODEL_IDS[0] if SALVAGE_KIT_MODEL_IDS else 0),
                    0.0,
                ),
                ("report_inventory_state", request_id, "", ""),
            )
            pending[email] = label

        state["started"] = True
        state["request_id"] = request_id
        state["sender_email"] = sender_email
        state["pending"] = pending
        state["results"] = results
        state["started_at"] = time.monotonic()

        ConsoleLog(MODULE_NAME, f"[Inventory] Requested real inventory state from {len(targets)} active account(s).", Console.MessageType.Info, True)

    def _tick(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        try:
            if bool(node.blackboard.get("USER_INTERRUPT_ACTIVE", False)):
                _reset()
                return BehaviorTree.NodeState.FAILURE

            if not bool(state["started"]):
                _start()

            pending: dict[str, str] = state["pending"]
            request_id = str(state["request_id"])

            for email in list(pending):
                reply = get_inventory_state(email, request_id)
                if reply is None:
                    continue
                label = pending.pop(email)
                state["results"][email] = _build_inventory_status(email, label, reply)

            if not pending:
                return _finish()

            elapsed_ms = int((time.monotonic() - float(state["started_at"])) * 1000.0)
            if elapsed_ms < max(0, int(timeout_ms)):
                return BehaviorTree.NodeState.RUNNING

            for email, label in list(pending.items()):
                state["results"][email] = _build_inventory_status(email, label, None)
                ConsoleLog(MODULE_NAME, f"[Inventory] Real inventory query timed out for {label}.", Console.MessageType.Warning, True)
            pending.clear()
            return _finish()

        except Exception as exc:
            ConsoleLog(MODULE_NAME, f"[Inventory] Multibox inventory-state query failed: {exc}", Console.MessageType.Error, True)
            return _finish()

    return BehaviorTree(BehaviorTree.ActionNode(name=name, action_fn=_tick, aftercast_ms=_INVENTORY_QUERY_POLL_MS))


def _inventory_maintenance_trigger_node() -> BehaviorTree:
    def _log(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        statuses = _inventory_account_statuses()
        trigger_labels = [str(status["label"]) for status in statuses if status["issues"]]
        recipients = _inventory_recipient_emails()
        trigger_text = ", ".join(trigger_labels) if trigger_labels else "inventory verification"
        recipient_text = ", ".join(str(status["label"]) for status in statuses if str(status["email"]) in recipients)
        ConsoleLog(
            MODULE_NAME,
            f"[Inventory] Maintenance triggered by: {trigger_text}. MerchantRules will run on ALL {len(recipients)} active account(s)"
            + (f": {recipient_text}." if recipient_text else "."),
            Console.MessageType.Warning,
            True,
        )
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name="Log Collective Inventory Maintenance Trigger", action_fn=_log, aftercast_ms=0))


def _inventory_is_healthy_node(name: str, *, log_success: bool = True) -> BehaviorTree:
    def _check(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        statuses = _inventory_account_statuses()
        _log_inventory_statuses(statuses)

        if not statuses:
            ConsoleLog(MODULE_NAME, "Inventory maintenance required - no active account inventory snapshot is available.", Console.MessageType.Warning, True)
            return BehaviorTree.NodeState.FAILURE

        issues = [f"{status['label']}: {', '.join(status['issues'])}" for status in statuses if status["issues"]]
        if issues:
            ConsoleLog(MODULE_NAME, "Inventory maintenance required - " + "; ".join(issues), Console.MessageType.Warning, True)
            return BehaviorTree.NodeState.FAILURE

        if log_success:
            ConsoleLog(MODULE_NAME, "Inventory check passed on every active account.", Console.MessageType.Info, True)
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ConditionNode(name=name, condition_fn=_check))


def _send_widget_state(widget_name: str, *, enabled: bool, refs_key: str) -> BehaviorTree:
    return BTShared.SendAndWait(
        command=SharedCommandType.EnableWidget if enabled else SharedCommandType.DisableWidget,
        extra_data=(widget_name, "", "", ""),
        include_self=True,
        refs_blackboard_key=refs_key,
        timeout_ms=20000,
        poll_interval_ms=100,
        log=True,
    )


def _set_local_auto_inventory_handler(enabled: bool) -> BehaviorTree:
    def _set(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if botting_tree is None:
            return BehaviorTree.NodeState.SUCCESS
        fn = getattr(botting_tree, "SetAutoInventoryHandlerEnabled", None)
        if fn is None:
            return BehaviorTree.NodeState.SUCCESS
        try:
            fn(enabled)
        except Exception:
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.SUCCESS

    return BehaviorTree(BehaviorTree.ActionNode(name="Enable Local Auto Inventory Handler" if enabled else "Disable Local Auto Inventory Handler", action_fn=_set, aftercast_ms=0))


def _restore_inventoryplus_after_merchant(attempt_key: str) -> BehaviorTree:
    return BT.Sequence(
        name="Restore InventoryPlus After MerchantRules",
        children=[
            _send_widget_state(INVENTORY_PLUS_WIDGET_NAME, enabled=True, refs_key=f"{attempt_key}_enable_inventoryplus_refs"),
            _set_local_auto_inventory_handler(True),
        ],
    )


def _run_merchant_rules(attempt_key: str) -> BehaviorTree:
    def _build(node: BehaviorTree.Node) -> BehaviorTree:
        recipients = _inventory_recipient_emails()
        if not recipients:
            ConsoleLog(MODULE_NAME, "[Inventory] MerchantRules aborted: no active account recipients.", Console.MessageType.Error, True)
            return BehaviorTree(BehaviorTree.FailerNode(name="No Active MerchantRules Recipients"))

        request_id = f"totf_inventory_{attempt_key}_{int(time.monotonic() * 1000)}"
        ConsoleLog(MODULE_NAME, f"[Inventory] Dispatching MerchantRules to all {len(recipients)} active account(s).", Console.MessageType.Info, True)
        execute = BTShared.SendAndWait(
            command=SharedCommandType.MerchantRules,
            params=(3.0, 0.0, 0.0, 0.0),
            extra_data=(request_id, "", "0", "0"),
            recipients=recipients,
            include_self=True,
            refs_blackboard_key=f"{attempt_key}_merchant_rules_refs",
            timeout_ms=INVENTORY_MERCHANT_TIMEOUT_MS,
            poll_interval_ms=250,
            log=True,
        )

        return BT.Selector(
            name="Execute MerchantRules And Restore InventoryPlus",
            children=[
                BT.Sequence(name="MerchantRules Completed", children=[execute, _restore_inventoryplus_after_merchant(attempt_key)]),
                BT.Sequence(name="Restore InventoryPlus After MerchantRules Failure", children=[_restore_inventoryplus_after_merchant(f"{attempt_key}_failure"), BehaviorTree(BehaviorTree.FailerNode(name="Propagate MerchantRules Failure"))]),
            ],
        )

    return BT.Subtree(name="Run MerchantRules On All Active Accounts", subtree_fn=_build)


def _inventory_maintenance_attempt(attempt_number: int) -> BehaviorTree:
    attempt_key = f"inventory_attempt_{attempt_number}"
    return BT.Sequence(
        name=f"Inventory Maintenance Attempt {attempt_number}",
        children=[
            BT.LogMessage(message=f"Inventory maintenance attempt {attempt_number}/{INVENTORY_MAINTENANCE_RETRY_COUNT}.", module_name=MODULE_NAME),
            _set_local_auto_inventory_handler(False),
            _send_widget_state(INVENTORY_PLUS_WIDGET_NAME, enabled=False, refs_key=f"{attempt_key}_disable_inventoryplus_refs"),
            _send_widget_state(MERCHANT_RULES_WIDGET_NAME, enabled=True, refs_key=f"{attempt_key}_enable_merchant_rules_refs"),
            BT.Wait(1_000),
            _run_merchant_rules(attempt_key),
            BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS),
            _query_all_inventory_states_node(name=f"Refresh Real Inventories After Attempt {attempt_number}"),
            _inventory_is_healthy_node(f"Verify Inventory After Attempt {attempt_number}", log_success=True),
        ],
    )


def _stop_for_inventory_failure_node() -> BehaviorTree:
    stopped = False

    def _stop(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        nonlocal stopped
        if not stopped:
            stopped = True
            issues = _inventory_maintenance_issues()
            issue_text = "; ".join(issues) if issues else "unknown verification error"
            ConsoleLog(MODULE_NAME, f"Inventory maintenance failed twice. The bot was paused safely. Remaining issue(s): {issue_text}", Console.MessageType.Error, True)

            if botting_tree is not None:
                fn = getattr(botting_tree, "SetAutoInventoryHandlerEnabled", None)
                if callable(fn):
                    try:
                        fn(True)
                    except Exception:
                        pass

            sender_email = str(Player.GetAccountEmail() or "").strip()
            for account in _all_active_accounts():
                receiver_email = str(getattr(account, "AccountEmail", "") or "").strip()
                if not sender_email or not receiver_email:
                    continue
                GLOBAL_CACHE.ShMem.SendMessage(sender_email, receiver_email, SharedCommandType.EnableWidget, (0.0, 0.0, 0.0, 0.0), (INVENTORY_PLUS_WIDGET_NAME, "", "", ""))

            if botting_tree is not None:
                fn = getattr(botting_tree, "Pause", None)
                if callable(fn):
                    try:
                        fn(True)
                    except Exception:
                        pass

        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.ActionNode(name="Pause Bot After Inventory Maintenance Failure", action_fn=_stop, aftercast_ms=0))


def InventoryCheckAndMaintenance() -> BehaviorTree:
    """Query every active account's real inventory; if anyone is below threshold, run
    MerchantRules across the whole party. Ported from LBSS's
    _inventory_check_and_maintenance_node(), itself ported from Shards Of Orr's
    InventoryCheckAndMaintenance(). Shards Of Orr is multibox-only and unconditionally
    leaves party before running merchant, then re-forms it. Tunnels also supports
    Single Account (heroes), where leaving party would eject the heroes for no reason,
    so the leave/re-invite pair is skipped there and only used in Multiboxing."""
    disabled = BehaviorTree(BehaviorTree.ConditionNode(name="Inventory Maintenance Disabled", condition_fn=lambda node: not _inventory_maintenance_enabled))

    maintenance_attempts = [_inventory_maintenance_attempt(n) for n in range(1, INVENTORY_MAINTENANCE_RETRY_COUNT + 1)]
    maintenance_attempts.append(_stop_for_inventory_failure_node())

    maintenance_children: list[BehaviorTree | BehaviorTree.Node] = [_inventory_maintenance_trigger_node()]
    if _is_multibox():
        maintenance_children.append(BT.LeaveParty())
    maintenance_children.append(BT.Wait(INVENTORY_SNAPSHOT_SETTLE_MS))
    maintenance_children.append(BT.Selector(name="Retry Inventory Maintenance At Outpost", children=maintenance_attempts))
    if _is_multibox():
        maintenance_children.append(_multibox_party_setup_node())

    enabled_flow = BT.Sequence(
        name="Enabled Inventory Check And Maintenance",
        children=[
            _query_all_inventory_states_node(name="Query Real Inventory State On Every Active Account"),
            BT.Selector(
                name="Check Inventory Thresholds",
                children=[
                    _inventory_is_healthy_node("Inventory Thresholds Already Satisfied", log_success=True),
                    BT.Sequence(name="Run Inventory Maintenance", children=maintenance_children),
                ],
            ),
        ],
    )

    return _map_guarded_step(
        'Inventory Check And Maintenance Map Guard',
        PIKEN_SQUARE,
        BT.Selector(name="Inventory Check And Maintenance", children=[disabled, enabled_flow]),
    )


def _setup_heroes_node() -> BehaviorTree:
    def _kick() -> BehaviorTree.NodeState:
        GLOBAL_CACHE.Party.Heroes.KickAllHeroes()
        return BehaviorTree.NodeState.SUCCESS

    def _add() -> BehaviorTree.NodeState:
        seen: set[int] = set()
        for slot in _hero_slots:
            hero_id = int(slot.hero_id)
            if hero_id > 0 and hero_id not in seen:
                seen.add(hero_id)
                GLOBAL_CACHE.Party.Heroes.AddHero(hero_id)
        return BehaviorTree.NodeState.SUCCESS

    def _load_templates() -> BehaviorTree.NodeState:
        template_map = {int(s.hero_id): s.template for s in _hero_slots if s.template}
        hero_count = GLOBAL_CACHE.Party.GetHeroCount()
        for pos in range(1, hero_count + 1):
            agent_id = GLOBAL_CACHE.Party.Heroes.GetHeroAgentIDByPartyPosition(pos)
            if agent_id > 0:
                hero_id = GLOBAL_CACHE.Party.Heroes.GetHeroIDByAgentID(agent_id)
                template = template_map.get(hero_id, "")
                if template:
                    GLOBAL_CACHE.SkillBar.LoadHeroSkillTemplate(pos, template)
        return BehaviorTree.NodeState.SUCCESS

    return BTComposite.Sequence(
        BehaviorTree.ActionNode(_kick, aftercast_ms=500, name="KickHeroes"),
        BehaviorTree.ActionNode(_add, aftercast_ms=1000, name="AddHeroes"),
        BehaviorTree.ActionNode(_load_templates, aftercast_ms=500, name="LoadTemplates"),
        name="SetupHeroes",
    )


def _multibox_party_setup_node() -> BehaviorTree:
    """Summon every configured alt account and invite it into the local party."""
    return BT.CreateParty(multibox_invite=True, timeout_ms=30_000, log=True)


def _maybe_setup_party_node() -> BehaviorTree:
    """One-time party setup: heroes for Single Account mode, alt accounts for
    Multiboxing. Heroes only need adding once -- unlike CreateParty (safe/idempotent
    to re-run every loop, which is how alts recover from a real-world disconnect),
    re-kicking and re-adding heroes every loop would be pure waste."""

    def _check_skip() -> bool:
        return _heroes_setup_done

    def _mark_done() -> BehaviorTree.NodeState:
        global _heroes_setup_done
        _heroes_setup_done = True
        return BehaviorTree.NodeState.SUCCESS

    def _build_setup(node: BehaviorTree.Node) -> BehaviorTree:
        return _multibox_party_setup_node() if _is_multibox() else _setup_heroes_node()

    return BehaviorTree(
        BehaviorTree.SelectorNode(
            name="MaybeSetupParty",
            children=[
                BehaviorTree.ConditionNode(_check_skip, name="AlreadySetup"),
                BehaviorTree.SequenceNode(
                    name="DoSetup",
                    children=[
                        BehaviorTree.SubtreeNode(_build_setup, name="SetupSubtree"),
                        BehaviorTree.ActionNode(_mark_done, name="MarkDone"),
                    ],
                ),
            ],
        )
    )


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()
    return BT.Sequence(
        name='Initialize Bot',
        map_id_or_name=PIKEN_SQUARE,
        random_travel=True,
        hard_mode=_use_hard_mode,
        children=[
            bot.Config.Aggressive(multi_account=_is_multibox(), account_isolation=not _is_multibox()),
            _maybe_setup_party_node(),
            _runtime_restock_node(),
            _abandon_quest_node(),
        ],
    )


def _map_guarded_step(
    name: str,
    map_id: int,
    child: BehaviorTree,
    skip_if_in_maps: tuple[int, ...] = (),
) -> BehaviorTree:
    """Run a named step only on its expected map, or accept it as already done when a
    later map is already loaded. Ported from Shards Of Orr's _map_guarded_point.

    Named planner steps can be resumed directly from the BottingTree UI's "Start At"
    dropdown — without this gate, resuming e.g. "Floor 3" while still at Piken Square
    would call VanquishNode/MoveAndExitMap with Tunnels-Level-3 coordinates from the
    wrong map instead of failing loudly. Like Shards Of Orr's version, this only
    protects steps whose prerequisites are already true; it doesn't travel anywhere
    itself, so a resume point still has to be picked responsibly.
    """
    branches: list[BehaviorTree] = [
        BT.Sequence(name=f'{name} - Active Map', children=[BT.IsCurrentMap(map_id=map_id, log=False), child])
    ]
    for later_map_id in skip_if_in_maps:
        branches.append(
            BT.Sequence(
                name=f'{name} - Later Map {later_map_id}',
                children=[BT.IsCurrentMap(map_id=later_map_id, log=False), BT.Succeeder(f'{name}AlreadyPassed')],
            )
        )
    if len(branches) == 1:
        return branches[0]
    return BT.Selector(name=name, children=branches)


def _vanquish_point_steps(
    prefix: str,
    map_id: int,
    points: list[object],
    *,
    clear_area_radius: float = TUNNELS_AGGRO_RANGE,
    skip_if_in_maps: tuple[int, ...] = (),
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """One named planner step per route point. Ported from Shards Of Orr's
    _vanquish_point_steps. Points may be plain (x, y) tuples or
    {'pos': (x, y), 'clear_area_radius': override} dicts, matching what
    BT.VanquishNode itself already accepts per-point (used by Floor 2's
    crowded-room overrides)."""
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []
    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"
        point_pos = point['pos'] if isinstance(point, dict) else point
        point_radius = point['clear_area_radius'] if isinstance(point, dict) else clear_area_radius

        def _build(point_pos=point_pos, point_radius=point_radius, name=name) -> BehaviorTree:
            return _map_guarded_step(
                name,
                map_id,
                BT.VanquishNode([point_pos], clear_area_radius=point_radius, name=name),
                skip_if_in_maps=skip_if_in_maps,
            )

        steps.append((name, _build))
    return steps


def _all_active_accounts() -> list[object]:
    from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE

    try:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(sort_results=False)
    except TypeError:
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
    except Exception:
        accounts = []

    unique: list[object] = []
    seen: set[str] = set()
    for account in accounts or []:
        email = str(getattr(account, "AccountEmail", "") or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        unique.append(account)
    return unique


def _account_map_id(account: object) -> int:
    agent_data = getattr(account, "AgentData", None)
    map_data = getattr(agent_data, "Map", None)
    return int(getattr(map_data, "MapID", 0) or 0)


def _all_accounts_on_map(map_id: int) -> bool:
    accounts = _all_active_accounts()
    return bool(accounts) and all(_account_map_id(a) == int(map_id) for a in accounts)


def _wait_for_all_accounts_on_map(map_id: int, *, name: str, timeout_ms: int = 60000) -> BehaviorTree:
    def _check(node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        if _all_accounts_on_map(map_id):
            return BehaviorTree.NodeState.SUCCESS
        return BehaviorTree.NodeState.RUNNING

    return BehaviorTree(BehaviorTree.WaitUntilNode(name=name, condition_fn=_check, throttle_interval_ms=500, timeout_ms=timeout_ms))


def TheBreachApproach() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    # Walk through Piken Square to the portal, then clear The Breach to the
    # Tunnels entrance.
    breach_route: list[object] = [
        (21264., 3562.),
        (18837., -919.),
        (19213., -4201.),
        (18004., -1686.),
    ]

    def _enter_the_breach() -> BehaviorTree:
        return _map_guarded_step(
            'Enter The Breach Map Guard',
            PIKEN_SQUARE,
            BT.MoveAndExitMap(
                [
                    (21030., 9015.),
                    (20255., 8712.),
                    (20180., 7500.)
                ],
                THE_BREACH,
            ),
            skip_if_in_maps=(THE_BREACH, TUNNELS_LVL_1, TUNNELS_LVL_2, TUNNELS_LVL_3),
        )

    def _use_summoning_stone() -> BehaviorTree:
        return _map_guarded_step('Use Summoning Stone (Breach) Map Guard', THE_BREACH, UseAvailableSummoningStone())

    def _enter_tunnels_level_1() -> BehaviorTree:
        return _map_guarded_step(
            'Enter Tunnels Level 1 Map Guard',
            THE_BREACH,
            BT.MoveAndExitMap((17750., -1416.), TUNNELS_LVL_1),
            skip_if_in_maps=(TUNNELS_LVL_1, TUNNELS_LVL_2, TUNNELS_LVL_3),
        )

    return [
        ('Enter The Breach', _enter_the_breach),
        ('Use Summoning Stone (Breach)', _use_summoning_stone),
        *_vanquish_point_steps('Breach Kill Route', THE_BREACH, breach_route, skip_if_in_maps=(TUNNELS_LVL_1, TUNNELS_LVL_2, TUNNELS_LVL_3)),
        ('Enter Tunnels Level 1', _enter_tunnels_level_1),
    ]


def Floor1ToNPC() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    points: list[object] = [
        (-17442., -4638.),
        (-12710., -6983.),
        (-7836., -9115.),
    ]

    def _use_summoning_stone() -> BehaviorTree:
        return _map_guarded_step('Use Summoning Stone (Floor 1) Map Guard', TUNNELS_LVL_1, UseAvailableSummoningStone(), skip_if_in_maps=(TUNNELS_LVL_2, TUNNELS_LVL_3))

    return [
        ('Use Summoning Stone (Floor 1)', _use_summoning_stone),
        *_vanquish_point_steps('Floor 1 Route A', TUNNELS_LVL_1, points, skip_if_in_maps=(TUNNELS_LVL_2, TUNNELS_LVL_3)),
    ]


def NPCQuest() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    """Accept The Dreamer and the Zealot on all accounts."""
    def _build() -> BehaviorTree:
        return _map_guarded_step(
            'NPC Quest Map Guard',
            TUNNELS_LVL_1,
            BT.MoveAndDialog(
                QUEST_NPC_POS,
                dialog_id=QUEST_ACCEPT_DIALOG,
                target_distance=Range.Area.value,
                multi_account=_is_multibox(),
                log=True,
            ),
            skip_if_in_maps=(TUNNELS_LVL_2, TUNNELS_LVL_3),
        )

    return [('NPC Quest', _build)]


def Floor1ToFloor2() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    def _point(pos: tuple[float, float], label: str, *, with_loot: bool) -> Callable[[], BehaviorTree]:
        def _build() -> BehaviorTree:
            children: list[BehaviorTree | BehaviorTree.Node] = [BT.VanquishNode([pos], clear_area_radius=TUNNELS_AGGRO_RANGE, name=label)]
            if with_loot:
                children.append(BT.LootItems())
            return _map_guarded_step(label, TUNNELS_LVL_1, BT.Sequence(name=label, children=children), skip_if_in_maps=(TUNNELS_LVL_2, TUNNELS_LVL_3))
        return _build

    def _enter_tunnels_level_2() -> BehaviorTree:
        return _map_guarded_step(
            'Enter Tunnels Level 2 Map Guard',
            TUNNELS_LVL_1,
            BT.MoveAndExitMap((-8687., 4700.), TUNNELS_LVL_2),
            skip_if_in_maps=(TUNNELS_LVL_2, TUNNELS_LVL_3),
        )

    return [
        ('Floor 1 to Floor 2 - Point 01', _point((-9672., -3286.), 'Floor 1 to Floor 2 - Point 01', with_loot=True)),
        ('Floor 1 to Floor 2 - Point 02', _point((-11415., -900.), 'Floor 1 to Floor 2 - Point 02', with_loot=True)),
        ('Floor 1 to Floor 2 - Point 03', _point((-10727., -304.), 'Floor 1 to Floor 2 - Point 03', with_loot=True)),
        ('Floor 1 to Floor 2 - Point 04', _point((-8618., 3132.), 'Floor 1 to Floor 2 - Point 04', with_loot=False)),
        ('Enter Tunnels Level 2', _enter_tunnels_level_2),
    ]


def Floor2() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    # Points 8, 9, 10 use RANGE_NEARBY in the original (crowded rooms).
    route: list[object] = [
        (-991.,   10963.),
        (2007.,   15561.),
        (-764.,   17454.),
        (-643.,   20296.),
        (-8922.,  21419.),
        (-17622., 19010.),
        (-18139., 17292.),
        {'pos': (-16466., 15466.), 'clear_area_radius': Range.Nearby.value},
        {'pos': (-7110.,  18292.), 'clear_area_radius': Range.Nearby.value},
        {'pos': (-6065.,  14829.), 'clear_area_radius': Range.Nearby.value},
        (-10273., 14406.),
        (-11164., 16520.),
        (-16715.,  9618.),
        (-16748.,  5350.),
    ]

    def _use_summoning_stone() -> BehaviorTree:
        return _map_guarded_step('Use Summoning Stone (Floor 2) Map Guard', TUNNELS_LVL_2, UseAvailableSummoningStone(), skip_if_in_maps=(TUNNELS_LVL_3,))

    def _enter_tunnels_level_3() -> BehaviorTree:
        return _map_guarded_step(
            'Enter Tunnels Level 3 Map Guard',
            TUNNELS_LVL_2,
            BT.MoveAndExitMap((-16780., 4324.), TUNNELS_LVL_3),
            skip_if_in_maps=(TUNNELS_LVL_3,),
        )

    return [
        ('Use Summoning Stone (Floor 2)', _use_summoning_stone),
        *_vanquish_point_steps('Floor 2 Route', TUNNELS_LVL_2, route, skip_if_in_maps=(TUNNELS_LVL_3,)),
        ('Enter Tunnels Level 3', _enter_tunnels_level_3),
    ]



def Floor3() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    route_a: list[object] = [
        (-11162., 3309.),
        (-10127., 2505.),
        (-17353., -952.),
        (-16644., -3499.),
        (-13208., -4395.),
        (-12436., -5865.),
    ]
    route_b: list[object] = [
        (-13244., -2246.),
        (-10537., -1300.),
        (-10264., -4463.),  # Triggers the beacon
    ]
    route_c: list[object] = [
        (-9819., -1276.),
        (-7260.,  1425.),
        (-3990.,  -940.),
        (-6418., -4303.),
    ]
    route_d: list[object] = [
        (-10642., -8052.),
        (-13186., -8718.),
        (-15949., -8561.),
    ]

    def _use_summoning_stone() -> BehaviorTree:
        return _map_guarded_step('Use Summoning Stone (Floor 3) Map Guard', TUNNELS_LVL_3, UseAvailableSummoningStone())

    def _route_a_loot() -> BehaviorTree:
        return _map_guarded_step('Floor 3 Route A Loot Map Guard', TUNNELS_LVL_3, BT.LootItems())

    def _open_dungeon_door() -> BehaviorTree:
        return _map_guarded_step('Open Dungeon Door Map Guard', TUNNELS_LVL_3, BT.MoveAndInteractWithGadget((-6442., -4281.)))

    def _collect_quest_reward() -> BehaviorTree:
        return _map_guarded_step(
            'Collect Quest Reward Map Guard',
            TUNNELS_LVL_3,
            BT.MoveAndDialog(
                QUEST_REWARD_NPC_POS,
                dialog_id=QUEST_REWARD_DIALOG,
                target_distance=Range.Area.value,
                multi_account=_is_multibox(),
                log=True,
            ),
        )

    def _open_dungeon_chest() -> BehaviorTree:
        return _map_guarded_step(
            'Open Dungeon Chest Map Guard',
            TUNNELS_LVL_3,
            BT.Sequence(
                name='Open Dungeon Chest',
                children=[
                    BT.MoveAndInteractWithGadget(DUNGEON_CHEST_POS, multi_account=_is_multibox(), include_self=True, log=True),
                    BT.LootItems(),
                ],
            ),
        )

    def _resign_to_piken_square() -> BehaviorTree:
        return _map_guarded_step(
            'Resign To Piken Square Map Guard',
            TUNNELS_LVL_3,
            BT.Sequence(
                name='Resign To Piken Square',
                children=[
                    BT.Resign(wait_for_map_load=True, target_map_id=PIKEN_SQUARE, multi_account=_is_multibox()),
                    _wait_for_all_accounts_on_map(PIKEN_SQUARE, name='Wait For Party Return To Piken Square'),
                ],
            ),
        )

    return [
        ('Use Summoning Stone (Floor 3)', _use_summoning_stone),
        *_vanquish_point_steps('Floor 3 Route A', TUNNELS_LVL_3, route_a),
        ('Floor 3 Route A Loot', _route_a_loot),
        *_vanquish_point_steps('Floor 3 Route B', TUNNELS_LVL_3, route_b),
        *_vanquish_point_steps('Floor 3 Route C', TUNNELS_LVL_3, route_c),
        ('Open Dungeon Door', _open_dungeon_door),
        *_vanquish_point_steps('Floor 3 Route D', TUNNELS_LVL_3, route_d),
        ('Collect Quest Reward', _collect_quest_reward),
        ('Open Dungeon Chest', _open_dungeon_chest),
        ('Resign To Piken Square', _resign_to_piken_square),
    ]


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ('Initialize Bot', InitializeBot),
        *TheBreachApproach(),
        *Floor1ToNPC(),
        *NPCQuest(),
        *Floor1ToFloor2(),
        *Floor2(),
        *Floor3(),
        ('Inventory Check And Maintenance', InventoryCheckAndMaintenance),
    ]


def main() -> None:
    global initialized

    if not initialized:
        _load_settings()
        _load_hero_config()
        ensure_botting_tree()
        initialized = True

    tree = ensure_botting_tree()
    tree.tick()
    tree.UI.draw_window(icon_path=TEXTURE, extra_tabs=[('Bot Config', _draw_bot_config), ('Heroes', _draw_hero_settings_tab)])


if __name__ == '__main__':
    main()
