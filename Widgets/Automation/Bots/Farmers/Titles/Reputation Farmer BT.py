# ============================================================================
# Reputation Farmer BT - All-In-One Faction / Title Farmer
# ============================================================================
# A single BottingTree driver that farms any one of the selectable faction
# reputation (title) routes. Each faction is described by a small route
# dataclass; the selected route's planner steps are built with the same BT
# wrappers used by the working Vanguard / Luxon (Mount Qinkai) / Kurzick
# (Drazach Thicket) bots, so almost no bespoke combat code lives here.
#
# The six vanquish-family routes (Vanguard, Asuran, Norn, Deldrimor, Luxon,
# Kurzick) and the two Nightfall bounty loops (Sunspear, Lightbringer) are
# fully implemented with coordinates taken from the existing repo bots.
#
# Combat / movement follow the Nightfall Leveler BT conventions:
#   - ConfigureAggressiveEnv() wraps tree.Config.Aggressive(...)
#   - every fight path is a BT.VanquishNode(...) point list
#   - travel + hard mode via BT.Sequence(map_id_or_name=..., hard_mode=True)
# ============================================================================
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

import os
import json
import types
import PySystem

from Py4GWCoreLib import HeroType, Map, Player, PyImGui
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.enums_src.Title_enums import TitleID, TITLE_TIERS
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as CoreBT
from Sources.ApoSource.ApoBottingLib import wrappers as BT

MODULE_NAME = "Reputation Farmer BT"
MODULE_ICON = "Assets/Textures/Skill_Icons/[1887] - Lightbringers Insight.jpg"
ROUTINE_NAME = "ReputationFarmerSequence"

# Goal for the vanquish-family loop: max faction held on hand, then donate.
FACTION_GOAL = 10_000
VQ_MAX_RUNS = 6

# Canthan faction (Luxon/Kurzick) blessings require bribing the faction priest
# from character gold. Equalize to this amount on hand in the outpost so every
# run can afford the blessing even after the previous run spent the gold.
BLESSING_GOLD = 500

# ---------------------------------------------------------------------------
# Hero team setup (modeled on Outpost Unlocker BT.py)
# ---------------------------------------------------------------------------
BOT_BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
PARTY_FORMATION_CONFIG_PATH = os.path.join(BOT_BASE_DIR, "Reputation Farmer Party Formation.json")

HERO_AGGRESSIVE_MODE = 1  # ForceHeroState behavior: 0=guard, 1=fight, 2=avoid

TEAM_PRESET_SIZES = [4, 6, 8]
TEAM_PRESET_SLOT_COUNTS = {4: 3, 6: 5, 8: 7}

# HeroType enums from Py4GWCoreLib; used for the slot editor combo box.
HERO_OPTIONS: List[HeroType] = [HeroType.None_] + [hero for hero in HeroType if hero != HeroType.None_]
HERO_OPTION_LABELS = [hero.name.replace("_", " ") if hero != HeroType.None_ else "<Empty>" for hero in HERO_OPTIONS]
HERO_ID_TO_OPTION_INDEX = {int(hero.value): index for index, hero in enumerate(HERO_OPTIONS)}

# Default skillbar templates per hero (used when a hero is newly slotted in).
DEFAULT_HERO_TEMPLATES: dict = {
    HeroType.Norgu: "OQBDAawDSvAIgcQ5ZkAFgZAEBA",
    HeroType.Gwen: "OQhkAsC8gFKzJIHM9MdDBcaG4iB",
    HeroType.Vekk: "OgVDI8gsS5AnATPmOHgCAZAFBA",
    HeroType.MasterOfWhispers: "OABDUshnSyBVBoBKgbhVVfCWCA",
    HeroType.Olias: "OAhjQoGYIP3hhWVVaO5EeDTqNA",
    HeroType.Ogden: "OwUUMsG/E4SNgbE3N3ETfQgZAMEA",
    HeroType.Razah: "OAWjMMgMJPYTr3jLcCNdmZgeAA",
    HeroType.Xandra: "OAWjMMgMJPYTr3jLcCNdmZgeAA",
    HeroType.ZhedShadowhoof: "OgVDI8gsS5AnATPmOHgCAZAFBA",
}


@dataclass
class PartyHeroSlot:
    hero_id: int = HeroType.None_.value
    template: str = ""

# Consumable upkeeps (mirrors the shared CONSUMABLE_UPKEEPS list).
from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import CONSUMABLE_UPKEEPS


class Faction(Enum):
    VANGUARD = "vanguard"
    ASURAN = "asuran"
    NORN = "norn"
    DELDRIMOR = "deldrimor"
    LUXON = "luxon"
    KURZICK = "kurzick"
    SUNSPEAR = "sunspear"
    LIGHTBRINGER = "lightbringer"


@dataclass
class Blessing:
    """A faction blessing / shrine point along a vanquish route."""
    pos: Tuple[float, float]
    dialog_id: int = 0x84


@dataclass
class Route:
    key: str
    name: str
    icon: str
    title_id: int
    outpost_id: int
    explorable_id: int
    exit_pos: Tuple[float, float]
    exit_by_name: bool = False
    pre_path: Sequence[Tuple[float, float]] = ()
    blessing_points: Sequence[Blessing] = ()
    kill_path: Sequence[Tuple[float, float]] = ()
    bounty: bool = False
    bounty_pos: Optional[Tuple[float, float]] = None
    bounty_dialog: int = 0x85
    entry_dialog_id: int = 0  # set to a dialog id when the explorable is entered via NPC dialog (e.g. Deldrimor)


# ---------------------------------------------------------------------------
# Route data (coordinates from the existing repo bots)
# ---------------------------------------------------------------------------

# Vanguard - Dalada Uplands (Ebon Vanguard title).
# Source: Vanguard Farm BT.py (DALADA_OUTPOST/MAP + DALADA path).
VANGUARD_ROUTE = Route(
    key="vanguard",
    name="Vanguard",
    icon="[2233] - Ebon Battle Standard of Honor.jpg",
    title_id=TitleID.Ebon_Vanguard,
    outpost_id=648,      # Dalada Uplands outpost
    explorable_id=647,   # Dalada Uplands explorable
    exit_pos=(-15400.0, 13500.0),
    pre_path=[(-16016.0, 17340.0), (-15400.0, 13500.0)],
    blessing_points=[
        Blessing((-14971.0, 11013.0)),
    ],
    kill_path=[
        # Dalada segment 1
        (-14350.5, 12790.6), (-17600.7, 10388.3), (-16649.0, 6485.4), (-16131.3, 2494.2),
        (-13528.1, -571.5), (-15663.4, -3959.4), (-18089.6, -7150.1), (-17921.5, -11167.4),
        (-15917.0, -14662.3), (-13390.84, -16843.04), (-12191.4, -16190.6), (-8482.2, -14675.8),
        (-7746.7, -18628.1), (-4699.0, -15996.0), (-734.2, -16733.1), (3209.2, -17521.2),
        (7204.8, -17236.8), (10660.3, -15173.9), (14231.2, -13323.1), (15486.11, -14122.26),
        (17868.1, -11540.7), (14280.7, -9705.3), (13958.0, -5657.5), (17851.7, -4510.7),
        (14141.2, -2985.1), (10104.9, -2608.4), (10392.6, 1429.8), (14414.1, 923.4),
        (16536.4, 4358.9), (17027.8, 8366.5), (14253.5, 11258.4), (12708.4, 14995.4),
        (8842.1, 16056.3), (5366.9, 18114.6), (2657.9, 15144.8), (-1025.2, 16731.2),
        (1142.8, 13355.0), (-2272.1, 11178.6), (-6246.7, 12038.8), (-8875.1, 15092.1),
        (-9545.32, 16453.30), (-10593.52, 14475.55), (-11859.57, 12183.40), (-9680.6, 11168.8),
        (-7630.3, 7678.4), (-3717.2, 8618.1), (-3227.72, 8829.67), (232.2, 9451.7),
        (4266.0, 9959.4), (8007.6, 8342.5), (4888.8, 5766.7), (1037.3, 4668.6),
        (-2887.1, 3697.4), (-6918.0, 4104.1), (-10897.1, 4922.3), (-14702.6, 6233.5),
        (-10898.6, 4878.2), (-9045.5, 1321.2), (-8657.0, -2712.6), (-5189.2, -611.5),
        (-1172.4, 95.6), (2474.3, 1913.7), (6476.9, 2343.3), (5489.0, -1545.9),
        (5552.4, -5596.4), (7189.7, -9305.8), (8261.67, -12055.48), (5228.1, -5784.1),
        (2164.1, -3177.7), (-1530.8, -4867.3), (156.3, -8499.8), (3819.1, -10133.5),
        (2167.7, -13796.2), (-1821.5, -14135.8), (-5747.9, -13218.7),
    ],
)

# Asuran - Magus Stones / Rata Sum (Asuran title).
# Source: Asura title farm by Wick Divinus.py + EotN storyline BT.
ASURAN_ROUTE = Route(
    key="asuran",
    name="Asuran",
    icon="[2372] - Edification.jpg",
    title_id=TitleID.Asuran,
    outpost_id=640,      # Rata Sum
    explorable_id=569,   # Magus Stones
    exit_pos=(-6062.0, -2688.0),
    blessing_points=[
        Blessing((14901.87, 13126.21)),
    ],
    kill_path=[
        (18825, 6180), (18447, 4537), (18331, 2108), (17526, 143),
        (17205, -1355), (17542, -4865), (15562, -5524), (16270, -6288),
        (17501, -5545), (18111, -8030), (18409, -8474), (18613, -11799),
        (17154, -15669), (14250, -16744), (12186, -14139), (12540, -13440),
        (13234, -9948), (8875, -9065), (8647, -5852), (6939, -3629),
        (8711, -6046), (7616, -8978), (4671, -8699), (-5203, -8280),
        (1534, -5493), (1052, -7074), (-1029, -8724), (-3439, -10339),
        (-3024, -12586), (-742, -13786), (-2755, -14099), (-3393, -15633),
        (-4635, -16643), (-7814, -17796), (-10109, -17520), (-9111, -17237),
        (-10963, -15506), (-13975, -17857), (-11912, -10641), (-8760, -9933),
        (-14030, -9780), (-12368, -7330), (-16527, -8175), (-17391, -5984),
        (-15704, -3996), (-16609, -2607), (-16480, 2522), (-17090, 5252),
        (-18640, 8724), (-18484, 12021), (-17180, 13093), (-15072, 14075),
        (-11888, 15628), (-12043, 18463), (-8876, 17415), (-4770, 20353),
        (-10970, 16860), (-9301, 15054), (-9942, 12561), (-9786, 10297),
        (-5379, 16642), (-2828, 18210), (-4246, 16728), (-2974, 14197),
        (-5228, 12475), (-6756, 12380), (-3468, 10837), (-3804, 8017),
        (-3288, 7276), (-1346, 12360), (874, 14367), (3572, 13698),
        (5899, 14205), (7407, 11867), (9541, 9027), (12639, 7537),
        (9064, 7312), (7986, 4365), (8558, 2759), (10685, 3500),
        (10202, 5369), (8043, 5949), (7978, 3339), (6341, 3029),
        (5362, 3391), (7097, 92), (8943, -985), (10949, -2056),
        (13780, -5667), (10752, 991), (8193, -841), (3284, -1599),
        (-76, -1498), (578, 719), (1703, 3975), (316, 2489),
        (-1018, -1235), (-3195, -1538), (-6322, -2565), (-11414, 4055),
        (-7030, 8396), (-8689, 11227),
    ],
)

# Norn - Varajar Fells / Olafstead (Norn title).
# Source: Norn title farmer by Wick Divinus.py.
NORN_ROUTE = Route(
    key="norn",
    name="Norn",
    icon="[2373] - Heart of the Norn.jpg",
    title_id=TitleID.Norn,
    outpost_id=645,      # Olafstead
    explorable_id=553,   # Varajar Fells
    exit_pos=(-1500.0, 1250.0),
    pre_path=[(-328.0, 1240.0), (-1500.0, 1250.0)],
    blessing_points=[
        Blessing((-1892.0, -4505.0)),
    ],
    kill_path=[
        # Source: Norn title farmer by Wick Divinus.py - active routine
        # (excludes blessing dialog steps; those are handled by TakeBlessing)
        (-2034, -4512), (-5278, -5771), (-5456, -7921), (-8793, -5837), (-14092, -9662),
        (-17260, -7906), (-21964, -12877), (-22275, -12462), (-21671, -2163),
        (-19592, 772), (-13795, -751), (-17012, -5376), (-12071, -4274),
        (-8351, -2633), (-4362, -1610), (-4316, 4033), (-8809, 5639),
        (-14916, 2475), (-11282, 5466), (-16051, 6492), (-16934, 11145),
        (-19378, 14555), (-22751, 14163), (-15932, 9386), (-13777, 8097),
        (19416.26, 1142.77), (24169.45, -4288.69), (19745, -2718), (23504, 1801),
    ],
)

# Deldrimor - Depths of Tyria / Sifhalla (Deldrimor title).
# Source: Deldrimor title farm by Wick Divinus.py.
DELDRIMOR_ROUTE = Route(
    key="deldrimor",
    name="Deldrimor",
    icon="[2424] - Stout-Hearted.jpg",
    title_id=TitleID.Deldrimor,
    outpost_id=639,      # Sifhalla
    explorable_id=701,   # Depths of Tyria
    exit_pos=(-23884.0, 13954.0),
    entry_dialog_id=0x84,
    blessing_points=[
        Blessing((-14078.0, 15449.0)),
    ],
    kill_path=[
        (-14804, 10703), (-15628, 9589), (-17602, 6858), (-19769, 5046),
        (-16697.96, 1302.89), (-15090.34, 2057.10), (-14450.00, 3411.00),
        (-13824.00, 924.00), (-13752.06, -504.66), (-12084.77, -1592.58),
        (-12745.70, -3899.97), (-13262.00, -7346.00), (-14891.95, -10069.69),
        (-9573.00, -10963.00), (-15756.00, -12335.00), (-17542.00, -14048.00),
        (-13088.00, -17749.00), (-13004.20, -17304.91), (-11136.00, -18043.00),
        (-7422.59, -18622.13),
    ],
)
# Luxon - Mount Qinkai / Aspenwood Gate (Luxon title).
# Source: VQ Mount Quinkai Redux.py.
LUXON_ROUTE = Route(
    key="luxon",
    name="Luxon",
    icon="[1813] - Lightbringer.jpg",
    title_id=TitleID.Luxon,
    outpost_id=389,      # Aspenwood Gate (Luxon)
    explorable_id=200,   # Mount Qinkai
    exit_pos=(-5490.0, 13672.0),
    blessing_points=[Blessing((-8394.0, -9801.0))],
    kill_path=[
        (-13087.83, -9683.66), (-14952.93, -7771.10), (-16848.37, -9525.87),
        (-11624.00, -3465.98), (-13161.35, -1919.82), (-9122.62, -581.28),
        (-7091.64, 2400.57), (-2916.10, 8324.81), (-8317.40, 8299.81),
        (-10024.89, 2699.75), (-7352.91, 1323.47), (-6666.01, -4688.44),
        (-23.21, -9324.52), (5566.71, -3648.33), (6897.17, -196.10),
        (6243.11, -8762.36), (11648.28, -6957.10), (14615.63, -7808.74),
        (13236.78, -3757.25), (13283.18, 970.89), (10531.36, 8155.91),
        (5295.29, 6138.04), (2336.91, 1077.21), (-372.49, -2613.79),
    ],
)

# Kurzick - Drazach Thicket / Eternal Grove (Kurzick title).
# Source: VQ Drazach Thicket Redux.py.
KURZICK_ROUTE = Route(
    key="kurzick",
    name="Kurzick",
    icon="[1813] - Lightbringer.jpg",
    title_id=TitleID.Kurzick,
    outpost_id=222,      # Eternal Grove outpost
    explorable_id=195,   # Drazach Thicket
    exit_pos=(-7544.0, 14343.0),
    blessing_points=[Blessing((-5592.0, -16263.0))],
    kill_path=[
        (-9878.31, -14870.55), (-6024.71, -10824.51), (-4546.84, -9157.54),
        (-6683.80, -8867.51), (-7756.96, -9672.30), (-5651.87, -6857.37),
        (-6603.41, -5635.55), (-11036.84, -8096.66), (-12024.07, -8840.55),
        (-10875.07, -5594.80), (-10516.25, -2471.60), (-9792.65, -536.86),
        (-11308.45, 3273.95), (-12730.60, 5712.96), (-7237.03, -2142.75),
        (-7105.36, -2426.90), (-4554.99, 776.04), (-1223.03, 2129.13),
        (-1896.83, 5606.69), (-1813.93, -2020.71), (-5234.42, -5652.45),
    ],
)

# Sunspear - Arkjok Ward / Yohlon Haven (Sunspear title bounty loop).
# Source: Sunspear title farm.py + Ewoog's Yohlon Haven Sunspear Title Farm.py.
SUNSPEAR_ROUTE = Route(
    key="sunspear",
    name="Sunspear",
    icon="[1816] - Sunspear Rebirth Signet.jpg",
    title_id=TitleID.Sunspear,
    outpost_id=381,      # Yohlon Haven
    explorable_id=380,   # Arkjok Ward
    exit_pos=(4603.0, 904.0),
    pre_path=[(-998.09, 1505.14)],
    bounty=True,
    bounty_pos=(-17229.18, -12695.88),
    bounty_dialog=0x85,
    kill_path=[
        (-18697.0, -12296.0),
        (-18557.0, -10503.0),
        (-17265.0, -15287.0),
        (-17158.0, -16655.0),
    ],
)

# Lightbringer - Mirror of Lyss / Gate of Pain (Lightbringer title bounty loop).
# Source: Lightbringer - MirrorOfLyss.py.
LIGHTBRINGER_ROUTE = Route(
    key="lightbringer",
    name="Lightbringer",
    icon="[1813] - Lightbringer.jpg",
    title_id=TitleID.Lightbringer,
    outpost_id=433,      # Gate of Pain
    explorable_id=419,   # Mirror of Lyss
    exit_pos=(-4779.0, -1726.0),
    bounty=True,
    bounty_pos=(19505.0, 11209.0),
    bounty_dialog=0x85,
    kill_path=[
        (15914.0, 10322.0),
        (12202.0, 8074.0),
        (13750.0, 5535.0),
        (13277.0, 3332.0),
        (11737.0, 1475.0),
        (10912.0, 3648.0),
        (20100.0, 7990.0),
        (19201.0, 733.0),
        (20273.0, -5210.0),
        (16293.0, -5574.0),
        (19066.0, -12837.0),
    ],
)

ALL_ROUTES: List[Route] = [
    VANGUARD_ROUTE,
    ASURAN_ROUTE,
    NORN_ROUTE,
    DELDRIMOR_ROUTE,
    LUXON_ROUTE,
    KURZICK_ROUTE,
    SUNSPEAR_ROUTE,
    LIGHTBRINGER_ROUTE,
]

def _route_by_key(key: str) -> Optional[Route]:
    for route in ALL_ROUTES:
        if route.key == key:
            return route
    return None
# ---------------------------------------------------------------------------
# Runtime state
# ---------------------------------------------------------------------------
botting_tree: Optional[BottingTree] = None
initialized: bool = False

# Selected faction (persisted across frames).
selected_key: str = "vanguard"

# Party mode: False = single account with hero team, True = multibox accounts.
_multi_account: bool = False


# ---------------------------------------------------------------------------
# Faction point getters
# ---------------------------------------------------------------------------
def _kurzick_faction() -> int:
    try:
        return int(Player.GetKurzickData()[0] or 0)
    except Exception:
        return 0


def _luxon_faction() -> int:
    try:
        return int(Player.GetLuxonData()[0] or 0)
    except Exception:
        return 0


def _title_points(route: Route) -> int:
    try:
        title = Player.GetTitle(route.title_id)
        return int(title.current_points or 0) if title else 0
    except Exception:
        return 0


def _faction_points(route: Route) -> int:
    """Current faction buffer relevant to a route's reward loop."""
    if route.key == "kurzick":
        return _kurzick_faction()
    if route.key == "luxon":
        return _luxon_faction()
    return _title_points(route)


# ---------------------------------------------------------------------------
# Environment + reusable vanquish run
# ---------------------------------------------------------------------------
def AggressiveEnv() -> Sequence[BehaviorTree]:
    """Aggressive env template (used only once we are on an explorable map)."""
    return [
        ensure_botting_tree().Config.Aggressive(multi_account=_multi_account, auto_loot=True),
    ]


# ---------------------------------------------------------------------------
# Hero team setup (modeled on Outpost Unlocker BT.py)
# ---------------------------------------------------------------------------

def _normalize_team_size(party_size: int) -> int:
    if party_size <= 4:
        return 4
    if party_size <= 6:
        return 6
    return 8


def _build_default_party_formations() -> "Dict[int, List[PartyHeroSlot]]":
    gwen = PartyHeroSlot(hero_id=HeroType.Gwen.value, template=DEFAULT_HERO_TEMPLATES.get(HeroType.Gwen, ""))
    vekk = PartyHeroSlot(hero_id=HeroType.Vekk.value, template=DEFAULT_HERO_TEMPLATES.get(HeroType.Vekk, ""))
    olias = PartyHeroSlot(hero_id=HeroType.Olias.value, template=DEFAULT_HERO_TEMPLATES.get(HeroType.Olias, ""))
    norgu = PartyHeroSlot(hero_id=HeroType.Norgu.value, template=DEFAULT_HERO_TEMPLATES.get(HeroType.Norgu, ""))
    mow = PartyHeroSlot(hero_id=HeroType.MasterOfWhispers.value, template=DEFAULT_HERO_TEMPLATES.get(HeroType.MasterOfWhispers, ""))
    razah = PartyHeroSlot(hero_id=HeroType.Razah.value, template=DEFAULT_HERO_TEMPLATES.get(HeroType.Razah, ""))
    ogden = PartyHeroSlot(hero_id=HeroType.Ogden.value, template=DEFAULT_HERO_TEMPLATES.get(HeroType.Ogden, ""))
    return {
        4: [PartyHeroSlot(gwen.hero_id, gwen.template), PartyHeroSlot(vekk.hero_id, vekk.template), PartyHeroSlot(olias.hero_id, olias.template)],
        6: [PartyHeroSlot(gwen.hero_id, gwen.template), PartyHeroSlot(norgu.hero_id, norgu.template), PartyHeroSlot(mow.hero_id, mow.template), PartyHeroSlot(olias.hero_id, olias.template), PartyHeroSlot(razah.hero_id, razah.template)],
        8: [PartyHeroSlot(norgu.hero_id, norgu.template), PartyHeroSlot(gwen.hero_id, gwen.template), PartyHeroSlot(vekk.hero_id, vekk.template), PartyHeroSlot(mow.hero_id, mow.template), PartyHeroSlot(olias.hero_id, olias.template), PartyHeroSlot(razah.hero_id, razah.template), PartyHeroSlot(ogden.hero_id, ogden.template)],
    }


class Settings:
    def __init__(self) -> None:
        self.party_formations: "Dict[int, List[PartyHeroSlot]]" = _build_default_party_formations()
        self.party_config_dirty: bool = False
        self.party_config_status: str = ""

    def get_party_slots(self, team_size: int) -> List[PartyHeroSlot]:
        slot_count = TEAM_PRESET_SLOT_COUNTS.get(team_size, TEAM_PRESET_SLOT_COUNTS[8])
        slots = self.party_formations.get(team_size)
        if slots is None or len(slots) != slot_count:
            defaults = _build_default_party_formations()
            slots = [PartyHeroSlot(slot.hero_id, slot.template) for slot in defaults[team_size]]
            self.party_formations[team_size] = slots
        return slots

    def reset_party_formations(self) -> None:
        self.party_formations = _build_default_party_formations()
        self.party_config_dirty = True
        self.party_config_status = "Party presets reset to defaults. Save to keep them."

    def load_party_formations(self) -> None:
        self.party_formations = _build_default_party_formations()
        if not os.path.exists(PARTY_FORMATION_CONFIG_PATH):
            self.save_party_formations()
            return
        try:
            with open(PARTY_FORMATION_CONFIG_PATH, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            for team_size_str, slots in loaded.items():
                team_size = int(team_size_str)
                slot_count = TEAM_PRESET_SLOT_COUNTS.get(team_size, TEAM_PRESET_SLOT_COUNTS[8])
                loaded_slots: List[PartyHeroSlot] = []
                for slot_data in slots:
                    loaded_slots.append(
                        PartyHeroSlot(
                            hero_id=int(slot_data.get("hero_id", 0)),
                            template=str(slot_data.get("template", "")),
                        )
                    )
                if len(loaded_slots) >= slot_count:
                    self.party_formations[team_size] = loaded_slots[:slot_count]
                else:
                    self.party_formations[team_size] = loaded_slots + [
                        PartyHeroSlot() for _ in range(slot_count - len(loaded_slots))
                    ]
        except Exception:
            self.party_formations = _build_default_party_formations()
            self.party_config_status = "Failed to load party formation config. Using defaults."
            self.party_config_dirty = True

    def save_party_formations(self) -> None:
        serializable = {
            str(team_size): [
                {"hero_id": slot.hero_id, "template": slot.template}
                for slot in slots
            ]
            for team_size, slots in self.party_formations.items()
        }
        try:
            os.makedirs(os.path.dirname(PARTY_FORMATION_CONFIG_PATH), exist_ok=True)
            with open(PARTY_FORMATION_CONFIG_PATH, "w", encoding="utf-8") as handle:
                json.dump(serializable, handle, indent=2, sort_keys=True)
                handle.write("\n")
            self.party_config_dirty = False
            self.party_config_status = "Party formation saved."
        except Exception:
            self.party_config_status = "Failed to save party formation."
            self.party_config_dirty = True


settings = Settings()


def _party_setup(route: Route) -> List[BehaviorTree]:
    """Party formation while still in the outpost.

    Multibox mode summons/invites the configured accounts; single-account
    mode loads the hero team (leader-only, outpost-gated).
    """
    if _multi_account:
        return [BT.CreateParty(multibox_invite=True)]
    return [SetupHeroTeam()]


def SetupHeroTeam() -> BehaviorTree:
    # Built lazily as a Subtree so Map.GetMaxPartySize() is read when this node
    # TICKS (after the preceding Travel has landed us in the destination
    # outpost), not when the parent sequence is constructed.
    def _build_team(_node: BehaviorTree.Node) -> BehaviorTree:
        try:
            team_size = _normalize_team_size(Map.GetMaxPartySize())
        except Exception:
            team_size = 8
        selected_slots: List[PartyHeroSlot] = []
        seen_hero_ids = set()
        for slot in settings.get_party_slots(team_size):
            hero_id = int(slot.hero_id)
            if hero_id <= 0 or hero_id in seen_hero_ids:
                continue
            seen_hero_ids.add(hero_id)
            selected_slots.append(PartyHeroSlot(hero_id=hero_id, template=slot.template.strip()))
        hero_ids = [slot.hero_id for slot in selected_slots]
        skillbars = [(pos, slot.template) for pos, slot in enumerate(selected_slots, start=1) if slot.template]

        return BT.Sequence(
            name="Setup Hero Team",
            children=[
                BT.LeaveParty(),
                BT.CreateParty(hero_ids=hero_ids, log=False),
                BT.Wait(1000),
                *[BT.LoadHeroSkillbar(position, template) for position, template in skillbars],
                CoreBT.Party.ForceHeroState(HERO_AGGRESSIVE_MODE),
            ],
        )

    return BT.Subtree("Setup Hero Team", _build_team)


def _killing_loop(route: Route) -> BehaviorTree:
    """The vanquish-style farming loop for one faction run.

    Mirrors the Nightfall Leveler / VQFarm convention: travel to outpost,
    cross into the explorable map, take blessings, run the kill path, wait
    out of combat, then resign back to the outpost.
    """
    children: List[BehaviorTree] = [
        BT.Travel(target_map_id=route.outpost_id, random_travel=True, hard_mode=True),
        *_party_setup(route),
    ]
    # Canthan faction routes bribe their faction priest for the blessing. Top up
    # gold to BLESSING_GOLD BEFORE leaving the outpost; storage/no bank access
    # is only available while still in the outpost, so this must precede the
    # exit step below or a run can start too poor to obtain the blessing.
    if route.key in ("kurzick", "luxon"):
        children.append(BT.EqualizeGold(target_gold=BLESSING_GOLD, log=True))
    # Enter the explorable map. Most routes cross a plain zone line, but some
    # (e.g. Deldrimor via Sifhalla) require talking to an NPC at the entrance —
    # move to the entry point, send the dialog, then wait for the map to change.
    if route.entry_dialog_id:
        children.append(BT.Move(route.exit_pos, tolerance=120.0, log=True))
        children.append(BT.DialogAtXY(route.exit_pos, route.entry_dialog_id, target_distance=300.0, log=True))
        children.append(BT.WaitForMapLoad(map_id=route.explorable_id))
    elif route.exit_by_name:
        children.append(
            BT.MoveAndExitMap(route.exit_pos, target_map_name=str(route.explorable_id))
        )
    else:
        children.append(
            BT.MoveAndExitMap(route.exit_pos, target_map_id=route.explorable_id)
        )

    children.extend(AggressiveEnv())

    # Blessings at fixed shrine points. TakeBlessing handles both the Canthan
    # faction priests (luxon/kurzick: bribe + blessing dialog) and the EotN
    # shrines (plain auto-dialog button 0). The EotN path uses SendAutomaticDialog
    # instead of TargetNearestNPCXY, so it works on shrine objects that are not NPCs.
    for blessing in route.blessing_points:
        if route.key in ("kurzick", "luxon"):
            # Let TakeBlessing use its default blessing_dialog_id=0x86 —
            # the Blessing dataclass default (0x84) is the bribe dialog, not
            # the blessing dialog, so we must not forward it here.
            children.append(
                BT.TakeBlessing(
                    blessing.pos,
                    faction=route.key,
                    multi_account=_multi_account,
                )
            )
        else:
            children.append(
                BT.TakeBlessing(
                    blessing.pos,
                    multi_account=_multi_account,
                )
            )

    # The kill path is a VanquishNode list of aggro points.
    if route.kill_path:
        children.append(
            BT.VanquishNode(
                steps=list(route.kill_path),
                name=f"{route.name} Kill Path",
                flag_heroes_to_waypoint=False,
            )
        )

    children.append(BT.WaitUntilOutOfCombat())

    return BT.Sequence(name=f"{route.name} VQ Run", children=children)


def _bounty_loop(route: Route) -> BehaviorTree:
    """One Nightfall bounty run (Sunspear / Lightbringer).

    Mirrors the legacy bounty bots: travel to the outpost, cross into the
    explorable map, accept the bounty from the NPC via dialog, run the kill
    path, then wait out of combat (the next run's Travel returns to the
    outpost, replacing the legacy resign step).
    """
    if route.bounty_pos is None:
        return BT.LogMessage(
            f"{route.name} route has no bounty position configured.",
            module_name=MODULE_NAME,
        )

    children: List[BehaviorTree] = [
        BT.Travel(target_map_id=route.outpost_id, random_travel=True),
    ]
    # Pre-path: optional manual waypoints in the outpost from spawn toward the
    # exit. They steer the autopath around a stuck point before the exit
    # crossing (Sunspear: an NPC in Yohlon Haven). A no-op when unset.
    for point in route.pre_path:
        children.append(BT.Move(point, tolerance=150.0, log=True))
    children.append(BT.MoveAndExitMap(route.exit_pos, target_map_id=route.explorable_id))
    children.extend(AggressiveEnv())
    # Walk into targeting range of the bounty NPC first — DialogAtXY only targets
    # the nearest NPC within target_distance of bounty_pos, so we must get close
    # before it dialogs (otherwise the dialog node times out). Keeping bounty_pos
    # as the anchor also picks the right Wandering Priest (there is one per exit).
    children.append(BT.Move(route.bounty_pos, tolerance=120.0, log=True))
    # Accept the bounty by targeting the nearest Wandering Priest to bounty_pos
    # and sending the bounty dialog (dialog id route.bounty_dialog).
    children.append(
        BT.DialogAtXY(
            route.bounty_pos,
            route.bounty_dialog,
            target_distance=300.0,
            log=True,
            multi_account=_multi_account,
        )
    )

    if route.kill_path:
        children.append(
            BT.VanquishNode(
                steps=list(route.kill_path),
                name=f"{route.name} Bounty Kill Path",
                flag_heroes_to_waypoint=False,
                log=True,
            )
        )

    children.append(BT.WaitUntilOutOfCombat())

    return BT.Sequence(name=f"{route.name} Bounty Run", children=children)
# ---------------------------------------------------------------------------
# Planner step builders
# ---------------------------------------------------------------------------
def _goal_threshold(route: Route) -> Optional[int]:
    """Point threshold at which the route is done.

    Kurzick/Luxon stop at the faction donate cap (FACTION_GOAL). All other
    titles farm until max rank, i.e. the highest tier requirement; with no
    tier data the route never completes on points alone.
    """
    if route.key in ("kurzick", "luxon"):
        return FACTION_GOAL
    tiers = TITLE_TIERS.get(int(route.title_id), [])
    if not tiers:
        return None
    return int(max(tier.required for tier in tiers))


def FarmFaction() -> BehaviorTree:
    route = _route_by_key(selected_key)
    if route is None:
        return BT.LogMessage(f"Unknown faction: {selected_key}", module_name=MODULE_NAME)

    def _goal_reached() -> BehaviorTree.NodeState:
        threshold = _goal_threshold(route)
        if threshold is None:
            return BehaviorTree.NodeState.FAILURE
        return (
            BehaviorTree.NodeState.SUCCESS
            if _faction_points(route) >= threshold
            else BehaviorTree.NodeState.FAILURE
        )

    def _one_run() -> BehaviorTree:
        run_loop = _bounty_loop(route) if route.bounty else _killing_loop(route)
        return BehaviorTree(
            BehaviorTree.SelectorNode(
                name=f"{route.name} Run Or Skip",
                children=[
                    BehaviorTree(BehaviorTree.ActionNode(name="Goal Reached?", action_fn=_goal_reached)),
                    run_loop,
                ],
            )
        )

    # Donation is faction-to-guild (Luxon/Kurzick only, handled by the Donate
    # step). Gold prep for the faction-priest blessing is done inside the
    # killing loop (see _killing_loop), before the route exits the outpost.
    return BT.Sequence(
        name=f"Farm {route.name}",
        children=[
            BT.Repeater(name=f"Farm {route.name}", repeat_count=VQ_MAX_RUNS, children=[_one_run()]),
        ],
    )


# Donation outposts: the shared DonateFaction handler (Messaging.py) only
# donates while standing in the faction's guild hall town.
HOUSE_ZU_HELZER = 77    # Kurzick donation outpost
CAVALON = 193           # Luxon donation outpost


def DonateFaction() -> BehaviorTree:
    route = _route_by_key(selected_key)
    if route is None:
        return BT.LogMessage(f"Unknown faction: {selected_key}", module_name=MODULE_NAME)

    # Only the Canthan factions donate faction on-hand; the rest donate the title
    # currency implicitly by switching the tracked title (converted by title-tracker).
    if route.key not in ("kurzick", "luxon"):
        return BT.Succeeder()

    donation_map = {"kurzick": "kurzick", "luxon": "luxon"}
    travel_map = {"kurzick": HOUSE_ZU_HELZER, "luxon": CAVALON}
    return BT.DonateFaction(
        faction=donation_map[route.key],
        threshold=FACTION_GOAL,
        travel_map_id=travel_map[route.key],
        multi_account=_multi_account,
        log=True,
    )


def get_execution_steps() -> List[Tuple[str, Callable[[], BehaviorTree]]]:
    steps: List[Tuple[str, Callable[[], BehaviorTree]]] = [("Farm Faction", FarmFaction)]
    # Only Luxon/Kurzick donate (faction-to-guild); other routes have no
    # donate step at all, so the routine never touches it.
    route = _route_by_key(selected_key)
    if route is not None and route.key in ("kurzick", "luxon"):
        steps.append(("Donate Faction", DonateFaction))
    return steps
# ---------------------------------------------------------------------------
# Tree creation + UI
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Tree creation + UI
# ---------------------------------------------------------------------------
def _configure_upkeep(tree: BottingTree) -> None:
    tree.Config.ConfigureUpkeep(
        looting_enabled=True,
        resurrection_scroll=True,
        auto_inventory_handler_enabled=True,
        consumable_upkeeps=tuple(int(m) for m in CONSUMABLE_UPKEEPS),
        enable_party_wipe_recovery=True,
    )


def ensure_botting_tree() -> BottingTree:
    global botting_tree
    if botting_tree is None:
        botting_tree = BottingTree.Create(
            MODULE_NAME,
            main_routine=get_execution_steps(),
            routine_name=ROUTINE_NAME,
            repeat=True,
            multi_account=_multi_account,
            auto_loot=True,
            configure_fn=_configure_upkeep,
        )
        botting_tree.UI.override_draw_config(draw_settings_tab)
        # Bind a custom Main-tab body (farm dropdown + Start control) instead
        # of the framework's planner "Start At" step list. Pattern mirrors
        # EOTN_SKILL_UNLOCKER.py.
        botting_tree.UI._draw_main_child = types.MethodType(_draw_main_child_custom, botting_tree.UI)
    return botting_tree


def _draw_party_slot_editor(team_size: int, slot_index: int) -> None:
    slot = settings.get_party_slots(team_size)[slot_index]
    PyImGui.text(f"Hero {slot_index + 1}")
    PyImGui.same_line(90.0, 8.0)
    current_index = HERO_ID_TO_OPTION_INDEX.get(int(slot.hero_id), 0)
    new_index = PyImGui.combo(f"##party_hero_{team_size}_{slot_index}", current_index, HERO_OPTION_LABELS)
    if new_index != current_index:
        hero = HERO_OPTIONS[new_index]
        slot.hero_id = int(hero.value)
        slot.template = "" if hero == HeroType.None_ else DEFAULT_HERO_TEMPLATES.get(hero, slot.template)
        settings.party_config_dirty = True
    PyImGui.text("Template")
    PyImGui.same_line(90.0, 8.0)
    new_template = PyImGui.input_text(f"##party_template_{team_size}_{slot_index}", slot.template)
    if new_template != slot.template:
        slot.template = new_template
        settings.party_config_dirty = True


def draw_party_tab() -> None:
    """Hero team setup tab: pick heroes + skillbar templates per team size."""
    if settings.party_config_dirty:
        PyImGui.text_colored("Unsaved party changes", (1.0, 0.8, 0.2, 1.0))
    elif settings.party_config_status:
        PyImGui.text_colored(settings.party_config_status, (0.6, 0.9, 0.6, 1.0))
    if PyImGui.button("Save Party Formation"):
        settings.save_party_formations()
    PyImGui.same_line(0.0, 8.0)
    if PyImGui.button("Reload Saved"):
        settings.load_party_formations()
    PyImGui.same_line(0.0, 8.0)
    if PyImGui.button("Reset Defaults"):
        settings.reset_party_formations()
    PyImGui.separator()
    if PyImGui.begin_tab_bar("PartyFormationTabs"):
        for team_size in TEAM_PRESET_SIZES:
            if PyImGui.begin_tab_item(f"Team of {team_size}"):
                for slot_index in range(TEAM_PRESET_SLOT_COUNTS[team_size]):
                    _draw_party_slot_editor(team_size, slot_index)
                    PyImGui.separator()
                PyImGui.end_tab_item()
        PyImGui.end_tab_bar()


def draw_settings_tab() -> None:
    """Settings window with the Faction configuration."""
    global selected_key, botting_tree, _multi_account

    if PyImGui.begin_tab_bar("SettingsTabs"):
        if PyImGui.begin_tab_item("Faction"):
            _draw_faction_settings_tab()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()


def _apply_route_selection(new_key: str) -> None:
    """Switch the active faction route and rebuild the planner tree.

    The planner tree is built from the step list once; rebuild it so the
    Donate step only exists for Luxon/Kurzick routes. This resets the routine
    to its first step, which is intended on a faction switch.
    """
    global selected_key, botting_tree
    if new_key == selected_key:
        return
    selected_key = new_key
    ensure_botting_tree().SetMainRoutine(
        get_execution_steps(),
        name=ROUTINE_NAME,
        repeat=True,
    )


def _draw_route_selector() -> None:
    """Radio-list farm picker shared by the Settings and Main tabs."""
    route_index_by_key = {route.key: index for index, route in enumerate(ALL_ROUTES)}
    selected_index = route_index_by_key.get(selected_key, 0)

    for index, route in enumerate(ALL_ROUTES):
        label = route.name + ("  (bounty loop)" if route.bounty else "")
        selected_index = PyImGui.radio_button(label, selected_index, index)

    _apply_route_selection(ALL_ROUTES[selected_index].key)


def _draw_route_readout(route: Route) -> None:
    """Live points / tier / session-goal readout for a selected route."""
    points = _faction_points(route)
    tiers = TITLE_TIERS.get(int(route.title_id), [])
    tier_name = "Unranked"
    for tier in tiers:
        if points >= tier.required:
            tier_name = tier.name
    PyImGui.text(f"{route.name} points: {points:,}")
    PyImGui.text(f"Current tier: {tier_name}")
    threshold = _goal_threshold(route)
    if route.bounty:
        goal = f"max rank ({threshold:,} points)" if threshold is not None else "max rank"
    else:
        goal = f"{threshold:,} points" if threshold is not None else "max rank"
    PyImGui.text(f"Session goal: {goal}")


def _draw_faction_settings_tab() -> None:
    """Faction selector + multibox toggle + live title readout."""
    global selected_key, botting_tree, _multi_account
    PyImGui.text("Faction")
    PyImGui.separator()

    new_multi = PyImGui.checkbox("Multi Account (Multibox) Team", _multi_account)
    if new_multi != _multi_account:
        _multi_account = new_multi
        # multi_account is a creation-time flag: drop the tree so it is
        # recreated with the new party mode on the next ensure call.
        botting_tree = None
    PyImGui.separator()

    _draw_route_selector()

    PyImGui.separator()
    selected = _route_by_key(selected_key)
    if selected is not None:
        _draw_route_readout(selected)


def _draw_main_child_custom(
    self,
    main_child_dimensions=(350, 300),
    icon_path="",
    iconwidth=96,
) -> None:
    """Custom Main-tab body for the Reputation Farmer.

    Bound onto botting_tree.UI in ensure_botting_tree() so the selected farm
    shows as a dropdown where the framework normally draws the planner "Start
    At" list, with the Start control directly below it.
    """
    status = self._main_status_snapshot()
    if PyImGui.begin_table(
        "botting_tree_header_table",
        2,
        PyImGui.TableFlags.RowBg | PyImGui.TableFlags.BordersOuterH,
    ):
        PyImGui.table_setup_column("Icon", PyImGui.TableColumnFlags.WidthFixed, iconwidth)
        PyImGui.table_setup_column("Status", PyImGui.TableColumnFlags.WidthFixed, main_child_dimensions[0] - iconwidth)
        PyImGui.table_next_row()
        PyImGui.table_set_column_index(0)
        self._draw_texture(icon_path, (float(iconwidth), float(iconwidth)))
        PyImGui.table_set_column_index(1)
        PyImGui.text(self.parent.bot_name)
        selected = _route_by_key(selected_key)
        current_farm = selected.name if selected else selected_key
        PyImGui.text(f"Current farm: {current_farm}")
        PyImGui.text(f"HeroAI: {self.parent.GetBlackboardValue('HEROAI_STATUS', 'Idle')}")
        PyImGui.text(f"Planner: {self.parent.GetBlackboardValue('PLANNER_STATUS', 'Idle')}")
        PyImGui.end_table()

    # Selected farm dropdown (replaces the framework "Start At" step list).
    route_index_by_key = {route.key: index for index, route in enumerate(ALL_ROUTES)}
    current_index = route_index_by_key.get(selected_key, 0)
    route_labels = [route.name for route in ALL_ROUTES]
    selected_index = PyImGui.combo("Selected Farm", current_index, route_labels)
    if selected_index != current_index:
        _apply_route_selection(ALL_ROUTES[selected_index].key)

    if self.parent.IsStarted():
        if PyImGui.button("Stop##BottingTreeStop"):
            self.parent.Stop()
        PyImGui.same_line(0, -1)
        if self.parent.IsPaused():
            if PyImGui.button("Resume##BottingTreePause"):
                self.parent.Pause(False)
        else:
            if PyImGui.button("Pause##BottingTreePause"):
                self.parent.Pause(True)
    else:
        if PyImGui.button("Start##BottingTreeStart"):
            self.parent.Start()

    PyImGui.separator()
    self._colored_bool("Started", status["started"])
    self._colored_bool("Paused", status["paused"])
    self._colored_bool("Headless HeroAI Enabled", status["headless_heroai_enabled"])
    self._colored_bool("Looting Enabled", status["looting_enabled"])
    self._colored_bool("Resurrection Scroll Enabled", status["resurrection_scroll_enabled"])
    self._colored_bool("Account Isolation Enabled", status["account_isolation_enabled"])
    self._colored_bool("Pause On Combat Enabled", status["pause_on_combat_enabled"])
    self._colored_bool("Combat Routine Active", status["combat_active"])
    self._colored_bool("Loot Routine Active", status["looting_active"])


def main() -> None:
    global initialized
    if not initialized:
        settings.load_party_formations()
        ensure_botting_tree()
        initialized = True
    tree = ensure_botting_tree()
    tree.tick()
    # Party formation is single-account only; render it as its own top-level
    # tab (the framework appends extra_tabs after the Debug tab).
    extra_tabs = [("Party", draw_party_tab)] if not _multi_account else None
    tree.UI.draw_window(
        icon_path=os.path.join(PySystem.Console.get_projects_path(), MODULE_ICON),
        main_child_dimensions=(520, 420),
        extra_tabs=extra_tabs,
    )


def tooltip() -> str:
    return MODULE_NAME + " - selectable all-in-one faction/title farmer (BT)."
