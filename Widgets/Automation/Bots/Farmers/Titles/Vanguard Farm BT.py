from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Dict, List, Optional
import os
import time

import PySystem

from Py4GWCoreLib import GLOBAL_CACHE, HeroType, ModelID, Player, SharedCommandType
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.ImGui_src.ImGuisrc import ImGui
from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Title_enums import TITLE_TIERS, TitleID
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.py4gwcorelib_src.JsonFactory import JsonFactory
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
from Py4GWCoreLib.routines_src.behaviourtrees_src.items import BTItems
from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import BTShared
from Sources.ApoSource.ApoBottingLib import wrappers as BT


# region Metadata / maps

BOT_NAME = "Vanguard Title Farm BT"
MODULE_NAME = BOT_NAME
MODULE_ICON = "Assets/Textures/Skill_Icons/[2233] - Ebon Battle Standard of Honor.jpg"

REFORGED_TEXTURE = os.path.join(
    PySystem.Console.get_projects_path(),
    "Assets",
    "Textures",
    "Skill_Icons",
    "[2233] - Ebon Battle Standard of Honor.jpg",
)

DALADA_UPLANDS_OUTPOST_ID = 648
DALADA_UPLANDS_MAP_ID = 647

DALADA_UPLANDS_OUTPOST_PATH = [
    (-16016.0, 17340.0),
    (-15400.0, 13500.0),
]

DALADA_SEGMENT_1_BLESS = (-14971.00, 11013.00)
DALADA_SEGMENT_1_PATH = [
    (-14350.5, 12790.6), (-17600.7, 10388.3), (-16649.0, 6485.4), (-16131.3, 2494.2),
    (-13528.1, -571.5), (-15663.4, -3959.4), (-18089.6, -7150.1), (-17921.5, -11167.4),
    (-15917.0, -14662.3), (-13390.84, -16843.04), (-12191.4, -16190.6), (-8482.2, -14675.8), (-7746.7, -18628.1),
    (-4699.0, -15996.0), (-734.2, -16733.1), (3209.2, -17521.2), (7204.8, -17236.8),
    (10660.3, -15173.9), (14231.2, -13323.1), (15486.11, -14122.26), (17868.1, -11540.7), (14280.7, -9705.3),
    (13958.0, -5657.5), (17851.7, -4510.7), (14141.2, -2985.1), (10104.9, -2608.4),
    (10392.6, 1429.8), (14414.1, 923.4), (16536.4, 4358.9), (17027.8, 8366.5),
    (14253.5, 11258.4), (12708.4, 14995.4), (8842.1, 16056.3), (5366.9, 18114.6),
    (2657.9, 15144.8), (-1025.2, 16731.2), (1142.8, 13355.0), (-2272.1, 11178.6),
    (-6246.7, 12038.8), (-8875.1, 15092.1), (-9545.32, 16453.30), (-10593.52, 14475.55), (-11859.57, 12183.40), (-9680.6, 11168.8), (-7630.3, 7678.4),
    (-3717.2, 8618.1), (-3227.72, 8829.67), (232.2, 9451.7), (4266.0, 9959.4), (8007.6, 8342.5),
    (4888.8, 5766.7), (1037.3, 4668.6), (-2887.1, 3697.4), (-6918.0, 4104.1),
    (-10897.1, 4922.3), (-14702.6, 6233.5), (-10898.6, 4878.2), (-9045.5, 1321.2),
    (-8657.0, -2712.6), (-5189.2, -611.5), (-1172.4, 95.6), (2474.3, 1913.7),
    (6476.9, 2343.3), (5489.0, -1545.9), (5552.4, -5596.4), (7189.7, -9305.8), (8261.67, -12055.48),
    (5228.1, -5784.1), (2164.1, -3177.7), (-1530.8, -4867.3), (156.3, -8499.8),
    (3819.1, -10133.5), (2167.7, -13796.2), (-1821.5, -14135.8), (-5747.9, -13218.7),
]

DALADA_SEGMENT_2_BLESS = (-2641.00, 449.00)
DALADA_SEGMENT_2_PATH = [
    (-1172.4, 95.6), (2474.3, 1913.7), (6476.9, 2343.3), (5489.0, -1545.9),
    (5552.4, -5596.4), (7189.7, -9305.8), (8261.67, -12055.48), (5228.1, -5784.1),
    (2164.1, -3177.7), (-1530.8, -4867.3), (156.3, -8499.8), (3819.1, -10133.5),
    (2167.7, -13796.2), (-1821.5, -14135.8), (-5747.9, -13218.7),
]

DALADA_SEGMENT_3_BLESS = (-3954.00, -11426.00)
DALADA_SEGMENT_3_PATH = [
    (-5747.9, -13218.7), (-9790.9, -13258.0), (-11047.5, -9448.2), (-7777.1, -7032.2),
    (-4638.2, -4496.5), (-1131.0, -2524.7), (1852.3, 163.3), (5104.8, 2594.2),
    (8307.3, 5060.4), (7509.3, 8998.1), (10537.1, 11668.0), (8091.5, 8492.2),
    (11725.8, 6705.3), (7964.3, 8157.4), (4666.3, 10422.2),
]

DALADA_SEGMENT_4_BLESS = (5884.00, 11749.00)
DALADA_SEGMENT_4_PATH = [
    (4666.3, 10422.2),
    (1772.7, 13212.8),
]


# endregion


# region Settings

INI_PATH = "Widgets/Automation/Bots/Farmers/Titles/Vanguard Title Farm BT"
INI_FILENAME = "Vanguard_Title_Farm_BT.ini"
_SETTINGS_SECTION = "TitleBotSettings"

_USE_MULTIBOX_KEY = "use_multibox_alts"
_USE_CONSET_KEY = "use_conset"
_USE_PCONS_KEY = "use_pcons"
_CONSET_RESTOCK_TARGET_KEY = "conset_restock_target"
_PCON_RESTOCK_TARGET_KEY = "pcon_restock_target"

_DEFAULT_CONSET_RESTOCK_TARGET = 250
_DEFAULT_PCON_RESTOCK_TARGET = 250
_MAX_CONSUMABLE_RESTOCK_TARGET = 999

_settings = Settings(f"{INI_PATH}/{INI_FILENAME}", "account")

_party_mode = 0  # 0 = Single Account with Heroes, 1 = Multiboxing
_use_conset = False
_use_pcons = False
_conset_restock_target = _DEFAULT_CONSET_RESTOCK_TARGET
_pcon_restock_target = _DEFAULT_PCON_RESTOCK_TARGET
_settings_loaded = False

initialized = False
botting_tree: BottingTree | None = None
_tree_party_mode: int | None = None


def _is_multibox() -> bool:
    return _party_mode == 1


def _load_settings() -> None:
    global _settings_loaded
    global _party_mode, _use_conset, _use_pcons
    global _conset_restock_target, _pcon_restock_target

    if _settings_loaded:
        return

    _party_mode = 1 if _settings.get_bool(_SETTINGS_SECTION, _USE_MULTIBOX_KEY, False) else 0
    _use_conset = _settings.get_bool(_SETTINGS_SECTION, _USE_CONSET_KEY, False)
    _use_pcons = _settings.get_bool(_SETTINGS_SECTION, _USE_PCONS_KEY, False)

    _conset_restock_target = max(
        0,
        min(
            _MAX_CONSUMABLE_RESTOCK_TARGET,
            int(
                _settings.get_int(
                    _SETTINGS_SECTION,
                    _CONSET_RESTOCK_TARGET_KEY,
                    _DEFAULT_CONSET_RESTOCK_TARGET,
                )
            ),
        ),
    )
    _pcon_restock_target = max(
        0,
        min(
            _MAX_CONSUMABLE_RESTOCK_TARGET,
            int(
                _settings.get_int(
                    _SETTINGS_SECTION,
                    _PCON_RESTOCK_TARGET_KEY,
                    _DEFAULT_PCON_RESTOCK_TARGET,
                )
            ),
        ),
    )

    _settings_loaded = True


def _save_settings() -> None:
    _settings.set(_SETTINGS_SECTION, _USE_MULTIBOX_KEY, _is_multibox())
    _settings.set(_SETTINGS_SECTION, _USE_CONSET_KEY, bool(_use_conset))
    _settings.set(_SETTINGS_SECTION, _USE_PCONS_KEY, bool(_use_pcons))
    _settings.set(
        _SETTINGS_SECTION,
        _CONSET_RESTOCK_TARGET_KEY,
        int(_conset_restock_target),
    )
    _settings.set(
        _SETTINGS_SECTION,
        _PCON_RESTOCK_TARGET_KEY,
        int(_pcon_restock_target),
    )


# endregion


# region Hero configuration

# Keep the original hero config path so the legacy bot's saved party can be reused.
_hero_cfg = JsonFactory("Widgets/Bots/Vanguard Title Farm/Heroes.json")
_HERO_ICONS_BASE = os.path.normpath(
    os.path.join(
        PySystem.Console.get_projects_path(),
        "..",
        "Property-of-Wick-Divinus-and-Kendor",
        "PVE Skills Unlocker",
        "Textures",
        "Skill_Icons",
    )
)
_HERO_SLOTS_COUNT = 7


class _PartyHeroSlot:
    __slots__ = ("hero_id", "template")

    def __init__(self, hero_id: int = 0, template: str = "") -> None:
        self.hero_id = hero_id
        self.template = template


def _humanize_hero_name(enum_name: str) -> str:
    if enum_name == "None_":
        return "<Empty>"

    words: List[str] = []
    current = enum_name[0]
    for char in enum_name[1:]:
        if (
            (char.isupper() and not current[-1].isupper())
            or (char.isdigit() and not current[-1].isdigit())
        ):
            words.append(current)
            current = char
        else:
            current += char
    words.append(current)
    return " ".join(words)


_HERO_OPTIONS: List[HeroType] = [HeroType.None_] + sorted(
    [hero for hero in HeroType if hero != HeroType.None_],
    key=lambda hero: _humanize_hero_name(hero.name),
)
_HERO_OPTION_LABELS: List[str] = [
    _humanize_hero_name(hero.name) for hero in _HERO_OPTIONS
]
_HERO_ID_TO_OPTION_INDEX: Dict[int, int] = {
    int(hero): index for index, hero in enumerate(_HERO_OPTIONS)
}

_HERO_ICON_FILENAMES: Dict[HeroType, str] = {
    HeroType.Norgu: "Norgu-icon.jpg",
    HeroType.Goren: "Goren-icon.jpg",
    HeroType.Tahlkora: "Tahlkora-icon.jpg",
    HeroType.MasterOfWhispers: "MasterOfWhispers-icon.jpg",
    HeroType.AcolyteJin: "AcolyteSousuke-icon.jpg",
    HeroType.Koss: "Koss-icon.jpg",
    HeroType.Dunkoro: "Dunkoro-icon.jpg",
    HeroType.AcolyteSousuke: "AcolyteSousuke-icon.jpg",
    HeroType.Melonni: "Melonni-icon.jpg",
    HeroType.ZhedShadowhoof: "ZhedShadowhoof-icon.jpg",
    HeroType.GeneralMorgahn: "GeneralMorgahn-icon.jpg",
    HeroType.MagridTheSly: "MargridTheSly-icon.jpg",
    HeroType.Zenmai: "Zenmai-icon.jpg",
    HeroType.Olias: "Olias-icon.jpg",
    HeroType.Razah: "Razah-icon.jpg",
    HeroType.MOX: "M.O.X.-icon.jpg",
    HeroType.KeiranThackeray: "KeiranThackeray-icon.jpg",
    HeroType.Jora: "Jora-icon.jpg",
    HeroType.PyreFierceshot: "Pyre_Fierceshot-icon.jpg",
    HeroType.Anton: "Anton-icon.jpg",
    HeroType.Livia: "Livia-icon.jpg",
    HeroType.Hayda: "Hayda-icon.jpg",
    HeroType.Kahmu: "Kahmu-icon.jpg",
    HeroType.Gwen: "Gwen-icon.jpg",
    HeroType.Xandra: "Xandra-icon.jpg",
    HeroType.Vekk: "Vekk-icon.jpg",
    HeroType.Ogden: "Ogden_Stonehealer-icon.jpg",
    HeroType.Miku: "Miku-icon.jpg",
    HeroType.ZeiRi: "Zei_Ri-icon.jpg",
}

_DEFAULT_HERO_TEMPLATES: Dict[HeroType, str] = {
    HeroType.Norgu: "OQBDAawDSvAIgcQ5ZkAFgZAEBA",
    HeroType.Gwen: "OQhkAsC8gFKzJIHM9MdDBcaG4iB",
    HeroType.Vekk: "OgVDI8gsS5AnATPmOHgCAZAFBA",
    HeroType.MasterOfWhispers: "OABDUshnSyBVBoBKgbhVVfCWCA",
    HeroType.Olias: "OAhjQoGYIP3hhWVVaO5EeDTqNA",
    HeroType.Ogden: "OwUUMsG/E4SNgbE3N3ETfQgZAMEA",
    HeroType.Razah: "OAWjMMgMJPYTr3jLcCNdmZgeAA",
}

_hero_slots: List[_PartyHeroSlot] = [
    _PartyHeroSlot() for _ in range(_HERO_SLOTS_COUNT)
]
_hero_config_dirty = False
_hero_config_status = ""
_hero_config_loaded = False


def _load_hero_config() -> None:
    global _hero_slots, _hero_config_dirty, _hero_config_status

    raw = _hero_cfg.get_json("slots", [])
    if not raw:
        _hero_config_status = ""
        return

    _hero_slots = _parse_hero_config_entries(raw)
    _hero_config_dirty = False
    _hero_config_status = "Loaded."


def _save_hero_config() -> None:
    global _hero_config_dirty, _hero_config_status

    payload = [
        {"hero_id": int(slot.hero_id), "template": slot.template}
        for slot in _hero_slots
    ]
    _hero_cfg.set_json("slots", payload)
    _hero_config_dirty = False
    _hero_config_status = "Saved."


def _reset_hero_config() -> None:
    global _hero_slots, _hero_config_dirty, _hero_config_status

    _hero_slots = [
        _PartyHeroSlot() for _ in range(_HERO_SLOTS_COUNT)
    ]
    _hero_config_dirty = True
    _hero_config_status = "Reset to empty."


def _parse_hero_config_entries(raw) -> List[_PartyHeroSlot]:
    slots: List[_PartyHeroSlot] = []
    for index in range(_HERO_SLOTS_COUNT):
        entry = raw[index] if isinstance(raw, list) and index < len(raw) else {}
        hero_id = int(entry.get("hero_id", 0) or 0)
        if hero_id not in _HERO_ID_TO_OPTION_INDEX:
            hero_id = 0
        slots.append(
            _PartyHeroSlot(
                hero_id=hero_id,
                template=str(entry.get("template", "") or ""),
            )
        )
    return slots


def _resolved_hero_party() -> tuple[list[int], list[str]]:
    hero_ids: list[int] = []
    templates: list[str] = []
    seen: set[int] = set()

    for slot in _hero_slots:
        hero_id = int(slot.hero_id)
        if hero_id <= 0 or hero_id in seen:
            continue
        seen.add(hero_id)
        hero_ids.append(hero_id)
        templates.append(str(slot.template or ""))

    return hero_ids, templates


# endregion


# region Consumables

CONSET_ITEMS: list[tuple[int, str]] = [
    (int(ModelID.Essence_Of_Celerity.value), "Essence_of_Celerity_item_effect"),
    (int(ModelID.Grail_Of_Might.value), "Grail_of_Might_item_effect"),
    (int(ModelID.Armor_Of_Salvation.value), "Armor_of_Salvation_item_effect"),
]

PCON_ITEMS: list[tuple[int, str]] = [
    (int(ModelID.Birthday_Cupcake.value), "Birthday_Cupcake_skill"),
    (int(ModelID.Golden_Egg.value), "Golden_Egg_skill"),
    (int(ModelID.Candy_Corn.value), "Candy_Corn_skill"),
    (int(ModelID.Candy_Apple.value), "Candy_Apple_skill"),
    (int(ModelID.Slice_Of_Pumpkin_Pie.value), "Pie_Induced_Ecstasy"),
    (int(ModelID.Drake_Kabob.value), "Drake_Skin"),
    (int(ModelID.Bowl_Of_Skalefin_Soup.value), "Skale_Vigor"),
    (int(ModelID.Pahnai_Salad.value), "Pahnai_Salad_item_effect"),
    (int(ModelID.War_Supplies.value), "Well_Supplied"),
]

HONEYCOMB_MODEL_ID = int(ModelID.Honeycomb.value)
RESURRECTION_SCROLL_MODEL_ID = int(ModelID.Scroll_Of_Resurrection.value)


def _enabled_consumable_upkeeps() -> tuple[int, ...]:
    model_ids: list[int] = []
    if _use_conset:
        model_ids.extend(model_id for model_id, _effect in CONSET_ITEMS)
    if _use_pcons:
        model_ids.extend(model_id for model_id, _effect in PCON_ITEMS)
        model_ids.append(HONEYCOMB_MODEL_ID)
    return tuple(dict.fromkeys(int(model_id) for model_id in model_ids))


def _local_restock_tree() -> BehaviorTree:
    items: list[tuple[int, int]] = []

    if _use_conset:
        items.extend(
            (model_id, int(_conset_restock_target))
            for model_id, _effect in CONSET_ITEMS
        )

    if _use_pcons:
        items.extend(
            (model_id, int(_pcon_restock_target))
            for model_id, _effect in PCON_ITEMS
        )
        items.append((HONEYCOMB_MODEL_ID, int(_pcon_restock_target)))
        items.append((RESURRECTION_SCROLL_MODEL_ID, int(_pcon_restock_target)))

    if not items:
        return BT.Succeeder("Consumable Restock Disabled")

    return BT.RestockItemsFromList(
        items,
        allow_missing=True,
    )


def _multibox_restock_tree() -> BehaviorTree:
    children: list[BehaviorTree] = []

    if _use_conset:
        children.append(
            BTShared.SendAndWait(
                command=SharedCommandType.RestockConset,
                params=(float(_conset_restock_target), 0.0, 0.0, 0.0),
                include_self=True,
                refs_blackboard_key="vanguard_restock_conset_refs",
                timeout_ms=30_000,
                poll_interval_ms=100,
                log=True,
            )
        )

    if _use_pcons:
        children.append(
            BTShared.SendAndWait(
                command=SharedCommandType.RestockAllPcons,
                params=(float(_pcon_restock_target), 0.0, 0.0, 0.0),
                include_self=True,
                refs_blackboard_key="vanguard_restock_pcons_refs",
                timeout_ms=30_000,
                poll_interval_ms=100,
                log=True,
            )
        )

    if not children:
        return BT.Succeeder("Multibox Consumable Restock Disabled")

    return BT.Sequence(
        name="Multibox Restock Consumables",
        children=children,
    )


def RestockConsumables() -> BehaviorTree:
    return BT.Subtree(
        name="Restock Consumables If Enabled",
        subtree_fn=lambda _node: (
            _multibox_restock_tree()
            if _is_multibox()
            else _local_restock_tree()
        ),
    )


def _local_use_consumables_tree() -> BehaviorTree:
    consumables: list[tuple[int, str]] = []
    if _use_conset:
        consumables.extend(CONSET_ITEMS)
    if _use_pcons:
        consumables.extend(PCON_ITEMS)
        consumables.append((HONEYCOMB_MODEL_ID, ""))

    if not consumables:
        return BT.Succeeder("Consumable Use Disabled")

    return BTItems.UseConsumables(
        consumables,
        aftercast_ms=100,
    )


def _multibox_use_consumables_tree() -> BehaviorTree:
    consumables: list[tuple[int, str]] = []
    if _use_conset:
        consumables.extend(CONSET_ITEMS)
    if _use_pcons:
        consumables.extend(PCON_ITEMS)
        consumables.append((HONEYCOMB_MODEL_ID, ""))

    children: list[BehaviorTree] = []
    for index, (model_id, effect_name) in enumerate(consumables, start=1):
        effect_id = (
            int(GLOBAL_CACHE.Skill.GetID(effect_name) or 0)
            if effect_name
            else 0
        )
        children.append(
            BTShared.SendAndWait(
                command=SharedCommandType.PCon,
                params=(
                    float(model_id),
                    float(effect_id),
                    0.0,
                    0.0,
                ),
                include_self=True,
                refs_blackboard_key=f"vanguard_use_pcon_{index}_refs",
                timeout_ms=10_000,
                poll_interval_ms=100,
                log=False,
                aftercast_ms=100,
            )
        )

    if not children:
        return BT.Succeeder("Multibox Consumable Use Disabled")

    return BT.Sequence(
        name="Use Multibox Consumables",
        children=children,
    )


def UseConsumablesAtRunStart() -> BehaviorTree:
    return BT.Subtree(
        name="Use Consumables If Enabled",
        subtree_fn=lambda _node: (
            _multibox_use_consumables_tree()
            if _is_multibox()
            else _local_use_consumables_tree()
        ),
    )


# endregion


# region BottingTree setup


def _configure_tree_upkeep(tree: BottingTree) -> BottingTree:
    return tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=_enabled_consumable_upkeeps(),
        enable_party_wipe_recovery=True,
        party_wipe_default_step_name="Enter Dalada Uplands",
        heroai_state_logging=False,
    )


def _refresh_tree_upkeep() -> None:
    if botting_tree is not None:
        _configure_tree_upkeep(botting_tree)


def _rebuild_tree_for_party_mode() -> None:
    global botting_tree, _tree_party_mode

    if botting_tree is not None:
        try:
            if bool(getattr(botting_tree, "started", False)):
                botting_tree.Stop()
        except Exception:
            pass

    botting_tree = None
    _tree_party_mode = None


def ensure_botting_tree() -> BottingTree:
    global botting_tree, _tree_party_mode

    _load_settings()

    if botting_tree is not None and _tree_party_mode != _party_mode:
        _rebuild_tree_for_party_mode()

    if botting_tree is None:
        multi_account = _is_multibox()

        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name=(
                "MultiAccountSequence"
                if multi_account
                else "SingleAccountSequence"
            ),
            repeat=True,
            multi_account=multi_account,
            isolation_enabled=not multi_account,
            configure_fn=_configure_tree_upkeep,
        )
        _tree_party_mode = _party_mode

    return botting_tree


# endregion


# region Planner helpers


def _map_guarded_point(
    name: str,
    child: BehaviorTree,
) -> BehaviorTree:
    return BT.Sequence(
        name=name,
        children=[
            BT.IsCurrentMap(
                map_id=DALADA_UPLANDS_MAP_ID,
                log=False,
            ),
            child,
        ],
    )


def _movement_point_steps(
    prefix: str,
    points: Sequence[tuple[float, float]],
    *,
    move_tolerance: float = 250.0,
) -> list[tuple[str, Callable[[], BehaviorTree]]]:
    steps: list[tuple[str, Callable[[], BehaviorTree]]] = []

    for index, point in enumerate(points, start=1):
        name = f"{prefix} - Point {index:02d}"
        steps.append(
            (
                name,
                lambda point=point, name=name: _map_guarded_point(
                    name,
                    BT.Move(
                        point,
                        pause_on_combat=True,
                        tolerance=move_tolerance,
                        flag_heroes_to_waypoint=False,
                        log=False,
                    ),
                ),
            )
        )

    return steps


# endregion


# region Main routine


def InitializeBot() -> BehaviorTree:
    bot = ensure_botting_tree()

    return BT.Sequence(
        name="Initialize Vanguard Title Farm BT",
        children=[
            bot.Config.Aggressive(
                multi_account=_is_multibox(),
                account_isolation=not _is_multibox(),
                auto_loot=True,
                resurrection_scroll=True,
            ),
            BT.LogMessage(
                message=(
                    "Vanguard Title Farm BT initialized in "
                    + ("Multiboxing" if _is_multibox() else "Single Account + Heroes")
                    + " mode."
                ),
                module_name=MODULE_NAME,
            ),
        ],
    )


def _party_setup_tree() -> BehaviorTree:
    if _is_multibox():
        return BT.CreateParty(
            multibox_invite=True,
            log=True,
        )

    hero_ids, templates = _resolved_hero_party()
    children: list[BehaviorTree] = [
        BT.CreateParty(
            hero_ids=hero_ids,
            multibox_invite=False,
            log=True,
        )
    ]

    for hero_position, template in enumerate(templates, start=1):
        if not template.strip():
            continue
        children.append(
            BT.LoadHeroSkillbar(
                hero_position,
                template,
                log=True,
            )
        )

    return BT.Sequence(
        name="Setup Hero Party",
        children=children,
    )


def PreparePartyAndSupplies() -> BehaviorTree:
    already_in_dalada = BT.Sequence(
        name="Skip Outpost Preparation - Already In Dalada",
        children=[
            BT.IsCurrentMap(
                map_id=DALADA_UPLANDS_MAP_ID,
                log=False,
            ),
            BT.Succeeder("Already In Dalada Uplands"),
        ],
    )

    prepare_from_outpost = BT.Sequence(
        name="Prepare Vanguard Party And Supplies",
        children=[
            BT.Travel(
                target_map_id=DALADA_UPLANDS_OUTPOST_ID,
                hard_mode=True,
                log=True,
            ),
            BT.Subtree(
                name="Setup Party",
                subtree_fn=lambda _node: _party_setup_tree(),
            ),
            RestockConsumables(),
            BT.SetHardMode(
                hard_mode=True,
                log=True,
            ),
        ],
    )

    return BT.Selector(
        name="Prepare Party And Supplies",
        children=[
            already_in_dalada,
            prepare_from_outpost,
        ],
    )


def EnterDaladaUplands() -> BehaviorTree:
    return BT.Selector(
        name="Enter Dalada Uplands",
        children=[
            BT.Sequence(
                name="Already In Dalada Uplands",
                children=[
                    BT.IsCurrentMap(
                        map_id=DALADA_UPLANDS_MAP_ID,
                        log=False,
                    ),
                    BT.Succeeder("Skip Dalada Entry"),
                ],
            ),
            BT.Sequence(
                name="Leave Dalada Outpost",
                children=[
                    BT.IsCurrentMap(
                        map_id=DALADA_UPLANDS_OUTPOST_ID,
                        log=False,
                    ),
                    BT.MoveAndExitMap(
                        DALADA_UPLANDS_OUTPOST_PATH,
                        target_map_id=DALADA_UPLANDS_MAP_ID,
                        flag_heroes_to_waypoint=False,
                        timeout_ms=60_000,
                        log=True,
                    ),
                    BT.Wait(4_000),
                    ensure_botting_tree().Config.Aggressive(
                        multi_account=_is_multibox(),
                        account_isolation=not _is_multibox(),
                        auto_loot=True,
                        resurrection_scroll=True,
                    ),
                    UseConsumablesAtRunStart(),
                ],
            ),
        ],
    )


def _take_vanguard_blessing(
    name: str,
    bless_xy: tuple[float, float],
) -> BehaviorTree:
    x, y = float(bless_xy[0]), float(bless_xy[1])

    return _map_guarded_point(
        name,
        BT.Sequence(
            name=name,
            children=[
                BT.Wait(1_500),
                BT.MoveAndDialog(bless_xy,
                    dialog_id=0x84,
                    multi_account=_is_multibox(),
                    log=True,
                ),
                BT.Wait(250),
            ],
        ),
    )


def Segment1Blessing() -> BehaviorTree:
    return _take_vanguard_blessing(
        "Segment 1 Vanguard Blessing",
        DALADA_SEGMENT_1_BLESS,
    )


def Segment2Blessing() -> BehaviorTree:
    return _take_vanguard_blessing(
        "Segment 2 Vanguard Blessing",
        DALADA_SEGMENT_2_BLESS,
    )


def Segment3Blessing() -> BehaviorTree:
    return _take_vanguard_blessing(
        "Segment 3 Vanguard Blessing",
        DALADA_SEGMENT_3_BLESS,
    )


def Segment4Blessing() -> BehaviorTree:
    return _take_vanguard_blessing(
        "Segment 4 Vanguard Blessing",
        DALADA_SEGMENT_4_BLESS,
    )


def FinishRun() -> BehaviorTree:
    return BT.Sequence(
        name="Finish Vanguard Run",
        children=[
            BT.Resign(
                wait_for_map_load=True,
                target_map_id=DALADA_UPLANDS_OUTPOST_ID,
                multi_account=_is_multibox(),
                timeout_ms=60_000,
                log=True,
            ),
            BT.Wait(5_000),
        ],
    )


def get_execution_steps() -> list[tuple[str, Callable[[], BehaviorTree]]]:
    return [
        ("Initialize Bot", InitializeBot),
        ("Prepare Party And Supplies", PreparePartyAndSupplies),
        ("Enter Dalada Uplands", EnterDaladaUplands),

        ("Segment 1 Blessing", Segment1Blessing),
        *_movement_point_steps(
            "Segment 1 Route",
            DALADA_SEGMENT_1_PATH,
        ),

        ("Segment 2 Blessing", Segment2Blessing),
        *_movement_point_steps(
            "Segment 2 Route",
            DALADA_SEGMENT_2_PATH,
        ),

        ("Segment 3 Blessing", Segment3Blessing),
        *_movement_point_steps(
            "Segment 3 Route",
            DALADA_SEGMENT_3_PATH,
        ),

        ("Segment 4 Blessing", Segment4Blessing),
        *_movement_point_steps(
            "Segment 4 Route",
            DALADA_SEGMENT_4_PATH,
        ),

        ("Finish Run", FinishRun),
    ]


# endregion


# region GUI - Heroes


_EXPANDED_TAB_CHILD_SIZE = (500, 620)


def _get_hero_icon_path(hero_id: int) -> Optional[str]:
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
    import PyImGui

    path = _get_hero_icon_path(hero_id)
    if path:
        try:
            cx, cy = PyImGui.get_cursor_screen_pos()
            ImGui.DrawTextureInDrawList(
                pos=(float(cx), float(cy)),
                size=(float(size), float(size)),
                texture_path=path,
            )
        except Exception:
            try:
                ImGui.DrawTexture(
                    texture_path=path,
                    width=size,
                    height=size,
                )
            except Exception:
                pass

    PyImGui.dummy((int(size), int(size)))


def _draw_hero_combo(label: str, hero_id: int) -> int:
    import PyImGui

    current_index = _HERO_ID_TO_OPTION_INDEX.get(hero_id, 0)
    preview = _HERO_OPTION_LABELS[current_index]

    if PyImGui.begin_combo(
        label,
        preview,
        PyImGui.ImGuiComboFlags.NoFlag,
    ):
        for index, hero in enumerate(_HERO_OPTIONS):
            if hero != HeroType.None_:
                _draw_hero_icon(int(hero), size=20)
            else:
                PyImGui.dummy((20, 20))

            PyImGui.same_line(0.0, 8.0)
            if PyImGui.selectable(
                f"{_HERO_OPTION_LABELS[index]}##{label}_{index}",
                index == current_index,
                0,
                [0.0, 0.0],
            ):
                current_index = index

        PyImGui.end_combo()

    return int(_HERO_OPTIONS[current_index])


def _draw_hero_slot_editor(slot_index: int) -> None:
    import PyImGui
    global _hero_config_dirty

    slot = _hero_slots[slot_index]
    combo_label_width = 70.0

    PyImGui.text(f"Hero {slot_index + 1}")
    PyImGui.same_line(combo_label_width, 8.0)
    _draw_hero_icon(slot.hero_id, size=24)
    PyImGui.same_line(0.0, 8.0)

    PyImGui.set_next_item_width(
        PyImGui.get_content_region_avail()[0]
    )
    new_hero_id = _draw_hero_combo(
        f"##hero_{slot_index}",
        slot.hero_id,
    )

    if new_hero_id != slot.hero_id:
        slot.hero_id = new_hero_id
        if slot.hero_id == HeroType.None_.value:
            slot.template = ""
        elif not slot.template.strip():
            try:
                hero_type = HeroType(slot.hero_id)
            except ValueError:
                hero_type = HeroType.None_
            slot.template = _DEFAULT_HERO_TEMPLATES.get(
                hero_type,
                "",
            )
        _hero_config_dirty = True

    PyImGui.text("Template")
    PyImGui.same_line(0.0, 8.0)

    if PyImGui.small_button(f"Clear##slot_{slot_index}"):
        if slot.hero_id != HeroType.None_.value or slot.template:
            slot.hero_id = HeroType.None_.value
            slot.template = ""
            _hero_config_dirty = True

    PyImGui.set_next_item_width(
        PyImGui.get_content_region_avail()[0]
    )
    new_template = PyImGui.input_text(
        f"##template_{slot_index}",
        slot.template,
    )

    if new_template != slot.template:
        slot.template = new_template
        _hero_config_dirty = True


def _draw_heroes_contents() -> None:
    import PyImGui

    PyImGui.text("Configure up to 7 heroes for Single Account mode.")
    PyImGui.text("Heroes are loaded in order; duplicates and empty slots are skipped.")
    PyImGui.spacing()

    if _hero_config_dirty:
        PyImGui.text_colored(
            "Unsaved changes",
            (1.0, 0.8, 0.2, 1.0),
        )
    elif _hero_config_status:
        PyImGui.text_colored(
            _hero_config_status,
            (0.6, 0.9, 0.6, 1.0),
        )

    if PyImGui.button("Save", 100, 26):
        _save_hero_config()
    PyImGui.same_line(0, 8)

    if PyImGui.button("Reload", 100, 26):
        _load_hero_config()
    PyImGui.same_line(0, 8)

    if PyImGui.button("Reset", 100, 26):
        _reset_hero_config()

    PyImGui.separator()

    if PyImGui.begin_child(
        "VanguardHeroSlotsChild",
        (0, -1),
        True,
    ):
        for index in range(_HERO_SLOTS_COUNT):
            _draw_hero_slot_editor(index)
            if index < _HERO_SLOTS_COUNT - 1:
                PyImGui.separator()
    PyImGui.end_child()


def _draw_heroes_tab() -> None:
    import PyImGui

    if PyImGui.begin_child(
        "VanguardHeroesTabChild",
        _EXPANDED_TAB_CHILD_SIZE,
        False,
    ):
        _draw_heroes_contents()
    PyImGui.end_child()


# endregion


# region GUI - Config


def _draw_config_tab() -> None:
    import PyImGui

    global _party_mode, _use_conset, _use_pcons
    global _conset_restock_target, _pcon_restock_target

    PyImGui.text("Vanguard Title Farm BT")
    PyImGui.separator()

    PyImGui.text("Party Mode")
    new_mode = PyImGui.radio_button(
        "Single Account with Heroes",
        _party_mode,
        0,
    )
    PyImGui.same_line(0, 16)
    new_mode = PyImGui.radio_button(
        "Multiboxing",
        new_mode,
        1,
    )

    if new_mode != _party_mode:
        _party_mode = int(new_mode)
        _save_settings()
        _rebuild_tree_for_party_mode()

    if _is_multibox():
        PyImGui.text_colored(
            "Multibox: accounts are summoned/invited automatically.",
            (0.6, 0.9, 1.0, 1.0),
        )
    else:
        PyImGui.text_colored(
            "Single account: configured heroes are loaded automatically.",
            (0.7, 1.0, 0.7, 1.0),
        )

    PyImGui.separator()
    PyImGui.text("Consumables")

    new_use_conset = PyImGui.checkbox(
        "Restock & use Conset",
        _use_conset,
    )
    if new_use_conset != _use_conset:
        _use_conset = bool(new_use_conset)
        _save_settings()
        _refresh_tree_upkeep()

    new_use_pcons = PyImGui.checkbox(
        "Restock & use Pcons",
        _use_pcons,
    )
    if new_use_pcons != _use_pcons:
        _use_pcons = bool(new_use_pcons)
        _save_settings()
        _refresh_tree_upkeep()

    new_conset_target = PyImGui.input_int(
        "Conset restock target",
        int(_conset_restock_target),
    )
    if new_conset_target != _conset_restock_target:
        _conset_restock_target = max(
            0,
            min(
                _MAX_CONSUMABLE_RESTOCK_TARGET,
                int(new_conset_target),
            ),
        )
        _save_settings()

    new_pcon_target = PyImGui.input_int(
        "Pcons restock target",
        int(_pcon_restock_target),
    )
    if new_pcon_target != _pcon_restock_target:
        _pcon_restock_target = max(
            0,
            min(
                _MAX_CONSUMABLE_RESTOCK_TARGET,
                int(new_pcon_target),
            ),
        )
        _save_settings()

    PyImGui.separator()
    PyImGui.text_wrapped(
        "BT conversion: every Dalada route waypoint is an individual planner step. "
        "A shrine revive can therefore restart the current waypoint instead of "
        "jumping back to the start of the full route."
    )


# endregion


# region Statistics

_session_baselines: dict[str, int] = {}
_session_start_times: dict[str, float] = {}


def _get_title_track_accounts():
    accounts = list(
        GLOBAL_CACHE.ShMem.GetAllAccountData()
        or []
    )

    if _is_multibox():
        return accounts

    own_email = str(Player.GetAccountEmail() or "")
    filtered = [
        account
        for account in accounts
        if str(getattr(account, "AccountEmail", "") or "") == own_email
    ]
    if filtered:
        return filtered

    own_name = str(Player.GetName() or "")
    filtered = [
        account
        for account in accounts
        if str(
            getattr(
                getattr(account, "AgentData", None),
                "CharacterName",
                "",
            )
            or ""
        )
        == own_name
    ]
    if filtered:
        return filtered

    return accounts[:1] if len(accounts) == 1 else []


def _draw_statistics_contents() -> None:
    global _session_baselines, _session_start_times
    import PyImGui

    title_idx = int(TitleID.Ebon_Vanguard)
    tiers = TITLE_TIERS.get(TitleID.Ebon_Vanguard, [])
    now = time.time()
    accounts = _get_title_track_accounts()

    if not accounts:
        PyImGui.text(
            "No local account statistics available yet."
        )
        return

    for account in accounts:
        agent_data = getattr(account, "AgentData", None)
        titles_data = getattr(account, "TitlesData", None)

        name = str(
            getattr(agent_data, "CharacterName", "")
            or getattr(account, "AccountEmail", "")
            or "Unknown"
        )

        try:
            pts = int(
                titles_data.Titles[title_idx].CurrentPoints
            )
        except Exception:
            PyImGui.text(f"{name}: title data unavailable.")
            continue

        if name not in _session_baselines:
            _session_baselines[name] = pts
            _session_start_times[name] = now

        tier_name = "Unranked"
        tier_rank = 0
        next_required = tiers[0].required if tiers else 0

        for index, tier in enumerate(tiers):
            if pts >= tier.required:
                tier_name = tier.name
                tier_rank = index + 1
                next_required = (
                    tiers[index + 1].required
                    if index + 1 < len(tiers)
                    else tier.required
                )
            else:
                next_required = tier.required
                break

        is_maxed = bool(
            tiers and pts >= tiers[-1].required
        )
        gained = pts - _session_baselines[name]
        elapsed = now - _session_start_times[name]
        pts_hr = (
            int(gained / elapsed * 3600)
            if elapsed > 0
            else 0
        )

        tier_missing = max(next_required - pts, 0)
        progress_current = max(pts, 0)
        progress_total = max(next_required, 1)

        PyImGui.separator()
        PyImGui.text(
            f"{name}  [{tier_name} (Rank {tier_rank})]"
        )
        PyImGui.text(f"Total Points: {pts:,}")

        if is_maxed:
            PyImGui.text("Next Rank: Maxed")
            PyImGui.text("Points To Go: 0")
            PyImGui.progress_bar(
                1.0,
                -1,
                0,
                "Complete",
            )
            PyImGui.text_colored(
                "Maximum rank achieved. Title complete.",
                (0.4, 1.0, 0.4, 1.0),
            )
        else:
            PyImGui.text(
                f"Next Rank: {next_required:,}"
            )
            PyImGui.text(
                f"Points To Go: {tier_missing:,}"
            )
            fraction = min(
                progress_current / progress_total,
                1.0,
            )
            PyImGui.progress_bar(
                fraction,
                -1,
                0,
                f"{progress_current:,} / {progress_total:,}",
            )

        PyImGui.text(
            f"+{gained:,}  ({pts_hr:,}/hr)"
        )


def _draw_statistics_tab() -> None:
    import PyImGui

    if PyImGui.begin_child(
        "VanguardStatisticsTabChild",
        _EXPANDED_TAB_CHILD_SIZE,
        False,
    ):
        _draw_statistics_contents()
    PyImGui.end_child()


# endregion


# region Entry point


def main() -> None:
    global initialized, _hero_config_loaded

    if not initialized:
        _load_settings()

        if not _hero_config_loaded:
            _load_hero_config()
            _hero_config_loaded = True

        ensure_botting_tree()
        initialized = True

    if Map.IsMapLoading():
        return

    tree = ensure_botting_tree()
    tree.tick()

    tree.UI.draw_window(
        icon_path=REFORGED_TEXTURE,
        iconwidth=96,
        main_child_dimensions=(500, 420),
        extra_tabs=[
            ("Config", _draw_config_tab),
            ("Statistics", _draw_statistics_tab),
            ("Heroes", _draw_heroes_tab),
        ],
    )


if __name__ == "__main__":
    main()

# endregion