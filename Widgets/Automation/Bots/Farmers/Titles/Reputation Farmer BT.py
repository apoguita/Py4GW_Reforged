# Reputation Farmer BT - All-In-One Faction / Title Farmer
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

import os
import json
import time
import types
import PySystem

from Py4GWCoreLib import GLOBAL_CACHE, HeroType, Map, Player, PyImGui
from Py4GWCoreLib.BottingTree import BottingTree
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree
from Py4GWCoreLib.enums_src.Title_enums import TitleID, TITLE_TIERS
from Py4GWCoreLib.routines_src.BehaviourTrees import BT as CoreBT
from Sources.ApoSource.ApoBottingLib import wrappers as BT

MODULE_NAME = "Reputation Farmer BT"
MODULE_ICON = "Assets/Textures/Skill_Icons/[1887] - Lightbringers Insight.jpg"
ROUTINE_NAME = "ReputationFarmerSequence"

FACTION_GOAL = 10_000
VQ_MAX_RUNS = 6
RUN_RETRY_TIMEOUT_MS = 30 * 60 * 1000
BLESSING_GOLD = 500

# Hero team setup
BOT_BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
PARTY_FORMATION_CONFIG_PATH = os.path.join(BOT_BASE_DIR, "Reputation Farmer Party Formation.json")

HERO_AGGRESSIVE_MODE = 1

TEAM_PRESET_SIZES = [4, 6, 8]
TEAM_PRESET_SLOT_COUNTS = {4: 3, 6: 5, 8: 7}

HERO_OPTIONS: List[HeroType] = [HeroType.None_] + [hero for hero in HeroType if hero != HeroType.None_]
HERO_OPTION_LABELS = [hero.name.replace("_", " ") if hero != HeroType.None_ else "<Empty>" for hero in HERO_OPTIONS]
HERO_ID_TO_OPTION_INDEX = {int(hero.value): index for index, hero in enumerate(HERO_OPTIONS)}

# Default skillbar templates per hero.
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

from Py4GWCoreLib.routines_src.behaviourtrees_src.constants.lists import (
    CONSUMABLE_UPKEEPS,
    CONSET_UPKEEPS,
)

PCON_UPKEEPS: Tuple[int, ...] = tuple(
    int(model_id) for model_id in CONSUMABLE_UPKEEPS if int(model_id) not in CONSET_UPKEEPS
)


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
    pos: Tuple[float, float]
    dialog_id: int = 0x84


@dataclass
class RouteSegment:
    name: str = ""
    blessing: Optional[Blessing] = None
    path: Sequence[Tuple[float, float]] = ()


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
    segments: Sequence[RouteSegment] = ()
    bounty: bool = False
    bounty_pos: Optional[Tuple[float, float]] = None
    bounty_dialog: int = 0x85
    entry_dialog_id: int = 0


# Route data
# Vanguard - Dalada Uplands (Ebon Vanguard title).
VANGUARD_ROUTE = Route(
    key="vanguard",
    name="Vanguard",
    icon="[2233] - Ebon Battle Standard of Honor.jpg",
    title_id=TitleID.Ebon_Vanguard,
    outpost_id=648,      # Dalada Uplands outpost
    explorable_id=647,   # Dalada Uplands explorable
    exit_pos=(-15400.0, 13500.0),
    pre_path=[(-16016.0, 17340.0), (-15400.0, 13500.0)],
    segments=[
        RouteSegment(
            name="Vanguard Segment 1",
            blessing=Blessing((-14971.0, 11013.0)),
            path=[
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
        ),
        RouteSegment(
            name="Vanguard Segment 2",
            blessing=Blessing((-2641.0, 449.0)),
            path=[
                (-1172.4, 95.6), (2474.3, 1913.7), (6476.9, 2343.3), (5489.0, -1545.9),
                (5552.4, -5596.4), (7189.7, -9305.8), (8261.67, -12055.48), (5228.1, -5784.1),
                (2164.1, -3177.7), (-1530.8, -4867.3), (156.3, -8499.8), (3819.1, -10133.5),
                (2167.7, -13796.2), (-1821.5, -14135.8), (-5747.9, -13218.7),
            ],
        ),
        RouteSegment(
            name="Vanguard Segment 3",
            blessing=Blessing((-3954.0, -11426.0)),
            path=[
                (-5747.9, -13218.7), (-9790.9, -13258.0), (-11047.5, -9448.2), (-7777.1, -7032.2),
                (-4638.2, -4496.5), (-1131.0, -2524.7), (1852.3, 163.3), (5104.8, 2594.2),
                (8307.3, 5060.4), (7509.3, 8998.1), (10537.1, 11668.0), (8091.5, 8492.2),
                (11725.8, 6705.3), (7964.3, 8157.4), (4666.3, 10422.2),
            ],
        ),
        RouteSegment(
            name="Vanguard Segment 4",
            blessing=Blessing((5884.0, 11749.0)),
            path=[
                (4666.3, 10422.2),
                (1772.7, 13212.8),
            ],
        ),
    ],
)

# Asuran - Magus Stones / Rata Sum (Asuran title).
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
NORN_ROUTE = Route(
    key="norn",
    name="Norn",
    icon="[2373] - Heart of the Norn.jpg",
    title_id=TitleID.Norn,
    outpost_id=645,      # Olafstead
    explorable_id=553,   # Varajar Fells
    exit_pos=(-1500.0, 1250.0),
    pre_path=[(-328.0, 1240.0), (-1500.0, 1250.0)],
    segments=[
        RouteSegment(
            name="Norn Approach - Shrine 1",
            path=[
                (-2484.73, 118.55), (-3059.12, -419.00), (-3301.01, -2008.23),
                (-2034, -4512),
            ],
        ),
        RouteSegment(
            name="Norn Blessing 1",
            blessing=Blessing((-1892.0, -4505.0)),
            path=[
                (-5278, -5771), (-5456, -7921), (-8793, -5837), (-14092, -9662),
                (-17260, -7906), (-21964, -12877), (-25341.00, -11957.00),
            ],
        ),
        RouteSegment(
            name="Norn Blessing 2",
            blessing=Blessing((-25341.0, -11957.0)),
            path=[
                (-22275, -12462), (-21671, -2163), (-19592, 772), (-13795, -751),
                (-17012, -5376), (-10606.23, -1625.26), (-12158.00, -4277.00),
            ],
        ),
        RouteSegment(
            name="Norn Blessing 3",
            blessing=Blessing((-12158.0, -4277.0)),
            path=[
                (-12071, -4274), (-8351, -2633), (-4362, -1610), (-4316, 4033),
                (-8809, 5639), (-14916, 2475), (-11204.00, 5479.00),
            ],
        ),
        RouteSegment(
            name="Norn Blessing 4",
            blessing=Blessing((-11204.0, 5479.0)),
            path=[
                (-11282, 5466), (-16051, 6492), (-16934, 11145), (-19378, 14555),
                (-22889.00, 14165.00),
            ],
        ),
        RouteSegment(
            name="Norn Blessing 5",
            blessing=Blessing((-22889.0, 14165.0)),
            path=[
                (-22751, 14163), (-15932, 9386), (-13777, 8097), (-2217.00, 14914.00),
            ],
        ),
        RouteSegment(
            name="Norn Blessing 6",
            blessing=Blessing((-2217.0, 14914.0)),
            path=[
                (-2290, 14879), (-1810, 4679), (-6911, 5240), (-15471, 6384),
                (-411, 5874), (2859, 3982), (4909, -4259), (7514, -6587),
                (3800, -6182), (7755, -11467), (15403, -4243),
            ],
        ),
        RouteSegment(
            name="Norn Continue Route - East",
            path=[
                (21597, -6798), (24522, -6532), (22883, -4248), (18606, -1894),
                (14969, -4048), (13599, -7339), (10056, -4967), (10147, -1630),
            ],
        ),
        RouteSegment(
            name="Norn Blessing 8",
            blessing=Blessing((8963.0, 4043.0)),
            path=[
                (9339.46, 3859.12), (15576, 7156),
            ],
        ),
        RouteSegment(
            name="Norn Blessing 9",
            blessing=Blessing((22838.0, 7914.0)),
            path=[
                (22961, 12757), (18067, 8766), (13311, 11917), (13714, 14520),
                (11126, 10443), (5575, 4696), (-503, 9182), (1582, 15275),
                (7857, 10409),
            ],
        ),
    ],
)

# Deldrimor - Depths of Tyria / Umbral Grotto (Deldrimor title).
DELDRIMOR_ROUTE = Route(
    key="deldrimor",
    name="Deldrimor",
    icon="[2424] - Stout-Hearted.jpg",
    title_id=TitleID.Deldrimor,
    outpost_id=639,
    explorable_id=701,
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
    bounty_pos=(-17223.00, -12543.00),
    bounty_dialog=0x85,
    kill_path=[
        (-18697.0, -12296.0),
        (-18557.0, -10503.0),
        (-17265.0, -15287.0),
        (-17158.0, -16655.0),
    ],
)

# Lightbringer - Mirror of Lyss / Gate of Pain (Lightbringer title bounty loop).
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


# The six rank-tracked reputation routes farmed by auto-rotate.
ROTATION_ROUTE_KEYS: Tuple[str, ...] = (
    "vanguard",
    "asuran",
    "norn",
    "deldrimor",
    "sunspear",
    "lightbringer",
)


def _reputation_routes() -> List[Route]:
    return [route for route in ALL_ROUTES if route.key in ROTATION_ROUTE_KEYS]

# Portal proximity gate
def _near_exit_gate(route: Route, radius: float = 1500.0) -> BehaviorTree:

    def _near_exit() -> BehaviorTree.NodeState:
        try:
            player_x, player_y = Player.GetXY()
        except Exception:
            return BehaviorTree.NodeState.FAILURE
        dx = player_x - route.exit_pos[0]
        dy = player_y - route.exit_pos[1]
        return (
            BehaviorTree.NodeState.SUCCESS
            if (dx * dx + dy * dy) <= radius * radius
            else BehaviorTree.NodeState.FAILURE
        )

    return BehaviorTree(
        BehaviorTree.ActionNode(name="Already Near Exit Portal?", action_fn=_near_exit)
    )

# Runtime state
botting_tree: Optional[BottingTree] = None
initialized: bool = False

selected_key: str = "vanguard"
_multi_account: bool = False
_farm_all: bool = False
_target_rank: int = 5
_farm_to_max: bool = False
_active_farm_key: str = ""
_activate_conset: bool = True
_activate_pcons: bool = True


def _enabled_consumable_upkeeps() -> Tuple[int, ...]:
    enabled: List[int] = []
    if _activate_conset:
        enabled.extend(int(model_id) for model_id in CONSET_UPKEEPS)
    if _activate_pcons:
        enabled.extend(PCON_UPKEEPS)
    return tuple(dict.fromkeys(enabled))


# Faction point getters
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
    if route.key == "kurzick":
        return _kurzick_faction()
    if route.key == "luxon":
        return _luxon_faction()
    return _title_points(route)


# NPC approach helper. Bare BT.Move treats the destination NPC as a wall
# (ignore_destination_obstacles defaults False), so the approach orbits.
# Arming destination-ignore drives straight at the NPC for the dialog.
def _move_to_npc(pos: Tuple[float, float]) -> BehaviorTree:
    return BT.Move(
        pos,
        tolerance=120.0,
        log=True,
        ignore_destination_obstacles=True,
        destination_obstacle_ignore_distance=2500.0,
        ignore_destination_npcs=True,
        ignore_destination_gadgets=True,
    )


def AggressiveEnv() -> Sequence[BehaviorTree]:
    return [
        ensure_botting_tree().Config.Aggressive(multi_account=_multi_account, auto_loot=True),
    ]


# Hero team setup
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


def _hero_party_already_formed(hero_ids: List[int]) -> bool:
    if not hero_ids:
        return False
    from Py4GWCoreLib import Party

    try:
        if not Map.IsOutpost():
            return False
        if not Party.IsPartyLoaded():
            return False
        if int(Party.GetPartySize() or 0) <= 1:
            return False
        existing_ids: set[int] = set()
        for hero in Party.GetHeroes() or []:
            try:
                hero_id = int(getattr(hero, "hero_id", 0) or 0)
            except (TypeError, ValueError):
                continue
            if hero_id > 0:
                existing_ids.add(hero_id)
        return all(int(hero_id) in existing_ids for hero_id in hero_ids)
    except Exception:
        return False


def _party_setup(route: Route) -> List[BehaviorTree]:
    if _multi_account:
        return [_multibox_party_setup()]
    return [SetupHeroTeam()]


def _multibox_party_already_formed() -> bool:
    from Py4GWCoreLib.routines_src.behaviourtrees_src.shared import (
        _account_emails_not_on_same_map_as_local,
        _account_is_in_local_party,
    )

    try:
        if _account_emails_not_on_same_map_as_local():
            return False
        sender_email = str(Player.GetAccountEmail() or "")
        if not sender_email:
            return False
        if GLOBAL_CACHE.ShMem.GetAccountDataFromEmail(sender_email) is None:
            return False
        for account in GLOBAL_CACHE.ShMem.GetAllAccountData() or []:
            receiver_email = str(getattr(account, "AccountEmail", "") or "")
            if not receiver_email or receiver_email == sender_email:
                continue
            if not _account_is_in_local_party(account):
                return False
    except Exception:
        return False
    return True


def _multibox_party_setup() -> BehaviorTree:
    def _party_intact(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
        return (
            BehaviorTree.NodeState.SUCCESS
            if _multibox_party_already_formed()
            else BehaviorTree.NodeState.FAILURE
        )

    return BT.Selector(
        name="MultiboxPartySetup",
        children=[
            BT.Sequence(
                name="PartyAlreadyFormed?",
                children=[
                    BehaviorTree(
                        BehaviorTree.ActionNode(
                            name="MultiboxPartyAlreadyFormed?",
                            action_fn=_party_intact,
                        )
                    ),
                    BT.LogMessage(
                        "Multibox party already formed - skipping disband/reinvite",
                        module_name=MODULE_NAME,
                    ),
                ],
            ),
            BT.CreateParty(multibox_invite=True),
        ],
    )


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

        def _team_present(_node: BehaviorTree.Node) -> BehaviorTree.NodeState:
            return (
                BehaviorTree.NodeState.SUCCESS
                if _hero_party_already_formed(hero_ids)
                else BehaviorTree.NodeState.FAILURE
            )

        # Selector mirrors the multibox pattern: the fallback branch holds the
        # ENTIRE re-formation (CreateParty itself opens with LeaveParty), so an
        # intact hero team is never taken apart and reloaded every cycle.
        return BT.Selector(
            name="HeroPartySetup",
            children=[
                BT.Sequence(
                    name="HeroTeamAlreadyFormed?",
                    children=[
                        BehaviorTree(
                            BehaviorTree.ActionNode(
                                name="HeroTeamAlreadyFormed?",
                                action_fn=_team_present,
                            )
                        ),
                        BT.LogMessage(
                            "Hero team already formed - skipping leave party",
                            module_name=MODULE_NAME,
                        ),
                    ],
                ),
                BT.Sequence(
                    name="Form Hero Team",
                    children=[
                        BT.CreateParty(hero_ids=hero_ids, log=False),
                        BT.Wait(1000),
                        *[BT.LoadHeroSkillbar(position, template) for position, template in skillbars],
                        CoreBT.Party.ForceHeroState(HERO_AGGRESSIVE_MODE),
                    ],
                ),
            ],
        )

    return BT.Subtree("Setup Hero Team", _build_team)


def _killing_loop(route: Route) -> BehaviorTree:
    """The vanquish-style farming loop for one faction run.

    Mirrors the Nightfall Leveler / VQFarm convention: travel to outpost,
    cross into the explorable map, then either run per-leg route segments
    (blessing + fight leg each) or collect the route's blessings and run its
    single kill path, wait out of combat, then resign back to the outpost.
    """
    children: List[BehaviorTree] = [
        BT.Travel(target_map_id=route.outpost_id, random_travel=True, hard_mode=True),
        *_party_setup(route),
    ]

    if route.key in ("kurzick", "luxon"):
        children.append(BT.EqualizeGold(target_gold=BLESSING_GOLD, log=True))
    if route.entry_dialog_id:
        children.append(_move_to_npc(route.exit_pos))
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

    def _take_blessing(blessing: Blessing) -> None:
        if route.key in ("kurzick", "luxon"):
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


    if route.segments:
        for index, segment in enumerate(route.segments, start=1):
            if segment.blessing is not None:
                _take_blessing(segment.blessing)
            if segment.path:
                children.append(
                    BT.VanquishNode(
                        steps=list(segment.path),
                        name=segment.name or f"{route.name} Leg {index}",
                        flag_heroes_to_waypoint=False,
                    )
                )
    else:
        for blessing in route.blessing_points:
            _take_blessing(blessing)

        if route.kill_path:
            children.append(
                BT.VanquishNode(
                    steps=list(route.kill_path),
                    name=f"{route.name} Kill Path",
                    flag_heroes_to_waypoint=False,
                )
            )

    children.append(BT.WaitUntilOutOfCombat())
    children.append(
        BT.Resign(
            wait_for_map_load=True,
            target_map_id=route.outpost_id,
            multi_account=_multi_account,
        )
    )

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
        BT.Travel(target_map_id=route.outpost_id, random_travel=True, hard_mode=True),
        *_party_setup(route),
    ]
    for point in route.pre_path:
        children.append(
            BehaviorTree(
                BehaviorTree.SelectorNode(
                    name="Pre-Path Needed?",
                    children=[
                        _near_exit_gate(route),
                        BT.Move(point, tolerance=150.0, log=True),
                    ],
                )
            )
        )
    children.append(BT.MoveAndExitMap(route.exit_pos, target_map_id=route.explorable_id))
    children.extend(AggressiveEnv())
    children.append(_move_to_npc(route.bounty_pos))
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
    children.append(
        BT.Resign(
            wait_for_map_load=True,
            target_map_id=route.outpost_id,
            multi_account=_multi_account,
        )
    )

    return BT.Sequence(name=f"{route.name} Bounty Run", children=children)
# ---------------------------------------------------------------------------
# Planner step builders
# ---------------------------------------------------------------------------
def _current_rank(route: Route) -> int:
    """Current tier index (1-based) of a route's title, 0 when unranked.

    Uses the same points scan as the live UI readout, so the goal check and
    the displayed tier always agree.
    """
    points = _faction_points(route)
    rank = 0
    for tier in TITLE_TIERS.get(int(route.title_id), []):
        if points >= tier.required:
            rank = int(tier.tier)
    return rank


def _route_goal_rank(route: Route) -> Optional[int]:
    """Target tier for a rank-tracked route, or None when no tier data exists.

    `_farm_to_max` pushes to the title's top tier; otherwise the route farms
    to `_target_rank` (default 5, where faction skills / most unlocks cap).
    """
    tiers = TITLE_TIERS.get(int(route.title_id), [])
    if not tiers:
        return None
    if _farm_to_max:
        return int(max(tier.tier for tier in tiers))
    return _target_rank


def _goal_threshold(route: Route) -> Optional[int]:
    """Point threshold at which the route is done.

    Kurzick/Luxon stop at the faction donate cap (FACTION_GOAL) — the Canthan
    donation loop, which has no reputation-rank target. All rank-tracked routes
    stop at the configured target: `_farm_to_max` pushes to the title's top
    tier, otherwise `_target_rank` (default 5). With no tier data the route
    never completes on points alone. The threshold is read live at tick time,
    so changing `_farm_to_max` / `_target_rank` needs no planner rebuild.
    """
    if route.key in ("kurzick", "luxon"):
        return FACTION_GOAL
    goal_rank = _route_goal_rank(route)
    if goal_rank is None:
        return None
    for tier in TITLE_TIERS.get(int(route.title_id), []):
        if int(tier.tier) == goal_rank:
            return int(tier.required)
    return None


def _build_farm_sequence(route: Route) -> BehaviorTree:
    def _goal_reached() -> BehaviorTree.NodeState:
        global _active_farm_key
        threshold = _goal_threshold(route)
        if threshold is None:
            return BehaviorTree.NodeState.FAILURE
        if _faction_points(route) >= threshold:
            return BehaviorTree.NodeState.SUCCESS
        _active_farm_key = route.key
        return BehaviorTree.NodeState.FAILURE

    def _one_run() -> BehaviorTree:
        run_loop = _bounty_loop(route) if route.bounty else _killing_loop(route)
        retried_run = BehaviorTree(
            BehaviorTree.RepeaterUntilSuccessNode(
                child=run_loop.root,
                timeout_ms=RUN_RETRY_TIMEOUT_MS,
                name=f"{route.name} Run Retry",
            )
        )
        return BehaviorTree(
            BehaviorTree.SelectorNode(
                name=f"{route.name} Run Or Skip",
                children=[
                    BehaviorTree(BehaviorTree.ActionNode(name="Goal Reached?", action_fn=_goal_reached)),
                    retried_run,
                ],
            )
        )

    return BT.Sequence(
        name=f"Farm {route.name}",
        children=[
            BT.Repeater(name=f"Farm {route.name}", repeat_count=VQ_MAX_RUNS, children=[_one_run()]),
        ],
    )


def FarmFaction() -> BehaviorTree:
    route = _route_by_key(selected_key)
    if route is None:
        return BT.LogMessage(f"Unknown faction: {selected_key}", module_name=MODULE_NAME)
    return _build_farm_sequence(route)


def FarmAll() -> BehaviorTree:
    children: List[BehaviorTree] = []
    for route in _reputation_routes():
        threshold = _goal_threshold(route)
        if threshold is None:
            continue
        children.append(_build_farm_sequence(route))
    if not children:
        return BT.LogMessage(
            "All reputation routes have reached the target rank.",
            module_name=MODULE_NAME,
        )
    return BT.Sequence(name="Farm All Reputation", children=children)


HOUSE_ZU_HELZER = 77    # Kurzick donation outpost
CAVALON = 193           # Luxon donation outpost


def DonateFaction() -> BehaviorTree:
    route = _route_by_key(selected_key)
    if route is None:
        return BT.LogMessage(f"Unknown faction: {selected_key}", module_name=MODULE_NAME)
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
    if _farm_all:
        return [("Farm All Reputation", FarmAll)]
    steps: List[Tuple[str, Callable[[], BehaviorTree]]] = [("Farm Faction", FarmFaction)]
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
        consumable_upkeeps=_enabled_consumable_upkeeps(),
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
        botting_tree.UI.override_draw_help(_draw_help_tab)
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
        if PyImGui.begin_tab_item("Consumables"):
            _draw_consumables_settings()
            PyImGui.end_tab_item()
        PyImGui.end_tab_bar()


def _draw_consumables_settings() -> None:
    """Cons / Pcons usage toggles; applied live to the running tree."""
    global _activate_conset, _activate_pcons

    PyImGui.text("Consumable Upkeep")
    PyImGui.separator()
    PyImGui.text("Only affects items already in inventory or storage-restocked elsewhere.")

    new_conset = PyImGui.checkbox("Use Consets (Essence / Grail / Armor)", _activate_conset)
    if new_conset != _activate_conset:
        _activate_conset = new_conset
        _apply_consumable_upkeep_change()

    new_pcons = PyImGui.checkbox("Use Pcons (Cupcake, Kabob, Pie, ...)", _activate_pcons)
    if new_pcons != _activate_pcons:
        _activate_pcons = new_pcons
        _apply_consumable_upkeep_change()


def _apply_consumable_upkeep_change() -> None:
    """Re-push the upkeep service so toggles apply without a tree rebuild.

    ConfigureUpkeep only replaces the upkeep trees; it does not reset the
    running planner (same runtime-reconfigure pattern as Shards Of Orr BT).
    """
    if botting_tree is None:
        return
    _configure_upkeep(botting_tree)

# ---------------------------------------------------------------------------
# Statistics tab (per-account title progress; modeled on Sunspear title farm)
# ---------------------------------------------------------------------------
_session_baselines: Dict[str, int] = {}
_session_start_times: Dict[str, float] = {}


def _stats_accounts() -> List[Any]:
    """Accounts shown on the Statistics tab.

    Multibox mode shows every shared-memory account; single-account mode shows
    only the local account (heroes do not carry reputation titles).
    """
    accounts = list(GLOBAL_CACHE.ShMem.GetAllAccountData())
    if _multi_account:
        return accounts
    own_email = str(Player.GetAccountEmail() or "").strip()
    filtered = [
        account for account in accounts
        if str(getattr(account, "AccountEmail", "") or "").strip() == own_email
    ]
    if filtered:
        return filtered
    own_name = str(Player.GetName() or "")
    return [
        account for account in accounts
        if str(getattr(account.AgentData, "CharacterName", "") or "") == own_name
    ]


def _draw_title_track(route: Route) -> None:
    """Per-account title/tier/points-to-next readout for the selected route."""
    global _session_baselines, _session_start_times

    title_idx = int(route.title_id)
    tiers = TITLE_TIERS.get(route.title_id, [])
    now = time.time()
    accounts = _stats_accounts()
    if not accounts:
        PyImGui.text("No account statistics available yet.")
        return

    for account in accounts:
        try:
            name = str(account.AgentData.CharacterName or "Unknown")
            pts = int(account.TitlesData.Titles[title_idx].CurrentPoints)
        except Exception:
            continue

        if name not in _session_baselines:
            _session_baselines[name] = pts
            _session_start_times[name] = now

        tier_name = "Unranked"
        tier_rank = 0
        tier_max_rank = len(tiers)
        next_required = tiers[0].required if tiers else 0
        for index, tier in enumerate(tiers):
            if pts >= tier.required:
                tier_rank = index + 1
                tier_name = tier.name
                next_required = tiers[index + 1].required if index + 1 < len(tiers) else tier.required
            else:
                next_required = tier.required
                break

        gained = pts - _session_baselines[name]
        elapsed = now - _session_start_times[name]
        formatted_time = time.strftime("%H:%M:%S", time.gmtime(elapsed))
        pts_per_hour = int(gained / elapsed * 3600) if elapsed > 0 else 0
        is_maxed = bool(tiers) and pts >= tiers[-1].required
        points_to_next = max(next_required - pts, 0)

        PyImGui.separator()
        PyImGui.text(f"{name} - {tier_name} [{tier_rank}/{tier_max_rank}]")
        PyImGui.text(f"Total Points: {pts:,}")
        if is_maxed:
            PyImGui.text("Next Rank: Maxed")
            PyImGui.text("Points To Go: 0")
            PyImGui.progress_bar(1.0, -1, 0, "Complete")
            PyImGui.text_colored("Maximum rank achieved. Title complete.", (0.4, 1.0, 0.4, 1.0))
        else:
            PyImGui.text(f"Next Rank: {next_required:,}")
            PyImGui.text(f"Points To Go: {points_to_next:,}")
            total = max(next_required, 1)
            PyImGui.progress_bar(min(max(pts, 0) / total, 1.0), -1, 0, f"{max(pts, 0):,} / {total:,}")
        PyImGui.text(f"+{gained:,} points ({pts_per_hour:,}/hr) - Running for: {formatted_time}")


def _active_route() -> Optional[Route]:
    """The route the UI should track.

    In auto-rotate mode this is the route currently being farmed (`_active_farm_key`,
    set live by the goal check). Before the planner has ticked (or if it is not
    currently tracking yet), fall back to the first reputation route that still
    needs work — so the Stats tab shows the real target (e.g. Lightbringer) on a
    character where the other five are already done, instead of the preselected
    Vanguard. In single mode it is simply the selected route.
    """
    if _farm_all:
        if _active_farm_key:
            route = _route_by_key(_active_farm_key)
            if route is not None:
                return route
        for route in _reputation_routes():
            threshold = _goal_threshold(route)
            if threshold is None:
                continue
            if _faction_points(route) < threshold:
                return route
        routes = _reputation_routes()
        return routes[0] if routes else None
    return _route_by_key(selected_key)


def _draw_statistics_tab() -> None:
    """Top-level Statistics tab showing the active route's title progress.

    In auto-rotate mode this follows the route currently being farmed (falling
    back to the next route that still needs work before the planner has ticked);
    in single mode it is the selected route.
    """
    active = _active_route()
    if active is None:
        PyImGui.text("No route selected.")
        return
    if PyImGui.begin_child("ReputationFarmerStatisticsChild", (500, 620), False):
        _draw_title_track(active)
    PyImGui.end_child()




def _draw_help_tab() -> None:
    """Help tab: practical notes for running the Reputation Farmer effectively."""

    def _section(title: str) -> None:
        PyImGui.separator()
        PyImGui.text(title)
        PyImGui.separator()

    _section("What this farm does")
    PyImGui.text_wrapped(
        "Farms faction reputation (title) points for one selected route or for every "
        "rank-tracked route in rotation. Six routes are EotN / Nightfall titles with a "
        "rank ladder (Vanguard, Asuran, Norn, Deldrimor, Sunspear, Lightbringer). "
        "Luxon and Kurzick are the Canthan faction loop: they farm on-hand faction "
        "points and donate them to the guild hall instead of tracking a title rank."
    )

    _section("Two farm modes")
    PyImGui.text_wrapped(
        "Single mode (Farm Faction) runs only the route selected in the picker. "
        "Auto-rotate (Farm All Reputation) runs every rank-tracked route in turn and "
        "skips any route that already reached the target. Toggling the mode rebuilds "
        "the planner and resets the routine to its first step, so pick your mode before "
        "starting a long session."
    )

    _section("Target rank")
    PyImGui.text_wrapped(
        "Rank 5 is where faction skills and most unlocks cap for the EotN / Nightfall "
        "titles, so it is the default stopping point. Max rank pushes a route to the "
        "top of its title tier. The goal is checked live from your title points, so "
        "changing the target mid-run needs no rebuild: routes that already qualify skip "
        "and unfinished ones continue from where they left off."
    )
    PyImGui.text_wrapped(
        "Once every route in the active mode has already reached Rank 5, the Rank 5 "
        "option disappears from the Farm to dropdown and only Max rank remains. Since "
        "all titles are already at the lower target, the bot automatically pushes on "
        "to the top tier. In auto-rotate this applies when all six reputation routes "
        "are at rank 5 or higher; in single-faction mode it applies to the selected "
        "route alone."
    )

    _section("Vanquish vs bounty routes")
    PyImGui.text_wrapped(
        "Vanquish routes enter the explorable map, take the route's shrine blessings, "
        "and clear their kill path. Sunspear and Lightbringer are bounty loops: each "
        "run walks to the bounty priest, accepts the bounty through the dialog, then "
        "clears the kill path. Both loop types travel to the route's outpost on hard "
        "mode and resign back to it at the end of every run."
    )

    _section("Party setup")
    PyImGui.text_wrapped(
        "- Single account: the hero team is sized to the outpost's max party size "
        "(4/6/8 presets). Edit the hero slots and skillbar templates on the Party tab "
        "and Save. The team is re-formed at the start of a run only when a hero is "
        "missing; an intact team is left alone."
    )
    PyImGui.text_wrapped(
        "- Multibox: enable Multi Account (Multibox) Team before starting - the toggle "
        "rebuilds the tree and resets the planner. The bot summons and invites every "
        "account from shared memory, and only re-forms the party when an account is "
        "missing or on a different map. Make sure every account is loaded before you "
        "start."
    )

    _section("Practical tips")
    PyImGui.text_wrapped(
        "- A route's outpost must be unlocked: the bot travels to it every run and "
        "enters the explorable on hard mode."
    )
    PyImGui.text_wrapped(
        "- Luxon / Kurzick blessings require bribing the faction priest. The bot tops "
        "gold up to 500g while in the outpost before each run, so keep at least that "
        "much reachable from storage."
    )
    PyImGui.text_wrapped(
        "- Consumable upkeep: toggle consets and pcons in Settings - Consumables. "
        "Keep them in inventory or storage so the upkeep service can restock."
    )
    PyImGui.text_wrapped(
        "- Runs retry in place (up to 30 minutes) before the planner restarts the "
        "step from the outpost, so a single autopath miss usually does not waste the "
        "run or the party."
    )
    PyImGui.text_wrapped(
        "- Progress is measured by title points (or on-hand faction for Luxon / "
        "Kurzick), not by the number of runs. The farm runs 6 runs per planner pass "
        "and the planner repeats, so leave it alone until the readout shows the "
        "target rank or donate cap is reached."
    )


def _rebuild_main_routine() -> None:
    """Rebuild the planner tree from the current step list (mode / route change).

    The plan step list changes between `Farm Faction` and `Farm All
    Reputation`, and the Donate step only exists for Luxon / Kurzick routes,
    so a rebuild is required whenever those change. Target-rank changes are
    read live and do not need one.
    """
    ensure_botting_tree().SetMainRoutine(
        get_execution_steps(),
        name=ROUTINE_NAME,
        repeat=True,
    )


def _apply_route_selection(new_key: str) -> None:
    """Switch the active faction route and rebuild the planner tree.

    Resets the routine to its first step, which is intended on a faction
    switch.
    """
    global selected_key
    if new_key == selected_key:
        return
    selected_key = new_key
    _rebuild_main_routine()


def _apply_rotation_mode(enable_all: bool) -> None:
    """Turn auto-rotate on/off and rebuild the planner for the new step list.

    The mode changes the plan from `Farm Faction` to `Farm All Reputation`, so
    the tree must be rebuilt; the rank selector inside each mode is read live.
    """
    global _farm_all
    if enable_all == _farm_all:
        return
    _farm_all = enable_all
    _rebuild_main_routine()


def _all_farmed_routes_at_target() -> bool:
    """True when every route the current mode farms is already at the target rank.

    Auto-rotate checks all reputation routes; single mode checks just the
    selected route. When true, the "Rank {_target_rank}" selector option is
    hidden so the only forward choice is Max rank.
    """
    routes = _reputation_routes() if _farm_all else [r for r in [_route_by_key(selected_key)] if r]
    if not routes:
        return False
    return all(_current_rank(route) >= _target_rank for route in routes)


def _draw_farm_controls(id_suffix: str = "") -> None:
    """Rotation-mode + target-rank controls, shared by the Settings and Main tabs.

    Auto-rotate farms every reputation route (the six EotN / Nightfall titles)
    to the target; single mode farms only `selected_key`. The rank selector
    picks the stopping point: Rank 5 (where faction skills / most unlocks cap)
    or Max rank. Toggling the mode rebuilds the planner (the step list changes
    between `Farm Faction` and `Farm All Reputation`); the rank selector is
    read live by the goal check, so it needs no rebuild.

    `id_suffix` keeps ImGui widget IDs unique when this is drawn in more than
    one place at once (Main body + Settings tab), or ImGui raises conflicting
    ID errors.
    """
    global _farm_all, _farm_to_max
    new_all = PyImGui.checkbox(f"Auto-rotate all reputation factions##{id_suffix}", _farm_all)
    if new_all != _farm_all:
        _apply_rotation_mode(new_all)
    only_max = _all_farmed_routes_at_target()
    if only_max and not _farm_to_max:
        _farm_to_max = True
    target_labels = ["Max rank"] if only_max else [f"Rank {_target_rank}", "Max rank"]
    target_index = 0 if only_max else (1 if _farm_to_max else 0)
    new_index = PyImGui.combo(f"Farm to##{id_suffix}", target_index, target_labels)
    if new_index != target_index:
        _farm_to_max = bool(new_index)


def _draw_route_selector() -> None:
    """Radio-list farm picker shared by the Settings and Main tabs."""
    route_index_by_key = {route.key: index for index, route in enumerate(ALL_ROUTES)}
    selected_index = route_index_by_key.get(selected_key, 0)

    for index, route in enumerate(ALL_ROUTES):
        label = route.name + ("  (bounty loop)" if route.bounty else "")
        selected_index = PyImGui.radio_button(label, selected_index, index)

    _apply_route_selection(ALL_ROUTES[selected_index].key)


def _draw_route_readout(route: Route) -> None:
    points = _faction_points(route)
    tiers = TITLE_TIERS.get(int(route.title_id), [])
    tier_name = "Unranked"
    for tier in tiers:
        if points >= tier.required:
            tier_name = tier.name
    PyImGui.text(f"{route.name} points: {points:,}")
    PyImGui.text(f"Current tier: {tier_name}")
    threshold = _goal_threshold(route)
    if route.key in ("kurzick", "luxon"):
        goal = f"donate cap ({threshold:,} on-hand)" if threshold is not None else "donate cap"
    else:
        goal_rank = _route_goal_rank(route)
        target = "max rank" if goal_rank is None else f"rank {goal_rank}"
        goal = f"{target} ({threshold:,} points)" if threshold is not None else target
    PyImGui.text(f"Session goal: {goal}")


def _draw_faction_settings_tab() -> None:
    """Faction selector + rotation / target + multibox toggle + live readout."""
    global selected_key, botting_tree, _multi_account
    PyImGui.text("Faction")
    PyImGui.separator()

    _draw_farm_controls("Settings")

    PyImGui.separator()

    new_multi = PyImGui.checkbox("Multi Account (Multibox) Team", _multi_account)
    if new_multi != _multi_account:
        _multi_account = new_multi
        botting_tree = None
    PyImGui.separator()

    if _farm_all:
        PyImGui.text("Auto-rotate: every reputation faction is farmed to the target rank.")
        PyImGui.text("The picker below only applies in single-faction mode.")
        PyImGui.separator()

    _draw_route_selector()

    PyImGui.separator()
    display = _active_route()
    if display is not None:
        _draw_route_readout(display)


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
        if _farm_all:
            active = _active_route()
            active_name = active.name if active else "All reputation factions"
            PyImGui.text(f"Current farm: Auto-rotate -> {active_name}")
        else:
            selected = _route_by_key(selected_key)
            current_farm = selected.name if selected else selected_key
            PyImGui.text(f"Current farm: {current_farm}")
        PyImGui.text(f"HeroAI: {self.parent.GetBlackboardValue('HEROAI_STATUS', 'Idle')}")
        PyImGui.text(f"Planner: {self.parent.GetBlackboardValue('PLANNER_STATUS', 'Idle')}")
        PyImGui.end_table()

    _draw_farm_controls("Main")
    if _farm_all:
        PyImGui.text("Auto-rotate: every reputation faction farmed to the target rank.")
    else:
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
    extra_tabs: List[Tuple[str, Callable[[], None]]] = [("Statistics", _draw_statistics_tab)]
    if not _multi_account:
        extra_tabs.append(("Party", draw_party_tab))
    tree.UI.draw_window(
        icon_path=os.path.join(PySystem.Console.get_projects_path(), MODULE_ICON),
        main_child_dimensions=(520, 420),
        extra_tabs=extra_tabs,
    )


def tooltip() -> str:
    return MODULE_NAME + " - selectable all-in-one faction/title farmer (BT)."
